# Analyse-harness: vaste feiten voor een De Wolden-analyse

Bedoeld voor wie een telling, een before/after of een scratch-script tegen de OroX-dataset
schrijft. Elke sessie ontdekte dezelfde dingen opnieuw, meestal achter een ~1,5-minuut/3-GB
De Wolden-load, zodat een verkeerde gok duur is. Ken deze feiten vooraf; verifieer bij twijfel,
want de code kan schuiven.

## Dataset-, config- en registry-API

Voor een scratch-script tegen de echte data:

- Laad via de **cache**, niet vers, als het even kan (scheelt de volledige laadtijd).
- `dataset.conduits` is een **dict** → itereer met `.values()`, niet als lijst.
- Config laden met **`load_check_config()`**, niet `CheckConfig()`.
- De checks komen uit **`REGISTRY`**; kijk hoe bestaande code eroverheen loopt vóór je de
  iteratievorm gokt.
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

## Drempelrecept: vijf gekoppelde plekken

Eén drempel wijzigen raakt vijf plekken, plus een generator en een drifttest die het geheel
bewaakt:

1. de default in `checkconfig.py`;
2. `src/nlriochecker/checks.toml` (staat **niet** in de repo-root);
3. `configs/dewoldenhoogeveen.toml` (de projectwaarde);
4. de TTL-fixture (via `scripts/maak_ttl_fixtures.py`, niet met de hand);
5. een regel onder `## [Unreleased]` in `CHANGELOG.md`.

Een config-drifttest faalt als deze uit elkaar lopen.
