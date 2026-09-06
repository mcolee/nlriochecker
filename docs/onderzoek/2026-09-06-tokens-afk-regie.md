# Token-hefbomen voor een agent-gestuurde issue-regie (2026-09-06)

**Vraag:** welke vijf hefbomen beperken het tokengebruik van een AFK-agent-regiesessie
(Fable-regisseur op `nlriochecker`) zonder verslechtering of regressie? Gemeten in sessie C
(06-09-2026): implementer 150–335k tokens (Opus 4.8), reviewer 70–170k, `/code-review medium`
70–90k, fixronde +30–70k bovenop bestaande context; totaal ~2,3 M voor vijf issues
(~460k/issue gemiddeld).

Gelezen vóór het onderzoek: `CLAUDE.md` (secties "Modelkeuze subagents" en "Mega-sessies
splitsen"), `docs/agents/afk-regie.md`. Al ingevoerd volgens die documenten: kortere leesfase
voor kleine issues, CI-overlap, worktrees, model naar zwaarte (Opus bij substantieel/kritiek
pad, Sonnet bij klein), geen re-review bij één bevinding, geen dubbele poort-run bij groen.

Onderzocht tegen primaire bronnen: de Claude API-docs over prompt caching en pricing
(platform.claude.com), de Claude Code-docs over subagents (code.claude.com), en de
Agent-tool-beschrijving van deze harness zelf (fork versus fresh subagent).

## 1. Hoofdsessie licht houden — korte agentrapporten, bestand i.p.v. antwoord

**Bron en mechanisme.** De Claude API stuurt bij elke beurt de **volledige voorgaande
geschiedenis** opnieuw mee; caching maakt dat goedkoper (cache-read = 0,1× de basisprijs) maar
niet gratis, en elke groei van de geschiedenis wordt bij élke volgende beurt opnieuw verwerkt
en betaald als cache-read (platform.claude.com/docs/en/build-with-claude/prompt-caching,
sectie "Usage Tracking": `cache_read_input_tokens` telt mee in het totaal per aanroep). Een
subagent retourneert bovendien **alleen een samenvatting**, niet het volledige transcript, naar
de hoofdsessie — het volledige transcript blijft apart opgeslagen
(`~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`,
code.claude.com/docs/en/sub-agents, sectie "What Returns to Main Session"). Wat er wél
terugkomt (de tekst die de regisseur laat zien en onthoudt) bepaalt dus rechtstreeks hoe zwaar
elke volgende beurt van de hoofdsessie is.
**Verwachte besparing.** `CLAUDE.md` citeert een eigen meting (31-08): een handvol
lange, multi-deliverable sessies was goed voor >50% van álle tool-calls in die review-ronde.
Voor een AFK-regie van vijf issues is de hoofdsessie de enige component die de hele sessie
meesleept; een `progress.md`/rapport-bestand i.p.v. proza in het antwoord, en een vast
rapportcontract ("status + commits + één regel detail" — al de stavaza-tabel in
`afk-regie.md`) kan het aandeel van de hoofdsessie in het totaal met een schatting van
20–40% van de hoofdsessie-tokens verminderen (aanname: geen harde meting voorhanden, want de
2,3 M is subagent-tokens, niet hoofdsessie-tokens — dat is precies het gat dat dit rapport
niet kan dichten zonder een aparte hoofdsessie-meting).
**Risico.** De auteur kijkt tussendoor mee vanaf een ander apparaat en leest alleen het
laatste bericht (`afk-regie.md`, "Voortgang tonen") — een te compact rapport kan een probleem
verbergen. Bewaking: het contract blijft "status + commits + één regel", niet "geen statusregel";
bij een vastloper (regel 9 van de lus) blijft de volledige toestand verplicht in de
issue-comment, niet in het antwoord aan de auteur.
**Past bij CLAUDE.md/AFK-routine.** Ja, rechtstreeks: dit is exact de sectie "Mega-sessies
splitsen" en de bestaande stavaza-tabel in `afk-regie.md`; geen nieuwe afspraak, wel een
scherpere naleving (rapporten naar bestand, geen proza-recap per stap).

## 2. Prompt caching bewust benutten: resume i.p.v. verse agent, diff als bestand

**Bron en mechanisme.** Cache-hits kosten 0,1× de basisprijs, een 5-minuten-cache-write 1,25×
en een 1-uur-write 2× (platform.claude.com/docs/en/about-claude/pricing, "Prompt caching").
De cache is **volgorde-gevoelig**: alles vóór het laatste stabiele blok blijft gecached zolang
er niets vóór dat blok verandert (zelfde bron, "What Invalidates Cache" /
prompt-caching-pagina, "Structuring for Maximum Cache Hits" — stabiele prefix eerst, dynamische
inhoud laatst). Een **resume** via `SendMessage` naar een bestaand agent-ID behoudt de volledige
conversatiegeschiedenis en dus de cache-opbouw; een **verse** `Agent`-aanroep begint met een
"fresh, isolated context window" dat de twee volle documenten en de dataset-context opnieuw
moet lezen (code.claude.com/docs/en/sub-agents, "Context Isolation": "Each subagent's initial
context contains… System prompt… Task message"; GitHub-issue #43265 van
`anthropics/claude-code` bevestigt dat `SendMessage` een voltooide agent laat hervatten "in
the background without a new Agent invocation"). Deze harnas-instantie documenteert het zelf
zo in de Agent-tool-beschrijving: "To continue a previously spawned agent, use SendMessage…
that resumes it with full context."
**Verwachte besparing.** De gemeten fixronde kost nu +30–70k bovenop de bestaande context —
dat getal impliceert al een resume-achtig patroon (anders zou een fixronde de volle
150–335k opnieuw kosten). De hefboom hier is smaller maar reëel: (1) het diff-bestand als
`file_path` doorgeven aan de reviewer i.p.v. de diff in de prompt plakken voorkomt dat de
diff-tekst twee keer door de conversatie reist (eenmaal in de dispatch-prompt, eenmaal als de
reviewer hem "leest" en erover redeneert) — geschatte besparing 2–5k tokens per review-dispatch
op een gemiddelde diff; (2) een stabiele volgorde in de implementer-brief (systeeminstructie en
statische secties eerst, issue-specifieke details en de diff-referentie laatst) houdt de
cache-prefix intact tussen een dispatch en een eventuele resume, en bespaart de 1,25×-schrijfkost
op een herhaalde write die anders bij een subtiele prompt-herordening opnieuw zou optreden.
**Risico.** Resume behoudt de vólledige eerdere context, dus er is geen informatieverlies —
het risico zit aan de andere kant: als de implementer hervat ná een externe wijziging (bv. de
regisseur heeft intussen iets anders op `dev` gecommit dat het issue raakt), werkt de agent
met een voorstelling van de repo die niet meer klopt. Bewaking: laat de implementer bij een
resume expliciet `git status`/`git log -1` opnieuw draaien vóór hij verdergaat, en resume alleen
binnen dezelfde issue-scope (nooit een implementer van issue N hervatten voor issue N+1).
**Past bij CLAUDE.md/AFK-routine.** Ja — `afk-regie.md` noemt `SendMessage`-resume al impliciet
("Task 2" fix-agent na een rode poort); dit maakt expliciet dat resume de standaard is voor élke
fixronde, en dat de diff altijd als bestand gaat (nooit inline), in lijn met de Agent-tool-notitie
in de systeemprompt van deze harness zelf ("hand over the exact command/diff").

## 3. Compact context-pakket per issue i.p.v. twee volle docs per verse agent

**Bron en mechanisme.** Elke subagent (behalve een fork) start met een **losstaand, geïsoleerd
context-venster**: hij ziet de gespreksgeschiedenis van de hoofdsessie niet, en ook niet welke
bestanden de hoofdsessie al gelezen heeft (code.claude.com/docs/en/sub-agents, "What Non-Fork
Subagents Inherit" / "What They DON'T Inherit": "Conversation history or previous tool
results"). Dat betekent dat `docs/architectuur.md` (groot) en `docs/agents/analyse-harness.md`
voor élke fresh agent in de keten opnieuw volledig gelezen worden: de implementer, de verse
reviewer, en — bij een fixronde zonder resume — de fix-agent. Vier fresh agents × twee volle
documenten is acht volle leesbeurten per issue.
**Verwachte besparing.** `afk-regie.md` noemt al een gedeeltelijke versie hiervan voor kleine
issues ("van `docs/architectuur.md` alleen de sectie(s) die het issue raakt… de volle leesfase
kostte 3–5 min per dispatch") — dat is een wall-clock-getal, geen tokengetal, maar de twee zijn
gekoppeld: minder gelezen tekst is minder input-tokens. Aanname: als `architectuur.md` en
`analyse-harness.md` samen in de orde van 15–30k tokens liggen (niet hier gemeten — verifieer met
`wc -w docs/architectuur.md docs/agents/analyse-harness.md` × ~1,3), en een issue-specifiek
pakket dat tot een derde terugbrengt, bespaart dat 10–20k tokens per leesbeurt × meerdere fresh
agents per issue = een schatting van 30–60k tokens per issue. Dat is een substantieel deel van
het verschil tussen de huidige 150–335k en een kleiner implementer-budget.
**Risico.** Het echte risico van deze hefboom: een curatie die te smal knipt, mist de ene
Harde-regel-paragraaf die net dit issue raakt (bv. de CFK-set-regel bij een uitvoer-issue) —
en `CLAUDE.md` is expliciet dat GWSW-domeinregels en Harde regels nooit stilzwijgend
overgeslagen mogen worden. Bewaking: genereer het pakket niet handmatig maar via een vaste,
issue-onafhankelijke sectie-lijst (bv. altijd de Harde-regels-kop plus de secties die de
issue-titel/gewijzigde bestanden raken, zoals `afk-regie.md` al doet voor kleine issues) en
laat het volledige document als fallback bereikbaar (de implementer mag het altijd zelf
opvragen als het pakket een vraag niet beantwoordt) — nooit vervangen door een samenvatting die
zelf al interpreteert.
**Past bij CLAUDE.md/AFK-routine.** Ja, dit is een generalisatie van een regel die er al
staat voor "Klein-issue op Sonnet"; de hefboom is die aanpak standaard te maken voor élke
fresh agent (ook Substantieel/Opus), niet alleen voor Sonnet-kleine issues.

## 4. Minder rondes: geen dubbele poort, geen overbodige re-review, batchen van kleine issues

**Bron en mechanisme.** Dit is geen externe-docs-hefboom maar een eigen-data-hefboom: `CLAUDE.md`
citeert de meting van 26-08 dat alle 12 herhalingen van de poort in die sessie groen waren en
~36 calls + ~1 uur pytest kostten, en dat 6 van 6 re-reviews na een één-bevinding-fix niets
veranderden. `afk-regie.md` heeft deze twee al als vaste regel ("draai je hem niet nog eens",
"Re-review alleen als de fixronde meer dan één bevinding… raakte"). De resterende hefboom is
**batchen van same-shape kleine issues**: één Sonnet-implementer-dispatch die twee of drie
losstaande, bestandsdisjuncte kleine issues in serie afhandelt binnen dezelfde subagent-context
bespaart de vaste overhead per dispatch (de systeem-brief, de leesfase van de docs, de
"Task N"-briefing) die anders N keer optreedt.
**Verwachte besparing.** Elke overgeslagen overbodige stap is 100% besparing op die stap: een
niet-herhaalde groene poort bespaart de volle poort-kosten (pytest-uitvoer als tool-resultaat
telt mee als input-tokens bij de volgende beurt); een niet-gedane re-review bespaart de volle
70–170k van een reviewer-dispatch. Batchen van bv. drie kleine issues in één dispatch bespaart
naar schatting 2× de vaste brief-/leesoverhead (aanname: 5–15k tokens aan brief+docs-overhead
per dispatch, dus 10–30k bespaard over drie issues samen).
**Risico.** Batchen van issues in één subagent-context vermindert de isolatie tussen issues:
een fout in issue A kan de agent's aanpak van issue B beïnvloeden (context-lek in de goede
richting én de foute). `afk-regie.md` staat al twee-tegelijk toe onder vier voorwaarden (geen
gedeelde bestanden buiten `CHANGELOG.md`, geen `blocked by`-relatie, geen contract-issue, hooguit
één meting); batchen-in-serie-binnen-één-dispatch is strenger dan dat en vereist dezelfde
voorwaarden plus: commit per issue apart (nooit één commit voor twee issues), en de poort
draait per issue, niet pas aan het eind — anders wordt een falende poort niet aan het juiste
issue toegeschreven.
**Past bij CLAUDE.md/AFK-routine.** Ja voor de twee al-bestaande regels (expliciet genoemd);
het batchen van kleine issues in serie is een uitbreiding die niet ingaat tegen "Eén sessie =
één issue" (dat gaat over de *sessie*, niet over de subagent-dispatch) maar wel de bestaande
grens van "twee tegelijk, nooit meer" in acht moet nemen — batchen-in-serie is dus een derde
issue er niet gelijktijdig maar wel binnen één dispatch bij zetten, wat een nieuwe afspraak is
en dus bevestiging van de auteur verdient vóór het standaardpraktijk wordt.

## 5. Modelkeuze scherper: Sonnet-implementer als norm, Opus gericht op redeneerwerk

**Bron en mechanisme.** De Anthropic-pricingpagina noemt dit letterlijk als
kostenoptimalisatie: "Choose Haiku for simple tasks, Sonnet for most production workloads, and
Opus for the most complex reasoning" (platform.claude.com/docs/en/about-claude/pricing,
"Cost optimization strategies"). De prijstabel op diezelfde pagina: Opus 4.8 kost $5/MTok
basis-input en $25/MTok output; Sonnet 5 kost $2/MTok basis-input en $10/MTok output — Opus is
2,5× zo duur per token op zowel input als output. `CLAUDE.md` heeft deze regel al
("Modelkeuze subagents"): Sonnet 5 is de default voor "normaal implementeren, single-file
edits"; Opus is voor "architectuur/ontwerp, subtiele bugdiagnose, security-review van échte
code-wijziging". De huidige praktijk in sessie C zet Opus 4.8 in als implementer voor "een
issue" in het algemeen, met Sonnet alleen bij expliciet "kleine issues" — dat is smaller dan
wat `CLAUDE.md` toestaat.
**Verwachte besparing.** Dit is primair een **kostenhefboom** (2,5× per token), niet in de
eerste plaats een **volumehefboom**: de pricing-bron zegt niets over of Opus voor gelijk werk
meer tokens genereert dan Sonnet, dus een claim dat dit het tokenaantal zelf verlaagt zou een
aanname zijn die de bron niet dekt. Voor "tokengebruik" in de zin van rekening/budget is de
besparing wel groot: een implementer die van Opus (150–335k tokens) naar Sonnet verschuift voor
issues die niet kritiek-pad zijn, bespaart 2,5× op zowel de input- als outputkosten van dat
budget, zonder dat het aantal tokens per se daalt. Voor mechanisch werk (transcript-digests,
poort-uitvoer samenvatten) is Haiku 4.5 goedkoper én — volgens dezelfde bron — bedoeld voor
"simple tasks"; `CLAUDE.md` noemt digest-leeswerk al als schoolvoorbeeld.
**Risico.** Dit is de hefboom met het duidelijkste kwaliteitsrisico: een Substantieel issue
(kritiek pad, publiek contract, Harde regel) op Sonnet kan een subtiele bug of een contractbreuk
missen die Opus wel had gevonden — precies het scenario dat `CLAUDE.md` beschrijft als "waar
een fout duur is". Bewaking: de verse Opus-reviewer blijft **altijd** Opus voor Substantieel
werk (asymmetrische opzet: goedkope generator, dure, onafhankelijke reviewer) — dit rapport
beveelt niet aan de reviewer te downgraden, alleen de implementer-keuze scherper tegen de
bestaande regel te toetsen. Nooit toepassen op een issue dat een Harde regel of een publiek
contract raakt (`CLAUDE.md`: daar is de review altijd Substantieel, ongeacht inschatting) — de
implementer-modelkeuze voor zúlke issues blijft Opus.
**Past bij CLAUDE.md/AFK-routine.** Ja, dit is geen nieuwe regel maar strikter toepassen van
een bestaande: de sectie "Modelkeuze subagents" staat er al; de hefboom is het criterium
("substantieel/kritiek pad" versus "normaal implementeren") consequenter te gebruiken dan sessie
C deed, niet het criterium veranderen.

## Samenvatting

| Hefboom | Geschatte besparing | Risico | Inspanning |
|---|---|---|---|
| 1. Hoofdsessie licht (korte rapporten, bestand i.p.v. antwoord) | Grootste aandeel over de hele sessie (CLAUDE.md-meting: >50% tokens in lange sessies), maar niet apart gemeten voor deze routine | Laag — auteur kan een probleem missen bij te compact rapport; bewaakt door vast contract | Laag — is al beleid, kwestie van striktere naleving |
| 2. Prompt caching: resume i.p.v. vers, diff als bestand | Matig — 2–5k/review-dispatch plus behoud van de al-gemeten 30–70k fixronde-besparing | Laag — resume verliest geen context; risico zit in stale repo-state, op te vangen met een `git status`-check | Laag — grotendeels al praktijk, expliciet maken |
| 3. Compact context-pakket per issue | Matig-hoog — geschat 30–60k/issue (aanname, niet gemeten) | Matig — te smal knippen mist een Harde regel; bewaakt met vaste sectie-lijst + volledig document als fallback | Matig — pakket-generatie moet gebouwd en onderhouden worden |
| 4. Minder rondes (geen dubbele poort/re-review, batchen) | Hoog per overgeslagen stap (100% van die stap: 70–170k voor een overbodige review) | Laag voor de twee bestaande regels; matig voor batchen (context-lek tussen issues) | Laag voor de bestaande regels; matig voor batchen (nieuwe afspraak, auteursgoedkeuring) |
| 5. Modelkeuze scherper (Sonnet-implementer als norm) | Hoog in kosten (2,5× per token), neutraal in tokenvolume | Hoog voor kritiek-pad-issues als de grens niet gerespecteerd wordt; bewaakt door Opus-reviewer altijd te behouden en Harde-regel-issues nooit te downgraden | Laag — bestaande regel, kwestie van consequenter toepassen |

**Eerste twee om in te voeren:** 1 (hoofdsessie licht) en 4 (minder rondes), omdat beide al
beleid zijn met eigen meetbewijs in `CLAUDE.md`/`afk-regie.md` — de hefboom is striktere
naleving, geen nieuwe afspraak, dus geen auteursgoedkeuring nodig en het laagste risico op
regressie. Hefboom 3 (compact context-pakket) is de beste kandidaat voor een volgende sessie
zodra er een eerste meting is van de werkelijke omvang van `architectuur.md` en
`analyse-harness.md` — die meting ontbreekt nog in dit onderzoek.

## Bronnen

- Prompt caching — <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>
- Pricing (model- en cache-tarieven, cost optimization strategies) —
  <https://platform.claude.com/docs/en/about-claude/pricing>
- Claude Code subagents (context-isolatie, wat wel/niet overerft, worktree-isolatie) —
  <https://code.claude.com/docs/en/sub-agents>
- `SendMessage`-resume behoudt volledige context (bevestiging vanuit de issue-tracker van
  `anthropics/claude-code`) —
  <https://github.com/anthropics/claude-code/issues/43265>
- Deze harness' eigen Agent-tool-beschrijving (fork deelt prompt-cache met de ouder; resume via
  `SendMessage` behoudt volledige context) — systeemprompt van deze sessie, geen publieke URL.
- `CLAUDE.md` (repo-root) — secties "Modelkeuze subagents", "Mega-sessies splitsen".
- `docs/agents/afk-regie.md` — de bestaande AFK-routine en haar eigen meetregels (26-08, 06-09).
