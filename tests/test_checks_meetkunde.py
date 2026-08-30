"""Directe tests op de meetkundige primitieven onder de TOP-familie.

`checks/meetkunde.py` levert negen functies waar zeven TOP-checks op staan, maar zij
werden tot nu toe alleen indirect geraakt -- via de TTL-fixtures van
`test_checks_topologie_meetkundig.py`. Juist de rommelige-data-terugvallen (een
multi-geometrie, een vlak met een gat, een NaN-coordinaat, een segment met lengte nul)
zijn vanuit een GML-literaal nauwelijks te bouwen. Hier gebeurt dat met shapely-objecten:
geen TTL, geen leeslaag, geen `data/`.

Deze tests leggen het gedrag van vandaag vast; zij schrijven geen nieuw contract voor.
Waar dat gedrag zelf een defect is, staat dat bij de betreffende test (issue #116).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable

import pytest
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)

from nlriochecker.checks.meetkunde import (
    coords_of,
    distinct_coords,
    duplicate_vertices,
    endpoints,
    half_diameter_m,
    is_finite,
    max_offset_from_chord,
    overlap_length,
    vertex_angles,
)

BUITENRING = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]


def zonder_nan_waarschuwing(bouw):
    """Bouwt een geometrie met een NaN erin zonder shapely's RuntimeWarning te tonen.

    Shapely meldt `invalid value encountered in ...` bij het bouwen. De waarschuwing
    hoort bij de fixture en niet bij de code die getoetst wordt; hem hier lokaal
    onderdrukken houdt de testuitvoer schoon zonder een filterregel in pyproject.toml.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return bouw()


def multilijn() -> MultiLineString:
    """Twee losse lijnstukken als een multi-geometrie."""
    return MultiLineString([[(0.0, 0.0), (1.0, 1.0)], [(2.0, 2.0), (3.0, 3.0)]])


def multivlak() -> MultiPolygon:
    """Twee losse driehoeken als een multi-geometrie."""
    return MultiPolygon(
        [
            Polygon([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]),
            Polygon([(2.0, 2.0), (3.0, 2.0), (3.0, 3.0)]),
        ]
    )


def hoek_bij(hoeken: Iterable[tuple[int, float]], index: int) -> float:
    """De hoek bij een vertexindex; faalt als die er niet in staat."""
    for gevonden, graden in hoeken:
        if gevonden == index:
            return graden
    raise AssertionError(f"geen hoek op index {index}")


def test_coords_of_geeft_een_lege_lijst_zonder_geometrie() -> None:
    """Zonder geometrie en op een lege lijn zijn er geen coordinaten."""
    assert coords_of(None) == []
    assert coords_of(LineString()) == []


def test_coords_of_geeft_de_buitenring_van_een_vlak() -> None:
    """Een vlak levert zijn gesloten buitenring; het gat blijft buiten beeld."""
    vlak = Polygon(BUITENRING, [[(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)]])
    assert coords_of(vlak) == [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0)]


def test_coords_of_laat_multi_geometrieen_vallen() -> None:
    """Een multi-geometrie heeft geen eigen coordinatenreeks en levert een lege lijst."""
    assert coords_of(multilijn()) == []
    assert coords_of(multivlak()) == []


def test_endpoints_geeft_none_zonder_geometrie() -> None:
    """Zonder lijn is er geen begin- en eindpunt."""
    assert endpoints(None) is None


def test_endpoints_geeft_begin_en_eindpunt() -> None:
    """Het eerste en het laatste coordinaat worden punten, het herhaalde punt telt mee."""
    begin, eind = endpoints(LineString([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]))
    assert (begin.x, begin.y) == (0.0, 0.0)
    assert (eind.x, eind.y) == (1.0, 0.0)


def test_distinct_coords_vouwt_direct_herhaalde_punten() -> None:
    """Een punt dat zijn voorganger herhaalt valt weg."""
    lijn = LineString([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0)])
    assert distinct_coords(lijn) == [(0.0, 0.0), (1.0, 0.0)]


def test_is_finite_is_onwaar_zonder_geometrie() -> None:
    """Geen geometrie en een lege geometrie tellen niet als eindig."""
    assert is_finite(None) is False
    assert is_finite(LineString()) is False


def test_is_finite_is_onwaar_bij_een_nan_coordinaat() -> None:
    """Een NaN in de coordinaten maakt de geometrie oneindig, niet leeg."""
    lijn = zonder_nan_waarschuwing(lambda: LineString([(0.0, 0.0), (math.nan, 1.0)]))
    assert not lijn.is_empty  # anders zou de uitkomst uit de lege-tak komen
    assert is_finite(lijn) is False


def test_is_finite_is_waar_voor_een_punt() -> None:
    """Een gewoon punt is eindig."""
    assert is_finite(Point(1.0, 2.0)) is True


