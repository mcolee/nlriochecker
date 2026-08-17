# Uitvoer ronde 2: implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De GIS-uitvoer leesbaar en zelfverklarend maken, en een run op een enkel dorp van vier minuten terugbrengen naar seconden, zonder dat de checks er valse bevindingen door geven.

**Architecture:** Alle uitvoervormen blijven uit een enkele meldingenstroom komen; de wijzigingen zitten in `uitvoer/` (kolommen, lagen, stijlen) en in een nieuwe afbakeningslaag die vóór de checks een analyseset bouwt (kern plus contextschil) en een cache die het inlezen overslaat. Het checkregister gaat naar v0.8 en blijft de bron van waarheid: contractwijzigingen gaan daar eerst in.

**Tech Stack:** Python 3.12, uv, pytest, ruff, sqlite3 (stdlib), shapely, networkx, rdflib, pydantic, click. QGIS/PyQGIS alleen in een optionele smoketest.

**Spec:** `docs/superpowers/specs/2026-08-16-uitvoer-ronde2-design.md`

## Global Constraints

- Python 3.12+, src-layout, beheer met uv. Geen nieuwe afhankelijkheden: pandas, click, pydantic, rdflib, shapely, networkx en de standaardbibliotheek zijn alles.
- Nederlandse docstrings, Engelse code-identifiers, type hints overal.
- Na elke wijziging: `uv run pytest` en `uv run ruff check` plus `uv run ruff format --check`. Beide groen voordat je commit.
- Elke taak eindigt met een commit. Commitboodschappen in het Nederlands, in de gebiedende of beschrijvende vorm zoals de bestaande historie (`git log --oneline`).
- Geen enkele drempelwaarde in de code: alles wat een getal is dat een project mag verleggen, hoort in `src/nlriochecker/checks.toml` en in het pydantic-model in `checkconfig.py`.
- Check-ID's zijn stabiel; een vervallen ID wordt nooit hergebruikt.
- Wat een check niet bekeken heeft, hoort in het rapport. Zwijgen leest als "alles gecontroleerd".
- De uitvoermap `uitvoer/` staat met een leidende slash in `.gitignore`; de package `src/nlriochecker/uitvoer/` staat wél onder versiebeheer. Controleer na elke taak die daar bestanden toevoegt met `git status` dat de nieuwe bestanden gezien worden.
- Draai zware tests niet standaard mee: `pytest -m "not zwaar"` is de gewone gang; nieuwe zware tests krijgen `@pytest.mark.zwaar`.

## Bestandsindeling

| Bestand | Verantwoordelijkheid | Taak |
|---|---|---|
| `data/checkregister-gwsw-nulmeting-v0_8.md` | nieuw; het contract | 1, 2, 3 |
| `src/nlriochecker/uitvoer/gpkg.py` | GeoPackage-schrijver: lagen, kolommen, stijlregistratie | 4, 5, 6, 7, 8, 10 |
| `src/nlriochecker/uitvoer/stijlen/*.qml` | de meegeleverde QGIS-stijlen | 6, 7, 8 |
| `src/nlriochecker/uitvoer/melding.py` | de meldingenstroom; nieuwe velden `object_id`, `object2_id` | 5 |
| `src/nlriochecker/uitvoer/identiteit.py` | melding-ID plus de nieuwe `kort()` | 5 |
| `src/nlriochecker/uitvoer/bevindingen.py` | Markdown en CSV | 5, 10 |
| `src/nlriochecker/checks/extern.py` | EXT-checks | 2, 3 |
| `src/nlriochecker/dataset.py` | `Conduit.bob_verval`, `GwswDataset.richting_van_geometrie()`, `GwswDataset.subset()` | 7, 9 |
| `src/nlriochecker/afbakening.py` | nieuw; kern, contextschil, analyseset | 9 |
| `src/nlriochecker/cache.py` | nieuw; de geparseerde dataset bewaren | 11 |
| `src/nlriochecker/checks/base.py` | `volledig_bereik` op `Check`; `objecten_in_gebied` verhuist | 9, 10 |
| `src/nlriochecker/checkconfig.py` | `klassen.mechanisch`, sectie `[studiegebied]` | 2, 6, 9 |
| `src/nlriochecker/cli.py` | de nieuwe opties en de meldingen op stdout | 10, 11 |

---

### Taak 1: Checkregister v0.8 en de versieverwijzingen

Het register is de bron van waarheid; contractwijzigingen gaan daar eerst in. Deze taak
maakt het bestand en zet alle verwijzingen om, nog zonder inhoudelijke checkwijziging, zodat
de suite groen blijft en de volgende taken een plek hebben om hun regel aan te passen.

**Files:**
- Create: `data/checkregister-gwsw-nulmeting-v0_8.md` (kopie van v0.7 plus de wijzigingen hieronder)
- Create: `tests/test_register_versie.py`
- Modify: `src/nlriochecker/register.py` (docstring regel 3, `default_register_path()` regel 148-150)
- Modify: `src/nlriochecker/dekking.toml` (regels 9-10)
- Modify: `src/nlriochecker/checks.toml` (`[rapport] register_versie`)
- Modify: `tests/test_checks_registry.py` (regel 12)

**Interfaces:**
- Consumes: niets uit eerdere taken.
- Produces: `data/checkregister-gwsw-nulmeting-v0_8.md` met de sectie `## Afbakening van een analyse` en de tabel `## Vervallen checks (niet relevant voor deze toepassing)`; taken 2 en 3 vullen die verder.

- [ ] **Step 1: Schrijf de falende test**

Maak `tests/test_register_versie.py`:

```python
"""Bewaakt dat elke verwijzing naar de registerversie dezelfde versie noemt.

De versie staat op vijf plekken: het registerbestand zelf, de dekkingmapping (twee
velden), de checkconfig en het pad in `register.py`. Loopt een van de vijf achter,
dan faalt `verify_register()` of rapporteert de uitvoer een versie waaraan niet
getoetst is.
"""

from __future__ import annotations

from nlriochecker.checkconfig import load_check_config
from nlriochecker.config import load_coverage_config
from nlriochecker.register import default_register_path, load_register

VERWACHTE_VERSIE = "0.8"


def test_registerbestand_bestaat_en_draagt_de_versie() -> None:
    pad = default_register_path()

    assert pad.exists(), f"{pad} bestaat niet"
    assert pad.name == f"checkregister-gwsw-nulmeting-v0_{VERWACHTE_VERSIE[-1]}.md"
    assert load_register(pad).version == VERWACHTE_VERSIE


def test_dekkingmapping_wijst_naar_dezelfde_versie() -> None:
    config = load_coverage_config()

    assert config.checkregister_versie == VERWACHTE_VERSIE
    assert config.bron.endswith(f"v0_{VERWACHTE_VERSIE[-1]}.md")


def test_checkconfig_rapporteert_dezelfde_versie() -> None:
    assert load_check_config().rapport.register_versie == f"v{VERWACHTE_VERSIE}"
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_register_versie.py -v`
Verwacht: FAIL — `default_register_path()` wijst nog naar v0.7.

- [ ] **Step 3: Maak het registerbestand**

```bash
cp data/checkregister-gwsw-nulmeting-v0_7.md data/checkregister-gwsw-nulmeting-v0_8.md
```

Wijzig in het nieuwe bestand de tweede regel (de versieregel onder de titel) zodat hij begint met:

```
Versie 0.8, werkdocument (afbakening tot een studiegebied toegevoegd d.d. 2026-08-16; EXT-008 vervallen).
```

Laat de rest van die alinea staan.

- [ ] **Step 4: Voeg de sectie over afbakening toe**

Zet deze sectie direct vóór `## TOP: Topologie en geometrie`:

```markdown
## Afbakening van een analyse

Een toets kan tot een studiegebied beperkt worden. De pijplijn analyseert dan niet de
volledige export en ook niet alleen het gebied zelf, maar een analyseset:

- **kern** — de objecten waarvan de geometrie het studiegebied raakt; hierover, en alleen
  hierover, wordt gerapporteerd;
- **contextschil** — de samenhangende vrijvervalcomponenten die de kern raken, plus alle
  objecten binnen een instelbare buffer om het gebied.

De component is nodig omdat NET-001, NET-002, NET-004, NET-005 en NET-006 over een
samenhangend net redeneren: zonder de rest van de component zou een streng die het gebied
uit loopt ten onrechte als doodlopend gelden. De buffer is nodig voor de checks die naar
nabijheid kijken zonder netwerkverband: TOP-005, TOP-006, TOP-010, TOP-011, TOP-021 en de
EXT-checks. Mechanische leidingen doen bewust niet mee aan de component; ze verbinden
deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen, terwijl de
NET-checks ze niet volgen.

Checks die over de hele populatie gaan in plaats van over losse objecten — ADM-002, unieke
identificaties — draaien altijd op de volledige export. Welke dat zijn is configureerbaar.
Het rapport meldt per run hoeveel objecten er in de kern zitten, hoeveel in de schil en
hoeveel de export in totaal telt.

Mechanische riolering (persleiding, drukleiding, vacuumleiding) blijft buiten scope, zoals
de inleiding al zegt. In de GIS-uitvoer staat ze in een eigen laag met de aanduiding
"Mechanisch riool: niet geanalyseerd", zodat een leeg kaartbeeld daar niet als "geen
gebreken" leest.
```

- [ ] **Step 5: Voeg de tabel met vervallen checks toe**

Zet deze sectie direct ná de tabel `## Geschrapte checks (gedekt door GWSW-nulmeting)` en vóór `## Open punten`:

```markdown
## Vervallen checks (niet relevant voor deze toepassing)

Anders dan de geschrapte checks hierboven zijn deze niet door de nulmeting gedekt; er
kijkt niets meer naar. Ze zijn vervallen omdat ze voor deze opdracht geen bruikbare
uitkomst geven. De ID's worden niet hergebruikt.

| ID | Check | Vervallen in | Reden |
|---|---|---|---|
```

De rij zelf volgt in taak 2; de tabel blijft nu leeg onder de kop.

- [ ] **Step 6: Voeg de versiehistorie toe**

Zet dit als eerste alinea onder `## Versiehistorie`:

```markdown
Versie 0.8 (2026-08-16): EXT-008 vervallen (BAG-verblijfsobjecten zijn voor deze opdracht
niet relevant; het ID wordt niet hergebruikt). EXT-001 uitgebreid van strengen naar
strengen en putten, met de relatie binnen, kruist of nabij als uitkomst; ernst en
dimensie ongewijzigd. Nieuwe paragraaf Afbakening van een analyse, waarin het scopebeleid
kern-plus-contextschil staat en de mechanische riolering expliciet als niet-geanalyseerd
wordt benoemd. Verder geen checks toegevoegd, geschrapt of van ernst of dimensie
veranderd.
```

- [ ] **Step 7: Zet de vijf verwijzingen om**

In `src/nlriochecker/register.py`: vervang in de moduledocstring en in `default_register_path()` `checkregister-gwsw-nulmeting-v0_7.md` door `checkregister-gwsw-nulmeting-v0_8.md`.

In `src/nlriochecker/dekking.toml`:

```toml
checkregister_versie = "0.8"
bron = "data/checkregister-gwsw-nulmeting-v0_8.md"
```

In `src/nlriochecker/checks.toml`, onder `[rapport]`:

```toml
register_versie = "v0.8"
```

In `tests/test_checks_registry.py` regel 12: `"checkregister-gwsw-nulmeting-v0_8.md"`.

Het v0.7-bestand blijft staan; eerdere runs verwijzen ernaar.

- [ ] **Step 8: Draai de tests**

Run: `uv run pytest tests/test_register_versie.py tests/test_checks_registry.py tests/test_coverage.py -v`
Verwacht: PASS. Draai daarna de hele suite: `uv run pytest -m "not zwaar"` — ook groen, want er is nog geen check gewijzigd.

- [ ] **Step 9: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add data/checkregister-gwsw-nulmeting-v0_8.md tests/test_register_versie.py \
        src/nlriochecker/register.py src/nlriochecker/dekking.toml \
        src/nlriochecker/checks.toml tests/test_checks_registry.py
git commit -m "Checkregister v0.8: het scopebeleid vastgelegd en de vijf versieverwijzingen omgezet"
```

---

### Taak 2: EXT-008 vervalt

**Files:**
- Modify: `data/checkregister-gwsw-nulmeting-v0_8.md` (EXT-tabel en de tabel met vervallen checks)
- Modify: `src/nlriochecker/checks/extern.py` (klasse `PandZonderRiolering`, regels 569-651)
- Modify: `src/nlriochecker/checkconfig.py` (regel 191, `ext_riolering_bij_pand_m`)
- Modify: `tests/test_checks_extern.py` (regels 26, 41-42, 109, 206-220)
- Modify: `tests/test_uitvoer_locatie.py` (regel 72)
- Modify: `tests/test_integration.py` (regel 234)

**Interfaces:**
- Consumes: het registerbestand uit taak 1.
- Produces: `REGISTRY` zonder `EXT-008`; `CheckThresholds` zonder `ext_riolering_bij_pand_m`.

- [ ] **Step 1: Haal EXT-008 uit het register**

Verwijder in `data/checkregister-gwsw-nulmeting-v0_8.md` deze rij uit de EXT-tabel:

```
| EXT-008 | BAG-verblijfsobject zonder riolering binnen X m (dekkingscheck) | W | Compleetheid |
```

en zet hem onder `## Vervallen checks (niet relevant voor deze toepassing)`:

```
| EXT-008 | BAG-verblijfsobject zonder riolering binnen X m (dekkingscheck) | v0.8 | Niet relevant voor deze opdracht: de vraag of elk pand op riolering is aangesloten hoort bij het rioleringsplan, niet bij een datakwaliteitstoets op de bestaande registratie. Bovendien zijn er panden aangeleverd en geen verblijfsobjecten, waardoor de check alleen een benadering kon geven. |
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_checks_registry.py -k EXT-008 -v`
Verwacht: FAIL met "EXT-008 staat niet in het checkregister" — de engine kent de check nog wel.

- [ ] **Step 3: Haal de check uit de engine**

Verwijder in `src/nlriochecker/checks/extern.py` de hele klasse `PandZonderRiolering` inclusief de `@register`-decorator. Verwijder in `src/nlriochecker/checkconfig.py` de regel:

```python
    ext_riolering_bij_pand_m: float = Field(default=40.0, gt=0.0)
```

Controleer met `grep -rn "ext_riolering_bij_pand_m\|PandZonderRiolering" src tests` dat er niets meer naar verwijst; `checks.toml` noemt de drempel niet, dus daar is niets te doen.

- [ ] **Step 4: Haal de check uit de tests**

In `tests/test_checks_extern.py`:
- regel 26: `EXT_IDS = ["EXT-001", "EXT-002", "EXT-003", "EXT-005", "EXT-006", "EXT-007"]`
- verwijder in de `config`-fixture de twee commentaarregels over EXT-008 en de regel `gekozen.drempels.ext_riolering_bij_pand_m = 10.0`
- verwijder de parametrisatieregel `("EXT-008", ["bag-verweg"]),`
- verwijder de test die `uitkomst("EXT-008", ...)` draait (rond regel 206) in zijn geheel
- vervang in de lus rond regel 219 `for check_id in ("EXT-006", "EXT-008"):` door `for check_id in ("EXT-006",):`

In `tests/test_uitvoer_locatie.py` regel 72: vervang de docstring `"""EXT-006 en EXT-008 melden objecten die niet in de GWSW-dataset staan."""` door `"""EXT-006 meldt objecten die niet in de GWSW-dataset staan."""` en haal de EXT-008-tak uit die test als die er is.

In `tests/test_integration.py` regel 234: haal `"EXT-008"` uit de lijst `ids`.

- [ ] **Step 5: Draai de tests**

Run: `uv run pytest -m "not zwaar"`
Verwacht: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "EXT-008 vervalt: de dekkingsvraag hoort bij het rioleringsplan, niet bij deze toets"
```

---

### Taak 3: EXT-001 toetst ook putten en benoemt de relatie

De check meldt nu alles binnen de buffer zonder onderscheid: afstand nul betekent zowel
"kruist de gevel" als "ligt volledig binnen het pand", en putten worden helemaal niet
bekeken. Na deze taak draagt elke bevinding een relatie.

**Files:**
- Modify: `data/checkregister-gwsw-nulmeting-v0_8.md` (EXT-001-rij)
- Modify: `src/nlriochecker/checks/extern.py` (klasse `KruisingMetBouwwerk`, regels 207-295)
- Modify: `tests/fixtures/ttl/ext_scenario.ttl` (twee putten en een streng erbij)
- Modify: `tests/test_checks_extern.py` (verwachtingen EXT-001 en EXT-005)
- Modify: `tests/test_integration.py` (regel 239)

**Interfaces:**
- Consumes: `_ExterneCheck`, `_strengen()`, `_putten()` uit `checks/extern.py`; `Melding.waarde` en `Melding.drempel` uit `uitvoer/melding.py`.
- Produces: bevindingen van EXT-001 met `details["waarde"]` in `{"binnen", "kruist", "nabij"}` en `details["drempel"]` gelijk aan de buffer in meters.

- [ ] **Step 1: Breid de fixture uit**

Het BGT-pand in de fixtures beslaat (1020, 1998) tot (1030, 2002). Voeg in
`tests/fixtures/ttl/ext_scenario.ttl` twee putten en een streng toe die daarbinnen
liggen. Volg exact de opmaak van de bestaande putten en strengen in dat bestand (elk
object met zijn orientatie, `Putorientatie` respectievelijk `Leidingorientatie`, en een
`gml:Point` of `gml:LineString` als aspect). De coordinaten:

- put `P` op (1022.0, 2000.0)
- put `Q` op (1028.0, 2000.0)
- vrijvervalstreng `4` van (1022.0, 2000.0) naar (1028.0, 2000.0), met `P` als beginput en
  `Q` als eindput

Geef ze geen maaiveldhoogte, BOB of inwinning; dan raken ze de HGT- en BTR-tests niet.

- [ ] **Step 2: Schrijf de falende test**

Vervang in `tests/test_checks_extern.py` de parametrisatieregel voor EXT-001 door
`("EXT-001", ["1", "4", "P", "Q"]),` en voeg deze test toe:

```python
def test_ext001_benoemt_de_relatie_met_het_bouwwerk(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    outcome = uitkomst("EXT-001", config, bronnen)
    relaties = {
        finding.object_label: finding.details["waarde"] for finding in outcome.findings
    }

    # Streng 1 steekt door de gevel, streng 4 en de twee putten liggen er binnen.
    assert relaties == {"1": "kruist", "4": "binnen", "P": "binnen", "Q": "binnen"}
    assert all(finding.details["drempel"] == config.drempels.ext_pand_buffer_m
               for finding in outcome.findings)
```

Werk in dezelfde parametrisatie de EXT-005-verwachting bij naar
`("EXT-005", ["C", "E", "F", "L1", "L2", "P", "Q"]),`: de twee nieuwe putten hebben geen
BGT-putdeksel in de buurt.

- [ ] **Step 3: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_checks_extern.py -k "ext001 or defect_wordt_gevonden" -v`
Verwacht: FAIL — EXT-001 vindt alleen streng "1" en kent geen `waarde`.

- [ ] **Step 4: Herschrijf de check**

Vervang in `src/nlriochecker/checks/extern.py` de body van `KruisingMetBouwwerk` (laat
`bouwwerklagen()`, `bruikbaar()` en `notes()` staan) door:

```python
# De relaties van sterk naar zwak; de sterkste die op een object van toepassing is
# komt in de melding.
RELATIE_BINNEN = "binnen"
RELATIE_KRUIST = "kruist"
RELATIE_NABIJ = "nabij"
RELATIE_VOLGORDE = (RELATIE_BINNEN, RELATIE_KRUIST, RELATIE_NABIJ)


@register
class KruisingMetBouwwerk(_ExterneCheck):
    """EXT-001: een streng of put die in, door of vlak langs een bouwwerk ligt."""

    id = "EXT-001"
    title = "Kruising of nabijheid van BGT-panden en overige bouwwerken"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rol = "bgt_pand"
    soort = "vrijvervalstrengen en putten"

    def objecten(self, context: CheckContext) -> list:
        """De vrijvervalstrengen en de putten; beide horen niet in een pand."""
        return [*_strengen(context), *_putten(context)]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk object dat binnen, door of vlak langs een bouwwerk ligt.

        Panden komen uit de BGT en worden aangevuld met de BAG-panden; die twee
        overlappen grotendeels maar niet volledig. Overige bouwwerken tellen mee als
        aparte laag. Een put in een pand is een ander gebrek dan een streng die de
        gevel raakt, dus staat de relatie in de melding.
        """
        lagen = self.bouwwerklagen(context)
        if not lagen or not self.bruikbaar(context):
            return
        buffer = context.config.drempels.ext_pand_buffer_m

        for object_ in self.selectie(context).toetsbaar:
            geometrie = self.geometrie_van(object_)
            if geometrie is None or geometrie.is_empty:
                continue
            geraakt = self._sterkste(geometrie, lagen, buffer)
            if geraakt is None:
                continue
            relatie, afstand, laag = geraakt
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
            )

    def _sterkste(self, geometrie, lagen, buffer: float):
        """De zwaarste relatie met een bouwwerk binnen de buffer, met afstand en laag.

        Bij gelijke relatie wint het dichtstbijzijnde bouwwerk; zo hangt de melding
        niet af van de volgorde waarin de lagen toevallig gelezen zijn.
        """
        beste = None
        for laag in lagen:
            for vorm, _ in laag.nabij(geometrie, buffer):
                afstand = geometrie.distance(vorm)
                if afstand > buffer:
                    continue
                relatie = self._relatie(geometrie, vorm, afstand)
                kandidaat = (RELATIE_VOLGORDE.index(relatie), afstand, relatie, laag)
                if beste is None or kandidaat[:2] < beste[:2]:
                    beste = kandidaat
        return None if beste is None else (beste[2], beste[1], beste[3])

    def _relatie(self, geometrie, bouwwerk, afstand: float) -> str:
        """De relatie tussen object en bouwwerk: binnen, kruist of nabij."""
        if geometrie.within(bouwwerk):
            return RELATIE_BINNEN
        if afstand == 0.0:
            return RELATIE_KRUIST
        return RELATIE_NABIJ

    def _zin(self, relatie: str, afstand: float) -> str:
        """De relatie als leesbare zin voor in de melding."""
        if relatie == RELATIE_BINNEN:
            return "ligt volledig binnen"
        if relatie == RELATIE_KRUIST:
            return "kruist"
        return f"ligt {afstand:.2f} m van"
```

`geometrie_van()` staat al op `_ExterneCheck` en blijft daar; `_putten()` levert de knopen
inclusief de eindpunten en bergbezinkvoorzieningen, precies zoals EXT-005 die gebruikt.

- [ ] **Step 5: Draai de tests**

Run: `uv run pytest tests/test_checks_extern.py -v`
Verwacht: PASS.

- [ ] **Step 6: Werk het register bij**

Vervang de EXT-001-rij in `data/checkregister-gwsw-nulmeting-v0_8.md` door:

```
| EXT-001 | Kruising of nabijheid van BGT-panden en overige bouwwerken; getoetst op strengen en putten, met als uitkomst de relatie binnen, kruist of nabij | W | Plausibiliteit |
```

- [ ] **Step 7: Werk de zware integratietest bij**

`tests/test_integration.py` regel 239 legt `per_check["EXT-001"].examined == 29` vast; dat
was het aantal vrijvervalstrengen binnen het bronbereik. Nu tellen de putten mee.

Run: `uv run pytest -m zwaar -k ext_checks_op_koekangerveld -v`
Neem het getal over dat de fout meldt en controleer dat het klopt met de telling die
`EXT-005` (`examined`, alleen putten) en de oude 29 samen geven. Leg in een commentaarregel
vast waar het getal vandaan komt.

- [ ] **Step 8: Commit**

```bash
uv run ruff check && uv run ruff format --check
uv run pytest -m "not zwaar"
git add -A
git commit -m "EXT-001 toetst ook putten en benoemt of een object binnen, door of langs een bouwwerk ligt"
```

---

### Taak 4: Stijlen die QGIS ook echt toepast

QGIS negeert de stijlen in het huidige bestand. De oorzaak is geverifieerd met de QGIS van
deze machine: `layer_styles` staat niet in `gpkg_contents`, en dan vindt de OGR-provider de
tabel niet. Na registratie geeft `loadDefaultStyle()` op alle lagen
`('Loaded from Provider', True)`. Een losse QML naast het bestand kan het nooit oplossen:
die geldt alleen voor een GeoPackage met een enkele laag en heet dan naar het bestand, niet
naar de laag.

**Files:**
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`_schrijf_stijlen`, regels 555-585, en de aanroep in `schrijf_geopackage` regel 82)
- Modify: `tests/test_uitvoer_gpkg.py` (`test_stijlen_liggen_ook_los_naast_het_bestand`, regel 183)

**Interfaces:**
- Consumes: `_registreer(verbinding, naam, soort, omschrijving)` uit `gpkg.py`.
- Produces: `_schrijf_stijlen(verbinding)` — zonder `output_dir`, want er komt geen bestand meer naast te liggen.

- [ ] **Step 1: Schrijf de falende tests**

Vervang in `tests/test_uitvoer_gpkg.py` de test `test_stijlen_liggen_ook_los_naast_het_bestand` door:

```python
def test_stijltabel_is_als_laag_geregistreerd(tmp_path: Path) -> None:
    """Zonder rij in gpkg_contents vindt de OGR-provider layer_styles niet."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    rijen = _rijen(
        pad,
        "select data_type, srs_id from gpkg_contents where table_name = 'layer_styles'",
    )

    assert rijen == [("attributes", None)]


def test_stijlen_dragen_een_tijdstempel_in_iso8601(tmp_path: Path) -> None:
    """GDAL meldt elk ander formaat als non-conformant bij het lezen."""
    import re

    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    tijden = [tijd for (tijd,) in _rijen(pad, "select update_time from layer_styles")]

    assert tijden
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", tijd) for tijd in tijden)


def test_er_liggen_geen_losse_qml_bestanden_meer(tmp_path: Path) -> None:
    """Een sidecar-QML werkt niet bij meerdere lagen; hem toch neerleggen misleidt."""
    _schrijf(_run("schoon.ttl"), tmp_path)

    assert list(tmp_path.glob("*.qml")) == []
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k "stijl or qml" -v`
Verwacht: FAIL — de tabel staat niet in `gpkg_contents`, het tijdstempel heeft geen T en Z, en de QML-bestanden liggen er nog.

