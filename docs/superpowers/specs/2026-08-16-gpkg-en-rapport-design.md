# Ontwerp: rapportverbeteringen en GeoPackage-export

Datum: 2026-08-16. Status: vastgesteld na brainstorm.

Bronnen: `instructie-claude-code-gpkg-en-rapport.md` (opdracht), `ontwerp-gis-output-datakwaliteit.md`
(GPKG-ontwerp), `bevindingen-verbeterd.md` (richtbeeld rapport), `CLAUDE.md` (projectconventies,
gaan boven de instructie).

Ankerrun: `uitvoer/koekangerveld_volledig/` — De Wolden, studiegebied Koekangerveld,
113 bevindingen (57 F, 56 W) uit 87 checks.

---

## 1. Doel en afbakening

Deze ronde levert twee dingen:

**A. Rapportverbeteringen** — een synthesesectie, clusterduiding bij de netwerkchecks, een
naamgevingscorrectie in de netwerktoelichtingen, een semantiekcorrectie bij HGT-001/002, correct
Nederlands in gegenereerde meldingen, geen afkap meer in de bevindingentabellen, en een
uitgebreide CSV.

**B. GeoPackage-export** — een zelfvoorzienend GPKG per run met de lagen `putten`, `strengen`,
`meldinglocaties`, `meldingen`, `overzicht_checks` en `gwsw_run`, in EPSG:28992, met embedded
QGIS-stijlen.

**Buiten deze ronde (ronde 2):** het meenemen van de SHACL-nulmetingmeldingen in de GPKG
(focusnode-herleiding, Mds/Hyd-deduplicatie, systemisch-vlag op nulmetingtypen). De structuur
van deze ronde is daarop voorbereid: de kolom `bron` bestaat, de `systemisch`-vlag wordt nu al
generiek gebouwd, en de meldingentabel heeft de kolommen die ronde 2 nodig heeft.

---

## 2. Architectuur: één bevindingenstroom

### 2.1 Het probleem dat dit oplost

§3.4 van de instructie eist dat CSV, MD en GPKG uit dezelfde interne structuur komen en dat er
geen tweede codepad ontstaat dat meldingen opnieuw formuleert. Nu formuleert `reporting.py` de
MD-tabel en de CSV-tabel elk apart uit `Finding`. Een derde schrijver erbij zou het probleem
verdrievoudigen.

### 2.2 De oplossing

Nieuw pakket `src/gwswpijplijn/uitvoer/` met daarin `melding.py`:

```python
@dataclass(frozen=True)
class Melding:
    """Een bevinding, verrijkt tot wat alle uitvoervormen nodig hebben."""

    melding_id: str
    check_id: str
    categorie: str          # TOP / ADM / ATTR / HGT / NET / RVZ / BTR / EXT
    bron: str               # register (ronde 2 voegt nulmeting_mds / nulmeting_hyd toe)
    ernst: str              # F / W
    dimensie: str
    object_uri: str
    object_label: str
    object2_uri: str        # leeg bij niet-paarmeldingen
    object2_label: str
    boodschap: str
    waarde: str             # gemeten waarde, leeg als de check er geen levert
    drempel: str            # verwachte waarde of drempel, leeg idem
    typering_betrouwbaar: bool
    cluster_id: str         # deelstelsel-ID, leeg buiten NET-001/002 en RVZ-006
    scope: str              # binnen_studiegebied / geen_studiegebied
    gebied: str
    prioriteit: int         # 1, 2 of 3
    systemisch: bool
    foutlocatie: Point | None
    run_datum: str          # ISO-datum
    dataset: str            # bestandsnaam van de OroX-TTL
```

Eén bouwfunctie:

```python
def bouw_meldingen(run: CheckRun, run_datum: date) -> list[Melding]: ...
```

MD, CSV en GPKG lezen alle drie uitsluitend deze lijst. Er is geen pad waarlangs een schrijver
nog zelf een `Finding` interpreteert. Daarmee is §3.4 geen afspraak maar een eigenschap van de
code.

### 2.3 Gereserveerde detailsleutels

`Finding.details` is nu vrij invulbaar. De velden die `Melding` eruit haalt worden een vaste,
gedocumenteerde set:

