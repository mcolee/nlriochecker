#!/usr/bin/env python
"""Meet de stelselboom-leeslaag op de volledige De Wolden- en Hoogeveen-export (issue #131).

Telt twee dingen voor het afrondingscomment van #131:

1. het aantal `gwsw:Stelsel`-instanties in de dataset, en
2. het aantal knopen en strengen met ten minste één omvattend stelsel.

De leeslaag draagt hier nog geen consumer, dus deze telling verandert geen enkele melding
(de referentierun `uitvoer/31082026_slotrun` blijft 147.706); ze is puur ter onderbouwing.

Recept en API: `docs/agents/analyse-harness.md`. Draai met een ruime timeout of in de
achtergrond -- de koude load kost circa een halve minuut.

    uv run python scripts/meet_stelsels.py

Gemeten op repo-commit 35567566 (dev), dataset
`data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`. Bewaard onder BO-43: een getal dat een
issue onderbouwt hoort in een script met de commit-hash erbij, niet in een losse heredoc.
"""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, selectie

DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
CONFIG = Path("configs/dewoldenhoogeveen.toml")


def main() -> None:
    """Laadt de export en print de twee tellingen."""
    # De BrutIS-export draagt cp850-bytes in straatnamen; de terugvalcodering vangt die op.
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    config = load_check_config(CONFIG)
    context = CheckContext(dataset=dataset, config=config)

    stelsels = selectie.stelsels(context)

    knopen_met_stelsel = sum(1 for uri in dataset.nodes if context.stelsels_van(uri))
    strengen_met_stelsel = sum(1 for uri in dataset.conduits if context.stelsels_van(uri))

    print(f"gwsw:Stelsel-instanties: {len(stelsels)}")
    print(f"knopen met >=1 omvattend stelsel: {knopen_met_stelsel} van {len(dataset.nodes)}")
    print(f"strengen met >=1 omvattend stelsel: {strengen_met_stelsel} van {len(dataset.conduits)}")
    print(f"knopen+strengen met >=1 stelsel: {knopen_met_stelsel + strengen_met_stelsel}")


if __name__ == "__main__":
    main()
