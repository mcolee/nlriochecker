"""Tests voor de vergelijking van twee nulmetingen."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.analysis import analyze
from nlriochecker.comparison import ChangeStatus, MetingComparison, compare_metingen
from nlriochecker.config import load_coverage_config
from nlriochecker.errors import ComparisonError
from nlriochecker.meting import laad_nulmeting

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


def _later(paden: list[Path], tmp_path: Path) -> list[Path]:
    """Maakt een tweede meetmoment met bekende verschillen.

    Uit het Hyd-rapport verdwijnen de twee LengteLeiding_val-meldingen en er komt
    een verzonnen melding bij, zodat de delta's met de hand narekenbaar zijn.
    """
    nieuw = []
    for pad in paden:
        regels = pad.read_text(encoding="utf-8").splitlines()
        regels = [
            r.replace("2026-08-16T12:51:51", "2027-01-05T09:00:00")
            .replace("2026-08-16T12:55:55", "2027-01-05T09:20:00")
            .replace("2026-08-16T13:00:01", "2027-01-05T09:40:00")
            for r in regels
        ]
        if "hyd" in pad.name:
            regels = [r for r in regels if "LengteLeiding_val" not in r]
            regels.append(
                '"knpNIEUW";"LengteLeiding_val";"999 (decimal) ";"Violation";"verzonnen";'
                '"hasValue";"";"Focus-node: type=Inspectieput, label=NIEUW";'
            )
        doel = tmp_path / f"later_{pad.name}"
        doel.write_text("\n".join(regels) + "\n", encoding="utf-8")
        nieuw.append(doel)
    return nieuw


@pytest.fixture
def comparison(shacl_drieluik: list[Path], tmp_path: Path) -> MetingComparison:
    """De vergelijking van de mini-nulmeting met een later meetmoment."""
    eerder = analyze(laad_nulmeting(shacl_drieluik, VEREIST))
    later = analyze(laad_nulmeting(_later(shacl_drieluik, tmp_path), VEREIST))
    return compare_metingen(eerder, later, load_coverage_config())


def _cfk(comparison: MetingComparison, cfk: str):
    """Zoekt de vergelijking van een conformiteitsklasse op."""
    return next(item for item in comparison.per_cfk if item.cfk == cfk)


def test_dataset_en_volgorde(comparison: MetingComparison) -> None:
    assert comparison.dataset_file == "dewolden_orox.ttl"
    assert comparison.timestamps_out_of_order is False


def test_delta_per_vorm(comparison: MetingComparison) -> None:
    hyd = _cfk(comparison, "Hyd")
    tabel = hyd.by_shape.set_index("Source")

    # Twee LengteLeiding_val-meldingen weg, een nieuwe erbij.
    assert int(tabel.loc["LengteLeiding_val", "Eerder"]) == 2
    assert int(tabel.loc["LengteLeiding_val", "Later"]) == 1
    assert hyd.total_delta == -1


def test_objectniveau_op_focus_node(comparison: MetingComparison) -> None:
    telling = _cfk(comparison, "Hyd").status_counts()

    assert telling[ChangeStatus.RESOLVED.value] == 2
    assert telling[ChangeStatus.NEW.value] == 1


def test_ongewijzigde_cfk(comparison: MetingComparison) -> None:
    mdsplan = _cfk(comparison, "MdsPlan")

    assert mdsplan.total_delta == 0
    assert mdsplan.status_counts()[ChangeStatus.REMAINING.value] > 0


def test_zelfvergelijking_geeft_overal_nul(shacl_drieluik: list[Path]) -> None:
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))
    comparison = compare_metingen(analyse, analyse, load_coverage_config())

    assert comparison.timestamps_out_of_order is True
    for item in comparison.per_cfk:
        assert item.total_delta == 0
        assert int(item.by_shape["Verschil"].abs().sum()) == 0
        assert set(item.object_changes["Status"]) == {ChangeStatus.REMAINING.value}
    assert not comparison.coverage_changes["Gewijzigd"].any()


def test_verschillende_datasets(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    afwijkend = []
    for pad in shacl_drieluik:
        doel = tmp_path / f"ander_{pad.name}"
        doel.write_text(
            pad.read_text(encoding="utf-8").replace("dewolden_orox.ttl", "elders.ttl"),
            encoding="utf-8",
        )
        afwijkend.append(doel)

    eerder = analyze(laad_nulmeting(shacl_drieluik, VEREIST))
    later = analyze(laad_nulmeting(afwijkend, VEREIST))

    with pytest.raises(ComparisonError, match="verschillende datasets"):
        compare_metingen(eerder, later, load_coverage_config())


def test_vergelijk_weigert_ongelijke_cfk_sets(
    shacl_drieluik: list[Path], mini_hyd_shacl: Path
) -> None:
    """Een daling die uit een kleinere getoetste set komt is geen verbetering.

    Zonder deze weigering leest een trendrapport als vooruitgang terwijl er alleen
    minder gemeten is.
    """
    eerder = analyze(laad_nulmeting(shacl_drieluik, VEREIST))
    later = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))

    with pytest.raises(ComparisonError, match="Hyd, MdsPlan, MdsProj"):
        compare_metingen(eerder, later, load_coverage_config())


def test_vergelijk_slaagt_bij_gelijke_deelsets(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    """Twee deelmetingen op dezelfde set zijn wel te vergelijken."""
    eerder = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))
    later = analyze(laad_nulmeting(_later([mini_hyd_shacl], tmp_path), ["Hyd"], VEREIST))

    vergelijking = compare_metingen(eerder, later, load_coverage_config())

    assert [item.cfk for item in vergelijking.per_cfk] == ["Hyd"]
