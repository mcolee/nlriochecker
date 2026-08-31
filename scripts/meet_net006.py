"""Meet NET-006 op De Wolden en Hoogeveen door de echte pijplijn (issue #126, BO-87).

Onderbouwt het na-getal van de koppelmatrix-herschrijving (BO-43: een getal in een BO
krijgt een bewaard meetscript). Draait NET-006 over de volledige OroX-dataset met de
projectconfig `configs/dewoldenhoogeveen.toml`, ná `markeer_vulwaarden` -- precies de
stappen die `toetsrun.py` vóór de checks zet, zodat het cijfer met een volle `toets`-run
overeenkomt. Het voor-getal komt uit de referentierun `uitvoer/31082026_slotrun`
(`bevindingen.json`, check_id NET-006).

Zwaar: een koude laadronde kost circa een halve minuut en piekt onder de 2 GB; start dit
script met `run_in_background`.

    uv run python scripts/meet_net006.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, run_checks

WORTEL = Path(__file__).resolve().parents[1]
DATASET = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
CONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"


def main() -> None:
    """Laadt de dataset, draait NET-006 en telt de bevindingen."""
    config = load_check_config(CONFIG)
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )

    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["NET-006"]).outcomes[0]

    koppelingen: Counter[str] = Counter()
    for finding in outcome.findings:
        for koppeling in finding.details.get("koppelingen", []):
            koppelingen[koppeling] += 1

    print(f"NET-006 bevindingen (na, whitelist): {len(outcome.findings)}")
    print(f"NET-006 beoordeelde knopen (examined): {outcome.examined}")
    print("Overtreden gerichte koppelingen (aantal knoop-koppelingen):")
    for koppeling, aantal in koppelingen.most_common():
        print(f"  {koppeling}: {aantal}")
    print("Toelichting (wat niet beoordeeld is):")
    for note in outcome.notes:
        print(f"  - {note}")


if __name__ == "__main__":
    main()
