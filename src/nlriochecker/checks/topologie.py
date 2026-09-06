"""TOP-checks: topologie en geometrie van putten en strengen."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import cast

import numpy as np
import shapely
from gwsw_orox_helpers.dataset import Conduit, Node
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.hulpstukken import _hulpstuktelling, zuiver_mechanische_knopen
from nlriochecker.checks.meetkunde import (
    coords_van,
    duplicate_vertices_kern,
    endpoints_kern,
    half_diameter_m,
    is_finite,
    max_offset_from_chord_kern,
    unieke_coords_van,
    vertex_angles_kern,
)
from nlriochecker.checks.selectie import (
    functieloze_knopen,
    leidingen,
    nabijheidsleidingen,
    netwerkknopen,
    vrijvervalrioolleidingen,
)
from nlriochecker.checks.verbanden import verbonden_knopen
from nlriochecker.taal import getal, vorm


def _punt(node: Node) -> Point:
    """Het punt van een knoop uit de topologie-index.

    De index bevat alleen knopen met een punt -- `_bouw_topologie` filtert daarop
    voordat de STRtree gebouwd wordt -- maar aan het type `Node` is dat niet te zien.
    Deze functie legt die belofte op een plek vast in plaats van op elke gebruikssite.
    """
    return cast(Point, node.point)


def _lijn(conduit: Conduit) -> LineString:
    """De hartlijn van een streng uit `_Topologie.lined`.

    Dezelfde belofte als `_punt`: `lined` bevat alleen strengen waarvan de uiteinden
    te bepalen waren, dus met een geometrie. Dat filter laat
    strikt genomen ook een andere lijnvormige geometrie dan `LineString` door (zie
    `coords_of` in `checks/meetkunde.py`); de cast is een runtime-noop en de gebruikte
    bewerkingen -- afstand, kruising, snijpunt -- gelden voor elke shapely-geometrie.
    """
    return cast(LineString, conduit.line)


def _eindige_eindpunten(punten: tuple[tuple[float, ...], ...]) -> tuple[Point, Point] | None:
    """De uiteinden van een coordinatenreeks, of None als die er niet eindig zijn.

    Een niet-eindige coordinaat (NaN of oneindig) wordt hier als "geen uiteinden"
    behandeld, net als een reeks van minder dan twee punten. Shapely's STRtree en de
    afstands- en snijfuncties vallen op zo'n coordinaat om met een GEOSException (en
    `round()` op een oneindige lengte met een OverflowError); door de streng hier over
    te slaan blijven de snapping- en nabijheidsindexen bruikbaar, terwijl TOP-007 en
    TOP-009 de geometrie langs hun eigen weg melden. Zie issue #152.
    """
    if not all(math.isfinite(waarde) for punt in punten for waarde in punt):
        return None
    return endpoints_kern(punten)


@dataclass(frozen=True)
class _Topologie:
    """Hulpstructuur met de putten, hun geometrie en een index erop."""

    nodes: list[Node]
    tree: STRtree | None
    conduits: list[Conduit]
    all_conduits: list[Conduit]
    lined: list[Conduit] = field(default_factory=list)
    line_tree: STRtree | None = None
    # Per streng-URI de uiteinden, een keer bepaald bij het bouwen; voorheen
    # rekende elke check ze opnieuw uit, met verse Point-objecten per aanroep.
    eindpunten: dict[str, tuple[Point, Point] | None] = field(default_factory=dict)
    # Hoeveel knopen als `c<n>`-duplicaat zijn samengevoegd en dus niet in `nodes`
    # staan; `_dedupnotitie` verantwoordt ze. Zie `_dedupliceer` en BO-71.
    samengevoegd: int = 0

    def endpoints_of(self, context: CheckContext, conduit: Conduit) -> tuple[Point, Point] | None:
        """Het begin- en eindpunt van de strenggeometrie, uit de gedeelde tabel.

        Vult de tabel bij een onbekende streng alsnog: de vrijvervalselectie is in
        de praktijk een deelverzameling van alle leidingen, maar dat is aan de
        configuratie niet af te dwingen, en een ontbrekende streng als "geen
        uiteinden" lezen zou een stille gedragswijziging zijn. Het bijvullen loopt
        over de coordinatentabel van de context, zodat de streng ook daar bekend
        wordt (issue #123).
        """
        if conduit.uri not in self.eindpunten:
            self.eindpunten[conduit.uri] = _eindige_eindpunten(
                coords_van(context, conduit.uri, conduit.line)
            )
        return self.eindpunten[conduit.uri]

    def nearest_node(self, punt: Point, tolerantie: float) -> Node | None:
        """De put binnen de tolerantie die het dichtst bij dit punt ligt.

        Een niet-eindig zoekpunt levert None: `STRtree.query` valt er met een
        GEOSException op om (issue #152). De snapping voedt hier al alleen eindige
        uiteinden in (`endpoints_of`), maar de poort staat er ook direct op.
        """
        if self.tree is None or not (math.isfinite(punt.x) and math.isfinite(punt.y)):
            return None
        kandidaten = self.tree.query(punt, predicate="dwithin", distance=tolerantie)
        dichtstbij: Node | None = None
        kleinste = float("inf")
        for index in kandidaten:
            node = self.nodes[int(index)]
            afstand = _punt(node).distance(punt)
            if afstand <= tolerantie and afstand < kleinste:
                kleinste = afstand
                dichtstbij = node
        return dichtstbij


def _topologie(context: CheckContext) -> _Topologie:
    """Bouwt de puttenindex en de strengenlijst, of geeft de eerder gebouwde terug."""
    return context.cached("topologie", lambda: _bouw_topologie(context))


def _bouw_topologie(context: CheckContext) -> _Topologie:
    """Bouwt de puttenindex en de lijst met strengen die geometrie hebben."""
    # De selectie ontdubbelt al, dus hier blijft alleen het filter over dat bij deze
    # structuur hoort en niet bij de rol: een knoop zonder punt kan niet in de index.
    knopen = [node for node in netwerkknopen(context) if node.point is not None]
    knopen, samengevoegd = _dedupliceer(knopen, context.config.drempels.dubbele_put_tolerantie_m)
    tree = STRtree([node.point for node in knopen]) if knopen else None

    alle = leidingen(context)
    eindpunten = {
        conduit.uri: _eindige_eindpunten(coords_van(context, conduit.uri, conduit.line))
        for conduit in alle
    }
    met_lijn = [conduit for conduit in alle if eindpunten[conduit.uri] is not None]

    return _Topologie(
        nodes=knopen,
        tree=tree,
        conduits=vrijvervalrioolleidingen(context),
        all_conduits=alle,
        lined=met_lijn,
        line_tree=STRtree([conduit.line for conduit in met_lijn]) if met_lijn else None,
        eindpunten=eindpunten,
        samengevoegd=samengevoegd,
    )


# Het achtervoegsel waarmee de Kikker-export een gecompartimenteerde put per deel
# uitschrijft: het putlabel, met spaties uitgevuld, plus `c1`, `c2`, ... De export van De
# Wolden en Hoogeveen draagt 189 zulke labels in 98 groepen (c1 96x, c2 92x, c3 1x); de
# spatie ervoor staat er altijd, maar hij is hier optioneel omdat de uitvulling een
# opmaakkeuze van de leverancier is en niet het patroon zelf.
_COMPARTIMENT_POSTFIX = re.compile(r"^(?P<basis>.*\S)\s*c(?P<nummer>\d+)$")


def _basislabel(label: str) -> tuple[str, int] | None:
    """De putnaam en het compartimentnummer achter een `c<n>`-label, of None."""
    treffer = _COMPARTIMENT_POSTFIX.match(label.strip())
    if treffer is None:
        return None
    return treffer["basis"].strip(), int(treffer["nummer"])


def _dedupliceer(knopen: list[Node], tolerantie: float) -> tuple[list[Node], int]:
    """Voegt de compartimentduplicaten van dezelfde put samen; het origineel wint.

    Twee knopen zijn hetzelfde fysieke object wanneer hun labels op een `c<n>`-postfix
    na gelijk zijn **en** hun punten binnen de dubbele-put-tolerantie samenvallen. Beide
    eisen tellen: alleen op de naam matchen zou twee echte putten samenvoegen die
    toevallig zo heten, en alleen op de ligging matchen is precies wat TOP-005 al meldt.
    Zie BO-71 en issue #85.

    Het origineel wint: de knoop wiens label géén postfix draagt, en is die er niet --
    in de export van De Wolden en Hoogeveen 95 van de 98 groepen -- de laagste
    postfix. Een knoop zonder postfix wordt nooit weggenomen; twee gelijknamige putten
    zonder postfix blijven dus gewoon een dubbele put.
    """
    per_basis: defaultdict[str, list[tuple[int, Node]]] = defaultdict(list)
    zonder_postfix: defaultdict[str, list[Node]] = defaultdict(list)
    for node in knopen:
        label = (node.label or "").strip()
        gevonden = _basislabel(label)
        if gevonden is None:
            zonder_postfix[label].append(node)
        else:
            per_basis[gevonden[0]].append((gevonden[1], node))

    duplicaten: set[str] = set()
    for basis, leden in per_basis.items():
        genummerd = sorted(leden, key=lambda paar: (paar[0], paar[1].uri))
        originelen = sorted(zonder_postfix.get(basis, []), key=lambda node: node.uri)
        winnaar = originelen[0] if originelen else genummerd[0][1]
        for _, node in genummerd:
            if node.uri != winnaar.uri and _punt(node).distance(_punt(winnaar)) <= tolerantie:
                duplicaten.add(node.uri)

    if not duplicaten:
        return knopen, 0
    return [node for node in knopen if node.uri not in duplicaten], len(duplicaten)


def _dedupnotitie(context: CheckContext) -> list[str]:
    """Verantwoordt de knopen die als compartimentduplicaat zijn samengevoegd.

    Zegt precies wat de samenvoeging doet en wat zij niet doet. Zij haalt de knoop uit
    de populatie -- ze rekent niets van het duplicaat bij het origineel op, dus wat
    alleen op het duplicaat staat wordt hier niet meer beoordeeld -- en het strengeinde
    dat erop uitkwam snapt alleen op het origineel als dat binnen de snapping-tolerantie
    ligt. Die tweede zin is er niet voor de sier: `dubbele_put_tolerantie_m` is ruimer
    dan `snapping_tolerantie_m`, dus tussen die twee maten in kan een strengeinde zijn
    aansluiting verliezen. Zie BO-71.
    """
    aantal = _topologie(context).samengevoegd
    if not aantal:
        return []
    drempels = context.config.drempels
    return [
        f"{getal(aantal, 'knoop', 'knopen')} {vorm(aantal, 'is', 'zijn')} vóór deze toets "
        "samengevoegd met een gelijknamige knoop: de labels verschillen alleen in een "
        "`c<n>`-postfix -- waarmee de bronexport een gecompartimenteerde put per deel "
        f"uitschrijft -- en de punten liggen binnen {drempels.dubbele_put_tolerantie_m:g} m "
        "van elkaar (`[drempels] dubbele_put_tolerantie_m`). Zij tellen hier niet als eigen "
        "knoop, en wat alleen op zo'n duplicaat staat is hier dus niet getoetst. Een "
        "strengeinde dat erop uitkwam snapt op de knoop die overbleef zolang die binnen "
        f"{drempels.snapping_tolerantie_m:g} m ligt "
        "(`[drempels] snapping_tolerantie_m`); ligt het duplicaat verder van het origineel "
        "dan die maat, dan geldt dat eind hier als niet-aangesloten. Zie BO-71."
    ]


def _snapping(context: CheckContext) -> dict[str, tuple[Node | None, ...]]:
    """Per streng-URI de put waarop elk uiteinde snapt; een keer per context.

    TOP-001, TOP-002, TOP-003 en TOP-021 zoeken alle vier per strengeinde de
    dichtstbijzijnde put binnen de snapping-tolerantie. Die afbeelding staat hier
    een keer, zodat de vier dezelfde uitkomst delen in plaats van elk hun eigen
    boomrondgang te doen.
    """
    return context.cached("topologie:snapping", lambda: _bouw_snapping(context))


def _bouw_snapping(context: CheckContext) -> dict[str, tuple[Node | None, ...]]:
    """Snapt elk strengeinde op de dichtstbijzijnde put binnen de tolerantie."""
    topologie = _topologie(context)
    tolerantie = context.config.drempels.snapping_tolerantie_m

    # Over alle leidingen plus de vrijvervalselectie, ontdubbeld op URI: de tweede
    # is in de praktijk een deelverzameling van de eerste, maar de configuratie
    # dwingt dat niet af en een streng zonder ingang zou hier stil wegvallen.
    strengen = {conduit.uri: conduit for conduit in topologie.all_conduits}
    strengen.update((conduit.uri, conduit) for conduit in topologie.conduits)

    snapping: dict[str, tuple[Node | None, ...]] = {}
    for uri, conduit in strengen.items():
        uiteinden = topologie.endpoints_of(context, conduit)
        if uiteinden is None:
            continue
        snapping[uri] = tuple(topologie.nearest_node(punt, tolerantie) for punt in uiteinden)
    return snapping


@dataclass(frozen=True)
class _Eindhulpstukken:
    """De hulpstukken die als geldig strengeinde tellen, met een index erop.

    Een `Hulpstuk` is in het GWSW geen `Put` en dus geen netwerkknoop, dus een streng
    die op een T-stuk eindigt heeft geometrisch geen put aan die zijde. TOP-002 en
    TOP-003 lazen dat als een gebrek; op De Wolden en Hoogeveen ging het bij 45 van de
    56 respectievelijk 107 van de 109 meldingen om precies dat. Zie BO-72 en issue #89.
    """

    nodes: list[Node]
    tree: STRtree | None

    def raakt(self, punt: Point, tolerantie: float) -> bool:
        """Of een van deze hulpstukken binnen de tolerantie van dit punt ligt."""
        if self.tree is None:
            return False
        for index in self.tree.query(punt, predicate="dwithin", distance=tolerantie):
            if _punt(self.nodes[int(index)]).distance(punt) <= tolerantie:
                return True
        return False


def _eindhulpstukken(context: CheckContext) -> _Eindhulpstukken:
    """De index met de hulpstukken die als eind tellen; een keer per context."""
    return context.cached("topologie:eindhulpstukken", lambda: _bouw_eindhulpstukken(context))


def _bouw_eindhulpstukken(context: CheckContext) -> _Eindhulpstukken:
    """Indexeert de hulpstukken met een telbare GWSW-functie en een puntgeometrie.

    Precies de populatie die TOP-022 en TOP-023 toetsen (`_hulpstuktelling().telbaar`),
    en met opzet dezelfde lijst: "telbare functie" is de grens die daar al ligt, en een
    tweede klassenlijst zou stil van die grens weglopen. Een hulpstuk waarvan de klasse
    wel een functie draagt maar geen aantal (`Afsluitstuk`, `Ontstoppingsstuk`) telt dus
    niet als eind.
    """
    knopen = [
        aansluiting.node
        for aansluiting in _hulpstuktelling(context).telbaar
        if aansluiting.node.point is not None
    ]
    return _Eindhulpstukken(knopen, STRtree([node.point for node in knopen]) if knopen else None)


def _midden(links: Point, rechts: Point) -> tuple[float, float]:
    """Het punt precies tussen twee punten in."""
    return ((links.x + rechts.x) / 2, (links.y + rechts.y) / 2)


def _dichtste_midden(links: BaseGeometry, rechts: BaseGeometry) -> tuple[float, float] | None:
    """Het midden van het stuk waar twee geometrieen elkaar het dichtst naderen.

    Bij overlappende of rakende strengen zit het probleem daar, niet in het midden
    van een van beide strengen.
    """
    try:
        eerste, tweede = nearest_points(links, rechts)
    except (ValueError, AttributeError):
        return None
    return _midden(eerste, tweede)


def _representatief(geometrie: BaseGeometry | None) -> tuple[float, float] | None:
    """Een punt op een snijgeometrie; None als er geen snijding is."""
    if geometrie is None or geometrie.is_empty:
        return None
    punt = geometrie.representative_point()
    return (punt.x, punt.y)


@dataclass(frozen=True)
class _Nabijheid:
    """De leidingen waarvan TOP-006, TOP-010 en TOP-011 de onderlinge ligging toetsen.

    Een eigen index naast `_Topologie`, en met opzet: die laatste draagt élke leiding
    met geometrie, want TOP-021 vraagt of er *enige* streng langs een put doorloopt.
    Deze drie checks vragen iets anders -- liggen twee leidingen elkaar in de weg -- en
    dat is alleen zinnig binnen de rol `nabijheidsleidingen`. Zie issue #82 en BO-69.
    """

    conduits: list[Conduit]
    # De hartlijnen als object-array, in dezelfde volgorde als `conduits`. De drie checks
    # bevragen de STRtree in bulk (`_paren`) en rekenen hun afstanden, snijdingen en
    # buffers over deze array; hem een keer bewaren scheelt een array per aanroep. Zie
    # issue #145.
    lijnen: np.ndarray
    tree: STRtree | None
    # Per streng-URI de uiteinden; alleen voor de strengen in `conduits`, dus altijd
    # gevuld. TOP-010 gebruikt ze om een gedeeld uiteinde te herkennen.
    eindpunten: dict[str, tuple[Point, Point]]
    # Hoeveel leidingen buiten deze populatie vielen, en hoeveel er in totaal zijn;
    # `notes()` verantwoordt de versmalling ermee. Invariant: `totaal - buiten` is de
    # populatie, anders noemt die regel een ander getal dan er getoetst is.
    buiten: int
    totaal: int


def _nabijheid(context: CheckContext) -> _Nabijheid:
    """De nabijheidsindex, een keer per context gebouwd."""
    return context.cached("topologie:nabijheid", lambda: _bouw_nabijheid(context))


def _bouw_nabijheid(context: CheckContext) -> _Nabijheid:
    """Bouwt de index over de leidingen waarvan de onderlinge ligging getoetst wordt.

    De populatie is de rol `nabijheidsleidingen` zelf, en niet haar doorsnede met de
    leidingenrol: `[klassen] streng` en `[klassen] nabijheidsleiding` zijn los
    configureerbaar, en een duiker zou bij een versmalde `streng` anders stil uit de
    populatie vallen. De leidingenrol wordt alleen geteld, voor de verantwoording in
    `notes()`: hoeveel leidingen er buiten de versmalde populatie vielen.

    Dat tellen gaat over de vereniging van de twee rollen, zodat `totaal - buiten` de
    populatie blijft. Zou `totaal` alleen de leidingenrol tellen, dan zou een project
    dat `streng` versmalt een verantwoordingsregel krijgen die een kleiner getal noemt
    dan er getoetst is. Onder de standaardconfiguratie (`streng = ["Leiding"]`) valt de
    populatie binnen de leidingenrol en verandert er niets.
    """
    binnen = nabijheidsleidingen(context)
    in_populatie = {conduit.uri for conduit in binnen}
    alle = leidingen(context)
    totaal = len({conduit.uri for conduit in alle} | in_populatie)

    conduits: list[Conduit] = []
    eindpunten: dict[str, tuple[Point, Point]] = {}
    for conduit in binnen:
        uiteinden = _eindige_eindpunten(coords_van(context, conduit.uri, conduit.line))
        if uiteinden is None:
            continue
        eindpunten[conduit.uri] = uiteinden
        conduits.append(conduit)

    lijnen = np.array([conduit.line for conduit in conduits], dtype=object)
    return _Nabijheid(
        conduits=conduits,
        lijnen=lijnen,
        tree=STRtree(lijnen) if conduits else None,
        eindpunten=eindpunten,
        buiten=totaal - len(in_populatie),
        totaal=totaal,
    )


def _nabijheidsnotitie(context: CheckContext) -> list[str]:
    """Verantwoordt de versmalde populatie van TOP-006, TOP-010 en TOP-011."""
    nabijheid = _nabijheid(context)
    klassen = ", ".join(context.config.klassen.nabijheidsleiding) or "(geen)"
    return [
        f"Getoetst zijn alleen paren waarvan beide leidingen onder {klassen} vallen "
        f"(`[klassen] nabijheidsleiding`). {nabijheid.buiten} van de "
        f"{getal(nabijheid.totaal, 'leiding', 'leidingen')} "
        f"{vorm(nabijheid.buiten, 'valt', 'vallen')} daarbuiten -- onder meer drains, "
        "mechanische leidingen en aansluitleidingen -- en elk paar waarin zo'n leiding "
        "voorkomt is niet beoordeeld."
    ]


def _buren(nabijheid: _Nabijheid, conduit: Conduit, marge: float) -> Iterator[Conduit]:
    """De andere strengen die binnen de marge van deze streng liggen.

    `dwithin` toetst de echte afstand en is daarmee strenger dan de oude
    omhullende-vergelijking op een gebufferde lijn; elke aanroeper past op de
    kandidaten alsnog zijn eigen exacte afstandstoets toe, dus de uitkomst
    verandert niet. Bij marge nul blijven alleen rakende of snijdende lijnen over.
    """
    if nabijheid.tree is None or conduit.line is None:
        return
    for index in nabijheid.tree.query(conduit.line, predicate="dwithin", distance=marge):
        ander = nabijheid.conduits[int(index)]
        if ander.uri != conduit.uri:
            yield ander


def _paren(nabijheid: _Nabijheid, **kw: object) -> tuple[np.ndarray, np.ndarray]:
    """De gerichte (a, b)-indexparen uit één STRtree-query over alle lijnen.

    De bulkvariant van `_buren`: `tree.query(lijnen, ...)` levert alle kandidaatparen in
    één keer, in plaats van een boomrondgang per streng. `a` en `b` zijn indexen in
    `nabijheid.conduits`; het zelfpaar valt weg op de URI, net als in `_buren`. De
    keyword-argumenten gaan onveranderd naar `STRtree.query` (`predicate=` en, voor de
    afstandspredicaten, een `distance=` die scalair of per lijn mag zijn). Bij een lege
    boom geeft de aanroeper deze functie niet aan; `nabijheid.tree` is dan `None`.
    """
    assert nabijheid.tree is not None
    paren = nabijheid.tree.query(nabijheid.lijnen, **kw)  # type: ignore[arg-type]
    a, b = paren[0], paren[1]
    uris = np.array([conduit.uri for conduit in nabijheid.conduits], dtype=object)
    houd = uris[a] != uris[b]
    return a[houd], b[houd]


@register
class LosliggendePut(Check):
    """TOP-001: putten waarop geen enkele streng aansluit."""

    id = "TOP-001"
    title = "Losliggende putten (geen enkele streng aangesloten)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putten zonder strengeindpunt binnen de snapping-tolerantie.

        Dit is de geometrische variant; de administratieve koppeling dekt de
        nulmeting al via Hyd. Elke leiding telt mee, ook een persleiding of drain:
        het register vraagt of er *enige* streng aansluit. Zou hier alleen op
        vrijvervalleidingen gekeken worden, dan zou elke put van de drukriolering
        als losliggend gelden.
        """
        topologie = _topologie(context)
        tolerantie = context.config.drempels.snapping_tolerantie_m
        snapping = _snapping(context)

        aangesloten: set[str] = set()
        for conduit in topologie.all_conduits:
            for treffer in snapping.get(conduit.uri, ()):
                if treffer is not None:
                    aangesloten.add(treffer.uri)

        for node in topologie.nodes:
            if node.uri not in aangesloten:
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Geen strengeindpunt binnen {tolerantie:g} m van deze put.",
                    drempel=f"{tolerantie:g} (drempels.snapping_tolerantie_m)",
                    tolerantie_m=tolerantie,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samengevoegde compartimentduplicaten."""
        return _dedupnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met geometrie."""
        return len(_topologie(context).nodes)


class _StrengPutAansluiting(Check):
    """Gedeelde basis voor de checks op het aantal aangesloten eindobjecten per streng."""

    verwacht: int

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt per streng hoeveel uiteinden op een geldig eindobject vallen.

        Geldig is een put binnen de snapping-tolerantie, of -- sinds issue #89 -- een
        hulpstuk met een telbare GWSW-functie op diezelfde afstand: een streng die
        tussen twee T-stukken ligt is aangesloten, ook al is een `Hulpstuk` in het GWSW
        geen `Put`. Mist zo'n hulpstuk zelf een leiding, dan is dat het gebrek dat
        TOP-022 meldt; hier telt alleen of de streng ergens op uitkomt. Zie BO-72.
        """
        topologie = _topologie(context)
        tolerantie = context.config.drempels.snapping_tolerantie_m
        snapping = _snapping(context)
        eindhulpstukken = _eindhulpstukken(context)

        for conduit in topologie.conduits:
            treffers = snapping.get(conduit.uri)
            uiteinden = topologie.endpoints_of(context, conduit)
            if treffers is None or uiteinden is None:
                continue
            geldig = sum(
                1
                for node, punt in zip(treffers, uiteinden, strict=True)
                if node is not None or eindhulpstukken.raakt(punt, tolerantie)
            )
            if geldig != self.verwacht:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                self.melding(tolerantie),
                drempel=f"{tolerantie:g} (drempels.snapping_tolerantie_m)",
                tolerantie_m=tolerantie,
            )

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        raise NotImplementedError

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samenvoeging en dat een hulpstuk als eind meetelt.

        Deze twee checks lezen de puttenindex niet rechtstreeks, maar wel via de
        snapping, en die draait op de STRtree over dezelfde -- ontdubbelde -- lijst. Valt
        een duplicaat weg dat verder dan de snapping-tolerantie van het origineel lag,
        dan verliest het strengeinde dat erop uitkwam zijn aansluiting en is het precies
        deze check die dat meldt. Zie BO-71.
        """
        tolerantie = context.config.drempels.snapping_tolerantie_m
        aantal = len(_eindhulpstukken(context).nodes)
        return [
            *_dedupnotitie(context),
            f"Een strengeinde dat binnen {tolerantie:g} m op een hulpstuk met een telbare "
            "GWSW-functie valt (T-stuk, kruisstuk, mof) telt hier als geldig eind: de streng "
            f"komt ergens op uit. {getal(aantal, 'hulpstuk', 'hulpstukken')} met geometrie "
            f"{vorm(aantal, 'telt', 'tellen')} zo mee. Of zo'n hulpstuk zelf het juiste aantal "
            "leidingen verbindt is een andere vraag, en die stelt TOP-022. Een hulpstuk waarvan "
            "de klasse geen aantal voorschrijft -- een afsluitstuk of ontstoppingsstuk -- telt "
            "niet als eind. Zie BO-72.",
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen met geometrie."""
        topologie = _topologie(context)
        return sum(1 for conduit in topologie.conduits if topologie.endpoints_of(context, conduit))


@register
class LosliggendeStreng(_StrengPutAansluiting):
    """TOP-002: strengen zonder put aan beide zijden."""

    id = "TOP-002"
    title = "Losliggende strengen (aan geen van beide zijden een put)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    verwacht = 0

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        return (
            f"Geen van beide strengeinden ligt binnen {tolerantie:g} m van een put of van "
            "een hulpstuk met een telbare GWSW-functie."
        )


@register
class StrengMetEenPut(_StrengPutAansluiting):
    """TOP-003: strengen met slechts aan een zijde een put."""

    id = "TOP-003"
    title = "Streng met slechts aan een zijde een put"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    verwacht = 1

    def melding(self, tolerantie: float) -> str:
        """De tekst van de bevinding."""
        return (
            f"Slechts een van beide strengeinden ligt binnen {tolerantie:g} m van een put "
            "of van een hulpstuk met een telbare GWSW-functie."
        )


def _omgekeerd_gesnapt(context: CheckContext) -> frozenset[str]:
    """De vrijvervalstrengen die gesnapt zijn maar omgekeerd getekend (TOP-004, issue #156).

    Een streng die administratief van A naar B loopt maar van B naar A getekend is, heeft
    haar beide uiteinden wél op een put liggen -- alleen in de omgekeerde volgorde. TOP-004
    vergelijkt de uiteinden in administratieve volgorde en zou zo'n streng twee keer als
    'niet gesnapt' melden (elk eind ligt ver van de put waaraan het administratief hangt),
    terwijl er geen snappingsfout is. NET-009 signaleert de omgekeerde tekenrichting al;
    deze set houdt die dubbele valse diagnose uit TOP-004.

    Alleen wanneer de lijn omgekeerd is (`richting_van_geometrie`) én beide uiteinden
    binnen de snapping-tolerantie van de put aan de andere kant liggen. Ligt één eind
    daarbuiten, dan is er wél een echte snappingsfout en blijft de melding staan.
    """
    return context.cached("topologie:omgekeerd_gesnapt", lambda: _bouw_omgekeerd_gesnapt(context))


def _bouw_omgekeerd_gesnapt(context: CheckContext) -> frozenset[str]:
    """Bepaalt welke strengen 'gesnapt maar omgekeerd getekend' zijn; zie `_omgekeerd_gesnapt`."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    tolerantie = context.config.drempels.snapping_tolerantie_m
    topologie = _topologie(context)

    gevonden: set[str] = set()
    for conduit in topologie.conduits:
        uiteinden = topologie.endpoints_of(context, conduit)
        if uiteinden is None:
            continue
        uitslag = dataset.richting_van_geometrie(conduit, wortels)
        if uitslag is None:
            continue
        omgekeerd, begin, eind = uitslag
        if not omgekeerd or begin.point is None or eind.point is None:
            continue
        # Omgekeerd getekend: de lijn loopt van de administratieve eindput naar de beginput.
        # Beide uiteinden gesnapt = de lijnstart ligt op de eindput en het lijneind op de
        # beginput, elk binnen de tolerantie.
        if (
            eind.point.distance(uiteinden[0]) <= tolerantie
            and begin.point.distance(uiteinden[1]) <= tolerantie
        ):
            gevonden.add(conduit.uri)
    return frozenset(gevonden)


@register
class NietGesneptStrengeinde(Check):
    """TOP-004: strengeindpunt ligt te ver van de put waaraan het gekoppeld is."""

    id = "TOP-004"
    title = "Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de administratieve koppeling met de geometrische afstand.

        Een streng die gesnapt is maar omgekeerd getekend, wordt overgeslagen: haar
        uiteinden liggen wél op een put, alleen in de omgekeerde volgorde, dus de
        administratieve-volgordevergelijking hieronder zou er twee valse
        snappingsmeldingen van maken. NET-009 draagt dat signaal al; `notes()` telt ze.
        Zie issue #156.
        """
        dataset = context.dataset
        tolerantie = context.config.drempels.snapping_tolerantie_m
        wortels = context.config.klassen.netwerkknopen
        topologie = _topologie(context)
        omgekeerd = _omgekeerd_gesnapt(context)

        for conduit in topologie.conduits:
            if conduit.uri in omgekeerd:
                continue
            uiteinden = topologie.endpoints_of(context, conduit)
            if uiteinden is None:
                continue
            koppelingen = (
                ("beginpunt", conduit.start_node, uiteinden[0]),
                ("eindpunt", conduit.end_node, uiteinden[1]),
            )
            for zijde, gekoppeld, punt in koppelingen:
                node_uri = dataset.resolve_network_node(gekoppeld, wortels)
                node = dataset.nodes.get(node_uri) if node_uri else None
                if node is None or node.point is None:
                    continue
                afstand = node.point.distance(punt)
                if afstand > tolerantie:
                    yield self.finding(
                        context,
                        conduit.uri,
                        conduit.label,
                        f"Het {zijde} ligt {afstand:.3f} m van put {node.label!r}, "
                        f"meer dan de tolerantie van {tolerantie:g} m.",
                        waarde=f"{afstand:.3f}",
                        drempel=f"{tolerantie:g} (drempels.snapping_tolerantie_m)",
                        zijde=zijde,
                        afstand_m=round(afstand, 3),
                        put=node.label,
                        tolerantie_m=tolerantie,
                        foutlocatie=(punt.x, punt.y),
                    )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de strengen die gesnapt zijn maar omgekeerd getekend (issue #156)."""
        aantal = len(_omgekeerd_gesnapt(context))
        if not aantal:
            return []
        return [
            f"{getal(aantal, 'streng is', 'strengen zijn')} gesnapt maar omgekeerd getekend "
            f"(van eind naar begin) en {vorm(aantal, 'is', 'zijn')} hier niet als "
            "snappingsfout gemeld; NET-009 signaleert de omgekeerde tekenrichting."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen met geometrie."""
        topologie = _topologie(context)
        return sum(1 for conduit in topologie.conduits if topologie.endpoints_of(context, conduit))


@register
class DubbelePut(Check):
    """TOP-005: twee putten die binnen de tolerantie samenvallen."""

    id = "TOP-005"
    title = "Dubbele putten: twee knopen binnen tolerantie"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putparen die dichter bij elkaar liggen dan de tolerantie."""
        topologie = _topologie(context)
        tolerantie = context.config.drempels.dubbele_put_tolerantie_m
        if topologie.tree is None:
            return

        gemeld: set[tuple[str, str]] = set()
        for node in topologie.nodes:
            for index in topologie.tree.query(_punt(node).buffer(tolerantie)):
                ander = topologie.nodes[int(index)]
                if ander.uri == node.uri:
                    continue
                afstand = _punt(node).distance(_punt(ander))
                if afstand > tolerantie:
                    continue
                eerste, tweede = sorted((node.uri, ander.uri))
                sleutel = (eerste, tweede)
                if sleutel in gemeld:
                    continue
                gemeld.add(sleutel)
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Ligt {afstand:.3f} m van put {ander.label!r}, binnen de "
                    f"tolerantie van {tolerantie:g} m.",
                    waarde=f"{afstand:.3f}",
                    drempel=f"{tolerantie:g} (drempels.dubbele_put_tolerantie_m)",
                    object2_label=ander.label,
                    object2_uri=ander.uri,
                    afstand_m=round(afstand, 3),
                    tolerantie_m=tolerantie,
                    foutlocatie=_midden(node.point, ander.point),
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samengevoegde compartimentduplicaten."""
        return _dedupnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met geometrie."""
        return len(_topologie(context).nodes)


@register
class StrengMetZelfdePut(Check):
    """TOP-012: streng met dezelfde put aan begin- en eindpunt."""

    id = "TOP-012"
    title = "Streng met dezelfde put aan begin- en eindpunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen waarvan beide uiteinden naar dezelfde put verwijzen."""
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        for conduit in _topologie(context).conduits:
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            eind = dataset.resolve_network_node(conduit.end_node, wortels)
            if begin is None or begin != eind:
                continue
            node = dataset.nodes.get(begin)
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Begin- en eindpunt verwijzen allebei naar put {node.label if node else begin!r}.",
                put=node.label if node else begin,
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).conduits)


@register
class OverlappendeStreng(Check):
    """TOP-006: strengen die (deels) over elkaar heen liggen."""

    id = "TOP-006"
    title = "Dubbel ingetekende of (deels) overlappende strengen"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS
    rollen = ("leidingen", "nabijheidsleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengparen die over een aanzienlijke lengte samenvallen.

        Twee strengen die alleen in een put bij elkaar komen raken elkaar over een
        verwaarloosbare lengte; pas als ze over meer dan de minimumlengte binnen
        elkaars tolerantie blijven liggen ze dubbel ingetekend. Beide strengen van
        een paar moeten in de rol `nabijheidsleidingen` zitten (issue #82).
        """
        nabijheid = _nabijheid(context)
        if nabijheid.tree is None:
            return
        drempels = context.config.drempels
        tolerantie = drempels.overlap_tolerantie_m
        minimum = drempels.overlap_minimale_lengte_m

        a, b = _paren(nabijheid, predicate="dwithin", distance=tolerantie)
        if not a.size:
            return
        # Buffer alleen de strengen die werkelijk als tegenpartij (`b`) voorkomen en map
        # terug; `quad_segs=16` houdt het bit-gelijk aan het oude `_lijn(ander).buffer(tol)`.
        # `intersection`/`length` daarna bulk over de paren.
        uniek_b, terug = np.unique(b, return_inverse=True)
        buffers = shapely.buffer(nabijheid.lijnen[uniek_b], tolerantie, quad_segs=16)
        lengten = shapely.length(
            shapely.intersection(nabijheid.lijnen[a], buffers[terug.reshape(-1)])
        )
        lengte_van = {
            (int(i), int(j)): float(lengte) for i, j, lengte in zip(a, b, lengten, strict=True)
        }

        gemeld: set[tuple[int, int]] = set()
        for i, j in zip(a, b, strict=True):
            i, j = int(i), int(j)
            sleutel = (min(i, j), max(i, j))
            if sleutel in gemeld:
                continue
            lengte = lengte_van[(i, j)]
            if lengte < minimum:
                continue
            gemeld.add(sleutel)
            conduit, ander = nabijheid.conduits[i], nabijheid.conduits[j]
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Valt over {lengte:.2f} m samen met streng {ander.label!r} "
                f"(tolerantie {tolerantie:g} m).",
                waarde=f"{lengte:.2f}",
                drempel=f"{minimum:g} (drempels.overlap_minimale_lengte_m)",
                object2_label=ander.label,
                object2_uri=ander.uri,
                overlaplengte_m=round(lengte, 3),
                tolerantie_m=tolerantie,
                foutlocatie=_dichtste_midden(conduit.line, ander.line),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de leidingen die buiten de versmalde populatie vielen."""
        return _nabijheidsnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal getoetste leidingen met bruikbare geometrie."""
        return len(_nabijheid(context).conduits)


@register
class DegeneratieveGeometrie(Check):
    """TOP-007: nul-lengte, zelfkruisende of anderszins onbruikbare geometrie."""

    id = "TOP-007"
    title = "Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen zonder bruikbare lijn.

        Vier vormen tellen mee: geen geometrie, een lengte onder de drempel, minder
        dan twee verschillende punten, en niet-eindige coordinaten. Zelfkruising
        valt hier ook onder; die wordt daarnaast door TOP-017 als waarschuwing
        gemeld, omdat het register beide ID's kent met een eigen ernst.
        """
        drempel = context.config.drempels.nul_lengte_m

        for conduit in _topologie(context).all_conduits:
            geval = self._reden(context, conduit, drempel)
            if geval is None:
                continue
            reden, waarde, drempeltekst = geval
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                reden,
                waarde=waarde,
                drempel=drempeltekst,
                nul_lengte_m=drempel,
            )

    def _reden(
        self, context: CheckContext, conduit: Conduit, drempel: float
    ) -> tuple[str, str, str] | None:
        """De reden waarom deze geometrie onbruikbaar is, met de gemeten lengte en drempel.

        Alleen de lengtegrens vergelijkt een gemeten waarde met de drempel; de andere
        redenen (geen lijn, oneindige coordinaten, te weinig punten, zelfkruising) dragen
        geen waarde en geen drempel en laten die velden leeg.
        """
        if conduit.line is None or conduit.line.is_empty:
            return "Heeft geen lijngeometrie.", "", ""
        if not is_finite(conduit.line):
            return "Bevat coordinaten die geen eindig getal zijn.", "", ""
        punten = unieke_coords_van(context, conduit.uri, conduit.line)
        if len(punten) < 2:
            return (
                f"Bestaat uit {len(punten)} verschillend(e) punt(en) en heeft geen verloop.",
                "",
                "",
            )
        if conduit.line.length <= drempel:
            lengte = conduit.line.length
            return (
                f"Heeft een lengte van {lengte:.4f} m, onder de drempel {drempel:g} m.",
                f"{lengte:.4f}",
                f"{drempel:g} (drempels.nul_lengte_m)",
            )
        if not conduit.line.is_simple:
            return "Kruist zichzelf; zie ook TOP-017.", "", ""
        return None

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).all_conduits)


@register
class StrengNietRecht(Check):
    """TOP-008: vrijvervalstreng loopt niet recht van put tot put."""

    id = "TOP-008"
    title = "Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meet hoe ver de hartlijn van de rechte put-putverbinding afwijkt.

        Een vrijvervalstreng hoort recht te zijn: elke knik hoort een put te
        hebben. Extra vertices zijn op zichzelf geen fout zolang ze op de rechte
        lijn liggen; pas de afwijking loodrecht daarop telt.
        """
        drempel = context.config.drempels.rechtheid_afwijking_m

        for conduit in _topologie(context).conduits:
            if conduit.line is None or conduit.line.is_empty:
                continue
            punten = unieke_coords_van(context, conduit.uri, conduit.line)
            if len(punten) < 3:
                continue
            afwijking = max_offset_from_chord_kern(punten)
            if afwijking <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Wijkt {afwijking:.2f} m af van de rechte lijn tussen begin- en eindpunt "
                f"({len(punten) - 2} tussenpunt(en), drempel {drempel:g} m).",
                waarde=f"{afwijking:.2f}",
                drempel=f"{drempel:g} (drempels.rechtheid_afwijking_m)",
                afwijking_m=round(afwijking, 3),
                tussenpunten=len(punten) - 2,
                drempel_m=drempel,
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal vrijvervalstrengen met geometrie."""
        return sum(1 for conduit in _topologie(context).conduits if conduit.line is not None)


@register
class BuitenRdBereik(Check):
    """TOP-009: ontbrekende coordinaten of coordinaten buiten het RD-bereik."""

    id = "TOP-009"
    title = "Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten"
    severity = Severity.ERROR
    dimension = Dimension.ACCURACY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst elke knoop en streng op aanwezige, geldige RD-coordinaten."""
        drempels = context.config.drempels
        grenzen = (drempels.rd_x_min, drempels.rd_x_max, drempels.rd_y_min, drempels.rd_y_max)

        gedekt: set[str] = set()
        for node in _topologie(context).nodes:
            gedekt.add(node.uri)
            geval = self._melding(node.point, grenzen, "put")
            if geval is not None:
                melding, waarde, drempel = geval
                yield self.finding(
                    context, node.uri, node.label, melding, waarde=waarde, drempel=drempel
                )

        # De topologie-index draagt alleen knopen met een punt (`_bouw_topologie` filtert
        # daarop); een put zonder coordinaten valt er dus buiten en zou anders nooit
        # gemeld worden. Dat is precies wat het register onder "ontbrekende coordinaten"
        # verwacht (BO-4, issue #152). `gedekt` houdt een knoop die de index wél kent
        # (ook een lege puntgeometrie) uit de tweede lus, zodat niets dubbel telt.
        for node in netwerkknopen(context):
            if node.uri in gedekt or (node.point is not None and not node.point.is_empty):
                continue
            geval = self._melding(node.point, grenzen, "put")
            if geval is not None:
                melding, waarde, drempel = geval
                yield self.finding(
                    context, node.uri, node.label, melding, waarde=waarde, drempel=drempel
                )

        for conduit in _topologie(context).all_conduits:
            geval = self._melding(conduit.line, grenzen, "streng")
            if geval is not None:
                melding, waarde, drempel = geval
                yield self.finding(
                    context, conduit.uri, conduit.label, melding, waarde=waarde, drempel=drempel
                )

    def _melding(
        self, geometrie: BaseGeometry, grenzen: tuple[float, ...], soort: str
    ) -> tuple[str, str, str] | None:
        """De reden waarom deze geometrie buiten het geldige bereik valt, met waarde en drempel.

        De overschreden coordinaat is de gemeten waarde en de RD-grens die zij passeert de
        drempel; een ontbrekende of oneindige coordinaat draagt er geen en laat ze leeg.
        """
        x_min, x_max, y_min, y_max = grenzen
        if geometrie is None or geometrie.is_empty:
            return f"Deze {soort} heeft geen coordinaten.", "", ""
        if not is_finite(geometrie):
            return f"Deze {soort} heeft coordinaten die geen eindig getal zijn.", "", ""
        omhullende = geometrie.bounds
        if omhullende[0] < x_min or omhullende[2] > x_max:
            melding = (
                f"De x-coordinaat ligt buiten het RD-bereik "
                f"[{x_min:g}, {x_max:g}]: {omhullende[0]:.1f} tot {omhullende[2]:.1f}."
            )
            if omhullende[0] < x_min:
                return melding, f"{omhullende[0]:.1f}", f"{x_min:g} (drempels.rd_x_min)"
            return melding, f"{omhullende[2]:.1f}", f"{x_max:g} (drempels.rd_x_max)"
        if omhullende[1] < y_min or omhullende[3] > y_max:
            melding = (
                f"De y-coordinaat ligt buiten het RD-bereik "
                f"[{y_min:g}, {y_max:g}]: {omhullende[1]:.1f} tot {omhullende[3]:.1f}."
            )
            if omhullende[1] < y_min:
                return melding, f"{omhullende[1]:.1f}", f"{y_min:g} (drempels.rd_y_min)"
            return melding, f"{omhullende[3]:.1f}", f"{y_max:g} (drempels.rd_y_max)"
        return None

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welk deel van deze check niet uitgevoerd is."""
        return [
            *_dedupnotitie(context),
            "Alleen het RD-bereik en het ontbreken van coordinaten zijn getoetst. Het "
            "beheergebied is niet getoetst: er is geen beheergebiedpolygoon aangeleverd. "
            "Het studiegebied Koekangerveld is daarvoor geen vervanging, want dat beslaat "
            "een kern binnen de gemeente en niet het beheergebied.",
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal beoordeelde knopen plus strengen.

        De puttenindex (`_topologie().nodes`) is ná de compartiment-ontdubbeling (BO-71),
        net als bij de zusterchecks TOP-001/005/014/015/021 die die samenvoeging via
        `_dedupnotitie` verantwoorden; daar bovenop komen de knopen zonder punt, die de
        index weglaat maar de tweede lus juist toetst. Een rauwe `len(netwerkknopen)` zou
        de door dedup samengevoegde knopen dubbel tellen en de dekking-% laten verschuiven
        (op De Wolden ~91, BO-71). Puntloze knopen worden nooit ontdubbeld, dus de twee
        tellingen overlappen niet. Zie issue #152.
        """
        zonder_punt = sum(1 for node in netwerkknopen(context) if node.point is None)
        return len(_topologie(context).nodes) + zonder_punt + len(_topologie(context).all_conduits)


@register
class StrengenRakenMetBuffer(Check):
    """TOP-010: strengen die elkaar raken zodra de diameter meegerekend wordt."""

    id = "TOP-010"
    title = "Streng met buffer op basis van diameter kruist of raakt andere strengen"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY
    rollen = ("leidingen", "nabijheidsleidingen")
    kenmerken = ("BreedteLeiding", "HoogteLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengparen waarvan de buizen elkaar in het platte vlak raken.

        Strengen die een put delen raken elkaar per definitie; die vallen af. Wat
        overblijft zijn kruisingen en te dicht langs elkaar lopende buizen. De
        toets is tweedimensionaal: een kruising op verschillende diepte komt er ook
        in voor. HGT-004 en HGT-009 kijken naar de hoogten. Beide strengen van een
        paar moeten in de rol `nabijheidsleidingen` zitten (issue #82).
        """
        nabijheid = _nabijheid(context)
        if nabijheid.tree is None:
            return
        marge = context.config.drempels.diameterbuffer_marge_m
        tolerantie = context.config.drempels.snapping_tolerantie_m

        stralen = np.array(
            [half_diameter_m(c.breedte_mm, c.hoogte_mm) for c in nabijheid.conduits], dtype=float
        )
        # De grootste straal in de dataset bepaalt hoe ver een tegenpartij kan
        # liggen en toch nog binnen de gezamenlijke buffer vallen.
        grootste = float(stralen.max()) if stralen.size else 0.0

        a, b = _paren(nabijheid, predicate="dwithin", distance=stralen + grootste + marge)
        if not a.size:
            return
        afstanden = shapely.distance(nabijheid.lijnen[a], nabijheid.lijnen[b])
        buffers = stralen[a] + stralen[b] + marge
        houd = (buffers > 0.0) & (afstanden <= buffers)
        a, b, afstanden, buffers = a[houd], b[houd], afstanden[houd], buffers[houd]

        # De verbonden knopen alleen voor de strengen die na de buffertoets overblijven,
        # lui: `verbonden_knopen` was in de oude vorm per streng vooraf uitgerekend.
        knopen: dict[int, tuple[str | None, str | None]] = {}

        def knopen_van(i: int) -> tuple[str | None, str | None]:
            if i not in knopen:
                knopen[i] = verbonden_knopen(context, nabijheid.conduits[i])
            return knopen[i]

        gemeld: set[tuple[int, int]] = set()
        for i, j, afstand_ruw, buffer_ruw in zip(a, b, afstanden, buffers, strict=True):
            i, j = int(i), int(j)
            sleutel = (min(i, j), max(i, j))
            if sleutel in gemeld:
                continue
            conduit, ander = nabijheid.conduits[i], nabijheid.conduits[j]
            if self._deelt_put(knopen_van(i), knopen_van(j)):
                continue
            if self._deelt_uiteinde(nabijheid, conduit, ander, tolerantie):
                continue
            gemeld.add(sleutel)
            afstand, buffer = float(afstand_ruw), float(buffer_ruw)
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Ligt {afstand:.2f} m van streng "
                f"{ander.label!r}, binnen de gezamenlijke buisbuffer van {buffer:.2f} m.",
                waarde=f"{afstand:.2f}",
                drempel=f"{marge:g} (drempels.diameterbuffer_marge_m)",
                object2_label=ander.label,
                object2_uri=ander.uri,
                afstand_m=round(afstand, 3),
                buffer_m=round(buffer, 3),
                foutlocatie=_dichtste_midden(conduit.line, ander.line),
            )

    def _deelt_put(
        self, links: tuple[str | None, str | None], rechts: tuple[str | None, str | None]
    ) -> bool:
        """Geeft aan of twee strengen administratief een put delen."""
        return bool({uri for uri in links if uri} & {uri for uri in rechts if uri})

    def _deelt_uiteinde(
        self, nabijheid: _Nabijheid, conduit: Conduit, ander: Conduit, tolerantie: float
    ) -> bool:
        """Geeft aan of twee strengen geometrisch een uiteinde delen."""
        eigen, andere = nabijheid.eindpunten[conduit.uri], nabijheid.eindpunten[ander.uri]
        return any(links.distance(rechts) <= tolerantie for links in eigen for rechts in andere)

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de populatie, de tweedimensionale afbakening en de strengen zonder maat."""
        nabijheid = _nabijheid(context)
        notities = [
            *_nabijheidsnotitie(context),
            "Deze toets is tweedimensionaal. In een stedelijk stelsel kruisen leidingen "
            "elkaar routinematig op verschillende diepte; zo'n kruising is pas een gebrek "
            "als de buizen elkaar ook in hoogte raken. Gebruik HGT-004, HGT-009 en HGT-018 "
            "om te bepalen welke van deze bevindingen een echt conflict zijn.",
        ]
        zonder = sum(
            1
            for conduit in nabijheid.conduits
            if half_diameter_m(conduit.breedte_mm, conduit.hoogte_mm) == 0.0
        )
        if zonder:
            notities.append(
                f"{zonder} van de {len(nabijheid.conduits)} strengen hebben geen bruikbare "
                "breedte- of hoogtemaat; die krijgen buffer nul en komen alleen in beeld als "
                "de tegenpartij dik genoeg is."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal getoetste leidingen met bruikbare geometrie."""
        return len(_nabijheid(context).conduits)


@register
class Hartlijnkruising(Check):
    """TOP-011: strengen waarvan de hartlijnen elkaar kruisen."""

    id = "TOP-011"
    title = "Hartlijnkruisingen strengen onderling (zonder buffer)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("leidingen", "nabijheidsleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengparen waarvan de hartlijnen elkaar echt snijden.

        `crosses` is precies wat het register bedoelt: de binnenkanten snijden
        elkaar. Strengen die alleen in een gedeelde put samenkomen raken elkaar en
        kruisen niet, en vallen dus vanzelf af. Beide strengen van een paar moeten
        in de rol `nabijheidsleidingen` zitten (issue #82).
        """
        nabijheid = _nabijheid(context)
        if nabijheid.tree is None:
            return

        a, b = _paren(nabijheid, predicate="crosses")
        gemeld: set[tuple[int, int]] = set()
        for i, j in zip(a, b, strict=True):
            i, j = int(i), int(j)
            sleutel = (min(i, j), max(i, j))
            if sleutel in gemeld:
                continue
            gemeld.add(sleutel)
            conduit, ander = nabijheid.conduits[i], nabijheid.conduits[j]
            snijpunt = _lijn(conduit).intersection(_lijn(ander))
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"De hartlijn kruist die van streng {ander.label!r}.",
                object2_label=ander.label,
                object2_uri=ander.uri,
                foutlocatie=_representatief(snijpunt),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de populatie en dat een kruising in het platte vlak nog geen conflict is."""
        return [
            *_nabijheidsnotitie(context),
            "Een hartlijnkruising in het platte vlak is normaal: hemelwater en gemengd "
            "kruisen elkaar in vrijwel elke straat, op verschillende diepte. Deze check "
            "wijst de plaatsen aan waar dat gebeurt; of het een conflict is volgt uit de "
            "hoogten (HGT-004, HGT-009, HGT-018), niet uit deze bevinding.",
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal getoetste leidingen met bruikbare geometrie."""
        return len(_nabijheid(context).conduits)


@register
class ParallelleStrengen(Check):
    """TOP-013: meer dan twee strengen tussen hetzelfde putpaar."""

    id = "TOP-013"
    title = "Meer dan twee parallelle strengen tussen hetzelfde putpaar"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt de strengen per putpaar en meldt de paren boven het maximum."""
        maximum = context.config.drempels.parallelle_strengen_maximum

        per_paar: dict[frozenset[str], list[Conduit]] = {}
        for conduit in _topologie(context).all_conduits:
            begin, eind = verbonden_knopen(context, conduit)
            if begin is None or eind is None or begin == eind:
                continue
            per_paar.setdefault(frozenset((begin, eind)), []).append(conduit)

        for paar, strengen in per_paar.items():
            if len(strengen) <= maximum:
                continue
            labels = sorted(conduit.label for conduit in strengen)
            putten = sorted(self._label(context, uri) for uri in paar)
            for conduit in strengen:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Een van {len(strengen)} strengen tussen de putten "
                    f"{putten[0]!r} en {putten[-1]!r} (maximum {maximum}): {', '.join(labels)}.",
                    waarde=str(len(strengen)),
                    drempel=f"{maximum:g} (drempels.parallelle_strengen_maximum)",
                    aantal=len(strengen),
                    putten=putten,
                    maximum=maximum,
                )

    def _label(self, context: CheckContext, uri: str) -> str:
        """Het label van een knoop, of de URI als dat er niet is."""
        node = context.dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).all_conduits)


@register
class VeelAansluitendeStrengen(Check):
    """TOP-014: meer dan vier strengen op een put."""

    id = "TOP-014"
    title = "Meer dan vier aansluitende strengen op een put"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt per put hoeveel strengen erop aansluiten."""
        maximum = context.config.drempels.aansluitende_strengen_maximum

        telling: dict[str, list[str]] = {}
        for conduit in _topologie(context).all_conduits:
            for uri in verbonden_knopen(context, conduit):
                if uri is not None:
                    telling.setdefault(uri, []).append(conduit.label)

        for node in _topologie(context).nodes:
            strengen = telling.get(node.uri, [])
            if len(strengen) <= maximum:
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Er sluiten {len(strengen)} strengen aan op deze put (maximum {maximum}): "
                f"{', '.join(sorted(strengen))}.",
                waarde=str(len(strengen)),
                drempel=f"{maximum:g} (drempels.aansluitende_strengen_maximum)",
                aantal=len(strengen),
                maximum=maximum,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samengevoegde compartimentduplicaten."""
        return _dedupnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten."""
        return len(_topologie(context).nodes)


@register
class MultipartGeometrie(Check):
    """TOP-015: een feature met meerdere losse geometriedelen."""

    id = "TOP-015"
    title = "Streng of put met multipart-geometrie (meerdere losse delen in een feature)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk object waarvan de GML-literaal uit meerdere delen bestaat.

        De GML-lezer neemt alleen het eerste deel mee. Zonder deze check zou het
        weggelaten deel onzichtbaar blijven en zouden alle vervolgtoetsen op een
        halve geometrie draaien.
        """
        topologie = _topologie(context)

        for node in topologie.nodes:
            if node.multipart:
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    "De puntgeometrie bestaat uit meerdere losse delen; alleen het eerste "
                    "deel is ingelezen.",
                )
        for conduit in topologie.all_conduits:
            if conduit.multipart:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    "De lijngeometrie bestaat uit meerdere losse delen; alleen het eerste "
                    "deel is ingelezen.",
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samengevoegde compartimentduplicaten."""
        return _dedupnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen plus strengen."""
        topologie = _topologie(context)
        return len(topologie.nodes) + len(topologie.all_conduits)


