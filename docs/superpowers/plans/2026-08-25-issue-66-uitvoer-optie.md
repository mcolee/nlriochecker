# Issue #66: `toets --uitvoer csv|json|gpkg` vervangt `--geen-gpkg` en `--geen-json` — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eén bevestigende optie `--uitvoer` (herhaalbaar; `csv`, `json`, `gpkg`; standaard alle drie) zegt welke bijproducten `toets` schrijft. Het Markdown-rapport wordt altijd geschreven. `--geen-gpkg` en `--geen-json` vervallen zonder alias. Ook de CSV is nu uit te zetten.

**Architecture:** De CLI vertaalt de keuze naar drie booleans op `Toetsopdracht` (`met_csv` komt erbij naast `met_geopackage` en `met_json`). `Uitvoer.csv` wordt `Path | None`; `schrijf_uitvoer`, `schrijf_uitvoer_gebieden` en `_schrijf_totaal` krijgen `met_csv`. `write_check_report` blijft de schrijver van Markdown én CSV en krijgt `met_csv`; zonder CSV geeft hij `(markdown, None)` terug. Alleen `toets`; `analyseer`, `dekking` en `vergelijk` veranderen niet.

**Tech Stack:** Python 3.12, click, pytest (`CliRunner`). Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #66 (`gh issue view 66 --json body --jq .body`). Eén ruling van de regisseur: `write_check_report` krijgt `met_csv` en levert `tuple[Path, Path | None]`, zodat de CSV-schrijver op zijn plek blijft en er geen tweede schrijfpad ontstaat.

## Global Constraints

