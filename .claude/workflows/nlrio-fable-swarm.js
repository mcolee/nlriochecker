export const meta = {
  name: 'nlrio-fable-swarm',
  description: 'Fable 5.1-swarm op nlriochecker: 12 lenzen met bewijsplicht (defecten, security, architectuur, performance, kwaliteit, tests, product-hefboom), Fable-skepticus, Fable-regisseur met <=25 aanbevelingen voor 10x',
  phases: [
    { title: 'Audit', detail: '12 Fable-lenzen: defecten met repro, security, architectuur, performance met meting, kwaliteit, tests/CI, product-hefboom', model: 'fable' },
    { title: 'Verify', detail: 'Fable-skepticus draait repro/meting na of controleert het citaat in de code', model: 'fable' },
    { title: 'Regie', detail: 'Fable-regisseur: oordeel per as, 10x-hefbomen, <=25 aanbevelingen, contract-rakers achteraan', model: 'fable' },
  ],
}

// Optioneel: args = { scratch: '<map voor repro-/meetscripts>', stap: 'audit' }
const SCRATCH = (args && args.scratch) || '/home/martin/nlriochecker-onderzoek/2026-09-05-fable-swarm'

const CONTEXT = `
Repo-root (cwd): /home/martin/Development/nlriochecker  (Python 3.12+, src-layout, uv, versie 0.3.1, dev=b83848d).
Package: src/nlriochecker/ (~25,5k LOC) — toetst de datakwaliteit van vrijvervalriolering: (1) de
GWSW-nulmeting (SHACL-rapporten, CSV) inlezen en analyseren, (2) eigen checks op de GWSW-OroX/TTL-
dataset conform het checkregister v0.9 (TOP/NET/HGT/ATTR/RVZ/ADM/EXT-families), (3) EXT-checks tegen
BGT/BAG/AHN/NWB. Vier uitvoervormen uit een schrijver: Markdown, CSV, GeoPackage, JSON.
Grote modules (LOC): uitvoer/gpkg 2037, checks/topologie 1720, checks/attributen 1686,
uitvoer/bevindingen 1497, checks/netwerk 1473, checks/extern 1365, checks/randvoorzieningen 1152,
checks/hoogten 1066, checks/base 805, checkconfig 778, checks/administratief 768, uitvoer/melding 671,
studiegebied 621, checks/wegvakken 621, externedata 619, cli 613, checks/verbanden 537, reporting 510,
toetsrun 462. Overige modules: checks/{selectie,treffers,meetkunde,hulpstukken,betrouwbaarheid},
uitvoer/{herkomst,identiteit,locatie,objectkaart,omvang,samenvatting,schrijver,synthese,tabel,voorbehoud},
afbakening, analysis, comparison, config, coverage, karakteristiek, meting, nulbevinding,
nulmeting_teksten, plausibiliteit, register, shaclrapport, taal, toetsloop, errors.
Deps: click, pandas, pydantic, rdflib, shapely, networkx, geopandas, rasterio, gwsw-orox-helpers
(de leeslaag: OroX/TTL inlezen, graaf, geometrie, ontologie, cache, voortgang — APARTE package,
lokaal in /home/martin/gwsw-orox-helpers, gepind via git-tag in pyproject/uv.lock).
Tests: 67 testbestanden, ~1190 tests, dekking >=95% met takken; marker 'zwaar' = de volle
De Wolden-integratietests (niet standaard).

LEES EERST, een keer volledig met Read (geen giswerk): manifesto.md (missie en beslisregels),
docs/architectuur.md (449 r), docs/gebruik.md (476 r), data/checkregister-gwsw-nulmeting-v0_9.md
(415 r), docs/agents/analyse-harness.md (vaste feiten en valkuilen voor een De Wolden-analyse).
docs/beslislog.md (5106 r) alleen gericht doorzoeken met grep op een BO-nummer of trefwoord.
Lees elk bestand dat je beoordeelt EEN KEER VOLLEDIG. Geen cd; werkmap is de repo-root.

DOEL VAN DE AUTEUR (manifesto.md): de digitale transformatie van de rioleringssector 10-100x
versnellen. De meetlat is de doorlooptijd van een terugkerende taak van een rioolbeheerder:
dagen -> minuten, met een controleerbare uitkomst. Beslisregels bij conflict, van boven naar
beneden: 1 correctheid en herleidbaarheid, 2 standaarden (GWSW voorop), 3 toetsbaarheid aan
metingen, 4 herbruikbaarheid/onderhoudbaarheid, 5 begrijpelijkheid voor de eindgebruiker, 6
ontwikkelsnelheid, 7 elegantie. De auteur zoekt HEFBOMEN: deze package moet sneller, beter en
met meer kwaliteit leveren. Een bevinding weegt naar die meetlat; "zou mooier kunnen" telt niet.

HARDE CONTEXTREGELS (CLAUDE.md; overtreden = geen aanbeveling):
- GWSW IS LEIDEND. Bestaat een klasse/property in de gebundelde ontologie, dan bestaat het. Voor
  je beweert dat iets niet bestaat: grep de ontologie (pad via
  uv run python -c "from gwsw_orox_helpers.bronnen import gebundelde_ontologie as g; print(g())").
  Scheid "bestaat de klasse in de ontologie" van "komen er instanties voor in deze dataset".
- De LEESLAAG (gwsw-orox-helpers) is BEVROREN vanuit deze repo: alleen haar publieke API, geen
  monkeypatch, geen afhankelijkheid van privegedrag. Een leeslaagwijziging is een release daar
  plus uv lock hier. Een bevinding die daar thuishoort is een VOORSTEL-VOOR-DE-AUTEUR
  (raaktContract=true), wel opnemen, wel labelen.
- BEVROREN PUBLIEKE CONTRACTEN van deze repo (raaktContract=true): de CLI (analyseer/dekking/
  vergelijk/toets en hun opties); de JSON-envelop (docs/json-schema.md); de GeoPackage-structuur
  (lagen, kolommen, status, popup, gwsw_run-velden); de CSV-kolommen van bevindingen.csv;
  checks.toml (de Meetbereik-lijst is daar verplicht); check-ID's zijn stabiel, vervallen ID's
  worden nooit hergebruikt.
- EEN UITVOERSCHRIJVER: alle vier vormen uit uitvoer/melding.py met herkomst uit
  uitvoer/herkomst.py; nooit zelf to_csv/write_text/json.dump; nooit invoer overschrijven
  (tests/test_uitvoer_herkomst.py bewaakt dit).
- Elke check DECLAREERT rollen + kenmerken (issue #64); twee drifttests bewaken dat (AST-sweep en
  ontologie). Verander je wat een check selecteert/leest, dan moet de declaratie mee.
- Standaard toetst een run aan ALLE CFK's (Hyd, MdsPlan, MdsProj); deelset alleen via --cfk. Drie
  Meetbereik-toestanden (meting.py). Drempels per project in TOML, geen hardcoded drempels.
  Ernst F/W; dimensietag uit de enum Dimension. toets draait nooit zonder klassenhierarchie
  tenzij --geen-ontologie (issue #33).
- Wat een check NIET bekeek hoort in het rapport; stilte leest als "alles gecontroleerd".
- Poort: ruff check, ruff format, mypy over src/nlriochecker, pytest (zonder zwaar), dekking >=95%.

WAT AL GEDAAN IS (niet opnieuw voorstellen; wel voortbouwen). Issues #1-#135 zijn gesloten,
waaronder de 12 uit de vorige review-swarm van 30-08 (#113-#124: gouden ledger per check,
waardegelijkheid CSV/JSON/GeoPackage, takdekking, meetkunde-unittests, SHACL-vormen-drifttest,
vier drifthekken, kapotte invoer/sqlite-URI, CI-hygiene met SHA-pins/dependabot, mypy-ratchet,
feitenkanaal naast de meldingenstroom, shapely-cache in TOP, graafscans dedupliceren) en de
checkaudit-golf #79-#107 (richtingscluster NET-009, scope-besluiten, drempelbesluiten). Open:
#136 (1.7-vormtabel, wacht op data), #137 (HGT-011-declaratie), #138 (populatievraag EXT-001/
ATTR-017/TOP-014 aan de auteur), #139 (bug: drie check-idiomen lezen op een GWSW 1.7-export stil
nul door 1.6-constanten als munteenheid — bekend, niet opnieuw melden, wel andere gevallen van
hetzelfde patroon). De leeslaag heeft haar eigen perf-plan (issues #59-#75 daar: GC uit om
pickle.load, laadpiek, str-laag verbreden, verwijdering van rdflib-typed functies en 1.6-
constanten in een latere minor); nlriochecker migreert daarna. Voorstellen die in de leeslaag
horen, verwijs je daarheen.

MEETFEITEN: koude toetsrun op De Wolden (108 MB TTL, 23.485 knopen / 23.440 strengen, ~162k
meldingen) ~144 s waarvan ~77 s checkwerk (scripts/profiel_checks.py, 01-09); zwaarste HGT-003
13 s (AHN-raster), EXT-001 11,5 s (shapely), EXT-009 8,8 s (NWB), HGT-001/002 elk 6,5 s, TOP-006
5,4 s; piek < 2 GB. Cachetreffer van de leeslaag scheelt de parse (~30 s). Bestaande volle runs
staan in uitvoer/ (git-ignored; recentste 04092026_slotrun): tel daarop voordat je een nieuwe
run van minuten start. Het getrackte voorbeeld draait in seconden:
  uv run nlriochecker toets --dataset voorbeelden/koekangerveld/koekangerveld_orox.ttl
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_Hyd.csv
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_MdsPlan.csv
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_MdsProj.csv
    --studiegebied voorbeelden/koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg
    --bronnen voorbeelden/koekangerveld --output ${SCRATCH}/<lens>/voorbeeld
De machine heeft 4 cores en 15 GB en is NIET stil: andere lenzen draaien tegelijk. Een volle
De Wolden-run of een gepaarde meting serialiseer je met \`flock ${SCRATCH}/meet.lock <cmd>\`.
Hotspot-claims komen uit een PROFIEL (cProfile/pyinstrument via uv run --with), niet uit
wandklok; een versnellingsclaim is alleen 'aangetoond' als hij gepaard (referentie en experiment
om en om, n>=3) en eenduidig gemeten is (traagste experiment sneller dan snelste referentie),
met sha256-gelijke uitvoer. Prototypes als monkeypatch of kopie in ${SCRATCH}/<lens>/, NOOIT in src/.

BEWIJSPLICHT. Elke bevinding heeft een 'soort':
- defect / security: aantoonbaar fout gedrag op concrete invoer. Schrijf een minimale repro
  (pytest-bestand met een handgeschreven TTL of SHACL-CSV met precies een ingebouwd defect, naar
  het model van tests/fixtures/) in ${SCRATCH}/<lens>/ (maak de map aan; NOOIT in de repo), draai
  hem met \`uv run pytest <pad> -x -q -p no:cacheprovider\` of \`uv run python ...\` vanuit de
  repo-root en plak de werkelijke uitvoer. Zonder draaiende repro: zekerheid='vermoeden'.
- architectuur / kwaliteit / tests / product: bewijs is een exact bestand:regel-citaat, een
  importgraaf- of telling-uitvoer, of de uitvoer van een commando.
- performance: een profiel-uittreksel of een gepaarde meting met de ruwe getallen.
Draai NIET de volledige testsuite en NIET de marker zwaar. Wijzig NIETS in de repo. Meningen en
stijlvoorkeuren tellen niet; "dit kost een beheerder aantoonbaar tijd, vertrouwen of een fout
oordeel" telt wel, mits met bewijs. Benoem ook wat GOED is: de regisseur moet weten wat hij
niet mag aanraken.`

