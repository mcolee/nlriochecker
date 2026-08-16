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

# Turtle moet volgens de spec UTF-8 zijn. Sommige exports (BrutIS) schrijven een
# handvol bytes in een MS-DOS-codering; cp850 is de gangbare Nederlandse variant.
FALLBACK_ENCODING = "cp850"

HAS_ASPECT = URIRef(f"{GWSW}hasAspect")
HAS_PART = URIRef(f"{GWSW}hasPart")
HAS_CONNECTION = URIRef(f"{GWSW}hasConnection")
HAS_VALUE = URIRef(f"{GWSW}hasValue")

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
class Node:
    """Een knooppunt in het netwerk: een put, gemaal of lozingspunt."""

    uri: str
    label: str
    types: frozenset[str]
    orientation: str | None
    orientation_types: frozenset[str]
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


def _uri(naam: str) -> str:
    """Maakt van een korte klassenaam een volledige GWSW-URI."""
    return naam if naam.startswith("http") else f"{GWSW}{naam}"


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


def _read_nodes(
    graph: Graph, errors: dict[str, str], knooppunt_klassen: frozenset[str] | None = None
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
        for subject in graph.subjects(HAS_ASPECT, orientation):
            uri = str(subject)
            if uri in nodes:
                continue
            nodes[uri] = Node(
                uri=uri,
                label=_label(graph, subject),
                types=_types(graph, subject),
                orientation=str(orientation),
                orientation_types=_types(graph, orientation),
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
        line, _ = _geometry(graph, orientation, KLASSE_LIJN, errors)
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
                bob_start=_bob(graph, begin, KLASSE_BOB_BEGIN),
                bob_end=_bob(graph, eind, KLASSE_BOB_EIND),
            )

    return conduits


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
