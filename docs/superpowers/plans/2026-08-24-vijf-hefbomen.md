# Vijf hefbomen — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De vijf goedgekeurde 80/20-hefbomen uit de architectuur- en performanceanalyse van 2026-08-24 doorvoeren, plus de goedgekeurde JSON-compactie, met byte-/inhoudsgelijke uitvoer als harde poort per taak.

**Architecture:** Eerst vier architectuurtaken zonder verwacht uitvoereffect (config verplicht, runcontext naar de schrijvers, smalle graafinterface, importgraaf + drifttests), dan de checks-optimalisaties, dan de graafmotor (rdflib-store eruit), als laatste de JSON-compactie. Elke taak eindigt met de mechanische poort, een uitvoervergelijking tegen de referentierun en een commit op `dev`.

**Tech Stack:** Python 3.12, uv, pyoxigraph (parser), rdflib (terms), shapely ≥2 (STRtree), pytest.

**Spec:** het hefboomrapport (artifact "Vijf hefbomen", 2026-08-24) + de analyseresultaten in deze plantekst. Baseline: `dev` @ `508a6cc`.

## Global Constraints

- Werk op `dev`; nooit rechtstreeks op `main`.
- **Uitvoergelijkheid is de harde poort.** Referentie-uitvoer:
  `/tmp/claude-1000/-home-martin-nlriochecker/b86ea000-8195-4d43-8bc4-2487070c2558/scratchpad/perf/uit_koud/`
  (gedraaid op baseline `508a6cc`). Vergelijker:
  `python3 /tmp/claude-1000/-home-martin-nlriochecker/b86ea000-8195-4d43-8bc4-2487070c2558/scratchpad/vergelijk_uitvoer.py REF NIEUW`
  (exit 0 = gelijk; GPKG wordt op inhoud vergeleken, `last_change`/`update_time`/datums genormaliseerd). Vanaf Taak 7 met `--json-inhoud`.
  Wijkt de uitvoer af: NIET doorgaan, oorzaak melden aan de regisseur.
- **Verificatierun** (na elke taak; `<UIT>` = verse map onder de scratchmap):
  ```
  uv run nlriochecker toets \
    --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
    --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
    --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
    --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
    --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
    --studiegebied data/gis_dewoldenhoogeveen/CBS_buurten_DeWoldenHoogeveen_buffer_100m.gpkg \
    --projectconfig configs/dewoldenhoogeveen.toml \
    --output <UIT>
  ```
  (zonder `--geen-cache`; wijzigt een taak `dataset.py`/`geometry.py`/`ontologie.py`, dan verandert de cachesleutel vanzelf en is de run koud — dat is bedoeld gedrag).
- **Mechanische poort per commit:** `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest` — alles groen vóór de commit.
- Geen nieuwe afhankelijkheden. Geen nieuwe drempels of gedragsopties.
- `uitvoer/herkomst.py` blijft de enige bestandsschrijver in `src/` (sweep in `tests/test_uitvoer_herkomst.py`).
- Elke taak: één regel onder `## [Unreleased]` in `CHANGELOG.md`, in de stijl van de bestaande regels (Nederlands, imperatief).
- Deterministische volgorde bewaren: geen `set`-iteratie die een uitvoervolgorde bepaalt; bestaande insertievolgordes respecteren.

---

### Taak 1: `CheckRun.config` verplicht

**Files:**
- Modify: `src/nlriochecker/checks/base.py:206-208`
- Modify: `src/nlriochecker/uitvoer/melding.py:96`, `uitvoer/omvang.py:50,187`, `uitvoer/synthese.py:59`, `uitvoer/gpkg.py:478,1063,1347`, `uitvoer/bevindingen.py:680,873`
- Test: `tests/test_uitvoer_klassentelling.py:97` (fixture), bestaande suites

**Interfaces:**
- Produces: `CheckRun.config: CheckConfig` (niet meer optioneel). Elke consument gebruikt `run.config` rechtstreeks.

