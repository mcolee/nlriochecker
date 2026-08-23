"""Bestaat elke GWSW-naam die dit pakket gebruikt werkelijk in de ontologie?

De aanleiding staat in issue #30: twee keer op rij is beweerd dat een GWSW-klasse
niet bestond terwijl ze gewoon in `Ontologie_GWSW_Totaal.ttl` staat, en beide keren
corrigeerde de auteur dat en niet een test. Deze module maakt die controle
mechanisch: hij verzamelt de GWSW-namen uit de configuratiebestanden, de
plausibiliteitstabellen en de symbolentabellen, plus de aspectnamen die in `src/` als
letterlijk eerste argument van een kenmerklezer staan, en houdt die naast de ontologie.

Drie ontwerpkeuzes dragen de test:

* **De termen worden nergens overgeschreven.** Ze komen uit de geladen `CheckConfig`,
  de `PlausibilityTables`, de symbolentabellen en een AST-sweep over `src/`. Een
  handgeschreven kopie zou uit de pas lopen en dan toetst de test zichzelf. Elke bron
  heeft daarom een eigen sentinel in `BRONSENTINELS`: een verzamelaar die stilvalt
  maakt de module rood in plaats van hem leeg en groen te laten draaien.
* **Er wordt op `rdf:type` getoetst, niet op "komt de naam voor in de TTL".**
  `Kunststof` bestaat, maar als lid van `MateriaalAfsluiterColl`; als putmateriaal is
  hij nergens legaal. Een naamvergelijking laat die fout door.
* **De uitkomst hangt aan `BEKENDE_AFWIJKINGEN`, in twee richtingen.** Een nieuwe
  schending die niet op de lijst staat maakt de test rood, en een term die van de
  lijst af had gemoeten ook. De inhoud van die lijst is het werk van issue #31.

De test gaat *uitsluitend* over de vraag of een begrip in het model bestaat. Of er
instanties van in een dataset voorkomen is een andere vraag met een ander antwoord.

**Wat de AST-sweep niet ziet.** Hij ziet de aanroep zelf, dus alleen een aspectnaam die
als stringliteraal het eerste argument is -- op dit moment zestien van de eenentwintig
kandidaat-aanroepen in `src/`, goed voor tien namen. Wie zijn naam eerst in een tuple of
een modulevariabele zet en die pas daarna doorgeeft, blijft buiten beeld:
`checks/attributen.py` (`_grootste_putmaat`), `checks/randvoorzieningen.py` (de
bergingskenmerken) en `dataset.py` (de vertex- en BOB-klassen) dragen samen ruim een
dozijn van zulke namen. Ze zijn met de hand tegen de index gehouden en alle geldig, maar
deze module bewaakt ze niet; ze komen er pas onder zodra ze een directe aanroep worden.

**Wat waar draait.** De ontologie zelf is 2,6 MB en staat buiten versiebeheer, dus de
test leest niet de TTL maar de getrackte afgeleide `data/gwsw-vocabulaire-index.json`:
per GWSW-naam zijn `rdf:type`s en zijn directe superklassen, en niets meer. Daardoor
draait alles hier gewoon mee op de CI-runner -- dat was het hele punt van #30, en eerder
sloegen daar 140 van de 142 gevallen over. Het bestand is geen invoerdata maar een
afgeleide; het wordt nooit met de hand bijgewerkt maar met `scripts/maak_gwsw_index.py`.
Zie BO-32 voor de afweging om het te tracken.

Eén test heeft de ontologie zelf nodig: `test_index_volgt_de_ontologie` vergelijkt de
getrackte index met een vers geparseerde TTL, en dat kan alleen op een machine waar
`data/gwsw_ontologieen/` staat -- op de CI-runner dus niet. Dat is geen ongedekt gat.
De enige die de index kan laten verouderen is de auteur die GWSW 1.7 neerzet, en dat
is dezelfde persoon op dezelfde machine die deze test wél draait. `scripts/uitgave.py`
draait `uv run pytest -q` als uitgavepoort en `TAKVOORWAARDE` dwingt die poort af op
`main`; een verouderde index kan dus geen uitgave overleven. Automatisch ophalen bij
data.gwsw.nl is geen alternatief: `CLAUDE.md` verbiedt dat expliciet, en upgraden is
met opzet handwerk van de auteur.

Eén restrisico blijft, en het hoort hier genoemd: een naam die GWSW 1.7 **hernoemt** of
naar een andere collectie verplaatst valideert gewoon door tegen de 1.6-index, tot de
index vervangen is. Nieuwe namen vallen luid om, hernoemde niet. `versie=` uit de index
moet daarom in `CLAUDE.md` terugkomen (`test_indexversie_staat_in_claude_md`), zodat de
twee niet elk hun eigen GWSW-versie kunnen gaan dragen.

Er zit met opzet **geen skip** op het inlezen van de index: ontbreekt het bestand, dan
valt de hele module om. Een skip zou de oude stilte in een nieuwe vorm terugbrengen.
"""

