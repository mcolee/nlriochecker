# Bugronde: de vijf open bug-issues — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De vijf GitHub-issues met label `bug` (#5, #2, #3, #6, #1) zijn gerepareerd,
elk met een regressietest, een commit op `dev` en een sluitreactie op het issue; het
checkregister staat op v0.9.

**Architecture:** Elke fix is een eigen taak en raakt een afgebakende plek: NET-004 leest
strengen uit een dict in plaats van uit kantattributen (#5); ATTR-006 zet `zijde` zodat de
identiteit sluit (#2); de fixturehiërarchie volgt de echte ontologie en EXT-002/003 delen
één kruisingenlijst (#3); RVZ-002/003 worden gebouwd op de bestaande drempelinfrastructuur
en de dekkinganalyse krijgt een inhoudelijke poort (#6); een vulwaarde-leesregel zet
0,000-hoogten naar `None` ná het laden en ATTR-013 meldt dat (#1). Twee fixes wijzigen het
register; daarom één registerbump naar v0.9 vóór die twee.

**Tech Stack:** Python 3.12, networkx, rdflib, shapely, pydantic, click; pytest; uv;
ruff + mypy. Geen nieuwe afhankelijkheden.

**Spec:** `docs/superpowers/specs/2026-08-19-bugfixes-issues-1-2-3-5-6-design.md`

## Global Constraints

- Werk op branch `dev`. Het pakketversienummer in `pyproject.toml` blijft `0.2.0`.
- Geen nieuwe afhankelijkheden.
- Geen hardcoded drempels: de vulwaardeband komt uit `[vulwaarden] hoogte_band_m`.
- Nederlandse docstrings, Engelse identifiers, type hints overal; bestaande stijl volgen.
- Enige schrijvers blijven `schrijf_markdown`/`schrijf_csv`/`schrijf_json`
  (`uitvoer/herkomst.py`) en `schrijf_geopackage`; je raakt ze in dit plan niet aan.
- Elke gegenereerde TTL-fixture komt uit `scripts/maak_ttl_fixtures.py`
  (`uv run python scripts/maak_ttl_fixtures.py`); `tests/test_ttl_fixtures.py` bewaakt
  dat. Alleen de NET-004-fixtures zijn handgeschreven (die staan buiten het script).
- Na elke taak de poort: `uv run ruff check`, `uv run ruff format --check .`,
  `uv run mypy`, `uv run pytest` (zonder `-m zwaar`) — alles groen — en committen.
  Commitboodschappen in het Nederlands, in de stijl van `git log` (een zin, tegenwoordige
  tijd, zonder prefix), afgesloten met `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
  (of het model dat uitvoert).
- Issues sluiten met `gh issue close <n> --comment "..."`; de reactie noemt de commit-hash
  en wat er veranderd is. Let op: `gh issue view` faalt in dit repo met een
  GraphQL-fout over Projects (classic); lees issues via
  `gh issue list --state all --json number,title,body,comments --jq ...`.
- `CHANGELOG.md` wordt in taak 8 in één keer bijgewerkt; `docs/beslislog.md` ook.
- Geen merge naar `main`.

## Bestandsindeling

| Bestand | Verantwoordelijkheid | Actie |
|---|---|---|
| `src/nlriochecker/checks/netwerk.py` | `_Netwerk.strengen_per_kant`, NET-004 `_eerste_streng` | wijzigen (#5) |
| `tests/fixtures/ttl/net004_parallelle_strengen.ttl`, `…_omgekeerd.ttl` | handgeschreven kringloopfixtures met parallelle strengen | nieuw (#5) |
| `tests/test_checks_netwerk.py` | NET-004-regressietest | uitbreiden (#5) |
| `src/nlriochecker/checks/attributen.py` | ATTR-006 met `zijde`; ATTR-013 | wijzigen (#2, #1) |
| `scripts/maak_ttl_fixtures.py` | PRELUDE-hiërarchie; nieuwe fixtures attr006/attr013/rvz002/rvz003; ext_scenario | wijzigen (#2, #3, #6, #1) |
| `tests/test_checks_blok_a.py` | `DEFECTEN`-rijen voor de nieuwe fixtures | uitbreiden (#2, #6, #1) |
| `src/nlriochecker/checks/extern.py` | gedeelde kruisingenlijst, duikernotitie | wijzigen (#3) |
| `tests/test_checks_extern.py` | verwachtingen na de fixturecorrectie | wijzigen (#3) |
| `data/checkregister-gwsw-nulmeting-v0_9.md` | register v0.9 | hernoemen + wijzigen |
| `src/nlriochecker/register.py`, `dekking.toml`, `checkconfig.py`, `checks.toml`, `configs/dewoldenhoogeveen.toml`, `CLAUDE.md`, `CONTEXT.md`, `uitvoer/bevindingen.py`, tests | versieverwijzingen v0.9 | wijzigen |
| `src/nlriochecker/checks/randvoorzieningen.py` | RVZ-002, RVZ-003 | uitbreiden (#6) |
| `src/nlriochecker/dekking.toml` | sentinels RVZ-002/003 eruit | wijzigen (#6) |
| `tests/test_coverage.py`, `test_coverage_regressie.py`, `test_cli.py`, `test_reporting.py`, `test_integration.py`, `test_config.py`, `test_checks_registry.py` | schrapping omdraaien; inhoudelijke poort | wijzigen (#6) |
| `docs/dekkingsmatrix.md` | regenereren via `scripts/dekkingsmatrix.py` | regenereren (#6, #1) |
| `src/nlriochecker/dataset.py` | `Vulwaarde`, velden `vulwaarden`, `markeer_vulwaarden` | uitbreiden (#1) |
| `src/nlriochecker/checkconfig.py` | `VulwaardeOptions`, `CheckConfig.vulwaarden` | uitbreiden (#1) |
| `src/nlriochecker/checks.toml`, `configs/dewoldenhoogeveen.toml` | sectie `[vulwaarden]` | uitbreiden (#1) |
| `src/nlriochecker/toetsrun.py` | `markeer_vulwaarden` toepassen na het laden | wijzigen (#1) |
| `src/nlriochecker/checks/hoogten.py` | `notes()` op HGT-018 | uitbreiden (#1) |
| `tests/test_dataset_vulwaarden.py` | tests op de leesregel | nieuw (#1) |
| `CHANGELOG.md`, `docs/beslislog.md` | BO-25, BO-26, BO-27 | uitbreiden (taak 8) |

## Vaste feiten (geverifieerd op 2026-08-19; vertrouw erop, meet niet opnieuw)

- In alle drie de SHACL-rapporten onder `data/shacl_nulmeting/` bestaat geen enkele vorm
  op `Drempelniveau` of `Drempelbreedte`; de enige drempelvorm is
  `Overstortput_Overstortdrempel_card` (Hyd 218, MdsPlan 218, MdsProj 0).
- `data/gwsw_orox_ttl/dewolden_orox.ttl`: 218 `Overstortput`, nul `Overstortdrempel`.
- Ontologie `data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl`:
  `gwsw:Duiker rdfs:subClassOf gwsw:Leiding` (regel 40184);
  `gwsw:Zinker rdfs:subClassOf gwsw:VrijvervalRioolleiding` (regel 50980).
- De De Wolden-run van 2026-08-19 (na BO-24): EXT-002 = EXT-003 = 859 meldingen;
  ATTR-006 logde 18 keer de id_sleutels-waarschuwing; NET-004 17 bevindingen.
- `tests/test_uitvoer_identiteit_sweep.py` draait al alle checks over
  `tests/fixtures/ttl/*.ttl` en faalt op een volgnummer of een id_sleutels-waarschuwing.
- `CheckContext.cached`-voorvoegsel `ext:` bestaat al (`ext:selectie:<id>` in
  `checks/extern.py`).
- `Finding`-details met sleutel `object2_uri` gaan de melding-ID in; `zijde` is de
  default `id_sleutels` van elke check (`checks/base.py:318`).

---

## Task 1: Nulmeting van de poort

**Files:** geen wijzigingen.

- [ ] **Step 1: Tak en schone staat**

Run: `git status --short && git branch --show-current`
Expected: lege status, `dev`.

- [ ] **Step 2: Poort groen vóór je begint**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: alles groen. Noteer het aantal tests (het staat in de pytest-samenvatting); dat
getal moet aan het eind van elke taak gestegen zijn, nooit gedaald.

- [ ] **Step 3: Lees de vijf issues**

Run:
```bash
gh issue list --state open --label bug --json number,title,body,comments \
  --jq '.[] | "## #\(.number) \(.title)\n\(.body)\n--- reacties:\n\([.comments[].body]|join("\n---\n"))\n"'
```
Expected: #1, #2, #3, #5, #6. Geen commit.

---

## Task 2: Issue #5 — NET-004 noemt een streng op de kant, onafhankelijk van de invoervolgorde

**Files:**
- Modify: `src/nlriochecker/checks/netwerk.py:24-68` (`_Netwerk`, `_bouw_netwerk`) en `:343-412` (`KringloopInNetwerk.run`, `_eerste_streng`)
- Create: `tests/fixtures/ttl/net004_parallelle_strengen.ttl`, `tests/fixtures/ttl/net004_parallelle_strengen_omgekeerd.ttl`
- Test: `tests/test_checks_netwerk.py`

**Interfaces:**
- Produces: `_Netwerk.strengen_per_kant: dict[tuple[str, str], tuple[Conduit, ...]]` — per
  gerichte kant (zoals in de graaf, dus ná de BOB-omdraaiing) de strengen, gesorteerd op URI.
- De graafkanten dragen geen attributen meer.

Achtergrond: twee gelijkgerichte parallelle strengen liggen allebei op de kring, dus de
genoemde streng is nooit "naast" de kring — maar welke van de twee genoemd wordt hangt nu
af van de iteratievolgorde over de conduits (de laatste `add_edge` wint). Tussen twee
exports met een andere volgorde verschuift zo de `melding_id` van NET-004. De test pint
daarom volgorde-onafhankelijkheid plus "ligt op de kant".

- [ ] **Step 1: Twee handgeschreven fixtures**

Kopieer `tests/fixtures/ttl/net004_kringloop.ttl` naar
`tests/fixtures/ttl/net004_parallelle_strengen.ttl`. Vervang de DEFECT-regel door
`# DEFECT: strengen '5' en '5b' liggen parallel op C -> D; '5', '6' en '7' vormen een kringloop C -> D -> E -> C`
en voeg **direct na het blok van `:L5`** toe:

```turtle
:L5b rdf:type gwsw:GemengdRiool ; rdfs:label "5b" ;
    gwsw:hasAspect :L5b_ori .
:L5b_ori rdf:type gwsw:Leidingorientatie ;
    gwsw:hasPart :L5b_b , :L5b_e ;
    gwsw:hasAspect [ rdf:type gwsw:Lijn ;
        gwsw:hasValue "<gml:LineString xmlns:gml=\"http://www.opengis.net/gml\"><gml:posList srsDimension=\"2\">2000.0 3000.0 2025.0 3001.0 2050.0 3000.0</gml:posList></gml:LineString>"^^geo:gmlLiteral ] .
:L5b_b rdf:type gwsw:BeginpuntLeiding .
:L5b_e rdf:type gwsw:EindpuntLeiding .
:L5b_b gwsw:hasConnection :PutC_ori .
:L5b_e gwsw:hasConnection :PutD_ori .
```

Maak `net004_parallelle_strengen_omgekeerd.ttl` als exacte kopie daarvan waarin het
`:L5b`-blok **vóór** het `:L5`-blok staat (en verder byte-gelijk).

- [ ] **Step 2: De falende test**

Voeg toe aan `tests/test_checks_netwerk.py` (import `verbonden_knopen` uit
`nlriochecker.checks.verbanden` erbij):

```python
@pytest.mark.parametrize(
    "bestand", ["net004_parallelle_strengen.ttl", "net004_parallelle_strengen_omgekeerd.ttl"]
)
def test_net004_noemt_dezelfde_streng_ongeacht_de_invoervolgorde(bestand: str) -> None:
    """Twee parallelle strengen op de kring: de melding hangt aan een streng die echt op
    de kant kring[0] -> kring[1] ligt, en aan dezelfde streng ongeacht de volgorde waarin
    de export ze declareert. Anders verschuift de melding-ID tussen twee exports."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=load_check_config())
    bevindingen = run_checks(context, ["NET-004"]).outcomes[0].findings

    assert len(bevindingen) == 1
    assert bevindingen[0].details["voorbeeldkring"] == ["C", "D", "E"]
    streng = dataset.conduits[bevindingen[0].object_uri]
    begin, eind = verbonden_knopen(context, streng)
    assert (dataset.nodes[begin].label, dataset.nodes[eind].label) == ("C", "D")
    # De kleinste URI van de parallelle set, in beide declaratievolgordes.
    assert bevindingen[0].object_label == "5"
```

- [ ] **Step 3: Rood zien**

Run: `uv run pytest tests/test_checks_netwerk.py -k invoervolgorde -v`
Expected: minstens de `_omgekeerd`-variant faalt op `object_label == "5"` (de laatste
`add_edge` wint en dat is daar `5b`). Faalt geen van beide, controleer dan met
`print(bevindingen[0].object_label)` in beide varianten dat de uitkomst van de volgorde
afhangt; zo niet, meld dat in de taakuitkomst en ga toch door — de structurele fix blijft
nodig (zie het issue).

- [ ] **Step 4: De fix**

In `src/nlriochecker/checks/netwerk.py`:

```python
from dataclasses import dataclass, field
```

```python
@dataclass(frozen=True)
class _Netwerk:
    """...(docstring ongewijzigd)..."""

    graph: nx.DiGraph
    conduits: list[Conduit]
    unconnected: list[Conduit]
    reversed_count: int = 0
    # Per gerichte kant de strengen die erop liggen, gesorteerd op URI. De graaf zelf
    # draagt geen kantattributen: in een DiGraph delen parallelle strengen een kant en
    # zou de laatste de eerste stilzwijgend overschrijven (zie issue #5 en
    # `afbakening._componentstructuur`, dat hetzelfde patroon bewust vermijdt).
    strengen_per_kant: dict[tuple[str, str], tuple[Conduit, ...]] = field(default_factory=dict)
```

In `_bouw_netwerk`:

```python
    per_kant: dict[tuple[str, str], list[Conduit]] = {}
    for conduit in conduits:
        begin = dataset.resolve_network_node(conduit.start_node, wortels)
        eind = dataset.resolve_network_node(conduit.end_node, wortels)
        if begin is None or eind is None:
            los.append(conduit)
            continue
        if op_bob and _stijgt(conduit):
            begin, eind = eind, begin
            omgedraaid += 1
        graph.add_edge(begin, eind)
        per_kant.setdefault((begin, eind), []).append(conduit)
        aangesloten.append(conduit)

    return _Netwerk(
        graph=graph,
        conduits=aangesloten,
        unconnected=los,
        reversed_count=omgedraaid,
        strengen_per_kant={
            kant: tuple(sorted(groep, key=lambda streng: streng.uri))
            for kant, groep in per_kant.items()
        },
    )
```

In `KringloopInNetwerk.run`: `uri, label = self._eerste_streng(netwerk, kring, dataset)`.

```python
    def _eerste_streng(self, netwerk: _Netwerk, kring: list[str], dataset) -> tuple[str, str]:
        """De streng waarop de melding wordt gehangen: de eerste op de kant kring[0] -> kring[1]."""
        if len(kring) > 1:
            strengen = netwerk.strengen_per_kant.get((kring[0], kring[1]), ())
            if strengen:
                return strengen[0].uri, strengen[0].label
        return kring[0], self._label(dataset, kring[0])
```

Controleer met `grep -n 'edges\[' src/nlriochecker/checks/netwerk.py` dat er geen
lezer van kantattributen overblijft.

- [ ] **Step 5: Groen zien, hele poort**

Run: `uv run pytest tests/test_checks_netwerk.py -v && uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: alles groen; `test_net004_vindt_de_kringloop` ongewijzigd groen.

- [ ] **Step 6: Commit en issue sluiten**

```bash
git add src/nlriochecker/checks/netwerk.py tests/fixtures/ttl/net004_parallelle_strengen*.ttl tests/test_checks_netwerk.py
git commit -m "NET-004 noemt bij parallelle strengen de eerste op de kant, niet de laatst toegevoegde"
gh issue close 5 --comment "Gerepareerd in <hash> op dev: _bouw_netwerk houdt per gerichte kant de strengen los van de graaf bij (strengen_per_kant, gesorteerd op URI) en de graaf draagt geen kantattributen meer; NET-004 noemt de eerste streng op de kant. Twee fixtures die alleen in declaratievolgorde verschillen geven nu dezelfde melding. Op De Wolden blijft het aantal NET-004-bevindingen 17; welke streng genoemd wordt kan eenmalig verschuiven (meting volgt in de afronding van deze ronde)."
```

---

## Task 3: Issue #2 — ATTR-006 onderscheidt begin- en eindput

**Files:**
- Modify: `src/nlriochecker/checks/attributen.py:336-370` (`DiameterGroterDanPut.run`)
- Modify: `scripts/maak_ttl_fixtures.py` (nieuwe fixture na `attr006_te_grote_streng.ttl`, regel ~541)
- Modify: `tests/test_checks_blok_a.py` (`DEFECTEN`)
- Test: `tests/test_checks_blok_a.py`, `tests/test_uitvoer_identiteit_sweep.py`

**Interfaces:**
- Consumes: `verbonden_knopen(context, conduit) -> tuple[str | None, str | None]` uit
  `checks/verbanden.py:19` (begin, eind).
- Produces: ATTR-006-findings met `details["zijde"] in {"beginpunt", "eindpunt"}` en
  `details["put"]` (label, ongewijzigd).

- [ ] **Step 1: Fixture met twee te kleine putten**

In `scripts/maak_ttl_fixtures.py`, direct onder `FIXTURES["attr006_te_grote_streng.ttl"]`:

```python
FIXTURES["attr006_twee_te_kleine_putten.ttl"] = (
    "streng 1 is 1200 mm terwijl put A en put B allebei 800 bij 800 mm zijn",
    nette_put("PutA", "A", *A, BreedtePut=800, LengtePut=800)
    + nette_put("PutB", "B", *B, BreedtePut=800, LengtePut=800)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"BreedteLeiding": 1200, "HoogteLeiding": 1200},
    ),
)
```

Run: `uv run python scripts/maak_ttl_fixtures.py && git status --short tests/fixtures/ttl`
Expected: alleen `attr006_twee_te_kleine_putten.ttl` nieuw.

- [ ] **Step 2: Falende tests**

In `tests/test_checks_blok_a.py`, in `DEFECTEN` direct na de ATTR-006-rij:

```python
    ("attr006_twee_te_kleine_putten.ttl", "ATTR-006", ["1", "1"]),
```

en als losse test onderaan (naast de bestaande detailtests):

```python
def test_attr006_onderscheidt_de_twee_zijden() -> None:
    bevindingen = uitkomst("attr006_twee_te_kleine_putten.ttl", "ATTR-006").findings

    assert sorted(b.details["zijde"] for b in bevindingen) == ["beginpunt", "eindpunt"]
    assert sorted(b.details["put"] for b in bevindingen) == ["A", "B"]
```

Run: `uv run pytest tests/test_checks_blok_a.py -k attr006 tests/test_uitvoer_identiteit_sweep.py -v`
Expected: de sweep faalt (volgnummer `-2` / waarschuwing op ATTR-006) en
`test_attr006_onderscheidt_de_twee_zijden` faalt op `KeyError: 'zijde'`.

- [ ] **Step 3: De fix**

Vervang in `DiameterGroterDanPut.run` de binnenlus:

```python
        for conduit in vrijvervalrioolleidingen(context):
            maat = _grootste_maat(conduit)
            if maat is None:
                continue
            begin, eind = verbonden_knopen(context, conduit)
            for zijde, put_uri in (("beginpunt", begin), ("eindpunt", eind)):
                node = context.dataset.nodes.get(put_uri) if put_uri else None
                if node is None:
                    continue
                putmaat = _grootste_putmaat(node)
                if putmaat is None or maat <= putmaat + marge:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Profielmaat {maat:g} mm is groter dan de grootste binnenmaat "
                    f"{putmaat:g} mm van put {node.label!r} aan het {zijde}.",
                    maat_mm=maat,
                    putmaat_mm=putmaat,
                    put=node.label,
                    zijde=zijde,
                )
```

Importeer `verbonden_knopen` uit `nlriochecker.checks.verbanden` (staat `putten_van`
daarna nergens meer in `attributen.py`, haal die import dan weg; `ruff` meldt het).

- [ ] **Step 4: Groen en poort**

Run: `uv run pytest tests/test_checks_blok_a.py tests/test_uitvoer_identiteit_sweep.py -q && uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: groen. De bestaande rij `("attr006_te_grote_streng.ttl", "ATTR-006", ["1"])` blijft groen.

- [ ] **Step 5: Commit en issue sluiten**

```bash
git add src/nlriochecker/checks/attributen.py scripts/maak_ttl_fixtures.py tests/fixtures/ttl/attr006_twee_te_kleine_putten.ttl tests/test_checks_blok_a.py
git commit -m "ATTR-006 zet de zijde in de melding, zodat begin- en eindput een eigen ID krijgen"
gh issue close 2 --comment "Gerepareerd in <hash> op dev: ATTR-006 loopt over begin- en eindpunt met zijde in de details; de default id_sleutels (zijde) maakt de twee meldingen per streng uniek, zonder volgnummer. De sweep over alle checks die het issue voorstelt bestond al (tests/test_uitvoer_identiteit_sweep.py); de fixture had maar één te kleine put. Er is nu een fixture met twee. Gevolg: de melding-ID's van ATTR-006 verschuiven eenmalig (schema_versie blijft 1.0, zoals bij EXT-001/003); komt in de CHANGELOG."
```

---

## Task 4: Issue #3 — fixturehiërarchie volgt de ontologie; EXT-002/003 delen de kruisingen en melden de duikers

**Files:**
- Modify: `scripts/maak_ttl_fixtures.py:46` (PRELUDE) en `:1085-1135` (`ext_scenario.ttl`)
- Modify: `src/nlriochecker/checks/extern.py:389-518` (`_WatergangKruising`, EXT-002, EXT-003)
- Modify: `src/nlriochecker/checks/base.py:122-128` (docstring van `cached`: eigenaar van `ext:`)
- Modify: `tests/test_checks_extern.py:99-108` en `:186-190`
- Modify: `data/checkregister-gwsw-nulmeting-v0_8.md:163` (rij EXT-003; de versiebump komt in taak 5)

**Interfaces:**
- Produces: `_WatergangKruising.kruisingen(context) -> tuple[tuple[Conduit, BaseGeometry, Mapping, object, float], ...]`
  (gecachet onder `ext:watergangkruisingen`); `_WatergangKruising.buiten_populatie(context) -> dict[str, int]`
  (klasse uit `klassen.kruisingsleiding` die geen vrijvervalleiding is → aantal strengen).

- [ ] **Step 1: PRELUDE en scenario corrigeren**

In `scripts/maak_ttl_fixtures.py` PRELUDE, vervang
`gwsw:Duiker rdfs:subClassOf gwsw:VrijvervalRioolleiding .` door:

```turtle
gwsw:Duiker rdfs:subClassOf gwsw:Leiding .
gwsw:Zinker rdfs:subClassOf gwsw:VrijvervalRioolleiding .
```

In `FIXTURES["ext_scenario.ttl"]` vervang het blok van streng 3 door:

```python
    # Streng 3 is een zinker die water-2 kruist: wel EXT-002, geen EXT-003. Een zinker
    # is in de ontologie een VrijvervalRioolleiding en zit dus in de populatie.
    + hoogteleiding("L3", "3", [EXT_E, EXT_F], "PutE", "PutF", bob=(9.60, 9.55)).replace(
        "gwsw:GemengdRiool", "gwsw:Zinker"
    )
    # Streng 6 is een duiker op dezelfde route: een duiker is geen rioolleiding
    # (subklasse van Leiding, niet van VrijvervalRioolleiding) en valt buiten de
    # populatie van EXT-002 en EXT-003; geen van beide meldt hem.
    + leiding("L6", "6", [EXT_E, EXT_F], "PutE", "PutF", klasse="Duiker")
```

Run: `uv run python scripts/maak_ttl_fixtures.py && uv run pytest -q -x --deselect tests/test_ttl_fixtures.py 2>&1 | tail -30`
Expected: rood in `tests/test_checks_extern.py` (EXT-002 verwacht `["2","3"]`: blijft
waar; `test_ext003_zwijgt_over_een_duiker` verwijst naar een duiker die nu buiten de
populatie valt) — en mogelijk elders. **Beoordeel elke rode test afzonderlijk**: faalt hij
omdat de oude hiërarchie een verkeerde aanname droeg (dan volgt de verwachting de
ontologie), of raakt de nieuwe streng 6 een check onbedoeld (dan verplaats je streng 6,
niet de verwachting). Schrijf in de taakuitkomst per rode test welke van de twee het was.

- [ ] **Step 2: Verwachtingen in `tests/test_checks_extern.py`**

Vervang `test_ext003_zwijgt_over_een_duiker` door:

```python
def test_ext003_zwijgt_over_een_zinker(config: CheckConfig, bronnen: ExternalData) -> None:
    # Streng 3 is een zinker en kruist water-2; EXT-002 meldt hem wel, EXT-003 niet.
    assert "3" in labels(uitkomst("EXT-002", config, bronnen))
    assert "3" not in labels(uitkomst("EXT-003", config, bronnen))


def test_een_duiker_valt_buiten_beide_kruisingschecks(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Streng 6 is een Duiker: in de ontologie een Leiding, geen VrijvervalRioolleiding.
    Hij kruist water-2 net als streng 3, maar zit in geen van beide populaties. De
    toelichting van beide checks zegt dat hij niet bekeken is."""
    for check_id in ("EXT-002", "EXT-003"):
        outcome = uitkomst(check_id, config, bronnen)
        assert "6" not in labels(outcome)
        assert any("1 strengen van de klasse Duiker" in note for note in outcome.notes), outcome.notes
```

De parametrisering `("EXT-002", ["2", "3"])` en `("EXT-003", ["2"])` blijft staan.

- [ ] **Step 3: Gedeelde kruisingenlijst en duikernotitie in `extern.py`**

Vervang `_WatergangKruising` door:

```python
class _WatergangKruising(_ExterneCheck):
    """Gedeelde basis voor de twee kruisingschecks op BGT-waterdelen.

    De populatie is die van `klassen.vrijvervalleiding`. Een duiker is in de
    GWSW-ontologie een `Leiding` die oppervlaktewater verbindt, geen rioolleiding;
    hij valt dus buiten deze checks en `buiten_populatie()` telt hoeveel dat er zijn,
    zodat het rapport dat meldt in plaats van erover te zwijgen (BO-25).
    """

    rol = "bgt_water"
    soort = "vrijvervalstrengen"

    def objecten(self, context: CheckContext) -> list:
        """De vrijvervalstrengen."""
        return vrijvervalrioolleidingen(context)

    def kruisingen(self, context: CheckContext) -> tuple[tuple, ...]:
        """De strengen die een waterdeel raken, met het waterdeel erbij.

        Levert `(conduit, geometrie, rij, laag, buffer)`, een keer per context berekend
        en gedeeld door EXT-002 en EXT-003: dezelfde populatie, dezelfde buffer, dezelfde
        laag, dus dezelfde ruimtelijke toets. De `break` na het eerste gevonden waterdeel
        per streng blijft staan: een streng die twee waterdelen kruist levert er een, en
        welke hangt van de volgorde af (BO-17, bewust geaccepteerd).
        """
        return context.cached("ext:watergangkruisingen", lambda: tuple(self._zoek_kruisingen(context)))

    def _zoek_kruisingen(self, context: CheckContext):
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

    def buiten_populatie(self, context: CheckContext) -> dict[str, int]:
        """Per kruisingsklasse die geen vrijvervalleiding is: hoeveel strengen erbuiten vallen."""
        dataset = context.dataset
        binnen = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
        telling: dict[str, int] = {}
        for wortel in context.config.klassen.kruisingsleiding:
            buiten = [
                uri for uri in dataset.of_class(wortel) if uri in dataset.conduits and uri not in binnen
            ]
            if buiten:
                telling[wortel] = len(buiten)
        return telling

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de strengen die wel kruisingsklasse zijn maar buiten de populatie vallen."""
        notities = super().notes(context)
        for klasse, aantal in self.buiten_populatie(context).items():
            notities.append(
                f"{aantal} strengen van de klasse {klasse} vallen buiten de populatie "
                "(geen vrijvervalleiding) en zijn niet bekeken; een kruising van zo'n streng "
                "met een watergang is geen bevinding."
            )
        return notities
```

Let op `dataset.of_class(wortel)`: controleer de signatuur in `dataset.py` (het is de
functie die `selectie._van_klassen` gebruikt) en of ze URI-strings oplevert; pas zo nodig
aan. Zorg dat `self.selectie(context)` voor EXT-002 en EXT-003 dezelfde `toetsbaar`-set
oplevert (beide `objecten()` zijn `vrijvervalrioolleidingen`), anders is het delen van de
lijst niet geoorloofd — dat is al zo, maar noteer het in de docstring als je het
gecontroleerd hebt.

`KruisingMetWatergang.notes` en `KruisingZonderZinkerOfDuiker.notes` roepen
`super().notes(context)` al aan; daarmee komt de duikerregel in beide. In
`KruisingZonderZinkerOfDuiker` verandert de uitzonderingslogica niet.

In `checks/base.py` docstring van `cached`, voeg aan de zin over eigenaren toe:
"`ext:` is van `checks/extern.py`".

- [ ] **Step 4: Registerrij EXT-003 preciseren**

In `data/checkregister-gwsw-nulmeting-v0_8.md` regel 163:

```
| EXT-003 | Kruising met watergang zonder registratie als zinker; een duiker is in het GWSW geen rioolleiding (subklasse van Leiding) en valt buiten de populatie van EXT-002 en EXT-003, het rapport meldt hoeveel dat er zijn | W | Compleetheid |
```

- [ ] **Step 5: Groen en poort**

Run: `uv run pytest tests/test_checks_extern.py tests/test_ttl_fixtures.py tests/test_checks_treffers.py tests/test_uitvoer_gpkg.py -q && uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: groen.

- [ ] **Step 6: Commit en issue sluiten**

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl src/nlriochecker/checks/extern.py src/nlriochecker/checks/base.py tests/test_checks_extern.py data/checkregister-gwsw-nulmeting-v0_8.md
git commit -m "EXT-002 en EXT-003 delen de kruisingen en melden de duikers buiten hun populatie; de fixturehierarchie volgt de ontologie"
gh issue close 3 --comment "Afgehandeld in <hash> op dev. Uitkomst van het uitzoeken: in de GWSW-ontologie is Zinker een VrijvervalRioolleiding (de uitzondering van EXT-003 kan dus wél afgaan) en Duiker een Leiding die oppervlaktewater verbindt — geen rioolleiding, en een duiker die een waterdeel raakt is geen kruising. De populatie blijft daarom VrijvervalRioolleiding. Wat er veranderd is: de testfixtures verklaarden Duiker ten onrechte onder VrijvervalRioolleiding (nu gelijk aan de ontologie, met een Zinker- en een Duiker-streng in het scenario); EXT-002 en EXT-003 delen één kruisingenlijst (één ruimtelijke toets in plaats van twee); beide melden in hun toelichting hoeveel duikers buiten de populatie vallen; registerrij EXT-003 is gepreciseerd. Op De Wolden verandert er niets aan de 859 meldingen; BO-25 in de beslislog volgt in de afronding."
```

---

## Task 5: Checkregister v0.9

**Files:**
- Rename: `data/checkregister-gwsw-nulmeting-v0_8.md` → `data/checkregister-gwsw-nulmeting-v0_9.md`
- Modify: alles wat `grep -rn 'v0_8\|v0\.8' --include='*.md' --include='*.toml' --include='*.py' . | grep -v '^./docs/superpowers\|^./docs/ronde\|^./docs/review\|^./docs/kandidaat\|^./docs/fase4\|^./CHANGELOG\|^./uitvoer\|^./.venv'` vindt
- Test: `tests/test_register_versie.py` (`VERWACHTE_VERSIE`), `tests/test_checks_registry.py:12`, `tests/test_dekkingsmatrix.py`

- [ ] **Step 1: Hernoem en verwijzingen**

```bash
git mv data/checkregister-gwsw-nulmeting-v0_8.md data/checkregister-gwsw-nulmeting-v0_9.md
grep -rln 'v0_8' --include='*.md' --include='*.toml' --include='*.py' . | grep -v '^./docs/superpowers\|^./docs/ronde\|^./docs/review\|^./docs/kandidaat\|^./docs/fase4\|^./CHANGELOG\|^./uitvoer\|^./.venv'
```

Vervang in die bestanden `v0_8` door `v0_9`, en de versieteksten `v0.8` / `"0.8"` die
over het register gaan (niet over het pakket, niet over historische alinea's in
`docs/beslislog.md` — lees elke treffer) door `v0.9` / `"0.9"`. Concreet minimaal:
`src/nlriochecker/register.py`, `src/nlriochecker/dekking.toml` (`checkregister_versie`
én `bron`), `src/nlriochecker/checkconfig.py` (`ReportOptions.register_versie`),
`src/nlriochecker/checks.toml`, `configs/dewoldenhoogeveen.toml`,
`src/nlriochecker/uitvoer/bevindingen.py`, `CLAUDE.md`, `CONTEXT.md`,
`tests/test_register_versie.py` (`VERWACHTE_VERSIE = "0.9"`),
`tests/test_checks_registry.py`, `tests/test_checkconfig.py`, `tests/test_uitvoer_*.py`,
`tests/test_coverage_regressie.py`, `tests/test_cli.py`, `tests/test_config.py`. In
`tests/test_config.py` staat een `GELDIGE_TOML` met `checkregister_versie = "0.9"` als
*afwijkende* testwaarde — lees de test en kies een nieuwe afwijkende waarde (bijv. `"0.7"`)
als hij op ongelijkheid met de echte versie leunt.

- [ ] **Step 2: Kop en versiehistorie van het register**

Kopregel: `Versie 0.9, werkdocument (RVZ-002 en RVZ-003 terug in de engine, ATTR-013 toegevoegd, EXT-003 gepreciseerd d.d. 2026-08-19; afbakening tot een studiegebied toegevoegd d.d. 2026-08-16; EXT-008 vervallen). Scope: ...` (rest ongewijzigd).

Bovenaan `## Versiehistorie`:

```
Versie 0.9 (2026-08-19): RVZ-002 en RVZ-003 zijn uit de tabel Geschrapte checks gehaald
en gebouwd (W, Compleetheid): in geen van de drie SHACL-rapporten bestaat een vorm op
Drempelniveau of Drempelbreedte, de enige drempelvorm
(Overstortput_Overstortdrempel_card) toetst of de put een drempel heeft, dus de
dekkingclaim was niet aantoonbaar en er keek niets naar die twee eigenschappen (issue
#6). ATTR-013 toegevoegd (W, Compleetheid): een hoogtekenmerk op een vulwaarde rond 0 m
NAP dat als meting geregistreerd staat (issue #1). EXT-003 gepreciseerd: een duiker is
geen rioolleiding en valt buiten de populatie (issue #3). Verder geen checks toegevoegd,
geschrapt of van ernst of dimensie veranderd. Vervallen ID's worden niet hergebruikt.
```

(De tabelrijen zelf verhuizen in taak 6 en 7; deze taak legt alleen de versie vast.
`tests/test_checks_registry.py::test_geschrapte_checks_worden_niet_opnieuw_gebouwd`
blijft tot taak 6 groen omdat RVZ-002/003 nog niet in `REGISTRY` zitten.)

- [ ] **Step 3: Dekkingsmatrix regenereren en poort**

Run: `uv run python scripts/dekkingsmatrix.py && git status --short docs/dekkingsmatrix.md`
(lees de kop van `scripts/dekkingsmatrix.py` voor de exacte aanroep als die anders is).

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: groen, in het bijzonder `tests/test_register_versie.py`,
`tests/test_checks_registry.py`, `tests/test_dekkingsmatrix.py`.

- [ ] **Step 4: Commit**

```bash
git add -A data/ src/ tests/ configs/ docs/dekkingsmatrix.md CLAUDE.md CONTEXT.md
git commit -m "Checkregister v0.9: de vijf versieverwijzingen omgezet, versiehistorie vooruit"
```

---

## Task 6: Issue #6 — RVZ-002 en RVZ-003 gebouwd; de dekkinganalyse krijgt een inhoudelijke poort

**Files:**
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md` (RVZ-tabel `:126-140`, tabel Geschrapte checks `:181-182`, open punt 7 `:202`)
- Modify: `src/nlriochecker/checks/randvoorzieningen.py` (na RVZ-001, of onderaan)
- Modify: `src/nlriochecker/dekking.toml:71-92`
- Modify: `scripts/maak_ttl_fixtures.py` (drie RVZ-fixtures bij de andere `rvz0*`)
- Modify: `tests/test_checks_blok_a.py`, `tests/test_coverage.py`, `tests/test_coverage_regressie.py`, `tests/test_cli.py`, `tests/test_reporting.py`, `tests/test_integration.py`, `tests/test_config.py`, `tests/test_checks_registry.py`
- Regenerate: `docs/dekkingsmatrix.md`

**Interfaces:**
- Consumes: `drempels_per_put(context) -> dict[str, list[Drempel]]`, `overstortputten(context) -> list[Node]` (`checks/selectie.py:97`), `Drempel.niveau`, `Drempel.breedte`.
- Produces: checks `OverstortZonderDrempelniveau` (RVZ-002) en `OverstortZonderDrempelbreedte` (RVZ-003).

- [ ] **Step 1: Register**

Verwijder in `data/checkregister-gwsw-nulmeting-v0_9.md` de twee rijen RVZ-002/RVZ-003 uit
de tabel *Geschrapte checks* en voeg in de RVZ-tabel, tussen RVZ-001 en RVZ-004, toe:

```
| RVZ-002 | Overstort zonder geregistreerde drempelhoogte (Drempelniveau), ook als het drempelonderdeel zelf ontbreekt; overlapt bewust met de nulmetingvorm Overstortput_Overstortdrempel_card, want die toetst alleen of de put een drempel heeft en de check werkt ook zonder nulmeting | W | Compleetheid |
| RVZ-003 | Overstort zonder geregistreerde drempelbreedte (Drempelbreedte), ook als het drempelonderdeel zelf ontbreekt | W | Compleetheid |
```

Open punt 7: vervang "ATTR-011 en RVZ-003 zijn juist wel geschrapt" door "ATTR-011 is
juist wel geschrapt; RVZ-003 was dat ook maar is in v0.9 teruggehaald (issue #6)". Lees
de hele zin voordat je vervangt.

- [ ] **Step 2: Fixtures**

In `scripts/maak_ttl_fixtures.py` staat `FIXTURES["rvz_schoon.ttl"]` (regel ~815) als
één lange expressie. Trek daar een helper uit, zodat de drie nieuwe fixtures alleen in
de drempelregel verschillen, en laat `rvz_schoon.ttl` die helper óók gebruiken — de
gegenereerde inhoud van `rvz_schoon.ttl` moet byte-identiek blijven
(`tests/test_ttl_fixtures.py` en `git diff tests/fixtures/ttl/rvz_schoon.ttl` leeg):

```python
def _overstortstelsel(drempelregel: str) -> str:
    """Een gemengd stelsel met een aangesloten overstortput O die op een sloot loost.

    `drempelregel` is de TTL van de overstortdrempel van put O (uit `drempel(...)`),
    of een lege string voor een put zonder drempelonderdeel. Basis van rvz_schoon en
    van de RVZ-002/003-fixtures.
    """
    return (
        hoogteput("PutA", "A", A)
        + put(
            "PutO",
            "O",
            B[0],
            B[1],
            klasse="Overstortput",
            extra=kenmerken(
                "PutO", BreedtePut=1000, LengtePut=1000, HoogtePut=1500, MateriaalPut_ref="Beton"
            ),
        )
        + maaiveld("PutO", 10.0)
        + deksel("PutO", 10.0)
        + drempelregel
        + hoogteput("PutU", "U", C)
        + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55))
        + hoogteleiding(
            "L2", "2", [B, C], "PutO", "PutU", bob=(9.00, 8.95), Begindatum="1980-01-01"
        ).replace("gwsw:GemengdRiool", "gwsw:Overstortleiding")
        + """:Sloot1 rdf:type gwsw:Sloot ; rdfs:label "sloot" ;
    gwsw:hasAspect :Sloot1_ori .
:Sloot1_ori rdf:type gwsw:Putorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1062.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
"""
    )


FIXTURES["rvz_schoon.ttl"] = (
    "geen; een gemengd stelsel met een aangesloten overstortput die op een sloot loost",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=9.00, breedte=2000.0)),
)

FIXTURES["rvz002_drempel_zonder_niveau.ttl"] = (
    "de drempel van overstortput O heeft wel een breedte maar geen Drempelniveau",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=None, breedte=2000.0)),
)

FIXTURES["rvz003_drempel_zonder_breedte.ttl"] = (
    "de drempel van overstortput O heeft wel een niveau maar geen Drempelbreedte",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=9.00, breedte=None)),
)

FIXTURES["rvz002_overstort_zonder_drempel.ttl"] = (
    "overstortput O heeft geen enkel Overstortdrempel-onderdeel; RVZ-002 en RVZ-003 gaan allebei af",
    _overstortstelsel(""),
)
```

(Kopieer de body van `_overstortstelsel` letterlijk uit de huidige
`rvz_schoon`-expressie in het script, niet uit dit plan, als de twee ergens verschillen:
het script is de bron.)

Run: `uv run python scripts/maak_ttl_fixtures.py && git diff --stat tests/fixtures/ttl/rvz_schoon.ttl`
Expected: drie nieuwe bestanden, `rvz_schoon.ttl` ongewijzigd.

- [ ] **Step 3: Falende tests**

`tests/test_checks_blok_a.py` — in `DEFECTEN` na de RVZ-001-rij:

```python
    ("rvz002_drempel_zonder_niveau.ttl", "RVZ-002", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-002", ["O"]),
    ("rvz003_drempel_zonder_breedte.ttl", "RVZ-003", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-003", ["O"]),
```

en:

```python
def test_rvz002_zwijgt_bij_een_drempel_met_niveau() -> None:
    assert labels(uitkomst("rvz003_drempel_zonder_breedte.ttl", "RVZ-002")) == []


def test_rvz002_verantwoordt_de_putten_zonder_drempel() -> None:
    outcome = uitkomst("rvz002_overstort_zonder_drempel.ttl", "RVZ-002")
    assert outcome.examined == 1
    assert any("zonder enig `Overstortdrempel`-onderdeel" in note for note in outcome.notes), outcome.notes
    assert any("Overstortput_Overstortdrempel_card" in note for note in outcome.notes)
```

`tests/test_checks_registry.py:61`: haal `"RVZ-002", "RVZ-003"` uit de set `geschrapt`.
`tests/test_config.py:12`: idem uit `REGISTER_IDS`; verwijder
`test_rvz_003_leunt_uitsluitend_op_hyd` (de mapping bestaat straks niet meer) of laat
hem op `ATTR-011` toetsen met de bijbehorende assertie (`vereiste_cfk == ["Hyd","MdsPlan","MdsProj"]`, `bewijs[0].vorm == "LengteLeiding_val"`).

Run: `uv run pytest tests/test_checks_blok_a.py -k rvz00 -v`
Expected: rood (`KeyError`/onbekende check RVZ-002, RVZ-003).

- [ ] **Step 4: De twee checks**

In `src/nlriochecker/checks/randvoorzieningen.py`, na RVZ-001 (zoek `id = "RVZ-001"` en
plaats erna) of onderaan de module:

```python
class _OverstortZonderDrempelkenmerk(Check):
    """Basis voor RVZ-002 en RVZ-003: een overstortput waarvan geen enkele drempel
    het gevraagde kenmerk draagt -- ook als er helemaal geen drempelonderdeel is.

    De nulmetingvorm `Overstortput_Overstortdrempel_card` meldt het ontbreken van het
    onderdeel zelf al; die overlap is bewust (BO-26): het register vraagt naar de
    geregistreerde waarde, en `toets` moet ook zonder `--shacl` iets zien.
    """

    kenmerk: str = ""  # "Drempelniveau" of "Drempelbreedte"
    omschrijving: str = ""  # "drempelniveau" of "drempelbreedte"

    def _waarde(self, drempel: Drempel) -> float | None:
        raise NotImplementedError

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke overstortput zonder geregistreerd kenmerk op een van haar drempels."""
        per_put = drempels_per_put(context)
        for node in overstortputten(context):
            groep = per_put.get(node.uri, [])
            if any(self._waarde(drempel) is not None for drempel in groep):
                continue
            if groep:
                tekst = (
                    f"Geen van de {len(groep)} overstortdrempels van deze put heeft een "
                    f"geregistreerd {self.omschrijving} (`{self.kenmerk}`)."
                )
            else:
                tekst = (
                    "Deze overstortput heeft geen enkel `Overstortdrempel`-onderdeel, en dus "
                    f"ook geen {self.omschrijving}."
                )
            yield self.finding(context, node.uri, node.label, tekst, drempels=len(groep))

    def notes(self, context: CheckContext) -> list[str]:
        """Zegt hoeveel putten geen drempel hebben en dat de nulmeting dat ook meldt."""
        per_put = drempels_per_put(context)
        putten = overstortputten(context)
        zonder = sum(1 for node in putten if not per_put.get(node.uri))
        notities = [
            f"Bekeken zijn de {len(putten)} overstortputten "
            f"({', '.join(context.config.klassen.overstortput)})."
        ]
        if zonder:
            notities.append(
                f"{zonder} daarvan staan zonder enig `Overstortdrempel`-onderdeel geregistreerd; "
                "de nulmetingvorm `Overstortput_Overstortdrempel_card` meldt dat ook. De "
                "overlap is bewust: deze check toetst de geregistreerde waarde en werkt ook "
                "zonder nulmeting."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal overstortputten."""
        return len(overstortputten(context))


@register
class OverstortZonderDrempelniveau(_OverstortZonderDrempelkenmerk):
    """RVZ-002: overstortput zonder geregistreerd drempelniveau."""

    id = "RVZ-002"
    title = "Overstort zonder geregistreerde drempelhoogte"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    kenmerk = "Drempelniveau"
    omschrijving = "drempelniveau"

    def _waarde(self, drempel: Drempel) -> float | None:
        return drempel.niveau


@register
class OverstortZonderDrempelbreedte(_OverstortZonderDrempelkenmerk):
    """RVZ-003: overstortput zonder geregistreerde drempelbreedte."""

    id = "RVZ-003"
    title = "Overstort zonder geregistreerde drempelbreedte"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    kenmerk = "Drempelbreedte"
    omschrijving = "drempelbreedte"

    def _waarde(self, drempel: Drempel) -> float | None:
        return drempel.breedte
```

Controleer in `checks/base.py` hoe `Check` abstracte leden declareert (`id`, `title`
als `ClassVar`?) en volg dat voor `kenmerk`/`omschrijving`. Zorg dat de basisklasse
zelf niet in `REGISTRY` komt (geen `@register`).

Werk de moduledocstring van `randvoorzieningen.py` bij: de zin over "Losse
`Overstortdrempel`-onderdelen ... komen er niet in voor" blijft waar, voeg toe dat
RVZ-002/003 dat per overstortput melden.

- [ ] **Step 5: Sentinels eruit, dekkingtests omdraaien**

`src/nlriochecker/dekking.toml`: verwijder de twee `[[check]]`-blokken RVZ-002 en RVZ-003
(regels 71-92) volledig.

`tests/test_coverage.py`: verwijder de twee RVZ-rijen uit de parametrisering en verwijder
`test_drempelvormen_ontbreken_in_de_shacl_meting`. Voeg toe (dit is de inhoudelijke poort):

```python
def test_elke_geschrapte_check_wordt_door_de_nulmeting_geraakt(result: CoverageResult) -> None:
    """Voorwaarde 3 van de schrapronde eist een sentinel per geschrapte check;
    `verify_register` toetst alleen of die er is, niet of hij iets aantoont. Dit is de
    inhoudelijke poort: een geschrapte check waarvan het bewijs in de referentiemeting
    nul meldingen oplevert, wordt door niets meer bewaakt (RVZ-002/003 waren zo'n gat)."""
    assert result.untouched == []
```

Controleer dat `result` hier op de mini-nulmeting (`shacl_drieluik`) draait en dat alle
vier de resterende geschrapte checks daarin geraakt worden (de parametrisering zegt
`TOUCHED` voor ADM-001/004/005 en ATTR-011, dus ja). Voeg dezelfde assertie toe in
`tests/test_integration.py::test_dekkingoordelen` (op de echte De Wolden-rapporten),
waar nu de twee `UNTOUCHED`-regels staan:

```python
    # Geen enkele geschrapte check mag ongeraakt blijven; zie test_coverage.py.
    assert result.untouched == []
```

`tests/test_cli.py:48` en `:69`, `tests/test_reporting.py:74-76`: deze toetsen de
weergave van "niet geraakt". Die weergave moet getest blijven, maar niet meer via
RVZ-002/003. Gebruik het patroon van `tests/test_coverage_regressie.py::_mapping_bestand`
om in `tmp_path` een mapping te schrijven met één verzonnen sentinel (bijv. id
`"ADM-001"`, `vorm_prefix = "BestaatNiet"`) en geef die via de bestaande CLI-optie voor de
dekkingmapping mee (zoek in `cli.py` naar de optie die `load_coverage_config` een pad
geeft; bestaat die niet, toets de weergave dan op `write_coverage_report` in
`test_reporting.py` met een `CoverageResult` uit `assess_coverage(analyse, eigen_config)`
en laat in `test_cli.py` de "niet geraakt"-asserties vervallen met een regel commentaar
waarom). De assertie in `test_cli.py:48` wordt dan `"Niet geraakte geschrapte checks" not in resultaat.output`.

- [ ] **Step 6: Groen, matrix, poort**

Run: `uv run python scripts/dekkingsmatrix.py`
Run: `uv run pytest tests/test_checks_blok_a.py tests/test_coverage.py tests/test_coverage_regressie.py tests/test_cli.py tests/test_reporting.py tests/test_config.py tests/test_checks_registry.py tests/test_dekkingsmatrix.py tests/test_uitvoer_identiteit_sweep.py -q`
Run: `uv run pytest tests/test_integration.py -q` (slaat over zonder `data/`; op deze
machine staat `data/` er, dus hij moet draaien).
Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: groen. `test_elk_defect_heeft_een_eigen_fixture` eist nu fixtures voor
RVZ-002 en RVZ-003 — die staan er.

- [ ] **Step 7: Commit en issue sluiten**

```bash
git add -A src/nlriochecker/checks/randvoorzieningen.py src/nlriochecker/dekking.toml data/ scripts/maak_ttl_fixtures.py tests/ docs/dekkingsmatrix.md
git commit -m "RVZ-002 en RVZ-003 terug in de engine: de nulmeting levert de dekking niet, en de dekkinganalyse eist nu dat elke sentinel iets aantoont"
gh issue close 6 --comment "Afgehandeld in <hash> op dev. Uitgezocht: in geen van de drie SHACL-rapporten bestaat een vorm op Drempelniveau of Drempelbreedte (het woord 'niveau' komt er niet in voor); de enige drempelvorm is Overstortput_Overstortdrempel_card, die toetst of de put een drempel hééft. De schrapping is teruggedraaid (register v0.9): RVZ-002 en RVZ-003 zijn gebouwd (W, Compleetheid) en gaan af op elke overstortput zonder geregistreerd niveau resp. breedte, ook als het drempelonderdeel zelf ontbreekt; de toelichting benoemt de overlap met de nulmetingvorm. De sentinels zijn uit dekking.toml. Het raakvlak klopte: verify_register toetste alleen ID-pariteit; er is nu een test dat CoverageResult.untouched leeg is op de mini-nulmeting én op de De Wolden-rapporten, zodat een schrapping zonder aantoonbare dekking voortaan in CI faalt. Op De Wolden: 218 meldingen per check (meting volgt in de afronding)."
```

---

## Task 7: Issue #1 — vulwaarden in BOB en maaiveld als leesregel, plus ATTR-013

**Files:**
- Modify: `src/nlriochecker/checkconfig.py` (nieuwe `VulwaardeOptions`, veld `vulwaarden` op `CheckConfig`)
- Modify: `src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml` (sectie `[vulwaarden]`, na `[inwinning]`)
- Modify: `src/nlriochecker/dataset.py` (`Vulwaarde`, velden op `Node`/`Conduit`, `markeer_vulwaarden`)
- Modify: `src/nlriochecker/toetsrun.py:194-203` (toepassen na `laad_met_cache`)
- Modify: `src/nlriochecker/checks/attributen.py` (ATTR-013)
- Modify: `src/nlriochecker/checks/hoogten.py:814-845` (HGT-018 `notes()`)
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md:86` (rij ATTR-013)
- Modify: `scripts/maak_ttl_fixtures.py` (fixture `attr013_vulwaarde_hoogte.ttl`)
- Create: `tests/test_dataset_vulwaarden.py`
- Modify: `tests/test_checks_blok_a.py`, `tests/test_checkconfig.py`
- Regenerate: `docs/dekkingsmatrix.md`

**Interfaces:**
- Produces in `dataset.py`:
  ```python
  @dataclass(frozen=True)
  class Vulwaarde:
      kind: str      # bijv. "BobBeginpuntLeiding"
      value: float   # de ruwe waarde die als vulwaarde gold

  Node.vulwaarden: tuple[Vulwaarde, ...] = ()
  Conduit.vulwaarden: tuple[Vulwaarde, ...] = ()

  def markeer_vulwaarden(dataset: GwswDataset, kenmerken: Sequence[str], band_m: float) -> GwswDataset
  ```
- Produces in `checkconfig.py`: `CheckConfig.vulwaarden: VulwaardeOptions` met
  `hoogte_kenmerken: list[str]` en `hoogte_band_m: float`.
- Kenmerknamen zoals in `dataset.py` constanten: `Maaiveldhoogte`, `Putdekselniveau`,
  `BobBeginpuntLeiding`, `BobEindpuntLeiding` (korte GWSW-namen; `Aspect.kind`).

- [ ] **Step 1: Config**

In `checkconfig.py`, na `InwinningOptions`:

```python
class VulwaardeOptions(BaseModel):
    """Welke hoogtekenmerken een vulwaarde rond 0 m NAP kunnen dragen.

    Sommige bronsystemen schrijven 0,000 als "niet geregistreerd" in plaats van het
    kenmerk leeg te laten. Dat is per project te beoordelen: in laag Nederland kan
    0,00 m NAP een echte meting zijn. Een lege lijst zet de leesregel uit.
    """

    model_config = ConfigDict(extra="forbid")

    # De kenmerken (korte GWSW-naam, zoals `Aspect.kind`) waarop de leesregel werkt.
    hoogte_kenmerken: list[str] = Field(default_factory=list)
    # |waarde| kleiner dan of gelijk aan deze band telt als vulwaarde.
    hoogte_band_m: float = Field(default=0.01, ge=0.0)
```

`CheckConfig`: `vulwaarden: VulwaardeOptions = Field(default_factory=VulwaardeOptions)`.

`checks.toml` en `configs/dewoldenhoogeveen.toml`, na de sectie `[inwinning]`:

```toml
[vulwaarden]
# Hoogtekenmerken waarin deze bronexport 0,000 schrijft voor "niet geregistreerd".
# In De Wolden is 25% van de BOB's en 14% van de maaiveldhoogten exact 0,00 bij een
# maaiveld van 5 tot 17 m NAP. Zo'n waarde wordt bij het laden als ontbrekend gelezen
# en door ATTR-013 een keer per object gemeld; de hoogtechecks slaan het object over
# en zeggen dat in hun toelichting. Een lege lijst zet de leesregel uit (laag
# Nederland: daar kan 0,00 m NAP een meting zijn).
hoogte_kenmerken = ["BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte", "Putdekselniveau"]
# |waarde| tot en met deze band geldt als vulwaarde; 0.01 omdat ook 0,01 voorkomt.
hoogte_band_m = 0.01
```

Test in `tests/test_checkconfig.py` (volg de stijl van de bestaande configtests):

```python
def test_vulwaarden_uit_de_standaardconfig() -> None:
    config = load_check_config()
    assert config.vulwaarden.hoogte_kenmerken == [
        "BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte", "Putdekselniveau"
    ]
    assert config.vulwaarden.hoogte_band_m == 0.01
```

Run: `uv run pytest tests/test_checkconfig.py -q` → rood, dan implementeren, groen.

- [ ] **Step 2: Falende tests voor de leesregel**

`tests/test_dataset_vulwaarden.py`:

```python
"""De vulwaarde-leesregel: 0,000 in een hoogtekenmerk is geen meting (issue #1)."""

from __future__ import annotations

from pathlib import Path

from nlriochecker.dataset import Vulwaarde, load_dataset, markeer_vulwaarden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
KENMERKEN = ["BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte", "Putdekselniveau"]


def _dataset():
    return load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl")


def test_markeren_zet_de_vulwaarde_op_none_en_onthoudt_haar() -> None:
    dataset = markeer_vulwaarden(_dataset(), KENMERKEN, 0.01)
    put = next(node for node in dataset.nodes.values() if node.label == "A")
    streng = next(conduit for conduit in dataset.conduits.values() if conduit.label == "1")

    assert put.maaiveld is None
    assert put.vulwaarden == (Vulwaarde("Maaiveldhoogte", 0.0),)
    assert streng.bob_start is None
    assert streng.bob_end == 8.55
    assert streng.vulwaarden == (Vulwaarde("BobBeginpuntLeiding", 0.0),)


def test_ruwe_dataset_blijft_onaangeraakt() -> None:
    ruw = _dataset()
    markeer_vulwaarden(ruw, KENMERKEN, 0.01)
    put = next(node for node in ruw.nodes.values() if node.label == "A")
    assert put.maaiveld == 0.0
    assert put.vulwaarden == ()


def test_lege_kenmerkenlijst_is_de_identiteit() -> None:
    ruw = _dataset()
    assert markeer_vulwaarden(ruw, [], 0.01) is ruw


def test_band_nul_markeert_alleen_exact_nul() -> None:
    dataset = markeer_vulwaarden(_dataset(), KENMERKEN, 0.0)
    put_b = next(node for node in dataset.nodes.values() if node.label == "B")
    # Put B heeft maaiveld 0.01: binnen band 0.01, buiten band 0.0.
    assert put_b.maaiveld == 0.01
    assert put_b.vulwaarden == ()
```

Fixture in `scripts/maak_ttl_fixtures.py`, bij de ATTR-fixtures (gebruik de HGT-helpers,
die zijn verderop gedefinieerd — plaats de fixture daarom ná `hoogteleiding`, bij de
HGT-fixtures, met een comment dat ze bij ATTR-013 hoort):

```python
# ATTR-013: vulwaarden in hoogtekenmerken (issue #1). Put A heeft maaiveld 0,00 (en
# geen deksel), put B maaiveld 0,01, put C is schoon; streng 1 heeft een BOB van 0,000
# aan het beginpunt. Met de standaardconfig meldt ATTR-013 put A, put B en streng 1;
# HGT-004 en HGT-014 zwijgen over hen met een toelichting.
FIXTURES["attr013_vulwaarde_hoogte.ttl"] = (
    "put A (maaiveld 0,00), put B (maaiveld 0,01) en streng 1 (BOB begin 0,000) dragen een vulwaarde",
    hoogteput("PutA", "A", A, mv=0.0, dek=None)
    + hoogteput("PutB", "B", B, mv=0.01, dek=None)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(0.0, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.60, 8.55)),
)
```

Run: `uv run python scripts/maak_ttl_fixtures.py && uv run pytest tests/test_dataset_vulwaarden.py -q`
Expected: rood (`ImportError: Vulwaarde`).

- [ ] **Step 3: De leesregel in `dataset.py`**

Na `Aspect` (regel ~100):

```python
@dataclass(frozen=True)
class Vulwaarde:
    """Een hoogtekenmerk dat een vulwaarde droeg en bij het lezen als ontbrekend geldt."""

    kind: str
    value: float
```

`Node` en `Conduit` krijgen als laatste veld `vulwaarden: tuple[Vulwaarde, ...] = ()`.

Na `load_dataset` (of onderaan de module):

```python
def markeer_vulwaarden(
    dataset: GwswDataset, kenmerken: Sequence[str], band_m: float
) -> GwswDataset:
    """Leest een hoogtekenmerk binnen de vulwaardeband als niet geregistreerd.

    Sommige exports schrijven 0,000 waar het kenmerk leeg hoort te zijn (De Wolden:
    een kwart van de BOB's). De checks zouden die nul als meting lezen en er duizenden
    hoogtefouten van maken. Deze stap zet zo'n kenmerk op `None` en onthoudt op het
    object dat en welke waarde er stond, zodat ATTR-013 het een keer kan melden en de
    hoogtechecks het object overslaan en dat in hun toelichting zeggen.

    De stap staat los van het laden: de cache bewaart de ruwe parse, de band is
    projectconfiguratie. Met een lege kenmerkenlijst is dit de identiteit.
    """
    if not kenmerken:
        return dataset
    gekozen = set(kenmerken)

    def vul(aspect: Aspect | None) -> bool:
        return (
            aspect is not None
            and aspect.kind in gekozen
            and aspect.number is not None
            and abs(aspect.number) <= band_m
        )

    nodes: dict[str, Node] = {}
    for uri, node in dataset.nodes.items():
        gevonden: list[Vulwaarde] = []
        velden: dict[str, object] = {}
        for veld in ("maaiveld_aspect", "deksel_aspect"):
            aspect = getattr(node, veld)
            if vul(aspect):
                gevonden.append(Vulwaarde(aspect.kind, aspect.number))
                velden[veld] = None
        nodes[uri] = replace(node, vulwaarden=tuple(gevonden), **velden) if gevonden else node

    conduits: dict[str, Conduit] = {}
    for uri, conduit in dataset.conduits.items():
        gevonden = []
        velden = {}
        for veld in ("bob_start_aspect", "bob_end_aspect"):
            aspect = getattr(conduit, veld)
            if vul(aspect):
                gevonden.append(Vulwaarde(aspect.kind, aspect.number))
                velden[veld] = None
        conduits[uri] = replace(conduit, vulwaarden=tuple(gevonden), **velden) if gevonden else conduit

    return replace(dataset, nodes=nodes, conduits=conduits)
```

Importeer `replace` uit `dataclasses` en `Sequence` uit `collections.abc`. Controleer
dat `Node.maaiveld_aspect.kind` inderdaad `"Maaiveldhoogte"` is en `deksel_aspect.kind`
`"Putdekselniveau"` (zie `_maaiveld_kenmerk`/`_deksel_kenmerk`, `dataset.py:512-570`);
zo niet, pas de namen in de config en de fixture aan zodat ze overeenkomen met
`Aspect.kind`. mypy: `replace(node, **velden)` met `dict[str, object]` kan een
type-klacht geven; schrijf de twee gevallen dan expliciet uit.

Run: `uv run pytest tests/test_dataset_vulwaarden.py -q` → groen.

- [ ] **Step 4: Toepassen in `toetsrun.py`**

Na `laad_met_cache(...)` en vóór `_typeringspoort(...)`:

```python
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
```

Import `markeer_vulwaarden` uit `nlriochecker.dataset`. Controleer dat `dataset` daarna
overal in `voer_toets_uit` de gemarkeerde versie is (ook in `Toetsuitslag`, als die de
dataset draagt).

- [ ] **Step 5: ATTR-013 — falende tests**

`tests/test_checks_blok_a.py`, `DEFECTEN`:

```python
    ("attr013_vulwaarde_hoogte.ttl", "ATTR-013", ["1", "A", "B"]),
```

Let op: `uitkomst()` in die testmodule laadt met `load_dataset` en past de leesregel niet
toe. Pas `uitkomst()` (of een nieuwe helper ernaast) aan zodat de dataset door
`markeer_vulwaarden(dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m)`
gaat vóór de `CheckContext` gebouwd wordt — dat is precies wat `toetsrun` doet, en zo
toetsen de blok-A-tests de werkelijke pijplijn. Controleer dat de rest van `DEFECTEN`
groen blijft (geen andere fixture heeft een hoogte binnen de band).

Plus:

```python
def test_attr013_meldt_een_keer_per_object_met_de_kenmerken() -> None:
    outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", "ATTR-013")
    per_label = {b.object_label: b for b in outcome.findings}
    assert per_label["1"].details["kenmerken"] == ["BobBeginpuntLeiding"]
    assert per_label["1"].details["waarden"] == [0.0]
    assert per_label["A"].details["kenmerken"] == ["Maaiveldhoogte"]
    assert outcome.examined == 5  # 3 putten + 2 strengen
    assert any("0.01" in note or "0,01" in note for note in outcome.notes)


def test_hoogtechecks_zwijgen_over_vulwaarden_met_toelichting() -> None:
    for check_id in ("HGT-004", "HGT-014"):
        outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", check_id)
        assert labels(outcome) == [], check_id
        assert outcome.notes, check_id


def test_attr013_zegt_dat_de_regel_uit_staat() -> None:
    config = fixtureconfig()
    config.vulwaarden.hoogte_kenmerken = []
    outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", "ATTR-013", config)
    assert outcome.findings == []
    assert any("uit" in note for note in outcome.notes)
```

(Pas de signatuur van `uitkomst` aan als die geen config-parameter heeft; volg hoe
`test_checks_netwerk._outcome` dat doet.)

`test_elk_defect_heeft_een_eigen_fixture` eist een fixture voor elk ATTR-ID; ATTR-013
staat er nu.

Run: `uv run pytest tests/test_checks_blok_a.py -k attr013 -v` → rood (onbekende check).

- [ ] **Step 6: ATTR-013**

In `src/nlriochecker/checks/attributen.py`, na ATTR-012:

```python
@register
class HoogteOpVulwaarde(Check):
    """ATTR-013: een hoogtekenmerk dat een vulwaarde draagt in plaats van een meting.

    De leesregel zelf staat in `dataset.markeer_vulwaarden` (toegepast in `toetsrun`);
    deze check meldt per object een keer wat die regel heeft weggezet, zodat het in de
    uitvoer staat en niet alleen in de toelichting van de hoogtechecks.
    """

    id = "ATTR-013"
    title = "Hoogtekenmerk op vulwaarde (rond 0 m NAP) geregistreerd als meting"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS

    def _objecten(self, context: CheckContext) -> list:
        return [*netwerkknopen(context), *vrijvervalrioolleidingen(context)]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk object waarop ten minste een hoogtekenmerk een vulwaarde was."""
        band = context.config.vulwaarden.hoogte_band_m
        for object_ in self._objecten(context):
            if not object_.vulwaarden:
                continue
            kenmerken = [vul.kind for vul in object_.vulwaarden]
            waarden = [vul.value for vul in object_.vulwaarden]
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"{', '.join(kenmerken)} staat op {', '.join(f'{w:g}' for w in waarden)} m NAP; "
                f"binnen de vulwaardeband van {band:g} m geldt dat als niet geregistreerd.",
                kenmerken=kenmerken,
                waarden=waarden,
                band_m=band,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Zegt waarop de leesregel werkte, of dat hij uit staat."""
        opties = context.config.vulwaarden
        if not opties.hoogte_kenmerken:
            return [
                "De vulwaarde-leesregel staat uit (`[vulwaarden] hoogte_kenmerken` is leeg); "
                "een 0,000 in een hoogtekenmerk is in dit project als meting gelezen."
            ]
        return [
            f"Als vulwaarde gold |waarde| <= {opties.hoogte_band_m:g} m op "
            f"{', '.join(opties.hoogte_kenmerken)}. Zo'n kenmerk is als ontbrekend gelezen; "
            "de hoogtechecks slaan het object over en melden dat in hun toelichting."
        ]

    def examined(self, context: CheckContext) -> int:
        """Putten plus vrijvervalstrengen."""
        return len(self._objecten(context))
```

Importeer `netwerkknopen` uit `nlriochecker.checks.selectie` (staat daar op regel 67)
en `Check` uit `checks.base` als dat nog niet gebeurt.

- [ ] **Step 7: HGT-018 krijgt een toelichting**

In `hoogten.py`, `BuiskruinBovenMaaiveld`, voeg toe:

```python
    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengeinden zonder BOB of zonder bovenkant zijn overgeslagen."""
        uiteinden = _uiteinden(context)
        return [
            *_ontbreekt(context, "BOB", lambda u: u.bob, objecten=uiteinden, soort="strengeinden"),
            *_ontbreekt(
                context, "bovenkant (dekselniveau of maaiveld) aan de put",
                lambda u: u.node.bovenkant, objecten=uiteinden, soort="strengeinden",
            ),
        ]
```

- [ ] **Step 8: Register en matrix**

`data/checkregister-gwsw-nulmeting-v0_9.md`, ATTR-tabel, na ATTR-012:

```
| ATTR-013 | Hoogtekenmerk (BOB, maaiveldhoogte, putdekselniveau) op een vulwaarde rond 0 m NAP dat als meting geregistreerd staat; de band en de kenmerken zijn projectconfiguratie (`[vulwaarden]`), de leesregel zet het kenmerk op ontbrekend en de hoogtechecks slaan het object over | W | Compleetheid |
```

Run: `uv run python scripts/dekkingsmatrix.py`

- [ ] **Step 9: Groen en poort**

Run: `uv run pytest tests/test_checks_blok_a.py tests/test_dataset_vulwaarden.py tests/test_checkconfig.py tests/test_checks_registry.py tests/test_dekkingsmatrix.py tests/test_uitvoer_identiteit_sweep.py tests/test_toetsrun.py -q`
Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`
Expected: groen.

- [ ] **Step 10: Commit en issue sluiten**

```bash
git add -A src/ tests/ scripts/maak_ttl_fixtures.py data/ configs/ docs/dekkingsmatrix.md
git commit -m "Een vulwaarde rond 0 m NAP in BOB of maaiveld is geen meting: leesregel bij het laden en ATTR-013 meldt het een keer per object"
gh issue close 1 --comment "Afgehandeld in <hash> op dev. Beslissing (beslislog BO-27, register v0.9): een leesregel in dataset.markeer_vulwaarden, toegepast in toetsrun direct na het laden, zet een hoogtekenmerk met |waarde| <= band op ontbrekend en onthoudt dat op het object; nieuwe check ATTR-013 (W, Compleetheid) meldt het één keer per object; HGT-002/003/004/014/018 slaan het object over en zeggen dat in hun toelichting (HGT-018 had die nog niet). Configureerbaar in [vulwaarden]: hoogte_kenmerken (lege lijst = uit, voor laag Nederland) en hoogte_band_m = 0.01. Gemeten effect op De Wolden volgt in de afronding van deze ronde."
```

---

## Task 8: Zware meting, CHANGELOG, beslislog

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Modify: `docs/beslislog.md` (BO-25, BO-26, BO-27 onder `## Onderhoud`, na BO-24)

- [ ] **Step 1: De volledige run op De Wolden + Hoogeveen**

Run (duurt minuten; de cache van de dataset helpt, de leesregel loopt erna):

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --projectconfig configs/dewoldenhoogeveen.toml \
  --bronnen data/gis_dewoldenhoogeveen \
  --output uitvoer/bugronde 2> uitvoer/bugronde.stderr
```

Haal uit `uitvoer/bugronde/bevindingen.csv` (kolomnamen: kijk in de kop) per check het
aantal meldingen: ATTR-006 (en controleer `grep -c 'id_sleutels' uitvoer/bugronde.stderr`
= 0), ATTR-013, RVZ-002, RVZ-003, NET-004, EXT-002, EXT-003 (moeten gelijk zijn: 859),
HGT-002/003/004/014/018, en de totalen F en W. Vergelijk met de cijfers in de issues
(issue #1: 31.901 F; HGT-002 5.231, HGT-003 2.813, HGT-004 532, HGT-018 1.190, HGT-014 889;
issue #3: 859/859; issue #2: 18 waarschuwingen; issue #5: 17 NET-004).
Meet `uitvoer/` niet mee in git (`.gitignore`).

- [ ] **Step 2: Getallen op de issues**

Voor elk van de vijf issues: `gh issue comment <n> --body "Gemeten op De Wolden + Hoogeveen (commit <hash>): ..."` met de getallen van dat issue. Klopt een getal niet met de verwachting (bijv. EXT-002 ≠ EXT-003, of de F-daling wijkt ver af van ~5.700), dan is dat een bevinding: stop, zoek de oorzaak, en schrijf die in de reactie — rapporteer geen cijfer dat je niet gelooft.

- [ ] **Step 3: CHANGELOG**

Onder `## [Unreleased]`, in de passende subsecties (`### Toegevoegd`, `### Gewijzigd`,
`### Gerepareerd` — kijk welke er staan):

```markdown
- Checkregister v0.9: RVZ-002 en RVZ-003 zijn uit de tabel Geschrapte checks gehaald en
  gebouwd, ATTR-013 is toegevoegd, EXT-003 is gepreciseerd. De vijf versieverwijzingen
  wijzen naar v0.9.
- RVZ-002 en RVZ-003 (W, Compleetheid): een overstortput zonder geregistreerd
  drempelniveau resp. drempelbreedte, ook zonder drempelonderdeel. De nulmeting kent
  geen vorm op die twee kenmerken; de sentinels zijn uit `dekking.toml`. Nieuwe
  regressietest: geen enkele geschrapte check mag in de referentiemeting ongeraakt
  blijven (issue #6).
- ATTR-013 (W, Compleetheid) en de vulwaarde-leesregel `dataset.markeer_vulwaarden`,
  geconfigureerd in `[vulwaarden]`: een hoogtekenmerk met |waarde| <= `hoogte_band_m`
  geldt als niet geregistreerd. Op De Wolden vervallen daarmee circa <gemeten> harde
  fouten in HGT-002/003/004/014/018 die op een 0,000 stonden; ATTR-013 meldt <gemeten>
  objecten. HGT-018 heeft nu een toelichting (issue #1).
- ATTR-006 zet de zijde (begin- of eindpunt) in de melding; de twee meldingen op een
  streng krijgen een eigen, stabiele ID. **De melding-ID's van ATTR-006 verschuiven
  eenmalig**; `schema_versie` blijft 1.0 (issue #2).
- NET-004 noemt bij parallelle strengen de eerste op de kant (gesorteerd op URI) in
  plaats van de laatst ingelezen; de graafkanten dragen geen attributen meer. De
  genoemde streng kan eenmalig verschuiven (issue #5).
- EXT-002 en EXT-003 delen een kruisingenlijst en melden in hun toelichting hoeveel
  duikers buiten de populatie vallen; de testfixtures volgen de ontologie (Duiker onder
  Leiding, Zinker onder VrijvervalRioolleiding). Geen verandering in de meldingen
  (issue #3).
```

Vul `<gemeten>` in met de getallen uit stap 1.

- [ ] **Step 4: Beslislog**

Na BO-24 in `docs/beslislog.md`, in de stijl van de bestaande BO's (kop, Besluit, Waarom,
Gevolg; lees BO-24 als voorbeeld):

- **BO-25 Een duiker is geen rioolleiding; EXT-002/003 blijven op VrijvervalRioolleiding**
  — de ontologiefeiten (Duiker ⊂ Leiding, "verbindt oppervlaktewater"; Zinker ⊂
  VrijvervalRioolleiding), de verworpen alternatieven (populatie verbreden naar Leiding:
  drains en kolkaansluitingen als kruising; EXT-003 een eigen populatie: bekijken om uit
  te zonderen is theater), de fixturecorrectie, en dat het rapport de duikers buiten de
  populatie telt.
- **BO-26 RVZ-002 en RVZ-003 terug; een sentinel moet iets aantonen** — de SHACL-feiten,
  de keuze om ook putten zonder drempelonderdeel te melden (overlap met `_card` bewust,
  werkt zonder `--shacl`), W/Compleetheid naar analogie van RVZ-007/008/009, en de nieuwe
  test op `CoverageResult.untouched == []` als inhoudelijke poort naast de ID-pariteit
  van `verify_register`.
- **BO-27 Een vulwaarde rond 0 m NAP is geen meting: leesregel plus ATTR-013** — de
  getallen uit issue #1, waarom een leesregel ná het laden (cache bewaart de ruwe parse,
  band is projectconfig, één toepassingsplek in `toetsrun`), waarom een nieuw ATTR-nummer
  en geen HGT (registratiegebrek, geen hoogtefout), waarom een band en geen exacte nul
  (0,01 komt voor), waarom `[vulwaarden]` met een lege lijst als uit-schakelaar (TOML
  kent geen null; laag Nederland), en dat het alternatief "elke HGT-check filtert zelf"
  verworpen is.

- [ ] **Step 5: Poort en commit**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest -q`

```bash
git add CHANGELOG.md docs/beslislog.md
git commit -m "Bugronde vastgelegd: wijzigingslog en drie beslissingen (BO-25 t/m BO-27)"
```

---

## Task 9: Reviewstappen

- [ ] **Step 1:** Draai `/superpowers:requesting-code-review` over `git diff 7d810ea..HEAD`
  (de spec-commit is het beginpunt van deze ronde). Verwerk de bevindingen; houd je aan
  `superpowers:receiving-code-review` (verifieer voordat je wijzigt).
- [ ] **Step 2:** Draai `/python-library-complete:reviewing-python-libraries`; verwerk wat
  op deze ronde slaat.
- [ ] **Step 3:** Poort, commit: `git commit -m "Reviewbevindingen van de bugronde verwerkt"`.
- [ ] **Step 4:** Controleer dat `gh issue list --label bug --state open` leeg is en dat
  elk gesloten issue een reactie met commit-hash én gemeten getallen heeft. Meld in de
  eindrapportage per issue: commit, testnaam, gemeten effect, en wat er bewust niet is
  gedaan (bijv. geen merge naar `main`, geen pakketversiebump).
