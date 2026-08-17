"""ADM-checks: administratieve en referentiele consistentie.

ADM-001, ADM-004 en ADM-005 zijn geschrapt: de nulmeting dekt ze aantoonbaar. Wat
overblijft zijn de dingen die de SHACL-meting niet ziet, hetzij omdat de fout al in
de RDF-conversie verdwijnt (ADM-002), hetzij omdat het GWSW er geen regel voor kent
(ADM-003, ADM-006 t/m ADM-009).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date

from rdflib import RDF, URIRef

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.verbanden import aansluitingen, objecten_van_klassen
from nlriochecker.dataset import HAS_CONNECTION, HAS_PART


def _putten(context: CheckContext):
    """De putten van het netwerk."""
    return context.cached(
        "adm:putten",
        lambda: objecten_van_klassen(context, context.config.klassen.netwerkknopen, "nodes"),
    )


def _strengen(context: CheckContext):
    """Alle leidingen van de dataset."""
    return context.cached(
        "adm:strengen",
        lambda: objecten_van_klassen(context, context.config.klassen.streng, "conduits"),
    )


@register
class NietUniekeIdentificatie(Check):
    """ADM-002: twee objecten met hetzelfde identificerende label."""

    id = "ADM-002"
    title = "Niet-unieke identificaties van putten of strengen"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    # Dubbele identificaties kunnen overal in de export zitten, niet alleen in de
    # analyseset; deze check draait daarom altijd op de volledige export.
    volledig_bereik = True

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt labels die aan meer dan een object hangen.

        Het register wil deze toets eigenlijk op de bronexport draaien, voor de
        OroX-conversie: twee rijen met hetzelfde ID smelten in RDF geruisloos samen
        tot een subject en zijn daarna niet meer te vinden. Wat hier wel te zien is,
        is het omgekeerde geval: twee verschillende subjecten met hetzelfde
        `rdfs:label`. De toelichting zegt welke helft dit is.
        """
        for soort, objecten in (("put", _putten(context)), ("streng", _strengen(context))):
            per_label: dict[str, list[str]] = {}
            for object_ in objecten:
                if object_.label:
                    per_label.setdefault(object_.label, []).append(object_.uri)
            for label, uris in per_label.items():
                if len(uris) < 2:
                    continue
                for uri in uris:
                    yield self.finding(
                        context,
                        uri,
                        label,
                        f"Er zijn {len(uris)} {soort}en met de identificatie {label!r}.",
                        aantal=len(uris),
                        soort=soort,
                    )

    def notes(self, context: CheckContext) -> list[str]:
        """Legt vast welk deel van ADM-002 hier niet uitgevoerd kan worden."""
        return [
            "Deze check draait op de OroX-dataset, niet op de bronexport. Duplicaat-ID's "
            "die in de RDF-conversie tot een subject zijn samengesmolten zijn hier per "
            "definitie niet meer zichtbaar; alleen verschillende subjecten met hetzelfde "
            "`rdfs:label` komen naar voren. Voor de andere helft is een toets op de "
            "Brutis- of Kikker-export nodig, en die is hier niet beschikbaar."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten plus strengen."""
        return len(_putten(context)) + len(_strengen(context))


@register
class NaamgevingWijktAfVanConventie(Check):
    """ADM-003: een identificatie die niet aan het projectpatroon voldoet."""

    id = "ADM-003"
    title = "Naamgeving knopen en strengen wijkt af van conventie (patroon configureerbaar)"
    severity = Severity.ERROR
    dimension = Dimension.COMPLIANCE

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst de labels tegen de regex-patronen uit de projectconfig.

        Zonder patroon draait de check niet. Een verzonnen conventie zou elke
        dataset afkeuren; het register noemt het patroon expliciet projectafhankelijk.
        """
        naamgeving = context.config.naamgeving
        for patroon, objecten, soort in (
            (naamgeving.putpatroon, _putten(context), "put"),
            (naamgeving.strengpatroon, _strengen(context), "streng"),
        ):
            if patroon is None:
                continue
            regex = re.compile(patroon)
            for object_ in objecten:
                if regex.match(object_.label or ""):
                    continue
                yield self.finding(
                    context,
                    object_.uri,
                    object_.label,
                    f"De {soort}identificatie {object_.label!r} voldoet niet aan het patroon "
                    f"{patroon!r}.",
                    patroon=patroon,
                    soort=soort,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke patronen gelden, of dat er geen zijn."""
        naamgeving = context.config.naamgeving
        gezet = [
            f"{naam}: `{patroon}`"
            for naam, patroon in (
                ("putten", naamgeving.putpatroon),
                ("strengen", naamgeving.strengpatroon),
            )
            if patroon is not None
        ]
        if not gezet:
            return [
                "Deze check is niet gedraaid: er is geen naamgevingspatroon geconfigureerd "
                "(`naamgeving.putpatroon` en `naamgeving.strengpatroon`). De conventie is "
                "projectafhankelijk; een verzonnen patroon zou elke dataset afkeuren."
            ]
        return [f"Getoetst tegen {', '.join(gezet)}."]

    def examined(self, context: CheckContext) -> int:
        """Het aantal objecten waarvoor een patroon geconfigureerd is."""
        naamgeving = context.config.naamgeving
        aantal = 0
        if naamgeving.putpatroon is not None:
            aantal += len(_putten(context))
        if naamgeving.strengpatroon is not None:
            aantal += len(_strengen(context))
        return aantal


@register
class VervallenObjectInActiefNetwerk(Check):
    """ADM-006: een vervallen of nog gepland object dat wel meedoet in het netwerk."""

    id = "ADM-006"
    title = "Vervallen of geplande objecten die topologisch meedoen in het actieve netwerk"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt objecten met een einddatum in het verleden of een begindatum in de toekomst.

        Het GWSW kent `Begindatum` en `Einddatum` per object. Een object waarvan de
        einddatum verstreken is hoort niet meer in het actieve netwerk te zitten, en
        een object dat nog moet komen ook niet.
        """
        vandaag = date.today()
        index = aansluitingen(context)
        dataset = context.dataset

        for object_ in (*_putten(context), *_strengen(context)):
            reden = self._reden(object_, vandaag)
            if reden is None:
                continue
            if not self._doet_mee(object_, index, dataset):
                continue
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                reden,
                begindatum=_iso(object_.date("Begindatum")),
                einddatum=_iso(object_.date("Einddatum")),
            )

    def _reden(self, object_, vandaag: date) -> str | None:
        """De reden waarom dit object niet actief hoort te zijn, of None."""
        einde = object_.date("Einddatum")
        if einde is not None and einde < vandaag:
            return f"Einddatum {einde.isoformat()} is verstreken, maar het object doet mee."
        begin = object_.date("Begindatum")
        if begin is not None and begin > vandaag:
            return f"Begindatum {begin.isoformat()} ligt in de toekomst, maar het object doet mee."
        return None

    def _doet_mee(self, object_, index, dataset) -> bool:
        """Geeft aan of dit object topologisch in het netwerk hangt."""
        if object_.uri in dataset.nodes:
            return bool(index.strengen(object_.uri))
        begin, eind = index.knopen(object_.uri)
        return begin is not None or eind is not None

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel objecten geen einddatum hebben."""
        objecten = [*_putten(context), *_strengen(context)]
        met_einde = sum(1 for object_ in objecten if object_.date("Einddatum") is not None)
        if met_einde:
            return [f"{met_einde} van de {len(objecten)} objecten hebben een einddatum."]
        return [
            f"Geen van de {len(objecten)} objecten heeft een `Einddatum`. De check kan dan "
            "alleen op een begindatum in de toekomst aanslaan; vervallen objecten zijn in "
            "deze dataset niet als zodanig herkenbaar."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten plus strengen."""
        return len(_putten(context)) + len(_strengen(context))


@register
class PuttypePastNietBijLeiding(Check):
    """ADM-007: een puttype waarvan de bijbehorende aansluiting ontbreekt."""

    id = "ADM-007"
    title = "Puttype past niet bij het type aangesloten leiding"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst de netwerkfunctie van elk puttype tegen de regels uit de config.

        De samenstellingsregels per puttype (welke onderdelen een put mag hebben)
        dekt de nulmeting al. Wat hier getoetst wordt is de netwerkfunctie: heeft
        een overstortput ook werkelijk een overstort in het netwerk?
        """
        dataset = context.dataset
        index = aansluitingen(context)

        for regel in context.config.puttyperegels:
            for uri in dataset.of_class(regel.puttype):
                node = dataset.nodes.get(uri)
                if node is None:
                    continue
                if self._voldoet(context, node, regel, index):
                    continue
                yield self.finding(
                    context,
                    uri,
                    node.label,
                    f"Puttype {regel.puttype} zonder aangesloten of ingebouwde "
                    f"{' of '.join(regel.vereist_een_van)}. {regel.toelichting}".strip(),
                    puttype=regel.puttype,
                    vereist=regel.vereist_een_van,
                )

    def _voldoet(self, context: CheckContext, node, regel, index) -> bool:
        """Geeft aan of de put aan een van de vereiste klassen voldoet."""
        dataset = context.dataset
        for conduit in index.strengen(node.uri):
            if any(dataset.is_a(conduit.uri, wortel) for wortel in regel.vereist_een_van):
                return True
        for deel in dataset.graph.objects(URIRef(node.uri), HAS_PART):
            if any(dataset.is_a(str(deel), wortel) for wortel in regel.vereist_een_van):
                return True
        return False

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke regels gelden."""
        regels = context.config.puttyperegels
        if not regels:
            return [
                "Deze check is niet gedraaid: er zijn geen puttyperegels geconfigureerd "
                "(`puttyperegels`). Welk puttype welke netwerkfunctie hoort te hebben is "
                "een projectafspraak."
            ]
        return [
            "Getoetste regels: "
            + "; ".join(
                f"{regel.puttype} vereist {' of '.join(regel.vereist_een_van)}" for regel in regels
            )
            + "."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten van de geconfigureerde puttypen."""
        dataset = context.dataset
        return len(
            {
                uri
                for regel in context.config.puttyperegels
                for uri in dataset.of_class(regel.puttype)
                if uri in dataset.nodes
            }
        )


@register
class PutonderdelenZonderVerbinding(Check):
    """ADM-008: compartimenten of onderdelen die binnen de put nergens op aansluiten."""

    id = "ADM-008"
    title = "Putcompartimenten of -onderdelen zonder onderlinge verbinding binnen de put"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putten met meerdere onderdelen die niet aan elkaar hangen.

        Een put met twee compartimenten hoort een verbinding tussen die
        compartimenten te hebben: een drempel, een opening of een onderdeel met
        begin- en eindpunt. Ontbreekt die, dan is de put binnenin niet doorlopend.
        """
        dataset = context.dataset

        for node in _putten(context):
            onderdelen = self._onderdelen(context, node)
            if len(onderdelen) < 2:
                continue
            if self._verbonden(context, onderdelen):
                continue
            labels = sorted(
                dataset.nodes[uri].label if uri in dataset.nodes else uri for uri in onderdelen
            )
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Deze put heeft {len(onderdelen)} onderdelen zonder onderlinge verbinding: "
                f"{', '.join(labels)}.",
                onderdelen=labels,
            )

    def _onderdelen(self, context: CheckContext, node) -> list[str]:
        """De compartimenten van een put, als URI's."""
        dataset = context.dataset
        gevonden = []
        for deel in dataset.graph.objects(URIRef(node.uri), HAS_PART):
            uri = str(deel)
            if uri in dataset.nodes and dataset.nodes[uri].orientation is not None:
                gevonden.append(uri)
        return gevonden

    def _verbonden(self, context: CheckContext, onderdelen: list[str]) -> bool:
        """Geeft aan of er tussen deze onderdelen een verbinding geregistreerd is."""
        dataset = context.dataset
        orientaties = {
            orientatie
            for uri in onderdelen
            if uri in dataset.nodes and (orientatie := dataset.nodes[uri].orientation) is not None
        }
        for orientatie in orientaties:
            subject = URIRef(orientatie)
            buren = {str(buur) for buur in dataset.graph.objects(subject, HAS_CONNECTION)}
            buren |= {str(buur) for buur in dataset.graph.subjects(HAS_CONNECTION, subject)}
            # Een verbinding loopt via een begin- of eindpunt van een onderdeel; dat
            # eindpunt hangt met hasPart aan een onderdeelorientatie.
            for buur in buren:
                for houder in dataset.graph.subjects(HAS_PART, URIRef(buur)):
                    andere = self._raakt_ander_onderdeel(dataset, houder, orientaties, orientatie)
                    if andere:
                        return True
                if buur in orientaties:
                    return True
        return False

    def _raakt_ander_onderdeel(self, dataset, houder, orientaties: set[str], eigen: str) -> bool:
        """Geeft aan of deze onderdeelorientatie ook een ander compartiment raakt."""
        for deel in dataset.graph.objects(houder, HAS_PART):
            for buur in dataset.graph.objects(deel, HAS_CONNECTION):
                if str(buur) in orientaties and str(buur) != eigen:
                    return True
            for buur in dataset.graph.subjects(HAS_CONNECTION, deel):
                if str(buur) in orientaties and str(buur) != eigen:
                    return True
        return False

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten meer dan een onderdeel hebben."""
        putten = _putten(context)
        met_delen = sum(1 for node in putten if len(self._onderdelen(context, node)) >= 2)
        if met_delen:
            return [f"{met_delen} van de {len(putten)} putten hebben meer dan een onderdeel."]
        return [
            f"Geen van de {len(putten)} putten heeft meer dan een compartiment; er valt "
            "niets te verbinden en er is dus niets getoetst."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten."""
        return len(_putten(context))


@register
class LeidingAanPutInPlaatsVanCompartiment(Check):
    """ADM-009: een leiding aan de put terwijl er compartimenten zijn."""

    id = "ADM-009"
    title = "Leiding gekoppeld aan de put als geheel waar koppeling aan een compartiment vereist is"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen die aan een gecompartimenteerde put als geheel hangen.

        Heeft een put compartimenten, dan zegt het GWSW dat een leiding aan het
        compartiment gekoppeld hoort te worden en niet aan de put. Alleen dan is
        bekend welk compartiment de leiding bedient.
        """
        dataset = context.dataset
        index = aansluitingen(context)
        wortels = context.config.klassen.netwerkknopen

        for node in _putten(context):
            compartimenten = self._compartimenten(context, node)
            if not compartimenten:
                continue
            for conduit in index.strengen(node.uri):
                for zijde, gekoppeld in (
                    ("beginpunt", conduit.start_node),
                    ("eindpunt", conduit.end_node),
                ):
                    if gekoppeld is None:
                        continue
                    if dataset.resolve_network_node(gekoppeld, wortels) != node.uri:
                        continue
                    if gekoppeld != node.uri:
                        continue
                    yield self.finding(
                        context,
                        conduit.uri,
                        conduit.label,
                        f"Het {zijde} is aan put {node.label!r} als geheel gekoppeld, terwijl "
                        f"die {len(compartimenten)} compartimenten heeft.",
                        zijde=zijde,
                        put=node.label,
                        compartimenten=len(compartimenten),
                    )

    def _compartimenten(self, context: CheckContext, node) -> list[str]:
        """De compartimenten van een put, inclusief subklassen als een pompkelder."""
        dataset = context.dataset
        afsluiting = dataset.closure("Compartiment")
        gevonden = []
        for deel in dataset.graph.objects(URIRef(node.uri), HAS_PART):
            soorten = {str(soort) for soort in dataset.graph.objects(deel, RDF.type)}
            if soorten & afsluiting:
                gevonden.append(str(deel))
        return gevonden

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten compartimenten hebben."""
        putten = _putten(context)
        met = sum(1 for node in putten if self._compartimenten(context, node))
        if met:
            return [f"{met} van de {len(putten)} putten hebben compartimenten."]
        return [
            f"Geen van de {len(putten)} putten heeft compartimenten; elke leiding hoort dan "
            "aan de put zelf te hangen en er is niets getoetst."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten met compartimenten."""
        return sum(1 for node in _putten(context) if self._compartimenten(context, node))


def _iso(waarde: date | None) -> str | None:
    """Een datum als ISO-tekst, of None."""
    return waarde.isoformat() if waarde is not None else None
