# Ontwerp ronde 3: BGT/BAG-treffers als lagen, en een dekkingspoort op de bronnen

Bron: `masterinstructie-claude-code-nlriochecker.md`, ronde 3. Ronde 1 (CFK-keuze,
JSON-export, voortgang) en ronde 2 (rapportage per studiegebied-feature) zijn afgerond
en gecommit; dit ontwerp leunt op de meldingenstroom, het JSON-schema, het
voortgangsprotocol en de rapportage per gebied daaruit.

Twee dingen erbij:

1. De GeoPackage krijgt twee featurelagen met de externe objecten waarnaar de
   EXT-meldingen verwijzen: `bouwwerken` (EXT-001) en `waterdelen_zonder_zinker`
   (EXT-003).
2. Bij het laden van de externe bronnen komt een harde poortcheck op de dekking van
   elke aangeleverde laag.

## 1. Geverifieerde feiten

Alles hieronder is in de code of op de data nagekeken, niet aangenomen.

1. `KruisingMetBouwwerk._sterkste()` levert `(relatie, afstand, laag)` terug en gooit
   de geraakte *geometrie en attributen* weg; `laag.nabij()` had ze wel in handen. De
   winnaar wordt gekozen op `(RELATIE_VOLGORDE.index(relatie), afstand)`, waarbij bij
   gelijke sleutel de eerst geziene wint.
2. `_WatergangKruising.kruisingen()` levert `(conduit, rij, laag, buffer)` -- `rij` is
   het attributendict, de geometrie ontbreekt -- en breekt met `break` af na het eerste
   gevonden waterdeel per streng.
3. `Check.finding(context, uri, label, message, location, **details)` zet alle extra
   sleutelwoorden in `Finding.details`. `uitvoer/melding.py` haalt daar precies vijf
   sleutels uit: `object2_uri`, `object2_label`, `waarde`, `drempel` en `cluster_id`.
   De eerste twee zijn voor EXT-001 en EXT-003 nu leeg. Alles wat een check verder in
   `details` zet -- EXT-001 zet er `afstand_m`, EXT-003 `buffer_m` -- bereikt de
   meldingenstroom **niet** en is dus voor de schrijver onzichtbaar.
4. `CheckContext` is bevroren maar draagt al een mutabel veld `_cache`
   (`field(default_factory=dict, compare=False, repr=False)`). Er is dus precedent
   voor een mutabele structuur op de context.
5. `CheckContext.volledige_context()` maakt met `replace(...)` een nieuwe context; een
   veld dat een objectreferentie draagt gaat daarbij mee. `toetsloop._per_gebied` zet
   `_cache={}` expliciet, dus per gebied is te sturen wat vers moet zijn.
6. De GeoPackage-schrijver kent `FEATURELAGEN = ("putten", "strengen",
   "meldinglocaties", "mechanisch_riool")`, maakt elke laag altijd aan, registreert
   hem via `_registreer(...)` in `gpkg_contents`, vult de omhullende met
   `_zet_omhullende(...)` en schrijft geometrie met `_blob(...)`. De stijlen komen uit
   `uitvoer/stijlen/<laag>.qml` en worden per naam uit `FEATURELAGEN` in
   `layer_styles` gezet.
7. `schrijf_geopackage` opent de voortgangsfase met `start_fase("GeoPackage", 8)`;
   `_LaagTellingen` draagt `putten`, `strengen`, `mechanisch`.
8. `ExternalData.extent` komt uit `bronnen.studiegebied` -- het gebied waarvoor de
   bronnen geldig verklaard zijn -- en is iets anders dan het `--studiegebied` van de
   run. Zonder extent geeft `_ExterneCheck.bruikbaar()` altijd `False`: dan toetst
   geen enkele EXT-check iets.
9. Kolomnamen, gemeten op `data/gis` én op `tests/fixtures/gis/ext`: de BGT-lagen
   dragen `lokaal_id` (echte data ook `id`), de BAG-laag draagt `identificatie` (ook
   `id`). BGT-water en BGT-bouwwerk dragen `type` (`waterloop`, `niet-bgt`).
