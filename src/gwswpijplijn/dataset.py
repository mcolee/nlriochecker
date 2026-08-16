"""Inlezen van een GWSW-OroX-dataset (TTL) tot een toetsbaar domeinmodel."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, RDFS, Graph, URIRef
from rdflib.term import Node as RdfNode
from shapely.geometry import LineString, Point

from gwswpijplijn.errors import DatasetError
from gwswpijplijn.geometry import GeometryError, parse_gml, parse_gml_z

GWSW = "http://data.gwsw.nl/1.6/totaal/"

HAS_ASPECT = URIRef(f"{GWSW}hasAspect")
HAS_PART = URIRef(f"{GWSW}hasPart")
HAS_CONNECTION = URIRef(f"{GWSW}hasConnection")
HAS_VALUE = URIRef(f"{GWSW}hasValue")

KLASSE_PUNT = URIRef(f"{GWSW}Punt")
KLASSE_LIJN = URIRef(f"{GWSW}Lijn")
KLASSE_BEGINPUNT = URIRef(f"{GWSW}BeginpuntLeiding")
KLASSE_EINDPUNT = URIRef(f"{GWSW}EindpuntLeiding")
KLASSE_BOB_BEGIN = URIRef(f"{GWSW}BobBeginpuntLeiding")
KLASSE_BOB_EIND = URIRef(f"{GWSW}BobEindpuntLeiding")


@dataclass(frozen=True)
class Node:
    """Een knooppunt in het netwerk: een put, gemaal of lozingspunt."""

    uri: str
    label: str
    types: frozenset[str]
    orientation: str | None
    point: Point | None
    z: float | None
    parent: str | None


@dataclass(frozen=True)
class Conduit:
    """Een streng: een leiding met een begin- en eindpunt."""

    uri: str
    label: str
    types: frozenset[str]
    line: LineString | None
    start_node: str | None
    end_node: str | None
    bob_start: float | None
    bob_end: float | None


@dataclass(frozen=True)
class GwswDataset:
    """De ingelezen dataset met de knooppunten, strengen en de klassenhierarchie."""

    source: Path
    graph: Graph
    nodes: dict[str, Node]
    conduits: dict[str, Conduit]
    subclasses: dict[str, frozenset[str]]
    geometry_errors: dict[str, str] = field(default_factory=dict)

    def is_a(self, uri: str, root: str) -> bool:
        """Geeft aan of het object van het type `root` of een subklasse daarvan is."""
        object_types = self.types_of(uri)
        return bool(object_types & self.closure(root))

    def types_of(self, uri: str) -> frozenset[str]:
        """De rdf:type-waarden van een object; objecten hebben er vaak meerdere."""
        if uri in self.nodes:
            return self.nodes[uri].types
        if uri in self.conduits:
            return self.conduits[uri].types
        return frozenset()

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

    def closure(self, root: str) -> frozenset[str]:
        """De klasse zelf plus al haar subklassen, als volledige URI's."""
        return self.subclasses.get(_uri(root), frozenset({_uri(root)}))

    def of_class(self, root: str) -> list[str]:
        """De URI's van alle knooppunten en strengen van dit type."""
        gesloten = self.closure(root)
        return [
            uri
            for uri, item in (*self.nodes.items(), *self.conduits.items())
            if item.types & gesloten
        ]

    def subjects_of_class(self, root: str) -> list[RdfNode]:
        """Alle objecten van dit type in de graaf, ook zonder eigen geometrie.

        Onderdelen als een overstortdrempel hebben geen punt- of lijngeometrie en
        komen daarom niet in `nodes` of `conduits` voor; die zijn hier wel te vinden.
        """
        gevonden: list[RdfNode] = []
        for klasse in self.closure(root):
            gevonden.extend(self.graph.subjects(RDF.type, URIRef(klasse)))
        return gevonden


def _uri(naam: str) -> str:
    """Maakt van een korte klassenaam een volledige GWSW-URI."""
    return naam if naam.startswith("http") else f"{GWSW}{naam}"


def load_dataset(dataset_path: Path, ontology_paths: list[Path] | None = None) -> GwswDataset:
    """Leest de OroX-dataset en de ontologie(en) en bouwt het domeinmodel op."""
    dataset_path = Path(dataset_path)
    graph = _parse(dataset_path)

    ontology = Graph()
    for pad in ontology_paths or []:
        ontology += _parse(Path(pad))

    subclasses = _subclass_closure(ontology or graph)
    geometry_errors: dict[str, str] = {}
    nodes = _read_nodes(graph, geometry_errors)
    conduits = _read_conduits(graph, nodes, geometry_errors)

    if not nodes and not conduits:
        raise DatasetError(
            f"{dataset_path}: geen knooppunten of strengen aangetroffen. Is dit een "
            f"GWSW-OroX-dataset?"
        )

    return GwswDataset(
        source=dataset_path,
        graph=graph,
        nodes=nodes,
        conduits=conduits,
        subclasses=subclasses,
        geometry_errors=geometry_errors,
    )


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


