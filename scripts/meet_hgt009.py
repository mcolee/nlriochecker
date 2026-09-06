"""Meet HGT-009 op De Wolden en Hoogeveen door de echte pijplijn (issue #141, BO-93).

Onderbouwt de voor/na-getallen van de HGT-009-wijziging (BO-43: een getal in een BO krijgt
een bewaard meetscript). HGT-009 vergeleek `min(aanvoer-BOB-eind)` met `max(afvoer-BOB-begin)`
en miste zo een enkele hoge aanvoer naast een lage die gelijk ligt met de afvoer. De check
toetst sinds #141 per aanvoerende streng `bob_eind - max(afvoer)`.

Draait HGT-009 over de volledige OroX-dataset met de projectconfig
`configs/dewoldenhoogeveen.toml`, ná `markeer_vulwaarden` -- precies de stappen die
`toetsrun.py` vóór de checks zet, zodat het cijfer met een volle `toets`-run overeenkomt.

Meet drie getallen langs dezelfde `paren`-index:
  - oud (min(aanvoer) - max(afvoer) > drempel):   282 knopen
  - nieuw (per aanvoerende streng > drempel):      730 knopen / 816 strengen
en `controle` via `run_checks(["HGT-009"])`, dat sinds de fix per aanvoerende streng meldt:
816 bevindingen op 730 knopen. De trendbreuk (282 -> 816 meldingen) is er een die
`vergelijk` tussen twee meetmomenten over deze codewijziging zal tonen.

Zwaar: een koude laadronde kost circa een halve minuut en piekt onder de 2 GB. Draai op de
voorgrond met een ruime timeout (de harness-watchdog kilt achtergrond-runs op deze machine).

    uv run python scripts/meet_hgt009.py

Gemeten op codestand `eef6e3b` (dev) als basis -- de fix-commit die dit script draagt bouwt
daarop voort (het scripteigen hash is pas ná committen bekend, zoals `meet_net006.py` na #129
en `meet_stelsels.py` na #131). Dataset-lader: `gwsw-orox-helpers` 0.2.2
(`laad_met_cache` + gebundelde ontologie). Dataset
`data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`. Bewaard onder BO-43.
"""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.checks.hoogten import BobSprongZonderValput
from nlriochecker.checks.selectie import valconstructies

WORTEL = Path(__file__).resolve().parents[1]
DATASET = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
CONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"


def main() -> None:
    """Laadt de dataset en meet HGT-009 voor (min-toets) en na (per-aanvoer-toets)."""
    config = load_check_config(CONFIG)
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config)
    drempel = config.drempels.bob_sprong_m
    valput = {node.uri for node in valconstructies(context)}

    check = BobSprongZonderValput()
    oud = 0
    meer_aanvoer = 0
    nieuw_knopen = 0
    nieuw_strengen = 0
    for node, aanvoer, afvoer in check.paren(context):
        if node.uri in valput:
            continue
        binnen = [c.bob_end for c in aanvoer if c.bob_end is not None]
        uit = [c.bob_start for c in afvoer if c.bob_start is not None]
        if not binnen or not uit:
            continue
        if len(binnen) >= 2:
            meer_aanvoer += 1
        if min(binnen) - max(uit) > drempel:
            oud += 1
        hoog = [b for b in binnen if b - max(uit) > drempel]
        if hoog:
            nieuw_knopen += 1
            nieuw_strengen += len(hoog)

    outcome = run_checks(context, ["HGT-009"]).outcomes[0]
    controle_knopen = len({finding.object_uri for finding in outcome.findings})

    print(f"drempel {drempel} m")
    print(f"knopen met >=2 aanvoerende BOB's: {meer_aanvoer}")
    print(f"oud   (min(aanvoer) - max(afvoer)):            {oud} knopen")
    print(
        f"nieuw (per aanvoerende streng > drempel):      {nieuw_knopen} knopen, "
        f"{nieuw_strengen} strengen"
    )
    print(
        f"controle: HGT-009 via run_checks = {len(outcome.findings)} bevindingen "
        f"op {controle_knopen} knopen (examined {outcome.examined})"
    )


if __name__ == "__main__":
    main()
