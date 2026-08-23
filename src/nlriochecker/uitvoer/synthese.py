"""De rode draad: wat de losse bevindingen samen zeggen.

Een lijst van 113 bevindingen leest als 113 gebreken. Vaak zijn het er veel minder:
een systematisch verkeerd geregistreerde afvoerrichting, een enkele verdachte BOB
waar vier checks over struikelen, een deelstelsel dat als geheel iets mist. Deze
sectie benoemt die verbanden voordat de lezer aan de tabellen begint.

Slaat geen enkele detectie aan, dan komt de kop er niet: een lege sectie suggereert
dat er niets te zeggen valt, terwijl er niets *gemeten* is.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, Severity
from nlriochecker.checks.selectie import vrijvervalrioolleidingen
from nlriochecker.taal import getal, vorm
from nlriochecker.uitvoer.melding import BRON_REGISTER, Melding
from nlriochecker.uitvoer.tabel import table

ERNST_FOUT = Severity.ERROR.value
ERNST_WAARSCHUWING = Severity.WARNING.value


@dataclass(frozen=True)
class GebiedsSamenvatting:
    """Wat de totaalsynthese van een enkel gebied nodig heeft.

    De meldingen komen kant-en-klaar uit de meldingenstroom; deze module
    interpreteert geen enkele `Finding` opnieuw.
    """

    naam: str
    oppervlak_ha: float
    weggelaten: int
    kern_objecten: int
    meldingen: list[Melding]


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
    # Het percentage is over de volledige dataset geteld, het aantal bevindingen niet.
    # Zonder die zin staat er een datasetbreed getal boven een afgebakende lijst.
    afbakening = (
        f" Het percentage is over de volledige dataset geteld, niet over "
        f"{run.study_area.name}; de bevindingen eronder wel."
        if run.study_area is not None
        else ""
    )
    return [
        f"Bij {stijgend} van de {meetbaar} strengen met bekende BOB's stijgt de bodem in de "
        f"administratieve afvoerrichting ({100 * aandeel:.0f}%). Dat wijst op systematisch "
        f"omgekeerd geregistreerde van-naar-richtingen, en die verklaren vermoedelijk het "
        f"merendeel van de {getal(aantal, 'bevinding', 'bevindingen')} van "
        f"{', '.join(geraakt)} in een keer. Herstel van de registratierichting gaat voor "
        f"het herstellen van de losse bevindingen.{afbakening}"
    ]


def _bodemverloop(run: CheckRun, config: CheckConfig) -> tuple[int, int]:
    """Telt de vrijvervalstrengen waarvan de bodem stijgt van begin naar eind.

    De selectie komt uit `checks/selectie.py`; de context wordt hier gemaakt over de
    dataset van de run, want de uitvoerlaag heeft er geen.
    """
    stijgend = meetbaar = 0
    for conduit in vrijvervalrioolleidingen(CheckContext(dataset=run.dataset, config=config)):
        if conduit.bob_start is None or conduit.bob_end is None:
            continue
        meetbaar += 1
        if conduit.bob_start < conduit.bob_end:
            stijgend += 1
    return stijgend, meetbaar


def _multi_melding(meldingen: list[Melding], config: CheckConfig) -> list[str]:
    """Benoemt objecten waar meerdere checks op struikelen als een vermoedelijke fout.

    Alleen meldingen uit het checkregister tellen mee. De redenering -- "meerdere
    onafhankelijke checks over hetzelfde object wijzen op een enkele verdachte
    waarde" -- gaat niet op voor de nulmeting: haar vormen zijn niet onafhankelijk
    maar per kenmerk gesplitst, dus `Put_HoogtePut_card`,
    `Rioolput_Maaiveldschematisering_card` en `Rioolput_BergendOppervlak_card` slaan
    per constructie samen aan. Op De Wolden en Hoogeveen dragen 23.296 van de 32.389 focusnodes
    drie of meer verschillende vormen; die alle als "verdacht object" aanwijzen maakt
    van deze sectie ruis en geeft advies dat nergens toe leidt.

    Meldingen zonder object doen ook niet mee: die zouden anders samen in een
    naamloze emmer belanden en als een verdacht object gepresenteerd worden, met het
    label van de laatste die erin viel.
    """
    drempel = config.rapport.multi_melding_checks
    per_object: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for melding in meldingen:
        if melding.bron != BRON_REGISTER or not melding.object_uri:
            continue
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


def totaalsynthese(
    gebieden: Sequence[GebiedsSamenvatting],
    beschikbaar: Sequence[str],
    overgeslagen: Sequence[str],
    dataset: str = "",
) -> list[str]:
    """Stelt de romp van de totaalsynthese over meerdere studiegebieden samen.

    `dataset` staat in de romp en niet meer in de titel: die noemt sinds issue #16 het
    gebied waar het rapport over gaat, hier "Totaal (N gebieden)".

    Per gebied de omvang en de meldingen, en daarboven het totaal over alle
    gebieden. Objecten op een gebiedsgrens tellen in elk rakend gebied mee (zie
    `StudyArea.bevat`); daarom is de som der delen hoger dan het aantal unieke
    meldingen, en zegt deze sectie precies hoeveel dat verschil is. Zonder die zin
    leest een lezer die de kolommen optelt een verschil dat er niet is.
    """
    kop = [f"Dataset: `{dataset}`.", ""] if dataset else []
    per_gebied = pd.DataFrame(
        [
            {
                "Gebied": deel.naam,
                "Oppervlak (ha)": round(deel.oppervlak_ha, 1),
                "Objecten in de kern": deel.kern_objecten,
                "Meldingen": len(deel.meldingen),
                "Fouten": sum(1 for melding in deel.meldingen if melding.ernst == ERNST_FOUT),
                "Waarschuwingen": sum(
                    1 for melding in deel.meldingen if melding.ernst == ERNST_WAARSCHUWING
                ),
                "Buiten het gebied": deel.weggelaten,
            }
            for deel in gebieden
        ]
    )

    alle_ids = [melding.melding_id for deel in gebieden for melding in deel.meldingen]
    uniek = set(alle_ids)
    meervoudig = sum(1 for aantal in Counter(alle_ids).values() if aantal > 1)

    regels = [
        *kop,
        f"Deze synthese beslaat {getal(len(gebieden), 'gebied', 'gebieden')} "
        f"({', '.join(deel.naam for deel in gebieden)}).",
        "",
    ]
    if len(beschikbaar) > len(gebieden):
        regels += [
            f"> **Selectie:** het studiegebiedbestand telt {len(beschikbaar)} gebieden; "
            f"met `--gebied` zijn er {len(gebieden)} getoetst. Over de overige "
            f"{len(beschikbaar) - len(gebieden)} zegt dit rapport niets.",
            "",
        ]
    if overgeslagen:
        regels += [f"> **Overgeslagen in het gebiedsbestand:** {'; '.join(overgeslagen)}.", ""]

    leeg = [deel.naam for deel in gebieden if deel.kern_objecten == 0]
    if leeg:
        regels += [
            f"> **{getal(len(leeg), 'gebied bevat', 'gebieden bevatten')} geen enkel "
            f"GWSW-object** ({', '.join(leeg)}). Daar is niets getoetst; nul bevindingen "
            "betekent er dus niet dat het in orde is.",
            "",
        ]

    regels += [
        f"{len(uniek)} unieke meldingen over alle gebieden samen, waarvan "
        f"{getal(meervoudig, 'melding voorkomt', 'meldingen voorkomen')} in meer dan een "
        f"gebied. Objecten op een gebiedsgrens tellen in elk rakend gebied mee: elk gebied "
        f"ziet zijn eigen volledige werkelijkheid. Daarom is de som van de kolom Meldingen "
        f"({len(alle_ids)}) hoger dan het aantal unieke meldingen; er is niet ontdubbeld "
        f"tussen gebieden.",
        "",
        *table(per_gebied, "Per gebied"),
        "",
        *table(_per_gebied_en_check(gebieden), "Meldingen per gebied en check"),
        "",
        "De bestanden per gebied staan in de submappen; `bevindingen.csv` en "
        "`bevindingen.json` hiernaast bevatten de unieke meldingen over alle gebieden, "
        "waarbij een melding uit meerdere gebieden het gebied van zijn eerste voorkomen "
        "draagt.",
    ]
    return regels


def _per_gebied_en_check(gebieden: Sequence[GebiedsSamenvatting]) -> pd.DataFrame:
    """Telt per gebied per check de meldingen en de fouten."""
    rijen = [
        {
            "Gebied": deel.naam,
            "Check": check_id,
            "Ernst": meldingen_van_check[0].ernst,
            "Meldingen": len(meldingen_van_check),
        }
        for deel in gebieden
        for check_id, meldingen_van_check in sorted(_per_check(deel.meldingen).items())
    ]
    return pd.DataFrame(rijen, columns=["Gebied", "Check", "Ernst", "Meldingen"])


def _per_check(meldingen: list[Melding]) -> dict[str, list[Melding]]:
    """Groepeert de meldingen van een gebied per check."""
    gegroepeerd: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        gegroepeerd[melding.check_id].append(melding)
    return gegroepeerd