| Sleutel | Betekenis |
|---|---|
| `object2_uri` | URI van het tweede object bij een paarmelding |
| `object2_label` | label daarvan |
| `waarde` | de gemeten waarde als tekst, inclusief eenheid |
| `drempel` | de verwachte waarde of drempel als tekst |
| `cluster_id` | deelstelsel-ID |

De bestaande conventie `andere_uri` / `andere_streng` / `andere_put` in TOP-005, TOP-006, TOP-010,
TOP-011, TOP-013 en TOP-019 wordt naar `object2_uri` / `object2_label` genormaliseerd. Dat is een
hernoeming binnen de checks; de sleutels staan nergens in de bestaande uitvoer, dus er breekt niets
naar buiten.

De overige detailsleutels blijven vrij en gaan niet mee naar de uitvoer.

### 2.4 `Finding.location` blijft wat het is

`Finding.location` is de eigen RD-coördinaat van een object dat niet uit de GWSW-dataset komt (een
BGT-putdeksel zonder put, een BAG-verblijfsobject zonder riolering). `beperk_tot_studiegebied()`
gebruikt hem als afbakeningscriterium wanneer `object_uri` niet in de dataset zit.

De foutlocatie uit §3.3 van de instructie is iets anders en wordt een **apart afgeleid veld** op
`Melding`. Ze samenvoegen zou de scopefiltering veranderen: een streng die grotendeels buiten het
gebied ligt maar wiens middelpunt erbinnen valt, zou dan ineens meetellen. Dat is een stille
gedragswijziging in een onderdeel dat nu correct werkt.

### 2.5 Verhuizing binnen `reporting.py`

`reporting.py` is 849 regels en bedient vier verschillende rapporten. Deze ronde raakt bijna elke
functie van het bevindingenrapport aan. Dat deel — `write_check_report`, `_render_checks`,
`_check_findings_table`, `_check_summary`, `_findings_frame`, `_karakteristiek_section`,
`_bronnen_section`, ongeveer 340 regels — verhuist naar `uitvoer/bevindingen.py`. De nulmeting-,
dekking- en vergelijkingsrapporten blijven in `reporting.py`; die raken we niet aan.

Publieke namen (`FILE_CHECKS_MARKDOWN`, `FILE_CHECKS_CSV`, `write_check_report`) blijven vanuit
`reporting.py` importeerbaar, zodat bestaande imports en tests blijven werken.

### 2.6 Modulestructuur

```
src/gwswpijplijn/uitvoer/
    __init__.py        publieke ingang: schrijf_uitvoer(run, output_dir, opties)
    melding.py         het Melding-record en bouw_meldingen()
    identiteit.py      melding_id-hash
    locatie.py         foutlocatieregels (§3.3)
    synthese.py        de rode draad (A1)
    taal.py            getal- en lidwoordcongruentie (A5.2)
    bevindingen.py     MD- en CSV-schrijver (verhuisd uit reporting.py)
    gpkg.py            GeoPackage-schrijver
    stijlen/           QML-sjablonen als package-resource
        putten.qml
        strengen.qml
        meldinglocaties.qml
```

---

## 3. Stabiele melding-ID

```
melding_id = sha256("<check_id>|<object_uri>|<object2_uri>|<k1=v1;k2=v2>").hexdigest()[:16]
```

De laatste component bevat de **identificerende detailsleutels** van die check, op sleutelnaam
gesorteerd, als `key=value` met puntkomma's ertussen. Elke `Check` declareert ze:

```python
class Check(ABC):
    id_sleutels: ClassVar[tuple[str, ...]] = ()
```

HGT-003 zet `id_sleutels = ("zijde",)` omdat die check twee bevindingen op dezelfde streng kan
geven, één per zijde. De meeste checks laten het leeg.

**Vangnet.** Bij het bouwen van de meldingenlijst wordt uniciteit geëist. Botsen er toch twee, dan
krijgt de tweede een volgnummersuffix (`<hash>-2`) **en** wordt er een waarschuwing gelogd met
check-ID en object erbij. Zo valt een vergeten `id_sleutels` op in plaats van stil twee meldingen
tot één te laten versmelten.

Eigenschappen: ongevoelig voor wijzigingen in de meldingtekst en in niet-identificerende details;
gevoelig voor het feit zelf. Geschikt voor run-vergelijking in een latere fase zonder
schemawijziging.

---

## 4. Foutlocatieregels

`locatie.py` bepaalt per melding het punt in `meldinglocaties`. De regels, in volgorde:

