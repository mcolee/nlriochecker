# Project: nlriochecker

## Doel
Python-package dat de datakwaliteit van vrijvervalriolering toetst in twee lagen:
1. Inlezen en analyseren van de GWSW-nulmeting, aangeleverd als SHACL-validatierapporten (apps.gwsw.nl/item_validate_shacl).
2. Eigen aanvullende checks conform het checkregister (data/checkregister-gwsw-nulmeting-v0_8.md) op de GWSW-dataset (OroX/TTL) en later externe bronnen.

We bouwen gefaseerd; implementeer nooit meer dan de actuele fase vraagt. Fase 1 en 2 (nulmeting inlezen, dekkinganalyse, trendvergelijking) en de kernset van fase 3 (TOP- en NET-checks) staan. Fase 4 is EXT: BGT, BAG, BRK en waterschapsdata uit data/gis/.

## Domeinregels (hard, uit het checkregister v0.8)
- De dataset moet ALTIJD aan alle conformiteitsklassen (CFK's) getoetst zijn: Hyd, MdsPlan EN MdsProj. Ontbreekt er een, dan faalt de pijplijn met een duidelijke foutmelding. De lijst staat in checks.toml, niet in de code.
- Typeringspoort: de SHACL-meting benoemt via de vorm `CfkTypes_typ` welke KLASSEN binnen een CFK te globaal zijn (niet welke objecten). De instanties volgen uit de OroX-dataset. Zonder dataset is er wel een klassenlijst maar geen score; verzin er dan geen.
- Alle drempelwaarden (toleranties, min/max-waarden, bufferafstanden) zijn configureerbaar per project via een configbestand (TOML). Geen hardcoded drempels.
- Check-ID's uit het checkregister (TOP-001 enz.) zijn stabiel; vervallen ID's worden nooit hergebruikt.
- Ernstniveaus: F = fout, W = waarschuwing. Elke check heeft een dimensietag (Consistentie, Compleetheid, Plausibiliteit, Actualiteit, Traceerbaarheid, Precisie). In de SHACL-rapporten komt de ernst uit de kolom Severity: Violation = F, Warning = W.

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

### Studiegebied (data/gis/)
- GeoPackage of GeoJSON, gelezen met stdlib sqlite3 plus shapely; geen extra afhankelijkheid. Moet in EPSG:28992 staan, net als de GWSW-coordinaten; herprojecteren doen we niet.
- Analyseer de kern plus een contextschil, rapporteer de kern. De schil is de
  samenhangende vrijvervalcomponent waar de kern in ligt plus een buffer om het gebied;
  precies zo groot dat NET-001 en NET-002 geen valse bevindingen geven. Zonder
  studiegebied draait alles op de volledige dataset. Meld altijd hoeveel bevindingen
  buiten het gebied vielen en hoe groot kern, schil en export zijn.

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
- Rapportage-output: Markdown, CSV en een GeoPackage naar een output-map; nooit invoerbestanden
  overschrijven. Alle drie komen uit dezelfde meldingenstroom (`uitvoer/melding.py`); een
  schrijver die zelf een `Finding` interpreteert laat de drie uit elkaar lopen.
- Elk uitvoerbestand draagt zijn herkomst: pakketnaam plus versie, uit
  `uitvoer/herkomst.py`. Dat is de enige schrijver in `src/`: `schrijf_markdown` zet de
  titel en de herkomstregel erboven, `schrijf_csv` de kolom `Gereedschap` achteraan, en
  de GeoPackage krijgt het veld `gereedschap` in `gwsw_run`. Roep nooit zelf `to_csv` of
  `write_text` aan -- de sweep in `tests/test_uitvoer_herkomst.py` verbiedt een tweede
  schrijver in `src/`, en die is de waarborg dat de drie uitvoervormen niet uit elkaar
  lopen.
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
- De QGIS-stijlen gaan mee in de tabel `layer_styles` van de GeoPackage, die zelf in
  `gpkg_contents` geregistreerd moet staan; zonder die rij vindt QGIS haar niet. Een QML
  los naast het bestand werkt niet bij meerdere lagen en leggen we dus niet neer.
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
- Bij twijfel over domeinlogica: raadpleeg eerst data/checkregister-gwsw-nulmeting-v0_8.md en de ontologie in data/gwsw_ontologieen/; verzin geen eigen interpretaties.
- Voer na elke wijziging ruff, mypy en pytest uit voordat je afrondt.
- Elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in
  `CHANGELOG.md`. `scripts/uitgave.py` weigert een uitgave met een lege sectie.
- Geloof onwaarschijnlijke uitkomsten niet. Duizenden bevindingen op een dataset wijzen meestal op een modelleerfout in de engine, niet op duizenden gebreken; zoek de oorzaak voordat je het cijfer rapporteert.
- Wat een check NIET heeft bekeken hoort in het rapport: objecten buiten de graaf, weggelaten bevindingen, ontbrekende typeringspoort. Stilte leest als "alles gecontroleerd".

## Open punten
- 1773 doodlopende eindknopen in De Wolden: het vrijverval watert af op 2148 knopen waarvan er maar 375 als uitstroompunt gelden. Bepaalt of NET-001 zinvolle uitkomsten geeft. Bij een afgebakende run raakt dit alleen de kern; de contextschil voorkomt dat de grens van het studiegebied zelf als doodlopend eindpunt meetelt.
- Bij de SHACL-meting komt de put-strengkoppeling in alle drie de CFK's voor, terwijl het register stelt dat die alleen uit Hyd komt (ADM-001).
- Er is geen SHACL-vorm voor Drempelniveau of Drempelbreedte; RVZ-002 en RVZ-003 gelden daardoor als niet geraakt terwijl ze juist geschrapt zijn omdat de nulmeting ze zou dekken.
- Negentien TOP- en NET-checks uit het register zijn nog niet gebouwd.
