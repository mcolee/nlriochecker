"""Gedeelde fixtures voor de testsuite."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_mds() -> Path:
    """Pad naar het kleine MdsPlan-uittreksel."""
    return FIXTURE_DIR / "mini_mdsplan.csv"


@pytest.fixture
def mini_hyd() -> Path:
    """Pad naar het kleine Hyd-uittreksel."""
    return FIXTURE_DIR / "mini_hyd.csv"


@pytest.fixture
def mini_hyd_other_dataset() -> Path:
    """Hyd-uittreksel met een afwijkende datasetnaam in de titelregel."""
    return FIXTURE_DIR / "mini_hyd_other_dataset.csv"


@pytest.fixture
def mini_broken() -> Path:
    """Uittreksel met een onherkenbare titelregel."""
    return FIXTURE_DIR / "mini_broken.csv"


@pytest.fixture
def mini_mds_later() -> Path:
    """MdsPlan-uittreksel van een later meetmoment, met bekende verschillen."""
    return FIXTURE_DIR / "mini_mdsplan_later.csv"


@pytest.fixture
def mini_hyd_later() -> Path:
    """Hyd-uittreksel van een later meetmoment, met bekende verschillen."""
    return FIXTURE_DIR / "mini_hyd_later.csv"
