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
from collections.abc import Iterable
from dataclasses import dataclass, field

import networkx as nx
from gwsw_orox_helpers.dataset import Conduit, Node
from shapely.geometry import LineString

from nlriochecker.checks.base import CheckContext
from nlriochecker.checks.hulpstukken import telbare_hulpstukken
from nlriochecker.checks.selectie import mechanischeleidingen, vrijvervalrioolleidingen


def verbonden_knopen(context: CheckContext, conduit: Conduit) -> tuple[str | None, str | None]:
    """De URI's van de putten aan het begin en het eind van een streng."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    return (
        dataset.resolve_network_node(conduit.start_node, wortels),
        dataset.resolve_network_node(conduit.end_node, wortels),
    )


def _doorgeefknopen(context: CheckContext, conduit: Conduit) -> tuple[str | None, str | None]:
    """De knopen van een streng, met een telbaar hulpstuk als doorgeefknoop (BO-83).

    Als `verbonden_knopen`, maar waar `resolve_network_node` niets oplevert valt deze
    terug op de rauwe `Conduit.start_node`/`end_node` zolang die op een hulpstuk met een
    telbare GWSW-functie wijst (`hulpstukken.telbare_hulpstukken`: mof, T-stuk, Y-stuk,
    kruisstuk). Een `Hulpstuk` is geen `Put` en klimt via `hasPart` niet naar een put,
    dus zonder terugval laat de vrijvervalgraaf elke streng vallen die op een T-stuk
    eindigt -- terwijl zij daar in werkelijkheid aan het net vastzit. Een `Afsluitstuk`
    of `Ontstoppingsstuk` draagt een functie zonder aantal en blijft een breuk; dezelfde
    grens die TOP-002/TOP-003 sinds BO-72 hanteren.

    Alleen de vrijvervalgraaf leest deze terugval. `verbonden_knopen` zelf blijft de
    putten geven -- TOP, HGT en ATTR lezen putkenmerken, en een hulpstuk hoort daar niet
    bij -- en `_bouw_bereikbaarheid` houdt zijn eigen, ruimere terugval voor het persnet.
    """
    begin, eind = verbonden_knopen(context, conduit)
    telbaar = telbare_hulpstukken(context)
    if begin is None and conduit.start_node in telbaar:
        begin = conduit.start_node
    if eind is None and conduit.end_node in telbaar:
        eind = conduit.end_node
    return begin, eind


def putknopen(context: CheckContext, knopen: Iterable[str]) -> set[str]:
    """Dezelfde knopen zonder de doorgeefhulpstukken: wat er te beoordelen valt (BO-83).

    De graaf draagt een telbaar hulpstuk als knoop, want daar geeft het door. Geen enkele
    check beoordeelt het: een hulpstuk is geen put, draagt geen dekselniveau en krijgt
    nooit een bevinding. Waar knopen geteld worden -- een drempel als
    `klein_deelstelsel_knopen`, de zin "een deelstelsel van N knopen", het detailveld
    `knopen_in_deelstelsel`, `examined()` en `n_knopen` in de GeoPackage -- betekent
    "knoop" daarom een beheerobject uit de rol `netwerkknopen` (put, gemaal,
    bergbezinkvoorziening, uitlaat), en hoort het doorgeefhulpstuk er niet bij.

    De verzamelingen zelf blijven ongemoeid: `netwerkdelen`, `_Netwerk.graph` en
    `deelstelsel_ids` dragen het hulpstuk gewoon, anders zou het net er weer op stukvallen.
    Alleen de tellingen lopen langs deze functie, zodat de aftrek op een plek staat en niet
    als losse `- telbare_hulpstukken(...)` door de checks verspreid raakt.
    """
    return set(knopen) - telbare_hulpstukken(context)


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

    Een knoop is een put of een hulpstuk met een telbare GWSW-functie: zo'n hulpstuk
    geeft door (`_doorgeefknopen`, BO-83), en twee putten aan weerszijden van een T-stuk
    horen dus tot hetzelfde deelstelsel.
    """
    return context.cached("netwerkdelen", lambda: _bouw_netwerkdelen(context))


def _bouw_netwerkdelen(context: CheckContext) -> list[set[str]]:
    """Bouwt een ongerichte graaf van het vrijverval en splitst hem in delen."""
    graaf = nx.Graph()
    for conduit in vrijvervalrioolleidingen(context):
        begin, eind = _doorgeefknopen(context, conduit)
        if begin is None or eind is None:
            graaf.add_node(begin or eind or conduit.uri)
            continue
        graaf.add_edge(begin, eind)
    return sorted((set(deel) for deel in nx.connected_components(graaf)), key=min)


def strengen_per_knoop(context: CheckContext) -> dict[str, list[Conduit]]:
    """Per graafknoop de vrijvervalstrengen die erop uitkomen; een keer per context.

    De tegenhanger van `aansluitingen` voor wie met de graaf werkt. Die index herleidt elk
    strengeinde naar een put en is daarmee precies goed voor TOP, HGT en ATTR -- die lezen
    putkenmerken -- maar zij kent een streng die met beide einden aan een hulpstuk hangt
    helemaal niet, en van een streng met een hulpstuk aan een kant alleen de andere kant.
    Wie de strengen van een netwerkdeel opvraagt (RVZ-006, en de deelstelselvlakken in de
    GeoPackage) moet dezelfde afleiding lezen als de graaf zelf (`_doorgeefknopen`), anders
    ligt zo'n streng wel als kant in het deel maar telt zij niet mee. Op De Wolden en
    Hoogeveen gaat het om enkele tientallen strengen tussen twee T-stukken. Zie BO-83.

    De strengen staan per knoop in selectievolgorde, en een streng met beide einden op
    dezelfde knoop staat er een keer -- net als in `_bouw_aansluitingen`.
    """
    return context.cached(
        "vrijverval:strengen_per_knoop", lambda: _bouw_strengen_per_knoop(context)
    )


