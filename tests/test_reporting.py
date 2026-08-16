"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.analysis import analyze
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import CheckContext, run_checks
from gwswpijplijn.comparison import compare_metingen
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import assess_coverage
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.meting import laad_nulmeting
from gwswpijplijn.reporting import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_MARKDOWN,
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    write_check_report,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from gwswpijplijn.studiegebied import load_study_area

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


@pytest.fixture
def analyse(shacl_drieluik: list[Path]):
    """De analyse van de mini-nulmeting."""
    return analyze(laad_nulmeting(shacl_drieluik, VEREIST))


def test_schrijft_samenvatting_en_csv(analyse, tmp_path: Path) -> None:
    markdown_path, csv_path = write_reports(analyse, tmp_path / "uitvoer")

    assert markdown_path.name == FILE_MARKDOWN
    assert csv_path.name == FILE_CSV
    tabel = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    assert set(tabel["CFK"]) == {"Hyd", "MdsPlan", "MdsProj"}


def test_samenvatting_meldt_ontbrekende_dataset(analyse, tmp_path: Path) -> None:
    markdown_path, _ = write_reports(analyse, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "dewolden_orox.ttl" in tekst
    assert "## Typeringspoort" in tekst
    # Zonder dataset hoort er geen score te staan, maar wel een uitleg waarom niet.
    assert "geen OroX-dataset meegegeven" in tekst


def test_dekkingrapport(analyse, tmp_path: Path) -> None:
    coverage = assess_coverage(analyse, load_coverage_config())
    markdown_path, csv_path = write_coverage_report(coverage, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == FILE_COVERAGE_MARKDOWN
    assert csv_path.name == FILE_COVERAGE_CSV
    assert "RVZ-003" in tekst
    assert "niet goedgekeurd" in tekst
    assert "RVZ-002, RVZ-003" in tekst


def test_vergelijkingsrapport(analyse, tmp_path: Path) -> None:
    comparison = compare_metingen(analyse, analyse, load_coverage_config())
    markdown_path, csv_path, objects_path = write_comparison_reports(comparison, tmp_path)

    assert markdown_path.name == FILE_COMPARISON_MARKDOWN
    assert "# Trendvergelijking dewolden_orox.ttl" in markdown_path.read_text(encoding="utf-8")
    verschillen = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    assert set(verschillen["Niveau"]) == {"vorm", "objecttype"}
    objecten = pd.read_csv(objects_path, sep=";", encoding="utf-8")
    assert set(objecten["Status"]) == {"gebleven"}


def test_uitvoer_overschrijft_nooit_de_invoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    invoermap = tmp_path / "invoer"
    invoermap.mkdir()
    paden = []
    for bron, naam in zip(shacl_drieluik, [FILE_MARKDOWN, "b.csv", "c.csv"], strict=True):
        doel = invoermap / naam
        doel.write_bytes(bron.read_bytes())
        paden.append(doel)
    analyse = analyze(laad_nulmeting(paden, VEREIST))

    with pytest.raises(PipelineError, match="invoerbestand"):
        write_reports(analyse, invoermap)


def test_checkrapport_meldt_het_studiegebied(tmp_path: Path) -> None:
    dataset = load_dataset(TTL_DIR / "top001_losliggende_put.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())
    run = run_checks(context, ["TOP-001"])
    assert len(run.findings) == 1

    gebied_pad = Path(__file__).parent / "fixtures" / "gis" / "vierkant.gpkg"
    gebied = load_study_area(gebied_pad)
    beperkt = run.beperk_tot_studiegebied(gebied)

    markdown_path, csv_path = write_check_report(beperkt, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == FILE_CHECKS_MARKDOWN
    assert csv_path.name == FILE_CHECKS_CSV
    assert "Studiegebied" in tekst
    assert beperkt.findings == []
    assert sum(outcome.weggelaten for outcome in beperkt.outcomes) == 1
