# Ontwerp ronde 2: uitvoer, afbakening en checkregister v0.8

Datum: 2026-08-16. Aanleiding: acht aandachtspunten van de opdrachtgever na de eerste
echte uitvoer (`uitvoer/koekangerveld_ronde2/`), plus de vraag of dit tot versie 0.8 van
het checkregister moet leiden. Voorganger: `2026-08-16-gpkg-en-rapport-design.md`.

## 1. Geverifieerde feiten

Vastgesteld tijdens de brainstorm, niet aangenomen:

| Feit | Meting |
|---|---|
| Inlezen De Wolden (112 MB TTL plus totaal-ontologie) | 176 s, circa 3 GB |
| Draaien van de volledige registry op die dataset | 69 s, 35.975 bevindingen |
| Omvang dataset | 23.485 knooppunten, 23.440 verbindingen |
| Mechanische leidingen in de export | 3.548 Persleiding, 147 Vacuumleiding, 25 Drukleiding |
| QGIS laadt de stijlen uit de huidige GPKG | nee: `loadDefaultStyle()` geeft `False` op alle drie de lagen |
| Reden | `layer_styles` staat niet in `gpkg_contents`; de OGR-provider vindt de tabel dan niet |
| Na registratie als `data_type = 'attributes'` | alle drie de lagen: `('Loaded from Provider', True)` |
| Losse QML naast een GPKG met meerdere lagen | werkt niet; een sidecar-QML geldt alleen voor een bestand met een enkele laag en heet naar het bestand |

De QGIS-metingen zijn gedaan met de QGIS van deze machine via PyQGIS, offscreen, op een
kopie van de bestaande uitvoer.

## 2. Ontwerpbesluiten uit de brainstorm

| # | Punt | Keuze |
|---|---|---|
| 1 | Stijlen | `layer_styles` registreren in `gpkg_contents`; losse `.qml`-bestanden vervallen |
| 2 | EXT-008 | Vervalt, ID wordt niet hergebruikt |
| 3 | EXT-001 | Putten erbij, relatie `binnen` / `kruist` / `nabij` als waarde; ernst blijft W |
| 4 | Richtingspijlen | Twee pijlen bij strijd, grijze pijl met eigen legenda-regel bij onbekende BOB |
| 5 | Stapeling | Stapelkolommen plus datagestuurde schermoffset; geometrie blijft exact |
| 6 | Afbakening | Contextschil én datasetcache |
| 7 | Mechanisch riool | Alleen leidingen naar een eigen grijze laag; gemalen blijven in `putten` |
| 8 | `feature_id` | URI-fragment, volledige URI in `gwsw_uri` |
| 9 | Register | v0.8 met de contractwijzigingen én het scopebeleid |

## 3. Stijlen in de GeoPackage

`_schrijf_stijlen()` in `uitvoer/gpkg.py`:

- registreert `layer_styles` via `_registreer(..., 'attributes', ...)`; die zet `srs_id`
  op `null`, wat de spec voor een tabel zonder geometrie voorschrijft. De tabel zelf
  houdt haar eigen `create table` met de kolomnamen die QGIS verwacht;
- schrijft `update_time` als `strftime('%Y-%m-%dT%H:%M:%fZ','now')` in plaats van het
  SQLite-standaardformaat, anders meldt GDAL bij elke rij "non-conformant content";
- schrijft geen losse `.qml`-bestanden meer. Ze kunnen niet automatisch toegepast worden
  en suggereren het tegendeel. Wie een stijl los wil hebben, exporteert hem uit QGIS.

De commentaarregel in de docstring die stelt dat QGIS `layer_styles` zelf ook niet
registreert, is onjuist gebleken en wordt vervangen door de geverifieerde reden.

Elke laag met geometrie krijgt een stijl: `putten`, `strengen`, `meldinglocaties` en de
nieuwe `mechanisch_riool`.

## 4. Afbakening tot het studiegebied

### 4.1 De analyseset

Nieuw: `src/gwswpijplijn/afbakening.py`.

```
Analyseset(kern: frozenset[str], schil: frozenset[str], dataset: GwswDataset,
           volledig_aantal: int)   # plus de properties `alles` en `aandeel`
```

`bouw_analyseset(dataset, area, config)` bepaalt:

1. **kern** — objecten waarvan de geometrie het gebied raakt; dit is de bestaande
   `objecten_in_gebied()`, ongewijzigd van betekenis.
2. **contextschil**, de vereniging van:
   - de samenhangende netwerkcomponenten die de kern raken, berekend over de
     **vrijvervalleidingen** (`klassen.vrijvervalleiding`). Bewust niet over de
     mechanische leidingen: die verbinden dorpen onderling en zouden de component tot
     bijna de hele gemeente laten uitdijen, terwijl de NET-checks ze niet volgen;
   - alle objecten binnen `studiegebied.context_buffer_m` van het gebied, ongeacht
     klasse. Dit vangt de checks die naar nabijheid kijken zonder netwerkverband:
     TOP-005, TOP-006, TOP-010, TOP-011, TOP-021 en de EXT-checks.

