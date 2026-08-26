"""Gedeelde navigatie door de dataset: welke put hoort bij welke streng.

Meerdere categorieen checks (TOP, ATTR, HGT, ADM, RVZ) hebben hetzelfde nodig: de
putten aan weerszijden van een streng, en omgekeerd de strengen die op een put
uitkomen. Die afleiding staat hier een keer, zodat de categorieen niet elk hun
eigen variant krijgen.

Ook de gerichte vrijvervalgraaf en de afvoerpadberekening staan hier: de NET-checks
en de GeoPackage-schrijver lezen allebei dezelfde gecachte uitkomst, en
`checks/netwerk.py` importeert de graaf vandaar -- andersom zou een importkring
ontstaan.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import networkx as nx
from gwsw_orox_helpers.dataset import Conduit, Node
from shapely.geometry import LineString

from nlriochecker.checks.base import CheckContext
from nlriochecker.checks.selectie import mechanischeleidingen, vrijvervalrioolleidingen


def verbonden_knopen(context: CheckContext, conduit: Conduit) -> tuple[str | None, str | None]:
    """De URI's van de putten aan het begin en het eind van een streng."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    return (
        dataset.resolve_network_node(conduit.start_node, wortels),
        dataset.resolve_network_node(conduit.end_node, wortels),
    )


@dataclass(frozen=True)
class Aansluitingen:
    """Welke strengen op welke put uitkomen, in beide richtingen opzoekbaar."""

    per_knoop: dict[str, list[Conduit]] = field(default_factory=dict)
    knopen_per_streng: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)

    def strengen(self, knoop_uri: str) -> list[Conduit]:
        """De strengen die op deze put uitkomen."""
        return self.per_knoop.get(knoop_uri, [])

    def knopen(self, conduit_uri: str) -> tuple[str | None, str | None]:
        """De putten aan weerszijden van deze streng."""
        return self.knopen_per_streng.get(conduit_uri, (None, None))


def aansluitingen(context: CheckContext, rol: str = "streng") -> Aansluitingen:
    """Bouwt de put-strengindex voor deze klassenrol; een keer per context."""
    return context.cached(f"aansluitingen:{rol}", lambda: _bouw_aansluitingen(context, rol))


def _bouw_aansluitingen(context: CheckContext, rol: str) -> Aansluitingen:
    """Loopt de strengen van deze rol langs en indexeert ze op hun putten."""
    dataset = context.dataset
    wortels = getattr(context.config.klassen, rol)

    strengen = {
        uri: dataset.conduits[uri]
        for wortel in wortels
        for uri in dataset.of_class(wortel)
        if uri in dataset.conduits
    }

    index = Aansluitingen()
    for uri, conduit in strengen.items():
        knopen = verbonden_knopen(context, conduit)
        index.knopen_per_streng[uri] = knopen
        # Een streng met dezelfde put aan begin en eind (TOP-012) mag daar maar een
        # keer in de lijst staan; anders geldt hij later als zijn eigen buur.
        for knoop in dict.fromkeys(knoop for knoop in knopen if knoop is not None):
            index.per_knoop.setdefault(knoop, []).append(conduit)
    return index


def putten_van(context: CheckContext, conduit: Conduit) -> list[Node]:
    """De putobjecten aan weerszijden van een streng, voor zover bekend."""
    dataset = context.dataset
    gevonden = []
    for uri in verbonden_knopen(context, conduit):
        node = dataset.nodes.get(uri) if uri else None
        if node is not None:
            gevonden.append(node)
    return gevonden


def netwerkdelen(context: CheckContext) -> list[set[str]]:
    """De samenhangende delen van het vrijvervalnetwerk, als knoopverzamelingen.

    Ongericht: voor de vraag of twee putten tot hetzelfde deelstelsel horen doet de
    afvoerrichting niet ter zake. De delen staan op volgorde van hun eerste knoop,
    zodat de nummering tussen runs gelijk blijft.
    """
    return context.cached("netwerkdelen", lambda: _bouw_netwerkdelen(context))


def _bouw_netwerkdelen(context: CheckContext) -> list[set[str]]:
    """Bouwt een ongerichte graaf van het vrijverval en splitst hem in delen."""
    index = aansluitingen(context, "vrijvervalleiding")
    graaf = nx.Graph()
    for uri, (begin, eind) in index.knopen_per_streng.items():
        if begin is None or eind is None:
            graaf.add_node(begin or eind or uri)
            continue
        graaf.add_edge(begin, eind)
    return sorted((set(deel) for deel in nx.connected_components(graaf)), key=min)


