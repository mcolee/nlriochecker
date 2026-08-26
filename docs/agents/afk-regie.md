# AFK-regie: een reeks issues fixen met Opus-agents (sjabloon)

Geef dit, met de issuelijst ingevuld, aan een **verse (gecleared) Fable-sessie** in
`/home/martin/nlriochecker`. Fable is de regisseur; het echte werk doen **Opus-subagents**
(`model: opus`; in deze harness levert dat Opus 5). De auteur is er niet bij — **unattended**.
De vorige invulling staat in `afk-regie-issues-72-77.md`; de meting van die run (26-08) is
de bron van de punten die hier zijn aangescherpt.

## Houding

- **Stel geen vragen aan de auteur.** De issues zijn volledige `ready-for-agent`-specs; ze zijn
  de bron. Twijfel je over een detail, volg de sectie **Aannames** in het issue en leg een
  afwijking vast als issue-comment — verzin geen domeinlogica (GWSW is leidend, `CLAUDE.md`).
- **"Klaar" pas als jíj het bewijs zag** — maar bewijs is de *geplakte* poort-uitvoer van de
  implementer plus je eigen `runnerpoort.py` vóór de push, niet een derde run (zie de lus).
- **Werk op `dev`, nooit op `main`.** Commit na elke groene stap.
- Lees vooraf één keer: `CLAUDE.md`, `docs/architectuur.md` (het deel dat het issue raakt) en
  `docs/agents/analyse-harness.md` (voor de metingen en de dataset-API).
- **Volg `CLAUDE.md` strikt.** Bij twijfel wint `CLAUDE.md` boven deze brief.
- **Gebruik de superpowers-skills expliciet.** Fable stuurt via `superpowers:executing-plans`
  en `superpowers:subagent-driven-development`; elke implementer draait
  `superpowers:test-driven-development` en `superpowers:verification-before-completion`;
  een bug los je op met `superpowers:systematic-debugging`; de review gaat via
  `superpowers:requesting-code-review`. Een agent die een skill negeert, doet het over.

## Volgorde — strikt sequentieel

Issues die bestanden delen doe je één voor één; noteer hier de volgorde en de
`blocked by`-relaties:

1. **#…** …
2. **#…** … — *blocked by #…*

Eén issue = één sessie-eenheid: commit + push + CI groen + comment + close vóór het volgende.

## De lus per issue N

1. **Lees** het issue volledig: `gh api repos/mcolee/nlriochecker/issues/N --jq .body` en
   `.../issues/N/comments` (`gh issue view` faalt op een GraphQL-deprecatie). Dat is de spec.
