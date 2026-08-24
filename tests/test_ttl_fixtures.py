"""Bewaakt dat de TTL-fixtures nog bij hun generator passen.

Alle bestanden onder `tests/fixtures/ttl` worden geschreven door
`scripts/maak_ttl_fixtures.py`. Zonder deze test kan een fixture met de hand
bijgewerkt worden zonder het script: dan draait de suite gewoon door, en de eerste
die het script opnieuw draait ziet zijn wijziging zonder waarschuwing verdwijnen.
Dat is precies wat er met `ext_scenario.ttl` gebeurd is.

Niet elke fixture komt uit het script: een deel is met de hand geschreven van voor
het bestond. Die blijven bij het regenereren staan -- `main` schrijft alleen en
verwijdert niets -- en vallen dus buiten deze bewaking. De bewaking geldt precies
voor de bestanden die het script wel kent, want alleen daar kan een handmatige
wijziging stil ongedaan gemaakt worden.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

WORTEL = Path(__file__).resolve().parents[1]
SCRIPT = WORTEL / "scripts" / "maak_ttl_fixtures.py"
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def generator() -> ModuleType:
    """Laadt het generatorscript als module; het schrijft bij import niets."""
    spec = importlib.util.spec_from_file_location("maak_ttl_fixtures", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = generator()


@pytest.mark.parametrize("naam", sorted(GENERATOR.FIXTURES))
def test_fixture_komt_overeen_met_de_generator(naam: str) -> None:
    """Het bestand op schijf is letterlijk wat het script ervan zou maken."""
    defect, inhoud = GENERATOR.FIXTURES[naam]
    assert (TTL_DIR / naam).read_text(encoding="utf-8") == GENERATOR.render(defect, inhoud)