- [ ] **Step 3: Pas de schrijver aan**

In `src/nlriochecker/uitvoer/gpkg.py`:

```python
def _schrijf_stijlen(verbinding: sqlite3.Connection) -> None:
    """Zet de QML-stijlen in `layer_styles` en registreert die tabel.

    Zonder rij in `gpkg_contents` vindt de OGR-provider van QGIS de tabel niet en
    krijgt elke laag de standaard-symbologie; dat is met PyQGIS vastgesteld op deze
    uitvoer. `update_time` moet ISO-8601 met T en Z zijn, anders meldt GDAL bij elke
    rij "non-conformant content".

    Een QML los naast het bestand is geen alternatief: die werkt alleen bij een
    GeoPackage met een enkele laag en heet dan naar het bestand, niet naar de laag.
    """
    verbinding.execute(
        "create table layer_styles ("
        "id integer primary key autoincrement, f_table_catalog text, f_table_schema text, "
        "f_table_name text, f_geometry_column text, styleName text, styleQML text, "
        "styleSLD text, useAsDefault boolean, description text, owner text, ui text, "
        "update_time datetime default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    _registreer(
        verbinding,
        "layer_styles",
        "attributes",
        "QGIS-stijlen van dit bestand; QGIS past de standaardstijl per laag zelf toe.",
    )
    for laag in FEATURELAGEN:
        qml = _stijl(laag)
        verbinding.execute(
            "insert into layer_styles (f_table_catalog, f_table_schema, f_table_name, "
            "f_geometry_column, styleName, styleQML, styleSLD, useAsDefault, description, "
            "owner, ui, update_time) values ('', '', ?, 'geom', ?, ?, '', 1, ?, "
            "'nlriochecker', '', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
            (laag, f"{laag} (datakwaliteit)", qml, f"Standaardstijl voor {laag}."),
        )
```

Pas in `schrijf_geopackage` de aanroep aan naar `_schrijf_stijlen(verbinding)` en haal de
nu ongebruikte doorgifte van `output_dir` weg. Werk ook de moduledocstring bij: de bewering
dat QGIS `layer_styles` zelf niet registreert is onjuist gebleken.

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -v`
Verwacht: PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "QGIS past de stijlen nu toe: layer_styles stond niet in gpkg_contents"
```

---

### Taak 5: feature_id als fragment, de URI apart

`feature_id` bevat nu `http://sparql.gwsw.nl/kikker_vrij#knp3437`. Dat leest als een
webadres dat niet bestaat. Het fragment is even uniek en veel bruikbaarder; de volledige
URI blijft als eigen kolom staan voor de herleidbaarheid naar de TTL.

**Files:**
- Modify: `src/nlriochecker/uitvoer/identiteit.py` (nieuwe functie `kort`)
- Modify: `src/nlriochecker/uitvoer/melding.py` (`Melding`, `bouw_meldingen`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`_samenvatting_kolommen`, `_samenvatting`, `MELDING_KOLOMMEN`, `_melding_rij`)
- Modify: `src/nlriochecker/uitvoer/bevindingen.py` (`CSV_KOLOMMEN`, `meldingen_tabel`)
- Modify: `tests/test_uitvoer_identiteit.py`, `tests/test_uitvoer_gpkg.py`, `tests/test_uitvoer_melding.py`

**Interfaces:**
- Consumes: niets uit eerdere taken.
- Produces: `kort(uri: str) -> str`; `Melding.object_id` en `Melding.object2_id`; GPKG-kolommen `feature_id`, `gwsw_uri`, `feature_id_2`, `gwsw_uri_2`; CSV-kolommen `Object`, `ObjectURI`, `Object2`, `Object2URI`.

- [ ] **Step 1: Schrijf de falende test voor `kort`**

Voeg toe aan `tests/test_uitvoer_identiteit.py`:

```python
from nlriochecker.uitvoer.identiteit import kort


def test_kort_geeft_het_fragment_van_een_gwsw_uri() -> None:
    assert kort("http://sparql.gwsw.nl/kikker_vrij#knp3437") == "knp3437"
    assert kort("http://sparql.gwsw.nl/kikker_vrij#lei3436-3435-1") == "lei3436-3435-1"


def test_kort_laat_een_uri_zonder_fragment_ongemoeid() -> None:
    """De EXT-checks melden objecten uit BGT en BAG; die hebben geen dataset-URI."""
    assert kort("bgt:put/deksel-los") == "bgt:put/deksel-los"
    assert kort("") == ""
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_uitvoer_identiteit.py -k kort -v`
Verwacht: FAIL met ImportError.

- [ ] **Step 3: Schrijf `kort`**

Voeg toe aan `src/nlriochecker/uitvoer/identiteit.py`:

```python
def kort(uri: str) -> str:
    """Het leesbare deel van een object-URI: het fragment achter de `#`.

    De GWSW-URI's zijn van de vorm `http://sparql.gwsw.nl/<export>#knp3437`; alleen
    het fragment zegt iets tegen een lezer, en het is binnen een export uniek. Een
    URI zonder `#` komt niet uit de dataset maar uit een externe bron (BGT, BAG) en
    blijft ongewijzigd: daar is de hele tekst de identificatie.
    """
    return uri.split("#", 1)[1] if "#" in uri else uri
```

- [ ] **Step 4: Draai de test**

Run: `uv run pytest tests/test_uitvoer_identiteit.py -v`
Verwacht: PASS. Commit deze stap nog niet.

- [ ] **Step 5: Schrijf de falende test voor de uitvoerkolommen**

Voeg toe aan `tests/test_uitvoer_gpkg.py`:

```python
def test_feature_id_is_het_fragment_en_de_uri_staat_erbij(tmp_path: Path) -> None:
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    rijen = _rijen(pad, "select feature_id, gwsw_uri from putten limit 1")

    feature_id, uri = rijen[0]
    assert "#" not in feature_id
    assert uri.endswith(f"#{feature_id}")


def test_meldingen_dragen_fragment_en_uri(tmp_path: Path) -> None:
    run = _run("top005_dubbele_put.ttl", "TOP-005")
    pad = _schrijf(run, tmp_path)

    rijen = _rijen(pad, "select feature_id, gwsw_uri, feature_id_2, gwsw_uri_2 from meldingen")

    assert rijen
    for feature_id, uri, tweede_id, tweede_uri in rijen:
        assert "#" not in feature_id
        assert uri.endswith(f"#{feature_id}")
        assert "#" not in tweede_id
        assert tweede_uri.endswith(f"#{tweede_id}")
```

En aan `tests/test_uitvoer_melding.py`:

```python
def test_melding_draagt_zowel_fragment_als_uri() -> None:
    run = _run("top005_dubbele_put.ttl", "TOP-005")

    melding = bouw_meldingen(run, RUNDATUM)[0]

    assert melding.object_uri.endswith(f"#{melding.object_id}")
    assert "#" not in melding.object_id


def test_de_melding_id_blijft_over_de_volledige_uri_gehasht() -> None:
    """De ID's moeten vergelijkbaar blijven met die van eerdere runs."""
    run = _run("top005_dubbele_put.ttl", "TOP-005")

    melding = bouw_meldingen(run, RUNDATUM)[0]

    assert melding.melding_id == melding_id(
        melding.check_id, melding.object_uri, melding.object2_uri, {}
    )
```

(Importeer `melding_id` uit `nlriochecker.uitvoer.identiteit` en volg voor `_run` de opzet
van de bestaande tests in dat bestand. Draagt TOP-005 een onderscheidende detailsleutel,
gebruik die dan als vierde argument in plaats van het lege woordenboek.)

- [ ] **Step 6: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py tests/test_uitvoer_melding.py -k "fragment or uri" -v`
Verwacht: FAIL — de kolom `gwsw_uri` bestaat niet.

- [ ] **Step 7: Zet de velden op de melding**

In `src/nlriochecker/uitvoer/melding.py`, in de dataclass `Melding` direct onder `object_uri` respectievelijk `object2_uri`:

```python
    object_uri: str
    object_id: str
    object_label: str
    object2_uri: str
    object2_id: str
    object2_label: str
```

En in `bouw_meldingen`, bij het opbouwen van de `Melding`:

```python
                    object_uri=finding.object_uri,
                    object_id=kort(finding.object_uri),
                    object_label=finding.object_label,
                    object2_uri=_tekst(finding.details.get(SLEUTEL_OBJECT2_URI)),
                    object2_id=kort(_tekst(finding.details.get(SLEUTEL_OBJECT2_URI))),
                    object2_label=_tekst(finding.details.get(SLEUTEL_OBJECT2_LABEL)),
```

Breid de import bovenin uit: `from nlriochecker.uitvoer.identiteit import kort, melding_id`.
De hash in `_uniek_id` blijft over `finding.object_uri` gaan; de ID's veranderen dus niet
ten opzichte van eerdere runs.

- [ ] **Step 8: Zet de kolommen in de GeoPackage**

In `src/nlriochecker/uitvoer/gpkg.py`:
- in `_samenvatting_kolommen()` blijft `_Kolom("feature_id", "text")` vooraan staan; voeg
  achteraan, na `_Kolom("register_versie", "text")`, toe: `_Kolom("gwsw_uri", "text")`.
- in `_samenvatting()` wordt de eerste waarde `kort(uri)` en komt `uri` als laatste waarde
  achter de metadata.
- in `MELDING_KOLOMMEN` blijven `feature_id` en `feature_id_2` op hun plaats; voeg
  achteraan toe: `_Kolom("gwsw_uri", "text")` en `_Kolom("gwsw_uri_2", "text")`.
- in `_melding_rij()` worden de eerste twee objectvelden `melding.object_id` en
  `melding.object2_id`, en komen `melding.object_uri` en `melding.object2_uri` achteraan.

Importeer `kort` uit `nlriochecker.uitvoer.identiteit`.

- [ ] **Step 9: Zet de kolommen in de CSV**

In `src/nlriochecker/uitvoer/bevindingen.py`:
- laat `"Object"` en `"Object2"` op hun plaats in `CSV_KOLOMMEN` staan, en voeg achteraan
  `"ObjectURI"` en `"Object2URI"` toe;
- in `meldingen_tabel()`: `"Object": melding.object_id`, `"Object2": melding.object2_id`,
  en achteraan `"ObjectURI": melding.object_uri`, `"Object2URI": melding.object2_uri`;
- werk de commentaarregel boven `CSV_KOLOMMEN` bij: de eerste negen kolommen houden hun
  naam en plaats, maar `Object` draagt vanaf v0.8 het fragment en de volledige URI staat
  in `ObjectURI`.

- [ ] **Step 10: Draai de volledige suite**

Run: `uv run pytest -m "not zwaar"`
Verwacht: PASS. Tests die op een volledige URI in de CSV of de GPKG rekenen, moeten mee
worden aangepast; zoek ze met `grep -rn "sparql.gwsw.nl\|#knp\|#lei" tests/`.

- [ ] **Step 11: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "feature_id draagt het fragment; de volledige URI staat als gwsw_uri ernaast"
```

---

### Taak 6: Mechanische leidingen als eigen laag

In de De Wolden-export zitten 3.548 persleidingen, 147 vacuumleidingen en 25 drukleidingen.
Die staan nu in de laag `strengen` met `ergste_ernst = 'geen'` — precies zoals een streng
die wél getoetst is en in orde bleek. Mechanisch riool valt buiten scope; dat hoort in het
kaartbeeld te staan.

**Files:**
- Modify: `src/nlriochecker/checks.toml` (sectie `[klassen]`)
- Modify: `src/nlriochecker/checkconfig.py` (`ClassRoots`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`FEATURELAGEN`, `_schrijf_features`, `_schrijf_runmetadata`)
- Create: `src/nlriochecker/uitvoer/stijlen/mechanisch_riool.qml`
- Create: `tests/fixtures/ttl/mechanisch_riool.ttl`
- Modify: `tests/test_uitvoer_gpkg.py`, `tests/test_checkconfig.py`

**Interfaces:**
- Consumes: `_maak_featurelaag`, `_blob`, `_zet_omhullende` uit `gpkg.py`.
- Produces: laag `mechanisch_riool` met kolommen `feature_id`, `label`, `objecttype`, `omschrijving`, `gebied`, `run_datum`, `dataset_versie`, `gwsw_uri`; `gwsw_run` met de kolommen `n_putten`, `n_strengen`, `n_mechanisch`; `config.klassen.mechanisch`.

- [ ] **Step 1: Maak de fixture**

Maak `tests/fixtures/ttl/mechanisch_riool.ttl` naar het model van `tests/fixtures/ttl/schoon.ttl`:
twee putten met een vrijvervalstreng ertussen, plus één `gwsw:Persleiding` met eigen
orientatie en lijngeometrie tussen twee andere punten. Houd de coordinaten in hetzelfde
bereik als de andere fixtures (rond x=1000, y=2000).

- [ ] **Step 2: Schrijf de falende tests**

In `tests/test_uitvoer_gpkg.py`:

```python
def test_mechanische_leidingen_staan_in_een_eigen_laag(tmp_path: Path) -> None:
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    soorten = [rij[0] for rij in _rijen(pad, "select objecttype from mechanisch_riool")]
    omschrijvingen = {rij[0] for rij in _rijen(pad, "select omschrijving from mechanisch_riool")}

    assert soorten == ["Persleiding"]
    assert omschrijvingen == {"Mechanisch riool: niet geanalyseerd"}


