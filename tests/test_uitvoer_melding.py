"""Tests voor de meldingenstroom waar Markdown, CSV en GeoPackage uit lezen."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

from gwsw_orox_helpers.dataset import load_dataset

from helpers_melding import nulbevinding
from nlriochecker.checkconfig import CheckConfig, Uitzondering, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.studiegebied import load_study_area
from nlriochecker.uitvoer.identiteit import melding_id
from nlriochecker.uitvoer.melding import (
    BRON_DATASET,
    BRON_NULMETING,
    GEEN_ONDERDRUKKING,
    GEEN_UITZONDERINGEN,
    Melding,
    _is_systemisch,
    bouw_meldingen,
    bouw_meldingenstroom,
)

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
    dataset = load_dataset(TTL_DIR / bestand, [])
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

    # De datasetsignalen (bron "dataset") zijn niet aan een gebied gebonden; het
    # scope-en-gebied-contract geldt de gelokaliseerde meldingen.
    gelokaliseerd = [melding for melding in meldingen if melding.bron != "dataset"]
    assert gelokaliseerd
    assert all(melding.scope == "binnen_studiegebied" for melding in gelokaliseerd)
    assert all(melding.gebied == "rond_de_fixture" for melding in gelokaliseerd)


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


def test_melding_draagt_zowel_fragment_als_uri() -> None:
    run = _run("top005_dubbele_put.ttl", "TOP-005")

    melding = bouw_meldingen(run, RUNDATUM)[0]

    assert melding.object_uri.endswith(f"#{melding.object_id}")
    assert "#" not in melding.object_id


def test_de_melding_id_blijft_over_de_volledige_uri_gehasht() -> None:
    """De ID's moeten vergelijkbaar blijven met die van eerdere runs."""
    run = _run("top005_dubbele_put.ttl", "TOP-005")

    melding = bouw_meldingen(run, RUNDATUM)[0]

    assert melding.melding_id == melding_id(
        melding.check_id, melding.object_uri, melding.object2_uri, {}
    )


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


# Issue #122: het feitenkanaal naast de meldingenstroom. Een check declareert met
# `feit_sleutels` welke detailsleutels de uitvoer mag lezen; ze reizen in een zijmap
# `melding_id -> feiten` en niet in een veld op `Melding` -- dat zou reflectief in de
# bevroren JSON-envelop landen.
AANWIJZINGEN_KOP = "Aanwijzingen: "
AANWIJZING_SCHEIDING = "; "


def test_de_zijmap_draagt_de_gedeclareerde_feiten_van_rvz006() -> None:
    """Elke RVZ-006-melding krijgt haar twee aanwijzingen als eigen rij in de zijmap.

    De waarden zijn per constructie hetzelfde als wat de boodschap achter
    `Aanwijzingen: ` draagt -- de GeoPackage parseerde die zin tot issue #122 terug om er
    weer twee feiten uit te winnen. Deze test legt de gelijkheid vast, zodat de popup en
    de zin niet uit elkaar kunnen lopen.
    """
    stroom = bouw_meldingenstroom(_run("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006"), RUNDATUM)

    rvz = [melding for melding in stroom.meldingen if melding.check_id == "RVZ-006"]
    assert rvz
    for melding in rvz:
        staart = melding.boodschap.partition(AANWIJZINGEN_KOP)[2].rstrip(".")
        aandeel, _, overige = staart.partition(AANWIJZING_SCHEIDING)
        assert stroom.feiten[melding.melding_id] == {
            "aandeel_gemengd": aandeel,
            "overige_aanwijzingen": overige,
        }


