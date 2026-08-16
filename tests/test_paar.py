"""Tests voor het laden en valideren van het rapportenpaar."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.fouten import RapportPaarFout
from gwswpijplijn.paar import laad_paar


def test_geldig_paar(mini_mds: Path, mini_hyd: Path) -> None:
    paar = laad_paar(mini_mds, mini_hyd)

    assert paar.dataset == "DeWolden"
    assert paar.mds.rapport.cfk == "MdsPlan"
    assert paar.hyd.rapport.cfk == "Hyd"
    assert paar.tijdstempels_verschillen is True


def test_verwisselde_paden_geven_fout(mini_mds: Path, mini_hyd: Path) -> None:
    with pytest.raises(RapportPaarFout, match="verwisseld"):
        laad_paar(mini_hyd, mini_mds)


def test_ontbrekende_hyd_geeft_fout(mini_mds: Path) -> None:
    with pytest.raises(RapportPaarFout, match="Hyd wordt verwacht"):
        laad_paar(mini_mds, mini_mds)


def test_verschillende_datasets_geven_fout(mini_mds: Path, mini_hyd_andere_dataset: Path) -> None:
    with pytest.raises(RapportPaarFout, match="verschillende datasets"):
        laad_paar(mini_mds, mini_hyd_andere_dataset)
