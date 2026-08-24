"""Integratietests op de echte De Wolden en Hoogeveen-bestanden."""

from __future__ import annotations

import csv
import logging
import sqlite3
import time
from datetime import date
from pathlib import Path

import pytest

from gpkghelper import schrijf_buurten, schrijf_buurtenraster
from nlriochecker.afbakening import bouw_analyseset
from nlriochecker.analysis import analyze
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import REGISTRY, CheckContext, run_checks
from nlriochecker.config import load_coverage_config
from nlriochecker.coverage import Verdict, assess_coverage
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import Meetbereik, laad_nulmeting
from nlriochecker.reporting import write_check_report, write_reports
from nlriochecker.studiegebied import load_studiegebieden, load_study_area
from nlriochecker.toetsloop import toets_gebieden
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer_gebieden

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SHACL_DIR = DATA_DIR / "shacl_nulmeting"
OROX_DIR = DATA_DIR / "gwsw_orox_ttl"
ONTOLOGIE_DIR = DATA_DIR / "gwsw_ontologieen"
GIS_DIR = DATA_DIR / "gis_koekangerveld"

OROX_DEWOLDENHOOGEVEEN = OROX_DIR / "dewoldenhoogeveen_orox.ttl"
VOORBEELD_TTL = OROX_DIR / "GwswDataset__Voorbeeld_v1_6_orox.ttl"
ONTOLOGIE_TTL = ONTOLOGIE_DIR / "Ontologie_GWSW_Mds.ttl"
ONTOLOGIE_TOTAAL = ONTOLOGIE_DIR / "Ontologie_GWSW_Totaal.ttl"
STUDIEGEBIED = GIS_DIR / "cbs_buurt_koekangerveld_studiegebied.gpkg"

SHACL_PADEN = sorted(SHACL_DIR.glob("*.csv"))
RUNDATUM = date(2026, 8, 18)

pytestmark = pytest.mark.integratie


@pytest.fixture(scope="module")
def meting():
    """De volledige SHACL-nulmeting van De Wolden en Hoogeveen."""
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
    # Geen enkele geschrapte check mag ongeraakt blijven; zie test_coverage.py.
    assert result.untouched == []


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
    not (OROX_DEWOLDENHOOGEVEEN.exists() and ONTOLOGIE_TOTAAL.exists()),
    reason="de De Wolden en Hoogeveen-OroX staat niet in data/",
)
def test_checks_op_dewoldenhoogeveen_met_typeringspoort(meting, tmp_path: Path) -> None:
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
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
    not (OROX_DEWOLDENHOOGEVEEN.exists() and ONTOLOGIE_TOTAAL.exists()),
    reason="de De Wolden en Hoogeveen-OroX staat niet in data/",
)
def test_attr014_op_dewoldenhoogeveen_meldt_alleen_wibonthema() -> None:
    """ATTR-014 vindt precies een property-tegenspraak op De Wolden en Hoogeveen: WIBONThema.

    De verificatie-eis uit issue #37: meer dan een melding zou betekenen dat de check
    te breed staat. De aantallen (23.440 objecten, 18.363 met de vulwaarde 0) komen
    rechtstreeks uit de audit in het issue.
    """
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["ATTR-014"]).outcomes[0]

    assert len(outcome.findings) == 1
    bevinding = outcome.findings[0]
    assert bevinding.details["kenmerk"] == "WIBONThema"
    assert bevinding.systemisch is True
    assert bevinding.message == (
        "WIBONThema gebruikt hasValue in plaats van hasReference op 23440 objecten, "
        "waarvan 18363 met de vulwaarde 0."
    )


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and ONTOLOGIE_TOTAAL.exists()),
    reason="de De Wolden en Hoogeveen-OroX staat niet in data/",
)
def test_attr017_op_dewoldenhoogeveen_meldt_de_pe_leidingen() -> None:
    """ATTR-017 meldt de 962 PE-leidingen die de betonwaarde 30 (3,0 mm) dragen.

    De verificatie-eis uit issue #38: de schaal 1:10 volgt uit de data (23.440
    leidingen dragen alle een wandruwheid), en dan valt precies de PE-groep buiten zijn
    band -- beton (30), pvc (4) en gres (5) passen wel. Loopt het aantal op naar
    duizenden, dan is de schaallezing misgegaan. De 49 Polypropyleen-leidingen en de
    1.362 zonder materiaal blijven ongetoetst en staan in de toelichting.
    """
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["ATTR-017"]).outcomes[0]

    assert len(outcome.findings) == 962
    assert {finding.details["materiaal"] for finding in outcome.findings} == {"PE"}
    assert all(finding.details["schaal"] == 10 for finding in outcome.findings)
    assert any("schaal 1:10" in note for note in outcome.notes), outcome.notes
    assert any("Polypropyleen" in note for note in outcome.notes), outcome.notes


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of het studiegebied staat niet in data/",
)
def test_studiegebied_koekangerveld(tmp_path: Path) -> None:
    """De afbakening moet aanzienlijk minder bevindingen opleveren, en dat melden."""
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
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


AHN_TIF = GIS_DIR / "ahn5_dtm_koekangerveld.tif"


