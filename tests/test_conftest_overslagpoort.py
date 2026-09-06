"""Tegenproef bij de over-marge-waarschuwing in `conftest.pytest_sessionfinish` (issue #160).

De ondergrens `NLRIOCHECKER_MIN_GESLAAGD` kruipt met de suite mee omhoog; zonder een
nudge veroudert hij tot een marge die geen regressie meer vangt. De waarschuwing hieronder
roept om een herijking zodra er meer dan 10% boven de grens slagen. Het is een
waarschuwing, geen fout: de exitstatus blijft 0.
"""

from __future__ import annotations

import pytest

from conftest import (
    MAXIMUM_MODULE_OVERGESLAGEN_ENV,
    MINIMUM_ENV,
    STRIKT_ENV,
    pytest_sessionfinish,
)


class _Reporter:
    """Een terminalreporter die de geschreven regels onthoudt."""

    def __init__(self, geslaagd: int, overgeslagen: int = 0) -> None:
        self.stats = {
            "passed": [object()] * geslaagd,
            "skipped": [object()] * overgeslagen,
        }
        self.regels: list[tuple[str, bool]] = []

    def write_line(self, tekst: str, red: bool = False) -> None:
        self.regels.append((tekst, red))


class _Option:
    collectonly = False


class _PluginManager:
    def __init__(self, reporter: _Reporter) -> None:
        self._reporter = reporter

    def get_plugin(self, naam: str) -> _Reporter | None:
        return self._reporter if naam == "terminalreporter" else None


class _Config:
    def __init__(self, reporter: _Reporter) -> None:
        self.option = _Option()
        self.pluginmanager = _PluginManager(reporter)


class _Session:
    def __init__(self, reporter: _Reporter) -> None:
        self.config = _Config(reporter)
        self.exitstatus = 0


def _draai(reporter: _Reporter, monkeypatch: pytest.MonkeyPatch, minimum: str | None) -> _Session:
    """Draait `pytest_sessionfinish` met een geisoleerde omgeving en de fake reporter."""
    monkeypatch.delenv(STRIKT_ENV, raising=False)
    monkeypatch.delenv(MAXIMUM_MODULE_OVERGESLAGEN_ENV, raising=False)
    if minimum is None:
        monkeypatch.delenv(MINIMUM_ENV, raising=False)
    else:
        monkeypatch.setenv(MINIMUM_ENV, minimum)
    session = _Session(reporter)
    pytest_sessionfinish(session, 0)  # type: ignore[arg-type]
    return session


def _waarschuwt(reporter: _Reporter) -> bool:
    """Of de over-marge-waarschuwing is geschreven."""
    return any("meer dan 10%" in tekst for tekst, _ in reporter.regels)


def test_waarschuwing_bij_ruime_marge(monkeypatch: pytest.MonkeyPatch) -> None:
    """111 > 100 x 1,10: de waarschuwing valt, maar de run zakt er niet op."""
    reporter = _Reporter(geslaagd=111)

    session = _draai(reporter, monkeypatch, minimum="100")

    assert _waarschuwt(reporter)
    assert session.exitstatus == 0


def test_geen_waarschuwing_binnen_de_marge(monkeypatch: pytest.MonkeyPatch) -> None:
    """105 <= 100 x 1,10: geen nudge."""
    reporter = _Reporter(geslaagd=105)

    _draai(reporter, monkeypatch, minimum="100")

    assert not _waarschuwt(reporter)


def test_geen_waarschuwing_zonder_grens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder `NLRIOCHECKER_MIN_GESLAAGD` zwijgt de poort, hoeveel er ook slagen."""
    reporter = _Reporter(geslaagd=100_000)

    _draai(reporter, monkeypatch, minimum=None)

    assert not _waarschuwt(reporter)
