# Issue #65: meldingen onderdrukken per klasse en per check — implementatieplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Een projectconfiguratie kan meldingen onderdrukken op twee lijsten in `[rapport]` — `onderdruk_klassen` (GWSW-wortelklassen, subklassen via de ontologie) en `onderdruk_checks` (check-ID's). Het filter zit op één plek, vóór elke schrijver; het rapport, `gwsw_run` en de JSON-envelop tellen wat er wegviel; een object waarvan alle meldingen onderdrukt zijn wordt grijs met een reden. De Wolden onderdrukt zo het mechanische riool.

**Architecture:** De twee lijsten zijn velden van `ReportOptions` (`checkconfig.py`). `uitvoer/melding.py` krijgt `bouw_meldingenstroom`, dat na het samenstellen van de drie bronnen filtert en telt en een `Meldingenstroom` (meldingen + `Onderdrukking`) teruggeeft; `bouw_meldingen` blijft bestaan als dunne wrapper die alleen de lijst geeft (66 aanroepen in de tests blijven zo ongemoeid). `schrijver.py` gebruikt de stroom en geeft de `Onderdrukking` door aan rapport, GeoPackage, JSON en synthese. Onderdrukking is een uitvoerkeuze: de checks, `examined` en `_is_systemisch` veranderen niet.

**Tech Stack:** Python 3.12, pydantic, pytest, sqlite3 (bestaand). Geen nieuwe afhankelijkheid.

**Spec:** GitHub-issue #65 (`gh issue view 65 --json body --jq .body`). De regisseur heeft vier rulings toegevoegd, zie Global Constraints (wrapper i.p.v. nieuw retourtype; lazy import voor de ID-validatie; JSON-veld alleen bij actieve onderdrukking; totaal-JSON telt de som over de gebieden).

## Global Constraints

- **Sleutelnamen** `onderdruk_klassen` en `onderdruk_checks`, beide `list[str] = Field(default_factory=list)` op `ReportOptions`, ná `register_versie`. Beide staan expliciet in `src/nlriochecker/checks.toml` `[rapport]` (leeg) en in `configs/dewoldenhoogeveen.toml` `[rapport]` (`onderdruk_klassen = ["MechanischeRioolleiding", "MechanischeTransportleiding"]`, `onderdruk_checks = []`); `test_elke_drempel_staat_expliciet_in_de_toml` eist dat.
- **Onbekend check-ID faalt bij het laden** met een `ConfigError` die het onbekende ID noemt. **Ruling van de regisseur:** een `field_validator("onderdruk_checks")` op `ReportOptions` met een *lazy* import `from nlriochecker.checks import REGISTRY` ín de validator, met een commentaar dat `checks/base.py` `checkconfig` importeert en een import op moduleniveau een kringimport zou zijn. Geen tweede registerlijst.
- **Het filter zit in `bouw_meldingenstroom`** en nergens anders. Regels, in deze volgorde per melding: (1) `check_id in onderdruk_checks` → telt onder `per_check[check_id]`; (2) anders `run.dataset.is_a(melding.object_uri, wortel)` voor `wortel in onderdruk_klassen` in lijstvolgorde, eerste treffer → telt onder `per_klasse[wortel]`; (3) anders blijft de melding. Een lege `object_uri` (datasetsignaal, onherleide nulmelding) valt nooit op klasse weg; `object2_uri` telt niet mee. Elke melding valt hooguit één keer weg.
- **Ruling van de regisseur — geen nieuw retourtype voor `bouw_meldingen`:** `bouw_meldingen(run, run_datum) -> list[Melding]` blijft en geeft `bouw_meldingenstroom(run, run_datum).meldingen` terug. De schrijvers (`schrijver.py`) gebruiken `bouw_meldingenstroom`. De parameter `meldingen` van `schrijf_uitvoer` wordt `stroom: Meldingenstroom | None = None`.
- **De dataclasses** (in `uitvoer/melding.py`, exact deze velden):

```python
@dataclass(frozen=True)
class Onderdrukking:
    """Wat er op grond van `[rapport]` uit de meldingenstroom is gehouden.

    `klassen` en `checks` zijn de twee lijsten uit de projectconfiguratie; `per_check`
    en `per_klasse` tellen wat erdoor wegviel. Een melding valt hooguit een keer weg:
    eerst op check-ID, dan op de klasse van het hoofdobject, in de volgorde van de
    lijst. Een uitvoerkeuze, geen toetskeuze: de checks, `examined` en de
    systemisch-bepaling zien deze lijsten niet.
    """

    klassen: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()
    per_check: dict[str, int] = field(default_factory=dict)
    per_klasse: dict[str, int] = field(default_factory=dict)

    @property
    def actief(self) -> bool:
        """Of de projectconfiguratie iets onderdrukt -- ook als er nul meldingen wegvielen."""
        return bool(self.klassen or self.checks)

    @property
    def totaal(self) -> int:
        """Hoeveel meldingen er in totaal wegvielen."""
        return sum(self.per_check.values()) + sum(self.per_klasse.values())


GEEN_ONDERDRUKKING = Onderdrukking()


@dataclass(frozen=True)
class Meldingenstroom:
    """De meldingen die de schrijvers krijgen, plus wat er vóór hen uit is gehouden."""

    meldingen: list[Melding]
    onderdrukking: Onderdrukking
```

- **Rapport (verantwoording):** alleen als `onderdrukking.actief`, direct ná het studiegebiedblok (`if run.study_area is not None: ...`) in `_verantwoording`, altijd — ook bij nul weggevallen meldingen, want stilte leest als "alles gecontroleerd":
  `**{getal(N, 'melding onderdrukt', 'meldingen onderdrukt')}** op grond van `[rapport]` in de projectconfiguratie — per check: {"TOP-011 3, ATTR-001 2" of "geen"}; per klasse: {"MechanischeRioolleiding 5" of "geen"}. Die meldingen staan in geen enkele uitvoervorm; wie ze wil zien draait zonder `onderdruk_klassen` en `onderdruk_checks`.` gevolgd door een lege regel. Gesorteerd op sleutel.
