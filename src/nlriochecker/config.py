"""Inlezen en valideren van de configureerbare dekkingmapping (TOML)."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from nlriochecker.errors import ConfigError

DEFAULT_CONFIG_NAME = "dekking.toml"


class MessagePattern(BaseModel):
    """Een patroon dat SHACL-meldingen selecteert op vorm, objecttype en ernst.

    De SHACL-nulmeting benoemt de geschonden regel als vormnaam (kolom Source),
    bijvoorbeeld `LengteLeiding_val`. Dat is aanmerkelijk preciezer dan de vrije
    meldingtekst van het vervallen detailrapportformaat.
    """

    model_config = ConfigDict(extra="forbid")

    vorm: str | None = None
    vorm_prefix: str | None = None
    objecttype: list[str] = Field(default_factory=list)
    ernst: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _precies_een_vormveld(self) -> Self:
        """Eist precies een van `vorm` en `vorm_prefix`."""
        if (self.vorm is None) == (self.vorm_prefix is None):
            raise ValueError("geef precies een van 'vorm' of 'vorm_prefix' op")
        return self


class CheckMapping(BaseModel):
    """De dekkingclaim van een geschrapte check, met de bijbehorende meldingpatronen."""

    model_config = ConfigDict(extra="forbid")

    id: str
    onderwerp: str
    claim: str
    vereiste_cfk: list[str] = Field(min_length=1)
    bewijs: list[MessagePattern] = Field(min_length=1)
    tegenbewijs: list[MessagePattern] = Field(default_factory=list)


class Thresholds(BaseModel):
    """Configureerbare drempelwaarden."""

    model_config = ConfigDict(extra="forbid")

    typeringsscore_minimum: float = Field(default=95.0, ge=0.0, le=100.0)


class CoverageConfig(BaseModel):
    """De volledige dekkingconfiguratie zoals ingelezen uit een TOML-bestand."""

    model_config = ConfigDict(extra="forbid")

    checkregister_versie: str
    bron: str
    drempels: Thresholds = Field(default_factory=Thresholds)
    check: list[CheckMapping] = Field(min_length=1)

    @model_validator(mode="after")
    def _unieke_check_ids(self) -> Self:
        """Eist dat elk check-ID hoogstens een keer voorkomt."""
        ids = [mapping.id for mapping in self.check]
        duplicaten = sorted({check_id for check_id in ids if ids.count(check_id) > 1})
        if duplicaten:
            raise ValueError(f"dubbele check-ID's: {', '.join(duplicaten)}")
        return self

    def mapping(self, check_id: str) -> CheckMapping:
        """Geeft de mapping met dit check-ID, of `KeyError` als die er niet is."""
        for item in self.check:
            if item.id == check_id:
                return item
        raise KeyError(check_id)


def default_config_path() -> Path:
    """Pad naar de meegeleverde standaardmapping in het package."""
    return Path(str(resources.files("nlriochecker").joinpath(DEFAULT_CONFIG_NAME)))


def load_coverage_config(path: Path | None = None) -> CoverageConfig:
    """Leest de dekkingmapping; zonder pad wordt de meegeleverde standaard gebruikt."""
    path = Path(path) if path is not None else default_config_path()

    try:
        inhoud = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"{path}: configbestand kan niet gelezen worden ({error}).") from error

    try:
        rauw = tomllib.loads(inhoud.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: geen geldige TOML ({error}).") from error

    try:
        return CoverageConfig.model_validate(rauw)
    except ValidationError as error:
        raise ConfigError(f"{path}: configuratie is ongeldig.\n{error}") from error
