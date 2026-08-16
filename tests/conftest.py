"""Gedeelde fixtures voor de testsuite."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.dataset import GwswDataset, load_dataset

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TTL_DIR = FIXTURE_DIR / "ttl"
SHACL_DIR = FIXTURE_DIR / "shacl"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OROX_DIR = DATA_DIR / "gwsw_orox_ttl"
ONTOLOGIE_DIR = DATA_DIR / "gwsw_ontologieen"
VOORBEELD_TTL = OROX_DIR / "GwswDataset__Voorbeeld_v1_6_orox.ttl"
# De deelmodellen Mds en Hyd zijn filters op het totaalmodel; alleen de
# totaal-ontologie kent alle Knooppunt- en Verbinding-klassen.
ONTOLOGIE_TTL = ONTOLOGIE_DIR / "Ontologie_GWSW_Totaal.ttl"


@pytest.fixture(scope="session")
def ontologie() -> list[Path]:
    """De GWSW-totaalontologie, voor de klassenhierarchie."""
    if not ONTOLOGIE_TTL.exists():
        pytest.skip("de GWSW-ontologie staat niet in data/")
    return [ONTOLOGIE_TTL]


@pytest.fixture(scope="session")
def juinen(ontologie: list[Path]) -> GwswDataset:
    """Het meegeleverde Juinen-voorbeeld als schone referentiedataset."""
    if not VOORBEELD_TTL.exists():
        pytest.skip("het OroX-voorbeeldbestand staat niet in data/")
    return load_dataset(VOORBEELD_TTL, ontologie)


@pytest.fixture
def mini_hyd_shacl() -> Path:
    """Klein SHACL-rapport voor CFK Hyd."""
    return SHACL_DIR / "mini_hyd.csv"


@pytest.fixture
def mini_mdsplan_shacl() -> Path:
    """Klein SHACL-rapport voor CFK MdsPlan."""
    return SHACL_DIR / "mini_mdsplan.csv"


@pytest.fixture
def mini_mdsproj_shacl() -> Path:
    """Klein SHACL-rapport voor CFK MdsProj."""
    return SHACL_DIR / "mini_mdsproj.csv"


@pytest.fixture
def shacl_drieluik(
    mini_hyd_shacl: Path, mini_mdsplan_shacl: Path, mini_mdsproj_shacl: Path
) -> list[Path]:
    """De drie SHACL-rapporten die samen een volledige nulmeting vormen."""
    return [mini_hyd_shacl, mini_mdsplan_shacl, mini_mdsproj_shacl]
