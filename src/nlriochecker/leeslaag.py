"""De naad tussen de checks en de graaflaag van `gwsw-orox-helpers`.

Dit is de enige module in `src/` die de graafvragen van de leeslaag stelt: `of_class`,
`subjects_of_class`, `onderdelen`, `graph_is_a` (rechtstreeks), de `hasPart`/`hasAspect`-
houders en de kenmerkinstanties (gedelegeerd naar `GwswDataset.houders`/`dragers`/
`kenmerkinstanties` sinds v0.2.4, issue #166), en de `hasConnection`-buren en de
overige kenmerkvragen die nog rechtstreeks op `dataset.graph` en rdflib leunen. Elders in
`src/` staat achter elke bewerking een van de domeinvragen hieronder; `tests/
test_architectuur_laagsnit.py` (hek a4) bewaakt dat geen andere module nog rdflib
importeert of `dataset.graph` aanraakt.

De winst: een check-schrijver leert acht domeinvragen in plaats van achttien
leeslaagnamen plus rdflib, en de versie-juiste predicaatkeuze (`hasConnection`,
`hasValue`, `hasReference` via `gwsw_versie.basis` -- issue #139) staat op één plek in
plaats van als privé-helper in elke module. Een toekomstige leeslaagrelease
(gwsw-orox-helpers #74) raakt daarmee alleen dit bestand.

De module leunt uitsluitend op de publieke API van `gwsw-orox-helpers`
(`gwsw_orox_helpers.dataset`, `.namen`) en op rdflib; hij importeert niets uit
`nlriochecker` en ligt daarmee onder `afbakening` in de laagvolgorde.
"""

from __future__ import annotations

from gwsw_orox_helpers.dataset import GwswDataset
from gwsw_orox_helpers.namen import termen_voor
from rdflib import BNode, URIRef
from rdflib.term import Node as RdfNode


def knopen_van(dataset: GwswDataset, wortel: str) -> list[str]:
    """De knopen (en strengen) van een klasse, via de gesloten klassenhierarchie.

    `of_class` levert de URI's van alle knopen én strengen van dit type; een
    knoop-rol kiest deze vraag, een leiding-rol `strengen_van`. Beide leveren
    dezelfde verzameling -- de beller filtert zelf op `dataset.nodes`/`.conduits`
    waar hij maar één soort verwacht.
    """
    return dataset.of_class(wortel)


def strengen_van(dataset: GwswDataset, wortel: str) -> list[str]:
    """De strengen (en knopen) van een klasse; de leiding-tegenhanger van `knopen_van`.

    Zie `knopen_van`: `of_class` maakt geen onderscheid, dus deze vraag is er voor de
    leesbaarheid van een leiding-rol. De beller houdt zijn eigen `uri in
    dataset.conduits`-filter.
    """
    return dataset.of_class(wortel)


def subject_uris_van(dataset: GwswDataset, wortel: str) -> list[str]:
    """De URI's van alle objecten van een klasse in de graaf, ook zonder eigen geometrie.

    `subjects_of_class` levert de rauwe graaftermen (ook een overstortdrempel zonder
    punt- of lijngeometrie); deze vraag geeft ze als tekst, in dezelfde graafvolgorde.
    """
    return [str(subject) for subject in dataset.subjects_of_class(wortel)]


def is_van_klasse(dataset: GwswDataset, uri: str, wortel: str) -> bool:
    """Of dit object -- ook een onderdeel dat alleen in de graaf staat -- van deze klasse is."""
    return dataset.graph_is_a(uri, wortel)


def onderdelen_van(dataset: GwswDataset, uri: str, wortel: str | None = None) -> list[str]:
    """De directe `hasPart`-onderdelen van een object, optioneel beperkt tot een klasse."""
    return dataset.onderdelen(uri, wortel)


