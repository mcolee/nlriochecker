"""Bestaat elke GWSW-naam die dit pakket gebruikt werkelijk in de ontologie?

De aanleiding staat in issue #30: twee keer op rij is beweerd dat een GWSW-klasse
niet bestond terwijl ze gewoon in `Ontologie_GWSW_Totaal.ttl` staat, en beide keren
corrigeerde de auteur dat en niet een test. Deze module maakt die controle
mechanisch: hij verzamelt elke GWSW-naam die de configuratie en de code noemen en
houdt die naast de ontologie.

Drie ontwerpkeuzes dragen de test:

* **De termen worden nergens overgeschreven.** Ze komen uit de geladen `CheckConfig`,
  de `PlausibilityTables`, de symbolentabellen en een AST-sweep over `src/`. Een
  handgeschreven kopie zou uit de pas lopen en dan toetst de test zichzelf.
* **Er wordt op `rdf:type` getoetst, niet op "komt de naam voor in de TTL".**
  `Kunststof` bestaat, maar als lid van `MateriaalAfsluiterColl`; als putmateriaal is
  hij nergens legaal. Een naamvergelijking laat die fout door.
* **De uitkomst hangt aan `BEKENDE_AFWIJKINGEN`, in twee richtingen.** Een nieuwe
  schending die niet op de lijst staat maakt de test rood, en een term die van de
  lijst af had gemoeten ook. De inhoud van die lijst is het werk van issue #31.

De test gaat *uitsluitend* over de vraag of een begrip in het model bestaat. Of er
instanties van in een dataset voorkomen is een andere vraag met een ander antwoord.

**Wat waar draait.** De ontologie zelf is 2,6 MB en staat buiten versiebeheer, dus de
test leest niet de TTL maar de getrackte afgeleide `data/gwsw-vocabulaire-index.json`:
per GWSW-naam zijn `rdf:type`s, en niets meer. Daardoor draait alles hier gewoon mee
op de CI-runner -- dat was het hele punt van #30, en eerder sloegen daar 140 van de
142 gevallen over. Het bestand is geen invoerdata maar een afgeleide; het wordt nooit
met de hand bijgewerkt maar met `scripts/maak_gwsw_index.py`.

Eén test draait alleen lokaal: `test_index_volgt_de_ontologie` vergelijkt de getrackte
index met een vers geparseerde ontologie, en die kan hij alleen doen op een machine
waar `data/gwsw_ontologieen/` staat. Zonder die test zou de index stil verouderen
zodra de auteur GWSW 1.7 neerzet, en dan bewaakte deze module een verleden dat
niemand meer draait. Automatisch ophalen bij data.gwsw.nl is geen alternatief:
`CLAUDE.md` verbiedt dat expliciet, en upgraden is met opzet handwerk van de auteur.

Er zit met opzet **geen skip** op het inlezen van de index: ontbreekt het bestand, dan
valt de hele module om. Een skip zou de oude stilte in een nieuwe vorm terugbrengen.
"""

from __future__ import annotations

import ast
import difflib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from nlriochecker.checkconfig import ClassRoots, load_check_config
from nlriochecker.dataset import VULWAARDE_KENMERKEN
from nlriochecker.plausibiliteit import load_plausibility
from nlriochecker.uitvoer.stijlen.symbolen import LIJNSYMBOLEN, PUNTSYMBOLEN

WORTEL = Path(__file__).resolve().parents[1]
BRON = WORTEL / "src" / "nlriochecker"
PROJECTCONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"
INDEXBESTAND = WORTEL / "data" / "gwsw-vocabulaire-index.json"
INDEXSCRIPT = WORTEL / "scripts" / "maak_gwsw_index.py"

OWL = "http://www.w3.org/2002/07/owl#"
OWL_KLASSE = f"{OWL}Class"

# Hoe veel gelijkenis een bestaande naam nodig heeft om als "bedoelde u" te dienen.
# Lager dan de 0,6 van difflib: `Muil` tegenover `Muilprofiel` haalt 0,53, en juist
# die suggestie had de fout uit #31 punt 1 voorkomen.
SUGGESTIEDREMPEL = 0.5

