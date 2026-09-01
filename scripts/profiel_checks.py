"""Profileer een koude toetsrun op De Wolden: runtime per check.

Draait de echte pijplijn (`voer_toets_uit`, cache uit = koud, incl. externe
bronnen) en meet per check de wandkloktijd van run()/examined()/notes(). De
meting wikkelt elke check-klasse afzonderlijk om, zodat een geerfde run()-methode
(HGT-001/002, NET-001/002, TOP-002/003, TOP-022/023 delen er een) correct per
check splitst -- cProfile aggregeert per code-object en kan dat niet.

Laatste meting (HEAD 9f42eb9, gwsw-orox-helpers 0.1.0, 2026-09-01): koude
wandkloktijd ~144 s, waarvan ~77 s checkwerk. Zwaarste: HGT-003 13,3 s
(AHN-raster + dure notes()), EXT-001 11,5 s (shapely-doorkruisingen), EXT-009
8,8 s (NWB-wegvakken), HGT-001/002 elk ~6,5 s (AHN-bemonstering), TOP-006 5,4 s.
Twee kostenmotoren: rasterio AHN-bemonstering en shapely-geometrie.

Caveat: dit zijn tijden zoals een echte cold run ze beleeft. Checks delen lui
opgebouwde structuren (graafindexen, `treffers`, `volledige_context()`); de
eerste check die zo'n structuur aanraakt draagt de opbouwkosten, latere krijgen
een cachetreffer. De volgorde is `sorted(REGISTRY)`.

Draaien: uv run python scripts/profiel_checks.py <uitvoermap>
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

from nlriochecker.checks import REGISTRY
from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit

TTL = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
CONFIG = Path("configs/dewoldenhoogeveen.toml")
BRONNEN = Path("data/gis_dewoldenhoogeveen")

tijden: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))


def wikkel() -> None:
    """Vervang run/examined/notes van elke check-klasse door een timer per check-id."""
    for check_id in sorted(REGISTRY):
        cls = REGISTRY[check_id]
        for methode in ("run", "examined", "notes"):
            origineel = getattr(cls, methode)

            def maak(orig, cid=check_id, m=methode):  # type: ignore[no-untyped-def]
                def getimed(self, context):  # type: ignore[no-untyped-def]
                    t = time.perf_counter()
                    resultaat = orig(self, context)
                    if m == "run":  # run() geeft een iterator -> materialiseren om te meten
                        resultaat = list(resultaat)
                    tijden[cid][m] += time.perf_counter() - t
                    return resultaat

                return getimed

            # setattr op de subklasse zelf schaduwt een geerfde methode, dus
            # gedeelde run()-code krijgt per check zijn eigen wrapper.
            setattr(cls, methode, maak(origineel))


def main() -> None:
    """Draai de koude toets en print de runtime per check, aflopend."""
    uitvoermap = Path(sys.argv[1])
    wikkel()
    opdracht = Toetsopdracht(
        dataset_pad=TTL,
        uitvoermap=uitvoermap,
        projectconfig=CONFIG,
        bronnen=BRONNEN,
        met_geopackage=False,
        met_csv=False,
        met_json=False,
        gebruik_cache=False,
    )
    t0 = time.perf_counter()
    voer_toets_uit(opdracht)
    wand = time.perf_counter() - t0

    print(f"\nKOUDE WANDKLOKTIJD: {wand:.1f} s\n")
    print(f"{'check':<12} {'run':>9} {'examined':>9} {'notes':>9} {'totaal':>9}")
    rijen = []
    for cid, m in tijden.items():
        r, e, n = m.get("run", 0.0), m.get("examined", 0.0), m.get("notes", 0.0)
        rijen.append((cid, r, e, n, r + e + n))
    for cid, r, e, n, tot in sorted(rijen, key=lambda x: x[4], reverse=True):
        if tot >= 0.05:
            print(f"{cid:<12} {r:>9.2f} {e:>9.2f} {n:>9.2f} {tot:>9.2f}")
    print(f"\nSom per-check-totalen: {sum(x[4] for x in rijen):.1f} s")
    print(f"Checks met totaal < 0,05 s: {sum(1 for x in rijen if x[4] < 0.05)} (weggelaten)")


if __name__ == "__main__":
    main()
