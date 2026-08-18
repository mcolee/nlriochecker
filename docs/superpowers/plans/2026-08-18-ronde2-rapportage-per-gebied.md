# Ronde 2: rapportage per studiegebied-feature — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `toets` rapporteert per feature van het studiegebiedbestand — eigen submap
met alle vier uitvoervormen — plus één totaalsynthese, met strenge voorafgaande
validatie van dat bestand en zonder de dataset meer dan één keer te laden.

**Architecture:** Het studiegebied wordt een container `Studiegebieden` met één
`StudyArea` per feature. Een nieuwe module `toetsloop.py` laadt alles één keer, bouwt
één gedeelde ruimtelijke index en componentenstructuur, en draait de checks per
gebied via de bestaande `bouw_analyseset`. De schrijflaag krijgt één extra ingang die
per gebied de bestaande `schrijf_uitvoer` aanroept en er een totaalsynthese naast zet.

**Tech Stack:** Python 3.12, click, pydantic, shapely (incl. `STRtree`), networkx,
pandas, stdlib `sqlite3`; pytest; uv; ruff + mypy.

**Spec:** `docs/superpowers/specs/2026-08-18-ronde2-rapportage-per-gebied-design.md`

## Global Constraints

- Werk op branch `dev`. Versienummer nergens ophogen.
- Geen nieuwe afhankelijkheden. GeoPackage lezen blijft stdlib `sqlite3` + shapely.
- Geen hardcoded drempels of lijsten; RD-grenzen komen uit `config.drempels.rd_*`.
- Nederlandse docstrings, Engelse identifiers, type hints overal.
- Enige schrijvers zijn `schrijf_markdown`, `schrijf_csv`, `schrijf_json`
  (`uitvoer/herkomst.py`) plus `schrijf_geopackage`; `tests/test_uitvoer_herkomst.py`
  bewaakt dat er geen tweede bijkomt. Roep nooit zelf `to_csv`, `write_text` of
  `json.dump` aan in `src/`.
- Equivalentie-eis: de meldingen per gebied moeten identiek zijn aan een losse run met
  alleen dat gebied. Elke optimalisatie moet dat aantoonbaar laten staan.
