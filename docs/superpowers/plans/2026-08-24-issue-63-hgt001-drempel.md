# Issue #63: HGT-001 waarschuwingsdrempel naar 10 cm, halfopen band — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HGT-001 meldt een AHN-afwijking vanaf **10 cm (inclusief)** in plaats van boven 5 cm; de band van HGT-001 wordt `[0,10 – 0,25)` en die van HGT-002 `[0,25 – ∞)`, vergeleken op millimeters afgerond, en het rapport noemt de gehanteerde drempel.

**Architecture:** De twee checks delen `_DekselAfwijking.run` in `src/nlriochecker/checks/extern.py`; de bandvergelijking zit alleen daar. De drempel staat op de drie configplekken uit het drempelrecept (`checkconfig.py`, `checks.toml`, `configs/dewoldenhoogeveen.toml`). Een nieuwe TTL-fixture `hgt001_grens.ttl` toetst de vier grensgevallen op het vlakke fixture-raster van 10,00 m NAP.

**Tech Stack:** Python 3.12, pytest, rasterio (bestaand). Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #63 (`gh issue list --json number,body --search 63`). De regisseur heeft één ruling toegevoegd, zie Global Constraints (afronding op millimeters).

## Global Constraints

- `ahn_afwijking_waarschuwing_m` gaat van `0.05` naar `0.10` op alle drie de plekken: `src/nlriochecker/checkconfig.py` (default), `src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml`. `ahn_afwijking_fout_m` blijft `0.25`.
- **Halfopen banden:** overslaan bij `afwijking < onder` en bij `boven is not None and afwijking >= boven`. HGT-001 dekt `[0,10 – 0,25)`, HGT-002 `[0,25 – ∞)`. Een object krijgt nooit beide meldingen.
- **Ruling van de regisseur — vergelijk op millimeters afgerond:** `afwijking = round(abs(geregistreerd - gemeten), 3)` vóór de vergelijking. Reden: `10.10 - 10.00` is in floating point `0.0999…`, dus zonder afronding zwijgt een put met precies 0,100 m afwijking en is de grenstest uit het issue ("0,100 m meldt") onhaalbaar. Bovendien is de afgeronde waarde precies wat de melding toont (`afwijking_m`), zodat band en getoond getal nooit tegenspreken. Gevolg op De Wolden: de 4 HGT-001-meldingen die op 0,250 afronden schuiven naar HGT-002. Verwacht daarom **HGT-001 = 2847 en HGT-002 = 2132** (gemeten op `uitvoer/volledig_24082026/bevindingen.json`), níét de 2851/2128 uit het issue. Dit staat in BO-44 en in de CHANGELOG.
- Titels: HGT-001 `"Deksel- of maaiveldhoogte wijkt af van AHN: 10 cm of meer"`, HGT-002 `"Deksel- of maaiveldhoogte wijkt af van AHN: 25 cm of meer"` (ook HGT-002 is nu inclusief).
- `notes()` van beide checks noemt de gehanteerde drempel(s) en de afronding.
- Gegenereerde bestanden nooit met de hand bewerken: `tests/fixtures/ttl/*.ttl` via `uv run python scripts/maak_ttl_fixtures.py`, `docs/dekkingsmatrix.md` via `uv run python scripts/dekkingsmatrix.py`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten; volg de stijl van `extern.py`. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden (`git add <pad> …`), nooit `git add -A`: er kunnen ongecommitte planbestanden van andere issues in de werkmap staan.
- Een nieuw BO-nummer: **BO-44** in `docs/beslislog.md`, direct na BO-43 (het bestand eindigt daar).
- CHANGELOG: een nieuwe kop `### Gewijzigd` onder `## [Unreleased]`, **boven** de bestaande `### Gerepareerd`.

---

### Task 1: Drempel, halfopen band op de millimeter, fixture, tests, config en documentatie

