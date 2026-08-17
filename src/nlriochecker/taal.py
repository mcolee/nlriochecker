"""Grammaticale hulp voor de meldingen die de checks zelf samenstellen.

De meldingen worden met f-strings opgebouwd; zonder hulp sluipen er fouten in als
"Het maaiveldhoogte" of "1 bevindingen". Deze module houdt de twee gevallen bij
die daarbij misgaan: getalcongruentie en het lidwoord.
"""

from __future__ import annotations

# De lidwoorden van de zelfstandige naamwoorden die wij zelf in meldingen zetten.
# Bewust een expliciete lijst: een onbekend woord hoort om te vallen in de test,
# niet stilzwijgend "de" te krijgen en zo in het rapport te belanden.
LIDWOORDEN: dict[str, str] = {
    "maaiveldhoogte": "de",
    "putdekselniveau": "het",
}


def vorm(aantal: int, enkelvoud: str, meervoud: str) -> str:
    """Kiest de vorm die bij dit aantal hoort, zonder het telwoord ervoor.

    Voor werkwoorden ('loopt' / 'lopen') en voor woorden waar het getal al elders
    in de zin staat.
    """
    return enkelvoud if aantal == 1 else meervoud


def getal(aantal: int, enkelvoud: str, meervoud: str) -> str:
    """Zet een telwoord bij de juiste vorm: '1 bevinding', '2 bevindingen'."""
    return f"{aantal} {vorm(aantal, enkelvoud, meervoud)}"


def met_lidwoord(zelfstandig_naamwoord: str) -> str:
    """Zet het juiste bepaalde lidwoord voor een woord dat wij zelf genereren."""
    if zelfstandig_naamwoord not in LIDWOORDEN:
        raise KeyError(
            f"{zelfstandig_naamwoord}: geen lidwoord bekend. Vul nlriochecker.taal."
            f"LIDWOORDEN aan voordat dit woord in een melding gebruikt wordt."
        )
    return f"{LIDWOORDEN[zelfstandig_naamwoord]} {zelfstandig_naamwoord}"
