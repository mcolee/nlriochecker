"""Tests voor de aggregaties en de typeringspoort op SHACL-basis."""

from __future__ import annotations

from pathlib import Path

from nlriochecker.analysis import analyze, analyze_report
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import laad_nulmeting
from nlriochecker.shaclrapport import lees_shacl_rapport

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_totalen_en_ernst(mini_hyd_shacl: Path) -> None:
    analyse = analyze_report(lees_shacl_rapport(mini_hyd_shacl))

    assert analyse.total_count == len(analyse.report.findings)
    assert analyse.error_count + analyse.warning_count == analyse.total_count
    # De ernst komt uit de nulmeting zelf; het oude formaat kende die niet.
    assert analyse.error_count > 0


def test_aggregatie_per_vorm(mini_hyd_shacl: Path) -> None:
    per_vorm = analyze_report(lees_shacl_rapport(mini_hyd_shacl)).by_shape

    assert list(per_vorm.columns) == ["Source", "Meldingen", "Fouten", "Waarschuwingen"]
    assert int(per_vorm["Meldingen"].sum()) == len(lees_shacl_rapport(mini_hyd_shacl).findings)
    assert list(per_vorm["Meldingen"]) == sorted(per_vorm["Meldingen"], reverse=True)


def test_typeringspoort_zonder_dataset(mini_mdsplan_shacl: Path) -> None:
    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl)).typing_gate

    assert poort.classes == ["MechanischRioolstelsel", "Overstortput", "Rioolstelsel"]
    assert poort.resolved is False
    # Zonder dataset zijn de objecten niet te bepalen; dan ook geen score verzinnen.
    assert poort.score is None
    assert poort.objects == []


def test_typeringspoort_met_dataset(mini_mdsplan_shacl: Path, tmp_path: Path) -> None:
    bron = (TTL_DIR / "schoon.ttl").read_text(encoding="utf-8")
    # Geef put B het te globale type Overstortput uit het SHACL-rapport.
    bron += "\n:PutB rdf:type gwsw:Overstortput .\ngwsw:Overstortput rdfs:subClassOf gwsw:Put .\n"
    pad = tmp_path / "met_overstortput.ttl"
    pad.write_text(bron, encoding="utf-8")
    dataset = load_dataset(pad)

    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl), dataset).typing_gate

    assert poort.resolved is True
    assert [uri.rsplit("#", 1)[-1] for uri in poort.objects] == ["PutB"]
    assert poort.total_objects == len(dataset.nodes) + len(dataset.conduits)
    assert poort.score is not None


def test_analyse_van_de_hele_nulmeting(shacl_drieluik: list[Path]) -> None:
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))

    assert sorted(analyse.per_cfk) == ["Hyd", "MdsPlan", "MdsProj"]
    assert analyse.total_count == sum(deel.total_count for deel in analyse.per_cfk.values())