const ARCH_SKILLS = 'SKILLS voor deze lens: laad eerst mattpocock-skills:codebase-design (deep modules, seams, adapters) met de Skill-tool.'
const PERF_SKILLS = 'SKILLS voor deze lens: laad eerst python-library-quality:optimizing-python-performance en mattpocock-skills:diagnosing-bugs (meten -> hypothese -> experiment -> meten). Ontbrekende tools als pyinstrument draai je met `uv run --with pyinstrument ...`, niet installeren in de repo.'

const DIMENSIONS = [
  { key: 'defecten-checks', prompt: `LENS: DEFECTEN in de check-engine (checks/*.py, selectie, treffers, meetkunde, hulpstukken, checkconfig). Toets de implementaties aan het checkregister v0.9 en de GWSW-ontologie. Jaag op modelleerfouten van het soort dat duizenden valse of nul bevindingen geeft: verkeerde populatieselectie (rollen), verkeerd gelezen kenmerken (eenheid, datatype, lege string vs None, taaltag), richting-/graafaannames (hasConnection symmetrisch, hasPart omhoog tot een put, knoop is een orientatie), off-by-one op drempels en toleranties, dubbele meldingen per object, checks die door een geerfde run() stil overslaan, en het #139-patroon (1.6-constante als munteenheid op een 1.7-graaf) op andere plekken. Bouw per bevinding een handgeschreven TTL met precies een defect en draai de check erop.` },
  { key: 'defecten-invoer', prompt: `LENS: DEFECTEN in het invoerpad en de drie andere subcommando's: shaclrapport (SHACL-CSV: kolommen, Severity->F/W, CfkTypes_typ-typeringspoort, kopblokvelden), nulbevinding, nulmeting_teksten, analysis/coverage/comparison (analyseer, dekking, vergelijk), meting.py (de drie Meetbereik-toestanden en CFK-deelset), studiegebied/afbakening (kern/schil, studiegebied-validatie, CRS), config/checkconfig (TOML-validatie, ontbrekende sleutels, verkeerde types, dubbele check-ID's), toetsrun/_ontologiekeuze/--geen-ontologie, cli-foutafhandeling (errors.py). Jaag op randgevallen: lege CSV, BOM, andere kolomvolgorde, Windows-regeleinden, een CFK dubbel, een rapport voor een niet-gekozen CFK, twee meetmomenten met ongelijke sets, ontbrekende geometrie, studiegebied zonder overlap. Repro per bevinding.` },
  { key: 'defecten-uitvoer', prompt: `LENS: DEFECTEN in de uitvoerlaag (uitvoer/*.py, reporting.py). Beloften: een schrijver, vier vormen met dezelfde meldingen, herkomst/voorbehoud/markering in alle vier, 'wat niet bekeken is' in het rapport, GeoPackage-lagen met status en popup, JSON-envelop volgens docs/json-schema.md. Jaag op: meldingen die in een vorm wel en in een andere niet landen (onderdrukking, deelset, systemische bevindingen), objecten zonder geometrie die stil uit de GeoPackage vallen, tellingen die niet optellen (rapportkop vs CSV vs gwsw_run), popup-teksten die kapotgaan op quotes/newlines/unicode, niet-deterministische volgorde tussen runs (draai het voorbeeld twee keer met verschillende PYTHONHASHSEED en vergelijk), overschrijven van bestaande uitvoer, Markdown-injectie uit datawaarden. Repro op het Koekangerveld-voorbeeld.` },
  { key: 'security', prompt: `LENS: SECURITY op onvertrouwde invoer. De package leest TTL/SHACL-CSV/GeoPackage/GeoJSON/GeoTIFF/TOML en schrijft bestanden. Jaag op: path-traversal via --output of via namen uit de data (check-ID's, laagnamen, bestandsnamen in de herkomst), invoer die overschreven wordt, symlink-volging bij schrijven, resource-uitputting zonder plafond (een TTL met miljoenen triples, een CSV met een kolom van 1 GB, een raster van 100k x 100k, een geometrie met 10^7 punten), XML/GML-entiteitsuitbreiding via rdflib of GDAL, onveilige deserialisatie (pickle via de leeslaagcache: wie kan die planten?), TOML-waarden die als code of pad landen, sqlite-URI-injectie in de GeoPackage-schrijver, en secrets/persoonsgegevens/artefacten in de repo of de getrackte data (voorbeelden/, data/). Lever een concrete aanvalsinvoer en draai hem; wat #119/#120 al dichtten, meld je niet opnieuw.` },
  { key: 'arch-lagen', prompt: `${ARCH_SKILLS}\nLENS: ARCHITECTUUR — lagen, importrichting en god-modules. Bouw de importgraaf (grep -n '^from nlriochecker\\|^import nlriochecker\\|^from \\.' over src/nlriochecker/**/*.py) en leg hem naast de lagentekening in docs/architectuur.md en de laagsnit-test (tests/test_architectuur_laagsnit.py). Waar loopt een import tegen de richting in, waar lekt engine-kennis in uitvoer/ (gpkg 2037, bevindingen 1497) of uitvoerkennis in checks/? Ontleed de god-modules (gpkg, topologie, attributen, netwerk, bevindingen, base) in verantwoordelijkheden met regelbereiken: hoeveel redenen om te veranderen dragen ze? Waar woont dezelfde kennis op twee plekken (drempels, rolnamen, stelseltypes, zinsbouw, laagnamen)? Per punt bestand:regel en een additieve hersnit.` },
  { key: 'arch-leeslaag', prompt: `${ARCH_SKILLS}\nLENS: ARCHITECTUUR — de naad met de leeslaag gwsw-orox-helpers. Grep alle importplekken ('from gwsw_orox_helpers') en beoordeel de diepte van het interface: welke samenstellingen herhaalt nlriochecker zelf die de bibliotheek had moeten dragen (patronen die 3x+ terugkomen: graafwandelingen, is_a-vragen, kenmerk-lezen met eenheid, geometrie-parses), welke leeslaag-interna bereiken de checks (rdflib-termen, IRI-constanten, 1.6-constanten, RdfNode), en hoe kwetsbaar is de aansluiting voor de aangekondigde leeslaag-wijziging (verwijdering van rdflib-typed functies en 1.6-constanten; lees /home/martin/gwsw-orox-helpers/docs/afnemers.md en docs/architectuur.md daar). Tel het oppervlak dat nlriochecker nu leert, schets een adapter-seam (checks/ praat alleen met CheckContext/selectie, niet met de leeslaag) en zeg wat additief hier kan en wat een leeslaagvoorstel is (raaktContract=true). Bewijs: bestand:regel in beide repo's en de telling.` },
  { key: 'arch-evolutie', prompt: `${ARCH_SKILLS} Plus mattpocock-skills:domain-modeling (begrippenmodel, CONTEXT.md).\nLENS: ARCHITECTUUR — evolueerbaarheid. Tel concreet wat de volgende bouwstenen kosten in te wijzigen bestanden en regels: een nieuwe check in een bestaande familie; een nieuwe checkfamilie; een checkregister v1.0 met andere ID's/drempels; een vierde CFK; een nieuwe externe bron (bv. BRO-grondwater of KNMI-neerslag); een vijfde uitvoervorm; een tweede gemeente met een eigen config; GWSW 1.8. Is het begrippenmodel (CONTEXT.md, docs/architectuur.md) een plek of verspreid? Zijn de kernmodules diep (smalle interface, veel verborgen complexiteit) of ondiep (de aanroeper stelt zelf samen)? Waar dwingt een bevroren contract een ontwerp af dat alleen additief kan groeien, en hoe ziet een schone laag ernaast eruit (raaktContract=true waar het pin raakt)? Bewijs: bestand:regel en tellingen.` },
  { key: 'perf-checks', prompt: `${PERF_SKILLS}\nLENS: PERFORMANCE — de checkfase (~77 s van ~144 s). Profileer met scripts/profiel_checks.py (lees zijn docstring en de meting van 01-09) en cProfile/pyinstrument op de zwaarste checks (HGT-003, EXT-001, EXT-009, HGT-001/002, TOP-006, en de graafscans in netwerk/topologie). Wat is Python-verspilling versus de vloer van rasterio/shapely/GEOS: per-object rastersampling i.p.v. vectorized sample op alle punten in een keer, per-object shapely-predicaten i.p.v. STRtree/bulk-predicaten, herhaalde geometrie-parses, O(n^2) over de graaf, is_a-vragen in een lus, pandas-kopieen? Bouw hooguit EEN of TWEE prototypes als monkeypatch in ${SCRATCH}/perf-checks/ en meet gepaard achter flock met sha256-gelijke bevindingen.csv. Wat #123/#124 al deden, meld je niet opnieuw. Een negatieve uitkomst met meting is ook een bevinding.` },
  { key: 'perf-uitvoer-geheugen', prompt: `${PERF_SKILLS}\nLENS: PERFORMANCE — de uitvoerfase, het geheugen en de schaal. Profileer de fase na de checks: meldingenstroom -> Markdown/CSV/GeoPackage/JSON (uitvoer/gpkg 2037: per-rij inserts? geopandas to_file per laag? stijlen?), en meet ru_maxrss van de volle run (piek < 2 GB): welke structuren houden 162k meldingen plus 47k objecten meermaals in geheugen (meldingenlijst, DataFrame-kopieen, objectkaart, rdflib-graaf van de leeslaag ernaast)? Extrapoleer naar een 5x grotere export (Rotterdam-schaal): welk pad breekt eerst (geheugen, kwadratisch, sqlite-schrijver) en wat vergt dat? Zoek generatoren die tot lijsten gematerialiseerd worden en structuren die na hun fase blijven leven. Bewijs: profiel of gepaarde meting achter flock; prototypes in ${SCRATCH}/perf-uitvoer-geheugen/.` },
  { key: 'kwaliteit', prompt: `LENS: CODEKWALITEIT & onderhoudbaarheid zoals een strenge reviewer van een professionele bibliotheek leest. Duplicatie tussen de zeven check-modules (zelfde graafwandeling, zelfde drempel-lezing, zelfde zinsbouw drie keer geschreven — tel het met grep en citeer), te lange functies (noem lengte en aantal verantwoordelijkheden), foutafhandeling (kale except, verzwolgen uitzonderingen, uitzonderingen buiten de errors.py-familie die als traceback bij de gebruiker landen), typehints die liegen (Any, cast, type: ignore — tel ze per module), dode code, logging/print-hygiene, inconsistente naamgeving NL/EN, docstrings die niet meer kloppen met de code. Bewijs met bestand:regel; per punt de kortste additieve vereenvoudiging en wat hij aan regels scheelt.` },
  { key: 'tests-ci', prompt: `LENS: TESTS & CI als kwaliteitsbewijs. Dekt >=95% de kritieke paden echt: elke check-familie op een fixture met precies een defect, de meldingenstroom, de GeoPackage-schrijver, de drie Meetbereik-toestanden, --geen-ontologie, de deelrun --cfk, de onderdrukking? Zoek zwakke asserties (alleen 'geen exception', alleen aantallen), tests die de implementatie kopieren, ontbrekende negatieve tests, fixture-drift tussen tests/fixtures en voorbeelden/, drifttests die te los zijn, flaky-risico (tmp, volgorde, tijd, PYTHONHASHSEED), en het gat tussen het lichte pad en de marker zwaar (welke bugs kan alleen zwaar vangen?). Beoordeel .github/workflows/toets.yml en scripts/runnerpoort.py: beschermt de poort een vreemde bijdrager (matrix, locked install, wheel-rooktest, dekking met takken, dubbele triggers, caching)? Bewijs met bestand:regel of commando-uitvoer.` },
  { key: 'product-hefboom', prompt: `LENS: PRODUCT-HEFBOOM — de 10x-meetlat uit het manifest. Draai het Koekangerveld-voorbeeld (commando in de context) en lees de uitvoer zoals een rioolbeheerder zonder programmeerachtergrond en een wethouder dat doen: het Markdown-rapport, de CSV, de GeoPackage in woorden (laagnamen, popup, status), de terminaluitvoer. Beoordeel tegen de principes: is elke melding herleidbaar naar bron, regel (register-ID, BO-nummer) en drempel (principe 1 en 6)? Wordt duidelijk wat NIET bekeken is? Kan een beheerder de uitkomst in minuten omzetten in een werklijst voor het beheerpakket (welk formaat mist daarvoor: een GWSW-conforme terugkoppeling, een prioriteitsscore per object, een samenvatting per stelsel/wijk)? Wat kost een tweede gemeente concreet (config, bronnen, kennis) — de package mag niet 'alleen op mijn machine' werken (uv-only installatie, git-pins, paden)? Wat maakt de trendvergelijking (vergelijk) tot een stuurinstrument of houdt haar tegen? Zoek de drie tot vijf hefbomen die de doorlooptijd van een terugkerende beheerderstaak het meest verkorten of het vertrouwen in de uitkomst het meest vergroten, met bewijs uit de echte uitvoer (citeer regels) of bestand:regel. Contract-rakers (nieuwe CLI-optie, nieuwe laag/kolom) markeer je eerlijk als raaktContract=true.` },
]

