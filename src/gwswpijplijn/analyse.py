"""Aggregaties over de meldingen van een detailrapport, plus de typeringspoort."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from gwswpijplijn.rapport import Detailrapport

MELDING_TE_GLOBAAL_PREFIX = "Objecttype te globaal"


@dataclass(frozen=True)
class Typeringspoort:
    """Kwaliteitsvoorwaarde: hoeveel objecten zijn betrouwbaar genoeg getypeerd.

    De score is een ondergrens: het detailrapport bevat alleen objecten met
    minstens een melding, dus objecten zonder meldingen ontbreken in de noemer.
    """

    aantal_te_globaal: int
    aantal_benoemde_objecten: int
    score: float
    objecten: pd.DataFrame


@dataclass(frozen=True)
class RapportAnalyse:
    """Alle afgeleide cijfers van een enkel detailrapport."""

    rapport: Detailrapport
    totaal_aantal: int
    per_melding: pd.DataFrame
    per_objecttype: pd.DataFrame
    per_melding_objecttype: pd.DataFrame
    typeringspoort: Typeringspoort


def analyseer(rapport: Detailrapport) -> RapportAnalyse:
    """Berekent de gewogen aggregaties en de typeringspoort voor een detailrapport."""
    meldingen = rapport.meldingen
    return RapportAnalyse(
        rapport=rapport,
        totaal_aantal=int(meldingen["Aantal"].sum()),
        per_melding=_aggregeer(meldingen, ["Type Melding"]),
        per_objecttype=_aggregeer(meldingen, ["Type object"]),
        per_melding_objecttype=_aggregeer(meldingen, ["Type Melding", "Type object"]),
        typeringspoort=bepaal_typeringspoort(meldingen),
    )


def _aggregeer(meldingen: pd.DataFrame, sleutels: list[str]) -> pd.DataFrame:
    """Telt `Aantal` en het aantal regels per sleutelcombinatie, aflopend gesorteerd."""
    if meldingen.empty:
        return pd.DataFrame(columns=[*sleutels, "Aantal", "Regels"])

    samenvatting = (
        meldingen.groupby(sleutels, dropna=False)["Aantal"]
        .agg(Aantal="sum", Regels="size")
        .reset_index()
    )
    return samenvatting.sort_values(
        ["Aantal", *sleutels], ascending=[False, *[True] * len(sleutels)]
    ).reset_index(drop=True)


def bepaal_typeringspoort(meldingen: pd.DataFrame) -> Typeringspoort:
    """Bepaalt hoeveel benoemde objecten een melding 'Objecttype te globaal' hebben.

    Teller en noemer werken op unieke (Type object, Naam)-paren, zodat een object
    met meerdere meldingen niet meermaals meetelt.
    """
    benoemd = meldingen[meldingen["Naam"].str.strip() != ""]
    alle_objecten = benoemd[["Type object", "Naam"]].drop_duplicates()

    te_globaal = benoemd[benoemd["Type Melding"].str.startswith(MELDING_TE_GLOBAAL_PREFIX)]
    objecten_te_globaal = (
        te_globaal[["Type object", "Naam"]]
        .drop_duplicates()
        .sort_values(["Type object", "Naam"])
        .reset_index(drop=True)
    )

    aantal_benoemd = len(alle_objecten)
    aantal_te_globaal = len(objecten_te_globaal)
    if aantal_benoemd == 0:
        score = 100.0
    else:
        score = 100.0 * (aantal_benoemd - aantal_te_globaal) / aantal_benoemd

    return Typeringspoort(
        aantal_te_globaal=aantal_te_globaal,
        aantal_benoemde_objecten=aantal_benoemd,
        score=score,
        objecten=objecten_te_globaal,
    )
