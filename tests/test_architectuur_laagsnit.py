"""Drifttests op de laagsnit en op de bevroren leeslaag-API.

`docs/architectuur.md` belooft drie dingen over de importrichtingen in `src/`, en tot
issue #118 stonden ze alleen in proza -- net als de "één schrijver"-regel voordat
`tests/test_uitvoer_herkomst.py` haar ging bewaken:

* **a1** -- `checks/` importeert nooit `nlriochecker.uitvoer.*`. De engine levert
  bevindingen en weet niet in welke vorm ze landen.
* **a2** -- `uitvoer/` leest waardetypen uit de facade `nlriochecker.checks`; verder
  alleen wat in `MAG_UIT_CHECKSUBMODULE` staat.
* **a3** -- geen module in `src/` importeert een `_`-naam uit `gwsw_orox_helpers`. Dat is
  de bevriezing van de leeslaag-API uit `CLAUDE.md`.

De sweeps lopen over de AST en niet over regels tekst: een import in een docstring of in
een commentaarregel is geen import, en `checks/base.py` noemt `uitvoer.identiteit` in
allebei.

Wat een AST-sweep niet kan, en hier bewust niet staat: "geen module zet een attribuut op
een object uit `gwsw_orox_helpers`". Een toewijzing op een lokale variabele is statisch
niet naar de package van herkomst te herleiden, dus die helft van de bevriezing blijft
een afspraak zonder hek.

Elke sweep heeft een tegenproef op een synthetisch stukje broncode. Zonder die
tegenproef is een sweep die niets vindt niet te onderscheiden van een sweep die niets
kán vinden -- en dan staat hier een groen hek dat nooit kan afgaan.
"""

from __future__ import annotations

import ast
from pathlib import Path

BRON = Path(__file__).resolve().parents[1] / "src"
PAKKET = "nlriochecker"
LEESLAAG = "gwsw_orox_helpers"

# De bestandsnamen in `checks/`. Ze scheiden `from nlriochecker.checks import selectie`
# (de submodule zelf, dus buiten de facade om) van `from nlriochecker.checks import
# CheckRun` (een waardetype uit de facade, altijd toegestaan).
CHECKMODULES = frozenset(pad.stem for pad in (BRON / PAKKET / "checks").glob("*.py"))

# Wat een module onder `uitvoer/` uit een checksubmodule mag halen, met de reden erbij.
# De facade `nlriochecker.checks` staat er niet in: die is altijd toegestaan, want daar
# wonen de waardetypen (`CheckRun`, `Finding`, `Severity`) die de uitvoerlaag per
# definitie leest.
#
# **Deze lijst mag alleen krimpen.** Elke regel is logica die een schrijver uit de engine
# haalt, en elke regel is dus een plek waar laag en uitslag uit elkaar kunnen lopen. Wie
# hier iets toevoegt schrijft de reden erbij; wie een import overbodig maakt haalt de
# regel weg. Issue #122 heeft dat gedaan: het feitenkanaal maakte `aanwijzingen_van`
# overbodig, en daarmee verdween de regel voor `checks.randvoorzieningen` uit `gpkg.py`.
MAG_UIT_CHECKSUBMODULE: dict[str, dict[str, frozenset[str]]] = {
    "nlriochecker/uitvoer/gpkg.py": {
        # Het mechanische riool krijgt geen richtingspijl en geen beoordeelde kleuring
        # (issue #74); de schrijver heeft de rol dus zelf nodig.
        f"{PAKKET}.checks.selectie": frozenset({"mechanischeleidingen"}),
        # De laag `vlakken` joint op het trefferregister en het wegvakregister van de
        # run; dat zijn de registers zelf, geen tweede bevraging van de externe bron.
        f"{PAKKET}.checks.treffers": frozenset({"Treffer", "Wegvakoordeel"}),
        # De geometrie van een deelstelselvlak komt uit de graaf waarop de check draaide
        # -- een tweede afleiding zou een ander vlak kunnen tekenen.
        f"{PAKKET}.checks.verbanden": frozenset(
            {
                "Afvoer",
                "afvoerpad_van_streng",
                "afvoerpaden",
                "deelstelsel_ids",
                "putknopen",
                "strengen_per_knoop",
            }
        ),
    },
    "nlriochecker/uitvoer/omvang.py": {
        # De aantallen per objecttype en de klassen-op-nul lezen de registry en dezelfde
        # rollen als de checks; een eigen selectie zou andere getallen geven.
        f"{PAKKET}.checks.base": frozenset({"REGISTRY"}),
        f"{PAKKET}.checks.selectie": frozenset({"klassen_van_rol", "putten"}),
        f"{PAKKET}.checks.verbanden": frozenset({"verbonden_knopen"}),
    },
    "nlriochecker/uitvoer/bevindingen.py": {
        # De regel "Toetst <klassen> op <kenmerken>" per check leest de klassen van een
        # rol; de EXT-checks noemen daarnaast hun bronrollen.
        f"{PAKKET}.checks.extern": frozenset({"bronrollen_met_check"}),
        f"{PAKKET}.checks.selectie": frozenset({"klassen_van_rol"}),
    },
    "nlriochecker/uitvoer/synthese.py": {
        # De synthese telt de strengen in meters over dezelfde rol als de checks.
        f"{PAKKET}.checks.selectie": frozenset({"vrijvervalrioolleidingen"}),
    },
}


