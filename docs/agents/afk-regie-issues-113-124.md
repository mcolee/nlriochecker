# AFK-regie 30-08-2026: issues #113 t/m #124 (swarm-reeks)

Geef dit aan een **verse (gecleared) Fable-sessie** in `/home/martin/nlriochecker`, in
auto-mode. Fable is de regisseur; het werk doen **Opus-subagents** (`model: opus`,
`subagent_type: general-purpose`, per taak een verse agent). De auteur is er niet bij:
**unattended, stel geen vragen**. Het sjabloon `docs/agents/afk-regie.md` geldt onverkort;
dit bestand vult alleen de issuelijst, de volgorde, de bewijslast en de bijzonderheden van
deze reeks in. Bij tegenspraak wint `CLAUDE.md`, dan het sjabloon, dan dit bestand.

De twaalf issues komen uit de multi-lens review-swarm van 30-08 (57 agents, eindplan van
25 aanbevelingen). Ze zijn de **besluitvrije** helft: geen domeinregel verschuift, geen
publiek contract (JSON-schema, CLI, GeoPackage-structuur) verandert, en de uitslag van een
run blijft — op #119's foutafhandeling na — **identiek**. Dat is tegelijk de bewijslast van
deze reeks: elk issue moet aantonen dat er niets verschoof.

## Vooraf, één keer