- **Synthese (`totaal/synthese.md`):** `GebiedsSamenvatting` krijgt `onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING` als laatste veld. Als er een gebied met `actief` is, één regel ná de alinea "… unieke meldingen over alle gebieden samen …": `Over alle gebieden samen zijn {N} meldingen onderdrukt op grond van `[rapport]` (som over de gebieden, niet ontdubbeld; de telling per check en per klasse staat in de verantwoording van elk gebied).` plus lege regel.
- **GeoPackage:** `gwsw_run` krijgt drie kolommen ná `volledig` en vóór `markering`: `onderdruk_klassen` (text, `", ".join`), `onderdruk_checks` (text), `meldingen_onderdrukt` (integer). `schrijf_geopackage` krijgt keyword `onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING`. Nieuwe constante `REDEN_ONDERDRUKT = "meldingen onderdrukt op grond van de projectconfiguratie"` naast `REDEN_MECHANISCH`; `_reden_niet_beoordeeld` krijgt een parameter `onderdrukt: frozenset[str]` vóór `mechanisch` en toetst die als eerste. De verzameling komt uit `run.config.rapport.onderdruk_klassen` via `run.dataset.of_class(wortel)` (lege lijst → `frozenset()`).
- **JSON:** `schrijf_json` krijgt keyword `onderdrukking: Onderdrukking | None = None` en schrijft, alleen als `onderdrukking is not None and onderdrukking.actief`, ná `typeringspoort_toegepast` en vóór `markering` het veld `"onderdrukt": {"klassen": [...], "checks": [...], "meldingen": N}`. **Ruling van de regisseur:** optioneel en additief, dus `SCHEMA_VERSIE` blijft `"1.1"` (dezelfde regel als `markering`); een run zonder lijsten blijft byte-voor-byte gelijk. In `totaal/bevindingen.json` is `meldingen` de som over de gebieden (ruling: consistent met de kolom Meldingen in de synthese, niet ontdubbeld; `docs/json-schema.md` zegt dat). De CSV krijgt **geen** kolom.
- **Fixture** alleen via de generator: `scripts/maak_ttl_fixtures.py` → `uv run python scripts/maak_ttl_fixtures.py`. Nooit een `tests/fixtures/ttl/*.ttl` met de hand bewerken.
- **Poort** vóór elke commit die `src/**.py` raakt: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q` (zonder `zwaar`). Draai lange commando's op de **voorgrond** (Bash met `timeout` tot 600000 ms), niet in de achtergrond.
- Nederlandse docstrings en meldingsteksten, Engelse identifiers; volg de stijl van het bestand dat je bewerkt. Werk op `dev`. Geen `gh issue create`. Commit met expliciete paden (`git add <pad> …`), nooit `git add -A`; voeg geen `docs/superpowers/plans/*` of `uitvoer/` toe.
- Nieuw besluit: **BO-49** in `docs/beslislog.md`, direct ná BO-48 (het bestand eindigt daar). CHANGELOG: nieuwe eerste regel onder `### Toegevoegd` onder `## [Unreleased]`.

---

### Task 1: Config, ID-validatie, het filter en de telling

**Files:**
- Modify: `src/nlriochecker/checkconfig.py:426-440` (`ReportOptions`)
- Modify: `src/nlriochecker/checks.toml:404-418` en `configs/dewoldenhoogeveen.toml:400-414` (`[rapport]`)
- Modify: `src/nlriochecker/uitvoer/melding.py:93-145` (`bouw_meldingen` → `bouw_meldingenstroom`, `Onderdrukking`, `Meldingenstroom`)
- Modify: `scripts/maak_ttl_fixtures.py` (na `FIXTURES["top011_hartlijnkruising.ttl"]`, regel ~314); regenerate `tests/fixtures/ttl/onderdruk_persleiding.ttl`
- Modify: `tests/test_checkconfig.py` (regel 167-175 en twee nieuwe tests), `tests/test_uitvoer_melding.py` (nieuwe tests), `tests/test_gwsw_vocabulaire.py:176-208, 440-470`

**Interfaces:**
- Consumes: `run.config.rapport`, `run.dataset.is_a(uri, root)`, `load_check_config`, `ConfigError`, `REGISTRY` (`nlriochecker.checks`), testhelpers `_config()`, `_run()`, `_nulbevinding()`, `_run_met_nulbevindingen()` uit `tests/test_uitvoer_melding.py`.
- Produces: `Onderdrukking`, `GEEN_ONDERDRUKKING`, `Meldingenstroom`, `bouw_meldingenstroom(run, run_datum) -> Meldingenstroom`; `bouw_meldingen` ongewijzigd van buiten gezien. `ReportOptions.onderdruk_klassen`, `.onderdruk_checks`.

- [ ] **Step 1: Fixture (generator, niet het bestand)**

In `scripts/maak_ttl_fixtures.py`, direct ná het afsluitende `)` van `FIXTURES["top011_hartlijnkruising.ttl"]` en vóór `# TOP-013: drie strengen tussen hetzelfde putpaar.`:

```python

# Issue #65: dezelfde kruising, maar streng 2 is een persleiding. TOP-011 meldt beide
# richtingen (elke streng is een keer het hoofdobject); met `[rapport] onderdruk_klassen`
# op de mechanische wortel valt de melding op de persleiding weg en blijft die op de
# vrijvervalstreng -- met de persleiding als tweede object -- staan.
FIXTURES["onderdruk_persleiding.ttl"] = (
    "een vrijvervalstreng kruist een persleiding; onderdrukking per klasse (issue #65)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 1975.0)
    + put("PutD", "D", 1025.0, 2025.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "L2", "2", [(1025.0, 1975.0), (1025.0, 2025.0)], "PutC", "PutD", klasse="Persleiding"
    ),
)
```

Regenereer: `uv run python scripts/maak_ttl_fixtures.py`. Controleer met `git status --short` dat alleen `tests/fixtures/ttl/onderdruk_persleiding.ttl` nieuw is en geen andere fixture verandert. De prelude van de generator declareert `gwsw:Persleiding rdfs:subClassOf gwsw:MechanischeTransportleiding` (regel 41), dus de fixture draagt zijn eigen hiërarchie. Controleer met `uv run pytest tests/test_ttl_fixtures.py -q`.

- [ ] **Step 2: Schrijf de falende tests**

1. `tests/test_checkconfig.py`, in `test_rapportinstellingen_hebben_bruikbare_defaults` twee asserties toevoegen:

```python
    assert rapport.onderdruk_klassen == []
    assert rapport.onderdruk_checks == []
```

en direct ná die test twee nieuwe:

```python
def test_onbekend_onderdruk_check_id_faalt_bij_het_laden(tmp_path: Path) -> None:
    """Een typefout in `onderdruk_checks` zou stil niets onderdrukken (issue #65)."""
    bron = default_check_config_path().read_text(encoding="utf-8")
    pad = tmp_path / "checks.toml"
    pad.write_text(
        bron.replace('onderdruk_checks = []', 'onderdruk_checks = ["XYZ-999"]'), encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="XYZ-999"):
        load_check_config(pad)


def test_de_projectconfig_onderdrukt_het_mechanische_riool() -> None:
    """De Wolden: dezelfde twee wortels als `[klassen] mechanisch` (issue #56, #65)."""
    config = load_check_config(PROJECTCONFIG)

    assert config.rapport.onderdruk_klassen == config.klassen.mechanisch
    assert config.rapport.onderdruk_checks == []
```

Controleer welke van `Path`, `pytest`, `ConfigError`, `default_check_config_path`, `PROJECTCONFIG` het bestand al importeert (regel 1-30) en vul aan wat ontbreekt.

2. `tests/test_uitvoer_melding.py`, aan het einde van het bestand:

```python
# Issue #65: onderdrukking per klasse en per check, in `bouw_meldingenstroom` en nergens
# anders. De fixture: vrijvervalstreng L1 kruist persleiding L2; TOP-011 meldt beide
# richtingen.
PERSLEIDING = "http://example.org/toets#L2"
VRIJVERVAL = "http://example.org/toets#L1"


def _run_onderdrukt(
    klassen: list[str] = (), checks: list[str] = (), *bevindingen: Nulbevinding
) -> CheckRun:
    """TOP-011 op de kruisingsfixture, met de twee lijsten uit `[rapport]` gezet."""
    config = _config()
    config.rapport.onderdruk_klassen = list(klassen)
    config.rapport.onderdruk_checks = list(checks)
    dataset = load_dataset(TTL_DIR / "onderdruk_persleiding.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config), ["TOP-011"])
    return replace(run, nulbevindingen=tuple(bevindingen))


def test_zonder_lijsten_verandert_er_niets() -> None:
    stroom = bouw_meldingenstroom(_run_onderdrukt(), RUNDATUM)

    assert sorted(m.object_uri for m in stroom.meldingen) == [VRIJVERVAL, PERSLEIDING]
    assert stroom.onderdrukking == GEEN_ONDERDRUKKING
    assert not stroom.onderdrukking.actief
    assert bouw_meldingen(_run_onderdrukt(), RUNDATUM) == stroom.meldingen


def test_onderdrukking_per_klasse_haalt_het_hoofdobject_weg_en_laat_het_tweede_object_staan() -> None:
    """De persleiding verliest haar TOP-011- en nulmetingmelding; de kruisingsmelding op de
    vrijvervalstreng, die de persleiding als object2 noemt, blijft."""
    nul = _nulbevinding(object_uri=PERSLEIDING, object_label="2", objecttype="Persleiding")
    stroom = bouw_meldingenstroom(
        _run_onderdrukt(["MechanischeTransportleiding"], [], nul), RUNDATUM
    )

    assert [m.object_uri for m in stroom.meldingen] == [VRIJVERVAL]
    assert stroom.meldingen[0].object2_uri == PERSLEIDING
    assert stroom.onderdrukking.per_klasse == {"MechanischeTransportleiding": 2}
    assert stroom.onderdrukking.per_check == {}
    assert stroom.onderdrukking.totaal == 2
    assert stroom.onderdrukking.actief
    assert stroom.onderdrukking.klassen == ("MechanischeTransportleiding",)


def test_onderdrukking_per_check_gaat_voor_en_telt_een_melding_maar_een_keer() -> None:
    """Een melding die op check én klasse zou wegvallen telt alleen bij de check."""
    stroom = bouw_meldingenstroom(
        _run_onderdrukt(["MechanischeTransportleiding"], ["TOP-011"]), RUNDATUM
    )

    assert stroom.meldingen == []
    assert stroom.onderdrukking.per_check == {"TOP-011": 2}
    assert stroom.onderdrukking.per_klasse == {}
    assert stroom.onderdrukking.totaal == 2


def test_een_melding_zonder_object_valt_nooit_op_klasse_weg() -> None:
    """Een onherleide nulmelding heeft geen hoofdobject en dus geen klasse."""
    los = _nulbevinding(object_uri="", object_label="", objecttype="", herleid=False)
    stroom = bouw_meldingenstroom(_run_onderdrukt(["Leiding"], [], los), RUNDATUM)

    assert [m.bron for m in stroom.meldingen] == ["nulmeting"]
    assert stroom.onderdrukking.per_klasse == {"Leiding": 2}


def test_onderdrukking_raakt_examined_en_systemisch_niet() -> None:
    """Een uitvoerkeuze, geen toetskeuze: de check zelf ziet de lijsten niet."""
    met = _run_onderdrukt(["MechanischeTransportleiding"], [])
    zonder = _run_onderdrukt()

    assert [o.examined for o in met.outcomes] == [o.examined for o in zonder.outcomes]
    assert [len(o.findings) for o in met.outcomes] == [len(o.findings) for o in zonder.outcomes]
    assert _is_systemisch(met.outcomes[0], met.config) == _is_systemisch(
        zonder.outcomes[0], zonder.config
    )
```

Importeer bovenaan `bouw_meldingenstroom` en `GEOEN_ONDERDRUKKING` -- let op: de naam is `GEEN_ONDERDRUKKING` -- uit `nlriochecker.uitvoer.melding`. Controleer dat de nulbevinding-helper `_nulbevinding` de sleutels `object_uri`, `object_label`, `objecttype` en `herleid` accepteert (regel 209-226; `herleid=False` met lege URI is het patroon uit `test_onherleide_nulmelding_heeft_geen_object_en_geen_gebied`). Controleer ook met `uv run python -c` of TOP-011 op deze fixture inderdaad **twee** bevindingen geeft (een per richting); geeft hij er één, meld dat in je rapport en pas de verwachte tellingen (2 → 1) in de tests aan met een regel commentaar.

3. `tests/test_gwsw_vocabulaire.py`: in `_termen_uit_config` ná het `[vulwaarden]`-blok (regel 204-207) toevoegen:

```python
    termen += [
        Term(naam, f"{herkomst} [rapport] onderdruk_klassen")
        for naam in config.rapport.onderdruk_klassen
    ]
```

en in `BRONSENTINELS` ná de regel `("configs/dewoldenhoogeveen.toml [vulwaarden]", "Maaiveldhoogte"),`:

```python
    # `checks.toml` laat de lijst leeg; alleen de projectconfig levert hier een term.
    ("configs/dewoldenhoogeveen.toml [rapport]", "MechanischeRioolleiding"),
```

- [ ] **Step 3: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_checkconfig.py tests/test_uitvoer_melding.py tests/test_gwsw_vocabulaire.py -q -x`
Expected: FAIL (ImportError op `bouw_meldingenstroom`, `AttributeError` op `onderdruk_klassen`, of de sentinel die ontbreekt).

- [ ] **Step 4: Implementeer**

1. `src/nlriochecker/checkconfig.py`, `ReportOptions`, ná `register_versie: str = "v0.9"`:

```python
    # Issue #65: meldingen die de uitvoer niet haalt. Wortelklassen (subklassen via de
    # ontologie) van het hoofdobject, en check-ID's. Een uitvoerkeuze: de checks draaien
    # ongewijzigd, `bouw_meldingenstroom` filtert en telt. De CSV draagt de lijsten niet,
    # om dezelfde reden als de CFK-set; zie BO-49.
    onderdruk_klassen: list[str] = Field(default_factory=list)
    onderdruk_checks: list[str] = Field(default_factory=list)

    @field_validator("onderdruk_checks")
    @classmethod
    def _bekende_check_ids(cls, check_ids: list[str]) -> list[str]:
        """Weigert een check-ID dat het register niet kent; dat zou stil niets onderdrukken."""
        # Lazy: `checks/base.py` importeert deze module, dus een import op moduleniveau
        # is een kringimport. Bij het valideren is het register allang geladen.
        from nlriochecker.checks import REGISTRY

        onbekend = [check_id for check_id in check_ids if check_id not in REGISTRY]
        if onbekend:
            raise ValueError(
                f"onderdruk_checks kent {', '.join(onbekend)} niet; bekende checks: "
                f"{', '.join(sorted(REGISTRY))}"
            )
        return check_ids
```

Controleer met `uv run python -c "from nlriochecker.checkconfig import load_check_config; load_check_config()"` dat de import geen kring oplevert. Levert hij er wél een (ImportError bij het laden van `nlriochecker.checks`), meld dat in je rapport en valideer dan in `load_check_config` ná `model_validate`, met dezelfde boodschap als `ConfigError`.

2. `src/nlriochecker/checks.toml`, `[rapport]`, ná `register_versie = "v0.9"`:

```toml
# Meldingen die de uitvoer niet halen (issue #65): wortelklassen van het hoofdobject
# (subklassen via de ontologie) en check-ID's. Een uitvoerkeuze, geen toetskeuze: de
# checks draaien ongewijzigd, het rapport telt wat er wegviel. Standaard leeg; De Wolden
# zet hier het mechanische riool. Zie BO-49.
onderdruk_klassen = []
onderdruk_checks = []
```

`configs/dewoldenhoogeveen.toml`, `[rapport]`, ná `register_versie = "v0.9"`:

```toml
# Meldingen die de uitvoer niet halen (issue #65): het mechanische riool, dezelfde twee
# wortels als `[klassen] mechanisch`. Het checkregister rekent mechanisch riool buiten
# scope; wat TOP-010/TOP-011 en de nulmeting er toch op melden, blijft zo uit rapport en
# kaart en wordt in de verantwoording geteld. Zie BO-49.
onderdruk_klassen = ["MechanischeRioolleiding", "MechanischeTransportleiding"]
onderdruk_checks = []
```

3. `src/nlriochecker/uitvoer/melding.py`: importeer `field` uit `dataclasses`; voeg de twee dataclasses en `GEEN_ONDERDRUKKING` uit Global Constraints toe direct ná `class Melding`. Hernoem de huidige `bouw_meldingen` naar `_alle_meldingen(run, run_datum) -> list[Melding]` (docstring: "De drie bronnen samengesteld, vóór de onderdrukking.") en voeg toe:

```python
def bouw_meldingenstroom(run: CheckRun, run_datum: date) -> Meldingenstroom:
    """Zet alle bevindingen van een run om in meldingen en past de onderdrukking toe.

    De enige plek waar bevindingen naar uitvoer vertaald worden, en de enige plek waar
    `[rapport] onderdruk_klassen` en `onderdruk_checks` gelezen worden: wat hier wegvalt
    bereikt geen enkele schrijver. Zie BO-49.
    """
    return _onderdruk(_alle_meldingen(run, run_datum), run)


def bouw_meldingen(run: CheckRun, run_datum: date) -> list[Melding]:
    """Alleen de meldingen, voor wie de telling van de onderdrukking niet nodig heeft."""
    return bouw_meldingenstroom(run, run_datum).meldingen


def _onderdruk(meldingen: list[Melding], run: CheckRun) -> Meldingenstroom:
    """Houdt de meldingen uit de stroom die `[rapport]` onderdrukt, en telt ze.

    Eerst op check-ID, dan op de klasse van het hoofdobject (`object_uri`, niet
    `object2_uri`) in de volgorde van de lijst; een melding telt hooguit een keer. Een
    melding zonder hoofdobject heeft geen klasse en valt dus nooit op klasse weg.
    """
    rapport = run.config.rapport
    checks = set(rapport.onderdruk_checks)
    per_check: dict[str, int] = {}
    per_klasse: dict[str, int] = {}
    over: list[Melding] = []
    for melding in meldingen:
        if melding.check_id in checks:
            per_check[melding.check_id] = per_check.get(melding.check_id, 0) + 1
            continue
        klasse = _onderdrukte_klasse(run, melding.object_uri, rapport.onderdruk_klassen)
        if klasse is not None:
            per_klasse[klasse] = per_klasse.get(klasse, 0) + 1
            continue
        over.append(melding)
    return Meldingenstroom(
        over,
        Onderdrukking(
            tuple(rapport.onderdruk_klassen), tuple(rapport.onderdruk_checks), per_check, per_klasse
        ),
    )


def _onderdrukte_klasse(run: CheckRun, object_uri: str, klassen: list[str]) -> str | None:
    """De eerste wortel uit de lijst waar het object onder valt, of None."""
    if not object_uri:
        return None
    return next((wortel for wortel in klassen if run.dataset.is_a(object_uri, wortel)), None)
```

Werk de moduledocstring bij: noem dat de onderdrukking hier zit. Controleer dat `Onderdrukking()` met dict-velden als frozen dataclass werkt (`field(default_factory=dict)`; vergelijking `==` volstaat, hashen is niet nodig).

- [ ] **Step 5: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_checkconfig.py tests/test_uitvoer_melding.py tests/test_gwsw_vocabulaire.py tests/test_ttl_fixtures.py -q`
Expected: alles PASS. Daarna de hele suite: `uv run pytest -q`. Een test in een ander bestand die omvalt omdat hij `[rapport]` telt of de vocabulairelijst bindt, werk je bij met een regel commentaar en verklaar je in je rapport; elke andere faal is een bug in je wijziging.

- [ ] **Step 6: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`. Faalt `ruff format --check`, draai `uv run ruff format` en herhaal.

```bash
git add scripts/maak_ttl_fixtures.py tests/fixtures/ttl/onderdruk_persleiding.ttl \
  src/nlriochecker/checkconfig.py src/nlriochecker/checks.toml configs/dewoldenhoogeveen.toml \
  src/nlriochecker/uitvoer/melding.py tests/test_checkconfig.py tests/test_uitvoer_melding.py \
  tests/test_gwsw_vocabulaire.py
git status --short
git commit -m "Onderdrukking per klasse en per check in de meldingenstroom, met telling (issue #65)"
```

---

### Task 2: Rapport, synthese, GeoPackage, JSON en documentatie

**Files:**
- Modify: `src/nlriochecker/uitvoer/schrijver.py` (drie functies), `src/nlriochecker/uitvoer/bevindingen.py:116-149, 230-253, 360-445`, `src/nlriochecker/uitvoer/synthese.py:32-44, 191-273`, `src/nlriochecker/uitvoer/gpkg.py:90-100, 167-180, 484-520, 587-611, 1352-1440`, `src/nlriochecker/uitvoer/herkomst.py:103-174`
- Modify: `tests/test_uitvoer_gpkg.py`, `tests/test_uitvoer_herkomst.py:536-563` en nieuwe tests, `tests/test_reporting.py` of `tests/test_uitvoer_rapportopbouw.py` (rapportregel), `tests/test_toetsloop.py` (synthese; helper `_draai` met `buurten_twee.gpkg`)
- Modify: `docs/json-schema.md`, `docs/architectuur.md` (Meldingenstroom en GeoPackage), `CLAUDE.md` (CSV-valkuil bij de CFK-set), `docs/beslislog.md` (BO-49), `CHANGELOG.md`

**Interfaces:**
- Consumes: `Onderdrukking`, `GEEN_ONDERDRUKKING`, `Meldingenstroom`, `bouw_meldingenstroom` uit Task 1; `run.config.rapport.onderdruk_klassen`; `run.dataset.of_class(wortel)`; `getal()` uit `nlriochecker.taal`; testhelpers `_rijen(pad, sql)` en `_laagrijen(pad, laag)` uit `tests/test_uitvoer_gpkg.py`.
- Produces: `schrijf_uitvoer(..., stroom: Meldingenstroom | None = None)` (was `meldingen`); `write_check_report(..., onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING)`; `schrijf_geopackage(..., onderdrukking=...)`; `schrijf_json(..., onderdrukking: Onderdrukking | None = None)`; `GebiedsSamenvatting.onderdrukking`; `REDEN_ONDERDRUKT`; kolommen `onderdruk_klassen`, `onderdruk_checks`, `meldingen_onderdrukt` in `gwsw_run`; JSON-veld `onderdrukt`.

- [ ] **Step 1: Schrijf de falende tests**

1. `tests/test_uitvoer_gpkg.py`, aan het einde. Bouw een run zoals in `tests/test_uitvoer_melding.py` (`_run_onderdrukt`): `onderdruk_persleiding.ttl`, check `TOP-011`, `config.rapport.onderdruk_klassen` gezet; gebruik de bestaande config-/run-helpers van dít bestand (lees regel 1-60) en schrijf met `schrijf_uitvoer(run, tmp_path, RUNDATUM, met_json=False)` zodat de GeoPackage uit de echte stroom komt. Drie tests:

```python
def test_een_onderdrukte_persleiding_is_grijs_met_de_reden(tmp_path: Path) -> None:
    """Alle meldingen weg -> grijs; en de reden is de onderdrukking, niet 'mechanisch'."""
    ...  # onderdruk_klassen = ["MechanischeTransportleiding"]
    rijen = {rij["id"]: rij for rij in _laagrijen(pad, "strengen")}
    assert rijen["L2"]["status"] == "grijs"
    assert rijen["L2"]["reden"] == REDEN_ONDERDRUKT
    assert rijen["L1"]["status"] != "grijs"
    assert rijen["L1"]["reden"] == ""


def test_een_niet_mechanische_onderdrukte_klasse_leest_grijs_en_niet_groen(tmp_path: Path) -> None:
    ...  # onderdruk_klassen = ["GemengdRiool"]: L1 valt weg, wordt grijs met REDEN_ONDERDRUKT


def test_gwsw_run_draagt_de_lijsten_en_de_telling(tmp_path: Path) -> None:
    ...  # onderdruk_klassen = ["MechanischeTransportleiding"], onderdruk_checks = []
    assert _rijen(pad, "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run") == [
        ("MechanischeTransportleiding", "", 2)
    ]
```

Controleer de kolomnaam van het objectfragment in de lagen (`id` of `object_id`; lees `_object_kolommen` of een bestaande test) en de naam van de redenkolom (`reden`). Zonder lijsten: `("", "", 0)` -- voeg die assertie aan een bestaande `gwsw_run`-test toe of als vierde test.

2. `tests/test_uitvoer_herkomst.py`: in `test_json_schemadocument_beschrijft_elk_enveloppeveld` de aanroep uitbreiden met `onderdrukking=Onderdrukking(klassen=("Leiding",), checks=("TOP-001",), per_check={"TOP-001": 1}, per_klasse={})`, zodat de drifttest het nieuwe veld dekt. Twee nieuwe tests:

```python
def test_json_zonder_onderdrukking_draagt_het_veld_niet(tmp_path: Path) -> None:
    """Optioneel en additief: een run zonder lijsten blijft byte-voor-byte gelijk (BO-49)."""
    ...  # schrijf_json zonder `onderdrukking` en met `onderdrukking=GEEN_ONDERDRUKKING`: "onderdrukt" not in document


def test_json_met_onderdrukking_draagt_de_lijsten_en_de_telling(tmp_path: Path) -> None:
    ...
    assert document["onderdrukt"] == {"klassen": ["Leiding"], "checks": ["TOP-001"], "meldingen": 1}
    assert document["schema_versie"] == "1.1"
```

3. Rapportregel — in `tests/test_uitvoer_rapportopbouw.py` (lees de helpers regel 1-70): een test die `schrijf_uitvoer` draait op de kruisingsfixture met `onderdruk_klassen = ["MechanischeTransportleiding"]`, `met_geopackage=False, met_json=False`, en in `bevindingen.md` eist: `"**2 meldingen onderdrukt**"`, `"per klasse: MechanischeTransportleiding 2"`, `"per check: geen"`. En een tweede die zonder lijsten eist dat `"onderdrukt"` niet in het rapport staat.

4. Synthese — in `tests/test_toetsloop.py` bij de tests rond `_draai("buurten_twee.gpkg", ...)`: een test die met een config met `onderdruk_klassen` gezet (kijk hoe `_draai` zijn config krijgt; voeg zo nodig een parameter toe) `schrijf_uitvoer_gebieden` draait en in `totaal/synthese.md` de regel `"meldingen onderdrukt op grond van `[rapport]`"` eist. Levert de fixture bij die klasse nul onderdrukte meldingen op, dan is de regel er toch (`actief`); assert dan op `"0 meldingen onderdrukt"`.

- [ ] **Step 2: Draai de tests en zie ze falen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py tests/test_uitvoer_herkomst.py tests/test_uitvoer_rapportopbouw.py tests/test_toetsloop.py -q -x -k "onderdruk"`
Expected: FAIL (ImportError/TypeError/AssertionError).

- [ ] **Step 3: Implementeer**

1. `schrijver.py`: importeer `GEEN_ONDERDRUKKING`, `Meldingenstroom`, `Onderdrukking`, `bouw_meldingenstroom`. In `schrijf_uitvoer`: parameter `meldingen: list[Melding] | None = None` → `stroom: Meldingenstroom | None = None`; `stroom = stroom if stroom is not None else bouw_meldingenstroom(run, run_datum)`, `meldingen = stroom.meldingen`; geef `onderdrukking=stroom.onderdrukking` door aan `write_check_report`, `schrijf_geopackage` en `schrijf_json`. In `schrijf_uitvoer_gebieden`: `stroom = bouw_meldingenstroom(...)`, `stroom=stroom` doorgeven, `meldingen=stroom.meldingen` en `onderdrukking=stroom.onderdrukking` in `GebiedsSamenvatting`. In `_schrijf_totaal`: een `Onderdrukking` voor het totaal met de lijsten uit `eerste.config.rapport` en `per_check`/`per_klasse` als som over `verzameld` (een kleine helper `_som_onderdrukking(verzameld, eerste.config.rapport) -> Onderdrukking`), doorgeven aan de totaal-JSON. Werk de moduledocstring bij (vier vormen uit één stroom, na onderdrukking).

2. `bevindingen.py`: `write_check_report(..., notities=(), *, onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING)`; doorgeven via `_render_checks` naar `_verantwoording(run, meldingen, notities, onderdrukking)`; daar het blok uit Global Constraints, alleen bij `onderdrukking.actief`. Helper `_telling(aantallen: dict[str, int]) -> str` die `"TOP-011 3, ATTR-001 2"` of `"geen"` geeft (gesorteerd op sleutel).

3. `synthese.py`: `GebiedsSamenvatting.onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING` als laatste veld; in `totaalsynthese` de regel uit Global Constraints, als `any(deel.onderdrukking.actief for deel in gebieden)`, met `N = sum(deel.onderdrukking.totaal for deel in gebieden)`.

4. `gpkg.py`: `REDEN_ONDERDRUKT` naast `REDEN_MECHANISCH` (regel 92) met een regel commentaar; `schrijf_geopackage(..., *, voortgang=..., onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING)` doorgeven tot `_schrijf_runmetadata(..., onderdrukking)`; daar de drie kolommen en waarden (`", ".join(onderdrukking.klassen)`, `", ".join(onderdrukking.checks)`, `onderdrukking.totaal`). In de objectlagenfunctie (regel ~484): `onderdrukt = _onderdrukte_uris(run)` naast `mechanisch = _mechanische_uris(run)`; `_reden_niet_beoordeeld(uri, binnen, onderdrukt, mechanisch, geen_hierarchie)` met als eerste tak `if uri in onderdrukt: return REDEN_ONDERDRUKT`; docstring aanvullen ("Onderdrukking gaat vóór mechanisch: ook een niet-mechanische onderdrukte klasse hoort grijs te lezen en niet groen; voor De Wolden vallen de twee samen."). `_onderdrukte_uris(run) -> frozenset[str]`: `frozenset(uri for wortel in run.config.rapport.onderdruk_klassen for uri in run.dataset.of_class(wortel))`.

5. `herkomst.py`: `schrijf_json(..., onderdrukking: Onderdrukking | None = None)`; het veld `onderdrukt` zoals in Global Constraints, ná `typeringspoort_toegepast` en vóór `markering`; docstringalinea erbij (optioneel, additief, `SCHEMA_VERSIE` blijft). Import `from nlriochecker.uitvoer.melding import Onderdrukking` -- controleer dat dit geen kringimport geeft (`melding.py` importeert `herkomst.py` niet).

- [ ] **Step 4: Draai de tests en zie ze slagen**

Run: `uv run pytest tests/test_uitvoer_gpkg.py tests/test_uitvoer_herkomst.py tests/test_uitvoer_rapportopbouw.py tests/test_toetsloop.py tests/test_uitvoer_melding.py -q`, daarna `uv run pytest -q`. `test_gpkg_kolommen_dekken_elk_meldingveld`, `test_geen_enkele_module_schrijft_buiten_herkomst_om` en de PyQGIS-test moeten groen blijven.

- [ ] **Step 5: Documentatie**

1. `docs/json-schema.md`: in de enveloptabel een rij ná `markering`:
   `| `onderdrukt` | object | *Optioneel.* Wat `[rapport]` in de projectconfiguratie uit de stroom hield: `klassen` (array van string, de wortelklassen), `checks` (array van string, de check-ID's) en `meldingen` (integer, hoeveel meldingen wegvielen). Het veld ontbreekt als beide lijsten leeg zijn. In `totaal/bevindingen.json` is `meldingen` de som over de gebieden, niet ontdubbeld -- net als de kolom Meldingen in de synthese. De CSV draagt de lijsten niet: de keuze hoort bij de run, niet bij de melding. |`
   En een subkop `### Over `onderdrukt`` ná `### Over `markering``: drie zinnen -- wat het is, dat de onderdrukte meldingen nergens bewaard worden (wie ze wil, draait zonder de lijsten), en dat het veld er binnen `1.1` bij kwam als optioneel en additief, net als `markering`. Voeg `onderdrukt` toe in de zin onder Versionering die `gebied`, `gebieden` en `markering` opsomt.
2. `docs/architectuur.md`, sectie "Meldingenstroom en rapport": een bullet ná het datasetsignaal-bullet: `bouw_meldingenstroom` past als laatste stap de onderdrukking uit `[rapport]` toe (`onderdruk_klassen` op het hoofdobject via `is_a`, `onderdruk_checks` op het ID), telt per check en per klasse, en geeft `Meldingenstroom` terug; wat wegvalt bereikt geen schrijver; rapport (verantwoording), synthese, `gwsw_run` en JSON-envelop dragen de telling, de CSV niet; zie BO-49. Sectie "GeoPackage en QGIS", eerste bullet: bij "Grijs betekent" toevoegen dat een object van een onderdrukte klasse grijs is met de reden `REDEN_ONDERDRUKT`, die vóór "mechanisch" gaat.
3. `CLAUDE.md`, Domein-regel over de CFK-set: zoek de zin `twee `bevindingen.csv` uit een volle en een deelrun zijn aan het bestand zelf niet te onderscheiden; lees ze naast het rapport of de JSON.` en voeg er direct achter toe: `Hetzelfde geldt voor de onderdrukking uit `[rapport]` (issue #65): een CSV met en zonder `onderdruk_klassen`/`onderdruk_checks` ziet er hetzelfde uit; de telling staat in het rapport, in `gwsw_run` en in de JSON.` (dezelfde inspringing als de omringende regels).
4. `docs/beslislog.md`, ná BO-48 (einde van het bestand):

```markdown

### BO-49 Meldingen onderdrukken per klasse en per check is een uitvoerkeuze, op één plek, met telling

**Wat.** `[rapport]` krijgt `onderdruk_klassen` (GWSW-wortelklassen; subklassen via de ontologie) en
`onderdruk_checks` (check-ID's), beide standaard leeg. `bouw_meldingenstroom` houdt ná het samenstellen
van de drie bronnen elke melding uit de stroom waarvan het check-ID op de tweede lijst staat of waarvan
het hoofdobject (`object_uri`, niet `object2_uri`) onder een klasse van de eerste valt, en telt per check
en per klasse wat wegviel. Rapport (verantwoording), `totaal/synthese.md`, `gwsw_run`
(`onderdruk_klassen`, `onderdruk_checks`, `meldingen_onderdrukt`) en de JSON-envelop (`onderdrukt`,
optioneel) dragen de telling; de CSV niet. Een object waarvan alle meldingen onderdrukt zijn wordt grijs
met de reden "meldingen onderdrukt op grond van de projectconfiguratie", die vóór "mechanisch" gaat. Een
onbekend check-ID faalt bij het laden. De Wolden onderdrukt `MechanischeRioolleiding` en
`MechanischeTransportleiding`, dezelfde wortels als `[klassen] mechanisch`. Uitgewerkt in issue #65.

**Waarom.** Het checkregister rekent mechanisch riool buiten scope, maar TOP-010, TOP-011 en de
SHACL-nulmeting melden er toch op (Koekangerveld: 17 van de 20 mechanische strengen gekleurd). De
kaartregel van BO-29 -- grijs wint niet van een gebrek -- is juist en blijft; wat weg moet is de melding
zelf, vóór hij een schrijver bereikt, anders lopen de vier uitvoervormen uit elkaar. Daarom één plek
(`bouw_meldingenstroom`) en geen filter per schrijver. Het is een uitvoerkeuze en geen toetskeuze:
`examined` en de systemisch-bepaling veranderen niet, anders zou een onderdrukte klasse de noemer van
een andere check verschuiven. De telling staat erbij omdat stilte leest als "alles gecontroleerd".

**Alternatieven.** Een CLI-vlag (verworpen: de keuze is projectgebonden en hoort reproduceerbaar in de
TOML). De checks zelf op `[klassen] mechanisch` laten filteren (verworpen: dan verdwijnt ook de
kruisingsmelding op de vrijvervalstreng, en de nulmeting filtert niet). Een kolom in de CSV (verworpen:
dezelfde reden als bij de CFK-set, BO-7). Het JSON-veld altijd schrijven (verworpen: een run zonder
lijsten blijft byte-voor-byte gelijk, zoals bij `markering`).
```

5. `CHANGELOG.md`, onder `## [Unreleased]` → `### Toegevoegd`, als **eerste** regel:

```markdown
- **Meldingen onderdrukken per klasse en per check** (issue #65). `[rapport]` krijgt
  `onderdruk_klassen` (GWSW-wortelklassen, subklassen via de ontologie) en `onderdruk_checks`
  (check-ID's; een onbekend ID faalt bij het laden). Het filter zit op één plek, in de
  meldingenstroom vóór elke schrijver, en telt per check en per klasse wat wegviel: in de
  verantwoording van het rapport, in `totaal/synthese.md`, in `gwsw_run`
  (`onderdruk_klassen`, `onderdruk_checks`, `meldingen_onderdrukt`) en als optioneel veld
  `onderdrukt` in de JSON-envelop (`schema_versie` blijft 1.1). Een object waarvan alle
  meldingen onderdrukt zijn is grijs op de kaart met die reden. De CSV draagt de lijsten niet.
  `configs/dewoldenhoogeveen.toml` onderdrukt het mechanische riool. Gemeten effect: zie BO-49.

```

- [ ] **Step 6: Mechanische poort en commit**

Run: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q`.

```bash
git add src/nlriochecker/uitvoer/schrijver.py src/nlriochecker/uitvoer/bevindingen.py \
  src/nlriochecker/uitvoer/synthese.py src/nlriochecker/uitvoer/gpkg.py src/nlriochecker/uitvoer/herkomst.py \
  tests/test_uitvoer_gpkg.py tests/test_uitvoer_herkomst.py tests/test_uitvoer_rapportopbouw.py tests/test_toetsloop.py \
  docs/json-schema.md docs/architectuur.md CLAUDE.md docs/beslislog.md CHANGELOG.md
git status --short
git commit -m "Onderdrukking in rapport, synthese, gwsw_run en JSON-envelop; grijs met reden op de kaart (issue #65)"
```

Staan er na `git status --short` nog gewijzigde testbestanden buiten deze lijst, voeg die toe vóór de commit.

---

### Task 3: Effect meten op De Wolden en Koekangerveld, vastleggen

**Files:**
- Create (niet committen; `uitvoer/` is git-ignored): `uitvoer/issue65_zonder/`, `uitvoer/issue65_met/`, `uitvoer/issue65_koekangerveld_zonder/`, `uitvoer/issue65_koekangerveld_met/`
- Create (niet committen): een scratch-kopie van de projectconfig met lege lijsten
- Modify: `docs/beslislog.md` (BO-49: alinea "Gemeten uitkomst"), `CHANGELOG.md` (getallen)

- [ ] **Step 1: Twee volledige runs, zonder en met de lijsten**

Maak een kopie van de projectconfig met de lijsten leeg: `sed 's/^onderdruk_klassen = .*/onderdruk_klassen = []/' configs/dewoldenhoogeveen.toml > uitvoer/issue65_zonder.toml` (maak `uitvoer/` eerst aan als hij ontbreekt). Draai beide runs op de **voorgrond** met `timeout` 600000 (elk ca. 2-3 minuten):

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv \
  --projectconfig uitvoer/issue65_zonder.toml \
  --bronnen data/gis_dewoldenhoogeveen \
  --output uitvoer/issue65_zonder
