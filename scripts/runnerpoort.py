#!/usr/bin/env python
"""Draait de poort in de conditie van de CI-runner, vóór je pusht.

De runner heeft van `data/` alleen wat git kent (de twee checkregisters), geen PyQGIS, en
de grensvariabelen uit `.github/workflows/toets.yml`. Een test die hier slaagt maar daar
overslaat -- of andersom -- zie je pas na de push, en dan als rode run. Dit script bootst
die conditie na: het zet `data/` tijdelijk opzij, zet alleen de getrackte bestanden terug,
zet PyQGIS uit en draait dezelfde pytest-regel met dezelfde omgeving als de workflow.
Beide leest het uit de workflow zelf, zodat er maar een waarheid is (BO-48).

Gebruik:  uv run python scripts/runnerpoort.py
De exitcode is die van pytest.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
DATA = WORTEL / "data"
# Waar de echte data/ tijdens de run staat. Bestaat hij al, dan is een vorige run niet
# netjes teruggezet en start dit script niet: het zou anders de verkeerde map wegzetten.
OPZIJ = WORTEL / "data_runnerpoort_opzij"
WORKFLOW = WORTEL / ".github" / "workflows" / "toets.yml"


def ci_omgeving() -> dict[str, str]:
    """De NLRIOCHECKER_*-grenzen uit het env-blok van de workflow."""
    tekst = WORKFLOW.read_text(encoding="utf-8")
    return dict(re.findall(r'^\s+(NLRIOCHECKER_\w+):\s*"([^"]*)"', tekst, re.MULTILINE))


def ci_pytest_opdracht() -> list[str]:
    """De pytest-regel van de stap 'Pytest en dekking' in de workflow, als argumentenlijst."""
    tekst = WORKFLOW.read_text(encoding="utf-8")
    treffer = re.search(r"^\s+run:\s*(uv run --with pytest-cov pytest .*)$", tekst, re.MULTILINE)
    if treffer is None:
        raise SystemExit("de pytest-stap is niet gevonden in .github/workflows/toets.yml")
    return treffer.group(1).split()


def getrackte_databestanden() -> list[Path]:
    """De bestanden onder data/ die git kent, relatief aan de repo-wortel."""
    uitvoer = subprocess.run(
        ["git", "ls-files", "--", "data"], cwd=WORTEL, capture_output=True, text=True, check=True
    ).stdout
    return [Path(regel) for regel in uitvoer.splitlines() if regel]


def main() -> int:
    """Zet data/ opzij, draait de CI-pytest-regel op de getrackte rest en zet data/ terug."""
    if OPZIJ.exists():
        raise SystemExit(
            f"{OPZIJ.name}/ bestaat al: een eerdere run is niet netjes teruggezet. Zet hem terug "
            f"met `mv {OPZIJ.name} data` -- maar alleen als `data/` niet bestaat; bestaat hij wel, "
            "ruim die eerst op. Probeer daarna opnieuw."
        )
    if not DATA.is_dir():
        raise SystemExit("data/ ontbreekt; er valt niets na te bootsen")
    bestanden = getrackte_databestanden()
    omgeving = {**os.environ, **ci_omgeving(), "GWSW_QGIS_SITE_PACKAGES": "/nonexistent"}
    opdracht = ci_pytest_opdracht()

    print(f"data/ opzij naar {OPZIJ.name}/; alleen mee: {', '.join(p.name for p in bestanden)}")
    DATA.rename(OPZIJ)
    try:
        DATA.mkdir()
        for relatief in bestanden:
            binnen = relatief.relative_to("data")
            (DATA / binnen).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(OPZIJ / binnen, DATA / binnen)
        print("omgeving:", " ".join(f"{k}={v}" for k, v in sorted(ci_omgeving().items())))
        print("$", " ".join(opdracht), flush=True)
        return subprocess.run(opdracht, cwd=WORTEL, env=omgeving, check=False).returncode
    finally:
        shutil.rmtree(DATA, ignore_errors=True)
        if DATA.exists():
            raise SystemExit(
                f"kon de tijdelijke data/ niet opruimen; de echte data staat nog in {OPZIJ.name}/. "
                "Ruim data/ met de hand op en zet daarna terug met: mv "
                f"{OPZIJ.name} data"
            )
        OPZIJ.rename(DATA)
        print("data/ teruggezet")


if __name__ == "__main__":
    sys.exit(main())
