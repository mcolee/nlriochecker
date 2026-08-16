"""Aggregaties over de meldingen van een detailrapport, plus de typeringspoort."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gwswpijplijn.report import DetailReport

MESSAGE_TOO_GENERIC_PREFIX = "Objecttype te globaal"


@dataclass(frozen=True)
class TypingGate:
    """Kwaliteitsvoorwaarde: hoeveel objecten zijn betrouwbaar genoeg getypeerd.

    De score is een ondergrens: het detailrapport bevat alleen objecten met
    minstens een melding, dus objecten zonder meldingen ontbreken in de noemer.
    """

    too_generic_count: int
    named_object_count: int
    score: float
    objects: pd.DataFrame


@dataclass(frozen=True)
class ReportAnalysis:
    """Alle afgeleide cijfers van een enkel detailrapport."""

    report: DetailReport
    total_count: int
    by_message_type: pd.DataFrame
    by_object_type: pd.DataFrame
    by_message_and_object_type: pd.DataFrame
    typing_gate: TypingGate


def analyze(report: DetailReport) -> ReportAnalysis:
    """Berekent de gewogen aggregaties en de typeringspoort voor een detailrapport."""
    messages = report.messages
    return ReportAnalysis(
        report=report,
        total_count=int(messages["Aantal"].sum()),
        by_message_type=_aggregate(messages, ["Type Melding"]),
        by_object_type=_aggregate(messages, ["Type object"]),
        by_message_and_object_type=_aggregate(messages, ["Type Melding", "Type object"]),
        typing_gate=determine_typing_gate(messages),
    )


def _aggregate(messages: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Telt `Aantal` en het aantal regels per sleutelcombinatie, aflopend gesorteerd."""
    if messages.empty:
        return pd.DataFrame(columns=[*keys, "Aantal", "Regels"])

    summary = (
        messages.groupby(keys, dropna=False)["Aantal"]
        .agg(Aantal="sum", Regels="size")
        .reset_index()
    )
    return summary.sort_values(
        ["Aantal", *keys], ascending=[False, *[True] * len(keys)]
    ).reset_index(drop=True)


def determine_typing_gate(messages: pd.DataFrame) -> TypingGate:
    """Bepaalt hoeveel benoemde objecten een melding 'Objecttype te globaal' hebben.

    Teller en noemer werken op unieke (Type object, Naam)-paren, zodat een object
    met meerdere meldingen niet meermaals meetelt.
    """
    named = messages[messages["Naam"].str.strip() != ""]
    all_objects = named[["Type object", "Naam"]].drop_duplicates()

    too_generic = named[named["Type Melding"].str.startswith(MESSAGE_TOO_GENERIC_PREFIX)]
    too_generic_objects = (
        too_generic[["Type object", "Naam"]]
        .drop_duplicates()
        .sort_values(["Type object", "Naam"])
        .reset_index(drop=True)
    )

    named_count = len(all_objects)
    too_generic_count = len(too_generic_objects)
    if named_count == 0:
        score = 100.0
    else:
        score = 100.0 * (named_count - too_generic_count) / named_count

    return TypingGate(
        too_generic_count=too_generic_count,
        named_object_count=named_count,
        score=score,
        objects=too_generic_objects,
    )
