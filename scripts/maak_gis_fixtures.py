#!/usr/bin/env python
"""Schrijft de kleine externe-bronfixtures onder tests/fixtures/gis/ext.

De echte bronnen in `data/gis_koekangerveld/` dekken alleen Koekangerveld en zijn te
groot en te traag voor unit tests. Deze fixtures zijn miniatuurversies met dezelfde
structuur (dezelfde laagnamen, dezelfde attribuutnamen, EPSG:28992) in het lokale
assenstelsel dat de TTL-fixtures ook gebruiken.

Gebruik:  uv run python scripts/maak_gis_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point, box

# rasterio en pyogrio brengen elk hun eigen GDAL mee. Het raster wordt daarom als
# eerste geschreven, voordat geopandas geladen is; dat scheelt een hoop
# gepuzzel met twee GDAL-instanties in een proces.

DOEL = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "gis" / "ext"
GIS = DOEL.parent
RD = "EPSG:28992"

# De twee buurten van de multi-gebiedfixtures, op de coordinaten van
# `afbakening_kern_en_schil.ttl`. Noord omsluit put A en B, Zuid put C en D; streng
# B-C raakt ze allebei en is daarmee het grensobject waarop de dubbeltelling te
# zien is.
BUURTEN = {
    "Noord": (990.0, 1990.0, 1060.0, 2010.0),
    "Zuid": (1060.0, 1990.0, 1160.0, 2010.0),
}

# Het studiegebied van de fixtures: een vlak rond de TTL-coordinaten. Het was een
# smalle strook (980, 1980)-(1120, 2020) tot issue #104; de EXT-009-straten hebben
# ruimte nodig voor hun voronoi-vlakken (buffer 25 m) en liggen daarom zuidelijker.
# Put D op (2000, 2000) valt er nog steeds buiten -- daar leunen de EXT-tests op.
GEBIED = (900.0, 1900.0, 1200.0, 2100.0)
NODATA = 3.4028234663852886e38

# De bebouwde kom van de EXT-009-fixture (TOP10NL `plaats_vlak`) en het buitengebied
# erboven. De drie kandidaat-straten liggen in de kom; `Buitenweg` en `Fixturestraat`
# liggen erbuiten en vallen daarom af.
KOM = (900.0, 1900.0, 1200.0, 1970.0)
BUITEN_KOM = (900.0, 1970.0, 1200.0, 2100.0)


def schrijf(frame, pad: Path, laag: str) -> None:
    """Schrijft een laag naar een GeoPackage."""
    frame.set_crs(RD, allow_override=True).to_file(pad, layer=laag, driver="GPKG")
    print(f"{pad.name}:{laag} ({len(frame)})")


def main() -> None:
    """Schrijft alle fixturebestanden."""
    DOEL.mkdir(parents=True, exist_ok=True)
    for bestand in DOEL.glob("*"):
        if bestand.is_file():
            bestand.unlink()

    _schrijf_raster(DOEL / "ahn.tif")

    import geopandas as gpd

    schrijf(
        gpd.GeoDataFrame(
            {"statnaam": ["Fixturebuurt"]},
            geometry=[box(*GEBIED)],
        ),
        DOEL / "studiegebied.gpkg",
        "studiegebied",
    )

    bgt = DOEL / "bgt.gpkg"
    # Pand P1 ligt over streng 1 heen; EXT-001 moet die kruising vinden.
    schrijf(
        gpd.GeoDataFrame(
            {"lokaal_id": ["pand-1"], "status": ["bestaand"]},
            geometry=[box(1020.0, 1998.0, 1030.0, 2002.0)],
        ),
        bgt,
        "pand",
    )
    # W1 kruist streng 2 (gemengd), W2 kruist streng 3 (een zinker) en streng 6
    # (een duiker, en dus geen rioolleiding). De vier onderste zijn de grensgevallen
    # van issue #59: streng 7 eindigt in water-3 (lozingspunt), streng 8 ligt 0,5 m
    # naast water-4 (raakt niet), streng 9 doorkruist de 0,3 m smalle greppel
    # water-5 (echte doorkruising, geen drempel) en streng 10 loopt precies over de
    # oostrand van water-6 (tangentieel). Water-7 is een tweede smalle greppel die
    # streng 9 óók doorkruist: die streng levert dus twee bevindingen, en dat is de
    # bewaking tegen het terugkeren van de `break` na het eerste waterdeel (BO-43).
    schrijf(
        gpd.GeoDataFrame(
            {
                "lokaal_id": [
                    "water-1",
                    "water-2",
                    "water-3",
                    "water-4",
                    "water-5",
                    "water-6",
                    "water-7",
                ],
                "type": [
                    "waterloop",
                    "greppel",
                    "waterloop",
                    "waterloop",
                    "greppel",
                    "waterloop",
                    "greppel",
                ],
            },
            geometry=[
                box(1070.0, 1995.0, 1075.0, 2005.0),
                box(1015.0, 2005.0, 1020.0, 2015.0),
                box(1080.0, 1985.0, 1085.0, 1992.0),
                box(1090.0, 1985.0, 1095.0, 1992.0),
                box(1050.0, 1985.0, 1050.3, 1992.0),
                box(1100.0, 1985.0, 1103.0, 1992.0),
                box(1052.0, 1985.0, 1052.3, 1992.0),
            ],
        ),
        bgt,
        "waterdeel",
    )
    # Deksels bij put A en B; het deksel op (1100, 2000) heeft geen put.
    schrijf(
        gpd.GeoDataFrame(
            {"lokaal_id": ["deksel-A", "deksel-B", "deksel-los"]},
            geometry=[Point(1000.0, 2000.0), Point(1050.0, 2000.0), Point(1100.0, 2000.0)],
        ),
        bgt,
        "put",
    )
    schrijf(
        gpd.GeoDataFrame(
            {"lokaal_id": ["bouwwerk-1"], "type": ["niet-bgt"]},
            geometry=[box(1104.0, 2012.0, 1108.0, 2016.0)],
        ),
        bgt,
        "overigbouwwerk",
    )
    _schrijf_wegdelen(gpd, bgt)

    # Pand 1 ligt bij de riolering, pand 2 ver ervandaan.
    schrijf(
        gpd.GeoDataFrame(
            {
                "identificatie": ["bag-dichtbij", "bag-verweg"],
                "aantal_verblijfsobjecten": [1, 4],
                "bouwjaar": [1980, 1975],
            },
            geometry=[
                box(1025.0, 1996.0, 1028.0, 1998.0),
                box(1108.0, 1984.0, 1112.0, 1987.0),
            ],
        ),
        DOEL / "bag_pand.gpkg",
        "output",
    )

    _schrijf_wegvakken(gpd)
    _schrijf_kom(gpd)
    _schrijf_buurten(gpd)

    print(f"Geschreven in {DOEL}")


# De acht NWB-wegvakken van de EXT-009-fixture: drie kandidaten en vijf die om elk een
# eigen reden afvallen. De kolomnamen staan in kleine letters, net als in het
# Koekangerveld-extract; het De Wolden-extract schrijft ze in hoofdletters, en de lezer
# hoort daar ongevoelig voor te zijn.
#
# (naam, wegbehsrt, bst_code, wvk_id, lijn, waarom)
WEGVAKKEN = [
    ("Fixturestraat", "G", "VOW", 1, [(998.0, 2000.0), (1092.0, 2000.0)], "buiten de kom"),
    ("Rioolstraat", "G", "VOW", 2, [(920.0, 1940.0), (1000.0, 1940.0)], "kandidaat: bediend"),
    ("Lege Laan", "G", "VOW", 3, [(1020.0, 1940.0), (1100.0, 1940.0)], "kandidaat: leeg"),
    ("Grindweg", "G", "VOW", 4, [(920.0, 1910.0), (1000.0, 1910.0)], "kandidaat: onverhard"),
    ("Buitenweg", "G", "VOW", 5, [(920.0, 2050.0), (1000.0, 2050.0)], "buiten de kom"),
    ("Rijksweg", "R", "VOW", 6, [(1020.0, 1910.0), (1100.0, 1910.0)], "niet gemeentelijk"),
    ("Fietspad", "G", "FP", 7, [(1020.0, 1960.0), (1100.0, 1960.0)], "pad"),
    ("Kort Straatje", "G", "VOW", 8, [(920.0, 1960.0), (940.0, 1960.0)], "korter dan 25 m"),
]


def _schrijf_wegvakken(gpd) -> None:
    """Schrijft de NWB-wegvakken voor EXT-009."""
    schrijf(
        gpd.GeoDataFrame(
            {
                "stt_naam": [rij[0] for rij in WEGVAKKEN],
                "wegbehsrt": [rij[1] for rij in WEGVAKKEN],
                "bst_code": [rij[2] for rij in WEGVAKKEN],
                "wvk_id": [rij[3] for rij in WEGVAKKEN],
                "frc": ["6"] * len(WEGVAKKEN),
            },
            geometry=[LineString(rij[4]) for rij in WEGVAKKEN],
        ),
        DOEL / "nwb_wegvakken.gpkg",
        "output",
    )


def _schrijf_kom(gpd) -> None:
    """Schrijft het TOP10NL-plaatsvlak: een bebouwde kom en een buitengebied.

    Twee lagen in een bestand, net als het De Wolden-extract: `enige_laag` volstaat
    daar niet, dus de rol noemt haar laagnaam (`top10nl_komlagen`).
    """
    frame = gpd.GeoDataFrame(
        {
            "naamnl": ["Fixturekom", "Buitengebied"],
            "bebouwdekom": ["ja", "nee"],
            "typegebied": ["woonkern", "buurtschap"],
        },
        geometry=[box(*KOM), box(*BUITEN_KOM)],
    )
    pad = DOEL / "top10nl_plaats_vlak.gpkg"
    schrijf(frame, pad, "plaats_vlak")
    schrijf(frame.iloc[:1], pad, "output")


def _schrijf_wegdelen(gpd, bgt: Path) -> None:
    """Schrijft de BGT-wegdelen onder de EXT-009-straten.

    Rioolstraat en Lege Laan liggen op asfalt en klinkers, Grindweg op zand: die laatste
    komt daardoor boven het onverhard-aandeel uit en wordt niet beoordeeld.
    """
    schrijf(
        gpd.GeoDataFrame(
            {
                "lokaal_id": ["weg-1", "weg-2", "weg-3"],
                "plus_fysiek_voorkomen": ["asfalt", "betonstraatstenen", "zand"],
            },
            geometry=[
                box(920.0, 1937.0, 1000.0, 1943.0),
                box(1020.0, 1937.0, 1100.0, 1943.0),
                box(920.0, 1907.0, 1000.0, 1913.0),
            ],
        ),
        bgt,
        "wegdeel",
    )


def _schrijf_buurten(gpd) -> None:
    """Schrijft de studiegebiedbestanden voor de rapportage per gebied.

    Drie bestanden: een met beide buurten, en per buurt een met alleen die ene. De
    equivalentietest draait ze tegen elkaar; per gebied moeten de meldingen gelijk
    zijn aan die van de losse run.
    """
    schrijf(
        gpd.GeoDataFrame(
            {"naam_gebied": list(BUURTEN)},
            geometry=[box(*vak) for vak in BUURTEN.values()],
        ),
        GIS / "buurten_twee.gpkg",
        "buurten",
    )
    for naam, vak in BUURTEN.items():
        schrijf(
            gpd.GeoDataFrame({"naam_gebied": [naam]}, geometry=[box(*vak)]),
            GIS / f"buurt_{naam.lower()}.gpkg",
            "buurten",
        )


def _schrijf_raster(pad: Path) -> None:
    """Schrijft een vlak hoogteraster van 10,00 m NAP met een nodata-vlek.

    De vlek ligt rond (1040, 2010); een put daar valt op een cel zonder waarde en
    hoort in de toelichting van de AHN-checks terug te komen.
    """
    resolutie = 0.5
    links, onder, rechts, boven = GEBIED
    breedte = int((rechts - links) / resolutie)
    hoogte = int((boven - onder) / resolutie)

    raster = np.full((hoogte, breedte), 10.0, dtype="float32")
    transform = from_origin(links, boven, resolutie, resolutie)
    for rij in range(hoogte):
        for kolom in range(breedte):
            x = links + (kolom + 0.5) * resolutie
            y = boven - (rij + 0.5) * resolutie
            if 1035.0 <= x <= 1045.0 and 2005.0 <= y <= 2015.0:
                raster[rij, kolom] = NODATA

    with rasterio.open(
        pad,
        "w",
        driver="GTiff",
        height=hoogte,
        width=breedte,
        count=1,
        dtype="float32",
        crs=RD,
        transform=transform,
        nodata=NODATA,
    ) as doel:
        doel.write(raster, 1)
    print(f"{pad.name} ({breedte}x{hoogte} cellen)")


if __name__ == "__main__":
    main()