from __future__ import annotations

import ast
import difflib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from nlriochecker.checkconfig import ClassRoots, load_check_config
from nlriochecker.dataset import VULWAARDE_KENMERKEN
from nlriochecker.plausibiliteit import load_plausibility
from nlriochecker.uitvoer.stijlen.symbolen import LIJNSYMBOLEN, MECHANISCHE_LIJNEN, PUNTSYMBOLEN

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
#
# De sleutel is `(naam, collectie)` en niet de naam alleen: `Metselwerk` staat legaal
# in `MateriaalLeidingColl` en onterecht in `MateriaalPutColl`, en een sleutel op naam
# zou die vier legitieme vindplaatsen mee de skip in trekken. Omdat het oordeel per
# term alleen van naam en collectie afhangt, is een groep onder deze sleutel homogeen:
# er valt niet langer twee derde van de vindplaatsen op te ruimen met een groene test
# als beloning.
BEKENDE_AFWIJKINGEN: dict[tuple[str, str], str] = {
    ("AHN5", "WijzeVanInwinningColl"): (
        "ontbreekt in de ontologie -- WijzeVanInwinningColl stopt bij AHN4. Weghalen of "
        "laten staan als vooruitloop op een latere GWSW-versie is een open vraag; besluit "
        "bij de auteur, zie vraag 1 van issue #47."
    ),
}
# `("Metselwerk", "MateriaalPutColl")` stond hier tot issue #43. Die afwijking heeft geen
# drager meer: `[[leiding_put_materiaal]]` noemt sinds de omkering alleen nog
# onwaarschijnlijke putmaterialen, en `Metselwerk` staat op geen van die twee lijsten.
# Dat is geen antwoord op vraag 2 van issue #47 -- de 33 gemetselde putten van De Wolden
# werden ook voorheen niet gemeld -- maar het pakket claimt niet langer dat `Metselwerk`
# een putmateriaal is. Zie BO-35 en BO-36.


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
                f"{regel.leidingmateriaal}.onwaarschijnlijke_putmaterialen",
                "MateriaalPutColl",
            )
            for naam in regel.onwaarschijnlijke_putmaterialen
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
# Het oordeel over een term hangt alleen van zijn naam en de collectie af waarin hij
# gebruikt wordt; dat paar is dus de eenheid waarin deze module telt, skipt en meldt.
SLEUTELS = sorted({(term.naam, term.collectie) for term in TERMEN})


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


def _laad_kinderen() -> dict[str, frozenset[str]]:
    """De omgekeerde `subklasse_van` uit de index: per klasse haar directe subklassen."""
    document = json.loads(INDEXBESTAND.read_text(encoding="utf-8"))
    kinderen: dict[str, set[str]] = {}
    for kind, ouders in document["subklasse_van"].items():
        for ouder in ouders:
            kinderen.setdefault(ouder, set()).add(kind)
    return {ouder: frozenset(namen) for ouder, namen in kinderen.items()}


KINDEREN = _laad_kinderen()


