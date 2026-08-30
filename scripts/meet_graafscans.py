#!/usr/bin/env python
"""Meet wat het dedupliceren van de graafscans oplevert (issue #124).

Twee ingrepen worden hier gemeten, allebei gedragsneutraal: `_eindpunten` uit
`checks/verbanden.py` achter `context.cached`, en `_property_tellingen` uit
`checks/attributen.py` op twee indexsweeps in plaats van twee `graph.value`-aanroepen
per kenmerkinstantie. Het bewijs dat er niets verschuift zijn de ATTR-014-tellingen per
kenmerk en het aantal bevindingen per check; het bewijs dat de deduplicatie werkt is
`ncalls`.

Waarom dit script onder `scripts/` staat en niet in een scratchpad (BO-43): het
onderbouwt de getallen in issue #124 en in het `CHANGELOG`, en het is de enige manier om
ze na een codewijziging opnieuw te meten.

**Wat het script wel en niet doet.** Het meet één toestand: de code zoals die op dít
moment in de werkboom staat, zonder monkeypatch. Het vergelijkt niets en het wisselt geen
broncode om. Een voor/na-vergelijking maak je door hem twee keer te draaien met de
wijziging ertussenin, en de twee JSON-bestanden naast elkaar te leggen:

    uv run python scripts/meet_graafscans.py --uit uitvoer/meting_124_voor.json
    uv run python scripts/meet_graafscans.py --uit uitvoer/meting_124_na.json

Het veld `commit` in de uitslag zegt welke toestand gemeten is; het draagt `-vuil` zodra er
ongecommitte wijzigingen in `src/` staan. De vijf-runs-per-kant-tijdmeting van issue #124
komt dus **niet** uit dit script: die is gedraaid door een wikkel die `--alleen-tijd
--runs 5` twee keer aanroept en de drie gewijzigde bronbestanden ertussenin omwisselt
(`git checkout --` naar HEAD en weer terug). Dat omwisselen hoort niet in een meetscript
thuis -- het schrijft in de werkboom -- en staat daarom in het verslag van het issue.

Drie dingen die de meting anders waardeloos maken:

- **`ncalls` en de tijd worden apart gemeten.** cProfile telt per aanroep ongeveer een
  microseconde op, en beide posten zijn miljoenen zeer goedkope aanroepen; de geprofileerde
  run zegt dus niets over de wandkloktijd. `ncalls` is wél exact.
- **Elke run krijgt een verse `CheckContext`.** Met een gedeelde context zou de tweede run
  alle gecachte structuren van de eerste erven en bijna nul meten.
- **De dataset gaat door `markeer_vulwaarden`, net als in de echte pijplijn**
  (`toetsrun.py`); een losstaand script mist die markering en geeft afwijkende cijfers.

Deze run mist EXT (geen `--bronnen`) en de nulmeting (geen `--shacl`); dat is prima voor
tellingen en aanroeptellingen, niet voor een uitkomstvergelijking met een `toets`-run.
"""

from __future__ import annotations

import argparse
import cProfile
import gc
import json
import os
import pstats
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import (
    HAS_REFERENCE,
    HAS_VALUE,
    GwswDataset,
    markeer_vulwaarden,
)

from nlriochecker.checkconfig import FALLBACK_ENCODING, CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.checks.attributen import _property_tellingen

DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
PROJECTCONFIG = Path("configs/dewoldenhoogeveen.toml")

# De leeslaagbewerkingen waarvan de aanroeptelling iets zegt over de twee ingrepen.
# `of_class` is de scan die `_eindpunten` per wortelklasse deed, `value` de twee
# aanroepen per kenmerkinstantie van ATTR-014, en `subject_objects` de twee sweeps die
# ervoor in de plaats komen. `subjects` staat erbij als tegenproef: die telling hoort
# niet te bewegen.
GEVOLGD = ("of_class", "value", "subject_objects", "subjects", "types_of")


def _laad() -> tuple[GwswDataset, CheckConfig]:
    """De dataset door de echte pijplijn plus de projectconfig."""
    # `fallback_encoding` is niet optioneel: de BrutIS-export van De Wolden en Hoogeveen
    # draagt CP850-bytes in straatnamen en de lader weigert zonder terugvalcodering.
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    config = load_check_config(PROJECTCONFIG)
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    return dataset, config


def _context(dataset: GwswDataset, config: CheckConfig) -> CheckContext:
    """Een verse context: geen enkele afgeleide structuur uit een vorige run."""
    return CheckContext(dataset=dataset, config=config)


