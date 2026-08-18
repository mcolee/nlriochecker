# Ontwerp ronde 2: rapportage per studiegebied-feature

Bron: `masterinstructie-claude-code-nlriochecker.md`, ronde 2. Ronde 1 (CFK-keuze,
JSON-export, voortgang) is afgerond en gecommit; dit ontwerp leunt op het
JSON-schema en het voortgangsprotocol daaruit.

Doel: bevat het studiegebiedbestand meerdere features, dan rapporteert `toets` per
feature — een eigen submap met alle vier de uitvoervormen — plus één totaalsynthese.
Het bestand wordt vooraf streng gevalideerd. Eén feature verandert niets.

## 1. Geverifieerde feiten

Alles hieronder is in de code nagekeken, niet aangenomen.

1. `StudyArea` (`studiegebied.py`) is bevroren en draagt `name`, `geometry`,
   `source`, `feature_count`, `gebied`. `load_study_area` uniet alle geometrieën van
   de laag tot één vlak; er is nu geen enkele plek die per feature kijkt.
2. `load_study_area` heeft twee bellers: `cli.py` (`toets`) en
   `externedata._lees_studiegebied` (die alleen de omhullende van de bron nodig heeft).
3. `bouw_analyseset(dataset, area, config)` bouwt kern, contextschil en uitgedunde
   dataset. `_component` bouwt de vrijvervalgraaf over de **volledige** dataset en
   selecteert daarna de componenten die de kern raken; de graafbouw is dus al
   gebiedsonafhankelijk.
4. `objecten_in_gebied` en `_binnen_buffer` lopen elk lineair over alle knoop- en
   strenggeometrieën; met 80 buurten is dat 80 volledige doorlopen.
5. `CheckRun.beperk_tot_studiegebied(area)` bakent na afloop tot de kern af en telt
   `weggelaten` per check.
6. `melding_id` (`uitvoer/identiteit.py`) is `sha256(check|object|object2|sleutels)`;
   het gebied komt er niet in voor. Dat is precies wat ronde 2 nodig heeft, en het
   wordt met een test vastgelegd zodat het niet ongemerkt verandert.
7. `Melding.gebied` wordt gevuld uit `run.study_area.gebied`; `scope` uit het al of
   niet aanwezig zijn van een gebied.
8. `schrijf_uitvoer` (`uitvoer/__init__.py`) schrijft de vier vormen naar één map uit
   één meldingenlijst. `schrijf_markdown`, `schrijf_csv` en `schrijf_json`
   (`uitvoer/herkomst.py`) zijn de enige schrijvers; `tests/test_uitvoer_herkomst.py`
   bewaakt dat.
9. `CheckContext.volledige_context()` maakt per context een **nieuwe** volledige
   context met een lege cache. Per gebied opnieuw aanroepen betekent per gebied
   opnieuw `bepaal_karakteristiek` over de volledige export en per gebied opnieuw de
   volledige topologie-index voor ADM-002. Dat is de duurste verborgen post van een
   80-buurtenrun.
10. De GIS-fixtures (`tests/fixtures/gis/*.geojson`) zijn kale geometrieobjecten met
    lokale coördinaten rond (1000, 2000) — ver buiten de RD-bounds. De TTL-fixtures
    delen dat assenstelsel; TOP-009-tests verlagen daarvoor `drempels.rd_y_min`.
11. `drempels.rd_x_min/rd_x_max/rd_y_min/rd_y_max` bestaan al in `checkconfig.py` en
    worden door TOP-009 gebruikt. Er komt geen tweede plek met RD-grenzen bij.
12. `shapely` is 2.1.2; `shapely.STRtree` is beschikbaar zonder nieuwe afhankelijkheid.

## 2. Ontwerpbesluiten

### 2.1 De RD-bounds-heuristiek botst met de bestaande fixtures (opgelost)

Het masterdocument eist voor GeoJSON een harde error als de coördinaten buiten de
RD-bounds vallen, én dat de bestaande tests ongewijzigd groen blijven. Die twee
kunnen niet allebei letterlijk: elke GeoJSON-fixture in deze repository ligt op
(±1000, ±2000) en zou door de nieuwe poort vallen — drie CLI-tests, `test_afbakening`,
`test_reporting`, `test_uitvoer_gpkg`, `test_uitvoer_melding` en
`test_uitvoer_synthese` erbij.