**Files:**
- Modify: `scripts/maak_ttl_fixtures.py:1690-1693` (put E van 0,08 naar 0,12 m) en na regel 1751 (nieuwe fixture `hgt001_grens.ttl`)
- Regenerate: `tests/fixtures/ttl/ext_scenario.ttl`, `tests/fixtures/ttl/hgt001_grens.ttl`
- Modify: `src/nlriochecker/checks/extern.py:943-1008` (`_DekselAfwijking.run` en `.notes`), `:1067`, `:1079` (titels)
- Modify: `src/nlriochecker/checkconfig.py:191`, `src/nlriochecker/checks.toml:264-267`, `configs/dewoldenhoogeveen.toml:266-269`
- Modify: `tests/test_checks_extern.py` (titelassertie regel 359-360, twee nieuwe tests), `tests/test_integration.py:313-315`
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md:99-100`, regenerate `docs/dekkingsmatrix.md`
- Modify: `docs/beslislog.md` (BO-44), `CHANGELOG.md`

**Interfaces:**
- Consumes: `hoogteput(naam, label, punt, mv=, dek=, mv_wijze=, dek_wijze=)` uit `scripts/maak_ttl_fixtures.py`; `uitkomst(check_id, config, bronnen, bestand)` en `labels(outcome)` uit `tests/test_checks_extern.py`; `context.config.drempels.<naam>`.
- Produces: geen nieuwe publieke namen. `Finding.details["afwijking_m"]` is voortaan de op mm afgeronde waarde waarmee ook vergeleken is (was: aparte `round()` bij het melden).

- [ ] **Step 1: Fixtures (generator, niet de bestanden)**

In `scripts/maak_ttl_fixtures.py`, in `FIXTURES["ext_scenario.ttl"]`, vervang de regels

```python
    # Put E heeft geen putdekselniveau, net als elke put in De Wolden en Hoogeveen. De hoogtechecks
    # vallen dan terug op de maaiveldhoogte, en die komt hier uit AHN2. Zijn afwijking
    # is 0,08 m, dus hij komt in HGT-001 terecht.
    + hoogteput("PutE", "E", EXT_E, mv=10.08, dek=None, mv_wijze="AHN2")
```

door

```python
    # Put E heeft geen putdekselniveau, net als elke put in De Wolden en Hoogeveen. De hoogtechecks
    # vallen dan terug op de maaiveldhoogte, en die komt hier uit AHN2. Zijn afwijking
    # is 0,12 m, dus hij komt in HGT-001 terecht (vanaf 0,10 m, issue #63).
    + hoogteput("PutE", "E", EXT_E, mv=10.12, dek=None, mv_wijze="AHN2")
```

Direct ná het afsluitende `)` van `FIXTURES["ext_scenario.ttl"]` (regel 1751) en vóór het commentaar `# Geen check maar de klassenselecties uit checks/selectie.py` voeg je toe:

```python


# De vier grensgevallen van issue #63 op het vlakke raster van 10,00 m NAP uit
# tests/fixtures/gis/ext: 0,099 m zwijgt, 0,100 m is HGT-001 (ondergrens inclusief),
# 0,249 m blijft HGT-001 en 0,251 m is HGT-002. Geen putdeksel, zoals in De Wolden en
# Hoogeveen; de maaiveldhoogte is dan het getoetste kenmerk. De afwijking wordt op
# millimeters afgerond vergeleken, anders is 10,10 - 10,00 in floating point 0,0999.
FIXTURES["hgt001_grens.ttl"] = (
    "de halfopen banden van HGT-001 en HGT-002, op de millimeter (issue #63)",
    hoogteput("Grens099", "099", (1000.0, 1990.0), mv=10.099, dek=None)
    + hoogteput("Grens100", "100", (1010.0, 1990.0), mv=10.100, dek=None)
    + hoogteput("Grens249", "249", (1020.0, 1990.0), mv=10.249, dek=None)
    + hoogteput("Grens251", "251", (1030.0, 1990.0), mv=10.251, dek=None),
)
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. Controleer met `git status --short` dat alleen `tests/fixtures/ttl/ext_scenario.ttl` gewijzigd is en `tests/fixtures/ttl/hgt001_grens.ttl` nieuw is; andere fixtures mogen niet veranderen. De vier punten liggen binnen het studiegebied van de fixtures, (980, 1980)–(1120, 2020), en niet op de nodata-vlek rond (1040, 2010); ligt een put toch buiten het raster, dan zie je dat in Step 5 aan een nodata-notitie (vergelijk `test_nodata_cellen_worden_gemeld`).

- [ ] **Step 2: Schrijf de falende tests**

In `tests/test_checks_extern.py`:

1. Na `SCENARIO = TTL_DIR / "ext_scenario.ttl"` toevoegen: `GRENS = TTL_DIR / "hgt001_grens.ttl"`.
2. In `test_hgt001_en_hgt002_claimen_geen_dekselhoogte` de twee asserties vervangen door:

```python
    assert REGISTRY["HGT-001"].title == "Deksel- of maaiveldhoogte wijkt af van AHN: 10 cm of meer"
    assert REGISTRY["HGT-002"].title == "Deksel- of maaiveldhoogte wijkt af van AHN: 25 cm of meer"
