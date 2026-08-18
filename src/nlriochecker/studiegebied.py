"""Afbakening van de analyse tot een studiegebied.

Een studiegebiedbestand met een enkele feature levert een `StudyArea`: de rapportage
wordt tot dat gebied beperkt en er verandert niets aan de uitvoervorm. Bevat het
bestand meer features, dan levert het een `Studiegebieden` met een `StudyArea` per
feature, en rapporteert `toets` per gebied in een eigen submap.

De validatie zit hier en nergens anders, en ze is streng: een defect gebiedsbestand
dat pas na drie minuten laden opvalt, of erger, dat stilzwijgend een half gebied
rapporteert, kost meer dan een harde foutmelding vooraf.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from shapely import from_wkb
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from nlriochecker.errors import StudyAreaError

logger = logging.getLogger(__name__)

# De GWSW-coordinaten staan in Rijksdriehoek; herprojecteren doen we niet.
RD_NEW = 28992

# GeoPackage Binary: 'GP', versie, vlaggen, srs_id, envelope, dan de WKB.
GPKG_MAGIC = b"GP"
GPKG_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}

# De kolom of property waarmee een bestand met meerdere features zijn gebieden
# benoemt. Bij een enkele feature is hij optioneel; daarboven verplicht, want zonder
# naam is er geen submap en geen kolom om de uitvoer aan te herkennen.
KOLOM_NAAM = "naam_gebied"

# Alleen vlakken begrenzen een gebied. Een GeometryCollection wordt niet uitgepakt:
# dan zouden er vlakken meedoen die de gebruiker niet als gebied aanleverde.
VLAKTYPEN = frozenset({"Polygon", "MultiPolygon"})

# Meer namen dan dit in een foutmelding opsommen leest niet meer; dan het aantal
# plus de dichtstbijzijnde suggesties.
MAX_NAMEN_IN_MELDING = 10

# Alles buiten deze tekens wordt in een mapnaam een underscore: hij moet op elk
# bestandssysteem te maken zijn en in een pad leesbaar blijven.
_ONVEILIG = re.compile(r"[^a-z0-9]+")


class RdGrenzen(NamedTuple):
    """De omhullende waarbinnen RD-coordinaten horen te vallen."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float


def mapnaam(naam: str) -> str:
    """Zet een gebiedsnaam om in een veilige mapnaam.

    Diakrieten eraf, lowercase, alles wat geen letter of cijfer is naar een
    underscore, opeenvolgende underscores samengevoegd. Alleen het bestandssysteem
    krijgt deze vorm; in de rapporttitels, de kolom `Gebied` en de JSON blijft de
    originele naam staan.
    """
    ontleed = unicodedata.normalize("NFKD", naam)
    zonder_diakrieten = "".join(teken for teken in ontleed if not unicodedata.combining(teken))
    veilig = _ONVEILIG.sub("_", zonder_diakrieten.lower()).strip("_")
    if not veilig:
        raise StudyAreaError(
            f"{naam!r} levert geen bruikbare mapnaam op: er blijft na sanering niets over."
        )
    return veilig


@dataclass(frozen=True)
class StudyArea:
    """Het gebied waartoe de rapportage beperkt wordt."""

    name: str
    geometry: BaseGeometry
    source: Path
    feature_count: int
    # De gebiedsaanduiding die in de GIS-uitvoer per object komt te staan. Uit
    # `naam_gebied` als het bestand die kolom heeft, anders uit de CBS-attributen,
    # anders de laagnaam.
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


