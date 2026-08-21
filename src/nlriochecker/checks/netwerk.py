"""NET-checks: netwerklogica op de gerichte vrijvervalgraaf."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import networkx as nx

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.selectie import infiltratieleidingen, vrijvervalrioolleidingen
from nlriochecker.checks.verbanden import deelstelsel_ids
from nlriochecker.dataset import Conduit, GwswDataset, part_holders_of
from nlriochecker.taal import getal, vorm


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
    # Per gerichte kant de strengen die erop liggen, gesorteerd op URI. De graaf zelf
    # draagt geen kantattributen: in een DiGraph delen parallelle strengen een kant en
    # zou de laatste de eerste stilzwijgend overschrijven (zie issue #5 en
    # `afbakening._componentstructuur`, dat hetzelfde patroon bewust vermijdt).
    strengen_per_kant: dict[tuple[str, str], tuple[Conduit, ...]] = field(default_factory=dict)


def _netwerk(context: CheckContext) -> _Netwerk:
    """Geeft de netwerkgraaf; die wordt per context een keer gebouwd."""
    return context.cached("netwerk", lambda: _bouw_netwerk(context))


def _bouw_netwerk(context: CheckContext) -> _Netwerk:
    """Bouwt de gerichte graaf: knoop is put of eindpunt, kant is streng."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen

    conduits = vrijvervalrioolleidingen(context)

    op_bob = context.config.netwerk.richting == "bob"
    graph = nx.DiGraph()
    aangesloten: list[Conduit] = []
    los: list[Conduit] = []
    omgedraaid = 0
    per_kant: dict[tuple[str, str], list[Conduit]] = {}
    for conduit in conduits:
        begin = dataset.resolve_network_node(conduit.start_node, wortels)
        eind = dataset.resolve_network_node(conduit.end_node, wortels)
        if begin is None or eind is None:
            los.append(conduit)
            continue
        if op_bob and _stijgt(conduit):
            begin, eind = eind, begin
            omgedraaid += 1
        graph.add_edge(begin, eind)
        per_kant.setdefault((begin, eind), []).append(conduit)
        aangesloten.append(conduit)

    return _Netwerk(
        graph=graph,
        conduits=aangesloten,
        unconnected=los,
        reversed_count=omgedraaid,
        strengen_per_kant={
            kant: tuple(sorted(groep, key=lambda streng: streng.uri))
            for kant, groep in per_kant.items()
        },
    )


def _stijgt(conduit: Conduit) -> bool:
    """Geeft aan of de bodem stijgt van begin- naar eindpunt."""
    verval = conduit.bob_verval
    return verval is not None and verval < 0


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


def _eindknoop_notitie(context: CheckContext, netwerk: _Netwerk, rol: str) -> list[str]:
    """Beschrijft waar het vrijverval op uitkomt en wat daarvan als uitstroom telt.

    Een streng zonder afvoerpad is zelden een los gebrek: het netwerk watert af op
    een beperkt aantal eindknopen, en als die niet als uitstroompunt herkend worden
    slaat de check aan op alles wat erachter ligt. Deze telling maakt zichtbaar of
    het om ontbrekende uitstroomobjecten gaat.
    """
    sinks = [uri for uri in netwerk.graph if netwerk.graph.out_degree(uri) == 0]
    if not sinks:
        return []

    endpoints = _eindpunten(context, rol)
    doodlopend = [uri for uri in sinks if uri not in endpoints]
    if not doodlopend:
        return []

    tellen: dict[str, int] = {}
    for uri in doodlopend:
        soort = _soort(context, uri)
        tellen[soort] = tellen.get(soort, 0) + 1
    top = ", ".join(
        f"{soort} {aantal}"
        for soort, aantal in sorted(tellen.items(), key=lambda paar: -paar[1])[:5]
    )
    uitstroom = len(sinks) - len(doodlopend)
    return [
        f"Het vrijverval watert af op {getal(len(sinks), 'eindknoop', 'eindknopen')}; "
        f"{uitstroom} daarvan {vorm(uitstroom, 'geldt', 'gelden')} als uitstroompunt van dit "
        f"soort; de overige {len(doodlopend)} {vorm(len(doodlopend), 'loopt', 'lopen')} dood "
        f"({top}). Alles wat daarachter ligt telt daardoor als zonder afvoerpad."
    ]


