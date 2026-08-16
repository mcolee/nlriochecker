"""Tests voor de dekkinganalyse op SHACL-vormen."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.analysis import MetingAnalysis, analyze
from gwswpijplijn.config import CoverageConfig, load_coverage_config
from gwswpijplijn.coverage import CheckCoverage, CoverageResult, Verdict, assess_coverage
from gwswpijplijn.meting import laad_nulmeting

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


@pytest.fixture
def analyse(shacl_drieluik: list[Path]) -> MetingAnalysis:
    """De analyse van de mini-nulmeting."""
    return analyze(laad_nulmeting(shacl_drieluik, VEREIST))


@pytest.fixture
def config() -> CoverageConfig:
    """De meegeleverde standaardmapping."""
    return load_coverage_config()


@pytest.fixture
def result(analyse: MetingAnalysis, config: CoverageConfig) -> CoverageResult:
    """De dekkinganalyse over de mini-nulmeting."""
    return assess_coverage(analyse, config)


def _check(result: CoverageResult, check_id: str) -> CheckCoverage:
    """Zoekt het dekkingoordeel van een check op."""
    return next(check for check in result.checks if check.mapping.id == check_id)


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


def test_drempelvormen_ontbreken_in_de_shacl_meting(result: CoverageResult) -> None:
    """RVZ-002 en RVZ-003 zijn geschrapt omdat de nulmeting de drempel zou dekken.

    In de SHACL-rapporten komt geen enkele vorm op Drempelniveau of Drempelbreedte
    voor, dus die dekking is hier niet aan te tonen.
    """
    for check_id in ("RVZ-002", "RVZ-003"):
        check = _check(result, check_id)
        assert check.evidence_cfks == []
        assert check in result.untouched


def test_koppeling_zit_in_alle_drie_de_cfks(result: CoverageResult) -> None:
    """Het register stelt dat de put-strengkoppeling alleen uit Hyd komt."""
    check = _check(result, "ADM-001")

    assert check.evidence_cfks == ["Hyd", "MdsPlan", "MdsProj"]
    assert all(item.required for item in check.evidence)


def test_bewijs_noemt_de_vormen(result: CoverageResult) -> None:
    bewijs = _check(result, "ATTR-011").evidence[0]

    assert bewijs.shapes == ["LengteLeiding_val"]
    assert bewijs.row_count > 0
    assert bewijs.object_count > 0


def test_eigen_mapping_op_vormprefix(analyse: MetingAnalysis, tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        'checkregister_versie = "0.7"\n'
        'bron = "x"\n'
        "[[check]]\n"
        'id = "EIGEN-001"\n'
        'onderwerp = "x"\n'
        'claim = "x"\n'
        'vereiste_cfk = ["Hyd"]\n'
        'bewijs = [{ vorm_prefix = "Knooppunt_" }]\n',
        encoding="utf-8",
    )

    result = assess_coverage(analyse, load_coverage_config(eigen))

    assert _check(result, "EIGEN-001").verdict is Verdict.TOUCHED


def test_zonder_dataset_geen_typeringsvoorbehoud(result: CoverageResult) -> None:
    # De score is niet te bepalen zonder OroX-bestand; dan valt er niets voor te behouden.
    assert _check(result, "ADM-004").typing_reliable is True
