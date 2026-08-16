"""TOP-checks: topologie en geometrie van putten en strengen."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from shapely.geometry import Point
from shapely.strtree import STRtree

from gwswpijplijn.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from gwswpijplijn.dataset import Conduit, Node


@dataclass(frozen=True)
class _Topologie:
    """Hulpstructuur met de putten, hun geometrie en een index erop."""

    nodes: list[Node]
    tree: STRtree | None
    conduits: list[Conduit]

    def nearest_node(self, punt: Point, tolerantie: float) -> Node | None:
        """De put binnen de tolerantie die het dichtst bij dit punt ligt."""
        if self.tree is None:
            return None
        kandidaten = self.tree.query(punt.buffer(tolerantie))
        dichtstbij: Node | None = None
        kleinste = float("inf")
        for index in kandidaten:
            node = self.nodes[int(index)]
            afstand = node.point.distance(punt)
            if afstand <= tolerantie and afstand < kleinste:
                kleinste = afstand
                dichtstbij = node
        return dichtstbij


def _topologie(context: CheckContext) -> _Topologie:
    """Bouwt de puttenindex en de lijst met strengen die geometrie hebben."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen

    nodes = [
        dataset.nodes[uri]
        for wortel in wortels
        for uri in dataset.of_class(wortel)
        if uri in dataset.nodes and dataset.nodes[uri].point is not None
    ]
    uniek = list({node.uri: node for node in nodes}.values())
    tree = STRtree([node.point for node in uniek]) if uniek else None

    conduits = [
        dataset.conduits[uri]
        for wortel in context.config.klassen.vrijvervalleiding
        for uri in dataset.of_class(wortel)
        if uri in dataset.conduits
    ]
    uniek_conduits = list({conduit.uri: conduit for conduit in conduits}.values())

    return _Topologie(nodes=uniek, tree=tree, conduits=uniek_conduits)


def _endpoints(conduit: Conduit) -> tuple[Point, Point] | None:
    """Het begin- en eindpunt van de strenggeometrie."""
    if conduit.line is None or conduit.line.is_empty:
        return None
    coordinaten = list(conduit.line.coords)
    if len(coordinaten) < 2:
        return None
    return Point(coordinaten[0]), Point(coordinaten[-1])


@register
class LosliggendePut(Check):
    """TOP-001: putten waarop geen enkele streng aansluit."""

    id = "TOP-001"
    title = "Losliggende putten (geen enkele streng aangesloten)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putten zonder strengeindpunt binnen de snapping-tolerantie.

        Dit is de geometrische variant; de administratieve koppeling dekt de
        nulmeting al via Hyd.
        """
        topologie = _topologie(context)
        tolerantie = context.config.drempels.snapping_tolerantie_m

        aangesloten: set[str] = set()
        for conduit in topologie.conduits:
            uiteinden = _endpoints(conduit)
            if uiteinden is None:
                continue
            for punt in uiteinden:
                node = topologie.nearest_node(punt, tolerantie)
                if node is not None:
                    aangesloten.add(node.uri)

        for node in topologie.nodes:
            if node.uri not in aangesloten:
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Geen strengeindpunt binnen {tolerantie:g} m van deze put.",
                    tolerantie_m=tolerantie,
                )

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met geometrie."""
        return len(_topologie(context).nodes)


class _StrengPutAansluiting(Check):
    """Gedeelde basis voor de checks op het aantal aangesloten putten per streng."""

    verwacht: int

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt per streng hoeveel uiteinden geometrisch op een put vallen."""
        topologie = _topologie(context)
        tolerantie = context.config.drempels.snapping_tolerantie_m

        for conduit in topologie.conduits:
            uiteinden = _endpoints(conduit)
            if uiteinden is None:
                continue
            treffers = [topologie.nearest_node(punt, tolerantie) for punt in uiteinden]
            if sum(1 for node in treffers if node is not None) != self.verwacht:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                self.melding(tolerantie),
                tolerantie_m=tolerantie,
            )

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        raise NotImplementedError

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen met geometrie."""
        return sum(1 for conduit in _topologie(context).conduits if _endpoints(conduit))


