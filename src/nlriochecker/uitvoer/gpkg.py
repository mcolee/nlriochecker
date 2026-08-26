"""De GeoPackage-export: een zelfvoorzienend bestand per run.

Geschreven met `sqlite3` en `shapely.wkb` — dezelfde route waarmee
`studiegebied.py` een GeoPackage al *leest*, nu de schrijfkant. Dat scheelt een
afhankelijkheid en houdt lees- en schrijfkant bij elkaar.

Er zijn twee objectlagen -- `putten` en `strengen` -- met de gebreken *op* het object:
de kolom `status` draagt de uitslag in vier waarden en `popup_html` de voorgebakken
hoverpopup. Mechanisch riool staat tussen de strengen met status `grijs`, en met een
studiegebied staat de contextschil er ook grijs bij: wat de checks wel zagen maar niet
beoordeelden, hoort zichtbaar te zijn.

Het bestand is bewust zelfvoorzienend: de featurelagen bevatten genoeg samenvatting
om zonder join bruikbaar te zijn, de tabel `meldingen` draagt elke melding met haar
coordinaat, en er zijn geen GPKG-relaties of andere uitbreidingen die niet elk
GIS-pakket leest.

QGIS-stijlen worden in de tabel `layer_styles` opgeslagen en via `gpkg_contents`
geregistreerd. Zonder die registratie vindt de OGR-provider de tabel niet en
past QGIS de default-symbologie toe.
"""

from __future__ import annotations

import sqlite3
import struct
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckContext, CheckRun, Severity
from nlriochecker.checks.selectie import mechanischeleidingen
from nlriochecker.checks.treffers import Treffer
from nlriochecker.checks.verbanden import (
    Aansluitingen,
    Afvoer,
    aansluitingen,
    afvoerpad_van_streng,
    afvoerpaden,
    deelstelsel_ids,
)
from nlriochecker.dataset import Conduit, Node
from nlriochecker.errors import PipelineError
from nlriochecker.uitvoer.herkomst import PAKKET, VELD_GEREEDSCHAP, gereedschap
from nlriochecker.uitvoer.identiteit import kort
from nlriochecker.uitvoer.melding import (
    BRON_NULMETING,
    BRON_REGISTER,
    GEEN_ONDERDRUKKING,
    Melding,
    Onderdrukking,
    categorie_van,
)
from nlriochecker.uitvoer.objectkaart import (
    STATUS_ORANJE,
    STATUS_ROOD,
    Objectkop,
    bepaal_status,
    popup_html,
)
from nlriochecker.uitvoer.omvang import stelseltypen
from nlriochecker.uitvoer.stijlen.symbolen import bouw_qml
from nlriochecker.uitvoer.tabel import prepare
from nlriochecker.uitvoer.voorbehoud import markering
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang

# De GWSW-coordinaten staan in Rijksdriehoek; herprojecteren doen we niet.
RD_NEW = 28992

# 'GPKG' als big-endian ASCII, het application_id dat de spec voorschrijft.
APPLICATION_ID = 0x47504B47
USER_VERSION = 10300

CATEGORIEEN = ("TOP", "ADM", "ATTR", "HGT", "NET", "RVZ", "BTR", "EXT", "NULMETING")

RICHTING_MEE = "mee"
RICHTING_TEGEN = "tegen"
RICHTING_ONBEKEND = "onbekend"

FEATURELAGEN = (
    "putten",
    "strengen",
    "vlakken",
    "gemengd_zonder_overstort",
)

# De relaties van EXT-001, van zwaar naar licht. De laag toont de sterkste over de
# meldingen die naar hetzelfde bouwwerk verwijzen.
RELATIE_STERKTE = ("binnen", "kruist", "nabij")

# Waarom een object grijs is. De popup noemt de reden; grijs zonder reden leest als
# "in orde", en dat is het niet.
REDEN_MECHANISCH = "mechanisch riool, dat de meeste checks overslaan"
REDEN_SCHIL = "ligt naast het studiegebied en niet erin"
# De projectconfiguratie houdt de meldingen van deze klasse uit de stroom (BO-49). Niet
# hetzelfde als "mechanisch": dat zegt dat de checks er grotendeels overheen lopen, dit
# dat de uitkomst bewust niet gerapporteerd wordt -- ook op een klasse die wel getoetst is.
# De reden is een eigenschap van de klasse en niet van dit object: hij staat er ook op een
# object waarop niets gevonden was, en mag dus geen weggevallen meldingen suggereren.
REDEN_ONDERDRUKT = (
    "klasse onderdrukt in de projectconfiguratie; meldingen erop komen niet in de uitvoer"
)
# Deze reden geldt niet voor een object maar voor de hele run: zonder klassenhierarchie
# heeft de lader knopen en strengen op geometrie herkend en draaiden de checks over een
# onvolledige selectie. Groen zou hier "beoordeeld en niets gevonden" beweren, terwijl
# er niets beoordeeld is; grijs is precies de waarde die dat zegt.
REDEN_GEEN_KLASSENHIERARCHIE = (
    "deze run kende de klassenhierarchie niet; de checks draaiden over een onvolledige selectie"
)
RD_WKT = (
    'PROJCS["Amersfoort / RD New",GEOGCS["Amersfoort",DATUM["Amersfoort",'
    'SPHEROID["Bessel 1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Oblique_Stereographic"],'
    'PARAMETER["latitude_of_origin",52.15616055555555],'
    'PARAMETER["central_meridian",5.38763888888889],'
    'PARAMETER["scale_factor",0.9999079],PARAMETER["false_easting",155000],'
    'PARAMETER["false_northing",463000],UNIT["metre",1],AUTHORITY["EPSG","28992"]]'
)


# De stappen van de GeoPackage-fase, in de volgorde waarin ze gezet worden. Het
# fase-totaal was een met de hand geteld getal dat over drie functies verspreid
# stond; liep het uit de pas met de `stap()`-aanroepen, dan telde de balk over of
# stopte hij te vroeg. `tests/test_uitvoer_gpkg.py` toetst dat de gezette labels
# precies deze rij zijn.
GEOPACKAGE_STAPPEN = (
    "putten",
    "strengen",
    "vlakken",
    "gemengd_zonder_overstort",
    "meldingen",
    "overzicht_checks",
    "gwsw_run",
    "layer_styles",
)


@dataclass(frozen=True)
class _Kolom:
    """Een kolom van een laag: naam en SQLite-type."""

    naam: str
    type: str


@dataclass(frozen=True)
class _LaagTellingen:
    """Het aantal objecten dat daadwerkelijk in elke featurelaag terechtkwam.

    Voor de runmetadata: niet het aantal in de dataset, maar wat er na het
    studiegebied en het ontbreken van geometrie echt is weggeschreven.
    """

    putten: int
    # Alle lijnen in de laag `strengen`, mechanisch riool en contextschil inbegrepen.
    strengen: int
    # Hoeveel van die lijnen mechanisch riool zijn; ze staan sinds issue #13 tussen de
    # strengen met status `grijs` in plaats van in een eigen laag.
    mechanisch: int
    # De externe vlakken (pand, bouwwerk, water) waarnaar een EXT-melding wijst; sinds
    # issue #67 één laag `vlakken` in plaats van `bouwwerken` en `waterdelen_zonder_zinker`.
    vlakken: int
    # De gemengde deelstelsels waarop RVZ-006 aansloeg en die een vlak kregen (issue
    # #75).
    gemengd_zonder_overstort: int
    # En de deelstelsels waarop RVZ-006 wél aansloeg maar die geen vlak konden krijgen,
    # omdat geen enkele streng ervan een bruikbare lijn draagt. Ze staan in geen enkele
    # rij van de laag; zonder deze telling zou "dit deelstelsel bestaat niet" niet van
    # "we konden het niet tekenen" te onderscheiden zijn.
    gemengd_zonder_vlak: int


def schrijf_geopackage(
    run: CheckRun,
    meldingen: list[Melding],
    output_dir: Path,
    run_datum: date,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
) -> Path:
    """Schrijft de GeoPackage van deze run en geeft het pad terug.

    Is er een studiegebied, dan is dat de grens van het bestand: de featurelagen
    bevatten alleen objecten binnen of snijdend met het gebied. De checks draaiden
    op de kern plus de contextschil (ruim genoeg voor randeffectvrije netwerkchecks),
    dus wat hier buiten valt is bewust weggelaten, niet over het hoofd gezien.

    `onderdrukking` komt uit de meldingenstroom en is de enige bron voor beide dingen
    die zij hier bepaalt: welke objecten grijs worden met `REDEN_ONDERDRUKT` en wat
    `gwsw_run` daarover meldt. De meldingen die `[rapport]` wegliet zitten niet in
    `meldingen`, en zonder die telling zou het bestand niet zeggen dat er iets
    weggelaten is (BO-49).
    """
    output_dir = prepare(output_dir)
    doel = _doelpad(run, output_dir, run_datum)
    doel.unlink(missing_ok=True)

    binnen = run.objecten_binnen()
    # `connect` staat binnen de try: faalde hij ervoor, dan werd `einde_fase` nooit
    # geroepen en kreeg de gebruiker na de foutmelding een terminal zonder cursor
    # terug -- die zet click pas bij het afsluiten van de balk weer aan.
    voortgang.start_fase("GeoPackage", len(GEOPACKAGE_STAPPEN))
    verbinding: sqlite3.Connection | None = None
    try:
        verbinding = sqlite3.connect(doel)
        _leg_fundament(verbinding)
        tellingen = _schrijf_features(
            verbinding, run, meldingen, binnen, run_datum, voortgang, onderdrukking
        )
        _schrijf_meldingen(verbinding, meldingen)
        voortgang.stap(label="meldingen")
        _schrijf_overzicht(verbinding, run, meldingen)
        voortgang.stap(label="overzicht_checks")
        _schrijf_runmetadata(verbinding, run, meldingen, run_datum, tellingen, onderdrukking)
        voortgang.stap(label="gwsw_run")
        _schrijf_stijlen(verbinding)
        voortgang.stap(label="layer_styles")
        verbinding.commit()
    finally:
        if verbinding is not None:
            verbinding.close()
        voortgang.einde_fase()
    return doel


