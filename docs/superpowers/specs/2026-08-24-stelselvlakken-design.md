# Ontwerp: stelselvlakken als GeoPackage-laag (#25)

Peildatum 2026-08-24. Dit stuk legt alleen de keuzes vast die **bovenop** issue #25
komen; de eis zelf staat daar. Blokkades #17 en #18 zijn gesloten en leveren de bron.

## Bron: de geregistreerde stelselboom (#17)

#17 heeft de boom `StedelijkGebied → hasPart → Rioleringsgebied → hasPart → Stelsel →
hasPart → strengen/putten` volledig doorgemeten: 276 stelsels, 100% dekking, elke streng
aan **exact één** stelsel. Twee feiten sturen dit ontwerp:

1. **De registratie scheidt putten van strengen.** 267 stelsels bevatten alléén strengen
   (lokaal, mediaan ~1 km breed); daarnaast zijn er 8 gemeentebrede `_geb_0`-buckets (één
   per type) die álle putten van dat type dragen **plus verspreide strengen over de hele
   gemeente** (22-34 km breed op De Wolden en Hoogeveen). Een stelselvlak baseren we op de
   **strengen**, en we tekenen **alleen de 267 lokale stelsels**: een bucket zou een
   uitgesmeerde vlek geven. Het onderscheid is robuust en semantisch: een bucket bevat
   putten, een lokaal stelsel niet (`dataset.stelsel_leden`). Gevolg: ~5077 strengen (o.a.
   alle drukriolering) zitten alleen in buckets en krijgen geen vlak; ze staan wel in de
   strengenlaag. *(Correctie op de #17-overdracht, die aannam dat de bucketstrengen lokaal
   lagen; de data weerlegt dat. Auteurskeuze 2026-08-24: buckets overslaan.)*
2. **575 objectloze SHACL-nulmetingmeldingen** (over 202 focusnodes) hebben een stelsel-URI
   als focusnode. Ze dragen al naam en type maar geen kaartplek — precies omdat er geen
   stelselgeometrie was.

De engine leest deze boom vandaag nergens (BO-34, #17): `verbanden.py` leidt deelstelsels
af uit grafsamenhang. Dit issue leest de **geregistreerde** boom rechtstreeks uit de graaf;
het raakt de grafafleiding niet aan.

## Beslissingen

- **B1 — Alleen lokale stelsels (met alleen strengen) tekenen.** Een stelsel dat putten
  bevat is een gemeentebrede `_geb_0`-bucket en krijgt geen vlak; ook een stelsel zonder
  strengen valt weg. Op De Wolden en Hoogeveen levert dat 267 vlakken. `gwsw_run` draagt
  `n_stelsels`, zodat het aantal expliciet is in plaats van stil kleiner dan 276.
  *(Auteurskeuze, 2026-08-24, aangescherpt nadat de data de bucketstrengen gemeentebreed
  bleken; zie De vondst punt 1.)*
- **B2 — De 575-nulmeldingkoppeling zit in scope.** De join zet hun `object_uri` op de
  stelsel-URI, zodat ze aan de nieuwe laag koppelen en op de kaart verschijnen. *(Auteurskeuze,
  2026-08-24.)*
- **B3 — Reikwijdte is de hele dataset, niet de kern van een studiegebied.** Consistent met
  BO-12 (een stelsel is aan geen studiegebied toe te wijzen) en met `klassentelling`. Gevolg:
  bij een run zonder studiegebied valt de strenglengte-som samen met de omvangtabel (de
  verificatie-eis van #25); bij een studiegebiedrun toont de laag ook stelsels buiten het
  gebied, en dat is juist wat "welke stelsels liggen los" cartografisch vraagt.
- **B4 — Bufferafstand `stelselvlak_buffer_m = 10.0` m** in `checks.toml` `[drempels]`,
  projectkeuze zonder externe bron (net als `klein_deelstelsel_knopen`). 10 m buffert elke
  lijn tot een lint van 20 m breed; dat voegt de strengen van een stelsel langs een straat
  samen tot één samenhangend vlak zonder een langgerekt stelsel op te blazen. Configureerbaar
  per project.
- **B5 — De vlakken dragen een popup + `n_meldingen`.** Zonder popup is "op de kaart
  verschijnen" (B2) alleen een tabel-join; mét popup toont een klik op het vlak de
  nulmeldingen die erop landen. De symbologie blijft op `bereikt_eindpunt` (B6), los van de
  meldingen.
- **B6 — Symbologie toont standaard alleen de probleemgevallen.** `stelsels.qml` als bestand
  (net als `waterdelen_zonder_zinker.qml`), rule-based op `bereikt_eindpunt`: de regel "geen
  afvoerroute" staat aan, de regel "wel afvoerroute" uit (`checkstate="0"`). `styleCategories`
  noemt `Symbology` én `MapTips`.

## Onderdelen

### 1. Stelsellezer (nieuw, `dataset.py` of klein eigen module)

Per `subjects_of_class("Stelsel")` (sluit alle subklassen in): het stelseltype (meest-
specifieke klasse binnen de Stelsel-afsluiting, via het bestaande `_meest_specifiek`), het
label, en de `hasPart`-leden die in `dataset.conduits` vallen. Levert per stelsel: URI,
label, type, en de lijst streng-URI's. Pure leesfunctie over de graaf; geen gedragswijziging
aan bestaande checks.

### 2. Afvoer per stelsel (hergebruik #18)

`bereikt_eindpunt` = waar of ten minste één streng van het stelsel via
`afvoerpad_van_streng` een afvoer- of lozingseindpunt bereikt. Eén `CheckContext` +
`afvoerpaden` per run, zoals `_schrijf_features` dat al doet.

### 3. De laag `stelsels` (`uitvoer/gpkg.py`)

Kolommen: `feature_id` (`kort(uri)`), `label`, `stelseltype`, `bereikt_eindpunt`,
`n_putten`, `n_strengen`, `strenglengte_m`, `n_meldingen`, `popup_html`.

- `n_putten` = aantal distinct putten aan de eindpunten van de strengen
  (`resolve_network_node` op start/eind). Dit is de enige grafafleiding in de laag en alleen
  voor een teller, niet voor de geometrie.
- `strenglengte_m` = som van de getekende lijnlengtes (zoals de omvangtabel telt).
- geometrie: `unary_union([lijn.buffer(drempel) for lijn in strengen])`, via
  `_als_multipolygon` naar MULTIPOLYGON, in het bestaande `_blob`-formaat.
- popup: `Objectkop` + `popup_html(kop, nulmeldingen_van_dit_stelsel)`.

Toevoegen aan `FEATURELAGEN` en `GEOPACKAGE_STAPPEN`; `n_stelsels` als kolom in `gwsw_run`
(bij `n_bouwwerken` c.s.). De laag is **geen** opgebouwde stijl → `_stijl` leest
`stelsels.qml` uit het bestand.

### 4. De join (`nulbevinding.py`)

In `bouw_nulbevindingen`: is `herleid(focus)` leeg, kijk dan of `{basis}{focus}` een lokaal
stelsel is dat #25 ook tekent (`graph_is_a(uri, "Stelsel")` én `stelsel_leden` geeft strengen
zonder knopen). Zo ja → `object_uri = die URI`. Een `_geb_0`-bucket of een `CfkTypes_typ`-
klassenaam blijft objectloos: koppelen aan een stelsel zonder vlak zou naar een niet-bestaande
feature wijzen en het rapport laten overclaimen. Zo blijft de rapportregel "landt op de
stelsellaag" waar zonder een aparte telling.

`herleid` blijft "op een knoop of streng uitgekomen"; een stelselkoppeling is dus **niet**
`herleid=True`. Downstream: `dataset.nodes.get(uri) or conduits.get(uri)` (regel 115) geeft
`None` voor een stelsel → label valt terug op het SHACL-label, precies goed.
`_meldingen_per_object` in gpkg groepeert op `object_uri`; een stelsel-URI matcht geen
put/streng, dus de meldingen landen niet per ongeluk op een objectlaag, maar wél op de
stelsellaag via dezelfde groepering.

### 5. Het rapport (`bevindingen.py`, `_nulmeting_section`)

De regel "X overtredingen kwamen nergens op uit" telt nu alleen nog de klassenamen. Een
nieuwe regel meldt hoeveel overtredingen op de stelsellaag terechtkomen. Stilte zou lezen als
"nog steeds nergens".

## Reikwijdte-grens (bewust buiten dit issue)

- De grafafleiding in `verbanden.py` blijft ongemoeid; NET-001/002/RVZ-006 lezen hun
  deelstelsel niet uit deze boom (dat is een eigen ingreep, zie BO-34).
- Geen check op tegenspraak registratie vs. afleiding (#17 fase 2: 0 gevallen op De Wolden).

## Verificatie (uit #25, aangevuld)

- `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest`.
- Rijen in `stelsels` = de lokale stelsels (267 op De Wolden en Hoogeveen); `n_stelsels` in
  `gwsw_run` gelijk daaraan.
- `strenglengte_m` som over de laag dekt de strengen van de 267 lokale stelsels (18363 van
  23440 strengen; de bucketstrengen vallen weg). Dit is bewust **niet** meer gelijk aan het
  omvangtabel-totaal, dat over álle strengen telt -- gevolg van het overslaan van de buckets.
- De stelselmeldingen die op een lokaal stelsel landen dragen een `object_uri` en tellen in de
  rapportregel "landt op de stelsellaag"; die op een bucket of klassenaam blijven objectloos
  ("nergens op uit"). `op_stelsel` in het rapport = som van `n_meldingen` over de laag.
- De bestaande vier lagen veranderen niet (kolommen noch tellingen).
- `tests/test_uitvoer_qgis.py` pakt de nieuwe laag via `FEATURELAGEN` mee; met QGIS opent de
  laag met alleen de stelsels zonder afvoerroute zichtbaar.
- Nevenbevinding voor de auteur: 115 van de 267 stelsels staan standaard aan
  (`bereikt_eindpunt=0`), waarvan ~76 mechanisch/duiker/infiltratie/druk/vacuum -- die hebben
  per definitie geen vrijverval-afvoerpad. Alleen ~39 vrijvervalstelsels zijn een echt
  aandachtspunt. Buiten scope van #25; ter beslissing van de auteur.
