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
# De ondergrens hierboven meet "geslaagd" en kruipt met de suite mee omhoog. Wat de poort
# wil vangen is stille overslag: een fixture die niet meekomt, een generator die niet
# gedraaid is, een tool die op de runner ontbreekt. Een telgrens op "overgeslagen"
# (`NLRIOCHECKER_MAX_OVERGESLAGEN`, tot 2026-08-25) ving dat, maar telde ook de bedoelde,
# datagebonden overslagen mee -- de ontologie, het Juinen-voorbeeld en de SHACL-rapporten
# staan niet op de runner -- en klapte daardoor twee keer op legitieme testgroei. Daarom
# classificeert de poort nu op *reden*: een overslag is verwacht als zijn reden zegt waar
# hij vandaan komt. Al het andere is met deze vlag gezet een harde fout, zonder getal om
# te herijken (BO-48).
STRIKT_ENV = "NLRIOCHECKER_STRIKTE_OVERSLAG"
# Wat een reden verwacht maakt: `data/` (echte data die op de runner ontbreekt -- elke
# datagebonden skip hoort die map te noemen) of een BO-nummer (een bewuste uitzondering
# met besluit, zoals BO-40 in test_gwsw_vocabulaire.py).
VERWACHTE_REDENEN = ("data/", "BO-")
# Een `pytest.skip(allow_module_level=True)` viel tussen wal en schip (issue #52): die
# telt als één overslag hoeveel tests de module ook draagt, dus liet de vervallen
# telgrens een hele weggevallen module lopen en zou de ondergrens op een zeer krappe,
# brosse waarde moeten staan om hem te vangen. Deze derde grens telt uitsluitend de
# modulewijde overslagen, hangt niet aan de omvang van de suite en veroudert dus niet
# mee. Modulewijde overslagen zijn in `stats["skipped"]` te herkennen: ze komen als
# `CollectReport`, test-overslagen als `TestReport`.
MAXIMUM_MODULE_OVERGESLAGEN_ENV = "NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN"

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


def _modulewijde_overslagen(overgeslagen: list[object]) -> int:
    """Telt de overslagen die een hele module afhaken, niet de losse test-skips.

    Een `pytest.skip(allow_module_level=True)` levert een `CollectReport`, een
    test-skip een `TestReport`; beide belanden in `rapporteur.stats["skipped"]`. Alleen
    de eerste soort telt hier mee, zodat de grens niet meebeweegt met het aantal tests
    dat in zo'n module zit.
    """
    return sum(1 for rapport in overgeslagen if isinstance(rapport, pytest.CollectReport))


def _reden(rapport: object) -> str:
    """De overslagreden uit een rapport.

    pytest zet hem bij een overslag in `longrepr` als `(pad, regel, "Skipped: <reden>")`;
    het voorvoegsel gaat eraf zodat de classificatie op de reden zelf werkt.
    """
    longrepr = getattr(rapport, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2]).removeprefix("Skipped: ")
    return str(longrepr or "")


def _onverwachte_overslagen(overgeslagen: list[object]) -> list[tuple[str, str]]:
    """De test-overslagen waarvan de reden niet zegt dat ze verwacht zijn, als (nodeid, reden).

    Alleen `TestReport`s: een modulewijde overslag is een `CollectReport` en hoort bij de
    modulegrens. Verwacht is een reden die een merk uit `VERWACHTE_REDENEN` draagt.
    """
    return [
        (rapport.nodeid, _reden(rapport))
        for rapport in overgeslagen
        if isinstance(rapport, pytest.TestReport)
        and not any(merk in _reden(rapport) for merk in VERWACHTE_REDENEN)
    ]


def _strikt() -> bool:
    """Of de strikte overslagcontrole aanstaat.

    Niet gezet of leeg is uit, en "0" ook. Een kale `os.environ.get` zou "0" als aan
    lezen, zodat een run die de vlag bewust uitzet hem juist ingeschakeld kreeg.
    """
    return os.environ.get(STRIKT_ENV, "") not in ("", "0")


def _grens(naam: str, rapporteur: pytest.TerminalReporter) -> int | None:
    """De waarde van een grensvariabele, of None als hij niet gezet of onleesbaar is."""
    waarde = os.environ.get(naam)
    if not waarde:
        return None
    try:
        return int(waarde)
    except ValueError:
        rapporteur.write_line(f"{naam}={waarde!r} is geen getal; grens genegeerd.", red=True)
        return None


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Laat de run alsnog vallen als er te weinig tests echt gedraaid hebben.

    Zonder deze controle leest een run met een halve suite als volledig groen. Zonder
    de twee grensvariabelen gebeurt er niets, zodat een lokale run op een deelselectie
    (`pytest tests/test_dataset.py`) gewoon werkt.

    De ondergrens ligt op wat een schone kloon haalt; hij vangt dus geen ontbrekende
    `data/` op -- die haalt de grens ruim -- maar wel het wegvallen van meer dan dat.
    De strikte overslagcontrole doet het omgekeerde: zij hangt niet aan een aantal maar
    aan de reden van elke overslag, en veroudert dus niet met de suite mee.
    """
    if session.config.option.collectonly:
        return

    rapporteur = session.config.pluginmanager.get_plugin("terminalreporter")
    if rapporteur is None:
        return

    overgeslagen_rapporten = rapporteur.stats.get("skipped", [])
    geslaagd = len(rapporteur.stats.get("passed", []))
    overgeslagen = len(overgeslagen_rapporten)
    modulewijd = _modulewijde_overslagen(overgeslagen_rapporten)
    minimum = _grens(MINIMUM_ENV, rapporteur)
    maximum_module = _grens(MAXIMUM_MODULE_OVERGESLAGEN_ENV, rapporteur)

    gezakt = False
    if minimum is not None and geslaagd < minimum:
        rapporteur.write_line(
            f"{MINIMUM_ENV}={minimum}, maar er slaagden er {geslaagd} "
            f"({overgeslagen} overgeslagen). Staat data/ op zijn plek?",
            red=True,
        )
        gezakt = True
    if _strikt():
        onverwacht = _onverwachte_overslagen(overgeslagen_rapporten)
        if onverwacht:
            rapporteur.write_line(
                f"{STRIKT_ENV} staat aan, maar {len(onverwacht)} overslagen hebben een reden "
                "die niet zegt dat ze verwacht zijn. Noem `data/` in de reden als de test echte "
                "data nodig heeft, of het BO-nummer van de bewuste uitzondering; is het geen van "
                "beide, dan is er een fixture, generator of tool weggevallen:",
                red=True,
            )
            for nodeid, reden in onverwacht:
                rapporteur.write_line(f"  {nodeid}: {reden or '(geen reden opgegeven)'}", red=True)
            gezakt = True
    if maximum_module is not None and modulewijd > maximum_module:
        rapporteur.write_line(
            f"{MAXIMUM_MODULE_OVERGESLAGEN_ENV}={maximum_module}, maar er haakten er "
            f"{modulewijd} modulewijd af (pytest.skip(allow_module_level=True)). Een hele "
            "module die overslaat telt in de gewone grens als één; kwam er een bij, dan is "
            "een fixture of bron weggevallen. Draai met -rs om te zien welke.",
            red=True,
        )
        gezakt = True

    # Een bestaande foutcode is specifieker dan de onze; die blijft staan.
    if gezakt and session.exitstatus == 0:
        session.exitstatus = 1
