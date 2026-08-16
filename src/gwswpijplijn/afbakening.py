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
    schil = _component(dataset, config, kern) | _binnen_buffer(dataset, area, config)
    schil -= kern
    volledig = len(dataset.nodes) + len(dataset.conduits)
    return Analyseset(
        kern=kern,
        schil=frozenset(schil),
        dataset=dataset.subset(kern | schil),
        volledig_aantal=volledig,
    )


def _component(dataset: GwswDataset, config: CheckConfig, kern: frozenset[str]) -> set[str]:
    """De samenhangende vrijvervalcomponenten die de kern raken.

    Bewust alleen over de vrijvervalleidingen: mechanische leidingen verbinden
    deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen,
    terwijl de NET-checks ze niet volgen.
    """
    wortels = config.klassen.netwerkknopen
    graaf = nx.Graph()
    for wortel in config.klassen.vrijvervalleiding:
        for uri in dataset.of_class(wortel):
            conduit = dataset.conduits.get(uri)
            if conduit is None:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            if begin is None or eind is None:
                continue
            graaf.add_edge(begin, eind, uri=uri)

    gevonden: set[str] = set()
    for knopen in nx.connected_components(graaf):
        if not (knopen & kern) and not any(
            graaf.edges[kant]["uri"] in kern for kant in graaf.subgraph(knopen).edges
        ):
            continue
        gevonden |= knopen
        gevonden |= {graaf.edges[kant]["uri"] for kant in graaf.subgraph(knopen).edges}
    return gevonden


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