1. Levert de check zelf een foutlocatie in `details["foutlocatie"]` (een `(x, y)`-paar), dan is die
   leidend. TOP-011 zet het al berekende hartlijnsnijpunt; TOP-006 en TOP-010 het middelpunt van
   het overlappende respectievelijk rakende deel; TOP-004 het niet-gesnapte strengeindpunt;
   TOP-005 het middelpunt tussen de twee putten.
2. Anders, is `Finding.location` gevuld (een object buiten de GWSW-dataset), dan dat punt.
3. Anders, is het object een knoop met geometrie, dan de putlocatie.
4. Anders, is het object een streng met geometrie, dan het middelpunt van de lijn
   (`line.interpolate(0.5, normalized=True)`).
5. RVZ-006 en andere deelstelselmeldingen: het zwaartepunt van de knopen in het deelstelsel.
6. Lukt geen van deze, dan geen punt: de melding staat wel in `meldingen`, niet in
   `meldinglocaties`. Het aantal meldingen zonder punt staat in `gwsw_run` en in het MD-rapport —
   stilte hierover zou lezen als "alles staat op de kaart".

TOP-011 haalt de coördinaat uit de meldingtekst zodra hij als kolom en geometrie bestaat; §A6 van
de instructie vraagt dat expliciet.

---

## 5. Deelstelsel-ID (cluster_id)

Nieuwe gedeelde functie in `checks/verbanden.py`:

```python
def deelstelsel_ids(context: CheckContext) -> dict[str, str]:
    """Geeft per knoop-URI het ID van het vrijverval-deelstelsel waarin hij ligt."""
```

Gebouwd op dezelfde ongerichte vrijvervalgraaf die `_bouw_stelseldelen()` in
`randvoorzieningen.py` nu al opbouwt; die functie gaat de nieuwe gebruiken, zodat er één
componentindeling bestaat. Beide gebruiken `resolve_network_node()` met
`config.klassen.netwerkknopen`, dus de knoopverzameling is identiek aan die van de gerichte
NET-graaf; de richting doet voor samenhang niet ter zake.

ID-vorm: `ds-<label van de lexicografisch eerste knoop-URI in de component>`, met terugval op het
URI-fragment als er geen label is. Deterministisch en leesbaar; De Wolden krijgt zo
`ds-Kv1G0002` voor het gemengde eiland.

NET-001 en NET-002 zetten `cluster_id` op elke bevinding. RVZ-006 zet hem ook, zodat de
kruisverbandsdetectie uit §6.1 op gelijke ID's kan vergelijken in plaats van op namen.

---

## 6. Rapportverbeteringen

### 6.1 A1 — Synthesesectie "Rode draad"

`synthese.py`, direct na de kopmetadata en vóór de samenvattingstabel. Drie detecties:

1. **Richtings-rootcause.** Ligt het aandeel strengen waarbij de bodem stijgt in de administratieve
   richting boven `rapport.richtingsdrempel` (default 0,10), dan een alinea die systematisch
   omgekeerde registratie als vermoedelijke gezamenlijke oorzaak benoemt van de NET-003-, NET-001-,
   NET-004-, HGT-005- en HGT-006-bevindingen, met het percentage erbij. Het getal komt uit
   `_bob_tegen_de_richting()`, dat al bestaat.
2. **Multi-meldingsobjecten.** Objecten met meldingen uit `rapport.multi_melding_checks` of meer
   verschillende checks (default 3) worden apart benoemd, met de check-ID's en de gedeelde
   verdachte waarde.
3. **Kruisverbanden.** Vallen NET-001-clusters samen met RVZ-006-deelstelsels (gelijk
   `cluster_id`), dan wordt dat benoemd.

Slaat geen enkele detectie aan, dan komt de kop er niet — geen lege sectie.

### 6.2 A2 — Clusterduiding

Boven de bevindingentabel van NET-001 en NET-002 een blok in de trant van: "de 24 bevindingen
betreffen twee deelstelsels, geen 24 losse gebreken", met per cluster het aantal strengen en het
ID. De bevindingen blijven per streng, conform het register en omdat de kaart per-strenggeometrie
nodig heeft.

### 6.3 A3 — Naamgevingscorrectie in de netwerktoelichtingen

**Geverifieerde diagnose.** `_read_nodes()` (`dataset.py:730`) neemt als knoop het *subject* dat de
orientatie via `hasAspect` draagt, nooit de orientatie zelf. In de De Wolden-TTL:

```
:knp1      rdf:type gwsw:Rioolgemaal ; rdfs:label "Nw2V0002" .
:knp1_put  rdf:type gwsw:Bouwwerkorientatie .
:knp1      gwsw:hasAspect :knp1_put .
```

De graafknoop is `:knp1`. Wat misgaat zit in `_soort()` (`checks/netwerk.py:139`):
`sorted(types_of(uri))[0]`, en `types_of()` voegt bewust `orientation_types` samen met de
objecttypen (`dataset.py:297`, en terecht — Lozingspunt en UitlaatPunt staan volgens het GWSW op de
orientatie). Alfabetisch wint dan "Bouwwerkorientatie" van "Rioolgemaal" en "Putorientatie" van
"Rioolput".

De "233 Bouwwerkorientatie-eindknopen" in het richtbeeld zijn dus 233 echte bouwwerken met een
verkeerd label, geen lek in de netwerkopbouw.

**Fix.** `_soort()` kiest het beheerobjecttype: de orientatie-aspecttypen worden overgeslagen, en
alleen als er niets anders overblijft wordt het aspecttype getoond. De kanttekening uit het
richtbeeld vervalt.

**Gevolg voor de aantallen: geen.** De naamfix raakt uitsluitend de tekst van een toelichting. De
ankerpunten 113 / 57 F / 56 W, NET-001 = 24 en EXT-008 = 16 blijven gelden. Dit wijkt af van §A3
van de instructie, die verschuiving verwachtte; de reden staat hierboven en gaat mee in het
eindverslag.

### 6.4 A4 — Semantiek HGT-001 en HGT-002

Titels worden "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 5 cm" respectievelijk
"meer dan 25 cm". Vaste titels, want dezelfde titel voedt ook de dekkingsmatrix en het
registeroverzicht, waar een datasetafhankelijke tekst niet thuishoort.

Beide checks krijgen een **verplichte** toelichtingsregel met de telling, bijvoorbeeld: "In deze
dataset is 40 van de 40 keer de maaiveldhoogte vergeleken; `Putdekselniveau` ontbreekt in deze
export." Bij een gemengde dataset noemt de regel beide aantallen. De check kiest per put al het
juiste kenmerk en zet dat in de meldingtekst; dat blijft zo.

### 6.5 A5.1 — Geen afkap

De constante `TOP_N = 15` in het bevindingenrapport wordt `rapport.max_bevindingen_per_check`,
default `0` = onbeperkt. De regel "Alle bevindingen staan in `bevindingen.csv`" blijft staan. Is de
waarde niet 0 en wordt er afgekapt, dan staat onder de tabel hoeveel bevindingen er niet getoond
zijn.

De `TOP_N` in het nulmetingrapport (`_render_markdown`) blijft ongemoeid; dat is een andere tabel
met een ander doel.

### 6.6 A5.2 — Grammatica-helper

`taal.py`, met twee functies:

```python
def getal(aantal: int, enkelvoud: str, meervoud: str) -> str:
    """'1 bevinding' / '2 bevindingen'."""

def met_lidwoord(zelfstandig_naamwoord: str) -> str:
    """'de maaiveldhoogte' / 'het putdekselniveau'."""
```

Het lidwoord komt uit een expliciete woordenlijst van de termen die wij zelf genereren
(maaiveldhoogte → de, putdekselniveau → het, dekselhoogte → de, BOB → de, streng → de, put → de,
deelstelsel → het, verhang → het). Onbekende woorden geven een `KeyError` bij het genereren, niet
stilzwijgend "de" — dan valt het op in de test in plaats van in het rapport.

Alle gegenereerde meldingsjablonen gaan hierlangs. De bekende fout "Het maaiveldhoogte" in `extern.py:751` verdwijnt daarmee.

### 6.7 A5.3 — Scopebeleid

**Beslissing van de opdrachtgever, afwijkend van §A5.3 van de instructie:** is er een studiegebied
opgegeven, dan bevatten MD, CSV én GPKG uitsluitend de bevindingen binnen dat gebied.

De kolom `scope` blijft bestaan en houdt per run één waarde: `binnen_studiegebied` als er een
gebied is, `geen_studiegebied` als er geen is. Hij legt daarmee vast wélk beleid gold toen het
bestand geschreven werd — nodig zodra iemand twee exports naast elkaar legt.

