"""Wegschrijven van de analyse als Markdown-samenvatting en geaggregeerde CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gwswpijplijn.analysis import MetingAnalysis
from gwswpijplijn.comparison import ChangeStatus, MetingComparison
from gwswpijplijn.coverage import CheckEvidence, CoverageResult
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.uitvoer.bevindingen import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_MARKDOWN,
    write_check_report,
)
from gwswpijplijn.uitvoer.tabel import TOP_N, prepare, table, title

FILE_MARKDOWN = "samenvatting.md"
FILE_CSV = "geaggregeerde_meldingen.csv"
FILE_COVERAGE_MARKDOWN = "dekking.md"
FILE_COVERAGE_CSV = "dekking.csv"
FILE_COMPARISON_MARKDOWN = "vergelijking.md"
FILE_COMPARISON_CSV = "verschillen.csv"
FILE_OBJECT_CHANGES_CSV = "objectverschillen.csv"

TOELICHTING_NIET_GERAAKT = (
    "Een check die *niet geraakt* is, is niet goedgekeurd: de nulmeting geeft over dat "
    "onderwerp in deze dataset geen enkele melding. Dat betekent ofwel dat de data op "
    "dit punt schoon is, ofwel dat de nulmeting het hier niet toetst. Die twee zijn uit "
    "het detailrapport alleen niet te onderscheiden."
)


def write_reports(
    analyse: MetingAnalysis,
    output_dir: Path,
    coverage: CoverageResult | None = None,
) -> tuple[Path, Path]:
    """Schrijft de Markdown-samenvatting en de geaggregeerde CSV naar `output_dir`."""
    output_dir = prepare(output_dir)
    return write_markdown(analyse, output_dir, coverage), write_csv(analyse, output_dir)


def write_markdown(
    analyse: MetingAnalysis,
    output_dir: Path,
    coverage: CoverageResult | None = None,
) -> Path:
    """Schrijft de samenvatting als Markdown en geeft het geschreven pad terug."""
    target = _check_target(Path(output_dir) / FILE_MARKDOWN, analyse)
    target.write_text(_render_markdown(analyse, coverage), encoding="utf-8")
    return target


def write_csv(analyse: MetingAnalysis, output_dir: Path) -> Path:
    """Schrijft de geaggregeerde meldingen van alle CFK's als een enkele CSV."""
    target = _check_target(Path(output_dir) / FILE_CSV, analyse)
    _aggregated_table(analyse).to_csv(target, sep=";", index=False, encoding="utf-8")
    return target


def _aggregated_table(analyse: MetingAnalysis) -> pd.DataFrame:
    """Zet de analyses van alle CFK's onder elkaar met een CFK-kolom."""
    parts = []
    for cfk in analyse.meting.cfks:
        part = analyse.per_cfk[cfk].by_shape_and_object_type.copy()
        part.insert(0, "CFK", cfk)
        parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _check_target(target: Path, analyse: MetingAnalysis) -> Path:
    """Weigert te schrijven als het doelpad een van de invoerbestanden is."""
    inputs = {rapport.source_file.resolve() for rapport in analyse.meting.reports.values()}
    if target.resolve() in inputs:
        raise PipelineError(
            f"{target}: de uitvoer zou een invoerbestand overschrijven. Kies een andere uitvoermap."
        )
    return target


