"""Inlezen van een GWSW-OroX-dataset (TTL) tot een toetsbaar domeinmodel."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.term import Node as RdfNode
from shapely.geometry import LineString, Point

from nlriochecker.errors import DatasetError
from nlriochecker.geometry import (
    GeometryError,
    is_multipart_literal,
    parse_gml,
    parse_gml_z,
)

GWSW = "http://data.gwsw.nl/1.6/totaal/"

# Turtle moet volgens de spec UTF-8 zijn. Sommige exports (BrutIS) schrijven een
# handvol bytes in een MS-DOS-codering; cp850 is de gangbare Nederlandse variant.
FALLBACK_ENCODING = "cp850"

HAS_ASPECT = URIRef(f"{GWSW}hasAspect")
HAS_PART = URIRef(f"{GWSW}hasPart")
HAS_CONNECTION = URIRef(f"{GWSW}hasConnection")
HAS_VALUE = URIRef(f"{GWSW}hasValue")
HAS_REFERENCE = URIRef(f"{GWSW}hasReference")

KLASSE_INWINNING = URIRef(f"{GWSW}Inwinning")
KLASSE_WIJZE_VAN_INWINNING = URIRef(f"{GWSW}WijzeVanInwinning")
KLASSE_DATUM_INWINNING = URIRef(f"{GWSW}DatumInwinning")
KLASSE_MAAIVELDORIENTATIE = URIRef(f"{GWSW}Maaiveldorientatie")
KLASSE_MAAIVELDHOOGTE = URIRef(f"{GWSW}Maaiveldhoogte")
KLASSE_PUTDEKSELNIVEAU = URIRef(f"{GWSW}Putdekselniveau")

KLASSE_PUNT = URIRef(f"{GWSW}Punt")
KLASSE_LIJN = URIRef(f"{GWSW}Lijn")
# Het GWSW kent drie soorten verbindingen, elk met een eigen begin- en eindvertex.
# Alle zes zijn subklassen van gwsw:Vertex.
KLASSEN_BEGINPUNT = tuple(
    URIRef(f"{GWSW}{naam}")
    for naam in ("BeginpuntLeiding", "BeginpuntOnderdeel", "BeginpuntAfvoerrelatie")
)
KLASSEN_EINDPUNT = tuple(
    URIRef(f"{GWSW}{naam}")
    for naam in ("EindpuntLeiding", "EindpuntOnderdeel", "EindpuntAfvoerrelatie")
)
KLASSE_BEGINPUNT = KLASSEN_BEGINPUNT[0]
KLASSE_EINDPUNT = KLASSEN_EINDPUNT[0]
KLASSE_BOB_BEGIN = URIRef(f"{GWSW}BobBeginpuntLeiding")
KLASSE_BOB_EIND = URIRef(f"{GWSW}BobEindpuntLeiding")


@dataclass(frozen=True)
class Inwinning:
    """De inwinningsmetagegevens die aan een kenmerk kunnen hangen."""

    wijze: str | None = None
    datum: date | None = None

    def __bool__(self) -> bool:
        """Waar zodra er iets ingevuld is."""
        return self.wijze is not None or self.datum is not None


@dataclass(frozen=True)
class Aspect:
    """Een kenmerk van een object: een waarde of een verwijzing naar een GWSW-begrip.

    Het GWSW hangt kenmerken als `gwsw:hasAspect [ rdf:type gwsw:MateriaalLeiding ;
    gwsw:hasReference gwsw:Beton ]` aan een object. Waardekenmerken gebruiken
    `hasValue`, domeinlijstkenmerken `hasReference`.
    """

    kind: str
    value: str | None = None
    reference: str | None = None
    inwinning: Inwinning | None = None

    @property
    def number(self) -> float | None:
        """De waarde als getal, of None als die er niet is of niet numeriek is."""
        if self.value is None:
            return None
        try:
            return float(self.value)
        except ValueError:
            return None

    @property
    def date(self) -> date | None:
        """De waarde als datum (ISO of jaartal), of None."""
        return _as_date(self.value)


class _MetAspecten:
    """Toegang tot de kenmerken van een object, per GWSW-klassenaam."""

    aspects: tuple[Aspect, ...]

    def aspect(self, kind: str) -> Aspect | None:
        """Het eerste kenmerk van deze soort, of None."""
        for aspect in self.aspects:
            if aspect.kind == kind:
                return aspect
        return None

    def number(self, kind: str) -> float | None:
        """De numerieke waarde van dit kenmerk, of None."""
        aspect = self.aspect(kind)
        return aspect.number if aspect is not None else None

    def reference(self, kind: str) -> str | None:
        """De domeinlijstverwijzing van dit kenmerk (korte naam), of None."""
        aspect = self.aspect(kind)
        return aspect.reference if aspect is not None else None

    def date(self, kind: str) -> date | None:
        """De datumwaarde van dit kenmerk, of None."""
        aspect = self.aspect(kind)
        return aspect.date if aspect is not None else None


@dataclass(frozen=True)
class Node(_MetAspecten):
    """Een knooppunt in het netwerk: een put, gemaal of lozingspunt."""

    uri: str
    label: str
    types: frozenset[str]
    orientation: str | None
    orientation_types: frozenset[str]
    point: Point | None
    z: float | None
    parent: str | None
    aspects: tuple[Aspect, ...] = ()
    maaiveld_aspect: Aspect | None = None
    maaiveld_inwinning: Inwinning | None = None
    deksel_aspect: Aspect | None = None
    deksel_inwinning: Inwinning | None = None
    multipart: bool = False

    @property
    def maaiveld(self) -> float | None:
        """De maaiveldhoogte bij dit knooppunt, in m NAP."""
        return self.maaiveld_aspect.number if self.maaiveld_aspect is not None else None

    @property
    def dekselniveau(self) -> float | None:
        """Het putdekselniveau, in m NAP."""
        return self.deksel_aspect.number if self.deksel_aspect is not None else None

    @property
    def bovenkant(self) -> float | None:
        """Het bovenkantniveau: het dekselniveau, of anders het maaiveld.

        Het register spreekt bij HGT-004, HGT-012 en HGT-018 over de dekselhoogte.
        Ontbreekt die, dan is de maaiveldhoogte de dichtstbijzijnde benadering; welke
        van de twee gebruikt is, hoort in de bevinding te staan.
        """
        return self.dekselniveau if self.dekselniveau is not None else self.maaiveld

    @property
    def hoogte_m(self) -> float | None:
        """De hoogte van de put in meters; het GWSW noteert die in millimeters."""
        waarde = self.number("HoogtePut")
        return waarde / 1000 if waarde is not None else None

    @property
    def bodem(self) -> float | None:
        """Het putbodemniveau, afgeleid uit bovenkant minus puthoogte.

        Het GWSW kent geen kenmerk `Putbodemniveau`; de bodem volgt uit het
        dekselniveau en `HoogtePut`. Ontbreekt een van beide, dan is de bodem
        onbekend en mag er niet op getoetst worden.
        """
        boven, hoogte = self.bovenkant, self.hoogte_m
        if boven is None or hoogte is None:
            return None
        return boven - hoogte


@dataclass(frozen=True)
class Conduit(_MetAspecten):
    """Een streng: een leiding met een begin- en eindpunt."""

    uri: str
    label: str
    types: frozenset[str]
    line: LineString | None
    start_node: str | None
    end_node: str | None
    bob_start_aspect: Aspect | None = None
    bob_end_aspect: Aspect | None = None
    aspects: tuple[Aspect, ...] = ()
    multipart: bool = False
    z_values: tuple[float | None, ...] = ()

    @property
    def z_start(self) -> float | None:
        """De z-waarde van het eerste lijnpunt, als de geometrie er een heeft."""
        return self.z_values[0] if self.z_values else None

    @property
    def z_end(self) -> float | None:
        """De z-waarde van het laatste lijnpunt, als de geometrie er een heeft."""
        return self.z_values[-1] if self.z_values else None

    @property
    def bob_start(self) -> float | None:
        """De binnenonderkant buis aan het beginpunt, in m NAP."""
        return self.bob_start_aspect.number if self.bob_start_aspect is not None else None

    @property
    def bob_end(self) -> float | None:
        """De binnenonderkant buis aan het eindpunt, in m NAP."""
        return self.bob_end_aspect.number if self.bob_end_aspect is not None else None

    @property
    def bob_verval(self) -> float | None:
        """Het verval van de bodem over de streng, in meters.

        Positief als de bodem van het administratieve beginpunt naar het eindpunt
        daalt. Ontbreekt een van beide BOB's, dan valt er niets te zeggen.
        """
        if self.bob_start is None or self.bob_end is None:
            return None
        return self.bob_start - self.bob_end

    @property
    def breedte_mm(self) -> float | None:
        """De breedte (bij een rond profiel: de diameter) in millimeters."""
        return self.number("BreedteLeiding")

    @property
    def hoogte_mm(self) -> float | None:
        """De hoogte van het profiel in millimeters."""
        return self.number("HoogteLeiding")

    @property
    def lengte_m(self) -> float | None:
        """De administratieve lengte in meters."""
        return self.number("LengteLeiding")

    @property
    def materiaal(self) -> str | None:
        """Het leidingmateriaal als korte GWSW-naam."""
        return self.reference("MateriaalLeiding")

    @property
    def vorm(self) -> str | None:
        """De profielvorm als korte GWSW-naam."""
        return self.reference("VormLeiding")

    @property
    def aanlegjaar(self) -> int | None:
        """Het jaartal uit de begindatum."""
        datum = self.date("Begindatum")
        return datum.year if datum is not None else None


@dataclass(frozen=True)
class DecodeFallback:
    """Vastlegging dat een bestand niet als UTF-8 gelezen kon worden."""

    path: Path
    encoding: str
    byte_count: int
    samples: list[str]


@dataclass(frozen=True)
class GwswDataset:
    """De ingelezen dataset met de knooppunten, strengen en de klassenhierarchie."""

    source: Path
    graph: Graph
    nodes: dict[str, Node]
    conduits: dict[str, Conduit]
    subclasses: dict[str, frozenset[str]]
    geometry_errors: dict[str, str] = field(default_factory=dict)
    decode_fallback: DecodeFallback | None = None
    ontologies: tuple[Path, ...] = ()
    structural_diff: dict[str, int] = field(default_factory=dict)

    def is_a(self, uri: str, root: str) -> bool:
        """Geeft aan of het object van het type `root` of een subklasse daarvan is."""
        object_types = self.types_of(uri)
        return bool(object_types & self.closure(root))

    def types_of(self, uri: str) -> frozenset[str]:
        """De typen van een object, inclusief die van zijn orientatie.

        Het GWSW legt de topologische rol bij de orientatie: klassen als
        Lozingspunt, Overnamepunt en UitlaatPunt zijn subklassen van Knooppunt en
        staan dus op de orientatie, niet op de put of het bouwwerk zelf. Wie op
        zulke klassen wil selecteren, moet ze hier terugvinden.
        """
        if uri in self.nodes:
            node = self.nodes[uri]
            return node.types | node.orientation_types
        if uri in self.conduits:
            return self.conduits[uri].types
        return frozenset()

    def beheerobjecttype(self, uri: str) -> str:
        """De korte naam van het beheerobjecttype van een object.

        `types_of()` voegt de typen van de orientatie bij die van het object, en
        terecht: Lozingspunt en UitlaatPunt staan volgens het GWSW op de orientatie.
        Voor een soortnaam is dat aspecttype juist het verkeerde antwoord -- een
        knoop heet Uitlaatconstructie, niet Bouwwerkorientatie. De typen van het
        object zelf gaan daarom voor; alleen als die ontbreken valt de naam terug
        op het aspect.
        """
        node = self.nodes.get(uri)
        types = node.types if node is not None and node.types else self.types_of(uri)
        namen = sorted(naam.rsplit("/", 1)[-1] for naam in types)
        return namen[0] if namen else ""

    def resolve_network_node(self, uri: str | None, roots: list[str]) -> str | None:
        """Herleidt een gekoppeld object naar het knooppunt waar het onderdeel van is.

        Een streng koppelt niet altijd aan een put: in de GWSW-praktijk wijst de
        koppeling ook naar een compartiment of een hulpstuk. Voor de netwerkanalyse
        telt de put eromheen, dus wordt via hasPart omhooggelopen tot een object van
        een van de opgegeven wortelklassen.
        """
        gezien: set[str] = set()
        huidig = uri
        while huidig is not None and huidig not in gezien:
            gezien.add(huidig)
            if any(self.is_a(huidig, root) for root in roots):
                return huidig
            node = self.nodes.get(huidig)
            huidig = node.parent if node is not None else None
        return None

    def richting_van_geometrie(
        self, conduit: Conduit, roots: list[str]
    ) -> tuple[bool, Node, Node] | None:
        """Vergelijkt de tekenrichting van de lijn met de van-naar-richting.

        Geeft (omgekeerd, beginput, eindput) terug, waarbij `omgekeerd` zegt of de
        lijn bij de administratieve eindput begint. None als er niets te vergelijken
        valt: geen geometrie, geen echte lijngeometrie, geen twee verschillende
        putten, of putten zonder punt. TOP-020 en de kaartlaag met richtingspijlen
        lezen allebei deze methode, zodat het kaartbeeld en de bevinding niet uit
        elkaar kunnen lopen.
        """
        if conduit.line is None or conduit.line.is_empty:
            return None
        if not isinstance(conduit.line, LineString):
            # Een GML-literaal in de leidinggeometrie hoeft geen lijn te zijn (zie
            # TOP-016 en `checks.meetkunde.coords_of`); zonder lijn is er geen
            # tekenrichting om te vergelijken.
            return None
        begin = self.nodes.get(self.resolve_network_node(conduit.start_node, roots) or "")
        eind = self.nodes.get(self.resolve_network_node(conduit.end_node, roots) or "")
        if begin is None or eind is None or begin.point is None or eind.point is None:
            return None
        if begin.uri == eind.uri:
            return None
        punten = list(conduit.line.coords)
        eerste, laatste = Point(punten[0][:2]), Point(punten[-1][:2])
        juist = eerste.distance(begin.point) + laatste.distance(eind.point)
        omgekeerd = eerste.distance(eind.point) + laatste.distance(begin.point)
        return omgekeerd < juist, begin, eind

    def closure(self, root: str) -> frozenset[str]:
        """De klasse zelf plus al haar subklassen, als volledige URI's."""
        return self.subclasses.get(_uri(root), frozenset({_uri(root)}))

    def of_class(self, root: str) -> list[str]:
        """De URI's van alle knooppunten en strengen van dit type."""
        gesloten = self.closure(root)
        return [uri for uri in (*self.nodes, *self.conduits) if self.types_of(uri) & gesloten]

    def subjects_of_class(self, root: str) -> list[RdfNode]:
        """Alle objecten van dit type in de graaf, ook zonder eigen geometrie.

        Onderdelen als een overstortdrempel hebben geen punt- of lijngeometrie en
        komen daarom niet in `nodes` of `conduits` voor; die zijn hier wel te vinden.
        """
        gevonden: list[RdfNode] = []
        for klasse in self.closure(root):
            gevonden.extend(self.graph.subjects(RDF.type, URIRef(klasse)))
        return gevonden

    def subset(self, uris: Iterable[str]) -> GwswDataset:
        """Dezelfde dataset met alleen deze knopen en verbindingen.

        De rdflib-graaf gaat ongewijzigd mee: hij is de bron waaruit de checks hun
        onderdelen opzoeken, en hem meesnijden zou stilzwijgend gegevens weglaten.
        Alleen `subjects_of_class()` loopt daardoor nog over de volledige export;
        dat zijn de drempels in NET-007 en RVZ, en dat staat in het rapport.
        """
        behouden = frozenset(uris)
        return replace(
            self,
            nodes={uri: node for uri, node in self.nodes.items() if uri in behouden},
            conduits={uri: kant for uri, kant in self.conduits.items() if uri in behouden},
            geometry_errors={
                uri: fout for uri, fout in self.geometry_errors.items() if uri in behouden
            },
        )


