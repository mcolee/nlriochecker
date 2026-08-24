"""Welke objecten horen bij welke rol: de klassenselecties van de checks, op een plek.

Een check begint bijna altijd met dezelfde vraag: geef me de putten, of de
vrijvervalrioolleidingen, of de netwerkknopen. Die vraag werd tot nu toe per
checkmodule opnieuw beantwoord, elk met een eigen cachesleutel (`adm:putten`,
`hgt:putten`, `ext:putten`), zodat dezelfde selectie meermaals werd opgebouwd en
naast elkaar in geheugen stond. Hier staat elke rol een keer.

**Naamgeving.** Heeft de GWSW-ontologie een klasse die de rol dekt, dan draagt de
functie die naam: `putten` (`gwsw:Put`), `leidingen` (`gwsw:Leiding`),
`vrijvervalrioolleidingen` (`gwsw:VrijvervalRioolleiding`). Let op het verschil
tussen `leidingen` en het woord "streng": `gwsw:Streng` bestaat niet, en
`gwsw:Rioolstreng` is iets anders -- de NEN 3300-aanduiding voor de riolering
tussen twee putmiddelpunten. Wat de checks selecteren is de `gwsw:Leiding`.

Dekt geen enkele klasse de rol, dan is de naam een *rolnaam* en zegt de docstring
dat erbij. `netwerkknopen` is het duidelijkste geval: `gwsw:Knooppunt` bestaat wel,
maar dat is de orientatie (`Putorientatie`, `Bouwwerkorientatie`, `Aansluitpunt`,
`Hulpstukorientatie`) en niet het object. Een `gwsw:Put` is dus geen `gwsw:Knooppunt`.

Welke klassen onder een rol vallen staat in `[klassen]` van de projectconfiguratie,
niet hier; de subklassen volgen uit de geladen ontologie.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from nlriochecker.checks.base import CheckContext
from nlriochecker.dataset import Conduit, GwswDataset, Node


# `Object` is het objecttype van de verzameling waarin gezocht wordt: een knoop of
# een verbinding. De beller krijgt terug wat hij erin stopt, dus geen `list[Any]`.
def _van_klassen[Object: (Node, Conduit)](
    dataset: GwswDataset, wortels: list[str], verzameling: Mapping[str, Object]
) -> list[Object]:
    """De objecten van deze klassen uit een verzameling, ontdubbeld en in vaste volgorde.

    Ontdubbelen is nodig omdat de wortelklassen elkaar mogen overlappen: een
    lozingsput is zowel een `gwsw:Put` als een lozingspunt, en zou anders twee keer
    in de netwerkknopen belanden.
    """
    gevonden = {
        uri: verzameling[uri]
        for wortel in wortels
        for uri in dataset.of_class(wortel)
        if uri in verzameling
    }
    return list(gevonden.values())


def _knopen(context: CheckContext, sleutel: str, wortels: list[str]) -> list[Node]:
    """Een knoopselectie, een keer per context opgebouwd."""
    return context.cached(
        sleutel, lambda: _van_klassen(context.dataset, wortels, context.dataset.nodes)
    )


def _verbindingen(context: CheckContext, sleutel: str, wortels: list[str]) -> list[Conduit]:
    """Een verbindingsselectie, een keer per context opgebouwd."""
    return context.cached(
        sleutel, lambda: _van_klassen(context.dataset, wortels, context.dataset.conduits)
    )


def netwerkknopen(context: CheckContext) -> list[Node]:
    """De objecten die in de netwerkdefinitie als knoop meedoen.

    Een *rol*, geen GWSW-klasse: `gwsw:Knooppunt` is de orientatie en niet het
    object. Deze selectie is de put plus de afvoer- en lozingseindpunten plus de
    bergbezinkvoorzieningen -- een BBB is in het GWSW een `gwsw:Bouwwerk` en geen
    put, maar het water loopt er wel doorheen. Zie `Klassen.netwerkknopen`.
    """
    return _knopen(context, "sel:netwerkknopen", context.config.klassen.netwerkknopen)


def putten(context: CheckContext) -> list[Node]:
    """De putten: `gwsw:Put` en haar subklassen.

    Enger dan `netwerkknopen`: een gemaal of een bergbezinkbassin hoort er niet bij.
    """
    return _knopen(context, "sel:putten", context.config.klassen.put)


def lozingspunten(context: CheckContext) -> list[Node]:
    """De punten waar het afvalwater het stelsel verlaat of binnenkomt.

    `gwsw:Lozingspunt` beschrijft precies dat, maar de rol is breder dan die ene
    klasse: `Lozingspunt` en `UitlaatPunt` zijn subklassen van `Aansluitpunt` en dus
    van `Knooppunt`, en staan daarmee op de orientatie, terwijl `Lozingsput` (een
    rioolput) en `Uitlaatconstructie` (een bouwwerk) fysieke objecten zijn. Welke van
    de twee een export gebruikt verschilt per leverancier.

    De losse klasse `Uitlaat` stond hier tot issue #56 en is geschrapt: die hangt onder
    `RepresentatieFysiekObject` en `TopologischElement`, niet onder `Knooppunt` en niet
    onder `FysiekObject`, en belandt dus in geen van beide bakken. Zelfs een object met
    dubbele typering (`Uitlaatconstructie` én `Uitlaat`) matcht al via `Uitlaatconstructie`,
    dus de regel voegde niets toe en las als dekking die er niet was.
    """
    return _knopen(context, "sel:lozingspunten", context.config.klassen.lozings_eindpunt)


def overstortputten(context: CheckContext) -> list[Node]:
    """De overstortputten: `gwsw:Overstortput`, en de stuwput die dezelfde rol speelt."""
    return _knopen(context, "sel:overstortputten", context.config.klassen.overstortput)


def bergbezinkvoorzieningen(context: CheckContext) -> list[Node]:
    """De bergbezinkvoorzieningen als knoop in het netwerk.

    Een *rol*: `gwsw:Bergbezinkvoorziening` bestaat niet. De drie bassins
    (`Bergbezinkbassin`, `Bergingsbassin`, `Bezinkbassin`) vallen wel samen onder
    `gwsw:Reservoir`, maar die klasse is te breed -- ze is een `gwsw:Bouwwerk` en
    omvat ook reservoirs die geen bergbezinkfunctie hebben.
    """
    return _knopen(
        context, "sel:bergbezinkvoorzieningen", context.config.klassen.bergbezinkvoorziening
    )


def valconstructies(context: CheckContext) -> list[Node]:
    """De constructies die een BOB-sprong verklaren.

    Een *rol*: er is geen klasse die precies deze rol dekt. `gwsw:Valput` en
    `gwsw:Zandvangput` hebben wel een gemeenschappelijke bovenklasse -- via
    `gwsw:Rioolput` respectievelijk `gwsw:Aansluitput` zijn het allebei een
    `gwsw:Put` -- maar dat is elke put.
    """
    return _knopen(context, "sel:valconstructies", context.config.klassen.valconstructie)


def functieloze_knopen(context: CheckContext) -> list[Node]:
    """De knopen die twee leidingen aan elkaar knopen zonder eigen functie.

    Een *rol*, en een die per project ingevuld wordt: in een rioolstelsel zit op
    vrijwel elke knik een put, en die put *is* een functie. Staat de lijst leeg, dan
    is deze selectie leeg en draait TOP-019 niet.
    """
    return _knopen(context, "sel:functieloze_knopen", context.config.klassen.functieloze_knoop)


def hulpstukken(context: CheckContext) -> list[Node]:
    """De hulpstukken: `gwsw:Hulpstuk` en haar subklassen (T-stuk, kruisstuk, mof, ...).

    Een hulpstuk is een knoop -- zijn `Hulpstukorientatie` is een `Knooppunt` -- maar
    geen put en geen netwerkknoop. TOP-022 en TOP-023 tellen er de leidingen op.
    """
    return _knopen(context, "sel:hulpstukken", context.config.klassen.hulpstuk)


def leidingen(context: CheckContext) -> list[Conduit]:
    """Alle leidingen: `gwsw:Leiding` en haar subklassen.

    Dus inclusief pers-, druk- en vacuumleidingen. Niet te verwarren met de streng:
    `gwsw:Streng` bestaat niet en `gwsw:Rioolstreng` is de NEN 3300-aanduiding voor
    de riolering tussen twee putmiddelpunten.
    """
    return _verbindingen(context, "sel:leidingen", context.config.klassen.streng)


def vrijvervalrioolleidingen(context: CheckContext) -> list[Conduit]:
    """De vrijvervalrioolleidingen: `gwsw:VrijvervalRioolleiding` en haar subklassen.

    Daaronder vallen ook de overstort-, bergbezink- en infiltratieleiding; die zijn
    subklassen en horen dus in deze selectie thuis.
    """
    return _verbindingen(
        context, "sel:vrijvervalrioolleidingen", context.config.klassen.vrijvervalleiding
    )


def overstortleidingen(context: CheckContext) -> list[Conduit]:
    """De overstortleidingen: `gwsw:Overstortleiding`."""
    return _verbindingen(context, "sel:overstortleidingen", context.config.klassen.overstortleiding)


def bergbezinkleidingen(context: CheckContext) -> list[Conduit]:
    """De bergbezinkriolen: `gwsw:Bergbezinkleiding` en de bergingsleiding.

    Een bergbezinkriool is een leiding en geen bouwwerk; hij hoort dus niet bij
    `bergbezinkvoorzieningen`, die de knoopkant van dezelfde voorziening beschrijft.
    """
    return _verbindingen(
        context, "sel:bergbezinkleidingen", context.config.klassen.bergbezinkleiding
    )


def vuilwaterleidingen(context: CheckContext) -> list[Conduit]:
    """De leidingen die vuilwater afvoeren.

    Een *rol*: de ontologie kent `gwsw:Vuilwaterriool` en `gwsw:GemengdRiool`, en
    voor de vraag of er vuilwater doorheen gaat tellen ze allebei mee.
    """
    return _verbindingen(context, "sel:vuilwaterleidingen", context.config.klassen.vuilwater)


def infiltratieleidingen(context: CheckContext) -> list[Conduit]:
    """De infiltratieriolen: `gwsw:Infiltratieriool`."""
    return _verbindingen(context, "sel:infiltratieleidingen", context.config.klassen.infiltratie)


def mechanischeleidingen(context: CheckContext) -> list[Conduit]:
    """De leidingen van het mechanische stelsel: pers-, druk- en vacuumleiding.

    Een *rol*: de ontologie kent de drie klassen los van elkaar. Deze selectie doet
    niet mee aan de checks -- mechanisch riool valt buiten het checkregister -- maar
    de GIS-uitvoer heeft haar nodig om die leidingen uit de strengenlaag te houden,
    waar "geen melding" ten onrechte als "getoetst en in orde" zou lezen.
    """
    return _verbindingen(context, "sel:mechanischeleidingen", context.config.klassen.mechanisch)


def oppervlaktewaterobjecten(context: CheckContext) -> list[Node | Conduit]:
    """Het oppervlaktewater uit de GWSW-dataset zelf: `gwsw:Oppervlaktewater`.

    De enige selectie die in beide verzamelingen kijkt: een sloot staat als lijn in
    de export en een vijver als punt, en beide vormen komen voor. Wie er geometrie
    van wil, leest die van het opgeleverde object af.

    Twee verschillen met `randvoorzieningen._bouw_watergeometrieen`, dat hierdoor
    vervangen wordt; ze zijn bedoeld en moeten bij die vervanging opgevangen worden.
    Ten eerste levert een selectie de objecten van de klasse, ook die zonder
    geometrie -- het filteren op `point`/`line` hoort bij de beller, niet hier. Ten
    tweede ontdubbelt deze selectie over de wortelklassen heen; dat maakt geen
    verschil zolang `[klassen] oppervlaktewater` een enkele wortel heeft, maar het
    is een correctie zodra een project er twee overlappende configureert.
    """

    def bouw() -> list[Node | Conduit]:
        """Zoekt de objecten in de knopen en anders in de verbindingen."""
        gevonden: dict[str, Node | Conduit] = {}
        for wortel in context.config.klassen.oppervlaktewater:
            for uri in context.dataset.of_class(wortel):
                # Expliciet op None toetsen en niet op de waarheidswaarde: die is
                # voor een dataclass met velden altijd waar, maar erop leunen is
                # precies wat deze codebase elders weigert te doen.
                object_: Node | Conduit | None = context.dataset.nodes.get(uri)
                if object_ is None:
                    object_ = context.dataset.conduits.get(uri)
                if object_ is not None:
                    gevonden[uri] = object_
        return list(gevonden.values())

    return context.cached("sel:oppervlaktewaterobjecten", bouw)


# Alle rollen op naam. Bewust privé: een publieke opzoeking op naam zou de
# generieke ingang zijn die deze module juist opheft -- `objecten_van_klassen` stond
# klaar, en dus schreef elke checkmodule zijn eigen variant. Een check kiest de
# functie die hij nodig heeft. De tests lopen er wel overheen, om te bewaken dat
# geen rol uitsluitend op een lege verzameling getoetst wordt; `test_checks_selectie`
# toetst ook dat deze lijst volledig is.
_ROLLEN: dict[str, Callable[[CheckContext], Sequence[object]]] = {
    "netwerkknopen": netwerkknopen,
    "putten": putten,
    "lozingspunten": lozingspunten,
    "overstortputten": overstortputten,
    "bergbezinkvoorzieningen": bergbezinkvoorzieningen,
    "valconstructies": valconstructies,
    "functieloze_knopen": functieloze_knopen,
    "hulpstukken": hulpstukken,
    "leidingen": leidingen,
    "vrijvervalrioolleidingen": vrijvervalrioolleidingen,
    "overstortleidingen": overstortleidingen,
    "bergbezinkleidingen": bergbezinkleidingen,
    "vuilwaterleidingen": vuilwaterleidingen,
    "infiltratieleidingen": infiltratieleidingen,
    "mechanischeleidingen": mechanischeleidingen,
    "oppervlaktewaterobjecten": oppervlaktewaterobjecten,
}
