# Issue #60: fantoomkoppeling herstellen en TOP-022/TOP-023 (hulpstuk met een ander aantal aansluitingen) — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) De lader herstelt de fantoomkoppeling `<hulpstuk>_put` naar de knoop van het hulpstuk en meldt dat als datasetsignaal; (2) twee nieuwe checks tellen per hulpstuk de aangesloten richtingen tegen het aantal dat de GWSW-`functie`-restrictie op zijn klasse voorschrijft: **TOP-022** (F, minder) en **TOP-023** (W, meer).

**Architecture:** Het herstel zit in `_connected_node` in `src/nlriochecker/dataset.py` (alleen als geen enkel `hasConnection`-doel een bekende orientatie is, en alleen als de naamstam een knoop met een `Hulpstukorientatie` is); de telling landt in een nieuw veld `GwswDataset.koppelingsherstel` en gaat via `uitvoer/omvang.py` → `uitvoer/melding.py` als tweede datasetsignaal (`SIG-hulpstukkoppeling`) de meldingenstroom in, naast `SIG-nulklasse`. Het verwachte aantal leidingen komt uit de ontologie: `load_dataset` leest per hulpstukklasse de `owl:Restriction` op `gwsw:functie` (`ontologie.functie_van_klasse`) in een afgeleid woordenboek `GwswDataset.functie_per_klasse`; de checks in `checks/topologie.py` vertalen de functiewaarde naar een getal (`AANTAL_PER_FUNCTIE`) en tellen buurknopen, niet strengen.

**Tech Stack:** Python 3.12, rdflib/pyoxigraph via `GraafIndex` (bestaand), pytest. Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #60 (`gh issue list --json number,body --search 60`).

## Global Constraints

