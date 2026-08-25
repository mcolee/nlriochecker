# Analyse-harness: vaste feiten voor een De Wolden-analyse

Bedoeld voor wie een telling, een before/after of een scratch-script tegen de OroX-dataset
schrijft. Elke sessie ontdekte dezelfde dingen opnieuw, meestal achter een ~0,5-minuut/<2-GB
De Wolden-load, zodat een verkeerde gok duur is. Ken deze feiten vooraf; verifieer bij twijfel,
want de code kan schuiven.

## Dataset-, config- en registry-API

Voor een scratch-script tegen de echte data — dit recept, verbatim, zodat je de
signaturen niet elke sessie opnieuw hoeft op te zoeken:

```python
from pathlib import Path

from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks

# Cachetreffer = geen parse: seconden i.p.v. de koude ~0,5 min. De cache staat in
# standaard_cachemap() (~/.cache/nlriochecker); laad_met_cache geeft (dataset, cache).
dataset, _ = laad_met_cache(
    Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
    [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")],
)
config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
context = CheckContext(dataset=dataset, config=config)
```

- `dataset.nodes` en `dataset.conduits` zijn **dicts** (`dict[str, Node]` /
  `dict[str, Conduit]`) → itereer met `.values()`, niet als lijst.
- Geometrie zit op **`Node.point`** (`shapely.Point | None`) en **`Conduit.line`**
  (`LineString | None`); beide kunnen `None` zijn.
- Config laden met **`load_check_config()`**, niet `CheckConfig()`; zonder pad krijg je
  de defaults, met `configs/dewoldenhoogeveen.toml` de projectwaarden.
- De checks komen uit **`REGISTRY`**; kijk hoe bestaande code eroverheen loopt vóór je de
  iteratievorm gokt.
- `bevindingen.csv` is **`;`-gescheiden** (zie `uitvoer/herkomst.py`), niet komma.
- Nieuwe `src/`-bestanden moeten `git add` krijgen vóór de tracked-sweep-test slaagt.

## Verrassende, maar correcte aantallen

Onwaarschijnlijke uitkomsten eerst wantrouwen (zie de hoofdregel in `CLAUDE.md`), maar deze
zijn geen bug:

- **ATTR-001** toetst de vrijverval-subset (~17603 strengen), niet alle conduits (~23440).
- **HGT-012** leest `HoogtePut`; De Wolden levert daar **0** instanties.
- Een before/after-telling moet door de **echte pijplijn** (`markeer_vulwaarden` vóór de
  checks). Een losstaand snel script mist die markering en geeft afwijkende cijfers die later
  niet met de geleverde getallen kloppen.

## Gegenereerde bestanden — nooit met de hand bewerken

Bewerk de generator en regenereer; anders valt de bijbehorende drifttest:

| Bestand | Generator |
|---|---|
| `tests/fixtures/ttl/*.ttl` | `scripts/maak_ttl_fixtures.py` |
| `docs/dekkingsmatrix.md` | `scripts/dekkingsmatrix.py` |
| `data/gwsw-vocabulaire-index.json` | `scripts/maak_gwsw_index.py` |

Check dit **vóór** je een fixture aanraakt: met de hand bewerken lijkt lokaal te werken maar
is een valse start — de drifttest en de review sturen je terug naar de generator (kostte in
twee sessies ~15 calls herwerk). Een nieuwe fixture: declareer lokale subklassen inline (de
PRELUDE is over ~140 fixtures gedeeld), draai `uv run python scripts/maak_ttl_fixtures.py`,
en diff.

## Drempelrecept: vijf gekoppelde plekken

Eén drempel wijzigen raakt vijf plekken, plus een generator en een drifttest die het geheel
bewaakt:

1. de default in `checkconfig.py`;
2. `src/nlriochecker/checks.toml` (staat **niet** in de repo-root);
3. `configs/dewoldenhoogeveen.toml` (de projectwaarde);
4. de TTL-fixture (via `scripts/maak_ttl_fixtures.py`, niet met de hand);
5. een regel onder `## [Unreleased]` in `CHANGELOG.md`.

Een config-drifttest faalt als deze uit elkaar lopen.

## Valkuilen die elke sessie opnieuw kostten

Mechanisch, geen domeinlogica — maar telkens teruggevonden door te zoeken:

- **Een nieuwe check raakt meer dan het drempelrecept.** Naast de vijf plekken hierboven:
  de check-module zelf (bv. `attributen.py`), de tests, `test_gwsw_vocabulaire.py` (bewaakt
  materiaal- en aspectnamen), een regel in het checkregister, `scripts/dekkingsmatrix.py`
  regenereren, een BO in `docs/beslislog.md`, en `CHANGELOG.md`.
- **Check-ID's in issue-teksten zijn vaak al bezet.** Grep het eerste vrije nummer uit de
  check-module (`id = "ATTR-0` enz.) in plaats van de aanbeveling in het issue te vertrouwen;
  ATTR-014/015/016 waren telkens al vergeven toen het issue ze voorstelde.
- **CI kan "N geslaagd" tonen én toch exit 1 geven.** `.github/workflows/toets.yml` zet
  `NLRIOCHECKER_STRIKTE_OVERSLAG`: elke test-overslag waarvan de reden geen `data/` en geen
  `BO-` noemt is daar een harde fout (BO-48). Een nieuwe test die echte data laadt hoort dus
  "… staat niet in data/" in zijn skip-reden te dragen; een bewuste uitzondering noemt haar
  BO-nummer. Speel de runner-conditie lokaal na met `uv run python scripts/runnerpoort.py`
  vóór je pusht: alleen de getrackte `data/`-bestanden, geen PyQGIS, dezelfde grenzen.
- **`gh`-schrijfacties falen soms tijdelijk** (`gh pr create` → GraphQL-permissie/404)
  terwijl `git push` en reads gewoon werken; opnieuw proberen slaagt meestal. Niet je
  token-scope of account onderzoeken — dat is dood werk.
- **Byte-/inhoudsvergelijking van `toets`-gpkg tussen runs:** de `update_time`-kolom in
  `layer_styles` is een tijdstempel die per schrijfactie verandert; normaliseer hem, anders
  faalt een verder identieke vergelijking.
