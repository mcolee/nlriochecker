"""Gedeelde fixtures voor de testsuite."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTUREMAP = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_mds() -> Path:
    """Pad naar het kleine MdsPlan-uittreksel."""
    return FIXTUREMAP / "mini_mdsplan.csv"


@pytest.fixture
def mini_hyd() -> Path:
    """Pad naar het kleine Hyd-uittreksel."""
    return FIXTUREMAP / "mini_hyd.csv"


@pytest.fixture
def mini_hyd_andere_dataset() -> Path:
    """Hyd-uittreksel met een afwijkende datasetnaam in de titelregel."""
    return FIXTUREMAP / "mini_hyd_andere_dataset.csv"


@pytest.fixture
def mini_kapot() -> Path:
    """Uittreksel met een onherkenbare titelregel."""
    return FIXTUREMAP / "mini_kapot.csv"
