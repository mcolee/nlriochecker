"""Aggregaties over een SHACL-nulmeting, plus de typeringspoort."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gwswpijplijn.dataset import GwswDataset
from gwswpijplijn.meting import Nulmeting
from gwswpijplijn.shaclrapport import ShaclReport

ERNST_FOUT = "Violation"
ERNST_WAARSCHUWING = "Warning"


@dataclass(frozen=True)
class TypingGate:
    """Kwaliteitsvoorwaarde: welke objecten zijn te globaal getypeerd.

    De SHACL-meting noemt de te globale *klassen*, niet de objecten. Met de dataset
    erbij worden de instanties opgezocht; zonder dataset blijft het bij de klassen
    en is er geen score te geven.
    """

    classes: list[str]
    objects: list[str]
    total_objects: int
    resolved: bool

    @property
    def too_generic_count(self) -> int:
        """Het aantal te globaal getypeerde objecten."""
        return len(self.objects)

    @property
    def score(self) -> float | None:
        """Het aandeel betrouwbaar getypeerde objecten, of None zonder dataset."""
        if not self.resolved or self.total_objects == 0:
            return None
        return 100.0 * (self.total_objects - len(self.objects)) / self.total_objects


@dataclass(frozen=True)
class ReportAnalysis:
    """Alle afgeleide cijfers van een enkel SHACL-rapport."""

    report: ShaclReport
    total_count: int
    error_count: int
    warning_count: int
    by_shape: pd.DataFrame
    by_object_type: pd.DataFrame
    by_shape_and_object_type: pd.DataFrame
    typing_gate: TypingGate

    @property
    def cfk(self) -> str:
        """De conformiteitsklasse van dit rapport."""
        return self.report.cfk


@dataclass(frozen=True)
class MetingAnalysis:
    """De analyse van een volledige nulmeting."""

    meting: Nulmeting
    per_cfk: dict[str, ReportAnalysis]

    @property
    def total_count(self) -> int:
        """Alle meldingen over alle conformiteitsklassen."""
        return sum(analyse.total_count for analyse in self.per_cfk.values())


def analyze(nulmeting: Nulmeting, dataset: GwswDataset | None = None) -> MetingAnalysis:
    """Berekent de aggregaties en de typeringspoort per conformiteitsklasse."""
    return MetingAnalysis(
        meting=nulmeting,
        per_cfk={cfk: analyze_report(nulmeting.report(cfk), dataset) for cfk in nulmeting.cfks},
    )


def analyze_report(report: ShaclReport, dataset: GwswDataset | None = None) -> ReportAnalysis:
    """Berekent de aggregaties en de typeringspoort voor een enkel rapport."""
    meldingen = report.findings
    return ReportAnalysis(
        report=report,
        total_count=len(meldingen),
        error_count=int((meldingen["Severity"] == ERNST_FOUT).sum()) if len(meldingen) else 0,
        warning_count=(
            int((meldingen["Severity"] == ERNST_WAARSCHUWING).sum()) if len(meldingen) else 0
        ),
        by_shape=_aggregeer(meldingen, ["Source"]),
        by_object_type=_aggregeer(meldingen, ["Objecttype"]),
        by_shape_and_object_type=_aggregeer(meldingen, ["Source", "Objecttype"]),
        typing_gate=bepaal_typeringspoort(report, dataset),
    )


def _aggregeer(meldingen: pd.DataFrame, sleutels: list[str]) -> pd.DataFrame:
    """Telt de meldingen per sleutelcombinatie, aflopend gesorteerd."""
    if meldingen.empty:
        return pd.DataFrame(columns=[*sleutels, "Meldingen", "Fouten", "Waarschuwingen"])

    samenvatting = (
        meldingen.assign(
            Fout=(meldingen["Severity"] == ERNST_FOUT).astype("int64"),
            Waarschuwing=(meldingen["Severity"] == ERNST_WAARSCHUWING).astype("int64"),
        )
        .groupby(sleutels, dropna=False)
        .agg(
            Meldingen=("Severity", "size"),
            Fouten=("Fout", "sum"),
            Waarschuwingen=("Waarschuwing", "sum"),
        )
        .reset_index()
    )
    return samenvatting.sort_values(
        ["Meldingen", *sleutels], ascending=[False, *[True] * len(sleutels)]
    ).reset_index(drop=True)


def bepaal_typeringspoort(report: ShaclReport, dataset: GwswDataset | None = None) -> TypingGate:
    """Bepaalt welke objecten te globaal getypeerd zijn.

    De klassen komen uit de CfkTypes_typ-meldingen; de instanties uit de dataset.
    Zonder dataset zijn de objecten niet te bepalen en blijft de score leeg, in
    plaats van een getal te suggereren dat er niet is.
    """
    klassen = report.too_generic_classes
    if dataset is None:
        return TypingGate(classes=klassen, objects=[], total_objects=0, resolved=False)

    objecten: set[str] = set()
    for klasse in klassen:
        objecten.update(dataset.of_class(klasse))

    return TypingGate(
        classes=klassen,
        objects=sorted(objecten),
        total_objects=len(dataset.nodes) + len(dataset.conduits),
        resolved=True,
    )
