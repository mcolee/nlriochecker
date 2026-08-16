"""Wegschrijven van de analyse als Markdown-samenvatting en geaggregeerde CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gwswpijplijn.checks import CheckRun, Severity
from gwswpijplijn.comparison import ChangeStatus, PairComparison
from gwswpijplijn.coverage import CheckEvidence, CoverageResult
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import ReportPair

FILE_MARKDOWN = "samenvatting.md"
FILE_CSV = "geaggregeerde_meldingen.csv"
FILE_COVERAGE_MARKDOWN = "dekking.md"
FILE_COVERAGE_CSV = "dekking.csv"
FILE_COMPARISON_MARKDOWN = "vergelijking.md"
FILE_COMPARISON_CSV = "verschillen.csv"
FILE_OBJECT_CHANGES_CSV = "objectverschillen.csv"
FILE_CHECKS_MARKDOWN = "bevindingen.md"
FILE_CHECKS_CSV = "bevindingen.csv"
TOP_N = 15

TOELICHTING_NIET_GERAAKT = (
    "Een check die *niet geraakt* is, is niet goedgekeurd: de nulmeting geeft over dat "
    "onderwerp in deze dataset geen enkele melding. Dat betekent ofwel dat de data op "
    "dit punt schoon is, ofwel dat de nulmeting het hier niet toetst. Die twee zijn uit "
    "het detailrapport alleen niet te onderscheiden."
)


def write_reports(
    pair: ReportPair,
    output_dir: Path,
    coverage: CoverageResult | None = None,
) -> tuple[Path, Path]:
    """Schrijft de Markdown-samenvatting en de geaggregeerde CSV naar `output_dir`."""
    output_dir = _prepare(output_dir)
    return write_markdown(pair, output_dir, coverage), write_csv(pair, output_dir)


def write_markdown(
    pair: ReportPair,
    output_dir: Path,
    coverage: CoverageResult | None = None,
) -> Path:
    """Schrijft de samenvatting als Markdown en geeft het geschreven pad terug."""
    target = _check_target(Path(output_dir) / FILE_MARKDOWN, pair)
    target.write_text(_render_markdown(pair, coverage), encoding="utf-8")
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


def _prepare(output_dir: Path) -> Path:
    """Maakt de uitvoermap aan en geeft hem terug."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _render_markdown(pair: ReportPair, coverage: CoverageResult | None = None) -> str:
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

    if coverage is not None:
        lines += ["", "## Dekking van de geschrapte checks", ""]
        lines += _coverage_section(coverage)

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
    """Geeft aan of een kolom numeriek is en dus rechts uitgelijnd hoort te worden.

    Booleans tellen niet mee: die lezen als tekst, niet als getal.
    """
    return pd.api.types.is_numeric_dtype(column) and not pd.api.types.is_bool_dtype(column)


def write_coverage_report(result: CoverageResult, output_dir: Path) -> tuple[Path, Path]:
    """Schrijft de dekkinganalyse als Markdown en CSV en geeft beide paden terug."""
    output_dir = _prepare(output_dir)

    markdown_path = Path(output_dir) / FILE_COVERAGE_MARKDOWN
    markdown_path.write_text(_render_coverage(result), encoding="utf-8")

    csv_path = Path(output_dir) / FILE_COVERAGE_CSV
    _coverage_table(result).to_csv(csv_path, sep=";", index=False, encoding="utf-8")

    return markdown_path, csv_path


def _coverage_table(result: CoverageResult) -> pd.DataFrame:
    """Zet bewijs en tegenbewijs per check en CFK in een lang formaat."""
    rows = []
    for check in result.checks:
        for rol, items in (("bewijs", check.evidence), ("tegenbewijs", check.counter_evidence)):
            for item in items:
                rows.append(
                    {
                        "Check": check.mapping.id,
                        "Oordeel": check.verdict.value,
                        "CFK": item.cfk,
                        "Rol": rol,
                        "Vereist": item.required,
                        "Meldingregels": item.row_count,
                        "Aantal": item.weighted_count,
                        "Objecten": item.object_count,
                    }
                )
    return pd.DataFrame(
        rows,
        columns=[
            "Check",
            "Oordeel",
            "CFK",
            "Rol",
            "Vereist",
            "Meldingregels",
            "Aantal",
            "Objecten",
        ],
    )