def test_mechanische_leidingen_staan_niet_meer_bij_de_strengen(tmp_path: Path) -> None:
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    soorten = {rij[0] for rij in _rijen(pad, "select objecttype from strengen")}

    assert "Persleiding" not in soorten


def test_runmetadata_telt_de_lagen(tmp_path: Path) -> None:
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    (putten, strengen, mechanisch), = _rijen(
        pad, "select n_putten, n_strengen, n_mechanisch from gwsw_run"
    )

    assert (putten, strengen, mechanisch) == (4, 1, 1)
```

De getallen horen bij de fixture uit stap 1: vier knopen (twee voor de vrijvervalstreng,
twee voor de persleiding), één vrijvervalstreng en één persleiding. Klopt het niet, dan
klopt de fixture niet — pas die aan, niet de assertie.

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k mechanisch -v`
Verwacht: FAIL — de tabel `mechanisch_riool` bestaat niet.

- [ ] **Step 4: Zet de klassen in de configuratie**

In `src/nlriochecker/checks.toml`, onder `[klassen]`, na de regel voor `streng`:

```toml
# Mechanisch riool valt buiten scope (zie het checkregister). Deze klassen komen
# niet in de analyse maar wel in de GIS-uitvoer, in een eigen grijze laag; een leeg
# kaartbeeld daar zou anders als "geen gebreken" lezen. De namen zijn geverifieerd
# tegen de export: Persleiding 3548, Vacuumleiding 147, Drukleiding 25.
mechanisch = ["Persleiding", "Drukleiding", "Vacuumleiding"]
```

In `src/nlriochecker/checkconfig.py`, in `ClassRoots` onder `streng`:

```python
    # Mechanisch riool: buiten scope voor de checks, wel zichtbaar in de GIS-uitvoer.
    mechanisch: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: Splits de lagen in de schrijver**

In `src/nlriochecker/uitvoer/gpkg.py`:

```python
FEATURELAGEN = ("putten", "strengen", "meldinglocaties", "mechanisch_riool")

MECHANISCH_OMSCHRIJVING = "Mechanisch riool: niet geanalyseerd"


def _mechanische_uris(run: CheckRun, config: CheckConfig) -> frozenset[str]:
    """De verbindingen die tot het mechanische stelsel horen.

    Ze doen niet mee aan de checks en horen dus niet tussen de strengen te staan,
    waar 'geen melding' ten onrechte als 'getoetst en in orde' leest.
    """
    return frozenset(
        uri
        for wortel in config.klassen.mechanisch
        for uri in run.dataset.of_class(wortel)
        if uri in run.dataset.conduits
    )
```

`_schrijf_features` schrijft `strengen` voortaan uit `{uri: c for uri, c in
run.dataset.conduits.items() if uri not in mechanisch}` — alles behalve het mechanische
stelsel, zodat er niets stilzwijgend verdwijnt — en roept daarna
`_schrijf_mechanisch(verbinding, run, binnen, mechanisch, metadata)` aan:

```python
def _mechanisch_kolommen() -> list[_Kolom]:
    """De smalle kolomset van de laag `mechanisch_riool`."""
    return [
        _Kolom("feature_id", "text"),
        _Kolom("label", "text"),
        _Kolom("objecttype", "text"),
        _Kolom("omschrijving", "text"),
        _Kolom("gebied", "text"),
        _Kolom("run_datum", "text"),
        _Kolom("dataset_versie", "text"),
        _Kolom("gwsw_uri", "text"),
    ]
```

De rijen bevatten `kort(uri)`, het label, `run.dataset.beheerobjecttype(uri)`,
`MECHANISCH_OMSCHRIJVING`, `_gebied(run)`, de rundatum, de datasetnaam en de volledige URI.
Sla objecten zonder geometrie over en respecteer `binnen` net als de andere lagen.

In `_schrijf_runmetadata` komen er drie kolommen bij — `n_putten`, `n_strengen`,
`n_mechanisch` — gevuld met de aantallen die daadwerkelijk weggeschreven zijn.

- [ ] **Step 6: Maak de stijl**

Maak `src/nlriochecker/uitvoer/stijlen/mechanisch_riool.qml`:

```xml
<!-- Default-stijl voor het mechanische stelsel: grijs en dun, met de reden in de
     legenda. Deze leidingen zijn niet getoetst; ze staan er alleen zodat een leeg
     kaartbeeld niet als "geen gebreken" leest. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="singleSymbol" forceraster="0" symbollevels="0">
    <symbols>
      <symbol type="line" name="0" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="140,140,140,200"/>
          <prop k="line_width" v="0.4"/>
          <prop k="customdash" v="4;2"/>
          <prop k="use_custom_dash" v="1"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <legend type="default-vector"/>
</qgis>
```

- [ ] **Step 7: Draai de tests**

Run: `uv run pytest tests/test_uitvoer_gpkg.py tests/test_checkconfig.py -v`
Verwacht: PASS.

- [ ] **Step 8: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Mechanisch riool krijgt een eigen grijze laag; het stond tussen de getoetste strengen"
```

---

### Taak 7: Richtingspijlen op de strengen

Twee pijlen per streng: één die de tekenrichting van de lijn volgt en één die het
BOB-verval volgt. Zijn ze het eens, dan één groene pijl; zijn ze het oneens, dan twee
pijlen die tegen elkaar in wijzen. Ontbreken de BOB's of zijn ze gelijk, dan één grijze
pijl met een eigen legenda-regel.

