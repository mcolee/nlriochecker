"""Tests voor EXT-009: straten in de bebouwde kom zonder (vrijverval)riolering.

De fixture bestaat uit twee helften die bij elkaar horen. `tests/fixtures/gis/ext`
draagt de externe bronnen (acht NWB-wegvakken, een TOP10NL-plaatsvlak met een bebouwde
kom, drie BGT-wegdelen), `tests/fixtures/ttl/ext009_straten.ttl` de riolering. Drie van
de acht wegvakken zijn kandidaat, en elk staat voor een van de drie uitkomsten:
Rioolstraat is bediend (groen), Lege Laan leeg (rood, W-melding) en Grindweg onverhard
(grijs, niet beoordeeld). De vijf andere vallen elk om een eigen reden uit de
kandidaatselectie; zie `scripts/maak_gis_fixtures.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import load_dataset

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, CheckRun, run_checks
from nlriochecker.externedata import ExternalData, load_external_data

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis" / "ext"
STRATEN = TTL_DIR / "ext009_straten.ttl"

pytestmark = pytest.mark.skipif(
    not (GIS_DIR / "top10nl_plaats_vlak.gpkg").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)


@pytest.fixture
def config() -> CheckConfig:
    """De standaardconfig, afgestemd op het assenstelsel van de fixtures."""
    gekozen = load_check_config()
    gekozen.drempels.rd_y_min = 0.0
    return gekozen


@pytest.fixture(scope="session")
def bronnen() -> ExternalData:
    """De miniatuurbronnen uit tests/fixtures/gis/ext."""
    basis = load_check_config().bronnen
    aangepast = basis.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": "bag_pand.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "top10nl": "top10nl_plaats_vlak.gpkg",
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    return load_external_data(aangepast, GIS_DIR)


def draai(config: CheckConfig, bronnen: ExternalData | None) -> CheckRun:
    """Draait EXT-009 op de stratenfixture."""
    dataset = load_dataset(STRATEN, [])
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)
    return run_checks(context, ["EXT-009"])


def uitkomst(config: CheckConfig, bronnen: ExternalData | None) -> CheckOutcome:
    """De uitslag van EXT-009 op de stratenfixture."""
    return draai(config, bronnen).outcomes[0]


def test_elke_kandidaatstraat_krijgt_haar_eigen_status(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Drie kandidaten, drie uitkomsten; de vijf andere wegvakken vallen af."""
    run = draai(config, bronnen)

    assert {oordeel.straat: oordeel.status for oordeel in run.wegvakken} == {
        "Rioolstraat": "groen",
        "Lege Laan": "rood",
        "Grindweg": "grijs",
    }


def test_alleen_de_lege_straat_levert_een_waarschuwing(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """De melding hangt aan een NWB-sleutel en draagt het middelpunt als locatie."""
    outcome = uitkomst(config, bronnen)

    assert [bevinding.object_label for bevinding in outcome.findings] == ["Lege Laan (Fixturekom)"]
    bevinding = outcome.findings[0]
    assert bevinding.object_uri == "nwb:wegvak/3"
    assert bevinding.severity.value == "W"
    assert bevinding.location == (1060.0, 1940.0)
    assert outcome.examined == 3


def test_de_toelichting_telt_wat_er_niet_beoordeeld_is(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Stilte over de grijze straten zou lezen als 'alles gecontroleerd'."""
    outcome = uitkomst(config, bronnen)

    assert any("1 groen" in notitie for notitie in outcome.notes), outcome.notes
    assert any(
        "niet beoordeeld" in notitie.lower() and "onverhard" in notitie for notitie in outcome.notes
    ), outcome.notes


def test_zonder_bronnen_wordt_er_niets_getoetst(config: CheckConfig) -> None:
    outcome = uitkomst(config, None)

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("geen externe bronnen" in notitie for notitie in outcome.notes)


def test_een_ontbrekende_bron_slaat_de_check_over(config: CheckConfig) -> None:
    """Zonder komlaag is er geen bebouwde kom en dus geen kandidaatselectie."""
    basis = load_check_config().bronnen
    zonder_kom = basis.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "top10nl": None,
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    outcome = uitkomst(config, load_external_data(zonder_kom, GIS_DIR))

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("laag niet aanwezig in aangeleverde data" in n for n in outcome.notes), outcome.notes
