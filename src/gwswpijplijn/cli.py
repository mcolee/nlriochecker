"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

from pathlib import Path

import click

from gwswpijplijn import __version__
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import REGISTRY, CheckContext, Severity, run_checks
from gwswpijplijn.comparison import compare_pairs
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import assess_coverage
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import ReportPair, load_pair
from gwswpijplijn.reporting import (
    write_check_report,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)


class _CliError(click.ClickException):
    """ClickException met een Nederlandse aanhef."""

    def show(self, file: object | None = None) -> None:
        """Toont de foutmelding op stderr."""
        click.echo(f"Fout: {self.format_message()}", err=True)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Toetst de datakwaliteit van vrijvervalriolering (GWSW-nulmeting)."""


RAPPORT_TYPE = click.Path(exists=True, dir_okay=False, path_type=Path)


def _report_option(naam: str, doel: str, hulp: str):
    """Bouwt een verplichte optie die naar een detailrapport wijst."""
    return click.option(naam, doel, required=True, type=RAPPORT_TYPE, help=hulp)


def _config_option():
    """Bouwt de optionele optie voor een eigen dekkingmapping."""
    return click.option(
        "--config",
        "config_path",
        default=None,
        type=RAPPORT_TYPE,
        help="Eigen dekkingmapping (TOML); standaard de meegeleverde dekking.toml.",
    )


def _output_option(hulp: str):
    """Bouwt de optie voor de uitvoermap."""
    return click.option(
        "--output",
        "output_dir",
        default=Path("uitvoer"),
        show_default=True,
        type=click.Path(file_okay=False, path_type=Path),
        help=hulp,
    )


def _echo_pair(pair: ReportPair) -> None:
    """Toont dataset, CFK's en typeringsscore van een rapportenpaar."""
    click.echo(f"Dataset {pair.dataset}: {pair.mds.report.cfk} + {pair.hyd.report.cfk}")
    for analysis in (pair.mds, pair.hyd):
        gate = analysis.typing_gate
        click.echo(
            f"  {analysis.report.cfk}: {analysis.total_count} meldingen, "
            f"typeringsscore {gate.score:.1f}% "
            f"({gate.too_generic_count} van {gate.named_object_count} objecten te globaal)"
        )


