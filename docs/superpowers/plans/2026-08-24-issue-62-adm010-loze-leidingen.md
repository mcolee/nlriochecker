# Issue #62: ADM-010/ADM-011 — loze leidingen die in het actieve netwerk hangen — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Twee nieuwe checks groeperen de loze leidingen (`gwsw:LozeLeiding` en subklassen) tot ketens en melden per loze streng hoe de keten aan actief riool hangt: **ADM-010** (F) voor *doorgaand*, *aanvoer* en *afvoer*, **ADM-011** (W) voor een *losgekoppelde* keten. De keten staat in `cluster_id`; het aantal actieve strengen bovenstrooms staat als detail.

**Architecture:** De checks komen in `src/nlriochecker/checks/administratief.py`. Een gedeelde, gecachte ketenbouwer leest álle leidingen (`selectie.leidingen`), pakt de loze eruit (nieuwe rol `[klassen] loze_leiding = ["LozeLeiding"]`, `selectie.lozeleidingen`), verbindt loze strengen die een knoop delen tot ketens, en bepaalt per keten in de administratieve richting (`start_node` → `end_node`, herleid naar de netwerkknoop met terugval op de rauwe URI zodat ook een hulpstuk als knoop telt) welke actieve strengen inkomen en uitgaan, plus het transitieve aantal actieve strengen bovenstrooms.

**Tech Stack:** Python 3.12, pytest. Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #62 (`gh issue list --json number,body --search 62`).

## Global Constraints

- **Ruling van de regisseur — twee ID's, niet één met twee ernsten.** Elke check draagt in deze engine precies één ernst (`Check.severity`, bewaakt door `tests/test_checks_registry.py::test_ernst_en_dimensie_volgen_het_register`). Daarom **ADM-010** (`Severity.ERROR`) voor de gevallen `doorgaand`, `aanvoer` en `afvoer`, en **ADM-011** (`Severity.WARNING`) voor `losgekoppeld`. Beide `Dimension.CONSISTENCY`. Het issue nam één ID aan; de afwijking staat in BO-47 en in de afsluitende issue-comment.
- Keten: loze leidingen die via een knoop aan elkaar hangen. Knoop van een strengeinde = `dataset.resolve_network_node(uri, klassen.netwerkknopen) or uri` (None blijft None).
- Per keten, in de administratieve richting: `inkomend` = niet-loze leidingen die *eindigen* in een knoop waar een loze streng van de keten *begint*; `uitgaand` = niet-loze leidingen die *beginnen* in een knoop waar een loze streng van de keten *eindigt*. Geval: beide → `doorgaand`; alleen inkomend → `aanvoer`; alleen uitgaand → `afvoer`; geen van beide → `losgekoppeld`.
- **Ruling:** de richting is altijd de administratieve begin→eind-richting, ongeacht `[netwerk] richting`; NET-003 toetst of die klopt. Staat in de docstring en in BO-47.
- `bovenstrooms` = het aantal verschillende niet-loze leidingen dat transitief bovenstrooms van de keten ligt (vanuit de beginknopen terug via `eind == knoop`, cyclusveilig). Detailveld, geen invloed op de ernst.
- Melding per loze streng; `details["cluster_id"]` is de keten-ID (`SLEUTEL_CLUSTER` in `uitvoer/melding.py` is `"cluster_id"`); verder de details `geval`, `keten_strengen` (aantal), `inkomend` en `uitgaand` (labels, komma-gescheiden) en `bovenstrooms`.
- Populatie/`examined` = het aantal loze leidingen; `notes()` telt ketens en strengen per geval.
- Gegenereerde bestanden nooit met de hand bewerken: `tests/fixtures/ttl/*.ttl` via `uv run python scripts/maak_ttl_fixtures.py`, `docs/dekkingsmatrix.md` via `uv run python scripts/dekkingsmatrix.py`.
- Poort vóór elke commit die `src/**.py` raakt: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest` (zonder `zwaar`).
- Nederlandse docstrings en meldingsteksten; volg de stijl van `administratief.py` en `netwerk.py`. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden, nooit `git add -A`.
- Nieuw BO-nummer: het eerstvolgende na het laatste `### BO-` in `docs/beslislog.md` (verwacht **BO-47**; controleer). Gebruik dat nummer overal waar dit plan `BO-47` schrijft.
- CHANGELOG: onder `## [Unreleased]` → `### Toegevoegd`, bovenaan (maak de kop aan boven de andere koppen als hij ontbreekt).

---

### Task 1: ADM-010 en ADM-011 met fixtures, tests, register en documentatie

