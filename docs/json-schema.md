# Het JSON-contract van `bevindingen.json`

`nlriochecker toets` schrijft de volledige meldingenstroom weg als
`bevindingen.json`, naast `bevindingen.md` en `bevindingen.csv`. Dit document is het
contract: welke velden erin staan, wat ze betekenen, en wanneer het versienummer
omhoog gaat.

Bedoeld voor een afnemer die de bevindingen machinaal verwerkt — bijvoorbeeld een
nog te bouwen package die er mutatievoorstellen voor Kikker of BrutIS uit afleidt.
Wie de bevindingen met het oog leest heeft `bevindingen.md`; wie ze in Excel of QGIS
wil heeft `bevindingen.csv`.

Uitzetten kan met `--geen-json`, symmetrisch met `--geen-gpkg`.

## Waarom alleen `toets`

`analyseer` schrijft geen JSON. Dat commando analyseert SHACL-nulmetingrapporten en
kent de meldingenstroom niet: er komt geen `CheckRun` en dus geen `Melding` aan te
pas. Een tweede schema ernaast zou een tweede contract zijn om te onderhouden, en
dezelfde envelop met een lege meldingenlijst zou "nul meldingen" zeggen terwijl de
nulmeting er duizenden telt. Wie de SHACL-analyse machineleesbaar wil, heeft
`geaggregeerde_meldingen.csv`.

## Eigenschappen van het bestand

- UTF-8, zonder ontsnapte codepunten (`ensure_ascii=False`), ingesprongen met twee
  spaties, met een afsluitende regelovergang. Leesbaar bij inspectie; het bestand
  blijft daar klein genoeg voor.
- De meldingen staan gesorteerd op `melding_id`. Twee runs op dezelfde data met
  dezelfde `run_datum` leveren daarom een byte-identiek bestand, en twee
  meetmomenten zijn met een gewone diff te vergelijken. Zie de kanttekening bij
  `melding_id` over botsende ID's.
- Ongeldige getallen worden geweigerd (`allow_nan=False`). Een NaN-coördinaat zou als
  `[NaN, 1.0]` in het bestand komen, wat geen geldige JSON is; dan faalt de run liever
  luid dan dat er een onleesbaar contract wegschrijft.
- Coördinaten staan in EPSG:28992 (RD New). Er wordt niet geherprojecteerd, net als
  in de rest van de uitvoer.
- Het bestand komt uit dezelfde `list[Melding]` als de Markdown, de CSV en de
  GeoPackage. Er is geen pad waarlangs de JSON-schrijver zelf een `Finding`
  interpreteert, en `tests/test_uitvoer_herkomst.py` legt vast dat de uitvoervormen
  hetzelfde over de CFK-set zeggen. Eén verschil is bewust: de CSV draagt de CFK-set
  niet, want die hoort bij de run en niet bij de melding.

## Volledig voorbeeld

```json
{
  "schema_versie": "1.0",
  "gereedschap": "nlriochecker 0.2.0",
  "run_datum": "2026-08-18",
  "dataset": "hgt004_bob_boven_deksel.ttl",
  "cfk_set": ["Hyd"],
  "volledig": false,
  "typeringspoort_toegepast": true,
  "aantal_meldingen": 1,
  "meldingen": [
    {
      "melding_id": "01d06a2c1e0a1bd8",
      "check_id": "TOP-009",
      "categorie": "TOP",
      "bron": "register",
      "ernst": "F",
      "dimensie": "Nauwkeurigheid",
      "object_uri": "http://example.org/toets#L1",
      "object_id": "L1",
      "object_label": "1",
      "object2_uri": "",
      "object2_id": "",
      "object2_label": "",
      "boodschap": "De y-coordinaat ligt buiten het RD-bereik [300000, 630000].",
      "waarde": "",
      "drempel": "",
      "typering_betrouwbaar": true,
      "cluster_id": "",
      "scope": "geen_studiegebied",
      "gebied": "",
      "prioriteit": 2,
      "systemisch": true,
      "foutlocatie": [1025.0, 2000.0],
      "run_datum": "2026-08-18",
      "dataset": "hgt004_bob_boven_deksel.ttl"
    }
  ]
}
```

