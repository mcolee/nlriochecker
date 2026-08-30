"""Drifttest op de cachesleutels van `CheckContext` (issue #118).

`CheckContext._cache` is één platte stringruimte over alle checkmodules heen, en
`CheckContext.cached` leunt met zijn ene `cast` op de afspraak dat een sleutel altijd met
dezelfde `bouw` gevuld wordt. Botsen er twee, dan krijgt de ene beller de structuur van
de andere terug -- zonder foutmelding, want de `cast` gelooft hem op zijn woord.

Er is vandaag geen botsing: alle literale sleutels zijn uniek. Dit is preventie. De
enige bewaking die er tot dit issue was, `test_elke_rol_heeft_een_eigen_cachesleutel` in
`test_checks_selectie.py`, kijkt uitsluitend naar de `sel:`-familie.

De sweep verzamelt drie soorten sleutel, en de tweede is de valkuil:

1. de stringliteralen bij een `.cached(`-aanroep;
2. de `sel:`-literalen die aan de doorgeefhelpers `_knopen`/`_verbindingen` worden
   meegegeven. **Die staan niet bij de `.cached(`-aanroep**; een sweep die alleen
   `.cached("…")` leest mist ze allemaal;
3. de dynamisch samengestelde sleutels, beoordeeld op hun literale voorvoegsel.

De eigenaarstabel zelf staat in `checks/base.py`, naast `cached`, en niet hier: de
docstring die de afspraak in proza vastlegt woont daar ook, en zo blijft er één plek.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from nlriochecker.checks.base import CACHE_KALE_SLEUTELS, CACHE_VOORVOEGSELS

BRON = Path(__file__).resolve().parents[1] / "src"

# Functies die de cachesleutel van hun beller doorkrijgen in plaats van hem zelf te
# schrijven, met de plaats van het sleutelargument. `_knopen` en `_verbindingen` in
# `checks/selectie.py` zijn de enige twee: elke rolfunctie geeft er haar eigen
# `sel:`-literaal aan mee.
DOORGEEFHELPERS = {"_knopen": 1, "_verbindingen": 1}

# De modules waarin een `.cached(`-aanroep zijn sleutel uit een parameter krijgt in
# plaats van uit een literaal of een f-string. Alleen `checks/selectie.py`: dat zijn de
# twee doorgeefhelpers hierboven, en hun sleutels worden via `DOORGEEFHELPERS` alsnog
# geteld. Wie hier een module aan toevoegt, zorgt eerst dat de sweep de sleutels van die
# module langs een andere weg te pakken krijgt -- anders vallen ze stilzwijgend buiten
# elke bewering hieronder.
MAG_DOORGEVEN = {"nlriochecker.checks.selectie"}


@dataclass(frozen=True)
class Sleutel:
    """Een cachesleutel zoals de broncode hem schrijft."""

    module: str
    tekst: str
    # False voor een dynamisch samengestelde sleutel; `tekst` is dan het literale begin
    # van de f-string (`"ext:selectie:"`), niet de volledige sleutel.
    letterlijk: bool

    @property
    def voorvoegsel(self) -> str:
        """Het deel voor de eerste dubbele punt, of "" bij een kale sleutel."""
        return self.tekst.split(":", 1)[0] if ":" in self.tekst else ""


def _modulenaam(pad: Path) -> str:
    """De puntnotatie van een bronbestand: `src/nlriochecker/checks/base.py` -> module."""
    delen = pad.relative_to(BRON).with_suffix("").parts
    return ".".join(delen[:-1] if delen[-1] == "__init__" else delen)


def _sleutel_van(knoop: ast.expr, toewijzingen: dict[str, str], module: str) -> Sleutel | None:
    """De sleutel achter een argument, of None als hij uit een parameter komt."""
    if isinstance(knoop, ast.Constant) and isinstance(knoop.value, str):
        return Sleutel(module, knoop.value, letterlijk=True)
    if isinstance(knoop, ast.JoinedStr):
        return Sleutel(module, _literale_kop(knoop), letterlijk=False)
    if isinstance(knoop, ast.Name) and knoop.id in toewijzingen:
        return Sleutel(module, toewijzingen[knoop.id], letterlijk=False)
    return None


def _literale_kop(knoop: ast.JoinedStr) -> str:
    """Het literale begin van een f-string, tot het eerste ingevulde veld."""
    kop = ""
    for deel in knoop.values:
        if not isinstance(deel, ast.Constant):
            break
        kop += str(deel.value)
    return kop


def _fstring_namen(knoop: ast.AST) -> dict[str, str]:
    """Per naam in deze scope het literale begin van de f-string die eraan toegekend wordt.

    `sleutel = f"onbereikbaar:…"` gevolgd door `context.cached(sleutel, …)` is de enige
    vorm waarin een sleutel in deze codebase een omweg maakt. Geneste functies tellen
    niet mee: zonder die grens zou een variabele elders in het bestand een gelijknamige
    parameter maskeren, en dan ziet de sweep een doorgeefsleutel voor een echte aan.
    """
    gevonden: dict[str, str] = {}
    for kind in ast.iter_child_nodes(knoop):
        if isinstance(kind, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            continue
        if isinstance(kind, ast.Assign) and isinstance(kind.value, ast.JoinedStr):
            gevonden |= {
                doel.id: _literale_kop(kind.value)
                for doel in kind.targets
                if isinstance(doel, ast.Name)
            }
        gevonden |= _fstring_namen(kind)
    return gevonden


def _scope(functie: ast.AST, geerfd: dict[str, str]) -> dict[str, str]:
    """De f-string-namen binnen een functie: de erfenis minus haar parameters, plus lokaal."""
    parameters = {arg.arg for arg in ast.walk(functie) if isinstance(arg, ast.arg)}
    buiten = {naam: kop for naam, kop in geerfd.items() if naam not in parameters}
    return buiten | _fstring_namen(functie)


def _sleutelplek(knoop: ast.Call) -> int | None:
    """De plaats van het sleutelargument in deze aanroep, of None als het er geen is."""
    if isinstance(knoop.func, ast.Attribute) and knoop.func.attr == "cached":
        return 0
    if isinstance(knoop.func, ast.Name) and knoop.func.id in DOORGEEFHELPERS:
        return DOORGEEFHELPERS[knoop.func.id]
    return None


def _sleutelargument(knoop: ast.Call, plek: int) -> ast.expr | None:
    """Het sleutelargument, positioneel of als keyword.

    Zonder de keyword-vorm zou `context.cached(sleutel="…", bouw=…)` volledig aan de
    sweep ontsnappen: `args` is dan leeg, en een aanroep die de sweep helemaal niet ziet
    telt ook niet als doorgegeven. De parameter heet in alle drie de functies `sleutel`.
    """
    if plek < len(knoop.args):
        return knoop.args[plek]
    return next((woord.value for woord in knoop.keywords if woord.arg == "sleutel"), None)


def _sleutels_van_module(bron: str, module: str) -> tuple[list[Sleutel], int]:
    """De sleutels in deze broncode, plus het aantal dat uit een parameter komt."""
    sleutels: list[Sleutel] = []
    doorgegeven = 0

    def loop(knoop: ast.AST, namen: dict[str, str]) -> None:
        """Bezoekt de boom; elke functie krijgt haar eigen scope."""
        nonlocal doorgegeven
        for kind in ast.iter_child_nodes(knoop):
            if isinstance(kind, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                loop(kind, _scope(kind, namen))
                continue
            if isinstance(kind, ast.Call) and (plek := _sleutelplek(kind)) is not None:
                argument = _sleutelargument(kind, plek)
                sleutel = None if argument is None else _sleutel_van(argument, namen, module)
                if sleutel is None:
                    doorgegeven += 1
                else:
                    sleutels.append(sleutel)
            loop(kind, namen)

    boom = ast.parse(bron)
    loop(boom, _fstring_namen(boom))
    return sleutels, doorgegeven


def _alle_sleutels() -> tuple[list[Sleutel], dict[str, int]]:
    """Elke cachesleutel in `src/`, plus per module het aantal doorgegeven sleutels."""
    sleutels: list[Sleutel] = []
    doorgegeven: dict[str, int] = {}
    for pad in sorted(BRON.rglob("*.py")):
        module = _modulenaam(pad)
        gevonden, aantal = _sleutels_van_module(pad.read_text(encoding="utf-8"), module)
        sleutels += gevonden
        if aantal:
            doorgegeven[module] = aantal
    return sleutels, doorgegeven


SLEUTELS, DOORGEGEVEN = _alle_sleutels()
LETTERLIJK = [sleutel for sleutel in SLEUTELS if sleutel.letterlijk]
DYNAMISCH = [sleutel for sleutel in SLEUTELS if not sleutel.letterlijk]


def test_elke_literale_cachesleutel_is_uniek() -> None:
    """Twee bellers onder dezelfde sleutel geven elkaar stil de verkeerde structuur.

    De `cast` in `CheckContext.cached` kan dat niet zien: hij gelooft de beller. Een
    botsing komt dus niet als typefout naar boven maar als een verkeerd antwoord.
    """
    per_tekst: dict[str, list[str]] = {}
    for sleutel in LETTERLIJK:
        per_tekst.setdefault(sleutel.tekst, []).append(sleutel.module)

    dubbel = {tekst: modules for tekst, modules in per_tekst.items() if len(modules) > 1}

    assert dubbel == {}


def test_elke_sleutel_hoort_bij_zijn_eigenaarsmodule() -> None:
    """Een voorvoegsel heeft een eigenaar, en die staat in `CACHE_VOORVOEGSELS`.

    Dat is waar de veiligheid van de `cast` op rust: zolang één module een voorvoegsel
    vult, kan een sleutel niet twee soorten structuur dragen. De tabel is daarmee geen
    documentatie naast de code maar de bewering zelf.
    """
    onbekend = sorted(
        {
            f"{sleutel.module}: {sleutel.tekst!r}"
            for sleutel in SLEUTELS
            if sleutel.voorvoegsel and sleutel.voorvoegsel not in CACHE_VOORVOEGSELS
        }
    )
    assert onbekend == []

    vreemd = sorted(
        {
            f"{sleutel.module}: {sleutel.tekst!r}"
            for sleutel in SLEUTELS
            if sleutel.voorvoegsel and sleutel.module not in CACHE_VOORVOEGSELS[sleutel.voorvoegsel]
        }
    )
    assert vreemd == []


def test_elke_kale_sleutel_staat_expliciet_in_de_tabel() -> None:
    """Een sleutel zonder voorvoegsel deelt de naamruimte met alle andere.

    Ze zijn er negen, ze zijn niet fout, en ze mogen blijven -- maar dan wel opgeschreven.
    Let op: "begint met een bekend voorvoegsel" is niet hetzelfde als "heeft een
    voorvoegsel". `topologie` is allebei: een kale sleutel én het voorvoegsel van
    `topologie:snapping`.
    """
    kaal = {sleutel.tekst: sleutel.module for sleutel in SLEUTELS if not sleutel.voorvoegsel}

    ongenoemd = sorted(tekst for tekst in kaal if tekst not in CACHE_KALE_SLEUTELS)
    assert ongenoemd == []

    vreemd = sorted(
        f"{module}: {tekst!r}"
        for tekst, module in kaal.items()
        if module not in CACHE_KALE_SLEUTELS[tekst]
    )
    assert vreemd == []


def test_een_dynamische_sleutel_draagt_een_literaal_voorvoegsel() -> None:
    """Wat de f-string invult is niet te lezen; het voorvoegsel ervoor wel.

    Zonder literaal voorvoegsel valt een samengestelde sleutel buiten elke bewering
    hierboven: de sweep weet dan niet wie hem vult.
    """
    zonder = sorted(f"{s.module}: {s.tekst!r}" for s in DYNAMISCH if not s.tekst.endswith(":"))

    assert zonder == []
    assert DYNAMISCH, "de sweep leest geen enkele samengestelde sleutel meer"


def test_alleen_de_doorgeefhelpers_krijgen_hun_sleutel_van_de_beller() -> None:
    """Een `.cached(`-aanroep met een sleutel uit een parameter ontsnapt aan de sweep.

    De twee helpers in `checks/selectie.py` zijn de bekende uitzondering; hun sleutels
    worden via `DOORGEEFHELPERS` bij de rolfuncties opgehaald. Een derde zou 21 sleutels
    stil buiten beeld kunnen brengen.
    """
    assert sorted(DOORGEGEVEN) == sorted(MAG_DOORGEVEN)


def test_de_sweep_ziet_de_sel_sleutels_bij_de_rolfuncties() -> None:
    """De valkuil, uitgeschreven: `sel:`-sleutels staan niet bij een `.cached(`-aanroep.

    Ze worden aan `_knopen`/`_verbindingen` meegegeven. Zou de sweep alleen
    `.cached("…")` lezen, dan zou hij deze hele familie missen en er groen bij blijven.
    """
    sel = {sleutel.tekst for sleutel in LETTERLIJK if sleutel.voorvoegsel == "sel"}

    assert "sel:putten" in sel
    assert "sel:vrijvervalrioolleidingen" in sel
    # Eén `sel:`-sleutel staat wél bij een `.cached(`-aanroep (`oppervlaktewaterobjecten`
    # bouwt zijn eigen selectie); de rest komt uit de doorgeefhelpers.
    assert len(sel) > 1


def test_de_sweep_kan_werkelijk_afgaan() -> None:
    """De tegenproef: op een synthetisch stukje broncode vindt de sweep wat er staat.

    Zonder deze test is een sweep die niets vindt niet te onderscheiden van een sweep
    die niets kán vinden -- en de vier beweringen hierboven zijn alle vier groen op de
    huidige boom.
    """
    bron = """
def _iets(context):
    return context.cached("verzonnen:sleutel", bouw)


def _nog_iets(context, rol):
    sleutel = f"anders:{rol}"
    return context.cached(sleutel, bouw)


def _rol(context):
    return _knopen(context, "sel:verzonnen", [])


def _met_keyword(context):
    return context.cached(sleutel="keyword:sleutel", bouw=bouw)


def _doorgeef(context, sleutel):
    return context.cached(sleutel, bouw)
"""

    sleutels, doorgegeven = _sleutels_van_module(bron, "verzonnen")

    assert {(s.tekst, s.letterlijk) for s in sleutels} == {
        ("verzonnen:sleutel", True),
        ("anders:", False),
        ("sel:verzonnen", True),
        # De keyword-vorm heeft lege `args` en ontsnapte volledig aan de eerste versie:
        # de sweep zag de aanroep niet, en telde hem ook niet als doorgegeven.
        ("keyword:sleutel", True),
    }
    assert doorgegeven == 1
    assert Sleutel("verzonnen", "netwerk", letterlijk=True).voorvoegsel == ""
