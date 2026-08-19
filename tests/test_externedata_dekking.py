"""Tests voor de dekkingspoort op de externe bronnen.

Een extract dat maar een deel van het bereik dekt geeft een misleidend schone
uitkomst: geen treffer leest als geen probleem, terwijl de bron er domweg niet was.
Deze poort maakt daar een fout van. Wat hij niet kan -- een gat middenin zien -- staat
hier ook vastgelegd, zodat de belofte niet groter wordt dan de meting.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import box

from gpkghelper import schrijf_vlakken
from nlriochecker.checkconfig import ExternalSources, load_check_config
from nlriochecker.externedata import Dekkingseis, ExternalDataError, load_external_data

# Het bereik waarvoor de bronnen geldig verklaard worden.
GEBIED = box(0, 0, 100, 100)


def _bronnen(map_pad: Path, panden: list, met_gebied: bool = True) -> ExternalSources:
    """Schrijft een miniatuurbron met een pandenlaag en een bereik."""
    map_pad.mkdir(parents=True, exist_ok=True)
    schrijf_vlakken(
        map_pad / "bgt.gpkg",
        "pand",
        [({"lokaal_id": f"p{index}"}, vlak) for index, vlak in enumerate(panden)],
    )
    if met_gebied:
        schrijf_vlakken(
            map_pad / "studiegebied.gpkg", "studiegebied", [({"lokaal_id": "g"}, GEBIED)]
        )
    return load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": "studiegebied.gpkg" if met_gebied else None,
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
            "bgt_waterlagen": [],
            "bgt_putdeksellagen": [],
            "bgt_overige_bouwwerklagen": [],
        }
    )


def test_te_kleine_laag_faalt_met_beide_omhullenden(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)])

    with pytest.raises(ExternalDataError) as fout:
        load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    tekst = str(fout.value)
    assert "bgt_pand" in tekst
    assert "tekort" in tekst
    assert "10.0" in tekst
    assert "dekking_tolerantie_m" in tekst


def test_dekkende_laag_slaagt(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(-10, -10, 110, 110)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_pand") is not None


def test_marge_vraagt_dekking_buiten_het_bereik(tmp_path: Path) -> None:
    """Een laag die exact op het bereik geknipt is, dekt de zoekafstand niet."""
    bronnen = _bronnen(tmp_path / "b", [GEBIED])

    with pytest.raises(ExternalDataError):
        load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(10.0, 0.0))


def test_tolerantie_laat_een_klein_tekort_toe(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(2, 2, 98, 98)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 5.0))

    assert data.layer("bgt_pand") is not None


def test_gat_middenin_slaagt(tmp_path: Path) -> None:
    """De gedocumenteerde beperking: bbox-dekking ziet geen gat in het extract."""
    bronnen = _bronnen(tmp_path / "b", [box(0, 0, 20, 100), box(80, 0, 100, 100)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_pand") is not None


def test_zonder_bereik_draait_de_poort_niet(tmp_path: Path) -> None:
    """Zonder bereik geeft geen enkele EXT-check een uitslag; er valt niets te maskeren."""
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)], met_gebied=False)

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.extent is None
    assert data.layer("bgt_pand") is not None


def test_ontbrekende_laag_raakt_de_poort_niet(tmp_path: Path) -> None:
    """Een bron die niet aangeleverd is blijft toegestaan; de check meldt dat zelf."""
    bronnen = _bronnen(tmp_path / "b", [box(-10, -10, 110, 110)]).model_copy(
        update={"bgt_waterlagen": ["waterdeel"]}
    )

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_water") is None
    assert any("bgt_water" in ontbreekt for ontbreekt in data.missing)


def test_zonder_dekkingseis_geen_poort(tmp_path: Path) -> None:
    """Een beller die de eis niet kent, krijgt geen verzonnen oordeel."""
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)])

    assert load_external_data(bronnen, tmp_path / "b").layer("bgt_pand") is not None


def test_te_klein_raster_faalt(tmp_path: Path) -> None:
    """De HGT-checks falen even stil als de EXT-checks; het raster telt dus mee."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    map_pad = tmp_path / "b"
    bronnen = _bronnen(map_pad, [box(-10, -10, 110, 110)]).model_copy(update={"ahn_dtm": "ahn.tif"})
    with rasterio.open(
        map_pad / "ahn.tif",
        "w",
        driver="GTiff",
        height=20,
        width=20,
        count=1,
        dtype="float32",
        crs="EPSG:28992",
        transform=from_origin(0.0, 20.0, 1.0, 1.0),
    ) as doel:
        doel.write(__import__("numpy").full((20, 20), 10.0, dtype="float32"), 1)

    with pytest.raises(ExternalDataError) as fout:
        load_external_data(bronnen, map_pad, dekkingseis=Dekkingseis(0.0, 0.0))

    assert "ahn" in str(fout.value).lower()


def test_raster_krijgt_geen_marge(tmp_path: Path) -> None:
    """Bemonsteren is puntsgewijs; een raster hoeft niet buiten het bereik te reiken."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    map_pad = tmp_path / "b"
    bronnen = _bronnen(map_pad, [box(-20, -20, 120, 120)]).model_copy(update={"ahn_dtm": "ahn.tif"})
    with rasterio.open(
        map_pad / "ahn.tif",
        "w",
        driver="GTiff",
        height=100,
        width=100,
        count=1,
        dtype="float32",
        crs="EPSG:28992",
        transform=from_origin(0.0, 100.0, 1.0, 1.0),
    ) as doel:
        doel.write(__import__("numpy").full((100, 100), 10.0, dtype="float32"), 1)

    data = load_external_data(bronnen, map_pad, dekkingseis=Dekkingseis(10.0, 0.0))

    assert data.raster is not None