def _uri(naam: str) -> str:
    """Maakt van een korte klassenaam een volledige GWSW-URI."""
    return naam if naam.startswith("http") else f"{GWSW}{naam}"


def _short(uri: str) -> str:
    """De korte klassenaam achter de laatste scheidingstekens van een URI."""
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


ISO_DATUM = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
JAARTAL = re.compile(r"^(\d{4})$")


def _as_date(waarde: str | None) -> date | None:
    """Leest een GWSW-datumwaarde; een kaal jaartal telt als 1 januari."""
    if waarde is None:
        return None
    match = ISO_DATUM.match(waarde)
    if match is not None:
        try:
            return date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None
    jaar = JAARTAL.match(waarde.strip())
    if jaar is not None:
        try:
            return date(int(jaar[1]), 1, 1)
        except ValueError:
            return None
    return None


def _read_aspects(graph: Graph, subject: RdfNode) -> tuple[Aspect, ...]:
    """Leest de kenmerken die via hasAspect aan een object hangen.

    Aspecten zonder waarde en zonder verwijzing zijn geen kenmerken maar
    orientaties en geometrieen; die horen hier niet thuis en vallen af.
    """
    gevonden: list[Aspect] = []
    for aspect in graph.objects(subject, HAS_ASPECT):
        waarde = graph.value(aspect, HAS_VALUE)
        referentie = graph.value(aspect, HAS_REFERENCE)
        if waarde is None and referentie is None:
            continue
        inwinning = _read_inwinning(graph, aspect)
        for soort in graph.objects(aspect, RDF.type):
            gevonden.append(
                Aspect(
                    kind=_short(str(soort)),
                    value=str(waarde) if waarde is not None else None,
                    reference=_short(str(referentie)) if referentie is not None else None,
                    inwinning=inwinning,
                )
            )
    return tuple(gevonden)


