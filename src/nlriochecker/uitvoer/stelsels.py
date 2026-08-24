"""De geregistreerde stelselboom uit de GWSW-export lezen (#17, #25).

#17 heeft aangetoond dat de OroX-export stelsels als objecten modelleert, in een
`hasPart`-boom `Stelsel -> strengen/putten`, met 100% dekking en exact één stelsel per
streng. De engine leidde deelstelsels tot dan toe af uit grafsamenhang
(`checks/verbanden.py`); dit leest de **geregistreerde** boom rechtstreeks.

Alleen de cartografische laag `stelsels` in de GeoPackage gebruikt hem. Een vlak baseert
zich op de **strengen** van een stelsel: #17 vond dat alle putten in een handvol
gemeentebrede buckets zitten, los van de strengen waarop ze fysiek aansluiten, dus de
omhullende van álle leden zou een gemeentebrede vlek geven. Een stelsel zonder strengen
(zo'n put-bucket) levert daarom geen vlak op.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDFS, URIRef

from nlriochecker.dataset import GwswDataset, parts_of
from nlriochecker.uitvoer.identiteit import kort


@dataclass(frozen=True)
class Stelselvlak:
    """Een geregistreerd stelsel met de strengen die eronder hangen.

    `stelseltype` is de korte, meest-specifieke klasse binnen de Stelsel-afsluiting
    (Vuilwaterstelsel, GemengdStelsel, ...); `strengen` zijn de streng-URI's die het
    stelsel via `hasPart` draagt, gesorteerd zodat twee runs dezelfde volgorde geven.
    """

    uri: str
    label: str
    stelseltype: str
    strengen: tuple[str, ...]

    @property
    def feature_id(self) -> str:
        """Het korte fragment van de stelsel-URI, zoals de andere lagen dat dragen."""
        return kort(self.uri)


def lees_stelsels(dataset: GwswDataset) -> list[Stelselvlak]:
    """De geregistreerde stelsels met ten minste één streng, gesorteerd op URI.

    Een stelsel zonder strengen (een put-bucket uit #17) krijgt geen vlak en valt hier
    weg. De volgorde is die van de stelsel-URI: determinisme boven leesbaarheid, net als
    bij de object- en trefferlagen.
    """
    afsluiting = dataset.closure("Stelsel")
    vlakken: list[Stelselvlak] = []
    for subject in sorted({str(s) for s in dataset.subjects_of_class("Stelsel")}):
        strengen = tuple(
            sorted(
                str(lid)
                for lid in parts_of(dataset.graph, URIRef(subject))
                if str(lid) in dataset.conduits
            )
        )
        if not strengen:
            continue
        vlakken.append(
            Stelselvlak(
                uri=subject,
                label=_label(dataset, subject),
                stelseltype=_stelseltype(dataset, subject, afsluiting),
                strengen=strengen,
            )
        )
    return vlakken


def _label(dataset: GwswDataset, uri: str) -> str:
    """Het rdfs:label van het stelsel, of leeg."""
    for waarde in dataset.graph.objects(URIRef(uri), RDFS.label):
        return str(waarde)
    return ""


def _stelseltype(dataset: GwswDataset, uri: str, afsluiting: frozenset[str]) -> str:
    """De korte, meest-specifieke klasse van het stelsel binnen de Stelsel-afsluiting.

    #17 vond dat een stelsel exact één type draagt, maar de meest-specifieke reductie
    hoort hier toch: leunen op die eigenschap zou een dataset met dubbele typering stil
    de verkeerde naam geven. De reductie komt uit `dataset._meest_specifiek`, dezelfde
    die `beheerobjecttype` gebruikt, zodat er geen tweede kopie van de subsumptieregel
    ontstaat.
    """
    typen = frozenset(t for t in dataset.graph_types_of(uri) if t in afsluiting)
    namen = sorted(_short(t) for t in dataset._meest_specifiek(typen))
    return namen[0] if namen else ""


def _short(uri: str) -> str:
    """De korte klassenaam achter de laatste scheidingstekens van een URI."""
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