def _doelpad(run: CheckRun, output_dir: Path, run_datum: date) -> Path:
    """`dq_<dataset>_<rundatum>.gpkg`, en nooit over een invoerbestand heen."""
    naam = f"dq_{run.dataset.source.stem}_{run_datum:%Y%m%d}.gpkg"
    doel = Path(output_dir) / naam
    if doel.resolve() == run.dataset.source.resolve():
        raise PipelineError(
            f"{doel}: de uitvoer zou een invoerbestand overschrijven. Kies een andere uitvoermap."
        )
    if doel.resolve().parent == run.dataset.source.resolve().parent:
        raise PipelineError(
            f"{doel}: de uitvoermap is de map met invoerbestanden. Kies een andere uitvoermap."
        )
    return doel


# --------------------------------------------------------------------------- #
# Het GeoPackage-fundament
# --------------------------------------------------------------------------- #


def _leg_fundament(verbinding: sqlite3.Connection) -> None:
    """Maakt de tabellen aan die de GeoPackage-spec verplicht stelt."""
    verbinding.execute(f"pragma application_id = {APPLICATION_ID}")
    verbinding.execute(f"pragma user_version = {USER_VERSION}")
    verbinding.execute(
        "create table gpkg_spatial_ref_sys ("
        "srs_name text not null, srs_id integer primary key, organization text not null, "
        "organization_coordsys_id integer not null, definition text not null, description text)"
    )
    verbinding.executemany(
        "insert into gpkg_spatial_ref_sys values (?, ?, ?, ?, ?, ?)",
        [
            ("Undefined cartesian SRS", -1, "NONE", -1, "undefined", None),
            ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
            ("WGS 84 geodetic", 4326, "EPSG", 4326, "GEOGCS unsupported", None),
            ("Amersfoort / RD New", RD_NEW, "EPSG", RD_NEW, RD_WKT, "Rijksdriehoek"),
        ],
    )
    verbinding.execute(
        "create table gpkg_contents ("
        "table_name text primary key, data_type text not null, identifier text unique, "
        "description text default '', last_change text not null, "
        "min_x double, min_y double, max_x double, max_y double, srs_id integer)"
    )
    verbinding.execute(
        "create table gpkg_geometry_columns ("
        "table_name text not null, column_name text not null, geometry_type_name text not null, "
        "srs_id integer not null, z tinyint not null, m tinyint not null, "
        "primary key (table_name, column_name))"
    )


def _maak_featurelaag(
    verbinding: sqlite3.Connection,
    naam: str,
    soort: str,
    kolommen: list[_Kolom],
    omschrijving: str,
) -> None:
    """Maakt een tabel met geometrie aan en registreert hem."""
    velden = ", ".join(f'"{kolom.naam}" {kolom.type}' for kolom in kolommen)
    verbinding.execute(
        f'create table "{naam}" (fid integer primary key autoincrement, geom blob, {velden})'
    )
    verbinding.execute(
        "insert into gpkg_geometry_columns values (?, 'geom', ?, ?, 0, 0)", (naam, soort, RD_NEW)
    )
    _registreer(verbinding, naam, "features", omschrijving)


def _maak_attribuuttabel(
    verbinding: sqlite3.Connection, naam: str, kolommen: list[_Kolom], omschrijving: str
) -> None:
    """Maakt een tabel zonder geometrie aan en registreert hem."""
    velden = ", ".join(f'"{kolom.naam}" {kolom.type}' for kolom in kolommen)
    verbinding.execute(f'create table "{naam}" (fid integer primary key autoincrement, {velden})')
    _registreer(verbinding, naam, "attributes", omschrijving)


def _registreer(verbinding: sqlite3.Connection, naam: str, soort: str, omschrijving: str) -> None:
    """Zet een laag in gpkg_contents.

    `last_change` is ISO-8601 met T en Z, en een tabel zonder geometrie krijgt geen
    srs_id; beide schrijft de GeoPackage-spec zo voor. GDAL is er soepel in, maar
    strengere validators niet.
    """
    verbinding.execute(
        "insert into gpkg_contents (table_name, data_type, identifier, description, "
        "last_change, srs_id) values (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)",
        (naam, soort, naam, omschrijving, RD_NEW if soort == "features" else None),
    )


def _zet_omhullende(
    verbinding: sqlite3.Connection, naam: str, grenzen: list[tuple[float, float, float, float]]
) -> None:
    """Vult de bounding box van een featurelaag in gpkg_contents.

    De grenzen komen van de aanroeper, die de geometrieen toch al in handen had;
    ze terugvragen uit de database zou tienduizenden blobs opnieuw laten ontleden.
    """
    if not grenzen:
        return
    verbinding.execute(
        "update gpkg_contents set min_x = ?, min_y = ?, max_x = ?, max_y = ? where table_name = ?",
        (
            min(g[0] for g in grenzen),
            min(g[1] for g in grenzen),
            max(g[2] for g in grenzen),
            max(g[3] for g in grenzen),
            naam,
        ),
    )


def _als_multipolygon(geometrie: BaseGeometry) -> BaseGeometry:
    """Promoveert een enkele polygoon naar een MultiPolygon.

    De trefferlagen zijn als `MULTIPOLYGON` gedeclareerd. GDAL leest een `POLYGON` daar
    zonder morren, maar de GeoPackage-spec wil een feature van het gedeclareerde type;
    promoveren kost niets en houdt het bestand ook voor strengere lezers geldig.
    """
    if geometrie.geom_type == "Polygon":
        return MultiPolygon([geometrie])
    return geometrie


def _blob(geometrie: BaseGeometry) -> bytes:
    """Verpakt een geometrie in het GeoPackage-binaire formaat.

    Kop: magic 'GP', versie 0, vlaggen 0x01 (little endian, geen envelope), het
    srs_id als int32, dan de gewone WKB. Precies wat `studiegebied._ontleed_gpkg()`
    terugleest.
    """
    return b"GP" + bytes([0, 1]) + struct.pack("<i", RD_NEW) + geometrie.wkb


# --------------------------------------------------------------------------- #
# De lagen
# --------------------------------------------------------------------------- #


def _richting_bob(run: CheckRun, conduit: Conduit, config: CheckConfig) -> tuple[str, float | None]:
    """De BOB-richting ten opzichte van de getekende lijn, en het verval erlangs.

    Het BOB-verval is administratief: van beginpunt naar eindpunt. De pijl op de
    kaart volgt de getekende lijn. Loopt de lijn andersom dan de administratie, dan
    keert het teken om -- anders zou de kaart het tegenovergestelde tonen van wat er
    staat.

    Is de tekenrichting niet te bepalen (`richting_van_geometrie` geeft None: geen
    lijngeometrie, geen herleidbare putten, of dezelfde put aan beide zijden), dan is
    er geen richting om het administratieve verval tegen te spiegelen. Dan valt
    stilzwijgend terugvallen op het administratieve teken *niet* terug op iets
    juists: de kolom staat gedocumenteerd als het verval langs de getekende lijn, en
    zonder bekende tekenrichting is er geen waarde die dat eerlijk uitdrukt. De rij
    krijgt dan `onbekend` met een lege waarde, net als bij een ontbrekend of nul
    BOB-verval.

    Deze functie weet niets van mechanisch riool: dat de *pijl* daar wegvalt is een
    besluit van de schrijver en staat op de enige plek waar de mechanische populatie
    bekend is (`_schrijf_features`, issue #74). Het verval zelf blijft er wel staan.
    """
    verval = conduit.bob_verval
    if verval is None or verval == 0.0:
        return RICHTING_ONBEKEND, verval
    uitslag = run.dataset.richting_van_geometrie(conduit, config.klassen.netwerkknopen)
    if uitslag is None:
        return RICHTING_ONBEKEND, None
    langs_lijn = -verval if uitslag[0] else verval
    return (RICHTING_MEE if langs_lijn > 0 else RICHTING_TEGEN), langs_lijn


def _samenvatting_kolommen() -> list[_Kolom]:
    """De kolommen van `putten` en `strengen`."""
    return [
        _Kolom("feature_id", "text"),
        _Kolom("label", "text"),
        _Kolom("objecttype", "text"),
        _Kolom("stelsel", "text"),
        # Het aanlegjaar uit `Begindatum`, om op te filteren; leeg als het object er
        # geen draagt (ATTR-018 meldt dat dan). Het jaar en niet de datum, net als de
        # rest van de code (`Conduit.begindatum_jaar`).
        _Kolom("begindatum_jaar", "integer"),
        _Kolom("richting_bob", "text"),
        _Kolom("bob_verval_m", "real"),
        # Het benedenstroomse uitstroompunt dat dit object bereikt, met de padmaat
        # ernaartoe (#18, fase 1). `afvoer_eindpunt` draagt het label of anders de URI;
        # leeg als er geen pad is. `afvoer_meters` is leeg zonder bruikbare lijn op het
        # pad, `afvoer_stappen` telt de strengen erin.
        _Kolom("afvoer_eindpunt", "text"),
        _Kolom("afvoer_meters", "real"),
        _Kolom("afvoer_stappen", "integer"),
        _Kolom("gebied", "text"),
        _Kolom("status", "text"),
        _Kolom("ergste_ernst", "text"),
        _Kolom("n_fout", "integer"),
        _Kolom("n_waarschuwing", "integer"),
        _Kolom("n_systemisch", "integer"),
        _Kolom("checks_f", "text"),
        _Kolom("checks_w", "text"),
        *[_Kolom(f"n_{naam.lower()}", "integer") for naam in CATEGORIEEN],
        _Kolom("prioriteit", "integer"),
        _Kolom("run_datum", "text"),
        _Kolom("dataset_versie", "text"),
        _Kolom("register_versie", "text"),
        _Kolom("gwsw_uri", "text"),
        _Kolom("popup_html", "text"),
    ]


