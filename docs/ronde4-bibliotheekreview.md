# Bibliotheekreview na ronde 4

Uitgevoerd op de staat van `dev` na de nulmeting in de meldingenstroom, de twee
objectlagen, de GWSW-symbologie met hoverpopup en het herbouwde rapport (issues #12 t/m
#16), met de checklist uit `python-library-complete:reviewing-python-libraries`. Zelfde
opzet als [het verslag na ronde 3](ronde3-bibliotheekreview.md), zodat de cijfers
vergelijkbaar zijn.

## Beoordeling: goed

| Onderdeel | Oordeel | Onderbouwing |
|---|---|---|
| Structuur | goed | src-layout, `py.typed`; vier nieuwe modules met elk een eigen verantwoordelijkheid (`nulbevinding.py`, `uitvoer/objectkaart.py`, `uitvoer/omvang.py`, `uitvoer/samenvatting.py`, `uitvoer/stijlen/symbolen.py`) |
| Verpakking | goed | `pyproject.toml` met hatchling; geen nieuwe afhankelijkheid deze ronde, ondanks vier issues |
| Code | goed | typehints overal, `uv run mypy` schoon over 53 bestanden (was 46) |
| Tests | goed | 1152 geslaagd (was 873), 7 zwaar overgeslagen; regeldekking 96%, gelijk aan ronde 3 terwijl de codebase met ruim 750 regels groeide |
| Beveiliging | licht verbeterd van aard | bandit meldt elf punten (was twaalf): 2 laag, 9 middel, 0 hoog. Alle middelpunten zijn dezelfde soort als voorheen -- SQL die met f-strings wordt samengesteld in `uitvoer/gpkg.py`, waar de variabele delen laagnamen en kolomnamen uit constanten van deze package zijn en geen invoer van een gebruiker |
| Documentatie | goed | README, `docs/json-schema.md`, beslislog (BO-28 t/m BO-31), wijzigingslog en `CLAUDE.md` bijgewerkt; twee ontwerpdocumenten en twee plannen onder `docs/superpowers/` |
| API | goed | `Melding` kreeg het veld `cfk` en `schema_versie` ging naar `1.1` -- een achterwaarts verenigbare toevoeging, beschreven in het contract; `CheckRun` kreeg `nulbevindingen` en `nulbevindingen_weggelaten`, `Analyseset` kreeg `buffer`, alle drie met een standaardwaarde |
| CI/CD | goed | ruff, mypy en pytest op elke push, met een ondergrens aan het aantal geslaagde tests |

## Dekking van de nieuwe en geraakte code

| Module | Regels | Gemist | Dekking |
|---|---:|---:|---:|
| `uitvoer/objectkaart.py` | 71 | 0 | 100% |
| `uitvoer/omvang.py` | 44 | 0 | 100% |
| `uitvoer/samenvatting.py` | 49 | 0 | 100% |
| `uitvoer/stijlen/symbolen.py` | 85 | 1 | 99% |
| `uitvoer/gpkg.py` | 305 | 4 | 99% |
| `uitvoer/bevindingen.py` | 254 | 4 | 98% |
| `toetsrun.py` | 166 | 0 | 100% |
| `toetsloop.py` | 38 | 0 | 100% |
| **Totaal** | 7590 | 276 | **96%** |

Gemeten met `uv run --with pytest-cov pytest --cov=nlriochecker`; `pytest-cov` staat
bewust niet in de projectafhankelijkheden, net als bij de vorige rondes.

## Wat opviel

**De verificatie leunt niet meer alleen op tekstvergelijking.** PyQGIS staat op deze
machine, en `tests/test_uitvoer_qgis.py` laadt de geschreven GeoPackage nu echt: hij
controleert dat elke stijl uit `layer_styles` komt, dat elke expressie naar een bestaande
kolom verwijst, dat QGIS de markervormen terugcodeert zoals de symbolentabel ze bedoelde,
en dat de maptipexpressie op een echte feature HTML oplevert. Daarmee is de handmatige
QGIS-controle uit issues #14 en #15 vervangen door iets dat in elke run meedraait.

**Twee bestanden groeien uit hun jasje.** `uitvoer/gpkg.py` staat op 1.155 regels en
`uitvoer/bevindingen.py` op 827. Beide doen nog een ding -- een GeoPackage schrijven,
respectievelijk het bevindingenrapport samenstellen -- maar de Markdown-opbouw in
`bevindingen.py` is inmiddels een eigen onderwerp naast het schrijven van de CSV en de
JSON. Een splitsing is de volgende keer dat er aan gewerkt wordt de moeite waard; nu
opsplitsen zonder aanleiding zou een grote diff opleveren zonder dat er iets verandert.

**De GeoPackage groeit met de popup.** `popup_html` kost 1.085 bytes per object, wat op
de volledige De Wolden-export circa 51 MB is. Dat is gemeten en vastgelegd in BO-29; de
klassenamen zijn al ingekort (dat scheelde 15%), en wat overblijft is de boodschaptekst
zelf.

**Twee codereviewrondes leverden vier echte defecten op**, alle vier van dezelfde soort:
een tweede bron van meldingen toevoegen zonder de plekken bij te werken die ze
samenvatten. `synthese.rode_draad` las de SHACL-vormen als onafhankelijke checks,
`gwsw_run` telde fouten uit een andere bron dan `meldingen_totaal`, de opdrachtregel
noemde alleen de eigen checks, en `status` liet grijs een gebrek verbergen. Ze staan met
naam in BO-28 en BO-29. Dat is een patroon om te onthouden: `bouw_meldingen` heeft meer
afnemers dan de vier schrijvers.
