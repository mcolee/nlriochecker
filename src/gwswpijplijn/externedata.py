"""Externe geodata uit `data/gis/` voor de EXT- en AHN-checks.

De aangeleverde bronnen dekken alleen het studiegebied Koekangerveld, terwijl de
GWSW-dataset de hele gemeente De Wolden beslaat. Een GWSW-object buiten dat gebied
mag daarom nooit een check-uitslag krijgen: dat een BGT-deksel of BAG-pand ontbreekt
zegt daar niets over de datakwaliteit en alles over de dekking van de bron. Alle
EXT- en AHN-checks vragen daarom eerst `binnen_bereik()` en markeren de rest als
*buiten studiegebied*.

De laadfuncties zelf worden in blok C ingevuld.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry.base import BaseGeometry

from gwswpijplijn.errors import PipelineError


class ExternalDataError(PipelineError):
    """Een externe bron ontbreekt, is onleesbaar of staat in een ander stelsel."""


@dataclass(frozen=True)
class VectorLayer:
    """Een ingelezen vectorlaag uit een van de aangeleverde bestanden."""

    name: str
    source: Path
    crs: str
    geometries: tuple[BaseGeometry, ...]
    attributes: tuple[dict[str, object], ...] = ()

    def __len__(self) -> int:
        """Het aantal features."""
        return len(self.geometries)


@dataclass(frozen=True)
class ExternalData:
    """Alle beschikbare externe bronnen plus het bereik waarbinnen ze gelden."""

    extent: BaseGeometry | None = None
    extent_source: Path | None = None
    layers: dict[str, VectorLayer] = field(default_factory=dict)
    raster: RasterSampler | None = None
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def layer(self, rol: str) -> VectorLayer | None:
        """De laag die deze rol vervult, of None als die niet aangeleverd is."""
        return self.layers.get(rol)

    def binnen_bereik(self, geometrie: BaseGeometry | None) -> bool:
        """Geeft aan of een geometrie binnen het bereik van de externe bronnen valt."""
        if geometrie is None or geometrie.is_empty:
            return False
        if self.extent is None:
            return False
        return self.extent.intersects(geometrie)


@dataclass(frozen=True)
class RasterSampler:
    """Een hoogteraster waaruit op puntlocaties bemonsterd kan worden."""

    source: Path
    crs: str
    nodata: float | None
    bounds: tuple[float, float, float, float]
    _reader: object = None

    def sample(self, x: float, y: float) -> float | None:
        """De rasterwaarde op deze RD-coordinaat, of None buiten het raster."""
        raise NotImplementedError