```

en hetzelfde met `--projectconfig configs/dewoldenhoogeveen.toml --output uitvoer/issue65_met`. Let op: `[bronnen] map` in de kopie is relatief aan de werkmap, net als in het origineel; blijft dat een probleem, gebruik dan een pad dat vanuit de repo-root klopt.

- [ ] **Step 2: Vergelijk**

```bash
uv run python - <<'EOF'
import pandas as pd, sqlite3, glob
z = pd.read_csv("uitvoer/issue65_zonder/bevindingen.csv", sep=";", keep_default_na=False)
m = pd.read_csv("uitvoer/issue65_met/bevindingen.csv", sep=";", keep_default_na=False)
print(list(z.columns))  # lees de kolomnamen voor Check en Bron
kol_check, kol_bron = "Check", "Bron"  # pas aan als de kolommen anders heten
tz = z.groupby([kol_bron, kol_check]).size(); tm = m.groupby([kol_bron, kol_check]).size()
verschil = (tz - tm.reindex(tz.index, fill_value=0))
print("totaal zonder/met:", len(z), len(m), "weggevallen:", len(z) - len(m))
print(verschil[verschil > 0].sort_values(ascending=False).to_string())
for naam in ("zonder", "met"):
    pad = glob.glob(f"uitvoer/issue65_{naam}/*.gpkg")[0]
    con = sqlite3.connect(pad)
    print(naam, "gwsw_run:", con.execute("select n_mechanisch, meldingen_onderdrukt, onderdruk_klassen from gwsw_run").fetchall())
    print(naam, "strengen status x reden:", con.execute("select status, reden, count(*) from strengen group by status, reden").fetchall())