**Files:**
- Modify: `src/nlriochecker/checkconfig.py:26-67` (`ClassRoots.loze_leiding`), `src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml` (`[klassen] loze_leiding`)
- Modify: `src/nlriochecker/checks/selectie.py` (`lozeleidingen()`, `_ROLLEN`), `tests/test_checks_selectie.py` (`ROLLENSET_AANTALLEN`)
- Modify: `src/nlriochecker/checks/administratief.py` (ná ADM-009, onderaan: ketenbouwer + twee checks)
- Modify: `scripts/maak_ttl_fixtures.py` (`LOZE_KLASSE`; `selectie_rollen.ttl` krijgt een loze leiding; vier nieuwe fixtures), regenerate `tests/fixtures/ttl/selectie_rollen.ttl` en de vier nieuwe fixtures
- Modify: `tests/test_checks_blok_a.py` (`DEFECTEN`, drie tests)
- Modify: `data/checkregister-gwsw-nulmeting-v0_9.md` (twee rijen na ADM-009; addendum), regenerate `docs/dekkingsmatrix.md`; `docs/beslislog.md` (BO-47); `CHANGELOG.md`

**Interfaces:**
- Consumes: `leidingen(context) -> list[Conduit]` en `_verbindingen(context, sleutel, wortels)` in `selectie.py`; `Conduit.start_node/end_node/label/uri`; `dataset.resolve_network_node(uri, wortels)`; `context.config.klassen.netwerkknopen`; `CheckContext.cached`; `SLEUTEL_CLUSTER`-conventie (detailsleutel `cluster_id`); `getal` uit `nlriochecker.taal`; fixturehelpers `put`, `leiding`.
- Produces: `ClassRoots.loze_leiding: list[str]`; `selectie.lozeleidingen(context) -> list[Conduit]`; `REGISTRY["ADM-010"]` (`LozeLeidingAanActiefRiool`), `REGISTRY["ADM-011"]` (`LosgekoppeldeLozeLeiding`); detailvelden `cluster_id`, `geval`, `keten_strengen`, `inkomend`, `uitgaand`, `bovenstrooms`.

- [ ] **Step 1: Fixtures (generator, niet de bestanden)**

In `scripts/maak_ttl_fixtures.py`:

1. Direct ná `HULPSTUK_KLASSEN` (of, als dat blok er niet is, direct ná `put()`):

```python
# De loze leiding staat niet in de gedeelde prelude; alleen de fixtures van issue #62
# hebben haar nodig. Ze hangt onder Leiding en niet onder VrijvervalRioolleiding.
LOZE_KLASSE = "gwsw:LozeLeiding rdfs:subClassOf gwsw:Leiding .\n\n"
```

2. In `FIXTURES["selectie_rollen.ttl"]`: zet `LOZE_KLASSE +` vóór de bestaande eerste string (na `HULPSTUK_KLASSEN +` als dat er staat), en voeg ná de regel `+ leiding("P1", "P1", … klasse="Persleiding")` toe:

```python
    # Een loze leiding is wel een gwsw:Leiding maar geen vrijvervalrioolleiding en
    # geen mechanische leiding (issue #62).
    + leiding("Loos2", "Loos2", [(1300.0, 2000.0), (1300.0, 2050.0)], "Loos1", None, klasse="LozeLeiding")
```