- [ ] **Stap 1:** In `checks/base.py` het veld `config: CheckConfig | None = None` wijzigen naar `config: CheckConfig`, met een docstringregel naar het model van `meetbereik` (base.py:216-221): een ontbrekende config zou elke schrijver dwingen stil een eigen `checks.toml` te lezen.
- [ ] **Stap 2:** De 9 fallback-sites vervangen door directe toegang (`config = run.config`; bij `bevindingen.py:680,873` de `if run.config`-tak weghalen). De `load_check_config`-imports die daardoor ongebruikt raken verwijderen (alleen die).
- [ ] **Stap 3:** `tests/test_uitvoer_klassentelling.py:97` een expliciete config meegeven: `config=load_check_config()` (import bovenaan het testbestand).
- [ ] **Stap 4:** Poort draaien; verwacht groen. `grep -rn "load_check_config" src/nlriochecker/uitvoer/` moet 0 treffers geven.
- [ ] **Stap 5:** Verificatierun + vergelijker; verwacht `UITVOER GELIJK`.
- [ ] **Stap 6:** CHANGELOG-regel + commit: `Maak CheckRun.config verplicht en schrap de stille configherlezing in de uitvoerlaag`.

---

### Taak 2: De runcontext naar de schrijvers; afvoerpad niet meer herberekend

