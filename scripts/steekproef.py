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

Gebruik:

    uv run python scripts/steekproef.py uitvoer/<run>/dq_*.gpkg
    uv run python scripts/steekproef.py <run.gpkg> --uit steekproef.gpkg --aantal 10
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

# De velden die uit `meldingen` meekomen, in de volgorde waarin ze in de steekproef
# staan. `oordeel` en `opmerking` staan er niet bij: die blijven leeg en zijn er om
# in QGIS zelf in te vullen.
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


def steekproefkolommen(met_objectlaag: bool) -> list[tuple[str, str]]:
    """De kolommen van een steekproeflaag.

    `objectlaag` staat alleen op `steekproef_locaties`: daar is het de enige plek
    waar te zien is of het object zelf in de puttenlaag of in de strengenlaag ligt.
    """
    kolommen = [("steekproef_nr", "integer")]
    kolommen += [(veld, _kolomtype(veld)) for veld in MELDINGVELDEN]
    kolommen += [("objecttype", "text")]
    if met_objectlaag:
        kolommen += [("objectlaag", "text")]
    return kolommen + [("oordeel", "text"), ("opmerking", "text")]


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
    verbinding: sqlite3.Connection, uris: set[str]
) -> dict[str, tuple[str, str, bytes]]:
    """Zoekt per object-URI de laag, het objecttype en de geometrieblob op.

    Alleen de URI's van de getrokken meldingen, en per laag in blokken: een `in`-lijst
    met tienduizenden waarden is niet nodig als de steekproef er een paar honderd telt.
    """
    gevonden: dict[str, tuple[str, str, bytes]] = {}
    lijst = sorted(uris)
    for laag in ("putten", "strengen"):
        for begin in range(0, len(lijst), 500):
            blok = lijst[begin : begin + 500]
            plaatshouders = ", ".join("?" * len(blok))
            for uri, objecttype, geom in verbinding.execute(
                f'select gwsw_uri, objecttype, geom from "{laag}" '
                f"where gwsw_uri in ({plaatshouders})",
                blok,
            ):
                gevonden.setdefault(str(uri), (laag, str(objecttype or ""), geom))
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


def reden(check: dict[str, Any], getrokken: int) -> str:
    """Waarom er niets te trekken viel; leeg zodra er wel een steekproef is.

    Een lege regel in de dekkingstabel zou lezen als "check draaide en vond niets",
    en dat is precies het misverstand dat dit project vermijdt: een skelet en een
    check die niets te bekijken had zeggen iets heel anders dan een schone uitslag.
    """
    if getrokken:
        return ""
    if check["skelet"]:
        return f"skelet: {check['skelet']}"
    if not check["bekeken"]:
        return "niets bekeken"
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
    melding: dict[str, Any], nummer: int, objecttype: str, objectlaag: str | None
) -> list[Any]:
    """Zet een getrokken melding om in een rij van een steekproeflaag."""
    waarden: list[Any] = [nummer]
    waarden += [melding[veld] for veld in MELDINGVELDEN]
    waarden += [objecttype]
    if objectlaag is not None:
        waarden += [objectlaag]
    return waarden + ["", ""]


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


