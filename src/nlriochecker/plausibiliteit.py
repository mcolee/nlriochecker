"""Inlezen van de plausibiliteitstabellen voor de ATTR-checks.

De tabellen materiaal-versus-diameter, materiaal-versus-begindatum,
materiaal-versus-profielvorm en leidingmateriaal-versus-putmateriaal staan in een
apart TOML-bestand. Het zijn vakinhoudelijke aannames die per project verschillen
(een gemeente met veel oud metselwerk hanteert andere grenzen dan een nieuwbouwkern),
dus ze horen in configuratie en niet in de code.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nlriochecker.errors import ConfigError

DEFAULT_PLAUSIBILITY_NAME = "plausibiliteit.toml"

# De herkomst van een tabelregel. De vier eerste zijn harde projectankers; komt een
# waarde uit geen van die vier -- een fabrikantmaattabel, een NEN-norm, wetgeving of
# een expertaanname -- dan is `ervaringsregel` de eerlijke bak en staat de specifieke
# bron in `toelichting`. Zie issue #20; de sweep staat in
# `tests/test_plausibiliteit_herkomst.py`.
Bron = Literal[
    "ontologie",
    "checkregister",
    "RIONED Kennisbank",
    "Leidraad C2100",
    "ervaringsregel",
]


class MaterialDiameter(BaseModel):
    """ATTR-001: het aannemelijke diameterbereik per leidingmateriaal, in mm."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    bron: Bron
    minimum_mm: float | None = None
    maximum_mm: float | None = None
    toelichting: str = ""


class MinimumDiameter(BaseModel):
    """ATTR-002: de gangbare ondergrens per stelseltype, in mm.

    Vervangt de ene drempel `minimale_diameter_mm`: een gemengd of hemelwaterriool
    begint hoger dan een vuilwaterriool. Het stelseltype volgt uit de eigen
    GWSW-klasse van de streng (`klassen.stelseltypen`); een streng zonder herkenbaar
    type valt op de regel `overig` terug.
    """

    model_config = ConfigDict(extra="forbid")

    stelseltype: str
    bron: Bron
    minimum_mm: float = Field(gt=0.0)
    toelichting: str = ""


class MaterialRoughness(BaseModel):
    """ATTR-017: de aannemelijke wandruwheid per leidingmateriaal, in mm.

    De band omsluit de door RIONED geautoriseerde defaultwaarde uit Leidraad
    Riolering C2100 tabel B2.1, met ruimte voor een beter gefundeerde projectwaarde;
    de bron staat in `toelichting`. Dezelfde vorm als `MaterialDiameter`.
    """

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    bron: Bron
    minimum_mm: float | None = None
    maximum_mm: float | None = None
    toelichting: str = ""


class MaterialYear(BaseModel):
    """ATTR-003: vanaf (en eventueel tot) welk jaar een materiaal voorkomt."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    bron: Bron
    vanaf_jaar: int | None = None
    tot_jaar: int | None = None
    toelichting: str = ""


class MaterialShape(BaseModel):
    """ATTR-012: welke profielvormen bij een leidingmateriaal passen."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    bron: Bron
    toegestane_vormen: list[str] = Field(min_length=1)
    toelichting: str = ""


class ConduitManholeMaterial(BaseModel):
    """ATTR-010: welk putmateriaal onwaarschijnlijk is bij een leidingmateriaal.

    De tabel noemt het verbod en niet de toestemming. Een lijst met verwachte
    materialen maakt van elk lid van `MateriaalPutColl` dat niemand heeft ingetypt
    een bevinding, en dat waren er 26 van de 30 (issue #43).
    """

    model_config = ConfigDict(extra="forbid")

    leidingmateriaal: str
    bron: Bron
    onwaarschijnlijke_putmaterialen: list[str] = Field(min_length=1)
    toelichting: str = ""


class ShapeDimensions(BaseModel):
    """ATTR-004: wat er bij een profielvorm over breedte en hoogte moet gelden."""

    model_config = ConfigDict(extra="forbid")

    vorm: str
    bron: Bron
    breedte_gelijk_hoogte: bool = False
    hoogte_groter_dan_breedte: bool = False
    hoogte_kleiner_dan_breedte: bool = False
    toelichting: str = ""