def _render_markdown(analyse: MetingAnalysis, coverage: CoverageResult | None = None) -> str:
    """Stelt de volledige Markdown-samenvatting samen."""
    meting = analyse.meting
    lines = [
        f"# Nulmeting-samenvatting {meting.dataset_file}",
        "",
        "## Herkomst",
        "",
        "| CFK | Bronbestand | Toetsmoment | Meldingen | Fouten | Waarschuwingen |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for cfk in meting.cfks:
        deel = analyse.per_cfk[cfk]
        lines.append(
            f"| {cfk} | `{deel.report.source_file.name}` | "
            f"{deel.report.timestamp:%Y-%m-%d %H:%M:%S} | {deel.total_count} | "
            f"{deel.error_count} | {deel.warning_count} |"
        )
    if meting.timestamps_differ:
        lines += [
            "",
            "> **Let op:** de rapporten komen uit verschillende toetsmomenten.",
        ]

    lines += ["", "## Typeringspoort", ""]
    lines += _typing_section(analyse)

    if coverage is not None:
        lines += ["", "## Dekking van de geschrapte checks", ""]
        lines += _register_section(coverage)
        lines += _coverage_section(coverage)
        lines += _discrepancy_section(coverage)

    for cfk in meting.cfks:
        deel = analyse.per_cfk[cfk]
        lines += ["", f"## Meldingen CFK {cfk}", ""]
        lines += table(deel.by_shape.head(TOP_N), title("SHACL-vormen", deel.by_shape))
        lines += [""]
        lines += table(deel.by_object_type.head(TOP_N), title("Objecttypen", deel.by_object_type))

    return "\n".join(lines) + "\n"


def _typing_section(analyse: MetingAnalysis) -> list[str]:
    """Bouwt de sectie over de typeringspoort."""
    lines = [
        "De SHACL-meting benoemt de klassen die binnen een conformiteitsklasse te",
        "globaal zijn; vervolgvalidaties op objecten van die klassen zijn daardoor",
        "onbetrouwbaar. De instanties volgen uit de dataset, dus zonder OroX-bestand",
        "is er wel een klassenlijst maar geen score.",
        "",
        "| CFK | Te globale klassen | Objecten | Typeringsscore |",
        "| --- | --- | ---: | ---: |",
    ]
    for cfk in analyse.meting.cfks:
        gate = analyse.per_cfk[cfk].typing_gate
        klassen = ", ".join(gate.classes) or "geen"
        score = f"{gate.score:.1f}%" if gate.score is not None else "\u2014"
        objecten = str(gate.too_generic_count) if gate.resolved else "\u2014"
        lines.append(f"| {cfk} | {klassen} | {objecten} | {score} |")

    if not any(analyse.per_cfk[cfk].typing_gate.resolved for cfk in analyse.meting.cfks):
        lines += [
            "",
            "> Er is geen OroX-dataset meegegeven, dus het aantal betrokken objecten en "
            "de score zijn niet te bepalen. Geef `--dataset` op voor een volledig beeld.",
        ]

    return lines


def write_coverage_report(result: CoverageResult, output_dir: Path) -> tuple[Path, Path]:
    """Schrijft de dekkinganalyse als Markdown en CSV en geeft beide paden terug."""
    output_dir = prepare(output_dir)

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
    lines += _register_section(result)
    lines += _coverage_section(result)
    lines += _discrepancy_section(result)

    for check in result.checks:
        lines += ["", f"## {check.mapping.id} — {check.mapping.onderwerp}", ""]
        lines += [f"**Oordeel:** {check.verdict.value}", ""]
        lines += [f"**Dekkingclaim uit het register:** {check.mapping.claim}", ""]
        lines += [f"**Bewijs moet komen uit:** {', '.join(check.mapping.vereiste_cfk)}", ""]
        lines += table(_evidence_frame(check.evidence), "Bewijs")
        if check.counter_evidence:
            lines += [""]
            lines += table(_evidence_frame(check.counter_evidence), "Tegenbewijs")
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


def _register_section(result: CoverageResult) -> list[str]:
    """Meldt of de dekkingmapping nog bij het checkregister past.

    Zonder deze regel leest het rapport als een geverifieerde dekking, ook wanneer
    het register intussen is opgeschoven en niemand de mapping heeft bijgewerkt.
    """
    controle = result.registercontrole
    if controle is None or not controle.uitgevoerd:
        return [
            "> **Niet gecontroleerd:** de dekkingmapping is niet tegen het checkregister "
            "gelegd (geen register meegegeven). Of de mapping nog bij de registerversie "
            "past waarop de schrapronde geverifieerd is, staat hier dus niet vast.",
            "",
        ]
    if controle.klopt:
        return [
            f"De dekkingmapping past bij `{controle.register}` (versie "
            f"{controle.register_versie}): elke geschrapte check heeft een sentinel en "
            "omgekeerd.",
            "",
        ]
    regels = "".join(f"\n> - {regel}" for regel in controle.toelichting())
    return [
        f"> **Dekking vervallen:** de mapping loopt uit de pas met `{controle.register}`.{regels}",
        ">",
        "> Zolang dit niet is opgelost, is de dekking van de geschrapte checks niet "
        "aangetoond. Die checks zitten niet in de engine, dus er kijkt niets anders naar.",
        "",
    ]


def _discrepancy_section(result: CoverageResult) -> list[str]:
    """Meldt bewijsvormen die niet in alle vereiste CFK's meldingen opleveren."""
    if not result.discrepanties:
        return []
    lines = [
        "",
        "### Vormen die niet in alle vereiste CFK's vuren",
        "",
        "Alle CFK's toetsen hetzelfde RDF-bestand, dus schone data verklaart deze "
        "verschillen niet: ze zitten in de meting.",
        "",
        "| Check | Vorm | Wel meldingen | Geen meldingen |",
        "| --- | --- | --- | --- |",
    ]
    for afwijking in result.discrepanties:
        lines.append(
            f"| {afwijking.check_id} | `{afwijking.patroon}` | "
            f"{', '.join(afwijking.met_meldingen)} | "
            f"{', '.join(afwijking.zonder_meldingen)} |"
        )

    if result.ongelijke_meting:
        lines += [
            "",
            "> **Voorzichtig:** de rapporten zijn niet op dezelfde manier gedraaid ("
            + "; ".join(result.ongelijke_meting)
            + "). Dat verklaart deze verschillen evengoed, dus ze zeggen hier niets over "
            "de vormverzameling van de conformiteitsklassen.",
        ]
    else:
        lines += [
            "",
            "De rapporten zijn op dezelfde onderdelen gevalideerd en noemen dezelfde "
            "uitzonderingen, dus het verschil zit in de vormverzameling van de CFK: een "
            'dekkingclaim van de vorm "beide CFK\'s" rust in werkelijkheid op een deel '
            "ervan.",
        ]
    return lines


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
                "Objecten": item.object_count,
                "Vormen": ", ".join(item.shapes) or "—",
            }
            for item in evidence
        ],
        columns=["CFK", "Vereist", "Meldingregels", "Objecten", "Vormen"],
    )


