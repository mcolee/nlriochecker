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
    unconnected: list[Conduit]
    reversed_count: int = 0


def _netwerk(context: CheckContext) -> _Netwerk:
    """Geeft de netwerkgraaf; die wordt per context een keer gebouwd."""
    return context.cached("netwerk", lambda: _bouw_netwerk(context))


def _bouw_netwerk(context: CheckContext) -> _Netwerk:
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

    op_bob = context.config.netwerk.richting == "bob"
    graph = nx.DiGraph()
    aangesloten: list[Conduit] = []
    los: list[Conduit] = []
    omgedraaid = 0
    for conduit in conduits:
        begin = dataset.resolve_network_node(conduit.start_node, wortels)
        eind = dataset.resolve_network_node(conduit.end_node, wortels)
        if begin is None or eind is None:
            los.append(conduit)
            continue
        if op_bob and _stijgt(conduit):
            begin, eind = eind, begin
            omgedraaid += 1
        graph.add_edge(begin, eind, uri=conduit.uri, label=conduit.label)
        aangesloten.append(conduit)

    return _Netwerk(graph=graph, conduits=aangesloten, unconnected=los, reversed_count=omgedraaid)


def _stijgt(conduit: Conduit) -> bool:
    """Geeft aan of de bodem stijgt van begin- naar eindpunt."""
    if conduit.bob_start is None or conduit.bob_end is None:
        return False
    return conduit.bob_start < conduit.bob_end


def _eindpunten(context: CheckContext, rol: str) -> set[str]:
    """De knopen in de graaf die als eindpunt van deze soort afvoer gelden."""
    netwerk = _netwerk(context)
    dataset = context.dataset
    return {
        uri
        for wortel in getattr(context.config.klassen, rol)
        for uri in dataset.of_class(wortel)
        if uri in netwerk.graph
    }


def _bereikbaar_vanaf(netwerk: _Netwerk, endpoints: set[str]) -> set[str]:
    """De knopen die stroomafwaarts een van deze eindpunten bereiken.

    Een enkele doorloop over de omgekeerde graaf vanaf alle eindpunten tegelijk.
    Per eindpunt afzonderlijk zoeken kost O(eindpunten x graaf): De Wolden heeft
    893 gemalen op ruim 20.000 knopen, en dat loopt in de tientallen miljoenen
    stappen. Zo blijft het een enkele O(knopen + kanten)-doorloop.
    """
    if not endpoints:
        return set()

    omgekeerd = netwerk.graph.reverse(copy=False)
    bereikt = {uri for uri in endpoints if uri in omgekeerd}
    stapel = list(bereikt)
    while stapel:
        knoop = stapel.pop()
        for buur in omgekeerd[knoop]:
            if buur not in bereikt:
                bereikt.add(buur)
                stapel.append(buur)
    return bereikt


def _richtingsverlies(context: CheckContext, netwerk: _Netwerk, rol: str | None) -> tuple[int, int]:
    """Splitst de onbereikbare knopen in twee oorzaken.

    Een knoop kan een eindpunt missen omdat zijn netwerkdeel er geen bevat, of omdat
    het eindpunt er wel is maar niet in de gevolgde richting ligt. Dat onderscheid
    bepaalt of je naar ontbrekende objecten of naar verkeerde richtingen moet kijken.
    """
    if rol is None:
        return 0, 0

    endpoints = _eindpunten(context, rol)
    bereikt = _bereikbaar_vanaf(netwerk, endpoints)

    zonder = met = 0
    for deel in nx.weakly_connected_components(netwerk.graph):
        onbereikt = len(deel - bereikt)
        if deel & endpoints:
            met += onbereikt
        else:
            zonder += onbereikt
    return zonder, met


def _bob_tegen_de_richting(netwerk: _Netwerk) -> tuple[int, int]:
    """Telt de strengen waarvan de BOB stijgt in de aangenomen afvoerrichting."""
    tegendraads = meetbaar = 0
    for conduit in netwerk.conduits:
        if conduit.bob_start is None or conduit.bob_end is None:
            continue
        meetbaar += 1
        if conduit.bob_start < conduit.bob_end:
            tegendraads += 1
    return tegendraads, meetbaar


