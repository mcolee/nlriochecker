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
tienduizenden keren in het bestand -- op De Wolden zou een stijlblok per rij de
GeoPackage tientallen megabytes groter maken zonder dat er iets bij komt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape

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
    # Waarom dit object grijs is: 'mechanisch riool' of 'contextschil'. Grijs zonder
    # reden leest als "in orde", en dat is het niet.
    reden: str = ""


def bepaal_status(meldingen: Sequence[Melding], *, geanalyseerd: bool) -> str:
    """De status van een object: rood, oranje, groen of grijs.

    `geanalyseerd` is onwaar voor een object dat buiten de beoordeling viel -- de
    contextschil van een studiegebied, of mechanisch riool, dat volgens het
    checkregister buiten scope valt. Dat wint van alles: een object dat niet
    beoordeeld is, is niet half beoordeeld.

    Systemische meldingen tellen niet mee, net als in `ergste_ernst`, `n_fout` en
    `n_waarschuwing`. Op De Wolden draagt de nulmeting 68.882 systemische meldingen
    op 105.963; zouden die meetellen, dan is vrijwel elke put rood en zegt de kaart
    niets meer. Gevolg: een object waarvan *alle* meldingen systemisch zijn krijgt
    groen. Dat betekent hier "geen gebrek dat dit object van zijn buren
    onderscheidt", niet "in orde" -- de kolom `n_systemisch` en de popup zeggen het
    er allebei bij.
    """
    if not geanalyseerd:
        return STATUS_GRIJS
    eigen = [melding for melding in meldingen if not melding.systemisch]
    if any(melding.ernst == "F" for melding in eigen):
        return STATUS_ROOD
    return STATUS_ORANJE if eigen else STATUS_GROEN


def popup_html(kop: Objectkop, meldingen: Sequence[Melding]) -> str:
    """Bouwt de popup-inhoud van een object als HTML-fragment.

    De meldingen staan op prioriteit en dan op check-ID, zodat de cap van vijf de
    fouten niet wegsnijdt ten gunste van waarschuwingen. Alles wat uit de brondata
    komt wordt geescaped: een label met een `<` mag de popup niet breken.
    """
    gesorteerd = sorted(meldingen, key=lambda m: (m.prioriteit, m.check_id, m.melding_id))
    getoond = gesorteerd[:MAX_MELDINGEN_IN_POPUP]
    rest = len(gesorteerd) - len(getoond)

    regels = [f'<div class="gwsw-popup s-{escape(kop.status)}">', _kopregel(kop)]
    if kop.feiten:
        regels.append(
            '<div class="gwsw-feiten">' + " · ".join(escape(feit) for feit in kop.feiten) + "</div>"
        )
    if kop.reden:
        regels.append(f'<div class="gwsw-reden">Niet beoordeeld: {escape(kop.reden)}.</div>')

    if getoond:
        regels.append('<ul class="gwsw-meldingen">')
        regels += [_meldingregel(melding) for melding in getoond]
        regels.append("</ul>")
        if rest:
            regels.append(f'<div class="gwsw-rest">… en nog {rest} andere</div>')
    else:
        regels.append('<div class="gwsw-leeg">Geen meldingen op dit object.</div>')

    regels.append("</div>")
    return "".join(regels)


def _kopregel(kop: Objectkop) -> str:
    """Label, GWSW-objecttype en de status in woorden."""
    naam = escape(kop.label) or "(zonder label)"
    woord = STATUS_WOORD.get(kop.status, kop.status)
    return (
        f'<div class="gwsw-kop"><span class="gwsw-label">{naam}</span>'
        f'<span class="gwsw-type">{escape(kop.objecttype)}</span>'
        f'<span class="gwsw-status">{escape(woord)}</span></div>'
    )


def _meldingregel(melding: Melding) -> str:
    """Een melding als lijstitem: ernst, check, boodschap, herkomst en waarden."""
    symbool = ERNST_SYMBOOL.get(melding.ernst, melding.ernst)
    delen = [
        f'<li class="e-{escape(melding.ernst)}">',
        f'<span class="gwsw-ernst">{symbool}</span>',
        f'<span class="gwsw-check">{escape(melding.check_id)}</span>',
        f'<span class="gwsw-boodschap">{escape(melding.boodschap)}</span>',
    ]
    if melding.waarde:
        delen.append(f'<span class="gwsw-waarde">waarde {escape(melding.waarde)}</span>')
    if melding.drempel:
        delen.append(f'<span class="gwsw-drempel">drempel {escape(melding.drempel)}</span>')
    if melding.systemisch:
        delen.append('<span class="gwsw-systemisch">systemisch</span>')
    delen.append(f'<span class="gwsw-herkomst">{_herkomst(melding)}</span>')
    delen.append("</li>")
    return "".join(delen)


def _herkomst(melding: Melding) -> str:
    """Waar deze melding vandaan komt: de nulmeting met haar klassen, of een eigen check."""
    if melding.bron != BRON_NULMETING:
        return "eigen check"
    klassen = ", ".join(melding.cfk)
    return f"nulmeting · {escape(klassen)}" if klassen else "nulmeting"