def _read_inwinning(graph: Graph, subject: RdfNode) -> Inwinning | None:
    """Leest de inwinningsmetagegevens die aan een kenmerk hangen."""
    for aspect in graph.objects(subject, HAS_ASPECT):
        if (aspect, RDF.type, KLASSE_INWINNING) not in graph:
            continue
        wijze: str | None = None
        datum: date | None = None
        for deel in graph.objects(aspect, HAS_ASPECT):
            if (deel, RDF.type, KLASSE_WIJZE_VAN_INWINNING) in graph:
                referentie = graph.value(deel, HAS_REFERENCE)
                wijze = _short(str(referentie)) if referentie is not None else None
            elif (deel, RDF.type, KLASSE_DATUM_INWINNING) in graph:
                waarde = graph.value(deel, HAS_VALUE)
                datum = _as_date(str(waarde)) if waarde is not None else None
        gevonden = Inwinning(wijze=wijze, datum=datum)
        if gevonden:
            return gevonden
    return None


def _aspect_van_klasse(graph: Graph, subject: RdfNode, klasse: URIRef) -> Aspect | None:
    """Het kenmerk van deze klasse dat direct aan het object hangt."""
    for aspect in graph.objects(subject, HAS_ASPECT):
        if (aspect, RDF.type, klasse) not in graph:
            continue
        waarde = graph.value(aspect, HAS_VALUE)
        if waarde is None:
            continue
        return Aspect(
            kind=_short(str(klasse)),
            value=str(waarde),
            inwinning=_read_inwinning(graph, aspect),
        )
    return None


