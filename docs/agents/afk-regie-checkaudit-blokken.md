# AFK-regie: checkaudit-blokken A–G (issues #81–#101, deelset)

Invulling van het sjabloon `afk-regie.md` — lees dat eerst; alles daar geldt, met de
blokdelta's hieronder. Geef dit aan een **verse (gecleared) Fable-sessie** in
`/home/martin/nlriochecker`; Fable regisseert, **Opus-subagents** (`model: opus`)
implementeren en reviewen. Unattended.

**Buiten deze run**: blok H (#80, het richtingscluster), blok I (#97, #102 — native
geblokkeerd door #80) en de slotrun. Die doet de auteur in aparte, bijgewoonde sessies.

## Blokdelta's op het sjabloon

De eenheid is een **blok** (zie `docs/superpowers/plans/2026-08-28-checkaudit-blokken.md`),
niet één issue. Per blok:

1. **Binnen het blok strikt sequentieel** in de volgorde hieronder (blokgenoten delen
   bestanden). Per issue: de lus uit het sjabloon t/m stap 4 (implementer, groene geplakte
   poort, commit op `dev`).
2. **Eén review per blok** (sjabloon stap 5), na het laatste issue, op het zwaarste niveau
   in het blok; fixes als extra commit.
3. **Eén hermeting per blok**: alle richtgetallen van het blok in één meting; door de echte
   pijplijn (`docs/agents/analyse-harness.md`).
4. **Eén push + CI-watch per blok** (sjabloon stap 7: `runnerpoort.py`, push,
   `gh run watch --exit-status`).
5. **Dan pas comments + closes** van alle blokissues (sjabloon stap 8), elk met het gemeten
   getal naast de voorspelling.
6. Nieuwe Harde regel (28-08): **functionaliteit mag `gwsw-orox-helpers` niet breken** —
   alleen de publieke API, geen patches op internals (`CLAUDE.md`, Techniek).

## Volgorde en richtgetallen (De Wolden, baseline `uitvoer/audit_27082026`)

### Blok A — schrapronde (review: Klein)

| Issue | Wat | Richtgetal |
|---|---|---|
| #81 | ADM-011 vervalt | ADM-011-post weg; ADM-010 blijft gelijk aan de baseline |
| #90 | ATTR-008 vervalt (nulmeting dekt) | ATTR-008-post (443) weg; sentinel in de dekkingsmatrix |
| #95 | BTR-002, BTR-005, EXT-005, EXT-006 vervallen | vier "bekeken 0"-regels weg; nul meldingen verschuiven |

### Blok B — extern.py (review: Substantieel, wegens #94)

| Issue | Wat | Richtgetal |
|---|---|---|
| #83 | EXT-002 vervalt, EXT-003 blijft | EXT-003 = 281; waterdeel-vlakken blijven in de GeoPackage |
| #94 | EXT-007 alleen aan-water-klassen (GWSW-conform) | 71 → ~39 |
| #99 | `bob_maximale_diepte_m` 3,0 → 4,0 m | HGT-003-dieptemeldingen 1.042 → ~123 |

### Blok C — topologie-scope en -drempels (review: Substantieel; volgorde #82 → #100)

| Issue | Wat | Richtgetal |
|---|---|---|
| #82 | scope TOP-006/010/011: vrijverval × (vrijverval + duiker) | TOP-006 81 → 39, TOP-010 2.184 → 1.359, TOP-011 1.872 → 1.161, en lager met de aansluitleidingen eruit |
| #100 | TOP-006 naar 0,02 m/2,0 m; TOP-010-marge blijft 0,0 | TOP-006 → ~13 (ná #82) |

### Blok D — topologie-structuur (review: Substantieel; volgorde #85 → #89 → #88)

| Issue | Wat | Richtgetal |
|---|---|---|
| #85 | c*-deduplicatie vóór de topologiechecks | TOP-001 102 → ~9, TOP-005 112 → ~20, TOP-021 5 → ~3 |
| #89 | TOP-002/003: hulpstuk met telbare functie = geldig eind | TOP-002 56 → ~11, TOP-003 109 → ~2 |
| #88 | TOP-019-herleiding ook via hulpstukken | onbekend (nu structureel 0); meet en rapporteer |

### Blok E — teksten en declaraties (review: Substantieel, wegens #84)

| Issue | Wat | Richtgetal |
|---|---|---|
| #84 | teksten HGT-008/ATTR-003 + RVZ-001-tekst én -index | HGT-008/ATTR-003 gelijk; RVZ-001 kan stijgen — meet en verklaar |
| #92 | ATTR-016 twee boodschapvarianten | 88 totaal, ±67 "niet geregistreerd" / ±21 tegenspraak |
| #93 | NET-001/002-teksten met stelseltype + eindpuntrol | aantallen gelijk |
| #96 | declaratie EXT-003, rapportregels RVZ-011/ADM-007, BO-34 | drifttests groen; geen getalswijziging |

### Blok F — uitvoer en contracten (review: Altijd Substantieel)

| Issue | Wat | Richtgetal |
|---|---|---|
| #91 | ATTR-018-aandeel prominent in de rapportkop | aantallen gelijk; kopregel aanwezig |
| #98 | GPKG naar drie objectlagen; `gemengd_zonder_overstort` in `vlakken` | vlakken 614 + 99 = 713; laag weg |
| #101 | mensleesbare nulmeting-teksten (tabel in de issue-body is vastgesteld) | 43/43 vormen vertaald, 0 onvertaald; MD/GPKG alleen de zin, CSV/JSON beide velden |

### Blok G — ATTR-001 drains (review: Substantieel)

| Issue | Wat | Richtgetal |
|---|---|---|
| #86 | research gangbare drainrange (bron in BO), dan constructietype-uitzondering | drain-meldingen met gangbare maat uit ATTR-001; vrijverval ongewijzigd |

## Slotstap van déze run

Geen gemeentebrede eindrun (die hoort bij de slotrun-sessie na blok I). Wel: slotrapport aan
de auteur per blok (wat landde, gemeten naast voorspeld, BO's, uitgestelde minors, open
gebleven issues en waarom), als comment op #79.
