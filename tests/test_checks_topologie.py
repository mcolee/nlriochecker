"""Tests voor de TOP-checks op kleine fixtures met een bekend defect."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, Finding, run_checks
from nlriochecker.dataset import GwswDataset, load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

TOP_IDS = ["TOP-001", "TOP-002", "TOP-003", "TOP-004", "TOP-005", "TOP-012"]


def _bevindingen(pad: Path, check_id: str, config: CheckConfig | None = None) -> list[Finding]:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(pad)
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0].findings


def _labels(bevindingen: list[Finding]) -> list[str]:
    """De labels van de gevonden objecten."""
    return sorted(finding.object_label for finding in bevindingen)


@pytest.mark.parametrize(
    ("bestand", "check_id", "label"),
    [
        ("top001_losliggende_put.ttl", "TOP-001", "C"),
        ("top002_losliggende_streng.ttl", "TOP-002", "2"),
        ("top003_een_put.ttl", "TOP-003", "2"),
        ("top004_niet_gesnapt.ttl", "TOP-004", "1"),
        ("top005_dubbele_put.ttl", "TOP-005", "B"),
        ("top012_zelfde_put.ttl", "TOP-012", "2"),
    ],
)
def test_defect_wordt_gevonden(bestand: str, check_id: str, label: str) -> None:
    bevindingen = _bevindingen(TTL_DIR / bestand, check_id)

    assert len(bevindingen) == 1
    assert bevindingen[0].object_label == label
    assert bevindingen[0].check_id == check_id


@pytest.mark.parametrize("check_id", TOP_IDS)
def test_schone_fixture_geeft_geen_bevinding(check_id: str) -> None:
    assert _bevindingen(TTL_DIR / "schoon.ttl", check_id) == []


def test_top004_meldt_afstand_en_put() -> None:
    bevinding = _bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004")[0]

    assert bevinding.details["afstand_m"] == pytest.approx(0.5)
    assert bevinding.details["put"] == "B"
    assert bevinding.details["zijde"] == "eindpunt"


def test_top005_meldt_beide_putten_een_keer() -> None:
    bevindingen = _bevindingen(TTL_DIR / "top005_dubbele_put.ttl", "TOP-005")

    # Een paar levert een melding, niet twee spiegelbeelden.
    assert len(bevindingen) == 1
    assert bevindingen[0].details["object2_label"] == "B2"
    assert bevindingen[0].details["afstand_m"] == pytest.approx(0.1)


def test_drempel_uit_de_config_bepaalt_de_uitkomst(tmp_path: Path) -> None:
    ruim = tmp_path / "ruim.toml"
    ruim.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\nsnapping_tolerantie_m = 1.0\n",
        encoding="utf-8",
    )

    # Met de standaardtolerantie van 0,10 m is de streng niet gesnapt;
    # met 1,00 m valt hij ruim binnen de marge.
    assert len(_bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004")) == 1
    assert (
        _bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004", load_check_config(ruim)) == []
    )


def test_dubbele_put_drempel_uit_de_config(tmp_path: Path) -> None:
    streng = tmp_path / "streng.toml"
    streng.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\ndubbele_put_tolerantie_m = 0.05\n",
        encoding="utf-8",
    )

    assert (
        _bevindingen(TTL_DIR / "top005_dubbele_put.ttl", "TOP-005", load_check_config(streng)) == []
    )


def test_juinen_voorbeeld_levert_verklaarbare_bevindingen(juinen: GwswDataset) -> None:
    context = CheckContext(dataset=juinen, config=load_check_config())
    run = run_checks(context, TOP_IDS)
    per_check = {outcome.check_id: _labels(outcome.findings) for outcome in run.outcomes}

    # Kolk "75" hangt aan een kolkaansluitleiding en is dus niet losliggend;
    # leiding "13" eindigt niet op een put. De overige TOP-checks zijn schoon.
    assert per_check["TOP-001"] == []
    assert per_check["TOP-003"] == ["13"]
    assert per_check["TOP-002"] == []
    assert per_check["TOP-004"] == []
    assert per_check["TOP-005"] == []
    assert per_check["TOP-012"] == []


def test_put_aan_alleen_een_persleiding_is_niet_losliggend() -> None:
    """TOP-001 vraagt of er enige streng aansluit, niet of er vrijverval aansluit.

    Zou alleen op vrijvervalleidingen gekeken worden, dan zou elke put van de
    drukriolering als losliggend gelden; in De Wolden en Hoogeveen zijn dat er duizenden.
    """
    bevindingen = _bevindingen(TTL_DIR / "top001_put_aan_persleiding.ttl", "TOP-001")

    assert _labels(bevindingen) == ["LOS"]
