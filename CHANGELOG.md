# Wijzigingslog

Alle noemenswaardige wijzigingen aan dit project staan hier. De opzet volgt
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/), de nummering volgt
[semantische versionering](https://semver.org/lang/nl/) zoals
[docs/versionering.md](docs/versionering.md) die voor dit project uitlegt.

`scripts/uitgave.py` zet bij elke uitgave de sectie `Unreleased` om in een sectie met
het nieuwe nummer en de datum, en opent een lege nieuwe. Hij weigert uit te brengen als
`Unreleased` leeg is: een uitgave zonder wijzigingen is geen uitgave.

## [Unreleased]

### Gewijzigd

- **Het bevindingenrapport van `toets` is opnieuw opgebouwd** (issue #16). De volgorde
  is nu: de naam van het gebied als titel, dan wat er in dat gebied ligt, dan of het
  voldoet, dan de verantwoording, en pas daarna het detail. De rapporten van
  `analyseer`, `dekking` en `vergelijk` blijven ongewijzigd.

  - **Titel:** de `naam_gebied` van het studiegebied, met terugval op de aanduiding die
    `StudyArea` zelf samenstelt en, zonder studiegebied, op de dataset. De synthese in
    `totaal/` heet "Totaal (N gebieden)"; de dataset staat in de romp.
  - **Aantallen:** een tabel objecttype x stelseltype over de kern van het gebied, met
    bij de leidingen zowel het aantal als de getekende meters. De contextschil staat als
    voetnoot eronder en telt niet mee -- er wordt niet over gerapporteerd.
  - **Managementsamenvatting:** een regel per conformiteitsklasse uit `vereiste_cfk`
    plus een totaalregel voor de eigen checks. Een vinkje betekent nul fouten in dit
    gebied; waarschuwingen blokkeren niet maar hun aantal staat er wel bij, met tussen
    haakjes hoeveel er systemisch zijn. Een klasse waarop niet gemeten is -- geen
    `--shacl`, of een `--cfk`-deelset waar zij buiten valt -- krijgt geen oordeel maar de
    toestandstekst. Een klasse die wél in de deelset zat krijgt haar oordeel; het
    voorbehoud over de deelset staat als markering boven het rapport (BO-7).
  - **Detailrapportage** in twee herkomstblokken: eerst de GWSW-nulmeting (per SHACL-vorm,
    fouten boven waarschuwingen, met de conformiteitsklassen erbij), dan de eigen checks
    (de foutchecks boven de waarschuwingschecks).
  - De rode draad staat bij de samenvatting in plaats van achter de tabellen. De
    verantwoording -- niet-bekeken objecten, weggelaten bevindingen, ontbrekende
    typeringspoort, niet-herleidbare focusnodes, externe bronnen, datakarakteristieken --
    is verplaatst maar niet ingekort.

  Nieuwe modules `uitvoer/omvang.py` (de aantallen, plus `stelseltypen` die de
  GeoPackage ook gebruikt) en `uitvoer/samenvatting.py` (de vier regels).

- **GWSW-conforme symbologie voor `putten` en `strengen`, met de kleur uitsluitend uit
  `status`.** Het symbool zegt wat voor object het is -- de indeling komt uit de
  PDOK-SLD's in `data/gwsw_opmaak/` -- en de kleur zegt hoe het ervoor staat:
  `#b2182b` rood, `#e08214` oranje, `#4d9221` groen, `#9e9e9e` grijs. Rood is duidelijk
  donkerder dan groen, dus ze blijven ook in grijstinten en bij deuteranopie uit elkaar
  te houden. De richtingpijl van een streng is er nog een in plaats van twee: `tegen`
  krijgt een enkele rode pijl die 180 graden gedraaid is en dus in de
  BOB-vervalrichting wijst -- waar het water werkelijk heen loopt. De logica erachter
  (`_richting_bob`) is ongewijzigd.

  De SVG's waar de SLD's naar verwijzen staan op `data.gwsw.nl` en zijn niet
  meegeleverd; elk symbool is daarom hertekend als eenvoudige QGIS-marker in de
  GWSW-vorm, met in de tabel de SLD-regel die hij vervangt. Elk objecttype uit de
  De Wolden-export en uit het Juinen-voorbeeld heeft een eigen regel met een eigen
  legendalabel; wat niet in de tabel staat krijgt een expliciet vangnetsymbool
  gelabeld "objecttype niet in de symbolentabel". De filters vergelijken
  hoofdletterongevoelig, want de export schrijft `DwaPerceelaansluitleiding` waar de
  SLD `DWAPerceelaansluitleiding` noemt.

  De twee QML's worden opgebouwd uit een tabel in
  `src/nlriochecker/uitvoer/stijlen/symbolen.py` in plaats van als bestand
  meegeleverd: de regelstructuur objecttype x status levert met de 44 knoop- en 37
  verbindingstypen in die tabel 220 respectievelijk 185 bladregels op, en die met de
  hand in XML onderhouden zou de typenlijst op twee plekken zetten. De stijl die in een
  GeoPackage meegaat draagt bovendien alleen regels voor de typen die er werkelijk in
  staan: met de volledige tabel zou de lagenboom van QGIS 225 legendaregels tonen op
  een laag met zes typen, met de voorkomende typen zijn het er 35. `bouwwerken.qml` en
  `waterdelen_zonder_zinker.qml` blijven onveranderde bestanden. Zie BO-30 (issue #14).

- **Hoverpopups (QGIS Map Tips) op beide objectlagen.** De QML draagt een
  `<mapTip enabled="1">` met een stijlblok, een vaste breedte van 300 px en één
  expressie: `[% "popup_html" %]`. De inhoud komt uit de voorgebakken kolom van issue
  #13, dus er is geen live join of relation nodig -- die zouden niet meereizen in
  `layer_styles`. Het stijlblok staat een keer in de QML en niet in elke rij; per rij
  herhaald zou het de GeoPackage tientallen megabytes groter maken. Geen webfont en
  geen afbeelding-URL. `styleCategories` noemt `MapTips` expliciet, anders leest QGIS
  het element niet terug uit `layer_styles` en blijft de popup leeg zonder foutmelding.
  **Let op:** map tips verschijnen alleen als "Show Map Tips" in de QGIS-werkbalk
  aanstaat (issue #15).

- **De GeoPackage heeft nog twee objectlagen: `putten` en `strengen`.**
  `meldinglocaties` vervalt als featurelaag en `mechanisch_riool` gaat op in de
  lijnenlaag. Elk object draagt twee nieuwe kolommen: `status` met precies vier
  waarden (`rood` bij een fout, `oranje` bij alleen waarschuwingen, `groen` bij geen
  eigen gebrek, `grijs` als er niet beoordeeld is én niets gevonden) en `popup_html`
  met een voorgebakken hoverpopup. Mechanisch riool houdt zijn GWSW-objecttype; het
  wordt door de meeste checks overgeslagen, maar niet door alle -- TOP-010, TOP-011 en
  de SHACL-nulmeting raken het wel -- en dan kleurt het gewoon mee, met "maar deels
  beoordeeld" in zijn popup. Met een studiegebied komt er een grijze ring om het gebied
  heen: de objecten binnen de buffer, zodat de kaart niet bij de gebiedsgrens ophoudt
  alsof daar niets ligt. Niet de hele contextschil -- die bevat ook de samenhangende
  vrijvervalcomponent, op een buurt van 507 objecten al gauw 12.106, en dan zou elk
  buurtbestand het net van de halve gemeente meesturen. De popup zegt per grijs object
  waarom.

  **Bewust verlies:** de exacte foutlocatie op een lijn -- het snijpunt van een
  kruising, het midden van een streng -- en het naloopwerk in een kaal GIS-pakket
  zonder joins verdwijnen van de kaart. De meldingen zelf blijven volledig in de tabel
  `meldingen`, joinbaar op `feature_id`, en die tabel draagt nu de kolommen `x` en `y`
  met diezelfde foutlocatie -- anders zou hij stilzwijgend uit de GeoPackage
  verdwijnen. Objectloze meldingen (dataset-breed, EXT-verwijzingen zonder rioolobject,
  de onherleide focusnodes van de nulmeting) stonden ook voorheen niet op de kaart en
  blijven in rapport en meldingentabel staan. Zie BO-29 (issue #13).

- `status` telt systemische meldingen niet mee, net als `ergste_ernst`, `n_fout` en
  `n_waarschuwing` al deden. Op De Wolden draagt de nulmeting 68.882 systemische
  meldingen op 105.963; zouden die meetellen, dan is vrijwel elke put rood. Gevolg: een
  object waarvan alle meldingen systemisch zijn krijgt `groen`, wat hier "geen gebrek
  dat dit object van zijn buren onderscheidt" betekent en niet "in orde". De kolom
  `n_systemisch` en de popup zeggen het er allebei bij.

- De opdrachtregel noemt de tellingen van de eigen checks en die van de nulmeting
  apart, `gwsw_run` telt `fouten` en `waarschuwingen` uit de meldingenstroom (zodat ze
  niet met `meldingen_totaal` uit de pas lopen), en de rode draad in het rapport
  redeneert alleen nog over meldingen uit het checkregister -- de SHACL-vormen zijn per
  kenmerk gesplitst en slaan per constructie samen aan, dus "meerdere checks op
  hetzelfde object" zegt daar niets. Het rapport meldt voortaan ook hoeveel
  nulmetingovertredingen buiten het studiegebied vielen.

### Toegevoegd

- De SHACL-nulmetingovertredingen komen als meldingen in alle vier de uitvoervormen
  terecht, uit dezelfde meldingenstroom als de eigen checks: `Bron = nulmeting`,
  `Categorie = NULMETING`, check-ID `NULMETING-<SHACL-vorm>`, dimensie `Compliance`.
  Nieuw veld `cfk` op `Melding` -- kolom `CFK` in de CSV, kolom `cfk` in de
  GeoPackage-tabel `meldingen`, veld `cfk` in de JSON -- met de conformiteitsklassen
  die de overtreding noemen. Daarmee gaat `schema_versie` van `1.0` naar `1.1`; het is
  een achterwaarts verenigbare toevoeging, dus een afnemer die op het hoofdnummer pint
  merkt er niets van. Dezelfde overtreding in meerdere CFK-rapporten levert **een**
  melding met de klassen erbij. Een focusnode die niet zelf een put of streng is --
  het eindpunt van een leiding, de maaiveldorientatie van een put -- wordt via
  `hasPart`, `hasAspect` en als laatste `hasConnection` omhooggelopen tot het object
  waar hij bij hoort; op De Wolden herleidt daarmee 99,5% (105.385 van de 105.963),
  waar een strikt directe join op 87% was blijven steken. Komt hij nergens op uit --
  de 578 overtredingen op een stelsel of een klassenaam -- dan blijft de melding staan
  zonder object, zonder plek op de kaart en met een leeg gebied, en het rapport telt
  die gevallen expliciet -- ook als het er nul zijn. Op De
  Wolden leveren de drie rapporten samen 213.500 regels en na ontdubbeling 105.963
  meldingen (87.017 fouten, 18.946 waarschuwingen); de zwaarste posten zijn drie
  kardinaliteitsvormen die vrijwel elke inspectieput raken en die daardoor als
  systemisch gemarkeerd worden. Zie BO-28 (issue #12).

- RVZ-002 en RVZ-003 (W, Compleetheid): een overstortput zonder geregistreerd
  drempelniveau respectievelijk zonder geregistreerde drempelbreedte, ook als het
  `Overstortdrempel`-onderdeel zelf ontbreekt. De nulmeting kent geen vorm op die twee
  kenmerken, dus de schrapping rustte op niets; de sentinels zijn uit `dekking.toml`.
  Nieuwe regressietest: geen enkele geschrapte check mag in de referentiemeting ongeraakt
  blijven. Op De Wolden melden ze allebei alle 245 bekeken overstortputten (218
  `Overstortput` plus 27 `Stuwput`) -- de export bevat geen enkel
  `Overstortdrempel`-onderdeel. Zie BO-26 (issue #6).
- ATTR-013 (W, Compleetheid) en de vulwaarde-leesregel `dataset.markeer_vulwaarden`,
  geconfigureerd in `[vulwaarden]`: een hoogtekenmerk met |waarde| <= `hoogte_band_m`
  geldt als niet geregistreerd. De regel wordt na het laden toegepast, op een plek in
  `toetsrun`; de cache bewaart de ruwe parse. Op De Wolden vervallen daarmee 6.498 harde
  fouten en 3.647 waarschuwingen die op zo'n vulwaarde rustten (HGT-002 5.231 naar 2.128,
  HGT-003 2.813 naar 1.090, HGT-004 532 naar 31, HGT-018 1.190 naar 175, HGT-013 2.545
  naar 340, HGT-014 889 naar 157, HGT-007 2.126 naar 1.559, HGT-009 327 naar 282, en
  kleinere dalingen bij HGT-001, HGT-005, HGT-006, HGT-008 en NET-003); ATTR-013 meldt
  4.215 objecten. Er komt er geen bij, op twee HGT-009-bevindingen na: die check verliest
  er 47 en wint er 2, doordat een vulwaarde daar de werkelijke, kleinere BOB-sprong stond
  te verdringen. HGT-018 heeft nu een toelichting. De tabel met datakarakteristieken
  telt sindsdien alleen echte registraties -- een hoogte binnen de vulwaardeband staat
  niet meer als gevulde waarde in de noemer -- en het rapport zegt onder die tabel
  hoeveel waarden de leesregel heeft weggezet. Zie BO-27 (issue #1).
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
  `_WatergangKruising.kruisingen()` levert `_Kruising`-objecten (streng, geometrie en
  attributen van het waterdeel, laag, buffer) in plaats van tuples van vier waarden --
  de geometrie van het waterdeel is erbij gekomen en de velden hebben een naam
  gekregen. De eerste twee zijn additief.
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

- Checkregister v0.9: RVZ-002 en RVZ-003 zijn uit de tabel Geschrapte checks gehaald en
  gebouwd, ATTR-013 is toegevoegd, EXT-003 is gepreciseerd. De versieverwijzingen in code,
  configuratie en documentatie wijzen naar v0.9.
- Openstaand werk staat voortaan als GitHub-issue op `mcolee/nlriochecker` en niet meer in
  `CLAUDE.md` of in de open punten van het checkregister. Van de open punten van het
  register zijn 1, 9, 11 en 13 issues geworden en dragen ze nu een verwijzing daarheen;
  2 (drempelwaarden), 3 (ADM-003 als regex) en 6 (hoe overstorten in de export verschijnen)
  staan als afgehandeld gemarkeerd, elk met de plek waar dat te controleren is; en van
  punt 10 wordt het restant niet opgepakt -- er is geen Mds-nulmetingrapport beschikbaar,
  en daarmee valt het buiten scope -- wat er met de inhoud bij staat. Wat er onder
  punt 6 nog wel open stond -- dat `Overnamepunt` en een klasse voor het IT-stelsel niet in
  de GWSW-ontologie bestaan en de engine ze zelf invult -- is een eigen issue geworden; de
  twee verwijzingen in `checks.toml` wijzen daarheen in plaats van naar open punt 6. De
  nummering van de open punten is ongemoeid gelaten, omdat `checks.toml` en twee modules er
  bij nummer naar verwijzen.
- `bgt_waterlagen` bevat alleen nog `waterdeel`; `ondersteunendwaterdeel` valt buiten
  scope. Dat is de oever en niet het water zelf, en een streng die een slootkant raakt
  kruist geen watergang. Op De Wolden gaan EXT-002 en EXT-003 daarmee van 993 naar 859
  meldingen, wijzen er 195 een andere watergang aan dan voorheen, en komen er bij EXT-007
  drie bevindingen bij die een oever eerder afdekte. Binnen `waterdeel` telt elk type mee.
  Zie BO-24.
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
- `[vulwaarden]` weigert een kenmerk waarop de leesregel niet werkt: alleen
  `Maaiveldhoogte`, `Putdekselniveau`, `BobBeginpuntLeiding` en `BobEindpuntLeiding`
  (de verzameling staat als `VULWAARDE_KENMERKEN` bij `Vulwaarde` in `dataset.py`).
  Een tikfout in het hoofdlettergebruik gaf tot nu toe een run waarin de regel stil
  niets deed terwijl ATTR-013 meldde dat hij gold. `hoogte_band_m` heeft daarnaast een
  bovengrens van 0,5 m gekregen: dat is geen drempelkeuze maar een invoertoets, want een
  band in centimeters of millimeters leest elke BOB en elke maaiveldhoogte als ontbrekend,
  waarna dertien checks stilvallen en ATTR-013 elk object met een hoogte meldt.
- De toelichting van ATTR-013 telt hoeveel knopen en strengen met een vulwaarde buiten
  haar gemelde populatie vallen (persleidingen, drains, compartiment- en
  hulpstukorientaties). De leesregel raakt ze wel, geen enkele melding noemt ze; het
  getal komt per run uit de gemarkeerde dataset. Zie BO-27.

### Gerepareerd

- ATTR-006 zet de zijde (begin- of eindpunt) in de melding; de twee meldingen op een
  streng krijgen daarmee een eigen, stabiele ID in plaats van een volgnummer dat tussen
  runs kon verschuiven. **De melding-ID's van ATTR-006 verschuiven eenmalig**;
  `schema_versie` blijft 1.0 (issue #2).

- NET-004 noemt bij parallelle strengen de eerste op de kant (gesorteerd op URI) in plaats
  van de laatst ingelezen; de graafkanten dragen geen attributen meer. Twee parallelle
  strengen delen in een `DiGraph` een kantsleutel, dus de tweede `add_edge` overschreef de
  `uri` en het `label` van de eerste. De genoemde streng kan eenmalig verschuiven
  (issue #5).

- EXT-002 en EXT-003 delen een kruisingenlijst en melden in hun toelichting hoeveel
  duikers buiten de populatie vallen; de testfixtures volgen de ontologie (`Duiker` onder
  `Leiding`, `Zinker` onder `VrijvervalRioolleiding`). Geen verandering in de meldingen.
  Zie BO-25 (issue #3).

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