def _afsluiting(wortel: str) -> frozenset[str]:
    """De wortel plus al haar subklassen, hoe diep ook."""
    gevonden = {wortel}
    stapel = [wortel]
    while stapel:
        for kind in KINDEREN.get(stapel.pop(), frozenset()):
            if kind not in gevonden:
                gevonden.add(kind)
                stapel.append(kind)
    return frozenset(gevonden)


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


def _schendingen(naam: str, collectie: str, index: dict[str, frozenset[str]]) -> list[Schending]:
    """Elke schending van dit naam-collectiepaar, over al zijn vindplaatsen."""
    gevonden = (
        _schending(term, index)
        for term in TERMEN
        if term.naam == naam and term.collectie == collectie
    )
    return [schending for schending in gevonden if schending is not None]


SENTINELS = ("Inspectieput", "Beton", "Rond", "Begindatum")

# Per termenbron een sentinel: het begin van de vindplaats die die bron schrijft, en
# een naam die daar hoort te staan. Een gezamenlijke ondergrens op `NAMEN` doet dit
# niet -- laat je beide TOML-configuraties weg, dan houd je nog 111 namen over en
# blijft de module groen terwijl 126 van de 278 termen ongetoetst zijn. Wie een bron
# hernoemt of eruit haalt hoort hier langs te komen; dat is de bedoeling.
BRONSENTINELS: tuple[tuple[str, str], ...] = (
    ("checks.toml [klassen]", "Put"),
    ("checks.toml [klassen.stelseltypen]", "GemengdRiool"),
    ("checks.toml [[puttyperegels]]", "Overstortput"),
    ("checks.toml [inwinning]", "AHN4"),
    ("checks.toml [vulwaarden]", "Maaiveldhoogte"),
    ("configs/dewoldenhoogeveen.toml [klassen]", "Put"),
    ("configs/dewoldenhoogeveen.toml [klassen.stelseltypen]", "GemengdRiool"),
    ("configs/dewoldenhoogeveen.toml [[puttyperegels]]", "Overstortput"),
    ("configs/dewoldenhoogeveen.toml [inwinning]", "AHN4"),
    ("configs/dewoldenhoogeveen.toml [vulwaarden]", "Maaiveldhoogte"),
    ("plausibiliteit.toml [[materiaal_diameter]]", "Beton"),
    ("plausibiliteit.toml [[materiaal_aanlegjaar]]", "PVC"),
    ("plausibiliteit.toml [[materiaal_vorm]]", "PVC"),
    # Een naam die alleen aan de leidingkant staat: `PVC` en `PE` staan sinds issue #43
    # in `onwaarschijnlijke_putmaterialen` en zouden deze sentinel ook groen houden als
    # de leidingkant wegviel.
    ("plausibiliteit.toml [[leiding_put_materiaal]]", "GewapendBeton"),
    ("plausibiliteit.toml [[vorm_afmeting]]", "Rond"),
    ("symbolen.py PUNTSYMBOLEN", "Inspectieput"),
    ("symbolen.py LIJNSYMBOLEN", "Drain"),
    ("dataset.py VULWAARDE_KENMERKEN", "Maaiveldhoogte"),
    # De AST-sweep schrijft `<module>.py:<regel> .<methode>()`; de dubbele punt scheidt
    # hem van de VULWAARDE_KENMERKEN-regel hierboven, en het regelnummer valt buiten
    # het voorvoegsel zodat een verschuiving in `dataset.py` deze test niet raakt.
    ("dataset.py:", "Begindatum"),
)


def test_de_termen_zijn_gevonden() -> None:
    """Zonder termen zou elke andere test hier groen zijn zonder iets te toetsen."""
    assert len(NAMEN) > 100
    assert set(SENTINELS) <= set(NAMEN)