def _render_coverage(result: CoverageResult) -> str:
    """Stelt het volledige dekkingrapport samen."""
    lines = [
        f"# Dekkinganalyse {result.dataset}",
        "",
        f"Checkregister versie {result.config.checkregister_versie} (`{result.config.bron}`), "
        f"typeringsdrempel {result.config.drempels.typeringsscore_minimum:.1f}%.",
        "",
    ]
    lines += _coverage_section(result)

    for check in result.checks:
        lines += ["", f"## {check.mapping.id} — {check.mapping.onderwerp}", ""]
        lines += [f"**Oordeel:** {check.verdict.value}", ""]
        lines += [f"**Dekkingclaim uit het register:** {check.mapping.claim}", ""]
        lines += [f"**Bewijs moet komen uit:** {', '.join(check.mapping.vereiste_cfk)}", ""]
        lines += _table(_evidence_frame(check.evidence), "Bewijs")
        if check.counter_evidence:
            lines += [""]
            lines += _table(_evidence_frame(check.counter_evidence), "Tegenbewijs")
            if check.has_counter_evidence:
                lines += [
                    "",
                    "> Deze meldingen zeggen dat de betreffende collectie in die CFK juist "
                    "niet getoetst wordt; de dekking heeft daar een gat.",
                ]
        if not check.typing_reliable:
            lines += [
                "",
                "> **Voorbehoud:** de typeringsscore van een vereiste CFK ligt onder de "
                "drempel. De nulmeting verklaart haar eigen vervolgvalidaties voor te "
                "globaal getypeerde objecten onbetrouwbaar; deze dekkingclaim erft dat "
                "voorbehoud.",
            ]

    return "\n".join(lines) + "\n"