`dataset.subset(uris)` geeft een `GwswDataset` terug met alleen die knopen en
verbindingen; `closure`, `ontologies`, `source`, `decode_fallback` en `structural_diff`
gaan ongewijzigd mee, `geometry_errors` wordt meegefilterd.

### 4.2 Waarom dit geen randeffecten geeft

Bereikbaarheid (NET-001, NET-002), kringen (NET-004) en buurstrengvergelijking (NET-005,
NET-006) redeneren binnen een samenhangende component; door de hele component mee te
nemen is hun uitkomst op de kern gelijk aan die op de volledige dataset. De
nabijheidschecks hebben geen netwerkverband nodig maar wel ruimtelijke buren; die levert
de buffer. Blijft over: checks die over de hele populatie gaan.

### 4.3 Dataset-brede checks

Een check kan `volledig_bereik = True` declareren; die draait op de volledige dataset in
plaats van op de analyseset. De lijst staat in `checks.toml` onder
`studiegebied.volledige_dataset_checks` en bevat vooralsnog ADM-002 (unieke
identificaties: een duplicaat kan overal in de export zitten). De volledige dataset is op
dat moment nog in geheugen, dus dit kost alleen de eigen looptijd van die check.

### 4.4 Wat het rapport erover zegt

De kop van het bevindingenrapport en `gwsw_run` melden drie getallen: geanalyseerd n
(kern k plus schil s) van totaal t. Per check blijft `examined` het aantal werkelijk
bekeken objecten, nu dus over de analyseset -- behalve bij een check met
`volledig_bereik`, die over de volledige dataset telt. Het rapport zegt van beide dat het
zo is.
Overschrijdt het aandeel van de component `studiegebied.component_waarschuwingsdrempel`
(voorstel 0,5) van de dataset, dan meldt de run dat de afbakening weinig oplevert. Dat is
een mededeling, geen fout.

Levert de analyseset geen enkel object op, dan geldt de bestaande harde fout uit
`beperk_tot_studiegebied()`.

De rapportage blijft ongewijzigd tot de kern beperkt: `beperk_tot_studiegebied()` blijft
staan en draait na de checks.

### 4.5 Datasetcache

Nieuw: `src/gwswpijplijn/cache.py`.

- Sleutel: sha256 over (a) inhoudshash van het datasetbestand, (b) inhoudshash van elk
  ontologiebestand, (c) de broncode van `dataset.py` en `geometry.py`, (d) de versies van
  rdflib en shapely. (c) en (d) voorkomen dat een wijziging in de lader stilzwijgend op
  een oude cache blijft draaien; dat is het enige echte risico van deze constructie.
- Opslag: `~/.cache/gwswpijplijn/<sleutel>.pickle` (XDG-cachemap als die gezet is),
  geschreven via een tijdelijk bestand plus `rename`, zodat een afgebroken run geen halve
  cache achterlaat.
- Formaat: `pickle` protocol 5, in twee bestanden. Gemeten op De Wolden (1.877.729
  triples): de structuren (knopen, strengen, klassenhierarchie) zijn 31 MB en lezen terug
  in 1,4 s, de rdflib-graaf is 423 MB en leest terug in 58 s; opnieuw parsen kost 176 tot
  205 s en de omweg via N-Triples 118 s. De graaf gaat daarom achter een luie
  plaatsvervanger: hij komt pas van schijf als een check hem aanraakt. Geen extra
  afhankelijkheid; de cachemap is van de gebruiker zelf.
- CLI: standaard aan, `--geen-cache` slaat over, `--cache-map` verlegt de locatie. De
  uitvoer meldt welke van de twee wegen gebruikt is en hoe lang die duurde.
- Een beschadigde of onleesbare cache is geen fout: hij wordt gemeld, genegeerd en
  opnieuw geschreven.

Verwachting op grond van die metingen: de koude run blijft ongeveer gelijk (176 s plus
circa 25 s wegschrijven). Een warme run die de graaf niet nodig heeft -- alleen
geometrie-, hoogte- en netwerkchecks -- kost seconden. Een warme run met de volledige
registry raakt de graaf via ADM-007 tot en met ADM-009, NET-007 en de RVZ-checks en komt
uit op ongeveer een minuut in plaats van vier. De eerdere schatting van tien seconden voor
een volledige run was te optimistisch: die ging eraan voorbij dat een deel van de checks
de rdflib-graaf zelf leest.

