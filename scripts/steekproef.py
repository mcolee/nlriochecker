#!/usr/bin/env python
"""Trekt een gemeentebrede steekproef uit de bevindingen van een `toets`-run.

Bedoeld om elke eigen check met de hand na te lopen: tien bevindingen per check,
ruimtelijk gespreid over het hele gebied, als GeoPackage die je in QGIS naast de
run legt.

De bron is de GeoPackage die `toets` zelf schrijft, niet de dataset: de tabel
`meldingen` voor de bevindingen, `overzicht_checks` voor de checks zonder
bevindingen, en de lagen `putten` en `strengen` voor de geometrie. De geometrie
wordt als blob overgenomen. Daardoor kan de steekproef niet afwijken van de run die
hij bemonstert, en hoeft de TTL er niet voor ingelezen te worden.

Alleen `bron = 'register'`: de eigen checks. De overtredingen uit de SHACL-nulmeting
blijven buiten deze steekproef.

Elke rij draagt naast de melding ook alle kolommen van de put of streng uit de run
(stelsel, status, prioriteit, popup_html, ...) en een lege kolom `feedback` om in
QGIS in te vullen. Met `--buurten` en `--buurt` beperkt de trekking zich tot de
meldingen met een foutlocatie in de genoemde CBS-buurten; met `--per-bestand` wordt
de uitvoer in genummerde bestanden van ten hoogste zoveel rijen gesplitst, in de
volgorde van het checkregister en met elke check heel in één bestand.

Gebruik:

    uv run python scripts/steekproef.py uitvoer/<run>/dq_*.gpkg
    uv run python scripts/steekproef.py <run.gpkg> --uit steekproef.gpkg --aantal 10
    uv run python scripts/steekproef.py <run.gpkg> --aantal 3 --per-bestand 10 \\
        --buurten data/gis_dewoldenhoogeveen/CBS_buurten_DeWoldenHoogeveen.gpkg \\
        --buurt Koekangerveld --buurt Veeningen
"""

from __future__ import annotations

import argparse
import random
import sqlite3
import struct
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from shapely import wkb
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import prep

from nlriochecker.uitvoer.gpkg import APPLICATION_ID, RD_NEW, RD_WKT, USER_VERSION
from nlriochecker.uitvoer.herkomst import gereedschap

# De koptekst die `uitvoer/gpkg.py` voor elke geometrie schrijft: magic, versie 0,
# vlaggen 1 (little-endian, geen omhullende), en het SRS-id. Acht bytes, dus de WKB
# begint op positie 8. Dit script leest alleen GeoPackages van dit gereedschap; een
# blob met een andere kop wordt geweigerd in plaats van verkeerd ontleed.
GPB_KOP = b"GP" + bytes([0, 1]) + struct.pack("<i", RD_NEW)

BRON_REGISTER = "register"
STANDAARD_AANTAL = 10
STANDAARD_SEED = "nlriochecker"
# De maaswijdte waarover de trekking gespreid wordt. 1000 m is ruim een buurt: groot
# genoeg om per cel meestal iets te vinden, klein genoeg om tien bevindingen niet in
# een straat te laten klonteren.
STANDAARD_CEL_M = 1000.0

LAAG_PUTTEN = "steekproef_putten"
LAAG_STRENGEN = "steekproef_strengen"
LAAG_LOCATIES = "steekproef_locaties"
TABEL_DEKKING = "steekproef_dekking"
TABEL_RUN = "steekproef_run"

# De volgorde van het checkregister, en dus van de bestanden bij `--per-bestand`.
# Een categorie die hier niet staat komt achteraan, alfabetisch.
CATEGORIE_VOLGORDE = ("TOP", "ADM", "ATTR", "HGT", "NET", "RVZ", "BTR", "EXT")

# De kolom met de buurtnaam in de CBS-buurtenlaag (`naam_gebied` in
# `CBS_buurten_DeWoldenHoogeveen.gpkg`).
BUURT_NAAMKOLOM = "naam_gebied"

# De lege kolom die in QGIS ingevuld wordt.
KOLOM_FEEDBACK = "feedback"
# Het voorvoegsel voor een objectkolom uit de run die botst met een meldingveld.
OBJECT_VOORVOEGSEL = "obj_"

# De velden die uit `meldingen` meekomen, in de volgorde waarin ze in de steekproef
# staan. `feedback` staat er niet bij: die blijft leeg en is er om in QGIS zelf in
# te vullen.
MELDINGVELDEN = (
    "melding_id",
    "check_id",
    "categorie",
    "ernst",
    "dimensie",
    "boodschap",
    "waarde",
    "drempel",
    "systemisch",
    "feature_id",
    "label",
    "feature_id_2",
    "gwsw_uri",
    "gwsw_uri_2",
    "gebied",
    "prioriteit",
    "x",
    "y",
    "run_datum",
)

