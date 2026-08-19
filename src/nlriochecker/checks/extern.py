"""EXT-checks en de AHN-hoogtechecks: toetsing tegen externe bronnen.

Alle bronnen in `data/gis_koekangerveld/` dekken uitsluitend het studiegebied
Koekangerveld, terwijl de GWSW-dataset de hele gemeente De Wolden beslaat. Een GWSW-object daar
buiten krijgt daarom geen uitslag maar de status *buiten studiegebied*: dat er geen
BGT-deksel of BAG-pand naast ligt zegt daar niets over de datakwaliteit en alles
over de dekking van de bron. Elke check meldt in haar toelichting hoeveel objecten
om die reden buiten beschouwing bleven.

De typeringspoort telt hier zwaarder dan in de interne checks: een te globaal
getypeerd object krijgt geen uitslag maar de markering *niet betrouwbaar toetsbaar*,
en wordt in de toelichting geteld. De nulmeting verklaart haar eigen
vervolgvalidaties voor zulke objecten immers onbetrouwbaar.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    SkeletonCheck,
    register,
)
from nlriochecker.checks.selectie import lozingspunten, netwerkknopen, vrijvervalrioolleidingen
from nlriochecker.checks.treffers import Treffer, bouw_sleutel
from nlriochecker.checks.verbanden import verbonden_knopen
from nlriochecker.dataset import Node
from nlriochecker.taal import getal, met_lidwoord

MARKERING_BUITEN_SCOPE = "bron buiten scope in deze fase"
MARKERING_NIET_TOETSBAAR = "niet betrouwbaar toetsbaar"

# Het URI-voorvoegsel per bron-rol; de sleutel van een treffer wordt
# `<voorvoegsel>/<bron-id>`. Zie `checks/treffers.py` voor de terugval.
VOORVOEGSEL = {
    "bgt_pand": "bgt:pand",
    "bag_pand": "bag:pand",
    "bgt_bouwwerk": "bgt:bouwwerk",
    "bgt_water": "bgt:waterdeel",
}

MARKERING_ZONDER_ID = (
    "Een of meer geraakte objecten komen uit een bron zonder identificatie; die dragen "
    "een sleutel op grond van hun geometrie (`geo:...`) in plaats van hun bron-ID."
)


def _notitie_zonder_id(context: CheckContext, check_id: str) -> list[str]:
    """De toelichting bij bronnen die geen identificatie dragen, of niets.

    `run()` draait voor `notes()` in `run_checks`, dus wat de check tijdens het
    draaien in het register meldde staat hier al klaar.
    """
    bronbestanden = context.treffers.zonder_id(check_id)
    if not bronbestanden:
        return []
    return [f"{MARKERING_ZONDER_ID} Betreft: {', '.join(bronbestanden)}."]


@dataclass(frozen=True)
class _Selectie:
    """De objecten waarover een externe check wel en niet iets mag zeggen."""

    toetsbaar: list
    buiten_gebied: int
    onbetrouwbaar: int
    zonder_geometrie: int

    @property
    def totaal(self) -> int:
        """Het aantal objecten dat de check heeft bekeken."""
        return len(self.toetsbaar) + self.buiten_gebied + self.onbetrouwbaar + self.zonder_geometrie


def _selecteer(context: CheckContext, objecten, geometrie_van) -> _Selectie:
    """Splitst objecten in toetsbaar, buiten het gebied en niet betrouwbaar getypeerd."""
    bronnen = context.bronnen
    toetsbaar: list = []
    buiten = onbetrouwbaar = zonder = 0

    for object_ in objecten:
        geometrie = geometrie_van(object_)
        if geometrie is None or geometrie.is_empty:
            zonder += 1
            continue
        if bronnen is None or not bronnen.binnen_bereik(geometrie):
            buiten += 1
            continue
        if not context.is_reliable(object_.uri):
            onbetrouwbaar += 1
            continue
        toetsbaar.append(object_)

    return _Selectie(
        toetsbaar=toetsbaar,
        buiten_gebied=buiten,
        onbetrouwbaar=onbetrouwbaar,
        zonder_geometrie=zonder,
    )


def _bereiknotities(context: CheckContext, selectie: _Selectie, soort: str) -> list[str]:
    """Beschrijft wat er buiten deze check viel en waarom."""
    if context.bronnen is None:
        return [
            "Er zijn geen externe bronnen geladen (`--bronnen`); deze check heeft niets "
            "kunnen toetsen."
        ]
    if context.bronnen.extent is None:
        return [
            "Er is geen begrenzingspolygoon geladen. Zonder begrenzing is niet vast te "
            "stellen waar de externe bronnen wel en niet dekken, en mag geen enkele "
            "EXT-check een uitslag geven; er is dus niets getoetst."
        ]
    notities = [
        f"Getoetst: {len(selectie.toetsbaar)} van de {selectie.totaal} {soort}.",
    ]
    if selectie.buiten_gebied:
        gebied = context.bronnen.extent_name or "het bereik van de externe bronnen"
        notities.append(
            f"Buiten studiegebied: {selectie.buiten_gebied} van de {selectie.totaal} {soort} "
            f"liggen buiten {gebied} en krijgen geen uitslag. De aangeleverde bronnen dekken "
            "daar niets, dus het ontbreken van een tegenhanger is er geen bevinding."
        )
    if selectie.onbetrouwbaar:
        notities.append(
            f"Markering *{MARKERING_NIET_TOETSBAAR}*: {selectie.onbetrouwbaar} van de "
            f"{selectie.totaal} {soort} krijgen geen uitslag omdat de nulmeting hun klasse "
            "te globaal noemt en haar eigen vervolgvalidaties daarop onbetrouwbaar verklaart."
        )
    if selectie.zonder_geometrie:
        notities.append(
            f"Zonder bruikbare geometrie: {selectie.zonder_geometrie} van de "
            f"{selectie.totaal} {soort}."
        )
    return notities


class _ExterneCheck(Check):
    """Basis voor de checks die een externe laag nodig hebben."""

    rol: str = ""
    soort: str = "objecten"

    def objecten(self, context: CheckContext) -> list:
        """De GWSW-objecten die deze check bekijkt."""
        raise NotImplementedError

    def geometrie_van(self, object_):
        """De geometrie waarmee dit object in het platte vlak ligt.

        Een streng heeft een lijn, een knoop een punt; welke van de twee het is
        wordt hier expliciet uitgezocht in plaats van op de waarheidswaarde van een
        shapely-geometrie te leunen.
        """
        for naam in ("line", "point"):
            geometrie = getattr(object_, naam, None)
            if geometrie is not None and not geometrie.is_empty:
                return geometrie
        return None

    def selectie(self, context: CheckContext) -> _Selectie:
        """De toetsbare objecten, een keer per context bepaald."""
        return context.cached(
            f"ext:selectie:{self.id}",
            lambda: _selecteer(context, self.objecten(context), self.geometrie_van),
        )

    def laag(self, context: CheckContext):
        """De externe laag die deze check nodig heeft, of None."""
        return context.bronnen.layer(self.rol) if context.bronnen is not None else None

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt het bereik en of de benodigde laag aanwezig was."""
        if context.bronnen is None:
            return _bereiknotities(context, self.selectie(context), self.soort)
        if self.rol and self.laag(context) is None:
            return [context.bronnen.ontbreekt(self.rol)]
        notities = _bereiknotities(context, self.selectie(context), self.soort)
        laag = self.laag(context)
        if laag is not None:
            notities.append(
                f"Externe bron: {len(laag)} features uit `{laag.source.name}` "
                f"(laag {laag.layer}, {laag.crs})."
            )
        return notities

    def bruikbaar(self, context: CheckContext) -> bool:
        """Geeft aan of deze check de bronnen heeft die zij nodig heeft."""
        if context.bronnen is None or context.bronnen.extent is None:
            return False
        return not self.rol or self.laag(context) is not None

    def examined(self, context: CheckContext) -> int:
        """Het aantal objecten dat werkelijk getoetst is.

        Ontbreekt een benodigde bron, dan is er niets bekeken; een getal neerzetten
        zou suggereren dat de check gedraaid heeft.
        """
        if not self.bruikbaar(context):
            return 0
        return len(self.selectie(context).toetsbaar)


