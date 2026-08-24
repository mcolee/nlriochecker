"""Wat er in het gebied ligt: de aantallen per objecttype en stelseltype.

Het bevindingenrapport opent met deze tabel. De lezer wil eerst weten waar het over
gaat -- hoeveel putten, hoeveel meter riool, van welk stelsel -- en pas daarna of het
in orde is.

De telling gaat over de **kern**: de objecten binnen het studiegebied. De contextschil
zit wel in de dataset van de run, want de netwerkchecks hebben hem nodig, maar er wordt
niet over gerapporteerd; hij staat als voetnoot onder de tabel. Zonder studiegebied is
alles kern.

`stelseltypen` staat hier omdat zowel deze tabel als de GeoPackage hem nodig heeft. Hij
stond in `gpkg.py`; twee kopieen zouden op een dag verschillende stelsels aan dezelfde
put toekennen.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckRun
from nlriochecker.checks.verbanden import verbonden_knopen
from nlriochecker.dataset import GwswDataset
from nlriochecker.taal import getal

KOLOMMEN = ["Objecttype", "Stelsel", "Aantal", "Lengte (m)"]

# De kolommen van de rollentelling en de afvoereindpuntregel; de tests lezen ze.
KLASSENTELLING_KOLOMMEN = ["Rol", "Klassen", "Aantal"]
EINDPUNT_KOLOMMEN = ["Klasse", "Aantal"]

# Wat er in de kolom Stelsel staat als een object er geen heeft. Een leeg veld leest
# als een ontbrekende waarde in de tabel; dit zegt wat het is.
GEEN_STELSEL = "—"

# En wat er in de kolom Lengte staat bij een object dat er geen heeft: een put. Een
# eigen constante, want hij betekent iets anders dan een ontbrekend stelseltype.
GEEN_LENGTE = "—"


def stelseltypen(run: CheckRun) -> dict[str, str]:
    """Het stelseltype per streng, en per put dat van de aansluitende strengen.

    Het GWSW legt het stelseltype op de leiding vast; een put ontleent het aan wat
    erop uitkomt. Komen daar meerdere soorten samen, dan staan ze er allemaal --
    dat is voor NET-006 juist het interessante geval.
    """
    config = run.config
    dataset = run.dataset
    per_object: dict[str, str] = {}
    per_put: dict[str, set[str]] = defaultdict(set)

    for uri, conduit in dataset.conduits.items():
        soort = config.klassen.stelseltype(conduit.types, dataset.closure)
        if soort is None:
            continue
        per_object[uri] = soort
        for knoop in verbonden_knopen(run.context, conduit):
            if knoop is not None:
                per_put[knoop].add(soort)

    for knoop, soorten in per_put.items():
        per_object[knoop] = ", ".join(sorted(soorten))
    return per_object


def omvangtabel(run: CheckRun) -> pd.DataFrame:
    """Een rij per objecttype en stelseltype, met aantallen en meters.

    De meters staan alleen bij verbindingen, en het is de **getekende** lengte: dat
    is wat er op de kaart ligt. Wijkt hij af van het kenmerk `LengteLeiding`, dan is
    dat een bevinding van ATTR-009 en die staat verderop in het rapport.

    Lange vorm en geen kruistabel: het aantal stelseltypen ligt niet vast -- een put
    waar twee stelsels samenkomen draagt ze allebei -- en een kruistabel zou daar
    kolommen bij krijgen tot hij niet meer op een scherm past.

    Alleen objecten met een bruikbare geometrie tellen mee, ook zonder studiegebied.
    Mét een gebied gebeurde dat al vanzelf -- `objecten_in_gebied` kan een object
    zonder plek niet binnen een vlak leggen -- en zonder gebied telde de tabel ze wel,
    zodat dezelfde export twee verschillende aantallen opleverde naargelang er een
    gebied was opgegeven. `omvang_toelichting` telt wat er zo buiten valt.
    """
    binnen = run.objecten_binnen()
    stelsels = stelseltypen(run)
    aantallen: defaultdict[tuple[str, str], int] = defaultdict(int)
    meters: defaultdict[tuple[str, str], float] = defaultdict(float)

    for uri, node in run.dataset.nodes.items():
        if not _telt_mee(uri, binnen, node.point):
            continue
        aantallen[(run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))] += 1
    for uri, conduit in run.dataset.conduits.items():
        if not _telt_mee(uri, binnen, conduit.line):
            continue
        sleutel = (run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))
        aantallen[sleutel] += 1
        if conduit.line is not None:
            meters[sleutel] += conduit.line.length

    rijen = [
        {
            "Objecttype": objecttype or "(zonder type)",
            "Stelsel": stelsel or GEEN_STELSEL,
            "Aantal": aantal,
            "Lengte (m)": round(meters[(objecttype, stelsel)])
            if meters.get((objecttype, stelsel))
            else GEEN_LENGTE,
        }
        for (objecttype, stelsel), aantal in sorted(aantallen.items())
    ]
    return pd.DataFrame(rijen, columns=KOLOMMEN)


def _telt_mee(uri: str, binnen: frozenset[str] | None, geometrie: object) -> bool:
    """Of dit object in de tabel hoort: binnen het gebied en met een plek op de kaart."""
    if binnen is not None and uri not in binnen:
        return False
    return geometrie is not None and not geometrie.is_empty  # type: ignore[attr-defined]


def zonder_geometrie(run: CheckRun) -> int:
    """Het aantal objecten dat geen plek op de kaart heeft en dus niet in de tabel staat.

    Compartimenten en hulpstukken zonder eigen punt, bijvoorbeeld. Ze bestaan wel en de
    checks zien ze; ze zijn alleen niet te tekenen en niet aan een gebied toe te wijzen.
    Zwijgen zou de tabel als volledig laten lezen.
    """
    if run.objecten_binnen() is not None:
        return 0
    zonder = sum(1 for node in run.dataset.nodes.values() if _leeg(node.point))
    return zonder + sum(1 for conduit in run.dataset.conduits.values() if _leeg(conduit.line))


def _leeg(geometrie: object) -> bool:
    """Of een geometrie ontbreekt of leeg is."""
    return geometrie is None or geometrie.is_empty  # type: ignore[attr-defined]


@dataclass(frozen=True)
class _Rol:
    """Een klassenlijst waar een check op leunt, en hoe hij geteld en bewaakt wordt.

    `via_onderdeel` kiest de teller: de meeste rollen selecteren hun objecten zoals
    de checks dat doen, via `of_class` op de knopen en strengen; de drempel telt via
    `subjects_of_class`, want een `Overstortdrempel` is een onderdeel zonder eigen
    geometrie dat NET-007 zo leest. Wie via `of_class` zou tellen, zou hem missen en
    een valse nul melden.

    `per_klasse` kiest het niveau van de nul-bewaking. Bij het afvoereindpunt draagt
    elke klasse een eigen betekenis -- `Gemaal` en `Pompunit` zijn het noodverband,
    `Overnamepunt` het echte overdrachtspunt (BO-33) -- dus daar telt elke lege klasse
    als een signaal. De andere rollen bevatten alternatieve schrijfwijzen van dezelfde
    rol (een export gebruikt `Lozingsput` OF `Lozingspunt`, niet allebei); daar zou een
    signaal per klasse elke ongebruikte schrijfwijze als gebrek melden. Zij waarschuwen
    daarom pas als de hele rol leeg is.
    """

    label: str
    klassen: tuple[str, ...]
    via_onderdeel: bool
    per_klasse: bool = False


def _rollen(config: CheckConfig) -> list[_Rol]:
    """De klassenlijsten uit `checks.toml` waar de zwaarste checks van afhangen.

    Geen eigen configlijst: precies de bestaande rollen, zodat een klasse die iemand
    later aan een lijst toevoegt vanzelf in de telling en de nul-bewaking verschijnt.
    """
    klassen = config.klassen
    return [
        _Rol("afvoereindpunt", tuple(klassen.afvoer_eindpunt), False, per_klasse=True),
        _Rol("lozingseindpunt", tuple(klassen.lozings_eindpunt), False),
        _Rol("bergbezinkvoorziening", tuple(klassen.bergbezinkvoorziening), False),
        _Rol("overstortdrempel", tuple(klassen.drempel), True),
        _Rol("infiltratieleiding", tuple(klassen.infiltratie), False),
        _Rol("mechanische leiding", tuple(klassen.mechanisch), False),
    ]


def _aantal_klasse(dataset: GwswDataset, klasse: str, via_onderdeel: bool) -> int:
    """Hoeveel objecten van deze klasse de bijbehorende check ziet."""
    if via_onderdeel:
        return len({str(subject) for subject in dataset.subjects_of_class(klasse)})
    return len(dataset.of_class(klasse))


def _aantal_rol(dataset: GwswDataset, rol: _Rol) -> int:
    """Hoeveel objecten deze rol samen telt, ontdubbeld over haar klassen."""
    if rol.via_onderdeel:
        uris = {
            str(subject) for klasse in rol.klassen for subject in dataset.subjects_of_class(klasse)
        }
    else:
        uris = {uri for klasse in rol.klassen for uri in dataset.of_class(klasse)}
    return len(uris)


def klassentelling(run: CheckRun) -> pd.DataFrame:
    """Een rij per rol waar een check op leunt, met haar totaal.

    De telling gaat over de volledige geanalyseerde export (`run.dataset`), niet over
    de kern van een studiegebied: of een klasse voorkomt is een eigenschap van de
    aanlevering, net als de datakarakteristiek, en verandert niet met de afbakening
    van de rapportage.
    """
    config = run.config
    dataset = run.dataset
    rijen = [
        {
            "Rol": rol.label,
            "Klassen": ", ".join(rol.klassen),
            "Aantal": _aantal_rol(dataset, rol),
        }
        for rol in _rollen(config)
    ]
    return pd.DataFrame(rijen, columns=KLASSENTELLING_KOLOMMEN)


def eindpunttelling(run: CheckRun) -> pd.DataFrame:
    """Een rij per afvoereindpuntklasse, met hoeveel instanties de check ervan ziet.

    Het is de betrouwbaarheidsregel voor NET-001: zolang `Overnamepunt` op nul staat,
    leunt de bereikbaarheid op het noodverband `Gemaal`/`Pompunit` (BO-33). Zodra hij
    een getal boven nul toont, kan dat noodverband weg. Zie issue #22.
    """
    config = run.config
    dataset = run.dataset
    rijen = [
        {"Klasse": klasse, "Aantal": _aantal_klasse(dataset, klasse, False)}
        for klasse in config.klassen.afvoer_eindpunt
    ]
    return pd.DataFrame(rijen, columns=EINDPUNT_KOLOMMEN)


@dataclass(frozen=True)
class NulSignaal:
    """Een klasse of rol die op nul staat terwijl een check erop leunt.

    `label` is de aanduiding in het rapport en op de melding (een klassenaam bij het
    afvoereindpunt, een rolnaam bij de andere rollen); `boodschap` is de tekst van de
    systemische waarschuwing.
    """

    label: str
    boodschap: str


def klassen_op_nul(run: CheckRun) -> list[NulSignaal]:
    """De klassen en rollen die op nul staan terwijl een check erop leunt.

    Het afvoereindpunt per klasse, de andere rollen als geheel (zie `_Rol.per_klasse`);
    nul is nul en vraagt geen drempel. Zonder klassenhierarchie herkent `of_class` geen
    klassen -- dan zou elke telling nul zijn en elke waarschuwing vals -- dus dan valt er
    niets te bewaken; het rapport draagt daarvoor al zijn eigen voorbehoud (issue #33).
    """
    dataset = run.dataset
    if not dataset.klassenhierarchie_bekend:
        return []
    signalen: list[NulSignaal] = []
    for rol in _rollen(run.config):
        if rol.per_klasse:
            signalen += [
                NulSignaal(
                    klasse,
                    f"Geen enkele {klasse} in de export, terwijl de afvoereindpuntrol "
                    "(NET-001) erop leunt. Wat op deze klasse toetst, heeft niets te beoordelen.",
                )
                for klasse in rol.klassen
                if _aantal_klasse(dataset, klasse, rol.via_onderdeel) == 0
            ]
        elif _aantal_rol(dataset, rol) == 0:
            signalen.append(
                NulSignaal(
                    rol.label,
                    f"Geen enkel object in de rol {rol.label} ({', '.join(rol.klassen)}) in de "
                    "export, terwijl een check erop leunt. Wat op deze rol toetst, heeft niets "
                    "te beoordelen.",
                )
            )
    return signalen


@dataclass(frozen=True)
class HerstelSignaal:
    """Het datasetsignaal over de herstelde fantoomkoppelingen (issue #60)."""

    koppelingen: int
    hulpstukken: int
    boodschap: str


def koppelingsherstel(run: CheckRun) -> HerstelSignaal | None:
    """Het signaal over de fantoomkoppeling, of None als de lader niets hoefde te herstellen.

    Herstel dat je niet meldt is stille interpretatie: de export koppelt leidingeinden
    aan een orientatie-URI die niet bestaat, en de lader raadt de knoop op naamstam.
    Dat het rapport dat zegt, houdt de aanlevering aanwijsbaar.
    """
    herstel = run.dataset.koppelingsherstel
    if not herstel.koppelingen:
        return None
    return HerstelSignaal(
        herstel.koppelingen,
        herstel.hulpstukken,
        f"De export koppelt {getal(herstel.koppelingen, 'leidingeind', 'leidingeinden')} aan "
        "een orientatie-URI die niet bestaat (`<hulpstuk>_put`, waar de Hulpstukorientatie van "
        f"{getal(herstel.hulpstukken, 'hulpstuk', 'hulpstukken')} anders heet). De lader heeft "
        "die koppelingen op naamstam hersteld zodat de netwerkchecks ze zien; de aanlevering "
        "zelf is daar niet op verbeterd.",
    )