def _maaiveld_kenmerk(graph: Graph, orientation: RdfNode) -> tuple[Aspect | None, Inwinning | None]:
    """De maaiveldhoogte bij een knooppunt, met de herkomst ervan.

    Het GWSW hangt het maaiveld niet aan de put zelf maar aan een aparte
    maaiveldorientatie, die via hasConnection aan de putorientatie hangt.
    """
    for buur in _connections(graph, orientation):
        if (buur, RDF.type, KLASSE_MAAIVELDORIENTATIE) not in graph:
            continue
        aspect = _aspect_van_klasse(graph, buur, KLASSE_MAAIVELDHOOGTE)
        if aspect is not None:
            return aspect, _herkomst(graph, buur, aspect)
    return None, None


def _herkomst(graph: Graph, orientation: RdfNode, aspect: Aspect) -> Inwinning | None:
    """De inwinning van een kenmerk, met terugval op die van de puntgeometrie.

    De BrutIS-export van De Wolden hangt een record-brede inwinningswijze aan het
    Punt-aspect van de orientatie en herhaalt hem op het kenmerk zelf. Bij AHN2
    blijft die herhaling uit: dan staat de wijze uitsluitend op het Punt. Zonder
    deze terugval zou juist de uit het AHN afgeleide helft van de maaiveldhoogten
    als herkomstloos gelden.
    """
    if aspect.inwinning is not None:
        return aspect.inwinning
    punt = _aspect_van_klasse(graph, orientation, KLASSE_PUNT)
    return punt.inwinning if punt is not None else None