**Files:**
- Modify: `src/nlriochecker/checks/base.py` (veld `context` op `CheckRun`, vulling in `run_checks` rond base.py:546)
- Modify: `src/nlriochecker/checks/verbanden.py` (ontvangt `Afvoer`, `afvoerpad_van_streng`, `afvoerpaden` uit `checks/netwerk.py:151-205`)
- Modify: `src/nlriochecker/checks/netwerk.py` (importeert de drie voortaan uit `verbanden`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py:40,420-424,484` en `uitvoer/synthese.py:113`
- Test: `tests/test_uitvoer_gpkg.py`, `tests/test_uitvoer_synthese.py`, `tests/test_checks_netwerk.py`

**Interfaces:**
- Produces: `CheckRun.context: CheckContext` — exact de context waarmee de checks draaiden. Schrijvers bouwen **geen** eigen `CheckContext` meer.
- Produces: `verbanden.Afvoer`, `verbanden.afvoerpad_van_streng(context, ...)`, `verbanden.afvoerpaden(context)` — zelfde signaturen als nu in `netwerk.py`; resultaat blijft via `context.cached` gedeeld, dus de GPKG-fase hergebruikt wat de NET-checks al berekenden.

- [ ] **Stap 1:** Veld `context: CheckContext` aan `CheckRun` toevoegen; `run_checks` vult het met de context die hij al heeft.
- [ ] **Stap 2:** `Afvoer`/`afvoerpad_van_streng`/`afvoerpaden` verplaatsen naar `verbanden.py` (letterlijk, inclusief docstrings en hun `context.cached`-sleutels ongewijzigd); `netwerk.py` importeert ze vandaar. Geen her-export vanuit `netwerk` naar buiten toe laten bestaan als niets hem meer gebruikt.
- [ ] **Stap 3:** `gpkg.py`: de import op regel 40 en de twee zelfgebouwde contexten (424, 484) vervangen door `run.context`; `mechanischeleidingen(run.context)` idem. `synthese.py:113` idem. De docstring op gpkg.py:420-423 ("Deze laag heeft geen CheckContext van de run") vervangen door de nieuwe werkelijkheid.
- [ ] **Stap 3b:** `CheckOutcome` (base.py:174-191) de velden `id_sleutels: tuple[str, ...]` en `volledig_bereik: bool` geven, gevuld in `run_checks` (base.py:515-526) uit de checkklasse — net als `title`/`severity`/`skeleton` nu. De twee registry-joins in de uitvoer vervangen: `uitvoer/melding.py:283-286` en `uitvoer/bevindingen.py:672-686` lezen voortaan van de outcome; de `REGISTRY`/`CHECK_REGISTRY`-imports daar weg (het `KeyError`-pad op bevindingen.py:684 verdwijnt daarmee).
- [ ] **Stap 4:** Poort draaien. `grep -rn "CheckContext(" src/nlriochecker/uitvoer/` moet 0 treffers geven; `grep -rn "from nlriochecker.checks.netwerk" src/nlriochecker/uitvoer/` idem; `grep -rn "REGISTRY" src/nlriochecker/uitvoer/melding.py src/nlriochecker/uitvoer/bevindingen.py` idem.
- [ ] **Stap 5:** Verificatierun + vergelijker. **Let op:** wijkt de GPKG af, dan betekende de oude eigen context een écht ander afvoerpad (kaart≠bevinding, een bestaande bug). Niet zelf kiezen: stoppen en aan de regisseur melden met het verschil.
- [ ] **Stap 6:** CHANGELOG-regel + commit: `Geef de runcontext aan de schrijvers en verhuis de afvoerpadberekening naar checks/verbanden`.

---

### Taak 3: Smalle graafinterface voor de checks

**Files:**
- Modify: `src/nlriochecker/dataset.py` (nieuwe methoden op `GwswDataset`, deel C rond regel 305-631)
- Modify: `src/nlriochecker/checks/topologie.py:120-127`, `checks/netwerk.py:69-70,666,962-963,972-973,1053-1054`, `checks/administratief.py:262,337,453`, `checks/randvoorzieningen.py:115,133-149,618`, `uitvoer/omvang.py:61`, `uitvoer/gpkg.py:927`
- Test: `tests/test_dataset.py` (nieuwe methoden), bestaande checksuites

**Interfaces:**
- Produces op `GwswDataset`:
  - `onderdelen(self, uri: str, wortel: str | None = None) -> list[str]` — neerwaartse `hasPart`-wandeling (tegenhanger van `klim_naar_knoop`), optioneel gefilterd op `graph_is_a(deel, wortel)`; volgorde = graafvolgorde van `parts_of`, ongewijzigd.
  - `onderdeel_label(self, uri: str) -> str | None` — `rdfs:label` van een willekeurig subject (ook niet-`Node`/`Conduit`).
  - `onderdeel_aspecten(self, uri: str) -> list[Aspect]` — de aspectlezing die `randvoorzieningen.py:137` nu via de private `_read_aspects` doet.
- Consumes: `verbanden.verbonden_knopen(context, conduit)` (bestaat al, verbanden.py:19-26).

- [ ] **Stap 1 (TDD):** In `tests/test_dataset.py` drie tests op een bestaande TTL-fixture: `onderdelen` vindt de delen van een put (en filtert op wortel), `onderdeel_label` leest een label, `onderdeel_aspecten` geeft dezelfde aspecten als de huidige private lezing. Draaien: rood (methoden bestaan niet).
- [ ] **Stap 2:** De drie methoden implementeren als dunne wrappers om `parts_of`/`graph.value`/`_read_aspects` binnen `dataset.py` — de graaf blijft binnen de module. Tests groen.
- [ ] **Stap 3:** De aanroepsites omzetten: de zes losse `resolve_network_node`-paren → `verbonden_knopen`; de `parts_of`/`URIRef`/`_read_aspects`/`graph.value`-sites in `administratief`/`randvoorzieningen`/`netwerk` → de nieuwe methoden. `URIRef`- en `parts_of`-imports die daardoor ongebruikt raken verwijderen.
- [ ] **Stap 4:** Poort draaien. Meting: `grep -rn "dataset\.graph\b\|\.graph\." src/nlriochecker/checks/ | grep -v graph_is_a | grep -v graph_types_of` — doel ≤4 treffers (de resterende gevallen zijn voor Taak 6); `grep -rn "_read_aspects" src/nlriochecker/checks/` = 0.
- [ ] **Stap 5:** Verificatierun (koud — `dataset.py` wijzigde, nieuwe cachesleutel) + vergelijker; verwacht `UITVOER GELIJK`.
- [ ] **Stap 6:** CHANGELOG-regel + commit: `Geef de checks een onderdelen-API op GwswDataset en dwing verbonden_knopen af`.

---

### Taak 4: `uitvoer/__init__.py` leegmaken + Melding-drifttests

**Files:**
- Create: `src/nlriochecker/uitvoer/schrijver.py` (orkestratie uit `__init__.py:20-241`: `Uitvoer`, `UitvoerPerGebied`, `schrijf_uitvoer`, `schrijf_uitvoer_gebieden`, `_schrijf_totaal`)
- Modify: `src/nlriochecker/uitvoer/__init__.py` (alleen docstring over), `toetsrun.py:40`, de 8 testimports (`test_toetsloop.py:27`, `test_uitvoer_voorbehoud.py:23`, `test_voortgang.py:19`, `test_uitvoer_rapportopbouw.py:21`, `test_uitvoer_herkomst.py:46`, `test_uitvoer_nulmeting.py:24`, `test_integration.py:26`)
- Modify: `src/nlriochecker/nulbevinding.py:264`, `uitvoer/melding.py:94,159,220` (functie-lokale imports naar top-level)
- Test: nieuwe drifttests naast `tests/test_uitvoer_herkomst.py:346`

**Interfaces:**
- Produces: `nlriochecker.uitvoer.schrijver.schrijf_uitvoer` / `.schrijf_uitvoer_gebieden` — zelfde signaturen als nu in `__init__`.

- [ ] **Stap 1 (TDD):** Twee drifttests schrijven naar het model van de JSON-drifttest (`test_uitvoer_herkomst.py:346`): elk veld uit `dataclasses.fields(Melding)` moet voorkomen in `bevindingen.CSV_KOLOMMEN` én in `gpkg.MELDING_KOLOMMEN` (via de bestaande veld→kolom-afbeelding; is die impliciet, leg hem dan als expliciete dict naast de kolomlijst). Draaien: verwacht direct groen (de lijsten zijn nu compleet) — de test is het vangnet, noteer dat in de docstring.
- [ ] **Stap 2:** Orkestratie verplaatsen naar `schrijver.py`; `__init__.py` houdt uitsluitend de moduledocstring. De 9 importsites omzetten naar `from nlriochecker.uitvoer.schrijver import ...`.
- [ ] **Stap 3:** De vier functie-lokale imports (`nulbevinding.py:264`, `melding.py:94,159,220`) naar top-level; de commentaarregels over de importkring verwijderen (ze zijn niet meer waar).
- [ ] **Stap 4:** Poort draaien; daarnaast `uv run python -c "import nlriochecker.uitvoer.identiteit"` als rooktest dat de lichte module niet meer de hele stack laadt (te zien aan `python -X importtime`, geen `gpkg`/`toetsloop` in de keten).
- [ ] **Stap 5:** Verificatierun + vergelijker; verwacht `UITVOER GELIJK`.
- [ ] **Stap 6:** CHANGELOG-regel + commit: `Maak uitvoer/__init__ een naamruimte en borg de CSV- en GPKG-kolommen met drifttests`.

---

### Taak 5: Checks — ruimtelijke caches en memoisatie

**Files:**
- Modify: `src/nlriochecker/checks/topologie.py:74-87` (`nearest_node`), `:156-168` (`_buren`), `:180-248` (TOP-001/002/003)
- Modify: `src/nlriochecker/checks/meetkunde.py:30-35` (`endpoints`), `:118-121` (`overlap_length`)
- Modify: `src/nlriochecker/dataset.py:430,440` (`resolve_network_node`-memo), `checks/netwerk.py:620-626` (NET-007)
- Test: bestaande checksuites; geen nieuwe publieke interface

**Interfaces:**
- Consumes: `context.cached(sleutel, bouwer)` — de bestaande cachediscipline (base.py:124-140), voorvoegsels volgen de gedocumenteerde conventie.
- Produces: geen nieuwe publieke namen; alleen interne caches.

- [ ] **Stap 1:** `nearest_node`, `_buren` en `overlap_length` omzetten naar `STRtree.query(geom, predicate="dwithin", distance=tol)` in plaats van per aanroep `geom.buffer(tol)`. **Gedragsgrens:** `dwithin` is exact, `buffer(...).intersects` een 16-segments-benadering; wijkt de verificatierun af, dan `dwithin` als voorfilter houden en het oorspronkelijke bufferpredicaat alleen op de kandidaten toepassen (dat behoudt de oude uitkomst en wint alsnog het gros).
- [ ] **Stap 2:** Endpoints per conduit één keer bepalen bij het bouwen van `_Topologie` (nu 211.355 herberekeningen met verse `Point`-objecten); de snapping streng-einde→put één keer per context via `context.cached`, zodat TOP-001/002/003 dezelfde afbeelding delen.
- [ ] **Stap 3:** `resolve_network_node` memoïzeren met een instantie-dict `uri → uri` op `GwswDataset` (aanmaken in `__init__`; hij is leeg op het moment dat de cache pickle't, dus de cacheomvang verandert niet). NET-007 herschrijven op een vooraf gebouwde `component_van`-dict (zie `afbakening._componentstructuur` als voorbeeld): van O(componenten × strengen) naar O(N+C). **De meldingsvolgorde van NET-007 moet identiek blijven** — bouw de dict, maar loop de bestaande iteratievolgorde.
- [ ] **Stap 4:** Poort draaien.
- [ ] **Stap 5:** Verificatierun (koud, `dataset.py` wijzigde) + vergelijker; verwacht `UITVOER GELIJK`. Noteer de wall-time uit de CLI-voortgang (doel: checks-fase merkbaar korter; de eindmeting volgt na Taak 7).
- [ ] **Stap 6:** CHANGELOG-regel + commit: `Versnel de topologie- en netwerkchecks met STRtree-dwithin, gedeelde snapping en memoisatie`.

---

### Taak 6: Graafmotor — rdflib-store vervangen door eigen indexen

**Files:**
- Create: `src/nlriochecker/graaf.py` (de index + het leescontract)
- Modify: `src/nlriochecker/dataset.py` (lader deel E: `_parse`/`_naar_rdflib` rond 1058-1115; lezers `_read_nodes`/`_read_conduits`/`_read_aspects`/`_structural_diff`; grafhelpers deel D 633-841; `subjects_of_class` rond 584)
- Modify: `src/nlriochecker/cache.py:59-117` (`LuieGraaf`), overige graaflezers: `nulbevinding.py`, `uitvoer/stelsels.py`, `analysis.py:132`, restanten in `checks/`
- Test: `tests/test_dataset.py`, `tests/test_cache.py`; de `zwaar`-integratietests als eindcontrole

**Interfaces:**
- Produces: `graaf.GraafIndex` met **uitsluitend** de nu gebruikte leesbewerkingen (inventariseer eerst met grep welke `Graph`-methoden daadwerkelijk aangeroepen worden: verwacht `triples`, `objects`, `subjects`, `value`, `subject_objects`, membership). Intern twee dicts (s→p→[o], p→o→[s]) gevuld **in stream-volgorde** uit de pyoxigraph-parse; rdflib-termtypen blijven de munteenheid zodat aanroepende code en vergelijkingen niet veranderen.
- `GwswDataset.graph` wordt een `GraafIndex`; de buitenwereld merkt het verschil alleen aan het type.

- [ ] **Stap 0 (inventarisatie, verplicht vóór code):** `grep -rn "\.graph\." src/ | grep -v graph_is_a` en de interne lezers in `dataset.py` — de volledige lijst gebruikte `Graph`-bewerkingen vastleggen in de moduledocstring van `graaf.py`.
- [ ] **Stap 1 (TDD):** `tests/test_graaf.py`: bouw een `GraafIndex` uit een kleine triple-lijst en toets elk van de geïnventariseerde bewerkingen tegen het rdflib-antwoord op dezelfde triples, **inclusief volgorde**.
- [ ] **Stap 2:** `GraafIndex` implementeren; `_parse` vult hem rechtstreeks uit de pyoxigraph-stream (de `_naar_rdflib`-terms blijven, de `graph.addN`-store-vulling vervalt).
- [ ] **Stap 3:** De lezers omzetten (dataset-deel C/D, `nulbevinding`, `uitvoer/stelsels`, `analysis`, checks-restanten). `ontologie.py` blijft ongemoeid op rdflib (2,5 MB, seconden).
- [ ] **Stap 4:** De cache: meet éérst welke variant wint — (a) de `GraafIndex` picklen zoals nu de graaf, (b) niet picklen maar per warme run in ~10 s uit de stream herbouwen (parse is ~0 s). Kies op gemeten warme wall-time; `LuieGraaf` verdwijnt of verhuist mee. De cachesleutel verandert vanzelf (hash van `dataset.py`).
- [ ] **Stap 5:** Poort draaien, daarna óók `uv run pytest -m zwaar` (eenmalig; dit is de taak waarvoor die marker bestaat).
- [ ] **Stap 6:** Verificatie: koude run mét `/usr/bin/time -v` en warme run idem; vergelijker op beide. **Doelen: koud ≤135 s, warm ≤110 s, piek-RSS ≤2,5 GB, uitvoer gelijk.** Uitvoer ongelijk = stoppen en melden; doelen niet gehaald maar uitvoer gelijk = resultaat rapporteren, de regisseur beslist.
- [ ] **Stap 7:** CHANGELOG-regel + commit: `Vervang de rdflib-store door eigen graafindexen uit de pyoxigraph-stream`.

---

### Taak 7: JSON compact schrijven

**Files:**
- Modify: `src/nlriochecker/uitvoer/herkomst.py:172` (`schrijf_json`)
- Modify: `docs/json-schema.md` (regel over serialisatievorm, alleen als het document whitespace noemt)
- Test: bestaande JSON-tests (verwacht: geen die op indent toetst; zo wel, aanpassen met motivering)

- [ ] **Stap 1:** `json.dumps(..., indent=2)` → `json.dumps(..., separators=(",", ":"))`. Sortering en veldvolgorde ongewijzigd laten.
- [ ] **Stap 2:** Poort draaien; `docs/json-schema.md` nalezen op whitespace-beloften (het contract gaat over structuur, niet over opmaak — klopt dat niet, melden).
- [ ] **Stap 3:** Verificatierun + vergelijker **met `--json-inhoud`**; verwacht: MD/CSV/GPKG gelijk, JSON "geparste inhoud gelijk".
- [ ] **Stap 4:** CHANGELOG-regel (met de bewuste bytes-wijziging benoemd) + commit: `Schrijf bevindingen.json compact; de structuur en sortering veranderen niet`.

---

### Taak 8 (regisseur, hoofdsessie): eindmeting, review, PR, uitgave

- [ ] Eindmeting: koude + warme benchmark met `/usr/bin/time -v`, `uv run pytest` met duur, dekking via `uv run --with pytest-cov pytest --cov=nlriochecker` (≥95%). Alle meetlat-getallen naast de baseline zetten.
- [ ] Slotvergelijking van de uitvoer tegen de referentie (met `--json-inhoud`).
- [ ] Substantiële eindreview (verplicht vóór merge naar `main`), bevindingen verwerken, poort opnieuw.
- [ ] Rapport-artifact bijwerken met de na-cijfers; push `dev`; PR `dev` → `main`.
- [ ] Na de merge: op `main` `uv run python scripts/uitgave.py minor`; tag en commits pushen; `dev` weer gelijktrekken met `main`.
