"""Gedeelde opmaakhulp voor de Markdown-rapporten."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# De nulmetingtabellen tonen de grootste posten; de volledige lijst staat in de CSV.
TOP_N = 15


def prepare(output_dir: Path) -> Path:
    """Maakt de uitvoermap aan en geeft hem terug."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def title(label: str, frame: pd.DataFrame) -> str:
    """Maakt een tabeltitel die alleen 'top N' vermeldt als er daadwerkelijk is afgekapt."""
    if len(frame) > TOP_N:
        return f"{label} (top {TOP_N} van {len(frame)})"
    return f"{label} ({len(frame)})"


def table(frame: pd.DataFrame, kop: str) -> list[str]:
    """Rendert een DataFrame als Markdown-tabel met een vetgedrukte titelregel."""
    lines = [f"**{kop}**", ""]
    if frame.empty:
        return [*lines, "_geen_"]

    columns = list(frame.columns)
    alignment = ["---:" if is_numeric(frame[column]) else "---" for column in columns]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(alignment) + " |")
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def is_numeric(column: pd.Series) -> bool:
    """Geeft aan of een kolom numeriek is en dus rechts uitgelijnd hoort te worden.

    Booleans tellen niet mee: die lezen als tekst, niet als getal.
    """
    return pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column)
