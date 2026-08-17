# Wijzigingslog

Alle noemenswaardige wijzigingen aan dit project staan hier. De opzet volgt
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/), de nummering volgt
[semantische versionering](https://semver.org/lang/nl/) zoals
[docs/versionering.md](docs/versionering.md) die voor dit project uitlegt.

`scripts/uitgave.py` zet bij elke uitgave de sectie `Unreleased` om in een sectie met
het nieuwe nummer en de datum, en opent een lege nieuwe. Hij weigert uit te brengen als
`Unreleased` leeg is: een uitgave zonder wijzigingen is geen uitgave.

## [Unreleased]

### Toegevoegd

- Elk uitvoerbestand noemt de package en versie die het schreef: de Markdown-rapporten
  in een regel onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het
  veld `gereedschap` van `gwsw_run`.
- `py.typed`, zodat de typehints van deze package ook bij een importerende toepassing
  aankomen.
- CI (`.github/workflows/toets.yml`): ruff, mypy en pytest op elke push naar `main` of
  `dev` en op elke pull request naar `main`. De run valt als er nog meer tests overgeslagen
  worden dan de 32 die een schone kloon sowieso overslaat -- een fixturemap die niet
  meekomt leest anders als "alles groen".
- Mypy als poort, met een configuratie in `pyproject.toml`; de codebase is schoon.
- Dit wijzigingslog.

### Gewijzigd

- `CheckContext.cached()` is generiek geworden: bellers krijgen hun eigen structuur terug
  in plaats van `object`. Dat haalde in een keer 23 typefouten weg.
- `scripts/uitgave.py` toetst nu ook met mypy en onderhoudt dit wijzigingslog.
- Werkafspraak: werk staat op `dev`, `main` draagt alleen uitgebrachte versies.

### Gerepareerd

- NET-004 wees per run een andere streng aan. `nx.find_cycle` zonder `source` begint bij
  de eerste knoop in invoegvolgorde, en die volgt uit de hashseed; twee runs op dezelfde
  data toonden daardoor een verschil dat er niet was. De kringloop start nu bij de
  kleinste URI van het samenhangende deel.

### Verwijderd

- De afhankelijkheid `pyproj`; die werd nergens geimporteerd en komt zo nodig via
  geopandas en rasterio mee.

## [0.2.0] - 2026-08-17

Eerste uitgave onder een vast versienummer.

### Toegevoegd

- Afbakening met een studiegebied: de checks draaien op een kern plus contextschil,
  het rapport gaat over de kern.
- Een cache van de geparseerde dataset (`~/.cache/nlriochecker`), met een sleutel die de
  broncode van de lader meeneemt.
- GeoPackage-uitvoer met QGIS-stijlen in `layer_styles`, uit dezelfde meldingenstroom
  als de Markdown- en CSV-uitvoer.
- Checkregister v0.8 als contract, met een dekkingsmatrix die uit het register
  gegenereerd wordt.
- `scripts/uitgave.py` en een enkele versiewaarheid in `pyproject.toml`.

### Gewijzigd

- Hernoemd naar `nlriochecker`: package, commando en cachemap.
- Onder EUPL-1.2 gebracht.

[Unreleased]: https://github.com/mcolee/nlriochecker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mcolee/nlriochecker/releases/tag/v0.2.0
