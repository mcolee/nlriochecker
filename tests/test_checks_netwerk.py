"""Tests voor de NET-checks op kleine netwerkfixtures."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, run_checks
from nlriochecker.checks.netwerk import KringloopInNetwerk
from nlriochecker.checks.verbanden import _netwerk, deelstelsel_ids, verbonden_knopen
from nlriochecker.dataset import GWSW, load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
NET_IDS = ["NET-001", "NET-002", "NET-004", "NET-007"]


def _outcome(bestand: str, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def _labels(bestand: str, check_id: str) -> list[str]:
    """De labels van de gevonden objecten."""
    return sorted(finding.object_label for finding in _outcome(bestand, check_id).findings)


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
    dataset = load_dataset(TTL_DIR / bestand)

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
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n",
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
    dataset = load_dataset(TTL_DIR / "net001_overnamepunt.ttl")
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
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=load_check_config())
    bevindingen = run_checks(context, ["NET-004"]).outcomes[0].findings

    assert len(bevindingen) == 1
    assert bevindingen[0].details["voorbeeldkring"] == ["C", "D", "E"]
    streng = dataset.conduits[bevindingen[0].object_uri]
    begin, eind = verbonden_knopen(context, streng)
    assert (dataset.nodes[begin].label, dataset.nodes[eind].label) == ("C", "D")
    # De kleinste URI van de parallelle set, in beide declaratievolgordes.
    assert bevindingen[0].object_label == "5"


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
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n",
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


def test_lozingspunt_telt_niet_als_afvoerpad_voor_vuilwater() -> None:
    """Een gemengde streng die alleen een lozingsput bereikt is niet in orde.

    NET-001 vraagt een gemaal of overnamepunt, NET-002 een lozingspunt. Met een
    gedeelde eindpuntlijst zou de gemengde streng ten onrechte goedgekeurd worden.
    """
    bestand = "net001_alleen_lozingspunt.ttl"

    assert _labels(bestand, "NET-001") == ["1"]
    assert _labels(bestand, "NET-002") == []


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

    dataset = load_dataset(pad)
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
    assert "loopt dood" in notitie
    assert "Inspectieput" in notitie


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
        "afvoer_eindpunt = ['Gemaal']\nvuilwater = ['GemengdRiool']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[netwerk]\nrichting = 'bob'\n",
        encoding="utf-8",
    )

    # Administratief bereikt alles het gemaal; op de bodem gedraaid loopt streng "1"
    # de verkeerde kant op en raakt put A het gemaal niet meer.
    assert _labels_op(pad, "NET-001", None) == []
    assert _labels_op(pad, "NET-001", load_check_config(op_bob)) == ["1"]


def _labels_op(pad: Path, check_id: str, config: CheckConfig | None) -> list[str]:
    """Draait een check op een pad buiten de fixturemap."""
    dataset = load_dataset(pad)
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    outcome = run_checks(context, [check_id]).outcomes[0]
    return sorted(finding.object_label for finding in outcome.findings)


def test_eindknoopverdeling_noemt_het_beheerobject_niet_zijn_orientatie() -> None:
    """De soortnaam van een eindknoop hoort het beheerobject te zijn.

    Het GWSW hangt de topologische rol aan een orientatie-aspect, en `types_of()`
    voegt die aspecttypen bewust bij de objecttypen (Lozingspunt en UitlaatPunt
    staan er immers op). Alfabetisch sorteren liet daardoor "Bouwwerkorientatie"
    winnen van "Uitlaatconstructie" en "Putorientatie" van "Rioolput", waardoor de
    toelichting aspecten leek te tellen in plaats van bouwwerken.
    """
    outcome = _outcome("net001_bouwwerk_eindknoop.ttl", "NET-001")

    verdeling = next(note for note in outcome.notes if "dood" in note)
    assert "Uitlaatconstructie 1" in verdeling
    assert "orientatie" not in verdeling
    # En meteen de getalcongruentie: een eindknoop is er een, geen "1 eindknopen".
    assert "1 eindknoop;" in verdeling
    assert "de overige 1 loopt dood" in verdeling


def test_orientatie_aspecten_zijn_geen_knoop_in_de_netwerkgraaf() -> None:
    """Elke graafknoop is een beheerobject, niet het aspect waar zijn rol op hangt.

    De lader neemt als knoop het subject dat de orientatie via hasAspect draagt.
    Deze test legt dat vast, zodat een latere wijziging in `_read_nodes()` niet
    stilzwijgend aspecten de graaf in laat lopen.
    """
    dataset = load_dataset(TTL_DIR / "net001_bouwwerk_eindknoop.ttl")
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
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl")
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
    dataset = load_dataset(TTL_DIR / "net001_geen_afvoerpad.ttl")
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
