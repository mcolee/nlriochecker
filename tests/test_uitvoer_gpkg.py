"""Tests voor de GeoPackage-export.

De GPKG wordt met `sqlite3` en shapely geschreven, dezelfde route waarmee
`studiegebied.py` er al een leest. Deze tests lezen het geschreven bestand ook weer
met `sqlite3` terug, zodat lees- en schrijfkant elkaar in de gaten houden.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from shapely.geometry import box

from gpkghelper import schrijf_vlakken
from nlriochecker.afbakening import bouw_analyseset
from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.errors import PipelineError
from nlriochecker.externedata import ExternalData, load_external_data
from nlriochecker.meting import Meetbereik
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.studiegebied import _lees_geopackage, load_study_area
from nlriochecker.uitvoer.gpkg import (
    GEOPACKAGE_STAPPEN,
    RD_NEW,
    REDEN_MECHANISCH,
    REDEN_ONDERDRUKT,
    schrijf_geopackage,
)
from nlriochecker.uitvoer.melding import bouw_meldingen
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
RUNDATUM = date(2026, 8, 16)
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


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
    assert "meldinglocaties" not in soorten
    assert "mechanisch_riool" not in soorten
    assert soorten["meldingen"] == "attributes"
    assert soorten["overzicht_checks"] == "attributes"
    assert soorten["gwsw_run"] == "attributes"


def test_putten_en_strengen_dragen_leesbare_geometrie(tmp_path: Path) -> None:
    """De schrijfkant moet leveren wat de leeskant in studiegebied.py verwacht."""
    from nlriochecker.studiegebied import _ontleed_gpkg

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


def test_de_meldingentabel_houdt_elke_melding(tmp_path: Path) -> None:
    """`meldinglocaties` verviel als featurelaag; de tabel bleef, met alles erin."""
    run = _run("top011_hartlijnkruising.ttl", "TOP-011")
    meldingen = bouw_meldingen(run, RUNDATUM)
    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select count(*) from meldingen")[0][0] == len(meldingen)
    tabellen = {naam for (naam,) in _rijen(pad, "select name from sqlite_master")}
    assert "meldinglocaties" not in tabellen


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
    assert rij[2] == "v0.9"
    assert rij[3] == 0
    assert rij[4] == ""


def test_stijlen_staan_in_het_bestand(tmp_path: Path) -> None:
    """De ontvanger moet het bestand kunnen openen zonder handmatige stappen."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    stijlen = _rijen(
        pad, "select f_table_name, styleQML, useAsDefault from layer_styles order by f_table_name"
    )

    assert [naam for naam, _, _ in stijlen] == [
        "bouwwerken",
        "putten",
        "stelsels",
        "strengen",
        "waterdelen_zonder_zinker",
    ]
    for _, qml, standaard in stijlen:
        assert standaard == 1
        ET.fromstring(qml)


