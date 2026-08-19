"""Tests voor de EXT-checks en de AHN-hoogtechecks op miniatuurbronnen.

De fixtures onder `tests/fixtures/gis/ext` hebben dezelfde structuur als de echte
bronnen in `data/gis` (dezelfde laagnamen, dezelfde attribuutnamen, EPSG:28992),
maar dan in het lokale assenstelsel van de TTL-fixtures. Ze worden gemaakt met
`scripts/maak_gis_fixtures.py`; het hoogteraster staat overal op 10,00 m NAP met
een nodata-vlek rond (1040, 2010).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import REGISTRY, CheckContext, CheckOutcome, run_checks
from nlriochecker.checks.extern import MARKERING_BUITEN_SCOPE, MARKERING_NIET_TOETSBAAR
from nlriochecker.dataset import load_dataset
from nlriochecker.externedata import ExternalData, load_external_data

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis" / "ext"
SCENARIO = TTL_DIR / "ext_scenario.ttl"

EXT_IDS = ["EXT-001", "EXT-002", "EXT-003", "EXT-005", "EXT-006", "EXT-007"]
AHN_IDS = ["HGT-001", "HGT-002", "HGT-003"]

pytestmark = pytest.mark.skipif(
    not (GIS_DIR / "ahn.tif").exists(),
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
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    return load_external_data(aangepast, GIS_DIR)


def uitkomst(
    check_id: str,
    config: CheckConfig,
    bronnen: ExternalData | None,
    bestand: Path = SCENARIO,
) -> CheckOutcome:
    """Draait een enkele check op de scenariofixture."""
    dataset = load_dataset(bestand)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)
    return run_checks(context, [check_id]).outcomes[0]


def labels(outcome: CheckOutcome) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in outcome.findings)


def test_bronnen_worden_gelezen_in_rd(bronnen: ExternalData) -> None:
    assert bronnen.extent is not None
    assert {rol: len(laag) for rol, laag in bronnen.layers.items()} == {
        "bgt_pand": 1,
        "bgt_water": 2,
        "bgt_putdeksel": 3,
        "bgt_bouwwerk": 1,
        "bag_pand": 2,
        "nwb_wegvak": 1,
    }
    assert all(laag.crs == "EPSG:28992" for laag in bronnen.layers.values())
    assert all(laag.reprojected_from is None for laag in bronnen.layers.values())
    assert bronnen.raster is not None
    assert bronnen.raster.sample(1000.0, 2000.0) == pytest.approx(10.0)
    # De nodata-vlek levert geen hoogte op in plaats van de sentinelwaarde.
    assert bronnen.raster.sample(1040.0, 2010.0) is None
    # Buiten het raster is er niets te bemonsteren.
    assert bronnen.raster.sample(5000.0, 5000.0) is None


@pytest.mark.parametrize(
    ("check_id", "verwacht"),
    [
        ("EXT-001", ["1", "4", "P", "Q"]),
        ("EXT-002", ["2", "3"]),
        ("EXT-003", ["2"]),
        ("EXT-005", ["C", "E", "F", "L1", "L2", "P", "Q"]),
        ("EXT-006", ["deksel-los"]),
        ("EXT-007", ["L1"]),
        ("HGT-001", ["B", "E"]),
        ("HGT-002", ["C"]),
        ("HGT-003", ["1", "2"]),
    ],
)
def test_defect_wordt_gevonden(
    check_id: str, verwacht: list[str], config: CheckConfig, bronnen: ExternalData
) -> None:
    assert labels(uitkomst(check_id, config, bronnen)) == verwacht


@pytest.mark.parametrize("check_id", [*EXT_IDS, *AHN_IDS])
def test_zonder_bronnen_wordt_er_niets_getoetst(check_id: str, config: CheckConfig) -> None:
    outcome = uitkomst(check_id, config, None)

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("geen externe bronnen" in note for note in outcome.notes)


@pytest.mark.parametrize("check_id", [*EXT_IDS, *AHN_IDS])
def test_objecten_buiten_het_studiegebied_krijgen_geen_uitslag(
    check_id: str, config: CheckConfig, bronnen: ExternalData
) -> None:
    # Put D ligt op (2000, 2000), ruim buiten het fixturegebied. Hij mag nergens
    # als bevinding opduiken, ook al wijkt zijn maaiveld 89 m van het AHN af.
    outcome = uitkomst(check_id, config, bronnen)

    assert "D" not in labels(outcome)


def test_buiten_studiegebied_wordt_geteld_in_de_toelichting(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    outcome = uitkomst("HGT-001", config, bronnen)

    # Putten P en Q liggen binnen het fixturegebied; alleen D valt erbuiten.
    assert any("Buiten studiegebied: 1 van de 10 putten" in note for note in outcome.notes)


def test_nodata_cellen_worden_gemeld(config: CheckConfig, bronnen: ExternalData) -> None:
    # Put F ligt op de nodata-vlek; zonder rasterwaarde is er niets te vergelijken.
    outcome = uitkomst("HGT-001", config, bronnen)

    assert "F" not in labels(outcome)
    assert any("nodata" in note for note in outcome.notes)


def test_typeringspoort_haalt_objecten_uit_de_uitslag(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    dataset = load_dataset(SCENARIO)
    verdacht = next(uri for uri, node in dataset.nodes.items() if node.label == "C")
    context = CheckContext(
        dataset=dataset,
        config=config,
        bronnen=bronnen,
        unreliable_objects=frozenset({verdacht}),
    )
    outcome = run_checks(context, ["HGT-002"]).outcomes[0]

    assert outcome.findings == []
    assert any(MARKERING_NIET_TOETSBAAR in note for note in outcome.notes)


def test_ext001_benoemt_de_relatie_met_het_bouwwerk(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    outcome = uitkomst("EXT-001", config, bronnen)
    relaties = {finding.object_label: finding.details["waarde"] for finding in outcome.findings}

    # Streng 1 steekt door de gevel, streng 4 en de twee putten liggen er binnen.
    assert relaties == {"1": "kruist", "4": "binnen", "P": "binnen", "Q": "binnen"}
    assert all(
        finding.details["drempel"] == config.drempels.ext_pand_buffer_m
        for finding in outcome.findings
    )


def test_ext003_zwijgt_over_een_duiker(config: CheckConfig, bronnen: ExternalData) -> None:
    # Streng 3 is een duiker en kruist water-2; EXT-002 meldt hem wel, EXT-003 niet.
    assert "3" in labels(uitkomst("EXT-002", config, bronnen))
    assert "3" not in labels(uitkomst("EXT-003", config, bronnen))


def test_ext004_is_een_skelet_met_markering(config: CheckConfig, bronnen: ExternalData) -> None:
    outcome = uitkomst("EXT-004", config, bronnen)

    assert outcome.findings == []
    assert outcome.skeleton == MARKERING_BUITEN_SCOPE
    assert any("BRK" in note for note in outcome.notes)


def test_ontbrekende_laag_laat_de_check_overslaan(config: CheckConfig) -> None:
    # Zonder BGT-bestand is er geen putdeksellaag; EXT-005 hoort dat te melden in
    # plaats van elke put als dekselloos te bestempelen.
    basis = load_check_config().bronnen
    zonder_bgt = basis.model_copy(
        update={"map": ".", "bgt": None, "studiegebied": "studiegebied.gpkg", "ahn_dtm": "ahn.tif"}
    )
    bronnen = load_external_data(zonder_bgt, GIS_DIR)
    outcome = uitkomst("EXT-005", config, bronnen)

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("laag niet aanwezig in aangeleverde data" in note for note in outcome.notes)


def test_externe_bevindingen_dragen_een_eigen_locatie(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    # EXT-006 meldt objecten die niet uit de GWSW-dataset komen; zonder eigen
    # coordinaat zou het bij de afbakening tot een studiegebied wegvallen.
    for check_id in ("EXT-006",):
        for bevinding in uitkomst(check_id, config, bronnen).findings:
            assert bevinding.location is not None


def test_hgt003_meldt_beide_richtingen(config: CheckConfig, bronnen: ExternalData) -> None:
    meldingen = {
        bevinding.object_label: bevinding.message
        for bevinding in uitkomst("HGT-003", config, bronnen).findings
    }

    assert "boven het AHN-maaiveld" in meldingen["1"]
    assert "onder het AHN-maaiveld" in meldingen["2"]


def test_hgt001_meldt_een_maaiveld_uit_hetzelfde_hoogtemodel(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Put B heeft een maaiveldhoogte uit AHN2 en wijkt af van het AHN-raster.

    Een afwijking is daar geen fout in de beheerdata maar het verschil tussen twee
    hoogtemodellen. Zonder die kanttekening leest de bevinding als iets wat in het
    veld te herstellen valt.
    """
    outcome = uitkomst("HGT-001", config, bronnen)

    bevinding = next(f for f in outcome.findings if f.object_label == "B")
    assert bevinding.details["inwinning"] == "AHN2"
    assert bevinding.details["uit_hoogtemodel"] is True
    assert any("hoogtemodel" in note for note in outcome.notes)