def _mechanische_uris(run: CheckRun) -> frozenset[str]:
    """De verbindingen die tot het mechanische stelsel horen.

    Het merendeel van de checks slaat ze over -- het checkregister rekent mechanisch
    riool niet tot zijn bereik -- maar niet alle: TOP-010 en TOP-011 draaien er wel op,
    en de SHACL-nulmeting sowieso. Daarom krijgen ze status `grijs` alleen zolang er
    niets op staat; wat er wel op staat kleurt ze (zie `objectkaart.bepaal_status`).
    Zonder die uitzondering zou 'geen kleur' hier als 'getoetst en in orde' lezen.

    De selectie komt uit `checks/selectie.py` en leest `run.context`: exact de
    context waarmee de checks draaiden -- onder een studiegebied dus de kern plus
    de contextschil -- inclusief haar cache.
    """
    return frozenset(conduit.uri for conduit in mechanischeleidingen(run.context))


def _onderdrukte_uris(run: CheckRun, klassen: tuple[str, ...]) -> frozenset[str]:
    """De objecten waarvan `[rapport]` de meldingen uit de stroom houdt (BO-49).

    De klassen komen uit de meegegeven `Onderdrukking` en niet uit `run.config`: dan
    hebben de grijze objecten en de telling in `gwsw_run` dezelfde bron, en kan een
    beller die de stroom zelf samenstelde geen bestand krijgen waarin objecten grijs
    staan met een reden die de runtabel niet noemt.

    Niet uit de meldingen: een object van een onderdrukte klasse hoort ook grijs te lezen
    als er toevallig niets op stond. Anders zou de kaart bij het ene object "niet
    gerapporteerd" en bij het andere "beoordeeld en in orde" zeggen op grond van
    hetzelfde besluit.
    """
    return frozenset(uri for wortel in klassen for uri in run.dataset.of_class(wortel))


def _schrijf_features(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    binnen: frozenset[str] | None,
    run_datum: date,
    voortgang: Voortgang = NUL_VOORTGANG,
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
) -> _LaagTellingen:
    """Schrijft de twee objectlagen plus de vlakkenlaag met externe objecten.

    Naast de beoordeelde objecten komt erin wat de checks wel zagen maar niet
    beoordeelden: mechanisch riool, dat volgens het checkregister buiten scope valt,
    de klassen uit `onderdrukking`, en de contextschil van een studiegebied. Alle drie
    krijgen status `grijs` met de reden in hun popup. Ze weglaten zou de kaart bij de
    gebiedsgrens laten ophouden alsof daar niets ligt, en een lege mechanische laag zou
    als "geen mechanisch riool aanwezig" lezen.

    Kende de run de klassenhierarchie niet, dan geldt dat voor *elk* object: de checks
    hebben dan over een onvolledige selectie gedraaid en er valt niets te beoordelen.
    De hele kaart wordt dan grijs waar zij anders groen was. Het voorbehoud staat ook
    in `gwsw_run`, maar dat is een metadatatabel die niemand in QGIS openslaat, en een
    groene kaart eronder zou het tegenovergestelde uitstralen.

    De grijze context is `Analyseset.buffer`: de objecten die binnen de buffer om het
    gebied liggen. Niet de hele schil -- daar hoort ook de samenhangende
    vrijvervalcomponent bij, en die kan in een stad het halve net zijn, zodat elk
    buurtbestand met het net van de hele stad zou worden opgezadeld. En niet "alles wat
    niet in de kern ligt": een run die met `beperk_tot_studiegebied` op de volledige
    export is afgebakend heeft geen analyseset, en dan hoort het bestand bij de
    gebiedsgrens op te houden zoals het altijd deed.
    """
    kolommen = _samenvatting_kolommen()
    _maak_featurelaag(
        verbinding,
        "putten",
        "POINT",
        kolommen,
        "Knooppunten met de uitslag per object; `status` draagt hem in vier waarden.",
    )
    _maak_featurelaag(
        verbinding,
        "strengen",
        "LINESTRING",
        kolommen,
        "Verbindingen met de uitslag per object; mechanisch riool en een onderdrukte "
        "klasse staan er grijs bij.",
    )

    per_object = _meldingen_per_object(meldingen)
    metadata = _metadata(run, run_datum)
    stelsels = stelseltypen(run)
    config = run.config
    mechanisch = _mechanische_uris(run)
    onderdrukt = _onderdrukte_uris(run, onderdrukking.klassen)
    ring = run.analyseset.buffer if run.analyseset is not None else frozenset()
    geen_hierarchie = not run.dataset.klassenhierarchie_bekend
    # Het afvoerpad per knoop, uit `run.context`: de NET-checks hebben de graaf daar
    # al gebouwd, en de strengen leunen erop via `afvoerpad_van_streng`, dat
    # dezelfde gecachte uitkomst leest.
    afvoer_per_knoop = afvoerpaden(run.context)

    tellingen: dict[str, int] = {}
    mechanisch_geschreven = 0
    for laag, verzameling, geometrie_veld in (
        ("putten", run.dataset.nodes, "point"),
        ("strengen", run.dataset.conduits, "line"),
    ):
        rijen = []
        grenzen: list[tuple[float, float, float, float]] = []
        # Gesorteerd, niet in de volgorde van het woordenboek: anders wisselen
        # rijvolgorde en fid-toekenning tussen twee runs op dezelfde data.
        for uri in sorted(verzameling):
            if binnen is not None and uri not in binnen and uri not in ring:
                continue
            object_ = verzameling[uri]
            geometrie = getattr(object_, geometrie_veld)
            if geometrie is None or geometrie.is_empty:
                continue
            grenzen.append(geometrie.bounds)
            is_mechanisch = uri in mechanisch
            richting, verval = (
                _richting_bob(run, object_, config) if isinstance(object_, Conduit) else ("", None)
            )
            # Een mechanische leiding is pompgestuurd: het water loopt er niet met het
            # bodemverval mee, dus een groene of rode pijl zou een stroomrichting tekenen
            # die er fysiek niet is (issue #74). Alleen de pijl vervalt -- het verval zelf
            # blijft in `bob_verval_m` staan, want dat is een gemeten waarde en geen
            # bewering over de stroomrichting. De popupregel zegt waarom er geen pijl is;
            # zonder die eigen tekst zou hij "niet te bepalen" beweren waar de leiding er
            # domweg geen heeft.
            if is_mechanisch:
                richting, richting_woord = RICHTING_ONBEKEND, RICHTING_MECHANISCH
            else:
                richting_woord = richting
            afvoer_eindpunt, afvoer_meters, afvoer_stappen = _afvoer_velden(
                run.context, afvoer_per_knoop, uri, object_
            )
            reden = _reden_niet_beoordeeld(uri, binnen, onderdrukt, mechanisch, geen_hierarchie)
            if is_mechanisch:
                mechanisch_geschreven += 1
            rijen.append(
                (
                    _blob(geometrie),
                    *_samenvatting(
                        run,
                        uri,
                        object_,
                        per_object.get(uri, []),
                        metadata,
                        stelsel=stelsels.get(uri, ""),
                        richting_bob=richting,
                        richting_woord=richting_woord,
                        bob_verval_m=verval,
                        afvoer_eindpunt=afvoer_eindpunt,
                        afvoer_meters=afvoer_meters,
                        afvoer_stappen=afvoer_stappen,
                        reden=reden,
                    ),
                )
            )
        if rijen:
            plaatshouders = ", ".join("?" * (len(kolommen) + 1))
            velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
            verbinding.executemany(
                f'insert into "{laag}" (geom, {velden}) values ({plaatshouders})', rijen
            )
        _zet_omhullende(verbinding, laag, grenzen)
        tellingen[laag] = len(rijen)
        voortgang.stap(label=laag)

    vlakken = _schrijf_treffers(verbinding, run, meldingen, voortgang)
    gemengd, zonder_vlak = _schrijf_gemengd_zonder_overstort(
        verbinding, run, config, meldingen, voortgang
    )

    return _LaagTellingen(
        putten=tellingen["putten"],
        strengen=tellingen["strengen"],
        mechanisch=mechanisch_geschreven,
        vlakken=vlakken,
        gemengd_zonder_overstort=gemengd,
        gemengd_zonder_vlak=zonder_vlak,
    )