Het masterdocument biedt zelf de uitweg: een bestand wordt óók geaccepteerd als een
legacy `crs`-member expliciet EPSG:28992 noemt. De fixtures krijgen die member:

```json
{ "type": "Polygon",
  "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::28992" } },
  "coordinates": [[[990, 1990], …]] }
```

Dat is een wijziging in de **fixturebestanden**, niet in de tests: geen enkele
testregel gaat op de schop, en de fixtures zeggen nu expliciet wat ze altijd al
beweerden — dat hun lokale assenstelsel voor RD doorgaat, net als de TTL-fixtures.
De heuristiek zelf wordt onverkort gebouwd zoals gevraagd.

Uitzondering: `tests/test_studiegebied.py::test_geojson` schrijft zijn eigen GeoJSON
in `tmp_path` met coördinaten 0–100. Die ene testhelper krijgt dezelfde `crs`-member;
dat is een test over precies dit contract, dus hij hoort mee te bewegen.

### 2.2 De grenzen komen mee als parameter, niet als import

`studiegebied.py` krijgt geen `CheckConfig`-import. `load_studiegebieden` en
`load_study_area` krijgen een keyword `grenzen: RdGrenzen | None = None` (een
`NamedTuple` van vier floats). `None` betekent: geen CRS-heuristiek op GeoJSON — de
beller kent de grenzen niet, en een verzonnen grens is erger dan geen. De CLI kent
de config en geeft ze altijd mee; `externedata` (dat alleen een omhullende nodig
heeft, in de praktijk uit een GeoPackage met echte `srs_id`) laat ze weg.

De GeoPackage-route houdt haar bestaande exacte `srs_id == 28992`-toets en heeft de
heuristiek niet nodig.

### 2.3 Eén loop voor nul, één en veel gebieden

De CLI krijgt geen drie takken. `toetsloop.toets_gebieden(...)` levert altijd een
`list[GebiedsRun]`:

- geen `--studiegebied` → één `GebiedsRun` met `gebied=None`;
- één feature → één `GebiedsRun` met dat gebied;
- N features → N `GebiedsRun`s.

De schrijflaag beslist op de lengte: één run schrijft naar de uitvoermap zelf
(byte-voor-byte zoals nu, geen submap, geen synthese), meer runs schrijven per gebied
in een submap plus `totaal/`. Zo kan het enkelvoudige geval niet uit de pas lopen met
het meervoudige: het is dezelfde code.

### 2.4 Wat wél gedeeld wordt over gebieden, en waarom dat veilig is

De equivalentie-eis (per gebied dezelfde meldingen als bij een losse run) staat
voorop. Gedeeld wordt uitsluitend wat aantoonbaar niet van het gebied afhangt:

| Gedeeld | Waarom veilig |
|---|---|
| De geparseerde dataset en ontologie | Invoer; hangt niet van het gebied af. Laden kost ruim drie minuten. |
| De SHACL-inlezing en de typeringspoort | Gaan over de volledige export; het gebied speelt er geen rol in. |
| `STRtree` over alle knoop- en strenggeometrieën | Zuivere opzoekstructuur, levert alleen kandidaten; het antwoord komt onveranderd van `area.bevat`. |
| De vrijvervalcomponenten van het volledige net | `_component` bouwt de graaf nu al over de volledige dataset; alleen de selectie *welke* component de kern raakt is gebiedsafhankelijk, en die blijft per gebied. |
| De volledige-export-`CheckContext` (één instantie, dus één cache) | Hangt af van volledige dataset, config en de onbetrouwbare objecten — alle drie gebiedsonafhankelijk. Hierin zitten de karakteristiek en de topologie-index voor ADM-002. |

Nooit gedeeld: de per-gebied `CheckContext` en alles in zijn cache (topologie-index,
netwerkgraaf) — die hangen aan de uitgedunde dataset van dát gebied.

De uitgestelde optimalisatie (lokale checks één keer over de unie draaien) wordt
**niet** gebouwd; zie beslislog. De voortgangsfasen dragen de gebiedsnaam, zodat de
meting op de 80-buurtencasus later mogelijk is.

### 2.5 Dubbeltelling, en wat de synthese daarover zegt

`StudyArea.bevat` blijft `intersects`: elk gebied ziet zijn eigen volledige
werkelijkheid. Er wordt niet ontdubbeld tussen gebieden. De totaalsynthese telt
unieke `melding_id`'s en noemt apart hoeveel meldingen in meer dan één gebied
voorkomen, zodat de som der delen verklaarbaar afwijkt van het totaal.

