"""De GeoPackage-export: een zelfvoorzienend bestand per run.

Geschreven met `sqlite3` en `shapely.wkb` — dezelfde route waarmee
`studiegebied.py` een GeoPackage al *leest*, nu de schrijfkant. Dat scheelt een
afhankelijkheid en houdt lees- en schrijfkant bij elkaar.

Het bestand is bewust zelfvoorzienend: de featurelagen bevatten genoeg samenvatting
om zonder join bruikbaar te zijn, `meldinglocaties` is bewust redundant met
`meldingen`, en er zijn geen GPKG-relaties of andere uitbreidingen die niet elk
GIS-pakket leest.
"""

from __future__ import annotations

import sqlite3
import struct
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path

from shapely.geometry.base import BaseGeometry

from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import CheckRun, Severity
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.uitvoer.melding import Melding, categorie_van
from gwswpijplijn.uitvoer.tabel import prepare

# De GWSW-coordinaten staan in Rijksdriehoek; herprojecteren doen we niet.
RD_NEW = 28992

# 'GPKG' als big-endian ASCII, het application_id dat de spec voorschrijft.
APPLICATION_ID = 0x47504B47
USER_VERSION = 10300

CATEGORIEEN = ("TOP", "ADM", "ATTR", "HGT", "NET", "RVZ", "BTR", "EXT", "NULMETING")

FEATURELAGEN = ("putten", "strengen", "meldinglocaties")

RD_WKT = (
    'PROJCS["Amersfoort / RD New",GEOGCS["Amersfoort",DATUM["Amersfoort",'
    'SPHEROID["Bessel 1841",6377397.155,299.1528128]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Oblique_Stereographic"],'
    'PARAMETER["latitude_of_origin",52.15616055555555],'
    'PARAMETER["central_meridian",5.38763888888889],'
    'PARAMETER["scale_factor",0.9999079],PARAMETER["false_easting",155000],'
    'PARAMETER["false_northing",463000],UNIT["metre",1],AUTHORITY["EPSG","28992"]]'
)


@dataclass(frozen=True)
class _Kolom:
    """Een kolom van een laag: naam en SQLite-type."""

    naam: str
    type: str


def schrijf_geopackage(
    run: CheckRun,
    meldingen: list[Melding],
    output_dir: Path,
    run_datum: date,
) -> Path:
    """Schrijft de GeoPackage van deze run en geeft het pad terug.

    Is er een studiegebied, dan is dat de grens van het bestand: de featurelagen
    bevatten alleen objecten binnen of snijdend met het gebied. De checks zijn op de
    volledige dataset gedraaid, dus zonder randeffecten.
    """
    output_dir = prepare(output_dir)
    doel = _doelpad(run, output_dir, run_datum)
    doel.unlink(missing_ok=True)

    binnen = run.objecten_binnen()
    verbinding = sqlite3.connect(doel)
    try:
        _leg_fundament(verbinding)
        _schrijf_features(verbinding, run, meldingen, binnen, run_datum)
        _schrijf_meldingen(verbinding, meldingen)
        _schrijf_overzicht(verbinding, run, meldingen)
        _schrijf_runmetadata(verbinding, run, meldingen, run_datum)
        _schrijf_stijlen(verbinding, output_dir)
        verbinding.commit()
    finally:
        verbinding.close()
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


def _samenvatting_kolommen() -> list[_Kolom]:
    """De kolommen van `putten` en `strengen`."""
    return [
        _Kolom("feature_id", "text"),
        _Kolom("label", "text"),
        _Kolom("objecttype", "text"),
        _Kolom("stelsel", "text"),
        _Kolom("gebied", "text"),
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
    ]


def _schrijf_features(
    verbinding: sqlite3.Connection,
    run: CheckRun,
    meldingen: list[Melding],
    binnen: frozenset[str] | None,
    run_datum: date,
) -> None:
    """Schrijft `putten`, `strengen` en `meldinglocaties`."""
    kolommen = _samenvatting_kolommen()
    _maak_featurelaag(
        verbinding, "putten", "POINT", kolommen, "Knooppunten met een samenvatting per object."
    )
    _maak_featurelaag(
        verbinding,
        "strengen",
        "LINESTRING",
        kolommen,
        "Vrijvervalstrengen met een samenvatting per object.",
    )

    per_object = _meldingen_per_object(meldingen)
    metadata = _metadata(run, run_datum)
    stelsels = _stelseltypen(run)

    for laag, verzameling, geometrie_veld in (
        ("putten", run.dataset.nodes, "point"),
        ("strengen", run.dataset.conduits, "line"),
    ):
        rijen = []
        grenzen: list[tuple[float, float, float, float]] = []
        for uri, object_ in verzameling.items():
            if binnen is not None and uri not in binnen:
                continue
            geometrie = getattr(object_, geometrie_veld)
            if geometrie is None or geometrie.is_empty:
                continue
            grenzen.append(geometrie.bounds)
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

    _schrijf_meldinglocaties(verbinding, meldingen)


def _samenvatting(
    run: CheckRun,
    uri: str,
    object_: object,
    eigen: list[Melding],
    metadata: tuple[str, str, str],
    stelsel: str = "",
) -> tuple[object, ...]:
    """De samenvattingsvelden van een object, in de volgorde van de kolommen."""
    niet_systemisch = [melding for melding in eigen if not melding.systemisch]
    fouten = [melding for melding in niet_systemisch if melding.ernst == "F"]
    waarschuwingen = [melding for melding in niet_systemisch if melding.ernst == "W"]
    ernst = "F" if fouten else ("W" if waarschuwingen else "geen")
    # Zonder meldingen is er niets te prioriteren; 3 zou als "waarschuwing" lezen.
    prioriteit = min((melding.prioriteit for melding in eigen), default=None)
    per_categorie = defaultdict(int)
    for melding in eigen:
        per_categorie[melding.categorie] += 1

    return (
        uri,
        getattr(object_, "label", ""),
        run.dataset.beheerobjecttype(uri),
        stelsel,
        _gebied(run),
        ernst,
        len(fouten),
        len(waarschuwingen),
        sum(1 for melding in eigen if melding.systemisch),
        ", ".join(sorted({melding.check_id for melding in fouten})),
        ", ".join(sorted({melding.check_id for melding in waarschuwingen})),
        *[per_categorie.get(naam, 0) for naam in CATEGORIEEN],
        prioriteit,
        *metadata,
    )


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
]


