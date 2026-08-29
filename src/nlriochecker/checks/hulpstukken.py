"""Welke hulpstukken een GWSW-functie met een aantal leidingen dragen.

Een `Hulpstuk` (T-stuk, kruisstuk, mof, afsluitstuk) is in het GWSW geen `Put` en dus
geen netwerkknoop, maar zijn klasse kan wel een functie dragen die zegt hoeveel
leidingen hij hoort te verbinden (`VerbindenVanDrieLeidingen`). Die grens -- "een
telbare functie" -- wordt inmiddels op drie plaatsen gebruikt: TOP-022 en TOP-023
tellen erop (issue #60), TOP-002 en TOP-003 laten een strengeinde erop als geldig eind
gelden (BO-72) en de vrijvervalgraaf maakt er een doorgeefknoop van (BO-83). Zij staat
daarom hier, in een module die alleen `base` en `selectie` leest, en niet in
`checks/topologie.py`: `checks/verbanden.py` heeft haar nodig en topologie importeert
verbanden, dus daar zou een importkring ontstaan.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from gwsw_orox_helpers.dataset import Conduit, GwswDataset, Node

from nlriochecker.checks.base import CheckContext
from nlriochecker.checks.selectie import hulpstukken, leidingen

# Het aantal leidingen dat een functiewaarde van een hulpstuk voorschrijft. De klasse
# → functie-koppeling komt uit de ontologie (`GwswDataset.functie_per_klasse`); dit
# vertaalt alleen het woord naar het getal. Functiewaarden zonder aantal
# (AfsluitenVanLeidingen, VerbindenVanLeidingenInEenHoek, ...) staan er bewust niet in.
AANTAL_PER_FUNCTIE: dict[str, int] = {
    "VerbindenVanTweeLeidingen": 2,
    "VerbindenVanDrieLeidingen": 3,
    "VerbindenVanVierLeidingen": 4,
}


@dataclass(frozen=True)
class _Hulpstukaansluiting:
    """Wat er op een hulpstuk met telbare functie aangesloten is."""

    node: Node
    functie: str
    verwacht: int
    # De verschillende knopen aan de andere kant, naar de put herleid; twee strengen
    # tussen dezelfde twee knopen zijn een richting.
    buren: tuple[str, ...]
    # Strengen waarvan het andere eind aan niets hangt; elk telt als eigen richting.
    losse_einden: int
    strengen: tuple[str, ...]

    @property
    def richtingen(self) -> int:
        """Het aantal richtingen dat dit hulpstuk werkelijk verbindt."""
        return len(self.buren) + self.losse_einden


@dataclass(frozen=True)
class _Hulpstuktelling:
    """De telbare hulpstukken plus, per klasse, hoeveel er buiten de toets vielen."""

    telbaar: tuple[_Hulpstukaansluiting, ...]
    buiten_per_klasse: dict[str, int]


def telbare_hulpstukken(context: CheckContext) -> frozenset[str]:
    """De URI's van de hulpstukken waarvan de klasse een aantal leidingen voorschrijft.

    Bewust een eigen, smalle afleiding naast `_hulpstuktelling` en niet
    `{a.node.uri for a in _hulpstuktelling(context).telbaar}`: die telling leest naast de
    hulpstukken ook de leidingen -- ze telt er immers de richtingen op -- en wie haar
    aanroept declareert daarmee de rol `leidingen`. De vrijvervalgraaf heeft alleen de
    populatie nodig, niet de telling, en elke NET-check zou anders over "alle leidingen"
    verklaren. De grens zelf staat maar een keer, in `_functie_met_aantal`.
    """
    return context.cached("hulpstukken:telbaar", lambda: _bouw_telbare_hulpstukken(context))


def _bouw_telbare_hulpstukken(context: CheckContext) -> frozenset[str]:
    """Filtert de hulpstukken op een functie met een aantal leidingen."""
    dataset = context.dataset
    return frozenset(
        node.uri for node in hulpstukken(context) if _functie_met_aantal(dataset, node) is not None
    )


def _hulpstuktelling(context: CheckContext) -> _Hulpstuktelling:
    """De aansluitingen per hulpstuk; een keer per context, gedeeld door TOP-022 en TOP-023."""
    return context.cached("hulpstukken:aansluitingen", lambda: _bouw_hulpstuktelling(context))


def _bouw_hulpstuktelling(context: CheckContext) -> _Hulpstuktelling:
    """Telt per hulpstuk de richtingen: verschillende buurknopen plus losse einden.

    Rechtstreeks op `start_node`/`end_node` en niet via `aansluitingen()`: die index
    herleidt elk eind naar een netwerkknoop, en een hulpstuk is er geen. De strengen
    komen uit de leidingenrol en niet uit `dataset.conduits`: dat laatste bevat ook
    verbindingen die geen `Leiding` zijn (in het Juinen-voorbeeld 25 om 19).
    """
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    alle = hulpstukken(context)
    uris = {node.uri for node in alle}
    per_hulpstuk: defaultdict[str, list[tuple[Conduit, str | None]]] = defaultdict(list)
    for conduit in leidingen(context):
        for eigen, ander in (
            (conduit.start_node, conduit.end_node),
            (conduit.end_node, conduit.start_node),
        ):
            # Een streng met beide einden aan hetzelfde hulpstuk telt niet als buur.
            if eigen in uris and ander != eigen:
                per_hulpstuk[eigen].append((conduit, ander))

    telbaar: list[_Hulpstukaansluiting] = []
    buiten: Counter[str] = Counter()
    for node in sorted(alle, key=lambda knoop: knoop.uri):
        gevonden = _functie_met_aantal(dataset, node)
        if gevonden is None:
            buiten[dataset.beheerobjecttype(node.uri) or "(zonder type)"] += 1
            continue
        functie, verwacht = gevonden
        buren: set[str] = set()
        los = 0
        labels: list[str] = []
        for conduit, ander in per_hulpstuk.get(node.uri, []):
            labels.append(conduit.label or conduit.uri)
            if ander is None:
                los += 1
            else:
                buren.add(dataset.resolve_network_node(ander, wortels) or ander)
        telbaar.append(
            _Hulpstukaansluiting(
                node, functie, verwacht, tuple(sorted(buren)), los, tuple(sorted(labels))
            )
        )
    return _Hulpstuktelling(tuple(telbaar), dict(buiten))


def _functie_met_aantal(dataset: GwswDataset, node: Node) -> tuple[str, int] | None:
    """De functiewaarde van dit hulpstuk en het aantal leidingen dat zij voorschrijft."""
    for soort in sorted(node.types):
        functie = dataset.functie_per_klasse.get(soort)
        if functie in AANTAL_PER_FUNCTIE:
            return functie, AANTAL_PER_FUNCTIE[functie]
    return None
