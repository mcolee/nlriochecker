"""Inlezen en valideren van de projectconfiguratie voor de check-engine."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from gwswpijplijn.errors import ConfigError

DEFAULT_CHECK_CONFIG_NAME = "checks.toml"


class ClassRoots(BaseModel):
    """Wortelklassen per rol; de subklassen volgen uit de ontologie."""

    model_config = ConfigDict(extra="forbid")

    put: list[str] = Field(min_length=1)
    vrijvervalleiding: list[str] = Field(min_length=1)
    # TOP-001 vraagt of er *enige* streng aansluit, niet of er een vrijvervalstreng
    # aansluit; een put aan een persleiding is niet losliggend.
    streng: list[str] = Field(default_factory=lambda: ["Leiding"])
    # NET-001 en NET-002 vragen elk om een ander soort eindpunt; een vuilwaterstreng
    # die alleen een uitlaat bereikt is niet in orde.
    afvoer_eindpunt: list[str] = Field(default_factory=list)
    lozings_eindpunt: list[str] = Field(default_factory=list)
    vuilwater: list[str] = Field(default_factory=list)
    hemelwater: list[str] = Field(default_factory=list)
    infiltratie: list[str] = Field(default_factory=list)
    drempel: list[str] = Field(default_factory=list)

    @property
    def netwerkknopen(self) -> list[str]:
        """De klassen die als knooppunt in de netwerkgraaf meetellen."""
        return [*self.put, *self.afvoer_eindpunt, *self.lozings_eindpunt]


class CheckThresholds(BaseModel):
    """Configureerbare drempelwaarden van de checks."""

    model_config = ConfigDict(extra="forbid")

    snapping_tolerantie_m: float = Field(default=0.10, gt=0.0)
    dubbele_put_tolerantie_m: float = Field(default=0.30, gt=0.0)


class CheckConfig(BaseModel):
    """De volledige projectconfiguratie van de check-engine."""

    model_config = ConfigDict(extra="forbid")

    klassen: ClassRoots
    drempels: CheckThresholds = Field(default_factory=CheckThresholds)


def default_check_config_path() -> Path:
    """Pad naar de meegeleverde standaardconfiguratie in het package."""
    return Path(str(resources.files("gwswpijplijn").joinpath(DEFAULT_CHECK_CONFIG_NAME)))


def load_check_config(path: Path | None = None) -> CheckConfig:
    """Leest de projectconfiguratie; zonder pad de meegeleverde standaard."""
    path = Path(path) if path is not None else default_check_config_path()

    try:
        inhoud = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"{path}: configbestand kan niet gelezen worden ({error}).") from error

    try:
        rauw = tomllib.loads(inhoud.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: geen geldige TOML ({error}).") from error

    try:
        return CheckConfig.model_validate(rauw)
    except ValidationError as error:
        raise ConfigError(f"{path}: configuratie is ongeldig.\n{error}") from error
