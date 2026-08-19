# nlriochecker

Python package die helpt met het analyseren en rapporteren over (mogelijke-) fouten in
GWSW-OroX (TTL) bestanden. Maakt gebruik van GWSW nulmeting maar biedt ook aanvullende
checks.

## Gebruik

De nulmeting inlezen en samenvatten. De dataset moet altijd aan alle drie de
conformiteitsklassen getoetst zijn, dus geef alle rapporten mee:

```bash
nlriochecker analyseer \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --output uitvoer
```

De eigen checks uit het checkregister op de OroX-dataset draaien:

```bash
nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --output uitvoer
```

Verder: `nlriochecker dekking` toetst de nulmeting tegen het checkregister, en
`nlriochecker vergelijk --eerder ... --later ...` zet twee meetmomenten naast elkaar voor
de trend. Elk subcommando kent `--help`.

### Toetsen op een deelverzameling conformiteitsklassen

Standaard moet de dataset aan alle drie de klassen getoetst zijn en faalt de pijplijn bij
een ontbrekend rapport. Met `--cfk` kies je expliciet een deelset:

```bash
nlriochecker analyseer \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --cfk Hyd \
  --output uitvoer
```

De optie staat op `analyseer`, `dekking`, `toets` en `vergelijk`, mag meermaals mee, en
accepteert alleen klassen uit `vereiste_cfk` in de projectconfiguratie. Een rapport voor
een klasse buiten de keuze is een fout, geen stille overslag.

Elke afwijking van de volle set wordt gemarkeerd: een waarschuwingsregel boven elk
Markdown-rapport, en de velden `cfk_set` en `volledig` in de tabel `gwsw_run` van de
GeoPackage en in de JSON-envelop. `vergelijk` weigert twee meetmomenten met ongelijke
sets, want een daling die uit een kleinere getoetste set komt is geen verbetering.

`bevindingen.csv` draagt de markering **niet**: de CFK-set hoort bij de run en niet bij
elke melding. Twee CSV's uit een volle en een deelrun zijn daardoor aan het bestand zelf
niet te onderscheiden. Lees zo'n CSV naast het rapport of de JSON van dezelfde run.

Een `toets` zonder `--shacl` meldt dat er niet tegen de conformiteitsklassen gemeten is.
Dat is een eigen toestand, los van "volledig" en van "deelset".

### De nulmeting tussen de eigen bevindingen

Met `--shacl` komen de SHACL-overtredingen zelf ook in de uitvoer terecht, naast de
bevindingen van de eigen checks en uit dezelfde meldingenstroom. Ze dragen
`Bron = nulmeting`, `Categorie = NULMETING` en een check-ID dat de SHACL-vorm noemt
(`NULMETING-LengteLeiding_val`). De kolom `CFK` -- in de JSON het veld `cfk` -- zegt welke
conformiteitsklassen de overtreding noemen.

Dezelfde overtreding staat vaak in meerdere CFK-rapporten. Er komt er dan **een**, met
alle klassen erbij: de kaart en de kolom `n_fout` tellen gebreken, geen rapportregels.
Een telling per klasse telt zo'n melding bij elke genoemde klasse mee, dus de som over de
klassen ligt hoger dan het totaal.

De focusnode van een SHACL-melding is meestal een put of een streng, en anders een
onderdeel daarvan: het eindpunt van een leiding, de maaiveldorientatie van een put. Zo'n
onderdeel wordt via `hasPart`, `hasAspect` en als laatste `hasConnection` omhooggelopen
tot het object waar het bij hoort. Op De Wolden herleidt daarmee 99,5% van de
overtredingen tot een put of een streng. Komt de focusnode nergens op uit -- een
klassenaam uit `CfkTypes_typ`, een stelsel dat geen kaartobject is -- dan blijft de
melding staan zonder object, zonder plek op de kaart en met een leeg gebied. Het rapport
telt die gevallen expliciet, ook als het er nul zijn.

Op de De Wolden-export leveren de drie rapporten samen 213.500 regels, en na ontdubbeling
105.963 meldingen: 87.017 fouten en 18.946 waarschuwingen. Dat is geen modelleerfout maar
de uitslag van de nulmeting zelf; de zwaarste posten zijn drie kardinaliteitsvormen die
vrijwel elke inspectieput raken. Precies daarvoor is de systemisch-vlag: die zegt dat het
over de export als geheel gaat en niet over een los gebrek.

### Rapporteren per gebied

Met `--studiegebied` wordt de rapportage tot dat gebied beperkt. Bevat het bestand meer
dan een feature, dan rapporteert `toets` per feature:

```bash
nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --studiegebied data/gis_koekangerveld/buurten.gpkg \
  --output uitvoer
```

```
uitvoer/
  koekangerveld/     bevindingen.md, bevindingen.csv, bevindingen.json, dq_*.gpkg
  zuidwolde_noord/   idem
  totaal/            synthese.md, bevindingen.csv, bevindingen.json
```

De mapnaam is de gesaneerde `naam_gebied`: diakrieten eraf, lowercase, alles wat geen
letter of cijfer is naar een underscore. In de rapporten, de kolom `Gebied` en de JSON
blijft de originele naam staan.

Met `--gebied` beperk je de run tot een of meer gebieden (meermaals opgeefbaar, exacte
naam). Het volledige bestand wordt altijd eerst gevalideerd: een deelrun mag een defect
in een ander gebied niet maskeren. De synthese vermeldt dat het een selectie was en
hoeveel gebieden het bestand telde.

De dataset wordt ook bij tachtig gebieden precies een keer geladen, en per gebied wordt
een eigen kern, contextschil en uitgedunde dataset gebouwd. De meldingen van een gebied
zijn daardoor gelijk aan die van een losse run met alleen dat gebied; daar staat een
test op.

Een gebied zonder GWSW-objecten -- water, natuur, een bedrijventerrein op eigen beheer --
stopt een meervoudige run niet: het krijgt een eigen rapport met nul bevindingen en een
expliciete regel dat er niets te toetsen viel, en de synthese noemt het apart. Bij een run
op een enkel gebied blijft dat een harde fout, want daar is het bijna altijd een verkeerd
bestand of een verkeerde laag.

Een object dat meerdere gebieden raakt telt in elk rakend gebied mee -- elk gebied ziet
zijn eigen volledige werkelijkheid. Er wordt niet ontdubbeld. De totaalsynthese telt de
unieke meldingen en zegt hoeveel er in meer dan een gebied voorkomen, zodat de som der
delen verklaarbaar afwijkt van het totaal. In `totaal/` staat geen GeoPackage: de
featurelagen zijn per gebied afgebakend, en een unie ervan zou grensobjecten dubbel
bevatten of ze stilzwijgend ontdubbelen.

`analyseer`, `dekking` en `vergelijk` werken op de SHACL-rapporten en kennen geen
studiegebied. Wil je twee meetmomenten per gebied vergelijken, richt `vergelijk` dan op
de uitvoer van een gebied tegelijk: map tegen map.

#### Eisen aan het studiegebiedbestand

GeoPackage of GeoJSON in EPSG:28992. De GeoPackage moet `srs_id = 28992` dragen; voor
GeoJSON, dat formeel alleen WGS84 kent, geldt een legacy `crs`-member die EPSG:28992
noemt, en anders moeten alle coordinaten binnen de RD-grenzen uit de projectconfiguratie
(`[drempels] rd_x_min` en verder) vallen. Buiten bereik is een harde fout met de melding
dat het bestand vermoedelijk in WGS84 staat.

Alleen `Polygon` en `MultiPolygon` worden geladen; een `GeometryCollection` wordt niet
uitgepakt. Overgeslagen typen worden geteld en gemeld -- in het logboek en in de
synthese. Blijft er geen enkel vlak over, dan faalt de run.

Vanaf twee features is een kolom of property `naam_gebied` verplicht: aanwezig, per
feature gevuld en uniek, en twee namen mogen niet dezelfde mapnaam opleveren. De mapnaam
`totaal` is gereserveerd voor de synthese en dus als gebiedsnaam verboden. Bij een
enkele feature verandert er niets ten opzichte van eerdere versies; een aanwezige
`naam_gebied` wordt dan wel de gebiedsaanduiding, anders blijft de terugval op
`statcode`/`statnaam` of de laagnaam gelden.

### Uitvoer

`analyseer`, `dekking` en `vergelijk` schrijven Markdown en CSV. `toets` schrijft
daarnaast een GeoPackage met de bevindingen op locatie (`--geen-gpkg` slaat die over) en
`bevindingen.json` met de volledige meldingenstroom (`--geen-json` slaat die over). Dat
JSON-bestand is een geversioneerd contract voor machinale verwerking; zie
[docs/json-schema.md](docs/json-schema.md). `--output` staat standaard op `uitvoer/`.
Invoerbestanden worden nooit overschreven.

