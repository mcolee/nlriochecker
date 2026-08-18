"""Uitvoervormen van de checkbevindingen: Markdown, CSV, GeoPackage en JSON.

`schrijf_uitvoer` is de enige ingang die ze alle vier tegelijk wegschrijft. Hij
bouwt de meldingenlijst een keer en geeft hem aan elke schrijver door, zodat de vier
uitvoervormen niet uit elkaar kunnen lopen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from nlriochecker.checks import CheckRun
from nlriochecker.uitvoer.bevindingen import (
    FILE_CHECKS_JSON,
    meldingen_json,
    write_check_report,
)
from nlriochecker.uitvoer.gpkg import schrijf_geopackage
from nlriochecker.uitvoer.herkomst import schrijf_json
from nlriochecker.uitvoer.melding import bouw_meldingen
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang


@dataclass(frozen=True)
class Uitvoer:
    """De geschreven bestanden van een toets."""

    markdown: Path
    csv: Path
    geopackage: Path | None
    json: Path | None


def schrijf_uitvoer(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    *,
    met_geopackage: bool = True,
    met_json: bool = True,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> Uitvoer:
    """Schrijft rapport, archief, GIS-uitvoer en JSON uit dezelfde meldingenstroom.

    De JSON komt na het rapport: `write_check_report` maakt de uitvoermap aan. Zet
    hem er niet voor zonder zelf `prepare` te roepen.
    """
    run_datum = run_datum or date.today()
    meldingen = bouw_meldingen(run, run_datum)

    markdown, csv = write_check_report(run, output_dir, run_datum, meldingen)
    geopackage = (
        schrijf_geopackage(run, meldingen, output_dir, run_datum, voortgang=voortgang)
        if met_geopackage
        else None
    )
    json_pad = (
        schrijf_json(
            Path(output_dir) / FILE_CHECKS_JSON,
            meldingen_json(meldingen),
            run_datum=run_datum,
            dataset=run.dataset.source.name,
            cfk_set=list(run.meetbereik.gekozen),
            volledig=run.meetbereik.volledig,
            typeringspoort_toegepast=run.typing_gate_applied,
        )
        if met_json
        else None
    )
    return Uitvoer(markdown=markdown, csv=csv, geopackage=geopackage, json=json_pad)
