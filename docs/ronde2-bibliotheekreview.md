# Bibliotheekreview na ronde 2

Uitgevoerd op de staat van `dev` na de rapportage per studiegebied-feature, met de
checklist uit `python-library-complete:reviewing-python-libraries`. Dit document legt de
uitkomst vast; het is geen nieuwe eis, maar de meting waar de volgende ronde tegen af
kan zetten.

## Beoordeling: goed

| Onderdeel | Oordeel | Onderbouwing |
|---|---|---|
| Structuur | goed | src-layout, `py.typed`, geen losse modules buiten de package |
| Verpakking | goed | `pyproject.toml` met hatchling, geen `setup.py`, ondergrenzen in plaats van vastgepinde versies |
| Code | goed | typehints overal, `uv run mypy` schoon over 45 bestanden, Nederlandse docstrings |
| Tests | goed | 835 geslaagd, 6 zwaar overgeslagen; regeldekking 95% over de package |
| Beveiliging | ongewijzigd | bandit meldt elf punten, exact dezelfde als voor deze ronde; zie BO-6 |
| Documentatie | goed | README, `docs/json-schema.md`, beslislog, wijzigingslog alle bijgewerkt |
| API | goed | uitbreidingen zijn additief; de breuken staan met naam in het wijzigingslog |
| CI/CD | goed | ruff, mypy en pytest op elke push; ondergrens aan het aantal geslaagde tests |

## Dekking van de nieuwe code

| Module | Regels | Gemist | Dekking |
|---|---:|---:|---:|
| `toetsloop.py` | 36 | 0 | 100% |
| `uitvoer/__init__.py` | 61 | 0 | 100% |
| `uitvoer/synthese.py` | 105 | 2 | 98% |
| `studiegebied.py` | 253 | 14 | 94% |
| `afbakening.py` | 135 | 5 | 96% |

De gemiste regels in `studiegebied.py` zijn sqlite-foutpaden (een onleesbaar bestand, een
laag zonder geometriekolom) en de blob-varianten die de fixtures niet schrijven.

`pytest-cov` staat bewust niet in de dev-groep: de meting is met
`uvx --with pytest-cov --with-editable . pytest --cov=nlriochecker` gedaan, zodat er geen
afhankelijkheid bijkomt voor iets wat we een paar keer per ronde doen.

## Beveiliging

Bandit meldt elf punten, precies dezelfde als op de basis van deze ronde (`1dbd9e7`):
acht keer B608 (SQL uit een f-string voor tabel- en kolomnamen, die SQLite niet als
parameter accepteert) en drie keer pickle voor de datasetcache. De onderbouwing staat in
BO-6 van de beslislog; deze ronde voegt geen nieuw aanvalsvlak toe. De enige nieuwe
f-string-query (`select * from "<laag>"` in `_lees_geopackage`) vervangt een bestaande en
loopt door hetzelfde `_escape()`.

## Schaalmeting

`test_schaal_tachtig_buurten` op de volledige De Wolden-export: 80 gebieden in 2,7 s
(TOP-001 als enige check), tegen ruim twee en een halve minuut voor het laden van de
dataset. Zie BO-14 voor wat dat wel en niet zegt.

## Aanbevelingen

1. **Dekking van `externedata.py` (81%)** is de laagste van de package; dat is de module
   die ronde 3 raakt met de dekkingsvalidatie van de externe bronnen. Neem de ontbrekende
   paden daar mee.
2. **`cli.py` telt 800 regels.** Ronde 2 heeft de zware orkestratie eruit gehaald naar
   `toetsloop.py`; de rest is optiedefinities en schermuitvoer. Als ronde 3 er weer
   opties bij zet, is de schermuitvoer de volgende kandidaat om te verhuizen.
3. **`pip-audit`** is deze ronde niet opnieuw gedraaid: er is geen afhankelijkheid
   bijgekomen. Draai hem weer bij de volgende uitgave.
