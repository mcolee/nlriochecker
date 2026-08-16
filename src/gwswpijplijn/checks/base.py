"""Raamwerk voor de checks: ernst, dimensie, bevindingen en de registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from shapely.geometry import Point

from gwswpijplijn.checkconfig import CheckConfig
from gwswpijplijn.dataset import GwswDataset
from gwswpijplijn.errors import StudyAreaError
from gwswpijplijn.externedata import ExternalData
from gwswpijplijn.karakteristiek import DataCharacteristics, bepaal_karakteristiek
from gwswpijplijn.plausibiliteit import PlausibilityTables, load_plausibility
from gwswpijplijn.studiegebied import StudyArea


class Severity(StrEnum):
    """Ernstniveau conform het checkregister."""

    ERROR = "F"
    WARNING = "W"


class Dimension(StrEnum):
    """Dimensietag conform het kwaliteitsraamwerk uit het checkregister."""

    CONSISTENCY = "Consistentie"
    COMPLETENESS = "Compleetheid"
    PLAUSIBILITY = "Plausibiliteit"
    TIMELINESS = "Actualiteit"
    TRACEABILITY = "Traceerbaarheid"
    PRECISION = "Precisie"
    ACCURACY = "Nauwkeurigheid"
    COMPLIANCE = "Compliance"


@dataclass(frozen=True)
class Finding:
    """Een enkele bevinding van een check op een object."""

    check_id: str
    severity: Severity
    dimension: Dimension
    object_uri: str
    object_label: str
    message: str
    typing_reliable: bool
    details: dict[str, object] = field(default_factory=dict)
    # De EXT-checks melden ook objecten die niet uit de GWSW-dataset komen (een
    # BGT-putdeksel zonder put, een BAG-pand zonder riolering). Die hebben geen
    # dataset-URI om op af te bakenen; hun eigen RD-coordinaat neemt die rol over.
    location: tuple[float, float] | None = None


@dataclass(frozen=True)
class CheckContext:
    """Alles wat een check nodig heeft om te draaien."""

    dataset: GwswDataset
    config: CheckConfig
    unreliable_objects: frozenset[str] = frozenset()
    plausibiliteit: PlausibilityTables = field(default_factory=load_plausibility)
    bronnen: ExternalData | None = None
    _cache: dict[str, object] = field(default_factory=dict, compare=False, repr=False)

    def cached(self, sleutel: str, bouw: Callable[[], object]) -> object:
        """Bouwt een afgeleide structuur een keer per context en hergebruikt die.

        De topologie-index en de netwerkgraaf worden door meerdere checks en door
        `examined()` en `notes()` opgevraagd. Op een dataset met tienduizenden
        objecten is telkens opnieuw opbouwen merkbaar duur.
        """
        if sleutel not in self._cache:
            self._cache[sleutel] = bouw()
        return self._cache[sleutel]

    def is_reliable(self, uri: str) -> bool:
        """Geeft aan of de typering van dit object betrouwbaar genoeg is.

        De vergelijking gaat op URI. De SHACL-meting benoemt de te globale klassen
        en de instanties komen uit de dataset zelf, dus de koppeling is exact; het
        vervallen detailrapportformaat kon alleen op labels joinen.
        """
        return uri not in self.unreliable_objects

    def matched_objects(self) -> frozenset[str]:
        """De onbetrouwbare objecten die daadwerkelijk in de dataset voorkomen."""
        aanwezig = set(self.dataset.nodes) | set(self.dataset.conduits)
        return frozenset(self.unreliable_objects & aanwezig)


@dataclass(frozen=True)
class CheckOutcome:
    """Het resultaat van een enkele check."""

    check_id: str
    title: str
    severity: Severity
    dimension: Dimension
    examined: int
    findings: list[Finding]
    notes: list[str] = field(default_factory=list)
    weggelaten: int = 0
    skeleton: str = ""

    @property
    def unreliable_count(self) -> int:
        """Het aantal bevindingen waarvan de typering onbetrouwbaar is."""
        return sum(1 for finding in self.findings if not finding.typing_reliable)


@dataclass(frozen=True)
class CheckRun:
    """Alle uitgevoerde checks over een dataset."""

    dataset: GwswDataset
    outcomes: list[CheckOutcome]
    typing_gate_applied: bool
    unreliable_labels: int = 0
    unreliable_labels_in_dataset: int = 0
    study_area: StudyArea | None = None
    bronnen: ExternalData | None = None
    karakteristiek: DataCharacteristics | None = None
    # De uitvoerlaag heeft de klassenlijsten en de rapportdrempels nodig; die
    # meegeven is minder broos dan ze langs elke schrijver door te reiken.
    config: CheckConfig | None = None

    @property
    def findings(self) -> list[Finding]:
        """Alle bevindingen van alle checks, na afbakening tot het studiegebied."""
        return [finding for outcome in self.outcomes for finding in outcome.findings]

    def count(self, severity: Severity) -> int:
        """Het aantal bevindingen van een ernstniveau."""
        return sum(1 for finding in self.findings if finding.severity is severity)

    def beperk_tot_studiegebied(self, area: StudyArea) -> CheckRun:
        """Geeft een run terug met alleen de bevindingen binnen het gebied.

        De checks zijn op de volledige dataset gedraaid; pas hier wordt afgebakend.
        Zo blijven de netwerkchecks over het hele stelsel redeneren en ontstaan er
        geen randeffecten doordat een streng het gebied uit loopt.
        """
        binnen = objecten_in_gebied(self.dataset, area)
        if not binnen:
            raise StudyAreaError(
                f"studiegebied {area.name!r} ({area.area_ha:.1f} ha) bevat geen GWSW-objecten: "
                f"geen enkele put en geen enkele streng valt erbinnen. Controleer de laagkeuze "
                f"en of het gebied binnen het beheergebied van {self.dataset.source.name} ligt."
            )

        def hoort_erbij(finding: Finding) -> bool:
            """Geeft aan of deze bevinding binnen het studiegebied valt."""
            if finding.object_uri in binnen:
                return True
            if finding.location is not None:
                return area.bevat(Point(*finding.location))
            return False

        outcomes = [
            CheckOutcome(
                check_id=outcome.check_id,
                title=outcome.title,
                severity=outcome.severity,
                dimension=outcome.dimension,
                examined=outcome.examined,
                findings=[f for f in outcome.findings if hoort_erbij(f)],
                notes=outcome.notes,
                weggelaten=sum(1 for f in outcome.findings if not hoort_erbij(f)),
                skeleton=outcome.skeleton,
            )
            for outcome in self.outcomes
        ]
        return CheckRun(
            dataset=self.dataset,
            outcomes=outcomes,
            typing_gate_applied=self.typing_gate_applied,
            unreliable_labels=self.unreliable_labels,
            unreliable_labels_in_dataset=self.unreliable_labels_in_dataset,
            study_area=area,
            bronnen=self.bronnen,
            karakteristiek=self.karakteristiek,
            config=self.config,
        )


class Check(ABC):
    """Basisklasse van een check uit het checkregister."""

    id: ClassVar[str]
    title: ClassVar[str]
    severity: ClassVar[Severity]
    dimension: ClassVar[Dimension]
    # De detailsleutels die twee bevindingen van deze check op hetzelfde object van
    # elkaar onderscheiden. 'zijde' is de gangbare: verschillende HGT-checks melden
    # per strengeinde. Heeft een check een eigen onderscheid, dan declareert ze dat
    # hier; de meldingenlaag waarschuwt als er toch twee dezelfde ID krijgen.
    id_sleutels: ClassVar[tuple[str, ...]] = ("zijde",)

    @abstractmethod
    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Levert de bevindingen van deze check op de dataset."""

    def notes(self, context: CheckContext) -> list[str]:
        """Toelichtingen bij het bereik van deze check, bijvoorbeeld wat er buiten viel."""
        return []

    def examined(self, context: CheckContext) -> int:
        """Het aantal objecten dat deze check bekeken heeft."""
        return len(context.dataset.nodes) + len(context.dataset.conduits)

    def finding(
        self,
        context: CheckContext,
        uri: str,
        label: str,
        message: str,
        location: tuple[float, float] | None = None,
        **details: object,
    ) -> Finding:
        """Bouwt een bevinding en zet de typeringsvlag op grond van het label."""
        return Finding(
            check_id=self.id,
            severity=self.severity,
            dimension=self.dimension,
            object_uri=uri,
            object_label=label,
            message=message,
            typing_reliable=context.is_reliable(uri),
            details=details,
            location=location,
        )


