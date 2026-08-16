"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

from pathlib import Path

import click

from gwswpijplijn import __version__
from gwswpijplijn.fouten import GwswPijplijnFout
from gwswpijplijn.paar import laad_paar
from gwswpijplijn.rapportage import schrijf_rapportage


class _PijplijnFout(click.ClickException):
    """ClickException met een Nederlandse aanhef."""

    def show(self, file: object | None = None) -> None:
        """Toont de foutmelding op stderr."""
        click.echo(f"Fout: {self.format_message()}", err=True)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Toetst de datakwaliteit van vrijvervalriolering (GWSW-nulmeting)."""


@main.command()
@click.option(
    "--mds",
    "mds_pad",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Detailrapport getoetst aan CFK Mds of MdsPlan.",
)
@click.option(
    "--hyd",
    "hyd_pad",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Detailrapport getoetst aan CFK Hyd.",
)
@click.option(
    "--output",
    "uitvoermap",
    default=Path("uitvoer"),
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Map waarin de samenvatting en de geaggregeerde CSV worden geschreven.",
)
def analyseer(mds_pad: Path, hyd_pad: Path, uitvoermap: Path) -> None:
    """Analyseert een rapportenpaar en schrijft samenvatting en aggregaties weg."""
    try:
        paar = laad_paar(mds_pad, hyd_pad)
        markdown_pad, csv_pad = schrijf_rapportage(paar, uitvoermap)
    except GwswPijplijnFout as fout:
        raise _PijplijnFout(str(fout)) from fout

    click.echo(f"Dataset {paar.dataset}: {paar.mds.rapport.cfk} + {paar.hyd.rapport.cfk}")
    for analyse in (paar.mds, paar.hyd):
        poort = analyse.typeringspoort
        click.echo(
            f"  {analyse.rapport.cfk}: {analyse.totaal_aantal} meldingen, "
            f"typeringsscore {poort.score:.1f}% "
            f"({poort.aantal_te_globaal} van {poort.aantal_benoemde_objecten} objecten te globaal)"
        )
    click.echo(f"Geschreven: {markdown_pad}")
    click.echo(f"Geschreven: {csv_pad}")
