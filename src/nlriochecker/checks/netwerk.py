"""NET-checks: netwerklogica op de gerichte vrijvervalgraaf."""

from __future__ import annotations

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
from nlriochecker.checks.hulpstukken import telbare_hulpstukken
from nlriochecker.checks.selectie import (
    infiltratieleidingen,
    overstortputten,
)
from nlriochecker.checks.verbanden import (
    _bereikbaarheid,
    _doorgeefknopen,
    _eindpunten,
    _Netwerk,
    _netwerk,
    deelstelsel_ids,
    putknopen,
    verbonden_knopen,
)
from nlriochecker.taal import getal, vorm


def _bereikbaar_vanaf(
    context: CheckContext, endpoints: set[str], graph: nx.DiGraph | None = None
) -> set[str]:
    """De knopen die stroomafwaarts een van deze eindpunten bereiken.

    Standaard over de bereikbaarheidsgraaf, dus inclusief het mechanische riool als
    ongerichte connectiviteit: een vrijvervalstreng die op een pompput eindigt voert
    wel degelijk af, langs het persnet naar het gemaal erachter (BO-54). Met een eigen
    `graph` (issue #127: het zuivere vrijverval van `_gemengd_benedenstrooms`) draait
    dezelfde doorloop op die graaf in plaats van op de bereikbaarheidslaag.

    Een enkele doorloop over de omgekeerde graaf vanaf alle eindpunten tegelijk.
    Per eindpunt afzonderlijk zoeken kost O(eindpunten x graaf): De Wolden en Hoogeveen heeft
    893 gemalen op ruim 20.000 knopen, en dat loopt in de tientallen miljoenen
    stappen. Zo blijft het een enkele O(knopen + kanten)-doorloop.
    """
    if not endpoints:
        return set()

    basis = graph if graph is not None else _bereikbaarheid(context)
    omgekeerd = basis.reverse(copy=False)
    bereikt = {uri for uri in endpoints if uri in omgekeerd}
    stapel = list(bereikt)
    while stapel:
        knoop = stapel.pop()
        for buur in omgekeerd[knoop]:
            if buur not in bereikt:
                bereikt.add(buur)
                stapel.append(buur)
    return bereikt


def _gemengd_benedenstrooms(context: CheckContext, netwerk: _Netwerk) -> set[str]:
    """Knopen vanwaar het vrijverval, benedenstrooms gevolgd, in gemengd riool overgaat.

    Voor NET-002 (issue #127): een hemelwaterstreng die uiteindelijk in het gemengde
    riool uitkomt, mag ook op een overnamepunt of gemaal uitkomen in plaats van op een
    lozingspunt -- water dat eenmaal gemengd is, hoort niet meer bij het aparte
    hemelwaterafvoerpad. De vereenvoudigde regel uit de spec (het "eenvoudiger"-
    alternatief): het volstaat dat de streng benedenstrooms ooit gemengd wordt, los van
    of dat exact hetzelfde pad is als waarlangs zij het overnamepunt bereikt.

    Op het zuivere vrijverval (`netwerk.graph`), niet de bereikbaarheidslaag: een
    gemengde streng is per definitie vrijverval, en het mechanische riool draagt geen
    stelseltype.
    """
    startknopen: set[str] = set()
    for conduit in netwerk.conduits:
        if _stelseltype(context, conduit) != "gemengd":
            continue
        begin, _ = _doorgeefknopen(context, conduit)
        if begin is not None:
            startknopen.add(begin)
    return _bereikbaar_vanaf(context, startknopen, netwerk.graph)


def _bereikt_via_gemengd(
    context: CheckContext, netwerk: _Netwerk, rollen_via_gemengd: Sequence[str]
) -> set[str]:
    """De knopen die een voorwaardelijke eindpuntrol bereiken én benedenstrooms gemengd worden.

    Dezelfde combinatie als `_ZonderAfvoerpad._bouw_onbereikbaar` toepast op een streng
    (issue #127/BO-88): een knoop telt hier pas mee als hij een eindpunt uit
    `rollen_via_gemengd` bereikt *en* zelf in `_gemengd_benedenstrooms` zit. Gedeeld met de
    toelichtingsfuncties hieronder (`_eindknoop_notitie`, `_richtingsverlies`), zodat de
    toelichting nooit een andere bereikbaarheid claimt dan de bevinding toepast -- dat was
    de fixronde-1-bevinding op dit issue: de toelichting gebruikte tot nu toe alleen de
    onvoorwaardelijke `eindpuntrollen` en beweerde daardoor over een via-gemengd-bereikte
    knoop nog steeds dat alles erachter zonder afvoerpad is.
    """
    if not rollen_via_gemengd:
        return set()
    endpoints = _eindpuntset(context, rollen_via_gemengd)
    return _bereikbaar_vanaf(context, endpoints) & _gemengd_benedenstrooms(context, netwerk)


def _eindpuntset(context: CheckContext, rollen: Sequence[str]) -> set[str]:
    """De knopen die als eindpunt van een van deze afvoerrollen gelden."""
    gevonden: set[str] = set()
    for rol in rollen:
        gevonden |= _eindpunten(context, rol)
    return gevonden


def _bereikt_voor_toelichting(
    context: CheckContext,
    netwerk: _Netwerk,
    rollen: Sequence[str],
    rollen_via_gemengd: Sequence[str],
) -> set[str]:
    """De 'bereikt'-verzameling voor de toelichtingsfuncties (issue #127, fixronde 1).

    Drie delen, elk nodig om de toelichting niet iets anders te laten beweren dan
    `_bouw_onbereikbaar` toepast: de onvoorwaardelijke ancestors van `rollen`
    (ongewijzigd), de RAUWE eindpunten van `rollen_via_gemengd` zelf (zo'n knoop is per
    definitie een erkend uitstroompunt van het bredere soort -- de gemengd-voorwaarde
    gaat over de STRENG ernaartoe, niet over de knoop zelf, dus een overnamepunt- of
    gemaalknoop die toevallig ook een netwerk-sink is hoort nooit als doodlopend te
    gelden), en `_bereikt_via_gemengd` voor de ancestors die zelf aan de voorwaarde
    voldoen (nodig voor `_richtingsverlies`, dat elke vrijvervalknoop beoordeelt en niet
    alleen de sinks).
    """
    endpoints = _eindpuntset(context, rollen)
    endpoints_via_gemengd = _eindpuntset(context, rollen_via_gemengd)
    return (
        _bereikbaar_vanaf(context, endpoints)
        | endpoints_via_gemengd
        | _bereikt_via_gemengd(context, netwerk, rollen_via_gemengd)
    )