def _melding_rij(melding: Melding) -> tuple:
    """Een melding als rij, in de volgorde van MELDING_KOLOMMEN."""
    return (
        melding.melding_id,
        melding.object_uri,
        melding.object2_uri,
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
    )


def _schrijf_meldingen(verbinding: sqlite3.Connection, meldingen: list[Melding]) -> None:
    """Schrijft de meldingentabel: het volledige register, zonder geometrie."""
    _maak_attribuuttabel(
        verbinding,
        "meldingen",
        MELDING_KOLOMMEN,
        "Alle meldingen van deze run, koppelbaar op feature_id.",
    )
    velden = ", ".join(f'"{kolom.naam}"' for kolom in MELDING_KOLOMMEN)
    plaatshouders = ", ".join("?" * len(MELDING_KOLOMMEN))
    verbinding.executemany(
        f"insert into meldingen ({velden}) values ({plaatshouders})",
        [_melding_rij(melding) for melding in meldingen],
    )


def _schrijf_meldinglocaties(verbinding: sqlite3.Connection, meldingen: list[Melding]) -> None:
    """Schrijft de naloopwerklaag: een punt per melding op de foutlocatie.

    Bewust redundant met de meldingentabel: wie met een kaal GIS-pakket werkt kan
    hiermee uit de voeten zonder joins.
    """
    _maak_featurelaag(
        verbinding,
        "meldinglocaties",
        "POINT",
        MELDING_KOLOMMEN,
        "Een punt per melding, op de plek waar het probleem zit.",
    )
    velden = ", ".join(f'"{kolom.naam}"' for kolom in MELDING_KOLOMMEN)
    plaatshouders = ", ".join("?" * (len(MELDING_KOLOMMEN) + 1))
    met_punt = [melding for melding in meldingen if melding.foutlocatie is not None]
    rijen = [(_blob(melding.foutlocatie), *_melding_rij(melding)) for melding in met_punt]
    if rijen:
        verbinding.executemany(
            f"insert into meldinglocaties (geom, {velden}) values ({plaatshouders})", rijen
        )
    _zet_omhullende(
        verbinding, "meldinglocaties", [melding.foutlocatie.bounds for melding in met_punt]
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
) -> None:
    """Schrijft een enkele rij met alles wat het bestand herleidbaar maakt."""
    kolommen = [
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
    ]
    _maak_attribuuttabel(verbinding, "gwsw_run", kolommen, "Herkomst en bereik van deze run.")

    config = run.config if run.config is not None else load_check_config()
    gebied = run.study_area
    fallback = run.dataset.decode_fallback
    velden = ", ".join(f'"{kolom.naam}"' for kolom in kolommen)
    plaatshouders = ", ".join("?" * len(kolommen))
    verbinding.execute(
        f"insert into gwsw_run ({velden}) values ({plaatshouders})",
        (
            run.dataset.source.name,
            run_datum.isoformat(),
            config.rapport.register_versie,
            ", ".join(pad.name for pad in run.dataset.ontologies),
            int(run.typing_gate_applied),
            f"{fallback.encoding} ({fallback.byte_count} bytes)" if fallback else "",
            len(meldingen),
            sum(1 for melding in meldingen if melding.foutlocatie is None),
            run.count(Severity.ERROR),
            run.count(Severity.WARNING),
            gebied.source.name if gebied is not None else "",
            gebied.name if gebied is not None else "",
            round(gebied.area_ha, 2) if gebied is not None else None,
            gebied.feature_count if gebied is not None else None,
            _gebied(run),
        ),
    )


def _schrijf_stijlen(verbinding: sqlite3.Connection, output_dir: Path) -> None:
    """Zet de QML-stijlen in `layer_styles` en legt ze los naast het bestand neer.

    `layer_styles` is een QGIS-conventie en staat bewust niet in gpkg_contents; dat
    doet QGIS zelf ook niet. Andere pakketten negeren de tabel en kunnen de losse
    QML-bestanden importeren.
    """
    verbinding.execute(
        "create table layer_styles ("
        "id integer primary key autoincrement, f_table_catalog text, f_table_schema text, "
        "f_table_name text, f_geometry_column text, styleName text, styleQML text, "
        "styleSLD text, useAsDefault boolean, description text, owner text, ui text, "
        "update_time datetime default (datetime('now')))"
    )
    for laag in FEATURELAGEN:
        qml = _stijl(laag)
        (Path(output_dir) / f"{laag}.qml").write_text(qml, encoding="utf-8")
        verbinding.execute(
            "insert into layer_styles (f_table_catalog, f_table_schema, f_table_name, "
            "f_geometry_column, styleName, styleQML, styleSLD, useAsDefault, description, "
            "owner, ui) values ('', '', ?, 'geom', ?, ?, '', 1, ?, 'gwswpijplijn', '')",
            (laag, f"{laag} (datakwaliteit)", qml, f"Standaardstijl voor {laag}."),
        )


def _stijl(laag: str) -> str:
    """Leest een meegeleverde QML-sjabloon."""
    return (
        resources.files("gwswpijplijn.uitvoer.stijlen")
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
