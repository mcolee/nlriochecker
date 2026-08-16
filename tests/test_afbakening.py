"""Tests voor de afbakening tot een studiegebied.

De vraag die deze tests beantwoorden: krimpt de analyseset genoeg om tijd te
schelen, en groeit hij genoeg om de netwerkchecks hun antwoord te laten houden?
"""

from __future__ import annotations

from pathlib import Path

from gwswpijplijn.afbakening import bouw_analyseset, objecten_in_gebied
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import CheckContext, run_checks
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.studiegebied import load_study_area

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


def test_objecten_in_gebied_blijft_importeerbaar_uit_checks() -> None:
    """De functie is verhuisd; bestaande importen mogen niet breken."""
    from gwswpijplijn.checks import objecten_in_gebied as via_checks

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
