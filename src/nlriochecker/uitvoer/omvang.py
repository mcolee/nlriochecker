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
from gwsw_orox_helpers.dataset import GwswDataset

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckRun
from nlriochecker.checks.base import REGISTRY
from nlriochecker.checks.selectie import klassen_van_rol, putten
from nlriochecker.checks.verbanden import verbonden_knopen
from nlriochecker.taal import getal, vorm

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


def putten_in_beeld(run: CheckRun) -> frozenset[str]:
    """De putten waar dit rapport over gaat: de rol `putten`, afgebakend tot de kern.

    De noemer van het aanlegjaar-aandeel in de rapportkop (issue #91). Het is dezelfde
    selectie waarop ATTR-018 draaide -- `selectie.putten` op de context van de run, dus
    uit haar cache -- want een eigen doorloop over de dataset zou op een dag een ander
    getal geven dan de check die de teller levert.

    Met een studiegebied blijft alleen de kern over. De meldingen in dit rapport zijn
    daartoe afgebakend, en een noemer over de volledige export zou het aandeel in een
    kleine buurt naar nul drukken -- anders dan de klassentelling hierboven, die niet
    tegen een teller wordt afgezet.
    """
    binnen = run.objecten_binnen()
    uris = {node.uri for node in putten(run.context)}
    return frozenset(uris if binnen is None else uris & binnen)


@dataclass(frozen=True)
class _Rol:
    """Een klassenlijst waar een check op leunt, en hoe hij geteld en bewaakt wordt.

    `via_onderdeel` kiest de teller: de meeste rollen selecteren hun objecten zoals
    de checks dat doen, via `of_class` op de knopen en strengen; de drempel telt via
    `subjects_of_class`, want een `Overstortdrempel` is een onderdeel zonder eigen
    geometrie dat NET-007 zo leest. Wie via `of_class` zou tellen, zou hem missen en
    een valse nul melden.

    `per_klasse` kiest het niveau van de nul-bewaking. Bij het afvoereindpunt draagt
    elke klasse een eigen betekenis -- `Gemaal` is het noodverband,
    `Overnamepunt` het echte overdrachtspunt (BO-33) -- dus daar telt elke lege klasse
    als een signaal. De andere rollen bevatten alternatieve schrijfwijzen van dezelfde
    rol (een export gebruikt `Lozingsput` OF `Lozingspunt`, niet allebei); daar zou een
    signaal per klasse elke ongebruikte schrijfwijze als gebrek melden. Zij waarschuwen
    daarom pas als de hele rol leeg is.

    `checks` zijn de check-ID's die op deze rol leunen; de nul-melding noemt ze (het gat
    uit issue #22, nu generiek). Voor een gedeclareerde rol komen ze uit de registry,
    voor de twee speciale bewakingen is het de canonieke check (NET-001, NET-007).
    """

    label: str
    klassen: tuple[str, ...]
    via_onderdeel: bool
    checks: tuple[str, ...]
    per_klasse: bool = False


# Rollen die een check wél declareert maar die géén toetspopulatie zijn: hij leest ze als
# *indicator* om objecten juist buiten zijn oordeel te houden. Nul instanties betekent daar
# niet "deze check heeft niets te beoordelen" maar "deze uitzondering gaat nooit af", en de
# check werkt verder volledig. `pompunits` is het enige geval: EXT-009 gebruikt de pompput
# om een straat met drukriolering niet te beoordelen, en een gemeente zonder drukriolering
# krijgt anders een systemische waarschuwing die het omgekeerde beweert van wat er aan de
# hand is. Zij vallen alleen buiten de nul-bewaking; in de rollentelling van het rapport
# blijven ze gewoon staan, want daar is nul een feit en geen oordeel. Zie BO-80 en BO-52.
INDICATORROLLEN = frozenset({"pompunits"})


def _gedeclareerde_rollen() -> dict[str, tuple[str, ...]]:
    """Per gedeclareerde rol de check-ID's die haar in `check.rollen` noemen.

    De bron voor de rollentelling en de nul-bewaking (issue #71): precies de rollen waar
    een geregistreerde check op leunt, met de checks erbij zodat de nul-melding ze kan
    noemen. Gesorteerd voor een stabiele uitvoer.
    """
    per_rol: defaultdict[str, list[str]] = defaultdict(list)
    for check in REGISTRY.values():
        for rol in check.rollen:
            per_rol[rol].append(check.id)
    return {rol: tuple(sorted(ids)) for rol, ids in per_rol.items()}


