"""Tests voor de vergelijking van twee nulmetingen."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.comparison import ChangeStatus, PairComparison, compare_pairs
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import Verdict
from gwswpijplijn.errors import ComparisonError
from gwswpijplijn.pair import ReportPair, load_pair


@pytest.fixture
def earlier(mini_mds: Path, mini_hyd: Path) -> ReportPair:
    """Het eerste meetmoment."""
    return load_pair(mini_mds, mini_hyd)


@pytest.fixture
def later(mini_mds_later: Path, mini_hyd_later: Path) -> ReportPair:
    """Het tweede meetmoment, met bewust aangebrachte verschillen."""
    return load_pair(mini_mds_later, mini_hyd_later)


@pytest.fixture
def comparison(earlier: ReportPair, later: ReportPair) -> PairComparison:
    """De vergelijking van beide meetmomenten."""
    return compare_pairs(earlier, later, load_coverage_config())


def _cfk(comparison: PairComparison, cfk: str):
    """Zoekt de vergelijking van een conformiteitsklasse op."""
    return next(item for item in comparison.per_cfk if item.cfk == cfk)


def _verschil(frame, kolom: str, waarde: str) -> int:
    """Het verschil van een enkele rij uit een deltatabel."""
    return int(frame.loc[frame[kolom] == waarde, "Verschil"].iloc[0])


def test_dataset_en_volgorde(comparison: PairComparison) -> None:
    assert comparison.dataset == "DeWolden"
    assert comparison.timestamps_out_of_order is False


def test_totalen_en_typeringsscore(comparison: PairComparison) -> None:
    mds = _cfk(comparison, "MdsPlan")
    hyd = _cfk(comparison, "Hyd")

    # MdsPlan: twee te-globaal-regels weg, een nieuwe lengtemelding erbij.
    assert mds.total_delta == -1
    assert mds.typing_score_delta == pytest.approx(11.6667, abs=0.001)
    # Hyd: twee koppelingsmeldingen weg, een drempelbreedte-melding erbij.
    assert hyd.total_delta == -1
    assert hyd.typing_score_delta == 0.0


def test_delta_per_meldingtype(comparison: PairComparison) -> None:
    mds = _cfk(comparison, "MdsPlan")

    assert (
        _verschil(
            mds.by_message_type,
            "Type Melding",
            "Objecttype te globaal voor deze CFK [type = onvoldoende]",
        )
        == -2
    )
    assert _verschil(mds.by_message_type, "Type Melding", "Waarde te groot") == 1
    assert _verschil(mds.by_message_type, "Type Melding", "Waarde te klein") == 0


def test_delta_per_objecttype_kent_nieuwe_en_verdwenen_typen(comparison: PairComparison) -> None:
    hyd = _cfk(comparison, "Hyd")
    tabel = hyd.by_object_type.set_index("Type object")

    # Overstortput bestond eerder niet in het Hyd-uittreksel.
    assert int(tabel.loc["Overstortput", "Eerder"]) == 0
    assert int(tabel.loc["Overstortput", "Later"]) == 1


@pytest.mark.parametrize("cfk", ["MdsPlan", "Hyd"])
def test_objectniveau(comparison: PairComparison, cfk: str) -> None:
    telling = _cfk(comparison, cfk).status_counts()

    assert telling == {
        ChangeStatus.RESOLVED.value: 2,
        ChangeStatus.NEW.value: 1,
        ChangeStatus.REMAINING.value: 14,
    }


def test_objectstatussen_dekken_de_unie(comparison: PairComparison) -> None:
    for item in comparison.per_cfk:
        eerder = {
            (rij["Type Melding"], rij["Type object"], rij["Naam"])
            for _, rij in item.earlier.report.messages.iterrows()
            if rij["Naam"].strip()
        }
        later = {
            (rij["Type Melding"], rij["Type object"], rij["Naam"])
            for _, rij in item.later.report.messages.iterrows()
            if rij["Naam"].strip()
        }

        assert len(item.object_changes) == len(eerder | later)


def test_dekkingoordeel_verschuift(comparison: PairComparison) -> None:
    veranderd = comparison.coverage_changes.set_index("Check")

    # De nieuwe Drempelbreedte-melding in Hyd raakt RVZ-003 alsnog.
    assert veranderd.loc["RVZ-003", "Eerder"] == Verdict.UNTOUCHED.value
    assert veranderd.loc["RVZ-003", "Later"] == Verdict.TOUCHED.value
    assert bool(veranderd.loc["RVZ-003", "Gewijzigd"]) is True
    assert bool(veranderd.loc["ADM-001", "Gewijzigd"]) is False


def test_zelfvergelijking_geeft_overal_nul(earlier: ReportPair) -> None:
    comparison = compare_pairs(earlier, earlier, load_coverage_config())

    assert comparison.timestamps_out_of_order is True
    for item in comparison.per_cfk:
        assert item.total_delta == 0
        assert item.typing_score_delta == 0.0
        assert int(item.by_message_type["Verschil"].abs().sum()) == 0
        assert set(item.object_changes["Status"]) == {ChangeStatus.REMAINING.value}
    assert not comparison.coverage_changes["Gewijzigd"].any()


def test_verschillende_datasets_geven_fout(
    earlier: ReportPair, mini_mds: Path, mini_hyd_other_dataset: Path, tmp_path: Path
) -> None:
    andere_mds = tmp_path / "andere_mds.csv"
    regels = mini_mds.read_text(encoding="cp1252").splitlines()
    regels[0] = regels[0].replace("dataset DeWolden", "dataset AndereGemeente")
    andere_mds.write_text("\n".join(regels) + "\n", encoding="cp1252")
    andere = load_pair(andere_mds, mini_hyd_other_dataset)

    with pytest.raises(ComparisonError, match="verschillende datasets"):
        compare_pairs(earlier, andere, load_coverage_config())