def _eindknoop_notitie(
    context: CheckContext,
    netwerk: _Netwerk,
    rollen: Sequence[str],
    rollen_via_gemengd: Sequence[str] = (),
) -> list[str]:
    """Beschrijft waar het vrijverval op uitkomt en wat daarvan als uitstroom telt.

    Een streng zonder afvoerpad is zelden een los gebrek: het netwerk watert af op
    een beperkt aantal eindknopen, en als die niet als uitstroompunt herkend worden
    slaat de check aan op alles wat erachter ligt. Deze telling maakt zichtbaar of
    het om ontbrekende uitstroomobjecten gaat.

    Een eindknoop die zelf geen uitstroompunt is maar er wel een bereikt -- een
    pompput met een persleiding naar het gemaal -- loopt niet dood en telt hier niet
    mee; anders zou de notitie het persnet als gebrek presenteren. Sinds issue #127
    telt hetzelfde voor een eindknoop van het voorwaardelijke soort
    (`rollen_via_gemengd`, bijvoorbeeld een overnamepunt of gemaal): NET-002 keurt zo'n
    knoop al goed als bestemming (`_bereikt_voor_toelichting`), en de toelichting mag
    dat niet tegenspreken door haar toch als doodlopend te tellen.
    """
    sinks = [uri for uri in netwerk.graph if netwerk.graph.out_degree(uri) == 0]
    if not sinks:
        return []

    bereikt = _bereikt_voor_toelichting(context, netwerk, rollen, rollen_via_gemengd)
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
    context: CheckContext,
    netwerk: _Netwerk,
    rollen: Sequence[str],
    rollen_via_gemengd: Sequence[str] = (),
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

    Sinds BO-83 staan de telbare hulpstukken zelf in `netwerk.graph` -- ze geven daar
    door -- dus reduceert `putknopen` de verzameling hier tot de beoordeelde objecten.
    Zonder die aftrek zou dit getal ze meetellen en de zin erboven onwaar maken.

    Sinds issue #127 telt een netwerkdeel met alleen een `rollen_via_gemengd`-eindpunt
    (bijvoorbeeld een Gemaal zonder lozingspunt) ook als "met eindpunt": de graaf draagt
    er wel degelijk een bestemming van het bredere soort, ook al accepteert de check hem
    alleen voor een streng die zelf benedenstrooms gemengd wordt. `bereikt`
    (`_bereikt_voor_toelichting`) telt dezelfde combinatie mee die `run()` toepast, zodat
    het AANTAL geen knoop als onbereikt meetelt die de check al goedkeurde.
    """
    endpoints = _eindpuntset(context, rollen)
    endpoints_via_gemengd = _eindpuntset(context, rollen_via_gemengd)
    bereikt = _bereikt_voor_toelichting(context, netwerk, rollen, rollen_via_gemengd)
    vrijverval = putknopen(context, netwerk.graph)

    zonder = met = 0
    for deel in nx.weakly_connected_components(_bereikbaarheid(context)):
        onbereikt = len((deel & vrijverval) - bereikt)
        if deel & (endpoints | endpoints_via_gemengd):
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
            f"{len(netwerk.unconnected)} vrijvervalstrengen hebben niet aan beide zijden "
            f"een herleidbare put of een telbaar hulpstuk en vallen buiten de "
            f"netwerkanalyse: {labels}."
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
            f"({100 * tegendraads / meetbaar:.0f}%). NET-009 toetst de richting integraal; "
            "tot die tijd verdienen de bereikbaarheidsuitkomsten een slag om de arm."
        )

    return notities


def _eindpuntnotities(
    context: CheckContext, rollen: Sequence[str], rollen_via_gemengd: Sequence[str] = ()
) -> list[str]:
    """De notities die op de bereikbaarheidsgraaf leunen: waar komt het water uit?

    Alleen voor de checks die werkelijk een eindpunt zoeken (NET-001, NET-002,
    NET-008). Die lezen daarmee het persnet -- dat is de rol `mechanischeleidingen`
    in hun declaratie -- terwijl de overige NET-checks op het zuivere vrijverval
    blijven. Zie BO-54.

    `rollen_via_gemengd` is de voorwaardelijke eindpuntrol van NET-002 (issue #127):
    zonder haar hier mee te geven zou deze toelichting een engere bereikbaarheid
    beweren dan `run()` toepast (fixronde-1-bevinding op #127). Leeg voor de andere
    aanroepers (NET-001, NET-008), die dat voorbehoud niet kennen.
    """
    netwerk = _netwerk(context)
    notities = list(_eindknoop_notitie(context, netwerk, rollen, rollen_via_gemengd))

    zonder, in_deel_met_eindpunt = _richtingsverlies(context, netwerk, rollen, rollen_via_gemengd)
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

    if not (_eindpuntset(context, rollen) | _eindpuntset(context, rollen_via_gemengd)):
        namen = [
            naam
            for rol in (*rollen, *rollen_via_gemengd)
            for naam in getattr(context.config.klassen, rol)
        ]
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
    # Rollen die alleen als geldige bestemming tellen als de streng zelf benedenstrooms
    # in gemengd riool overgaat (`_gemengd_benedenstrooms`, issue #127): NET-002
    # accepteert zo een overnamepunt of gemaal (`afvoer_eindpunt`) naast het lozingspunt.
    # Leeg voor de andere subklassen -- die kennen dit voorbehoud niet.
    eindpuntrollen_via_gemengd: tuple[str, ...] = ()
    # De leesbare naam van die eindpuntrollen, zoals hij in de melding verschijnt. Hij
    # hoort niets te noemen dat `eindpuntrollen` (of, voorwaardelijk, `eindpuntrollen_via_
    # gemengd`) niet zoekt; NET-002 beloofde tot issue #93 een overnamepunt dat alleen in
    # `afvoer_eindpunt` staat.
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
        sleutel = (
            f"onbereikbaar:{self.stelselrol}:{'+'.join(self.eindpuntrollen)}:"
            f"{'+'.join(self.eindpuntrollen_via_gemengd)}"
        )
        return context.cached(sleutel, lambda: self._bouw_onbereikbaar(context))

    def _bouw_onbereikbaar(self, context: CheckContext) -> tuple[list[tuple[Conduit, str]], bool]:
        """Loopt de strengen van dit stelseltype langs en houdt de onbereikbare over."""
        netwerk = _netwerk(context)
        endpoints: set[str] = set()
        for rol in self.eindpuntrollen:
            endpoints |= _eindpunten(context, rol)
        bereikt = _bereikbaar_vanaf(context, endpoints)

        # Issue #127: een voorwaardelijke bestemming, alleen geldig voor een streng die
        # zelf benedenstrooms in gemengd riool overgaat. Ongebruikt (lege tuple) voor de
        # andere subklassen, dus dan blijft `via_gemengd_raw` leeg en `bereikt_via_gemengd`
        # ook. `via_gemengd_raw` (vóór de gemengd-voorwaarde) is de rauwe eindpuntverzameling
        # -- die bepaalt of de graaf ÜBERHAUPT een eindpunt van dit soort draagt -- en is
        # gedeeld met `_eindpuntnotities` (via `_eindpuntset`), zodat de toelichting niet
        # een ander "geen eindpunt"-oordeel geeft dan deze vlag.
        via_gemengd_raw = _eindpuntset(context, self.eindpuntrollen_via_gemengd)
        bereikt_via_gemengd = _bereikt_via_gemengd(
            context, netwerk, self.eindpuntrollen_via_gemengd
        )

        dataset = context.dataset
        clusters = deelstelsel_ids(context)
        soorten = getattr(context.config.klassen, self.stelselrol)

        gezocht = {
            uri for wortel in soorten for uri in dataset.of_class(wortel) if uri in dataset.conduits
        }

        gevonden: list[tuple[Conduit, str]] = []
        for conduit in netwerk.conduits:
            if conduit.uri not in gezocht:
                continue
            # Dezelfde knoopafleiding als de graaf zelf (`_doorgeefknopen`, BO-83), en
            # niet `resolve_network_node`: sinds een telbaar hulpstuk doorgeeft staat een
            # streng die op een T-stuk begint in de graaf, en zou de putherleiding er
            # None voor geven en haar onvoorwaardelijk als onbereikbaar melden.
            begin, _ = _doorgeefknopen(context, conduit)
            if begin in bereikt or begin in bereikt_via_gemengd:
                continue
            # Een streng waarvan het beginpunt niet op te lossen is hoort hier thuis --
            # onbereikbaar is onbereikbaar -- maar heeft geen cluster.
            gevonden.append((conduit, clusters.get(begin, "") if begin else ""))
        return gevonden, not endpoints and not via_gemengd_raw

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er buiten de graaf viel; dat mag niet stilzwijgend verdwijnen.

        De clusterduiding staat bewust niet hier maar in het rapport: een check
        draait op de kern plus de contextschil (met een studiegebied) of op de
        volledige dataset (zonder), terwijl het rapport altijd tot de kern
        afgebakend is. Hier geteld zou de duiding het aantal deelstelsels van het
        hele werkbereik van de check melden bij de bevindingen van een enkele buurt.
        """
        return _netwerk_notities(context) + _eindpuntnotities(
            context, self.eindpuntrollen, self.eindpuntrollen_via_gemengd
        )

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
    rollen = (
        "hulpstukken",
        "lozingspunten",
        "mechanischeleidingen",
        "vrijvervalrioolleidingen",
    )
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")
    stelselrol = "vuilwater"
    eindpuntrollen = ("afvoer_eindpunt", "lozings_eindpunt")
    doel = "een gemaal, overnamepunt of lozingspunt"


@register
class HemelwaterZonderAfvoerpad(_ZonderAfvoerpad):
    """NET-002: hemelwater zonder pad naar een lozingspunt, of via gemengd naar een overnamepunt.

    Tot issue #127 telde alleen `lozings_eindpunt`, ook al noemde de titel (checkregister
    v0.9) en de oorspronkelijke docstring (issue #93) het overnamepunt niet -- terecht,
    want die rol (`afvoer_eindpunt`) werd toen niet gelezen. Een hemelwaterstreng die
    zelfstandig op een overnamepunt uitkomt is nog steeds geen afvoerpad; maar is zij
    onderweg aangesloten op een gemengd riool, dan loost het hemelwater via dat gemengde
    stelsel wél op het overnamepunt of gemaal, en is er niets mis. Dat voorbehoud legt
    `eindpuntrollen_via_gemengd` vast: `afvoer_eindpunt` telt alleen mee voor een streng
    die benedenstrooms in gemengd riool overgaat (`_gemengd_benedenstrooms`). Zie BO-88.
    """

    id = "NET-002"
    title = (
        "Hemelwaterstreng zonder afvoerpad naar een lozingspunt, of via gemengd riool "
        "naar een overnamepunt of gemaal"
    )
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = (
        "hulpstukken",
        "lozingspunten",
        "mechanischeleidingen",
        "vrijvervalrioolleidingen",
    )
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")
    stelselrol = "hemelwater"
    eindpuntrollen = ("lozings_eindpunt",)
    eindpuntrollen_via_gemengd = ("afvoer_eindpunt",)
    doel = "een lozingspunt, of via een gemengd riool een overnamepunt of gemaal"


@register
class KringloopInNetwerk(Check):
    """NET-004: cirkels in het vrijvervalnetwerk."""

    id = "NET-004"
    title = "Cirkels (kringlopen) in het vrijvervalnetwerk"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk deel van de graaf waarin een echte kringloop zit.

        Per sterk samenhangend deel een melding, niet per enkelvoudige kringloop:
        het aantal enkelvoudige kringlopen groeit exponentieel met de graafgrootte,
        en op een echt stelsel loopt dat vast. Een deel met meer dan een knoop
        bevat per definitie minstens een kringloop; van elk deel wordt een
        voorbeeldkringloop getoond.

        Richting-bewust sinds issue #102: de kring wordt op de BETROUWBARE richting
        gezocht (de strengen die NET-009 niet tegenspreekt, de richtingsbron uit #80).
        Een kring die alleen op een omgekeerd geregistreerde streng leunt, valt met de
        betrouwbare richting uiteen en wordt niet gemeld -- NET-009 draagt dat signaal
        al. Een BOB-consistente ring die vlak ligt is bewust vermaasd net (legitiem in
        vlak Nederland); een ring die alleen via een BOB-sprong omhoog in een put sluit
        hoort bij HGT-009. Beide worden gedempt en in de toelichting geteld. Zie BO-77.
        """
        te_melden, _, _ = self._kringlopen(context)
        for uri, label, putten, labels in te_melden:
            yield self.finding(
                context,
                uri,
                label,
                f"Ligt in een deel van het netwerk met {putten} putten waarin een "
                f"kringloop zit; voorbeeld: {' -> '.join(labels)}.",
                putten_in_deel=putten,
                voorbeeldkring=labels,
            )

    def _kringlopen(
        self, context: CheckContext
    ) -> tuple[list[tuple[str, str, int, list[str]]], int, int]:
        """De te melden kringen plus het aantal gedempte vermaasde en putsprong-ringen."""
        return context.cached("net004:kringlopen", lambda: self._bouw_kringlopen(context))

    def _bouw_kringlopen(
        self, context: CheckContext
    ) -> tuple[list[tuple[str, str, int, list[str]]], int, int]:
        """Zoekt de kringen op de betrouwbare richting en classificeert ze (issue #102).

        De index `per_kant` is administratief georiënteerd (van BeginpuntLeiding naar
        EindpuntLeiding), los van de config-keuze `netwerk.richting`: de betrouwbaarheid
        uit NET-009 is per definitie ten opzichte van de administratie, dus de kring
        hoort op die oriëntatie gezocht en geclassificeerd. `netwerk.strengen_per_kant`
        wordt hier bewust NIET gebruikt -- die keert kanten om bij `richting = "bob"` en
        zou dan tegen de administratieve betrouwbaarheid in wijzen.
        """
        netwerk = _netwerk(context)
        dataset = context.dataset
        betrouwbaar = _betrouwbare_richting(context)
        drempel = context.config.drempels.bob_sprong_m

        ruw: dict[tuple[str, str], list[Conduit]] = {}
        for conduit in netwerk.conduits:
            begin, eind = verbonden_knopen(context, conduit)
            if begin is None or eind is None:
                continue
            ruw.setdefault((begin, eind), []).append(conduit)
        per_kant = {
            kant: sorted(strengen, key=lambda streng: streng.uri) for kant, strengen in ruw.items()
        }

        reliable: nx.DiGraph = nx.DiGraph()
        for (begin, eind), strengen in per_kant.items():
            if any(betrouwbaar.get(streng.uri, False) for streng in strengen):
                reliable.add_edge(begin, eind)

        te_melden: list[tuple[str, str, int, list[str]]] = []
        vermaasd = putsprong = 0
        for deel in nx.strongly_connected_components(reliable):
            if len(deel) < 2 and not self._heeft_zelflus(reliable, deel):
                continue
            kring = self._voorbeeldkring(reliable.subgraph(deel))
            soort = self._klasseer(per_kant, betrouwbaar, kring, drempel)
            if soort == "vermaasd":
                vermaasd += 1
            elif soort == "putsprong":
                putsprong += 1
            else:
                labels = [self._label(dataset, uri) for uri in kring]
                uri, label = self._eerste_streng(per_kant, kring, dataset)
                te_melden.append((uri, label, len(deel), labels))
        return te_melden, vermaasd, putsprong

    def _klasseer(
        self,
        per_kant: dict[tuple[str, str], list[Conduit]],
        betrouwbaar: dict[str, bool],
        kring: list[str],
        drempel: float,
    ) -> str:
        """Classificeert een overgebleven kring: 'echte', 'vermaasd' of 'putsprong'.

        Een zelflus of een kring met een been zonder bruikbare BOB is 'echte': er is dan
        geen BOB-bewijs dat haar tot vermaasd net of een putsprong herleidt. Anders geldt
        een ring die ergens in een put omhoog springt (boven de sprongdrempel) als
        putsprong (HGT-009-terrein), en een verder vlakke of dalende ring als vermaasd.
        """
        if len(kring) < 2:
            return "echte"
        benen = self._benen(per_kant, betrouwbaar, kring)
        bobben = [
            (been.bob_start, been.bob_end) if been is not None else (None, None) for been in benen
        ]
        if any(start is None or eind is None for start, eind in bobben):
            return "echte"
        aantal = len(kring)
        for i in range(aantal):
            # In put kring[i] komt been (i-1) binnen (BOB aan het eind) en gaat been i
            # verder (BOB aan het begin). Springt de afvoerende BOB boven de aanvoerende
            # uit, dan klimt het water in de put -- een putsprong.
            bob_aanvoer = bobben[(i - 1) % aantal][1]
            bob_afvoer = bobben[i][0]
            assert bob_aanvoer is not None and bob_afvoer is not None  # gedekt door de any-check
            if bob_afvoer - bob_aanvoer > drempel:
                return "putsprong"
        return "vermaasd"

    def _benen(
        self,
        per_kant: dict[tuple[str, str], list[Conduit]],
        betrouwbaar: dict[str, bool],
        kring: list[str],
    ) -> list[Conduit | None]:
        """De betrouwbare streng op elke opeenvolgende kant van de voorbeeldkring."""
        benen: list[Conduit | None] = []
        aantal = len(kring)
        for i in range(aantal):
            kant = (kring[i], kring[(i + 1) % aantal])
            goede = [
                streng for streng in per_kant.get(kant, ()) if betrouwbaar.get(streng.uri, False)
            ]
            benen.append(goede[0] if goede else None)
        return benen

    def _heeft_zelflus(self, graaf: nx.DiGraph, deel: set[str]) -> bool:
        """Geeft aan of het enige knooppunt in dit deel naar zichzelf wijst."""
        knoop = next(iter(deel))
        return graaf.has_edge(knoop, knoop)

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
        self,
        per_kant: dict[tuple[str, str], list[Conduit]],
        kring: list[str],
        dataset: GwswDataset,
    ) -> tuple[str, str]:
        """De streng waarop de melding wordt gehangen: de eerste op de kant kring[0] -> kring[1]."""
        if len(kring) > 1:
            strengen = per_kant.get((kring[0], kring[1]), ())
            if strengen:
                return strengen[0].uri, strengen[0].label
        return kring[0], self._label(dataset, kring[0])

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de gedempte vermaasde en putsprong-ringen en wat er buiten de graaf viel."""
        _, vermaasd, putsprong = self._kringlopen(context)
        notities = _netwerk_notities(context)
        if vermaasd:
            notities.append(
                f"{getal(vermaasd, 'BOB-consistente ring', 'BOB-consistente ringen')} zonder "
                f"putsprong {vorm(vermaasd, 'geldt', 'gelden')} als bewust vermaasd net (in vlak "
                f"Nederland legitiem) en {vorm(vermaasd, 'is', 'zijn')} niet gemeld."
            )
        if putsprong:
            notities.append(
                f"{getal(putsprong, 'ring', 'ringen')} {vorm(putsprong, 'sluit', 'sluiten')} "
                "alleen via een BOB-sprong omhoog in een put; dat hoort bij HGT-009, niet bij "
                "NET-004, en is hier niet als kringloop gemeld."
            )
        return notities

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
    rollen = (
        "hulpstukken",
        "infiltratieleidingen",
        "overstortputten",
        "vrijvervalrioolleidingen",
    )
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


# NET-003 (strengorientatie tegen de afvoerrichting) is per issue #80 opgegaan in NET-009
# en vervallen; het ID wordt niet hergebruikt. De BOB-tegen-richting is nu een deelgeval
# van de integrale richtingscheck hieronder.

_RICHTING_MEE = "mee"
_RICHTING_TEGEN = "tegen"
_RICHTING_VLAK = "vlak"
_RICHTING_ONBEKEND = "onbekend"


@dataclass(frozen=True)
class _Richtingsdiagnose:
    """De drie richtingssignalen van een streng, elk ten opzichte van de administratie.

    `geometrie` en `bob` zeggen of dat signaal met de administratieve van-naar-richting
    meeloopt (`mee`), er tegenin (`tegen`), niet te bepalen is (`onbekend`) of -- alleen
    de BOB -- vlak ligt (`vlak`). De administratie zelf is de referentie: van
    `begin_label` naar `eind_label`.
    """

    conduit: Conduit
    begin_label: str
    eind_label: str
    geometrie: str
    bob: str
    bob_verval: float | None


def _knooplabel(context: CheckContext, uri: str | None) -> str:
    """Het label van de knoop boven een strengkoppeling, of de URI als er geen label is."""
    dataset = context.dataset
    knoop = dataset.resolve_network_node(uri, context.config.klassen.netwerkknopen)
    # Een streng die op een telbaar hulpstuk eindigt zit sinds BO-83 in de graaf en wordt
    # dus door NET-009 beoordeeld; zonder deze terugval noemt de melding daar een lege
    # naam ("van 'A' naar ''") in plaats van het T-stuk waar zij werkelijk op uitkomt.
    if knoop is None and uri is not None and uri in telbare_hulpstukken(context):
        knoop = uri
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


def _richtingsdiagnoses(context: CheckContext) -> list[_Richtingsdiagnose]:
    """De richtingssignalen per streng in de graaf; een keer per context."""
    return context.cached("net009", lambda: _bouw_richtingsdiagnoses(context))


def _bouw_richtingsdiagnoses(context: CheckContext) -> list[_Richtingsdiagnose]:
    """Bepaalt per aangesloten vrijvervalstreng haar drie richtingssignalen."""
    drempel = context.config.drempels.tegenverhang_licht_m
    return [
        _Richtingsdiagnose(
            conduit=conduit,
            begin_label=_knooplabel(context, conduit.start_node),
            eind_label=_knooplabel(context, conduit.end_node),
            geometrie=_geometrie_richting(context, conduit),
            bob=_bob_richting(conduit, drempel),
            bob_verval=conduit.bob_verval,
        )
        for conduit in _netwerk(context).conduits
    ]


def _tegenspraak(diagnose: _Richtingsdiagnose) -> bool:
    """Geeft aan of een van de signalen tegen de administratie in wijst.

    De administratie is de referentie (altijd 'mee'), dus er is tegenspraak zodra de
    geometrie of de BOB de andere kant op wijst. Twee tegen-signalen die het onderling
    eens zijn spreken de administratie nog steeds tegen -- de streng lijkt dan omgekeerd
    geregistreerd.
    """
    return _RICHTING_TEGEN in (diagnose.geometrie, diagnose.bob)


def _geen_signaal(diagnose: _Richtingsdiagnose) -> bool:
    """Geeft aan of noch de geometrie noch de BOB iets over de richting zegt."""
    return diagnose.geometrie == _RICHTING_ONBEKEND and diagnose.bob == _RICHTING_ONBEKEND


def _richting_op_knoop(knoop: str, begin: str | None, eind: str | None, betrouwbaar: bool) -> str:
    """Of de streng op deze knoop instroomt ('in'), uitstroomt ('uit') of onbekend is.

    Alleen bij een betrouwbare administratieve richting; een streng met een put aan
    beide zijden gelijk (zelflus) of een onbetrouwbare richting levert '?' en telt als
    onbekend, zodat de koppeling niet ten onrechte gedempt wordt.
    """
    if not betrouwbaar or begin == eind:
        return "?"
    if knoop == eind:
        return "in"
    if knoop == begin:
        return "uit"
    return "?"


def _betrouwbaar_gericht(diagnose: _Richtingsdiagnose) -> bool:
    """Geeft aan of de administratieve richting van deze streng te vertrouwen is.

    De richtingsbron van blok I (issue #97, #102): #80/BO-76 leverde geen herbruikbare
    afvoerrichting op, maar NET-009's per-streng oordeel wel. Een streng is betrouwbaar
    gericht als geen enkel signaal de administratie tegenspreekt en er minstens een
    signaal is dat haar bevestigt -- precies de strengen die NET-009 niet meldt en die
    niet zonder enig richtingssignaal zijn.
    """
    return not _tegenspraak(diagnose) and not _geen_signaal(diagnose)


def _betrouwbare_richting(context: CheckContext) -> dict[str, bool]:
    """Per streng-URI of haar administratieve van-naar-richting betrouwbaar is."""
    return {d.conduit.uri: _betrouwbaar_gericht(d) for d in _richtingsdiagnoses(context)}


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


@register
class RichtingssignalenSprekenElkaarTegen(Check):
    """NET-009: administratie, geometrie en BOB wijzen niet dezelfde kant op."""

    id = "NET-009"
    title = "Richtingssignalen (administratie, geometrie, BOB) spreken elkaar tegen"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke streng waarvan de drie richtingssignalen elkaar tegenspreken.

        De integrale richtingscheck (issue #80): de administratieve van-naar-richting is
        de referentie, en zodra de geometrie of de BOB de andere kant op wijst is er een
        W. Wijzen administratie, tekenrichting én BOB dezelfde kant op, dan is de streng
        goed. De melding noemt alle drie de waarden, zodat de beheerder zelf ziet welke
        fout is. NET-003 (BOB tegen) en TOP-020 (tekenrichting tegen) gingen hierin op en
        vervielen als aparte checks.

        De ongerichte-graaf "harde waarheid" uit een bereikbaar lozingspunt is bewust
        weggelaten (BO-76): op De Wolden gaf zij 2.822 vals-alarmen op strengen die intern
        kloppen -- de topologisch dichtstbijzijnde uitstroom is vaak niet de werkelijke,
        en drie eensgezinde signalen wegen zwaarder dan die heuristiek.
        """
        for diagnose in _richtingsdiagnoses(context):
            if not _tegenspraak(diagnose):
                continue
            boodschap = (
                "De richtingssignalen spreken elkaar tegen. Administratief loopt de "
                f"streng van {diagnose.begin_label!r} naar {diagnose.eind_label!r}. "
                f"{_geometrie_zin(diagnose.geometrie)} "
                f"{_bob_zin(diagnose.bob, diagnose.bob_verval)}"
            )
            yield self.finding(
                context,
                diagnose.conduit.uri,
                diagnose.conduit.label,
                boodschap,
                geometrie=diagnose.geometrie,
                bob=diagnose.bob,
                bob_verval_m=round(diagnose.bob_verval, 3)
                if diagnose.bob_verval is not None
                else None,
                administratief_begin=diagnose.begin_label,
                administratief_eind=diagnose.eind_label,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de vlakke strengen ('geen uitspraak') en de BOB's die als vulwaarde wegvielen."""
        diagnoses = _richtingsdiagnoses(context)
        notities = _netwerk_notities(context)

        vlak = sum(1 for d in diagnoses if not _tegenspraak(d) and d.bob == _RICHTING_VLAK)
        if vlak:
            drempel = context.config.drempels.tegenverhang_licht_m
            notities.append(
                f"{getal(vlak, 'streng', 'strengen')} {vorm(vlak, 'ligt', 'liggen')} vlak "
                f"(|verval| ≤ {drempel} m): de BOB zegt niets over de richting, dus deze toets "
                f"doet daar geen uitspraak over."
            )

        vulwaarde = sum(1 for d in diagnoses if d.conduit.vulwaarden)
        if vulwaarde:
            notities.append(
                f"{getal(vulwaarde, 'streng', 'strengen')} {vorm(vulwaarde, 'heeft', 'hebben')} "
                "een BOB die als vulwaarde (rond 0 m NAP) is gelezen en daardoor ontbreekt; "
                "hun richting kon niet op de BOB getoetst worden."
            )

        geen_signaal = sum(1 for d in diagnoses if _geen_signaal(d))
        if geen_signaal:
            notities.append(
                f"{getal(geen_signaal, 'streng', 'strengen')} "
                f"{vorm(geen_signaal, 'draagt', 'dragen')} geen bruikbare tekenrichting en geen "
                "BOB, dus met geen enkel richtingssignaal te toetsen; deze strengen zijn niet "
                "beoordeeld."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """De strengen met minstens een richtingssignaal; de rest kon niet beoordeeld worden."""
        return sum(1 for d in _richtingsdiagnoses(context) if not _geen_signaal(d))


@register
class StelseltypeWijktAfVanBuren(Check):
    """NET-005: een streng met een ander stelseltype dan al haar buren."""

    id = "NET-005"
    title = "Stelseltype streng wijkt af van boven- en benedenstroomse buren"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    rollen = ("hulpstukken", "vrijvervalrioolleidingen")
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


@dataclass
class _Koppelknoop:
    """Een knoop met minstens één gerichte koppeling die de koppelregels overtreedt.

    `verschillen` draagt de (bovenstroom, benedenstroom)-paren die niet in de whitelist
    staan; `boven_labels`/`beneden_labels` de strenglabels per stelseltype dat op de knoop
    in- respectievelijk uitstroomt, zodat de melding de betrokken strengen kan noemen.
    """

    uri: str
    verschillen: tuple[tuple[str, str], ...]
    boven_labels: dict[str, tuple[str, ...]]
    beneden_labels: dict[str, tuple[str, ...]]


# NET-006 (issue #129, BO-92): de koppeling hemelwater -> vuilwater staat sinds dit issue
# niet meer onvoorwaardelijk in de koppelregels (uit beide configs gehaald), maar is alleen
# toegestaan binnen een Verbeterd Gescheiden Stelsel. Alleen deze ene cel is voorwaardelijk;
# de rest van de matrix volgt de whitelist. De tags zijn de stelseltype-tags uit
# `[koppelregels]`/`[klassen.stelseltypen]`.
_VGS_KOPPELING = ("hemelwater", "vuilwater")


def _vgs_instanties(context: CheckContext) -> tuple[str, ...]:
    """De expliciete `gwsw:VerbeterdGescheidenStelsel`-instanties in de dataset.

    `VerbeterdGescheidenStelsel` is in de GWSW-ontologie een `Systeem`
    (VerbeterdGescheidenStelsel < GescheidenSysteem < Systeem), géén subklasse van `Stelsel`
    -- die twee zijn zusters onder `FysiekObject`. `context.stelsels_van` leest de rol
    `stelsels` (`[klassen] stelsel`, wortel `Stelsel`) en ziet een VGS daardoor structureel
    niet: op De Wolden en Hoogeveen levert `subjects_of_class("Stelsel")` 276 instanties, alle
    uit de Stelsel-tak (Rioolstelsel, Vuilwaterstelsel, ...), en nul uit de Systeem-tak. NET-006
    leest de VGS-instanties daarom rechtstreeks -- `subjects_of_class` over de typesluiting van
    `[klassen] vgs` -- precies zoals NET-007 zijn drempels via `[klassen] drempel` leest. De
    impliciete gepaarde-rioleringsgebied-variant doen we bewust niet: GWSW is leidend en de
    ontologie legt VGS niet zo. Zie issue #129 en BO-92.
    """

    def bouw() -> tuple[str, ...]:
        """De unieke VGS-instantie-URI's over de typesluiting van `[klassen] vgs`."""
        gevonden = {
            str(subject)
            for wortel in context.config.klassen.vgs
            for subject in context.dataset.subjects_of_class(wortel)
        }
        return tuple(sorted(gevonden))

    return context.cached("net006:vgs-instanties", bouw)


def _vgs_leden(context: CheckContext) -> frozenset[str]:
    """De knopen en strengen die in een expliciet Verbeterd Gescheiden Stelsel liggen.

    De directe `hasPart`-leden (`stelsel_leden`, één hop) van elke VGS-instantie uit
    `_vgs_instanties`. Let op de single-hop-aanname: een echte export die een VGS genest legt
    (VGS -> sub-stelsels -> objecten, twee hops) zou hier leeg blijven; `notes()` maakt dat
    voorbehoud luid. Zie BO-92.
    """

    def bouw() -> frozenset[str]:
        """Verzamelt de leden over alle VGS-instanties in de dataset."""
        leden: set[str] = set()
        for subject in _vgs_instanties(context):
            strengen, knopen = context.dataset.stelsel_leden(subject)
            leden.update(strengen)
            leden.update(knopen)
        return frozenset(leden)

    return context.cached("net006:vgs-leden", bouw)


@register
class KoppelingTussenStelseltypen(Check):
    """NET-006: een gerichte koppeling tussen stelseltypen die de koppelregels overtreedt."""

    id = "NET-006"
    title = "Koppelingen tussen verschillende stelseltypen"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("hulpstukken", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding", "config:koppelregels")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke knoop met een gerichte koppeling die de koppelregels overtreedt.

        Sinds issue #126 leunt de check op de whitelist `[koppelregels]` (bovenstroom-tag →
        toegestane benedenstroom-tags) in plaats van op de ad-hoc gemengd+vuilwater-regel
        van issue #97. Per knoop wordt gekeken welke stelseltypen er *binnenstromen* en welke
        er *uitstromen* -- alleen bij een betrouwbare stroomrichting (`_betrouwbare_richting`,
        de richtingsbron uit #80). Een gerichte koppeling `boven → beneden` is een bevinding
        als `beneden` niet in `koppelregels[boven]` staat. De bevinding staat op de knoop,
        want daar zit de koppeling.

        Eén cel is sinds issue #129 voorwaardelijk: `hemelwater → vuilwater` staat niet meer
        in de whitelist (uit beide configs gehaald), maar is wél toegestaan binnen een
        Verbeterd Gescheiden Stelsel. Ligt de koppelknoop in een expliciete
        `gwsw:VerbeterdGescheidenStelsel`-instantie (`_vgs_leden`), dan vervalt die ene cel;
        anders is hemelwater op een vuilwaterriool een bevinding. Zie BO-92.

        Wat NIET beoordeeld wordt, meldt `notes()`: koppelingen waarvan de richting niet
        betrouwbaar is (dan valt niet te zeggen wat boven- en wat benedenstrooms ligt) en
        strengen zonder herkenbaar stelseltype. Tags buiten de zeven mediumbepalende
        (drainage, transport) vallen buiten de whitelist en worden niet gericht getoetst.
        """
        dataset = context.dataset
        knopen, _ = self._koppelingen(context)
        for knoop in knopen:
            node = dataset.nodes.get(knoop.uri)
            delen = [
                f"{boven} → {beneden} "
                f"({', '.join(knoop.boven_labels[boven])} → "
                f"{', '.join(knoop.beneden_labels[beneden])})"
                for boven, beneden in knoop.verschillen
            ]
            yield self.finding(
                context,
                knoop.uri,
                node.label if node is not None else knoop.uri,
                "Ongeldige koppeling tussen stelseltypen: "
                f"{'; '.join(delen)}. Deze gerichte koppeling staat niet in de koppelregels.",
                koppelingen=[f"{boven}→{beneden}" for boven, beneden in knoop.verschillen],
            )

    def _koppelingen(self, context: CheckContext) -> tuple[list[_Koppelknoop], int]:
        """De te melden koppelknopen plus het aantal niet gericht beoordeelde knopen.

        `run()` meldt en `notes()` duidt; beide hebben zowel de meldingen als de telling
        van het onbeoordeelde nodig, dus staat de beslissing hier een keer.
        """
        return context.cached("net006:koppelingen", lambda: self._bouw_koppelingen(context))

    def _bouw_koppelingen(self, context: CheckContext) -> tuple[list[_Koppelknoop], int]:
        """Bepaalt per knoop de gerichte koppelingen en toetst ze tegen de whitelist."""
        netwerk = _netwerk(context)
        regels = context.config.koppelregels
        in_scope = set(regels)
        betrouwbaar = _betrouwbare_richting(context)
        vgs_leden = _vgs_leden(context)

        instroom: dict[str, dict[str, list[str]]] = {}
        uitstroom: dict[str, dict[str, list[str]]] = {}
        typen_per_knoop: dict[str, set[str]] = {}
        onbetrouwbaar_bij: set[str] = set()
        for conduit in netwerk.conduits:
            soort = _stelseltype(context, conduit)
            if soort is None:
                continue
            begin, eind = verbonden_knopen(context, conduit)
            reliable = betrouwbaar.get(conduit.uri, False)
            for uri in (begin, eind):
                if uri is None:
                    continue
                typen_per_knoop.setdefault(uri, set()).add(soort)
                if not reliable:
                    onbetrouwbaar_bij.add(uri)
                richting = _richting_op_knoop(uri, begin, eind, reliable)
                if richting == "in":
                    instroom.setdefault(uri, {}).setdefault(soort, []).append(conduit.label)
                elif richting == "uit":
                    uitstroom.setdefault(uri, {}).setdefault(soort, []).append(conduit.label)

        knopen: list[_Koppelknoop] = []
        onbeoordeeld = 0
        for uri in sorted(typen_per_knoop):
            boven = instroom.get(uri, {})
            beneden = uitstroom.get(uri, {})
            verschillen = [
                (a, b)
                for a in sorted(boven)
                if a in in_scope
                for b in sorted(beneden)
                if b in in_scope and b not in regels[a]
            ]
            # Issue #129/BO-92: hemelwater -> vuilwater staat niet meer in de koppelregels,
            # maar is toegestaan binnen een Verbeterd Gescheiden Stelsel. Ligt deze knoop in
            # een VGS, dan vervalt juist die ene cel; de rest van de matrix blijft gelden.
            if uri in vgs_leden:
                verschillen = [paar for paar in verschillen if paar != _VGS_KOPPELING]
            if verschillen:
                knopen.append(
                    _Koppelknoop(
                        uri,
                        tuple(verschillen),
                        {soort: tuple(labels) for soort, labels in boven.items()},
                        {soort: tuple(labels) for soort, labels in beneden.items()},
                    )
                )
            elif len(typen_per_knoop[uri] & in_scope) >= 2 and uri in onbetrouwbaar_bij:
                # Twee in-scope typen komen samen, maar door een onbetrouwbare richting was
                # de koppeling niet in een richting te leggen: niet beoordeeld, geen stille
                # groen. Zie `notes()`.
                onbeoordeeld += 1
        return knopen, onbeoordeeld

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat niet gericht beoordeeld kon worden en de typeloze strengen."""
        _, onbeoordeeld = self._koppelingen(context)
        notities = _stelseltype_notities(context)
        if onbeoordeeld:
            notities.insert(
                0,
                f"Op {getal(onbeoordeeld, 'knoop', 'knopen')} komen verschillende stelseltypen "
                "samen zonder betrouwbare stroomrichting; die koppelingen zijn niet gericht "
                "tegen de koppelregels getoetst.",
            )
        # Issue #129/BO-92: de uitzondering hemelwater->vuilwater geldt alleen binnen een VGS.
        # Wat de check daarvoor NIET zag hoort in het rapport: het VGS-lidmaatschap is als de
        # directe hasPart-leden gelezen (één hop), dus een genest gelegde VGS (VGS -> sub-
        # stelsels -> objecten) wordt niet herkend. Bij nul VGS-instanties is de uitzondering
        # inert en meldt NET-006 elke hemelwater->vuilwater-koppeling.
        vgs = len(_vgs_instanties(context))
        notities.append(
            f"De koppeling hemelwater→vuilwater is alleen binnen een Verbeterd Gescheiden "
            f"Stelsel toegestaan; het lidmaatschap is gelezen als de directe hasPart-leden van "
            f"{getal(vgs, 'VGS-instantie', 'VGS-instanties')} in de dataset. Een genest gelegde "
            "VGS (VGS → sub-stelsels → objecten) wordt zo niet herkend."
        )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal beoordeelde knopen in de graaf, zonder de doorgeefhulpstukken."""
        return len(putknopen(context, _netwerk(context).graph))


@register
class VeelLozingspuntenInDeelstelsel(Check):
    """NET-008: opvallend veel lozingspunten in een klein deelstelsel."""

    id = "NET-008"
    title = "Opvallend veel lozingspunten binnen een klein deelstelsel"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = (
        "hulpstukken",
        "lozingspunten",
        "mechanischeleidingen",
        "vrijvervalrioolleidingen",
    )
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
            # "Klein" gaat over de beoordeelde knopen: een doorgeefhulpstuk is geen put,
            # en zou een T-stukrijk deelstelsel over de drempel duwen (BO-83).
            putten = len(putknopen(context, deel))
            if putten > drempels.klein_deelstelsel_knopen:
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
                    f"{putten} knopen (maximaal {drempels.lozingspunten_per_deelstelsel} "
                    f"bij ten hoogste {drempels.klein_deelstelsel_knopen} knopen): "
                    f"{', '.join(labels)}.",
                    knopen_in_deelstelsel=putten,
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
        """Het aantal beoordeelde knopen in de graaf, zonder de doorgeefhulpstukken."""
        return len(putknopen(context, _netwerk(context).graph))


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
