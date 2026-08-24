# Ronde 3: EXT-treffers als lagen, en een dekkingspoort — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De GeoPackage van `toets` krijgt de externe objecten waarnaar EXT-001 en
EXT-003 verwijzen als twee featurelagen, strikt gejoind vanuit de meldingenstroom; en
het laden van de externe bronnen krijgt een harde poortcheck op de dekking.

**Architecture:** De checks registreren de geraakte externe objecten tijdens het
draaien in een `Trefferregister` op de `CheckContext`; `run_checks` geeft dat als
`CheckRun.treffers` door. De GeoPackage-schrijver joint de meldingen van déze uitvoer
op dat register via `object2_uri`, zodat laag en testuitkomst per constructie gelijk
zijn. De dekkingspoort zit volledig binnen `load_external_data` en meet elke
aangeleverde laag tegen de omhullende van `bronnen.studiegebied`.

**Tech Stack:** Python 3.12, shapely, stdlib `sqlite3` en `hashlib`, click, pydantic,
rasterio (alleen in tests voor een miniatuurraster); pytest; uv; ruff + mypy.

**Spec:** `docs/superpowers/specs/2026-08-19-ronde3-ext-lagen-en-dekkingspoort-design.md`

## Global Constraints

- Werk op branch `dev`. Versienummer nergens ophogen.
- Geen nieuwe afhankelijkheden.
- Geen hardcoded drempels: de tolerantie komt uit `[bronnen] dekking_tolerantie_m`
  (standaard `0.0`), de marge uit de EXT-zoekafstanden in `[drempels]`.
- De detectielogica van EXT-001 en EXT-003 verandert niet: geen `break` weg, geen
  `_sterkste` verruimen. De bestaande suite draait ongewijzigd groen.
- Enige schrijvers blijven `schrijf_markdown`, `schrijf_csv`, `schrijf_json`
  (`uitvoer/herkomst.py`) plus `schrijf_geopackage`; de sweep in
  `tests/test_uitvoer_herkomst.py` bewaakt dat.
- De lagen worden uitsluitend gevuld vanuit de meldingenstroom; de schrijver bevraagt
  geen externe laag en doet geen ruimtelijke selectie.
- Geen treffergeometrie in CSV of JSON.
- Nederlandse docstrings, Engelse identifiers, type hints overal.
- Na elke taak: `uv run ruff check`, `uv run ruff format --check .`, `uv run mypy`,
  `uv run pytest` — alles groen, en committen.
- `CHANGELOG.md` wordt in taak 8 in één keer bijgewerkt.

## Bestandsindeling

| Bestand | Verantwoordelijkheid | Actie |
|---|---|---|
| `src/nlriochecker/checks/treffers.py` | `Treffer`, `Trefferregister`, sleutel- en labelbepaling | nieuw |
| `src/nlriochecker/checks/base.py` | `CheckContext.treffers`, `CheckRun.treffers` | uitbreiden |
| `src/nlriochecker/toetsloop.py` | vers register per gebied | uitbreiden |
| `src/nlriochecker/checks/extern.py` | EXT-001 en EXT-003 vullen object2 en registreren | uitbreiden |
| `src/nlriochecker/uitvoer/gpkg.py` | twee lagen, tellingen, voortgang | uitbreiden |
| `src/nlriochecker/uitvoer/stijlen/bouwwerken.qml` | rode omlijning | nieuw |
| `src/nlriochecker/uitvoer/stijlen/waterdelen_zonder_zinker.qml` | blauwe omlijning | nieuw |
| `src/nlriochecker/externedata.py` | `Dekkingseis` en de poortcheck | uitbreiden |
| `src/nlriochecker/checkconfig.py` | `dekking_tolerantie_m`, `ext_zoekafstand_max_m` | uitbreiden |
| `src/nlriochecker/cli.py` | de dekkingseis meegeven | uitbreiden |
| `tests/gpkghelper.py` | vlakken met vrije attributen schrijven | uitbreiden |

## Vaste feiten uit de fixtures (gemeten, gebruik ze in de tests)

- `tests/fixtures/ttl/ext_scenario.ttl` met `tests/fixtures/gis/ext`:
  EXT-001 levert vier bevindingen (streng 1 `kruist`, streng 4 `binnen`, put P
  `binnen`, put Q `binnen`) en **alle vier** raken hetzelfde pand
  `lokaal_id = "pand-1"` uit de laag `pand` van `bgt.gpkg` (rol `bgt_pand`).
- EXT-003 levert één bevinding: streng 2, waterdeel `water-1`, `type = "waterloop"`.
  EXT-002 levert er twee (streng 2 en streng 3); streng 3 is een duiker en hoort
  daarom **niet** in `waterdelen_zonder_zinker`.
- Geometrie in `ext_scenario.ttl`: streng 1 = `(1000 2000, 1050 2000)`, knoop A =
  `(1000 2000)`, knoop B = `(1050 2000)`, put P = `(1022 2000)`, put Q = `(1028 2000)`.

---

## Task 1: Het trefferregister

**Files:**
- Create: `src/nlriochecker/checks/treffers.py`
- Test: `tests/test_checks_treffers.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Treffer` met `sleutel: str`, `bron: str`,
    `label: str`, `bronbestand: str`, `geometrie: BaseGeometry`,
    `attributen: dict[str, object]`
  - `class Trefferregister` met
    `registreer(treffer: Treffer, *, check_id: str, object_uri: str, afstand_m: float | None = None) -> str`,
    `get(sleutel: str) -> Treffer | None`,
    `afstand(sleutel: str, check_id: str, object_uri: str) -> float | None`,
    `__len__`, `__iter__` (over de treffers)
  - `bouw_sleutel(voorvoegsel: str, attributen: dict[str, object], geometrie: BaseGeometry) -> tuple[str, bool]`
    — levert de sleutel en of er op de geometriehash is teruggevallen
  - `SLEUTELKOLOMMEN = ("lokaal_id", "identificatie", "id")`

- [ ] **Step 1: Schrijf de falende tests**

