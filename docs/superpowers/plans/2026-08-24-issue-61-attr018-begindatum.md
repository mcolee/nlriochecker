# Issue #61: ATTR-018 ontbrekende begindatum en de kolom `begindatum_jaar` — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een nieuwe check **ATTR-018** (F, Compleetheid) meldt per vrijvervalrioolleiding en per put dat de `Begindatum` ontbreekt, zodat het gat in alle vier de uitvoervormen landt en het object op de kaart kleurt; de GeoPackage-lagen `putten` en `strengen` krijgen een kolom `begindatum_jaar`; de dubbele telling in `notes()` van ATTR-007 vervalt.

**Architecture:** De check komt in `src/nlriochecker/checks/attributen.py` naast ATTR-007 en gebruikt dezelfde populatie (`vrijvervalrioolleidingen` + `putten` uit `checks/selectie.py`). Via de meldingenstroom (`uitvoer/melding.py`) landt hij vanzelf in Markdown, CSV, GeoPackage en JSON. De kolom komt in `_samenvatting_kolommen()` en `_samenvatting()` in `src/nlriochecker/uitvoer/gpkg.py`; de waarde volgt uit `object_.date("Begindatum")`, dat `Node` en `Conduit` allebei via `_MetAspecten` hebben.

**Tech Stack:** Python 3.12, pytest, sqlite3 (bestaand). Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #61 (`gh issue list --json number,body --search 61`).

## Global Constraints

- Check-ID **ATTR-018**, ernst `Severity.ERROR` (F), dimensie `Dimension.COMPLETENESS` (Compleetheid). `tests/test_checks_registry.py::test_ernst_en_dimensie_volgen_het_register` eist dat de registerregel dezelfde ernst en dimensie draagt.
- Populatie: `vrijvervalrioolleidingen(context)` plus `putten(context)`; `examined` = de som van beide. Mechanisch riool en andere niet-vrijvervalleidingen vallen erbuiten en worden in `notes()` geteld (aantal buiten de toets, en hoeveel daarvan geen begindatum dragen).
- Alleen `Begindatum`; `Einddatum` blijft bij ADM-006.
- ATTR-007 houdt zijn eerste notitieregel ("… in deze toets dragen geen begindatum en zijn niet getoetst") en verliest de tweede ("In deze meetset hebben … geen begindatum; …").
- Kolom `begindatum_jaar` (`integer`, leeg zonder datum) in **beide** objectlagen, direct na `stelsel` in `_samenvatting_kolommen()` en op dezelfde positie in de tuple van `_samenvatting()`.
- Gegenereerde bestanden nooit met de hand bewerken: `tests/fixtures/ttl/*.ttl` via `uv run python scripts/maak_ttl_fixtures.py`, `docs/dekkingsmatrix.md` via `uv run python scripts/dekkingsmatrix.py`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten; volg de stijl van `attributen.py` en `gpkg.py`. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden, nooit `git add -A` (er staan ongecommitte planbestanden van andere issues in de werkmap).
- Nieuw BO-nummer: het eerstvolgende na het laatste `### BO-` in `docs/beslislog.md` (verwacht **BO-45**; controleer met `grep -n '^### BO-' docs/beslislog.md | tail -1`). Gebruik dat nummer overal waar dit plan `BO-45` schrijft.
- CHANGELOG: een kop `### Toegevoegd` onder `## [Unreleased]`, **boven** de bestaande koppen (`### Gewijzigd` en `### Gerepareerd`). Bestaat `### Toegevoegd` al onder Unreleased, voeg de regel daar bovenaan toe.

---

### Task 1: ATTR-018, ATTR-007-notitie, fixture, tests, register en documentatie

