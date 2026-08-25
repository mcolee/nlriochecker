"""Tests voor de afbakening tot een studiegebied.

De vraag die deze tests beantwoorden: krimpt de analyseset genoeg om tijd te
schelen, en groeit hij genoeg om de netwerkchecks hun antwoord te laten houden?
"""

from __future__ import annotations

from pathlib import Path

from nlriochecker.afbakening import (
    _component,
    bouw_analyseset,
    bouw_gedeelde_index,
    objecten_in_gebied,
)
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.studiegebied import load_study_area

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"


def _labels(dataset, uris) -> set[str]:
    """De labels van een verzameling URI's."""
    alles = {**dataset.nodes, **dataset.conduits}
    return {alles[uri].label for uri in uris if uri in alles}


def _opzet():
    """De fixture, het gebied en de config."""
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return dataset, area, config


def test_de_kern_is_wat_het_gebied_raakt() -> None:
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert _labels(dataset, analyseset.kern) == {"A", "B", "A-B", "B-C"}


def test_de_schil_haalt_het_afvoerpad_erbij() -> None:
    """Zonder gemaal G zou NET-001 de hele streng als doodlopend melden."""
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert {"C", "D", "G", "C-D", "D-G"} <= _labels(dataset, analyseset.schil)


def test_een_losstaand_net_blijft_buiten_de_analyseset() -> None:
    """Anders levert de afbakening geen tijdwinst op."""
    dataset, area, config = _opzet()

    analyseset = bouw_analyseset(dataset, area, config)

    assert not {"E", "F", "E-F"} & _labels(dataset, analyseset.alles)
    assert set(analyseset.dataset.nodes) | set(analyseset.dataset.conduits) == analyseset.alles


def test_zonder_schil_geeft_net001_een_valse_bevinding() -> None:
    """De reden van bestaan van de contextschil, in een enkele test."""
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    alleen_kern = run_checks(
        CheckContext(dataset=dataset.subset(analyseset.kern), config=config), ["NET-001"]
    )
    met_schil = run_checks(CheckContext(dataset=analyseset.dataset, config=config), ["NET-001"])

    assert alleen_kern.outcomes[0].findings, "zonder schil hoort NET-001 juist aan te slaan"
    assert met_schil.outcomes[0].findings == []