def _coverage_section(result: CoverageResult) -> list[str]:
    """Bouwt de samenvattende dekkingtabel, ook gebruikt in samenvatting.md."""
    lines = [
        "| Check | Onderwerp | Oordeel | Vereiste CFK | Bewijs gevonden in | Voorbehoud |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in result.checks:
        gevonden = ", ".join(check.evidence_cfks) or "—"
        voorbehoud = []
        if not check.typing_reliable:
            voorbehoud.append("typering")
        if check.has_counter_evidence:
            voorbehoud.append("tegenbewijs")
        lines.append(
            f"| {check.mapping.id} | {check.mapping.onderwerp} | {check.verdict.value} | "
            f"{', '.join(check.mapping.vereiste_cfk)} | {gevonden} | "
            f"{', '.join(voorbehoud) or '—'} |"
        )

    niet_geraakt = [check.mapping.id for check in result.untouched]
    lines += ["", TOELICHTING_NIET_GERAAKT]
    if niet_geraakt:
        lines += [
            "",
            f"In deze dataset geldt dat voor: {', '.join(niet_geraakt)}.",
        ]
    else:
        lines += ["", "In deze dataset raakt de nulmeting alle geschrapte checks."]
    return lines


def _evidence_frame(evidence: list[CheckEvidence]) -> pd.DataFrame:
    """Zet een lijst bewijsposten om in een tabel voor de Markdown-uitvoer."""
    return pd.DataFrame(
        [
            {
                "CFK": item.cfk,
                "Vereist": "ja" if item.required else "nee",
                "Meldingregels": item.row_count,
                "Aantal": item.weighted_count,
                "Objecten": item.object_count,
                "Aspecten": ", ".join(item.aspects) or "—",
            }
            for item in evidence
        ],
        columns=["CFK", "Vereist", "Meldingregels", "Aantal", "Objecten", "Aspecten"],
    )


def write_comparison_reports(
    comparison: PairComparison, output_dir: Path
) -> tuple[Path, Path, Path]:
    """Schrijft de vergelijking als Markdown plus twee CSV's."""
    output_dir = _prepare(output_dir)

    markdown_path = Path(output_dir) / FILE_COMPARISON_MARKDOWN
    markdown_path.write_text(_render_comparison(comparison), encoding="utf-8")

    csv_path = Path(output_dir) / FILE_COMPARISON_CSV
    _comparison_table(comparison).to_csv(csv_path, sep=";", index=False, encoding="utf-8")

    objects_path = Path(output_dir) / FILE_OBJECT_CHANGES_CSV
    _object_changes_table(comparison).to_csv(objects_path, sep=";", index=False, encoding="utf-8")

    return markdown_path, csv_path, objects_path


def _comparison_table(comparison: PairComparison) -> pd.DataFrame:
    """Zet de aggregaatdelta's van beide CFK's onder elkaar."""
    parts = []
    for item in comparison.per_cfk:
        for niveau, frame, sleutel in (
            ("meldingtype", item.by_message_type, "Type Melding"),
            ("objecttype", item.by_object_type, "Type object"),
        ):
            deel = frame.rename(columns={sleutel: "Sleutel"}).copy()
            deel.insert(0, "CFK", item.cfk)
            deel.insert(1, "Niveau", niveau)
            parts.append(deel[["CFK", "Niveau", "Sleutel", "Eerder", "Later", "Verschil"]])
    return pd.concat(parts, ignore_index=True)


def _object_changes_table(comparison: PairComparison) -> pd.DataFrame:
    """Zet de objectverschillen van beide CFK's onder elkaar."""
    parts = []
    for item in comparison.per_cfk:
        deel = item.object_changes.copy()
        deel.insert(0, "CFK", item.cfk)
        parts.append(deel)
    return pd.concat(parts, ignore_index=True)


def _render_comparison(comparison: PairComparison) -> str:
    """Stelt het volledige vergelijkingsrapport samen."""
    lines = [
        f"# Trendvergelijking {comparison.dataset}",
        "",
        "| Meetmoment | CFK | Toetsmoment | Meldingregels | Totaal Aantal | Typeringsscore |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for label, pair in (("eerder", comparison.earlier), ("later", comparison.later)):
        for analysis in (pair.mds, pair.hyd):
            lines.append(
                f"| {label} | {analysis.report.cfk} | "
                f"{analysis.report.timestamp:%Y-%m-%d %H:%M:%S} | "
                f"{len(analysis.report.messages)} | {analysis.total_count} | "
                f"{analysis.typing_gate.score:.1f}% |"
            )

    if comparison.timestamps_out_of_order:
        lines += [
            "",
            "> **Let op:** het als later aangeboden paar is niet nieuwer dan het eerste. "
            "De verschillen hieronder zijn daarmee geen trend in de tijd.",
        ]

    lines += ["", "## Dekking van de geschrapte checks", ""]
    lines += _table(comparison.coverage_changes, "Oordeel per meetmoment")

    for item in comparison.per_cfk:
        lines += ["", f"## CFK {item.cfk}", ""]
        lines += [
            f"Totaal Aantal {item.total_delta:+d}, "
            f"typeringsscore {item.typing_score_delta:+.1f} procentpunt.",
            "",
        ]
        telling = item.status_counts()
        lines += [
            "| Status op objectniveau | Meldingen |",
            "| --- | ---: |",
            f"| opgelost | {telling[ChangeStatus.RESOLVED.value]} |",
            f"| nieuw | {telling[ChangeStatus.NEW.value]} |",
            f"| gebleven | {telling[ChangeStatus.REMAINING.value]} |",
            "",
        ]
        lines += _table(
            _grootste_verschillen(item.by_message_type, "Type Melding"),
            "Grootste verschillen per meldingtype",
        )
        lines += [""]
        lines += _table(
            _grootste_verschillen(item.by_object_type, "Type object"),
            "Grootste verschillen per objecttype",
        )

    lines += [
        "",
        f"De volledige objectverschillen staan in `{FILE_OBJECT_CHANGES_CSV}`.",
    ]
    return "\n".join(lines) + "\n"


def _grootste_verschillen(frame: pd.DataFrame, sleutel: str) -> pd.DataFrame:
    """De rijen met de grootste absolute verschillen, ongelijk aan nul."""
    gewijzigd = frame[frame["Verschil"] != 0]
    if gewijzigd.empty:
        return gewijzigd
    volgorde = gewijzigd["Verschil"].abs().sort_values(ascending=False).index
    return gewijzigd.loc[volgorde].head(TOP_N)[[sleutel, "Eerder", "Later", "Verschil"]]


def write_check_report(run: CheckRun, output_dir: Path) -> tuple[Path, Path]:
    """Schrijft de bevindingen van de check-engine als Markdown en CSV."""
    output_dir = _prepare(output_dir)

    markdown_path = Path(output_dir) / FILE_CHECKS_MARKDOWN
    markdown_path.write_text(_render_checks(run), encoding="utf-8")

    csv_path = Path(output_dir) / FILE_CHECKS_CSV
    _check_findings_table(run).to_csv(csv_path, sep=";", index=False, encoding="utf-8")

    return markdown_path, csv_path


def _check_findings_table(run: CheckRun) -> pd.DataFrame:
    """Zet alle bevindingen in een tabel."""
    rows = [
        {
            "Check": finding.check_id,
            "Ernst": finding.severity.value,
            "Dimensie": finding.dimension.value,
            "Label": finding.object_label,
            "Object": finding.object_uri,
            "Melding": finding.message,
            "TyperingBetrouwbaar": finding.typing_reliable,
        }
        for finding in run.findings
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "Check",
            "Ernst",
            "Dimensie",
            "Label",
            "Object",
            "Melding",
            "TyperingBetrouwbaar",
        ],
    )


def _render_checks(run: CheckRun) -> str:
    """Stelt het bevindingenrapport samen."""
    onbetrouwbaar = sum(outcome.unreliable_count for outcome in run.outcomes)
    lines = [
        f"# Checkbevindingen {run.dataset.source.name}",
        "",
        f"Bron: `{run.dataset.source}` — {len(run.dataset.nodes)} knooppunten, "
        f"{len(run.dataset.conduits)} strengen.",
        "",
        f"{run.count(Severity.ERROR)} fouten en {run.count(Severity.WARNING)} waarschuwingen "
        f"uit {len(run.outcomes)} checks.",
        "",
    ]

    if run.typing_gate_applied:
        lines += [
            f"De typeringspoort is toegepast: {onbetrouwbaar} bevindingen staan op objecten "
            "die de nulmeting te globaal getypeerd noemt. Die bevindingen blijven staan, "
            "maar zijn niet betrouwbaar te duiden.",
            "",
        ]
        buiten = run.unreliable_labels - run.unreliable_labels_in_dataset
        if buiten:
            lines += [
                f"> Van de {run.unreliable_labels} objecten die de nulmeting te globaal "
                f"getypeerd noemt, komen er {run.unreliable_labels_in_dataset} in deze dataset "
                f"voor; {buiten} niet. De detailrapporten en de OroX-export zijn losse "
                "bestanden en hoeven niet uit dezelfde momentopname te komen.",
                "",
            ]
    else:
        lines += [
            "> **Let op:** er is geen typeringspoort toegepast. Zonder de nulmeting-"
            "detailrapporten (`--mds` en `--hyd`) is niet bekend welke objecten te globaal "
            "getypeerd zijn, en dus welke bevindingen onbetrouwbaar zijn.",
            "",
        ]

    if run.dataset.geometry_errors:
        lines += [
            f"> {len(run.dataset.geometry_errors)} objecten hebben een onleesbare geometrie "
            "en konden niet volledig meedoen.",
            "",
        ]

    lines += _table(_check_summary(run), "Samenvatting per check")

    for outcome in run.outcomes:
        lines += ["", f"## {outcome.check_id} — {outcome.title}", ""]
        lines += [
            f"Ernst {outcome.severity.value}, dimensie {outcome.dimension.value}. "
            f"{len(outcome.findings)} bevindingen op {outcome.examined} bekeken objecten.",
        ]
        for note in outcome.notes:
            lines += ["", f"> {note}"]
        if not outcome.findings:
            lines += ["", "_geen bevindingen_"]
            continue
        lines += [""]
        lines += _table(
            _findings_frame(outcome.findings[:TOP_N]),
            _title("Bevindingen", pd.DataFrame(outcome.findings)),
        )

    lines += ["", f"Alle bevindingen staan in `{FILE_CHECKS_CSV}`."]
    return "\n".join(lines) + "\n"


def _check_summary(run: CheckRun) -> pd.DataFrame:
    """Een regel per check met de aantallen."""
    return pd.DataFrame(
        [
            {
                "Check": outcome.check_id,
                "Omschrijving": outcome.title,
                "Ernst": outcome.severity.value,
                "Dimensie": outcome.dimension.value,
                "Bekeken": outcome.examined,
                "Bevindingen": len(outcome.findings),
                "Typering onbetrouwbaar": outcome.unreliable_count,
            }
            for outcome in run.outcomes
        ],
        columns=[
            "Check",
            "Omschrijving",
            "Ernst",
            "Dimensie",
            "Bekeken",
            "Bevindingen",
            "Typering onbetrouwbaar",
        ],
    )


def _findings_frame(findings: list) -> pd.DataFrame:
    """Zet bevindingen om in een tabel voor de Markdown-uitvoer."""
    return pd.DataFrame(
        [
            {
                "Label": finding.object_label or "—",
                "Melding": finding.message,
                "Typering": "betrouwbaar" if finding.typing_reliable else "onbetrouwbaar",
            }
            for finding in findings
        ],
        columns=["Label", "Melding", "Typering"],
    )