def _afvoer_velden(
    context: CheckContext,
    afvoer_per_knoop: dict[str, Afvoer],
    uri: str,
    object_: object,
) -> tuple[str, float | None, int | None]:
    """De drie afvoerpadvelden van een object: uitstroompunt, meters en stappen.

    Een streng leest het pad vanaf haar eigen eindpunt (`afvoerpad_van_streng`), een
    put het pad vanaf zichzelf. Zonder pad naar enig uitstroompunt zijn alle drie leeg.
    Het uitstroompunt draagt het label, en anders de URI als er geen label is.
    """
    pad = (
        afvoerpad_van_streng(context, object_)
        if isinstance(object_, Conduit)
        else afvoer_per_knoop.get(uri)
    )
    if pad is None:
        return "", None, None
    node = context.dataset.nodes.get(pad.eindpunt)
    label = node.label if node is not None and node.label else pad.eindpunt
    return label, pad.meters, pad.stappen


def _reden_niet_beoordeeld(
    uri: str,
    binnen: frozenset[str] | None,
    onderdrukt: frozenset[str],
    mechanisch: frozenset[str],
    geen_klassenhierarchie: bool = False,
) -> str:
    """Waarom dit object buiten de beoordeling viel, of leeg als het erbinnen lag.

    Onderdrukking gaat vóór mechanisch: ook een niet-mechanische onderdrukte klasse hoort
    grijs te lezen en niet groen; voor De Wolden vallen de twee samen.

    Mechanisch riool gaat voor de ring: het wordt door de meeste checks overgeslagen,
    ook binnen de kern, en dat is de scherpere reden om te noemen. De reden staat er
    ook als het object toch een melding draagt -- dan is het niet grijs maar wel maar
    deels beoordeeld, en de popup zegt dat.

    Het runbrede voorbehoud komt achteraan, en juist omdat het voor elk object geldt:
    het staat al in `gwsw_run` en boven het rapport, terwijl "mechanisch" en "schil"
    dit ene object van zijn buren onderscheiden. Voor de status maakt de volgorde niet
    uit -- elke reden zet hem op grijs zolang er niets op het object staat.
    """
    if uri in onderdrukt:
        return REDEN_ONDERDRUKT
    if uri in mechanisch:
        return REDEN_MECHANISCH
    if binnen is not None and uri not in binnen:
        return REDEN_SCHIL
    if geen_klassenhierarchie:
        return REDEN_GEEN_KLASSENHIERARCHIE
    return ""


# De EXT-checks die een extern vlak aanwijzen. Alleen hun meldingen worden op het
# trefferregister gejoind; een andere check met een `object2_uri` (een SHACL-paar) wijst
# geen extern object aan en hoort niet in deze laag.
VLAK_CHECKS = ("EXT-001", "EXT-002", "EXT-003")

# De soort van een vlak volgt op één plek uit `Treffer.bron`: de rol waarmee de check hem
# registreerde. Panden komen uit twee bronnen (BGT en BAG) maar zijn dezelfde soort.
VLAK_SOORT = {
    "bgt_pand": "pand",
    "bag_pand": "pand",
    "bgt_bouwwerk": "bouwwerk",
    "bgt_water": "water",
}