def houders(dataset: GwswDataset, uri: str, *, aspecten: bool = False) -> list[str]:
    """De objecten die dit object via `hasPart` (en optioneel `hasAspect`) bevatten.

    Delegeert naar `GwswDataset.houders`/`dragers` (v0.2.4): dezelfde lezing van de
    `hasPart`-houders in beide schrijfrichtingen, en met `aspecten=True` daarachter de
    `hasAspect`-houders, in dezelfde graafvolgorde. De BNode-terugval waar dit lichaam
    vroeger `_term` voor riep, zit nu in de leeslaag zelf (`_subject_term`, gelijk aan
    het `_term` hieronder), dus de uitkomst blijft byte-gelijk (issue #166).
    """
    gevonden = dataset.houders(uri)
    if aspecten:
        gevonden += dataset.dragers(uri)
    return gevonden


def buren(dataset: GwswDataset, uri: str) -> set[str]:
    """De objecten die via `hasConnection` met dit object verbonden zijn, beide richtingen.

    `hasConnection` is een `owl:SymmetricProperty` zonder inverse, dus welk object
    subject is, is een keuze van de exporteur; daarom worden beide schrijfrichtingen
    gelezen. Het predicaat komt versie-juist uit `gwsw_versie.basis`, zodat een
    1.7-export niet stil nul buren geeft (issue #139).
    """
    term = _term(dataset, uri)
    graaf = dataset.graph
    has_connection = URIRef(termen_voor(dataset.gwsw_versie.basis).has_connection)
    verbonden = {str(ander) for ander in graaf.subjects(has_connection, term)}
    verbonden |= {str(ander) for ander in graaf.objects(term, has_connection)}
    return verbonden


def kenmerkinstanties(dataset: GwswDataset, kenmerk: str) -> list[str]:
    """De URI's van de instanties van een kenmerktype (`rdf:type` gelijk aan `basis+kenmerk`).

    Delegeert naar `GwswDataset.kenmerkinstanties` (v0.2.4) en houdt alleen de URI aan:
    die methode geeft per instantie ook de `hasValue`/`hasReference`, die ATTR-014 langs
    deze weg niet nodig heeft. Versie-juist via de gedetecteerde basis, dus op een
    1.7-export geen stille nul (issue #139); de instantieset en -volgorde blijven gelijk
    (issue #166).
    """
    return [uri for uri, _waarde, _referentie in dataset.kenmerkinstanties(kenmerk)]


def subjecten_met_waardeproperty(dataset: GwswDataset) -> tuple[set[str], set[str]]:
    """De subjecten met een `hasValue`- respectievelijk `hasReference`-property.

    Twee indexsweeps over alle triples met die predicaten (issue #124), niet twee
    `value`-aanroepen per instantie. De predicaten komen versie-juist uit
    `gwsw_versie.basis`. Levert `(met_waarde, met_referentie)` als URI-verzamelingen.
    """
    termen = termen_voor(dataset.gwsw_versie.basis)
    graaf = dataset.graph
    met_waarde = {str(subject) for subject, _ in graaf.subject_objects(URIRef(termen.has_value))}
    met_referentie = {
        str(subject) for subject, _ in graaf.subject_objects(URIRef(termen.has_reference))
    }
    return met_waarde, met_referentie


def vulwaarde(dataset: GwswDataset, uri: str) -> str | None:
    """De eerste `hasValue`-waarde van dit object als tekst, of None als die er niet is.

    Het versie-juiste `hasValue`-predicaat uit `gwsw_versie.basis`; ATTR-014 leest de
    waarde alleen voor de foute instanties om te zien of het de vulwaarde 0 is.
    """
    termen = termen_voor(dataset.gwsw_versie.basis)
    waarde = dataset.graph.value(_term(dataset, uri), URIRef(termen.has_value))
    return None if waarde is None else str(waarde)


def _term(dataset: GwswDataset, uri: str) -> RdfNode:
    """De graafterm achter deze URI-tekst: de URIRef, of anders de gelijknamige BNode.

    Dezelfde afweging als de leeslaag zelf maakt voor haar `onderdeel_*`-lezers: een
    BNode-subject verliest zijn triples achter een kale `URIRef(uri)`. De URIRef wint
    als die als subject voorkomt; anders telt de gelijknamige BNode; is geen van beide
    een subject, dan blijft de URIRef -- hetzelfde lege antwoord als een kale omweg.
    """
    term: RdfNode = URIRef(uri)
    if dataset.graph.heeft_subject(term):
        return term
    bnode = BNode(uri)
    if dataset.graph.heeft_subject(bnode):
        return bnode
    return term
