"""Hoe een object op de kaart komt te staan: zijn status en zijn popup.

De GeoPackage draagt sinds issue #13 twee objectlagen, met de gebreken *op* het
object in plaats van in een aparte meldingenlaag. Twee kolommen dragen dat: `status`
(vier waarden, waar de symbologie op filtert) en `popup_html` (voorgebakken, zodat de
maptip in QGIS een expressie van een regel is).

Beide worden hier gemaakt en nergens anders. `gpkg.py` schrijft ze weg; de QML's
lezen ze. Zou de schrijver de popup zelf in elkaar zetten, dan zou de kolom iets
anders kunnen zeggen dan de meldingentabel ernaast.

`popup_html` levert een **fragment**, geen volledig document: geen `<style>`-blok en
geen vaste breedte. Die staan een keer in de maptip van de QML (issue #15), en niet
tienduizenden keren in het bestand.

Om dezelfde reden zijn de klassenamen kort. De markup staat per object in de
GeoPackage, de stijl staat er een keer in de QML; wat hier een teken scheelt, scheelt
op de volledige De Wolden en Hoogeveen-export tienduizenden keren zoveel. Gemeten op de
Koekangerveld-run: 1.284 bytes per object met lange namen, 1.085 met korte, en dat
schaalt op de 46.925 objecten van de volledige export naar circa 60 tegen circa 51 MB.
De rest is de boodschaptekst zelf, en die valt niet in te korten zonder er informatie
uit te halen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape

from nlriochecker.taal import getal, vorm
from nlriochecker.uitvoer.melding import BRON_NULMETING, Melding

# De vier statuswaarden, en geen vijfde. De symbologie filtert erop, dus een waarde
# erbij betekent een regel erbij in elke QML.
STATUS_ROOD = "rood"
STATUS_ORANJE = "oranje"
STATUS_GROEN = "groen"
STATUS_GRIJS = "grijs"

STATUSSEN = (STATUS_ROOD, STATUS_ORANJE, STATUS_GROEN, STATUS_GRIJS)

# Wat de status in woorden zegt. De QML-legenda gebruikt dezelfde teksten, zodat
# kaart en popup hetzelfde zeggen.
STATUS_WOORD = {
    STATUS_ROOD: "fouten",
    STATUS_ORANJE: "alleen waarschuwingen",
    STATUS_GROEN: "geen eigen gebrek",
    STATUS_GRIJS: "niet geanalyseerd",
}

# Zoveel meldingen toont de popup; daarna volgt een afsluitende regel. Hoveren is
# een blik, geen lijst doorlopen -- daarvoor is de meldingentabel.
MAX_MELDINGEN_IN_POPUP = 5

ERNST_SYMBOOL = {"F": "✕", "W": "⚠"}


@dataclass(frozen=True)
class Objectkop:
    """De kopregel van een popup: wat voor object dit is en hoe het ervoor staat."""

    label: str
    objecttype: str
    status: str
    # Losse feiten die alleen bij sommige objecten horen: stelsel, lengte en de
    # BOB-richtingsregel van een streng. Ze staan als kant-en-klare regels in de
    # lijst, zodat deze module niets over strengen hoeft te weten.
    feiten: tuple[str, ...] = field(default=())
    # Waarom dit object buiten de beoordeling viel: mechanisch riool of contextschil.
    # Staat er ook als het object toch gekleurd is -- mechanisch riool wordt door de
    # meeste checks overgeslagen maar niet door alle, en dan hoort de lezer te weten
    # dat de stilte eromheen niets bewijst.
    reden: str = ""


def bepaal_status(meldingen: Sequence[Melding], *, geanalyseerd: bool) -> str:
    """De status van een object: rood, oranje, groen of grijs.

    `geanalyseerd` is onwaar voor een object dat buiten de beoordeling viel -- de
    contextschil van een studiegebied, of mechanisch riool, dat het checkregister
    grotendeels overslaat.

    **Grijs wint niet van een gebrek.** Dat is een correctie op de aanname dat
    mechanisch riool ongetoetst blijft: TOP-010 en TOP-011 draaien er wel degelijk op,
    en de SHACL-nulmeting sowieso. Op de Koekangerveld-run dragen 17 van de 20
    mechanische strengen een melding. Zouden die grijs blijven, dan zou de kaart
    beweren dat er niets bekeken is terwijl er fouten op staan -- en sinds
    `meldinglocaties` verviel is er geen tweede plek meer waar ze wel zichtbaar zijn.
    Grijs betekent daarom: niet beoordeeld **en niets gevonden**. Wat er wel gevonden
    is kleurt het object, en de popup zegt erbij dat het maar deels beoordeeld is.

    Systemische meldingen tellen niet mee, net als in `ergste_ernst`, `n_fout` en
    `n_waarschuwing`. Op De Wolden en Hoogeveen draagt de nulmeting 68.882 systemische meldingen
    op 105.963; zouden die meetellen, dan is vrijwel elke put rood en zegt de kaart
    niets meer. Gevolg: een object waarvan *alle* meldingen systemisch zijn krijgt
    groen (of grijs). Dat betekent hier "geen gebrek dat dit object van zijn buren
    onderscheidt", niet "in orde" -- de kolom `n_systemisch` zegt het, en de popup
    zet het er met zoveel woorden onder.
    """
    eigen = [melding for melding in meldingen if not melding.systemisch]
    if any(melding.ernst == "F" for melding in eigen):
        return STATUS_ROOD
    if eigen:
        return STATUS_ORANJE
    return STATUS_GROEN if geanalyseerd else STATUS_GRIJS


def popup_html(
    kop: Objectkop, meldingen: Sequence[Melding], *, toon_systemisch: bool = False
) -> str:
    """Bouwt de popup-inhoud van een object als HTML-fragment.

    Systemische meldingen staan er niet bij (issue #76). Zij zijn dezelfde structurele
    kwestie op (vrijwel) elk object van dit type: per object getoond verdringen ze de
    gebreken die dít object van zijn buren onderscheiden -- op de volledige export is
    twee derde van de nulmetingmeldingen systemisch. Ze worden wel geteld, met een
    afsluitende regel; stilzwijgend weglaten zou lezen als "hier is niets gevonden".
    De losse rijen blijven in de meldingentabel, de CSV en de JSON staan.

    Met `toon_systemisch` staan ze er wél bij, zonder afsluitende regel. Dat is voor een
    rij die per constructie een gebrek is -- een gemengd deelstelsel in de laag `vlakken`,
    dat alleen bestaat omdat RVZ-006 op dat deelstelsel aansloeg. Daar is er
    geen "andere objecten van dit type" om zich van te onderscheiden. Zie BO-59.

    Wat overblijft staat op prioriteit, dan check-ID, dan melding-ID: de zwaarste
    eerst, zodat de cap van vijf niet de melding wegsnijdt die de status bepaalde.

    Alles wat uit de brondata komt wordt geescaped: een label met een `<` mag de popup
    niet breken.
    """
    systemisch = 0 if toon_systemisch else sum(1 for melding in meldingen if melding.systemisch)
    gesorteerd = sorted(
        (melding for melding in meldingen if toon_systemisch or not melding.systemisch),
        key=lambda m: (m.prioriteit, m.check_id, m.melding_id),
    )
    getoond = gesorteerd[:MAX_MELDINGEN_IN_POPUP]
    rest = len(gesorteerd) - len(getoond)

    regels = [f'<div class="gwsw-popup s-{escape(kop.status)}">', _kopregel(kop)]
    if kop.feiten:
        regels.append(
            '<div class="f">' + " · ".join(escape(feit) for feit in kop.feiten) + "</div>"
        )
    if kop.reden:
        aanhef = "Niet beoordeeld" if kop.status == STATUS_GRIJS else "Maar deels beoordeeld"
        regels.append(f'<div class="r">{aanhef}: {escape(kop.reden)}.</div>')

    if getoond:
        regels.append('<ul class="m">')
        regels += [_meldingregel(melding) for melding in getoond]
        regels.append("</ul>")
        if rest:
            regels.append(f'<div class="x">… en nog {rest} andere</div>')
    elif not systemisch:
        # Alleen als er echt niets is. Draagt het object enkel systemische meldingen,
        # dan zegt de regel hieronder wat er is en hoeveel; "geen meldingen" zou dat in
        # dezelfde popup tegenspreken -- op de vlakkenlaag zelfs naast een kopregel die
        # het aantal gemelde strengen noemt.
        regels.append('<div class="z">Geen meldingen op dit object.</div>')

    if systemisch:
        regels.append(
            f'<div class="n">{getal(systemisch, "systemische melding", "systemische meldingen")} '
            f"{vorm(systemisch, 'telt', 'tellen')} niet mee in de status en "
            f"{vorm(systemisch, 'staat', 'staan')} hier niet: die vorm slaat op vrijwel elk "
            f"object van dit type aan. In de meldingentabel {vorm(systemisch, 'staat', 'staan')} "
            "zij wel.</div>"
        )

    regels.append("</div>")
    return "".join(regels)


def _kopregel(kop: Objectkop) -> str:
    """Label, GWSW-objecttype en de status in woorden."""
    naam = escape(kop.label) or "(zonder label)"
    woord = STATUS_WOORD.get(kop.status, kop.status)
    return (
        f'<div class="k"><span class="l">{naam}</span>'
        f'<span class="t">{escape(kop.objecttype)}</span>'
        f'<span class="s">{escape(woord)}</span></div>'
    )


def _meldingregel(melding: Melding) -> str:
    """Een melding als lijstitem: ernst, check, boodschap, herkomst en waarden."""
    symbool = ERNST_SYMBOOL.get(melding.ernst, escape(melding.ernst))
    delen = [
        f'<li class="e-{escape(melding.ernst)}">',
        f'<span class="e">{symbool}</span>',
        f'<span class="c">{escape(melding.check_id)}</span>',
        escape(melding.boodschap),
    ]
    if melding.waarde:
        delen.append(f'<span class="v">waarde {escape(melding.waarde)}</span>')
    if melding.drempel:
        delen.append(f'<span class="d">drempel {escape(melding.drempel)}</span>')
    delen.append(f'<span class="h">{_herkomst(melding)}</span>')
    delen.append("</li>")
    return "".join(delen)


def _herkomst(melding: Melding) -> str:
    """Waar deze melding vandaan komt: de nulmeting met haar klassen, of een eigen check."""
    if melding.bron != BRON_NULMETING:
        return "eigen check"
    klassen = ", ".join(melding.cfk)
    return f"nulmeting · {escape(klassen)}" if klassen else "nulmeting"