TEKSTVELDEN = frozenset(
    {
        "melding_id",
        "check_id",
        "categorie",
        "ernst",
        "dimensie",
        "boodschap",
        "waarde",
        "drempel",
        "feature_id",
        "label",
        "feature_id_2",
        "gwsw_uri",
        "gwsw_uri_2",
        "gebied",
        "run_datum",
    }
)

# De velden die uit `overzicht_checks` gelezen worden: het dashboard van de run, met
# een rij per check en dus ook de checks die niets vonden.
CHECKVELDEN = (
    "check_id",
    "omschrijving",
    "categorie",
    "ernst",
    "dimensie",
    "bekeken",
    "aantal_meldingen",
    "skelet",
)


def _kolomtype(veld: str) -> str:
    """Het SQLite-type van een steekproefkolom."""
    if veld in TEKSTVELDEN:
        return "text"
    return "real" if veld in ("x", "y") else "integer"


def steekproefkolommen(
    met_objectlaag: bool, objectkolommen: list[tuple[str, str]] | None = None
) -> list[tuple[str, str]]:
    """De kolommen van een steekproeflaag.

    `objectlaag` staat alleen op `steekproef_locaties`: daar is het de enige plek
    waar te zien is of het object zelf in de puttenlaag of in de strengenlaag ligt.
    `objectkolommen` zijn de kolommen van de put-/strenglaag uit de run, al hernoemd
    waar ze met een meldingveld botsen (zie `lees_objectkolommen`).
    """
    kolommen = [("steekproef_nr", "integer")]
    kolommen += [(veld, _kolomtype(veld)) for veld in MELDINGVELDEN]
    kolommen += [("objecttype", "text")]
    if met_objectlaag:
        kolommen += [("objectlaag", "text")]
    kolommen += objectkolommen or []
    return kolommen + [(KOLOM_FEEDBACK, "text")]


def _basiskolommen() -> set[str]:
    """De kolomnamen die een steekproeflaag al heeft vóór de objectkolommen."""
    return {kolom for kolom, _ in steekproefkolommen(met_objectlaag=True)}


def lees_objectkolommen(verbinding: sqlite3.Connection) -> list[tuple[str, str, str]]:
    """De kolommen van de lagen `putten` en `strengen` uit de run, zonder `fid`/`geom`.

    Levert per kolom (naam in de run, naam in de steekproef, SQLite-type). Een naam
    die al als meldingveld bestaat (`label`, `gebied`, `prioriteit`, ...) krijgt het
    voorvoegsel `obj_`, zodat de objectwaarde naast de meldingwaarde komt te staan in
    plaats van haar te verdringen. De volgorde is die van de puttenlaag; een kolom die
    alleen de strengenlaag heeft komt daarachter.
    """
    bezet = _basiskolommen()
    gezien: dict[str, str] = {}
    for laag in ("putten", "strengen"):
        for _, naam, type_, *_rest in verbinding.execute(f'pragma table_info("{laag}")'):
            if naam in ("fid", "geom") or naam in gezien:
                continue
            gezien[str(naam)] = str(type_ or "text").lower()
    kolommen = []
    for naam, type_ in gezien.items():
        doelnaam = f"{OBJECT_VOORVOEGSEL}{naam}" if naam in bezet else naam
        if type_ not in ("text", "integer", "real"):
            type_ = "text"
        kolommen.append((naam, doelnaam, type_))
    return kolommen


def lees_buurten(pad: Path, namen: list[str]) -> BaseGeometry:
    """Leest de genoemde buurten uit een CBS-buurtenbestand en verenigt hun vlakken.

    Een naam die niet in het bestand staat is een fout, met de beschikbare namen
    erbij: een tikfout in "Fluitenberg kern" zou anders stilzwijgend een lege
    steekproef opleveren.
    """
    import geopandas as gpd

    buurten = gpd.read_file(pad)
    if BUURT_NAAMKOLOM not in buurten.columns:
        raise ValueError(f"{pad} heeft geen kolom {BUURT_NAAMKOLOM}.")
    aanwezig = set(buurten[BUURT_NAAMKOLOM].astype(str))
    onbekend = sorted(set(namen) - aanwezig)
    if onbekend:
        raise ValueError(
            f"onbekende buurt(en) {', '.join(onbekend)} in {pad}; "
            f"beschikbaar: {', '.join(sorted(aanwezig))}"
        )
    keuze = buurten[buurten[BUURT_NAAMKOLOM].astype(str).isin(namen)]
    return keuze.geometry.union_all()


