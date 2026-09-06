"""Drifttests bij de rol- en kenmerkdeclaraties van issue #64.

Elke check declareert in `rollen` en `kenmerken` over welke GWSW-populatie hij gaat en
welke kenmerken hij leest. Twee tests bewaken dat die declaratie waar blijft:

* `test_declaratie_volgt_de_code` houdt de declaratie tegen de feitelijke code, via de
  AST-sweep in `checkdeclaratie_analyse`. Te veel of te weinig gedeclareerd is allebei
  rood. Skeletten (`SkeletonCheck`) doen niet mee: hun code is leeg, dus hun declaratie
  is een belofte die alleen tegen de ontologie te houden is.
* `test_declaratie_past_bij_de_ontologie` (in `test_checkdeclaraties_ontologie.py`)
  houdt de declaratie tegen de GWSW-ontologie: draagt de klasse het kenmerk werkelijk?

Een `config:<pad>`-kenmerk (ATTR-013) en het sterretje `*` (ATTR-014) zijn geen
letterlijke kenmerknaam maar een verwijzing; de codetest laat ze staan en de
ontologietest lost ze op.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import Conduit, Node

import nlriochecker.checks  # noqa: F401  (vult de registry)
from checkdeclaratie_analyse import (
    DERIVED_PROPS,
    _parse_module,
    analyseer_alle_checks,
    bevinding_kwargs_van_check,
    drempelsleutels_van_check,
)
from nlriochecker.checks.base import REGISTRY, Check, Dimension, Severity, SkeletonCheck, register

# De eigenschappen van `Node`/`Conduit` die geen GWSW-kenmerk lezen maar de geometrie: de
# z-waarde uit de GML-lijn. Ze horen daarom niet in `DERIVED_PROPS`.
GEOMETRIE_EIGENSCHAPPEN = frozenset({"z_start", "z_end"})

WORTEL = Path(__file__).resolve().parents[1]

DECLARATIES = analyseer_alle_checks()
CHECK_IDS = sorted(REGISTRY)
# Skeletten hebben geen `run()`-code om tegen te sweepen; hun declaratie wordt alleen
# tegen de ontologie getoetst. Ze doen daarom niet mee aan de AST-sweep hieronder --
# niet als overslag (een overslag zonder `data/`- of BO-reden valt onder de strikte
# overslagbewaking, BO-48), maar door ze niet te parametriseren.
CODE_CHECK_IDS = sorted(
    cid for cid, check in REGISTRY.items() if not issubclass(check, SkeletonCheck)
)


def _concrete_kenmerken(check: type[Check]) -> frozenset[str]:
    """De gedeclareerde kenmerken zonder de `config:`- en `*`-verwijzingen."""
    return frozenset(k for k in check.kenmerken if not k.startswith("config:") and k != "*")


@pytest.mark.parametrize("check_id", CODE_CHECK_IDS)
def test_declaratie_volgt_de_code(check_id: str) -> None:
    """De gedeclareerde rollen en kenmerken zijn precies wat de code bereikt."""
    check = REGISTRY[check_id]
    feitelijk = DECLARATIES[check_id]
    assert frozenset(check.rollen) == feitelijk.rollen, (
        f"{check_id}: gedeclareerde rollen {sorted(check.rollen)} wijken af van wat de code "
        f"bereikt {sorted(feitelijk.rollen)}."
    )
    assert _concrete_kenmerken(check) == feitelijk.kenmerken, (
        f"{check_id}: gedeclareerde kenmerken {sorted(_concrete_kenmerken(check))} wijken af "
        f"van wat de code leest {sorted(feitelijk.kenmerken)}."
    )


@pytest.mark.parametrize("check_id", CODE_CHECK_IDS)
def test_declaratie_klassenlijsten_volgt_de_code(check_id: str) -> None:
    """De gedeclareerde `[klassen]`-lijsten zijn precies de niet-rol-velden die de code leest.

    Issue #137: naast rollen en kenmerken leest een check soms een `[klassen]`-lijst die
    geen rol is -- NET-006 het VGS, HGT-011/NET-007/RVZ-002/009/011 de drempels,
    NET-001/002/RVZ-006 het afvoereindpunt, EXT-003 de kruisingsleiding, RVZ-008 de
    ledigingsvoorziening, NET-005/006 de stelseltypen. De sweep vindt elke
    `context.config.klassen.<veld>`-keten en elke veldnamen-ClassVar vanuit
    `run`/`examined`/`notes`, houdt de niet-rol-velden over, en deze test bindt de
    declaratie er in beide richtingen aan: te veel of te weinig is allebei rood.
    """
    check = REGISTRY[check_id]
    feitelijk = DECLARATIES[check_id]
    assert frozenset(check.klassenlijsten) == feitelijk.klassenlijsten, (
        f"{check_id}: gedeclareerde klassenlijsten {sorted(check.klassenlijsten)} wijken af "
        f"van wat de code leest {sorted(feitelijk.klassenlijsten)}."
    )


def test_parse_module_volgt_functie_lokale_imports() -> None:
    """`_parse_module` verzamelt een import uit een checks-module ook binnen een functie.

    De sweep volgt een hulpfunctie die een check pas in haar `run` importeert (issue #137;
    de lazy import die de #64-sweep aanvankelijk miste). Een top-level import en een
    functie-lokale import horen daarom allebei in `ModuleModel.imports` te landen; deze
    gerichte proef bewijst dat zonder van een echte checkmodule af te hangen.
    """
    bron = (
        "from nlriochecker.checks.selectie import putten\n"
        "def run(self, context):\n"
        "    from nlriochecker.checks.randvoorzieningen import alle_drempels\n"
        "    return alle_drempels(context) or putten(context)\n"
    )
    model = _parse_module("mini", ast.parse(bron))
    assert model.imports["putten"] == ("selectie", "putten")
    assert model.imports["alle_drempels"] == ("randvoorzieningen", "alle_drempels")


def test_elke_check_declareert_beide() -> None:
    """Geen enkele geregistreerde check mist een van de twee declaraties."""
    ontbreekt = [
        cid
        for cid in CHECK_IDS
        if not hasattr(REGISTRY[cid], "rollen") or not hasattr(REGISTRY[cid], "kenmerken")
    ]
    assert not ontbreekt, f"checks zonder declaratie: {ontbreekt}"


def test_derived_props_dekt_elke_eigenschap() -> None:
    """Elke waardedragende `Node`/`Conduit`-eigenschap staat in `DERIVED_PROPS`.

    De AST-sweep vertaalt een eigenschapslezing (`node.bovenkant`) naar haar GWSW-kenmerk
    via `DERIVED_PROPS`. Zet iemand er een nieuwe eigenschap bij zonder die tabel bij te
    werken, dan ziet de sweep dat kenmerk niet -- een stille valse groen. Deze test dwingt
    af dat elke eigenschap óf een kenmerk oplevert (in de tabel) óf uitdrukkelijk als
    geometrie is uitgezonderd.
    """
    for klass in (Node, Conduit):
        eigenschappen = {naam for naam in dir(klass) if isinstance(getattr(klass, naam), property)}
        ongedekt = eigenschappen - set(DERIVED_PROPS) - GEOMETRIE_EIGENSCHAPPEN
        assert not ongedekt, (
            f"{klass.__name__}-eigenschappen zonder vertaling in DERIVED_PROPS: "
            f"{sorted(ongedekt)}. Voeg ze toe met hun GWSW-kenmerk, of aan "
            "GEOMETRIE_EIGENSCHAPPEN."
        )


def test_register_weigert_check_zonder_declaratie() -> None:
    """`register()` weigert een check die `rollen` of `kenmerken` niet declareert."""

    class ZonderDeclaratie(Check):
        id = "TST-000"
        title = "test"
        severity = Severity.WARNING
        dimension = Dimension.CONSISTENCY

        def run(self, context):  # type: ignore[no-untyped-def]
            return iter(())

    with pytest.raises(ValueError, match="rollen"):
        register(ZonderDeclaratie)
    assert "TST-000" not in REGISTRY


def test_alleen_de_bereikbaarheids_en_dekkingschecks_gaan_over_het_persnet() -> None:
    """Alleen wie het persnet echt leest declareert `mechanischeleidingen`.

    Het mechanische riool wordt inhoudelijk niet getoetst; het draagt alleen
    connectiviteit voor de vraag of vrijverval ergens uitkomt (BO-54). Die vraag stellen
    NET-001, NET-002 en NET-008 (die zijn lozingspunten uit dezelfde laag haalt); de
    overige NET-checks draaien op het zuivere vrijverval. NET-004 (kringlopen) is daar
    het scherpste geval: elke ongerichte persleidingkant zou er een kringloop van twee
    knopen zijn, dus die check mág het persnet niet zien -- en hoort het dan ook niet te
    declareren.

    EXT-009 staat er sinds issue #104 bij, om een andere reden: die leest de persleiding
    niet als kant in een graaf maar als geometrie langs een straat. Ligt er persleiding
    langs, dan is dat een drukriolering-indicatie en wordt de straat niet beoordeeld.

    RVZ-006 staat er sinds issue #106 bij, om een derde reden, en juist niet als kant: de
    check blijft op het zuivere vrijverval rekenen (een persleiding is geen afvoereindpunt,
    BO-82) en leest het persnet alleen om te kúnnen zeggen waar het water dan wél heen
    gaat. Zou zij het als kant lezen, dan verdween het gebrek in plaats van dat het
    verklaard werd.

    TOP-019, TOP-022 en TOP-023 staan er sinds issue #130 bij, om een vierde reden: zij
    lezen het persnet niet als kant maar om een hulpstuk of functieloze knoop die zuiver
    in het drukriool zit (alleen mechanische leidingen, geen vrijvervalrioolleiding) buiten
    hun toets te laten -- dat riool valt buiten het checkregister. Zij vergelijken
    `mechanischeleidingen` met `vrijvervalrioolleidingen` in `zuiver_mechanische_knopen`.
    """
    met_persnet = {cid for cid in CHECK_IDS if "mechanischeleidingen" in REGISTRY[cid].rollen}

    assert met_persnet == {
        "EXT-009",
        "NET-001",
        "NET-002",
        "NET-008",
        "RVZ-006",
        "TOP-019",
        "TOP-022",
        "TOP-023",
    }


def test_alleen_een_check_zonder_rol_omschrijft_zijn_populatie() -> None:
    """Een `populatie_omschrijving` staat alleen waar de rol niet de populatie is (issue #96/#137).

    De omschrijving gaat in de regel "Toetst ..." vóór de klassen van de rollen
    (`_toetst_regel`). Zonder rol is dat de enige populatiebron (ADM-007 leest
    `[[puttyperegels]]`, RVZ-011 loopt de overstortdrempel-index). HGT-011 houdt sinds
    issue #137 wél een rol -- de aanvoerende vrijvervalstreng -- maar zijn populatie zijn
    de overstortdrempels, dus ook daar is de omschrijving nodig en geen dode tekst.
    ATTR-014 staat er met opzet niet bij: die gaat werkelijk over de hele export.
    """
    met_omschrijving = {cid for cid in CHECK_IDS if REGISTRY[cid].populatie_omschrijving}

    assert met_omschrijving == {"ADM-007", "HGT-011", "RVZ-011"}
    # Alleen HGT-011 draagt de omschrijving náást een rol; de andere twee hebben er geen.
    assert not REGISTRY["ADM-007"].rollen and not REGISTRY["RVZ-011"].rollen
    assert REGISTRY["HGT-011"].rollen == ("vrijvervalrioolleidingen",)


def test_alleen_de_twee_instantietellers_zijn_zo_gemarkeerd() -> None:
    """Wie `examined()` op instanties zet, zegt dat erbij (issue #77).

    De scope-taxonomie van BO-58 is met de hand gedeclareerd: er is geen manier om uit
    `examined()` af te leiden of het getal objecten of kenmerkinstanties telt. Deze
    lijst is daarom de plek waar dat besluit staat; komt er een derde teller bij zonder
    vlag, dan noemt het rapport zijn getal "bekeken objecten" terwijl het dat niet is.
    """
    gemarkeerd = {cid for cid in CHECK_IDS if REGISTRY[cid].telt_instanties}

    assert gemarkeerd == {"ATTR-014", "BTR-006"}


def _bouwt_finding(bron: str) -> bool:
    """Of deze broncode ergens een `Finding` construeert.

    Twee vormen: `Finding(...)` en `base.Finding(...)`. Een annotatie of een returntype
    is geen aanroep en telt niet mee -- `Finding` komt als `Iterator[Finding]` door de
    hele checkmap voor, dus een tekstsweep op `Finding(` zou het halve bestand vlaggen.

    De grens: een import onder een andere naam (`from ... import Finding as F`) is
    statisch niet te volgen en ontsnapt. Dat is een bewuste rest, geen omissie -- zij
    vergt een naamresolutie die deze sweep niet doet.
    """
    return any(
        isinstance(knoop, ast.Call)
        and (
            (isinstance(knoop.func, ast.Name) and knoop.func.id == "Finding")
            or (isinstance(knoop.func, ast.Attribute) and knoop.func.attr == "Finding")
        )
        for knoop in ast.walk(ast.parse(bron))
    )


# Issue #142: een check die een `[drempels]`-sleutel leest, hoort die drempel ook in haar
# bevinding te zetten (`drempel=`), zodat elke rij zonder `checks.toml` herleidbaar is. De
# uitzonderingen zijn checks waar de gelezen drempel de bevinding niet als grens stuurt maar
# als filter, classificatie of geometrie-hulp -- daar zou een `drempel=` de lezer op het
# verkeerde been zetten.
GEEN_DREMPELMELDING = {
    "EXT-003": "ext_watergang_buffer_m is de zoekstraal; de bevinding is een geometrisch "
    "bevestigde doorkruising en geen drempeloverschrijding.",
    "NET-004": "bob_sprong_m classificeert welke kringen als putsprong wegvallen; de gemelde "
    "kring is er juist geen, dus de drempel stuurt de bevinding niet.",
    "RVZ-006": "snapping_tolerantie_m is een geometrie-hulp in de aanwijzing bij het gebrek, "
    "niet de grens waarop het gemengde deelstelsel gemeld wordt.",
    "TOP-018": "spike_hoek_graden en dubbele_vertex_tolerantie_m zijn twee losse "
    "geometriegrenzen; een bevinding kan beide overschrijden, dus geen enkele waarde is "
    "'de drempel' van de rij.",
}


@pytest.mark.parametrize("check_id", CODE_CHECK_IDS)
def test_een_drempellezende_check_vult_drempel(check_id: str) -> None:
    """Leest een check een `[drempels]`-sleutel, dan zet zij die drempel in haar bevinding.

    De AST-sweep leidt per check af welke `[drempels]`-sleutels zij in haar eigen methoden
    leest; leest zij er geen, dan valt er niets af te dwingen. Leest zij er wel een, dan hoort
    `drempel=` in een van haar `self.finding(...)`-aanroepen te staan -- tenzij de sleutel in
    `GEEN_DREMPELMELDING` als filter of classificatie verantwoord is.
    """
    sleutels = drempelsleutels_van_check(REGISTRY[check_id])
    if not sleutels:
        return
    if check_id in GEEN_DREMPELMELDING:
        return
    assert "drempel" in bevinding_kwargs_van_check(REGISTRY[check_id]), (
        f"{check_id} leest de drempel(s) {sorted(sleutels)} maar zet geen `drempel=` in haar "
        'bevinding (issue #142). Voeg `drempel=f"{waarde:g} (drempels.<sleutel>)"` toe, of '
        "verantwoord de check in GEEN_DREMPELMELDING als de drempel een filter is."
    )


def test_geen_drempelmelding_is_niet_verlopen() -> None:
    """Elke naam in `GEEN_DREMPELMELDING` is een geregistreerde, drempellezende check.

    Zonder deze bewaking blijft een uitzondering staan nadat de check verdween of geen
    drempel meer leest, en dekt zij stil een toekomstige check met dezelfde naam.
    """
    for check_id in GEEN_DREMPELMELDING:
        assert check_id in REGISTRY, f"{check_id} in GEEN_DREMPELMELDING bestaat niet meer"
        assert drempelsleutels_van_check(REGISTRY[check_id]), (
            f"{check_id} leest geen `[drempels]`-sleutel meer; haal het uit GEEN_DREMPELMELDING"
        )


def test_alleen_de_gedeelde_fabriek_bouwt_een_finding() -> None:
    """Elke bevinding komt uit `Check.finding()` en nergens anders (issue #118).

    Die fabriek is de plek waar `typing_reliable` via `context.is_reliable()` gezet
    wordt. Wie zelf een `Finding(` bouwt zet die vlag met de hand -- ATTR-014 en
    ATTR-015 deden dat, allebei op een hardgecodeerde `True` -- en dan hangt de
    typeringspoort af van wie er toevallig aan denkt.

    De sweep loopt over heel `src/` en niet alleen over `checks/`: een bevinding buiten
    de checkmap zou dezelfde vlag met de hand zetten en al helemaal geen check achter
    zich hebben. Alleen `checks/base.py` is vrijgesteld, want daar staat de fabriek.
    """
    src = WORTEL / "src"

    overtreders = sorted(
        pad.relative_to(src).as_posix()
        for pad in src.rglob("*.py")
        if pad.relative_to(src).as_posix() != "nlriochecker/checks/base.py"
        and _bouwt_finding(pad.read_text(encoding="utf-8"))
    )

    assert overtreders == []


def test_de_findingsweep_kan_werkelijk_afgaan() -> None:
    """De tegenproef: de sweep herkent een eigen constructor ook echt.

    Zonder haar zou een sweep die alleen naar de verkeerde knoopsoort kijkt hier groen
    blijven terwijl `checks/attributen.py` twee constructors draagt -- precies de
    toestand van vóór dit issue.
    """
    assert _bouwt_finding("yield Finding(check_id=self.id, systemisch=True)")
    # De gekwalificeerde vorm: `from nlriochecker.checks import base` en dan `base.Finding`.
    assert _bouwt_finding("yield base.Finding(check_id=self.id)")
    # Een annotatie of een returntype is geen constructie, en de fabriek zelf ook niet.
    assert not _bouwt_finding("def run(self) -> Iterator[Finding]:\n    return iter(())")
    assert not _bouwt_finding("yield self.finding(context, uri, label, boodschap)")
