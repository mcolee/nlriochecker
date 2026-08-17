"""Bewaakt dat de geregistreerde checks niet van het checkregister af drijven."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nlriochecker.checks import REGISTRY, Dimension, Severity

REGISTER = Path(__file__).resolve().parents[1] / "data" / "checkregister-gwsw-nulmeting-v0_8.md"
RIJ_PATROON = re.compile(
    r"^\|\s*(?P<id>[A-Z]{3,4}-\d{3})\s*\|(?P<check>[^|]*)\|\s*(?P<ernst>[FW])\s*\|"
    r"\s*(?P<dimensie>[A-Za-z]+)\s*\|"
)

pytestmark = pytest.mark.skipif(
    not REGISTER.exists(), reason="het checkregister staat niet in data/"
)


def _register_rijen() -> dict[str, tuple[str, str]]:
    """Leest ernst en dimensie per check-ID uit de tabellen van het register."""
    rijen: dict[str, tuple[str, str]] = {}
    for regel in REGISTER.read_text(encoding="utf-8").splitlines():
        match = RIJ_PATROON.match(regel)
        if match:
            rijen[match["id"]] = (match["ernst"], match["dimensie"])
    return rijen


def test_register_is_leesbaar() -> None:
    rijen = _register_rijen()

    # Een steekproef die vastlegt dat de tabel echt gelezen wordt.
    assert rijen["TOP-001"] == ("F", "Consistentie")
    assert rijen["TOP-005"] == ("F", "Compleetheid")
    assert len(rijen) > 60


def test_er_zijn_checks_geregistreerd() -> None:
    assert REGISTRY, "de registry is leeg; wordt de checkmodule wel geimporteerd?"


@pytest.mark.parametrize("check_id", sorted(REGISTRY))
def test_ernst_en_dimensie_volgen_het_register(check_id: str) -> None:
    rijen = _register_rijen()
    assert check_id in rijen, f"{check_id} staat niet in het checkregister"

    ernst, dimensie = rijen[check_id]
    check = REGISTRY[check_id]

    assert check.severity is Severity(ernst)
    assert check.dimension is Dimension(dimensie)


@pytest.mark.parametrize("check_id", sorted(REGISTRY))
def test_geschrapte_checks_worden_niet_opnieuw_gebouwd(check_id: str) -> None:
    # De schrapronde dekt deze ID's al via de nulmeting; ze horen niet in de engine.
    geschrapt = {"ADM-001", "ADM-004", "ADM-005", "ATTR-011", "RVZ-002", "RVZ-003"}

    assert check_id not in geschrapt
