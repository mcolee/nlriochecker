"""Toetst per geschrapte check of de nulmeting het onderwerp in deze dataset raakt."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from gwswpijplijn.analysis import ReportAnalysis
from gwswpijplijn.config import CheckMapping, CoverageConfig, MessagePattern
from gwswpijplijn.pair import ReportPair


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
    weighted_count: int
    object_count: int
    aspects: list[str]

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


def assess_coverage(pair: ReportPair, config: CoverageConfig) -> CoverageResult:
    """Toetst elke geconfigureerde dekkingclaim tegen de meldingen van het paar."""
    analyses = [pair.mds, pair.hyd]
    checks = [_assess_check(mapping, analyses, config) for mapping in config.check]
    return CoverageResult(dataset=pair.dataset, config=config, checks=checks)


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
    typing_reliable = all(
        analysis.typing_gate.score >= minimum
        for analysis in analyses
        if analysis.report.cfk in mapping.vereiste_cfk
    )

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
    messages = analysis.report.messages
    matched = messages[_mask(messages, patterns)]
    named = matched[matched["Naam"].str.strip() != ""]

    return CheckEvidence(
        cfk=analysis.report.cfk,
        required=analysis.report.cfk in mapping.vereiste_cfk,
        row_count=len(matched),
        weighted_count=int(matched["Aantal"].sum()),
        object_count=len(named[["Type object", "Naam"]].drop_duplicates()),
        aspects=sorted(set(matched["Type aspect"])),
    )


def _mask(messages: pd.DataFrame, patterns: list[MessagePattern]) -> pd.Series:
    """Bouwt een booleaans masker: waar als de regel aan minstens een patroon voldoet."""
    total = pd.Series(False, index=messages.index)
    for pattern in patterns:
        total |= _pattern_mask(messages, pattern)
    return total


def _pattern_mask(messages: pd.DataFrame, pattern: MessagePattern) -> pd.Series:
    """Bouwt het masker van een enkel patroon; lege lijsten filteren niet."""
    if pattern.melding is not None:
        mask = messages["Type Melding"] == pattern.melding
    else:
        mask = messages["Type Melding"].str.startswith(pattern.melding_prefix)

    if pattern.aspect:
        mask &= messages["Type aspect"].isin(pattern.aspect)
    if pattern.objecttype:
        mask &= messages["Type object"].isin(pattern.objecttype)

    return mask