def _deksel_kenmerk(
    graph: Graph, subject: RdfNode, deksel_klassen: frozenset[str]
) -> tuple[Aspect | None, Inwinning | None]:
    """Het putdekselniveau van een put, met de herkomst ervan.

    Het niveau hangt aan de dekselorientatie van een Putdeksel-onderdeel; sommige
    exports hangen het rechtstreeks aan de put. Beide wegen worden gevolgd. De
    herkomst volgt dezelfde terugval als bij de maaiveldhoogte: staat er geen
    inwinning op het kenmerk zelf, dan telt die van de puntgeometrie ernaast.
    """
    direct = _aspect_van_klasse(graph, subject, KLASSE_PUTDEKSELNIVEAU)
    if direct is not None:
        return direct, _herkomst(graph, subject, direct)

    for deel in graph.objects(subject, HAS_PART):
        if not any((deel, RDF.type, URIRef(klasse)) in graph for klasse in deksel_klassen):
            continue
        for orientatie in graph.objects(deel, HAS_ASPECT):
            aspect = _aspect_van_klasse(graph, orientatie, KLASSE_PUTDEKSELNIVEAU)
            if aspect is not None:
                return aspect, _herkomst(graph, orientatie, aspect)
        aspect = _aspect_van_klasse(graph, deel, KLASSE_PUTDEKSELNIVEAU)
        if aspect is not None:
            return aspect, _herkomst(graph, deel, aspect)
    return None, None


def load_dataset(
    dataset_path: Path,
    ontology_paths: list[Path] | None = None,
    fallback_encoding: str = FALLBACK_ENCODING,
) -> GwswDataset:
    """Leest de OroX-dataset en de ontologie(en) en bouwt het domeinmodel op."""
    dataset_path = Path(dataset_path)
    graph, fallback = _parse(dataset_path, fallback_encoding)

    ontology = Graph()
    for pad in ontology_paths or []:
        ontology += _parse(Path(pad), fallback_encoding)[0]

    subclasses = _subclass_closure(ontology or graph)
    geometry_errors: dict[str, str] = {}
    knooppunt = _bruikbare_afsluiting(subclasses, "Knooppunt")
    verbinding = _bruikbare_afsluiting(subclasses, "Verbinding")
    nodes = _read_nodes(graph, geometry_errors, knooppunt)
    conduits = _read_conduits(graph, nodes, geometry_errors, verbinding)

    if not nodes and not conduits:
        raise DatasetError(
            f"{dataset_path}: geen knooppunten of strengen aangetroffen. Is dit een "
            f"GWSW-OroX-dataset?"
        )

    dataset = GwswDataset(
        source=dataset_path,
        graph=graph,
        nodes=nodes,
        conduits=conduits,
        subclasses=subclasses,
        geometry_errors=geometry_errors,
        decode_fallback=fallback,
        ontologies=tuple(Path(pad) for pad in ontology_paths or []),
    )
    if knooppunt or verbinding:
        dataset.structural_diff.update(_structural_diff(graph, nodes, conduits))
    return dataset


