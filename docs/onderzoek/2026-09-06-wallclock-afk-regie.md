# Wall-clock hefbomen voor een agent-gestuurde issue-regie (2026-09-06)

**Vraag:** welke hefbomen versnellen de wall-clock tijd van een agent-gestuurde regie die een
reeks GitHub-issues afhandelt? Gemeten in sessie C (06-09): 25–45 min per Klein-issue,
45–75 min per Substantieel-issue met fixronde. Machine: 4 kernen, 16 GB, Linux, repo
`mcolee/nlriochecker` (publiek).

Gelezen vóór het onderzoek: `CLAUDE.md`, `.github/workflows/toets.yml`, `pyproject.toml`,
`scripts/runnerpoort.py`, `docs/agents/afk-regie.md`. Al ingevoerd volgens die documenten:
CI-wacht overlapt met de volgende dispatch, `runnerpoort.py` alleen bij datatests, kortere
leesfase bij kleine issues, twee implementers in eigen worktrees, concurrency+cancel-in-progress
in de workflow, `setup-uv` met cache aan, inerte-diff-review overslaan, geen re-review bij een
één-bevinding-fix.

## 1. Lokale poort

### 1.1 pytest-xdist (`-n auto`)
**Bron:** pytest-xdist docs, distributiemodi — "pytest-xdist will use as many processes as
your computer has physical CPU cores" (<https://pytest-xdist.readthedocs.io/en/stable/distribution.html>);
pytest-cov's xdist-pagina toont `pytest --cov=myproj -n 2 tests/` als voorbeeld dat de dekking
van alle workers combineert (<https://pytest-cov.readthedocs.io/en/latest/xdist.html>).
**Verwachte winst:** de poort draait `pytest -m 'not zwaar'` (≈2400 tests, ≈90 s). Op 4 kernen
kan `-n auto` dat richting 30–45 s brengen. De poort draait meerdere keren per issue
(implementer, evt. fixronde, evt. `runnerpoort.py`), dus cumulatief 2–4 min/issue.
**Kosten/risico:** (a) nieuwe dependency — moet permissief zijn (pytest-xdist is MIT, voldoet)
en hoort in de beslislog (BO-3); (b) de pytest-cov-docs bevestigen het combineren van dekking
over workers, maar zeggen niets expliciet over `branch = true` — dat moet eerst lokaal
geverifieerd worden vóór het de CI-poort raakt, nooit meteen live; (c) de repo heeft een
gedeelde schijf-cache op `~/.cache/gwsw-orox-helpers` (`cli.py:571`); gelijktijdige workers die
daarin lezen/schrijven kunnen conflicteren — de cache-zware tests zitten al onder de marker
`zwaar` (buiten de standaardpoort), dus het risico voor de gewone poort is waarschijnlijk klein
maar niet geverifieerd; (d) 37 van de 74 testbestanden gebruiken `tmp_path` — isolatie is niet
overal aantoonbaar.
**Past bij CLAUDE.md:** mits. Voeg toe via `--with pytest-xdist` net als `pytest-cov` (BO-38-
precedent), niet in de dev-groep — dat houdt "afhankelijkheden minimaal" overeind. Eerst
lokaal verifiëren dat `--cov-fail-under=95` met `branch = true` nog correct optelt vóór het in
`toets.yml` of `runnerpoort.py` landt.

### 1.2 pytest-testmon en `--lf`/`--ff`
**Bron:** pytest-testmon README (tarpas/pytest-testmon op GitHub): selecteert tests op basis
van coverage-afhankelijkheden tussen vorige run en gewijzigde bestanden; vereist eerst een
volledige `--testmon`-run om een database op te bouwen. pytest's eigen cache-documentatie
(<https://docs.pytest.org/en/stable/how-to/cache.html>): `--lf` (last-failed) en `--ff`
(failed-first) zijn ingebouwd, geen extra dependency.
**Verwachte winst:** verwaarloosbaar op de wall-clock van de regie zelf, want de **volledige**
poort blijft verplicht vóór commit (CLAUDE.md, "de mechanische poort … draait bij elke commit").
`--lf`/`--ff` kunnen wel de *interne* TDD-lus van een implementer-subagent bekorten tijdens het
schrijven van code (seconden i.p.v. 90 s per tussentijdse run), vooral bij een Substantieel
issue met veel bestaande tests.
**Kosten/risico:** testmon voegt een dependency en een state-bestand (`.testmondata`) toe voor
een baat die alleen de interne TDD-lus raakt, niet de verplichte volle poort. `--lf`/`--ff`
kosten niets (ingebouwd), mits nooit gebruikt als vervanging van de volle poort.
**Past bij CLAUDE.md:** `--lf`/`--ff` ja, als instructie aan de implementer tijdens TDD (nooit
i.p.v. de volle poort). testmon nee/mits — alleen overwegen als een issue aantoonbaar
herhaaldelijk >5 min in de TDD-lus doorbrengt; nu niet aangetoond.

### 1.3 mypy-daemon (`dmypy`)
**Bron:** mypy-docs, mypy-daemon (<https://mypy.readthedocs.io/en/stable/mypy_daemon.html>):
"for large codebases, running mypy using the mypy daemon can be 10 or more times faster."
**Verwachte winst:** onbekend voor deze repo. `src/nlriochecker` is ≈27.000 regels; mypy's
eigen aandeel in de 90 s van de poort is nooit apart gemeten (die tijd wordt aan pytest
toegeschreven). mypy's incrementele cache (`.mypy_cache`, standaard aan) geeft al het grootste
deel van de versnelling zonder daemon; de daemon-belofte geldt vooral bij veel herhaalde,
interactieve runs.
**Kosten/risico:** een lang-levend daemonproces per implementer/worktree (twee gelijktijdige
worktrees = twee daemons met eigen caches); moet herstart worden na een merge-base-wijziging
(expliciete waarschuwing in de mypy-docs) — extra procesbeheer voor een ongemeten winst.
**Past bij CLAUDE.md:** nee, niet nu. Eerst `time uv run mypy` meten vóór dit overwegen
("geen configureerbaarheid die niet gevraagd is", Karpathy-regel 2).

### 1.4 ruff-snelheid
**Bron:** astral-sh/ruff, benchmarks (<https://github.com/astral-sh/ruff>): 150–200× sneller
dan flake8 op codebases van honderdduizenden regels; sub-seconde op de meeste projecten.
**Verwachte winst:** verwaarloosbaar. Op 27.000 regels is ruff nooit de bottleneck in de 90 s
poort.
**Kosten/risico:** geen.
**Past bij CLAUDE.md:** n.v.t. — geen hefboom hier, geen wijziging nodig.

## 2. CI (`.github/workflows/toets.yml`)

### 2.1 concurrency + cancel-in-progress
**Bron:** GitHub Actions docs, concurrency (<https://docs.github.com/en/actions/using-jobs/using-concurrency>).
**Status:** al aanwezig (`toets.yml:26-28`). De workflow documenteert zelf een resterend
dubbelvuur (push naar `dev` + open PR naar `main` vanaf `dev` geven verschillende
`github.ref`, dus verschillende concurrency-groepen die elkaar niet cancelen) als een bewust
geaccepteerd punt, geen bug. Een fix hiervoor zou complexiteit toevoegen voor CI-minuten, niet
voor de wall-clock van de regie (de regisseur wacht toch op de push-run, niet op de PR-run).
**Past bij CLAUDE.md:** n.v.t. — geen wijziging aanbevolen.

### 2.2 `astral-sh/setup-uv`-cache
**Bron:** setup-uv README (<https://github.com/astral-sh/setup-uv>): `enable-cache` cachet
geïnstalleerde dependencies op basis van `cache-dependency-glob` (standaard o.a.
`pyproject.toml`, `uv.lock`).
**Status:** al aan (`toets.yml:106`). De docs zelf relativeren de winst op GitHub-hosted
runners ("minimal benefit since they include pre-installed Python versions") — het grootste
deel van de winst (dependency-resolutie overslaan) is hier al geïncasseerd.
**Past bij CLAUDE.md:** n.v.t. — al gedaan.

### 2.3 pytest-xdist in CI
**Bron:** GitHub-docs, gehost-runners (<https://docs.github.com/en/actions/reference/runners/github-hosted-runners>):
`ubuntu-latest` geeft een publieke repo 4 vCPU/16 GB (geverifieerd: `mcolee/nlriochecker` is
PUBLIC via `gh repo view`).
**Verwachte winst:** de pytest-substap kan van dezelfde 4 vCPU's profiteren als lokaal (zie
1.1). De totale CI-run is ≈40 s tot enkele minuten (toets.yml's eigen meting, commentaar
regel 41); hoeveel daarvan pytest is, is niet apart gelogd, dus de exacte winst is niet
gekwantificeerd — vermoedelijk enkele tientallen seconden.
**Kosten/risico:** zelfde als 1.1 (coverage-combinatie eerst lokaal verifiëren). Bijvangst:
`scripts/runnerpoort.py` leest de pytest-regel automatisch uit `toets.yml` via regex, dus een
`-n auto`-toevoeging aan de CI-regel werkt vanzelf ook lokaal mee — geen aparte wijziging nodig
in `runnerpoort.py`.
**Past bij CLAUDE.md:** mits — zelfde voorwaarde als 1.1, en pas toepassen ná lokale
verificatie.

### 2.4 `paths`/`paths-ignore`-filters
**Bron:** GitHub-docs, workflow-triggers (<https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow>):
een workflow die door `paths-ignore` wordt overgeslagen laat vereiste status-checks
"Pending" staan, wat een PR naar een beschermde branch blokkeert.
**Status:** `toets.yml` gebruikt dit bewust niet (eigen commentaar, regel 20-24): Markdown is
hier testinvoer (drie drifttests lezen `.md`-bestanden), dus een filter zou de poort precies
uitzetten op commits waar de drifttests voor bestaan. De GitHub-bron bevestigt bovendien een
extra risico: met `main` GitHub-beschermd (PR verplicht, `enforce_admins`) zou een geskipte
workflow een PR blijvend blokkeren.
**Verwachte winst:** nul; verder toepassen zou schadelijk zijn.
**Past bij CLAUDE.md:** nee — bevestigt de bestaande keuze.

### 2.5 kosten van `--cov` in CI
**Bron:** pytest-cov/coverage.py-mechaniek (algemeen bekend, geen aparte primaire bron nodig
naast de repo's eigen meting: `branch = true` kost ≈1 procentpunt, CLAUDE.md).
**Verwachte winst:** geen hefboom — dekking is een Harde regel (dekkingsondergrens 95%,
verplicht), niet optioneel. De totale CI-tijd is al klein (≈40 s), dus er is weinig te winnen
en niets weg te laten.
**Past bij CLAUDE.md:** nee — dekkingsmeting is niet onderhandelbaar.

### 2.6 push+pull_request-dubbelvuur
**Bron:** zelfde concurrency-docs als 2.1: verschillende `github.ref` betekent verschillende
concurrency-groep, dus geen automatische annulering tussen een push-run en een PR-run op
dezelfde commit.
**Status:** al benoemd en geaccepteerd in het workflow-commentaar zelf (regel 12-16).
**Verwachte winst:** een fix zou CI-minuten besparen, niet de wall-clock van de regie — de
regisseur volgt toch de push-run via `gh run list --commit`.
**Past bij CLAUDE.md:** n.v.t. voor deze vraag (wall-clock van de regie).

## 3. Claude Code-mechaniek

### 3.1 Subagent-worktrees voor parallelle implementers
**Bron:** Claude Code docs, worktrees (<https://code.claude.com/docs/en/worktrees>) en de
vergelijkingspagina "Run agents in parallel" (<https://code.claude.com/docs/en/agents>).
Bevestigd: een subagent met `isolation: worktree` krijgt een eigen checkout, opgeruimd zodra
hij geen wijzigingen achterlaat; permissie-goedkeuringen en project-scope plugins worden wél
gedeeld met de main checkout.
**Status:** al toegepast (twee implementers, elk een eigen worktree, `docs/agents/afk-regie.md`).
**Kosten/risico:** de prompt-cache is per werkdirectory gescoped (zie 3.2) — "that includes
worktrees of the same repository" — dus twee worktrees bouwen élk hun eigen cache op. De
dubbele leesfase (architectuur.md, analyse-harness.md) per implementer is dus onvermijdelijk
bij twee worktrees, geen los op te lossen probleem.
**Past bij CLAUDE.md:** ja, al vastgelegd (CLAUDE.md, Naslag-punt 4). Het onderzoek bevestigt
dat de mechaniek klopt met de officiële documentatie; geen verdere winst zonder eigen
resource-metingen (CLAUDE.md's "nooit meer dan twee" is een lokale resourcegrens, geen
Claude Code-limiet).

### 3.2 Prompt caching — welke acties een dure, trage beurt veroorzaken
**Bron:** Claude Code docs, prompt caching (<https://code.claude.com/docs/en/prompt-caching>).
Cache-brekende acties: model wisselen (`/model`), effort-niveau wijzigen, MCP-server
aan/uitzetten (tenzij tools deferred blijven), een deny-regel op een hele tool toevoegen,
compacten (`/compact`), veel afbeeldingen opstapelen, Claude Code zelf upgraden. Cache-veilige
acties: bestanden lezen/wijzigen, CLAUDE.md midden-sessie aanpassen (laadt pas na
clear/compact/restart), permissiemodus wisselen, skills/commands aanroepen, `/rewind`.
Subagenten krijgen een eigen 5-minuten-TTL-cache (tenzij expliciet op 1 uur gezet).
**Verwachte winst:** niet gekwantificeerd door Anthropic voor dit scenario, maar elke
cache-miss herleest de volledige contextprefix (CLAUDE.md + architectuur.md + eerdere
tool-resultaten) op de dure, ongecachte snelheid. Concreet advies voor de regie: wissel geen
model/effort binnen de implementeer- of fixfase van hetzelfde issue.
**Kosten/risico:** geen — dit is gratis (geen tooling, alleen dispatch-discipline).
**Past bij CLAUDE.md:** ja — kleine toevoeging aan de implementer-brief in `afk-regie.md`.

### 3.3 SendMessage-resume versus een verse fix-agent
**Bron:** Claude Code docs, prompt caching, sectie "Subagents and the cache"
(<https://code.claude.com/docs/en/prompt-caching>) en sub-agents-documentatie
(<https://code.claude.com/docs/en/sub-agents>). Feit: elke subagent bouwt zijn eigen cache op,
apart van de hoofdsessie en van andere subagents. Een resume via `SendMessage` hergebruikt de
eigen opgebouwde geschiedenis (en dus cache, binnen de TTL) van die subagent; een verse agent
begint bij nul en herleest architectuur.md/analyse-harness.md/de issue-body opnieuw als een
volle, ongecachte eerste beurt.
**Verwachte winst:** bij een fixronde op hetzelfde issue is `SendMessage`-resume van de
implementer die het net deed goedkoper dan een nieuwe fix-agent dispatchen: geen herhaald lezen
van de documentatie, geen her-uitleg van de context. Schatting: 1–3 min per fixronde, mits de
fixronde binnen enkele minuten na de vorige beurt start (anders is de cache toch koud en is het
verschil nihil).
**Kosten/risico:** de regisseur moet de agent-referentie bewaren; is de subagent-sessie
opgeschoond of te lang geleden actief, dan faalt resume alsnog en moet een verse agent starten
— geen technische blokkade, wel een procesdiscipline.
**Past bij CLAUDE.md:** ja, mits — pas de afk-regie-brief aan: bij een fixronde op hetzelfde
issue eerst `SendMessage` naar de bestaande implementer proberen, pas bij falen een nieuwe Task.

### 3.4 Achtergrondagents en niet pollen
**Bron:** Claude Code docs, "Run agents in parallel" en sub-agents-documentatie: een
achtergrond-subagent stuurt een voltooiingsmelding in een latere beurt; een vraag naar
voortgang vóór die melding levert een "nog bezig"-antwoord op, geen resultaat.
**Status:** bevestigt letterlijk de bestaande "Wachten"-regel in de globale CLAUDE.md (niet
pollen, geen `sleep`/`ListAgents`-lus). Geen nieuwe hefboom, wel een expliciete bevestiging dat
de huidige aanpak de door Anthropic bedoelde werkwijze is.
**Past bij CLAUDE.md:** n.v.t. — bevestiging, geen wijziging.

## 4. Proces

### 4.1 Batchen van kleine, gelijkvormige issues in één dispatch
**Bron:** intern (geen externe bron van toepassing); onderbouwd door de gemeten cijfers in
CLAUDE.md zelf (scoped reading bespaart ≈10 min/20-30% tokens per Klein-issue, sessie 06-09).
Claude Code's eigen `/batch`-commando (<https://code.claude.com/docs/en/agents>) splitst wél
werk over meerdere worktree-subagents, maar is ontworpen voor één grote wijziging in stukken
die elk een eigen PR openen — niet voor losse GitHub-issues die elk hun eigen close/comment
nodig hebben, dus niet direct herbruikbaar zonder "één issue = één sessie-eenheid" te breken.
**Verwachte winst:** bij 2–3 écht identiek gevormde issues (zelfde bestand, zelfde patroon,
bv. drie docstring-only fixes) kan één implementer-dispatch de leesfase en de poortrun één keer
i.p.v. N keer laten draaien: (N-1) × 3–5 min.
**Kosten/risico:** blijft binnen "één issue = één sessie-eenheid" zolang commit/comment/close
per issue apart blijven (alleen de dispatch en de poortrun worden gedeeld). Risico: een fix op
één van de N issues mag de andere niet meeslepen; scoping wordt lastiger.
**Past bij CLAUDE.md:** ja, mits — alleen bij aantoonbaar identiek gevormde issues, geen
`blocked by`, geen contract-issue (zelfde voorwaarden als de bestaande twee-implementers-regel),
met aparte commit/comment/close per issue.

### 4.2 Scoped review (inerte diff overslaan, geen overbodige re-review)
**Status:** al vastgelegd in `CLAUDE.md` en `afk-regie.md` na de sessiereview van 31-08
(≈10 van 18 reviews op inerte diffs was tokenverspilling; 6 van 6 re-reviews op 26-08
veranderden niets). Geen nieuwe stap hier te vinden.
**Past bij CLAUDE.md:** n.v.t. — al geïncasseerd.

### 4.3 Eén context-pakket in plaats van twee losse documenten
**Bron:** geen externe primaire bron voor dit specifieke idee; wel hetzelfde onderliggende
principe als Claude Code's eigen kostenadvies (<https://code.claude.com/docs/en/costs>): "keep
CLAUDE.md under 200 lines", verplaats gedetailleerde instructies naar skills die alleen laden
wanneer nodig.
**Verwachte winst:** klein — één samengevoegd bestand scheelt één Read-call in plaats van twee
en wat overbodige tekst; orde van tientallen seconden per dispatch, geen dramatische
wall-clock-winst.
**Kosten/risico:** een derde, afgeleide versie van architectuur.md en analyse-harness.md moet
synchroon blijven met de twee brondocumenten — onderhoudslast zonder aangetoonde noodzaak,
en botst met "geen abstractie die niet gevraagd is" (Karpathy-regel 2/3).
**Past bij CLAUDE.md:** nee, niet nu. De bestaande regel "Klein-issue leest alleen de relevante
secties" lost hetzelfde probleem al op zonder een derde bestand te onderhouden.

### 4.4 Checklist tegen fixrondes
**Bron:** intern, sessie C (06-09): drie gevonden fouten waren een popupregel zonder test,
"examined" geteld vóór in plaats van na deduplicatie, en een GeoJSON-invariant die niet
gespiegeld was in een andere uitvoervorm. CLAUDE.md citeert zelf dat reviews en fixrondes
"3 van 5 keer een echte fout" vingen — de fixronde is dus nu de facto de detectielaag.
**Verwachte winst:** een expliciete checklist met deze drie categorieën in de implementer-brief
(Task 1, `afk-regie.md`) kan een deel van die fouten vóór de review al laten vangen door de
implementer zelf. Eén voorkomen fixronde bespaart de review-tijd (5–10 min) plus een herhaalde
poort (90 s–3 min); bij zelfs 1 op de 3 fixrondes die hierdoor wegvalt: winst ≈5–10 min op dat
issue.
**Kosten/risico:** een te lange checklist wordt genegeerd (zelfde risico als een te lange
CLAUDE.md, per Claude Code's eigen kostenadvies) — hou hem tot de drie concrete regels: "nieuwe
UI/rapport-regel → test erbij", "tel ná deduplicatie, niet vóór", "een structuurwijziging in
de ene uitvoervorm controleren op spiegeling in de andere uitvoervormen".
**Past bij CLAUDE.md:** ja — een tekstuele toevoeging aan `afk-regie.md`, geen codewijziging,
dus geen poort nodig (docs/config-wijziging).

## Gerangschikte tabel

| # | Hefboom | Winst/issue | Inspanning | Past bij CLAUDE.md |
|---|---|---|---|---|
| 1 | 4.4 Checklist tegen fixrondes | ≈5–10 min (bij ⅓ van de issues) | laag (tekst in brief) | ja |
| 2 | 3.3 SendMessage-resume bij fixronde | ≈1–3 min | laag (procesregel) | ja, mits |
| 3 | 3.2 Prompt-caching-discipline (geen model/effort-wissel midden-issue) | niet gekwantificeerd, "gratis" | laag (procesregel) | ja |
| 4 | 1.1 pytest-xdist lokaal | ≈2–4 min | middel (nieuwe dependency + verificatie) | mits |
| 5 | 4.1 Batchen van identieke issues | (N-1)×3–5 min, smal toepasbaar | laag, smalle voorwaarde | ja, mits |
| 6 | 2.3 pytest-xdist in CI | enkele tientallen sec. | middel (afhankelijk van #4) | mits |
| 7 | 4.3 Eén context-pakket | tientallen sec. | middel (onderhoudslast) | nee |
| 8 | 1.2 pytest-testmon | 0 op de regie-wall-clock | middel | nee |
| 9 | 1.3 mypy-daemon | onbekend, vermoedelijk klein | middel | nee, eerst meten |
| 10 | 1.4 ruff-snelheid | verwaarloosbaar | n.v.t. | n.v.t. |
| — | 2.1/2.2 concurrency, setup-uv-cache | al geïncasseerd | — | n.v.t. |
| — | 2.4 paths-ignore | schadelijk | — | nee |
| — | 2.5 cov-kosten in CI | geen hefboom | — | nee |
| — | 2.6 push+PR-dubbelvuur | geen regie-impact | — | n.v.t. |
| — | 3.1 worktrees, 3.4 niet pollen | al toegepast/bevestigd | — | n.v.t. |
| — | 4.2 scoped review | al toegepast | — | n.v.t. |

## Aanbeveling (top 3)

1. **Checklist tegen fixrondes** (4.4) toevoegen aan `afk-regie.md` — gratis, docs-only,
   grootste verwachte winst per voorkomen fixronde.
2. **SendMessage-resume bij een fixronde** (3.3) i.p.v. een verse fix-agent dispatchen —
   gratis, alleen een procesregel in de brief.
3. **pytest-xdist lokaal** (1.1), maar pas nadat op een aparte worktree geverifieerd is dat
   `--cov-fail-under=95` met `branch = true` correct blijft optellen over de workers. Dit is de
   enige hefboom met echte, meetbare winst op de mechanische poort zelf; de eerste twee zijn
   grotis maar raken alleen de fixronde-frequentie en de agent-overhead.

Prompt-caching-discipline (3.2) is even gratis als de top-3 en verdient een plek in dezelfde
brief-update, ook al is de winst niet apart gekwantificeerd.
