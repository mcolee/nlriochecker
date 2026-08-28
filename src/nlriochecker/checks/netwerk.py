"""NET-checks: netwerklogica op de gerichte vrijvervalgraaf."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import networkx as nx
from gwsw_orox_helpers.dataset import Conduit, GwswDataset, part_holders_of

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.selectie import (
    infiltratieleidingen,
    overstortputten,
)
from nlriochecker.checks.verbanden import (
    _bereikbaarheid,
    _eindpunten,
    _Netwerk,
    _netwerk,
    deelstelsel_ids,
    verbonden_knopen,
)
from nlriochecker.taal import getal, vorm


def _bereikbaar_vanaf(context: CheckContext, endpoints: set[str]) -> set[str]:
    """De knopen die stroomafwaarts een van deze eindpunten bereiken.

    Over de bereikbaarheidsgraaf, dus inclusief het mechanische riool als ongerichte
    connectiviteit: een vrijvervalstreng die op een pompput eindigt voert wel degelijk
    af, langs het persnet naar het gemaal erachter (BO-54).

    Een enkele doorloop over de omgekeerde graaf vanaf alle eindpunten tegelijk.
    Per eindpunt afzonderlijk zoeken kost O(eindpunten x graaf): De Wolden en Hoogeveen heeft
    893 gemalen op ruim 20.000 knopen, en dat loopt in de tientallen miljoenen
    stappen. Zo blijft het een enkele O(knopen + kanten)-doorloop.
    """
    if not endpoints:
        return set()

    omgekeerd = _bereikbaarheid(context).reverse(copy=False)
    bereikt = {uri for uri in endpoints if uri in omgekeerd}
    stapel = list(bereikt)
    while stapel:
        knoop = stapel.pop()
        for buur in omgekeerd[knoop]:
            if buur not in bereikt:
                bereikt.add(buur)
                stapel.append(buur)
    return bereikt


def _eindpuntset(context: CheckContext, rollen: Sequence[str]) -> set[str]:
    """De knopen die als eindpunt van een van deze afvoerrollen gelden."""
    gevonden: set[str] = set()
    for rol in rollen:
        gevonden |= _eindpunten(context, rol)
    return gevonden


def _eindknoop_notitie(
    context: CheckContext, netwerk: _Netwerk, rollen: Sequence[str]
) -> list[str]:
    """Beschrijft waar het vrijverval op uitkomt en wat daarvan als uitstroom telt.

    Een streng zonder afvoerpad is zelden een los gebrek: het netwerk watert af op
    een beperkt aantal eindknopen, en als die niet als uitstroompunt herkend worden
    slaat de check aan op alles wat erachter ligt. Deze telling maakt zichtbaar of
    het om ontbrekende uitstroomobjecten gaat.

    Een eindknoop die zelf geen uitstroompunt is maar er wel een bereikt -- een
    pompput met een persleiding naar het gemaal -- loopt niet dood en telt hier niet
    mee; anders zou de notitie het persnet als gebrek presenteren.
    """
    sinks = [uri for uri in netwerk.graph if netwerk.graph.out_degree(uri) == 0]
    if not sinks:
        return []

    endpoints = _eindpuntset(context, rollen)
    bereikt = _bereikbaar_vanaf(context, endpoints)
    doodlopend = [uri for uri in sinks if uri not in bereikt]
    if not doodlopend:
        return []

    tellen: dict[str, int] = {}
    for uri in doodlopend:
        soort = _soort(context, uri)
        tellen[soort] = tellen.get(soort, 0) + 1
    top = ", ".join(
        f"{soort} {aantal}"
        for soort, aantal in sorted(tellen.items(), key=lambda paar: -paar[1])[:5]
    )
    uitstroom = len(sinks) - len(doodlopend)
    return [
        f"Het vrijverval watert af op {getal(len(sinks), 'eindknoop', 'eindknopen')}; "
        f"{uitstroom} daarvan {vorm(uitstroom, 'bereikt', 'bereiken')} een uitstroompunt van "
        f"dit soort; de overige {len(doodlopend)} {vorm(len(doodlopend), 'loopt', 'lopen')} dood "
        f"({top}). Alles wat daarachter ligt telt daardoor als zonder afvoerpad."
    ]


def _soort(context: CheckContext, uri: str) -> str:
    """De korte naam van het beheerobjecttype van een knoop."""
    return context.dataset.beheerobjecttype(uri) or "onbekend"


def _richtingsverlies(
    context: CheckContext, netwerk: _Netwerk, rollen: Sequence[str]
) -> tuple[int, int]:
    """Splitst de onbereikbare knopen in twee oorzaken.

    Een knoop kan een eindpunt missen omdat zijn netwerkdeel er geen bevat, of omdat
    het eindpunt er wel is maar niet in de gevolgde richting ligt. Dat onderscheid
    bepaalt of je naar ontbrekende objecten of naar verkeerde richtingen moet kijken.

    De DELEN komen van de bereikbaarheidsgraaf, want een deel kan zijn gemaal via het
    persnet bereiken en zou op het zuivere vrijverval ten onrechte als "zonder enig
    eindpunt" verschijnen. Het AANTAL telt alleen de vrijvervalknopen: een hulpstuk of
    een knoop die uitsluitend aan het persnet hangt wordt door geen enkele NET-check
    beoordeeld (mechanisch riool valt buiten het checkregister), en zou hier als
    ongemelde last verschijnen in een getal dat de lezer op de bevindingen betrekt.
    """
    endpoints = _eindpuntset(context, rollen)
    bereikt = _bereikbaar_vanaf(context, endpoints)
    vrijverval = set(netwerk.graph)

    zonder = met = 0
    for deel in nx.weakly_connected_components(_bereikbaarheid(context)):
        onbereikt = len((deel & vrijverval) - bereikt)
        if deel & endpoints:
            met += onbereikt
        else:
            zonder += onbereikt
    return zonder, met


def _bob_tegen_de_richting(netwerk: _Netwerk) -> tuple[int, int]:
    """Telt de strengen waarvan de BOB stijgt in de aangenomen afvoerrichting."""
    tegendraads = meetbaar = 0
    for conduit in netwerk.conduits:
        if conduit.bob_start is None or conduit.bob_end is None:
            continue
        meetbaar += 1
        if conduit.bob_start < conduit.bob_end:
            tegendraads += 1
    return tegendraads, meetbaar


def _netwerk_notities(context: CheckContext) -> list[str]:
    """Beschrijft welke objecten niet in de netwerkanalyse konden meedoen.

    Alleen wat op het zuivere vrijverval te zien is; wat de bereikbaarheidsgraaf nodig
    heeft staat in `_eindpuntnotities`, zodat een check die geen eindpunt zoekt het
    persnet niet aanraakt en het dus ook niet hoeft te declareren.
    """
    netwerk = _netwerk(context)
    notities = []
    if netwerk.unconnected:
        labels = ", ".join(sorted(conduit.label for conduit in netwerk.unconnected)[:10])
        notities.append(
            f"{len(netwerk.unconnected)} vrijvervalstrengen hebben geen herleidbare "
            f"put aan beide zijden en vallen buiten de netwerkanalyse: {labels}."
        )
    if netwerk.reversed_count:
        notities.append(
            f"De richting is uit het bodemverloop afgeleid; {netwerk.reversed_count} "
            "strengen zijn daarbij omgedraaid ten opzichte van de administratieve "
            "van-naar-richting."
        )

    tegendraads, meetbaar = _bob_tegen_de_richting(netwerk)
    if meetbaar and tegendraads:
        notities.append(
            f"De analyse neemt aan dat de administratieve begin-naar-eindrichting de "
            f"afvoerrichting is. Bij {tegendraads} van de {meetbaar} strengen met bekende "
            f"BOB's stijgt de bodem juist in die richting "
            f"({100 * tegendraads / meetbaar:.0f}%). NET-003 toetst dat later expliciet; "
            "tot die tijd verdienen de bereikbaarheidsuitkomsten een slag om de arm."
        )

    return notities


def _eindpuntnotities(context: CheckContext, rollen: Sequence[str]) -> list[str]:
    """De notities die op de bereikbaarheidsgraaf leunen: waar komt het water uit?

    Alleen voor de checks die werkelijk een eindpunt zoeken (NET-001, NET-002,
    NET-008). Die lezen daarmee het persnet -- dat is de rol `mechanischeleidingen`
    in hun declaratie -- terwijl de overige NET-checks op het zuivere vrijverval
    blijven. Zie BO-54.
    """
    netwerk = _netwerk(context)
    notities = list(_eindknoop_notitie(context, netwerk, rollen))

    zonder, in_deel_met_eindpunt = _richtingsverlies(context, netwerk, rollen)
    if in_deel_met_eindpunt:
        notities.append(
            f"{in_deel_met_eindpunt} knopen liggen in een netwerkdeel dat wel een eindpunt "
            "bevat, maar bereiken dat eindpunt niet als de richting gevolgd wordt. Zoveel "
            "knopen wijzen op een systematisch verkeerd gerichte administratie, niet op "
            "evenzoveel losse gebreken."
        )
    if zonder:
        notities.append(
            f"{zonder} knopen liggen in een netwerkdeel zonder enig eindpunt van dit soort."
        )

    if not _eindpuntset(context, rollen):
        namen = [naam for rol in rollen for naam in getattr(context.config.klassen, rol)]
        klassen = ", ".join(namen) or "geen geconfigureerd"
        notities.append(
            f"De graaf bevat geen enkel eindpunt van het gevraagde soort ({klassen}); "
            "deze check slaat daardoor op elke streng aan."
        )
    return notities


class _ZonderAfvoerpad(Check):
    """Gedeelde basis voor de bereikbaarheidschecks."""

    stelselrol: str
    # Meer dan een rol mag: NET-001 accepteert naast het afvoereindpunt ook het
    # lozingspunt (BO-53). De eindpuntverzameling is de vereniging van hun knopen.
    eindpuntrollen: tuple[str, ...]
    # De leesbare naam van die eindpuntrollen, zoals hij in de melding verschijnt. Hij
    # hoort niets te noemen dat `eindpuntrollen` niet zoekt; NET-002 beloofde tot issue
    # #93 een overnamepunt dat alleen in `afvoer_eindpunt` staat.
    doel: str

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen van dit stelseltype zonder pad naar een eindpunt.

        De melding noemt het stelseltype van DEZE streng en het eindpunt dat deze
        check zoekt (issue #93). NET-001 en NET-002 delen nul objecten, maar met
        alleen "Geen afvoerpad naar ..." was uit de melding zelf niet te lezen welke
        van de twee aansloeg en waarom juist deze streng. NET-001 gaat bovendien over
        twee stelseltypen tegelijk, dus de rol waarop de check selecteert (`vuilwater`)
        zegt hier minder dan het type van de streng zelf. Valt de streng onder geen
        enkel geconfigureerd stelseltype, dan blijft de rol over.
        """
        onbereikbaar, geen_eindpunten = self._onbereikbaar(context)
        staart = (
            " De graaf bevat geen enkel bereikbaar eindpunt van dit soort, dus geldt dit "
            "voor elke streng."
            if geen_eindpunten
            else ""
        )

        for conduit, cluster in onbereikbaar:
            stelsel = _stelseltype(context, conduit) or self.stelselrol
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Streng van stelseltype {stelsel!r} zonder afvoerpad naar {self.doel}.{staart}",
                stelseltype=stelsel,
                geen_eindpunten_in_graaf=geen_eindpunten,
                cluster_id=cluster,
            )

    def _onbereikbaar(self, context: CheckContext) -> tuple[list[tuple[Conduit, str]], bool]:
        """De onbereikbare strengen met hun deelstelsel; een keer per context.

        `run()` en `notes()` hebben allebei deze uitkomst nodig — de een om te
        melden, de ander om te duiden hoeveel deelstelsels het betreft. Zonder deze
        gedeelde bron zouden ze uit elkaar kunnen lopen.
        """
        sleutel = f"onbereikbaar:{self.stelselrol}:{'+'.join(self.eindpuntrollen)}"
        return context.cached(sleutel, lambda: self._bouw_onbereikbaar(context))

    def _bouw_onbereikbaar(self, context: CheckContext) -> tuple[list[tuple[Conduit, str]], bool]:
        """Loopt de strengen van dit stelseltype langs en houdt de onbereikbare over."""
        netwerk = _netwerk(context)
        endpoints: set[str] = set()
        for rol in self.eindpuntrollen:
            endpoints |= _eindpunten(context, rol)
        bereikt = _bereikbaar_vanaf(context, endpoints)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen
        clusters = deelstelsel_ids(context)
        soorten = getattr(context.config.klassen, self.stelselrol)

        gezocht = {
            uri for wortel in soorten for uri in dataset.of_class(wortel) if uri in dataset.conduits
        }

        gevonden: list[tuple[Conduit, str]] = []
        for conduit in netwerk.conduits:
            if conduit.uri not in gezocht:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            if begin not in bereikt:
                # Een streng waarvan het beginpunt niet op te lossen is hoort hier
                # thuis -- onbereikbaar is onbereikbaar -- maar heeft geen cluster.
                gevonden.append((conduit, clusters.get(begin, "") if begin else ""))
        return gevonden, not endpoints

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel; dat mag niet stilzwijgend verdwijnen.

        De clusterduiding staat bewust niet hier maar in het rapport: een check
        draait op de kern plus de contextschil (met een studiegebied) of op de
        volledige dataset (zonder), terwijl het rapport altijd tot de kern
        afgebakend is. Hier geteld zou de duiding het aantal deelstelsels van het
        hele werkbereik van de check melden bij de bevindingen van een enkele buurt.
        """
        return _netwerk_notities(context) + _eindpuntnotities(context, self.eindpuntrollen)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class VuilwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-001: vuilwater of gemengd zonder pad naar gemaal, overnamepunt of lozingspunt.

    Het lozingspunt telt sinds issue #72 mee (BO-53): vuilwater loost in Nederland
    niet meer rechtstreeks op oppervlaktewater, dus een lozingspunt is per definitie
    een geldig afvoereindpunt en er valt geen echt gebrek mee te maskeren.
    """

    id = "NET-001"
    title = (
        "Vuilwater- of gemengde streng zonder afvoerpad naar gemaal, overnamepunt of lozingspunt"
    )
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("lozingspunten", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")
    stelselrol = "vuilwater"
    eindpuntrollen = ("afvoer_eindpunt", "lozings_eindpunt")
    doel = "een gemaal, overnamepunt of lozingspunt"


@register
class HemelwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-002: hemelwater zonder pad naar een lozingspunt.

    De titel komt uit het checkregister (v0.9) en noemt daar ook het overnamepunt,
    maar `Overnamepunt` staat in de rol `afvoer_eindpunt` en die leest NET-002 niet:
    alleen `lozings_eindpunt` telt hier als bestemming. De melding noemt daarom sinds
    issue #93 alleen het lozingspunt -- de tekst hoort te zeggen wat de check meet.
    """

    id = "NET-002"
    title = "Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("lozingspunten", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")
    stelselrol = "hemelwater"
    eindpuntrollen = ("lozings_eindpunt",)
    doel = "een lozingspunt"


@register
class KringloopInNetwerk(Check):
    """NET-004: cirkels in het vrijvervalnetwerk."""

    id = "NET-004"
    title = "Cirkels (kringlopen) in het vrijvervalnetwerk"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk deel van de graaf waarin een kringloop zit.

        Per sterk samenhangend deel een melding, niet per enkelvoudige kringloop:
        het aantal enkelvoudige kringlopen groeit exponentieel met de graafgrootte,
        en op een echt stelsel loopt dat vast. Een deel met meer dan een knoop
        bevat per definitie minstens een kringloop; van elk deel wordt een
        voorbeeldkringloop getoond.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset

        for deel in nx.strongly_connected_components(netwerk.graph):
            if len(deel) < 2 and not self._heeft_zelflus(netwerk, deel):
                continue
            subgraaf = netwerk.graph.subgraph(deel)
            kring = self._voorbeeldkring(subgraaf)
            labels = [self._label(dataset, uri) for uri in kring]
            uri, label = self._eerste_streng(netwerk, kring, dataset)
            yield self.finding(
                context,
                uri,
                label,
                f"Ligt in een deel van het netwerk met {len(deel)} putten waarin een "
                f"kringloop zit; voorbeeld: {' -> '.join(labels)}.",
                putten_in_deel=len(deel),
                voorbeeldkring=labels,
            )

    def _heeft_zelflus(self, netwerk: _Netwerk, deel: set[str]) -> bool:
        """Geeft aan of het enige knooppunt in dit deel naar zichzelf wijst."""
        knoop = next(iter(deel))
        return netwerk.graph.has_edge(knoop, knoop)

    def _voorbeeldkring(self, subgraaf) -> list[str]:
        """Een kringloop uit dit deel, als illustratie in de melding.

        Met een vast beginpunt, want zonder `source` begint `find_cycle` bij de eerste
        knoop in invoegvolgorde. Die volgt uit de `set` die
        `strongly_connected_components` oplevert en dus uit de hashseed: dezelfde data
        zou per run een andere streng aanwijzen, en `vergelijk` zou daar een verschil
        in zien dat er niet is. Elk knooppunt van een sterk samenhangend deel ligt op
        een kringloop, dus de kleinste URI voldoet als startpunt.
        """
        try:
            kanten = nx.find_cycle(subgraaf, source=min(subgraaf))
        except nx.NetworkXNoCycle:
            return sorted(subgraaf)[:1]
        return [begin for begin, _, *_ in kanten]

    def _label(self, dataset: GwswDataset, uri: str) -> str:
        """Het label van een knooppunt, of de URI als dat er niet is."""
        node = dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def _eerste_streng(
        self, netwerk: _Netwerk, kring: list[str], dataset: GwswDataset
    ) -> tuple[str, str]:
        """De streng waarop de melding wordt gehangen: de eerste op de kant kring[0] -> kring[1]."""
        if len(kring) > 1:
            strengen = netwerk.strengen_per_kant.get((kring[0], kring[1]), ())
            if strengen:
                return strengen[0].uri, strengen[0].label
        return kring[0], self._label(dataset, kring[0])

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel."""
        return _netwerk_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class ItStelselZonderDrempel(Check):
    """NET-007: een deelstelsel met infiltratieleidingen zonder drempel."""

    id = "NET-007"
    title = "IT-stelsel zonder drempel"
    severity = Severity.ERROR
    dimension = Dimension.COMPLETENESS
    rollen = ("infiltratieleidingen", "overstortputten", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt samenhangende delen met infiltratieleidingen maar zonder drempel.

        De GWSW-ontologie kent het IT-stelsel wel (Infiltratiestelsel en zijn
        subklasse DrainageInfiltratieTransportStelsel), maar de engine leest de
        stelselboom uit de export nergens; een deelstelsel waarin infiltratieleidingen
        liggen geldt hier daarom als IT-stelsel. Welke klassen dat zijn, staat in de
        projectconfig. Zie BO-34 in docs/beslislog.md.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        infiltratie = {conduit.uri for conduit in infiltratieleidingen(context)}
        if not infiltratie:
            return

        drempelknopen = self._knopen_met_drempel(context)

        # Een doorloop over de strengen in plaats van een per component: de dict
        # wijst elke knoop zijn component aan, en de meldingsvolgorde blijft die
        # van de componenten met daarbinnen de volgorde van `netwerk.conduits`.
        componenten = list(nx.weakly_connected_components(netwerk.graph))
        component_van = {knoop: index for index, deel in enumerate(componenten) for knoop in deel}
        per_component: dict[int, list[Conduit]] = {}
        for conduit in netwerk.conduits:
            if conduit.uri not in infiltratie:
                continue
            begin = dataset.resolve_network_node(conduit.start_node, wortels)
            index = component_van.get(begin) if begin is not None else None
            if index is not None:
                per_component.setdefault(index, []).append(conduit)

        for index, deel in enumerate(componenten):
            strengen = per_component.get(index, [])
            if not strengen or deel & drempelknopen:
                continue
            for conduit in strengen:
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    "Ligt in een deelstelsel met infiltratieleidingen zonder enige drempel.",
                    putten_in_deelstelsel=len(deel),
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat als drempel telt en wat er buiten de graaf viel."""
        notities = _netwerk_notities(context)
        if infiltratieleidingen(context):
            notities.insert(
                0,
                "Een deelstelsel telt hier als voorzien van een drempel wanneer er een los "
                "`Overstortdrempel`-onderdeel in ligt of een overstortput (`Overstortput`, "
                "`Stuwput`); een bergbezinkvoorziening telt niet mee.",
            )
        return notities

    def _knopen_met_drempel(self, context: CheckContext) -> set[str]:
        """De knopen die een overstortvoorziening dragen.

        Twee vormen, dezelfde als `checks/randvoorzieningen.py` leest: een los
        `Overstortdrempel`-onderdeel, en de overstortput zelf. Op de De
        Wolden en Hoogeveen-export staan overstorten als `Overstortput` met een
        `Overstortleiding`, niet als los `Overstortdrempel`-object (BO-34, open
        punt 6); alleen op `Overstortdrempel` afgaan liet de verzameling leeg en
        meldde elk infiltratieriool onvoorwaardelijk. Zie issue #42.
        """
        dataset = context.dataset
        wortels = context.config.klassen.netwerkknopen

        knopen: set[str] = set()
        for wortel in context.config.klassen.drempel:
            for drempel in dataset.subjects_of_class(wortel):
                for houder in part_holders_of(dataset.graph, drempel):
                    knoop = dataset.resolve_network_node(str(houder), wortels)
                    if knoop is not None:
                        knopen.add(knoop)
        for put in overstortputten(context):
            knoop = dataset.resolve_network_node(put.uri, wortels)
            if knoop is not None:
                knopen.add(knoop)
        return knopen

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


def _stelseltype(context: CheckContext, conduit: Conduit) -> str | None:
    """Het stelseltype van een streng volgens de projectconfig."""
    return context.config.klassen.stelseltype(conduit.types, context.dataset.closure)


@register
class OrientatieTegenAfvoerrichting(Check):
    """NET-003: de administratieve richting loopt tegen het bodemverval in."""

    id = "NET-003"
    title = "Strengorientatie tegen de afvoerrichting in"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst of de bodem daalt van de administratieve begin- naar de eindput.

        Vrijverval stroomt naar beneden. Stijgt de BOB in de van-naar-richting met
        meer dan de drempel voor licht tegenverhang, dan wijst dat op een omgekeerd
        geregistreerde streng. HGT-005 en HGT-006 melden hetzelfde verschijnsel als
        hoogteprobleem; NET-003 leest het als richtingsprobleem, en het register
        kent beide.
        """
        drempel = context.config.drempels.tegenverhang_licht_m

        for conduit in _netwerk(context).conduits:
            if conduit.bob_start is None or conduit.bob_end is None:
                continue
            stijging = conduit.bob_end - conduit.bob_start
            if stijging <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"De bodem stijgt {stijging:.3f} m van begin- naar eindpunt "
                f"(BOB {conduit.bob_start:.3f} naar {conduit.bob_end:.3f} m NAP); "
                "de streng lijkt omgekeerd geregistreerd.",
                bob_begin=conduit.bob_start,
                bob_eind=conduit.bob_end,
                stijging_m=round(stijging, 3),
                drempel_m=drempel,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen door ontbrekende BOB's buiten beeld bleven."""
        netwerk = _netwerk(context)
        zonder = sum(
            1
            for conduit in netwerk.conduits
            if conduit.bob_start is None or conduit.bob_end is None
        )
        notities = _netwerk_notities(context)
        if zonder:
            notities.append(
                f"{zonder} van de {len(netwerk.conduits)} strengen in de graaf missen een "
                "BOB aan begin- of eindpunt; die konden niet op richting getoetst worden."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf met beide BOB's."""
        return sum(
            1
            for conduit in _netwerk(context).conduits
            if conduit.bob_start is not None and conduit.bob_end is not None
        )


_RICHTING_MEE = "mee"
_RICHTING_TEGEN = "tegen"
_RICHTING_VLAK = "vlak"
_RICHTING_ONBEKEND = "onbekend"


@dataclass(frozen=True)
class _Richtingsdiagnose:
    """De richtingssignalen van een streng, elk ten opzichte van de administratie.

    `geometrie` en `bob` zeggen of dat signaal met de administratieve van-naar-richting
    meeloopt (`mee`), er tegenin (`tegen`), niet te bepalen is (`onbekend`) of -- alleen
    de BOB -- vlak ligt (`vlak`). `waarheid` is de harde referentie uit de ongerichte
    graaf: is er vanuit de streng een lozingspunt bereikbaar, dan loopt de afvoer die
    kant op en zegt `waarheid` of dat met de van-naar-richting meeloopt (`mee`), er
    tegenin gaat (`tegen`) of niet vast te leggen is (`onbekend`). De administratie is de
    tekstuele referentie: van `begin_label` naar `eind_label`.
    """

    conduit: Conduit
    begin_label: str
    eind_label: str
    geometrie: str
    bob: str
    bob_verval: float | None
    waarheid: str


def _knooplabel(context: CheckContext, uri: str | None) -> str:
    """Het label van de knoop boven een strengkoppeling, of de URI als er geen label is."""
    dataset = context.dataset
    knoop = dataset.resolve_network_node(uri, context.config.klassen.netwerkknopen)
    node = dataset.nodes.get(knoop or "")
    return node.label if node is not None and node.label else (knoop or "")


def _geometrie_richting(context: CheckContext, conduit: Conduit) -> str:
    """De tekenrichting van de lijn ten opzichte van de van-naar-richting."""
    uitslag = context.dataset.richting_van_geometrie(conduit, context.config.klassen.netwerkknopen)
    if uitslag is None:
        return _RICHTING_ONBEKEND
    omgekeerd, _, _ = uitslag
    return _RICHTING_TEGEN if omgekeerd else _RICHTING_MEE


def _bob_richting(conduit: Conduit, drempel: float) -> str:
    """De BOB-richting: daalt (mee), stijgt (tegen), ligt vlak, of ontbreekt."""
    verval = conduit.bob_verval
    if verval is None:
        return _RICHTING_ONBEKEND
    if verval > drempel:
        return _RICHTING_MEE
    if verval < -drempel:
        return _RICHTING_TEGEN
    return _RICHTING_VLAK


def _lozingspunt_afstanden(context: CheckContext) -> dict[str, int]:
    """Per knoop de ongerichte afstand tot het dichtstbijzijnde lozingspunt.

    De harde waarheid van NET-009: waar het water werkelijk uitkomt, los van hoe de
    richting geregistreerd staat. Daarom een ongerichte doorloop -- een verkeerd
    gerichte administratie mag de afvoerrichting niet mee bepalen. Een keer per context.
    """
    return context.cached("net009:lozingsafstand", lambda: _bouw_lozingspunt_afstanden(context))


def _bouw_lozingspunt_afstanden(context: CheckContext) -> dict[str, int]:
    """Multi-source breedte-eerst vanaf alle lozingspunten over de ongerichte graaf.

    Over de bereikbaarheidsgraaf (BO-54: het persnet telt als ongerichte connectiviteit),
    zodat een streng die via een pompput en het persnet op een lozingspunt uitkomt óók
    zijn afvoerrichting vastgelegd krijgt. Een enkele O(knopen + kanten)-doorloop.
    """
    lozingen = _eindpunten(context, "lozings_eindpunt")
    ongericht = _bereikbaarheid(context).to_undirected(as_view=True)
    afstand = {uri: 0 for uri in lozingen if uri in ongericht}
    rij: deque[str] = deque(sorted(afstand))
    while rij:
        knoop = rij.popleft()
        for buur in ongericht[knoop]:
            if buur not in afstand:
                afstand[buur] = afstand[knoop] + 1
                rij.append(buur)
    return afstand


def _waarheid_richting(context: CheckContext, conduit: Conduit, afstanden: dict[str, int]) -> str:
    """De afvoerrichting uit een bereikbaar lozingspunt, ten opzichte van de administratie.

    Ligt de administratieve beginput dichter bij een lozingspunt dan de eindput, dan
    hoort het water van eind naar begin te lopen en staat de administratie omgekeerd
    (`tegen`); ligt de eindput dichterbij, dan loopt de afvoer mee. Bereikt geen van
    beide een lozingspunt, of liggen ze even ver, dan legt de waarheid niets vast.
    """
    begin, eind = verbonden_knopen(context, conduit)
    begin_afstand = afstanden.get(begin) if begin is not None else None
    eind_afstand = afstanden.get(eind) if eind is not None else None
    if begin_afstand is None or eind_afstand is None or begin_afstand == eind_afstand:
        return _RICHTING_ONBEKEND
    return _RICHTING_MEE if begin_afstand > eind_afstand else _RICHTING_TEGEN


def _richtingsdiagnoses(context: CheckContext) -> list[_Richtingsdiagnose]:
    """De richtingssignalen per streng in de graaf; een keer per context."""
    return context.cached("net009", lambda: _bouw_richtingsdiagnoses(context))


def _bouw_richtingsdiagnoses(context: CheckContext) -> list[_Richtingsdiagnose]:
    """Bepaalt per aangesloten vrijvervalstreng haar richtingssignalen en de harde waarheid."""
    drempel = context.config.drempels.tegenverhang_licht_m
    afstanden = _lozingspunt_afstanden(context)
    return [
        _Richtingsdiagnose(
            conduit=conduit,
            begin_label=_knooplabel(context, conduit.start_node),
            eind_label=_knooplabel(context, conduit.end_node),
            geometrie=_geometrie_richting(context, conduit),
            bob=_bob_richting(conduit, drempel),
            bob_verval=conduit.bob_verval,
            waarheid=_waarheid_richting(context, conduit, afstanden),
        )
        for conduit in _netwerk(context).conduits
    ]


def _tegenspraak(diagnose: _Richtingsdiagnose) -> bool:
    """Geeft aan of administratie, geometrie en BOB niet alle drie dezelfde kant op wijzen.

    De referentie is de harde waarheid uit een bereikbaar lozingspunt (`waarheid`); is er
    geen lozingspunt bereikbaar, dan valt de referentie terug op de administratie zelf.
    Er is tegenspraak zodra een stellig signaal -- de administratie (altijd 'mee'), de
    geometrie of de BOB -- de andere kant op wijst dan die referentie. Een vlak of
    onbekend signaal doet geen uitspraak en telt daarom niet als tegenspraak. Loopt de
    waarheid tegen de administratie in, dan is de administratie zelf het foute signaal --
    ook als geometrie en BOB haar keurig volgen.
    """
    referentie = diagnose.waarheid if diagnose.waarheid != _RICHTING_ONBEKEND else _RICHTING_MEE
    signalen = (_RICHTING_MEE, diagnose.geometrie, diagnose.bob)
    return any(
        signaal in (_RICHTING_MEE, _RICHTING_TEGEN) and signaal != referentie
        for signaal in signalen
    )


def _geen_signaal(diagnose: _Richtingsdiagnose) -> bool:
    """Geeft aan of noch de geometrie noch de BOB iets over de richting zegt."""
    return diagnose.geometrie == _RICHTING_ONBEKEND and diagnose.bob == _RICHTING_ONBEKEND


def _niet_beoordeeld(diagnose: _Richtingsdiagnose) -> bool:
    """Geen enkel richtingssignaal: geometrie noch BOB, en geen bereikbaar lozingspunt.

    Een bereikbaar lozingspunt maakt de administratie toetsbaar (zij is dan zelf een
    signaal tegen de harde waarheid), dus een streng met alleen een waarheid telt wél
    als beoordeeld.
    """
    return _geen_signaal(diagnose) and diagnose.waarheid == _RICHTING_ONBEKEND


def _geometrie_zin(richting: str) -> str:
    """De geometrieregel van de melding."""
    if richting == _RICHTING_TEGEN:
        return "De lijn is omgekeerd getekend, van eind naar begin."
    if richting == _RICHTING_MEE:
        return "De lijn is in de van-naar-richting getekend."
    return "De tekenrichting van de lijn is niet te bepalen."


def _bob_zin(richting: str, verval: float | None) -> str:
    """De BOB-regel van de melding."""
    if richting == _RICHTING_MEE and verval is not None:
        return f"De BOB daalt {verval:.3f} m van begin naar eind."
    if richting == _RICHTING_TEGEN and verval is not None:
        return f"De BOB stijgt {abs(verval):.3f} m van begin naar eind."
    if richting == _RICHTING_VLAK and verval is not None:
        return f"De BOB ligt vlak ({verval:.3f} m)."
    return "De BOB ontbreekt."


def _waarheid_zin(richting: str) -> str:
    """De regel over de harde waarheid uit een bereikbaar lozingspunt."""
    if richting == _RICHTING_TEGEN:
        return (
            " Naar het dichtstbijzijnde bereikbare lozingspunt loopt de afvoer juist van "
            "eind naar begin; de administratie wijst de verkeerde kant op."
        )
    if richting == _RICHTING_MEE:
        return (
            " Naar het dichtstbijzijnde bereikbare lozingspunt loopt de afvoer in de "
            "van-naar-richting; de administratie klopt en een ander signaal is fout."
        )
    return ""


@register
class RichtingssignalenSprekenElkaarTegen(Check):
    """NET-009: de integrale richtingscheck. Administratie, geometrie en BOB moeten
    dezelfde kant op wijzen als de afvoer werkelijk loopt."""

    id = "NET-009"
    title = "Richtingssignalen (administratie, geometrie, BOB) spreken elkaar tegen"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("lozingspunten", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke streng waarvan de richtingssignalen niet één kant op wijzen.

        De integrale richtingscheck (issue #80): zijn administratie, tekenrichting én
        BOB het eens, dan is de streng goed. In elk ander geval een W. Is er vanuit de
        streng een lozingspunt bereikbaar, dan legt een ongerichte graaf de werkelijke
        afvoerrichting vast en is dát de referentie -- ook de administratie zelf kan er
        dan tegen in blijken te staan. De melding noemt alle waarden, zodat de beheerder
        ziet welke fout is. NET-003 (BOB tegen) en TOP-020 (tekenrichting tegen) gingen
        hierin op en vervielen als aparte checks.
        """
        for diagnose in _richtingsdiagnoses(context):
            if not _tegenspraak(diagnose):
                continue
            intern = _RICHTING_TEGEN in (diagnose.geometrie, diagnose.bob)
            lead = (
                "De richtingssignalen spreken elkaar tegen."
                if intern
                else "De registratie is intern consistent, maar wijst de verkeerde kant op."
            )
            boodschap = (
                f"{lead} Administratief loopt de streng van {diagnose.begin_label!r} naar "
                f"{diagnose.eind_label!r}. {_geometrie_zin(diagnose.geometrie)} "
                f"{_bob_zin(diagnose.bob, diagnose.bob_verval)}"
                f"{_waarheid_zin(diagnose.waarheid)}"
            )
            yield self.finding(
                context,
                diagnose.conduit.uri,
                diagnose.conduit.label,
                boodschap,
                geometrie=diagnose.geometrie,
                bob=diagnose.bob,
                waarheid=diagnose.waarheid,
                bob_verval_m=round(diagnose.bob_verval, 3)
                if diagnose.bob_verval is not None
                else None,
                administratief_begin=diagnose.begin_label,
                administratief_eind=diagnose.eind_label,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de harde waarheid, de vlakke strengen en de BOB's die als vulwaarde wegvielen."""
        diagnoses = _richtingsdiagnoses(context)
        notities = _netwerk_notities(context)

        met_waarheid = sum(1 for d in diagnoses if d.waarheid != _RICHTING_ONBEKEND)
        if met_waarheid:
            omgekeerd = sum(1 for d in diagnoses if d.waarheid == _RICHTING_TEGEN)
            notities.append(
                f"Voor {getal(met_waarheid, 'streng', 'strengen')} is via een ongerichte graaf "
                f"een bereikbaar lozingspunt gevonden en de afvoerrichting daaruit vastgelegd; "
                f"bij {omgekeerd} daarvan wijst de administratie de verkeerde kant op."
            )

        vlak = sum(
            1
            for d in diagnoses
            if not _tegenspraak(d) and d.bob == _RICHTING_VLAK and d.waarheid == _RICHTING_ONBEKEND
        )
        if vlak:
            drempel = context.config.drempels.tegenverhang_licht_m
            notities.append(
                f"{getal(vlak, 'streng', 'strengen')} {vorm(vlak, 'ligt', 'liggen')} vlak "
                f"(|verval| ≤ {drempel} m) zonder bereikbaar lozingspunt: de BOB zegt niets over "
                f"de richting, dus deze toets doet daar geen uitspraak over."
            )

        vulwaarde = sum(1 for d in diagnoses if d.conduit.vulwaarden)
        if vulwaarde:
            notities.append(
                f"{getal(vulwaarde, 'streng', 'strengen')} {vorm(vulwaarde, 'heeft', 'hebben')} "
                "een BOB die als vulwaarde (rond 0 m NAP) is gelezen en daardoor ontbreekt; "
                "hun richting kon niet op de BOB getoetst worden."
            )

        niet_beoordeeld = sum(1 for d in diagnoses if _niet_beoordeeld(d))
        if niet_beoordeeld:
            notities.append(
                f"{getal(niet_beoordeeld, 'streng', 'strengen')} "
                f"{vorm(niet_beoordeeld, 'draagt', 'dragen')} geen bruikbare tekenrichting, geen "
                "BOB en geen bereikbaar lozingspunt, dus met geen enkel richtingssignaal te "
                "toetsen; deze strengen zijn niet beoordeeld."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """De strengen met minstens een richtingssignaal; de rest kon niet beoordeeld worden."""
        return sum(1 for d in _richtingsdiagnoses(context) if not _niet_beoordeeld(d))


@register
class StelseltypeWijktAfVanBuren(Check):
    """NET-005: een streng met een ander stelseltype dan al haar buren."""

    id = "NET-005"
    title = "Stelseltype streng wijkt af van boven- en benedenstroomse buren"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen die als enige van hun soort tussen andere soorten liggen.

        Een enkele hemelwaterstreng midden in een gemengd tracee is vrijwel altijd
        een typeringsfout. De check slaat alleen aan als de streng aan beide zijden
        buren heeft en geen van die buren hetzelfde stelseltype heeft; een streng
        aan de rand van een stelsel is namelijk terecht anders dan haar buur.
        """
        netwerk = _netwerk(context)

        soorten = {conduit.uri: _stelseltype(context, conduit) for conduit in netwerk.conduits}
        per_knoop: dict[str, list[Conduit]] = {}
        for conduit in netwerk.conduits:
            for uri in verbonden_knopen(context, conduit):
                if uri is not None:
                    per_knoop.setdefault(uri, []).append(conduit)

        for conduit in netwerk.conduits:
            eigen = soorten[conduit.uri]
            if eigen is None:
                continue
            begin, eind = verbonden_knopen(context, conduit)
            bovenstrooms = self._buren(per_knoop, begin, conduit.uri, soorten)
            benedenstrooms = self._buren(per_knoop, eind, conduit.uri, soorten)
            # Het register vraagt om afwijking van *boven- en* benedenstroomse
            # buren. Een streng aan het uiteinde van een stelsel heeft er maar aan
            # een kant; die is niet afwijkend maar simpelweg de laatste van haar
            # soort, en hoort hier niet te verschijnen.
            if not bovenstrooms or not benedenstrooms:
                continue
            buursoorten = bovenstrooms | benedenstrooms
            if eigen in buursoorten:
                continue
            aantal = sum(
                1
                for uri in (begin, eind)
                if uri is not None
                for buur in per_knoop.get(uri, [])
                if buur.uri != conduit.uri
            )
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Is van stelseltype {eigen!r} terwijl alle {aantal} buurstrengen "
                f"van type {', '.join(sorted(buursoorten))} zijn.",
                stelseltype=eigen,
                buurtypen=sorted(buursoorten),
            )

    def _buren(
        self,
        per_knoop: dict[str, list[Conduit]],
        knoop: str | None,
        eigen_uri: str,
        soorten: dict[str, str | None],
    ) -> set[str]:
        """De stelseltypen van de andere strengen op deze knoop."""
        if knoop is None:
            return set()
        return {
            soort
            for buur in per_knoop.get(knoop, [])
            if buur.uri != eigen_uri and (soort := soorten[buur.uri]) is not None
        }

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen herkenbaar stelseltype hebben."""
        return _stelseltype_notities(context) + _netwerk_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen in de graaf."""
        return len(_netwerk(context).conduits)


@register
class KoppelingTussenStelseltypen(Check):
    """NET-006: een knoop waar verschillende stelseltypen samenkomen."""

    id = "NET-006"
    title = "Koppelingen tussen verschillende stelseltypen"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke knoop waarop strengen van meer dan een stelseltype uitkomen.

        Zulke koppelingen bestaan legitiem — een overstort of een aansluiting van
        hemelwater op een gemengd stelsel — maar ze horen bewust te zijn. De
        bevinding staat op de knoop, want daar zit de koppeling.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset

        per_knoop: dict[str, dict[str, list[str]]] = {}
        for conduit in netwerk.conduits:
            soort = _stelseltype(context, conduit)
            if soort is None:
                continue
            for uri in verbonden_knopen(context, conduit):
                if uri is not None:
                    per_knoop.setdefault(uri, {}).setdefault(soort, []).append(conduit.label)

        for uri, soorten in sorted(per_knoop.items()):
            if len(soorten) < 2:
                continue
            node = dataset.nodes.get(uri)
            omschrijving = "; ".join(
                f"{soort}: {', '.join(sorted(labels))}" for soort, labels in sorted(soorten.items())
            )
            yield self.finding(
                context,
                uri,
                node.label if node is not None else uri,
                f"Hier komen {len(soorten)} stelseltypen samen ({omschrijving}).",
                stelseltypen=sorted(soorten),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen herkenbaar stelseltype hebben."""
        return _stelseltype_notities(context)

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen in de graaf."""
        return _netwerk(context).graph.number_of_nodes()


@register
class VeelLozingspuntenInDeelstelsel(Check):
    """NET-008: opvallend veel lozingspunten in een klein deelstelsel."""

    id = "NET-008"
    title = "Opvallend veel lozingspunten binnen een klein deelstelsel"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("lozingspunten", "mechanischeleidingen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt de lozingspunten per samenhangend deel van het netwerk.

        Veel uitlaten op weinig putten wijst zelden op veel lozingen en meestal op
        een deelstelsel dat in stukken uiteengevallen is of op uitlaten die als
        gewone put opgevoerd hadden moeten worden.
        """
        netwerk = _netwerk(context)
        drempels = context.config.drempels
        endpoints = _eindpunten(context, "lozings_eindpunt")
        if not endpoints:
            return

        for deel in nx.weakly_connected_components(netwerk.graph):
            lozingen = sorted(deel & endpoints)
            if len(deel) > drempels.klein_deelstelsel_knopen:
                continue
            if len(lozingen) <= drempels.lozingspunten_per_deelstelsel:
                continue
            labels = [self._label(context, uri) for uri in lozingen]
            for uri in lozingen:
                yield self.finding(
                    context,
                    uri,
                    self._label(context, uri),
                    f"Een van {len(lozingen)} lozingspunten in een deelstelsel van "
                    f"{len(deel)} knopen (maximaal {drempels.lozingspunten_per_deelstelsel} "
                    f"bij ten hoogste {drempels.klein_deelstelsel_knopen} knopen): "
                    f"{', '.join(labels)}.",
                    knopen_in_deelstelsel=len(deel),
                    lozingspunten=len(lozingen),
                )

    def _label(self, context: CheckContext, uri: str) -> str:
        """Het label van een knoop, of de URI als dat er niet is."""
        node = context.dataset.nodes.get(uri)
        return node.label if node is not None and node.label else uri

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel."""
        return _netwerk_notities(context) + _eindpuntnotities(context, ("lozings_eindpunt",))

    def examined(self, context: CheckContext) -> int:
        """Het aantal knopen in de graaf."""
        return _netwerk(context).graph.number_of_nodes()


def _stelseltype_notities(context: CheckContext) -> list[str]:
    """Meldt hoe de stelseltypen ingedeeld zijn en wat er niet in past."""
    klassen = context.config.klassen.stelseltypen
    if not klassen:
        return [
            "Er zijn geen stelseltypen geconfigureerd (`klassen.stelseltypen`); deze check "
            "kon daardoor niets vergelijken."
        ]
    netwerk = _netwerk(context)
    zonder = [
        conduit.label for conduit in netwerk.conduits if _stelseltype(context, conduit) is None
    ]
    notities = [f"Stelseltypen uit de config: {', '.join(sorted(klassen))}."]
    if zonder:
        notities.append(
            f"{len(zonder)} van de {len(netwerk.conduits)} strengen in de graaf vallen onder "
            "geen enkel geconfigureerd stelseltype en doen niet mee."
        )
    return notities
