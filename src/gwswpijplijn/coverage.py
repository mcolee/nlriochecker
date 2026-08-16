"""Toetst per geschrapte check of de nulmeting het onderwerp in deze dataset raakt."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from gwswpijplijn.analysis import MetingAnalysis, ReportAnalysis
from gwswpijplijn.config import CheckMapping, CoverageConfig, MessagePattern


class Verdict(StrEnum):
    """Het oordeel over een dekkingclaim binnen deze dataset."""

    TOUCHED = "geraakt"
    UNTOUCHED = "niet geraakt"
    UNVERIFIABLE = "niet toetsbaar"


@dataclass(frozen=True)
class CheckEvidence:
    """Wat de nulmeting binnen een CFK over dit onderwerp meldt."""

    cfk: str
    required: bool
    row_count: int
    object_count: int
    shapes: list[str]

    @property
    def found(self) -> bool:
        """Geeft aan of er uberhaupt een melding gevonden is."""
        return self.row_count > 0


@dataclass(frozen=True)
class CheckCoverage:
    """Het dekkingoordeel over een enkele geschrapte check."""

    mapping: CheckMapping
    evidence: list[CheckEvidence]
    counter_evidence: list[CheckEvidence]
    verdict: Verdict
    typing_reliable: bool

    @property
    def evidence_cfks(self) -> list[str]:
        """De CFK's waarin daadwerkelijk bewijs gevonden is."""
        return [item.cfk for item in self.evidence if item.found]

    @property
    def has_counter_evidence(self) -> bool:
        """Geeft aan of er meldingen zijn die juist op een gat in de dekking wijzen."""
        return any(item.found for item in self.counter_evidence)


@dataclass(frozen=True)
class CoverageResult:
    """De dekkinganalyse over een volledig rapportenpaar."""

    dataset: str
    config: CoverageConfig
    checks: list[CheckCoverage]

    @property
    def untouched(self) -> list[CheckCoverage]:
        """De checks waarvan het onderwerp in deze dataset niet geraakt wordt."""
        return [check for check in self.checks if check.verdict is not Verdict.TOUCHED]


def assess_coverage(analyse: MetingAnalysis, config: CoverageConfig) -> CoverageResult:
    """Toetst elke geconfigureerde dekkingclaim tegen de meldingen van de nulmeting."""
    analyses = [analyse.per_cfk[cfk] for cfk in analyse.meting.cfks]
    checks = [_assess_check(mapping, analyses, config) for mapping in config.check]
    return CoverageResult(dataset=analyse.meting.dataset_file, config=config, checks=checks)


def _assess_check(
    mapping: CheckMapping,
    analyses: list[ReportAnalysis],
    config: CoverageConfig,
) -> CheckCoverage:
    """Bepaalt bewijs, tegenbewijs en oordeel voor een enkele dekkingclaim."""
    evidence = [_gather(analysis, mapping, mapping.bewijs) for analysis in analyses]
    counter_evidence = [
        _gather(analysis, mapping, mapping.tegenbewijs)
        for analysis in analyses
        if mapping.tegenbewijs
    ]

    required = [item for item in evidence if item.required]
    if not required:
        verdict = Verdict.UNVERIFIABLE
    elif any(item.found for item in required):
        verdict = Verdict.TOUCHED
    else:
        verdict = Verdict.UNTOUCHED

    minimum = config.drempels.typeringsscore_minimum
    scores = [
        analysis.typing_gate.score
        for analysis in analyses
        if analysis.cfk in mapping.vereiste_cfk and analysis.typing_gate.score is not None
    ]
    # Zonder dataset is er geen score; dan valt er ook niets voor te behouden.
    typing_reliable = all(score >= minimum for score in scores)

    return CheckCoverage(
        mapping=mapping,
        evidence=evidence,
        counter_evidence=counter_evidence,
        verdict=verdict,
        typing_reliable=typing_reliable,
    )


def _gather(
    analysis: ReportAnalysis,
    mapping: CheckMapping,
    patterns: list[MessagePattern],
) -> CheckEvidence:
    """Telt de meldingen van een rapport die aan een van de patronen voldoen."""
    meldingen = analysis.report.findings
    geraakt = meldingen[_mask(meldingen, patterns)] if len(meldingen) else meldingen

    return CheckEvidence(
        cfk=analysis.cfk,
        required=analysis.cfk in mapping.vereiste_cfk,
        row_count=len(geraakt),
        object_count=len(set(geraakt["Focus node"])) if len(geraakt) else 0,
        shapes=sorted(set(geraakt["Source"])) if len(geraakt) else [],
    )


def _mask(meldingen: pd.DataFrame, patterns: list[MessagePattern]) -> pd.Series:
    """Bouwt een booleaans masker: waar als de regel aan minstens een patroon voldoet."""
    total = pd.Series(False, index=meldingen.index)
    for pattern in patterns:
        total |= _pattern_mask(meldingen, pattern)
    return total


def _pattern_mask(meldingen: pd.DataFrame, pattern: MessagePattern) -> pd.Series:
    """Bouwt het masker van een enkel patroon; lege lijsten filteren niet."""
    if pattern.vorm is not None:
        mask = meldingen["Source"] == pattern.vorm
    else:
        mask = meldingen["Source"].str.startswith(pattern.vorm_prefix)

    if pattern.objecttype:
        mask &= meldingen["Objecttype"].isin(pattern.objecttype)
    if pattern.ernst:
        mask &= meldingen["Severity"].isin(pattern.ernst)

    return mask
