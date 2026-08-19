"""Het trefferregister: de externe objecten die de checks tijdens een run raken.

De GeoPackage krijgt twee lagen met de BGT- en BAG-objecten waarnaar EXT-meldingen
verwijzen. De geometrie van zo'n object hoort niet in `Finding.details` -- dat zou de
CSV en de JSON met WKB vervuilen -- en de schrijver mag de externe lagen niet zelf
bevragen, want dan kunnen laag en testuitkomst uit elkaar lopen. Daarom registreert de
check de treffer op het moment dat hij de bevinding bouwt, en joint de schrijver later
op de sleutel.

Het register doet zelf geen uitspraken: het is een opzoektabel. Een treffer die erin
staat maar door geen enkele melding wordt aangewezen, komt nergens terecht. Daardoor
kan een register dat te veel bevat -- bijvoorbeeld doordat een gedeelde context er
entries in achterlaat -- geen verkeerde laag opleveren.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from hashlib import sha256

from shapely.geometry.base import BaseGeometry

# De kolommen waarin de aangeleverde bronnen hun identificatie dragen, in de volgorde
# waarin ze gezocht worden. Gemeten op data/gis en op de fixtures: de BGT-lagen dragen
# `lokaal_id`, de BAG-laag `identificatie`, en beide daarnaast een `id`.
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
    _afstanden: dict[tuple[str, str, str], float] = field(default_factory=dict)
    _zonder_id: dict[str, set[str]] = field(default_factory=dict)

    def registreer(
        self,
        treffer: Treffer,
        *,
        check_id: str,
        object_uri: str,
        afstand_m: float | None = None,
    ) -> str:
        """Legt een treffer vast en levert zijn sleutel terug.

        De eerste registratie van een sleutel wint; de geometrie is per sleutel per
        definitie dezelfde. `afstand_m` hoort bij deze ene melding en niet bij de
        treffer -- twee objecten kunnen hetzelfde pand op verschillende afstand raken
        -- en wordt daarom bewaard onder de drie velden die elke melding wél draagt.
        `Melding` zelf draagt de afstand niet, dus dit is de enige weg waarlangs de
        schrijver hem exact voor de meldingen van déze uitvoer kan terugvinden.
        """
        self._treffers.setdefault(treffer.sleutel, treffer)
        if afstand_m is not None:
            self._afstanden[(treffer.sleutel, check_id, object_uri)] = afstand_m
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

    def afstand(self, sleutel: str, check_id: str, object_uri: str) -> float | None:
        """De afstand die bij deze melding hoort, of None."""
        return self._afstanden.get((sleutel, check_id, object_uri))

    def __len__(self) -> int:
        """Het aantal verschillende getroffen objecten."""
        return len(self._treffers)

    def __iter__(self) -> Iterator[Treffer]:
        """Loopt over de geregistreerde treffers."""
        return iter(self._treffers.values())