@contextmanager
def _quiet_rdflib():
    """Dempt rdflib-waarschuwingen over onjuiste literalen tijdens het parsen.

    De meegeleverde GWSW-ontologie bevat een xsd:date "20210830" zonder streepjes;
    rdflib logt daar een volledige traceback bij. Dat is geen fout in onze invoer en
    hoort niet in de CLI-uitvoer thuis.
    """
    logger = logging.getLogger("rdflib.term")
    oud = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(oud)


def _bruikbare_afsluiting(
    subclasses: dict[str, frozenset[str]], wortel: str
) -> frozenset[str] | None:
    """De subklasse-afsluiting van een wortel, of None als de ontologie ontbreekt."""
    afsluiting = subclasses.get(_uri(wortel))
    return afsluiting if afsluiting and len(afsluiting) > 1 else None


def _structural_diff(
    graph: Graph, nodes: dict[str, Node], conduits: dict[str, Conduit]
) -> dict[str, int]:
    """Vergelijkt de ontologische uitkomst met de structurele herkenning.

    Zonder ontologie herkent de lader knopen aan een puntgeometrie en verbindingen
    aan hun begin- en eindvertex. Die aanname is niet altijd waar: een knooppunt mag
    best geen geometrie hebben. Het verschil tussen beide manieren is een maat voor
    hoeveel de dataset op geometrie leunt, en hoort in het rapport te staan.
    """
    structureel_knopen = {
        str(subject)
        for orientation in _orientations_with(graph, KLASSE_PUNT)
        for subject in graph.subjects(HAS_ASPECT, orientation)
    }
    structureel_strengen = {
        str(subject)
        for orientation in _leiding_orientations(graph)
        for subject in graph.subjects(HAS_ASPECT, orientation)
    }

    verschillen: dict[str, int] = {}
    for rol, ontologisch, structureel in (
        ("knooppunten", set(nodes), structureel_knopen),
        ("strengen", set(conduits), structureel_strengen),
    ):
        zonder_geometrie = len(ontologisch - structureel)
        geen_knoop = len(structureel - ontologisch)
        if zonder_geometrie:
            verschillen[f"{rol}_zonder_geometrie"] = zonder_geometrie
        if geen_knoop:
            verschillen[f"{rol}_wel_geometrie_geen_rol"] = geen_knoop
    return verschillen


def _parse(path: Path, fallback_encoding: str) -> tuple[Graph, DecodeFallback | None]:
    """Leest een enkel TTL-bestand in, desnoods via een terugvalcodering."""
    try:
        rauw = path.read_bytes()
    except OSError as error:
        raise DatasetError(f"{path}: bestand kan niet gelezen worden ({error}).") from error

    tekst, fallback = _decode(path, rauw, fallback_encoding)

    graph = Graph()
    try:
        with _quiet_rdflib():
            graph.parse(data=tekst, format="turtle")
    except Exception as error:  # rdflib gooit uiteenlopende parsefouten
        raise DatasetError(f"{path}: geen geldige Turtle ({error}).") from error
    return graph, fallback


def _decode(path: Path, rauw: bytes, fallback_encoding: str) -> tuple[str, DecodeFallback | None]:
    """Decodeert de inhoud als UTF-8, of anders met de terugvalcodering.

    Turtle hoort UTF-8 te zijn, maar niet elke exporttool houdt zich daaraan. Wijkt
    een bestand af, dan wordt dat vastgelegd en gerapporteerd; stilzwijgend
    vervangen van tekens zou de inhoud ongemerkt veranderen.
    """
    try:
        return rauw.decode("utf-8"), None
    except UnicodeDecodeError as error:
        # De uitzondering bestaat niet meer buiten dit blok; leg de feiten nu vast.
        eerste_byte, eerste_positie = rauw[error.start], error.start

    try:
        tekst = rauw.decode(fallback_encoding)
    except (UnicodeDecodeError, LookupError) as fout:
        raise DatasetError(
            f"{path}: geen geldige UTF-8 (byte {eerste_byte:#04x} op positie "
            f"{eerste_positie}) en ook niet te lezen als {fallback_encoding} ({fout})."
        ) from fout

    afwijkend = [byte for byte in rauw if byte > 0x7F]
    return tekst, DecodeFallback(
        path=path,
        encoding=fallback_encoding,
        byte_count=len(afwijkend),
        samples=_fallback_samples(rauw, fallback_encoding),
    )


def _fallback_samples(rauw: bytes, encoding: str, limiet: int = 5) -> list[str]:
    """De regels waarin de niet-ASCII-bytes staan, ter controle door de gebruiker."""
    voorbeelden: list[str] = []
    for index, byte in enumerate(rauw):
        if byte <= 0x7F:
            continue
        start = rauw.rfind(b"\n", 0, index) + 1
        eind = rauw.find(b"\n", index)
        regel = rauw[start : eind if eind != -1 else len(rauw)]
        tekst = regel.decode(encoding, "replace").strip()
        if tekst not in voorbeelden:
            voorbeelden.append(tekst)
        if len(voorbeelden) >= limiet:
            break
    return voorbeelden


