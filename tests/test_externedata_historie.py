"""Tests voor het actualiteitsfilter op de BGT-lagen (issue #58).

Elk BGT-object draagt zijn registratiegeschiedenis mee: de levende versie heeft
`eind_registratie` leeg, elke afgesloten oudere versie heeft die kolom gevuld. Zonder
filter draaien de ruimtelijke toetsen over de hele stapel versies; op De Wolden is
meer dan de helft van de waterdelen oude historie.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from shapely.geometry import box

from gpkghelper import schrijf_vlakken
from nlriochecker.checkconfig import load_check_config
from nlriochecker.externedata import load_external_data


def _bgt_met_historie(map_pad: Path) -> Path:
    """Een BGT-achtig bestand: een waterdeellaag met historie en een pandlaag zonder."""
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    pad = map_pad / "bgt.gpkg"
    water = gpd.GeoDataFrame(
        {
            "lokaal_id": ["actueel", "verlopen", "beeindigd"],
            "eind_registratie": [pd.NaT, pd.Timestamp("2020-01-01"), pd.NaT],
            "termination_date": [pd.NaT, pd.NaT, pd.Timestamp("2021-06-01")],
        },
        geometry=[box(10, 10, 20, 20), box(30, 30, 40, 40), box(50, 50, 60, 60)],
        crs="EPSG:28992",
    )
    water.to_file(pad, layer="waterdeel", driver="GPKG")
    schrijf_vlakken(pad, "pand", [({"lokaal_id": "p1"}, box(70, 70, 80, 80))])
    return pad


def _bronnen():
    return load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": None,
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
            "bgt_waterlagen": ["waterdeel"],
            "bgt_putdeksellagen": [],
            "bgt_overige_bouwwerklagen": [],
        }
    )


def test_verlopen_versies_vallen_af_en_worden_geteld(tmp_path: Path) -> None:
    _bgt_met_historie(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    water = data.layer("bgt_water")
    assert water is not None
    assert [rij["lokaal_id"] for rij in water.attributes] == ["actueel"]
    assert (
        "`bgt.gpkg` laag 'waterdeel': 2 verlopen objectversies overgeslagen "
        "(eind_registratie of termination_date gevuld); 1 actuele feature gelezen."
    ) in data.notes


def test_laag_zonder_historievelden_gaat_ongefilterd_door(tmp_path: Path) -> None:
    _bgt_met_historie(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    pand = data.layer("bgt_pand")
    assert pand is not None
    assert len(pand) == 1
    assert not any("laag 'pand'" in notitie for notitie in data.notes)


def _bgt_met_een_veld(map_pad: Path) -> Path:
    """Een BGT-achtig bestand waarvan de waterdeellaag alleen `eind_registratie` draagt.

    Niet elke BGT-export levert beide historievelden; het filter moet dan op het veld
    werken dat er wél is.
    """
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    pad = map_pad / "bgt.gpkg"
    water = gpd.GeoDataFrame(
        {
            "lokaal_id": ["actueel", "verlopen"],
            "eind_registratie": [pd.NaT, pd.Timestamp("2020-01-01")],
        },
        geometry=[box(10, 10, 20, 20), box(30, 30, 40, 40)],
        crs="EPSG:28992",
    )
    water.to_file(pad, layer="waterdeel", driver="GPKG")
    schrijf_vlakken(pad, "pand", [({"lokaal_id": "p1"}, box(70, 70, 80, 80))])
    return pad


def _bgt_zonder_verlopen(map_pad: Path) -> Path:
    """Een BGT-achtig bestand met historievelden waarin niets verlopen is."""
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    pad = map_pad / "bgt.gpkg"
    water = gpd.GeoDataFrame(
        {
            "lokaal_id": ["een", "twee"],
            "eind_registratie": [pd.NaT, pd.NaT],
            "termination_date": [pd.NaT, pd.NaT],
        },
        geometry=[box(10, 10, 20, 20), box(30, 30, 40, 40)],
        crs="EPSG:28992",
    )
    water.to_file(pad, layer="waterdeel", driver="GPKG")
    schrijf_vlakken(pad, "pand", [({"lokaal_id": "p1"}, box(70, 70, 80, 80))])
    return pad


def test_een_enkel_historieveld_filtert_op_dat_veld(tmp_path: Path) -> None:
    _bgt_met_een_veld(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    water = data.layer("bgt_water")
    assert water is not None
    assert [rij["lokaal_id"] for rij in water.attributes] == ["actueel"]
    assert (
        "`bgt.gpkg` laag 'waterdeel': 1 verlopen objectversie overgeslagen "
        "(eind_registratie gevuld); 1 actuele feature gelezen."
    ) in data.notes


def test_nul_verlopen_versies_levert_toch_een_notitie(tmp_path: Path) -> None:
    _bgt_zonder_verlopen(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    water = data.layer("bgt_water")
    assert water is not None
    assert len(water) == 2
    assert (
        "`bgt.gpkg` laag 'waterdeel': 0 verlopen objectversies overgeslagen "
        "(eind_registratie of termination_date gevuld); 2 actuele features gelezen."
    ) in data.notes
