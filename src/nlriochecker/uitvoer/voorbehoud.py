"""De runbrede voorbehouden: wat er over deze hele run gezegd moet worden.

Een voorbehoud raakt niet een melding maar de run zelf: de meting liep over een
deelverzameling conformiteitsklassen, of de lader kende de klassenhierarchie niet en
heeft daardoor nul objecten getoetst. Zulke uitspraken horen boven het rapport, niet
erin -- wie ze mist leest de stilte als "alles gecontroleerd".

Deze module is de plek waar ze samenkomen. Er kan er meer dan een tegelijk gelden --
een `--cfk`-deelset zonder klassenkennis draagt er twee -- en `schrijf_markdown` heeft
maar een markeringsslot. Zonder samenstelplek zou een schrijver er een moeten kiezen,
en dan verdwijnt de andere stilzwijgend. `markering()` voegt ze daarom tot een kop
samen; wie een uitvoervorm schrijft roept die ene functie aan en hoeft de bronnen niet
te kennen.

Markdown, GeoPackage en JSON dragen de uitkomst. De CSV bewust niet: een voorbehoud
hoort bij de run en niet bij de melding, dus het wordt geen kolom op elke rij (BO-7).
"""

from __future__ import annotations

from nlriochecker.checks import CheckRun

GEEN_KLASSENHIERARCHIE = (
    "**Geen klassenhierarchie:** er is geen ontologie geladen en de export draagt zelf "
    "geen enkele subklasserelatie. De GWSW-wortels dekken hun subklassen dus niet, en "
    "de export typeert niets op wortelniveau: `putten()` en `leidingen()` leveren nul "
    "objecten en knopen en strengen zijn hier aan hun geometrie herkend. Lees de kolom "
    "*Bekeken* in de samenvatting per check om te zien hoeveel elke check werkelijk "
    "gezien heeft; wat er dan nog gemeld wordt komt uit een onvolledige selectie en is "
    "geen oordeel over de dataset. Ook wat dit rapport niet meldt, zegt niets over haar "
    "kwaliteit."
)


def voorbehouden(run: CheckRun) -> list[str]:
    """De runbrede voorbehouden van deze run, in volgorde van zwaarte.

    De klassenhierarchie staat voorop: ontbreekt zij, dan is er niets getoetst en doet
    de vraag tegen welke conformiteitsklassen dat gebeurde er nauwelijks meer toe.
    """
    gevonden = []
    if not run.dataset.klassenhierarchie_bekend:
        gevonden.append(GEEN_KLASSENHIERARCHIE)
    bereik = run.meetbereik.markering()
    if bereik:
        gevonden.append(bereik)
    return gevonden


def markering(run: CheckRun) -> str | None:
    """De voorbehouden als een kop, of None als er niets voor te behouden valt.

    Twee voorbehouden worden twee alinea's en geen opsomming: de tekst gaat zo
    ongewijzigd door `schrijf_markdown`, en in de GeoPackage en de JSON is het een
    veld dat een mens leest.
    """
    regels = voorbehouden(run)
    return "\n\n".join(regels) if regels else None
