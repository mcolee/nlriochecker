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

from gwsw_orox_helpers.dataset import Conduit, GwswDataset, Node

from nlriochecker.checkconfig import ClassRoots
from nlriochecker.checks.base import CheckContext


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


def rioolputten(context: CheckContext) -> list[Node]:
    """De rioolputten: `gwsw:Rioolput` en haar subklassen (inspectie-, lozings-, overstortput, ...).

    Enger dan `putten`: alleen de putten met een verwijderbare deksel. De ontologie
    definieert `Rioolput` als "een put met een verwijderbare deksel", en alleen daaraan
    hangen het `Putdekselniveau` (via de `Dekselorientatie`) en daarmee de putdiepte
    betekenis. Een `Kolk`, een `Drainageput` of een gemaal is wel (of geen) `Put` maar
    geen `Rioolput` en valt erbuiten. Issue #64.
    """
    return _knopen(context, "sel:rioolputten", context.config.klassen.rioolput)


def pompunits(context: CheckContext) -> list[Node]:
    """De pompputten van de drukriolering: `gwsw:Pompunit` en haar subklassen.

    De ontologie omschrijft haar als "pompput in een drukrioleringsstelsel" en hangt
    haar onder `gwsw:Rioolput`; het is dus een echte deelverzameling van `putten`. Een
    `Gemaal` hoort er niet bij: dat is een bouwwerk en het einde van de afvoer, geen
    aansluitpunt van een buurt. EXT-009 leest deze rol als drukriolering-indicatie --
    staat er een pompunit naast de straat, dan zegt het ontbreken van vrijverval
    daar niets over de datakwaliteit.
    """
    return _knopen(context, "sel:pompunits", context.config.klassen.pompunit)


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


def waterlozingspunten(context: CheckContext) -> list[Node]:
    """De lozingspunten die volgens het GWSW op oppervlaktewater lozen.

    Een *rol*: geen enkele klasse dekt hem. Enger dan `lozingspunten`, en met opzet.
    EXT-007 vraagt of er open water naast een lozingspunt ligt, en die vraag hoort
    alleen bij de punten die daar volgens de ontologie op lozen: `Uitlaatconstructie`
    ("de constructie waar uitstroming van water uit een leiding naar het
    oppervlaktewater mogelijk is"), `UitlaatPunt` (datzelfde als punt) en
    `LozingspuntOppervlaktewater` ("de locatie van de lozing bevindt zich in het
    oppervlaktewater"). `Lozingsput` valt erbuiten -- die loost "naar, of ontvangt uit,
    een ander rioolstelsel" -- en de wortel `Lozingspunt` ook, want daaronder hangt naast
    `LozingspuntOppervlaktewater` ook `LozingspuntBodem`.

    De brede rol `lozingspunten` blijft ongemoeid: NET-001, NET-002 en NET-008 hebben
    haar als netwerkeindpunt nodig, en daar telt elke uitweg uit het stelsel mee. Zie
    issue #94 en BO-67.
    """
    return _knopen(context, "sel:waterlozingspunten", context.config.klassen.waterlozingspunt)


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

    Dus inclusief het mechanische riool (zie `mechanischeleidingen`) en de loze
    leidingen. Niet te verwarren met de streng: `gwsw:Streng` bestaat niet en
    `gwsw:Rioolstreng` is de NEN 3300-aanduiding voor de riolering tussen twee
    putmiddelpunten.
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