def _tellingen(dataset: GwswDataset, config: CheckConfig) -> dict[str, list[Any]]:
    """De ATTR-014-telling per kenmerk, als vergelijkbare JSON."""
    tellingen = _property_tellingen(_context(dataset, config))
    return {
        kenmerk: [telling.verwacht, telling.totaal, telling.fout, telling.vulwaarde_nul]
        for kenmerk, telling in sorted(tellingen.items())
    }


def _aanroepen(dataset: GwswDataset, config: CheckConfig) -> tuple[dict[str, int], float]:
    """De `ncalls` van de gevolgde leeslaagbewerkingen tijdens een volledige checkrun."""
    context = _context(dataset, config)
    profiel = cProfile.Profile()
    start = time.perf_counter()
    profiel.enable()
    run_checks(context)
    profiel.disable()
    duur = time.perf_counter() - start

    statistiek = pstats.Stats(profiel)
    gevonden: dict[str, int] = {}
    for (bestand, _regel, functie), waarden in statistiek.stats.items():  # type: ignore[attr-defined]
        if functie not in GEVOLGD:
            continue
        # `ncalls` is het derde element (primitieve aanroepen staan op index 0); het
        # totale aantal aanroepen is wat hier telt.
        naam = f"{Path(bestand).name}:{functie}"
        gevonden[naam] = gevonden.get(naam, 0) + waarden[1]
    return dict(sorted(gevonden.items())), duur


def _uitslag(dataset: GwswDataset, config: CheckConfig) -> dict[str, dict[str, int]]:
    """Per check het aantal bevindingen en de bekeken populatie, plus de tijd."""
    context = _context(dataset, config)
    run = run_checks(context)
    return {
        outcome.check_id: {"bevindingen": len(outcome.findings), "examined": outcome.examined}
        for outcome in run.outcomes
    }


def _tijd(dataset: GwswDataset, config: CheckConfig) -> float:
    """De wandkloktijd van een volledige checkrun, zonder profiler."""
    context = _context(dataset, config)
    start = time.perf_counter()
    run_checks(context)
    return time.perf_counter() - start


def _scankosten(dataset: GwswDataset, config: CheckConfig) -> dict[str, float]:
    """Wat één `of_class`-scan per wortelklasse van de eindpuntrollen kost.

    Stap 1 haalt een vast aantal van die scans weg; met deze prijs erbij is te zien of de
    verwachte winst in de ruis van de runtijd hoort te verdwijnen of niet. Vijf metingen
    per wortel, de kleinste telt -- die draagt de minste storing van buiten.
    """
    wortels = [
        wortel
        for rol in ("afvoer_eindpunt", "lozings_eindpunt")
        for wortel in getattr(config.klassen, rol)
    ]
    per_wortel: dict[str, float] = {}
    for wortel in wortels:
        metingen = []
        for _ in range(5):
            start = time.perf_counter()
            dataset.of_class(wortel)
            metingen.append(time.perf_counter() - start)
        per_wortel[wortel] = round(min(metingen), 4)
    return per_wortel


def _sweepkosten(dataset: GwswDataset) -> dict[str, float]:
    """Hoeveel subjecten de twee ATTR-014-sweeps dragen en wat ze aan geheugen kosten.

    Stap 2 ruilt 2 x 459.108 `value`-aanroepen in voor twee verzamelingen die over álle
    triples met `hasValue`/`hasReference` lopen, ook die van niet-kenmerkinstanties. Dat
    beslag is te meten en hoort in het verslag: een volledige toetsrun piekt vandaag onder
    de 2 GB zonder externe bronnen (BO-41/BO-42).

    **Eerst warmdraaien, anders meet je iets anders.** Een gecachte dataset draagt een
    `LuieGraaf` (`gwsw_orox_helpers/cache.py`): die leest `graaf.pickle` -- 91 MB op schijf,
    circa 780 MB in geheugen -- pas bij de eerste graafbewerking in. Zonder de telronde
    hieronder valt die eenmalige inleesbeurt in de RSS-delta en lijkt de sweep 792 MB te
    kosten in plaats van 20 MB. Een echte checkrun leest de graaf sowieso (elke
    `graph.subjects`-aanroep doet dat), dus die kosten hangen niet aan deze wijziging.
    """
    paren = sum(1 for _ in dataset.graph.subject_objects(HAS_VALUE))
    paren += sum(1 for _ in dataset.graph.subject_objects(HAS_REFERENCE))
    gc.collect()
    voor_rss = _rss_mb()
    met_waarde = {subject for subject, _ in dataset.graph.subject_objects(HAS_VALUE)}
    met_referentie = {subject for subject, _ in dataset.graph.subject_objects(HAS_REFERENCE)}
    gc.collect()
    na_rss = _rss_mb()
    return {
        "paren": paren,
        "met_waarde": len(met_waarde),
        "met_referentie": len(met_referentie),
        # Twee lezingen naast elkaar. `getsizeof` is de hashtabel van de twee
        # verzamelingen zelf; de termen erin zijn geinterneerd en gedeeld met de
        # graafindex (`GraafIndex.vul_uit`), dus die kosten niets extra's. De RSS-delta is
        # wat het proces er feitelijk bij vasthoudt en hoort in dezelfde orde uit te
        # komen. `tracemalloc` is hier bewust NIET gebruikt: op een graafindex met
        # miljoenen levende blokken meet die vooral zijn eigen instrumentatie -- de eerste
        # meting gaf 718 MB tegen 20 MB aan feitelijke verzamelingen.
        "getsizeof_mb": round(
            (sys.getsizeof(met_waarde) + sys.getsizeof(met_referentie)) / 2**20, 1
        ),
        "rss_delta_mb": round(na_rss - voor_rss, 1),
    }


