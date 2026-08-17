# Bibliotheekreview 0.2.0

Doorlichting van de package tegen de gangbare maatstaven voor een Python-bibliotheek:
structuur, packaging, codekwaliteit, tests, beveiliging, documentatie, API en CI.
Uitgevoerd op 2026-08-17, op commit `0052fb6` (tak `dev`). Dit document beschrijft wat
er gevonden is en wat er meteen aan gedaan is; wat er niet aan gedaan is staat onderaan.

## Uitkomst

**Goed.** De inhoudelijke discipline was al sterk: 702 tests, 95 % dekking, een beslislog
die keuzes vastlegt, een uitgavescript met een echte poort. De zwakte zat niet in de code
maar in de automatisering eromheen -- er was geen CI, en de typehints waren nooit
gecontroleerd.

| Categorie | Voor | Na | Wat er veranderde |
| --- | --- | --- | --- |
| Structuur | 4/5 | 5/5 | `py.typed` toegevoegd |
| Packaging | 4/5 | 5/5 | ongebruikte `pyproj` eruit |
| Codekwaliteit | 3/5 | 5/5 | 55 mypy-fouten weg, mypy in de poort |
| Tests | 5/5 | 5/5 | ondergrens tegen stille overslagen |
| Beveiliging | 4/5 | 4/5 | meldingen onderbouwd in BO-6 |
| Documentatie | 4/5 | 5/5 | `CHANGELOG.md` |
| API-ontwerp | 4/5 | 4/5 | ongewijzigd |
| CI/CD | 1/5 | 4/5 | `.github/workflows/toets.yml` |

## Wat er goed stond

- **Dekking van 95 %** over 6159 regels, geen module onder 81 %. Gemeten met
  `uv run --with pytest-cov pytest --cov=nlriochecker`.
- **De uitgavepoort werkte al**: `scripts/uitgave.py` draaide ruff en pytest voor het
  bumpen en brak af op een vuile werkboom. Het probleem was niet dat er geen poort was,
  maar dat hij pas op het laatste moment dichtging.
- **De SQL was al correct verdedigd.** `studiegebied.py` verdubbelt aanhalingstekens in
  identifiers en parametriseert alle waarden, met een docstring die uitlegt waarom een
  laagnaam niet als parameter kan.
- **Repo-hygiene.** Van `data/` zijn alleen de twee checkregisters getrackt; het grootste
  getrackte bestand is 156 KB. `pip-audit` vindt geen kwetsbaarheden in 29 pakketten.

## Wat er gerepareerd is

**CI.** `.github/workflows/toets.yml` draait ruff, mypy en pytest op elke push naar `main`
of `dev` en op elke pull request naar `main`. Zie BO-5 voor de ondergrens op het aantal
geslaagde tests. Let op wat die grens wel en niet doet: een schone kloon zonder de
niet-getrackte delen van `data/` haalt hem ruim (675 van de 707), dus die situatie vangt
hij niet. Hij vangt het wegvallen van meer dan de bekende 32 overslagen.

**Mypy.** Van 55 fouten in dertien bestanden naar nul. Drieentwintig kwamen uit een enkele
oorzaak: `CheckContext.cached()` gaf `object` terug. De rest waren versmallingsgrenzen en
`set[str | None]`-verzamelingen die met `.discard(None)` werden opgeschoond in plaats van
meteen goed opgebouwd. Geen van de 55 bleek een echt defect -- maar dat was vooraf niet
vast te stellen.

Dat geen van de reparaties gedrag veranderde is niet uit de groene tests afgeleid -- die
bewijzen dat niet -- maar uit een vergelijking van de uitvoer voor en na, over de volledige
De Wolden-run met studiegebied en externe bronnen: `bevindingen.csv` en `bevindingen.md`
byte-identiek, en alle twaalf tabellen van de GeoPackage gelijk op
`layer_styles.update_time` na, dat de kloktijd draagt.

**`py.typed`.** De package leverde typehints maar publiceerde ze niet; een importerende
toepassing zag er niets van. Gecontroleerd aanwezig in de gebouwde wheel.

**`pyproj` verwijderd.** Werd nergens geimporteerd en komt zo nodig via geopandas en
rasterio mee. Tegelijk is `CLAUDE.md` gelijkgetrokken met de werkelijkheid: geopandas en
rasterio stonden niet in de lijst van toegestane afhankelijkheden terwijl `externedata.py`
ze gebruikt.

**`CHANGELOG.md`.** Keep a Changelog, gekoppeld aan `scripts/uitgave.py`: dat weigert een
uitgave met een lege `Unreleased`-sectie en verplaatst de inhoud bij het bumpen naar een
sectie met het nieuwe nummer en de datum. Getoetst in `tests/test_uitgave.py`.

## Wat er niet aan gedaan is

- **Mypy in strikte modus.** `disallow_untyped_defs` staat uit. Een paar hulpfuncties in
  `administratief.py` en `dataset.py` hebben nog ongetypeerde parameters; die annoteren
  trekt hun lichamen alsnog de controle in en is een eigen ronde waard.
- **Bandit draait niet in CI.** De elf meldingen zijn onderbouwd in BO-6 en blijven bewust
  onopgemerkt door een configuratie: wegdrukken zou de afweging onzichtbaar maken.
- **Dekking wordt niet bewaakt.** Er is geen `pytest-cov` in de dev-afhankelijkheden en
  geen ondergrens op het percentage. De 95 % is een meting, geen belofte.
- **`docs/ronde1-gpkg-en-rapport-verslag.md`** noemt 23 kolommen in de bevindingen-CSV; het
  zijn er inmiddels 26. Historisch verslag, dus bewust niet bijgewerkt.
- **Geen CONTRIBUTING of gedragscode.** Eenauteursproject; pas zinvol zodra er een tweede
  bijdrager is.
