"""Toetst per geschrapte check of de nulmeting het onderwerp in deze dataset raakt.

Naast dat oordeel per check bewaakt deze module of de dekkingclaims zelf nog
geldig zijn. De schrapronde rust op twee voorwaarden uit het checkregister: de
dataset is aan alle vereiste conformiteitsklassen getoetst, en de typering is op
orde. Daar komt in de praktijk een derde bij: de dekkingmapping moet nog bij de
registerversie passen waarop de schrapronde is geverifieerd. Loopt een van die
drie stuk, dan is de dekking vervallen en zijn de geschrapte checks onbewaakt --
en omdat ze niet in de engine zitten, kijkt dan niemand er meer naar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import pandas as pd

from gwswpijplijn.analysis import MetingAnalysis, ReportAnalysis
from gwswpijplijn.config import CheckMapping, CoverageConfig, MessagePattern
from gwswpijplijn.errors import CoverageError
from gwswpijplijn.register import Register


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
class ShapeDiscrepancy:
    """Een bewijspatroon dat niet in alle vereiste CFK's meldingen oplevert.

    Alle CFK's toetsen hetzelfde RDF-bestand. Vuurt een vorm in de ene CFK wel en
    in de andere niet, dan kan dat niet aan schone data liggen: de vormverzameling
    van die CFK's verschilt. Een dekkingclaim van de vorm "beide CFK's" rust dan in
    werkelijkheid op een deel ervan. Nul meldingen in *alle* CFK's zegt niets --
    dat kan ook schone data zijn -- en telt hier dus niet mee.
    """

    check_id: str
    patroon: str
    met_meldingen: list[str]
    zonder_meldingen: list[str]


@dataclass(frozen=True)
class RegisterCheck:
    """De vergelijking tussen de dekkingmapping en het checkregister.

    De mapping noteert op welke registerversie de schrapronde geverifieerd is. Gaat
    het register vooruit of verschuift de lijst geschrapte checks, dan claimt de
    mapping een dekking die niemand meer getoetst heeft.
    """

    register: Path | None
    register_versie: str
    config_versie: str
    zonder_mapping: list[str] = field(default_factory=list)
    zonder_registerrij: list[str] = field(default_factory=list)

    @property
    def uitgevoerd(self) -> bool:
        """Geeft aan of er een register beschikbaar was om tegen te vergelijken."""
        return self.register is not None

    @property
    def versie_klopt(self) -> bool:
        """Geeft aan of mapping en register dezelfde versie noemen."""
        return self.register_versie == self.config_versie

    @property
    def klopt(self) -> bool:
        """Geeft aan of mapping en register elkaar volledig dekken."""
        return self.versie_klopt and not self.zonder_mapping and not self.zonder_registerrij

    def toelichting(self) -> list[str]:
        """De afwijkingen als leesbare regels; leeg als alles klopt."""
        regels: list[str] = []
        if not self.versie_klopt:
            regels.append(
                f"de dekkingmapping is geverifieerd op checkregister {self.config_versie}, "
                f"maar het register is versie {self.register_versie}"
            )
        if self.zonder_mapping:
            regels.append(
                "geschrapt in het register maar zonder dekkingmapping: "
                + ", ".join(self.zonder_mapping)
            )
        if self.zonder_registerrij:
            regels.append(
                "dekkingmapping voor een check die niet (meer) geschrapt is: "
                + ", ".join(self.zonder_registerrij)
            )
        return regels


@dataclass(frozen=True)
class CoverageResult:
    """De dekkinganalyse over een volledig rapportenpaar."""

    dataset: str
    config: CoverageConfig
    checks: list[CheckCoverage]
    discrepanties: list[ShapeDiscrepancy] = field(default_factory=list)
    registercontrole: RegisterCheck | None = None

    @property
    def untouched(self) -> list[CheckCoverage]:
        """De checks waarvan het onderwerp in deze dataset niet geraakt wordt."""
        return [check for check in self.checks if check.verdict is not Verdict.TOUCHED]

    @property
    def vervallen(self) -> list[str]:
        """De check-ID's waarvan de dekking niet langer aantoonbaar is.

        Dat zijn de checks waarvan het onderwerp niet geraakt wordt, plus die met
        een typeringsvoorbehoud. Ze staan niet in de engine en worden dus door
        niets meer bewaakt; dat hoort in het rapport te staan.
        """
        return sorted(
            check.mapping.id
            for check in self.checks
            if check.verdict is not Verdict.TOUCHED or not check.typing_reliable
        )


def assess_coverage(
    analyse: MetingAnalysis,
    config: CoverageConfig,
    register: Register | None = None,
) -> CoverageResult:
    """Toetst elke geconfigureerde dekkingclaim tegen de meldingen van de nulmeting."""
    analyses = [analyse.per_cfk[cfk] for cfk in analyse.meting.cfks]
    checks = [_assess_check(mapping, analyses, config) for mapping in config.check]
    discrepanties = [
        afwijking for mapping in config.check for afwijking in _discrepanties(mapping, analyses)
    ]
    return CoverageResult(
        dataset=analyse.meting.dataset_file,
        config=config,
        checks=checks,
        discrepanties=discrepanties,
        registercontrole=verify_register(config, register) if register is not None else None,
    )


def verify_register(
    config: CoverageConfig,
    register: Register | None,
    eisen: bool = False,
) -> RegisterCheck:
    """Vergelijkt de dekkingmapping met de tabel Geschrapte checks van het register.

    Zonder register is er niets te vergelijken; de controle meldt dan dat ze niet
    is uitgevoerd in plaats van te doen alsof alles klopt. Met `eisen=True` wordt
    een afwijking een pijplijnfout: de dekkingclaims zijn dan niet te vertrouwen en
    doorgaan zou een dekking rapporteren die niemand geverifieerd heeft.
    """
    mapping_ids = {item.id for item in config.check}
    if register is None:
        controle = RegisterCheck(
            register=None,
            register_versie=config.checkregister_versie,
            config_versie=config.checkregister_versie,
        )
    else:
        geschrapt = {entry.check_id for entry in register.entries if entry.dropped}
        controle = RegisterCheck(
            register=register.source,
            register_versie=register.version,
            config_versie=config.checkregister_versie,
            zonder_mapping=sorted(geschrapt - mapping_ids),
            zonder_registerrij=sorted(mapping_ids - geschrapt),
        )

    if eisen and controle.uitgevoerd and not controle.klopt:
        regels = "\n  - ".join(controle.toelichting())
        raise CoverageError(
            f"De dekkingmapping past niet meer bij {controle.register}:\n  - {regels}\n"
            "De dekking van de geschrapte checks is daarmee vervallen; werk de mapping "
            "bij of voer de schrapronde opnieuw uit."
        )
    return controle


def _discrepanties(mapping: CheckMapping, analyses: list[ReportAnalysis]) -> list[ShapeDiscrepancy]:
    """Zoekt per bewijspatroon de CFK's waarin het wel en niet meldingen oplevert."""
    vereist = [analysis for analysis in analyses if analysis.cfk in mapping.vereiste_cfk]
    if len(vereist) < 2:
        return []

    gevonden: list[ShapeDiscrepancy] = []
    for pattern in mapping.bewijs:
        met = [analysis.cfk for analysis in vereist if _telt(analysis, pattern)]
        zonder = [analysis.cfk for analysis in vereist if not _telt(analysis, pattern)]
        if met and zonder:
            gevonden.append(
                ShapeDiscrepancy(
                    check_id=mapping.id,
                    patroon=_patroonnaam(pattern),
                    met_meldingen=sorted(met),
                    zonder_meldingen=sorted(zonder),
                )
            )
    return gevonden


def _telt(analysis: ReportAnalysis, pattern: MessagePattern) -> bool:
    """Geeft aan of dit patroon in dit rapport minstens een melding oplevert."""
    meldingen = analysis.report.findings
    if meldingen.empty:
        return False
    return bool(_pattern_mask(meldingen, pattern).any())


def _patroonnaam(pattern: MessagePattern) -> str:
    """De leesbare naam van een meldingpatroon."""
    return pattern.vorm if pattern.vorm is not None else f"{pattern.vorm_prefix}*"


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