## De envelop

| Veld | Type | Betekenis |
|---|---|---|
| `schema_versie` | string | De versie van dít contract, los van het versienummer van de package. Zie [Versionering](#versionering). |
| `gereedschap` | string | Pakketnaam plus versie die het bestand schreef, bijvoorbeeld `nlriochecker 0.2.0`. Dezelfde string die de Markdown onder de titel zet en de GeoPackage in `gwsw_run` draagt. |
| `run_datum` | string | De datum van de run, ISO-8601 (`JJJJ-MM-DD`). |
| `dataset` | string | Bestandsnaam van de getoetste OroX-export. |
| `gebied` | string of `null` | *Optioneel.* De originele `naam_gebied` van het gebied waarover dit bestand gaat. Staat alleen in de uitvoer van een run over meerdere studiegebied-features: per gebied de eigen naam, in `totaal/bevindingen.json` `null`. Een run zonder studiegebied of met een bestand met een enkele feature draagt het veld niet. |
| `gebieden` | array van string | *Optioneel.* Alleen in `totaal/bevindingen.json`: de gebieden waarover de synthese gaat, in de volgorde van het gebiedsbestand. Bij een selectie met `--gebied` staan alleen de gekozen gebieden erin; hoeveel het bestand er telde, staat in `totaal/synthese.md`. |
| `cfk_set` | array van string | De conformiteitsklassen waarop getoetst is, gesorteerd. Leeg als er geen nulmeting is meegegeven. |
| `volledig` | boolean | Waar als `cfk_set` gelijk is aan de volledige set uit `checks.toml`. Onwaar bij een deelset én bij een run zonder nulmeting. |
| `typeringspoort_toegepast` | boolean | Of de typeringspoort daadwerkelijk gedraaid heeft. Zie [Over `typering_betrouwbaar`](#over-typering_betrouwbaar) — lees dit veld voordat je `typering_betrouwbaar` gebruikt. |
| `aantal_meldingen` | integer | Het aantal elementen in `meldingen`. Redundant, maar zo kan een afnemer een afgekapt bestand herkennen. |
| `meldingen` | array van object | De meldingen, gesorteerd op `melding_id`. |

### Over `volledig` en `cfk_set`

`volledig: false` heeft twee oorzaken die het bestand niet van elkaar onderscheidt:
een expliciete deelset via `--cfk` (dan is `cfk_set` gevuld) of een run zonder
`--shacl` (dan is `cfk_set` leeg). Het Markdown-rapport ernaast benoemt het verschil
wel, in de regel onder de herkomstregel.

`volledig: true` betekent níét dat de dataset in orde is — alleen dat er tegen alle
conformiteitsklassen gemeten is die de projectconfiguratie eist.

### Over `gebied` en `gebieden`

Beide velden zijn optioneel en kwamen erbij zonder de schemaversie te verhogen: een
afnemer die ze niet kent, leest de bestanden zoals voorheen. Wie ze wel leest, moet ze
als optioneel behandelen -- ze ontbreken bij elke run die niet over meerdere
studiegebied-features gaat.

`totaal/bevindingen.json` bevat de **unieke** meldingen over alle gebieden, ontdubbeld
op `melding_id`. Een object dat meerdere gebieden raakt levert per gebied een melding op
met hetzelfde `melding_id`; in de totaal-JSON staat die een keer, met het `gebied` van
het eerste voorkomen bij oplopende gebiedsnaam. De aantallen per gebied staan in
`totaal/synthese.md`.

De geometrieen van de gebieden gaan niet mee in de JSON; die staan in het
studiegebiedbestand dat de run meekreeg.

### Over `object2_uri` en `object2_label`

De meeste checks laten deze twee leeg. Ze zijn gevuld bij een melding die twee objecten
tegen elkaar afzet: de TOP-checks (twee GWSW-objecten, dus twee dataset-URI's) en sinds
deze versie EXT-001 en EXT-003, die een extern object aanwijzen. Dat is een
achterwaarts verenigbare toevoeging: de velden bestonden al.

De URI's van externe objecten volgen een vaste conventie:

| Voorvoegsel | Bron | `<id>` uit |
|---|---|---|
| `bgt:pand/<id>` | BGT-pand | `lokaal_id` |
| `bgt:bouwwerk/<id>` | overig BGT-bouwwerk | `lokaal_id` |
| `bgt:waterdeel/<id>` | BGT-waterdeel | `lokaal_id` |
| `bag:pand/<id>` | BAG-pand | `identificatie` |
| `geo:<12 hex>` | een bron zonder identificatie | sha256 over de WKB |

De zoekvolgorde voor `<id>` is `lokaal_id`, `identificatie`, `id`. Draagt de bron geen
van drieen, dan valt de sleutel terug op `geo:` plus de eerste twaalf hextekens van de
sha256 over de WKB van de geometrie; de checkuitkomst meldt dat in haar toelichting.
Zo'n sleutel is stabiel over runs op hetzelfde bestand, maar verandert zodra de
geometrie in de bron wijzigt.

De geometrie van het externe object zit **niet** in de JSON -- die zou als WKB in het
contract belanden. Wie hem wil, vindt het object in de GeoPackage: de lagen
`bouwwerken` en `waterdelen_zonder_zinker` dragen dezelfde sleutel in hun kolom `id`.

### Over `typering_betrouwbaar`

Elke melding draagt `typering_betrouwbaar`. Dat veld is onwaar als de SHACL-nulmeting
het object te globaal getypeerd noemt — maar die verzameling is leeg als er geen
nulmeting is meegegeven. Zonder `--shacl` staat er dus overal `true`, en dat betekent
"niet weerlegd", niet "gemeten".

Lees daarom altijd eerst `typeringspoort_toegepast`. Is die onwaar, dan zegt
`typering_betrouwbaar` niets en hoort een afnemer er geen gewicht aan te geven. De twee
velden zijn met opzet gescheiden: het alternatief was `typering_betrouwbaar` op `null`
zetten, en dan zou het per melding herhaald worden terwijl het een eigenschap van de
run is.

## Een melding

Alle velden van de dataclass `Melding` (`src/nlriochecker/uitvoer/melding.py`), met
dezelfde namen in snake_case. Ze zijn alle altijd aanwezig; een ontbrekende
tekstwaarde is een lege string, niet `null`. De enige uitzondering is
`foutlocatie`, die wél `null` kan zijn.

| Veld | Type | Betekenis |
|---|---|---|
| `melding_id` | string | Identiteit van deze melding: dezelfde check op hetzelfde object geeft hetzelfde ID, ook tussen runs. De sorteersleutel van het bestand. Eén uitzondering: botsen twee meldingen binnen één check op dezelfde ID, dan krijgt de tweede een volgnummer (`…-2`) dat tussen runs kan verschuiven. Dat is een gebrek in de `id_sleutels` van die check en het wordt als waarschuwing gelogd; zolang het optreedt is het bestand op dat punt niet diffbaar. |
| `check_id` | string | Check-ID uit het checkregister, bijvoorbeeld `TOP-009`. ID's zijn stabiel en worden nooit hergebruikt. |
| `categorie` | string | Het voorvoegsel van het check-ID: `TOP`, `NET`, `HGT`, `ATTR`, `ADM`, `RVZ`, `BTR`, `EXT`. |
| `bron` | string | Waar de melding uit komt. `register` voor de eigen check-engine. |
| `ernst` | string | `F` voor fout, `W` voor waarschuwing. |
| `dimensie` | string | Dimensietag uit het kwaliteitsraamwerk: `Consistentie`, `Compleetheid`, `Plausibiliteit`, `Actualiteit`, `Traceerbaarheid`, `Precisie`, `Nauwkeurigheid` of `Compliance`. |
| `object_uri` | string | Volledige GWSW-URI van het object waarop de melding staat. |
| `object_id` | string | Het URI-fragment van `object_uri`, bijvoorbeeld `L1`. |
| `object_label` | string | Het label uit de dataset; leeg als het object er geen heeft. |
| `object2_uri` | string | Het tweede betrokken object, bij checks die een paar beoordelen (een kruising, een koppeling). Leeg als de check maar één object aanwijst. |
| `object2_id` | string | Het URI-fragment van `object2_uri`. |
| `object2_label` | string | Leesbare aanduiding van het tweede object. |
| `boodschap` | string | De bevinding in woorden, zoals ook in het Markdown-rapport en de CSV. |
| `waarde` | string | De aangetroffen waarde, als de check er een noemt. Tekst, niet getal: de eenheid en de opmaak horen bij de boodschap. |
| `drempel` | string | De drempel waartegen `waarde` is afgezet, als die er is. |
| `typering_betrouwbaar` | boolean | Onwaar als de nulmeting dit object te globaal getypeerd noemt. De melding blijft staan, maar is niet betrouwbaar te duiden. |
| `cluster_id` | string | Het deelstelsel of de meldingcluster waar dit object in valt, als de check clustert. |
| `scope` | string | `binnen_studiegebied` bij een afgebakende run, `geen_studiegebied` zonder afbakening. |
| `gebied` | string | De aanduiding van het studiegebied; leeg zonder afbakening. |
| `prioriteit` | integer | `1` bij een fout op een kritiek object, `2` bij overige fouten, `3` bij waarschuwingen. |
| `systemisch` | boolean | Waar als deze check op vrijwel de hele populatie aanslaat. Zo'n melding zegt iets over de export als geheel; hem even zwaar wegen als een los gebrek geeft een vertekend beeld. |
| `foutlocatie` | array van twee getallen, of `null` | `[x, y]` in EPSG:28992. `null` als de melding niet op een plek te zetten is. |
| `run_datum` | string | Gelijk aan het enveloppeveld. |
| `dataset` | string | Gelijk aan het enveloppeveld. |

### Waarom `run_datum` en `dataset` dubbel staan

Ze staan zowel in de envelop als op elke melding. Dat is bewust: de meldingenlijst is
een getrouwe spiegel van de dataclass — elk veld dat `Melding` heeft, staat erin — en
de envelop is de run-waarheid. Zoek geen verschil tussen de twee; er is er geen.

## Gereserveerd: `voorstel`

Het veld `voorstel` is gereserveerd voor een latere fase: een concreet
mutatievoorstel per melding (welk veld, huidige waarde, voorgestelde waarde). Het
importformaat van Kikker en BrutIS is nog niet gespecificeerd, dus die fase is nu
buiten scope.

Het veld wordt daarom **niet geschreven** — ook niet als `null`. Een altijd-lege
sleutel zou een belofte zijn die het schema nog niet waarmaakt. Wie ertegen
programmeert, behandelt hem als afwezig-en-optioneel; toevoegen kan later binnen
versie 1.x.

## Versionering

`schema_versie` staat los van het versienummer van de package. Een afnemer pint
hierop en niet op de packageversie: de checks mogen veranderen zonder dat het formaat
dat doet.

Het tweede nummer telt op bij een achterwaarts verenigbare toevoeging: `"1.0"` wordt
`"1.1"` zodra er een optioneel veld bij komt. Pin daarom op het **hoofdnummer**
(`schema_versie.split(".")[0] == "1"`), niet op de volledige string.

**Binnen een hoofdversie mag:**

- een nieuw optioneel veld in de envelop of op een melding;
- een nieuwe waarde in een bestaande opsomming (een nieuw check-ID, een nieuwe
  dimensietag);
- een gewijzigde `boodschap`-tekst.

**Het hoofdnummer gaat omhoog bij:**

- een verwijderd of hernoemd veld;
- een gewijzigd type van een bestaand veld;
- een gewijzigde betekenis van een bestaand veld;
- een andere sorteerorde of een andere structuur van het document.

Een afnemer die op `1.x` gebouwd is, mag onbekende velden dus negeren, maar mag niet
aannemen dat `2.0` nog leesbaar is.
