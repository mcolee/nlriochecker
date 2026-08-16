"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.comparison import compare_pairs
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import assess_coverage
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import load_pair
from gwswpijplijn.reporting import (
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)


def test_writes_both_files(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    markdown_path, csv_path = write_reports(pair, tmp_path / "uitvoer")

    assert markdown_path.name == FILE_MARKDOWN
    assert csv_path.name == FILE_CSV
    assert markdown_path.exists()
    assert csv_path.exists()


def test_markdown_contains_dataset_and_typing_score(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    markdown_path, _ = write_reports(pair, tmp_path)
    text = markdown_path.read_text(encoding="utf-8")

    assert "DeWolden" in text
    assert "## Typeringspoort" in text
    assert "| MdsPlan | 75.0% | 4 | 16 |" in text
    assert "ondergrens" in text


def test_csv_contains_both_cfks_and_sums_correctly(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    _, csv_path = write_reports(pair, tmp_path)
    table = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    assert list(table.columns) == ["CFK", "Type Melding", "Type object", "Aantal", "Regels"]
    assert set(table["CFK"]) == {"MdsPlan", "Hyd"}
    assert table.loc[table["CFK"] == "MdsPlan", "Aantal"].sum() == pair.mds.total_count
    assert table.loc[table["CFK"] == "Hyd", "Aantal"].sum() == pair.hyd.total_count


def test_output_never_overwrites_input(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    input_dir = tmp_path / "invoer"
    input_dir.mkdir()
    mds = input_dir / FILE_MARKDOWN
    mds.write_bytes(mini_mds.read_bytes())
    hyd = input_dir / "mini_hyd.csv"
    hyd.write_bytes(mini_hyd.read_bytes())
    pair = load_pair(mds, hyd)

    with pytest.raises(PipelineError, match="invoerbestand"):
        write_reports(pair, input_dir)


def test_samenvatting_bevat_de_dekkingsectie(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    coverage = assess_coverage(pair, load_coverage_config())
    markdown_path, _ = write_reports(pair, tmp_path, coverage)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "## Dekking van de geschrapte checks" in tekst
    assert "niet goedgekeurd" in tekst
    assert "RVZ-002, RVZ-003" in tekst


def test_dekkingrapport(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    coverage = assess_coverage(pair, load_coverage_config())
    markdown_path, csv_path = write_coverage_report(coverage, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")
    tabel = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    assert markdown_path.name == FILE_COVERAGE_MARKDOWN
    assert csv_path.name == FILE_COVERAGE_CSV
    assert "## RVZ-003 — Overstort zonder geregistreerde drempelbreedte" in tekst
    assert "Voorbehoud:" in tekst
    assert set(tabel["Rol"]) == {"bewijs", "tegenbewijs"}
    adm001 = tabel[(tabel["Check"] == "ADM-001") & (tabel["Rol"] == "bewijs")]
    assert list(adm001["Meldingregels"]) == [0, 4]


def test_vergelijkingsrapport(
    mini_mds: Path,
    mini_hyd: Path,
    mini_mds_later: Path,
    mini_hyd_later: Path,
    tmp_path: Path,
) -> None:
    config = load_coverage_config()
    comparison = compare_pairs(
        load_pair(mini_mds, mini_hyd),
        load_pair(mini_mds_later, mini_hyd_later),
        config,
    )
    markdown_path, csv_path, objects_path = write_comparison_reports(comparison, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")
    verschillen = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    objecten = pd.read_csv(objects_path, sep=";", encoding="utf-8")

    assert markdown_path.name == FILE_COMPARISON_MARKDOWN
    assert "# Trendvergelijking DeWolden" in tekst
    assert "| opgelost | 2 |" in tekst
    assert set(verschillen["Niveau"]) == {"meldingtype", "objecttype"}
    assert set(objecten["CFK"]) == {"MdsPlan", "Hyd"}
    assert set(objecten["Status"]) == {"opgelost", "nieuw", "gebleven"}
    assert len(objecten) == 34


def test_vergelijking_waarschuwt_bij_omgekeerde_volgorde(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    pair = load_pair(mini_mds, mini_hyd)
    comparison = compare_pairs(pair, pair, load_coverage_config())
    markdown_path, _, _ = write_comparison_reports(comparison, tmp_path)

    assert "niet nieuwer dan het eerste" in markdown_path.read_text(encoding="utf-8")