def write_comparison_reports(
    comparison: MetingComparison, output_dir: Path
) -> tuple[Path, Path, Path]:
    """Schrijft de vergelijking als Markdown plus twee CSV's."""
    output_dir = prepare(output_dir)

    markdown_path = Path(output_dir) / FILE_COMPARISON_MARKDOWN
    markdown_path.write_text(_render_comparison(comparison), encoding="utf-8")

    csv_path = Path(output_dir) / FILE_COMPARISON_CSV
    _comparison_table(comparison).to_csv(csv_path, sep=";", index=False, encoding="utf-8")

    objects_path = Path(output_dir) / FILE_OBJECT_CHANGES_CSV
    _object_changes_table(comparison).to_csv(objects_path, sep=";", index=False, encoding="utf-8")

    return markdown_path, csv_path, objects_path


def _comparison_table(comparison: MetingComparison) -> pd.DataFrame:
    """Zet de aggregaatdelta's van beide CFK's onder elkaar."""
    parts = []
    for item in comparison.per_cfk:
        for niveau, frame, sleutel in (
            ("vorm", item.by_shape, "Source"),
            ("objecttype", item.by_object_type, "Objecttype"),
        ):
            deel = frame.rename(columns={sleutel: "Sleutel"}).copy()
            deel.insert(0, "CFK", item.cfk)
            deel.insert(1, "Niveau", niveau)
            parts.append(deel[["CFK", "Niveau", "Sleutel", "Eerder", "Later", "Verschil"]])
    return pd.concat(parts, ignore_index=True)


def _object_changes_table(comparison: MetingComparison) -> pd.DataFrame:
    """Zet de objectverschillen van beide CFK's onder elkaar."""
    parts = []
    for item in comparison.per_cfk:
        deel = item.object_changes.copy()
        deel.insert(0, "CFK", item.cfk)
        parts.append(deel)
    return pd.concat(parts, ignore_index=True)


def _render_comparison(comparison: MetingComparison) -> str:
    """Stelt het volledige vergelijkingsrapport samen."""
    lines = [
        f"# Trendvergelijking {comparison.dataset_file}",
        "",
        "| Meetmoment | CFK | Toetsmoment | Meldingen | Fouten | Typeringsscore |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for label, kant in (("eerder", comparison.earlier), ("later", comparison.later)):
        for cfk in kant.meting.cfks:
            deel = kant.per_cfk[cfk]
            score = deel.typing_gate.score
            lines.append(
                f"| {label} | {cfk} | {deel.report.timestamp:%Y-%m-%d %H:%M:%S} | "
                f"{deel.total_count} | {deel.error_count} | "
                f"{f'{score:.1f}%' if score is not None else '—'} |"
            )

    if comparison.timestamps_out_of_order:
        lines += [
            "",
            "> **Let op:** het als later aangeboden paar is niet nieuwer dan het eerste. "
            "De verschillen hieronder zijn daarmee geen trend in de tijd.",
        ]

    lines += ["", "## Dekking van de geschrapte checks", ""]
    lines += table(comparison.coverage_changes, "Oordeel per meetmoment")

    for item in comparison.per_cfk:
        lines += ["", f"## CFK {item.cfk}", ""]
        lines += [
            f"Meldingen {item.total_delta:+d}, waarvan fouten {item.error_delta:+d}.",
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
        lines += table(
            _grootste_verschillen(item.by_shape, "Source"),
            "Grootste verschillen per SHACL-vorm",
        )
        lines += [""]
        lines += table(
            _grootste_verschillen(item.by_object_type, "Objecttype"),
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


# Het bevindingenrapport is naar uitvoer/bevindingen.py verhuisd, maar blijft hier
# importeerbaar: bestaande aanroepen en tests hoeven daar niet van te weten.
__all__ = [
    "FILE_CHECKS_CSV",
    "FILE_CHECKS_MARKDOWN",
    "write_check_report",
    "write_comparison_reports",
    "write_coverage_report",
    "write_markdown",
    "write_reports",
]