Wat dit niet oplost en wat een volgende ronde kan oppakken: de graaf pruimen tot de
triples die de checks werkelijk raken (hasPart, hasConnection, type, label, aspecten), of
die gegevens in de structuren opnemen zodat de graaf helemaal kan vervallen. Dat is een
ingreep in vier checkmodules en hoort niet in deze ronde.

### 4.6 Gevolg voor CLAUDE.md

De regel "Analyseer breed, rapporteer smal" wordt "Analyseer de kern plus een
contextschil, rapporteer de kern", met de reden erbij: de schil is precies zo groot dat
NET-001 en NET-002 geen valse bevindingen geven.

## 5. EXT-001: putten erbij en de relatie benoemd

- Populatie: vrijvervalstrengen én putten (`objecten()` levert beide, `soort` wordt
  "vrijvervalstrengen en putten").
- Relatie per bevinding, in deze volgorde bepaald: `binnen` als de geometrie volledig
  binnen het bouwwerk ligt, anders `kruist` als ze het bouwwerk snijdt, anders `nabij`
  binnen `ext_pand_buffer_m`.
- Ligt een object bij meerdere bouwwerken, dan telt de zwaarste relatie (binnen boven
  kruist boven nabij), en bij gelijke relatie het dichtstbijzijnde bouwwerk.
- De relatie komt in de kolom `waarde` van de melding, de buffer in `drempel`. Geen
  schemawijziging.
- De boodschap noemt relatie, bron en laag; bij `nabij` ook de afstand.
- Ernst blijft W, conform het register.

## 6. EXT-008 vervalt

`PandZonderRiolering` en de bijbehorende tests verdwijnen. Het ID komt in v0.8 in de
tabel met vervallen checks te staan, met de reden en de aantekening dat het niet
hergebruikt wordt. De dekkingmapping raakt dit niet: die gaat alleen over geschrapte
checks die de nulmeting dekt.

## 7. Mechanisch riool als eigen laag

- `checks.toml` krijgt `klassen.mechanisch = ["Persleiding", "Drukleiding",
  "Vacuumleiding"]`; de subklasse-afsluiting doet de rest.
- Nieuwe featurelaag `mechanisch_riool` (LINESTRING) met een smalle kolomset:
  `feature_id`, `label`, `objecttype`, `gwsw_uri`, `omschrijving`, `gebied`, `run_datum`,
  `dataset_versie`. `omschrijving` bevat "Mechanisch riool: niet geanalyseerd".
- `strengen` bevat voortaan alles behalve het mechanische stelsel. Verbindingen die in
  geen van beide klassenlijsten vallen (LozeLeiding, Drain, Duiker) blijven daar dus staan
  met hun eigen `objecttype`; ze verdwijnen niet.
- `gwsw_run` krijgt tellingen per laag, zodat zichtbaar is dat er objecten verhuisd zijn.
- Stijl: grijs, dun, met de omschrijving als legenda-regel.

## 8. Richtingspijlen op de strengen

