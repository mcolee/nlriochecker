"""Integratietest op de volledige De Wolden-detailrapporten."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gwswpijplijn.analysis import MESSAGE_TOO_GENERIC_PREFIX
from gwswpijplijn.pair import ReportPair, load_pair
from gwswpijplijn.reporting import write_reports

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MDS_FULL = DATA_DIR / "dewolden_nulmeting.csv"
HYD_FULL = DATA_DIR / "dewolden_nulmeting_1.csv"

pytestmark = [
    pytest.mark.integratie,
    pytest.mark.skipif(
        not (MDS_FULL.exists() and HYD_FULL.exists()),
        reason="de volledige De Wolden-bestanden staan niet in data/",
    ),
]


def _independent_count(path: Path) -> dict[str, int]:
    """Telt het bestand na met een kale csv.reader, buiten de parser om."""
    with path.open(encoding="cp1252", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))

    messages = rows[2:]
    named = {(row[2], row[3]) for row in messages if row[3].strip()}
    too_generic = {
        (row[2], row[3])
        for row in messages
        if row[3].strip() and row[1].startswith(MESSAGE_TOO_GENERIC_PREFIX)
    }
    return {
        "rows": len(messages),
        "sum": sum(int(row[0]) for row in messages),
        "named": len(named),
        "too_generic": len(too_generic),
    }


@pytest.fixture(scope="module")
def pair() -> ReportPair:
    """Het volledige rapportenpaar van De Wolden, eenmalig ingelezen."""
    return load_pair(MDS_FULL, HYD_FULL)


def test_metadata(pair: ReportPair) -> None:
    assert pair.dataset == "DeWolden"
    assert pair.mds.report.cfk == "MdsPlan"
    assert pair.hyd.report.cfk == "Hyd"


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_totals_match_independent_count(pair: ReportPair, cfk: str) -> None:
    analysis = getattr(pair, cfk)
    counted = _independent_count(analysis.report.source_file)

    assert len(analysis.report.messages) == counted["rows"]
    assert analysis.total_count == counted["sum"]
    assert int(analysis.by_message_type["Aantal"].sum()) == counted["sum"]
    assert int(analysis.by_object_type["Aantal"].sum()) == counted["sum"]
    assert int(analysis.by_message_and_object_type["Aantal"].sum()) == counted["sum"]


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_typing_gate_matches_independent_count(pair: ReportPair, cfk: str) -> None:
    analysis = getattr(pair, cfk)
    counted = _independent_count(analysis.report.source_file)
    gate = analysis.typing_gate

    assert gate.named_object_count == counted["named"]
    assert gate.too_generic_count == counted["too_generic"]


def test_known_key_figures(pair: ReportPair) -> None:
    # Vastgelegde cijfers van de De Wolden-rapporten van 2026-08-14.
    assert pair.mds.total_count == 24938
    assert pair.hyd.total_count == 47440
    assert pair.mds.typing_gate.too_generic_count == 1228
    assert pair.mds.typing_gate.named_object_count == 10146
    assert pair.mds.typing_gate.score == pytest.approx(87.9, abs=0.05)
    assert pair.hyd.typing_gate.too_generic_count == 0


def test_reporting_on_full_files(pair: ReportPair, tmp_path: Path) -> None:
    markdown_path, csv_path = write_reports(pair, tmp_path)

    assert "DeWolden" in markdown_path.read_text(encoding="utf-8")
    assert csv_path.stat().st_size > 0
