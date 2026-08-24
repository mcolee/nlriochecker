"""Eigenschappen van de aangeleverde dataset die de bevindingen kleuren.

Dit zijn geen bevindingen. Een dataset waarin elke begindatum op 1 januari valt
of waarin een zesde van de inwinningsregistraties "niet achterhaald" zegt, heeft
daarmee geen gebrek per object; er valt niets aan te herstellen en een melding
per object zou alleen ruis geven. Het bepaalt wel hoe de bevindingen gelezen
moeten worden: leeftijdsberekeningen zijn dan op jaarniveau, en een
compleetheidscijfer dat expliciete onbekend-waarden meetelt leest te
rooskleurig. Daarom staat het als samenvattende regel in het rapport en niet als
check in het register.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.dataset import GwswDataset, Inwinning

JAARGRENS = (1, 1)


@dataclass(frozen=True)
class DatumPrecisie:
    """Hoeveel waarden van een datumkenmerk op de jaargrens vallen."""

    kenmerk: str
    aantal: int
    op_jaargrens: int

    @property
    def aandeel(self) -> float:
        """Het aandeel op de jaargrens, in procenten."""
        return 100.0 * self.op_jaargrens / self.aantal if self.aantal else 0.0

    @property
    def jaarprecisie(self) -> bool:
        """Waar als elke waarde op 1 januari valt en alleen het jaartal telt."""
        return self.aantal > 0 and self.op_jaargrens == self.aantal


@dataclass(frozen=True)
class InwinningVulling:
    """Hoe de inwinningsmetagegevens van een kenmerk gevuld zijn."""

    kenmerk: str
    aantal: int
    met_wijze: int
    onbekend: int
    per_wijze: dict[str, int] = field(default_factory=dict)

    @property
    def zonder_wijze(self) -> int:
        """Het aantal waarden zonder enige inwinningswijze."""
        return self.aantal - self.met_wijze

    @property
    def onbekend_aandeel(self) -> float:
        """Het aandeel expliciete onbekend-waarden binnen de gevulde wijzen."""
        return 100.0 * self.onbekend / self.met_wijze if self.met_wijze else 0.0


@dataclass(frozen=True)
class DataCharacteristics:
    """De karakteristieken van een dataset, voor in de rapportkop."""

    datums: list[DatumPrecisie] = field(default_factory=list)
    inwinning: list[InwinningVulling] = field(default_factory=list)
    # Hoeveel hoogtewaarden de vulwaarde-leesregel als niet geregistreerd heeft
    # gelezen. Ze tellen niet mee in `inwinning`, want die telt over de gemarkeerde
    # dataset. Zonder dit getal zouden de noemers van die tabel bewegen zonder dat
    # het rapport zegt waarom.
    vulwaarden: int = 0

    @property
    def jaarprecisie(self) -> list[DatumPrecisie]:
        """De datumkenmerken die alleen op jaarniveau informatie dragen."""
        return [precisie for precisie in self.datums if precisie.jaarprecisie]

    @property
    def onbekend_totaal(self) -> int:
        """Het totaal aantal expliciete onbekend-waarden over alle kenmerken."""
        return sum(vulling.onbekend for vulling in self.inwinning)


def bepaal_karakteristiek(dataset: GwswDataset, config: CheckConfig) -> DataCharacteristics:
    """Meet de datumprecisie en de vulling van de inwinningsmetagegevens."""
    return DataCharacteristics(
        datums=_datumprecisie(dataset),
        inwinning=_inwinningsvulling(dataset, config),
        vulwaarden=_vulwaarden(dataset),
    )


def _vulwaarden(dataset: GwswDataset) -> int:
    """Telt de hoogtewaarden die de vulwaarde-leesregel heeft weggezet.

    Precies de vier kenmerken die `_inwinningsvulling` telt: `markeer_vulwaarden`
    werkt op geen andere velden. Elk van deze waarden is uit de noemers van die
    tabel verdwenen.
    """
    return sum(len(node.vulwaarden) for node in dataset.nodes.values()) + sum(
        len(conduit.vulwaarden) for conduit in dataset.conduits.values()
    )


def _datumprecisie(dataset: GwswDataset) -> list[DatumPrecisie]:
    """Telt per datumkenmerk hoeveel waarden op 1 januari vallen.

    Welke kenmerken datums zijn volgt uit de dataset zelf (de GWSW-naam bevat
    "datum" en de waarde is als datum te lezen), niet uit een vaste lijst; een
    export met een datumkenmerk dat hier niet in staat zou anders ongemerkt buiten
    beeld blijven.
    """
    totaal: Counter[str] = Counter()
    jaargrens: Counter[str] = Counter()

    for aspect in _alle_aspecten(dataset):
        if "datum" not in aspect.kind.lower():
            continue
        datum = aspect.date
        if datum is None:
            continue
        totaal[aspect.kind] += 1
        if (datum.month, datum.day) == JAARGRENS:
            jaargrens[aspect.kind] += 1

    return [
        DatumPrecisie(kenmerk=kenmerk, aantal=aantal, op_jaargrens=jaargrens[kenmerk])
        for kenmerk, aantal in sorted(totaal.items())
    ]


def _inwinningsvulling(dataset: GwswDataset, config: CheckConfig) -> list[InwinningVulling]:
    """Telt per kritiek hoogtekenmerk hoe de inwinningswijze gevuld is.

    Alleen de kenmerken die het datamodel van deze pijplijn draagt: maaiveldhoogte,
    putdekselniveau en de beide BOB's. Andere kenmerken hebben in de export ook
    inwinning, maar die leest de pijplijn niet in en er valt dus niets over te
    zeggen.
    """
    onbekend = set(config.inwinning.onbekend)
    nodes = list(dataset.nodes.values())
    conduits = list(dataset.conduits.values())
    # Elke reeks leest de herkomst zoals de rest van de pijplijn hem leest, dus
    # inclusief de terugval op de puntgeometrie waar die geldt. Anders zouden de
    # kolommen van de ene rij niet met die van de volgende te vergelijken zijn.
    reeksen: list[tuple[str, list[Inwinning | None]]] = [
        (
            "maaiveldhoogte",
            [node.maaiveld_inwinning for node in nodes if node.maaiveld_aspect is not None],
        ),
        (
            "putdekselniveau",
            [node.deksel_inwinning for node in nodes if node.deksel_aspect is not None],
        ),
        ("BOB beginpunt", _herkomsten(conduit.bob_start_aspect for conduit in conduits)),
        ("BOB eindpunt", _herkomsten(conduit.bob_end_aspect for conduit in conduits)),
    ]

    vullingen = []
    for kenmerk, herkomsten in reeksen:
        if not herkomsten:
            continue
        wijzen = Counter(
            herkomst.wijze
            for herkomst in herkomsten
            if herkomst is not None and herkomst.wijze is not None
        )
        vullingen.append(
            InwinningVulling(
                kenmerk=kenmerk,
                aantal=len(herkomsten),
                met_wijze=sum(wijzen.values()),
                onbekend=sum(aantal for wijze, aantal in wijzen.items() if wijze in onbekend),
                per_wijze=dict(sorted(wijzen.items())),
            )
        )
    return vullingen


def _herkomsten(aspecten) -> list[Inwinning | None]:
    """De inwinning van de aanwezige kenmerken; ontbrekende kenmerken tellen niet mee.

    Voor de BOB's is er geen terugval nodig: die hangen aan een begin- of
    eindpunt van een leiding, en dat draagt geen eigen puntgeometrie waarop een
    conversie de wijze zou kunnen parkeren.
    """
    return [aspect.inwinning for aspect in aspecten if aspect is not None]


def _alle_aspecten(dataset: GwswDataset):
    """Alle kenmerken van alle knopen en strengen."""
    for node in dataset.nodes.values():
        yield from node.aspects
    for conduit in dataset.conduits.values():
        yield from conduit.aspects
