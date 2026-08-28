# Architectuur en naslag — nlriochecker

Naslag bij het bouwen. `CLAUDE.md` draagt de harde regels en de werkwijze; dit bestand
draagt de geverifieerde feiten over de invoerbestanden en de engine/uitvoer-interna die je
alleen nodig hebt als je het betreffende deel aanraakt. De harde regels zelf (GWSW is
leidend, de drie ontologietoestanden van `toets`, één uitvoerschrijver, drempels
configureerbaar) staan in `CLAUDE.md`, niet hier — lees die eerst.

**De leeslaag leeft sinds 0.4 in `gwsw-orox-helpers`** (`gwsw_orox_helpers.dataset`,
`.graaf`, `.geometry`, `.ontologie`, `.cache`, `.voortgang`, `.bronnen`): het inlezen van
de OroX-TTL, de klassenhierarchie, de netwerkgraaf, de geometrie, de cache en het
voortgangsprotocol. De mechaniek die hieronder beschreven staat blijft onverkort gelden —
alleen het bestand waarin zij staat is verhuisd.

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
- De koppeling wijst naar de ORIENTATIE, niet naar het object, en kan naar een compartiment of hulpstuk wijzen; loop via hasPart omhoog tot een put. De BrutIS-export van De Wolden en Hoogeveen koppelt elk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een URI zonder type of aspect (1122 hulpstukken, 3024 koppelingen over 2165 strengen; nagemeten). De lader herstelt dat op naamstam -- alleen als het doel onbekend is én de stam een knoop met een Hulpstukorientatie is -- telt het in `GwswDataset.koppelingsherstel` en het rapport meldt het als datasetsignaal `SIG-hulpstukkoppeling` (issue #60). Let op wat het herstel NIET doet: het herstelde eind wijst naar het hulpstuk zelf, en dat is geen netwerkknoop en klimt via hasPart niet naar een put, dus `resolve_network_node` geeft er nog steeds `None` voor. TOP-022/TOP-023 zien die einden, en sinds issue #88 ook TOP-019: waar `resolve_network_node` niets oplevert valt die check terug op de rauwe `start_node`/`end_node`, zodat een T-stuk als functieloze knoop in beeld komt. De netwerkgraaf en de overige checks veranderden er geen bevinding door. TOP-002 en TOP-003 lezen sinds issue #89 dezelfde hulpstukpopulatie -- de hulpstukken met een telbare GWSW-functie tellen daar als geldig strengeinde (BO-72) -- maar geometrisch, via de snapping-tolerantie; dat staat los van de herstelde koppeling.
- De netwerkgraaf uit `checks/verbanden.py` bestaat sinds issue #72 uit twee lagen. `_Netwerk.graph` is het zuivere vrijverval, gericht van BeginpuntLeiding naar EindpuntLeiding; daarop draaien kringlopen (NET-004), stelseltypen (NET-005/006) en de afvoerpadanalyse (`afvoerpaden`). `_bereikbaarheid(context)` is diezelfde graaf plus het mechanische riool (`selectie.mechanischeleidingen`) als ONGERICHTE kanten -- een persleiding is pompgestuurd, dus haar administratieve richting telt niet mee, alleen haar connectiviteit. Alleen de bereikbaarheidsvraag leest die tweede laag: `_bereikbaar_vanaf` (NET-001/002), `_eindpunten` en `_eindpuntnotities`. Die laag wordt LUI gebouwd, in een eigen `context.cached`, en is met opzet geen veld op `_Netwerk`: wie hem opvraagt leest de rol `mechanischeleidingen` en moet die declareren, en zo blijft die declaratie beperkt tot NET-001, NET-002 en NET-008 in plaats van tot elke check die de graaf aanraakt. Waar `resolve_network_node` geen netwerkknoop oplevert valt de mechanische kant terug op de rauwe `Conduit.start_node`/`end_node`, zodat een hulpstuk een doorgeefknoop wordt in plaats van een breuk: het persnet komt samen op T-stukken, en die klimmen via hasPart niet naar een put. Op De Wolden en Hoogeveen hebben 1914 van de 3720 mechanische leidingen (51%) geen twee oplosbare knopen. De notities eromheen tellen bewust alleen vrijvervalknopen: `_richtingsverlies` neemt de samenhangende delen van de bereikbaarheidsgraaf (het gemaal kan buiten het vrijvervaldeel liggen) maar telt binnen zo'n deel alleen de knopen die ook in `graph` staan, want een hulpstuk of een knoop die uitsluitend aan het persnet hangt wordt door geen enkele NET-check beoordeeld. Zie BO-53 en BO-54.
- De BrutIS-export schrijft een gecompartimenteerde put per compartiment uit: elk deel wordt een eigen put op precies dezelfde coordinaat, met het putlabel plus (met spaties uitgevuld) `c1`, `c2`, ... Op De Wolden en Hoogeveen zijn dat 189 knopen in 98 groepen, onderling op 0,000 m. Voor de topologiechecks worden die sinds issue #85 samengevoegd -- in `_bouw_topologie` van `checks/topologie.py`, niet in de leeslaag. Welke checks de samengevoegde populatie zien (negen: zeven op `_Topologie.nodes`, plus TOP-002 en TOP-003 via de snapping) en wat er bewust ongemoeid blijft (de netwerkgraaf, de administratieve koppeling, de afbakening en de GIS-lagen) staat in BO-71.
- Klassen als Lozingspunt, Overnamepunt en UitlaatPunt zijn Knooppunt-subklassen en staan dus op de orientatie. Overnamepunt bestaat alleen in de totaal-ontologie, niet in de deelmodellen.
- Welke ontologie je laadt bepaalt de uitkomst; zonder eigen `--ontologie` is dat de gebundelde totaalontologie uit `gwsw-orox-helpers` (`bronnen.gebundelde_ontologie()`). Zonder ontologie valt de lader terug op herkenning via geometrie en meldt het verschil. (De drie toestanden van `toets` -- eigen pad, gebundeld, `--geen-ontologie` -- staan als harde regel in `CLAUDE.md`.)

### Studiegebied (data/gis_koekangerveld/, data/gis_dewoldenhoogeveen/)
- GeoPackage of GeoJSON, gelezen met stdlib sqlite3 plus shapely; geen extra afhankelijkheid. Moet in EPSG:28992 staan, net als de GWSW-coordinaten; herprojecteren doen we niet.
- Analyseer de kern plus een contextschil, rapporteer de kern. De schil is de
  samenhangende component waar de kern in ligt plus een buffer om het gebied; precies zo
  groot dat NET-001 en NET-002 geen valse bevindingen geven. Die component loopt sinds
  issue #73 over vrijverval EN persnet: de bereikbaarheid volgt sinds #72 de mechanische
  leidingen (BO-54) en een pompput is zelf geen eindpunt meer (BO-55), dus zonder het
  persnet in de schil valt het gemaal erachter buiten de analyseset. Zie BO-56 voor de
  meting (17 van de 88 buurten weken af) en de prijs (analyseset 1,7x). Zonder
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
- **De nulmetingmelding draagt twee teksten** (issue #101, BO-74): `boodschap` is de
  vastgestelde Nederlandse zin bij de SHACL-vorm, `boodschap_technisch` de tekst van de
  GWSW-server. De keuze valt in `nulbevinding.py` -- de enige plek waar `Source`,
  `Message` en `Value` bijeen staan -- en leest de vertaaltabel
  `nulmeting_teksten.toml`, een package-resource met de 43 vormen die de De
  Wolden-rapporten kennen. De sjabloonvelden `{min}`, `{max}` en `{n}` komen uit de
  meldingsrij zelf (`{min}`/`{max}` uit de grens achter de boodschap, `{n}` uit het
  getal waarmee `Value` opent); is een veld niet te vullen, dan vervalt de haakjesgroep
  eromheen. Een vorm zonder tekst valt terug op de technische boodschap en het rapport
  telt hoeveel meldingen dat waren. Wat waar landt: de mensgerichte views (het
  Markdown-rapport, de tabel per SHACL-vorm en de GeoPackage-popup) tonen alleen de zin,
  de drie archieven (CSV `MeldingTechnisch`, JSON `boodschap_technisch`, de kolom
  `boodschap_technisch` van de meldingentabel) dragen beide. Het melding-ID hangt aan de
  **technische** tekst, want die is ook de ontdubbelsleutel: zou het aan de zin hangen,
  dan verschoof elke nulmeting-ID zodra de tabel bijgewerkt werd. `drempel` blijft leeg,
  ook al vult de zin dezelfde grens in.
- Een derde bron in dezelfde stroom is het datasetsignaal (`bron = "dataset"`, categorie
  `SIG`): `_alle_meldingen` (binnen `bouw_meldingenstroom`) leest
  `uitvoer/omvang.klassen_op_nul` en maakt één systemische
  waarschuwing per klasse of rol waar een check op leunt maar die nul keer voorkomt
  (`SIG-nulklasse`, issue #22), en één voor de herstelde fantoomkoppeling naar
  hulpstukken (`SIG-hulpstukkoppeling`, `uitvoer/omvang.koppelingsherstel`, issue #60).
  Zonder object en zonder gebied, net als een onherleide nulmelding;
  systemisch, dus buiten `status` en `ergste_ernst` (BO-29). Het afvoereindpunt bewaakt
  per klasse (`Overnamepunt` is het criterium van BO-33), de andere rollen per rol.
  Vervalt zonder klassenhierarchie, want dan herkent `of_class` geen klassen.
- `bouw_meldingenstroom` past als laatste stap de onderdrukking uit `[rapport]` toe:
  `onderdruk_klassen` op het hoofdobject via `is_a` (nooit op `object2_uri`),
  `onderdruk_checks` op het check-ID, eerst op check en dan op klasse; een melding valt
  hooguit een keer weg. Hij geeft een `Meldingenstroom` terug (meldingen plus
  `Onderdrukking`) met twee tellingen die geen partitie zijn: `per_check` telt élke
  weggevallen melding onder haar check-ID -- precies het verschil met de kolom
  Bevindingen, ook als ze op klasse wegviel -- en `per_klasse` alleen het deel dat op
  klasse wegviel. `Onderdrukking.totaal` telt daarom alleen `per_check`. Wat wegvalt
  bereikt geen enkele schrijver. Het rapport (verantwoording), `totaal/synthese.md`,
  `gwsw_run` (`onderdruk_klassen`, `onderdruk_checks`, `meldingen_onderdrukt`) en de
  JSON-envelop (`onderdrukt`) dragen de telling; de CSV niet. Zie BO-49.
- Het bevindingenrapport van `toets` leest van gebied naar detail: gebiedsnaam als
  titel, aantallen (objecttype x stelseltype over de kern, leidingen ook in meters),
  managementsamenvatting (een regel per CFK plus de eigen checks; vinkje = nul fouten),
  rode draad, verantwoording, en dan detail in twee herkomstblokken -- eerst de
  nulmeting per SHACL-vorm, dan de eigen checks, elk met de fouten voorop. De
  aantallen komen uit `uitvoer/omvang.py`, de samenvatting uit
  `uitvoer/samenvatting.py`. Zie BO-31.
- De datakarakteristieken in de verantwoording openen sinds issue #91 met het aandeel
  putten zonder aanlegjaar ("44% van de putten draagt geen aanlegjaar"). Teller en noemer
  komen uit wat er al is: de ATTR-018-meldingen van díé uitvoer -- dus na afbakening en na
  de onderdrukking uit `[rapport]` -- en `uitvoer/omvang.putten_in_beeld`, de rol `putten`
  van de context waarop de checks draaiden, met een studiegebied tot de kern afgebakend.
  Geen tweede teller naast de check, en geen drempel: meldt ATTR-018 niets of staat er geen
  put in beeld, dan blijft de regel weg -- "0% van de putten" is geen karakteristiek. De
  meldingen per object blijven volledig bestaan, ook op putniveau; alleen de kop zegt wat
  ze samen betekenen. De check zelf (`checks/attributen.py`) verandert er niet door.
- Systemische bevindingen staan in het rapport en in de popup **generiek**, niet per
  object (issue #76): `_detail_eigen` vervangt hun rijen door een regel met check,
  aantal en bekeken populatie -- dezelfde vorm waarin het nulmetingblok per SHACL-vorm
  samenvat -- en `objectkaart.popup_html` laat ze weg en telt ze in een afsluitende
  regel. De scheiding gaat per melding (`Melding.systemisch`, zelf gedeclareerd of uit
  de populatieratio), dus een check waarvan maar een deel systemisch is toont de rest
  gewoon per object. De populatieratio geldt pas vanaf `[rapport]
  systemisch_minimum_bekeken` bekeken objecten (standaard 100): daaronder is zij geen
  uitspraak over de export maar een breuk van kleine getallen, en zou een echt gebrek
  in een klein gebied juist uit de mensgerichte views verdwijnen (BO-59). CSV, JSON en de meldingentabel van de GeoPackage houden elke rij
  met haar vlag: dat zijn archieven en een publiek contract, en alleen de mensgerichte
  views vouwen samen.
- **Wat `bekeken` telde staat erbij** (issue #77): elke `CheckOutcome` draagt
  `bekeken_scope` -- `analyseset`, `volledige_export` of `attribuut_instanties`, de enum
  `checks.base.Scope` -- en `populatie`, de gedeclareerde rollen van de check (zonder
  rollen: zijn kenmerken; zonder beide: leeg). `run_checks` leidt de scope af uit
  dezelfde beslissing die de check zijn dataset gaf (`over_volledige_populatie`) plus de
  klassevlag `Check.telt_instanties`, die staat op de twee checks waarvan `examined()`
  kenmerkinstanties telt in plaats van objecten (ATTR-014, BTR-006); die vlag wint, want
  "volledige export" zegt niets over een noemer in instanties. Zonder dat label mengt één
  kolom 95, 45.803 en 459.108, en deelt `percentage_populatie` in de GeoPackage door een
  getal waarvan de eenheid onbekend is. Het staat in de checktabel (kolommen Bekeken scope
  en Gaat over, met een voetnoot eronder), in de detailregel en de generieke systemische
  regel per check (`_bekeken_regel`), in `overzicht_checks` en in het optionele
  enveloppeveld `checks` van de JSON -- niet in de meldingen-CSV en niet in
  `totaal/bevindingen.json`. **`populatie` is geen noemer**: de declaratie is de vereniging
  van wat `run()`, `examined()` en `notes()` aanraken en dus een bovengrens, en zij staat
  daarom achter "gaat over" en niet achter het getal. Er is bewust geen terugval op "de
  hele export" -- die formulering hoort bij de regel "Toetst ...". Ook daar geldt zij
  sinds issue #96 niet meer voor elke rolloze check: `Check.populatie_omschrijving`
  (klassevariabele, overgenomen op `CheckOutcome`) laat zo'n check zijn deelpopulatie
  zelf in woorden noemen, en `_toetst_regel` in `uitvoer/bevindingen.py` zet die tekst op
  de plaats van de klassen. Zet het veld op een check zonder rollen die zijn objecten via
  engine-navigatie haalt (RVZ-011 loopt de overstortdrempel-index) of via de
  projectconfiguratie (ADM-007 leest `[[puttyperegels]]`); laat het leeg bij een check
  mét rollen -- daar komen de klassen uit de rollen en is de zin dode tekst -- en bij
  ATTR-014, die werkelijk de hele export op alle kenmerken langsloopt. Aan het veld
  `populatie` ("gaat over") verandert dit niets. Zie BO-58.
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
- De GeoPackage draagt sinds issue #98 precies drie featurelagen, een per geometrievorm:
  `putten` (punt), `strengen` (lijn) en `vlakken` (vlak). De twee objectlagen dragen de
  gebreken op het object. Elk object heeft `status` (precies vier waarden: rood, oranje,
  groen, grijs) en `popup_html` (een voorgebakken fragment, zonder stijlblok -- dat
  staat een keer in de maptip). Beide lagen dragen ook `begindatum_jaar` (het aanlegjaar
  uit `Begindatum`, leeg zonder datum; ATTR-018 meldt dat gat per object, issue #61).
  Grijs betekent: niet beoordeeld **en** niets gevonden;
  mechanisch riool wordt door de meeste checks overgeslagen maar niet door alle, en wat
  er wel op staat kleurt het object. **Elk** object van een klasse uit `[rapport]
  onderdruk_klassen` is grijs met de reden `REDEN_ONDERDRUKT` ("klasse onderdrukt in de
  projectconfiguratie; meldingen erop komen niet in de uitvoer"), ook een object waarop
  niets gevonden was: de reden hoort bij de klasse en niet bij weggevallen meldingen. Hij
  gaat vóór "mechanisch", want ook een niet-mechanische onderdrukte klasse hoort grijs te
  lezen en niet groen (BO-49). Met een studiegebied komt `Analyseset.buffer` als
  grijze ring mee -- niet de hele schil, die kan het halve net zijn. `status` telt
  systemische meldingen niet mee, net als `ergste_ernst`, en sinds issue #76 staan ze
  ook niet meer in de popup -- alleen geteld, in de afsluitende regel. `meldinglocaties` bestaat niet meer; de
  tabel `meldingen` draagt de foutlocatie in de kolommen `x` en `y`. De statusregel en
  de opmaak van de popup staan in `uitvoer/objectkaart.py`; `gpkg.py` levert alleen de
  feiten die alleen hij kent (stelsel, lengte, BOB-richting) als kant-en-klare regels
  aan. Op elke leiding uit de rol `mechanischeleidingen` (`[klassen] mechanisch`, de twee
  wortels `MechanischeRioolleiding` en `MechanischeTransportleiding` -- samen Drukleiding,
  Luchtpersleiding, Vacuumleiding, Persleiding, Leidingsegment en Spoelleiding) staat
  `richting_bob` altijd op `onbekend`, ook als zij een BOB-verval draagt: zij is
  pompgestuurd, dus dat verval zegt niets over de stroomrichting en een groene of rode pijl
  zou een richting tekenen die er fysiek niet is. Alleen de pijl vervalt -- `bob_verval_m`
  wordt gewoon berekend en blijft staan, want dat is een gemeten waarde. De beslissing zit
  in `_schrijf_features` en niet in `_richting_bob`: daar is de mechanische populatie
  bekend. De grijze `onbekend`-stijl wordt hergebruikt; alleen de popupregel splitst
  ("mechanische leiding -- geen vrijvervalrichting" in plaats van "BOB-richting niet te
  bepalen"), via een popup-only sleutel in `RICHTING_IN_WOORDEN` die géén kolomwaarde is.
  Zie issue #74 en BO-29.
- De laag `vlakken` (MULTIPOLYGON) draagt naast de rioleringslagen alles wat bij een
  melding hoort en geen punt of lijn is. Twee bronnen, één laag (BO-73, issue #98), en de
  kolom `soort` houdt ze uit elkaar. De eerste bron zijn de externe objecten waarnaar de
  meldingen van díé uitvoer verwijzen, gejoind op het
  trefferregister (`checks/treffers.py`) via `object2_uri` (BO-50, issue #67); hun
  `soort` scheidt de drie categorieën (`pand`, `bouwwerk`, `water`) en volgt op één plek
  uit `Treffer.bron` (`bgt_pand`/`bag_pand` → `pand`, `bgt_bouwwerk` → `bouwwerk`,
  `bgt_water` → `water`). `subtype` draagt voor water het BGT-`type` (waterloop, greppel;
  uit `Treffer.label`) en voor pand en bouwwerk het BGT-type uit `Treffer.attributen`;
  `relatie` en `afstand_min_m` gelden alleen voor pand en bouwwerk (EXT-001) en blijven
  leeg bij water. `check_ids` somt de checks op die naar het vlak wijzen; sinds EXT-002
  vervallen is (BO-66) draagt een watervlak altijd alleen EXT-003. De vroegere `buffer_m` vervalt --
  dat is runmetadata en staat in `gwsw_run` (`n_vlakken` telt de hele laag, de
  deelstelsels hieronder inbegrepen). De schrijver
  bevraagt zelf nooit een externe bron -- dan zouden laag en uitslag uit elkaar kunnen
  lopen. Eén beperking erft mee en blijft staan: EXT-001 meldt alleen het sterkste
  bouwwerk (BO-17). De watervlakken komen sinds issue #83 uitsluitend van EXT-003, dat
  het doorkruiste waterdeel zelf als treffer registreert (issue #67); een doorkruising
  door een als zinker geregistreerde streng is geen bevinding meer en krijgt dus ook geen
  vlak -- dat vlak hing aan het vervallen EXT-002 (BO-66). De watergangcheck geeft elke
  echte doorkruising per streng terug (de `break` na het eerste waterdeel is met BO-43
  vervallen). Zie ook BO-18.
- Aangeleverde externe bronnen worden bij het laden getoetst op dekking van
  `bronnen.studiegebied` (vectorlagen plus de grootste EXT-zoekafstand, het raster
  zonder marge). Een tekort boven `[bronnen] dekking_tolerantie_m` (standaard 0) is een
  harde fout: een te kleine bron geeft stilte in plaats van bevindingen. Ontbrekende
  bronnen blijven toegestaan. Zie BO-19.
- De tweede bron van `vlakken` is RVZ-006 (issue #75, BO-57; sinds issue #98 in deze laag
  in plaats van in een eigen vierde laag `gemengd_zonder_overstort`, BO-73): één vlak per
  gemengd deelstelsel waarop de check aansloeg, `soort = gemengd_deelstelsel`, als buffer
  (`[drempels] gemengd_zonder_overstort_buffer_m`, 10 m) om de vrijvervalstrengen van de
  hele samenhangende component. De rijen komen uit de **meldingen van díé uitvoer**,
  gegroepeerd op `cluster_id` -- dezelfde strikte aansluiting als bij de externe vlakken,
  zodat de laag na afbakening of onderdrukking niet meer kan tonen dan de uitslag; de
  geometrie komt uit `run.context`, de graaf waarop de check draaide. Zo'n rij vult wat zij
  kent en laat de rest leeg, net zoals `relatie` en `afstand_min_m` bij water leeg blijven:
  `id` en `label` dragen het deelstelsel-ID dat RVZ-006, NET-001 en NET-002 delen (waarop
  de meldingentabel te koppelen is), `aantal_meldingen` telt de meldingen (één per gemengde
  streng), `check_ids` staat op `RVZ-006`, en `n_knopen`, `n_strengen`, `strenglengte_m` en
  `popup_html` gelden uitsluitend voor deze soort -- `subtype`, `bron`, `bronbestand`,
  `relatie` en `afstand_min_m` blijven leeg. Die popup is
  de enige die systemische meldingen wél toont en zijn status niet uit `bepaal_status`
  haalt: zo'n rij bestaat alleen omdat RVZ-006 aansloeg en is per constructie
  een gebrek (BO-59). `gwsw_run`
  telt deze rijen apart in `n_gemengd_zonder_overstort`, naast `n_vlakken` dat de hele laag
  telt; het aantal externe vlakken is het verschil. Twee dingen kunnen er minder vlakken
  opleveren dan er gemelde deelstelsels zijn, en
  ze worden verschillend behandeld. Een `cluster_id` die de graaf van de run niet kent is
  een **harde fout** (`PipelineError`): de check en de schrijver lezen dezelfde
  `deelstelsel_ids` van dezelfde context, dus dat is een interne tegenspraak en geen
  datatoestand -- dezelfde lijn als `_trefferrijen` bij een niet-geregistreerde
  treffer. Een deelstelsel waarvan geen enkele streng een bruikbare lijn draagt is wél een
  datatoestand: er valt niets te tekenen, dus het krijgt geen rij, maar het wordt geteld
  in de kolom **`n_gemengd_zonder_vlak`** van `gwsw_run`. Zonder die telling zou "dit
  deelstelsel bestaat niet" niet van "we konden het niet tekenen" te onderscheiden zijn.
  De meldingen zelf staan hoe dan ook in de meldingentabel en op hun eigen streng in
  `strengen`. De vroegere laag `stelsels` (#25) bestaat niet meer: zij groepeerde
  strengen via de GWSW-stelselregistratie, en die
  groepering is niet betrouwbaar. Gevolg voor de nulmeting: een SHACL-overtreding waarvan
  de focusnode een geregistreerd stelsel is houdt haar stelsel als `object_uri` maar krijgt
  géén kaartobject; het rapport telt haar samen met de `CfkTypes_typ`-klassenamen in de
  regel "geen kaartobject" (op De Wolden 567 van de 578).
- De QGIS-stijlen gaan mee in de tabel `layer_styles` van de GeoPackage, die zelf in
  `gpkg_contents` geregistreerd moet staan; zonder die rij vindt QGIS haar niet. Een QML
  los naast het bestand werkt niet bij meerdere lagen en leggen we dus niet neer.
- De stijlen van `putten` en `strengen` worden opgebouwd uit de tabel in
  `uitvoer/stijlen/symbolen.py` (regelstructuur objecttype x status, ruim honderd
  bladregels); `vlakken.qml` (rule-based op `soort`, met vier regels: pand, bouwwerk,
  water en gemengd deelstelsel) blijft een bestand. Het symbool volgt het
  GWSW-objecttype, de kleur
  uitsluitend de kolom `status`. Een stijl
  draagt alleen regels voor de objecttypen die in zijn laag staan; met de hele tabel
  krijgt de lagenboom van QGIS ruim tweehonderd legendaregels. De maptip is een
  expressie van een regel op `popup_html`; op `vlakken` kiest die expressie per rij:
  een deelstelsel toont zijn voorgebakken `popup_html`, een extern vlak (dat die kolom
  leeg laat) krijgt zijn tekst uit de kolommen. Het stijlblok staat in de QML en niet in
  elke rij. `styleCategories` moet `MapTips` noemen, anders leest QGIS het element niet
  terug. Zie BO-30.
- `tests/test_uitvoer_qgis.py` vindt PyQGIS door de systeem-site-packages achter
  deze (van het systeem afgeschermde) venv aan `sys.path` te plakken; zonder QGIS
  op de machine slaat hij gewoon over. Zie de moduledocstring van dat bestand voor
  hoe dat pad afgeleid wordt en `GWSW_QGIS_SITE_PACKAGES` om het te overschrijven.

## Cache en voortgang

Deze laag leeft sinds 0.4 in `gwsw-orox-helpers` (`gwsw_orox_helpers.cache` en
`.voortgang`); de mechaniek hieronder blijft gelden.

- De geparseerde dataset wordt gecachet (`~/.cache/gwsw-orox-helpers`, `--geen-cache` om
  hem over te slaan). De sleutel bevat de broncode van de lader; wie `dataset.py`,
  `geometry.py`, `ontologie.py` of `graaf.py` in die package wijzigt, krijgt vanzelf een
  nieuwe cache.
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