Werk het rollenaantal in het commentaar bij (`vijftien` → `zestien`, of `veertien` → `vijftien` als issue #60 nog niet geland is).

3. Direct ná `FIXTURES["adm009_leiding_aan_put.ttl"] = (...)` (zoek op naam) vier fixtures. Putten op een rij: A0 (950), A (1000), B (1050), C (1100), D (1150), E (1200), alle op y = 2000:

```python
# ADM-010/ADM-011: loze leidingen in ketens (issue #62). Elke fixture bevat precies een
# keten en precies een geval. Streng 0 en 1 zijn actief en komen binnen (bovenstrooms 2),
# X1 en X2 zijn loos, streng 3 is actief en gaat verder.
FIXTURES["adm010_loze_keten_doorgaand.ttl"] = (
    "actief riool loopt via loze strengen X1 en X2 door: aanvoer via 1, afvoer via 3 (issue #62)",
    LOZE_KLASSE
    + put("PutA0", "A0", 950.0, 2000.0)
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + put("PutD", "D", 1150.0, 2000.0)
    + put("PutE", "E", 1200.0, 2000.0)
    + leiding("L0", "0", [(950.0, 2000.0), (1000.0, 2000.0)], "PutA0", "PutA")
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding")
    + leiding("X2", "X2", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutC", "PutD", klasse="LozeLeiding")
    + leiding("L3", "3", [(1150.0, 2000.0), (1200.0, 2000.0)], "PutD", "PutE"),
)

FIXTURES["adm010_loze_keten_aanvoer.ttl"] = (
    "actieve streng 1 watert af op loze streng X1; er gaat niets verder (issue #62)",
    LOZE_KLASSE
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"),
)

FIXTURES["adm010_loze_keten_afvoer.ttl"] = (
    "loze streng X1 voert af op actieve streng 3; er komt niets binnen (issue #62)",
    LOZE_KLASSE
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + put("PutD", "D", 1150.0, 2000.0)
    + leiding("X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding")
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutC", "PutD"),
)

FIXTURES["adm011_loze_keten_los.ttl"] = (
    "loze streng X1 hangt aan geen enkele actieve streng: dode data (issue #62)",
    LOZE_KLASSE
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + leiding("X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"),
)
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. `git status --short`: `selectie_rollen.ttl` gewijzigd, vier nieuwe fixtures, verder niets.

- [ ] **Step 2: Schrijf de falende tests**

1. `tests/test_checks_selectie.py`: `"lozeleidingen": 1,` in `ROLLENSET_AANTALLEN`; `"leidingen"` gaat van 5 naar **6** (de loze leiding is een `gwsw:Leiding`). Werk het commentaar bij.

2. `tests/test_checks_blok_a.py`, in `DEFECTEN` ná de rij van ADM-009:

```python
    # ADM-010 meldt per loze streng; de twee strengen van de doorgaande keten allebei.
    ("adm010_loze_keten_doorgaand.ttl", "ADM-010", ["X1", "X2"]),
    ("adm010_loze_keten_aanvoer.ttl", "ADM-010", ["X1"]),
    ("adm010_loze_keten_afvoer.ttl", "ADM-010", ["X1"]),
    ("adm011_loze_keten_los.ttl", "ADM-011", ["X1"]),
```

en onderaan het bestand:

```python
def test_adm010_doorgaande_keten_draagt_keten_buren_en_omvang() -> None:
    """Beide loze strengen delen een keten-ID en noemen de aansluitende actieve strengen."""
    outcome = uitkomst("adm010_loze_keten_doorgaand.ttl", "ADM-010")

    per_label = {f.object_label: f for f in outcome.findings}
    assert set(per_label) == {"X1", "X2"}
    assert per_label["X1"].details["cluster_id"] == per_label["X2"].details["cluster_id"]
    assert per_label["X1"].details["cluster_id"].startswith("loos-")
    for bevinding in per_label.values():
        assert bevinding.details["geval"] == "doorgaand"
        assert bevinding.details["keten_strengen"] == 2
        assert bevinding.details["inkomend"] == "1"
        assert bevinding.details["uitgaand"] == "3"
        # Streng 1 en streng 0 liggen transitief bovenstrooms.
        assert bevinding.details["bovenstrooms"] == 2
        assert "1" in bevinding.message and "3" in bevinding.message
    assert outcome.examined == 2


@pytest.mark.parametrize(
    ("bestand", "geval"),
    [
        ("adm010_loze_keten_aanvoer.ttl", "aanvoer"),
        ("adm010_loze_keten_afvoer.ttl", "afvoer"),
    ],
)
def test_adm010_benoemt_het_geval(bestand: str, geval: str) -> None:
    outcome = uitkomst(bestand, "ADM-010")

    assert [f.details["geval"] for f in outcome.findings] == [geval]
    assert labels(uitkomst(bestand, "ADM-011")) == []


def test_adm011_losgekoppelde_keten_is_een_waarschuwing_en_geen_adm010() -> None:
    outcome = uitkomst("adm011_loze_keten_los.ttl", "ADM-011")

    assert labels(outcome) == ["X1"]
    assert outcome.findings[0].details["geval"] == "losgekoppeld"
    assert outcome.findings[0].details["bovenstrooms"] == 0
    assert labels(uitkomst("adm011_loze_keten_los.ttl", "ADM-010")) == []
    assert labels(uitkomst("adm010_loze_keten_doorgaand.ttl", "ADM-011")) == []


def test_adm010_verantwoordt_de_ketens_per_geval() -> None:
    outcome = uitkomst("adm010_loze_keten_doorgaand.ttl", "ADM-010")

    assert any(
        "2 loze leidingen in 1 keten" in note and "1 doorgaand" in note for note in outcome.notes
    ), outcome.notes
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checks_blok_a.py tests/test_checks_selectie.py -k "adm010 or adm011 or loze or rollen" -v`
Expected: FAIL (`KeyError: 'ADM-010'`, `KeyError: 'lozeleidingen'`).

- [ ] **Step 4: Rol en selectie**

1. `src/nlriochecker/checkconfig.py`, in `ClassRoots` ná `vervallen`:

```python
    # ADM-010 en ADM-011: leidingen die buiten gebruik zijn maar nog in de ondergrond
    # liggen. LozeLeiding hangt onder Leiding, niet onder VrijvervalRioolleiding, en
    # dekt GedammerdeLeiding, Uitlegger, VolgeschuimdeLeiding en VolgezandeLeiding.
    loze_leiding: list[str] = Field(default_factory=list)
```

2. `src/nlriochecker/checks.toml` én `configs/dewoldenhoogeveen.toml`, in `[klassen]` direct ná de regel `mechanisch = [...]` (of ná `hulpstuk = ["Hulpstuk"]` als die er staat), letterlijk:

```toml
# ADM-010 en ADM-011: loze leidingen (GWSW: "Leiding is buiten gebruik"). De wortelklasse
# dekt ook GedammerdeLeiding, Uitlegger, VolgeschuimdeLeiding en VolgezandeLeiding; De
# Wolden levert alleen instanties van LozeLeiding zelf (54).
loze_leiding = ["LozeLeiding"]
```

3. `src/nlriochecker/checks/selectie.py`, ná `mechanischeleidingen`:

```python
def lozeleidingen(context: CheckContext) -> list[Conduit]:
    """De loze leidingen: `gwsw:LozeLeiding` en haar subklassen.

    Buiten gebruik, maar nog in de ondergrond. Geen vrijvervalrioolleiding, dus elke
    check die daarop selecteert slaat ze over; ADM-010 en ADM-011 kijken juist of het
    actieve riool er nog op aansluit.
    """
    return _verbindingen(context, "sel:lozeleidingen", context.config.klassen.loze_leiding)
```

en `"lozeleidingen": lozeleidingen,` in `_ROLLEN` ná `"mechanischeleidingen"`.

- [ ] **Step 5: De checks**

`src/nlriochecker/checks/administratief.py`, onderaan (ná ADM-009). Importeer `dataclass` uit `dataclasses`, `deque` uit `collections`, `leidingen` en `lozeleidingen` uit `nlriochecker.checks.selectie`, `getal` uit `nlriochecker.taal`:

```python
GEVAL_DOORGAAND = "doorgaand"
GEVAL_AANVOER = "aanvoer"
GEVAL_AFVOER = "afvoer"
GEVAL_LOSGEKOPPELD = "losgekoppeld"


@dataclass(frozen=True)
class _LozeKeten:
    """Loze leidingen die via een knoop aan elkaar hangen, met wat er actief op aansluit."""

    id: str
    strengen: tuple[Conduit, ...]
    inkomend: tuple[Conduit, ...]
    uitgaand: tuple[Conduit, ...]
    bovenstrooms: int

    @property
    def geval(self) -> str:
        """Hoe de keten aan het actieve riool hangt."""
        if self.inkomend and self.uitgaand:
            return GEVAL_DOORGAAND
        if self.inkomend:
            return GEVAL_AANVOER
        if self.uitgaand:
            return GEVAL_AFVOER
        return GEVAL_LOSGEKOPPELD


def _loze_ketens(context: CheckContext) -> tuple[_LozeKeten, ...]:
    """De ketens van loze leidingen; een keer per context, gedeeld door ADM-010 en ADM-011."""
    return context.cached("adm010:ketens", lambda: _bouw_loze_ketens(context))


def _bouw_loze_ketens(context: CheckContext) -> tuple[_LozeKeten, ...]:
    """Groepeert de loze leidingen tot ketens en bepaalt per keten de aansluitingen.

    De richting is de administratieve begin-naar-eindrichting, ongeacht `[netwerk]
    richting`: dat is de bron die NET-003 toetst, en een verkeerd gerichte administratie
    is daar een bevinding en niet hier. Een strengeinde wordt naar zijn netwerkknoop
    herleid met terugval op de rauwe URI, zodat ook een hulpstuk als knoop telt.
    """
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen

    def knoop(uri: str | None) -> str | None:
        if uri is None:
            return None
        return dataset.resolve_network_node(uri, wortels) or uri

    loos = sorted(lozeleidingen(context), key=lambda conduit: conduit.uri)
    loos_uris = {conduit.uri for conduit in loos}
    actief = [conduit for conduit in leidingen(context) if conduit.uri not in loos_uris]
    einden = {conduit.uri: (knoop(conduit.start_node), knoop(conduit.end_node)) for conduit in loos}
    # Actieve strengen per eindknoop (voor inkomend en bovenstrooms) en per beginknoop.
    actief_per_eind: dict[str, list[Conduit]] = {}
    actief_per_begin: dict[str, list[Conduit]] = {}
    for conduit in actief:
        begin, eind = knoop(conduit.start_node), knoop(conduit.end_node)
        if eind is not None:
            actief_per_eind.setdefault(eind, []).append(conduit)
        if begin is not None:
            actief_per_begin.setdefault(begin, []).append(conduit)

    # Loze strengen die een knoop delen horen bij dezelfde keten.
    loos_per_knoop: dict[str, list[Conduit]] = {}
    for conduit in loos:
        for uri in einden[conduit.uri]:
            if uri is not None:
                loos_per_knoop.setdefault(uri, []).append(conduit)
    gezien: set[str] = set()
    gebruikt: set[str] = set()
    ketens: list[_LozeKeten] = []
    for start in loos:
        if start.uri in gezien:
            continue
        groep: list[Conduit] = []
        wachtrij = deque([start])
        gezien.add(start.uri)
        while wachtrij:
            conduit = wachtrij.popleft()
            groep.append(conduit)
            for uri in einden[conduit.uri]:
                for buur in loos_per_knoop.get(uri, []) if uri is not None else []:
                    if buur.uri not in gezien:
                        gezien.add(buur.uri)
                        wachtrij.append(buur)
        groep.sort(key=lambda conduit: conduit.uri)
        beginknopen = {einden[c.uri][0] for c in groep if einden[c.uri][0] is not None}
        eindknopen = {einden[c.uri][1] for c in groep if einden[c.uri][1] is not None}
        inkomend = sorted(
            {c.uri: c for k in beginknopen for c in actief_per_eind.get(k, [])}.values(),
            key=lambda conduit: conduit.uri,
        )
        uitgaand = sorted(
            {c.uri: c for k in eindknopen for c in actief_per_begin.get(k, [])}.values(),
            key=lambda conduit: conduit.uri,
        )
        naam = _uniek_ketennaam(f"loos-{groep[0].label or groep[0].uri.rsplit('#', 1)[-1]}", gebruikt)
        gebruikt.add(naam)
        ketens.append(
            _LozeKeten(
                naam,
                tuple(groep),
                tuple(inkomend),
                tuple(uitgaand),
                _bovenstrooms(beginknopen, actief_per_eind, knoop),
            )
        )
    return tuple(ketens)


def _bovenstrooms(
    beginknopen: set[str],
    actief_per_eind: dict[str, list[Conduit]],
    knoop,
) -> int:
    """Het aantal verschillende actieve strengen transitief bovenstrooms van deze knopen."""
    gezien_knopen = set(beginknopen)
    gezien_strengen: set[str] = set()
    wachtrij = deque(beginknopen)
    while wachtrij:
        huidig = wachtrij.popleft()
        for conduit in actief_per_eind.get(huidig, []):
            if conduit.uri in gezien_strengen:
                continue
            gezien_strengen.add(conduit.uri)
            begin = knoop(conduit.start_node)
            if begin is not None and begin not in gezien_knopen:
                gezien_knopen.add(begin)
                wachtrij.append(begin)
    return len(gezien_strengen)


def _uniek_ketennaam(naam: str, gebruikt: set[str]) -> str:
    """Maakt de ketennaam uniek; twee ketens mogen niet hetzelfde ID krijgen."""
    if naam not in gebruikt:
        return naam
    volgnummer = 2
    while f"{naam}-{volgnummer}" in gebruikt:
        volgnummer += 1
    return f"{naam}-{volgnummer}"


def _labels(strengen: tuple[Conduit, ...]) -> str:
    """De labels van deze strengen, komma-gescheiden."""
    return ", ".join(conduit.label or conduit.uri for conduit in strengen)


class _LozeLeidingen(Check):
    """Gedeelde basis voor ADM-010 (keten aan actief riool) en ADM-011 (losgekoppeld)."""

    gevallen: frozenset[str]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt per loze streng in een keten van de gevallen van deze check."""
        for keten in _loze_ketens(context):
            geval = keten.geval
            if geval not in self.gevallen:
                continue
            for conduit in keten.strengen:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    self._boodschap(keten),
                    cluster_id=keten.id,
                    geval=geval,
                    keten_strengen=len(keten.strengen),
                    inkomend=_labels(keten.inkomend),
                    uitgaand=_labels(keten.uitgaand),
                    bovenstrooms=keten.bovenstrooms,
                )

    @staticmethod
    def _boodschap(keten: _LozeKeten) -> str:
        """De tekst per geval, met de aansluitende actieve strengen bij naam."""
        omvang = f" Bovenstrooms liggen {getal(keten.bovenstrooms, 'actieve streng', 'actieve strengen')}."
        if keten.geval == GEVAL_DOORGAAND:
            return (
                f"Het actieve riool loopt door deze loze leiding heen: {_labels(keten.inkomend)} "
                f"komt binnen en {_labels(keten.uitgaand)} gaat verder.{omvang}"
            )
        if keten.geval == GEVAL_AANVOER:
            return (
                f"Actief riool ({_labels(keten.inkomend)}) watert af op deze loze leiding, "
                f"maar er gaat niets verder.{omvang}"
            )
        if keten.geval == GEVAL_AFVOER:
            return (
                f"Deze loze leiding voert af op actief riool ({_labels(keten.uitgaand)}), "
                "maar er komt niets binnen."
            )
        return "Deze loze leiding hangt aan geen enkele actieve streng: dode data."

    def notes(self, context: CheckContext) -> list[str]:
        """Telt de ketens en strengen per geval, zodat de lezer het geheel ziet."""
        ketens = _loze_ketens(context)
        if not ketens:
            return []
        per_geval = {
            geval: [keten for keten in ketens if keten.geval == geval]
            for geval in (GEVAL_DOORGAAND, GEVAL_AANVOER, GEVAL_AFVOER, GEVAL_LOSGEKOPPELD)
        }
        delen = ", ".join(
            f"{len(groep)} {geval} ({sum(len(keten.strengen) for keten in groep)} strengen)"
            for geval, groep in per_geval.items()
        )
        totaal = sum(len(keten.strengen) for keten in ketens)
        return [
            f"{getal(totaal, 'loze leiding', 'loze leidingen')} in "
            f"{getal(len(ketens), 'keten', 'ketens')}: {delen}. De richting is de "
            "administratieve begin-naar-eindrichting; of die klopt toetst NET-003."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal loze leidingen."""
        return len(lozeleidingen(context))


@register
class LozeLeidingAanActiefRiool(_LozeLeidingen):
    """ADM-010: een keten van loze leidingen waar actief riool op aansluit.

    Een `LozeLeiding` is buiten gebruik (GWSW: "Leiding is buiten gebruik"); er kan per
    definitie geen actief riool op afwateren. Gebeurt dat toch, dan is de loze leiding
    verkeerd geclassificeerd, of zijn de buurstrengen dat, of ontbreekt er een omlegging.
    Doorgaand is het ergste: het actieve riool loopt volgens het model dwars door een
    buiten gebruik gestelde streng (issue #62).
    """

    id = "ADM-010"
    title = "Loze leiding waar actief riool op aansluit (doorgaand, aanvoer of afvoer)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    gevallen = frozenset({GEVAL_DOORGAAND, GEVAL_AANVOER, GEVAL_AFVOER})


@register
class LosgekoppeldeLozeLeiding(_LozeLeidingen):
    """ADM-011: een keten van loze leidingen zonder enige actieve aansluiting: dode data."""

    id = "ADM-011"
    title = "Loze leiding zonder enige aansluiting op actief riool"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    gevallen = frozenset({GEVAL_LOSGEKOPPELD})
```

Controleer: de test eist `"2 loze leidingen in 1 keten"` en `"1 doorgaand"` in één notitie; `getal(1, 'keten', 'ketens')` levert `"1 keten"` en de delen beginnen met `"1 doorgaand (2 strengen)"`. Pas de tekst aan als `getal` anders werkt dan `f"{aantal} {woord}"`.

- [ ] **Step 6: Draai de tests en zie ze slagen; hele suite**

Run: `uv run pytest tests/test_checks_blok_a.py tests/test_checks_selectie.py tests/test_checkconfig.py tests/test_ttl_fixtures.py -q`
Expected: PASS, op `test_checks_registry.py`/`test_dekkingsmatrix.py` na (Step 7). Daarna `uv run pytest -q`. Valt een test elders omdat er nu twee checks meer zijn (een telling van `REGISTRY`, een verslag met vaste aantallen), werk de verwachting bij met een regel commentaar en verklaar dat in je rapport.

- [ ] **Step 7: Register, dekkingsmatrix, beslislog, CHANGELOG**

1. `data/checkregister-gwsw-nulmeting-v0_9.md`, ná de rij ADM-009:

```markdown
| ADM-010 | Loze leiding (`LozeLeiding` en subklassen: buiten gebruik, nog in de ondergrond) waar actief riool op aansluit. Loze leidingen die een knoop delen vormen een keten; per keten in de administratieve richting: actief riool dat in een beginknoop eindigt (aanvoer), actief riool dat in een eindknoop begint (afvoer), of beide (doorgaand: het actieve riool loopt volgens het model door een buiten gebruik gestelde streng). Melding per loze streng met de keten in `cluster_id` en het aantal actieve strengen bovenstrooms als detail; de nulmeting noemt loze leidingen alleen voor attribuutgebreken, nooit voor hun plaats in het net (issue #62) | F | Consistentie |
| ADM-011 | Loze leiding in een keten zonder enige aansluiting op actief riool: geen hydraulische fout maar dode data. Zelfde ketenbouw als ADM-010 (issue #62) | W | Consistentie |
```

2. In `## Versiehistorie`, bovenaan een alinea:

```markdown
Versie 0.9, addendum (2026-08-24): ADM-010 (F) en ADM-011 (W), beide Consistentie, toegevoegd:
loze leidingen, tot ketens gegroepeerd, waar actief riool op aansluit (doorgaand, aanvoer of
afvoer) respectievelijk die aan niets hangen. Melding per loze streng met de keten in
`cluster_id`. Twee ID's en niet één met twee ernsten, want elke check draagt hier precies één
ernst. De klasse komt uit `[klassen] loze_leiding`; ADM-006 blijft ongemoeid (dat meldt op
`Einddatum`/`Begindatum`, dit op de klasse). Zie
[#62](https://github.com/mcolee/nlriochecker/issues/62) en BO-47.

```

3. Regenereer: `uv run python scripts/dekkingsmatrix.py`; `git diff docs/dekkingsmatrix.md` toont twee nieuwe ADM-rijen en de ADM-telling 9 → 11.

4. `docs/beslislog.md`, aan het einde:

```markdown

### BO-47 Loze leidingen in ketens: ADM-010 voor een keten aan actief riool, ADM-011 voor dode data

**Wat.** Loze leidingen (`LozeLeiding` en subklassen, rol `[klassen] loze_leiding`) die via een
knoop aan elkaar hangen vormen een keten. Per keten, in de administratieve begin→eindrichting:
`inkomend` zijn de niet-loze leidingen die eindigen in een beginknoop van de keten, `uitgaand`
de niet-loze leidingen die beginnen in een eindknoop. ADM-010 (F) meldt *doorgaand* (beide),
*aanvoer* (alleen inkomend) en *afvoer* (alleen uitgaand); ADM-011 (W) meldt *losgekoppeld*
(geen van beide). Melding per loze streng, keten in `cluster_id`, het transitieve aantal actieve
strengen bovenstrooms als detail `bovenstrooms` (zonder invloed op de ernst). Uitgewerkt in
issue #62.

**Waarom.** Een `LozeLeiding` is buiten gebruik; er kan per definitie geen actief riool op
afwateren. In De Wolden en Hoogeveen gebeurt dat in 19 van de 33 ketens, waarvan 3 doorgaand.
Geen enkele check zag het: `LozeLeiding` hangt onder `Leiding` en niet onder
`VrijvervalRioolleiding`, dus alle checks op `klassen.vrijvervalleiding` slaan haar over; de
nulmeting noemt loze leidingen 37 keer, alleen voor attribuutgebreken. Per streng melden en niet
per keten, zodat elke streng op de kaart kleurt; het keten-ID houdt ze in het rapport bij elkaar.

**Twee ID's, niet een.** Het issue nam ADM-010 met F én W aan; de engine en het register kennen
per check een ernst (`Check.severity`, `test_ernst_en_dimensie_volgen_het_register`). Vandaar
ADM-011 voor de losgekoppelde keten.

**Richting.** Altijd de administratieve richting, ongeacht `[netwerk] richting`: dat is de bron
die NET-003 toetst, en een verkeerd gerichte administratie is dáár een bevinding.

**Alternatieven.** Melden per keten (verworpen: dan kleurt maar een streng). ADM-006 uitbreiden
(verworpen: die gaat over `Einddatum`/`Begindatum`, dit over de klasse; en ADM-006 vindt hier
niets, want geen enkel object draagt een `Einddatum`). De ernst laten afhangen van het aantal
strengen bovenstrooms (verworpen: het aantal is een sorteersleutel, geen norm).
```

5. `CHANGELOG.md`, onder `## [Unreleased]` → `### Toegevoegd`, bovenaan:

```markdown
- **ADM-010 en ADM-011: loze leidingen die in het actieve netwerk hangen** (issue #62).
  Loze leidingen (`LozeLeiding`, buiten gebruik) worden tot ketens gegroepeerd; ADM-010
  (F) meldt per loze streng een keten waar actief riool op aansluit (doorgaand, aanvoer
  of afvoer, in de administratieve richting), ADM-011 (W) een keten die aan niets hangt.
  De keten staat in `cluster_id`, het aantal actieve strengen bovenstrooms als detail.
  Nieuwe rol `[klassen] loze_leiding`. Op De Wolden en Hoogeveen: 54 loze leidingen in 33
  ketens, 38 F en 16 W (Task 2 meet het). Zie BO-47.
```

- [ ] **Step 8: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`
Expected: alle vier groen.

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/selectie_rollen.ttl \
  tests/fixtures/ttl/adm010_loze_keten_doorgaand.ttl tests/fixtures/ttl/adm010_loze_keten_aanvoer.ttl \
  tests/fixtures/ttl/adm010_loze_keten_afvoer.ttl tests/fixtures/ttl/adm011_loze_keten_los.ttl \
  src/nlriochecker/checkconfig.py src/nlriochecker/checks.toml configs/dewoldenhoogeveen.toml \
  src/nlriochecker/checks/selectie.py src/nlriochecker/checks/administratief.py \
  tests/test_checks_blok_a.py tests/test_checks_selectie.py \
  data/checkregister-gwsw-nulmeting-v0_9.md docs/dekkingsmatrix.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "ADM-010/ADM-011: loze leidingen in ketens die aan actief riool hangen of aan niets (issue #62)"
```

---

### Task 2: Effect op De Wolden meten en vastleggen

**Files:**
- Create (niet committen): `uitvoer/issue62/`
- Modify: `docs/beslislog.md` (BO-47: alinea "Gemeten uitkomst"), `CHANGELOG.md` (getallen)

- [ ] **Step 1: Draai de volledige toets**

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
  --output uitvoer/issue62
```

- [ ] **Step 2: Meet**

```bash
head -1 uitvoer/issue62/bevindingen.csv
uv run python - <<'EOF'
import pandas as pd, re
frame = pd.read_csv("uitvoer/issue62/bevindingen.csv", sep=";")
deel = frame[frame.Check.isin(["ADM-010", "ADM-011"])].copy()
print("meldingen:", deel.Check.value_counts().to_dict(), "ernst:", deel.Ernst.value_counts().to_dict())
print("ketens:", deel.ClusterId.nunique() if "ClusterId" in deel else "kolomnaam controleren")
def geval(b):
    return ("doorgaand" if "loopt door" in b else "aanvoer" if "watert af op" in b
            else "afvoer" if "voert af op" in b else "losgekoppeld")
deel["geval"] = deel.Boodschap.map(geval)
print(deel.groupby("geval").agg(strengen=("ObjectLabel", "size"), ketens=("ClusterId", "nunique")))
kv = deel[deel.ObjectLabel.isin(["ID0500-Kv1X0002-1", "Kv1X0002-Kv1G0014-1"])]
print(kv[["ObjectLabel", "Boodschap"]].to_string())
deel["bovenstrooms"] = deel.Boodschap.str.extract(r"Bovenstrooms liggen (\d+)")[0].astype(float)
print(deel.sort_values("bovenstrooms", ascending=False)[["ObjectLabel", "bovenstrooms"]].head(5).to_string())
EOF
grep -n "loze leidingen in" uitvoer/issue62/bevindingen.md | head -2
```

Lees eerst de kolomnamen (`Check`, `Ernst`, `ClusterId`, `ObjectLabel`, `Boodschap` -- pas aan wat afwijkt). Verwacht volgens het issue: 54 strengen in 33 ketens; doorgaand 3 ketens/8 strengen, aanvoer 11/16, afvoer 5/14, losgekoppeld 14/16; 38 F (ADM-010) en 16 W (ADM-011). Het Koekangerveld-controlegeval: `ID0500-Kv1X0002-1` en `Kv1X0002-Kv1G0014-1` allebei doorgaand, met `ID6391-ID0500-1` als inkomend en `Kv1G0014-Kv1G0012-1`, `Kv1G0014-Kv1G0016-1` als uitgaand. Top-5 bovenstrooms: `Zu1G0932-Zu1X0006-1` 253, `Wi1G0282-Wi1X0002-1` 126, `An2G0048-An2X0002-1` 58, `Ru1G0138-Ru1X0004-1` 46, `Ru1G0142-Ru1X0002-1` 41. Is issue #60 (de fantoomkoppeling) al geland, dan kunnen de aantallen iets oplopen: meet, en meld het verschil met de tabel uit het issue. Wijkt iets anders af, meld het getal en de richting; redeneer het niet weg.

- [ ] **Step 3: Leg vast en commit**

Aan BO-47 in `docs/beslislog.md` een slotalinea:

```markdown

**Gemeten uitkomst (2026-08-24).** Volledige toets op De Wolden en Hoogeveen: <N> loze leidingen in
<K> ketens -- doorgaand <kd>/<sd>, aanvoer <ka>/<sa>, afvoer <kf>/<sf>, losgekoppeld <kl>/<sl>
(ketens/strengen); ADM-010 <F> meldingen, ADM-011 <W>. Het Koekangerveld-controlegeval
(`ID0500-Kv1X0002-1`, `Kv1X0002-Kv1G0014-1`) is doorgaand met `ID6391-ID0500-1` als aanvoer en
`Kv1G0014-Kv1G0012-1`/`Kv1G0014-Kv1G0016-1` als afvoer. Grootste ketens naar actief riool
bovenstrooms: <top-5>. Verschil met de tabel uit het issue: <geen, of de verklaring; bv. de
herstelde fantoomkoppeling uit #60>.
```

Corrigeer de getallen in de CHANGELOG-regel van Task 1 en haal `(Task 2 meet het)` weg. Dan:

```bash
git add docs/beslislog.md CHANGELOG.md
git commit -m "BO-47: gemeten uitkomst van ADM-010/ADM-011 op De Wolden (issue #62)"
```

Zet de metingen in het rapportbestand van deze taak.
