"""NET-checks: netwerklogica op de gerichte vrijvervalgraaf."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import networkx as nx

from gwswpijplijn.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from gwswpijplijn.dataset import HAS_PART, Conduit


@dataclass(frozen=True)
class _Netwerk:
    """De gerichte vrijvervalgraaf plus de strengen die erin zitten.

    De richting is de administratieve van-naar-richting: van BeginpuntLeiding naar
    EindpuntLeiding. Dat is de richting die het GWSW-model als afvoerrichting
    bedoelt; NET-003 toetst later of de geometrie daarmee overeenkomt.
    """

    graph: nx.DiGraph
    conduits: list[Conduit]
    endpoints: set[str]
    unconnected: list[Conduit]


def _netwerk(context: CheckContext) -> _Netwerk:
    """Bouwt de gerichte graaf: knoop is put of eindpunt, kant is streng."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen

    conduits = list(
        {
            uri: dataset.conduits[uri]
            for wortel in context.config.klassen.vrijvervalleiding
            for uri in dataset.of_class(wortel)
            if uri in dataset.conduits
        }.values()
    )

    graph = nx.DiGraph()
    aangesloten: list[Conduit] = []
    los: list[Conduit] = []
    for conduit in conduits:
        begin = dataset.resolve_network_node(conduit.start_node, wortels)
        eind = dataset.resolve_network_node(conduit.end_node, wortels)
        if begin is None or eind is None:
            los.append(conduit)
            continue
        graph.add_edge(begin, eind, uri=conduit.uri, label=conduit.label)
        aangesloten.append(conduit)

    endpoints = {
        uri
        for wortel in context.config.klassen.netwerk_eindpunt
        for uri in dataset.of_class(wortel)
        if uri in graph
    }

    return _Netwerk(graph=graph, conduits=aangesloten, endpoints=endpoints, unconnected=los)


def _bereikbaar_vanaf(netwerk: _Netwerk) -> set[str]:
    """De knopen die stroomafwaarts een eindpunt bereiken.

    Een omgekeerde doorloop vanaf alle eindpunten tegelijk, in plaats van per
    streng een pad zoeken; dat laatste wordt kwadratisch op een echt stelsel.
    """
    if not netwerk.endpoints:
        return set()
    omgekeerd = netwerk.graph.reverse(copy=False)
    bereikt: set[str] = set()
    for endpoint in netwerk.endpoints:
        if endpoint in omgekeerd:
            bereikt |= nx.descendants(omgekeerd, endpoint) | {endpoint}
    return bereikt


def _netwerk_notities(context: CheckContext) -> list[str]:
    """Beschrijft welke objecten niet in de netwerkanalyse konden meedoen."""
    netwerk = _netwerk(context)
    notities = []
    if netwerk.unconnected:
        labels = ", ".join(sorted(conduit.label for conduit in netwerk.unconnected)[:10])
        notities.append(
            f"{len(netwerk.unconnected)} vrijvervalstrengen hebben geen herleidbare "
            f"put aan beide zijden en vallen buiten de netwerkanalyse: {labels}."
        )
    if not netwerk.endpoints:
        notities.append(
            "De graaf bevat geen enkel eindpunt (gemaal, lozingspunt of uitlaat); "
            "alle bereikbaarheidschecks slaan daardoor op elke streng aan."
        )
    return notities