RELATIE_BINNEN = "binnen"
RELATIE_KRUIST = "kruist"
RELATIE_NABIJ = "nabij"
# De relaties van sterk naar zwak; de sterkste die op een object van toepassing is
# komt in de melding.
RELATIE_VOLGORDE = (RELATIE_BINNEN, RELATIE_KRUIST, RELATIE_NABIJ)


@register
class KruisingMetBouwwerk(_ExterneCheck):
    """EXT-001: een streng of put die in, door of vlak langs een bouwwerk ligt."""

    id = "EXT-001"
    title = "Kruising of nabijheid van BGT-panden en overige bouwwerken"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rol = "bgt_pand"
    soort = "vrijvervalstrengen en putten"

    def objecten(self, context: CheckContext) -> list:
        """De vrijvervalstrengen en de putten; beide horen niet in een pand."""
        return [*vrijvervalrioolleidingen(context), *netwerkknopen(context)]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk object dat binnen, door of vlak langs een bouwwerk ligt.

        Panden komen uit de BGT en worden aangevuld met de BAG-panden; die twee
        overlappen grotendeels maar niet volledig. Overige bouwwerken tellen mee als
        aparte laag. Een put in een pand is een ander gebrek dan een streng die de
        gevel raakt, dus staat de relatie in de melding.
        """
        lagen = self.bouwwerklagen(context)
        if not lagen or not self.bruikbaar(context):
            return
        buffer = context.config.drempels.ext_pand_buffer_m

        for object_ in self.selectie(context).toetsbaar:
            geometrie = self.geometrie_van(object_)
            if geometrie is None or geometrie.is_empty:
                continue
            geraakt = self._sterkste(geometrie, lagen, buffer)
            if geraakt is None:
                continue
            relatie, afstand, laag, vorm, attributen = geraakt
            sleutel, aanduiding = self._registreer(
                context, object_, laag, vorm, attributen, afstand
            )
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"Dit object {self._zin(relatie, afstand)} een bouwwerk uit "
                f"`{laag.source.name}` (laag {laag.layer}); buffer {buffer:g} m.",
                waarde=relatie,
                drempel=buffer,
                afstand_m=round(afstand, 3),
                bron=laag.source.name,
                laag=laag.layer,
                object2_uri=sleutel,
                object2_label=aanduiding,
            )

    def _registreer(
        self, context: CheckContext, object_, laag, vorm, attributen, afstand: float
    ) -> tuple[str, str]:
        """Legt het geraakte bouwwerk vast en levert sleutel en aanduiding terug.

        De GeoPackage-laag `bouwwerken` wordt hieruit gevuld, gejoind op de meldingen;
        de melding zelf draagt alleen de sleutel en de aanduiding, want een polygoon
        hoort niet in de CSV of de JSON.
        """
        sleutel, terugval = bouw_sleutel(VOORVOEGSEL[laag.role], attributen, vorm)
        if terugval:
            context.treffers.meld_zonder_id(self.id, laag.source.name)
        naam = sleutel.split("/")[-1]
        soort = attributen.get("type")
        if laag.role == "bgt_bouwwerk":
            aanduiding = f"bouwwerk {naam}" + (f" ({soort})" if soort else "")
        else:
            aanduiding = f"pand {naam}"
        context.treffers.registreer(
            Treffer(
                sleutel=sleutel,
                bron=laag.role,
                label=aanduiding,
                bronbestand=laag.source.name,
                geometrie=vorm,
                attributen=dict(attributen),
            ),
            check_id=self.id,
            object_uri=object_.uri,
            afstand_m=round(afstand, 3),
        )
        return sleutel, aanduiding

    def _sterkste(self, geometrie, lagen, buffer: float):
        """De zwaarste relatie met een bouwwerk binnen de buffer.

        Bij gelijke relatie wint het dichtstbijzijnde bouwwerk; zo hangt de melding
        niet af van de volgorde waarin de lagen toevallig gelezen zijn.

        Levert `(relatie, afstand, laag, vorm, attributen)`. De vorm en de attributen
        zijn nodig om de treffer te registreren voor de GIS-uitvoer; de keuze zelf
        verandert er niet door, want de vergelijking blijft op `(volgorde, afstand)`.
        """
        beste = None
        for laag in lagen:
            for vorm, attributen in laag.nabij(geometrie, buffer):
                afstand = geometrie.distance(vorm)
                if afstand > buffer:
                    continue
                relatie = self._relatie(geometrie, vorm, afstand)
                kandidaat = (
                    RELATIE_VOLGORDE.index(relatie),
                    afstand,
                    relatie,
                    laag,
                    vorm,
                    attributen,
                )
                if beste is None or kandidaat[:2] < beste[:2]:
                    beste = kandidaat
        if beste is None:
            return None
        return (beste[2], beste[1], beste[3], beste[4], beste[5])

    def _relatie(self, geometrie, bouwwerk, afstand: float) -> str:
        """De relatie tussen object en bouwwerk: binnen, kruist of nabij."""
        if geometrie.within(bouwwerk):
            return RELATIE_BINNEN
        if afstand == 0.0:
            return RELATIE_KRUIST
        return RELATIE_NABIJ

    def _zin(self, relatie: str, afstand: float) -> str:
        """De relatie als leesbare zin voor in de melding."""
        if relatie == RELATIE_BINNEN:
            return "ligt volledig binnen"
        if relatie == RELATIE_KRUIST:
            return "kruist"
        return f"ligt {afstand:.2f} m van"

    def bouwwerklagen(self, context: CheckContext) -> list:
        """De pand- en bouwwerklagen die deze check gebruikt.

        EXT-001 leunt op drie rollen tegelijk; als er ook maar een van aanwezig is
        kan de check draaien. De basisklasse kijkt naar een enkele rol en zou hier
        het verkeerde antwoord geven.
        """
        if context.bronnen is None:
            return []
        return [
            laag
            for rol in ("bgt_pand", "bag_pand", "bgt_bouwwerk")
            for laag in [context.bronnen.layer(rol)]
            if laag is not None
        ]

    def bruikbaar(self, context: CheckContext) -> bool:
        """Een van de drie pand- of bouwwerklagen volstaat."""
        if context.bronnen is None or context.bronnen.extent is None:
            return False
        return bool(self.bouwwerklagen(context))

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke pandbronnen gebruikt zijn, en of er identificaties ontbraken."""
        if context.bronnen is None or context.bronnen.extent is None:
            return _bereiknotities(context, self.selectie(context), self.soort)
        gebruikt = self.bouwwerklagen(context)
        if not gebruikt:
            return [context.bronnen.ontbreekt("bgt_pand")]
        omschrijving = ", ".join(f"{laag.role} ({len(laag)})" for laag in gebruikt)
        return [
            *_bereiknotities(context, self.selectie(context), self.soort),
            f"Getoetst tegen: {omschrijving}.",
            *_notitie_zonder_id(context, self.id),
        ]


