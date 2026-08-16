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

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import REGISTRY as CHECK_REGISTRY
from gwswpijplijn.checks import CheckOutcome, CheckRun, Finding
from gwswpijplijn.uitvoer.identiteit import melding_id

logger = logging.getLogger(__name__)

BRON_REGISTER = "register"

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
    object_label: str
    object2_uri: str
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


def bouw_meldingen(run: CheckRun, run_datum: date) -> list[Melding]:
    """Zet alle bevindingen van een run om in meldingen.

    De enige plek waar bevindingen naar uitvoer vertaald worden.
    """
    from gwswpijplijn.uitvoer.locatie import foutlocatie

    config = run.config if run.config is not None else load_check_config()
    scope = SCOPE_BINNEN if run.study_area is not None else SCOPE_GEEN_GEBIED
    gebied = run.study_area.gebied if run.study_area is not None else ""
    kritiek = set(config.klassen.kritiek)

    meldingen: list[Melding] = []
    gebruikte_ids: set[str] = set()
    for outcome in run.outcomes:
        systemisch = _is_systemisch(outcome, config)
        sleutels = _id_sleutels(outcome.check_id)
        for finding in outcome.findings:
            kenmerk = _uniek_id(finding, sleutels, gebruikte_ids)
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
                    object_label=finding.object_label,
                    object2_uri=_tekst(finding.details.get(SLEUTEL_OBJECT2_URI)),
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
    return meldingen


def categorie_van(check_id: str) -> str:
    """De categorie van een check-ID: TOP-011 wordt TOP."""
    return check_id.split("-", 1)[0]


def _id_sleutels(check_id: str) -> tuple[str, ...]:
    """De detailsleutels waarmee deze check haar bevindingen onderscheidt."""
    check = CHECK_REGISTRY.get(check_id)
    return check.id_sleutels if check is not None else ()


def _uniek_id(finding: Finding, sleutels: tuple[str, ...], gebruikt: set[str]) -> str:
    """De melding-ID, met een volgnummer als vangnet bij een botsing.

    Botst er iets, dan ontbreekt er een identificerende sleutel bij die check. Dat
    hoort op te vallen: zwijgend twee meldingen tot een laten versmelten kost een
    gebrek.
    """
    onderscheid = {
        sleutel: _tekst(finding.details.get(sleutel))
        for sleutel in sleutels
        if sleutel in finding.details
    }
    kenmerk = melding_id(
        finding.check_id,
        finding.object_uri,
        _tekst(finding.details.get(SLEUTEL_OBJECT2_URI)),
        onderscheid,
    )
    if kenmerk not in gebruikt:
        return kenmerk

    volgnummer = 2
    while f"{kenmerk}-{volgnummer}" in gebruikt:
        volgnummer += 1
    logger.warning(
        "%s levert twee meldingen met dezelfde ID op object %s; vul id_sleutels aan. "
        "De tweede krijgt volgnummer %d, wat tussen runs kan verschuiven.",
        finding.check_id,
        finding.object_label or finding.object_uri,
        volgnummer,
    )
    return f"{kenmerk}-{volgnummer}"


def _is_systemisch(outcome: CheckOutcome, config: CheckConfig) -> bool:
    """Geeft aan of deze check op vrijwel de hele populatie aanslaat.

    Zo'n check zegt iets over de export als geheel; hem even zwaar op de kaart
    zetten als een los gebrek maakt het kaartbeeld onbruikbaar.
    """
    if not outcome.examined or not outcome.findings:
        return False
    return len(outcome.findings) / outcome.examined > config.rapport.systemisch_drempel


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
