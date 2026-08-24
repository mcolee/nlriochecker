# Issue #58: BGT-historiefilter — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elke ingelezen BGT-laag houdt na het lezen alleen de actuele objectversie over (`eind_registratie` én `termination_date` leeg), met een telling per laag in de bronnotities.

**Architecture:** Eén filter op één plek: `_lees_laag` in `src/nlriochecker/externedata.py`, direct na `gpd.read_file` en de CRS-bewaking. Het filter werkt alleen als de historievelden aanwezig zijn; een laag zonder die velden (fixtures, studiegebied, waterschapsbestand) gaat ongewijzigd door. De telling gaat via de bestaande `notities`-lijst die `load_external_data` in `ExternalData.notes` zet en die het rapport onder *Externe bronnen* afdrukt.

**Tech Stack:** Python 3.12, geopandas/pyogrio (bestaand), pytest. Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #58 (`gh issue list --json number,body --search 58`); besluit BO-43 in `docs/beslislog.md` (regel 2303 e.v.).

## Global Constraints

- Filterregel: houd rijen met `eind_registratie` leeg **en** `termination_date` leeg (`isna()`); filter op de velden die aanwezig zijn; geen van beide aanwezig → geen filter.
- Altijd aan, geen config- of CLI-schakelaar.
- Notitie per gefilterde laag, via de bestaande `notities`-lijst; nooit een eigen schrijver (harde regel "Eén uitvoerschrijver").
- Gemeten op `data/gis_dewoldenhoogeveen/BGT.gpkg` laag `waterdeel`: 97.148 rijen, 44.601 actueel (de 44.601 hebben beide velden leeg). Kolomtypen na `gpd.read_file`: `datetime64[ms, UTC]`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten, Engelse identifiers waar de module dat al doet (deze module gebruikt Nederlandse lokale namen; volg de bestaande stijl van `externedata.py`).
- Werk op branch `dev`. Geen `gh issue create`. Geen wijziging aan `tests/fixtures/gis/ext/*` (de fixtures dragen geen historievelden en dat blijft zo).
- CHANGELOG-regel onder `## [Unreleased]`, kop `### Gerepareerd`.

---

### Task 1: Actualiteitsfilter in `_lees_laag`

**Files:**
- Modify: `src/nlriochecker/externedata.py:439-470` (`_lees_laag`)
- Create: `tests/test_externedata_historie.py`
- Modify: `CHANGELOG.md` (sectie `## [Unreleased]`, direct onder de kop op regel 13)

**Interfaces:**
- Consumes: `_lees_laag(pad: Path, laag: str, notities: list[str])` (bestaand; geeft `(rijen, crs_naam, herprojectie)` terug).
- Produces: dezelfde signatuur en teruggave; het `rijen`-resultaat bevat alleen actuele features; `notities` krijgt één regel per laag met historievelden, van de vorm ``"`BGT.gpkg` laag 'waterdeel': 2 verlopen objectversies overgeslagen (eind_registratie of termination_date gevuld); 1 actuele feature gelezen."``. Wees exact: het rapport en de tests lezen deze tekst.

- [ ] **Step 1: Schrijf de falende test**

Maak `tests/test_externedata_historie.py`:

