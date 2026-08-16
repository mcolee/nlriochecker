"""Tests voor de aggregaties en de typeringspoort."""

from __future__ import annotations

from pathlib import Path

from gwswpijplijn.analysis import analyze
from gwswpijplijn.report import read_detail_report

# Het MdsPlan-uittreksel telt 20 meldingregels met samen Aantal 155.
MINI_MDS_TOTAL = 155


def test_total_is_weighted_sum(mini_mds: Path) -> None:
    analysis = analyze(read_detail_report(mini_mds))

    assert analysis.total_count == MINI_MDS_TOTAL


def test_aggregations_add_up_to_the_total(mini_mds: Path) -> None:
    analysis = analyze(read_detail_report(mini_mds))

    assert int(analysis.by_message_type["Aantal"].sum()) == MINI_MDS_TOTAL
    assert int(analysis.by_object_type["Aantal"].sum()) == MINI_MDS_TOTAL
    assert int(analysis.by_message_and_object_type["Aantal"].sum()) == MINI_MDS_TOTAL
    assert int(analysis.by_message_type["Regels"].sum()) == len(analysis.report.messages)


def test_aggregation_is_sorted_descending(mini_mds: Path) -> None:
    by_message_type = analyze(read_detail_report(mini_mds)).by_message_type

    assert list(by_message_type["Aantal"]) == sorted(by_message_type["Aantal"], reverse=True)
    assert by_message_type.iloc[0]["Type Melding"].startswith("Collectie ontbreekt")


def test_typing_gate_counts_unique_objects(mini_mds: Path) -> None:
    gate = analyze(read_detail_report(mini_mds)).typing_gate

    # 16 benoemde objecten, waarvan 4 Overstortputten te globaal getypeerd zijn.
    assert gate.named_object_count == 16
    assert gate.too_generic_count == 4
    assert gate.score == 75.0
    assert list(gate.objects.columns) == ["Type object", "Naam"]
    assert set(gate.objects["Type object"]) == {"Overstortput"}


def test_typing_gate_without_messages_is_complete(mini_hyd: Path) -> None:
    gate = analyze(read_detail_report(mini_hyd)).typing_gate

    assert gate.too_generic_count == 0
    assert gate.score == 100.0
    assert gate.objects.empty
