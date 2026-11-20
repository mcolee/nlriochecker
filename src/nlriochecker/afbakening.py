"""De afbakening van een studiegebied: kern, ring en (historisch) de analyseset.

Sinds BO-100 draait `toets` de checks één keer over de volledige export en bakent hij
die ene run per gebied af tot de kern. Daarvoor is per gebied alleen `Afbakening`
nodig: de kern en de ring die de GeoPackage grijs meetekent (BO-29). De STRtree van
`GedeeldeIndex` levert de kandidaten, het oordeel blijft `area.bevat`.

De analyseset hieronder (kern plus contextschil, met een uitgedunde dataset) was tot
BO-100 de rekenbasis van een gebiedsrun. De schil was precies zo groot dat de
netwerkchecks hun antwoord hielden: de samenhangende component waar de kern in ligt --
vrijverval EN persnet (BO-54, BO-56) -- plus een buffer. De toetsroute gebruikt haar
niet meer; `scripts/maak_voorbeeld.py` en de analysescripts die de oude route nameten
wel, en daarvoor blijft zij staan.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property

import networkx as nx
from gwsw_orox_helpers.dataset import GwswDataset
from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from nlriochecker import leeslaag
from nlriochecker.checkconfig import CheckConfig
from nlriochecker.studiegebied import StudyArea


@dataclass(frozen=True)
class Afbakening:
    """Wat de rapportage van één studiegebied nodig heeft (BO-100).

    Geen schil en geen uitgedunde dataset: de checks zagen de volledige export. Over
    blijven de kern, waartoe de run afgebakend wordt, en de ring om het gebied die de
    GeoPackage grijs meetekent, zodat de kaart niet bij de gebiedsgrens ophoudt alsof
    daar niets ligt (BO-29).
    """

    kern: frozenset[str]
    # De objecten binnen `[studiegebied] context_buffer_m` om het gebied, zonder de kern.
    buffer: frozenset[str]
    # Het aantal knopen en strengen in de export: waarover de checks gedraaid hebben.
    volledig_aantal: int


def bouw_afbakening(
    dataset: GwswDataset, area: StudyArea, config: CheckConfig, gedeeld: GedeeldeIndex
) -> Afbakening:
    """Kern en ring van een gebied, uit de gedeelde ruimtelijke index."""
    kern = objecten_in_gebied(dataset, area, gedeeld=gedeeld)
    return Afbakening(
        kern=kern,
        buffer=frozenset(_binnen_buffer(dataset, area, config, gedeeld) - kern),
        volledig_aantal=len(dataset.nodes) + len(dataset.conduits),
    )


@dataclass(frozen=True)
class Analyseset:
    """De objecten die met een studiegebied door de checks gingen (vóór BO-100)."""

    kern: frozenset[str]
    schil: frozenset[str]
    dataset: GwswDataset
    volledig_aantal: int
    # Vrijvervalstrengen die de componentberekening moest overslaan omdat een van
    # beide uiteinden niet naar een netwerkknoop herleidt (zie `_component`). Ze
    # kunnen daardoor nooit via de component in de schil belanden, ook niet als hun
    # wel herleidbare kant in een geraakte component ligt. Hetzelfde als wat
    # `checks/verbanden.py` als `unconnected` apart houdt; hier alleen het aantal,
    # zodat het rapport kan zeggen wat er niet meegewogen is in plaats van te
    # zwijgen.
    strengen_zonder_netwerkverband: int = 0
    # Het deel van de schil dat om het gebied heen ligt: de objecten binnen de buffer,
    # zonder de kern. De schil is groter -- daar hoort de hele samenhangende
    # vrijvervalcomponent bij, en die kan in een stad het halve net zijn -- maar alleen
    # deze ring is wat een lezer om zijn gebied heen ziet liggen. De GeoPackage tekent
    # hem grijs mee, zodat de kaart niet bij de gebiedsgrens ophoudt alsof daar niets
    # ligt; de rest van de component grijs meesturen zou elk buurtbestand met het net
    # van de hele stad opzadelen. Zie BO-29.
    buffer: frozenset[str] = frozenset()

    @property
    def alles(self) -> frozenset[str]:
        """Kern en schil samen: waarover de checks redeneren."""
        return self.kern | self.schil


@dataclass(frozen=True)
class GedeeldeIndex:
    """Wat bij meerdere studiegebieden over de gebieden heen hergebruikt mag worden.

    Twee structuren die niet van het gebied afhangen: een ruimtelijke index over alle
    objectgeometrieen, en de samenhangende vrijvervalcomponenten van het volledige
    net. Met tachtig buurten zouden ze anders tachtig keer opnieuw berekend worden,
    terwijl de uitkomst elke keer dezelfde is.

    De boom levert alleen *kandidaten* op omhullende; het oordeel blijft
    `area.bevat`. Daarmee kan de uitkomst per constructie niet verschillen van die
    zonder index -- ook niet bij de ongeldige geometrieen die in deze datasets
    voorkomen (zie TOP-016), waar een voorbereid predicaat anders zou kunnen
    beslissen dan `intersects` zelf.
    """

    boom: STRtree
    uris: tuple[str, ...]
    dataset: GwswDataset = field(compare=False, repr=False)
    config: CheckConfig = field(compare=False, repr=False)

    def kandidaten(self, geometrie: BaseGeometry) -> Iterator[str]:
        """De URI's waarvan de omhullende die van `geometrie` raakt."""
        for index in self.boom.query(geometrie):
            yield self.uris[index]

    @cached_property
    def _structuur(self) -> tuple[list[set[str]], dict[str, int], tuple[tuple[str, str], ...], int]:
        """De componentstructuur, lui: alleen `bouw_analyseset` vraagt hem (BO-100)."""
        return _componentstructuur(self.dataset, self.config)

    def component(self, kern: frozenset[str]) -> tuple[set[str], int]:
        """De samenhangende vrijvervalcomponenten die deze kern raken.

        Alleen deze selectie hangt van het gebied af; de componentstructuur zelf niet.
        """
        return _selecteer_component(*self._structuur, kern)