class SkeletonCheck(Check):
    """Een check die in het register staat maar (nog) geen uitslag kan geven.

    Stilzwijgend overslaan mag niet: een check die er niet is, leest in het rapport
    als een check zonder bevindingen. Een skelet levert daarom nul bevindingen op
    met een expliciete markering en reden erbij, zodat rapport en dekkingsmatrix
    laten zien wat er *niet* gekeken is.
    """

    markering: ClassVar[str]
    reden: ClassVar[str]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Levert nooit bevindingen; deze check is niet uitvoerbaar."""
        return iter(())

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de markering en de reden waarom er niets getoetst is."""
        return [f"**{self.markering}** — {self.reden}"]

    def examined(self, context: CheckContext) -> int:
        """Een skelet bekijkt niets."""
        return 0


def objecten_in_gebied(dataset: GwswDataset, area: StudyArea) -> frozenset[str]:
    """De URI's van de objecten waarvan de geometrie het studiegebied raakt."""
    binnen = {uri for uri, node in dataset.nodes.items() if area.bevat(node.point)}
    binnen |= {uri for uri, conduit in dataset.conduits.items() if area.bevat(conduit.line)}
    return frozenset(binnen)


REGISTRY: dict[str, type[Check]] = {}


def register(check: type[Check]) -> type[Check]:
    """Registreert een check onder haar ID uit het checkregister."""
    if check.id in REGISTRY:
        raise ValueError(f"check-ID {check.id} is al geregistreerd")
    REGISTRY[check.id] = check
    return check


def run_checks(
    context: CheckContext,
    check_ids: list[str] | None = None,
    typing_gate_applied: bool = False,
) -> CheckRun:
    """Draait de gevraagde checks; zonder selectie draait de hele registry."""
    gekozen = sorted(REGISTRY) if check_ids is None else list(check_ids)

    onbekend = [check_id for check_id in gekozen if check_id not in REGISTRY]
    if onbekend:
        raise KeyError(f"onbekende check-ID's: {', '.join(sorted(onbekend))}")

    outcomes = []
    for check_id in gekozen:
        check = REGISTRY[check_id]()
        outcomes.append(
            CheckOutcome(
                check_id=check.id,
                title=check.title,
                severity=check.severity,
                dimension=check.dimension,
                examined=check.examined(context),
                findings=list(check.run(context)),
                notes=check.notes(context),
                skeleton=check.markering if isinstance(check, SkeletonCheck) else "",
            )
        )

    return CheckRun(
        dataset=context.dataset,
        outcomes=outcomes,
        typing_gate_applied=typing_gate_applied,
        unreliable_labels=len(context.unreliable_objects),
        unreliable_labels_in_dataset=len(context.matched_objects()),
        bronnen=context.bronnen,
        karakteristiek=bepaal_karakteristiek(context.dataset, context.config),
        config=context.config,
    )
