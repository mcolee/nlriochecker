"""Gedeelde navigatie door de dataset: welke put hoort bij welke streng.

Meerdere categorieen checks (TOP, ATTR, HGT, ADM, RVZ) hebben hetzelfde nodig: de
putten aan weerszijden van een streng, en omgekeerd de strengen die op een put
uitkomen. Die afleiding staat hier een keer, zodat de categorieen niet elk hun
eigen variant krijgen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gwswpijplijn.checks.base import CheckContext
from gwswpijplijn.dataset import Conduit, Node


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


def objecten_van_klassen(context: CheckContext, wortels: list[str], bron: str) -> list:
    """De knopen of strengen van deze klassen, ontdubbeld en in vaste volgorde."""
    dataset = context.dataset
    verzameling = dataset.nodes if bron == "nodes" else dataset.conduits
    gevonden = {
        uri: verzameling[uri]
        for wortel in wortels
        for uri in dataset.of_class(wortel)
        if uri in verzameling
    }
    return list(gevonden.values())
