# CI-overslagbewaking op reden en een lokale runnerpoort — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De CI-poort faalt niet meer op legitieme groei van datagebonden tests: overslagen worden op *reden* geclassificeerd (verwacht = de reden noemt `data/` of een `BO-`-nummer; al het andere is op CI een harde fout) in plaats van geteld tegen `NLRIOCHECKER_MAX_OVERGESLAGEN`; en `scripts/runnerpoort.py` draait de poort lokaal in de conditie van de CI-runner (alleen de getrackte delen van `data/`, geen PyQGIS, dezelfde grensvariabelen), zodat een rode run vóór de push zichtbaar is.

**Architecture:** De bewaking zit in `tests/conftest.py::pytest_sessionfinish`. De telgrens `NLRIOCHECKER_MAX_OVERGESLAGEN` verdwijnt en wordt vervangen door de vlag `NLRIOCHECKER_STRIKTE_OVERSLAG` (CI zet hem): elke test-overslag (`TestReport`) waarvan de reden geen `data/` en geen `BO-` bevat laat de run vallen, met nodeid en reden in de uitvoer. `NLRIOCHECKER_MIN_GESLAAGD` en `NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` blijven. Het script leest de grenzen en de pytest-regel uit `.github/workflows/toets.yml` (één waarheid), zet `data/` tijdelijk opzij en zet alleen `git ls-files data` terug.

**Tech Stack:** Python 3.12, pytest (bestaand). Geen nieuwe afhankelijkheid; het script gebruikt alleen stdlib + git.

**Spec:** de analyse van 2026-08-25 (twee rode runs op legitieme groei: herijking 24-08 van 50 → 57, 25-08 van 57 → 65) en de afspraak met de auteur: maatregel 1 (classificatie op reden) en 2 (lokale runnerpoort).

## Global Constraints

- Verwachte overslagreden: bevat `data/` (echte data die op de runner ontbreekt) óf `BO-` (bewuste uitzondering met besluit; vandaag BO-40 in `tests/test_gwsw_vocabulaire.py`). Beide als substring, hoofdlettergevoelig. `VERWACHTE_REDENEN = ("data/", "BO-")` in `conftest.py` is de enige plek.
- Alleen `TestReport`-overslagen worden geclassificeerd; `CollectReport` (modulewijd) blijft het domein van `NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` (1).
- De strikte controle staat alleen aan met `NLRIOCHECKER_STRIKTE_OVERSLAG` gezet (CI en het script); een gewone lokale `uv run pytest` verandert niet van gedrag.
- `NLRIOCHECKER_MAX_OVERGESLAGEN` verdwijnt overal: `conftest.py`, workflow, README, `docs/agents/analyse-harness.md`. Oude CHANGELOG-regels blijven staan (historie).
- Het script raakt de echte `data/` alleen via één `rename` heen en één terug in een `try/finally`; het weigert te starten als de opzij-map al bestaat; de tijdelijke `data/` bevat precies `git ls-files -- data`.
- Poort vóór de commit: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`) — én, als sluitstuk van dit plan, `uv run python scripts/runnerpoort.py` zelf, die groen moet zijn.
- Nederlandse docstrings en meldingsteksten; werk op `dev`; commit met expliciete paden (geen `git add -A`).
- Nieuw BO-nummer: het eerstvolgende na het laatste `### BO-` in `docs/beslislog.md` (verwacht **BO-48**; controleer). CHANGELOG-regel onder `## [Unreleased]` → `### Gewijzigd`, bovenaan die sectie.

---

### Task 1: Classificatie op reden, runnerpoort, tests en documentatie

**Files:**
- Modify: `tests/conftest.py:12-31` (constanten), `:132-141` (helpers), `:155-210` (`pytest_sessionfinish`)
- Modify: `tests/test_poort.py` (twee tests erbij)
- Modify: `.github/workflows/toets.yml:61-90` (het `MAX_OVERGESLAGEN`-blok)
- Create: `scripts/runnerpoort.py`, `tests/test_runnerpoort.py`
- Modify: `README.md:351`, `docs/agents/analyse-harness.md:92-99`, `CLAUDE.md` (Werkwijze, bij de mechanische poort), `docs/beslislog.md` (BO-48), `CHANGELOG.md`

