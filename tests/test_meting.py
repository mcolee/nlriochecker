"""Tests voor het samenstellen van een nulmeting uit SHACL-rapporten."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.errors import NulmetingError
from gwswpijplijn.meting import laad_nulmeting

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


def test_volledige_nulmeting(shacl_drieluik: list[Path]) -> None:
    meting = laad_nulmeting(shacl_drieluik, VEREIST)

    assert meting.dataset_file == "dewolden_orox.ttl"
    assert meting.cfks == ["Hyd", "MdsPlan", "MdsProj"]
    assert meting.timestamps_differ is True


def test_ontbrekende_cfk_is_een_harde_fout(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="mist conformiteitsklasse"):
        laad_nulmeting([mini_hyd_shacl], VEREIST)


def test_zonder_rapporten(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="minstens een"):
        laad_nulmeting([], VEREIST)


def test_dubbele_cfk(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="Twee rapporten voor CFK"):
        laad_nulmeting([mini_hyd_shacl, mini_hyd_shacl], ["Hyd"])


def test_verschillende_datasets(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    afwijkend = tmp_path / "ander.csv"
    tekst = shacl_drieluik[0].read_text(encoding="utf-8")
    afwijkend.write_text(
        tekst.replace("dewolden_orox.ttl", "andere_gemeente.ttl"), encoding="utf-8"
    )

    with pytest.raises(NulmetingError, match="verschillende RDF-bestanden"):
        laad_nulmeting([afwijkend, shacl_drieluik[1], shacl_drieluik[2]], VEREIST)


def test_eigen_eisenlijst(mini_hyd_shacl: Path) -> None:
    # De vereiste klassen komen uit de projectconfig, niet uit de code.
    meting = laad_nulmeting([mini_hyd_shacl], ["Hyd"])

    assert meting.cfks == ["Hyd"]