10. Gemeten dekking van de echte bronnen ten opzichte van de omhullende van
    `bronnen.studiegebied` (`218637, 525338 - 219445, 526255`), verruimd met 10 m:
    `bgt_water` dekt volledig; `bgt_pand` komt 59 m tekort in het westen;
    `bgt_bouwwerk` 76/41/276/127 m; `bag_pand` tot 127 m; `nwb_wegvak` tot 121 m; het
    AHN-raster 0,3 m in het zuiden en 0,1 m in het noorden.
11. De EXT-zoekafstanden in de standaardconfig: `ext_pand_buffer_m` 1,0,
    `ext_watergang_buffer_m` 1,0, `ext_putdeksel_afstand_m` 2,0,
    `ext_lozingspunt_water_afstand_m` 10,0, `ext_perceel_buffer_m` 1,0. De
    contextschil (`studiegebied.context_buffer_m`, 50 m) is iets anders: die hoort bij
    de afbakening van de GWSW-analyse, niet bij het zoekbereik in de externe lagen.

## 2. Ontwerpbesluiten

### 2.1 Het trefferregister staat op de context, niet op de uitkomst

Het masterdocument laat de plek open ("bij `CheckRun` of `CheckOutcome`, waar het
past"). Het wordt een mutabel `Trefferregister` op `CheckContext`, dat `run_checks`
als `CheckRun.treffers` naar buiten geeft.

Reden: een check registreert zijn treffer op het moment dat hij de finding bouwt, en
`run_checks` bouwt de `CheckOutcome` pas als de generator leeg is. Het register op de
outcome zetten zou vragen om een tweede doorloop van de detectie -- en een tweede
doorloop is precies hoe laag en uitslag alsnog uit elkaar gaan lopen. `_cache` is het
precedent voor een mutabel veld op de bevroren context.

Het register is een lookup-tabel, geen verzameling die uitspraken doet. Een treffer
die er wel in staat maar door geen enkele melding wordt aangewezen, komt nergens
terecht. Dat maakt het veilig als een gedeelde context er entries in achterlaat, en
lost het multi-gebied-geval op zonder extra werk: per gebied wordt op de meldingen van
dát gebied gejoind.

### 2.2 De sleutel is de bron-ID, met een geometriehash als terugval

`object2_uri` wordt `bgt:pand/<id>`, `bag:pand/<id>`, `bgt:bouwwerk/<id>` of
`bgt:waterdeel/<id>`. Zoekvolgorde voor `<id>`: `lokaal_id`, dan `identificatie`, dan
`id`. Levert geen van drieën een waarde, dan
`geo:<eerste 12 hex van sha256 over de WKB>`, met een notitie in de checkuitkomst dat
het bronbestand ID's mist. Geen harde fout: externe data is context, geen poort (BC-1).

De hash gaat over de WKB van de geometrie, dus twee runs op hetzelfde bestand geven
dezelfde sleutel. Twee bestanden met dezelfde geometrie geven ook dezelfde sleutel;
dat is precies de bedoelde ontdubbeling.

### 2.3 De detectie verandert niet

`_sterkste()` en `kruisingen()` geven voortaan ook de geraakte geometrie en attributen
terug. Dat is additief: de tie-break blijft `(volgorde, afstand)` en de `break` na het
eerste waterdeel blijft staan. Beide geërfde beperkingen -- alleen het sterkste
bouwwerk, alleen het eerste waterdeel -- worden bewust niet gerepareerd; ze gaan als
geaccepteerde beperking de beslislog in, met de verruiming als benoemde maar niet
geplande optie.

### 2.4 De poortcheck meet tegen `bronnen.studiegebied`, niet tegen het studiegebied van de run

Het masterdocument stelt de unie van de studiegebied-features (of de dataset-bbox)
als referentie voor. Dat is hier niet de juiste maat, om twee redenen.

De eerste is inhoudelijk. Dat de bronnen maar een deel van de dataset dekken is in dit
project een normale, gedocumenteerde situatie (BC-2): objecten buiten `extent` krijgen
geen uitslag maar de status *buiten studiegebied*, en dat staat geteld in de
toelichting. Die faalwijze is dus al eerlijk afgevangen. Het gat dat overblijft is een
laag die kleiner is dan het gebied waarvoor je hem geldig verklaart -- daar leest "geen
treffer" ten onrechte als "geen probleem". De omhullende van `bronnen.studiegebied` is
precies dat gebied.

De tweede is praktisch: met de voorgeschreven referentie faalt `toets --bronnen` op de
eigen data van dit project op vijf van de zes bronnen, en zonder `--studiegebied` op
alle zes (feit 10).

Bijkomend voordeel: de poort blijft volledig binnen `load_external_data`. Er is geen
nieuwe parameter met het studiegebied van de run nodig, en daarmee ook geen
volgorde-afspraak in de CLI die iemand later kan omdraaien.

De marge om de referentie is de grootste zoekafstand die de EXT-checks werkelijk
gebruiken (feit 11), niet de contextschil: de checks kijken nooit verder dan hun eigen
buffer. Het raster krijgt marge nul -- bemonsteren is puntsgewijs.

### 2.5 De strengheid is instelbaar, met 0 als standaard

Nieuwe drempel `dekking_tolerantie_m` in `[bronnen]`, standaard `0.0`: uit de doos is
de poort streng.

Reden dat hij er is: de bbox van een laag is de omhullende van zijn *features*, niet
van de uitsnede. Een dunne laag met een lege rand is niet te onderscheiden van een
afgeknipt extract. Feit 10 laat beide uitersten zien: 0,3 m tekort op het raster is
afrondingsruis van de uitsnede, 276 m op `bgt_bouwwerk` is een laag met 52 objecten
die aan de oostkant gewoon ophoudt. Elke drempel is hier een keuze, geen meting, en
die keuze hoort in de projectconfig thuis en niet in de code.

Dit is geen forceer-vlag: het is een geconfigureerde drempel, zoals elke andere drempel
in dit project, en de standaard is de strengst mogelijke waarde.

## 3. Het trefferregister

```python
@dataclass(frozen=True)
class Treffer:
    """Een extern object waarnaar ten minste een melding verwijst."""

    sleutel: str  # gelijk aan object2_uri
    bron: str  # bgt_pand, bag_pand, bgt_bouwwerk, bgt_waterdeel
    label: str
    bronbestand: str
    geometrie: BaseGeometry
    attributen: dict[str, object]


class Trefferregister:
    """De externe objecten die de checks tijdens deze run geraakt hebben."""

    def registreer(
        self,
        treffer: Treffer,
        *,
        check_id: str,
        object_uri: str,
        afstand_m: float | None = None,
    ) -> str: ...  # levert de sleutel terug

    def get(self, sleutel: str) -> Treffer | None: ...
    def afstand(self, sleutel: str, check_id: str, object_uri: str) -> float | None: ...
    def __len__(self) -> int: ...
```

Ontdubbeling op de sleutel gebeurt in `registreer`: de eerste registratie wint, latere
met dezelfde sleutel worden genegeerd. De geometrie is per sleutel per definitie
dezelfde.

`afstand_m` is de enige waarde die per *melding* verschilt in plaats van per treffer,
en `Melding` draagt hem niet (feit 3). Het register bewaart hem daarom onder
`(sleutel, check_id, object_uri)` -- precies de drie velden die elke melding wél
draagt, zodat de schrijver hem exact terug kan vinden voor de meldingen van déze
uitvoer en niet voor die van een ander gebied.

`CheckContext` krijgt `treffers: Trefferregister = field(default_factory=Trefferregister,
compare=False, repr=False)`; `run_checks` zet hem als `CheckRun.treffers`.
`toetsloop._per_gebied` geeft elke gebiedscontext een vers register mee, net als
`_cache={}` -- niet omdat een gedeeld register fout zou zijn (de join beslist), maar
omdat een register dat alleen de treffers van dit gebied bevat leesbaarder is bij het
debuggen en niet meegroeit met het aantal buurten.

## 4. De checks

`KruisingMetBouwwerk.run` registreert de winnende treffer en zet de twee velden in de
finding:

```python
relatie, afstand, laag, vorm, attributen = geraakt
sleutel = context.treffers.registreer(_bouwwerktreffer(laag, vorm, attributen))
yield self.finding(
    context, object_.uri, object_.label, <ongewijzigde boodschap>,
    waarde=relatie, drempel=buffer, afstand_m=round(afstand, 3),
    bron=laag.source.name, laag=laag.layer,
    object2_uri=sleutel, object2_label=<label>,
)
```

Het label is `pand <id>` respectievelijk `bouwwerk <id>`, met het `type`-attribuut
erbij als de laag dat draagt. `KruisingZonderZinkerOfDuiker.run` doet hetzelfde met
`bgt:waterdeel/<id>` en het watertype als label.

De bron-rol volgt uit de laag waarin de treffer gevonden is; `bouwwerklagen()` levert
de lagen al in de volgorde pand, BAG-pand, overig bouwwerk en kent hun rol.

EXT-002 blijft ongemoeid: die meldt kruisingen *met* een geregistreerde zinker of
duiker, en die horen bewust niet in de laag.

## 5. De twee lagen in de GeoPackage

`uitvoer/gpkg.py` bouwt de lagen door de meldingen van deze uitvoer te joinen op
`run.treffers` via `object2_uri`. Alleen treffers waarnaar ten minste een melding in
déze uitvoer verwijst worden geschreven.

`bouwwerken` (uit EXT-001-meldingen), `POLYGON`/`MULTIPOLYGON`:

| kolom | inhoud |
|---|---|
| `id` | de object2-sleutel |
| `bron` | `bgt_pand`, `bag_pand` of `bgt_bouwwerk` |
| `bronbestand` | bestandsnaam van de bron |
| `label` | leesbare aanduiding |
| `relatie` | de sterkste over de verwijzende meldingen: binnen > kruist > nabij |
| `afstand_min_m` | de kleinste afstand over de verwijzende meldingen |
| `aantal_meldingen` | het aantal meldingen dat naar deze treffer verwijst |
| `check_ids` | kommagescheiden, gesorteerd |

`waterdelen_zonder_zinker` (uit EXT-003-meldingen): `id`, `watertype`, `bronbestand`,
`label`, `aantal_meldingen`, `check_ids`, `buffer_m`.

`relatie` komt uit het meldingveld `waarde`, dat EXT-001 al vult. `afstand_min_m` is
het minimum over de verwijzende meldingen, opgehaald uit het register op
`(sleutel, check_id, object_uri)`; ontbreekt de afstand, dan blijft de kolom leeg.
`buffer_m` in `waterdelen_zonder_zinker` komt niet uit de melding maar uit
`run.config.drempels.ext_watergang_buffer_m`: het is een runbrede configuratiewaarde,
voor elke rij dezelfde. De schrijver leidt niets af uit geometrie en interpreteert
geen enkele `Finding`. Beide lagen worden altijd aangemaakt, ook leeg,
krijgen een rij in `gpkg_contents` met gevulde omhullende zodra er inhoud is, en tellen
mee in `_LaagTellingen`. `FEATURELAGEN` groeit met twee namen, waarmee ze automatisch
in `layer_styles` belanden.

Twee nieuwe QML's naar het patroon van de bestaande vier: `bouwwerken.qml` met rode
omlijning (`#d73027`) en volledig doorzichtige vulling, `waterdelen_zonder_zinker.qml`
met blauwe omlijning (`#2166ac`).

De voortgangsfase van de GeoPackage gaat van 8 naar 10 stappen.

## 6. De dekkingspoort

In `externedata.py`, aangeroepen aan het eind van `load_external_data`, vóór het
teruggeven van `ExternalData`:

```python
class Dekkingseis(NamedTuple):
    """Hoe ver buiten het bereik de checks kijken, en wat er aan tekort mag zijn."""

    marge_m: float
    tolerantie_m: float


def load_external_data(
    bronnen, wortel: Path | None = None, *, dekkingseis: Dekkingseis | None = None
) -> ExternalData: ...
```

`None` betekent: geen poort. De CLI geeft hem altijd mee en bouwt hem uit de config:
`marge_m` = de grootste EXT-zoekafstand uit `drempels`, `tolerantie_m` =
`bronnen.dekking_tolerantie_m`.

De regel: is er een `extent`, dan moet de omhullende van elke aangeleverde laag de
omhullende van `extent`, verruimd met `marge_m`, omvatten; voor het raster geldt
`marge_m = 0`. Een tekort per zijde groter dan `tolerantie_m` is een
`ExternalDataError` die per falende laag beide omhullenden noemt plus het tekort in
meters per zijde. Ontbreekt `extent`, dan draait de poort niet -- zonder bereik geeft
geen enkele EXT-check een uitslag, dus valt er niets te maskeren.

De docstring zegt expliciet wat deze poort niet kan: bbox-dekking is noodzakelijk maar
niet voldoende (een gat middenin valt er niet mee op), en een tekort op een dunne laag
betekent "hier staan geen features", niet per se "extract afgeknipt". De
`binnen_bereik`-notities per object blijven het tweede vangnet.

## 7. Koppelpunten met eerdere rondes

1. **JSON**: `object2_uri` en `object2_label` zaten al in het schema en worden nu voor
   EXT-001 en EXT-003 gevuld. Achterwaarts verenigbaar binnen 1.x;
   `docs/json-schema.md` krijgt de URI-conventies en de `geo:`-terugval erbij. De
   treffergeometrieen gaan niet mee in de JSON.
2. **Voortgang**: twee extra stappen in de GeoPackage-fase.
3. **Multi-gebied**: geen extra werk, mits de schrijver strikt vanuit de
   per-gebied-meldingen joint. Daar staat een test op.

## 8. Tests

1. **Striktheid (kerntest):** de inhoud van elke nieuwe laag is exact de verzameling
   unieke `object2_uri`'s van de EXT-001- respectievelijk EXT-003-meldingen van die
   run.
2. Ontdubbeling: twee strengen raken hetzelfde pand; een rij, `aantal_meldingen == 2`,
   de sterkste relatie.
3. Relaties: een `nabij`-geval (binnen de buffer, geen raakvlak) staat in de laag met
   `relatie = nabij`.
4. EXT-002-afbakening: de duiker-fixture levert geen waterdeel in de laag.
5. Terugval-ID: een fixture-laag zonder bron-ID's levert `geo:`-sleutels plus de
   notitie; twee identieke runs geven identieke sleutels.
6. Lege lagen: een run zonder EXT-treffers bevat beide lagen leeg, met registratie in
   `gpkg_contents` en een stijl in `layer_styles`.
7. Multi-gebied: een grenspand staat in beide per-gebied-GeoPackages; een pand dat
   alleen vanuit buurt A geraakt wordt staat niet in die van buurt B.
8. Regressie: de bestaande suite draait ongewijzigd groen, in het bijzonder de exacte
   relatie-asserties van EXT-001 en de EXT-003-labels. Expliciet nagaan dat geen
   bestaande test asserteert dat de object2-velden leeg zijn.
9. Dekkingspoort: (a) een laag die net te klein is faalt met beide omhullenden en het
   tekort per zijde; (b) een laag die exact op de extent-bbox is geknipt faalt zodra
   `marge_m > 0`; (c) een dekkende laag met een gat middenin slaagt, waarmee de
   gedocumenteerde beperking getest vastligt; (d) zonder `extent` draait de poort niet;
   (e) een ontbrekende laag raakt de poort niet; (f) een te klein raster faalt op
   dezelfde wijze; (g) een tekort binnen `dekking_tolerantie_m` slaagt.
10. Onder `zwaar`: op de echte De Wolden-bronnen zijn de laagaantallen gelijk aan de
    unieke object2-tellingen uit de meldingen.

## 9. Wat niet

- De detectielogica van EXT-001 en EXT-003 wordt niet verruimd (geen `break` weg, geen
  `_sterkste` verbreed).
- Geen treffergeometrie in CSV of JSON.
- Geen forceer-vlag op de dekkingspoort; wel een geconfigureerde tolerantie.
- Geen nieuwe afhankelijkheden.
- `analyseer`, `dekking` en `vergelijk` blijven ongemoeid.

## 10. Afronding

`CHANGELOG.md` onder `## [Unreleased]`; `README.md` (de twee lagen bij de uitvoer, de
dekkingseis en `dekking_tolerantie_m` bij de invoer, met de aantekening dat `data/gis`
een tolerantie van circa 300 m nodig heeft); `docs/beslislog.md` met drie vermeldingen
(strikte aansluiting inclusief de twee geaccepteerde beperkingen, de
object2-URI-conventie met de geometriehash-terugval, en de dekkingspoort inclusief
waarom een harde fout hier niet botst met "externe data is context, geen poort");
`docs/json-schema.md`; `CLAUDE.md` bij de GeoPackage-beschrijving; kwaliteitspoort
schoon; versienummer niet ophogen.
