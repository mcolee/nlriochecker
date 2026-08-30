"""Mensleesbare teksten bij de SHACL-vormen van de GWSW-nulmeting (issue #101).

De nulmeting levert haar overtredingen in de taal van de SHACL-vorm: "Subject Put,
path hasAspect, object HoogtePut - aantal voorkomens wijkt af (exact=1)". Dat is een
juiste beschrijving van de geschonden regel en een onbruikbare zin voor de beheerder
die met het rapport aan de slag moet. Deze module zet er een vaste Nederlandse zin
naast: "Put zonder (of met meer dan één) geregistreerde puthoogte".

De tabel zelf staat als package-resource in `nulmeting_teksten.toml` -- 43 vormen, de
volledige verzameling die in de drie De Wolden-rapporten voorkomt, met teksten die de
auteur heeft vastgesteld (BO-74). De code hier kent geen enkele tekst en geen enkele
grens: zij leest de tabel en vult de sjabloonvelden uit de meldingsrij.

Drie regels, en ze horen bij elkaar:

1. **Geen grens uit de code of de config.** `{min}`, `{max}` en `{n}` komen uit de rij
   waarover de melding gaat -- `{min}`/`{max}` uit de grens die de kolom `Message`
   achteraan tussen haakjes noemt, `{n}` uit het getal waarmee de kolom `Value` opent.
   De GWSW-server mag per conformiteitsklasse een andere grens stellen; een hier
   opgeschreven getal zou dan de verkeerde noemen.
2. **Niet in te vullen is niet verzinnen.** Kan een veld niet uit de rij gehaald
   worden, dan vervalt de haakjesgroep eromheen en blijft de rest van de zin staan.
   Een groep zonder sjabloonveld -- `(bijv. "Put" waar "Inspectieput" hoort)` -- hoort
   bij de tekst en blijft altijd staan.
3. **Een onbekende vorm valt terug op de technische tekst.** Zwijgen zou een gebrek
   laten verdwijnen dat de nulmeting wel telt. `vertaald()` maakt zichtbaar dat het
   gebeurde, zodat het rapport kan tellen hoeveel meldingen zo'n terugval kregen.

De grens gaat uitsluitend naar deze zin. Het meldingveld `drempel` blijft leeg bij een
nulmetingmelding, zoals `docs/json-schema.md` zegt: dat is een tweede lezing van
dezelfde tekst en die zou een eigen contract worden.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from functools import cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType

BESTANDSNAAM = "nulmeting_teksten.toml"
TABELSLEUTEL = "vormen"

# Een sjabloonveld in een tekst: `{min}`, `{max}`, `{n}`.
_VELD = re.compile(r"\{(\w+)\}")

# Een groep tussen haakjes met ten minste een sjabloonveld erin. Alleen zo'n groep
# vervalt als het veld niet te vullen is; haakjes die bij de tekst horen blijven staan.
_GROEP_MET_VELD = re.compile(r"\s*\([^()]*\{\w+\}[^()]*\)")

# De grens die de SHACL-boodschap achteraan tussen haakjes noemt, zoals
# `... waarde wijkt af (min=63,max=4000)` of `... wijkt af (exact=1)`.
_GRENS = re.compile(r"\(([^()]*)\)\s*$")
_PAAR = re.compile(r"(\w+)\s*=\s*(-?\d+(?:\.\d+)?)")

# Het getal waarmee de kolom `Value` opent: `0 (integer)`, `164.200 (decimal)`.
_AANTAL = re.compile(r"\s*(-?\d+)\b")


@cache
def vormteksten() -> Mapping[str, str]:
    """De vertaaltabel: SHACL-vormnaam naar leesbare zin.

    Onveranderlijk teruggegeven: de tabel is een package-resource die elke run leest,
    en een beller die er een sleutel in wijzigt zou elke volgende melding raken.
    """
    with tabelpad().open("rb") as bestand:
        inhoud = tomllib.load(bestand)
    return MappingProxyType(dict(inhoud[TABELSLEUTEL]))


def tabelpad() -> Path:
    """Het pad van de meegeleverde vertaaltabel."""
    return Path(str(resources.files("nlriochecker").joinpath(BESTANDSNAAM)))


def vertaald(vorm: str) -> bool:
    """Of deze SHACL-vorm een vastgestelde tekst heeft."""
    return vorm in vormteksten()


def leesbaar(vorm: str, boodschap: str, waarde: str) -> str:
    """De leesbare zin bij deze overtreding, of de technische boodschap.

    `boodschap` en `waarde` zijn de kolommen `Message` en `Value` van de meldingsrij;
    daar komen de sjabloonvelden uit. Een vorm zonder tekst valt terug op `boodschap`.
    """
    sjabloon = vormteksten().get(vorm)
    if sjabloon is None:
        return boodschap
    return vul_sjabloon(sjabloon, boodschap, waarde)


def vul_sjabloon(sjabloon: str, boodschap: str, waarde: str) -> str:
    """Vult de sjabloonvelden van een tekst uit de meldingsrij.

    Een haakjesgroep waarvan een veld niet uit de rij te halen is vervalt in haar
    geheel; wat overblijft is de zin zonder ingevulde grens.
    """
    velden = _velden(boodschap, waarde)

    def groep(match: re.Match[str]) -> str:
        gevonden = match.group(0)
        return gevonden if all(naam in velden for naam in _VELD.findall(gevonden)) else ""

    zin = _GROEP_MET_VELD.sub(groep, sjabloon)
    return _VELD.sub(lambda match: velden.get(match.group(1), ""), zin)


def _velden(boodschap: str, waarde: str) -> dict[str, str]:
    """De sjabloonwaarden die deze meldingsrij draagt.

    Uit de boodschap komen de sleutel-waardeparen van de grens achteraan (`min`, `max`,
    `exact`), uit de waarde het getal waarmee zij opent (`n`). Draagt de rij ze niet,
    dan staan ze er niet in en vervalt de groep die ze nodig heeft.
    """
    velden: dict[str, str] = {}
    grens = _GRENS.search(boodschap)
    if grens is not None:
        velden.update(dict(_PAAR.findall(grens.group(1))))
    aantal = _AANTAL.match(waarde)
    if aantal is not None:
        velden["n"] = aantal.group(1)
    return velden