```python
"""Tests voor het trefferregister: de externe objecten die de checks raken."""

from __future__ import annotations

from shapely.geometry import box

from nlriochecker.checks.treffers import Treffer, Trefferregister, bouw_sleutel

VLAK = box(0, 0, 10, 10)


def _treffer(sleutel: str = "bgt:pand/p1") -> Treffer:
    return Treffer(
        sleutel=sleutel,
        bron="bgt_pand",
        label="pand p1",
        bronbestand="bgt.gpkg",
        geometrie=VLAK,
        attributen={"lokaal_id": "p1"},
    )


def test_sleutel_komt_uit_het_bron_id() -> None:
    sleutel, terugval = bouw_sleutel("bgt:pand", {"lokaal_id": "p1"}, VLAK)

    assert sleutel == "bgt:pand/p1"
    assert terugval is False


def test_sleutel_valt_terug_op_de_geometriehash() -> None:
    """Zonder bron-ID moet de sleutel toch stabiel en herhaalbaar zijn."""
    sleutel, terugval = bouw_sleutel("bgt:pand", {"status": "bestaand"}, VLAK)
    opnieuw, _ = bouw_sleutel("bgt:pand", {"status": "bestaand"}, VLAK)

    assert sleutel.startswith("geo:")
    assert len(sleutel) == len("geo:") + 12
    assert sleutel == opnieuw
    assert terugval is True


def test_sleutelvolgorde_lokaal_id_wint_van_identificatie() -> None:
    sleutel, _ = bouw_sleutel("bgt:pand", {"identificatie": "b", "lokaal_id": "a"}, VLAK)

    assert sleutel == "bgt:pand/a"


def test_lege_waarde_telt_niet_als_id() -> None:
    sleutel, terugval = bouw_sleutel("bgt:pand", {"lokaal_id": "  ", "id": "x"}, VLAK)

    assert sleutel == "bgt:pand/x"
    assert terugval is False


def test_registreren_ontdubbelt_op_de_sleutel() -> None:
    register = Trefferregister()

    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:a", afstand_m=0.0)
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:b", afstand_m=0.5)

    assert len(register) == 1
    assert register.get("bgt:pand/p1") is not None


def test_afstand_wordt_per_melding_bewaard() -> None:
    """`Melding` draagt de afstand niet; de schrijver moet hem hier terugvinden."""
    register = Trefferregister()
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:a", afstand_m=0.0)
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:b", afstand_m=0.5)

    assert register.afstand("bgt:pand/p1", "EXT-001", "urn:b") == 0.5
    assert register.afstand("bgt:pand/p1", "EXT-001", "urn:onbekend") is None


def test_onbekende_sleutel_geeft_none() -> None:
    assert Trefferregister().get("bgt:pand/weg") is None
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_checks_treffers.py -q`
Expected: FAIL — `No module named 'nlriochecker.checks.treffers'`.

- [ ] **Step 3: Implementeer**

