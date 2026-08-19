# Wijzigingslog

Alle noemenswaardige wijzigingen aan dit project staan hier. De opzet volgt
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/), de nummering volgt
[semantische versionering](https://semver.org/lang/nl/) zoals
[docs/versionering.md](docs/versionering.md) die voor dit project uitlegt.

`scripts/uitgave.py` zet bij elke uitgave de sectie `Unreleased` om in een sectie met
het nieuwe nummer en de datum, en opent een lege nieuwe. Hij weigert uit te brengen als
`Unreleased` leeg is: een uitgave zonder wijzigingen is geen uitgave.

## [Unreleased]

### Toegevoegd

- `configs/dewoldenhoogeveen.toml`: de projectconfiguratie voor het hele gebied van de
  OroX-dataset, met de bronnen uit `data/gis_dewoldenhoogeveen`. Alleen het blok
  `[bronnen]` wijkt af van de meegeleverde `checks.toml`.
- `nlriochecker.toetsrun` voert een toets uit zonder de opdrachtregel:
  `Toetsopdracht` in, `Toetsuitslag` uit, met de gemeten uitkomsten als velden en het
  verhaal voor de gebruiker in `regels()`. Het commando `toets` is er de adapter van
  geworden; de uitvoer op het scherm en op schijf is ongewijzigd. Zie BO-21.
- `errors.OpdrachtError` voor een verzoek dat niet kan (een gebiedskeuze zonder
  studiegebied, een onbekende conformiteitsklasse, een onbekend check-ID), en
  `meting.kies_cfk` om een CFK-keuze tegen de vereiste set te toetsen.
- Twee lagen in de GeoPackage met de externe objecten waarnaar de EXT-checks verwijzen:
  `bouwwerken` (EXT-001) en `waterdelen_zonder_zinker` (EXT-003), elk met een eigen
  QGIS-stijl. Ze worden uitsluitend gevuld vanuit de meldingen van die uitvoer, dus hun
  inhoud is per constructie gelijk aan de testuitkomst -- ook per gebied.
- EXT-001 en EXT-003 wijzen het geraakte externe object aan in `object2_uri` en
  `object2_label` (`bgt:pand/...`, `bag:pand/...`, `bgt:bouwwerk/...`,
  `bgt:waterdeel/...`, met `geo:<hash>` als terugval voor een bron zonder
  identificatie). Achterwaarts verenigbaar binnen schemaversie 1.0; de conventies staan
  in [docs/json-schema.md](docs/json-schema.md).
- Een dekkingspoort op de externe bronnen: elke aangeleverde laag en het AHN-raster
  moeten het bereik uit `bronnen.studiegebied` dekken, vectorlagen inclusief de grootste
  EXT-zoekafstand. Een tekort boven `[bronnen] dekking_tolerantie_m` (standaard 0) is
  een harde fout die beide omhullenden en het tekort per zijde noemt. Een te kleine bron
  gaf tot nu toe stilte in plaats van bevindingen.
- Rapportage per studiegebied-feature. Bevat het studiegebiedbestand meer dan een vlak,
  dan schrijft `toets` per gebied een submap met alle vier de uitvoervormen, plus een
  `totaal/` met de synthese en de unieke meldingen over alle gebieden. De meldingen van
  een gebied zijn gelijk aan die van een losse run met alleen dat gebied; daar staat een
  test op. Met `--gebied` beperk je de run tot een of meer gebieden.
- Strenge validatie van het studiegebiedbestand, altijd voordat de dataset geladen wordt:
  alleen Polygon en MultiPolygon (overgeslagen typen worden geteld en gemeld), vanaf twee
  vlakken een verplichte, gevulde, unieke kolom `naam_gebied` waarvan de gesaneerde
  mapnamen niet mogen botsen, en voor GeoJSON een toets op het coordinaatstelsel: een
  legacy `crs`-member met EPSG:28992, of alle coordinaten binnen de RD-grenzen uit
  `[drempels]`.
- **De melding-ID's van EXT-001 en EXT-003 verschuiven.** `melding_id` is een hash over
  check, objecten en detailsleutels; nu die twee checks hun `object2_uri` vullen, krijgen
  hun meldingen een ander ID dan in de vorige versie. Wie meetmomenten vergelijkt, ziet
  ze eenmalig als opgelost plus nieuw. Datzelfde gebeurt bij een bron zonder
  identificatie zodra haar geometrie wijzigt, want dan verschuift de `geo:`-sleutel mee.
  Het JSON-schema blijft 1.0: het contract verandert niet, alleen de inhoud van een veld
  dat er al was.
- `[bronnen] dekking_tolerantie_m` staat in de meegeleverde `checks.toml` op 300 m. De
  code blijft standaard streng (0 m); deze waarde hoort bij de bronnen in `data/gis`,
  waarvan `bgt_bouwwerk` aan de oostkant 276 m voor de rand ophoudt.
- Uitbreidingen in de Python-API rond de externe bronnen (0.x, dus zonder
  deprecatietermijn): `load_external_data` kreeg een keyword-only `dekkingseis`,
  `CheckContext` en `CheckRun` kregen het veld `treffers`, en
  `_WatergangKruising.kruisingen()` levert vijf waarden in plaats van vier -- de
  geometrie van het waterdeel is erbij gekomen. De eerste twee zijn additief.
- Een gebied zonder GWSW-objecten stopt een run over meerdere gebieden niet meer, maar
  levert een eigen rapport met nul bevindingen en een expliciete melding -- in dat rapport
  en in de synthese. Bij een run op een enkel gebied blijft het een harde fout.
- De JSON-envelop kan `gebied` en `gebieden` dragen. Achterwaarts verenigbaar binnen
  schemaversie 1.0: een run zonder studiegebieden schrijft de velden niet.
- `--cfk` op `analyseer`, `dekking`, `toets` en `vergelijk`: toetsen op een
  deelverzameling conformiteitsklassen. Standaard blijven alle drie vereist; elke
  afwijking staat als waarschuwingsregel boven elk rapport en in de GeoPackage
  (`cfk_set`, `volledig`). Een run zonder `--shacl` meldt dat er niet gemeten is --
  dat is iets anders dan een deelset, en iets anders dan volledig.
- Een JSON-export van de meldingenstroom (`bevindingen.json`), met een envelop en een
  eigen `schema_versie` los van het packagenummer; uit te zetten met `--geen-json`.
  Het contract staat in [docs/json-schema.md](docs/json-schema.md).
- Zichtbare voortgang bij het inlezen van de TTL's, het inlezen van de
  SHACL-rapporten, het draaien van de checks en het wegschrijven van de GeoPackage.
  Als library via het protocol in `voortgang.py`, op de opdrachtregel als balk op
  stderr. Geen nieuwe afhankelijkheid.
- Elk uitvoerbestand noemt de package en versie die het schreef: de Markdown-rapporten
  in een regel onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het
  veld `gereedschap` van `gwsw_run`.
- `py.typed`, zodat de typehints van deze package ook bij een importerende toepassing
  aankomen.
- CI (`.github/workflows/toets.yml`): ruff, mypy en pytest op elke push naar `main` of
  `dev` en op elke pull request naar `main`. De run valt als er nog meer tests overgeslagen
  worden dan de runner sowieso overslaat -- een fixturemap die niet meekomt leest anders
  als "alles groen".
- Mypy als poort, met een configuratie in `pyproject.toml`; de codebase is schoon.
- Dit wijzigingslog.

### Gewijzigd

- De aangeleverde geodata staat niet meer in `data/gis` maar in
  `data/gis_koekangerveld`; daarnaast is er `data/gis_dewoldenhoogeveen` met dezelfde
  bronsoorten voor het hele gebied van de OroX-dataset. De standaard `[bronnen] map`
  in `checks.toml` en de integratietests wijzen mee.
- De laatste twee plekken in de uitvoerlaag die hun eigen klassenselectie opbouwden
  (`uitvoer/synthese.py` en `uitvoer/gpkg.py`) gebruiken nu `checks/selectie.py`,
  waarmee het restant uit BO-20 weg is. De rol `mechanischeleidingen` is daar
  bijgekomen.

- De klassenselecties van de checks staan op een plek, `checks/selectie.py`, in plaats
  van in vijf checkmodules met elk hun eigen cachesleutel. De namen volgen de
  GWSW-ontologie waar een klasse de rol dekt; `gwsw:Streng` bestaat niet, dus wat
  `_strengen` heette selecteert `gwsw:Leiding` en heet nu `leidingen`. Interne
  wijziging: de uitvoer van een volledige run is byte-identiek gebleven. Zie BO-20 en
  [CONTEXT.md](CONTEXT.md).
- Een studiegebiedbestand met meerdere vlakken zonder kolom `naam_gebied` is voortaan een
  fout in plaats van een stilzwijgende samenvoeging tot een gebied. Datzelfde geldt voor
  niet-vlakken: die werden ingelezen en tellen nu niet meer mee.
- Breuken in de Python-API (0.x, dus zonder deprecatietermijn):
  - `load_study_area` levert nog steeds een `StudyArea` (de unie van alle vlakken), maar
    valideert nu als hierboven. `load_studiegebieden` levert de gebieden per feature.
  - `bouw_analyseset` kreeg een keyword-only `gedeeld`, `run_checks` een keyword-only
    `fase`, `CheckContext` het veld `gedeelde_volledige_context`, `schrijf_uitvoer` de
    keywords `gebied`, `meldingen` en `notities`, `write_check_report` de parameter
    `notities` en `beperk_tot_studiegebied` de parameters `binnen` en `leeg_toegestaan`.
    Alle additief.
  - `CheckContext.volledige_context()` draagt geen `analyseset` meer. Checks die op de
    volledige export draaien (`volledige_dataset_checks`) noemen hun bereik daardoor
    "deze dataset" in plaats van "het geanalyseerde deel"; dat laatste was onjuist, want
    ze zien de hele export. Raakt alleen projecten die zelf checks aan die lijst
    toevoegen; de standaard (ADM-002) noemt zijn bereik niet.
- `toets` zonder `--shacl` schrijft een extra regel `**Geen nulmeting:** ...` in
  `bevindingen.md`. Wie rapporten van voor en na deze versie vergelijkt, ziet die regel
  als verschil.
- Breuken in de Python-API (0.x, dus zonder deprecatietermijn):
  - `Nulmeting` kreeg het verplichte veld `meetbereik`; `CoverageResult` kreeg het
    verplichte veld `meetbereik` **tussen** `checks` en `discrepanties` in, en `Uitvoer`
    kreeg het verplichte veld `json`. Wie deze dataclasses positioneel construeerde,
    krijgt bij `CoverageResult` geen `TypeError` maar een stille verschuiving van
    argumenten. Construeer ze met sleutelwoorden.
  - `laad_nulmeting` kreeg een derde parameter `volledige_cfk`. Zonder die parameter
    geldt de meegegeven set als de volledige set, en dan meldt de run "volledig". Een
    library-gebruiker die op een deelset toetst, moet hem dus meegeven; de CLI doet dat.
  - `schrijf_uitvoer` kreeg `met_json` en `voortgang`; `load_dataset`, `laad_nulmeting`,
    `run_checks`, `laad_met_cache` en `schrijf_geopackage` kregen een keyword-only
    `voortgang`. Die laatste zijn additief.
  - `CheckRun.meetbereik` is nooit `None`; een run zonder opgegeven bereik draagt
    `Meetbereik.niet_gemeten(())`.
- De ondergrens van `click` is naar `>=8.2`: daarvoor mengde `CliRunner` stderr in
  stdout en bestond `Result.stderr` niet.
- `vergelijk` weigert twee nulmetingen die op verschillende conformiteitsklassen
  getoetst zijn: een daling in het aantal meldingen die uit een kleinere getoetste set
  komt is geen verbetering. Geen forceer-vlag.
- Een SHACL-rapport voor een conformiteitsklasse buiten de gekozen set is een fout in
  plaats van een stille overslag.
- `[nulmeting] vereiste_cfk` is verplicht in de projectconfiguratie. De lijst stond ook
  als default in `checkconfig.py`; een config die de sectie miste viel daar
  stilzwijgend op terug, en sinds `--cfk` bepaalt diezelfde lijst ook welke klassen die
  optie accepteert.
- `CheckContext.cached()` is generiek geworden: bellers krijgen hun eigen structuur terug
  in plaats van `object`. Dat haalde in een keer 23 typefouten weg.
- `scripts/uitgave.py` toetst nu ook met mypy en onderhoudt dit wijzigingslog.
- Werkafspraak: werk staat op `dev`, `main` draagt alleen uitgebrachte versies.

### Gerepareerd

- Het fase-totaal van de GeoPackage-voortgang werd met de hand geteld en kon uit de
  pas lopen met het aantal gezette stappen. Het volgt nu uit dezelfde rij staplabels.

- Een streng met een lijngeometrie van precies een coordinaat brak het inlezen van de
  hele export af. GEOS gooit daar zijn eigen fout, en die erft niet van `ValueError`,
  dus vloog hij ongevangen door de GML-parser heen. Het object wordt nu als onleesbaar
  geteld en het rapport meldt het, zoals bij elke andere onleesbare geometrie.

- NET-004 wees per run een andere streng aan. `nx.find_cycle` zonder `source` begint bij
  de eerste knoop in invoegvolgorde, en die volgt uit de hashseed; twee runs op dezelfde
  data toonden daardoor een verschil dat er niet was. De kringloop start nu bij de
  kleinste URI van het samenhangende deel.

### Verwijderd

- De afhankelijkheid `pyproj`; die werd nergens geimporteerd en komt zo nodig via
  geopandas en rasterio mee.

## [0.2.0] - 2026-08-17

Eerste uitgave onder een vast versienummer.

### Toegevoegd

- Afbakening met een studiegebied: de checks draaien op een kern plus contextschil,
  het rapport gaat over de kern.
- Een cache van de geparseerde dataset (`~/.cache/nlriochecker`), met een sleutel die de
  broncode van de lader meeneemt.
- GeoPackage-uitvoer met QGIS-stijlen in `layer_styles`, uit dezelfde meldingenstroom
  als de Markdown- en CSV-uitvoer.
- Checkregister v0.8 als contract, met een dekkingsmatrix die uit het register
  gegenereerd wordt.
- `scripts/uitgave.py` en een enkele versiewaarheid in `pyproject.toml`.

### Gewijzigd

- Hernoemd naar `nlriochecker`: package, commando en cachemap.
- Onder EUPL-1.2 gebracht.

[Unreleased]: https://github.com/mcolee/nlriochecker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mcolee/nlriochecker/releases/tag/v0.2.0
