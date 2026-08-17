"""Vergelijkt twee nulmetingen van dezelfde dataset voor trendbewaking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from nlriochecker.analysis import MetingAnalysis, ReportAnalysis
from nlriochecker.config import CoverageConfig
from nlriochecker.coverage import CoverageResult, assess_coverage
from nlriochecker.errors import ComparisonError

OBJECT_KEYS = ["Source", "Focus node"]


class ChangeStatus(StrEnum):
    """De status van een melding tussen twee meetmomenten."""

    RESOLVED = "opgelost"
    NEW = "nieuw"
    REMAINING = "gebleven"


@dataclass(frozen=True)
class CfkComparison:
    """De vergelijking van een conformiteitsklasse tussen twee meetmomenten."""

    cfk: str
    earlier: ReportAnalysis
    later: ReportAnalysis
    by_shape: pd.DataFrame
    by_object_type: pd.DataFrame
    object_changes: pd.DataFrame

    @property
    def total_delta(self) -> int:
        """Het verschil in aantal meldingen (negatief is een verbetering)."""
        return self.later.total_count - self.earlier.total_count

    @property
    def error_delta(self) -> int:
        """Het verschil in aantal fouten."""
        return self.later.error_count - self.earlier.error_count

    def status_counts(self) -> dict[str, int]:
        """Het aantal meldingen per statuscategorie."""
        if self.object_changes.empty:
            return {status.value: 0 for status in ChangeStatus}
        telling = self.object_changes["Status"].value_counts()
        return {status.value: int(telling.get(status.value, 0)) for status in ChangeStatus}


@dataclass(frozen=True)
class MetingComparison:
    """De volledige vergelijking van twee nulmetingen."""

    dataset_file: str
    earlier: MetingAnalysis
    later: MetingAnalysis
    per_cfk: list[CfkComparison]
    coverage_earlier: CoverageResult
    coverage_later: CoverageResult
    coverage_changes: pd.DataFrame

    @property
    def timestamps_out_of_order(self) -> bool:
        """Geeft aan of de latere meting niet daadwerkelijk later is."""
        return self.later.meting.latest <= self.earlier.meting.latest


def compare_metingen(
    earlier: MetingAnalysis,
    later: MetingAnalysis,
    config: CoverageConfig,
) -> MetingComparison:
    """Zet twee nulmetingen van dezelfde dataset naast elkaar."""
    if earlier.meting.dataset_file != later.meting.dataset_file:
        raise ComparisonError(
            f"De nulmetingen gaan over verschillende datasets: "
            f"{earlier.meting.dataset_file!r} tegenover {later.meting.dataset_file!r}."
        )

    gedeeld = [cfk for cfk in earlier.meting.cfks if cfk in later.meting.cfks]
    if not gedeeld:
        raise ComparisonError(
            f"De nulmetingen delen geen enkele conformiteitsklasse: "
            f"{earlier.meting.cfks} tegenover {later.meting.cfks}."
        )

    per_cfk = [_compare_cfk(earlier.per_cfk[cfk], later.per_cfk[cfk]) for cfk in gedeeld]
    dekking_eerder = assess_coverage(earlier, config)
    dekking_later = assess_coverage(later, config)

    return MetingComparison(
        dataset_file=earlier.meting.dataset_file,
        earlier=earlier,
        later=later,
        per_cfk=per_cfk,
        coverage_earlier=dekking_eerder,
        coverage_later=dekking_later,
        coverage_changes=_coverage_changes(dekking_eerder, dekking_later),
    )


def _compare_cfk(earlier: ReportAnalysis, later: ReportAnalysis) -> CfkComparison:
    """Vergelijkt twee analyses van dezelfde conformiteitsklasse."""
    return CfkComparison(
        cfk=earlier.cfk,
        earlier=earlier,
        later=later,
        by_shape=_delta(earlier.by_shape, later.by_shape, ["Source"]),
        by_object_type=_delta(earlier.by_object_type, later.by_object_type, ["Objecttype"]),
        object_changes=_object_changes(earlier, later),
    )


def _delta(earlier: pd.DataFrame, later: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Zet twee aggregaties naast elkaar met een verschilkolom."""
    kolommen = [*keys, "Meldingen"]
    links = earlier[kolommen] if not earlier.empty else pd.DataFrame(columns=kolommen)
    rechts = later[kolommen] if not later.empty else pd.DataFrame(columns=kolommen)

    samen = links.merge(rechts, on=keys, how="outer", suffixes=("_eerder", "_later"))
    samen = samen.fillna({"Meldingen_eerder": 0, "Meldingen_later": 0})
    samen["Eerder"] = samen.pop("Meldingen_eerder").astype("int64")
    samen["Later"] = samen.pop("Meldingen_later").astype("int64")
    samen["Verschil"] = samen["Later"] - samen["Eerder"]

    return samen.sort_values(
        ["Verschil", *keys], ascending=[True, *[True] * len(keys)]
    ).reset_index(drop=True)


def _object_changes(earlier: ReportAnalysis, later: ReportAnalysis) -> pd.DataFrame:
    """Bepaalt per melding op objectniveau of die is opgelost, nieuw is of blijft.

    De sleutel is de combinatie van vorm en focus node. Dat is een URI-fragment uit
    de dataset zelf, dus de koppeling is exact; het vervallen detailrapportformaat
    kon alleen op labels joinen.
    """
    eerder = _keys(earlier)
    later_keys = _keys(later)

    samen = eerder.merge(later_keys, on=OBJECT_KEYS, how="outer", indicator=True)
    status = samen.pop("_merge").map(
        {
            "left_only": ChangeStatus.RESOLVED.value,
            "right_only": ChangeStatus.NEW.value,
            "both": ChangeStatus.REMAINING.value,
        }
    )
    samen["Status"] = status.astype(str)
    return samen.sort_values(["Status", *OBJECT_KEYS]).reset_index(drop=True)


def _keys(analysis: ReportAnalysis) -> pd.DataFrame:
    """De unieke (vorm, focus node)-combinaties van een rapport."""
    meldingen = analysis.report.findings
    if meldingen.empty:
        return pd.DataFrame(columns=OBJECT_KEYS)
    return meldingen[OBJECT_KEYS].drop_duplicates().reset_index(drop=True)


def _coverage_changes(earlier: CoverageResult, later: CoverageResult) -> pd.DataFrame:
    """Zet de dekkingoordelen van beide meetmomenten naast elkaar."""
    later_op_id = {check.mapping.id: check for check in later.checks}

    rijen = []
    for check in earlier.checks:
        ander = later_op_id.get(check.mapping.id)
        rijen.append(
            {
                "Check": check.mapping.id,
                "Onderwerp": check.mapping.onderwerp,
                "Eerder": check.verdict.value,
                "Later": ander.verdict.value if ander else "",
                "Gewijzigd": ander is not None and ander.verdict is not check.verdict,
            }
        )
    return pd.DataFrame(rijen, columns=["Check", "Onderwerp", "Eerder", "Later", "Gewijzigd"])
