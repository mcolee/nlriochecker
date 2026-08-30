"""Tests voor het inlezen van SHACL-nulmetingrapporten."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from nlriochecker.errors import ReportFormatError
from nlriochecker.shaclrapport import KOLOMMEN, lees_shacl_rapport

SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"


def test_kopblok(mini_hyd_shacl: Path) -> None:
    rapport = lees_shacl_rapport(mini_hyd_shacl)

    assert rapport.cfk == "Hyd"
    assert rapport.dataset_file == "dewolden_orox.ttl"
    assert rapport.timestamp == datetime(2026, 8, 16, 12, 51, 51)
    assert rapport.processor == "TopBraid 1.4.4"
    assert rapport.conforms is False
    assert "Kardinaliteit" in rapport.validated_parts
    assert "Verbindingen netwerk" in rapport.validated_parts


def test_kolommen_en_afgeleide_velden(mini_hyd_shacl: Path) -> None:
    meldingen = lees_shacl_rapport(mini_hyd_shacl).findings

    assert list(meldingen.columns) == [*KOLOMMEN, "Objecttype", "Label"]
    assert set(meldingen["Severity"]) <= {"Violation", "Warning"}
    # Label en Objecttype komen uit Detail-value; ontbreekt dat, dan blijven ze leeg.
    netwerk = meldingen[meldingen["Source"] == "Knooppunt_Netwerk_conn"].iloc[0]
    assert netwerk["Objecttype"] != ""
    assert netwerk["Label"] != ""


def test_focus_node_is_het_object(mini_hyd_shacl: Path) -> None:
    meldingen = lees_shacl_rapport(mini_hyd_shacl).findings
    netwerk = meldingen[meldingen["Source"] == "Knooppunt_Netwerk_conn"].iloc[0]

    # De focus node is het URI-fragment uit de dataset, niet het label.
    assert netwerk["Focus node"].startswith("knp")
    assert netwerk["Focus node"] != netwerk["Label"]


@pytest.mark.parametrize(
    ("bestand", "klassen"),
    [
        ("mini_hyd.csv", ["Rioolstelsel"]),
        ("mini_mdsplan.csv", ["MechanischRioolstelsel", "Overstortput", "Rioolstelsel"]),
        ("mini_mdsproj.csv", ["MechanischRioolstelsel", "Rioolstelsel"]),
    ],
)
def test_te_globale_klassen_per_cfk(bestand: str, klassen: list[str]) -> None:
    """SHACL meldt de typering per klasse, niet per object."""
    rapport = lees_shacl_rapport(SHACL_DIR / bestand)

    assert rapport.too_generic_classes == klassen


def test_ontbrekende_kolomkop(tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.csv"
    stuk.write_text("Rapport SHACL-meting dd;2026-01-01T00:00:00\n", encoding="utf-8")

    with pytest.raises(ReportFormatError, match="geen kolomkop"):
        lees_shacl_rapport(stuk)


def test_ontbrekende_cfk(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    regels = mini_hyd_shacl.read_text(encoding="utf-8").splitlines()
    zonder = [r for r in regels if not r.startswith("SHACL-meting op basis CFK")]
    stuk = tmp_path / "zonder_cfk.csv"
    stuk.write_text("\n".join(zonder), encoding="utf-8")

    with pytest.raises(ReportFormatError, match="CFK"):
        lees_shacl_rapport(stuk)


def test_ongeldig_tijdstempel(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    tekst = mini_hyd_shacl.read_text(encoding="utf-8").replace("2026-08-16T12:51:51", "gisteren")
    stuk = tmp_path / "stuk.csv"
    stuk.write_text(tekst, encoding="utf-8")

    with pytest.raises(ReportFormatError, match="ISO-datum"):
        lees_shacl_rapport(stuk)


def test_ontbrekend_bestand(tmp_path: Path) -> None:
    with pytest.raises(ReportFormatError, match="kan niet gelezen worden"):
        lees_shacl_rapport(tmp_path / "weg.csv")


def test_veld_boven_de_csv_veldgrens(tmp_path: Path) -> None:
    """Een veld boven `csv.field_size_limit()` gaf een kale `_csv.Error`."""
    stuk = tmp_path / "reuzenveld.csv"
    reus = "A" * (csv.field_size_limit() + 1)
    stuk.write_text(f'Focus node;Source\n"{reus}";x\n', encoding="utf-8")

    with pytest.raises(ReportFormatError, match="geen leesbare CSV"):
        lees_shacl_rapport(stuk)


def test_lege_meldingtabel(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    regels = mini_hyd_shacl.read_text(encoding="utf-8").splitlines()
    kop = next(i for i, r in enumerate(regels) if r.startswith("Focus node"))
    leeg = tmp_path / "leeg.csv"
    leeg.write_text("\n".join(regels[: kop + 1]), encoding="utf-8")

    rapport = lees_shacl_rapport(leeg)

    assert rapport.findings.empty
    assert isinstance(rapport.findings, pd.DataFrame)
    assert rapport.too_generic_classes == []
