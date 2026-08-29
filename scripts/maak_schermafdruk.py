#!/usr/bin/env python
"""Rendert de twee schermafdrukken in `docs/img/` uit de uitvoer van de voorbeeldrun.

De GeoPackage is het overtuigendste product van `toets` en in een README onzichtbaar
zonder plaatje. Dit script maakt er twee, allebei uit `uitvoer/voorbeeld/` -- de run op
het getrackte voorbeeld `voorbeelden/koekangerveld/`. Er wordt niets met de hand
getekend: de stijl komt uit `layer_styles` van de GeoPackage zelf en de teksten uit de
geschreven bestanden, zodat een gewijzigde stijl of een gewijzigd rapport vanzelf een
nieuw plaatje oplevert.

1. **`kaart-koekangerveld.png`** -- de drie featurelagen (`putten`, `strengen`,
   `vlakken`) met hun eigen stijl, op de extent van het studiegebied, met linksboven een
   legenda en rechtsonder een voorbeeldpopup.

   De legenda is met opzet niet die van QGIS zelf: `QgsLegendRenderer` zet elke bladregel
   van de renderers neer en dat zijn er hier 73 (36 putten, 33 strengen, 4 vlakken), want
   het symbool volgt het GWSW-objecttype. Dat is een muur en geen legenda. Wat de kaart
   leesbaar maakt is de kleur, en die volgt uitsluitend de kolom `status` (BO-30). De
   legenda toont daarom de vier statuskleuren -- uit `STATUSKLEUR` en `STATUS_WOORD`, dus
   uit dezelfde tabel waarmee de stijl gebouwd is -- plus de vier regels van de
   vlakkenlaag, die wel uit de renderer van die laag zelf komen.

2. **`rapport-kop.png`** -- de kop van `bevindingen.md`, van de titel tot en met de
   managementsamenvatting, gerenderd als Markdown met `QTextDocument`. Het blok met de
   rollen waarop de checks selecteren (een tabel van ruim twintig regels) wordt
   overgeslagen; er staat een zichtbare regel in de plaats, zodat het plaatje niet doet
   alsof het rapport daar niets heeft.

PyQGIS is geen afhankelijkheid van dit project en staat in de site-packages van de
systeem-Python, niet in deze venv; `_voeg_systeem_pyqgis_toe()` plakt die map achteraan
`sys.path`. Dezelfde afleiding als in `tests/test_uitvoer_qgis.py`, met dezelfde
ontsnapping via `GWSW_QGIS_SITE_PACKAGES`. Overgenomen en niet geimporteerd: een script
importeert niet uit de testsuite.

De uitvoer is gegenereerd en wordt nooit met de hand bijgewerkt; zie de tabel
"Gegenereerde bestanden" in `docs/agents/analyse-harness.md`.

Gebruik (de voorbeeldrun staat in `voorbeelden/koekangerveld/README.md`):

    nlriochecker toets --dataset voorbeelden/koekangerveld/koekangerveld_orox.ttl ... \
      --output uitvoer/voorbeeld
    uv run python scripts/maak_schermafdruk.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import sysconfig
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
RUN = WORTEL / "uitvoer" / "voorbeeld"
DOEL = WORTEL / "docs" / "img"

# De kaart op 1600 px breed: leesbaar op GitHub, dat een afbeelding tot de kolombreedte
# terugschaalt. De teksten erop worden in pixels gezet (niet in punten), zodat ze die
# terugschaling overleven.
KAARTBREEDTE = 1600
KAARTMARGE_M = 25.0
TEKSTGROOTTE = 21
LEGENDAREGEL = 34
LEGENDAMARGE = 18
POPUPBREEDTE = 300
POPUPSCHAAL = 1.5

# De rapportkop op zijn natuurlijke grootte: 900 px tekstbreedte leest als een document
# en niet als een uitvergroting.
RAPPORTBREEDTE = 900
RAPPORTMARGE = 12
WEGGELATEN = "*[ tabel met de rollen en klassen waar de checks op selecteren -- ingekort ]*"


def _systeem_pyqgis_pad() -> Path | None:
    """Het pad waar de systeem-PyQGIS te vinden is, of None als dat niet lukt.

    `GWSW_QGIS_SITE_PACKAGES` overschrijft het pad voor een machine met een andere
    lay-out. Zonder die variabele wordt het afgeleid uit het `deb_system`-schema van
    `sysconfig` (het schema waarin Debian en Ubuntu met apt geinstalleerde pakketten als
    `python3-qgis` zetten), toegepast op `sys.base_prefix` en niet op de venv.
    """
    override = os.environ.get("GWSW_QGIS_SITE_PACKAGES")
    if override:
        return Path(override)
    if "deb_system" not in sysconfig.get_scheme_names():
        return None
    basisvars = {"base": sys.base_prefix, "platbase": sys.base_prefix}
    return Path(sysconfig.get_path("purelib", scheme="deb_system", vars=basisvars))


def _voeg_systeem_pyqgis_toe() -> None:
    """Zet de systeem-site-packages achteraan `sys.path`, als ze bestaan.

    Achteraan: de nieuwere pakketten uit de venv houden voorrang en alleen wat daar
    ontbreekt (`qgis`, `PyQt5`) komt van het systeem.
    """
    pad = _systeem_pyqgis_pad()
    if pad is not None and pad.is_dir() and str(pad) not in sys.path:
        sys.path.append(str(pad))


_voeg_systeem_pyqgis_toe()

try:
    from PyQt5.QtCore import QRectF, QSize  # noqa: E402
    from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QTextDocument  # noqa: E402
    from qgis.core import (  # noqa: E402
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsMapRendererParallelJob,
        QgsMapSettings,
        QgsRectangle,
        QgsSymbolLayerUtils,
        QgsVectorLayer,
    )
except ImportError as fout:  # pragma: no cover - alleen op een machine zonder QGIS
    raise SystemExit(
        f"PyQGIS is hier niet te importeren ({fout}). Installeer QGIS, of wijs de "
        "site-packages aan met GWSW_QGIS_SITE_PACKAGES."
    ) from fout

from nlriochecker.checkconfig import load_check_config  # noqa: E402
from nlriochecker.uitvoer.objectkaart import STATUS_WOORD, STATUSSEN  # noqa: E402
from nlriochecker.uitvoer.stijlen.symbolen import MAPTIP, STATUSKLEUR  # noqa: E402

WIT = QColor(255, 255, 255)
RAND = QColor(120, 120, 120)
TEKST = QColor(34, 34, 34)


def _gpkg(run: Path) -> Path:
    """De GeoPackage van de voorbeeldrun; de naam draagt de rundatum."""
    paden = sorted(run.glob("dq_*.gpkg"))
    if not paden:
        raise SystemExit(
            f"geen GeoPackage in {run}; draai eerst `toets` op het voorbeeld "
            "(zie voorbeelden/koekangerveld/README.md)."
        )
    return paden[-1]


def _laag(gpkg: Path, naam: str) -> QgsVectorLayer:
    """Een featurelaag met haar eigen stijl uit `layer_styles`."""
    laag = QgsVectorLayer(f"{gpkg}|layername={naam}", naam, "ogr")
    if not laag.isValid():
        raise SystemExit(f"laag {naam} is niet leesbaar uit {gpkg}.")
    boodschap, gelukt = laag.loadDefaultStyle()
    if not gelukt:
        raise SystemExit(f"QGIS past de stijl van {naam} niet toe: {boodschap}")
    return laag


def _bereik(gebiedsbestand: Path) -> QgsRectangle:
    """De extent van het studiegebied, met een marge eromheen."""
    gebied = QgsVectorLayer(str(gebiedsbestand), "studiegebied", "ogr")
    if not gebied.isValid():
        raise SystemExit(f"{gebiedsbestand} is niet leesbaar.")
    kader = gebied.extent()
    return QgsRectangle(
        kader.xMinimum() - KAARTMARGE_M,
        kader.yMinimum() - KAARTMARGE_M,
        kader.xMaximum() + KAARTMARGE_M,
        kader.yMaximum() + KAARTMARGE_M,
    )


def _render_kaart(lagen: list[QgsVectorLayer], bereik: QgsRectangle) -> QImage:
    """De kaart zelf: de lagen op het bereik, op een witte ondergrond.

    De eerste laag in de lijst tekent bovenop, net als in de lagenboom van QGIS; de
    putten moeten dus vooraan staan en de vlakken achteraan.
    """
    hoogte = round(KAARTBREEDTE * bereik.height() / bereik.width())
    instellingen = QgsMapSettings()
    instellingen.setLayers(lagen)
    instellingen.setBackgroundColor(WIT)
    instellingen.setOutputSize(QSize(KAARTBREEDTE, hoogte))
    instellingen.setExtent(bereik)
    instellingen.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:28992"))
    instellingen.setFlag(QgsMapSettings.Antialiasing, True)
    opdracht = QgsMapRendererParallelJob(instellingen)
    opdracht.start()
    opdracht.waitForFinished()
    return opdracht.renderedImage()


def _legendaregels(vlakken: QgsVectorLayer) -> list[tuple[QImage | QColor, str]]:
    """De regels van de legenda: eerst de vier statuskleuren, dan de vier vlakregels.

    De statuskleuren komen uit de symbolentabel waarmee de stijl gebouwd is, de
    vlakregels uit de renderer van de laag zelf -- geen van beide is hier overgetypt.
    """
    regels: list[tuple[QImage | QColor, str]] = [
        (QColor(*(int(deel) for deel in STATUSKLEUR[status].split(","))), STATUS_WOORD[status])
        for status in STATUSSEN
    ]
    grootte = QSize(LEGENDAREGEL - 12, LEGENDAREGEL - 12)
    for item in vlakken.renderer().legendSymbolItems():
        vlag = QgsSymbolLayerUtils.symbolPreviewPixmap(item.symbol(), grootte).toImage()
        regels.append((vlag, item.label()))
    return regels


def _teken_legenda(kaart: QImage, regels: list[tuple[QImage | QColor, str]]) -> None:
    """Zet de legenda linksboven op de kaart, in een eigen kader."""
    schilder = QPainter(kaart)
    schilder.setRenderHint(QPainter.Antialiasing, True)
    lettertype = QFont("DejaVu Sans")
    lettertype.setPixelSize(TEKSTGROOTTE)
    schilder.setFont(lettertype)
    maten = schilder.fontMetrics()
    # De tweede kop staat waar de statusregels ophouden en de vlakregels beginnen; die
    # grens is het aantal statussen, niet een geteld aantal vlakregels -- dat laatste
    # verschuift zodra de QML er een regel bij krijgt.
    koppen = {0: "Kleur = status van het object", len(STATUSSEN): "Vlakken per check"}
    breedte = max(maten.horizontalAdvance(tekst) for _, tekst in regels)
    breedte = max(breedte, *(maten.horizontalAdvance(kop) for kop in koppen.values()))
    hoogte = (len(regels) + len(koppen)) * LEGENDAREGEL + LEGENDAMARGE
    kader = QRectF(
        LEGENDAMARGE,
        LEGENDAMARGE,
        breedte + LEGENDAREGEL + 3 * LEGENDAMARGE,
        hoogte + LEGENDAMARGE,
    )
    schilder.setPen(QPen(RAND, 1))
    schilder.setBrush(QColor(255, 255, 255, 232))
    schilder.drawRect(kader)

    y = kader.top() + LEGENDAMARGE
    for index, (vlag, tekst) in enumerate(regels):
        if index in koppen:
            schilder.setPen(QPen(TEKST, 1))
            lettertype.setBold(True)
            schilder.setFont(lettertype)
            schilder.drawText(
                QRectF(kader.left() + LEGENDAMARGE, y, kader.width(), LEGENDAREGEL),
                0,
                koppen[index],
            )
            lettertype.setBold(False)
            schilder.setFont(lettertype)
            y += LEGENDAREGEL
        vak = QRectF(kader.left() + LEGENDAMARGE, y + 6, LEGENDAREGEL - 12, LEGENDAREGEL - 12)
        if isinstance(vlag, QColor):
            schilder.setPen(QPen(QColor(60, 60, 60), 1))
            schilder.setBrush(vlag)
            schilder.drawRect(vak)
        else:
            schilder.drawImage(vak.topLeft(), vlag)
        schilder.setPen(QPen(TEKST, 1))
        schilder.drawText(
            QRectF(vak.right() + LEGENDAMARGE, y, kader.width(), LEGENDAREGEL), 0, tekst
        )
        y += LEGENDAREGEL
    schilder.end()


def _document(css: str, inhoud: str, *, markdown: bool) -> QTextDocument:
    """Een QTextDocument met een stijlblok; Qt leest CSS alleen als default-stylesheet."""
    doc = QTextDocument()
    doc.setDefaultStyleSheet(css)
    doc.setDefaultFont(QFont("DejaVu Sans", 11))
    if markdown:
        doc.setMarkdown(inhoud)
    else:
        doc.setHtml(inhoud)
    return doc


def _teken_document(doc: QTextDocument, breedte: int, schaal: float, marge: int) -> QImage:
    """Rendert een document op een witte ondergrond, `schaal` keer zo groot.

    Schalen tijdens het tekenen en niet achteraf: de tekst blijft dan scherp in plaats
    van uitvergroot.
    """
    doc.setTextWidth(breedte)
    hoogte = round(doc.size().height())
    afbeelding = QImage(
        round((breedte + 2 * marge) * schaal),
        round((hoogte + 2 * marge) * schaal),
        QImage.Format_ARGB32,
    )
    afbeelding.fill(WIT)
    schilder = QPainter(afbeelding)
    schilder.setRenderHint(QPainter.Antialiasing, True)
    schilder.setRenderHint(QPainter.TextAntialiasing, True)
    schilder.scale(schaal, schaal)
    schilder.translate(marge, marge)
    doc.drawContents(schilder)
    schilder.end()
    return afbeelding


def _popup(gpkg: Path, kaart: QImage) -> None:
    """Zet de popup van de zwaarst belaste rode streng rechtsonder op de kaart.

    Dezelfde HTML als de maptip in QGIS: de voorgebakken kolom `popup_html` in het
    stijlblok van `MAPTIP`. Qt is geen browser -- `float: right` valt weg en een marge
    op een inline-element ook, waardoor het check-ID tegen zijn boodschap aan komt te
    staan; daar komt hieronder een spatie tussen. De inhoud en de kleuren komen door.
    """
    verbinding = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        rij = verbinding.execute(
            "select popup_html from strengen where status = 'rood' "
            "order by n_fout desc, n_waarschuwing desc, feature_id limit 1"
        ).fetchone()
    finally:
        verbinding.close()
    if rij is None:
        return

    css, _, rest = MAPTIP.partition("</style>")
    doc = _document(
        css.removeprefix("<style>"),
        rest.replace('[% "popup_html" %]', rij[0]).replace("</span>", "</span> "),
        markdown=False,
    )
    afbeelding = _teken_document(doc, POPUPBREEDTE, POPUPSCHAAL, 8)

    schilder = QPainter(kaart)
    x = kaart.width() - afbeelding.width() - LEGENDAMARGE
    y = kaart.height() - afbeelding.height() - LEGENDAMARGE
    schilder.drawImage(x, y, afbeelding)
    schilder.setPen(QPen(RAND, 1))
    schilder.setBrush(QColor(0, 0, 0, 0))
    schilder.drawRect(QRectF(x, y, afbeelding.width(), afbeelding.height()))
    schilder.end()


def _kop(rapport: Path) -> str:
    """De kop van het bevindingenrapport: titel tot en met de managementsamenvatting.

    De grenzen komen uit de vaste kopregels van `uitvoer/bevindingen.py`; verandert de
    opbouw van het rapport, dan valt dit script om in plaats van stil een ander stuk te
    tonen.
    """
    regels = rapport.read_text(encoding="utf-8").splitlines()

    def eerste(begin: str) -> int:
        for index, regel in enumerate(regels):
            if regel.startswith(begin):
                return index
        raise SystemExit(f"{rapport}: geen regel die met {begin!r} begint.")

    weg_van = eerste("**Objecten waar de checks van afhangen**")
    weg_tot = eerste("## Voldoen we in dit gebied?")
    einde = eerste("**Rode draad**")
    return "\n".join(regels[:weg_van] + [WEGGELATEN, ""] + regels[weg_tot:einde])


def _schermafdrukken() -> None:
    """Rendert en schrijft beide afbeeldingen.

    Een eigen functie en niet de body van `main()`: alles wat QGIS aanmaakt moet vrij
    zijn voordat `exitQgis()` de bibliotheek afsluit. Blijven de lagen tot na die
    afsluiting in leven -- en dat doen ze als ze in `main()` staan -- dan valt het proces
    bij het opruimen om met een segmentatiefout, na de laatste geschreven regel.
    """
    DOEL.mkdir(parents=True, exist_ok=True)
    gpkg = _gpkg(RUN)
    putten, strengen, vlakken = (_laag(gpkg, naam) for naam in ("putten", "strengen", "vlakken"))
    kaart = _render_kaart([putten, strengen, vlakken], _bereik(_studiegebied()))
    _teken_legenda(kaart, _legendaregels(vlakken))
    _popup(gpkg, kaart)
    _bewaar(kaart, DOEL / "kaart-koekangerveld.png")

    doc = _document("", _kop(RUN / "bevindingen.md"), markdown=True)
    _bewaar(_teken_document(doc, RAPPORTBREEDTE, 1, RAPPORTMARGE), DOEL / "rapport-kop.png")


def main() -> None:
    """Rendert beide schermafdrukken uit `uitvoer/voorbeeld/`."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        _schermafdrukken()
    finally:
        app.exitQgis()


def _studiegebied() -> Path:
    """Het studiegebiedbestand van het voorbeeld, uit de meegeleverde configuratie."""
    naam = load_check_config().bronnen.studiegebied
    return WORTEL / "voorbeelden" / "koekangerveld" / naam


def _bewaar(afbeelding: QImage, pad: Path) -> None:
    """Schrijft de afbeelding weg als PNG met een beperkt palet.

    Beperkt palet (8 bits): een schermafdruk van kaart of tekst draagt weinig kleuren en
    wordt daarmee ruim drie keer zo klein, zonder zichtbaar verschil.
    """
    if not afbeelding.convertToFormat(QImage.Format_Indexed8).save(str(pad), "PNG"):
        raise SystemExit(f"kon {pad} niet schrijven.")
    print(
        f"{pad.relative_to(WORTEL)}: {afbeelding.width()}x{afbeelding.height()} px, "
        f"{pad.stat().st_size / 1000:.0f} kB"
    )


if __name__ == "__main__":
    main()
