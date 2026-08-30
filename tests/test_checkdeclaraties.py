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
from checkdeclaratie_analyse import DERIVED_PROPS, analyseer_alle_checks
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
    """
    met_persnet = {cid for cid in CHECK_IDS if "mechanischeleidingen" in REGISTRY[cid].rollen}

    assert met_persnet == {"EXT-009", "NET-001", "NET-002", "NET-008", "RVZ-006"}


def test_alleen_een_check_zonder_rol_omschrijft_zijn_populatie() -> None:
    """Wie geen rol declareert, zegt zelf welke deelpopulatie hij bekeek (issue #96).

    `populatie_omschrijving` vult de regel "Toetst ..." waar anders "de hele export"
    zou staan, en die terugval treedt alleen op zonder rollen. Op een check mét rollen
    is de zin dus dode tekst; deze test houdt hem daar weg. ATTR-014 heeft ook geen
    rollen en staat er met opzet niet bij: die gaat werkelijk over de hele export.
    """
    met_omschrijving = {cid for cid in CHECK_IDS if REGISTRY[cid].populatie_omschrijving}

    assert met_omschrijving == {"ADM-007", "RVZ-011"}
    assert all(not REGISTRY[cid].rollen for cid in met_omschrijving)


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
