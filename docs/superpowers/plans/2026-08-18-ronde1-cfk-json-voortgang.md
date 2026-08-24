# Ronde 1 implementatieplan: CFK-keuze, JSON-export en voortgang

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `nlriochecker` krijgt een expliciete keuze van conformiteitsklassen via `--cfk` (met een luide markering bij elke afwijking), een geversioneerde JSON-export van de meldingenstroom, en zichtbare voortgang bij de zware stappen.

**Architecture:** Eén waardeobject `Meetbereik` in `meting.py` draagt de CFK-keuze; `Nulmeting` bouwt hem, `CheckRun` draagt hem voor `toets` (dat zonder nulmeting kan draaien), en de schrijvers nemen zijn tekst en velden ongewijzigd over. De JSON komt als derde schrijver in `uitvoer/herkomst.py`, gevoed door dezelfde `list[Melding]` als Markdown, CSV en GeoPackage. Voortgang is een `typing.Protocol` in een nieuwe module, met een niets-doende standaardwaarde, geïnstrumenteerd op vier ingangen en met één adapter in `cli.py`.

**Tech Stack:** Python 3.12, click, pydantic, pandas, shapely, rdflib, pytest, ruff, mypy, uv. Geen nieuwe afhankelijkheden.

**Spec:** `docs/superpowers/specs/2026-08-18-ronde1-cfk-json-voortgang-design.md`

## Global Constraints

Elke taak erft deze eisen. Ze komen uit `CLAUDE.md` en de masterinstructie.

