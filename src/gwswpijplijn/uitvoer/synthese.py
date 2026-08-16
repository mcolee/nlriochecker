"""De rode draad: wat de losse bevindingen samen zeggen.

Een lijst van 113 bevindingen leest als 113 gebreken. Vaak zijn het er veel minder:
een systematisch verkeerd geregistreerde afvoerrichting, een enkele verdachte BOB
waar vier checks over struikelen, een deelstelsel dat als geheel iets mist. Deze
sectie benoemt die verbanden voordat de lezer aan de tabellen begint.

Slaat geen enkele detectie aan, dan komt de kop er niet: een lege sectie suggereert
dat er niets te zeggen valt, terwijl er niets *gemeten* is.
"""

from __future__ import annotations

from collections import defaultdict

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckRun
from gwswpijplijn.taal import getal, vorm
from gwswpijplijn.uitvoer.melding import Melding

# De checks die samen op een verkeerd geregistreerde afvoerrichting wijzen.
RICHTINGSCHECKS = ("NET-001", "NET-003", "NET-004", "HGT-005", "HGT-006")

# Meer dan dit aantal objecten bij naam noemen maakt de synthese onleesbaar; de
# rest staat toch in de bevindingentabellen en in de CSV.
MAX_VERDACHTE_OBJECTEN = 5


def rode_draad(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Stelt de synthesesectie samen; leeg als er niets te melden valt."""
    if not meldingen:
        return []

    config = run.config if run.config is not None else load_check_config()
    alinea = [
        *_richting(run, meldingen, config),
        *_multi_melding(meldingen, config),
        *_gedeelde_deelstelsels(meldingen),
    ]
    if not alinea:
        return []

    regels = ["**Rode draad**", ""]
    for tekst in alinea:
        regels += [tekst, ""]
    return regels


def _richting(run: CheckRun, meldingen: list[Melding], config: CheckConfig) -> list[str]:
    """Benoemt omgekeerde registratie als gezamenlijke oorzaak, met het percentage."""
    stijgend, meetbaar = _bodemverloop(run, config)
    if not meetbaar:
        return []
    aandeel = stijgend / meetbaar
    if aandeel <= config.rapport.richtingsdrempel:
        return []

    geraakt = sorted({m.check_id for m in meldingen if m.check_id in RICHTINGSCHECKS})
    if not geraakt:
        return []

    aantal = sum(1 for m in meldingen if m.check_id in geraakt)
    return [
        f"Bij {stijgend} van de {meetbaar} strengen met bekende BOB's stijgt de bodem in de "
        f"administratieve afvoerrichting ({100 * aandeel:.0f}%). Dat wijst op systematisch "
        f"omgekeerd geregistreerde van-naar-richtingen, en die verklaren vermoedelijk het "
        f"merendeel van de {getal(aantal, 'bevinding', 'bevindingen')} van "
        f"{', '.join(geraakt)} in een keer. Herstel van de registratierichting gaat voor "
        "het herstellen van de losse bevindingen."
    ]


def _bodemverloop(run: CheckRun, config: CheckConfig) -> tuple[int, int]:
    """Telt de vrijvervalstrengen waarvan de bodem stijgt van begin naar eind."""
    dataset = run.dataset
    gezocht = {
        uri
        for wortel in config.klassen.vrijvervalleiding
        for uri in dataset.of_class(wortel)
        if uri in dataset.conduits
    }
    stijgend = meetbaar = 0
    for uri in gezocht:
        conduit = dataset.conduits[uri]
        if conduit.bob_start is None or conduit.bob_end is None:
            continue
        meetbaar += 1
        if conduit.bob_start < conduit.bob_end:
            stijgend += 1
    return stijgend, meetbaar


def _multi_melding(meldingen: list[Melding], config: CheckConfig) -> list[str]:
    """Benoemt objecten waar meerdere checks op struikelen als een vermoedelijke fout."""
    drempel = config.rapport.multi_melding_checks
    per_object: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for melding in meldingen:
        per_object[melding.object_uri].add(melding.check_id)
        labels[melding.object_uri] = melding.object_label or melding.object_uri

    verdacht = sorted(
        ((uri, checks) for uri, checks in per_object.items() if len(checks) >= drempel),
        key=lambda paar: (-len(paar[1]), labels[paar[0]]),
    )
    if not verdacht:
        return []

    beschrijving = "; ".join(
        f"{labels[uri]} ({', '.join(sorted(checks))})"
        for uri, checks in verdacht[:MAX_VERDACHTE_OBJECTEN]
    )
    rest = len(verdacht) - MAX_VERDACHTE_OBJECTEN
    if rest > 0:
        beschrijving += f", en {rest} andere (zie de bevindingentabellen)"

    return [
        f"{getal(len(verdacht), 'object draagt', 'objecten dragen')} meldingen uit "
        f"{drempel} of meer verschillende checks: {beschrijving}. Zulke stapelingen komen "
        "meestal uit een enkele verdachte waarde voort; controleer die eerst, voordat de "
        f"losse {vorm(len(verdacht), 'melding', 'meldingen')} "
        f"{vorm(len(verdacht), 'wordt', 'worden')} nagelopen."
    ]


def _gedeelde_deelstelsels(meldingen: list[Melding]) -> list[str]:
    """Benoemt deelstelsels waar zowel een NET-check als RVZ-006 over meldt."""
    per_check: dict[str, set[str]] = defaultdict(set)
    for melding in meldingen:
        if melding.cluster_id:
            per_check[melding.check_id].add(melding.cluster_id)

    netclusters = per_check.get("NET-001", set()) | per_check.get("NET-002", set())
    gedeeld = sorted(netclusters & per_check.get("RVZ-006", set()))
    if not gedeeld:
        return []

    return [
        f"{getal(len(gedeeld), 'deelstelsel komt', 'deelstelsels komen')} zowel bij de "
        f"bereikbaarheidscheck als bij RVZ-006 terug ({', '.join(gedeeld)}): het is daar "
        "topologisch een eiland zonder externe overstort of bergbezinkvoorziening. Dat is "
        "een gebrek van het deelstelsel als geheel, niet van de losse strengen erin."
    ]
