"""Tests voor het laden en valideren van het rapportenpaar."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.errors import ReportPairError
from gwswpijplijn.pair import load_pair


def test_valid_pair(mini_mds: Path, mini_hyd: Path) -> None:
    pair = load_pair(mini_mds, mini_hyd)

    assert pair.dataset == "DeWolden"
    assert pair.mds.report.cfk == "MdsPlan"
    assert pair.hyd.report.cfk == "Hyd"
    assert pair.timestamps_differ is True


def test_swapped_paths_raise(mini_mds: Path, mini_hyd: Path) -> None:
    with pytest.raises(ReportPairError, match="verwisseld"):
        load_pair(mini_hyd, mini_mds)


def test_missing_hyd_raises(mini_mds: Path) -> None:
    with pytest.raises(ReportPairError, match="Hyd wordt verwacht"):
        load_pair(mini_mds, mini_mds)


def test_different_datasets_raise(mini_mds: Path, mini_hyd_other_dataset: Path) -> None:
    with pytest.raises(ReportPairError, match="verschillende datasets"):
        load_pair(mini_mds, mini_hyd_other_dataset)