**Files:**
- Modify: `scripts/maak_ttl_fixtures.py` (nieuwe fixture na `attr007_toekomstig_jaar.ttl`, regel ~908)
- Regenerate: `tests/fixtures/ttl/attr018_zonder_begindatum.ttl`
- Modify: `src/nlriochecker/checks/attributen.py:758-834` (ATTR-007 `notes`), nieuwe klasse direct ná ATTR-007 en vóór `class BegindatumVulwaardejaar`
- Modify: `tests/test_checks_blok_a.py` (`DEFECTEN`-rij, `test_attr007_verantwoordt_de_objecten_zonder_begindatum`, twee nieuwe tests)
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md` (rij na ATTR-017 op regel 91; addendum in Versiehistorie), regenerate `docs/dekkingsmatrix.md`
- Modify: `docs/beslislog.md` (BO-45), `CHANGELOG.md`

**Interfaces:**
- Consumes: `vrijvervalrioolleidingen(context) -> list[Conduit]`, `putten(context) -> list[Node]`, `leidingen(context) -> list[Conduit]` uit `nlriochecker.checks.selectie`; `object_.date("Begindatum") -> date | None`; `self.finding(context, uri, label, message, **details)`; `nette_put`, `nette_leiding`, `leiding`, `put` uit de fixturegenerator (`kenmerken()` slaat een `None`-waarde over, dus `velden={"Begindatum": None}` geeft een leiding zónder begindatum).
- Produces: `REGISTRY["ATTR-018"]` (klasse `BegindatumOntbreekt`), bevindingen met `details["objectsoort"]` (`"streng"` of `"put"`).

- [ ] **Step 1: Fixture (generator, niet het bestand)**

In `scripts/maak_ttl_fixtures.py`, direct ná het blok `FIXTURES["attr007_toekomstig_jaar.ttl"] = (...)` en vóór `FIXTURES["attr008_lange_streng.ttl"]`, toevoegen:

```python
# ATTR-018: streng 1 en put A dragen geen begindatum en melden; streng 2 en put B
# dragen er wel een en zwijgen; persleiding 3 draagt er geen maar valt buiten de
# populatie (mechanisch riool) en zwijgt ook. `kenmerken()` slaat een None-waarde
# over, dus `velden={"Begindatum": None}` haalt de standaarddatum van nette_leiding weg.
FIXTURES["attr018_zonder_begindatum.ttl"] = (
    "streng 1 en put A hebben geen begindatum; streng 2, put B en persleiding 3 zijn "
    "geen bevinding (issue #61)",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B, Begindatum="1985-01-01")
    + nette_put("PutC", "C", *C, Begindatum="1985-01-01")
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"Begindatum": None})
    + nette_leiding("L2", "2", [B, C], "PutB", "PutC")
    + nette_leiding("L3", "3", [C, D], "PutC", "PutD", klasse="Persleiding", velden={"Begindatum": None})
    + nette_put("PutD", "D", *D, Begindatum="1985-01-01"),
)
```

Controleer eerst dat `nette_leiding` een `klasse=`-argument doorgeeft aan `leiding` (dat doet het via `**extra`) en dat `Persleiding` in de gedeelde prelude staat (`grep -n 'gwsw:Persleiding rdfs:subClassOf' scripts/maak_ttl_fixtures.py` → regel 41). Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. Controleer met `git status --short` dat alleen `tests/fixtures/ttl/attr018_zonder_begindatum.ttl` nieuw is; andere fixtures mogen niet veranderen.

- [ ] **Step 2: Schrijf de falende tests**

In `tests/test_checks_blok_a.py`:

1. In `DEFECTEN`, direct ná de rij `("attr007_toekomstig_jaar.ttl", "ATTR-007", ["1"]),`:

```python
    # ATTR-018: alleen de vrijvervalstreng en de put zonder begindatum; persleiding 3
    # valt buiten de populatie.
    ("attr018_zonder_begindatum.ttl", "ATTR-018", ["1", "A"]),
```

2. Vervang `test_attr007_verantwoordt_de_objecten_zonder_begindatum` door:

```python
def test_attr007_verantwoordt_de_objecten_zonder_begindatum() -> None:
    """De putten zonder begindatum horen in de toelichting; de meetsettelling niet meer.

    De fixture heeft twee putten zonder begindatum en een streng met een (te toekomstige)
    datum. De tweede regel van voorheen ("In deze meetset hebben … geen begindatum")
    telde wat ATTR-018 nu per object meldt; twee plekken die hetzelfde zeggen lopen
    uit elkaar (issue #61).
    """
    outcome = uitkomst("attr007_toekomstig_jaar.ttl", "ATTR-007")

    assert any("2 van de 2 putten in deze toets" in note for note in outcome.notes), outcome.notes
    assert not any("meetset" in note for note in outcome.notes), outcome.notes