@register
class LosliggendeStreng(_StrengPutAansluiting):
    """TOP-002: strengen zonder put aan beide zijden."""

    id = "TOP-002"
    title = "Losliggende strengen (aan geen van beide zijden een put)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    verwacht = 0

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        return f"Geen van beide strengeinden ligt binnen {tolerantie:g} m van een put."


@register
class StrengMetEenPut(_StrengPutAansluiting):
    """TOP-003: strengen met slechts aan een zijde een put."""

    id = "TOP-003"
    title = "Streng met slechts aan een zijde een put"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    verwacht = 1

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        return f"Slechts een van beide strengeinden ligt binnen {tolerantie:g} m van een put."


@register
class NietGesneptStrengeinde(Check):
    """TOP-004: strengeindpunt ligt te ver van de put waaraan het gekoppeld is."""

    id = "TOP-004"
    title = "Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de administratieve koppeling met de geometrische afstand."""
        dataset = context.dataset
        tolerantie = context.config.drempels.snapping_tolerantie_m
        wortels = context.config.klassen.netwerkknopen

        for conduit in _topologie(context).conduits:
            uiteinden = _endpoints(conduit)
            if uiteinden is None:
                continue
            koppelingen = (
                ("beginpunt", conduit.start_node, uiteinden[0]),
                ("eindpunt", conduit.end_node, uiteinden[1]),
            )
            for zijde, gekoppeld, punt in koppelingen:
                node_uri = dataset.resolve_network_node(gekoppeld, wortels)
                node = dataset.nodes.get(node_uri) if node_uri else None
                if node is None or node.point is None:
                    continue
                afstand = node.point.distance(punt)
                if afstand > tolerantie:
                    yield self.finding(
                        context,
                        conduit.uri,
                        conduit.label,
                        f"Het {zijde} ligt {afstand:.3f} m van put {node.label!r}, "
                        f"meer dan de tolerantie van {tolerantie:g} m.",
                        zijde=zijde,
                        afstand_m=round(afstand, 3),
                        put=node.label,
                        tolerantie_m=tolerantie,
                    )

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen met geometrie."""
        return sum(1 for conduit in _topologie(context).conduits if _endpoints(conduit))


@register
class DubbelePut(Check):
    """TOP-005: twee putten die binnen de tolerantie samenvallen."""

    id = "TOP-005"
    title = "Dubbele putten: twee knopen binnen tolerantie"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putparen die dichter bij elkaar liggen dan de tolerantie."""
        topologie = _topologie(context)
        tolerantie = context.config.drempels.dubbele_put_tolerantie_m
        if topologie.tree is None:
            return

        gemeld: set[tuple[str, str]] = set()
        for node in topologie.nodes:
            for index in topologie.tree.query(node.point.buffer(tolerantie)):
                ander = topologie.nodes[int(index)]
                if ander.uri == node.uri:
                    continue
                afstand = node.point.distance(ander.point)
                if afstand > tolerantie:
                    continue
                sleutel = tuple(sorted((node.uri, ander.uri)))
                if sleutel in gemeld:
                    continue
                gemeld.add(sleutel)
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Ligt {afstand:.3f} m van put {ander.label!r}, binnen de "
                    f"tolerantie van {tolerantie:g} m.",
                    andere_put=ander.label,
                    andere_uri=ander.uri,
                    afstand_m=round(afstand, 3),
                    tolerantie_m=tolerantie,
                )

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met geometrie."""
        return len(_topologie(context).nodes)


@register
class StrengMetZelfdePut(Check):
    """TOP-012: streng met dezelfde put aan begin- en eindpunt."""

    id = "TOP-012"
    title = "Streng met dezelfde put aan begin- en eindpunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen waarvan beide uiteinden naar dezelfde put verwijzen."""
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        for conduit in _topologie(context).conduits:
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            if begin is None or begin != eind:
                continue
            node = dataset.nodes.get(begin)
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Begin- en eindpunt verwijzen allebei naar put {node.label if node else begin!r}.",
                put=node.label if node else begin,
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).conduits)
