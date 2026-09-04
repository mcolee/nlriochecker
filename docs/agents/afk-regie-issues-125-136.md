# AFK-regie 04-09-2026: issues #135, #130, #133, #134, #132, #125, #131, #129

Geef dit aan een **verse (gecleared) Fable 5.1-sessie** in `/home/martin/nlriochecker`, in
auto-mode. Fable is de regisseur en schrijft zelf geen code; het werk doen **Opus
4.8-subagents** via `subagent_type: opus48` (de kale alias `model: opus` levert in deze
harness Opus 5 — niet gebruiken). Alleen #135 is klein genoeg voor `model: sonnet`,
`subagent_type: general-purpose`. **Meld bij elke dispatch welk model je inzet.** De auteur
is er niet bij: **unattended, stel geen vragen**. Het sjabloon `docs/agents/afk-regie.md`
geldt onverkort; dit bestand vult de issuelijst, de volgorde, de bewijslast en de
bijzonderheden in. Bij tegenspraak wint `CLAUDE.md`, dan het sjabloon, dan dit bestand.

De acht issues zijn op 04-09 in een grilling-sessie met de auteur naar de huisstijl
gebracht (`docs/agents/issue-tracker.md`, zes koppen). Alle ontwerpkeuzes zijn genomen;
kop 6 (Aannames) bevat alleen nog wat de auteur bewust aan de agent laat. Anders dan de
reeks van 30-08 verschuift hier wél iets: drie issues raken een publiek contract
(#134, #132, #125: JSON-envelop, `[rapport]`-config, GeoPackage) en twee veranderen de
uitslag (#133: +20.758, #129: +24). Dat maakt de meting per issue de bewijslast.

## Vooraf, één keer

1. Lees `CLAUDE.md`, `docs/agents/afk-regie.md`, `docs/agents/analyse-harness.md`, en van
   `docs/architectuur.md` de delen over de meldingenstroom, herkomst, JSON-contract en
   GeoPackage (#134, #132, #125) en over `CheckContext`/cache en de rollen (#131, #130,
   #133). Eén keer volledig, niet per symbool.
2. Uitgangstoestand: `git status` schoon op `dev`, `git log --oneline -1` toont `adf126c`
   of later, en `gh issue list --label ready-for-agent` toont precies #125, #129, #130,
   #131, #132, #133, #134 en #135. #136 is `needs-info` en hoort **niet** in deze reeks.
3. De referentierun is **`uitvoer/31082026_slotrun`** (31-08, **147.706 meldingen**;
   `bevindingen.csv` is `;`-gescheiden, kolom `Check`). Tel dáár op; start geen nieuwe volle
   run vóór de slotstap. Na #135 draait elke meting op helper v0.2.1; de referentie is met
   v0.1.0 gemaakt en moet per check gelijk blijven — dat is precies wat #135 bewijst.
4. Issues lezen: `gh issue view N --comments`. Elk issue heeft zes koppen; **kop 6
   (Aannames)** is de tweede bron bij twijfel, een comment de derde. Het comment onder #133
   (BRUTIS-herkomst) en onder #125 (impact-analyse) zijn feiten, geen opdrachten.
5. BO-nummers: het hoogste is **BO-88**. #130, #133, #132 en #129 vragen elk één nieuw BO;
   neem altijd `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1 op het moment van
   schrijven, nooit een nummer uit een issue (#130 noemde ooit "BO-89"; dat is een
   voorspelling, geen reservering).
6. Native GitHub-dependencies staan op #135 (← `mcolee/gwsw-orox-helpers#39`), #125
   (← #135 en helper#39) en #129 (← #131). De frontier-query uit `issue-tracker.md` slaat
   een geblokkeerd issue vanzelf over; de volgorde hieronder respecteert ze al. **Is
   helper#39 nog open of nog niet uitgebracht bij de start, dan begin je bij #130 en laat je
   #135 en #125 liggen** — de rest van de reeks leunt er niet op. Een helper-release is
   handwerk van de auteur; vraag er niet om, meld het in het slotrapport.

## Volgorde — strikt sequentieel

| # | Issue | Blocked by | Model | Review | Poort-bijzonderheid |
|---|---|---|---|---|---|
| 1 | **#135** leeslaag naar de `gwsw-orox-helpers`-release met #39 (≥ v0.2.1) | helper#39 | Sonnet | `/code-review medium` | geen `src/**.py`; **`pytest -m zwaar` verplicht** (de leeslaag zelf verandert) + volle run = 147.706 |
| 2 | **#130** TOP-019/022/023: zuiver-mechanische hulpstukken buiten scope | — | Opus 4.8 | **Substantieel** | `checks/` + `rollen`-declaratie; fixtures via `scripts/maak_ttl_fixtures.py`; meting op Koekangerveld |
| 3 | **#133** ATTR-019 putdiepte ontbreekt | — | Opus 4.8 | **Substantieel** | nieuwe check; `runnerpoort.py` (datatest erbij); dekkingsmatrix regenereren |
| 4 | **#134** nulmeting-kopblok: `max_meldingen`, `lokale_eisen` als voorbehoud | — | Opus 4.8 | **Substantieel** | meldingenstroom + JSON (additief, `SCHEMA_VERSIE` blijft 1.2) |
| 5 | **#132** geaccepteerde bevindingen (uitzonderingen) | — | Opus 4.8 | **Altijd-Substantieel** | `[rapport] uitzonderingen`, vijfde `status`-waarde, `gwsw_run`-kolommen, JSON-blok; QGIS-stijl |
| 6 | **#125** GWSW 1.7-support | #135, helper#39 | Opus 4.8 | **Substantieel** | 1.7-fixtureset, versie-bewuste drifttests, rapportkop; **géén** `gh issue create` (#136 bestaat al) |
| 7 | **#131** stelselboom-leeslaag: `stelsels_van`, rol `stelsels` | — | Opus 4.8 | **Substantieel** | aansluiting op de leeslaag; alleen publieke helper-API (`stelsel_leden`, `subjects_of_class`) |
| 8 | **#129** VGS-voorwaarde NET-006 | #131 | Opus 4.8 | **Substantieel** | `checks/` + koppelmatrix in twee configs; declaratie NET-006 |

Eén issue = commit + push + CI groen + comment + close vóór het volgende.

## Bewijslast per issue (De Wolden en Hoogeveen, tegen `uitvoer/31082026_slotrun`)

| Issue | Wat de agent meet | Verwacht |
|---|---|---|
| #135 | volledige poort zonder `-x`; `pytest -m zwaar`; volle run | **147.706**, elke check gelijk; `GEBUNDELDE_VERSIES == ('1.6', '1.7')` |
| #130 | TOP-019/022/023 door de registry op `voorbeelden/koekangerveld/koekangerveld_orox.ttl` | TOP-022 7 → **2**, TOP-019 5 → **0**, TOP-023 0; `examined()` 29 → 2; notes melden 27 buiten scope |
| #133 | ATTR-019 op de volle export | **20.758** (= `putten`), systemisch (>80 %); HGT-012 blijft 20.756 / 0; totaal ≈ **168.464** |
| #134 | fixture-rapporten met `Maximaal aantal meldingen;1000` en `Lokale kwaliteitseisen uit bestand;<naam>` | voorbehoud in kop, `gwsw_run` en JSON; De Wolden/Koekangerveld: **nul** verschil |
| #132 | drie fixtures: één uitzondering, één dode, één met verschoven waarde | eigen telling in rapport/JSON/`gwsw_run`, niet in CSV; De Wolden: **nul** verschil (geen bestand) |
| #125 | 1.7-fixtureset + 1.6-regressie (182 fixtures) + end-to-end op een 1.7-dataset | 1.6-set intact; rapportkop noemt de versie; De Wolden: **nul** verschil, kopregel "1.6" |
| #131 | scratch-telling: stelselinstanties en knopen/strengen met ≥1 stelsel | getal in de comment; meldingen: **nul** verschil |
| #129 | NET-006 vóór/ná | **+24** (0 VGS-instanties in De Wolden) |

Elke andere check blijft gelijk aan de referentierun (na #133 en #129 verschoven met
precies de genoemde aantallen). Wijkt iets af: verklaar het in de issue-comment, verzin geen
nieuwe waarheid.

## Bijzonderheden per issue

- **#135.** Proefbump van 04-09 staat in het issue: 965 groen, 1 rood op de hernoemde
  bestandsnaam (`test_cli.py:1012`, `test_toetsrun.py:609/612`); de rest van de suite is toen
  **niet** gezien, dus draai zonder `-x`. Naam afleiden uit `gebundelde_ontologie().name`,
  niet hardcoden. Wijkt de volle run af van 147.706: **stoppen en melden** — een
  leeslaagverschil los je niet hier op (harde techniekregel).
- **#130.** Graaf en `telbare_hulpstukken` blijven ongemoeid (BO-72/83). De drie definities
  (≥1 mechanisch én 0 vrijverval; los hulpstuk blijft in scope; mechanische benen tellen mee
  bij gemengd) zijn besluiten, geen aannames. `rollen` van TOP-019/022/023 uitbreiden, anders
  valt de AST-sweep.
- **#133.** De BRUTIS-tweedeling (conversiegat vs. leeg in de bron) komt **niet** in de code
  of `checks.toml`; alleen in de sluitcomment en de run-README. `HoogtePut = 0` blijft aan
  HGT-012. De "n van de m zonder afleidbaar bodemniveau"-regels van HGT-004/012/015/016
  blijven staan.
- **#134.** Bijvangst (1) en (4) zijn docs-regels binnen dit issue (`docs/architectuur.md`
  SHACL-kolommen; register regel 5 → drie CFK's, BO-7). Bijvangst (2) en (3) worden **niet**
  gebouwd. Niet in CSV.
- **#132.** Eén ingreeppunt in `melding.py` naast `Onderdrukking`. Stringgelijkheid op
  `waarde`, geen tolerantie. Status `geaccepteerd` krijgt een eigen grijstint, onderscheiden
  van `grijs`; kies hem in de stijlmodule en leg de keuze in de comment vast. Lijsten in het
  rapport volledig, niet afgekapt. `SCHEMA_VERSIE` blijft 1.2 (additief).
- **#125.** De versie in de rapportkop komt uit de publieke property
  `GwswDataset.gwsw_versie` (`basis`, `versie`, `gedetecteerd`) die helper#39 levert; `_basis`
  en `graph.gwsw_basis` zijn verboden terrein (harde techniekregel). Ontbreekt de property
  in de gepinde release, dan is dát de bevinding: comment, issue open laten, niet eromheen
  bouwen. Taak 6 verwijst naar #136; er wordt **geen** issue aangemaakt.
- **#131.** Geen consumer. Tuple, geen `str | None`: een streng kan in een `Rioolstelsel` én
  het omvattende `Transportstelsel` zitten. Cache-voorvoegsel registreren in `base.py`.
- **#129.** Pas na #131 (native dependency). VGS = alleen expliciete
  `VerbeterdGescheidenStelsel`-instanties — BO-nieuw; de impliciete
  gepaarde-rioleringsgebied-variant is verworpen (GWSW is leidend).

## De lus per issue

Precies het sjabloon (`docs/agents/afk-regie.md`, "De lus per issue N"):

- Brief aan elke implementer bevat letterlijk: *"Lees `docs/architectuur.md` en
  `docs/agents/analyse-harness.md` één keer volledig vóór je begint, en daarna elk bestand
  dat je aanraakt één keer volledig; geen `cd`; draai de poort en elke meetrun op de
  voorgrond en plak de uitvoer; niet pushen."* Taaklabel "Task N" in het Engels. Geef de
  implementer het issuenummer en de regel "kop 6 (Aannames) is je tweede bron; een afwijking
  leg je vast in je rapport, niet in een vraag".
- Vertrouw de geplakte poort van de implementer; draai hem niet nog eens.
  `scripts/runnerpoort.py` één keer, vlak vóór de push, nooit parallel aan een pytest.
- Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels
  raakte.
- Voor de zeven Substantiële issues: verse **Opus 4.8**-reviewer (`opus48`) via
  `superpowers:requesting-code-review`, adversarieel, met de vraag erbij: *"welke meting in
  het rapport bewijst het verwachte getal, en klopt die?"* Bij #134, #132 en #125 ook:
  *"is de JSON-wijziging additief en blijft elke bestaande lezer werken?"*
- Comment pas na het reviewoordeel; dan `gh issue close`. In de comment: het gemeten getal
  naast de verwachting uit de tabel hierboven.
- Push: `timeout 45 git push`; CI selecteren op `gh run list --commit <sha>`, dan
  `gh run watch <id> --exit-status`. Rood → fixen, niet door naar het volgende issue.
- Na een dispatch of een achtergrondcommando: niets doen tot de melding komt.
- De enige `gh`-schrijfacties zijn `edit --add-assignee`, `comment` en `close`. Geen
  `gh issue create`.

## Slotstap

1. Volledige gemeentebrede run op de eindstand van `dev`, met **dezelfde vlaggen** als
   `docs/checks-audit-2026-08.md:20` (drie `--shacl`, `--projectconfig
   configs/dewoldenhoogeveen.toml`, `--bronnen data/gis_dewoldenhoogeveen`), naar
   `uitvoer/<datum>_slotrun`, als `run_in_background` (4,5–5,5 min, ~4 GB).
2. Vergelijk per check met `uitvoer/31082026_slotrun/bevindingen.csv`; verwacht: elke check
   gelijk behalve ATTR-019 (**+20.758**, nieuw) en NET-006 (**+24**); totaal **168.488**.
   Elk ander verschil is een regressie van deze reeks — zoek de oorzaak.
3. Open de GeoPackage niet zelf; de PyQGIS-test (`tests/test_uitvoer_qgis.py`, lokaal) en de
   waardegelijkheidstest (#114) zijn het bewijs. Voor #132 hoort daar een stijltest bij voor
   de vijfde status.
4. Slotrapport in `uitvoer/<datum>_slotrun/_slotrapport.md` én als laatste bericht: per issue
   wat er landde, gemeten naast verwacht, BO-nummers, open gebleven punten, de uitgestelde
   minors uit de reviews. Noem #136 als "wacht op de auteur (1.7-SHACL-CSV)".
5. Laat `dev` schoon achter: alles gecommit en gepusht, CI groen, geen half bewerkt bestand.

## Harde grenzen

- Nooit `main`; geen uitgave; geen `scripts/uitgave.py`.
- Contractwijzigingen alleen zoals de issues ze beschrijven (additief; `SCHEMA_VERSIE`
  blijft 1.2). Vindt een implementer dat een issue méér vraagt, dan is dat een fout in het
  issue: comment, issue open laten, door naar het volgende dat er niet op leunt.
- Geen wijziging aan `gwsw-orox-helpers` of aan zijn internals (#135, #125, #131).
- Overschrijf nooit invoerbestanden; alleen `uitvoer/` schrijft; versienummer alleen in
  `pyproject.toml`. Bij twijfel over domeinlogica: GWSW is leidend, de issue-sectie
  **Aannames** is de tweede bron, een comment de derde; nooit een vraag aan de auteur.
