"""Drifttest: draagt de GWSW-ontologie de kenmerken die een check declareert?

De tweede helft van issue #64. `test_declaratie_volgt_de_code` bewaakt dat de declaratie
klopt met de code; deze test bewaakt dat ze klopt met de ontologie: leest een check een
kenmerk op een populatie die dat kenmerk volgens het GWSW niet kan dragen (een
dekselhoogte op een gemaal), dan is dat rood.

**De regel.** Een gedeclareerd kenmerk `K` is geldig als er minstens één gedeclareerde,
in deze projectconfiguratie niet-lege rol is waarvan *elke* wortelklasse `K` kan dragen.
Bereikbaarheid loopt over de drie indexblokken: omhoog langs `subklasse_van` (een
subklasse erft de aspecten van haar ouder), en langs `aspecten_van`/`onderdelen_van` naar
de onderdelen en oriëntaties (Rioolput -> Putdeksel -> Dekselorientatie ->
Putdekselniveau). De rol hoeft niet ál haar kenmerken op ál haar klassen te dragen -- een
check leest verschillende kenmerken op verschillende rollen -- maar élk kenmerk moet
érgens volledig gedekt zijn. Een rol die in een config leeg staat telt niet mee (die valt
onder de nul-bewaking, niet onder deze test; zie issue #64).

**Waarom "∃ rol draagt het volledig" en niet "∃ wortel draagt het".** Een deksel is
bereikbaar vanaf `Bergbezinkbassin`, dus "∃ wortel" zou een dekselkenmerk op
`netwerkknopen` (dat óók een BBB bevat) goedkeuren en de bug missen. "Elke wortel van de
rol" eist dat de hele populatie het kenmerk kan dragen, en dat is precies wat een gemaal
in `netwerkknopen` breekt.

**Grens van de garantie -- de test is een ondergrens, geen uitputtende lijst.** De
declaratie is een platte verzameling rollen en een platte verzameling kenmerken; ze legt
niet vast wélk kenmerk op wélke rol gelezen wordt. Declareert een check naast een brede
rol die het kenmerk niet volledig draagt óók een smalle rol die dat wél doet -- ook als
die smalle rol alleen als overslagverzameling op `.uri` gelezen wordt -- dan dekt de smalle
rol het kenmerk af en valt de vlag weg. Het ene geval dat dit in deze codebase blootlegde
was `(HGT-016, HoogtePut)`: HGT-016 las de putbodem op `netwerkknopen` maar declareerde
daarnaast `valconstructies` (met `HoogtePut`), die het afdekte. Dat is met de reparatie
weg -- HGT-016 toetst de bodem nu op `rioolputten` -- dus op dit moment triggert geen enkele
check de blinde vlek. Ze blijft theoretisch bestaan; een sluitende oplossing vraagt een
sweep die kenmerken per rol bijhoudt, en dat is bewust uitgesteld (de meerkost weegt niet
op tegen deze inmiddels lege blinde vlek).

De overgebleven afwijkingen staan met reden in `UITZONDERINGEN`; de domeinkeuzes daarin
gaan als tabel naar de auteur (sluitcomment van issue #64). Een afwijking die niet meer
optreedt maakt de test óók rood, zodat de lijst niet stil veroudert.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import nlriochecker.checks  # noqa: F401  (vult de registry)
from checkdeclaratie_analyse import _veld_naar_rol
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks.base import REGISTRY

WORTEL = Path(__file__).resolve().parents[1]
INDEXBESTAND = WORTEL / "data" / "gwsw-vocabulaire-index.json"
CONFIGS = {
    "checks.toml": None,
    "dewoldenhoogeveen.toml": WORTEL / "configs" / "dewoldenhoogeveen.toml",
}

# Kenmerken die vanaf geen enkele klasse bereikbaar zijn en dat met reden blijven.
GLOBALE_UITZONDERINGEN: dict[str, str] = {
    "Maaiveldhoogte": (
        "Hangt via `hasConnection` aan de `Maaiveldorientatie` (Putorientatie hasConnection "
        "Maaiveldorientatie, Maaiveldhoogte isAspectOf Maaiveldorientatie). Het indexblok "
        "volgt bewust alleen `hasAspect`/`hasPart`, niet de structuurrelatie `hasConnection`, "
        "dus Maaiveldhoogte is vanaf geen klasse bereikbaar. De hoogtechecks lezen hem als "
        "terugval op het dekselniveau; dat is geregeld en geen ontologiefout."
    ),
}

# (check-ID, kenmerk) -> reden. Twee soorten:
#   [domeinkeuze] gaat als vraag naar de auteur (tabel in de sluitcomment van issue #64):
#       de check leest een dekselkenmerk op `netwerkknopen` of op de put aan het
#       streng-uiteinde, en die populatie bevat gemalen en uitlaten zonder deksel. Of dat
#       een fout is of een aanvaarde terugval op de maaiveldhoogte is een domeinvraag.
#   [structuur] is geen fout: het kenmerk wordt gelezen op een object dat structureel bij
#       de gedeclareerde rol hoort (de put aan het streng-uiteinde), of als terugval/
#       alternatief dat op de betreffende klasse simpelweg niet voorkomt.
UITZONDERINGEN: dict[tuple[str, str], str] = {
    ("BTR-006", "Putdekselniveau"): (
        "[domeinkeuze] Leest het putdekselniveau op `netwerkknopen` (incl. gemalen/uitlaten "
        "zonder deksel) om de afronding van de reeks te meten; terugval op maaiveld."
    ),
    ("HGT-001", "Putdekselniveau"): (
        "[domeinkeuze] AHN-vergelijking op `netwerkknopen`; leest het dekselniveau met "
        "terugval op de maaiveldhoogte. Restrictie tot `rioolputten` zou de "
        "maaiveld-vs-AHN-toets op gemalen/uitlaten laten vervallen -- keuze voor de auteur."
    ),
    ("HGT-002", "Putdekselniveau"): ("[domeinkeuze] Als HGT-001, zware drempel."),
    ("HGT-011", "Putdekselniveau"): (
        "[domeinkeuze] Leest het bovenkantniveau (deksel/maaiveld) op `netwerkknopen`."
    ),
    ("HGT-018", "Putdekselniveau"): (
        "[domeinkeuze] Leest het bovenkantniveau (deksel/maaiveld) op de put aan het "
        "streng-uiteinde; de gedeclareerde rol is de vrijvervalstreng."
    ),
    ("ATTR-006", "BreedteBouwwerk"): (
        "[structuur] `_grootste_putmaat` leest naast de putmaten ook de bouwwerkmaten als "
        "terugval; op een `Put` staan die nooit, dus de terugval is dood maar niet fout."
    ),
    ("ATTR-006", "LengteBouwwerk"): (
        "[structuur] Als BreedteBouwwerk: terugval in `_grootste_putmaat`."
    ),
    ("ATTR-010", "MateriaalPut"): (
        "[structuur] Gelezen op de put aan het streng-uiteinde (`putten_van`, structureel "
        "bereikt); de gedeclareerde rol is de vrijvervalstreng."
    ),
    ("ATTR-010", "MateriaalBouwwerk"): (
        "[structuur] Als MateriaalPut: terugval `MateriaalPut or MateriaalBouwwerk` op de put "
        "aan het streng-uiteinde."
    ),
    ("RVZ-007", "Inhoud"): (
        "[structuur] Eén van zes alternatieve bergingskenmerken; niet elke bassinklasse "
        "draagt elk kenmerk. De check meldt pas als álle zes ontbreken."
    ),
    ("RVZ-007", "NuttigeBerging"): ("[structuur] Als Inhoud: alternatief bergingskenmerk."),
}


def _index() -> dict:
    return json.loads(INDEXBESTAND.read_text(encoding="utf-8"))


_INDEX = _index()
_SUB = _INDEX["subklasse_van"]
_ASP = _INDEX["aspecten_van"]
_PART = _INDEX["onderdelen_van"]


def _omhoog(klasse: str) -> set[str]:
    """De klasse plus al haar superklassen (transitieve `subklasse_van`)."""
    gezien: set[str] = set()
    stapel = [klasse]
    while stapel:
        huidig = stapel.pop()
        if huidig in gezien:
            continue
        gezien.add(huidig)
        stapel.extend(_SUB.get(huidig, []))
    return gezien


@cache
def _bereikbaar(klasse: str) -> frozenset[str]:
    """De kenmerken en klassen die vanaf deze klasse te bereiken zijn.

    Omhoog langs `subklasse_van` om aspecten te erven, en langs `aspecten_van`/
    `onderdelen_van` naar onderdelen en oriëntaties, tot een vast punt.
    """
    eigenaren: set[str] = set()
    resultaat: set[str] = set()
    grens = [klasse]
    while grens:
        huidig = grens.pop()
        if huidig in eigenaren:
            continue
        eigenaren.add(huidig)
        for voorouder in _omhoog(huidig):
            for lid in _ASP.get(voorouder, []) + _PART.get(voorouder, []):
                if lid not in resultaat:
                    resultaat.add(lid)
                    grens.append(lid)
    return frozenset(resultaat)


_ROL_NAAR_VELD = {rol: veld for veld, rol in _veld_naar_rol().items()}
_ROL_NAAR_VELD["rioolputten"] = "rioolput"


def _wortels(rol: str, klassen) -> list[str]:
    """De wortelklassen van een rol in deze `[klassen]`-configuratie."""
    veld = _ROL_NAAR_VELD.get(rol)
    if veld is None:
        return []
    if veld == "netwerkknopen":
        return klassen.netwerkknopen
    return list(getattr(klassen, veld, []))


def _concrete_kenmerken(check) -> list[str]:
    """De gedeclareerde kenmerken zonder de `config:`- en `*`-verwijzingen."""
    return [k for k in check.kenmerken if not k.startswith("config:") and k != "*"]


def _schendingen() -> dict[tuple[str, str], list[str]]:
    """Per (check, kenmerk) de configs waarin geen enkele rol het kenmerk volledig draagt."""
    gevonden: dict[tuple[str, str], list[str]] = {}
    for naam, pad in CONFIGS.items():
        klassen = load_check_config(pad).klassen
        for check_id in sorted(REGISTRY):
            check = REGISTRY[check_id]
            nietleeg = {rol: wortels for rol in check.rollen if (wortels := _wortels(rol, klassen))}
            if not nietleeg:
                # Een check zonder (niet-lege) rol valt hier buiten: RVZ-011 haalt zijn
                # putten via de overstortdrempel-index (`drempels_per_put`, engine-navigatie)
                # en niet via een rol, dus `rollen = ()`. Zijn dekselkenmerk staat feitelijk
                # op overstortputten (een Rioolput, mét deksel), dus dat is correct, maar het
                # wordt hier niet tegen de ontologie gehouden. Een check die zijn hele
                # populatie via engine-navigatie haalt, ontsnapt zo aan deze bewaking; nu is
                # dat alleen RVZ-011, met reden.
                continue
            for kenmerk in _concrete_kenmerken(check):
                if kenmerk in GLOBALE_UITZONDERINGEN:
                    continue
                gedekt = any(
                    all(kenmerk in _bereikbaar(wortel) for wortel in wortels)
                    for wortels in nietleeg.values()
                )
                if not gedekt:
                    gevonden.setdefault((check_id, kenmerk), []).append(naam)
    return gevonden


SCHENDINGEN = _schendingen()


def test_declaratie_past_bij_de_ontologie() -> None:
    """Elke schending staat met reden in `UITZONDERINGEN`; geen enkele nieuwe."""
    onverklaard = {
        sleutel: configs
        for sleutel, configs in SCHENDINGEN.items()
        if sleutel not in UITZONDERINGEN
    }
    assert not onverklaard, (
        "Kenmerken die de ontologie niet draagt en die niet in UITZONDERINGEN staan:\n"
        + "\n".join(
            f"  {cid}: {k} ({', '.join(cfgs)})" for (cid, k), cfgs in sorted(onverklaard.items())
        )
    )


def test_geen_verouderde_uitzondering() -> None:
    """Elke (check, kenmerk) in `UITZONDERINGEN` schendt ook echt; anders moet hij weg."""
    verouderd = [sleutel for sleutel in UITZONDERINGEN if sleutel not in SCHENDINGEN]
    assert not verouderd, f"UITZONDERINGEN die niet meer schenden (verwijderen): {verouderd}"


def test_globale_uitzondering_wordt_gebruikt() -> None:
    """Elk globaal uitgezonderd kenmerk wordt ook echt ergens gedeclareerd."""
    gedeclareerd = {k for check in REGISTRY.values() for k in _concrete_kenmerken(check)}
    ongebruikt = [k for k in GLOBALE_UITZONDERINGEN if k not in gedeclareerd]
    assert not ongebruikt, f"GLOBALE_UITZONDERINGEN die niemand declareert: {ongebruikt}"
