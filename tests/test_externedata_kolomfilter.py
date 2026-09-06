"""Tests voor het kolomfilter op de externe vectorlagen (issue #147).

Een brede bron -- het BGT-wegdeel draagt 32 kolommen -- werd tot dit issue in zijn
geheel ingelezen, terwijl de checks en de uitvoer maar een handvol kolommen lezen. Sinds
issue #147 leest `_lees_laag` alleen de kolommen uit `LEESKOLOMMEN` (`columns=`), zodat de
rest niet in het geheugen belandt. Een kolom die niet gelezen is, gedraagt zich als een
lege kolom: `VectorLayer.kolom()` geeft er `None` voor, net als voor een ontbrekende.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box

from nlriochecker.checkconfig import load_check_config
from nlriochecker.externedata import (
    HISTORIEVELDEN,
    ExternalDataError,
    _lees_laag,
    load_external_data,
)


def _bronnen(**extra: object):
    return load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": None,
            "ahn_dtm": None,
            "top10nl": None,
            "bgt_pandlagen": ["pand"],
            "bgt_waterlagen": ["waterdeel"],
            "bgt_putdeksellagen": [],
            "bgt_overige_bouwwerklagen": [],
            "bgt_wegdeellagen": [],
            **extra,
        }
    )


def _bgt_met_extra_kolom(map_pad: Path) -> None:
    """Een BGT-waterdeellaag met een gelezen kolom (`type`) en een niet-gelezen (`bronhouder`)."""
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    water = gpd.GeoDataFrame(
        {
            "lokaal_id": ["w1", "w2"],
            "type": ["waterloop", "greppel"],
            "bronhouder": ["G0000", "G0001"],
            "eind_registratie": [pd.NaT, pd.NaT],
        },
        geometry=[box(10, 10, 20, 20), box(30, 30, 40, 40)],
        crs="EPSG:28992",
    )
    water.to_file(map_pad / "bgt.gpkg", layer="waterdeel", driver="GPKG")
    gpd.GeoDataFrame(
        {"lokaal_id": ["p1"]}, geometry=[box(70, 70, 80, 80)], crs="EPSG:28992"
    ).to_file(map_pad / "bgt.gpkg", layer="pand", driver="GPKG")


def test_alleen_de_leeskolommen_worden_ingelezen(tmp_path: Path) -> None:
    _bgt_met_extra_kolom(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    water = data.layer("bgt_water")
    assert water is not None
    # De niet-gelezen kolom staat niet in de attributen ...
    assert all("bronhouder" not in rij for rij in water.attributes)
    # ... en gedraagt zich als een lege kolom.
    assert water.kolom("bronhouder") == [None, None]
    # De gelezen kolommen zijn er wel.
    assert water.kolom("type") == ["waterloop", "greppel"]
    assert [rij["lokaal_id"] for rij in water.attributes] == ["w1", "w2"]


def _nwb_met_kleine_letters(map_pad: Path) -> None:
    """Een NWB-achtige laag die zijn kolommen in kleine letters schrijft (Koekangerveld)."""
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(
        {"wvk_id": ["1"], "wegbehsrt": ["G"], "stt_naam": ["Dorpsstraat"]},
        geometry=[box(0, 0, 100, 1)],
        crs="EPSG:28992",
    ).to_file(map_pad / "nwb.gpkg", layer="wegvak", driver="GPKG")
    # De pand-/waterlagen die `_bronnen` verwacht, minimaal gevuld.
    gpd.GeoDataFrame(
        {"lokaal_id": ["p1"]}, geometry=[box(70, 70, 80, 80)], crs="EPSG:28992"
    ).to_file(map_pad / "bgt.gpkg", layer="pand", driver="GPKG")
    gpd.GeoDataFrame(
        {"lokaal_id": ["w1"]}, geometry=[box(10, 10, 20, 20)], crs="EPSG:28992"
    ).to_file(map_pad / "bgt.gpkg", layer="waterdeel", driver="GPKG")


def test_kolomnaam_wordt_hoofdletterongevoelig_ingelezen(tmp_path: Path) -> None:
    """`WEGBEHSRT` uit `wegvakken.py` moet ook een veld `wegbehsrt` in de bron treffen.

    Het De Wolden-extract schrijft de NWB-kolommen in hoofdletters, het Koekangerveld-extract
    in kleine letters; `columns=` van pyogrio is hoofdlettergevoelig. Het filter matcht
    daarom hoofdletterongevoelig en leest het veld in zijn eigen schrijfwijze in.
    """
    _nwb_met_kleine_letters(tmp_path / "b")

    data = load_external_data(_bronnen(nwb_wegvakken="nwb.gpkg"), tmp_path / "b")

    nwb = data.layer("nwb_wegvak")
    assert nwb is not None
    assert nwb.kolom("WEGBEHSRT") == ["G"]
    assert nwb.kolom("STT_NAAM") == ["Dorpsstraat"]


def test_onleesbare_laag_meldt_maar_een_keer(tmp_path: Path) -> None:
    """De foutmelding van een onleesbare laag mag niet dubbel ingepakt worden.

    `_leeskolommen` (`pyogrio.read_info`) draait vóór het `try`-blok van `_lees_laag`, zodat
    de `ExternalDataError` die het bij een kapotte bron gooit niet nog eens door de buitenste
    `except` wordt ingepakt tot '... is niet leesbaar (...: ... is niet leesbaar (...))'.
    """
    kapot = tmp_path / "kapot.gpkg"
    kapot.write_text("dit is geen GeoPackage")

    with pytest.raises(ExternalDataError) as fout:
        _lees_laag(kapot, "welke_laag_dan_ook", [])

    assert str(fout.value).count("is niet leesbaar") == 1


def test_leeskolommen_dekt_alle_lezers() -> None:
    """De drifttest: elke kolom die een lezer noemt, staat in `LEESKOLOMMEN`.

    `_lees_laag` leest alleen `LEESKOLOMMEN`; loopt die lijst achter op wat een check of de
    uitvoer werkelijk leest, dan valt een kolom stil weg en verandert de uitvoer. Deze test
    bindt de drie bronnen aan de lijst zodat dat opvalt.
    """
    from nlriochecker.checks import wegvakken
    from nlriochecker.checks.treffers import SLEUTELKOLOMMEN
    from nlriochecker.externedata import LEESKOLOMMEN

    gedekt = {naam.casefold() for naam in LEESKOLOMMEN}

    # Sleutelkolommen (treffers.py) en het type (extern.py, gpkg.py).
    for kolom in (*SLEUTELKOLOMMEN, "type"):
        assert kolom.casefold() in gedekt, kolom
    # Historievelden (_alleen_actueel).
    for kolom in HISTORIEVELDEN:
        assert kolom.casefold() in gedekt, kolom
    # De KOLOM_*-constanten van EXT-009 (wegvakken.py).
    kolom_namen = [getattr(wegvakken, naam) for naam in dir(wegvakken) if naam.startswith("KOLOM_")]
    assert kolom_namen  # er zijn er
    for kolom in kolom_namen:
        assert kolom.casefold() in gedekt, kolom