**Files:**
- Modify: `src/nlriochecker/dataset.py` (`Conduit.bob_verval`, `GwswDataset.richting_van_geometrie`)
- Modify: `src/nlriochecker/checks/topologie.py` (TOP-020 gebruikt de nieuwe methode)
- Modify: `src/nlriochecker/checks/netwerk.py` (`_stijgt` gebruikt `bob_verval`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (kolommen `richting_bob`, `bob_verval_m`)
- Modify: `src/nlriochecker/uitvoer/stijlen/strengen.qml`
- Create: `tests/fixtures/ttl/richting_omgekeerd_met_bob.ttl`
- Modify: `tests/test_dataset.py`, `tests/test_uitvoer_gpkg.py`

**Interfaces:**
- Consumes: `resolve_network_node`, `config.klassen.netwerkknopen`.
- Produces: `Conduit.bob_verval -> float | None`; `GwswDataset.richting_van_geometrie(conduit, roots) -> tuple[bool, Node, Node] | None`; GPKG-kolommen `richting_bob` (`mee`, `tegen`, `onbekend`) en `bob_verval_m` (verval langs de getekende lijn, positief als de bodem daalt).

- [ ] **Step 1: Schrijf de falende tests voor de dataset**

Voeg toe aan `tests/test_dataset.py`:

```python
def test_bob_verval_is_het_verschil_over_de_streng(juinen) -> None:
    conduit = next(c for c in juinen.conduits.values() if c.bob_start and c.bob_end)

    assert conduit.bob_verval == pytest.approx(conduit.bob_start - conduit.bob_end)


def test_bob_verval_ontbreekt_zonder_beide_bobs(juinen) -> None:
    conduit = next(
        (c for c in juinen.conduits.values() if c.bob_start is None or c.bob_end is None),
        None,
    )
    if conduit is None:
        pytest.skip("elke streng in het voorbeeld draagt beide BOB's")

    assert conduit.bob_verval is None


def test_richting_van_geometrie_ziet_een_omgekeerd_getekende_lijn() -> None:
    from nlriochecker.checkconfig import load_check_config

    dataset = load_dataset(TTL_DIR / "top020_omgekeerd_getekend.ttl")
    wortels = load_check_config().klassen.netwerkknopen
    conduit = next(iter(dataset.conduits.values()))

    uitslag = dataset.richting_van_geometrie(conduit, wortels)

    assert uitslag is not None
    omgekeerd, begin, eind = uitslag
    assert omgekeerd is True
    assert begin.uri != eind.uri
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_dataset.py -k "bob_verval or richting_van_geometrie" -v`
Verwacht: FAIL met AttributeError.

- [ ] **Step 3: Zet de twee methoden op de dataset**

In `src/nlriochecker/dataset.py`, bij de andere properties van `Conduit`:

```python
    @property
    def bob_verval(self) -> float | None:
        """Het verval van de bodem over de streng, in meters.

        Positief als de bodem van het administratieve beginpunt naar het eindpunt
        daalt. Ontbreekt een van beide BOB's, dan valt er niets te zeggen.
        """
        if self.bob_start is None or self.bob_end is None:
            return None
        return self.bob_start - self.bob_end
```

En op `GwswDataset`:

```python
    def richting_van_geometrie(
        self, conduit: Conduit, roots: list[str]
    ) -> tuple[bool, Node, Node] | None:
        """Vergelijkt de tekenrichting van de lijn met de van-naar-richting.

        Geeft (omgekeerd, beginput, eindput) terug, waarbij `omgekeerd` zegt of de
        lijn bij de administratieve eindput begint. None als er niets te vergelijken
        valt: geen geometrie, geen twee verschillende putten, of putten zonder punt.
        TOP-020 en de kaartlaag met richtingspijlen lezen allebei deze methode, zodat
        het kaartbeeld en de bevinding niet uit elkaar kunnen lopen.
        """
        if conduit.line is None or conduit.line.is_empty:
            return None
        begin = self.nodes.get(self.resolve_network_node(conduit.start_node, roots) or "")
        eind = self.nodes.get(self.resolve_network_node(conduit.end_node, roots) or "")
        if begin is None or eind is None or begin.point is None or eind.point is None:
            return None
        if begin.uri == eind.uri:
            return None
        punten = list(conduit.line.coords)
        eerste, laatste = Point(punten[0][:2]), Point(punten[-1][:2])
        juist = eerste.distance(begin.point) + laatste.distance(eind.point)
        omgekeerd = eerste.distance(eind.point) + laatste.distance(begin.point)
        return omgekeerd < juist, begin, eind
```

Controleer dat `Point` bovenin `dataset.py` geimporteerd is; zo niet, voeg
`from shapely.geometry import Point` toe bij de andere shapely-imports.

- [ ] **Step 4: Laat TOP-020 en NET-003 dezelfde methode gebruiken**

In `src/nlriochecker/checks/topologie.py`, in de `run()` van TOP-020: vervang de blokken
die begin- en eindput opzoeken en de twee afstandssommen vergelijken door:

```python
            uitslag = dataset.richting_van_geometrie(
                conduit, context.config.klassen.netwerkknopen
            )
            if uitslag is None:
                continue
            omgekeerd, begin, eind = uitslag
            if not omgekeerd:
                continue
```

De rest van de melding blijft ongewijzigd. In `src/nlriochecker/checks/netwerk.py` wordt
`_stijgt`:

```python
def _stijgt(conduit: Conduit) -> bool:
    """Geeft aan of de bodem stijgt van begin- naar eindpunt."""
    verval = conduit.bob_verval
    return verval is not None and verval < 0
```

- [ ] **Step 5: Draai de bestaande checktests**

Run: `uv run pytest tests/test_checks_topologie.py tests/test_checks_netwerk.py tests/test_dataset.py -v`
Verwacht: PASS — het gedrag is gelijk gebleven, alleen de plek van de logica is verschoven.

- [ ] **Step 6: Schrijf de falende test voor de kolommen**

In `tests/test_uitvoer_gpkg.py`:

```python
def test_strengen_dragen_de_bob_richting(tmp_path: Path) -> None:
    pad = _schrijf(_run("hgt_schoon.ttl"), tmp_path)

    rijen = _rijen(pad, "select richting_bob, bob_verval_m from strengen")

    assert rijen
    assert {rij[0] for rij in rijen} <= {"mee", "tegen", "onbekend"}
    for richting, verval in rijen:
        if richting == "mee":
            assert verval > 0
        elif richting == "tegen":
            assert verval < 0
        else:
            assert verval is None or verval == 0


def test_omgekeerd_getekende_streng_meet_het_verval_langs_de_lijn(tmp_path: Path) -> None:
    """De pijl volgt de getekende lijn; het verval hoort daar dus bij te horen."""
    pad = _schrijf(_run("richting_omgekeerd_met_bob.ttl"), tmp_path)

    (richting, verval), = _rijen(pad, "select richting_bob, bob_verval_m from strengen")

    # Administratief daalt de bodem 0,50 m van A naar B, maar de lijn is van B naar A
    # getekend; langs de lijn stijgt de bodem dus.
    assert richting == "tegen"
    assert verval == pytest.approx(-0.50)
```

Maak daarvoor `tests/fixtures/ttl/richting_omgekeerd_met_bob.ttl`: een kopie van
`tests/fixtures/ttl/top020_omgekeerd_getekend.ttl` (put A op 1000,2000, put B op
1050,2000, lijn getekend van 1050 naar 1000) met twee BOB-aspecten erbij op de streng:
`BobBeginpuntLeiding` 8,00 m en `BobEindpuntLeiding` 7,50 m. Neem de opmaak van de
BOB-aspecten over uit `tests/fixtures/ttl/hgt005_tegenverhang_licht.ttl`. Laat
`top020_omgekeerd_getekend.ttl` zelf ongemoeid; die fixture draagt bewust geen hoogten en
wordt door de TOP-020-test gebruikt.

- [ ] **Step 7: Vul de kolommen**

In `src/nlriochecker/uitvoer/gpkg.py`:

```python
RICHTING_MEE = "mee"
RICHTING_TEGEN = "tegen"
RICHTING_ONBEKEND = "onbekend"


def _richting_bob(run: CheckRun, conduit, config: CheckConfig) -> tuple[str, float | None]:
    """De BOB-richting ten opzichte van de getekende lijn, en het verval erlangs.

    Het BOB-verval is administratief: van beginpunt naar eindpunt. De pijl op de
    kaart volgt de getekende lijn. Loopt de lijn andersom dan de administratie, dan
    keert het teken om -- anders zou de kaart het tegenovergestelde tonen van wat er
    staat.
    """
    verval = conduit.bob_verval
    if verval is None or verval == 0.0:
        return RICHTING_ONBEKEND, verval
    uitslag = run.dataset.richting_van_geometrie(conduit, config.klassen.netwerkknopen)
    langs_lijn = -verval if (uitslag is not None and uitslag[0]) else verval
    return (RICHTING_MEE if langs_lijn > 0 else RICHTING_TEGEN), langs_lijn
```

Voeg `_Kolom("richting_bob", "text")` en `_Kolom("bob_verval_m", "real")` toe aan
`_samenvatting_kolommen()`, direct na `stelsel`. Vul ze in `_samenvatting()`: voor een put
blijven ze leeg (`""` en `None`), voor een streng komen ze uit `_richting_bob`. Geef
`_samenvatting()` daarvoor de al bekende waarden mee zoals `stelsel` dat nu ook krijgt.

- [ ] **Step 8: Vervang de stijl**

Vervang de inhoud van `src/nlriochecker/uitvoer/stijlen/strengen.qml` door onderstaande,
regelgebaseerde stijl. Deze is met PyQGIS gecontroleerd: hij laadt als
`QgsRuleBasedRenderer` met zes regels, waarvan de richtingregels `MarkerLine`-lagen dragen.

```xml
<!-- Default-stijl voor de laag `strengen`.

     De lijnkleur volgt de zwaarste melding op het object. Daar bovenop tekenen drie
     regels de richting: een groene pijl als het BOB-verval met de getekende lijn
     meeloopt, twee tegengestelde pijlen als lijn en verval elkaar tegenspreken (blauw
     is de tekenrichting, rood het verval), en een grijze pijl als er geen BOB-verval
     te bepalen valt. Een regelgebaseerde renderer tekent alle regels die passen, dus
     kleur en pijl komen over elkaar heen. -->
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">
    <rules key="{aa000000-0000-4000-8000-000000000000}">
      <rule key="{aa000000-0000-4000-8000-000000000001}" filter="&quot;ergste_ernst&quot; = 'F'" symbol="0" label="Fout"/>
      <rule key="{aa000000-0000-4000-8000-000000000002}" filter="&quot;ergste_ernst&quot; = 'W'" symbol="1" label="Waarschuwing"/>
      <rule key="{aa000000-0000-4000-8000-000000000003}" filter="&quot;ergste_ernst&quot; = 'geen'" symbol="2" label="Geen melding"/>
      <rule key="{aa000000-0000-4000-8000-000000000004}" filter="&quot;richting_bob&quot; = 'mee'" symbol="3" label="BOB volgt de lijnrichting"/>
      <rule key="{aa000000-0000-4000-8000-000000000005}" filter="&quot;richting_bob&quot; = 'tegen'" symbol="4" label="BOB tegen de lijnrichting in"/>
      <rule key="{aa000000-0000-4000-8000-000000000006}" filter="&quot;richting_bob&quot; = 'onbekend'" symbol="5" label="BOB onbekend of vlak"/>
    </rules>
    <symbols>
      <symbol type="line" name="0" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="203,24,29,255"/><prop k="line_width" v="0.9"/></layer></symbol>
      <symbol type="line" name="1" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="230,145,56,255"/><prop k="line_width" v="0.7"/></layer></symbol>
      <symbol type="line" name="2" alpha="1"><layer class="SimpleLine"><prop k="line_color" v="150,150,150,160"/><prop k="line_width" v="0.3"/></layer></symbol>
      <symbol type="line" name="3" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <symbol type="marker" name="@3@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="27,120,55,255"/>
              <prop k="outline_color" v="27,120,55,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol type="line" name="4" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <prop k="offset" v="1.2"/>
          <symbol type="marker" name="@4@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="33,102,172,255"/>
              <prop k="outline_color" v="33,102,172,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <prop k="offset" v="-1.2"/>
          <symbol type="marker" name="@4@1" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="178,24,43,255"/>
              <prop k="outline_color" v="178,24,43,255"/>
              <prop k="size" v="3"/>
              <prop k="angle" v="180"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
      <symbol type="line" name="5" alpha="1">
        <layer class="MarkerLine">
          <prop k="placement" v="centralpoint"/>
          <prop k="rotate" v="1"/>
          <symbol type="marker" name="@5@0" alpha="1">
            <layer class="SimpleMarker">
              <prop k="name" v="filled_arrowhead"/>
              <prop k="color" v="130,130,130,255"/>
              <prop k="outline_color" v="130,130,130,255"/>
              <prop k="size" v="2.6"/>
              <prop k="angle" v="0"/>
            </layer>
          </symbol>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
```

- [ ] **Step 9: Draai de tests**

Run: `uv run pytest -m "not zwaar"`
Verwacht: PASS.

- [ ] **Step 10: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Richtingspijlen op de strengen: tekenrichting en BOB-verval naast elkaar"
```

---

### Taak 8: Stapelende meldingen uit elkaar

Meldingen op dezelfde plek liggen op elkaar en zijn dan onzichtbaar. De geometrie blijft
exact waar de fout zit; de stijl zet de punten op het scherm uiteen, en de kolommen zeggen
ook zonder QGIS dat er meer onder liggen.

**Files:**
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`MELDING_KOLOMMEN`, `_schrijf_meldinglocaties`)
- Modify: `src/nlriochecker/uitvoer/stijlen/meldinglocaties.qml`
- Modify: `tests/test_uitvoer_gpkg.py`

**Interfaces:**
- Consumes: `Melding.foutlocatie`, `Melding.melding_id`.
- Produces: kolommen `stapel_aantal` (integer) en `stapel_nr` (integer, 1-gebaseerd) op `meldinglocaties`.

- [ ] **Step 1: Schrijf de falende test**

```python
def test_meldingen_op_dezelfde_plek_worden_genummerd(tmp_path: Path) -> None:
    """Twee meldingen op hetzelfde punt moeten in de kaart uit elkaar te halen zijn."""
    run = _run("top005_dubbele_put.ttl")
    pad = _schrijf(run, tmp_path)

    rijen = _rijen(
        pad,
        "select stapel_aantal, stapel_nr from meldinglocaties order by stapel_aantal desc, stapel_nr",
    )

    assert rijen
    aantallen = {aantal for aantal, _ in rijen}
    for aantal in aantallen:
        nummers = sorted(nr for a, nr in rijen if a == aantal)
        assert nummers[: aantal] == list(range(1, aantal + 1)) or aantal == 1


def test_stapelnummering_is_stabiel_tussen_runs(tmp_path: Path) -> None:
    run = _run("top005_dubbele_put.ttl")
    eerste = _rijen(_schrijf(run, tmp_path / "a"), "select melding_id, stapel_nr from meldinglocaties order by melding_id")
    tweede = _rijen(_schrijf(run, tmp_path / "b"), "select melding_id, stapel_nr from meldinglocaties order by melding_id")

    assert eerste == tweede
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k stapel -v`
Verwacht: FAIL — de kolommen bestaan niet.

- [ ] **Step 3: Tel en nummer de stapels**

In `src/nlriochecker/uitvoer/gpkg.py`:

```python
# Op welke afstand twee meldingen als dezelfde plek gelden. Een millimeter: kleiner
# dan elke echte afstand in een rioolbestand en groter dan het afrondingsverschil
# tussen twee berekende punten.
STAPEL_RASTER_M = 0.001


def _stapels(meldingen: list[Melding]) -> dict[str, tuple[int, int]]:
    """Per melding het aantal meldingen op haar plek en haar volgnummer daarin.

    De volgorde is die van de melding-ID en niet die van de lijst, zodat twee runs
    over dezelfde data dezelfde nummering opleveren en het kaartbeeld niet
    verspringt.
    """
    per_plek: dict[tuple[int, int], list[str]] = defaultdict(list)
    for melding in sorted(meldingen, key=lambda m: m.melding_id):
        if melding.foutlocatie is None:
            continue
        sleutel = (
            round(melding.foutlocatie.x / STAPEL_RASTER_M),
            round(melding.foutlocatie.y / STAPEL_RASTER_M),
        )
        per_plek[sleutel].append(melding.melding_id)

    return {
        melding_id: (len(groep), nummer)
        for groep in per_plek.values()
        for nummer, melding_id in enumerate(groep, start=1)
    }
```

Voeg `_Kolom("stapel_aantal", "integer")` en `_Kolom("stapel_nr", "integer")` toe aan
`MELDING_KOLOMMEN`. Omdat die lijst ook de tabel `meldingen` vult, krijgt die de kolommen
ook; dat is juist handig, want dan zie je de stapeling ook in de attributentabel. Vul ze in
`_melding_rij(melding, stapel)`; geef de functie de tuple mee die `_stapels()` oplevert,
met `(1, 1)` als terugval voor een melding zonder foutlocatie.

- [ ] **Step 4: Zet de offset in de stijl**

Voeg in `src/nlriochecker/uitvoer/stijlen/meldinglocaties.qml` aan beide
`SimpleMarker`-lagen dit blok toe, direct na de `<prop>`-regels. De expressie is met
PyQGIS gecontroleerd: bij `stapel_aantal = 4` levert ze `0,2.6`, `-2.6,0`, `0,-2.6` en
`2.6,0`.

```xml
          <data_defined_properties>
            <Option type="Map">
              <Option name="name" type="QString" value=""/>
              <Option name="properties" type="Map">
                <Option name="offset" type="Map">
                  <Option name="active" type="bool" value="true"/>
                  <Option name="expression" type="QString" value="if(&quot;stapel_aantal&quot; &lt;= 1, '0,0', format('%1,%2', round(2.6 * cos(radians(360.0 * &quot;stapel_nr&quot; / &quot;stapel_aantal&quot;)), 3), round(2.6 * sin(radians(360.0 * &quot;stapel_nr&quot; / &quot;stapel_aantal&quot;)), 3)))"/>
                  <Option name="type" type="int" value="3"/>
                </Option>
              </Option>
              <Option name="type" type="QString" value="collection"/>
            </Option>
          </data_defined_properties>
```

Werk de commentaarkop van het bestand bij: de punten staan op hun echte plek, de offset is
alleen schermopmaak.

- [ ] **Step 5: Draai de tests**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -v`
Verwacht: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Meldingen op dezelfde plek worden geteld, genummerd en uiteengezet"
```

---

### Taak 9: De analyseset: kern plus contextschil

De kern van de afbakening. Nog zonder aansluiting op de pijplijn: deze taak levert de
bouwsteen en bewijst dat hij de randeffecten wegneemt.

**Files:**
- Create: `src/nlriochecker/afbakening.py`
- Create: `tests/test_afbakening.py`
- Create: `tests/fixtures/ttl/afbakening_kern_en_schil.ttl`
- Create: `tests/fixtures/gis/afbakening_gebied.geojson`
- Modify: `src/nlriochecker/dataset.py` (`GwswDataset.subset`)
- Modify: `src/nlriochecker/checkconfig.py` (`StudyAreaOptions`)
- Modify: `src/nlriochecker/checks.toml` (sectie `[studiegebied]`)
- Modify: `src/nlriochecker/checks/base.py` (`objecten_in_gebied` verhuist naar `afbakening.py`)

**Interfaces:**
- Consumes: `StudyArea.bevat`, `GwswDataset.of_class`, `GwswDataset.resolve_network_node`.
- Produces: `GwswDataset.subset(uris: Iterable[str]) -> GwswDataset`; `Analyseset(kern, schil, dataset, component_aandeel)`; `bouw_analyseset(dataset, area, config) -> Analyseset`; `objecten_in_gebied(dataset, area) -> frozenset[str]` (verhuisd, blijft importeerbaar uit `nlriochecker.checks`).

- [ ] **Step 1: Maak de fixtures**

`tests/fixtures/ttl/afbakening_kern_en_schil.ttl`, naar het model van
`tests/fixtures/ttl/net001_geen_afvoerpad.ttl`:

- putten `A` (1000, 2000), `B` (1050, 2000), `C` (1100, 2000), `D` (1150, 2000);
- een gemaal `G` (1200, 2000);
- vier vuilwaterstrengen: `A-B`, `B-C`, `C-D`, `D-G`, elk met beide BOB's aflopend;
- en een tweede, losstaand netje ver weg: putten `E` (5000, 2000) en `F` (5050, 2000) met
  streng `E-F` ertussen, zonder verbinding met de rest.

`tests/fixtures/gis/afbakening_gebied.geojson`: een enkel vlak
(990, 1990) - (1060, 1990) - (1060, 2010) - (990, 2010), zoals de bestaande
`rond_put_ab.geojson` is opgebouwd.

- [ ] **Step 2: Schrijf de falende tests**

Maak `tests/test_afbakening.py`:

```python
"""Tests voor de afbakening tot een studiegebied.

De vraag die deze tests beantwoorden: krimpt de analyseset genoeg om tijd te
schelen, en groeit hij genoeg om de netwerkchecks hun antwoord te laten houden?
"""

from __future__ import annotations

from pathlib import Path

from nlriochecker.afbakening import bouw_analyseset, objecten_in_gebied
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.studiegebied import load_study_area

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"


def _labels(dataset, uris) -> set[str]:
    """De labels van een verzameling URI's."""
    alles = {**dataset.nodes, **dataset.conduits}
    return {alles[uri].label for uri in uris if uri in alles}


def _opzet():
    """De fixture, het gebied en de config."""
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return dataset, area, config


def test_de_kern_is_wat_het_gebied_raakt() -> None:
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert _labels(dataset, analyseset.kern) == {"A", "B", "A-B", "B-C"}


def test_de_schil_haalt_het_afvoerpad_erbij() -> None:
    """Zonder gemaal G zou NET-001 de hele streng als doodlopend melden."""
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert {"C", "D", "G", "C-D", "D-G"} <= _labels(dataset, analyseset.schil)


def test_een_losstaand_net_blijft_buiten_de_analyseset() -> None:
    """Anders levert de afbakening geen tijdwinst op."""
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert not {"E", "F", "E-F"} & _labels(dataset, analyseset.alles)
    assert set(analyseset.dataset.nodes) | set(analyseset.dataset.conduits) == analyseset.alles


def test_zonder_schil_geeft_net001_een_valse_bevinding() -> None:
    """De reden van bestaan van de contextschil, in een enkele test."""
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    alleen_kern = run_checks(
        CheckContext(dataset=dataset.subset(analyseset.kern), config=config), ["NET-001"]
    )
    met_schil = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config), ["NET-001"]
    )

    assert alleen_kern.outcomes[0].findings, "zonder schil hoort NET-001 juist aan te slaan"
    assert met_schil.outcomes[0].findings == []


