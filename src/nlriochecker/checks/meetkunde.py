"""Meetkundige hulpfuncties die meerdere checks delen."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

if TYPE_CHECKING:
    # Alleen als typehint: zo houdt deze module haar meetkunde los van de checklaag en
    # krijgt `checks/base.py` er geen importer bij tijdens het draaien.
    from nlriochecker.checks.base import CheckContext

# Een coordinatenreeks zoals `coords_of` en de gedeelde tabel hem opleveren: een lijst of
# een tuple van punten. De kernfuncties hieronder lezen alleen, dus de vorm doet er niet toe.
Punten = Sequence[tuple[float, ...]]


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


def endpoints_kern(punten: Punten) -> tuple[Point, Point] | None:
    """Het begin- en eindpunt van een coordinatenreeks, of None."""
    if len(punten) < 2:
        return None
    return Point(punten[0][:2]), Point(punten[-1][:2])


def endpoints(line: LineString | None) -> tuple[Point, Point] | None:
    """Het begin- en eindpunt van een lijngeometrie, of None."""
    return endpoints_kern(coords_of(line))


def distinct_coords_kern(punten: Punten) -> list[tuple[float, ...]]:
    """Een coordinatenreeks zonder direct herhaalde punten."""
    uniek: list[tuple[float, ...]] = []
    for punt in punten:
        if not uniek or punt != uniek[-1]:
            uniek.append(punt)
    return uniek


def distinct_coords(line: LineString | None) -> list[tuple[float, ...]]:
    """De coordinaten van een lijn zonder direct herhaalde punten."""
    return distinct_coords_kern(coords_of(line))


def _lege_coordinatentabel() -> dict[str, tuple[tuple[float, ...], ...]]:
    """Een lege coordinatentabel.

    Een eigen functie in plaats van een `lambda`, zodat `CheckContext.cached` zijn
    TypeVar uit deze returnannotatie oplost en de bellers geen `cast` nodig hebben.
    """
    return {}


def coords_van(
    context: CheckContext, uri: str, geometrie: BaseGeometry | None
) -> tuple[tuple[float, ...], ...]:
    """De coordinaten van dit object, uit de tabel die deze context deelt.

    Dezelfde streng wordt door vijf tot zes checks langs `coords_of` gehaald, en die
    doet er elke keer een `is_empty` en een verse lijst uit de shapely-buffer voor.
    Deze tabel bepaalt ze een keer per context (issue #123). De uitkomst is per
    constructie gelijk aan `tuple(coords_of(geometrie))`.

    Tuples en geen lijsten: de tabel wordt gedeeld, en een lijst laat een beller de
    inhoud voor alle andere veranderen. Bijvullen bij een misser, net als
    `_Topologie.endpoints_of`: "onbekend" mag nooit als "geen geometrie" gelezen
    worden, want de tabel is gevuld met de populatie van deze context en een beller
    kan met een object uit de volledige export langskomen.
    """
    tabel = context.cached("geo:coords", _lege_coordinatentabel)
    punten = tabel.get(uri)
    if punten is None:
        punten = tuple(coords_of(geometrie))
        tabel[uri] = punten
    return punten


def unieke_coords_van(
    context: CheckContext, uri: str, geometrie: BaseGeometry | None
) -> tuple[tuple[float, ...], ...]:
    """De coordinaten zonder direct herhaalde punten, uit de gedeelde tabel.

    Afgeleid uit `coords_van` en niet nog een keer uit `coords_of`, zodat een streng
    zijn coordinaten hoogstens een keer uit shapely haalt. Gelijk aan
    `tuple(distinct_coords(geometrie))`.
    """
    tabel = context.cached("geo:unieke-coords", _lege_coordinatentabel)
    punten = tabel.get(uri)
    if punten is None:
        punten = tuple(distinct_coords_kern(coords_van(context, uri, geometrie)))
        tabel[uri] = punten
    return punten


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


def max_offset_from_chord_kern(punten: Punten) -> float:
    """De grootste afstand van een tussenvertex tot de rechte begin-eindverbinding.

    Over de *unieke* punten: een direct herhaald punt is geen tussenvertex.
    """
    if len(punten) < 3:
        return 0.0
    koorde = LineString([punten[0], punten[-1]])
    return max(koorde.distance(Point(punt[0], punt[1])) for punt in punten[1:-1])


def max_offset_from_chord(line: LineString) -> float:
    """De grootste afstand van een tussenvertex tot de rechte begin-eindverbinding."""
    return max_offset_from_chord_kern(distinct_coords(line))


def vertex_angles_kern(punten: Punten) -> list[tuple[int, float]]:
    """De hoek in graden bij elke tussenvertex van de unieke punten, met haar index.

    De hoek is die tussen de twee aansluitende segmenten: 180 graden is recht
    doorlopend, 0 graden is helemaal terug over zichzelf (een spike).
    """
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


def vertex_angles(line: LineString) -> list[tuple[int, float]]:
    """De hoek in graden bij elke tussenvertex van een lijn, met haar index."""
    return vertex_angles_kern(distinct_coords(line))


def duplicate_vertices_kern(punten: Punten, tolerantie: float) -> list[int]:
    """De indexen van punten die binnen de tolerantie op hun voorganger vallen."""
    dubbel: list[int] = []
    for index in range(1, len(punten)):
        vorige, huidig = punten[index - 1], punten[index]
        if math.hypot(huidig[0] - vorige[0], huidig[1] - vorige[1]) <= tolerantie:
            dubbel.append(index)
    return dubbel


def duplicate_vertices(line: LineString, tolerantie: float) -> list[int]:
    """De indexen van vertices die binnen de tolerantie op hun voorganger vallen."""
    return duplicate_vertices_kern(coords_of(line), tolerantie)


def overlap_length_met_buffer(line: LineString, gebufferd: BaseGeometry) -> float:
    """De lengte waarover een lijn binnen een al gebufferde geometrie valt.

    De buffer hangt alleen van de tegenpartij en de tolerantie af, niet van het paar.
    Wie hem over meerdere paren hergebruikt roept deze variant aan; `intersection`
    muteert haar argument niet, dus dezelfde buffer kan mee naar het volgende paar.
    """
    return float(line.intersection(gebufferd).length)


def overlap_length(line: LineString, other: LineString, tolerantie: float) -> float:
    """De lengte waarover een lijn binnen de buffer van een andere lijn valt."""
    return overlap_length_met_buffer(line, other.buffer(tolerantie))


def half_diameter_m(breedte_mm: float | None, hoogte_mm: float | None) -> float:
    """De halve breedte van een profiel in meters; nul als de maat ontbreekt."""
    maten = [maat for maat in (breedte_mm, hoogte_mm) if maat is not None and maat > 0]
    return max(maten) / 2000 if maten else 0.0
