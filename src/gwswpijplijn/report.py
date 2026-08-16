"""Inlezen van GWSW-nulmeting-detailrapporten (CSV, cp1252, puntkomma)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from gwswpijplijn.errors import ReportFormatError

ENCODING = "cp1252"
DELIMITER = ";"

COLUMNS = ["Aantal", "Type Melding", "Type object", "Naam", "Type aspect", "Opmerking"]

TITLE_PATTERN = re.compile(
    r"Detailrapport GWSW-Nulmeting van dataset (?P<dataset>.+?) "
    r"\(Toetsing aan CFK: (?P<cfk>\w+)\) "
    r"\(dd (?P<timestamp>[0-9T:\-.]+)\)"
)


@dataclass(frozen=True)
class DetailReport:
    """Een ingelezen detailrapport: metadata uit de titelregel plus de meldingen."""

    dataset: str
    cfk: str
    timestamp: datetime
    source_file: Path
    messages: pd.DataFrame


def read_detail_report(path: Path) -> DetailReport:
    """Leest een detailrapport-CSV en geeft het terug als `DetailReport`.

    Regel 1 is de titelregel met datasetnaam, conformiteitsklasse en tijdstempel;
    regel 2 is de kolomkop. Wijkt het bestand af, dan volgt een `ReportFormatError`.
    """
    path = Path(path)
    dataset, cfk, timestamp = _read_title_line(path)
    messages = _read_messages(path)
    return DetailReport(
        dataset=dataset,
        cfk=cfk,
        timestamp=timestamp,
        source_file=path,
        messages=messages,
    )


def _read_title_line(path: Path) -> tuple[str, str, datetime]:
    """Leest de eerste regel en haalt daar datasetnaam, CFK en tijdstempel uit."""
    with path.open(encoding=ENCODING, newline="") as handle:
        title_line = handle.readline().strip()

    if not title_line:
        raise ReportFormatError(f"{path}: het bestand is leeg; een titelregel wordt verwacht.")

    match = TITLE_PATTERN.search(title_line)
    if match is None:
        raise ReportFormatError(
            f"{path}: de titelregel is niet herkend als GWSW-nulmeting-detailrapport. "
            f"Aangetroffen regel: {title_line!r}"
        )

    try:
        timestamp = datetime.fromisoformat(match["timestamp"])
    except ValueError as error:
        raise ReportFormatError(
            f"{path}: tijdstempel {match['timestamp']!r} in de titelregel is geen geldige "
            f"ISO-datum."
        ) from error

    return match["dataset"].strip(), match["cfk"], timestamp


def _read_messages(path: Path) -> pd.DataFrame:
    """Leest de meldingtabel vanaf regel 2 in als DataFrame met een integer `Aantal`."""
    messages = pd.read_csv(
        path,
        sep=DELIMITER,
        encoding=ENCODING,
        skiprows=1,
        dtype=str,
        keep_default_na=False,
    )

    if list(messages.columns) != COLUMNS:
        raise ReportFormatError(
            f"{path}: onverwachte kolommen. Verwacht {COLUMNS}, gevonden {list(messages.columns)}."
        )

    counts = pd.to_numeric(messages["Aantal"], errors="coerce")
    if counts.isna().any():
        first = int(counts.isna().idxmax()) + 3
        raise ReportFormatError(
            f"{path}: kolom 'Aantal' bevat een waarde die geen geheel getal is (regel {first})."
        )
    messages["Aantal"] = counts.astype("int64")

    return messages