def _bouw_strengen_per_knoop(context: CheckContext) -> dict[str, list[Conduit]]:
    """Indexeert de vrijvervalstrengen op de knopen waarmee de graaf ze verbindt."""
    index: dict[str, list[Conduit]] = {}
    for conduit in vrijvervalrioolleidingen(context):
        knopen = _doorgeefknopen(context, conduit)
        for knoop in dict.fromkeys(uri for uri in knopen if uri is not None):
            index.setdefault(knoop, []).append(conduit)
    return index


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
    bedoelt; NET-009 toetst of de geometrie en de BOB daarmee overeenkomen.

    `graph` is het zuivere vrijverval. Het mechanische riool zit in een tweede laag
    die `_bereikbaarheid` los opbouwt, want kringlopen (NET-004), stelseltypen
    (NET-005/006) en de afvoerpadanalyse zijn vrijverval-begrippen en zouden op
    ongerichte persleidingkanten onzin opleveren. Zie BO-54.

    Een knoop is een put of een hulpstuk met een telbare GWSW-functie (`_doorgeefknopen`,
    BO-83). Het onderscheid met de tweede laag is bewust: het vrijverval geeft alleen
    door op zo'n telbaar hulpstuk, het persnet op elk rauw eindpunt.
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
        begin, eind = _doorgeefknopen(context, conduit)
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

    Deze terugval is ruimer dan die van het vrijverval (`_doorgeefknopen`, BO-83): hier
    telt élk rauw eindpunt, daar alleen een hulpstuk met een telbare GWSW-functie. Het
    verschil is niet gemeten maar wel bedoeld -- het persnet wordt inhoudelijk niet
    getoetst en draagt hier alleen connectiviteit, terwijl een vrijvervalknoop de plek is
    waar de NET-checks een oordeel op hangen.
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


def _eindpunten(context: CheckContext, rol: str) -> frozenset[str]:
    """De knopen in de graaf die als eindpunt van deze soort afvoer gelden.

    Getoetst op de bereikbaarheidsgraaf en niet op het zuivere vrijverval: een gemaal
    dat alleen aan het persnet hangt is wel degelijk een eindpunt, maar komt in de
    vrijvervalgraaf niet voor. Die graaf is een deelverzameling van deze, dus voor de
    lezers die met vrijvervalknopen werken verandert er niets.

    Een keer per context en per rol, net als de acht andere afgeleide structuren in dit
    bestand (issue #124). Elke aanroep kostte anders een volledige `of_class`-scan per
    wortelklasse over alle objecten van de export, en er zijn vier aanroepplekken --
    `_eindpuntset` en `_ZonderAfvoerpad._bouw_onbereikbaar` in `checks/netwerk.py`,
    NET-008, en `_uitstroompunten` hieronder, die hem tweemaal aanroept.

    **Een `frozenset`, want de uitkomst is gedeeld.** Alle bellers lezen hem alleen -- ze
    verenigen hem in een eigen verzameling (`gevonden |= ...`), snijden ermee
    (`deel & endpoints`) of maken er een nieuwe van (`a | b`) -- en het type houdt dat zo:
    een beller die de gedeelde verzameling zou wijzigen, wijzigt hem voor alle andere, en
    dat hoort niet van een docstring af te hangen.
    """
    return context.cached(f"eindpunten:{rol}", lambda: _bouw_eindpunten(context, rol))


def _bouw_eindpunten(context: CheckContext, rol: str) -> frozenset[str]:
    """Scant de wortelklassen van deze rol en houdt de knopen over die in de graaf staan."""
    graaf = _bereikbaarheid(context)
    dataset = context.dataset
    return frozenset(
        uri
        for wortel in getattr(context.config.klassen, rol)
        for uri in dataset.of_class(wortel)
        if uri in graaf
    )


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
    """De knopen die als uitstroompunt gelden: afvoer- en lozingseindpunten samen.

    Een gewone `set`: de vereniging van twee `frozenset`s is er zelf een, en die zou het
    deelverbod van `_eindpunten` doorgeven aan een beller die hem niet deelt.
    """
    return set(_eindpunten(context, "afvoer_eindpunt") | _eindpunten(context, "lozings_eindpunt"))


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

    De eindknoop komt uit dezelfde afleiding als de graaf (`_doorgeefknopen`, BO-83) en
    niet uit de putherleiding: een streng die op een telbaar hulpstuk eindigt zit in de
    graaf, en `afvoerpaden` draagt die hulpstuk-URI's als sleutel. Met de putherleiding
    zou zij hier stil op None uitkomen -- geen uitstroompunt en geen padlengte in de
    GeoPackage -- terwijl NET-001 haar wel bereikbaar noemt.
    """
    if conduit.uri not in _netwerkstrengen(context):
        return None
    _, eind = _doorgeefknopen(context, conduit)
    if eind is None:
        return None
    vervolg = afvoerpaden(context).get(eind)
    if vervolg is None:
        return None
    eigen = _lijnlengte(conduit)
    meters = None if eigen is None or vervolg.meters is None else eigen + vervolg.meters
    return Afvoer(eindpunt=vervolg.eindpunt, stappen=vervolg.stappen + 1, meters=meters)
