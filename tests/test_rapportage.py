"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.fouten import GwswPijplijnFout
from gwswpijplijn.paar import laad_paar
from gwswpijplijn.rapportage import BESTAND_CSV, BESTAND_MARKDOWN, schrijf_rapportage


def test_schrijft_beide_bestanden(mini_mds: Path, mini_hyd: Path, tmp_path: Path) -> None:
    paar = laad_paar(mini_mds, mini_hyd)
    markdown_pad, csv_pad = schrijf_rapportage(paar, tmp_path / "uitvoer")

    assert markdown_pad.name == BESTAND_MARKDOWN
    assert csv_pad.name == BESTAND_CSV
    assert markdown_pad.exists()
    assert csv_pad.exists()


def test_markdown_bevat_dataset_en_typeringsscore(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    paar = laad_paar(mini_mds, mini_hyd)
    markdown_pad, _ = schrijf_rapportage(paar, tmp_path)
    tekst = markdown_pad.read_text(encoding="utf-8")

    assert "DeWolden" in tekst
    assert "## Typeringspoort" in tekst
    assert "| MdsPlan | 75.0% | 4 | 16 |" in tekst
    assert "ondergrens" in tekst


def test_csv_bevat_beide_cfks_en_klopt_qua_som(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    paar = laad_paar(mini_mds, mini_hyd)
    _, csv_pad = schrijf_rapportage(paar, tmp_path)
    tabel = pd.read_csv(csv_pad, sep=";", encoding="utf-8")

    assert list(tabel.columns) == ["CFK", "Type Melding", "Type object", "Aantal", "Regels"]
    assert set(tabel["CFK"]) == {"MdsPlan", "Hyd"}
    assert tabel.loc[tabel["CFK"] == "MdsPlan", "Aantal"].sum() == paar.mds.totaal_aantal
    assert tabel.loc[tabel["CFK"] == "Hyd", "Aantal"].sum() == paar.hyd.totaal_aantal


def test_uitvoer_overschrijft_nooit_de_invoer(
    mini_mds: Path, mini_hyd: Path, tmp_path: Path
) -> None:
    invoermap = tmp_path / "invoer"
    invoermap.mkdir()
    mds = invoermap / BESTAND_MARKDOWN
    mds.write_bytes(mini_mds.read_bytes())
    hyd = invoermap / "mini_hyd.csv"
    hyd.write_bytes(mini_hyd.read_bytes())
    paar = laad_paar(mds, hyd)

    with pytest.raises(GwswPijplijnFout, match="invoerbestand"):
        schrijf_rapportage(paar, invoermap)
