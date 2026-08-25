"""De SHACL-nulmeting als bevindingen op dataset-objecten.

De nulmeting voedde tot nu toe alleen de typeringspoort; de overtredingen zelf
verdwenen. Deze module zet ze om in `Nulbevinding`'s, zodat `uitvoer.melding` er
gewone meldingen van kan maken en alle vier de uitvoervormen laten zien welk gebrek
uit de GWSW SHACL-nulmeting komt, en uit welke conformiteitsklasse.

Drie dingen gebeuren hier, en nergens anders:

1. **De join.** De kolom `Focus node` draagt het URI-fragment uit de dataset. Meestal
   is dat een knoop of een streng en is de join direct. Bij een leidingeinde niet:
   `lei2806-2807-1_lei2706_beg2706` is een `BeginpuntLeiding` die via `hasPart` onder
   de leidingorientatie hangt en via `hasAspect` onder de streng. Er wordt daarom
   omhooggelopen tot een knoop of streng -- dezelfde beweging als
   `dataset.resolve_network_node`. Op De Wolden en Hoogeveen herleidt 98% van de overtredingen zo
   tot een object: 103.780 van de 105.963. Wat overblijft zijn de stelsels
   (`vw_geb_6`, 575 stuks) en drie klassenamen uit `CfkTypes_typ` -- objecten die
   geen put en geen streng zijn, en dat ook niet horen te worden.
2. **De ontdubbeling.** Dezelfde overtreding staat vaak in meerdere CFK-rapporten.
   Er komt er een, met de conformiteitsklassen erbij. De sleutel is (focusnode,
   vorm, boodschap): binnen een rapport is (focusnode, vorm) al uniek, en de
   boodschap zit erin omdat dezelfde vorm per CFK een andere drempel kan noemen --
   dan zijn het echt twee eisen en horen het twee bevindingen te zijn.
3. **De systemisch-vlag.** Per (vorm, objecttype), met als noemer het aantal
   instanties van dat type in de dataset. Zonder objecttype of zonder instanties is
   er geen noemer en valt de vlag naar de veilige kant: een melding ten onrechte
   systemisch noemen haalt hem van de kaart.

De teller van die vlag telt over de volledige export, vóór afbakening tot een
studiegebied -- dezelfde keuze als bij de eigen checks (`melding._is_systemisch`), en
om dezelfde reden: anders betekent "systemisch" iets anders naargelang er een gebied
is opgegeven.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from rdflib import URIRef

from nlriochecker.dataset import GWSW, GwswDataset, aspect_holders_of, part_holders_of
from nlriochecker.meting import Nulmeting
from nlriochecker.uitvoer.identiteit import kort

logger = logging.getLogger(__name__)

# Het voorvoegsel van elk check-ID uit de nulmeting; ook de categorie, want die is
# het deel van het ID voor het eerste koppelteken (`melding.categorie_van`).
CHECK_VOORVOEGSEL = "NULMETING"

# De SHACL-ernst zoals de GWSW-server hem schrijft. Alles wat geen `Violation` is
# geldt als waarschuwing: het checkregister kent maar twee niveaus, en een onbekende
# derde als fout lezen zou zwaarder wegen dan de meting rechtvaardigt.
ERNST_VIOLATION = "Violation"

# Hoe ver er omhoog gelopen wordt. De langste keten in de export is drie stappen
# (beginpunt, orientatie, streng); de rem is er tegen een cyclus in de brondata.
MAX_DIEPTE = 6

HAS_CONNECTION = URIRef(f"{GWSW}hasConnection")


@dataclass(frozen=True)
class Nulbevinding:
    """Een SHACL-overtreding, herleid tot een object uit de dataset.

    `herleid` zegt of de focusnode op een knoop of streng uitkwam. Is dat niet zo --
    een klassenaam uit `CfkTypes_typ`, een stelsel als `dru_geb_0` -- dan blijft de
    bevinding staan zonder object: hem overslaan zou betekenen dat het rapport
    zwijgt over een gebrek dat de nulmeting wel telt.
    """

    check_id: str
    vorm: str
    focus_node: str
    ernst: str
    object_uri: str
    object_label: str
    objecttype: str
    boodschap: str
    waarde: str
    cfk: tuple[str, ...]
    systemisch: bool
    herleid: bool
    # Onwaar als de typeringspoort dit object te globaal getypeerd noemt. Dezelfde
    # betekenis als op een checkbevinding: de melding blijft staan, maar is niet
    # betrouwbaar te duiden.
    typering_betrouwbaar: bool = True


def bouw_nulbevindingen(
    nulmeting: Nulmeting,
    dataset: GwswDataset,
    systemisch_drempel: float,
    onbetrouwbaar: frozenset[str] = frozenset(),
) -> list[Nulbevinding]:
    """Zet de rapporten van een nulmeting om in ontdubbelde bevindingen.

    De volgorde is die van (vorm, focusnode, boodschap), zodat twee runs op dezelfde
    bestanden hetzelfde opleveren en een diff tussen meetmomenten geen ruis geeft.

    `onbetrouwbaar` is de uitkomst van de typeringspoort uit diezelfde nulmeting. Hij
    komt van de beller en wordt hier niet zelf berekend: `analysis.bepaal_typeringspoort`
    is er de ene plek voor, en die draait in `toetsrun` al.
    """
    ruw = _ontdubbel(nulmeting)
    joiner = _Joiner(dataset)
    tellingen = _tellingen(ruw)

    bevindingen = []
    for (vorm, focus, boodschap), gegevens in sorted(ruw.items()):
        ernst_rauw, waarde, objecttype, label, cfks = gegevens
        uri = joiner.herleid(focus)
        # Een focusnode die geen knoop of streng is maar wel een geregistreerd stelsel
        # (#17) krijgt het stelsel zelf als object, zodat de melding zegt waarover ze
        # gaat. Het blijft onherleid: een stelsel is geen knoop of streng, dus het krijgt
        # geen studiegebied, geen foutlocatie en geen kaartobject (BO-12, #75).
        stelsel_uri = joiner.stelsel(focus) if not uri else ""
        object_uri = uri or stelsel_uri
        object_ = (dataset.nodes.get(uri) or dataset.conduits.get(uri)) if uri else None
        eigen_label = object_.label if object_ is not None else ""
        bevindingen.append(
            Nulbevinding(
                check_id=f"{CHECK_VOORVOEGSEL}-{vorm}",
                vorm=vorm,
                focus_node=focus,
                ernst="F" if ernst_rauw == ERNST_VIOLATION else "W",
                object_uri=object_uri,
                object_label=eigen_label or label,
                objecttype=objecttype,
                boodschap=boodschap,
                waarde=waarde,
                cfk=tuple(sorted(cfks)),
                systemisch=_systemisch(
                    vorm, objecttype, tellingen, joiner.instanties, systemisch_drempel
                ),
                herleid=bool(uri),
                typering_betrouwbaar=uri not in onbetrouwbaar,
            )
        )
    return bevindingen


# Wat er per ontdubbelde overtreding onthouden wordt: ernst, waarde, objecttype,
# label en de conformiteitsklassen die hem noemen.
_Gegevens = tuple[str, str, str, str, set[str]]


def _ontdubbel(nulmeting: Nulmeting) -> dict[tuple[str, str, str], _Gegevens]:
    """Groepeert de meldingen van alle rapporten op (vorm, focusnode, boodschap).

    De eerste CFK op alfabet levert de ernst, de waarde, het objecttype en het label.
    Op de drie meegeleverde De Wolden en Hoogeveen-rapporten zijn die over alle 105.963 sleutels
    gelijk, en dat is ook wat je verwacht zodra de boodschap gelijk is. Maar niets
    dwingt het af, dus wijken ze toch af, dan wordt dat gelogd in plaats van
    stilzwijgend de eerste te nemen -- zwijgen zou hier betekenen dat een CFK een
    overtreding zwaarder noemt dan een andere en dat niemand het merkt.
    """
    verzameld: dict[tuple[str, str, str], _Gegevens] = {}
    afwijkingen = 0
    for cfk in nulmeting.cfks:
        meldingen = nulmeting.report(cfk).findings
        kolommen = zip(
            meldingen["Source"],
            meldingen["Focus node"],
            meldingen["Message"],
            meldingen["Severity"],
            meldingen["Value"],
            meldingen["Objecttype"],
            meldingen["Label"],
            strict=True,
        )
        for vorm, focus, boodschap, ernst, waarde, objecttype, label in kolommen:
            sleutel = (vorm, focus, boodschap)
            bestaand = verzameld.get(sleutel)
            if bestaand is None:
                verzameld[sleutel] = (ernst, waarde, objecttype, label, {cfk})
            else:
                afwijkingen += _meld_afwijking(
                    sleutel, bestaand, (ernst, waarde, objecttype, label), cfk, afwijkingen
                )
                bestaand[4].add(cfk)
    if afwijkingen > MAX_GEMELDE_AFWIJKINGEN:
        logger.warning(
            "In totaal %d overtredingen worden door de CFK-rapporten verschillend "
            "beschreven; alleen de eerste %d staan hierboven.",
            afwijkingen,
            MAX_GEMELDE_AFWIJKINGEN,
        )
    return verzameld


# Zoveel afwijkingen tussen CFK-rapporten worden er per meting hooguit met naam en
# toenaam gelogd. Een export waarin ze structureel voorkomen zou anders tienduizenden
# regels opleveren en het logboek onbruikbaar maken; het totaal volgt aan het eind.
MAX_GEMELDE_AFWIJKINGEN = 5


def _meld_afwijking(
    sleutel: tuple[str, str, str],
    bestaand: _Gegevens,
    nieuw: tuple[str, str, str, str],
    cfk: str,
    gemeld: int,
) -> bool:
    """Logt dat twee CFK-rapporten dezelfde overtreding verschillend beschrijven.

    Geeft terug of er iets te melden viel. De teller staat bij de beller en niet als
    moduleniveau-variabele: die zou over gebieden, over aanroepen en over tests heen
    blijven staan, en dan hangt af wat er gelogd wordt van wat er daarvoor gebeurde.
    """
    if bestaand[:4] == nieuw:
        return False
    if gemeld < MAX_GEMELDE_AFWIJKINGEN:
        vorm, focus, _boodschap = sleutel
        logger.warning(
            "%s op %s wordt door %s anders beschreven dan door de eerdere klasse(n) "
            "(%s tegen %s); de eerste op alfabet telt.",
            vorm,
            focus,
            cfk,
            nieuw,
            bestaand[:4],
        )
    return True


def _tellingen(ruw: dict[tuple[str, str, str], _Gegevens]) -> dict[tuple[str, str], int]:
    """Het aantal overtredingen per (vorm, objecttype)."""
    per_groep: dict[tuple[str, str], int] = defaultdict(int)
    for (vorm, _focus, _boodschap), gegevens in ruw.items():
        per_groep[(vorm, gegevens[2])] += 1
    return dict(per_groep)


def _systemisch(
    vorm: str,
    objecttype: str,
    tellingen: dict[tuple[str, str], int],
    instanties: dict[str, int],
    drempel: float,
) -> bool:
    """Geeft aan of deze vorm vrijwel elke instantie van dit objecttype raakt."""
    if not objecttype:
        return False
    noemer = instanties.get(objecttype)
    if noemer is None or noemer == 0:
        return False
    return tellingen.get((vorm, objecttype), 0) / noemer > drempel


class _Joiner:
    """Herleidt een SHACL-focusnode tot de knoop of streng waar hij bij hoort.

    Houdt zijn antwoorden vast: op De Wolden en Hoogeveen komen dertigduizend focusnodes langs,
    en de opgaande wandeling raakt de rdflib-graaf.
    """

    def __init__(self, dataset: GwswDataset) -> None:
        self._dataset = dataset
        self._objecten = frozenset(dataset.nodes) | frozenset(dataset.conduits)
        self._per_fragment = {kort(uri): uri for uri in self._objecten}
        self._basis = _basis(self._objecten)
        self._memo: dict[str, str] = {}
        self._instanties: dict[str, int] | None = None

    @property
    def instanties(self) -> dict[str, int]:
        """Het aantal knopen en strengen per korte typenaam.

        De telling gaat over `types_of`, dus inclusief de typen van de orientatie:
        een Lozingspunt staat volgens het GWSW daar, en de nulmeting noemt hem in
        haar `type=`. Alleen de korte naam telt, want dat is wat `Detail-value`
        draagt.
        """
        if self._instanties is None:
            per_type: dict[str, int] = defaultdict(int)
            for uri in self._objecten:
                for volledig in self._dataset.types_of(uri):
                    per_type[volledig.rsplit("/", 1)[-1].rsplit("#", 1)[-1]] += 1
            self._instanties = dict(per_type)
        return self._instanties

    def stelsel(self, focus: str) -> str:
        """De URI van het geregistreerde stelsel achter deze focusnode, of leeg.

        Voor focusnodes die `herleid` niet op een knoop of streng kreeg: een deel ervan
        zijn stelselobjecten (`vw_geb_1` c.s.), die #17 blootlegde. Een
        `CfkTypes_typ`-klassenaam matcht hier niet: die is een klasse, geen instantie,
        dus `graph_is_a` op de Stelsel-afsluiting geeft False.

        De melding houdt het stelsel als `object_uri`, zodat in de CSV, de JSON en de
        meldingentabel te zien blijft over welk stelsel de overtreding gaat. Een
        kaartobject wordt het niet: een stelsel is geen knoop of streng, en sinds issue
        #75 tekent de GeoPackage er ook geen vlak meer omheen. Het rapport telt deze
        overtredingen daarom apart onder "geen kaartobject" (`bevindingen.py`).

        Alleen een lokaal stelsel -- met alleen strengen -- koppelt hier, via
        `dataset.stelsel_leden`. De gemeentebrede `_geb_0`-buckets uit #17 dragen
        strengen en putten door elkaar heen over de hele gemeente; zo'n bak is geen
        stelsel waarover een overtreding iets plaatselijks zegt, en die blijft
        objectloos.
        """
        if not self._basis:
            return ""
        kandidaat = f"{self._basis}{focus}"
        if not self._dataset.graph_is_a(kandidaat, "Stelsel"):
            return ""
        strengen, knopen = self._dataset.stelsel_leden(kandidaat)
        return kandidaat if strengen and not knopen else ""

    def herleid(self, focus: str) -> str:
        """De URI van de knoop of streng achter deze focusnode, of leeg."""
        if focus in self._memo:
            return self._memo[focus]
        direct = self._per_fragment.get(focus)
        if direct is not None:
            self._memo[focus] = direct
            return direct
        gevonden = self._omhoog(focus) if self._basis else ""
        self._memo[focus] = gevonden
        return gevonden

    def _omhoog(self, focus: str) -> str:
        """Loopt in de breedte omhoog tot de eerste knoop of streng.

        In de breedte en niet langs een enkel pad: een onderdeel kan meer dan een
        houder hebben, en de eerste die rdflib oplevert hoeft niet de houder te zijn
        die op een object uitkomt. Een enkelpadswandeling zou dan leeg teruggeven
        terwijl er wel degelijk een object boven hangt -- en welke houder "de eerste"
        is, hangt af van de opslagvolgorde van rdflib en is dus niet stabiel tussen
        versies of tussen twee keer inlezen.

        Bij gelijke diepte wint de kleinste URI. Dat is willekeurig maar
        deterministisch, en dat is wat telt: twee runs op dezelfde bestanden moeten
        dezelfde meldingen opleveren.
        """
        start = f"{self._basis}{focus}"
        if start in self._objecten:
            return start
        gezien = {start}
        laag = [start]
        for stap in range(MAX_DIEPTE):
            volgende: set[str] = set()
            for uri in laag:
                volgende |= self._ouders(uri, met_verbinding=stap == 0) - gezien
            if not volgende:
                return ""
            gevonden = sorted(volgende & self._objecten)
            if gevonden:
                return gevonden[0]
            gezien |= volgende
            laag = sorted(volgende)
        return ""

    def _ouders(self, uri: str, *, met_verbinding: bool) -> set[str]:
        """De objecten die dit object bevatten, van sterk naar zwak verband.

        `hasPart` en `hasAspect` zijn insluitingen: wat eraan hangt hoort echt bij de
        houder. Levert een van beide iets op, dan is dat het antwoord en komt
        `hasConnection` er niet meer aan te pas.

        `hasConnection` is geen insluiting maar een symmetrische netwerkverbinding.
        Hij doet daarom alleen mee bij de eerste stap en alleen als laatste. Die twee
        beperkingen samen zijn wat het veilig maakt: een `Maaiveldorientatie` hangt in
        de De Wolden en Hoogeveen-export via `hasConnection` onder haar putorientatie en heeft
        verder geen houder, dus die wordt zo alsnog aan zijn put toegewezen (1.605
        overtredingen). Een `BeginpuntLeiding` heeft ook een `hasConnection`, naar de
        put aan die kant, maar heeft daarnaast een `hasPart`-houder in zijn
        leidingorientatie -- en die gaat voor, dus zijn melding landt op de streng en
        niet op de verkeerde soort object. En doordat de verbinding alleen in de
        eerste stap meedoet, kan de wandeling daarna niet zijwaarts het netwerk in
        lopen.

        Beide schrijfrichtingen van `hasConnection` worden gelezen. Het GWSW noemt hem
        een `owl:SymmetricProperty` zonder inverse, dus welke van de twee objecten
        subject is, is een keuze van de exporteur. De De Wolden en Hoogeveen-export schrijft
        `:knp1_put gwsw:hasConnection :knp1_put_maa`; een export die het andersom doet
        zou anders stil 1.605 meldingen van de kaart laten vallen.
        """
        knoop = URIRef(uri)
        graaf = self._dataset.graph
        insluitend = {str(houder) for houder in part_holders_of(graaf, knoop)}
        insluitend |= {str(houder) for houder in aspect_holders_of(graaf, knoop)}
        if insluitend or not met_verbinding:
            return insluitend
        verbonden = {str(ander) for ander in graaf.subjects(HAS_CONNECTION, knoop)}
        verbonden |= {str(ander) for ander in graaf.objects(knoop, HAS_CONNECTION)}
        return verbonden


def _basis(objecten: frozenset[str]) -> str:
    """De naamruimte van de export, afgeleid uit een willekeurig object.

    Een OroX-export gebruikt een enkele naamruimte voor al haar objecten
    (`http://sparql.gwsw.nl/<export>#`), dus een object volstaat. Draagt die geen
    `#`, dan is er geen fragmentconventie en is er niets omhoog te lopen.
    """
    for uri in sorted(objecten):
        if "#" in uri:
            return uri.rsplit("#", 1)[0] + "#"
    return ""