class PlausibilityTables(BaseModel):
    """Alle plausibiliteitstabellen samen."""

    model_config = ConfigDict(extra="forbid")

    bron: str = ""
    materiaal_diameter: list[MaterialDiameter] = Field(default_factory=list)
    minimale_diameter: list[MinimumDiameter] = Field(default_factory=list)
    materiaal_wandruwheid: list[MaterialRoughness] = Field(default_factory=list)
    materiaal_begindatum: list[MaterialYear] = Field(default_factory=list)
    materiaal_vorm: list[MaterialShape] = Field(default_factory=list)
    leiding_put_materiaal: list[ConduitManholeMaterial] = Field(default_factory=list)
    vorm_afmeting: list[ShapeDimensions] = Field(default_factory=list)
    standaarddiameters_mm: list[float] = Field(default_factory=list)

    def diameter(self, materiaal: str | None) -> MaterialDiameter | None:
        """De diameterregel voor dit materiaal, of None."""
        return _zoek(self.materiaal_diameter, "materiaal", materiaal)

    def ondergrens(self, stelseltype: str | None) -> MinimumDiameter | None:
        """De ondergrensregel voor dit stelseltype, met terugval op `overig`."""
        regel = _zoek(self.minimale_diameter, "stelseltype", stelseltype)
        if regel is not None:
            return regel
        return _zoek(self.minimale_diameter, "stelseltype", "overig")

    def wandruwheid(self, materiaal: str | None) -> MaterialRoughness | None:
        """De wandruwheidsband voor dit materiaal, of None."""
        return _zoek(self.materiaal_wandruwheid, "materiaal", materiaal)

    def begindatum(self, materiaal: str | None) -> MaterialYear | None:
        """De begindatumregel (tijdvak) voor dit materiaal, of None."""
        return _zoek(self.materiaal_begindatum, "materiaal", materiaal)

    def vorm(self, materiaal: str | None) -> MaterialShape | None:
        """De profielvormregel voor dit materiaal, of None."""
        return _zoek(self.materiaal_vorm, "materiaal", materiaal)

    def putmateriaal(self, materiaal: str | None) -> ConduitManholeMaterial | None:
        """De putmateriaalregel voor dit leidingmateriaal, of None."""
        return _zoek(self.leiding_put_materiaal, "leidingmateriaal", materiaal)

    def afmetingen(self, vorm: str | None) -> ShapeDimensions | None:
        """De afmetingsregel voor deze profielvorm, of None."""
        return _zoek(self.vorm_afmeting, "vorm", vorm)

    def is_standaardmaat(self, waarde: float | None) -> bool:
        """Geeft aan of deze maat op de lijst met handelsmaten staat."""
        return waarde is not None and any(
            abs(waarde - maat) < 0.5 for maat in self.standaarddiameters_mm
        )


def _zoek(regels: list, veld: str, waarde: str | None):
    """De eerste regel waarvan het veld gelijk is aan de waarde."""
    if waarde is None:
        return None
    for regel in regels:
        if getattr(regel, veld) == waarde:
            return regel
    return None


def default_plausibility_path() -> Path:
    """Pad naar de meegeleverde plausibiliteitstabellen in het package."""
    return Path(str(resources.files("nlriochecker").joinpath(DEFAULT_PLAUSIBILITY_NAME)))


def load_plausibility(path: Path | None = None) -> PlausibilityTables:
    """Leest de plausibiliteitstabellen; zonder pad de meegeleverde standaard."""
    path = Path(path) if path is not None else default_plausibility_path()

    try:
        inhoud = path.read_bytes()
    except OSError as error:
        raise ConfigError(
            f"{path}: plausibiliteitstabellen kunnen niet gelezen worden ({error})."
        ) from error

    try:
        rauw = tomllib.loads(inhoud.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: geen geldige TOML ({error}).") from error

    try:
        return PlausibilityTables.model_validate(rauw)
    except ValidationError as error:
        raise ConfigError(f"{path}: plausibiliteitstabellen zijn ongeldig.\n{error}") from error
