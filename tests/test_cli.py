"""Tests voor de opdrachtregel."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gwswpijplijn.cli import main
from gwswpijplijn.rapportage import BESTAND_CSV, BESTAND_MARKDOWN


def test_analyseer_schrijft_uitvoer(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        ["analyseer", "--mds", str(mini_mds), "--hyd", str(mini_hyd), "--output", str(uitvoer)],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / BESTAND_MARKDOWN).exists()
    assert (uitvoer / BESTAND_CSV).exists()
    assert "typeringsscore 75.0%" in resultaat.output


def test_verwisselde_paden_geven_exitcode_1(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        ["analyseer", "--mds", str(mini_hyd), "--hyd", str(mini_mds), "--output", str(tmp_path)],
    )

    assert resultaat.exit_code == 1
    assert "verwisseld" in resultaat.output


def test_ontbrekend_bestand_geeft_gebruiksfout(mini_mds: Path, tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer",
            "--mds",
            str(mini_mds),
            "--hyd",
            str(tmp_path / "bestaat_niet.csv"),
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 2