def _koekangerveld_bronnen():
    """Leest de echte externe bronnen uit data/gis_koekangerveld."""
    from nlriochecker.externedata import load_external_data

    basis = load_check_config().bronnen
    return load_external_data(basis.model_copy(update={"map": "."}), GIS_DIR)


@pytest.mark.skipif(
    not AHN_TIF.exists(), reason="de externe bronnen staan niet in data/gis_koekangerveld/"
)
def test_externe_bronnen_van_koekangerveld() -> None:
    """Legt de inventarisatie uit docs/gis-inventarisatie.md vast."""
    bronnen = _koekangerveld_bronnen()

    assert bronnen.extent is not None
    assert bronnen.extent.area / 10_000 == pytest.approx(43.2, abs=0.5)
    assert {rol: len(laag) for rol, laag in bronnen.layers.items()} == {
        "bgt_pand": 199,
        # Alleen `waterdeel`; `ondersteunendwaterdeel` (94 oevers) valt buiten scope.
        "bgt_water": 233,
        "bgt_bouwwerk": 52,
        "bag_pand": 166,
        "nwb_wegvak": 13,
    }
    # De BGT-laag `put` bestaat wel maar is leeg; EXT-005 en EXT-006 worden daarom
    # overgeslagen in plaats van elke put als dekselloos te melden.
    assert bronnen.layer("bgt_putdeksel") is None
    assert any("bgt_putdeksel" in ontbreekt for ontbreekt in bronnen.missing)
    # Alles staat al in RD New; er is niets geherprojecteerd.
    assert all(laag.reprojected_from is None for laag in bronnen.layers.values())
    assert bronnen.raster is not None
    assert bronnen.raster.crs == "EPSG:28992"


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and AHN_TIF.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of de externe bronnen staan niet in data/",
)
def test_ext_checks_op_koekangerveld(tmp_path: Path) -> None:
    """De EXT- en AHN-checks draaien op de Koekangerveld-uitsnede.

    De GWSW-dataset beslaat de hele gemeente en de bronnen alleen deze kern; het
    overgrote deel van de objecten hoort daarom de status *buiten studiegebied* te
    krijgen en geen uitslag.
    """
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    context = CheckContext(
        dataset=dataset, config=load_check_config(), bronnen=_koekangerveld_bronnen()
    )
    ids = ["EXT-001", "EXT-002", "EXT-003", "EXT-007", "HGT-001", "HGT-002", "HGT-003"]
    run = run_checks(context, ids)
    per_check = {outcome.check_id: outcome for outcome in run.outcomes}

    # Maar een fractie van de dataset ligt binnen het studiegebied.
    # 69 = 29 vrijvervalstrengen plus 40 putten binnen het bereik van de externe
    # bronnen; EXT-001 toetst sinds deze uitbreiding beide soorten objecten.
    assert per_check["EXT-001"].examined == 69
    assert per_check["HGT-001"].examined == 40
    for outcome in run.outcomes:
        if outcome.check_id.startswith("HGT") or outcome.check_id in {"EXT-001", "EXT-002"}:
            assert any("Buiten studiegebied" in note for note in outcome.notes)

    # Geen enkele put wijkt meer dan 25 cm van het AHN5 af, 15 wel meer dan 5 cm.
    assert len(per_check["HGT-002"].findings) == 0
    assert len(per_check["HGT-001"].findings) == 15

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")
    assert "Buiten studiegebied" in tekst


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of het studiegebied staat niet in data/",
)
def test_afbakening_op_koekangerveld_verandert_de_bevindingen_niet() -> None:
    """De contextschil mag de uitkomst op de kern niet veranderen, alleen sneller maken."""
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    config = load_check_config()
    area = load_study_area(STUDIEGEBIED)
    ids = ["NET-001", "NET-002", "NET-004", "TOP-001", "TOP-005"]

    volledig = run_checks(CheckContext(dataset=dataset, config=config), ids)
    volledig = volledig.beperk_tot_studiegebied(area)

    analyseset = bouw_analyseset(dataset, area, config)
    afgebakend = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config, analyseset=analyseset), ids
    )
    afgebakend = afgebakend.beperk_tot_studiegebied(area)

    def sleutel(run):
        return sorted((finding.check_id, finding.object_uri) for finding in run.findings)

    assert sleutel(afgebakend) == sleutel(volledig)
    assert len(analyseset.alles) < len(dataset.nodes) + len(dataset.conduits)


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of het studiegebied staat niet in data/",
)
def test_twee_buurten_op_dewoldenhoogeveen(tmp_path: Path) -> None:
    """Rapportage per gebied op de echte data, met de equivalentie-eis erbij.

    Het gebiedsbestand wordt uit de Koekangerveld-buurt afgeleid: de westelijke en
    de oostelijke helft, elk als eigen feature. Per helft moeten de meldingen
    gelijk zijn aan die van een losse run op alleen die helft.
    """
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    config = load_check_config()
    ids = ["NET-001", "TOP-001", "TOP-005"]
    west, oost = _helften(load_study_area(STUDIEGEBIED).geometry)

    samen = schrijf_buurten(tmp_path / "twee.gpkg", [("West", west), ("Oost", oost)])
    los = schrijf_buurten(tmp_path / "west.gpkg", [("West", west)])

    beide = toets_gebieden(
        dataset,
        load_studiegebieden(samen),
        config,
        check_ids=ids,
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    alleen = toets_gebieden(
        dataset,
        load_studiegebieden(los),
        config,
        check_ids=ids,
        meetbereik=Meetbereik.niet_gemeten(()),
    )

    uitvoer = schrijf_uitvoer_gebieden(beide, tmp_path / "uit", RUNDATUM)

    def sleutel(gebiedsrun):
        return sorted((f.check_id, f.object_uri) for f in gebiedsrun.run.findings)

    assert [run.naam for run in beide] == ["West", "Oost"]
    assert sleutel(beide[0]) == sleutel(alleen[0])
    assert (tmp_path / "uit" / "west" / "bevindingen.md").exists()
    assert (tmp_path / "uit" / "oost" / "bevindingen.md").exists()
    assert uitvoer.synthese is not None and uitvoer.synthese.exists()


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of het studiegebied staat niet in data/",
)
def test_schaal_tachtig_buurten(tmp_path: Path) -> None:
    """De referentiecasus telt 80+ buurten; die run moet doorlopen.

    Geen tijdslimiet in de test -- die zou op een trage machine willekeurig falen --
    maar de duur wordt wel gelogd, zodat de meting op deze casus mogelijk blijft.
    Dat is de meting waarop het uitstel van de lokaal/contextueel-optimalisatie
    wacht (zie de beslislog).
    """
    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    bestand = schrijf_buurtenraster(
        tmp_path / "tachtig.gpkg", 80, load_study_area(STUDIEGEBIED).geometry.bounds
    )
    gebieden = load_studiegebieden(bestand)

    begin = time.monotonic()
    runs = toets_gebieden(
        dataset,
        gebieden,
        load_check_config(),
        check_ids=["TOP-001"],
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    uitvoer = schrijf_uitvoer_gebieden(
        runs, tmp_path / "uit", RUNDATUM, met_geopackage=False, beschikbaar=gebieden.beschikbaar
    )
    duur = time.monotonic() - begin
    logging.getLogger(__name__).warning("80 buurten in %.1f s", duur)

    assert len(runs) == 80
    assert len(uitvoer.per_gebied) == 80
    assert sorted(pad.name for pad in (tmp_path / "uit").iterdir())[:2] == [
        "buurt_001",
        "buurt_002",
    ]
    assert uitvoer.synthese is not None and uitvoer.synthese.exists()


def _helften(vlak):
    """Splitst een vlak in een westelijke en een oostelijke helft."""
    from shapely.geometry import box

    x_min, y_min, x_max, y_max = vlak.bounds
    midden = (x_min + x_max) / 2
    return (
        vlak.intersection(box(x_min, y_min, midden, y_max)),
        vlak.intersection(box(midden, y_min, x_max, y_max)),
    )


@pytest.mark.zwaar
@pytest.mark.skipif(
    not (OROX_DEWOLDENHOOGEVEEN.exists() and AHN_TIF.exists() and STUDIEGEBIED.exists()),
    reason="de De Wolden en Hoogeveen-OroX of de externe bronnen staan niet in data/",
)
def test_ext_lagen_op_dewoldenhoogeveen(tmp_path: Path) -> None:
    """De lagen in de GeoPackage zijn exact de treffers uit de meldingen.

    Op de echte BGT- en BAG-bronnen, met het studiegebied Koekangerveld als bereik.
    De dekkingspoort krijgt hier geen eis mee: deze extracten komen tot 276 m tekort
    doordat hun randen leeg zijn, en dat is een projectkeuze (`dekking_tolerantie_m`)
    en geen eigenschap van deze test.
    """
    from nlriochecker.uitvoer.gpkg import schrijf_geopackage
    from nlriochecker.uitvoer.melding import bouw_meldingen

    dataset = load_dataset(OROX_DEWOLDENHOOGEVEEN, [ONTOLOGIE_TOTAAL])
    context = CheckContext(
        dataset=dataset, config=load_check_config(), bronnen=_koekangerveld_bronnen()
    )
    run = run_checks(context, ["EXT-001", "EXT-002", "EXT-003"])
    meldingen = bouw_meldingen(run, RUNDATUM)

    pad = schrijf_geopackage(run, meldingen, tmp_path, RUNDATUM)

    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        geschreven = {
            laag: {rij[0] for rij in verbinding.execute(f'select id from "{laag}"')}
            for laag in ("bouwwerken", "waterdelen_zonder_zinker")
        }
    finally:
        verbinding.close()

    for laag, check_id in (("bouwwerken", "EXT-001"), ("waterdelen_zonder_zinker", "EXT-003")):
        verwacht = {m.object2_uri for m in meldingen if m.check_id == check_id and m.object2_uri}
        assert geschreven[laag] == verwacht
        assert all(sleutel.startswith(("bgt:", "bag:")) for sleutel in geschreven[laag])
    assert geschreven["bouwwerken"]
