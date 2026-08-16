"""Tests voor de dekkinganalyse van de geschrapte checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.config import CoverageConfig, load_coverage_config
from gwswpijplijn.coverage import CheckCoverage, CoverageResult, Verdict, assess_coverage
from gwswpijplijn.pair import ReportPair, load_pair


@pytest.fixture
def pair(mini_mds: Path, mini_hyd: Path) -> ReportPair:
    """Het rapportenpaar van de mini-uittreksels."""
    return load_pair(mini_mds, mini_hyd)


@pytest.fixture
def config() -> CoverageConfig:
    """De meegeleverde standaardmapping."""
    return load_coverage_config()


@pytest.fixture
def result(pair: ReportPair, config: CoverageConfig) -> CoverageResult:
    """De dekkinganalyse over de mini-uittreksels."""
    return assess_coverage(pair, config)


def _check(result: CoverageResult, check_id: str) -> CheckCoverage:
    """Zoekt het dekkingoordeel van een check op."""
    return next(check for check in result.checks if check.mapping.id == check_id)


def _counts(check: CheckCoverage) -> dict[str, int]:
    """Meldingregels per CFK."""
    return {item.cfk: item.row_count for item in check.evidence}


@pytest.mark.parametrize(
    ("check_id", "verdict"),
    [
        ("ADM-001", Verdict.TOUCHED),
        ("ADM-004", Verdict.TOUCHED),
        ("ADM-005", Verdict.TOUCHED),
        ("ATTR-011", Verdict.TOUCHED),
        ("RVZ-002", Verdict.UNTOUCHED),
        ("RVZ-003", Verdict.UNTOUCHED),
    ],
)
def test_oordeel_per_check(result: CoverageResult, check_id: str, verdict: Verdict) -> None:
    assert _check(result, check_id).verdict is verdict


def test_adm_001_leunt_op_hyd(result: CoverageResult) -> None:
    check = _check(result, "ADM-001")

    assert _counts(check) == {"MdsPlan": 0, "Hyd": 4}
    assert check.evidence_cfks == ["Hyd"]
    # Alleen Hyd telt mee voor het oordeel; MdsPlan wordt wel gemeten.
    assert [item.required for item in check.evidence] == [False, True]


def test_rvz_003_wordt_in_deze_uittreksels_niet_geraakt(result: CoverageResult) -> None:
    check = _check(result, "RVZ-003")

    assert _counts(check) == {"MdsPlan": 0, "Hyd": 0}
    assert check.verdict is Verdict.UNTOUCHED
    assert check in result.untouched


def test_attr_011_telt_alleen_lengte_leiding(result: CoverageResult) -> None:
    check = _check(result, "ATTR-011")

    # Vier "Waarde te groot"-regels per rapport, waarvan drie op Lengte leiding.
    assert _counts(check) == {"MdsPlan": 3, "Hyd": 3}
    assert check.evidence[0].aspects == ["Lengte leiding (datatype)"]


def test_adm_005_telt_gewogen_en_heeft_tegenbewijs(result: CoverageResult) -> None:
    check = _check(result, "ADM-005")

    assert _counts(check) == {"MdsPlan": 1, "Hyd": 1}
    assert [item.weighted_count for item in check.evidence] == [33, 33]
    assert check.has_counter_evidence
    assert [item.row_count for item in check.counter_evidence] == [3, 0]


def test_typeringsvoorbehoud_volgt_de_vereiste_cfk(result: CoverageResult) -> None:
    # MdsPlan-uittreksel scoort 75% en blijft onder de standaarddrempel van 95%;
    # het Hyd-uittreksel scoort 100%.
    assert _check(result, "ADM-004").typing_reliable is False
    assert _check(result, "ADM-001").typing_reliable is True


def test_lagere_drempel_haalt_het_voorbehoud_weg(pair: ReportPair, tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        'checkregister_versie = "0.7"\n'
        'bron = "x"\n'
        "[drempels]\n"
        "typeringsscore_minimum = 70.0\n"
        "[[check]]\n"
        'id = "ADM-004"\n'
        'onderwerp = "x"\n'
        'claim = "x"\n'
        'vereiste_cfk = ["MdsPlan"]\n'
        'bewijs = [{ melding = "Ontbrekende relatie [hasAspect]" }]\n',
        encoding="utf-8",
    )

    result = assess_coverage(pair, load_coverage_config(eigen))

    assert _check(result, "ADM-004").typing_reliable is True


def test_ontbrekende_cfk_is_niet_toetsbaar(pair: ReportPair, tmp_path: Path) -> None:
    # Het paar is aan MdsPlan getoetst, niet aan Mds; er is dus geen vereiste CFK.
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        'checkregister_versie = "0.7"\n'
        'bron = "x"\n'
        "[[check]]\n"
        'id = "ALLEEN-MDS"\n'
        'onderwerp = "x"\n'
        'claim = "x"\n'
        'vereiste_cfk = ["Mds"]\n'
        'bewijs = [{ melding = "Collectie-item onbekend" }]\n',
        encoding="utf-8",
    )

    result = assess_coverage(pair, load_coverage_config(eigen))

    assert _check(result, "ALLEEN-MDS").verdict is Verdict.UNVERIFIABLE


def test_objecttypefilter_werkt(pair: ReportPair, tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        'checkregister_versie = "0.7"\n'
        'bron = "x"\n'
        "[[check]]\n"
        'id = "ALLEEN-DRAIN"\n'
        'onderwerp = "x"\n'
        'claim = "x"\n'
        'vereiste_cfk = ["MdsPlan", "Hyd"]\n'
        'bewijs = [{ melding = "Waarde te groot", objecttype = ["Drain"] }]\n',
        encoding="utf-8",
    )

    result = assess_coverage(pair, load_coverage_config(eigen))

    assert _counts(_check(result, "ALLEEN-DRAIN")) == {"MdsPlan": 2, "Hyd": 2}
