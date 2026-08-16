"""Uitvoervormen van de checkbevindingen: Markdown, CSV en GeoPackage.

`schrijf_uitvoer` is de enige ingang die alle drie tegelijk wegschrijft. Hij bouwt
de meldingenlijst een keer en geeft hem aan elke schrijver door, zodat de drie
uitvoervormen niet uit elkaar kunnen lopen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from gwswpijplijn.checks import CheckRun
from gwswpijplijn.uitvoer.bevindingen import write_check_report
from gwswpijplijn.uitvoer.gpkg import schrijf_geopackage
from gwswpijplijn.uitvoer.melding import bouw_meldingen


@dataclass(frozen=True)
class Uitvoer:
    """De geschreven bestanden van een toets."""

    markdown: Path
    csv: Path
    geopackage: Path | None


def schrijf_uitvoer(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    met_geopackage: bool = True,
) -> Uitvoer:
    """Schrijft rapport, archief en GIS-uitvoer uit dezelfde meldingenstroom."""
    run_datum = run_datum or date.today()
    meldingen = bouw_meldingen(run, run_datum)

    markdown, csv = write_check_report(run, output_dir, run_datum, meldingen)
    geopackage = (
        schrijf_geopackage(run, meldingen, output_dir, run_datum) if met_geopackage else None
    )
    return Uitvoer(markdown=markdown, csv=csv, geopackage=geopackage)