**Interfaces:**
- Consumes: `pytest.TestReport.longrepr` (bij een overslag een tuple `(pad, regel, "Skipped: <reden>")`), `pytest.CollectReport`, `rapporteur.stats["skipped"]`; `git ls-files -- data`; het `env:`-blok en de `run:`-regel van de pytest-stap in `toets.yml`.
- Produces: `conftest.STRIKT_ENV = "NLRIOCHECKER_STRIKTE_OVERSLAG"`, `conftest.VERWACHTE_REDENEN`, `conftest._reden(rapport) -> str`, `conftest._onverwachte_overslagen(overgeslagen) -> list[tuple[str, str]]`; `runnerpoort.ci_omgeving() -> dict[str, str]`, `runnerpoort.ci_pytest_opdracht() -> list[str]`, `runnerpoort.getrackte_databestanden() -> list[Path]` (relatief aan de repo-wortel), `runnerpoort.main() -> int`.

- [ ] **Step 1: Schrijf de falende tests voor de classificatie**

In `tests/test_poort.py`, onderaan (kijk hoe de bestaande test `pytest.TestReport(...)` construeert en gebruik dezelfde verplichte argumenten; voeg `longrepr` als tuple toe):

```python
from conftest import _onverwachte_overslagen, _reden


def _overslag(nodeid: str, reden: str) -> pytest.TestReport:
    """Een test-overslag zoals pytest hem rapporteert: longrepr = (pad, regel, 'Skipped: reden')."""
    return pytest.TestReport(
        nodeid=nodeid,
        location=(nodeid.split("::")[0], 1, nodeid.split("::")[-1]),
        keywords={},
        outcome="skipped",
        longrepr=(nodeid.split("::")[0], 1, f"Skipped: {reden}"),
        when="setup",
    )


def test_reden_komt_uit_longrepr_zonder_voorvoegsel() -> None:
    assert _reden(_overslag("tests/test_x.py::test_a", "de GWSW-ontologie staat niet in data/")) == (
        "de GWSW-ontologie staat niet in data/"
    )


def test_alleen_een_onverklaarde_overslag_is_onverwacht() -> None:
    """`data/` en een BO-nummer verklaren een overslag; een fixture die ontbreekt niet.

    Modulewijde overslagen (CollectReport) horen bij de modulegrens en tellen hier niet.
    """
    rapporten = [
        _overslag("tests/test_dataset.py::test_a", "de GWSW-ontologie staat niet in data/"),
        _overslag("tests/test_gwsw_vocabulaire.py::test_b", "ontbreekt in de ontologie; bewust, zie BO-40"),
        _overslag("tests/test_checks_extern.py::test_c", "de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py"),
        pytest.CollectReport(nodeid="tests/test_uitvoer_qgis.py", outcome="skipped", longrepr=None, result=[]),
    ]

    assert _onverwachte_overslagen(rapporten) == [
        ("tests/test_checks_extern.py::test_c", "de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py")
    ]
```

Run: `uv run pytest tests/test_poort.py -q` → FAIL met `ImportError`.

- [ ] **Step 2: Implementeer de classificatie in `tests/conftest.py`**

1. Vervang het commentaar + constante van regel 17-23 (`MAXIMUM_OVERGESLAGEN_ENV`) door:

```python
# De ondergrens hierboven meet "geslaagd" en kruipt met de suite mee omhoog. Wat de poort
# wil vangen is stille overslag: een fixture die niet meekomt, een generator die niet
# gedraaid is, een tool die op de runner ontbreekt. Een telgrens op "overgeslagen"
# (`NLRIOCHECKER_MAX_OVERGESLAGEN`, tot 2026-08-25) ving dat, maar telde ook de bedoelde,
# datagebonden overslagen mee -- de ontologie, het Juinen-voorbeeld en de SHACL-rapporten
# staan niet op de runner -- en klapte daardoor twee keer op legitieme testgroei. Daarom
# classificeert de poort nu op *reden*: een overslag is verwacht als zijn reden zegt waar
# hij vandaan komt. Al het andere is met deze vlag gezet een harde fout, zonder getal om
# te herijken (BO-48).
STRIKT_ENV = "NLRIOCHECKER_STRIKTE_OVERSLAG"
# Wat een reden verwacht maakt: `data/` (echte data die op de runner ontbreekt -- elke
# datagebonden skip hoort die map te noemen) of een BO-nummer (een bewuste uitzondering
# met besluit, zoals BO-40 in test_gwsw_vocabulaire.py).
VERWACHTE_REDENEN = ("data/", "BO-")
```