```python
"""Het trefferregister: de externe objecten die de checks tijdens een run raken.

De GeoPackage krijgt twee lagen met BGT- en BAG-objecten waarnaar EXT-meldingen
verwijzen. De geometrie van zo'n object hoort niet in `Finding.details` -- dat zou de
CSV en de JSON met WKB vervuilen -- en de schrijver mag de externe lagen niet zelf
bevragen, want dan kunnen laag en testuitkomst uit elkaar lopen. Daarom registreert de
check de treffer op het moment dat hij de bevinding bouwt, en joint de schrijver later
op de sleutel.

Het register doet zelf geen uitspraken: een treffer die er wel in staat maar door geen
enkele melding wordt aangewezen, komt nergens terecht.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from hashlib import sha256

from shapely.geometry.base import BaseGeometry

# De kolommen waarin de aangeleverde bronnen hun identificatie dragen, in de volgorde
# waarin ze gezocht worden. Gemeten op data/gis en op de fixtures: de BGT-lagen dragen
# `lokaal_id`, de BAG-laag `identificatie`, en beide daarnaast een `id`.
SLEUTELKOLOMMEN = ("lokaal_id", "identificatie", "id")

# Zo lang is de geometriehash in de terugvalsleutel. Twaalf hex is 48 bits: ruim
# genoeg om binnen een bronbestand niet te botsen, kort genoeg om te lezen.
HASHLENGTE = 12


@dataclass(frozen=True)
class Treffer:
    """Een extern object waarnaar ten minste een melding verwijst."""

    sleutel: str
    bron: str
    label: str
    bronbestand: str
    geometrie: BaseGeometry
    attributen: dict[str, object]


def bouw_sleutel(
    voorvoegsel: str, attributen: dict[str, object], geometrie: BaseGeometry
) -> tuple[str, bool]:
    """De sleutel van een extern object, en of er op de geometrie is teruggevallen.

    Voorbeelden: `bgt:pand/G1690.01d7...`, `bag:pand/1690100000000178`. Draagt het
    bronbestand geen enkele identificatie, dan `geo:<12 hex van sha256 over de WKB>`.
    Die is stabiel over runs op hetzelfde bestand en ontdubbelt twee bestanden met
    dezelfde geometrie -- precies wat hier bedoeld is.
    """
    for kolom in SLEUTELKOLOMMEN:
        waarde = attributen.get(kolom)
        if waarde is not None and str(waarde).strip():
            return f"{voorvoegsel}/{str(waarde).strip()}", False
    return f"geo:{sha256(geometrie.wkb).hexdigest()[:HASHLENGTE]}", True


@dataclass
class Trefferregister:
    """De externe objecten die de checks tijdens deze run geraakt hebben."""

    _treffers: dict[str, Treffer] = field(default_factory=dict)
    _afstanden: dict[tuple[str, str, str], float] = field(default_factory=dict)

    def registreer(
        self,
        treffer: Treffer,
        *,
        check_id: str,
        object_uri: str,
        afstand_m: float | None = None,
    ) -> str:
        """Legt een treffer vast en levert zijn sleutel terug.

        De eerste registratie van een sleutel wint; de geometrie is per sleutel per
        definitie dezelfde. `afstand_m` hoort bij deze ene melding en niet bij de
        treffer, want twee objecten kunnen hetzelfde pand op verschillende afstand
        raken; hij wordt daarom onder de drie velden bewaard die elke melding draagt.
        """
        self._treffers.setdefault(treffer.sleutel, treffer)
        if afstand_m is not None:
            self._afstanden[(treffer.sleutel, check_id, object_uri)] = afstand_m
        return treffer.sleutel

    def get(self, sleutel: str) -> Treffer | None:
        """De treffer bij deze sleutel, of None."""
        return self._treffers.get(sleutel)

    def afstand(self, sleutel: str, check_id: str, object_uri: str) -> float | None:
        """De afstand die bij deze melding hoort, of None."""
        return self._afstanden.get((sleutel, check_id, object_uri))

    def __len__(self) -> int:
        """Het aantal verschillende getroffen objecten."""
        return len(self._treffers)

    def __iter__(self) -> Iterator[Treffer]:
        """Loopt over de treffers."""
        return iter(self._treffers.values())
```

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_checks_treffers.py -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Trefferregister voor de externe objecten die de checks raken"
```

---

## Task 2: Het register loopt mee met de run

**Files:**
- Modify: `src/nlriochecker/checks/base.py`, `src/nlriochecker/toetsloop.py`
- Test: `tests/test_checks_blok_a.py`

**Interfaces:**
- Consumes: `Trefferregister` (taak 1)
- Produces: `CheckContext.treffers: Trefferregister`, `CheckRun.treffers: Trefferregister`

- [ ] **Step 1: Schrijf de falende test**

```python
def test_de_run_draagt_het_trefferregister_van_zijn_context() -> None:
    """De schrijver joint later de meldingen op dit register."""
    dataset = load_dataset(TTL_DIR / "schoon.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())

    run = run_checks(context, ["TOP-001"])

    assert run.treffers is context.treffers
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_checks_blok_a.py -k trefferregister -q`
Expected: FAIL — `CheckContext` heeft geen attribuut `treffers`.

- [ ] **Step 3: Implementeer**

In `checks/base.py`, import erbij:

```python
from nlriochecker.checks.treffers import Trefferregister
```

In `CheckContext`, direct na `gedeelde_volledige_context`:

```python
    # De externe objecten die de EXT-checks tijdens deze run raken. Mutabel, net als
    # `_cache`: een check registreert zijn treffer terwijl hij draait, en `run_checks`
    # bouwt de `CheckOutcome` pas als de generator leeg is. Het register doet geen
    # uitspraken -- alleen wat een melding aanwijst komt in de uitvoer terecht -- dus
    # een entry die blijft staan kan geen verkeerde laag opleveren.
    treffers: Trefferregister = field(default_factory=Trefferregister, compare=False, repr=False)
```

In `CheckRun`, na `meetbereik`:

```python
    # Het trefferregister van de context waarop deze run gedraaid heeft; de
    # GeoPackage-schrijver joint de meldingen erop. Zie `checks/treffers.py`.
    treffers: Trefferregister = field(default_factory=Trefferregister, compare=False, repr=False)
```

In `run_checks`, in de `CheckRun(...)`-constructie:

```python
treffers = (context.treffers,)
```

In `toetsloop._per_gebied`, in de `replace(...)`-aanroep:

```python
treffers = (Trefferregister(),)
```

met een regel commentaar erbij:

```python
    # Vers register per gebied: een gedeeld register zou geen verkeerde laag opleveren
    # (de join op de meldingen beslist), maar het zou wel meegroeien met het aantal
    # buurten en bij het debuggen treffers van een ander gebied tonen.
```

en de import `from nlriochecker.checks.treffers import Trefferregister` bovenaan
`toetsloop.py`.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "De run draagt het trefferregister van zijn context"
```

---

## Task 3: EXT-001 wijst het geraakte bouwwerk aan

**Files:**
- Modify: `src/nlriochecker/checks/extern.py`
- Test: `tests/test_checks_extern.py`

**Interfaces:**
- Consumes: `Trefferregister`, `Treffer`, `bouw_sleutel` (taak 1); `context.treffers` (taak 2)
- Produces: EXT-001-bevindingen met `details["object2_uri"]` en
  `details["object2_label"]`; treffers met bron `bgt_pand`, `bag_pand` of
  `bgt_bouwwerk`
- Produces: `VOORVOEGSEL = {"bgt_pand": "bgt:pand", "bag_pand": "bag:pand",
  "bgt_bouwwerk": "bgt:bouwwerk", "bgt_water": "bgt:waterdeel"}` in `extern.py`
- Produces: `MARKERING_ZONDER_ID`, de notitietekst bij een bron zonder identificatie

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_ext001_wijst_het_geraakte_pand_aan(config: CheckConfig, bronnen: ExternalData) -> None:
    """Alle vier de bevindingen raken hetzelfde pand uit de BGT-fixture."""
    outcome = uitkomst("EXT-001", config, bronnen)

    uris = {finding.details["object2_uri"] for finding in outcome.findings}
    labels_ = {finding.details["object2_label"] for finding in outcome.findings}

    assert uris == {"bgt:pand/pand-1"}
    assert labels_ == {"pand pand-1"}


def test_ext001_registreert_de_treffer_met_geometrie(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    dataset = load_dataset(SCENARIO)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)

    run = run_checks(context, ["EXT-001"])

    treffer = run.treffers.get("bgt:pand/pand-1")
    assert treffer is not None
    assert treffer.bron == "bgt_pand"
    assert treffer.bronbestand == "bgt.gpkg"
    assert treffer.geometrie.geom_type in {"Polygon", "MultiPolygon"}
    assert len(run.treffers) == 1


def test_ext001_bewaart_de_afstand_per_melding(config: CheckConfig, bronnen: ExternalData) -> None:
    """`Melding` draagt de afstand niet; de laag haalt hem uit het register."""
    dataset = load_dataset(SCENARIO)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)

    run = run_checks(context, ["EXT-001"])
    streng = next(f for f in run.findings if f.object_label == "1")

    assert run.treffers.afstand("bgt:pand/pand-1", "EXT-001", streng.object_uri) == 0.0


def test_ext001_verandert_zijn_uitslag_niet(config: CheckConfig, bronnen: ExternalData) -> None:
    """De detectie blijft gelijk; er komt alleen een verwijzing bij."""
    outcome = uitkomst("EXT-001", config, bronnen)
    relaties = {finding.object_label: finding.details["waarde"] for finding in outcome.findings}

    assert relaties == {"1": "kruist", "4": "binnen", "P": "binnen", "Q": "binnen"}
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_checks_extern.py -k ext001 -q`
Expected: FAIL — `KeyError: 'object2_uri'`.

- [ ] **Step 3: Implementeer**

Bovenin `extern.py` erbij:

```python
from nlriochecker.checks.treffers import Treffer, bouw_sleutel

# Het URI-voorvoegsel per bron-rol; de sleutel wordt `<voorvoegsel>/<bron-id>`.
VOORVOEGSEL = {
    "bgt_pand": "bgt:pand",
    "bag_pand": "bag:pand",
    "bgt_bouwwerk": "bgt:bouwwerk",
    "bgt_water": "bgt:waterdeel",
}

MARKERING_ZONDER_ID = (
    "Een of meer geraakte objecten komen uit een bron zonder identificatie; die "
    "dragen een sleutel op grond van hun geometrie (`geo:...`) in plaats van hun "
    "bron-ID."
)
```

`_sterkste` geeft de geraakte vorm en attributen mee terug:

```python
    def _sterkste(self, geometrie, lagen, buffer: float):
        """De zwaarste relatie met een bouwwerk binnen de buffer.

        Levert `(relatie, afstand, laag, vorm, attributen)`. De vorm en de attributen
        zijn nodig om de treffer te registreren; de keuze zelf verandert er niet door,
        want de vergelijking blijft op `(volgorde, afstand)`.
        """
        beste = None
        for laag in lagen:
            for vorm, attributen in laag.nabij(geometrie, buffer):
                afstand = geometrie.distance(vorm)
                if afstand > buffer:
                    continue
                relatie = self._relatie(geometrie, vorm, afstand)
                kandidaat = (
                    RELATIE_VOLGORDE.index(relatie),
                    afstand,
                    relatie,
                    laag,
                    vorm,
                    attributen,
                )
                if beste is None or kandidaat[:2] < beste[:2]:
                    beste = kandidaat
        return None if beste is None else (beste[2], beste[1], beste[3], beste[4], beste[5])