const RECS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['bevindingen', 'sterkePunten'],
  properties: {
    sterkePunten: { type: 'array', items: { type: 'string' }, description: 'wat aantoonbaar goed is en bewaard moet blijven, met bestand:regel, meting of citaat uit de uitvoer' },
    bevindingen: {
      type: 'array', maxItems: 5,
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'soort', 'probleem', 'bewijs', 'zekerheid', 'ernst', 'bestanden', 'fixrichting', 'winst', 'raaktContract'],
        properties: {
          title: { type: 'string' },
          soort: { type: 'string', enum: ['defect', 'security', 'architectuur', 'performance', 'kwaliteit', 'tests', 'product'] },
          probleem: { type: 'string', description: 'verwacht vs werkelijk, concreet' },
          bewijs: { type: 'string', description: 'repro-pad + commando + geplakte uitvoer, bestand:regel-citaat, telling, profiel-uittreksel of gepaarde meting' },
          zekerheid: { type: 'string', enum: ['aangetoond', 'vermoeden'] },
          ernst: { type: 'string', enum: ['laag', 'midden', 'hoog', 'kritiek'], description: 'kritiek = een beheerder krijgt een fout oordeel of de run faalt; hoog = aantoonbaar tijd/vertrouwen-verlies' },
          bestanden: { type: 'array', items: { type: 'string' } },
          fixrichting: { type: 'string', description: 'kortste additieve fix' },
          winst: { type: 'string', description: 'wat het de beheerder of de auteur oplevert op de 10x-meetlat: tijd, vertrouwen, wijzigingsmoeite, s/MiB/%' },
          raaktContract: { type: 'boolean' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['isEcht', 'bewijsGecontroleerd', 'additief', 'ernst', 'redenering'],
  properties: {
    isEcht: { type: 'boolean', description: 'true alleen als jij het zelf reproduceerde, namat of het citaat in de code bevestigde' },
    bewijsGecontroleerd: { type: 'boolean' },
    additief: { type: 'boolean', description: 'fix mogelijk zonder bevroren contract of de leeslaag-API te breken' },
    ernst: { type: 'string', enum: ['laag', 'midden', 'hoog', 'kritiek'], description: 'jouw eigen inschatting, niet die van de vinder' },
    redenering: { type: 'string' },
  },
}

const OORDEEL = {
  type: 'object', additionalProperties: false,
  required: ['cijfer', 'sterk', 'zwak', 'richting10'],
  properties: {
    cijfer: { type: 'integer', minimum: 1, maximum: 10 },
    sterk: { type: 'array', items: { type: 'string' }, description: 'wat de auteur moet bewaren' },
    zwak: { type: 'array', items: { type: 'string' }, description: 'de structurele zwaktes, met bestand' },
    richting10: { type: 'string', description: 'het pad naar een 9-10, additief waar het kan, contract-rakers benoemd' },
  },
}

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['oordeel', 'hefbomen10x', 'aanbevelingen', 'themas', 'slotnoot'],
  properties: {
    oordeel: {
      type: 'object', additionalProperties: false,
      required: ['correctheid', 'architectuur', 'performance', 'onderhoudbaarheid', 'product'],
      properties: { correctheid: OORDEEL, architectuur: OORDEEL, performance: OORDEEL, onderhoudbaarheid: OORDEEL, product: OORDEEL },
    },
    hefbomen10x: {
      type: 'array', maxItems: 5, description: 'de drie tot vijf ingrepen die de doorlooptijd van een beheerderstaak of het vertrouwen in de uitkomst het meest vergroten',
      items: {
        type: 'object', additionalProperties: false,
        required: ['hefboom', 'nu', 'straks', 'waarom', 'rangen', 'raaktContract'],
        properties: {
          hefboom: { type: 'string' },
          nu: { type: 'string', description: 'de huidige toestand, gemeten of geciteerd' },
          straks: { type: 'string', description: 'de toestand na de ingreep, in de meetlat van het manifest' },
          waarom: { type: 'string' },
          rangen: { type: 'array', items: { type: 'integer' }, description: 'de aanbevelingsrangen die deze hefboom samen vormen' },
          raaktContract: { type: 'boolean' },
        },
      },
    },
    aanbevelingen: {
      type: 'array', maxItems: 25,
      items: {
        type: 'object', additionalProperties: false,
        required: ['rang', 'titel', 'soort', 'ernst', 'lens', 'bewijs', 'fixrichting', 'winst', 'additief', 'inspanning', 'hangtAf', 'bestanden'],
        properties: {
          rang: { type: 'integer' },
          titel: { type: 'string' },
          soort: { type: 'string', enum: ['defect', 'security', 'architectuur', 'performance', 'kwaliteit', 'tests', 'product'] },
          ernst: { type: 'string', enum: ['laag', 'midden', 'hoog', 'kritiek'] },
          lens: { type: 'string' },
          bewijs: { type: 'string' },
          fixrichting: { type: 'string' },
          winst: { type: 'string' },
          additief: { type: 'boolean' },
          inspanning: { type: 'string', enum: ['S', 'M', 'L', 'XL'] },
          hangtAf: { type: 'string', description: 'rang(en) waar dit van afhangt, of leeg' },
          bestanden: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    themas: { type: 'array', items: { type: 'string' } },
    slotnoot: { type: 'string', description: 'contract-rakers en leeslaagvoorstellen voor de auteur; wat een agent additief mag oppakken; de aanbevolen volgorde' },
  },
}

// Auditstap als losse functie: byte-identieke prompt/opts, zodat een latere volledige run
// met resumeFromRunId de auditresultaten uit de cache haalt.
const auditeer = (d) => agent(
  `${CONTEXT}\n\n${d.prompt}\n\nLever maximaal 5 bevindingen; liever 2 aangetoonde dan 5 vermoedens. Noem ook de sterke punten. Werkmap voor repro's, metingen en uitvoer: ${SCRATCH}/${d.key}/ (maak hem aan).`,
  { label: `audit:${d.key}`, phase: 'Audit', model: 'fable', schema: RECS_SCHEMA, effort: 'high' },
)

phase('Audit')
log(`Fable-swarm nlriochecker: ${DIMENSIONS.length} lenzen, werk in ${SCRATCH}`)

if (args && args.stap === 'audit') {
  const ruw = await parallel(DIMENSIONS.map((d) => () => auditeer(d).then((r) => ({ lens: d.key, ...(r || { bevindingen: [], sterkePunten: [] }) }))))
  const n = ruw.filter(Boolean).reduce((s, r) => s + r.bevindingen.length, 0)
  log(`Audit klaar: ${n} ruwe bevindingen, geen verify (stap=audit)`)
  return { stap: 'audit', ruw: ruw.filter(Boolean) }
}

const reviewed = await pipeline(
  DIMENSIONS,
  auditeer,
  (review, d) => parallel(((review && review.bevindingen) || []).map((r, i) => () =>
    agent(
      `${CONTEXT}\n\nJij bent de SKEPTICUS. Probeer deze bevinding te weerleggen (lens ${d.key}).\nTITEL: ${r.title}\nSOORT: ${r.soort}\nPROBLEEM: ${r.probleem}\nGECLAIMD BEWIJS: ${r.bewijs}\nGECLAIMDE WINST: ${r.winst}\nCLAIM ernst=${r.ernst}, zekerheid=${r.zekerheid}, raaktContract=${r.raaktContract}.\n\nBij defect/security: draai de repro zelf (of schrijf een betere in ${SCRATCH}/verify-${d.key}-${i}/). Bij performance: controleer het profiel of draai de gepaarde meting na achter flock; zonder eenduidige gepaarde meting hooguit 'vermoeden' en dan isEcht alleen als het profiel de hotspot wel bewijst. Bij architectuur/kwaliteit/tests/product: controleer elk citaat in de echte code of de echte uitvoer, bouw de telling zo nodig na, en toets of docs/architectuur.md, docs/beslislog.md (grep) of het checkregister dit al als bewuste keuze benoemt. Is het echt fout, of gedocumenteerd, bedoeld, al gedekt door een test, al gedaan in #1-#135, of een leeslaagzaak (dan raaktContract)? Is de fix additief? isEcht=true ALLEEN als jij het zelf bevestigde.`,
      { label: `verify:${d.key}:${i}`, phase: 'Verify', model: 'fable', schema: VERDICT_SCHEMA, effort: 'medium' },
    ).then((v) => (v ? { ...r, lens: d.key, verdict: v } : null)),
  )).then((vs) => ({ lens: d.key, sterkePunten: (review && review.sterkePunten) || [], items: vs })),
)

const alle = reviewed.filter(Boolean)
const overleefd = alle.flatMap((r) => r.items).filter(Boolean).filter((x) => x.verdict && x.verdict.isEcht)
const gesneuveld = alle.flatMap((r) => r.items).filter(Boolean).length - overleefd.length
const sterk = alle.flatMap((r) => r.sterkePunten.map((s) => `[${r.lens}] ${s}`))
log(`Verify: ${overleefd.length} bevestigd, ${gesneuveld} afgevallen; ${sterk.length} sterke punten`)

phase('Regie')
const bundel = overleefd.map((x, i) => ({
  n: i + 1, lens: x.lens, soort: x.soort, titel: x.title, probleem: x.probleem, bewijs: x.bewijs,
  winst: x.winst, ernstVinder: x.ernst, ernstSkepticus: x.verdict.ernst, bestanden: x.bestanden,
  fixrichting: x.fixrichting, additief: x.verdict.additief, raaktContract: x.raaktContract,
  verifyNoot: x.verdict.redenering,
}))

const plan = await agent(
  `${CONTEXT}\n\nJij bent de REGISSEUR. ${bundel.length} bevestigde bevindingen uit ${DIMENSIONS.length} lenzen:\n\n${JSON.stringify(bundel, null, 1)}\n\nSTERKE PUNTEN volgens de lenzen:\n${sterk.map((s) => `- ${s}`).join('\n')}\n\nLaad eerst mattpocock-skills:codebase-design. Geef een eigen oordeel per as (correctheid, architectuur, performance, onderhoudbaarheid, product) met cijfer 1-10, sterk/zwak en het pad naar 9-10; lees daarvoor zelf manifesto.md, docs/architectuur.md en de importgraaf en draai zelf het Koekangerveld-voorbeeld — leun niet alleen op de lenzen. Benoem dan de HEFBOMEN10X: de drie tot vijf ingrepen die op de meetlat van het manifest (doorlooptijd van een beheerderstaak, vertrouwen in de uitkomst, kosten van een tweede gemeente) het meest opleveren, elk met de huidige en de toekomstige toestand en de rangen die hem vormen. Ontdubbel (zelfde oorzaak = een punt), fuseer waar lenzen elkaar raken, rangschik op ernst x zekerheid x winst, geef per punt de kortste additieve fixrichting, inspanning en afhankelijkheden. Contract-rakers en leeslaagvoorstellen apart en achteraan. Benoem de rode draden; zet in de slotnoot wat de auteur zelf beslist versus wat een agent additief mag oppakken, en de aanbevolen volgorde. Controleer twijfelgevallen zelf in de code.`,
  { label: 'regisseur:fable', phase: 'Regie', model: 'fable', schema: PLAN_SCHEMA, effort: 'high' },
)

return { bevestigd: overleefd.length, afgevallen: gesneuveld, sterkePunten: sterk, plan }
