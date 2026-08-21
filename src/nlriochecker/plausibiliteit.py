"""Inlezen van de plausibiliteitstabellen voor de ATTR-checks.

De tabellen materiaal-versus-diameter, materiaal-versus-aanlegjaar,
materiaal-versus-profielvorm en leidingmateriaal-versus-putmateriaal staan in een
apart TOML-bestand. Het zijn vakinhoudelijke aannames die per project verschillen
(een gemeente met veel oud metselwerk hanteert andere grenzen dan een nieuwbouwkern),
dus ze horen in configuratie en niet in de code.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nlriochecker.errors import ConfigError

DEFAULT_PLAUSIBILITY_NAME = "plausibiliteit.toml"


class MaterialDiameter(BaseModel):
    """ATTR-001: het aannemelijke diameterbereik per leidingmateriaal, in mm."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    minimum_mm: float | None = None
    maximum_mm: float | None = None
    toelichting: str = ""


class MaterialYear(BaseModel):
    """ATTR-003: vanaf (en eventueel tot) welk jaar een materiaal voorkomt."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
    vanaf_jaar: int | None = None
    tot_jaar: int | None = None
    toelichting: str = ""


class MaterialShape(BaseModel):
    """ATTR-012: welke profielvormen bij een leidingmateriaal passen."""

    model_config = ConfigDict(extra="forbid")

    materiaal: str
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
    onwaarschijnlijke_putmaterialen: list[str] = Field(min_length=1)
    toelichting: str = ""


class ShapeDimensions(BaseModel):
    """ATTR-004: wat er bij een profielvorm over breedte en hoogte moet gelden."""

    model_config = ConfigDict(extra="forbid")

    vorm: str
    breedte_gelijk_hoogte: bool = False
    hoogte_groter_dan_breedte: bool = False
    hoogte_kleiner_dan_breedte: bool = False
    toelichting: str = ""


class PlausibilityTables(BaseModel):
    """Alle plausibiliteitstabellen samen."""

    model_config = ConfigDict(extra="forbid")

    bron: str = ""
    materiaal_diameter: list[MaterialDiameter] = Field(default_factory=list)
    materiaal_aanlegjaar: list[MaterialYear] = Field(default_factory=list)
    materiaal_vorm: list[MaterialShape] = Field(default_factory=list)
    leiding_put_materiaal: list[ConduitManholeMaterial] = Field(default_factory=list)
    vorm_afmeting: list[ShapeDimensions] = Field(default_factory=list)
    standaarddiameters_mm: list[float] = Field(default_factory=list)

    def diameter(self, materiaal: str | None) -> MaterialDiameter | None:
        """De diameterregel voor dit materiaal, of None."""
        return _zoek(self.materiaal_diameter, "materiaal", materiaal)

    def aanlegjaar(self, materiaal: str | None) -> MaterialYear | None:
        """De aanlegjaarregel voor dit materiaal, of None."""
        return _zoek(self.materiaal_aanlegjaar, "materiaal", materiaal)

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
