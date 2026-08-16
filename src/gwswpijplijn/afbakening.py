"""De analyseset: welke objecten met een studiegebied door de checks gaan.

Analyseer de kern plus een contextschil, rapporteer de kern. De schil is precies zo
groot dat de netwerkchecks hun antwoord houden: de samenhangende vrijvervalcomponent
waar de kern in ligt, plus een buffer voor de checks die naar nabijheid kijken zonder
netwerkverband. Zonder die schil zou een streng die het gebied uit loopt als
doodlopend gelden en zouden NET-001 en NET-002 valse bevindingen geven.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from gwswpijplijn.checkconfig import CheckConfig
from gwswpijplijn.dataset import GwswDataset
from gwswpijplijn.studiegebied import StudyArea


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

    @property
    def alles(self) -> frozenset[str]:
        """Kern en schil samen: waarover de checks redeneren."""
        return self.kern | self.schil

    @property
    def aandeel(self) -> float:
        """Welk deel van de export de analyseset beslaat."""
        return len(self.alles) / self.volledig_aantal if self.volledig_aantal else 0.0


def objecten_in_gebied(dataset: GwswDataset, area: StudyArea) -> frozenset[str]:
    """De URI's van de objecten waarvan de geometrie het studiegebied raakt."""
    binnen = {uri for uri, node in dataset.nodes.items() if area.bevat(node.point)}
    binnen |= {uri for uri, conduit in dataset.conduits.items() if area.bevat(conduit.line)}
    return frozenset(binnen)


def bouw_analyseset(dataset: GwswDataset, area: StudyArea, config: CheckConfig) -> Analyseset:
    """Bouwt kern en contextschil en levert de uitgedunde dataset."""
    kern = objecten_in_gebied(dataset, area)
    component, zonder_netwerkverband = _component(dataset, config, kern)
    schil = component | _binnen_buffer(dataset, area, config)
    schil -= kern
    volledig = len(dataset.nodes) + len(dataset.conduits)
    return Analyseset(
        kern=kern,
        schil=frozenset(schil),
        dataset=dataset.subset(kern | schil),
        volledig_aantal=volledig,
        strengen_zonder_netwerkverband=zonder_netwerkverband,
    )


def _component(
    dataset: GwswDataset, config: CheckConfig, kern: frozenset[str]
) -> tuple[set[str], int]:
    """De samenhangende vrijvervalcomponenten die de kern raken.

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

    geraakt = {component_van[knoop] for knoop in kern if knoop in component_van}
    geraakt |= {component_van[begin] for uri, begin in strengen if uri in kern}

    gevonden: set[str] = set()
    for index in geraakt:
        gevonden |= componenten[index]
    gevonden |= {uri for uri, begin in strengen if component_van.get(begin) in geraakt}
    return gevonden, zonder_netwerkverband


def _binnen_buffer(dataset: GwswDataset, area: StudyArea, config: CheckConfig) -> set[str]:
    """De objecten binnen de contextbuffer om het gebied."""
    afstand = config.studiegebied.context_buffer_m
    if afstand <= 0:
        return set()
    gebufferd = area.geometry.buffer(afstand)
    binnen = {
        uri
        for uri, node in dataset.nodes.items()
        if node.point is not None and not node.point.is_empty and gebufferd.intersects(node.point)
    }
    binnen |= {
        uri
        for uri, kant in dataset.conduits.items()
        if kant.line is not None and not kant.line.is_empty and gebufferd.intersects(kant.line)
    }
    return binnen
