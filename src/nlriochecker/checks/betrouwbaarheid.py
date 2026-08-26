"""BTR-checks: betrouwbaarheid en metagegevens van de hoogtewaarden.

BTR-001 t/m BTR-005 hangen aan inwinningsmetagegevens (wijze en datum van
inwinning, grondwaterstand, inspectiedata) en staan hier als skelet: ze zijn in
deze fase niet gebouwd, en zonder gevulde metagegevens zouden ze alleen
ontbreken-meldingen opleveren. Zie het register, open punt 8.

BTR-006 is de uitzondering: die werkt op de waarden zelf en is wel gebouwd.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    SkeletonCheck,
    register,
)
from nlriochecker.checks.selectie import netwerkknopen, vrijvervalrioolleidingen

MARKERING_METAGEGEVENS = "vereist inwinningsmetagegevens"


class _Metagegevensskelet(SkeletonCheck):
    """Basis voor de BTR-skeletten die op inwinningsmetagegevens wachten."""

    markering = MARKERING_METAGEGEVENS


@register
class HoogteZonderInwinningsmetagegevens(_Metagegevensskelet):
    """BTR-001: kritieke hoogtekenmerken zonder inwinningsmetagegevens."""

    id = "BTR-001"
    title = (
        "Kritieke hoogtekenmerken (BOB, dekselniveau, drempelniveau) zonder inwinningsmetagegevens"
    )
    severity = Severity.WARNING
    dimension = Dimension.TRACEABILITY
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    reden = (
        "Niet gebouwd in deze fase. De De Wolden en Hoogeveen-export bevat 25.546 keer "
        "`WijzeVanInwinning` en geen enkele `DatumInwinning`, dus de datumhelft van deze "
        "check is er sowieso niet. De wijze is er wel, maar zo dun dat een toets vrijwel "
        "alles zou melden: 266 van de 23.440 BOB's aan het beginpunt en 271 aan het "
        "eindpunt hebben er een, 10.050 van de 22.363 maaiveldhoogten (waarvan 4.875 op "
        "het kenmerk zelf en 5.175 pas via de terugval op het Punt-aspect, zie HGT-001), "
        "en `Putdekselniveau` komt in deze export helemaal niet voor. Dat is een "
        "eigenschap van de bronexport en geen gebrek per object. Zie het register, open "
        "punt 8."
    )


@register
class InwinningNietGemeten(_Metagegevensskelet):
    """BTR-002: kritieke kenmerken geschat of ontworpen in plaats van gemeten."""

    id = "BTR-002"
    title = "Kritieke kenmerken ingewonnen via schatting, plan of ontwerp in plaats van meting"
    severity = Severity.WARNING
    dimension = Dimension.TRACEABILITY
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    reden = (
        "Niet gebouwd in deze fase. De inwinningswijze staat in De Wolden en Hoogeveen wel op de "
        "kritieke hoogtekenmerken, maar op te weinig ervan om een uitslag op te baseren: "
        "537 van de 46.880 BOB's en 10.050 van de 22.363 maaiveldhoogten. Van die laatste "
        "zijn er 5.104 uit het AHN afgeleid en 1.351 met de waarde NietAchterhaald, dus "
        "geschat noch gemeten. Deze check wordt zinvol zodra een export de wijze op de "
        "BOB's zelf meelevert."
    )


@register
class InwinningsdatumTeOud(_Metagegevensskelet):
    """BTR-003: BOB's die te lang geleden zijn ingewonnen."""

    id = "BTR-003"
    title = "Inwinningsdatum BOB ouder dan drempel, afhankelijk van grondsoort"
    severity = Severity.WARNING
    dimension = Dimension.TIMELINESS
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    reden = (
        "Niet gebouwd in deze fase. Er is geen enkele `DatumInwinning` in de "
        "De Wolden en Hoogeveen-export, en er is geen grondsoortenkaart aangeleverd om de drempel "
        "(zand 40 jaar, veen 10 jaar) op te differentieren."
    )


@register
class GrondwaterstandBuitenBereik(_Metagegevensskelet):
    """BTR-004: een grondwaterstand boven maaiveld of onwaarschijnlijk diep."""

    id = "BTR-004"
    title = "Geregistreerde grondwaterstand boven maaiveld of meer dan 5 m onder maaiveld"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("netwerkknopen",)
    kenmerken = ()
    reden = (
        "Niet gebouwd in deze fase. De De Wolden en Hoogeveen-export bevat geen enkel "
        "`Grondwaterniveau`-kenmerk; er valt niets te toetsen."
    )


@register
class ToestandsgegevensTeOud(_Metagegevensskelet):
    """BTR-005: inspectiegegevens die te oud zijn voor de risicoligging."""

    id = "BTR-005"
    title = "Toestands- of inspectiegegevens ouder dan drempel, gewogen naar risicoligging"
    severity = Severity.WARNING
    dimension = Dimension.TIMELINESS
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    reden = (
        "Niet gebouwd in deze fase. De export bevat geen inspectie- of toestandsgegevens, "
        "en de weging naar risicoligging (spoor, dijk, wegfunctie) vraagt bronnen die niet "
        "aangeleverd zijn."
    )


