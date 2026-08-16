"""Tests voor de opdrachtregel."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gwswpijplijn.cli import main
from gwswpijplijn.reporting import FILE_CSV, FILE_MARKDOWN


def test_analyseer_writes_output(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "uitvoer"
    result = CliRunner().invoke(
        main,
        ["analyseer", "--mds", str(mini_mds), "--hyd", str(mini_hyd), "--output", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / FILE_MARKDOWN).exists()
    assert (output_dir / FILE_CSV).exists()
    assert "typeringsscore 75.0%" in result.output


def test_swapped_paths_give_exit_code_1(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["analyseer", "--mds", str(mini_hyd), "--hyd", str(mini_mds), "--output", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "verwisseld" in result.output


def test_missing_file_gives_usage_error(mini_mds: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
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

    assert result.exit_code == 2
