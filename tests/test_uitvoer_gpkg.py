"""Tests voor de GeoPackage-export.

De GPKG wordt met `sqlite3` en shapely geschreven, dezelfde route waarmee
`studiegebied.py` er al een leest. Deze tests lezen het geschreven bestand ook weer
met `sqlite3` terug, zodat lees- en schrijfkant elkaar in de gaten houden.
"""

from __future__ import annotations

import json
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
from nlriochecker.checks import CheckContext, CheckRun, Severity, run_checks
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
from nlriochecker.uitvoer.melding import bouw_meldingen, bouw_meldingenstroom
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
RUNDATUM = date(2026, 8, 16)
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten.

    De minimumpopulatie van BO-59 staat op 1. De fixtures tellen een handvol objecten
    en halen de productiewaarde van 100 nooit; zonder deze verlaging vouwt niets samen
    en is het gedrag rond systemische meldingen (status, popup, vlakkenlaag) hier niet
    te tonen.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    config.rapport.systemisch_minimum_bekeken = 1
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


def test_overzicht_checks_labelt_waarover_bekeken_geteld_is(tmp_path: Path) -> None:
    """`percentage_populatie` deelt door `bekeken`; zonder label is dat onvergelijkbaar.

    ADM-002 telt de volledige export, TOP-013 de analyseset (hier gelijk, want er is
    geen studiegebied) en ATTR-014 kenmerkinstanties. `populatie` staat daarnaast en is
    de declaratie van de check, geen noemer: RVZ-011 noemt zijn kenmerken en ADM-007,
    die niets declareert, blijft leeg -- "de hele export" naast `percentage_populatie`
    zou juist het misverstand terugbrengen. Zie issue #77 en BO-58.
    """
    run = _run("top013_parallel.ttl", "ADM-002", "ADM-007", "ATTR-014", "RVZ-011", "TOP-013")
    pad = _schrijf(run, tmp_path)

    rijen = dict(
        (check_id, (scope, populatie))
        for check_id, scope, populatie in _rijen(
            pad, "select check_id, bekeken_scope, populatie from overzicht_checks"
        )
    )

    assert rijen["TOP-013"] == ("analyseset", "leidingen, netwerkknopen, vrijvervalrioolleidingen")
    assert rijen["ADM-002"] == ("volledige_export", "leidingen, netwerkknopen")
    assert rijen["ATTR-014"] == ("attribuut_instanties", "alle kenmerken")
    assert rijen["RVZ-011"] == (
        "analyseset",
        "Drempelbreedte, Drempelniveau, Maaiveldhoogte, Putdekselniveau",
    )
    assert rijen["ADM-007"] == ("analyseset", "")


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
        "gemengd_zonder_overstort",
        "putten",
        "strengen",
        "vlakken",
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


def test_persleiding_met_bob_krijgt_geen_vrijvervalrichting(tmp_path: Path) -> None:
    """Issue #74: een gepompte leiding draagt geen betrouwbare vrijverval-BOB.

    Beide strengen in de fixture dragen hetzelfde verval (8,00 naar 7,50, dalend langs
    de getekende lijn). De vrijvervalstreng hoort daar `mee` van te krijgen; de
    persleiding hoort grijs te blijven, want een pijl zou daar een fysiek onjuiste
    stroomrichting tekenen.

    Alleen de pijl vervalt. `bob_verval_m` is een gemeten waarde en geen bewering over
    de stroomrichting, dus die blijft op de persleiding gewoon staan -- anders was zij
    niet meer te onderscheiden van een mechanische leiding zonder BOB.
    """
    pad = _schrijf(_run("richting_persleiding_met_bob.ttl"), tmp_path)

    strengen = {
        label: (richting, verval)
        for label, richting, verval in _rijen(
            pad, "select label, richting_bob, bob_verval_m from strengen"
        )
    }

    assert strengen["1"] == ("mee", pytest.approx(0.50))
    assert strengen["p"] == ("onbekend", pytest.approx(0.50))


