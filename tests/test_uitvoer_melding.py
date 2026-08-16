"""Tests voor de meldingenstroom waar Markdown, CSV en GeoPackage uit lezen."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, CheckRun, run_checks
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.studiegebied import load_study_area
from gwswpijplijn.uitvoer.melding import bouw_meldingen

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
RUNDATUM = date(2026, 8, 16)


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _run(bestand: str, *check_ids: str) -> CheckRun:
    """Draait checks op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=_config())
    return run_checks(context, list(check_ids) or None)


def test_categorie_volgt_uit_het_check_id() -> None:
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].categorie == "TOP"


def test_bron_is_het_register() -> None:
    """Ronde 2 vult hier nulmeting_mds en nulmeting_hyd bij."""
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].bron == "register"


def test_elke_melding_heeft_een_eigen_id() -> None:
    """Een botsing zou twee gebreken tot een samenvoegen in CSV en GIS."""
    run = _run("top011_hartlijnkruising.ttl")
    meldingen = bouw_meldingen(run, RUNDATUM)

    kenmerken = [melding.melding_id for melding in meldingen]
    assert len(set(kenmerken)) == len(kenmerken)


def test_paarmelding_draagt_het_tweede_object() -> None:
    meldingen = bouw_meldingen(_run("top011_hartlijnkruising.ttl", "TOP-011"), RUNDATUM)

    melding = meldingen[0]
    assert melding.object2_uri
    assert melding.object2_label


def test_gewone_melding_heeft_geen_tweede_object() -> None:
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].object2_uri == ""


def test_scope_zonder_studiegebied() -> None:
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].scope == "geen_studiegebied"
    assert meldingen[0].gebied == ""


def test_scope_en_gebied_met_studiegebied() -> None:
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    gebied = load_study_area(GIS_DIR / "rond_de_fixture.geojson")

    meldingen = bouw_meldingen(run.beperk_tot_studiegebied(gebied), RUNDATUM)

    assert meldingen
    assert all(melding.scope == "binnen_studiegebied" for melding in meldingen)
    assert all(melding.gebied == "rond_de_fixture" for melding in meldingen)


def test_waarschuwing_krijgt_de_laagste_prioriteit() -> None:
    meldingen = bouw_meldingen(_run("top014_vijf_strengen.ttl", "TOP-014"), RUNDATUM)

    assert meldingen[0].ernst == "W"
    assert meldingen[0].prioriteit == 3


def test_fout_op_een_gewoon_object_krijgt_prioriteit_twee() -> None:
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].ernst == "F"
    assert meldingen[0].prioriteit == 2


def test_fout_op_een_kritiek_object_krijgt_prioriteit_een() -> None:
    """Een losgeraakte overstort weegt zwaarder dan een losgeraakte inspectieput."""
    meldingen = bouw_meldingen(_run("rvz001_losse_overstort.ttl", "RVZ-001"), RUNDATUM)

    assert meldingen[0].ernst == "F"
    assert meldingen[0].prioriteit == 1


def test_melding_draagt_de_foutlocatie() -> None:
    meldingen = bouw_meldingen(_run("top011_hartlijnkruising.ttl", "TOP-011"), RUNDATUM)

    assert meldingen[0].foutlocatie is not None


def test_runmetadata_staat_op_elke_melding() -> None:
    """Een los rondslingerend bestand moet herleidbaar zijn."""
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].run_datum == "2026-08-16"
    assert meldingen[0].dataset == "top001_losliggende_put.ttl"


def test_systemische_check_wordt_als_zodanig_gemarkeerd() -> None:
    """Slaat een check op vrijwel de hele populatie aan, dan zegt hij iets over de
    export als geheel en niet over de losse objecten."""
    run = _run("net001_geen_afvoerpad.ttl", "NET-001")
    uitkomst = run.outcomes[0]
    assert len(uitkomst.findings) / uitkomst.examined < 0.8

    meldingen = bouw_meldingen(run, RUNDATUM)

    assert all(not melding.systemisch for melding in meldingen)


def test_cluster_id_komt_mee_uit_de_netwerkchecks() -> None:
    meldingen = bouw_meldingen(_run("net001_geen_afvoerpad.ttl", "NET-001"), RUNDATUM)

    assert meldingen[0].cluster_id.startswith("ds-")


def test_check_boven_de_drempel_heet_systemisch() -> None:
    """De drempel is configureerbaar; hier verlaagd om het gedrag te tonen.

    NET-001 slaat op de fixture op 1 van de 3 strengen aan. Met de standaarddrempel
    van 80% is dat geen systemische melding, met 10% wel.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl")
    config = _config()
    config.rapport.systemisch_drempel = 0.1
    context = CheckContext(dataset=dataset, config=config)
    run = run_checks(context, ["NET-001"])

    meldingen = bouw_meldingen(run, RUNDATUM)

    assert meldingen
    assert all(melding.systemisch for melding in meldingen)