```python
"""Tests voor het actualiteitsfilter op de BGT-lagen (issue #58).

Elk BGT-object draagt zijn registratiegeschiedenis mee: de levende versie heeft
`eind_registratie` leeg, elke afgesloten oudere versie heeft die kolom gevuld. Zonder
filter draaien de ruimtelijke toetsen over de hele stapel versies; op De Wolden is
meer dan de helft van de waterdelen oude historie.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from shapely.geometry import box

from gpkghelper import schrijf_vlakken
from nlriochecker.checkconfig import load_check_config
from nlriochecker.externedata import load_external_data


def _bgt_met_historie(map_pad: Path) -> Path:
    """Een BGT-achtig bestand: een waterdeellaag met historie en een pandlaag zonder."""
    import geopandas as gpd

    map_pad.mkdir(parents=True, exist_ok=True)
    pad = map_pad / "bgt.gpkg"
    water = gpd.GeoDataFrame(
        {
            "lokaal_id": ["actueel", "verlopen", "beeindigd"],
            "eind_registratie": [pd.NaT, pd.Timestamp("2020-01-01"), pd.NaT],
            "termination_date": [pd.NaT, pd.NaT, pd.Timestamp("2021-06-01")],
        },
        geometry=[box(10, 10, 20, 20), box(30, 30, 40, 40), box(50, 50, 60, 60)],
        crs="EPSG:28992",
    )
    water.to_file(pad, layer="waterdeel", driver="GPKG")
    schrijf_vlakken(pad, "pand", [({"lokaal_id": "p1"}, box(70, 70, 80, 80))])
    return pad


def _bronnen():
    return load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": None,
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
            "bgt_waterlagen": ["waterdeel"],
            "bgt_putdeksellagen": [],
            "bgt_overige_bouwwerklagen": [],
        }
    )


def test_verlopen_versies_vallen_af_en_worden_geteld(tmp_path: Path) -> None:
    _bgt_met_historie(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    water = data.layer("bgt_water")
    assert water is not None
    assert [rij["lokaal_id"] for rij in water.attributes] == ["actueel"]
    assert (
        "`bgt.gpkg` laag 'waterdeel': 2 verlopen objectversies overgeslagen "
        "(eind_registratie of termination_date gevuld); 1 actuele feature gelezen."
    ) in data.notes


def test_laag_zonder_historievelden_gaat_ongefilterd_door(tmp_path: Path) -> None:
    _bgt_met_historie(tmp_path / "b")

    data = load_external_data(_bronnen(), tmp_path / "b")

    pand = data.layer("bgt_pand")
    assert pand is not None
    assert len(pand) == 1
    assert not any("laag 'pand'" in notitie for notitie in data.notes)
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_externedata_historie.py -v`
Expected: `test_verlopen_versies_vallen_af_en_worden_geteld` FAILS op de eerste assert (lijst bevat `["actueel", "verlopen", "beeindigd"]`); de tweede test slaagt al (dat is goed: hij bewaakt dat het filter niets raakt wat geen historie draagt).

- [ ] **Step 3: Bouw het filter in `_lees_laag`**

In `src/nlriochecker/externedata.py`, in `_lees_laag`, direct ná het herprojectieblok (dat eindigt op de regel `)` na `f"EPSG:{RD_NEW}" geherprojecteerd."`) en vóór `kolommen = [...]`:

```python
    frame = _alleen_actueel(frame, pad, laag, notities)
```

en voeg onder `_lees_laag` deze functie toe:

```python
HISTORIEVELDEN = ("eind_registratie", "termination_date")


def _alleen_actueel(frame, pad: Path, laag: str, notities: list[str]):
    """Houdt van een BGT-laag alleen de actuele objectversies over.

    Elk BGT-object draagt zijn registratiegeschiedenis mee: de levende versie heeft
    `eind_registratie` leeg, elke afgesloten oudere versie heeft die kolom gevuld;
    `termination_date` houdt daarnaast een officieel beëindigd object buiten. Zonder
    dit filter draaien alle ruimtelijke toetsen over de hele stapel versies -- op De
    Wolden is meer dan de helft van de waterdelen oude historie (issue #58, BO-43).

    Alleen de aanwezige historievelden tellen; een laag zonder die velden (een los
    studiegebied, een waterschapsbestand) gaat ongewijzigd door. Wat afvalt komt als
    notitie in het rapport: stilte zou lezen als "alles meegenomen".
    """
    aanwezig = [veld for veld in HISTORIEVELDEN if veld in frame.columns]
    if not aanwezig:
        return frame
    actueel = frame[aanwezig].isna().all(axis=1)
    verlopen = int((~actueel).sum())
    frame = frame[actueel]
    notities.append(
        f"`{pad.name}` laag {laag!r}: {verlopen} verlopen objectversies overgeslagen "
        f"({' of '.join(HISTORIEVELDEN)} gevuld); "
        f"{getal(len(frame), 'actuele feature', 'actuele features')} gelezen."
    )
    return frame
```

