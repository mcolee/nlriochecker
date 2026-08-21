"""De analyseset: welke objecten met een studiegebied door de checks gaan.

Analyseer de kern plus een contextschil, rapporteer de kern. De schil is precies zo
groot dat de netwerkchecks hun antwoord houden: de samenhangende vrijvervalcomponent
waar de kern in ligt, plus een buffer voor de checks die naar nabijheid kijken zonder
netwerkverband. Zonder die schil zou een streng die het gebied uit loopt als
doodlopend gelden en zouden NET-001 en NET-002 valse bevindingen geven.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import networkx as nx
from shapely import STRtree
from shapely.geometry.base import BaseGeometry

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.dataset import GwswDataset
from nlriochecker.studiegebied import StudyArea


@dataclass(frozen=True)
class Analyseset:
    """De objecten die met een studiegebied door de checks gaan."""

    kern: frozenset[str]
    schil: frozenset[str]
    dataset: GwswDataset
    volledig_aantal: int
    # Vrijvervalstrengen die de componentberekening moest overslaan omdat een van
    # beide uiteinden niet naar een netwerkknoop herleidt (zie `_component`). Ze
    # kunnen daardoor nooit via de component in de schil belanden, ook niet als hun
    # wel herleidbare kant in een geraakte component ligt. Hetzelfde als wat
    # `checks/netwerk.py` als `unconnected` apart houdt; hier alleen het aantal,
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

    @property
    def aandeel(self) -> float:
        """Welk deel van de export de analyseset beslaat."""
        return len(self.alles) / self.volledig_aantal if self.volledig_aantal else 0.0


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
    componenten: list[set[str]]
    component_van: dict[str, int]
    strengen: tuple[tuple[str, str], ...]
    zonder_netwerkverband: int

    def kandidaten(self, geometrie: BaseGeometry) -> Iterator[str]:
        """De URI's waarvan de omhullende die van `geometrie` raakt."""
        for index in self.boom.query(geometrie):
            yield self.uris[index]

    def component(self, kern: frozenset[str]) -> tuple[set[str], int]:
        """De samenhangende vrijvervalcomponenten die deze kern raken.

        Alleen deze selectie hangt van het gebied af; de componentstructuur zelf niet.
        """
        return _selecteer_component(
            self.componenten, self.component_van, self.strengen, self.zonder_netwerkverband, kern
        )


def bouw_gedeelde_index(dataset: GwswDataset, config: CheckConfig) -> GedeeldeIndex:
    """Bouwt de ruimtelijke index en de componentenstructuur van de volledige export."""
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

    componenten, component_van, strengen, zonder_netwerkverband = _componentstructuur(
        dataset, config
    )
    return GedeeldeIndex(
        boom=STRtree(geometrieen),
        uris=tuple(uris),
        componenten=componenten,
        component_van=component_van,
        strengen=strengen,
        zonder_netwerkverband=zonder_netwerkverband,
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
    """De schakels op de weg omhoog naar de herleidbare netwerkknoop, die erbij.

    Loopt langs `GwswDataset.klim_naar_knoop`, dezelfde wandeling als
    `resolve_network_node` -- twee klimfuncties naast elkaar zouden op een export met
    meervoudige houders uiteenlopen, en dan houdt de analyseset precies de schakel
    niet vast die de resolutie nodig heeft. Schakels die niet in `dataset.nodes`
    staan blijven eruit: die zouden objecten in de analyseset zetten die niet in
    `dataset.nodes` of `dataset.conduits` voorkomen.
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

    Bewust alleen over de vrijvervalleidingen: mechanische leidingen verbinden
    deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen,
    terwijl de NET-checks ze niet volgen.

    De graaf dient alleen om de samenhang tussen knopen vast te stellen; welke
    strengen erbij horen, wordt er los van bijgehouden. Twee evenwijdige strengen
    tussen hetzelfde knopenpaar veranderen niets aan die samenhang, maar zouden als
    kantattribuut (`add_edge(..., uri=...)`) elkaar overschrijven en zo een van de
    twee stilzwijgend uit de analyseset laten vallen -- parallelle strengen zijn in
    dit domein normaal (zie TOP-013).

    Een streng waarvan een van beide uiteinden niet naar een netwerkknoop herleidt,
    slaat deze functie over: hij komt in geen enkele component terecht en kan dus
    nooit via de component in de schil belanden, ook niet als zijn wel herleidbare
    kant in een geraakte component ligt. Dat is hetzelfde antwoord dat de
    netwerkchecks zelf geven -- `_bouw_netwerk` in `checks/netwerk.py` zet zulke
    strengen apart in `unconnected` en houdt ze buiten de graaf -- maar mag niet
    stilzwijgend gebeuren; het aantal gaat terug naar de aanroeper.
    """
    wortels = config.klassen.netwerkknopen
    graaf = nx.Graph()
    strengen: list[tuple[str, str]] = []
    zonder_netwerkverband = 0
    for wortel in config.klassen.vrijvervalleiding:
        for uri in dataset.of_class(wortel):
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
