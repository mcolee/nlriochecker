"""De GWSW-symbologie van de twee objectlagen, en de QML die eruit volgt.

De symbolen komen uit de PDOK-SLD's in `data/gwsw_opmaak/`. Die verwijzen hun beeld
niet als bestand maar als `ExternalGraphic` naar `https://data.gwsw.nl/img/*.svg`, en
die bestanden zijn niet meegeleverd; ze ophalen zou dit pakket van een netwerkbron
afhankelijk maken en symbolen van een derde in onze uitvoer bakken. Issue #14 voorziet
dat geval: dan hertekenen we het symbool als eenvoudige marker in de GWSW-vorm. De
SLD's blijven wel de bron voor de *indeling* -- welk objecttype welk symbool krijgt en
welke typen er een delen -- en elke regel in de tabellen hieronder noemt de SLD-regel
die hij vervangt.

De QML's worden hier opgebouwd in plaats van als bestand meegeleverd. De
regelstructuur die issue #14 voorschrijft is objecttype x status, en op de
De Wolden-export zijn dat 56 respectievelijk 68 bladregels met evenzoveel symbolen.
Met de hand is dat ruim vijftienhonderd regels XML waarin een tikfout de kaart stil
leegtrekt, en waarin de typenlijst op twee plekken zou staan. `bouwwerken.qml` en
`waterdelen_zonder_zinker.qml` blijven wel gewone bestanden: die hebben een enkel
symbool en veranderen niet.

De kleur komt uitsluitend van de kolom `status`; het symbool zegt wat voor object het
is. Voor verbindingen kan het symbool dat maar half dragen: het GWSW onderscheidt
leidingsoorten met kleur, en die is hier aan de status vergeven. Wat overblijft is
lijndikte en streepjespatroon. Elk type houdt daarom zijn eigen regel met zijn eigen
legendalabel -- de legenda blijft volledig -- maar verwante typen delen een lijnstijl,
zodat het kaartbeeld de families onderscheidt: vrijverval, mechanisch, aansluiting,
drain, duiker, berging, loos.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape, quoteattr

from nlriochecker.uitvoer.objectkaart import (
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ORANJE,
    STATUS_ROOD,
    STATUS_WOORD,
    STATUSSEN,
)

# De statuskleuren, als RGB. Kleurenblind-veilig gekozen: rood is duidelijk donkerder
# dan groen, dus ook in grijstinten en bij deuteranopie blijven ze uit elkaar te
# houden. Grijs is als enige onverzadigd en valt daarmee uit de reeks weg -- precies
# wat "niet beoordeeld" hoort te doen.
STATUSKLEUR = {
    STATUS_ROOD: "178,24,43",
    STATUS_ORANJE: "224,130,20",
    STATUS_GROEN: "77,146,33",
    STATUS_GRIJS: "158,158,158",
}

# De randkleur van elk symbool. Een donkere rand houdt een licht symbool leesbaar op
# een lichte ondergrond; grijs krijgt een lichtere rand, zodat het naar achteren valt.
RANDKLEUR = {status: "60,60,60" for status in STATUSSEN} | {STATUS_GRIJS: "130,130,130"}

# De kleur van de richtingpijl. Los van de statuskleur van de lijn: de pijl zegt iets
# anders dan de uitslag, en beide lagen over elkaar heen.
PIJLKLEUR_MEE = "27,120,55"
PIJLKLEUR_TEGEN = "178,24,43"
PIJLKLEUR_ONBEKEND = "130,130,130"

# En hun grootte. `mee` is het normale geval en hoort stil te zijn -- op een echte
# kaart staat er op vrijwel elke streng een pijl, en een luide pijl overstemt dan de
# putsymbolen die het eigenlijke onderwerp zijn. `tegen` is de uitzondering en mag
# opvallen: daar loopt het water de andere kant op dan de tekening suggereert.
PIJLGROOTTE_NORMAAL = 1.8
PIJLGROOTTE_UITZONDERING = 3.0


@dataclass(frozen=True)
class Puntsymbool:
    """Een knooppuntsymbool: een QGIS-markervorm die een GWSW-symbool vervangt."""

    vorm: str
    grootte: float
    # De regel uit de PDOK-SLD die dit symbool vervangt, zodat naspeurbaar blijft
    # waar de indeling vandaan komt.
    sld: str


@dataclass(frozen=True)
class Lijnsymbool:
    """Een verbindingssymbool: dikte en streepjespatroon, want kleur is van de status."""

    breedte: float
    streep: str
    sld: str


# Knooppunttypen. De GWSW-namen zijn de korte klassenamen zoals
# `GwswDataset.beheerobjecttype` ze oplevert; de filters vergelijken
# hoofdletterongevoelig, want exports schrijven ze niet allemaal gelijk
# (De Wolden heeft `DwaPerceelaansluitleiding` waar de SLD `DWAPerceelaansluitleiding`
# noemt).
PUNTSYMBOLEN: dict[str, Puntsymbool] = {
    # Putten (PDOK; Put.sld)
    "Inspectieput": Puntsymbool("circle", 2.6, "Put.sld: Inspectieput"),
    "Kruisingsput": Puntsymbool("octagon", 2.8, "Put.sld: Kruisingsput"),
    "Zandvangput": Puntsymbool("circle", 2.8, "Put.sld: Zandvangput"),
    "Doorspoelput": Puntsymbool("circle", 2.2, "Put.sld: Doorspoelput"),
    "BijzonderePutconstructie": Puntsymbool("hexagon", 3.0, "Put.sld: Bijzondere putconstructie"),
    "Stuwput": Puntsymbool("pentagon", 3.0, "Put.sld: Stuwput"),
    "Vacuumopslagtank": Puntsymbool("square", 3.0, "Put.sld: Vacuumopslagtank"),
    "Overnamepunt": Puntsymbool("diamond", 3.2, "Put.sld: Overnamepunt"),
    "Drainageput": Puntsymbool("circle", 2.0, "Put.sld: Drainageput"),
    "Infiltratieput": Puntsymbool("circle", 2.0, "Put.sld: Drainageput"),
    # Lozingen (PDOK; Lozing.sld)
    "Overstortput": Puntsymbool("triangle", 3.2, "Lozing.sld: Overstortput"),
    "ExterneOverstortput": Puntsymbool("triangle", 3.2, "Lozing.sld: Externe overstortput"),
    "Interneoverstortput": Puntsymbool("triangle", 2.8, "Lozing.sld: Interne overstortput"),
    "Noodoverstortput": Puntsymbool("triangle", 3.2, "Lozing.sld: Noodoverstortput"),
    "Lozingsput": Puntsymbool("triangle", 3.0, "Lozing.sld: Lozingsput"),
    "UitlaatPunt": Puntsymbool("triangle", 3.0, "Lozing.sld: Uitlaat"),
    # Aansluitpunten (PDOK; Aansluitpunt.sld)
    "Kolk": Puntsymbool("square", 2.0, "Aansluitpunt.sld: Kolk"),
    "Straatkolk": Puntsymbool("square", 2.0, "Aansluitpunt.sld: Kolk"),
    "Opvangput": Puntsymbool("square", 2.2, "Aansluitpunt.sld: Kolk"),
    "Inlaat": Puntsymbool("circle", 2.2, "Aansluitpunt.sld: Inlaat"),
    # Pompen (PDOK; Pomp.sld)
    "Pompput": Puntsymbool("star", 3.2, "Pomp.sld: Pompput"),
    "Pompunit": Puntsymbool("star", 3.2, "Pomp.sld: Pompput"),
    "Vacuumgemaal": Puntsymbool("star", 3.4, "Pomp.sld: Vacuumgemaal"),
    # Bouwwerken (PDOK; Bouwwerk.sld)
    "Rioolgemaal": Puntsymbool("star", 3.6, "Bouwwerk.sld: Rioolgemaal"),
    "Boostergemaal": Puntsymbool("star", 3.6, "Bouwwerk.sld: Rioolgemaal"),
    "Opvoergemaal": Puntsymbool("star", 3.6, "Bouwwerk.sld: Rioolgemaal"),
    "Vijzelgemaal": Puntsymbool("star", 3.6, "Bouwwerk.sld: Rioolgemaal"),
    "Vacuumpompstation": Puntsymbool("star", 3.6, "Bouwwerk.sld: Rioolgemaal"),
    "Uitlaatconstructie": Puntsymbool("triangle", 3.4, "Bouwwerk.sld: Uitlaatconstructie"),
    "Nooduitlaat": Puntsymbool("triangle", 3.4, "Bouwwerk.sld: Nooduitlaat"),
    "Bergbezinkbassin": Puntsymbool("square", 3.6, "Bouwwerk.sld: Reservoir"),
    "Bergingsbassin": Puntsymbool("square", 3.6, "Bouwwerk.sld: Reservoir"),
    "Bezinkbassin": Puntsymbool("square", 3.6, "Bouwwerk.sld: Reservoir"),
    "Helofytenfilter": Puntsymbool("square", 3.2, "Bouwwerk.sld: Infiltratievoorziening"),
    "IBA": Puntsymbool("square", 3.0, "Bouwwerk.sld: IBA"),
    "Septictank": Puntsymbool("square", 3.0, "Bouwwerk.sld: IBA"),
    "RWZI": Puntsymbool("square", 4.0, "Bouwwerk.sld: RWZI"),
    # Hulpstukken. De SLD's kennen ze niet als eigen regel, maar De Wolden telt er
    # 1.122; ze stil in het vangnet laten vallen zou de kaart onnodig laten schreeuwen
    # over objecten die gewoon zijn wat ze zijn.
    "T_stuk": Puntsymbool("cross2", 2.4, "geen SLD-regel; hulpstuk"),
    "Afsluitstuk": Puntsymbool("square", 2.2, "geen SLD-regel; hulpstuk"),
    "Ontstoppingsstuk": Puntsymbool("hexagon", 2.2, "geen SLD-regel; hulpstuk"),
    "Aansluitpunt": Puntsymbool("circle", 2.0, "Aansluitpunt.sld: Default"),
    "Verbindingsstuk": Puntsymbool("hexagon", 2.2, "geen SLD-regel; hulpstuk"),
    # Onderdelen binnen een bouwwerk. Ze hebben een orientatie van het type Knooppunt
    # en komen dus in de puttenlaag terecht; het Juinen-voorbeeld bevat ze.
    "Compartiment": Puntsymbool("square", 2.4, "geen SLD-regel; onderdeel"),
    "InlaatLeiding": Puntsymbool("circle", 2.2, "Aansluitpunt.sld: Inlaat"),
}

# Het vangnet. Een open cirkel met een kruis erin: zichtbaar anders dan elk symbool uit
# de tabel, zodat een onbekend type als onbekend te zien is in plaats van stilzwijgend
# als put door te gaan.
VANGNET_PUNT = Puntsymbool("circle", 2.8, "geen; vangnet")
VANGNET_PUNT_LABEL = "objecttype niet in de symbolentabel"

# Verbindingstypen.
LIJNSYMBOLEN: dict[str, Lijnsymbool] = {
    # Vrijverval (PDOK; Leiding.sld): doorgetrokken, normale dikte.
    "GemengdRiool": Lijnsymbool(0.9, "solid", "Leiding.sld: Gemengd riool"),
    "Vuilwaterriool": Lijnsymbool(0.9, "solid", "Leiding.sld: Vuilwaterriool"),
    "Hemelwaterriool": Lijnsymbool(0.9, "solid", "Leiding.sld: Hemelwaterriool"),
    "Infiltratieriool": Lijnsymbool(0.9, "solid", "Leiding.sld: Infiltratieriool"),
    "Overstortleiding": Lijnsymbool(1.2, "solid", "Leiding.sld: Overstortleiding"),
    "Transportrioolleiding": Lijnsymbool(1.6, "solid", "Leiding.sld: Transportrioolleiding"),
    "VrijvervalLeidingsegment": Lijnsymbool(1.6, "solid", "Leiding.sld: Transportrioolleiding"),
    "Zinker": Lijnsymbool(1.2, "dash", "geen SLD-regel; vrijverval onder een watergang"),
    # Mechanisch: gestreept, want er is geen vrij verval.
    "Persleiding": Lijnsymbool(1.2, "dash", "Leiding.sld: Persleiding"),
    "Leidingsegment": Lijnsymbool(1.2, "dash", "Leiding.sld: Persleiding"),
    "Drukleiding": Lijnsymbool(0.9, "dash", "Leiding.sld: Drukleiding"),
    "Vacuumleiding": Lijnsymbool(0.9, "dash", "Leiding.sld: Vacuumleiding"),
    "Luchtpersleiding": Lijnsymbool(1.2, "dash", "Leiding.sld: Luchtpersleiding"),
    # Aansluitleidingen (PDOK; Aansluitleiding.sld): dun.
    "Perceelaansluitleiding": Lijnsymbool(0.4, "solid", "Aansluitleiding.sld: Perceelaansluiting"),
    "DwaPerceelaansluitleiding": Lijnsymbool(0.4, "solid", "Aansluitleiding.sld: DWA"),
    "HwaPerceelaansluitleiding": Lijnsymbool(0.4, "solid", "Aansluitleiding.sld: HWA"),
    "GemengdePerceelaansluitleiding": Lijnsymbool(0.4, "solid", "Aansluitleiding.sld: Gemengd"),
    "Kolkaansluitleiding": Lijnsymbool(0.4, "solid", "Aansluitleiding.sld: Kolkaansluitleiding"),
    "Goot": Lijnsymbool(0.4, "dot", "Aansluitleiding.sld: Goot"),
    "Lijngoot": Lijnsymbool(0.4, "dot", "Aansluitleiding.sld: Goot"),
    "Roostergoot": Lijnsymbool(0.4, "dot", "Aansluitleiding.sld: Goot"),
    "Taludgoot": Lijnsymbool(0.4, "dot", "Aansluitleiding.sld: Goot"),
    "Verholengoot": Lijnsymbool(0.4, "dot", "Aansluitleiding.sld: Goot"),
    # Overig.
    "Drain": Lijnsymbool(0.4, "dot", "Leiding.sld: Drain"),
    "Duiker": Lijnsymbool(1.4, "solid", "Leiding.sld: Duiker"),
    "Mantelbuis": Lijnsymbool(1.8, "solid", "Leiding.sld: Mantelbuis"),
    "Bergingsleiding": Lijnsymbool(1.8, "solid", "Leiding.sld: Bergingsleiding"),
    "Bergbezinkleiding": Lijnsymbool(1.8, "solid", "Leiding.sld: Bergingsleiding"),
    "LozeLeiding": Lijnsymbool(0.5, "dash dot", "Leiding.sld: Loze leiding"),
    "GedammerdeLeiding": Lijnsymbool(0.5, "dash dot", "Leiding.sld: Loze leiding"),
    "Uitlegger": Lijnsymbool(0.5, "dash dot", "Leiding.sld: Loze leiding"),
    "VolgeschuimdeLeiding": Lijnsymbool(0.5, "dash dot", "Leiding.sld: Loze leiding"),
    "VolgezandeLeiding": Lijnsymbool(0.5, "dash dot", "Leiding.sld: Loze leiding"),
    # Verbindingen binnen een bouwwerk: een drempel, een stuwmuur, een pomp, een
    # opening in een wand. Geen leidingen, maar wel verbindingen in de zin van het
    # GWSW, dus ze komen in de strengenlaag terecht. Dun en gestippeld: ze horen bij
    # het bouwwerk en niet bij het net eromheen.
    "Overstortdrempel": Lijnsymbool(0.6, "dot", "geen SLD-regel; onderdeel"),
    "Stuwmuur": Lijnsymbool(0.6, "dot", "geen SLD-regel; onderdeel"),
    "OpeningInWand": Lijnsymbool(0.4, "dot", "geen SLD-regel; onderdeel"),
    "Pomp": Lijnsymbool(0.6, "dot", "geen SLD-regel; onderdeel"),
}

VANGNET_LIJN = Lijnsymbool(0.9, "dash dot dot", "geen; vangnet")
VANGNET_LIJN_LABEL = "objecttype niet in de symbolentabel"

# De maptip: een stijlblok, een vaste breedte en de voorgebakken kolom. De vaste
# breedte houdt het popupframe stil in plaats van bij elk object te herschalen; het
# stijlblok staat hier en niet in elke rij van `popup_html`, want per object herhaald
# zou het de GeoPackage tientallen megabytes groter maken. Geen webfont en geen
# afbeelding-URL: de popup moet zelfstandig reizen.
MAPTIP = """<style>
  .gwsw-popup { font-family: sans-serif; font-size: 9pt; color: #222; }
  .gwsw-popup .k { border-bottom: 1px solid #bbb; padding-bottom: 2px; margin-bottom: 4px; }
  .gwsw-popup .l { font-weight: bold; }
  .gwsw-popup .t { color: #555; margin-left: 6px; }
  .gwsw-popup .s { float: right; text-transform: uppercase; font-size: 7pt; }
  .s-rood .s { color: #b2182b; }
  .s-oranje .s { color: #e08214; }
  .s-groen .s { color: #4d9221; }
  .s-grijs .s { color: #777; }
  .gwsw-popup .f, .gwsw-popup .r { color: #555; font-size: 8pt; margin-bottom: 4px; }
  .gwsw-popup .m { margin: 0; padding-left: 14px; }
  .gwsw-popup .m li { margin-bottom: 3px; }
  .gwsw-popup .e { font-weight: bold; margin-right: 3px; }
  .e-F .e { color: #b2182b; }
  .e-W .e { color: #e08214; }
  .gwsw-popup .c { font-weight: bold; margin-right: 4px; }
  .gwsw-popup .v, .gwsw-popup .d, .gwsw-popup .y, .gwsw-popup .h {
    color: #666; font-size: 8pt; margin-left: 5px;
  }
  .gwsw-popup .x, .gwsw-popup .z, .gwsw-popup .n {
    color: #666; font-size: 8pt; margin-top: 4px;
  }
</style>
<div style="width:300px">[% "popup_html" %]</div>"""

# QGIS wil per regel en per symbool een sleutel. Ze hoeven alleen uniek te zijn binnen
# het bestand; deze reeks is deterministisch, zodat twee runs dezelfde QML opleveren.
_SLEUTELBASIS = "aa000000-0000-4000-8000-{:012d}"


def bouw_qml(laag: str) -> str:
    """De opgebouwde QML van een objectlaag.

    Alleen `putten` en `strengen`; de andere twee lagen zijn gewone bestanden.
    """
    if laag == "putten":
        return _qml_punten()
    if laag == "strengen":
        return _qml_lijnen()
    raise ValueError(f"{laag!r} heeft geen opgebouwde stijl; lees het QML-bestand.")


class _Opbouw:
    """Verzamelt regels en symbolen en houdt hun sleutels en nummers bij."""

    def __init__(self) -> None:
        self.regels: list[str] = []
        self.symbolen: list[str] = []
        self._teller = 0

    def sleutel(self) -> str:
        """Een verse, deterministische sleutel."""
        self._teller += 1
        return _SLEUTELBASIS.format(self._teller)

    def voeg_symbool_toe(self, xml_van_naam) -> str:
        """Voegt een symbool toe en levert zijn nummer als tekst."""
        naam = str(len(self.symbolen))
        self.symbolen.append(xml_van_naam(naam))
        return naam


def _qml_punten() -> str:
    """De stijl van `putten`: markervorm naar objecttype, kleur naar status."""
    opbouw = _Opbouw()
    for objecttype, symbool in PUNTSYMBOLEN.items():
        opbouw.regels.append(_typeregel(opbouw, _filter_type(objecttype), objecttype, symbool))
    opbouw.regels.append(
        _typeregel(opbouw, _filter_vangnet(PUNTSYMBOLEN), VANGNET_PUNT_LABEL, VANGNET_PUNT)
    )
    return _document(opbouw)


def _qml_lijnen() -> str:
    """De stijl van `strengen`: lijndikte en streep naar objecttype, kleur naar status.

    Daar bovenop drie richtingsregels. De logica erachter (`gpkg._richting_bob`) is
    ongewijzigd; alleen de weergave verandert. `tegen` krijgt een enkele rode pijl die
    over 180 graden gedraaid is en dus in de BOB-vervalrichting wijst -- waar het water
    werkelijk heen loopt. De dubbele pijl van voorheen vervalt.
    """
    opbouw = _Opbouw()
    for objecttype, symbool in LIJNSYMBOLEN.items():
        opbouw.regels.append(_typeregel(opbouw, _filter_type(objecttype), objecttype, symbool))
    opbouw.regels.append(
        _typeregel(opbouw, _filter_vangnet(LIJNSYMBOLEN), VANGNET_LIJN_LABEL, VANGNET_LIJN)
    )
    for richting, kleur, hoek, grootte, label in (
        ("mee", PIJLKLEUR_MEE, 0, PIJLGROOTTE_NORMAAL, "BOB volgt de lijnrichting"),
        (
            "tegen",
            PIJLKLEUR_TEGEN,
            180,
            PIJLGROOTTE_UITZONDERING,
            "BOB tegen de lijnrichting in",
        ),
        (
            "onbekend",
            PIJLKLEUR_ONBEKEND,
            0,
            PIJLGROOTTE_NORMAAL,
            "BOB-richting niet te bepalen",
        ),
    ):
        naam = opbouw.voeg_symbool_toe(
            lambda n, k=kleur, h=hoek, g=grootte: _pijlsymbool(n, k, h, g)
        )
        voorwaarde = f'"richting_bob" = {_tekst(richting)}'
        opbouw.regels.append(
            f"<rule key={quoteattr('{' + opbouw.sleutel() + '}')} "
            f"filter={quoteattr(voorwaarde)} "
            f"symbol={quoteattr(naam)} label={quoteattr(label)}/>"
        )
    return _document(opbouw)


def _typeregel(opbouw: _Opbouw, filter_: str, label: str, symbool: object) -> str:
    """Een regel per objecttype, met vier kindregels: een per status."""
    kinderen = []
    for status in STATUSSEN:
        if isinstance(symbool, Puntsymbool):
            naam = opbouw.voeg_symbool_toe(lambda n, s=symbool, t=status: _puntsymbool(n, s, t))
        else:
            naam = opbouw.voeg_symbool_toe(lambda n, s=symbool, t=status: _lijnsymbool(n, s, t))
        voorwaarde = f'"status" = {_tekst(status)}'
        kinderen.append(
            f"<rule key={quoteattr('{' + opbouw.sleutel() + '}')} "
            f"filter={quoteattr(voorwaarde)} "
            f"symbol={quoteattr(naam)} "
            f"label={quoteattr(STATUS_WOORD[status])}/>"
        )
    return (
        f"<rule key={quoteattr('{' + opbouw.sleutel() + '}')} "
        f"filter={quoteattr(filter_)} label={quoteattr(label)}>" + "".join(kinderen) + "</rule>"
    )


def _filter_type(objecttype: str) -> str:
    """Een hoofdletterongevoelige vergelijking op `objecttype`.

    Exports schrijven de klassenaam niet allemaal gelijk: De Wolden heeft
    `DwaPerceelaansluitleiding` waar de PDOK-SLD `DWAPerceelaansluitleiding` noemt.
    Hoofdlettergevoelig filteren zou zulke objecten stil in het vangnet laten vallen.
    """
    return f'lower("objecttype") = {_tekst(objecttype.lower())}'


def _filter_vangnet(tabel: dict) -> str:
    """Alles wat niet in de tabel staat, plus objecten zonder objecttype."""
    bekend = ", ".join(_tekst(naam.lower()) for naam in sorted(tabel))
    return f'lower("objecttype") not in ({bekend}) or "objecttype" is null'


def _tekst(waarde: str) -> str:
    """Een tekstliteraal voor een QGIS-expressie."""
    return "'" + waarde.replace("'", "''") + "'"


def _puntsymbool(naam: str, symbool: Puntsymbool, status: str) -> str:
    """Een markersymbool: de vorm van het objecttype, de kleur van de status."""
    return (
        f'<symbol type="marker" name={quoteattr(naam)} alpha="1">'
        '<layer class="SimpleMarker">'
        f'<prop k="name" v={quoteattr(symbool.vorm)}/>'
        f'<prop k="color" v={quoteattr(STATUSKLEUR[status] + ",255")}/>'
        f'<prop k="outline_color" v={quoteattr(RANDKLEUR[status] + ",255")}/>'
        '<prop k="outline_width" v="0.2"/>'
        f'<prop k="size" v={quoteattr(f"{symbool.grootte}")}/>'
        "</layer></symbol>"
    )


def _lijnsymbool(naam: str, symbool: Lijnsymbool, status: str) -> str:
    """Een lijnsymbool: dikte en streep van het objecttype, kleur van de status."""
    return (
        f'<symbol type="line" name={quoteattr(naam)} alpha="1">'
        '<layer class="SimpleLine">'
        f'<prop k="line_color" v={quoteattr(STATUSKLEUR[status] + ",255")}/>'
        f'<prop k="line_width" v={quoteattr(f"{symbool.breedte}")}/>'
        f'<prop k="line_style" v={quoteattr(symbool.streep)}/>'
        "</layer></symbol>"
    )


def _pijlsymbool(naam: str, kleur: str, hoek: int, grootte: float) -> str:
    """De richtingpijl op het midden van een streng.

    `rotate=1` laat de marker met de lijn meedraaien; `angle=180` keert hem om, zodat
    hij bij `tegen` in de BOB-vervalrichting wijst in plaats van met de getekende lijn
    mee.

    De grootte verschilt per geval, en dat is een keuze en geen detail: op een echte
    kaart draagt vrijwel elke streng een pijl, en een pijl die groter is dan het
    putsymbool overstemt precies datgene waar de kaart over gaat. `mee` is het normale
    geval en blijft klein; `tegen` is de uitzondering en mag opvallen.
    """
    return (
        f'<symbol type="line" name={quoteattr(naam)} alpha="1">'
        '<layer class="MarkerLine">'
        '<prop k="placement" v="centralpoint"/>'
        '<prop k="rotate" v="1"/>'
        f'<symbol type="marker" name={quoteattr("@" + naam + "@0")} alpha="1">'
        '<layer class="SimpleMarker">'
        '<prop k="name" v="filled_arrowhead"/>'
        f'<prop k="color" v={quoteattr(kleur + ",255")}/>'
        f'<prop k="outline_color" v={quoteattr(kleur + ",255")}/>'
        f'<prop k="size" v={quoteattr(f"{grootte}")}/>'
        f'<prop k="angle" v={quoteattr(str(hoek))}/>'
        "</layer></symbol>"
        "</layer></symbol>"
    )


def _document(opbouw: _Opbouw) -> str:
    """Zet de regels en symbolen in een QML met symbologie en maptip.

    `styleCategories` noemt beide categorieen expliciet. Zonder `MapTips` leest QGIS
    het `mapTip`-element niet terug uit `layer_styles` en blijft de hoverpopup leeg,
    zonder dat er ergens een fout gemeld wordt.
    """
    return (
        '<qgis version="3.28" styleCategories="Symbology|MapTips">'
        '<renderer-v2 type="RuleRenderer" forceraster="0" symbollevels="0">'
        f"<rules key={quoteattr('{' + _SLEUTELBASIS.format(0) + '}')}>"
        + "".join(opbouw.regels)
        + "</rules><symbols>"
        + "".join(opbouw.symbolen)
        + "</symbols></renderer-v2>"
        f'<mapTip enabled="1">{escape(MAPTIP)}</mapTip>'
        '<legend type="default-vector"/>'
        "</qgis>"
    )
