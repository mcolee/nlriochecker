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

`analyseer`, `dekking` en `vergelijk` schrijven Markdown en CSV; `toets` schrijft
daarnaast een GeoPackage met de bevindingen op locatie (`--geen-gpkg` slaat die over).
`--output` staat standaard op `uitvoer/`. Invoerbestanden worden nooit overschreven.

Elk geschreven bestand noemt waarmee het gemaakt is: de Markdown-rapporten in een regel
onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het veld
`gereedschap` van de tabel `gwsw_run`. Een rapport is daarmee altijd te herleiden tot
de versie die het opleverde.

## Ontwikkelen

```bash
uv sync
uv run pytest          # zware tests draaien niet mee; `-m zwaar` wel
uv run ruff check
```

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