### 2.6 De totaal-uitvoer is dezelfde uitvoer, niet een nieuwe vorm

`totaal/` bevat `synthese.md` (het overzicht over de gebieden), plus
`bevindingen.csv` en `bevindingen.json` met de **unieke** meldingen — precies dezelfde
kolommen en hetzelfde JSON-contract als een gewone run. Geen nieuwe schrijver, geen
tweede tabelvorm: `meldingen_tabel` en `meldingen_json` worden hergebruikt, en de
drie bestanden lopen via `schrijf_markdown` / `schrijf_csv` / `schrijf_json`.

Ontdubbelen gebeurt op `melding_id`, eerste voorkomen wint bij oplopende
gebiedsnaam. De `Gebied`-kolom van zo'n rij noemt dus één van de gebieden; de
synthese vermeldt dat expliciet en geeft het aantal meervoudige meldingen.

Geen GeoPackage in `totaal/`: de featurelagen zijn per gebied afgebakend en een unie
ervan zou objecten dubbel bevatten of stilzwijgend ontdubbelen. Wie het geheel in GIS
wil, opent de per-gebied-bestanden naast elkaar. Dit staat in de README.

## 3. Datamodel

```python
@dataclass(frozen=True)
class Studiegebieden:
    """Alle features van een studiegebiedbestand, elk als eigen StudyArea."""

    gebieden: tuple[StudyArea, ...]
    source: Path
    laag: str
    overgeslagen: tuple[str, ...] = ()  # meldingen over niet-polygonen
    beschikbaar: tuple[str, ...] = ()  # alle namen in het bestand, vóór --gebied

    @property
    def enkel(self) -> bool: ...  # precies één feature
    @property
    def totaal(self) -> StudyArea: ...  # de unie, voor wie het geheel nodig heeft
    def selecteer(self, namen: Sequence[str]) -> Studiegebieden: ...
```

`StudyArea` blijft ongewijzigd. Per feature geldt:

- meerdere features: `name = naam_gebied`, `gebied = naam_gebied`, `feature_count = 1`;
- één feature: `name` en `gebied` exact zoals nu (`<stem>:<laag>` respectievelijk de
  `statcode statnaam`-terugval), behalve dat een aanwezige en gevulde `naam_gebied`
  de gebiedsaanduiding wordt.

`load_study_area(path, laag, *, grenzen=None)` blijft bestaan en levert
`load_studiegebieden(...).totaal`. Bestaande bellers en tests merken niets — met één
uitzondering: een multi-feature bestand zónder `naam_gebied` is voortaan ook langs
deze weg een fout. Dat is bedoeld; validatie mag niet afhangen van welke ingang je kiest.

## 4. Validatie (`studiegebied.py`)

Alle fouten via `StudyAreaError`, met pad, laag en oorzaak. Volgorde:

1. **CRS.** GeoPackage: `srs_id == 28992` (bestaand). GeoJSON: legacy `crs`-member die
   EPSG:28992 noemt (`urn:ogc:def:crs:EPSG::28992` of `EPSG:28992`, hoofdletterloos
   vergeleken) → goed; anders, mits `grenzen` meegegeven is, moeten alle coördinaten
   binnen de RD-bounds vallen. Buiten bereik: harde error die de gevonden omhullende
   noemt en meldt dat het bestand vermoedelijk in WGS84 staat en eerst
   geherprojecteerd moet worden.
2. **Geometrietypen.** Alleen `Polygon` en `MultiPolygon` worden geladen.
   `GeometryCollection` wordt níét uitgepakt. Overgeslagen typen worden geteld per
   type, gemeld via de logger én meegegeven in `Studiegebieden.overgeslagen` zodat de
   samenvattende uitvoer ze noemt. Nul polygonen over: harde error.
3. **`naam_gebied`.** Alleen vereist als er ná filtering meer dan één feature is:
   kolom/property moet bestaan (anders error die de gevonden kolommen opsomt),
   waarde niet-leeg na `strip()` (error met rijnummer of feature-index), waarden
   uniek (error die de dubbele naam noemt).
4. **Mapnaambotsing.** De sanering van twee verschillende namen mag niet dezelfde
   mapnaam opleveren; anders harde error die beide namen noemt.

