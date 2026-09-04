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
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from shapely.geometry import Point, box


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

from gwsw_orox_helpers.dataset import load_dataset  # noqa: E402

from nlriochecker.checkconfig import load_check_config  # noqa: E402
from nlriochecker.checks import CheckContext, run_checks  # noqa: E402
from nlriochecker.checks.treffers import Wegvakoordeel, Wegvakregister  # noqa: E402
from nlriochecker.uitvoer.gpkg import FEATURELAGEN, schrijf_geopackage  # noqa: E402
from nlriochecker.uitvoer.melding import bouw_meldingenstroom  # noqa: E402
from test_uitvoer_symbolen import VLAKKEN_LEGENDA  # noqa: E402

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
    """Een GeoPackage van de mechanische fixture, met alle drie de lagen."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl", [])
    run = run_checks(CheckContext(dataset=dataset, config=config))
    map_ = tmp_path_factory.mktemp("qgis")
    stroom = bouw_meldingenstroom(run, RUNDATUM)
    return schrijf_geopackage(run, stroom.meldingen, map_, RUNDATUM, feiten=stroom.feiten)


@pytest.fixture(scope="module")
def gpkg_met_deelstelselvlak(tmp_path_factory) -> Path:
    """Een GeoPackage met een RVZ-006-deelstelselvlak in de laag `vlakken` (issue #98)."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl", [])
    run = run_checks(CheckContext(dataset=dataset, config=config), ["RVZ-006"])
    map_ = tmp_path_factory.mktemp("qgis_vlak")
    stroom = bouw_meldingenstroom(run, RUNDATUM)
    return schrijf_geopackage(run, stroom.meldingen, map_, RUNDATUM, feiten=stroom.feiten)


@pytest.fixture(scope="module")
def gpkg_met_wegvakken(tmp_path_factory) -> Path:
    """Een GeoPackage met een groen en een grijs EXT-009-wegvak in `vlakken`.

    Het wegvakregister wordt hier met de hand gevuld in plaats van door EXT-009: die
    check heeft de externe GIS-bronnen nodig, en dat is voor een stijltest een dure
    omweg -- de rij die de schrijver ervan maakt is dezelfde. Een rood wegvak zit er
    niet in: rood krijgt alleen een rij als er een EXT-009-melding naar wijst.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "mechanisch_riool.ttl", [])
    run = run_checks(CheckContext(dataset=dataset, config=config))
    register = Wegvakregister()
    for nummer, (straat, status, reden) in enumerate(
        (("Rioolstraat", "groen", ""), ("Grindweg", "grijs", "overwegend onverhard")), start=1
    ):
        register.registreer(
            Wegvakoordeel(
                sleutel=f"nwb:wegvak/{nummer}",
                straat=straat,
                plaats="Fixturekom",
                status=status,
                reden=reden,
                straatlengte_m=100.0,
                streng_in_cel=0.0,
                aandeel_onverhard=None,
                middelpunt=Point(1010.0 + nummer * 20.0, 2010.0),
                vlak=box(1000.0 + nummer * 20.0, 2000.0, 1020.0 + nummer * 20.0, 2020.0),
                bronbestand="nwb_wegvakken.gpkg",
            )
        )
    met_wegvakken = replace(run, wegvakken=register)
    map_ = tmp_path_factory.mktemp("qgis_wegvak")
    stroom = bouw_meldingenstroom(met_wegvakken, RUNDATUM)
    return schrijf_geopackage(met_wegvakken, stroom.meldingen, map_, RUNDATUM, feiten=stroom.feiten)


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

        # Per objecttype de typeregel plus zes statusregels (vijf statuswaarden en het
        # vangnet, sinds issue #132 met `geaccepteerd` erbij), en bij de strengen drie
        # richtingsregels. Ruim genomen, maar ver onder de tweehonderd.
        assert regels <= (len(soorten) + 1) * 7 + 5, f"{laag}: {regels} legendaregels"


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


def test_de_vlakkenlaag_geeft_elke_check_een_regel(qgis_app, geschreven_gpkg: Path) -> None:
    """De kern van #107: één regel per check, met de checkcode voorop.

    De laag draagt vlakken van vier checks (EXT-001, EXT-003, RVZ-006 en EXT-009) en de
    legenda leest daarmee als de checklijst. Pand en bouwwerk delen hun regel -- ze komen
    van dezelfde check -- en van de wegvakken tekent alleen de rode; groen en grijs
    blijven wel als rij bestaan (BO-85). De regels staan vast in de QML, ook op een lege
    laag.
    """
    vector = qgis_core.QgsVectorLayer(f"{geschreven_gpkg}|layername=vlakken", "v", "ogr")
    boodschap, gelukt = vector.loadDefaultStyle()

    assert gelukt, f"vlakken: {boodschap}"
    labels = [regel.label() for regel in vector.renderer().rootRule().children()]
    assert labels == list(VLAKKEN_LEGENDA)


def test_elke_stijlregel_slaat_aan_op_de_soort_waarvoor_zij_bedoeld_is(
    qgis_app, gpkg_met_wegvakken: Path
) -> None:
    """De vier filters positief getoetst; een filter dat op niets past tekent niets.

    Zonder deze test zou een tikfout in een filterwaarde onopgemerkt blijven: de laag
    wordt er leeg van en QGIS meldt niets. Pand en bouwwerk staan er allebei in omdat
    juist zij sinds issue #107 één regel delen, en het rode wegvak omdat de test hiernaast
    vastlegt dat groen en grijs er géén krijgen.
    """
    vector = qgis_core.QgsVectorLayer(f"{gpkg_met_wegvakken}|layername=vlakken", "v", "ogr")
    boodschap, gelukt = vector.loadDefaultStyle()
    ext001, ext003, rvz006, ext009 = VLAKKEN_LEGENDA

    assert gelukt, f"vlakken: {boodschap}"
    for soort, status, verwacht in (
        ("pand", "", ext001),
        ("bouwwerk", "", ext001),
        ("water", "", ext003),
        ("gemengd_deelstelsel", "", rvz006),
        ("wegvak", "rood", ext009),
    ):
        kenmerk = qgis_core.QgsFeature(vector.fields())
        kenmerk["soort"] = soort
        kenmerk["status"] = status

        assert _regels_voor(vector, kenmerk) == {verwacht}, soort


def test_een_groen_of_grijs_wegvak_blijft_een_rij_maar_krijgt_geen_regel(
    qgis_app, gpkg_met_wegvakken: Path
) -> None:
    """De bewuste afwijking van BO-79, vastgelegd in BO-85.

    De rijen blijven -- dat is de kern van BO-79: in de attributentabel, in een filter en
    in de popup is nog steeds na te gaan of een straat bekeken is. De standaardstijl
    tekent ze alleen niet meer, want met 3593 groene en 23 grijze vlakken over 500 rode
    was de kaart niet te lezen. Het deelstelselvlak uit dezelfde fixture is de controle:
    een rij die wél getekend wordt, zodat "geen regel" hier niet "de hele stijl doet
    niets" kan betekenen.
    """
    vector = qgis_core.QgsVectorLayer(f"{gpkg_met_wegvakken}|layername=vlakken", "v", "ogr")
    boodschap, gelukt = vector.loadDefaultStyle()
    rijen = list(vector.getFeatures())
    wegvakken = [kenmerk for kenmerk in rijen if kenmerk["soort"] == "wegvak"]  # type: ignore[index]

    assert gelukt, f"vlakken: {boodschap}"
    assert len(wegvakken) == 2
    assert {kenmerk["status"] for kenmerk in wegvakken} == {"groen", "grijs"}  # type: ignore[index]
    for kenmerk in wegvakken:
        assert _regels_voor(vector, kenmerk) == set(), kenmerk["status"]  # type: ignore[index]

    gemengd = [
        kenmerk
        for kenmerk in rijen
        if kenmerk["soort"] == "gemengd_deelstelsel"  # type: ignore[index]
    ]

    assert gemengd, "de fixture levert geen deelstelselvlak als controle"
    for kenmerk in gemengd:
        assert _regels_voor(vector, kenmerk) == {"RVZ-006 - Gemengd stelsel zonder overstort"}


def test_de_maptip_van_een_deelstelselvlak_toont_de_voorgebakken_popup(
    qgis_app, gpkg_met_deelstelselvlak: Path
) -> None:
    """QGIS kent één maptip per laag; de expressie kiest per rij welke tekst hij toont.

    Een gemengd deelstelsel draagt zijn popup voorgebakken in `popup_html` -- inclusief de
    systemische meldingen (BO-59) -- en die hoort de maptip dan te tonen. Klopt de
    expressie niet, dan blijft er een `[%`-fragment in de uitkomst staan.
    """
    vector = qgis_core.QgsVectorLayer(f"{gpkg_met_deelstelselvlak}|layername=vlakken", "v", "ogr")
    vector.loadDefaultStyle()
    feature = next(vector.getFeatures())

    gerenderd = _maptip(vector, feature)

    assert "gwsw-popup" in gerenderd
    assert "RVZ-006" in gerenderd
    assert "[%" not in gerenderd


def test_de_maptip_van_een_extern_vlak_stelt_zijn_tekst_uit_de_kolommen_samen(
    qgis_app, gpkg_met_deelstelselvlak: Path
) -> None:
    """De andere tak van diezelfde expressie: een vlak zonder voorgebakken popup.

    Een extern vlak (pand, bouwwerk, water) laat `popup_html` leeg en krijgt zijn tekst
    uit de kolommen. De rij is hier met de hand samengesteld, zodat deze tak ook getoetst
    wordt op een machine zonder de GIS-fixtures van de EXT-checks.
    """
    vector = qgis_core.QgsVectorLayer(f"{gpkg_met_deelstelselvlak}|layername=vlakken", "v", "ogr")
    vector.loadDefaultStyle()
    feature = qgis_core.QgsFeature(vector.fields())
    for veld, waarde in (
        ("soort", "pand"),
        ("label", "pand pand-1"),
        ("subtype", "woonfunctie"),
        ("relatie", "binnen"),
        ("afstand_min_m", 0.0),
        ("aantal_meldingen", 4),
        ("check_ids", "EXT-001"),
        ("bronbestand", "bgt.gpkg"),
        ("popup_html", ""),
    ):
        feature[veld] = waarde

    gerenderd = _maptip(vector, feature)

    assert "pand pand-1" in gerenderd
    assert "woonfunctie" in gerenderd
    assert "binnen" in gerenderd
    assert "4 melding(en)" in gerenderd
    assert "EXT-001" in gerenderd
    assert "bgt.gpkg" in gerenderd
    assert "[%" not in gerenderd


def _maptip(vector, feature) -> str:
    """De maptip van een laag, uitgerekend voor een enkele rij."""
    context = qgis_core.QgsExpressionContext()
    context.appendScopes(qgis_core.QgsExpressionContextUtils.globalProjectLayerScopes(vector))
    context.setFeature(feature)
    return qgis_core.QgsExpression.replaceExpressionText(vector.mapTipTemplate(), context)


def _regels_voor(vector, feature) -> set[str]:
    """De labels van de stijlregels waarvan het filter op deze rij aanslaat.

    Een lege verzameling betekent dat QGIS de rij niet tekent: een regelgebaseerde
    renderer laat een object waarop geen enkel filter past ongemoeid. Een filter dat niet
    te ontleden is of op deze rij niet uit te rekenen valt, levert stil NULL op en zou dan
    niet van "bewust niet getekend" te onderscheiden zijn; daarom faalt dat hier luid.
    """
    context = qgis_core.QgsExpressionContext()
    context.appendScopes(qgis_core.QgsExpressionContextUtils.globalProjectLayerScopes(vector))
    context.setFeature(feature)
    labels = set()
    for regel in vector.renderer().rootRule().children():
        expressie = qgis_core.QgsExpression(regel.filterExpression())
        assert not expressie.hasParserError(), f"{regel.label()}: {expressie.parserErrorString()}"
        uitkomst = expressie.evaluate(context)
        assert not expressie.hasEvalError(), f"{regel.label()}: {expressie.evalErrorString()}"
        if uitkomst:
            labels.add(regel.label())
    return labels


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
