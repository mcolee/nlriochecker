# Ontwerp: gwsw-orox-helpers

**Datum:** 2026-08-26
**Status:** goedgekeurd door de auteur (brainstormsessie)
**Scope van dit document:** de hele package (v0.1–v0.3); het eerste implementatieplan dekt alleen v0.1.

## Doel

De GWSW-OroX-leeslaag van nlriochecker wordt een zelfstandige, herbruikbare package:
lezen, schrijven en clippen van OroX/TTL-bestanden. Motieven: architectuur (checkcode
gescheiden van engine), hergebruik in toekomstige packages, en de leeslaag stabiel
krijgen zodat hij zelden nog wijzigt.

GitHub-onderzoek (2026-08-26): dit bestaat nog niet. `nens/hydxlib` doet het
Hydx-CSV-formaat (geen OroX), `HansvBug/GWSW-Exporter` schrijft OroX maar in Pascal,
StichtingRIONED publiceert ontologieën en SPARQL-queries maar geen bibliotheekcode,
en PyPI kent geen enkele `gwsw*`-package. Deze package is de eerste in zijn niche.

## Identiteit

| Aspect | Besluit |
|---|---|
| Naam | `gwsw-orox-helpers` (repo `mcolee/gwsw-orox-helpers`) |
| Licentie | MIT (nlriochecker blijft EUPL-1.2 en mag een MIT-dependency gebruiken) |
| Identifiers | Nederlands, 100% GWSW-conform — geen hernoemingen bij de verhuizing |
| Distributie | Nu git-dependency (`uv add git+...`); PyPI pas veel later, richting 1.0 |
| Versies | 0.x; de API mag breken tot 1.0 |
| Tooling | uv, src-layout, Python 3.12+, `py.typed`, CHANGELOG, uitgavescript |
| Kwaliteitspoort | Zelfde vijf stappen als nlriochecker: ruff lint, ruff format, mypy, pytest, dekkingsondergrens 95% — in GitHub Actions |
| Dependencies | pyoxigraph, rdflib, shapely (networkx blijft bij nlriochecker: alleen `afbakening.py` gebruikt het) |

## Wat verhuist (v0.1), wat blijft

**Verhuist één-op-één** (het leescluster is al gesloten; checks importeren alléén uit `dataset`):

| Module | Regels | Rol |
|---|---|---|
| `dataset.py` | 1575 | OroX-TTL → domeinmodel (`GwswDataset`, `Node`, `Conduit`, `Aspect`, `Inwinning`), klassenhiërarchie |
| `graaf.py` | 203 | `GraafIndex` (s→p→o en p→o→s) gevuld uit de pyoxigraph-stream |
| `geometry.py` | 122 | GML-literalen → shapely |
| `ontologie.py` | 143 | Facetbereiken/datatypes uit de GWSW-ontologie |
| `cache.py` | 262 | Pickle-cache + `LuieGraaf`; broncode-hash-sleutel werkt in de git-dep-fase door |
| `voortgang.py` | 59 | Voortgangsprotocol (callbacks) |
| errors (deels) | — | `DatasetError` mee; `StudyAreaError`/`PipelineError` blijven |

**Mee verhuist ook:**
- De GWSW-ontologie zelf: `Ontologie_GWSW_Totaal.ttl` (CC0) wordt **gebundeld** in de
  package. `load_dataset` gebruikt standaard de gebundelde ontologie; een pad-parameter
  overrulet. De package is daarmee ontology-aware out-of-the-box.
- De vocabulaire-index-generator (`maak_gwsw_index.py`) en de bijbehorende
  index-drifttests. De "leidende GWSW-versie"-regel verhuist van nlriochecker-CLAUDE.md
  naar de package-repo; een GWSW-upgrade wordt: package-release + `uv lock` in afnemers.
- De dataset-/graaf-/geometrie-/ontologie-/cachetests, met een **gesplitste
  fixturegenerator**: de package krijgt een eigen kleine generator + fixtures;
  nlriochecker houdt `maak_ttl_fixtures.py` met de defect-fixtures voor de checktests.

**Blijft in nlriochecker** (checkspecifiek):
- `afbakening.py` (kern/schil, leest `CheckConfig`), `studiegebied.py`
  (studiegebied-validatie; de kale GPKG/GeoJSON-polygonlezer gaat pas bij v0.3 mee
  als invoer voor de clipper).
- `VULWAARDE_KENMERKEN` en de cp850-keuze (zie API-grens).
- Alle checks, config, uitvoer, CLI.

