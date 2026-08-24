"""De meldingenstroom: een bevinding, verrijkt tot wat de uitvoer nodig heeft.

Markdown, CSV en GeoPackage lezen alle drie uit deze lijst. Dat is geen afspraak
maar een eigenschap van de code: er is geen pad waarlangs een schrijver zelf nog
een `Finding` interpreteert, dus kunnen de drie uitvoervormen niet uit elkaar
lopen.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from shapely.geometry import Point

from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckOutcome, CheckRun, Dimension, Finding, Severity
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.uitvoer.identiteit import kort, melding_id
from nlriochecker.uitvoer.locatie import foutlocatie, objectlocatie
from nlriochecker.uitvoer.omvang import klassen_op_nul

logger = logging.getLogger(__name__)

BRON_REGISTER = "register"
# De tweede bron naast het register: de GWSW SHACL-nulmeting. Zie `nulbevinding.py`.
BRON_NULMETING = "nulmeting"
# De derde bron: een signaal over de dataset zelf, geen gebrek aan een los object. Nu
# alleen de nul-bewaking van issue #22: een klasse waar een check op leunt maar die
# nul keer voorkomt. Systemisch, ernst W, zonder object -- telt dus niet mee in de
# GeoPackage-status (BO-29).
BRON_DATASET = "dataset"
# De check-ID van die nul-bewaking. Geen checkregister-ID: dit is geen check maar een
# datasetsignaal. `categorie_van` maakt er de categorie `SIG` van.
CHECK_NULKLASSE = "SIG-nulklasse"

# De dimensietag van elke nulmetingmelding. Een SHACL-nulmeting toetst of de dataset
# aan een conformiteitsklasse voldoet, en dat is voor elke vorm dezelfde vraag; een
# fijnere tag zou een tweede register van vorm naar dimensie vergen dat bij elke
# serverwijziging achterloopt.
DIMENSIE_NULMETING = Dimension.COMPLIANCE

SCOPE_BINNEN = "binnen_studiegebied"
SCOPE_GEEN_GEBIED = "geen_studiegebied"

# Gereserveerde detailsleutels: alles wat de uitvoer uit `Finding.details` haalt.
SLEUTEL_OBJECT2_URI = "object2_uri"
SLEUTEL_OBJECT2_LABEL = "object2_label"
SLEUTEL_WAARDE = "waarde"
SLEUTEL_DREMPEL = "drempel"
SLEUTEL_CLUSTER = "cluster_id"


@dataclass(frozen=True)
class Melding:
    """Een bevinding met alles erbij wat rapport, CSV en GeoPackage nodig hebben."""

    melding_id: str
    check_id: str
    categorie: str
    bron: str
    ernst: str
    dimensie: str
    object_uri: str
    object_id: str
    object_label: str
    object2_uri: str
    object2_id: str
    object2_label: str
    boodschap: str
    waarde: str
    drempel: str
    typering_betrouwbaar: bool
    cluster_id: str
    scope: str
    gebied: str
    prioriteit: int
    systemisch: bool
    foutlocatie: Point | None
    run_datum: str
    dataset: str
    # De conformiteitsklassen die deze overtreding noemen, gesorteerd. Leeg bij een
    # eigen check: die toetst niet tegen een CFK. Dezelfde overtreding staat vaak in
    # meerdere CFK-rapporten en levert een melding op; tellingen per CFK tellen hem
    # bij elke genoemde klasse mee.
    cfk: tuple[str, ...] = ()


def bouw_meldingen(run: CheckRun, run_datum: date) -> list[Melding]:
    """Zet alle bevindingen van een run om in meldingen.

    De enige plek waar bevindingen naar uitvoer vertaald worden.
    """
    config = run.config
    scope = SCOPE_BINNEN if run.study_area is not None else SCOPE_GEEN_GEBIED
    gebied = run.study_area.gebied if run.study_area is not None else ""
    kritiek = set(config.klassen.kritiek)

    meldingen: list[Melding] = []
    gebruikte_ids: set[str] = set()
    for outcome in run.outcomes:
        outcome_systemisch = _is_systemisch(outcome, config)
        sleutels = outcome.id_sleutels
        for finding in outcome.findings:
            # Een check kan een losse bevinding als systemisch merken (ATTR-014 meldt
            # per kenmerk, over de hele export); dat OR't met de populatieratio.
            systemisch = outcome_systemisch or finding.systemisch
            kenmerk = _uniek_id_van_finding(finding, sleutels, gebruikte_ids)
            gebruikte_ids.add(kenmerk)
            meldingen.append(
                Melding(
                    melding_id=kenmerk,
                    check_id=finding.check_id,
                    categorie=categorie_van(finding.check_id),
                    bron=BRON_REGISTER,
                    ernst=finding.severity.value,
                    dimensie=finding.dimension.value,
                    object_uri=finding.object_uri,
                    object_id=kort(finding.object_uri),
                    object_label=finding.object_label,
                    object2_uri=_tekst(finding.details.get(SLEUTEL_OBJECT2_URI)),
                    object2_id=kort(_tekst(finding.details.get(SLEUTEL_OBJECT2_URI))),
                    object2_label=_tekst(finding.details.get(SLEUTEL_OBJECT2_LABEL)),
                    boodschap=finding.message,
                    waarde=_tekst(finding.details.get(SLEUTEL_WAARDE)),
                    drempel=_tekst(finding.details.get(SLEUTEL_DREMPEL)),
                    typering_betrouwbaar=finding.typing_reliable,
                    cluster_id=_tekst(finding.details.get(SLEUTEL_CLUSTER)),
                    scope=scope,
                    gebied=gebied,
                    prioriteit=_prioriteit(run, finding, kritiek),
                    systemisch=systemisch,
                    foutlocatie=foutlocatie(finding, run.dataset),
                    run_datum=run_datum.isoformat(),
                    dataset=run.dataset.source.name,
                )
            )

    meldingen += _nulmeldingen(run, run_datum, scope, gebied, kritiek, gebruikte_ids)
    meldingen += _signaalmeldingen(run, run_datum, scope, gebruikte_ids)
    return meldingen


def _signaalmeldingen(
    run: CheckRun,
    run_datum: date,
    scope: str,
    gebruikte_ids: set[str],
) -> list[Melding]:
    """Een systemische waarschuwing per klasse die op nul staat terwijl een check ervan afhangt.

    Geen gebrek aan een object maar een signaal over de export: geen object-URI, geen
    plek op de kaart, en systemisch, zodat het de GeoPackage-status niet raakt (BO-29).
    Zonder gebied, net als een nulmetingbevinding die nergens op uitkwam: het is aan
    geen enkel studiegebied toe te wijzen. Zie issue #22.
    """
    meldingen = []
    for signaal in klassen_op_nul(run):
        kenmerk = _uniek_id(
            CHECK_NULKLASSE, "", "", {"klasse": signaal.label}, signaal.label, gebruikte_ids
        )
        gebruikte_ids.add(kenmerk)
        meldingen.append(
            Melding(
                melding_id=kenmerk,
                check_id=CHECK_NULKLASSE,
                categorie=categorie_van(CHECK_NULKLASSE),
                bron=BRON_DATASET,
                ernst=Severity.WARNING.value,
                dimensie=Dimension.COMPLETENESS.value,
                object_uri="",
                object_id="",
                object_label=signaal.label,
                object2_uri="",
                object2_id="",
                object2_label="",
                boodschap=signaal.boodschap,
                waarde="0",
                drempel="",
                typering_betrouwbaar=True,
                cluster_id="",
                scope=scope,
                gebied="",
                prioriteit=3,
                systemisch=True,
                foutlocatie=None,
                run_datum=run_datum.isoformat(),
                dataset=run.dataset.source.name,
            )
        )
    return meldingen


def _nulmeldingen(
    run: CheckRun,
    run_datum: date,
    scope: str,
    gebied: str,
    kritiek: set[str],
    gebruikte_ids: set[str],
) -> list[Melding]:
    """Zet de overtredingen uit de SHACL-nulmeting om in meldingen.

    Ze lopen door dezelfde functie als de checkbevindingen en dragen daarom dezelfde
    velden; alleen `bron`, `categorie` en `cfk` verraden waar ze vandaan komen.

    De onderscheidende sleutels zijn de focusnode en de boodschap. De object-URI
    volstaat niet: twee eindpunten van dezelfde streng herleiden naar diezelfde
    streng. De boodschap zit erin omdat hij ook de ontdubbelsleutel is; herformuleert
    de GWSW-server hem, dan verschuiven de melding-ID's van die vorm eenmalig.

    Een bevinding die nergens op uitkwam draagt geen gebied: hij is aan geen enkel
    studiegebied toe te wijzen. Hem het gebied van de run geven zou beweren dat hij
    daarbinnen ligt, en dat is niet gemeten.
    """
    meldingen = []
    for bevinding in run.nulbevindingen:
        kenmerk = _uniek_id(
            bevinding.check_id,
            bevinding.object_uri,
            "",
            {"focusnode": bevinding.focus_node, "boodschap": bevinding.boodschap},
            bevinding.focus_node,
            gebruikte_ids,
        )
        gebruikte_ids.add(kenmerk)
        meldingen.append(
            Melding(
                melding_id=kenmerk,
                check_id=bevinding.check_id,
                categorie=categorie_van(bevinding.check_id),
                bron=BRON_NULMETING,
                ernst=bevinding.ernst,
                dimensie=DIMENSIE_NULMETING.value,
                object_uri=bevinding.object_uri,
                object_id=kort(bevinding.object_uri),
                object_label=bevinding.object_label,
                object2_uri="",
                object2_id="",
                object2_label="",
                boodschap=bevinding.boodschap,
                waarde=bevinding.waarde,
                drempel="",
                typering_betrouwbaar=bevinding.typering_betrouwbaar,
                cluster_id="",
                scope=scope,
                gebied=gebied if bevinding.herleid else "",
                prioriteit=_nulprioriteit(run, bevinding, kritiek),
                systemisch=bevinding.systemisch,
                # Een bevinding die nergens op uitkwam heeft geen object en dus geen
                # plek op de kaart.
                foutlocatie=(
                    objectlocatie(run.dataset, bevinding.object_uri) if bevinding.herleid else None
                ),
                run_datum=run_datum.isoformat(),
                dataset=run.dataset.source.name,
                cfk=bevinding.cfk,
            )
        )
    return meldingen


def _nulprioriteit(run: CheckRun, bevinding: Nulbevinding, kritiek: set[str]) -> int:
    """Dezelfde regel als bij een eigen check: 1 kritiek, 2 fout, 3 waarschuwing."""
    if bevinding.ernst != Severity.ERROR.value:
        return 3
    if kritiek and any(run.dataset.is_a(bevinding.object_uri, wortel) for wortel in kritiek):
        return 1
    return 2


def categorie_van(check_id: str) -> str:
    """De categorie van een check-ID: TOP-011 wordt TOP."""
    return check_id.split("-", 1)[0]


def _uniek_id_van_finding(finding: Finding, sleutels: tuple[str, ...], gebruikt: set[str]) -> str:
    """De melding-ID van een checkbevinding, met haar eigen onderscheidende sleutels."""
    onderscheid = {
        sleutel: _tekst(finding.details.get(sleutel))
        for sleutel in sleutels
        if sleutel in finding.details
    }
    return _uniek_id(
        finding.check_id,
        finding.object_uri,
        _tekst(finding.details.get(SLEUTEL_OBJECT2_URI)),
        onderscheid,
        finding.object_label or finding.object_uri,
        gebruikt,
    )


def _uniek_id(
    check_id: str,
    object_uri: str,
    object2_uri: str,
    onderscheid: dict[str, str],
    aanduiding: str,
    gebruikt: set[str],
) -> str:
    """De melding-ID, met een volgnummer als vangnet bij een botsing.

    Botst er iets, dan ontbreekt er een onderscheidende sleutel: bij een eigen check
    de `id_sleutels`, bij de nulmeting de focusnode en de boodschap. Dat hoort op te
    vallen: zwijgend twee meldingen tot een laten versmelten kost een gebrek.
    """
    kenmerk = melding_id(check_id, object_uri, object2_uri, onderscheid)
    if kenmerk not in gebruikt:
        return kenmerk

    volgnummer = 2
    while f"{kenmerk}-{volgnummer}" in gebruikt:
        volgnummer += 1
    logger.warning(
        "%s levert twee meldingen met dezelfde ID op %s; de onderscheidende sleutels "
        "(%s) volstaan daar niet. De tweede krijgt volgnummer %d, wat tussen runs kan "
        "verschuiven.",
        check_id,
        aanduiding,
        ", ".join(sorted(onderscheid)) or "geen",
        volgnummer,
    )
    return f"{kenmerk}-{volgnummer}"


def _is_systemisch(outcome: CheckOutcome, config: CheckConfig) -> bool:
    """Geeft aan of deze check op vrijwel de hele populatie aanslaat.

    Zo'n check zegt iets over de export als geheel; hem even zwaar op de kaart
    zetten als een los gebrek maakt het kaartbeeld onbruikbaar.

    De teller is bewust het aantal bevindingen *voor* de afbakening tot een
    studiegebied (`weggelaten` telt de rest), want `examined` slaat op de volledige
    dataset. Zonder die correctie zou een tot een buurt afgebakende run de vlag
    nooit meer laten aanslaan en zou "systemisch" iets anders betekenen naargelang
    er een studiegebied is opgegeven.
    """
    gevonden = len(outcome.findings) + outcome.weggelaten
    if not outcome.examined or not gevonden:
        return False
    return gevonden / outcome.examined > config.rapport.systemisch_drempel


def _prioriteit(run: CheckRun, finding: Finding, kritiek: set[str]) -> int:
    """1 bij een fout op een kritiek object, 2 bij overige fouten, 3 bij waarschuwingen."""
    if finding.severity.value != "F":
        return 3
    if kritiek and any(run.dataset.is_a(finding.object_uri, wortel) for wortel in kritiek):
        return 1
    return 2


def _tekst(waarde: object) -> str:
    """Een detailwaarde als tekst; ontbreekt hij, dan leeg."""
    return "" if waarde is None else str(waarde)