def _rss_mb() -> float:
    """Het huidige residente geheugen van dit proces in MB.

    Uit `/proc/self/statm` en niet uit `resource.getrusage`: die geeft `ru_maxrss`, een
    hoogwatermerk dat na een piek nooit meer daalt en dus geen delta oplevert.
    """
    pagina = os.sysconf("SC_PAGE_SIZE")
    resident = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
    return resident * pagina / 2**20


def _commit() -> str:
    """De HEAD-commit waarop deze meting draaide, met `-vuil` bij ongecommitte `src/`.

    Zonder dat achtervoegsel dragen een voor- en een na-meting hetzelfde commit-nummer
    zolang de wijziging nog in de werkboom staat, en is achteraf niet te zien welk bestand
    welke kant meet. Alleen `src/` telt: een gewijzigd meetscript of `CHANGELOG` verandert
    de gemeten code niet.
    """
    gedraaid = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    commit = gedraaid.stdout.strip() or "onbekend"
    vuil = subprocess.run(
        ["git", "status", "--porcelain", "--", "src/"], capture_output=True, text=True, check=False
    )
    return f"{commit}-vuil" if vuil.stdout.strip() else commit


def main() -> None:
    """Meet en schrijft de uitslag als JSON weg."""
    argumenten = argparse.ArgumentParser(description=__doc__)
    argumenten.add_argument("--uit", type=Path, required=True, help="pad voor de JSON-uitslag")
    argumenten.add_argument("--runs", type=int, default=2, help="aantal tijdmetingen")
    argumenten.add_argument(
        "--alleen-tijd",
        action="store_true",
        help="sla de tellingen en de profielrun over; alleen de wandkloktijd",
    )
    keuze = argumenten.parse_args()

    dataset, config = _laad()

    uitslag: dict[str, Any] = {"commit": _commit(), "dataset": str(DATASET)}
    if not keuze.alleen_tijd:
        tellingen = _tellingen(dataset, config)
        uitslag["attr014_tellingen"] = tellingen
        uitslag["attr014_som_totaal"] = sum(telling[1] for telling in tellingen.values())
        uitslag["per_check"] = _uitslag(dataset, config)
        ncalls, profieltijd = _aanroepen(dataset, config)
        uitslag["ncalls"] = ncalls
        uitslag["profieltijd_s"] = round(profieltijd, 2)
        print(f"kenmerken: {len(tellingen)}, som totaal: {uitslag['attr014_som_totaal']}")
        print(f"ncalls: {ncalls}")
        print(f"profieltijd: {profieltijd:.2f} s")

    uitslag["of_class_scan_s"] = _scankosten(dataset, config)
    uitslag["sweep"] = _sweepkosten(dataset)
    print(f"sweep: {uitslag['sweep']}")
    uitslag["tijden_s"] = [round(_tijd(dataset, config), 2) for _ in range(keuze.runs)]

    keuze.uit.parent.mkdir(parents=True, exist_ok=True)
    keuze.uit.write_text(json.dumps(uitslag, indent=2, sort_keys=True), encoding="utf-8")
    print(f"geschreven: {keuze.uit}")
    print(f"of_class-scan: {uitslag['of_class_scan_s']}")
    print(f"tijden: {uitslag['tijden_s']}")


if __name__ == "__main__":
    main()