def _subclass_closure(graph: Graph) -> dict[str, frozenset[str]]:
    """Berekent per klasse de verzameling van zichzelf en al haar subklassen."""
    kinderen: dict[str, set[str]] = {}
    for kind, ouder in graph.subject_objects(RDFS.subClassOf):
        if isinstance(kind, URIRef) and isinstance(ouder, URIRef):
            kinderen.setdefault(str(ouder), set()).add(str(kind))

    afsluiting: dict[str, frozenset[str]] = {}
    # Een eigen naam voor de lus: `ouder` hierboven is een rdflib-term, hier een str.
    for klasse in kinderen:
        gezien = {klasse}
        stapel = [klasse]
        while stapel:
            huidig = stapel.pop()
            for afstammeling in kinderen.get(huidig, ()):
                if afstammeling not in gezien:
                    gezien.add(afstammeling)
                    stapel.append(afstammeling)
        afsluiting[klasse] = frozenset(gezien)
    return afsluiting


def _label(graph: Graph, subject: RdfNode) -> str:
    """Het rdfs:label van een object, of een lege tekst."""
    waarde = graph.value(subject, RDFS.label)
    return str(waarde) if waarde is not None else ""


def _types(graph: Graph, subject: RdfNode) -> frozenset[str]:
    """Alle rdf:type-waarden van een object."""
    return frozenset(str(waarde) for waarde in graph.objects(subject, RDF.type))


def _geometry(graph: Graph, orientation: RdfNode, klasse: URIRef, errors: dict[str, str]):
    """Zoekt de geometrie van een orientatie en geeft die met haar z-waarden terug."""
    for aspect in graph.objects(orientation, HAS_ASPECT):
        if (aspect, RDF.type, klasse) not in graph:
            continue
        literal = graph.value(aspect, HAS_VALUE)
        if literal is None:
            continue
        try:
            return parse_gml(str(literal)), parse_gml_z(str(literal))
        except GeometryError as error:
            errors[str(orientation)] = str(error)
            return None, []
    return None, []


def _read_nodes(
    graph: Graph,
    errors: dict[str, str],
    knooppunt_klassen: frozenset[str] | None = None,
    deksel_klassen: frozenset[str] = frozenset({_uri("Putdeksel")}),
) -> dict[str, Node]:
    """Leest de knooppunten van het netwerk.

    Het GWSW definieert een knoop als een object met een orientatie van het type
    Knooppunt. Is de ontologie beschikbaar, dan wordt die definitie gevolgd; anders
    valt de lader terug op de structurele herkenning (een orientatie met een
    puntgeometrie), zodat een dataset ook zonder ontologie leesbaar blijft.
    """
    nodes: dict[str, Node] = {}

    if knooppunt_klassen:
        bron = _orientations_of_class(graph, knooppunt_klassen)
    else:
        bron = _orientations_with(graph, KLASSE_PUNT)

    for orientation in bron:
        point, z_waarden = _geometry(graph, orientation, KLASSE_PUNT, errors)
        maaiveld, maaiveld_inwinning = _maaiveld_kenmerk(graph, orientation)
        multipart = _is_multipart(graph, orientation, KLASSE_PUNT)
        for subject in graph.subjects(HAS_ASPECT, orientation):
            uri = str(subject)
            if uri in nodes:
                continue
            deksel, deksel_inwinning = _deksel_kenmerk(graph, subject, deksel_klassen)
            nodes[uri] = Node(
                uri=uri,
                label=_label(graph, subject),
                types=_types(graph, subject),
                orientation=str(orientation),
                orientation_types=_types(graph, orientation),
                point=point,
                z=z_waarden[0] if z_waarden else None,
                parent=_parent(graph, subject),
                aspects=_read_aspects(graph, subject),
                maaiveld_aspect=maaiveld,
                maaiveld_inwinning=maaiveld_inwinning,
                deksel_aspect=deksel,
                deksel_inwinning=deksel_inwinning,
                multipart=multipart,
            )

    return nodes


def _parent(graph: Graph, subject: RdfNode) -> str | None:
    """Het object dat dit object via hasPart bevat, als dat er is."""
    for houder in graph.subjects(HAS_PART, subject):
        if isinstance(houder, URIRef) and houder != subject:
            return str(houder)
    return None


def _orientations_of_class(graph: Graph, klassen: frozenset[str]):
    """De orientaties waarvan het type in deze verzameling klassen valt."""
    gezien = set()
    for klasse in klassen:
        for orientation in graph.subjects(RDF.type, URIRef(klasse)):
            if orientation not in gezien:
                gezien.add(orientation)
                yield orientation


def _orientations_with(graph: Graph, klasse: URIRef):
    """De orientaties die via hasAspect een geometrie van dit type dragen."""
    gezien = set()
    for aspect in graph.subjects(RDF.type, klasse):
        for orientation in graph.subjects(HAS_ASPECT, aspect):
            if orientation not in gezien:
                gezien.add(orientation)
                yield orientation