class _ZonderAfvoerpad(Check):
    """Gedeelde basis voor de bereikbaarheidschecks."""

    stelselrol: str
    doel: str

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen van dit stelseltype zonder pad naar een eindpunt."""
        netwerk = _netwerk(context)
        bereikt = _bereikbaar_vanaf(netwerk)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen
        soorten = getattr(context.config.klassen, self.stelselrol)

        gezocht = {
            uri for wortel in soorten for uri in dataset.of_class(wortel) if uri in dataset.conduits
        }

        geen_eindpunten = not netwerk.endpoints
        staart = (
            " De graaf bevat geen enkel bereikbaar eindpunt van dit type, dus geldt dit "
            "voor elke streng."
            if geen_eindpunten
            else ""
        )

        for conduit in netwerk.conduits:
            if conduit.uri not in gezocht:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            if begin not in bereikt:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Geen afvoerpad naar {self.doel}.{staart}",
                    stelseltype=self.stelselrol,
                    geen_eindpunten_in_graaf=geen_eindpunten,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel; dat mag niet stilzwijgend verdwijnen."""
        return _netwerk_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class VuilwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-001: vuilwater of gemengd zonder pad naar gemaal of overnamepunt."""

    id = "NET-001"
    title = "Vuilwater- of gemengde streng zonder afvoerpad naar gemaal of overnamepunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    stelselrol = "vuilwater"
    doel = "een gemaal of overnamepunt"


@register
class HemelwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-002: hemelwater zonder pad naar lozingspunt of overnamepunt."""

    id = "NET-002"
    title = "Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    stelselrol = "hemelwater"
    doel = "een lozingspunt of overnamepunt"


@register
class KringloopInNetwerk(Check):
    """NET-004: cirkels in het vrijvervalnetwerk."""

    id = "NET-004"
    title = "Cirkels (kringlopen) in het vrijvervalnetwerk"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke gerichte kringloop een keer, op de eerste streng ervan."""
        netwerk = _netwerk(context)
        dataset = context.dataset

        for kring in nx.simple_cycles(netwerk.graph):
            labels = [dataset.nodes[uri].label if uri in dataset.nodes else uri for uri in kring]
            kant = netwerk.graph.edges[kring[0], kring[1 % len(kring)]] if len(kring) > 1 else None
            uri = kant["uri"] if kant else kring[0]
            label = kant["label"] if kant else labels[0]
            yield self.finding(
                context,
                uri,
                label,
                f"Maakt deel uit van een kringloop over {len(kring)} putten: "
                f"{' -> '.join(labels)}.",
                putten=labels,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel."""
        return _netwerk_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class ItStelselZonderDrempel(Check):
    """NET-007: een deelstelsel met infiltratieleidingen zonder drempel."""

    id = "NET-007"
    title = "IT-stelsel zonder drempel"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt samenhangende delen met infiltratieleidingen maar zonder drempel.

        De GWSW-ontologie kent geen klasse 'IT-stelsel'; een deelstelsel waarin
        infiltratieleidingen liggen geldt hier als zodanig. Welke klassen dat zijn,
        staat in de projectconfig.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        infiltratie = {
            uri
            for wortel in context.config.klassen.infiltratie
            for uri in dataset.of_class(wortel)
            if uri in dataset.conduits
        }
        if not infiltratie:
            return

        drempelknopen = self._knopen_met_drempel(context)

        for deel in nx.weakly_connected_components(netwerk.graph):
            strengen = [
                conduit
                for conduit in netwerk.conduits
                if conduit.uri in infiltratie
                and dataset.resolve_network_node(conduit.start_node, wortels) in deel
            ]
            if not strengen or deel & drempelknopen:
                continue
            for conduit in strengen:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    "Ligt in een deelstelsel met infiltratieleidingen zonder enige drempel.",
                    putten_in_deelstelsel=len(deel),
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel."""
        return _netwerk_notities(context)

    def _knopen_met_drempel(self, context: CheckContext) -> set[str]:
        """De knopen die zelf een drempel bevatten of er onderdeel van zijn."""
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        knopen: set[str] = set()
        for wortel in context.config.klassen.drempel:
            for drempel in dataset.subjects_of_class(wortel):
                for houder in dataset.graph.subjects(HAS_PART, drempel):
                    knoop = dataset.resolve_network_node(str(houder), wortels)
                    if knoop is not None:
                        knopen.add(knoop)
        return knopen

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)