- Voortgang is weergave: geen check leest er state uit.
- Na elke taak: `uv run ruff check`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest` — alles groen, en committen.
- Elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in
  `CHANGELOG.md` (gebeurt in taak 10, in één keer).

---

## Bestandsindeling

| Bestand | Verantwoordelijkheid | Actie |
|---|---|---|
| `src/nlriochecker/studiegebied.py` | Lezen en valideren van het studiegebiedbestand; `StudyArea`, `Studiegebieden`, `mapnaam` | uitbreiden |
| `src/nlriochecker/afbakening.py` | Analyseset per gebied; gedeelde index en componenten | uitbreiden |
| `src/nlriochecker/checks/base.py` | Gedeelde volledige-export-context; faselabel van `run_checks` | uitbreiden |
| `src/nlriochecker/toetsloop.py` | De loop over nul, één of veel gebieden | nieuw |
| `src/nlriochecker/uitvoer/herkomst.py` | `schrijf_json` met `gebied`/`gebieden` | uitbreiden |
| `src/nlriochecker/uitvoer/synthese.py` | `rode_draad` (bestaand) + `totaalsynthese` | uitbreiden |
| `src/nlriochecker/uitvoer/__init__.py` | `schrijf_uitvoer` (bestaand) + `schrijf_uitvoer_gebieden` | uitbreiden |
| `src/nlriochecker/cli.py` | `--gebied`, wiring, schermuitvoer | uitbreiden |
| `scripts/maak_gis_fixtures.py` | Fixtures voor twee buurten, losse buurten, 80 buurten | uitbreiden |
| `tests/fixtures/gis/*.geojson` | `crs`-member EPSG:28992 | wijzigen |

---

## Task 1: GeoJSON-fixtures verklaren hun stelsel

**Files:**
- Modify: `tests/fixtures/gis/afbakening_gebied.geojson`, `rond_deelstelsel_cd.geojson`,
  `rond_de_fixture.geojson`, `rond_put_ab.geojson`
- Test: bestaande suite (mag niet veranderen)

**Interfaces:**
- Consumes: niets
- Produces: fixtures die de CRS-heuristiek uit taak 3 passeren zonder testwijziging

De fixtures liggen op lokale coördinaten (±1000, ±2000), buiten de RD-bounds. Zonder
deze stap valt elke fixture door de nieuwe poort. De legacy `crs`-member is de door
het masterdocument genoemde geaccepteerde vorm.

- [ ] **Step 1: Voeg de crs-member toe aan elk van de vier bestanden**

```json
{
  "type": "Polygon",
  "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:EPSG::28992" } },
  "coordinates": [[[990, 1990], [1060, 1990], [1060, 2010], [990, 2010], [990, 1990]]]
}
```

(Behoud per bestand de eigen `coordinates`; alleen de `crs`-regel komt erbij.)

- [ ] **Step 2: Draai de suite**

Run: `uv run pytest -q`
Expected: 774 passed — de member verandert niets aan het huidige gedrag.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/gis
git commit -m "GIS-fixtures noemen hun coordinaatstelsel expliciet"
```

---

## Task 2: `mapnaam` — sanering voor het bestandssysteem

**Files:**
- Modify: `src/nlriochecker/studiegebied.py`
- Test: `tests/test_studiegebied.py`

**Interfaces:**
- Produces: `mapnaam(naam: str) -> str` in `nlriochecker.studiegebied`, gooit
  `StudyAreaError` als er niets overblijft.

- [ ] **Step 1: Schrijf de falende tests**

```python
import pytest
from nlriochecker.errors import StudyAreaError
from nlriochecker.studiegebied import mapnaam


@pytest.mark.parametrize(
    ("naam", "verwacht"),
    [
        ("De Wolden", "de_wolden"),
        ("Zuidwolde-Noord", "zuidwolde_noord"),
        ("Échéllé", "echelle"),
        ("A/B", "a_b"),
        ("  dubbele   spatie ", "dubbele_spatie"),
        ("BUURT 01", "buurt_01"),
    ],
)
def test_mapnaam_saneert(naam: str, verwacht: str) -> None:
    assert mapnaam(naam) == verwacht


def test_mapnaam_zonder_bruikbare_tekens_is_een_fout() -> None:
    with pytest.raises(StudyAreaError, match="geen bruikbare mapnaam"):
        mapnaam("///")
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_studiegebied.py -k mapnaam -q`
Expected: FAIL — `cannot import name 'mapnaam'`.

- [ ] **Step 3: Implementeer**

```python
import re
import unicodedata

# Alles buiten deze tekens wordt een underscore: een mapnaam moet op elk
# bestandssysteem te maken zijn en in een pad te lezen blijven.
_ONVEILIG = re.compile(r"[^a-z0-9]+")


def mapnaam(naam: str) -> str:
    """Zet een gebiedsnaam om in een veilige mapnaam.

    Diakrieten eraf, lowercase, alles wat geen letter of cijfer is naar een
    underscore, opeenvolgende underscores samengevoegd. De originele naam blijft in
    de rapporttitels, de `Gebied`-kolom en de JSON staan; alleen het bestandssysteem
    krijgt deze vorm.
    """
    ontleed = unicodedata.normalize("NFKD", naam)
    zonder_diakrieten = "".join(teken for teken in ontleed if not unicodedata.combining(teken))
    veilig = _ONVEILIG.sub("_", zonder_diakrieten.lower()).strip("_")
    if not veilig:
        raise StudyAreaError(
            f"{naam!r} levert geen bruikbare mapnaam op: er blijft na sanering niets over."
        )
    return veilig
```

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_studiegebied.py -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Gebiedsnamen worden veilige mapnamen"
```

---

## Task 3: `Studiegebieden` — lezen en valideren per feature

**Files:**
- Modify: `src/nlriochecker/studiegebied.py`
- Test: `tests/test_studiegebied.py`

**Interfaces:**
- Consumes: `mapnaam` (taak 2)
- Produces:
  - `class RdGrenzen(NamedTuple): x_min: float; x_max: float; y_min: float; y_max: float`
  - `@dataclass(frozen=True) class Studiegebieden` met `gebieden: tuple[StudyArea, ...]`,
    `source: Path`, `laag: str`, `overgeslagen: tuple[str, ...]`,
    `beschikbaar: tuple[str, ...]`, properties `enkel: bool`, `totaal: StudyArea`,
    methode `selecteer(namen: Sequence[str]) -> Studiegebieden`
  - `load_studiegebieden(path: Path, laag: str | None = None, *, grenzen: RdGrenzen | None = None) -> Studiegebieden`
  - `load_study_area(path, laag=None, *, grenzen=None) -> StudyArea` (bestaand, nu een
    dunne schil om `load_studiegebieden(...).totaal`)

**Ontwerpregels die de tests vastleggen:**

1. Alleen `Polygon` en `MultiPolygon` worden geladen; `GeometryCollection` wordt niet
   uitgepakt. Overgeslagen typen: geteld per type in `overgeslagen`, plus `logger.warning`.
2. Nul polygonen na filtering: `StudyAreaError`.
3. `naam_gebied` is alleen vereist bij meer dan één feature: aanwezig, niet-leeg na
   `strip()`, uniek; en de gesaneerde namen moeten onderling verschillen.
4. Eén feature: `name`/`gebied` exact zoals nu, behalve dat een gevulde `naam_gebied`
   de gebiedsaanduiding wordt.
5. GeoJSON-CRS: legacy `crs`-member die 28992 noemt → goed; anders, als `grenzen`
   meegegeven is, moeten alle coördinaten binnen die bounds vallen.

- [ ] **Step 1: Schrijf de falende tests**

```python
def _maak_buurten_gpkg(
    pad: Path,
    vlakken: list[tuple[str, Polygon]],
    laag: str = "buurten",
    kolom: str = "naam_gebied",
) -> Path:
    """Schrijft een GeoPackage met meerdere buurten en een naamkolom."""
    con = sqlite3.connect(pad)
    con.execute("PRAGMA application_id = 0x47504B47")
    con.execute(
        "create table gpkg_contents (table_name text, data_type text, identifier text, "
        "srs_id integer)"
    )
    con.execute(
        "create table gpkg_geometry_columns (table_name text, column_name text, "
        "geometry_type_name text, srs_id integer)"
    )
    con.execute(f'create table "{laag}" (fid integer primary key, "{kolom}" text, geom blob)')
    con.execute("insert into gpkg_contents values (?, 'features', ?, 28992)", (laag, laag))
    con.execute("insert into gpkg_geometry_columns values (?, 'geom', 'POLYGON', 28992)", (laag,))
    kop = b"GP" + bytes([0, 0]) + struct.pack("<i", 28992)
    for naam, vlak in vlakken:
        con.execute(
            f'insert into "{laag}" ("{kolom}", geom) values (?, ?)', (naam, kop + vlak.wkb)
        )
    con.commit()
    con.close()
    return pad


NOORD = Polygon([(0, 100), (100, 100), (100, 200), (0, 200)])
ZUID = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])


def test_twee_features_leveren_twee_gebieden(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    gebieden = load_studiegebieden(pad)

    assert [gebied.gebied for gebied in gebieden.gebieden] == ["Noord", "Zuid"]
    assert [gebied.name for gebied in gebieden.gebieden] == ["Noord", "Zuid"]
    assert not gebieden.enkel
    assert gebieden.totaal.area_ha == pytest.approx(2.0)


def test_een_feature_houdt_het_bestaande_gedrag(tmp_path: Path) -> None:
    pad = _maak_geopackage(tmp_path / "gebied.gpkg", VIERKANT)

    gebieden = load_studiegebieden(pad)

    assert gebieden.enkel
    assert gebieden.gebieden[0].name == "gebied"
    assert gebieden.gebieden[0].gebied == "gebied"


def test_naam_gebied_ontbreekt_bij_meerdere_features(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)], kolom="naam")

    with pytest.raises(StudyAreaError, match="naam_gebied"):
        load_studiegebieden(pad)


def test_lege_naam_noemt_de_rij(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("   ", ZUID)])

    with pytest.raises(StudyAreaError, match="rij 2"):
        load_studiegebieden(pad)


def test_dubbele_naam_is_een_fout(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Noord", ZUID)])

    with pytest.raises(StudyAreaError, match="Noord"):
        load_studiegebieden(pad)


def test_botsende_mapnamen_zijn_een_fout(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("De Wolden", NOORD), ("de-wolden", ZUID)])

    with pytest.raises(StudyAreaError, match="dezelfde mapnaam"):
        load_studiegebieden(pad)


def test_niet_polygonen_worden_gemeld_en_overgeslagen(tmp_path: Path) -> None:
    pad = tmp_path / "gemengd.geojson"
    pad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:28992"}},
                "features": [
                    {"type": "Feature", "properties": {}, "geometry": mapping(VIERKANT)},
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": mapping(Point(10, 10)),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    gebieden = load_studiegebieden(pad)

    assert gebieden.enkel
    assert any("Point" in melding for melding in gebieden.overgeslagen)


def test_alleen_niet_polygonen_is_een_fout(tmp_path: Path) -> None:
    pad = tmp_path / "punten.geojson"
    pad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:28992"}},
                "features": [
                    {"type": "Feature", "properties": {}, "geometry": mapping(Point(10, 10))}
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(StudyAreaError, match="geen enkel vlak"):
        load_studiegebieden(pad)


def test_geojson_buiten_de_rd_bounds(tmp_path: Path) -> None:
    pad = tmp_path / "wgs84.geojson"
    pad.write_text(
        json.dumps(mapping(Polygon([(6.4, 52.7), (6.5, 52.7), (6.5, 52.8), (6.4, 52.8)]))),
        encoding="utf-8",
    )

    with pytest.raises(StudyAreaError, match="WGS84"):
        load_studiegebieden(pad, grenzen=RdGrenzen(0.0, 300_000.0, 300_000.0, 620_000.0))


def test_geojson_met_legacy_crs_wordt_geaccepteerd(tmp_path: Path) -> None:
    """Een bestand dat zelf 28992 noemt, hoeft niet binnen de bounds te liggen."""
    pad = tmp_path / "lokaal.geojson"
    inhoud = mapping(VIERKANT) | {
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::28992"}}
    }
    pad.write_text(json.dumps(inhoud), encoding="utf-8")

    gebieden = load_studiegebieden(
        pad, grenzen=RdGrenzen(0.0, 300_000.0, 300_000.0, 620_000.0)
    )

    assert gebieden.enkel


def test_selecteer_kiest_gebieden(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    keuze = load_studiegebieden(pad).selecteer(["Zuid"])

    assert [gebied.gebied for gebied in keuze.gebieden] == ["Zuid"]
    assert keuze.beschikbaar == ("Noord", "Zuid")


def test_selecteer_onbekende_naam(tmp_path: Path) -> None:
    pad = _maak_buurten_gpkg(tmp_path / "b.gpkg", [("Noord", NOORD), ("Zuid", ZUID)])

    with pytest.raises(StudyAreaError, match="Noord, Zuid"):
        load_studiegebieden(pad).selecteer(["Oost"])
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_studiegebied.py -q`
Expected: FAIL — `load_studiegebieden` bestaat niet.

- [ ] **Step 3: Implementeer**

Structuur in `studiegebied.py`:

```python
class RdGrenzen(NamedTuple):
    """De omhullende waarbinnen RD-coordinaten horen te vallen."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(frozen=True)
class Studiegebieden:
    """Alle features van een studiegebiedbestand, elk als eigen StudyArea.

    Een bestand met een enkele feature levert precies wat `load_study_area` altijd
    al leverde; met meer features rapporteert `toets` per gebied.
    """

    gebieden: tuple[StudyArea, ...]
    source: Path
    laag: str
    overgeslagen: tuple[str, ...] = ()
    beschikbaar: tuple[str, ...] = ()

    @property
    def enkel(self) -> bool: ...
    @property
    def totaal(self) -> StudyArea: ...
    def selecteer(self, namen: Sequence[str]) -> Studiegebieden: ...
```

`_lees_geopackage` en `_lees_geojson` leveren voortaan een tussenvorm
`list[tuple[BaseGeometry, dict[str, str]]]` (geometrie plus attributen) plus de
overgeslagen-meldingen; de gedeelde nabewerking (`naam_gebied`-eisen, mapnaambotsing,
StudyArea's bouwen) staat in één functie `_bouw_gebieden`. Zo kan de validatie niet
per formaat uiteenlopen.

`totaal` bouwt een `StudyArea` met de unie, `name` en `gebied` van de enkele feature
als er één is, anders `_naam(path, laag)` en `feature_count = len(gebieden)`.

`selecteer` matcht exact op `gebied`; onbekende namen leveren
`StudyAreaError` met de beschikbare namen (tot tien) of het aantal plus
`difflib.get_close_matches(...)` daarboven.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_studiegebied.py -q`
Expected: PASS

- [ ] **Step 5: Draai de volle suite**

Run: `uv run pytest -q`
Expected: PASS, ongewijzigd aantal — `load_study_area` gedraagt zich hetzelfde.

- [ ] **Step 6: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Het studiegebiedbestand wordt per feature gelezen en streng gevalideerd"
```

---

## Task 4: gedeelde ruimtelijke index en componenten

**Files:**
- Modify: `src/nlriochecker/afbakening.py`
- Test: `tests/test_afbakening.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class GedeeldeIndex` met `boom: STRtree`,
    `uris: tuple[str, ...]`, `componenten: list[set[str]]`,
    `component_van: dict[str, int]`, `strengen: tuple[tuple[str, str], ...]`,
    `zonder_netwerkverband: int`
  - `bouw_gedeelde_index(dataset: GwswDataset, config: CheckConfig) -> GedeeldeIndex`
  - `bouw_analyseset(dataset, area, config, *, gedeeld: GedeeldeIndex | None = None) -> Analyseset`

De boom levert **kandidaten**; het oordeel blijft `area.bevat(...)`. Zo kan de
uitkomst per constructie niet verschillen.

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_gedeelde_index_geeft_dezelfde_analyseset() -> None:
    """De optimalisatie mag geen enkel object toevoegen of weglaten."""
    dataset, area, config = _opzet()

    zonder = bouw_analyseset(dataset, area, config)
    met = bouw_analyseset(dataset, area, config, gedeeld=bouw_gedeelde_index(dataset, config))

    assert met.kern == zonder.kern
    assert met.schil == zonder.schil
    assert met.strengen_zonder_netwerkverband == zonder.strengen_zonder_netwerkverband


def test_componenten_uit_de_gedeelde_index_gelijk_aan_directe_graafanalyse() -> None:
    """De componentstructuur hangt niet van het gebied af; hoisten mag hem niet raken."""
    dataset, area, config = _opzet()
    index = bouw_gedeelde_index(dataset, config)

    kern = objecten_in_gebied(dataset, area)
    via_index = _component_uit_index(index, kern)
    direct = _component(dataset, config, kern)

    assert via_index == direct


def test_index_kandidaten_omvatten_alle_treffers() -> None:
    dataset, area, config = _opzet()
    index = bouw_gedeelde_index(dataset, config)

    assert objecten_in_gebied(dataset, area, gedeeld=index) == objecten_in_gebied(dataset, area)
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_afbakening.py -q`
Expected: FAIL — `bouw_gedeelde_index` bestaat niet.

- [ ] **Step 3: Implementeer**

```python
@dataclass(frozen=True)
class GedeeldeIndex:
    """Wat over gebieden heen hergebruikt mag worden bij het bouwen van analysesets.

    Twee structuren die niet van het gebied afhangen: een ruimtelijke index over alle
    object-geometrieen, en de samenhangende vrijvervalcomponenten van het volledige
    net. Met tachtig buurten zou beide anders tachtig keer opnieuw berekend worden.

    De boom levert alleen kandidaten op omhullende; het oordeel blijft `area.bevat`,
    zodat de uitkomst per constructie gelijk is aan die zonder index -- ook bij de
    ongeldige geometrieen die in deze datasets voorkomen.
    """

    boom: STRtree
    uris: tuple[str, ...]
    componenten: list[set[str]]
    component_van: dict[str, int]
    strengen: tuple[tuple[str, str], ...]
    zonder_netwerkverband: int

    def kandidaten(self, geometrie: BaseGeometry) -> Iterator[str]:
        """De URI's waarvan de omhullende die van `geometrie` raakt."""
        for index in self.boom.query(geometrie):
            yield self.uris[index]
```

`bouw_gedeelde_index` bouwt de lijst `(uri, geometrie)` uit `dataset.nodes` (met
`node.point`) en `dataset.conduits` (met `conduit.line`), slaat `None` en lege
geometrieën over, en hergebruikt de bestaande graafcode uit `_component` — die code
verhuist naar `bouw_gedeelde_index` en laat in `_component` alleen de selectie achter.

`objecten_in_gebied(dataset, area, *, gedeeld=None)` en `_binnen_buffer(...)` lopen
over `gedeeld.kandidaten(...)` als er een index is, anders over de volledige
dictionaries. `_component_uit_index(index, kern)` bevat de selectiecode die nu in
`_component` staat; `_component(dataset, config, kern)` wordt
`_component_uit_index(bouw_gedeelde_index(dataset, config), kern)` en houdt zijn
huidige retourwaarde, zodat de bestaande tests niet hoeven te wijzigen.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_afbakening.py -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Ruimtelijke index en componenten worden een keer gebouwd, niet per gebied"
```

---

## Task 5: gedeelde volledige-export-context en faselabel

**Files:**
- Modify: `src/nlriochecker/checks/base.py`
- Test: `tests/test_checks_registry.py`

**Interfaces:**
- Produces:
  - `CheckContext.gedeelde_volledige_context: CheckContext | None = None`
  - `run_checks(context, check_ids=None, *, typing_gate_applied=False, voortgang=NUL_VOORTGANG, fase="Checks")`

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_gedeelde_volledige_context_wordt_hergebruikt() -> None:
    """Anders wordt de karakteristiek van de volledige export per gebied herrekend."""
    dataset = load_dataset(TTL_DIR / "schoon.ttl")
    config = load_check_config()
    basis = CheckContext(dataset=dataset, config=config, volledige_dataset=dataset)
    gedeeld = basis.volledige_context()

    een = CheckContext(
        dataset=dataset, config=config, volledige_dataset=dataset,
        gedeelde_volledige_context=gedeeld,
    )
    twee = CheckContext(
        dataset=dataset, config=config, volledige_dataset=dataset,
        gedeelde_volledige_context=gedeeld,
    )

    assert een.volledige_context() is gedeeld
    assert twee.volledige_context() is gedeeld


def test_faselabel_van_run_checks_is_instelbaar() -> None:
    class Opname:
        def __init__(self) -> None:
            self.fasen: list[str] = []

        def start_fase(self, naam: str, totaal: int | None) -> None:
            self.fasen.append(naam)

        def stap(self, n: int = 1, label: str | None = None) -> None: ...
        def einde_fase(self) -> None: ...

    opname = Opname()
    context = CheckContext(dataset=load_dataset(TTL_DIR / "schoon.ttl"), config=load_check_config())

    run_checks(context, ["TOP-001"], voortgang=opname, fase="Checks Noord")

    assert opname.fasen == ["Checks Noord"]
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_checks_registry.py -q`
Expected: FAIL — onbekend keyword `gedeelde_volledige_context` / `fase`.

- [ ] **Step 3: Implementeer**

In `CheckContext`, na `analyseset`:

```python
    # De volledige-export-context van een run met meerdere studiegebieden. Hij hangt
    # af van de volledige dataset, de config en de onbetrouwbare objecten -- alle
    # drie gebiedsonafhankelijk -- en mag daarom over gebieden heen gedeeld worden.
    # Zonder dit veld bouwt elk gebied zijn eigen volledige context met een lege
    # cache, en draaien de karakteristiek en de checks met `volledig_bereik` per
    # gebied opnieuw over de hele export.
    gedeelde_volledige_context: CheckContext | None = field(default=None, compare=False, repr=False)
```

`volledige_context()` begint met:

```python
        if self.gedeelde_volledige_context is not None:
            return self.gedeelde_volledige_context
```

`run_checks` krijgt `fase: str = "Checks"` en gebruikt dat in `start_fase`. De
karakteristiek gaat via de cache van de volledige context:

```python
    karakteristiek = volledig.cached(
        "karakteristiek", lambda: bepaal_karakteristiek(volledig.dataset, context.config)
    )
```

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_checks_registry.py -q && uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "De volledige-export-context wordt over gebieden heen gedeeld"
```

---

## Task 6: `toetsloop.py` — nul, een of veel gebieden

**Files:**
- Create: `src/nlriochecker/toetsloop.py`
- Test: `tests/test_toetsloop.py`

**Interfaces:**
- Consumes: `Studiegebieden` (taak 3), `bouw_gedeelde_index`/`bouw_analyseset` (taak 4),
  `CheckContext.gedeelde_volledige_context`/`run_checks(fase=…)` (taak 5)
- Produces:
  - `@dataclass(frozen=True) class GebiedsRun: gebied: StudyArea | None; run: CheckRun; map: str`
  - `def toets_gebieden(dataset, gebieden, config, *, onbetrouwbaar, plausibiliteit, bronnen, check_ids=None, typing_gate_applied=False, meetbereik, voortgang=NUL_VOORTGANG) -> list[GebiedsRun]`

`map` is de gesaneerde naam; leeg bij één gebied of geen gebied (dan schrijft de
uitvoerlaag in de uitvoermap zelf).

- [ ] **Step 1: Schrijf de falende equivalentietest**

```python
def test_per_gebied_gelijk_aan_een_losse_run(tmp_path: Path) -> None:
    """De kerntest: een gebied in een tweebuurtenbestand geeft dezelfde meldingen."""
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    twee = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")
    los = load_studiegebieden(GIS_DIR / "buurt_noord.gpkg")

    samen = toets_gebieden(dataset, twee, config, **_leeg())
    alleen = toets_gebieden(dataset, los, config, **_leeg())

    noord = next(run for run in samen if run.gebied.gebied == "Noord")
    assert _sleutels(noord.run) == _sleutels(alleen[0].run)


def test_zonder_studiegebied_een_run_zonder_gebied() -> None:
    dataset = load_dataset(TTL_DIR / "top001_losliggende_put.ttl")

    runs = toets_gebieden(dataset, None, load_check_config(), **_leeg())

    assert len(runs) == 1
    assert runs[0].gebied is None
    assert runs[0].map == ""
```

waarbij `_sleutels(run)` de verzameling `(melding_id, check_id, object_uri)` uit
`bouw_meldingen(run, date(2026, 1, 1))` is, en `_leeg()` de verplichte keywords met
lege waarden vult (`onbetrouwbaar=frozenset()`, `plausibiliteit=load_plausibility()`,
`bronnen=None`, `meetbereik=Meetbereik.niet_gemeten(())`).

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_toetsloop.py -q`
Expected: FAIL — module bestaat niet (en de fixtures uit taak 8 ontbreken nog; die
worden in deze taak alvast gegenereerd — zie stap 3b).

- [ ] **Step 3: Implementeer `toetsloop.py`**

```python
"""De toetsloop: dezelfde checks over nul, een of veel studiegebieden.

Het laden van de dataset kost op de De Wolden-export ruim drie minuten en circa
3 GB; N keer laden is uitgesloten. Deze module laadt dus niets, maar krijgt de
geladen dataset mee en bouwt er per gebied een eigen analyseset op.

Wat over gebieden heen gedeeld wordt, is uitsluitend wat niet van het gebied
afhangt: de ruimtelijke index, de componenten van het volledige net en de
volledige-export-context. Alles wat aan de uitgedunde dataset van een gebied hangt
-- de topologie-index, de netwerkgraaf -- blijft per gebied.
"""
```

De loop:

```python
def toets_gebieden(...) -> list[GebiedsRun]:
    gedeeld = bouw_gedeelde_index(dataset, config) if gebieden is not None else None
    basis = CheckContext(dataset=dataset, config=config, unreliable_objects=onbetrouwbaar, ...)
    volledig = basis.volledige_context()
    resultaat: list[GebiedsRun] = []
    for area in _gebiedenlijst(gebieden):
        analyseset = bouw_analyseset(dataset, area, config, gedeeld=gedeeld) if area else None
        context = replace(basis, dataset=..., analyseset=analyseset,
                          gedeelde_volledige_context=volledig, _cache={})
        run = run_checks(context, check_ids, typing_gate_applied=..., voortgang=voortgang,
                         fase=_faselabel(area, gebieden))
        if area is not None:
            run = run.beperk_tot_studiegebied(area)
        resultaat.append(GebiedsRun(gebied=area, run=replace(run, meetbereik=meetbereik),
                                    map=_mapnaam(area, gebieden)))
    return resultaat
```

`KeyError` uit `run_checks` blijft doorlopen naar de CLI, die hem al vertaalt.

- [ ] **Step 3b: Genereer de fixtures die de test nodig heeft**

Breid `scripts/maak_gis_fixtures.py` uit met een `buurten`-sectie die drie bestanden
schrijft in `tests/fixtures/gis/`:

- `buurten_twee.gpkg`: laag `buurten`, kolom `naam_gebied`, features `Noord`
  (het vlak dat put A en B omsluit) en `Zuid` (het vlak eromheen dat put C raakt),
  zo gelegd dat één streng beide raakt (grensobject voor taak 9).
- `buurt_noord.gpkg` en `buurt_zuid.gpkg`: elk één feature met hetzelfde vlak en
  dezelfde `naam_gebied`.

Draai: `uv run python scripts/maak_gis_fixtures.py`

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_toetsloop.py -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "De toetsloop draait de checks per studiegebied-feature"
```

---

## Task 7: schrijflaag — submappen, totaalsynthese en JSON-envelop

**Files:**
- Modify: `src/nlriochecker/uitvoer/herkomst.py`, `src/nlriochecker/uitvoer/synthese.py`,
  `src/nlriochecker/uitvoer/__init__.py`
- Test: `tests/test_uitvoer_herkomst.py`, `tests/test_uitvoer_synthese.py`,
  `tests/test_toetsloop.py`

**Interfaces:**
- Consumes: `GebiedsRun` (taak 6)
- Produces:
  - `schrijf_json(..., gebied: str | None = None, gebieden: list[str] | None = None)`
  - `totaalsynthese(runs: list[GebiedsRun], meldingen: dict[str, list[Melding]], selectie: SelectieInfo | None) -> list[str]` in `uitvoer/synthese.py`
  - `@dataclass(frozen=True) class UitvoerPerGebied` met `per_gebied: dict[str, Uitvoer]`,
    `synthese: Path | None`, `totaal_csv: Path | None`, `totaal_json: Path | None`
  - `schrijf_uitvoer_gebieden(runs, output_dir, run_datum=None, *, met_geopackage=True, met_json=True, voortgang=NUL_VOORTGANG, beschikbaar=()) -> UitvoerPerGebied`

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_json_zonder_gebied_blijft_ongewijzigd(tmp_path: Path) -> None:
    """Een enkelvoudige run moet byte-voor-byte gelijk blijven aan ronde 1."""
    pad = schrijf_json(tmp_path / "b.json", [], run_datum=date(2026, 1, 1), dataset="d.ttl",
                       cfk_set=["Hyd"], volledig=True, typeringspoort_toegepast=False)

    document = json.loads(pad.read_text(encoding="utf-8"))

    assert "gebied" not in document and "gebieden" not in document


def test_json_van_een_gebied_noemt_het(tmp_path: Path) -> None:
    pad = schrijf_json(tmp_path / "b.json", [], run_datum=date(2026, 1, 1), dataset="d.ttl",
                       cfk_set=["Hyd"], volledig=True, typeringspoort_toegepast=False,
                       gebied="Noord")

    assert json.loads(pad.read_text(encoding="utf-8"))["gebied"] == "Noord"


def test_totaal_json_noemt_alle_gebieden(tmp_path: Path) -> None:
    pad = schrijf_json(tmp_path / "b.json", [], run_datum=date(2026, 1, 1), dataset="d.ttl",
                       cfk_set=["Hyd"], volledig=True, typeringspoort_toegepast=False,
                       gebieden=["Noord", "Zuid"])

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert document["gebied"] is None
    assert document["gebieden"] == ["Noord", "Zuid"]


def test_twee_gebieden_leveren_twee_submappen_en_een_totaal(tmp_path: Path) -> None:
    runs = ...  # uit toets_gebieden op buurten_twee.gpkg

    uitvoer = schrijf_uitvoer_gebieden(runs, tmp_path)

    assert (tmp_path / "noord" / FILE_CHECKS_MARKDOWN).exists()
    assert (tmp_path / "zuid" / FILE_CHECKS_MARKDOWN).exists()
    assert (tmp_path / "totaal" / "synthese.md").exists()
    assert uitvoer.totaal_json is not None


def test_een_gebied_schrijft_zonder_submap(tmp_path: Path) -> None:
    runs = ...  # uit toets_gebieden op buurt_noord.gpkg

    uitvoer = schrijf_uitvoer_gebieden(runs, tmp_path)

    assert (tmp_path / FILE_CHECKS_MARKDOWN).exists()
    assert uitvoer.synthese is None


def test_synthese_telt_unieke_en_meervoudige_meldingen(tmp_path: Path) -> None:
    """Een grensobject telt in beide gebieden, en een keer uniek."""
    runs = ...  # tweebuurtenrun met een streng die beide buurten raakt

    tekst = (tmp_path / "totaal" / "synthese.md").read_text(encoding="utf-8")

    assert "in meer dan een gebied" in tekst
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_uitvoer_herkomst.py tests/test_toetsloop.py -q`
Expected: FAIL — onbekende keywords / functie bestaat niet.

- [ ] **Step 3: Implementeer**

`schrijf_json`: bouw het document zoals nu en voeg toe:

```python
    if gebieden is not None:
        document["gebied"] = None
        document["gebieden"] = list(gebieden)
    elif gebied is not None:
        document["gebied"] = gebied
```

Zet die twee velden direct achter `dataset` in de sleutelvolgorde door het document
in de juiste volgorde op te bouwen; de docstring legt uit dat een enkelvoudige run
de velden niet krijgt, zodat hij byte-voor-byte gelijk blijft aan ronde 1.

`uitvoer/synthese.py` krijgt `totaalsynthese(...)`, die de Markdown-romp levert (de
kop en de herkomstregel komen van `schrijf_markdown`). Inhoud: de gebiedenlijst en
of het een selectie was, een tabel per gebied (oppervlak ha, meldingen, fouten,
waarschuwingen, weggelaten), een tabel per gebied per check, het aantal unieke
meldingen, het aantal in meer dan één gebied met de uitleg waarom de som der delen
afwijkt, en de overgeslagen niet-polygonen. Tabellen via `uitvoer.tabel.table`.

`uitvoer/__init__.py` krijgt `schrijf_uitvoer_gebieden`: bij één run gewoon
`schrijf_uitvoer(run, output_dir, …)`; bij meer runs per gebied
`schrijf_uitvoer(run, output_dir / gebiedsrun.map, …, gebied=…)` en daarna `totaal/`
met `schrijf_markdown` (synthese), `schrijf_csv(meldingen_tabel(uniek), …)` en
`schrijf_json(meldingen_json(uniek), …, gebieden=[...])`. `schrijf_uitvoer` krijgt
daarvoor een keyword `gebied: str | None = None` dat het alleen doorgeeft aan
`schrijf_json`.

Ontdubbelen: `melding_id` als sleutel, eerste voorkomen wint bij oplopende
gebiedsnaam.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Uitvoer per gebied in submappen, met een totaalsynthese"
```

---

## Task 8: CLI — `--gebied` en de wiring

**Files:**
- Modify: `src/nlriochecker/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_studiegebieden`, `toets_gebieden`, `schrijf_uitvoer_gebieden`

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_toets_schrijft_per_gebied(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(main, [
        "toets", "--dataset", str(TTL_DIR / "afbakening_kern_en_schil.ttl"),
        "--studiegebied", str(GIS_DIR / "buurten_twee.gpkg"),
        "--check", "TOP-001", "--output", str(tmp_path),
    ])

    assert resultaat.exit_code == 0, resultaat.output
    assert (tmp_path / "noord" / FILE_CHECKS_CSV).exists()
    assert (tmp_path / "zuid" / FILE_CHECKS_CSV).exists()
    assert (tmp_path / "totaal" / "synthese.md").exists()


def test_gebied_selecteert(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(main, [
        "toets", "--dataset", str(TTL_DIR / "afbakening_kern_en_schil.ttl"),
        "--studiegebied", str(GIS_DIR / "buurten_twee.gpkg"),
        "--gebied", "Noord", "--check", "TOP-001", "--output", str(tmp_path),
    ])

    assert resultaat.exit_code == 0, resultaat.output
    assert (tmp_path / "noord").exists()
    assert not (tmp_path / "zuid").exists()


def test_onbekend_gebied_faalt_met_de_namen(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(main, [
        "toets", "--dataset", str(TTL_DIR / "afbakening_kern_en_schil.ttl"),
        "--studiegebied", str(GIS_DIR / "buurten_twee.gpkg"),
        "--gebied", "Oost", "--output", str(tmp_path),
    ])

    assert resultaat.exit_code != 0
    assert "Noord" in resultaat.output and "Zuid" in resultaat.output
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_cli.py -k gebied -q`
Expected: FAIL — geen optie `--gebied`.

- [ ] **Step 3: Implementeer**

`--gebied` (multiple) op `toets`. In `check_command`:

```python
        gebieden = (
            load_studiegebieden(study_path, study_layer, grenzen=_rd_grenzen(config))
            if study_path is not None
            else None
        )
        if gebied_keuze:
            if gebieden is None:
                raise _CliError("--gebied vereist --studiegebied.")
            gebieden = gebieden.selecteer(list(gebied_keuze))
        runs = toets_gebieden(dataset, gebieden, config, …, voortgang=voortgang)
        uitvoer = schrijf_uitvoer_gebieden(runs, output_dir, …)
```

`_rd_grenzen(config)` bouwt `RdGrenzen` uit `config.drempels`. De schermuitvoer
loopt per `GebiedsRun`: bij één run precies de huidige regels; bij meer runs per
gebied een kopregel met de naam en daaronder dezelfde tellingen, gevolgd door de
geschreven bestanden en de synthese.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_cli.py -q && uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "toets rapporteert per gebied, met --gebied als selectie"
```

---

## Task 9: de resterende tests uit de spec

**Files:**
- Modify: `tests/test_toetsloop.py`, `tests/test_uitvoer_identiteit.py`,
  `tests/test_integration.py`, `scripts/maak_gis_fixtures.py`

- [ ] **Step 1: Grensobject in beide gebieden, zelfde ID**

```python
def test_grensobject_verschijnt_in_beide_gebieden_met_hetzelfde_id() -> None:
    runs = ...  # tweebuurtenrun
    noord = {m.melding_id for m in bouw_meldingen(runs[0].run, DATUM)}
    zuid = {m.melding_id for m in bouw_meldingen(runs[1].run, DATUM)}

    assert noord & zuid
```

- [ ] **Step 2: `melding_id` bevat het gebied niet**

```python
def test_melding_id_hangt_niet_van_het_gebied_af() -> None:
    """Anders zou hetzelfde defect in twee buurten twee ID's krijgen."""
    assert melding_id("TOP-001", "u", "", {}) == melding_id("TOP-001", "u", "", {})
```

plus een sweep die controleert dat `identiteit.melding_id` geen parameter met
`gebied` in de naam heeft.

- [ ] **Step 3: Zware tests onder de marker `zwaar`**

Een test op de volledige De Wolden-data met een twee-buurtenbestand (overslaan als
`data/` ontbreekt), en een schaaltest met 80+ gegenereerde buurten die bewaakt dat de
run doorloopt en de mappenstructuur klopt; duur loggen, geen tijdslimiet.

Breid `scripts/maak_gis_fixtures.py` uit met `schrijf_buurtenraster(pad, aantal)` die
een GeoPackage met `aantal` aaneengesloten vierkanten en unieke `naam_gebied`-waarden
schrijft; de zware test roept die functie aan via `importlib` op het scriptpad, zoals
`tests/test_uitgave.py` dat voor `scripts/uitgave.py` doet.

- [ ] **Step 4: Draai alles, ook de zware**

Run: `uv run pytest -q && uv run pytest -q -m zwaar`
Expected: PASS (of skip waar `data/` ontbreekt)

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Tests voor grensobjecten, ID-stabiliteit en schaal"
```

---

## Task 10: documentatie

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `docs/json-schema.md`,
  `docs/beslislog.md`

- [ ] **Step 1: `docs/beslislog.md` — vier vermeldingen**

BO-11 dubbeltelling van grensobjecten als bewuste keuze; BO-12 het hybride
uitvoeringsmodel met de equivalentie-eis en de twee verplichte optimalisaties;
BO-13 de RD-bounds-heuristiek voor GeoJSON, inclusief de `crs`-members in de
fixtures en waarom dat geen testwijziging is; BO-14 het bewust uitstellen van de
lokaal/contextueel-optimalisatie tot na meting op de 80-buurtencasus.

- [ ] **Step 2: `docs/json-schema.md`**

De velden `gebied` (per-gebied-JSON) en `gebied: null` + `gebieden` (totaal-JSON),
als achterwaarts verenigbare toevoeging binnen 1.x — schemaversie blijft `"1.0"`.
Noem expliciet dat een run zonder gebieden de velden niet draagt.

- [ ] **Step 3: `README.md`**

Multi-feature-gedrag, de `naam_gebied`-eis, `--gebied`, de mappenstructuur, de
validatieregels, dat er geen GeoPackage in `totaal/` staat, en dat `vergelijk` bij
per-gebied-vergelijking op de map van één gebied gericht moet worden.

- [ ] **Step 4: `CLAUDE.md`, sectie Studiegebied**

Bijwerken in dezelfde toon en dichtheid als de bestaande tekst.

- [ ] **Step 5: `CHANGELOG.md` onder `## [Unreleased]`**

Rubrieken Toegevoegd en Gewijzigd.

- [ ] **Step 6: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Ronde 2 vastgelegd: leeswijzer, beslislog, schema en wijzigingslog"
```

---

## Task 11: reviewstappen

- [ ] **Step 1:** `/superpowers:requesting-code-review` en de bevindingen verwerken.
- [ ] **Step 2:** `/python-library-complete:reviewing-python-libraries` en de
      bevindingen verwerken.
- [ ] **Step 3:** Kwaliteitspoort schoon, afsluitende commit, versienummer niet ophogen.
