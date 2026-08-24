# Architectuur en naslag — nlriochecker

Naslag bij het bouwen. `CLAUDE.md` draagt de harde regels en de werkwijze; dit bestand
draagt de geverifieerde feiten over de invoerbestanden en de engine/uitvoer-interna die je
alleen nodig hebt als je het betreffende deel aanraakt. De harde regels zelf (GWSW is
leidend, `toets` eist `--ontologie`, één uitvoerschrijver, drempels configureerbaar) staan
in `CLAUDE.md`, niet hier — lees die eerst.

## Feiten over de invoerbestanden (geverifieerd)

### SHACL-nulmetingrapporten (data/shacl_nulmeting/)
- CSV met puntkomma (;) als scheidingsteken, encoding utf-8.
- Kopblok van sleutel;waarde-paren met onder meer "SHACL-meting op basis CFK", "Gevalideerd RDF-bestand" en "Rapport 'conforms'". Daaronder de kolomkop; zoek die op de regel die met `Focus node` begint, niet op een vast regelnummer.
- Kolommen: Focus node;Source;Value;Severity;Message;Path;Detail-message;Detail-value
- `Focus node` is het URI-fragment uit de dataset en joint direct op de OroX-TTL. `Source` is de naam van de geschonden SHACL-vorm (bijvoorbeeld `LengteLeiding_val`). Uit `Detail-value` zijn `type=` en `label=` te halen; die ontbreken soms, en dan blijven ze leeg.
- Een regel per overtreding; er is geen aggregatiegewicht.