# De GWSW-namen die het pakket gebruikt maar die hier (nog) niet als schending
# gelden, elk met de reden. De lijst is het resultaat van de audit uit #30; issue #31
# ruimt hem op. Wie hier een term afvoert terwijl hij nog schendt, of laat staan
# terwijl hij opgeruimd is, krijgt een rode test.
BEKENDE_AFWIJKINGEN: dict[str, str] = {
    "AHN5": (
        "ontbreekt in de ontologie -- WijzeVanInwinningColl stopt bij AHN4. Blijft "
        "bewust staan: de waarde loopt vooruit op een toekomstige GWSW-versie, het "
        "besluit ligt bij de auteur (#31 punt 4)."
    ),
    "Interneoverstortput": (
        "hoofdletterafwijking -- de ontologie schrijft InterneOverstortput. Werkt wel, "
        "want de symboolkeuze en het QML-filter vergelijken hoofdletterongevoelig "
        "(#31 punt 5)."
    ),
    "Kunststof": (
        "verkeerde collectie -- bestaat als lid van MateriaalAfsluiterColl, "
        "MaterialOfStepsColl en Uitvoering, maar niet van MateriaalPutColl. Geen enkele "
        "legale export kan die waarde op een put schrijven (#31 punt 3)."
    ),
    "Metselwerk": (
        "bewuste afwijking -- zit in MateriaalLeidingColl en niet in MateriaalPutColl, "
        "maar De Wolden schrijft gwsw:Metselwerk feitelijk op 33 putten. De regel blijft "
        "staan; dat de export buiten de domeinlijst valt hoort ADM-005 te melden "
        "(#31 punt 6)."
    ),
    "Muilprofiel": (
        "ontbreekt in de ontologie -- de term is Muil. Kost vandaag een valse ATTR-012 "
        "en een ATTR-004-regel die nooit vuurt (#31 punt 1)."
    ),
    "Vacuumgemaal": (
        "ontbreekt in de ontologie -- alleen Sym_Vacuumgemaal bestaat, en dat is een "
        "symboolklasse en geen objecttype. De symboolregel krijgt nooit een treffer "
        "(#31 punt 2)."
    ),
    "Verholengoot": (
        "hoofdletterafwijking -- de ontologie schrijft VerholenGoot. Werkt wel, om "
        "dezelfde reden als Interneoverstortput (#31 punt 5)."
    ),
}


@dataclass(frozen=True)
class Term:
    """Een GWSW-naam zoals het pakket hem gebruikt, met zijn vindplaats.

    `collectie` is het `rdf:type` dat de ontologie op die plek hoort te geven: een
    collectienaam voor een domeinlijstwaarde, en anders `owl:Class`.
    """

    naam: str
    vindplaats: str
    collectie: str = OWL_KLASSE


def _kort(soort: str) -> str:
    """Een `rdf:type` in leesbare vorm: `owl:Class` in plaats van de hele URI."""
    return f"owl:{soort.removeprefix(OWL)}" if soort.startswith(OWL) else soort


@dataclass(frozen=True)
class Schending:
    """Een term die de ontologie niet zo kent als het pakket hem gebruikt."""

    term: Term
    soort: str
    gevonden: tuple[str, ...]
    suggestie: str

    def __str__(self) -> str:
        """De melding in de vorm die #30 voorschrijft: vindplaats, eis, alternatief."""
        kop = (
            f"{self.term.naam} komt niet voor in Ontologie_GWSW_Totaal.ttl."
            if self.soort == "ontbreekt"
            else f"{self.term.naam}: {self.soort}."
        )
        verwacht = (
            "owl:Class"
            if self.term.collectie == OWL_KLASSE
            else f"lid van gwsw:{self.term.collectie}"
        )
        regels = [
            kop,
            f"  gebruikt in: {self.term.vindplaats}",
            f"  verwacht:    {verwacht}",
        ]
        if self.gevonden:
            regels.append(f"  gevonden:    {', '.join(_kort(soort) for soort in self.gevonden)}")
        if self.suggestie:
            regels.append(f"  bedoelde u:  {self.suggestie}")
        return "\n".join(regels)