2. Ná `_modulewijde_overslagen` twee helpers:

```python
def _reden(rapport: object) -> str:
    """De overslagreden uit een rapport.

    pytest zet hem bij een overslag in `longrepr` als `(pad, regel, "Skipped: <reden>")`;
    het voorvoegsel gaat eraf zodat de classificatie op de reden zelf werkt.
    """
    longrepr = getattr(rapport, "longrepr", None)
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return str(longrepr[2]).removeprefix("Skipped: ")
    return str(longrepr or "")


def _onverwachte_overslagen(overgeslagen: list[object]) -> list[tuple[str, str]]:
    """De test-overslagen waarvan de reden niet zegt dat ze verwacht zijn, als (nodeid, reden).

    Alleen `TestReport`s: een modulewijde overslag is een `CollectReport` en hoort bij de
    modulegrens. Verwacht is een reden die een merk uit `VERWACHTE_REDENEN` draagt.
    """
    return [
        (rapport.nodeid, _reden(rapport))
        for rapport in overgeslagen
        if isinstance(rapport, pytest.TestReport)
        and not any(merk in _reden(rapport) for merk in VERWACHTE_REDENEN)
    ]
```

3. In `pytest_sessionfinish`: haal `maximum = _grens(MAXIMUM_OVERGESLAGEN_ENV, rapporteur)` en het `if maximum is not None ...`-blok weg en zet ervoor in de plaats (ná het `minimum`-blok):

```python
    if os.environ.get(STRIKT_ENV):
        onverwacht = _onverwachte_overslagen(overgeslagen_rapporten)
        if onverwacht:
            rapporteur.write_line(
                f"{STRIKT_ENV} staat aan, maar {len(onverwacht)} overslagen hebben een reden "
                "die niet zegt dat ze verwacht zijn. Noem `data/` in de reden als de test echte "
                "data nodig heeft, of het BO-nummer van de bewuste uitzondering; is het geen van "
                "beide, dan is er een fixture, generator of tool weggevallen:",
                red=True,
            )
            for nodeid, reden in onverwacht:
                rapporteur.write_line(f"  {nodeid}: {reden}", red=True)
            gezakt = True
```

Werk de docstring van `pytest_sessionfinish` bij: de zin over "de bovengrens op de overslagen" wordt "De strikte overslagcontrole doet het omgekeerde: zij hangt niet aan een aantal maar aan de reden van elke overslag, en veroudert dus niet met de suite mee." Grep daarna `MAXIMUM_OVERGESLAGEN_ENV` in `tests/`: nul treffers.

Run: `uv run pytest tests/test_poort.py -q` → PASS. En de echte controle: `NLRIOCHECKER_STRIKTE_OVERSLAG=1 uv run pytest -q` moet lokaal groen zijn (de enige lokale overslag is BO-40); zet daarna tijdelijk `VERWACHTE_REDENEN = ("nooit",)` en zie de run rood worden met de BO-40-regel erbij; zet terug. Meld beide uitkomsten in je rapport.

- [ ] **Step 3: Workflow**

In `.github/workflows/toets.yml` vervang je het hele blok vanaf de regel `# De ondergrens hierboven is nu tweemaal met de hand nagetrokken nadat hij was` (regel 61) tot en met `NLRIOCHECKER_MAX_OVERGESLAGEN: "65"` (regel 90) door:

```yaml
      # Overslagen worden niet geteld maar op reden geclassificeerd (BO-48). Een telgrens
      # (`NLRIOCHECKER_MAX_OVERGESLAGEN`, 50 → 57 → 65) telde ook de bedoelde, datagebonden
      # overslagen mee -- de ontologie, het Juinen-voorbeeld en de SHACL-rapporten staan
      # niet op deze runner -- en klapte op 24-08 en 25-08 op legitieme testgroei. Met deze
      # vlag is elke test-overslag waarvan de reden geen `data/` en geen `BO-` noemt een
      # harde fout: een fixture die niet meekomt, een generator die niet gedraaid is, een
      # tool die hier ontbreekt. Geen getal meer om te herijken. Lokaal na te spelen met
      # `uv run python scripts/runnerpoort.py`. De controle zelf staat in tests/conftest.py.
      NLRIOCHECKER_STRIKTE_OVERSLAG: "1"
```

Laat `NLRIOCHECKER_MIN_GESLAAGD` en `NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` met hun commentaar staan. Controleer de YAML met `uv run python -c "import tomllib" ` — nee: YAML heeft geen stdlib-parser; controleer de inspringing met het oog en met `grep -n 'NLRIOCHECKER_' .github/workflows/toets.yml` (drie variabelen, gelijke inspringing).

- [ ] **Step 4: Schrijf de falende tests voor het script**

`tests/test_runnerpoort.py`:

```python
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
```

Run: `uv run pytest tests/test_runnerpoort.py -q` → FAIL (script bestaat niet).

- [ ] **Step 5: Het script**

`scripts/runnerpoort.py`:

```python
#!/usr/bin/env python
"""Draait de poort in de conditie van de CI-runner, vóór je pusht.

De runner heeft van `data/` alleen wat git kent (de checkregisters en de
vocabulaire-index), geen PyQGIS, en de grensvariabelen uit
`.github/workflows/toets.yml`. Een test die hier slaagt maar daar overslaat -- of andersom
-- zie je pas na de push, en dan als rode run. Dit script bootst die conditie na: het zet
`data/` tijdelijk opzij, zet alleen de getrackte bestanden terug, zet PyQGIS uit en draait
dezelfde pytest-regel met dezelfde omgeving als de workflow. Beide leest het uit de
workflow zelf, zodat er maar een waarheid is (BO-48).

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
    if OPZIJ.exists():
        raise SystemExit(
            f"{OPZIJ.name}/ bestaat al: een eerdere run is niet netjes teruggezet. Zet hem zelf "
            f"terug (mv {OPZIJ.name} data) en probeer opnieuw."
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
        OPZIJ.rename(DATA)
        print("data/ teruggezet")


if __name__ == "__main__":
    sys.exit(main())
```

Run: `uv run pytest tests/test_runnerpoort.py -q` → PASS. Daarna het script zelf: `uv run python scripts/runnerpoort.py` → verwacht groen (geslaagd ≥ 1200, alle overslagen met een `data/`- of `BO-`-reden, 1 moduleskip). Controleer erna `ls data | wc -l` (weer 9 items) en `git status --short` (geen sporen). Zet de laatste regels van de uitvoer in je rapport.

- [ ] **Step 6: Documentatie**

1. `README.md:351`: vervang `NLRIOCHECKER_MIN_GESLAAGD` en `NLRIOCHECKER_MAX_OVERGESLAGEN` door `NLRIOCHECKER_MIN_GESLAAGD` en `NLRIOCHECKER_STRIKTE_OVERSLAG` en pas de zin aan zodat hij klopt (lees de omringende alinea; "dat er niet te veel overslaan" wordt "dat elke overslag een verklaarde reden heeft").
2. `docs/agents/analyse-harness.md:92-99`: vervang de bullet die begint met `**CI kan "N geslaagd" tonen én toch exit 1 geven.**` door:

```markdown
- **CI kan "N geslaagd" tonen én toch exit 1 geven.** `.github/workflows/toets.yml` zet
  `NLRIOCHECKER_STRIKTE_OVERSLAG`: elke test-overslag waarvan de reden geen `data/` en geen
  `BO-` noemt is daar een harde fout (BO-48). Een nieuwe test die echte data laadt hoort dus
  "… staat niet in data/" in zijn skip-reden te dragen; een bewuste uitzondering noemt haar
  BO-nummer. Speel de runner-conditie lokaal na met `uv run python scripts/runnerpoort.py`
  vóór je pusht: alleen de getrackte `data/`-bestanden, geen PyQGIS, dezelfde grenzen.
```

