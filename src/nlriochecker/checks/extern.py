"""EXT-checks en de AHN-hoogtechecks: toetsing tegen externe bronnen.

Alle bronnen in `data/gis_koekangerveld/` dekken uitsluitend het studiegebied
Koekangerveld, terwijl de GWSW-dataset de gemeenten De Wolden en Hoogeveen beslaat. Een
GWSW-object daar buiten krijgt daarom geen uitslag maar de status *buiten studiegebied*: dat er geen
BGT-deksel of BAG-pand naast ligt zegt daar niets over de datakwaliteit en alles
over de dekking van de bron. Elke check meldt in haar toelichting hoeveel objecten
om die reden buiten beschouwing bleven.

De typeringspoort telt hier zwaarder dan in de interne checks: een te globaal
getypeerd object krijgt geen uitslag maar de markering *niet betrouwbaar toetsbaar*,
en wordt in de toelichting geteld. De nulmeting verklaart haar eigen
vervolgvalidaties voor zulke objecten immers onbetrouwbaar.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

from gwsw_orox_helpers.dataset import Conduit, Node
from shapely.geometry import MultiPoint
from shapely.geometry.base import BaseGeometry

from nlriochecker.checks.base import (
    REGISTRY,
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    SkeletonCheck,
    register,
)
from nlriochecker.checks.selectie import (
    lozingspunten,
    netwerkknopen,
    vrijvervalrioolleidingen,
    waterlozingspunten,
)
from nlriochecker.checks.treffers import Treffer, bouw_sleutel
from nlriochecker.checks.verbanden import verbonden_knopen
from nlriochecker.checks.wegvakken import (
    REDEN_DRUKRIOLERING,
    REDEN_ONVERHARD,
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ROOD,
    beoordeel,
)
from nlriochecker.externedata import ROL_RASTER, ROL_STUDIEGEBIED, RasterSampler, VectorLayer
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

    toetsbaar: list[Node | Conduit]
    buiten_gebied: int
    onbetrouwbaar: int
    zonder_geometrie: int

    @property
    def totaal(self) -> int:
        """Het aantal objecten dat de check heeft bekeken."""
        return len(self.toetsbaar) + self.buiten_gebied + self.onbetrouwbaar + self.zonder_geometrie


def _selecteer(
    context: CheckContext,
    objecten: Iterable[Node | Conduit],
    geometrie_van: Callable[[Node | Conduit], BaseGeometry | None],
) -> _Selectie:
    """Splitst objecten in toetsbaar, buiten het gebied en niet betrouwbaar getypeerd."""
    bronnen = context.bronnen
    toetsbaar: list[Node | Conduit] = []
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


def _van_soort[Object: (Node, Conduit)](selectie: _Selectie, soort: type[Object]) -> list[Object]:
    """De toetsbare objecten van een selectie, versmald tot een enkel objecttype.

    `_Selectie` draagt de brede unie omdat EXT-001 strengen en putten tegelijk toetst.
    Een check waarvan de populatie uit uitsluitend knopen (of uitsluitend strengen)
    bestaat leest velden die alleen daarop bestaan -- `Node.point`, `Conduit.line` --
    en haalt haar populatie hier terug in de vorm waarin haar eigen `objecten()` hem
    opleverde. Er valt per constructie niets weg.
    """
    return [object_ for object_ in selectie.toetsbaar if isinstance(object_, soort)]


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

    @classmethod
    def bronrollen(cls) -> frozenset[str]:
        """De externe bronnen waar deze check op leunt.

        Het bereik hoort er altijd bij: zonder begrenzingspolygoon geeft geen enkele
        EXT-check een uitslag. `bronrollen_met_check()` telt deze verzamelingen op,
        zodat het rapport het ontbreken van een bron alleen als overgeslagen check
        presenteert waar dat waar is.
        """
        return frozenset({ROL_STUDIEGEBIED, *([cls.rol] if cls.rol else [])})

    def objecten(self, context: CheckContext) -> Sequence[Node | Conduit]:
        """De GWSW-objecten die deze check bekijkt.

        `Sequence` en niet `list`: `list` is invariant, en de overrides hieronder leveren
        een `list[Conduit]` of een `list[Node]` uit `checks/selectie.py`. Met `list[Node |
        Conduit]` zou geen van die rolfuncties nog passen.
        """
        raise NotImplementedError

    def geometrie_van(self, object_: Node | Conduit) -> BaseGeometry | None:
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

    def laag(self, context: CheckContext) -> VectorLayer | None:
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


def bronrollen_met_check() -> frozenset[str]:
    """De externe bronnen waar een geregistreerde check op leunt.

    Het rapport zegt van een ontbrekende bron dat de checks die hem nodig hebben zijn
    overgeslagen; die zin mag alleen over deze bronnen gaan. `bgt_putdeksel` staat er
    niet meer bij sinds EXT-005 en EXT-006 vervielen (BO-64, BO-65): die laag wordt nog
    geladen en op dekking getoetst, maar haar ontbreken slaat niets over. `nwb_wegvak`
    stond er tot issue #104 evenmin bij; sinds EXT-009 hoort hij er wel bij, samen met
    `top10nl_kom` en `bgt_wegdeel`. De opdrachtregel van `toets` somt wel alles op wat
    niet geladen is.
    """
    return frozenset().union(
        *(check.bronrollen() for check in REGISTRY.values() if issubclass(check, _ExterneCheck))
    )


# De pand- en bouwwerkrollen van EXT-001, in leesvolgorde. Een van de drie volstaat om
# de check te laten draaien; `rol` noemt alleen de eerste.
BOUWWERKROLLEN = ("bgt_pand", "bag_pand", "bgt_bouwwerk")

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
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ()
    rol = "bgt_pand"
    soort = "vrijvervalstrengen en putten"

    def objecten(self, context: CheckContext) -> Sequence[Node | Conduit]:
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
        self,
        context: CheckContext,
        object_: Node | Conduit,
        laag: VectorLayer,
        vorm: BaseGeometry,
        attributen: dict[str, object],
        afstand: float,
    ) -> tuple[str, str]:
        """Legt het geraakte bouwwerk vast en levert sleutel en aanduiding terug.

        De GeoPackage-laag `vlakken` wordt hieruit gevuld, gejoind op de meldingen;
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

    def _sterkste(
        self, geometrie: BaseGeometry, lagen: Sequence[VectorLayer], buffer: float
    ) -> tuple[str, float, VectorLayer, BaseGeometry, dict[str, object]] | None:
        """De zwaarste relatie met een bouwwerk binnen de buffer.

        Bij gelijke relatie wint het dichtstbijzijnde bouwwerk; zo hangt de melding
        niet af van de volgorde waarin de lagen toevallig gelezen zijn.

        Levert `(relatie, afstand, laag, vorm, attributen)`. De vorm en de attributen
        zijn nodig om de treffer te registreren voor de GIS-uitvoer; de keuze zelf
        verandert er niet door, want de vergelijking blijft op `(volgorde, afstand)`.
        """
        beste: tuple[int, float, str, VectorLayer, BaseGeometry, dict[str, object]] | None = None
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

    def _relatie(self, geometrie: BaseGeometry, bouwwerk: BaseGeometry, afstand: float) -> str:
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

    @classmethod
    def bronrollen(cls) -> frozenset[str]:
        """Alle drie de pand- en bouwwerkrollen, niet alleen `rol`."""
        return frozenset({ROL_STUDIEGEBIED, *BOUWWERKROLLEN})

    def bouwwerklagen(self, context: CheckContext) -> list[VectorLayer]:
        """De pand- en bouwwerklagen die deze check gebruikt.

        EXT-001 leunt op drie rollen tegelijk; als er ook maar een van aanwezig is
        kan de check draaien. De basisklasse kijkt naar een enkele rol en zou hier
        het verkeerde antwoord geven.
        """
        if context.bronnen is None:
            return []
        return [
            laag
            for rol in BOUWWERKROLLEN
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


@dataclass(frozen=True)
class _Kruising:
    """Een vrijvervalstreng die een BGT-waterdeel echt doorkruist.

    De geometrie van het waterdeel gaat mee omdat EXT-003 er de treffer voor de
    GIS-uitvoer mee registreert; de detectie verandert er niet door. `buffer` is de
    zoekstraal waarbinnen het waterdeel als kandidaat gevonden is, niet het
    criterium (BO-43). Een dataclass in plaats van een tuple: hij werd op positie
    uitgepakt, en een veld erbij of een andere volgorde zou daar pas tijdens het
    draaien opvallen.

    Dat veld heet `waterdeel` en niet `vorm`: op een `Conduit` is `vorm` de
    profielvorm, dus de AST-sweep van issue #64 las `kruising.vorm` als een lezing
    van `VormLeiding` en EXT-003 declareerde een kenmerk dat hij niet leest. De
    naam is het herstel; een uitzondering in de sweep zou dezelfde val voor de
    volgende dataclass laten liggen (issue #96).
    """

    conduit: Conduit
    waterdeel: BaseGeometry
    rij: dict[str, object]
    laag: VectorLayer
    buffer: float


@dataclass(frozen=True)
class _Kruisingen:
    """De doorkruisingen plus de telling van wat binnen de zoekstraal viel maar afviel.

    De tellingen zijn per paar (streng, kandidaat-waterdeel); een streng die twee
    waterdelen nadert telt twee keer.
    """

    doorkruisingen: tuple[_Kruising, ...]
    raakt_niet: int
    lozingspunt: int
    tangentieel: int

    @property
    def kandidaten(self) -> int:
        """Het aantal paren dat binnen de zoekstraal viel."""
        return len(self.doorkruisingen) + self.raakt_niet + self.lozingspunt + self.tangentieel


DOORKRUISING = "doorkruising"
RAAKT_NIET = "raakt niet"
LOZINGSPUNT = "lozingspunt"
TANGENTIEEL = "tangentieel"


def _verhouding(lijn: BaseGeometry, waterdeel: BaseGeometry) -> str:
    """Hoe een streng zich tot een waterdeel verhoudt (BO-43).

    Een doorkruising gaat het waterdeel in door de ene oever en eruit door de andere:
    de lijn snijdt het waterdeel, geen van haar eindpunten ligt in of op het waterdeel
    (`e = 0`) en zij kruist de rand in minstens twee punten (`k >= 2`). Een streng die
    erin eindigt is een lozingspunt (overstort, inlaat); een streng die de rand alleen
    aanraakt of ernaast ligt raakt het waterdeel niet; een streng die een stuk óver de
    rand loopt is tangentieel. Geen van die drie is een bevinding, en er is bewust geen
    drempel: een minimum-doorsnijding zou echte doorkruisingen van smalle greppels
    (0,3-0,5 m) wegfilteren.
    """
    if not lijn.intersects(waterdeel):
        return RAAKT_NIET
    rand = lijn.intersection(waterdeel.boundary)
    if rand.length > 0:
        return TANGENTIEEL
    # `boundary` van een lijn zijn haar twee eindpunten; `intersects` telt ook een
    # eindpunt dat precies op de oever ligt als erin.
    if waterdeel.intersects(lijn.boundary):
        return LOZINGSPUNT
    if isinstance(rand, MultiPoint) and len(rand.geoms) >= 2:
        return DOORKRUISING
    return RAAKT_NIET


def _zoek_kruisingen(
    strengen: list[Conduit], laag: VectorLayer | None, buffer: float
) -> _Kruisingen:
    """Loopt de toetsbare strengen langs alle kandidaat-waterdelen binnen de zoekstraal.

    Vrije functie zonder `self`: de uitkomst hangt alleen van deze drie argumenten af,
    zodat de gedeelde cache-ingang van `_WatergangKruising.kruisingen` niet aan de
    eerste aanroepende subklasse vastzit. Elke kandidaat wordt beoordeeld; er is geen
    `break` na de eerste (de herziening van BO-17 in BO-43).
    """
    doorkruisingen: list[_Kruising] = []
    telling = {RAAKT_NIET: 0, LOZINGSPUNT: 0, TANGENTIEEL: 0}
    if laag is not None:
        for conduit in strengen:
            # `_selecteer` liet alleen strengen met een geometrie door; deze functie
            # leunt daar niet op, zodat ze ook los van die selectie te lezen is.
            if conduit.line is None:
                continue
            for geometrie, rij in laag.nabij(conduit.line, buffer):
                if conduit.line.distance(geometrie) > buffer:
                    continue
                verhouding = _verhouding(conduit.line, geometrie)
                if verhouding == DOORKRUISING:
                    doorkruisingen.append(_Kruising(conduit, geometrie, rij, laag, buffer))
                else:
                    telling[verhouding] += 1
    return _Kruisingen(
        doorkruisingen=tuple(doorkruisingen),
        raakt_niet=telling[RAAKT_NIET],
        lozingspunt=telling[LOZINGSPUNT],
        tangentieel=telling[TANGENTIEEL],
    )


class _WatergangKruising(_ExterneCheck):
    """Basis voor de kruisingscheck op BGT-waterdelen.

    Tot issue #83 hingen EXT-002 en EXT-003 hier allebei onder; EXT-002 is vervallen
    (BO-66) en EXT-003 is de enige die overblijft. De basis blijft staan omdat zij de
    populatie, de kruisingstoets en de telling van wat buiten de populatie valt bij
    elkaar houdt -- de uitzondering op een geregistreerde zinker is wat EXT-003 er
    zelf bovenop legt.

    De populatie is die van `klassen.vrijvervalleiding`. Een duiker is in de
    GWSW-ontologie een `Leiding` die oppervlaktewater verbindt, geen rioolleiding;
    hij valt dus buiten deze checks en `buiten_populatie()` telt hoeveel dat er zijn,
    zodat het rapport dat meldt in plaats van erover te zwijgen (BO-25).
    """

    rol = "bgt_water"
    soort = "vrijvervalstrengen"

    def objecten(self, context: CheckContext) -> Sequence[Conduit]:
        """De vrijvervalstrengen."""
        return vrijvervalrioolleidingen(context)

    def kruisingstoets(self, context: CheckContext) -> _Kruisingen:
        """De doorkruisingen en de afvaltellingen, een keer per context berekend.

        De cache-ingang staat op de context en niet op de check, omdat de drie
        ingredienten van deze basisklasse zijn en niet van de aanroepende check: de
        populatie (`objecten()` levert `vrijvervalrioolleidingen(context)`, door
        `selectie()` gefilterd), de laag `bgt_water` en de zoekstraal. Toen EXT-002 er
        nog onder hing deelden de twee checks hem, zodat de ruimtelijke toets niet
        tweemaal draaide.

        De bouwer is daarom een vrije functie: hij krijgt die drie mee en kent geen
        `self`, zodat de ingang niet stilzwijgend van de eerste aanroeper kan gaan
        afhangen. Wie hier ooit een tweede subklasse met een eigen populatie onder
        hangt (BO-25 verwierp dat voor EXT-003), moet haar dus een eigen sleutel geven.
        """
        toetsbaar = _van_soort(self.selectie(context), Conduit)
        laag = self.laag(context)
        buffer = context.config.drempels.ext_watergang_buffer_m
        return context.cached(
            "ext:watergangkruisingen",
            lambda: _zoek_kruisingen(toetsbaar, laag, buffer),
        )

    def kruisingen(self, context: CheckContext) -> tuple[_Kruising, ...]:
        """De echte doorkruisingen, met het waterdeel erbij."""
        return self.kruisingstoets(context).doorkruisingen

    def buiten_populatie(self, context: CheckContext) -> dict[str, int]:
        """Per kruisingsklasse die geen vrijvervalleiding is: hoeveel strengen erbuiten vallen."""
        dataset = context.dataset
        binnen = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
        telling: dict[str, int] = {}
        for wortel in context.config.klassen.kruisingsleiding:
            buiten = [
                uri
                for uri in dataset.of_class(wortel)
                if uri in dataset.conduits and uri not in binnen
            ]
            if buiten:
                telling[wortel] = len(buiten)
        return telling

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de strengen die wel kruisingsklasse zijn maar buiten de populatie vallen."""
        notities = super().notes(context)
        if self.bruikbaar(context):
            toets = self.kruisingstoets(context)
            buffer = context.config.drempels.ext_watergang_buffer_m
            raakt_niet = getal(
                toets.raakt_niet, "raakt het waterdeel niet", "raken het waterdeel niet"
            )
            lozingspunt = getal(
                toets.lozingspunt, "eindigt erin (lozingspunt)", "eindigen erin (lozingspunt)"
            )
            notities.append(
                "Alleen een echte doorkruising is een bevinding: de streng gaat het "
                "waterdeel in door de ene oever en eruit door de andere, zonder erin te "
                f"eindigen (BO-43). Binnen de zoekstraal van {buffer:g} m vielen "
                f"{getal(toets.kandidaten, 'paar', 'paren')} streng-waterdeel: "
                f"{getal(len(toets.doorkruisingen), 'doorkruising', 'doorkruisingen')}, "
                f"{raakt_niet}, {lozingspunt} "
                f"en {getal(toets.tangentieel, 'loopt over de rand', 'lopen over de rand')}. "
                "Doorkruisingen door een streng die als kruisingsconstructie "
                "geregistreerd staat tellen in die telling mee, maar blijven buiten de "
                "bevindingen."
            )
        for klasse, aantal in self.buiten_populatie(context).items():
            notities.append(
                "Buiten de populatie (geen vrijvervalleiding) en dus niet bekeken: "
                f"{getal(aantal, 'streng', 'strengen')} van de klasse {klasse}. Een "
                "kruising van zo'n streng met een watergang is geen bevinding."
            )
        return notities


@register
class KruisingZonderZinkerOfDuiker(_WatergangKruising):
    """EXT-003: een watergangkruising die niet als kruisingsconstructie geregistreerd staat.

    De klassenaam dateert van voor de correctie van de klassenhierarchie. Wat de
    uitzondering doorlaat staat in `klassen.kruisingsleiding`, en dat is nog steeds
    zinker en duiker; alleen een zinker kan binnen de populatie voorkomen, want een
    duiker is geen vrijvervalleiding. De titel en de meldingstekst noemen daarom de
    zinker: dat is wat het gebrek oplost.
    """

    id = "EXT-003"
    title = "Kruising met watergang zonder registratie als zinker"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ()

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt doorkruisingen waarvan de streng geen kruisingsconstructie is."""
        dataset = context.dataset
        wortels = context.config.klassen.kruisingsleiding

        for kruising in self.kruisingen(context):
            conduit = kruising.conduit
            if any(dataset.is_a(conduit.uri, wortel) for wortel in wortels):
                continue
            soort = str(kruising.rij.get("type") or "waterdeel")
            sleutel, terugval = bouw_sleutel(
                VOORVOEGSEL["bgt_water"], kruising.rij, kruising.waterdeel
            )
            if terugval:
                context.treffers.meld_zonder_id(self.id, kruising.laag.source.name)
            context.treffers.registreer(
                Treffer(
                    sleutel=sleutel,
                    bron="bgt_water",
                    label=soort,
                    bronbestand=kruising.laag.source.name,
                    geometrie=kruising.waterdeel,
                    attributen=dict(kruising.rij),
                ),
                check_id=self.id,
                object_uri=conduit.uri,
            )
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Doorkruist een BGT-waterdeel ({soort}) maar staat niet geregistreerd als zinker.",
                watertype=soort,
                buffer_m=kruising.buffer,
                object2_uri=sleutel,
                object2_label=soort,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke klassen als kruisingsconstructie gelden en welke waterbron gebruikt is.

        De regel over de waterschapsbron stond tot issue #83 bij EXT-002; die check is
        vervallen en dit is nu de enige watergangmelding, dus zonder deze zin zou het
        rapport niet meer zeggen dat er alleen op BGT-waterdelen getoetst is.
        """
        wortels = context.config.klassen.kruisingsleiding
        bron = (
            "Waterschapsdata is niet aangeleverd; alleen de BGT-waterdelen zijn gebruikt. "
            "Het register staat die bron expliciet toe."
        )
        if not wortels:
            return [
                *super().notes(context),
                "Er zijn geen kruisingsconstructieklassen geconfigureerd "
                "(`klassen.kruisingsleiding`); elke kruising telt daardoor mee.",
                bron,
                *_notitie_zonder_id(context, self.id),
            ]
        return [
            *super().notes(context),
            f"Als kruisingsconstructie gelden: {', '.join(wortels)}.",
            bron,
            *_notitie_zonder_id(context, self.id),
        ]


@register
class StrengOpParticulierTerrein(SkeletonCheck):
    """EXT-004: een streng op of nabij particulier terrein (BRK)."""

    id = "EXT-004"
    title = "Streng op of nabij particulier terrein (op basis van BRK-percelen)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("vrijvervalrioolleidingen",)
    kenmerken = ()
    markering = MARKERING_BUITEN_SCOPE
    reden = (
        "BRK-percelen zijn in deze fase niet aangeleverd en er wordt geen vervangende bron "
        "gezocht. De check is als skelet opgenomen zodat zichtbaar blijft dat het register "
        "hem kent en dat hij niet gedraaid is. De bufferafstand staat al in de config "
        "(`drempels.ext_perceel_buffer_m`)."
    )


@register
class LozingspuntZonderWatergang(_ExterneCheck):
    """EXT-007: een lozingspunt op oppervlaktewater zonder watergang in de buurt.

    De populatie is sinds issue #94 de rol `waterlozingspunten` en niet meer de brede
    rol `lozingspunten`: de vraag of er open water naast ligt hoort alleen bij de punten
    die volgens het GWSW op oppervlaktewater lozen. Een `Lozingsput` loost "naar, of
    ontvangt uit, een ander rioolstelsel" en hoort dus juist niet aan het water te
    liggen; op De Wolden en Hoogeveen stond 32 van de 71 meldingen op zo'n put. Welke
    klassen wel meetellen staat in `[klassen] waterlozingspunt`, afgeleid uit de
    ontologie; zie BO-67.

    `notes()` leest daarnaast de brede rol, om te melden hoeveel lozingspunten buiten
    deze check vallen -- vandaar dat beide rollen gedeclareerd staan.
    """

    id = "EXT-007"
    title = "Lozingspunt zonder watergang binnen X m"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    rollen = ("lozingspunten", "waterlozingspunten")
    kenmerken = ()
    rol = "bgt_water"
    soort = "lozingspunten op oppervlaktewater"

    def objecten(self, context: CheckContext) -> Sequence[Node]:
        """De knopen die volgens het GWSW op oppervlaktewater lozen."""
        return waterlozingspunten(context)

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke klassen meetellen en hoeveel lozingspunten erbuiten vallen."""
        klassen = context.config.klassen.waterlozingspunt
        if klassen:
            scope = (
                "Alleen de klassen die volgens de GWSW-ontologie op oppervlaktewater lozen "
                f"tellen mee (`[klassen] waterlozingspunt`): {', '.join(klassen)}."
            )
        else:
            scope = (
                "Er zijn geen lozingsklassen geconfigureerd (`[klassen] waterlozingspunt`); "
                "deze check heeft niets kunnen toetsen."
            )
        notities = [*super().notes(context), scope]
        binnen = {node.uri for node in self.objecten(context)}
        buiten = sum(1 for node in lozingspunten(context) if node.uri not in binnen)
        if buiten:
            notities.append(
                f"Buiten deze check: {getal(buiten, 'lozingspunt', 'lozingspunten')} uit de "
                "bredere rol `lozingspunten`, die NET-001, NET-002 en NET-008 als "
                "netwerkeindpunt gebruiken. Een `Lozingsput` bijvoorbeeld loost volgens het "
                "GWSW naar een ander rioolstelsel; dat er geen open water naast ligt is daar "
                "geen bevinding."
            )
        return notities

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt lozingspunten zonder BGT-waterdeel binnen de afstand."""
        laag = self.laag(context)
        if laag is None:
            return
        afstand = context.config.drempels.ext_lozingspunt_water_afstand_m

        for node in _van_soort(self.selectie(context), Node):
            assert node.point is not None  # gedekt door _selecteer
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


# De drie externe bronnen die EXT-009 nodig heeft. Ontbreekt er een, dan slaat de check
# over met de standaardmelding; er is geen aparte aan/uit-schakelaar in de config, want
# de afwezigheid van een rol geeft dat gedrag al (BO-80). Een project dat de check niet
# wil, laat `nwb_wegvakken` of `top10nl` weg.
WEGVAKROLLEN = ("nwb_wegvak", "top10nl_kom", "bgt_wegdeel")


@register
class StraatZonderRiolering(_ExterneCheck):
    """EXT-009: een straat in de bebouwde kom zonder vrijvervalriolering.

    De enige EXT-check waarvan het toetsobject geen GWSW-object is. Hij vraagt niet of
    een streng ergens doorheen ligt maar of er langs deze weg riolering *bestaat*, en
    dus is de populatie het NWB-wegvak. De melding draagt daarom een eigen sleutel
    (`nwb:wegvak/<WVK_ID>`) en haar plek op de kaart via `Finding.location`, de weg die
    `uitvoer/locatie.py` openhoudt voor een bevinding zonder dataset-object.

    De uitslag kent drie toestanden en niet twee: naast rood (geen riolering, deze
    waarschuwing) en groen (riolering aangetoond) is er grijs -- niet beoordeeld, omdat
    de straat onverhard is of op drukriolering ligt. Groen en grijs dragen geen melding
    maar wel een rij in de laag `vlakken`; die komen uit het register op de context
    (`context.wegvakken`), zodat de schrijver de NWB-laag niet zelf hoeft te bevragen.
    Getekend worden ze niet: de standaardstijl heeft sinds BO-85 alleen een regel voor
    rood. Zie BO-79 en BO-81, en `checks/wegvakken.py` voor de regel zelf.
    """

    id = "EXT-009"
    title = "Straat in de bebouwde kom zonder vrijvervalriolering"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS
    rollen = ("mechanischeleidingen", "pompunits", "putten", "vrijvervalrioolleidingen")
    kenmerken = ()
    rol = "nwb_wegvak"
    soort = "wegvakken"

    @classmethod
    def bronrollen(cls) -> frozenset[str]:
        """Alle drie de wegvakrollen, niet alleen `rol`."""
        return frozenset({ROL_STUDIEGEBIED, *WEGVAKROLLEN})

    def objecten(self, context: CheckContext) -> Sequence[Node | Conduit]:
        """Leeg: de populatie van deze check zijn wegvakken en geen GWSW-objecten.

        De basisklasse splitst GWSW-objecten in toetsbaar, buiten het gebied en niet
        betrouwbaar getypeerd. Die drieslag hoort bij een check op een streng of een put;
        hier zou hij een lege bak zijn met een misleidend getal erin. `examined()` en
        `notes()` tellen daarom de wegvakken.
        """
        return []

    def ontbrekende_rol(self, context: CheckContext) -> str | None:
        """De eerste bron die deze check mist, of None."""
        if context.bronnen is None:
            return WEGVAKROLLEN[0]
        return next(
            (rol for rol in WEGVAKROLLEN if context.bronnen.layer(rol) is None),
            None,
        )

    def bruikbaar(self, context: CheckContext) -> bool:
        """Deze check heeft alle drie de wegvakrollen nodig."""
        if context.bronnen is None or context.bronnen.extent is None:
            return False
        return self.ontbrekende_rol(context) is None

    def examined(self, context: CheckContext) -> int:
        """Het aantal kandidaat-wegvakken dat beoordeeld is."""
        return len(beoordeel(context)) if self.bruikbaar(context) else 0

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elke straat zonder riolering en legt het hele oordeel in het register.

        Ook groen en grijs gaan het register in: zij worden een rij in de laag `vlakken`,
        en die rij is de enige plek waar "hier is gekeken en er ligt riolering" van "hier
        is niet gekeken" te onderscheiden is. Op de kaart komen ze niet: de standaardstijl
        tekent alleen de rode (BO-85).
        """
        drempel = context.config.drempels.ext_wegvak_streng_in_cel
        for oordeel in beoordeel(context).oordelen:
            context.wegvakken.registreer(oordeel)
            if oordeel.status != STATUS_ROOD:
                continue
            punt = oordeel.middelpunt
            yield self.finding(
                context,
                oordeel.sleutel,
                oordeel.label,
                "Deze straat ligt in de bebouwde kom, maar er ligt geen "
                f"vrijvervalriolering in haar eigen straatvlak: {oordeel.streng_in_cel:.2f} "
                f"maal de straatlengte, minder dan de drempel {drempel:g}.",
                location=(punt.x, punt.y),
                waarde=round(oordeel.streng_in_cel, 3),
                drempel=drempel,
                straat=oordeel.straat,
                plaats=oordeel.plaats,
                straatlengte_m=round(oordeel.straatlengte_m, 1),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt wat er beoordeeld is, wat niet, en waarom niet.

        Drie dingen die zonder deze regels stil zouden blijven: de wegvakken die buiten
        de kandidaatselectie vielen, de straten die wél bekeken zijn en in orde bleken
        (groen), en de straten die de regel bewust niet beoordeelt (grijs). Alleen de
        rode staan als melding in het rapport, en een lijst rode straten zonder noemer
        zegt niets.
        """
        if context.bronnen is None or context.bronnen.extent is None:
            return _bereiknotities(context, self.selectie(context), self.soort)
        ontbreekt = self.ontbrekende_rol(context)
        if ontbreekt is not None:
            return [context.bronnen.ontbreekt(ontbreekt)]

        uitslag = beoordeel(context)
        redenen = uitslag.reden_telling()
        grijs = uitslag.aantal(STATUS_GRIJS)
        drempels = context.config.drempels
        return [
            f"Kandidaten: {getal(len(uitslag), 'wegvak', 'wegvakken')} van de "
            f"{uitslag.wegvakken_totaal} NWB-wegvakken. Afgevallen: "
            f"{_afvalregel(uitslag.afgevallen)}.",
            f"Beoordeeld: {uitslag.aantal(STATUS_GROEN)} groen (riolering aangetoond) en "
            f"{uitslag.aantal(STATUS_ROOD)} rood (geen riolering). Een straat heet bediend "
            f"vanaf {drempels.ext_wegvak_streng_in_cel:g} maal haar lengte aan "
            "vrijvervalstreng in haar eigen straatvlak, of zodra er een put in dat vlak "
            "ligt (lus- en hoefijzerwegen).",
            f"Niet beoordeeld: {getal(grijs, 'wegvak', 'wegvakken')} "
            f"({redenen[REDEN_ONVERHARD]} met {REDEN_ONVERHARD}, "
            f"{redenen[REDEN_DRUKRIOLERING]} met {REDEN_DRUKRIOLERING}). Daar zegt het "
            "ontbreken van vrijverval niets over de datakwaliteit; ze staan als grijze "
            "rij in de laag `vlakken`, niet getekend in de standaardstijl (BO-85), en "
            "dragen geen melding. De drukriolering-uitzondering geldt "
            "alleen waar er wél vrijverval in het straatvlak ligt maar te weinig: een "
            "straat met nul meter is meetbaar leeg en blijft een bevinding.",
            f"Externe bronnen: {_bronregel(context)}.",
        ]


def _afvalregel(afgevallen: dict[str, int]) -> str:
    """De redenen waarom wegvakken buiten de kandidaatselectie vielen, met aantallen."""
    if not afgevallen:
        return "geen"
    return "; ".join(f"{aantal} {reden}" for reden, aantal in afgevallen.items())


def _bronregel(context: CheckContext) -> str:
    """Welke externe lagen EXT-009 gebruikt heeft, met hun omvang."""
    bronnen = context.bronnen
    if bronnen is None:
        return "geen"
    delen = []
    for rol in WEGVAKROLLEN:
        laag = bronnen.layer(rol)
        if laag is not None:
            delen.append(f"{rol} ({len(laag)} features uit `{laag.source.name}`)")
    return ", ".join(delen)


class _AhnCheck(_ExterneCheck):
    """Basis voor de hoogtechecks die het AHN als referentie gebruiken."""

    soort = "putten"

    @classmethod
    def bronrollen(cls) -> frozenset[str]:
        """Deze checks leunen op het hoogteraster in plaats van op een vectorlaag."""
        return frozenset({ROL_STUDIEGEBIED, ROL_RASTER})

    def objecten(self, context: CheckContext) -> Sequence[Node]:
        """De putten van het netwerk."""
        return netwerkknopen(context)

    def raster(self, context: CheckContext) -> RasterSampler | None:
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
            for node in _van_soort(self.selectie(context), Node):
                assert node.point is not None  # gedekt door _selecteer
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

        De De Wolden en Hoogeveen-export bevat geen `Putdekselniveau`; de `Maaiveldhoogte` bij de
        put is dan de dichtstbijzijnde benadering van de dekselhoogte. Welke van de
        twee gebruikt is staat in de melding.

        De band is halfopen en wordt op millimeters afgerond vergeleken: HGT-001
        meldt vanaf de waarschuwingsdrempel tot (niet tot en met) de foutdrempel,
        HGT-002 vanaf de foutdrempel. Zie BO-44.
        """
        drempels = context.config.drempels
        onder = getattr(drempels, self.ondergrens)
        boven = getattr(drempels, self.bovengrens) if self.bovengrens else None

        for node, gemeten in self.monsters(context):
            geregistreerd = node.dekselniveau if node.dekselniveau is not None else node.maaiveld
            if geregistreerd is None:
                continue
            # Op millimeters afgerond, en dan een halfopen band [onder, boven): een
            # verschil van precies 0,100 m is in floating point 0,0999... en zou anders
            # onder de drempel doorglippen, en een object krijgt nooit beide meldingen.
            # De afgeronde waarde is ook wat de melding toont (BO-44).
            afwijking = round(abs(geregistreerd - gemeten), 3)
            if afwijking < onder:
                continue
            if boven is not None and afwijking >= boven:
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
                afwijking_m=afwijking,
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

        onder = getattr(context.config.drempels, self.ondergrens)
        boven = getattr(context.config.drempels, self.bovengrens) if self.bovengrens else None
        bereik = (
            f"vanaf een afwijking van {onder:.3f} m tot {boven:.3f} m (vanaf daar meldt HGT-002)"
            if boven is not None
            else f"vanaf een afwijking van {onder:.3f} m"
        )
        notities.append(
            f"Gemeld {bereik}; de afwijking is op millimeters afgerond voordat hij met de "
            "drempel vergeleken is."
        )

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
    Wolden en Hoogeveen-export. Zonder deze regel claimt het rapport iets anders te hebben
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
    """HGT-001: de deksel- of maaiveldhoogte wijkt de lichte drempel of meer af."""

    id = "HGT-001"
    title = "Deksel- of maaiveldhoogte wijkt af van AHN: 10 cm of meer"
    severity = Severity.WARNING
    dimension = Dimension.ACCURACY
    rollen = ("netwerkknopen",)
    kenmerken = ("Maaiveldhoogte", "Putdekselniveau")
    ondergrens = "ahn_afwijking_waarschuwing_m"
    bovengrens = "ahn_afwijking_fout_m"


@register
class DekselAfwijkingFors(_DekselAfwijking):
    """HGT-002: de deksel- of maaiveldhoogte wijkt de zware drempel of meer af."""

    id = "HGT-002"
    title = "Deksel- of maaiveldhoogte wijkt af van AHN: 25 cm of meer"
    severity = Severity.ERROR
    dimension = Dimension.ACCURACY
    rollen = ("netwerkknopen",)
    kenmerken = ("Maaiveldhoogte", "Putdekselniveau")
    ondergrens = "ahn_afwijking_fout_m"
    bovengrens = None


@register
class BobSanityTenOpzichteVanAhn(_AhnCheck):
    """HGT-003: een BOB boven het AHN-maaiveld of onaannemelijk diep eronder."""

    id = "HGT-003"
    title = "BOB-sanity ten opzichte van AHN (boven maaiveld of onaannemelijk diep eronder)"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY
    rollen = ("netwerkknopen", "vrijvervalrioolleidingen")
    kenmerken = ("BobBeginpuntLeiding", "BobEindpuntLeiding")

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst elke BOB die op een toetsbare put uitkomt tegen het AHN."""
        diepte = context.config.drempels.bob_maximale_diepte_m
        toetsbaar = {node.uri: node for node in _van_soort(self.selectie(context), Node)}
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
                assert node.point is not None  # gedekt door _selecteer
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

    def notes(self, context: CheckContext) -> list[str]:
        """Vult de bereiknotities aan met de gehanteerde diepte en de tweede tak.

        De titel noemt de drempel sinds BO-68 niet meer als getal, want hij is
        configureerbaar; zonder deze regel zegt het rapport nergens welke grens gold --
        bij nul bevindingen al helemaal niet.
        """
        notities = super().notes(context)
        if not self.bruikbaar(context):
            return notities
        diepte = context.config.drempels.bob_maximale_diepte_m
        notities.append(
            f"Gemeld vanaf een diepteligging van meer dan {diepte:g} m onder het "
            "AHN-maaiveld (`drempels.bob_maximale_diepte_m`); een BOB boven het "
            "AHN-maaiveld is altijd een bevinding en kent geen drempel."
        )
        return notities

    def _melding(
        self, bob: float, maaiveld: float, diepte: float, zijde: str, node: Node
    ) -> str | None:
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
