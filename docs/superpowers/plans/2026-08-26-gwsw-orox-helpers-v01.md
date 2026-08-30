# gwsw-orox-helpers v0.1 — verhuizing leescluster: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De OroX-leeslaag van nlriochecker verhuist één-op-één naar de nieuwe publieke package `gwsw-orox-helpers` (repo `mcolee/gwsw-orox-helpers`, MIT); nlriochecker gaat erop draaien via een git-dependency, zonder gedragswijziging.

**Architecture:** Twee repo's. Fase A bouwt de package op `/home/martin/gwsw-orox-helpers`: zeven modules (`dataset`, `graaf`, `geometry`, `ontologie`, `cache`, `voortgang`, `errors`), gebundelde GWSW-ontologie 1.6 + vocabulaire-index als package-resources, negen verhuisde testmodules met eigen fixtures, zelfde vijfstappenpoort in GitHub Actions. Fase B zet nlriochecker om: dependency erbij, oude modules eruit, mechanische importomzetting, generieke parameters (vulwaarden, encoding) gevuld vanuit nlriochecker-constanten, `--ontologie` optioneel op de gebundelde ontologie.

**Tech Stack:** Python 3.12+, uv, hatchling, pyoxigraph, rdflib, shapely, ruff, mypy, pytest (+pytest-cov via `--with`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-26-gwsw-orox-helpers-design.md`

## Global Constraints

- Package-naam `gwsw-orox-helpers`, importnaam `gwsw_orox_helpers`, licentie MIT, versie start op `0.1.0`.
- Nederlandse identifiers en docstrings; modulenamen blijven exact gelijk (`dataset.py`, `graaf.py`, `geometry.py`, `ontologie.py`, `cache.py`, `voortgang.py`, `errors.py`).
- Dependencies van de package: uitsluitend `pyoxigraph>=0.5`, `rdflib>=7.0`, `shapely>=2.0`. Geen click, geen networkx, geen pandas.
- De package kent géén nlriochecker-begrippen: geen `VULWAARDE_KENMERKEN`, geen `cp850`-default, geen `CheckConfig`.
- Kwaliteitspoort in beide repo's: `uv run ruff check`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`, `uv run --with pytest-cov pytest --cov=<pkg> --cov-fail-under=95`.
- Gedrag van nlriochecker verandert niet (op de nieuwe optionele `--ontologie`-default na); alle bestaande tests blijven groen.
- nlriochecker-werk gebeurt op `dev`. De nieuwe repo werkt op `main` (er is daar nog geen release-splitsing).
- Commits: kleine stappen, na elke groene stap.

---

## Fase A — de package

### Task 1: Repo-skelet gwsw-orox-helpers

**Files:**
- Create: `/home/martin/gwsw-orox-helpers/pyproject.toml`
- Create: `/home/martin/gwsw-orox-helpers/LICENSE` (MIT), `README.md`, `CHANGELOG.md`, `.gitignore`, `CLAUDE.md`
- Create: `/home/martin/gwsw-orox-helpers/src/gwsw_orox_helpers/__init__.py`, `py.typed`
- Create: `/home/martin/gwsw-orox-helpers/.github/workflows/toets.yml`

**Interfaces:**
- Produces: een lege maar installeerbare package met werkende poort; alle latere taken werken in deze repo.

- [ ] **Step 1: Repo en skelet aanmaken**

```bash
mkdir -p /home/martin/gwsw-orox-helpers/src/gwsw_orox_helpers /home/martin/gwsw-orox-helpers/tests /home/martin/gwsw-orox-helpers/scripts /home/martin/gwsw-orox-helpers/.github/workflows
cd /home/martin/gwsw-orox-helpers && git init -b main
```

`pyproject.toml` (gespiegeld aan nlriochecker, gesnoeid tot de leeslaag):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gwsw-orox-helpers"
version = "0.1.0"
description = "Lezen (en later schrijven en clippen) van GWSW-OroX (TTL) rioleringsdatasets: grafmodel, geometrie, klassenhierarchie en cache."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.12"
dependencies = [
    # pyoxigraph levert de Rust-parser die het OroX-TTL ordegrootten sneller inleest dan
    # rdflib's pure-Python notation3.
    "pyoxigraph>=0.5",
    "rdflib>=7.0",
    "shapely>=2.0",
]

[dependency-groups]
dev = [
    "mypy>=1.11",
    "pytest>=8.2",
    "ruff>=0.6",
]

[tool.hatch.build.targets.wheel]
packages = ["src/gwsw_orox_helpers"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "N"]

[tool.ruff.lint.per-file-ignores]
# De fixturegenerator bevat GML-literalen die niet af te breken zijn zonder de
# TTL-uitvoer te veranderen.
"scripts/maak_fixtures.py" = ["E501"]

[tool.mypy]
python_version = "3.12"
files = ["src/gwsw_orox_helpers"]
# rdflib en shapely leveren geen bruikbare stubs.
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`src/gwsw_orox_helpers/__init__.py`:

```python
"""Lezen van GWSW-OroX (TTL) rioleringsdatasets."""

from importlib.metadata import version

__version__ = version("gwsw-orox-helpers")
```

`py.typed`: leeg bestand. `.gitignore`: `__pycache__/`, `.venv/`, `dist/`, `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`. `LICENSE`: standaard MIT-tekst met `Copyright (c) 2026 Martin Colee`. `README.md`: drie regels — wat het is, dat v0.1 alleen lezen dekt, verwijzing naar nlriochecker als eerste afnemer. `CHANGELOG.md`:

```markdown
# Changelog

## [Unreleased]

## [0.1.0] - 2026-08-26
- Leeslaag overgenomen uit nlriochecker: OroX-TTL naar domeinmodel, grafindex,
  GML-geometrie, ontologiefacetten, cache en voortgangsprotocol.
- GWSW-ontologie 1.6 en vocabulaire-index gebundeld als package-resources.
```

`CLAUDE.md` met de verhuisde harde regel (letterlijk overnemen, aangepast aan deze repo):

```markdown
# Project: gwsw-orox-helpers

Leeslaag voor GWSW-OroX (TTL): grafmodel, geometrie, klassenhierarchie, cache.
Eerste afnemer: nlriochecker. Nederlandse identifiers, GWSW-conform.

## Harde regels
- **Leidende GWSW-versie: 1.6**, uit de gebundelde
  `src/gwsw_orox_helpers/data/Ontologie_GWSW_Totaal.ttl` (`owl:versionInfo`).
  Upgraden is handwerk van de auteur: hij levert een nieuw ontologiebestand en dan
  trekt de package bij. Draai daarbij `uv run python scripts/maak_gwsw_index.py`
  (herschrijft de gebundelde index) en werk deze regel bij; de drifttests bewaken
  beide richtingen.
- De publieke API is wat nlriochecker importeert; breken mag tot 1.0 maar alleen
  met een CHANGELOG-regel en een versiebump.
- Geen nlriochecker-begrippen in deze package: vulwaardenlijsten, encodingkeuzes
  en checkconfiguratie zijn parameters, geen constanten.

## Werkwijze
- Python 3.12+, src-layout, uv; poort: ruff check, ruff format, mypy, pytest,
  dekking >= 95% (`uv run --with pytest-cov pytest --cov=gwsw_orox_helpers`).
```

`.github/workflows/toets.yml`:

```yaml
name: toets
on:
  push:
  pull_request:
jobs:
  poort:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check
      - run: uv run ruff format --check .
      - run: uv run mypy
      - run: uv run --with pytest-cov pytest -q --cov=gwsw_orox_helpers --cov-fail-under=95
```

- [ ] **Step 2: Poort draait (leeg maar groen)**

Run: `cd /home/martin/gwsw-orox-helpers && uv sync && uv run ruff check && uv run ruff format --check . && uv run mypy`
Expected: alles groen; pytest slaan we hier over (nog geen tests — de CI-run met `--cov-fail-under` wordt pas relevant vanaf Task 2).

- [ ] **Step 3: GitHub-repo aanmaken en eerste commit**

```bash
git add -A && git commit -m "Skelet: uv/src-layout, MIT, poort in GitHub Actions"
gh repo create mcolee/gwsw-orox-helpers --public --source . --push
```

### Task 2: Modules verhuizen

**Files:**
- Create: `src/gwsw_orox_helpers/{dataset,graaf,geometry,ontologie,cache,voortgang,errors}.py` (kopieën uit `/home/martin/nlriochecker/src/nlriochecker/`)

**Interfaces:**
- Produces: `from gwsw_orox_helpers.dataset import GwswDataset, Node, Conduit, Aspect, Inwinning, load_dataset, markeer_vulwaarden, parts_of, part_holders_of, aspects_of, aspect_holders_of, GWSW, HAS_CONNECTION, HAS_VALUE, HAS_REFERENCE, HAS_ASPECT, HAS_PART` — exact de huidige signaturen (generiek maken volgt in Task 3). `from gwsw_orox_helpers.errors import OroxError, DatasetError`. `from gwsw_orox_helpers.cache import laad_met_cache, cachesleutel, CacheUitslag, standaard_cachemap, BESTAND_GRAAF, BESTAND_STRUCTUREN`. `from gwsw_orox_helpers.voortgang import Voortgang, NulVoortgang, NUL_VOORTGANG`. `from gwsw_orox_helpers.geometry import GeometryError, parse_gml, parse_gml_z, is_multipart_literal`. `from gwsw_orox_helpers.ontologie import Facetbereik, kenmerkbereik, verwachte_property, functie_van_klasse`. `from gwsw_orox_helpers.graaf import GraafIndex`.

- [ ] **Step 1: Kopiëren en imports hernoemen**

```bash
for m in dataset graaf geometry ontologie cache voortgang; do
  cp /home/martin/nlriochecker/src/nlriochecker/$m.py src/gwsw_orox_helpers/$m.py
done
grep -rl "from nlriochecker" src/ | xargs sed -i 's/from nlriochecker import/from gwsw_orox_helpers import/; s/from nlriochecker\./from gwsw_orox_helpers./'
```

- [ ] **Step 2: Eigen errors.py schrijven**

`src/gwsw_orox_helpers/errors.py` (níét gekopieerd — de package kent geen `PipelineError`):

```python
"""Uitzonderingen van gwsw-orox-helpers."""


class OroxError(Exception):
    """Basisfout van de leeslaag; afnemers vangen deze."""


class DatasetError(OroxError):
    """De OroX-dataset ontbreekt, is onleesbaar of bevat geen toetsbare objecten."""
```

De docstring van `DatasetError` is letterlijk die uit nlriochecker. `dataset.py` importeert hem al goed na de sed (`from gwsw_orox_helpers.errors import DatasetError`).

- [ ] **Step 3: Cachemapnaam op de package zetten**

In `src/gwsw_orox_helpers/cache.py`, functie `standaard_cachemap` (rond r. 158-161): vervang de letterlijke mapnaam `"nlriochecker"` door `"gwsw-orox-helpers"`. Verder niets — de broncode-hash-mechaniek (`module.__file__`) werkt padonafhankelijk.

- [ ] **Step 4: Lint/type-poort groen**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy`
Expected: groen. Faalt ruff format op de gekopieerde bestanden, draai `uv run ruff format` en bekijk de diff (moet leeg of triviaal zijn — de bron was al geformatteerd op line-length 100).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Leeslaag overgenomen uit nlriochecker (dataset, graaf, geometry, ontologie, cache, voortgang, errors)"
```

### Task 3: Generieke parameters — vulwaarden en encoding

**Files:**
- Modify: `src/gwsw_orox_helpers/dataset.py`, `src/gwsw_orox_helpers/cache.py`
- Test: `tests/test_generieke_parameters.py`

**Interfaces:**
- Produces: `markeer_vulwaarden(dataset: GwswDataset, kenmerken: Collection[str]) -> None` (parameter verplicht; de constante `VULWAARDE_KENMERKEN` verdwijnt uit deze package). `load_dataset(dataset_path, ontology_paths, fallback_encoding: str | None = None, *, voortgang=NUL_VOORTGANG)` — `None` betekent: alleen UTF-8, een decodeerfout is een `DatasetError`. `cachesleutel(..., fallback_encoding: str | None = None)` en `laad_met_cache(..., fallback_encoding: str | None = None)` idem. De constante `FALLBACK_ENCODING` verdwijnt uit deze package.

- [ ] **Step 1: Falende tests schrijven**

`tests/test_generieke_parameters.py`:

```python
"""De package kent geen afnemersspecifieke defaults: vulwaardenlijst en encoding zijn parameters."""

import inspect
from pathlib import Path

import pytest

from gwsw_orox_helpers.cache import cachesleutel, laad_met_cache
from gwsw_orox_helpers.dataset import load_dataset, markeer_vulwaarden
from gwsw_orox_helpers.errors import DatasetError

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_markeer_vulwaarden_eist_de_kenmerkenlijst() -> None:
    parameters = inspect.signature(markeer_vulwaarden).parameters
    assert parameters["kenmerken"].default is inspect.Parameter.empty


def test_geen_encoding_fallback_zonder_opgave() -> None:
    with pytest.raises(DatasetError):
        load_dataset(TTL_DIR / "codering_cp850.ttl")


def test_encoding_fallback_op_verzoek() -> None:
    dataset = load_dataset(TTL_DIR / "codering_cp850.ttl", fallback_encoding="cp850")
    assert dataset.nodes


def test_cachesleutel_draagt_de_encodingkeuze() -> None:
    for functie in (cachesleutel, laad_met_cache):
        parameter = inspect.signature(functie).parameters["fallback_encoding"]
        assert parameter.default is None
```

Vereist de fixture `codering_cp850.ttl`; kopieer die nu vast:

```bash
mkdir -p tests/fixtures/ttl
cp /home/martin/nlriochecker/tests/fixtures/ttl/codering_cp850.ttl tests/fixtures/ttl/
```

- [ ] **Step 2: Run — verifieer dat ze falen**

Run: `uv run pytest tests/test_generieke_parameters.py -v`
Expected: FAIL (defaults bestaan nog: `kenmerken=VULWAARDE_KENMERKEN`, `fallback_encoding="cp850"`).

- [ ] **Step 3: Implementeren**

In `src/gwsw_orox_helpers/dataset.py`:
- Verwijder de constanten `FALLBACK_ENCODING` en `VULWAARDE_KENMERKEN`.
- `load_dataset(..., fallback_encoding: str | None = None, ...)`: de bestaande decodeer-fallbacklus slaat de fallbackpoging over als de waarde `None` is en raist dan de bestaande `DatasetError` ("bestand kan niet gelezen worden").
- `markeer_vulwaarden(dataset, kenmerken)`: tweede parameter zonder default; de body gebruikt `kenmerken` waar hij nu de constante las.

In `src/gwsw_orox_helpers/cache.py`:
- Importregel `FALLBACK_ENCODING` weg; `cachesleutel(..., fallback_encoding: str | None = None)` en hash de tekst `str(fallback_encoding)` zodat `None` en `"cp850"` verschillende sleutels geven; `laad_met_cache` geeft de parameter door.

- [ ] **Step 4: Run — groen**

Run: `uv run pytest tests/test_generieke_parameters.py -v && uv run mypy && uv run ruff check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Vulwaardenlijst en encoding-fallback zijn parameters, geen package-constanten"
```

### Task 4: Ontologie en vocabulaire-index bundelen

**Files:**
- Create: `src/gwsw_orox_helpers/data/Ontologie_GWSW_Totaal.ttl` (kopie, 2,6 MB), `src/gwsw_orox_helpers/data/gwsw-vocabulaire-index.json` (kopie, 316 kB)
- Create: `src/gwsw_orox_helpers/bronnen.py`
- Create: `scripts/maak_gwsw_index.py` (verhuisd uit nlriochecker, paden aangepast)
- Test: `tests/test_bronnen.py`, `tests/test_gwsw_index.py`

**Interfaces:**
- Produces: `from gwsw_orox_helpers.bronnen import gebundelde_ontologie, vocabulaire_index_pad` — beide `-> Path`, wijzend naar de meegeleverde bestanden. `load_dataset(pad)` zonder `ontology_paths` gebruikt de gebundelde ontologie; `ontology_paths=[]` betekent expliciet "geen ontologie" (klassenhierarchie onbekend, zoals nu met `--geen-ontologie`).

- [ ] **Step 1: Data kopiëren en falende tests schrijven**

```bash
mkdir -p src/gwsw_orox_helpers/data
cp /home/martin/nlriochecker/data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl src/gwsw_orox_helpers/data/
cp /home/martin/nlriochecker/data/gwsw-vocabulaire-index.json src/gwsw_orox_helpers/data/
```

`tests/test_bronnen.py`:

```python
"""De gebundelde ontologie en index zijn als resource bereikbaar en consistent."""

import json
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie, vocabulaire_index_pad
from gwsw_orox_helpers.dataset import load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_gebundelde_ontologie_bestaat_en_draagt_versie_1_6() -> None:
    pad = gebundelde_ontologie()
    assert pad.exists()
    kop = pad.read_text(encoding="utf-8")[:2000]
    assert "versie=1.6" in kop


def test_index_bestaat_en_is_gevuld() -> None:
    index = json.loads(vocabulaire_index_pad().read_text(encoding="utf-8"))
    assert len(index["termen"]) > 3_000


def test_load_dataset_gebruikt_standaard_de_gebundelde_ontologie() -> None:
    dataset = load_dataset(TTL_DIR / "codering_cp850.ttl", fallback_encoding="cp850")
    assert dataset.klassenhierarchie_bekend


def test_lege_lijst_betekent_geen_ontologie() -> None:
    dataset = load_dataset(
        TTL_DIR / "codering_cp850.ttl", ontology_paths=[], fallback_encoding="cp850"
    )
    assert not dataset.klassenhierarchie_bekend
```

Let op: klopt de sleutelnaam `termen` niet met de echte JSON-structuur, neem dan de echte structuur over (kijk in het bestand) — de test toetst omvang, niet vorm. En verifieer bij het schrijven dat `klassenhierarchie_bekend` een property zonder argumenten is (zo staat hij in de inventaris, `dataset.py:577`); pas de aanroep anders aan.

- [ ] **Step 2: Run — verifieer dat ze falen**

Run: `uv run pytest tests/test_bronnen.py -v`
Expected: FAIL (`bronnen.py` bestaat niet; `ontology_paths` heeft geen default).

- [ ] **Step 3: Implementeren**

`src/gwsw_orox_helpers/bronnen.py`:

```python
"""Toegang tot de meegeleverde GWSW-ontologie en vocabulaire-index."""

from importlib.resources import files
from pathlib import Path


def gebundelde_ontologie() -> Path:
    """Pad naar de meegeleverde GWSW-ontologie (deelmodel Totaal)."""
    return Path(str(files("gwsw_orox_helpers").joinpath("data/Ontologie_GWSW_Totaal.ttl")))


def vocabulaire_index_pad() -> Path:
    """Pad naar de meegeleverde vocabulaire-index (JSON)."""
    return Path(str(files("gwsw_orox_helpers").joinpath("data/gwsw-vocabulaire-index.json")))
```

In `src/gwsw_orox_helpers/dataset.py`: `load_dataset(dataset_path, ontology_paths: list[Path] | None = None, ...)`; bij `None` wordt het `[gebundelde_ontologie()]` (import bovenin uit `.bronnen` — geen circulaire import, `bronnen` importeert niets uit `dataset`). Een lege lijst blijft een lege lijst. In `pyproject.toml` niets nodig: hatchling neemt `src/gwsw_orox_helpers/data/` automatisch mee in de wheel (controleer met `uv build` + `unzip -l dist/*.whl | grep data/` als je twijfelt).

Verhuis `scripts/maak_gwsw_index.py` uit nlriochecker: kopieer, en pas de kopregels aan:

```python
from gwsw_orox_helpers.dataset import GWSW

WORTEL = Path(__file__).resolve().parents[1]
ONTOLOGIE = WORTEL / "src" / "gwsw_orox_helpers" / "data" / "Ontologie_GWSW_Totaal.ttl"
DOEL = WORTEL / "src" / "gwsw_orox_helpers" / "data" / "gwsw-vocabulaire-index.json"
```

`tests/test_gwsw_index.py` — de drifttest dat de index de ontologie volgt (het equivalent van `test_index_volgt_de_ontologie` in nlriochecker):

```python
"""De gebundelde index is exact wat de generator uit de gebundelde ontologie maakt."""

import importlib.util
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]


def _generator():
    spec = importlib.util.spec_from_file_location(
        "maak_gwsw_index", WORTEL / "scripts" / "maak_gwsw_index.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_index_volgt_de_ontologie() -> None:
    generator = _generator()
    assert generator.DOEL.read_text(encoding="utf-8") == generator.documenttekst(
        generator.ONTOLOGIE
    )
```

Neem daarnaast uit nlriochecker's `tests/test_gwsw_vocabulaire.py` de CLAUDE.md-versietest over, aangepast: `test_indexversie_staat_in_claude_md` leest `owl:versionInfo` uit de gebundelde ontologie en asserteert dat het versienummer in deze repo's `CLAUDE.md` staat (kopieer de bestaande testfunctie en vervang de paden; de exacte regex staat in die functie — neem hem letterlijk over).

- [ ] **Step 4: Run — groen**

Run: `uv run pytest tests/ -v && uv run mypy && uv run ruff check`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "GWSW-ontologie 1.6 en vocabulaire-index gebundeld; load_dataset default op de gebundelde ontologie"
```

### Task 5: Tests en fixtures verhuizen

**Files:**
- Create: `tests/test_dataset.py`, `test_dataset_codering.py`, `test_dataset_inwinning.py`, `test_dataset_vulwaarden.py`, `test_graaf.py`, `test_geometry.py`, `test_ontologie.py`, `test_cache.py`, `test_cachemap.py` (verhuisd uit nlriochecker, aangepast)
- Create: `tests/fixtures/ttl/*.ttl` (17 stuks), `scripts/maak_fixtures.py`, `tests/test_fixtures.py`

**Interfaces:**
- Consumes: de publieke API uit Task 2-4.
- Produces: een suite die de leeslaag volledig dekt; `scripts/maak_fixtures.py` met `FIXTURES`-dict en `render(defect, inhoud)`, zelfde mechaniek als nlriochecker's generator.

- [ ] **Step 1: Fixtures overbrengen**

De 17 fixtures die de verhuizende tests gebruiken (lijst uit de inventaris): `adm007_overstort_met_drempel`, `attr013_vulwaarde_hoogte`, `codering_cp850` (staat er al), `dataset_dubbele_schrijfrichting`, `dataset_fantoomkoppeling`, `dataset_inverse_properties`, `dataset_meervoudig_objecttype`, `dataset_twee_houders_put_eerst`, `dataset_twee_houders_straat_eerst`, `dataset_zwaarverkeerdeksel`, `ext_scenario`, `net001_bouwwerk_eindknoop`, `schoon`, `stelsels_registratie`, `top001_losliggende_put`, `top020_omgekeerd_getekend`, `top022_hulpstuk_te_weinig` (alle `.ttl`).

```bash
cd /home/martin/nlriochecker/tests/fixtures/ttl && cp adm007_overstort_met_drempel.ttl attr013_vulwaarde_hoogte.ttl dataset_dubbele_schrijfrichting.ttl dataset_fantoomkoppeling.ttl dataset_inverse_properties.ttl dataset_meervoudig_objecttype.ttl dataset_twee_houders_put_eerst.ttl dataset_twee_houders_straat_eerst.ttl dataset_zwaarverkeerdeksel.ttl ext_scenario.ttl net001_bouwwerk_eindknoop.ttl schoon.ttl stelsels_registratie.ttl top001_losliggende_put.ttl top020_omgekeerd_getekend.ttl top022_hulpstuk_te_weinig.ttl /home/martin/gwsw-orox-helpers/tests/fixtures/ttl/
```

`scripts/maak_fixtures.py`: kopieer uit nlriochecker's `scripts/maak_ttl_fixtures.py` de `PRELUDE`, de helperfuncties (`put`, `hulpstuk`, `leiding`, `kenmerken`, `maat`, `maaiveld`, `deksel`, `drempel`, `nette_put`, `nette_leiding` — en wat de onderstaande entries verder nodig hebben), `render()` en `main()`, maar met een `FIXTURES`-dict die alléén de 13 gegenereerde van de 17 bevat (alles behalve `codering_cp850`, `net001_bouwwerk_eindknoop`, `schoon`, `top001_losliggende_put` — die vier zijn handwerk en bestaan alleen als bestand). Zet `DOEL = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ttl"` (absoluut, niet relatief aan de cwd zoals het origineel).

`tests/test_fixtures.py` (drifttest, naar het model van nlriochecker's `test_ttl_fixtures.py`):

```python
"""Elke gegenereerde fixture op schijf is exact wat de generator maakt."""

import importlib.util
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[1]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def _generator():
    spec = importlib.util.spec_from_file_location(
        "maak_fixtures", WORTEL / "scripts" / "maak_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GENERATOR = _generator()


@pytest.mark.parametrize("naam", sorted(GENERATOR.FIXTURES))
def test_fixture_volgt_de_generator(naam: str) -> None:
    defect, inhoud = GENERATOR.FIXTURES[naam]
    assert (TTL_DIR / naam).read_text(encoding="utf-8") == GENERATOR.render(defect, inhoud)
```

- [ ] **Step 2: Testmodules overbrengen en aanpassen**

```bash
cd /home/martin/nlriochecker/tests && cp test_dataset.py test_dataset_codering.py test_dataset_inwinning.py test_dataset_vulwaarden.py test_graaf.py test_geometry.py test_ontologie.py test_cache.py test_cachemap.py /home/martin/gwsw-orox-helpers/tests/
cd /home/martin/gwsw-orox-helpers && grep -rl "nlriochecker" tests/ | xargs sed -i 's/nlriochecker\./gwsw_orox_helpers./g; s/from nlriochecker import/from gwsw_orox_helpers import/'
```

Daarna de zes inhoudelijke aanpassingen (de sed vangt de rest):

1. **`test_dataset.py`** — de functie `test_richting_van_geometrie_ziet_een_omgekeerd_getekende_lijn` importeert na de sed `gwsw_orox_helpers.checkconfig`, die niet bestaat. Vervang de twee regels

   ```python
   from gwsw_orox_helpers.checkconfig import load_check_config

   ...
   wortels = load_check_config().klassen.netwerkknopen
   ```

   door een inline literal: lees in nlriochecker de defaultwaarde na (`grep -A5 netwerkknopen /home/martin/nlriochecker/configs/*.toml` of `checkconfig.py:115-125`) en zet die lijst er letterlijk in, met een commentaarregel `# De netwerkknoop-wortels zoals nlriochecker ze configureert; hier inline om de package los te houden.`
2. **`test_dataset.py`** — `juinen`-verwijzingen: de test `test_bob_verval_ontbreekt_zonder_beide_bobs(juinen)` en de assert op `juinen.ontologies == ["Ontologie_GWSW_Totaal.ttl"]` (r. 348) leunen op nlriochecker's conftest-fixture met het (niet-getrackte) Voorbeeld-bestand. Maak in deze repo een `tests/conftest.py`:

   ```python
   """Gedeelde fixtures: een geladen voorbeelddataset op basis van een eigen fixture."""

   from pathlib import Path

   import pytest

   from gwsw_orox_helpers.dataset import GwswDataset, load_dataset

   TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


   @pytest.fixture(scope="session")
   def juinen() -> GwswDataset:
       """Sessiebrede dataset, geladen met de gebundelde ontologie."""
       return load_dataset(TTL_DIR / "schoon.ttl")
   ```

   Pas de ontologies-assert aan: de verwachte naam blijft `"Ontologie_GWSW_Totaal.ttl"` (de gebundelde), dus die test blijft letterlijk werken; controleer het bij de run. Tests die eigenschappen van het echte Voorbeeld-bestand aannamen (zoals de BOB-skip) blijven werken door hun bestaande `pytest.skip`-pad.
3. **`test_geometry.py`** — r. 82 importeert `checks.meetkunde.is_finite`. Herschrijf die assert zonder de import: `import math` en toets hetzelfde met `math.isfinite(...)` op de betreffende coördinaten (lees de testfunctie; `is_finite` is een dunne wrapper).
4. **`test_cache.py`** — verving het Voorbeeld-pad: `VOORBEELD = TTL_DIR / "schoon.ttl"` en de ontologieverwijzing wordt `gebundelde_ontologie()`. De `pytestmark = pytest.mark.skipif(...)` op het bestaan van het Voorbeeld kan weg (de fixture bestaat altijd). De monkeypatch-string `"gwsw_orox_helpers.cache.LADER_VERSIE"` is door de sed al goed.
5. **`test_cachemap.py`** — de verwachte mapnaam wordt `gwsw-orox-helpers`: `Path("/huis/iemand/.cache/gwsw-orox-helpers")` en `Path("/elders/cache/gwsw-orox-helpers")`.
6. **`test_ontologie.py`** — het pad `parents[1] / "data" / "gwsw_ontologieen" / "Ontologie_GWSW_Totaal.ttl"` wordt `gebundelde_ontologie()`; de skipifs op het bestaan ervan kunnen weg.

- [ ] **Step 3: Run — hele suite groen**

Run: `uv run pytest -q`
Expected: PASS, nul skips (alles wat vroeger op `data/` skipte draait nu op de gebundelde ontologie of eigen fixtures).

- [ ] **Step 4: Dekking meten**

Run: `uv run --with pytest-cov pytest -q --cov=gwsw_orox_helpers --cov-fail-under=95`
Expected: PASS. Zakt hij onder de 95 (kan: de suite mist nu de indirecte dekking die nlriochecker's check- en uitvoertests gaven), inventariseer de gaten met `--cov-report=term-missing` en schrijf gerichte tests bij voor de onbedekte takken vóór je verder gaat — verlaag de grens niet.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Testsuite en fixtures overgenomen; eigen generator voor de 13 gegenereerde fixtures"
```

### Task 6: Package-poort en release v0.1.0

**Files:**
- Modify: geen nieuwe — dit is de slotcontrole van fase A.

**Interfaces:**
- Produces: tag `v0.1.0` op `mcolee/gwsw-orox-helpers`, CI groen; fase B kan de dependency leggen.

- [ ] **Step 1: Volledige poort**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run --with pytest-cov pytest -q --cov=gwsw_orox_helpers --cov-fail-under=95`
Expected: alles groen.

- [ ] **Step 2: Pushen en CI afwachten**

```bash
git push && gh run watch --exit-status
```

Expected: workflow `toets` groen. Niet verder vóór dit bewijs.

- [ ] **Step 3: Taggen**

```bash
git tag v0.1.0 && git push origin v0.1.0
```

---

## Fase B — nlriochecker omzetten (werkmap `/home/martin/nlriochecker`, branch `dev`)

### Task 7: Dependency, module-verwijdering en importomzetting in src/

**Files:**
- Modify: `pyproject.toml`, alle 24 src-importregels uit de inventaris (o.a. `cli.py`, `toetsrun.py`, `toetsloop.py`, `checkconfig.py`, `checks/*.py`, `uitvoer/*.py`, `analysis.py`, `karakteristiek.py`, `nulbevinding.py`, `meting.py`, `afbakening.py`)
- Delete: `src/nlriochecker/{dataset,graaf,geometry,ontologie,cache,voortgang}.py`
- Modify: `src/nlriochecker/errors.py` (DatasetError eruit)

**Interfaces:**
- Consumes: `gwsw_orox_helpers` 0.1.0 (API uit Task 2-4).
- Produces: `nlriochecker.checkconfig.VULWAARDE_KENMERKEN` en `nlriochecker.checkconfig.FALLBACK_ENCODING` — de afnemersconstanten, door `toetsrun.py` en `cli.py` doorgegeven aan de package.

- [ ] **Step 1: Dependency leggen**

In `pyproject.toml` onder `dependencies`: `"gwsw-orox-helpers>=0.1.0"`, plus:

```toml
[tool.uv.sources]
gwsw-orox-helpers = { git = "https://github.com/mcolee/gwsw-orox-helpers", tag = "v0.1.0" }
```

Run: `uv sync && uv run python -c "import gwsw_orox_helpers; print(gwsw_orox_helpers.__version__)"`
Expected: `0.1.0`.

- [ ] **Step 2: Oude modules weg, imports om**

```bash
git rm src/nlriochecker/dataset.py src/nlriochecker/graaf.py src/nlriochecker/geometry.py src/nlriochecker/ontologie.py src/nlriochecker/cache.py src/nlriochecker/voortgang.py
grep -rl "nlriochecker\.\(dataset\|graaf\|geometry\|ontologie\|cache\|voortgang\)" src/ | xargs sed -i 's/nlriochecker\.\(dataset\|graaf\|geometry\|ontologie\|cache\|voortgang\)/gwsw_orox_helpers.\1/g'
```

Controleer daarna met `grep -rn "gwsw_orox_helpers" src/` dat precies de 24 geïnventariseerde regels omgingen en niets anders.

- [ ] **Step 3: Constanten en aanroepen bijwerken**

- `src/nlriochecker/checkconfig.py`: de importregel `from gwsw_orox_helpers.dataset import VULWAARDE_KENMERKEN` faalt (bestaat daar niet meer) — vervang hem door de definitie zelf, letterlijk overgenomen uit de oude `dataset.py` (haal de waarde uit de git-historie: `git show HEAD~1:src/nlriochecker/dataset.py | grep -A5 VULWAARDE_KENMERKEN`), plus:

  ```python
  # De Wolden-export: cp850-vervuiling in de aanlevering; zie de spec van gwsw-orox-helpers.
  FALLBACK_ENCODING = "cp850"
  ```

- `src/nlriochecker/toetsrun.py`: `markeer_vulwaarden(dataset, VULWAARDE_KENMERKEN)` (import uit `checkconfig`), en elke `laad_met_cache(...)`/`load_dataset(...)`-aanroep krijgt `fallback_encoding=FALLBACK_ENCODING`.
- `src/nlriochecker/cli.py`: `load_dataset(dataset_path, list(ontology_paths), fallback_encoding=FALLBACK_ENCODING)`; en `from gwsw_orox_helpers.errors import DatasetError` op de vier `except PipelineError`-plekken (r. 355, 396, 462, 601): `except (PipelineError, DatasetError) as error:`.
- `src/nlriochecker/errors.py`: verwijder de klasse `DatasetError` (hij leeft nu in de package); `tests/test_analysis.py` en anderen die hem importeren volgen in Task 8.
- `--ontologie` optioneel: in `cli.py` vervalt de verplichting bij `toets` — geen `--ontologie` en geen `--geen-ontologie` betekent `ontology_paths=None` richting `load_dataset` (gebundelde ontologie); `--geen-ontologie` wordt `ontology_paths=[]`. Pas in `toetsrun.py` de weigering (`voer_toets_uit`) en de foutmeldingstekst op r. 294 hierop aan: de melding verwijst niet meer naar `data/gwsw_ontologieen/...` maar zegt dat standaard de gebundelde GWSW-ontologie 1.6 van gwsw-orox-helpers geldt. De helptekst van `--ontologie` wordt: "GWSW-ontologie (TTL); standaard de gebundelde versie 1.6; meermaals toegestaan."

- [ ] **Step 4: Lint en types**

Run: `uv run ruff check && uv run mypy`
Expected: groen (pytest volgt pas na Task 8 — de testboom verwijst nu nog naar verdwenen modules).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Leeslaag vervangen door gwsw-orox-helpers 0.1.0; constanten naar checkconfig; --ontologie optioneel op de gebundelde versie"
```

### Task 8: Testboom omzetten

**Files:**
- Delete: `tests/test_dataset.py`, `test_dataset_codering.py`, `test_dataset_inwinning.py`, `test_dataset_vulwaarden.py`, `test_graaf.py`, `test_geometry.py`, `test_ontologie.py`, `test_cache.py`, `test_cachemap.py`
- Modify: `tests/conftest.py`, de 33 blijvende testbestanden met leeslaag-imports (inventarislijst), `tests/test_gwsw_vocabulaire.py`, `tests/test_checkdeclaraties_ontologie.py`, `tests/test_runnerpoort.py`, `tests/test_uitvoer_herkomst.py`, `.github/workflows/toets.yml`

**Interfaces:**
- Consumes: `gwsw_orox_helpers.bronnen.{gebundelde_ontologie, vocabulaire_index_pad}`.

- [ ] **Step 1: Verhuisde tests verwijderen, blijvende imports omzetten**

```bash
git rm tests/test_dataset.py tests/test_dataset_codering.py tests/test_dataset_inwinning.py tests/test_dataset_vulwaarden.py tests/test_graaf.py tests/test_geometry.py tests/test_ontologie.py tests/test_cache.py tests/test_cachemap.py
grep -rl "nlriochecker\.\(dataset\|graaf\|geometry\|ontologie\|cache\|voortgang\)" tests/ scripts/ | xargs sed -i 's/nlriochecker\.\(dataset\|graaf\|geometry\|ontologie\|cache\|voortgang\)/gwsw_orox_helpers.\1/g'
```

De sed dekt ook de zeven analyse-scripts en `test_voortgang.py` (die blijft: hij test de instrumentatie van de nlriochecker-pijplijn, en `NulVoortgang` komt nu uit de package). `tests/test_analysis.py`: `from nlriochecker.errors import DatasetError` wordt `from gwsw_orox_helpers.errors import DatasetError`.

- [ ] **Step 2: conftest en ontologie-paden**

In `tests/conftest.py`: `ONTOLOGIE_DIR`/`ONTOLOGIE_TTL` vervallen; de `ontologie`-fixture wordt

```python
from gwsw_orox_helpers.bronnen import gebundelde_ontologie


@pytest.fixture(scope="session")
def ontologie() -> Path:
    """De gebundelde GWSW-ontologie; altijd aanwezig."""
    return gebundelde_ontologie()
```

(de skipif op het ontbreken vervalt — de resource bestaat altijd). De `juinen`-fixture behoudt zijn skipif op het niet-getrackte `VOORBEELD_TTL`. `tests/test_integration.py`: `Ontologie_GWSW_Totaal.ttl`-pad → `gebundelde_ontologie()`; het `Ontologie_GWSW_Mds.ttl`-pad blijft op `data/` wijzen (blijft niet-getrackt, de bestaande skip dekt hem). Alle `load_dataset`-aanroepen in blijvende tests die impliciet op cp850 leunden krijgen niets extra's — controleer bij de run welke falen op de encoding en geef alleen dié `fallback_encoding="cp850"` mee.

- [ ] **Step 3: Indexlezers, runnerpoort, herkomst-allowlist**

- `tests/test_gwsw_vocabulaire.py` en `tests/test_checkdeclaraties_ontologie.py`: `INDEXBESTAND = WORTEL / "data" / "gwsw-vocabulaire-index.json"` wordt `INDEXBESTAND = vocabulaire_index_pad()` (import uit `gwsw_orox_helpers.bronnen`). In `test_gwsw_vocabulaire.py` vervallen daarnaast de tests die tegen `scripts/maak_gwsw_index.py` en de CLAUDE.md-versieregel toetsen (`test_index_volgt_de_ontologie`, `test_indexversie_staat_in_claude_md` — die leven nu in de package-repo); de AST-sweep over `src/nlriochecker` blijft en dekt vanzelf alleen nog de blijvende modules.
- `git rm scripts/maak_gwsw_index.py` en `git rm data/gwsw-vocabulaire-index.json`; haal de `!data/gwsw-vocabulaire-index.json`-regel uit `.gitignore`.
- `tests/test_runnerpoort.py`: de assert dat `getrackte_databestanden()` `gwsw-vocabulaire-index.json` bevat vervalt (de checkregister-assert blijft).
- `tests/test_uitvoer_herkomst.py`: verwijder `"nlriochecker/cache.py"` uit `MAG_ZELF_SCHRIJVEN` (dode vrijstelling).
- `.github/workflows/toets.yml`: meet na Step 4 het nieuwe aantal geslaagde tests in de CI-conditie en zet `NLRIOCHECKER_MIN_GESLAAGD` op dat aantal minus een marge van 25, met een commentaarregel met de meetdatum en de gemeten waarde (zelfde stijl als de huidige).

- [ ] **Step 4: Poort en runnerpoort**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Daarna: `uv run --with pytest-cov pytest -q --cov=nlriochecker --cov-fail-under=95`
Daarna: `uv run python scripts/runnerpoort.py`
Expected: alles groen. De dekking verschuift doordat de leeslaag uit de noemer valt; komt hij onder de 95, inventariseer met `--cov-report=term-missing` welke blijvende module de daler is en schrijf daar tests bij — verlaag de grens niet zonder BO-besluit van de auteur.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Testboom op gwsw-orox-helpers: verhuisde suites eruit, index en ontologie uit de package-resources"
```

### Task 9: data/-opruiming en documentatie

**Files:**
- Modify: `CLAUDE.md`, `docs/architectuur.md`, `docs/agents/analyse-harness.md`, `CHANGELOG.md`, `configs/dewoldenhoogeveen.toml` (commentaarregel), zeven `scripts/analyse_*.py` + `scripts/metingen/issue32_klassendekking.py` (ontologiepaden)

**Interfaces:**
- Consumes: `gebundelde_ontologie()`.

- [ ] **Step 1: Scripts op de gebundelde ontologie**

In de zeven `scripts/analyse_*.py` en `scripts/metingen/issue32_klassendekking.py`: vervang `Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")` (en de `WORTEL / ...`-variant) door `gebundelde_ontologie()` met de bijbehorende import. De niet-getrackte map `data/gwsw_ontologieen/` zelf blijft op schijf staan (De Wolden-pdf's, Hyd/Mds voor de integratietest) — er verandert niets aan `.gitignore` behalve de indexregel uit Task 8.

- [ ] **Step 2: CLAUDE.md en architectuurdocs bijwerken**

- `CLAUDE.md`: de harde regel "Leidende GWSW-versie 1.6" wordt vervangen door een verwijzing: de leidende versie leeft in `gwsw-orox-helpers` (CLAUDE.md aldaar); hier blijft alleen de aanwijzing dat een upgrade via een package-release + `uv lock` loopt. De regels over `maak_gwsw_index.py`/`test_index_volgt_de_ontologie`/`test_indexversie_staat_in_claude_md` verhuizen in dezelfde beweging (staan al in de package-CLAUDE.md uit Task 1). In de afhankelijkhedenlijst komt `gwsw-orox-helpers` erbij; de beschrijving van de leeslaagmodules verwijst naar de package. De `toets`-eis "`--ontologie` verplicht" wordt: standaard de gebundelde ontologie, `--geen-ontologie` blijft de ontsnappingsvlag (issue #33-semantiek ongewijzigd).
- `docs/architectuur.md` en `docs/agents/analyse-harness.md`: vervang verwijzingen naar `src/nlriochecker/{dataset,graaf,geometry,ontologie,cache,voortgang}.py` door de package (één zin bovenaan de betreffende secties volstaat: "deze laag leeft sinds 0.4 in gwsw-orox-helpers; de mechaniek hieronder blijft gelden"). Geen herschrijving van de inhoud.
- `configs/dewoldenhoogeveen.toml` r. 20: commentaarregel met `--ontologie data/...` bijwerken naar de nieuwe default.
- `CHANGELOG.md` onder `## [Unreleased]`: "Leeslaag (dataset, graaf, geometrie, ontologie, cache, voortgang) afgesplitst naar de package gwsw-orox-helpers 0.1.0 (MIT); `--ontologie` is optioneel geworden en valt terug op de gebundelde GWSW-ontologie 1.6."

- [ ] **Step 3: Drifttests van de docs**

Run: `uv run pytest tests/test_gwsw_vocabulaire.py tests/test_checkdeclaraties_ontologie.py tests/test_runnerpoort.py tests/test_uitgave.py -q`
Expected: PASS (geen test verwijst nog naar de verdwenen CLAUDE.md-regels of dataspaden).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "Docs en scripts op gwsw-orox-helpers: GWSW-versieregel naar de package, gebundelde ontologie als default"
```

### Task 10: Slotpoort, review en push

**Files:**
- Geen nieuwe.

- [ ] **Step 1: Volledige poort + zware integratietest**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run --with pytest-cov pytest -q --cov=nlriochecker --cov-fail-under=95 && uv run python scripts/runnerpoort.py`
Daarna éénmalig het bewijs dat de echte dataset nog laadt: `uv run pytest -m zwaar -q tests/test_integration.py`
Expected: alles groen.

- [ ] **Step 2: Review (Substantieel)**

Dit raakt kritieke paden (engine, CLI-contract, Harde regels): `/superpowers:requesting-code-review` over de gecommitte diff van fase B; verwerk de uitkomsten en draai de poort opnieuw.

- [ ] **Step 3: Pushen en CI afwachten, beide repo's**

```bash
cd /home/martin/gwsw-orox-helpers && git push && gh run watch --exit-status
cd /home/martin/nlriochecker && git push && gh run watch --exit-status
```

Expected: beide workflows groen. Pas daarna is v0.1 klaar (acceptatie uit de spec: beide CI's groen, gedrag ongewijzigd).

---

## Zelfreview-notities (verwerkt)

- De acht overlappende fixtures bestaan bewust in twee repo's; nlriochecker's `test_ttl_fixtures.py` en de identiteitssweep blijven ongewijzigd omdat álle fixtures daar blijven staan.
- `test_voortgang.py` blijft in nlriochecker (test de pijplijninstrumentatie), maar importeert de typen uit de package — gedekt door de sed in Task 8 Step 1.
- De cache-sleutel verandert eenmalig door de gewijzigde bronbytes; bestaande caches worden stilzwijgend genegeerd, precies zoals het mechanisme bedoelt.
- `standaard_cachemap` wijzigt van `~/.cache/nlriochecker` naar `~/.cache/gwsw-orox-helpers`; oude cachemappen blijven als wees achter — opruimen is aan de gebruiker (melden in de CHANGELOG-regel van de package is al gedekt door "overgenomen uit nlriochecker").