def _importregels(bron: str) -> list[tuple[str, tuple[str, ...]]]:
    """Elke import als (modulenaam, geimporteerde namen).

    `import a.b` levert `("a.b", ())`, `from a.b import c, d` levert
    `("a.b", ("c", "d"))`. Een relatieve import heeft geen absolute modulenaam en valt
    weg; deze codebase gebruikt er geen enkele.
    """
    regels: list[tuple[str, tuple[str, ...]]] = []
    for knoop in ast.walk(ast.parse(bron)):
        if isinstance(knoop, ast.Import):
            regels += [(alias.name, ()) for alias in knoop.names]
        elif isinstance(knoop, ast.ImportFrom) and knoop.level == 0 and knoop.module:
            regels.append((knoop.module, tuple(alias.name for alias in knoop.names)))
    return regels


def _uitvoerimports(bron: str) -> list[str]:
    """De modules uit `nlriochecker.uitvoer` die deze broncode importeert.

    Drie vormen: `import nlriochecker.uitvoer[.x]`, `from nlriochecker.uitvoer[.x] import
    …` en `from nlriochecker import uitvoer` -- die laatste noemt de uitvoerlaag als naam
    en niet als module, en ontsnapte daarmee aan de eerste versie van deze sweep.

    Wat er niet onder valt en de gedocumenteerde grens is: `import nlriochecker` gevolgd
    door `nlriochecker.uitvoer.…` als attribuut. Die vorm komt in deze codebase nergens
    voor en is statisch niet van elk ander attribuutgebruik te onderscheiden.
    """
    gevonden: list[str] = []
    for module, namen in _importregels(bron):
        if module == f"{PAKKET}.uitvoer" or module.startswith(f"{PAKKET}.uitvoer."):
            gevonden.append(module)
        elif module == PAKKET and "uitvoer" in namen:
            gevonden.append(f"{PAKKET}.uitvoer")
    return gevonden


