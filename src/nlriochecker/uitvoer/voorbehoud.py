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
from nlriochecker.meting import Meetbereik
from nlriochecker.shaclrapport import LOKALE_EISEN_GEEN, MELDINGEN_ONBEPERKT

# De tekst spreekt de lezer van het rapport aan, niet de ontwikkelaar: geen
# functienamen, wel GWSW-klassen die hij in QGIS terugvindt. Twee dingen staan er
# bewust niet in, allebei omdat deze module ze niet weet. Waar de klassenkennis vandaan
# had moeten komen -- het signaal is dat de graaf de subklassen van Knooppunt of
# Verbinding niet draagt, en dat kan ook met een meegegeven ontologie zo zijn. En dat de
# export niets op wortelniveau typeert: dat volgt niet uit het ontbreken van subklassen,
# want een export die haar objecten rechtstreeks als `gwsw:Put` schrijft heeft er geen
# nodig. Wat wel volgt is hoe ver een wortelselectie dan reikt, en dat is wat er staat.
#
# De tweede zin is voorwaardelijk geformuleerd, en dat is geen slag om de arm: het
# voorbehoud geldt zodra de subklassen van `gwsw:Knooppunt` of `gwsw:Verbinding`
# ontbreken, en een dataset die de andere wortels wel kent -- de tussentoestand waarin
# een deel van de TTL-fixtures in deze repo staat -- vult `gwsw:Put` gewoon.
GEEN_KLASSENHIERARCHIE = (
    "**Geen klassenhierarchie:** deze dataset draagt geen subklassen van "
    "`gwsw:Knooppunt`, van `gwsw:Verbinding`, of van geen van beide. Knopen en strengen "
    "zijn hier daarom aan hun geometrie herkend in plaats van aan hun GWSW-type: een "
    "knooppunt zonder punt valt dan buiten de selectie, en een object met een punt dat "
    "geen knooppunt is valt erbinnen. Draagt de dataset ook verder geen "
    "subklasserelaties -- een OroX-export draagt er geen enkele -- dan dekken de "
    "GWSW-wortels bovendien hun subklassen niet: een selectie op `gwsw:Put` of "
    "`gwsw:Leiding` vindt dan alleen objecten die letterlijk zo getypeerd zijn, en een "
    "export schrijft daar doorgaans `Inspectieput` en `GemengdRiool`. De eigen checks "
    "hebben over een onvolledige selectie gedraaid: de kolom *Bekeken* in de "
    "samenvatting per check zegt per check hoeveel objecten dat waren. Wat er gemeld "
    "wordt is daarmee geen oordeel over de dataset, en wat er niet gemeld wordt zegt "
    "niets over haar kwaliteit."
)


# De meting is met een maximum aan het aantal meldingen gedraaid: boven dat maximum
# kapt de GWSW-server de meldingtabel af, en dan telt deze toets minder overtredingen uit
# de nulmeting dan er in de dataset staan. `{waarde}` is de gemeten limiet, of bij
# ongelijke CFK-rapporten de per-CFK-opsomming uit `Nulmeting.max_meldingen`.
MELDINGENLIMIET = (
    "**Meldingenlimiet:** de SHACL-meting is met een maximum aan het aantal meldingen "
    "gedraaid ({waarde}); zonder limiet staat hier `onbeperkt`. Boven dat maximum kapt "
    "de GWSW-server de meldingtabel af, en dan telt deze toets minder overtredingen uit "
    "de nulmeting dan er in de dataset zitten. Wat hier over de nulmeting gerapporteerd "
    "wordt is daarmee een ondergrens; laat de meting zonder limiet opnieuw draaien om "
    "zeker te weten dat u alles ziet."
)

# De meting is tegen een bestand met lokale kwaliteitseisen gedraaid: die voegen vormen
# toe die niet uit het GWSW komen, terwijl dit rapport de uitkomst als GWSW-nulmeting
# presenteert. `{waarde}` is de eisenverwijzing zoals de bron hem noemt.
LOKALE_EISEN = (
    "**Lokale kwaliteitseisen:** de SHACL-meting is tegen een bestand met lokale "
    "kwaliteitseisen gedraaid ({waarde}); zonder zo'n bestand staat hier `geen`. Die "
    "eisen voegen vormen toe die niet uit het GWSW komen, terwijl dit rapport de "
    "uitkomst als GWSW-nulmeting presenteert. Een overtreding kan daardoor op een lokale "
    "eis slaan in plaats van op een GWSW-regel; leg het eisenbestand naast dit rapport "
    "om ze te duiden."
)


def voorbehouden(run: CheckRun) -> list[str]:
    """De runbrede voorbehouden van deze run, in volgorde van zwaarte.

    De klassenhierarchie staat voorop: ontbreekt zij, dan draagt geen enkele uitkomst
    van deze run een oordeel, en doet de vraag tegen welke conformiteitsklassen er
    gemeten is er nauwelijks meer toe. Daaronder de nulmeting-kopblokvelden: een limiet
    op het aantal meldingen (de tabel kan afgekapt zijn) en lokale kwaliteitseisen (er
    zijn niet-GWSW-vormen bijgemeten). Ze verschijnen alleen als ze van hun neutrale
    waarde afwijken.
    """
    gevonden = []
    if not run.dataset.klassenhierarchie_bekend:
        gevonden.append(GEEN_KLASSENHIERARCHIE)
    bereik = run.meetbereik.markering()
    if bereik:
        gevonden.append(bereik)
    if run.max_meldingen and run.max_meldingen != MELDINGEN_ONBEPERKT:
        gevonden.append(MELDINGENLIMIET.format(waarde=run.max_meldingen))
    if run.lokale_eisen and run.lokale_eisen != LOKALE_EISEN_GEEN:
        gevonden.append(LOKALE_EISEN.format(waarde=run.lokale_eisen))
    return gevonden


def markering(run: CheckRun) -> str | None:
    """De voorbehouden als een kop, of None als er niets voor te behouden valt.

    Twee voorbehouden worden twee alinea's en geen opsomming: de tekst gaat zo
    ongewijzigd door `schrijf_markdown`, en in de GeoPackage en de JSON is het een
    veld dat een mens leest.
    """
    regels = voorbehouden(run)
    return "\n\n".join(regels) if regels else None


def markering_van(meetbereik: Meetbereik) -> str | None:
    """De kop voor een schrijver die geen `CheckRun` heeft, maar wel een meetbereik.

    `analyseer`, `dekking` en `vergelijk` schrijven over een nulmeting en niet over een
    toetsrun: `CoverageResult` draagt een datasetnáám en `MetingAnalysis` en
    `MetingComparison` dragen helemaal geen datasetobject. `klassenhierarchie_bekend` is
    daar dus onbereikbaar, en die drie kunnen per constructie maar één voorbehoud dragen
    -- dat van het meetbereik. Deze ingang zegt dat hardop, in plaats van de aanroep
    verspreid over `reporting.py` te laten staan waar niets hem aan de samenstelplek
    bindt.

    Hij geeft exact `meetbereik.markering()` terug en vervalt zodra `CoverageResult` of
    `MetingAnalysis` wél een datasetobject gaat dragen: dan gaan die drie schrijvers over
    op `markering(run)` en is er weer één ingang.
    """
    return meetbereik.markering()
