# AFK-regie na de Fable-swarm van 05-09-2026: issues #139, #141–#161 en sessies E/F

Geef dit aan een **verse (gecleared) Fable 5.1-sessie** in `/home/martin/Development/nlriochecker`,
in auto-mode. Fable is de regisseur en schrijft zelf geen code; het werk doen **Opus
4.8-subagents** via `subagent_type: opus48` (de kale alias `model: opus` levert in deze
harness Opus 5 — niet gebruiken). Alleen de issues die in de tabel **Sonnet** dragen zijn
klein genoeg voor `model: sonnet`, `subagent_type: general-purpose`. **Meld bij elke
dispatch welk model je inzet.** De auteur is er niet bij: **unattended, stel geen vragen**.
Het sjabloon `docs/agents/afk-regie.md` geldt onverkort; dit bestand vult de issuelijst, de
volgorde, de bewijslast en de bijzonderheden in. Bij tegenspraak wint `CLAUDE.md`, dan het
sjabloon, dan dit bestand.

De 22 issues komen uit de Fable-swarm van 05-09 (`.claude/workflows/nlrio-fable-swarm.js`,
run `wf_77797a1d-338`: 12 lenzen met bewijsplicht, 51 van 52 bevindingen door een skepticus
bevestigd, plan in `~/nlriochecker-onderzoek/2026-09-05-fable-swarm/plan.json`) en zijn op
06-09 in een grilling met de auteur naar de huisstijl gebracht (`docs/agents/issue-tracker.md`,
zes koppen). Alle ontwerpkeuzes staan onder kop 2 ("Keuzes die al gemaakt zijn"); kop 6
(Aannames) is wat de auteur bewust aan de agent laat. Van de vijf geparkeerde punten
(#162–#166) zijn #163, #165 en #166 op 06-09 in een grilling `ready-for-agent` geworden en
vormen met #137, #138, #169 en #170 de **sessies E en F**; #162 en #164 blijven geparkeerd.

**Splits de reeks in zes sessies** (globale `CLAUDE.md`, "Mega-sessies splitsen"): elke
sessie eindigt met CI groen, issues dicht en een slotcomment; de volgende sessie start vers
met dit bestand en de sessieletter. Eén sessie draagt nooit meer dan één perf-issue met een
volle De Wolden-meting tegelijk.

## Vooraf, één keer per sessie

1. Lees `CLAUDE.md`, `docs/agents/afk-regie.md`, `docs/agents/analyse-harness.md`, en van
   `docs/architectuur.md` de delen die de issues van de sessie raken. Eén keer volledig.
2. Uitgangstoestand: `git status` schoon op `dev`, `gh issue list --label ready-for-agent`
   toont de issues van deze en de volgende sessies. Een issue met een open blokkeerder
   (#159 ← #139; de frontier-query uit `issue-tracker.md`) sla je over tot de blokkeerder dicht is.
3. De referentierun is **`uitvoer/04092026_slotrun`** (dev `b83848d`, **161.158 meldingen**,
   `bevindingen.csv` `;`-gescheiden). Tel dáár op; start geen volle run vóór de slotstap van
   de sessie, behalve waar de bewijslast hieronder er expliciet één vraagt.
4. Issues lezen: `gh issue view N --comments`. Kop 6 (Aannames) is de tweede bron bij
   twijfel, een comment de derde.
5. BO-nummers: het hoogste is **BO-92**. Alleen #141 vraagt een nieuw BO (HGT-009 282 → 730);
   neem `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1 op het moment van schrijven.
6. Perf-issues (#143–#149) zijn pas klaar met de **gepaarde meting**: referentie en
   experiment om en om, n ≥ 3, achter `flock`, eenduidig (traagste experiment sneller dan
   snelste referentie), én een volle `toets` met `--bronnen data/gis_dewoldenhoogeveen`
   waarvan `bevindingen.csv` na blanken van RunDatum sha256-gelijk is aan de referentie.
   De meetstraat (`scripts/harnas.py`, `scripts/vergelijk_csv.py`) landt in #143; tot dan
   staan ze in `~/nlriochecker-onderzoek/2026-09-05-fable-swarm/perf-checks/`. De
   prototypes daar (`patch_*.py`) zijn de letterlijke vorm van de fix; kopieer de vorm, niet
   het monkeypatch-mechanisme.

## Volgorde — strikt sequentieel, in zes sessies

| Sessie | # | Issue | Blocked by | Model | Review | Poort-bijzonderheid |
|---|---|---|---|---|---|---|
| **A** | 1 | **#139** 1.7 stil nul: `termen_voor` + gepaarde 1.6/1.7-drifttest | — | Opus 4.8 | **Substantieel** | drifttest rood vóór, groen na; ledger gelijk |
| A | 2 | **#141** HGT-009 per aanvoerende streng (282 → 730) | — | Opus 4.8 | **Substantieel** | nieuw BO; fixture via generator; ledger regenereren; audit-doc bijwerken |
| A | 3 | **#142** `waarde`/`drempel` in elke check met een meting | — | Opus 4.8 | **Substantieel** | zeven checkmodules; drifttest op `[drempels]`-sweep; geen schema-bump |
| **B** | 4 | **#143** AHN één keer bemonsteren + meetstraat naar `scripts/` | — | Opus 4.8 | Klein, bij twijfel Substantieel | gepaard + sha-gelijke CSV |
| B | 5 | **#144** EXT-001 bulk-STRtree | — | Opus 4.8 | Klein | gepaard + sha-gelijk; unittest tiebreak |
| B | 6 | **#145** TOP-006/010/011 bulk | — | Opus 4.8 | **Substantieel** | gepaard + sha-gelijk |
| B | 7 | **#146** `shapely.prepare(extent)` + selectie per populatie | — | Opus 4.8 | Klein | cachesleutel-drifttest mee |
| B | 8 | **#147** bronkolommen smal + geheugenclaim rechtzetten | — | Opus 4.8 | Klein | `ru_maxrss` vóór/na; CLAUDE.md/BO-42 tekst |
| B | 9 | **#148** JSON/CSV streamend, GeoPackage atomisch | — | Opus 4.8 | **Substantieel** | `cmp` bytes gelijk; schrijversweep blijft groen |
| B | 10 | **#149** type-index, `klassen_op_nul` één keer, xy-map | — | Opus 4.8 | **Substantieel** | `CACHE_VOORVOEGSELS['omvang']` |
| **C** | 11 | **#150** één telling per rapport | — | Opus 4.8 | **Substantieel** | drifttest samenvatting == verantwoording == tabel |
| C | 12 | **#151** kaartpijl leest de vlak-band | — | Opus 4.8 | **Substantieel** | telscript 557 → 0 |
| C | 13 | **#152** TOP-009 put zonder punt; NaN/Inf | — | Opus 4.8 | **Substantieel** | end-to-end fixtures NaN/1e999 |
| C | 14 | **#153** validaties vóór de laadfase | — | Sonnet | Klein | CliRunner op `/proc`-pad |
| C | 15 | **#154** studiegebied zonder geometrie | — | Sonnet | Klein | twee fixtures |
| C | 16 | **#155** `dekking` zegt "typering niet gemeten" | — | Sonnet | Klein | tekst-only |
| C | 17 | **#156** vier kleine fixes (BOM, tabel, TOP-004, T-stuk-examined) | — | Opus 4.8 | **Substantieel** | TOP-004 24 → ~2; NET-005/007 examined |
| **D** | 18 | **#157** `zwaar` als zesde stap in `uitgave.py` | — | Sonnet | Klein | geen `src/**.py` |
| D | 19 | **#158** wheel-rooktest + git-dependency als direct reference | — | Sonnet | Klein | rooktest rood vóór, groen na |
| D | 20 | **#159** `leeslaag.py` + hek a4 | #139 | Opus 4.8 | **Substantieel** | `tel_oppervlak.py`: 14 → 1 bestand |
| D | 21 | **#160** zes hekken die niet bijten | — | Opus 4.8 | Klein; (a) Substantieel | elk hek met tegenproef |
| D | 22 | **#161** kopieën, docstrings, naamregel, mypy-ratchet | — | Opus 4.8 | **Substantieel** | ledger gelijk; override-blok leeg |
| **E** | 23 | **#137** checks declareren hun `[klassen]`-lijsten; HGT-011 toetst de drempels | — | Opus 4.8 | **Substantieel** | nieuw BO; drifttest rood vóór, groen na; dekkingsmatrix regenereren; volle run |
| E | 24 | **#138** rol versmallen naar het register: EXT-001, ATTR-017, TOP-014 | #137 | Opus 4.8 | **Substantieel** | nieuw BO (het issue zegt BO-94: neem het vrije nummer); volle run |
| E | 25 | **#169** `gwsw_run` bij naam schrijven: dict i.p.v. positionele 35-tuple | — | Opus 4.8 | **Substantieel** | GeoPackage sha-gelijk (`update_time` genormaliseerd) |
| **F** | 26 | **#165** CONTRACT `bevindingen.csv` als NL-Excel-bestand | #161 | Opus 4.8 | **Altijd Substantieel** | nieuw BO; handmatige `soffice`-controle in de comment |
| F | 27 | **#163** CONTRACT overlay op `--projectconfig` met `basis = "standaard"` | #161, #165 | Opus 4.8 | **Altijd Substantieel** | zonder `basis` byte-voor-byte hetzelfde gedrag |
| F | 28 | **#166** LEESLAAG pin v0.2.2 → v0.2.4; `leeslaag.py` delegeert | #158, #159 | Opus 4.8 | **Substantieel** | `uv lock`; cache koud herbouwd; gepaarde meting achter `flock` |
| F | 29 | **#170** research puntbemonstering uit een float32-raster → `docs/onderzoek/` | — | Sonnet | Klein | geen code; `mattpocock-skills:research`; comment op #168 |

Eén issue = commit + push + CI groen + comment + close; alleen de CI-wacht mag overlappen
met de dispatch van het volgende issue (sjabloon, stap 7), en twee implementers mogen in
eigen worktrees naast elkaar werken onder de voorwaarden uit het sjabloon ("Volgorde").
Paren die daarvoor in aanmerking komen: **D:** #157 + #158 naast #159; **E:** #169 naast
#137; **F:** #170 (alleen docs) naast elk ander issue. Niet: #159/#160/#161 onderling
(delen `src/`), #163/#165 (contract), #166 naast een ander (meting + pin).

## Bewijslast per issue (De Wolden, tegen `uitvoer/04092026_slotrun`)

| Issue | Wat de agent meet | Verwacht |
|---|---|---|
| #139 | `repro_17_stil_nul.py` uit de scratchmap; nieuwe gepaarde 1.6/1.7-test | ADM-008 en ATTR-014 per fixture gelijk in 1.6 en 1.7; De Wolden **nul** verschil |
| #141 | `meet_hgt009.py` door de echte pijplijn | HGT-009 **282 → 730 knopen / 816 meldingen**; andere checks gelijk |
| #142 | Koekangerveld-CSV: kolommen Waarde/Drempel | gevuld op elke register-melding met een meting (nu 2 van 162); repro A/B geeft `gewijzigde_waarde` |
| #143 | `harnas.py gepaard 3` op HGT-001/002/003 | **27–29 s → 6,4–6,9 s**, eenduidig; CSV sha-gelijk |
| #144 | `harnas.py gepaard 3` op EXT-001 | **11,7 s → 2,8 s**; CSV sha-gelijk |
| #145 | `harnas.py gepaard 3` op TOP-006/010/011 | **~9 s → ~3,5 s**; CSV sha-gelijk |
| #146 | `extent_micro.py` + volle run | extent-toets **1,6 s → ~0,2 s** per pas; CSV sha-gelijk |
| #147 | `ru_maxrss` van de volle run | **−0,5 GB** (bronnen 1,8 GB → ~1,3 GB); CSV sha-gelijk |
| #148 | `cmp` op json/csv; tracemalloc van `schrijf_json` | bytes identiek; piek **817 → ~27 MiB**; half GeoPackage-repro groen |
| #149 | `meet_gepaard2.py` | Markdown-kop **~4,5 s → ~0,9 s**; stroom ~5,4 → ~4,3 s; `gelijk_aan_A` |
| #150 | Koekangerveld met `onderdruk_checks` | één foutentotaal in tabel, Verantwoording en terminal |
| #151 | `tel_pijl_vs_net009.py` op de nieuwe GeoPackage | pijlen binnen de band **557 → 0**; meldingen gelijk |
| #152 | fixtures put-zonder-punt, NaN, Inf | TOP-009 meldt; CLI eindigt met een melding; De Wolden **nul** verschil |
| #153–#155 | CliRunner-tests | `Fout: …` zonder traceback; `dekking.md` draagt de typeringsregel |
| #156 | `bevindingen.csv` TOP-004; `meet_tstuk.py` | TOP-004 **24 → ~2**; NET-005/006/007 examined −152 of 152 beoordeeld |
| #157–#158 | droge run `uitgave.py`; rooktest in CI | zesde stap zichtbaar; rooktest groen na de dependency-wijziging |
| #159 | `tel_oppervlak.py` | bestanden die release B raken **14 → 1**; hek a4 groen en kan afgaan |
| #160 | elk hek met tegenproef; `load_check_config()` | geen checkmodule geladen bij een TOML-load (was 16) |
| #161 | ledger; `ruff --select ARG`; `mypy` zonder override | byte-gelijk; 0 ARG001; groen |
| #137 | `examined` van HGT-011 in de volle run; `aantal_meldingen` | HGT-011 `examined` **22.363 → 0** (gelijk aan RVZ-011); 0 F / 0 W blijft; geen enkele bevinding verschuift |
| #138 | volle run: `examined` EXT-001, onderdrukkingstelling, TOP-014 | EXT-001 `examined` **−~1.605**; **962** ATTR-017-meldingen weg uit de onderdrukking (`gwsw_run`, JSON); TOP-014 **−3** |
| #169 | sha256 van de GeoPackage vóór/na (Koekangerveld en De Wolden) | gelijk; de nieuwe naam-test rood op een bewust verwisselde tuple, groen op de dict |
| #165 | `soffice --headless --convert-to ods` op `bevindingen.csv` van een volle run | alle X/Y-cellen numeriek; JSON/GeoPackage ongewijzigd |
| #163 | CliRunner: projectconfig mét en zonder `basis`; `configs/dewoldenhoogeveen.toml` | zonder `basis` identiek aan vandaag; De Wolden-run sha-gelijk |
| #166 | meetscript onder `scripts/`: `laad_met_cache` bij cachetreffer, `ru_maxrss`, n ≥ 3 om en om | `uv.lock` op v0.2.4; cache één keer koud (~0,5 min); CSV sha-gelijk aan de referentie |
| #170 | het verslag in `docs/onderzoek/` | per techniek bron, lossless ja/nee, richting koud/warm; herziene variantenlijst voor #168 |

Elke andere check blijft gelijk aan de referentierun (na #141 verschoven met precies +448
knopen HGT-009, na #156 TOP-004 −22). Wijkt iets af: verklaar het in de issue-comment,
verzin geen nieuwe waarheid.

## Bijzonderheden per issue

- **#139.** Alleen publieke namen uit v0.2.2 (`gwsw_versie.basis`, `namen.termen_voor`);
  `_basis` en `graph.gwsw_basis` zijn verboden terrein. Is #159 nog niet geland, dan een
  kleine privé-helper per module die #159 later vervangt.
- **#141.** Melding op de **put** met `id_sleutels=('streng',)`; rollen ongewijzigd. De BO
  legt de trendbreuk voor `vergelijk` uit. HGT-011 houdt `min(aanvoer)`.
- **#142.** Conventie `drempel='0.10 (drempels.tegenverhang_fors_m)'`; HGT-011/RVZ-011 hernoemen
  hun labelsleutel naar `drempel_label`. Geen schema-bump.
- **#143.** Neemt `harnas.py` en `vergelijk_csv.py` op onder `scripts/` met de commit-hash
  van de dataset-lader in de docstring (BO-43). Alle latere perf-issues verwijzen ernaar.
- **#144–#146.** Eén perf-issue per sessie-eenheid; de meting draait achter `flock` op de
  voorgrond van de implementer en wordt geplakt. Geen parallelle metingen.
- **#147.** Het tijdreeks-slot voor BTR-004 **niet** bouwen. De CLAUDE.md-zin over 2 GB
  wordt het gemeten getal ná dit issue.
- **#148.** De tijdwinst van streamend JSON is níét bevestigd; de winst is geheugen en
  atomiciteit. De sweep in `tests/test_uitvoer_herkomst.py` mag geen tweede schrijver zien.
- **#149.** Het hijsen van `closure()` uit de per-melding-lus **niet** doen (gemeten geen winst).
- **#151.** Korte variant: band in `_richting_bob`, popup-only tekst, geen vierde kolomwaarde.
  Het structurele vervolg hoort bij het geparkeerde #162.
- **#152.** NaN/Inf hier oplossen; de leeslaag-eindigheidstoets (#166) is geen voorwaarde.
- **#156.** Vier fixes in één issue; elk zijn eigen fixture of repro uit de scratchmap.
- **#158.** Dependency als `gwsw-orox-helpers @ git+https://github.com/mcolee/gwsw-orox-helpers@v0.2.2`
  (auteurskeuze 06-09). `uv tool install git+…` moet blijven werken.
- **#160.** Onderdeel (a) (kringtest) raakt `checkconfig.py` en `checks/base.py`: daar
  Substantieel. De grens `NLRIOCHECKER_MIN_GESLAAGD` naar ~2090 én de waarschuwing bij
  > 10 % marge.
- **#161.** De CLAUDE.md-naamregel en het mypy-override-blok zijn auteursbesluiten van 06-09;
  het verwijderen van de rol `stelsels` is dat **niet** (checks.toml bevroren): alleen de
  docstrings worden eerlijk.
- **Sessies E en F — referentie.** Tel tegen de laatste slotrun (E: na sessie D
  `uitvoer/<datum>_slotrun_D`; F: `uitvoer/<datum>_slotrun_E`), niet tegen 04092026.
  E (#137, #138, #169) draagt twee volle runs vóór de slotstap; F (#165, #163, #166, #170)
  draagt de twee contract-issues en de gepaarde meting van #166. Nooit twee metingen tegelijk.
- **#137.** Veldnaam `klassenlijsten`; de zes velden uit het issue zijn de volledige lijst.
  HGT-011 houdt `vrijvervalrioolleidingen` als rol (kop Aannames). De nul-bewaking (BO-52)
  blijft ongewijzigd. Nieuw BO: "checks declareren hun `[klassen]`-lijsten; HGT-011 toetst
  de drempels".
- **#138.** Drie auteurskeuzes van 06-09, één opruimpass, één BO-blok. Het issue noemt BO-94;
  is dat nummer al vergeven, neem het vrije nummer en meld dat in de comment. ATTR-017 óók
  op mechanische leidingen toetsen is **niet** in scope.
- **#169.** Alleen `_schrijf_runmetadata` en de naam-test; `_eis_feiten`, de bewakingen,
  de fid-volgorde en objectkaart/omvang/voorbehoud blijven ongemoeid. Geen kolomwijziging.
- **#165 en #163.** Publiek contract (label `contract` blijft als reviewsignaal): review
  Altijd Substantieel, BO verplicht bij #165. `Waarde`/`Drempel` blijven tekst (#142).
  Zonder `basis` mag geen byte veranderen.
- **#166.** Heft de harde grens "pin blijft v0.2.2" op, en alleen dáár: `pyproject.toml`
  (direct reference uit #158) en `uv lock`; `LADER_VERSIE` "1" → "3". De leeslaag-punten
  zelf (`knoop_boven`, `isfinite`, `afnemers.md`) leven als gwsw-orox-helpers#77–#79 en
  horen hier niet. HMAC/pickle blijft buiten beeld (BO-6).
- **#170.** Alleen leeswerk tegen primaire bronnen (GDAL/rasterio-docs, GeoTIFF/COG-spec);
  geen meting, geen code, geen nieuwe dependency (BO-3). Draait als
  `mattpocock-skills:research` op Sonnet; `WebFetch` eerst via ToolSearch laden.
- **#140 hoort niet in deze reeks.** Het bouwen van `nlrio-fable-product.js` kan een agent,
  maar "klaar" eist dat de audit-stap van de swarm draait, en dat is een gefactureerde run
  die de auteur zelf start (`args: {stap: 'audit'}`). Pas oppakken na een expliciet startsein.

## De lus per issue

Precies het sjabloon (`docs/agents/afk-regie.md`, "De lus per issue N"):

- Brief aan elke implementer bevat letterlijk: *"Lees `docs/architectuur.md` en
  `docs/agents/analyse-harness.md` één keer volledig vóór je begint, en daarna elk bestand
  dat je aanraakt één keer volledig; geen `cd`; de repo-root is
  `/home/martin/Development/nlriochecker`; draai de poort en elke meetrun op de voorgrond en
  plak de uitvoer; niet pushen."* Voor een **Sonnet/Klein-issue** vervang je het eerste deel
  door de sectie(s) van `docs/architectuur.md` die het issue raakt (bij naam) en laat je
  `analyse-harness.md` weg tenzij het issue meet. Taaklabel "Task N" in het Engels. Geef de implementer het
  issuenummer en de regel "kop 6 (Aannames) is je tweede bron; een afwijking leg je vast in
  je rapport, niet in een vraag".
- De brief draagt de checklist uit het sjabloon (rapportregel → test; tellen ná dedup;
  invariant spiegelen) en het korte rapportcontract (rapport naar bestand, antwoord ≤ 15
  regels); een fixronde is altijd een `SendMessage`-resume (auteursbesluit 06-09, uit
  `docs/onderzoek/2026-09-06-wallclock-afk-regie.md` en `…-tokens-afk-regie.md`).
- Vertrouw de geplakte poort van de implementer; draai hem niet nog eens.
  `scripts/runnerpoort.py` alleen als het issue tests toevoegt die echte data laden
  (CLAUDE.md), vlak vóór de push, nooit parallel aan een pytest.
- Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels raakte.
- Voor de Substantiële issues: verse **Opus 4.8**-reviewer (`opus48`) via
  `superpowers:requesting-code-review`, adversarieel, met de vraag erbij: *"welke meting in
  het rapport bewijst het verwachte getal, en klopt die?"* Bij de perf-issues ook: *"is de
  meting gepaard en eenduidig, en is de CSV sha-gelijk?"*
- Comment pas na het reviewoordeel; dan `gh issue close`. In de comment: het gemeten getal
  naast de verwachting uit de tabel hierboven.
- Push: `timeout 45 git push`; **dispatch daarna meteen de implementer van het volgende
  issue** en wacht pas dán op de CI: selecteren op
  `gh run list --commit "$(git rev-parse HEAD)" --json databaseId --jq '.[0].databaseId'`,
  dan `gh run watch <id> --exit-status`; comment en close van het vorige issue ná groen,
  terwijl de nieuwe implementer werkt. Rood → fix-agent op het vorige issue vóór de
  volgende commit landt (auteursbesluit 06-09, sessie C; zie het sjabloon, stap 7).
- Na een dispatch of een achtergrondcommando: niets doen tot de melding komt.
- Na elke stap en bij elke issuewisseling: de stavaza-tabel met emoticons uit het sjabloon
  (`afk-regie.md`, "Voortgang tonen") als bericht aan de auteur.
- De enige `gh`-schrijfacties zijn `edit --add-assignee`, `comment` en `close`. Geen
  `gh issue create`.

## Slotstap per sessie

1. Volledige gemeentebrede run op de eindstand van `dev`, met **dezelfde vlaggen** als
   `docs/checks-audit-2026-08.md:20` (drie `--shacl`, `--projectconfig
   configs/dewoldenhoogeveen.toml`, `--bronnen data/gis_dewoldenhoogeveen`), naar
   `uitvoer/<datum>_slotrun_<sessieletter>`, als `run_in_background` (~2,5–5 min, ~4 GB;
   na sessie B korter en lichter — noteer de wandklok en `ru_maxrss` in het slotrapport).
2. Vergelijk per check met de referentierun; verwacht: elke check gelijk behalve wat de
   bewijslast hierboven noemt (sessie A: HGT-009 +448 knopen; sessie C: TOP-004 −22;
   sessie E: HGT-011 `examined` → 0, EXT-001 `examined` −~1.605, 962 minder onderdrukt,
   TOP-014 −3; sessie F: alleen de CSV-vorm van #165, verder sha-gelijk).
   Elk ander verschil is een regressie van deze reeks — zoek de oorzaak.
3. Slotrapport in `uitvoer/<datum>_slotrun_<letter>/_slotrapport.md` én als laatste bericht:
   per issue wat er landde, gemeten naast verwacht, BO-nummers, open gebleven punten, de
   uitgestelde minors uit de reviews, en voor sessie B de wandklok en piek vóór/na.
4. Laat `dev` schoon achter: alles gecommit en gepusht, CI groen, geen half bewerkt bestand.

## Harde grenzen

- Nooit `main`; geen uitgave; geen `scripts/uitgave.py` draaien (behalve de droge test in #157).
- Geen contractwijziging: geen CLI-optie, JSON-veld, GeoPackage-kolom, CSV-kolom of
  check-ID. Vindt een implementer dat een issue méér vraagt, dan is dat een fout in het
  issue: comment, issue open laten, door naar het volgende dat er niet op leunt.
- Geen wijziging aan `gwsw-orox-helpers` of aan zijn internals; alleen publieke namen uit
  de gepinde v0.2.2 (#139, #159). De pin zelf gaat alleen in #166 (sessie F) naar v0.2.4.
- Een perf-issue zonder eenduidige gepaarde meting en sha-gelijke CSV is **niet klaar**:
  comment met de ruwe cijfers, issue open laten.
- Overschrijf nooit invoerbestanden; alleen `uitvoer/` schrijft; versienummer alleen in
  `pyproject.toml`. Bij twijfel over domeinlogica: GWSW is leidend, kop 6 is de tweede bron,
  een comment de derde; nooit een vraag aan de auteur.
