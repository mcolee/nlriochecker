"""Inlezen van GWSW-nulmeting-detailrapporten (CSV, cp1252, puntkomma)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from gwswpijplijn.fouten import RapportFormaatFout

ENCODING = "cp1252"
SCHEIDINGSTEKEN = ";"

KOLOMMEN = ["Aantal", "Type Melding", "Type object", "Naam", "Type aspect", "Opmerking"]

TITEL_PATROON = re.compile(
    r"Detailrapport GWSW-Nulmeting van dataset (?P<dataset>.+?) "
    r"\(Toetsing aan CFK: (?P<cfk>\w+)\) "
    r"\(dd (?P<tijdstempel>[0-9T:\-.]+)\)"
)


@dataclass(frozen=True)
class Detailrapport:
    """Een ingelezen detailrapport: metadata uit de titelregel plus de meldingen."""

    dataset: str
    cfk: str
    tijdstempel: datetime
    bronbestand: Path
    meldingen: pd.DataFrame


def lees_detailrapport(pad: Path) -> Detailrapport:
    """Leest een detailrapport-CSV en geeft het terug als `Detailrapport`.

    Regel 1 is de titelregel met datasetnaam, conformiteitsklasse en tijdstempel;
    regel 2 is de kolomkop. Wijkt het bestand af, dan volgt een `RapportFormaatFout`.
    """
    pad = Path(pad)
    dataset, cfk, tijdstempel = _lees_titelregel(pad)
    meldingen = _lees_meldingen(pad)
    return Detailrapport(
        dataset=dataset,
        cfk=cfk,
        tijdstempel=tijdstempel,
        bronbestand=pad,
        meldingen=meldingen,
    )


def _lees_titelregel(pad: Path) -> tuple[str, str, datetime]:
    """Leest de eerste regel en haalt daar datasetnaam, CFK en tijdstempel uit."""
    with pad.open(encoding=ENCODING, newline="") as bestand:
        titelregel = bestand.readline().strip()

    if not titelregel:
        raise RapportFormaatFout(f"{pad}: het bestand is leeg; een titelregel wordt verwacht.")

    match = TITEL_PATROON.search(titelregel)
    if match is None:
        raise RapportFormaatFout(
            f"{pad}: de titelregel is niet herkend als GWSW-nulmeting-detailrapport. "
            f"Aangetroffen regel: {titelregel!r}"
        )

    try:
        tijdstempel = datetime.fromisoformat(match["tijdstempel"])
    except ValueError as fout:
        raise RapportFormaatFout(
            f"{pad}: tijdstempel {match['tijdstempel']!r} in de titelregel is geen geldige "
            f"ISO-datum."
        ) from fout

    return match["dataset"].strip(), match["cfk"], tijdstempel


def _lees_meldingen(pad: Path) -> pd.DataFrame:
    """Leest de meldingtabel vanaf regel 2 in als DataFrame met een integer `Aantal`."""
    meldingen = pd.read_csv(
        pad,
        sep=SCHEIDINGSTEKEN,
        encoding=ENCODING,
        skiprows=1,
        dtype=str,
        keep_default_na=False,
    )

    if list(meldingen.columns) != KOLOMMEN:
        raise RapportFormaatFout(
            f"{pad}: onverwachte kolommen. Verwacht {KOLOMMEN}, gevonden {list(meldingen.columns)}."
        )

    aantal = pd.to_numeric(meldingen["Aantal"], errors="coerce")
    if aantal.isna().any():
        eerste = int(aantal.isna().idxmax()) + 3
        raise RapportFormaatFout(
            f"{pad}: kolom 'Aantal' bevat een waarde die geen geheel getal is (regel {eerste})."
        )
    meldingen["Aantal"] = aantal.astype("int64")

    return meldingen