`getal` komt uit `nlriochecker.taal` (bestaat al: `getal(aantal, enkelvoud, meervoud)` levert bv. `"1 actuele feature"` / `"3 actuele features"`); voeg bovenaan de module toe: `from nlriochecker.taal import getal`. Controleer met `uv run python -c "from nlriochecker.taal import getal; print(getal(1,'actuele feature','actuele features'), getal(3,'actuele feature','actuele features'))"` dat de uitvoer `1 actuele feature 3 actuele features` is; is de signatuur anders, pas de aanroep aan en niet de verwachte tekst in de test.

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_externedata_historie.py tests/test_externedata_dekking.py tests/test_checks_extern.py -v`
Expected: alles PASS. De bestaande fixtures onder `tests/fixtures/gis/ext` dragen geen historievelden, dus `test_checks_extern.py` verandert niet.

- [ ] **Step 5: CHANGELOG**

Onder `## [Unreleased]` in `CHANGELOG.md` (nu leeg) toevoegen:

```markdown
### Gerepareerd

- **BGT-lagen worden op de actuele objectversie gefilterd** (issue #58). Elke ingelezen
  BGT-laag houdt alleen de rijen met `eind_registratie` én `termination_date` leeg
  over; verlopen versies telden tot nu toe in elke ruimtelijke toets mee (op De Wolden
  97.148 waterdelen waarvan 44.601 actueel). Het filter werkt alleen op lagen die de
  historievelden dragen en meldt per laag hoeveel rijen vervielen onder *Externe
  bronnen* in het rapport. Zie BO-43.
```

- [ ] **Step 6: Mechanische poort**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen. Faalt `ruff format --check`, draai `uv run ruff format` en herhaal.

- [ ] **Step 7: Commit**

```bash
git add src/nlriochecker/externedata.py tests/test_externedata_historie.py CHANGELOG.md
git commit -m "Filter BGT-lagen op de actuele objectversie (issue #58)"
```

---

### Task 2: Effect op De Wolden meten (geen code)

**Files:**
- Read: `uitvoer/volledig_24082026/bevindingen.csv` en `bevindingen.md` (de baseline, gedraaid met 0.3.0 vóór dit filter)
- Create (niet committen; `uitvoer/` is git-ignored): `uitvoer/issue58/`

**Interfaces:**
- Consumes: de code uit Task 1 op `dev`.
- Produces: een deltatabel per check in het rapportbestand van deze taak.

- [ ] **Step 1: Draai de volledige toets**

Run (duurt ca. 2 minuten; ~2 GB geheugen):

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --projectconfig configs/dewoldenhoogeveen.toml \
  --bronnen data/gis_dewoldenhoogeveen \
  --geen-gpkg --geen-json \
  --output uitvoer/issue58
```

Expected: eindigt met `Geschreven: uitvoer/issue58/bevindingen.csv`.

- [ ] **Step 2: Vergelijk met de baseline**

```bash
uv run python - <<'EOF'
import pandas as pd
oud = pd.read_csv("uitvoer/volledig_24082026/bevindingen.csv", sep=";")
nieuw = pd.read_csv("uitvoer/issue58/bevindingen.csv", sep=";")
checks = ["EXT-001", "EXT-002", "EXT-003", "EXT-005", "EXT-006", "EXT-007"]
for check in checks:
    a, b = oud[oud.Check == check], nieuw[nieuw.Check == check]
    print(f"{check}: {len(a)} -> {len(b)} meldingen; unieke Object2URI {a.Object2URI.nunique()} -> {b.Object2URI.nunique()}")
EOF
grep -n "bgt_water\|bgt_pand\|bgt_bouwwerk\|verlopen objectversies" uitvoer/issue58/bevindingen.md | head -20
```

Expected volgens het issue: `bgt_water` in de brontabel van het rapport 97148 → 44601; EXT-003 unieke `Object2URI` 638 → 580 (de 58 verlopen waterdelen verdwijnen). Wijkt een getal af, rapporteer het getal én wat je in de data ziet; redeneer het niet weg.

- [ ] **Step 3: Rapporteer**

Schrijf de deltatabel (per check: meldingen oud → nieuw, unieke Object2URI oud → nieuw) en de drie brontelling-regels uit het rapport in het rapportbestand van deze taak. Geen commit.