def test_de_buffer_haalt_ongekoppelde_buren_erbij() -> None:
    """TOP-005 en de EXT-checks kijken naar nabijheid zonder netwerkverband."""
    dataset, area, config = _opzet()
    config.studiegebied.context_buffer_m = 60.0

    analyseset = bouw_analyseset(dataset, area, config)

    assert "C" in _labels(dataset, analyseset.alles)


def test_objecten_in_gebied_blijft_importeerbaar_uit_checks() -> None:
    """De functie is verhuisd; bestaande importen mogen niet breken."""
    from nlriochecker.checks import objecten_in_gebied as via_checks

    assert via_checks is objecten_in_gebied
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_afbakening.py -v`
Verwacht: FAIL met ModuleNotFoundError voor `nlriochecker.afbakening`.

- [ ] **Step 4: Zet de configuratie neer**

In `src/nlriochecker/checkconfig.py`, naast de andere optieklassen:

```python
class StudyAreaOptions(BaseModel):
    """Hoe de analyse wordt afgebakend als er een studiegebied is opgegeven."""

    model_config = ConfigDict(extra="forbid")

    # Hoe ver om het gebied heen objecten meedoen die geen netwerkverband met de
    # kern hebben. Nodig voor TOP-005, TOP-006, TOP-010, TOP-011, TOP-021 en de
    # EXT-checks, die naar buren kijken zonder de graaf te volgen.
    context_buffer_m: float = Field(default=50.0, ge=0.0)
    # Checks die over de hele populatie gaan in plaats van over losse objecten; die
    # draaien altijd op de volledige export.
    volledige_dataset_checks: list[str] = Field(default_factory=lambda: ["ADM-002"])
    # Boven dit aandeel van de dataset levert de afbakening zo weinig op dat de run
    # dat meldt. Een mededeling, geen fout.
    component_waarschuwingsdrempel: float = Field(default=0.5, gt=0.0, le=1.0)
```

Voeg het veld toe aan `CheckConfig`: `studiegebied: StudyAreaOptions = Field(default_factory=StudyAreaOptions)` (volg de schrijfwijze van de bestaande velden in die klasse).

In `src/nlriochecker/checks.toml`, onderaan:

```toml
# Hoe een analyse wordt afgebakend als er een studiegebied is opgegeven. De checks
# draaien dan op de kern (wat het gebied raakt) plus een contextschil, zodat de
# netwerkchecks hun antwoord houden; gerapporteerd wordt alleen de kern.
[studiegebied]
context_buffer_m = 50.0
volledige_dataset_checks = ["ADM-002"]
component_waarschuwingsdrempel = 0.5
```

- [ ] **Step 5: Zet `subset` op de dataset**

In `src/nlriochecker/dataset.py`, bij de andere methoden van `GwswDataset`:

```python
    def subset(self, uris: Iterable[str]) -> GwswDataset:
        """Dezelfde dataset met alleen deze knopen en verbindingen.

        De rdflib-graaf gaat ongewijzigd mee: hij is de bron waaruit de checks hun
        onderdelen opzoeken, en hem meesnijden zou stilzwijgend gegevens weglaten.
        Alleen `subjects_of_class()` loopt daardoor nog over de volledige export;
        dat zijn de drempels in NET-007 en RVZ, en dat staat in het rapport.
        """
        behouden = frozenset(uris)
        return replace(
            self,
            nodes={uri: node for uri, node in self.nodes.items() if uri in behouden},
            conduits={uri: kant for uri, kant in self.conduits.items() if uri in behouden},
            geometry_errors={
                uri: fout for uri, fout in self.geometry_errors.items() if uri in behouden
            },
        )
```

Voeg `from dataclasses import replace` en `from collections.abc import Iterable` toe aan de
importen als ze er nog niet staan.

- [ ] **Step 6: Schrijf `afbakening.py`**

```python
"""De analyseset: welke objecten met een studiegebied door de checks gaan.

Analyseer de kern plus een contextschil, rapporteer de kern. De schil is precies zo
groot dat de netwerkchecks hun antwoord houden: de samenhangende vrijvervalcomponent
waar de kern in ligt, plus een buffer voor de checks die naar nabijheid kijken zonder
netwerkverband. Zonder die schil zou een streng die het gebied uit loopt als
doodlopend gelden en zouden NET-001 en NET-002 valse bevindingen geven.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.dataset import GwswDataset
from nlriochecker.studiegebied import StudyArea


@dataclass(frozen=True)
class Analyseset:
    """De objecten die met een studiegebied door de checks gaan."""

    kern: frozenset[str]
    schil: frozenset[str]
    dataset: GwswDataset
    volledig_aantal: int

    @property
    def alles(self) -> frozenset[str]:
        """Kern en schil samen: waarover de checks redeneren."""
        return self.kern | self.schil

    @property
    def aandeel(self) -> float:
        """Welk deel van de export de analyseset beslaat."""
        return len(self.alles) / self.volledig_aantal if self.volledig_aantal else 0.0


def objecten_in_gebied(dataset: GwswDataset, area: StudyArea) -> frozenset[str]:
    """De URI's van de objecten waarvan de geometrie het studiegebied raakt."""
    binnen = {uri for uri, node in dataset.nodes.items() if area.bevat(node.point)}
    binnen |= {uri for uri, conduit in dataset.conduits.items() if area.bevat(conduit.line)}
    return frozenset(binnen)


def bouw_analyseset(
    dataset: GwswDataset, area: StudyArea, config: CheckConfig
) -> Analyseset:
    """Bouwt kern en contextschil en levert de uitgedunde dataset."""
    kern = objecten_in_gebied(dataset, area)
    schil = _component(dataset, config, kern) | _binnen_buffer(dataset, area, config)
    schil -= kern
    volledig = len(dataset.nodes) + len(dataset.conduits)
    return Analyseset(
        kern=kern,
        schil=frozenset(schil),
        dataset=dataset.subset(kern | schil),
        volledig_aantal=volledig,
    )


def _component(dataset: GwswDataset, config: CheckConfig, kern: frozenset[str]) -> set[str]:
    """De samenhangende vrijvervalcomponenten die de kern raken.

    Bewust alleen over de vrijvervalleidingen: mechanische leidingen verbinden
    deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen,
    terwijl de NET-checks ze niet volgen.
    """
    wortels = config.klassen.netwerkknopen
    graaf = nx.Graph()
    for wortel in config.klassen.vrijvervalleiding:
        for uri in dataset.of_class(wortel):
            conduit = dataset.conduits.get(uri)
            if conduit is None:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            if begin is None or eind is None:
                continue
            graaf.add_edge(begin, eind, uri=uri)

    gevonden: set[str] = set()
    for knopen in nx.connected_components(graaf):
        if not (knopen & kern) and not any(
            graaf.edges[kant]["uri"] in kern for kant in graaf.subgraph(knopen).edges
        ):
            continue
        gevonden |= knopen
        gevonden |= {graaf.edges[kant]["uri"] for kant in graaf.subgraph(knopen).edges}
    return gevonden


def _binnen_buffer(dataset: GwswDataset, area: StudyArea, config: CheckConfig) -> set[str]:
    """De objecten binnen de contextbuffer om het gebied."""
    afstand = config.studiegebied.context_buffer_m
    if afstand <= 0:
        return set()
    gebufferd = area.geometry.buffer(afstand)
    binnen = {
        uri
        for uri, node in dataset.nodes.items()
        if node.point is not None and not node.point.is_empty and gebufferd.intersects(node.point)
    }
    binnen |= {
        uri
        for uri, kant in dataset.conduits.items()
        if kant.line is not None and not kant.line.is_empty and gebufferd.intersects(kant.line)
    }
    return binnen
```

- [ ] **Step 7: Verhuis `objecten_in_gebied`**

Haal de functie uit `src/nlriochecker/checks/base.py` en importeer haar daar voortaan uit
`nlriochecker.afbakening`, zodat `from nlriochecker.checks import objecten_in_gebied`
blijft werken (`checks/__init__.py` exporteert hem al). Controleer met
`grep -rn "objecten_in_gebied" src tests` dat alle aanroepers nog dezelfde functie krijgen.

- [ ] **Step 8: Draai de tests**

Run: `uv run pytest tests/test_afbakening.py tests/test_studiegebied.py tests/test_checks_netwerk.py -v`
Verwacht: PASS. Daarna de hele suite: `uv run pytest -m "not zwaar"`.

- [ ] **Step 9: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Analyseset: de kern plus de contextschil die de netwerkchecks hun antwoord laat houden"
```

---

### Taak 10: De analyseset in de pijplijn

**Files:**
- Modify: `src/nlriochecker/checks/base.py` (`Check.volledig_bereik`, `CheckContext`, `run_checks`, `CheckRun`)
- Modify: `src/nlriochecker/checks/administratief.py` (ADM-002 krijgt de vlag)
- Modify: `src/nlriochecker/cli.py` (`check_command`)
- Modify: `src/nlriochecker/uitvoer/gpkg.py` (`_schrijf_runmetadata`)
- Modify: `src/nlriochecker/uitvoer/bevindingen.py` (de kop van het rapport)
- Modify: `tests/test_afbakening.py`, `tests/test_cli.py`, `tests/test_reporting.py`

**Interfaces:**
- Consumes: `Analyseset` uit taak 9.
- Produces: `Check.volledig_bereik: ClassVar[bool]`; `CheckContext(volledige_dataset=..., analyseset=...)`; `CheckRun.analyseset`; GPKG-kolommen `kern_objecten`, `schil_objecten`, `dataset_objecten`.

- [ ] **Step 1: Schrijf de falende tests**

Voeg toe aan `tests/test_afbakening.py`:

```python
def test_een_dataset_brede_check_ziet_de_hele_export() -> None:
    """ADM-002 zoekt dubbele identificaties; die kunnen overal zitten."""
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    run = run_checks(context, ["ADM-002", "TOP-001"])
    per_check = {outcome.check_id: outcome for outcome in run.outcomes}

    volledig = len(dataset.nodes) + len(dataset.conduits)
    assert per_check["ADM-002"].examined == volledig
    assert per_check["TOP-001"].examined < volledig


def test_de_run_onthoudt_de_omvang_van_kern_en_schil() -> None:
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    run = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config, analyseset=analyseset),
        ["TOP-001"],
    )

    assert run.analyseset is analyseset
```

