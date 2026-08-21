"""De runbrede voorbehouden: wat er over deze hele run gezegd moet worden.

Een voorbehoud raakt niet een melding maar de run zelf: de meting liep over een
deelverzameling conformiteitsklassen, of de lader kende de klassenhierarchie niet en
heeft de checks daardoor over een onvolledige selectie laten draaien. Zulke uitspraken
horen boven het rapport, niet erin -- wie ze mist leest de uitkomst als een oordeel.

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

# De tekst spreekt de lezer van het rapport aan, niet de ontwikkelaar: geen
# functienamen, wel GWSW-klassen die hij in QGIS terugvindt. En hij zegt niets over
# waar de klassenkennis vandaan had moeten komen -- het signaal is dat de graaf geen
# subklasserelaties draagt, en dat kan ook met een meegegeven ontologie zo zijn.
GEEN_KLASSENHIERARCHIE = (
    "**Geen klassenhierarchie:** deze dataset draagt geen enkele subklasserelatie, dus "
    "de GWSW-wortels dekken hun subklassen niet en de export typeert niets op "
    "wortelniveau. Een selectie op `gwsw:Put` of `gwsw:Leiding` blijft daardoor leeg, "
    "en knopen en strengen zijn hier aan hun geometrie herkend in plaats van aan hun "
    "GWSW-type. De eigen checks hebben over een onvolledige selectie gedraaid: de kolom "
    "*Bekeken* in de samenvatting per check zegt per check hoeveel objecten dat waren. "
    "Wat er gemeld wordt is daarmee geen oordeel over de dataset, en wat er niet gemeld "
    "wordt zegt niets over haar kwaliteit."
)


def voorbehouden(run: CheckRun) -> list[str]:
    """De runbrede voorbehouden van deze run, in volgorde van zwaarte.

    De klassenhierarchie staat voorop: ontbreekt zij, dan draagt geen enkele uitkomst
    van deze run een oordeel, en doet de vraag tegen welke conformiteitsklassen er
    gemeten is er nauwelijks meer toe.
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
