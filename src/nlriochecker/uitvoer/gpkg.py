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

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, Severity
from nlriochecker.checks.selectie import mechanischeleidingen
from nlriochecker.checks.treffers import Treffer
from nlriochecker.dataset import Conduit
from nlriochecker.errors import PipelineError
from nlriochecker.uitvoer.herkomst import PAKKET, VELD_GEREEDSCHAP, gereedschap
from nlriochecker.uitvoer.identiteit import kort
from nlriochecker.uitvoer.melding import Melding, categorie_van
from nlriochecker.uitvoer.objectkaart import (
    Objectkop,
    bepaal_status,
    popup_html,
)
from nlriochecker.uitvoer.tabel import prepare
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
    "bouwwerken",
    "waterdelen_zonder_zinker",
)

# De relaties van EXT-001, van zwaar naar licht. De laag toont de sterkste over de
# meldingen die naar hetzelfde bouwwerk verwijzen.
RELATIE_STERKTE = ("binnen", "kruist", "nabij")

# Waarom een object grijs is. De popup noemt de reden; grijs zonder reden leest als
# "in orde", en dat is het niet.
REDEN_MECHANISCH = "mechanisch riool, valt buiten scope van het checkregister"
REDEN_SCHIL = "contextschil van het studiegebied, buiten de kern"

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
    "bouwwerken",
    "waterdelen_zonder_zinker",
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
    bouwwerken: int
    waterdelen: int


def schrijf_geopackage(
    run: CheckRun,
    meldingen: list[Melding],
    output_dir: Path,
    run_datum: date,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> Path:
    """Schrijft de GeoPackage van deze run en geeft het pad terug.

    Is er een studiegebied, dan is dat de grens van het bestand: de featurelagen
    bevatten alleen objecten binnen of snijdend met het gebied. De checks draaiden
    op de kern plus de contextschil (ruim genoeg voor randeffectvrije netwerkchecks),
    dus wat hier buiten valt is bewust weggelaten, niet over het hoofd gezien.
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
        tellingen = _schrijf_features(verbinding, run, meldingen, binnen, run_datum, voortgang)
        _schrijf_meldingen(verbinding, meldingen)
        voortgang.stap(label="meldingen")
        _schrijf_overzicht(verbinding, run, meldingen)
        voortgang.stap(label="overzicht_checks")
        _schrijf_runmetadata(verbinding, run, meldingen, run_datum, tellingen)
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
        _Kolom("richting_bob", "text"),
        _Kolom("bob_verval_m", "real"),
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


def _mechanische_uris(run: CheckRun, config: CheckConfig) -> frozenset[str]:
    """De verbindingen die tot het mechanische stelsel horen.

    Ze doen niet mee aan de checks en horen dus niet tussen de strengen te staan,
    waar 'geen melding' ten onrechte als 'getoetst en in orde' leest.

    De selectie komt uit `checks/selectie.py` en niet uit een eigen comprehension.
    Deze laag heeft geen `CheckContext` van de run, dus hij wordt hier gemaakt over
    de dataset van de run -- onder een studiegebied dus de kern plus de contextschil,
    net als voorheen.
    """
    context = CheckContext(dataset=run.dataset, config=config)
    return frozenset(conduit.uri for conduit in mechanischeleidingen(context))


def _schrijf_features(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    binnen: frozenset[str] | None,
    run_datum: date,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> _LaagTellingen:
    """Schrijft de twee objectlagen plus de twee lagen met externe objecten.

    Naast de beoordeelde objecten komt erin wat de checks wel zagen maar niet
    beoordeelden: mechanisch riool, dat volgens het checkregister buiten scope valt,
    en de contextschil van een studiegebied. Beide krijgen status `grijs` met de reden
    in hun popup. Ze weglaten zou de kaart bij de gebiedsgrens laten ophouden alsof
    daar niets ligt, en een lege mechanische laag zou als "geen mechanisch riool
    aanwezig" lezen.

    De schil komt uit `run.analyseset` en niet uit "alles wat niet in de kern ligt".
    Een run die met `beperk_tot_studiegebied` op de volledige export is afgebakend
    heeft geen analyseset, en dan hoort het bestand bij de gebiedsgrens op te houden
    zoals het altijd deed -- anders zou een toets op een buurt de hele export als
    grijze achtergrond meesturen.
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
        "Verbindingen met de uitslag per object; mechanisch riool staat er grijs bij.",
    )

    per_object = _meldingen_per_object(meldingen)
    metadata = _metadata(run, run_datum)
    stelsels = _stelseltypen(run)
    config = run.config if run.config is not None else load_check_config()
    mechanisch = _mechanische_uris(run, config)
    schil = run.analyseset.schil if run.analyseset is not None else frozenset()

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
            if binnen is not None and uri not in binnen and uri not in schil:
                continue
            object_ = verzameling[uri]
            geometrie = getattr(object_, geometrie_veld)
            if geometrie is None or geometrie.is_empty:
                continue
            grenzen.append(geometrie.bounds)
            richting, verval = (
                _richting_bob(run, object_, config) if isinstance(object_, Conduit) else ("", None)
            )
            reden = _reden_niet_beoordeeld(uri, binnen, mechanisch)
            if uri in mechanisch:
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
                        stelsels.get(uri, ""),
                        richting,
                        verval,
                        reden,
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

    bouwwerken, waterdelen = _schrijf_treffers(verbinding, run, meldingen, config, voortgang)

    return _LaagTellingen(
        putten=tellingen["putten"],
        strengen=tellingen["strengen"],
        mechanisch=mechanisch_geschreven,
        bouwwerken=bouwwerken,
        waterdelen=waterdelen,
    )


