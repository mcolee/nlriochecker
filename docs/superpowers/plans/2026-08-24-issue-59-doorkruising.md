# Issue #59: EXT-002/003 melden doorkruising, geen nabijheid — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** EXT-002 en EXT-003 melden alleen nog een *echte doorkruising* van een BGT-waterdeel (erin door de ene oever, eruit door de andere, zonder erin te eindigen), per (streng, waterdeel)-paar, met in de toelichting de telling van wat binnen de zoekstraal viel maar afviel.

**Architecture:** De gedeelde ruimtelijke toets zit in `_zoek_kruisingen` / `_WatergangKruising.kruisingen` in `src/nlriochecker/checks/extern.py`; beide checks lezen daaruit. De fix zit dus alleen daar: een classificatie per paar (`_verhouding`), geen `break` meer na het eerste waterdeel, en een resultaatobject dat naast de doorkruisingen de afvaltellingen draagt voor de notitie. De populatie (`vrijvervalrioolleidingen`) en de GeoPackage-laag `waterdelen_zonder_zinker` (volgt de meldingen via het trefferregister) veranderen niet.

**Tech Stack:** Python 3.12, shapely 2 (bestaand), pytest. Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #59 (`gh issue list --json number,body --search 59`); besluit BO-43 in `docs/beslislog.md` (regel 2303 e.v.). Issue #58 (actualiteitsfilter op de BGT) is al gelandeerd op `dev`.

## Global Constraints