- `strengen` krijgt `bob_verval_m` (BOB-begin minus BOB-eind, positief als de bodem met
  de lijnrichting mee daalt) en `richting_bob` met de waarden `mee`, `tegen` en
  `onbekend` (ontbrekende BOB's of verval nul).
- Beide worden afgeleid met dezelfde code die NET-003 en TOP-020 gebruiken, zodat kaart
  en bevinding niet uit elkaar kunnen lopen.
- Stijl: regelgebaseerd. Drie regels voor de lijnkleur (ernst F, W, geen) en drie
  regels die er pijlen overheen tekenen:
  - `richting_bob = 'mee'`: één groene pijl met de lijn mee;
  - `richting_bob = 'tegen'`: een pijl met de lijn mee (digitalisatierichting) en een
    tweede, 180 graden gedraaide pijl in een andere kleur (BOB-verval);
  - `richting_bob = 'onbekend'`: één grijze pijl met de lijn mee, eigen legenda-regel
    "BOB onbekend of vlak".

## 9. Stapelende meldingen

- `meldinglocaties` krijgt `stapel_aantal` en `stapel_nr` (1-gebaseerd), bepaald per
  foutlocatie afgerond op millimeters, in een vaste volgorde (melding-ID) zodat de
  nummering tussen runs gelijk blijft.
- De stijl zet ze uiteen met een datagestuurde offset in millimeters op het scherm:
  hoek `360 / stapel_aantal * stapel_nr`, straal oplopend per ring van acht. Bij
  `stapel_aantal = 1` geen offset.
- De geometrie blijft exact op de foutlocatie; wie de kolommen leest ziet ook zonder
  QGIS dat er meer meldingen onder liggen.

## 10. feature_id

- `feature_id` wordt het deel achter de `#` van de URI (`knp3437`, `lei3436-3435-1`).
  URI's zonder `#` blijven ongewijzigd; dat zijn de bevindingen op BGT- en BAG-objecten,
  die geen dataset-URI hebben.
- De volledige URI verhuist naar een nieuwe kolom `gwsw_uri`, in `putten`, `strengen`,
  `mechanisch_riool`, `meldingen` en `meldinglocaties`. `feature_id_2` krijgt op dezelfde
  manier `gwsw_uri_2`.
- De CSV volgt dezelfde kolommen; het Markdown-rapport toont het fragment.
- De melding-ID blijft over de volledige URI gehasht: ID's blijven stabiel ten opzichte
  van eerdere runs.

## 11. Checkregister v0.8

Nieuw bestand `data/checkregister-gwsw-nulmeting-v0_8.md`, met:

- EXT-008 vervallen (eigen tabel met vervallen checks, ID niet hergebruiken);
- EXT-001 herschreven: populatie putten én strengen, relatie binnen/kruist/nabij;
- mechanisch riool expliciet benoemd als niet-geanalyseerd, met verwijzing naar de eigen
  laag in de uitvoer;
- het scopebeleid: kern plus contextschil, met de onderbouwing waarom de NET-checks
  daarmee exact blijven;
- open punten bijgewerkt (onder meer punt 1, dat naar EXT-004 verwijst, en punt 4 over de
  mechanische scopegrens);
- versiehistorie met wat er wel en niet aan het contract verandert.

Meelopen -- alle vijf verwijzen nu naar v0.7:

- `rapport.register_versie` in `checks.toml`;
- `checkregister_versie` en `bron` in `dekking.toml` (`verify_register()` vergelijkt die
  met de versie uit het registerbestand en laat de dekkingcontrole falen bij verschil);
- `default_register_path()` en de docstring van `register.py`;
- `REGISTER` in `tests/test_checks_registry.py`;
- de tekst van het dekkingrapport, die de versie uit de config overneemt.

Het oude registerbestand blijft staan: eerdere runs verwijzen ernaar.

## 12. Testen

- **Stijlen:** kale sqlite-assertions (registratie in `gpkg_contents`, geldige XML, elke
  expressie verwijst naar een bestaande kolom van de laag) plus een PyQGIS-smoketest die
  per laag controleert dat `loadDefaultStyle()` de stijl uit de bron haalt. Die test
  wordt overgeslagen waar `qgis.core` niet importeerbaar is.
- **Afbakening:** een handgeschreven netwerk waarvan een streng het gebied uit loopt en
  pas ver daarbuiten een gemaal bereikt; zonder contextschil geeft NET-001 daar een valse
  bevinding, met schil niet. Plus een test dat een dataset-brede check op de volledige
  dataset draait.
- **Cache:** schrijven en teruglezen levert dezelfde uitkomsten; een gewijzigde
  loaderbroncode of ontologie geeft een andere sleutel; een beschadigd cachebestand leidt
  tot opnieuw inlezen en een melding.
- **EXT-001:** fixtures met een pand waar een streng doorheen loopt, een streng die er
  volledig in ligt, een put erin en een put ernaast.
- **Uitvoer:** kolomtests voor `gwsw_uri`, `feature_id`, de stapelkolommen, de
  richtingskolommen en de laag `mechanisch_riool`.
- **Register:** de bestaande pariteitstest tegen v0.8.
- **Zwaar:** een integratietest op De Wolden met studiegebied Koekangerveld, die de
  looptijd van de warme run vastlegt en controleert dat kern en schil kloppen.

## 13. Risico's

- **Verouderde cache.** Ondervangen door de broncodehash van de lader in de sleutel. Blijft
  gevoelig voor wijzigingen in modules die de lader gebruikt maar die niet in de sleutel
  zitten; daarom staat de sleutelopbouw in de docstring van `cache.py`.
- **Grote component.** Als het vrijvervalnet van een gemeente grotendeels samenhangt,
  levert de afbakening weinig snelheidswinst. De run meldt dat in plaats van te doen
  alsof.
- **QML's zijn niet door ruff of pytest gedekt.** Daarom de expressietest tegen de
  kolomnamen en de PyQGIS-smoketest.
- **Minder objecten in `strengen`.** Wie de vorige uitvoer naast de nieuwe legt ziet
  3.720 objecten verdwijnen; de tellingen in `gwsw_run` en een regel in het rapport
  maken duidelijk waarheen.

## 14. Buiten scope

- Sneller inlezen op een koude run. Een ruimtelijk voorfilter tijdens het parsen zou de
  176 s kunnen drukken, maar vraagt een eigen TTL-lezer; niet nu.
- De negentien nog ongebouwde TOP- en NET-checks.
- Waterschapsdata en BRK (EXT-004 blijft skelet).
