# nlriochecker

Toetst de datakwaliteit van vrijvervalriolering in een GWSW-OroX-export (TTL). Het leest de GWSW-nulmeting -- de
SHACL-rapporten van [apps.gwsw.nl](https://apps.gwsw.nl/item_validate_shacl) -- in en draait daarnaast een eigen
checkregister op de dataset zelf en op externe bronnen (BGT, BAG, NWB, TOP10NL, AHN). De uitkomst is een rapport
per gebied plus een kaart die je in QGIS opent.

[![toets](https://github.com/mcolee/nlriochecker/actions/workflows/toets.yml/badge.svg?branch=main)](https://github.com/mcolee/nlriochecker/actions/workflows/toets.yml)
[![licentie EUPL-1.2](https://img.shields.io/badge/licentie-EUPL--1.2-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

## Stand van zaken

Bruikbaar, maar in aanbouw: lees de uitkomst als het oordeel van een instrument dat nog groeit.

- **Fase 4 van vier.** De nulmeting inlezen, de dekkingsanalyse, de trendvergelijking en de eigen checks op de
  OroX-dataset (ADM, ATTR, BTR, HGT, NET, RVZ, TOP) staan; de EXT-checks tegen externe bronnen zijn de lopende fase.
- **Getoetst op één echte export:** die van De Wolden en Hoogeveen, bijna 47.000 objecten. Andere gemeenten en
  andere beheerpakketten zijn nog niet geprobeerd.
- **Niet op PyPI**, en de API en de CLI-opties kunnen nog wijzigen; alleen `bevindingen.json` draagt een eigen
  schemaversie. Welk versienummer dit is en wat er veranderde: [CHANGELOG.md](CHANGELOG.md).

## Wat je krijgt

Eén `toets` levert vier bestanden uit dezelfde meldingenstroom -- ze kunnen dus niet uit elkaar lopen.

**`bevindingen.md`** -- het rapport, van gebied naar detail: wat er in dit gebied ligt, of het aan de drie
conformiteitsklassen voldoet, de rode draad, de verantwoording (wat er *niet* bekeken is) en pas daarna de tabellen
per SHACL-vorm en per eigen check. [Meer](docs/gebruik.md#het-bevindingenrapport).

![De kop van bevindingen.md, met de gebiedstabel en de conformiteitsregels](docs/img/rapport-kop.png)

**`bevindingen.csv`** -- elke melding als rij: check-ID, ernst, object, gebied, locatie en boodschap.

**De GeoPackage** (`dq_<dataset>_<datum>.gpkg`) -- de bevindingen op de kaart, in de lagen `putten`, `strengen` en
`vlakken`: rood bij een fout, oranje bij alleen waarschuwingen, groen als er geen eigen gebrek is, grijs als er niet
beoordeeld is. Opmaak (`layer_styles`) en hoverpopup zitten erin ([meer](docs/gebruik.md#wat-je-in-qgis-ziet)).

![De drie lagen van de voorbeeldrun in QGIS](docs/img/kaart-koekangerveld.png)

**`bevindingen.json`** -- dezelfde meldingen als geversioneerd contract voor machinale verwerking
([docs/json-schema.md](docs/json-schema.md)). Welke bijproducten er komen kies je met `--uitvoer`; het rapport wordt
altijd geschreven ([meer](docs/gebruik.md#uitvoer)).

## Snel proberen

De repository draagt een compleet voorbeeld: de buurt Koekangerveld in de gemeente De Wolden, met de OroX-uitsnede,
de drie SHACL-rapporten, het studiegebied en de externe bronnen erbij. Drie commando's, samen enkele seconden werk:

```bash
uv tool install git+https://github.com/mcolee/nlriochecker
git clone https://github.com/mcolee/nlriochecker.git && cd nlriochecker
nlriochecker toets \
  --dataset voorbeelden/koekangerveld/koekangerveld_orox.ttl \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_MdsProj.csv \
  --studiegebied voorbeelden/koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg \
  --bronnen voorbeelden/koekangerveld \
  --output uitvoer/voorbeeld
```

Zonder [uv](https://docs.astral.sh/uv/) doet `pipx install git+https://github.com/mcolee/nlriochecker` hetzelfde.
Wat je ziet, ingekort -- er staat een regel per check:

```
koekangerveld_orox.ttl: 109 knooppunten, 107 strengen
  Analyseset: 98 objecten in de kern, 118 in de contextschil, van 216 in de export.
  ADM-010   F      2 bevindingen
  ...
  TOP-022   F      3 bevindingen
Totaal 84 fouten, 41 waarschuwingen uit de eigen checks; 201 overtredingen uit de nulmeting (162 fouten, 39 waarschuwingen)
Geschreven: uitvoer/voorbeeld/bevindingen.md
Geschreven: uitvoer/voorbeeld/bevindingen.csv
Geschreven: uitvoer/voorbeeld/dq_koekangerveld_orox_20260829.gpkg
Geschreven: uitvoer/voorbeeld/bevindingen.json
```

Vier bestanden, samen 337 meldingen; de GeoPackage draagt de rundatum in haar naam. Het hoogteraster (AHN) is te
groot voor een repository en gaat niet mee: HGT-001 tot en met HGT-003 melden daarom zelf dat ze niets konden
toetsen. Herkomst en licenties -- OroX De Wolden met toestemming gepubliceerd, BGT, BAG, NWB en GWSW CC0, TOP10NL
CC-BY 4.0 (Kadaster) -- staan in [voorbeelden/koekangerveld/README.md](voorbeelden/koekangerveld/README.md).

## Met je eigen data

1. **De OroX-export** van je areaal: het GWSW-uitwisselbestand (TTL) dat je beheerpakket levert.
2. **De drie SHACL-rapporten** van de GWSW-nulmeting op diezelfde export, gedraaid via
   [apps.gwsw.nl](https://apps.gwsw.nl/item_validate_shacl): één per conformiteitsklasse (Hyd, MdsPlan, MdsProj).
   Alle drie zijn verplicht; een deelset vraag je expliciet met `--cfk`, en dat voorbehoud komt in de uitvoer te
   staan ([meer](docs/gebruik.md#toetsen-op-een-deelverzameling-conformiteitsklassen)).
3. **Een map met externe bronnen** voor de EXT-checks (`--bronnen`): BGT, BAG, NWB, TOP10NL en het AHN-raster.
   Welke bestanden en laagnamen dat zijn staat in `[bronnen]` van de projectconfiguratie, en elke bron wordt vóór
   de eerste check op dekking van je gebied getoetst ([meer](docs/gebruik.md#externe-bronnen-en-hun-dekking)).
4. **Een projectconfiguratie** met je eigen drempels en bronpaden (`--projectconfig`, voorbeeld
   `configs/dewoldenhoogeveen.toml`). Die vervangt de configuratie in haar geheel -- er is geen overlay, dus zij is
   een volledige kopie van `src/nlriochecker/checks.toml` ([meer](docs/gebruik.md#projectconfiguraties)).

Rapporteren per buurt of wijk gaat met `--studiegebied`, desgewenst beperkt met `--gebied`; zie
[Rapporteren per gebied](docs/gebruik.md#rapporteren-per-gebied) en
[Eisen aan het studiegebiedbestand](docs/gebruik.md#eisen-aan-het-studiegebiedbestand).

## Verder lezen

- **[docs/gebruik.md](docs/gebruik.md)** -- de gebruiksaanwijzing, met wat hierboven niet paste:
  [`analyseer`, `dekking`, `toets` en `vergelijk`](docs/gebruik.md#de-commandos),
  [`toets` en de ontologie](docs/gebruik.md#toets-en-de-ontologie),
  [de nulmeting](docs/gebruik.md#de-nulmeting-tussen-de-eigen-bevindingen) en [de voortgangsbalk](docs/gebruik.md#voortgang).
- **[docs/architectuur.md](docs/architectuur.md)** -- het OroX-grafmodel, de afbakening, de meldingenstroom, de GeoPackage.
- **[data/checkregister-gwsw-nulmeting-v0_9.md](data/checkregister-gwsw-nulmeting-v0_9.md)** -- elke check met conditie, ernst, dimensie en herkomst.
- **[docs/dekkingsmatrix.md](docs/dekkingsmatrix.md)** -- welke check waar landt en wat hij leest.
- **[docs/json-schema.md](docs/json-schema.md)** -- het contract van `bevindingen.json`.
- **[docs/versionering.md](docs/versionering.md)** -- hoe een versie uitkomt.
- **[docs/beslislog.md](docs/beslislog.md)** -- de vastgelegde besluiten (de BO-nummers).

## Ontwikkelen

```bash
uv sync
uv run ruff check
uv run ruff format --check .
uv run mypy                                          # over src/nlriochecker
uv run pytest                                        # zware tests niet; `-m zwaar` wel
uv run --with pytest-cov pytest --cov=nlriochecker   # dekking, ondergrens 95%
```

Diezelfde vijf stappen draaien in CI op elke push naar `main` of `dev` (`.github/workflows/toets.yml`) en bij een
uitgave (`scripts/uitgave.py`). Een schone kloon mist de niet-getrackte delen van `data/`; de tests die daarop
leunen slaan dan over, en CI bewaakt dat er genoeg overblijven en dat elke overslag een verklaarde reden heeft. Die
runner-conditie speel je lokaal na met `uv run python scripts/runnerpoort.py`.

Het inlezen van de OroX-TTL zelf staat niet hier: de leeslaag (dataset, graaf, geometrie, ontologie, cache,
voortgang) is de package [gwsw-orox-helpers](https://github.com/mcolee/gwsw-orox-helpers) (MIT), die ook de
GWSW-ontologie meelevert; een nieuwe GWSW-versie is dus een release daar plus `uv lock` hier. De werkwijze en de
harde regels staan in [CLAUDE.md](CLAUDE.md), uitbrengen in [docs/versionering.md](docs/versionering.md).

## Bijdragen

Issues zijn welkom op de [issuetracker](https://github.com/mcolee/nlriochecker/issues): een fout, een check die iets
anders zou moeten meten, of een export waarop het misgaat. Overleg een pull request eerst in een issue -- de
domeinregels komen uit het GWSW en het checkregister, en dat gesprek gaat vóór de code.

## Licentie

Copyright © 2026 Martin Colee. Licensed under the EUPL.

Dit werk valt onder de [European Union Public Licence v1.2](LICENSE) (EUPL-1.2), een copyleft-licentie: verspreid je
een aangepaste versie, of geef je anderen toegang tot de wezenlijke functionaliteit ervan -- ook online, als dienst
-- dan gaat dat onder dezelfde licentie, met de broncode erbij. De EUPL is in 23 talen rechtsgeldig; de
[Nederlandse tekst](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12) telt even zwaar als de Engelse.