1. Lees `CLAUDE.md`, `docs/agents/afk-regie.md`, `docs/agents/analyse-harness.md` en van
   `docs/architectuur.md` de delen over de meldingenstroom, herkomst en de GeoPackage
   (#114, #118, #122) en over de cache/`CheckContext` (#118, #123, #124). Eén keer volledig,
   niet per symbool.
2. Uitgangstoestand: `git status` schoon op `dev` (de untracked mappen `scratchpad/` en
   `.claude/workflows/` mogen er staan; #120 zet ze in `.gitignore`), `git log --oneline -1`
   toont `9c1a7bd` (HGT-010-hernoeming, #112) of later, en
   `gh issue list --label ready-for-agent` toont precies #113 t/m #124.
3. De referentierun voor alle vergelijkingen is **`uitvoer/30082026_slotrun`** (30-08, versie
   0.3.0, **147.706 meldingen**; `bevindingen.csv` is `;`-gescheiden, kolom `Check`; de
   checktabel staat in `bevindingen.md` vanaf regel 277). Tel dáár op; start geen nieuwe volle
   run vóór de slotstap.
4. **Byte-gelijk bestaat niet tegen de slotrun.** Die draaide met `nlriochecker 0.3.0`; `dev`
   staat op 0.3.1 en de herkomst zit in elke CSV-rij en in de JSON-envelop, plus `RunDatum`.
   "Niets verschoven" bewijs je daarom zo: (a) per check het aantal uit `bevindingen.csv`
   gelijk aan de slotrun, en (b) waar het issue byte-gelijkheid eist (#121, #122): een
   **voor/na-paar op dezelfde HEAD** — run vóór de wijziging op een kleine set
   (`voorbeelden/koekangerveld/` of de gebiedsrun Koekangerveld), run ná, en `cmp` op CSV en
   JSON met `RunDatum` weggefilterd. De issues beschrijven de precieze procedure; volg die.
5. Issues lezen: `gh issue view N --comments` of
   `gh api repos/mcolee/nlriochecker/issues/N --jq .body` plus `/comments`. Elk issue heeft
   zes koppen; **kop 6 (Aannames)** is de tweede bron bij twijfel, een comment de derde.
6. BO-nummers: het hoogste is **BO-85**. In deze reeks is er hooguit één nieuw BO (#115 vult
   BO-38 aan in plaats van een nieuw nummer; #120 en #119 hebben er geen nodig). Neem altijd
   `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1.

## Volgorde — strikt sequentieel

De volgorde is die van het swarm-plan: eerst het bewijsmateriaal (#113), dan de lichte
test-/configissues, dan de hekken zonder kritiek pad, dan de twee kritieke-padissues, dan
de twee perf-issues die op #113 leunen.

| # | Issue | Blocked by | Review | Poort-bijzonderheid |
|---|---|---|---|---|
| 1 | **#113** gouden ledger per check over de fixtureveeg en het voorbeeld | — | `/code-review medium` | test-only; nieuw `tests/golden/ledger.json` + `scripts/maak_ledger.py` |
| 2 | **#114** waardegelijkheid CSV/JSON/GeoPackage; objectlagen tegen meldingentabel | — | `/code-review medium` | test-only |
| 3 | **#115** takdekking aan (`branch = true`, grens blijft 95) | — | geen review; drifttests `tests/test_uitgave.py` | **`runnerpoort.py` verplicht**: CI-marge kan nul zijn |
| 4 | **#116** directe unittests `checks/meetkunde.py`; `is_finite(MultiLineString)` | — | `/code-review low` | test-only; `_flat_coords` **niet** aanpassen |
| 5 | **#117** data-vrije drifttest op de 17 SHACL-vormen van het voorbeeld | — | `/code-review low` | test-only; moet op de runner draaien |
| 6 | **#118** vier drifthekken: laagsnit, cachesleutels, markering, `Finding()` | #122 (zacht, zie onder) | **Substantieel** | raakt `checks/base.py`, `attributen.py`, `reporting.py` |
| 7 | **#119** kapotte invoer → PipelineError; sqlite-URI quoten | — | `/code-review medium` | enige issue met een gedragsverandering (foutpad) |
| 8 | **#120** CI/repo-hygiëne: permissions, SHA-pins, dependabot, `--frozen`, `.gitignore` | — | geen review; nieuwe drifttest op `--frozen` | raakt `.github/workflows/` — zie bijzonderheden |
| 9 | **#121** mypy-ratchet; EXT-tak uit het Any-gat | — | **Substantieel** | `checks/extern.py`; voor/na-paar byte-gelijk |
| 10 | **#122** feitenkanaal naast de meldingenstroom; popup parseert geen zin | — | **Substantieel** | `uitvoer/melding.py`, `checks/base.py`, `gpkg.py`; voor/na-paar |
| 11 | **#123** shapely-herhaling TOP-familie: gecachte coords en buffers | #113 | **Substantieel** | `checks/`; nul verschuiving + tijdmeting |
| 12 | **#124** graafscans: `_eindpunten` cachen, ATTR-014 op indexsweeps | #113 | **Substantieel** | `checks/`; nul verschuiving + `_PropertyTelling` per kenmerk |

De GitHub-dependencies staan native (#123/#124 ← #113, #118 ← #122). **#118 vóór #122 is
bewust**: het laagsnit-hek start met een gevulde allowlist (de import `gpkg.py` →
`checks.randvoorzieningen`), en #122 laat die allowlist daarna krimpen. Verwijder bij #122
de regel uit de allowlist; laat je hem staan, dan is het hek loos.

Eén issue = commit + push + CI groen + comment + close vóór het volgende.

## Bewijslast per issue (De Wolden en Hoogeveen, tegen `uitvoer/30082026_slotrun`)

| Issue | Wat de agent meet | Verwacht |
|---|---|---|
| #113 | ledger over de fixtureveeg (183 fixtures × 89 checks) | 869 rijen met ≥1 bevinding, 56 `DEFECTEN`-rijen; `MELDINGEN_IN_HET_VOORBEELD = 337` blijft |
| #114 | nieuwe test op fixture met paarmelding, systemische melding en melding zonder object | groen; `_melding_rij` 28 posities, `_samenvatting` 33 |
| #115 | `--cov-branch` lokaal en via `runnerpoort.py` | lokaal ~96 %; runner **≥ 95,0** — zakt hij eronder: **niet verlagen, niet doordrukken**, comment en open laten |
| #116 | 24 verwachte waarden uit het issue; reproductie `is_finite(MultiLineString)` | `NotImplementedError` vastgelegd als huidig gedrag (xfail of expliciete assert, zoals het issue kiest) |
| #117 | unieke vormen in `voorbeelden/koekangerveld/` | **17**, alle vertaald; telling `== 17` vóór de "alle vertaald"-assert |
| #118 | de vier sweeps | groen op `dev`; 52 literale cachesleutels, 21 `sel:`-sleutels bij de rolfuncties |
| #119 | de vijf reproducties uit het issue via de CLI | elk eindigt in een nette foutmelding, geen traceback; `mode=ro` niet omzeilbaar |
| #120 | `gh api …/git/ref/tags/<tag>` voor beide actions; `uv run --frozen` in `uitgave.py:toets()` | SHA's opnieuw opgezocht, niet overgenomen; CI-pytest-regel **ongewijzigd** |
| #121 | mypy met de drie vlaggen + overrides; ruff `D` | precies **25** tranchefouten resteren vóór de fix (extern 18, externedata 6, selectie 1), **0** erna; `ANN` blijft uit |
| #122 | voor/na-paar op dezelfde HEAD | CSV en JSON byte-gelijk (`RunDatum` weggefilterd); RVZ-006-popup en EXT-001-afstand inhoudelijk gelijk |
| #123 | checkaantallen tegen slotrun; tijd vóór/ná | TOP-006 **13** (op 18.213), TOP-007/008/010/011/017/018 en EXT-rijen gelijk; ~10 s winst is een lensmeting, te reproduceren |
| #124 | `_PropertyTelling` per kenmerk vóór/ná; `ncalls` en `perf_counter` apart | ATTR-014-tellingen identiek; "winst nul → stap 2 laten liggen" is een geldige uitkomst |

Elke andere check blijft gelijk aan de referentierun. Wijkt iets af: verklaar het in de
issue-comment, verzin geen nieuwe waarheid.

## Bijzonderheden per issue

- **#113.** Het bewijsmateriaal voor #123 en #124 — doe het eerst en goed. De veeglus komt in
  `scripts/maak_ledger.py` met een session-fixture in `conftest.py`; generator en test delen
  letterlijk één lus. Laadrecept mét `markeer_vulwaarden` (zoals `toetsrun.py`), anders legt
  de ledger iets vast wat geen run oplevert. Klok pinnen voor de fixtureveeg (ATTR-007 via
  `begindatum_maximum`, ADM-006 via monkeypatch), **niet** voor de voorbeeldrun.
- **#114.** `_meldingen_per_object` groepeert alleen op `object_uri`; een paarmelding telt
  niet mee op zijn tweede object — de test moet dat volgen, niet "corrigeren". CSV lezen met
  `dtype=str, keep_default_na=False`.
- **#115.** Eén regel in `pyproject.toml`; `toets.yml` en `uitgave.py` niet aanraken (één
  vindplaats). Bewijs dat coverage de sectie leest (kolommen `Branch BrPart` in de uitvoer).
  De vervolgronde over de tien modules met de meeste halve takken is **geen** onderdeel en
  wordt niet als issue aangemaakt.
- **#116.** Nieuw testbestand met shapely-objecten zonder TTL. `_flat_coords` gelijktrekken
  met `coords_of` is een auteursbesluit → buiten scope; leg het huidige gedrag vast.
- **#117.** De omgekeerde bewering (elke tabeltekst komt in het voorbeeld voor) mag **niet**
  mee: 26 van 43 teksten staan niet in het voorbeeld. `vormteksten.cache_clear()` bij de
  rood/groen-stap. Geen `workflow_dispatch`-job.
- **#118.** Substantieel voor het hele issue (hek (c) verplaatst `.markering()`-aanroepen in
  `reporting.py` en repareert een doc-belofte in `docs/architectuur.md:164` die nu al onwaar
  is). Volgorde binnen het issue: eerst de regel in `docs/architectuur.md` opschrijven, dan
  het hek. `Sleutel[T]`, een protocol en een monkeypatch-sweep zijn buiten scope.
- **#119.** Geen `tests/fixtures/kapot/`: defecte invoer bouw je in `tmp_path` (het `?`-geval
  is op Windows onmaakbaar als gecommit bestand). Helper `readonly_uri` in `studiegebied.py`
  met lokale import in `externedata.py` (andersom geeft een importkring). De configureerbare
  invoergrens in `[nulmeting]` is verworpen. CHANGELOG: gedragsverandering op het foutpad.
- **#120.** Dit issue raakt de CI zelf; drie valkuilen. (1) `--frozen` gaat in
  `scripts/uitgave.py:toets()`, **niet** in de CI-pytest-regel van `toets.yml`:
  `scripts/runnerpoort.py:41` matcht die regel letterlijk en breekt anders. (2) SHA's opzoeken
  met `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (beide tags zijn lightweight, dus
  `object.sha` is de commit); de SHA's in het issue zijn controlewaarden, geen bron.
  (3) dependabot alleen `github-actions`, `target-branch: "dev"`, en daarom
  `pull_request: branches: [main, dev]` in `toets.yml` — anders krijgt een dependabot-PR geen
  poort. `.gitignore`: `scratchpad/` en `.claude/workflows/` (zonder leidende slash is hier
  goed; controleer dat `src/` niets verliest met `git status --ignored`). pip-audit en het
  verhuizen van de repo-hook zijn verworpen. Na de push: de CI draait mét het nieuwe
  `permissions:`-blok — `gh run watch` is hier het echte bewijs.
- **#121.** Ratchet zoals het issue voorschrijft: drie vlaggen aan in `[tool.mypy]` plus één
  `[[tool.mypy.overrides]]` met de 15 modules die nog uit staan; de tranche is de EXT-tak
  (extern 18, externedata 6, selectie 1). Ruff `D` met `ignore = ["D203","D213","D400","D401"]`,
  D415 blijft aan; **`ANN` gaat niet mee**. Ruff draait repo-breed, dus scoping op `tests/**`
  en `scripts/**` via `per-file-ignores` is verplicht. Annoteren van `objecten()`/
  `geometrie_van` kan echte subklasse-mismatches blootleggen — dat is het doel; los ze op in
  de subklasse, niet met `# type: ignore`.
- **#122.** Geen nieuw veld op `Melding` (landt reflectief in de JSON: contract). De zijmap
  `melding_id -> feiten` komt uit `bouw_meldingenstroom` als tweede retourwaarde, gevuld uit
  `feit_sleutels` per check (zelfde vorm als `id_sleutels`). Drie lezers omzetten: RVZ-006
  (`aanwijzingen_van`), EXT-001 (`_kleinste_afstand`) en `scripts/meet_rvz006_aanwijzingen.py`.
  Alleen de import `gpkg.py` → `checks.randvoorzieningen` vervalt; `selectie`, `treffers`,
  `verbanden` blijven. Werk daarna de allowlist van #118 bij. `Trefferregister._afstanden`/
  `afstand()` worden wees: opruimen.
- **#123.** `is_finite` en TOP-009 buiten scope (lopen over `_flat_coords`). `overlap_length`
  houdt zijn signatuur (`scripts/meet_v5_gevoeligheid.py` roept hem aan) en delegeert.
  Buffers gesleuteld op `(uri, tolerantie)`. Beide richtingen van een paar behouden. Tijd
  meten met `perf_counter` op de voorgrond, zonder profiler, op de gebiedsrun én op de volle
  export — plak beide.
- **#124.** Alleen stap (1) en (2); de klasse-index (stap 3, `checks/klasseindex.py`) is
  **buiten scope** en wordt niet als issue aangemaakt. Mutatie-audit: een gecachte `set`
  teruggeven mag alleen als geen beller hem muteert (nagelopen: alle vier lezen alleen —
  controleer het opnieuw na je wijziging). Werk de voorvoegsel-eigenaren in de docstring van
  `CheckContext.cached` bij; `subject_objects` is publieke API van `gwsw_orox_helpers`
  (Harde regel blijft heel).

## De lus per issue

Precies het sjabloon (`docs/agents/afk-regie.md`, "De lus per issue N"), met de
aanscherpingen uit de metingen van 24–26-08:

- Brief aan elke implementer bevat letterlijk: *"Lees `docs/architectuur.md` en
  `docs/agents/analyse-harness.md` één keer volledig vóór je begint, en daarna elk bestand
  dat je aanraakt één keer volledig; geen `cd`; draai de poort en elke meetrun op de
  voorgrond en plak de uitvoer; niet pushen."* Taaklabel "Task N" in het Engels. Geef de
  implementer het issuenummer en de regel "kop 6 (Aannames) is je tweede bron; een afwijking
  leg je vast in je rapport, niet in een vraag".
- Vertrouw de geplakte poort van de implementer; draai hem niet nog eens.
  `scripts/runnerpoort.py` één keer, vlak vóór de push, nooit parallel aan een pytest. Bij
  **#115 en #117** is runnerpoort de eigenlijke test (runner-conditie), dus lees zijn uitvoer
  inhoudelijk, niet alleen de exitcode.
- Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels
  raakte.
- Voor de vijf Substantiële issues (#118, #121, #122, #123, #124): verse Opus-reviewer via
  `superpowers:requesting-code-review`, adversarieel, met de vraag erbij: *"toon aan dat de
  uitslag niet verschoof — welke meting in het rapport bewijst dat, en klopt die?"*
- Comment pas na het reviewoordeel; dan `gh issue close`. In de comment: het gemeten getal
  naast de verwachting uit de tabel hierboven.
- Push: `timeout 45 git push`; CI selecteren op `gh run list --commit <sha>`, dan
  `gh run watch <id> --exit-status`. Rood → fixen, niet door naar het volgende issue.
- Na een dispatch of een achtergrondcommando: niets doen tot de melding komt.
- Classifier-blokkade (soms de eerste dispatch): geen varianten proberen; noteer het en
  probeer één keer opnieuw. Er hoeft in deze reeks **geen issue aangemaakt** te worden en
  er komt geen nieuwe repo; de enige `gh`-schrijfacties zijn `edit --add-assignee`,
  `comment` en `close`.

## Slotstap

1. Volledige gemeentebrede run op de eindstand van `dev`, met **dezelfde vlaggen** als
   `docs/checks-audit-2026-08.md:20` (drie `--shacl`, `--projectconfig
   configs/dewoldenhoogeveen.toml`, `--bronnen data/gis_dewoldenhoogeveen`), naar
   `uitvoer/<datum>_slotrun`, als `run_in_background` (4,5–5,5 min, ~4 GB). Meet de
   wall-clock van deze run en zet hem naast die van `uitvoer/30082026_slotrun/_slotrapport.md`:
   dat is het gezamenlijke perf-cijfer van #123 en #124.
2. Vergelijk per check met `uitvoer/30082026_slotrun/bevindingen.csv`; verwacht:
   **elke check gelijk, totaal 147.706**. Elk verschil is een regressie van deze reeks, geen
   verbetering — zoek de oorzaak, verzin geen verklaring.
3. Open de GeoPackage niet zelf; de PyQGIS-test (`tests/test_uitvoer_qgis.py`, lokaal) en de
   waardegelijkheidstest uit #114 zijn het bewijs.
4. Slotrapport in `uitvoer/<datum>_slotrun/_slotrapport.md` én als laatste bericht: per
   issue wat er landde, gemeten naast verwacht, BO-nummers, open gebleven punten, de
   uitgestelde minors uit de reviews (de ledger is git-ignored en telt niet als bewaarplek),
   en de twee perf-cijfers. Noem ook de dertien swarm-aanbevelingen die **niet** in deze reeks
   zaten (2, 3, 4, 6, 7, 9, 11, 15, 18, 21, 22, 23, 25 in
   `scratchpad/nlrio-swarm-plan-2026-08-30.json`; beslisvragen in
   `scratchpad/beslisvragen-swarm-2026-08-30.docx`) als "wacht op de auteur" — maak er geen
   issue van.
5. Laat `dev` schoon achter: alles gecommit en gepusht, CI groen, geen half bewerkt bestand.

## Harde grenzen

- Nooit `main`; geen uitgave; geen `scripts/uitgave.py`.
- Het JSON-schema, de CLI-opties en de GeoPackage-structuur veranderen in deze reeks **niet**.
  Vindt een implementer dat een issue dat toch vraagt, dan is dat een fout in het issue:
  comment, issue open laten, door naar het volgende.
- Geen nieuw `Melding`-veld (#122), geen klasse-index (#124), geen `_flat_coords`-wijziging
  (#116/#123), geen `ANN` (#121), geen pip-audit of hook-verhuizing (#120), geen
  `tests/fixtures/kapot/` (#119).
- Overschrijf nooit invoerbestanden; alleen `uitvoer/` schrijft; versienummer alleen in
  `pyproject.toml`. Bij twijfel over domeinlogica: GWSW is leidend, de issue-sectie
  **Aannames** is de tweede bron, een comment de derde; nooit een vraag aan de auteur.
