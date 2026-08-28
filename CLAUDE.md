# Project: nlriochecker

## Doel
Python-package dat de datakwaliteit van vrijvervalriolering toetst in twee lagen:
1. Inlezen en analyseren van de GWSW-nulmeting, aangeleverd als SHACL-validatierapporten (apps.gwsw.nl/item_validate_shacl).
2. Eigen aanvullende checks conform het checkregister (data/checkregister-gwsw-nulmeting-v0_9.md) op de GWSW-dataset (OroX/TTL) en later externe bronnen.

We bouwen gefaseerd; implementeer nooit meer dan de actuele fase vraagt. Fase 1 en 2 (nulmeting inlezen, dekkinganalyse, trendvergelijking) en de kernset van fase 3 (TOP- en NET-checks) staan. Fase 4 is EXT: BGT, BAG, BRK en waterschapsdata uit data/gis_koekangerveld/ (Koekangerveld) en data/gis_dewoldenhoogeveen/ (het hele OroX-gebied).

## Gouden regels van Karpathy

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.
1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

    State your assumptions explicitly. If uncertain, ask.
    If multiple interpretations exist, present them - don't pick silently.
    If a simpler approach exists, say so. Push back when warranted.
    If something is unclear, stop. Name what's confusing. Ask.

2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

    No features beyond what was asked.
    No abstractions for single-use code.
    No "flexibility" or "configurability" that wasn't requested.
    No error handling for impossible scenarios.
    If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

    Don't "improve" adjacent code, comments, or formatting.
    Don't refactor things that aren't broken.
    Match existing style, even if you'd do it differently.
    If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

    Remove imports/variables/functions that YOUR changes made unused.
    Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.
4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

    "Add validation" → "Write tests for invalid inputs, then make them pass"
    "Fix the bug" → "Write a test that reproduces it, then make it pass"
    "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Communicatie met de auteur
- Schrijf kort en concreet. Herhaal niet wat al vaststaat en som geen opties op die je
  toch niet volgt. Een echte tweesprong benoem je wél (Gouden regel 1), maar geef er je
  aanbeveling bij in plaats van de keuze open te laten.
- Gebruik gewone woorden. Vermijd jargon en zelfbedachte termen; is een vakterm nodig,
  leg hem één keer uit.

## Harde regels
Nooit breken. Domeinregels komen uit het checkregister v0.9; de techniekregels bewaken de
uitvoer- en versie-integriteit. De mechaniek en achtergrond staan in
`docs/architectuur.md` — hier staan alleen de regels zelf.

### Domein
- **GWSW IS LEIDEND.** Dit is de eerste regel en hij overstemt alle andere bronnen. Bestaat
  een begrip in de GWSW-ontologie, dan bestaat het -- ongeacht wat de Leidraad Riolering, de
  RIONED Kennisbank, een NEN-norm of je eigen aanname zegt. Externe bronnen leveren
  uitsluitend bereiken, drempels en periodes; nooit de vraag WELKE begrippen bestaan.
  Afwijken mag alleen als de auteur dat expliciet en onderbouwd heeft gedaan, en dan staat
  de afwijking als BO-nummer in `docs/beslislog.md` -- niet als commentaar in een
  configbestand.
  Voordat je beweert dat een klasse of property niet bestaat, grep je de gebundelde
  ontologie. Haar pad geeft dit commando:
  `uv run python -c "from gwsw_orox_helpers.bronnen import gebundelde_ontologie as g; print(g())"`
  Let op inconsistent hoofdlettergebruik:
  een regex als `[A-Za-z]*Stelsel` mist `Vuilwaterstelsel` met kleine s. Scheid twee vragen
  die makkelijk door elkaar lopen: "bestaat de klasse in de ontologie" en "komen er
  instanties voor in deze dataset" hebben verschillende antwoorden en vragen om
  tegengestelde ingrepen -- een ontbrekende klasse is een gat in ons model, ontbrekende
  instanties zijn een gat in de aanlevering. Zie de correctie op issue #11
  (`Overnamepunt` en `VerbeterdGescheidenStelsel` bestaan wél; De Wolden levert er nul).