def bouw_gedeelde_index(dataset: GwswDataset, config: CheckConfig) -> GedeeldeIndex:
    """Bouwt de ruimtelijke index; de componentstructuur volgt pas bij de eerste vraag."""
    uris: list[str] = []
    geometrieen: list[BaseGeometry] = []
    for uri, node in dataset.nodes.items():
        if node.point is not None and not node.point.is_empty:
            uris.append(uri)
            geometrieen.append(node.point)
    for uri, conduit in dataset.conduits.items():
        if conduit.line is not None and not conduit.line.is_empty:
            uris.append(uri)
            geometrieen.append(conduit.line)

    return GedeeldeIndex(
        boom=STRtree(geometrieen), uris=tuple(uris), dataset=dataset, config=config
    )


def objecten_in_gebied(
    dataset: GwswDataset, area: StudyArea, *, gedeeld: GedeeldeIndex | None = None
) -> frozenset[str]:
    """De URI's van de objecten waarvan de geometrie het studiegebied raakt."""
    if gedeeld is None:
        binnen = {uri for uri, node in dataset.nodes.items() if area.bevat(node.point)}
        binnen |= {uri for uri, conduit in dataset.conduits.items() if area.bevat(conduit.line)}
        return frozenset(binnen)
    return frozenset(
        uri for uri in gedeeld.kandidaten(area.geometry) if area.bevat(_geometrie(dataset, uri))
    )


def _geometrie(dataset: GwswDataset, uri: str) -> BaseGeometry | None:
    """De geometrie van een knoop of streng, of None als het object er niet is.

    De index staat op de volledige export; wordt hij op een uitgedunde dataset
    bevraagd, dan hoort een object dat daar niet in zit ook niet mee te tellen.
    """
    node = dataset.nodes.get(uri)
    if node is not None:
        return node.point
    conduit = dataset.conduits.get(uri)
    return conduit.line if conduit is not None else None


def bouw_analyseset(
    dataset: GwswDataset,
    area: StudyArea,
    config: CheckConfig,
    *,
    gedeeld: GedeeldeIndex | None = None,
) -> Analyseset:
    """Bouwt kern en contextschil en levert de uitgedunde dataset.

    `gedeeld` is de index van een run over meerdere gebieden; zonder die parameter
    bouwt deze functie hem zelf, en gedraagt een losse run zich precies als voorheen.
    """
    gedeeld = gedeeld if gedeeld is not None else bouw_gedeelde_index(dataset, config)
    kern = objecten_in_gebied(dataset, area, gedeeld=gedeeld)
    component, zonder_netwerkverband = gedeeld.component(kern)
    buffer = _binnen_buffer(dataset, area, config, gedeeld)
    schil = component | buffer
    schil |= _sluit_tussenschakels(dataset, config, kern | schil)
    schil -= kern
    volledig = len(dataset.nodes) + len(dataset.conduits)
    return Analyseset(
        kern=kern,
        schil=frozenset(schil),
        dataset=dataset.subset(kern | schil),
        volledig_aantal=volledig,
        strengen_zonder_netwerkverband=zonder_netwerkverband,
        buffer=frozenset(buffer - kern),
    )


