"""Gelijkwaardigheid van een gebiedsrun en de gemeentebrede run, per CBS-buurt.

Onderbouwt BO-56. BO-12 eist dat de meldingen van een gebied gelijk zijn aan die van de
gemeentebrede run beperkt tot datzelfde gebied. Sinds issue #72 loopt de bereikbaarheid van
NET-001/NET-002 door het persnet en sinds BO-55 is een pompput zelf geen eindpunt meer; de
contextschil moet die route dus meenemen, anders valt het gemaal erachter buiten de
analyseset.

Gemeten op De Wolden en Hoogeveen (88 buurten), NET-001/NET-002/RVZ-006:

  contextschil op alleen vrijverval, Pompunit nog eindpunt  ->  7 afwijkende buurten
  contextschil op alleen vrijverval, Pompunit eruit         -> 17 afwijkende buurten
  contextschil over vrijverval EN persnet (BO-56)           ->  0 afwijkende buurten

Alle afwijkingen zaten op NET-001 en waren extra bevindingen in de gebiedsrun; geen enkele
buurt meldde er minder dan de gemeentebrede run.

Draaien: `uv run python scripts/analyse_contextschil_persnet.py [configpad]`
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

from nlriochecker.afbakening import bouw_analyseset, bouw_gedeelde_index
from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import markeer_vulwaarden
from nlriochecker.studiegebied import StudyArea

CHECKS = ["NET-001", "NET-002", "RVZ-006"]
BUURTEN = Path("data/gis_dewoldenhoogeveen/CBS_buurten_DeWoldenHoogeveen.gpkg")


def gemeld(run: CheckRun, check_id: str) -> set[str]:
    """De URI's waarover deze check in deze run meldt."""
    for uitkomst in run.outcomes:
        if uitkomst.check_id == check_id:
            return {bevinding.object_uri for bevinding in uitkomst.findings}
    return set()


def buurten() -> list[StudyArea]:
    """Elke buurt als eigen studiegebied.

    Bewust niet via `load_studiegebieden`: die weigert dubbele buurtnamen, en de
    CBS-kaart draagt er een paar. Voor deze meting telt alleen de geometrie.
    """
    vlakken = gpd.read_file(BUURTEN)
    return [
        StudyArea(name=str(index), geometry=rij.geometry, source=BUURTEN, feature_count=1)
        for index, rij in vlakken.iterrows()
        if rij.geometry is not None and not rij.geometry.is_empty
    ]


def main() -> None:
    dataset, _ = laad_met_cache(
        Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
        [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")],
    )
    configpad = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/dewoldenhoogeveen.toml")
    config = load_check_config(configpad)
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config, volledige_dataset=dataset)
    volledig = run_checks(context, CHECKS)

    gedeeld = bouw_gedeelde_index(dataset, config)
    alle = buurten()
    print(f"config: {configpad}\n{len(alle)} buurten")

    afwijkend = 0
    for area in alle:
        analyseset = bouw_analyseset(dataset, area, config, gedeeld=gedeeld)
        if not analyseset.kern:
            continue
        gebiedscontext = CheckContext(
            dataset=analyseset.dataset,
            config=config,
            analyseset=analyseset,
            volledige_dataset=dataset,
            gedeelde_volledige_context=context,
        )
        gebiedsrun = run_checks(gebiedscontext, CHECKS).beperk_tot_studiegebied(
            area, analyseset.kern, leeg_toegestaan=True
        )
        referentie = volledig.beperk_tot_studiegebied(area, analyseset.kern, leeg_toegestaan=True)
        for check_id in CHECKS:
            gebied = gemeld(gebiedsrun, check_id)
            ref = gemeld(referentie, check_id)
            if gebied != ref:
                afwijkend += 1
                print(
                    f"  AFWIJKING buurt {area.name} {check_id}: gebiedsrun {len(gebied)} / "
                    f"gemeentebreed {len(ref)} (+{len(gebied - ref)} / -{len(ref - gebied)})"
                )

    print(f"KLAAR: {afwijkend} afwijkingen over {len(alle)} buurten x {len(CHECKS)} checks")


if __name__ == "__main__":
    main()