- **De GWSW-ontologie komt uit `gwsw-orox-helpers`.** De ontologie en de vocabulaire-index
  reizen als package-resource mee (`gwsw_orox_helpers.bronnen.gebundelde_ontologie()` en
  `vocabulaire_index_pad()`); ze staan niet meer in `data/` en er is hier geen generator
  meer voor. Welke GWSW-versie leidend is staat dáár, in de `CLAUDE.md` van die package --
  dit is niet de plek waar dat nummer opnieuw wordt opgeschreven. Upgraden loopt dus over
  een release van die package plus een `uv lock` hier; bouw geen automatische
  versiecontrole tegen data.gwsw.nl. `Mds` en `Hyd` komen alleen in een integratietest voor
  (uit `data/gwsw_ontologieen/`, niet getrackt) en dragen geen versienummer maar een
  conversiedatum van **20210920** -- jaren ouder dan het totaalmodel. Wees daarom
  voorzichtig met de uitspraak dat een klasse "alleen in de totaal-ontologie" zit: dat kan
  net zo goed ouderdom van de deelmodellen zijn als een modelleerkeuze. De index draagt
  naast `termen` en `subklasse_van` ook `aspecten_van` en `onderdelen_van` (per klasse de
  directe `hasAspect`/`hasPart`-doelen, beide richtingen gevouwen); daarop leunt de
  drifttest die elke checkdeclaratie (`rollen`, `kenmerken`) tegen de ontologie houdt
  (`tests/test_checkdeclaraties_ontologie.py`). De drifttests die index en ontologie aan
  elkaar en aan het versienummer binden (BO-32) draaien in de package-repo.