Het MD-rapport blijft expliciet melden hoeveel bevindingen buiten het gebied vielen (De Wolden:
35.899) en dat het rapport dus niets zegt over de rest van de dataset.

### 6.8 A6 — CSV-uitbreiding

Bestaande kolommen blijven ongewijzigd van naam en volgorde:

```
Check;Ernst;Dimensie;Label;Object;Melding;TyperingBetrouwbaar;X;Y
```

Daarachter komen:

```
MeldingID;Categorie;Bron;Object2Label;Object2;Waarde;Drempel;ClusterID;Scope;Gebied;Prioriteit;Systemisch;RunDatum;Dataset
```

`X` en `Y` worden de foutlocatie uit §4 in plaats van alleen de eigen coördinaat van externe
objecten; coördinaten verdwijnen uit de vrije meldingtekst zodra ze als kolom bestaan.

Scheidingsteken `;`, encoding utf-8, conform de huidige conventie.

**Afwijking van §A6:** de instructie noemt snake_case kolomnamen (`melding_id`, `object2`, `x`,
`y`). De bestaande CSV gebruikt Nederlandse CamelCase. Hernoemen breekt bestaande tests en
bestaande verwerking bij de gebruiker zonder dat er iets tegenover staat; de nieuwe kolommen
volgen daarom de bestaande stijl. De **GPKG** gebruikt wél lowercase snake_case, zoals het
GPKG-ontwerpdocument voorschrijft.

---

## 7. GeoPackage-export

### 7.1 Schrijfwijze zonder nieuwe afhankelijkheden

CLAUDE.md staat pandas, click, pydantic, rdflib, shapely en networkx toe en verbiedt uitbreiding
zonder noodzaak. `studiegebied.py` leest GeoPackages al met `sqlite3` plus shapely. De schrijfkant
volgt dezelfde route: `uitvoer/gpkg.py` op `sqlite3` en `shapely.wkb`.

Wat de schrijver aanmaakt:

- `PRAGMA application_id = 0x47504B47` en `PRAGMA user_version = 10300`.
- `gpkg_spatial_ref_sys` met de drie verplichte rijen (-1 undefined cartesian, 0 undefined
  geographic, 4326) plus EPSG:28992 met zijn WKT.
- `gpkg_contents`: één rij per laag, met `data_type` `features` of `attributes`, `srs_id` 28992 en
  de bounding box voor featurelagen.
- `gpkg_geometry_columns`: één rij per featurelaag.
- Featuretabellen met `fid INTEGER PRIMARY KEY AUTOINCREMENT` en een `geom BLOB` in
  GeoPackage-binair formaat: magic `GP`, versie `0x00`, vlaggen `0x01` (little endian, geen
  envelope), `srs_id` als int32 LE, dan de WKB uit shapely.
- Attribuuttabellen zonder geometrie, geregistreerd als `attributes`.

Dit is precies het formaat dat `studiegebied._ontleed_gpkg()` al leest, dus de lees- en
schrijfkant houden elkaar in de gaten.

### 7.2 Lagen

**`putten` (punt)** en **`strengen` (lijn)** — één rij per beheerobject binnen de grens, geometrie
uit de OroX. Kolommen conform het ontwerpdocument §2.1: `feature_id`, `label`, `objecttype`,
`stelsel`, `gebied`, `ergste_ernst`, `n_fout`, `n_waarschuwing`, `n_systemisch`, `checks_f`,
`checks_w`, `n_top` t/m `n_ext`, `prioriteit`, plus de metadatavelden `run_datum`,
`dataset_versie`, `register_versie`.

`n_nulmeting` staat in het schema en blijft in deze ronde 0; ronde 2 vult hem.

**`meldinglocaties` (punt)** — één punt per melding op de foutlocatie uit §4, met alle kolommen van
`meldingen` erbij, zodat de laag zonder join bruikbaar is.

**`meldingen` (attributes)** — het volledige register: `melding_id`, `feature_id`, `feature_id_2`,
`check_id`, `bron` (in deze ronde altijd `register`), `ernst`, `categorie`, `dimensie`,
`boodschap`, `waarde`, `drempel`, `systemisch`, `cluster_id`, `scope`, `gebied`, `prioriteit`,
`typering_betrouwbaar`.

