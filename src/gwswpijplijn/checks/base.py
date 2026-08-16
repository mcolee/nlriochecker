"""Raamwerk voor de checks: ernst, dimensie, bevindingen en de registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar

from gwswpijplijn.checkconfig import CheckConfig
from gwswpijplijn.dataset import GwswDataset


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


@dataclass(frozen=True)
class CheckContext:
    """Alles wat een check nodig heeft om te draaien."""

    dataset: GwswDataset
    config: CheckConfig
    unreliable_labels: frozenset[str] = frozenset()
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

    def is_reliable(self, label: str) -> bool:
        """Geeft aan of de typering van dit object betrouwbaar genoeg is."""
        return label not in self.unreliable_labels

    def matched_labels(self) -> frozenset[str]:
        """De onbetrouwbare labels die daadwerkelijk in de dataset voorkomen.

        De detailrapporten en de OroX-export zijn losse bestanden; labels die de
        nulmeting noemt hoeven niet allemaal in de dataset te staan. Dat verschil
        hoort zichtbaar te zijn, anders lijkt de typeringspoort vollediger dan hij is.
        """
        aanwezig = {item.label for item in self.dataset.nodes.values()}
        aanwezig |= {item.label for item in self.dataset.conduits.values()}
        return frozenset(self.unreliable_labels & aanwezig)


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

    @property
    def findings(self) -> list[Finding]:
        """Alle bevindingen van alle checks."""
        return [finding for outcome in self.outcomes for finding in outcome.findings]

    def count(self, severity: Severity) -> int:
        """Het aantal bevindingen van een ernstniveau."""
        return sum(1 for finding in self.findings if finding.severity is severity)


class Check(ABC):
    """Basisklasse van een check uit het checkregister."""

    id: ClassVar[str]
    title: ClassVar[str]
    severity: ClassVar[Severity]
    dimension: ClassVar[Dimension]

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
            typing_reliable=context.is_reliable(label),
            details=details,
        )


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
            )
        )

    return CheckRun(
        dataset=context.dataset,
        outcomes=outcomes,
        typing_gate_applied=typing_gate_applied,
        unreliable_labels=len(context.unreliable_labels),
        unreliable_labels_in_dataset=len(context.matched_labels()),
    )