- **Elke check declareert `rollen` en `kenmerken`** (issue #64, BO-51). Een nieuwe of
  gewijzigde check moet zeggen over welke GWSW-populatie hij gaat (`rollen`, namen uit
  `selectie._ROLLEN`) en welke kenmerken hij leest (`kenmerken`, GWSW-namen, of
  `config:<pad>`/`*`); `register()` weigert een check zonder beide. Twee drifttests bewaken
  het: `test_declaratie_volgt_de_code` (AST-sweep) en `test_declaratie_past_bij_de_ontologie`.
  Verander je wat een check selecteert of leest, werk dan de declaratie bij -- de AST-sweep
  valt anders. De dekselchecks putdiepte/putbodem (HGT-012/015) toetsen op de rol
  `rioolputten` (`gwsw:Rioolput`), niet op elke `netwerkknoop`.
- Standaard wordt de dataset aan ALLE conformiteitsklassen (CFK's) getoetst: Hyd,
  MdsPlan EN MdsProj. Ontbreekt er een, dan faalt de pijplijn met een duidelijke
  foutmelding. Een deelset kan alleen via de expliciete CLI-optie `--cfk`; zonder die
  optie verandert er niets. De afwijking staat in het Markdown-rapport (een regel onder
  de herkomst), in `gwsw_run` van de GeoPackage (`cfk_set`, `volledig`) en in de
  JSON-envelop. NIET in de CSV: de CFK-set hoort bij de run en niet bij de melding, dus
  hij wordt geen kolom op elke rij. Gevolg dat je moet kennen: twee `bevindingen.csv`
  uit een volle en een deelrun zijn aan het bestand zelf niet te onderscheiden; lees ze
  naast het rapport of de JSON. Hetzelfde geldt voor de onderdrukking uit `[rapport]`
  (issue #65): een CSV met en zonder `onderdruk_klassen`/`onderdruk_checks` ziet er
  hetzelfde uit; de telling staat in het rapport, in `gwsw_run` en in de JSON. Een
  rapport voor een niet-gekozen CFK is een fout, geen stille overslag, en `vergelijk`
  weigert twee meetmomenten met ongelijke sets. Een `toets` zonder `--shacl` is een
  eigen toestand ("niet gemeten"), los van volledig en van deelset. De drie toestanden
  en hun markeringstekst komen uit `Meetbereik` in `meting.py`, nergens anders. De lijst
  staat in `checks.toml` en is daar verplicht -- geen default in Python. Zie BO-7 in de
  beslislog.
- Typeringspoort: de SHACL-meting benoemt via de vorm `CfkTypes_typ` welke KLASSEN binnen een CFK te globaal zijn (niet welke objecten). De instanties volgen uit de OroX-dataset. Zonder dataset is er wel een klassenlijst maar geen score; verzin er dan geen.
- Alle drempelwaarden (toleranties, min/max-waarden, bufferafstanden) zijn configureerbaar per project via een configbestand (TOML). Geen hardcoded drempels.
- Check-ID's uit het checkregister (TOP-001 enz.) zijn stabiel; vervallen ID's worden nooit hergebruikt.
- Ernstniveaus: F = fout, W = waarschuwing. Elke check heeft een dimensietag (Consistentie, Compleetheid, Plausibiliteit, Actualiteit, Traceerbaarheid, Precisie, Nauwkeurigheid, Compliance; de enum `Dimension` is de bron). In de SHACL-rapporten komt de ernst uit de kolom Severity: Violation = F, Warning = W.

### Techniek
- **Functionaliteit hier mag `gwsw-orox-helpers` niet breken.** Deze repo gebruikt de
  leeslaag uitsluitend via haar publieke API: geen monkeypatches of overrides op
  internals, geen afhankelijkheid van privégedrag, en geen wijziging hier die een
  bestaande aanroep van die package een andere betekenis geeft. Is er echt een
  leeslaagwijziging nodig, dan loopt die via een release van die package plus een
  `uv lock` hier — nooit via een omweg in deze repo.
- **`toets` draait nooit zonder klassenhierarchie, tenzij je dat expliciet vraagt.** De
  export draagt nul `rdfs:subClassOf` en typeert niets op wortelniveau (`Inspectieput`
  wel, `Put` niet), dus zonder hierarchie draaien de checks over een onvolledige selectie
  en draagt hun uitkomst geen oordeel, terwijl het rapport dat nergens zei. Er zijn drie
  toestanden, en ze zijn niet uitwisselbaar (`_ontologiekeuze` in `toetsrun.py` is de
  enige plek waar ze uit elkaar gehaald worden): `--ontologie <pad>` gaat voor -- wie een
  pad noemt wil precies die hierarchie; géén vlag geeft de gebundelde GWSW-ontologie uit
  `gwsw-orox-helpers`, en dat is de standaardweg; `--geen-ontologie` is de bewuste
  ontsnappingsvlag en levert een rapport dat het voorbehoud in de kop draagt en de eigen
  checks op `–` zet in plaats van op een vinkje. De testfixtures declareren hun eigen
  hierarchie inline: die draaien legitiem met `--geen-ontologie` en houden hun oordeel,
  want het voorbehoud hangt aan `GwswDataset.klassenhierarchie_bekend` en niet aan de
  vraag of er een ontologiebestand meekwam. Zie issue #33.
- **Eén uitvoerschrijver.** Alle vier uitvoervormen (Markdown, CSV, GeoPackage, JSON)
  komen uit dezelfde meldingenstroom (`uitvoer/melding.py`) en dragen hun herkomst uit
  `uitvoer/herkomst.py` -- de enige schrijver in `src/`. Roep nooit zelf `to_csv`,
  `write_text` of `json.dump` aan; `tests/test_uitvoer_herkomst.py` verbiedt een tweede
  schrijver. Overschrijf nooit invoerbestanden. Mechaniek, herkomstvelden, JSON-contract
  en het samengestelde voorbehoud: `docs/architectuur.md`.
- **De uitvoermap heet `uitvoer/`** en staat in `.gitignore` — met een leidende slash,
  anders sluit die regel ook `src/nlriochecker/uitvoer/` uit en verdwijnt de package
  stilzwijgend uit de repository (en uit het zicht van ruff).
- **Het versienummer staat alleen in `pyproject.toml`;** `__version__` leest het via
  `importlib.metadata` en `tests/test_versie.py` bewaakt dat de twee gelijk blijven.
  Schrijf het nummer nergens een tweede keer op. Uitbrengen doe je met
  `uv run python scripts/uitgave.py patch|minor|major`, dat bumpt, toetst, commit en
  `vX.Y.Z` tagt; pushen blijft handwerk. Zie `docs/versionering.md`.

## Werkwijze
- Maak expliciet gebruik van de superpowers en dev-skills skills.
- Python 3.12+, src-layout (src/nlriochecker/), pyproject.toml, beheer met uv.
- Afhankelijkheden minimaal houden: pandas, click, pydantic, rdflib, shapely, networkx,
  plus geopandas en rasterio voor de EXT-checks op de externe bronnen (`externedata.py`),
  en `gwsw-orox-helpers` (MIT) voor de leeslaag. Voeg er niets aan toe zonder noodzaak;
  een nieuwe dep moet permissief of EUPL-verenigbaar zijn (BO-3) en hoort in de beslislog.
- **De leeslaag is een eigen package.** Het inlezen van OroX/TTL, de graaf, de geometrie,
  de ontologie, de cache en het voortgangsprotocol leven in `gwsw-orox-helpers`
  (`gwsw_orox_helpers.dataset`, `.graaf`, `.geometry`, `.ontologie`, `.cache`,
  `.voortgang`, `.bronnen`), niet in `src/nlriochecker/`. Een wijziging daaraan is een
  release van die package plus een `uv lock` hier -- niet een patch in deze repo.
- De licentie is EUPL-1.2 (copyleft, en 'toegang tot de wezenlijke functionaliteit'
  telt als verspreiding). Nieuwe afhankelijkheden mogen permissief of EUPL-verenigbaar
  zijn; zie de Appendix van `LICENSE` en BO-3 in de beslislog.
- Tests met pytest. Fixtures: kleine uittreksels van de echte rapporten en handgeschreven TTL's met precies een ingebouwd defect. Integratietests op de volledige De Wolden-bestanden; de zwaarste staan onder de marker `zwaar` en draaien niet standaard mee (laden kost sinds de eigen graafindexen circa een halve minuut koud en de volledige toetsrun piekt onder de 2 GB; zie BO-41 en BO-42).
- Codekwaliteit: ruff (lint en format), mypy schoon over `src/nlriochecker`
  (`uv run mypy`; `scripts/` en `tests/` vallen er nog buiten), type hints overal,
  Nederlandse docstrings, Engelse code-identifiers. De poort staat in
  `.github/workflows/toets.yml` en in `scripts/uitgave.py`; die twee draaien dezelfde
  vijf stappen (ruff lint, ruff format, mypy, pytest en een dekkingsondergrens).
  De package levert `py.typed`, dus haar hints komen bij een importeur aan.
- **Testdekking meet je met `uv run --with pytest-cov pytest --cov=nlriochecker`.**
  `pytest-cov` staat bewust niet in de dev-groep (afhankelijkheden minimaal); `--with`
  lost hem per run op. Beide poorten dwingen een ondergrens van 95% af
  (`DEKKINGSONDERGRENS` in `scripts/uitgave.py`, gelijk in de CI; `--cov-fail-under`).
  Laatst gemeten: 97% mét `data/` (dev, 2026-08-23) en 96% in de CI-conditie zonder
  `data/` -- beide ruim boven de grens, dus 95% raakt normale schommeling niet maar wel
  een echte regressie. Alleen een totaalgrens; de per-module-cijfers blijven een
  observatie in de rondeverslagen. Zie BO-38.
- CLI-ingang: nlriochecker (via entry point), subcommands: analyseer, dekking, vergelijk, toets.
- Werk op `dev`, niet op `main`. Elke wijziging gaat naar `dev`; `main` draagt alleen
  uitgebrachte, getagde versies. Pas als de auteur zegt dat het een nieuwe versie is,
  merge je `dev` in `main` en draai je daar `scripts/uitgave.py` -- in die volgorde,
  want het script eist `main` (`TAKVOORWAARDE`) en breekt af op elke andere tak. Zet
  `dev` daarna weer gelijk aan `main`, anders mist hij de bumpcommit.
- Eén sessie = één issue, en het issue is de enige plek waar de voortgang staat. Eindig je
  een issue niet af, zet dan een comment met de echte toestand: wat gecommit is en wat de
  poort nog mist. Beweer nooit "klaar/gepusht" als het dat niet is, en laat geen half
  bewerkt bestand achter zonder die comment -- anders herontdekt de volgende sessie het gat
  (of doet werk over dat al gedaan was). Zie `docs/agents/issue-tracker.md`.
- Kleine stappen; na elke werkende stap een commit. De **mechanische poort** --
  `uv run ruff check` en `uv run ruff format`, `uv run mypy`, `uv run pytest` (zonder
  `zwaar`) -- draait bij elke commit die `src/**.py` raakt. Vóór een push die tests
  toevoegt die echte data laden: `uv run python scripts/runnerpoort.py` -- dezelfde poort
  in de conditie van de CI-runner (alleen getrackte `data/`, geen PyQGIS, strikte
  overslagbewaking). Kies daarbovenop de review
  naar het **risico** van de wijziging, niet naar de omvang:
  - **Docs/config** (geen `src/**.py`, bv. deze regel): geen poort en geen review, alleen
    de drifttests die de wijziging raakt (bv.
    `test_de_dekkingsondergrens_is_overal_hetzelfde_getal`, die deze CLAUDE.md aan de
    dekkingsgrens van de CI en de uitgavepoort bindt).
  - **Klein** (code buiten de kritieke paden, geen nieuwe feature): `/code-review` --
    `low` bij een triviale one-liner, anders `medium`.
  - **Substantieel** (een nieuwe check/feature, óf de wijziging raakt een kritiek pad:
    `checks/`, de aansluiting op de leeslaag uit `gwsw-orox-helpers`, de meldingenstroom
    `uitvoer/`, of de ontologie): `/superpowers:requesting-code-review`; verwerk de
    uitkomsten en draai de poort daarna opnieuw.
  - **Altijd Substantieel**, ongeacht je inschatting: vlak vóór een merge naar `main` of
    een uitgave, en bij elke wijziging aan een Harde regel of aan een publiek contract
    (JSON-schema, CLI-opties, GeoPackage-structuur).
  Pas na een groene gate committen, met een duidelijke boodschap.
- Elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in
  `CHANGELOG.md`. `scripts/uitgave.py` weigert een uitgave met een lege sectie.
- Bij twijfel over domeinlogica: raadpleeg eerst data/checkregister-gwsw-nulmeting-v0_9.md en de gebundelde ontologie uit `gwsw-orox-helpers`; verzin geen eigen interpretaties.
- Geloof onwaarschijnlijke uitkomsten niet. Duizenden bevindingen op een dataset wijzen meestal op een modelleerfout in de engine, niet op duizenden gebreken; zoek de oorzaak voordat je het cijfer rapporteert.
- Wat een check NIET heeft bekeken hoort in het rapport: objecten buiten de graaf, weggelaten bevindingen, ontbrekende typeringspoort. Stilte leest als "alles gecontroleerd".

## Naslag
- **`docs/architectuur.md`** draagt de geverifieerde feiten en de engine/uitvoer-interna.
  Lees het vóór je aan het betreffende deel werkt:
  - invoerbestanden lezen of parsen: SHACL-CSV-kolommen, OroX-grafmodel (knoop is een
    orientatie, niet zijn geometrie; `hasConnection` symmetrisch; via `hasPart` omhoog tot
    een put), studiegebied-validatie en de kern/schil-afbakening;
  - uitvoer schrijven: meldingenstroom, rapportstructuur, voorbehoud/markering, herkomst,
    JSON-contract;
  - GeoPackage/QGIS: objectlagen, `status` en popup, stijlen, EXT-lagen, brondekking;
  - cache en het voortgangsprotocol, en de PyQGIS-test.
- **`docs/agents/analyse-harness.md`** verzamelt de vaste feiten voor een De Wolden-analyse:
  de dataset-/config-/registry-API voor scratch-scripts, de verrassende maar correcte
  aantallen (ATTR-001 vrijverval-subset, HGT-012 nul `HoogtePut`), de gegenereerde bestanden
  die je nooit met de hand bewerkt, en het drempelrecept over vijf gekoppelde plekken. Lees
  het vóór je zelf een telling of een scratch-script tegen de dataset schrijft -- het
  bespaart de ~1,5-min/3-GB herlaadronde op een verkeerde gok.
- **`docs/agents/afk-regie.md`** is het sjabloon voor een onbewaakte regiesessie die een reeks
  issues met Opus-subagents afwerkt (lus per issue, één poort, review-timing, slotrun).
- Openstaand werk staat als GitHub-issue op `mcolee/nlriochecker`, niet hier. Lijst ze met
  `gh issue list`; zie `docs/agents/issue-tracker.md`. Hou die lijst de enige plek, zodat
  niemand een openstaand punt in twee toestanden aantreft.

## Agent skills

### Issuetracker

Issues leven als GitHub-issues op `mcolee/nlriochecker`, bediend met de `gh` CLI. Zie
`docs/agents/issue-tracker.md`.

### Triage-labels

De vijf standaardrollen; elke labelstring is gelijk aan de rolnaam. Zie
`docs/agents/triage-labels.md`.

### Domeindocumentatie

Single-context: `CONTEXT.md` in de root. `docs/adr/` bestaat niet en wordt niet leeg
aangemaakt; `/domain-modeling` legt de map aan zodra er een eerste besluit in landt.
Vastgelegde besluiten staan tot die tijd als BO-nummer in `docs/beslislog.md`. Zie
`docs/agents/domain.md`.