def deelstelsel_ids(context: CheckContext) -> dict[str, str]:
    """Geeft per knoop het ID van het vrijverval-deelstelsel waarin hij ligt.

    NET-001, NET-002 en RVZ-006 melden alle drie over hetzelfde verschijnsel: een
    deel van het net dat als geheel iets mist. Met een gedeeld ID is in het rapport
    en op de kaart te zien dat 24 bevindingen twee deelstelsels betreffen en geen 24
    losse gebreken.
    """
    return context.cached("deelstelsel:ids", lambda: _bouw_deelstelsel_ids(context))


def _bouw_deelstelsel_ids(context: CheckContext) -> dict[str, str]:
    """Nummert de deelstelsels naar hun eerste knoop, en houdt de namen uniek."""
    ids: dict[str, str] = {}
    gebruikt: set[str] = set()
    for deel in netwerkdelen(context):
        cluster = _uniek(f"ds-{_knoopnaam(context, min(deel))}", gebruikt)
        gebruikt.add(cluster)
        for uri in deel:
            ids[uri] = cluster
    return ids


def _knoopnaam(context: CheckContext, uri: str) -> str:
    """Het label van een knoop, of anders het laatste stuk van zijn URI."""
    node = context.dataset.nodes.get(uri)
    if node is not None and node.label:
        return node.label
    return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _uniek(naam: str, gebruikt: set[str]) -> str:
    """Maakt de naam uniek; twee deelstelsels mogen niet hetzelfde ID krijgen."""
    if naam not in gebruikt:
        return naam
    volgnummer = 2
    while f"{naam}-{volgnummer}" in gebruikt:
        volgnummer += 1
    return f"{naam}-{volgnummer}"


