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


def test_net006_meldt_beide_stelseltypen_op_de_knoop() -> None:
    bevinding = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-006").findings[0]

    assert bevinding.details["stelseltypen"] == ["gemengd", "hemelwater"]


def test_net005_zwijgt_over_een_streng_aan_de_rand() -> None:
    # De koppeling uit NET-006 is voor NET-005 geen afwijking: beide strengen
    # hebben maar een buur en die is nu eenmaal van het andere type.
    outcome = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-005")

    assert outcome.findings == []


def test_net006_dempt_vuilwater_dat_op_gemengd_uitkomt() -> None:
    """Gemengd benedenstrooms van vuilwater is normaal en hoort niet gemeld (issue #97).

    Op knoop B stroomt vuilwater binnen en gaat het als gemengd verder. Beide strengen
    hebben een betrouwbare richting (BOB daalt, geometrie mee, NET-009 spreekt ze niet
    tegen), dus de koppeling is de goede kant op en NET-006 zwijgt. De toelichting maakt
    de demping zichtbaar in plaats van haar te verzwijgen.
    """
    outcome = uitkomst(TTL_DIR / "net006_vuilwater_naar_gemengd.ttl", "NET-006")

    assert outcome.findings == []
    assert any("vuilwater" in note and "gemengd" in note for note in outcome.notes)


def test_net006_dempt_doorgaand_gemengd_hoofdriool_met_vuilwatertak() -> None:
    """Een doorgaand gemengd hoofdriool met een vuilwatertak is geen fout (issue #97, optie B).

    Op knoop B stroomt gemengd zowel in als uit (het hoofdriool loopt door) en sluit een
    vuilwatertak aan die instroomt. De foutvorm -- vuilwater benedenstrooms van gemengd
    (gemengd ín én vuilwater úit) -- is afwezig en alle strengen zijn betrouwbaar gericht,
    dus NET-006 zwijgt. De strikte regel (optie A) meldde de knoop nog wél.
    """
    outcome = uitkomst(TTL_DIR / "net006_doorgaand_gemengd_hoofdriool.ttl", "NET-006")

    assert outcome.findings == []
    assert any("vuilwater" in note and "gemengd" in note for note in outcome.notes)


def test_net006_meldt_gemengd_dat_op_vuilwater_uitkomt() -> None:
    """De omgekeerde richting is wél een koppelingsfout (issue #97).

    Gemengd bovenstrooms van vuilwater betekent gemengd afvalwater in een vuilwaterriool;
    dat blijft een melding op de knoop.
    """
    outcome = uitkomst(TTL_DIR / "net006_gemengd_naar_vuilwater.ttl", "NET-006")

    assert labels(outcome) == ["B"]
    assert outcome.findings[0].details["stelseltypen"] == ["gemengd", "vuilwater"]


def test_net006_meldt_andere_typeparen_ongewijzigd() -> None:
    """De demping geldt alleen voor het paar gemengd+vuilwater; de rest verandert niet.

    Op de bestaande fixture komen gemengd en hemelwater samen -- geen vuilwater -- dus de
    richting-nuance van issue #97 raakt haar niet en de melding blijft staan.
    """
    outcome = uitkomst(TTL_DIR / "net006_koppeling_stelseltypen.ttl", "NET-006")

    assert labels(outcome) == ["B"]


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
