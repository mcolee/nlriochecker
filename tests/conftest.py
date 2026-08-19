"""Gedeelde fixtures voor de testsuite, en de waarborg tegen stille overslagen."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from nlriochecker.dataset import GwswDataset, load_dataset

# Een schone kloon heeft `data/` niet: die map staat buiten versiebeheer omdat de
# OroX-export en de GIS-bronnen gigabytes beslaan. De tests die erop leunen slaan
# dan over, en de run blijft groen terwijl er nauwelijks iets getoetst is. Zet deze
# variabele (CI doet dat) om een ondergrens aan het aantal geslaagde tests te eisen.
MINIMUM_ENV = "NLRIOCHECKER_MIN_GESLAAGD"

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


MINIREGISTER = """# Checkregister

Versie 99.9, werkdocument.

## ADM: Administratief

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| ADM-002 | Dubbele identificatie | F | Consistentie |

## Geschrapte checks

| ID | Check | Gedekt door |
|---|---|---|
| ADM-001 | Streng verwijst naar niet-bestaande begin- of eindput | verzonnen sentinel |
"""


@pytest.fixture
def mapping_zonder_bewijs(tmp_path: Path) -> Path:
    """Een dekkingmapping waarvan de enige sentinel nergens een melding oplevert.

    De meegeleverde `dekking.toml` raakt elke geschrapte check, ook op de
    mini-nulmeting; daarmee is er geen echte run meer waarin "niet geraakt" te zien
    is. Deze mapping toont die weergave zonder dat er een gat in de dekking van het
    project voor nodig is. Het bijgeleverde miniregister hoort erbij, zodat de ijking
    van mapping tegen register klopt.
    """
    register = tmp_path / "miniregister.md"
    register.write_text(MINIREGISTER, encoding="utf-8")
    pad = tmp_path / "dekking-zonder-bewijs.toml"
    pad.write_text(
        'checkregister_versie = "99.9"\n'
        f'bron = "{register}"\n'
        "[[check]]\n"
        'id = "ADM-001"\n'
        'onderwerp = "Streng verwijst naar niet-bestaande begin- of eindput"\n'
        'claim = "verzonnen sentinel"\n'
        'vereiste_cfk = ["Hyd", "MdsPlan", "MdsProj"]\n'
        'bewijs = [{ vorm_prefix = "BestaatNiet" }]\n',
        encoding="utf-8",
    )
    return pad


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Laat de run alsnog vallen als er te weinig tests echt gedraaid hebben.

    Zonder deze controle leest een run met een halve suite als volledig groen. Zonder
    `MINIMUM_ENV` gebeurt er niets, zodat een lokale run op een deelselectie
    (`pytest tests/test_dataset.py`) gewoon werkt.

    De grens ligt op wat een schone kloon haalt; hij vangt dus geen ontbrekende `data/`
    op -- die haalt de grens ruim -- maar wel het wegvallen van meer dan dat.
    """
    drempel = os.environ.get(MINIMUM_ENV)
    if not drempel or session.config.option.collectonly:
        return

    rapporteur = session.config.pluginmanager.get_plugin("terminalreporter")
    if rapporteur is None:
        return

    try:
        minimum = int(drempel)
    except ValueError:
        rapporteur.write_line(
            f"{MINIMUM_ENV}={drempel!r} is geen getal; grens genegeerd.", red=True
        )
        return

    geslaagd = len(rapporteur.stats.get("passed", []))
    if geslaagd >= minimum:
        return

    overgeslagen = len(rapporteur.stats.get("skipped", []))
    rapporteur.write_line(
        f"{MINIMUM_ENV}={minimum}, maar er slaagden er {geslaagd} "
        f"({overgeslagen} overgeslagen). Staat data/ op zijn plek?",
        red=True,
    )
    # Een bestaande foutcode is specifieker dan de onze; die blijft staan.
    if session.exitstatus == 0:
        session.exitstatus = 1