@pytest.mark.parametrize(("voorvoegsel", "sentinel"), BRONSENTINELS)
def test_elke_termenbron_levert_zijn_sentinel(voorvoegsel: str, sentinel: str) -> None:
    """Elke afzonderlijke termenbron draagt werkelijk bij aan `TERMEN`.

    De gezamenlijke ondergrens hierboven is te grof: hij overleeft het wegvallen van
    een hele bron. Deze test valt per bron om, met de bron in de testnaam.
    """
    assert any(
        term.naam == sentinel and term.vindplaats.startswith(voorvoegsel) for term in TERMEN
    ), f"{voorvoegsel} levert geen term {sentinel}; draagt die bron nog wel bij?"


def test_de_index_is_niet_uitgehold() -> None:
    """De keerzijde: een index die termen kwijtraakt mag niet ongemerkt doorgaan.

    Een krimpende index maakt de vocabulairetest weliswaar róder en niet groener --
    een naam die er niet in staat heet "ontbreekt" -- maar een index die zijn
    collectielidmaatschappen kwijtraakt zou de collectietoets uithollen zonder dat er
    iets rood wordt. Vandaar een ondergrens op het aantal termen, de vier sentinels,
    en het bestaan van de vier collecties waarop de rest van deze module leunt.

    Hetzelfde geldt voor de klassenboom: zonder `subklasse_van` is de afsluiting van
    `Put` gelijk aan `Put` zelf, en dan wordt de dekkingstest hieronder stil groen.
    """
    assert len(INDEX) > 3_000, f"{INDEXBESTAND.name} draagt maar {len(INDEX)} termen"
    assert len(_afsluiting("Put")) > 40, "de klassenboom in de index is uitgehold"
    for naam in SENTINELS:
        assert naam in INDEX, naam
    for collectie in (
        "MateriaalLeidingColl",
        "MateriaalPutColl",
        "VormLeidingColl",
        "WijzeVanInwinningColl",
    ):
        assert [naam for naam in INDEX if collectie in INDEX[naam]], collectie


@pytest.mark.parametrize(("naam", "collectie"), SLEUTELS, ids=_kort)
def test_gwsw_naam_bestaat_in_de_ontologie(
    naam: str, collectie: str, gwsw_index: dict[str, frozenset[str]]
) -> None:
    """Elke gebruikte GWSW-naam bestaat, en in de collectie waarin hij gebruikt wordt.

    Een paar op `BEKENDE_AFWIJKINGEN` slaat over met zijn reden erbij, zodat `-rs`
    de openstaande lijst toont. Dat het nog schendt bewaakt de test hieronder. Het
    andere gebruik van dezelfde naam -- `Metselwerk` als leidingmateriaal -- valt onder
    zijn eigen paar en wordt dus gewoon getoetst.
    """
    if (naam, collectie) in BEKENDE_AFWIJKINGEN:
        pytest.skip(BEKENDE_AFWIJKINGEN[naam, collectie])

    assert not (schendingen := _schendingen(naam, collectie, gwsw_index)), "\n".join(
        str(schending) for schending in schendingen
    )


