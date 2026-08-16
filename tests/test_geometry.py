"""Tests voor de GML-parser."""

from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point, Polygon

from gwswpijplijn.geometry import GeometryError, parse_gml, parse_gml_z

PUNT_3D = '<gml:Point xmlns:gml="g"><gml:pos>168462.01 442691.30 22.45</gml:pos></gml:Point>'
PUNT_2D = '<gml:Point xmlns:gml="g"><gml:pos>168462.51 442691.30</gml:pos></gml:Point>'
LIJN_3D = (
    '<gml:LineString xmlns:gml="g"><gml:posList srsDimension="3">'
    "1 2 30 4 5 60</gml:posList></gml:LineString>"
)
LIJN_2D = (
    '<gml:LineString xmlns:gml="g"><gml:posList srsDimension="2">'
    "1 2 4 5</gml:posList></gml:LineString>"
)
RING = (
    '<gml:Polygon xmlns:gml="g"><gml:exterior><gml:LinearRing><gml:posList srsDimension="2">'
    "0 0 0 1 1 1 0 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
)


def test_punt_met_hoogte() -> None:
    assert parse_gml(PUNT_3D) == Point(168462.01, 442691.30)
    assert parse_gml_z(PUNT_3D) == [22.45]


def test_punt_zonder_hoogte() -> None:
    # gml:pos draagt in de GWSW-export nooit een srsDimension; het aantal
    # waarden bepaalt dan de dimensie.
    assert parse_gml(PUNT_2D) == Point(168462.51, 442691.30)
    assert parse_gml_z(PUNT_2D) == [None]


def test_lijn_driedimensionaal() -> None:
    assert parse_gml(LIJN_3D) == LineString([(1, 2), (4, 5)])
    assert parse_gml_z(LIJN_3D) == [30.0, 60.0]


def test_lijn_tweedimensionaal() -> None:
    assert parse_gml(LIJN_2D) == LineString([(1, 2), (4, 5)])
    assert parse_gml_z(LIJN_2D) == [None, None]


def test_polygoon_uit_linearring() -> None:
    vlak = parse_gml(RING)

    assert isinstance(vlak, Polygon)
    assert vlak.area == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("literal", "melding"),
    [
        ("<gml:Kromme>1 2</gml:Kromme>", "GML-soort"),
        ('<gml:Point xmlns:gml="g"></gml:Point>', "gml:pos"),
        ('<gml:Point xmlns:gml="g"><gml:pos>een twee</gml:pos></gml:Point>', "niet-numeriek"),
        (
            '<gml:LineString xmlns:gml="g"><gml:posList srsDimension="3">1 2 3 4'
            "</gml:posList></gml:LineString>",
            "srsDimension",
        ),
    ],
)
def test_onbruikbare_geometrie(literal: str, melding: str) -> None:
    with pytest.raises(GeometryError, match=melding):
        parse_gml(literal)


def test_is_finite_verdraagt_een_vlak() -> None:
    """Een put met een vlak als geometrie mag TOP-009 niet laten omvallen.

    `hasattr(polygon, "coords")` roept de property aan, en die gooit bij shapely
    een NotImplementedError -- geen AttributeError, dus hasattr vangt hem niet op.
    De fixture top016_ongeldige_geometrie.ttl bevat zo'n vlak.
    """
    from shapely.geometry import Polygon

    from gwswpijplijn.checks.meetkunde import is_finite

    assert is_finite(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])) is True
    assert is_finite(Polygon([(0, 0), (float("inf"), 0), (1, 1), (0, 1)])) is False