def _termen_uit_config(pad: Path | None, herkomst: str) -> list[Term]:
    """De GWSW-namen uit een checkconfiguratie, via de pydantic-velden.

    De velden worden uit `ClassRoots.model_fields` gehaald en niet met de hand
    opgesomd: een nieuwe rol in de configuratie komt zo vanzelf onder de test te
    vallen. De sleutels van `stelseltypen` zijn projectnamen (`gemengd`) en geen
    GWSW-begrippen; alleen de waarden tellen mee.
    """
    config = load_check_config(pad)
    termen: list[Term] = []
    for veld in ClassRoots.model_fields:
        waarde = getattr(config.klassen, veld)
        if isinstance(waarde, dict):
            for sleutel, klassen in waarde.items():
                termen += [Term(naam, f"{herkomst} [klassen.{veld}] {sleutel}") for naam in klassen]
            continue
        termen += [Term(naam, f"{herkomst} [klassen] {veld}") for naam in waarde]
    for regel in config.puttyperegels:
        termen.append(Term(regel.puttype, f"{herkomst} [[puttyperegels]] puttype"))
        termen += [
            Term(naam, f"{herkomst} [[puttyperegels]] {regel.puttype}.vereist_een_van")
            for naam in regel.vereist_een_van
        ]
    for veld in ("uit_hoogtemodel", "onbekend"):
        termen += [
            Term(naam, f"{herkomst} [inwinning] {veld}", "WijzeVanInwinningColl")
            for naam in getattr(config.inwinning, veld)
        ]
    termen += [
        Term(naam, f"{herkomst} [vulwaarden] hoogte_kenmerken")
        for naam in config.vulwaarden.hoogte_kenmerken
    ]
    return termen


def _termen_uit_plausibiliteit() -> list[Term]:
    """De materialen en profielvormen uit de vijf plausibiliteitstabellen.

    Elk veld draagt zijn eigen verwachte collectie mee: een putmateriaal hoort in
    `MateriaalPutColl` en niet in zomaar enige materiaalcollectie. Dat onderscheid is
    de reden dat deze test op `rdf:type` toetst en niet op het bestaan van de naam.
    """
    tabellen = load_plausibility()
    termen: list[Term] = []
    for regel in tabellen.materiaal_diameter:
        termen.append(
            Term(
                regel.materiaal,
                "plausibiliteit.toml [[materiaal_diameter]]",
                "MateriaalLeidingColl",
            )
        )
    for regel in tabellen.materiaal_aanlegjaar:
        termen.append(
            Term(
                regel.materiaal,
                "plausibiliteit.toml [[materiaal_aanlegjaar]]",
                "MateriaalLeidingColl",
            )
        )
    for regel in tabellen.materiaal_vorm:
        termen.append(
            Term(regel.materiaal, "plausibiliteit.toml [[materiaal_vorm]]", "MateriaalLeidingColl")
        )
        termen += [
            Term(
                naam,
                f"plausibiliteit.toml [[materiaal_vorm]] {regel.materiaal}.toegestane_vormen",
                "VormLeidingColl",
            )
            for naam in regel.toegestane_vormen
        ]
    for regel in tabellen.leiding_put_materiaal:
        termen.append(
            Term(
                regel.leidingmateriaal,
                "plausibiliteit.toml [[leiding_put_materiaal]]",
                "MateriaalLeidingColl",
            )
        )
        termen += [
            Term(
                naam,
                f"plausibiliteit.toml [[leiding_put_materiaal]] "
                f"{regel.leidingmateriaal}.verwachte_putmaterialen",
                "MateriaalPutColl",
            )
            for naam in regel.verwachte_putmaterialen
        ]
    termen += [
        Term(regel.vorm, "plausibiliteit.toml [[vorm_afmeting]]", "VormLeidingColl")
        for regel in tabellen.vorm_afmeting
    ]
    return termen


# De methoden waarmee een object een kenmerk bij zijn GWSW-naam opvraagt. Het eerste
# argument is de klassenaam van het aspect.
KENMERKLEZERS = frozenset({"aspect", "number", "reference", "date"})


