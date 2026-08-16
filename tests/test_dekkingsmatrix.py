"""Bewaakt dat docs/dekkingsmatrix.md niet uit de pas loopt met de engine.

De matrix is de plek waar staat wat er *niet* gebouwd is. Loopt hij achter, dan
leest het document als een compleetheidsclaim die niet klopt. Deze test faalt zodra
het bestand niet meer overeenkomt met wat `scripts/dekkingsmatrix.py` nu zou
schrijven; `uv run python scripts/dekkingsmatrix.py` maakt hem weer gelijk.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
SCRIPT = WORTEL / "scripts" / "dekkingsmatrix.py"
MATRIX = WORTEL / "docs" / "dekkingsmatrix.md"


def _laad_script():
    """Importeert het generatorscript als module."""
    spec = importlib.util.spec_from_file_location("dekkingsmatrix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dekkingsmatrix"] = module
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="het generatorscript ontbreekt")


def test_matrix_is_actueel() -> None:
    module = _laad_script()
    register = module.load_register(module.default_register_path())
    verwacht = module.render(register, register.categories)

    assert MATRIX.exists(), "docs/dekkingsmatrix.md ontbreekt"
    assert MATRIX.read_text(encoding="utf-8") == verwacht, (
        "de dekkingsmatrix loopt achter op de engine; draai "
        "`uv run python scripts/dekkingsmatrix.py`"
    )


def test_geen_check_zonder_registerregel() -> None:
    module = _laad_script()
    register = module.load_register(module.default_register_path())
    bekend = {entry.check_id for entry in register.entries}

    from gwswpijplijn.checks import REGISTRY

    assert set(REGISTRY) - bekend == set()
