"""Controleert met QGIS zelf dat de stijlen uit het bestand geladen worden.

Deze test is de enige die het echte antwoord geeft op de vraag waar ronde 2 mee
begon: past QGIS de meegeleverde stijlen toe? Hij wordt overgeslagen waar PyQGIS
niet geinstalleerd is, want QGIS is geen afhankelijkheid van dit project.

Deze venv is met `include-system-site-packages = false` gebouwd (zie
`.venv/pyvenv.cfg`), dus een `import qgis.core` faalt hier altijd, ook op een
machine met een werkende systeem-QGIS: PyQGIS staat dan in de site-packages van
de systeem-Python, niet in deze venv. `_voeg_systeem_pyqgis_toe()` plakt die map
daarom vóór de import ACHTERAAN `sys.path`, zodat de nieuwere `pydantic`/
`typing_extensions` uit de venv voorrang houden en alleen de ontbrekende modules
(`qgis`, `PyQt5`, `osgeo`) van het systeem komen. Ontbreekt PyQGIS ook dan nog
(een andere Python-versie, een andere distributie), dan blijft `importorskip`
het vangnet: de test slaat gewoon over in plaats van te crashen.
"""

from __future__ import annotations

import os
import sys
import sysconfig
from datetime import date
from pathlib import Path

import pytest


def _systeem_pyqgis_pad() -> Path | None:
    """Het pad waar de systeem-PyQGIS te vinden is, of None als dat niet lukt.

    `GWSW_QGIS_SITE_PACKAGES` overschrijft het pad voor een machine met een
    andere lay-out. Zonder die variabele wordt het pad afgeleid: het
    `deb_system`-installatieschema van `sysconfig` is het schema dat
    Debian/Ubuntu voor met apt geinstalleerde Python-pakketten gebruikt (zoals
    `python3-qgis`), en levert daarmee het pad zonder dat wij het zelf
    hoeven te verzinnen. Toegepast op `sys.base_prefix` (de Python-installatie
    waar deze venv uit voortkomt), niet op de venv zelf -- anders krijg je een
    pad binnen de venv terug.
    """
    override = os.environ.get("GWSW_QGIS_SITE_PACKAGES")
    if override:
        return Path(override)
    if "deb_system" not in sysconfig.get_scheme_names():
        return None
    basisvars = {"base": sys.base_prefix, "platbase": sys.base_prefix}
    return Path(sysconfig.get_path("purelib", scheme="deb_system", vars=basisvars))


def _voeg_systeem_pyqgis_toe() -> None:
    """Zet de systeem-site-packages achteraan `sys.path`, als ze bestaan."""
    pad = _systeem_pyqgis_pad()
    if pad is not None and pad.is_dir() and str(pad) not in sys.path:
        sys.path.append(str(pad))


_voeg_systeem_pyqgis_toe()

qgis_core = pytest.importorskip("qgis.core", reason="PyQGIS is hier niet geinstalleerd")

from nlriochecker.checkconfig import load_check_config  # noqa: E402
from nlriochecker.checks import CheckContext, run_checks  # noqa: E402
from nlriochecker.dataset import load_dataset  # noqa: E402
from nlriochecker.uitvoer.gpkg import FEATURELAGEN, schrijf_geopackage  # noqa: E402
from nlriochecker.uitvoer.melding import bouw_meldingen  # noqa: E402

pytestmark = pytest.mark.qgis

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
RUNDATUM = date(2026, 8, 16)


@pytest.fixture(scope="module")
def qgis_app():
    """Een QGIS-toepassing zonder scherm, een keer per module."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    qgis_core.QgsApplication.setPrefixPath("/usr", True)
    app = qgis_core.QgsApplication([], False)
    app.initQgis()
    yield app
    app.exitQgis()


@pytest.fixture(scope="module")
def geschreven_gpkg(tmp_path_factory) -> Path:
    """Een GeoPackage van de mechanische fixture, met alle vier de lagen."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config))
    map_ = tmp_path_factory.mktemp("qgis")
    return schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), map_, RUNDATUM)


@pytest.mark.parametrize("laag", FEATURELAGEN)
def test_qgis_laadt_de_stijl_uit_het_bestand(qgis_app, geschreven_gpkg: Path, laag: str) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")

    assert vector.isValid(), f"laag {laag} is niet leesbaar"
    boodschap, gelukt = vector.loadDefaultStyle()

    assert gelukt, f"QGIS past de stijl van {laag} niet toe: {boodschap}"
    assert "Provider" in boodschap


def test_qgis_leest_de_symbolentabel_terug_zoals_ze_bedoeld_is(
    qgis_app, geschreven_gpkg: Path
) -> None:
    """Een onbekende markervorm wordt door QGIS stil een cirkel.

    De opgebouwde stijl noemt vormen als `octagon` en `cross2` bij naam. Staat daar een
    tikfout in, dan tekent QGIS zonder morren een cirkel en ziet niemand dat het
    GWSW-symbool weg is. Deze test laat QGIS de vorm terugcoderen en vergelijkt hem met
    de tabel.
    """
    from nlriochecker.uitvoer.stijlen.symbolen import PUNTSYMBOLEN, VANGNET_PUNT

    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=putten", "p", "ogr")
    vector.loadDefaultStyle()

    gevonden = set()
    for regel in vector.renderer().rootRule().children():
        for kind in regel.children():
            for symboollaag in kind.symbol().symbolLayers():
                gevonden.add(
                    qgis_core.QgsSimpleMarkerSymbolLayerBase.encodeShape(symboollaag.shape())
                )

    # De stijl draagt alleen regels voor de typen die in deze laag staan, plus het
    # vangnet; de vormen die QGIS teruggeeft horen daar precies bij te horen.
    aanwezig = {
        kenmerk["objecttype"]
        for kenmerk in vector.getFeatures()  # type: ignore[index]
    }
    bedoeld = {PUNTSYMBOLEN[naam].vorm for naam in aanwezig if naam in PUNTSYMBOLEN}
    bedoeld.add(VANGNET_PUNT.vorm)

    assert aanwezig, "de fixture levert geen putten op"
    assert gevonden == bedoeld