class _WatergangKruising(_ExterneCheck):
    """Gedeelde basis voor de twee kruisingschecks op BGT-waterdelen."""

    rol = "bgt_water"
    soort = "vrijvervalstrengen"

    def objecten(self, context: CheckContext) -> list:
        """De vrijvervalstrengen."""
        return vrijvervalrioolleidingen(context)

    def kruisingen(self, context: CheckContext):
        """De strengen die een waterdeel raken, met het waterdeel erbij.

        Levert `(conduit, geometrie, rij, laag, buffer)`. De geometrie is nodig om de
        treffer voor de GIS-uitvoer te registreren; de detectie verandert er niet
        door. Ook de `break` na het eerste gevonden waterdeel per streng blijft staan:
        een streng die twee waterdelen kruist levert er een, en welke hangt van de
        volgorde af. Dat is een bewust geaccepteerde beperking (zie de beslislog).
        """
        laag = self.laag(context)
        if laag is None:
            return
        buffer = context.config.drempels.ext_watergang_buffer_m
        for conduit in self.selectie(context).toetsbaar:
            for geometrie, rij in laag.nabij(conduit.line, buffer):
                if conduit.line.distance(geometrie) > buffer:
                    continue
                yield conduit, geometrie, rij, laag, buffer
                break


@register
class KruisingMetWatergang(_WatergangKruising):
    """EXT-002: een streng die een watergang kruist."""

    id = "EXT-002"
    title = "Kruising met watergang (waterschaps- of BGT-data)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke streng die binnen de buffer van een BGT-waterdeel komt.

        Het register laat BGT als watergangbron toe; waterschapsdata is niet
        aangeleverd en valt in deze fase buiten scope.
        """
        for conduit, _vorm, rij, laag, buffer in self.kruisingen(context):
            soort = rij.get("type") or "waterdeel"
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Kruist een BGT-waterdeel van het type {soort!r} (buffer {buffer:g} m).",
                watertype=soort,
                bron=laag.source.name,
                buffer_m=buffer,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt dat de waterschapsbron ontbreekt."""
        return [
            *super().notes(context),
            "Waterschapsdata is niet aangeleverd; alleen de BGT-waterdelen zijn gebruikt. "
            "Het register staat die bron expliciet toe.",
        ]


