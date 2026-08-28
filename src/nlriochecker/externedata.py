"""Externe geodata uit `data/gis_koekangerveld/` voor de EXT- en AHN-checks.

De aangeleverde bronnen dekken alleen het studiegebied Koekangerveld, terwijl de
GWSW-dataset de gemeenten De Wolden en Hoogeveen beslaat. Een GWSW-object buiten dat gebied
mag daarom nooit een check-uitslag krijgen: dat er geen BGT-deksel of BAG-pand in de
buurt ligt zegt daar niets over de datakwaliteit en alles over de dekking van de
bron. Alle EXT- en AHN-checks vragen daarom eerst `binnen_bereik()` en laten de rest
als *buiten studiegebied* buiten beschouwing.

Alles staat in RD New (EPSG:28992). Het CRS van elk bestand wordt bij het inlezen
gecontroleerd; alleen een bron met een correct gedefinieerd afwijkend CRS wordt
geherprojecteerd, en dat wordt vastgelegd in `notes`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from nlriochecker.errors import PipelineError
from nlriochecker.taal import getal

RD_NEW = 28992


class ExternalDataError(PipelineError):
    """Een externe bron ontbreekt, is onleesbaar of staat in een ander stelsel."""


class Dekkingseis(NamedTuple):
    """Hoe ver buiten het bereik de checks kijken, en welk tekort toegestaan is."""

    marge_m: float
    tolerantie_m: float


@dataclass(frozen=True)
class VectorLayer:
    """Een ingelezen vectorlaag uit een van de aangeleverde bestanden."""

    role: str
    source: Path
    layer: str
    crs: str
    geometries: tuple[BaseGeometry, ...]
    attributes: tuple[dict[str, object], ...] = ()
    tree: STRtree | None = None
    reprojected_from: str | None = None

    def __len__(self) -> int:
        """Het aantal features."""
        return len(self.geometries)

    def nabij(self, geometrie: BaseGeometry, afstand: float):
        """De features waarvan de omhullende binnen deze afstand komt.

        Levert paren van geometrie en attributen op. Bij afstand nul wordt de
        geometrie zelf bevraagd: `buffer(0)` van een lijn levert een lege polygoon
        op en die vindt in de index niets.
        """
        if self.tree is None or geometrie is None or geometrie.is_empty:
            return
        zoekvorm = geometrie.buffer(afstand) if afstand > 0 else geometrie
        for index in self.tree.query(zoekvorm):
            positie = int(index)
            yield self.geometries[positie], self._attributen(positie)

    def _attributen(self, positie: int) -> dict[str, object]:
        """De attributen van een feature, of een lege dict."""
        return self.attributes[positie] if positie < len(self.attributes) else {}


@dataclass(frozen=True)
class RasterSampler:
    """Een hoogteraster waaruit op puntlocaties bemonsterd kan worden."""

    source: Path
    crs: str
    nodata: float | None
    bounds: tuple[float, float, float, float]
    # Rasterio levert geen typestubs; het lezerobject blijft daarom ongetypeerd.
    reader: Any = None

    def sample(self, x: float, y: float) -> float | None:
        """De rasterwaarde op deze RD-coordinaat, of None buiten het raster."""
        if self.reader is None:
            return None
        links, onder, rechts, boven = self.bounds
        if not (links <= x <= rechts and onder <= y <= boven):
            return None
        waarde = next(self.reader.sample([(x, y)], 1))[0]
        if waarde is None:
            return None
        getal = float(waarde)
        if self.nodata is not None and abs(getal - self.nodata) < 1e-6:
            return None
        # Sommige rasters gebruiken een enorme sentinel in plaats van een echte
        # nodata-vlag; een maaiveldhoogte boven de Mount Everest is geen meting.
        if getal > 1e6 or getal < -1e6:
            return None
        return getal


@dataclass(frozen=True)
class ExternalData:
    """Alle beschikbare externe bronnen plus het bereik waarbinnen ze gelden."""

    extent: BaseGeometry | None = None
    extent_source: Path | None = None
    extent_name: str = ""
    layers: dict[str, VectorLayer] = field(default_factory=dict)
    raster: RasterSampler | None = None
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def layer(self, rol: str) -> VectorLayer | None:
        """De laag die deze rol vervult, of None als die niet aangeleverd is."""
        laag = self.layers.get(rol)
        return laag if laag is not None and len(laag) else None

    def binnen_bereik(self, geometrie: BaseGeometry | None) -> bool:
        """Geeft aan of een geometrie binnen het bereik van de externe bronnen valt."""
        if geometrie is None or geometrie.is_empty or self.extent is None:
            return False
        return self.extent.intersects(geometrie)

    def ontbreekt(self, rol: str) -> str:
        """De standaardmelding voor een rol waarvan de laag niet aangeleverd is."""
        return (
            f"laag niet aanwezig in aangeleverde data: er is geen bruikbare laag voor de rol "
            f"{rol!r} (leeg of niet meegeleverd); deze check is overgeslagen."
        )


# Welke lagen uit welk bestand welke rol vervullen. De laagnamen zijn overrulebaar
# via de projectconfig; deze lijst is de standaard voor de aangeleverde export.
ROLLEN = {
    "bgt_pand": "bgt_pandlagen",
    "bgt_water": "bgt_waterlagen",
    "bgt_putdeksel": "bgt_putdeksellagen",
    "bgt_bouwwerk": "bgt_overige_bouwwerklagen",
}


def load_external_data(
    bronnen, wortel: Path | None = None, *, dekkingseis: Dekkingseis | None = None
) -> ExternalData:
    """Leest de externe bronnen uit de geconfigureerde map.

    Ontbreekt een bestand, dan is dat geen fout: de bronnen zijn optioneel en de
    checks die ze nodig hebben melden zelf dat ze niets konden toetsen. Wat er niet
    was komt in `missing` te staan en daarmee in het rapport.

    Met een `dekkingseis` wordt elke aangeleverde bron getoetst op dekking van het
    bereik voordat er ook maar een check draait; zie `_toets_dekking`. Zonder eis
    blijft die toets achterwege -- een beller die de zoekafstanden en de tolerantie
    niet kent, kan er ook geen oordeel over vellen.
    """
    basis = Path(wortel) if wortel is not None else Path.cwd()
    map_pad = basis / bronnen.map

    ontbrekend: list[str] = []
    notities: list[str] = []
    lagen: dict[str, VectorLayer] = {}

    extent, extent_pad, extent_naam = _lees_studiegebied(
        map_pad, bronnen.studiegebied, ontbrekend, notities
    )

    for rol, veld in ROLLEN.items():
        laagnamen = getattr(bronnen, veld)
        laag = _lees_rol(map_pad, bronnen.bgt, rol, laagnamen, ontbrekend, notities)
        if laag is not None:
            lagen[rol] = laag

    for rol, bestand in (("bag_pand", bronnen.bag_pand), ("nwb_wegvak", bronnen.nwb_wegvakken)):
        laag = _lees_rol(map_pad, bestand, rol, [], ontbrekend, notities, enige_laag=True)
        if laag is not None:
            lagen[rol] = laag

    raster = _lees_raster(map_pad, bronnen.ahn_dtm, ontbrekend, notities)

    data = ExternalData(
        extent=extent,
        extent_source=extent_pad,
        extent_name=extent_naam,
        layers=lagen,
        raster=raster,
        missing=tuple(ontbrekend),
        notes=tuple(notities),
    )
    if dekkingseis is not None:
        _toets_dekking(data, dekkingseis)
    return data


def _toets_dekking(data: ExternalData, eis: Dekkingseis) -> None:
    """Weigert bronnen die kleiner zijn dan het bereik waarvoor ze gelden.

    Een extract dat maar een deel van het bereik dekt geeft een misleidend schone
    uitkomst: geen treffer leest als geen probleem, terwijl de bron er domweg niet
    was. Daarom is dit een fout en geen waarschuwing, en is er geen forceer-vlag --
    wel een geconfigureerde tolerantie (`[bronnen] dekking_tolerantie_m`).

    Het bereik is dat van `bronnen.studiegebied`: het gebied waarvoor je de bronnen
    geldig verklaart, en precies het gebied waarbinnen de checks uitslagen geven. Dat
    de bronnen maar een deel van de GWSW-dataset dekken is iets anders en al eerlijk
    afgevangen: objecten daarbuiten krijgen de status *buiten studiegebied* (BC-2).
    Zonder bereik draait deze poort dan ook niet -- dan geeft geen enkele EXT-check
    een uitslag en valt er niets te maskeren.

    De vectorlagen worden getoetst tegen het bereik plus `marge_m`, want een pand net
    buiten het bereik telt mee voor een object er net binnen. Het raster krijgt geen
    marge: bemonsteren is puntsgewijs.

    Wat deze poort *niet* kan: bbox-dekking is noodzakelijk maar niet voldoende. Een
    gat midden in het extract valt er niet mee op, en een tekort op een dunne laag
    betekent "hier staan geen features", niet per se "extract afgeknipt". De
    `binnen_bereik`-notities per object blijven het tweede vangnet.
    """
    if data.extent is None:
        return

    bereik = data.extent.bounds
    tekorten: list[str] = []
    for rol, laag in sorted(data.layers.items()):
        omhullende = _omhullende(laag.geometries)
        if omhullende is None:
            continue
        tekorten += _tekortregel(rol, laag.source.name, omhullende, bereik, eis.marge_m, eis)
    if data.raster is not None:
        tekorten += _tekortregel(
            "ahn_dtm", data.raster.source.name, data.raster.bounds, bereik, 0.0, eis
        )

    if tekorten:
        raise ExternalDataError(
            "de aangeleverde bronnen dekken het bereik niet waarvoor ze gelden; een te "
            "klein extract geeft een misleidend schone uitkomst. Trek de betreffende "
            "extracten opnieuw, ruimer dan het bereik, of verhoog "
            "`[bronnen] dekking_tolerantie_m` als de lege rand klopt -- die tolerantie "
            "geldt voor alle lagen tegelijk, dus een ruime waarde heft de poort ook voor "
            "de andere bronnen op.\n"
            "Is een bron niet te klein maar ongeschikt -- bevat hij iets "
            "anders dan zijn naam suggereert -- zet hem dan uit "
            "(`bgt_waterlagen = []`, of laat `bag_pand` weg); de bijbehorende checks "
            "slaan dan over met uitleg in het rapport, wat een eerlijker antwoord is dan "
            "een uitslag op een verkeerde bron.\n" + "\n".join(tekorten)
        )


def _omhullende(
    geometrieen: tuple[BaseGeometry, ...],
) -> tuple[float, float, float, float] | None:
    """De omhullende van een verzameling geometrieen, of None als er niets in zit.

    Met min/max over de losse omhullenden en niet met `unary_union`: die berekent een
    echte unie -- op de aangeleverde BGT-panden meetbaar traag -- terwijl hier alleen
    de buitenmaat telt.
    """
    grenzen = [vorm.bounds for vorm in geometrieen if vorm is not None and not vorm.is_empty]
    if not grenzen:
        return None
    return (
        min(g[0] for g in grenzen),
        min(g[1] for g in grenzen),
        max(g[2] for g in grenzen),
        max(g[3] for g in grenzen),
    )


def _tekortregel(
    rol: str,
    bestand: str,
    omhullende: tuple[float, float, float, float],
    bereik: tuple[float, float, float, float],
    marge_m: float,
    eis: Dekkingseis,
) -> list[str]:
    """De foutregel voor een bron die het bereik niet dekt, of niets."""
    referentie = (
        bereik[0] - marge_m,
        bereik[1] - marge_m,
        bereik[2] + marge_m,
        bereik[3] + marge_m,
    )
    tekort = (
        max(0.0, omhullende[0] - referentie[0]),
        max(0.0, omhullende[1] - referentie[1]),
        max(0.0, referentie[2] - omhullende[2]),
        max(0.0, referentie[3] - omhullende[3]),
    )
    if max(tekort) <= eis.tolerantie_m:
        return []
    return [
        f"- {rol} (`{bestand}`): bron {_bbox(omhullende)}, vereist {_bbox(referentie)}; "
        f"tekort west/zuid/oost/noord = "
        f"{tekort[0]:.1f}/{tekort[1]:.1f}/{tekort[2]:.1f}/{tekort[3]:.1f} m, "
        f"toegestaan {eis.tolerantie_m:.1f} m."
    ]


def _bbox(grenzen: tuple[float, float, float, float]) -> str:
    """Een omhullende als leesbare tekst."""
    return f"({grenzen[0]:.1f}, {grenzen[1]:.1f} - {grenzen[2]:.1f}, {grenzen[3]:.1f})"


def _lees_studiegebied(
    map_pad: Path, bestand: str | None, ontbrekend: list[str], notities: list[str]
):
    """Leest de begrenzingspolygoon waarbinnen de externe bronnen gelden."""
    from nlriochecker.errors import StudyAreaError
    from nlriochecker.studiegebied import load_study_area

    if bestand is None:
        ontbrekend.append("studiegebied")
        return None, None, ""

    pad = map_pad / bestand
    if not pad.exists():
        ontbrekend.append(f"studiegebied ({pad})")
        return None, None, ""

    try:
        gebied = load_study_area(pad)
    except StudyAreaError as error:
        raise ExternalDataError(
            f"{pad}: het studiegebied is niet leesbaar ({error}). Zonder begrenzing mag "
            "geen enkele EXT-check draaien: buiten het gebied is ontbrekende brondata "
            "geen bevinding."
        ) from error

    notities.append(
        f"Bereik van de externe bronnen: {gebied.name} ({gebied.area_ha:.1f} ha, bron "
        f"`{pad.name}`). GWSW-objecten buiten dit gebied krijgen geen EXT-uitslag."
    )
    return gebied.geometry, pad, gebied.name


def _lees_rol(
    map_pad: Path,
    bestand: str | None,
    rol: str,
    laagnamen: list[str],
    ontbrekend: list[str],
    notities: list[str],
    *,
    enige_laag: bool = False,
) -> VectorLayer | None:
    """Leest de lagen die een rol vervullen en voegt ze samen tot een laag.

    `enige_laag` scheidt de twee aanroepplekken: `bag_pand`/`nwb_wegvak` leveren een
    eenlaagsbestand aan en pakken de enige laag, ook zonder laagnaam. De BGT-rollen
    dragen hun laagnaam per rol; daar is een lege lijst een uitschakeling en wordt de
    rol niet gelezen -- ongeacht het aantal lagen. Zie issue #53.
    """
    if bestand is None:
        ontbrekend.append(rol)
        return None
    pad = map_pad / bestand
    if not pad.exists():
        ontbrekend.append(f"{rol} ({pad})")
        return None

    beschikbaar = _laagnamen(pad)
    if not laagnamen:
        if not enige_laag:
            # Een rol zonder laagnaam is uitgezet of niet ingevuld; hem alsnog aan de
            # enige laag koppelen is dezelfde gok die we bij meerdere lagen afwijzen.
            ontbrekend.append(f"{rol} (geen laagnaam geconfigureerd voor deze rol)")
            return None
        if len(beschikbaar) > 1:
            # Een eenlaagsbron met meer dan een laag: gokken welke bedoeld is levert
            # stille onzin op (de eerste BGT-laag is `bak`).
            ontbrekend.append(
                f"{rol} ({pad.name} heeft {len(beschikbaar)} lagen en er is geen laagnaam "
                f"geconfigureerd voor deze rol)"
            )
            return None
    gekozen = laagnamen or beschikbaar[:1]
    bestaan = [naam for naam in gekozen if naam in beschikbaar]
    if not bestaan:
        ontbrekend.append(f"{rol} (geen van de lagen {', '.join(gekozen)} in {pad.name})")
        return None

    geometrieen: list[BaseGeometry] = []
    attributen: list[dict[str, object]] = []
    crs_naam = ""
    herprojectie: str | None = None

    for naam in bestaan:
        deel, crs_naam, herprojectie = _lees_laag(pad, naam, notities)
        for geometrie, rij in deel:
            if geometrie is None or geometrie.is_empty:
                continue
            geometrieen.append(geometrie)
            attributen.append(rij)

    if not geometrieen:
        ontbrekend.append(f"{rol} (lagen {', '.join(bestaan)} bevatten geen features)")
        return None

    return VectorLayer(
        role=rol,
        source=pad,
        layer=", ".join(bestaan),
        crs=crs_naam,
        geometries=tuple(geometrieen),
        attributes=tuple(attributen),
        tree=STRtree(geometrieen),
        reprojected_from=herprojectie,
    )


def _laagnamen(pad: Path) -> list[str]:
    """De feature-lagen in een GeoPackage."""
    import sqlite3

    try:
        verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise ExternalDataError(f"{pad}: kan niet geopend worden ({error}).") from error
    try:
        return [
            naam
            for (naam,) in verbinding.execute(
                "select table_name from gpkg_contents where data_type = 'features'"
            )
        ]
    except sqlite3.Error as error:
        raise ExternalDataError(f"{pad}: kan niet gelezen worden ({error}).") from error
    finally:
        verbinding.close()


def _lees_laag(pad: Path, laag: str, notities: list[str]):
    """Leest een enkele laag met geopandas en bewaakt het coordinaatstelsel."""
    import geopandas as gpd

    try:
        frame = gpd.read_file(pad, layer=laag)
    except Exception as error:  # pyogrio en fiona gooien uiteenlopende fouten
        raise ExternalDataError(f"{pad}: laag {laag!r} is niet leesbaar ({error}).") from error

    crs = frame.crs
    herprojectie = None
    if crs is None:
        raise ExternalDataError(
            f"{pad}: laag {laag!r} heeft geen gedefinieerd coordinaatstelsel. Zonder CRS is "
            f"niet vast te stellen of hij op de GWSW-data (EPSG:{RD_NEW}) past; aannemen dat "
            "het RD is zou stilzwijgend fout kunnen zijn."
        )
    epsg = crs.to_epsg()
    if epsg != RD_NEW:
        frame = frame.to_crs(epsg=RD_NEW)
        herprojectie = str(crs)
        notities.append(
            f"`{pad.name}` laag {laag!r} stond in {crs.to_string()} en is naar "
            f"EPSG:{RD_NEW} geherprojecteerd."
        )

    frame = _alleen_actueel(frame, pad, laag, notities)

    kolommen = [kolom for kolom in frame.columns if kolom != frame.geometry.name]
    rijen = [
        (geometrie, {kolom: rij[kolom] for kolom in kolommen})
        for geometrie, rij in zip(frame.geometry, frame.to_dict("records"), strict=False)
    ]
    return rijen, f"EPSG:{RD_NEW}", herprojectie


HISTORIEVELDEN = ("eind_registratie", "termination_date")


def _alleen_actueel(frame, pad: Path, laag: str, notities: list[str]):
    """Houdt van een BGT-laag alleen de actuele objectversies over.

    Elk BGT-object draagt zijn registratiegeschiedenis mee: de levende versie heeft
    `eind_registratie` leeg, elke afgesloten oudere versie heeft die kolom gevuld;
    `termination_date` houdt daarnaast een officieel beëindigd object buiten. Zonder
    dit filter draaien alle ruimtelijke toetsen over de hele stapel versies -- op De
    Wolden is meer dan de helft van de waterdelen oude historie (issue #58, BO-43).

    Alleen de aanwezige historievelden tellen; een laag zonder die velden (een los
    studiegebied, een waterschapsbestand) gaat ongewijzigd door. Wat afvalt komt als
    notitie in het rapport: stilte zou lezen als "alles meegenomen".
    """
    aanwezig = [veld for veld in HISTORIEVELDEN if veld in frame.columns]
    if not aanwezig:
        return frame
    actueel = frame[aanwezig].isna().all(axis=1)
    verlopen = int((~actueel).sum())
    frame = frame[actueel]
    notities.append(
        f"`{pad.name}` laag {laag!r}: "
        f"{getal(verlopen, 'verlopen objectversie', 'verlopen objectversies')} overgeslagen "
        f"({' of '.join(aanwezig)} gevuld); "
        f"{getal(len(frame), 'actuele feature', 'actuele features')} gelezen."
    )
    return frame


def _lees_raster(
    map_pad: Path, bestand: str | None, ontbrekend: list[str], notities: list[str]
) -> RasterSampler | None:
    """Opent het hoogteraster en bewaakt het coordinaatstelsel."""
    if bestand is None:
        ontbrekend.append("ahn_dtm")
        return None
    pad = map_pad / bestand
    if not pad.exists():
        ontbrekend.append(f"ahn_dtm ({pad})")
        return None

    import rasterio

    try:
        bron = rasterio.open(pad)
    except Exception as error:  # rasterio gooit uiteenlopende fouten
        raise ExternalDataError(f"{pad}: hoogteraster is niet leesbaar ({error}).") from error

    if bron.crs is None or bron.crs.to_epsg() != RD_NEW:
        gevonden = bron.crs.to_string() if bron.crs is not None else "geen"
        bron.close()
        raise ExternalDataError(
            f"{pad}: het hoogteraster staat in {gevonden} en niet in EPSG:{RD_NEW}. "
            "Herprojecteren van een raster verandert de hoogtewaarden niet maar wel hun "
            "ligging; lever het bestand in RD New aan."
        )

    notities.append(
        f"Hoogteraster `{pad.name}`: {bron.width} bij {bron.height} cellen van "
        f"{bron.res[0]:g} m in EPSG:{RD_NEW}."
    )
    return RasterSampler(
        source=pad,
        crs=f"EPSG:{RD_NEW}",
        nodata=bron.nodata,
        bounds=tuple(bron.bounds),
        reader=bron,
    )