def test_de_legenda_blijft_hanteerbaar(qgis_app, geschreven_gpkg: Path) -> None:
    """De lagenboom van QGIS toont een regel per bladregel van de renderer.

    Met de volledige symbolentabel zijn dat er ruim tweehonderd per laag, op een
    bestand met een handvol objecttypen. Dat is geen legenda meer maar een muur, en
    het is precies wat een blik op het scherm zou hebben laten zien. De stijl draagt
    daarom alleen regels voor de typen die in de laag staan; deze test legt vast dat
    de legenda meeschaalt met de data en niet met de tabel.
    """
    for laag in ("putten", "strengen"):
        vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")
        vector.loadDefaultStyle()
        soorten = {kenmerk["objecttype"] for kenmerk in vector.getFeatures()}  # type: ignore[index]

        regels = len(vector.renderer().legendSymbolItems())

        # Per objecttype vijf statusregels plus het vangnet, en bij de strengen drie
        # richtingsregels. Ruim genomen, maar ver onder de tweehonderd.
        assert regels <= (len(soorten) + 1) * 6 + 5, f"{laag}: {regels} legendaregels"


def test_de_maptip_van_beide_objectlagen_toont_de_popup(qgis_app, geschreven_gpkg: Path) -> None:
    """De maptip moet uit `layer_styles` mee terugkomen, niet alleen in de QML staan."""
    for laag in ("putten", "strengen"):
        vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")
        boodschap, gelukt = vector.loadDefaultStyle()

        assert gelukt, f"{laag}: {boodschap}"
        assert '[% "popup_html" %]' in vector.mapTipTemplate(), laag
        assert "<style>" in vector.mapTipTemplate(), laag


def test_de_maptipexpressie_levert_de_popup_van_het_object(qgis_app, geschreven_gpkg: Path) -> None:
    """Niet alleen de tekst, maar de uitkomst: de expressie moet echt HTML opleveren."""
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=strengen", "s", "ogr")
    vector.loadDefaultStyle()
    feature = next(vector.getFeatures())

    context = qgis_core.QgsExpressionContext()
    context.appendScopes(qgis_core.QgsExpressionContextUtils.globalProjectLayerScopes(vector))
    context.setFeature(feature)
    gerenderd = qgis_core.QgsExpression.replaceExpressionText(vector.mapTipTemplate(), context)

    assert "gwsw-popup" in gerenderd
    assert "[%" not in gerenderd


def test_de_stijl_van_de_strengen_kent_de_richtingsregels(qgis_app, geschreven_gpkg: Path) -> None:
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=strengen", "s", "ogr")
    vector.loadDefaultStyle()

    labels = {regel.label() for regel in vector.renderer().rootRule().children()}

    assert {
        "BOB volgt de lijnrichting",
        "BOB tegen de lijnrichting in",
        "BOB-richting niet te bepalen",
    } <= labels


def _renderer_symbolen(renderer):
    """De symbolen van een renderer, met regels (rule-based) of zonder (simpel).

    De stapelverspringing van meldinglocaties (`stapel_nr`) zit niet in een
    filter of regelexpressie, maar als data-defined property op een
    symboollaag; die moet hier ook uitkomen, anders mist de test precies de
    plek waar een tikfout markeringen stil op 0,0 laat stapelen.
    """
    if hasattr(renderer, "rootRule"):
        return [
            regel.symbol() for regel in renderer.rootRule().children() if regel.symbol() is not None
        ]
    if hasattr(renderer, "symbol"):
        symbool = renderer.symbol()
        return [symbool] if symbool is not None else []
    return []


def test_elke_stijlexpressie_verwijst_naar_bestaande_kolommen(
    qgis_app, geschreven_gpkg: Path
) -> None:
    """Een tikfout in een kolomnaam levert een lege kaart op, geen foutmelding."""
    for laag in FEATURELAGEN:
        vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername={laag}", laag, "ogr")
        vector.loadDefaultStyle()
        velden = set(vector.fields().names())
        renderer = vector.renderer()
        expressies = [renderer.filter()] if hasattr(renderer, "filter") else []
        if hasattr(renderer, "rootRule"):
            expressies += [regel.filterExpression() for regel in renderer.rootRule().children()]
        for symbool in _renderer_symbolen(renderer):
            for symboollaag in symbool.symbolLayers():
                eigenschappen = symboollaag.dataDefinedProperties()
                expressies += [
                    eigenschappen.property(sleutel).expressionString()
                    for sleutel in eigenschappen.propertyKeys()
                ]
        for tekst in filter(None, expressies):
            gebruikt = set(qgis_core.QgsExpression(tekst).referencedColumns())
            assert gebruikt <= velden, f"{laag}: {tekst} verwijst naar {gebruikt - velden}"