def nabijheidsleidingen(context: CheckContext) -> list[Conduit]:
    """De leidingen waarvan de onderlinge ligging in het platte vlak getoetst wordt.

    Een *rol*: geen enkele klasse dekt hem. TOP-006 (overlap), TOP-010 (buisbuffer) en
    TOP-011 (hartlijnkruising) leggen twee leidingen naast elkaar en vragen of ze elkaar
    in de weg liggen. Die vraag is alleen zinnig als beide leidingen in hetzelfde vlak
    vrijverval water voeren: een `VrijvervalRioolleiding` of een `Duiker` ("een leiding
    die oppervlaktewater-elementen verbindt"). Een kruising van vrijverval met
    drukriolering is geen gebrek -- de persleiding ligt er nu eenmaal doorheen -- en
    hetzelfde geldt voor een drain en voor een aansluitleiding naar een kolk of perceel.

    Ligt precies tussen twee bestaande rollen in, en beide zijn hier verkeerd: `leidingen`
    is te breed (dat is elke `gwsw:Leiding`, dus ook het persnet, de drains en de loze
    leidingen) en `vrijvervalrioolleidingen` te smal, want `Duiker` hangt in de ontologie
    rechtstreeks onder `Leiding`. `Drain` en `Aansluitleiding` doen dat ook, en die blijven
    er juist buiten -- de grens is dus geen enkele tak van de hierarchie. Zie issue #82 en
    BO-69.
    """
    return _verbindingen(
        context, "sel:nabijheidsleidingen", context.config.klassen.nabijheidsleiding
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
    """De leidingen van het mechanische stelsel.

    Een *rol*: de ontologie kent de klassen los van elkaar en `[klassen] mechanisch`
    noemt ze via twee wortels. `MechanischeRioolleiding` dekt Drukleiding,
    Luchtpersleiding en Vacuumleiding; `MechanischeTransportleiding` dekt Persleiding,
    Leidingsegment en Spoelleiding -- zes klassen samen (issue #56).

    Getoetst wordt het mechanische riool niet: het valt buiten het checkregister, en
    geen enkele check leest zijn kenmerken. Maar de selectie stuurt wel degelijk
    uitkomsten, op drie plekken:

    * `checks/verbanden._bouw_bereikbaarheid` legt deze leidingen als ongerichte kanten
      in de bereikbaarheidsgraaf, en beslist daarmee mee over NET-001 en NET-002 (en over
      de lozingspunten die NET-008 telt): een streng die op een pompput eindigt bereikt
      het gemaal erachter via het persnet. Zie BO-54.
    * `afbakening._componentstructuur` laat de contextschil er sinds issue #73 doorheen
      lopen, want anders valt dat gemaal bij een gebiedsrun buiten de schil (BO-56).
    * `uitvoer/gpkg.py` houdt deze leidingen uit de beoordeelde kleuring -- ze krijgen
      status `grijs` zolang er niets op staat, want "geen melding" zou daar ten onrechte
      als "getoetst en in orde" lezen -- en laat hun richtingspijl weg (issue #74).
    """
    return _verbindingen(context, "sel:mechanischeleidingen", context.config.klassen.mechanisch)


def lozeleidingen(context: CheckContext) -> list[Conduit]:
    """De loze leidingen: `gwsw:LozeLeiding` en haar subklassen.

    Buiten gebruik, maar nog in de ondergrond. Geen vrijvervalrioolleiding, dus elke
    check die daarop selecteert slaat ze over; ADM-010 kijkt juist of het
    actieve riool er nog op aansluit.
    """
    return _verbindingen(context, "sel:lozeleidingen", context.config.klassen.loze_leiding)


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
    "rioolputten": rioolputten,
    "pompunits": pompunits,
    "lozingspunten": lozingspunten,
    "waterlozingspunten": waterlozingspunten,
    "overstortputten": overstortputten,
    "bergbezinkvoorzieningen": bergbezinkvoorzieningen,
    "valconstructies": valconstructies,
    "functieloze_knopen": functieloze_knopen,
    "hulpstukken": hulpstukken,
    "leidingen": leidingen,
    "vrijvervalrioolleidingen": vrijvervalrioolleidingen,
    "nabijheidsleidingen": nabijheidsleidingen,
    "overstortleidingen": overstortleidingen,
    "bergbezinkleidingen": bergbezinkleidingen,
    "vuilwaterleidingen": vuilwaterleidingen,
    "infiltratieleidingen": infiltratieleidingen,
    "mechanischeleidingen": mechanischeleidingen,
    "lozeleidingen": lozeleidingen,
    "oppervlaktewaterobjecten": oppervlaktewaterobjecten,
}


# Per rol het `[klassen]`-veld dat haar wortelklassen draagt. De rolfuncties hierboven
# lezen `context.config.klassen.<veld>`; deze tabel maakt datzelfde opvraagbaar zonder een
# context, voor de toelichtingsregel per check in het rapport en de dekkingsmatrix (issue
# #64). `test_checks_selectie` bewaakt dat de sleutels gelijk blijven aan `_ROLLEN`.
_ROL_VELDEN: dict[str, str] = {
    "netwerkknopen": "netwerkknopen",
    "putten": "put",
    "rioolputten": "rioolput",
    "pompunits": "pompunit",
    "lozingspunten": "lozings_eindpunt",
    "waterlozingspunten": "waterlozingspunt",
    "overstortputten": "overstortput",
    "bergbezinkvoorzieningen": "bergbezinkvoorziening",
    "valconstructies": "valconstructie",
    "functieloze_knopen": "functieloze_knoop",
    "hulpstukken": "hulpstuk",
    "leidingen": "streng",
    "vrijvervalrioolleidingen": "vrijvervalleiding",
    "nabijheidsleidingen": "nabijheidsleiding",
    "overstortleidingen": "overstortleiding",
    "bergbezinkleidingen": "bergbezinkleiding",
    "vuilwaterleidingen": "vuilwater",
    "infiltratieleidingen": "infiltratie",
    "mechanischeleidingen": "mechanisch",
    "lozeleidingen": "loze_leiding",
    "oppervlaktewaterobjecten": "oppervlaktewater",
}


def klassen_van_rol(rol: str, klassen: ClassRoots) -> list[str]:
    """De wortelklassen van een rol in deze `[klassen]`-configuratie.

    `netwerkknopen` is een samengestelde property; de andere rollen lezen één veld.
    """
    return list(getattr(klassen, _ROL_VELDEN[rol]))
