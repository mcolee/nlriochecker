"""Tests voor de meetkundige TOP-checks op fixtures met precies een defect."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, Finding, run_checks
from gwswpijplijn.dataset import load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

MEETKUNDIGE_IDS = [
    "TOP-006",
    "TOP-007",
    "TOP-008",
    "TOP-009",
    "TOP-010",
    "TOP-011",
    "TOP-013",
    "TOP-014",
    "TOP-015",
    "TOP-016",
    "TOP-017",
    "TOP-018",
    "TOP-019",
    "TOP-020",
    "TOP-021",
]


def fixtureconfig() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten.

    De fixtures spelen zich af rond (1000, 2000): een klein, leesbaar assenstelsel
    dat niet in het echte RD-vlak ligt. TOP-009 zou daar zonder meer op aanslaan.
    Dat het bereik hier verzet kan worden is precies waar de configureerbaarheid
    voor is; de standaardwaarden blijven het echte RD-bereik.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def bevindingen(pad: Path, check_id: str, config: CheckConfig | None = None) -> list[Finding]:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(pad)
    context = CheckContext(dataset=dataset, config=config or fixtureconfig())
    return run_checks(context, [check_id]).outcomes[0].findings


def labels(gevonden: list[Finding]) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in gevonden)


@pytest.mark.parametrize(
    ("bestand", "check_id", "verwachte_labels"),
    [
        ("top006_overlappende_streng.ttl", "TOP-006", ["1"]),
        ("top007_nul_lengte.ttl", "TOP-007", ["2"]),
        ("top008_boog.ttl", "TOP-008", ["1"]),
        ("top009_buiten_rd.ttl", "TOP-009", ["1", "B"]),
        ("top010_buffer_kruising.ttl", "TOP-010", ["1"]),
        ("top011_hartlijnkruising.ttl", "TOP-011", ["1"]),
        ("top013_parallel.ttl", "TOP-013", ["1", "2", "3"]),
        ("top014_vijf_strengen.ttl", "TOP-014", ["A"]),
        ("top015_multipart.ttl", "TOP-015", ["1"]),
        ("top016_ongeldige_geometrie.ttl", "TOP-016", ["1"]),
        ("top017_zelfkruisend.ttl", "TOP-017", ["1"]),
        ("top018_spike.ttl", "TOP-018", ["1"]),
        ("top019_pseudoknoop.ttl", "TOP-019", ["B"]),
        ("top020_omgekeerd_getekend.ttl", "TOP-020", ["1"]),
        ("top021_put_op_streng.ttl", "TOP-021", ["C"]),
    ],
)
def test_defect_wordt_gevonden(bestand: str, check_id: str, verwachte_labels: list[str]) -> None:
    gevonden = bevindingen(TTL_DIR / bestand, check_id)

    assert labels(gevonden) == verwachte_labels
    assert {finding.check_id for finding in gevonden} == {check_id}


@pytest.mark.parametrize("check_id", MEETKUNDIGE_IDS)
def test_schone_fixture_geeft_geen_bevinding(check_id: str) -> None:
    assert bevindingen(TTL_DIR / "schoon.ttl", check_id) == []


def test_top006_meldt_de_overlaplengte() -> None:
    bevinding = bevindingen(TTL_DIR / "top006_overlappende_streng.ttl", "TOP-006")[0]

    assert bevinding.details["overlaplengte_m"] == pytest.approx(50.0, abs=0.2)
    assert bevinding.details["object2_label"] == "2"


def test_top007_noemt_de_nul_lengte() -> None:
    bevinding = bevindingen(TTL_DIR / "top007_nul_lengte.ttl", "TOP-007")[0]

    assert "geen verloop" in bevinding.message


def test_top008_meldt_de_afwijking() -> None:
    bevinding = bevindingen(TTL_DIR / "top008_boog.ttl", "TOP-008")[0]

    assert bevinding.details["afwijking_m"] == pytest.approx(2.0, abs=0.01)
    assert bevinding.details["tussenpunten"] == 1


def test_top009_buiten_het_standaard_rd_bereik() -> None:
    # Met de standaardwaarden liggen de fixturecoordinaten zelf al buiten RD; dat
    # de check daarop aanslaat legt vast dat het bereik echt getoetst wordt.
    standaard = bevindingen(TTL_DIR / "schoon.ttl", "TOP-009", load_check_config())

    assert standaard
    assert all("RD-bereik" in finding.message for finding in standaard)


def test_top009_meldt_ook_wat_er_niet_getoetst_is() -> None:
    dataset = load_dataset(TTL_DIR / "top009_buiten_rd.ttl")
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    outcome = run_checks(context, ["TOP-009"]).outcomes[0]

    assert any("beheergebied" in note for note in outcome.notes)


def test_top010_slaat_niet_aan_zonder_maatvoering() -> None:
    # Dezelfde kruising, maar zonder diameter is er geen buis om te bufferen.
    assert bevindingen(TTL_DIR / "top011_hartlijnkruising.ttl", "TOP-010") == []


def test_top013_noemt_alle_parallelle_strengen() -> None:
    bevinding = bevindingen(TTL_DIR / "top013_parallel.ttl", "TOP-013")[0]

    assert bevinding.details["aantal"] == 3
    assert bevinding.details["maximum"] == 2


def test_top014_telt_de_aansluitingen() -> None:
    bevinding = bevindingen(TTL_DIR / "top014_vijf_strengen.ttl", "TOP-014")[0]

    assert bevinding.details["aantal"] == 5


def test_top018_meldt_de_scherpste_hoek() -> None:
    bevinding = bevindingen(TTL_DIR / "top018_spike.ttl", "TOP-018")[0]

    # Terugkeren en weer verder lopen levert twee scherpe knikken op: een bij het
    # keerpunt en een bij het punt waar de lijn de eerdere richting weer oppakt.
    assert bevinding.details["spikes"] == 2
    assert "graden" in bevinding.message


def test_top019_draait_niet_zonder_functieloze_klassen() -> None:
    config = fixtureconfig()
    config.klassen.functieloze_knoop = []

    dataset = load_dataset(TTL_DIR / "top019_pseudoknoop.ttl")
    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["TOP-019"]).outcomes[0]

    assert outcome.findings == []
    assert any("niet gedraaid" in note for note in outcome.notes)


def test_top020_noemt_beide_putten() -> None:
    bevinding = bevindingen(TTL_DIR / "top020_omgekeerd_getekend.ttl", "TOP-020")[0]

    assert bevinding.details["administratief_begin"] == "A"
    assert bevinding.details["administratief_eind"] == "B"


def test_top021_meldt_de_streng_waarlangs_de_put_ligt() -> None:
    bevinding = bevindingen(TTL_DIR / "top021_put_op_streng.ttl", "TOP-021")[0]

    assert bevinding.details["streng"] == "1"
    assert bevinding.details["afstand_m"] == pytest.approx(0.1, abs=0.01)


def test_top021_meldt_niets_bij_een_echt_losliggende_put() -> None:
    # TOP-001 vindt deze put wel; TOP-021 is de verfijning en hoort te zwijgen.
    assert bevindingen(TTL_DIR / "top001_losliggende_put.ttl", "TOP-021") == []
    assert bevindingen(TTL_DIR / "top001_losliggende_put.ttl", "TOP-001") != []


def test_paarmeldingen_dragen_het_tweede_object() -> None:
    """De uitvoer heeft de URI van de tegenpartij nodig, niet alleen haar label.

    TOP-005, TOP-006, TOP-010 en TOP-011 melden over precies twee objecten; zonder
    de tweede URI is de melding in CSV en GIS niet aan beide kanten te koppelen.
    """
    bevinding = bevindingen(TTL_DIR / "top011_hartlijnkruising.ttl", "TOP-011")[0]

    assert bevinding.details["object2_uri"].startswith("http")
    assert bevinding.details["object2_label"]
