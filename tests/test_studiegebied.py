"""Tests voor de afbakening tot een studiegebied."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point, Polygon, mapping

from gwswpijplijn.errors import StudyAreaError
from gwswpijplijn.studiegebied import load_study_area


def _maak_geopackage(pad: Path, vlak: Polygon, srs_id: int = 28992, laag: str = "gebied") -> Path:
    """Schrijft een minimale GeoPackage met een enkel vlak."""
    con = sqlite3.connect(pad)
    con.execute("PRAGMA application_id = 0x47504B47")
    con.execute(
        "create table gpkg_contents (table_name text, data_type text, identifier text, "
        "srs_id integer)"
    )
    con.execute(
        "create table gpkg_geometry_columns (table_name text, column_name text, "
        "geometry_type_name text, srs_id integer)"
    )
    con.execute(f'create table "{laag}" (fid integer primary key, geom blob)')
    con.execute("insert into gpkg_contents values (?, 'features', ?, ?)", (laag, laag, srs_id))
    con.execute(
        "insert into gpkg_geometry_columns values (?, 'geom', 'POLYGON', ?)", (laag, srs_id)
    )
    kop = b"GP" + bytes([0, 0]) + struct.pack("<i", srs_id)
    con.execute(f'insert into "{laag}" (geom) values (?)', (kop + vlak.wkb,))
    con.commit()
    con.close()
    return pad


VIERKANT = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])


def test_geopackage_lezen(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "gebied.gpkg", VIERKANT)

    gebied = load_study_area(pad)

    assert gebied.feature_count == 1
    assert gebied.area_ha == pytest.approx(1.0)
    assert gebied.bevat(Point(50, 50))
    assert not gebied.bevat(Point(150, 50))


def test_streng_die_de_grens_kruist_telt_mee(tmp_path: Path) -> None:
    """Anders zou een streng die het gebied uit loopt geheel wegvallen."""
    gebied = load_study_area(_maak_geopackage(tmp_path / "g.gpkg", VIERKANT))

    assert gebied.bevat(LineString([(50, 50), (500, 50)]))
    assert not gebied.bevat(LineString([(200, 200), (500, 500)]))


def test_object_zonder_geometrie_valt_buiten(tmp_path: Path) -> None:
    gebied = load_study_area(_maak_geopackage(tmp_path / "g.gpkg", VIERKANT))

    assert gebied.bevat(None) is False


def test_afwijkend_coordinaatstelsel(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "wgs84.gpkg", VIERKANT, srs_id=4326)

    with pytest.raises(StudyAreaError, match="EPSG:4326"):
        load_study_area(pad)


def test_meerdere_lagen_vraagt_een_keuze(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "twee.gpkg", VIERKANT, laag="een")
    con = sqlite3.connect(pad)
    con.execute("insert into gpkg_contents values ('twee', 'features', 'twee', 28992)")
    con.commit()
    con.close()

    with pytest.raises(StudyAreaError, match="meerdere lagen"):
        load_study_area(pad)

    # Met een expliciete laagnaam gaat het wel goed.
    assert load_study_area(pad, "een").feature_count == 1


def test_onbekende_laag(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "g.gpkg", VIERKANT, laag="een")

    with pytest.raises(StudyAreaError, match="bestaat niet"):
        load_study_area(pad, "twee")


def test_geojson(tmp_path: Path) -> None:
    pad = tmp_path / "gebied.geojson"
    pad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "geometry": mapping(VIERKANT)}],
            }
        ),
        encoding="utf-8",
    )

    gebied = load_study_area(pad)

    assert gebied.bevat(Point(50, 50))
    assert gebied.feature_count == 1


def test_ontbrekend_bestand(tmp_path: Path) -> None:
    with pytest.raises(StudyAreaError, match="bestaat niet"):
        load_study_area(tmp_path / "weg.gpkg")


def test_onbekend_formaat(tmp_path: Path) -> None:
    pad = tmp_path / "gebied.shp"
    pad.write_bytes(b"x")

    with pytest.raises(StudyAreaError, match="onbekend formaat"):
        load_study_area(pad)


def _maak_geopackage_met_attributen(pad: Path, vlak: Polygon, laag: str = "buurt") -> Path:
    """Een GeoPackage met de CBS-attributen die het Koekangerveld-bestand ook heeft."""
    con = sqlite3.connect(pad)
    con.execute("PRAGMA application_id = 0x47504B47")
    con.execute(
        "create table gpkg_contents (table_name text, data_type text, identifier text, "
        "srs_id integer)"
    )
    con.execute(
        "create table gpkg_geometry_columns (table_name text, column_name text, "
        "geometry_type_name text, srs_id integer)"
    )
    con.execute(
        f'create table "{laag}" (fid integer primary key, geom blob, statcode text, statnaam text)'
    )
    con.execute("insert into gpkg_contents values (?, 'features', ?, 28992)", (laag, laag))
    con.execute("insert into gpkg_geometry_columns values (?, 'geom', 'POLYGON', 28992)", (laag,))
    kop = b"GP" + bytes([0, 0]) + struct.pack("<i", 28992)
    con.execute(
        f'insert into "{laag}" (geom, statcode, statnaam) values (?, ?, ?)',
        (kop + vlak.wkb, "BU16901203", "Koekangerveld"),
    )
    con.commit()
    con.close()
    return pad


def test_gebiedsnaam_komt_uit_de_cbs_attributen(tmp_path: Path) -> None:
    """De GIS-uitvoer noemt per object het gebied; dat staat in het gebiedsbestand zelf.

    Een aparte buurtenlaag voor het hele beheergebied is er niet, en is bij een tot
    het gebied begrensde export ook niet nodig.
    """
    pad = _maak_geopackage_met_attributen(
        tmp_path / "buurt.gpkg", Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    )

    gebied = load_study_area(pad)

    assert gebied.gebied == "BU16901203 Koekangerveld"


def test_gebiedsnaam_valt_terug_op_de_laagnaam(tmp_path: Path) -> None:
    """Niet elk gebiedsbestand is een CBS-buurt."""
    pad = _maak_geopackage(tmp_path / "vlak.gpkg", Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]))

    assert load_study_area(pad).gebied == "gebied"