EOF
grep -n "meldingen onderdrukt" uitvoer/issue65_met/bevindingen.md
```

Verwacht: het aantal weggevallen meldingen is gelijk aan `meldingen_onderdrukt` in `gwsw_run` én aan het getal in de verantwoording; `n_mechanisch` is in beide runs 3720 (3548 + 147 + 25, issue #56) en verandert niet; het aantal strengen met status `grijs` stijgt in de met-run met precies het aantal mechanische strengen dat in de zonder-run gekleurd was; de reden van die strengen is `REDEN_ONDERDRUKT`. Wijkt iets af, meld het getal en de richting en wat je in de data ziet; redeneer het niet weg.

- [ ] **Step 3: Koekangerveld**

Twee runs met `--studiegebied data/gis_koekangerveld/buurten.gpkg --bronnen data/gis_koekangerveld` in plaats van `--bronnen data/gis_dewoldenhoogeveen`, dezelfde twee projectconfigs, output `uitvoer/issue65_koekangerveld_zonder` en `..._met`. Tel in de submap van Koekangerveld (naam via `ls`): `select status, count(*) from strengen where reden like 'mechanisch%' or reden like 'meldingen onderdrukt%' group by status`. Verwacht: zonder 17 gekleurd van 20 mechanische strengen (de docstring van `bepaal_status`), met 0 gekleurd. Wijkt het af, meld het.

- [ ] **Step 4: Leg vast en commit**

Voeg aan BO-49 in `docs/beslislog.md` een slotalinea toe:

```markdown

**Gemeten uitkomst (2026-08-25).** Volledige toets op De Wolden en Hoogeveen met de projectconfig:
<N> meldingen onderdrukt (<N_register> uit het register, <N_nulmeting> uit de nulmeting; per check:
<top 5 met aantallen>), `n_mechanisch` blijft 3720. In de laag `strengen` gingen <K> strengen van
gekleurd naar grijs met de reden "meldingen onderdrukt". Koekangerveld: van <A> gekleurde mechanische
strengen naar <B>.
```

Vervang `Gemeten effect: zie BO-49.` in de CHANGELOG-regel door `Op De Wolden en Hoogeveen vallen zo <N> meldingen weg en gaan <K> strengen van gekleurd naar grijs (BO-49).`

```bash
git add docs/beslislog.md CHANGELOG.md
git commit -m "BO-49: gemeten effect van de onderdrukking op De Wolden en Koekangerveld (issue #65)"
```

Zet de vergelijkingstabel (per bron en per check), de statustelling en de Koekangerveld-getallen in het rapportbestand van deze taak.