- **Ruling van de regisseur — twee ID's, niet één met twee ernsten.** De engine kent per check-ID precies één ernst (`Check.severity` is een ClassVar en `tests/test_checks_registry.py::test_ernst_en_dimensie_volgen_het_register` bindt hem aan de registerregel). Daarom: **TOP-022** = minder richtingen dan verwacht, `Severity.ERROR`; **TOP-023** = meer richtingen dan verwacht, `Severity.WARNING`. Beide `Dimension.CONSISTENCY`. Het issue nam één ID aan; de afwijking staat in BO-46 en in de afsluitende issue-comment.
- Herstelregel (stap 1), letterlijk: alleen als géén `hasConnection`-doel van het strengeindpunt in `orientation_to_node` staat, probeer per doel: strip de staart `_put`; is wat overblijft een URI in `nodes` waarvan `orientation_types` een klasse uit de afsluiting van `Hulpstukorientatie` bevat, dan is dát de knoop. Anders `None`, zoals nu. Niet ruimer zoeken.
- Het herstel wordt geteld (aantal herstelde koppelingen én aantal verschillende hulpstukken) en als datasetsignaal gemeld: `bron = "dataset"`, categorie `SIG`, `check_id = "SIG-hulpstukkoppeling"`, ernst W, systemisch, zonder object — dezelfde weg als `SIG-nulklasse`. Alleen als het aantal > 0 is.
- Verwacht aantal per functiewaarde: `VerbindenVanTweeLeidingen` → 2, `VerbindenVanDrieLeidingen` → 3, `VerbindenVanVierLeidingen` → 4. Welke klasse welke functie draagt komt uit de ontologie (of uit de inline restricties van een fixture), nooit uit code of config. Klassen zonder functiewaarde-met-aantal (`Afsluitstuk`, `Ontstoppingsstuk`, `Tubelure`, `Bochtstuk`, `Verloopstuk`, `Overgangsstuk`, `Verbindingsstuk` zelf) vallen buiten de toets en worden per klasse in `notes()` geteld.
- Telling per hulpstuk: het aantal **verschillende knopen aan de andere kant** (via `resolve_network_node` naar de put, met terugval op de rauwe URI), plús het aantal strengen waarvan het andere eind aan niets hangt (elk telt als een eigen richting). Een streng met beide einden aan hetzelfde hulpstuk telt niet.
- Populatie: de rol `hulpstukken` (`[klassen] hulpstuk = ["Hulpstuk"]`, nieuw in beide TOML's en in `ClassRoots`), via een nieuwe selectie `selectie.hulpstukken(context)`. `examined` = het aantal hulpstukken mét telbare functie.
- Gegenereerde bestanden nooit met de hand bewerken: `tests/fixtures/ttl/*.ttl` via `uv run python scripts/maak_ttl_fixtures.py`, `docs/dekkingsmatrix.md` via `uv run python scripts/dekkingsmatrix.py`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten; volg de stijl van `dataset.py` en `topologie.py`. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden, nooit `git add -A` (er kunnen ongecommitte planbestanden van andere issues in de werkmap staan).
- Nieuw BO-nummer: het eerstvolgende na het laatste `### BO-` in `docs/beslislog.md` (verwacht **BO-46**; controleer met `grep -n '^### BO-' docs/beslislog.md | tail -1`). Gebruik dat nummer overal waar dit plan `BO-46` schrijft.
- CHANGELOG onder `## [Unreleased]`: de herstelregel onder `### Gerepareerd` (bovenaan die sectie), de checks onder `### Toegevoegd` (bovenaan; maak die kop aan boven de andere koppen als hij ontbreekt).
- De cache van `laad_met_cache` invalideert zichzelf: `dataset.py` zit in de cachesleutel. Nieuwe velden op `GwswDataset` krijgen een default, zodat `GwswDataset(graph=GraafIndex(), **velden)` in `cache.py` blijft werken.

---

### Task 1: De fantoomkoppeling herstellen en melden

**Files:**
- Modify: `src/nlriochecker/dataset.py` (constanten bij regel 73; nieuwe dataclass `Koppelingsherstel` bij `DecodeFallback`; veld op `GwswDataset`; `load_dataset`; `_read_conduits`; `_connected_node`)
- Modify: `src/nlriochecker/uitvoer/omvang.py` (nieuwe `HerstelSignaal` + `koppelingsherstel(run)`), `src/nlriochecker/uitvoer/melding.py` (`CHECK_HULPSTUKKOPPELING`, `_signaalmeldingen`), `src/nlriochecker/uitvoer/bevindingen.py` (`_omvang_section`, na het `op_nul`-blok)
- Modify: `scripts/maak_ttl_fixtures.py` (`put()` krijgt `orientatie=`; nieuwe helpers `HULPSTUK_KLASSEN` en `hulpstuk()`; nieuwe fixture `dataset_fantoomkoppeling.ttl`)
- Regenerate: `tests/fixtures/ttl/dataset_fantoomkoppeling.ttl`
- Modify: `tests/test_dataset.py` (twee tests), `tests/test_uitvoer_klassentelling.py` (één testklasse)
- Modify: `docs/architectuur.md:22` en `:56-62`, `docs/json-schema.md:236-241`

**Interfaces:**
- Consumes: `GraafIndex.objects/subjects/value`, `_connections(graph, subject)`, `_afsluiting(subclasses, wortel)`, `Node.orientation_types: frozenset[str]` (volledige URI's), `_uniek_id(check_id, object_uri, object2_uri, onderscheid, aanduiding, gebruikt)` in `melding.py`, `getal(aantal, enkelvoud, meervoud)` uit `nlriochecker.taal`.
- Produces: `Koppelingsherstel(koppelingen: int = 0, hulpstukken: int = 0)` (frozen dataclass in `dataset.py`); `GwswDataset.koppelingsherstel: Koppelingsherstel`; `_read_conduits(...) -> tuple[dict[str, Conduit], Koppelingsherstel]`; `omvang.HerstelSignaal(koppelingen, hulpstukken, boodschap)` en `omvang.koppelingsherstel(run) -> HerstelSignaal | None`; `melding.CHECK_HULPSTUKKOPPELING = "SIG-hulpstukkoppeling"`; fixturehelpers `HULPSTUK_KLASSEN: str` en `hulpstuk(naam, label, x, y, klasse="T_stuk") -> str` (Task 2 gebruikt ze ook).

- [ ] **Step 1: Fixturehelpers en de fantoomfixture (generator, niet het bestand)**

In `scripts/maak_ttl_fixtures.py`:

1. Geef `put()` een extra parameter en gebruik hem in de orientatieregel — bestaande aanroepen veranderen niet van uitvoer:

```python
def put(
    naam: str,
    label: str,
    x: float,
    y: float,
    klasse: str = "Inspectieput",
    extra: str = "",
    orientatie: str = "Putorientatie",
) -> str:
    return f''':{naam} rdf:type gwsw:{klasse} ; rdfs:label "{label}" ;
    gwsw:hasAspect :{naam}_ori .{extra}
:{naam}_ori rdf:type gwsw:{orientatie} ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>{x} {y}</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
'''
```

2. Direct ná `put()` (vóór `leiding()`):

```python
# Hulpstukken staan niet in de gedeelde prelude: alleen de fixtures van issue #60 hebben
# ze nodig, mét de functierestrictie waar TOP-022/TOP-023 het verwachte aantal leidingen
# uit lezen. Een fixture die dit blok opneemt krijgt ook de owl-prefix; een prefixregel
# mag in Turtle overal op statementniveau staan.
HULPSTUK_KLASSEN = (
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "# Hulpstukken, met de functierestrictie uit de GWSW-ontologie (issue #60).\n"
    "gwsw:Hulpstukorientatie rdfs:subClassOf gwsw:Knooppunt .\n"
    "gwsw:Verbindingsstuk rdfs:subClassOf gwsw:Hulpstuk .\n"
    "gwsw:Afsluitstuk rdfs:subClassOf gwsw:Hulpstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:AfsluitenVanLeidingen ] .\n"
    "gwsw:T_stuk rdfs:subClassOf gwsw:Verbindingsstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:VerbindenVanDrieLeidingen ] .\n"
    "gwsw:Kruisstuk rdfs:subClassOf gwsw:Verbindingsstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:VerbindenVanVierLeidingen ] .\n\n"
)


def hulpstuk(naam: str, label: str, x: float, y: float, klasse: str = "T_stuk") -> str:
    """Een hulpstuk: als een put, maar met een Hulpstukorientatie als knooppunt."""
    return put(naam, label, x, y, klasse=klasse, orientatie="Hulpstukorientatie")
```

3. Direct ná het blok `FIXTURES["selectie_rollen.ttl"] = (...)` (zoek het op naam; het eindigt met `klasse="Sloot"),\n)`), een nieuwe fixture:

```python
# Issue #60, stap 1: de BrutIS-export koppelt elk leidingeinde op een hulpstuk aan
# `<hulpstuk>_put`, een URI zonder type of aspect, terwijl de orientatie `<hulpstuk>_ori`
# heet (in De Wolden `_put<n>`). Streng 1 heeft zo'n fantoomdoel en hoort na het herstel
# aan T1 te hangen; streng 2 koppelt netjes; streng 3 wijst naar een stam die geen
# hulpstuk is en blijft los.
FIXTURES["dataset_fantoomkoppeling.ttl"] = (
    "streng 1 koppelt haar eindpunt aan :T1_put, een URI die niet bestaat; de orientatie "
    "van T-stuk T1 heet :T1_ori (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", None)
    + ":L1_e gwsw:hasConnection :T1_put .\n"
    + put("PutB", "B", 1100.0, 2000.0)
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "PutB")
    + put("PutC", "C", 1050.0, 2050.0)
    + leiding("L3", "3", [(1050.0, 2050.0), (1050.0, 2000.0)], "PutC", None)
    + ":L3_e gwsw:hasConnection :Onbekend_put .\n",
)
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. Controleer met `git status --short` dat alleen `tests/fixtures/ttl/dataset_fantoomkoppeling.ttl` nieuw is en géén bestaande fixture verandert (de `orientatie=`-parameter heeft dezelfde default als de oude tekst).

- [ ] **Step 2: Schrijf de falende tests**

In `tests/test_dataset.py`, onderaan:

```python
FANTOOM = TTL_DIR / "dataset_fantoomkoppeling.ttl"
TOETS = "http://example.org/toets#"


def test_fantoomkoppeling_naar_een_hulpstuk_wordt_op_naamstam_hersteld() -> None:
    """`:L1_e hasConnection :T1_put` bestaat nergens; de stam `:T1` is een T-stuk (issue #60).

    Streng 2 koppelt netjes aan de orientatie en telt niet als herstel; streng 3 wijst
    naar `:Onbekend_put`, waarvan de stam geen hulpstukknoop is, en blijft los.
    """
    from nlriochecker.dataset import Koppelingsherstel

    dataset = load_dataset(FANTOOM)

    assert dataset.conduits[f"{TOETS}L1"].end_node == f"{TOETS}T1"
    assert dataset.conduits[f"{TOETS}L2"].start_node == f"{TOETS}T1"
    assert dataset.conduits[f"{TOETS}L3"].end_node is None
    assert dataset.koppelingsherstel == Koppelingsherstel(koppelingen=1, hulpstukken=1)


def test_zonder_fantoomkoppeling_is_er_niets_hersteld(juinen: GwswDataset) -> None:
    assert juinen.koppelingsherstel.koppelingen == 0
```

In `tests/test_uitvoer_klassentelling.py`, onderaan (gebruik de imports en helpers die het bestand al heeft; `load_dataset`, `CheckContext`, `CheckRun`, `bouw_meldingen`, `BRON_DATASET` en `_omvang_section` staan al in de importlijst — voeg `from nlriochecker.checks import run_checks` en `from nlriochecker.uitvoer.melding import CHECK_HULPSTUKKOPPELING` toe waar dat nodig is, en `TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"` als die constante ontbreekt):

```python
class TestKoppelingsherstel:
    """Het herstel van de fantoomkoppeling is een datasetsignaal, geen stille reparatie."""

    def _run(self) -> CheckRun:
        config = load_check_config()
        config.drempels.rd_y_min = 0.0
        dataset = load_dataset(TTL_DIR / "dataset_fantoomkoppeling.ttl")
        return run_checks(CheckContext(dataset=dataset, config=config), ["TOP-001"])

    def test_herstelde_koppelingen_geven_een_systemische_waarschuwing(self) -> None:
        meldingen = bouw_meldingen(self._run(), date(2026, 8, 24))
        signaal = [m for m in meldingen if m.check_id == CHECK_HULPSTUKKOPPELING]

        assert len(signaal) == 1
        assert signaal[0].bron == BRON_DATASET
        assert signaal[0].ernst == "W" and signaal[0].systemisch is True
        assert signaal[0].object_uri == "" and signaal[0].foutlocatie is None
        assert signaal[0].waarde == "1"
        assert "1 leidingeind" in signaal[0].boodschap and "1 hulpstuk" in signaal[0].boodschap

    def test_het_rapport_noemt_het_herstel(self) -> None:
        run = self._run()
        tekst = "\n".join(_omvang_section(run, bouw_meldingen(run, date(2026, 8, 24))))
        assert "Herstelde hulpstukkoppelingen" in tekst
```

Controleer de signatuur van `_omvang_section` in `src/nlriochecker/uitvoer/bevindingen.py` en roep hem aan zoals de bestaande tests in dit bestand dat doen; pas de aanroep hierboven daarop aan.

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_dataset.py tests/test_uitvoer_klassentelling.py -k "fantoom or hersteld or Koppelingsherstel" -v`
Expected: FAIL met `ImportError` (`Koppelingsherstel`, `CHECK_HULPSTUKKOPPELING`) of `AttributeError: koppelingsherstel`.

- [ ] **Step 4: Implementeer het herstel in de lader**

In `src/nlriochecker/dataset.py`:

1. Bij de constanten (na `WORTEL_VERBINDING = "Verbinding"`, regel 74):

```python
WORTEL_HULPSTUKORIENTATIE = "Hulpstukorientatie"
# De staart die de BrutIS-export achter de naam van een hulpstuk plakt in het
# hasConnection-doel van een leidingeinde, waar de orientatie zelf anders heet.
FANTOOM_STAART = "_put"
```

2. Direct ná de dataclass `DecodeFallback`:

```python
@dataclass(frozen=True)
class Koppelingsherstel:
    """Hoeveel `hasConnection`-doelen de lader op naamstam naar een hulpstuk herleid heeft.

    De BrutIS-export van De Wolden en Hoogeveen koppelt élk leidingeinde dat op een
    hulpstuk uitkomt aan `<hulpstuk>_put`, een URI zonder type of aspect, terwijl de
    orientatie `<hulpstuk>_put<n>` heet. Zonder herstel ziet de engine bij alle 1054
    T-stukken nul leidingen en hangen 3024 strengeinden aan niets. Het herstel is
    bewust smal (alleen een onbekend doel, alleen als de stam een hulpstukknoop is) en
    wordt hier geteld, zodat het rapport de aanlevering blijft aanwijzen in plaats van
    het gebrek stilletjes op te ruimen (issue #60).
    """

    koppelingen: int = 0
    hulpstukken: int = 0
```

3. In `GwswDataset`, ná `kenmerk_property`:

```python
    # Het herstel van de fantoomkoppeling naar hulpstukken (issue #60); nul zonder
    # fantomen. Het rapport meldt het als datasetsignaal `SIG-hulpstukkoppeling`.
    koppelingsherstel: Koppelingsherstel = Koppelingsherstel()
```

4. In `load_dataset`, ná `deksel = _afsluiting(subclasses, "Putdeksel")`:

```python
    hulpstuk = _afsluiting(subclasses, WORTEL_HULPSTUKORIENTATIE)
```

en vervang `conduits = _read_conduits(graph, nodes, geometry_errors, verbinding)` door `conduits, herstel = _read_conduits(graph, nodes, geometry_errors, verbinding, hulpstuk)`; geef `koppelingsherstel=herstel,` mee aan de `GwswDataset(...)`-constructor (ná `kenmerk_property=kenmerk_property,`).

5. `_read_conduits`: signatuur en einde worden

```python
def _read_conduits(
    graph: GraafIndex,
    nodes: dict[str, Node],
    errors: dict[str, str],
    verbinding_klassen: frozenset[str] | None = None,
    hulpstuk_klassen: frozenset[str] = frozenset(),
) -> tuple[dict[str, Conduit], Koppelingsherstel]:
```

Vul de docstring aan met: `Geeft naast de verbindingen het herstel van de fantoomkoppeling terug (issue #60).` Bouw ná `orientation_to_node = {...}`:

```python
    hulpstukken = frozenset(
        uri for uri, node in nodes.items() if node.orientation_types & hulpstuk_klassen
    )
    hersteld: list[str] = []
```

geef aan beide `_connected_node`-aanroepen `hulpstukken, hersteld` als extra argumenten mee, en eindig met

```python
    return conduits, Koppelingsherstel(len(hersteld), len(set(hersteld)))
```

Grep vóór je verder gaat naar andere aanroepers: `grep -rn '_read_conduits' src tests` — pas elke aanroep aan op de tuple.

6. `_connected_node` wordt

```python
def _connected_node(
    graph: GraafIndex,
    endpoint: RdfNode | None,
    orientation_to_node: dict[str, str],
    hulpstukken: frozenset[str] = frozenset(),
    hersteld: list[str] | None = None,
) -> str | None:
    """Herleidt de hasConnection van een strengeindpunt naar de put erachter.

    Twee dingen die uit de GWSW-documentatie volgen. De koppeling wijst naar de
    putorientatie, niet naar de put zelf; die extra stap wordt hier gezet. En
    gwsw:hasConnection is een owl:SymmetricProperty zonder inverse, dus de
    tripel mag ook andersom geschreven zijn; beide richtingen tellen.

    Eén herstel, en niet meer (issue #60): wijst geen enkel doel naar een bekende
    orientatie, dan wordt per doel de staart `_put` gestript; is de stam een knoop
    met een Hulpstukorientatie, dan is dat de knoop en gaat het doel in `hersteld`.
    Ruimer zoeken is gokken op namen, en dat hoort niet in een kritiek pad.
    """
    if endpoint is None:
        return None
    doelen = [str(target) for target in _connections(graph, endpoint)]
    for doel in doelen:
        node_uri = orientation_to_node.get(doel)
        if node_uri is not None:
            return node_uri
    for doel in doelen:
        stam = doel.removesuffix(FANTOOM_STAART)
        if stam != doel and stam in hulpstukken:
            if hersteld is not None:
                hersteld.append(stam)
            return stam
    return None
```

- [ ] **Step 5: Het signaal in de meldingenstroom en het rapport**

1. `src/nlriochecker/uitvoer/omvang.py`, onderaan (na `klassen_op_nul`):

```python
@dataclass(frozen=True)
class HerstelSignaal:
    """Het datasetsignaal over de herstelde fantoomkoppelingen (issue #60)."""

    koppelingen: int
    hulpstukken: int
    boodschap: str


def koppelingsherstel(run: CheckRun) -> HerstelSignaal | None:
    """Het signaal over de fantoomkoppeling, of None als de lader niets hoefde te herstellen.

    Herstel dat je niet meldt is stille interpretatie: de export koppelt leidingeinden
    aan een orientatie-URI die niet bestaat, en de lader raadt de knoop op naamstam.
    Dat het rapport dat zegt, houdt de aanlevering aanwijsbaar.
    """
    herstel = run.dataset.koppelingsherstel
    if not herstel.koppelingen:
        return None
    return HerstelSignaal(
        herstel.koppelingen,
        herstel.hulpstukken,
        f"De export koppelt {getal(herstel.koppelingen, 'leidingeind', 'leidingeinden')} aan "
        "een orientatie-URI die niet bestaat (`<hulpstuk>_put`, waar de Hulpstukorientatie van "
        f"{getal(herstel.hulpstukken, 'hulpstuk', 'hulpstukken')} anders heet). De lader heeft "
        "die koppelingen op naamstam hersteld zodat de netwerkchecks ze zien; de aanlevering "
        "zelf is daar niet op verbeterd.",
    )
```

Importeer `getal` uit `nlriochecker.taal` bovenaan `omvang.py`.

2. `src/nlriochecker/uitvoer/melding.py`: importeer `koppelingsherstel` naast `klassen_op_nul`; ná `CHECK_NULKLASSE = "SIG-nulklasse"`:

```python
# Het tweede datasetsignaal: de fantoomkoppeling naar hulpstukken die de lader op
# naamstam hersteld heeft (issue #60). Zelfde vorm als de nul-bewaking.
CHECK_HULPSTUKKOPPELING = "SIG-hulpstukkoppeling"
```

Werk de commentaarregels boven `BRON_DATASET` bij ("Nu alleen de nul-bewaking" → "de nul-bewaking van issue #22 en het koppelingsherstel van issue #60"). Trek uit `_signaalmeldingen` de opbouw van de `Melding` in een helper en roep die twee keer aan; de `onderscheid`-sleutel van de nul-bewaking blijft `{"klasse": label}`, anders verschuiven bestaande melding-ID's:

```python
def _signaalmeldingen(
    run: CheckRun,
    run_datum: date,
    scope: str,
    gebruikte_ids: set[str],
) -> list[Melding]:
    """Een systemische waarschuwing per datasetsignaal.

    Geen gebrek aan een object maar een signaal over de export: geen object-URI, geen
    plek op de kaart, en systemisch, zodat het de GeoPackage-status niet raakt (BO-29).
    Zonder gebied, net als een nulmetingbevinding die nergens op uitkwam: het is aan
    geen enkel studiegebied toe te wijzen. Twee soorten: een klasse of rol op nul waar
    een check op leunt (issue #22) en de herstelde fantoomkoppeling naar hulpstukken
    (issue #60).
    """
    meldingen = [
        _signaalmelding(
            run, run_datum, scope, gebruikte_ids, CHECK_NULKLASSE,
            {"klasse": signaal.label}, signaal.label, signaal.boodschap, "0",
        )
        for signaal in klassen_op_nul(run)
    ]
    herstel = koppelingsherstel(run)
    if herstel is not None:
        meldingen.append(
            _signaalmelding(
                run, run_datum, scope, gebruikte_ids, CHECK_HULPSTUKKOPPELING,
                {"signaal": "hulpstukkoppeling"}, "hulpstukkoppeling", herstel.boodschap,
                str(herstel.koppelingen),
            )
        )
    return meldingen


def _signaalmelding(
    run: CheckRun,
    run_datum: date,
    scope: str,
    gebruikte_ids: set[str],
    check_id: str,
    onderscheid: dict[str, str],
    label: str,
    boodschap: str,
    waarde: str,
) -> Melding:
    """Eén datasetsignaal als melding; registreert zijn ID in `gebruikte_ids`."""
    kenmerk = _uniek_id(check_id, "", "", onderscheid, label, gebruikte_ids)
    gebruikte_ids.add(kenmerk)
    return Melding(
        melding_id=kenmerk,
        check_id=check_id,
        categorie=categorie_van(check_id),
        bron=BRON_DATASET,
        ernst=Severity.WARNING.value,
        dimensie=Dimension.COMPLETENESS.value,
        object_uri="",
        object_id="",
        object_label=label,
        object2_uri="",
        object2_id="",
        object2_label="",
        boodschap=boodschap,
        waarde=waarde,
        drempel="",
        typering_betrouwbaar=True,
        cluster_id="",
        scope=scope,
        gebied="",
        prioriteit=3,
        systemisch=True,
        foutlocatie=None,
        run_datum=run_datum.isoformat(),
        dataset=run.dataset.source.name,
    )
```

Neem de veldwaarden letterlijk over uit de bestaande `_signaalmeldingen` (controleer `prioriteit`, `typering_betrouwbaar` en de overige velden tegen de huidige code; de tekst hierboven is daarvan afgeleid, de bestaande code wint bij een verschil).

3. `src/nlriochecker/uitvoer/bevindingen.py`, in `_omvang_section` direct ná het `if op_nul:`-blok en vóór `return regels`:

```python
    herstel = koppelingsherstel(run)
    if herstel is not None:
        regels += [
            "",
            f"> **Herstelde hulpstukkoppelingen:** {herstel.boodschap} Het signaal staat als "
            "systemische waarschuwing in de meldingenstroom.",
        ]
```

Importeer `koppelingsherstel` uit `nlriochecker.uitvoer.omvang` naast `klassen_op_nul`.

- [ ] **Step 6: Draai de tests en zie ze slagen; hele suite**

Run: `uv run pytest tests/test_dataset.py tests/test_uitvoer_klassentelling.py tests/test_uitvoer_melding.py tests/test_ttl_fixtures.py -q`
Expected: PASS. Daarna `uv run pytest -q`. Grep ook `grep -rn 'SIG-nulklasse' tests docs src` — staat het ID ergens in een lijst van toegestane `check_id`-waarden of in een schema-test, voeg `SIG-hulpstukkoppeling` daar toe. Valt een test elders (bv. een telling van `bron == "dataset"`-meldingen op een fixture zonder fantomen), dan is dat een bug in je wijziging: zonder herstel mag er geen signaal bijkomen.

- [ ] **Step 7: Documentatie**

1. `docs/architectuur.md`, regel 22 (de bullet "De koppeling wijst naar de ORIENTATIE …"): voeg aan het einde toe: ` De BrutIS-export van De Wolden en Hoogeveen koppelt elk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een URI zonder type of aspect (1122 hulpstukken, 3024 koppelingen). De lader herstelt dat op naamstam -- alleen als het doel onbekend is én de stam een knoop met een Hulpstukorientatie is -- telt het in `GwswDataset.koppelingsherstel` en het rapport meldt het als datasetsignaal `SIG-hulpstukkoppeling` (issue #60).`
2. `docs/architectuur.md`, de SIG-bullet (regel 56-62): vervang `maakt één systemische waarschuwing per klasse of rol waar een check op leunt maar die nul keer voorkomt (issue #22).` door `maakt één systemische waarschuwing per klasse of rol waar een check op leunt maar die nul keer voorkomt (`SIG-nulklasse`, issue #22), en één voor de herstelde fantoomkoppeling naar hulpstukken (`SIG-hulpstukkoppeling`, `uitvoer/omvang.koppelingsherstel`, issue #60).`
3. `docs/json-schema.md`, de alinea onder `### Datasetsignalen`: vervang `Nu is er één soort, de nul-bewaking van issue #22: … hun `ernst` altijd `W`.` door `Er zijn twee soorten: de nul-bewaking van issue #22 (een klasse of rol waar een check op leunt maar die nul keer voorkomt; `check_id` `SIG-nulklasse`, `waarde` `"0"`) en het koppelingsherstel van issue #60 (de lader heeft `hasConnection`-doelen `<hulpstuk>_put` op naamstam naar het hulpstuk herleid; `check_id` `SIG-hulpstukkoppeling`, `waarde` het aantal herstelde koppelingen). Hun `dimensie` is `Compleetheid`, hun `ernst` altijd `W`.` Laat de rest van de sectie staan.

- [ ] **Step 8: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen.

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/dataset_fantoomkoppeling.ttl \
  src/nlriochecker/dataset.py src/nlriochecker/uitvoer/omvang.py src/nlriochecker/uitvoer/melding.py \
  src/nlriochecker/uitvoer/bevindingen.py tests/test_dataset.py tests/test_uitvoer_klassentelling.py \
  docs/architectuur.md docs/json-schema.md
git status --short
git commit -m "Lader: herstel de fantoomkoppeling van leidingeinden naar hulpstukken en meld het als datasetsignaal (issue #60)"
```

Voeg gewijzigde testbestanden buiten deze lijst (uit Step 6) toe vóór de commit. Geen planbestanden, geen `uitvoer/`.

---

### Task 2: TOP-022 en TOP-023 — het aantal aansluitingen van een hulpstuk tegen zijn GWSW-functie

**Files:**
- Modify: `src/nlriochecker/ontologie.py` (nieuwe `functie_van_klasse`), `src/nlriochecker/dataset.py` (`WORTEL_HULPSTUK`, veld `functie_per_klasse`, `_klassefuncties`, `load_dataset`)
- Modify: `src/nlriochecker/checkconfig.py:26-67` (`ClassRoots.hulpstuk`), `src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml` (`[klassen] hulpstuk`)
- Modify: `src/nlriochecker/checks/selectie.py` (`hulpstukken()`, `_ROLLEN`), `tests/test_checks_selectie.py` (`ROLLENSET_AANTALLEN`)
- Modify: `src/nlriochecker/checks/topologie.py` (onderaan: telling + twee checks)
- Modify: `scripts/maak_ttl_fixtures.py` (`selectie_rollen.ttl` krijgt een T-stuk; twee nieuwe fixtures), regenerate `tests/fixtures/ttl/selectie_rollen.ttl`, `tests/fixtures/ttl/top022_hulpstuk_te_weinig.ttl`, `tests/fixtures/ttl/top023_hulpstuk_te_veel.ttl`
- Modify: `tests/test_checks_topologie.py`, `tests/test_dataset.py`, `tests/test_ontologie.py`
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md` (twee rijen na TOP-021; addendum), regenerate `docs/dekkingsmatrix.md`; `docs/beslislog.md` (BO-46); `CHANGELOG.md`

**Interfaces:**
- Consumes: `HULPSTUK_KLASSEN`, `hulpstuk()` uit Task 1; `_afsluiting`, `_short`, `_uri` in `dataset.py`; `GraafIndex.objects/value`; `OWL`, `RDFS`, `GWSW` in `ontologie.py`; `CheckContext.cached`; `dataset.resolve_network_node(uri, wortels)`; `dataset.beheerobjecttype(uri)`; `getal` uit `nlriochecker.taal`.
- Produces: `ontologie.functie_van_klasse(graph, klasse: URIRef) -> str | None` (korte functienaam); `GwswDataset.functie_per_klasse: dict[str, str]` (sleutel: volledige klasse-URI, waarde: korte functienaam; overgeerfd naar subklassen zonder eigen restrictie); `ClassRoots.hulpstuk: list[str]`; `selectie.hulpstukken(context) -> list[Node]`; `topologie.AANTAL_PER_FUNCTIE`; `REGISTRY["TOP-022"]` (`HulpstukMetTeWeinigAansluitingen`) en `REGISTRY["TOP-023"]` (`HulpstukMetTeVeelAansluitingen`); bevindingsdetails `verwacht`, `aangesloten`, `losse_einden`, `functie`, `buren`, `strengen`.

- [ ] **Step 1: Fixtures (generator)**

In `scripts/maak_ttl_fixtures.py`:

1. In `FIXTURES["selectie_rollen.ttl"]`: zet `HULPSTUK_KLASSEN +` vóór de bestaande eerste string (`"# Alleen deze fixture heeft de bergbezinkleiding nodig; …"`), en voeg ná de regel `+ put("Bbb1", … ).replace(…)` toe:

```python
    # Een T-stuk is een knoop (Hulpstukorientatie is een Knooppunt) maar geen put en
    # geen netwerkknoop; TOP-022/TOP-023 tellen er de leidingen op (issue #60).
    + hulpstuk("Tstuk1", "Tstuk1", 1350.0, 2000.0)
```

Werk het commentaar `zodat de fixture alle veertien rollen dekt` bij naar `alle vijftien rollen`.

2. Direct ná `FIXTURES["dataset_fantoomkoppeling.ttl"] = (...)`:

```python
# TOP-022: T-stuk T1 heeft twee richtingen waar zijn functie er drie voorschrijft. De
# rest is in orde en mag niet melden: T3 heeft drie richtingen waarvan een dubbel gelegd
# (twee strengen naar put D, hartlijnen 5 cm uit elkaar), kruisstuk K1 heeft er vier
# en afsluitstuk A1 draagt geen functie met een aantal en valt buiten de toets.
FIXTURES["top022_hulpstuk_te_weinig.ttl"] = (
    "T-stuk T1 verbindt twee leidingen waar zijn GWSW-functie er drie voorschrijft; T3 "
    "(drie richtingen, een dubbel gelegd), kruisstuk K1 (vier) en afsluitstuk A1 zijn in "
    "orde (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1100.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "PutB")
    + put("PutC", "C", 1000.0, 2100.0)
    + put("PutD", "D", 1100.0, 2100.0)
    + put("PutE", "E", 1050.0, 2150.0)
    + hulpstuk("T3", "T3", 1050.0, 2100.0)
    + leiding("L3", "3", [(1000.0, 2100.0), (1050.0, 2100.0)], "PutC", "T3")
    + leiding("L4a", "4a", [(1050.0, 2100.0), (1100.0, 2100.0)], "T3", "PutD")
    + leiding("L4b", "4b", [(1050.0, 2100.0), (1075.0, 2100.05), (1100.0, 2100.0)], "T3", "PutD")
    + leiding("L5", "5", [(1050.0, 2100.0), (1050.0, 2150.0)], "T3", "PutE")
    + put("PutF", "F", 1000.0, 2200.0)
    + put("PutG", "G", 1100.0, 2200.0)
    + put("PutH", "H", 1050.0, 2250.0)
    + put("PutI", "I", 1050.0, 2170.0)
    + hulpstuk("K1", "K1", 1050.0, 2200.0, klasse="Kruisstuk")
    + leiding("L6", "6", [(1000.0, 2200.0), (1050.0, 2200.0)], "PutF", "K1")
    + leiding("L7", "7", [(1050.0, 2200.0), (1100.0, 2200.0)], "K1", "PutG")
    + leiding("L8", "8", [(1050.0, 2200.0), (1050.0, 2250.0)], "K1", "PutH")
    + leiding("L9", "9", [(1050.0, 2170.0), (1050.0, 2200.0)], "PutI", "K1")
    + put("PutJ", "J", 1150.0, 2000.0)
    + hulpstuk("A1", "A1", 1200.0, 2000.0, klasse="Afsluitstuk")
    + leiding("L10", "10", [(1150.0, 2000.0), (1200.0, 2000.0)], "PutJ", "A1"),
)

# TOP-023: T-stuk T2 verbindt vier verschillende knopen; voor vier bestaat Kruisstuk.
FIXTURES["top023_hulpstuk_te_veel.ttl"] = (
    "T-stuk T2 verbindt vier leidingen naar vier verschillende knopen waar zijn "
    "GWSW-functie er drie voorschrijft (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1100.0, 2000.0)
    + put("PutC", "C", 1050.0, 2050.0)
    + put("PutD", "D", 1050.0, 1950.0)
    + hulpstuk("T2", "T2", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T2")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T2", "PutB")
    + leiding("L3", "3", [(1050.0, 2000.0), (1050.0, 2050.0)], "T2", "PutC")
    + leiding("L4", "4", [(1050.0, 1950.0), (1050.0, 2000.0)], "PutD", "T2"),
)
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. `git status --short`: `selectie_rollen.ttl` gewijzigd, de twee nieuwe fixtures nieuw, verder niets.

- [ ] **Step 2: Schrijf de falende tests**

1. `tests/test_ontologie.py`, onderaan. Het bestand laadt de echte ontologie alleen als `data/` er is; volg de bestaande `skipif`-conventie van dat bestand (zoek `ONTOLOGIE_TTL` en de fixture die er een `Graph` van maakt; gebruik dezelfde):

```python
@pytest.mark.skipif(not ONTOLOGIE_TTL.exists(), reason="de GWSW-ontologie staat niet in data/")
@pytest.mark.parametrize(
    ("klasse", "verwacht"),
    [
        ("Mof", "VerbindenVanTweeLeidingen"),
        ("T_stuk", "VerbindenVanDrieLeidingen"),
        ("Y_stuk", "VerbindenVanDrieLeidingen"),
        ("Kruisstuk", "VerbindenVanVierLeidingen"),
        ("Afsluitstuk", "AfsluitenVanLeidingen"),
        # Zijn definitie noemt drie leidingen, het model niet.
        ("Tubelure", None),
    ],
)
def test_functie_van_klasse_uit_de_echte_ontologie(klasse: str, verwacht: str | None) -> None:
    from nlriochecker.ontologie import functie_van_klasse

    graaf = Graph().parse(ONTOLOGIE_TTL)
    assert functie_van_klasse(graaf, URIRef(GWSW + klasse)) == verwacht
```

Bestaat er in dat bestand al een module-scoped fixture met de geparste echte ontologie, gebruik die in plaats van opnieuw te parsen (de totaal-ontologie parsen met rdflib duurt tientallen seconden; één keer per module is genoeg).

2. `tests/test_dataset.py`, onderaan:

```python
def test_functie_per_klasse_komt_uit_de_restricties() -> None:
    dataset = load_dataset(TTL_DIR / "top022_hulpstuk_te_weinig.ttl")

    assert dataset.functie_per_klasse[f"{GWSW}T_stuk"] == "VerbindenVanDrieLeidingen"
    assert dataset.functie_per_klasse[f"{GWSW}Kruisstuk"] == "VerbindenVanVierLeidingen"
    assert dataset.functie_per_klasse[f"{GWSW}Afsluitstuk"] == "AfsluitenVanLeidingen"
    assert f"{GWSW}Verbindingsstuk" not in dataset.functie_per_klasse
```

3. `tests/test_checks_selectie.py`: `"hulpstukken": 1,` in `ROLLENSET_AANTALLEN` (alfabetisch of achteraan; de test sorteert zelf). Werk het commentaar `Alle veertien rollen` bij naar vijftien.

4. `tests/test_checks_topologie.py`: `TOP_IDS` uitbreiden met `"TOP-022", "TOP-023"`; twee rijen in de parametrisatie van `test_defect_wordt_gevonden`:

```python
        ("top022_hulpstuk_te_weinig.ttl", "TOP-022", "T1"),
        ("top023_hulpstuk_te_veel.ttl", "TOP-023", "T2"),
```

en onderaan:

```python
def test_top022_telt_richtingen_en_niet_strengen() -> None:
    """T3 heeft vier strengen maar drie richtingen (een dubbel gelegd) en zwijgt; T1 meldt."""
    pad = TTL_DIR / "top022_hulpstuk_te_weinig.ttl"
    bevindingen = _bevindingen(pad, "TOP-022")

    assert _labels(bevindingen) == ["T1"]
    assert bevindingen[0].details["verwacht"] == 3
    assert bevindingen[0].details["aangesloten"] == 2
    assert bevindingen[0].details["functie"] == "VerbindenVanDrieLeidingen"
    assert bevindingen[0].details["strengen"] == "1, 2"
    assert _bevindingen(pad, "TOP-023") == []


def test_top023_meldt_een_t_stuk_met_vier_richtingen() -> None:
    pad = TTL_DIR / "top023_hulpstuk_te_veel.ttl"
    bevindingen = _bevindingen(pad, "TOP-023")

    assert _labels(bevindingen) == ["T2"]
    assert bevindingen[0].details["aangesloten"] == 4
    assert _bevindingen(pad, "TOP-022") == []


def test_hulpstukchecks_verantwoorden_de_klassen_zonder_aantal() -> None:
    """Afsluitstuk A1 draagt geen functie met een aantal: buiten de toets, wel geteld."""
    dataset = load_dataset(TTL_DIR / "top022_hulpstuk_te_weinig.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["TOP-022"]).outcomes[0]

    assert outcome.examined == 3
    assert any("1 Afsluitstuk" in note for note in outcome.notes), outcome.notes
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checks_topologie.py tests/test_dataset.py tests/test_checks_selectie.py tests/test_ontologie.py -k "top022 or top023 or hulpstuk or functie" -v`
Expected: FAIL (`ImportError`/`KeyError: 'TOP-022'`/`AttributeError: functie_per_klasse`).

- [ ] **Step 4: Ontologie en lader**

1. `src/nlriochecker/ontologie.py`, ná `verwachte_property`:

```python
def functie_van_klasse(graph: Graph | GraafIndex, klasse: URIRef) -> str | None:
    """De functiewaarde die de ontologie aan een klasse bindt, als korte naam, of None.

    Het GWSW zegt wat een hulpstuk doet via een `owl:Restriction` op `gwsw:functie`
    met `owl:hasValue` (`T_stuk` → `VerbindenVanDrieLeidingen`, `Kruisstuk` →
    `VerbindenVanVierLeidingen`). TOP-022 en TOP-023 lezen daar het verwachte aantal
    leidingen uit (issue #60). Alleen de restricties direct op de klasse; het
    overerven naar subklassen doet `dataset._klassefuncties`.
    """
    functie = URIRef(GWSW + "functie")
    for restrictie in graph.objects(klasse, RDFS.subClassOf):
        if graph.value(restrictie, OWL.onProperty) != functie:
            continue
        waarde = graph.value(restrictie, OWL.hasValue)
        if waarde is not None:
            return str(waarde).removeprefix(GWSW)
    return None
```

2. `src/nlriochecker/dataset.py`: constante `WORTEL_HULPSTUK = "Hulpstuk"` bij de andere wortels; op `GwswDataset` ná `kenmerk_property`:

```python
    # Per hulpstukklasse (volledige URI) de functiewaarde uit de `gwsw:functie`-restrictie
    # van de ontologie, overgeerfd naar subklassen zonder eigen restrictie. TOP-022 en
    # TOP-023 lezen er het verwachte aantal leidingen uit (issue #60). Net als
    # `kenmerk_property` een klein afgeleid woordenboek; leeg zonder klassenkennis.
    functie_per_klasse: dict[str, str] = field(default_factory=dict)
```

In `load_dataset`, ná `kenmerk_property = _kenmerk_properties(restrictiebron, subclasses)`: `functie_per_klasse = _klassefuncties(restrictiebron, subclasses)`, en `functie_per_klasse=functie_per_klasse,` in de constructor. Ná `_kenmerk_properties`:

```python
def _klassefuncties(graph: GraafIndex, subclasses: dict[str, frozenset[str]]) -> dict[str, str]:
    """Per hulpstukklasse de functiewaarde uit de ontologie, overgeerfd naar subklassen.

    Loopt over de afsluiting van `Hulpstuk`; een klasse met een eigen restrictie wint
    van wat zij van een bovenklasse zou erven. Sleutel is de volledige URI, zodat een
    knoop er met zijn `types` direct in kan kijken.
    """
    from nlriochecker.ontologie import functie_van_klasse

    eigen: dict[str, str] = {}
    for uri in _afsluiting(subclasses, WORTEL_HULPSTUK):
        functie = functie_van_klasse(graph, URIRef(uri))
        if functie is not None:
            eigen[uri] = functie
    gevonden = dict(eigen)
    for uri, functie in sorted(eigen.items()):
        for sub in _afsluiting(subclasses, _short(uri)):
            gevonden.setdefault(sub, functie)
    return gevonden
```

- [ ] **Step 5: Rol, selectie en checks**

1. `src/nlriochecker/checkconfig.py`, in `ClassRoots` ná `mechanisch`:

```python
    # TOP-022 en TOP-023: hulpstukken (T-stuk, kruisstuk, mof, afsluitstuk, ...). Een
    # hulpstuk is een knoop maar geen put; het verwachte aantal leidingen komt uit de
    # functierestrictie in de ontologie, niet uit deze lijst.
    hulpstuk: list[str] = Field(default_factory=list)
```

2. `src/nlriochecker/checks.toml` én `configs/dewoldenhoogeveen.toml`, in `[klassen]` direct ná de regel `mechanisch = [...]`, in beide bestanden letterlijk:

```toml
# TOP-022 en TOP-023: de hulpstukken. Hulpstuk is de ontologische wortel van T_stuk,
# Y_stuk, Kruisstuk, Mof, Afsluitstuk, Ontstoppingsstuk, Tubelure en de rest; welke
# daarvan een aantal leidingen voorschrijft leest de check uit de ontologie
# (functie hasValue VerbindenVanTwee/Drie/VierLeidingen), niet uit deze lijst.
hulpstuk = ["Hulpstuk"]
```

3. `src/nlriochecker/checks/selectie.py`, ná `functieloze_knopen`:

```python
def hulpstukken(context: CheckContext) -> list[Node]:
    """De hulpstukken: `gwsw:Hulpstuk` en haar subklassen (T-stuk, kruisstuk, mof, ...).

    Een hulpstuk is een knoop -- zijn `Hulpstukorientatie` is een `Knooppunt` -- maar
    geen put en geen netwerkknoop. TOP-022 en TOP-023 tellen er de leidingen op.
    """
    return _knopen(context, "sel:hulpstukken", context.config.klassen.hulpstuk)
```

en `"hulpstukken": hulpstukken,` in `_ROLLEN` ná `"functieloze_knopen"`.

4. `src/nlriochecker/checks/topologie.py`, onderaan (ná `_alle_geometrieen`). Importeer `Counter` en `defaultdict` uit `collections`, `hulpstukken` uit `nlriochecker.checks.selectie`, `getal` uit `nlriochecker.taal`:

```python
# Het aantal leidingen dat een functiewaarde van een hulpstuk voorschrijft. De klasse
# → functie-koppeling komt uit de ontologie (`GwswDataset.functie_per_klasse`); dit
# vertaalt alleen het woord naar het getal. Functiewaarden zonder aantal
# (AfsluitenVanLeidingen, VerbindenVanLeidingenInEenHoek, ...) staan er bewust niet in.
AANTAL_PER_FUNCTIE: dict[str, int] = {
    "VerbindenVanTweeLeidingen": 2,
    "VerbindenVanDrieLeidingen": 3,
    "VerbindenVanVierLeidingen": 4,
}


@dataclass(frozen=True)
class _Hulpstukaansluiting:
    """Wat er op een hulpstuk met telbare functie aangesloten is."""

    node: Node
    functie: str
    verwacht: int
    # De verschillende knopen aan de andere kant, naar de put herleid; twee strengen
    # tussen dezelfde twee knopen zijn een richting.
    buren: tuple[str, ...]
    # Strengen waarvan het andere eind aan niets hangt; elk telt als eigen richting.
    losse_einden: int
    strengen: tuple[str, ...]

    @property
    def richtingen(self) -> int:
        """Het aantal richtingen dat dit hulpstuk werkelijk verbindt."""
        return len(self.buren) + self.losse_einden


@dataclass(frozen=True)
class _Hulpstuktelling:
    """De telbare hulpstukken plus, per klasse, hoeveel er buiten de toets vielen."""

    telbaar: tuple[_Hulpstukaansluiting, ...]
    buiten_per_klasse: dict[str, int]


def _hulpstuktelling(context: CheckContext) -> _Hulpstuktelling:
    """De aansluitingen per hulpstuk; een keer per context, gedeeld door TOP-022 en TOP-023."""
    return context.cached("hulpstukken:aansluitingen", lambda: _bouw_hulpstuktelling(context))


def _bouw_hulpstuktelling(context: CheckContext) -> _Hulpstuktelling:
    """Telt per hulpstuk de richtingen: verschillende buurknopen plus losse einden.

    Rechtstreeks op `start_node`/`end_node` en niet via `aansluitingen()`: die index
    herleidt elk eind naar een netwerkknoop, en een hulpstuk is er geen.
    """
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    alle = hulpstukken(context)
    uris = {node.uri for node in alle}
    per_hulpstuk: defaultdict[str, list[tuple[Conduit, str | None]]] = defaultdict(list)
    for conduit in dataset.conduits.values():
        for eigen, ander in (
            (conduit.start_node, conduit.end_node),
            (conduit.end_node, conduit.start_node),
        ):
            # Een streng met beide einden aan hetzelfde hulpstuk telt niet als buur.
            if eigen in uris and ander != eigen:
                per_hulpstuk[eigen].append((conduit, ander))

    telbaar: list[_Hulpstukaansluiting] = []
    buiten: Counter[str] = Counter()
    for node in sorted(alle, key=lambda knoop: knoop.uri):
        gevonden = _functie_met_aantal(dataset, node)
        if gevonden is None:
            buiten[dataset.beheerobjecttype(node.uri) or "(zonder type)"] += 1
            continue
        functie, verwacht = gevonden
        buren: set[str] = set()
        los = 0
        labels: list[str] = []
        for conduit, ander in per_hulpstuk.get(node.uri, []):
            labels.append(conduit.label or conduit.uri)
            if ander is None:
                los += 1
            else:
                buren.add(dataset.resolve_network_node(ander, wortels) or ander)
        telbaar.append(
            _Hulpstukaansluiting(
                node, functie, verwacht, tuple(sorted(buren)), los, tuple(sorted(labels))
            )
        )
    return _Hulpstuktelling(tuple(telbaar), dict(buiten))


def _functie_met_aantal(dataset, node: Node) -> tuple[str, int] | None:
    """De functiewaarde van dit hulpstuk en het aantal leidingen dat zij voorschrijft."""
    for soort in sorted(node.types):
        functie = dataset.functie_per_klasse.get(soort)
        if functie in AANTAL_PER_FUNCTIE:
            return functie, AANTAL_PER_FUNCTIE[functie]
    return None


class _HulpstukAansluitingen(Check):
    """Gedeelde basis voor TOP-022 (te weinig richtingen) en TOP-023 (te veel)."""

    te_veel: bool

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt per hulpstuk het aantal richtingen met de GWSW-functie."""
        dataset = context.dataset
        for aansluiting in _hulpstuktelling(context).telbaar:
            if aansluiting.richtingen == aansluiting.verwacht:
                continue
            if (aansluiting.richtingen > aansluiting.verwacht) != self.te_veel:
                continue
            buren = ", ".join(
                (dataset.nodes[uri].label or uri) if uri in dataset.nodes else uri
                for uri in aansluiting.buren
            )
            los = (
                f", plus {getal(aansluiting.losse_einden, 'streng', 'strengen')} met een los eind"
                if aansluiting.losse_einden
                else ""
            )
            soort = dataset.beheerobjecttype(aansluiting.node.uri) or "Hulpstuk"
            yield self.finding(
                context,
                aansluiting.node.uri,
                aansluiting.node.label,
                f"{soort} verbindt {getal(aansluiting.richtingen, 'richting', 'richtingen')} "
                f"({buren or 'geen buurknoop'}{los}) waar de GWSW-functie "
                f"{aansluiting.functie} er {aansluiting.verwacht} voorschrijft.",
                verwacht=aansluiting.verwacht,
                aangesloten=aansluiting.richtingen,
                losse_einden=aansluiting.losse_einden,
                functie=aansluiting.functie,
                buren=buren,
                strengen=", ".join(aansluiting.strengen),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de hulpstukken waarvan de klasse geen aantal voorschrijft."""
        buiten = _hulpstuktelling(context).buiten_per_klasse
        if not buiten:
            return []
        delen = ", ".join(f"{aantal} {klasse}" for klasse, aantal in sorted(buiten.items()))
        return [
            f"{sum(buiten.values())} hulpstukken vallen buiten deze toets omdat hun klasse "
            f"geen functie met een aantal leidingen draagt ({delen}); een afsluitstuk met "
            "een leiding is precies goed."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal hulpstukken met een telbare functie."""
        return len(_hulpstuktelling(context).telbaar)


@register
class HulpstukMetTeWeinigAansluitingen(_HulpstukAansluitingen):
    """TOP-022: er ontbreekt een leiding, of het object is geen T-stuk."""

    id = "TOP-022"
    title = "Hulpstuk verbindt minder leidingen dan zijn GWSW-functie voorschrijft"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    te_veel = False


@register
class HulpstukMetTeVeelAansluitingen(_HulpstukAansluitingen):
    """TOP-023: waarschijnlijk de verkeerde klasse; voor vier bestaat Kruisstuk."""

    id = "TOP-023"
    title = "Hulpstuk verbindt meer leidingen dan zijn GWSW-functie voorschrijft"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    te_veel = True
```

Pas de imports bovenaan `topologie.py` aan (`Counter`, `defaultdict`, `hulpstukken`, `getal`; `dataclass` en `Node` staan er al). Typ `dataset` in `_functie_met_aantal` als `GwswDataset` als mypy erom vraagt (importeer hem dan uit `nlriochecker.dataset`).

- [ ] **Step 6: Draai de tests en zie ze slagen; hele suite**

Run: `uv run pytest tests/test_checks_topologie.py tests/test_dataset.py tests/test_checks_selectie.py tests/test_ontologie.py tests/test_checkconfig.py tests/test_ttl_fixtures.py tests/test_gwsw_vocabulaire.py -q`
Expected: PASS, op `test_checks_registry.py`/`test_dekkingsmatrix.py` na, die de registerregels van Step 7 nodig hebben. Daarna `uv run pytest -q`. Valt `test_gwsw_vocabulaire.py` op een naam (`Hulpstuk`, `VerbindenVanDrieLeidingen`): die namen bestaan in de ontologie; lees de foutmelding en kijk of de index (`data/gwsw-vocabulaire-index.json`) de naam kent -- pas nooit de test aan om een naam te ontwijken.

- [ ] **Step 7: Register, dekkingsmatrix, beslislog, CHANGELOG**

1. `data/checkregister-gwsw-nulmeting-v0_9.md`, ná de rij TOP-021:

```markdown
| TOP-022 | Hulpstuk verbindt minder leidingen dan zijn GWSW-functie voorschrijft. Het verwachte aantal volgt uit de `functie`-restrictie op de klasse in de ontologie (`VerbindenVanTweeLeidingen` 2 voor `Mof`, `VerbindenVanDrieLeidingen` 3 voor `T_stuk` en `Y_stuk`, `VerbindenVanVierLeidingen` 4 voor `Kruisstuk`); geteld naar verschillende knopen aan de andere kant, zodat een dubbel gelegde richting een keer telt. Klassen zonder aantal in hun functie (`Afsluitstuk`, `Ontstoppingsstuk`, `Tubelure`, `Bochtstuk`, `Verloopstuk`, `Overgangsstuk`) vallen erbuiten en worden in de toelichting geteld. De nulmeting kent geen kardinaliteit op `hasConnection` van een hulpstuk (issue #60) | F | Consistentie |
| TOP-023 | Hulpstuk verbindt meer leidingen dan zijn GWSW-functie voorschrijft; waarschijnlijk de verkeerde klasse gekozen (voor vier bestaat `Kruisstuk`). Zelfde telling als TOP-022 (issue #60) | W | Consistentie |
```

2. In `## Versiehistorie`, bovenaan een alinea:

```markdown
Versie 0.9, addendum (2026-08-24): TOP-022 (F) en TOP-023 (W), beide Consistentie, toegevoegd:
een hulpstuk verbindt minder respectievelijk meer leidingen dan de `functie`-restrictie op
zijn GWSW-klasse voorschrijft; het aantal komt uit de ontologie en niet uit de configuratie,
geteld naar buurknopen en niet naar strengen. Twee ID's en niet één met twee ernsten, want
elke check draagt hier precies één ernst. Tegelijk herstelt de lader de fantoomkoppeling van
de BrutIS-export (`<hulpstuk>_put`) en meldt dat als datasetsignaal; zonder dat herstel zag
de engine bij alle 1054 T-stukken van De Wolden en Hoogeveen nul leidingen. Zie
[#60](https://github.com/mcolee/nlriochecker/issues/60) en BO-46.

```

3. Regenereer: `uv run python scripts/dekkingsmatrix.py`; `git diff docs/dekkingsmatrix.md` toont twee nieuwe TOP-rijen en de TOP-telling 21 → 23.

4. `docs/beslislog.md`, aan het einde:

```markdown

### BO-46 De lader herstelt de fantoomkoppeling naar hulpstukken en meldt dat; TOP-022/TOP-023 tellen richtingen tegen de GWSW-functie

**Wat.** (1) Wijst geen enkel `hasConnection`-doel van een leidingeinde naar een bekende
orientatie, dan strip de lader de staart `_put` en neemt hij de stam als knoop -- alleen als
die stam een knoop met een `Hulpstukorientatie` is. Het aantal herstelde koppelingen en
hulpstukken staat op `GwswDataset.koppelingsherstel` en gaat als datasetsignaal
`SIG-hulpstukkoppeling` (W, systemisch, zonder object) de meldingenstroom in. (2) TOP-022 (F)
en TOP-023 (W) vergelijken per hulpstuk het aantal richtingen -- verschillende buurknopen plus
losse einden -- met het aantal dat de `gwsw:functie`-restrictie op zijn klasse voorschrijft
(`VerbindenVanTwee/Drie/VierLeidingen` → 2/3/4). De klasse→functie-koppeling komt uit de
ontologie (`GwswDataset.functie_per_klasse`, overgeerfd naar subklassen); alleen de vertaling
van woord naar getal staat in code. Uitgewerkt in issue #60.

**Waarom.** De BrutIS-export koppelt élk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een
URI die nergens een type of aspect draagt; de orientatie heet `<hulpstuk>_put<n>`. Gemeten:
1122 hulpstukken, 1122 fantoom-URI's, 3024 koppelingen, 3024 strengeinden zonder knoop, 859
strengen met beide einden los, 0 T-stukken met een herkende aansluiting. De nulmeting meldt
hetzelfde (`Knooppunt_Netwerk_conn` 1123×, `EindpuntLeiding_Knooppunt_card` 1846×,
`BeginpuntLeiding_Knooppunt_card` 1178×). Zonder herstel meet een T-stukcheck niets; met een
stil herstel zou het rapport het gebrek in de aanlevering verzwijgen. Richtingen in plaats van
strengen: in Alteveer ligt elke vacuümrichting dubbel (108 knoopparen met meer dan een streng
ertussen, 266 strengen), en per streng geteld zouden 17 hulpstukken ten onrechte melden.

**Twee ID's, niet een.** Het issue nam een ID met F voor te weinig en W voor te veel aan. De
engine en het register kennen per check precies een ernst (`Check.severity`;
`test_ernst_en_dimensie_volgen_het_register`). Daarom TOP-022 voor te weinig (F: er ontbreekt
een leiding, of het is geen T-stuk) en TOP-023 voor te veel (W: waarschijnlijk de verkeerde
klasse).

**Alternatieven.** Ruimer herstellen op naam (verworpen: gokken in een kritiek pad). Het
verwachte aantal in `checks.toml` (verworpen: het staat in de ontologie en zou een tweede
waarheid worden). Een losse streng zonder eind niet meetellen (verworpen: die leiding hangt
wel degelijk aan het hulpstuk; dat haar andere eind los is, is een TOP-002/003-zaak).
```

5. `CHANGELOG.md`, onder `## [Unreleased]`:
   - onder `### Gerepareerd`, bovenaan:

```markdown
- **De fantoomkoppeling naar hulpstukken wordt hersteld en gemeld** (issue #60). De
  BrutIS-export koppelt elk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een URI
  die niet bestaat, zodat de engine bij alle 1054 T-stukken van De Wolden en Hoogeveen
  nul leidingen zag en 3024 strengeinden aan niets hingen. De lader herleidt zo'n doel
  op naamstam naar het hulpstuk -- alleen als het doel onbekend is én de stam een knoop
  met een Hulpstukorientatie is -- en meldt het aantal als datasetsignaal
  `SIG-hulpstukkoppeling` (W, systemisch). Dit raakt elke netwerkcheck; het gemeten
  verschil per check staat in BO-46. Zie BO-46.
```

   - onder `### Toegevoegd`, bovenaan:

```markdown
- **TOP-022 en TOP-023: hulpstuk met een ander aantal aansluitingen dan zijn
  GWSW-functie voorschrijft** (issue #60). Het verwachte aantal komt uit de
  `functie`-restrictie op de klasse in de ontologie (`Mof` 2, `T_stuk`/`Y_stuk` 3,
  `Kruisstuk` 4); geteld naar verschillende buurknopen, zodat een dubbel gelegde
  richting een keer telt. TOP-022 (F) meldt te weinig, TOP-023 (W) te veel; klassen
  zonder aantal in hun functie (afsluitstuk, ontstoppingsstuk, tubelure) vallen buiten
  de toets en staan geteld in de toelichting. Nieuwe rol `[klassen] hulpstuk`. Op De
  Wolden en Hoogeveen: TOP-022 224 en TOP-023 37 op 1054 T-stukken (Task 3 meet het).
  Zie BO-46.
```

- [ ] **Step 8: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen.

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/selectie_rollen.ttl \
  tests/fixtures/ttl/top022_hulpstuk_te_weinig.ttl tests/fixtures/ttl/top023_hulpstuk_te_veel.ttl \
  src/nlriochecker/ontologie.py src/nlriochecker/dataset.py src/nlriochecker/checkconfig.py \
  src/nlriochecker/checks.toml configs/dewoldenhoogeveen.toml src/nlriochecker/checks/selectie.py \
  src/nlriochecker/checks/topologie.py tests/test_checks_topologie.py tests/test_dataset.py \
  tests/test_ontologie.py tests/test_checks_selectie.py \
  data/checkregister-gwsw-nulmeting-v0_9.md docs/dekkingsmatrix.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "TOP-022/TOP-023: hulpstuk met minder of meer aansluitingen dan zijn GWSW-functie voorschrijft (issue #60)"
```

---

### Task 3: Effect op De Wolden meten en vastleggen

**Files:**
- Read: de laatste volledige run vóór dit issue: `uitvoer/issue61/bevindingen.csv` als die bestaat, anders `uitvoer/issue63/bevindingen.csv`, anders `uitvoer/volledig_24082026/bevindingen.csv`
- Create (niet committen): `uitvoer/issue60/`
- Modify: `docs/beslislog.md` (BO-46: alinea "Gemeten uitkomst"), `CHANGELOG.md` (getallen)

- [ ] **Step 1: Meet de koppelingen op de geladen dataset**

```bash
uv run python - <<'EOF'
from pathlib import Path
from nlriochecker.cache import laad_met_cache
dataset, uitslag = laad_met_cache(
    Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
    [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")],
)
print("cache:", uitslag.bron, "herstel:", dataset.koppelingsherstel)
los_begin = sum(1 for c in dataset.conduits.values() if c.start_node is None)
los_eind = sum(1 for c in dataset.conduits.values() if c.end_node is None)
beide = sum(1 for c in dataset.conduits.values() if c.start_node is None and c.end_node is None)
print("strengeinden zonder knoop:", los_begin + los_eind, "(begin", los_begin, "eind", los_eind, ") beide los:", beide)
tstuk = f"http://data.gwsw.nl/1.6/totaal/T_stuk"
t = {u for u, n in dataset.nodes.items() if tstuk in n.types}
aangesloten = {c.start_node for c in dataset.conduits.values()} | {c.end_node for c in dataset.conduits.values()}
print("T-stukken:", len(t), "met minstens een aansluiting:", len(t & aangesloten))
print("functie T_stuk:", dataset.functie_per_klasse.get(tstuk))
EOF
```

Verwacht: `Koppelingsherstel(koppelingen=3024, hulpstukken=1122)`, strengeinden zonder knoop 3024 → **0** (of alleen de einden die géén `hasConnection` hebben; het issue meldt er 0), beide los 859 → **0**, T-stukken met aansluiting 0 → **1054**. De cache is door de wijziging aan `dataset.py` vanzelf ongeldig (`uitslag.bron == "bestand"` bij de eerste keer).

- [ ] **Step 2: Draai de volledige toets**

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
  --output uitvoer/issue60
```

- [ ] **Step 3: Vergelijk per check**

```bash
uv run python - <<'EOF'
import pandas as pd, pathlib
voor = next(p for p in ["uitvoer/issue61/bevindingen.csv", "uitvoer/issue63/bevindingen.csv", "uitvoer/volledig_24082026/bevindingen.csv"] if pathlib.Path(p).exists())
print("voor:", voor)
a = pd.read_csv(voor, sep=";"); b = pd.read_csv("uitvoer/issue60/bevindingen.csv", sep=";")
ta, tb = a.Check.value_counts(), b.Check.value_counts()
alle = sorted(set(ta.index) | set(tb.index))
print(f"{'check':22} {'voor':>7} {'na':>7} {'delta':>7}")
for c in alle:
    va, vb = int(ta.get(c, 0)), int(tb.get(c, 0))
    if va != vb: print(f"{c:22} {va:7d} {vb:7d} {vb - va:+7d}")
print("SIG:", b[b.Check.str.startswith("SIG")][["Check", "Waarde", "Boodschap"]].to_string())
t22 = b[b.Check == "TOP-022"]; t23 = b[b.Check == "TOP-023"]
print("TOP-022:", len(t22), "TOP-023:", len(t23))
EOF
```

Lees eerst de kolomnamen als `Check`/`Waarde`/`Boodschap` niet kloppen. Verwacht: TOP-022 **224** (94 met één en 130 met twee richtingen) en TOP-023 **37** (36 met vier, 1 met vijf); een `SIG-hulpstukkoppeling` met waarde 3024. Haal de verdeling naar `aangesloten` uit de boodschap of de CSV-kolommen en zet hem naast de tabel uit het issue (1: 94, 2: 130, 3: 793, 4: 36, 5: 1). **Elke andere check die verschuift** (TOP-002, TOP-003, NET-*, ADM-*, RVZ-*, …) krijgt een regel met een verklaring: 2165 strengen kregen hun knopen terug. Een sprong die je niet kunt verklaren is zelf een bevinding -- schrijf hem op als open punt, leg hem niet weg. Wijkt 224/37 af, meld het getal en de richting.

- [ ] **Step 4: Leg vast en commit**

Aan BO-46 in `docs/beslislog.md` een slotalinea:

```markdown

**Gemeten uitkomst (2026-08-24).** Na het herstel: <K> koppelingen naar <H> hulpstukken hersteld,
strengeinden zonder knoop 3024 → <L>, strengen met beide einden los 859 → <B>, T-stukken met
minstens een aansluiting 0 → <T>. TOP-022 meldt <N22> T-stukken (<n1> met een richting, <n2> met
twee), TOP-023 <N23> (<n4> met vier, <n5> met vijf); <buiten> hulpstukken vielen buiten de toets
(<per klasse>). Verschuivingen in de andere checks door het herstel: <per check: voor → na, met
verklaring>. Onverklaard: <geen, of de lijst>.
```

Corrigeer de getallen in de twee CHANGELOG-regels van dit issue en haal `(Task 3 meet het)` weg. Dan:

```bash
git add docs/beslislog.md CHANGELOG.md
git commit -m "BO-46: gemeten effect van het koppelingsherstel en TOP-022/TOP-023 op De Wolden (issue #60)"
```

Zet de vergelijkingstabel per check en de tellingen in het rapportbestand van deze taak.
