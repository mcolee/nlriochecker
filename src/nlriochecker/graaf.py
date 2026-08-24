"""Eigen graafindexen als vervanger van de rdflib-store (`GwswDataset.graph`).

De rdflib-`Memory`-store bouwt drie geneste indexen (spo, pos, osp) met per triple
dict-in-dict-in-dict-overhead; op de De Wolden en Hoogeveen-export kostte dat minuten
opbouwtijd en gigabytes geheugen. De checks gebruiken maar een handvol leesbewerkingen,
allemaal met gebonden argumenten. `GraafIndex` draagt daarom precies twee indexen
(s->p->[o] en p->o->[s]), gevuld in stream-volgorde uit de pyoxigraph-parse, met
rdflib-termtypen (`URIRef`, `BNode`, `Literal`) als munteenheid zodat de aanroepende
code en alle vergelijkingen ongewijzigd blijven.

Geinventariseerde `Graph`-bewerkingen (stap 0; `grep -rn "\\.graph\\." src/` plus de
interne lezers in `dataset.py`) -- dit is het volledige leescontract, en de tests in
`tests/test_graaf.py` toetsen elk ervan tegen het rdflib-antwoord op dezelfde triples,
inclusief volgorde:

- ``objects(subject, predicate)`` -- beide gebonden. `dataset.py` (`graph_types_of`,
  `parts_of`/`aspects_of`/`part_holders_of`/`aspect_holders_of`, `_read_aspects`,
  `_types`, `_connections`), `checks/administratief.py` (hasConnection),
  `nulbevinding.py` (`_ouders`), `uitvoer/stelsels.py` (`_label`) en
  `ontologie.verwachte_property` (de restrictiebron kan deze index zijn).
- ``subjects(predicate, object)`` -- beide gebonden. `dataset.py`
  (`subjects_of_class`, de vier hasPart/hasAspect-lezers, `_orientations_of_class`,
  `_orientations_with`, `_leiding_orientations`, `_connections`, `_subclass_closure`
  niet -- die gebruikt `subject_objects`), `checks/administratief.py`,
  `checks/attributen.py` (`_property_tellingen`), `nulbevinding.py`.
- ``value(subject, predicate)`` -- het eerste object of None. `dataset.py`
  (`onderdeel_label`, `_read_aspects`, `_read_inwinning`, `_aspect_van_klasse`,
  `_label`, `_geometry`, `_is_multipart`), `checks/attributen.py`,
  `ontologie.verwachte_property`.
- ``subject_objects(predicate)`` -- alleen het predicaat gebonden;
  `dataset._subclass_closure`. rdflib loopt hier de pos-index af (eerst per object,
  dan per subject), niet de triple-volgorde; de index spiegelt die groepering.
- ``(s, p, o) in graaf`` -- volledig gebonden membership. `dataset.py`
  (`_read_inwinning`, `_aspect_van_klasse`, `_maaiveld_kenmerk`, `_deksel_kenmerk`,
  `_geometry`, `_is_multipart`, `_endpoint`).
- ``len(graaf)`` -- het aantal triples. `load_dataset` (restrictiebron-keuze),
  `cache.py` (logregel) en de cachetests.

Niet gebruikt en dus niet aangeboden: `triples()`, patronen met andere ongebonden
argumenten, iteratie over de hele graaf, en elke schrijfbewerking na het vullen.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import pyoxigraph
from rdflib import BNode, Literal, URIRef
from rdflib.term import Node as RdfNode

XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"


def naar_rdflib(
    term: pyoxigraph.NamedNode | pyoxigraph.BlankNode | pyoxigraph.Literal,
) -> RdfNode:
    """Zet een pyoxigraph-term om naar de bijbehorende rdflib-term.

    Een gewone (ongetypeerde) string-literaal wordt `Literal(waarde)` met datatype `None`,
    net als rdflib's eigen Turtle-parser. Een expliciet getypeerde `"x"^^xsd:string` is
    niet te onderscheiden en dus niet exact te reconstrueren: pyoxigraph vouwt die (RDF 1.1)
    al samen met de gewone vorm tot dezelfde term, terwijl rdflib's parser hem als een aparte
    term zou bewaren. De byte-voor-byte-gelijkheid van de uitvoer steunt er daarom op dat de
    ingelezen bestanden geen expliciet `^^xsd:string` dragen (nagegaan voor de totaal-ontologie
    en de OroX-export), niet op een algemene reconstructiegarantie.

    Andere termsoorten (RDF-ster-triples, benoemde grafen) horen niet in een Turtle-parse en
    vallen luid om op een `AttributeError` in plaats van stilzwijgend verkeerd om te zetten.
    """
    if isinstance(term, pyoxigraph.NamedNode):
        return URIRef(term.value)
    if isinstance(term, pyoxigraph.BlankNode):
        return BNode(term.value)
    if term.language is not None:
        return Literal(term.value, lang=term.language)
    datatype = term.datatype.value
    if datatype == XSD_STRING:
        return Literal(term.value)
    return Literal(term.value, datatype=URIRef(datatype))


class GraafIndex:
    """Twee dicts met het volledige leescontract van de checks (zie de moduledocstring).

    De volgordegarantie is die van rdflib's `Memory`-store: binnen `objects(s, p)` en
    `subjects(p, o)` de eerste-toevoegvolgorde van de triples, en in
    `subject_objects(p)` de pos-groepering (objecten in eerste-toevoegvolgorde onder
    het predicaat, daarbinnen de subjecten). Duplicaten tellen een keer, net als in
    een rdflib-graaf.
    """

    def __init__(self) -> None:
        self._spo: dict[RdfNode, dict[RdfNode, list[RdfNode]]] = {}
        self._pos: dict[RdfNode, dict[RdfNode, list[RdfNode]]] = {}
        self._aantal = 0

    def voeg_toe(self, subject: RdfNode, predicate: RdfNode, object_: RdfNode) -> None:
        """Voegt een triple toe; een duplicaat verandert niets, ook de volgorde niet."""
        per_predicaat = self._spo.setdefault(subject, {})
        objecten = per_predicaat.setdefault(predicate, [])
        if object_ in objecten:
            return
        objecten.append(object_)
        self._pos.setdefault(predicate, {}).setdefault(object_, []).append(subject)
        self._aantal += 1

    def vul_uit(self, quads: Iterable[pyoxigraph.Quad]) -> None:
        """Vult de index in stream-volgorde uit een pyoxigraph-parse.

        Gelijke termen worden geinterneerd: elke unieke URI, blanke knoop of literaal
        bestaat een keer als rdflib-object en wordt in alle triples gedeeld. Dat
        scheelt op de De Wolden en Hoogeveen-export honderden megabytes -- elke triple
        draagt drie verwijzingen in plaats van drie verse objecten.
        """
        termen: dict[object, RdfNode] = {}

        def term(ruw: object) -> RdfNode:
            klaar = termen.get(ruw)
            if klaar is None:
                klaar = naar_rdflib(ruw)  # type: ignore[arg-type]
                termen[ruw] = klaar
            return klaar

        for quad in quads:
            self.voeg_toe(term(quad.subject), term(quad.predicate), term(quad.object))

    def objects(self, subject: RdfNode, predicate: RdfNode) -> Iterator[RdfNode]:
        """De objecten van (subject, predicate), in eerste-toevoegvolgorde."""
        return iter(self._spo.get(subject, _LEEG).get(predicate, ()))

    def subjects(self, predicate: RdfNode, object_: RdfNode) -> Iterator[RdfNode]:
        """De subjecten van (predicate, object), in eerste-toevoegvolgorde."""
        return iter(self._pos.get(predicate, _LEEG).get(object_, ()))

    def value(self, subject: RdfNode, predicate: RdfNode) -> RdfNode | None:
        """Het eerste object van (subject, predicate), of None."""
        objecten = self._spo.get(subject, _LEEG).get(predicate)
        return objecten[0] if objecten else None

    def subject_objects(self, predicate: RdfNode) -> Iterator[tuple[RdfNode, RdfNode]]:
        """Alle (subject, object)-paren van dit predicaat, in pos-groepering."""
        for object_, subjecten in self._pos.get(predicate, _LEEG).items():
            for subject in subjecten:
                yield subject, object_

    def heeft_subject(self, term: RdfNode) -> bool:
        """Of deze term als subject in de graaf voorkomt."""
        return term in self._spo

    def __contains__(self, triple: tuple[RdfNode, RdfNode, RdfNode]) -> bool:
        """Membership van een volledig gebonden triple; de lijstscan is kort --
        het aantal objecten per (subject, predicaat) is in de praktijk enkele."""
        subject, predicate, object_ = triple
        return object_ in self._spo.get(subject, _LEEG).get(predicate, ())

    def __len__(self) -> int:
        """Het aantal triples, zonder duplicaten."""
        return self._aantal


# Een gedeelde lege dict als terugval, zodat een misser geen nieuwe dict aanmaakt.
_LEEG: dict[RdfNode, list[RdfNode]] = {}