```

In `run`, de lus:

```python
            relatie, afstand, laag, vorm, attributen = geraakt
            sleutel, terugval = bouw_sleutel(VOORVOEGSEL[laag.role], attributen, vorm)
            if terugval:
                self._zonder_id.add(laag.source.name)
            label = f"pand {sleutel.split('/')[-1]}"
            if laag.role == "bgt_bouwwerk":
                soort = attributen.get("type")
                label = f"bouwwerk {sleutel.split('/')[-1]}" + (f" ({soort})" if soort else "")
            context.treffers.registreer(
                Treffer(
                    sleutel=sleutel,
                    bron=laag.role,
                    label=label,
                    bronbestand=laag.source.name,
                    geometrie=vorm,
                    attributen=dict(attributen),
                ),
                check_id=self.id,
                object_uri=object_.uri,
                afstand_m=round(afstand, 3),
            )
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"Dit object {self._zin(relatie, afstand)} een bouwwerk uit "
                f"`{laag.source.name}` (laag {laag.layer}); buffer {buffer:g} m.",
                waarde=relatie,
                drempel=buffer,
                afstand_m=round(afstand, 3),
                bron=laag.source.name,
                laag=laag.layer,
                object2_uri=sleutel,
                object2_label=label,
            )
```

`self._zonder_id` is een `set[str]` die in `run` bovenaan geleegd wordt
(`self._zonder_id = set()`), en `notes()` voegt `MARKERING_ZONDER_ID` toe zodra hij
gevuld is:

```python
    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke pandbronnen gebruikt zijn, en of er ID's ontbraken."""
        ...  # bestaande body, en aan het eind:
        if getattr(self, "_zonder_id", set()):
            regels.append(MARKERING_ZONDER_ID)
        return regels
```

Let op: `notes()` draait na `run()` in `run_checks` (eerst `findings`, dan `notes`);
dat is de volgorde in de bestaande code en dus de reden dat dit werkt. Verifieer die
volgorde in `run_checks` voordat je hierop leunt.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_checks_extern.py -q`
Expected: PASS, inclusief de bestaande EXT-001-tests.

- [ ] **Step 4b: Verifieer dat geen bestaande test op lege object2-velden leunt**

Run:

```bash
grep -rn "object2" tests/ | grep -v test_checks_treffers
```

Expected: geen enkele assertie die eist dat `object2_uri` of `object2_label` leeg is
voor EXT-001 of EXT-003. Vind je er een, dan is dat een bewuste vastlegging van het
oude gedrag: pas hem aan en noem hem in de commitboodschap.

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "EXT-001 wijst het geraakte bouwwerk aan en registreert het"
```

---

## Task 4: EXT-003 wijst het geraakte waterdeel aan

**Files:**
- Modify: `src/nlriochecker/checks/extern.py`
- Test: `tests/test_checks_extern.py`

**Interfaces:**
- Consumes: `VOORVOEGSEL`, `Treffer`, `bouw_sleutel`, `context.treffers`
- Produces: EXT-003-bevindingen met gevulde object2-velden; treffers met bron
  `bgt_water`

- [ ] **Step 1: Schrijf de falende tests**

```python
def test_ext003_wijst_het_geraakte_waterdeel_aan(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    outcome = uitkomst("EXT-003", config, bronnen)

    verwijzingen = {
        (finding.details["object2_uri"], finding.details["object2_label"])
        for finding in outcome.findings
    }

    assert verwijzingen == {("bgt:waterdeel/water-1", "waterloop")}


def test_ext002_registreert_geen_treffer(config: CheckConfig, bronnen: ExternalData) -> None:
    """De laag volgt EXT-003; kruisingen met een duiker horen er bewust buiten."""
    dataset = load_dataset(SCENARIO)
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)

    run = run_checks(context, ["EXT-002"])

    assert len(run.treffers) == 0


def test_ext003_verandert_zijn_uitslag_niet(config: CheckConfig, bronnen: ExternalData) -> None:
    assert labels(uitkomst("EXT-003", config, bronnen)) == ["2"]
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_checks_extern.py -k ext003 -q`
Expected: FAIL — `KeyError: 'object2_uri'`.

- [ ] **Step 3: Implementeer**

`_WatergangKruising.kruisingen` geeft de geometrie mee terug:

```python
    def kruisingen(self, context: CheckContext):
        """De strengen die een waterdeel raken, met het waterdeel erbij.

        Levert `(conduit, geometrie, rij, laag, buffer)`. De geometrie is nodig om de
        treffer te registreren; de detectie verandert niet -- ook de `break` na het
        eerste gevonden waterdeel per streng blijft staan (zie de beslislog).
        """
        laag = self.laag(context)
        if laag is None:
            return
        buffer = context.config.drempels.ext_watergang_buffer_m
        for conduit in self.selectie(context).toetsbaar:
            for geometrie, rij in laag.nabij(conduit.line, buffer):
                if conduit.line.distance(geometrie) > buffer:
                    continue
                yield conduit, geometrie, rij, laag, buffer
                break
```

`KruisingMetWatergang.run` (EXT-002) past alleen zijn uitpakking aan
(`for conduit, _vorm, rij, laag, buffer in self.kruisingen(context):`) en registreert
niets.

`KruisingZonderZinkerOfDuiker.run` (EXT-003):

```python
        for conduit, vorm, rij, laag, buffer in self.kruisingen(context):
            if any(dataset.is_a(conduit.uri, wortel) for wortel in wortels):
                continue
            soort = rij.get("type") or "waterdeel"
            sleutel, terugval = bouw_sleutel(VOORVOEGSEL["bgt_water"], rij, vorm)
            if terugval:
                self._zonder_id.add(laag.source.name)
            context.treffers.registreer(
                Treffer(
                    sleutel=sleutel,
                    bron="bgt_water",
                    label=str(soort),
                    bronbestand=laag.source.name,
                    geometrie=vorm,
                    attributen=dict(rij),
                ),
                check_id=self.id,
                object_uri=conduit.uri,
            )
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Kruist een BGT-waterdeel ({soort}) maar staat niet geregistreerd als "
                f"{' or '.join(wortels) or 'kruisingsconstructie'}.",
                watertype=soort,
                buffer_m=buffer,
                object2_uri=sleutel,
                object2_label=str(soort),
            )