@main.command("analyseer")
@_report_option("--mds", "mds_path", "Detailrapport getoetst aan CFK Mds of MdsPlan.")
@_report_option("--hyd", "hyd_path", "Detailrapport getoetst aan CFK Hyd.")
@_config_option()
@_output_option("Map waarin de samenvatting en de geaggregeerde CSV worden geschreven.")
def analyze(mds_path: Path, hyd_path: Path, config_path: Path | None, output_dir: Path) -> None:
    """Analyseert een rapportenpaar en schrijft samenvatting en aggregaties weg."""
    try:
        pair = load_pair(mds_path, hyd_path)
        coverage = assess_coverage(pair, load_coverage_config(config_path))
        markdown_path, csv_path = write_reports(pair, output_dir, coverage)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    _echo_pair(pair)
    niet_geraakt = [check.mapping.id for check in coverage.untouched]
    if niet_geraakt:
        click.echo(f"  Niet geraakte geschrapte checks: {', '.join(niet_geraakt)}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


@main.command("dekking")
@_report_option("--mds", "mds_path", "Detailrapport getoetst aan CFK Mds of MdsPlan.")
@_report_option("--hyd", "hyd_path", "Detailrapport getoetst aan CFK Hyd.")
@_config_option()
@_output_option("Map waarin het dekkingrapport wordt geschreven.")
def coverage_command(
    mds_path: Path, hyd_path: Path, config_path: Path | None, output_dir: Path
) -> None:
    """Toetst of de nulmeting de geschrapte checks in deze dataset daadwerkelijk raakt."""
    try:
        pair = load_pair(mds_path, hyd_path)
        result = assess_coverage(pair, load_coverage_config(config_path))
        markdown_path, csv_path = write_coverage_report(result, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(
        f"Dataset {result.dataset}, checkregister {result.config.checkregister_versie}: "
        f"{len(result.checks)} geschrapte checks getoetst"
    )
    for check in result.checks:
        gevonden = ", ".join(check.evidence_cfks) or "geen bewijs"
        voorbehoud = "" if check.typing_reliable else "  [typeringsvoorbehoud]"
        click.echo(f"  {check.mapping.id:9s} {check.verdict.value:14s} {gevonden}{voorbehoud}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


@main.command("vergelijk")
@_report_option("--eerder-mds", "earlier_mds", "Mds-rapport van het eerste meetmoment.")
@_report_option("--eerder-hyd", "earlier_hyd", "Hyd-rapport van het eerste meetmoment.")
@_report_option("--later-mds", "later_mds", "Mds-rapport van het tweede meetmoment.")
@_report_option("--later-hyd", "later_hyd", "Hyd-rapport van het tweede meetmoment.")
@_config_option()
@_output_option("Map waarin de vergelijking wordt geschreven.")
def compare_command(
    earlier_mds: Path,
    earlier_hyd: Path,
    later_mds: Path,
    later_hyd: Path,
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Zet twee nulmetingen van dezelfde dataset naast elkaar voor trendbewaking."""
    try:
        earlier = load_pair(earlier_mds, earlier_hyd)
        later = load_pair(later_mds, later_hyd)
        comparison = compare_pairs(earlier, later, load_coverage_config(config_path))
        markdown_path, csv_path, objects_path = write_comparison_reports(comparison, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(f"Dataset {comparison.dataset}")
    if comparison.timestamps_out_of_order:
        click.echo("  Let op: het latere paar is niet nieuwer dan het eerste.")
    for item in comparison.per_cfk:
        telling = item.status_counts()
        click.echo(
            f"  {item.cfk}: totaal {item.total_delta:+d}, "
            f"typering {item.typing_score_delta:+.1f} procentpunt, "
            f"{telling['opgelost']} opgelost / {telling['nieuw']} nieuw / "
            f"{telling['gebleven']} gebleven"
        )
    gewijzigd = comparison.coverage_changes[comparison.coverage_changes["Gewijzigd"]]
    for _, rij in gewijzigd.iterrows():
        click.echo(f"  Dekking {rij['Check']}: {rij['Eerder']} -> {rij['Later']}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")
    click.echo(f"Geschreven: {objects_path}")


@main.command("toets")
@click.option(
    "--dataset",
    "dataset_path",
    required=True,
    type=RAPPORT_TYPE,
    help="GWSW-OroX-dataset (TTL).",
)
@click.option(
    "--ontologie",
    "ontology_paths",
    multiple=True,
    type=RAPPORT_TYPE,
    help="GWSW-ontologie (TTL) voor de klassenhierarchie; meermaals toegestaan.",
)
@click.option(
    "--mds",
    "mds_path",
    default=None,
    type=RAPPORT_TYPE,
    help="Nulmeting-detailrapport Mds of MdsPlan, voor de typeringspoort.",
)
@click.option(
    "--hyd",
    "hyd_path",
    default=None,
    type=RAPPORT_TYPE,
    help="Nulmeting-detailrapport Hyd, voor de typeringspoort.",
)
@click.option(
    "--check",
    "check_ids",
    multiple=True,
    help="Check-ID uit het register; meermaals toegestaan. Zonder deze optie draaien ze alle.",
)
@_config_option()
@_output_option("Map waarin het bevindingenrapport wordt geschreven.")
def check_command(
    dataset_path: Path,
    ontology_paths: tuple[Path, ...],
    mds_path: Path | None,
    hyd_path: Path | None,
    check_ids: tuple[str, ...],
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Draait de checks uit het checkregister op een GWSW-OroX-dataset."""
    if (mds_path is None) != (hyd_path is None):
        raise _CliError("Geef --mds en --hyd samen op: de typeringspoort vraagt beide rapporten.")

    try:
        dataset = load_dataset(dataset_path, list(ontology_paths))
        config = load_check_config(config_path)
        unreliable, gate_applied = _typing_gate(mds_path, hyd_path)
        context = CheckContext(
            dataset=dataset,
            config=config,
            unreliable_labels=unreliable,
        )
        run = run_checks(context, list(check_ids) or None, typing_gate_applied=gate_applied)
        markdown_path, csv_path = write_check_report(run, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error
    except KeyError as error:
        bekend = ", ".join(sorted(REGISTRY))
        raise _CliError(f"{error.args[0]}. Bekende checks: {bekend}.") from error

    click.echo(
        f"{dataset_path.name}: {len(dataset.nodes)} knooppunten, {len(dataset.conduits)} strengen"
    )
    if not gate_applied:
        click.echo("  Geen typeringspoort toegepast (--mds en --hyd niet opgegeven).")
    for outcome in run.outcomes:
        voorbehoud = (
            f", {outcome.unreliable_count} met typeringsvoorbehoud"
            if outcome.unreliable_count
            else ""
        )
        click.echo(
            f"  {outcome.check_id:9s} {outcome.severity.value}  "
            f"{len(outcome.findings):5d} bevindingen{voorbehoud}"
        )
    click.echo(
        f"Totaal {run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen"
    )
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


def _typing_gate(mds_path: Path | None, hyd_path: Path | None) -> tuple[frozenset[str], bool]:
    """Haalt de te globaal getypeerde objectlabels uit het rapportenpaar."""
    if mds_path is None or hyd_path is None:
        return frozenset(), False

    pair = load_pair(mds_path, hyd_path)
    labels = {
        naam
        for analysis in (pair.mds, pair.hyd)
        for naam in analysis.typing_gate.objects["Naam"]
        if naam
    }
    return frozenset(labels), True