**`overzicht_checks` (attributes)** — één rij per check: `check_id`, `omschrijving`, `bron`,
`ernst`, `dimensie`, `aantal_meldingen`, `bekeken`, `percentage_populatie`, `systemisch`,
`aantal_gebieden`, `skelet`. Alle 87 checks staan erin, ook die met nul bevindingen en de
skeletchecks — een check die ontbreekt leest als een check zonder problemen.

**`gwsw_run` (attributes)** — één rij met de runmetadata: dataset, bestandsgrootte en tijdstempel,
gebruikte ontologieën, registerversie, run_datum, of de typeringspoort is toegepast, de
coderingsterugval, het aantal meldingen zonder foutlocatie, en de grens (bron, laag, oppervlakte in
ha, aantal vlakken). Zo is een los rondslingerend bestand altijd herleidbaar.

### 7.3 Stijlen

Handgeschreven QML-sjablonen als package-resource onder `uitvoer/stijlen/`. Bij export gaan ze in
de tabel `layer_styles` (kolommen conform QGIS: `f_table_catalog`, `f_table_schema`,
`f_table_name`, `f_geometry_column`, `styleName`, `styleQML`, `styleSLD`, `useAsDefault`,
`description`, `owner`, `ui`, `update_time`) **en** als losse `.qml`-bestanden naast de GPKG, voor
pakketten die de tabel niet lezen maar QML wel importeren. `layer_styles` wordt niet in
`gpkg_contents` geregistreerd; dat doet QGIS zelf ook niet.

De stijlen: `putten` en `strengen` gecategoriseerd op `ergste_ernst` (rood F, oranje W, grijs
geen), symboolgrootte op `n_fout + n_waarschuwing`; `meldinglocaties` met een default filter
`systemisch = 0`.

**Afwijking van het ontwerpdocument:** het `.qgz`-projectbestand vervalt. Een QGIS-project met de
hand samenstellen is broos (padverwijzingen, versieafhankelijke XML) en zonder QGIS in de
buildomgeving niet automatisch te verifiëren. De embedded stijl plus losse QML dekt de eis "opent
met opmaak zonder handmatige stappen".

### 7.4 Bestandsnaam en CLI

`dq_<dataset>_<rundatum>.gpkg`, bijvoorbeeld `dq_dewolden_20260816.gpkg`, in de uitvoermap.
`toets` schrijft hem standaard mee; `--geen-gpkg` slaat hem over. De export overschrijft nooit een
invoerbestand — dezelfde controle als `_check_target()` nu doet.

---

## 8. Grensregel, gebied, prioriteit en systemisch

### 8.1 Grensregel (harde eis)

- **Zonder studiegebied:** de volledige TTL gaat mee, `scope = geen_studiegebied`.
- **Met studiegebied:** het gebied is de grens. Featurelagen en `meldinglocaties` bevatten alleen
  objecten binnen of snijdend met het gebied; `meldingen` bevat de bevindingen van die objecten.
  De checks draaien onverminderd op de volledige dataset; de begrenzing gebeurt bij de export.
- **Snijdende strengen** tellen als binnen en worden **niet geclipt**; de geometrie blijft intact.
  Dat is al het gedrag van `StudyArea.bevat()`.
- **Nul objecten binnen het gebied** is een harde fout: `toets` faalt met bijvoorbeeld
  "studiegebied `cbs_buurt_koekangerveld:buurt_gegeneraliseerd` (43,2 ha) bevat geen enkele put en
  geen enkele streng; controleer de laagkeuze en of het gebied binnen het beheergebied ligt", en er
  wordt niets weggeschreven. Nul *bevindingen* bij wel aanwezige objecten blijft een geldige
  uitkomst.
- Een leeg, ongeldig of onleesbaar studiegebiedbestand faalt al hard in `load_study_area()`; dat
  blijft zo.
- De gehanteerde grens staat in `gwsw_run` én in het MD-rapport.

### 8.2 `gebied`

`load_study_area()` gaat de attributen van de gekozen laag meelezen en zet ze op `StudyArea`. Is er
een `statcode`- en `statnaam`-kolom (het Koekangerveld-bestand heeft beide), dan wordt `gebied`
`"BU16901203 Koekangerveld"`; anders de laagnaam. Zonder studiegebied blijft de kolom leeg.