## API-grens: generiek mechanisme, afnemersspecifieke waarden

De package kent géén nlriochecker-begrippen. Twee mechanismen worden geparametriseerd:

- **Vulwaarden**: `markeer_vulwaarden(dataset, kenmerken=...)` — het mechanisme
  (kenmerkwaarden als vulwaarde markeren) zit in de package, de lijst
  `VULWAARDE_KENMERKEN` blijft nlriochecker-kennis.
- **Encoding-fallback**: `fallback_encoding=`-parameter op `load_dataset`; de waarde
  `cp850` (De Wolden-leveranciersfeit) blijft bij de afnemer.

Het publieke oppervlak van v0.1 is exact wat nlriochecker vandaag importeert:
`GwswDataset` (met methoden), `Node`, `Conduit`, `Inwinning`, `load_dataset`,
`laad_met_cache`, `markeer_vulwaarden`, `parts_of`, `part_holders_of`,
`aspects_of`, `aspect_holders_of`, de constanten `GWSW`, `HAS_*`, en het
voortgangsprotocol.

## Routekaart

### v0.1 — de verhuizing (dit project)

Pure refactor met de bestaande tests als vangnet; geen gedragswijziging.

1. Repo opzetten (tooling + CI zoals hierboven).
2. Leescluster, ontologie, indexgenerator, tests en gesplitste fixtures over.
3. nlriochecker omzetten: git-dependency + **harde importomzetting** (~20 bestanden,
   mechanisch) — geen re-export-shim.
4. Acceptatie: beide CI's groen; nlriochecker-gedrag ongewijzigd (volledige poort,
   inclusief de drifttests van issue #64).

### v0.2 — write (geparkeerd)

Twee lagen, nadrukkelijk níét serialiseren vanuit het domeinmodel:
1. **Triple-getrouwe serialisatie** via pyoxigraph voor alles wat heel blijft
   (bit-getrouw kopiëren = generiek en onderhoudsarm).
2. **GML-schrijver** (shapely → GML-literal, met Z en dezelfde srsName) — alleen
   nodig voor door de clipper gewijzigde geometrieën.

### v0.3 — clip (geparkeerd)

"QGIS-clip voor OroX": GIS-bestand met polygonen (bv. gemeentegrenzen) erin,
per polygoon een geknipt OroX-bestand eruit.

- **Écht doorknippen**: geometrieën die de grens kruisen worden gesneden; elk
  bestand krijgt zijn deel. Het resultaat is een afgeleid product, niet de bronwaarheid.
- **Identiteit**: beide helften houden dezelfde URI (traceerbaar naar de bron).
- **Attributen**: onaangeroerd, ook als ze niet meer kloppen (lengte, BOB's);
  herrekenen is een latere expliciete optie.
- **Verwijzingen over de grens** (`hasConnection` e.d.): triple weg, maar
  gerapporteerd.
- **Kniprapport** (verplichte uitvoer): per object doorgeknipt ja/nee,
  oorspronkelijke/nieuwe lengte, verwijderde verbindingen, grensgevallen.
- **Geometrieloze objecten** volgen hun drager (aspect/onderdeel mee met het
  object); **containers** (stelsels, typeringen) komen in elk bestand waar ze
  leden hebben, met alleen de member-triples naar objecten in dát bestand.
- **`--overlap`-optie**: grensobjecten volledig in beide bestanden in plaats van
  geknipt.
- **CLI** `orox-clip` op argparse (stdlib; geen click-dependency voor één commando).
- Acceptatie van deze fase (niet van v0.1): de SWO-knip — de gecombineerde
  DWD+HGV-export knippen op de gemeentegrens; de twee bestanden zijn inleesbaar
  voor nlriochecker (integratietest, marker `zwaar`) en komen door de
  RIONED-validator met alleen de voorspelde klachten (handmatige eindcheck).

## Gevolgen voor nlriochecker

- `data/gwsw_ontologieen/` en `data/gwsw-vocabulaire-index.json` verdwijnen hier
  zodra de package ze draagt; de CLAUDE.md-regels over GWSW-versie en index
  verhuizen mee (v0.1).
- `--ontologie` wordt optioneel: standaard de gebundelde ontologie, een pad
  overrulet, `--geen-ontologie` blijft de bewuste ontsnappingsvlag met het
  voorbehoud in de rapportkop (issue #33 blijft daarmee gehonoreerd).
- De cachesleutel-mechaniek (broncode-hash) blijft werken; bij een package-update
  verandert de hash en vervalt de cache vanzelf.
