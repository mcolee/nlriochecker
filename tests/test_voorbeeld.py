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
from pathlib import Path

import pytest

from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit

WORTEL = Path(__file__).resolve().parents[1]
VOORBEELD = WORTEL / "voorbeelden" / "koekangerveld"
VOORBEELD_TTL = VOORBEELD / "koekangerveld_orox.ttl"
VOORBEELD_CONFIG = VOORBEELD / "koekangerveld.toml"
VOORBEELD_GEBIED = VOORBEELD / "cbs_buurt_koekangerveld_studiegebied.gpkg"
VOORBEELD_SHACL = (
    VOORBEELD / "gwsw_shacl_report_conformiteit_Hyd.csv",
    VOORBEELD / "gwsw_shacl_report_conformiteit_MdsPlan.csv",
    VOORBEELD / "gwsw_shacl_report_MdsProj.csv",
)

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
MELDINGEN_IN_HET_VOORBEELD = 337

# De twee soorten check die op het voorbeeld per definitie iets anders zien dan op de
# volledige export. Ze staan buiten de gelijkheidseis hieronder, met hun reden erbij.
#
# Zonder hoogteraster: het AHN-extract is 12 MB en gaat niet mee in de repository, dus de
# drie checks die erop leunen vinden hier niets. Ze zeggen dat zelf in het rapport.
ZONDER_HOOGTERASTER = frozenset({"HGT-001", "HGT-002", "HGT-003"})
# Over de volledige export: deze checks gaan niet over losse objecten maar over de hele
# populatie (`Check.volledig_bereik`), en die populatie *is* in het voorbeeld deze ene
# buurt. ATTR-015 slaat er daardoor aan waar hij dat gemeentebreed niet doet -- 1985 draagt
# 45,5% van de 44 gedateerde objecten hier, tegen niets in de buurt van de drempel over
# 46.925 objecten -- en ATTR-014 noemt in zijn boodschap een andere noemer.
OVER_DE_VOLLEDIGE_EXPORT = frozenset({"ADM-002", "ATTR-014", "ATTR-015"})


def _opdracht(uitvoermap: Path, dataset: Path, bronnen: Path, shacl, gebied: Path):
    """De toetsopdracht van een run; alleen dataset, bronnen en SHACL verschillen."""
    return Toetsopdracht(
        dataset_pad=dataset,
        uitvoermap=uitvoermap,
        shacl=tuple(shacl),
        studiegebied=gebied,
        projectconfig=VOORBEELD_CONFIG,
        bronnen=bronnen,
        # Geen cache: een rooktest hoort niet van een eerdere run af te hangen, en op
        # een schone kloon zou hij er een aanleggen die niemand vroeg.
        gebruik_cache=False,
    )


def _voorbeeldrun(uitvoermap: Path):
    """Draait `toets` op het getrackte voorbeeld."""
    return voer_toets_uit(
        _opdracht(uitvoermap, VOORBEELD_TTL, VOORBEELD, VOORBEELD_SHACL, VOORBEELD_GEBIED)
    )


def test_het_voorbeeld_levert_de_vier_uitvoervormen(tmp_path: Path) -> None:
    """De rooktest: `toets` op het voorbeeld schrijft rapport, CSV, GeoPackage en JSON."""
    uitslag = _voorbeeldrun(tmp_path)

    geschreven = uitslag.uitvoer.per_gebied[uitslag.runs[0].naam]

    assert geschreven.markdown.exists()
    assert geschreven.csv is not None and geschreven.csv.exists()
    assert geschreven.geopackage is not None and geschreven.geopackage.exists()
    assert geschreven.json is not None and geschreven.json.exists()


def test_het_voorbeeld_levert_hetzelfde_aantal_meldingen(tmp_path: Path) -> None:
    """Het vastgelegde getal uit de JSON; een stille verschuiving valt hier op."""
    uitslag = _voorbeeldrun(tmp_path)
    pad = uitslag.uitvoer.per_gebied[uitslag.runs[0].naam].json
    assert pad is not None

    envelop = json.loads(pad.read_text(encoding="utf-8"))

    assert len(envelop["meldingen"]) == MELDINGEN_IN_HET_VOORBEELD


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (VOLLE_OROX.exists() and VOLLE_GEBIED.exists() and all(p.exists() for p in VOLLE_SHACL)),
    reason="de De Wolden en Hoogeveen-OroX, de SHACL-rapporten of de GIS-bronnen staan "
    "niet in data/",
)
def test_het_voorbeeld_geeft_dezelfde_eigen_bevindingen_als_de_gebiedsrun(tmp_path: Path) -> None:
    """De acceptatie-eis van issue #103, in de opzet van de bestaande equivalentietests.

    Beide runs krijgen dezelfde projectconfiguratie mee; alleen de dataset, de
    bronnenmap en de SHACL-rapporten verschillen. Dat de configuratie identiek is, is de
    reden dat een verschil in de uitkomst alleen van het voorbeeld zelf kan komen.

    Gemeten op 29-08-2026: 125 bevindingen in het voorbeeld tegen 131 in de gebiedsrun,
    over achttien checks gelijk, met precies de twee uitgezonderde soorten als verschil
    (zeven HGT-001 en een HGT-003 zonder AHN, twee ATTR-015 die alleen in een kleine
    export boven hun signaaldrempel komen). De nulmeting verschilt 575 bevindingen, en
    die zijn stuk voor stuk onherleid: de gemeentebrede stelsels waarvan de focusnode
    geen put of streng is. Er is geen bevinding die alleen het voorbeeld heeft.
    """
    voorbeeld = _voorbeeldrun(tmp_path / "voorbeeld")
    volledig = voer_toets_uit(
        _opdracht(tmp_path / "volledig", VOLLE_OROX, VOLLE_BRONNEN, VOLLE_SHACL, VOLLE_GEBIED)
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
    assert verschil and all(not bevinding.herleid for bevinding in verschil), (
        f"{sum(1 for b in verschil if b.herleid)} van de {len(verschil)} nulmeting-"
        "verschillen komen wel op een object uit; het voorbeeld mist dan SHACL-regels "
        "die het wel had moeten dragen."
    )
