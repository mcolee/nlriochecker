"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

from pathlib import Path

import click

from gwswpijplijn import __version__
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import load_pair
from gwswpijplijn.reporting import write_reports


class _CliError(click.ClickException):
    """ClickException met een Nederlandse aanhef."""

    def show(self, file: object | None = None) -> None:
        """Toont de foutmelding op stderr."""
        click.echo(f"Fout: {self.format_message()}", err=True)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Toetst de datakwaliteit van vrijvervalriolering (GWSW-nulmeting)."""


@main.command("analyseer")
@click.option(
    "--mds",
    "mds_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Detailrapport getoetst aan CFK Mds of MdsPlan.",
)
@click.option(
    "--hyd",
    "hyd_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Detailrapport getoetst aan CFK Hyd.",
)
@click.option(
    "--output",
    "output_dir",
    default=Path("uitvoer"),
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Map waarin de samenvatting en de geaggregeerde CSV worden geschreven.",
)
def analyze(mds_path: Path, hyd_path: Path, output_dir: Path) -> None:
    """Analyseert een rapportenpaar en schrijft samenvatting en aggregaties weg."""
    try:
        pair = load_pair(mds_path, hyd_path)
        markdown_path, csv_path = write_reports(pair, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(f"Dataset {pair.dataset}: {pair.mds.report.cfk} + {pair.hyd.report.cfk}")
    for analysis in (pair.mds, pair.hyd):
        gate = analysis.typing_gate
        click.echo(
            f"  {analysis.report.cfk}: {analysis.total_count} meldingen, "
            f"typeringsscore {gate.score:.1f}% "
            f"({gate.too_generic_count} van {gate.named_object_count} objecten te globaal)"
        )
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")