Er is geen buurtdekkende laag voor het hele beheergebied beschikbaar — het aangeleverde bestand
bevat één feature — en die is ook niet nodig, want de export is tot het gebied begrensd. Dit
beantwoordt openstaande beslissing 2 uit het GPKG-ontwerpdocument.

### 8.3 `prioriteit`

- 1 = ernst F op een object van een klasse uit de nieuwe configlijst `klassen.kritiek`
  (default: overstortput, bergbezinkvoorziening, gemaal);
- 2 = overige F;
- 3 = W.

Geen netwerkanalyse voor de hoofdafvoerroute; het ontwerpdocument staat een objecttype-lijst als
eerste versie expliciet toe.

### 8.4 `systemisch`

Generiek en nu al gebouwd: een check is systemisch als haar aantal bevindingen boven
`rapport.systemisch_drempel` (default 0,80) van haar `examined`-populatie uitkomt. Op de
registerchecks slaat dat vrijwel nooit aan, maar de kolom, de telling in `overzicht_checks` en het
stijlfilter staan er dan al, zodat ronde 2 puur additief is.

De tellingen `n_fout` en `n_waarschuwing` op de featurelagen sluiten systemische meldingen uit;
`n_systemisch` telt ze apart.

---

## 9. Configuratie

Nieuw blok in `checks.toml`; geen drempel staat in de code.

```toml
[rapport]
# A1: boven welk aandeel strengen met stijgende bodem de rode draad wordt benoemd.
richtingsdrempel = 0.10
# A1: vanaf hoeveel verschillende checks op een object dat als een enkele fout geldt.
multi_melding_checks = 3
# A5.1: 0 = alle bevindingen tonen.
max_bevindingen_per_check = 0
# Boven welk aandeel van de bekeken populatie een check systemisch heet.
systemisch_drempel = 0.80
# Versie van het checkregister, voor de metadata in de GPKG.
register_versie = "v0.7"
```

Aanvulling op `[klassen]`:

```toml
# Prioriteit 1: ernst F op deze klassen weegt het zwaarst.
kritiek = ["Overstortput", "Bergbezinkbassin", "Gemaal"]
```

---

## 10. Tests en acceptatie

**Ankerpunten.** 113 bevindingen (57 F, 56 W), NET-001 = 24 in 2 clusters, EXT-008 = 16 blijven
gelden — de naamfix verschuift geen aantal. Wijkt een van deze getallen tóch af, dan is dat een
signaal om te onderzoeken, niet een nieuwe verwachting om vast te leggen.

1. **Graaf-regressietest** — geen enkele knoop in de netwerkgraaf heeft uitsluitend
   orientatie-aspecttypen, en de eindknoop-verdeling bevat geen `*orientatie`-naam. Op een
   handgeschreven TTL-fixture met een gemaal en een uitlaatconstructie.
2. **GPKG-tests**, alle via `sqlite3` op het geschreven bestand:
   a. run mét studiegebied bevat uitsluitend features binnen of snijdend de grens;
   b. run zonder studiegebied bevat de volledige dataset;
   c. een studiegebied zonder objecten geeft een foutmelding en schrijft niets;
   d. elke rij in `meldingen` heeft een geldige, unieke `melding_id`, en paarmeldingen
      (TOP-005/006/010/011/013/019) hebben `feature_id_2` gevuld;
   e. `layer_styles` bevat per featurelaag een default-stijl waarvan de QML welgevormd is
      (`xml.etree`) en de laagnaam klopt;
   f. het bestand voldoet aan de GPKG-basis: `application_id`, verplichte tabellen, srs 28992,
         en `studiegebied._ontleed_gpkg()` kan de geschreven geometrieën teruglezen.
3. **Grammatica** — unittests op enkelvoud/meervoud en lidwoorden voor elk gegenereerd sjabloon,
   plus de eis dat een onbekend woord een `KeyError` geeft.
4. **Consistentietest** — per check exact gelijke aantallen in MD, CSV en GPKG.
5. **Melding-ID** — stabiel als de meldingtekst verandert; verschillend als het feit verandert;
   HGT-003-paren op dezelfde streng krijgen verschillende ID's.
6. **Synthese** — een fixture onder de drempel levert géén "Rode draad"-kop op; een fixture erboven
   wel, met het juiste percentage.
7. **Foutlocaties** — per regel uit §4 een gerichte test, inclusief de terugval "geen punt" en de
   telling daarvan in `gwsw_run`.

