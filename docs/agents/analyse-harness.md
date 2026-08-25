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
- **Welke objecten "vrijverval", "mechanisch", "put" of "lozingspunt" zijn, staat in
  `checks/selectie.py`** (één rolfunctie per rol, klassen uit `[klassen]` in de config). Niet
  opnieuw uit de ontologie afleiden: dat kostte 4 calls en gaf een andere grens dan de checks
  hanteren.
- **Er is geen `sqlite3`-CLI** op deze machine. Een GeoPackage lees je met
  `python3 -c 'import sqlite3'` of `ogrinfo -q -sql`.
- **Een scratch-script tegen De Wolden overschrijdt de 2-minuten-timeout van een
  voorgrond-Bash.** Start het vanaf de eerste poging met `run_in_background`; het meldt zich.
  De `nohup` + `until … sleep`-omweg kostte in één sessie 16 calls en een hangend proces.
- **Laad zwaar spul één keer en pickle het in het scratchpad** (`raw.pkl`, `_alle.pkl`): een
  GeoPackage plus de BGT-lagen (97k waterdelen) per vraag opnieuw inlezen kostte een sessie
  14 herlaadbeurten van elk tientallen seconden.

## Bestaande runs en meetscripts

- `uitvoer/` (git-ignored) bevat volledige `toets`-runs: `volledig_24082026/` is de
  0.3.0-baseline (162.046 meldingen, met `steekproef_checks.gpkg`) en `issue58/` t/m
  `issue63/` zijn de nametingen per issue — `issue62/` is de recentste. **Tel eerst daarop**
  (`bevindingen.json`) voordat je een nieuwe run van ~6 minuten start; noem in je verslag
  welke run je gebruikte, want de baseline dateert van vóór #60–#63.
- **Een meetscript dat een getal in een issue of BO onderbouwt, bewaar je** — in het
  scratchpad volstaat niet. Zet het onder `scripts/` of naast het verslag in `docs/`, met de
  commit-hash van de dataset-lader erin. Op 24-08 bleef een 234-telling alleen als inline
  heredoc bestaan; de volgende sessie kwam op 319 en het verschil is nooit herleid (BO-43).

## Verrassende, maar correcte aantallen

Onwaarschijnlijke uitkomsten eerst wantrouwen (zie de hoofdregel in `CLAUDE.md`), maar deze
zijn geen bug:

- **ATTR-001** toetst de vrijverval-subset (~17603 strengen), niet alle conduits (~23440).
- **HGT-012** leest `HoogtePut`; De Wolden levert daar **0** instanties.
- **Baseline ná #60–#63 (0.3.0 + Unreleased, 25-08):** HGT-001 5811 → **2847** en HGT-002
  **2132** (drempel 10 cm inclusief, BO-44); ATTR-018 **9274** (9063 putten, 211 strengen);
  TOP-022 **224** en TOP-023 **37** op 1054 T-stukken; ADM-010/011 **54** loze leidingen in 33
  ketens (38 F, 16 W); EXT-001 **455**, EXT-003 **319** doorkruisingen op 281 strengen,
  EXT-007 **71**; `SIG-hulpstukkoppeling` 3024 herstelde leidingeinden naar 1122 hulpstukken.
  Bron: `CHANGELOG.md` onder Unreleased en de BO's 43–47; een run die hiervan afwijkt vraagt om
  een verklaring, niet om een nieuwe waarheid.
- **NET-001/NET-002** telden op 24-08 9062 en 3054 bevindingen, vóór de laderfix van #60
  (3024 losse strengeinden → 0); die twee cijfers zijn verouderd, meet ze opnieuw voor je ze
  citeert.
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
- **Het volgende BO-nummer**: `grep -n '^### BO-' docs/beslislog.md | tail -1`; een nieuw BO
  komt chronologisch onderaan. Drie sessies zochten dit in 12 calls bij elkaar.
- **De huisstijl van een issue** staat in `docs/agents/issue-tracker.md`; lees die in plaats
  van een bestaande issue-body te reverse-engineeren.
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
