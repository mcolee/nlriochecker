# Versionering

Het versienummer staat op één plek: `version` in `pyproject.toml`. Alles daaromheen
volgt daaruit.

- `nlriochecker.__version__` leest het via `importlib.metadata`, dus uit de
  geïnstalleerde metadata. Er staat geen tweede nummer in de broncode dat kan gaan
  drijven.
- `nlriochecker --version` toont hetzelfde nummer; `cli.py` geeft `__version__` door
  aan `click.version_option`.
- De git-tag heet `vX.Y.Z` en wordt gezet ná de commit die het nummer ophoogt. De tag
  volgt het nummer, nooit andersom.
- `tests/test_versie.py` bewaakt dat `__version__` en `pyproject.toml` gelijk zijn. Die
  test valt om als de omgeving verouderd is (`uv sync` vergeten) of als iemand het
  nummer alsnog ergens een tweede keer opschrijft.

## Een versie uitbrengen

```bash
uv run python scripts/uitgave.py patch|minor|major
```

Het script doorloopt:

1. eisen dat je op `main` staat, met een schone werkboom, niet achterlopend op
   `origin/main` (is de remote onbereikbaar, dan slaat die laatste controle over), en
   dat `CHANGELOG.md` onder `## [Unreleased]` iets te melden heeft;
2. het volgende nummer berekenen met `uv version --bump --dry-run`, dat niets schrijft,
   en controleren dat de bijbehorende tag nog niet bestaat;
3. pas dan echt bumpen met `uv version --bump`, wat `pyproject.toml` en `uv.lock` raakt;
4. `ruff check .`, `ruff format --check .` en `pytest -q` draaien;
5. committen als `Versie X.Y.Z` -- alleen `pyproject.toml` en `uv.lock` bij naam, nooit
   wat de toets toevallig in de werkboom achterliet;
6. taggen als `vX.Y.Z`.

De tagcontrole staat bewust voor de bump: een tag die al bestaat is te weten zonder ook
maar iets te schrijven.

Valt er onderweg iets om, dan draait het script terug wat het al gedaan had: eerst de
commit (`git reset --hard HEAD~1`, maar alleen als de bovenste commit ook echt de
zojuist gemaakte `Versie X.Y.Z` is), dan de bump. Een mislukte uitgave laat dus geen
opgehoogd nummer zonder tag achter, en geen commit zonder tag.

Mislukt het terugdraaien zelf ook, dan zegt het script dat met zoveel woorden en laat
het de oorspronkelijke fout staan; het ruimt dan niets half op. In dat geval controleer
je `pyproject.toml`, `uv.lock` en `git log` met de hand.

Pushen doet het script niet:

```bash
git push --follow-tags
```

## Wat betekenen de cijfers

De package staat in `0.x` en blijft daar zolang fase 4 (EXT) loopt en er checks uit het
checkregister ontbreken.

| Deel  | Wanneer |
|-------|---------|
| patch | Reparaties, en nieuwe checks binnen een blok dat er al is. |
| minor | Een afgerond blok of fase. Ook: een breuk in de CLI, de configuratie (`checks.toml`, projectconfig) of het uitvoerformaat. |
| major | Pas als het checkregister volledig gedekt is. Daarna: elke breuk in de publieke API. |

Check-ID's uit het checkregister zijn stabiel en staan los van dit nummer; een vervallen
ID wordt nooit hergebruikt, ongeacht de versie.