@register
class OngeldigeGeometrie(Check):
    """TOP-016: geometrie die niet aan OGC Simple Features voldoet."""

    id = "TOP-016"
    title = "Ongeldige geometrie volgens OGC Simple Features (ST_IsValid)"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke geometrie die shapely als ongeldig aanmerkt."""
        from shapely.validation import explain_validity

        topologie = _topologie(context)
        for uri, label, geometrie in _alle_geometrieen(topologie):
            if geometrie is None or geometrie.is_empty or geometrie.is_valid:
                continue
            yield self.finding(
                context,
                uri,
                label,
                f"Ongeldige geometrie: {explain_validity(geometrie)}.",
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de objecten waarvan de geometrie al bij het inlezen strandde."""
        notities = _dedupnotitie(context)
        aantal = len(context.dataset.geometry_errors)
        if aantal:
            notities.append(
                f"{aantal} objecten hebben een GML-literaal die niet te lezen was; die konden "
                "hier niet op geldigheid getoetst worden en staan in de lijst met "
                "geometriefouten van de dataset."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen plus strengen."""
        topologie = _topologie(context)
        return len(topologie.nodes) + len(topologie.all_conduits)


@register
class NietSimpeleGeometrie(Check):
    """TOP-017: geometrie met spikes of herhaalde structuren."""

    id = "TOP-017"
    title = "Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren)"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke lijn die zichzelf raakt of kruist."""
        for conduit in _topologie(context).all_conduits:
            line = conduit.line
            if line is None or line.is_empty or line.is_simple:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                "De lijn is niet simpel: hij raakt of kruist zichzelf.",
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de overlap met TOP-007."""
        return [
            "Zelfkruisende lijnen komen ook onder TOP-007 naar voren. Het register kent "
            "beide ID's met een eigen ernst (F respectievelijk W); de overlap is bewust en "
            "betekent niet dat er twee gebreken zijn."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).all_conduits)


@register
class DubbeleVertexOfSpike(Check):
    """TOP-018: dubbele vertices of scherpe terugkeerpunten in een streng."""

    id = "TOP-018"
    title = "Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt herhaalde punten en hoeken die vrijwel terugkeren over zichzelf."""
        drempels = context.config.drempels
        tolerantie = drempels.dubbele_vertex_tolerantie_m
        hoekdrempel = drempels.spike_hoek_graden

        for conduit in _topologie(context).all_conduits:
            line = conduit.line
            if line is None or line.is_empty:
                continue
            punten = coords_van(context, conduit.uri, line)
            uniek = unieke_coords_van(context, conduit.uri, line)
            dubbel = duplicate_vertices_kern(punten, tolerantie)
            spikes = [
                (index, hoek) for index, hoek in vertex_angles_kern(uniek) if hoek <= hoekdrempel
            ]
            if not dubbel and not spikes:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                self._melding(dubbel, spikes, tolerantie, hoekdrempel),
                dubbele_vertices=len(dubbel),
                spikes=len(spikes),
            )

    def _melding(
        self,
        dubbel: list[int],
        spikes: list[tuple[int, float]],
        tolerantie: float,
        hoekdrempel: float,
    ) -> str:
        """De tekst van de bevinding."""
        delen = []
        if dubbel:
            delen.append(
                f"{len(dubbel)} vertex(en) vallen binnen {tolerantie:g} m op hun voorganger"
            )
        if spikes:
            scherpste = min(hoek for _, hoek in spikes)
            delen.append(
                f"{len(spikes)} knik(ken) onder {hoekdrempel:g} graden (scherpste "
                f"{scherpste:.1f} graden)"
            )
        return "In deze lijn: " + " en ".join(delen) + "."

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen."""
        return len(_topologie(context).all_conduits)


@register
class PseudoKnoop(Check):
    """TOP-019: twee strengen met identieke kenmerken door een functieloze knoop."""

    id = "TOP-019"
    title = "Pseudo-knoop: twee strengen gescheiden door een functieloze knoop"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = (
        "functieloze_knopen",
        "leidingen",
        "mechanischeleidingen",
        "netwerkknopen",
        "vrijvervalrioolleidingen",
    )
    kenmerken = ("BreedteLeiding", "HoogteLeiding", "MateriaalLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt functieloze knopen met precies twee gelijk gekenmerkte strengen.

        Welke klassen als functieloos gelden staat in de projectconfig. Zonder die
        lijst draait de check niet: in een rioolstelsel heeft vrijwel elke knoop
        een put, en die put *is* een functie. Elke doorgaande put als pseudo-knoop
        melden zou tienduizenden bevindingen opleveren die geen gebrek zijn.
        """
        if not context.config.klassen.functieloze_knoop:
            return

        dataset = context.dataset
        # De functieloze knopen die zuiver in het drukriool zitten vallen buiten deze toets:
        # het mechanische riool valt buiten het checkregister (issue #130). `notes()`
        # verantwoordt hoeveel er zo overgeslagen zijn.
        functieloos = {
            node.uri for node in functieloze_knopen(context)
        } - zuiver_mechanische_knopen(context)
        if not functieloos:
            return

        aansluitend: dict[str, list[Conduit]] = {}
        for conduit in _topologie(context).all_conduits:
            begin, eind = verbonden_knopen(context, conduit)
            # Terugval op de rauwe koppeling, net als `_bouw_hulpstuktelling`: een
            # hulpstuk is geen netwerkknoop en `resolve_network_node` geeft er dus None
            # voor, terwijl het wel een functieloze knoop kan zijn (T-stuk,
            # ontstoppingsstuk). Zonder terugval blijft deze index per constructie leeg.
            # Ontdubbeld op knoop, net als in `_bouw_aansluitingen`: een streng met beide
            # einden op dezelfde knoop is een streng en geen paar.
            gevonden = (begin or conduit.start_node, eind or conduit.end_node)
            for uri in dict.fromkeys(uri for uri in gevonden if uri in functieloos):
                aansluitend.setdefault(uri, []).append(conduit)

        for uri, strengen in aansluitend.items():
            if len(strengen) != 2:
                continue
            verschil = self._verschillen(strengen[0], strengen[1])
            if verschil:
                continue
            node = dataset.nodes[uri]
            yield self.finding(
                context,
                uri,
                node.label,
                f"Scheidt de strengen {strengen[0].label!r} en {strengen[1].label!r}, die "
                "dezelfde diameter, hetzelfde materiaal en hetzelfde stelseltype hebben; "
                "dit zou een streng moeten zijn.",
                strengen=[conduit.label for conduit in strengen],
            )

    def _verschillen(self, links: Conduit, rechts: Conduit) -> list[str]:
        """De kenmerken waarop twee strengen van elkaar verschillen."""
        vergelijk = (
            (
                "diameter",
                (links.breedte_mm, links.hoogte_mm),
                (rechts.breedte_mm, rechts.hoogte_mm),
            ),
            ("materiaal", links.materiaal, rechts.materiaal),
            ("stelseltype", links.types, rechts.types),
        )
        return [naam for naam, eigen, ander in vergelijk if eigen != ander]

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt of de check uberhaupt kon draaien."""
        klassen = context.config.klassen.functieloze_knoop
        if not klassen:
            return [
                "Deze check is niet gedraaid: er zijn geen functieloze knoopklassen "
                "geconfigureerd (`klassen.functieloze_knoop`). In een rioolstelsel zit op "
                "vrijwel elke knik een put, en die put is een functie; zonder expliciete "
                "lijst zou de check het hele stelsel als pseudo-knopen melden."
            ]
        notities = [f"Als functieloze knoop gelden: {', '.join(klassen)}."]
        functieloos = {node.uri for node in functieloze_knopen(context)}
        overgeslagen = len(functieloos & zuiver_mechanische_knopen(context))
        if overgeslagen:
            notities.append(
                f"{getal(overgeslagen, 'functieloze knoop', 'functieloze knopen')} "
                f"{vorm(overgeslagen, 'valt', 'vallen')} buiten deze toets: "
                f"{vorm(overgeslagen, 'die knoop zit', 'die knopen zitten')} zuiver in het "
                "drukriool (alleen mechanische leidingen, geen vrijvervalrioolleiding), en het "
                "mechanische riool valt buiten het checkregister. Zie issue #130."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen van de geconfigureerde functieloze klassen."""
        return len(functieloze_knopen(context))


