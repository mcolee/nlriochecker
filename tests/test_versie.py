"""Bewaakt dat het versienummer op één plek staat en niet uit elkaar loopt."""

from __future__ import annotations

import tomllib
from pathlib import Path

import nlriochecker

WORTEL = Path(__file__).resolve().parent.parent


def _pyproject_versie() -> str:
    with (WORTEL / "pyproject.toml").open("rb") as bestand:
        return tomllib.load(bestand)["project"]["version"]


def test_versie_volgt_pyproject() -> None:
    """`__version__` komt uit de metadata en moet pyproject.toml volgen.

    Loopt dit uiteen, dan is de omgeving verouderd (`uv sync` vergeten na een
    bump) of staat er ergens weer een tweede, met de hand bijgehouden nummer.
    """
    assert nlriochecker.__version__ == _pyproject_versie(), "verouderde omgeving? draai `uv sync`"


def test_versie_is_semver() -> None:
    """De uitgavetags heten `vX.Y.Z`; dan moet het nummer die vorm ook hebben."""
    delen = _pyproject_versie().split(".")
    assert len(delen) == 3, "verwacht X.Y.Z"
    assert all(deel.isdigit() for deel in delen), "verwacht enkel cijfers per deel"