3. `CLAUDE.md`, in de bullet over de mechanische poort (regel ~196), ná de zin die eindigt op `draait bij elke commit die `src/**.py` raakt.` de zin: `Vóór een push die tests toevoegt die echte data laden: `uv run python scripts/runnerpoort.py` — dezelfde poort in de conditie van de CI-runner (alleen getrackte `data/`, geen PyQGIS, strikte overslagbewaking).`
4. `docs/beslislog.md`, aan het einde:

```markdown

### BO-48 De CI-poort classificeert overslagen op reden; de telgrens vervalt

**Wat.** `NLRIOCHECKER_MAX_OVERGESLAGEN` (een bovengrens op het aantal overgeslagen tests)
vervalt. Met `NLRIOCHECKER_STRIKTE_OVERSLAG` gezet (CI, en `scripts/runnerpoort.py`) laat
`tests/conftest.py` de run vallen op elke test-overslag waarvan de reden geen `data/` en geen
`BO-` noemt, met nodeid en reden in de uitvoer. `NLRIOCHECKER_MIN_GESLAAGD` en
`NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` blijven. `scripts/runnerpoort.py` draait de poort lokaal
in de runner-conditie en leest grenzen en pytest-regel uit de workflow.

**Waarom.** De telgrens telde ook de bedoelde overslagen mee -- 57 van de 58 op de runner zijn
tests die de ontologie, het Juinen-voorbeeld, de SHACL-rapporten of de externe bronnen nodig
hebben, en die staan daar niet -- en klapte daardoor twee keer in twee dagen op legitieme groei
(24-08: 51 → grens 57; 25-08: 59 → grens 65). Wat hij moest vangen is een fixture die niet
meekomt, een generator die niet gedraaid is of een tool die ontbreekt: overslagen met een
ándere reden. Op reden classificeren vangt precies die, zonder getal dat met de suite mee
moet, en is strenger dan de oude marge van zes.

**Conventie die dit oplegt.** Een skip-reden zegt waar hij vandaan komt: "… staat niet in
data/" voor echte data, het BO-nummer voor een bewuste uitzondering. Een reden die geen van
beide draagt is op CI rood -- ook als de overslag terecht was; dan is de reden fout, niet de
poort.

**Alternatieven.** De telgrens blijven herijken (verworpen: twee keer in twee dagen, en elke
herijking is handwerk dat de volgende sessie herhaalt). Een aparte lijst verwachte tests
(verworpen: dubbele administratie die achterloopt). Alleen de lokale runnerpoort (verworpen:
vangt de fout vóór de push, maar de grens zelf blijft verkeerd).
```

5. `CHANGELOG.md`, onder `## [Unreleased]` → `### Gewijzigd`, bovenaan:

```markdown
- **De CI-poort classificeert overslagen op reden; de telgrens vervalt** (BO-48).
  `NLRIOCHECKER_MAX_OVERGESLAGEN` telde ook de bedoelde, datagebonden overslagen mee en
  klapte twee keer op legitieme testgroei. Met `NLRIOCHECKER_STRIKTE_OVERSLAG` is voortaan
  elke test-overslag zonder `data/` of `BO-` in zijn reden een harde fout. Nieuw:
  `scripts/runnerpoort.py` draait dezelfde poort lokaal in de conditie van de CI-runner
  (alleen getrackte `data/`, geen PyQGIS, dezelfde grenzen uit de workflow).
```

- [ ] **Step 7: Poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q && uv run python scripts/runnerpoort.py`
Expected: alles groen; de laatste regel van de runnerpoort is `data/ teruggezet` en `git status --short` toont alleen je eigen wijzigingen.

```bash
git add tests/conftest.py tests/test_poort.py tests/test_runnerpoort.py scripts/runnerpoort.py \
  .github/workflows/toets.yml README.md docs/agents/analyse-harness.md CLAUDE.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "CI: overslagen op reden geclassificeerd i.p.v. geteld; scripts/runnerpoort.py speelt de runner-conditie lokaal na (BO-48)"
```