def _checksubmodule_imports(bron: str) -> list[tuple[str, tuple[str, ...]]]:
    """De imports uit een checksubmodule; de facade `nlriochecker.checks` telt niet mee.

    Twee vormen halen de submodule als geheel binnen in plaats van een naam eruit, en
    geven daarmee toegang tot álles wat erin staat. Ze krijgen `"*"` als naam, en `"*"`
    staat in geen enkele allowlist-regel:

    * `import nlriochecker.checks.netwerk` levert nul namen, dus een sweep die de
      geïmporteerde namen tegen de allowlist houdt heeft niets te vergelijken en laat
      hem door;
    * `from nlriochecker.checks import selectie` ziet eruit als een facade-import, maar
      `selectie` is een bestand in `checks/` en geen waardetype. Wat de facade wél mag
      leveren -- `CheckRun`, `Finding`, `Severity` -- is geen bestandsnaam en blijft dus
      toegestaan.
    """
    gevonden: list[tuple[str, tuple[str, ...]]] = []
    for module, namen in _importregels(bron):
        if module.startswith(f"{PAKKET}.checks."):
            gevonden.append((module, namen or ("*",)))
        elif module == f"{PAKKET}.checks":
            gevonden += [
                (f"{PAKKET}.checks.{naam}", ("*",)) for naam in namen if naam in CHECKMODULES
            ]
    return gevonden


def _prive_leeslaagnamen(bron: str) -> list[str]:
    """De namen met een leidende `_` die deze broncode uit `gwsw_orox_helpers` haalt.

    Zowel `from gwsw_orox_helpers.dataset import _iets` als `import
    gwsw_orox_helpers._intern`: het laatste deel van de modulenaam telt ook als naam.
    """
    gevonden: list[str] = []
    for module, namen in _importregels(bron):
        if module != LEESLAAG and not module.startswith(f"{LEESLAAG}."):
            continue
        gevonden += [f"{module}.{naam}" for naam in namen if naam.startswith("_")]
        if not namen and module.rsplit(".", 1)[-1].startswith("_"):
            gevonden.append(module)
    return gevonden


def _modules(deelmap: str = "") -> list[tuple[str, str]]:
    """Elke `.py` onder `src/` (of onder een deelmap ervan) als (relatief pad, broncode)."""
    wortel = BRON / deelmap if deelmap else BRON
    return [
        (pad.relative_to(BRON).as_posix(), pad.read_text(encoding="utf-8"))
        for pad in sorted(wortel.rglob("*.py"))
    ]


def test_geen_enkele_check_importeert_de_uitvoerlaag() -> None:
    """a1: `checks/` levert bevindingen en weet niet in welke vorm ze landen.

    De `if TYPE_CHECKING`-import in `checks/base.py` wijst naar `nlriochecker.nulbevinding`
    en niet naar `uitvoer`; die heeft dus geen vrijstelling nodig.
    """
    overtreders = {
        pad: gevonden
        for pad, bron in _modules(f"{PAKKET}/checks")
        if (gevonden := _uitvoerimports(bron))
    }

    assert overtreders == {}


def test_de_uitvoerlaag_leest_alleen_de_toegestane_checksubmodules() -> None:
    """a2: buiten de facade om lezen mag alleen wat in `MAG_UIT_CHECKSUBMODULE` staat.

    Op naam én op pad: een nieuwe `uitvoer/ext/gpkg.py` zou zichzelf anders vrijstellen
    met de regel van de bestaande.
    """
    overtreders = []
    for pad, bron in _modules(f"{PAKKET}/uitvoer"):
        toegestaan = MAG_UIT_CHECKSUBMODULE.get(pad, {})
        for module, namen in _checksubmodule_imports(bron):
            ongedekt = sorted(set(namen) - toegestaan.get(module, frozenset()))
            if ongedekt:
                overtreders.append(f"{pad}: {module} -> {', '.join(ongedekt)}")

    assert sorted(overtreders) == []


def test_geen_enkele_allowlistregel_is_verouderd() -> None:
    """De lijst mag krimpen -- en dan moet dat krimpen ook gebeuren.

    Zonder deze test is "alleen krimpen" een instructie in een docstring: een import die
    verdwijnt laat zijn regel achter, en die regel houdt de deur open voor precies die
    import zonder dat er nog een reden voor is. Hij gaat pas af nádat een import
    weggehaald is -- issue #122 haalde `aanwijzingen_van` uit `gpkg.py`, en deze test
    ging af tot de regel eronder ook weg was -- en dwingt dan alleen het opruimen van de
    regel af, niet het behouden van de import.
    """
    feitelijk = {
        (pad, module, naam)
        for pad, bron in _modules(f"{PAKKET}/uitvoer")
        for module, namen in _checksubmodule_imports(bron)
        for naam in namen
    }

    verouderd = sorted(
        f"{pad}: {module} -> {naam}"
        for pad, per_module in MAG_UIT_CHECKSUBMODULE.items()
        for module, namen in per_module.items()
        for naam in namen
        if (pad, module, naam) not in feitelijk
    )

    assert verouderd == []


