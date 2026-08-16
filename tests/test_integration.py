"""Integratietests op de echte De Wolden-bestanden."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gwswpijplijn.analysis import analyze
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import REGISTRY, CheckContext, run_checks
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import Verdict, assess_coverage
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.meting import laad_nulmeting
from gwswpijplijn.reporting import write_check_report, write_reports
from gwswpijplijn.studiegebied import load_study_area

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SHACL_DIR = DATA_DIR / "shacl_nulmeting"
OROX_DIR = DATA_DIR / "gwsw_orox_ttl"
ONTOLOGIE_DIR = DATA_DIR / "gwsw_ontologieen"
GIS_DIR = DATA_DIR / "gis"

OROX_DE_WOLDEN = OROX_DIR / "dewolden_orox.ttl"
VOORBEELD_TTL = OROX_DIR / "GwswDataset__Voorbeeld_v1_6_orox.ttl"
ONTOLOGIE_TTL = ONTOLOGIE_DIR / "Ontologie_GWSW_Mds.ttl"
ONTOLOGIE_TOTAAL = ONTOLOGIE_DIR / "Ontologie_GWSW_Totaal.ttl"
STUDIEGEBIED = GIS_DIR / "cbs_buurt_koekangerveld_studiegebied.gpkg"

SHACL_PADEN = sorted(SHACL_DIR.glob("*.csv"))

pytestmark = pytest.mark.integratie


@pytest.fixture(scope="module")
def meting():
    """De volledige SHACL-nulmeting van De Wolden."""
    if len(SHACL_PADEN) < 3:
        pytest.skip("de SHACL-rapporten staan niet in data/shacl_nulmeting/")
    return laad_nulmeting(SHACL_PADEN, ["Hyd", "MdsPlan", "MdsProj"])


def _onafhankelijke_telling(pad: Path) -> dict[str, int]:
    """Telt de vormen na met een kale csv.reader, buiten de parser om."""
    with pad.open(encoding="utf-8", newline="") as bestand:
        rijen = list(csv.reader(bestand, delimiter=";"))
    kop = next(i for i, r in enumerate(rijen) if r and r[0] == "Focus node")
    body = [r for r in rijen[kop + 1 :] if r and any(r)]
    telling: dict[str, int] = {}
    for rij in body:
        telling[rij[1]] = telling.get(rij[1], 0) + 1
    telling["__totaal__"] = len(body)
    return telling


def test_alle_drie_de_cfks(meting) -> None:
    assert meting.cfks == ["Hyd", "MdsPlan", "MdsProj"]
    assert meting.dataset_file == "dewolden_orox.ttl"


@pytest.mark.parametrize("cfk", ["Hyd", "MdsPlan", "MdsProj"])
def test_aantallen_komen_overeen_met_een_onafhankelijke_telling(meting, cfk: str) -> None:
    rapport = meting.report(cfk)
    telling = _onafhankelijke_telling(rapport.source_file)

    assert len(rapport.findings) == telling["__totaal__"]
    analyse = analyze(meting).per_cfk[cfk]
    for vorm, aantal in analyse.by_shape.set_index("Source")["Meldingen"].items():
        assert int(aantal) == telling[vorm]


def test_bekende_kerncijfers(meting) -> None:
    # Vastgelegde cijfers van de SHACL-meting van 2026-08-16.
    analyse = analyze(meting)

    assert analyse.per_cfk["Hyd"].total_count == 105582
    assert analyse.per_cfk["MdsPlan"].total_count == 54438
    assert analyse.per_cfk["MdsProj"].total_count == 53480
    # De ernst komt nu uit de nulmeting zelf; het waarschuwingsaantal is gelijk.
    assert {analyse.per_cfk[cfk].warning_count for cfk in meting.cfks} == {18946}


def test_te_globale_klassen_per_cfk(meting) -> None:
    assert meting.report("Hyd").too_generic_classes == ["Rioolstelsel"]
    assert meting.report("MdsPlan").too_generic_classes == [
        "MechanischRioolstelsel",
        "Overstortput",
        "Rioolstelsel",
    ]


def test_dekkingoordelen(meting) -> None:
    result = assess_coverage(analyze(meting), load_coverage_config())
    oordelen = {check.mapping.id: check.verdict for check in result.checks}

    assert oordelen["ADM-001"] is Verdict.TOUCHED
    assert oordelen["ADM-004"] is Verdict.TOUCHED
    assert oordelen["ADM-005"] is Verdict.TOUCHED
    assert oordelen["ATTR-011"] is Verdict.TOUCHED
    # In de SHACL-meting komt geen enkele vorm op Drempelniveau of Drempelbreedte voor.
    assert oordelen["RVZ-002"] is Verdict.UNTOUCHED
    assert oordelen["RVZ-003"] is Verdict.UNTOUCHED


def test_samenvatting_schrijven(meting, tmp_path: Path) -> None:
    markdown_path, csv_path = write_reports(analyze(meting), tmp_path)

    assert "dewolden_orox.ttl" in markdown_path.read_text(encoding="utf-8")
    assert csv_path.stat().st_size > 0


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


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DE_WOLDEN.exists() and ONTOLOGIE_TOTAAL.exists()),
    reason="de De Wolden-OroX staat niet in data/",
)
def test_checks_op_de_wolden_met_typeringspoort(meting, tmp_path: Path) -> None:
    dataset = load_dataset(OROX_DE_WOLDEN, [ONTOLOGIE_TOTAAL])
    analyse = analyze(meting, dataset)

    onbetrouwbaar = set()
    for deel in analyse.per_cfk.values():
        onbetrouwbaar.update(deel.typing_gate.objects)

    context = CheckContext(
        dataset=dataset,
        config=load_check_config(),
        unreliable_objects=frozenset(onbetrouwbaar),
    )
    run = run_checks(context, typing_gate_applied=True)

    assert len(dataset.conduits) == 23440
    assert len(dataset.nodes) == 23485
    assert dataset.geometry_errors == {}
    # De export is niet UTF-8: vijf CP850-bytes in straatnamen.
    assert dataset.decode_fallback is not None
    assert dataset.decode_fallback.byte_count == 5
    assert run.findings


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DE_WOLDEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden-OroX of het studiegebied staat niet in data/",
)
def test_studiegebied_koekangerveld(tmp_path: Path) -> None:
    """De afbakening moet aanzienlijk minder bevindingen opleveren, en dat melden."""
    dataset = load_dataset(OROX_DE_WOLDEN, [ONTOLOGIE_TOTAAL])
    context = CheckContext(dataset=dataset, config=load_check_config())
    volledig = run_checks(context)

    gebied = load_study_area(STUDIEGEBIED)
    beperkt = volledig.beperk_tot_studiegebied(gebied)

    assert gebied.area_ha == pytest.approx(43.2, abs=0.5)
    assert len(beperkt.findings) < len(volledig.findings)
    weggelaten = sum(outcome.weggelaten for outcome in beperkt.outcomes)
    assert weggelaten == len(volledig.findings) - len(beperkt.findings)

    markdown_path, _ = write_check_report(beperkt, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")
    assert "Studiegebied" in tekst
    assert "buiten het gebied" in tekst