En aan `tests/test_cli.py` een test die `toets` met `--studiegebied` draait op de fixture
uit taak 9 en controleert dat de uitvoer de drie getallen noemt:

```python
def test_toets_meldt_de_omvang_van_de_analyseset(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset", str(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            "--studiegebied", str(GIS_DIR / "afbakening_gebied.geojson"),
            "--check", "NET-001",
            "--output", str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "kern" in resultaat.output and "contextschil" in resultaat.output
```

(Volg voor de imports en de opzet de bestaande tests in `tests/test_cli.py`.)

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_afbakening.py tests/test_cli.py -k "dataset_brede or omvang" -v`
Verwacht: FAIL — `CheckContext` kent `volledige_dataset` en `analyseset` niet.

- [ ] **Step 3: Breid het raamwerk uit**

In `src/nlriochecker/checks/base.py`:

```python
@dataclass(frozen=True)
class CheckContext:
    ...
    # Met een studiegebied draaien de checks op de analyseset. Een check met
    # `volledig_bereik` heeft de volledige export nodig; die staat hier.
    volledige_dataset: GwswDataset | None = None
    analyseset: Analyseset | None = None

    def volledige_context(self) -> CheckContext:
        """Dezelfde context, maar over de volledige export.

        Krijgt een eigen cache: de topologie-index en de netwerkgraaf van de
        volledige export zijn andere structuren dan die van de analyseset, en ze
        door elkaar halen zou de verkeerde antwoorden geven.
        """
        if self.volledige_dataset is None or self.volledige_dataset is self.dataset:
            return self
        return self.cached(
            "volledige-context",
            lambda: replace(self, dataset=self.volledige_dataset, _cache={}),
        )
```

Op `Check`:

```python
    # Checks die over de hele populatie gaan in plaats van over losse objecten
    # (ADM-002: dubbele identificaties kunnen overal in de export zitten). Ze
    # draaien ook met een studiegebied op de volledige export.
    volledig_bereik: ClassVar[bool] = False
```

In `run_checks`, per check: `gebruikt = context.volledige_context() if check.volledig_bereik
else context`, en gebruik `gebruikt` voor `examined()`, `run()` en `notes()`. Geef
`analyseset=context.analyseset` mee aan de `CheckRun`, en voeg dat veld toe aan de
dataclass (en aan `beperk_tot_studiegebied`, die de run opnieuw opbouwt).

Zet in `src/nlriochecker/checks/administratief.py` op de ADM-002-klasse
`volledig_bereik = True`, met een regel commentaar waarom.

- [ ] **Step 4: Sluit de CLI aan**

In `src/nlriochecker/cli.py`, in `check_command`, vervang het blok rond `run_checks` door:

```python
        area = load_study_area(study_path, study_layer) if study_path is not None else None
        analyseset = bouw_analyseset(dataset, area, config) if area is not None else None
        context = CheckContext(
            dataset=analyseset.dataset if analyseset is not None else dataset,
            config=config,
            unreliable_objects=onbetrouwbaar,
            plausibiliteit=load_plausibility(plausibility_path),
            bronnen=bronnen,
            volledige_dataset=dataset,
            analyseset=analyseset,
        )
        run = run_checks(context, list(check_ids) or None, typing_gate_applied=gate_applied)
        if area is not None:
            run = run.beperk_tot_studiegebied(area)
```

En bij de meldingen op stdout, waar nu het studiegebied gemeld wordt:

```python
    if run.analyseset is not None:
        stel = run.analyseset
        click.echo(
            f"  Analyseset: {getal(len(stel.kern), 'object', 'objecten')} in de kern, "
            f"{len(stel.schil)} in de contextschil, van {stel.volledig_aantal} in de export."
        )
        if stel.aandeel > config.studiegebied.component_waarschuwingsdrempel:
            click.echo(
                "  Let op: het net binnen dit gebied hangt met vrijwel de hele export samen; "
                "de afbakening levert weinig tijdwinst op."
            )
```

- [ ] **Step 5: Zet de getallen in de uitvoer**

In `_schrijf_runmetadata` (`uitvoer/gpkg.py`) komen drie kolommen bij: `kern_objecten`,
`schil_objecten` en `dataset_objecten`, gevuld uit `run.analyseset` en leeg (None) zonder
studiegebied.

In de kop van het bevindingenrapport (`uitvoer/bevindingen.py`, waar nu het studiegebied
beschreven wordt) komt een regel bij:

```
Analyseset: 1.203 objecten in de kern, 811 in de contextschil, van 46.925 in de export.
De checks redeneren over kern en schil samen; gerapporteerd wordt alleen de kern. Checks
die over de hele populatie gaan (ADM-002) draaien op de volledige export.
```

Zonder studiegebied blijft die regel weg.

- [ ] **Step 6: Draai de tests**

Run: `uv run pytest -m "not zwaar"`
Verwacht: PASS.

- [ ] **Step 7: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "De checks draaien op de analyseset; dataset-brede checks houden de volledige export"
```

---

### Taak 11: Datasetcache

Gemeten op De Wolden (112 MB TTL plus totaal-ontologie, 1.877.729 triples):

| Weg | Schrijven | Lezen | Omvang |
|---|---|---|---|
| TTL opnieuw parsen | — | 176-205 s | — |
| Structuren (knopen, strengen, klassenhierarchie) als pickle | 2,1 s | **1,4 s** | 31 MB |
| De rdflib-graaf als pickle | 23 s | 58 s | 423 MB |
| De rdflib-graaf als N-Triples | 13 s | 118 s | 296 MB |

Daarom: de structuren altijd uit de cache, en de graaf pas inlezen als een check hem echt
aanraakt. Een run met alleen geometrie- en netwerkchecks kost dan seconden; een volledige
registry raakt de graaf (ADM-007 t/m ADM-009, NET-007, de RVZ-checks) en komt op ongeveer
een minuut in plaats van vier.

**Files:**
- Create: `src/nlriochecker/cache.py`
- Create: `tests/test_cache.py`
- Modify: `src/nlriochecker/cli.py` (`check_command`: opties en melding)

**Interfaces:**
- Consumes: `load_dataset(path, ontologies) -> GwswDataset`.
- Produces: `cachesleutel(dataset_path, ontology_paths) -> str`; `laad_met_cache(dataset_path, ontology_paths, cache_dir=None, gebruik_cache=True) -> tuple[GwswDataset, CacheUitslag]`; `CacheUitslag(bron, sleutel, seconden, melding)`.

- [ ] **Step 1: Schrijf de falende tests**

Maak `tests/test_cache.py`:

```python
"""Tests voor de datasetcache.

De cache mag nooit een ander antwoord geven dan opnieuw inlezen. Het gevaarlijkste
geval is een cache die achterloopt op de lader; daarom zit de broncode van de lader
in de sleutel.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.cache import cachesleutel, laad_met_cache
from nlriochecker.dataset import load_dataset

DATA = Path(__file__).resolve().parents[1] / "data"
VOORBEELD = DATA / "gwsw_orox_ttl" / "GwswDataset__Voorbeeld_v1_6_orox.ttl"

pytestmark = pytest.mark.skipif(
    not VOORBEELD.exists(), reason="het OroX-voorbeeldbestand staat niet in data/"
)


def test_de_cache_geeft_dezelfde_dataset_terug(tmp_path: Path) -> None:
    koud, eerste = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    warm, tweede = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)

    assert eerste.bron == "bestand"
    assert tweede.bron == "cache"
    assert set(warm.nodes) == set(koud.nodes)
    assert set(warm.conduits) == set(koud.conduits)
    assert warm.subclasses == koud.subclasses
    assert warm.source == koud.source


def test_de_graaf_werkt_ook_uit_de_cache(tmp_path: Path) -> None:
    """De graaf wordt lui geladen; hij moet zich als een graaf blijven gedragen."""
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    warm, _ = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    vers = load_dataset(VOORBEELD, [])

    assert len(warm.graph) == len(vers.graph)
    uri = next(iter(warm.nodes))
    assert set(warm.subjects_of_class("Put")) == set(vers.subjects_of_class("Put"))
    assert warm.beheerobjecttype(uri) == vers.beheerobjecttype(uri)


def test_de_sleutel_verandert_mee_met_de_lader(tmp_path: Path, monkeypatch) -> None:
    eerste = cachesleutel(VOORBEELD, [])
    monkeypatch.setattr("nlriochecker.cache.LADER_VERSIE", "gewijzigd")

    assert cachesleutel(VOORBEELD, []) != eerste


def test_een_beschadigde_cache_leidt_tot_opnieuw_inlezen(tmp_path: Path) -> None:
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    for bestand in tmp_path.rglob("*.pickle"):
        bestand.write_bytes(b"dit is geen pickle")

    dataset, uitslag = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)

    assert dataset.nodes
    assert uitslag.bron == "bestand"
    assert "cache" in uitslag.melding.lower()


def test_zonder_cache_wordt_er_niets_weggeschreven(tmp_path: Path) -> None:
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path, gebruik_cache=False)

    assert list(tmp_path.rglob("*.pickle")) == []
```

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_cache.py -v`
Verwacht: FAIL met ModuleNotFoundError.

- [ ] **Step 3: Schrijf `cache.py`**

```python
"""De geparseerde dataset bewaren, zodat een tweede run niet opnieuw hoeft te parsen.

Gemeten op De Wolden: het TTL parsen kost circa 180 s, de structuren teruglezen 1,4 s
en de rdflib-graaf teruglezen 58 s. De graaf wordt daarom pas ingelezen als een check
hem aanraakt; wie alleen geometrie- en netwerkchecks draait, betaalt hem niet.

Het gevaar van een cache is dat hij achterloopt. De sleutel bevat daarom niet alleen
de inhoud van de invoerbestanden maar ook de broncode van de lader en de versies van
rdflib en shapely: wijzigt daar iets, dan is het een andere sleutel en wordt er
opnieuw ingelezen.
"""

from __future__ import annotations

import os
import pickle
import time
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

import rdflib
import shapely
from rdflib import Graph

from nlriochecker import dataset as dataset_module
from nlriochecker import geometry as geometry_module
from nlriochecker.dataset import GwswDataset, load_dataset

# Losstaand van de bestandshashes, zodat een test hem kan verzetten.
LADER_VERSIE = "1"

BESTAND_STRUCTUREN = "structuren.pickle"
BESTAND_GRAAF = "graaf.pickle"


@dataclass(frozen=True)
class CacheUitslag:
    """Waar de dataset vandaan kwam en wat dat kostte."""

    bron: str  # 'cache' of 'bestand'
    sleutel: str
    seconden: float
    melding: str = ""


class LuieGraaf:
    """Een rdflib-graaf die pas van schijf komt als er iets uit gevraagd wordt.

    De checks gebruiken de graaf voor onderdelen die niet in de structuren zitten
    (hasPart, hasConnection, labels van drempels). Dat is een minderheid van de
    checks, en de graaf teruglezen kost 58 s; hem pas laden bij het eerste gebruik
    scheelt die tijd in alle andere runs.
    """

    def __init__(self, pad: Path) -> None:
        self._pad = pad
        self._graaf: Graph | None = None

    def _geladen(self) -> Graph:
        """Leest de graaf de eerste keer dat er iets uit gevraagd wordt."""
        if self._graaf is None:
            with self._pad.open("rb") as bestand:
                self._graaf = pickle.load(bestand)
        return self._graaf

    def __getattr__(self, naam: str):
        """Alles wat een graaf kan, kan deze plaatsvervanger ook."""
        return getattr(self._geladen(), naam)

    def __len__(self) -> int:
        """Het aantal triples."""
        return len(self._geladen())

    def __contains__(self, triple) -> bool:
        """Of een triple in de graaf staat."""
        return triple in self._geladen()

    def __iter__(self):
        """De triples zelf."""
        return iter(self._geladen())


def cachesleutel(dataset_path: Path, ontology_paths: list[Path]) -> str:
    """De sleutel van deze combinatie van invoer, lader en bibliotheken."""
    haas = sha256()
    haas.update(LADER_VERSIE.encode("utf-8"))
    haas.update(f"rdflib{rdflib.__version__}shapely{shapely.__version__}".encode())
    for module in (dataset_module, geometry_module):
        haas.update(Path(module.__file__).read_bytes())
    for pad in [Path(dataset_path), *sorted(Path(p) for p in ontology_paths)]:
        haas.update(pad.name.encode("utf-8"))
        haas.update(_bestandshash(pad).encode("utf-8"))
    return haas.hexdigest()[:32]


def _bestandshash(pad: Path) -> str:
    """De sha256 van een bestand, in blokken gelezen."""
    haas = sha256()
    with pad.open("rb") as bestand:
        for blok in iter(lambda: bestand.read(1 << 20), b""):
            haas.update(blok)
    return haas.hexdigest()


def standaard_cachemap() -> Path:
    """De cachemap volgens de XDG-conventie."""
    basis = os.environ.get("XDG_CACHE_HOME")
    return Path(basis or Path.home() / ".cache") / "nlriochecker"