def test_een_check_zonder_feit_sleutels_laat_geen_rij_in_de_zijmap_achter() -> None:
    """Geen algemeen doorgeefluik: alleen wat een check declareert reist mee.

    TOP-001 declareert niets, dus zijn `details` blijven waar ze zijn -- net zoals
    `id_sleutels` alleen doorlaat wat de check benoemt.
    """
    stroom = bouw_meldingenstroom(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert stroom.meldingen
    assert stroom.feiten == {}


def _run_rvz006_onderdrukt(klassen: Sequence[str] = (), checks: Sequence[str] = ()) -> CheckRun:
    """RVZ-006 op de gemengde fixture, met de twee lijsten uit `[rapport]` gezet."""
    config = _config()
    config.rapport.onderdruk_klassen = list(klassen)
    config.rapport.onderdruk_checks = list(checks)
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl", [])
    return run_checks(CheckContext(dataset=dataset, config=config), ["RVZ-006"])


def test_wat_onderdrukt_wordt_laat_ook_geen_feit_achter() -> None:
    """De zijmap blijft gelijk aan de lijst: wat `[rapport]` wegliet bereikt niemand.

    Zowel op check-ID als op de klasse van het hoofdobject (BO-49). Zou de map de
    weggevallen meldingen houden, dan droeg zij feiten waar geen melding meer bij hoort.
    """
    ongefilterd = bouw_meldingenstroom(_run_rvz006_onderdrukt(), RUNDATUM)
    assert ongefilterd.feiten

    op_check = bouw_meldingenstroom(_run_rvz006_onderdrukt(checks=["RVZ-006"]), RUNDATUM)
    op_klasse = bouw_meldingenstroom(_run_rvz006_onderdrukt(klassen=["Leiding"]), RUNDATUM)

    assert op_check.onderdrukking.per_check == {"RVZ-006": len(ongefilterd.feiten)}
    assert op_klasse.onderdrukking.per_klasse == {"Leiding": len(ongefilterd.feiten)}
    assert op_check.feiten == {}
    assert op_klasse.feiten == {}


def test_check_boven_de_drempel_heet_systemisch() -> None:
    """De drempel is configureerbaar; hier verlaagd om het gedrag te tonen.

    NET-001 slaat op de fixture op 1 van de 3 strengen aan. Met de standaarddrempel
    van 80% is dat geen systemische melding, met 10% wel. De minimumpopulatie van
    BO-59 staat hier op 1: drie bekeken strengen halen de productiewaarde nooit, en
    dan valt er geen ratio te tonen.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl", [])
    config = _config()
    config.rapport.systemisch_drempel = 0.1
    config.rapport.systemisch_minimum_bekeken = 1
    context = CheckContext(dataset=dataset, config=config)
    run = run_checks(context, ["NET-001"])

    meldingen = bouw_meldingen(run, RUNDATUM)

    assert meldingen
    assert all(melding.systemisch for melding in meldingen)


def test_een_te_kleine_populatie_is_nooit_systemisch() -> None:
    """Onder de minimumpopulatie zegt de ratio niets (BO-59).

    NET-001 slaat op deze fixture op 1 van de 3 strengen aan. Met de drempel op 10%
    haalt die ratio de grens ruim, maar drie bekeken objecten dragen geen uitspraak
    over de export als geheel; zo'n check hoort gewoon per object gemeld te worden.
    Pas vanaf `systemisch_minimum_bekeken` telt de ratio mee.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl", [])
    config = _config()
    config.rapport.systemisch_drempel = 0.1
    run = run_checks(CheckContext(dataset=dataset, config=config), ["NET-001"])
    assert run.outcomes[0].examined < config.rapport.systemisch_minimum_bekeken

    assert all(not melding.systemisch for melding in bouw_meldingen(run, RUNDATUM))

    config.rapport.systemisch_minimum_bekeken = 1
    assert all(melding.systemisch for melding in bouw_meldingen(run, RUNDATUM))


def test_systemisch_hangt_niet_af_van_de_afbakening() -> None:
    """De vlag telt de bevindingen van de hele dataset tegen de hele populatie.

    Na afbakening tot een studiegebied blijft `examined` datasetbreed terwijl de
    bevindingen tot het gebied beperkt zijn. Zou de teller meebewegen, dan zou
    "systemisch" iets anders betekenen naargelang er een gebied is opgegeven -- en
    daar hangen zowel de kaartstijl als de tellingen op de featurelagen aan.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl", [])
    config = _config()
    config.rapport.systemisch_drempel = 0.1
    config.rapport.systemisch_minimum_bekeken = 1
    run = run_checks(CheckContext(dataset=dataset, config=config), ["NET-001"])
    assert all(melding.systemisch for melding in bouw_meldingen(run, RUNDATUM))

    gebied = load_study_area(GIS_DIR / "rond_put_ab.geojson")
    beperkt = run.beperk_tot_studiegebied(gebied)
    assert beperkt.findings == []

    # Nul bevindingen binnen het gebied, maar het meldingtype blijft systemisch voor
    # de dataset als geheel; er is alleen niets meer om te markeren.
    assert bouw_meldingen(beperkt, RUNDATUM) == []
    assert _is_systemisch(beperkt.outcomes[0], config)


def _run_met_nulbevindingen(bestand: str, *bevindingen: Nulbevinding) -> CheckRun:
    """Een run zonder eigen checkbevindingen, met alleen nulmetingbevindingen."""
    dataset = load_dataset(TTL_DIR / bestand, [])
    context = CheckContext(dataset=dataset, config=_config())
    run = run_checks(context, [])
    return replace(run, nulbevindingen=tuple(bevindingen))


def _uit_nulmeting(meldingen: list) -> list:
    """De meldingen uit de nulmeting, los van de datasetsignalen (issue #22)."""
    return [melding for melding in meldingen if melding.bron == "nulmeting"]


def test_eigen_checkmelding_noemt_geen_conformiteitsklasse() -> None:
    """`cfk` hoort bij de nulmeting; een eigen check heeft er niets mee te maken."""
    meldingen = bouw_meldingen(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert meldingen[0].cfk == ()


def test_nulbevinding_wordt_een_melding_uit_de_nulmeting() -> None:
    """Bron, categorie en dimensie liggen vast; de CFK's komen van de bevinding."""
    run = _run_met_nulbevindingen("nulmeting_join.ttl", nulbevinding())

    (melding,) = _uit_nulmeting(bouw_meldingen(run, RUNDATUM))

    assert melding.bron == "nulmeting"
    assert melding.categorie == "NULMETING"
    assert melding.dimensie == "Compliance"
    assert melding.cfk == ("MdsPlan", "MdsProj")
    assert melding.check_id == "NULMETING-Put_HoogtePut_card"


def test_nulmelding_op_een_object_met_geometrie_krijgt_een_plek_op_de_kaart() -> None:
    run = _run_met_nulbevindingen("nulmeting_join.ttl", nulbevinding())

    (melding,) = _uit_nulmeting(bouw_meldingen(run, RUNDATUM))

    assert melding.foutlocatie is not None


def test_onherleide_nulmelding_heeft_geen_object_en_geen_gebied() -> None:
    """Een klassenaam of stelsel is aan geen enkel gebied toe te wijzen."""
    onherleid = nulbevinding(
        check_id="NULMETING-CfkTypes_typ",
        vorm="CfkTypes_typ",
        focus_node="Rioolstelsel",
        object_uri="",
        object_label="",
        objecttype="",
        herleid=False,
    )
    run = _run_met_nulbevindingen("nulmeting_join.ttl", onherleid)

    (melding,) = _uit_nulmeting(bouw_meldingen(run, RUNDATUM))

    assert melding.object_uri == ""
    assert melding.gebied == ""
    assert melding.foutlocatie is None


def test_twee_nulmeldingen_op_hetzelfde_object_krijgen_een_eigen_id() -> None:
    """De focusnode onderscheidt ze; de object-URI is dat niet.

    Twee eindpunten van dezelfde streng herleiden naar diezelfde streng.
    """
    run = _run_met_nulbevindingen(
        "nulmeting_join.ttl",
        nulbevinding(focus_node="L1_b", object_uri="http://example.org/toets#L1"),
        nulbevinding(focus_node="L1_e", object_uri="http://example.org/toets#L1"),
    )

    eerste, tweede = _uit_nulmeting(bouw_meldingen(run, RUNDATUM))

    assert eerste.melding_id != tweede.melding_id


def test_prioriteit_volgt_dezelfde_regel_als_bij_een_eigen_check() -> None:
    """Fout is 2 (of 1 op een kritiek object), waarschuwing is 3."""
    run = _run_met_nulbevindingen(
        "nulmeting_join.ttl",
        nulbevinding(ernst="W", focus_node="L1_e"),
    )

    (melding,) = _uit_nulmeting(bouw_meldingen(run, RUNDATUM))

    assert melding.prioriteit == 3


# Issue #65: onderdrukking per klasse en per check, in `bouw_meldingenstroom` en nergens
# anders. De fixture: vrijvervalstreng L1 kruist persleiding L2 en duiker L3. TOP-011
# meldt sinds issue #82 alleen het duikerpaar -- een persleiding valt buiten die
# populatie -- dus een keer, met L1 als hoofdobject en L3 als tweede object; daarnaast
# levert deze kleine fixture SIG-nulklassemeldingen zonder hoofdobject, die hier buiten
# beschouwing blijven (`_zonder_signalen`) behalve waar juist bewezen wordt dat ze blijven
# staan.
PERSLEIDING = "http://example.org/toets#L2"
DUIKER = "http://example.org/toets#L3"
VRIJVERVAL = "http://example.org/toets#L1"


def _run_onderdrukt(
    klassen: Sequence[str] = (), checks: Sequence[str] = (), *bevindingen: Nulbevinding
) -> CheckRun:
    """TOP-011 op de kruisingsfixture, met de twee lijsten uit `[rapport]` gezet."""
    config = _config()
    config.rapport.onderdruk_klassen = list(klassen)
    config.rapport.onderdruk_checks = list(checks)
    dataset = load_dataset(TTL_DIR / "onderdruk_persleiding.ttl", [])
    run = run_checks(CheckContext(dataset=dataset, config=config), ["TOP-011"])
    return replace(run, nulbevindingen=tuple(bevindingen))


def _zonder_signalen(meldingen: list[Melding]) -> list[Melding]:
    """De meldingen die niet uit de datasetsignalen komen (issue #22)."""
    return [melding for melding in meldingen if melding.bron != BRON_DATASET]


def test_zonder_lijsten_verandert_er_niets() -> None:
    stroom = bouw_meldingenstroom(_run_onderdrukt(), RUNDATUM)

    assert [m.object_uri for m in _zonder_signalen(stroom.meldingen)] == [VRIJVERVAL]
    assert stroom.onderdrukking == GEEN_ONDERDRUKKING
    assert not stroom.onderdrukking.actief
    assert bouw_meldingen(_run_onderdrukt(), RUNDATUM) == stroom.meldingen


def test_onderdrukking_per_klasse_haalt_het_hoofdobject_weg_en_laat_het_tweede_object_staan() -> (
    None
):
    """De duiker verliest haar nulmetingmelding; de kruisingsmelding op de
    vrijvervalstreng, die de duiker als object2 noemt, blijft.

    De onderdrukte klasse is die van het tweede object, want alleen dan bewijst de test
    iets: viel de melding op object2 weg, dan zou zij hier verdwijnen.
    """
    nul = nulbevinding(object_uri=DUIKER, object_label="3", objecttype="Duiker")
    stroom = bouw_meldingenstroom(_run_onderdrukt(["Duiker"], [], nul), RUNDATUM)

    over = _zonder_signalen(stroom.meldingen)
    assert [m.object_uri for m in over] == [VRIJVERVAL]
    assert over[0].object2_uri == DUIKER
    # Een: TOP-011 meldt het paar een keer, met de vrijvervalstreng als hoofdobject, dus
    # alleen de nulmetingmelding op de duiker valt hier weg. Ze staat in beide
    # tellingen: onder haar wortel en onder haar check-ID.
    assert stroom.onderdrukking.per_klasse == {"Duiker": 1}
    assert stroom.onderdrukking.per_check == {"NULMETING-Put_HoogtePut_card": 1}
    assert stroom.onderdrukking.totaal == 1
    assert stroom.onderdrukking.actief
    assert stroom.onderdrukking.klassen == ("Duiker",)


def test_onderdrukking_per_check_gaat_voor_en_telt_een_melding_maar_een_keer() -> None:
    """Een melding die op check én klasse zou wegvallen telt niet mee in `per_klasse`.

    `Leiding` en niet `MechanischeTransportleiding`, want alleen onder die wortel valt de
    TOP-011-melding op de vrijvervalstreng ook op klasse weg -- pas dan is er iets om
    voorrang over te geven.
    """
    stroom = bouw_meldingenstroom(_run_onderdrukt(["Leiding"], ["TOP-011"]), RUNDATUM)

    assert _zonder_signalen(stroom.meldingen) == []
    assert stroom.onderdrukking.per_check == {"TOP-011": 1}
    assert stroom.onderdrukking.per_klasse == {}
    assert stroom.onderdrukking.totaal == 1


def test_de_eerste_treffende_wortel_uit_de_lijst_krijgt_de_telling() -> None:
    """De volgorde van de lijst beslist: `Leiding` staat vooraan en telt de persleiding.

    Beide wortels dekken L2; zonder die regel zou een melding onder twee wortels kunnen
    vallen en zou de som van `per_klasse` hoger zijn dan het aantal weggevallen meldingen.
    """
    nul = nulbevinding(object_uri=PERSLEIDING, object_label="2", objecttype="Persleiding")
    stroom = bouw_meldingenstroom(
        _run_onderdrukt(["Leiding", "MechanischeTransportleiding"], [], nul), RUNDATUM
    )

    assert stroom.onderdrukking.per_klasse == {"Leiding": 2}
    assert stroom.onderdrukking.totaal == 2


def test_een_klassetreffer_telt_in_beide_tellingen_maar_een_keer_in_het_totaal() -> None:
    """De twee tellingen beantwoorden verschillende vragen en zijn geen partitie.

    `per_check` is het verschil met de kolom Bevindingen -- ook een check waarvan alle
    bevindingen op klasse wegvielen hoort er met zijn aantal in te staan, want anders
    leest hij als "0 bevindingen" met "per check: geen" ernaast. `per_klasse` zegt onder
    welke wortel dat gebeurde. `totaal` telt alleen `per_check`, dus elke melding een
    keer.
    """
    nul = nulbevinding(object_uri=PERSLEIDING, object_label="2", objecttype="Persleiding")
    stroom = bouw_meldingenstroom(_run_onderdrukt(["Leiding"], [], nul), RUNDATUM)

    assert stroom.onderdrukking.per_check == {
        "TOP-011": 1,
        "NULMETING-Put_HoogtePut_card": 1,
    }
    assert stroom.onderdrukking.per_klasse == {"Leiding": 2}
    assert stroom.onderdrukking.totaal == 2
    assert len(_zonder_signalen(stroom.meldingen)) == 0


def test_een_melding_zonder_object_valt_nooit_op_klasse_weg() -> None:
    """Een onherleide nulmelding en de datasetsignalen hebben geen hoofdobject, dus geen
    klasse; alleen de TOP-011-melding op de vrijvervalstreng valt op `Leiding` weg."""
    los = nulbevinding(object_uri="", object_label="", objecttype="", herleid=False)
    zonder = bouw_meldingenstroom(_run_onderdrukt([], [], los), RUNDATUM)
    stroom = bouw_meldingenstroom(_run_onderdrukt(["Leiding"], [], los), RUNDATUM)

    assert [m.bron for m in _zonder_signalen(stroom.meldingen)] == [BRON_NULMETING]
    assert len(stroom.meldingen) == len(zonder.meldingen) - 1
    assert stroom.onderdrukking.per_klasse == {"Leiding": 1}
    assert stroom.onderdrukking.per_check == {"TOP-011": 1}


def test_onderdrukking_raakt_examined_en_systemisch_niet() -> None:
    """Een uitvoerkeuze, geen toetskeuze: de check zelf ziet de lijsten niet."""
    met = _run_onderdrukt(["MechanischeTransportleiding"], [])
    zonder = _run_onderdrukt()

    assert [o.examined for o in met.outcomes] == [o.examined for o in zonder.outcomes]
    assert [len(o.findings) for o in met.outcomes] == [len(o.findings) for o in zonder.outcomes]
    assert _is_systemisch(met.outcomes[0], met.config) == _is_systemisch(
        zonder.outcomes[0], zonder.config
    )


# Issue #132: geaccepteerde bevindingen (uitzonderingen). De acceptatie haalt de melding
# uit de foutentelling maar laat haar in de stroom staan; de twee luide lijsten vervallen
# nooit vanzelf.


def _met_uitzonderingen(run: CheckRun, *records: Uitzondering) -> CheckRun:
    """Zet een uitzonderingenbestand op de config van een bestaande run.

    De config draagt normaal alleen het pad; `load_check_config` vult de records. Hier
    zetten we beide met de hand, zoals de onderdrukkingstests de twee `[rapport]`-lijsten
    rechtstreeks zetten.
    """
    run.config.rapport.uitzonderingen = "uitz.json"
    run.config.rapport._uitzonderingen = list(records)
    return run


def test_zonder_bestand_zijn_er_geen_uitzonderingen() -> None:
    """Zonder `[rapport] uitzonderingen` verandert er niets aan de stroom."""
    stroom = bouw_meldingenstroom(_run("top001_losliggende_put.ttl", "TOP-001"), RUNDATUM)

    assert stroom.uitzonderingen == GEEN_UITZONDERINGEN
    assert not stroom.uitzonderingen.actief


def test_een_uitzondering_accepteert_de_melding_maar_laat_haar_staan() -> None:
    """De melding valt uit de foutentelling (geaccepteerd) maar blijft in de stroom."""
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    doel = bouw_meldingenstroom(run, RUNDATUM).meldingen[0]
    _met_uitzonderingen(
        run, Uitzondering(melding_id=doel.melding_id, reden="klopt", waarde_snapshot=doel.waarde)
    )

    stroom = bouw_meldingenstroom(run, RUNDATUM)

    assert stroom.uitzonderingen.actief
    assert stroom.uitzonderingen.bestand == "uitz.json"
    assert stroom.uitzonderingen.geaccepteerd == (doel.melding_id,)
    assert stroom.uitzonderingen.zonder_bevinding == ()
    assert stroom.uitzonderingen.gewijzigde_waarde == ()
    # De melding zelf blijft ongewijzigd in de stroom staan.
    assert any(melding.melding_id == doel.melding_id for melding in stroom.meldingen)


def test_een_dode_uitzondering_telt_als_zonder_bevinding() -> None:
    """Een melding-ID uit het bestand dat deze run niet oplevert vervalt niet vanzelf."""
    run = _met_uitzonderingen(
        _run("top001_losliggende_put.ttl", "TOP-001"),
        Uitzondering(melding_id="bestaat-niet", reden="ooit geaccepteerd"),
    )

    stroom = bouw_meldingenstroom(run, RUNDATUM)

    assert stroom.uitzonderingen.zonder_bevinding == ("bestaat-niet",)
    assert stroom.uitzonderingen.geaccepteerd == ()


def test_een_verschoven_waarde_telt_als_gewijzigde_waarde() -> None:
    """Bestaat de melding nog maar wijkt de waarde af, dan is dat geen acceptatie."""
    run = _run("top001_losliggende_put.ttl", "TOP-001")
    doel = bouw_meldingenstroom(run, RUNDATUM).meldingen[0]
    _met_uitzonderingen(
        run,
        Uitzondering(
            melding_id=doel.melding_id, reden="ooit", waarde_snapshot=doel.waarde + "-anders"
        ),
    )

    stroom = bouw_meldingenstroom(run, RUNDATUM)

    assert stroom.uitzonderingen.geaccepteerd == ()
    assert len(stroom.uitzonderingen.gewijzigde_waarde) == 1
    gewijzigd = stroom.uitzonderingen.gewijzigde_waarde[0]
    assert gewijzigd.melding_id == doel.melding_id
    assert gewijzigd.snapshot == doel.waarde + "-anders"
    assert gewijzigd.waarde == doel.waarde


def test_een_uitzondering_op_een_shacl_nulmelding_werkt() -> None:
    """Reikwijdte: alle checks incl. de nulmeting, omdat ze dezelfde melding-ID krijgen."""
    nul = nulbevinding()
    run = replace(_run("top001_losliggende_put.ttl", "TOP-001"), nulbevindingen=(nul,))
    nulmelding = next(
        melding
        for melding in bouw_meldingenstroom(run, RUNDATUM).meldingen
        if melding.bron == BRON_NULMETING
    )
    _met_uitzonderingen(
        run,
        Uitzondering(
            melding_id=nulmelding.melding_id, reden="terecht", waarde_snapshot=nulmelding.waarde
        ),
    )

    stroom = bouw_meldingenstroom(run, RUNDATUM)

    assert stroom.uitzonderingen.geaccepteerd == (nulmelding.melding_id,)
    assert any(melding.melding_id == nulmelding.melding_id for melding in stroom.meldingen)