- **Branch:** werk op `dev`. Nooit op `main`.
- **Versienummer:** blijft `0.2.0`. Nergens ophogen; uitbrengen gaat apart via `scripts/uitgave.py`.
- **Single-writer:** `src/nlriochecker/uitvoer/herkomst.py` is de enige schrijver in `src/`. Roep nergens anders `.to_csv(`, `.write_text(` of `json.dump` aan. De sweep `tests/test_uitvoer_herkomst.py::test_geen_enkele_module_schrijft_buiten_herkomst_om` bewaakt dit.
- **Geen hardcoded drempels of lijsten:** CFK-namen komen uitsluitend uit `[nulmeting] vereiste_cfk` in `src/nlriochecker/checks.toml`.
- **Geen nieuwe afhankelijkheden:** geen tqdm, geen rich. Zie je een reden, stop dan en leg de afweging voor.
- **Taal:** Nederlandse docstrings, Engelse code-identifiers. Docstring op elke publieke functie, klasse en module (ruff `D` staat niet aan, maar de codebase doet dit consequent).
- **Poort na elke taak:** `uv run ruff check`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`. Alle vier schoon. Baseline bij aanvang: 711 geslaagd, 4 gedeselecteerd.
- **`ruff format` raakt ook Markdown:** codeblokken in `docs/**.md` worden meegeformatteerd. Draai `uv run ruff format .` ná het schrijven van documentatie met Python-blokken.
- **Regellengte:** 100 tekens (`[tool.ruff] line-length = 100`).
- **Wijzigingslog:** elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in `CHANGELOG.md`.

---

## Bestandsstructuur

| Bestand | Verantwoordelijkheid | Actie |
|---|---|---|
| `src/nlriochecker/meting.py` | `Meetbereik` en `Nulmeting`; leest en valideert de SHACL-set | Wijzigen |
| `src/nlriochecker/checkconfig.py` | `[nulmeting]` verplicht maken | Wijzigen |
| `src/nlriochecker/uitvoer/herkomst.py` | `markering`-parameter en `schrijf_json` | Wijzigen |
| `src/nlriochecker/uitvoer/bevindingen.py` | `meldingen_json` naast `meldingen_tabel`; markering doorgeven | Wijzigen |
| `src/nlriochecker/uitvoer/__init__.py` | `met_json` en `Uitvoer.json` | Wijzigen |
| `src/nlriochecker/uitvoer/gpkg.py` | `cfk_set` en `volledig` in `gwsw_run`; voortgang per laag | Wijzigen |
| `src/nlriochecker/checks/base.py` | `CheckRun.meetbereik`; voortgang in `run_checks` | Wijzigen |
| `src/nlriochecker/reporting.py` | markering in de drie nulmetingrapporten | Wijzigen |
| `src/nlriochecker/comparison.py` | weigering bij ongelijke meetbereiken | Wijzigen |
| `src/nlriochecker/dataset.py` | voortgang in `load_dataset` | Wijzigen |
| `src/nlriochecker/cache.py` | voortgang doorgeven; geen fase bij een cachetreffer | Wijzigen |
| `src/nlriochecker/voortgang.py` | het protocol en `NulVoortgang` | **Nieuw** |
| `src/nlriochecker/cli.py` | `--cfk`, `--geen-json`, de balkadapter | Wijzigen |
| `docs/json-schema.md` | het JSON-contract | **Nieuw** |
| `tests/test_meting.py` | `Meetbereik` en de aangescherpte validatie | Wijzigen |
| `tests/test_uitvoer_herkomst.py` | markering, `schrijf_json`, uitgebreide sweep | Wijzigen |
| `tests/test_voortgang.py` | protocol, opnamecallback, fasevolgorde | **Nieuw** |
| `tests/test_cli.py` | `--cfk`, `--geen-json`, rooktest met de balk | Wijzigen |

---

## Task 1: `Meetbereik` als drager van de CFK-keuze

**Files:**
- Modify: `src/nlriochecker/meting.py`
- Test: `tests/test_meting.py`

**Interfaces:**
- Consumes: niets uit eerdere taken.
- Produces:
  - `Meetbereik(volledige_set: tuple[str, ...], gekozen: tuple[str, ...], gemeten: bool)`, frozen dataclass
  - `Meetbereik.van(volledige_set: Sequence[str], gekozen: Sequence[str]) -> Meetbereik` (classmethod)
  - `Meetbereik.niet_gemeten(volledige_set: Sequence[str]) -> Meetbereik` (classmethod)
  - `Meetbereik.volledig -> bool`, `.ontbreekt -> tuple[str, ...]`, `.cfk_tekst -> str` (properties)
  - `Nulmeting.meetbereik: Meetbereik` (nieuw veld, derde positie)
  - `laad_nulmeting(paden: list[Path], vereiste_cfk: list[str], volledige_cfk: list[str] | None = None) -> Nulmeting`

- [ ] **Step 1: Write the failing tests**

Voeg toe aan `tests/test_meting.py`. De bestaande import bovenaan wordt
`from nlriochecker.meting import Meetbereik, laad_nulmeting`.

```python
def test_meetbereik_op_de_volle_set_is_volledig() -> None:
    """Alle klassen gekozen betekent volledig en niets ontbrekend."""
    bereik = Meetbereik.van(VEREIST, VEREIST)

    assert bereik.volledig
    assert bereik.ontbreekt == ()
    assert bereik.cfk_tekst == "Hyd, MdsPlan, MdsProj"


def test_meetbereik_sorteert_en_ontdubbelt() -> None:
    """De schrijfwijze voor GeoPackage en JSON is vast, wat de beller ook aanlevert."""
    bereik = Meetbereik.van(["MdsProj", "Hyd", "MdsPlan"], ["MdsPlan", "Hyd", "Hyd"])

    assert bereik.gekozen == ("Hyd", "MdsPlan")
    assert bereik.volledige_set == ("Hyd", "MdsPlan", "MdsProj")


def test_meetbereik_op_een_deelset_noemt_wat_ontbreekt() -> None:
    """Een deelset is niet volledig en weet welke klassen buiten de meting vielen."""
    bereik = Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"])

    assert not bereik.volledig
    assert bereik.ontbreekt == ("MdsProj",)


def test_meetbereik_zonder_meting_is_niet_volledig() -> None:
    """Een run zonder nulmeting is een eigen toestand, geen deelset van nul klassen."""
    bereik = Meetbereik.niet_gemeten(VEREIST)

    assert not bereik.gemeten
    assert not bereik.volledig
    assert bereik.gekozen == ()
    assert bereik.cfk_tekst == ""
    assert bereik.ontbreekt == ("Hyd", "MdsPlan", "MdsProj")


def test_nulmeting_draagt_het_meetbereik(shacl_drieluik: list[Path]) -> None:
    """De volledige drieluik levert een gemeten, volledig bereik."""
    meting = laad_nulmeting(shacl_drieluik, VEREIST)

    assert meting.meetbereik.volledig
    assert meting.meetbereik.gekozen == ("Hyd", "MdsPlan", "MdsProj")


def test_nulmeting_op_een_deelset_kent_de_volle_set(mini_hyd_shacl: Path) -> None:
    """De volle set komt uit de projectconfig, niet uit wat er aangeleverd is.

    Zonder dat onderscheid kan geen rapport melden wat er ontbreekt: een deelset
    zou dan altijd 'volledig' heten.
    """
    meting = laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST)

    assert not meting.meetbereik.volledig
    assert meting.meetbereik.ontbreekt == ("MdsPlan", "MdsProj")


def test_laad_nulmeting_weigert_een_rapport_voor_een_niet_gekozen_cfk(
    shacl_drieluik: list[Path],
) -> None:
    """Een rapport buiten de gekozen set is een fout, geen stille overslag.

    Wie op een deelset toetst en per ongeluk alle rapporten meegeeft, moet dat
    horen; anders zegt de markering 'MdsProj ontbreekt' terwijl het bestand er lag.
    """
    with pytest.raises(NulmetingError, match="MdsProj"):
        laad_nulmeting(shacl_drieluik, ["Hyd", "MdsPlan"], VEREIST)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_meting.py -v`
Expected: FAIL met `ImportError: cannot import name 'Meetbereik'`.

- [ ] **Step 3: Implement `Meetbereik`**

In `src/nlriochecker/meting.py`, boven `Nulmeting`. De import bovenaan wordt uitgebreid
met `from collections.abc import Sequence`.

```python
@dataclass(frozen=True)
class Meetbereik:
    """Tegen welke conformiteitsklassen deze run getoetst is, en of dat de volle set was.

    Drie toestanden, want een run zonder nulmeting is iets anders dan een deelset:
    volledig (alle klassen uit de projectconfiguratie), deelset (een expliciete
    keuze via `--cfk`) en niet gemeten (`toets` zonder `--shacl`). Alleen deze
    klasse kent dat verschil; de schrijvers nemen de tekst en de velden over zoals
    ze hier staan, zodat Markdown, GeoPackage en JSON niet uit elkaar kunnen lopen.
    """

    volledige_set: tuple[str, ...]
    gekozen: tuple[str, ...]
    gemeten: bool

    @classmethod
    def van(cls, volledige_set: Sequence[str], gekozen: Sequence[str]) -> Meetbereik:
        """Een gemeten bereik, met beide verzamelingen gesorteerd en ontdubbeld."""
        return cls(tuple(sorted(set(volledige_set))), tuple(sorted(set(gekozen))), True)

    @classmethod
    def niet_gemeten(cls, volledige_set: Sequence[str]) -> Meetbereik:
        """Het bereik van een run zonder nulmeting: niets gekozen, niets gemeten."""
        return cls(tuple(sorted(set(volledige_set))), (), False)

    @property
    def volledig(self) -> bool:
        """Waar als er gemeten is, en op de volle set."""
        return self.gemeten and self.gekozen == self.volledige_set

    @property
    def ontbreekt(self) -> tuple[str, ...]:
        """De klassen uit de volle set waarop niet getoetst is."""
        return tuple(cfk for cfk in self.volledige_set if cfk not in self.gekozen)

    @property
    def cfk_tekst(self) -> str:
        """De gekozen set als kommagescheiden tekst, voor de GeoPackage."""
        return ", ".join(self.gekozen)
```

- [ ] **Step 4: Add the field to `Nulmeting` and build it in `laad_nulmeting`**

`Nulmeting` krijgt een derde veld, achter `reports`:

```python
    meetbereik: Meetbereik
```

`laad_nulmeting` krijgt de derde parameter en de nieuwe toets. Vervang de signatuur en
voeg de aangegeven blokken toe:

```python
def laad_nulmeting(
    paden: list[Path],
    vereiste_cfk: list[str],
    volledige_cfk: list[str] | None = None,
) -> Nulmeting:
    """Leest de SHACL-rapporten en toetst de harde eisen.

    Alle vereiste conformiteitsklassen moeten aanwezig zijn en alle rapporten
    moeten over hetzelfde RDF-bestand gaan; anders zeggen de uitkomsten niets over
    dezelfde dataset.

    `vereiste_cfk` is wat deze run eist, `volledige_cfk` wat de projectconfiguratie
    als volle set kent. Zijn ze ongelijk, dan is dit een deelset en zegt het
    `Meetbereik` dat tegen elke uitvoervorm. Zonder `volledige_cfk` gelden ze als
    gelijk, zodat bestaande aanroepen een volledig bereik houden.
    """
```

Ná de lus die `rapporten` vult, vóór de `ontbreekt`-toets:

```python
    overtollig = sorted(cfk for cfk in rapporten if cfk not in vereiste_cfk)
    if overtollig:
        bestanden = ", ".join(
            f"{cfk}={rapporten[cfk].source_file}" for cfk in overtollig
        )
        raise NulmetingError(
            f"Rapport(en) voor niet-gekozen conformiteitsklasse(n) {', '.join(overtollig)} "
            f"({bestanden}). Deze run toetst op {', '.join(vereiste_cfk)}; laat ze weg of "
            f"breid de keuze uit."
        )
```

En de slotregel wordt:

```python
    return Nulmeting(
        dataset_file=datasets.pop(),
        reports=rapporten,
        meetbereik=Meetbereik.van(volledige_cfk or vereiste_cfk, vereiste_cfk),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_meting.py -v`
Expected: PASS, alle tests uit dit bestand.

- [ ] **Step 6: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon, 711 + 7 = 718 geslaagd, 4 gedeselecteerd.

- [ ] **Step 7: Commit**

```bash
git add src/nlriochecker/meting.py tests/test_meting.py
git commit -m "Meetbereik draagt de CFK-keuze, en een rapport buiten de keuze is een fout"
```

---

## Task 2: `[nulmeting]` verplicht in de projectconfiguratie

**Files:**
- Modify: `src/nlriochecker/checkconfig.py:225-232` (`NulmetingOptions`), `:325` (`CheckConfig.nulmeting`)
- Test: `tests/test_checkconfig.py`

**Interfaces:**
- Consumes: niets.
- Produces: `CheckConfig` weigert een projectconfig zonder `[nulmeting] vereiste_cfk` met een `ConfigError`.

**Waarom:** `checkconfig.py:232` draagt `["Hyd", "MdsPlan", "MdsProj"]` een tweede keer, in
Python. Dat botst met de domeinregel dat de lijst in `checks.toml` staat. `klassen:
ClassRoots` is al verplicht zonder default; dit volgt datzelfde patroon. Veilig omdat
niemand `CheckConfig` of `NulmetingOptions` rechtstreeks construeert — alles loopt via
`load_check_config()`.

- [ ] **Step 1: Write the failing test**

Voeg toe aan `tests/test_checkconfig.py`. Kijk hoe de bestaande tests daar een tijdelijke
TOML schrijven en volg dat patroon; heeft dat bestand nog geen helper, gebruik dan
`tmp_path` zoals hieronder.

```python
def test_config_zonder_nulmetingsectie_faalt(tmp_path: Path) -> None:
    """De CFK-lijst hoort in checks.toml te staan, niet als default in Python.

    Zonder deze eis valt een projectconfig die de sectie mist stilzwijgend terug op
    drie klassen, en dan staat de lijst tweemaal opgeschreven.
    """
    basis = default_check_config_path().read_text(encoding="utf-8")
    zonder = basis.replace('vereiste_cfk = ["Hyd", "MdsPlan", "MdsProj"]', "")
    pad = tmp_path / "zonder_nulmeting.toml"
    pad.write_text(zonder, encoding="utf-8")

    with pytest.raises(ConfigError, match="vereiste_cfk"):
        load_check_config(pad)
```

Vul de imports aan met `default_check_config_path` en `ConfigError` als die er nog niet
staan.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_checkconfig.py::test_config_zonder_nulmetingsectie_faalt -v`
Expected: FAIL — `DID NOT RAISE` (de default vangt het nu op).

- [ ] **Step 3: Make both fields required**

In `NulmetingOptions`:

```python
    # Het checkregister eist dat de dataset aan alle conformiteitsklassen getoetst is;
    # welke dat zijn, hangt af van wat de GWSW-server aanbiedt. Bewust zonder default:
    # de lijst hoort in checks.toml te staan en nergens anders. Een default hier zou
    # hem een tweede keer opschrijven en een config die de sectie mist onzichtbaar
    # laten terugvallen.
    vereiste_cfk: list[str] = Field(min_length=1)
```

In `CheckConfig`, vervang `nulmeting: NulmetingOptions = Field(default_factory=NulmetingOptions)` door:

```python
    nulmeting: NulmetingOptions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checkconfig.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon. Faalt hier een andere test, dan construeert die toch een
`CheckConfig` zonder `nulmeting`; geef daar de sectie mee in plaats van de default terug
te zetten.

- [ ] **Step 6: Commit**

```bash
git add src/nlriochecker/checkconfig.py tests/test_checkconfig.py
git commit -m "De CFK-lijst staat alleen nog in checks.toml, niet als default in Python"
```

---

## Task 3: De markering in de Markdown-rapporten

**Files:**
- Modify: `src/nlriochecker/meting.py` (`Meetbereik.markering`), `src/nlriochecker/uitvoer/herkomst.py:48-62` (`schrijf_markdown`)
- Test: `tests/test_meting.py`, `tests/test_uitvoer_herkomst.py`

**Interfaces:**
- Consumes: `Meetbereik` uit Task 1.
- Produces:
  - `Meetbereik.markering() -> str | None`
  - `schrijf_markdown(pad, titel, regels, run_datum=None, markering=None) -> Path`

- [ ] **Step 1: Write the failing tests**

In `tests/test_meting.py`:

```python
def test_markering_zwijgt_bij_een_volledige_meting() -> None:
    """Volledig gemeten rapporten blijven byte-voor-byte als voorheen."""
    assert Meetbereik.van(VEREIST, VEREIST).markering() is None


def test_markering_noemt_de_deelset_en_wat_ontbreekt() -> None:
    """De lezer moet zien waarop wél en waarop níét getoetst is."""
    regel = Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"]).markering()

    assert regel == (
        "**Onvolledige meting:** getoetst op Hyd, MdsPlan; MdsProj ontbreekt."
    )


def test_markering_vervoegt_bij_meer_dan_een_ontbrekende_klasse() -> None:
    """'MdsPlan, MdsProj ontbreken', niet 'ontbreekt'."""
    regel = Meetbereik.van(VEREIST, ["Hyd"]).markering()

    assert regel is not None
    assert regel.endswith("MdsPlan, MdsProj ontbreken.")


def test_markering_onderscheidt_een_run_zonder_nulmeting() -> None:
    """Niet gemeten is een andere boodschap dan een deelset."""
    regel = Meetbereik.niet_gemeten(VEREIST).markering()

    assert regel is not None
    assert regel.startswith("**Geen nulmeting:**")
    assert "typeringspoort" in regel
```

In `tests/test_uitvoer_herkomst.py`:

```python
def test_schrijf_markdown_zet_de_markering_onder_de_herkomst(tmp_path: Path) -> None:
    """De markering staat boven de romp, zodat geen lezer hem kan missen."""
    pad = schrijf_markdown(
        tmp_path / "r.md",
        "# Titel",
        ["## Kop"],
        RUNDATUM,
        markering="**Onvolledige meting:** getoetst op Hyd; MdsPlan ontbreekt.",
    )

    assert pad.read_text(encoding="utf-8").splitlines() == [
        "# Titel",
        "",
        herkomstregel(RUNDATUM),
        "",
        "**Onvolledige meting:** getoetst op Hyd; MdsPlan ontbreekt.",
        "",
        "## Kop",
    ]


def test_schrijf_markdown_zonder_markering_blijft_ongewijzigd(tmp_path: Path) -> None:
    """Zonder markering is de kop exact als voorheen: geen lege regel erbij."""
    pad = schrijf_markdown(tmp_path / "r.md", "# Titel", ["## Kop"], RUNDATUM)

    assert pad.read_text(encoding="utf-8").splitlines() == [
        "# Titel",
        "",
        herkomstregel(RUNDATUM),
        "",
        "## Kop",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_meting.py -k markering tests/test_uitvoer_herkomst.py -k markering -v`
Expected: FAIL — `AttributeError: 'Meetbereik' object has no attribute 'markering'` en
`TypeError: unexpected keyword argument 'markering'`.

- [ ] **Step 3: Implement `Meetbereik.markering`**

In `meting.py`, als methode op `Meetbereik`. Voeg bovenaan
`from nlriochecker.taal import vorm` toe.

```python
    def markering(self) -> str | None:
        """De waarschuwingsregel voor de rapporten, of None als er niets te melden is.

        Deze ene plek bepaalt de tekst voor alle uitvoervormen. Zou elke schrijver
        hem zelf samenstellen, dan zeggen Markdown en JSON op een dag iets anders
        over dezelfde run.
        """
        if self.volledig:
            return None
        if not self.gemeten:
            return (
                "**Geen nulmeting:** deze run is niet tegen de conformiteitsklassen "
                "getoetst; de typeringspoort is niet toegepast."
            )
        ontbreekt = ", ".join(self.ontbreekt)
        return (
            f"**Onvolledige meting:** getoetst op {self.cfk_tekst}; {ontbreekt} "
            f"{vorm(len(self.ontbreekt), 'ontbreekt', 'ontbreken')}."
        )
```

- [ ] **Step 4: Add the parameter to `schrijf_markdown`**

```python
def schrijf_markdown(
    pad: Path,
    titel: str,
    regels: list[str],
    run_datum: date | None = None,
    markering: str | None = None,
) -> Path:
    """Schrijft een Markdown-rapport als titel, herkomstregel en de meegegeven regels.

    De renderers leveren alleen de romp; de kop komt hiervandaan. Zo kan geen
    rapport zonder herkomst het bestand halen doordat een schrijver de kop vergeet.

    `markering` is de plek voor een voorbehoud dat de hele run raakt, zoals een
    meting op een deelverzameling conformiteitsklassen. Hij staat hier en niet in de
    romp, zodat geen enkel rapport hem kan overslaan.
    """
    kop = [titel, "", herkomstregel(run_datum), ""]
    if markering:
        kop += [markering, ""]
    pad.write_text("\n".join([*kop, *regels]) + "\n", encoding="utf-8")
    return pad
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_meting.py tests/test_uitvoer_herkomst.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 7: Commit**

```bash
git add src/nlriochecker/meting.py src/nlriochecker/uitvoer/herkomst.py tests/
git commit -m "Elk rapport kan een runbreed voorbehoud onder de herkomstregel dragen"
```

---

## Task 4: `CheckRun` draagt het meetbereik, de GeoPackage schrijft het weg

**Files:**
- Modify: `src/nlriochecker/checks/base.py:163-180` (`CheckRun`), `src/nlriochecker/uitvoer/gpkg.py:720-786` (`_schrijf_runmetadata`), `src/nlriochecker/uitvoer/bevindingen.py:79-84` (`write_check_report`)
- Test: `tests/test_uitvoer_gpkg.py`

**Interfaces:**
- Consumes: `Meetbereik` uit Task 1, `Meetbereik.markering()` uit Task 3, `schrijf_markdown(markering=...)` uit Task 3.
- Produces:
  - `CheckRun.meetbereik: Meetbereik | None = None` (nieuw veld, achter `analyseset`, vóór `_binnen`)
  - `gwsw_run` heeft de kolommen `cfk_set` (text) en `volledig` (integer), achter `dataset_objecten`
  - `write_check_report` geeft de markering door aan `schrijf_markdown`

**Let op:** `CheckRun._binnen` is het laatste veld en heeft `field(default=None, compare=False, repr=False)`. Zet `meetbereik` ervóór, anders verschuift de positionele volgorde van `_binnen`.

- [ ] **Step 1: Write the failing test**

In `tests/test_uitvoer_gpkg.py`. Kijk eerst hoe de bestaande tests daar een `CheckRun`
opbouwen en een verbinding openen; volg dat patroon. Het idee:

```python
def test_runmetadata_noemt_de_cfk_set_en_of_die_volledig_is(tmp_path: Path) -> None:
    """De CFK-set hoort bij de run, dus in gwsw_run en niet op elke melding."""
    run = _toetsrun()  # bestaande helper in dit bestand
    run = replace(run, meetbereik=Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"]))
    meldingen = bouw_meldingen(run, RUNDATUM)

    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        rijen = verbinding.execute("select cfk_set, volledig from gwsw_run").fetchall()
    finally:
        verbinding.close()
    assert rijen == [("Hyd, MdsPlan", 0)]


def test_runmetadata_zonder_meetbereik_laat_de_velden_leeg(tmp_path: Path) -> None:
    """Een run zonder nulmeting beweert niet dat hij volledig gemeten is."""
    run = _toetsrun()
    meldingen = bouw_meldingen(run, RUNDATUM)

    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        rijen = verbinding.execute("select cfk_set, volledig from gwsw_run").fetchall()
    finally:
        verbinding.close()
    assert rijen == [("", 0)]
```

Gebruik `from dataclasses import replace` en importeer `Meetbereik`. Bestaat er geen
`_toetsrun`-helper, bouw de run dan zoals de andere tests in dat bestand dat doen.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -k cfk_set -v`
Expected: FAIL — `TypeError: got an unexpected keyword argument 'meetbereik'`.

- [ ] **Step 3: Add the field to `CheckRun`**

In `src/nlriochecker/checks/base.py`, tussen `analyseset` en `_binnen`:

```python
    # Tegen welke conformiteitsklassen deze run getoetst is. None betekent: nog niet
    # vastgesteld. De uitvoerlaag heeft het nodig voor de markering en voor
    # `gwsw_run`; het hier meegeven is minder broos dan het langs elke schrijver
    # doorreiken -- dezelfde reden waarom `config` en `analyseset` hier staan.
    meetbereik: Meetbereik | None = None
```

Voeg de import toe: `from nlriochecker.meting import Meetbereik`. **Controleer op een
kringverwijzing:** importeert `meting.py` iets uit `checks/`? Nee — `meting.py` importeert
alleen `errors` en `shaclrapport`. Draai na deze stap `uv run python -c "import
nlriochecker.cli"` om dat te bevestigen.

- [ ] **Step 4: Write the two columns in `_schrijf_runmetadata`**

Voeg achter `_Kolom("dataset_objecten", "integer")` toe:

```python
        _Kolom("cfk_set", "text"),
        _Kolom("volledig", "integer"),
```

En achter `stel.volledig_aantal if stel is not None else None,` in de waardetupel:

```python
            run.meetbereik.cfk_tekst if run.meetbereik is not None else "",
            int(run.meetbereik.volledig) if run.meetbereik is not None else 0,
```

- [ ] **Step 5: Pass the markering through `write_check_report`**

In `src/nlriochecker/uitvoer/bevindingen.py`, de `schrijf_markdown`-aanroep:

```python
    markdown_path = schrijf_markdown(
        Path(output_dir) / FILE_CHECKS_MARKDOWN,
        f"# Checkbevindingen {run.dataset.source.name}",
        _render_checks(run, meldingen),
        run_datum,
        markering=run.meetbereik.markering() if run.meetbereik is not None else None,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_uitvoer_gpkg.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 8: Commit**

```bash
git add src/nlriochecker/checks/base.py src/nlriochecker/uitvoer/ tests/test_uitvoer_gpkg.py
git commit -m "De toetsrun draagt zijn CFK-set naar rapport en GeoPackage"
```

---

## Task 5: De markering in de drie nulmetingrapporten

**Files:**
- Modify: `src/nlriochecker/reporting.py:47-55` (`write_markdown`) en de Markdown-schrijvers van `write_coverage_report` en `write_comparison_reports`
- Test: `tests/test_reporting.py`

**Interfaces:**
- Consumes: `Nulmeting.meetbereik` uit Task 1, `Meetbereik.markering()` uit Task 3.
- Produces: `samenvatting.md`, `dekking.md` en `vergelijking.md` dragen de markering bij een deelset.

**Waarom dit zonder signatuurwijziging kan:** `MetingAnalysis` draagt `meting`, en die
draagt nu `meetbereik`. Elke Markdown-schrijver in `reporting.py` kan er dus zelf bij
zonder dat een beller iets extra doorgeeft. `CoverageResult` en `MetingComparison`:
controleer welk pad daar naar de analyse loopt en gebruik dat. Ontbreekt zo'n pad, voeg
dan een veld `meetbereik: Meetbereik` toe aan het resultaatobject en vul het in de
bouwfunctie — geen los argument door de schrijversketen.

- [ ] **Step 1: Write the failing test**

```python
def test_samenvatting_markeert_een_deelmeting(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    """Een deelset staat boven het rapport, niet ergens in een voetnoot."""
    analyse = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))

    pad = write_markdown(analyse, tmp_path)

    regels = pad.read_text(encoding="utf-8").splitlines()
    assert regels[4].startswith("**Onvolledige meting:**")
    assert "MdsPlan, MdsProj ontbreken" in regels[4]


def test_samenvatting_van_een_volledige_meting_draagt_geen_markering(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """Zonder deelset blijft het rapport byte-voor-byte als voorheen."""
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))

    pad = write_markdown(analyse, tmp_path)

    assert "Onvolledige meting" not in pad.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting.py -k deelmeting -v`
Expected: FAIL — `IndexError` of een regel die niet met `**Onvolledige meting:**` begint.

- [ ] **Step 3: Pass the markering in all three writers**

In `write_markdown`:

```python
    return schrijf_markdown(
        target,
        titel,
        _render_markdown(analyse, coverage),
        markering=analyse.meting.meetbereik.markering(),
    )
```

Doe hetzelfde in de Markdown-schrijvers van `write_coverage_report` en
`write_comparison_reports`. Bij de vergelijking is er één meetbereik, want Task 6 weigert
ongelijke sets; gebruik dat van het latere meetmoment en laat een commentaarregel zeggen
dat de twee per Task 6 gelijk zijn.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 6: Commit**

```bash
git add src/nlriochecker/reporting.py tests/test_reporting.py
git commit -m "De nulmetingrapporten melden het bovenaan als er op een deelset getoetst is"
```

---

## Task 6: `vergelijk` weigert ongelijke meetbereiken

**Files:**
- Modify: `src/nlriochecker/comparison.py:73-91` (`compare_metingen`)
- Test: `tests/test_comparison.py`

**Interfaces:**
- Consumes: `Nulmeting.meetbereik` uit Task 1.
- Produces: `compare_metingen` werpt `ComparisonError` als de twee meetbereiken verschillen. Geen signatuurwijziging.

- [ ] **Step 1: Write the failing test**

```python
def test_vergelijk_weigert_ongelijke_cfk_sets(
    shacl_drieluik: list[Path], mini_hyd_shacl: Path
) -> None:
    """Een daling die uit een kleinere getoetste set komt is geen verbetering.

    Zonder deze weigering leest een trendrapport als vooruitgang terwijl er alleen
    minder gemeten is.
    """
    eerder = analyze(laad_nulmeting(shacl_drieluik, VEREIST))
    later = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))

    with pytest.raises(ComparisonError, match="Hyd, MdsPlan, MdsProj"):
        compare_metingen(eerder, later, load_coverage_config())


def test_vergelijk_slaagt_bij_gelijke_deelsets(
    mini_hyd_shacl: Path, tmp_path: Path
) -> None:
    """Twee deelmetingen op dezelfde set zijn wel te vergelijken."""
    eerder = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))
    later = analyze(laad_nulmeting(_later([mini_hyd_shacl], tmp_path), ["Hyd"], VEREIST))

    vergelijking = compare_metingen(eerder, later, load_coverage_config())

    assert [item.cfk for item in vergelijking.per_cfk] == ["Hyd"]
```

`_later` is de bestaande helper in `tests/test_comparison.py`; controleer zijn signatuur
en pas de aanroep daarop aan.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_comparison.py -k cfk_sets -v`
Expected: FAIL — `DID NOT RAISE ComparisonError`.

- [ ] **Step 3: Add the refusal**

Direct ná de datasettoets in `compare_metingen`, vóór de `gedeeld`-berekening:

```python
    if earlier.meting.meetbereik.gekozen != later.meting.meetbereik.gekozen:
        raise ComparisonError(
            f"De nulmetingen zijn op verschillende conformiteitsklassen getoetst: "
            f"{', '.join(earlier.meting.meetbereik.gekozen)} tegenover "
            f"{', '.join(later.meting.meetbereik.gekozen)}. Een verschil in het aantal "
            f"meldingen zegt dan niets over de dataset, alleen over wat er gemeten is. "
            f"Toets beide meetmomenten op dezelfde set."
        )
```

Geen forceer-vlag: de vergelijking zou onjuist zijn, niet onzeker.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_comparison.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 6: Commit**

```bash
git add src/nlriochecker/comparison.py tests/test_comparison.py
git commit -m "Vergelijken van twee ongelijk gemeten nulmetingen wordt geweigerd"
```

---

## Task 7: `--cfk` op de vier commando's

**Files:**
- Modify: `src/nlriochecker/cli.py` (nieuwe `_cfk_option` en `_gekozen_cfk`; `analyze_command`, `coverage_command`, `compare_command`, `check_command`, `_laad_meting`, `_typing_gate`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: alles uit Tasks 1, 3, 4, 5, 6.
- Produces:
  - `_cfk_option()` decorator, parameternaam `cfk_keuze: tuple[str, ...]`
  - `_gekozen_cfk(cfk_keuze: tuple[str, ...], config: CheckConfig) -> list[str]`
  - `toets` zet `CheckRun.meetbereik` via `dataclasses.replace`

- [ ] **Step 1: Write the failing tests**

```python
def test_toets_met_cfk_deelset_markeert_het_rapport(tmp_path: Path, mini_hyd_shacl: Path) -> None:
    """Een deelsetrun zegt het in het rapport, niet alleen op de opdrachtregel."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset", str(TTL_DIR / "schoon.ttl"),
            "--shacl", str(mini_hyd_shacl),
            "--cfk", "Hyd",
            "--geen-cache",
            "--output", str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_CHECKS_MARKDOWN).read_text(encoding="utf-8")
    assert "**Onvolledige meting:** getoetst op Hyd;" in tekst


def test_toets_zonder_shacl_meldt_dat_er_niet_gemeten_is(tmp_path: Path) -> None:
    """Stilte mag niet lezen als 'alles gecontroleerd'."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset", str(TTL_DIR / "schoon.ttl"),
            "--geen-cache",
            "--output", str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_CHECKS_MARKDOWN).read_text(encoding="utf-8")
    assert "**Geen nulmeting:**" in tekst


def test_cfk_met_onbekende_waarde_somt_de_toegestane_op(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """Een typefout hoort de lijst te tonen in plaats van stil een lege set te maken."""
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer", *_shacl_args(shacl_drieluik),
            "--cfk", "Hydro",
            "--output", str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "Hydro" in resultaat.output
    assert "Hyd, MdsPlan, MdsProj" in resultaat.output


def test_cfk_deelset_weigert_een_rapport_buiten_de_keuze(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """Alle drie meegeven bij --cfk Hyd is een fout, geen stille overslag."""
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer", *_shacl_args(shacl_drieluik),
            "--cfk", "Hyd",
            "--output", str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "MdsPlan" in resultaat.output


def test_analyseer_zonder_cfk_gedraagt_zich_als_voorheen(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """De standaardrun verandert niet: geen markering, alle drie vereist."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["analyseer", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_MARKDOWN).read_text(encoding="utf-8")
    assert "Onvolledige meting" not in tekst
    assert "Geen nulmeting" not in tekst
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -k cfk -v`
Expected: FAIL — `no such option: --cfk`.

- [ ] **Step 3: Add the option and the resolver**

In `cli.py`, bij de andere `_*_option`-helpers:

```python
def _cfk_option():
    """Bouwt de optie voor een deelverzameling conformiteitsklassen."""
    return click.option(
        "--cfk",
        "cfk_keuze",
        multiple=True,
        help=(
            "Conformiteitsklasse om op te toetsen; meermaals toegestaan. Zonder deze optie "
            "gelden alle klassen uit de projectconfiguratie en is een ontbrekend rapport "
            "een fout. Een deelset wordt in alle uitvoervormen gemarkeerd."
        ),
    )


def _gekozen_cfk(cfk_keuze: tuple[str, ...], config: CheckConfig) -> list[str]:
    """Toetst de opgegeven conformiteitsklassen tegen de projectconfiguratie.

    Geen `click.Choice`: de toegestane waarden staan pas vast nadat
    `--projectconfig` gelezen is, en `click.Choice` moet ze al kennen bij het
    opbouwen van het commando.
    """
    volledig = config.nulmeting.vereiste_cfk
    if not cfk_keuze:
        return list(volledig)
    onbekend = sorted({keuze for keuze in cfk_keuze if keuze not in volledig})
    if onbekend:
        raise _CliError(
            f"Onbekende conformiteitsklasse(n): {', '.join(onbekend)}. "
            f"Toegestaan: {', '.join(volledig)}."
        )
    return sorted(set(cfk_keuze))
```

Voeg `from nlriochecker.checkconfig import CheckConfig, load_check_config` toe aan de
imports.

- [ ] **Step 4: Thread it through the four commands**

`_laad_meting` krijgt de keuze mee:

```python
def _laad_meting(shacl_paths, project_config_path, dataset_path, ontology_paths, cfk_keuze=()):
    """Leest de nulmeting en optioneel de dataset, en analyseert ze."""
    project = load_check_config(project_config_path)
    gekozen = _gekozen_cfk(cfk_keuze, project)
    nulmeting = laad_nulmeting(list(shacl_paths), gekozen, project.nulmeting.vereiste_cfk)
    dataset = load_dataset(dataset_path, list(ontology_paths)) if dataset_path is not None else None
    return project, nulmeting, analyze(nulmeting, dataset), dataset
```

- Hang `@_cfk_option()` aan `analyze_command`, `coverage_command`, `compare_command` en
  `check_command`, en voeg `cfk_keuze: tuple[str, ...]` aan elke signatuur toe.
- `analyze_command` en `coverage_command`: geef `cfk_keuze` door aan `_laad_meting`.
- `compare_command`: bereken `gekozen = _gekozen_cfk(cfk_keuze, project)` en geef die met
  `project.nulmeting.vereiste_cfk` aan beide `laad_nulmeting`-aanroepen.
- `_typing_gate` krijgt `cfk_keuze` mee en geeft een derde waarde terug:

```python
def _typing_gate(
    shacl_paths: tuple[Path, ...],
    config: CheckConfig,
    dataset: GwswDataset,
    cfk_keuze: tuple[str, ...],
) -> tuple[frozenset[str], bool, Meetbereik]:
    """Haalt de te globaal getypeerde objecten uit de nulmeting.

    De SHACL-meting noemt de te globale klassen; de instanties komen uit de dataset.
    Dat geeft een exacte verzameling in plaats van een labellijst.

    Zonder `--shacl` is er geen meting. Het meetbereik zegt dat dan expliciet, in
    plaats van de vereiste set te noemen alsof die gehaald is.
    """
    volledig = config.nulmeting.vereiste_cfk
    if not shacl_paths:
        return frozenset(), False, Meetbereik.niet_gemeten(volledig)

    nulmeting = laad_nulmeting(list(shacl_paths), _gekozen_cfk(cfk_keuze, config), volledig)
    analyse = analyze(nulmeting, dataset)
    objecten: set[str] = set()
    for deel in analyse.per_cfk.values():
        objecten.update(deel.typing_gate.objects)
    return frozenset(objecten), True, nulmeting.meetbereik
```

- In `check_command`: `onbetrouwbaar, gate_applied, meetbereik = _typing_gate(shacl_paths,
  config, dataset, cfk_keuze)`, en ná de `run_checks`- en `beperk_tot_studiegebied`-stappen:

```python
        run = replace(run, meetbereik=meetbereik)
```

Voeg `from dataclasses import replace` en `from nlriochecker.meting import Meetbereik,
laad_nulmeting` toe. **Let op de volgorde:** `replace` moet ná
`beperk_tot_studiegebied`, want die bouwt een nieuwe `CheckRun`; controleer of hij alle
velden overneemt en vul `meetbereik` daar aan als hij dat niet doet.

- Voeg aan de CLI-uitvoer van `check_command` een regel toe bij een afwijkend bereik:

```python
    if not run.meetbereik.volledig:
        click.echo(f"  {run.meetbereik.markering()}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 7: Commit**

```bash
git add src/nlriochecker/cli.py tests/test_cli.py
git commit -m "CLI-optie --cfk: toetsen op een deelverzameling conformiteitsklassen"
```

---

## Task 8: `schrijf_json` en `meldingen_json`

**Files:**
- Modify: `src/nlriochecker/uitvoer/herkomst.py`, `src/nlriochecker/uitvoer/bevindingen.py`
- Test: `tests/test_uitvoer_herkomst.py`

**Interfaces:**
- Consumes: `Melding` uit `uitvoer/melding.py`, `gereedschap()` uit `herkomst.py`.
- Produces:
  - `SCHEMA_VERSIE: str = "1.0"` in `herkomst.py`
  - `schrijf_json(pad: Path, meldingen: list[dict[str, object]], *, run_datum: date, dataset: str, cfk_set: list[str], volledig: bool) -> Path`
  - `meldingen_json(meldingen: list[Melding]) -> list[dict[str, object]]` in `bevindingen.py`
  - `FILE_CHECKS_JSON = "bevindingen.json"` in `bevindingen.py`

**Waarom deze splitsing:** exact zoals `schrijf_csv` een DataFrame krijgt die
`meldingen_tabel` bouwt. De omzetting `Melding -> dict` hoort bij de meldingenlaag, het
schrijven bij de herkomstlaag.

- [ ] **Step 1: Write the failing tests**

```python
def test_meldingen_json_spiegelt_de_dataclass(toets: CheckRun) -> None:
    """Elk veld van Melding komt in de JSON terug, met dezelfde naam.

    De rijen komen uit `dataclasses.asdict` en niet uit een lijst met de hand
    opgeschreven veldnamen: die zou stilzwijgend achterlopen zodra Melding een veld
    krijgt.
    """
    meldingen = bouw_meldingen(toets, RUNDATUM)

    rijen = meldingen_json(meldingen)

    assert {veld.name for veld in fields(Melding)} == set(rijen[0])


def test_meldingen_json_zet_de_foutlocatie_als_coordinatenpaar(toets: CheckRun) -> None:
    """[x, y] in EPSG:28992, of null; er wordt niet geherprojecteerd."""
    meldingen = bouw_meldingen(toets, RUNDATUM)

    rijen = meldingen_json(meldingen)

    for melding, rij in zip(meldingen, rijen, strict=True):
        if melding.foutlocatie is None:
            assert rij["foutlocatie"] is None
        else:
            assert rij["foutlocatie"] == [melding.foutlocatie.x, melding.foutlocatie.y]


def test_schrijf_json_draagt_de_envelop(tmp_path: Path) -> None:
    """Herkomst, schemaversie en CFK-set horen bij de run, niet bij een melding."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "b"}, {"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="dewolden.ttl",
        cfk_set=["Hyd", "MdsPlan"],
        volledig=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert document["schema_versie"] == "1.0"
    assert document["gereedschap"] == gereedschap()
    assert document["run_datum"] == "2026-08-17"
    assert document["dataset"] == "dewolden.ttl"
    assert document["cfk_set"] == ["Hyd", "MdsPlan"]
    assert document["volledig"] is False
    assert document["aantal_meldingen"] == 2


def test_schrijf_json_sorteert_op_melding_id(tmp_path: Path) -> None:
    """Twee runs op dezelfde data geven een diffbaar bestand."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "b"}, {"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert [rij["melding_id"] for rij in document["meldingen"]] == ["a", "b"]


def test_schrijf_json_reserveert_voorstel_zonder_het_te_schrijven(tmp_path: Path) -> None:
    """Fase B is buiten scope; een altijd-null veld zou een belofte zijn."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    assert "voorstel" not in pad.read_text(encoding="utf-8")


def test_schrijf_json_is_leesbaar_utf8(tmp_path: Path) -> None:
    """Geen \\uXXXX-ontsnappingen en twee spaties inspringen, voor inspectie met het oog."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "a", "object_label": "Rioolstraat Zuidwolde één"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    tekst = pad.read_text(encoding="utf-8")
    assert "Zuidwolde één" in tekst
    assert '\n  "schema_versie"' in tekst
    assert tekst.endswith("\n")
```

Vul de imports aan: `import json`, `from dataclasses import fields`,
`from nlriochecker.uitvoer.melding import Melding, bouw_meldingen`,
`from nlriochecker.uitvoer.bevindingen import meldingen_json`, en `schrijf_json` bij de
bestaande `herkomst`-import.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_uitvoer_herkomst.py -k json -v`
Expected: FAIL — `ImportError: cannot import name 'schrijf_json'`.

- [ ] **Step 3: Implement `schrijf_json`**

In `src/nlriochecker/uitvoer/herkomst.py`, met `import json` bovenaan. Werk ook de
moduledocstring bij: hij noemt nu "de drie uitvoervormen" en "`schrijf_csv` en
`schrijf_markdown` zijn de enige schrijvers"; dat worden er vier respectievelijk drie.

```python
# De versie van het JSON-contract, los van het versienummer van deze package. Een
# afnemer pint hierop, niet op de packageversie: de checks mogen veranderen zonder
# dat het formaat dat doet.
SCHEMA_VERSIE = "1.0"


def schrijf_json(
    pad: Path,
    meldingen: list[dict[str, object]],
    *,
    run_datum: date,
    dataset: str,
    cfk_set: list[str],
    volledig: bool,
) -> Path:
    """Schrijft de meldingenstroom als JSON, met een envelop die de run beschrijft.

    Bedoeld als stabiel contract voor een afnemer die er mutatievoorstellen uit
    afleidt. De meldingen komen kant-en-klaar binnen via `meldingen_json`; deze
    functie interpreteert geen enkel veld, precies zoals `schrijf_csv` een
    kant-en-klare tabel krijgt.

    De sortering op `melding_id` maakt twee runs op dezelfde data diffbaar. Zie
    `docs/json-schema.md` voor de veldbeschrijvingen en de versioneringsregel.
    """
    document = {
        "schema_versie": SCHEMA_VERSIE,
        "gereedschap": gereedschap(),
        "run_datum": run_datum.isoformat(),
        "dataset": dataset,
        "cfk_set": list(cfk_set),
        "volledig": volledig,
        "aantal_meldingen": len(meldingen),
        "meldingen": sorted(meldingen, key=lambda rij: str(rij["melding_id"])),
    }
    pad.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return pad
```

- [ ] **Step 4: Implement `meldingen_json`**

In `src/nlriochecker/uitvoer/bevindingen.py`, naast `meldingen_tabel`. Voeg
`from dataclasses import asdict` toe en de constante bij de twee bestaande:

```python
FILE_CHECKS_JSON = "bevindingen.json"
```

```python
def meldingen_json(meldingen: list[Melding]) -> list[dict[str, object]]:
    """Zet de meldingen om in JSON-klare rijen met dezelfde veldnamen als de dataclass.

    `asdict` in plaats van een lijst veldnamen met de hand: die zou achterlopen
    zodra `Melding` een veld krijgt, en dan mist de JSON stilzwijgend een gegeven
    dat de CSV wel heeft.

    Alleen `foutlocatie` wordt omgezet: een shapely `Point` is niet
    serialiseerbaar. Hij wordt `[x, y]` in EPSG:28992; er wordt niet
    geherprojecteerd, net als in de rest van de uitvoer.
    """
    rijen: list[dict[str, object]] = []
    for melding in meldingen:
        rij: dict[str, object] = asdict(melding)
        punt = melding.foutlocatie
        rij["foutlocatie"] = None if punt is None else [punt.x, punt.y]
        rijen.append(rij)
    return rijen
```

- [ ] **Step 5: Extend the sweep**

In `tests/test_uitvoer_herkomst.py`, breid de verboden aanroepen uit en documenteer waarom:

```python
# De schrijvers die de herkomst zouden omzeilen als een module ze rechtstreeks
# aanriep in plaats van via `uitvoer.herkomst`. `json.dump` staat erbij sinds de
# JSON-export: een tweede JSON-schrijver zou een envelop zonder herkomst en zonder
# schemaversie kunnen wegzetten, en geen test op de bestaande bestanden zou dat zien.
DIRECTE_SCHRIJVERS = (".to_csv(", ".write_text(", "json.dump")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_uitvoer_herkomst.py -v`
Expected: PASS, inclusief de sweep.

- [ ] **Step 7: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 8: Commit**

```bash
git add src/nlriochecker/uitvoer/ tests/test_uitvoer_herkomst.py
git commit -m "Derde uitvoervorm: de meldingenstroom als geversioneerde JSON"
```

---

## Task 9: De JSON in de uitvoerketen en `--geen-json`

**Files:**
- Modify: `src/nlriochecker/uitvoer/__init__.py`, `src/nlriochecker/cli.py` (`check_command`)
- Create: `docs/json-schema.md`
- Test: `tests/test_uitvoer_herkomst.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `schrijf_json`, `meldingen_json`, `FILE_CHECKS_JSON` uit Task 8; `CheckRun.meetbereik` uit Task 4.
- Produces:
  - `Uitvoer.json: Path | None`
  - `schrijf_uitvoer(run, output_dir, run_datum=None, met_geopackage=True, met_json=True) -> Uitvoer`
  - `toets` heeft `--geen-json`

- [ ] **Step 1: Write the failing tests**

In `tests/test_uitvoer_herkomst.py`:

```python
def test_schrijf_uitvoer_levert_de_json_uit_dezelfde_meldingenstroom(
    toets: CheckRun, tmp_path: Path
) -> None:
    """De vier uitvoervormen tellen hetzelfde aantal meldingen.

    Dit is de eigenschap waar de single-writer-regel voor bestaat: liepen ze uit
    elkaar, dan zou hier een verschil staan.
    """
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM)

    assert uitvoer.json is not None
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    csv = pd.read_csv(tmp_path / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    assert document["aantal_meldingen"] == len(document["meldingen"]) == len(csv)


def test_twee_identieke_runs_geven_een_identiek_json_bestand(
    toets: CheckRun, tmp_path: Path
) -> None:
    """Diffbaar tussen meetmomenten; anders is elke trendvergelijking ruis."""
    eerste = schrijf_uitvoer(toets, tmp_path / "a", RUNDATUM).json
    tweede = schrijf_uitvoer(toets, tmp_path / "b", RUNDATUM).json

    assert eerste is not None and tweede is not None
    assert eerste.read_text(encoding="utf-8") == tweede.read_text(encoding="utf-8")


def test_json_zonder_geopackage_blijft_geschreven(toets: CheckRun, tmp_path: Path) -> None:
    """De twee vlaggen staan los van elkaar."""
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_geopackage=False)

    assert uitvoer.geopackage is None
    assert uitvoer.json is not None


def test_geen_json_laat_het_bestand_weg(toets: CheckRun, tmp_path: Path) -> None:
    """Wie de JSON niet wil, houdt de andere drie."""
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_json=False)

    assert uitvoer.json is None
    assert not (tmp_path / FILE_CHECKS_JSON).exists()
    assert uitvoer.markdown.exists()
```

In `tests/test_cli.py`:

```python
def test_toets_schrijft_de_json_standaard_mee(tmp_path: Path) -> None:
    """Symmetrie met de GeoPackage: standaard erbij, uit te zetten met een vlag."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        ["toets", "--dataset", str(TTL_DIR / "schoon.ttl"), "--geen-cache",
         "--output", str(uitvoer)],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_JSON).exists()
    assert str(uitvoer / FILE_CHECKS_JSON) in resultaat.output


def test_toets_met_geen_json_laat_het_bestand_weg(tmp_path: Path) -> None:
    """De vlag doet wat hij zegt."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        ["toets", "--dataset", str(TTL_DIR / "schoon.ttl"), "--geen-cache",
         "--geen-json", "--output", str(uitvoer)],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert not (uitvoer / FILE_CHECKS_JSON).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_uitvoer_herkomst.py -k json tests/test_cli.py -k json -v`
Expected: FAIL — `AttributeError: 'Uitvoer' object has no attribute 'json'`.

- [ ] **Step 3: Extend `schrijf_uitvoer`**

In `src/nlriochecker/uitvoer/__init__.py`. Werk ook de moduledocstring bij: hij noemt nu
drie uitvoervormen.

```python
@dataclass(frozen=True)
class Uitvoer:
    """De geschreven bestanden van een toets."""

    markdown: Path
    csv: Path
    geopackage: Path | None
    json: Path | None


def schrijf_uitvoer(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    met_geopackage: bool = True,
    met_json: bool = True,
) -> Uitvoer:
    """Schrijft rapport, archief, GIS-uitvoer en JSON uit dezelfde meldingenstroom."""
    run_datum = run_datum or date.today()
    meldingen = bouw_meldingen(run, run_datum)

    markdown, csv = write_check_report(run, output_dir, run_datum, meldingen)
    geopackage = (
        schrijf_geopackage(run, meldingen, output_dir, run_datum) if met_geopackage else None
    )
    bereik = run.meetbereik
    json_pad = (
        schrijf_json(
            Path(output_dir) / FILE_CHECKS_JSON,
            meldingen_json(meldingen),
            run_datum=run_datum,
            dataset=run.dataset.source.name,
            cfk_set=list(bereik.gekozen) if bereik is not None else [],
            volledig=bereik.volledig if bereik is not None else False,
        )
        if met_json
        else None
    )
    return Uitvoer(markdown=markdown, csv=csv, geopackage=geopackage, json=json_pad)
```

Vul de imports aan met `FILE_CHECKS_JSON`, `meldingen_json` en `schrijf_json`.

**Let op:** `write_check_report` roept `prepare(output_dir)` aan; die maakt de map. De
JSON-aanroep hierna gebruikt dus een bestaande map. Verplaats de JSON nooit vóór de
Markdown zonder zelf `prepare` te roepen.

- [ ] **Step 4: Add `--geen-json` to the CLI**

In `check_command`, naast `--geen-gpkg`:

```python
@click.option(
    "--geen-json",
    "geen_json",
    is_flag=True,
    help="Sla de JSON-export over; schrijf alleen het rapport, de CSV en de GeoPackage.",
)
```

Voeg `geen_json: bool` aan de signatuur toe, geef `met_json=not geen_json` mee aan
`schrijf_uitvoer`, en meld het pad bij de andere:

```python
    if uitvoer.json is not None:
        click.echo(f"Geschreven: {uitvoer.json}")
```

- [ ] **Step 5: Write `docs/json-schema.md`**

Nieuw bestand met: doel en afnemer, het volledige voorbeeld hieronder, een tabel met per
enveloppeveld en per meldingveld een omschrijving en type, de versioneringsregel
(nieuwe optionele velden mogen binnen een versie; een verwijderd of hernoemd veld, een
gewijzigd type of een gewijzigde betekenis verhoogt het hoofdnummer), de vermelding dat
`voorstel` gereserveerd is voor fase B en nu niet geschreven wordt, en de notitie dat
`run_datum` en `dataset` bewust zowel in de envelop als op elke melding staan — de
meldingenlijst is een getrouwe spiegel van de dataclass, de envelop is de run-waarheid.

Noem ook expliciet dat `analyseer` geen JSON schrijft en waarom (dat commando kent geen
meldingenstroom).

```json
{
  "schema_versie": "1.0",
  "gereedschap": "nlriochecker 0.2.0",
  "run_datum": "2026-08-18",
  "dataset": "dewolden.ttl",
  "cfk_set": ["Hyd", "MdsPlan"],
  "volledig": false,
  "aantal_meldingen": 1,
  "meldingen": [
    {
      "melding_id": "hgt004-knp3437",
      "check_id": "HGT-004",
      "categorie": "HGT",
      "bron": "register",
      "ernst": "F",
      "dimensie": "Plausibiliteit",
      "object_uri": "http://sparql.gwsw.nl/dewolden#knp3437",
      "object_id": "knp3437",
      "object_label": "Put 3437",
      "object2_uri": "",
      "object2_id": "",
      "object2_label": "",
      "boodschap": "De binnenonderkant buis ligt boven het putdekselniveau.",
      "waarde": "12.40",
      "drempel": "11.85",
      "typering_betrouwbaar": true,
      "cluster_id": "",
      "scope": "geen_studiegebied",
      "gebied": "",
      "prioriteit": 2,
      "systemisch": false,
      "foutlocatie": [233123.45, 528901.2],
      "run_datum": "2026-08-18",
      "dataset": "dewolden.ttl"
    }
  ]
}
```

Draai daarna `uv run ruff format .` — ruff formatteert codeblokken in Markdown mee.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_uitvoer_herkomst.py tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 8: Commit**

```bash
git add src/nlriochecker/ docs/json-schema.md tests/
git commit -m "toets schrijft de JSON standaard mee, met --geen-json en een gedocumenteerd schema"
```

---

## Task 10: Het voortgangsprotocol

**Files:**
- Create: `src/nlriochecker/voortgang.py`, `tests/test_voortgang.py`

**Interfaces:**
- Consumes: niets.
- Produces:
  - `Voortgang` (`typing.Protocol`) met `start_fase(naam: str, totaal: int | None) -> None`, `stap(n: int = 1, label: str | None = None) -> None`, `einde_fase() -> None`
  - `NulVoortgang` — implementatie die niets doet
  - `NUL_VOORTGANG: Voortgang` — de standaardwaarde overal

- [ ] **Step 1: Write the failing tests**

`tests/test_voortgang.py`:

```python
"""Tests voor het voortgangsprotocol.

Voortgang is weergave. De harde eis is dat hij de uitkomst van een run nergens
raakt; de tests hier leggen vast dat de standaardwaarde niets doet en dat een
opnemer de fasen in de juiste volgorde ziet.
"""

from __future__ import annotations

from nlriochecker.voortgang import NUL_VOORTGANG, NulVoortgang, Voortgang


class Opnemer:
    """Legt vast welke fasen en stappen langskomen."""

    def __init__(self) -> None:
        self.gebeurtenissen: list[tuple[str, object, object]] = []

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Legt het begin van een fase vast."""
        self.gebeurtenissen.append(("start", naam, totaal))

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Legt een stap vast."""
        self.gebeurtenissen.append(("stap", n, label))

    def einde_fase(self) -> None:
        """Legt het einde van een fase vast."""
        self.gebeurtenissen.append(("einde", None, None))


def test_nulvoortgang_voldoet_aan_het_protocol() -> None:
    """De standaardwaarde is een geldige implementatie, niet een None-vervanger."""
    bereik: Voortgang = NUL_VOORTGANG

    bereik.start_fase("iets", 3)
    bereik.stap(2, label="TOP-001")
    bereik.einde_fase()

    assert isinstance(NUL_VOORTGANG, NulVoortgang)


def test_opnemer_voldoet_aan_het_protocol() -> None:
    """De testopnemer is structureel een Voortgang; anders bijten de tests niet."""
    opnemer: Voortgang = Opnemer()

    opnemer.start_fase("Checks", 2)
    opnemer.stap(label="TOP-001")
    opnemer.einde_fase()

    assert isinstance(opnemer, Opnemer)
    assert opnemer.gebeurtenissen == [
        ("start", "Checks", 2),
        ("stap", 1, "TOP-001"),
        ("einde", None, None),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_voortgang.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nlriochecker.voortgang'`.

- [ ] **Step 3: Write the module**

`src/nlriochecker/voortgang.py`:

```python
"""Voortgang van de zware stappen, als protocol.

De pijplijn heeft drie stappen die minuten kosten: het inlezen van de TTL's, het
draaien van de checks en het wegschrijven van de GeoPackage. Zonder terugkoppeling
is er geen verschil te zien tussen "rekent" en "hangt".

Wie deze package als library gebruikt geeft een eigen implementatie mee; de CLI
heeft er een op basis van `click.progressbar`. De standaardwaarde `NUL_VOORTGANG`
doet niets, zodat elke bestaande aanroep ongewijzigd blijft werken.

Voortgang is weergave, geen logica. Geen check leest hier state uit en geen aanroep
hier beinvloedt de uitkomst van een run. Wie hier iets aan toevoegt dat een check
kan lezen, haalt die eigenschap weg.

Wat dit protocol niet kan: voortgang binnen een enkel bestand. rdflib geeft geen
tussenstand tijdens het parsen, en het laden van de De Wolden-export is een enkele
aanroep van ruim drie minuten. De laadfase toont daarom hoeveel bestanden klaar
zijn en verzint geen percentage voor het bestand dat loopt.
"""

from __future__ import annotations

from typing import Final, Protocol


class Voortgang(Protocol):
    """Ontvangt de voortgang van een langlopende stap."""

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Begint een fase; `totaal` is None als het aantal stappen onbekend is."""
        ...

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Meldt `n` afgeronde stappen, met een label voor wat er net klaar is."""
        ...

    def einde_fase(self) -> None:
        """Sluit de lopende fase af."""
        ...


class NulVoortgang:
    """Doet niets; de standaardwaarde overal waar voortgang optioneel is."""

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Doet niets."""

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Doet niets."""

    def einde_fase(self) -> None:
        """Doet niets."""


# Een enkele instantie: hij houdt geen state en een nieuwe per aanroep maken zou
# alleen ruis zijn.
NUL_VOORTGANG: Final[Voortgang] = NulVoortgang()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_voortgang.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 6: Commit**

```bash
git add src/nlriochecker/voortgang.py tests/test_voortgang.py
git commit -m "Voortgangsprotocol met een standaardwaarde die niets doet"
```

---

## Task 11: De vier zware fasen instrumenteren

**Files:**
- Modify: `src/nlriochecker/dataset.py:568-580` (`load_dataset`), `src/nlriochecker/cache.py:155-166` (`laad_met_cache`), `src/nlriochecker/meting.py` (`laad_nulmeting`), `src/nlriochecker/checks/base.py:352-380` (`run_checks`), `src/nlriochecker/uitvoer/gpkg.py:87-116` (`schrijf_geopackage`) en `:315-341` (`_schrijf_features`)
- Test: `tests/test_voortgang.py`

**Interfaces:**
- Consumes: `Voortgang`, `NUL_VOORTGANG` uit Task 10.
- Produces: alle vijf functies krijgen een keyword-only `voortgang: Voortgang = NUL_VOORTGANG`. Fasenamen exact: `"TTL laden"`, `"SHACL-rapporten"`, `"Checks"`, `"GeoPackage"`.

- [ ] **Step 1: Write the failing tests**

Voeg toe aan `tests/test_voortgang.py`:

```python
def test_checksfase_zet_een_stap_per_check() -> None:
    """De gebruiker ziet welke check loopt, niet alleen dat er iets loopt."""
    opnemer = Opnemer()
    config = load_check_config()
    dataset = load_dataset(TTL_DIR / "schoon.ttl")

    run = run_checks(CheckContext(dataset=dataset, config=config), voortgang=opnemer)

    start = [g for g in opnemer.gebeurtenissen if g[0] == "start"]
    stappen = [g for g in opnemer.gebeurtenissen if g[0] == "stap"]
    assert start == [("start", "Checks", len(run.outcomes))]
    assert len(stappen) == len(run.outcomes)
    assert [g[2] for g in stappen] == [outcome.check_id for outcome in run.outcomes]
    assert opnemer.gebeurtenissen[-1] == ("einde", None, None)


def test_laadfase_zet_een_stap_per_bestand() -> None:
    """rdflib geeft geen tussenstand binnen een bestand; dit is wat er wel te melden is."""
    opnemer = Opnemer()

    load_dataset(TTL_DIR / "schoon.ttl", voortgang=opnemer)

    assert opnemer.gebeurtenissen[0] == ("start", "TTL laden", 1)
    assert ("stap", 1, "schoon.ttl") in opnemer.gebeurtenissen
    assert opnemer.gebeurtenissen[-1] == ("einde", None, None)


def test_shaclfase_zet_een_stap_per_rapport(shacl_drieluik: list[Path]) -> None:
    """Drie rapporten, drie stappen."""
    opnemer = Opnemer()

    laad_nulmeting(shacl_drieluik, VEREIST, voortgang=opnemer)

    assert opnemer.gebeurtenissen[0] == ("start", "SHACL-rapporten", 3)
    assert len([g for g in opnemer.gebeurtenissen if g[0] == "stap"]) == 3


def test_cachetreffer_start_geen_laadfase(tmp_path: Path) -> None:
    """Een balk die in nul seconden vol schiet liegt over waar de tijd blijft."""
    laad_met_cache(TTL_DIR / "schoon.ttl", [], tmp_path, True)
    opnemer = Opnemer()

    _, uitslag = laad_met_cache(TTL_DIR / "schoon.ttl", [], tmp_path, True, voortgang=opnemer)

    assert uitslag.bron == "cache"
    assert opnemer.gebeurtenissen == []


def test_geen_voortgang_verandert_de_uitvoerbestanden_niet(tmp_path: Path) -> None:
    """Met de standaardwaarde is de uitvoer identiek aan die zonder voortgangscode.

    De harde eis: voortgang is weergave. Zou een fase iets aan de run veranderen,
    dan zou dit bestand verschillen.
    """
    config = load_check_config()
    dataset = load_dataset(TTL_DIR / "hgt004_bob_boven_deksel.ttl")
    context = CheckContext(dataset=dataset, config=config)

    zonder = schrijf_uitvoer(run_checks(context), tmp_path / "a", RUNDATUM)
    met = schrijf_uitvoer(run_checks(context, voortgang=Opnemer()), tmp_path / "b", RUNDATUM)

    assert zonder.markdown.read_text(encoding="utf-8") == met.markdown.read_text(
        encoding="utf-8"
    )
    assert zonder.json is not None and met.json is not None
    assert zonder.json.read_text(encoding="utf-8") == met.json.read_text(encoding="utf-8")
```

Vul de imports en constanten van het testbestand aan: `TTL_DIR`, `VEREIST`, `RUNDATUM`,
`load_check_config`, `load_dataset`, `laad_met_cache`, `laad_nulmeting`, `run_checks`,
`CheckContext`, `schrijf_uitvoer`.

**Let op bij `test_geen_voortgang_verandert_de_uitvoerbestanden_niet`:** de dataset in
`hgt004_bob_boven_deksel.ttl` kan buiten de RD-grenzen liggen; de fixture `toets` in
`tests/test_uitvoer_herkomst.py` zet daarvoor `config.drempels.rd_y_min = 0.0`. Doe
hetzelfde als de test op TOP-009-bevindingen struikelt.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_voortgang.py -v`
Expected: FAIL — `TypeError: got an unexpected keyword argument 'voortgang'`.

- [ ] **Step 3: Instrument `load_dataset`**

```python
def load_dataset(
    dataset_path: Path,
    ontology_paths: list[Path] | None = None,
    fallback_encoding: str = FALLBACK_ENCODING,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> GwswDataset:
    """Leest de OroX-dataset en de ontologie(en) en bouwt het domeinmodel op.

    De voortgang gaat per bestand. rdflib geeft geen tussenstand binnen een bestand,
    en juist het parsen van de dataset is de lange stap; er wordt daarom geen
    percentage getoond dat er niet is.
    """
    dataset_path = Path(dataset_path)
    voortgang.start_fase("TTL laden", 1 + len(ontology_paths or []))
    try:
        graph, fallback = _parse(dataset_path, fallback_encoding)
        voortgang.stap(label=dataset_path.name)

        ontology = Graph()
        for pad in ontology_paths or []:
            ontology += _parse(Path(pad), fallback_encoding)[0]
            voortgang.stap(label=Path(pad).name)
    finally:
        voortgang.einde_fase()
```

De rest van de functie blijft ongewijzigd en staat ná de `try/finally`. Importeer
`from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang`.

- [ ] **Step 4: Pass it through `laad_met_cache`**

Voeg `*, voortgang: Voortgang = NUL_VOORTGANG` aan de signatuur toe en geef hem door aan
elke `load_dataset`-aanroep in die functie. Start hier zelf géén fase. Vul de docstring
aan:

```python
    """Leest de dataset uit de cache, of leest hem in en legt hem weg.

    Bij een cachetreffer wordt er niets geparseerd en start er dus geen laadfase:
    een balk die in nul seconden vol schiet zou suggereren dat het inlezen snel was
    in plaats van overgeslagen.
    """
```

- [ ] **Step 5: Instrument `laad_nulmeting`**

Signatuur wordt (bovenop Task 1):

```python
def laad_nulmeting(
    paden: list[Path],
    vereiste_cfk: list[str],
    volledige_cfk: list[str] | None = None,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> Nulmeting:
```

Zet de leeslus tussen `start_fase("SHACL-rapporten", len(paden))` en een `finally` met
`einde_fase()`, met `voortgang.stap(label=Path(pad).name)` ná elk gelezen rapport. De
`if not paden`-toets blijft vóór `start_fase`.

- [ ] **Step 6: Instrument `run_checks`**

```python
def run_checks(
    context: CheckContext,
    check_ids: list[str] | None = None,
    typing_gate_applied: bool = False,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> CheckRun:
    """Draait de gevraagde checks; zonder selectie draait de hele registry.

    De voortgang meldt per check het ID, zodat zichtbaar is welke check loopt en
    niet alleen dat er iets loopt.
    """
```

Zet de bestaande `for check_id in gekozen:`-lus tussen
`voortgang.start_fase("Checks", len(gekozen))` en een `finally` met `einde_fase()`, en
zet `voortgang.stap(label=check_id)` aan het eind van elke iteratie. De
`onbekend`-controle blijft vóór `start_fase`.

- [ ] **Step 7: Instrument the GeoPackage writer**

`schrijf_geopackage` krijgt `*, voortgang: Voortgang = NUL_VOORTGANG`. Acht stappen: de
vier featurelagen, `meldingen`, `overzicht_checks`, `gwsw_run` en `layer_styles`.

```python
    voortgang.start_fase("GeoPackage", 8)
    verbinding = sqlite3.connect(doel)
    try:
        _leg_fundament(verbinding)
        tellingen = _schrijf_features(verbinding, run, meldingen, binnen, run_datum, voortgang)
        _schrijf_meldingen(verbinding, meldingen)
        voortgang.stap(label="meldingen")
        _schrijf_overzicht(verbinding, run, meldingen)
        voortgang.stap(label="overzicht_checks")
        _schrijf_runmetadata(verbinding, run, meldingen, run_datum, tellingen)
        voortgang.stap(label="gwsw_run")
        _schrijf_stijlen(verbinding)
        voortgang.stap(label="layer_styles")
        verbinding.commit()
    finally:
        verbinding.close()
        voortgang.einde_fase()
```

`_schrijf_features` krijgt een parameter `voortgang: Voortgang` (positioneel, hij is
module-privé) en roept `voortgang.stap(label=laag)` aan het eind van elke iteratie van de
`for laag, verzameling, geometrie_veld in (...)`-lus.

- [ ] **Step 8: Pass it from `schrijf_uitvoer`**

`schrijf_uitvoer` krijgt `voortgang: Voortgang = NUL_VOORTGANG` als laatste parameter en
geeft hem door aan `schrijf_geopackage`.

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/test_voortgang.py -v`
Expected: PASS.

- [ ] **Step 10: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 11: Commit**

```bash
git add src/nlriochecker/ tests/test_voortgang.py
git commit -m "De vier zware fasen melden hun voortgang"
```

---

## Task 12: De CLI-adapter op `click.progressbar`

**Files:**
- Modify: `src/nlriochecker/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Voortgang` uit Task 10, de geïnstrumenteerde ingangen uit Task 11.
- Produces: `_BalkVoortgang` in `cli.py`; `toets` geeft hem aan `laad_met_cache`, `laad_nulmeting`, `run_checks` en `schrijf_uitvoer`.

- [ ] **Step 1: Write the failing test**

```python
def test_toets_draait_met_de_voortgangsbalk(tmp_path: Path) -> None:
    """Rooktest: de adapter mag de run niet breken, ook niet zonder terminal.

    CliRunner is geen tty; click zet de balk dan zelf uit. Er komt hier geen eigen
    TTY-toets bij, dus deze test is de enige waarborg dat de adapter in die
    omgeving niet omvalt.
    """
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        ["toets", "--dataset", str(TTL_DIR / "schoon.ttl"), "--geen-cache",
         "--output", str(uitvoer)],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_JSON).exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_toets_draait_met_de_voortgangsbalk -v`
Expected: deze test kan al slagen vóór de adapter bestaat — hij is een rooktest, geen
specificatie. Draai hem eerst en bevestig dat hij groen is; na Step 3 moet hij nog steeds
groen zijn, en dát is de waarborg. Noteer de uitkomst in beide richtingen.

- [ ] **Step 3: Write the adapter**

In `cli.py`, met `import sys` en `from typing import Any` bovenaan:

```python
class _BalkVoortgang:
    """Voortgang als `click.progressbar`, op stderr.

    De balk gaat naar stderr en niet naar stdout: daar staan de geschreven paden en
    de tellingen, en wie die doorpipet moet er geen balkresten in krijgen.

    Er komt geen eigen TTY-detectie bij; click zet de balk in een niet-interactieve
    omgeving zelf uit. Zonder bepaalbaar totaal is er geen balk te tekenen -- dan
    wordt de fasenaam een keer gemeld, want een balk met een verzonnen lengte zou
    over de resterende tijd liegen.
    """

    def __init__(self) -> None:
        # click.progressbar levert een ProgressBar uit een private module; die
        # importeren om hem te kunnen annoteren zou een privaat pad vastleggen.
        self._balk: Any | None = None

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Opent een balk voor deze fase, of meldt hem als er geen totaal is."""
        if totaal is None:
            click.echo(f"{naam}...", err=True)
            return
        self._balk = click.progressbar(length=totaal, label=naam, file=sys.stderr)
        self._balk.__enter__()

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Schuift de balk op en zet het label op wat er net klaar is."""
        if self._balk is None:
            return
        if label is not None:
            self._balk.label = label
        self._balk.update(n)

    def einde_fase(self) -> None:
        """Sluit de balk van deze fase."""
        if self._balk is None:
            return
        self._balk.__exit__(None, None, None)
        self._balk = None
```

- [ ] **Step 4: Use it in `check_command`**

Maak bovenaan de `try` één `voortgang = _BalkVoortgang()` en geef hem mee aan
`laad_met_cache`, aan `_typing_gate` (die hem doorgeeft aan `laad_nulmeting`), aan
`run_checks` en aan `schrijf_uitvoer`.

Voeg een regel toe aan de docstring van `check_command`? Nee — die is de `--help`-tekst
van het commando en beschrijft wat het doet, niet hoe het meldt. Laat hem staan.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

**Als een CLI-test hier valt op onverwachte uitvoer:** `click.progressbar` echoot in een
niet-interactieve omgeving het label één keer. Dat is bekend en voorzien. Los het op door
de betreffende test op de inhoud te laten asserteren in plaats van op exacte uitvoer, of
door de assertie te verruimen — niet door een eigen TTY-toets in te bouwen, en niet door
de balk weg te laten. Meld wat je hebt aangepast.

- [ ] **Step 6: Run the full gate**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon.

- [ ] **Step 7: Commit**

```bash
git add src/nlriochecker/cli.py tests/test_cli.py
git commit -m "CLI toont voortgang bij het laden, toetsen en wegschrijven"
```

---

## Task 13: Documentatie en afronding

**Files:**
- Modify: `CHANGELOG.md`, `README.md`, `docs/beslislog.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: alles.
- Produces: geen code.

- [ ] **Step 1: `CHANGELOG.md`**

Onder `## [Unreleased]`, in de bestaande rubrieken. Voorbeeldregels:

Onder **Toegevoegd**:
- `--cfk` op `analyseer`, `dekking`, `toets` en `vergelijk`: toetsen op een deelverzameling conformiteitsklassen. Standaard blijven alle drie vereist; elke afwijking staat als waarschuwingsregel boven elk rapport en in de GeoPackage (`cfk_set`, `volledig`).
- Een JSON-export van de meldingenstroom (`bevindingen.json`), met een envelop en een eigen `schema_versie`; uit te zetten met `--geen-json`. Het contract staat in `docs/json-schema.md`.
- Zichtbare voortgang bij het inlezen van de TTL's, het draaien van de checks, het inlezen van de SHACL-rapporten en het wegschrijven van de GeoPackage. Als library via het protocol in `voortgang.py`, op de opdrachtregel als balk op stderr.

Onder **Gewijzigd**:
- `vergelijk` weigert twee nulmetingen die op verschillende conformiteitsklassen getoetst zijn: een daling die uit een kleinere getoetste set komt is geen verbetering.
- Een SHACL-rapport voor een conformiteitsklasse buiten de gekozen set is een fout in plaats van een stille overslag.
- `[nulmeting] vereiste_cfk` is verplicht in de projectconfiguratie. De lijst stond ook als default in `checkconfig.py`; een config die de sectie miste viel daar stilzwijgend op terug.
- `toets` zonder `--shacl` meldt in het rapport dat er niet tegen de conformiteitsklassen getoetst is.

- [ ] **Step 2: `README.md`**

- `--cfk` bij de optiebeschrijving van de vier commando's, met de standaard (alle drie) en de markering bij een deelset.
- `--geen-json` bij de opties van `toets`, naast `--geen-gpkg`.
- `bevindingen.json` bij de beschrijving van de uitvoerbestanden, met een verwijzing naar `docs/json-schema.md`.
- Een regel over de voortgangsbalk en dat hij naar stderr gaat.

- [ ] **Step 3: `docs/beslislog.md`**

Vier vermeldingen, in de vorm die dat bestand al gebruikt (kijk naar de bestaande
nummering en kopstijl):

1. **CFK-versoepeling.** Het checkregister v0.8 eist toetsing op alle conformiteitsklassen. `--cfk` versoepelt dat bewust, onder één voorwaarde: elke afwijking is expliciet opgegeven én wordt in alle uitvoervormen gemarkeerd. De standaard blijft alle drie.
2. **JSON-stabiliteitscontract.** `schema_versie` staat los van de packageversie. Nieuwe optionele velden mogen binnen een hoofdversie; een verwijderd of hernoemd veld, een gewijzigd type of een gewijzigde betekenis verhoogt hem. `voorstel` is gereserveerd voor fase B en wordt nu niet geschreven.
3. **`analyseer` schrijft geen JSON.** De masterinstructie noemde het commando wel, maar de eis dat de inhoud uitsluitend uit de meldingenstroom komt sluit het uit: `analyseer` kent geen `CheckRun`. Een tweede schema of een lege meldingenlijst zouden beide het contract ondermijnen.
4. **`[nulmeting]` verplicht.** De CFK-lijst stond zowel in `checks.toml` als als pydantic-default. De default is verwijderd; een config zonder de sectie faalt nu bij het laden in plaats van onzichtbaar op drie klassen terug te vallen.

- [ ] **Step 4: `CLAUDE.md`**

Werk de eerste domeinregel bij, in dezelfde toon en dichtheid als de bestaande tekst.
Huidige tekst: "De dataset moet ALTIJD aan alle conformiteitsklassen (CFK's) getoetst
zijn: Hyd, MdsPlan EN MdsProj. Ontbreekt er een, dan faalt de pijplijn met een duidelijke
foutmelding. De lijst staat in checks.toml, niet in de code."

Nieuwe strekking: standaard alle drie en dan faalt de pijplijn bij een ontbrekend
rapport; een deelset kan alleen via `--cfk` en wordt in álle uitvoervormen gemarkeerd;
een run zonder `--shacl` meldt dat er niet gemeten is; de lijst staat uitsluitend in
`checks.toml` en is daar verplicht.

Vul de sectie Technische afspraken aan: `bevindingen.json` als vierde uitvoervorm uit
dezelfde meldingenstroom, met `docs/json-schema.md` als contract, en `voortgang.py` als
weergavelaag die de uitkomst van een run niet raakt.

- [ ] **Step 5: Run the full gate**

Run: `uv run ruff format . && uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon. (`ruff format .` eerst, want deze taak raakt Markdown met
Python-blokken.)

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md README.md docs/beslislog.md CLAUDE.md
git commit -m "Ronde 1 vastgelegd: wijzigingslog, leeswijzer, beslislog en domeinregel"
```

- [ ] **Step 7: Run the two review steps**

Zoals `CLAUDE.md` voorschrijft, in deze volgorde:

1. `/superpowers:requesting-code-review`
2. `/python-library-complete:reviewing-python-libraries`

Verwerk de bevindingen van beide vóór de afsluitende commit. Gebruik
`/superpowers:receiving-code-review` bij feedback die onduidelijk of technisch
twijfelachtig lijkt: verifieer voordat je hem doorvoert.

- [ ] **Step 8: Final gate and stop**

Run: `uv run ruff check && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: alles schoon, geen nieuw overgeslagen tests boven de bestaande drempel van 4
gedeselecteerd.

Meld daarna aan de gebruiker: ronde 1 is afgerond en gecommit, ronde 2 (rapportage per
studiegebied-feature) hoort in een NIEUWE sessie op de actuele `dev` met het
masterdocument er opnieuw bij. Begin niet aan ronde 2, ook niet met voorbereidend werk.

---

## Zelfcontrole van dit plan

**Dekking van de spec.** Elke sectie van het ontwerpdocument heeft een taak: §3.1 → Task 1;
§3.2 → Task 7; §3.3 → Task 1; §3.4 → Tasks 3, 4, 5; §3.5 → Task 4; §3.6 → Task 6;
§3.7 → Task 2; §4.1 → Task 8; §4.2 → Tasks 8, 9; §4.3 → Task 9; §4.4 → Task 9;
§5.1 → Task 10; §5.2 → Task 11; §5.3 → Task 12; §8 → Task 13. De 18 tests uit §7 van de
spec komen alle terug: 1→T4/T7, 2→T1, 3→T1, 4→T7, 5→T7, 6→T6, 7→T7, 8→T2, 9→T8, 10→T8,
11→T9, 12→T8, 13→T9, 14→T8, 15→T11, 16→T11, 17→T11, 18→T12.

**Namen die over taken heen lopen.** `Meetbereik.van`, `.niet_gemeten`, `.volledig`,
`.ontbreekt`, `.cfk_tekst`, `.markering()`; `Nulmeting.meetbereik`; `CheckRun.meetbereik`;
`schrijf_markdown(..., markering=)`; `schrijf_json(pad, meldingen, *, run_datum, dataset,
cfk_set, volledig)`; `meldingen_json`; `FILE_CHECKS_JSON`; `Uitvoer.json`;
`schrijf_uitvoer(..., met_json=)`; `Voortgang`, `NulVoortgang`, `NUL_VOORTGANG`;
`_cfk_option`, `_gekozen_cfk`, `_BalkVoortgang`. Overal dezelfde spelling gebruikt.

**Twee plekken waar de implementator moet kijken in plaats van kopiëren**, omdat het plan
de bestaande code daar niet volledig heeft uitgeschreven: het resultaatobject van
`write_coverage_report` en `write_comparison_reports` (Task 5, Step 3) en de helper
`_toetsrun` in `tests/test_uitvoer_gpkg.py` (Task 4, Step 1). Beide staan als zodanig in
de taak benoemd.
