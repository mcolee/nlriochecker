"""Microbenchmark van de extent-toets: `extent.intersects` per object, ongeprepareerd
versus na `shapely.prepare(extent)`, plus de bulkvorm `shapely.intersects` (issue #146, BO-43).

`ExternalData.binnen_bereik` toetst voor elk GWSW-object `extent.intersects(geometrie)`.
Op De Wolden en Hoogeveen is de EXT-001-populatie (vrijvervalstrengen plus knopen) bijna
40.000 objecten op een begrenzingspolygoon van duizenden punten; zonder een ruimtelijke
index op die polygoon bouwt shapely die per aanroep opnieuw op. `shapely.prepare` bouwt hem
één keer en muteert de geometrie in situ. Dit script meet dat verschil op de echte
populatie, n keer om en om in één proces, en toont dat de uitkomst niet verschuift.

Verwacht (referentiemeting `~/nlriochecker-onderzoek/2026-09-05-fable-swarm/perf-checks/
extent_micro.txt`): ongeprepareerd ~1,6 s per pas, geprepareerd ~0,2 s, bulk ~0,02 s,
`gelijk: True`.

Draai op de voorgrond met een ruime timeout en achter een `flock`, zodat er nooit twee
metingen tegelijk om de vier cores strijden:

    flock /tmp/nlrio-meting.lock uv run python scripts/meet_extent_prepare.py 3

Zwaar: de bronnen- en dataset-laadronde kost circa een halve minuut koud, seconden met een
cachetreffer. De harness-watchdog kilt achtergrond-runs; dus voorgrond.

Gemeten op codestand `c4f5694` (dev, basis van issue #146) plus de #146-werkboom.
Dataset-lader: `gwsw-orox-helpers` 0.2.2 (`laad_met_cache` + gebundelde ontologie), via
`scripts/harnas.py:laad`. Dataset `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`, config
`configs/dewoldenhoogeveen.toml`, bronnen `data/gis_dewoldenhoogeveen`.
"""

from __future__ import annotations

import sys
import time

import numpy as np
import shapely
from harnas import laad, verse_context

from nlriochecker.checks.selectie import netwerkknopen, vrijvervalrioolleidingen


def main(n: int) -> None:
    """n keer om en om: de extent-toets ongeprepareerd, geprepareerd en in bulk."""
    dataset, config, bronnen = laad()
    context = verse_context(dataset, config, bronnen)
    extent = bronnen.extent
    assert extent is not None
    print(
        f"extent: {extent.geom_type}, {shapely.get_num_coordinates(extent)} coordinaten, "
        f"{shapely.get_num_geometries(extent)} delen, oppervlak {extent.area / 1e6:.0f} km2",
        flush=True,
    )
    geoms = [c.line for c in vrijvervalrioolleidingen(context) if c.line is not None] + [
        node.point for node in netwerkknopen(context) if node.point is not None
    ]
    print(f"{len(geoms)} objectgeometrieen (EXT-001-populatie)", flush=True)

    # Twee losse exemplaren van dezelfde extent: `prepare` muteert in situ, dus zonder een
    # verse kopie zou de ongeprepareerde meting na de eerste pas ook op de index leunen.
    ongeprepareerd = shapely.from_wkb(shapely.to_wkb(extent))
    geprepareerd = shapely.from_wkb(shapely.to_wkb(extent))
    shapely.prepare(geprepareerd)
    velden = np.array(geoms, dtype=object)

    def per_object_ongeprepareerd() -> list[bool]:
        return [ongeprepareerd.intersects(g) for g in geoms]

    def per_object_geprepareerd() -> list[bool]:
        return [geprepareerd.intersects(g) for g in geoms]

    def bulk() -> list[bool]:
        return list(shapely.intersects(geprepareerd, velden))

    varianten = (
        ("ongeprepareerd", per_object_ongeprepareerd),
        ("geprepareerd", per_object_geprepareerd),
        ("bulk", bulk),
    )
    tijden: dict[str, list[float]] = {naam: [] for naam, _ in varianten}
    uitkomst: dict[str, list[bool]] = {}
    for _ in range(n):
        for naam, functie in varianten:
            t = time.perf_counter()
            uitkomst[naam] = functie()
            tijden[naam].append(time.perf_counter() - t)

    for naam, lijst in tijden.items():
        print(f"{naam}: {' '.join(f'{t:.3f}' for t in lijst)} s", flush=True)
    gelijk = uitkomst["ongeprepareerd"] == uitkomst["geprepareerd"] == uitkomst["bulk"]
    print(f"gelijk: {gelijk} binnen: {sum(uitkomst['bulk'])}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