@dataclass(frozen=True)
class _Netwerk:
    """De gerichte vrijvervalgraaf plus de strengen die erin zitten.

    De richting is de administratieve van-naar-richting: van BeginpuntLeiding naar
    EindpuntLeiding. Dat is de richting die het GWSW-model als afvoerrichting
    bedoelt; NET-003 toetst later of de geometrie daarmee overeenkomt.

    `graph` is het zuivere vrijverval. Het mechanische riool zit in een tweede laag
    die `_bereikbaarheid` los opbouwt, want kringlopen (NET-004), stelseltypen
    (NET-005/006) en de afvoerpadanalyse zijn vrijverval-begrippen en zouden op
    ongerichte persleidingkanten onzin opleveren. Zie BO-54.
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
    conduits = vrijvervalrioolleidingen(context)

    op_bob = context.config.netwerk.richting == "bob"
    graph = nx.DiGraph()
    aangesloten: list[Conduit] = []
    los: list[Conduit] = []
    omgedraaid = 0
    per_kant: dict[tuple[str, str], list[Conduit]] = {}
    for conduit in conduits:
        begin, eind = verbonden_knopen(context, conduit)
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


def _bereikbaarheid(context: CheckContext) -> nx.DiGraph:
    """De bereikbaarheidsgraaf; die wordt per context een keer gebouwd.

    Bewust een eigen gecachte laag naast `_netwerk` en niet een tweede veld erin: wie
    hem opvraagt leest daarmee de rol `mechanischeleidingen`, en dat is precies wat een
    check hoort te declareren. Zat de laag in `_bouw_netwerk`, dan zou elke check die
    de graaf aanraakt het persnet declareren -- ook NET-004, dat er per se buiten moet
    blijven. Zie BO-54.
    """
    return context.cached("bereikbaarheid", lambda: _bouw_bereikbaarheid(context))


def _bouw_bereikbaarheid(context: CheckContext) -> nx.DiGraph:
    """De vrijvervalgraaf plus het mechanische riool als ongerichte kanten (BO-54).

    Ongericht, want een persleiding is pompgestuurd en haar administratieve
    van-naar-richting vertrouwen we niet; voor de vraag of het water ergens uitkomt
    telt alleen de connectiviteit. Beide richtingen als kant, zodat de gerichte
    doorloop van `_bereikbaar_vanaf` er in beide richtingen doorheen kan.

    Waar `resolve_network_node` geen netwerkknoop oplevert valt de kant terug op de
    rauwe koppeling. Het persnet komt namelijk samen op hulpstukken (T-stukken), en
    die klimmen via hasPart niet naar een put; zonder terugval versplintert elke T
    het persnet in losse stukken en blijft het gemaal erachter onbereikbaar. Met de
    terugval is het hulpstuk een doorgeefknoop.
    """
    graaf: nx.DiGraph = _netwerk(context).graph.copy()
    for conduit in mechanischeleidingen(context):
        begin, eind = verbonden_knopen(context, conduit)
        begin = begin or conduit.start_node
        eind = eind or conduit.end_node
        if begin is None or eind is None:
            continue
        graaf.add_edge(begin, eind)
        graaf.add_edge(eind, begin)
    return graaf


def _stijgt(conduit: Conduit) -> bool:
    """Geeft aan of de bodem stijgt van begin- naar eindpunt."""
    verval = conduit.bob_verval
    return verval is not None and verval < 0


def _eindpunten(context: CheckContext, rol: str) -> set[str]:
    """De knopen in de graaf die als eindpunt van deze soort afvoer gelden.

    Getoetst op de bereikbaarheidsgraaf en niet op het zuivere vrijverval: een gemaal
    dat alleen aan het persnet hangt is wel degelijk een eindpunt, maar komt in de
    vrijvervalgraaf niet voor. Die graaf is een deelverzameling van deze, dus voor de
    lezers die met vrijvervalknopen werken verandert er niets.
    """
    graaf = _bereikbaarheid(context)
    dataset = context.dataset
    return {
        uri
        for wortel in getattr(context.config.klassen, rol)
        for uri in dataset.of_class(wortel)
        if uri in graaf
    }


@dataclass(frozen=True)
class Afvoer:
    """Het benedenstroomse uitstroompunt dat een knoop of streng bereikt.

    `eindpunt` is de URI van het dichtstbijzijnde uitstroompunt, `stappen` het aantal
    strengen in het pad ernaartoe (0 voor het uitstroompunt zelf), en `meters` de
    padlengte langs de getekende lijnen van het gekozen pad. `meters` is None zodra een
    streng op dat pad geen bruikbare lijngeometrie heeft: de stap telt dan wel mee, maar
    de lengte niet. `meters` slaat op het gekozen pad, niet op "enig kortste pad": ligt
    er een tweede even kort pad zonder dat gat, dan telt dat hier niet mee.
    """

    eindpunt: str
    stappen: int
    meters: float | None


def _uitstroompunten(context: CheckContext) -> set[str]:
    """De knopen die als uitstroompunt gelden: afvoer- en lozingseindpunten samen."""
    return _eindpunten(context, "afvoer_eindpunt") | _eindpunten(context, "lozings_eindpunt")


def afvoerpaden(context: CheckContext) -> dict[str, Afvoer]:
    """Per knoop het dichtstbijzijnde benedenstroomse uitstroompunt.

    De uitstroompunten zijn de knopen in de rollen `afvoer_eindpunt` en
    `lozings_eindpunt` samen; welke klassen dat zijn staat in de projectconfig. Een
    knoop zonder pad naar enig uitstroompunt staat niet in de uitkomst.

    Bij meer dan een bereikbaar uitstroompunt wint het dichtstbijzijnde in stappen, en
    bij een gelijk aantal stappen de kleinste URI -- determinisme is een harde eis, twee
    runs op dezelfde data moeten dezelfde uitkomst geven.
    """
    return context.cached(
        "afvoerpaden", lambda: _afvoerpaden(_netwerk(context), _uitstroompunten(context))
    )


def _afvoerpaden(netwerk: _Netwerk, uitstroompunten: set[str]) -> dict[str, Afvoer]:
    """Rekent de afvoerpaden uit op de gerichte graaf; zie `afvoerpaden`."""
    graph = netwerk.graph
    bron = {uri for uri in uitstroompunten if uri in graph}
    if not bron:
        return {}

    stappen = _stappen_tot_uitstroom(graph, bron)
    eindpunt: dict[str, str] = {}
    meters: dict[str, float | None] = {}
    # Van dichtbij naar ver: een knoop leunt op zijn benedenstroomse buur een stap
    # dichterbij, en die is dan al bepaald.
    for knoop in sorted(stappen, key=lambda uri: (stappen[uri], uri)):
        if stappen[knoop] == 0:
            eindpunt[knoop] = knoop
            meters[knoop] = 0.0
            continue
        dichterbij = [
            buur for buur in graph.successors(knoop) if stappen.get(buur) == stappen[knoop] - 1
        ]
        eindpunt[knoop] = min(eindpunt[buur] for buur in dichterbij)
        # De volgende stap: de kleinste-URI buur die naar datzelfde uitstroompunt leidt.
        # De keuze bepaalt welke padlengte we optellen; kleinste URI houdt hem
        # deterministisch, ook bij parallelle takken naar hetzelfde eindpunt.
        volgende = min(buur for buur in dichterbij if eindpunt[buur] == eindpunt[knoop])
        kant = _kantlengte(netwerk, knoop, volgende)
        vervolg = meters[volgende]
        meters[knoop] = None if kant is None or vervolg is None else kant + vervolg

    return {
        knoop: Afvoer(eindpunt=eindpunt[knoop], stappen=stappen[knoop], meters=meters[knoop])
        for knoop in stappen
    }


def _stappen_tot_uitstroom(graph: nx.DiGraph, bron: set[str]) -> dict[str, int]:
    """Het minste aantal strengen van elke knoop naar een uitstroompunt.

    Een enkele doorloop over de omgekeerde graaf vanaf alle uitstroompunten tegelijk,
    net als `_bereikbaar_vanaf`, maar nu met de afstand erbij. Knopen zonder pad naar
    enig uitstroompunt komen niet in de uitkomst.
    """
    omgekeerd = graph.reverse(copy=False)
    stappen = {uri: 0 for uri in bron}
    rij: deque[str] = deque(sorted(bron))
    while rij:
        knoop = rij.popleft()
        for buur in omgekeerd[knoop]:
            if buur not in stappen:
                stappen[buur] = stappen[knoop] + 1
                rij.append(buur)
    return stappen


def _kantlengte(netwerk: _Netwerk, begin: str, eind: str) -> float | None:
    """De lengte van de streng op de kant begin->eind, of None zonder lijngeometrie.

    Bij parallelle strengen op dezelfde kant telt de kleinste-URI streng (de eerste in
    `strengen_per_kant`), zodat de lengte niet van de invoervolgorde afhangt.
    """
    strengen = netwerk.strengen_per_kant.get((begin, eind), ())
    return _lijnlengte(strengen[0]) if strengen else None


def _lijnlengte(conduit: Conduit) -> float | None:
    """De lengte van de getekende lijn van een streng, of None zonder bruikbare lijn."""
    lijn = conduit.line
    if isinstance(lijn, LineString) and not lijn.is_empty:
        return lijn.length
    return None


def _netwerkstrengen(context: CheckContext) -> frozenset[str]:
    """De URI's van de aangesloten vrijvervalstrengen in de graaf; een keer per context."""
    return context.cached(
        "netwerkstrengen", lambda: frozenset(c.uri for c in _netwerk(context).conduits)
    )


