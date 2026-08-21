"""Aggregaties over een SHACL-nulmeting, plus de typeringspoort."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from nlriochecker.dataset import GwswDataset
from nlriochecker.meting import Nulmeting
from nlriochecker.shaclrapport import ShaclReport

ERNST_FOUT = "Violation"
ERNST_WAARSCHUWING = "Warning"


@dataclass(frozen=True)
class TypingGate:
    """Kwaliteitsvoorwaarde: welke objecten zijn te globaal getypeerd.

    De SHACL-meting noemt de te globale *klassen*, niet de objecten. Met de dataset
    erbij worden de instanties opgezocht; zonder dataset blijft het bij de klassen
    en is er geen score te geven.

    `unassessable_classes` is de deelverzameling van `classes` die niet naar objecten
    in het domeinmodel te herleiden is: dat model kent alleen knopen en strengen, en
    een verbindingsklasse staat bovendien op de orientatie van een streng en niet op
    de streng zelf. Ze tellen niet mee in de score, en ze staan hier apart omdat het
    rapport ze moet noemen -- stilte over een klasse die niet beoordeeld is leest als
    "beoordeeld en niets gevonden".
    """

    classes: list[str]
    objects: list[str]
    total_objects: int
    resolved: bool
    unassessable_classes: list[str] = field(default_factory=list)

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

    Een verbindingsklasse is hier niet naar objecten te herleiden (zie
    `GwswDataset.is_connection_class`). Dat is geen vergissing van de gebruiker maar
    een meetuitkomst -- `Afvoerrelatie` is precies de vorm die een CFK te globaal
    kan noemen -- dus de klasse wordt onbeoordeelbaar genoemd en de run loopt door.

    Diezelfde behandeling krijgt elke klasse die op nul objecten uitkomt terwijl de
    graaf er wel instanties van draagt. Dat is niet het hypothetische geval maar het
    werkelijke: over de drie aangeleverde SHACL-rapporten samen noemt `CfkTypes_typ`
    drie klassen, en `Rioolstelsel` en `MechanischRioolstelsel` zijn er twee van. Die
    staan onder `Stelsel` en zijn dus knoop noch streng, dus `of_class()` geeft er stil
    `[]` op terug -- en zonder deze tak zou de poort er nul te globale objecten voor
    scoren zonder een woord, terwijl de dataset de stelsels wel bevat. Nul objecten bij
    nul instanties is iets anders: dan komt de klasse in deze dataset niet voor, en dat
    is een echte nul.
    """
    klassen = report.too_generic_classes
    if dataset is None:
        return TypingGate(classes=klassen, objects=[], total_objects=0, resolved=False)

    objecten: set[str] = set()
    onbeoordeelbaar: list[str] = []
    for klasse in klassen:
        if dataset.is_connection_class(klasse):
            onbeoordeelbaar.append(klasse)
            continue
        gevonden = dataset.of_class(klasse)
        if not gevonden and dataset.subjects_of_class(klasse):
            onbeoordeelbaar.append(klasse)
            continue
        objecten.update(gevonden)

    return TypingGate(
        classes=klassen,
        objects=sorted(objecten),
        total_objects=len(dataset.nodes) + len(dataset.conduits),
        resolved=True,
        unassessable_classes=onbeoordeelbaar,
    )