def _soort(context: CheckContext, uri: str) -> str:
    """De korte naam van het beheerobjecttype van een knoop."""
    return context.dataset.beheerobjecttype(uri) or "onbekend"


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

    if rol is not None:
        notities.extend(_eindknoop_notitie(context, netwerk, rol))

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
        onbereikbaar, geen_eindpunten = self._onbereikbaar(context)
        staart = (
            " De graaf bevat geen enkel bereikbaar eindpunt van dit type, dus geldt dit "
            "voor elke streng."
            if geen_eindpunten
            else ""
        )

        for conduit, cluster in onbereikbaar:
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Geen afvoerpad naar {self.doel}.{staart}",
                stelseltype=self.stelselrol,
                geen_eindpunten_in_graaf=geen_eindpunten,
                cluster_id=cluster,
            )

    def _onbereikbaar(self, context: CheckContext) -> tuple[list[tuple[Conduit, str]], bool]:
        """De onbereikbare strengen met hun deelstelsel; een keer per context.

        `run()` en `notes()` hebben allebei deze uitkomst nodig — de een om te
        melden, de ander om te duiden hoeveel deelstelsels het betreft. Zonder deze
        gedeelde bron zouden ze uit elkaar kunnen lopen.
        """
        sleutel = f"onbereikbaar:{self.stelselrol}:{self.eindpuntrol}"
        return context.cached(sleutel, lambda: self._bouw_onbereikbaar(context))

    def _bouw_onbereikbaar(self, context: CheckContext) -> tuple[list[tuple[Conduit, str]], bool]:
        """Loopt de strengen van dit stelseltype langs en houdt de onbereikbare over."""
        netwerk = _netwerk(context)
        endpoints = _eindpunten(context, self.eindpuntrol)
        bereikt = _bereikbaar_vanaf(netwerk, endpoints)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen
        clusters = deelstelsel_ids(context)
        soorten = getattr(context.config.klassen, self.stelselrol)

        gezocht = {
            uri for wortel in soorten for uri in dataset.of_class(wortel) if uri in dataset.conduits
        }

        gevonden: list[tuple[Conduit, str]] = []
        for conduit in netwerk.conduits:
            if conduit.uri not in gezocht:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            if begin not in bereikt:
                # Een streng waarvan het beginpunt niet op te lossen is hoort hier
                # thuis -- onbereikbaar is onbereikbaar -- maar heeft geen cluster.
                gevonden.append((conduit, clusters.get(begin, "") if begin else ""))
        return gevonden, not endpoints

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel; dat mag niet stilzwijgend verdwijnen.

        De clusterduiding staat bewust niet hier maar in het rapport: een check
        draait op de kern plus de contextschil (met een studiegebied) of op de
        volledige dataset (zonder), terwijl het rapport altijd tot de kern
        afgebakend is. Hier geteld zou de duiding het aantal deelstelsels van het
        hele werkbereik van de check melden bij de bevindingen van een enkele buurt.
        """
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
            uri, label = self._eerste_streng(netwerk, kring, dataset)
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
        """Een kringloop uit dit deel, als illustratie in de melding.

        Met een vast beginpunt, want zonder `source` begint `find_cycle` bij de eerste
        knoop in invoegvolgorde. Die volgt uit de `set` die
        `strongly_connected_components` oplevert en dus uit de hashseed: dezelfde data
        zou per run een andere streng aanwijzen, en `vergelijk` zou daar een verschil
        in zien dat er niet is. Elk knooppunt van een sterk samenhangend deel ligt op
        een kringloop, dus de kleinste URI voldoet als startpunt.
        """
        try:
            kanten = nx.find_cycle(subgraaf, source=min(subgraaf))
        except nx.NetworkXNoCycle:
            return sorted(subgraaf)[:1]
        return [begin for begin, _, *_ in kanten]

    def _label(self, dataset: GwswDataset, uri: str) -> str:
        """Het label van een knooppunt, of de URI als dat er niet is."""
        node = dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def _eerste_streng(
        self, netwerk: _Netwerk, kring: list[str], dataset: GwswDataset
    ) -> tuple[str, str]:
        """De streng waarop de melding wordt gehangen: de eerste op de kant kring[0] -> kring[1]."""
        if len(kring) > 1:
            strengen = netwerk.strengen_per_kant.get((kring[0], kring[1]), ())
            if strengen:
                return strengen[0].uri, strengen[0].label
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

        De GWSW-ontologie kent het IT-stelsel wel (Infiltratiestelsel en zijn
        subklasse DrainageInfiltratieTransportStelsel), maar de engine leest de
        stelselboom uit de export nergens; een deelstelsel waarin infiltratieleidingen
        liggen geldt hier daarom als IT-stelsel. Welke klassen dat zijn, staat in de
        projectconfig. Zie BO-34 in docs/beslislog.md.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        infiltratie = {conduit.uri for conduit in infiltratieleidingen(context)}
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
                for houder in part_holders_of(dataset.graph, drempel):
                    knoop = dataset.resolve_network_node(str(houder), wortels)
                    if knoop is not None:
                        knopen.add(knoop)
        return knopen

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


def _stelseltype(context: CheckContext, conduit: Conduit) -> str | None:
    """Het stelseltype van een streng volgens de projectconfig."""
    return context.config.klassen.stelseltype(conduit.types, context.dataset.closure)


@register
class OrientatieTegenAfvoerrichting(Check):
    """NET-003: de administratieve richting loopt tegen het bodemverval in."""

    id = "NET-003"
    title = "Strengorientatie tegen de afvoerrichting in"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst of de bodem daalt van de administratieve begin- naar de eindput.

        Vrijverval stroomt naar beneden. Stijgt de BOB in de van-naar-richting met
        meer dan de drempel voor licht tegenverhang, dan wijst dat op een omgekeerd
        geregistreerde streng. HGT-005 en HGT-006 melden hetzelfde verschijnsel als
        hoogteprobleem; NET-003 leest het als richtingsprobleem, en het register
        kent beide.
        """
        drempel = context.config.drempels.tegenverhang_licht_m

        for conduit in _netwerk(context).conduits:
            if conduit.bob_start is None or conduit.bob_end is None:
                continue
            stijging = conduit.bob_end - conduit.bob_start
            if stijging <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"De bodem stijgt {stijging:.3f} m van begin- naar eindpunt "
                f"(BOB {conduit.bob_start:.3f} naar {conduit.bob_end:.3f} m NAP); "
                "de streng lijkt omgekeerd geregistreerd.",
                bob_begin=conduit.bob_start,
                bob_eind=conduit.bob_end,
                stijging_m=round(stijging, 3),
                drempel_m=drempel,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen door ontbrekende BOB's buiten beeld bleven."""
        netwerk = _netwerk(context)
        zonder = sum(
            1
            for conduit in netwerk.conduits
            if conduit.bob_start is None or conduit.bob_end is None
        )
        notities = _netwerk_notities(context)
        if zonder:
            notities.append(
                f"{zonder} van de {len(netwerk.conduits)} strengen in de graaf missen een "
                "BOB aan begin- of eindpunt; die konden niet op richting getoetst worden."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf met beide BOB's."""
        return sum(
            1
            for conduit in _netwerk(context).conduits
            if conduit.bob_start is not None and conduit.bob_end is not None
        )


@register
class StelseltypeWijktAfVanBuren(Check):
    """NET-005: een streng met een ander stelseltype dan al haar buren."""

    id = "NET-005"
    title = "Stelseltype streng wijkt af van boven- en benedenstroomse buren"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen die als enige van hun soort tussen andere soorten liggen.

        Een enkele hemelwaterstreng midden in een gemengd tracee is vrijwel altijd
        een typeringsfout. De check slaat alleen aan als de streng aan beide zijden
        buren heeft en geen van die buren hetzelfde stelseltype heeft; een streng
        aan de rand van een stelsel is namelijk terecht anders dan haar buur.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        soorten = {conduit.uri: _stelseltype(context, conduit) for conduit in netwerk.conduits}
        per_knoop: dict[str, list[Conduit]] = {}
        for conduit in netwerk.conduits:
            for uri in (
                dataset.resolve_network_node(conduit.start_node, wortels),
                dataset.resolve_network_node(conduit.end_node, wortels),
            ):
                if uri is not None:
                    per_knoop.setdefault(uri, []).append(conduit)

        for conduit in netwerk.conduits:
            eigen = soorten[conduit.uri]
            if eigen is None:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            bovenstrooms = self._buren(per_knoop, begin, conduit.uri, soorten)
            benedenstrooms = self._buren(per_knoop, eind, conduit.uri, soorten)
            # Het register vraagt om afwijking van *boven- en* benedenstroomse
            # buren. Een streng aan het uiteinde van een stelsel heeft er maar aan
            # een kant; die is niet afwijkend maar simpelweg de laatste van haar
            # soort, en hoort hier niet te verschijnen.
            if not bovenstrooms or not benedenstrooms:
                continue
            buursoorten = bovenstrooms | benedenstrooms
            if eigen in buursoorten:
                continue
            aantal = sum(
                1
                for uri in (begin, eind)
                if uri is not None
                for buur in per_knoop.get(uri, [])
                if buur.uri != conduit.uri
            )
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Is van stelseltype {eigen!r} terwijl alle {aantal} buurstrengen "
                f"van type {', '.join(sorted(buursoorten))} zijn.",
                stelseltype=eigen,
                buurtypen=sorted(buursoorten),
            )

    def _buren(
        self,
        per_knoop: dict[str, list[Conduit]],
        knoop: str | None,
        eigen_uri: str,
        soorten: dict[str, str | None],
    ) -> set[str]:
        """De stelseltypen van de andere strengen op deze knoop."""
        if knoop is None:
            return set()
        return {
            soort
            for buur in per_knoop.get(knoop, [])
            if buur.uri != eigen_uri and (soort := soorten[buur.uri]) is not None
        }

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen herkenbaar stelseltype hebben."""
        return _stelseltype_notities(context) + _netwerk_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class KoppelingTussenStelseltypen(Check):
    """NET-006: een knoop waar verschillende stelseltypen samenkomen."""

    id = "NET-006"
    title = "Koppelingen tussen verschillende stelseltypen"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke knoop waarop strengen van meer dan een stelseltype uitkomen.

        Zulke koppelingen bestaan legitiem — een overstort of een aansluiting van
        hemelwater op een gemengd stelsel — maar ze horen bewust te zijn. De
        bevinding staat op de knoop, want daar zit de koppeling.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        per_knoop: dict[str, dict[str, list[str]]] = {}
        for conduit in netwerk.conduits:
            soort = _stelseltype(context, conduit)
            if soort is None:
                continue
            for uri in (
                dataset.resolve_network_node(conduit.start_node, wortels),
                dataset.resolve_network_node(conduit.end_node, wortels),
            ):
                if uri is not None:
                    per_knoop.setdefault(uri, {}).setdefault(soort, []).append(conduit.label)

        for uri, soorten in sorted(per_knoop.items()):
            if len(soorten) < 2:
                continue
            node = dataset.nodes.get(uri)
            omschrijving = "; ".join(
                f"{soort}: {', '.join(sorted(labels))}" for soort, labels in sorted(soorten.items())
            )
            yield self.finding(
                context,
                uri,
                node.label if node is not None else uri,
                f"Hier komen {len(soorten)} stelseltypen samen ({omschrijving}).",
                stelseltypen=sorted(soorten),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen herkenbaar stelseltype hebben."""
        return _stelseltype_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen in de graaf."""
        return _netwerk(context).graph.number_of_nodes()


@register
class VeelLozingspuntenInDeelstelsel(Check):
    """NET-008: opvallend veel lozingspunten in een klein deelstelsel."""

    id = "NET-008"
    title = "Opvallend veel lozingspunten binnen een klein deelstelsel"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt de lozingspunten per samenhangend deel van het netwerk.

        Veel uitlaten op weinig putten wijst zelden op veel lozingen en meestal op
        een deelstelsel dat in stukken uiteengevallen is of op uitlaten die als
        gewone put opgevoerd hadden moeten worden.
        """
        netwerk = _netwerk(context)
        drempels = context.config.drempels
        endpoints = _eindpunten(context, "lozings_eindpunt")
        if not endpoints:
            return

        for deel in nx.weakly_connected_components(netwerk.graph):
            lozingen = sorted(deel & endpoints)
            if len(deel) > drempels.klein_deelstelsel_knopen:
                continue
            if len(lozingen) <= drempels.lozingspunten_per_deelstelsel:
                continue
            labels = [self._label(context, uri) for uri in lozingen]
            for uri in lozingen:
                yield self.finding(
                    context,
                    uri,
                    self._label(context, uri),
                    f"Een van {len(lozingen)} lozingspunten in een deelstelsel van "
                    f"{len(deel)} knopen (maximaal {drempels.lozingspunten_per_deelstelsel} "
                    f"bij ten hoogste {drempels.klein_deelstelsel_knopen} knopen): "
                    f"{', '.join(labels)}.",
                    knopen_in_deelstelsel=len(deel),
                    lozingspunten=len(lozingen),
                )

    def _label(self, context: CheckContext, uri: str) -> str:
        """Het label van een knoop, of de URI als dat er niet is."""
        node = context.dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel."""
        return _netwerk_notities(context, "lozings_eindpunt")

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen in de graaf."""
        return _netwerk(context).graph.number_of_nodes()


def _stelseltype_notities(context: CheckContext) -> list[str]:
    """Meldt hoe de stelseltypen ingedeeld zijn en wat er niet in past."""
    klassen = context.config.klassen.stelseltypen
    if not klassen:
        return [
            "Er zijn geen stelseltypen geconfigureerd (`klassen.stelseltypen`); deze check "
            "kon daardoor niets vergelijken."
        ]
    netwerk = _netwerk(context)
    zonder = [
        conduit.label for conduit in netwerk.conduits if _stelseltype(context, conduit) is None
    ]
    notities = [f"Stelseltypen uit de config: {', '.join(sorted(klassen))}."]
    if zonder:
        notities.append(
            f"{len(zonder)} van de {len(netwerk.conduits)} strengen in de graaf vallen onder "
            "geen enkel geconfigureerd stelseltype en doen niet mee."
        )
    return notities