```

Let op: de bestaande boodschap gebruikt `' of '.join(wortels)` (Nederlands). Neem hem
letterlijk over uit de huidige code; de tekst mag niet veranderen.

`notes()` van EXT-003 krijgt dezelfde `_zonder_id`-regel als EXT-001.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_checks_extern.py -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "EXT-003 wijst het geraakte waterdeel aan en registreert het"
```

---

## Task 5: De twee lagen in de GeoPackage

**Files:**
- Modify: `src/nlriochecker/uitvoer/gpkg.py`
- Create: `src/nlriochecker/uitvoer/stijlen/bouwwerken.qml`,
  `src/nlriochecker/uitvoer/stijlen/waterdelen_zonder_zinker.qml`
- Test: `tests/test_uitvoer_gpkg.py`

**Interfaces:**
- Consumes: `CheckRun.treffers` (taak 2), gevulde object2-velden (taken 3 en 4)
- Produces: featurelagen `bouwwerken` en `waterdelen_zonder_zinker`;
  `_LaagTellingen` met de velden `bouwwerken` en `waterdelen`

- [ ] **Step 1: Schrijf de falende tests**

```python
def _ext_run():
    """Een run op de EXT-scenariofixture met de miniatuurbronnen."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    basis = config.bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": "bag_pand.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    bronnen = load_external_data(basis, GIS_DIR / "ext")
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)
    return run_checks(context, ["EXT-001", "EXT-002", "EXT-003"])


def _rijen(pad: Path, laag: str) -> list[dict]:
    """De rijen van een laag als dicts, zonder de geometrie."""
    con = sqlite3.connect(pad)
    con.row_factory = sqlite3.Row
    try:
        return [
            {k: rij[k] for k in rij.keys() if k not in {"geom", "fid"}}
            for rij in con.execute(f'select * from "{laag}"')
        ]
    finally:
        con.close()


def test_bouwwerkenlaag_is_exact_de_verzameling_uit_de_meldingen(tmp_path: Path) -> None:
    """De kerntest: niets erbij, niets eraf."""
    run = _ext_run()
    meldingen = bouw_meldingen(run, RUNDATUM)
    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verwacht = {m.object2_uri for m in meldingen if m.check_id == "EXT-001"}
    assert {rij["id"] for rij in _rijen(pad, "bouwwerken")} == verwacht


def test_bouwwerk_wordt_ontdubbeld_met_de_sterkste_relatie(tmp_path: Path) -> None:
    """Vier objecten raken hetzelfde pand: een rij, vier meldingen, binnen wint."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rijen = _rijen(pad, "bouwwerken")

    assert len(rijen) == 1
    assert rijen[0]["id"] == "bgt:pand/pand-1"
    assert rijen[0]["bron"] == "bgt_pand"
    assert rijen[0]["aantal_meldingen"] == 4
    assert rijen[0]["relatie"] == "binnen"
    assert rijen[0]["afstand_min_m"] == 0.0
    assert rijen[0]["check_ids"] == "EXT-001"
    assert rijen[0]["bronbestand"] == "bgt.gpkg"


def test_waterdelenlaag_volgt_ext003_en_niet_ext002(tmp_path: Path) -> None:
    """Streng 3 kruist water-2 met een duiker; dat waterdeel hoort er niet in."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rijen = _rijen(pad, "waterdelen_zonder_zinker")

    assert [rij["id"] for rij in rijen] == ["bgt:waterdeel/water-1"]
    assert rijen[0]["watertype"] == "waterloop"
    assert rijen[0]["aantal_meldingen"] == 1
    assert rijen[0]["buffer_m"] == load_check_config().drempels.ext_watergang_buffer_m


def test_lege_lagen_bestaan_en_zijn_geregistreerd(tmp_path: Path) -> None:
    """Een run zonder EXT-treffers heeft beide lagen, leeg, met stijl."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)
    con = sqlite3.connect(pad)
    try:
        for laag in ("bouwwerken", "waterdelen_zonder_zinker"):
            assert con.execute(f'select count(*) from "{laag}"').fetchone()[0] == 0
            geregistreerd = con.execute(
                "select count(*) from gpkg_contents where table_name = ?", (laag,)
            ).fetchone()[0]
            gestyled = con.execute(
                "select count(*) from layer_styles where f_table_name = ?", (laag,)
            ).fetchone()[0]
            assert (geregistreerd, gestyled) == (1, 1)
    finally:
        con.close()
```

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k "bouwwerk or waterdelen or lege_lagen" -q`
Expected: FAIL — `sqlite3.OperationalError: no such table: bouwwerken`.

- [ ] **Step 3: Implementeer**

In `gpkg.py`:

```python
FEATURELAGEN = (
    "putten",
    "strengen",
    "meldinglocaties",
    "mechanisch_riool",
    "bouwwerken",
    "waterdelen_zonder_zinker",
)

# De relaties van EXT-001, van zwaar naar licht; de laag toont de sterkste over de
# verwijzende meldingen.
RELATIE_STERKTE = ("binnen", "kruist", "nabij")
```

`_LaagTellingen` krijgt `bouwwerken: int` en `waterdelen: int`.
`schrijf_geopackage` opent met `start_fase("GeoPackage", 10)`.

Nieuwe functie, aangeroepen vanuit `_schrijf_features` na `_schrijf_meldinglocaties`:

```python
def _schrijf_treffers(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    voortgang: Voortgang,
) -> tuple[int, int]:
    """Schrijft de externe objecten waarnaar de EXT-meldingen verwijzen.

    Strikte aansluiting: de rijen komen uit de meldingen van déze uitvoer, gejoind op
    het trefferregister van de run. De schrijver bevraagt geen externe bron en doet
    geen ruimtelijke selectie, dus laag en testuitkomst kunnen niet uit elkaar lopen.
    Bij rapportage per gebied betekent dat vanzelf: alleen de treffers van dit gebied.
    """
