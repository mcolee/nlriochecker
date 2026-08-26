"""Welke checks systemisch heten, en wat de minimumpopulatie van BO-59 daaraan doet.

Onderbouwt BO-59 (de systemisch-vlag geldt pas vanaf 100 bekeken objecten). Het script
draait alle checks gemeentebreed door de echte pijplijn (`markeer_vulwaarden` ->
`run_checks`), zoekt de uitslagen waarvan de populatieratio boven `systemisch_drempel`
uitkomt, en zegt er per uitslag bij of `melding._is_systemisch` hem nog systemisch noemt.
Daarnaast draait het RVZ-006 als gebiedsrun op Koekangerveld -- het geval waarvoor de
minimumpopulatie er is.

Gemeten op De Wolden en Hoogeveen (`configs/dewoldenhoogeveen.toml`, commit `29ccb17`),
met drempel 0,80 en minimum 100:

  gemeentebreed  RVZ-002  245/245 = 1,00  -> systemisch (245 >= 100)
  gemeentebreed  RVZ-003  245/245 = 1,00  -> systemisch (245 >= 100)
  gemeentebreed  ATTR-014                 -> systemisch, zelf gedeclareerd
  Koekangerveld  RVZ-006   26/26  = 1,00  -> NIET systemisch (26 < 100)

Er is geen uitslag met een populatie tussen 26 en 245 die boven de drempel uitkomt; elke
minimumwaarde in dat bereik geeft vandaag dus dezelfde uitkomst.

Draaien: `uv run python scripts/analyse_systemisch_minimum.py`
"""

from pathlib import Path

import geopandas as gpd
from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden
from shapely import unary_union

from nlriochecker.afbakening import bouw_analyseset
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.studiegebied import StudyArea
from nlriochecker.uitvoer.melding import _is_systemisch

DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
ONTOLOGIE = gebundelde_ontologie()
KOEKANGERVELD = Path("data/gis_koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg")


def main() -> None:
    dataset, _ = laad_met_cache(DATASET, [ONTOLOGIE])
    config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    drempel = config.rapport.systemisch_drempel
    minimum = config.rapport.systemisch_minimum_bekeken
    print(f"drempel {drempel}, minimum {minimum}")

    context = CheckContext(dataset=dataset, config=config, volledige_dataset=dataset)
    run = run_checks(context)
    print("\n-- gemeentebreed: ratio boven de drempel --")
    for uitkomst in sorted(run.outcomes, key=lambda u: u.check_id):
        gevonden = len(uitkomst.findings) + uitkomst.weggelaten
        if not uitkomst.examined or not gevonden:
            continue
        ratio = gevonden / uitkomst.examined
        if ratio > drempel:
            vlag = "SYSTEMISCH" if _is_systemisch(uitkomst, config) else "vervalt (te klein)"
            print(f"  {uitkomst.check_id}: {gevonden}/{uitkomst.examined} = {ratio:.2f} -> {vlag}")
    zelf = sorted({f.check_id for u in run.outcomes for f in u.findings if f.systemisch})
    print(f"  zelf-gedeclareerd systemisch: {', '.join(zelf) or 'geen'}")

    vlakken = gpd.read_file(KOEKANGERVELD)
    area = StudyArea(
        name="Koekangerveld",
        geometry=unary_union(list(vlakken.geometry)),
        source=KOEKANGERVELD,
        feature_count=len(vlakken),
    )
    analyseset = bouw_analyseset(dataset, area, config)
    gebiedsrun = run_checks(
        CheckContext(
            dataset=analyseset.dataset,
            config=config,
            analyseset=analyseset,
            volledige_dataset=dataset,
            gedeelde_volledige_context=context,
        ),
        ["RVZ-006"],
    ).beperk_tot_studiegebied(area, analyseset.kern, leeg_toegestaan=True)
    uit = gebiedsrun.outcomes[0]
    gevonden = len(uit.findings) + uit.weggelaten
    ratio = gevonden / uit.examined if uit.examined else 0.0
    print("\n-- Koekangerveld, RVZ-006 --")
    print(
        f"  {gevonden} gevonden (waarvan {uit.weggelaten} weggelaten) op {uit.examined} "
        f"bekeken = {ratio:.2f}; boven drempel: {ratio > drempel}; "
        f"_is_systemisch: {_is_systemisch(uit, config)}"
    )


if __name__ == "__main__":
    main()