def _vlak_kolommen() -> list[_Kolom]:
    """De kolommen van de laag `vlakken`.

    Eén laag voor de drie soorten externe vlakken (pand, bouwwerk, water). `relatie` en
    `afstand_min_m` gelden alleen voor pand en bouwwerk (EXT-001) en blijven leeg bij
    water; `buffer_m` uit de oude waterdelenlaag vervalt -- dat is runmetadata en staat
    in `gwsw_run`.
    """
    return [
        _Kolom("id", "text"),
        _Kolom("soort", "text"),
        _Kolom("subtype", "text"),
        _Kolom("bron", "text"),
        _Kolom("bronbestand", "text"),
        _Kolom("label", "text"),
        _Kolom("relatie", "text"),
        _Kolom("afstand_min_m", "real"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("check_ids", "text"),
    ]


def _vlak_subtype(treffer: Treffer) -> str:
    """Het subtype van een vlak: voor water het BGT-type, anders de BGT-functie of het BGT-type.

    Voor water leest de check het BGT-`type`-veld in `Treffer.label` (waterloop, greppel);
    voor pand en bouwwerk staat het BGT-type in `Treffer.attributen` onder `type`. Panden
    dragen die kolom vaak niet en krijgen dan een leeg subtype.
    """
    if treffer.bron == "bgt_water":
        return treffer.label
    return str(treffer.attributen.get("type") or "")


def _vlak_label(treffer: Treffer) -> str:
    """Een leesbaar label voor een vlak.

    Voor water is dat het type plus de identificatie (`_waterdeel_aanduiding`); voor pand
    en bouwwerk draagt `Treffer.label` de aanduiding die EXT-001 al maakte.
    """
    if treffer.bron == "bgt_water":
        return _waterdeel_aanduiding(treffer)
    return treffer.label


def _schrijf_treffers(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    voortgang: Voortgang,
) -> int:
    """Schrijft de laag `vlakken`: de externe objecten waarnaar de EXT-meldingen verwijzen.

    Eén laag voor pand, bouwwerk en water (issue #67); de soort staat in de kolom `soort`
    en volgt uit `Treffer.bron`. Een waterdeel dat zowel EXT-002 als EXT-003 raakt krijgt
    één rij met beide check-ID's; een waterdeel dat alleen EXT-002 ziet -- een echte
    doorkruising door een geregistreerde zinker -- krijgt sindsdien ook een vlak, omdat
    EXT-002 zijn treffer nu registreert.

    Strikte aansluiting: de rijen komen uit de meldingen van déze uitvoer, gejoind op
    het trefferregister van de run (`checks/treffers.py`). Deze schrijver bevraagt
    geen externe bron en doet geen ruimtelijke selectie, dus laag en testuitkomst
    kunnen niet uit elkaar lopen. Bij rapportage per studiegebied-feature betekent dat
    vanzelf: per gebied alleen de treffers van dat gebied, en een pand op de
    buurtgrens in beide bestanden.

    Eén beperking erft mee uit de detectie en wordt bewust niet gerepareerd: EXT-001
    meldt per object alleen het sterkste bouwwerk (BO-17). De watergangcheck geeft
    sinds BO-43 elke echte doorkruising terug, ook meerdere per streng.
    """
    kolommen = _vlak_kolommen()
    _maak_featurelaag(
        verbinding,
        "vlakken",
        "MULTIPOLYGON",
        kolommen,
        "Externe vlakken (BGT-panden, overige bouwwerken en BGT-waterdelen) waarnaar een "
        "EXT-melding verwijst; de soort staat in de kolom `soort`.",
    )
    aantal = _vul_trefferlaag(
        verbinding,
        run,
        "vlakken",
        kolommen,
        _groepeer_op_treffer(meldingen, *VLAK_CHECKS),
        lambda treffer, verwijzend: (
            treffer.sleutel,
            VLAK_SOORT[treffer.bron],
            _vlak_subtype(treffer),
            treffer.bron,
            treffer.bronbestand,
            _vlak_label(treffer),
            _sterkste_relatie(verwijzend),
            _kleinste_afstand(run, treffer.sleutel, verwijzend),
            len(verwijzend),
            _check_ids(verwijzend),
        ),
    )
    voortgang.stap(label="vlakken")
    return aantal


def _groepeer_op_treffer(meldingen: list[Melding], *check_ids: str) -> dict[str, list[Melding]]:
    """De meldingen van de gegeven checks, gegroepeerd op het externe object dat ze aanwijzen.

    Twee checks kunnen naar hetzelfde vlak wijzen (EXT-002 en EXT-003 naar één waterdeel);
    ze belanden dan in dezelfde groep en de rij draagt beide check-ID's.
    """
    gekozen = set(check_ids)
    per_treffer: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        if melding.check_id in gekozen and melding.object2_uri:
            per_treffer[melding.object2_uri].append(melding)
    return per_treffer


def _vul_trefferlaag(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    laag: str,
    kolommen: list[_Kolom],
    per_treffer: dict[str, list[Melding]],
    rij_van: Callable[[Treffer, list[Melding]], tuple[object, ...]],
) -> int:
    """Schrijft een trefferlaag en levert het aantal rijen terug.

    Een melding die een extern object aanwijst dat niet in het register staat, is een
    gebroken afspraak: de check heeft de verwijzing wel gezet maar de treffer niet
    geregistreerd, en dan zou de laag stil kleiner zijn dan de uitslag. Dat is precies
    de afwijking die dit ontwerp uitsluit, dus faalt het luid in plaats van de rij over
    te slaan.
    """
    rijen = []
    ontbreekt: list[str] = []
    grenzen: list[tuple[float, float, float, float]] = []
    for sleutel in sorted(per_treffer):
        treffer = run.treffers.get(sleutel)
        if treffer is None:
            ontbreekt.append(sleutel)
            continue
        if treffer.geometrie.is_empty:
            continue
        grenzen.append(treffer.geometrie.bounds)
        rijen.append(
            (_blob(_als_multipolygon(treffer.geometrie)), *rij_van(treffer, per_treffer[sleutel]))
        )

    if ontbreekt:
        raise PipelineError(
            f"laag {laag!r}: {len(ontbreekt)} melding(en) verwijzen naar een extern object "
            f"dat niet in het trefferregister van deze run staat "
            f"({', '.join(sorted(ontbreekt)[:5])}). De laag zou stil kleiner zijn dan de "
            f"uitslag; controleer of de check zijn treffer registreert."
        )

    if rijen:
        velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
        plaatshouders = ", ".join("?" * (len(kolommen) + 1))
        verbinding.executemany(
            f'insert into "{laag}" (geom, {velden}) values ({plaatshouders})', rijen
        )
    _zet_omhullende(verbinding, laag, grenzen)
    return len(rijen)


def _sterkste_relatie(meldingen: list[Melding]) -> str:
    """De zwaarste relatie over de verwijzende meldingen: binnen > kruist > nabij.

    De relatie staat in het meldingveld `waarde`, dat EXT-001 al vulde; er wordt hier
    niets uit een `Finding` opnieuw afgeleid.
    """
    relaties = [melding.waarde for melding in meldingen if melding.waarde in RELATIE_STERKTE]
    if not relaties:
        return ""
    return min(relaties, key=RELATIE_STERKTE.index)


def _kleinste_afstand(run: CheckRun, sleutel: str, meldingen: list[Melding]) -> float | None:
    """De kleinste afstand over de verwijzende meldingen, of None.

    `Melding` draagt de afstand niet -- die zit in `Finding.details` en komt daar niet
    doorheen -- dus hij komt uit het trefferregister, opgezocht op de drie velden die
    elke melding wel draagt.
    """
    afstanden = [
        afstand
        for melding in meldingen
        if (afstand := run.treffers.afstand(sleutel, melding.check_id, melding.object_uri))
        is not None
    ]
    return min(afstanden) if afstanden else None


def _waterdeel_aanduiding(treffer: Treffer) -> str:
    """Een leesbare aanduiding van een waterdeel: het type plus zijn identificatie.

    De kolom `subtype` draagt het type kaal, zodat je erop kunt filteren; dit label is
    voor de lezer, en die heeft aan "waterloop" alleen niet genoeg om er een terug te
    vinden.
    """
    return f"{treffer.label} {treffer.sleutel.split('/')[-1]}".strip()


def _check_ids(meldingen: list[Melding]) -> str:
    """De checks die naar deze treffer verwijzen, gesorteerd."""
    return ", ".join(sorted({melding.check_id for melding in meldingen}))


# De check waarvan de bevindingen de laag `gemengd_zonder_overstort` vullen. Eén laag,
# één check: elke rij is een gemengd deelstelsel waarop RVZ-006 aansloeg.
CHECK_GEMENGD_ZONDER_OVERSTORT = "RVZ-006"

# Wat de popup boven de meldingenlijst als objecttype toont. Geen GWSW-klassenaam: een
# gemengd deelstelsel is geen GWSW-object maar een afleiding uit de graaf, en die naam
# hoort dat te zeggen in plaats van een klasse te suggereren die niet bestaat.
SOORT_GEMENGD_DEELSTELSEL = "gemengd deelstelsel"


def _gemengd_kolommen() -> list[_Kolom]:
    """De kolommen van de laag `gemengd_zonder_overstort`."""
    return [
        # Het deelstelsel-ID dat RVZ-006, NET-001 en NET-002 delen (`deelstelsel_ids`);
        # ook de sleutel waarop de meldingen van deze laag te koppelen zijn.
        _Kolom("cluster_id", "text"),
        _Kolom("n_knopen", "integer"),
        _Kolom("n_strengen", "integer"),
        _Kolom("strenglengte_m", "real"),
        # Het aantal RVZ-006-meldingen op dit deelstelsel: één per gemengde streng.
        _Kolom("n_meldingen", "integer"),
        _Kolom("popup_html", "text"),
    ]


def _schrijf_gemengd_zonder_overstort(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    config: CheckConfig,
    meldingen: list[Melding],
    voortgang: Voortgang,
) -> tuple[int, int]:
    """Schrijft de laag `gemengd_zonder_overstort`; geeft rijen en niet-tekenbare terug.

    Een vlak per gemengd deelstelsel waarop RVZ-006 aansloeg (issue #75): de buffer om
    de vrijvervalstrengen van de hele samenhangende component, samengevoegd tot een
    MULTIPOLYGON. De bevindingen zelf hangen aan de gemengde strengen; dit vlak toont
    waar dat deelstelsel ligt, want een deelstelsel is geen GWSW-object met een eigen
    geometrie.

    Strikte aansluiting, net als bij de trefferlaag: de rijen komen uit de meldingen van
    déze uitvoer, gegroepeerd op hun `cluster_id`. De laag kan daardoor niet groter zijn
    dan de uitslag -- na afbakening tot een studiegebied of na onderdrukking uit
    `[rapport]` verdwijnen de vlakken mee met hun meldingen. De geometrie komt uit
    `run.context`: dezelfde graaf waarop de check draaide. Met een studiegebied loopt zo'n
    vlak door tot buiten de kern -- een deelstelsel houdt niet op bij de gebiedsgrens, en
    de component is de eenheid waarover RVZ-006 oordeelt.

    Wat er gegarandeerd is, en wat niet. Twee dingen kunnen de laag kleiner maken dan het
    aantal gemelde deelstelsels, en ze worden verschillend behandeld:

    * **Een `cluster_id` die de graaf niet kent** is geen datatoestand maar een interne
      tegenspraak: de check en deze schrijver lezen dezelfde `deelstelsel_ids` van dezelfde
      context. Dat faalt luid, precies zoals `_vul_trefferlaag` doet bij een melding die
      naar een niet-geregistreerde treffer wijst.
    * **Een deelstelsel waarvan geen enkele streng een bruikbare lijn draagt** is wel een
      datatoestand: er valt niets te tekenen. Zo'n deelstelsel levert geen rij op maar
      wordt geteld en komt in `gwsw_run` als `n_gemengd_zonder_vlak` terecht, naast
      `n_gemengd_zonder_overstort` dat de geschreven rijen telt. Zonder die telling zou
      een lezer "dit deelstelsel bestaat niet" niet kunnen onderscheiden van "we konden
      het niet tekenen". De meldingen zelf staan gewoon in de meldingentabel en op hun
      eigen streng in de laag `strengen`.

    Geeft het aantal geschreven rijen terug plus het aantal deelstelsels zonder vlak.
    """
    kolommen = _gemengd_kolommen()
    _maak_featurelaag(
        verbinding,
        "gemengd_zonder_overstort",
        "MULTIPOLYGON",
        kolommen,
        "Gemengde deelstelsels zonder externe overstort/BBB of zonder afvoereindpunt "
        "(RVZ-006), als vlak om de strengen van het deelstelsel.",
    )
    per_cluster: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        if melding.check_id == CHECK_GEMENGD_ZONDER_OVERSTORT and melding.cluster_id:
            per_cluster[melding.cluster_id].append(melding)

    buffer_m = config.drempels.gemengd_zonder_overstort_buffer_m
    knopen_per_cluster = _knopen_per_cluster(run)
    onbekend = sorted(cluster for cluster in per_cluster if cluster not in knopen_per_cluster)
    if onbekend:
        raise PipelineError(
            f"laag 'gemengd_zonder_overstort': {len(onbekend)} melding(en) dragen een "
            f"deelstelsel-ID dat de graaf van deze run niet kent "
            f"({', '.join(onbekend[:5])}). De laag zou stil kleiner zijn dan de uitslag; "
            f"controleer of de check en deze schrijver dezelfde context lezen."
        )

    index = aansluitingen(run.context, "vrijvervalleiding")
    rijen = []
    zonder_vlak = 0
    grenzen: list[tuple[float, float, float, float]] = []
    for cluster in sorted(per_cluster):
        knopen = knopen_per_cluster[cluster]
        conduits = _strengen_van_cluster(index, knopen)
        geometrie = _gemengd_geometrie(conduits, buffer_m)
        if geometrie is None or geometrie.is_empty:
            zonder_vlak += 1
            continue
        grenzen.append(geometrie.bounds)
        rijen.append(
            (
                _blob(_als_multipolygon(geometrie)),
                *_gemengd_rij(cluster, knopen, conduits, per_cluster[cluster]),
            )
        )
    if rijen:
        plaatshouders = ", ".join("?" * (len(kolommen) + 1))
        velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
        verbinding.executemany(
            f'insert into "gemengd_zonder_overstort" (geom, {velden}) values ({plaatshouders})',
            rijen,
        )
    _zet_omhullende(verbinding, "gemengd_zonder_overstort", grenzen)
    voortgang.stap(label="gemengd_zonder_overstort")
    return len(rijen), zonder_vlak


def _knopen_per_cluster(run: CheckRun) -> dict[str, frozenset[str]]:
    """De knopen van elk vrijverval-deelstelsel, omgekeerd uit `deelstelsel_ids`."""
    gevonden: dict[str, set[str]] = defaultdict(set)
    for uri, cluster in deelstelsel_ids(run.context).items():
        gevonden[cluster].add(uri)
    return {cluster: frozenset(knopen) for cluster, knopen in gevonden.items()}


def _strengen_van_cluster(index: Aansluitingen, knopen: frozenset[str]) -> list[Conduit]:
    """De vrijvervalstrengen die op de knopen van dit deelstelsel uitkomen, ontdubbeld."""
    gevonden: dict[str, Conduit] = {}
    for knoop in sorted(knopen):
        for conduit in index.strengen(knoop):
            gevonden[conduit.uri] = conduit
    return [gevonden[uri] for uri in sorted(gevonden)]


def _gemengd_geometrie(conduits: list[Conduit], buffer_m: float) -> BaseGeometry | None:
    """De buffer om de strengen van een deelstelsel, samengevoegd tot een vlak."""
    lijnen = [
        conduit.line
        for conduit in conduits
        if conduit.line is not None and not conduit.line.is_empty
    ]
    if not lijnen:
        return None
    return unary_union([lijn.buffer(buffer_m) for lijn in lijnen])


def _gemengd_rij(
    cluster: str,
    knopen: frozenset[str],
    conduits: list[Conduit],
    meldingen: list[Melding],
) -> tuple[object, ...]:
    """De attribuutvelden van een gemengd-deelstelselvlak, in kolomvolgorde.

    De status komt hier niet uit `bepaal_status` en de popup laat niets weg: een rij in
    deze laag bestaat alleen omdat RVZ-006 op dit deelstelsel aansloeg, dus zij is per
    constructie een gebrek. `bepaal_status` en `popup_html` filteren systemische
    meldingen weg -- terecht op een put of een streng, waar zij naast andere gebreken
    staan, maar hier zou het vlak dan groen worden en "geen eigen gebrek" te lezen geven
    terwijl het alleen bestaat door de meldingen die het weglaat. Dat gebeurde op
    Koekangerveld: 26 van de 26 gemengde strengen gemeld, dus systemisch. Zie BO-59.

    Grijs komt hier niet voor -- er staat per definitie minstens één melding op.
    """
    strenglengte = sum(conduit.line.length for conduit in conduits if conduit.line is not None)
    kop = Objectkop(
        label=cluster,
        objecttype=SOORT_GEMENGD_DEELSTELSEL,
        status=STATUS_ROOD if any(m.ernst == "F" for m in meldingen) else STATUS_ORANJE,
        feiten=(
            f"{len(knopen)} knopen, {len(conduits)} strengen, {strenglengte:.0f} m",
            f"{len(meldingen)} gemengde strengen gemeld",
        ),
        reden="",
    )
    return (
        cluster,
        len(knopen),
        len(conduits),
        strenglengte,
        len(meldingen),
        popup_html(kop, meldingen, toon_systemisch=True),
    )


def _begindatum_jaar(object_: object) -> int | None:
    """Het jaartal van de begindatum, of None als het object er geen draagt."""
    if not isinstance(object_, (Node, Conduit)):
        return None
    datum = object_.date("Begindatum")
    return datum.year if datum is not None else None


def _samenvatting(
    run: CheckRun,
    uri: str,
    object_: object,
    eigen: list[Melding],
    metadata: tuple[str, str, str],
    *,
    stelsel: str = "",
    richting_bob: str = "",
    richting_woord: str = "",
    bob_verval_m: float | None = None,
    afvoer_eindpunt: str = "",
    afvoer_meters: float | None = None,
    afvoer_stappen: int | None = None,
    reden: str = "",
) -> tuple[object, ...]:
    """De samenvattingsvelden van een object, in de volgorde van de kolommen.

    De staart is met opzet keyword-only: acht velden op een rij met door elkaar heen
    str-, bool-, `float | None`- en `int | None`-gleuven laten zich positioneel
    verwisselen zonder dat mypy iets zegt, en dan schrijft de rij stil de verkeerde
    kolom.

    `richting_bob` is wat er in de kolom komt; `richting_woord` de sleutel waaronder de
    popup hem verwoordt. Op mechanisch riool lopen die twee uiteen (issue #74): de kolom
    staat op `onbekend` zodat de grijze stijl hem pakt, maar de popupregel zegt dat zo'n
    leiding geen vrijvervalrichting *heeft* in plaats van dat hij niet te bepalen was.

    `reden` is gevuld als dit object niet beoordeeld is; dan is de status grijs en
    noemt de popup waarom. De status volgt verder dezelfde regel als `ergste_ernst`:
    systemische meldingen tellen niet mee, want anders is op De Wolden en Hoogeveen vrijwel elke
    put rood. Zie `objectkaart.bepaal_status`.
    """
    niet_systemisch = [melding for melding in eigen if not melding.systemisch]
    fouten = [melding for melding in niet_systemisch if melding.ernst == "F"]
    waarschuwingen = [melding for melding in niet_systemisch if melding.ernst == "W"]
    ernst = "F" if fouten else ("W" if waarschuwingen else "geen")
    # Zonder meldingen is er niets te prioriteren; 3 zou als "waarschuwing" lezen.
    prioriteit = min((melding.prioriteit for melding in eigen), default=None)
    per_categorie: defaultdict[str, int] = defaultdict(int)
    for melding in eigen:
        per_categorie[melding.categorie] += 1

    label = getattr(object_, "label", "")
    objecttype = run.dataset.beheerobjecttype(uri)
    status = bepaal_status(eigen, geanalyseerd=not reden)
    kop = Objectkop(
        label=label,
        objecttype=objecttype,
        status=status,
        feiten=_feiten(object_, stelsel, richting_woord),
        reden=reden,
    )
    return (
        kort(uri),
        label,
        objecttype,
        stelsel,
        _begindatum_jaar(object_),
        richting_bob,
        bob_verval_m,
        afvoer_eindpunt,
        afvoer_meters,
        afvoer_stappen,
        _gebied(run),
        status,
        ernst,
        len(fouten),
        len(waarschuwingen),
        sum(1 for melding in eigen if melding.systemisch),
        ", ".join(sorted({melding.check_id for melding in fouten})),
        ", ".join(sorted({melding.check_id for melding in waarschuwingen})),
        *[per_categorie.get(naam, 0) for naam in CATEGORIEEN],
        prioriteit,
        *metadata,
        uri,
        popup_html(kop, eigen),
    )


# De sleutel waaronder een mechanische leiding haar popupregel krijgt. Geen waarde van
# de kolom `richting_bob` -- die staat op zo'n leiding op `onbekend`, zodat de grijze
# stijl hergebruikt wordt -- maar een vierde sleutel in de tabel hieronder, zodat de
# popup twee dingen uit elkaar houdt die op de kaart dezelfde kleur hebben. De tekst
# spreekt van "mechanische leiding" en niet van "persleiding": de rol
# `mechanischeleidingen` dekt zes klassen, en op De Wolden en Hoogeveen zijn 172 van de
# 3720 een Vacuumleiding of Drukleiding. Die zouden anders een popupregel krijgen die
# hun eigen `objecttype`-regel een paar pixels hoger tegenspreekt.
RICHTING_MECHANISCH = "mechanisch"

# Hoe de kolom `richting_bob` in de popup gelezen wordt. De logica erachter blijft
# ongewijzigd (`_richting_bob`); dit is alleen de verwoording.
RICHTING_IN_WOORDEN = {
    RICHTING_MEE: "BOB-verval loopt met de getekende lijn mee",
    RICHTING_TEGEN: "BOB-verval loopt tegen de getekende lijn in",
    RICHTING_ONBEKEND: "BOB-richting niet te bepalen",
    RICHTING_MECHANISCH: "mechanische leiding — geen vrijvervalrichting",
}


def _feiten(object_: object, stelsel: str, richting_woord: str) -> tuple[str, ...]:
    """De losse feiten die in de kopregel van de popup horen.

    Alleen bij een verbinding: stelsel, de getekende lengte en de BOB-richtingsregel.
    Een put heeft ze geen van drieen, en een lege regel tonen is erger dan geen regel.

    De lengte is die van de getekende lijn en niet het kenmerk `LengteLeiding`: de
    popup hoort te zeggen wat er op de kaart staat. Wijken de twee af, dan is dat een
    bevinding van ATTR-009 en die staat in de lijst eronder.

    `richting_woord` is de sleutel in `RICHTING_IN_WOORDEN` en niet per se de waarde van
    de kolom `richting_bob`: op mechanisch riool lopen die twee uiteen (issue #74).
    """
    if not isinstance(object_, Conduit):
        return ()
    feiten = []
    if stelsel:
        feiten.append(f"Stelsel: {stelsel}")
    if object_.line is not None and not object_.line.is_empty:
        feiten.append(f"Lengte: {object_.line.length:.1f} m")
    if richting_woord:
        feiten.append(RICHTING_IN_WOORDEN.get(richting_woord, richting_woord))
    return tuple(feiten)


def _gebied(run: CheckRun) -> str:
    """De gebiedsaanduiding van deze run."""
    return run.study_area.gebied if run.study_area is not None else ""


def _metadata(run: CheckRun, run_datum: date) -> tuple[str, str, str]:
    """De drie metadatavelden die op elke laag staan."""
    config = run.config
    return (
        run_datum.isoformat(),
        run.dataset.source.name,
        config.rapport.register_versie,
    )


# Op welke afstand twee meldingen als dezelfde plek gelden. Een millimeter: kleiner
# dan elke echte afstand in een rioolbestand en groter dan het afrondingsverschil
# tussen twee berekende punten. De kolommen `stapel_aantal` en `stapel_nr` dreven
# vroeger de verspringing in de laag `meldinglocaties`; die laag is er niet meer, maar
# de tellingen zeggen nog steeds hoeveel meldingen op dezelfde plek zitten en blijven
# daarom in de meldingentabel staan.
STAPEL_RASTER_M = 0.001

# De kolommen van `overzicht_checks`, het dashboard met een rij per check. Op
# moduleniveau en niet in de schrijver, net als `MELDING_KOLOMMEN`: buiten deze
# package leest `scripts/steekproef.py` deze tabel op naam, en een drifttest daar kan
# alleen tegen een lijst beweren die te noemen valt.
OVERZICHT_KOLOMMEN = [
    _Kolom("check_id", "text"),
    _Kolom("omschrijving", "text"),
    _Kolom("bron", "text"),
    _Kolom("ernst", "text"),
    _Kolom("categorie", "text"),
    _Kolom("dimensie", "text"),
    _Kolom("aantal_meldingen", "integer"),
    _Kolom("bekeken", "integer"),
    _Kolom("percentage_populatie", "real"),
    # Waarover `bekeken` geteld is (issue #77). Zonder die kolom mengt `bekeken` drie
    # noemers -- een rol op de analyseset, dezelfde rol op de volledige export, en
    # kenmerkinstanties -- en deelt `percentage_populatie` door een getal waarvan de
    # lezer de eenheid niet kent. `populatie` staat daar los van: dat is de populatie
    # die de check declareert (waar hij over gaat), en niet de noemer van `bekeken` --
    # de declaratie is een bovengrens, zie `CheckOutcome.populatie`.
    _Kolom("bekeken_scope", "text"),
    _Kolom("populatie", "text"),
    _Kolom("systemisch", "integer"),
    _Kolom("aantal_gebieden", "integer"),
    _Kolom("skelet", "text"),
    # De conformiteitsklassen die deze vorm stellen, net als in `meldingen`. Leeg op
    # een registerrij: een eigen check toetst niet tegen een CFK.
    _Kolom("cfk", "text"),
]

MELDING_KOLOMMEN = [
    _Kolom("melding_id", "text"),
    _Kolom("feature_id", "text"),
    _Kolom("feature_id_2", "text"),
    _Kolom("label", "text"),
    _Kolom("check_id", "text"),
    _Kolom("bron", "text"),
    _Kolom("ernst", "text"),
    _Kolom("categorie", "text"),
    _Kolom("dimensie", "text"),
    _Kolom("boodschap", "text"),
    _Kolom("waarde", "text"),
    _Kolom("drempel", "text"),
    _Kolom("systemisch", "integer"),
    _Kolom("cluster_id", "text"),
    _Kolom("scope", "text"),
    _Kolom("gebied", "text"),
    _Kolom("prioriteit", "integer"),
    _Kolom("typering_betrouwbaar", "integer"),
    _Kolom("run_datum", "text"),
    _Kolom("dataset_versie", "text"),
    _Kolom("gwsw_uri", "text"),
    _Kolom("gwsw_uri_2", "text"),
    _Kolom("stapel_aantal", "integer"),
    _Kolom("stapel_nr", "integer"),
    # De foutlocatie in RD, zoals de CSV hem als X/Y draagt en de JSON als
    # `foutlocatie`. Sinds de laag `meldinglocaties` verviel is dit de plek waar de
    # exacte plek van een melding in de GeoPackage staat; zonder deze twee kolommen
    # zou hij daar stilzwijgend uit verdwijnen. Leeg als de melding niet op een plek
    # te zetten is.
    _Kolom("x", "real"),
    _Kolom("y", "real"),
    # Achteraan, net als de kolom `CFK` in de CSV: bestaande kolommen houden hun
    # plaats, zodat een lezer die op positie werkt niet omvalt.
    _Kolom("cfk", "text"),
]

# Veld → kolom(men): de afbeelding die `_melding_rij` hieronder maakt, hier expliciet
# zodat de drifttest in `tests/test_uitvoer_herkomst.py` kan borgen dat elk
# `Melding`-veld in de meldingentabel verantwoord is. `foutlocatie` splitst in x en y;
# `stapel_aantal` en `stapel_nr` staan er niet in, want die zijn uit de hele lijst
# afgeleid en horen bij geen enkel veld.
MELDING_VELD_NAAR_KOLOM: dict[str, tuple[str, ...]] = {
    "melding_id": ("melding_id",),
    "object_id": ("feature_id",),
    "object2_id": ("feature_id_2",),
    "object_label": ("label",),
    "check_id": ("check_id",),
    "bron": ("bron",),
    "ernst": ("ernst",),
    "categorie": ("categorie",),
    "dimensie": ("dimensie",),
    "boodschap": ("boodschap",),
    "waarde": ("waarde",),
    "drempel": ("drempel",),
    "systemisch": ("systemisch",),
    "cluster_id": ("cluster_id",),
    "scope": ("scope",),
    "gebied": ("gebied",),
    "prioriteit": ("prioriteit",),
    "typering_betrouwbaar": ("typering_betrouwbaar",),
    "run_datum": ("run_datum",),
    "dataset": ("dataset_versie",),
    "object_uri": ("gwsw_uri",),
    "object2_uri": ("gwsw_uri_2",),
    "foutlocatie": ("x", "y"),
    "cfk": ("cfk",),
    # Het tweede object staat in de tabel als `feature_id_2` en `gwsw_uri_2`; zijn
    # label heeft hier nooit een kolom gehad. Expliciet leeg, zodat de drifttest dit
    # als bekende weglating leest -- een nieuw veld zonder vermelding valt er wél op.
    "object2_label": (),
}


def _stapels(meldingen: list[Melding]) -> dict[str, tuple[int, int]]:
    """Per melding het aantal meldingen op haar plek en haar volgnummer daarin.

    De volgorde is die van de melding-ID en niet die van de lijst, zodat twee runs
    over dezelfde data dezelfde nummering opleveren en het kaartbeeld niet
    verspringt.
    """
    per_plek: dict[tuple[int, int], list[str]] = defaultdict(list)
    for melding in sorted(meldingen, key=lambda m: m.melding_id):
        if melding.foutlocatie is None:
            continue
        sleutel = (
            round(melding.foutlocatie.x / STAPEL_RASTER_M),
            round(melding.foutlocatie.y / STAPEL_RASTER_M),
        )
        per_plek[sleutel].append(melding.melding_id)

    return {
        melding_id: (len(groep), nummer)
        for groep in per_plek.values()
        for nummer, melding_id in enumerate(groep, start=1)
    }


def _melding_rij(melding: Melding, stapel: tuple[int, int]) -> tuple:
    """Een melding als rij, in de volgorde van MELDING_KOLOMMEN."""
    return (
        melding.melding_id,
        melding.object_id,
        melding.object2_id,
        melding.object_label,
        melding.check_id,
        melding.bron,
        melding.ernst,
        melding.categorie,
        melding.dimensie,
        melding.boodschap,
        melding.waarde,
        melding.drempel,
        int(melding.systemisch),
        melding.cluster_id,
        melding.scope,
        melding.gebied,
        melding.prioriteit,
        int(melding.typering_betrouwbaar),
        melding.run_datum,
        melding.dataset,
        melding.object_uri,
        melding.object2_uri,
        stapel[0],
        stapel[1],
        melding.foutlocatie.x if melding.foutlocatie is not None else None,
        melding.foutlocatie.y if melding.foutlocatie is not None else None,
        ", ".join(melding.cfk),
    )


def _schrijf_meldingen(verbinding: sqlite3.Connection, meldingen: list[Melding]) -> None:
    """Schrijft de meldingentabel: het volledige register, zonder geometrie.

    De kolommen `x` en `y` dragen de foutlocatie. Sinds de laag `meldinglocaties`
    verviel (issue #13) staat de exacte plek van een melding -- het snijpunt van een
    kruising, het midden van een streng -- alleen nog hier; wie hem als punten wil,
    bouwt er in QGIS een geometriegenerator of een puntenlaag van.
    """
    _maak_attribuuttabel(
        verbinding,
        "meldingen",
        MELDING_KOLOMMEN,
        "Alle meldingen van deze run, koppelbaar op feature_id; x/y is de foutlocatie.",
    )
    stapels = _stapels(meldingen)
    velden = ", ".join(f'"{kolom.naam}"' for kolom in MELDING_KOLOMMEN)
    plaatshouders = ", ".join("?" * len(MELDING_KOLOMMEN))
    verbinding.executemany(
        f"insert into meldingen ({velden}) values ({plaatshouders})",
        [_melding_rij(melding, stapels.get(melding.melding_id, (1, 1))) for melding in meldingen],
    )


def _schrijf_overzicht(
    verbinding: sqlite3.Connection, run: CheckRun, meldingen: list[Melding]
) -> None:
    """Schrijft het dashboard: een rij per check en een rij per SHACL-vorm.

    Ook de skeletchecks staan erin. Een check die ontbreekt leest als een check
    zonder problemen, en dat is precies het misverstand dat dit project vermijdt.
    Om diezelfde reden staat de nulmeting erin: ze is de tweede bron in deze
    meldingenstroom, en een dashboard dat alleen het register toont, presenteert de
    helft van de meting als het geheel. Zie issue #24.
    """
    kolommen = OVERZICHT_KOLOMMEN
    _maak_attribuuttabel(
        verbinding,
        "overzicht_checks",
        kolommen,
        "Een rij per eigen check en een rij per SHACL-vorm uit de nulmeting; zie de kolom bron.",
    )

    systemisch = {melding.check_id for melding in meldingen if melding.systemisch}
    gebieden: dict[str, set[str]] = defaultdict(set)
    per_check: dict[str, list[Melding]] = defaultdict(list)
    per_vorm: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        gebieden[melding.check_id].add(melding.gebied)
        per_check[melding.check_id].append(melding)
        if melding.bron == BRON_NULMETING:
            per_vorm[melding.check_id].append(melding)

    rijen: list[tuple[object, ...]] = [
        (
            outcome.check_id,
            outcome.title,
            BRON_REGISTER,
            outcome.severity.value,
            categorie_van(outcome.check_id),
            outcome.dimension.value,
            len(per_check.get(outcome.check_id, [])),
            outcome.examined,
            round(100 * len(per_check.get(outcome.check_id, [])) / outcome.examined, 2)
            if outcome.examined
            else None,
            outcome.bekeken_scope.value,
            outcome.populatie,
            int(outcome.check_id in systemisch),
            len({gebied for gebied in gebieden.get(outcome.check_id, set()) if gebied}),
            outcome.skeleton,
            "",
        )
        for outcome in run.outcomes
    ]
    rijen += [
        (
            check_id,
            # Een SHACL-vorm draagt geen titel zoals een eigen check. De kolommen die
            # alleen een `CheckOutcome` kent -- de omschrijving, hoeveel objecten
            # bekeken zijn en waarover, het skelet -- blijven daarom leeg; een gevulde
            # waarde zou een dekking beweren die niemand gemeten heeft.
            "",
            BRON_NULMETING,
            # De zwaarste ernst binnen de vorm, dezelfde regel als in het rapport
            # (`bevindingen._detail_nulmeting`): twee overtredingen van dezelfde vorm
            # kunnen in ernst verschillen, en dan hoort hier de zwaarste te staan en
            # niet de toevallig eerste. Een meningsverschil tussen twee CFK-rapporten
            # over dezelfde overtreding is al eerder beslecht, in `_ontdubbel`.
            Severity.ERROR.value
            if any(melding.ernst == Severity.ERROR.value for melding in groep)
            else Severity.WARNING.value,
            groep[0].categorie,
            groep[0].dimensie,
            len(groep),
            None,
            None,
            "",
            "",
            int(check_id in systemisch),
            len({melding.gebied for melding in groep if melding.gebied}),
            "",
            ", ".join(sorted({cfk for melding in groep for cfk in melding.cfk})),
        )
        for check_id, groep in sorted(per_vorm.items())
    ]
    velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
    plaatshouders = ", ".join("?" * len(kolommen))
    verbinding.executemany(
        f"insert into overzicht_checks ({velden}) values ({plaatshouders})", rijen
    )


def _schrijf_runmetadata(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    run_datum: date,
    tellingen: _LaagTellingen,
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
) -> None:
    """Schrijft een enkele rij met alles wat het bestand herleidbaar maakt."""
    kolommen = [
        _Kolom(VELD_GEREEDSCHAP, "text"),
        _Kolom("dataset", "text"),
        _Kolom("run_datum", "text"),
        _Kolom("register_versie", "text"),
        _Kolom("ontologieen", "text"),
        _Kolom("typeringspoort", "integer"),
        _Kolom("codering_terugval", "text"),
        _Kolom("meldingen_totaal", "integer"),
        _Kolom("meldingen_zonder_locatie", "integer"),
        _Kolom("fouten", "integer"),
        _Kolom("waarschuwingen", "integer"),
        _Kolom("grens_bron", "text"),
        _Kolom("grens_laag", "text"),
        _Kolom("grens_oppervlak_ha", "real"),
        _Kolom("grens_vlakken", "integer"),
        _Kolom("gebied", "text"),
        _Kolom("n_putten", "integer"),
        _Kolom("n_strengen", "integer"),
        _Kolom("n_mechanisch", "integer"),
        _Kolom("n_vlakken", "integer"),
        _Kolom("n_gemengd_zonder_overstort", "integer"),
        # De gemelde deelstelsels die geen vlak konden krijgen (issue #75): geen enkele
        # streng ervan draagt een bruikbare lijn. Ze staan in geen rij van de laag, dus
        # zonder deze kolom zou het bestand erover zwijgen.
        _Kolom("n_gemengd_zonder_vlak", "integer"),
        _Kolom("kern_objecten", "integer"),
        _Kolom("schil_objecten", "integer"),
        _Kolom("dataset_objecten", "integer"),
        _Kolom("cfk_set", "text"),
        _Kolom("volledig", "integer"),
        # Wat `[rapport]` uit de meldingenstroom hield (BO-49): de twee lijsten uit de
        # projectconfiguratie en hoeveel meldingen erdoor wegvielen. Die meldingen staan
        # in geen enkele tabel van dit bestand; zonder deze telling zou de kaart zwijgen
        # over wat er weggelaten is.
        _Kolom("onderdruk_klassen", "text"),
        _Kolom("onderdruk_checks", "text"),
        _Kolom("meldingen_onderdrukt", "integer"),
        # De runbrede voorbehouden als een tekst, samengesteld door
        # `uitvoer.voorbehoud`; leeg als er niets voor te behouden valt. Dezelfde
        # string die boven het Markdown-rapport staat en in de JSON-envelop.
        _Kolom("markering", "text"),
    ]
    _maak_attribuuttabel(verbinding, "gwsw_run", kolommen, "Herkomst en bereik van deze run.")

    config = run.config
    gebied = run.study_area
    stel = run.analyseset
    fallback = run.dataset.decode_fallback
    velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
    plaatshouders = ", ".join("?" * len(kolommen))
    verbinding.execute(
        f"insert into gwsw_run ({velden}) values ({plaatshouders})",
        (
            gereedschap(),
            run.dataset.source.name,
            run_datum.isoformat(),
            config.rapport.register_versie,
            ", ".join(pad.name for pad in run.dataset.ontologies),
            int(run.typing_gate_applied),
            f"{fallback.encoding} ({fallback.byte_count} bytes)" if fallback else "",
            len(meldingen),
            sum(1 for melding in meldingen if melding.foutlocatie is None),
            # Uit de meldingenstroom en niet uit `run.count`: die telt alleen de
            # bevindingen van de eigen checks, terwijl `meldingen_totaal` erboven de
            # nulmeting meetelt. Bleven ze uit elkaar lopen, dan zou een lezer van
            # deze tabel een onverklaard verschil van tienduizenden zien.
            sum(1 for melding in meldingen if melding.ernst == Severity.ERROR.value),
            sum(1 for melding in meldingen if melding.ernst == Severity.WARNING.value),
            gebied.source.name if gebied is not None else "",
            gebied.name if gebied is not None else "",
            round(gebied.area_ha, 2) if gebied is not None else None,
            gebied.feature_count if gebied is not None else None,
            _gebied(run),
            tellingen.putten,
            tellingen.strengen,
            tellingen.mechanisch,
            tellingen.vlakken,
            tellingen.gemengd_zonder_overstort,
            tellingen.gemengd_zonder_vlak,
            len(stel.kern) if stel is not None else None,
            len(stel.schil) if stel is not None else None,
            stel.volledig_aantal if stel is not None else None,
            run.meetbereik.cfk_tekst,
            int(run.meetbereik.volledig),
            ", ".join(onderdrukking.klassen),
            ", ".join(onderdrukking.checks),
            onderdrukking.totaal,
            markering(run) or "",
        ),
    )


def _voorkomende_typen(verbinding: sqlite3.Connection, laag: str) -> set[str]:
    """De objecttypen die daadwerkelijk in een geschreven laag staan."""
    return {rij[0] for rij in verbinding.execute(f'select distinct objecttype from "{laag}"')}


def _schrijf_stijlen(verbinding: sqlite3.Connection) -> None:
    """Zet de QML-stijlen in `layer_styles` en registreert die tabel.

    Zonder rij in `gpkg_contents` vindt de OGR-provider van QGIS de tabel niet en
    krijgt elke laag de standaard-symbologie; dat is met PyQGIS vastgesteld op deze
    uitvoer. `update_time` moet ISO-8601 met T en Z zijn, anders meldt GDAL bij elke
    rij "non-conformant content".

    Een QML los naast het bestand is geen alternatief: die werkt alleen bij een
    GeoPackage met een enkele laag en heet dan naar het bestand, niet naar de laag.
    """
    verbinding.execute(
        "create table layer_styles ("
        "id integer primary key autoincrement, f_table_catalog text, f_table_schema text, "
        "f_table_name text, f_geometry_column text, styleName text, styleQML text, "
        "styleSLD text, useAsDefault boolean, description text, owner text, ui text, "
        "update_time datetime default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
    )
    _registreer(
        verbinding,
        "layer_styles",
        "attributes",
        "QGIS-stijlen van dit bestand; QGIS past de standaardstijl per laag zelf toe.",
    )
    for laag in FEATURELAGEN:
        qml = _stijl(laag, verbinding)
        verbinding.execute(
            "insert into layer_styles (f_table_catalog, f_table_schema, f_table_name, "
            "f_geometry_column, styleName, styleQML, styleSLD, useAsDefault, description, "
            "owner, ui, update_time) values ('', '', ?, 'geom', ?, ?, '', 1, ?, "
            "?, '', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
            (laag, f"{laag} (datakwaliteit)", qml, f"Standaardstijl voor {laag}.", PAKKET),
        )


# De lagen waarvan de stijl opgebouwd wordt in plaats van uit een bestand te komen.
# Hun regelstructuur is objecttype x status; op De Wolden en Hoogeveen zijn dat samen ruim honderd
# bladregels met evenzoveel symbolen, en die met de hand in XML onderhouden zou de
# typenlijst op twee plekken zetten. Zie `stijlen/symbolen.py`.
OPGEBOUWDE_STIJLEN = ("putten", "strengen")


def _stijl(laag: str, verbinding: sqlite3.Connection) -> str:
    """De QML van een laag: opgebouwd waar de regelstructuur dat vraagt, anders gelezen.

    De opgebouwde stijlen krijgen de objecttypen mee die werkelijk in de laag staan. De
    stijl reist mee in dit bestand, dus hij hoeft alleen regels te dragen voor wat erin
    zit; met de volledige symbolentabel zou de lagenboom van QGIS ruim tweehonderd
    legendaregels tonen op een laag met zes typen.
    """
    if laag in OPGEBOUWDE_STIJLEN:
        return bouw_qml(laag, _voorkomende_typen(verbinding, laag))
    return (
        resources.files("nlriochecker.uitvoer.stijlen")
        .joinpath(f"{laag}.qml")
        .read_text(encoding="utf-8")
    )


def _meldingen_per_object(meldingen: list[Melding]) -> dict[str, list[Melding]]:
    """Groepeert de meldingen op hun hoofdobject."""
    per_object: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        per_object[melding.object_uri].append(melding)
    return per_object
