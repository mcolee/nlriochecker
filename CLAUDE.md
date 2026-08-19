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

## Domeinregels (hard, uit het checkregister v0.9)
- Standaard wordt de dataset aan ALLE conformiteitsklassen (CFK's) getoetst: Hyd,
  MdsPlan EN MdsProj. Ontbreekt er een, dan faalt de pijplijn met een duidelijke
  foutmelding. Een deelset kan alleen via de expliciete CLI-optie `--cfk`; zonder die
  optie verandert er niets. De afwijking staat in het Markdown-rapport (een regel onder
  de herkomst), in `gwsw_run` van de GeoPackage (`cfk_set`, `volledig`) en in de
  JSON-envelop. NIET in de CSV: de CFK-set hoort bij de run en niet bij de melding, dus
  hij wordt geen kolom op elke rij. Gevolg dat je moet kennen: twee `bevindingen.csv`
  uit een volle en een deelrun zijn aan het bestand zelf niet te onderscheiden; lees ze
  naast het rapport of de JSON. Een
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

## Feiten over de invoerbestanden (geverifieerd)

### SHACL-nulmetingrapporten (data/shacl_nulmeting/)
- CSV met puntkomma (;) als scheidingsteken, encoding utf-8.
- Kopblok van sleutel;waarde-paren met onder meer "SHACL-meting op basis CFK", "Gevalideerd RDF-bestand" en "Rapport 'conforms'". Daaronder de kolomkop; zoek die op de regel die met `Focus node` begint, niet op een vast regelnummer.
- Kolommen: Focus node;Source;Value;Severity;Message;Path;Detail-message;Detail-value
- `Focus node` is het URI-fragment uit de dataset en joint direct op de OroX-TTL. `Source` is de naam van de geschonden SHACL-vorm (bijvoorbeeld `LengteLeiding_val`). Uit `Detail-value` zijn `type=` en `label=` te halen; die ontbreken soms, en dan blijven ze leeg.
- Een regel per overtreding; er is geen aggregatiegewicht.

### OroX-dataset (data/gwsw_orox_ttl/)
- Turtle hoort utf-8 te zijn, maar de BrutIS-export van De Wolden bevat een handvol CP850-bytes in straatnamen. De lader valt terug op een instelbare codering en meldt dat expliciet; nooit stilzwijgend tekens vervangen.
- Een knoop is een object met een orientatie van het type `Knooppunt` (Putorientatie, Bouwwerkorientatie, Compartimentorientatie, Hulpstukorientatie, Aansluitpunt, Afvoerpunt en verder). Een verbinding is een orientatie van het type `Verbinding`. Herken ze daaraan, niet aan hun geometrie: een knooppunt mag geen punt hebben.
- `gwsw:hasConnection` is een owl:SymmetricProperty zonder inverse; lees beide schrijfrichtingen.
- De koppeling wijst naar de ORIENTATIE, niet naar het object, en kan naar een compartiment of hulpstuk wijzen; loop via hasPart omhoog tot een put.
- Klassen als Lozingspunt, Overnamepunt en UitlaatPunt zijn Knooppunt-subklassen en staan dus op de orientatie. Overnamepunt bestaat alleen in de totaal-ontologie, niet in de deelmodellen.
- Welke ontologie je laadt bepaalt de uitkomst; gebruik data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl. Zonder ontologie valt de lader terug op herkenning via geometrie en meldt het verschil.

### Studiegebied (data/gis_koekangerveld/, data/gis_dewoldenhoogeveen/)
- GeoPackage of GeoJSON, gelezen met stdlib sqlite3 plus shapely; geen extra afhankelijkheid. Moet in EPSG:28992 staan, net als de GWSW-coordinaten; herprojecteren doen we niet.
- Analyseer de kern plus een contextschil, rapporteer de kern. De schil is de
  samenhangende vrijvervalcomponent waar de kern in ligt plus een buffer om het gebied;
  precies zo groot dat NET-001 en NET-002 geen valse bevindingen geven. Zonder
  studiegebied draait alles op de volledige dataset. Meld altijd hoeveel bevindingen
  buiten het gebied vielen en hoe groot kern, schil en export zijn.
- Bevat het bestand meer dan een feature, dan rapporteert `toets` per feature: een submap
  per gebied (de gesaneerde `naam_gebied`) plus `totaal/` met de synthese en de unieke
  meldingen. Bij een enkele feature verandert er niets. De harde eis is equivalentie: de
  meldingen van een gebied zijn gelijk aan die van een losse run met alleen dat gebied.
  De loop staat in `toetsloop.py`, de gedeelde structuren in `afbakening.GedeeldeIndex`;
  wat wel en niet gedeeld mag worden staat in BO-12 van de beslislog.
- Validatie van het gebiedsbestand hoort in `studiegebied.py` en nergens anders: alleen
  Polygon en MultiPolygon (GeometryCollection wordt niet uitgepakt, overgeslagen typen
  worden gemeld), en vanaf twee features een verplichte, gevulde, unieke kolom
  `naam_gebied` waarvan de gesaneerde mapnamen niet botsen. Een GeoJSON zonder legacy
  `crs`-member wordt tegen de RD-grenzen uit `[drempels]` gehouden -- geen tweede plek
  met die waarden.
- Een object dat meerdere gebieden raakt telt in elk rakend gebied mee; er wordt niet
  ontdubbeld. `melding_id` mag daarom het gebied niet bevatten. Zie BO-11.

## Technische afspraken
- Maak expliciet gebruik van de superpowers en dev-skills skills
- Python 3.12+, src-layout (src/nlriochecker/), pyproject.toml, beheer met uv.
- Afhankelijkheden minimaal houden: pandas, click, pydantic, rdflib, shapely, networkx,
  plus geopandas en rasterio voor de EXT-checks op de externe bronnen (`externedata.py`).
  Voeg er niets aan toe zonder noodzaak; een nieuwe dep moet permissief of
  EUPL-verenigbaar zijn (BO-3) en hoort in de beslislog.
- Tests met pytest. Fixtures: kleine uittreksels van de echte rapporten en handgeschreven TTL's met precies een ingebouwd defect. Integratietests op de volledige De Wolden-bestanden; de zwaarste staan onder de marker `zwaar` en draaien niet standaard mee (laden kost ruim drie minuten en circa 3 GB).
- Codekwaliteit: ruff (lint en format), mypy schoon over `src/nlriochecker`
  (`uv run mypy`; `scripts/` en `tests/` vallen er nog buiten), type hints overal,
  Nederlandse docstrings, Engelse code-identifiers. De poort staat in
  `.github/workflows/toets.yml` en in `scripts/uitgave.py`; die twee draaien hetzelfde.
  De package levert `py.typed`, dus haar hints komen bij een importeur aan.
- CLI-ingang: nlriochecker (via entry point), subcommands: analyseer, dekking, vergelijk, toets.
- De SHACL-nulmeting is naast het checkregister een tweede bron in diezelfde
  meldingenstroom: `nulbevinding.py` maakt van elke overtreding een `Nulbevinding` met
  `bron = "nulmeting"`, categorie `NULMETING` en het veld `cfk`, en `bouw_meldingen`
  maakt er meldingen van. Geen `CheckOutcome`, geen tweede schrijver. De focusnode
  wordt via `hasPart`, `hasAspect` en als laatste `hasConnection` omhooggelopen tot een
  put of streng; komt hij nergens op uit, dan blijft de melding staan zonder object en
  met een leeg gebied, en het rapport telt die gevallen. Zie BO-28.
- Rapportage-output: Markdown, CSV, een GeoPackage en JSON naar een output-map; nooit
  invoerbestanden overschrijven. Alle vier komen uit dezelfde meldingenstroom
  (`uitvoer/melding.py`); een schrijver die zelf een `Finding` interpreteert laat ze uit
  elkaar lopen. `bevindingen.json` is een geversioneerd contract met een eigen
  `schema_versie`, los van het packagenummer; het staat beschreven in
  `docs/json-schema.md` en twee drifttests houden dat document aan `Melding` vast. Het
  veld `voorstel` is daarin gereserveerd voor een latere fase en wordt niet geschreven.
- Elk uitvoerbestand draagt zijn herkomst: pakketnaam plus versie, uit
  `uitvoer/herkomst.py`. Dat is de enige schrijver in `src/`: `schrijf_markdown` zet de
  titel en de herkomstregel erboven (plus een optionele runbrede markering),
  `schrijf_csv` de kolom `Gereedschap` achteraan, `schrijf_json` het enveloppeveld
  `gereedschap`, en de GeoPackage krijgt het veld `gereedschap` in `gwsw_run`. Roep nooit
  zelf `to_csv`, `write_text` of `json.dump` aan -- de sweep in
  `tests/test_uitvoer_herkomst.py` verbiedt een tweede schrijver in `src/`, en die is de
  waarborg dat de vier uitvoervormen niet uit elkaar lopen.
- De uitvoermap heet `uitvoer/` en staat in `.gitignore` — met een leidende slash, anders
  sluit die regel ook `src/nlriochecker/uitvoer/` uit en verdwijnt de package stilzwijgend
  uit de repository (en uit het zicht van ruff).
- Het versienummer staat alleen in `pyproject.toml`; `__version__` leest het via
  `importlib.metadata` en `tests/test_versie.py` bewaakt dat de twee gelijk blijven.
  Schrijf het nummer nergens een tweede keer op. Uitbrengen doe je met
  `uv run python scripts/uitgave.py patch|minor|major`, dat bumpt, toetst, commit en
  `vX.Y.Z` tagt; pushen blijft handwerk. Zie `docs/versionering.md`.
- De licentie is EUPL-1.2 (copyleft, en 'toegang tot de wezenlijke functionaliteit'
  telt als verspreiding). Nieuwe afhankelijkheden mogen permissief of EUPL-verenigbaar
  zijn; zie de Appendix van `LICENSE` en BO-3 in de beslislog.
- Voordat je commit, doe je eerst /superpowers:requesting-code-review, dan /python-library-complete:reviewing-python-libraries, en verbeter je met de uitkomsten van beide testen de codebase. 
- Voortgang bij de zware stappen loopt via het protocol in `voortgang.py`, met
  `NUL_VOORTGANG` als standaardwaarde. Geinstrumenteerd zijn `load_dataset`,
  `laad_nulmeting`, `run_checks` en `schrijf_geopackage`; bij een cachetreffer start er
  geen laadfase, want er wordt niets geparseerd. Voortgang is weergave: geen check leest
  er state uit en geen aanroep mag de uitkomst van een run raken. De CLI-adapter staat
  in `cli.py`, schrijft naar stderr en zet het staplabel via `item_show_func` -- niet
  door `balk.label` te overschrijven, want dan echoot click in een niet-interactieve
  omgeving een regel per stap.
- De GeoPackage draagt twee objectlagen: `putten` (punt) en `strengen` (lijn), met de
  gebreken op het object. Elk object heeft `status` (precies vier waarden: rood, oranje,
  groen, grijs) en `popup_html` (een voorgebakken fragment, zonder stijlblok -- dat
  staat een keer in de maptip). Mechanisch riool staat grijs tussen de strengen en de
  contextschil komt grijs mee; de popup zegt waarom. `status` telt systemische
  meldingen niet mee, net als `ergste_ernst`. `meldinglocaties` bestaat niet meer; de
  tabel `meldingen` draagt de foutlocatie in de kolommen `x` en `y`. De statusregel en
  de opmaak van de popup staan in `uitvoer/objectkaart.py`; `gpkg.py` levert alleen de
  feiten die alleen hij kent (stelsel, lengte, BOB-richting) als kant-en-klare regels
  aan. Zie BO-29.
- De GeoPackage draagt naast de rioleringslagen `bouwwerken` (EXT-001) en
  `waterdelen_zonder_zinker` (EXT-003): de externe objecten waarnaar de meldingen van
  díé uitvoer verwijzen, gejoind op het trefferregister (`checks/treffers.py`) via
  `object2_uri`. De schrijver bevraagt zelf nooit een externe bron -- dan zouden laag en
  uitslag uit elkaar kunnen lopen. Twee beperkingen erven mee en blijven staan: EXT-001
  meldt alleen het sterkste bouwwerk, en de watergangcheck stopt na het eerste waterdeel
  per streng. Zie BO-17 en BO-18.
- Aangeleverde externe bronnen worden bij het laden getoetst op dekking van
  `bronnen.studiegebied` (vectorlagen plus de grootste EXT-zoekafstand, het raster
  zonder marge). Een tekort boven `[bronnen] dekking_tolerantie_m` (standaard 0) is een
  harde fout: een te kleine bron geeft stilte in plaats van bevindingen. Ontbrekende
  bronnen blijven toegestaan. Zie BO-19.
- De QGIS-stijlen gaan mee in de tabel `layer_styles` van de GeoPackage, die zelf in
  `gpkg_contents` geregistreerd moet staan; zonder die rij vindt QGIS haar niet. Een QML
  los naast het bestand werkt niet bij meerdere lagen en leggen we dus niet neer.
- De stijlen van `putten` en `strengen` worden opgebouwd uit de tabel in
  `uitvoer/stijlen/symbolen.py` (regelstructuur objecttype x status, ruim honderd
  bladregels); `bouwwerken.qml` en `waterdelen_zonder_zinker.qml` blijven bestanden. Het
  symbool volgt het GWSW-objecttype, de kleur uitsluitend de kolom `status`. De maptip
  is een expressie van een regel op `popup_html`; het stijlblok staat in de QML en niet
  in elke rij. `styleCategories` moet `MapTips` noemen, anders leest QGIS het element
  niet terug. Zie BO-30.
- De geparseerde dataset wordt gecachet (`~/.cache/nlriochecker`, `--geen-cache` om hem
  over te slaan). De sleutel bevat de broncode van de lader; wie `dataset.py` of
  `geometry.py` wijzigt, krijgt vanzelf een nieuwe cache.
  De cachemap groeit per sleutel (op De Wolden ruim 450 MB); oude sleutels worden niet
  automatisch opgeruimd.
- `tests/test_uitvoer_qgis.py` vindt PyQGIS door de systeem-site-packages achter
  deze (van het systeem afgeschermde) venv aan `sys.path` te plakken; zonder QGIS
  op de machine slaat hij gewoon over. Zie de moduledocstring van dat bestand voor
  hoe dat pad afgeleid wordt en `GWSW_QGIS_SITE_PACKAGES` om het te overschrijven.

## Werkwijze
- Werk op `dev`, niet op `main`. Elke wijziging gaat naar `dev`; `main` draagt alleen
  uitgebrachte, getagde versies. Pas als de auteur zegt dat het een nieuwe versie is,
  merge je `dev` in `main` en draai je daar `scripts/uitgave.py` -- in die volgorde,
  want het script eist `main` (`TAKVOORWAARDE`) en breekt af op elke andere tak. Zet
  `dev` daarna weer gelijk aan `main`, anders mist hij de bumpcommit.
- Kleine stappen, na elke werkende stap een git-commit met een duidelijke boodschap.
- Bij twijfel over domeinlogica: raadpleeg eerst data/checkregister-gwsw-nulmeting-v0_9.md en de ontologie in data/gwsw_ontologieen/; verzin geen eigen interpretaties.
- Voer na elke wijziging ruff, mypy en pytest uit voordat je afrondt.
- Elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in
  `CHANGELOG.md`. `scripts/uitgave.py` weigert een uitgave met een lege sectie.
- Geloof onwaarschijnlijke uitkomsten niet. Duizenden bevindingen op een dataset wijzen meestal op een modelleerfout in de engine, niet op duizenden gebreken; zoek de oorzaak voordat je het cijfer rapporteert.
- Wat een check NIET heeft bekeken hoort in het rapport: objecten buiten de graaf, weggelaten bevindingen, ontbrekende typeringspoort. Stilte leest als "alles gecontroleerd".

## Open punten
Openstaand werk staat als GitHub-issue op `mcolee/nlriochecker`, niet hier. Lijst ze met
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

Single-context: `CONTEXT.md` in de root plus `docs/adr/`. Zie `docs/agents/domain.md`.
