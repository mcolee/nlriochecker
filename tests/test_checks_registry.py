"""Bewaakt dat de geregistreerde checks niet van het checkregister af drijven."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from nlriochecker.checks import REGISTRY, Dimension, Severity

CHECKS_DIR = Path(__file__).resolve().parents[1] / "src" / "nlriochecker" / "checks"
REGISTER = Path(__file__).resolve().parents[1] / "data" / "checkregister-gwsw-nulmeting-v0_9.md"
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
    geschrapt = {"ADM-001", "ADM-004", "ADM-005", "ATTR-008", "ATTR-011"}

    assert check_id not in geschrapt


@pytest.mark.parametrize("check_id", sorted(REGISTRY))
def test_vervallen_ids_worden_nooit_hergebruikt(check_id: str) -> None:
    # ID's die in een andere check zijn opgegaan; een vervallen ID hergebruik je nooit
    # (harde regel in CLAUDE.md). RVZ-003 ging op in RVZ-002 (#87, BO-78).
    vervallen = {"RVZ-003"}

    assert check_id not in vervallen


def _is_register(decorator: ast.expr) -> bool:
    """Of deze decorator de `register`-decorator uit `checks.base` is."""
    if isinstance(decorator, ast.Name):
        return decorator.id == "register"
    return isinstance(decorator, ast.Attribute) and decorator.attr == "register"


def _geregistreerde_check_ids(bron: str) -> set[str]:
    """De check-ID's van elke `@register`-klasse in deze broncode.

    AST en niet importeren: een module die `checks/__init__.py` vergeet te importeren
    vult de registry niet, en juist dat gat moet zichtbaar worden. Het `id`-attribuut is
    een stringliteraal op klasseniveau; een klasse zonder `@register` (een basisklasse als
    `_ExterneCheck`) telt niet mee.
    """
    ids: set[str] = set()
    for node in ast.walk(ast.parse(bron)):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_is_register(decorator) for decorator in node.decorator_list):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for doel in stmt.targets:
                if (
                    isinstance(doel, ast.Name)
                    and doel.id == "id"
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)
                ):
                    ids.add(stmt.value.value)
    return ids


def test_elke_geregistreerde_checkklasse_zit_in_de_registry() -> None:
    """Een `@register`-klasse in `checks/*.py` levert een ID in `REGISTRY` (issue #160).

    Zonder deze test glipt een vergeten import in `checks/__init__.py` er ongezien
    doorheen: de nieuwe checkmodule wordt nooit uitgevoerd, `@register` draait niet, en de
    registry mist de check terwijl alle andere tests groen blijven -- precies de repro
    (`checks/grondwater.py` met `GWA-001`) uit de Fable-swarm.
    """
    ontbreekt: dict[str, list[str]] = {}
    for pad in sorted(CHECKS_DIR.glob("*.py")):
        for check_id in _geregistreerde_check_ids(pad.read_text(encoding="utf-8")):
            if check_id not in REGISTRY:
                ontbreekt.setdefault(pad.name, []).append(check_id)

    assert ontbreekt == {}


def test_de_registry_drift_sweep_kan_werkelijk_afgaan() -> None:
    """De tegenproef: de sweep vindt de ID van een niet-geimporteerde `@register`-klasse.

    Een synthetische bron, geen echt bestand in `src/`. Zou `checks/grondwater.py` echt
    bestaan zonder import, dan zou de hoofdtest hier vallen -- `GWA-001` zit niet in de
    registry.
    """
    bron = (
        "from nlriochecker.checks.base import Check, register\n"
        "@register\n"
        "class Grondwater(Check):\n"
        '    id = "GWA-001"\n'
    )

    assert _geregistreerde_check_ids(bron) == {"GWA-001"}
    assert "GWA-001" not in REGISTRY
    # Een basisklasse zonder `@register` telt niet mee.
    assert _geregistreerde_check_ids('class _Basis(Check):\n    id = "X"\n') == set()
