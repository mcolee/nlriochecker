"""Afbakening van de analyse tot een studiegebied."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shapely import from_wkb
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from nlriochecker.errors import StudyAreaError

# De GWSW-coordinaten staan in Rijksdriehoek; herprojecteren doen we niet.
RD_NEW = 28992

# GeoPackage Binary: 'GP', versie, vlaggen, srs_id, envelope, dan de WKB.
GPKG_MAGIC = b"GP"
GPKG_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


@dataclass(frozen=True)
class StudyArea:
    """Het gebied waartoe de rapportage beperkt wordt."""

    name: str
    geometry: BaseGeometry
    source: Path
    feature_count: int
    # De gebiedsaanduiding die in de GIS-uitvoer per object komt te staan. Uit de
    # CBS-attributen als het bestand ze heeft, anders de laagnaam.
    gebied: str = ""

    @property
    def area_ha(self) -> float:
        """Het oppervlak in hectare."""
        return self.geometry.area / 10_000

    def bevat(self, geometrie: BaseGeometry | None) -> bool:
        """Geeft aan of een geometrie het gebied raakt.

        Een punt moet erbinnen liggen; een lijn telt mee zodra hij het gebied
        snijdt, zodat een streng die de grens kruist niet wegvalt. Objecten zonder
        geometrie vallen buiten; de beller telt die apart.
        """
        if geometrie is None or geometrie.is_empty:
            return False
        return self.geometry.intersects(geometrie)


def load_study_area(path: Path, laag: str | None = None) -> StudyArea:
    """Leest een studiegebied uit een GeoPackage of GeoJSON."""
    path = Path(path)
    if not path.exists():
        raise StudyAreaError(f"{path}: bestand bestaat niet.")

    if path.suffix.lower() in {".gpkg", ".geopackage"}:
        return _lees_geopackage(path, laag)
    if path.suffix.lower() in {".geojson", ".json"}:
        return _lees_geojson(path)
    raise StudyAreaError(
        f"{path}: onbekend formaat {path.suffix!r}. Gebruik een GeoPackage of GeoJSON."
    )


def _lees_geopackage(path: Path, laag: str | None) -> StudyArea:
    """Leest een laag uit een GeoPackage met de standaardbibliotheek."""
    try:
        verbinding = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as error:
        raise StudyAreaError(f"{path}: kan niet geopend worden ({error}).") from error

    try:
        lagen = verbinding.execute(
            "select table_name, srs_id from gpkg_contents where data_type = 'features'"
        ).fetchall()
        if not lagen:
            raise StudyAreaError(f"{path}: bevat geen feature-lagen.")

        namen = [naam for naam, _ in lagen]
        if laag is None:
            if len(namen) > 1:
                raise StudyAreaError(
                    f"{path}: bevat meerdere lagen ({', '.join(namen)}). Kies er een met "
                    f"--studiegebied-laag."
                )
            laag = namen[0]
        elif laag not in namen:
            raise StudyAreaError(
                f"{path}: laag {laag!r} bestaat niet. Beschikbaar: {', '.join(namen)}."
            )

        srs_id = dict(lagen)[laag]
        if srs_id != RD_NEW:
            raise StudyAreaError(
                f"{path}: laag {laag!r} staat in EPSG:{srs_id}, maar de GWSW-data staat in "
                f"EPSG:{RD_NEW}. Herprojecteer het bestand eerst."
            )

        geometriekolom = verbinding.execute(
            "select column_name from gpkg_geometry_columns where table_name = ?", (laag,)
        ).fetchone()
        if geometriekolom is None:
            raise StudyAreaError(f"{path}: laag {laag!r} heeft geen geometriekolom.")

        rijen = verbinding.execute(
            f'select "{_escape(geometriekolom[0])}" from "{_escape(laag)}"'
        ).fetchall()
        geometrieen = [_ontleed_gpkg(blob) for (blob,) in rijen if blob]
        gebied = _gebiedsaanduiding(verbinding, laag)
    except sqlite3.Error as error:
        raise StudyAreaError(f"{path}: kan niet gelezen worden ({error}).") from error
    finally:
        verbinding.close()

    if not geometrieen:
        raise StudyAreaError(f"{path}: laag {laag!r} bevat geen geometrieen.")

    return StudyArea(
        name=_naam(path, laag),
        geometry=unary_union(geometrieen),
        source=path,
        feature_count=len(geometrieen),
        gebied=gebied or laag,
    )


def _escape(naam: str) -> str:
    """Maakt een tabel- of kolomnaam veilig voor SQL-interpolatie.

    Een laagnaam komt van de gebruiker (`--studiegebied-laag`) en kan niet als
    parameter meegegeven worden; verdubbelde aanhalingstekens is de manier die
    SQLite daarvoor kent.
    """
    return naam.replace('"', '""')


def _gebiedsaanduiding(verbinding: sqlite3.Connection, laag: str) -> str:
    """De CBS-code en -naam van het gebied, als het bestand ze draagt.

    Het Koekangerveld-bestand is een CBS-buurt met `statcode` en `statnaam`. Andere
    gebiedsbestanden hebben die kolommen niet; dan blijft het bij de laagnaam.
    """
    kolommen = {rij[1] for rij in verbinding.execute(f'pragma table_info("{_escape(laag)}")')}
    if not {"statcode", "statnaam"} <= kolommen:
        return ""

    rij = verbinding.execute(f'select statcode, statnaam from "{_escape(laag)}" limit 1').fetchone()
    if rij is None:
        return ""
    code, naam = (waarde or "" for waarde in rij)
    return f"{code} {naam}".strip()


def _ontleed_gpkg(blob: bytes) -> BaseGeometry:
    """Haalt de WKB uit een GeoPackage-geometrieblob."""
    if blob[:2] != GPKG_MAGIC:
        raise StudyAreaError("geometrie is geen GeoPackage-blob")
    vlaggen = blob[3]
    envelope = (vlaggen >> 1) & 0x07
    if envelope not in GPKG_ENVELOPE_BYTES:
        raise StudyAreaError(f"onbekend envelope-type {envelope} in de GeoPackage-blob")
    return from_wkb(blob[8 + GPKG_ENVELOPE_BYTES[envelope] :])


def _lees_geojson(path: Path) -> StudyArea:
    """Leest een studiegebied uit GeoJSON; die staat per definitie in WGS84 tenzij anders."""
    try:
        inhoud = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyAreaError(f"{path}: geen leesbare GeoJSON ({error}).") from error

    features = inhoud.get("features") if inhoud.get("type") == "FeatureCollection" else [inhoud]
    geometrieen = []
    for feature in features or []:
        geometrie = feature.get("geometry") if "geometry" in feature else feature
        if geometrie:
            geometrieen.append(shape(geometrie))

    if not geometrieen:
        raise StudyAreaError(f"{path}: bevat geen geometrieen.")

    return StudyArea(
        name=path.stem,
        geometry=unary_union(geometrieen),
        source=path,
        feature_count=len(geometrieen),
        gebied=path.stem,
    )


def _naam(path: Path, laag: str) -> str:
    """Een leesbare naam voor het gebied."""
    return f"{path.stem}:{laag}" if laag != path.stem else path.stem
