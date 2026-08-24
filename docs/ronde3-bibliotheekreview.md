# Bibliotheekreview na ronde 3

Uitgevoerd op de staat van `dev` na de EXT-lagen en de dekkingspoort, met de checklist
uit `python-library-complete:reviewing-python-libraries`. Zelfde opzet als
[het verslag na ronde 2](ronde2-bibliotheekreview.md), zodat de cijfers vergelijkbaar
zijn.

## Beoordeling: goed

| Onderdeel | Oordeel | Onderbouwing |
|---|---|---|
| Structuur | goed | src-layout, `py.typed`; de nieuwe `checks/treffers.py` is een eigen module met een eigen verantwoordelijkheid |
| Verpakking | goed | `pyproject.toml` met hatchling, geen nieuwe afhankelijkheid deze ronde |
| Code | goed | typehints overal, `uv run mypy` schoon over 46 bestanden |
| Tests | goed | 873 geslaagd, 7 zwaar overgeslagen; regeldekking 96% (was 95%) |
| Beveiliging | ongewijzigd van aard | bandit meldt twaalf punten, een meer dan na ronde 2; het extra punt is dezelfde soort als de bestaande |
| Documentatie | goed | README, `docs/json-schema.md`, beslislog (BO-17 t/m BO-19), wijzigingslog bijgewerkt |
| API | goed | uitbreidingen additief, op één na; alle wijzigingen staan met naam in het wijzigingslog |
| CI/CD | goed | ruff, mypy en pytest op elke push, met een ondergrens aan het aantal geslaagde tests |

## Dekking van de nieuwe en geraakte code

| Module | Regels | Gemist | Dekking |
|---|---:|---:|---:|
| `checks/treffers.py` | 43 | 0 | 100% |
| `uitvoer/gpkg.py` | 307 | 7 | 98% |
| `checks/extern.py` | 444 | 19 | 96% |
| `checkconfig.py` | 182 | 5 | 97% |
| `externedata.py` | 212 | 29 | 86% |
| **Totaal** | 6828 | 298 | **96%** |

`externedata.py` stond na ronde 2 op 81% en was toen de laagste van de package; de
dekkingspoort heeft dat naar 86% getild. Wat er nog niet gedekt is, zijn de leespaden
voor onleesbare of afwijkend geprojecteerde bronbestanden.

## Beveiliging

Bandit meldt twaalf punten: negen keer B608 (SQL uit een f-string voor tabel- en
kolomnamen, die SQLite niet als parameter accepteert) en drie keer pickle voor de
datasetcache. Dat is er één meer dan na ronde 2, en het is de `insert` van de nieuwe
trefferlagen in `uitvoer/gpkg.py`: dezelfde vorm als de zes die er al stonden -- de
laagnaam is een constante uit `FEATURELAGEN`, alle waarden gaan als parameter mee. De
onderbouwing staat in BO-6 van de beslislog; die is met het nieuwe aantal bijgewerkt.

## Aanbevelingen

1. **De testsuite is trager geworden**: van circa 40 s na ronde 2 naar 50-130 s nu,
   afhankelijk van de belasting van de machine. De nieuwe fixtures schrijven
   GeoPackages met geopandas (pyogrio en GDAL), en dat is per aanroep merkbaar. Als het
   verder oploopt, is een sessiebrede fixture voor de miniatuurbronnen de eerste stap;
   nu is het hinderlijk maar niet blokkerend.
2. **`checks/extern.py` telt 900 regels** en draagt zowel de EXT- als de AHN-checks.
   Splitsen langs die grens is de logische volgende stap zodra er weer aan gewerkt
   wordt; deze ronde was er geen aanleiding om het te doen.
3. **`pip-audit`** is niet opnieuw gedraaid: er is geen afhankelijkheid bijgekomen.
   Draai hem bij de volgende uitgave.