- Doorkruising per (vrijvervalstreng `L`, waterdeel-polygoon `W`): `L.intersects(W)` én `e == 0` én `k >= 2`, met `e` = aantal eindpunten van `L` in of op `W`, `k` = aantal punten waarin `L` de rand van `W` kruist. Geen enkele drempel: `ext_watergang_buffer_m` (1,0 m) blijft uitsluitend de zoekstraal voor kandidaten (`VectorLayer.nabij`).
- Afvalcategorieën, in deze volgorde beslist: (1) `L.intersects(W)` onwaar → *raakt niet*; (2) de snijding van `L` met de rand van `W` heeft lengte > 0 → *tangentieel*; (3) `e >= 1` → *lozingspunt*; (4) `k >= 2` → *doorkruising*; (5) anders (raakt de rand in één punt) → *raakt niet*.
- De populatie blijft `vrijvervalrioolleidingen(context)`; `klassen.vrijvervalleiding` en `klassen.kruisingsleiding` wijzigen niet. `Infiltratieriool` en `Overstortleiding` blijven in de populatie.
- De `break` na het eerste waterdeel per streng (BO-17) vervalt: elke echte doorkruising van elke kandidaat wordt teruggegeven; EXT-003 registreert per paar een treffer.
- Transparantie: `_WatergangKruising.notes` krijgt één regel met de tellingen (doorkruisingen, raakt niet, lozingspunt, tangentieel) over de paren binnen de zoekstraal.
- Publiek contract blijft: de kolom `buffer_m` in de GeoPackage-laag `waterdelen_zonder_zinker` en het detail `buffer_m` op de meldingen blijven bestaan (het is de zoekstraal); het JSON-schema wijzigt niet.
- Gegenereerde fixtures nooit met de hand bewerken: `tests/fixtures/ttl/ext_scenario.ttl` komt uit `scripts/maak_ttl_fixtures.py`, `tests/fixtures/gis/ext/*` uit `scripts/maak_gis_fixtures.py`. Regenereer met `uv run python scripts/maak_ttl_fixtures.py` en `uv run python scripts/maak_gis_fixtures.py`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten; volg de stijl van `extern.py`. Werk op `dev`. Geen `gh issue create`.
- CHANGELOG-regel onder `## [Unreleased]` → `### Gerepareerd` (die kop staat er al door issue #58).

---

### Task 1: Doorkruisingstoets, fixtures, tests en documentatie

**Files:**
- Modify: `scripts/maak_gis_fixtures.py:79-94` (waterdeellaag: vier waterdelen erbij)
- Modify: `scripts/maak_ttl_fixtures.py:1677-1738` (`ext_scenario.ttl`: acht putten en vier strengen erbij)
- Regenerate: `tests/fixtures/ttl/ext_scenario.ttl`, `tests/fixtures/gis/ext/bgt.gpkg`
- Modify: `src/nlriochecker/checks/extern.py:393-536` (`_Kruising`, `_zoek_kruisingen`, `_WatergangKruising`, `KruisingMetWatergang`, `KruisingZonderZinkerOfDuiker`)
- Modify: `tests/test_checks_extern.py` (verwachtingen + drie nieuwe tests)
- Modify: `docs/architectuur.md:107-113`, `src/nlriochecker/uitvoer/gpkg.py:651-654` (docstring), `docs/beslislog.md` (BO-17, vooruitwijzing), `CHANGELOG.md`

**Interfaces:**
- Consumes: `VectorLayer.nabij(geometrie, afstand)` → paren `(geometrie, attributen)`; `Conduit.line: LineString | None`; `CheckContext.cached(sleutel, bouw)`; `getal(aantal, enkelvoud, meervoud)` uit `nlriochecker.taal`.
- Produces: `_verhouding(lijn: BaseGeometry, waterdeel: BaseGeometry) -> str` (een van `DOORKRUISING`, `RAAKT_NIET`, `LOZINGSPUNT`, `TANGENTIEEL`); `_Kruisingen` (dataclass: `doorkruisingen: tuple[_Kruising, ...]`, `raakt_niet: int`, `lozingspunt: int`, `tangentieel: int`, property `kandidaten`); `_zoek_kruisingen(strengen, laag, buffer) -> _Kruisingen`; `_WatergangKruising.kruisingen(context) -> tuple[_Kruising, ...]` (ongewijzigde signatuur, alleen nog doorkruisingen).

- [ ] **Step 1: Fixtures uitbreiden (generatoren, niet de bestanden)**

Geometrie van de huidige fixture, ter oriëntatie: studiegebied (980, 1980)–(1120, 2020). Streng 2 loopt van B (1050, 2000) naar C (1090, 2000) door water-1 `box(1070, 1995, 1075, 2005)`: dat is al een echte doorkruising (`e=0`, `k=2`). Streng 3 (zinker) en streng 6 (duiker) doorkruisen water-2 `box(1015, 2005, 1020, 2015)`. De strook y ∈ [1982, 1995] is vrij, op put L1 (1005, 1990) en het BAG-pand (1108–1112, 1984–1987) na.

In `scripts/maak_gis_fixtures.py` vervang je het `waterdeel`-blok (het commentaar `# W1 kruist streng 2 ...` tot en met `"waterdeel",\n    )`) door:

```python
    # W1 kruist streng 2 (gemengd), W2 kruist streng 3 (een zinker) en streng 6
    # (een duiker, en dus geen rioolleiding). De vier onderste zijn de grensgevallen
    # van issue #59: streng 7 eindigt in water-3 (lozingspunt), streng 8 ligt 0,5 m
    # naast water-4 (raakt niet), streng 9 doorkruist de 0,3 m smalle greppel
    # water-5 (echte doorkruising, geen drempel) en streng 10 loopt precies over de
    # oostrand van water-6 (tangentieel).
    schrijf(
        gpd.GeoDataFrame(
            {
                "lokaal_id": ["water-1", "water-2", "water-3", "water-4", "water-5", "water-6"],
                "type": ["waterloop", "greppel", "waterloop", "waterloop", "greppel", "waterloop"],
            },
            geometry=[
                box(1070.0, 1995.0, 1075.0, 2005.0),
                box(1015.0, 2005.0, 1020.0, 2015.0),
                box(1080.0, 1985.0, 1085.0, 1992.0),
                box(1090.0, 1985.0, 1095.0, 1992.0),
                box(1050.0, 1985.0, 1050.3, 1992.0),
                box(1100.0, 1985.0, 1103.0, 1992.0),
            ],
        ),
        bgt,
        "waterdeel",
    )
```

In `scripts/maak_ttl_fixtures.py`, in `FIXTURES["ext_scenario.ttl"]`, direct ná de regel `+ leiding("L5", "4", [(1022.0, 2000.0), (1028.0, 2000.0)], "PutP", "PutQ")` en vóór het afsluitende `,\n)`, toevoegen:

```python
    + "\n"
    # De grensgevallen van issue #59, allemaal in de vrije strook y 1982-1995. Kale
    # putten en strengen (geen hoogte, BOB of inwinning), zodat alleen de
    # kruisingschecks ze zien. Streng 7 eindigt in water-3: lozingspunt, geen
    # bevinding. Streng 8 ligt 0,5 m naast water-4: binnen de zoekstraal, snijdt
    # niet, geen bevinding. Streng 9 doorkruist de 0,3 m smalle greppel water-5:
    # echte doorkruising, wel een bevinding. Streng 10 loopt over de oostrand van
    # water-6 (x = 1103): tangentieel, geen bevinding.
    + "# Grensgevallen van issue #59: streng 7 eindigt in een waterdeel (lozingspunt),\n"
    + "# streng 8 ligt 0,5 m naast een waterdeel, streng 9 doorkruist een 0,3 m smalle\n"
    + "# greppel, streng 10 loopt over de rand van een waterdeel. Alleen 9 is een bevinding.\n"
    + put("PutR", "R", 1060.0, 1988.0)
    + put("PutS", "S", 1082.0, 1988.0)
    + leiding("L7", "7", [(1060.0, 1988.0), (1082.0, 1988.0)], "PutR", "PutS")
    + put("PutT", "T", 1088.0, 1992.5)
    + put("PutU", "U", 1097.0, 1992.5)
    + leiding("L8", "8", [(1088.0, 1992.5), (1097.0, 1992.5)], "PutT", "PutU")
    + put("PutV", "V", 1045.0, 1988.0)
    + put("PutW", "W", 1055.0, 1988.0)
    + leiding("L9", "9", [(1045.0, 1988.0), (1055.0, 1988.0)], "PutV", "PutW")
    + put("PutX", "X", 1103.0, 1984.0)
    + put("PutY", "Y", 1103.0, 1994.0)
    + leiding("L10", "10", [(1103.0, 1984.0), (1103.0, 1994.0)], "PutX", "PutY")
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py && uv run python scripts/maak_gis_fixtures.py`. Controleer met `git status` dat alleen `tests/fixtures/ttl/ext_scenario.ttl` en bestanden onder `tests/fixtures/gis/ext/` (plus eventueel `tests/fixtures/gis/buurt*.gpkg`, die de generator ook herschrijft) gewijzigd zijn; andere TTL-fixtures mogen niet veranderen.

- [ ] **Step 2: Schrijf de falende tests**

In `tests/test_checks_extern.py`:

1. In `test_bronnen_worden_gelezen_in_rd`: `"bgt_water": 2` → `"bgt_water": 6`.
2. In de parametrisatie van `test_defect_wordt_gevonden`:
   - `("EXT-002", ["2", "3"])` → `("EXT-002", ["2", "3", "9"])`
   - `("EXT-003", ["2"])` → `("EXT-003", ["2", "9"])`
   - `("EXT-005", ["C", "E", "F", "L1", "L2", "P", "Q"])` → `("EXT-005", ["C", "E", "F", "L1", "L2", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y"])`
3. In `test_ext003_wijst_het_geraakte_waterdeel_aan`: verwachting wordt `{("bgt:waterdeel/water-1", "waterloop"), ("bgt:waterdeel/water-5", "greppel")}`.
4. In `test_ext003_verandert_zijn_uitslag_niet`: `["2"]` → `["2", "9"]`.
5. Nieuwe tests, onderaan het bestand:

```python
def test_kruisingscheck_telt_wat_binnen_de_zoekstraal_afviel(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Streng 7 (lozingspunt), 8 (raakt niet) en 10 (over de rand) zijn geen bevinding.

    Ze vielen wel binnen de zoekstraal; de toelichting hoort ze te tellen, anders
    leest stilte als "alles is een doorkruising of ligt ver van het water".
    """
    for check_id in ("EXT-002", "EXT-003"):
        outcome = uitkomst(check_id, config, bronnen)
        notitie = next(note for note in outcome.notes if "doorkruis" in note.lower())
        assert "3 doorkruisingen" in notitie
        assert "1 raakt het waterdeel niet" in notitie
        assert "1 eindigt erin (lozingspunt)" in notitie
        assert "1 loopt over de rand" in notitie


def test_ext002_noemt_de_zoekstraal_niet_als_criterium(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    bevinding = next(f for f in uitkomst("EXT-002", config, bronnen).findings if f.object_label == "9")

    assert bevinding.message.startswith("Doorkruist een BGT-waterdeel")
    assert bevinding.details["buffer_m"] == config.drempels.ext_watergang_buffer_m


@pytest.mark.parametrize(
    ("lijn", "verwacht"),
    [
        # Erin door de westoever, eruit door de oostoever.
        (LineString([(0.0, 5.0), (20.0, 5.0)]), "doorkruising"),
        # Eindigt midden in het water.
        (LineString([(0.0, 5.0), (15.0, 5.0)]), "lozingspunt"),
        # Eindigt precies op de oever: telt als erin.
        (LineString([(0.0, 5.0), (10.0, 5.0)]), "lozingspunt"),
        # Ligt ernaast.
        (LineString([(0.0, 11.0), (20.0, 11.0)]), "raakt niet"),
        # Raakt met een knik alleen het hoekpunt (10, 10) aan, van buiten.
        (LineString([(0.0, 20.0), (10.0, 10.0), (0.0, 0.0)]), "raakt niet"),
        # Loopt over de noordrand.
        (LineString([(5.0, 10.0), (25.0, 10.0)]), "tangentieel"),
        # Twee keer erin en eruit (k = 4): nog steeds een doorkruising.
        (
            LineString(
                [(0.0, 5.0), (12.0, 5.0), (12.0, -5.0), (15.0, -5.0), (15.0, 5.0), (25.0, 5.0)]
            ),
            "doorkruising",
        ),
    ],
)
def test_verhouding_tussen_streng_en_waterdeel(lijn: LineString, verwacht: str) -> None:
    from nlriochecker.checks.extern import _verhouding

    assert _verhouding(lijn, box(10.0, 0.0, 20.0, 10.0)) == verwacht
```

Let op: het laatste geval loopt van (0,5) via (12,5) en (12,8) naar (20,8): erin op x=10, eruit op x=20; twee randkruisingen, geen eindpunt erin. Voeg bovenaan toe: `from shapely.geometry import LineString, box`.

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checks_extern.py -v`
Expected: FAIL op o.a. `test_defect_wordt_gevonden[EXT-002-...]` (huidige code meldt ook 7, 8 en 10), `test_kruisingscheck_telt_...` (geen notitie), `test_ext002_noemt_...` ("Kruist ..."), `test_verhouding_...` (`ImportError: cannot import name '_verhouding'`). `test_bronnen_worden_gelezen_in_rd` en de EXT-005-rij slagen al na de regeneratie.

- [ ] **Step 4: Implementeer de doorkruisingstoets**

In `src/nlriochecker/checks/extern.py` vervang je het blok van `@dataclass(frozen=True)\nclass _Kruising:` tot en met het einde van `_zoek_kruisingen` (de regel `            break`) door:

```python
@dataclass(frozen=True)
class _Kruising:
    """Een vrijvervalstreng die een BGT-waterdeel echt doorkruist.

    De geometrie van het waterdeel gaat mee omdat EXT-003 er de treffer voor de
    GIS-uitvoer mee registreert; de detectie verandert er niet door. `buffer` is de
    zoekstraal waarbinnen het waterdeel als kandidaat gevonden is, niet het
    criterium (BO-43). Een dataclass in plaats van een tuple: beide checks pakten
    hem uit op positie, en een veld erbij of een andere volgorde zou daar pas
    tijdens het draaien opvallen.
    """

    conduit: Conduit
    vorm: BaseGeometry
    rij: dict[str, object]
    laag: VectorLayer
    buffer: float


@dataclass(frozen=True)
class _Kruisingen:
    """De doorkruisingen plus de telling van wat binnen de zoekstraal viel maar afviel.

    De tellingen zijn per paar (streng, kandidaat-waterdeel); een streng die twee
    waterdelen nadert telt twee keer.
    """

    doorkruisingen: tuple[_Kruising, ...]
    raakt_niet: int
    lozingspunt: int
    tangentieel: int

    @property
    def kandidaten(self) -> int:
        """Het aantal paren dat binnen de zoekstraal viel."""
        return len(self.doorkruisingen) + self.raakt_niet + self.lozingspunt + self.tangentieel


DOORKRUISING = "doorkruising"
RAAKT_NIET = "raakt niet"
LOZINGSPUNT = "lozingspunt"
TANGENTIEEL = "tangentieel"


def _verhouding(lijn: BaseGeometry, waterdeel: BaseGeometry) -> str:
    """Hoe een streng zich tot een waterdeel verhoudt (BO-43).

    Een doorkruising gaat het waterdeel in door de ene oever en eruit door de andere:
    de lijn snijdt het waterdeel, geen van haar eindpunten ligt in of op het waterdeel
    (`e = 0`) en zij kruist de rand in minstens twee punten (`k >= 2`). Een streng die
    erin eindigt is een lozingspunt (overstort, inlaat); een streng die de rand alleen
    aanraakt of ernaast ligt raakt het waterdeel niet; een streng die een stuk óver de
    rand loopt is tangentieel. Geen van die drie is een bevinding, en er is bewust geen
    drempel: een minimum-doorsnijding zou echte doorkruisingen van smalle greppels
    (0,3-0,5 m) wegfilteren.
    """
    if not lijn.intersects(waterdeel):
        return RAAKT_NIET
    rand = lijn.intersection(waterdeel.boundary)
    if rand.length > 0:
        return TANGENTIEEL
    # `boundary` van een lijn zijn haar twee eindpunten; `intersects` telt ook een
    # eindpunt dat precies op de oever ligt als erin.
    if waterdeel.intersects(lijn.boundary):
        return LOZINGSPUNT
    if isinstance(rand, MultiPoint) and len(rand.geoms) >= 2:
        return DOORKRUISING
    return RAAKT_NIET
```

Voeg bovenaan de module toe: `from shapely.geometry import MultiPoint` (naast de bestaande `BaseGeometry`-import).

```python


def _zoek_kruisingen(
    strengen: list[Conduit], laag: VectorLayer | None, buffer: float
) -> _Kruisingen:
    """Loopt de toetsbare strengen langs alle kandidaat-waterdelen binnen de zoekstraal.

    Vrije functie zonder `self`: de uitkomst hangt alleen van deze drie argumenten af,
    zodat de gedeelde cache-ingang van `_WatergangKruising.kruisingen` niet aan de
    eerste aanroepende subklasse vastzit. Elke kandidaat wordt beoordeeld; er is geen
    `break` na de eerste (de herziening van BO-17 in BO-43).
    """
    doorkruisingen: list[_Kruising] = []
    telling = {RAAKT_NIET: 0, LOZINGSPUNT: 0, TANGENTIEEL: 0}
    if laag is not None:
        for conduit in strengen:
            # `_selecteer` liet alleen strengen met een geometrie door; deze functie
            # leunt daar niet op, zodat ze ook los van die selectie te lezen is.
            if conduit.line is None:
                continue
            for geometrie, rij in laag.nabij(conduit.line, buffer):
                if conduit.line.distance(geometrie) > buffer:
                    continue
                verhouding = _verhouding(conduit.line, geometrie)
                if verhouding == DOORKRUISING:
                    doorkruisingen.append(_Kruising(conduit, geometrie, rij, laag, buffer))
                else:
                    telling[verhouding] += 1
    return _Kruisingen(
        doorkruisingen=tuple(doorkruisingen),
        raakt_niet=telling[RAAKT_NIET],
        lozingspunt=telling[LOZINGSPUNT],
        tangentieel=telling[TANGENTIEEL],
    )
```

In `_WatergangKruising`:

- Vervang `kruisingen` door twee methoden (de docstring van de oude `kruisingen` blijft inhoudelijk, minus de alinea over de `break`):

```python
    def kruisingstoets(self, context: CheckContext) -> _Kruisingen:
        """De doorkruisingen en de afvaltellingen, een keer per context berekend.

        De lijst wordt door EXT-002 en EXT-003 gedeeld. Dat mag omdat de drie
        ingredienten van deze basisklasse zijn en niet van de aanroepende check: de
        populatie (`objecten()` levert voor beide `vrijvervalrioolleidingen(context)`,
        door dezelfde `selectie()` gefilterd), de laag `bgt_water` en de zoekstraal.
        De twee deden dus tweemaal dezelfde ruimtelijke toets.

        De bouwer is daarom een vrije functie: hij krijgt die drie mee en kent geen
        `self`, zodat de gedeelde ingang niet stilzwijgend van de eerste aanroeper kan
        gaan afhangen. Wie hier ooit een derde subklasse met een eigen populatie onder
        hangt (BO-25 verwierp dat voor EXT-003), moet haar dus een eigen sleutel geven.
        """
        toetsbaar = self.selectie(context).toetsbaar
        laag = self.laag(context)
        buffer = context.config.drempels.ext_watergang_buffer_m
        return context.cached(
            "ext:watergangkruisingen",
            lambda: _zoek_kruisingen(toetsbaar, laag, buffer),
        )

    def kruisingen(self, context: CheckContext) -> tuple[_Kruising, ...]:
        """De echte doorkruisingen, met het waterdeel erbij."""
        return self.kruisingstoets(context).doorkruisingen
```

- In `_WatergangKruising.notes`, ná `notities = super().notes(context)` en vóór de `for wortel ...`-lus, de transparantieregel (alleen als de check bruikbaar is, anders is er niets geteld):

```python
        if self.bruikbaar(context):
            toets = self.kruisingstoets(context)
            buffer = context.config.drempels.ext_watergang_buffer_m
            notities.append(
                "Alleen een echte doorkruising is een bevinding: de streng gaat het "
                "waterdeel in door de ene oever en eruit door de andere, zonder erin te "
                f"eindigen (BO-43). Binnen de zoekstraal van {buffer:g} m vielen "
                f"{getal(toets.kandidaten, 'paar', 'paren')} streng-waterdeel: "
                f"{getal(len(toets.doorkruisingen), 'doorkruising', 'doorkruisingen')}, "
                f"{getal(toets.raakt_niet, 'raakt het waterdeel niet', 'raken het waterdeel niet')}, "
                f"{getal(toets.lozingspunt, 'eindigt erin (lozingspunt)', 'eindigen erin (lozingspunt)')} "
                f"en {getal(toets.tangentieel, 'loopt over de rand', 'lopen over de rand')}."
            )
```

Controleer eerst hoe `getal` enkelvoud/meervoud kiest (`src/nlriochecker/taal.py`): bij `aantal == 1` het tweede argument, anders het derde. Klopt dat niet met deze aanroepen, pas de aanroepen aan zodat de testteksten uit Step 2 letterlijk ontstaan (`"3 doorkruisingen"`, `"1 raakt het waterdeel niet"`, `"1 eindigt erin (lozingspunt)"`, `"1 loopt over de rand"`).

- In `KruisingMetWatergang.run`: docstring `"""Meldt elke streng die een BGT-waterdeel echt doorkruist. ..."""` en de meldingstekst wordt
  `f"Doorkruist een BGT-waterdeel van het type {soort!r} (zoekstraal {kruising.buffer:g} m)."`.
- In `KruisingZonderZinkerOfDuiker.run`: docstring `"""Meldt doorkruisingen waarvan de streng geen kruisingsconstructie is."""` en de meldingstekst wordt
  `f"Doorkruist een BGT-waterdeel ({soort}) maar staat niet geregistreerd als zinker."`.
- De moduledocstring en `EXT-003`-klassedocstring hoeven niet te veranderen.

- [ ] **Step 5: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_checks_extern.py -v`
Expected: alles PASS. Draai daarna de hele suite: `uv run pytest -q`. Valt een test in een ander bestand (`test_uitvoer_gpkg.py`, `test_toetsrun.py`, `test_toetsloop.py`, `test_ttl_fixtures.py`, `test_dataset_inwinning.py` lezen dezelfde fixture): lees de assertie, bepaal of het nieuwe getal het gevolg is van de acht putten/vier strengen of van de nieuwe toets, en werk de verwachting bij met een regel commentaar waarom. Verklaar elke aangepaste verwachting in je rapport. Een test die faalt om een andere reden is een bug in je wijziging, geen verwachting om bij te werken.

- [ ] **Step 6: Documentatie**

1. `docs/architectuur.md` regels 111-113: vervang
   `Twee beperkingen erven mee en blijven staan: EXT-001 meldt alleen het sterkste bouwwerk, en de watergangcheck stopt na het eerste waterdeel per streng. Zie BO-17 en BO-18.`
   door
   `Eén beperking erft mee en blijft staan: EXT-001 meldt alleen het sterkste bouwwerk (BO-17). De watergangcheck geeft elke echte doorkruising per streng terug; de `break` na het eerste waterdeel is met BO-43 vervallen. Zie ook BO-18.`
2. `src/nlriochecker/uitvoer/gpkg.py` docstring van `_schrijf_treffers` (regels 651-654): vervang de alinea `Twee beperkingen erven mee ... Zie de beslislog.` door
   `Eén beperking erft mee uit de detectie en wordt bewust niet gerepareerd: EXT-001 meldt per object alleen het sterkste bouwwerk (BO-17). De watergangcheck geeft sinds BO-43 elke echte doorkruising terug, ook meerdere per streng.`
3. `docs/beslislog.md`, BO-17 (regel 832 e.v.): voeg aan het einde van dat besluit (vóór de kop `### BO-18`) een alinea toe:
   `**Herzien in [[BO-43]].** De hier geaccepteerde `break` na het eerste waterdeel per streng in de watergangcheck is vervallen; de beperking tot het sterkste bouwwerk (EXT-001) blijft.`
4. `CHANGELOG.md`, onder `### Gerepareerd` in `## [Unreleased]`, onder de regel van #58:

```markdown
- **EXT-002 en EXT-003 melden een doorkruising, geen nabijheid** (issue #59). Een
  vrijvervalstreng meldt alleen als zij het BGT-waterdeel echt doorkruist: erin door
  de ene oever, eruit door de andere, zonder erin te eindigen (`e = 0`, `k >= 2`,
  geen drempel). Een streng die binnen de zoekstraal ligt maar het water niet snijdt,
  of erin eindigt (lozingspunt), is geen bevinding meer; de toelichting telt die
  gevallen. Elke doorkruising per streng telt, de stop na het eerste waterdeel is
  vervallen. Op De Wolden zakt EXT-003 van 638 gemelde waterdelen naar de echte
  doorkruisingen. `ext_watergang_buffer_m` is voortaan alleen de zoekstraal. Zie BO-43.
```

- [ ] **Step 7: Mechanische poort**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen. Faalt `ruff format --check`, draai `uv run ruff format` en herhaal.

- [ ] **Step 8: Commit**

```bash
git add scripts/maak_gis_fixtures.py scripts/maak_ttl_fixtures.py tests/fixtures src/nlriochecker/checks/extern.py src/nlriochecker/uitvoer/gpkg.py tests/test_checks_extern.py docs/architectuur.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "EXT-002/003: meld een echte doorkruising van een waterdeel, geen nabijheid (issue #59)"
```

Staan er na `git status --short` nog gewijzigde testbestanden buiten deze lijst (verwachtingen uit Step 5), voeg die toe vóór de commit.

---

### Task 2: Effect op De Wolden meten (geen code)

**Files:**
- Read: `uitvoer/volledig_24082026/bevindingen.csv` (baseline 0.3.0, vóór #58 en #59) en `uitvoer/issue58/bevindingen.csv` (na #58, vóór #59; bestaat als Task 2 van het #58-plan gedraaid is)
- Create (niet committen; `uitvoer/` is git-ignored): `uitvoer/issue59/`

- [ ] **Step 1: Draai de volledige toets, mét GeoPackage**

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --projectconfig configs/dewoldenhoogeveen.toml \
  --bronnen data/gis_dewoldenhoogeveen \
  --geen-json \
  --output uitvoer/issue59
```

Expected: eindigt met `Geschreven: uitvoer/issue59/dq_dewoldenhoogeveen_orox_<datum>.gpkg`; duurt ca. 2-3 minuten.

- [ ] **Step 2: Vergelijk**

```bash
uv run python - <<'EOF'
import pandas as pd
runs = {
    "baseline": "uitvoer/volledig_24082026/bevindingen.csv",
    "na #58": "uitvoer/issue58/bevindingen.csv",
    "na #59": "uitvoer/issue59/bevindingen.csv",
}
frames = {naam: pd.read_csv(pad, sep=";") for naam, pad in runs.items()}
for check in ["EXT-002", "EXT-003"]:
    for naam, frame in frames.items():
        deel = frame[frame.Check == check]
        print(f"{check} {naam}: {len(deel)} meldingen, {deel.ObjectURI.nunique()} strengen, "
              f"{deel.Object2URI.nunique()} unieke waterdelen")
EOF
grep -n "doorkruising" uitvoer/issue59/bevindingen.md | head -4
uv run python -c "
import sqlite3; c = sqlite3.connect('$(ls uitvoer/issue59/*.gpkg)')
print('waterdelen_zonder_zinker:', c.execute('select count(*) from waterdelen_zonder_zinker').fetchone())
print('gwsw_run n_waterdelen:', c.execute('select n_waterdelen from gwsw_run').fetchone())"
```

Verwacht volgens het issue: EXT-003 unieke waterdelen 638 (baseline) → 580 (na #58) → **234** (na #59); de notitie met de tellingen staat bij EXT-002 en EXT-003; de GeoPackage-laag telt evenveel rijen als er unieke waterdelen bij EXT-003 zijn. Wijkt 234 af, meld het getal, de richting en wat je in de data ziet (bv. een steekproef van vijf gemelde paren met `Object2URI`); redeneer het niet weg.

- [ ] **Step 3: Rapporteer**

Zet de drie-kolomstabel (baseline / na #58 / na #59, per check: meldingen, strengen, unieke waterdelen), de tellingregel uit het rapport en de GeoPackage-telling in het rapportbestand van deze taak. Geen commit.