def _reden_niet_beoordeeld(
    uri: str, binnen: frozenset[str] | None, mechanisch: frozenset[str]
) -> str:
    """Waarom dit object niet beoordeeld is, of leeg als het dat wel is.

    Mechanisch riool gaat voor de contextschil: het valt sowieso buiten scope, ook
    binnen de kern, en dat is de scherpere reden om te noemen.
    """
    if uri in mechanisch:
        return REDEN_MECHANISCH
    if binnen is not None and uri not in binnen:
        return REDEN_SCHIL
    return ""


def _bouwwerk_kolommen() -> list[_Kolom]:
    """De kolommen van de laag `bouwwerken`."""
    return [
        _Kolom("id", "text"),
        _Kolom("bron", "text"),
        _Kolom("bronbestand", "text"),
        _Kolom("label", "text"),
        _Kolom("relatie", "text"),
        _Kolom("afstand_min_m", "real"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("check_ids", "text"),
    ]


def _waterdeel_kolommen() -> list[_Kolom]:
    """De kolommen van de laag `waterdelen_zonder_zinker`."""
    return [
        _Kolom("id", "text"),
        _Kolom("watertype", "text"),
        _Kolom("bronbestand", "text"),
        _Kolom("label", "text"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("check_ids", "text"),
        _Kolom("buffer_m", "real"),
    ]


def _schrijf_treffers(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    config: CheckConfig,
    voortgang: Voortgang,
) -> tuple[int, int]:
    """Schrijft de externe objecten waarnaar de EXT-meldingen verwijzen.

    Strikte aansluiting: de rijen komen uit de meldingen van déze uitvoer, gejoind op
    het trefferregister van de run (`checks/treffers.py`). Deze schrijver bevraagt
    geen externe bron en doet geen ruimtelijke selectie, dus laag en testuitkomst
    kunnen niet uit elkaar lopen. Bij rapportage per studiegebied-feature betekent dat
    vanzelf: per gebied alleen de treffers van dat gebied, en een pand op de
    buurtgrens in beide bestanden.

    Twee beperkingen erven mee uit de detectie en worden bewust niet gerepareerd:
    EXT-001 meldt per object alleen het sterkste bouwwerk, en de watergangcheck stopt
    na het eerste gevonden waterdeel per streng. Zie de beslislog.
    """
    _maak_featurelaag(
        verbinding,
        "bouwwerken",
        "MULTIPOLYGON",
        _bouwwerk_kolommen(),
        "BGT- en BAG-bouwwerken waarnaar een EXT-001-melding verwijst.",
    )
    _maak_featurelaag(
        verbinding,
        "waterdelen_zonder_zinker",
        "MULTIPOLYGON",
        _waterdeel_kolommen(),
        "BGT-waterdelen waarnaar een EXT-003-melding verwijst.",
    )

    aantal_bouwwerken = _vul_trefferlaag(
        verbinding,
        run,
        "bouwwerken",
        _bouwwerk_kolommen(),
        _groepeer_op_treffer(meldingen, "EXT-001"),
        lambda treffer, verwijzend: (
            treffer.sleutel,
            treffer.bron,
            treffer.bronbestand,
            treffer.label,
            _sterkste_relatie(verwijzend),
            _kleinste_afstand(run, treffer.sleutel, verwijzend),
            len(verwijzend),
            _check_ids(verwijzend),
        ),
    )
    voortgang.stap(label="bouwwerken")

    aantal_waterdelen = _vul_trefferlaag(
        verbinding,
        run,
        "waterdelen_zonder_zinker",
        _waterdeel_kolommen(),
        _groepeer_op_treffer(meldingen, "EXT-003"),
        lambda treffer, verwijzend: (
            treffer.sleutel,
            treffer.label,
            treffer.bronbestand,
            _waterdeel_aanduiding(treffer),
            len(verwijzend),
            _check_ids(verwijzend),
            config.drempels.ext_watergang_buffer_m,
        ),
    )
    voortgang.stap(label="waterdelen_zonder_zinker")
    return aantal_bouwwerken, aantal_waterdelen


def _groepeer_op_treffer(meldingen: list[Melding], check_id: str) -> dict[str, list[Melding]]:
    """De meldingen van een check, gegroepeerd op het externe object dat ze aanwijzen."""
    per_treffer: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        if melding.check_id == check_id and melding.object2_uri:
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

    `watertype` draagt het type kaal, zodat je erop kunt filteren; deze kolom is voor
    de lezer, en die heeft aan "waterloop" alleen niet genoeg om er een terug te
    vinden.
    """
    return f"{treffer.label} {treffer.sleutel.split('/')[-1]}".strip()


def _check_ids(meldingen: list[Melding]) -> str:
    """De checks die naar deze treffer verwijzen, gesorteerd."""
    return ", ".join(sorted({melding.check_id for melding in meldingen}))


def _samenvatting(
    run: CheckRun,
    uri: str,
    object_: object,
    eigen: list[Melding],
    metadata: tuple[str, str, str],
    stelsel: str = "",
    richting_bob: str = "",
    bob_verval_m: float | None = None,
    reden: str = "",
) -> tuple[object, ...]:
    """De samenvattingsvelden van een object, in de volgorde van de kolommen.

    `reden` is gevuld als dit object niet beoordeeld is; dan is de status grijs en
    noemt de popup waarom. De status volgt verder dezelfde regel als `ergste_ernst`:
    systemische meldingen tellen niet mee, want anders is op De Wolden vrijwel elke
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
        feiten=_feiten(object_, stelsel, richting_bob),
        reden=reden,
    )
    return (
        kort(uri),
        label,
        objecttype,
        stelsel,
        richting_bob,
        bob_verval_m,
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


# Hoe de kolom `richting_bob` in de popup gelezen wordt. De logica erachter blijft
# ongewijzigd (`_richting_bob`); dit is alleen de verwoording.
RICHTING_IN_WOORDEN = {
    RICHTING_MEE: "BOB-verval loopt met de getekende lijn mee",
    RICHTING_TEGEN: "BOB-verval loopt tegen de getekende lijn in",
    RICHTING_ONBEKEND: "BOB-richting niet te bepalen",
}


def _feiten(object_: object, stelsel: str, richting_bob: str) -> tuple[str, ...]:
    """De losse feiten die in de kopregel van de popup horen.

    Alleen bij een verbinding: stelsel, de getekende lengte en de BOB-richtingsregel.
    Een put heeft ze geen van drieen, en een lege regel tonen is erger dan geen regel.

    De lengte is die van de getekende lijn en niet het kenmerk `LengteLeiding`: de
    popup hoort te zeggen wat er op de kaart staat. Wijken de twee af, dan is dat een
    bevinding van ATTR-009 en die staat in de lijst eronder.
    """
    if not isinstance(object_, Conduit):
        return ()
    feiten = []
    if stelsel:
        feiten.append(f"Stelsel: {stelsel}")
    if object_.line is not None and not object_.line.is_empty:
        feiten.append(f"Lengte: {object_.line.length:.1f} m")
    if richting_bob:
        feiten.append(RICHTING_IN_WOORDEN.get(richting_bob, richting_bob))
    return tuple(feiten)


def _gebied(run: CheckRun) -> str:
    """De gebiedsaanduiding van deze run."""
    return run.study_area.gebied if run.study_area is not None else ""


def _metadata(run: CheckRun, run_datum: date) -> tuple[str, str, str]:
    """De drie metadatavelden die op elke laag staan."""
    config = run.config if run.config is not None else load_check_config()
    return (
        run_datum.isoformat(),
        run.dataset.source.name,
        config.rapport.register_versie,
    )


# Op welke afstand twee meldingen als dezelfde plek gelden. Een millimeter: kleiner
# dan elke echte afstand in een rioolbestand en groter dan het afrondingsverschil
# tussen twee berekende punten.
STAPEL_RASTER_M = 0.001

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
    """Schrijft het dashboard: een rij per check, ook die zonder bevindingen.

    Ook de skeletchecks staan erin. Een check die ontbreekt leest als een check
    zonder problemen, en dat is precies het misverstand dat dit project vermijdt.
    """
    kolommen = [
        _Kolom("check_id", "text"),
        _Kolom("omschrijving", "text"),
        _Kolom("bron", "text"),
        _Kolom("ernst", "text"),
        _Kolom("categorie", "text"),
        _Kolom("dimensie", "text"),
        _Kolom("aantal_meldingen", "integer"),
        _Kolom("bekeken", "integer"),
        _Kolom("percentage_populatie", "real"),
        _Kolom("systemisch", "integer"),
        _Kolom("aantal_gebieden", "integer"),
        _Kolom("skelet", "text"),
    ]
    _maak_attribuuttabel(
        verbinding, "overzicht_checks", kolommen, "Een rij per check: het dashboard."
    )

    systemisch = {melding.check_id for melding in meldingen if melding.systemisch}
    gebieden: dict[str, set[str]] = defaultdict(set)
    per_check: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        gebieden[melding.check_id].add(melding.gebied)
        per_check[melding.check_id].append(melding)

    rijen = [
        (
            outcome.check_id,
            outcome.title,
            "register",
            outcome.severity.value,
            categorie_van(outcome.check_id),
            outcome.dimension.value,
            len(per_check.get(outcome.check_id, [])),
            outcome.examined,
            round(100 * len(per_check.get(outcome.check_id, [])) / outcome.examined, 2)
            if outcome.examined
            else None,
            int(outcome.check_id in systemisch),
            len({gebied for gebied in gebieden.get(outcome.check_id, set()) if gebied}),
            outcome.skeleton,
        )
        for outcome in run.outcomes
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
        _Kolom("n_bouwwerken", "integer"),
        _Kolom("n_waterdelen", "integer"),
        _Kolom("kern_objecten", "integer"),
        _Kolom("schil_objecten", "integer"),
        _Kolom("dataset_objecten", "integer"),
        _Kolom("cfk_set", "text"),
        _Kolom("volledig", "integer"),
    ]
    _maak_attribuuttabel(verbinding, "gwsw_run", kolommen, "Herkomst en bereik van deze run.")

    config = run.config if run.config is not None else load_check_config()
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
            tellingen.bouwwerken,
            tellingen.waterdelen,
            len(stel.kern) if stel is not None else None,
            len(stel.schil) if stel is not None else None,
            stel.volledig_aantal if stel is not None else None,
            run.meetbereik.cfk_tekst,
            int(run.meetbereik.volledig),
        ),
    )


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
        qml = _stijl(laag)
        verbinding.execute(
            "insert into layer_styles (f_table_catalog, f_table_schema, f_table_name, "
            "f_geometry_column, styleName, styleQML, styleSLD, useAsDefault, description, "
            "owner, ui, update_time) values ('', '', ?, 'geom', ?, ?, '', 1, ?, "
            "?, '', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
            (laag, f"{laag} (datakwaliteit)", qml, f"Standaardstijl voor {laag}.", PAKKET),
        )


def _stijl(laag: str) -> str:
    """Leest een meegeleverde QML-sjabloon."""
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


def _stelseltypen(run: CheckRun) -> dict[str, str]:
    """Het stelseltype per streng, en per put dat van de aansluitende strengen.

    Het GWSW legt het stelseltype op de leiding vast; een put ontleent het aan wat
    erop uitkomt. Komen daar meerdere soorten samen, dan staan ze er allemaal --
    dat is voor NET-006 juist het interessante geval.
    """
    config = run.config if run.config is not None else load_check_config()
    dataset = run.dataset
    per_object: dict[str, str] = {}
    per_put: dict[str, set[str]] = defaultdict(set)

    for uri, conduit in dataset.conduits.items():
        soort = config.klassen.stelseltype(conduit.types, dataset.closure)
        if soort is None:
            continue
        per_object[uri] = soort
        for kant in (conduit.start_node, conduit.end_node):
            knoop = dataset.resolve_network_node(kant, config.klassen.netwerkknopen)
            if knoop is not None:
                per_put[knoop].add(soort)

    for knoop, soorten in per_put.items():
        per_object[knoop] = ", ".join(sorted(soorten))
    return per_object