- Optie `--uitvoer`, `click.Choice(["csv", "json", "gpkg"])`, `multiple=True`, `default=("csv", "json", "gpkg")`, `show_default=True`, help: `"Welke bijproducten naast het Markdown-rapport geschreven worden; meermaals toegestaan. Het rapport wordt altijd geschreven."`. `--geen-gpkg` en `--geen-json` verdwijnen volledig uit `cli.py`; wie ze opgeeft krijgt de gewone click-fout (`No such option`).
- `Toetsopdracht.met_csv: bool = True`, geplaatst vóór `met_geopackage`. De docstring van `Toetsopdracht` (regel ~48, "De vlaggen staan bevestigend …") blijft kloppen; werk hem bij als hij `geen_gpkg` als voorbeeld noemt.
- `Uitvoer.csv: Path | None`; `UitvoerPerGebied.totaal_csv` blijft `Path | None`. `Toetsuitslag._geschreven` slaat `None` al over.
- `write_check_report(run, output_dir, run_datum=None, meldingen=None, notities=(), *, met_csv: bool = True, ...)` → `tuple[Path, Path | None]`. Bestaande keyword-argumenten (waaronder `onderdrukking` uit issue #65) blijven.
- Geen overgangsperiode, geen alias, geen waarschuwing voor de oude vlaggen; het pakket is 0.x.
- Poort vóór de commit: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q` (zonder `zwaar`), op de voorgrond.
- Nederlandse docstrings, Engelse identifiers; stijl van het bestand volgen. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden, nooit `git add -A`; geen `docs/superpowers/plans/*` of `uitvoer/` toevoegen.
- CHANGELOG: onder `## [Unreleased]` → `### Gewijzigd`, als eerste regel, met de vermelding dat de twee vlaggen vervallen.

---

### Task 1: De optie, de doorgifte, de CSV-schakelaar, tests en documentatie

**Files:**
- Modify: `src/nlriochecker/cli.py:534-545, 573-597` (optie en doorgifte)
- Modify: `src/nlriochecker/toetsrun.py:48, 68-69, 245-252` (`met_csv`)
- Modify: `src/nlriochecker/uitvoer/schrijver.py` (`Uitvoer.csv`, `schrijf_uitvoer`, `schrijf_uitvoer_gebieden`, `_schrijf_totaal`)
- Modify: `src/nlriochecker/uitvoer/bevindingen.py:116-149` (`write_check_report`)
- Modify: `tests/test_cli.py:357-375, 580-598, 815-830` en nieuwe tests; `tests/test_toetsrun.py` (nieuwe test naast regel 278-290); `tests/test_uitvoer_rapportopbouw.py` of `tests/test_toetsloop.py` (twee gebieden zonder CSV)
- Modify: `README.md:213-218`, `docs/json-schema.md:13`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `Toetsopdracht`, `voer_toets_uit`, `schrijf_uitvoer(...)`, `schrijf_uitvoer_gebieden(...)`, `write_check_report(...)`, `FILE_CHECKS_CSV`/`FILE_CHECKS_JSON`/`FILE_CHECKS_MARKDOWN`, testhelper `toets(tmp_path, bestand, **opdracht)` in `tests/test_toetsrun.py` (lees regel 60-100 voor de signatuur) en `_draai(...)` in `tests/test_toetsloop.py`.
- Produces: `--uitvoer`; `Toetsopdracht.met_csv`; `Uitvoer.csv: Path | None`; `met_csv` op de drie schrijffuncties en op `write_check_report`.

- [ ] **Step 1: Schrijf de falende tests**

1. `tests/test_cli.py`: vervang in `test_geen_gpkg_slaat_de_gis_uitvoer_over` (regel 357) `"--geen-gpkg",` door `"--uitvoer", "csv", "--uitvoer", "json",` en hernoem de test naar `test_uitvoer_zonder_gpkg_slaat_de_gis_uitvoer_over`; voeg `assert (uitvoer / FILE_CHECKS_JSON).exists()` toe. Vervang in `test_toets_met_geen_json_laat_het_bestand_weg` (regel 580) `"--geen-json",` door `"--uitvoer", "csv", "--uitvoer", "gpkg",`, hernoem naar `test_uitvoer_zonder_json_laat_het_bestand_weg`. Vervang op regel ~825 `"--geen-gpkg",` door `"--uitvoer", "csv",`. Voeg direct ná de eerste hernoemde test toe:

```python
def test_zonder_uitvoer_optie_komen_alle_vier_de_bestanden(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--geen-ontologie",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--geen-cache",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_CSV).exists()
    assert (uitvoer / FILE_CHECKS_JSON).exists()
    assert len(list(uitvoer.glob("*.gpkg"))) == 1


def test_uitvoer_csv_schrijft_alleen_rapport_en_csv(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--geen-ontologie",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--geen-cache",
            "--uitvoer",
            "csv",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert sorted(p.name for p in uitvoer.iterdir()) == [FILE_CHECKS_CSV, FILE_CHECKS_MARKDOWN]
    assert "Geschreven:" in resultaat.output
    assert FILE_CHECKS_JSON not in resultaat.output


def test_uitvoer_json_en_gpkg_laat_de_csv_weg_maar_niet_het_rapport(tmp_path: Path) -> None:
    """Het rapport draagt de markering en het voorbehoud; dat is nooit uit te zetten."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--geen-ontologie",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--geen-cache",
            "--uitvoer",
            "json",
            "--uitvoer",
            "gpkg",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert not (uitvoer / FILE_CHECKS_CSV).exists()
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_JSON).exists()
    assert len(list(uitvoer.glob("*.gpkg"))) == 1


def test_de_oude_vlaggen_bestaan_niet_meer(tmp_path: Path) -> None:
    """Geen alias en geen overgangsperiode (issue #66)."""
    for vlag in ("--geen-gpkg", "--geen-json"):
        resultaat = CliRunner().invoke(
            main,
            ["toets", "--dataset", str(TTL_DIR / "schoon.ttl"), vlag, "--output", str(tmp_path)],
        )
        assert resultaat.exit_code == 2
        assert "No such option" in resultaat.output


def test_uitvoer_weigert_een_onbekende_vorm(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        ["toets", "--dataset", str(TTL_DIR / "schoon.ttl"), "--uitvoer", "xlsx", "--output", str(tmp_path)],
    )
    assert resultaat.exit_code == 2
    assert "xlsx" in resultaat.output
```

Controleer of `FILE_CHECKS_MARKDOWN` en `FILE_CHECKS_JSON` al geïmporteerd zijn (regel 1-40) en of de tests hier `--geen-cache` gebruiken; volg wat het bestand doet. Als het eerste testbestand een `.gpkg` naast de vier bestanden geen naam met `dq_` draagt, pas de `iterdir`-assertie aan op wat er werkelijk staat -- maar dan pas na Step 3.

2. `tests/test_toetsrun.py`, ná de test op regel ~278-290 (`met_json=False`):

```python
def test_zonder_csv_wordt_het_bestand_niet_geschreven_en_niet_gemeld(tmp_path: Path) -> None:
    """`met_csv=False` laat de CSV weg; het rapport blijft (issue #66)."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",), met_csv=False)

    geschreven = next(iter(uitslag.uitvoer.per_gebied.values()))
    assert geschreven.csv is None
    assert geschreven.markdown.exists()
    assert not any("bevindingen.csv" in regel for regel in uitslag.regels())
```

Pas de naam van de helper en van het rapportbestand aan op wat het bestaande `met_json`-test doet.

3. Twee gebieden zonder CSV -- in `tests/test_toetsloop.py` naast de test die `schrijf_uitvoer_gebieden(runs, tmp_path, RUNDATUM, met_geopackage=False)` aanroept (regel ~538):

```python
def test_zonder_csv_schrijft_ook_totaal_geen_csv(tmp_path: Path) -> None:
    """Issue #66: `met_csv=False` geldt per gebied én voor `totaal/`."""
    ...  # zelfde opzet als de test erboven, met met_csv=False, met_geopackage=False
    assert uitvoer.totaal_csv is None
    assert all(geschreven.csv is None for geschreven in uitvoer.per_gebied.values())
    assert not list(tmp_path.rglob("bevindingen.csv"))
    assert uitvoer.synthese is not None and uitvoer.synthese.exists()
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_cli.py tests/test_toetsrun.py tests/test_toetsloop.py -q -x -k "uitvoer or csv or oude_vlaggen"`
Expected: FAIL (`No such option: --uitvoer`, `TypeError: met_csv`).

- [ ] **Step 3: Implementeer**

1. `cli.py`: vervang de twee `@click.option`-blokken `--geen-gpkg`/`--geen-json` (regel 534-545) door:

```python
@click.option(
    "--uitvoer",
    "uitvoervormen",
    multiple=True,
    type=click.Choice(["csv", "json", "gpkg"]),
    default=("csv", "json", "gpkg"),
    show_default=True,
    help=(
        "Welke bijproducten naast het Markdown-rapport geschreven worden; meermaals "
        "toegestaan. Het rapport wordt altijd geschreven."
    ),
)
```

In de signatuur van `check_command`: `geen_gpkg: bool, geen_json: bool,` → `uitvoervormen: tuple[str, ...],`. In de `Toetsopdracht(...)`-aanroep: `met_geopackage=not geen_gpkg, met_json=not geen_json,` → `met_csv="csv" in uitvoervormen, met_geopackage="gpkg" in uitvoervormen, met_json="json" in uitvoervormen,`.

2. `toetsrun.py`: `met_csv: bool = True` vóór `met_geopackage`; in `voer_toets_uit` `met_csv=opdracht.met_csv,` vóór `met_geopackage=...` in de aanroep van `schrijf_uitvoer_gebieden`. Docstring regel ~48 bijwerken als hij de oude vlagnaam noemt.

3. `schrijver.py`: `Uitvoer.csv: Path | None` (commentaar: "`None` als de CSV niet gevraagd is (`--uitvoer` zonder `csv`)"). `schrijf_uitvoer(..., *, met_csv: bool = True, met_geopackage: bool = True, met_json: bool = True, ...)`; geef `met_csv=met_csv` door aan `write_check_report`. Idem `schrijf_uitvoer_gebieden` (beide aanroepen van `schrijf_uitvoer` en de aanroep van `_schrijf_totaal`). `_schrijf_totaal(..., met_csv: bool, met_json: bool)`: `totaal_csv = schrijf_csv(...) if met_csv else None`. Moduledocstring: "vier vormen" → het rapport altijd, de andere drie naar keuze.

4. `bevindingen.py`, `write_check_report`: keyword `met_csv: bool = True`, retourtype `tuple[Path, Path | None]`; `csv_path = schrijf_csv(meldingen_tabel(meldingen), Path(output_dir) / FILE_CHECKS_CSV) if met_csv else None`. Docstring: een zin dat het rapport altijd komt en de CSV op verzoek.

Controleer met `grep -rn "geen_gpkg\|geen_json\|geen-gpkg\|geen-json" src/ tests/ README.md docs/json-schema.md` dat er buiten `docs/beslislog.md`, `docs/ronde1-*.md` en `docs/superpowers/` niets overblijft.

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_cli.py tests/test_toetsrun.py tests/test_toetsloop.py tests/test_uitvoer_herkomst.py tests/test_integration.py -q`, daarna `uv run pytest -q`. Een test die `uitvoer.csv.read_text(...)` doet zonder `met_csv=False` blijft werken; mypy kan bij zulke tests klagen dat `csv` `None` kan zijn -- `tests/` valt buiten mypy, dus dat is geen poortfout, maar meld het als het gebeurt.

- [ ] **Step 5: Documentatie**

1. `README.md`, regel 213-218: vervang de zinnen over `--geen-gpkg` en `--geen-json` door: "`toets` schrijft daarnaast een GeoPackage met de bevindingen op locatie en `bevindingen.json` met de volledige meldingenstroom. Met `--uitvoer csv|json|gpkg` (herhaalbaar; standaard alle drie) kies je welke van die drie bijproducten er komen; het Markdown-rapport wordt altijd geschreven, want het draagt de markering en het voorbehoud. Dat JSON-bestand is …" (rest van de alinea ongewijzigd).
2. `docs/json-schema.md`, regel 13: `Uitzetten kan met `--geen-json`, symmetrisch met `--geen-gpkg`.` → `Uitzetten kan door `json` weg te laten uit `--uitvoer` (`toets --uitvoer csv --uitvoer gpkg`).`
3. `CHANGELOG.md`, onder `### Gewijzigd`, als eerste regel:

```markdown
- **`toets --uitvoer csv|json|gpkg` vervangt `--geen-gpkg` en `--geen-json`** (issue #66).
  Eén bevestigende, herhaalbare optie zegt welke bijproducten er naast het Markdown-rapport
  komen; standaard alle drie, en ook de CSV is nu uit te zetten. Het rapport wordt altijd
  geschreven: het draagt de markering en het voorbehoud. De twee oude vlaggen vervallen
  zonder alias; wie ze opgeeft krijgt de gewone optiefout. `Toetsopdracht` krijgt `met_csv`
  en `Uitvoer.csv` kan `None` zijn.

```

- [ ] **Step 6: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`.

```bash
git add src/nlriochecker/cli.py src/nlriochecker/toetsrun.py src/nlriochecker/uitvoer/schrijver.py \
  src/nlriochecker/uitvoer/bevindingen.py tests/test_cli.py tests/test_toetsrun.py tests/test_toetsloop.py \
  README.md docs/json-schema.md CHANGELOG.md
git status --short
git commit -m "toets --uitvoer csv|json|gpkg vervangt --geen-gpkg en --geen-json; het rapport blijft altijd (issue #66)"
```
