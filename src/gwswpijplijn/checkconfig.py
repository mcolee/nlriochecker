"""Inlezen en valideren van de projectconfiguratie voor de check-engine."""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    # TOP-019: knopen die alleen twee strengen aan elkaar knopen zonder eigen functie.
    functieloze_knoop: list[str] = Field(default_factory=list)
    # ADM-006: klassen die aangeven dat een object vervallen of nog gepland is.
    # De status zelf komt uit Begindatum en Einddatum; deze lijst is voor
    # datasets die er een eigen klasse voor gebruiken.
    vervallen: list[str] = Field(default_factory=list)
    # RVZ: hoe overstorten en bergbezinkvoorzieningen in de export verschijnen.
    overstortput: list[str] = Field(default_factory=list)
    overstortleiding: list[str] = Field(default_factory=list)
    bergbezinkvoorziening: list[str] = Field(default_factory=list)
    ledigingsvoorziening: list[str] = Field(default_factory=list)
    oppervlaktewater: list[str] = Field(default_factory=list)
    valconstructie: list[str] = Field(default_factory=list)
    # NET-005 en NET-006: welke leidingklassen tot welk stelseltype horen.
    stelseltypen: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def netwerkknopen(self) -> list[str]:
        """De klassen die als knooppunt in de netwerkgraaf meetellen."""
        return [*self.put, *self.afvoer_eindpunt, *self.lozings_eindpunt]

    def stelseltype(self, dataset_types: frozenset[str], closure) -> str | None:
        """Het stelseltype waar deze leidingklassen onder vallen, of None."""
        for naam in sorted(self.stelseltypen):
            for wortel in self.stelseltypen[naam]:
                if dataset_types & closure(wortel):
                    return naam
        return None


class PutTypeRule(BaseModel):
    """ADM-007: welke leiding- of onderdeelklasse bij een puttype hoort."""

    model_config = ConfigDict(extra="forbid")

    puttype: str
    vereist_een_van: list[str] = Field(min_length=1)
    toelichting: str = ""