def afvoerpad_van_streng(context: CheckContext, conduit: Conduit) -> Afvoer | None:
    """Het afvoerpad van een streng: de streng zelf plus het pad vanaf haar eindpunt.

    Alleen voor aangesloten vrijvervalstrengen: een afvoerpad is een vrijverval-begrip.
    Mechanisch riool (persleidingen) en strengen die niet aan beide zijden op een put
    uitkomen, horen er niet in en leveren None -- ook al komen ze op een uitstroompunt
    uit, gepompt riool is geen vrijverval-afvoerpad.

    Verder None als de streng geen herleidbaar eindpunt heeft of vanaf daar geen
    uitstroompunt bereikt. De streng telt als eerste stap; haar eigen lengte telt bij de
    meters, en ontbreekt die (geen bruikbare lijngeometrie) dan valt de hele padlengte weg.
    """
    if conduit.uri not in _netwerkstrengen(context):
        return None
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    eind = dataset.resolve_network_node(conduit.end_node, wortels)
    if eind is None:
        return None
    vervolg = afvoerpaden(context).get(eind)
    if vervolg is None:
        return None
    eigen = _lijnlengte(conduit)
    meters = None if eigen is None or vervolg.meters is None else eigen + vervolg.meters
    return Afvoer(eindpunt=vervolg.eindpunt, stappen=vervolg.stappen + 1, meters=meters)