def test_de_schil_haalt_de_route_door_het_persnet_erbij() -> None:
    """De gelijkwaardigheidseis van BO-12 houdt ook als de route gepompt is (BO-56).

    Sinds issue #72 loopt de bereikbaarheid van NET-001/NET-002 door het mechanische
    riool, en sinds issue #73 is een pompput zelf geen eindpunt meer. Bakende de
    contextschil zich alleen op de vrijvervalcomponent af, dan valt het gemaal achter
    de persleiding buiten de analyseset en meldt een gebiedsrun een streng die de
    gemeentebrede run niet meldt.

    De fixture zet dat gemaal achter twee drukleidingen op 450 m van de kern, ver
    buiten de contextbuffer van 50 m, zodat het alleen via de mechanische kanten mee
    kan komen. De tweede helft is de controle: zonder schil slaat NET-001 wel aan.
    """
    dataset = load_dataset(TTL_DIR / "afbakening_persnet.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    analyseset = bouw_analyseset(dataset, area, config)

    assert {"G", "d2"} <= _labels(dataset, analyseset.schil)

    alleen_kern = run_checks(
        CheckContext(dataset=dataset.subset(analyseset.kern), config=config), ["NET-001"]
    )
    met_schil = run_checks(CheckContext(dataset=analyseset.dataset, config=config), ["NET-001"])
    volledig = run_checks(CheckContext(dataset=dataset, config=config), ["NET-001"])

    assert alleen_kern.outcomes[0].findings, "zonder schil hoort NET-001 juist aan te slaan"
    assert met_schil.outcomes[0].findings == volledig.outcomes[0].findings == []


def test_de_buffer_haalt_ongekoppelde_buren_erbij() -> None:
    """TOP-005 en de EXT-checks kijken naar nabijheid zonder netwerkverband.

    Put H heeft geen enkele streng en kan dus nooit via de component meekomen: dit
    bewijst wat de buffer toevoegt, niet wat de component al zou leveren. Met
    context_buffer_m = 60 (H ligt 5 meter buiten het gebied) hoort hij erbij, met
    context_buffer_m = 0 juist niet.
    """
    dataset = load_dataset(TTL_DIR / "afbakening_buffer_los_object.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    config.studiegebied.context_buffer_m = 60.0
    met_buffer = bouw_analyseset(dataset, area, config)
    assert "H" in _labels(dataset, met_buffer.alles)

    config.studiegebied.context_buffer_m = 0.0
    zonder_buffer = bouw_analyseset(dataset, area, config)
    assert "H" not in _labels(dataset, zonder_buffer.alles)


def test_streng_via_compartiment_zonder_geometrie_houdt_haar_netwerkverband() -> None:
    """Een compartiment zonder geometrie moet in de analyseset terechtkomen.

    De streng A-B koppelt aan de orientatie van compartiment Comp1, dat via
    hasPart bij put A hoort maar zelf geen punt heeft. Kern en schil bestonden tot
    de reparatie alleen uit objecten met geometrie en de knoop waar de
    componentberekening op uitkomt (put A); Comp1 viel daar tussenuit, en
    `resolve_network_node` gaf op de uitgedunde dataset dan None terug in plaats
    van put A -- de streng zou ten onrechte als niet aangesloten tellen.
    """
    dataset = load_dataset(TTL_DIR / "afbakening_compartiment_zonder_geometrie.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    analyseset = bouw_analyseset(dataset, area, config)
    comp_uri = _uri_van(dataset, "Comp1")

    assert comp_uri in analyseset.alles

    resolved = analyseset.dataset.resolve_network_node(comp_uri, config.klassen.netwerkknopen)
    assert resolved == _uri_van(dataset, "A")


def test_objecten_in_gebied_blijft_importeerbaar_uit_checks() -> None:
    """De functie is verhuisd; bestaande importen mogen niet breken."""
    from nlriochecker.checks import objecten_in_gebied as via_checks

    assert via_checks is objecten_in_gebied


def test_evenwijdige_strengen_vallen_geen_van_beide_buiten_de_schil() -> None:
    """Twee vuilwaterstrengen tussen hetzelfde knopenpaar horen er allebei bij.

    Een gewone nx.Graph onthoudt van twee kanten tussen hetzelfde knopenpaar alleen de
    laatst toegevoegde; zonder correctie valt een van de twee evenwijdige strengen
    stilzwijgend buiten de analyseset, terwijl allebei in dezelfde component zitten
    als de kern (put A).
    """
    dataset = load_dataset(TTL_DIR / "afbakening_parallelle_strengen.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    analyseset = bouw_analyseset(dataset, area, config)

    assert {"M-N-1", "M-N-2"} <= _labels(dataset, analyseset.schil)


def test_streng_met_los_uiteinde_telt_mee_maar_verdwijnt_niet_ongemerkt() -> None:
    """Een streng die nergens op uitkomt, mag niet zomaar uit beeld verdwijnen.

    _component slaat zo'n streng terecht over (net als `_bouw_netwerk` in
    checks/netwerk.py, die hem in `unconnected` zet), maar het aantal moet
    zichtbaar blijven in plaats van stilzwijgend te verdwijnen.
    """
    dataset = load_dataset(TTL_DIR / "afbakening_los_uiteinde.ttl")
    area = load_study_area(GIS_DIR / "afbakening_gebied.geojson")
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    analyseset = bouw_analyseset(dataset, area, config)

    assert analyseset.strengen_zonder_netwerkverband == 1
    assert analyseset.alles == frozenset()


def test_een_dataset_brede_check_ziet_de_hele_export() -> None:
    """ADM-002 zoekt dubbele identificaties; die kunnen overal zitten."""
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    run = run_checks(context, ["ADM-002", "TOP-001"])
    per_check = {outcome.check_id: outcome for outcome in run.outcomes}

    volledig = len(dataset.nodes) + len(dataset.conduits)
    assert per_check["ADM-002"].examined == volledig
    assert per_check["TOP-001"].examined < volledig


def test_een_via_config_aangewezen_check_ziet_ook_de_hele_export() -> None:
    """De configroute moet hetzelfde effect hebben als `Check.volledig_bereik`.

    TOP-001 heeft geen `volledig_bereik` en telt in `examined()` alleen putten met
    geometrie, niet knopen plus strengen -- daarom wordt hier niet tegen
    `len(dataset.nodes) + len(dataset.conduits)` vergeleken (zoals bij ADM-002 in
    `test_een_dataset_brede_check_ziet_de_hele_export`), maar tegen wat TOP-001
    zelf op de volledige export telt.
    """
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    smal = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config, analyseset=analyseset),
        ["TOP-001"],
    )

    config.studiegebied.volledige_dataset_checks = ["TOP-001"]
    breed = run_checks(
        CheckContext(
            dataset=analyseset.dataset,
            config=config,
            volledige_dataset=dataset,
            analyseset=analyseset,
        ),
        ["TOP-001"],
    )
    referentie = run_checks(CheckContext(dataset=dataset, config=config), ["TOP-001"])

    assert breed.outcomes[0].examined > smal.outcomes[0].examined
    assert breed.outcomes[0].examined == referentie.outcomes[0].examined


def test_de_run_onthoudt_de_omvang_van_kern_en_schil() -> None:
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)

    run = run_checks(
        CheckContext(dataset=analyseset.dataset, config=config, analyseset=analyseset),
        ["TOP-001"],
    )

    assert run.analyseset is analyseset


def _uri_van(dataset, label: str) -> str:
    """De URI van het object met dit label; nodig om iets buiten de kern te pakken."""
    alles = {**dataset.nodes, **dataset.conduits}
    return next(uri for uri, object_ in alles.items() if object_.label == label)


def test_karakteristiek_en_typeringstelling_blijven_over_de_volledige_export() -> None:
    """Het rapport belooft dat deze getallen niet met de afbakening meebewegen.

    Put E hoort bij het losstaande netje dat buiten de analyseset valt (zie
    `test_een_losstaand_net_blijft_buiten_de_analyseset`). Zonder de reparatie zou
    `matched_objects()` hem missen zodra er een studiegebied is, en zou de
    typeringstelling met en zonder studiegebied uiteenlopen.
    """
    dataset, area, config = _opzet()
    analyseset = bouw_analyseset(dataset, area, config)
    onbetrouwbaar = frozenset({_uri_van(dataset, "E")})

    zonder_gebied = run_checks(
        CheckContext(dataset=dataset, config=config, unreliable_objects=onbetrouwbaar),
        ["TOP-001"],
    )
    met_gebied = run_checks(
        CheckContext(
            dataset=analyseset.dataset,
            config=config,
            unreliable_objects=onbetrouwbaar,
            volledige_dataset=dataset,
            analyseset=analyseset,
        ),
        ["TOP-001"],
    )

    assert met_gebied.karakteristiek == zonder_gebied.karakteristiek
    assert (
        met_gebied.unreliable_labels_in_dataset == zonder_gebied.unreliable_labels_in_dataset == 1
    )


def test_gedeelde_index_geeft_dezelfde_analyseset() -> None:
    """De optimalisatie mag geen enkel object toevoegen of weglaten."""
    dataset, area, config = _opzet()

    zonder = bouw_analyseset(dataset, area, config)
    met = bouw_analyseset(dataset, area, config, gedeeld=bouw_gedeelde_index(dataset, config))

    assert met.kern == zonder.kern
    assert met.schil == zonder.schil
    assert met.strengen_zonder_netwerkverband == zonder.strengen_zonder_netwerkverband


def test_componenten_uit_de_gedeelde_index_gelijk_aan_directe_graafanalyse() -> None:
    """De componentstructuur hangt niet van het gebied af; hoisten mag hem niet raken."""
    dataset, area, config = _opzet()
    kern = objecten_in_gebied(dataset, area)

    via_index = bouw_gedeelde_index(dataset, config).component(kern)
    direct = _component(dataset, config, kern)

    assert via_index == direct


def test_index_levert_dezelfde_kern() -> None:
    dataset, area, config = _opzet()
    index = bouw_gedeelde_index(dataset, config)

    assert objecten_in_gebied(dataset, area, gedeeld=index) == objecten_in_gebied(dataset, area)
