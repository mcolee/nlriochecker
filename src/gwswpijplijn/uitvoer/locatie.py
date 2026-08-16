"""De foutlocatie van een melding: waar het probleem zit, niet waar het object staat.

De kaartlaag `meldinglocaties` zet elke melding als punt neer. Voor een kruising is
dat het snijpunt, voor een attribuutfout op een streng het midden ervan, en voor een
melding over een deelstelsel het zwaartepunt van dat deel. Alleen de check zelf weet
zulke bijzondere plekken; die geeft ze mee onder de sleutel `foutlocatie`. Voor de
rest volstaat de geometrie van het object.
"""

from __future__ import annotations

from shapely.geometry import Point

from gwswpijplijn.checks import Finding
from gwswpijplijn.dataset import GwswDataset

# Onder deze detailsleutel geeft een check zelf de plek van het probleem op, als
# een (x, y)-paar in Rijksdriehoek.
SLEUTEL_FOUTLOCATIE = "foutlocatie"


def foutlocatie(finding: Finding, dataset: GwswDataset) -> Point | None:
    """Bepaalt het punt waarop deze melding op de kaart hoort te staan."""
    eigen = finding.details.get(SLEUTEL_FOUTLOCATIE)
    if eigen is not None:
        return _punt(eigen)

    # Een object dat niet uit de GWSW-dataset komt (een BGT-putdeksel zonder put,
    # een BAG-verblijfsobject zonder riolering) draagt zijn coordinaat zelf.
    if finding.location is not None:
        return _punt(finding.location)

    node = dataset.nodes.get(finding.object_uri)
    if node is not None and node.point is not None:
        return node.point

    conduit = dataset.conduits.get(finding.object_uri)
    if conduit is not None and conduit.line is not None and not conduit.line.is_empty:
        return conduit.line.interpolate(0.5, normalized=True)

    return None


def _punt(coordinaat: object) -> Point | None:
    """Maakt een punt van een (x, y)-paar; alles anders levert niets op."""
    if isinstance(coordinaat, Point):
        return coordinaat
    if isinstance(coordinaat, (tuple, list)) and len(coordinaat) == 2:
        return Point(float(coordinaat[0]), float(coordinaat[1]))
    return None