```

De opbouw per laag: groepeer de meldingen op `object2_uri`, sla lege sleutels over,
zoek de treffer met `run.treffers.get(sleutel)` en sla een sleutel zonder treffer over
(dat kan alleen bij een handmatig samengestelde `CheckRun`). Kolommen:

```python
def _bouwwerk_kolommen() -> list[_Kolom]:
    return [
        _Kolom("id", "text"),
        _Kolom("bron", "text"),
        _Kolom("bronbestand", "text"),
        _Kolom("label", "text"),
        _Kolom("relatie", "text"),
        _Kolom("afstand_min_m", "real"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("check_ids", "text"),
    ]


def _waterdeel_kolommen() -> list[_Kolom]:
    return [
        _Kolom("id", "text"),
        _Kolom("watertype", "text"),
        _Kolom("bronbestand", "text"),
        _Kolom("label", "text"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("check_ids", "text"),
        _Kolom("buffer_m", "real"),
    ]
```

Per rij:

- `relatie` = de sterkste `melding.waarde` volgens `RELATIE_STERKTE`;
- `afstand_min_m` = het minimum van
  `run.treffers.afstand(sleutel, m.check_id, m.object_uri)` over de verwijzende
  meldingen, of `None` als geen enkele een afstand heeft;
- `aantal_meldingen` = het aantal verwijzende meldingen;
- `check_ids` = `", ".join(sorted({m.check_id for m in verwijzend}))`;
- `watertype` = `treffer.label`;
- `buffer_m` = `config.drempels.ext_watergang_buffer_m` (runbrede waarde, geen
  meldingveld — zie de spec).

Beide lagen worden altijd aangemaakt met `_maak_featurelaag(..., "MULTIPOLYGON", ...)`
en krijgen `_zet_omhullende(...)` op de geschreven geometrieën.

Twee QML's naar het patroon van `mechanisch_riool.qml`:

```xml
<!-- Default-stijl voor de bouwwerken waar EXT-001 over meldt: rode omlijning en een
     doorzichtige vulling, zodat de riolering eronder zichtbaar blijft. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="singleSymbol" forceraster="0" symbollevels="0">
    <symbols>
      <symbol type="fill" name="0" alpha="1">
        <layer class="SimpleFill">
          <prop k="color" v="215,48,39,0"/>
          <prop k="outline_color" v="215,48,39,255"/>
          <prop k="outline_width" v="0.4"/>
          <prop k="style" v="no"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <legend type="default-vector"/>
</qgis>
```

en dezelfde met `33,102,172` (`#2166ac`) voor `waterdelen_zonder_zinker.qml`.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -q && uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "De GeoPackage krijgt de geraakte bouwwerken en waterdelen als laag"
```

---

## Task 6: De nabij-relatie, de geo-terugval en het multi-gebiedgeval

**Files:**
- Modify: `tests/gpkghelper.py`, `tests/test_uitvoer_gpkg.py`
- Test: `tests/test_uitvoer_gpkg.py`

**Interfaces:**
- Consumes: alles uit de taken 1 tot en met 5
- Produces: `schrijf_vlakken(pad, laag, vlakken, kolom=None) -> Path` in
  `tests/gpkghelper.py`, waarmee een BGT-achtige laag met vrije attributen te
  schrijven is

- [ ] **Step 1: Breid de fixturehulp uit**

```python
def schrijf_vlakken(
    pad: Path,
    laag: str,
    vlakken: list[tuple[dict[str, str], BaseGeometry]],
    kolommen: tuple[str, ...] = ("lokaal_id",),
) -> Path:
    """Schrijft een vlakkenlaag met vrije tekstkolommen.

    Voor de EXT-tests: een BGT-achtige laag met of juist zonder `lokaal_id`, zodat
    zowel de gewone sleutel als de terugval op de geometriehash te toetsen is.
    """
```

De implementatie volgt `schrijf_buurten` in hetzelfde bestand: `gpkg_contents`,
`gpkg_geometry_columns`, een tabel met `fid`, de kolommen en `geom`, en de
`GP`-kopbytes voor EPSG:28992. Meerdere lagen in één bestand schrijven moet mogelijk
zijn (de functie voegt toe aan een bestaand bestand als het er al is).

- [ ] **Step 2: Schrijf de falende tests**

```python
def _bronnen_met_pand(map_pad: Path, vlakken, kolommen=("lokaal_id",)) -> ExternalData:
    """Miniatuurbronnen met een zelfgekozen pandenlaag, zonder dekkingspoort."""
    schrijf_vlakken(map_pad / "bgt.gpkg", "pand", vlakken, kolommen)
    schrijf_vlakken(
        map_pad / "studiegebied.gpkg",
        "studiegebied",
        [({"lokaal_id": "gebied"}, box(990, 1985, 1100, 2015))],
    )
    basis = load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
        }
    )
    return load_external_data(basis, map_pad)


def test_nabij_geval_komt_in_de_laag(tmp_path: Path) -> None:
    """Een pand op 0,5 m van streng 1 en knoop A: geen raakvlak, wel binnen de buffer."""
    bronnen = _bronnen_met_pand(
        tmp_path / "bron", [({"lokaal_id": "p-nabij"}, box(1000, 2000.5, 1010, 2005))]
    )
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config, bronnen=bronnen), ["EXT-001"])

    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path / "uit", RUNDATUM)
    rijen = _rijen(pad, "bouwwerken")

    assert [rij["id"] for rij in rijen] == ["bgt:pand/p-nabij"]
    assert rijen[0]["relatie"] == "nabij"
    assert rijen[0]["aantal_meldingen"] == 2
    assert rijen[0]["afstand_min_m"] == 0.5


def test_bron_zonder_id_levert_een_geo_sleutel(tmp_path: Path) -> None:
    bronnen = _bronnen_met_pand(
        tmp_path / "bron",
        [({"soort": "pand"}, box(1000, 2000.5, 1010, 2005))],
        kolommen=("soort",),
    )
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config, bronnen=bronnen), ["EXT-001"])

    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path / "uit", RUNDATUM)
    rijen = _rijen(pad, "bouwwerken")

    assert rijen[0]["id"].startswith("geo:")
    assert any("geo:" in note for note in run.outcomes[0].notes)


