"""Meetkundige hulpfuncties die meerdere checks delen."""

from __future__ import annotations

import math

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry


def coords_of(geometry: BaseGeometry | None) -> list[tuple[float, ...]]:
    """De coordinaten van een enkelvoudige geometrie, of een lege lijst.

    Een GML-literaal in de leidinggeometrie hoeft geen lijn te zijn: een export
    die er een polygoon in zet levert een Polygon op. Die heeft geen `coords` maar
    wel een buitenring, en de meetkundige checks moeten er niet op stuklopen.
    """
    if geometry is None or geometry.is_empty:
        return []
    buitenring = getattr(geometry, "exterior", None)
    if buitenring is not None:
        return list(buitenring.coords)
    try:
        return list(geometry.coords)
    except (AttributeError, NotImplementedError):
        # Multi-geometrieen hebben geen eigen coordinatenreeks; die vallen af.
        return []


def endpoints(line: LineString | None) -> tuple[Point, Point] | None:
    """Het begin- en eindpunt van een lijngeometrie, of None."""
    coordinaten = coords_of(line)
    if len(coordinaten) < 2:
        return None
    return Point(coordinaten[0][:2]), Point(coordinaten[-1][:2])


def distinct_coords(line: LineString | None) -> list[tuple[float, ...]]:
    """De coordinaten van een lijn zonder direct herhaalde punten."""
    uniek: list[tuple[float, ...]] = []
    for punt in coords_of(line):
        if not uniek or punt != uniek[-1]:
            uniek.append(punt)
    return uniek


def is_finite(geometry: BaseGeometry | None) -> bool:
    """Geeft aan of alle coordinaten eindige getallen zijn."""
    if geometry is None or geometry.is_empty:
        return False
    return all(math.isfinite(waarde) for waarde in _flat_coords(geometry))


def _flat_coords(geometry: BaseGeometry):
    """Alle coordinaatwaarden van een geometrie, plat achter elkaar.

    Een vlak heeft geen eigen `coords` maar wel ringen; `hasattr` helpt daar niet,
    want shapely laat die property een NotImplementedError gooien in plaats van een
    AttributeError. Vlakken horen niet in een GWSW-export thuis, maar ze komen er
    voor (zie de fixture top016_ongeldige_geometrie.ttl) en TOP-009 hoort ze te
    kunnen melden in plaats van erop om te vallen.
    """
    if isinstance(geometry, Polygon):
        yield from _flat_coords(geometry.exterior)
        for ring in geometry.interiors:
            yield from _flat_coords(ring)
        return
    coords = getattr(geometry, "coords", None)
    if coords is not None:
        for punt in coords:
            yield from punt
        return
    for deel in getattr(geometry, "geoms", ()):
        yield from _flat_coords(deel)


def max_offset_from_chord(line: LineString) -> float:
    """De grootste afstand van een tussenvertex tot de rechte begin-eindverbinding."""
    punten = distinct_coords(line)
    if len(punten) < 3:
        return 0.0
    koorde = LineString([punten[0], punten[-1]])
    return max(koorde.distance(Point(punt[0], punt[1])) for punt in punten[1:-1])


def vertex_angles(line: LineString) -> list[tuple[int, float]]:
    """De hoek in graden bij elke tussenvertex, met haar index.

    De hoek is die tussen de twee aansluitende segmenten: 180 graden is recht
    doorlopend, 0 graden is helemaal terug over zichzelf (een spike).
    """
    punten = distinct_coords(line)
    hoeken: list[tuple[int, float]] = []
    for index in range(1, len(punten) - 1):
        vorige, huidig, volgende = punten[index - 1], punten[index], punten[index + 1]
        eerste = (vorige[0] - huidig[0], vorige[1] - huidig[1])
        tweede = (volgende[0] - huidig[0], volgende[1] - huidig[1])
        lengte_een = math.hypot(*eerste)
        lengte_twee = math.hypot(*tweede)
        if lengte_een == 0.0 or lengte_twee == 0.0:
            continue
        cosinus = (eerste[0] * tweede[0] + eerste[1] * tweede[1]) / (lengte_een * lengte_twee)
        hoeken.append((index, math.degrees(math.acos(max(-1.0, min(1.0, cosinus))))))
    return hoeken


def duplicate_vertices(line: LineString, tolerantie: float) -> list[int]:
    """De indexen van vertices die binnen de tolerantie op hun voorganger vallen."""
    punten = coords_of(line)
    dubbel: list[int] = []
    for index in range(1, len(punten)):
        vorige, huidig = punten[index - 1], punten[index]
        if math.hypot(huidig[0] - vorige[0], huidig[1] - vorige[1]) <= tolerantie:
            dubbel.append(index)
    return dubbel


def overlap_length(line: LineString, other: LineString, tolerantie: float) -> float:
    """De lengte waarover een lijn binnen de buffer van een andere lijn valt."""
    doorsnede = line.intersection(other.buffer(tolerantie))
    return float(doorsnede.length)


def half_diameter_m(breedte_mm: float | None, hoogte_mm: float | None) -> float:
    """De halve breedte van een profiel in meters; nul als de maat ontbreekt."""
    maten = [maat for maat in (breedte_mm, hoogte_mm) if maat is not None and maat > 0]
    return max(maten) / 2000 if maten else 0.0
