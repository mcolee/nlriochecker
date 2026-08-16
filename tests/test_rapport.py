"""Tests voor de parser van detailrapporten."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.fouten import RapportFormaatFout
from gwswpijplijn.rapport import KOLOMMEN, lees_detailrapport


def test_metadata_uit_titelregel(mini_mds: Path) -> None:
    rapport = lees_detailrapport(mini_mds)

    assert rapport.dataset == "DeWolden"
    assert rapport.cfk == "MdsPlan"
    assert rapport.tijdstempel == datetime(2026, 8, 14, 14, 6, 53)
    assert rapport.bronbestand == mini_mds


def test_hyd_titelregel(mini_hyd: Path) -> None:
    rapport = lees_detailrapport(mini_hyd)

    assert rapport.cfk == "Hyd"
    assert rapport.tijdstempel == datetime(2026, 8, 14, 14, 30, 6)


def test_kolommen_en_datatypes(mini_mds: Path) -> None:
    meldingen = lees_detailrapport(mini_mds).meldingen

    assert list(meldingen.columns) == KOLOMMEN
    assert pd.api.types.is_integer_dtype(meldingen["Aantal"])
    assert len(meldingen) == 20


def test_lege_naam_blijft_lege_tekst(mini_mds: Path) -> None:
    meldingen = lees_detailrapport(mini_mds).meldingen
    zonder_naam = meldingen[meldingen["Type Melding"] == "Collectie-item onbekend"]

    assert list(zonder_naam["Naam"]) == [""]
    assert not meldingen["Naam"].isna().any()


def test_onherkenbare_titelregel_geeft_fout(mini_kapot: Path) -> None:
    with pytest.raises(RapportFormaatFout, match="niet herkend"):
        lees_detailrapport(mini_kapot)


def test_leeg_bestand_geeft_fout(tmp_path: Path) -> None:
    leeg = tmp_path / "leeg.csv"
    leeg.write_text("", encoding="cp1252")

    with pytest.raises(RapportFormaatFout, match="leeg"):
        lees_detailrapport(leeg)


def test_niet_numeriek_aantal_geeft_fout(mini_mds: Path, tmp_path: Path) -> None:
    regels = mini_mds.read_text(encoding="cp1252").splitlines()
    regels[2] = regels[2].replace("33;", "veel;", 1)
    stuk = tmp_path / "stuk.csv"
    stuk.write_text("\n".join(regels) + "\n", encoding="cp1252")

    with pytest.raises(RapportFormaatFout, match="Aantal"):
        lees_detailrapport(stuk)
