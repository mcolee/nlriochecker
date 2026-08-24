"""Tests voor de opgebouwde GWSW-symbologie van de twee objectlagen.

Wat hier staat is te toetsen zonder QGIS: de structuur van de QML, de dekking van de
symbolentabel en de belofte dat de kleur alleen van de status komt.
`tests/test_uitvoer_qgis.py` doet de andere helft -- of QGIS het ook werkelijk laadt.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from nlriochecker.dataset import load_dataset
from nlriochecker.uitvoer.objectkaart import STATUSSEN
from nlriochecker.uitvoer.stijlen.symbolen import (
    LIJNSYMBOLEN,
    MECHANISCHE_LIJNEN,
    PIJLKLEUR_TEGEN,
    PUNTSYMBOLEN,
    STATUSKLEUR,
    bouw_qml,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
STIJLEN = Path(__file__).resolve().parents[1] / "src" / "nlriochecker" / "uitvoer" / "stijlen"


@pytest.fixture(params=["putten", "strengen"])
def laag(request: pytest.FixtureRequest) -> str:
    """De twee objectlagen met een opgebouwde stijl."""
    return str(request.param)


def _boom(laag: str) -> ET.Element:
    return ET.fromstring(bouw_qml(laag))


def test_alleen_de_voorkomende_typen_krijgen_een_regel(laag: str) -> None:
    """De stijl reist mee in het bestand en hoeft alleen te dragen wat erin staat.

    Met de volledige tabel krijgt de lagenboom van QGIS ruim tweehonderd legendaregels
    op een laag met een handvol typen; dat is geen legenda meer maar een muur.
    """
    tabel = PUNTSYMBOLEN if laag == "putten" else LIJNSYMBOLEN
    aanwezig = sorted(tabel)[:2]

    boom = ET.fromstring(bouw_qml(laag, aanwezig))
    labels = {regel.get("label") for regel in boom.iter("rule") if list(regel)}

    assert labels == {*aanwezig, "objecttype niet in de symbolentabel"}


def test_een_afwijkende_schrijfwijze_krijgt_toch_zijn_eigen_regel() -> None:
    """De export schrijft `DwaPerceelaansluitleiding`, de tabel de SLD-schrijfwijze."""
    boom = ET.fromstring(bouw_qml("strengen", ["dwaperceelaansluitleiding"]))
    labels = {regel.get("label") for regel in boom.iter("rule") if list(regel)}

    assert "DwaPerceelaansluitleiding" in labels


def test_de_qml_is_geldige_xml(laag: str) -> None:
    assert _boom(laag).tag == "qgis"


def test_elke_regel_verwijst_naar_een_bestaand_symbool(laag: str) -> None:
    """Een regel zonder symbool tekent niets, zonder dat QGIS iets meldt."""
    boom = _boom(laag)
    namen = {symbool.get("name") for symbool in boom.iter("symbol") if symbool.get("type")}
    verwijzingen = {
        regel.get("symbol") for regel in boom.iter("rule") if regel.get("symbol") is not None
    }

    assert verwijzingen
    assert verwijzingen <= namen


def test_elk_objecttype_heeft_een_regel_per_status(laag: str) -> None:
    """Regelstructuur objecttype x status; een ontbrekende status tekent niets.

    De filters worden bij naam vergeleken en niet alleen geteld: vier verschillende
    filters op `'blauw'` zouden een telling ook halen.
    """
    tabel = PUNTSYMBOLEN if laag == "putten" else LIJNSYMBOLEN
    boom = _boom(laag)
    verwacht = {f"\"status\" = '{status}'" for status in STATUSSEN}

    ouders = [regel for regel in boom.iter("rule") if list(regel)]
    assert len(ouders) == len(tabel) + 1, "elk type plus een vangnet"
    for ouder in ouders:
        filters = {kind.get("filter", "") for kind in ouder}
        assert verwacht <= filters
        # En een vangnet, zodat een onbekende statuswaarde niet onzichtbaar wordt.
        assert any("not in" in uitdrukking for uitdrukking in filters)


def test_een_onbekende_status_wordt_niet_stil_overgeslagen(laag: str) -> None:
    """Zonder vangnet raakt een object met een lege of onbekende status geen regel."""
    filters = [regel.get("filter", "") for regel in _boom(laag).iter("rule")]
    vangnetten = [f for f in filters if f.startswith('"status" not in')]

    assert vangnetten
    assert all('"status" is null' in f for f in vangnetten)


def test_er_is_een_expliciet_vangnet(laag: str) -> None:
    """Een onbekend objecttype moet als onbekend te zien zijn, niet stil als put."""
    labels = {regel.get("label") for regel in _boom(laag).iter("rule")}

    assert "objecttype niet in de symbolentabel" in labels


def test_alleen_de_status_bepaalt_de_kleur(laag: str) -> None:
    """De symboolkleur volgt uitsluitend `status`; het symbool zegt wat het object is."""
    boom = _boom(laag)
    sleutel = "color" if laag == "putten" else "line_color"
    kleuren = {prop.get("v") for prop in boom.iter("prop") if prop.get("k") == sleutel}
    toegestaan = {f"{waarde},255" for waarde in STATUSKLEUR.values()}
    # De richtingpijlen op de strengenlaag hebben hun eigen kleur; die staan onder
    # `color` van een markerlaag, niet onder `line_color`.
    assert kleuren <= toegestaan


def test_de_pijl_bij_tegen_is_rood_en_gedraaid() -> None:
    """Een rode pijl in de BOB-vervalrichting; de dubbele pijl van voorheen vervalt."""
    boom = _boom("strengen")
    tegen = next(
        regel for regel in boom.iter("rule") if regel.get("filter", "").endswith("'tegen'")
    )
    naam = tegen.get("symbol")
    symbool = next(s for s in boom.iter("symbol") if s.get("name") == naam)

    markers = [laag for laag in symbool.iter("layer") if laag.get("class") == "SimpleMarker"]
    assert len(markers) == 1, "een pijl, niet twee"
    props = {prop.get("k"): prop.get("v") for prop in markers[0].iter("prop")}
    assert props["color"] == f"{PIJLKLEUR_TEGEN},255"
    assert props["angle"] == "180"


def test_de_pijl_bij_mee_wijst_met_de_lijn_mee() -> None:
    boom = _boom("strengen")
    mee = next(regel for regel in boom.iter("rule") if regel.get("filter", "").endswith("'mee'"))
    symbool = next(s for s in boom.iter("symbol") if s.get("name") == mee.get("symbol"))
    props = {prop.get("k"): prop.get("v") for prop in symbool.iter("prop")}

    assert props["angle"] == "0"


def test_de_qml_verwijst_niet_naar_een_bestand_of_een_url(laag: str) -> None:
    """Een stijl in `layer_styles` moet zelfstandig reizen."""
    tekst = bouw_qml(laag)

    assert "http://" not in tekst and "https://" not in tekst
    assert ".svg" not in tekst and ".png" not in tekst


def test_de_maptip_toont_de_voorgebakken_kolom(laag: str) -> None:
    boom = _boom(laag)
    maptip = boom.find("mapTip")

    assert maptip is not None and maptip.get("enabled") == "1"
    assert maptip.text is not None
    assert '[% "popup_html" %]' in maptip.text


def test_de_stijlcategorieen_noemen_de_maptip(laag: str) -> None:
    """Zonder `MapTips` leest QGIS het element niet terug en blijft de popup leeg."""
    assert "MapTips" in (_boom(laag).get("styleCategories") or "")


def test_de_opbouw_is_deterministisch(laag: str) -> None:
    """Twee runs op dezelfde data horen dezelfde GeoPackage op te leveren."""
    assert bouw_qml(laag) == bouw_qml(laag)


def test_de_vlaklagen_blijven_gewone_bestanden() -> None:
    """De vlaklagen dragen een bestand-QML; alleen de twee objectlagen zijn opgebouwd.

    Bouwwerken en waterdelen hebben een enkele symbologie, en de stelsellaag (#25) een
    rule-based stijl op `bereikt_eindpunt`; geen van drie volgt de objecttype x
    status-structuur die `symbolen.py` opbouwt.
    """
    aanwezig = {pad.name for pad in STIJLEN.glob("*.qml")}

    assert aanwezig == {"bouwwerken.qml", "waterdelen_zonder_zinker.qml", "stelsels.qml"}


def test_elk_objecttype_in_de_voorbeelddataset_staat_in_de_tabel(juinen) -> None:
    """Een type zonder eigen regel valt in het vangnet en is dan niet te herkennen."""
    knopen = {juinen.beheerobjecttype(uri) for uri in juinen.nodes}
    strengen = {juinen.beheerobjecttype(uri) for uri in juinen.conduits}

    assert not knopen - set(PUNTSYMBOLEN)
    assert not strengen - set(LIJNSYMBOLEN)


# De typen die de De Wolden en Hoogeveen-export bevat, geteld op 2026-08-19. Ze staan hier als
# lijst en niet als run over het bestand: dat laden kost ruim drie minuten en 3 GB, en
# deze test hoort in elke suite mee te draaien. Wijzigt de export, dan hoort deze
# lijst mee te wijzigen.
DEWOLDENHOOGEVEEN_KNOPEN = (
    "Inspectieput",
    "Pompunit",
    "T_stuk",
    "Rioolgemaal",
    "Uitlaatconstructie",
    "Overstortput",
    "Afsluitstuk",
    "Lozingsput",
    "Kruisingsput",
    "Stuwput",
    "Ontstoppingsstuk",
    "Drainageput",
    "Kolk",
)
DEWOLDENHOOGEVEEN_STRENGEN = (
    "GemengdRiool",
    "Vuilwaterriool",
    "Hemelwaterriool",
    "Persleiding",
    "Drain",
    "Duiker",
    "Infiltratieriool",
    "Vacuumleiding",
    "Kolkaansluitleiding",
    "DwaPerceelaansluitleiding",
    "Overstortleiding",
    "LozeLeiding",
    "HwaPerceelaansluitleiding",
    "Drukleiding",
    "GemengdePerceelaansluitleiding",
    "Bergbezinkleiding",
)


def test_elk_objecttype_uit_de_wolden_staat_in_de_tabel() -> None:
    """De acceptatie-eis van issue #14, zonder de export te hoeven laden."""
    assert not set(DEWOLDENHOOGEVEEN_KNOPEN) - set(PUNTSYMBOLEN)
    assert not set(DEWOLDENHOOGEVEEN_STRENGEN) - set(LIJNSYMBOLEN)


def test_de_mechanische_lijnen_staan_als_streepjeslijn_in_de_tabel() -> None:
    """`MECHANISCHE_LIJNEN` mag niet van de tabel afdrijven die hij benoemt.

    De set is de expliciete tegenhanger van `[klassen] mechanisch` (issue #56). Wie een
    klasse als mechanisch benoemt maar in de tabel doorgetrokken tekent, laat de twee
    alsnog uiteenlopen; deze test bindt de set aan de streepjeslijn in de tabel.
    """
    for naam in MECHANISCHE_LIJNEN:
        assert naam in LIJNSYMBOLEN, f"{naam} staat niet in LIJNSYMBOLEN"
        assert "dash" in LIJNSYMBOLEN[naam].streep, f"{naam} is geen streepjeslijn"

    # En de andere richting, zodat een nieuwe mechanische klasse die als streepjeslijn
    # wordt toegevoegd maar `MECHANISCHE_LIJNEN` mist niet stil het gat van #56 heropent.
    # `Zinker` is de enige uitzondering: streepjeslijn maar vrijverval, geen mechanisch riool.
    gestreept = {naam for naam, sym in LIJNSYMBOLEN.items() if sym.streep == "dash"}
    assert gestreept - MECHANISCHE_LIJNEN == {"Zinker"}, (
        f"streepjeslijnen zonder mechanisch-etiket: {sorted(gestreept - MECHANISCHE_LIJNEN)}"
    )


def test_de_filters_zijn_hoofdletterongevoelig() -> None:
    """De export schrijft `DwaPerceelaansluitleiding`, de SLD `DWAPerceelaansluitleiding`."""
    filters = [regel.get("filter", "") for regel in _boom("strengen").iter("rule")]

    assert any('lower("objecttype")' in uitdrukking for uitdrukking in filters)
    assert not any("'DwaPerceelaansluitleiding'" in uitdrukking for uitdrukking in filters)


def test_een_type_met_een_afwijkende_schrijfwijze_valt_niet_in_het_vangnet(
    tmp_path: Path,
) -> None:
    """Regressie op de hoofdletterval: een filter dat niet matcht tekent het vangnet."""
    import sqlite3
    from datetime import date

    from nlriochecker.checkconfig import load_check_config
    from nlriochecker.checks import CheckContext, run_checks
    from nlriochecker.uitvoer.gpkg import schrijf_geopackage
    from nlriochecker.uitvoer.melding import bouw_meldingen

    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config))
    pad = schrijf_geopackage(
        run, bouw_meldingen(run, date(2026, 8, 19)), tmp_path, date(2026, 8, 19)
    )

    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        soorten = {rij[0] for rij in verbinding.execute("select objecttype from strengen")}
    finally:
        verbinding.close()

    assert soorten <= set(LIJNSYMBOLEN), f"zonder regel: {soorten - set(LIJNSYMBOLEN)}"