@register
class SystematischAfgerondeHoogtewaarden(Check):
    """BTR-006: hoogtewaarden die op ronde getallen clusteren."""

    id = "BTR-006"
    title = (
        "Systematisch afgeronde hoogtewaarden: BOB's of dekselhoogten clusteren op ronde waarden"
    )
    severity = Severity.WARNING
    dimension = Dimension.PRECISION
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte", "Putdekselniveau")
    # `examined()` telt hoogtewaarden en geen objecten: een streng draagt er twee (beide
    # BOB's) en een knoop hooguit twee (deksel en maaiveld). Zie issue #77.
    telt_instanties = True

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meet per kenmerksoort welk deel van de waarden op het raster valt.

        Als vrijwel alle BOB's op hele of halve decimeters vallen, zijn ze geschat
        en niet gemeten. Dat is geen gebrek per waarde maar een eigenschap van de
        verzameling; de bevinding hangt daarom aan de dataset als geheel, met een
        vertegenwoordigend object erbij.
        """
        drempels = context.config.drempels
        raster = drempels.afronding_raster_m
        aandeel_drempel = drempels.afronding_aandeel_procent
        minimum = drempels.afronding_minimum_waarnemingen

        for naam, waarden, voorbeeld in self._reeksen(context):
            if len(waarden) < minimum:
                continue
            op_raster = sum(1 for waarde in waarden if _op_raster(waarde, raster))
            aandeel = 100.0 * op_raster / len(waarden)
            if aandeel < aandeel_drempel:
                continue
            uri, label = voorbeeld
            yield self.finding(
                context,
                uri,
                label,
                f"{aandeel:.1f}% van de {len(waarden)} {naam} valt precies op een raster van "
                f"{raster:g} m ({op_raster} van {len(waarden)}, drempel "
                f"{aandeel_drempel:g}%). Dat wijst op geschatte in plaats van gemeten waarden.",
                kenmerk=naam,
                aantal=len(waarden),
                op_raster=op_raster,
                aandeel_procent=round(aandeel, 2),
                raster_m=raster,
            )

    def _reeksen(self, context: CheckContext):
        """De hoogtereeksen die op afronding getoetst worden, met een voorbeeld erbij."""
        strengen = vrijvervalrioolleidingen(context)
        knopen = netwerkknopen(context)

        bobs = [
            waarde
            for conduit in strengen
            for waarde in (conduit.bob_start, conduit.bob_end)
            if waarde is not None
        ]
        if bobs and strengen:
            yield "BOB-waarden", bobs, (strengen[0].uri, strengen[0].label)

        for naam, kies in (
            ("putdekselniveaus", lambda node: node.dekselniveau),
            ("maaiveldhoogten", lambda node: node.maaiveld),
        ):
            waarden = [kies(node) for node in knopen if kies(node) is not None]
            if waarden and knopen:
                yield naam, waarden, (knopen[0].uri, knopen[0].label)

    def notes(self, context: CheckContext) -> list[str]:
        """Beschrijft per reeks hoeveel waarden er zijn en welk deel op het raster valt."""
        raster = context.config.drempels.afronding_raster_m
        regels = [
            "De bevinding hangt aan een vertegenwoordigend object; het gaat om de reeks als "
            "geheel, niet om dat ene object.",
            f"Gemeten over {context.scope_in_woorden()}: BTR-006 heeft geen "
            "`volledig_bereik`, want het representatieve object zou anders uit de kern "
            "kunnen wegvallen en de bevinding met een studiegebied ongemerkt uit het "
            "rapport laten verdwijnen.",
        ]
        for naam, waarden, _ in self._reeksen(context):
            op_raster = sum(1 for waarde in waarden if _op_raster(waarde, raster))
            aandeel = 100.0 * op_raster / len(waarden) if waarden else 0.0
            veelvoorkomend = _laatste_decimalen(waarden)
            regels.append(
                f"{naam}: {len(waarden)} waarden, {aandeel:.1f}% op een raster van "
                f"{raster:g} m; meest voorkomende laatste twee decimalen: {veelvoorkomend}."
            )
        return regels

    def examined(self, context: CheckContext) -> int:
        """Het aantal hoogtewaarden dat bekeken is."""
        return sum(len(waarden) for _, waarden, _ in self._reeksen(context))


def _op_raster(waarde: float, raster: float) -> bool:
    """Geeft aan of een waarde precies op een veelvoud van het raster valt."""
    if raster <= 0:
        return False
    rest = abs(waarde / raster - round(waarde / raster))
    return rest < 1e-6


def _laatste_decimalen(waarden: list[float], top: int = 3) -> str:
    """De meest voorkomende laatste twee decimalen, als leesbare opsomming."""
    telling = Counter(f"{abs(waarde) % 1:.2f}"[2:] for waarde in waarden)
    return (
        ", ".join(f"{staart} ({aantal}x)" for staart, aantal in telling.most_common(top)) or "geen"
    )
