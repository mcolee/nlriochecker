"""Het getrackte voorbeeld `voorbeelden/koekangerveld/`: rooktest en gelijkheid.

Twee tests met een verschillend doel.

De **rooktest** draait `toets` op het getrackte voorbeeld en heeft `data/` niet nodig:
hij draait dus ook op de CI-runner en op een schone kloon. Dat is precies wat hij
bewaakt -- de README belooft dat het voorbeeld in drie commando's werkt, en zonder deze
test merkt niemand dat die belofte breekt. Hij controleert dat de vier uitvoervormen
ontstaan en dat het aantal meldingen gelijk is aan een vastgelegd getal.

De **gelijkheidstest** is de acceptatie-eis van issue #103: het voorbeeld moet voor de
eigen checks dezelfde bevindingen geven als een gebiedsrun Koekangerveld op de volle
export. Hij laadt de echte data en is daarom `zwaar` en overgeslagen zonder `data/`.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import REGISTRY
from nlriochecker.externedata import ROL_RASTER
from nlriochecker.toetsrun import voer_toets_uit

WORTEL = Path(__file__).resolve().parents[1]
# De paden van het voorbeeld zelf staan niet hier maar in `scripts/maak_ledger.py`
# (`voorbeeldopdracht`), zodat de run die de ledger vastlegt en de run die deze module
# toetst er een is.
DATA = WORTEL / "data"
VOLLE_OROX = DATA / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
VOLLE_BRONNEN = DATA / "gis_koekangerveld"
VOLLE_GEBIED = VOLLE_BRONNEN / "cbs_buurt_koekangerveld_studiegebied.gpkg"
VOLLE_SHACL = (
    DATA / "shacl_nulmeting" / "gwsw_shacl_report_conformiteit_Hyd.csv",
    DATA / "shacl_nulmeting" / "gwsw_shacl_report_conformiteit_MdsPlan.csv",
    DATA / "shacl_nulmeting" / "gwsw_shacl_report_MdsProj.csv",
)

# Het aantal meldingen dat de voorbeeldrun oplevert: de eigen checks plus de nulmeting
# plus de datasetsignalen, na afbakening tot de kern. Vastgelegd, niet berekend -- een
# rooktest die zijn eigen verwachting uitrekent toetst niets. Wijkt hij af, dan is er
# iets aan de checks, de uitvoer of het voorbeeld veranderd; regenereer het voorbeeld
# met `uv run python scripts/maak_voorbeeld.py` en werk dit getal bij als het verschil
# verklaard is. Twee checks lezen de dag van vandaag (ADM-006 op Einddatum/Begindatum,
# ATTR-007 op het huidige jaar als bovengrens), dus een export met datums rond nu zou
# dit getal vanzelf laten schuiven; deze export heeft die niet.
MELDINGEN_IN_HET_VOORBEELD = 335

# De sectie `voorbeeld` van de gouden ledger draagt datzelfde getal uitgesplitst per
# check (`scripts/maak_ledger.py`). Het losse getal hierboven blijft ernaast staan: wie
# de ledger klakkeloos regenereert loopt alsnog tegen die assertie aan.
LEDGER = Path(__file__).parent / "golden" / "ledger.json"


def _leunt_op_raster(check) -> bool:
    """Of deze check het hoogteraster als externe bron declareert.

    Alleen de EXT-familie kent `bronrollen()`; een check zonder die classmethod leunt op
    geen enkele externe bron. Geen handlijst van HGT-nummers: die zou verouderen zodra er
    een AHN-check bij komt of afvalt.
    """
    bronrollen = getattr(check, "bronrollen", None)
    return bronrollen is not None and ROL_RASTER in bronrollen()


# De twee soorten check die op het voorbeeld per definitie iets anders zien dan op de
# volledige export. Ze staan buiten de gelijkheidseis hieronder, met hun reden erbij, en
# ze worden uit de engine afgeleid in plaats van met de hand opgesomd.
#
# Zonder hoogteraster: het AHN-extract is 12 MB en gaat niet mee in de repository, dus de
# checks die erop leunen vinden hier niets. Ze zeggen dat zelf in het rapport. Vandaag zijn
# dat HGT-001, HGT-002 en HGT-003.
ZONDER_HOOGTERASTER = frozenset(
    check_id for check_id, check in REGISTRY.items() if _leunt_op_raster(check)
)
# Over de volledige export: deze checks gaan niet over losse objecten maar over de hele
# populatie -- `Check.volledig_bereik`, of aangewezen via `[studiegebied]
# volledige_dataset_checks` -- en die populatie *is* in het voorbeeld deze ene buurt.
# ATTR-015 slaat er daardoor aan waar hij dat gemeentebreed niet doet (1985 draagt 45,5%
# van de 44 gedateerde objecten hier, tegen niets in de buurt van de drempel over 46.925
# objecten) en ATTR-014 noemt in zijn boodschap een andere noemer. Vandaag: ADM-002,
# ATTR-014 en ATTR-015.
OVER_DE_VOLLEDIGE_EXPORT = frozenset(
    {check_id for check_id, check in REGISTRY.items() if check.volledig_bereik}
    | set(load_check_config().studiegebied.volledige_dataset_checks)
)


@pytest.fixture(scope="module")
def voorbeeld(ledgergenerator, tmp_path_factory):
    """Eén `toets` op het getrackte voorbeeld, gedeeld door de tests hieronder.

    De opdracht komt uit `scripts/maak_ledger.py` (`voorbeeldopdracht`): dat is de ene
    plek waar het commando uit `voorbeelden/koekangerveld/README.md` staat -- zonder
    `--projectconfig`, dus op de meegeleverde `checks.toml`, en zonder cache. Zou deze
    module haar eigen opdracht bouwen, dan kan de ledger tegen een andere run
    vergeleken worden dan zij vastlegt.

    Module-scoped, want de run kost anderhalve seconde per test en de uitslag is voor
    elke test dezelfde; `tmp_path_factory` levert de uitvoermap, want de gewone
    `tmp_path` bestaat alleen per test.
    """
    return voer_toets_uit(ledgergenerator.voorbeeldopdracht(tmp_path_factory.mktemp("voorbeeld")))


def _geschreven(uitslag):
    """De vier uitvoerpaden van de enige gebiedsrun."""
    return uitslag.uitvoer.per_gebied[uitslag.runs[0].naam]


def test_het_voorbeeld_levert_de_vier_uitvoervormen(voorbeeld) -> None:
    """De rooktest: `toets` op het voorbeeld schrijft rapport, CSV, GeoPackage en JSON."""
    geschreven = _geschreven(voorbeeld)

    assert geschreven.markdown.exists()
    assert geschreven.csv is not None and geschreven.csv.exists()
    assert geschreven.geopackage is not None and geschreven.geopackage.exists()
    assert geschreven.json is not None and geschreven.json.exists()


def test_het_voorbeeld_levert_hetzelfde_aantal_meldingen(voorbeeld) -> None:
    """Het vastgelegde getal uit de JSON; een stille verschuiving valt hier op."""
    pad = _geschreven(voorbeeld).json
    assert pad is not None

    envelop = json.loads(pad.read_text(encoding="utf-8"))

    assert envelop["aantal_meldingen"] == MELDINGEN_IN_HET_VOORBEELD


def test_het_voorbeeld_meldt_per_check_hetzelfde_aantal(voorbeeld) -> None:
    """Per check vastgelegd; een verschuiving tussen twee checks valt hier op.

    Het totaal hierboven ziet twintig meldingen die van HGT-007 naar HGT-013 verhuizen
    niet: dat blijven er 335. De uitsplitsing telt ook de `NULMETING-*`-vormen en de
    `SIG-*`-datasetsignalen mee -- die zitten in dezelfde meldingenstroom.
    """
    pad = _geschreven(voorbeeld).json
    assert pad is not None

    envelop = json.loads(pad.read_text(encoding="utf-8"))
    gemeten = Counter(melding["check_id"] for melding in envelop["meldingen"])

    assert dict(gemeten) == json.loads(LEDGER.read_text(encoding="utf-8"))["voorbeeld"]


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (VOLLE_OROX.exists() and VOLLE_GEBIED.exists() and all(p.exists() for p in VOLLE_SHACL)),
    reason="de De Wolden en Hoogeveen-OroX, de SHACL-rapporten of de GIS-bronnen staan "
    "niet in data/",
)
def test_het_voorbeeld_geeft_dezelfde_eigen_bevindingen_als_de_gebiedsrun(
    voorbeeld, ledgergenerator, tmp_path: Path
) -> None:
    """De acceptatie-eis van issue #103, in de opzet van de bestaande equivalentietests.

    Beide runs draaien op de meegeleverde `checks.toml`; alleen de dataset, de bronnenmap
    en de SHACL-rapporten verschillen. Dat de configuratie identiek is, is de reden dat
    een verschil in de uitkomst alleen van het voorbeeld zelf kan komen -- vandaar
    `replace()` op de voorbeeldopdracht in plaats van een tweede constructie: zo kan er
    geen vlag tussen de twee runs uit elkaar lopen.

    Gemeten op 29-08-2026: 125 bevindingen in het voorbeeld tegen 131 in de gebiedsrun,
    over achttien checks gelijk, met precies de twee uitgezonderde soorten als verschil
    (zeven HGT-001 en een HGT-003 zonder AHN, twee ATTR-015 die alleen in een kleine
    export boven hun signaaldrempel komen). De nulmeting verschilt 575 bevindingen, en
    die zijn stuk voor stuk onherleid: de gemeentebrede stelsels waarvan de focusnode
    geen put of streng is. Er is geen bevinding die alleen het voorbeeld heeft.
    """
    volledig = voer_toets_uit(
        replace(
            ledgergenerator.voorbeeldopdracht(tmp_path / "volledig"),
            dataset_pad=VOLLE_OROX,
            bronnen=VOLLE_BRONNEN,
            shacl=VOLLE_SHACL,
            studiegebied=VOLLE_GEBIED,
        )
    )

    def sleutels(uitslag, *, uitgezonderd: frozenset[str] = frozenset()):
        """Per bevinding de check en het object, gesorteerd."""
        return sorted(
            (bevinding.check_id, bevinding.object_uri.rsplit("#", 1)[-1])
            for bevinding in uitslag.runs[0].run.findings
            if bevinding.check_id not in uitgezonderd
        )

    buiten = ZONDER_HOOGTERASTER | OVER_DE_VOLLEDIGE_EXPORT
    assert sleutels(voorbeeld, uitgezonderd=buiten) == sleutels(volledig, uitgezonderd=buiten)
    assert not {check for check, _ in sleutels(voorbeeld)} & ZONDER_HOOGTERASTER, (
        "het voorbeeld draagt geen AHN; de hoogtechecks horen er niets te vinden"
    )

    # Op (vorm, focusnode) en niet op de hele bevinding: de systemisch-vlag deelt door
    # het aantal instanties in de dataset, en dat zijn er in het voorbeeld minder.
    in_voorbeeld = {
        (bevinding.vorm, bevinding.focus_node) for bevinding in voorbeeld.runs[0].run.nulbevindingen
    }
    verschil = [
        bevinding
        for bevinding in volledig.runs[0].run.nulbevindingen
        if (bevinding.vorm, bevinding.focus_node) not in in_voorbeeld
    ]
    herleid = [bevinding for bevinding in verschil if bevinding.herleid]
    assert not herleid, (
        f"{len(herleid)} van de {len(verschil)} nulmeting-verschillen komen wel op een "
        "object uit; het voorbeeld mist dan SHACL-regels die het wel had moeten dragen."
    )
    assert verschil, (
        "de gebiedsrun draagt geen enkele nulmetingbevinding meer die het voorbeeld mist; "
        "de onherleide regels (gemeentebrede stelsels) horen er te zijn, dus dit wijst op "
        "een verandering in de join of in de meting."
    )
