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

import pytest
from gwsw_orox_helpers.dataset import Conduit, Node

import nlriochecker.checks  # noqa: F401  (vult de registry)
from checkdeclaratie_analyse import DERIVED_PROPS, analyseer_alle_checks
from nlriochecker.checks.base import REGISTRY, Check, Dimension, Severity, SkeletonCheck, register

# De eigenschappen van `Node`/`Conduit` die geen GWSW-kenmerk lezen maar de geometrie: de
# z-waarde uit de GML-lijn. Ze horen daarom niet in `DERIVED_PROPS`.
GEOMETRIE_EIGENSCHAPPEN = frozenset({"z_start", "z_end"})

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


def test_alleen_de_bereikbaarheidschecks_gaan_over_het_persnet() -> None:
    """Alleen wie de bereikbaarheidsgraaf leest declareert `mechanischeleidingen`.

    Het mechanische riool wordt inhoudelijk niet getoetst; het draagt alleen
    connectiviteit voor de vraag of vrijverval ergens uitkomt (BO-54). Die vraag stellen
    NET-001, NET-002 en NET-008 (die zijn lozingspunten uit dezelfde laag haalt), en sinds
    issue #80 ook NET-009: die legt de harde afvoerrichting vast met een ongerichte graaf
    tot aan een bereikbaar lozingspunt en leest daarvoor het persnet mee. De overige
    NET-checks draaien op het zuivere vrijverval. NET-004 (kringlopen) is daar het
    scherpste geval: elke ongerichte persleidingkant zou er een kringloop van twee knopen
    zijn, dus die check mág het persnet niet zien -- en hoort het dan ook niet te
    declareren.
    """
    met_persnet = {cid for cid in CHECK_IDS if "mechanischeleidingen" in REGISTRY[cid].rollen}

    assert met_persnet == {"NET-001", "NET-002", "NET-008", "NET-009"}


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
