"""De foutlocatie van een melding: waar het probleem zit, niet waar het object staat.

Voor een kruising is dat het snijpunt, voor een attribuutfout op een streng het midden
ervan, en voor een melding over een deelstelsel het zwaartepunt van dat deel. Alleen de
check zelf weet zulke bijzondere plekken; die geeft ze mee onder de sleutel
`foutlocatie`. Voor de rest volstaat de geometrie van het object.

De uitvoer draagt hem als `X`/`Y` in de CSV, als `foutlocatie` in de JSON en als
`x`/`y` in de meldingentabel van de GeoPackage. Een eigen kaartlaag is er sinds issue
#13 niet meer; de gebreken staan op het object zelf.
"""

from __future__ import annotations

from gwsw_orox_helpers.dataset import GwswDataset
from shapely.geometry import LinearRing, LineString, Point
from shapely.geometry.base import BaseGeometry

from nlriochecker.checks import Finding

# Onder deze detailsleutel geeft een check zelf de plek van het probleem op, als
# een (x, y)-paar in Rijksdriehoek.
SLEUTEL_FOUTLOCATIE = "foutlocatie"


def foutlocatie(finding: Finding, dataset: GwswDataset) -> Point | None:
    """Bepaalt het punt waarop deze melding op de kaart hoort te staan."""
    eigen = finding.details.get(SLEUTEL_FOUTLOCATIE)
    if eigen is not None:
        return _punt(eigen)

    # Een object dat niet uit de GWSW-dataset komt (bijvoorbeeld een BGT-putdeksel
    # zonder put, EXT-003) draagt zijn coordinaat zelf.
    if finding.location is not None:
        return _punt(finding.location)

    return objectlocatie(dataset, finding.object_uri)


def objectlocatie(dataset: GwswDataset, uri: str) -> Point | None:
    """De plek van een object zelf: zijn punt, of het midden van zijn lijn.

    Los van `Finding`, want de overtredingen uit de SHACL-nulmeting hebben er geen
    en hoeven er ook geen te verzinnen om op de kaart te komen.
    """
    node = dataset.nodes.get(uri)
    if node is not None and node.point is not None:
        return node.point

    conduit = dataset.conduits.get(uri)
    if conduit is not None and conduit.line is not None and not conduit.line.is_empty:
        return _middelpunt(conduit.line)

    return None


def _middelpunt(geometrie: BaseGeometry) -> Point:
    """Het punt halverwege een lijn, of anders een punt op de geometrie zelf.

    TOP-015 en TOP-016 melden juist objecten met een geometrie die geen nette lijn
    is -- een vlak, een multipart. `interpolate` weigert die; dan is een
    representatief punt beter dan geen melding op de kaart.
    """
    if isinstance(geometrie, (LineString, LinearRing)):
        return geometrie.interpolate(0.5, normalized=True)
    return geometrie.representative_point()


def _punt(coordinaat: object) -> Point | None:
    """Maakt een punt van een (x, y)-paar; alles anders levert niets op."""
    if isinstance(coordinaat, Point):
        return coordinaat
    if isinstance(coordinaat, (tuple, list)) and len(coordinaat) == 2:
        return Point(float(coordinaat[0]), float(coordinaat[1]))
    return None
