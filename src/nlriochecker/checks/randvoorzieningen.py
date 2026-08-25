"""RVZ-checks: bergbezinkvoorzieningen, overstorten en drempels.

Hoe overstorten in een export verschijnen ligt niet vast; het checkregister noemde
dat als open punt 6, inmiddels afgehandeld op grond van wat hieronder staat.
Empirisch op de De Wolden en Hoogeveen-export (zie
docs/beslislog.md): overstorten staan er als `Overstortput` met een
`Overstortleiding` eraan. Losse `Overstortdrempel`-onderdelen met `Drempelniveau`
en `Drempelbreedte` komen er niet in voor, terwijl het GWSW-voorbeeldbestand ze wel
kent. Deze module leest daarom beide vormen, en meldt in de toelichting welke ze in
deze dataset heeft aangetroffen. RVZ-002 en RVZ-003 melden dat per overstortput: een
put zonder geregistreerd drempelniveau of zonder geregistreerde drempelbreedte, ook
als het drempelonderdeel zelf ontbreekt.

Een *externe* overstort loost op oppervlaktewater en heeft een overstortleiding naar
buiten; een *interne* overstort verbindt twee compartimenten binnen dezelfde put.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar

from nlriochecker import taal
from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.selectie import (
    bergbezinkleidingen,
    bergbezinkvoorzieningen,
    oppervlaktewaterobjecten,
    overstortleidingen,
    overstortputten,
    vrijvervalrioolleidingen,
)
from nlriochecker.checks.verbanden import (
    aansluitingen,
    deelstelsel_ids,
    netwerkdelen,
)
from nlriochecker.dataset import Conduit, Node, part_holders_of


@dataclass(frozen=True)
class Drempel:
    """Een overstortdrempel met haar geregistreerde kenmerken."""

    uri: str
    label: str
    niveau: float | None
    breedte: float | None
    put_uri: str | None


def bbb_notitie(context: CheckContext) -> list[str]:
    """Meldt of er bergbezinkvoorzieningen zijn en wat er buiten de toets valt."""
    knopen = bergbezinkvoorzieningen(context)
    riolen = bergbezinkleidingen(context)
    notities: list[str] = []
    if not knopen:
        klassen = ", ".join(context.config.klassen.bergbezinkvoorziening) or "geen"
        notities.append(
            f"{context.scope_in_woorden().capitalize()} bevat geen enkele "
            f"bergbezinkvoorziening van de geconfigureerde klassen ({klassen}); er is niets "
            "getoetst."
        )
    if riolen:
        notities.append(
            f"{len(riolen)} bergbezinkriolen staan als leiding geregistreerd en niet als "
            "bouwwerk. Deze check redeneert over de voorziening als knoop in het netwerk "
            "(aanvoer, lediging, nooduitlaat) en laat die leidingen buiten beschouwing; "
            f"het gaat om: {', '.join(sorted(conduit.label for conduit in riolen)[:10])}."
        )
    return notities


def drempels_per_put(context: CheckContext) -> dict[str, list[Drempel]]:
    """De overstortdrempels, gegroepeerd per put waar ze deel van uitmaken.

    Een put kan meer dan een drempel hebben (twee compartimenten, een dubbele
    overstort). Alleen de laatste bewaren zou een te lage drempel op de andere
    stilzwijgend laten passeren.
    """
    return context.cached("rvz:drempels", lambda: _bouw_drempels(context))


def alle_drempels(context: CheckContext) -> list[Drempel]:
    """Alle drempels die aan een put gekoppeld zijn."""
    return [drempel for groep in drempels_per_put(context).values() for drempel in groep]


def _bouw_drempels(context: CheckContext) -> dict[str, list[Drempel]]:
    """Loopt de Overstortdrempel-objecten langs en koppelt ze aan hun put."""
    dataset = context.dataset
    wortels = context.config.klassen.netwerkknopen
    gevonden: dict[str, list[Drempel]] = {}

    gezien: set[str] = set()
    for wortel in context.config.klassen.drempel:
        for subject in dataset.subjects_of_class(wortel):
            uri = str(subject)
            if uri in gezien:
                continue
            gezien.add(uri)
            niveau = _waarde(context, subject, "Drempelniveau")
            breedte = _waarde(context, subject, "Drempelbreedte")
            put_uri = None
            for houder in part_holders_of(dataset.graph, subject):
                put_uri = dataset.resolve_network_node(str(houder), wortels)
                if put_uri is not None:
                    break
            if put_uri is None:
                continue
            gevonden.setdefault(put_uri, []).append(
                Drempel(
                    uri=uri,
                    label=_label(context, subject) or uri,
                    niveau=niveau,
                    breedte=breedte,
                    put_uri=put_uri,
                )
            )
    return gevonden


def _waarde(context: CheckContext, subject, kenmerk: str) -> float | None:
    """De numerieke waarde van een kenmerk dat aan dit object hangt."""
    for aspect in context.dataset.onderdeel_aspecten(str(subject)):
        if aspect.kind == kenmerk:
            return aspect.number
    return None


def _label(context: CheckContext, subject) -> str:
    """Het rdfs:label van een object in de graaf."""
    return context.dataset.onderdeel_label(str(subject)) or ""


def drempelnotitie(context: CheckContext) -> list[str]:
    """Beschrijft welke drempelgegevens deze dataset bevat."""
    drempels = alle_drempels(context)
    if not drempels:
        return [
            f"{context.scope_in_woorden().capitalize()} bevat geen enkel "
            "`Overstortdrempel`-object; er is dus geen drempelniveau en geen "
            "drempelbreedte om op te toetsen. Nul bevindingen betekent hier niet dat het "
            "in orde is."
        ]
    zonder_niveau = sum(1 for drempel in drempels if drempel.niveau is None)
    notities = [
        f"{len(drempels)} overstortdrempels gevonden, verdeeld over "
        f"{len(drempels_per_put(context))} putten."
    ]
    if zonder_niveau:
        notities.append(f"{zonder_niveau} daarvan hebben geen `Drempelniveau`.")
    return notities


def _stelseldelen(context: CheckContext) -> list[set[str]]:
    """De samenhangende delen van het vrijvervalnetwerk, als knoopverzamelingen.

    Een gedeelde afleiding met de NET-checks: RVZ-006 en NET-001 melden over
    hetzelfde deelstelsel, en dat kan alleen als ze het op dezelfde manier
    afbakenen.
    """
    return netwerkdelen(context)


def _gemengde_strengen_van(context: CheckContext, knopen: set[str]) -> list[Conduit]:
    """De gemengde strengen binnen dit deel van het netwerk, op URI gesorteerd.

    "Gemengd" is geen eigen GWSW-object maar een eigenschap van de leiding
    (`GemengdRiool` en haar subklassen, via `[klassen] stelseltypen`). Deze strengen
    zijn dus de dragers van een gebrek aan het deelstelsel als geheel: RVZ-006 meldt
    op elk van hen (issue #75). De volgorde is die van de URI, zodat twee runs op
    dezelfde data dezelfde meldingen in dezelfde volgorde opleveren.
    """
    index = aansluitingen(context, "vrijvervalleiding")
    klassen = context.config.klassen
    gevonden: dict[str, Conduit] = {}
    for knoop in knopen:
        for conduit in index.strengen(knoop):
            if klassen.stelseltype(conduit.types, context.dataset.closure) == "gemengd":
                gevonden[conduit.uri] = conduit
    return [gevonden[uri] for uri in sorted(gevonden)]


def _gemengde_strengen(context: CheckContext) -> list[Conduit]:
    """Alle gemengde vrijvervalstrengen: de populatie waarover RVZ-006 oordeelt."""
    klassen = context.config.klassen
    return [
        conduit
        for conduit in vrijvervalrioolleidingen(context)
        if klassen.stelseltype(conduit.types, context.dataset.closure) == "gemengd"
    ]


def _afvoereindpunten(context: CheckContext) -> set[str]:
    """De knopen die als afvoereindpunt gelden: gemaal of overnamepunt.

    Dezelfde klassen als NET-001 gebruikt (`klassen.afvoer_eindpunt`), zodat de twee
    checks over hetzelfde begrip oordelen. `of_class` sluit de subklassen in, dus
    `Gemaal` dekt de 893 `Rioolgemaal` van De Wolden zonder ze los op te sommen. Een
    `Pompunit` telt sinds issue #73 niet mee: dat is een overdrachtspunt naar de
    drukriolering, geen einde van de afvoer (BO-55).
    """
    dataset = context.dataset
    return {
        uri for wortel in context.config.klassen.afvoer_eindpunt for uri in dataset.of_class(wortel)
    }


def _rvz006_gebrek(heeft_overstort: bool, heeft_eindpunt: bool) -> str:
    """De deelreden voor RVZ-006: welke van de twee eisen het deelstelsel mist."""
    zonder_overstort = "zonder enige externe overstort of bergbezinkvoorziening"
    zonder_eindpunt = "zonder afvoereindpunt (gemaal of overnamepunt)"
    if not heeft_overstort and not heeft_eindpunt:
        return f"{zonder_overstort} en {zonder_eindpunt}"
    if not heeft_overstort:
        return zonder_overstort
    return zonder_eindpunt


@register
class RandvoorzieningNietAangesloten(Check):
    """RVZ-001: een randvoorziening die topologisch nergens op uitkomt."""

    id = "RVZ-001"
    title = "Randvoorziening (BBB, overstortput) topologisch niet aangesloten op het netwerk"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("bergbezinkvoorzieningen", "overstortputten")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt overstortputten en BBB's zonder enige aangesloten streng.

        Dit is de geometrisch-topologische variant: er wordt gekeken of er
        werkelijk een streng op uitkomt. De administratieve koppeling dekt de
        nulmeting al.
        """
        index = aansluitingen(context)
        for node in (*overstortputten(context), *bergbezinkvoorzieningen(context)):
            if index.strengen(node.uri):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                "Deze randvoorziening heeft geen enkele aangesloten streng.",
                soort=_soortnaam(context, node),
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal randvoorzieningen."""
        return len(overstortputten(context)) + len(bergbezinkvoorzieningen(context))


class _OverstortZonderDrempelkenmerk(Check):
    """Basis voor RVZ-002 en RVZ-003: een overstortput waarvan geen enkele drempel
    het gevraagde kenmerk draagt -- ook als er helemaal geen drempelonderdeel is.

    De nulmetingvorm `Overstortput_Overstortdrempel_card` meldt het ontbreken van het
    onderdeel zelf al; die overlap is bewust (BO-26): het register vraagt naar de
    geregistreerde waarde, en `toets` moet ook zonder `--shacl` iets zien.
    """

    kenmerk: ClassVar[str] = ""
    omschrijving: ClassVar[str] = ""

    @abstractmethod
    def _kenmerkwaarde(self, drempel: Drempel) -> float | None:
        """De waarde van het gevraagde kenmerk op deze drempel."""

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke overstortput zonder geregistreerd kenmerk op een van haar drempels."""
        per_put = drempels_per_put(context)
        for node in overstortputten(context):
            groep = per_put.get(node.uri, [])
            if any(self._kenmerkwaarde(drempel) is not None for drempel in groep):
                continue
            # Het voltooid deelwoord achteraan: `drempelniveau` is onzijdig en
            # `drempelbreedte` niet, dus "een geregistreerd {omschrijving}" klopt maar
            # voor een van de twee checks.
            if len(groep) == 1:
                tekst = (
                    "De enige overstortdrempel van deze put heeft geen "
                    f"{self.omschrijving} (`{self.kenmerk}`) geregistreerd."
                )
            elif groep:
                tekst = (
                    f"Geen van de {len(groep)} overstortdrempels van deze put heeft een "
                    f"{self.omschrijving} (`{self.kenmerk}`) geregistreerd."
                )
            else:
                tekst = (
                    "Deze overstortput heeft geen enkel `Overstortdrempel`-onderdeel, en dus "
                    f"ook geen {self.omschrijving}."
                )
            yield self.finding(context, node.uri, node.label, tekst, drempels=len(groep))

    def notes(self, context: CheckContext) -> list[str]:
        """Zegt hoeveel putten geen drempel hebben en dat de nulmeting dat ook meldt."""
        per_put = drempels_per_put(context)
        putten = overstortputten(context)
        zonder = sum(1 for node in putten if not per_put.get(node.uri))
        notities = [
            f"Bekeken: {taal.getal(len(putten), 'overstortput', 'overstortputten')} in "
            f"{context.scope_in_woorden()} "
            f"({', '.join(context.config.klassen.overstortput)})."
        ]
        if zonder:
            notities.append(
                f"{zonder} daarvan {taal.vorm(zonder, 'staat', 'staan')} zonder enig "
                "`Overstortdrempel`-onderdeel geregistreerd; "
                "de nulmetingvorm `Overstortput_Overstortdrempel_card` meldt dat ook. De "
                "overlap is bewust: deze check toetst de geregistreerde waarde en werkt ook "
                "zonder nulmeting."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal overstortputten."""
        return len(overstortputten(context))


@register
class OverstortZonderDrempelniveau(_OverstortZonderDrempelkenmerk):
    """RVZ-002: overstortput zonder geregistreerd drempelniveau."""

    id = "RVZ-002"
    title = "Overstort zonder geregistreerde drempelhoogte"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("overstortputten",)
    kenmerken = ("Drempelbreedte", "Drempelniveau")
    kenmerk = "Drempelniveau"
    omschrijving = "drempelniveau"

    def _kenmerkwaarde(self, drempel: Drempel) -> float | None:
        """Het geregistreerde drempelniveau."""
        return drempel.niveau


@register
class OverstortZonderDrempelbreedte(_OverstortZonderDrempelkenmerk):
    """RVZ-003: overstortput zonder geregistreerde drempelbreedte."""

    id = "RVZ-003"
    title = "Overstort zonder geregistreerde drempelbreedte"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("overstortputten",)
    kenmerken = ("Drempelbreedte", "Drempelniveau")
    kenmerk = "Drempelbreedte"
    omschrijving = "drempelbreedte"

    def _kenmerkwaarde(self, drempel: Drempel) -> float | None:
        """De geregistreerde drempelbreedte."""
        return drempel.breedte


@register
class ExterneOverstortZonderWater(Check):
    """RVZ-004: een externe overstort zonder ontvangend oppervlaktewater in de buurt."""

    id = "RVZ-004"
    title = "Externe overstort zonder ontvangend oppervlaktewater binnen X m"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("oppervlaktewaterobjecten", "overstortputten")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt overstortputten zonder GWSW-oppervlaktewater binnen de afstand.

        Het gaat hier om oppervlaktewater dat in de GWSW-dataset zelf staat.
        EXT-007 doet dezelfde toets op de BGT-waterdelen; die bron dekt alleen het
        studiegebied en staat daarom in `extern.py`.
        """
        afstand = context.config.drempels.overstort_water_afstand_m
        wateren = _watergeometrieen(context)
        if not wateren:
            return

        for node in overstortputten(context):
            if node.point is None:
                continue
            if any(water.distance(node.point) <= afstand for water in wateren):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Geen oppervlaktewater uit de GWSW-dataset binnen {afstand:g} m van deze "
                "overstort.",
                afstand_m=afstand,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt of er oppervlaktewater in de dataset staat."""
        if _watergeometrieen(context):
            return [
                f"Getoetst op {len(_watergeometrieen(context))} oppervlaktewaterobjecten uit "
                "de GWSW-dataset zelf. EXT-007 doet dezelfde toets op de BGT-waterdelen."
            ]
        return [
            f"{context.scope_in_woorden().capitalize()} bevat geen enkel "
            "`Oppervlaktewater`-object; er is niets om de afstand tot te meten. EXT-007 "
            "doet dezelfde toets op de BGT-waterdelen, maar die dekken alleen het "
            "studiegebied."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal overstortputten."""
        return len(overstortputten(context))


@register
class OverstortOpVerkeerdStelsel(Check):
    """RVZ-005: een overstort in een hemelwater- of infiltratiestelsel."""

    id = "RVZ-005"
    title = "Overstort aangesloten op een hemelwater- of IT-stelsel"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("overstortputten", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt overstorten waarvan de aanvoer hemelwater of infiltratie is.

        Een overstort hoort bij een gemengd of vuilwaterstelsel: die moeten bij
        hevige neerslag hun overschot kwijt. Hemelwater en infiltratie lozen per
        definitie al op oppervlaktewater of bodem; een overstort daarin duidt op
        een verkeerd getypeerd stelsel of een verkeerd getypeerde put.
        """
        index = aansluitingen(context, "vrijvervalleiding")
        klassen = context.config.klassen
        verdacht = {"hemelwater", "infiltratie"}

        for node in overstortputten(context):
            soorten = {
                soort
                for conduit in index.strengen(node.uri)
                if (soort := klassen.stelseltype(conduit.types, context.dataset.closure))
                is not None
                and soort != "overstort"
            }
            if not soorten or not soorten <= verdacht:
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Deze overstort hangt uitsluitend aan strengen van type "
                f"{', '.join(sorted(soorten))}.",
                stelseltypen=sorted(soorten),
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal overstortputten."""
        return len(overstortputten(context))


@register
class GemengdDeelstelselZonderOverstort(Check):
    """RVZ-006: een gemengd deelstelsel zonder overstort/BBB of zonder afvoereindpunt."""

    id = "RVZ-006"
    title = "Gemengd deelstelsel zonder externe overstort/BBB of zonder afvoereindpunt"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY
    rollen = ("bergbezinkvoorzieningen", "overstortputten", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt gemengde deelstelsels zonder overstort of zonder afvoereindpunt.

        Een gemengd stelsel moet zijn vuilwater ergens kwijt kunnen -- via een
        externe overstort/BBB bij hoogwater, en via een afvoereindpunt (gemaal of
        overnamepunt) in de gewone toestand. Ontbreekt een van beide, dan is het
        stelsel onvolledig geregistreerd; de melding noemt welke eis faalt.

        De bevinding hangt per gemengde streng van het falende deel (issue #75) en
        niet meer op de lexicografisch eerste knoop ervan. Er is geen GWSW-object
        "gemengd stelsel" om het gebrek aan te hangen -- gemengd volgt uit het
        leidingtype -- dus de gemengde strengen zijn de dragers, net zoals NET-001
        een subsysteem dat iets mist per streng meldt. De gedeelde `cluster_id`
        houdt zichtbaar dat het om één deelstelsel gaat en niet om losse gebreken.
        """
        randvoorzieningen = {node.uri for node in overstortputten(context)}
        randvoorzieningen |= {node.uri for node in bergbezinkvoorzieningen(context)}
        afvoereindpunten = _afvoereindpunten(context)
        clusters = deelstelsel_ids(context)

        for deel in _stelseldelen(context):
            strengen = _gemengde_strengen_van(context, deel)
            if not strengen:
                continue
            heeft_overstort = bool(deel & randvoorzieningen)
            heeft_eindpunt = bool(deel & afvoereindpunten)
            if heeft_overstort and heeft_eindpunt:
                continue
            cluster = clusters.get(min(deel), "")
            for conduit in strengen:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Ligt in een gemengd deelstelsel van {len(deel)} knopen "
                    f"{_rvz006_gebrek(heeft_overstort, heeft_eindpunt)}.",
                    knopen_in_deelstelsel=len(deel),
                    gemengde_strengen=len(strengen),
                    cluster_id=cluster,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Legt uit waaraan de melding hangt en waar het gebrek werkelijk zit."""
        return [
            "Het gebrek zit in het deelstelsel als geheel; de bevinding hangt aan elke "
            "gemengde streng ervan, want een gemengd stelsel is geen GWSW-object. De "
            "bevindingen van hetzelfde deelstelsel dragen dezelfde `cluster_id`."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal gemengde vrijvervalstrengen."""
        return len(_gemengde_strengen(context))


class _BbbKenmerk(Check):
    """Basis voor de checks op ontbrekende BBB-kenmerken."""

    kenmerken: ClassVar[tuple[str, ...]] = ()
    ontbreekt: str = ""

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke BBB waarvan het gevraagde kenmerk ontbreekt."""
        for node in bergbezinkvoorzieningen(context):
            if self.aanwezig(context, node):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                self.ontbreekt,
                soort=_soortnaam(context, node),
            )

    def aanwezig(self, context: CheckContext, node: Node) -> bool:
        """Geeft aan of het gevraagde kenmerk geregistreerd is."""
        return any(node.aspect(kenmerk) is not None for kenmerk in self.kenmerken)

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt of er uberhaupt BBB's in deze dataset staan."""
        return bbb_notitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal bergbezinkvoorzieningen."""
        return len(bergbezinkvoorzieningen(context))


@register
class BbbZonderBerging(_BbbKenmerk):
    """RVZ-007: een BBB zonder bergingsinhoud of afmetingen."""

    id = "RVZ-007"
    title = "BBB zonder geregistreerde bergingsinhoud of afmetingen"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("bergbezinkleidingen", "bergbezinkvoorzieningen")
    kenmerken = (
        "Inhoud",
        "NettoBerging",
        "NuttigeBerging",
        "BreedteBouwwerk",
        "LengteBouwwerk",
        "HoogteBouwwerk",
    )
    ontbreekt = "Deze bergbezinkvoorziening heeft geen bergingsinhoud en geen afmetingen."


@register
class BbbZonderLediging(Check):
    """RVZ-008: een BBB zonder ledigingsvoorziening of ledigingsroute."""

    id = "RVZ-008"
    title = "BBB zonder ledigingsvoorziening of ledigingsroute terug naar het stelsel"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("bergbezinkleidingen", "bergbezinkvoorzieningen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt BBB's zonder geregistreerde lediging.

        Het register merkt op dat lediging in de praktijk vaak via een gemaal
        loopt; dat gemaal valt buiten scope. Getoetst wordt alleen of er *iets*
        geregistreerd staat: een ledigingsvoorziening als onderdeel, of een streng
        die uit de BBB terugvoert het stelsel in.
        """
        index = aansluitingen(context)
        ledigingsklassen = context.config.klassen.ledigingsvoorziening

        for node in bergbezinkvoorzieningen(context):
            if self._heeft_voorziening(context, node, ledigingsklassen):
                continue
            uit = [
                conduit
                for conduit in index.strengen(node.uri)
                if index.knopen(conduit.uri)[0] == node.uri
            ]
            if uit:
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                "Geen ledigingsvoorziening als onderdeel en geen afvoerende streng terug "
                "het stelsel in.",
                soort=_soortnaam(context, node),
            )

    def _heeft_voorziening(self, context: CheckContext, node: Node, klassen: list[str]) -> bool:
        """Geeft aan of de BBB een ledigingsvoorziening als onderdeel heeft."""
        dataset = context.dataset
        for deel in dataset.onderdelen(node.uri):
            if any(dataset.graph_is_a(deel, wortel) for wortel in klassen):
                return True
        return False

    def notes(self, context: CheckContext) -> list[str]:
        """Legt de scopegrens vast."""
        return [
            "Alleen de registratie is getoetst, niet of de lediging werkt: het gemaal dat de "
            "lediging in de praktijk verzorgt valt buiten de scope van het register.",
            *bbb_notitie(context),
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal bergbezinkvoorzieningen."""
        return len(bergbezinkvoorzieningen(context))


@register
class BbbZonderNooduitlaat(Check):
    """RVZ-009: een BBB zonder nooduitlaat of externe overstortdrempel."""

    id = "RVZ-009"
    title = "BBB zonder nooduitlaat of externe overstortdrempel"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("bergbezinkleidingen", "bergbezinkvoorzieningen", "overstortleidingen")
    kenmerken = ("Drempelbreedte", "Drempelniveau")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt BBB's zonder overstortdrempel en zonder overstortleiding."""
        drempels = drempels_per_put(context)
        index = aansluitingen(context)
        overstort_uris = {conduit.uri for conduit in overstortleidingen(context)}

        for node in bergbezinkvoorzieningen(context):
            if node.uri in drempels:
                continue
            if any(conduit.uri in overstort_uris for conduit in index.strengen(node.uri)):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                "Geen overstortdrempel als onderdeel en geen overstortleiding eraan; er is "
                "geen nooduitlaat geregistreerd.",
                soort=_soortnaam(context, node),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke vormen van nooduitlaat herkend worden."""
        return [*drempelnotitie(context), *bbb_notitie(context)]

    def examined(self, context: CheckContext) -> int:
        """Het aantal bergbezinkvoorzieningen."""
        return len(bergbezinkvoorzieningen(context))


@register
class InterneOverstortZelfdeStelseltype(Check):
    """RVZ-010: een interne overstort tussen twee gelijke stelseltypen."""

    id = "RVZ-010"
    title = "Interne overstort waarbij beide zijden hetzelfde stelseltype hebben"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("overstortleidingen", "vrijvervalrioolleidingen")
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt het stelseltype aan weerszijden van een overstortleiding.

        Een overstort brengt water van het ene stelsel naar het andere, of naar
        buiten. Loopt hij tussen twee strengen van hetzelfde type, dan overstort
        hij op zichzelf en is er iets mis met de typering.
        """
        index = aansluitingen(context, "vrijvervalleiding")
        klassen = context.config.klassen
        dataset = context.dataset

        for conduit in overstortleidingen(context):
            begin, eind = index.knopen(conduit.uri)
            if begin is None or eind is None:
                continue
            soorten: list[set[str]] = []
            for knoop in (begin, eind):
                buren = {
                    soort
                    for buur in index.strengen(knoop)
                    if buur.uri != conduit.uri
                    and (soort := klassen.stelseltype(buur.types, dataset.closure)) is not None
                    and soort != "overstort"
                }
                soorten.append(buren)
            if not soorten[0] or not soorten[1]:
                continue
            if soorten[0] != soorten[1]:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Aan beide zijden ligt uitsluitend stelseltype "
                f"{', '.join(sorted(soorten[0]))}; deze overstort stort op zijn eigen "
                "stelseltype over.",
                stelseltypen=sorted(soorten[0]),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoe interne overstorten in deze dataset herkend worden."""
        aantal = len(overstortleidingen(context))
        if not aantal:
            klassen = ", ".join(context.config.klassen.overstortleiding) or "geen"
            return [
                f"{context.scope_in_woorden().capitalize()} bevat geen enkele "
                f"overstortleiding van de geconfigureerde klassen ({klassen}); er is niets "
                "getoetst."
            ]
        return [
            f"{aantal} overstortleidingen getoetst. Een overstort tussen compartimenten "
            "binnen dezelfde put (`Overstortdrempel` met begin- en eindpunt op twee "
            "compartimenten) komt hier alleen in beeld als de export die als leiding heeft "
            "opgevoerd."
        ]

    def examined(self, context: CheckContext) -> int:
        """Het aantal overstortleidingen."""
        return len(overstortleidingen(context))


@register
class OnvoldoendeWaking(Check):
    """RVZ-011: te weinig ruimte tussen overstortdrempel en dekselniveau."""

    id = "RVZ-011"
    title = "Waking overstortdrempel kleiner dan 0,40 m (dekselniveau minus drempelniveau)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ()
    kenmerken = ("Drempelbreedte", "Drempelniveau", "Maaiveldhoogte", "Putdekselniveau")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Berekent de waking per drempel en toetst die op het minimum."""
        minimum = context.config.drempels.minimale_waking_m
        dataset = context.dataset

        for put_uri, groep in drempels_per_put(context).items():
            node = dataset.nodes.get(put_uri)
            if node is None:
                continue
            boven = node.bovenkant
            if boven is None:
                continue
            for drempel in groep:
                if drempel.niveau is None:
                    continue
                waking = boven - drempel.niveau
                if waking >= minimum:
                    continue
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"Waking {waking:.3f} m tussen drempel {drempel.label!r} "
                    f"({drempel.niveau:.3f} m NAP) en het {_bovenkant_bron(node)} "
                    f"({boven:.3f} m NAP), onder het minimum van {minimum:g} m.",
                    waking_m=round(waking, 3),
                    drempel=drempel.label,
                    drempelniveau=drempel.niveau,
                    bovenkant=boven,
                    minimum_m=minimum,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt of er drempelniveaus in de dataset staan."""
        return drempelnotitie(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal drempels dat aan een put hangt."""
        return len(alle_drempels(context))


def _bovenkant_bron(node: Node) -> str:
    """Waar het bovenkantniveau vandaan komt: dekselniveau of maaiveld."""
    return "dekselniveau" if node.dekselniveau is not None else "maaiveldhoogte"


def _soortnaam(context: CheckContext, node: Node) -> str:
    """De korte GWSW-klassenaam van een object."""
    types = sorted(soort.rsplit("/", 1)[-1] for soort in node.types)
    return types[0] if types else "onbekend"


def _watergeometrieen(context: CheckContext) -> list:
    """De geometrieen van de oppervlaktewaterobjecten uit de GWSW-dataset."""
    return context.cached("rvz:water", lambda: _bouw_watergeometrieen(context))


def _bouw_watergeometrieen(context: CheckContext) -> list:
    """Verzamelt punt- en lijngeometrie van alle oppervlaktewaterobjecten.

    De selectie levert de objecten van de klasse, ook die zonder geometrie; het
    filteren hoort hier, want een object zonder punt of lijn kan deze structuur niet
    gebruiken.
    """
    gevonden = []
    for object_ in oppervlaktewaterobjecten(context):
        meetkunde = object_.point if isinstance(object_, Node) else object_.line
        if meetkunde is not None:
            gevonden.append(meetkunde)
    return gevonden