def _read_conduits(
    graph: Graph,
    nodes: dict[str, Node],
    errors: dict[str, str],
    verbinding_klassen: frozenset[str] | None = None,
) -> dict[str, Conduit]:
    """Leest de verbindingen: leidingen en andere kanten van het netwerk.

    Net als bij de knopen geldt de ontologische definitie (een orientatie van het
    type Verbinding) zodra de ontologie beschikbaar is, met terugval op de
    structurele herkenning via begin- en eindvertices.
    """
    orientation_to_node = {
        node.orientation: uri for uri, node in nodes.items() if node.orientation is not None
    }
    conduits: dict[str, Conduit] = {}

    bron = (
        _orientations_of_class(graph, verbinding_klassen)
        if verbinding_klassen
        else _leiding_orientations(graph)
    )
    for orientation in bron:
        line, z_waarden = _geometry(graph, orientation, KLASSE_LIJN, errors)
        multipart = _is_multipart(graph, orientation, KLASSE_LIJN)
        begin = _endpoint(graph, orientation, KLASSEN_BEGINPUNT)
        eind = _endpoint(graph, orientation, KLASSEN_EINDPUNT)

        for subject in graph.subjects(HAS_ASPECT, orientation):
            uri = str(subject)
            if uri in conduits:
                continue
            conduits[uri] = Conduit(
                uri=uri,
                label=_label(graph, subject),
                types=_types(graph, subject),
                line=line,
                start_node=_connected_node(graph, begin, orientation_to_node),
                end_node=_connected_node(graph, eind, orientation_to_node),
                bob_start_aspect=_bob(graph, begin, KLASSE_BOB_BEGIN),
                bob_end_aspect=_bob(graph, eind, KLASSE_BOB_EIND),
                aspects=_read_aspects(graph, subject),
                multipart=multipart,
                z_values=tuple(z_waarden),
            )

    return conduits


def _is_multipart(graph: Graph, orientation: RdfNode, klasse: URIRef) -> bool:
    """Geeft aan of de geometrie van deze orientatie uit meerdere losse delen bestaat.

    Twee vormen tellen mee: een GML-literaal met een multi-geometrie erin, en meer
    dan een geometrie-aspect van dezelfde soort aan dezelfde orientatie.
    """
    literalen = [
        str(graph.value(aspect, HAS_VALUE))
        for aspect in graph.objects(orientation, HAS_ASPECT)
        if (aspect, RDF.type, klasse) in graph and graph.value(aspect, HAS_VALUE) is not None
    ]
    if len(literalen) > 1:
        return True
    return any(is_multipart_literal(literal) for literal in literalen)


def _leiding_orientations(graph: Graph):
    """De orientaties die een begin- of eindpunt van een leiding bevatten."""
    gezien = set()
    for klasse in (*KLASSEN_BEGINPUNT, *KLASSEN_EINDPUNT):
        for endpoint in graph.subjects(RDF.type, klasse):
            for orientation in graph.subjects(HAS_PART, endpoint):
                if orientation not in gezien:
                    gezien.add(orientation)
                    yield orientation


def _endpoint(graph: Graph, orientation: RdfNode, klassen: tuple[URIRef, ...]) -> RdfNode | None:
    """Het begin- of eindpunt van een verbinding, van welke soort dan ook."""
    for part in graph.objects(orientation, HAS_PART):
        if any((part, RDF.type, klasse) in graph for klasse in klassen):
            return part
    return None


def _connected_node(
    graph: Graph, endpoint: RdfNode | None, orientation_to_node: dict[str, str]
) -> str | None:
    """Herleidt de hasConnection van een strengeindpunt naar de put erachter.

    Twee dingen die uit de GWSW-documentatie volgen. De koppeling wijst naar de
    putorientatie, niet naar de put zelf; die extra stap wordt hier gezet. En
    gwsw:hasConnection is een owl:SymmetricProperty zonder inverse, dus de
    tripel mag ook andersom geschreven zijn; beide richtingen tellen.
    """
    if endpoint is None:
        return None
    for target in _connections(graph, endpoint):
        node_uri = orientation_to_node.get(str(target))
        if node_uri is not None:
            return node_uri
    return None


def _connections(graph: Graph, subject: RdfNode):
    """De hasConnection-buren van een object, in beide schrijfrichtingen."""
    yield from graph.objects(subject, HAS_CONNECTION)
    yield from graph.subjects(HAS_CONNECTION, subject)


def _bob(graph: Graph, endpoint: RdfNode | None, klasse: URIRef) -> Aspect | None:
    """Het BOB-kenmerk dat aan een strengeindpunt hangt, met zijn inwinning."""
    if endpoint is None:
        return None
    return _aspect_van_klasse(graph, endpoint, klasse)