def test_hgt001_valt_terug_op_de_wijze_van_het_punt(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Put E heeft geen putdekselniveau, net als elke put in De Wolden.

    De check valt dan terug op de maaiveldhoogte, en die draagt haar
    inwinningswijze niet zelf maar op het Punt van de maaiveldorientatie. Zonder
    die terugval zou juist de uit AHN afgeleide helft van de export als
    herkomstloos gelden en zou de kanttekening nooit verschijnen.
    """
    outcome = uitkomst("HGT-001", config, bronnen)

    bevinding = next(f for f in outcome.findings if f.object_label == "E")
    assert bevinding.details["bron"] == "maaiveldhoogte"
    assert bevinding.details["inwinning"] == "AHN2"
    assert bevinding.details["uit_hoogtemodel"] is True
    assert "twee hoogtemodellen" in bevinding.message
    assert any("2 van de" in note and "hoogtemodel" in note for note in outcome.notes)


def test_hgt002_meldt_een_gemeten_maaiveld_zonder_voorbehoud(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    outcome = uitkomst("HGT-002", config, bronnen)

    bevinding = next(f for f in outcome.findings if f.object_label == "C")
    assert bevinding.details["inwinning"] == "Inmeting"
    assert bevinding.details["uit_hoogtemodel"] is False


def test_lege_lijst_zet_de_kanttekening_uit(config: CheckConfig, bronnen: ExternalData) -> None:
    """Zonder geconfigureerde hoogtemodelwijzen valt er niets te kwalificeren."""
    config.inwinning.uit_hoogtemodel = []

    outcome = uitkomst("HGT-001", config, bronnen)

    bevinding = next(f for f in outcome.findings if f.object_label == "B")
    assert bevinding.details["uit_hoogtemodel"] is False


def test_hgt001_en_hgt002_claimen_geen_dekselhoogte() -> None:
    """De titel mag niet meer onvoorwaardelijk over de dekselhoogte spreken.

    In De Wolden ontbreekt `Putdekselniveau` en toetst de check de maaiveldhoogte;
    de titel voedt ook de dekkingsmatrix en het registeroverzicht, dus hij hoort
    beide kenmerken te dekken in plaats van er een te claimen.
    """
    assert REGISTRY["HGT-001"].title == "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 5 cm"
    assert REGISTRY["HGT-002"].title == "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 25 cm"


def test_hgt001_benoemt_welk_kenmerk_vergeleken_is(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Het feitelijk getoetste kenmerk hoort met aantallen in de toelichting."""
    outcome = uitkomst("HGT-001", config, bronnen)

    assert any("Vergeleken is" in note and "maaiveldhoogte" in note for note in outcome.notes)


def test_hgt001_gebruikt_het_juiste_lidwoord(config: CheckConfig, bronnen: ExternalData) -> None:
    """'De maaiveldhoogte', niet 'Het maaiveldhoogte'."""
    outcome = uitkomst("HGT-001", config, bronnen)

    bevinding = next(f for f in outcome.findings if f.details["bron"] == "maaiveldhoogte")
    assert bevinding.message.startswith("De maaiveldhoogte ")


def test_ext001_wijst_het_geraakte_pand_aan(config: CheckConfig, bronnen: ExternalData) -> None:
    """Alle vier de bevindingen raken hetzelfde pand uit de BGT-fixture."""
    outcome = uitkomst("EXT-001", config, bronnen)

    uris = {finding.details["object2_uri"] for finding in outcome.findings}
    aanduidingen = {finding.details["object2_label"] for finding in outcome.findings}

    assert uris == {"bgt:pand/pand-1"}
    assert aanduidingen == {"pand pand-1"}


def test_ext001_registreert_de_treffer_met_geometrie(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    dataset = load_dataset(SCENARIO)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)

    run = run_checks(context, ["EXT-001"])

    treffer = run.treffers.get("bgt:pand/pand-1")
    assert treffer is not None
    assert treffer.bron == "bgt_pand"
    assert treffer.bronbestand == "bgt.gpkg"
    assert treffer.geometrie.geom_type in {"Polygon", "MultiPolygon"}
    assert len(run.treffers) == 1


def test_ext001_bewaart_de_afstand_per_melding(config: CheckConfig, bronnen: ExternalData) -> None:
    """`Melding` draagt de afstand niet; de laag haalt hem uit het register."""
    dataset = load_dataset(SCENARIO)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)

    run = run_checks(context, ["EXT-001"])
    streng = next(f for f in run.findings if f.object_label == "1")

    assert run.treffers.afstand("bgt:pand/pand-1", "EXT-001", streng.object_uri) == 0.0


def test_ext001_verandert_zijn_uitslag_niet(config: CheckConfig, bronnen: ExternalData) -> None:
    """De detectie blijft gelijk; er komt alleen een verwijzing bij."""
    outcome = uitkomst("EXT-001", config, bronnen)
    relaties = {finding.object_label: finding.details["waarde"] for finding in outcome.findings}

    assert relaties == {"1": "kruist", "4": "binnen", "P": "binnen", "Q": "binnen"}
