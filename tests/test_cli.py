"""Tests voor de opdrachtregel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from gwswpijplijn.cli import main
from gwswpijplijn.reporting import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_MARKDOWN,
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    FILE_OBJECT_CHANGES_CSV,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"


def _shacl_args(paden: list[Path]) -> list[str]:
    """Bouwt de --shacl-argumenten voor een volledige nulmeting."""
    return [arg for pad in paden for arg in ("--shacl", str(pad))]


def test_analyseer_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["analyseer", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_MARKDOWN).exists()
    assert (uitvoer / FILE_CSV).exists()
    assert "Hyd, MdsPlan, MdsProj" in resultaat.output
    assert "Niet geraakte geschrapte checks: RVZ-002, RVZ-003" in resultaat.output


def test_ontbrekende_cfk_geeft_exitcode_1(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main, ["analyseer", "--shacl", str(mini_hyd_shacl), "--output", str(tmp_path)]
    )

    assert resultaat.exit_code == 1
    assert "mist conformiteitsklasse" in resultaat.output


def test_dekking_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["dekking", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_COVERAGE_MARKDOWN).exists()
    assert (uitvoer / FILE_COVERAGE_CSV).exists()
    assert "RVZ-003   niet geraakt" in resultaat.output


def test_vergelijk_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    argumenten = ["vergelijk"]
    for pad in shacl_drieluik:
        argumenten += ["--eerder", str(pad), "--later", str(pad)]
    resultaat = CliRunner().invoke(main, [*argumenten, "--output", str(uitvoer)])

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_COMPARISON_MARKDOWN).exists()
    assert (uitvoer / FILE_OBJECT_CHANGES_CSV).exists()
    assert "niet nieuwer dan de eerste" in resultaat.output


def test_toets_schrijft_uitvoer(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_CSV).exists()
    assert "Geen typeringspoort toegepast" in resultaat.output
    assert "TOP-001   F      1 bevindingen" in resultaat.output


def test_toets_met_studiegebied_meldt_wat_wegvalt(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--studiegebied",
            str(GIS_DIR / "vierkant.gpkg"),
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "Studiegebied" in resultaat.output
    assert "1 bevindingen buiten het gebied weggelaten" in resultaat.output
    tabel = pd.read_csv(uitvoer / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    assert tabel.empty


def test_toets_gebruikt_shacl_voor_de_typeringspoort(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    bron = (TTL_DIR / "top001_losliggende_put.ttl").read_text(encoding="utf-8")
    bron += "\n:PutC rdf:type gwsw:Overstortput .\ngwsw:Overstortput rdfs:subClassOf gwsw:Put .\n"
    dataset = tmp_path / "met_overstortput.ttl"
    dataset.write_text(bron, encoding="utf-8")

    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(dataset),
            *_shacl_args(shacl_drieluik),
            "--check",
            "TOP-001",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "met typeringsvoorbehoud" in resultaat.output


def test_toets_meldt_onbekende_check(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--check",
            "TOP-999",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 1
    assert "TOP-999" in resultaat.output
    assert "Bekende checks" in resultaat.output


def test_toets_meldt_onleesbare_dataset(tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.ttl"
    stuk.write_text("dit is <geen turtle", encoding="utf-8")

    resultaat = CliRunner().invoke(
        main, ["toets", "--dataset", str(stuk), "--output", str(tmp_path)]
    )

    assert resultaat.exit_code == 1
    assert "geldige Turtle" in resultaat.output


def test_toets_meldt_afwijkende_codering(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "codering_cp850.ttl"),
            "--check",
            "TOP-001",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "geen geldige UTF-8" in resultaat.output


def test_ongeldige_config_geeft_exitcode_1(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text("dit is [geen geldige toml", encoding="utf-8")

    resultaat = CliRunner().invoke(
        main,
        [
            "dekking",
            *_shacl_args(shacl_drieluik),
            "--config",
            str(stuk),
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 1
    assert "geldige TOML" in resultaat.output