def _netwerk_notities(context: CheckContext, rol: str | None = None) -> list[str]:
    """Beschrijft welke objecten niet in de netwerkanalyse konden meedoen."""
    netwerk = _netwerk(context)
    notities = []
    if netwerk.unconnected:
        labels = ", ".join(sorted(conduit.label for conduit in netwerk.unconnected)[:10])
        notities.append(
            f"{len(netwerk.unconnected)} vrijvervalstrengen hebben geen herleidbare "
            f"put aan beide zijden en vallen buiten de netwerkanalyse: {labels}."
        )
    if netwerk.reversed_count:
        notities.append(
            f"De richting is uit het bodemverloop afgeleid; {netwerk.reversed_count} "
            "strengen zijn daarbij omgedraaid ten opzichte van de administratieve "
            "van-naar-richting."
        )

    zonder, in_deel_met_eindpunt = _richtingsverlies(context, netwerk, rol)
    if in_deel_met_eindpunt:
        notities.append(
            f"{in_deel_met_eindpunt} knopen liggen in een netwerkdeel dat wel een eindpunt "
            "bevat, maar bereiken dat eindpunt niet als de richting gevolgd wordt. Zoveel "
            "knopen wijzen op een systematisch verkeerd gerichte administratie, niet op "
            "evenzoveel losse gebreken."
        )
    if zonder:
        notities.append(
            f"{zonder} knopen liggen in een netwerkdeel zonder enig eindpunt van dit soort."
        )

    tegendraads, meetbaar = _bob_tegen_de_richting(netwerk)
    if meetbaar and tegendraads:
        notities.append(
            f"De analyse neemt aan dat de administratieve begin-naar-eindrichting de "
            f"afvoerrichting is. Bij {tegendraads} van de {meetbaar} strengen met bekende "
            f"BOB's stijgt de bodem juist in die richting "
            f"({100 * tegendraads / meetbaar:.0f}%). NET-003 toetst dat later expliciet; "
            "tot die tijd verdienen de bereikbaarheidsuitkomsten een slag om de arm."
        )

    if rol is not None and not _eindpunten(context, rol):
        klassen = ", ".join(getattr(context.config.klassen, rol)) or "geen geconfigureerd"
        notities.append(
            f"De graaf bevat geen enkel eindpunt van het gevraagde soort ({klassen}); "
            "deze check slaat daardoor op elke streng aan."
        )
    return notities


class _ZonderAfvoerpad(Check):
    """Gedeelde basis voor de bereikbaarheidschecks."""

    stelselrol: str
    eindpuntrol: str
    doel: str

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen van dit stelseltype zonder pad naar een eindpunt."""
        netwerk = _netwerk(context)
        endpoints = _eindpunten(context, self.eindpuntrol)
        bereikt = _bereikbaar_vanaf(netwerk, endpoints)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen
        soorten = getattr(context.config.klassen, self.stelselrol)

        gezocht = {
            uri for wortel in soorten for uri in dataset.of_class(wortel) if uri in dataset.conduits
        }

        geen_eindpunten = not endpoints
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
        return _netwerk_notities(context, self.eindpuntrol)

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
    eindpuntrol = "afvoer_eindpunt"
    doel = "een gemaal of overnamepunt"


@register
class HemelwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-002: hemelwater zonder pad naar lozingspunt of overnamepunt."""

    id = "NET-002"
    title = "Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    stelselrol = "hemelwater"
    eindpuntrol = "lozings_eindpunt"
    doel = "een lozingspunt of overnamepunt"


@register
class KringloopInNetwerk(Check):
    """NET-004: cirkels in het vrijvervalnetwerk."""

    id = "NET-004"
    title = "Cirkels (kringlopen) in het vrijvervalnetwerk"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk deel van de graaf waarin een kringloop zit.

        Per sterk samenhangend deel een melding, niet per enkelvoudige kringloop:
        het aantal enkelvoudige kringlopen groeit exponentieel met de graafgrootte,
        en op een echt stelsel loopt dat vast. Een deel met meer dan een knoop
        bevat per definitie minstens een kringloop; van elk deel wordt een
        voorbeeldkringloop getoond.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset

        for deel in nx.strongly_connected_components(netwerk.graph):
            if len(deel) < 2 and not self._heeft_zelflus(netwerk, deel):
                continue
            subgraaf = netwerk.graph.subgraph(deel)
            kring = self._voorbeeldkring(subgraaf)
            labels = [self._label(dataset, uri) for uri in kring]
            uri, label = self._eerste_streng(subgraaf, kring, dataset)
            yield self.finding(
                context,
                uri,
                label,
                f"Ligt in een deel van het netwerk met {len(deel)} putten waarin een "
                f"kringloop zit; voorbeeld: {' -> '.join(labels)}.",
                putten_in_deel=len(deel),
                voorbeeldkring=labels,
            )

    def _heeft_zelflus(self, netwerk: _Netwerk, deel: set[str]) -> bool:
        """Geeft aan of het enige knooppunt in dit deel naar zichzelf wijst."""
        knoop = next(iter(deel))
        return netwerk.graph.has_edge(knoop, knoop)

    def _voorbeeldkring(self, subgraaf) -> list[str]:
        """Een kringloop uit dit deel, als illustratie in de melding."""
        try:
            kanten = nx.find_cycle(subgraaf)
        except nx.NetworkXNoCycle:
            return sorted(subgraaf)[:1]
        return [begin for begin, _, *_ in kanten]

    def _label(self, dataset, uri: str) -> str:
        """Het label van een knooppunt, of de URI als dat er niet is."""
        node = dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def _eerste_streng(self, subgraaf, kring: list[str], dataset) -> tuple[str, str]:
        """De streng waarop de melding wordt gehangen."""
        if len(kring) > 1 and subgraaf.has_edge(kring[0], kring[1]):
            kant = subgraaf.edges[kring[0], kring[1]]
            return kant["uri"], kant["label"]
        return kring[0], self._label(dataset, kring[0])

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