De GeoPackage heeft twee objectlagen: `putten` (punt) en `strengen` (lijn), met de
gebreken *op* het object. Elk object draagt een kolom `status` met precies vier waarden --
`rood` bij een fout, `oranje` bij alleen waarschuwingen, `groen` als er geen eigen gebrek
is, `grijs` als er niet beoordeeld is -- en een kolom `popup_html` met de voorgebakken
hoverpopup. Mechanisch riool staat tussen de strengen met status `grijs`: het objecttype
klopt, alleen is er niets getoetst. Met een studiegebied staat de contextschil er ook
grijs bij, zodat de kaart niet bij de gebiedsgrens ophoudt alsof daar niets ligt. De
popup zegt per grijs object waarom.

`status` telt systemische meldingen niet mee, net als `ergste_ernst`, `n_fout` en
`n_waarschuwing`. Een object waarvan álle meldingen systemisch zijn is dus groen; dat
betekent "geen gebrek dat dit object van zijn buren onderscheidt", niet "in orde". De
kolom `n_systemisch` en de popup zeggen het er allebei bij.

Er is geen laag `meldinglocaties` meer. Alle meldingen staan in de tabel `meldingen`,
joinbaar op `feature_id`, met de foutlocatie in de kolommen `x` en `y`. Wat daarmee van de
kaart verdween is de exacte plek van een melding op een lijn -- het snijpunt van een
kruising, het midden van een streng -- en het naloopwerk zonder joins; wie de punten terug
wil, maakt er in QGIS een geometriegenerator van.

Daarnaast bevat de GeoPackage twee lagen met de externe objecten waarnaar de
EXT-checks verwijzen: `bouwwerken` (elk BGT-pand, BAG-pand of overig bouwwerk waarover
EXT-001 meldt, rood omlijnd) en `waterdelen_zonder_zinker` (elk BGT-waterdeel waarover
EXT-003 meldt, blauw omlijnd). Beide lagen worden uitsluitend gevuld vanuit de
meldingen van die uitvoer: wat erin staat is exact wat de check gemeld heeft, niet meer
en niet minder. Kruisingen mét geregistreerde zinker of duiker (EXT-002) blijven er dus
buiten, en bij rapportage per gebied bevat elk gebied alleen zijn eigen treffers. De
lagen bestaan altijd, ook leeg.

#### Wat je in QGIS ziet

De GeoPackage brengt haar eigen opmaak mee (tabel `layer_styles`), dus openen volstaat.
Het symbool zegt wat voor GWSW-object het is -- de indeling komt uit de PDOK-SLD's -- en
de kleur zegt uitsluitend hoe het ervoor staat: rood bij een fout, oranje bij alleen
waarschuwingen, groen als er geen eigen gebrek is, grijs als er niet beoordeeld is. Rood
is duidelijk donkerder dan groen, zodat de twee ook in grijstinten en bij kleurenblindheid
uit elkaar te houden zijn. Een objecttype dat de symbolentabel niet kent krijgt een
vangnetsymbool met het legendalabel "objecttype niet in de symbolentabel"; er is geen
stille default.

Een streng draagt daarbovenop een richtingpijl: groen als het BOB-verval met de getekende
lijn meeloopt, **rood en omgekeerd** als het daar tegenin loopt -- de pijl wijst dan waar
het water werkelijk heen loopt -- en grijs als de richting niet te bepalen is.

Hoveren over een object toont een popup met het label, het GWSW-type, de status en tot
vijf meldingen, elk met ernst-symbool, check-ID, boodschap en herkomst (`nulmeting ·
MdsPlan` of `eigen check`). Bij een streng staan ook het stelsel, de lengte en de
BOB-richtingsregel erin; bij een grijs object waarom het niet beoordeeld is.

> **Zet "Show Map Tips" aan.** QGIS toont map tips alleen als die knop in de werkbalk
> ingedrukt is (View → Show Map Tips, of het icoon met de gele tooltip). Staat hij uit,
> dan gebeurt er bij hoveren niets -- en dat leest als kapot terwijl het een instelling is.

Alle vier de uitvoervormen komen uit dezelfde meldingenstroom, dus ze kunnen niet uit
elkaar lopen. Elk geschreven bestand noemt waarmee het gemaakt is: de Markdown-rapporten
in een regel onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het
veld `gereedschap` van de tabel `gwsw_run`, de JSON in het enveloppeveld `gereedschap`.
Een rapport is daarmee altijd te herleiden tot de versie die het opleverde.

### Externe bronnen en hun dekking