def laad_met_cache(
    dataset_path: Path,
    ontology_paths: list[Path],
    cache_dir: Path | None = None,
    gebruik_cache: bool = True,
) -> tuple[GwswDataset, CacheUitslag]:
    """Leest de dataset uit de cache, of leest hem in en legt hem weg."""
    begin = time.perf_counter()
    if not gebruik_cache:
        dataset = load_dataset(dataset_path, ontology_paths)
        return dataset, CacheUitslag("bestand", "", time.perf_counter() - begin)

    sleutel = cachesleutel(dataset_path, ontology_paths)
    map_ = (cache_dir or standaard_cachemap()) / sleutel
    melding = ""
    if (map_ / BESTAND_STRUCTUREN).exists() and (map_ / BESTAND_GRAAF).exists():
        try:
            with (map_ / BESTAND_STRUCTUREN).open("rb") as bestand:
                velden = pickle.load(bestand)
            dataset = replace(
                GwswDataset(graph=Graph(), **velden), graph=LuieGraaf(map_ / BESTAND_GRAAF)
            )
            return dataset, CacheUitslag("cache", sleutel, time.perf_counter() - begin)
        except (pickle.UnpicklingError, EOFError, TypeError, AttributeError) as fout:
            melding = f"De cache in {map_} is onbruikbaar ({fout}); opnieuw ingelezen."

    dataset = load_dataset(dataset_path, ontology_paths)
    _schrijf(map_, dataset)
    return dataset, CacheUitslag("bestand", sleutel, time.perf_counter() - begin, melding)


def _schrijf(map_: Path, dataset: GwswDataset) -> None:
    """Legt structuren en graaf weg, elk via een tijdelijk bestand.

    Zonder die omweg laat een afgebroken run een half bestand achter dat de volgende
    run als geldige cache zou lezen.
    """
    map_.mkdir(parents=True, exist_ok=True)
    velden = {
        naam: waarde for naam, waarde in vars(dataset).items() if naam != "graph"
    }
    for naam, inhoud in ((BESTAND_STRUCTUREN, velden), (BESTAND_GRAAF, dataset.graph)):
        tijdelijk = map_ / f"{naam}.tijdelijk"
        with tijdelijk.open("wb") as bestand:
            pickle.dump(inhoud, bestand, protocol=5)
        tijdelijk.replace(map_ / naam)
```

- [ ] **Step 4: Draai de tests**

Run: `uv run pytest tests/test_cache.py -v`
Verwacht: PASS.

- [ ] **Step 5: Sluit de CLI aan**

Voeg aan `check_command` in `src/nlriochecker/cli.py` twee opties toe:

```python
@click.option(
    "--geen-cache",
    "geen_cache",
    is_flag=True,
    help="Lees de dataset opnieuw in plaats van uit de cache; ook geen cache wegschrijven.",
)
@click.option(
    "--cache-map",
    "cache_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Waar de geparseerde dataset bewaard wordt; standaard ~/.cache/nlriochecker.",
)
```

Vervang `dataset = load_dataset(dataset_path, list(ontology_paths))` door:

```python
        dataset, cache = laad_met_cache(
            dataset_path, list(ontology_paths), cache_dir, not geen_cache
        )
```

en meld het resultaat bij de andere regels op stdout:

```python
    herkomst = "uit de cache" if cache.bron == "cache" else "ingelezen"
    click.echo(f"  Dataset {herkomst} in {cache.seconden:.1f} s.")
    if cache.melding:
        click.echo(f"  {cache.melding}")
```

- [ ] **Step 6: Draai de tests**

Run: `uv run pytest -m "not zwaar"`
Verwacht: PASS.

- [ ] **Step 7: Meet het effect**

```bash
rm -rf ~/.cache/nlriochecker
time uv run nlriochecker toets --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --studiegebied data/gis/cbs_buurt_koekangerveld_studiegebied.gpkg \
  --bronnen data/gis --output uitvoer/koekangerveld_ronde3
time uv run nlriochecker toets --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --studiegebied data/gis/cbs_buurt_koekangerveld_studiegebied.gpkg \
  --bronnen data/gis --output uitvoer/koekangerveld_ronde3
```

Noteer beide tijden en de omvang van de cachemap (`du -sh ~/.cache/nlriochecker`) voor het
verslag in taak 12. Loopt de warme run niet merkbaar sneller, ga dan niet verder maar zoek
uit waarom; dat is dan een bevinding, geen tegenvaller om weg te schrijven.

- [ ] **Step 8: Commit**

```bash
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Datasetcache: de structuren altijd, de rdflib-graaf pas als een check hem raakt"
```

---

### Taak 12: Sluitstuk — QGIS-smoketest, zware test, documentatie

**Files:**
- Create: `tests/test_uitvoer_qgis.py`
- Modify: `tests/test_integration.py` (zware test voor de afbakening)
- Modify: `pyproject.toml` (marker `qgis` naast `zwaar`, als markers daar gedeclareerd staan)
- Modify: `CLAUDE.md`
- Create: `docs/ronde2-verslag.md`

**Interfaces:**
- Consumes: alles uit de taken hiervoor.
- Produces: geen code-interface; de test bewaakt dat QGIS de stijlen toepast.

- [ ] **Step 1: Schrijf de QGIS-smoketest**

```python
"""Controleert met QGIS zelf dat de stijlen uit het bestand geladen worden.

Deze test is de enige die het echte antwoord geeft op de vraag waar ronde 2 mee
begon: past QGIS de meegeleverde stijlen toe? Hij wordt overgeslagen waar PyQGIS
niet geinstalleerd is, want QGIS is geen afhankelijkheid van dit project.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

qgis_core = pytest.importorskip("qgis.core", reason="PyQGIS is hier niet geinstalleerd")

from nlriochecker.checkconfig import load_check_config  # noqa: E402
from nlriochecker.checks import CheckContext, run_checks  # noqa: E402
from nlriochecker.dataset import load_dataset  # noqa: E402
from nlriochecker.uitvoer.gpkg import FEATURELAGEN, schrijf_geopackage  # noqa: E402
from nlriochecker.uitvoer.melding import bouw_meldingen  # noqa: E402

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
RUNDATUM = date(2026, 8, 16)


@pytest.fixture(scope="module")
def qgis_app():
    """Een QGIS-toepassing zonder scherm, een keer per module."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qgis_core.QgsApplication.setPrefixPath("/usr", True)
    app = qgis_core.QgsApplication([], False)
    app.initQgis()
    yield app
    app.exitQgis()


@pytest.fixture(scope="module")
def geschreven_gpkg(tmp_path_factory) -> Path:
    """Een GeoPackage van de mechanische fixture, met alle vier de lagen."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config))
    map_ = tmp_path_factory.mktemp("qgis")
    return schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), map_, RUNDATUM)


@pytest.mark.parametrize("laag", FEATURELAGEN)
def test_qgis_laadt_de_stijl_uit_het_bestand(qgis_app, geschreven_gpkg: Path, laag: str) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")

    assert vector.isValid(), f"laag {laag} is niet leesbaar"
    boodschap, gelukt = vector.loadDefaultStyle()

    assert gelukt, f"QGIS past de stijl van {laag} niet toe: {boodschap}"
    assert "Provider" in boodschap


def test_de_stijl_van_de_strengen_kent_de_richtingsregels(qgis_app, geschreven_gpkg: Path) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=strengen", "s", "ogr")
    vector.loadDefaultStyle()

    labels = {regel.label() for regel in vector.renderer().rootRule().children()}

    assert {"BOB volgt de lijnrichting", "BOB tegen de lijnrichting in", "BOB onbekend of vlak"} <= labels


def test_elke_stijlexpressie_verwijst_naar_bestaande_kolommen(qgis_app, geschreven_gpkg: Path) -> None:
    """Een tikfout in een kolomnaam levert een lege kaart op, geen foutmelding."""
    for laag in FEATURELAGEN:
        vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")
        vector.loadDefaultStyle()
        velden = set(vector.fields().names())
        renderer = vector.renderer()
        expressies = [renderer.filter()] if hasattr(renderer, "filter") else []
        if hasattr(renderer, "rootRule"):
            expressies += [regel.filterExpression() for regel in renderer.rootRule().children()]
        for tekst in filter(None, expressies):
            gebruikt = set(qgis_core.QgsExpression(tekst).referencedColumns())
            assert gebruikt <= velden, f"{laag}: {tekst} verwijst naar {gebruikt - velden}"
```

- [ ] **Step 2: Draai hem**

Run: `uv run pytest tests/test_uitvoer_qgis.py -v`
Verwacht: PASS op deze machine (QGIS staat op `/usr/bin/qgis`); overgeslagen waar PyQGIS
ontbreekt. Slaagt hij niet, dan is de stijl stuk — niet de test.

- [ ] **Step 3: Schrijf de zware test voor de afbakening**

Voeg toe aan `tests/test_integration.py`:

```python
@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DE_WOLDEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden-OroX of het studiegebied staat niet in data/",
)
def test_afbakening_op_koekangerveld_verandert_de_bevindingen_niet() -> None:
    """De contextschil mag de uitkomst op de kern niet veranderen, alleen sneller maken."""
    dataset = load_dataset(OROX_DE_WOLDEN, [ONTOLOGIE_TOTAAL])
    config = load_check_config()
    area = load_study_area(STUDIEGEBIED)
    ids = ["NET-001", "NET-002", "NET-004", "TOP-001", "TOP-005"]

    volledig = run_checks(CheckContext(dataset=dataset, config=config), ids)
    volledig = volledig.beperk_tot_studiegebied(area)

    analyseset = bouw_analyseset(dataset, area, config)
    afgebakend = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config, analyseset=analyseset), ids
    )
    afgebakend = afgebakend.beperk_tot_studiegebied(area)

    def sleutel(run):
        return sorted(
            (finding.check_id, finding.object_uri) for finding in run.findings
        )

    assert sleutel(afgebakend) == sleutel(volledig)
    assert len(analyseset.alles) < len(dataset.nodes) + len(dataset.conduits)
```

- [ ] **Step 4: Draai de zware tests**

Run: `uv run pytest -m zwaar -v`
Verwacht: PASS. Duurt minuten; dat hoort.

- [ ] **Step 5: Werk CLAUDE.md bij**

In de sectie "Studiegebied (data/gis/)": vervang de regel die begint met "Analyseer breed,
rapporteer smal" door:

```markdown
- Analyseer de kern plus een contextschil, rapporteer de kern. De schil is de
  samenhangende vrijvervalcomponent waar de kern in ligt plus een buffer om het gebied;
  precies zo groot dat NET-001 en NET-002 geen valse bevindingen geven. Zonder
  studiegebied draait alles op de volledige dataset. Meld altijd hoeveel bevindingen
  buiten het gebied vielen en hoe groot kern, schil en export zijn.
```

Voeg aan de sectie "Technische afspraken" toe:

```markdown
- De QGIS-stijlen gaan mee in de tabel `layer_styles` van de GeoPackage, die zelf in
  `gpkg_contents` geregistreerd moet staan; zonder die rij vindt QGIS haar niet. Een QML
  los naast het bestand werkt niet bij meerdere lagen en leggen we dus niet neer.
- De geparseerde dataset wordt gecachet (`~/.cache/nlriochecker`, `--geen-cache` om hem
  over te slaan). De sleutel bevat de broncode van de lader; wie `dataset.py` of
  `geometry.py` wijzigt, krijgt vanzelf een nieuwe cache.
```

Werk ook de sectie "Open punten" bij: het punt over de 1773 doodlopende eindknopen krijgt
de aantekening dat de contextschil dit voor een afgebakende run niet meer beinvloedt.

- [ ] **Step 6: Schrijf het verslag**

Maak `docs/ronde2-verslag.md` naar het model van `docs/ronde1-gpkg-en-rapport-verslag.md`:
de brainstormkeuzes, wat er per punt gebouwd is, waar je van het ontwerp afweek en waarom,
de gemeten looptijden uit taak 11 stap 7, en wat er open blijft (het pruimen van de graaf
in de cache, de koude run die nog steeds 180 s parst).

- [ ] **Step 7: Draai alles en commit**

```bash
uv run pytest -m "not zwaar"
uv run pytest -m zwaar
uv run ruff check && uv run ruff format --check
git add -A
git commit -m "Sluitstuk ronde 2: QGIS-smoketest, afbakeningstest op De Wolden en de verslaglegging"
```

- [ ] **Step 8: Vraag een codereview aan**

Volg de projectafspraak uit CLAUDE.md: `/superpowers:requesting-code-review` en verwerk de
uitkomsten voordat je de ronde afsluit.

---

## Volgorde en afhankelijkheden

Taken 1 tot en met 3 raken het contract en gaan voorop. Taken 4 tot en met 8 zijn
onderling onafhankelijk en kunnen in elke volgorde; ze raken alle `uitvoer/gpkg.py`, dus
achter elkaar uitvoeren scheelt samenvoegwerk. Taak 9 moet voor taak 10, en taak 10 voor
taak 11 (die de CLI op dezelfde plek aanpast). Taak 12 sluit af en verwacht alle
voorgaande.