def _parse(path: Path) -> Graph:
    """Leest een enkel TTL-bestand in."""
    graph = Graph()
    try:
        with _quiet_rdflib():
            graph.parse(path, format="turtle")
    except OSError as error:
        raise DatasetError(f"{path}: bestand kan niet gelezen worden ({error}).") from error
    except Exception as error:  # rdflib gooit uiteenlopende parsefouten
        raise DatasetError(f"{path}: geen geldige Turtle ({error}).") from error
    return graph


def _subclass_closure(graph: Graph) -> dict[str, frozenset[str]]:
    """Berekent per klasse de verzameling van zichzelf en al haar subklassen."""
    kinderen: dict[str, set[str]] = {}
    for kind, ouder in graph.subject_objects(RDFS.subClassOf):
        if isinstance(kind, URIRef) and isinstance(ouder, URIRef):
            kinderen.setdefault(str(ouder), set()).add(str(kind))

    afsluiting: dict[str, frozenset[str]] = {}
    for ouder in kinderen:
        gezien = {ouder}
        stapel = [ouder]
        while stapel:
            huidig = stapel.pop()
            for kind in kinderen.get(huidig, ()):
                if kind not in gezien:
                    gezien.add(kind)
                    stapel.append(kind)
        afsluiting[ouder] = frozenset(gezien)
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


def _read_nodes(graph: Graph, errors: dict[str, str]) -> dict[str, Node]:
    """Leest alle objecten met een orientatie die een gwsw:Punt draagt."""
    nodes: dict[str, Node] = {}

    for orientation in _orientations_with(graph, KLASSE_PUNT):
        point, z_waarden = _geometry(graph, orientation, KLASSE_PUNT, errors)
        for subject in graph.subjects(HAS_ASPECT, orientation):
            uri = str(subject)
            if uri in nodes:
                continue
            nodes[uri] = Node(
                uri=uri,
                label=_label(graph, subject),
                types=_types(graph, subject),
                orientation=str(orientation),
                point=point,
                z=z_waarden[0] if z_waarden else None,
                parent=_parent(graph, subject),
            )

    return nodes


def _parent(graph: Graph, subject: RdfNode) -> str | None:
    """Het object dat dit object via hasPart bevat, als dat er is."""
    for houder in graph.subjects(HAS_PART, subject):
        if isinstance(houder, URIRef) and houder != subject:
            return str(houder)
    return None


def _orientations_with(graph: Graph, klasse: URIRef):
    """De orientaties die via hasAspect een geometrie van dit type dragen."""
    gezien = set()
    for aspect in graph.subjects(RDF.type, klasse):
        for orientation in graph.subjects(HAS_ASPECT, aspect):
            if orientation not in gezien:
                gezien.add(orientation)
                yield orientation


def _read_conduits(
    graph: Graph, nodes: dict[str, Node], errors: dict[str, str]
) -> dict[str, Conduit]:
    """Leest alle strengen met hun geometrie, koppelingen en BOB's."""
    orientation_to_node = {
        node.orientation: uri for uri, node in nodes.items() if node.orientation is not None
    }
    conduits: dict[str, Conduit] = {}

    for orientation in _leiding_orientations(graph):
        line, _ = _geometry(graph, orientation, KLASSE_LIJN, errors)
        begin = _endpoint(graph, orientation, KLASSE_BEGINPUNT)
        eind = _endpoint(graph, orientation, KLASSE_EINDPUNT)

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
                bob_start=_bob(graph, begin, KLASSE_BOB_BEGIN),
                bob_end=_bob(graph, eind, KLASSE_BOB_EIND),
            )

    return conduits


def _leiding_orientations(graph: Graph):
    """De orientaties die een begin- of eindpunt van een leiding bevatten."""
    gezien = set()
    for klasse in (KLASSE_BEGINPUNT, KLASSE_EINDPUNT):
        for endpoint in graph.subjects(RDF.type, klasse):
            for orientation in graph.subjects(HAS_PART, endpoint):
                if orientation not in gezien:
                    gezien.add(orientation)
                    yield orientation


def _endpoint(graph: Graph, orientation: RdfNode, klasse: URIRef) -> RdfNode | None:
    """Het begin- of eindpunt van een leidingorientatie."""
    for part in graph.objects(orientation, HAS_PART):
        if (part, RDF.type, klasse) in graph:
            return part
    return None


def _connected_node(
    graph: Graph, endpoint: RdfNode | None, orientation_to_node: dict[str, str]
) -> str | None:
    """Herleidt de hasConnection van een strengeindpunt naar de put erachter.

    De koppeling wijst naar de putorientatie, niet naar de put zelf; die extra
    stap wordt hier gezet.
    """
    if endpoint is None:
        return None
    for target in graph.objects(endpoint, HAS_CONNECTION):
        node_uri = orientation_to_node.get(str(target))
        if node_uri is not None:
            return node_uri
    return None


def _bob(graph: Graph, endpoint: RdfNode | None, klasse: URIRef) -> float | None:
    """De BOB-waarde die aan een strengeindpunt hangt."""
    if endpoint is None:
        return None
    for aspect in graph.objects(endpoint, HAS_ASPECT):
        if (aspect, RDF.type, klasse) in graph:
            waarde = graph.value(aspect, HAS_VALUE)
            if waarde is not None:
                try:
                    return float(waarde)
                except (TypeError, ValueError):
                    return None
    return None
