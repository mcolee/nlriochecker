"""Controleert met QGIS zelf dat de stijlen uit het bestand geladen worden.

Deze test is de enige die het echte antwoord geeft op de vraag waar ronde 2 mee
begon: past QGIS de meegeleverde stijlen toe? Hij wordt overgeslagen waar PyQGIS
niet geinstalleerd is, want QGIS is geen afhankelijkheid van dit project.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

qgis_core = pytest.importorskip("qgis.core", reason="PyQGIS is hier niet geinstalleerd")

from gwswpijplijn.checkconfig import load_check_config  # noqa: E402
from gwswpijplijn.checks import CheckContext, run_checks  # noqa: E402
from gwswpijplijn.dataset import load_dataset  # noqa: E402
from gwswpijplijn.uitvoer.gpkg import FEATURELAGEN, schrijf_geopackage  # noqa: E402
from gwswpijplijn.uitvoer.melding import bouw_meldingen  # noqa: E402

pytestmark = pytest.mark.qgis

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
RUNDATUM = date(2026, 8, 16)


@pytest.fixture(scope="module")
def qgis_app():
    """Een QGIS-toepassing zonder scherm, een keer per module."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qgis_core.QgsApplication.setPrefixPath("/usr", True)
    app = qgis_core.QgsApplication([], False)
    app.initQgis()
    yield app
    app.exitQgis()


@pytest.fixture(scope="module")
def geschreven_gpkg(tmp_path_factory) -> Path:
    """Een GeoPackage van de mechanische fixture, met alle vier de lagen."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config))
    map_ = tmp_path_factory.mktemp("qgis")
    return schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), map_, RUNDATUM)


@pytest.mark.parametrize("laag", FEATURELAGEN)
def test_qgis_laadt_de_stijl_uit_het_bestand(qgis_app, geschreven_gpkg: Path, laag: str) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")

    assert vector.isValid(), f"laag {laag} is niet leesbaar"
    boodschap, gelukt = vector.loadDefaultStyle()

    assert gelukt, f"QGIS past de stijl van {laag} niet toe: {boodschap}"
    assert "Provider" in boodschap


def test_de_stijl_van_de_strengen_kent_de_richtingsregels(qgis_app, geschreven_gpkg: Path) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=strengen", "s", "ogr")
    vector.loadDefaultStyle()

    labels = {regel.label() for regel in vector.renderer().rootRule().children()}

    assert {
        "BOB volgt de lijnrichting",
        "BOB tegen de lijnrichting in",
        "BOB-richting niet te bepalen",
    } <= labels


def test_elke_stijlexpressie_verwijst_naar_bestaande_kolommen(
    qgis_app, geschreven_gpkg: Path
) -> None:
    """Een tikfout in een kolomnaam levert een lege kaart op, geen foutmelding."""
    for laag in FEATURELAGEN:
        vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")
        vector.loadDefaultStyle()
        velden = set(vector.fields().names())
        renderer = vector.renderer()
        expressies = [renderer.filter()] if hasattr(renderer, "filter") else []
        if hasattr(renderer, "rootRule"):
            expressies += [regel.filterExpression() for regel in renderer.rootRule().children()]
        for tekst in filter(None, expressies):
            gebruikt = set(qgis_core.QgsExpression(tekst).referencedColumns())
            assert gebruikt <= velden, f"{laag}: {tekst} verwijst naar {gebruikt - velden}"
