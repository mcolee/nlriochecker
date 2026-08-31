"""Tests voor NET-005, NET-006 en NET-008 op kleine fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import load_dataset

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, run_checks

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

NIEUWE_NET_IDS = ["NET-005", "NET-006", "NET-008"]


def uitkomst(pad: Path, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture en geeft de volledige uitkomst."""
    dataset = load_dataset(pad, [])
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def labels(outcome: CheckOutcome) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in outcome.findings)


@pytest.mark.parametrize(
    ("bestand", "check_id", "verwachte_labels"),
    [
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


def test_net005_noemt_het_afwijkende_type_en_dat_van_de_buren() -> None:
    bevinding = uitkomst(TTL_DIR / "net005_afwijkend_stelseltype.ttl", "NET-005").findings[0]

    assert bevinding.details["stelseltype"] == "hemelwater"
    assert bevinding.details["buurtypen"] == ["gemengd"]


def test_net006_meldt_de_gerichte_koppeling_op_de_knoop() -> None:
    # Op knoop B stroomt gemengd binnen en gaat als hemelwater verder; `gemengd → hemelwater`
    # staat niet in de koppelregels (matrix #3), dus de bevinding noemt die gerichte koppeling.
    bevinding = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-006").findings[0]

    assert bevinding.details["koppelingen"] == ["gemengd→hemelwater"]


def test_net005_zwijgt_over_een_streng_aan_de_rand() -> None:
    # De koppeling uit NET-006 is voor NET-005 geen afwijking: beide strengen
    # hebben maar een buur en die is nu eenmaal van het andere type.
    outcome = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-005")

    assert outcome.findings == []


def test_net006_staat_vuilwater_naar_gemengd_toe() -> None:
    """Gemengd benedenstrooms van vuilwater staat in de koppelregels (matrix #8: Ja).

    Op knoop B stroomt vuilwater binnen en gaat het als gemengd verder. Beide strengen
    hebben een betrouwbare richting (BOB daalt, geometrie mee), dus de koppeling is gericht
    te toetsen; `vuilwater → gemengd` is toegestaan en NET-006 zwijgt.
    """
    outcome = uitkomst(TTL_DIR / "net006_vuilwater_naar_gemengd.ttl", "NET-006")

    assert outcome.findings == []


def test_net006_staat_doorgaand_gemengd_hoofdriool_met_vuilwatertak_toe() -> None:
    """Een doorgaand gemengd hoofdriool met een aansluitende vuilwatertak is conform.

    Op knoop B stroomt gemengd zowel in als uit (het hoofdriool loopt door) en sluit een
    vuilwatertak aan die instroomt. De gerichte koppelingen zijn `gemengd → gemengd` en
    `vuilwater → gemengd`, allebei in de koppelregels, dus NET-006 zwijgt.
    """
    outcome = uitkomst(TTL_DIR / "net006_doorgaand_gemengd_hoofdriool.ttl", "NET-006")

    assert outcome.findings == []


def test_net006_meldt_gemengd_dat_op_vuilwater_uitkomt() -> None:
    """De omgekeerde richting is wél een koppelingsfout (matrix #2: Nee).

    Gemengd bovenstrooms van vuilwater betekent gemengd afvalwater in een vuilwaterriool;
    `gemengd → vuilwater` staat niet in de koppelregels en blijft een melding op de knoop.
    """
    outcome = uitkomst(TTL_DIR / "net006_gemengd_naar_vuilwater.ttl", "NET-006")

    assert labels(outcome) == ["B"]
    assert outcome.findings[0].details["koppelingen"] == ["gemengd→vuilwater"]


def test_net006_staat_hemelwater_naar_gemengd_toe() -> None:
    """De whitelist is richting-bewust: `hemelwater → gemengd` mag (matrix #15: Ja).

    De oude ad-hoc regel meldde elke gemengd+hemelwater-knoop; de koppelregels laten deze
    richting toe. Zonder deze test zou een te ruime whitelist niet opvallen.
    """
    outcome = uitkomst(TTL_DIR / "net006_hemelwater_naar_gemengd.ttl", "NET-006")

    assert outcome.findings == []


def test_net006_meldt_dit_naar_vuilwater() -> None:
    """De eigen tag `DIT` (issue #126) wordt herkend en getoetst (matrix #30: Nee).

    Een DIT-riool (grondwater) mag niet bovenstrooms van een vuilwaterriool liggen;
    `DIT → vuilwater` staat niet in de koppelregels.
    """
    outcome = uitkomst(TTL_DIR / "net006_dit_naar_vuilwater.ttl", "NET-006")

    assert labels(outcome) == ["B"]
    assert outcome.findings[0].details["koppelingen"] == ["DIT→vuilwater"]


def test_net006_telt_een_koppeling_zonder_betrouwbare_richting_maar_meldt_die_niet() -> None:
    """Wat niet gericht te beoordelen is, komt in de toelichting en niet als bevinding.

    Op knoop B komen gemengd en hemelwater samen, maar de gemengde streng heeft een
    stijgende BOB (NET-009 spreekt haar tegen), dus haar richting is onbetrouwbaar. De
    koppeling valt dan niet in een richting te leggen: geen bevinding, wel een telling.
    """
    outcome = uitkomst(TTL_DIR / "net006_onbetrouwbare_richting.ttl", "NET-006")

    assert outcome.findings == []
    assert any("zonder betrouwbare stroomrichting" in note for note in outcome.notes)


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
