"""Tests voor de parser van detailrapporten."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.errors import ReportFormatError
from gwswpijplijn.report import COLUMNS, read_detail_report


def test_metadata_from_title_line(mini_mds: Path) -> None:
    report = read_detail_report(mini_mds)

    assert report.dataset == "DeWolden"
    assert report.cfk == "MdsPlan"
    assert report.timestamp == datetime(2026, 8, 14, 14, 6, 53)
    assert report.source_file == mini_mds


def test_hyd_title_line(mini_hyd: Path) -> None:
    report = read_detail_report(mini_hyd)

    assert report.cfk == "Hyd"
    assert report.timestamp == datetime(2026, 8, 14, 14, 30, 6)


def test_columns_and_dtypes(mini_mds: Path) -> None:
    messages = read_detail_report(mini_mds).messages

    assert list(messages.columns) == COLUMNS
    assert pd.api.types.is_integer_dtype(messages["Aantal"])
    assert len(messages) == 20


def test_empty_name_stays_empty_string(mini_mds: Path) -> None:
    messages = read_detail_report(mini_mds).messages
    without_name = messages[messages["Type Melding"] == "Collectie-item onbekend"]

    assert list(without_name["Naam"]) == [""]
    assert not messages["Naam"].isna().any()


def test_unrecognised_title_line_raises(mini_broken: Path) -> None:
    with pytest.raises(ReportFormatError, match="niet herkend"):
        read_detail_report(mini_broken)


def test_empty_file_raises(tmp_path: Path) -> None:
    empty = tmp_path / "leeg.csv"
    empty.write_text("", encoding="cp1252")

    with pytest.raises(ReportFormatError, match="leeg"):
        read_detail_report(empty)


def test_non_numeric_count_raises(mini_mds: Path, tmp_path: Path) -> None:
    lines = mini_mds.read_text(encoding="cp1252").splitlines()
    lines[2] = lines[2].replace("33;", "veel;", 1)
    broken = tmp_path / "stuk.csv"
    broken.write_text("\n".join(lines) + "\n", encoding="cp1252")

    with pytest.raises(ReportFormatError, match="Aantal"):
        read_detail_report(broken)
