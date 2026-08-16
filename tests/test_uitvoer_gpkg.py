"""Tests voor de GeoPackage-export.

De GPKG wordt met `sqlite3` en shapely geschreven, dezelfde route waarmee
`studiegebied.py` er al een leest. Deze tests lezen het geschreven bestand ook weer
met `sqlite3` terug, zodat lees- en schrijfkant elkaar in de gaten houden.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, CheckRun, run_checks
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.studiegebied import load_study_area
from gwswpijplijn.uitvoer.gpkg import RD_NEW, schrijf_geopackage
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


def _schrijf(run: CheckRun, map_: Path) -> Path:
    """Schrijft de GeoPackage van een run."""
    return schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), map_, RUNDATUM)


def _rijen(pad: Path, sql: str, *parameters) -> list[tuple]:
    """Leest rijen uit het geschreven bestand."""
    con = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        return con.execute(sql, parameters).fetchall()
    finally:
        con.close()


def test_bestandsnaam_draagt_dataset_en_rundatum(tmp_path: Path) -> None:
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    assert pad.name == "dq_schoon_20260816.gpkg"


def test_bestand_is_een_geldige_geopackage(tmp_path: Path) -> None:
    """Zonder de juiste application_id herkent geen enkel GIS-pakket het bestand."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    assert _rijen(pad, "pragma application_id")[0][0] == 0x47504B47
    tabellen = {naam for (naam,) in _rijen(pad, "select name from sqlite_master")}
    assert {"gpkg_spatial_ref_sys", "gpkg_contents", "gpkg_geometry_columns"} <= tabellen
    assert RD_NEW in {srs for (srs,) in _rijen(pad, "select srs_id from gpkg_spatial_ref_sys")}


def test_lagen_staan_in_gpkg_contents(tmp_path: Path) -> None:
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    soorten = dict(_rijen(pad, "select table_name, data_type from gpkg_contents"))

    assert soorten["putten"] == "features"
    assert soorten["strengen"] == "features"
    assert soorten["meldinglocaties"] == "features"
    assert soorten["meldingen"] == "attributes"
    assert soorten["overzicht_checks"] == "attributes"
    assert soorten["gwsw_run"] == "attributes"


def test_putten_en_strengen_dragen_leesbare_geometrie(tmp_path: Path) -> None:
    """De schrijfkant moet leveren wat de leeskant in studiegebied.py verwacht."""
    from gwswpijplijn.studiegebied import _ontleed_gpkg

    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    putten = _rijen(pad, "select label, geom from putten order by label")
    assert [label for label, _ in putten] == ["A", "B"]
    assert all(_ontleed_gpkg(blob).geom_type == "Point" for _, blob in putten)

    strengen = _rijen(pad, "select label, geom from strengen")
    assert all(_ontleed_gpkg(blob).geom_type == "LineString" for _, blob in strengen)


def test_featurelaag_vat_de_meldingen_per_object_samen(tmp_path: Path) -> None:
    """De laag moet zonder join bruikbaar zijn."""
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    pad = _schrijf(run, tmp_path)

    rijen = dict(_rijen(pad, "select label, ergste_ernst from putten"))
    assert rijen["C"] == "F"
    assert rijen["A"] == "geen"

    fout = _rijen(pad, "select n_fout, checks_f from putten where label = 'C'")[0]
    assert fout == (1, "TOP-001")


def test_meldingen_bevat_elke_melding_met_een_eigen_id(tmp_path: Path) -> None:
    run = _run("top011_hartlijnkruising.ttl")
    meldingen = bouw_meldingen(run, RUNDATUM)
    pad = _schrijf(run, tmp_path)

    kenmerken = [rij[0] for rij in _rijen(pad, "select melding_id from meldingen")]

    assert len(kenmerken) == len(meldingen)
    assert len(set(kenmerken)) == len(kenmerken)


def test_paarmelding_draagt_beide_objecten(tmp_path: Path) -> None:
    run = _run("top011_hartlijnkruising.ttl", "TOP-011")
    pad = _schrijf(run, tmp_path)

    rij = _rijen(pad, "select feature_id, feature_id_2 from meldingen where check_id = 'TOP-011'")

    assert rij[0][0] and rij[0][1]


def test_meldinglocaties_bevat_een_punt_per_melding_met_locatie(tmp_path: Path) -> None:
    run = _run("top011_hartlijnkruising.ttl", "TOP-011")
    meldingen = bouw_meldingen(run, RUNDATUM)
    met_punt = [melding for melding in meldingen if melding.foutlocatie is not None]
    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select count(*) from meldinglocaties")[0][0] == len(met_punt)


def test_overzicht_checks_toont_ook_de_checks_zonder_bevinding(tmp_path: Path) -> None:
    """Een check die ontbreekt leest als een check zonder problemen."""
    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    aantal = _rijen(pad, "select count(*) from overzicht_checks")[0][0]

    assert aantal == len(run.outcomes)


