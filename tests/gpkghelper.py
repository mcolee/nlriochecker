"""Een minimale GeoPackage-schrijver voor de studiegebiedfixtures.

De vaste fixtures (`buurten_twee.gpkg` en de twee losse buurten) komen uit
`scripts/maak_gis_fixtures.py` en staan onder versiebeheer. Wat hier staat is voor
de gevallen die niet als bestand willen bestaan: een gebiedsbestand dat uit de echte
De Wolden en Hoogeveen-buurt afgeleid wordt, en de tachtig kunstmatige buurten van de schaaltest.
Die laatste zou als bestand alleen maar meeslepen, en met geopandas erbij zou hij een
zware afhankelijkheid aan een test hangen die hem verder niet nodig heeft.

Bewust dezelfde route als `studiegebied.py` gebruikt om te lezen: stdlib `sqlite3`
plus shapely, geen extra afhankelijkheid.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

RD_NEW = 28992


def schrijf_vlakken(
    pad: Path,
    laag: str,
    vlakken: list[tuple[dict[str, str], BaseGeometry]],
    kolommen: tuple[str, ...] = ("lokaal_id",),
) -> Path:
    """Schrijft een vlakkenlaag met vrije tekstkolommen naar een GeoPackage.

    Voor de EXT-tests: een BGT-achtige laag met of juist zonder `lokaal_id`, zodat
    zowel de gewone sleutel als de terugval op de geometriehash te toetsen is. Bestaat
    het bestand al, dan komt de laag erbij; zo passen meerdere rollen in een bestand,
    net als in de echte BGT-export.

    Met geopandas geschreven en niet met stdlib `sqlite3`, anders dan `schrijf_buurten`
    hieronder: `externedata.py` leest zijn lagen via pyogrio, en dat weigert een
    GeoPackage zonder `gpkg_spatial_ref_sys`. Dezelfde route als
    `scripts/maak_gis_fixtures.py`, dus geen extra afhankelijkheid.
    """
    import geopandas as gpd

    frame = gpd.GeoDataFrame(
        {kolom: [attributen.get(kolom, "") for attributen, _ in vlakken] for kolom in kolommen},
        geometry=[vlak for _, vlak in vlakken],
    )
    frame.set_crs(f"EPSG:{RD_NEW}", allow_override=True).to_file(pad, layer=laag, driver="GPKG")
    return pad


def schrijf_buurten(
    pad: Path,
    vlakken: list[tuple[str, BaseGeometry]],
    laag: str = "buurten",
    kolom: str = "naam_gebied",
) -> Path:
    """Schrijft een GeoPackage met een vlak en een naam per feature."""
    verbinding = sqlite3.connect(pad)
    verbinding.execute("PRAGMA application_id = 0x47504B47")
    verbinding.execute(
        "create table gpkg_contents (table_name text, data_type text, identifier text, "
        "srs_id integer)"
    )
    verbinding.execute(
        "create table gpkg_geometry_columns (table_name text, column_name text, "
        "geometry_type_name text, srs_id integer)"
    )
    verbinding.execute(
        f'create table "{laag}" (fid integer primary key, "{kolom}" text, geom blob)'
    )
    verbinding.execute(
        "insert into gpkg_contents values (?, 'features', ?, ?)", (laag, laag, RD_NEW)
    )
    verbinding.execute(
        "insert into gpkg_geometry_columns values (?, 'geom', 'POLYGON', ?)", (laag, RD_NEW)
    )
    kop = b"GP" + bytes([0, 0]) + struct.pack("<i", RD_NEW)
    for naam, vlak in vlakken:
        verbinding.execute(
            f'insert into "{laag}" ("{kolom}", geom) values (?, ?)', (naam, kop + vlak.wkb)
        )
    verbinding.commit()
    verbinding.close()
    return pad


def schrijf_buurtenraster(pad: Path, aantal: int, omhullende: tuple[float, ...]) -> Path:
    """Verdeelt een omhullende in `aantal` stroken en schrijft ze als buurten.

    De schaaltest van de 80-buurtencasus: elke strook is een eigen gebied met een
    eigen naam, zodat de run er evenveel submappen voor moet maken.
    """
    x_min, y_min, x_max, y_max = omhullende
    breedte = (x_max - x_min) / aantal
    vlakken = [
        (
            f"Buurt {index + 1:03d}",
            box(x_min + index * breedte, y_min, x_min + (index + 1) * breedte, y_max),
        )
        for index in range(aantal)
    ]
    return schrijf_buurten(pad, vlakken)