def binnen(meldingen: list[dict[str, Any]], gebied: BaseGeometry) -> list[dict[str, Any]]:
    """De meldingen waarvan de foutlocatie in `gebied` ligt; zonder locatie valt af."""
    voorbereid = prep(gebied)
    return [
        m
        for m in meldingen
        if m["x"] is not None
        and m["y"] is not None
        and voorbereid.contains(Point(float(m["x"]), float(m["y"])))
    ]


def registervolgorde(check_id: str) -> tuple[int, str]:
    """Sorteersleutel: de categorievolgorde van het register, dan het ID."""
    categorie = check_id.split("-", 1)[0]
    if categorie in CATEGORIE_VOLGORDE:
        return (CATEGORIE_VOLGORDE.index(categorie), check_id)
    return (len(CATEGORIE_VOLGORDE), check_id)


def verdeel(getrokken: dict[str, list[dict[str, Any]]], per_bestand: int | None) -> list[list[str]]:
    """Verdeelt de checks over bestanden van ten hoogste `per_bestand` rijen.

    Een check blijft heel; checks zonder trekking tellen niet mee en komen dus in
    geen enkel bestand voor (wel in de dekkingstabel van elk bestand). Zonder
    `per_bestand` is er één bestand met alles.
    """
    volgorde = sorted(getrokken, key=registervolgorde)
    if per_bestand is None:
        return [volgorde]
    bestanden: list[list[str]] = []
    huidig: list[str] = []
    gevuld = 0
    for check_id in volgorde:
        rijen = len(getrokken[check_id])
        if not rijen:
            continue
        if rijen > per_bestand:
            raise ValueError(
                f"{check_id} heeft {rijen} getrokken meldingen, meer dan --per-bestand "
                f"{per_bestand}; kies --aantal ten hoogste {per_bestand}."
            )
        if huidig and gevuld + rijen > per_bestand:
            bestanden.append(huidig)
            huidig, gevuld = [], 0
        huidig.append(check_id)
        gevuld += rijen
    if huidig:
        bestanden.append(huidig)
    return bestanden or [[]]


