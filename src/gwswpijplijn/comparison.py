"""Vergelijkt twee nulmetingen van dezelfde dataset voor trendbewaking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from gwswpijplijn.analysis import ReportAnalysis
from gwswpijplijn.config import CoverageConfig
from gwswpijplijn.coverage import CoverageResult, assess_coverage
from gwswpijplijn.errors import ComparisonError
from gwswpijplijn.pair import ReportPair

OBJECT_KEYS = ["Type Melding", "Type object", "Naam"]


class ChangeStatus(StrEnum):
    """De status van een melding op objectniveau tussen twee meetmomenten."""

    RESOLVED = "opgelost"
    NEW = "nieuw"
    REMAINING = "gebleven"


@dataclass(frozen=True)
class CfkComparison:
    """De vergelijking van een enkele conformiteitsklasse tussen twee meetmomenten."""

    cfk: str
    earlier: ReportAnalysis
    later: ReportAnalysis
    by_message_type: pd.DataFrame
    by_object_type: pd.DataFrame
    object_changes: pd.DataFrame

    @property
    def total_delta(self) -> int:
        """Het verschil in gewogen totaal (negatief is een verbetering)."""
        return self.later.total_count - self.earlier.total_count

    @property
    def typing_score_delta(self) -> float:
        """Het verschil in typeringsscore (positief is een verbetering)."""
        return self.later.typing_gate.score - self.earlier.typing_gate.score

    def status_counts(self) -> dict[str, int]:
        """Het aantal meldingen per statuscategorie op objectniveau."""
        counts = self.object_changes["Status"].value_counts()
        return {status.value: int(counts.get(status.value, 0)) for status in ChangeStatus}


@dataclass(frozen=True)
class PairComparison:
    """De volledige vergelijking van twee nulmetingen van dezelfde dataset."""

    dataset: str
    earlier: ReportPair
    later: ReportPair
    per_cfk: list[CfkComparison]
    coverage_earlier: CoverageResult
    coverage_later: CoverageResult
    coverage_changes: pd.DataFrame

    @property
    def timestamps_out_of_order(self) -> bool:
        """Geeft aan of het latere paar niet daadwerkelijk later getoetst is."""
        return _latest(self.later) <= _latest(self.earlier)


def compare_pairs(
    earlier: ReportPair,
    later: ReportPair,
    config: CoverageConfig,
) -> PairComparison:
    """Zet twee nulmetingen van dezelfde dataset naast elkaar.

    Een verschil in datasetnaam is een harde fout; gelijke of omgekeerde
    tijdstempels zijn een waarschuwing in het rapport, zodat een paar ook met
    zichzelf vergeleken kan worden.
    """
    if earlier.dataset != later.dataset:
        raise ComparisonError(
            f"De nulmetingen gaan over verschillende datasets: {earlier.dataset!r} "
            f"tegenover {later.dataset!r}. Trendbewaking vraagt dezelfde dataset."
        )

    per_cfk = [
        _compare_cfk(earlier.mds, later.mds),
        _compare_cfk(earlier.hyd, later.hyd),
    ]
    coverage_earlier = assess_coverage(earlier, config)
    coverage_later = assess_coverage(later, config)

    return PairComparison(
        dataset=earlier.dataset,
        earlier=earlier,
        later=later,
        per_cfk=per_cfk,
        coverage_earlier=coverage_earlier,
        coverage_later=coverage_later,
        coverage_changes=_coverage_changes(coverage_earlier, coverage_later),
    )


def _latest(pair: ReportPair):
    """Het laatste toetsmoment van een paar."""
    return max(pair.mds.report.timestamp, pair.hyd.report.timestamp)


def _compare_cfk(earlier: ReportAnalysis, later: ReportAnalysis) -> CfkComparison:
    """Vergelijkt twee analyses van dezelfde conformiteitsklasse."""
    if earlier.report.cfk != later.report.cfk:
        raise ComparisonError(
            f"De conformiteitsklassen komen niet overeen: {earlier.report.cfk!r} "
            f"tegenover {later.report.cfk!r}."
        )

    return CfkComparison(
        cfk=earlier.report.cfk,
        earlier=earlier,
        later=later,
        by_message_type=_delta(earlier.by_message_type, later.by_message_type, ["Type Melding"]),
        by_object_type=_delta(earlier.by_object_type, later.by_object_type, ["Type object"]),
        object_changes=_object_changes(earlier, later),
    )


def _delta(earlier: pd.DataFrame, later: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Zet twee aggregaties naast elkaar met een verschilkolom."""
    samen = earlier[[*keys, "Aantal"]].merge(
        later[[*keys, "Aantal"]],
        on=keys,
        how="outer",
        suffixes=("_eerder", "_later"),
    )
    samen = samen.fillna({"Aantal_eerder": 0, "Aantal_later": 0})
    samen["Eerder"] = samen.pop("Aantal_eerder").astype("int64")
    samen["Later"] = samen.pop("Aantal_later").astype("int64")
    samen["Verschil"] = samen["Later"] - samen["Eerder"]

    return samen.sort_values(
        ["Verschil", *keys], ascending=[True, *[True] * len(keys)]
    ).reset_index(drop=True)


def _object_changes(earlier: ReportAnalysis, later: ReportAnalysis) -> pd.DataFrame:
    """Bepaalt per benoemde melding of die is opgelost, nieuw is of blijft staan."""
    eerder = _named_keys(earlier)
    later_keys = _named_keys(later)

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


def _named_keys(analysis: ReportAnalysis) -> pd.DataFrame:
    """De unieke (meldingtype, objecttype, naam)-combinaties met een gevulde naam."""
    messages = analysis.report.messages
    named = messages[messages["Naam"].str.strip() != ""]
    return named[OBJECT_KEYS].drop_duplicates().reset_index(drop=True)


def _coverage_changes(earlier: CoverageResult, later: CoverageResult) -> pd.DataFrame:
    """Zet de dekkingoordelen van beide meetmomenten naast elkaar."""
    oordelen_later = {check.mapping.id: check for check in later.checks}

    rijen = []
    for check in earlier.checks:
        ander = oordelen_later.get(check.mapping.id)
        rijen.append(
            {
                "Check": check.mapping.id,
                "Onderwerp": check.mapping.onderwerp,
                "Eerder": check.verdict.value,
                "Later": ander.verdict.value if ander else "",
                "Gewijzigd": bool(ander) and ander.verdict is not check.verdict,
            }
        )
    return pd.DataFrame(rijen, columns=["Check", "Onderwerp", "Eerder", "Later", "Gewijzigd"])
