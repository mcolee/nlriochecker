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

### Rapporteren per gebied

Met `--studiegebied` wordt de rapportage tot dat gebied beperkt. Bevat het bestand meer
dan een feature, dan rapporteert `toets` per feature:

```bash
nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --studiegebied data/gis/buurten.gpkg \
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

Alle vier de uitvoervormen komen uit dezelfde meldingenstroom, dus ze kunnen niet uit
elkaar lopen. Elk geschreven bestand noemt waarmee het gemaakt is: de Markdown-rapporten
in een regel onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het
veld `gereedschap` van de tabel `gwsw_run`, de JSON in het enveloppeveld `gereedschap`.
Een rapport is daarmee altijd te herleiden tot de versie die het opleverde.

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