class CheckThresholds(BaseModel):
    """Configureerbare drempelwaarden van de checks."""

    model_config = ConfigDict(extra="forbid")

    snapping_tolerantie_m: float = Field(default=0.10, gt=0.0)
    dubbele_put_tolerantie_m: float = Field(default=0.30, gt=0.0)

    # TOP-006: hoeveel twee strengen mogen afwijken en hoe lang ze moeten samenvallen.
    overlap_tolerantie_m: float = Field(default=0.05, gt=0.0)
    overlap_minimale_lengte_m: float = Field(default=1.0, gt=0.0)
    # TOP-007: onder deze lengte geldt een streng als nul-lengte.
    nul_lengte_m: float = Field(default=0.01, gt=0.0)
    # TOP-008: hoe ver de hartlijn van de rechte put-putverbinding mag afwijken.
    rechtheid_afwijking_m: float = Field(default=0.50, gt=0.0)
    # TOP-009: het geldige RD-bereik (EPSG:28992) in meters.
    rd_x_min: float = 0.0
    rd_x_max: float = 300_000.0
    rd_y_min: float = 300_000.0
    rd_y_max: float = 630_000.0
    # TOP-010: extra marge bovenop de halve diameter van beide strengen.
    diameterbuffer_marge_m: float = Field(default=0.0, ge=0.0)
    # TOP-013 en TOP-014: aantallen waarboven het onaannemelijk wordt.
    parallelle_strengen_maximum: int = Field(default=2, ge=1)
    aansluitende_strengen_maximum: int = Field(default=4, ge=1)
    # TOP-018: wanneer twee vertices als dubbel gelden en wanneer een hoek een spike is.
    dubbele_vertex_tolerantie_m: float = Field(default=0.01, gt=0.0)
    spike_hoek_graden: float = Field(default=5.0, gt=0.0, le=180.0)
    # TOP-021: hoe dicht een put bij een doorlopende streng mag liggen.
    put_op_streng_tolerantie_m: float = Field(default=0.50, gt=0.0)

    # ATTR-002: diameters onder deze waarde zijn onaannemelijk voor een riool.
    minimale_diameter_mm: float = Field(default=200.0, gt=0.0)
    # ATTR-005: eenheidsfout binnen bereik; een diameter onder deze waarde in
    # combinatie met een deelbaar-door-tien-patroon wijst op centimeters.
    eenheidsverdenking_diameter_mm: float = Field(default=100.0, gt=0.0)
    # ATTR-006: hoeveel de strengdiameter de putafmeting mag overschrijden.
    put_diameter_marge_mm: float = Field(default=0.0, ge=0.0)
    # ATTR-007: geldig bereik voor het aanlegjaar.
    aanlegjaar_minimum: int = Field(default=1870, ge=1)
    # ATTR-008: aannemelijk bereik voor de strenglengte.
    minimale_strenglengte_m: float = Field(default=1.0, gt=0.0)
    maximale_strenglengte_m: float = Field(default=200.0, gt=0.0)
    # ATTR-009: toegestane afwijking tussen geometrische en administratieve lengte.
    lengte_afwijking_procent: float = Field(default=5.0, gt=0.0)
    # ATTR-004: hoeveel breedte en hoogte bij een rond profiel mogen verschillen.
    rondheid_tolerantie_mm: float = Field(default=0.0, ge=0.0)

    # HGT-001 en HGT-002: afwijking van het maaiveld ten opzichte van het AHN.
    ahn_afwijking_waarschuwing_m: float = Field(default=0.05, gt=0.0)
    ahn_afwijking_fout_m: float = Field(default=0.25, gt=0.0)
    # HGT-003: hoe diep een BOB onder het AHN-maaiveld mag liggen.
    bob_maximale_diepte_m: float = Field(default=3.0, gt=0.0)
    # HGT-005 en HGT-006: tegenverhang licht en fors, in meter over de streng.
    tegenverhang_licht_m: float = Field(default=0.01, gt=0.0)
    tegenverhang_fors_m: float = Field(default=0.05, gt=0.0)
    # HGT-007: minimaal verhang per meter voor vuilwater en gemengd.
    minimaal_verhang_promille: float = Field(default=1.0, gt=0.0)
    # HGT-008: steiler dan een op zoveel is verdacht.
    extreem_verhang_een_op: float = Field(default=50.0, gt=0.0)
    # HGT-009 en HGT-016: BOB-sprong waarboven een valconstructie verwacht wordt.
    bob_sprong_m: float = Field(default=0.25, gt=0.0)
    # HGT-012: aannemelijk bereik voor de putdiepte.
    maximale_putdiepte_m: float = Field(default=6.0, gt=0.0)
    # HGT-013: gronddekking op de buiskruin.
    minimale_gronddekking_m: float = Field(default=0.50, gt=0.0)
    maximale_gronddekking_m: float = Field(default=4.0, gt=0.0)
    # HGT-014: hoeveel het leidingverhang van het maaiveldverloop mag afwijken.
    maaiveldvolging_afwijking_m: float = Field(default=1.0, gt=0.0)
    # HGT-015: marge van het putbodemniveau ten opzichte van de laagste BOB.
    putbodem_boven_bob_m: float = Field(default=0.05, gt=0.0)
    putbodem_zonk_m: float = Field(default=0.50, gt=0.0)
    # HGT-017: afwijking tussen de z-waarde uit de geometrie en de administratie.
    z_afwijking_m: float = Field(default=0.05, gt=0.0)

    # RVZ-004: afstand tot ontvangend oppervlaktewater.
    overstort_water_afstand_m: float = Field(default=25.0, gt=0.0)
    # RVZ-011: minimale waking van de overstortdrempel.
    minimale_waking_m: float = Field(default=0.40, gt=0.0)
    # NET-008: wanneer een deelstelsel klein heet en hoeveel lozingspunten opvallen.
    klein_deelstelsel_knopen: int = Field(default=25, ge=1)
    lozingspunten_per_deelstelsel: int = Field(default=2, ge=1)

    # BTR-003: leeftijd van de inwinning per grondsoort, in jaren.
    inwinning_maximale_leeftijd_jaar: int = Field(default=40, ge=1)
    # BTR-004: geldig bereik van de grondwaterstand ten opzichte van maaiveld.
    grondwater_maximale_diepte_m: float = Field(default=5.0, gt=0.0)
    # BTR-006: raster waarop afronding gemeten wordt, en het aandeel waarboven het
    # cluster als systematisch geldt.
    afronding_raster_m: float = Field(default=0.05, gt=0.0)
    afronding_aandeel_procent: float = Field(default=80.0, gt=0.0, le=100.0)
    afronding_minimum_waarnemingen: int = Field(default=30, ge=1)

    # EXT-checks: bufferafstanden tot de externe bronnen.
    ext_pand_buffer_m: float = Field(default=1.0, ge=0.0)
    ext_watergang_buffer_m: float = Field(default=1.0, ge=0.0)
    ext_putdeksel_afstand_m: float = Field(default=2.0, gt=0.0)
    ext_lozingspunt_water_afstand_m: float = Field(default=10.0, gt=0.0)
    ext_riolering_bij_pand_m: float = Field(default=40.0, gt=0.0)
    ext_perceel_buffer_m: float = Field(default=1.0, ge=0.0)