def test_popup_van_een_persleiding_noemt_waarom_er_geen_richting_staat(tmp_path: Path) -> None:
    """Grijs zonder reden leest als "niet te bepalen"; hier is het een eigenschap van
    de leiding, en de popup hoort dat te zeggen.

    De regel spreekt van "mechanische leiding" en niet van "persleiding": de rol dekt
    zes klassen, en op een Vacuumleiding zou "persleiding" de objecttyperegel erboven
    tegenspreken.
    """
    pad = _schrijf(_run("richting_persleiding_met_bob.ttl"), tmp_path)

    popups = dict(_rijen(pad, "select label, popup_html from strengen"))

    assert "mechanische leiding — geen vrijvervalrichting" in popups["p"]
    assert "BOB-richting niet te bepalen" not in popups["p"]
    assert "BOB-verval loopt met de getekende lijn mee" in popups["1"]


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
def test_vlakkenlaag_is_exact_de_verzameling_uit_de_meldingen(tmp_path: Path) -> None:
    """De kerntest: niets erbij, niets eraf. Eén laag voor EXT-001, EXT-002 en EXT-003."""
    run = _ext_run()
    meldingen = bouw_meldingen(run, RUNDATUM)
    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verwacht = {
        m.object2_uri
        for m in meldingen
        if m.check_id in ("EXT-001", "EXT-002", "EXT-003") and m.object2_uri
    }

    assert {rij["id"] for rij in _laagrijen(pad, "vlakken")} == verwacht


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_pandvlak_wordt_ontdubbeld_met_de_sterkste_relatie(tmp_path: Path) -> None:
    """Vier objecten raken hetzelfde pand: één rij, vier meldingen, binnen wint."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    panden = [rij for rij in _laagrijen(pad, "vlakken") if rij["soort"] == "pand"]

    assert len(panden) == 1
    assert panden[0]["id"] == "bgt:pand/pand-1"
    assert panden[0]["soort"] == "pand"
    assert panden[0]["bron"] == "bgt_pand"
    assert panden[0]["bronbestand"] == "bgt.gpkg"
    assert panden[0]["label"] == "pand pand-1"
    assert panden[0]["relatie"] == "binnen"
    assert panden[0]["afstand_min_m"] == 0.0
    assert panden[0]["aantal_meldingen"] == 4
    assert panden[0]["check_ids"] == "EXT-001"


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_watervlak_draagt_beide_checks_en_ook_de_ext002_zinker(tmp_path: Path) -> None:
    """Water valt niet meer weg: EXT-002 registreert nu zijn treffer (issue #67).

    Water-1/5/7 worden door zowel EXT-002 als EXT-003 gemeld en dragen beide ID's;
    water-2 wordt door streng 3 (een duiker) doorkruist -- EXT-003 slaat dat over, maar
    EXT-002 niet -- en krijgt daardoor toch een vlak, met alleen EXT-002.
    """
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    water = {rij["id"]: rij for rij in _laagrijen(pad, "vlakken") if rij["soort"] == "water"}

    assert set(water) == {
        "bgt:waterdeel/water-1",
        "bgt:waterdeel/water-2",
        "bgt:waterdeel/water-5",
        "bgt:waterdeel/water-7",
    }
    assert water["bgt:waterdeel/water-1"]["check_ids"] == "EXT-002, EXT-003"
    assert water["bgt:waterdeel/water-2"]["check_ids"] == "EXT-002"
    # Water draagt geen relatie of afstand -- die gelden alleen voor pand en bouwwerk.
    assert water["bgt:waterdeel/water-1"]["relatie"] == ""
    assert water["bgt:waterdeel/water-1"]["afstand_min_m"] is None


def test_lege_vlakkenlaag_bestaat_en_is_geregistreerd(tmp_path: Path) -> None:
    """Een run zonder EXT-treffers heeft de laag `vlakken`, leeg, met stijl en registratie."""
    pad = _schrijf(_run("schoon.ttl"), tmp_path)

    assert _rijen(pad, 'select count(*) from "vlakken"')[0][0] == 0
    geregistreerd = _rijen(pad, "select count(*) from gpkg_contents where table_name = 'vlakken'")
    gestyled = _rijen(pad, "select count(*) from layer_styles where f_table_name = 'vlakken'")
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
    rijen = _laagrijen(pad, "vlakken")

    assert [rij["id"] for rij in rijen] == ["bgt:pand/p-nabij"]
    assert rijen[0]["soort"] == "pand"
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
    rijen = _laagrijen(pad, "vlakken")

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
def test_runmetadata_telt_de_vlakkenlaag_mee(tmp_path: Path) -> None:
    """Het aantal vlakken hoort ook in gwsw_run te staan, net als de andere lagen."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    (aantal,) = _rijen(pad, "select n_vlakken from gwsw_run")[0]

    # Vijf vlakken: één pand, drie waterdelen die EXT-003 meldt (water-1/5/7) plus water-2
    # dat alleen EXT-002 ziet, dat sinds issue #67 ook een treffer registreert.
    assert aantal == 5
    assert aantal == len(_laagrijen(pad, "vlakken"))


@pytest.mark.skipif(
    not (GIS_DIR / "ext" / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
def test_watervlak_subtype_noemt_type_en_label_de_identificatie(tmp_path: Path) -> None:
    """`subtype` is om op te filteren, `label` is om iets in terug te vinden."""
    run = _ext_run()
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rij = next(r for r in _laagrijen(pad, "vlakken") if r["id"] == "bgt:waterdeel/water-1")

    assert rij["soort"] == "water"
    assert rij["subtype"] == "waterloop"
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


def test_de_stelsellaag_bestaat_niet_meer(tmp_path: Path) -> None:
    """Issue #75: de laag groepeerde strengen via de GWSW-stelselregistratie.

    Die groepering is niet betrouwbaar, en de wel/geen-afvoerroute die zij toonde is
    een netwerk-eigenschap. De laag is daarom weg; de `stelsel`-kolom op `putten` en
    `strengen` blijft (dat is een labeling, geen vlak).
    """
    pad = _schrijf(_run("stelsels_registratie.ttl"), tmp_path)

    contents = {naam for (naam,) in _rijen(pad, "select table_name from gpkg_contents")}
    assert "stelsels" not in contents
    kolommen = {rij[1] for rij in _rijen(pad, "pragma table_info(strengen)")}
    assert "stelsel" in kolommen


def test_gemengd_zonder_overstort_is_een_multipolygon_in_gpkg_contents(tmp_path: Path) -> None:
    """De nieuwe vlakkenlaag staat geregistreerd, anders vindt QGIS haar niet."""
    pad = _schrijf(_run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006"), tmp_path)

    ((soort,),) = _rijen(
        pad,
        "select geometry_type_name from gpkg_geometry_columns "
        "where table_name = 'gemengd_zonder_overstort'",
    )
    assert soort == "MULTIPOLYGON"
    contents = {naam for (naam,) in _rijen(pad, "select table_name from gpkg_contents")}
    assert "gemengd_zonder_overstort" in contents


def test_gemengd_zonder_overstort_geeft_een_vlak_per_deelstelsel(tmp_path: Path) -> None:
    """De twee RVZ-006-bevindingen van hetzelfde deel leveren samen een vlak op.

    Het vlak omvat de hele component (drie knopen, twee strengen van 50 m) en telt de
    meldingen die erop landden.
    """
    pad = _schrijf(_run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006"), tmp_path)

    rijen = _rijen(
        pad,
        "select cluster_id, n_knopen, n_strengen, strenglengte_m, n_meldingen "
        "from gemengd_zonder_overstort",
    )

    assert len(rijen) == 1
    cluster, n_knopen, n_strengen, lengte, n_meldingen = rijen[0]
    assert cluster.startswith("ds-")
    assert (n_knopen, n_strengen, lengte, n_meldingen) == (3, 2, 100.0, 2)


def test_gemengd_zonder_overstort_draagt_een_leesbaar_vlak(tmp_path: Path) -> None:
    """De geometrie is een leesbare MULTIPOLYGON om de strengen van de component."""
    from shapely import wkb

    pad = _schrijf(_run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006"), tmp_path)

    ((blob,),) = _rijen(pad, "select geom from gemengd_zonder_overstort")
    vorm = wkb.loads(bytes(blob)[8:])  # de GPKG-kop (magic, versie, vlaggen, srs) overslaan
    assert vorm.geom_type == "MultiPolygon"
    assert not vorm.is_empty
    # Twee strengen van 50 m met 10 m buffer: een lint van ruim 100 x 20 m.
    assert vorm.bounds == pytest.approx((990.0, 1990.0, 1110.0, 2010.0), abs=0.5)


def test_gemengd_vlak_zwijgt_niet_over_systemisch_genoemde_meldingen(tmp_path: Path) -> None:
    """Een vlak in deze laag is per constructie een gebrek (BO-59).

    Zou het zijn status en zijn popup uit de systemisch-gefilterde meldingen afleiden,
    dan kreeg het "geen eigen gebrek" te lezen zodra RVZ-006 op een klein gebied de
    populatieratio haalt -- terwijl de rij alleen bestaat omdat die check aansloeg.
    De fixture meldt op beide gemengde strengen (2 van 2), dus de vlag staat aan.
    """
    run = _run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006")
    meldingen = bouw_meldingen(run, RUNDATUM)
    rvz = [melding for melding in meldingen if melding.check_id == "RVZ-006"]
    assert rvz and all(melding.systemisch for melding in rvz)

    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    ((popup,),) = _rijen(pad, "select popup_html from gemengd_zonder_overstort")
    assert "RVZ-006" in popup
    assert "s-rood" in popup
    assert "geen eigen gebrek" not in popup


def test_gemengd_zonder_overstort_blijft_leeg_zonder_bevinding(tmp_path: Path) -> None:
    """Zonder RVZ-006-melding blijft de laag leeg; ze volgt de uitslag, niet de graaf."""
    pad = _schrijf(_run("rvz_schoon.ttl", "RVZ-006"), tmp_path)

    assert _rijen(pad, "select count(*) from gemengd_zonder_overstort") == [(0,)]


def test_runmetadata_telt_de_gemengde_deelstelsels(tmp_path: Path) -> None:
    """`n_gemengd_zonder_overstort` maakt expliciet hoeveel vlakken er geschreven zijn."""
    pad = _schrijf(_run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006"), tmp_path)

    rij = _rijen(pad, "select n_gemengd_zonder_overstort, n_gemengd_zonder_vlak from gwsw_run")

    assert rij == [(1, 0)]


def test_gemengd_deelstelsel_zonder_geometrie_wordt_geteld(tmp_path: Path) -> None:
    """Een deelstelsel dat niet te tekenen is, verdwijnt niet stilzwijgend.

    De fixture meldt RVZ-006 op een gemengde streng zonder bruikbare lijn: er valt geen
    vlak omheen te tekenen, maar "dit deelstelsel bestaat niet" en "we konden het niet
    tekenen" horen in het bestand uit elkaar te houden zijn. De laag blijft leeg en
    `n_gemengd_zonder_vlak` telt het geval.
    """
    run = _run("rvz006_gemengd_zonder_geometrie.ttl", "RVZ-006")
    assert run.count(Severity.ERROR) == 1  # de melding is er wel

    pad = _schrijf(run, tmp_path)

    assert _rijen(pad, "select count(*) from gemengd_zonder_overstort") == [(0,)]
    rij = _rijen(pad, "select n_gemengd_zonder_overstort, n_gemengd_zonder_vlak from gwsw_run")
    assert rij == [(0, 1)]


def test_onbekend_deelstelsel_id_faalt_luid(tmp_path: Path) -> None:
    """Een `cluster_id` die de graaf niet kent is een interne tegenspraak, geen datageval.

    De check en deze schrijver lezen dezelfde `deelstelsel_ids` van dezelfde context, dus
    zo'n ID kan alleen ontstaan als die afspraak breekt. De laag zou dan stil kleiner zijn
    dan de uitslag -- precies wat `_vul_trefferlaag` bij de trefferlaag afvangt.
    """
    run = _run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006")
    meldingen = [
        replace(melding, cluster_id="ds-bestaat-niet") if melding.check_id == "RVZ-006" else melding
        for melding in bouw_meldingen(run, RUNDATUM)
    ]

    with pytest.raises(PipelineError, match="ds-bestaat-niet"):
        schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)


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


def test_gwsw_run_draagt_ook_de_onderdrukte_checks(tmp_path: Path) -> None:
    """De tweede lijst loopt door dezelfde stroom; hier vallen beide soorten weg."""
    uitvoer = schrijf_uitvoer(
        _run_onderdrukt(["MechanischeTransportleiding"], ["TOP-011"]),
        tmp_path,
        RUNDATUM,
        met_json=False,
    )

    assert uitvoer.geopackage is not None
    # TOP-011 op de vrijvervalstreng valt op check weg, de nulmelding op de persleiding
    # op klasse: samen twee.
    assert _rijen(
        uitvoer.geopackage,
        "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run",
    ) == [("MechanischeTransportleiding", "TOP-011", 2)]


def test_een_klasse_zonder_objecten_onderdrukt_niets_maar_wordt_wel_verantwoord(
    tmp_path: Path,
) -> None:
    """Actief met nul weggevallen meldingen: de keuze staat er, de uitslag is nul.

    De fixture kent geen enkel `Rioolgemaal`. Alle drie de uitvoervormen die de telling
    dragen horen dan hetzelfde te zeggen; zwijgen zou de keuze onzichtbaar maken.
    """
    uitvoer = schrijf_uitvoer(_run_onderdrukt(["Rioolgemaal"]), tmp_path, RUNDATUM)

    assert uitvoer.geopackage is not None and uitvoer.json is not None
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    assert "**0 meldingen onderdrukt**" in uitvoer.markdown.read_text(encoding="utf-8")
    assert document["onderdrukt"] == {"klassen": ["Rioolgemaal"], "checks": [], "meldingen": 0}
    assert _rijen(
        uitvoer.geopackage,
        "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run",
    ) == [("Rioolgemaal", "", 0)]


def test_de_grijze_objecten_en_de_telling_komen_uit_dezelfde_onderdrukking(
    tmp_path: Path,
) -> None:
    """Eén bron voor beide, en dat is het argument -- niet de config van de run.

    Zou de laag de klassenlijst uit `run.config` lezen, dan levert een beller die de
    stroom zelf samenstelt een bestand op waarin objecten grijs staan met een reden die
    `gwsw_run` niet noemt.
    """
    run = _run_onderdrukt(["MechanischeTransportleiding"])
    stroom = bouw_meldingenstroom(run, RUNDATUM)

    zonder = schrijf_geopackage(run, stroom.meldingen, tmp_path / "zonder", RUNDATUM)
    met = schrijf_geopackage(
        run, stroom.meldingen, tmp_path / "met", RUNDATUM, onderdrukking=stroom.onderdrukking
    )

    kolommen = "select onderdruk_klassen, onderdruk_checks, meldingen_onderdrukt from gwsw_run"
    popups_zonder = {rij["feature_id"]: rij["popup_html"] for rij in _laagrijen(zonder, "strengen")}
    popups_met = {rij["feature_id"]: rij["popup_html"] for rij in _laagrijen(met, "strengen")}

    assert _rijen(zonder, kolommen) == [("", "", 0)]
    assert all(REDEN_ONDERDRUKT not in popup for popup in popups_zonder.values())
    assert _rijen(met, kolommen) == [("MechanischeTransportleiding", "", 1)]
    assert REDEN_ONDERDRUKT in popups_met["L2"]
