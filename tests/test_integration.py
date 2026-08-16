"""Integratietest op de volledige De Wolden-detailrapporten."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gwswpijplijn.analysis import MESSAGE_TOO_GENERIC_PREFIX
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import REGISTRY, CheckContext, run_checks
from gwswpijplijn.comparison import compare_pairs
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import CoverageResult, Verdict, assess_coverage
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.pair import ReportPair, load_pair
from gwswpijplijn.reporting import write_check_report, write_reports

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MDS_FULL = DATA_DIR / "dewolden_nulmeting.csv"
HYD_FULL = DATA_DIR / "dewolden_nulmeting_1.csv"

pytestmark = [
    pytest.mark.integratie,
    pytest.mark.skipif(
        not (MDS_FULL.exists() and HYD_FULL.exists()),
        reason="de volledige De Wolden-bestanden staan niet in data/",
    ),
]


def _independent_count(path: Path) -> dict[str, int]:
    """Telt het bestand na met een kale csv.reader, buiten de parser om."""
    with path.open(encoding="cp1252", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))

    messages = rows[2:]
    named = {(row[2], row[3]) for row in messages if row[3].strip()}
    too_generic = {
        (row[2], row[3])
        for row in messages
        if row[3].strip() and row[1].startswith(MESSAGE_TOO_GENERIC_PREFIX)
    }
    return {
        "rows": len(messages),
        "sum": sum(int(row[0]) for row in messages),
        "named": len(named),
        "too_generic": len(too_generic),
    }


@pytest.fixture(scope="module")
def pair() -> ReportPair:
    """Het volledige rapportenpaar van De Wolden, eenmalig ingelezen."""
    return load_pair(MDS_FULL, HYD_FULL)


def test_metadata(pair: ReportPair) -> None:
    assert pair.dataset == "DeWolden"
    assert pair.mds.report.cfk == "MdsPlan"
    assert pair.hyd.report.cfk == "Hyd"


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_totals_match_independent_count(pair: ReportPair, cfk: str) -> None:
    analysis = getattr(pair, cfk)
    counted = _independent_count(analysis.report.source_file)

    assert len(analysis.report.messages) == counted["rows"]
    assert analysis.total_count == counted["sum"]
    assert int(analysis.by_message_type["Aantal"].sum()) == counted["sum"]
    assert int(analysis.by_object_type["Aantal"].sum()) == counted["sum"]
    assert int(analysis.by_message_and_object_type["Aantal"].sum()) == counted["sum"]


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_typing_gate_matches_independent_count(pair: ReportPair, cfk: str) -> None:
    analysis = getattr(pair, cfk)
    counted = _independent_count(analysis.report.source_file)
    gate = analysis.typing_gate

    assert gate.named_object_count == counted["named"]
    assert gate.too_generic_count == counted["too_generic"]


def test_known_key_figures(pair: ReportPair) -> None:
    # Vastgelegde cijfers van de De Wolden-rapporten van 2026-08-14.
    assert pair.mds.total_count == 24938
    assert pair.hyd.total_count == 47440
    assert pair.mds.typing_gate.too_generic_count == 1228
    assert pair.mds.typing_gate.named_object_count == 10146
    assert pair.mds.typing_gate.score == pytest.approx(87.9, abs=0.05)
    assert pair.hyd.typing_gate.too_generic_count == 0


def test_reporting_on_full_files(pair: ReportPair, tmp_path: Path) -> None:
    markdown_path, csv_path = write_reports(pair, tmp_path)

    assert "DeWolden" in markdown_path.read_text(encoding="utf-8")
    assert csv_path.stat().st_size > 0


def _independent_coverage_count(path: Path, melding: str, aspecten: set[str] | None) -> int:
    """Telt meldingregels van een meldingtype (optioneel op aspect), buiten de code om."""
    with path.open(encoding="cp1252", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))

    return sum(
        1 for row in rows[2:] if row[1] == melding and (aspecten is None or row[4] in aspecten)
    )


@pytest.fixture(scope="module")
def coverage(pair: ReportPair) -> CoverageResult:
    """De dekkinganalyse over het volledige paar, met de meegeleverde mapping."""
    return assess_coverage(pair, load_coverage_config())


def test_alle_geschrapte_checks_worden_geraakt(coverage: CoverageResult) -> None:
    assert {check.mapping.id for check in coverage.checks} == {
        "ADM-001",
        "ADM-004",
        "ADM-005",
        "ATTR-011",
        "RVZ-002",
        "RVZ-003",
    }
    assert all(check.verdict is Verdict.TOUCHED for check in coverage.checks)
    assert coverage.untouched == []


def test_rvz_003_leunt_aantoonbaar_alleen_op_hyd(coverage: CoverageResult) -> None:
    check = next(item for item in coverage.checks if item.mapping.id == "RVZ-003")
    per_cfk = {item.cfk: item.row_count for item in check.evidence}

    # Onafhankelijke telling: Drempelbreedte ontbreekt alleen in het Hyd-rapport.
    assert per_cfk["MdsPlan"] == _independent_coverage_count(
        MDS_FULL, "Ontbrekende relatie [hasAspect]", {"Drempelbreedte"}
    )
    assert per_cfk["Hyd"] == _independent_coverage_count(
        HYD_FULL, "Ontbrekende relatie [hasAspect]", {"Drempelbreedte"}
    )
    assert per_cfk == {"MdsPlan": 0, "Hyd": 3}
    assert check.evidence_cfks == ["Hyd"]


def test_adm_001_bewijs_komt_vooral_uit_hyd(coverage: CoverageResult) -> None:
    check = next(item for item in coverage.checks if item.mapping.id == "ADM-001")
    per_cfk = {item.cfk: item.row_count for item in check.evidence}

    assert per_cfk["MdsPlan"] == _independent_coverage_count(
        MDS_FULL, "Ontbrekende relatie [hasConnection]", {"Knooppunt"}
    )
    assert per_cfk["Hyd"] == _independent_coverage_count(
        HYD_FULL, "Ontbrekende relatie [hasConnection]", {"Knooppunt"}
    )
    assert per_cfk == {"MdsPlan": 3, "Hyd": 117}


def test_adm_005_heeft_tegenbewijs_uit_beide_rapporten(coverage: CoverageResult) -> None:
    check = next(item for item in coverage.checks if item.mapping.id == "ADM-005")
    tegen = {item.cfk: item.row_count for item in check.counter_evidence}

    # Collecties die in deze CFK juist niet getoetst worden: drie in MdsPlan, een in Hyd.
    assert tegen == {"MdsPlan": 3, "Hyd": 1}
    assert check.has_counter_evidence


def test_typeringsvoorbehoud_geldt_voor_de_mds_gebonden_claims(coverage: CoverageResult) -> None:
    oordelen = {check.mapping.id: check.typing_reliable for check in coverage.checks}

    # MdsPlan scoort 87,9% en blijft onder de standaarddrempel van 95%.
    assert oordelen["ADM-004"] is False
    # ADM-001 en RVZ-003 leunen alleen op Hyd, dat 100% scoort.
    assert oordelen["ADM-001"] is True
    assert oordelen["RVZ-003"] is True


def test_zelfvergelijking_van_het_volledige_paar(pair: ReportPair) -> None:
    comparison = compare_pairs(pair, pair, load_coverage_config())

    assert comparison.timestamps_out_of_order is True
    for item in comparison.per_cfk:
        telling = item.status_counts()
        assert item.total_delta == 0
        assert item.typing_score_delta == 0.0
        assert int(item.by_message_type["Verschil"].abs().sum()) == 0
        assert int(item.by_object_type["Verschil"].abs().sum()) == 0
        assert telling["opgelost"] == 0
        assert telling["nieuw"] == 0
        assert telling["gebleven"] == len(item.object_changes)
    assert not comparison.coverage_changes["Gewijzigd"].any()


OROX_DE_WOLDEN = DATA_DIR / "dewolden_orox.ttl"
VOORBEELD_TTL = DATA_DIR / "GwswDataset__Voorbeeld_v1_6_orox.ttl"
# Het Mds-deelmodel volstaat voor het kleine voorbeeld en scheelt laadtijd;
# de volledige dataset krijgt de totaal-ontologie, want die dekt alle klassen.
ONTOLOGIE_TTL = DATA_DIR / "Ontologie_GWSW_Mds.ttl"
ONTOLOGIE_TOTAAL = DATA_DIR / "Ontologie_GWSW_Totaal.ttl"


@pytest.mark.skipif(
    not (VOORBEELD_TTL.exists() and ONTOLOGIE_TTL.exists()),
    reason="het OroX-voorbeeld of de ontologie staat niet in data/",
)
def test_alle_checks_draaien_op_het_voorbeeld(tmp_path: Path) -> None:
    dataset = load_dataset(VOORBEELD_TTL, [ONTOLOGIE_TTL])
    context = CheckContext(dataset=dataset, config=load_check_config())
    run = run_checks(context)
    markdown_path, csv_path = write_check_report(run, tmp_path)

    assert len(run.outcomes) == len(REGISTRY)
    assert markdown_path.exists()
    assert csv_path.exists()
    assert "geen typeringspoort" in markdown_path.read_text(encoding="utf-8").lower()


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DE_WOLDEN.exists() and ONTOLOGIE_TOTAAL.exists()),
    reason="de De Wolden-OroX staat nog niet in data/",
)
def test_checks_op_de_wolden_met_typeringspoort(pair: ReportPair, tmp_path: Path) -> None:
    dataset = load_dataset(OROX_DE_WOLDEN, [ONTOLOGIE_TOTAAL])
    onbetrouwbaar = frozenset(
        naam
        for analysis in (pair.mds, pair.hyd)
        for naam in analysis.typing_gate.objects["Naam"]
        if naam
    )
    context = CheckContext(
        dataset=dataset, config=load_check_config(), unreliable_labels=onbetrouwbaar
    )
    run = run_checks(context, typing_gate_applied=True)

    # De typeringspoort van MdsPlan noemt 1228 objecten te globaal getypeerd.
    assert len(onbetrouwbaar) == 1228
    # Daarvan komen er 1174 in de OroX-export voor. De 54 die ontbreken zijn vooral
    # rioolstelsels; detailrapport en export zijn losse bestanden en hoeven niet uit
    # dezelfde momentopname te komen. Dat verschil hoort in het resultaat te staan.
    assert run.unreliable_labels == 1228
    assert run.unreliable_labels_in_dataset == 1174

    assert len(dataset.conduits) == 23440
    assert len(dataset.nodes) == 23485
    assert dataset.geometry_errors == {}

    # De export is niet UTF-8: vijf CP850-bytes in straatnamen.
    assert dataset.decode_fallback is not None
    assert dataset.decode_fallback.byte_count == 5

    # De vlag landt daadwerkelijk op bevindingen, niet alleen in theorie.
    gevlagd = [finding for finding in run.findings if not finding.typing_reliable]
    assert gevlagd, "geen enkele bevinding kreeg het typeringsvoorbehoud"
    assert all(finding.object_label in onbetrouwbaar for finding in gevlagd)