def test_geen_enkele_module_leest_een_prive_naam_uit_de_leeslaag() -> None:
    """a3: de leeslaag-API is bevroren op haar publieke namen.

    Een wijziging aan `gwsw_orox_helpers` loopt over een release van die package plus een
    `uv lock` hier; een `_`-naam is geen contract en zou die weg omzeilen.
    """
    overtreders = {
        pad: gevonden for pad, bron in _modules() if (gevonden := _prive_leeslaagnamen(bron))
    }

    assert overtreders == {}


def test_de_sweeps_kunnen_werkelijk_afgaan() -> None:
    """De tegenproef bij de drie hekken hierboven.

    Elk van de drie sweeps is groen op de huidige boom. Zonder deze test is dat niet te
    onderscheiden van een sweep die de overtreding niet zou herkennen -- een import in
    een `try`-blok, een `import x.y` in plaats van een `from`, een naam die de sweep
    niet uit de AST haalt.
    """
    assert _uitvoerimports("from nlriochecker.uitvoer.herkomst import schrijf_csv") == [
        "nlriochecker.uitvoer.herkomst"
    ]
    assert _uitvoerimports("import nlriochecker.uitvoer") == ["nlriochecker.uitvoer"]
    # De uitvoerlaag als naam in plaats van als module; ontsnapte aan de eerste versie.
    assert _uitvoerimports("from nlriochecker import uitvoer") == ["nlriochecker.uitvoer"]

    assert _checksubmodule_imports("from nlriochecker.checks.netwerk import NET") == [
        ("nlriochecker.checks.netwerk", ("NET",))
    ]
    # De twee vormen die de submodule als geheel binnenhalen: nul namen respectievelijk
    # een naam die op de facade lijkt. Allebei `"*"`, en `"*"` staat in geen allowlist.
    assert _checksubmodule_imports("import nlriochecker.checks.netwerk") == [
        ("nlriochecker.checks.netwerk", ("*",))
    ]
    assert _checksubmodule_imports("from nlriochecker.checks import selectie") == [
        ("nlriochecker.checks.selectie", ("*",))
    ]
    assert all(
        "*" not in namen
        for per_module in MAG_UIT_CHECKSUBMODULE.values()
        for namen in per_module.values()
    )

    assert _prive_leeslaagnamen("from gwsw_orox_helpers.dataset import _intern") == [
        "gwsw_orox_helpers.dataset._intern"
    ]
    assert _prive_leeslaagnamen("import gwsw_orox_helpers._intern") == ["gwsw_orox_helpers._intern"]


def test_de_sweeps_laten_het_toegestane_met_rust() -> None:
    """De keerzijde: wat mag, mag ook echt.

    Zonder deze helft zou een sweep die alles rood noemt er net zo groen uitzien als
    hierboven, want de tegenproef vraagt alleen om treffers.
    """
    assert _uitvoerimports("from nlriochecker.checks.base import Check") == []
    # De facade is geen submodule: een waardetype uit `nlriochecker.checks` mag altijd.
    assert _checksubmodule_imports("from nlriochecker.checks import CheckRun, Severity") == []
    assert _prive_leeslaagnamen("from gwsw_orox_helpers.dataset import GwswDataset") == []
    # Een `_`-naam uit een andere package raakt de bevriezing van de leeslaag niet.
    assert _prive_leeslaagnamen("from nlriochecker.checks.selectie import _knopen") == []