@dataclass(frozen=True)
class Studiegebieden:
    """Alle features van een studiegebiedbestand, elk als eigen gebied.

    Een bestand met een enkele feature levert via `totaal` precies wat
    `load_study_area` altijd al leverde. Met meer features rapporteert `toets` per
    gebied; de gebieden overlappen dan niet, maar objecten op de grens tellen wel in
    elk rakend gebied mee (zie `StudyArea.bevat`).
    """

    gebieden: tuple[StudyArea, ...]
    source: Path
    laag: str
    # De overgeslagen geometrietypen, als leesbare regels. Ze gaan mee naar de
    # uitvoer: wat niet bekeken is hoort in het rapport te staan.
    overgeslagen: tuple[str, ...] = ()
    # Alle gebiedsnamen in het bestand, ook na een selectie met `selecteer`.
    beschikbaar: tuple[str, ...] = ()
    # De terugval-gebiedsaanduiding van het bestand als geheel (CBS-attributen of
    # laagnaam), voor `totaal` bij meerdere features.
    aanduiding: str = ""

    @property
    def enkel(self) -> bool:
        """Geeft aan of het bestand precies een gebied bevat."""
        return len(self.gebieden) == 1

    @property
    def totaal(self) -> StudyArea:
        """Alle features als een gebied: de unie.

        Bij een enkele feature is dat die feature zelf, tot en met haar naam. Wie
        alleen de omhullende van het bestand nodig heeft (`externedata`) heeft hier
        genoeg aan.
        """
        if self.enkel:
            return self.gebieden[0]
        return StudyArea(
            name=_naam(self.source, self.laag),
            geometry=unary_union([gebied.geometry for gebied in self.gebieden]),
            source=self.source,
            feature_count=len(self.gebieden),
            gebied=self.aanduiding or self.laag,
        )

    def selecteer(self, namen: Sequence[str]) -> Studiegebieden:
        """Beperkt de run tot de opgegeven gebiedsnamen.

        Matcht exact op de originele naam, niet op de gesaneerde mapnaam: de
        gebruiker leest de namen in zijn eigen bestand. Een naam die niet voorkomt is
        een fout -- stil overslaan zou een typefout laten lezen als een gebied zonder
        bevindingen. De validatie van het volledige bestand is op dit moment al
        gebeurd, zodat een deelrun geen defect bestand maskeert.
        """
        if not namen:
            return self
        aanwezig = {gebied.gebied: gebied for gebied in self.gebieden}
        onbekend = [naam for naam in namen if naam not in aanwezig]
        if onbekend:
            raise StudyAreaError(
                f"{self.source}: {_opsomming(onbekend)} "
                f"{'komen' if len(onbekend) > 1 else 'komt'} niet in het bestand voor. "
                f"{self._namenhulp(onbekend)}"
            )
        gekozen = tuple(aanwezig[naam] for naam in dict.fromkeys(namen))
        return Studiegebieden(
            gebieden=gekozen,
            source=self.source,
            laag=self.laag,
            overgeslagen=self.overgeslagen,
            beschikbaar=self.beschikbaar,
            aanduiding=self.aanduiding,
        )

    def _namenhulp(self, onbekend: Sequence[str]) -> str:
        """Noemt de beschikbare namen, of bij veel gebieden het aantal plus suggesties."""
        if len(self.beschikbaar) <= MAX_NAMEN_IN_MELDING:
            return f"Beschikbaar: {', '.join(self.beschikbaar)}."
        suggesties = sorted(
            {
                match
                for naam in onbekend
                for match in difflib.get_close_matches(naam, self.beschikbaar, n=3)
            }
        )
        staart = f" Bedoelde je: {', '.join(suggesties)}?" if suggesties else ""
        return f"Het bestand telt {len(self.beschikbaar)} gebieden.{staart}"


@dataclass(frozen=True)
class _Ruw:
    """Wat een formaatlezer oplevert, voor de gedeelde validatie eroverheen."""

    features: list[tuple[BaseGeometry, dict[str, object]]]
    laag: str
    aanduiding: str


def load_studiegebieden(
    path: Path, laag: str | None = None, *, grenzen: RdGrenzen | None = None
) -> Studiegebieden:
    """Leest een studiegebiedbestand als een gebied per feature.

    `grenzen` is de RD-omhullende waartegen een GeoJSON zonder eigen CRS-vermelding
    getoetst wordt. Zonder grenzen blijft die toets achterwege: wie ze niet kent,
    kan er ook geen oordeel over vellen, en een verzonnen grens is erger dan geen.
    """
    path = Path(path)
    if not path.exists():
        raise StudyAreaError(f"{path}: bestand bestaat niet.")

    if path.suffix.lower() in {".gpkg", ".geopackage"}:
        ruw = _lees_geopackage(path, laag)
    elif path.suffix.lower() in {".geojson", ".json"}:
        ruw = _lees_geojson(path, grenzen)
    else:
        raise StudyAreaError(
            f"{path}: onbekend formaat {path.suffix!r}. Gebruik een GeoPackage of GeoJSON."
        )
    return _bouw_gebieden(path, ruw)


def load_study_area(
    path: Path, laag: str | None = None, *, grenzen: RdGrenzen | None = None
) -> StudyArea:
    """Leest een studiegebied als een enkel gebied: de unie van alle features."""
    return load_studiegebieden(path, laag, grenzen=grenzen).totaal


