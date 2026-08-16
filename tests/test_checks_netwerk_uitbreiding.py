"""Tests voor NET-003, NET-005, NET-006 en NET-008 op kleine fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, CheckOutcome, run_checks
from gwswpijplijn.dataset import load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

NIEUWE_NET_IDS = ["NET-003", "NET-005", "NET-006", "NET-008"]


def uitkomst(pad: Path, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture en geeft de volledige uitkomst."""
    dataset = load_dataset(pad)
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def labels(outcome: CheckOutcome) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in outcome.findings)


@pytest.mark.parametrize(
    ("bestand", "check_id", "verwachte_labels"),
    [
        ("net003_tegen_de_richting.ttl", "NET-003", ["1"]),
        ("net005_afwijkend_stelseltype.ttl", "NET-005", ["2"]),
        ("net006_koppeling_stelseltypen.ttl", "NET-006", ["B"]),
        ("net008_veel_lozingspunten.ttl", "NET-008", ["L1", "L2", "L3"]),
    ],
)
def test_defect_wordt_gevonden(bestand: str, check_id: str, verwachte_labels: list[str]) -> None:
    outcome = uitkomst(TTL_DIR / bestand, check_id)

    assert labels(outcome) == verwachte_labels


@pytest.mark.parametrize("check_id", NIEUWE_NET_IDS)
def test_schone_fixture_geeft_geen_bevinding(check_id: str) -> None:
    assert uitkomst(TTL_DIR / "net_schoon.ttl", check_id).findings == []


def test_net003_meldt_de_stijging() -> None:
    bevinding = uitkomst(TTL_DIR / "net003_tegen_de_richting.ttl", "NET-003").findings[0]

    assert bevinding.details["stijging_m"] == pytest.approx(0.5)
    assert bevinding.details["bob_begin"] == pytest.approx(10.0)
    assert bevinding.details["bob_eind"] == pytest.approx(10.5)


def test_net003_meldt_hoeveel_strengen_geen_bob_hebben() -> None:
    # In net_schoon.ttl staan geen BOB's; dat mag niet als "alles in orde" lezen.
    outcome = uitkomst(TTL_DIR / "net_schoon.ttl", "NET-003")

    assert outcome.examined == 0
    assert any("missen een BOB" in note for note in outcome.notes)


def test_net005_noemt_het_afwijkende_type_en_dat_van_de_buren() -> None:
    bevinding = uitkomst(TTL_DIR / "net005_afwijkend_stelseltype.ttl", "NET-005").findings[0]

    assert bevinding.details["stelseltype"] == "hemelwater"
    assert bevinding.details["buurtypen"] == ["gemengd"]


def test_net006_meldt_beide_stelseltypen_op_de_knoop() -> None:
    bevinding = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-006").findings[0]

    assert bevinding.details["stelseltypen"] == ["gemengd", "hemelwater"]


def test_net005_zwijgt_over_een_streng_aan_de_rand() -> None:
    # De koppeling uit NET-006 is voor NET-005 geen afwijking: beide strengen
    # hebben maar een buur en die is nu eenmaal van het andere type.
    outcome = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-005")

    assert outcome.findings == []


def test_net008_telt_de_lozingspunten_en_de_knopen() -> None:
    bevinding = uitkomst(TTL_DIR / "net008_veel_lozingspunten.ttl", "NET-008").findings[0]

    assert bevinding.details["lozingspunten"] == 3
    assert bevinding.details["knopen_in_deelstelsel"] == 4


def test_net008_zwijgt_bij_een_ruimer_maximum() -> None:
    config = load_check_config()
    config.drempels.lozingspunten_per_deelstelsel = 5

    assert uitkomst(TTL_DIR / "net008_veel_lozingspunten.ttl", "NET-008", config).findings == []


def test_stelseltypen_zonder_config_meldt_dat() -> None:
    config = load_check_config()
    config.klassen.stelseltypen = {}
    outcome = uitkomst(TTL_DIR / "net005_afwijkend_stelseltype.ttl", "NET-005", config)

    assert outcome.findings == []
    assert any("geen stelseltypen geconfigureerd" in note for note in outcome.notes)