def _termen_uit_broncode() -> list[Term]:
    """De aspectnamen die als stringliteraal in `src/` staan, via een AST-sweep.

    `"Begindatum"`, `"MateriaalPut"` en `"HoogtePut"` staan nergens centraal, en een
    constantenlijst zou achterlopen zodra iemand er een literaal bij zet. De sweep
    ziet daarom de aanroep zelf. Wat hij niet ziet: een naam die eerst in een tuple
    of een veld belandt en pas daarna wordt doorgegeven (`_grootste_putmaat` doet
    dat). Die namen blijven ongetoetst tot ze een directe aanroep worden.
    """
    termen: list[Term] = []
    for pad in sorted(BRON.rglob("*.py")):
        boom = ast.parse(pad.read_text(encoding="utf-8"))
        for knoop in ast.walk(boom):
            if not isinstance(knoop, ast.Call) or not isinstance(knoop.func, ast.Attribute):
                continue
            if knoop.func.attr not in KENMERKLEZERS or not knoop.args:
                continue
            eerste = knoop.args[0]
            if isinstance(eerste, ast.Constant) and isinstance(eerste.value, str):
                plek = f"{pad.relative_to(BRON).as_posix()}:{knoop.lineno} .{knoop.func.attr}()"
                termen.append(Term(eerste.value, plek))
    return termen


def _alle_termen() -> list[Term]:
    """Elke GWSW-naam die het pakket gebruikt, met vindplaats.

    `dekking.toml` en `shaclrapport.py` doen bewust niet mee: die dragen namen van
    SHACL-vormen van de validatieserver (`LengteLeiding_val`, `CfkTypes_typ`), geen
    ontologiebegrippen. Ze zouden gegarandeerd vals alarm geven.
    """
    return [
        *_termen_uit_config(None, "checks.toml"),
        *_termen_uit_config(PROJECTCONFIG, "configs/dewoldenhoogeveen.toml"),
        *_termen_uit_plausibiliteit(),
        *[Term(naam, "symbolen.py PUNTSYMBOLEN") for naam in PUNTSYMBOLEN],
        *[Term(naam, "symbolen.py LIJNSYMBOLEN") for naam in LIJNSYMBOLEN],
        *[Term(naam, "dataset.py VULWAARDE_KENMERKEN") for naam in sorted(VULWAARDE_KENMERKEN)],
        *_termen_uit_broncode(),
    ]


TERMEN = _alle_termen()
NAMEN = sorted({term.naam for term in TERMEN})


def _laad_index() -> dict[str, frozenset[str]]:
    """De getrackte afgeleide van de totaal-ontologie: naam naar `rdf:type`s.

    Bewust zonder terugval en zonder skip: is het bestand er niet, dan valt de module
    om in plaats van stil groen te worden. Uit Totaal en niet uit de deelmodellen,
    want die dragen een conversiedatum uit 2021 en missen klassen die wel degelijk
    bestaan (`Overnamepunt`, `LozePut`, `Valput`).
    """
    document = json.loads(INDEXBESTAND.read_text(encoding="utf-8"))
    return {naam: frozenset(soorten) for naam, soorten in document["termen"].items()}


INDEX = _laad_index()


@pytest.fixture(scope="session")
def gwsw_index() -> dict[str, frozenset[str]]:
    """De vocabulaire-index, als fixture voor de tests die hem bevragen."""
    return INDEX


def _schending(term: Term, index: dict[str, frozenset[str]]) -> Schending | None:
    """Toetst een term tegen de index; None als de ontologie hem zo kent.

    Een naam die alleen in hoofdlettergebruik afwijkt krijgt een eigen soort. De
    lookups in het pakket zijn hoofdletterongevoelig, dus zo'n term werkt gewoon;
    hem als ontbrekend melden zou de volgende ontwikkelaar aanzetten hem te
    schrappen -- precies de fout die deze test moet voorkomen.
    """
    soorten = index.get(term.naam)
    if soorten is None:
        anders = next((naam for naam in index if naam.lower() == term.naam.lower()), None)
        if anders is not None:
            return Schending(
                term,
                "hoofdletterafwijking",
                tuple(sorted(index[anders])),
                f"{anders} (zelfde begrip)",
            )
        return Schending(term, "ontbreekt", (), _suggestie(term, index))
    if term.collectie not in soorten:
        return Schending(
            term, "verkeerde collectie", tuple(sorted(soorten)), _suggestie(term, index)
        )
    return None