def _bouw_gebieden(path: Path, ruw: _Ruw) -> Studiegebieden:
    """Valideert de gelezen features en bouwt er de gebieden uit.

    Deze stap staat los van het formaat, zodat GeoPackage en GeoJSON niet elk hun
    eigen eisen kunnen ontwikkelen.
    """
    vlakken, overgeslagen = _filter_vlakken(ruw.features)
    if not vlakken:
        raise StudyAreaError(
            f"{path}: laag {ruw.laag!r} bevat geen enkel vlak. Alleen Polygon en "
            f"MultiPolygon begrenzen een gebied"
            + (f"; overgeslagen: {'; '.join(overgeslagen)}." if overgeslagen else ".")
        )

    gebieden: tuple[StudyArea, ...]
    if len(vlakken) == 1:
        geometrie, attributen = vlakken[0]
        naam = _naamwaarde(attributen)
        gebieden = (
            StudyArea(
                name=_naam(path, ruw.laag),
                geometry=geometrie,
                source=path,
                feature_count=1,
                gebied=naam or ruw.aanduiding or ruw.laag,
            ),
        )
    else:
        namen = _gebiedsnamen(path, ruw.laag, vlakken)
        gebieden = tuple(
            StudyArea(
                name=naam,
                geometry=geometrie,
                source=path,
                feature_count=1,
                gebied=naam,
            )
            for naam, (geometrie, _) in zip(namen, vlakken, strict=True)
        )

    for melding in overgeslagen:
        logger.warning("%s: %s", path, melding)

    return Studiegebieden(
        gebieden=gebieden,
        source=path,
        laag=ruw.laag,
        overgeslagen=overgeslagen,
        beschikbaar=tuple(gebied.gebied for gebied in gebieden),
        aanduiding=ruw.aanduiding,
    )


def _gebiedsnamen(
    path: Path, laag: str, vlakken: Sequence[tuple[BaseGeometry, dict[str, object]]]
) -> list[str]:
    """De gebiedsnamen van een bestand met meer dan een feature, streng getoetst."""
    ontbreekt = [
        index for index, (_, attributen) in enumerate(vlakken) if KOLOM_NAAM not in attributen
    ]
    if ontbreekt:
        kolommen = sorted({sleutel for _, attributen in vlakken for sleutel in attributen})
        raise StudyAreaError(
            f"{path}: laag {laag!r} telt {len(vlakken)} vlakken en heeft daarom een "
            f"kolom {KOLOM_NAAM!r} nodig om ze uit elkaar te houden. Gevonden: "
            f"{', '.join(kolommen) or 'geen kolommen'}."
        )

    namen: list[str] = []
    for index, (_, attributen) in enumerate(vlakken, start=1):
        naam = _naamwaarde(attributen)
        if not naam:
            raise StudyAreaError(
                f"{path}: laag {laag!r} heeft in rij {index} een lege {KOLOM_NAAM}. "
                f"Elk gebied moet een naam hebben; die wordt de submap en de kolom Gebied."
            )
        namen.append(naam)

    dubbel = [naam for naam, aantal in Counter(namen).items() if aantal > 1]
    if dubbel:
        raise StudyAreaError(
            f"{path}: laag {laag!r} heeft {_opsomming(dubbel)} meer dan een keer als "
            f"{KOLOM_NAAM}. Namen moeten uniek zijn; samenvoegen doen we niet stilzwijgend."
        )

    per_mapnaam: dict[str, str] = {}
    for naam in namen:
        veilig = mapnaam(naam)
        eerder = per_mapnaam.get(veilig)
        if eerder is not None:
            raise StudyAreaError(
                f"{path}: {eerder!r} en {naam!r} leveren dezelfde mapnaam {veilig!r} op; de "
                f"uitvoer van het ene gebied zou die van het andere overschrijven."
            )
        per_mapnaam[veilig] = naam
    return namen


def _naamwaarde(attributen: dict[str, object]) -> str:
    """De waarde van `naam_gebied`, ontdaan van omringende spaties."""
    waarde = attributen.get(KOLOM_NAAM)
    return str(waarde).strip() if waarde is not None else ""


def _opsomming(namen: Sequence[str]) -> str:
    """Een leesbare opsomming van namen tussen aanhalingstekens."""
    return ", ".join(repr(naam) for naam in namen)


def _filter_vlakken(
    features: list[tuple[BaseGeometry, dict[str, object]]],
) -> tuple[list[tuple[BaseGeometry, dict[str, object]]], tuple[str, ...]]:
    """Houdt alleen de vlakken over en meldt wat er afvalt.

    Nooit stilzwijgend: een gebiedsbestand waarin per ongeluk de puntenlaag zit,
    moet dat zeggen in plaats van een half gebied te rapporteren.
    """
    vlakken = [paar for paar in features if paar[0].geom_type in VLAKTYPEN]
    overige = Counter(paar[0].geom_type for paar in features if paar[0].geom_type not in VLAKTYPEN)
    overgeslagen = tuple(
        f"{aantal} object(en) van het type {soort} overgeslagen: geen vlak"
        for soort, aantal in sorted(overige.items())
    )
    return vlakken, overgeslagen


