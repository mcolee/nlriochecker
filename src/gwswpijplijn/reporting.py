"""Wegschrijven van de analyse als Markdown-samenvatting en geaggregeerde CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import ReportPair

FILE_MARKDOWN = "samenvatting.md"
FILE_CSV = "geaggregeerde_meldingen.csv"
TOP_N = 15


def write_reports(pair: ReportPair, output_dir: Path) -> tuple[Path, Path]:
    """Schrijft de Markdown-samenvatting en de geaggregeerde CSV naar `output_dir`."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return write_markdown(pair, output_dir), write_csv(pair, output_dir)


def write_markdown(pair: ReportPair, output_dir: Path) -> Path:
    """Schrijft de samenvatting als Markdown en geeft het geschreven pad terug."""
    target = _check_target(Path(output_dir) / FILE_MARKDOWN, pair)
    target.write_text(_render_markdown(pair), encoding="utf-8")
    return target


def write_csv(pair: ReportPair, output_dir: Path) -> Path:
    """Schrijft de geaggregeerde meldingen van beide CFK's als een enkele CSV."""
    target = _check_target(Path(output_dir) / FILE_CSV, pair)
    _aggregated_table(pair).to_csv(target, sep=";", index=False, encoding="utf-8")
    return target


def _aggregated_table(pair: ReportPair) -> pd.DataFrame:
    """Zet beide analyses onder elkaar in een lang formaat met een CFK-kolom."""
    parts = []
    for analysis in (pair.mds, pair.hyd):
        part = analysis.by_message_and_object_type.copy()
        part.insert(0, "CFK", analysis.report.cfk)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _check_target(target: Path, pair: ReportPair) -> Path:
    """Weigert te schrijven als het doelpad een van de invoerbestanden is."""
    inputs = {
        pair.mds.report.source_file.resolve(),
        pair.hyd.report.source_file.resolve(),
    }
    if target.resolve() in inputs:
        raise PipelineError(
            f"{target}: de uitvoer zou een invoerbestand overschrijven. Kies een andere uitvoermap."
        )
    return target


def _render_markdown(pair: ReportPair) -> str:
    """Stelt de volledige Markdown-samenvatting samen."""
    lines = [
        f"# Nulmeting-samenvatting {pair.dataset}",
        "",
        "## Herkomst",
        "",
        "| CFK | Bronbestand | Toetsmoment | Meldingregels | Totaal Aantal |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for analysis in (pair.mds, pair.hyd):
        report = analysis.report
        lines.append(
            f"| {report.cfk} | `{report.source_file}` | "
            f"{report.timestamp:%Y-%m-%d %H:%M:%S} | {len(report.messages)} | "
            f"{analysis.total_count} |"
        )
    if pair.timestamps_differ:
        lines += [
            "",
            "> **Let op:** de twee rapporten komen uit verschillende toetsmomenten.",
        ]

    lines += ["", "## Typeringspoort", ""]
    lines += _typing_section(pair)

    for analysis in (pair.mds, pair.hyd):
        lines += ["", f"## Meldingen CFK {analysis.report.cfk}", ""]
        lines += _table(
            analysis.by_message_type.head(TOP_N),
            _title("Meldingstypen", analysis.by_message_type),
        )
        lines += [""]
        lines += _table(
            analysis.by_object_type.head(TOP_N),
            _title("Objecttypen", analysis.by_object_type),
        )

    return "\n".join(lines) + "\n"


def _typing_section(pair: ReportPair) -> list[str]:
    """Bouwt de sectie over de typeringspoort, inclusief de ondergrens-toelichting."""
    lines = [
        "Meldingen van het type *Objecttype te globaal voor deze CFK* maken vervolg-",
        "validaties voor die objecten onbetrouwbaar. De score hieronder is een",
        "**ondergrens**: het detailrapport bevat alleen objecten met minstens een",
        "melding, dus objecten zonder meldingen ontbreken in de noemer.",
        "",
        "| CFK | Typeringsscore | Te globaal getypeerd | Benoemde objecten |",
        "| --- | ---: | ---: | ---: |",
    ]
    for analysis in (pair.mds, pair.hyd):
        gate = analysis.typing_gate
        lines.append(
            f"| {analysis.report.cfk} | {gate.score:.1f}% | {gate.too_generic_count} | "
            f"{gate.named_object_count} |"
        )

    for analysis in (pair.mds, pair.hyd):
        gate = analysis.typing_gate
        if gate.too_generic_count == 0:
            continue
        per_type = (
            gate.objects.groupby("Type object").size().sort_values(ascending=False).reset_index()
        )
        per_type.columns = ["Type object", "Objecten"]
        lines += ["", f"### Te globaal getypeerde objecten ({analysis.report.cfk})", ""]
        lines += _table(per_type, "Per objecttype")
        examples = ", ".join(f"`{name}`" for name in gate.objects["Naam"].head(10))
        lines += ["", f"Eerste tien objecten: {examples}"]

    return lines


def _title(label: str, frame: pd.DataFrame) -> str:
    """Maakt een tabeltitel die alleen 'top N' vermeldt als er daadwerkelijk is afgekapt."""
    if len(frame) > TOP_N:
        return f"{label} (top {TOP_N} van {len(frame)})"
    return f"{label} ({len(frame)})"


def _table(frame: pd.DataFrame, title: str) -> list[str]:
    """Rendert een DataFrame als Markdown-tabel met een vetgedrukte titelregel."""
    lines = [f"**{title}**", ""]
    if frame.empty:
        return [*lines, "_geen_"]

    columns = list(frame.columns)
    alignment = ["---:" if _is_numeric(frame[column]) else "---" for column in columns]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(alignment) + " |")
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def _is_numeric(column: pd.Series) -> bool:
    """Geeft aan of een kolom numeriek is en dus rechts uitgelijnd hoort te worden."""
    return pd.api.types.is_numeric_dtype(column)