2. **Claim**: `gh issue edit N --add-assignee @me`.
3. **Dispatch een Opus-implementer** (Agent-tool, `model: opus`, verse agent,
   `subagent_type: general-purpose`). Brief, zelfstandig en met een taaklabel:

   > **Task 1 — implementeer issue #N.** Repo `/home/martin/nlriochecker`, tak `dev`. Volg de
   > body van #N verbatim en `CLAUDE.md` strikt (Harde regels + Werkwijze). Draai
   > `superpowers:test-driven-development` (eerst de falende test/fixture, dan de code) en
   > sluit af met `superpowers:verification-before-completion`. Concreet:
   > - **Lezen:** lees `docs/architectuur.md` en `docs/agents/analyse-harness.md` één keer
   >   volledig vóór je begint, en daarna elk bestand dat je aanraakt één keer volledig — niet
   >   per symbool in plakjes. Geen `cd`: de werkmap is al de repo-root.
   > - Maak de BO('s) die het issue noemt aan in `docs/beslislog.md`; het volgende nummer is
   >   `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1 (chronologisch onderaan).
   > - Regenereer elke generator die je raakt (`scripts/maak_ttl_fixtures.py`,
   >   `scripts/dekkingsmatrix.py`) en werk de checkdeclaratie (`rollen`/`kenmerken`) bij
   >   als de check anders selecteert/leest.
   > - Voeg een regel toe onder `## [Unreleased]` in `CHANGELOG.md`.
   > - Draai de **volledige mechanische poort op de voorgrond** en plak de uitvoer:
   >   `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`,
   >   `uv run pytest -m 'not zwaar'`.
   > - **Niet pushen.** Rapporteer terug: gewijzigde bestanden, poort-uitvoer, BO-nummer, het
   >   gemeten De Wolden-getal (zie **Meten**), en open aannames.

4. **Lees de geplakte poort.** Staat er een rode regel of ontbreekt een van de vier stappen,
   dispatch een fix-agent (Task 2). Is hij groen, dan **draai je hem niet nog eens**: in de run
   van 26-08 waren alle 12 herhalingen groen en kostten ze ~36 calls en ~1 uur pytest.
5. **Review** (Opus-reviewer, verse agent):
   - **Klein** → `/code-review` (medium).
   - **Substantieel** (kritiek pad, publiek contract, Harde regel) →
     `superpowers:requesting-code-review` met een verse Opus-reviewer: *"Task 3 — review de
     diff op `dev` sinds de laatste commit tegen de spec van #N en de Harde regels.
     Adversarieel: correctheid, dekt het de spec, kloppen de drifttests, breekt het een publiek
     contract (JSON-schema, CLI, GeoPackage-structuur)?"* Verwerk de uitkomsten met
     `superpowers:receiving-code-review`; Important-bevindingen gaan naar een fix-agent,
     minors naar de ledger.
   - **Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels
     raakte.** Een één-bevinding-fix controleer je zelf op de diff: op 26-08 veranderden 6 van
     6 re-reviews niets.
6. **Commit** op `dev`, boodschap eindigend op `(issue #N)`.
7. **Push, dan CI.** Eén keer, ná de laatste fixronde: `uv run python scripts/runnerpoort.py`
   (runner-conditie, strikte overslag, BO-48; draait alleen de CI-pytest-regel, nooit parallel
   aan een eigen pytest — runnerpoort zet `data/` tijdelijk weg). Dan `git push` en
   **`gh run watch --exit-status`** tot groen; dat bewijst de CI, een extra `gh run view` niet.
8. **Comment + close — pas na het reviewoordeel.** `gh issue comment N` met wat er landde en
   het **gemeten getal** naast de voorspelling (klopt de ordegrootte? zo niet, verklaar het —
   geen nieuwe waarheid verzinnen). Schrijf de comment niet vooraf om hem later te patchen:
   op 26-08 kostte dat 6 patches en één teruggenomen claim. Dan `gh issue close N`.
9. **Vastloper?** Poort niet groen of iets echt onbeslist → meld nooit "klaar": comment met
   de échte toestand, issue open laten, door naar het volgende issue dat er niet op leunt.

## Ledger

Houd één `progress.md` bij in de SDD-werkruimte, maar laat het achtergrondcommando zijn eigen
slotregel schrijven (`...; tail -3 poort.log >> progress.md`) in plaats van `cat log` plus
`echo >> progress.md` als twee losse calls (17 losse ledger-calls op 26-08). Kopieer de ledger
aan het eind naar de uitvoermap; **uitgestelde minors die de auteur moet zien, zet je in het
slotrapport** — de ledger is git-ignored en verdwijnt met de werkruimte.

## Meten

Noteer hier per issue het voorspelde De Wolden-getal; reproduceer het na afloop **door de echte
pijplijn** (`markeer_vulwaarden` vóór de checks; `docs/agents/analyse-harness.md`). Een
meetscript dat een getal onderbouwt commit je mee (BO-43).

## Wachten (uit `CLAUDE.md`)

Niet pollen. Een subagent en een `run_in_background`-commando **melden zich vanzelf** — geen
`sleep`, geen `ListAgents`-lus. Alleen `gh run watch` gebruikt een voorgrond-wacht.

## Slotstap — na alle issues

1. **Volledige gemeentebrede uitvoer** op de eindstand van `dev`, naar `uitvoer/<datum>_<naam>/`.
   Zwaar (~6 min) → `run_in_background`. Gebruik **dezelfde vlaggen als de baseline** waarmee je
   vergelijkt, inclusief `--bronnen data/gis_dewoldenhoogeveen` (zie
   `docs/agents/analyse-harness.md`, "Bestaande runs"); op 26-08 kostte een run zonder die
   vlag een tweede run van 6 minuten.
2. **Slotrapport aan de auteur.** Per issue wat er landde, gemeten getal naast voorspelling,
   toegevoegde BO's, open gebleven issues en waarom, de uitgestelde minors, en de kerncijfers
   van de gemeentebrede run tegenover de laatste baseline onder `uitvoer/`.

## Harde grenzen

- Nooit `main` aanraken of ernaartoe pushen. Dit is `dev`-werk; geen uitgave.
- Raakt een wijziging een Harde regel of een publiek contract, dan is de review **verplicht
  Substantieel**, ongeacht je inschatting.
- Overschrijf nooit invoerbestanden; één uitvoerschrijver (`uitvoer/`); versienummer alleen in
  `pyproject.toml`. Zie `CLAUDE.md`.