def _sluit_tussenschakels(
    dataset: GwswDataset, config: CheckConfig, behouden: frozenset[str] | set[str]
) -> set[str]:
    """De compartimenten en hulpstukken die de behouden strengen nodig hebben.

    `GwswDataset.resolve_network_node` loopt via `parents` omhoog tot een put en
    heeft daarbij elke tussenliggende schakel in `dataset.nodes` nodig -- in dit
    domein normaal: een streng koppelt niet altijd rechtstreeks aan een put, maar
    soms aan een compartiment of hulpstuk zonder eigen geometrie. Kern en schil
    bevatten tot hier alleen objecten met geometrie (kern, buffer) en de knopen
    waar de componentberekening op uitkomt (de put zelf); zo'n tussenschakel valt
    daar tussenuit. Zonder deze sluiting resolveert een streng die er doorheen
    loopt op de uitgedunde dataset naar niets en telt hij ten onrechte als niet
    aangesloten, ook al klopt de aansluiting op de volledige export.
    """
    wortels = config.klassen.netwerkknopen
    aanvulling: set[str] = set()
    for uri in behouden:
        conduit = dataset.conduits.get(uri)
        if conduit is None:
            continue
        aanvulling |= _ouderketen(dataset, conduit.start_node, wortels)
        aanvulling |= _ouderketen(dataset, conduit.end_node, wortels)
    return aanvulling


def _ouderketen(dataset: GwswDataset, uri: str | None, wortels: list[str]) -> set[str]:
    """De knopen die de klim omhoog naar de netwerkknoop tegenkwam, die erbij.

    Loopt langs `GwswDataset.klim_naar_knoop`, dezelfde wandeling als
    `resolve_network_node` -- twee klimfuncties naast elkaar zouden op een export met
    meervoudige houders uiteenlopen, en dan houdt de analyseset precies de schakel
    niet vast die de resolutie nodig heeft. Schakels die niet in `dataset.nodes`
    staan blijven eruit: die zouden objecten in de analyseset zetten die niet in
    `dataset.nodes` of `dataset.conduits` voorkomen.

    Dit is bewust een superset van het gevonden pad: `klim_naar_knoop` loopt in de
    breedte en geeft *elke* bezochte knoop terug, dus ook broers op de laatste laag en
    doodgelopen takken. Met enkelvoudige houders (De Wolden en Hoogeveen) is dat dezelfde
    verzameling; met meervoudige houders groeit de schil met knopen die geen enkele
    resolutie nodig heeft. Veilig, want dit vult alleen de contextschil aan en die
    wordt nooit kern: wat erbij komt kan geen bevinding in het gebied opleveren. Het
    smallere alternatief -- alleen het gevonden pad -- zou het risico de andere kant op
    leggen, en dan loopt de wandeling op de uitgedunde dataset dood.
    """
    return set(dataset.klim_naar_knoop(uri, wortels)[1])


def _component(
    dataset: GwswDataset, config: CheckConfig, kern: frozenset[str]
) -> tuple[set[str], int]:
    """De samenhangende vrijvervalcomponenten die de kern raken.

    De weg zonder gedeelde index: bouwt de structuur en selecteert er meteen uit.
    `GedeeldeIndex.component` doet met dezelfde structuur alleen de selectie.

    In `src/` roept niets deze functie meer aan -- `bouw_analyseset` gaat altijd via
    de index. Hij staat er als referentie-implementatie voor de equivalentietest in
    `tests/test_afbakening.py`, die de gehoiste route ertegen afzet.
    """
    return _selecteer_component(*_componentstructuur(dataset, config), kern)


def _selecteer_component(
    componenten: list[set[str]],
    component_van: dict[str, int],
    strengen: tuple[tuple[str, str], ...],
    zonder_netwerkverband: int,
    kern: frozenset[str],
) -> tuple[set[str], int]:
    """De componenten uit de structuur die de kern raken, met de strengen erin."""
    geraakt = {component_van[knoop] for knoop in kern if knoop in component_van}
    geraakt |= {component_van[begin] for uri, begin in strengen if uri in kern}

    gevonden: set[str] = set()
    for index in geraakt:
        gevonden |= componenten[index]
    gevonden |= {uri for uri, begin in strengen if component_van.get(begin) in geraakt}
    return gevonden, zonder_netwerkverband


