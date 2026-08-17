"""De stabiele identificatie van een melding.

De ID moet ongevoelig zijn voor wijzigingen in de meldingtekst — die herformuleren
we regelmatig — en gevoelig voor het feit zelf. Hij bestaat daarom uit de check, de
betrokken objecten en de detailsleutels die de check zelf als onderscheidend
opgeeft.
"""

from __future__ import annotations

from hashlib import sha256

# Zestien hextekens is 64 bits: ruim genoeg voor honderdduizenden meldingen per run
# en kort genoeg om in een attributentabel te lezen.
ID_LENGTE = 16


def melding_id(
    check_id: str,
    object_uri: str,
    object2_uri: str,
    sleutels: dict[str, str],
) -> str:
    """Bouwt de deterministische ID van een melding."""
    onderscheid = ";".join(f"{naam}={sleutels[naam]}" for naam in sorted(sleutels))
    grondslag = f"{check_id}|{object_uri}|{object2_uri}|{onderscheid}"
    return sha256(grondslag.encode("utf-8")).hexdigest()[:ID_LENGTE]


def kort(uri: str) -> str:
    """Het leesbare deel van een object-URI: het fragment achter de `#`.

    De GWSW-URI's zijn van de vorm `http://sparql.gwsw.nl/<export>#knp3437`; alleen
    het fragment zegt iets tegen een lezer, en het is binnen een export uniek. Een
    URI zonder `#` komt niet uit de dataset maar uit een externe bron (BGT, BAG) en
    blijft ongewijzigd: daar is de hele tekst de identificatie.
    """
    return uri.split("#", 1)[1] if "#" in uri else uri
