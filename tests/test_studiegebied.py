"""Tests voor de afbakening tot een studiegebied."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point, Polygon, mapping

from nlriochecker.errors import StudyAreaError
from nlriochecker.studiegebied import (
    RdGrenzen,
    load_studiegebieden,
    load_study_area,
    mapnaam,
)


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


@pytest.mark.parametrize(
    ("naam", "verwacht"),
    [
        ("De Wolden", "de_wolden"),
        ("Zuidwolde-Noord", "zuidwolde_noord"),
        ("Échéllé", "echelle"),
        ("A/B", "a_b"),
        ("  dubbele   spatie ", "dubbele_spatie"),
        ("BUURT 01", "buurt_01"),
    ],
)
def test_mapnaam_saneert(naam: str, verwacht: str) -> None:
    assert mapnaam(naam) == verwacht


def test_mapnaam_zonder_bruikbare_tekens_is_een_fout() -> None:
    """Een naamloze map is geen uitvoer; dan liever een foutmelding met de naam erin."""
    with pytest.raises(StudyAreaError, match="geen bruikbare mapnaam"):
        mapnaam("///")


def _maak_buurten_gpkg(
    pad: Path,
    vlakken: list[tuple[str, Polygon]],
    laag: str = "buurten",
    kolom: str = "naam_gebied",
) -> Path:
    """Schrijft een GeoPackage met meerdere buurten en een naamkolom."""
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
    con.execute(f'create table "{laag}" (fid integer primary key, "{kolom}" text, geom blob)')
    con.execute("insert into gpkg_contents values (?, 'features', ?, 28992)", (laag, laag))
    con.execute("insert into gpkg_geometry_columns values (?, 'geom', 'POLYGON', 28992)", (laag,))
    kop = b"GP" + bytes([0, 0]) + struct.pack("<i", 28992)
    for naam, vlak in vlakken:
        con.execute(f'insert into "{laag}" ("{kolom}", geom) values (?, ?)', (naam, kop + vlak.wkb))
    con.commit()
    con.close()
    return pad


def _schrijf_geojson(pad: Path, inhoud: dict[str, object]) -> Path:
    """Schrijft een GeoJSON-bestand."""
    pad.write_text(json.dumps(inhoud), encoding="utf-8")
    return pad


NOORD = Polygon([(0, 100), (100, 100), (100, 200), (0, 200)])
ZUID = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
RD_GRENZEN = RdGrenzen(0.0, 300_000.0, 300_000.0, 620_000.0)


def test_twee_features_leveren_twee_gebieden(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    gebieden = load_studiegebieden(pad)

    assert [gebied.gebied for gebied in gebieden.gebieden] == ["Noord", "Zuid"]
    assert [gebied.name for gebied in gebieden.gebieden] == ["Noord", "Zuid"]
    assert not gebieden.enkel
    assert gebieden.totaal.area_ha == pytest.approx(2.0)
    assert gebieden.totaal.feature_count == 2


def test_een_feature_houdt_het_bestaande_gedrag(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "vlak.gpkg", VIERKANT)

    gebieden = load_studiegebieden(pad)

    assert gebieden.enkel
    assert gebieden.gebieden[0].name == "vlak:gebied"
    assert gebieden.gebieden[0].gebied == "gebied"


def test_naam_gebied_bij_een_feature_wint_van_de_terugval(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "een.gpkg", [("Koekangerveld", VIERKANT)])

    assert load_studiegebieden(pad).gebieden[0].gebied == "Koekangerveld"


def test_naam_gebied_ontbreekt_bij_meerdere_features(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)], kolom="naam")

    with pytest.raises(StudyAreaError, match="naam_gebied"):
        load_studiegebieden(pad)


def test_lege_naam_noemt_de_rij(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("   ", ZUID)])

    with pytest.raises(StudyAreaError, match="rij 2"):
        load_studiegebieden(pad)


def test_dubbele_naam_is_een_fout(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Noord", ZUID)])

    with pytest.raises(StudyAreaError, match="Noord"):
        load_studiegebieden(pad)


def test_botsende_mapnamen_zijn_een_fout(tmp_path: Path) -> None:
    """Twee namen die dezelfde map opleveren zouden elkaars uitvoer overschrijven."""
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("De Wolden", NOORD), ("de-wolden", ZUID)])

    with pytest.raises(StudyAreaError, match="dezelfde mapnaam"):
        load_studiegebieden(pad)


def test_niet_polygonen_worden_gemeld_en_overgeslagen(tmp_path: Path) -> None:
    pad = _schrijf_geojson(
        tmp_path / "gemengd.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": mapping(VIERKANT)},
                {"type": "Feature", "properties": {}, "geometry": mapping(Point(10, 10))},
            ],
        },
    )

    gebieden = load_studiegebieden(pad)

    assert gebieden.enkel
    assert any("Point" in melding for melding in gebieden.overgeslagen)


def test_geometrycollection_wordt_niet_uitgepakt(tmp_path: Path) -> None:
    """Uitpakken zou stilzwijgend vlakken toevoegen die de gebruiker niet aanleverde."""
    pad = _schrijf_geojson(
        tmp_path / "collectie.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": mapping(VIERKANT)},
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "GeometryCollection",
                        "geometries": [mapping(VIERKANT)],
                    },
                },
            ],
        },
    )

    gebieden = load_studiegebieden(pad)

    assert gebieden.enkel
    assert any("GeometryCollection" in melding for melding in gebieden.overgeslagen)


def test_alleen_niet_polygonen_is_een_fout(tmp_path: Path) -> None:
    pad = _schrijf_geojson(
        tmp_path / "punten.geojson",
        {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": mapping(Point(10, 10))}],
        },
    )

    with pytest.raises(StudyAreaError, match="geen enkel vlak"):
        load_studiegebieden(pad)


def test_geojson_buiten_de_rd_bounds(tmp_path: Path) -> None:
    pad = _schrijf_geojson(
        tmp_path / "wgs84.geojson",
        mapping(Polygon([(6.4, 52.7), (6.5, 52.7), (6.5, 52.8), (6.4, 52.8)])),
    )

    with pytest.raises(StudyAreaError, match="WGS84"):
        load_studiegebieden(pad, grenzen=RD_GRENZEN)


def test_geojson_met_legacy_crs_wordt_geaccepteerd(tmp_path: Path) -> None:
    """Een bestand dat zelf 28992 noemt hoeft niet binnen de bounds te liggen."""
    pad = _schrijf_geojson(
        tmp_path / "lokaal.geojson",
        {
            **mapping(VIERKANT),
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::28992"}},
        },
    )

    assert load_studiegebieden(pad, grenzen=RD_GRENZEN).enkel


def test_geojson_zonder_grenzen_wordt_niet_getoetst(tmp_path: Path) -> None:
    """Wie de grenzen niet meegeeft, krijgt geen verzonnen oordeel over het stelsel."""
    pad = _schrijf_geojson(tmp_path / "lokaal.geojson", mapping(VIERKANT))

    assert load_studiegebieden(pad).enkel


def test_selecteer_kiest_gebieden(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    keuze = load_studiegebieden(pad).selecteer(["Zuid"])

    assert [gebied.gebied for gebied in keuze.gebieden] == ["Zuid"]
    assert keuze.beschikbaar == ("Noord", "Zuid")


def test_selecteer_onbekende_naam_noemt_de_beschikbare(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    with pytest.raises(StudyAreaError, match="Noord, Zuid"):
        load_studiegebieden(pad).selecteer(["Oost"])
