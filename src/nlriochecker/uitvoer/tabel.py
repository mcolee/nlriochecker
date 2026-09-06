"""Gedeelde opmaakhulp voor de Markdown-rapporten."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nlriochecker.errors import OpdrachtError

# De nulmetingtabellen tonen de grootste posten; de volledige lijst staat in de CSV.
TOP_N = 15


def prepare(output_dir: Path) -> Path:
    """Maakt de uitvoermap aan en geeft hem terug.

    Een onaanmaakbare map (een ontbrekend bovenliggend pad zoals `/proc/...`, geen
    schrijfrecht) is een opdrachtfout en geen kale `OSError`: zonder deze vertaling
    valt een schrijver hier met een traceback in plaats van de nette `Fout: ...`-regel
    die de CLI voor elke andere invoerfout laat zien (issue #153).
    """
    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OpdrachtError(f"uitvoermap {output_dir} is niet aan te maken: {error}") from error
    return output_dir


def title(label: str, frame: pd.DataFrame) -> str:
    """Maakt een tabeltitel die alleen 'top N' vermeldt als er daadwerkelijk is afgekapt."""
    if len(frame) > TOP_N:
        return f"{label} (top {TOP_N} van {len(frame)})"
    return f"{label} ({len(frame)})"


def _cel(value: object) -> str:
    """Maakt een waarde veilig voor één Markdown-tabelcel.

    Drie tekens breken de tabel of de gerenderde uitvoer: `|` sluit een cel af, een
    regelovergang breekt de rij in tweeën, en `<` opent een HTML-tag. Een vrij
    tekstlabel als `1 | zie ook <b>"x"</b>` maakte er anders vier cellen in een
    driekolomstabel van, en een label met een regelovergang splitste de rij. CSV, JSON
    en de popup dragen de rauwe waarde; alleen de Markdown-view escapet. Zie issue #156.
    """
    return (
        str(value)
        .replace("|", r"\|")
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("<", "&lt;")
    )


def table(frame: pd.DataFrame, kop: str) -> list[str]:
    """Rendert een DataFrame als Markdown-tabel met een vetgedrukte titelregel."""
    lines = [f"**{kop}**", ""]
    if frame.empty:
        return [*lines, "_geen_"]

    columns = list(frame.columns)
    alignment = ["---:" if is_numeric(frame[column]) else "---" for column in columns]
    lines.append("| " + " | ".join(_cel(column) for column in columns) + " |")
    lines.append("| " + " | ".join(alignment) + " |")
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(_cel(value) for value in row) + " |")
    return lines


def is_numeric(column: pd.Series) -> bool:
    """Geeft aan of een kolom numeriek is en dus rechts uitgelijnd hoort te worden.

    Booleans tellen niet mee: die lezen als tekst, niet als getal.
    """
    return pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column)