class NetworkOptions(BaseModel):
    """Keuzes voor de netwerkanalyse."""

    model_config = ConfigDict(extra="forbid")

    # 'administratief' volgt de van-naar-richting uit het GWSW-model, zoals het
    # register bedoelt; NET-003 toetst juist of die richting klopt. 'bob' leidt de
    # richting af uit het bodemverloop en valt terug op de administratieve richting
    # als een BOB ontbreekt of beide gelijk zijn.
    richting: Literal["administratief", "bob"] = "administratief"


class NulmetingOptions(BaseModel):
    """Eisen aan de aangeleverde nulmeting."""

    model_config = ConfigDict(extra="forbid")

    # Het checkregister eist dat de dataset aan alle conformiteitsklassen getoetst is;
    # welke dat zijn, hangt af van wat de GWSW-server aanbiedt.
    vereiste_cfk: list[str] = Field(default=["Hyd", "MdsPlan", "MdsProj"], min_length=1)


class NamingOptions(BaseModel):
    """ADM-003: de naamgevingsconventie als configureerbaar regex-patroon."""

    model_config = ConfigDict(extra="forbid")

    # Zonder patroon draait ADM-003 niet; een verzonnen conventie zou elke dataset
    # afkeuren. Het register noemt het patroon expliciet projectafhankelijk.
    putpatroon: str | None = None
    strengpatroon: str | None = None

    @model_validator(mode="after")
    def _geldige_patronen(self) -> Self:
        """Eist dat de opgegeven patronen te compileren zijn."""
        for naam, patroon in (
            ("putpatroon", self.putpatroon),
            ("strengpatroon", self.strengpatroon),
        ):
            if patroon is None:
                continue
            try:
                re.compile(patroon)
            except re.error as error:
                raise ValueError(f"{naam} is geen geldig regex-patroon: {error}") from error
        return self


class ExternalSources(BaseModel):
    """Paden en laagnamen van de externe bronnen uit data/gis/."""

    model_config = ConfigDict(extra="forbid")

    map: str = "data/gis"
    bgt: str | None = None
    bag_pand: str | None = None
    nwb_wegvakken: str | None = None
    studiegebied: str | None = None
    ahn_dtm: str | None = None
    # Welke BGT-lagen welke rol vervullen; per aangeleverde export in te vullen.
    bgt_pandlagen: list[str] = Field(default_factory=list)
    bgt_waterlagen: list[str] = Field(default_factory=list)
    bgt_putdeksellagen: list[str] = Field(default_factory=list)
    bgt_overige_bouwwerklagen: list[str] = Field(default_factory=list)


class CheckConfig(BaseModel):
    """De volledige projectconfiguratie van de check-engine."""

    model_config = ConfigDict(extra="forbid")

    klassen: ClassRoots
    drempels: CheckThresholds = Field(default_factory=CheckThresholds)
    netwerk: NetworkOptions = Field(default_factory=NetworkOptions)
    nulmeting: NulmetingOptions = Field(default_factory=NulmetingOptions)
    naamgeving: NamingOptions = Field(default_factory=NamingOptions)
    puttyperegels: list[PutTypeRule] = Field(default_factory=list)
    bronnen: ExternalSources = Field(default_factory=ExternalSources)


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
