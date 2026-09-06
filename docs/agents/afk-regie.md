# AFK-regie: een reeks issues fixen met subagents (sjabloon)

Geef dit, met de issuelijst ingevuld, aan een **verse (gecleared) Fable-sessie** in
`/home/martin/nlriochecker`. Fable is de regisseur; het echte werk doen **subagents**. Kies
per issue het model naar zwaarte volgens de globale `CLAUDE.md` (sectie **Modelkeuze
subagents**): substantieel/kritiek-pad → **Opus 4.8** via de `opus48`-agent (de kale alias
`model: opus` levert in deze harness Opus 5), klein/docs/config/test-only → **Sonnet**.
**Rapporteer bij elke dispatch expliciet welk model je inzet.** De auteur is er niet bij — **unattended**.
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
- **Auto-mode blokkeert een paar schrijfacties.** In een unattended run weigert de
  auto-mode-classifier `gh repo create` en `gh issue create` ("Blocked by classifier"), en soms
  de eerste agent-dispatch (die lukt bij herhaling). Op 26-08 kostte dat drie geweigerde calls
  plus een auteur-tussenkomst. Verwacht het: stage de body/args in een scratchbestand en laat de
  auteur de call als `! gh issue create …` draaien, of doe het buiten de regie om. Probeer na
  een classifier-blokkade geen variant van dezelfde schrijfactie (op 26-08 hielp een tweede,
  kleinere `gh repo create` niet): meld het één keer aan de auteur en wacht op het startsein.
  Een nieuwe
  publieke repo pushen struikelt bovendien over GH007 (privé-e-mail): zet eerst
  `git config user.email <id>+mcolee@users.noreply.github.com` en `git commit --amend --reset-author`
  (dat herschrijft de SHA, dus verifieer de historie opnieuw).
- **Volg `CLAUDE.md` strikt.** Bij twijfel wint `CLAUDE.md` boven deze brief.
- **Gebruik de superpowers-skills expliciet.** Fable stuurt via `superpowers:executing-plans`
  en `superpowers:subagent-driven-development`; elke implementer draait
  `superpowers:test-driven-development` en `superpowers:verification-before-completion`;
  een bug los je op met `superpowers:systematic-debugging`; de review gaat via
  `superpowers:requesting-code-review`. Een agent die een skill negeert, doet het over.

## Volgorde — strikt sequentieel, met één toegestane overlap

Issues die bestanden delen doe je één voor één; noteer hier de volgorde en de
`blocked by`-relaties.

**Twee implementers tegelijk mag** (auteursbesluit 06-09), elk in een eigen worktree via
`superpowers:using-git-worktrees`, onder vier voorwaarden: de twee issues delen geen
bestanden buiten `CHANGELOG.md` (dus ook niet `tests/golden/ledger.json` of de
fixture-generator); hooguit één van de twee doet een De Wolden-meting (4 cores, 16 GB:
twee pytest-runs kunnen, twee volle runs niet); geen `blocked by`-relatie tussen de twee;
en geen van beide is een contract-issue (die gaan één voor één door de Substantiële
review). De regisseur merget in de volgorde van de tabel en lost de `CHANGELOG.md`-botsing
zelf op; review, commit en CI blijven per issue. Elke worktree heeft een eigen `.venv`
(`uv sync`, ~1 min eenmalig). Meer dan twee tegelijk nooit.

1. **#…** …
2. **#…** … — *blocked by #…*

Eén issue = één sessie-eenheid: commit + push + CI groen + comment + close vóór het volgende.

## De lus per issue N

1. **Lees** het issue volledig: `gh api repos/mcolee/nlriochecker/issues/N --jq .body` en
   `.../issues/N/comments` (`gh issue view` faalt op een GraphQL-deprecatie). Dat is de spec.
