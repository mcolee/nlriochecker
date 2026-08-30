# AFK-regie: issues #72–#77 fixen met Opus-agents

> **Uitgevoerd op 26-08 (alle zes gesloten).** Voor een volgende reeks gebruik je het sjabloon
> `afk-regie.md`; dat scherpt punt 4, 5, 7 en 8 aan op basis van de meting van deze run.

Geef dit aan een **verse (gecleared) Fable-sessie** in `/home/martin/nlriochecker`. Fable is
de regisseur; het echte werk doen **Opus-subagents**. De auteur is er niet bij — **unattended**.

> **Alle subagents draaien op Opus 4.8 (`claude-opus-4-8`).** Geef op elke Agent-aanroep
> `model: opus` en zorg dat dat Opus 4.8 oplevert (niet een andere Opus). Biedt de harness een
> fijnere selector, pin 4.8. Fable zelf blijft Fable.

## Houding

- **Stel geen vragen aan de auteur.** De issues zijn volledige `ready-for-agent`-specs; ze zijn
  de bron. Twijfel je over een detail, volg de sectie **Aannames** in het issue en leg een
  afwijking vast als issue-comment — verzin geen domeinlogica (GWSW is leidend, `CLAUDE.md`).
- **"Klaar" pas als jíj het bewijs zag.** Vertrouw nooit de "done" van een subagent: draai de
  poort zelf op de voorgrond en lees de uitvoer voor je verder gaat (`CLAUDE.md`, Voltooiing).
- **Werk op `dev`, nooit op `main`.** Commit na elke groene stap.
- Lees vooraf één keer: `CLAUDE.md`, `docs/architectuur.md` (het deel dat het issue raakt) en
  `docs/agents/analyse-harness.md` (voor de metingen en de dataset-API).
- **Volg `CLAUDE.md` strikt** — Harde regels, Werkwijze, review-timing, alles. Bij twijfel
  wint `CLAUDE.md` boven deze brief.