```

3. Direct na die test twee nieuwe tests:

```python
def test_hgt001_en_hgt002_delen_een_halfopen_band_op_de_millimeter(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """0,099 m zwijgt, 0,100 m meldt (ondergrens inclusief), 0,249 m blijft HGT-001
    en 0,251 m is HGT-002; geen enkele put krijgt beide meldingen.

    De put met 10,100 m op een raster van 10,000 m bewijst de afronding op
    millimeters: onafgerond is dat verschil 0,0999 en zou de put zwijgen.
    """
    licht = uitkomst("HGT-001", config, bronnen, GRENS)
    fors = uitkomst("HGT-002", config, bronnen, GRENS)

    assert labels(licht) == ["100", "249"]
    assert labels(fors) == ["251"]
    per_label = {f.object_label: f.details["afwijking_m"] for f in licht.findings + fors.findings}
    assert per_label == {"100": 0.1, "249": 0.249, "251": 0.251}


def test_hgt001_en_hgt002_noemen_de_gehanteerde_drempel(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Zonder deze regel leest een gehalveerde telling als 'de data is beter geworden'."""
    licht = uitkomst("HGT-001", config, bronnen, GRENS)
    fors = uitkomst("HGT-002", config, bronnen, GRENS)

    assert any(
        "vanaf een afwijking van 0.10 m" in note and "tot 0.25 m" in note for note in licht.notes
    )
    assert any("vanaf een afwijking van 0.25 m" in note for note in fors.notes)
    assert any("millimeter" in note for note in licht.notes)
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checks_extern.py -k "hgt001 or hgt002" -v`
Expected: FAIL op de titelassertie (oude titel), op de bandtest (met de oude drempel 0,05 meldt HGT-001 ook "099", en `100` valt door de floating-point-rest mogelijk om) en op de drempelnotitie (bestaat nog niet). `test_ttl_fixtures.py` slaagt al na Step 1.

- [ ] **Step 4: Implementeer**

1. `src/nlriochecker/checkconfig.py:191`: `Field(default=0.05, gt=0.0)` → `Field(default=0.10, gt=0.0)`.

2. `src/nlriochecker/checks.toml:264-267` — vervang het blok door:

```toml
# HGT-001 en HGT-002: afwijking van het maaiveld ten opzichte van het AHN. Waarschuwing
# vanaf 10 cm en fout vanaf 25 cm, beide inclusief: HGT-001 dekt [0,10 - 0,25) en
# HGT-002 [0,25 - oneindig), vergeleken op millimeters afgerond. Het checkregister v0.9
# zegt "meer dan 5 cm"; 5 cm ligt binnen de onzekerheid van de AHN-inwinning zelf. De
# afwijking is vastgelegd in BO-44.
ahn_afwijking_waarschuwing_m = 0.10
ahn_afwijking_fout_m = 0.25
```

3. `configs/dewoldenhoogeveen.toml:266-269` — hetzelfde blok, letterlijk dezelfde tekst.

4. `src/nlriochecker/checks/extern.py`, in `_DekselAfwijking.run`: vervang

```python
            afwijking = abs(geregistreerd - gemeten)
            if afwijking <= onder:
                continue
            if boven is not None and afwijking > boven:
                continue
```

door

```python
            # Op millimeters afgerond, en dan een halfopen band [onder, boven): een
            # verschil van precies 0,100 m is in floating point 0,0999... en zou anders
            # onder de drempel doorglippen, en een object krijgt nooit beide meldingen.
            # De afgeronde waarde is ook wat de melding toont (BO-44).
            afwijking = round(abs(geregistreerd - gemeten), 3)
            if afwijking < onder:
                continue
            if boven is not None and afwijking >= boven:
                continue
```

en in de `yield self.finding(...)`-aanroep `afwijking_m=round(afwijking, 3),` → `afwijking_m=afwijking,`. Vul de docstring van `run` aan met een derde alinea:

```
        De band is halfopen en wordt op millimeters afgerond vergeleken: HGT-001
        meldt vanaf de waarschuwingsdrempel tot (niet tot en met) de foutdrempel,
        HGT-002 vanaf de foutdrempel. Zie BO-44.
```

5. In `_DekselAfwijking.notes`, direct ná de regel `            return notities` van de guard `if context.bronnen is None or self.raster(context) is None:` en vóór `vergeleken = [...]`, toevoegen:

```python
        onder = getattr(context.config.drempels, self.ondergrens)
        boven = getattr(context.config.drempels, self.bovengrens) if self.bovengrens else None
        bereik = (
            f"vanaf een afwijking van {onder:.2f} m tot {boven:.2f} m (daarboven meldt HGT-002)"
            if boven is not None
            else f"vanaf een afwijking van {onder:.2f} m"
        )
        notities.append(
            f"Gemeld {bereik}; de afwijking is op millimeters afgerond voordat hij met de "
            "drempel vergeleken is."
        )
```

6. Titels: regel 1067 → `"Deksel- of maaiveldhoogte wijkt af van AHN: 10 cm of meer"`, regel 1079 → `"Deksel- of maaiveldhoogte wijkt af van AHN: 25 cm of meer"`. Docstrings van de twee klassen: `"""HGT-001: de deksel- of maaiveldhoogte wijkt de lichte drempel of meer af."""` en `"""HGT-002: de deksel- of maaiveldhoogte wijkt de zware drempel of meer af."""`.

- [ ] **Step 5: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_checks_extern.py tests/test_ttl_fixtures.py tests/test_checkconfig.py -q`
Expected: alles PASS. `test_defect_wordt_gevonden[HGT-001-...]` blijft `["B", "E"]` (B staat op precies 0,10 en E nu op 0,12).

Daarna de Koekangerveld-integratietest, die op de echte data draait (`data/` staat lokaal; koud laden duurt ca. een halve minuut):

Run: `uv run pytest tests/test_integration.py::test_ext_checks_op_koekangerveld -q`
Expected: FAIL op `assert len(per_check["HGT-001"].findings) == 15` — dat getal hoort bij de oude drempel. **Meet het nieuwe getal, gok het niet:** lees het uit de assertiefout (`assert N == 15`), en controleer het onafhankelijk met dit scratch-script (niet committen):

```bash
uv run python - <<'EOF'
import sys; sys.path.insert(0, "tests")
from test_integration import OROX_DEWOLDENHOOGEVEEN, ONTOLOGIE_TOTAAL, _koekangerveld_bronnen
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.dataset import load_dataset
dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
context = CheckContext(dataset=dataset, config=load_check_config(), bronnen=_koekangerveld_bronnen())
run = run_checks(context, ["HGT-001", "HGT-002"])
for o in run.outcomes:
    a = sorted(f.details["afwijking_m"] for f in o.findings)
    print(o.check_id, len(o.findings), a)
EOF
```

Verwacht: HGT-002 blijft 0 (geen enkele put in Koekangerveld wijkt 25 cm of meer af) en HGT-001 is het aantal van de oude 15 met een afgeronde afwijking ≥ 0,10. Zet dat getal in `tests/test_integration.py:315` en werk het commentaar op regel 313 bij: `# Geen enkele put wijkt 25 cm of meer van het AHN5 af, N wel 10 cm of meer (issue #63).` Draai de test opnieuw: PASS.

Daarna de hele suite: `uv run pytest -q`. Valt een test in een ander bestand op de nieuwe titel of drempel, werk de verwachting bij met een regel commentaar waarom en verklaar dat in je rapport. Een test die om een andere reden faalt is een bug in je wijziging.

- [ ] **Step 6: Documentatie**

1. `data/checkregister-gwsw-nulmeting-v0_9.md`, regel 99-100: vervang `meer dan 5 cm` door `10 cm of meer (v0.9 zei "meer dan 5 cm"; afwijking in BO-44)` en op regel 100 `meer dan 25 cm` door `25 cm of meer`. Raak de rest van de twee regels niet aan.
2. Regenereer: `uv run python scripts/dekkingsmatrix.py`. Controleer met `git diff docs/dekkingsmatrix.md` dat alleen de regels HGT-001 en HGT-002 veranderen.
3. `docs/beslislog.md`, ná BO-43 (aan het einde van het bestand) een nieuw besluit:

```markdown

### BO-44 HGT-001 waarschuwt vanaf 10 cm AHN-afwijking (inclusief); de banden zijn halfopen en op de millimeter

**Wat.** `ahn_afwijking_waarschuwing_m` gaat van 0,05 naar 0,10 m; `ahn_afwijking_fout_m` blijft
0,25 m. De vergelijking wordt halfopen: HGT-001 meldt `[0,10 – 0,25)`, HGT-002 `[0,25 – ∞)`, zodat
een object nooit beide meldingen krijgt. De afwijking wordt op millimeters afgerond voordat hij
met de drempels vergeleken wordt; dat afgeronde getal is ook wat de melding toont
(`afwijking_m`). Beide checks noemen de gehanteerde drempel in hun toelichting. Uitgewerkt in
issue #63.

**Waarom.** Het checkregister v0.9 zegt "meer dan 5 cm", maar 5 cm ligt binnen de onzekerheid van
de AHN-inwinning zelf: een afwijking van die orde zegt niets over de beheerdata, daar staat
meetruis naast meetruis. Gemeten op de volledige run van 2026-08-24 lag de mediane HGT-001-afwijking
op 0,098 m; de nieuwe drempel ligt dus vrijwel op de mediaan en de helft van de 5811 waarschuwingen
valt weg. De afronding op millimeters is geen cosmetiek: `10,10 − 10,00` is in floating point
`0,0999…`, en zonder afronding zou een put met precies 0,100 m afwijking onder de inclusieve
ondergrens doorglippen terwijl de melding "0,100 m" zou tonen.

**Afwijking van het checkregister.** Dit is een bewuste afwijking van de registertekst; de
registerregels van HGT-001 en HGT-002 zijn bijgewerkt en verwijzen hierheen.

**Openstaand punt voor de auteur.** Draagt deze drempel een externe onderbouwing — een specificatie
die de systematische en stochastische fout van het AHN kwantificeert — of is het een projectkeuze
zonder externe bron? Hier is niets ingevuld en geen specificatiegetal verzonnen; `checks.toml`
gebruikt bij andere drempels de formulering "projectkeuze, geen externe bron".

**Alternatieven.** Alleen de ondergrens inclusief maken (verworpen: een object met precies 0,25 m
krijgt dan HGT-001 én HGT-002). Onafgerond vergelijken (verworpen: de grenstest "0,100 m meldt" is
dan onhaalbaar en band en getoond getal kunnen tegenspreken). Een lichtere categorie voor 5–10 cm
(verworpen: die afwijkingen zeggen niets, dus ze horen niet in de uitvoer).
```

4. `CHANGELOG.md`, onder `## [Unreleased]`, **boven** `### Gerepareerd`, een nieuwe sectie:

```markdown
### Gewijzigd

- **HGT-001 waarschuwt vanaf 10 cm AHN-afwijking, inclusief** (issue #63). De
  waarschuwingsdrempel `ahn_afwijking_waarschuwing_m` gaat van 0,05 naar 0,10 m, omdat
  5 cm binnen de onzekerheid van de AHN-inwinning zelf ligt. De banden zijn halfopen en
  worden op millimeters afgerond vergeleken: HGT-001 meldt `[0,10 – 0,25)`, HGT-002
  `[0,25 – ∞)`; een object krijgt nooit beide meldingen en de toelichting noemt de
  gehanteerde drempel. Op De Wolden: HGT-001 5811 → 2847 en HGT-002 2128 → 2132 (vier
  meldingen die op 0,250 m afronden schuiven van W naar F). Zie BO-44.

```

(De getallen in die regel zijn de verwachting uit de baseline-JSON; Task 2 meet ze en corrigeert ze als ze afwijken.)

- [ ] **Step 7: Mechanische poort**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen. Faalt `ruff format --check`, draai `uv run ruff format` en herhaal.

- [ ] **Step 8: Commit**

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/ext_scenario.ttl tests/fixtures/ttl/hgt001_grens.ttl \
  src/nlriochecker/checks/extern.py src/nlriochecker/checkconfig.py src/nlriochecker/checks.toml \
  configs/dewoldenhoogeveen.toml tests/test_checks_extern.py tests/test_integration.py \
  data/checkregister-gwsw-nulmeting-v0_9.md docs/dekkingsmatrix.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "HGT-001: waarschuw vanaf 10 cm AHN-afwijking, halfopen banden op de millimeter (issue #63)"
```

Staan er na `git status --short` nog gewijzigde testbestanden buiten deze lijst (verwachtingen uit Step 5), voeg die toe vóór de commit. Voeg géén planbestanden (`docs/superpowers/plans/*`) of `uitvoer/` toe.

---

### Task 2: Effect op De Wolden meten en vastleggen

**Files:**
- Read: `uitvoer/volledig_24082026/bevindingen.csv` (baseline 0.3.0)
- Create (niet committen; `uitvoer/` is git-ignored): `uitvoer/issue63/`
- Modify: `docs/beslislog.md` (BO-44: alinea "Gemeten uitkomst"), `CHANGELOG.md` (getallen corrigeren als ze afwijken)

- [ ] **Step 1: Draai de volledige toets**

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --projectconfig configs/dewoldenhoogeveen.toml \
  --bronnen data/gis_dewoldenhoogeveen \
  --geen-json \
  --output uitvoer/issue63
```

Expected: eindigt met `Geschreven: uitvoer/issue63/dq_dewoldenhoogeveen_orox_<datum>.gpkg`; duurt ca. 2-3 minuten.

- [ ] **Step 2: Vergelijk**

```bash
uv run python - <<'EOF'
import pandas as pd, re
runs = {"baseline": "uitvoer/volledig_24082026/bevindingen.csv", "na #63": "uitvoer/issue63/bevindingen.csv"}
for naam, pad in runs.items():
    frame = pd.read_csv(pad, sep=";")
    for check in ["HGT-001", "HGT-002"]:
        deel = frame[frame.Check == check]
        afw = deel.Boodschap.str.extract(r"wijkt ([0-9.]+) m af")[0].astype(float)
        print(f"{check} {naam}: {len(deel)} meldingen; min {afw.min():.3f}, max {afw.max():.3f}; "
              f"op 0.100: {(afw == 0.100).sum()}, op 0.250: {(afw == 0.250).sum()}")
EOF
grep -n "Gemeld vanaf een afwijking" uitvoer/issue63/bevindingen.md | head -2
```

Lees eerst de kolomnamen als `Check`/`Boodschap` niet kloppen (`head -1 uitvoer/issue63/bevindingen.csv`). Verwacht: HGT-001 baseline 5811 → **2847**, min 0,100 en max 0,249; HGT-002 2128 → **2132**, min 0,250. Wijkt het af, meld het getal en de richting en wat je in de data ziet; redeneer het niet weg. Controleer ook dat geen enkel object in beide checks staat: `ObjectURI` van HGT-001 en HGT-002 disjunct.

- [ ] **Step 3: Leg vast en commit**

Voeg aan BO-44 in `docs/beslislog.md` een slotalinea toe, met de gemeten getallen:

```markdown

**Gemeten uitkomst (2026-08-24).** Volledige toets op De Wolden na de wijziging: HGT-001 5811 →
<N1> meldingen (kleinste afwijking <min1> m, grootste <max1> m), HGT-002 2128 → <N2> (kleinste
<min2> m). Geen enkel object staat in beide checks. De <K> meldingen die op 0,250 m afronden staan nu
in HGT-002; die op 0,100 m afronden (<M>) staan in HGT-001.
```

Corrigeer de getallen in de CHANGELOG-regel van Task 1 als ze afwijken. Dan:

```bash
git add docs/beslislog.md CHANGELOG.md
git commit -m "BO-44: gemeten uitkomst van de nieuwe HGT-001-drempel op De Wolden (issue #63)"
```

Zet de vergelijkingstabel en de drempelnotitie uit het rapport in het rapportbestand van deze taak.
