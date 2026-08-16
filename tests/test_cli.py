"""Tests voor de opdrachtregel."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from gwswpijplijn.cli import main
from gwswpijplijn.reporting import (
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    FILE_OBJECT_CHANGES_CSV,
)


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


def test_dekking_schrijft_uitvoer(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "uitvoer"
    result = CliRunner().invoke(
        main,
        ["dekking", "--mds", str(mini_mds), "--hyd", str(mini_hyd), "--output", str(output_dir)],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / FILE_COVERAGE_MARKDOWN).exists()
    assert (output_dir / FILE_COVERAGE_CSV).exists()
    assert "RVZ-003   niet geraakt" in result.output
    assert "typeringsvoorbehoud" in result.output


def test_analyseer_meldt_niet_geraakte_checks(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    result = CliRunner().invoke(
        main,
        ["analyseer", "--mds", str(mini_mds), "--hyd", str(mini_hyd), "--output", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "Niet geraakte geschrapte checks: RVZ-002, RVZ-003" in result.output


def test_vergelijk_schrijft_uitvoer(
    mini_mds: Path,
    mini_hyd: Path,
    mini_mds_later: Path,
    mini_hyd_later: Path,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "uitvoer"
    result = CliRunner().invoke(
        main,
        [
            "vergelijk",
            "--eerder-mds",
            str(mini_mds),
            "--eerder-hyd",
            str(mini_hyd),
            "--later-mds",
            str(mini_mds_later),
            "--later-hyd",
            str(mini_hyd_later),
            "--output",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / FILE_COMPARISON_MARKDOWN).exists()
    assert (output_dir / FILE_OBJECT_CHANGES_CSV).exists()
    assert "2 opgelost / 1 nieuw / 14 gebleven" in result.output
    assert "Dekking RVZ-003: niet geraakt -> geraakt" in result.output


def test_onbekende_config_geeft_exitcode_1(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    ontbrekend = tmp_path / "bestaat_niet.toml"
    result = CliRunner().invoke(
        main,
        [
            "dekking",
            "--mds",
            str(mini_mds),
            "--hyd",
            str(mini_hyd),
            "--config",
            str(ontbrekend),
            "--output",
            str(tmp_path),
        ],
    )

    # click controleert het bestaan van --config al; exitcode 2 is de gebruiksfout.
    assert result.exit_code == 2


def test_ongeldige_config_geeft_exitcode_1(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text("dit is [geen geldige toml", encoding="utf-8")
    result = CliRunner().invoke(
        main,
        [
            "dekking",
            "--mds",
            str(mini_mds),
            "--hyd",
            str(mini_hyd),
            "--config",
            str(stuk),
            "--output",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "geldige TOML" in result.output
