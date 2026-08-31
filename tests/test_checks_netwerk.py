"""Tests voor de NET-checks op kleine netwerkfixtures."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest
from gwsw_orox_helpers.dataset import GWSW, load_dataset

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, run_checks
from nlriochecker.checks.netwerk import KringloopInNetwerk
from nlriochecker.checks.verbanden import (
    _netwerk,
    deelstelsel_ids,
    netwerkdelen,
    verbonden_knopen,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
NET_IDS = ["NET-001", "NET-002", "NET-004", "NET-007"]


def _outcome(bestand: str, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand, [])
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def _labels(bestand: str, check_id: str, config: CheckConfig | None = None) -> list[str]:
    """De labels van de gevonden objecten."""
    return sorted(finding.object_label for finding in _outcome(bestand, check_id, config).findings)


@pytest.mark.parametrize("check_id", NET_IDS)
def test_schoon_netwerk_geeft_geen_bevinding(check_id: str) -> None:
    assert _outcome("net_schoon.ttl", check_id).findings == []


def test_net001_vindt_het_losse_deelstelsel() -> None:
    # Streng "1" en "2" bereiken het gemaal; "3" ligt in een los deelstelsel.
    assert _labels("net001_geen_afvoerpad.ttl", "NET-001") == ["3"]


def test_net001_accepteert_een_overnamepunt_op_de_orientatie(tmp_path: Path) -> None:
    """De belofte van BO-33 nagemeten: een geleverd overnamepunt werkt meteen.

    De Wolden en Hoogeveen levert er nul, dus zonder deze fixture draait de hele route
    `_eindpunten` -> `of_class` -> `types_of` -> `orientation_types` op geen enkele
    dataset en in geen enkele test. `gwsw:Overnamepunt` is een subklasse van
    `Aansluitpunt` en dus van `Knooppunt`, en staat daarom op de ORIENTATIE van de
    put; het is die weg die hier bewezen wordt.

    De tweede helft van de test is de controle: haal `Overnamepunt` uit
    `afvoer_eindpunt` en streng "1" wordt wel gemeld. Zonder die helft zou de lege
    lijst hierboven ook groen zijn als de klasse nooit werd opgezocht.
    """
    bestand = "net001_overnamepunt.ttl"
    dataset = load_dataset(TTL_DIR / bestand, [])

    # De klasse wordt op de orientatie van put B gevonden, niet op put B zelf.
    knoop = dataset.nodes["http://example.org/toets#PutB"]
    assert f"{GWSW}Overnamepunt" in knoop.orientation_types
    assert f"{GWSW}Overnamepunt" not in knoop.types
    assert dataset.of_class("Overnamepunt") == ["http://example.org/toets#PutB"]

    assert _labels(bestand, "NET-001") == []

    zonder_overnamepunt = tmp_path / "zonder.toml"
    zonder_overnamepunt.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "afvoer_eindpunt = []\nvuilwater = ['GemengdRiool']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n",
        encoding="utf-8",
    )
    gevonden = _outcome(bestand, "NET-001", load_check_config(zonder_overnamepunt))
    assert sorted(finding.object_label for finding in gevonden.findings) == ["1"]


def test_losse_overnamepuntorientatie_verdwijnt_uit_de_netwerkanalyse() -> None:
    """Het restrisico bij BO-33, als feit vastgelegd in plaats van als aanname.

    Levert een export een `Overnamepunt` als losstaande orientatie zonder dragend
    object, dan bouwt het domeinmodel er geen knoop van. Gevolg is niet dat de
    streng ernaartoe als onbereikbaar gemeld wordt, maar dat ze helemaal buiten de
    netwerkanalyse valt: geen herleidbare put aan beide zijden. Alleen de notitie
    van de check telt haar nog.
    """
    dataset = load_dataset(TTL_DIR / "net001_overnamepunt.ttl", [])
    assert "http://example.org/toets#LosOvp_ori" not in dataset.nodes

    outcome = _outcome("net001_overnamepunt.ttl", "NET-001")

    assert [finding.object_label for finding in outcome.findings] == []
    notitie = next(n for n in outcome.notes if "buiten de netwerkanalyse" in n)
    assert "2" in notitie


def test_net002_vindt_hemelwater_zonder_lozingspunt() -> None:
    assert _labels("net002_hemelwater_zonder_lozingspunt.ttl", "NET-002") == ["4"]


def test_net002_raakt_de_gemengde_strengen_niet() -> None:
    # De gemengde strengen vallen onder NET-001, niet onder NET-002.
    assert _labels("net001_geen_afvoerpad.ttl", "NET-002") == []


def test_net001_noemt_het_stelseltype_van_de_streng() -> None:
    """Het verschil met NET-002 hoort uit de melding zelf te lezen te zijn (issue #93).

    NET-001 gaat over twee stelseltypen tegelijk (`Vuilwaterriool` plus `GemengdRiool`);
    de melding noemt daarom het type van DEZE streng en niet de rol waarop de check
    selecteert. Twee fixtures, twee typen -- anders zou een vaste tekst ook groen zijn.
    """
    gemengd = _outcome("net001_geen_afvoerpad.ttl", "NET-001").findings[0]
    vuilwater = _outcome("net001_pompunit_zonder_persnet.ttl", "NET-001").findings[0]

    assert gemengd.message == (
        "Streng van stelseltype 'gemengd' zonder afvoerpad naar een gemaal, "
        "overnamepunt of lozingspunt."
    )
    assert gemengd.details["stelseltype"] == "gemengd"
    assert vuilwater.message.startswith(
        "Streng van stelseltype 'vuilwater' zonder afvoerpad naar een gemaal, "
        "overnamepunt of lozingspunt."
    )
    assert vuilwater.details["stelseltype"] == "vuilwater"


def test_net002_noemt_hemelwater_en_het_eindpunt_dat_hij_zoekt() -> None:
    """Dezelfde verheldering voor NET-002, nu met het bredere eindpunt van issue #127.

    Sinds #127 leest NET-002 ook `afvoer_eindpunt` (overnamepunt/gemaal), maar alleen
    als de hemelwaterstreng benedenstrooms in gemengd riool overgaat. Deze fixture heeft
    geen gemengd riool en geen lozingspunt, maar wél een Gemaal (via de standaardconfig
    in `afvoer_eindpunt`); de "geen enkel bereikbaar eindpunt"-staart verdwijnt dus, want
    de graaf draagt wel degelijk een eindpunt van het bredere soort -- alleen bereikt
    deze streng het niet (geen gemengd ertussen).
    """
    bevinding = _outcome("net002_hemelwater_zonder_lozingspunt.ttl", "NET-002").findings[0]

    assert bevinding.message == (
        "Streng van stelseltype 'hemelwater' zonder afvoerpad naar een lozingspunt, of "
        "via een gemengd riool een overnamepunt of gemaal."
    )
    assert bevinding.details["stelseltype"] == "hemelwater"


def test_net002_accepteert_een_overnamepunt_via_gemengd_riool() -> None:
    """De kern van issue #127: hemelwater dat benedenstrooms gemengd wordt, mag op een
    overnamepunt uitkomen. `1` (hemelwater) gaat op knoop B over in `2` (gemengd) en komt
    uit op overnamepunt C; er is geen lozingspunt in de fixture.
    """
    assert _labels("net002_hemelwater_via_gemengd_naar_overnamepunt.ttl", "NET-002") == []


def test_net002_blijft_hemelwater_rechtstreeks_naar_overnamepunt_melden() -> None:
    """De controlehelft: zonder gemengd ertussen blijft een overnamepunt geen bestemming.

    Streng '1' is hemelwater en komt rechtstreeks op een overnamepunt uit, zonder dat
    het stelseltype ooit gemengd wordt. Zou de check zomaar élk overnamepunt accepteren,
    dan was deze fixture ook groen -- en dat is precies de valse-positief-onderdrukking
    die het issue niet vraagt.
    """
    assert _labels("net002_hemelwater_naar_overnamepunt_zonder_gemengd.ttl", "NET-002") == ["1"]


def test_net002_toelichting_telt_een_via_gemengd_bereikt_eindpunt_niet_als_doodlopend() -> None:
    """Fixronde 1 op issue #127: de toelichting mag niet tegenspreken wat de check meet.

    Overnamepunt C is de enige eindknoop (sink) in deze fixture, en de check accepteert
    hem via het gemengde voorbehoud (`test_net002_accepteert_een_overnamepunt_via_gemengd_riool`
    hierboven bewijst dat er geen bevinding op '1' komt). `_eindknoop_notitie` moet diezelfde
    knoop dus ook als bereikt tellen -- zonder dat zou de toelichting beweren dat het
    vrijverval doodloopt en "alles wat daarachter ligt" onbeoordeeld blijft, terwijl de check
    die streng juist wél beoordeelde en goedkeurde.
    """
    outcome = _outcome("net002_hemelwater_via_gemengd_naar_overnamepunt.ttl", "NET-002")

    assert not any("watert af op" in note for note in outcome.notes)


def test_net004_vindt_de_kringloop() -> None:
    bevindingen = _outcome("net004_kringloop.ttl", "NET-004").findings

    # Een melding per samenhangend deel met een kringloop, niet per enkelvoudige
    # kringloop: dat laatste groeit exponentieel op een echt stelsel.
    assert len(bevindingen) == 1
    assert bevindingen[0].details["putten_in_deel"] == 3
    # Op volgorde, niet als verzameling: de kring hoort niet per run te verspringen.
    assert bevindingen[0].details["voorbeeldkring"] == ["C", "D", "E"]


def test_net004_voorbeeldkring_hangt_niet_van_de_knoopvolgorde_af() -> None:
    """Dezelfde kringloop moet dezelfde melding opleveren, hoe de graaf ook gevuld is.

    `nx.find_cycle` zonder `source` begint bij de eerste knoop in invoegvolgorde, en
    die volgt uit een `set` uit `strongly_connected_components` -- dus uit de hashseed.
    Zonder vast beginpunt wijst NET-004 per run een andere streng aan, en dan toont
    `vergelijk` verschillen tussen twee runs op dezelfde data die er niet zijn.
    """
    check = KringloopInNetwerk()
    kanten = [("c", "a"), ("a", "b"), ("b", "c")]
    volgordes = (kanten, list(reversed(kanten)), [kanten[1], kanten[2], kanten[0]])

    kringen = set()
    for volgorde in volgordes:
        graaf = nx.DiGraph()
        graaf.add_edges_from(volgorde)
        kringen.add(tuple(check._voorbeeldkring(graaf)))

    assert kringen == {("a", "b", "c")}


@pytest.mark.parametrize(
    "bestand", ["net004_parallelle_strengen.ttl", "net004_parallelle_strengen_omgekeerd.ttl"]
)
def test_net004_noemt_dezelfde_streng_ongeacht_de_invoervolgorde(bestand: str) -> None:
    """Twee parallelle strengen op de kring: de melding hangt aan een streng die echt op
    de kant kring[0] -> kring[1] ligt, en aan dezelfde streng ongeacht de volgorde waarin
    de export ze declareert. Anders verschuift de melding-ID tussen twee exports."""
    dataset = load_dataset(TTL_DIR / bestand, [])
    context = CheckContext(dataset=dataset, config=load_check_config())
    bevindingen = run_checks(context, ["NET-004"]).outcomes[0].findings

    assert len(bevindingen) == 1
    assert bevindingen[0].details["voorbeeldkring"] == ["C", "D", "E"]
    streng = dataset.conduits[bevindingen[0].object_uri]
    begin, eind = verbonden_knopen(context, streng)
    assert (dataset.nodes[begin].label, dataset.nodes[eind].label) == ("C", "D")
    # De kleinste URI van de parallelle set, in beide declaratievolgordes.
    assert bevindingen[0].object_label == "5"


def test_net004_dempt_een_lus_die_alleen_administratief_bestaat() -> None:
    """Een kring die op een omgekeerd geregistreerde streng leunt is geen echte lus (issue #102).

    Streng 7 (E->C) stijgt in de BOB; NET-009 spreekt haar tegen, dus haar richting is
    onbetrouwbaar. Met de betrouwbare richting valt de kring uiteen en NET-004 zwijgt --
    NET-009 draagt dit signaal al.
    """
    outcome = _outcome("net004_lus_door_richtingsfout.ttl", "NET-004")

    assert outcome.findings == []


def test_net004_dempt_een_vermaasde_ring() -> None:
    """Een vlakke, BOB-consistente ring zonder putsprong is bewust vermaasd net (issue #102).

    In vlak Nederland is zo'n ring legitiem en geen fout; NET-004 dempt hem en telt hem in
    de toelichting.
    """
    outcome = _outcome("net004_vermaasde_ring.ttl", "NET-004")

    assert outcome.findings == []
    assert any("vermaasd" in note for note in outcome.notes)


def test_net004_dempt_een_ring_die_via_een_putsprong_sluit() -> None:
    """Een ring die per been daalt maar via een BOB-sprong omhoog sluit is HGT-009 (issue #102)."""
    outcome = _outcome("net004_ring_met_putsprong.ttl", "NET-004")

    assert outcome.findings == []
    assert any("HGT-009" in note for note in outcome.notes)


def test_net007_vindt_it_zonder_drempel() -> None:
    assert _labels("net007_it_zonder_drempel.ttl", "NET-007") == ["8"]


def test_net007_zwijgt_als_er_een_drempel_is() -> None:
    assert _labels("net007_it_met_drempel.ttl", "NET-007") == []


def test_net007_zwijgt_bij_overstortput_zonder_los_drempelobject() -> None:
    # Zoals overstorten op de De Wolden en Hoogeveen-export staan: een Overstortput met een
    # Overstortleiding, geen los Overstortdrempel-object. NET-007 hoort die vorm te
    # herkennen; deed hij dat niet, dan meldde hij elk infiltratieriool. Zie issue #42.
    assert _labels("net007_it_met_overstortput.ttl", "NET-007") == []


def test_ontbrekend_eindpunt_wordt_expliciet_gemeld() -> None:
    # In de TOP-fixture zit geen gemaal; dan is elke streng onbereikbaar en dat
    # hoort met zoveel woorden in de bevinding en in de notities te staan.
    outcome = _outcome("schoon.ttl", "NET-001")

    assert len(outcome.findings) == 1
    assert "geen enkel bereikbaar eindpunt" in outcome.findings[0].message
    assert outcome.findings[0].details["geen_eindpunten_in_graaf"] is True
    assert any("geen enkel eindpunt" in notitie for notitie in outcome.notes)


def test_strengen_buiten_de_graaf_worden_geteld() -> None:
    # Streng "2" heeft geen koppelingen; die valt buiten de netwerkanalyse en
    # dat mag niet stilzwijgend gebeuren.
    outcome = _outcome("top002_losliggende_streng.ttl", "NET-001")

    assert any("buiten de netwerkanalyse" in notitie for notitie in outcome.notes)
    assert any("2" in notitie for notitie in outcome.notes)


def test_eindpuntklassen_komen_uit_de_config(tmp_path: Path) -> None:
    zonder_gemaal = tmp_path / "zonder.toml"
    zonder_gemaal.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "lozings_eindpunt = ['Lozingspunt']\nvuilwater = ['GemengdRiool']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n",
        encoding="utf-8",
    )

    # Met de standaardconfig bereikt alles het gemaal.
    assert _labels("net_schoon.ttl", "NET-001") == []

    # Zonder Gemaal als eindpuntklasse telt het gemaal ook niet meer als knoop:
    # streng "2" eindigt daarop en valt daarmee buiten de graaf, streng "1"
    # blijft over en bereikt niets.
    gevonden = _outcome("net_schoon.ttl", "NET-001", load_check_config(zonder_gemaal))

    assert sorted(finding.object_label for finding in gevonden.findings) == ["1"]
    assert any("buiten de netwerkanalyse" in notitie for notitie in gevonden.notes)


def test_lozingspunt_telt_als_afvoerpad_voor_vuilwater(tmp_path: Path) -> None:
    """Een gemengde streng die een lozingsput bereikt is in orde (BO-53).

    Vuilwater loost in Nederland niet meer rechtstreeks op oppervlaktewater, dus een
    lozingspunt is per definitie een geldig afvoereindpunt; er valt geen echt gebrek
    mee te maskeren. De tweede helft is de controle: haal de lozingsput uit
    `lozings_eindpunt` en streng "1" wordt wel gemeld, zodat de lege lijst hierboven
    niet ook groen zou zijn als de klasse nooit werd opgezocht.
    """
    bestand = "net001_alleen_lozingspunt.ttl"

    assert _labels(bestand, "NET-001") == []
    assert _labels(bestand, "NET-002") == []

    zonder_lozing = _testconfig(
        tmp_path,
        "zonder_lozing",
        "put = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "mechanisch = ['MechanischeRioolleiding']\n"
        "afvoer_eindpunt = ['Gemaal']\nlozings_eindpunt = []\nvuilwater = ['GemengdRiool']\n",
    )
    assert _labels(bestand, "NET-001", zonder_lozing) == ["1"]


# De drukrioleringsketen laat Pompunit buiten `afvoer_eindpunt`, net als de
# meegeleverde config sinds BO-55: was de pompput zelf al een eindpunt, dan bewees de
# fixture niets over de route erachter.
_DRUKRIOLERING_KLASSEN = (
    "put = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
    "mechanisch = ['MechanischeRioolleiding']\nafvoer_eindpunt = ['Gemaal']\n"
    "lozings_eindpunt = ['Lozingsput']\nvuilwater = ['Vuilwaterriool']\n"
)


def test_drukriolering_bereikt_het_gemaal_door_het_hulpstuk(tmp_path: Path) -> None:
    """Het persnet telt als connectiviteit, ook waar het op een T-stuk samenkomt (BO-54).

    Het T-stuk klimt via hasPart niet naar een put, dus `resolve_network_node` geeft er
    None voor; zonder terugval op de rauwe koppeling versplintert elke T het persnet en
    blijft het gemaal erachter onbereikbaar. De controle draait dezelfde fixture met een
    lege `mechanisch`-lijst: dan is er geen route en wordt streng "1" wel gemeld.

    De fixture pint meteen aanname 1 van issue #72 vast: de laatste drukleiding staat
    administratief van het gemaal naar het T-stuk geregistreerd. Een persleiding is
    pompgestuurd en die richting zegt niets, dus de mechanische kant hoort ongericht te
    zijn. Zou hij alleen in de geregistreerde richting gelegd worden, dan is er geen
    kant naar het gemaal toe en valt deze test om.
    """
    bestand = "net001_drukriolering_gemaal.ttl"
    config = _testconfig(tmp_path, "druk_gemaal", _DRUKRIOLERING_KLASSEN)
    dataset = load_dataset(TTL_DIR / bestand, [])

    assert (
        dataset.resolve_network_node("http://example.org/toets#T1", config.klassen.netwerkknopen)
        is None
    )
    # De route loopt tegen de registratie van 'd2' in: gemaal -> T-stuk staat er, en de
    # bereikbaarheid moet de andere kant op.
    d2 = next(streng for streng in dataset.conduits.values() if streng.label == "d2")
    assert (d2.start_node, d2.end_node) == (
        "http://example.org/toets#Gem",
        "http://example.org/toets#T1",
    )

    assert _labels(bestand, "NET-001", config) == []

    assert _labels(bestand, "NET-001", _zonder_persnet(config)) == ["1"]


def test_drukriolering_die_op_een_lozingsput_uitkomt_is_afgevoerd(tmp_path: Path) -> None:
    """Dezelfde keten, maar het persnet loost op een lozingsput in plaats van een gemaal.

    De twee wijzigingen van issue #72 samen: het persnet is doorlopend (BO-54) en het
    lozingspunt aan het eind telt als vuilwater-eindpunt (BO-53).
    """
    bestand = "net001_drukriolering_lozingsput.ttl"
    config = _testconfig(tmp_path, "druk_lozing", _DRUKRIOLERING_KLASSEN)

    assert _labels(bestand, "NET-001", config) == []

    zonder_lozing = _testconfig(
        tmp_path, "druk_zonder_lozing", _DRUKRIOLERING_KLASSEN.replace("['Lozingsput']", "[]")
    )
    assert _labels(bestand, "NET-001", zonder_lozing) == ["1"]


def test_hemelwater_door_het_persnet_geldt_ook_als_afgevoerd(tmp_path: Path) -> None:
    """De bereikbaarheidsgraaf is gedeeld, dus NET-002 volgt het persnet ook (BO-54).

    Dit is een bewust gevolg en geen bijvangst: `_bereikbaar_vanaf` is dezelfde functie
    voor beide bereikbaarheidschecks, en een hemelwaterstreng die op een pompput eindigt
    voert langs het persnet af. De domeinredenering van BO-53 (een lozingspunt is een
    geldig VUILWATER-eindpunt) speelt hier niet mee: NET-002 vroeg altijd al om een
    lozingspunt. Wat verandert is alleen de route ernaartoe. De controlehelft laat zien
    dat de route echt door het persnet loopt.
    """
    bestand = "net002_drukriolering_lozingsput.ttl"
    klassen = _DRUKRIOLERING_KLASSEN + "hemelwater = ['Hemelwaterriool']\n"
    config = _testconfig(tmp_path, "net002_druk", klassen)

    assert _labels(bestand, "NET-002", config) == []

    assert _labels(bestand, "NET-002", _zonder_persnet(config)) == ["1"]


def test_pompunit_zonder_persnet_is_geen_afvoereindpunt(tmp_path: Path) -> None:
    """Een pompput is een overdrachtspunt naar de drukriolering, geen eindpunt (BO-55).

    Draait bewust op de MEEGELEVERDE config: het is de lijst `afvoer_eindpunt` in
    `checks.toml` die hier bewezen wordt, niet een testlijst. Zonder persleiding
    achter de pompunit komt streng "1" nergens uit en hoort ze gemeld te worden.

    De controlehelft zet `Pompunit` terug in `afvoer_eindpunt`: dan zwijgt de check
    weer. Zonder die helft zou de melding hierboven ook groen zijn als de streng om
    een heel andere reden buiten de graaf viel.
    """
    bestand = "net001_pompunit_zonder_persnet.ttl"

    assert _labels(bestand, "NET-001") == ["1"]

    met_pompunit = _testconfig(
        tmp_path,
        "met_pompunit",
        "put = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "afvoer_eindpunt = ['Gemaal', 'Pompunit']\nvuilwater = ['Vuilwaterriool']\n",
    )
    assert _labels(bestand, "NET-001", met_pompunit) == []


# De vrijvervalketen door een hulpstuk, zonder pompunit en zonder persnet: het T-stuk
# is hier de enige schakel tussen put A en de rest. `mechanisch` staat er alleen omdat
# `ClassRoots._pompunit_heeft_een_uitweg` een geschreven config zonder persnet weigert.
_HULPSTUKKETEN_KLASSEN = (
    "put = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
    "mechanisch = ['MechanischeRioolleiding']\nafvoer_eindpunt = ['Gemaal']\n"
    "vuilwater = ['GemengdRiool']\n"
)


def test_netwerkdelen_lopen_door_een_telbaar_hulpstuk() -> None:
    """Een T-stuk is een doorgeefknoop in de vrijvervalgraaf (issue #105, BO-83).

    Een `Hulpstuk` is geen `Put`, dus `resolve_network_node` geeft er None voor en de
    graaf liet de streng erop vallen. Het net zit er in werkelijkheid wel aan vast --
    de leeslaag herstelde die koppeling zelfs (`SIG-hulpstukkoppeling`) -- dus valt de
    vrijvervalgraaf sinds dit issue terug op de rauwe koppeling zolang die op een
    hulpstuk met een telbare GWSW-functie wijst. Put A, T-stuk T1, overstortput O en het
    gemaal horen daarmee in een deelstelsel, met een gedeeld ID.
    """
    dataset = load_dataset(TTL_DIR / "net_hulpstuk_doorgeefknoop.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    delen = netwerkdelen(context)

    assert len(delen) == 1
    assert "http://example.org/toets#T1" in delen[0]
    assert len(set(deelstelsel_ids(context).values())) == 1


def test_net001_bereikt_het_gemaal_door_het_telbare_hulpstuk(tmp_path: Path) -> None:
    """De strengen aan het T-stuk doen weer mee aan de netwerkanalyse (issue #105).

    Ze vielen er niet uit met een bevinding maar zonder oordeel: "geen herleidbare put
    aan beide zijden", alleen zichtbaar in de notitie. De controlehelft haalt `hulpstuk`
    uit de config: dan is het T-stuk geen doorgeefknoop meer en vallen dezelfde twee
    strengen weer buiten de analyse.
    """
    bestand = "net_hulpstuk_doorgeefknoop.ttl"

    outcome = _outcome(bestand, "NET-001")

    assert outcome.findings == []
    assert not any("buiten de netwerkanalyse" in notitie for notitie in outcome.notes)

    zonder_hulpstuk = _testconfig(
        tmp_path, "zonder_hulpstuk", _HULPSTUKKETEN_KLASSEN + "hulpstuk = []\n"
    )
    andere = _outcome(bestand, "NET-001", zonder_hulpstuk)
    notitie = next(n for n in andere.notes if "buiten de netwerkanalyse" in n)
    assert notitie.startswith("2 vrijvervalstrengen")


def test_de_knooptellingen_laten_de_doorgeefknopen_buiten_beschouwing() -> None:
    """Een "knoop" in een melding, een drempel of `examined` is een beoordeeld object.

    De graaf draagt het hulpstuk wél als knoop -- daar geeft het door -- maar geen enkele
    NET-check beoordeelt het. Zou het meetellen, dan telde `examined` objecten die nooit
    een bevinding kunnen krijgen en zou de drempel `klein_deelstelsel_knopen` bij een
    T-stukrijk net eerder overlopen. De fixture heeft vier graafknopen waarvan er een een
    T-stuk is (issue #105, BO-83).
    """
    dataset = load_dataset(TTL_DIR / "net_hulpstuk_doorgeefknoop.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    assert _netwerk(context).graph.number_of_nodes() == 4

    for check_id in ("NET-006", "NET-008"):
        assert run_checks(context, [check_id]).outcomes[0].examined == 3


def test_een_afsluitstuk_blijft_een_breuk_in_de_vrijvervalgraaf() -> None:
    """Alleen een hulpstuk met een telbare functie geeft door; een afsluitstuk niet.

    Dezelfde grens als BO-72 voor TOP-002/TOP-003 trekt: `Afsluitstuk` draagt de functie
    `AfsluitenVanLeidingen`, en die schrijft geen aantal leidingen voor. De keten valt
    hier dus wel uiteen, en dat hoort in de notitie te staan.
    """
    dataset = load_dataset(TTL_DIR / "net_hulpstuk_afsluitstuk.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    assert len(netwerkdelen(context)) == 2

    outcome = _outcome("net_hulpstuk_afsluitstuk.ttl", "NET-001")
    assert any("buiten de netwerkanalyse" in notitie for notitie in outcome.notes)


def _zonder_persnet(config: CheckConfig) -> CheckConfig:
    """Dezelfde config met het persnet uitgezet, voor de controlehelften.

    Bewust niet als TOML: `ClassRoots._pompunit_heeft_een_uitweg` weigert sinds BO-55
    een geschreven config die `mechanisch` leeg laat terwijl `Pompunit` geen eindpunt is
    -- dat is de valse-positieventoestand van BO-33. Die poort bewaakt wat iemand als
    projectconfig opschrijft; hier wordt de lijst na de validatie leeggemaakt om te tonen
    dat de route echt door het persnet loopt en niet ergens anders vandaan komt.
    """
    zonder = config.model_copy(deep=True)
    zonder.klassen.mechanisch = []
    return zonder


def _testconfig(tmp_path: Path, naam: str, klassen: str) -> CheckConfig:
    """Een projectconfig met alleen de klassen die de test nodig heeft."""
    pad = tmp_path / f"{naam}.toml"
    pad.write_text(
        f"[klassen]\n{klassen}[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n",
        encoding="utf-8",
    )
    return load_check_config(pad)


def test_notitie_meldt_strengen_die_tegen_de_bob_in_lopen(tmp_path: Path) -> None:
    """De richtingsaanname is een aanname; hij hoort meetbaar in het rapport."""
    bron = (TTL_DIR / "net_schoon.ttl").read_text(encoding="utf-8")
    # Geef streng "1" een stijgende BOB in de aangenomen afvoerrichting.
    bron += (
        "\n:L1_b gwsw:hasAspect [ rdf:type gwsw:BobBeginpuntLeiding ; gwsw:hasValue 10.0 ] .\n"
        ":L1_e gwsw:hasAspect [ rdf:type gwsw:BobEindpuntLeiding ; gwsw:hasValue 11.0 ] .\n"
        ":L2_b gwsw:hasAspect [ rdf:type gwsw:BobBeginpuntLeiding ; gwsw:hasValue 11.0 ] .\n"
        ":L2_e gwsw:hasAspect [ rdf:type gwsw:BobEindpuntLeiding ; gwsw:hasValue 10.0 ] .\n"
    )
    pad = tmp_path / "bob.ttl"
    pad.write_text(bron, encoding="utf-8")

    dataset = load_dataset(pad, [])
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["NET-001"]).outcomes[0]

    assert any("stijgt de bodem juist in die richting" in n for n in outcome.notes)
    assert any("1 van de 2" in n for n in outcome.notes)


def test_notitie_telt_doodlopende_eindknopen() -> None:
    """Zonder deze telling lijkt elke onbereikbare streng een los gebrek.

    In het losse deelstelsel watert alles af op put 'D', en die is geen
    uitstroompunt; dat is de oorzaak van de bevinding, niet de streng zelf.
    """
    outcome = _outcome("net001_geen_afvoerpad.ttl", "NET-001")

    notitie = next(n for n in outcome.notes if "watert af op" in n)
    assert "de overige 1 loopt dood" in notitie
    # De soortnaam is het beheerobject en niet zijn orientatie: het GWSW hangt de
    # topologische rol aan een orientatie-aspect, en `types_of()` voegt die aspecttypen
    # bewust bij de objecttypen. Alfabetisch sorteren liet "Putorientatie" winnen van
    # "Inspectieput", waardoor de toelichting aspecten leek te tellen in plaats van putten.
    assert "Inspectieput 1" in notitie
    assert "orientatie" not in notitie


def test_richting_uit_het_bodemverloop_draait_strengen_om(tmp_path: Path) -> None:
    """De richtingskeuze uit de config moet daadwerkelijk doorwerken."""
    bron = (TTL_DIR / "net_schoon.ttl").read_text(encoding="utf-8")
    # Streng "1" is administratief A -> B, maar de bodem loopt van B naar A.
    bron += (
        "\n:L1_b gwsw:hasAspect [ rdf:type gwsw:BobBeginpuntLeiding ; gwsw:hasValue 10.0 ] .\n"
        ":L1_e gwsw:hasAspect [ rdf:type gwsw:BobEindpuntLeiding ; gwsw:hasValue 11.0 ] .\n"
    )
    pad = tmp_path / "bob.ttl"
    pad.write_text(bron, encoding="utf-8")

    op_bob = tmp_path / "bob.toml"
    op_bob.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "mechanisch = ['MechanischeRioolleiding']\n"
        "afvoer_eindpunt = ['Gemaal']\nvuilwater = ['GemengdRiool']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n"
        "[netwerk]\nrichting = 'bob'\n",
        encoding="utf-8",
    )

    # Administratief bereikt alles het gemaal; op de bodem gedraaid loopt streng "1"
    # de verkeerde kant op en raakt put A het gemaal niet meer.
    assert _labels_op(pad, "NET-001", None) == []
    assert _labels_op(pad, "NET-001", load_check_config(op_bob)) == ["1"]


def _labels_op(pad: Path, check_id: str, config: CheckConfig | None) -> list[str]:
    """Draait een check op een pad buiten de fixturemap."""
    dataset = load_dataset(pad, [])
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    outcome = run_checks(context, [check_id]).outcomes[0]
    return sorted(finding.object_label for finding in outcome.findings)


def test_uitlaatconstructie_is_geen_doodlopende_eindknoop_voor_vuilwater() -> None:
    """Een gemengde streng die op een uitlaatconstructie eindigt loopt niet dood (BO-53).

    Tot issue #72 was dit de fixture waarop NET-001 een doodlopende Bouwwerk-eindknoop
    telde. Nu het lozingspunt als geldig vuilwater-eindpunt geldt, is die uitlaat een
    uitstroompunt en blijft er geen doodlopende eindknoop over. Dat de soortnaam in de
    verdeling het beheerobject is en niet zijn orientatie, bewaakt
    `test_beheerobjecttype_negeert_de_orientatie` op deze fixture.
    """
    outcome = _outcome("net001_bouwwerk_eindknoop.ttl", "NET-001")

    assert outcome.findings == []
    assert not any("loopt dood" in note for note in outcome.notes)


def test_orientatie_aspecten_zijn_geen_knoop_in_de_netwerkgraaf() -> None:
    """Elke graafknoop is een beheerobject, niet het aspect waar zijn rol op hangt.

    De lader neemt als knoop het subject dat de orientatie via hasAspect draagt.
    Deze test legt dat vast, zodat een latere wijziging in `_read_nodes()` niet
    stilzwijgend aspecten de graaf in laat lopen.
    """
    dataset = load_dataset(TTL_DIR / "net001_bouwwerk_eindknoop.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    graaf = _netwerk(context).graph

    assert graaf.number_of_nodes() == 2
    for uri in graaf:
        # `types` zijn de typen van het object zelf; `orientation_types` die van het
        # aspect. Een knoop die alleen het laatste heeft, is een gelekt aspect.
        assert dataset.nodes[uri].types


def test_deelstelsel_ids_delen_een_id_binnen_hetzelfde_netwerkdeel() -> None:
    """Knopen in hetzelfde vrijvervaldeel horen bij hetzelfde deelstelsel.

    De fixture heeft twee losse delen: A-B-G rond het gemaal, en C-D daarbuiten.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    ids = deelstelsel_ids(context)

    per_label = {dataset.nodes[uri].label: cluster for uri, cluster in ids.items()}
    assert per_label["A"] == per_label["B"] == per_label["G"]
    assert per_label["C"] == per_label["D"]
    assert per_label["A"] != per_label["C"]


def test_net001_draagt_het_deelstelsel_id_van_zijn_streng() -> None:
    """24 bevindingen op 2 deelstelsels zijn geen 24 losse gebreken.

    Zonder ID op de bevinding is dat verband alleen uit de kaart af te leiden.
    """
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())
    ids = deelstelsel_ids(context)
    verwacht = next(cluster for uri, cluster in ids.items() if dataset.nodes[uri].label == "C")

    outcome = run_checks(context, ["NET-001"]).outcomes[0]

    bevinding = next(f for f in outcome.findings if f.object_label == "3")
    assert bevinding.details["cluster_id"] == verwacht


def test_net001_laat_de_clusterduiding_aan_het_rapport() -> None:
    """De check kent de afbakening niet, dus telt hij de deelstelsels niet zelf.

    Zou hij dat wel doen, dan meldde een tot een buurt afgebakend rapport het
    aantal deelstelsels van de hele dataset -- op De Wolden en Hoogeveen 174 bij 24 bevindingen.
    """
    outcome = _outcome("net001_geen_afvoerpad.ttl", "NET-001")

    assert not any("deelstelsel" in note for note in outcome.notes)
    assert all(f.details["cluster_id"] for f in outcome.findings)