`--bronnen` wijst de map met BGT, BAG, NWB en het AHN-raster aan. Welke bestanden en
laagnamen dat zijn staat in `[bronnen]` van de projectconfiguratie, samen met
`studiegebied`: de polygoon die het gebied afbakent waarvoor je die bronnen geldig
verklaart. Objecten daarbuiten krijgen geen EXT-uitslag maar de status *buiten
studiegebied*, en dat wordt geteld in het rapport.

Bij het laden wordt elke aangeleverde bron getoetst op dekking van dat bereik, voordat
er ook maar een check draait. Een laag die kleiner is dan het gebied waarvoor hij geldt
levert namelijk geen fout op maar stilte: de check draait, vindt niets, en dat leest
als "geen probleem". Een tekort is daarom een harde fout die per bron beide omhullenden
en het tekort per zijde noemt. De vectorlagen moeten het bereik plus de grootste
EXT-zoekafstand dekken; het raster alleen het bereik zelf, want bemonsteren is
puntsgewijs.

Wat die toets niet kan: een gat midden in een extract valt er niet mee op, en een
tekort op een dunne laag betekent "hier staan geen features" en niet per se "extract
afgeknipt". Daarvoor is `[bronnen] dekking_tolerantie_m`, standaard `0.0`. Voor de
bronnen in `data/gis_koekangerveld` is ongeveer `300` nodig: `bgt_bouwwerk` telt 52
objecten die aan de oostkant 276 m voor de rand ophouden, wat aan die bron niets
mankeert.

De tolerantie geldt voor alle lagen tegelijk. Dekt een enkele laag het gebied echt niet,
zet die laag dan uit in plaats van de tolerantie op te rekken: `bgt_putdeksellagen = []`
schakelt EXT-005 en EXT-006 uit met een uitleg in het rapport, terwijl een tolerantie van
kilometers de poort voor elke bron opheft.

### Projectconfiguraties

`configs/` bewaart de projectconfiguraties van de gebieden waarop dit project draait; geef
er een mee met `--projectconfig`. `configs/dewoldenhoogeveen.toml` hoort bij de bronnen in
`data/gis_dewoldenhoogeveen` en beslaat het hele gebied van de OroX-dataset. Zonder die
optie geldt de meegeleverde `src/nlriochecker/checks.toml`, die naar Koekangerveld wijst.

Let op: `--projectconfig` vervangt de configuratie in haar geheel; er is geen overlay. Een
projectconfiguratie is dus een volledige kopie van `checks.toml`, en een drempel die daar
verandert moet in elke kopie na.

### Voortgang

`toets` toont bij de zware stappen een voortgangsbalk: het inlezen van de TTL's, het
inlezen van de SHACL-rapporten, het draaien van de checks (met het lopende check-ID) en
het wegschrijven van de GeoPackage. De balk gaat naar stderr, zodat de tellingen en de
geschreven paden op stdout schoon blijven voor wie de uitvoer doorpipet; buiten een
terminal valt hij terug op een enkele regel per fase.

Wie de package als library gebruikt, geeft een eigen implementatie van het protocol in
`nlriochecker.voortgang` mee. Zonder argument gebeurt er niets: voortgang is weergave en
raakt de uitkomst van een run nergens.

## Ontwikkelen

```bash
uv sync
uv run pytest          # zware tests draaien niet mee; `-m zwaar` wel
uv run ruff check
uv run ruff format --check .
uv run mypy             # over src/nlriochecker
```

Dezelfde vier stappen draaien in CI op elke push naar `main` of `dev`
(`.github/workflows/toets.yml`) en in `scripts/uitgave.py` bij een uitgave. Een schone
kloon mist de niet-getrackte delen van `data/`; de tests die daarop leunen slaan dan
over, en CI bewaakt met `NLRIOCHECKER_MIN_GESLAAGD` dat dat er niet te veel worden.

Wat er per versie veranderde staat in [CHANGELOG.md](CHANGELOG.md); zet nieuwe
wijzigingen onder `## [Unreleased]`.

Een nieuwe versie uitbrengen gaat met `uv run python scripts/uitgave.py patch|minor|major`.
Zie [docs/versionering.md](docs/versionering.md).

## Licentie

Copyright © 2026 Martin Colee

Licensed under the EUPL

Dit werk valt onder de [European Union Public Licence v1.2](LICENSE) (EUPL-1.2). Dat is
een copyleft-licentie: verspreid je een aangepaste versie, of geef je anderen toegang tot
de wezenlijke functionaliteit ervan — ook online, als dienst — dan gaat dat onder dezelfde
licentie, met de broncode erbij. De EUPL is in 23 talen rechtsgeldig; de
[Nederlandse tekst](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12) telt
even zwaar als de Engelse hierboven.