def test_runmetadata_maakt_het_bestand_herleidbaar(tmp_path: Path) -> None:
    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    rij = _rijen(
        pad,
        "select dataset, run_datum, register_versie, typeringspoort, grens_bron from gwsw_run",
    )[0]

    assert rij[0] == "schoon.ttl"
    assert rij[1] == "2026-08-16"
    assert rij[2] == "v0.8"
    assert rij[3] == 0
    assert rij[4] == ""


def test_stijlen_staan_in_het_bestand(tmp_path: Path) -> None:
    """De ontvanger moet het bestand kunnen openen zonder handmatige stappen."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    stijlen = _rijen(
        pad, "select f_table_name, styleQML, useAsDefault from layer_styles order by f_table_name"
    )

    assert [naam for naam, _, _ in stijlen] == ["meldinglocaties", "putten", "strengen"]
    for _, qml, standaard in stijlen:
        assert standaard == 1
        ET.fromstring(qml)


def test_stijlen_liggen_ook_los_naast_het_bestand(tmp_path: Path) -> None:
    """Niet elk GIS-pakket leest layer_styles, maar QML importeren kan meestal wel."""
    _schrijf(_run("schoon.ttl"), tmp_path)

    assert (tmp_path / "putten.qml").exists()
    assert (tmp_path / "strengen.qml").exists()
    assert (tmp_path / "meldinglocaties.qml").exists()


def test_zonder_studiegebied_gaat_de_hele_dataset_mee(tmp_path: Path) -> None:
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select count(*) from putten")[0][0] == len(run.dataset.nodes)
    assert _rijen(pad, "select scope from meldingen")[0][0] == "geen_studiegebied"


def test_met_studiegebied_is_het_gebied_de_grens(tmp_path: Path) -> None:
    """De checks draaien op alles; de export wordt bij de grens afgekapt."""
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    gebied = load_study_area(GIS_DIR / "rond_put_ab.geojson")
    beperkt = run.beperk_tot_studiegebied(gebied)

    pad = _schrijf(beperkt, tmp_path)

    labels = {label for (label,) in _rijen(pad, "select label from putten")}
    assert labels == {"A", "B"}
    grens = _rijen(pad, "select grens_bron, grens_oppervlak_ha from gwsw_run")[0]
    assert grens[0] == "rond_put_ab.geojson"
    assert grens[1] == pytest.approx(0.14, abs=0.01)


def test_export_overschrijft_geen_invoerbestand(tmp_path: Path) -> None:
    """De uitvoermap mag nooit de datamap zijn."""
    run = _run("schoon.ttl")

    with pytest.raises(Exception, match="invoerbestand"):
        _schrijf(run, TTL_DIR)


def test_geschreven_bestand_is_leesbaar_met_de_eigen_lezer(tmp_path: Path) -> None:
    """De lees- en schrijfkant houden elkaar zo in de gaten.

    `load_study_area` is de productiecode die GeoPackages leest; kan die de
    geschreven strengenlaag terugvinden, dan klopt het formaat.
    """
    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    gelezen = load_study_area(pad, "strengen")

    assert gelezen.feature_count == len(run.dataset.conduits)
    assert not gelezen.geometry.is_empty


def test_meldinglocatiestijl_filtert_systemische_meldingen_echt(tmp_path: Path) -> None:
    """De stijl moet doen wat zijn toelichting belooft.

    Drie meldingtypen slaan op vrijwel elke put aan; die even zwaar tekenen maakt
    het kaartbeeld onbruikbaar. Ze blijven wel in het bestand staan, maar de
    default-stijl laat ze weg. Een toelichting die dat belooft terwijl de stijl het
    niet doet, is erger dan geen toelichting.
    """
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    qml = _rijen(pad, "select styleQML from layer_styles where f_table_name = 'meldinglocaties'")
    boom = ET.fromstring(qml[0][0])

    filters = [regel.get("filter", "") for regel in boom.iter("rule")]
    assert filters, "de stijl kent geen regels en kan dus niet filteren"
    assert all("systemisch" in uitdrukking for uitdrukking in filters)


def test_featurelagen_dragen_het_stelseltype(tmp_path: Path) -> None:
    """Filteren op stelseltype is de eerste vraag van elke gebruiker.

    Een streng draagt haar eigen type; een put ontleent het aan de strengen die
    erop uitkomen, want het GWSW legt het stelseltype op de leiding vast.
    """
    pad = _schrijf(_run("net001_geen_afvoerpad.ttl"), tmp_path)

    strengen = dict(_rijen(pad, "select label, stelsel from strengen"))
    putten = dict(_rijen(pad, "select label, stelsel from putten"))

    assert strengen["1"] == "gemengd"
    assert putten["A"] == "gemengd"
