"""Tests voor scripts/runnerpoort.py: de lokale poort in de conditie van de CI-runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

WORTEL = Path(__file__).resolve().parents[1]
SCRIPT = WORTEL / "scripts" / "runnerpoort.py"


def script() -> ModuleType:
    """Laadt het script als module; het draait bij import niets."""
    spec = importlib.util.spec_from_file_location("runnerpoort", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNERPOORT = script()


def test_de_grenzen_komen_uit_de_workflow() -> None:
    """Het script leest de CI-grenzen uit toets.yml, zodat er maar een waarheid is."""
    omgeving = RUNNERPOORT.ci_omgeving()

    assert set(omgeving) == {
        "NLRIOCHECKER_MIN_GESLAAGD",
        "NLRIOCHECKER_STRIKTE_OVERSLAG",
        "NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN",
    }
    assert omgeving["NLRIOCHECKER_STRIKTE_OVERSLAG"] == "1"


def test_de_pytest_regel_is_die_van_de_ci() -> None:
    opdracht = RUNNERPOORT.ci_pytest_opdracht()

    assert opdracht[:5] == ["uv", "run", "--with", "pytest-cov", "pytest"]
    assert any(deel.startswith("--cov-fail-under=") for deel in opdracht)


def test_alleen_de_getrackte_databestanden_gaan_mee() -> None:
    """De runner heeft van data/ alleen wat git kent: de checkregisters en de vocabulaire-index."""
    namen = {pad.name for pad in RUNNERPOORT.getrackte_databestanden()}

    assert "gwsw-vocabulaire-index.json" in namen
    assert "checkregister-gwsw-nulmeting-v0_9.md" in namen
    assert not any(naam.endswith(".ttl") or naam.endswith(".gpkg") for naam in namen)
    assert all(pad.parts[0] == "data" for pad in RUNNERPOORT.getrackte_databestanden())
