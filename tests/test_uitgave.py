"""Tests voor het uitgavescript, voor zover dat zonder git te draaien gaat.

De bewerkingen op het wijzigingslog zijn zuivere tekstfuncties; die zijn hier te
toetsen zonder een commit of een tag te maken. De git-stappen zelf blijven
ongetoetst: die zijn niet na te bootsen zonder een echte uitgave te doen.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

WORTEL = Path(__file__).resolve().parents[1]
SCRIPT = WORTEL / "scripts" / "uitgave.py"
CHANGELOG = WORTEL / "CHANGELOG.md"

VOORBEELD = """# Wijzigingslog

Inleiding.

## [Unreleased]

### Toegevoegd

- Iets nieuws.

## [0.2.0] - 2026-08-17

### Toegevoegd

- De eerste uitgave.

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/releases/tag/v0.2.0
"""

pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="het uitgavescript ontbreekt")


def _laad_script() -> ModuleType:
    """Importeert het uitgavescript als module."""
    spec = importlib.util.spec_from_file_location("uitgave", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["uitgave"] = module
    spec.loader.exec_module(module)
    return module


def test_lege_unreleased_blokkeert_de_uitgave() -> None:
    """Een uitgave zonder opgeschreven wijzigingen is naderhand niet te duiden."""
    module = _laad_script()
    leeg = VOORBEELD.replace("### Toegevoegd\n\n- Iets nieuws.\n\n", "", 1)

    with pytest.raises(module.ReleaseAbortedError, match="leeg"):
        module.controleer_changelog(leeg)


def test_gevulde_unreleased_laat_de_uitgave_door() -> None:
    """Staat er wel iets, dan is er niets aan de hand."""
    module = _laad_script()

    module.controleer_changelog(VOORBEELD)


def test_ontbrekende_sectie_blokkeert_de_uitgave() -> None:
    """Zonder de sectie weet het script niet waar het schrijven moet."""
    module = _laad_script()

    with pytest.raises(module.ReleaseAbortedError, match="Unreleased"):
        module.controleer_changelog("# Wijzigingslog\n\n## [0.2.0] - 2026-08-17\n")


def test_uitgave_verplaatst_unreleased_naar_het_nieuwe_nummer() -> None:
    """De inhoud verhuist naar de nieuwe sectie; Unreleased blijft leeg achter."""
    module = _laad_script()

    nieuw = module.verwerk_changelog(VOORBEELD, "0.3.0", date(2026, 9, 1))

    assert "## [Unreleased]\n\n## [0.3.0] - 2026-09-01\n\n### Toegevoegd\n\n- Iets nieuws." in nieuw
    # De oudere secties blijven staan.
    assert "## [0.2.0] - 2026-08-17" in nieuw
    # En de nieuwe Unreleased is echt leeg, dus een volgende uitgave valt erover.
    with pytest.raises(module.ReleaseAbortedError, match="leeg"):
        module.controleer_changelog(nieuw)


def test_uitgave_werkt_de_verwijzingen_onderaan_bij() -> None:
    """Zonder dit rendert de nieuwe kop als letterlijke `[0.3.0]` en loopt Unreleased achter."""
    module = _laad_script()

    nieuw = module.verwerk_changelog(VOORBEELD, "0.3.0", date(2026, 9, 1))

    assert "[Unreleased]: https://example.invalid/compare/v0.3.0...HEAD" in nieuw
    assert "[0.3.0]: https://example.invalid/compare/v0.2.0...v0.3.0" in nieuw
    # De verwijzing naar de oudste uitgave blijft ongemoeid.
    assert "[0.2.0]: https://example.invalid/releases/tag/v0.2.0" in nieuw


def test_ontbrekende_verwijzing_blokkeert_de_uitgave() -> None:
    """Zonder de Unreleased-verwijzing is niet af te leiden waartegen vergeleken wordt."""
    module = _laad_script()
    zonder = VOORBEELD.replace(
        "[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD\n", "", 1
    )

    with pytest.raises(module.ReleaseAbortedError, match="compare"):
        module.controleer_changelog(zonder)


def test_kop_in_de_inleiding_verschuift_de_sectie_niet() -> None:
    """De kop telt alleen aan het begin van een regel, niet in lopende tekst."""
    module = _laad_script()
    met_proza = VOORBEELD.replace(
        "Inleiding.", "Inleiding die de sectie ## [Unreleased] bij naam noemt.", 1
    )

    nieuw = module.verwerk_changelog(met_proza, "0.3.0", date(2026, 9, 1))

    assert "Inleiding die de sectie ## [Unreleased] bij naam noemt." in nieuw
    assert "## [0.3.0] - 2026-09-01\n\n### Toegevoegd\n\n- Iets nieuws." in nieuw


def test_de_dekkingsondergrens_is_overal_hetzelfde_getal() -> None:
    """De CI, de uitgavepoort en `CLAUDE.md` dwingen dezelfde dekkingsondergrens af
    (issue #54, BO-38). Het getal staat in code maar op een plek (`DEKKINGSONDERGRENS`);
    deze test bindt de drie eraan, zodat ze niet stil uiteen kunnen lopen en de
    documentatie niet iets anders belooft dan de poorten bewaken.
    """
    module = _laad_script()
    grens = module.DEKKINGSONDERGRENS

    # De uitgavepoort dwingt de dekking af via de constante.
    bron = SCRIPT.read_text(encoding="utf-8")
    assert "--cov-fail-under={DEKKINGSONDERGRENS}" in bron
    assert "--cov=nlriochecker" in bron

    # De CI-workflow draait dezelfde grens (daar een letterlijk getal, geen constante).
    workflow = (WORTEL / ".github" / "workflows" / "toets.yml").read_text(encoding="utf-8")
    assert f"--cov-fail-under={grens}" in workflow
    assert "--cov=nlriochecker" in workflow

    # En CLAUDE.md noemt hetzelfde getal en het meetcommando.
    claude = (WORTEL / "CLAUDE.md").read_text(encoding="utf-8")
    assert "uv run --with pytest-cov pytest --cov=nlriochecker" in claude
    # Anker op de ondergrens-zin, niet op het losse "97%" van de laatste meting.
    assert f"ondergrens van {grens}%" in claude


def test_het_echte_wijzigingslog_is_verwerkbaar() -> None:
    """Het bestand in de repository moet de vorm hebben die het script verwacht."""
    module = _laad_script()
    tekst = CHANGELOG.read_text(encoding="utf-8")

    # Bewust géén controleer_changelog hier: dat is een release-preconditie (een lege
    # [Unreleased] afkeuren), en precies dat is de legitieme toestand van een
    # release-commit -- uitgave.py verschuift de sectie en laat [Unreleased] leeg achter.
    # De poort op die commit (en op main na de merge) zou er anders rood van worden. De
    # preconditie zelf blijft gedekt door de synthetische gevallen hierboven. Deze test
    # bewaakt alleen dat verwerk_changelog het échte bestand aankan (issue #110).
    nieuw = module.verwerk_changelog(tekst, "0.9.9", date(2026, 9, 1))

    assert "## [0.9.9] - 2026-09-01" in nieuw
    assert "[0.9.9]: " in nieuw
    assert "[Unreleased]: https://github.com/mcolee/nlriochecker/compare/v0.9.9...HEAD" in nieuw