def _suggestie(term: Term, index: dict[str, frozenset[str]]) -> str:
    """De dichtstbijzijnde bestaande naam, bij voorkeur uit de verwachte collectie.

    Dit is de regel waar het #30 om begonnen is: wie leest dat `Muilprofiel` niet
    bestaat weet nog niet dat de term `Muil` is. Er wordt eerst binnen de verwachte
    collectie gezocht, zodat een profielvorm geen bodemprofiel voorgesteld krijgt.
    """
    leden = sorted(naam for naam in index if term.collectie in index[naam])
    nabij = difflib.get_close_matches(
        term.naam, leden or sorted(index), n=1, cutoff=SUGGESTIEDREMPEL
    )
    if not nabij:
        return ""
    soorten = ", ".join(_kort(soort) for soort in sorted(index[nabij[0]]))
    return f"{nabij[0]} ({soorten})"


def _schendingen(naam: str, index: dict[str, frozenset[str]]) -> list[Schending]:
    """Elke schending van deze naam, over al zijn vindplaatsen."""
    gevonden = (_schending(term, index) for term in TERMEN if term.naam == naam)
    return [schending for schending in gevonden if schending is not None]


SENTINELS = ("Inspectieput", "Beton", "Rond", "Begindatum")


def test_de_termen_zijn_gevonden() -> None:
    """Zonder termen zou elke andere test hier groen zijn zonder iets te toetsen."""
    assert len(NAMEN) > 100
    assert set(SENTINELS) <= set(NAMEN)


def test_de_index_is_niet_uitgehold() -> None:
    """De keerzijde: een index die termen kwijtraakt mag niet ongemerkt doorgaan.

    Een krimpende index maakt de vocabulairetest weliswaar róder en niet groener --
    een naam die er niet in staat heet "ontbreekt" -- maar een index die zijn
    collectielidmaatschappen kwijtraakt zou de collectietoets uithollen zonder dat er
    iets rood wordt. Vandaar een ondergrens op het aantal termen, de vier sentinels,
    en het bestaan van de vier collecties waarop de rest van deze module leunt.
    """
    assert len(INDEX) > 3_000, f"{INDEXBESTAND.name} draagt maar {len(INDEX)} termen"
    for naam in SENTINELS:
        assert naam in INDEX, naam
    for collectie in (
        "MateriaalLeidingColl",
        "MateriaalPutColl",
        "VormLeidingColl",
        "WijzeVanInwinningColl",
    ):
        assert [naam for naam in INDEX if collectie in INDEX[naam]], collectie


@pytest.mark.parametrize("naam", NAMEN)
def test_gwsw_naam_bestaat_in_de_ontologie(
    naam: str, gwsw_index: dict[str, frozenset[str]]
) -> None:
    """Elke gebruikte GWSW-naam bestaat, en in de collectie waarin hij gebruikt wordt.

    Een term op `BEKENDE_AFWIJKINGEN` slaat over met zijn reden erbij, zodat `-rs`
    de openstaande lijst toont. Dat hij nog schendt bewaakt de test hieronder.
    """
    if naam in BEKENDE_AFWIJKINGEN:
        pytest.skip(BEKENDE_AFWIJKINGEN[naam])

    assert not (schendingen := _schendingen(naam, gwsw_index)), "\n".join(
        str(schending) for schending in schendingen
    )


@pytest.mark.parametrize("naam", sorted(BEKENDE_AFWIJKINGEN))
def test_bekende_afwijking_is_nog_niet_opgeruimd(
    naam: str, gwsw_index: dict[str, frozenset[str]]
) -> None:
    """De andere richting: een opgeruimde term hoort van de lijst af.

    Zonder deze test zou `BEKENDE_AFWIJKINGEN` na de reparatie van #31 blijven staan
    als een lijst van problemen die er niet meer zijn, en dan dekt hij stilzwijgend
    een nieuwe fout met dezelfde naam af.
    """
    assert _schendingen(naam, gwsw_index), (
        f"{naam} levert geen schending meer op; haal hem uit BEKENDE_AFWIJKINGEN.\n"
        f"  stond er om deze reden: {BEKENDE_AFWIJKINGEN[naam]}"
    )