# TOP-020 (digitalisatierichting tegen de van-naar-richting) is per issue #80 opgegaan in
# NET-009 en vervallen; het ID wordt niet hergebruikt. De omgekeerde tekenrichting is nu
# een deelgeval van de integrale richtingscheck (`checks/netwerk.py`).


@register
class PutNaastDoorlopendeStreng(Check):
    """TOP-021: put zonder eigen strengeindpunt maar wel op een doorlopende streng."""

    id = "TOP-021"
    title = "Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een streng"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("leidingen", "netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Verfijnt TOP-001: ligt de losliggende put toch op een streng?

        Zo'n put is niet vergeten maar verkeerd aangesloten: de streng loopt eronder
        door in plaats van erin te eindigen. Dat is een ander gebrek en een andere
        reparatie dan een put die echt nergens ligt.
        """
        topologie = _topologie(context)
        tolerantie = context.config.drempels.put_op_streng_tolerantie_m
        snapping = _snapping(context)

        met_eindpunt: set[str] = set()
        for conduit in topologie.all_conduits:
            for treffer in snapping.get(conduit.uri, ()):
                if treffer is not None:
                    met_eindpunt.add(treffer.uri)

        if topologie.line_tree is None:
            return

        for node in topologie.nodes:
            if node.uri in met_eindpunt or node.point is None:
                continue
            for index in topologie.line_tree.query(node.point.buffer(tolerantie)):
                conduit = topologie.lined[int(index)]
                afstand = _lijn(conduit).distance(node.point)
                if afstand > tolerantie:
                    continue
                uiteinden = topologie.endpoints_of(context, conduit)
                if (
                    uiteinden is not None
                    and min(punt.distance(node.point) for punt in uiteinden) <= afstand
                ):
                    continue
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Ligt {afstand:.2f} m van streng {conduit.label!r}, die er langs "
                    "doorloopt in plaats van erin te eindigen.",
                    waarde=f"{afstand:.2f}",
                    drempel=f"{tolerantie:g} (drempels.put_op_streng_tolerantie_m)",
                    streng=conduit.label,
                    streng_uri=conduit.uri,
                    afstand_m=round(afstand, 3),
                    tolerantie_m=tolerantie,
                )
                break

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de samengevoegde compartimentduplicaten."""
        return _dedupnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met geometrie."""
        return len(_topologie(context).nodes)


def _alle_geometrieen(topologie: _Topologie) -> Iterator[tuple[str, str, BaseGeometry | None]]:
    """De geometrie van elke knoop en streng, met URI en label erbij."""
    for node in topologie.nodes:
        yield node.uri, node.label, node.point
    for conduit in topologie.all_conduits:
        yield conduit.uri, conduit.label, conduit.line


class _HulpstukAansluitingen(Check):
    """Gedeelde basis voor TOP-022 (te weinig richtingen) en TOP-023 (te veel)."""

    te_veel: bool

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt per hulpstuk het aantal richtingen met de GWSW-functie.

        Een hulpstuk dat zuiver in het drukriool zit (alleen mechanische leidingen, geen
        vrijvervalrioolleiding) valt buiten deze toets: het mechanische riool valt buiten
        het checkregister. `notes()` verantwoordt hoeveel er zo overgeslagen zijn. Zie
        issue #130. De telling zelf (`_hulpstuktelling`) blijft de volle populatie, zodat
        TOP-002/003 een zuiver-mechanisch T-stuk nog wel als geldig strengeinde zien.
        """
        dataset = context.dataset
        zuiver_mechanisch = zuiver_mechanische_knopen(context)
        for aansluiting in _hulpstuktelling(context).telbaar:
            if aansluiting.node.uri in zuiver_mechanisch:
                continue
            if aansluiting.richtingen == aansluiting.verwacht:
                continue
            if (aansluiting.richtingen > aansluiting.verwacht) != self.te_veel:
                continue
            buren = ", ".join(
                (dataset.nodes[uri].label or uri) if uri in dataset.nodes else uri
                for uri in aansluiting.buren
            )
            los = (
                f", plus {getal(aansluiting.losse_einden, 'streng', 'strengen')} met een los eind"
                if aansluiting.losse_einden
                else ""
            )
            soort = dataset.beheerobjecttype(aansluiting.node.uri) or "Hulpstuk"
            yield self.finding(
                context,
                aansluiting.node.uri,
                aansluiting.node.label,
                f"{soort} verbindt {getal(aansluiting.richtingen, 'richting', 'richtingen')} "
                f"({buren or 'geen buurknoop'}{los}) waar de GWSW-functie "
                f"{aansluiting.functie} er {aansluiting.verwacht} voorschrijft.",
                verwacht=aansluiting.verwacht,
                aangesloten=aansluiting.richtingen,
                losse_einden=aansluiting.losse_einden,
                functie=aansluiting.functie,
                buren=buren,
                strengen=", ".join(aansluiting.strengen),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de hulpstukken die buiten deze toets vielen.

        Twee groepen, om verschillende redenen: de klasse draagt geen functie met een aantal
        leidingen (afsluit- en ontstoppingsstukken), of het hulpstuk zit zuiver in het
        drukriool en valt daarmee buiten het checkregister (issue #130).
        """
        telling = _hulpstuktelling(context)
        zuiver_mechanisch = zuiver_mechanische_knopen(context)
        notities: list[str] = []

        buiten = telling.buiten_per_klasse
        if buiten:
            aantal = sum(buiten.values())
            delen = ", ".join(f"{hoeveel} {klasse}" for klasse, hoeveel in sorted(buiten.items()))
            # Het voorbeeld alleen als er werkelijk een afsluitstuk tussen zit; anders zou
            # het gaan uitleggen wat er niet staat.
            voorbeeld = (
                " Een afsluitstuk met een leiding is precies goed."
                if "Afsluitstuk" in buiten
                else ""
            )
            notities.append(
                f"{getal(aantal, 'hulpstuk', 'hulpstukken')} {vorm(aantal, 'valt', 'vallen')} "
                f"buiten deze toets omdat {vorm(aantal, 'zijn', 'hun')} klasse geen functie met "
                f"een aantal leidingen draagt ({delen}).{voorbeeld}"
            )

        mechanisch = sum(
            1 for aansluiting in telling.telbaar if aansluiting.node.uri in zuiver_mechanisch
        )
        if mechanisch:
            hoeveel = getal(
                mechanisch, "zuiver-mechanisch hulpstuk", "zuiver-mechanische hulpstukken"
            )
            notities.append(
                f"{hoeveel} {vorm(mechanisch, 'valt', 'vallen')} buiten deze toets "
                f"(drukriool): {vorm(mechanisch, 'het verbindt', 'ze verbinden')} alleen "
                "mechanische leidingen en geen vrijvervalrioolleiding, en het mechanische riool "
                "valt buiten het checkregister. Zie issue #130."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal hulpstukken met een telbare functie, zonder de zuiver-mechanische."""
        zuiver_mechanisch = zuiver_mechanische_knopen(context)
        return sum(
            1
            for aansluiting in _hulpstuktelling(context).telbaar
            if aansluiting.node.uri not in zuiver_mechanisch
        )


@register
class HulpstukMetTeWeinigAansluitingen(_HulpstukAansluitingen):
    """TOP-022: er ontbreekt een leiding, of het object is geen T-stuk."""

    id = "TOP-022"
    title = "Hulpstuk verbindt minder leidingen dan zijn GWSW-functie voorschrijft"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "leidingen", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ()
    te_veel = False


@register
class HulpstukMetTeVeelAansluitingen(_HulpstukAansluitingen):
    """TOP-023: waarschijnlijk de verkeerde klasse; voor vier bestaat Kruisstuk."""

    id = "TOP-023"
    title = "Hulpstuk verbindt meer leidingen dan zijn GWSW-functie voorschrijft"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "leidingen", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ()
    te_veel = True