Fixtures zijn kleine handgeschreven TTL's met precies één ingebouwd defect. De volledige De
Wolden-run draait als integratietest onder de marker `zwaar`.

Na elke wijziging `pytest` en `ruff`; vóór de commit `/superpowers:requesting-code-review`.

---

## 11. Afwijkingen van de instructie en het ontwerpdocument

| # | Bron | Afwijking | Reden |
|---|---|---|---|
| 1 | Instructie §A3 | Naamgevingsfix in plaats van graaf-fix; geen verschuiving in de NET-aantallen | De graaf bevat geen orientatie-aspecten; geverifieerd in de TTL en in `_read_nodes()`. Zie §6.3 |
| 2 | Instructie §A5.3, §A6 | CSV en GPKG volgen de MD-afbakening in plaats van alles te bewaren met scopestatus | Beslissing van de opdrachtgever tijdens de brainstorm; lost tegelijk de tegenstrijdigheid met §3.1 op |
| 3 | Instructie §3.2 | Nulmeting-integratie naar ronde 2 | Drie nieuwe onderdelen bovenop de rest; "kleine stappen" en "nooit meer dan de actuele fase" uit CLAUDE.md |
| 4 | Instructie §3.2 | `--shacl` in plaats van `--mds` / `--hyd` | Die vlaggen bestaan niet; `--shacl` neemt alle drie de CFK-rapporten aan, wat CLAUDE.md ook vereist |
| 5 | Ontwerp §1 | Geen `.qgz`-projectbestand | Broos met de hand te maken en niet automatisch te verifiëren zonder QGIS; zie §7.3 |
| 6 | Instructie §A6 | CSV-kolomnamen in de bestaande CamelCase-stijl; GPKG wél snake_case | Hernoemen breekt bestaande tests en verwerking zonder tegenprestatie |
| 7 | Ontwerp §2.3 | Hash uitgebreid met identificerende detailsleutels | `check_id + feature_id + feature_id_2` botst bij HGT-003-paren op dezelfde streng |
| 8 | Ontwerp §5.2 | `gebied` uit het studiegebiedbestand in plaats van een aparte buurtenlaag | Er is geen dekkende buurtenlaag, en die is bij een begrensde export niet nodig |
| 9 | Instructie §A6, ontwerp §2.3 | `object2` alleen gevuld bij TOP-005, TOP-006, TOP-010 en TOP-011 | TOP-013 en TOP-019 hebben geen enkele tegenpartij maar een verzameling; die staat in de details, niet in een kolom die één object suggereert |
| 10 | Ontwerp §3 | `Check.id_sleutels` heeft `("zijde",)` als default in plaats van `()` | Negen meldingen in vier modules gebruiken `zijde` als onderscheid; een lege default zou botsingen laten afhangen van wie eraan denkt. Een check met een eigen onderscheid declareert dat nog steeds zelf (ATTR-005 doet dat met `kenmerk`) |
| 11 | Ontwerp §7.3 | Symboolgrootte is vast per ernstcategorie, niet afgeleid van `n_fout + n_waarschuwing` | Een data-defined grootte is QGIS-versiegevoelige XML die zonder QGIS in de buildomgeving niet te verifiëren is. Dezelfde afweging als bij het `.qgz`-bestand: liever een stijl die aantoonbaar werkt dan een die het misschien doet |
| 12 | Ontwerp §6.6 | `taal.LIDWOORDEN` bevat twee woorden, niet de negen uit de opsomming | Alleen woorden opnemen die daadwerkelijk in een meldingsjabloon voorkomen; een onbekend woord valt hard om, dus de lijst groeit vanzelf mee met de sjablonen |

---

## 12. Openstaand na deze ronde

- Ronde 2: nulmeting-meldingen in de GPKG (focusnode-herleiding, Mds/Hyd-deduplicatie,
  systemisch-vlag op nulmetingtypen, vertaaltabel of doorgifte van de SHACL-boodschappen —
  openstaande beslissing 4 uit het ontwerpdocument).
- Openstaande beslissing 3 uit het ontwerpdocument (representatiepunt voor stelselmeldingen) is in
  §4 regel 5 beantwoord voor deelstelselmeldingen; stelselmeldingen uit de nulmeting volgen in
  ronde 2.
- De 19 nog niet gebouwde TOP- en NET-checks uit het register blijven openstaan.
