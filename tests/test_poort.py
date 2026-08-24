"""Tests voor de CI-poort tegen stille overslagen (`conftest.py`)."""

from __future__ import annotations

import pytest

from conftest import _modulewijde_overslagen


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
