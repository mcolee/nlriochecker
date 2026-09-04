#!/usr/bin/env python
"""Meet TOP-019/022/023 op koekangerveld, ter onderbouwing van issue #130.

Draait de drie checks door de registry op `voorbeelden/koekangerveld/koekangerveld_orox.ttl`
met `configs/dewoldenhoogeveen.toml`, door de echte pijplijn (`markeer_vulwaarden` vóór de
checks, net als `toetsrun.py`). Print per check het aantal bevindingen, `examined()` en de
notities; het aantal zuiver-mechanische hulpstukken respectievelijk functieloze knopen
buiten scope staat in die notities. BO-43: een meetscript dat een getal onderbouwt commit
je mee.

Gemeten met gwsw-orox-helpers 0.2.2 (de dataset-lader). Verwachting ná issue #130:
TOP-019 0 (van 5), TOP-022 2 (van 7), TOP-023 0; `examined()` van TOP-022/023 2 (van 29);
27 zuiver-mechanische hulpstukken / 27 functieloze knopen buiten scope.

Gebruik:  uv run python scripts/meet_issue130.py
"""

from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks

DATASET = Path("voorbeelden/koekangerveld/koekangerveld_orox.ttl")
CONFIG = Path("configs/dewoldenhoogeveen.toml")
CHECKS = ["TOP-019", "TOP-022", "TOP-023"]


def main() -> None:
    """Draait de drie checks en print de tellingen en notities."""
    config = load_check_config(CONFIG)
    dataset, _ = laad_met_cache(DATASET, [gebundelde_ontologie()])
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config)
    run = run_checks(context, CHECKS)
    for outcome in run.outcomes:
        print(
            f"{outcome.check_id}: {len(outcome.findings)} bevindingen, examined {outcome.examined}"
        )
        for note in outcome.notes:
            print(f"    note: {note}")


if __name__ == "__main__":
    main()