@pytest.mark.parametrize(("naam", "collectie"), sorted(BEKENDE_AFWIJKINGEN), ids=_kort)
def test_bekende_afwijking_is_nog_niet_opgeruimd(
    naam: str, collectie: str, gwsw_index: dict[str, frozenset[str]]
) -> None:
    """De andere richting: een opgeruimd paar hoort van de lijst af.

    Zonder deze test zou `BEKENDE_AFWIJKINGEN` na de reparatie van #31 blijven staan
    als een lijst van problemen die er niet meer zijn, en dan dekt hij stilzwijgend
    een nieuwe fout met dezelfde naam af.
    """
    assert _schendingen(naam, collectie, gwsw_index), (
        f"{naam} in {_kort(collectie)} levert geen schending meer op; haal het paar uit "
        f"BEKENDE_AFWIJKINGEN.\n"
        f"  stond er om deze reden: {BEKENDE_AFWIJKINGEN[naam, collectie]}"
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


# De vier GWSW-wortels waaronder de knoop- en bouwwerkklassen hangen die de laag
# `putten` kan tegenkomen. `Verbinding` staat er bewust niet bij: LIJNSYMBOLEN is wel
# de tegenhanger, maar die tabel volgt de SLD-indeling van de leidingsoorten en niet de
# klassenboom, en een verschil daar zou een andere vraag stellen dan deze test.
SYMBOOLWORTELS: tuple[str, ...] = ("Put", "Bouwwerk", "Hulpstuk", "Knooppunt")

# De klassen onder die vier wortels waarvoor de symbolentabellen vandaag géén regel
# dragen. Dit is een momentopname en geen besluitenlijst: er staat niet "deze willen we
# niet", er staat "deze zijn nog niet gedekt". De lijst korter maken is werk dat nog
# moet gebeuren -- issue #14 hertekent de symbolen -- en zolang het niet gebeurd is
# hoort hij hier zichtbaar te staan in plaats van als stilte in het rapport.
#
# Vastgelegd tegen GWSW 1.6: 137 klassen onder de vier wortels, 42 daarvan gedekt.
NOG_ONGEDEKTE_KLASSEN = frozenset({
    "Aansluitput", "Afleveringspunt", "Afvoerpunt", "AfvoerpuntGebied", "Beekriool", "Beerput",
    "Bergingsvijver", "Biofilter", "BlindeInlaat", "BlindePut", "Bochtstuk", "Bouwwerk",
    "Bouwwerkorientatie", "Brandput", "Compartimentorientatie", "Compensator", "Dijk",
    "Doorspuitput", "Drainagegemaal", "Duikerput", "Erfafscheidingsput", "ExplosievrijeKolk",
    "Filterput", "Gebouw", "GecombineerdeStraat_trottoirkolk", "Gemaal",
    "GemaalDrogeOpstelling", "GemaalNatteOpstelling", "Grindkoffer", "Hondenhokput", "Hulpstuk",
    "Hulpstukorientatie", "IBAKlasseI", "IBAKlasseII", "IBAKlasseIIIa", "IBAKlasseIIIb",
    "Infiltratiebassin", "Infiltratiegreppel", "Infiltratiekolk", "Infiltratiereservoir",
    "InlaatOppervlaktewater", "InlaatRioolput", "Knooppunt", "Kruisstuk", "Kunstwerk",
    "Lavakoffer", "Leidingbrug", "LozePut", "Lozingspunt", "LozingspuntBodem",
    "LozingspuntOppervlaktewater", "Luchtpersgemaal", "MantoegankelijkePut", "Mof",
    "Olie__benzineafvangput", "Ontlastput", "Ontstoppingsput", "OpenBerging",
    "Oppervlaktewatergemaal", "Overgangsstuk", "Overkluizing", "Perceelaansluitpunt", "Put",
    "Putbuis", "Putorientatie", "RWSKolk", "ReinigendePut", "Reservoir", "Riooleindgemaal",
    "Rioolput", "RioolputMetGeleiding", "Slokop", "Spoelgemaal", "Spoorlijn", "Steenwolkoffer",
    "Trottoirkolk", "Tubelure", "Tunnelgemaal", "Uitstroombak", "Valput",
    "VerbeterdeOverstortput", "VerdektePut", "VerdieptePut", "Verloopstuk", "Vetvangput",
    "VolgeschuimdePut", "Wadi", "Waterkering", "Werveloverstortput", "Wervelput", "Y_stuk",
    "Zadel", "Zandkoffer", "Zinkerput", "Zuiveringsreservoir",
})  # fmt: skip


def test_de_symbolentabel_raakt_niet_verder_achterop() -> None:
    """Dekken onze tabellen de knoopklassen die GWSW kent -- de andere kant van #30.

    Drie vragen die makkelijk door elkaar lopen, en dit is de tweede:

    1. Bestaan onze namen in GWSW? Dat is de rest van deze module.
    2. Dekken wij de klassen van GWSW? Dat is deze test.
    3. Krijgt elk objecttype dat in een dataset voorkomt een symbool? Dat is
       `tests/test_uitvoer_symbolen.py`, en het antwoord daarop zegt niets over 1 en 2.

    Dit is een drifttest en geen volledigheidseis: hij faalt wanneer het verschil
    *groeit*. Een nieuwe GWSW-versie die klassen toevoegt komt zo langs, in plaats van
    stil in de vangnetregel ("objecttype niet in de symbolentabel") te verdwijnen. Wordt
    de lijst korter -- en dat is de bedoeling -- dan haal je de gedekte namen eruit.
    """
    ongedekt = set()
    for wortel in SYMBOOLWORTELS:
        ongedekt |= _afsluiting(wortel)
    ongedekt -= set(PUNTSYMBOLEN) | set(LIJNSYMBOLEN)

    assert not (nieuw := sorted(ongedekt - NOG_ONGEDEKTE_KLASSEN)), (
        f"{len(nieuw)} klasse(n) onder {', '.join(SYMBOOLWORTELS)} hebben geen symbool en "
        f"staan niet op NOG_ONGEDEKTE_KLASSEN: {', '.join(nieuw)}.\n"
        "Geef ze een regel in symbolen.py, of zet ze op de lijst als bewuste huidige stand."
    )


def test_symbolen_en_checks_zijn_het_eens_over_mechanisch() -> None:
    """symbolen.py en checks.toml spreken elkaar niet tegen over wat mechanisch is.

    symbolen.py tekent `MECHANISCHE_LIJNEN` als streepjeslijn -- het beeld van een
    leiding zonder vrij verval. checks.toml bepaalt via `[klassen] mechanisch` welke
    strengen op de kaart grijs blijven zolang er niets op staat. Lopen de twee uiteen,
    dan tekent de kaart een leiding als mechanisch terwijl de status hem als getoetste
    vrijvervalstreng kleurt (issue #56). Elke mechanisch getekende klasse hoort dus in de
    afsluiting van de mechanisch-wortels te vallen -- de subklasse-afsluiting, want
    checks.toml noemt de wortels (`MechanischeRioolleiding`, `MechanischeTransportleiding`)
    en niet elk blad.
    """
    wortels = load_check_config().klassen.mechanisch
    afsluiting: set[str] = set()
    for wortel in wortels:
        afsluiting |= _afsluiting(wortel)

    ontbreekt = MECHANISCHE_LIJNEN - afsluiting
    assert not ontbreekt, (
        f"{', '.join(sorted(ontbreekt))} wordt in symbolen.py als mechanisch getekend maar "
        f"valt niet onder [klassen] mechanisch = {wortels}."
    )


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


def test_indexversie_staat_in_claude_md() -> None:
    """De index en `CLAUDE.md` dragen dezelfde GWSW-versie.

    De drifttest hierboven bewaakt maar één richting: `CLAUDE.md` bijwerken zonder het
    script te draaien valt om (op een machine met de ontologie). De omgekeerde richting
    -- het script draaien op 1.7 terwijl `CLAUDE.md` nog 1.6 zegt -- merkt niemand, en
    dan is `CLAUDE.md` niet langer "de enige plek waar hij staat". Beide bestanden zijn
    getrackt, dus deze test draait wél op CI.

    Alleen het `versie=X.Y`-deel wordt vergeleken en niet de hele regel: de
    conversiedatum erachter hoort bij de ontologie en niet bij de projectafspraak.
    """
    versieregel = json.loads(INDEXBESTAND.read_text(encoding="utf-8"))["gwsw_versie"]
    gevonden = re.search(r"versie=[0-9]+(?:\.[0-9]+)*", versieregel)

    assert gevonden is not None, f"geen versie= in {versieregel!r}"
    assert gevonden.group() in (WORTEL / "CLAUDE.md").read_text(encoding="utf-8"), (
        f"{INDEXBESTAND.name} draagt {gevonden.group()}, maar CLAUDE.md noemt die versie "
        "niet. CLAUDE.md is de gezaghebbende plek; werk de alinea over de leidende "
        "GWSW-versie bij."
    )