def _rollen(config: CheckConfig) -> list[_Rol]:
    """De rollen waar de checks op leunen: hun declaraties plus twee vaste bewakingen.

    Sinds issue #71 leidt deze lijst de rollen af uit wat de geregistreerde checks in
    `check.rollen` declareren (via `selectie.klassen_van_rol` naar hun klassen), zodat de
    telling en de nul-bewaking niet meer op een handlijst leunen. Twee bewakingen drukken
    geen `selectie._ROLLEN`-rol uit en blijven daarom expliciet (BO-52):

    - het **afvoereindpunt** (`Overnamepunt`, `Gemaal`) wordt per klasse
      bewaakt, want elke klasse draagt een eigen betekenis -- noodverband versus echt
      overdrachtspunt (BO-33) -- en er is geen rol `afvoer_eindpunt`;
    - de **overstortdrempel** is een `Overstortdrempel`-onderdeel zonder eigen geometrie
      dat via `subjects_of_class` geteld wordt (NET-007), niet via `of_class`, en heeft
      evenmin een rol.

    Een gedeclareerde rol zonder geconfigureerde klassen (een project mag
    `functieloze_knoop` leeg laten) valt weg: zonder verwachte populatie is er niets op
    nul te melden.
    """
    klassen = config.klassen
    speciaal = [
        _Rol(
            "afvoereindpunt",
            tuple(klassen.afvoer_eindpunt),
            False,
            ("NET-001",),
            per_klasse=True,
        ),
        _Rol("overstortdrempel", tuple(klassen.drempel), True, ("NET-007",)),
    ]
    gedeclareerd = [
        _Rol(rol, tuple(rolklassen), False, checks)
        for rol, checks in sorted(_gedeclareerde_rollen().items())
        if (rolklassen := klassen_van_rol(rol, klassen))
    ]
    return speciaal + gedeclareerd


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
    leunt de bereikbaarheid op het noodverband `Gemaal` (BO-33). Zodra hij
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

    De rollen in `INDICATORROLLEN` blijven erbuiten: daar zegt nul niet dat een check niets
    te beoordelen heeft maar dat een uitzondering nooit afgaat.
    """
    dataset = run.dataset
    if not dataset.klassenhierarchie_bekend:
        return []
    signalen: list[NulSignaal] = []
    for rol in _rollen(run.config):
        if rol.label in INDICATORROLLEN:
            continue
        if rol.per_klasse:
            signalen += [
                NulSignaal(klasse, _per_klasse_boodschap(klasse, rol))
                for klasse in rol.klassen
                if _aantal_klasse(dataset, klasse, rol.via_onderdeel) == 0
            ]
        elif _aantal_rol(dataset, rol) == 0:
            signalen.append(NulSignaal(rol.label, _rol_boodschap(rol)))
    return signalen


def _rol_boodschap(rol: _Rol) -> str:
    """De nul-melding voor een hele lege rol, met de checks die erop leunen."""
    checks = ", ".join(rol.checks)
    return (
        f"Geen enkel object in de rol {rol.label} ({', '.join(rol.klassen)}) in de "
        f"export, terwijl {checks} erop {vorm(len(rol.checks), 'leunt', 'leunen')}. "
        "Wat op deze rol toetst, heeft niets te beoordelen."
    )


def _per_klasse_boodschap(klasse: str, rol: _Rol) -> str:
    """De nul-melding voor een lege afvoereindpuntklasse, met de check die erop leunt."""
    checks = ", ".join(rol.checks)
    return (
        f"Geen enkele {klasse} in de export, terwijl {checks} op de rol {rol.label} "
        f"{vorm(len(rol.checks), 'leunt', 'leunen')} (BO-33). Wat op deze klasse toetst, "
        "heeft niets te beoordelen."
    )


@dataclass(frozen=True)
class HerstelSignaal:
    """Het datasetsignaal over de herstelde fantoomkoppelingen (issue #60)."""

    koppelingen: int
    hulpstukken: int
    boodschap: str


def koppelingsherstel(run: CheckRun) -> HerstelSignaal | None:
    """Het signaal over de fantoomkoppeling, of None als de lader niets hoefde te herstellen.

    Herstel dat je niet meldt is stille interpretatie: de export koppelt leidingeinden
    aan een `<hulpstuk>_put`-URI die niet bestaat, en de lader raadt de knoop op
    naamstam. Dat het rapport dat zegt, houdt de aanlevering aanwijsbaar.
    """
    herstel = run.dataset.koppelingsherstel
    if not herstel.koppelingen:
        return None
    return HerstelSignaal(
        herstel.koppelingen,
        herstel.hulpstukken,
        f"De export koppelt {getal(herstel.koppelingen, 'leidingeind', 'leidingeinden')} aan "
        "een `<hulpstuk>_put`-URI die niet bestaat, waar de Hulpstukorientatie van "
        f"{getal(herstel.hulpstukken, 'hulpstuk', 'hulpstukken')} anders heet. De lader heeft "
        "die koppelingen op naamstam hersteld zodat de hulpstukchecks TOP-022 en TOP-023 ze "
        "zien; een hulpstuk is geen netwerkknoop, dus de netwerkchecks veranderen er niet "
        "door. De aanlevering zelf is daar niet op verbeterd.",
    )