def test_een_verzonnen_naam_wordt_gemeld(gwsw_index: dict[str, frozenset[str]]) -> None:
    """De zelftest: zou de test uberhaupt rood worden, en met welke melding?"""
    schending = _schending(Term("Overnamepuntje", "checks.toml [klassen] put"), gwsw_index)

    assert schending is not None
    assert schending.soort == "ontbreekt"
    assert "Overnamepunt" in schending.suggestie
    assert "checks.toml [klassen] put" in str(schending)


def test_deelmodelverschil_geldt_niet_als_fout(gwsw_index: dict[str, frozenset[str]]) -> None:
    """Vals alarm 1: klassen die alleen in Totaal staan zijn gewoon geldig.

    `Overnamepunt` staat niet in Mds of Hyd; die dragen een conversiedatum uit 2021.
    Wie tegen een deelmodel valideert, dwingt de volgende ontwikkelaar precies de
    fout te maken die dit issue repareert.
    """
    for naam in ("Overnamepunt", "LozePut", "Valput"):
        assert _schending(Term(naam, "toets"), gwsw_index) is None, naam


def test_shacl_vormnamen_horen_niet_bij_de_termen() -> None:
    """Vals alarm 2: `dekking.toml` en `shaclrapport.py` dragen geen ontologietermen.

    `LengteLeiding_val` en `CfkTypes_typ` zijn namen van SHACL-vormen op de
    validatieserver. Gaat een toekomstige verzamelaar ze toch meenemen, dan zijn het
    gegarandeerd valse treffers en valt deze test.
    """
    assert not [naam for naam in NAMEN if naam.endswith(("_val", "_typ", "_ref", "_kwn"))]


def test_hoofdletterafwijking_krijgt_een_eigen_soort(gwsw_index: dict[str, frozenset[str]]) -> None:
    """Vals alarm 3: `Interneoverstortput` werkt, want de lookup is hoofdletterloos.

    Hem als ontbrekend melden is te streng en misleidend; zichtbaar maken is genoeg.
    """
    schending = _schending(Term("Interneoverstortput", "symbolen.py PUNTSYMBOLEN"), gwsw_index)

    assert schending is not None
    assert schending.soort == "hoofdletterafwijking"
    assert "InterneOverstortput" in schending.suggestie
    # `gevonden` is een gesorteerde tuple en geen frozenset: een naam met meerdere
    # `rdf:type`s zou anders per run in een andere volgorde in de melding staan.
    assert schending.gevonden == tuple(sorted(schending.gevonden))
    assert isinstance(schending.gevonden, tuple)


def _laad_indexscript() -> ModuleType:
    """Importeert `scripts/maak_gwsw_index.py` als module.

    De drifttest bouwt de index met precies dezelfde code als het script; een
    nagebouwde parser hier zou vroeg of laat iets anders opleveren dan wat er in het
    bestand staat, en dan meet de test zichzelf.
    """
    specificatie = importlib.util.spec_from_file_location("maak_gwsw_index", INDEXSCRIPT)
    assert specificatie is not None and specificatie.loader is not None
    module = importlib.util.module_from_spec(specificatie)
    sys.modules["maak_gwsw_index"] = module
    specificatie.loader.exec_module(module)
    return module


def test_index_volgt_de_ontologie(ontologie: list[Path]) -> None:
    """De getrackte index is bij tot en met de ontologie die er nu ligt.

    Draait alleen waar `data/gwsw_ontologieen/` staat -- op de CI-runner niet. Dit is
    de test die voorkomt dat de index stil veroudert zodra de auteur GWSW 1.7
    neerzet; zonder haar zou deze module een verleden bewaken dat niemand meer
    draait. De hele bestandstekst wordt vergeleken en niet alleen de termen, zodat
    ook de meegedragen `owl:versionInfo` en de opmaak niet uit de pas kunnen lopen.
    """
    verwacht = _laad_indexscript().documenttekst(ontologie[0])

    assert INDEXBESTAND.read_text(encoding="utf-8") == verwacht, (
        f"{INDEXBESTAND.relative_to(WORTEL)} loopt achter op "
        f"{ontologie[0].relative_to(WORTEL)}.\n"
        "Draai: uv run python scripts/maak_gwsw_index.py"
    )