def _lees_geopackage(path: Path, laag: str | None) -> _Ruw:
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

        cursor = verbinding.execute(f'select * from "{_escape(laag)}"')
        kolommen = [beschrijving[0] for beschrijving in cursor.description]
        geometrie_index = kolommen.index(geometriekolom[0])
        features: list[tuple[BaseGeometry, dict[str, object]]] = []
        for rij in cursor.fetchall():
            blob = rij[geometrie_index]
            if not blob:
                continue
            attributen = {
                naam: waarde
                for index, (naam, waarde) in enumerate(zip(kolommen, rij, strict=True))
                if index != geometrie_index
            }
            features.append((_ontleed_gpkg(blob), attributen))
        aanduiding = _gebiedsaanduiding(verbinding, laag)
    except sqlite3.Error as error:
        raise StudyAreaError(f"{path}: kan niet gelezen worden ({error}).") from error
    finally:
        verbinding.close()

    if not features:
        raise StudyAreaError(f"{path}: laag {laag!r} bevat geen geometrieen.")

    return _Ruw(features=features, laag=laag, aanduiding=aanduiding)


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


def _lees_geojson(path: Path, grenzen: RdGrenzen | None) -> _Ruw:
    """Leest een studiegebied uit GeoJSON en toetst het coordinaatstelsel.

    RFC 7946 kent formeel alleen WGS84, dus het bestand zegt zelden welk stelsel het
    voert. Twee dingen tellen: een legacy `crs`-member die EPSG:28992 noemt is
    afdoende, en anders moeten alle coordinaten binnen de meegegeven RD-omhullende
    vallen. Zonder meegegeven grenzen blijft die tweede toets achterwege.
    """
    try:
        inhoud = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StudyAreaError(f"{path}: geen leesbare GeoJSON ({error}).") from error

    features = inhoud.get("features") if inhoud.get("type") == "FeatureCollection" else [inhoud]
    gelezen: list[tuple[BaseGeometry, dict[str, object]]] = []
    for feature in features or []:
        geometrie = feature.get("geometry") if "geometry" in feature else feature
        if geometrie:
            eigenschappen = feature.get("properties") or {}
            gelezen.append((shape(geometrie), dict(eigenschappen)))

    if not gelezen:
        raise StudyAreaError(f"{path}: bevat geen geometrieen.")

    if not _noemt_rd(inhoud) and grenzen is not None:
        _toets_rd_bereik(path, gelezen, grenzen)

    return _Ruw(features=gelezen, laag=path.stem, aanduiding=path.stem)


def _noemt_rd(inhoud: dict[str, object]) -> bool:
    """Geeft aan of een legacy `crs`-member expliciet EPSG:28992 noemt."""
    crs = inhoud.get("crs")
    if not isinstance(crs, dict):
        return False
    eigenschappen = crs.get("properties")
    naam = eigenschappen.get("name", "") if isinstance(eigenschappen, dict) else ""
    return str(RD_NEW) in str(naam)


def _toets_rd_bereik(
    path: Path, features: Sequence[tuple[BaseGeometry, dict[str, object]]], grenzen: RdGrenzen
) -> None:
    """Toetst of alle coordinaten binnen de RD-omhullende vallen."""
    omhullende = unary_union([geometrie for geometrie, _ in features]).bounds
    x_min, y_min, x_max, y_max = omhullende
    binnen = (
        grenzen.x_min <= x_min
        and x_max <= grenzen.x_max
        and grenzen.y_min <= y_min
        and y_max <= grenzen.y_max
    )
    if not binnen:
        raise StudyAreaError(
            f"{path}: de coordinaten ({x_min:.1f}, {y_min:.1f}) - ({x_max:.1f}, {y_max:.1f}) "
            f"vallen buiten Rijksdriehoek ({grenzen.x_min:.0f}-{grenzen.x_max:.0f}, "
            f"{grenzen.y_min:.0f}-{grenzen.y_max:.0f}). Het bestand staat vermoedelijk in "
            f"WGS84; herprojecteer het eerst naar EPSG:{RD_NEW}, of zet een crs-member in het "
            f"bestand als het wel degelijk RD is."
        )


def _naam(path: Path, laag: str) -> str:
    """Een leesbare naam voor het gebied."""
    return f"{path.stem}:{laag}" if laag != path.stem else path.stem