def cel(x: float | None, y: float | None, grootte: float) -> tuple[int, int] | None:
    """De gridcel van een foutlocatie, of None als de melding er geen heeft."""
    if x is None or y is None:
        return None
    return (int(x // grootte), int(y // grootte))


def trek(
    meldingen: list[dict[str, Any]],
    aantal: int,
    seed: str,
    celgrootte: float,
) -> list[dict[str, Any]]:
    """Trekt ten hoogste `aantal` meldingen, gespreid over het gebied.

    De meldingen worden over een vast grid verdeeld en er wordt om beurten een uit
    elke cel gehaald. Zo liggen de tien nooit in een straat bij elkaar, ook niet als
    een check honderden bevindingen in een enkele wijk heeft.

    Cellen en de volgorde binnen een cel worden geschud met een seed die het
    check-ID bevat: reproduceerbaar, en toch niet voor elke check dezelfde volgorde.
    Meldingen zonder foutlocatie vormen een eigen bak die pas aan de beurt komt als
    de gelokaliseerde op zijn -- ze zijn in QGIS niet aan te wijzen en zijn dus de
    minst bruikbare steekproef.
    """
    rng = random.Random(seed)
    per_cel: dict[tuple[int, int], list[dict[str, Any]]] = {}
    zonder_locatie: list[dict[str, Any]] = []
    for melding in sorted(meldingen, key=lambda m: str(m["melding_id"])):
        sleutel = cel(melding["x"], melding["y"], celgrootte)
        if sleutel is None:
            zonder_locatie.append(melding)
        else:
            per_cel.setdefault(sleutel, []).append(melding)

    bakken = [per_cel[sleutel] for sleutel in sorted(per_cel)]
    rng.shuffle(bakken)
    for bak in bakken:
        rng.shuffle(bak)
    rng.shuffle(zonder_locatie)

    gekozen: list[dict[str, Any]] = []
    for groep in (bakken, [zonder_locatie] if zonder_locatie else []):
        while len(gekozen) < aantal and any(groep):
            for bak in groep:
                if not bak:
                    continue
                gekozen.append(bak.pop())
                if len(gekozen) == aantal:
                    break
        if len(gekozen) == aantal:
            break
    return gekozen


def lees_meldingen(verbinding: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Leest de meldingen van de eigen checks, gegroepeerd per check-ID."""
    velden = ", ".join(f'"{veld}"' for veld in MELDINGVELDEN)
    per_check: dict[str, list[dict[str, Any]]] = {}
    for rij in verbinding.execute(
        f"select {velden} from meldingen where bron = ?", (BRON_REGISTER,)
    ):
        melding = dict(zip(MELDINGVELDEN, rij, strict=True))
        per_check.setdefault(str(melding["check_id"]), []).append(melding)
    return per_check


def lees_geometrie(
    verbinding: sqlite3.Connection,
    uris: set[str],
    objectkolommen: list[tuple[str, str, str]],
) -> dict[str, tuple[str, str, bytes, list[Any]]]:
    """Zoekt per object-URI de laag, het objecttype, de geometrieblob en de objectkolommen op.

    Alleen de URI's van de getrokken meldingen, en per laag in blokken: een `in`-lijst
    met tienduizenden waarden is niet nodig als de steekproef er een paar honderd telt.
    De objectwaarden staan in de volgorde van `objectkolommen`; een kolom die de laag
    niet heeft is None.
    """
    gevonden: dict[str, tuple[str, str, bytes, list[Any]]] = {}
    lijst = sorted(uris)
    for laag in ("putten", "strengen"):
        aanwezig = {
            str(naam) for _, naam, *_rest in verbinding.execute(f'pragma table_info("{laag}")')
        }
        selectie = ", ".join(
            f'"{naam}"' if naam in aanwezig else "null" for naam, _, _ in objectkolommen
        )
        for begin in range(0, len(lijst), 500):
            blok = lijst[begin : begin + 500]
            plaatshouders = ", ".join("?" * len(blok))
            for uri, objecttype, geom, *waarden in verbinding.execute(
                f"select gwsw_uri, objecttype, geom{', ' + selectie if selectie else ''} "
                f'from "{laag}" where gwsw_uri in ({plaatshouders})',
                blok,
            ):
                gevonden.setdefault(str(uri), (laag, str(objecttype or ""), geom, waarden))
    return gevonden


def lees_checks(verbinding: sqlite3.Connection) -> list[dict[str, Any]]:
    """Leest het dashboard van de run: een rij per eigen check, ook de lege."""
    kolommen = ", ".join(f'"{veld}"' for veld in CHECKVELDEN)
    return [
        dict(zip(CHECKVELDEN, rij, strict=True))
        for rij in verbinding.execute(
            f"select {kolommen} from overzicht_checks where bron = ? order by check_id",
            (BRON_REGISTER,),
        )
    ]


def reden(check: dict[str, Any], getrokken: int, buiten_gebied: int = 0) -> str:
    """Waarom er niets te trekken viel; leeg zodra er wel een steekproef is.

    Een lege regel in de dekkingstabel zou lezen als "check draaide en vond niets",
    en dat is precies het misverstand dat dit project vermijdt: een skelet en een
    check die niets te bekijken had zeggen iets heel anders dan een schone uitslag.
    `buiten_gebied` is het aantal meldingen dat er wel was maar buiten de gekozen
    buurten viel: dan vond de check wél iets, alleen niet hier.
    """
    if getrokken:
        return ""
    if check["skelet"]:
        return f"skelet: {check['skelet']}"
    if not check["bekeken"]:
        return "niets bekeken"
    if buiten_gebied:
        return f"geen bevindingen in de gekozen buurten ({buiten_gebied} erbuiten)"
    return "geen bevindingen"


def _wkb(blob: bytes) -> bytes:
    """Haalt de WKB uit een GeoPackage-blob van dit gereedschap."""
    if not blob.startswith(GPB_KOP):
        raise ValueError(
            "onbekende geometriekop in de bron-GeoPackage; dit script leest alleen de "
            "uitvoer van nlriochecker zelf."
        )
    return blob[len(GPB_KOP) :]


def _punt(x: float, y: float) -> bytes:
    """Bouwt een puntgeometrie in hetzelfde blobformaat als de bron."""
    return GPB_KOP + Point(x, y).wkb


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
            # `definition` is de volledige WKT en niet `EPSG:28992`: de spec eist WKT.
            # GDAL is er soepel in en valt terug op `organization`, strengere validators
            # niet. Vandaar dat `RD_WKT` uit `uitvoer/gpkg.py` komt en hier niet nog een
            # keer opgeschreven staat.
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


def _registreer(verbinding: sqlite3.Connection, naam: str, soort: str, omschrijving: str) -> None:
    """Zet een laag in gpkg_contents; zonder die rij vindt QGIS haar niet."""
    verbinding.execute(
        "insert into gpkg_contents (table_name, data_type, identifier, description, "
        "last_change, srs_id) values (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)",
        (naam, soort, naam, omschrijving, RD_NEW if soort == "features" else None),
    )


def _maak_laag(
    verbinding: sqlite3.Connection,
    naam: str,
    soort: str,
    kolommen: list[tuple[str, str]],
    omschrijving: str,
) -> None:
    """Maakt een featurelaag aan en registreert haar."""
    velden = ", ".join(f'"{kolom}" {type_}' for kolom, type_ in kolommen)
    verbinding.execute(
        f'create table "{naam}" (fid integer primary key autoincrement, geom blob, {velden})'
    )
    verbinding.execute(
        "insert into gpkg_geometry_columns values (?, 'geom', ?, ?, 0, 0)", (naam, soort, RD_NEW)
    )
    _registreer(verbinding, naam, "features", omschrijving)


def _maak_tabel(
    verbinding: sqlite3.Connection,
    naam: str,
    kolommen: list[tuple[str, str]],
    omschrijving: str,
) -> None:
    """Maakt een tabel zonder geometrie aan en registreert haar."""
    velden = ", ".join(f'"{kolom}" {type_}' for kolom, type_ in kolommen)
    verbinding.execute(f'create table "{naam}" (fid integer primary key autoincrement, {velden})')
    _registreer(verbinding, naam, "attributes", omschrijving)


def _zet_omhullende(
    verbinding: sqlite3.Connection, naam: str, grenzen: list[tuple[float, float, float, float]]
) -> None:
    """Vult de omhullende van een featurelaag in gpkg_contents."""
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


def _rij(
    melding: dict[str, Any],
    nummer: int,
    objecttype: str,
    objectlaag: str | None,
    objectwaarden: list[Any],
) -> list[Any]:
    """Zet een getrokken melding om in een rij van een steekproeflaag."""
    waarden: list[Any] = [nummer]
    waarden += [melding[veld] for veld in MELDINGVELDEN]
    waarden += [objecttype]
    if objectlaag is not None:
        waarden += [objectlaag]
    waarden += objectwaarden
    return waarden + [""]


def _vul_laag(
    verbinding: sqlite3.Connection,
    naam: str,
    kolommen: list[tuple[str, str]],
    rijen: list[tuple[bytes, list[Any]]],
) -> int:
    """Schrijft de rijen van een steekproeflaag en vult haar omhullende."""
    if not rijen:
        return 0
    velden = ", ".join(f'"{kolom}"' for kolom, _ in kolommen)
    plaatshouders = ", ".join("?" * (len(kolommen) + 1))
    verbinding.executemany(
        f'insert into "{naam}" (geom, {velden}) values ({plaatshouders})',
        [(geom, *waarden) for geom, waarden in rijen],
    )
    _zet_omhullende(verbinding, naam, [wkb.loads(_wkb(geom)).bounds for geom, _ in rijen])
    return len(rijen)


def _open_bron(bron: Path) -> sqlite3.Connection:
    """Opent de run-GeoPackage alleen-lezen en toetst dat de nodige tabellen erin staan.

    Alleen-lezen omdat dit script niets aan een run te wijzigen heeft. Het pad wordt
    voor de URI geescaped: een `#` erin zou SQLite een fragment laten lezen, en dan
    opent hij stilzwijgend een ander bestand.

    De tabeltoets staat hier en niet bij de eerste query, zodat wie het script op een
    willekeurige GeoPackage richt een leesbare melding krijgt in plaats van een
    `no such table`.
    """
    verbinding = sqlite3.connect(f"file:{quote(str(bron))}?mode=ro", uri=True)
    aanwezig = {
        naam
        for (naam,) in verbinding.execute(
            "select name from sqlite_master where type = ?", ("table",)
        )
    }
    ontbreekt = sorted({"meldingen", "overzicht_checks", "putten", "strengen"} - aanwezig)
    if ontbreekt:
        verbinding.close()
        raise ValueError(
            f"{bron} mist de tabellen {', '.join(ontbreekt)}; dit is geen GeoPackage van "
            "een `nlriochecker toets`-run."
        )
    return verbinding


def bestandsnamen(doel: Path, aantal: int) -> list[Path]:
    """De doelbestanden: `doel` zelf bij één, anders `doel_01`, `doel_02`, ..."""
    if aantal == 1:
        return [doel]
    breedte = max(2, len(str(aantal)))
    return [
        doel.with_name(f"{doel.stem}_{i:0{breedte}d}{doel.suffix}") for i in range(1, aantal + 1)
    ]


def schrijf_steekproef(
    bron: Path,
    doel: Path,
    aantal: int,
    seed: str,
    celgrootte: float,
    buurten: tuple[Path, list[str]] | None = None,
    per_bestand: int | None = None,
    alleen_checks: list[str] | None = None,
) -> dict[str, int]:
    """Trekt de steekproef uit `bron` en schrijft haar naar `doel`.

    Levert per laag het aantal geschreven rijen (over alle bestanden samen) en onder
    `bestanden` het aantal geschreven bestanden, zodat de aanroeper kan melden wat er
    staat.

    `buurten` is (pad naar een CBS-buurtenbestand, buurtnamen): dan tellen alleen
    meldingen met een foutlocatie in die buurten mee. `per_bestand` splitst de uitvoer
    in genummerde bestanden van ten hoogste zoveel rijen, in registervolgorde en met
    elke check heel in één bestand; de dekkingstabel staat volledig in elk bestand.
    `alleen_checks` beperkt de steekproef én de dekkingstabel tot die check-ID's; een
    onbekend ID is een fout.

    `doel` mag de bron niet zijn: die wordt gewist voordat er gelezen wordt, en dan
    is een run van minuten weg door een typefout. Dezelfde voorwaarde als
    `uitvoer/gpkg.py` stelt -- nooit een invoerbestand overschrijven.
    """
    if doel.resolve() == bron.resolve():
        raise ValueError(f"{doel} is de bron-GeoPackage zelf; kies een ander doelbestand.")
    if per_bestand is not None and per_bestand < 1:
        raise ValueError("per_bestand moet ten minste 1 zijn.")

    gebied = lees_buurten(*buurten) if buurten else None

    lezen = _open_bron(bron)
    try:
        checks = lees_checks(lezen)
        alle = lees_meldingen(lezen)
        if alleen_checks:
            bekend = {str(check["check_id"]) for check in checks}
            onbekend = sorted(set(alleen_checks) - bekend)
            if onbekend:
                raise ValueError(f"onbekende check(s) {', '.join(onbekend)} in overzicht_checks.")
            checks = [check for check in checks if str(check["check_id"]) in alleen_checks]
            alle = {k: v for k, v in alle.items() if k in alleen_checks}
        per_check = (
            {check_id: binnen(meldingen, gebied) for check_id, meldingen in alle.items()}
            if gebied is not None
            else alle
        )
        getrokken = {
            check_id: trek(meldingen, aantal, f"{seed}:{check_id}", celgrootte)
            for check_id, meldingen in per_check.items()
        }
        uris = {
            str(melding["gwsw_uri"])
            for meldingen in getrokken.values()
            for melding in meldingen
            if melding["gwsw_uri"]
        }
        objectkolommen = lees_objectkolommen(lezen)
        geometrie = lees_geometrie(lezen, uris, objectkolommen)
    finally:
        lezen.close()

    # De dekkingstabel volgt `overzicht_checks` en is bedoeld als volledige lijst. Zou
    # een check wel meldingen hebben maar geen rij in dat dashboard, dan stond hij in
    # de steekproef zonder in de dekking te staan -- precies de stilte die dit bestand
    # moet uitsluiten. Kan met de huidige schrijver niet gebeuren; blijft een grendel.
    zonder_rij = sorted(set(getrokken) - {str(check["check_id"]) for check in checks})
    if zonder_rij:
        raise ValueError(
            f"checks met meldingen maar zonder rij in overzicht_checks: {', '.join(zonder_rij)}"
        )

    extra = [(doelnaam, type_) for _, doelnaam, type_ in objectkolommen]
    put_kolommen = steekproefkolommen(met_objectlaag=False, objectkolommen=extra)
    locatie_kolommen = steekproefkolommen(met_objectlaag=True, objectkolommen=extra)
    leeg: list[Any] = [None] * len(objectkolommen)

    verdeling = verdeel(getrokken, per_bestand)
    doelen = bestandsnamen(doel, len(verdeling))
    for pad in doelen:
        pad.unlink(missing_ok=True)

    tellingen = {LAAG_PUTTEN: 0, LAAG_STRENGEN: 0, LAAG_LOCATIES: 0, TABEL_DEKKING: 0}
    for volgnummer, (pad, check_ids) in enumerate(zip(doelen, verdeling, strict=True), start=1):
        putrijen: list[tuple[bytes, list[Any]]] = []
        strengrijen: list[tuple[bytes, list[Any]]] = []
        locatierijen: list[tuple[bytes, list[Any]]] = []
        for check_id in check_ids:
            for nummer, melding in enumerate(getrokken[check_id], start=1):
                laag, objecttype, geom, waarden = geometrie.get(
                    str(melding["gwsw_uri"]), ("", "", b"", leeg)
                )
                if laag == "putten":
                    putrijen.append((geom, _rij(melding, nummer, objecttype, None, waarden)))
                elif laag == "strengen":
                    strengrijen.append((geom, _rij(melding, nummer, objecttype, None, waarden)))
                if melding["x"] is not None and melding["y"] is not None:
                    locatierijen.append(
                        (
                            _punt(float(melding["x"]), float(melding["y"])),
                            _rij(melding, nummer, objecttype, laag or "geen", waarden),
                        )
                    )

        verbinding = sqlite3.connect(pad)
        try:
            _leg_fundament(verbinding)
            _maak_laag(
                verbinding,
                LAAG_PUTTEN,
                "POINT",
                put_kolommen,
                "Getrokken meldingen op een put, met de geometrie en de kolommen van de put.",
            )
            _maak_laag(
                verbinding,
                LAAG_STRENGEN,
                "LINESTRING",
                put_kolommen,
                "Getrokken meldingen op een streng, met de geometrie en de kolommen van de streng.",
            )
            _maak_laag(
                verbinding,
                LAAG_LOCATIES,
                "POINT",
                locatie_kolommen,
                "De foutlocatie van elke getrokken melding: de plek waar de check op wijst.",
            )
            tellingen[LAAG_PUTTEN] += _vul_laag(verbinding, LAAG_PUTTEN, put_kolommen, putrijen)
            tellingen[LAAG_STRENGEN] += _vul_laag(
                verbinding, LAAG_STRENGEN, put_kolommen, strengrijen
            )
            tellingen[LAAG_LOCATIES] += _vul_laag(
                verbinding, LAAG_LOCATIES, locatie_kolommen, locatierijen
            )
            tellingen[TABEL_DEKKING] = _schrijf_dekking(
                verbinding, checks, alle, per_check, getrokken, geometrie, celgrootte, check_ids
            )
            _schrijf_herkomst(
                verbinding,
                bron,
                aantal,
                seed,
                celgrootte,
                buurten[1] if buurten else [],
                alleen_checks or [],
                f"{volgnummer} van {len(doelen)}",
            )
            verbinding.commit()
        finally:
            verbinding.close()
    tellingen["bestanden"] = len(doelen)
    return tellingen


def _schrijf_dekking(
    verbinding: sqlite3.Connection,
    checks: list[dict[str, Any]],
    alle: dict[str, list[dict[str, Any]]],
    per_check: dict[str, list[dict[str, Any]]],
    getrokken: dict[str, list[dict[str, Any]]],
    geometrie: dict[str, tuple[str, str, bytes, list[Any]]],
    celgrootte: float,
    in_dit_bestand: list[str],
) -> int:
    """Schrijft een rij per eigen check, ook voor de checks zonder bevindingen.

    `aantal_meldingen` is de telling van de hele run, `in_gebied` wat daarvan in de
    gekozen buurten ligt (gelijk zonder buurtkeuze). `zonder_object` sluit de
    telling: `getrokken` is de som van wat er in de puttenlaag, in de strengenlaag en
    nergens terechtkwam. `bestand` zegt of de check in dít bestand staat (1) of in een
    ander (0); de tabel is in elk bestand volledig.
    """
    kolommen = [
        ("check_id", "text"),
        ("omschrijving", "text"),
        ("categorie", "text"),
        ("ernst", "text"),
        ("dimensie", "text"),
        ("bekeken", "integer"),
        ("aantal_meldingen", "integer"),
        ("in_gebied", "integer"),
        ("getrokken", "integer"),
        ("zonder_locatie", "integer"),
        ("zonder_object", "integer"),
        ("cellen", "integer"),
        ("bestand", "integer"),
        ("reden", "text"),
    ]
    _maak_tabel(
        verbinding,
        TABEL_DEKKING,
        kolommen,
        "Een rij per eigen check: hoeveel er te trekken viel en wat er getrokken is.",
    )
    rijen = []
    for check in sorted(checks, key=lambda c: registervolgorde(str(c["check_id"]))):
        check_id = str(check["check_id"])
        totaal = alle.get(check_id, [])
        meldingen = per_check.get(check_id, [])
        keuze = getrokken.get(check_id, [])
        cellen = {cel(m["x"], m["y"], celgrootte) for m in meldingen} - {None}
        rijen.append(
            (
                check_id,
                check["omschrijving"],
                check["categorie"],
                check["ernst"],
                check["dimensie"],
                check["bekeken"],
                len(totaal),
                len(meldingen),
                len(keuze),
                sum(1 for m in keuze if m["x"] is None or m["y"] is None),
                sum(1 for m in keuze if str(m["gwsw_uri"]) not in geometrie),
                len(cellen),
                int(check_id in in_dit_bestand),
                reden(check, len(keuze), len(totaal) - len(meldingen)),
            )
        )
    velden = ", ".join(f'"{kolom}"' for kolom, _ in kolommen)
    plaatshouders = ", ".join("?" * len(kolommen))
    verbinding.executemany(
        f'insert into "{TABEL_DEKKING}" ({velden}) values ({plaatshouders})',
        rijen,
    )
    return len(rijen)


def _schrijf_herkomst(
    verbinding: sqlite3.Connection,
    bron: Path,
    aantal: int,
    seed: str,
    celgrootte: float,
    buurten: list[str],
    alleen_checks: list[str],
    bestand: str,
) -> None:
    """Schrijft de herkomst van dit bestand: gereedschap, bron en trekkingsinstellingen.

    Zonder deze tabel is een steekproefbestand een half jaar later niet meer te
    herleiden tot de run waaruit het komt, en is de trekking niet over te doen.
    """
    kolommen = [
        ("gereedschap", "text"),
        ("bron_geopackage", "text"),
        ("gemaakt_op", "text"),
        ("aantal_per_check", "integer"),
        ("seed", "text"),
        ("celgrootte_m", "real"),
        ("buurten", "text"),
        ("checks", "text"),
        ("bestand", "text"),
    ]
    _maak_tabel(verbinding, TABEL_RUN, kolommen, "Herkomst van deze steekproef en haar trekking.")
    verbinding.execute(
        f'insert into "{TABEL_RUN}" '
        "(gereedschap, bron_geopackage, gemaakt_op, aantal_per_check, seed, celgrootte_m, "
        "buurten, checks, bestand) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            gereedschap(),
            str(bron),
            date.today().isoformat(),
            aantal,
            seed,
            celgrootte,
            ", ".join(buurten),
            ", ".join(alleen_checks),
            bestand,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    """Leest de opdrachtregel en schrijft de steekproef."""
    ontleder = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ontleder.add_argument("bron", type=Path, help="GeoPackage van een toets-run.")
    ontleder.add_argument(
        "--uit",
        type=Path,
        default=None,
        help="Doelbestand; standaard steekproef.gpkg naast de bron.",
    )
    ontleder.add_argument(
        "--aantal", type=int, default=STANDAARD_AANTAL, help="Bevindingen per check."
    )
    ontleder.add_argument("--seed", default=STANDAARD_SEED, help="Seed van de trekking.")
    ontleder.add_argument(
        "--cel", type=float, default=STANDAARD_CEL_M, help="Maaswijdte van de spreiding in meters."
    )
    ontleder.add_argument(
        "--buurten",
        type=Path,
        default=None,
        help=f"CBS-buurtenbestand (GeoPackage met kolom {BUURT_NAAMKOLOM}); eist --buurt.",
    )
    ontleder.add_argument(
        "--buurt",
        action="append",
        default=[],
        help="Buurtnaam uit --buurten; herhaalbaar. Alleen meldingen daarbinnen tellen mee.",
    )
    ontleder.add_argument(
        "--per-bestand",
        type=int,
        default=None,
        help="Splits in genummerde bestanden van ten hoogste zoveel rijen (check blijft heel).",
    )
    ontleder.add_argument(
        "--check",
        action="append",
        default=[],
        help="Beperk tot dit check-ID; herhaalbaar. Standaard alle eigen checks.",
    )
    argumenten = ontleder.parse_args(argv)

    bron: Path = argumenten.bron
    if not bron.is_file():
        print(f"Fout: {bron} bestaat niet.", file=sys.stderr)
        return 1
    if argumenten.aantal < 1:
        print("Fout: --aantal moet ten minste 1 zijn.", file=sys.stderr)
        return 1
    if argumenten.cel <= 0:
        print("Fout: --cel moet groter dan 0 zijn.", file=sys.stderr)
        return 1
    if argumenten.per_bestand is not None and argumenten.per_bestand < 1:
        print("Fout: --per-bestand moet ten minste 1 zijn.", file=sys.stderr)
        return 1
    if bool(argumenten.buurten) != bool(argumenten.buurt):
        print("Fout: --buurten en --buurt horen bij elkaar.", file=sys.stderr)
        return 1
    if argumenten.buurten and not argumenten.buurten.is_file():
        print(f"Fout: {argumenten.buurten} bestaat niet.", file=sys.stderr)
        return 1
    doel: Path = argumenten.uit or bron.parent / "steekproef.gpkg"
    buurten = (argumenten.buurten, argumenten.buurt) if argumenten.buurten else None

    try:
        tellingen = schrijf_steekproef(
            bron,
            doel,
            argumenten.aantal,
            argumenten.seed,
            argumenten.cel,
            buurten,
            argumenten.per_bestand,
            argumenten.check or None,
        )
    except ValueError as fout:
        print(f"Fout: {fout}", file=sys.stderr)
        return 1
    print(f"Geschreven: {', '.join(str(p) for p in bestandsnamen(doel, tellingen['bestanden']))}")
    for naam, aantal in tellingen.items():
        print(f"  {naam}: {aantal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