@register
class KruisingZonderZinkerOfDuiker(_WatergangKruising):
    """EXT-003: een watergangkruising die niet als zinker of duiker geregistreerd staat."""

    id = "EXT-003"
    title = "Kruising met watergang zonder registratie als zinker of duiker"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt kruisingen waarvan de streng geen kruisingsconstructie is."""
        dataset = context.dataset
        wortels = context.config.klassen.kruisingsleiding

        for conduit, vorm, rij, laag, buffer in self.kruisingen(context):
            if any(dataset.is_a(conduit.uri, wortel) for wortel in wortels):
                continue
            soort = str(rij.get("type") or "waterdeel")
            sleutel, terugval = bouw_sleutel(VOORVOEGSEL["bgt_water"], rij, vorm)
            if terugval:
                context.treffers.meld_zonder_id(self.id, laag.source.name)
            context.treffers.registreer(
                Treffer(
                    sleutel=sleutel,
                    bron="bgt_water",
                    label=soort,
                    bronbestand=laag.source.name,
                    geometrie=vorm,
                    attributen=dict(rij),
                ),
                check_id=self.id,
                object_uri=conduit.uri,
            )
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Kruist een BGT-waterdeel ({soort}) maar staat niet geregistreerd als "
                f"{' of '.join(wortels) or 'kruisingsconstructie'}.",
                watertype=soort,
                buffer_m=buffer,
                object2_uri=sleutel,
                object2_label=soort,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke klassen als kruisingsconstructie gelden."""
        wortels = context.config.klassen.kruisingsleiding
        if not wortels:
            return [
                *super().notes(context),
                "Er zijn geen kruisingsconstructieklassen geconfigureerd "
                "(`klassen.kruisingsleiding`); elke kruising telt daardoor mee.",
                *_notitie_zonder_id(context, self.id),
            ]
        return [
            *super().notes(context),
            f"Als kruisingsconstructie gelden: {', '.join(wortels)}.",
            *_notitie_zonder_id(context, self.id),
        ]


