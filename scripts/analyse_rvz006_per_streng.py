"""RVZ-006 per gemengde streng, en wat de nulmeting zonder kaartobject laat.

Onderbouwt issue #75. Twee getallen die in het CHANGELOG en in BO-57 staan:

1. **RVZ-006.** De check meldde per gemengd deelstelsel op een enkele knoop en meldt
   sinds #75 per gemengde streng van dat deelstelsel. Het script telt beide: het aantal
   bevindingen (het nieuwe model) en het aantal verschillende `cluster_id`'s daarin (het
   oude model, want dat was er precies een per falend deelstelsel). Gemeentebreed en in
   een gebiedsrun op Koekangerveld, allebei door de echte pijplijn
   (`markeer_vulwaarden` -> `run_checks` -> `beperk_tot_studiegebied`).
2. **De nulmeting zonder kaartobject.** De laag `stelsels` is met #75 vervallen, dus een
   SHACL-overtreding waarvan de focusnode een geregistreerd stelsel is komt niet meer op
   de kaart. Het script telt hoeveel dat er zijn, naast de overtredingen die al nergens
   op uitkwamen (een klassenaam uit `CfkTypes_typ`); samen is dat de rapportregel "geen
   kaartobject".

Het script draait ongewijzigd op de code van vóór #75, zodat het oude en het nieuwe model
met dezelfde meting vergeleken kunnen worden. Gemeten op De Wolden en Hoogeveen, `b9d6060`
(vóór) tegen `7000b5e` (ná):

                          | vóór            | ná
  RVZ-006 gemeentebreed   | 99 / 99 deelst. | 1062 / 99 deelst.  (794 -> 7784 onderzocht)
  RVZ-006 Koekangerveld   |  2 /  2 deelst. |   26 /  2 deelst.  ( 10 ->   26 onderzocht)
  nulmeting zonder kaart  | 578 (11 + 567)  |  578 (11 + 567)

Het aantal falende deelstelsels staat stil; alleen de korrel wordt fijner. "Onderzocht"
verschuift mee van het aantal netwerkdelen naar het aantal gemengde strengen. De
nulmetingtelling verandert niet -- die 567 stonden vóór #75 op de laag `stelsels` en
staan er sindsdien als rapportregel.

Draaien: `uv run python scripts/analyse_rvz006_per_streng.py [configpad]`
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
from shapely import unary_union

from nlriochecker.afbakening import bouw_analyseset
from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import markeer_vulwaarden
from nlriochecker.meting import laad_nulmeting
from nlriochecker.nulbevinding import bouw_nulbevindingen
from nlriochecker.studiegebied import StudyArea

CHECK = "RVZ-006"
DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
ONTOLOGIE = Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")
KOEKANGERVELD = Path("data/gis_koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg")
SHACL = Path("data/shacl_nulmeting")
RAPPORTEN = {
    "Hyd": SHACL / "gwsw_shacl_report_conformiteit_Hyd.csv",
    "MdsPlan": SHACL / "gwsw_shacl_report_conformiteit_MdsPlan.csv",
    "MdsProj": SHACL / "gwsw_shacl_report_MdsProj.csv",
}


def telling(run: CheckRun, check_id: str) -> tuple[int, int, int]:
    """(bevindingen, verschillende deelstelsels, onderzochte objecten) van een check."""
    for uitkomst in run.outcomes:
        if uitkomst.check_id == check_id:
            clusters = {
                str(bevinding.details.get("cluster_id", "")) for bevinding in uitkomst.findings
            }
            return len(uitkomst.findings), len(clusters - {""}), uitkomst.examined
    return 0, 0, 0


def koekangerveld() -> StudyArea:
    """Het studiegebied Koekangerveld als enkel vlak."""
    vlakken = gpd.read_file(KOEKANGERVELD)
    return StudyArea(
        name="Koekangerveld",
        geometry=unary_union(list(vlakken.geometry)),
        source=KOEKANGERVELD,
        feature_count=len(vlakken),
    )


def meet_nulmeting(dataset, drempel: float) -> None:
    """Telt de overtredingen die geen kaartobject krijgen."""
    nulmeting = laad_nulmeting(list(RAPPORTEN.values()), list(RAPPORTEN))
    bevindingen = bouw_nulbevindingen(nulmeting, dataset, drempel)
    stelsels = {str(subject) for subject in dataset.subjects_of_class("Stelsel")}
    zonder_object = sum(1 for b in bevindingen if not b.object_uri)
    op_stelsel = sum(1 for b in bevindingen if b.object_uri in stelsels)
    print(
        f"nulmeting: {len(bevindingen)} ontdubbelde overtredingen; "
        f"{zonder_object + op_stelsel} zonder kaartobject "
        f"({zonder_object} klassenaam uit CfkTypes_typ, {op_stelsel} op een stelsel)"
    )


def main() -> None:
    dataset, _ = laad_met_cache(DATASET, [ONTOLOGIE])
    configpad = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/dewoldenhoogeveen.toml")
    config = load_check_config(configpad)
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    print(f"config: {configpad}")

    context = CheckContext(dataset=dataset, config=config, volledige_dataset=dataset)
    volledig = run_checks(context, [CHECK])
    bevindingen, clusters, onderzocht = telling(volledig, CHECK)
    print(
        f"{CHECK} gemeentebreed: {bevindingen} bevindingen op {clusters} deelstelsels, "
        f"{onderzocht} onderzocht"
    )

    area = koekangerveld()
    analyseset = bouw_analyseset(dataset, area, config)
    gebiedscontext = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        analyseset=analyseset,
        volledige_dataset=dataset,
        gedeelde_volledige_context=context,
    )
    gebiedsrun = run_checks(gebiedscontext, [CHECK]).beperk_tot_studiegebied(
        area, analyseset.kern, leeg_toegestaan=True
    )
    bevindingen, clusters, onderzocht = telling(gebiedsrun, CHECK)
    print(
        f"{CHECK} Koekangerveld: {bevindingen} bevindingen op {clusters} deelstelsels, "
        f"{onderzocht} onderzocht (kern {len(analyseset.kern)} objecten)"
    )

    meet_nulmeting(dataset, config.rapport.systemisch_drempel)


if __name__ == "__main__":
    main()
