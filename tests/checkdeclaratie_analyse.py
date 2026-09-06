"""Leidt uit de broncode af welke rollen en kenmerken een check feitelijk gebruikt.

Dit is het gereedschap onder de twee drifttests van issue #64. Een check hoort in
`rollen` en `kenmerken` te declareren over welke GWSW-populatie hij gaat en welke
kenmerken hij leest; deze module haalt datzelfde langs een andere weg uit de code, via
een AST-sweep, zodat de declaratie tegen de feitelijke code gehouden kan worden.

**Wat als rol telt (Optie A, issue #64).** Een rol is een naam uit `selectie._ROLLEN`:
de populatie die een check langsloopt. De sweep vindt ze op drie manieren, elk vanuit de
methoden `run`, `examined` en `notes` en door de basisklassen en module-eigen
hulpfuncties heen:

1. een directe aanroep van een rolfunctie (`vrijvervalrioolleidingen(context)`, ook als
   `selectie.vrijvervalrioolleidingen(...)`);
2. een dynamische-rol-hulpfunctie die de rol als tekst krijgt
   (`aansluitingen(context, "vrijvervalleiding")`, `_eindpunten(context, rol)`): het
   veld uit `[klassen]` wordt teruggekoppeld naar de rolfunctie die datzelfde veld
   selecteert;
3. dezelfde tekst via een ClassVar (`_eindpunten(context, self.eindpuntrol)`).

Pure graafnavigatie (`verbonden_knopen`, `resolve_network_node`, samenhangende delen)
is engine-structuur en géén rol -- dat is de afspraak uit issue #64 en `dataset.py`.

**Wat als kenmerk telt.** Een GWSW-kenmerknaam die de code aan `aspect`, `number`,
`reference` of `date` geeft -- als letterlijke string, via een tuple/lus, via een
modulevariabele of via een ClassVar -- plus de afgeleide eigenschappen van `Node` en
`Conduit` (`bovenkant`, `bodem`, `bob_start`, ...), die elk via `DERIVED_PROPS` naar hun
GWSW-kenmerk vertaald worden.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import nlriochecker.checks  # noqa: F401  (vult de registry)
from nlriochecker.checks.base import REGISTRY

WORTEL = Path(__file__).resolve().parents[1]
CHECKS_DIR = WORTEL / "src" / "nlriochecker" / "checks"

# De methoden waarmee een object een kenmerk bij zijn GWSW-naam opvraagt; het eerste
# argument is de kenmerknaam. Gelijk aan `KENMERKLEZERS` in test_gwsw_vocabulaire.
KENMERKLEZERS = frozenset({"aspect", "number", "reference", "date"})

# De methoden die een dynamische rol als tekst krijgen; het tweede argument (of `rol=`)
# is een veldnaam uit `[klassen]`.
DYNAMISCHE_ROL_HELPERS = frozenset(
    {"aansluitingen", "_bouw_aansluitingen", "_eindpunten", "_bouw_eindpunten"}
)

# Module-eigen hulpfuncties die zich als kenmerklezer gedragen: de naam koppelt aan de
# positie van het kenmerk-argument. `_waarde(context, subject, "Drempelniveau")` in
# `randvoorzieningen.py` leest een kenmerk via `aspect.kind == kenmerk` in plaats van via
# een van de vier `KENMERKLEZERS`; zonder deze koppeling bleven de drempelkenmerken buiten
# beeld.
KENMERK_LEZER_HELPERS: dict[str, int] = {"_waarde": 2}

# De afgeleide eigenschappen van `Node`/`Conduit` en de GWSW-kenmerken die eronder
# liggen. `bovenkant` valt terug van dekselniveau op maaiveld, `bodem` trekt daar
# `HoogtePut` van af; die samengestelde eigenschappen dragen dus meer dan één kenmerk.
DERIVED_PROPS: dict[str, frozenset[str]] = {
    "maaiveld": frozenset({"Maaiveldhoogte"}),
    "dekselniveau": frozenset({"Putdekselniveau"}),
    "bovenkant": frozenset({"Putdekselniveau", "Maaiveldhoogte"}),
    "hoogte_m": frozenset({"HoogtePut"}),
    "bodem": frozenset({"Putdekselniveau", "Maaiveldhoogte", "HoogtePut"}),
    "bob_start": frozenset({"BobBeginpuntLeiding"}),
    "bob_end": frozenset({"BobEindpuntLeiding"}),
    "bob_verval": frozenset({"BobBeginpuntLeiding", "BobEindpuntLeiding"}),
    "breedte_mm": frozenset({"BreedteLeiding"}),
    "hoogte_mm": frozenset({"HoogteLeiding"}),
    "lengte_m": frozenset({"LengteLeiding"}),
    "materiaal": frozenset({"MateriaalLeiding"}),
    "vorm": frozenset({"VormLeiding"}),
    "begindatum_jaar": frozenset({"Begindatum"}),
}


@dataclass
class ModuleModel:
    """Het geparste beeld van één checkmodule dat de sweep nodig heeft."""

    naam: str
    funcs: dict[str, ast.FunctionDef] = field(default_factory=dict)
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    # lokale naam -> (modulebasename, oorspronkelijke naam) voor imports uit checks-modules.
    imports: dict[str, tuple[str, str]] = field(default_factory=dict)
    # modulevariabele -> de stringconstanten erin (tuple/list/set/frozenset van str).
    consts: dict[str, frozenset[str]] = field(default_factory=dict)


def _str_constanten(node: ast.AST) -> frozenset[str]:
    """De stringconstanten in een tuple/lijst/verzameling, of leeg als het dat niet is."""
    elts: list[ast.expr] = []
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        elts = list(node.elts)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in {"frozenset", "set", "tuple", "list"} and node.args:
            return _str_constanten(node.args[0])
    return frozenset(
        e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
    )


def _parse_module(naam: str, boom: ast.Module) -> ModuleModel:
    """Bouwt het `ModuleModel` van één geparste checkmodule.

    Functies, klassen en stringconstanten worden op moduleniveau verzameld; imports uit
    `nlriochecker.checks.*` daarentegen over de hele boom (`ast.walk`), dus ook een
    `from nlriochecker.checks.x import y` binnen een functie- of methodelichaam. Zonder
    die functie-lokale lezing verloor de sweep een hulpfunctie die een check pas in haar
    `run` importeerde -- de omissie die issue #137 blootlegde (HGT-011 las de drempels via
    een lazy import). De naam is binnen een module uniek genoeg dat de plek van de import
    er niet toe doet.
    """
    model = ModuleModel(naam)
    for knoop in boom.body:
        if isinstance(knoop, ast.FunctionDef):
            model.funcs[knoop.name] = knoop
        elif isinstance(knoop, ast.ClassDef):
            model.classes[knoop.name] = knoop
        elif isinstance(knoop, ast.Assign):
            strings = _str_constanten(knoop.value)
            if strings:
                for doel in knoop.targets:
                    if isinstance(doel, ast.Name):
                        model.consts[doel.id] = strings
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.ImportFrom) and (knoop.module or "").startswith(
            "nlriochecker.checks"
        ):
            bron = (knoop.module or "").rsplit(".", 1)[-1]
            for alias in knoop.names:
                model.imports[alias.asname or alias.name] = (bron, alias.name)
    return model


def _bouw_modules() -> dict[str, ModuleModel]:
    """Parseert elke checkmodule tot een `ModuleModel`."""
    modules: dict[str, ModuleModel] = {}
    for pad in sorted(CHECKS_DIR.glob("*.py")):
        modules[pad.stem] = _parse_module(pad.stem, ast.parse(pad.read_text(encoding="utf-8")))
    return modules


def _veld_naar_rol() -> dict[str, str]:
    """Koppelt elk `[klassen]`-veld aan de rolfunctie die het selecteert.

    Uit `selectie.py`: elke rolfunctie leest `context.config.klassen.<veld>`. Zo weet de
    sweep dat `aansluitingen(context, "vrijvervalleiding")` de rol `vrijvervalrioolleidingen`
    is, want die rolfunctie leest datzelfde veld.
    """
    boom = ast.parse((CHECKS_DIR / "selectie.py").read_text(encoding="utf-8"))
    rollen = _rolnamen()
    veld_van_rol: dict[str, str] = {}
    for knoop in boom.body:
        if not isinstance(knoop, ast.FunctionDef) or knoop.name not in rollen:
            continue
        for sub in ast.walk(knoop):
            # context.config.klassen.<veld>
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Attribute)
                and sub.value.attr == "klassen"
            ):
                veld_van_rol.setdefault(knoop.name, sub.attr)
    return {veld: rol for rol, veld in veld_van_rol.items()}


def _rolnamen() -> frozenset[str]:
    """De namen uit `selectie._ROLLEN`."""
    from nlriochecker.checks import selectie

    return frozenset(selectie._ROLLEN)


def _rol_velden() -> frozenset[str]:
    """De `[klassen]`-veldnamen die aan een rol hangen (`selectie._ROL_VELDEN`).

    De klassenlijst-sweep houdt alleen de velden over die hier *niet* in staan: een veld
    dat een rol draagt hoort in `rollen`, niet in `klassenlijsten`.
    """
    from nlriochecker.checks import selectie

    return frozenset(selectie._ROL_VELDEN.values())


def _klassen_velden() -> frozenset[str]:
    """Elke veldnaam van `[klassen]` (`ClassRoots`).

    Dient om een `self.eindpuntrollen`-achtige ClassVar te herkennen: een tuple waarvan
    élk element een `[klassen]`-veld is, is een lijst met veldnamen (issue #137). Zo blijft
    een gewone string-ClassVar (`stelselrol`, een drempelnaam) buiten beeld.
    """
    from nlriochecker.checkconfig import ClassRoots

    return frozenset(ClassRoots.model_fields)


@dataclass(frozen=True)
class Declaratie:
    """Wat de sweep voor één check afleidde."""

    rollen: frozenset[str]
    kenmerken: frozenset[str]
    # Issue #137: de `[klassen]`-veldnamen die de check leest en die geen rol zijn (`vgs`,
    # `drempel`, ...). Rolvelden vallen af; die staan in `rollen`.
    klassenlijsten: frozenset[str]


class _Sweep:
    """Loopt de callgraaf van één check af en verzamelt rollen en kenmerken."""

    def __init__(
        self,
        modules: dict[str, ModuleModel],
        rolnamen: frozenset[str],
        veld_naar_rol: dict[str, str],
    ) -> None:
        self.modules = modules
        self.rolnamen = rolnamen
        self.veld_naar_rol = veld_naar_rol

    def analyseer(self, check: type) -> Declaratie:
        """De rollen, kenmerken en klassenlijsten die vanuit `run`/`examined`/`notes` gaan."""
        self.rollen: set[str] = set()
        self.kenmerken: set[str] = set()
        self.klassenlijsten: set[str] = set()
        self.check = check
        # De klassen uit de MRO die in een checkmodule staan, nieuw-naar-oud.
        self.mro = [
            k
            for k in check.__mro__
            if k.__module__.startswith("nlriochecker.checks")
            and k.__module__.rsplit(".", 1)[-1] in self.modules
        ]
        self.bezocht: set[tuple[str, str, str]] = set()
        for methode in ("run", "examined", "notes"):
            self._volg_methode(methode)
        klassenlijsten = frozenset(self.klassenlijsten) - _rol_velden()
        return Declaratie(frozenset(self.rollen), frozenset(self.kenmerken), klassenlijsten)

    def _module_van(self, klass: type) -> ModuleModel:
        return self.modules[klass.__module__.rsplit(".", 1)[-1]]

    def _zoek_methode(self, naam: str) -> tuple[ast.FunctionDef, ModuleModel] | None:
        """Vindt de definitie van een methode langs de MRO van de check."""
        for klass in self.mro:
            model = self._module_van(klass)
            classdef = model.classes.get(klass.__name__)
            if classdef is None:
                continue
            for item in classdef.body:
                if isinstance(item, ast.FunctionDef) and item.name == naam:
                    return item, model
        return None

    def _volg_methode(self, naam: str) -> None:
        gevonden = self._zoek_methode(naam)
        if gevonden is not None:
            func, model = gevonden
            self._verwerk(func, model, sleutel=("methode", self.check.__name__, naam))

    def _classvar(self, naam: str) -> object:
        """De waarde van een ClassVar op de check, of None."""
        return getattr(self.check, naam, None)

    def _veldnamen_classvar(self, naam: str) -> frozenset[str]:
        """De `[klassen]`-velden uit een ClassVar-tuple met uitsluitend veldnamen (issue #137)."""
        waarde = self._classvar(naam)
        if not isinstance(waarde, tuple | list | frozenset | set):
            return frozenset()
        strings = {w for w in waarde if isinstance(w, str)}
        if strings and strings <= _klassen_velden():
            return frozenset(strings)
        return frozenset()

    def _verwerk(self, func: ast.FunctionDef, model: ModuleModel, sleutel) -> None:
        if sleutel in self.bezocht:
            return
        self.bezocht.add(sleutel)
        # De attributen die de `.func` van een aanroep zijn (`taal.vorm(...)`) zijn geen
        # eigenschapslezingen; alleen een kaal attribuutgebruik (`node.vorm`) telt.
        aanroep_functies = {
            id(knoop.func) for knoop in ast.walk(func) if isinstance(knoop, ast.Call)
        }
        # Kenmerken uit afgeleide eigenschappen: elk kaal attribuutgebruik met zo'n naam.
        for knoop in ast.walk(func):
            if (
                isinstance(knoop, ast.Attribute)
                and knoop.attr in DERIVED_PROPS
                and id(knoop) not in aanroep_functies
            ):
                self.kenmerken |= DERIVED_PROPS[knoop.attr]
            # Een `[klassen]`-lijst gelezen als attribuutketen `...klassen.<veld>` (issue
            # #137). Een methode-aanroep op `klassen` (`klassen.stelseltype(...)`) is de
            # `.func` van een Call en telt niet mee -- dat is een berekening, geen lijst.
            if (
                isinstance(knoop, ast.Attribute)
                and isinstance(knoop.value, ast.Attribute)
                and knoop.value.attr == "klassen"
                and id(knoop) not in aanroep_functies
            ):
                self.klassenlijsten.add(knoop.attr)
            # Een ClassVar met veldnamen (`self.eindpuntrollen`, `self.eindpuntrollen_via_
            # gemengd`): NET-002 leest zijn `afvoer_eindpunt` via zo'n tuple die door
            # `_eindpuntset` heen geïtereerd wordt -- te ver voor de argument-koppeling van
            # de sweep. Een tuple waarvan élk element een `[klassen]`-veld is, ís een
            # veldnamenlijst; een gewone string-ClassVar (`stelselrol`) valt af. Zie #137.
            if (
                isinstance(knoop, ast.Attribute)
                and _is_self(knoop.value)
                and id(knoop) not in aanroep_functies
            ):
                self.klassenlijsten |= self._veldnamen_classvar(knoop.attr)
            if isinstance(knoop, ast.Call):
                self._verwerk_call(knoop, func, model)

    def _verwerk_call(self, call: ast.Call, func: ast.FunctionDef, model: ModuleModel) -> None:
        naam = _call_naam(call)
        if naam in KENMERKLEZERS and call.args:
            self.kenmerken |= self._kenmerk_uit_arg(call.args[0], func, model)
        if naam in KENMERK_LEZER_HELPERS:
            index = KENMERK_LEZER_HELPERS[naam]
            if len(call.args) > index:
                self.kenmerken |= self._kenmerk_uit_arg(call.args[index], func, model)
        if naam in DYNAMISCHE_ROL_HELPERS:
            self._rol_uit_dynamische_helper(call, func)
        if naam in self.rolnamen:
            self.rollen.add(naam)
            return
        self._volg_call(call, naam, model)

    def _volg_call(self, call: ast.Call, naam: str | None, model: ModuleModel) -> None:
        """Volgt een aanroep naar een module-hulpfunctie of een `self`-methode."""
        if naam is None:
            return
        if isinstance(call.func, ast.Attribute) and _is_self(call.func.value):
            self._volg_methode(call.func.attr)
            return
        # Bare naam: module-eigen functie of een import uit een checks-module.
        if naam in model.funcs:
            self._verwerk(model.funcs[naam], model, sleutel=("func", model.naam, naam))
        elif naam in model.imports:
            bron, orig = model.imports[naam]
            bronmodel = self.modules.get(bron)
            if bronmodel is not None and orig in bronmodel.funcs:
                self._verwerk(bronmodel.funcs[orig], bronmodel, sleutel=("func", bron, orig))

    def _rol_uit_dynamische_helper(self, call: ast.Call, func: ast.FunctionDef) -> None:
        """Leidt de rol of klassenlijst af uit het tekstargument van `aansluitingen`/`_eindpunten`.

        Een dynamische-rol-helper krijgt een `[klassen]`-veld als tekst; is dat een rolveld
        (`vrijvervalleiding`), dan is het de bijbehorende rol, en anders (`afvoer_eindpunt`,
        de eindpuntrol van NET-001/002) een klassenlijst. De eindfilter in `analyseer` haalt
        de rolvelden er weer af, dus toevoegen aan beide is veilig (issue #137).
        """
        arg = _rol_argument(call)
        for veld in self._velden_uit_arg(arg, func):
            rol = self.veld_naar_rol.get(veld)
            if rol is not None:
                self.rollen.add(rol)
            self.klassenlijsten.add(veld)

    def _velden_uit_arg(self, arg: ast.expr | None, func: ast.FunctionDef) -> frozenset[str]:
        """De `[klassen]`-veldnaam/-namen achter een rol-argument."""
        if arg is None:
            return frozenset()
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return frozenset({arg.value})
        if isinstance(arg, ast.Attribute) and _is_self(arg.value):
            waarde = self._classvar(arg.attr)
            if isinstance(waarde, str):
                return frozenset({waarde})
        if isinstance(arg, ast.Name):
            return self._namen_binding(arg.id, func)
        return frozenset()

    def _kenmerk_uit_arg(
        self, arg: ast.expr, func: ast.FunctionDef, model: ModuleModel
    ) -> frozenset[str]:
        """De GWSW-kenmerknaam/-namen achter het eerste argument van een kenmerklezer."""
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return frozenset({arg.value})
        if isinstance(arg, ast.Attribute) and _is_self(arg.value):
            waarde = self._classvar(arg.attr)
            if isinstance(waarde, str):
                return frozenset({waarde})
            if isinstance(waarde, tuple | list | frozenset | set):
                return frozenset(w for w in waarde if isinstance(w, str))
        if isinstance(arg, ast.Name):
            lokaal = self._namen_binding(arg.id, func)
            if lokaal:
                return lokaal
            return model.consts.get(arg.id, frozenset())
        return frozenset()

    def _namen_binding(self, naam: str, func: ast.FunctionDef) -> frozenset[str]:
        """De stringconstanten waaraan een naam binnen deze functie gebonden wordt.

        Vangt de lus- en comprehensiepatronen (`for kenmerk in ("BreedtePut", ...)`) en
        eenvoudige toewijzingen aan een tuple/lijst van strings.
        """
        gevonden: set[str] = set()
        for knoop in ast.walk(func):
            doel: ast.expr | None = None
            iterabel: ast.expr | None = None
            if isinstance(knoop, ast.comprehension):
                doel, iterabel = knoop.target, knoop.iter
            elif isinstance(knoop, ast.For):
                doel, iterabel = knoop.target, knoop.iter
            elif isinstance(knoop, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == naam for t in knoop.targets):
                    gevonden |= _str_constanten(knoop.value)
                continue
            if isinstance(doel, ast.Name) and doel.id == naam and iterabel is not None:
                gevonden |= _str_constanten(iterabel)
                # `for kenmerk in self.kenmerken`: los de ClassVar op.
                if isinstance(iterabel, ast.Attribute) and _is_self(iterabel.value):
                    waarde = self._classvar(iterabel.attr)
                    if isinstance(waarde, tuple | list | frozenset | set):
                        gevonden |= {w for w in waarde if isinstance(w, str)}
        return frozenset(gevonden)


def _call_naam(call: ast.Call) -> str | None:
    """De naam van de aangeroepen functie: `f(...)` of `x.f(...)`."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _rol_argument(call: ast.Call) -> ast.expr | None:
    """Het rol-argument van een dynamische-rol-helper: het tweede positionele of `rol=`."""
    for kw in call.keywords:
        if kw.arg == "rol":
            return kw.value
    if len(call.args) >= 2:
        return call.args[1]
    return None


def _is_self(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "self"


def analyseer_alle_checks() -> dict[str, Declaratie]:
    """De feitelijke rollen en kenmerken per check-ID, uit de broncode."""
    modules = _bouw_modules()
    sweep = _Sweep(modules, _rolnamen(), _veld_naar_rol())
    return {check_id: sweep.analyseer(REGISTRY[check_id]) for check_id in sorted(REGISTRY)}


# ---------------------------------------------------------------------------
# Drempelsleutels per check (issue #142)
#
# Naast de rollen en kenmerken van issue #64 leidt deze sweep af welke
# `[drempels]`-sleutels een check leest, zodat `test_checkdeclaraties` kan afdwingen dat
# elke check die een drempel leest die drempel ook in haar bevinding zet (traceerbaarheid:
# elke rij is te herleiden zonder `checks.toml` te openen).
#
# De sweep loopt de eigen methoden van de check af -- `run`, `notes`, `examined` en de
# `self.`-methoden die daaruit bereikt worden -- en NIET de module-vrije hulpfuncties.
# Dat laatste is bewust: `_bouw_topologie` leest `snapping_tolerantie_m` voor de gedeelde
# index, en die lezing hoort niet bij elke topologiecheck die de index gebruikt. Wat een
# check zelf in haar methoden leest is de drempel die haar bevindingen stuurt.


def _class_index(modules: dict[str, ModuleModel]) -> dict[str, tuple[str, ast.ClassDef]]:
    """Elke checkklasse bij naam, over alle modules heen: naam -> (module, ClassDef)."""
    index: dict[str, tuple[str, ast.ClassDef]] = {}
    for model in modules.values():
        for naam, classdef in model.classes.items():
            index.setdefault(naam, (model.naam, classdef))
    return index


def _basisnamen(classdef: ast.ClassDef) -> list[str]:
    """De directe basisklassenamen (`class X(A, B)` -> ['A', 'B'])."""
    return [basis.id for basis in classdef.bases if isinstance(basis, ast.Name)]


def _classvar_constante(index: dict[str, tuple[str, ast.ClassDef]], naam: str, veld: str) -> object:
    """De waarde van een string-ClassVar op deze klasse of een van haar bases, of None."""
    seen: set[str] = set()
    stapel = [naam]
    while stapel:
        klass = stapel.pop()
        if klass in seen or klass not in index:
            continue
        seen.add(klass)
        _, classdef = index[klass]
        for item in classdef.body:
            if isinstance(item, ast.Assign) and any(
                isinstance(doel, ast.Name) and doel.id == veld for doel in item.targets
            ):
                if isinstance(item.value, ast.Constant):
                    return item.value.value
        stapel.extend(_basisnamen(classdef))
    return None


def _methoden_van(
    index: dict[str, tuple[str, ast.ClassDef]], naam: str
) -> dict[str, ast.FunctionDef]:
    """Elke methode van deze klasse plus haar bases; de meest afgeleide wint."""
    volgorde: list[str] = []
    seen: set[str] = set()
    stapel = [naam]
    while stapel:
        klass = stapel.pop(0)
        if klass in seen or klass not in index:
            continue
        seen.add(klass)
        volgorde.append(klass)
        stapel.extend(_basisnamen(index[klass][1]))
    methoden: dict[str, ast.FunctionDef] = {}
    for klass in volgorde:
        for item in index[klass][1].body:
            if isinstance(item, ast.FunctionDef) and item.name not in methoden:
                methoden[item.name] = item
    return methoden


def _drempelsleutels_in(
    func: ast.FunctionDef, index: dict[str, tuple[str, ast.ClassDef]], clsnaam: str
) -> set[str]:
    """De `[drempels]`-sleutels die deze functie direct leest.

    Herkent `context.config.drempels.<sleutel>`, een aan `context.config.drempels`
    gebonden lokale naam (`drempels = context.config.drempels; drempels.<sleutel>`), en
    `getattr(drempels, <literal>|self.<classvar>)` -- de vorm van `_Tegenverhang` en
    `_DekselAfwijking`.
    """
    drempelnamen = {"drempels"}
    for knoop in ast.walk(func):
        if (
            isinstance(knoop, ast.Assign)
            and isinstance(knoop.value, ast.Attribute)
            and knoop.value.attr == "drempels"
        ):
            for doel in knoop.targets:
                if isinstance(doel, ast.Name):
                    drempelnamen.add(doel.id)

    sleutels: set[str] = set()
    for knoop in ast.walk(func):
        if isinstance(knoop, ast.Attribute):
            binnen = knoop.value
            if isinstance(binnen, ast.Attribute) and binnen.attr == "drempels":
                sleutels.add(knoop.attr)
            elif isinstance(binnen, ast.Name) and binnen.id in drempelnamen:
                sleutels.add(knoop.attr)
        if (
            isinstance(knoop, ast.Call)
            and isinstance(knoop.func, ast.Name)
            and knoop.func.id == "getattr"
            and len(knoop.args) >= 2
        ):
            basis = knoop.args[0]
            is_drempel = (isinstance(basis, ast.Name) and basis.id in drempelnamen) or (
                isinstance(basis, ast.Attribute) and basis.attr == "drempels"
            )
            if is_drempel:
                arg = knoop.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    sleutels.add(arg.value)
                elif isinstance(arg, ast.Attribute) and _is_self(arg.value):
                    waarde = _classvar_constante(index, clsnaam, arg.attr)
                    if isinstance(waarde, str):
                        sleutels.add(waarde)
    return sleutels


def _self_aanroepen(func: ast.FunctionDef) -> set[str]:
    """De namen van de `self.<methode>()`-aanroepen in deze functie."""
    namen: set[str] = set()
    for knoop in ast.walk(func):
        if (
            isinstance(knoop, ast.Call)
            and isinstance(knoop.func, ast.Attribute)
            and _is_self(knoop.func.value)
        ):
            namen.add(knoop.func.attr)
    return namen


def _classnaam_van(check: type) -> str:
    """De AST-klassenaam van een check: de Python-klassenaam zelf."""
    return check.__name__


def drempelsleutels_van_check(check: type) -> frozenset[str]:
    """De `[drempels]`-sleutels die deze check in haar eigen methoden leest.

    Loopt `run`, `notes` en `examined` af plus de `self.`-methoden die daaruit bereikt
    worden; module-vrije hulpfuncties blijven buiten beeld (zie de kop hierboven).
    """
    modules = _bouw_modules()
    index = _class_index(modules)
    clsnaam = _classnaam_van(check)
    if clsnaam not in index:
        return frozenset()
    methoden = _methoden_van(index, clsnaam)

    sleutels: set[str] = set()
    bezocht: set[str] = set()
    stapel = [naam for naam in ("run", "notes", "examined") if naam in methoden]
    while stapel:
        naam = stapel.pop()
        if naam in bezocht or naam not in methoden:
            continue
        bezocht.add(naam)
        func = methoden[naam]
        sleutels |= _drempelsleutels_in(func, index, clsnaam)
        stapel.extend(_self_aanroepen(func))
    return frozenset(sleutels)


def bevinding_kwargs_van_check(check: type) -> frozenset[str]:
    """De keyword-namen die deze check aan `self.finding(...)` meegeeft, over al haar methoden."""
    modules = _bouw_modules()
    index = _class_index(modules)
    clsnaam = _classnaam_van(check)
    if clsnaam not in index:
        return frozenset()
    kwargs: set[str] = set()
    for func in _methoden_van(index, clsnaam).values():
        for knoop in ast.walk(func):
            if (
                isinstance(knoop, ast.Call)
                and isinstance(knoop.func, ast.Attribute)
                and knoop.func.attr == "finding"
            ):
                kwargs.update(kw.arg for kw in knoop.keywords if kw.arg)
    return frozenset(kwargs)