@register
class StrengOpParticulierTerrein(SkeletonCheck):
    """EXT-004: een streng op of nabij particulier terrein (BRK)."""

    id = "EXT-004"
    title = "Streng op of nabij particulier terrein (op basis van BRK-percelen)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    markering = MARKERING_BUITEN_SCOPE
    reden = (
        "BRK-percelen zijn in deze fase niet aangeleverd en er wordt geen vervangende bron "
        "gezocht. De check is als skelet opgenomen zodat zichtbaar blijft dat het register "
        "hem kent en dat hij niet gedraaid is. De bufferafstand staat al in de config "
        "(`drempels.ext_perceel_buffer_m`)."
    )


@register
class PutZonderBgtDeksel(_ExterneCheck):
    """EXT-005: een put zonder BGT-putdeksel in de buurt."""

    id = "EXT-005"
    title = "Put zonder BGT-putdeksel binnen X m"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rol = "bgt_putdeksel"
    soort = "putten"

    def objecten(self, context: CheckContext) -> list:
        """De putten van het netwerk."""
        return netwerkknopen(context)

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt putten zonder BGT-deksel binnen de afstand."""
        laag = self.laag(context)
        if laag is None:
            return
        afstand = context.config.drempels.ext_putdeksel_afstand_m

        for node in self.selectie(context).toetsbaar:
            if any(
                node.point.distance(geometrie) <= afstand
                for geometrie, _ in laag.nabij(node.point, afstand)
            ):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Geen BGT-putdeksel binnen {afstand:g} m van deze put.",
                afstand_m=afstand,
            )


@register
class BgtDekselZonderPut(_ExterneCheck):
    """EXT-006: een BGT-putdeksel zonder put in de beheerdata."""

    id = "EXT-006"
    title = "BGT-putdeksel zonder put in de beheerdata"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rol = "bgt_putdeksel"
    soort = "putten"

    def objecten(self, context: CheckContext) -> list:
        """De putten van het netwerk; die vormen de vergelijkingsbasis."""
        return netwerkknopen(context)

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt BGT-deksels zonder GWSW-put binnen de afstand.

        De bevinding hangt aan het BGT-object en niet aan een GWSW-object; het
        RD-coordinaat van het deksel neemt de rol van de dataset-URI over bij de
        afbakening tot het studiegebied.
        """
        laag = self.laag(context)
        if laag is None:
            return
        afstand = context.config.drempels.ext_putdeksel_afstand_m
        putten = [node.point for node in self.selectie(context).toetsbaar]
        if not putten:
            # Zonder putten binnen het gebied zou elk deksel als bevinding gelden;
            # dat zegt niets over de beheerdata. `notes()` meldt de reden.
            return

        from shapely.strtree import STRtree

        boom = STRtree(putten)
        for index, geometrie in enumerate(laag.geometries):
            rij = laag.attributes[index] if index < len(laag.attributes) else {}
            if any(
                putten[int(positie)].distance(geometrie) <= afstand
                for positie in boom.query(geometrie.buffer(afstand))
            ):
                continue
            punt = geometrie.representative_point()
            yield self.finding(
                context,
                f"bgt:put/{rij.get('lokaal_id') or rij.get('id') or index}",
                str(rij.get("lokaal_id") or rij.get("id") or f"BGT-deksel {index}"),
                f"Dit BGT-putdeksel heeft geen put in de beheerdata binnen {afstand:g} m.",
                location=(punt.x, punt.y),
                afstand_m=afstand,
                bron=laag.source.name,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de bron en of er wel putten in het gebied liggen."""
        notities = [
            "De bevindingen hangen aan BGT-deksels, niet aan GWSW-objecten; de putten "
            "hieronder vormen de vergelijkingsbasis.",
            *super().notes(context),
        ]
        if (
            context.bronnen is not None
            and self.laag(context) is not None
            and not self.selectie(context).toetsbaar
        ):
            notities.append(
                "Er ligt geen enkele put van deze dataset binnen het studiegebied; elk "
                "BGT-deksel zou dan als bevinding gelden. De check is daarom niet uitgevoerd."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Het aantal BGT-putdeksels dat werkelijk vergeleken is."""
        laag = self.laag(context)
        if laag is None or not self.selectie(context).toetsbaar:
            return 0
        return len(laag)


@register
class LozingspuntZonderWatergang(_ExterneCheck):
    """EXT-007: een lozingspunt zonder watergang in de buurt."""

    id = "EXT-007"
    title = "Lozingspunt zonder watergang binnen X m"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rol = "bgt_water"
    soort = "lozingspunten"

    def objecten(self, context: CheckContext) -> list:
        """De knopen die als lozings- of uitstroompunt gelden."""
        return lozingspunten(context)

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt lozingspunten zonder BGT-waterdeel binnen de afstand."""
        laag = self.laag(context)
        if laag is None:
            return
        afstand = context.config.drempels.ext_lozingspunt_water_afstand_m

        for node in self.selectie(context).toetsbaar:
            if any(
                node.point.distance(geometrie) <= afstand
                for geometrie, _ in laag.nabij(node.point, afstand)
            ):
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Geen BGT-waterdeel binnen {afstand:g} m van dit lozingspunt.",
                afstand_m=afstand,
            )


class _AhnCheck(_ExterneCheck):
    """Basis voor de hoogtechecks die het AHN als referentie gebruiken."""

    soort = "putten"

    def objecten(self, context: CheckContext) -> list:
        """De putten van het netwerk."""
        return netwerkknopen(context)

    def raster(self, context: CheckContext):
        """Het hoogteraster, of None."""
        return context.bronnen.raster if context.bronnen is not None else None

    def bruikbaar(self, context: CheckContext) -> bool:
        """Deze checks hebben geen vectorlaag nodig maar wel het hoogteraster."""
        if context.bronnen is None or context.bronnen.extent is None:
            return False
        return self.raster(context) is not None

    def monsters(self, context: CheckContext) -> list[tuple[Node, float]]:
        """Levert per toetsbare put het maaiveld uit de dataset en uit het AHN.

        Het resultaat wordt per context bewaard. `run()`, `notes()` en de telling
        van de nodata-cellen vragen er elk om, en elke doorloop bemonstert het
        raster per put; op een volledige dataset is dat merkbaar duur.
        """
        raster = self.raster(context)
        if raster is None:
            return []

        def bemonster() -> list[tuple[Node, float]]:
            """Bemonstert het raster voor elke toetsbare put."""
            gevonden = []
            for node in self.selectie(context).toetsbaar:
                gemeten = raster.sample(node.point.x, node.point.y)
                if gemeten is not None:
                    gevonden.append((node, gemeten))
            return gevonden

        return context.cached(f"ahn:monsters:{type(self).__name__}", bemonster)

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt het bereik en of het raster aanwezig was."""
        if context.bronnen is None or context.bronnen.extent is None:
            return _bereiknotities(context, self.selectie(context), self.soort)
        raster = self.raster(context)
        if raster is None:
            return [
                "laag niet aanwezig in aangeleverde data: er is geen hoogteraster geladen; "
                "deze check is overgeslagen."
            ]
        notities = _bereiknotities(context, self.selectie(context), self.soort)
        zonder = len(self.selectie(context).toetsbaar) - len(self.monsters(context))
        notities.append(f"Hoogtereferentie: `{raster.source.name}` ({raster.crs}).")
        if zonder:
            notities.append(
                f"{zonder} putten binnen het studiegebied vallen op een cel zonder "
                "rasterwaarde (nodata) en konden niet vergeleken worden."
            )
        return notities


class _DekselAfwijking(_AhnCheck):
    """Gedeelde basis voor HGT-001 en HGT-002."""

    ondergrens: str
    bovengrens: str | None

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de geregistreerde maaiveldhoogte met het AHN.

        De De Wolden-export bevat geen `Putdekselniveau`; de `Maaiveldhoogte` bij de
        put is dan de dichtstbijzijnde benadering van de dekselhoogte. Welke van de
        twee gebruikt is staat in de melding.
        """
        drempels = context.config.drempels
        onder = getattr(drempels, self.ondergrens)
        boven = getattr(drempels, self.bovengrens) if self.bovengrens else None

        for node, gemeten in self.monsters(context):
            geregistreerd = node.dekselniveau if node.dekselniveau is not None else node.maaiveld
            if geregistreerd is None:
                continue
            afwijking = abs(geregistreerd - gemeten)
            if afwijking <= onder:
                continue
            if boven is not None and afwijking > boven:
                continue
            bron = "putdekselniveau" if node.dekselniveau is not None else "maaiveldhoogte"
            wijze = _inwinningswijze(node)
            uit_model = _uit_hoogtemodel(context, wijze)
            kanttekening = (
                f" Let op: deze hoogte is zelf ingewonnen via {wijze}, dus hier staan twee "
                "hoogtemodellen naast elkaar en niet beheerdata naast een meting."
                if uit_model
                else ""
            )
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"{_hoofdletter(met_lidwoord(bron))} ({geregistreerd:.3f} m NAP) wijkt "
                f"{afwijking:.3f} m af van het AHN ({gemeten:.3f} m NAP).{kanttekening}",
                afwijking_m=round(afwijking, 3),
                geregistreerd=geregistreerd,
                ahn=round(gemeten, 3),
                bron=bron,
                inwinning=wijze or "",
                uit_hoogtemodel=uit_model,
                ondergrens_m=onder,
                bovengrens_m=boven,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Vult de bereiknotities aan met het getoetste kenmerk en zijn herkomst."""
        notities = super().notes(context)
        if context.bronnen is None or self.raster(context) is None:
            return notities

        vergeleken = [node for node, _ in self.monsters(context)]
        notities += _kenmerknotitie(vergeleken)

        uit_model = [node for node in vergeleken if _uit_model_node(context, node)]
        if not uit_model:
            return notities

        wijzen = sorted({_inwinningswijze(node) or "onbekend" for node in uit_model})
        notities.append(
            f"{len(uit_model)} van de {len(vergeleken)} vergeleken hoogten zijn zelf uit een "
            f"hoogtemodel ingewonnen ({', '.join(wijzen)}). Voor die putten vergelijkt deze "
            "check twee hoogtemodellen met elkaar; een afwijking daar is geen gebrek in de "
            "beheerdata en valt niet met een veldmeting te herstellen."
        )
        return notities


def _hoofdletter(zin: str) -> str:
    """Zet de eerste letter van een zin om in een hoofdletter."""
    return zin[:1].upper() + zin[1:]


def _kenmerknotitie(vergeleken: list[Node]) -> list[str]:
    """Meldt welk hoogtekenmerk er feitelijk vergeleken is, met aantallen.

    Het register spreekt van de dekselhoogte, maar de check valt terug op de
    maaiveldhoogte als `Putdekselniveau` ontbreekt — zoals in de hele De
    Wolden-export. Zonder deze regel claimt het rapport iets anders te hebben
    getoetst dan het deed.
    """
    if not vergeleken:
        return []

    deksel = sum(1 for node in vergeleken if node.dekselniveau is not None)
    maaiveld = len(vergeleken) - deksel
    if deksel and maaiveld:
        return [
            f"Vergeleken is het putdekselniveau bij {getal(deksel, 'put', 'putten')} en de "
            f"maaiveldhoogte bij {getal(maaiveld, 'put', 'putten')}."
        ]
    if maaiveld:
        return [
            f"Vergeleken is de maaiveldhoogte, bij alle {getal(maaiveld, 'put', 'putten')}; "
            f"`Putdekselniveau` ontbreekt in deze export."
        ]
    return [f"Vergeleken is het putdekselniveau, bij alle {getal(deksel, 'put', 'putten')}."]


def _inwinningswijze(node: Node) -> str | None:
    """De inwinningswijze van de hoogte die deze checks van een put gebruiken.

    Het putdekselniveau gaat voor; ontbreekt dat, dan is de maaiveldhoogte de
    gebruikte waarde en telt haar herkomst.
    """
    inwinning = node.deksel_inwinning if node.dekselniveau is not None else node.maaiveld_inwinning
    return inwinning.wijze if inwinning is not None else None


def _uit_hoogtemodel(context: CheckContext, wijze: str | None) -> bool:
    """Geeft aan of deze inwinningswijze uit een landelijk hoogtemodel komt."""
    return wijze is not None and wijze in context.config.inwinning.uit_hoogtemodel


def _uit_model_node(context: CheckContext, node: Node) -> bool:
    """Geeft aan of de gebruikte hoogte van deze put uit een hoogtemodel komt."""
    return _uit_hoogtemodel(context, _inwinningswijze(node))


@register
class DekselAfwijkingLicht(_DekselAfwijking):
    """HGT-001: de deksel- of maaiveldhoogte wijkt meer dan de lichte drempel af."""

    id = "HGT-001"
    title = "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 5 cm"
    severity = Severity.WARNING
    dimension = Dimension.ACCURACY
    ondergrens = "ahn_afwijking_waarschuwing_m"
    bovengrens = "ahn_afwijking_fout_m"


@register
class DekselAfwijkingFors(_DekselAfwijking):
    """HGT-002: de deksel- of maaiveldhoogte wijkt meer dan de zware drempel af."""

    id = "HGT-002"
    title = "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 25 cm"
    severity = Severity.ERROR
    dimension = Dimension.ACCURACY
    ondergrens = "ahn_afwijking_fout_m"
    bovengrens = None


@register
class BobSanityTenOpzichteVanAhn(_AhnCheck):
    """HGT-003: een BOB boven het AHN-maaiveld of onaannemelijk diep eronder."""

    id = "HGT-003"
    title = "BOB-sanity ten opzichte van AHN (boven maaiveld, meer dan 3 m eronder)"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst elke BOB die op een toetsbare put uitkomt tegen het AHN."""
        diepte = context.config.drempels.bob_maximale_diepte_m
        toetsbaar = {node.uri: node for node in self.selectie(context).toetsbaar}
        raster = self.raster(context)
        if raster is None:
            return

        for conduit in vrijvervalrioolleidingen(context):
            begin, eind = verbonden_knopen(context, conduit)
            for uri, bob, zijde in (
                (begin, conduit.bob_start, "beginpunt"),
                (eind, conduit.bob_end, "eindpunt"),
            ):
                node = toetsbaar.get(uri) if uri else None
                if node is None or bob is None:
                    continue
                maaiveld = raster.sample(node.point.x, node.point.y)
                if maaiveld is None:
                    continue
                melding = self._melding(bob, maaiveld, diepte, zijde, node)
                if melding is None:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    melding,
                    zijde=zijde,
                    bob=bob,
                    ahn=round(maaiveld, 3),
                    put=node.label,
                    maximale_diepte_m=diepte,
                )

    def _melding(self, bob: float, maaiveld: float, diepte: float, zijde: str, node) -> str | None:
        """De reden waarom deze BOB niet bij het AHN-maaiveld past, of None."""
        if bob > maaiveld:
            return (
                f"De BOB aan het {zijde} ({bob:.3f} m NAP) ligt boven het AHN-maaiveld bij "
                f"put {node.label!r} ({maaiveld:.3f} m NAP)."
            )
        if maaiveld - bob > diepte:
            return (
                f"De BOB aan het {zijde} ({bob:.3f} m NAP) ligt {maaiveld - bob:.2f} m onder "
                f"het AHN-maaiveld bij put {node.label!r}, meer dan {diepte:g} m."
            )
        return None