def _componentstructuur(
    dataset: GwswDataset, config: CheckConfig
) -> tuple[list[set[str]], dict[str, int], tuple[tuple[str, str], ...], int]:
    """De samenhangende vrijvervalcomponenten van de volledige export.

    Deze structuur hangt niet van een studiegebied af; alleen de vraag welke
    component een kern raakt doet dat. Daarom wordt hij bij een run over meerdere
    gebieden een keer gebouwd.

    De mechanische leidingen liggen er sinds issue #73 in, naast de vrijvervalleidingen.
    Ze stonden er bewust niet in zolang de NET-checks ze niet volgden, maar sinds issue
    #72 loopt de bereikbaarheid van NET-001 en NET-002 door het persnet (BO-54) en telt
    een pompput zelf niet meer als eindpunt (BO-55). Bakende de schil zich dan nog op
    het zuivere vrijverval af, dan viel het gemaal achter de persleiding erbuiten en
    meldde een gebiedsrun strengen die de gemeentebrede run niet meldt -- op De Wolden
    en Hoogeveen 17 van de 88 buurten. Dat botst met de gelijkwaardigheidseis van BO-12;
    zie BO-56 voor de meting en de prijs (analyseset 1,7x).

    De graaf dient alleen om de samenhang tussen knopen vast te stellen; welke
    strengen erbij horen, wordt er los van bijgehouden. Twee evenwijdige strengen
    tussen hetzelfde knopenpaar veranderen niets aan die samenhang, maar zouden als
    kantattribuut (`add_edge(..., uri=...)`) elkaar overschrijven en zo een van de
    twee stilzwijgend uit de analyseset laten vallen -- parallelle strengen zijn in
    dit domein normaal (zie TOP-013).

    Een VRIJVERVALstreng waarvan een van beide uiteinden niet naar een netwerkknoop
    herleidt, slaat deze functie over: hij komt in geen enkele component terecht en kan
    dus nooit via de component in de schil belanden, ook niet als zijn wel herleidbare
    kant in een geraakte component ligt. Dat is hetzelfde antwoord dat de
    netwerkchecks zelf geven -- `_bouw_netwerk` in `checks/verbanden.py` zet zulke
    strengen apart in `unconnected` en houdt ze buiten de graaf -- maar mag niet
    stilzwijgend gebeuren; het aantal gaat terug naar de aanroeper. Een mechanische
    leiding valt daar juist terug op de rauwe koppeling, precies zoals
    `_bouw_bereikbaarheid` dat doet: het persnet komt samen op hulpstukken
    die nergens naartoe klimmen, en zonder die terugval hakt elke T de route in stukken.
    Zulke leidingen tellen niet mee in `zonder_netwerkverband`; dat getal gaat over de
    vrijvervalstrengen die het rapport noemt.
    """
    wortels = config.klassen.netwerkknopen
    graaf = nx.Graph()
    strengen: list[tuple[str, str]] = []
    zonder_netwerkverband = 0
    for wortel in config.klassen.vrijvervalleiding:
        for uri in leeslaag.strengen_van(dataset, wortel):
            conduit = dataset.conduits.get(uri)
            if conduit is None:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            if begin is None or eind is None:
                zonder_netwerkverband += 1
                continue
            graaf.add_edge(begin, eind)
            strengen.append((uri, begin))

    for wortel in config.klassen.mechanisch:
        for uri in leeslaag.strengen_van(dataset, wortel):
            conduit = dataset.conduits.get(uri)
            if conduit is None:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels) or conduit.start_node
            eind = dataset.resolve_network_node(conduit.end_node, wortels) or conduit.end_node
            if begin is None or eind is None:
                continue
            graaf.add_edge(begin, eind)
            strengen.append((uri, begin))

    componenten = list(nx.connected_components(graaf))
    component_van = {knoop: index for index, knopen in enumerate(componenten) for knoop in knopen}
    return componenten, component_van, tuple(strengen), zonder_netwerkverband


def _binnen_buffer(
    dataset: GwswDataset,
    area: StudyArea,
    config: CheckConfig,
    gedeeld: GedeeldeIndex | None = None,
) -> set[str]:
    """De objecten binnen de contextbuffer om het gebied.

    Met een gedeelde index levert de boom de kandidaten; het oordeel blijft
    `intersects` op de gebufferde geometrie, precies zoals zonder index.
    """
    afstand = config.studiegebied.context_buffer_m
    if afstand <= 0:
        return set()
    gebufferd = area.geometry.buffer(afstand)
    if gedeeld is not None:
        return {
            uri
            for uri in gedeeld.kandidaten(gebufferd)
            if _raakt(gebufferd, _geometrie(dataset, uri))
        }
    binnen = {uri for uri, node in dataset.nodes.items() if _raakt(gebufferd, node.point)}
    binnen |= {uri for uri, kant in dataset.conduits.items() if _raakt(gebufferd, kant.line)}
    return binnen


def _raakt(gebufferd: BaseGeometry, geometrie: BaseGeometry | None) -> bool:
    """Geeft aan of een geometrie de gebufferde gebiedsrand raakt."""
    return geometrie is not None and not geometrie.is_empty and gebufferd.intersects(geometrie)