def test_is_finite_bezoekt_de_binnenringen_van_een_vlak() -> None:
    """Een NaN in het gat telt mee; de buitenring alleen zou eindig zijn."""
    binnenring = [(1.0, 1.0), (2.0, 1.0), (2.0, math.nan), (1.0, 2.0)]
    heel = Polygon(BUITENRING, [[(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)]])
    met_gat = zonder_nan_waarschuwing(lambda: Polygon(BUITENRING, [binnenring]))
    assert is_finite(heel) is True
    assert is_finite(met_gat) is False


def test_is_finite_valt_om_op_een_multi_geometrie() -> None:
    """Gemeten toestand, geen bedoeld contract (issue #116).

    `_flat_coords` haalt de coordinaten met `getattr(geometry, "coords", None)`; die
    default vangt alleen een AttributeError en niet de NotImplementedError die shapely
    bij een multi-geometrie gooit. De multi-tak eronder is daardoor onbereikbaar en
    `is_finite` valt om in plaats van False te geven. `coords_of` vangt diezelfde
    uitzondering wel. Gelijktrekken is een auteursbesluit en valt buiten dit issue.
    """
    with pytest.raises(NotImplementedError):
        is_finite(multilijn())


def test_max_offset_from_chord_is_nul_op_een_rechte_lijn() -> None:
    """Een tussenvertex op de koorde wijkt niet af."""
    assert max_offset_from_chord(LineString([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])) == 0.0


def test_max_offset_from_chord_is_nul_bij_minder_dan_drie_punten() -> None:
    """Na het vouwen blijven er twee punten over; dan is er geen tussenvertex."""
    assert max_offset_from_chord(LineString([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0)])) == 0.0


def test_max_offset_from_chord_meet_de_grootste_uitwijking() -> None:
    """De knik ligt een meter van de rechte verbinding tussen begin en eind."""
    lijn = LineString([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
    assert max_offset_from_chord(lijn) == pytest.approx(1.0)


def test_vertex_angles_geeft_180_graden_bij_recht_doorlopen() -> None:
    """Recht doorlopend is 180 graden."""
    hoeken = vertex_angles(LineString([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]))
    assert len(hoeken) == 1
    assert hoek_bij(hoeken, 1) == pytest.approx(180.0)


def test_vertex_angles_geeft_bijna_nul_graden_bij_een_spike() -> None:
    """Een spike loopt vrijwel helemaal over zichzelf terug: hoek bij nul graden."""
    hoeken = vertex_angles(LineString([(0.0, 0.0), (1.0, 0.0), (0.0, 0.001)]))
    assert len(hoeken) == 1
    assert hoek_bij(hoeken, 1) == pytest.approx(0.0573, abs=1e-4)


def test_vertex_angles_slaat_een_segment_met_2d_lengte_nul_over() -> None:
    """Twee punten die alleen in hoogte verschillen geven geen hoek."""
    assert vertex_angles(LineString([(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0)])) == []


def test_duplicate_vertices_wijst_het_herhaalde_punt_aan() -> None:
    """Het tweede punt valt binnen de tolerantie van zijn voorganger."""
    lijn = LineString([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0)])
    assert duplicate_vertices(lijn, 0.01) == [1]


def test_duplicate_vertices_meet_plat_waar_distinct_coords_3d_leest() -> None:
    """Hetzelfde punt op een andere hoogte: dubbel voor de een, uniek voor de ander.

    `duplicate_vertices` rekent met `math.hypot` over x en y en ziet index 1 als
    dubbel; `distinct_coords` vergelijkt hele tupels en houdt de lijn op drie punten,
    zodat `max_offset_from_chord` en `vertex_angles` iets anders zien.
    """
    lijn = LineString([(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 1.0)])
    assert duplicate_vertices(lijn, 0.0) == [1]
    assert len(distinct_coords(lijn)) == 3


def test_overlap_length_meet_de_bufferdoorsnede() -> None:
    """De buffer verlengt het overlappende deel met de tolerantie aan beide kanten."""
    lijn = LineString([(0.0, 0.0), (10.0, 0.0)])
    ander = LineString([(2.0, 0.0), (6.0, 0.0)])
    assert overlap_length(lijn, ander, 0.1) == pytest.approx(4.2)


def test_half_diameter_m_is_nul_zonder_maat() -> None:
    """Een ontbrekende of nulmaat geeft geen halve diameter."""
    assert half_diameter_m(None, None) == 0.0
    assert half_diameter_m(0, 0) == 0.0


def test_half_diameter_m_rekent_millimeters_naar_meters() -> None:
    """300 mm breed is 0,15 m halve diameter."""
    assert half_diameter_m(300, None) == pytest.approx(0.15)


def test_half_diameter_m_neemt_de_grootste_maat() -> None:
    """Bij een eivormig profiel wint de grootste van breedte en hoogte."""
    assert half_diameter_m(300, 500) == pytest.approx(0.25)