- **Gebruik de superpowers-skills expliciet.** Fable stuurt via `superpowers:executing-plans`
  en `superpowers:subagent-driven-development`; elke implementer draait
  `superpowers:test-driven-development` (test-first, conform Karpathy's Goal-Driven Execution)
  en `superpowers:verification-before-completion` vóór hij "klaar" meldt; een bug los je op met
  `superpowers:systematic-debugging`; de review gaat via `superpowers:requesting-code-review`.
  Een agent die een skill negeert, doet het over.

## Volgorde — strikt sequentieel

De issues delen bestanden (`gpkg.py`, `bevindingen.py`, `randvoorzieningen.py`), dus parallelle
worktrees zouden botsen. Doe ze één voor één:

1. **#72** Drukriolering traceerbaar (engine)
2. **#73** Pompunit uit `afvoer_eindpunt` — *blocked by #72; pas starten als #72 gemerged is*
3. **#74** Grijze pijlen op persleidingen (klein)
4. **#75** Vlakken herzien: stelsellaag weg + RVZ-006 per streng + netwerkvlak
5. **#76** Systematische bevindingen generiek
6. **#77** Scope/populatie labelen bij "bekeken"

Eén issue = één sessie-eenheid. Rond een issue helemaal af (commit + push + CI groen + comment +
close) vóór je aan het volgende begint.

## De lus per issue N

1. **Lees** het issue volledig: `gh issue view N --comments`. Dat is de spec.
2. **Claim**: `gh issue edit N --add-assignee @me`.
3. **Dispatch een Opus 4.8-implementer** (Agent-tool, `model: opus` → Opus 4.8, verse agent —
   `subagent_type: general-purpose`). Brief, zelfstandig en met een taaklabel:

   > **Task 1 — implementeer issue #N.** Repo `/home/martin/nlriochecker`, tak `dev`. Volg de
   > body van #N verbatim en `CLAUDE.md` strikt (Harde regels + Werkwijze). Draai
   > `superpowers:test-driven-development` (schrijf eerst de falende test/fixture, dan de code)
   > en sluit af met `superpowers:verification-before-completion`. Concreet:
   > - Maak de BO('s) die het issue noemt aan in `docs/beslislog.md`; het volgende nummer is
   >   `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1 (chronologisch onderaan).
   > - Regenereer elke generator die je raakt: `scripts/maak_ttl_fixtures.py` (fixtures),
   >   `scripts/dekkingsmatrix.py` (als het checkregister/dekking wijzigt),
   >   `scripts/maak_gwsw_index.py` (alleen als de ontologie wijzigt — hier niet). Werk de
   >   checkdeclaratie (`rollen`/`kenmerken`) bij als de check anders selecteert/leest, anders
   >   valt de AST-sweep (`tests/test_checkdeclaraties_ontologie.py`).
   > - Voeg een regel toe onder `## [Unreleased]` in `CHANGELOG.md`.
   > - Draai de **volledige mechanische poort** en plak de uitvoer: `uv run ruff check`,
   >   `uv run ruff format --check`, `uv run mypy`, `uv run pytest -m 'not zwaar'`.
   > - **Niet pushen.** Rapporteer terug: gewijzigde bestanden, poort-uitvoer, BO-nummer, het
   >   gemeten De Wolden-getal (zie **Meten**), en open aannames.

   De implementer verifieert op de voorgrond binnen z'n eigen run.
4. **Verifieer zelf.** Als de agent zich meldt, draai de poort nog eens op `dev`. Rood? Dispatch
   een fix-agent (Task 2) of fix inline; ga niet verder tot groen.
5. **Review** (Opus-reviewer, verse agent):
   - #74 is **Klein** → draai `/code-review` (medium).
   - Alle andere zijn **Substantieel** (kritiek pad en/of publiek contract) → gebruik
     `superpowers:requesting-code-review` met een verse **Opus 4.8**-reviewer: *"Task 3 — review
     de diff op `dev` sinds de laatste commit tegen de spec van #N en de Harde regels.
     Adversarieel: correctheid, dekt het de spec, kloppen de drifttests, breekt het een publiek
     contract (JSON-schema, CLI, GeoPackage-structuur)?"* Verwerk de uitkomsten met
     `superpowers:receiving-code-review`, voer ze terug naar een implementer-agent, draai de
     poort opnieuw.
6. **Commit** op `dev`, boodschap eindigend op `(issue #N)`.
7. **Push, dan CI.** Voegde je tests toe die echte data laden, draai eerst
   `uv run python scripts/runnerpoort.py` (runner-conditie, strikte overslag, BO-48). Dan
   `git push` en **`gh run watch`** tot groen — dat hoort bij "klaar" (BO-48). Geen `main`.
8. **Comment + close.** `gh issue comment N` met wat er landde en het **gemeten getal** naast de
   voorspelling uit het issue (klopt het ordegrootte? zo niet, verklaar het — geen nieuwe
   waarheid verzinnen). Dan `gh issue close N`.
9. **Vastloper?** Krijg je de poort niet groen of is iets echt onbeslist, meld nooit "klaar":
   zet een comment met de échte toestand (wat gecommit is, wat de poort mist), laat het issue
   open, en ga door naar het volgende issue dat niet op dit issue leunt.

## Meten

De zware issues voorspellen De Wolden-getallen die je na afloop moet reproduceren **door de
echte pijplijn** (`markeer_vulwaarden` vóór de checks; zie `docs/agents/analyse-harness.md`):

- **#72 + #73 samen**: NET-001 9062 → **8467**, Koekangerveld 24 → **7**.
- **#75**: RVZ-006 verspringt van 1 bevinding/deelstelsel naar per gemengde streng — meet het
  nieuwe aantal (baseline uit een recente run onder `uitvoer/`).
- **#77**: geen gedragsgetal, wel de scope-labels; jaartal-context 3/39 lokaal, 9063 putten
  gemeente-breed zonder Begindatum.

De onderbouwende scripts staan **untracked** onder `scripts/`
(`analyse_afvoer_pompunit.py`, `analyse_begindatum.py`); commit ze mee met #72 respectievelijk
#77 als onderbouwing (BO-43). Een run die materieel afwijkt vraagt om een verklaring.

## Wachten (uit `CLAUDE.md`)

Niet pollen. Een subagent en een `run_in_background`-commando **melden zich vanzelf** — geen
`sleep`, geen `ListAgents`-lus. Alleen `gh run watch` gebruikt een voorgrond-wacht. Dispatch je
een agent voor een scan, doe die scan dan niet ook zelf.

## Slotstap — na alle zes

Als #72–#77 gemerged zijn op `dev` en groen:

1. **Volledige gemeentebrede uitvoer.** Draai de hele `toets` op de eindstand van `dev`, over de
   hele gemeente (géén `--studiegebied`, alle CFK's), naar `uitvoer/26082026_godspeed/`. Zwaar
   (~6 min) → `run_in_background`; het meldt zich, niet pollen.

   ```
   uv run nlriochecker toets \
     --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
     --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
     --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
     --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
     --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
     --projectconfig configs/dewoldenhoogeveen.toml \
     --output uitvoer/26082026_godspeed
   ```

   Controleer daarna dat de map het rapport (`.md`), `bevindingen.csv`, `bevindingen.json` en de
   GeoPackage draagt, en dat de run zonder fout eindigde. `uitvoer/` is git-ignored — niet
   committen.

2. **Slotrapport aan de auteur.** Eén samenvatting: per issue (#72–#77) wat er landde, het
   gemeten getal naast de voorspelling, welke BO's zijn toegevoegd, welke issues eventueel open
   bleven en waarom, en de kerncijfers van de gemeentebrede run (o.a. NET-001, totaal aantal
   bevindingen) met een korte duiding tegenover de laatste baseline onder `uitvoer/`
   (bv. `volledig_24082026`). Geen "klaar" zonder dat de run gedraaid en gelezen is.

## Harde grenzen

- Nooit `main` aanraken of ernaartoe pushen. Dit is `dev`-werk; geen uitgave.
- Raakt een wijziging een Harde regel of een publiek contract, dan is de review **verplicht
  Substantieel**, ongeacht je inschatting.
- Overschrijf nooit invoerbestanden; één uitvoerschrijver (`uitvoer/`); versienummer alleen in
  `pyproject.toml`. Zie `CLAUDE.md`.
