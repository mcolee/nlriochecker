"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.errors import PipelineError
from gwswpijplijn.pair import load_pair
from gwswpijplijn.reporting import FILE_CSV, FILE_MARKDOWN, write_reports


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
