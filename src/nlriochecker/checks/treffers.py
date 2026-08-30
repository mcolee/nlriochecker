"""Het trefferregister: de externe objecten die de checks tijdens een run raken.

De GeoPackage krijgt één laag `vlakken` met de BGT- en BAG-objecten waarnaar EXT-meldingen
verwijzen (pand, bouwwerk, water; issue #67). De geometrie van zo'n object hoort niet in
`Finding.details` -- dat zou de
CSV en de JSON met WKB vervuilen -- en de schrijver mag de externe lagen niet zelf
bevragen, want dan kunnen laag en testuitkomst uit elkaar lopen. Daarom registreert de
check de treffer op het moment dat hij de bevinding bouwt, en joint de schrijver later
op de sleutel.

Het register doet zelf geen uitspraken: het is een opzoektabel. Een treffer die erin
staat maar door geen enkele melding wordt aangewezen, komt nergens terecht. Daardoor
kan een register dat te veel bevat -- bijvoorbeeld doordat een gedeelde context er
entries in achterlaat -- geen verkeerde laag opleveren.

Sinds issue #104 staat er een tweede register naast, met dezelfde vorm maar een andere
afspraak: `Wegvakregister` draagt het volledige oordeel van EXT-009 over elk
kandidaat-wegvak, ook de groene en de grijze, want die krijgen een rij zonder dat er
een melding naar wijst (BO-79). Daar telt élke rij mee in de uitvoer, en dus wordt dat
register wél tot het studiegebied afgebakend. Zichtbaar op de kaart zijn alleen de rode:
de standaardstijl van `vlakken` tekent er sinds BO-85 geen groen of grijs meer bij.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from hashlib import sha256

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from nlriochecker.errors import PipelineError

# De kolommen waarin de aangeleverde bronnen hun identificatie dragen, in de volgorde
# waarin ze gezocht worden. Gemeten op data/gis_koekangerveld en op de fixtures: de
# BGT-lagen dragen `lokaal_id`, de BAG-laag `identificatie`, en beide daarnaast een `id`.
SLEUTELKOLOMMEN = ("lokaal_id", "identificatie", "id")

# Zoveel hextekens van de geometriehash gaan in een terugvalsleutel. Twaalf is 48 bits:
# ruim genoeg om binnen een bronbestand niet te botsen, kort genoeg om te lezen.
HASHLENGTE = 12


@dataclass(frozen=True)
class Treffer:
    """Een extern object waarnaar ten minste een melding verwijst."""

    sleutel: str
    bron: str
    label: str
    bronbestand: str
    geometrie: BaseGeometry
    attributen: dict[str, object]


def bouw_sleutel(
    voorvoegsel: str, attributen: dict[str, object], geometrie: BaseGeometry
) -> tuple[str, bool]:
    """De sleutel van een extern object, en of er op de geometrie is teruggevallen.

    Voorbeelden: `bgt:pand/G1690.01d7...`, `bag:pand/1690100000000178`. Draagt het
    bronbestand geen enkele identificatie, dan wordt het
    `geo:<12 hex van sha256 over de WKB>`. Die sleutel is stabiel over runs op
    hetzelfde bestand, en twee bestanden met dezelfde geometrie leveren dezelfde
    sleutel op -- precies de bedoelde ontdubbeling.

    Een lege of alleen-spaties waarde telt niet als identificatie; anders zou een
    bron met een lege kolom sleutels als `bgt:pand/` opleveren die alle objecten op
    een hoop gooien.
    """
    for kolom in SLEUTELKOLOMMEN:
        waarde = attributen.get(kolom)
        if waarde is not None and str(waarde).strip():
            return f"{voorvoegsel}/{str(waarde).strip()}", False
    # Het voorvoegsel gaat mee in de hash: twee ID-loze bronnen met dezelfde geometrie
    # -- een pand en een waterdeel op precies dezelfde vorm -- zouden anders dezelfde
    # sleutel krijgen, en dan wint de eerste registratie met haar rol, label en
    # bronbestand. Onwaarschijnlijk, maar het voorkomen kost niets.
    grondslag = voorvoegsel.encode("utf-8") + b"|" + geometrie.wkb
    return f"geo:{sha256(grondslag).hexdigest()[:HASHLENGTE]}", True


@dataclass
class Trefferregister:
    """De externe objecten die de checks tijdens deze run geraakt hebben."""

    _treffers: dict[str, Treffer] = field(default_factory=dict)
    _zonder_id: dict[str, set[str]] = field(default_factory=dict)

    def registreer(self, treffer: Treffer, *, check_id: str, object_uri: str) -> str:
        """Legt een treffer vast en levert zijn sleutel terug.

        De eerste registratie van een sleutel wint; de geometrie is per sleutel per
        definitie dezelfde.

        Tot issue #122 bewaarde dit register daarnaast de afstand per melding, omdat
        `Finding.details` de meldingenstroom niet haalde. Die weg loopt nu over
        `Check.feit_sleutels` en de zijmap `Meldingenstroom.feiten`; hier blijft
        uitsluitend de opzoektabel op sleutel over.
        """
        self._treffers.setdefault(treffer.sleutel, treffer)
        return treffer.sleutel

    def meld_zonder_id(self, check_id: str, bronbestand: str) -> None:
        """Legt vast dat een bron geen identificatie draagt.

        De check meldt dat in haar toelichting: een sleutel op grond van geometrie is
        bruikbaar, maar hij verandert zodra de geometrie in de bron wijzigt, en dat
        hoort de lezer te weten. De staat staat hier en niet op de check zelf, omdat
        hij bij de run hoort en niet bij het checkobject.
        """
        self._zonder_id.setdefault(check_id, set()).add(bronbestand)

    def zonder_id(self, check_id: str) -> tuple[str, ...]:
        """De bronbestanden waarvoor deze check op de geometriehash terugviel."""
        return tuple(sorted(self._zonder_id.get(check_id, set())))

    def get(self, sleutel: str) -> Treffer | None:
        """De treffer bij deze sleutel, of None als hij niet geregistreerd is."""
        return self._treffers.get(sleutel)

    def __len__(self) -> int:
        """Het aantal verschillende getroffen objecten."""
        return len(self._treffers)

    def __iter__(self) -> Iterator[Treffer]:
        """Loopt over de geregistreerde treffers."""
        return iter(self._treffers.values())


@dataclass(frozen=True)
class Wegvakoordeel:
    """Het oordeel van EXT-009 over een kandidaat-wegvak (issue #104).

    Anders dan een `Treffer` hierboven staat dit oordeel *wel* op zichzelf: de laag
    `vlakken` draagt naast de rode wegvakken ook de groene en de grijze, en die dragen
    per definitie geen melding. Dat is de derde uitvoertoestand van BO-79, en dit
    register is de enige weg waarlangs de schrijver eraan komt -- hij mag de NWB-laag
    niet zelf bevragen, want dan kunnen laag en uitslag uit elkaar lopen. Getekend wordt
    alleen rood; groen en grijs blijven een rij zonder stijlregel (BO-85).

    `sleutel` is `nwb:wegvak/<WVK_ID>` en is ook de `object_uri` van de melding bij een
    rood wegvak; `middelpunt` is haar foutlocatie en tegelijk het punt waarop de
    afbakening tot een studiegebied werkt. `aandeel_onverhard` is `None` als er geen
    BGT-wegdeel naast de straat ligt: dan is er niets gemeten, en dat is iets anders
    dan een aandeel van nul.

    Het veld heet `straatlengte_m` en niet `lengte_m`: dat laatste is op een `Conduit`
    de afgeleide eigenschap achter `LengteLeiding`, en de AST-sweep van issue #64 zou
    elke lezing ervan als een kenmerklezing tellen -- dezelfde val als bij
    `_Kruising.waterdeel` in `checks/extern.py` (issue #96).
    """

    sleutel: str
    straat: str
    plaats: str
    status: str
    reden: str
    straatlengte_m: float
    streng_in_cel: float
    aandeel_onverhard: float | None
    middelpunt: Point
    vlak: BaseGeometry
    bronbestand: str

    @property
    def label(self) -> str:
        """De aanduiding van dit wegvak: de straatnaam, met de plaats erachter."""
        return f"{self.straat} ({self.plaats})" if self.plaats else self.straat


@dataclass
class Wegvakregister:
    """De wegvakken die EXT-009 tijdens deze run beoordeeld heeft.

    Dezelfde vorm als het trefferregister hierboven -- een opzoektabel op sleutel, door
    de check gevuld terwijl hij draait -- met een verschil dat er wezenlijk toe doet:
    hier telt élke rij mee in de uitvoer, ook zonder melding. Daarom is dit register wél
    aan de afbakening onderworpen (`binnen`), terwijl het trefferregister vanzelf
    meebeweegt met de meldingen die ernaar wijzen.
    """

    _oordelen: dict[str, Wegvakoordeel] = field(default_factory=dict)

    def registreer(self, oordeel: Wegvakoordeel) -> None:
        """Legt het oordeel over een wegvak vast, en weigert een tegenspraak luid.

        Anders dan bij het trefferregister hierboven is een tweede, *afwijkend* oordeel op
        dezelfde sleutel hier geen onschuldige dubbeling maar een fout: élke rij in dit
        register komt in de laag `vlakken` terecht, dus stil de eerste laten winnen betekent
        een kaart die iets anders zegt dan de uitslag. Precies zo ging het mis toen
        `toetsloop._per_gebied` het register niet per gebied ververste: elk gebied
        herberekende het oordeel tegen zijn eigen uitgedunde dataset en het eerste gebied
        won. Een gelijk oordeel opnieuw registreren mag; dat is geen tegenspraak.
        """
        eerder = self._oordelen.setdefault(oordeel.sleutel, oordeel)
        if eerder is not oordeel and (eerder.status, eerder.reden) != (
            oordeel.status,
            oordeel.reden,
        ):
            raise PipelineError(
                f"wegvakregister: {oordeel.sleutel} ({oordeel.label}) is al geregistreerd als "
                f"{eerder.status!r} en wordt nu {oordeel.status!r}. Twee runs delen hetzelfde "
                "register terwijl zij op verschillende datasets draaien; geef elke run een "
                "eigen `Wegvakregister` (zie `toetsloop._per_gebied`)."
            )

    def get(self, sleutel: str) -> Wegvakoordeel | None:
        """Het oordeel bij deze sleutel, of None."""
        return self._oordelen.get(sleutel)

    def binnen(self, bevat: Callable[[Point], bool]) -> Wegvakregister:
        """Een register met alleen de wegvakken waarvan het middelpunt binnen valt.

        Het predicaat komt van de aanroeper (`StudyArea.bevat`), zodat deze module niets
        van studiegebieden hoeft te weten. Het middelpunt is dezelfde plek waarop
        `beperk_tot_studiegebied` de meldingen afbakent, dus laag en uitslag houden
        dezelfde grens.
        """
        return Wegvakregister(
            {
                sleutel: oordeel
                for sleutel, oordeel in self._oordelen.items()
                if bevat(oordeel.middelpunt)
            }
        )

    def __len__(self) -> int:
        """Het aantal beoordeelde wegvakken."""
        return len(self._oordelen)

    def __iter__(self) -> Iterator[Wegvakoordeel]:
        """Loopt over de oordelen, op sleutel gesorteerd."""
        return iter([self._oordelen[sleutel] for sleutel in sorted(self._oordelen)])