`mapnaam(naam)` staat in `studiegebied.py`, waar de botsingscontrole hem nodig heeft:
diakrieten strippen (`unicodedata.normalize("NFKD")`), lowercase, alles buiten
`[a-z0-9]` naar `_`, opeenvolgende `_` samenvoegen, randen strippen. Levert de
sanering een lege string op (een naam van enkel leestekens), dan is dat eveneens een
harde error — een naamloze map is geen uitvoer. In rapporttitels, de `Gebied`-kolom
en de JSON blijft de originele naam staan.

## 5. Selectie `--gebied`

Nieuwe meervoudige optie op `toets`. Het volledige bestand wordt altijd eerst
gevalideerd, daarna pas geselecteerd: een deelrun mag geen defect bestand maskeren.
Matching is exact op de originele `naam_gebied`. Onbekende naam → harde error met de
beschikbare namen; bij meer dan tien namen het aantal plus de dichtstbijzijnde
suggesties (`difflib.get_close_matches`, stdlib). `--gebied` op een bestand zonder
`naam_gebied` is een fout die uitlegt dat selectie die kolom vereist. De synthese
vermeldt dat het een selectie betreft, welke, en hoeveel gebieden het bestand telde.

## 6. Prestatie

### 6.1 Ruimtelijke index

```python
@dataclass(frozen=True)
class GedeeldeIndex:
    boom: STRtree
    uris: tuple[str, ...]
    componenten: list[set[str]]
    component_van: dict[str, int]
    strengen: tuple[tuple[str, str], ...]
    zonder_netwerkverband: int
```

`bouw_gedeelde_index(dataset, config)` bouwt hem één keer. `bouw_analyseset` krijgt
een keyword `gedeeld: GedeeldeIndex | None = None` en bouwt hem zelf als hij ontbreekt
— één losse run gedraagt zich dus identiek.

De boom levert **kandidaten**, niet het antwoord: na de bbox-query blijft
`area.bevat(...)` het oordeel geven, precies zoals nu. Een bbox-query is per
constructie een superset van de snijdende geometrieën, dus de uitkomst kan niet
verschillen — ook niet bij de ongeldige geometrieën die deze dataset bevat
(TOP-016). Datzelfde geldt voor de bufferstap.

### 6.2 Componenten

De vrijvervalgraaf, de componenten en `zonder_netwerkverband` worden één keer
berekend. Per gebied blijft alleen de selectie over: welke componenten raakt deze
kern. Dat is letterlijk de bestaande code, met de graafbouw eruit gelicht.

### 6.3 Gedeelde volledige-export-context

`CheckContext` krijgt een veld `gedeelde_volledige_context: CheckContext | None = None`.
`volledige_context()` levert die terug als hij gezet is, in plaats van er een nieuwe
met lege cache te maken. De toetsloop bouwt hem één keer en geeft hem aan elke
gebiedscontext mee. Daarnaast gaat `bepaal_karakteristiek` in `run_checks` via
`cached("karakteristiek", …)` op die volledige context, zodat hij één keer per run
draait in plaats van één keer per gebied.

`run_checks` krijgt een keyword `fase: str = "Checks"` voor het voortgangslabel.

## 7. Uitvoer

```
uitvoer/
  dwd_kern/            bevindingen.md, bevindingen.csv, bevindingen.json, dq_*.gpkg
  hgv_centrum/         idem
  totaal/              synthese.md, bevindingen.csv, bevindingen.json
```

`schrijf_uitvoer` blijft ongewijzigd. Nieuw in `uitvoer/__init__.py`:

```python
@dataclass(frozen=True)
class UitvoerPerGebied:
    per_gebied: dict[str, Uitvoer]  # originele naam -> geschreven bestanden
    synthese: Path | None
    totaal_csv: Path | None
    totaal_json: Path | None
```

Bij één run: `per_gebied` met één sleutel, de rest `None`, geschreven in `output_dir`
zelf.

JSON-envelop: `schrijf_json` krijgt `gebied: str | None = None` en
`gebieden: list[str] | None = None`. Een veld dat `None` is en niet meegegeven werd
komt **niet** in het bestand — daarmee blijft een enkelvoudige run byte-voor-byte
gelijk aan ronde 1. De per-gebied-JSON van een meervoudige run krijgt
`"gebied": "<originele naam>"`; de totaal-JSON krijgt `"gebied": null` en
`"gebieden": [...]`. Achterwaarts verenigbaar binnen schemaversie 1.x;
`docs/json-schema.md` wordt bijgewerkt.

De totaalsynthese (`uitvoer/synthese.py`, naast `rode_draad`) bevat:

- welke gebieden gedraaid zijn, en of het een selectie was (welke, van hoeveel);
- per gebied: oppervlak in ha, aantal meldingen, fouten/waarschuwingen, aantal
  bevindingen dat buiten het gebied viel, en de meldingen per check;
- het aantal unieke meldingen over alle gebieden;
- het aantal meldingen dat in meer dan één gebied voorkomt, met de uitleg waarom de
  som der delen hoger is dan het totaal;
- de overgeslagen niet-polygonen, als die er waren.

Voortgang: één laadfase, daarna per gebied een fase `Checks <naam>`, plus per gebied
de GeoPackage-fase die er al is.

## 8. Volgorde van uitvoering

1. Validatie en datamodel in `studiegebied.py` (+ `mapnaam`), met de fixture-`crs`-members.
2. `GedeeldeIndex` in `afbakening.py`, met de equivalentietest tegen de oude route.
3. `CheckContext.gedeelde_volledige_context`, `run_checks(fase=…)`.
4. `toetsloop.py`.
5. Schrijflaag: `schrijf_json`-uitbreiding, `UitvoerPerGebied`, totaalsynthese.
6. CLI: `--gebied`, wiring, uitvoer op het scherm.
7. Fixtures (`scripts/maak_gis_fixtures.py`) en de tests uit §9.
8. Documentatie: README, CLAUDE.md, `docs/json-schema.md`, beslislog, CHANGELOG.

## 9. Tests

1. **Equivalentie (kerntest):** twee buurten in één bestand; per gebied zijn de
   meldingen identiek aan een losse run met alleen dat gebied.
2. Grensobject dat beide buurten raakt: in beide uitvoeren, zelfde `melding_id`; de
   synthese telt hem één keer uniek en één keer als meervoudig.
3. `melding_id` bevat het gebied niet (gericht op `identiteit.py`).
4. Validatie: ontbrekende kolom, lege waarde met rijaanduiding, dubbele naam,
   botsende mapnamen, niet-polygonen met melding, nul polygonen na filtering,
   GeoJSON buiten RD-bounds, GeoJSON met legacy `crs` 28992, GeoPackage met verkeerd
   `srs_id`. Elk een eigen test op de foutmelding.
5. Achterwaartse compatibiliteit: het Koekangerveld-scenario met `statcode`/`statnaam`
   ongewijzigd; enkelvoudige uitvoer byte-voor-byte gelijk (inclusief de JSON zonder
   `gebied`-veld).
6. Naamsanering: diakrieten, spaties, slashes, hoofdletters, botsing, lege uitkomst.
7. `--gebied`: één en meerdere, onbekende naam faalt met de juiste melding, validatie
   van het volledige bestand gebeurt ook bij selectie, synthese vermeldt de selectie.
8. Optimalisatie-equivalentie: componentbepaling via de gedeelde index versus de
   directe graafanalyse op één gebied; idem voor de STRtree-selectie.
9. `zwaar`: De Wolden met een twee-buurtenbestand; en een schaaltest met 80+
   gegenereerde buurten die bewaakt dat de run doorloopt en de mappenstructuur klopt,
   met de duur gelogd en zonder tijdslimiet.

## 10. Wat níét

- `analyseer`, `dekking` en `vergelijk` blijven buiten scope; de README legt uit dat
  `vergelijk` per gebied op de map van één gebied gericht moet worden.
- Geen ontdubbeling tussen gebieden, geen toewijzing aan één gebied, geen forceer-vlaggen.
- Geen GeoPackage in `totaal/` (§2.6).
- Geen nieuwe afhankelijkheden; GeoPackage-lezing blijft stdlib `sqlite3` plus shapely.
- De lokaal/contextueel-optimalisatie wordt niet gebouwd (beslislog).
- De dekkingsvalidatie van externe bronnen is ronde 3, niet hier.

## 11. Afronding

`CHANGELOG.md` onder `## [Unreleased]`; `README.md` (multi-feature-gedrag,
`naam_gebied`, `--gebied`, mappenstructuur, validatieregels); `docs/beslislog.md` met
vier vermeldingen (dubbeltelling, hybride uitvoeringsmodel met de twee verplichte
optimalisaties, RD-bounds-heuristiek inclusief de fixture-`crs`-members, uitstel van
de lokaal/contextueel-optimalisatie); `CLAUDE.md` sectie Studiegebied; kwaliteitspoort
schoon; versienummer niet ophogen.