### OroX-dataset (data/gwsw_orox_ttl/)
- Turtle hoort utf-8 te zijn, maar de BrutIS-export van De Wolden en Hoogeveen bevat een handvol CP850-bytes in straatnamen. De lader valt terug op een instelbare codering en meldt dat expliciet; nooit stilzwijgend tekens vervangen.
- Een knoop is een object met een orientatie van het type `Knooppunt` (Putorientatie, Bouwwerkorientatie, Compartimentorientatie, Hulpstukorientatie, Aansluitpunt, Afvoerpunt en verder). Een verbinding is een orientatie van het type `Verbinding`. Herken ze daaraan, niet aan hun geometrie: een knooppunt mag geen punt hebben.
- `gwsw:hasConnection` is een owl:SymmetricProperty zonder inverse; lees beide schrijfrichtingen.
- De koppeling wijst naar de ORIENTATIE, niet naar het object, en kan naar een compartiment of hulpstuk wijzen; loop via hasPart omhoog tot een put. De BrutIS-export van De Wolden en Hoogeveen koppelt elk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een URI zonder type of aspect (1122 hulpstukken, 3024 koppelingen). De lader herstelt dat op naamstam -- alleen als het doel onbekend is én de stam een knoop met een Hulpstukorientatie is -- telt het in `GwswDataset.koppelingsherstel` en het rapport meldt het als datasetsignaal `SIG-hulpstukkoppeling` (issue #60).
- Klassen als Lozingspunt, Overnamepunt en UitlaatPunt zijn Knooppunt-subklassen en staan dus op de orientatie. Overnamepunt bestaat alleen in de totaal-ontologie, niet in de deelmodellen.
- Welke ontologie je laadt bepaalt de uitkomst; gebruik data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl. Zonder ontologie valt de lader terug op herkenning via geometrie en meldt het verschil. (De harde eis dat `toets` `--ontologie` krijgt, staat in `CLAUDE.md`.)

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

## Meldingenstroom en rapport
- De SHACL-nulmeting is naast het checkregister een tweede bron in diezelfde
  meldingenstroom: `nulbevinding.py` maakt van elke overtreding een `Nulbevinding` met
  `bron = "nulmeting"`, categorie `NULMETING` en het veld `cfk`, en `bouw_meldingen`
  maakt er meldingen van. Geen `CheckOutcome`, geen tweede schrijver. De focusnode
  wordt via `hasPart`, `hasAspect` en als laatste `hasConnection` omhooggelopen tot een
  put of streng; komt hij nergens op uit, dan blijft de melding staan zonder object en
  met een leeg gebied, en het rapport telt die gevallen. Zie BO-28.
- Een derde bron in dezelfde stroom is het datasetsignaal (`bron = "dataset"`, categorie
  `SIG`): `bouw_meldingen` leest `uitvoer/omvang.klassen_op_nul` en maakt één systemische
  waarschuwing per klasse of rol waar een check op leunt maar die nul keer voorkomt
  (`SIG-nulklasse`, issue #22), en één voor de herstelde fantoomkoppeling naar
  hulpstukken (`SIG-hulpstukkoppeling`, `uitvoer/omvang.koppelingsherstel`, issue #60).
  Zonder object en zonder gebied, net als een onherleide nulmelding;
  systemisch, dus buiten `status` en `ergste_ernst` (BO-29). Het afvoereindpunt bewaakt
  per klasse (`Overnamepunt` is het criterium van BO-33), de andere rollen per rol.
  Vervalt zonder klassenhierarchie, want dan herkent `of_class` geen klassen.
- Het bevindingenrapport van `toets` leest van gebied naar detail: gebiedsnaam als
  titel, aantallen (objecttype x stelseltype over de kern, leidingen ook in meters),
  managementsamenvatting (een regel per CFK plus de eigen checks; vinkje = nul fouten),
  rode draad, verantwoording, en dan detail in twee herkomstblokken -- eerst de
  nulmeting per SHACL-vorm, dan de eigen checks, elk met de fouten voorop. De
  aantallen komen uit `uitvoer/omvang.py`, de samenvatting uit
  `uitvoer/samenvatting.py`. Zie BO-31.
- De runbrede markering boven een rapport wordt samengesteld in
  `uitvoer/voorbehoud.py`, en nergens anders. Er kan meer dan een voorbehoud tegelijk
  gelden -- een `--cfk`-deelset op een run met `--geen-ontologie` -- en
  `schrijf_markdown` heeft maar een markeringsslot; roept een schrijver
  `meetbereik.markering()` rechtstreeks aan, dan verdwijnt het andere voorbehoud
  stilzwijgend. Markdown, de kolom `markering` in `gwsw_run` en het optionele veld
  `markering` in de JSON-envelop dragen dezelfde samengestelde tekst; de CSV bewust
  geen enkel voorbehoud.
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

## GeoPackage en QGIS
- De GeoPackage draagt twee objectlagen: `putten` (punt) en `strengen` (lijn), met de
  gebreken op het object. Elk object heeft `status` (precies vier waarden: rood, oranje,
  groen, grijs) en `popup_html` (een voorgebakken fragment, zonder stijlblok -- dat
  staat een keer in de maptip). Beide lagen dragen ook `begindatum_jaar` (het aanlegjaar
  uit `Begindatum`, leeg zonder datum; ATTR-018 meldt dat gat per object, issue #61).
  Grijs betekent: niet beoordeeld **en** niets gevonden;
  mechanisch riool wordt door de meeste checks overgeslagen maar niet door alle, en wat
  er wel op staat kleurt het object. Met een studiegebied komt `Analyseset.buffer` als
  grijze ring mee -- niet de hele schil, die kan het halve net zijn. `status` telt
  systemische meldingen niet mee, net als `ergste_ernst`. `meldinglocaties` bestaat niet meer; de
  tabel `meldingen` draagt de foutlocatie in de kolommen `x` en `y`. De statusregel en
  de opmaak van de popup staan in `uitvoer/objectkaart.py`; `gpkg.py` levert alleen de
  feiten die alleen hij kent (stelsel, lengte, BOB-richting) als kant-en-klare regels
  aan. Zie BO-29.
- De GeoPackage draagt naast de rioleringslagen `bouwwerken` (EXT-001) en
  `waterdelen_zonder_zinker` (EXT-003): de externe objecten waarnaar de meldingen van
  díé uitvoer verwijzen, gejoind op het trefferregister (`checks/treffers.py`) via
  `object2_uri`. De schrijver bevraagt zelf nooit een externe bron -- dan zouden laag en
  uitslag uit elkaar kunnen lopen. Eén beperking erft mee en blijft staan: EXT-001
  meldt alleen het sterkste bouwwerk (BO-17). De watergangcheck geeft elke echte
  doorkruising per streng terug; de `break` na het eerste waterdeel is met BO-43
  vervallen. Zie ook BO-18.
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
  symbool volgt het GWSW-objecttype, de kleur uitsluitend de kolom `status`. Een stijl
  draagt alleen regels voor de objecttypen die in zijn laag staan; met de hele tabel
  krijgt de lagenboom van QGIS ruim tweehonderd legendaregels. De maptip is een
  expressie van een regel op `popup_html`; het stijlblok staat in de QML en niet in
  elke rij. `styleCategories` moet `MapTips` noemen, anders leest QGIS het element niet
  terug. Zie BO-30.
- `tests/test_uitvoer_qgis.py` vindt PyQGIS door de systeem-site-packages achter
  deze (van het systeem afgeschermde) venv aan `sys.path` te plakken; zonder QGIS
  op de machine slaat hij gewoon over. Zie de moduledocstring van dat bestand voor
  hoe dat pad afgeleid wordt en `GWSW_QGIS_SITE_PACKAGES` om het te overschrijven.

## Cache en voortgang
- De geparseerde dataset wordt gecachet (`~/.cache/nlriochecker`, `--geen-cache` om hem
  over te slaan). De sleutel bevat de broncode van de lader; wie `dataset.py`,
  `geometry.py`, `ontologie.py` of `graaf.py` wijzigt, krijgt vanzelf een nieuwe cache.
  De cachemap groeit per sleutel (op De Wolden en Hoogeveen circa 120 MB, waarvan de
  graafpickle 91 MB); oude sleutels worden niet automatisch opgeruimd.
- Voortgang bij de zware stappen loopt via het protocol in `voortgang.py`, met
  `NUL_VOORTGANG` als standaardwaarde. Geinstrumenteerd zijn `load_dataset`,
  `laad_nulmeting`, `run_checks` en `schrijf_geopackage`; bij een cachetreffer start er
  geen laadfase, want er wordt niets geparseerd. Voortgang is weergave: geen check leest
  er state uit en geen aanroep mag de uitkomst van een run raken. De CLI-adapter staat
  in `cli.py`, schrijft naar stderr en zet het staplabel via `item_show_func` -- niet
  door `balk.label` te overschrijven, want dan echoot click in een niet-interactieve
  omgeving een regel per stap.