```

3. Direct daarna twee nieuwe tests:

```python
def test_attr018_meldt_per_object_en_benoemt_de_soort() -> None:
    """Streng 1 en put A missen de begindatum; de melding zegt welke soort object het is."""
    outcome = uitkomst("attr018_zonder_begindatum.ttl", "ATTR-018")

    per_label = {f.object_label: f for f in outcome.findings}
    assert set(per_label) == {"1", "A"}
    assert per_label["1"].details["objectsoort"] == "streng"
    assert per_label["A"].details["objectsoort"] == "put"
    assert all("begindatum" in f.message.lower() for f in outcome.findings)
    # Twee vrijvervalstrengen plus vier putten; de persleiding telt niet mee.
    assert outcome.examined == 6


def test_attr018_verantwoordt_de_leidingen_buiten_de_populatie() -> None:
    """De persleiding zonder begindatum is geen bevinding, maar hoort wel geteld te zijn."""
    outcome = uitkomst("attr018_zonder_begindatum.ttl", "ATTR-018")

    assert any(
        "1 van de 3 leidingen" in note and "geen vrijvervalrioolleiding" in note and "1 zonder" in note
        for note in outcome.notes
    ), outcome.notes
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checks_blok_a.py -k "attr018 or attr007" -v`
Expected: FAIL — `test_defect_wordt_gevonden[attr018…]` en de twee ATTR-018-tests met `KeyError: 'ATTR-018'` (of een vergelijkbare fout uit `run_checks` op een onbekend ID), `test_attr007_…` op de `meetset`-assertie.

- [ ] **Step 4: Implementeer de check en kort ATTR-007 in**

1. In `src/nlriochecker/checks/attributen.py`, breid de import uit `nlriochecker.checks.selectie` uit met `leidingen` als die er nog niet staat (hij staat er: regel 28). Geen andere imports nodig.

2. In `BegindatumBuitenBereik.notes` (ATTR-007): vervang de hele methode door

```python
    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de objecten zonder begindatum, uitgesplitst naar strengen en putten.

        Geen melding en geen drempel: een grens voor "te weinig gedateerd" hebben we
        niet en zouden we verzinnen. Zonder deze regel leest een schone ATTR-007 als
        "alle aanlegdatums gecontroleerd", terwijl een groot deel van de objecten er
        geen draagt (issue #21). Dat gat zelf meldt ATTR-018 per object (issue #61);
        deze regel zegt alleen wat ATTR-007 daardoor niet kon toetsen.
        """
        strengen = vrijvervalrioolleidingen(context)
        alle_putten = putten(context)
        zonder_streng = sum(1 for conduit in strengen if conduit.date("Begindatum") is None)
        zonder_put = sum(1 for node in alle_putten if node.date("Begindatum") is None)

        if not (zonder_streng or zonder_put):
            return []
        return [
            f"{zonder_streng} van de {len(strengen)} strengen en {zonder_put} van de "
            f"{len(alle_putten)} putten in deze toets dragen geen begindatum en zijn niet "
            "getoetst."
        ]
```

3. Direct ná de klasse `BegindatumBuitenBereik` (na haar `examined`) en vóór `@register\nclass BegindatumVulwaardejaar` de nieuwe check:

```python
@register
class BegindatumOntbreekt(Check):
    """ATTR-018: een vrijvervalrioolleiding of put zonder begindatum.

    ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een *aanwezige* datum en de
    SHACL-nulmeting eist `Begindatum` nergens, zodat een object zonder aanlegjaar tot
    dit issue nergens een melding kreeg en op de kaart groen bleef -- en groen betekent
    daar "beoordeeld en niets gevonden". Zonder aanlegjaar is er geen
    vervangingsplanning, geen levensduurberekening en geen ATTR-003; vandaar een fout
    en niet een waarschuwing. Op De Wolden en Hoogeveen zijn het er ongeveer 9274,
    vooral putten; dat is het echte gat en geen modelleerfout (issue #61).
    """

    id = "ATTR-018"
    title = "Begindatum ontbreekt"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke vrijvervalstreng en elke put zonder `Begindatum`."""
        alles: list[Node | Conduit] = [*vrijvervalrioolleidingen(context), *putten(context)]
        for object_ in alles:
            if object_.date("Begindatum") is not None:
                continue
            soort = "streng" if isinstance(object_, Conduit) else "put"
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"Deze {soort} draagt geen begindatum; het aanlegjaar is onbekend.",
                objectsoort=soort,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de leidingen buiten de populatie.

        Mechanisch riool valt buiten het checkregister en andere leidingen (loze
        leidingen, duikers) zijn geen vrijvervalrioolleiding; ook daar ontbreekt het
        aanlegjaar vaak. Zonder deze regel leest de telling als het hele gat.
        """
        vrijverval = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
        alle = leidingen(context)
        buiten = [conduit for conduit in alle if conduit.uri not in vrijverval]
        if not buiten:
            return []
        zonder = sum(1 for conduit in buiten if conduit.date("Begindatum") is None)
        return [
            f"{len(buiten)} van de {len(alle)} leidingen vallen buiten deze toets omdat ze "
            "geen vrijvervalrioolleiding zijn (mechanisch riool en andere leidingen); "
            f"daarvan zijn er {zonder} zonder begindatum."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal vrijvervalstrengen plus putten."""
        return len(vrijvervalrioolleidingen(context)) + len(putten(context))
```

De test uit Step 2 eist letterlijk `"1 van de 3 leidingen"`, `"geen vrijvervalrioolleiding"` en `"1 zonder"` in één notitie; `"zijn er 1 zonder begindatum"` bevat dat laatste. Telt de notitie de persleiding niet (0 van de 3), controleer dan de subklasseketen in de prelude van de generator (`Persleiding` → `MechanischeTransportleiding` → … → `Leiding`); `leidingen()` selecteert op `klassen.streng`.

- [ ] **Step 5: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_checks_blok_a.py tests/test_ttl_fixtures.py tests/test_checks_registry.py -q`
Expected: `test_checks_blok_a.py` en `test_ttl_fixtures.py` PASS; `test_checks_registry.py::test_ernst_en_dimensie_volgen_het_register[ATTR-018]` faalt nog tot Step 6 de registerregel toevoegt (of `test_geen_check_zonder_registerregel` in `test_dekkingsmatrix.py`). Ga door naar Step 6 en draai daarna de hele suite: `uv run pytest -q`.

Valt een andere test (bv. `test_karakteristiek.py`, `test_uitvoer_*.py`, `test_toetsrun.py`) omdat er nu een check méér in `REGISTRY` staat of omdat ATTR-018 op een bestaande fixture meldt: lees de assertie, bepaal of het nieuwe getal het gevolg is van ATTR-018 en werk de verwachting bij met een regel commentaar waarom. Verklaar elke aangepaste verwachting in je rapport. Een test die om een andere reden faalt is een bug in je wijziging.

- [ ] **Step 6: Register, dekkingsmatrix, beslislog, CHANGELOG**

1. `data/checkregister-gwsw-nulmeting-v0_9.md`: direct ná de rij van ATTR-017 (regel 91) een nieuwe rij:

```markdown
| ATTR-018 | Begindatum ontbreekt op een vrijvervalrioolleiding of put. ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een aanwezige datum en de nulmeting eist `Begindatum` in geen van de drie CFK-rapporten; zonder aanlegjaar is er geen vervangingsplanning, geen levensduur en geen ATTR-003. Mechanisch riool valt buiten de populatie en wordt in de toelichting geteld (issue #61) | F | Compleetheid |
```

2. In `## Versiehistorie`, bovenaan (vóór de alinea "Versie 0.9, addendum (2026-08-23): ATTR-017 toegevoegd"), een nieuwe alinea:

```markdown
Versie 0.9, addendum (2026-08-24): ATTR-018 toegevoegd (F, Compleetheid): een
vrijvervalrioolleiding of put zonder `Begindatum`. Tot nu toe kreeg zo'n object nergens een
melding -- ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een aanwezige datum, de nulmeting
eist het kenmerk niet -- en bleef het op de kaart groen. De GeoPackage-lagen `putten` en
`strengen` dragen sindsdien ook de kolom `begindatum_jaar`. Op De Wolden en Hoogeveen meldt
hij ongeveer 9274 objecten (24% van de populatie), vooral putten. Zie
[#61](https://github.com/mcolee/nlriochecker/issues/61) en BO-45.

```

3. Regenereer: `uv run python scripts/dekkingsmatrix.py`. Controleer met `git diff docs/dekkingsmatrix.md` dat de ATTR-tellingen met één omhoog gaan en er een rij ATTR-018 "geimplementeerd met test" bijkomt.

4. `docs/beslislog.md`, aan het einde van het bestand (na het laatste BO) een nieuw besluit — vervang `BO-45` door het werkelijke eerstvolgende nummer:

```markdown

### BO-45 Een ontbrekende begindatum is een fout per object (ATTR-018), niet een notitieregel

**Wat.** ATTR-018 (F, Compleetheid) meldt per vrijvervalrioolleiding en per put dat `Begindatum`
ontbreekt. Populatie en `examined` zijn die van ATTR-007 (`vrijvervalrioolleidingen` plus
`putten`); mechanisch riool en andere niet-vrijvervalleidingen vallen erbuiten en worden in de
toelichting geteld. De GeoPackage-lagen `putten` en `strengen` krijgen de kolom `begindatum_jaar`
(integer, leeg zonder datum). De tweede notitieregel van ATTR-007, die het gat over de hele
meetset telde, vervalt. Uitgewerkt in issue #61.

**Waarom.** `notes()` gaat per ontwerp alleen naar het Markdown-rapport; een object zonder
aanlegjaar had dus geen spoor in de JSON, de CSV of de GeoPackage en kleurde groen -- "beoordeeld
en niets gevonden". Zonder aanlegjaar is er geen vervangingsplanning, geen levensduurberekening en
geen ATTR-003; dat is een gebrek in de aanlevering en geen signaal, vandaar F. Het jaar en niet de
datum in de kolom, omdat de rest van de code met het jaartal werkt (`Conduit.begindatum_jaar`).

**Gevolg dat je moet kennen.** Op De Wolden en Hoogeveen zijn het ongeveer 9274 bevindingen
(24,2% van 38361; putten 9063 van 20758, strengen 211 van 17603). Dat haalt de systemische
drempel (80%) niet, dus elke bevinding staat los in de CSV en op de kaart; het Markdown-rapport
groeit navenant (`max_bevindingen_per_check = 0`). Afkappen is een keuze voor de auteur, niet
voor de implementatie.

**Alternatieven.** Alleen de kolom (verworpen: een kolom kleurt niets en komt niet in de CSV of
JSON). Een systemische melding in plaats van per object (verworpen: het aandeel ligt onder de
drempel en het gat is per object te herstellen). `Einddatum` erbij (verworpen: dat is ADM-006, en
geen enkel object draagt er een).
```

5. `CHANGELOG.md`, onder `## [Unreleased]`, boven de bestaande koppen:

```markdown
### Toegevoegd

- **ATTR-018: ontbrekende begindatum wordt per object gemeld** (issue #61). Een
  vrijvervalrioolleiding of put zonder `Begindatum` krijgt een fout (Compleetheid); tot nu
  toe stond het gat alleen als één regel in de toelichting van ATTR-007 en bleef zo'n
  object op de kaart groen. De GeoPackage-lagen `putten` en `strengen` dragen de nieuwe
  kolom `begindatum_jaar` (leeg zonder datum). De meetsetregel van ATTR-007 vervalt; de
  regel die zegt wat ATTR-007 zelf niet kon toetsen blijft. Op De Wolden en Hoogeveen:
  ongeveer 9274 bevindingen, vooral putten (Task 2 meet het). Zie BO-45.

```

- [ ] **Step 7: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen. Faalt `ruff format --check`, draai `uv run ruff format` en herhaal.

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/attr018_zonder_begindatum.ttl \
  src/nlriochecker/checks/attributen.py tests/test_checks_blok_a.py \
  data/checkregister-gwsw-nulmeting-v0_9.md docs/dekkingsmatrix.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "ATTR-018: meld een ontbrekende begindatum per streng en put (issue #61)"
```

Staan er na `git status --short` nog gewijzigde testbestanden buiten deze lijst (verwachtingen uit Step 5), voeg die toe vóór de commit. Voeg géén planbestanden of `uitvoer/` toe.

---

### Task 2: Kolom `begindatum_jaar` in de GeoPackage

**Files:**
- Modify: `src/nlriochecker/uitvoer/gpkg.py:48` (import), `:381-412` (`_samenvatting_kolommen`), `:957-1021` (`_samenvatting`), nieuwe helper `_begindatum_jaar` direct vóór `_samenvatting`
- Modify: `tests/test_uitvoer_gpkg.py` (één nieuwe test na `test_featurelagen_dragen_het_stelseltype`)
- Modify: `docs/architectuur.md:95-107` (eerste bullet onder "GeoPackage en QGIS")

**Interfaces:**
- Consumes: `Node.date("Begindatum")`, `Conduit.date("Begindatum")`; de fixture `hgt_schoon.ttl` (twee `hoogteput`-putten zonder begindatum, één `hoogteleiding` met `Begindatum 1980-01-01`).
- Produces: kolom `begindatum_jaar` (integer) in de lagen `putten` en `strengen`, direct na `stelsel`.

- [ ] **Step 1: Schrijf de falende test**

In `tests/test_uitvoer_gpkg.py`, direct ná `test_featurelagen_dragen_het_stelseltype`:

```python
def test_featurelagen_dragen_het_begindatumjaar(tmp_path: Path) -> None:
    """Het aanlegjaar als kolom om op te filteren; leeg als het object er geen draagt.

    `hgt_schoon.ttl` heeft één streng met begindatum 1980-01-01 en twee putten zonder
    begindatum (issue #61).
    """
    pad = _schrijf(_run("hgt_schoon.ttl"), tmp_path)

    strengen = dict(_rijen(pad, "select label, begindatum_jaar from strengen"))
    putten = dict(_rijen(pad, "select label, begindatum_jaar from putten"))

    assert strengen == {"1": 1980}
    assert putten == {"A": None, "B": None}
```

- [ ] **Step 2: Draai de test en zie hem falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py::test_featurelagen_dragen_het_begindatumjaar -v`
Expected: FAIL met `sqlite3.OperationalError: no such column: begindatum_jaar`.

- [ ] **Step 3: Implementeer de kolom**

1. Regel 48: `from nlriochecker.dataset import Conduit, GwswDataset` → `from nlriochecker.dataset import Conduit, GwswDataset, Node`.

2. In `_samenvatting_kolommen()`, direct ná `_Kolom("stelsel", "text"),`:

```python
        # Het aanlegjaar uit `Begindatum`, om op te filteren; leeg als het object er
        # geen draagt (ATTR-018 meldt dat dan). Het jaar en niet de datum, net als de
        # rest van de code (`Conduit.begindatum_jaar`).
        _Kolom("begindatum_jaar", "integer"),
```

3. Direct vóór `def _samenvatting(` een helper:

```python
def _begindatum_jaar(object_: object) -> int | None:
    """Het jaartal van de begindatum, of None als het object er geen draagt."""
    if not isinstance(object_, (Node, Conduit)):
        return None
    datum = object_.date("Begindatum")
    return datum.year if datum is not None else None
```

4. In de returntuple van `_samenvatting`, direct ná `stelsel,`: `_begindatum_jaar(object_),`. Vul de docstring van `_samenvatting` niet aan; de kolomlijst is de documentatie.

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py tests/test_uitvoer_qgis.py tests/test_toetsrun.py -q`
Expected: PASS (`test_uitvoer_qgis.py` slaat over zonder QGIS op de machine; dat is geen fout). Valt een test op het aantal kolommen of op een vaste tuple-positie, werk hem bij met een regel commentaar en verklaar dat in je rapport.

- [ ] **Step 5: Documentatie**

In `docs/architectuur.md`, in de eerste bullet onder `## GeoPackage en QGIS`, ná de zin `Elk object heeft `status` (precies vier waarden: rood, oranje, groen, grijs) en `popup_html` (een voorgebakken fragment, zonder stijlblok -- dat staat een keer in de maptip).` invoegen: ` Beide lagen dragen ook `begindatum_jaar` (het aanlegjaar uit `Begindatum`, leeg zonder datum; ATTR-018 meldt dat gat per object, issue #61).`

- [ ] **Step 6: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen.

```bash
git add src/nlriochecker/uitvoer/gpkg.py tests/test_uitvoer_gpkg.py docs/architectuur.md
git status --short
git commit -m "GeoPackage: kolom begindatum_jaar op putten en strengen (issue #61)"
```

---

### Task 3: Effect op De Wolden meten en vastleggen

**Files:**
- Read: `uitvoer/volledig_24082026/bevindingen.csv` en `uitvoer/volledig_24082026/bevindingen.md` (baseline 0.3.0)
- Create (niet committen; `uitvoer/` is git-ignored): `uitvoer/issue61/`
- Modify: `docs/beslislog.md` (BO-45: alinea "Gemeten uitkomst"), `CHANGELOG.md` (getal corrigeren als het afwijkt)

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
  --output uitvoer/issue61
```

Expected: eindigt met `Geschreven: uitvoer/issue61/dq_dewoldenhoogeveen_orox_<datum>.gpkg`; duurt ca. 2-3 minuten.

- [ ] **Step 2: Meet**

```bash
head -1 uitvoer/issue61/bevindingen.csv
uv run python - <<'EOF'
import pandas as pd
frame = pd.read_csv("uitvoer/issue61/bevindingen.csv", sep=";")
deel = frame[frame.Check == "ATTR-018"]
print("ATTR-018:", len(deel), "meldingen;", deel.ObjectURI.nunique(), "objecten")
print(deel.groupby(deel.Boodschap.str.extract(r"Deze (\w+) draagt")[0]).size())
EOF
wc -l uitvoer/volledig_24082026/bevindingen.md uitvoer/issue61/bevindingen.md
du -h uitvoer/volledig_24082026/bevindingen.md uitvoer/issue61/bevindingen.md
grep -n "vallen buiten deze toets" uitvoer/issue61/bevindingen.md | head -2
uv run python -c "
import sqlite3, glob; c = sqlite3.connect(glob.glob('uitvoer/issue61/*.gpkg')[0])
for laag in ('putten', 'strengen'):
    print(laag, c.execute(f'select count(*), sum(begindatum_jaar is null), min(begindatum_jaar), max(begindatum_jaar) from {laag}').fetchone())"
```

Lees eerst de kolomnamen als `Check`/`Boodschap`/`ObjectURI` niet kloppen. Verwacht volgens het issue: **9274** ATTR-018-meldingen (211 strengen, 9063 putten), niet systemisch; een notitie met 5837 van de 23440 leidingen buiten de toets waarvan 1703 zonder begindatum; in de GeoPackage 9063 lege `begindatum_jaar` op `putten`. Let op: de laag `strengen` bevat ook mechanisch riool, dus daar zijn er meer lege waarden (ongeveer 1914) dan ATTR-018-meldingen. Wijkt een getal af, meld het getal en de richting; redeneer het niet weg. Meet ook hoeveel het Markdown-rapport groeit (regels en bytes) en meld dat.

- [ ] **Step 3: Leg vast en commit**

Voeg aan BO-45 in `docs/beslislog.md` een slotalinea toe met de gemeten getallen:

```markdown

**Gemeten uitkomst (2026-08-24).** Volledige toets op De Wolden en Hoogeveen: ATTR-018 meldt <N>
objecten (<Ns> strengen, <Np> putten), niet systemisch. Buiten de toets vallen <B> van de <L>
leidingen, waarvan <Bz> zonder begindatum. Het Markdown-rapport groeit van <R0> naar <R1> regels
(<G0> → <G1>). In de GeoPackage staan <Pl> lege `begindatum_jaar` op `putten` en <Sl> op `strengen`
(de laatste inclusief mechanisch riool).
```

Corrigeer het getal in de CHANGELOG-regel van Task 1 als het afwijkt van 9274 en haal `(Task 2 meet het)` uit die regel. Dan:

```bash
git add docs/beslislog.md CHANGELOG.md
git commit -m "BO-45: gemeten uitkomst van ATTR-018 op De Wolden (issue #61)"
```

Zet de metingen in het rapportbestand van deze taak.
