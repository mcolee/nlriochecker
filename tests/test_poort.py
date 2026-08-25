"""Tests voor de CI-poort tegen stille overslagen (`conftest.py`)."""

from __future__ import annotations

import pytest

from conftest import STRIKT_ENV, _modulewijde_overslagen, _onverwachte_overslagen, _reden, _strikt


def test_modulewijde_overslag_telt_alleen_collectreports() -> None:
    """Een `pytest.skip(allow_module_level=True)` komt als `CollectReport`, een
    test-skip als `TestReport` (issue #52).

    De gewone overslaggrens telt beide als één en beweegt mee met suitegroei; een
    aparte bovengrens op modulewijde overslagen vangt exact een fixturemap die niet
    meekomt en veroudert niet. Deze helper is de plek waar dat onderscheid valt.
    """
    modulewijd = pytest.CollectReport(
        nodeid="tests/test_iets.py", outcome="skipped", longrepr=None, result=[]
    )
    losse_test = pytest.TestReport(
        nodeid="tests/test_iets.py::test_x",
        location=("tests/test_iets.py", 0, "test_x"),
        keywords={},
        outcome="skipped",
        longrepr=None,
        when="call",
    )

    assert _modulewijde_overslagen([modulewijd, losse_test, modulewijd]) == 2
    assert _modulewijde_overslagen([losse_test, losse_test]) == 0
    assert _modulewijde_overslagen([]) == 0


def _overslag(nodeid: str, reden: str) -> pytest.TestReport:
    """Een test-overslag zoals pytest hem rapporteert: longrepr = (pad, regel, 'Skipped: reden')."""
    return pytest.TestReport(
        nodeid=nodeid,
        location=(nodeid.split("::")[0], 1, nodeid.split("::")[-1]),
        keywords={},
        outcome="skipped",
        longrepr=(nodeid.split("::")[0], 1, f"Skipped: {reden}"),
        when="setup",
    )


def test_reden_komt_uit_longrepr_zonder_voorvoegsel() -> None:
    overslag = _overslag("tests/test_x.py::test_a", "de GWSW-ontologie staat niet in data/")

    assert _reden(overslag) == "de GWSW-ontologie staat niet in data/"


def test_alleen_een_onverklaarde_overslag_is_onverwacht() -> None:
    """`data/` en een BO-nummer verklaren een overslag; een fixture die ontbreekt niet.

    Modulewijde overslagen (CollectReport) horen bij de modulegrens en tellen hier niet.
    """
    rapporten = [
        _overslag("tests/test_dataset.py::test_a", "de GWSW-ontologie staat niet in data/"),
        _overslag(
            "tests/test_gwsw_vocabulaire.py::test_b", "ontbreekt in de ontologie; bewust, zie BO-40"
        ),
        _overslag(
            "tests/test_checks_extern.py::test_c",
            "de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
        ),
        pytest.CollectReport(
            nodeid="tests/test_uitvoer_qgis.py", outcome="skipped", longrepr=None, result=[]
        ),
    ]

    assert _onverwachte_overslagen(rapporten) == [
        (
            "tests/test_checks_extern.py::test_c",
            "de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
        )
    ]


def test_de_vlag_staat_uit_bij_leeg_en_bij_nul(monkeypatch: pytest.MonkeyPatch) -> None:
    """`NLRIOCHECKER_STRIKTE_OVERSLAG=0` hoort uit te staan.

    Een kale `os.environ.get` leest de string "0" als aan; wie de vlag bewust uitzet zou
    de controle dan juist ingeschakeld krijgen.
    """
    monkeypatch.setenv(STRIKT_ENV, "1")
    assert _strikt() is True

    monkeypatch.setenv(STRIKT_ENV, "0")
    assert _strikt() is False

    monkeypatch.setenv(STRIKT_ENV, "")
    assert _strikt() is False

    monkeypatch.delenv(STRIKT_ENV)
    assert _strikt() is False
