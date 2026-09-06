"""Tests voor het uitgavescript, voor zover dat zonder git te draaien gaat.

De bewerkingen op het wijzigingslog zijn zuivere tekstfuncties; die zijn hier te
toetsen zonder een commit of een tag te maken. De git-stappen zelf blijven
ongetoetst: die zijn niet na te bootsen zonder een echte uitgave te doen.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

WORTEL = Path(__file__).resolve().parents[1]
SCRIPT = WORTEL / "scripts" / "uitgave.py"
CHANGELOG = WORTEL / "CHANGELOG.md"
WORKFLOWS = WORTEL / ".github" / "workflows"
# `owner/repo@<40 hex>` gevolgd door de tag als commentaar. De tag hoort erbij: zonder
# die regel is bij de volgende bump niet te zien welke versie er gepind staat.
PATROON_PIN = re.compile(r"uses: [\w.-]+/[\w.-]+@[0-9a-f]{40} +# \S+$")

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
    assert "uv run --with pytest-cov --with pytest-xdist pytest -n 4 --cov=nlriochecker" in claude
    # Anker op de ondergrens-zin, niet op het losse "97%" van de laatste meting.
    assert f"ondergrens van {grens}%" in claude


def test_de_uitgavepoort_draait_op_de_vastgezette_lock() -> None:
    """Geen poortstap mag `uv.lock` aanraken (issue #120).

    `uv.lock` staat in `VERSIEBESTANDEN` en gaat dus mee in de commit `Versie X.Y.Z`: een
    lockwijziging die `uv run` halverwege de uitgave maakt, rijdt ongezien de release in.
    `--frozen` ("run without updating the uv.lock file") houdt hem onaangeroerd; niet
    `--locked`, want het doel is niet te bewijzen dat de lock vers is. De CI bouwt haar
    omgeving om dezelfde reden uit de lock, en die binding wordt hier meegetoetst.
    """
    module = _laad_script()
    opdrachten: list[tuple[str, ...]] = []

    def _recorder(*opdracht: str, opvangen: bool = False) -> str:
        opdrachten.append(opdracht)
        return ""

    def _stil(*_argumenten: object, **_sleutelwoorden: object) -> None:
        return None

    module._draai = _recorder
    module._meld = _stil

    module.toets()

    uv_run = [opdracht for opdracht in opdrachten if opdracht[:2] == ("uv", "run")]
    assert len(uv_run) == 4, f"verwacht vier `uv run`-stappen, gevonden {len(uv_run)}"
    for opdracht in uv_run:
        assert "--frozen" in opdracht, f"`{' '.join(opdracht)}` draait zonder --frozen"

    # De CI bouwt de omgeving uit dezelfde lock; loopt dat uiteen, dan toetst de uitgave
    # iets anders dan de runner.
    workflow = (WORKFLOWS / "toets.yml").read_text(encoding="utf-8")
    assert "uv sync --frozen" in workflow


def test_de_workflows_pinnen_hun_actions_op_een_sha() -> None:
    """Elke `uses:` staat op een commit-SHA met de tag erachter (issue #120).

    Een tag kan naar een andere commit verplaatst worden, een SHA niet. Zonder deze test
    glijdt de pin bij de eerstvolgende handmatige bump terug naar een tag.
    """
    for naam in ("toets.yml", "release.yml"):
        regels = (WORKFLOWS / naam).read_text(encoding="utf-8").splitlines()
        gebruiken = [regel for regel in regels if regel.lstrip().startswith(("uses:", "- uses:"))]
        assert gebruiken, f"{naam} noemt geen enkele action"
        for regel in gebruiken:
            assert PATROON_PIN.search(regel), f"{naam}: `{regel.strip()}` is niet op een SHA gepind"


def test_zwaar_toets_draait_de_suite_als_de_data_er_is() -> None:
    """Met de export aanwezig draait de zesde stap gewoon de zwaar-suite (issue #157)."""
    module = _laad_script()
    opdrachten: list[tuple[str, ...]] = []
    module._draai = lambda *opdracht, opvangen=False: (opdrachten.append(opdracht), "")[1]
    module._meld = lambda *_a, **_k: None

    module.zwaar_toets("major", False, data_pad=SCRIPT)  # SCRIPT bestaat sowieso

    assert opdrachten == [("uv", "run", "--frozen", "pytest", "-m", "zwaar", "-q")]


def test_zwaar_toets_slaat_over_met_de_vlag_bij_patch() -> None:
    """`--zonder-zwaar` mag de suite overslaan, maar alleen bij een patch."""
    module = _laad_script()
    module._draai = lambda *_o, **_k: pytest.fail("de suite had niet mogen draaien")
    module._meld = lambda *_a, **_k: None

    module.zwaar_toets("patch", True, data_pad=Path("/bestaat-niet"))


def test_zwaar_toets_breekt_af_zonder_data_bij_minor_of_major() -> None:
    """Ontbrekende De Wolden-export bij een verplichte run is een afgebroken uitgave,
    geen stille overslag (het strengste dat consistent is met kop 2/6 van issue #157)."""
    module = _laad_script()

    with pytest.raises(module.ReleaseAbortedError, match="ontbreekt"):
        module.zwaar_toets("minor", False, data_pad=Path("/bestaat-niet"))


def test_controleer_zonder_zwaar_weigert_de_vlag_buiten_patch() -> None:
    """`--zonder-zwaar` bij minor/major zou de verplichte poort stilzwijgend uitzetten;
    deze voorcontrole hoort daarom vooraan, naast de andere `controleer_*`-functies."""
    module = _laad_script()

    with pytest.raises(module.ReleaseAbortedError, match="patch"):
        module.controleer_zonder_zwaar("minor", True)


def test_controleer_zonder_zwaar_laat_de_geldige_gevallen_door() -> None:
    """Patch met de vlag, en elk soort zonder de vlag, zijn geen reden om af te breken."""
    module = _laad_script()

    module.controleer_zonder_zwaar("patch", True)
    for soort in module.SOORTEN:
        module.controleer_zonder_zwaar(soort, False)


def test_main_breekt_af_voor_de_poort_en_de_commit_bij_minor_zonder_zwaar() -> None:
    """`uitgave.py minor --zonder-zwaar` mag niet eerst de hele poort en de versiecommit
    doorlopen om pas daarna te struikelen (reviewbevinding op issue #157): de vlag wordt
    vooraan geweigerd, vóór `controleer_werkboom` en dus vóór elke state-wijziging.
    """
    module = _laad_script()
    aangeroepen: list[str] = []

    def _spion(naam: str) -> Callable[..., None]:
        def _fn(*_a: object, **_k: object) -> None:
            aangeroepen.append(naam)

        return _fn

    module._git = lambda *_a, **_k: str(WORTEL)
    module.controleer_werkboom = _spion("werkboom")
    module.controleer_niet_achter = _spion("niet_achter")
    module.controleer_changelog = _spion("changelog")
    module.voorspel_versie = _spion("voorspel_versie")
    module.bump = _spion("bump")
    module.toets = _spion("toets")
    module.schrijf_changelog = _spion("schrijf_changelog")
    module.leg_vast = _spion("leg_vast")

    uitkomst = module.main(["minor", "--zonder-zwaar"])

    assert uitkomst == 1
    assert aangeroepen == []


UITGAVE_EIGEN_STAPPEN = frozenset({"pytest -m zwaar"})
# De wheel-rooktest (issue #158) staat alleen in toets.yml: de uitgavepoort bouwt geen
# wheel, dat doet release.yml al bij de tag-push. `_uv_run_stapnaam` herkent alleen
# `uv run ...`-regels; de rooktest begint met `uv build` en wordt dus sowieso niet
# opgepikt, maar de naam staat hier toch expliciet zodat dit geen stilzwijgende
# asymmetrie is.
WORKFLOW_EIGEN_STAPPEN: frozenset[str] = frozenset({"wheel-rooktest"})


def _uv_run_stapnaam(commando: str) -> str | None:
    """Herleidt een korte stapnaam uit een `uv run ...`-commandoregel, anders None."""
    delen = commando.split()
    if delen[:2] != ["uv", "run"]:
        return None
    kern: list[str] = []
    i = 2
    while i < len(delen):
        if delen[i] == "--frozen":
            i += 1
            continue
        if delen[i] == "--with":
            i += 2
            continue
        kern.append(delen[i])
        i += 1
    if not kern:
        return None
    if kern[0] == "pytest" and "-m" in kern:
        return f"pytest -m {kern[kern.index('-m') + 1]}"
    if len(kern) > 1 and not kern[1].startswith("-"):
        return f"{kern[0]} {kern[1]}"
    return kern[0]


def test_de_stappenlijst_van_uitgave_en_toets_yml_blijft_gelijk() -> None:
    """De poortstappen van `uitgave.py` en `toets.yml` blijven gelijk, op de benoemde
    uitzonderingen na (issue #157). De zwaar-suite hoort wel in de uitgave (verplicht bij
    minor/major) maar niet in de CI-workflow (de runner mist de De Wolden-export); dat is
    de enige toegestane asymmetrie totdat issue #158 er zelf een aan de workflow-kant
    aan toevoegt.
    """
    module = _laad_script()
    opdrachten: list[tuple[str, ...]] = []
    module._draai = lambda *opdracht, opvangen=False: (opdrachten.append(opdracht), "")[1]
    module._meld = lambda *_a, **_k: None

    module.toets()
    module.zwaar_toets("major", False, data_pad=SCRIPT)

    uitgave_stappen = {
        naam
        for opdracht in opdrachten
        if (naam := _uv_run_stapnaam(" ".join(opdracht))) is not None
    }

    workflow_tekst = (WORKFLOWS / "toets.yml").read_text(encoding="utf-8")
    workflow_stappen = {
        naam
        for regel in (ruwe_regel.strip() for ruwe_regel in workflow_tekst.splitlines())
        if regel.startswith("run: ")
        if (naam := _uv_run_stapnaam(regel.removeprefix("run: "))) is not None
    }

    assert uitgave_stappen - UITGAVE_EIGEN_STAPPEN == workflow_stappen - WORKFLOW_EIGEN_STAPPEN


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