def test_stijltabel_is_als_laag_geregistreerd(tmp_path: Path) -> None:
    """Zonder rij in gpkg_contents vindt de OGR-provider layer_styles niet."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    rijen = _rijen(
        pad,
        "select data_type, srs_id from gpkg_contents where table_name = 'layer_styles'",
    )

    assert rijen == [("attributes", None)]


def test_stijlen_dragen_een_tijdstempel_in_iso8601(tmp_path: Path) -> None:
    """GDAL meldt elk ander formaat als non-conformant bij het lezen."""
    import re

    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    tijden = [tijd for (tijd,) in _rijen(pad, "select update_time from layer_styles")]

    assert tijden
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", tijd) for tijd in tijden)


def test_er_liggen_geen_losse_qml_bestanden_meer(tmp_path: Path) -> None:
    """Een sidecar-QML werkt niet bij meerdere lagen; hem toch neerleggen misleidt."""
    _schrijf(_run("schoon.ttl"), tmp_path)

    assert list(tmp_path.glob("*.qml")) == []


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


def test_zonder_analyseset_blijven_de_kolommen_leeg(tmp_path: Path) -> None:
    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    rij = _rijen(pad, "select kern_objecten, schil_objecten, dataset_objecten from gwsw_run")[0]
    assert rij == (None, None, None)


def test_de_analyseset_omvang_staat_in_de_runmetadata(tmp_path: Path) -> None:
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = _config()
    analyseset = bouw_analyseset(dataset, area, config)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    run = run_checks(context, ["NET-001"]).beperk_tot_studiegebied(area)
    pad = _schrijf(run, tmp_path)

    rij = _rijen(pad, "select kern_objecten, schil_objecten, dataset_objecten from gwsw_run")[0]
    assert rij == (
        len(analyseset.kern),
        len(analyseset.schil),
        analyseset.volledig_aantal,
    )


def test_export_overschrijft_geen_invoerbestand(tmp_path: Path) -> None:
    """De uitvoermap mag nooit de datamap zijn."""
    run = _run("schoon.ttl")

    with pytest.raises(Exception, match="invoerbestand"):
        _schrijf(run, TTL_DIR)


def test_geschreven_bestand_is_leesbaar_met_de_eigen_lezer(tmp_path: Path) -> None:
    """De lees- en schrijfkant houden elkaar zo in de gaten.

    `_lees_geopackage` is de productiecode die GeoPackages leest; vindt die de
    geschreven strengenlaag terug, dan klopt het formaat. Niet via
    `load_study_area`: die accepteert sinds de rapportage per gebied alleen nog
    vlakken, en een strengenlaag is er geen.
    """
    run = _run("schoon.ttl")
    pad = _schrijf(run, tmp_path)

    gelezen = _lees_geopackage(pad, "strengen")

    assert len(gelezen.features) == len(run.dataset.conduits)
    assert all(not vlak.geometrie.is_empty for vlak in gelezen.features)


def test_feature_id_is_het_fragment_en_de_uri_staat_erbij(tmp_path: Path) -> None:
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    rijen = _rijen(pad, "select feature_id, gwsw_uri from putten limit 1")

    feature_id, uri = rijen[0]
    assert "#" not in feature_id
    assert uri.endswith(f"#{feature_id}")


def test_meldingen_dragen_fragment_en_uri(tmp_path: Path) -> None:
    run = _run("top005_dubbele_put.ttl", "TOP-005")
    pad = _schrijf(run, tmp_path)

    rijen = _rijen(pad, "select feature_id, gwsw_uri, feature_id_2, gwsw_uri_2 from meldingen")

    assert rijen
    for feature_id, uri, tweede_id, tweede_uri in rijen:
        assert "#" not in feature_id
        assert uri.endswith(f"#{feature_id}")
        assert "#" not in tweede_id
        assert tweede_uri.endswith(f"#{tweede_id}")


def test_meldingen_op_dezelfde_plek_worden_genummerd(tmp_path: Path) -> None:
    """Twee meldingen op hetzelfde punt moeten in de kaart uit elkaar te halen zijn.

    Groepeer op de echte locatie (niet op `stapel_aantal` alleen): anders bewijst de
    assertie niets meer zodra er twee stapels van gelijke grootte zijn -- hun
    volgnummers zouden dan door elkaar heen gesorteerd worden en toevallig weer op
    `1..aantal` kunnen uitkomen, of juist een correcte nummering laten falen.
    """
    from collections import defaultdict

    from nlriochecker.uitvoer.gpkg import STAPEL_RASTER_M

    run = _run("top005_dubbele_put.ttl")
    pad = _schrijf(run, tmp_path)

    rijen = _rijen(pad, "select x, y, stapel_aantal, stapel_nr from meldingen where x is not null")
    assert rijen

    per_plek: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for x, y, aantal, nummer in rijen:
        sleutel = (round(x / STAPEL_RASTER_M), round(y / STAPEL_RASTER_M))
        per_plek[sleutel].append((aantal, nummer))

    # De fixture moet zelf minstens een echte stapel bevatten, anders toetst deze
    # test niets.
    assert any(len(groep) > 1 for groep in per_plek.values())

    for groep in per_plek.values():
        aantallen = {aantal for aantal, _ in groep}
        assert aantallen == {len(groep)}
        nummers = sorted(nummer for _, nummer in groep)
        assert nummers == list(range(1, len(groep) + 1))


def test_stapelnummering_is_onafhankelijk_van_lijstvolgorde(tmp_path: Path) -> None:
    """De nummering moet stabiel zijn, ook als de meldingenlijst anders geordend is.

    Beide runs dezelfde meldingenlijst in dezelfde volgorde meegeven bewijst deze
    stabiliteit niet: een implementatie die simpelweg op lijstvolgorde nummert zou
    die test even goed doorstaan. Pas de tweede run een omgekeerde lijst toe, zodat
    alleen sortering op melding-ID -- en niet lijstvolgorde -- tot dezelfde uitkomst
    kan leiden.
    """
    run = _run("top005_dubbele_put.ttl")
    meldingen = bouw_meldingen(run, RUNDATUM)

    eerste_pad = schrijf_geopackage(run, meldingen, tmp_path / "a", RUNDATUM)
    tweede_pad = schrijf_geopackage(run, list(reversed(meldingen)), tmp_path / "b", RUNDATUM)

    eerste = {
        melding_id: (aantal, nummer)
        for melding_id, aantal, nummer in _rijen(
            eerste_pad, "select melding_id, stapel_aantal, stapel_nr from meldingen"
        )
    }
    tweede = {
        melding_id: (aantal, nummer)
        for melding_id, aantal, nummer in _rijen(
            tweede_pad, "select melding_id, stapel_aantal, stapel_nr from meldingen"
        )
    }

    assert eerste
    assert eerste == tweede


def test_mechanisch_riool_staat_grijs_tussen_de_strengen(tmp_path: Path) -> None:
    """Het objecttype blijft kloppen; alleen de status zegt dat er niets getoetst is."""
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    rijen = _rijen(pad, "select objecttype, status from strengen where objecttype = 'Persleiding'")

    assert rijen == [("Persleiding", "grijs")]


def test_mechanisch_riool_zegt_in_zijn_popup_waarom_het_grijs_is(tmp_path: Path) -> None:
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    ((popup,),) = _rijen(pad, "select popup_html from strengen where objecttype = 'Persleiding'")

    assert "mechanisch riool" in popup


def test_de_strengen_staan_in_een_vaste_volgorde(tmp_path: Path) -> None:
    """Ongesorteerd itereren zou de fid-toekenning tussen twee runs laten wisselen."""
    pad = _schrijf(_run("mechanisch_riool_twee.ttl"), tmp_path)

    labels = [rij[0] for rij in _rijen(pad, "select label from strengen order by fid")]

    assert labels == sorted(labels)


def test_runmetadata_telt_de_lagen(tmp_path: Path) -> None:
    """`n_strengen` telt de rijen in de laag; `n_mechanisch` hoeveel daarvan mechanisch zijn.

    Niet hoeveel er grijs zijn: met een studiegebied zit de contextschil ook in de laag,
    en een mechanische streng met een melding is niet grijs maar gekleurd.
    """
    pad = _schrijf(_run("mechanisch_riool.ttl"), tmp_path)

    ((putten, strengen, mechanisch),) = _rijen(
        pad, "select n_putten, n_strengen, n_mechanisch from gwsw_run"
    )

    assert (putten, strengen, mechanisch) == (4, 2, 1)


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


def test_featurelagen_dragen_het_begindatumjaar(tmp_path: Path) -> None:
    """Het aanlegjaar als kolom om op te filteren; leeg als het object er geen draagt.

    `hgt_schoon.ttl` heeft één streng met begindatum 1980-01-01 en twee putten zonder
    begindatum (issue #61).
    """
    pad = _schrijf(_run("hgt_schoon.ttl"), tmp_path)

    strengen = dict(_rijen(pad, "select label, begindatum_jaar from strengen"))
    putten = dict(_rijen(pad, "select label, begindatum_jaar from putten"))

    assert strengen == {"1": 1980}
    assert putten == {"A": None, "B": None}


def test_put_zonder_begindatum_kleurt_rood_door_attr018(tmp_path: Path) -> None:
    """Issue #61: een object zonder aanlegjaar was groen op de kaart, en groen betekent
    daar 'beoordeeld en niets gevonden'. ATTR-018 hoort het rood te maken."""
    pad = _schrijf(_run("attr018_zonder_begindatum.ttl"), tmp_path)

    putten = {
        label: (status, checks_f)
        for label, status, checks_f in _rijen(pad, "select label, status, checks_f from putten")
    }

    assert putten["A"][0] == "rood"
    assert "ATTR-018" in putten["A"][1]
    assert "ATTR-018" not in putten["B"][1]


def test_strengen_dragen_de_bob_richting(tmp_path: Path) -> None:
    pad = _schrijf(_run("hgt_schoon.ttl"), tmp_path)

    rijen = _rijen(pad, "select richting_bob, bob_verval_m from strengen")

    assert rijen
    assert {rij[0] for rij in rijen} <= {"mee", "tegen", "onbekend"}
    for richting, verval in rijen:
        if richting == "mee":
            assert verval > 0
        elif richting == "tegen":
            assert verval < 0
        else:
            assert verval is None or verval == 0


def test_omgekeerd_getekende_streng_meet_het_verval_langs_de_lijn(tmp_path: Path) -> None:
    """De pijl volgt de getekende lijn; het verval hoort daar dus bij te horen."""
    pad = _schrijf(_run("richting_omgekeerd_met_bob.ttl"), tmp_path)

    ((richting, verval),) = _rijen(pad, "select richting_bob, bob_verval_m from strengen")

    # Administratief daalt de bodem 0,50 m van A naar B, maar de lijn is van B naar A
    # getekend; langs de lijn stijgt de bodem dus.
    assert richting == "tegen"
    assert verval == pytest.approx(-0.50)


def test_onbepaalbare_tekenrichting_geeft_onbekend_geen_administratief_terugvalteken(
    tmp_path: Path,
) -> None:
    """Zonder bekende tekenrichting mag de kolom niet alsnog mee/tegen suggereren.

    De streng heeft dezelfde put aan begin- en eindpunt: er is geen van-naar-richting
    om de getekende lijn tegen af te zetten. Beide BOB's zijn wel ingevuld en
    verschillend (bob_verval is dus niet None of nul); de reden dat de kolom
    `onbekend` moet zijn ligt in de tekenrichting, niet in de BOB's.
    """
    pad = _schrijf(_run("richting_niet_bepaalbaar_met_bob.ttl"), tmp_path)

    ((richting, verval),) = _rijen(pad, "select richting_bob, bob_verval_m from strengen")

    assert richting == "onbekend"
    assert verval is None


def test_runmetadata_noemt_de_cfk_set_en_of_die_volledig_is(tmp_path: Path) -> None:
    """De CFK-set hoort bij de run, dus in gwsw_run en niet op elke melding."""
    run = replace(_run("schoon.ttl"), meetbereik=Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"]))

    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select cfk_set, volledig from gwsw_run") == [("Hyd, MdsPlan", 0)]


def test_runmetadata_bij_een_volledige_meting(tmp_path: Path) -> None:
    """Op de volle set getoetst: het veld zegt dat, en noemt alle drie de klassen."""
    run = replace(_run("schoon.ttl"), meetbereik=Meetbereik.van(VEREIST, VEREIST))

    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select cfk_set, volledig from gwsw_run") == [("Hyd, MdsPlan, MdsProj", 1)]


def test_runmetadata_zonder_meetbereik_laat_de_velden_leeg(tmp_path: Path) -> None:
    """Een run zonder nulmeting beweert niet dat hij volledig gemeten is."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    assert _rijen(pad, "select cfk_set, volledig from gwsw_run") == [("", 0)]


def _ext_bronnen() -> ExternalData:
    """De miniatuurbronnen uit tests/fixtures/gis/ext."""
    basis = load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": "bag_pand.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    return load_external_data(basis, GIS_DIR / "ext")


def _ext_run() -> CheckRun:
    """Een run met de EXT-checks op de scenariofixture."""
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    context = CheckContext(dataset=dataset, config=_config(), bronnen=_ext_bronnen())
    return run_checks(context, ["EXT-001", "EXT-002", "EXT-003"])


def _laagrijen(pad: Path, laag: str) -> list[dict]:
    """De rijen van een laag als dicts, zonder geometrie en fid."""
    con = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [
            {sleutel: rij[sleutel] for sleutel in rij.keys() if sleutel not in {"geom", "fid"}}
            for rij in con.execute(f'select * from "{laag}"')
        ]
    finally:
        con.close()


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_bouwwerkenlaag_is_exact_de_verzameling_uit_de_meldingen(tmp_path: Path) -> None:
    """De kerntest: niets erbij, niets eraf."""
    run = _ext_run()
    meldingen = bouw_meldingen(run, RUNDATUM)
    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verwacht = {m.object2_uri for m in meldingen if m.check_id == "EXT-001"}

    assert {rij["id"] for rij in _laagrijen(pad, "bouwwerken")} == verwacht


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_bouwwerk_wordt_ontdubbeld_met_de_sterkste_relatie(tmp_path: Path) -> None:
    """Vier objecten raken hetzelfde pand: een rij, vier meldingen, binnen wint."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rijen = _laagrijen(pad, "bouwwerken")

    assert len(rijen) == 1
    assert rijen[0]["id"] == "bgt:pand/pand-1"
    assert rijen[0]["bron"] == "bgt_pand"
    assert rijen[0]["bronbestand"] == "bgt.gpkg"
    assert rijen[0]["label"] == "pand pand-1"
    assert rijen[0]["relatie"] == "binnen"
    assert rijen[0]["afstand_min_m"] == 0.0
    assert rijen[0]["aantal_meldingen"] == 4
    assert rijen[0]["check_ids"] == "EXT-001"


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_waterdelenlaag_volgt_ext003_en_niet_ext002(tmp_path: Path) -> None:
    """Streng 3 kruist water-2 met een duiker; dat waterdeel hoort er niet in."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rijen = _laagrijen(pad, "waterdelen_zonder_zinker")

    # Water-5 en water-7 komen erbij: streng 9 doorkruist beide greppels (issue #59).
    assert [rij["id"] for rij in rijen] == [
        "bgt:waterdeel/water-1",
        "bgt:waterdeel/water-5",
        "bgt:waterdeel/water-7",
    ]
    assert rijen[0]["watertype"] == "waterloop"
    assert rijen[0]["aantal_meldingen"] == 1
    assert rijen[0]["check_ids"] == "EXT-003"
    assert rijen[0]["buffer_m"] == _config().drempels.ext_watergang_buffer_m


def test_lege_lagen_bestaan_en_zijn_geregistreerd(tmp_path: Path) -> None:
    """Een run zonder EXT-treffers heeft beide lagen, leeg, met stijl en registratie."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    for laag in ("bouwwerken", "waterdelen_zonder_zinker"):
        assert _rijen(pad, f'select count(*) from "{laag}"')[0][0] == 0
        geregistreerd = _rijen(pad, "select count(*) from gpkg_contents where table_name = ?", laag)
        gestyled = _rijen(pad, "select count(*) from layer_styles where f_table_name = ?", laag)
        assert (geregistreerd[0][0], gestyled[0][0]) == (1, 1)


def _bronnen_met_pand(
    map_pad: Path,
    vlakken: list[tuple[dict[str, str], object]],
    kolommen: tuple[str, ...] = ("lokaal_id",),
) -> ExternalData:
    """Miniatuurbronnen met een zelfgekozen pandenlaag, zonder dekkingspoort."""
    map_pad.mkdir(parents=True, exist_ok=True)
    schrijf_vlakken(map_pad / "bgt.gpkg", "pand", vlakken, kolommen)
    schrijf_vlakken(
        map_pad / "studiegebied.gpkg",
        "studiegebied",
        [({"lokaal_id": "gebied"}, box(990, 1985, 1160, 2015))],
    )
    basis = load_check_config().bronnen.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": None,
            "nwb_wegvakken": None,
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": None,
            "bgt_pandlagen": ["pand"],
        }
    )
    return load_external_data(basis, map_pad)


def _run_met_bronnen(bronnen: ExternalData, *check_ids: str) -> CheckRun:
    """Draait checks op de EXT-scenariofixture met eigen bronnen."""
    dataset = load_dataset(TTL_DIR / "ext_scenario.ttl")
    context = CheckContext(dataset=dataset, config=_config(), bronnen=bronnen)
    return run_checks(context, list(check_ids))


def test_nabij_geval_komt_in_de_laag(tmp_path: Path) -> None:
    """Een pand op 0,5 m van streng 1 en knoop A: geen raakvlak, wel binnen de buffer."""
    bronnen = _bronnen_met_pand(
        tmp_path / "bron", [({"lokaal_id": "p-nabij"}, box(1000, 2000.5, 1010, 2005))]
    )
    run = _run_met_bronnen(bronnen, "EXT-001")

    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path / "uit", RUNDATUM)
    rijen = _laagrijen(pad, "bouwwerken")

    assert [rij["id"] for rij in rijen] == ["bgt:pand/p-nabij"]
    assert rijen[0]["relatie"] == "nabij"
    assert rijen[0]["aantal_meldingen"] == 2
    assert rijen[0]["afstand_min_m"] == 0.5


def test_bron_zonder_id_levert_een_geo_sleutel(tmp_path: Path) -> None:
    """Externe data is context, geen poort: een bron zonder ID mag niet hard falen."""
    bronnen = _bronnen_met_pand(
        tmp_path / "bron",
        [({"soort": "pand"}, box(1000, 2000.5, 1010, 2005))],
        kolommen=("soort",),
    )
    run = _run_met_bronnen(bronnen, "EXT-001")

    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path / "uit", RUNDATUM)
    rijen = _laagrijen(pad, "bouwwerken")

    assert rijen[0]["id"].startswith("geo:")
    assert any("geo:" in note for note in run.outcomes[0].notes)


def test_geo_sleutel_is_stabiel_over_runs(tmp_path: Path) -> None:
    """Twee identieke runs moeten dezelfde sleutel opleveren."""
    sleutels = []
    for naam in ("een", "twee"):
        bronnen = _bronnen_met_pand(
            tmp_path / naam,
            [({"soort": "pand"}, box(1000, 2000.5, 1010, 2005))],
            kolommen=("soort",),
        )
        run = _run_met_bronnen(bronnen, "EXT-001")
        sleutels.append({finding.details["object2_uri"] for finding in run.findings})

    assert sleutels[0] == sleutels[1]
    assert len(sleutels[0]) == 1


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_runmetadata_telt_de_trefferlagen_mee(tmp_path: Path) -> None:
    """De aantallen per laag horen ook in gwsw_run te staan, net als de andere lagen."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rij = _rijen(pad, "select n_bouwwerken, n_waterdelen from gwsw_run")[0]

    # Drie waterdelen: EXT-003 meldt sinds issue #59 ook water-5 en water-7, de twee
    # greppels die streng 9 doorkruist.
    assert rij == (1, 3)


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_waterdeel_label_noemt_type_en_identificatie(tmp_path: Path) -> None:
    """`watertype` is om op te filteren, `label` is om iets in terug te vinden."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rij = _laagrijen(pad, "waterdelen_zonder_zinker")[0]

    assert rij["watertype"] == "waterloop"
    assert rij["label"] == "waterloop water-1"


def test_melding_zonder_geregistreerde_treffer_faalt_luid(tmp_path: Path) -> None:
    """Een laag die stil kleiner is dan de uitslag is precies wat hier uitgesloten is."""
    run = _run("schoon.ttl", "TOP-001")
    melding = replace(
        bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)[0],
        check_id="EXT-001",
        object2_uri="bgt:pand/verdwenen",
    )

    with pytest.raises(PipelineError, match="trefferregister"):
        schrijf_geopackage(run, [melding], tmp_path, RUNDATUM)


def test_de_voortgangsstappen_zijn_precies_de_vastgelegde_rij(tmp_path: Path) -> None:
    """Het fase-totaal en de gezette stappen mogen niet uit elkaar lopen.

    Het totaal was een met de hand geteld getal dat over drie functies verspreid
    stond. Telde iemand een laag erbij zonder het getal te verhogen, dan liep de balk
    over; verwijderde iemand er een, dan stopte hij te vroeg. Nu volgt het totaal uit
    dezelfde rij als de labels, en deze test bewaakt dat de rij klopt met wat er
    daadwerkelijk gezet wordt.
    """
    opnemer = _Stapopnemer()
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM, voortgang=opnemer)

    assert opnemer.totaal == len(GEOPACKAGE_STAPPEN)
    assert tuple(opnemer.labels) == GEOPACKAGE_STAPPEN


class _Stapopnemer:
    """Legt het fase-totaal en de labels van de gezette stappen vast."""

    def __init__(self) -> None:
        self.totaal: int | None = None
        self.labels: list[str] = []

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Onthoudt het aangekondigde totaal."""
        self.totaal = totaal

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Onthoudt het label van deze stap."""
        if label is not None:
            self.labels.append(label)

    def einde_fase(self) -> None:
        """Doet niets; het einde zegt hier niets."""


class TestStatusEnPopup:
    """De twee kolommen waarop de symbologie en de maptip rusten (issue #13)."""

    def test_elk_object_draagt_een_status_uit_de_vier(self, tmp_path: Path) -> None:
        from nlriochecker.uitvoer.objectkaart import STATUSSEN

        pad = _schrijf(_run("hgt010_diameterverjonging.ttl"), tmp_path)

        waarden = {rij[0] for rij in _rijen(pad, "select status from putten")}
        waarden |= {rij[0] for rij in _rijen(pad, "select status from strengen")}

        assert waarden <= set(STATUSSEN)
        # Een deelverzameling-assertie alleen zou ook slagen als alles groen was; de
        # fixture hoort meer dan een status op te leveren.
        assert len(waarden) > 1

    def test_zonder_klassenhierarchie_kleurt_de_kaart_niet_groen(self, tmp_path: Path) -> None:
        """Groen betekent hier "beoordeeld en niets gevonden"; dat mag dan niet.

        Zonder de subklassen van Knooppunt en Verbinding heeft de lader knopen en
        strengen op geometrie herkend en draaiden de checks over een onvolledige
        selectie. Het voorbehoud staat wel in `gwsw_run`, maar dat is een
        metadatatabel die niemand in QGIS openslaat -- terwijl de kaart eronder de
        tegenovergestelde boodschap uitstraalt. Grijs is precies de waarde die "niet
        beoordeeld en niets gevonden" zegt.

        De eerste helft is de tegenproef: dezelfde fixture *met* haar hierarchie levert
        wel degelijk groen op, dus deze test kan werkelijk falen.
        """
        bron = TTL_DIR / "schoon.ttl"
        kaal = tmp_path / "zonder_wortels.ttl"
        kaal.write_text(
            "\n".join(
                regel
                for regel in bron.read_text(encoding="utf-8").splitlines()
                if "subClassOf gwsw:Knooppunt" not in regel
                and "subClassOf gwsw:Verbinding" not in regel
            )
            + "\n",
            encoding="utf-8",
        )

        met = _schrijf(_run("schoon.ttl"), tmp_path / "met")
        zonder = load_dataset(kaal)
        assert zonder.klassenhierarchie_bekend is False
        pad = _schrijf(
            run_checks(CheckContext(dataset=zonder, config=_config())), tmp_path / "zonder"
        )

        vraag = (
            "select status, popup_html from putten union all "
            "select status, popup_html from strengen"
        )
        assert any(status == "groen" for status, _ in _rijen(met, vraag))
        rijen = _rijen(pad, vraag)
        assert rijen
        assert all(status != "groen" for status, _ in rijen)
        grijs = [popup for status, popup in rijen if status == "grijs"]
        assert grijs and all("klassenhierarchie" in popup for popup in grijs)

    def test_de_status_klopt_met_de_meldingentabel(self, tmp_path: Path) -> None:
        """De kolom en de tabel komen uit dezelfde stroom; ze mogen niet uiteenlopen."""
        run = _run("hgt010_diameterverjonging.ttl")
        pad = _schrijf(run, tmp_path)

        rijen = _rijen(
            pad,
            "select o.gwsw_uri, o.status, "
            "  sum(case when m.ernst = 'F' and m.systemisch = 0 then 1 else 0 end), "
            "  sum(case when m.ernst = 'W' and m.systemisch = 0 then 1 else 0 end) "
            "from (select gwsw_uri, status from putten "
            "      union all select gwsw_uri, status from strengen) o "
            "left join meldingen m on m.gwsw_uri = o.gwsw_uri "
            "group by o.gwsw_uri, o.status",
        )

        assert rijen
        for _uri, status, fouten, waarschuwingen in rijen:
            if status == "grijs":
                continue
            verwacht = "rood" if fouten else ("oranje" if waarschuwingen else "groen")
            assert status == verwacht

    def test_de_popup_noemt_de_meldingen_van_het_object(self, tmp_path: Path) -> None:
        run = _run("hgt010_diameterverjonging.ttl", "HGT-010")
        pad = _schrijf(run, tmp_path)
        meldingen = bouw_meldingen(run, RUNDATUM)
        eerste = meldingen[0]

        ((popup,),) = _rijen(
            pad, "select popup_html from strengen where gwsw_uri = ?", eerste.object_uri
        )

        assert eerste.check_id in popup

    def test_een_streng_noemt_stelsel_lengte_en_bob_in_haar_popup(self, tmp_path: Path) -> None:
        pad = _schrijf(_run("net003_tegen_de_richting.ttl"), tmp_path)

        ((popup,),) = _rijen(pad, "select popup_html from strengen order by fid limit 1")

        assert "Stelsel" in popup
        assert "Lengte" in popup
        assert "BOB" in popup

    def test_de_popup_van_een_put_noemt_geen_richtingsregel(self, tmp_path: Path) -> None:
        """Stelsel, lengte en richting horen bij een streng; een put heeft ze niet.

        De assertie kijkt naar het feitenblok en niet naar de hele popup: een
        checkboodschap mag best over een BOB gaan.
        """
        pad = _schrijf(_run("net003_tegen_de_richting.ttl"), tmp_path)

        popups = [rij[0] for rij in _rijen(pad, "select popup_html from putten order by fid")]

        assert popups
        assert all('class="f"' not in popup for popup in popups)

    def test_de_ring_om_het_gebied_komt_grijs_mee(self, tmp_path: Path) -> None:
        """Wat naast het gebied ligt hoort zichtbaar te zijn, maar wel begrensd.

        De ring is `Analyseset.buffer` en niet de hele schil: die bevat ook de
        samenhangende vrijvervalcomponent, en die kan in een stad het halve net zijn.
        """
        from nlriochecker.meting import Meetbereik
        from nlriochecker.studiegebied import load_studiegebieden
        from nlriochecker.toetsloop import toets_gebieden

        gebieden = load_studiegebieden(
            Path(__file__).parent / "fixtures" / "gis" / "buurt_noord.gpkg"
        )
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )
        run = runs[0].run
        assert run.analyseset is not None and run.analyseset.buffer
        pad = _schrijf(run, tmp_path)

        statussen = dict(
            _rijen(
                pad,
                "select gwsw_uri, status from putten union all "
                "select gwsw_uri, status from strengen",
            )
        )

        for uri in run.analyseset.buffer:
            assert statussen.get(uri) == "grijs", uri
        assert any(statussen.get(uri) != "grijs" for uri in run.analyseset.kern)
        buiten_de_ring = run.analyseset.schil - run.analyseset.buffer
        assert all(uri not in statussen for uri in buiten_de_ring)


def test_afvoerpad_kolommen_op_putten_en_strengen(tmp_path: Path) -> None:
    """#18 fase 1: elke put en streng draagt het bereikte uitstroompunt met padmaat.

    De keten A->B->C->gemaal levert per streng hetzelfde eindpunt en een aflopend
    aantal stappen; de meters (50 m per streng) tellen op.
    """
    pad = _schrijf(_run("net_afvoerpad_keten.ttl", "NET-001"), tmp_path)

    strengen = dict(
        (label, (eindpunt, stappen, meters))
        for label, eindpunt, stappen, meters in _rijen(
            pad, "select label, afvoer_eindpunt, afvoer_stappen, afvoer_meters from strengen"
        )
    )
    assert strengen["1"] == ("G", 3, 150.0)
    assert strengen["2"] == ("G", 2, 100.0)
    assert strengen["3"] == ("G", 1, 50.0)

    putten = dict(
        (label, (eindpunt, stappen, meters))
        for label, eindpunt, stappen, meters in _rijen(
            pad, "select label, afvoer_eindpunt, afvoer_stappen, afvoer_meters from putten"
        )
    )
    assert putten["A"] == ("G", 3, 150.0)
    assert putten["G"] == ("G", 0, 0.0)


def test_afvoerpad_zonder_lijn_geeft_stappen_zonder_meters(tmp_path: Path) -> None:
    """Een pad over een streng zonder bruikbare lijn krijgt wel stappen, geen meters.

    De streng zelf heeft geen lijngeometrie en valt daarom buiten de LINESTRING-laag;
    put A ligt er wel in en erft het gat: het bereikt het gemaal in een stap, maar de
    padlengte in meters is niet te geven.
    """
    pad = _schrijf(_run("net_afvoerpad_zonder_lijn.ttl", "NET-001"), tmp_path)

    ((eindpunt, stappen, meters),) = _rijen(
        pad, "select afvoer_eindpunt, afvoer_stappen, afvoer_meters from putten where label = 'A'"
    )
    assert (eindpunt, stappen, meters) == ("G", 1, None)


def test_stelsels_laag_is_een_multipolygon_in_gpkg_contents(tmp_path: Path) -> None:
    """De cartografische stelsellaag staat geregistreerd, anders vindt QGIS haar niet."""
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    ((soort,),) = _rijen(
        pad, "select geometry_type_name from gpkg_geometry_columns where table_name = 'stelsels'"
    )
    assert soort == "MULTIPOLYGON"
    contents = {naam for (naam,) in _rijen(pad, "select table_name from gpkg_contents")}
    assert "stelsels" in contents


def test_stelsels_laag_slaat_de_put_bucket_over(tmp_path: Path) -> None:
    """Alleen stelsels met strengen krijgen een vlak; de hemelwaterbucket valt weg."""
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    labels = {label for (label,) in _rijen(pad, "select label from stelsels")}

    assert labels == {"vuilwater-1", "gemengd-1"}


def test_stelsels_dragen_type_afvoer_en_omvang(tmp_path: Path) -> None:
    """Type, bereikt_eindpunt en de tellingen per stelsel.

    Het vuilwaterstelsel bereikt het gemaal (twee strengen van 50 m, samen 100 m);
    het gemengde stelsel heeft geen afvoerroute (een streng van 50 m).
    """
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    rijen = {
        label: (stelseltype, bereikt, n_strengen, lengte)
        for label, stelseltype, bereikt, n_strengen, lengte in _rijen(
            pad,
            "select label, stelseltype, bereikt_eindpunt, n_strengen, strenglengte_m from stelsels",
        )
    }
    assert rijen["vuilwater-1"] == ("Vuilwaterstelsel", 1, 2, 100.0)
    assert rijen["gemengd-1"] == ("GemengdStelsel", 0, 1, 50.0)


def test_stelsels_tellen_de_putten_aan_de_strengeinden(tmp_path: Path) -> None:
    """`n_putten` telt de distinct netwerkknopen aan de eindpunten van de strengen."""
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    putten = dict(_rijen(pad, "select label, n_putten from stelsels"))

    assert putten["vuilwater-1"] == 3  # PutA, PutB en het gemaal
    assert putten["gemengd-1"] == 2  # PutC en PutD


def test_stelsels_dragen_een_leesbaar_vlak(tmp_path: Path) -> None:
    """De geometrie is een leesbare MULTIPOLYGON om de strengen heen."""
    from shapely import wkb

    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    ((blob,),) = _rijen(pad, "select geom from stelsels where label = 'gemengd-1'")
    vorm = wkb.loads(bytes(blob)[8:])  # de GPKG-kop (magic, versie, vlaggen, srs) overslaan
    assert vorm.geom_type == "MultiPolygon"
    assert not vorm.is_empty


def test_runmetadata_telt_de_stelsels(tmp_path: Path) -> None:
    """`n_stelsels` maakt expliciet hoeveel stelsels een vlak kregen (put-buckets niet)."""
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    ((aantal,),) = _rijen(pad, "select n_stelsels from gwsw_run")

    assert aantal == 2


def test_stelselmelding_uit_de_nulmeting_landt_op_de_stelsellaag(tmp_path: Path) -> None:
    """De bonus van #25: een SHACL-overtreding op een stelsel komt op zijn vlak.

    De focusnode `vw_geb_1` is geen knoop of streng maar een geregistreerd stelsel; de
    join koppelt de overtreding aan de stelsel-URI, en zo verschijnt ze op de kaart via
    het stelselvlak in plaats van nergens op uit te komen.
    """
    from nlriochecker.meting import laad_nulmeting
    from nlriochecker.nulbevinding import bouw_nulbevindingen

    shacl = Path(__file__).parent / "fixtures" / "shacl"
    rapporten = [shacl / "join_mdsplan.csv", shacl / "join_mdsproj.csv"]
    nulmeting = laad_nulmeting(rapporten, VEREIST[1:])
    basis = _run("nulmeting_join.ttl")
    nulbevindingen = bouw_nulbevindingen(nulmeting, basis.dataset, 0.80)
    run = replace(
        basis, nulbevindingen=nulbevindingen, meetbereik=Meetbereik.van(VEREIST, VEREIST[1:])
    )

    pad = _schrijf(run, tmp_path)

    ((n_meldingen, popup),) = _rijen(
        pad, "select n_meldingen, popup_html from stelsels where label = 'vw-1'"
    )
    assert n_meldingen >= 1
    assert "Vuilwaterstelsel_Lozingspunt_card" in popup


# Issue #65: onderdrukking uit `[rapport]`. De fixture: vrijvervalstreng L1 (GemengdRiool)
# kruist persleiding L2 (Persleiding). TOP-011 meldt het paar een keer, met L1 als
# hoofdobject en L2 als tweede object; de nulbevinding hieronder geeft L2 een eigen
# melding, zodat er iets te onderdrukken valt.
def _run_onderdrukt(klassen: Sequence[str], checks: Sequence[str] = ()) -> CheckRun:
    """TOP-011 op de kruisingsfixture, met de twee lijsten uit `[rapport]` gezet."""
    config = _config()
    config.rapport.onderdruk_klassen = list(klassen)
    config.rapport.onderdruk_checks = list(checks)
    dataset = load_dataset(TTL_DIR / "onderdruk_persleiding.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config), ["TOP-011"])
    return replace(run, nulbevindingen=(_nulbevinding_op_de_persleiding(),))


def _nulbevinding_op_de_persleiding() -> Nulbevinding:
    """Een nulmetingmelding op L2, het enige gebrek dat de persleiding zelf draagt."""
    return Nulbevinding(
        check_id="NULMETING-Put_HoogtePut_card",
        vorm="Put_HoogtePut_card",
        focus_node="L2",
        ernst="F",
        object_uri="http://example.org/toets#L2",
        object_label="2",
        objecttype="Persleiding",
        boodschap="aantal voorkomens wijkt af (exact=1)",
        waarde="te weinig voorkomens",
        cfk=("MdsPlan",),
        systemisch=False,
        herleid=True,
    )


def _strengen_uit_de_stroom(run: CheckRun, map_: Path) -> dict[str, dict]:
    """Schrijft de uitvoer uit de echte meldingenstroom en leest de laag `strengen`."""
    uitvoer = schrijf_uitvoer(run, map_, RUNDATUM, met_json=False)
    assert uitvoer.geopackage is not None
    return {rij["feature_id"]: rij for rij in _laagrijen(uitvoer.geopackage, "strengen")}


def test_een_onderdrukte_persleiding_is_grijs_met_de_reden(tmp_path: Path) -> None:
    """Alle meldingen weg -> grijs; en de reden is de onderdrukking, niet 'mechanisch'."""
    rijen = _strengen_uit_de_stroom(_run_onderdrukt(["MechanischeTransportleiding"]), tmp_path)

    assert rijen["L2"]["status"] == "grijs"
    assert REDEN_ONDERDRUKT in rijen["L2"]["popup_html"]
    assert REDEN_MECHANISCH not in rijen["L2"]["popup_html"]
    assert rijen["L1"]["status"] != "grijs"
    assert REDEN_ONDERDRUKT not in rijen["L1"]["popup_html"]


def test_een_niet_mechanische_onderdrukte_klasse_leest_grijs_en_niet_groen(
    tmp_path: Path,
) -> None:
    """Grijs met de onderdrukkingsreden; groen zou 'beoordeeld en niets gevonden' beweren."""
    rijen = _strengen_uit_de_stroom(_run_onderdrukt(["GemengdRiool"]), tmp_path)

    assert rijen["L1"]["status"] == "grijs"
    assert REDEN_ONDERDRUKT in rijen["L1"]["popup_html"]
    # L2 is niet onderdrukt en blijft grijs om de oude reden: mechanisch riool.
    assert rijen["L2"]["status"] == "rood"
    assert REDEN_MECHANISCH in rijen["L2"]["popup_html"]


def test_gwsw_run_draagt_de_lijsten_en_de_telling(tmp_path: Path) -> None:
    """De keuze hoort bij de run, dus in `gwsw_run` en niet op elke melding."""
    uitvoer = schrijf_uitvoer(
        _run_onderdrukt(["MechanischeTransportleiding"]), tmp_path, RUNDATUM, met_json=False
    )

    assert uitvoer.geopackage is not None
    assert _rijen(
        uitvoer.geopackage,
        "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run",
    ) == [("MechanischeTransportleiding", "", 1)]


def test_gwsw_run_zonder_onderdrukking_telt_nul(tmp_path: Path) -> None:
    """Zonder lijsten blijft de tabel zeggen dat er niets weggehouden is."""
    uitvoer = schrijf_uitvoer(_run_onderdrukt([]), tmp_path, RUNDATUM, met_json=False)

    assert uitvoer.geopackage is not None
    assert _rijen(
        uitvoer.geopackage,
        "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run",
    ) == [("", "", 0)]
