# De nulmeting in de meldingenstroom — implementatieplan (issue #12)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `toets --shacl` levert de SHACL-nulmetingovertredingen als meldingen met
categorie `NULMETING` en een nieuw veld `cfk`, in alle vier de uitvoervormen, uit de
ene bestaande meldingenstroom.

**Architecture:** Een nieuwe module `nulbevinding.py` zet een `Nulmeting` plus een
`GwswDataset` om in een lijst `Nulbevinding` — ontdubbeld over de conformiteitsklassen,
met de focusnode via `hasPart`/`hasAspect` omhoog herleid tot een knoop of streng, en
met de systemisch-vlag al bepaald over de volledige export. `toetsrun` bouwt die lijst
één keer, `toetsloop` hangt hem aan elke `CheckRun`, `beperk_tot_studiegebied` filtert
hem mee, en `bouw_meldingen` maakt er `Melding`s van naast die van het register.

**Tech Stack:** Python 3.12, rdflib, pandas, pytest, sqlite3.

**Spec:** `docs/superpowers/specs/2026-08-19-nulmeting-in-de-meldingenstroom-design.md`

## Global Constraints

- Eén meldingenstroom, één schrijver: alleen `uitvoer/herkomst.py` schrijft bestanden
  (`gpkg.py` en `cache.py` staan op de allowlist). De sweep in
  `tests/test_uitvoer_herkomst.py` bewaakt dat.
- `SCHEMA_VERSIE` van `"1.0"` naar `"1.1"`; `docs/json-schema.md` mee.
- Ernst uit `Severity`: `Violation` = `F`, `Warning` = `W`.
- Dimensie van elke nulmetingmelding: `Dimension.COMPLIANCE`.
- `bron = "nulmeting"`; check-ID `NULMETING-<vormnaam>`; categorie dus `NULMETING`.
- Drempels komen uit `checks.toml`, nooit hardcoded (`rapport.systemisch_drempel`).
- Nederlandse docstrings, Engelse identifiers, `ruff` + `mypy` schoon over `src/`.
- Werk op `dev`, kleine commits, een regel onder `## [Unreleased]` in `CHANGELOG.md`.

---

### Task 1: `Nulbevinding` en de join op de dataset

**Files:**
- Create: `src/nlriochecker/nulbevinding.py`
- Test: `tests/test_nulbevinding.py`
- Create: `tests/fixtures/ttl/nulmeting_join.ttl`
- Create: `tests/fixtures/shacl/join_mdsplan.csv`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Nulbevinding` met velden `check_id: str`,
    `vorm: str`, `focus_node: str`, `ernst: str`, `object_uri: str`,
    `object_label: str`, `objecttype: str`, `boodschap: str`, `waarde: str`,
    `cfk: tuple[str, ...]`, `systemisch: bool`, `herleid: bool`.
  - `bouw_nulbevindingen(nulmeting: Nulmeting, dataset: GwswDataset, drempel: float) -> list[Nulbevinding]`
  - `CHECK_VOORVOEGSEL: str = "NULMETING"`

- [ ] **Step 1: schrijf de falende tests**

`tests/test_nulbevinding.py`, met een handgeschreven TTL waarin één streng
`:lei1-2-1` met een `BeginpuntLeiding` `:lei1-2-1_o_beg` hangt, plus een put
`:knp1` zonder geometrie en een put `:knp2` mét geometrie.

```python
def test_focusnode_op_een_knoop_joint_direct(...): ...
def test_focusnode_op_een_eindpunt_herleidt_naar_de_streng(...): ...
def test_focusnode_zonder_object_blijft_onherleid(...): ...
def test_dezelfde_overtreding_in_twee_cfks_geeft_een_melding_met_beide(...): ...
def test_violation_wordt_F_en_warning_wordt_W(...): ...
def test_systemisch_boven_de_drempel_per_vorm_en_objecttype(...): ...
def test_onbekend_objecttype_is_nooit_systemisch(...): ...
```

- [ ] **Step 2: draai ze en zie ze falen** — `uv run pytest tests/test_nulbevinding.py -q`
- [ ] **Step 3: schrijf `nulbevinding.py`**
- [ ] **Step 4: groen** — `uv run pytest tests/test_nulbevinding.py -q`
- [ ] **Step 5: commit**

### Task 2: `cfk` op `Melding`, en de nulbevindingen door `bouw_meldingen`

**Files:**
- Modify: `src/nlriochecker/uitvoer/melding.py`
- Modify: `src/nlriochecker/checks/base.py` (`CheckRun.nulbevindingen`, filter in
  `beperk_tot_studiegebied`)
- Test: `tests/test_uitvoer_melding.py`

**Interfaces:**
- Consumes: `Nulbevinding`, `bouw_nulbevindingen` uit Task 1.
- Produces: `Melding.cfk: tuple[str, ...]`, `BRON_NULMETING = "nulmeting"`,
  `CheckRun.nulbevindingen: tuple[Nulbevinding, ...]`.

- [ ] **Step 1..5** — zelfde TDD-lus: test dat een `CheckRun` met nulbevindingen
  meldingen met `bron="nulmeting"`, gevuld `cfk` en `dimensie="Compliance"` oplevert;
  dat een eigen-checkmelding `cfk == ()` houdt; dat `beperk_tot_studiegebied` een
  nulbevinding buiten het gebied weglaat en een onherleide erin houdt met leeg gebied.

### Task 3: de vier uitvoervormen dragen `cfk`

**Files:**
- Modify: `src/nlriochecker/uitvoer/bevindingen.py` (`CSV_KOLOMMEN`,
  `meldingen_tabel`, `meldingen_json`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`MELDING_KOLOMMEN`, `_melding_rij`)
- Modify: `src/nlriochecker/uitvoer/herkomst.py` (`SCHEMA_VERSIE = "1.1"`)
- Modify: `docs/json-schema.md`
- Test: `tests/test_uitvoer_herkomst.py`, `tests/test_uitvoer_gpkg.py`

- [ ] **Step 1..5** — de drifttests eisen het veld in het document en de versie in
  het voorbeeld; de GPKG-test eist de kolom `cfk` in `meldingen`.

### Task 4: `toetsrun` en `toetsloop` voeren de nulbevindingen aan

**Files:**
- Modify: `src/nlriochecker/toetsrun.py`
- Modify: `src/nlriochecker/toetsloop.py`
- Test: `tests/test_toetsrun.py`, `tests/test_toetsloop.py`

- [ ] **Step 1..5** — `_typeringspoort` levert voortaan ook de `Nulmeting` terug,
  zodat het rapport één keer gelezen wordt; `toets_gebieden` krijgt
  `nulbevindingen` mee en zet ze op elke run vóór `beperk_tot_studiegebied`.

### Task 5: het rapport zwijgt niet

**Files:**
- Modify: `src/nlriochecker/uitvoer/bevindingen.py` (`_render_checks`)
- Test: `tests/test_uitvoer_herkomst.py` of een nieuw `tests/test_uitvoer_nulmeting.py`

- [ ] **Step 1..5** — een blok met het aantal nulmetingmeldingen, de verdeling per
  CFK, en de twee tellingen uit K2 (geen object; object zonder geometrie), ook als
  ze nul zijn.

### Task 6: documentatie, wijzigingslog en beslislog

**Files:**
- Modify: `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `docs/beslislog.md` (BO-28)

- [ ] **Step 1: schrijf ze** — [ ] **Step 2: `ruff`, `mypy`, `pytest`** — [ ] **Step 3: commit**
