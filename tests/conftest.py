"""Gedeelde fixtures voor de testsuite."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.dataset import GwswDataset, load_dataset

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TTL_DIR = FIXTURE_DIR / "ttl"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OROX_DIR = DATA_DIR / "gwsw_orox_ttl"
ONTOLOGIE_DIR = DATA_DIR / "gwsw_ontologieen"
VOORBEELD_TTL = OROX_DIR / "GwswDataset__Voorbeeld_v1_6_orox.ttl"
# De deelmodellen Mds en Hyd zijn filters op het totaalmodel; alleen de
# totaal-ontologie kent alle Knooppunt- en Verbinding-klassen.
ONTOLOGIE_TTL = ONTOLOGIE_DIR / "Ontologie_GWSW_Totaal.ttl"


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


@pytest.fixture(scope="session")
def ontologie() -> list[Path]:
    """De GWSW-Mds-ontologie, voor de klassenhierarchie."""
    if not ONTOLOGIE_TTL.exists():
        pytest.skip("de GWSW-ontologie staat niet in data/")
    return [ONTOLOGIE_TTL]


@pytest.fixture(scope="session")
def juinen(ontologie: list[Path]) -> GwswDataset:
    """Het meegeleverde Juinen-voorbeeld als schone referentiedataset."""
    if not VOORBEELD_TTL.exists():
        pytest.skip("het OroX-voorbeeldbestand staat niet in data/")
    return load_dataset(VOORBEELD_TTL, ontologie)