def test_geo_sleutel_is_stabiel_over_runs(tmp_path: Path) -> None:
    """Twee identieke runs moeten dezelfde sleutel opleveren."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    sleutels = []
    for naam in ("een", "twee"):
        bronnen = _bronnen_met_pand(
            tmp_path / naam,
            [({"soort": "pand"}, box(1000, 2000.5, 1010, 2005))],
            kolommen=("soort",),
        )
        run = run_checks(CheckContext(dataset=dataset, config=config, bronnen=bronnen), ["EXT-001"])
        sleutels.append({f.details["object2_uri"] for f in run.findings})

    assert sleutels[0] == sleutels[1]
```

Plus de multi-gebiedtest in `tests/test_toetsloop.py`:

```python
def _rijen_van(pad: Path, laag: str) -> list[str]:
    """De id-kolom van een laag in een GeoPackage."""
    con = sqlite3.connect(pad)
    try:
        return [rij[0] for rij in con.execute(f'select id from "{laag}"')]
    finally:
        con.close()


def test_treffers_blijven_bij_hun_eigen_gebied(tmp_path: Path) -> None:
    """Een pand dat alleen vanuit Noord geraakt wordt, hoort niet in de uitvoer van Zuid.

    Dat volgt uit de strikte aansluiting: de laag komt uit de meldingen van dat
    gebied, niet uit het register.
    """
    bron = tmp_path / "bron"
    bron.mkdir()
    schrijf_vlakken(
        bron / "bgt.gpkg", "pand", [({"lokaal_id": "p-noord"}, box(1000, 2000.5, 1010, 2005))]
    )
    schrijf_vlakken(
        bron / "studiegebied.gpkg",
        "studiegebied",
        [({"lokaal_id": "g"}, box(990, 1985, 1160, 2015))],
    )
    config = _config()
    bronnen = load_external_data(
        config.bronnen.model_copy(
            update={
                "map": ".",
                "bgt": "bgt.gpkg",
                "bag_pand": None,
                "nwb_wegvakken": None,
                "studiegebied": "studiegebied.gpkg",
                "ahn_dtm": None,
                "bgt_pandlagen": ["pand"],
            }
        ),
        bron,
    )
    gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")

    runs = toets_gebieden(
        load_dataset(TTL_DIR / "ext_scenario.ttl"),
        gebieden,
        config,
        bronnen=bronnen,
        check_ids=["EXT-001"],
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM)

    noord = next((tmp_path / "uit" / "noord").glob("*.gpkg"))
    zuid = next((tmp_path / "uit" / "zuid").glob("*.gpkg"))

    assert _rijen_van(noord, "bouwwerken") == ["bgt:pand/p-noord"]
    assert _rijen_van(zuid, "bouwwerken") == []
```

Het pand ligt op `box(1000, 2000.5, 1010, 2005)`, dus binnen de noordelijke buurt
`box(990, 1990, 1060, 2010)` en buiten `box(1060, 1990, 1160, 2010)` uit
`buurten_twee.gpkg`. Zorg dat `sqlite3`, `box`, `schrijf_vlakken`,
`load_external_data` en `Meetbereik` in dat testbestand geïmporteerd zijn.

- [ ] **Step 3: Draai en zie falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k "nabij or geo_sleutel" -q`
Expected: FAIL — `schrijf_vlakken` bestaat nog niet.

- [ ] **Step 4: Implementeer `schrijf_vlakken` en laat de tests slagen**

Run: `uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Tests voor de nabij-relatie, de geo-terugval en de treffers per gebied"
```

---

## Task 7: De dekkingspoort op de externe bronnen

**Files:**
- Modify: `src/nlriochecker/externedata.py`, `src/nlriochecker/checkconfig.py`,
  `src/nlriochecker/cli.py`
- Test: `tests/test_externedata_dekking.py`

**Interfaces:**
- Produces:
  - `class Dekkingseis(NamedTuple)` met `marge_m: float` en `tolerantie_m: float` in
    `externedata.py`
  - `load_external_data(bronnen, wortel=None, *, dekkingseis: Dekkingseis | None = None)`
  - `ExternalSources.dekking_tolerantie_m: float = 0.0`
  - `DrempelOptions.ext_zoekafstand_max_m` (property): het maximum van
    `ext_pand_buffer_m`, `ext_watergang_buffer_m`, `ext_putdeksel_afstand_m`,
    `ext_lozingspunt_water_afstand_m` en `ext_perceel_buffer_m`

- [ ] **Step 1: Schrijf de falende tests**

```python
"""Tests voor de dekkingspoort op de externe bronnen."""

from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import box

from gpkghelper import schrijf_vlakken
from nlriochecker.checkconfig import load_check_config
from nlriochecker.externedata import Dekkingseis, ExternalDataError, load_external_data

GEBIED = box(0, 0, 100, 100)


def _bronnen(map_pad: Path, panden: list, met_gebied: bool = True):
    """Schrijft een miniatuurbron met een pandenlaag en een bereik."""
    map_pad.mkdir(parents=True, exist_ok=True)
    schrijf_vlakken(
        map_pad / "bgt.gpkg",
        "pand",
        [({"lokaal_id": f"p{i}"}, vlak) for i, vlak in enumerate(panden)],
    )
    if met_gebied:
        schrijf_vlakken(
            map_pad / "studiegebied.gpkg", "studiegebied", [({"lokaal_id": "g"}, GEBIED)]
        )
    return load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": "studiegebied.gpkg" if met_gebied else None,
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
        }
    )


def test_te_kleine_laag_faalt_met_beide_omhullenden(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)])

    with pytest.raises(ExternalDataError) as fout:
        load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    tekst = str(fout.value)
    assert "bgt_pand" in tekst and "10" in tekst and "tekort" in tekst


def test_dekkende_laag_slaagt(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(-10, -10, 110, 110)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_pand") is not None


def test_marge_vraagt_dekking_buiten_het_bereik(tmp_path: Path) -> None:
    """Een laag die exact op het bereik geknipt is dekt de zoekafstand niet."""
    bronnen = _bronnen(tmp_path / "b", [GEBIED])

    with pytest.raises(ExternalDataError):
        load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(10.0, 0.0))


def test_tolerantie_laat_een_klein_tekort_toe(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(2, 2, 98, 98)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 5.0))

    assert data.layer("bgt_pand") is not None


def test_gat_middenin_slaagt(tmp_path: Path) -> None:
    """De gedocumenteerde beperking: bbox-dekking ziet geen gat in het extract."""
    bronnen = _bronnen(tmp_path / "b", [box(0, 0, 20, 100), box(80, 0, 100, 100)])

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_pand") is not None


def test_zonder_bereik_draait_de_poort_niet(tmp_path: Path) -> None:
    """Zonder bereik geeft geen enkele EXT-check een uitslag; er valt niets te maskeren."""
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)], met_gebied=False)

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.extent is None


def test_ontbrekende_laag_raakt_de_poort_niet(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(-10, -10, 110, 110)]).model_copy(
        update={"bgt_waterlagen": ["waterdeel"]}
    )

    data = load_external_data(bronnen, tmp_path / "b", dekkingseis=Dekkingseis(0.0, 0.0))

    assert data.layer("bgt_water") is None


def test_zonder_dekkingseis_geen_poort(tmp_path: Path) -> None:
    bronnen = _bronnen(tmp_path / "b", [box(10, 10, 90, 90)])

    assert load_external_data(bronnen, tmp_path / "b").layer("bgt_pand") is not None
```

Plus een rastertest die met `rasterio` een raster van 20 x 20 m op (0,0) schrijft en
vaststelt dat het met `Dekkingseis(0.0, 0.0)` faalt; volg `_schrijf_raster` in
`scripts/maak_gis_fixtures.py` voor de aanroep.

- [ ] **Step 2: Draai en zie falen**

Run: `uv run pytest tests/test_externedata_dekking.py -q`
Expected: FAIL — `cannot import name 'Dekkingseis'`.

- [ ] **Step 3: Implementeer**

In `checkconfig.py`, in `ExternalSources`:

```python
    # Hoeveel een aangeleverde laag kleiner mag zijn dan het bereik waarvoor je hem
    # geldig verklaart, voordat het laden faalt. Nul is streng. De bbox van een laag
    # is de omhullende van zijn *features*: een dunne laag met een lege rand is niet
    # te onderscheiden van een afgeknipt extract, en die afweging hoort in het
    # project thuis en niet in de code. Zie BO-19 in de beslislog.
    dekking_tolerantie_m: float = Field(default=0.0, ge=0.0)
```

en in `DrempelOptions`:

```python
    @property
    def ext_zoekafstand_max_m(self) -> float:
        """De verste blik van de EXT-checks in de externe lagen.

        De dekkingspoort verruimt het bereik hiermee: een pand net buiten het bereik
        telt mee voor een object er net binnen. Bewust niet de contextschil -- die
        hoort bij de afbakening van de GWSW-analyse, niet bij het zoekbereik hier.
        """
        return max(
            self.ext_pand_buffer_m,
            self.ext_watergang_buffer_m,
            self.ext_putdeksel_afstand_m,
            self.ext_lozingspunt_water_afstand_m,
            self.ext_perceel_buffer_m,
        )
```

In `externedata.py`:

```python
class Dekkingseis(NamedTuple):
    """Hoe ver buiten het bereik de checks kijken, en welk tekort toegestaan is."""

    marge_m: float
    tolerantie_m: float


def _toets_dekking(data: ExternalData, eis: Dekkingseis) -> None:
    """Weigert bronnen die kleiner zijn dan het bereik waarvoor ze gelden.

    Een extract dat maar een deel van het bereik dekt geeft een misleidend schone
    uitkomst: geen treffer leest als geen probleem, terwijl de bron er domweg niet
    was. Daarom is dit een fout en geen waarschuwing.

    Wat deze poort *niet* kan: bbox-dekking is noodzakelijk maar niet voldoende. Een
    gat midden in het extract valt er niet mee op, en een tekort op een dunne laag
    betekent "hier staan geen features", niet per se "extract afgeknipt". De
    `binnen_bereik`-notities per object blijven het tweede vangnet. Zonder bereik
    draait deze poort niet: dan geeft geen enkele EXT-check een uitslag.
    """
```

De regel: `referentie = _verruim(data.extent.bounds, eis.marge_m)` voor vectorlagen en
`_verruim(data.extent.bounds, 0.0)` voor het raster; per bron het tekort per zijde
berekenen (`max(0.0, referentie.min_x - bron.min_x)` enzovoort), en falen zodra een
tekort groter is dan `eis.tolerantie_m`. De foutmelding somt per falende bron de
beide omhullenden op plus het tekort per zijde in meters, en noemt
`dekking_tolerantie_m` als de knop om aan te draaien.

`load_external_data` roept hem aan vlak voor het teruggeven van `ExternalData`, alleen
als `dekkingseis is not None` en `data.extent is not None`.

In `cli.py`, in `_externe_bronnen`:

```python
    bronnen = config.bronnen.model_copy(update={"map": "."})
    eis = Dekkingseis(
        marge_m=config.drempels.ext_zoekafstand_max_m,
        tolerantie_m=config.bronnen.dekking_tolerantie_m,
    )
    return load_external_data(bronnen, bronnen_dir, dekkingseis=eis)
```

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest -q`
Expected: PASS

- [ ] **Step 5: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Dekkingspoort op de externe bronnen bij het laden"
```

---

## Task 8: Zware integratietest en documentatie

**Files:**
- Modify: `tests/test_integration.py`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`,
  `docs/json-schema.md`, `docs/beslislog.md`

- [ ] **Step 1: Zware integratietest**

Onder `@pytest.mark.zwaar`, met de echte De Wolden-data en `data/gis`: draai EXT-001
en EXT-003 met een studiegebied, schrijf de GeoPackage en stel vast dat het aantal
rijen in beide lagen gelijk is aan het aantal unieke `object2_uri`'s in de meldingen
van de betreffende check. Geef `dekkingseis=None` mee, of zet
`dekking_tolerantie_m` in de testconfig op 300, want de echte extracten komen tot
276 m tekort (zie de spec, feit 10).

- [ ] **Step 2: `docs/beslislog.md` — drie vermeldingen**

BO-17 strikte aansluiting: de lagen volgen de meldingenstroom, inclusief de twee
geërfde beperkingen (EXT-001 meldt alleen het sterkste bouwwerk; `kruisingen()` breekt
af na het eerste waterdeel) met de verruiming als benoemde, niet geplande optie.
BO-18 de object2-URI-conventie en de terugval op de geometriehash.
BO-19 de dekkingspoort: waarom een harde fout hier niet botst met "externe data is
context, geen poort", waarom de referentie `bronnen.studiegebied` is en niet het
studiegebied van de run, en waarom er een geconfigureerde tolerantie is (met de
gemeten tekorten uit de spec).

- [ ] **Step 3: `docs/json-schema.md`**

De gevulde `object2_uri` en `object2_label` voor EXT-001 en EXT-003, de URI-conventies
per bron, de `geo:`-terugval, en dat de treffergeometrieën niet in de JSON zitten maar
in de GeoPackage.

- [ ] **Step 4: `README.md` en `CLAUDE.md`**

README: de twee lagen bij de uitvoerbeschrijving; de dekkingseis en
`dekking_tolerantie_m` bij de invoerbeschrijving, met de aantekening dat `data/gis`
een tolerantie van circa 300 m nodig heeft en waarom.
CLAUDE.md: de GeoPackage-beschrijving aanvullen met de twee lagen, in dezelfde toon en
dichtheid als de bestaande tekst.

- [ ] **Step 5: `CHANGELOG.md` onder `## [Unreleased]`**

Rubriek Toegevoegd (de twee lagen, de gevulde object2-velden, de dekkingspoort) en
Gewijzigd (de API-uitbreidingen: `load_external_data` met `dekkingseis`,
`CheckContext.treffers`, `CheckRun.treffers`, `kruisingen()` levert een tupel van vijf).

- [ ] **Step 6: Poort en commit**

```bash
uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q
git add -A && git commit -m "Ronde 3 vastgelegd: leeswijzer, beslislog, schema en wijzigingslog"
```

---

## Task 9: Reviewstappen

- [ ] **Step 1:** `/superpowers:requesting-code-review` en de bevindingen verwerken.
- [ ] **Step 2:** `/python-library-complete:reviewing-python-libraries` en de
      bevindingen verwerken.
- [ ] **Step 3:** Kwaliteitspoort schoon, de zware tests draaien, afsluitende commit.
      Versienummer niet ophogen.