2. **Claim**: `gh issue edit N --add-assignee @me`.
3. **Dispatch de implementer** — kies het model naar de zwaarte van #N (globale `CLAUDE.md`,
   **Modelkeuze subagents**): substantieel/kritiek-pad → Opus 4.8 via `subagent_type: opus48`;
   klein/test-/config-only → `model: sonnet`, `subagent_type: general-purpose`. **Meld
   expliciet welk model deze dispatch inzet.** Brief, zelfstandig en met een taaklabel:

   > **Task 1 — implementeer issue #N.** Repo `/home/martin/nlriochecker`, tak `dev`. Volg de
   > body van #N verbatim en `CLAUDE.md` strikt (Harde regels + Werkwijze). Draai
   > `superpowers:test-driven-development` (eerst de falende test/fixture, dan de code) en
   > sluit af met `superpowers:verification-before-completion`. Concreet:
   > - **Lezen:** lees `docs/architectuur.md` en `docs/agents/analyse-harness.md` één keer
   >   volledig vóór je begint, en daarna elk bestand dat je aanraakt één keer volledig — niet
   >   per symbool in plakjes. Geen `cd`: de werkmap is al de repo-root.
   >   (**Klein-issue op Sonnet:** van `docs/architectuur.md` alleen de sectie(s) die het
   >   issue raakt — noem ze in de brief — en `analyse-harness.md` alleen als het issue een
   >   meting of scratch-script vraagt; de volle leesfase kostte 3–5 min per dispatch.)
   > - Maak de BO('s) die het issue noemt aan in `docs/beslislog.md`; het volgende nummer is
   >   `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1 (chronologisch onderaan).
   > - Regenereer elke generator die je raakt (`scripts/maak_ttl_fixtures.py`,
   >   `scripts/dekkingsmatrix.py`) en werk de checkdeclaratie (`rollen`/`kenmerken`) bij
   >   als de check anders selecteert/leest.
   > - Voeg een regel toe onder `## [Unreleased]` in `CHANGELOG.md`.
   > - **Checklist vóór je "klaar" zegt** (de drie fouten die de reviews van sessie C vonden):
   >   (1) elke nieuwe of gewijzigde rapport-/popup-/terminalregel heeft een test die hem
   >   aantreft; (2) een telling (`examined`, totalen) telt ná de ontdubbeling en met dezelfde
   >   regel als de zusterchecks; (3) een invariant die je in één lezer of uitvoervorm invoert
   >   (GeoPackage/GeoJSON, tabel/terminal/JSON) spiegel je in de andere en test je daar ook.
   >   Vink de drie af in je rapport.
   > - Draai de **volledige mechanische poort op de voorgrond** en plak de uitvoer:
   >   `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`,
   >   `uv run --with pytest-xdist pytest -n 4 -m 'not zwaar'` (BO-94).
   > - **Niet pushen.** Schrijf het volledige rapport naar `<scratchpad>/task-N-report.md`
   >   en antwoord kort (≤ 15 regels): status, gewijzigde bestanden, de vier poortregels
   >   letterlijk, het gemeten De Wolden-getal (zie **Meten**), de checklist-vinkjes en open
   >   aannames. Geen proza-recap: alles wat je terugstuurt reist elke beurt van de regisseur
   >   opnieuw mee.

4. **Lees de geplakte poort.** Staat er een rode regel of ontbreekt een van de vier stappen,
   dan een fixronde (Task 2). Is hij groen, dan **draai je hem niet nog eens**: in de run
   van 26-08 waren alle 12 herhalingen groen en kostten ze ~36 calls en ~1 uur pytest.
   **Elke fixronde gaat via `SendMessage` naar de bestaande implementer**, niet via een verse
   agent: zijn context en prompt-cache staan nog (code.claude.com, prompt caching); een verse
   fix-agent leest de docs opnieuw (~12k tokens, 3–5 min). In de fixbrief: eerst `git status`
   en `git log -1` opnieuw draaien (de regisseur kan intussen gecommit hebben), en alleen
   binnen hetzelfde issue hervatten. Wissel binnen een issue nooit van model of effort:
   dat breekt de cache van de hoofdsessie. Geef een reviewer de diff altijd als bestand
   (`git diff -U10 > <scratchpad>/diff-N.txt`), nooit inline in de prompt.
5. **Review** (reviewer, verse agent — model naar risico, zie **Modelkeuze subagents**):
   - **Inerte diff eerst uitsluiten.** Raakt de diff alléén tests, docstrings, commentaar
     of config (geen codepad), dan is een volle code-/security-review verspilling: stel in
     één regel vast dat er geen codepad wijzigt en sla de review over (CLAUDE.md: *"geen
     volle review op een inerte diff"*; sessiereview 06-09: config-only diffs kregen toch
     een volle review). Raakt de diff wél code, ga verder:
   - **Klein** → `/code-review` (medium).
   - **Substantieel** (kritiek pad, publiek contract, Harde regel) →
     `superpowers:requesting-code-review` met een verse **Opus 4.8**-reviewer (`opus48`-agent): *"Task 3 — review de
     diff op `dev` sinds de laatste commit tegen de spec van #N en de Harde regels.
     Adversarieel: correctheid, dekt het de spec, kloppen de drifttests, breekt het een publiek
     contract (JSON-schema, CLI, GeoPackage-structuur)?"* Verwerk de uitkomsten met
     `superpowers:receiving-code-review`; Important-bevindingen gaan naar een fix-agent,
     minors naar de ledger.
   - **Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels
     raakte.** Een één-bevinding-fix controleer je zelf op de diff: op 26-08 veranderden 6 van
     6 re-reviews niets.
6. **Commit** op `dev`, boodschap eindigend op `(issue #N)`.
7. **Push, dan CI — overlappend met het volgende issue** (auteursbesluit 06-09, sessie C).
   - `uv run python scripts/runnerpoort.py` draai je **alleen als het issue tests toevoegt
     die echte data laden** (de CLAUDE.md-regel; runner-conditie, strikte overslag, BO-48;
     nooit parallel aan een eigen pytest — runnerpoort zet `data/` tijdelijk weg). Een
     issue zonder zulke tests slaat hem over: de geplakte poort is dan het bewijs.
   - `timeout 45 git push`, en **dispatch meteen de implementer van het volgende issue**:
     de commit staat, dus die kan aan de slag terwijl de CI loopt.
   - Dan pas `gh run watch --exit-status` (voorgrond-wacht, terwijl de implementer op de
     achtergrond werkt); dat bewijst de CI, een extra `gh run view` niet. Rood → fix-agent
     op het vorige issue vóór de volgende commit landt; de lopende implementer werkt door.
   - Meting 06-09: de CI-wacht (~5 min) en runnerpoort (~1,5 min) waren samen ~20 % van
     de tijd per issue.
8. **Comment + close — pas na het reviewoordeel én CI groen.** `gh issue comment N` met wat er landde en
   het **gemeten getal** naast de voorspelling (klopt de ordegrootte? zo niet, verklaar het —
   geen nieuwe waarheid verzinnen). Schrijf de comment niet vooraf om hem later te patchen:
   op 26-08 kostte dat 6 patches en één teruggenomen claim. Dan `gh issue close N`.
9. **Vastloper?** Poort niet groen of iets echt onbeslist → meld nooit "klaar": comment met
   de échte toestand, issue open laten, door naar het volgende issue dat er niet op leunt.

## Voortgang tonen — stavaza-tabel met emoticons

De auteur kijkt tussendoor mee (ook vanaf een ander apparaat) en leest alleen je laatste
bericht. Toon daarom **na elke stap van de lus** (dispatch, poort gelezen, review, commit,
CI, close) en **bij elke wisseling van issue** een korte stand-van-zaken-tabel, één rij per
issue van de sessie plus een rij voor de slotrun:

| Issue | Status | Model | Detail |
|---|---|---|---|
| #150 één telling per rapport | ✅ dicht | Opus 4.8 | adb7d9f, CI groen; 79/79/79 |
| #151 kaartpijl vlak-band | 🔍 review loopt | Opus 4.8 | poort groen; 557 → 0 |
| #152 TOP-009 / NaN-Inf | 📖 spec gelezen | Opus 4.8 | wacht op #151 |
| #153 … | ⏳ | Sonnet | |
| Slotrun C | ⏳ | — | tegen 06092026_slotrun_B |

Vaste emoticons: ⏳ nog niet begonnen · 📖 spec gelezen/geclaimd · 🔄 implementer loopt ·
🔍 review loopt · 🛠️ fixronde · ✅ dicht (CI groen) · ⚠️ open gebleven (comment gezet) ·
❌ vastgelopen. De kolom *Detail* draagt het gemeten getal naast het verwachte zodra het er
is, anders de laatste stap. Houd de tabel kort: geen proza eromheen, geen herhaling van wat
al vaststaat; vraagt de auteur "stavaza", dan is deze tabel het antwoord.

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