def schrijf_steekproef(
    bron: Path,
    doel: Path,
    aantal: int,
    seed: str,
    celgrootte: float,
) -> dict[str, int]:
    """Trekt de steekproef uit `bron` en schrijft haar naar `doel`.

    Levert per laag het aantal geschreven rijen, zodat de aanroeper kan melden wat
    er in het bestand staat.

    `doel` mag de bron niet zijn: die wordt gewist voordat er gelezen wordt, en dan
    is een run van minuten weg door een typefout. Dezelfde voorwaarde als
    `uitvoer/gpkg.py` stelt -- nooit een invoerbestand overschrijven.
    """
    if doel.resolve() == bron.resolve():
        raise ValueError(f"{doel} is de bron-GeoPackage zelf; kies een ander doelbestand.")
    doel.unlink(missing_ok=True)

    lezen = _open_bron(bron)
    try:
        checks = lees_checks(lezen)
        per_check = lees_meldingen(lezen)
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
        geometrie = lees_geometrie(lezen, uris)
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

    put_kolommen = steekproefkolommen(met_objectlaag=False)
    locatie_kolommen = steekproefkolommen(met_objectlaag=True)
    putrijen: list[tuple[bytes, list[Any]]] = []
    strengrijen: list[tuple[bytes, list[Any]]] = []
    locatierijen: list[tuple[bytes, list[Any]]] = []

    for check_id in sorted(getrokken):
        for nummer, melding in enumerate(getrokken[check_id], start=1):
            laag, objecttype, geom = geometrie.get(str(melding["gwsw_uri"]), ("", "", b""))
            if laag == "putten":
                putrijen.append((geom, _rij(melding, nummer, objecttype, None)))
            elif laag == "strengen":
                strengrijen.append((geom, _rij(melding, nummer, objecttype, None)))
            if melding["x"] is not None and melding["y"] is not None:
                locatierijen.append(
                    (
                        _punt(float(melding["x"]), float(melding["y"])),
                        _rij(melding, nummer, objecttype, laag or "geen"),
                    )
                )

    verbinding = sqlite3.connect(doel)
    try:
        _leg_fundament(verbinding)
        _maak_laag(
            verbinding,
            LAAG_PUTTEN,
            "POINT",
            put_kolommen,
            "Getrokken meldingen op een put, met de geometrie van de put.",
        )
        _maak_laag(
            verbinding,
            LAAG_STRENGEN,
            "LINESTRING",
            put_kolommen,
            "Getrokken meldingen op een streng, met de geometrie van de streng.",
        )
        _maak_laag(
            verbinding,
            LAAG_LOCATIES,
            "POINT",
            locatie_kolommen,
            "De foutlocatie van elke getrokken melding: de plek waar de check op wijst.",
        )
        tellingen = {
            LAAG_PUTTEN: _vul_laag(verbinding, LAAG_PUTTEN, put_kolommen, putrijen),
            LAAG_STRENGEN: _vul_laag(verbinding, LAAG_STRENGEN, put_kolommen, strengrijen),
            LAAG_LOCATIES: _vul_laag(verbinding, LAAG_LOCATIES, locatie_kolommen, locatierijen),
        }
        tellingen[TABEL_DEKKING] = _schrijf_dekking(
            verbinding, checks, per_check, getrokken, geometrie, celgrootte
        )
        _schrijf_herkomst(verbinding, bron, aantal, seed, celgrootte)
        verbinding.commit()
    finally:
        verbinding.close()
    return tellingen


def _schrijf_dekking(
    verbinding: sqlite3.Connection,
    checks: list[dict[str, Any]],
    per_check: dict[str, list[dict[str, Any]]],
    getrokken: dict[str, list[dict[str, Any]]],
    geometrie: dict[str, tuple[str, str, bytes]],
    celgrootte: float,
) -> int:
    """Schrijft een rij per eigen check, ook voor de checks zonder bevindingen.

    `zonder_object` sluit de telling: `getrokken` is de som van wat er in de
    puttenlaag, in de strengenlaag en nergens terechtkwam. Zonder die kolom zou een
    ontbrekend object alleen uit een vergelijking tussen de lagen af te leiden zijn.
    """
    kolommen = [
        ("check_id", "text"),
        ("omschrijving", "text"),
        ("categorie", "text"),
        ("ernst", "text"),
        ("dimensie", "text"),
        ("bekeken", "integer"),
        ("aantal_meldingen", "integer"),
        ("getrokken", "integer"),
        ("zonder_locatie", "integer"),
        ("zonder_object", "integer"),
        ("cellen", "integer"),
        ("reden", "text"),
    ]
    _maak_tabel(
        verbinding,
        TABEL_DEKKING,
        kolommen,
        "Een rij per eigen check: hoeveel er te trekken viel en wat er getrokken is.",
    )
    rijen = []
    for check in checks:
        check_id = str(check["check_id"])
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
                len(meldingen),
                len(keuze),
                sum(1 for m in keuze if m["x"] is None or m["y"] is None),
                sum(1 for m in keuze if str(m["gwsw_uri"]) not in geometrie),
                len(cellen),
                reden(check, len(keuze)),
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
    verbinding: sqlite3.Connection, bron: Path, aantal: int, seed: str, celgrootte: float
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
    ]
    _maak_tabel(verbinding, TABEL_RUN, kolommen, "Herkomst van deze steekproef en haar trekking.")
    verbinding.execute(
        f'insert into "{TABEL_RUN}" '
        "(gereedschap, bron_geopackage, gemaakt_op, aantal_per_check, seed, celgrootte_m) "
        "values (?, ?, ?, ?, ?, ?)",
        (gereedschap(), str(bron), date.today().isoformat(), aantal, seed, celgrootte),
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
    doel: Path = argumenten.uit or bron.parent / "steekproef.gpkg"

    try:
        tellingen = schrijf_steekproef(
            bron, doel, argumenten.aantal, argumenten.seed, argumenten.cel
        )
    except ValueError as fout:
        print(f"Fout: {fout}", file=sys.stderr)
        return 1
    print(f"Geschreven: {doel}")
    for naam, aantal in tellingen.items():
        print(f"  {naam}: {aantal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
