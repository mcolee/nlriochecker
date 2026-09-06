"""Meet tijd en RSS van `load_external_data` op De Wolden en Hoogeveen (issue #147).

Onderbouwt de winst van het kolomfilter (`externedata.LEESKOLOMMEN`, `columns=`): de
externe bronnen worden voortaan smal ingelezen in plaats van met al hun kolommen. Deze
meting isoleert de bronfase; de gepaarde meting van de *volle* `toets` (`ru_maxrss` en
wandklok, n>=3 voor/na om en om achter `flock /tmp/nlrio-meting.lock` met
`/usr/bin/time -f 'wandklok %e s, ru_maxrss %M kB'`) staat in het rapport bij het issue.

Meetvorm ontleend aan `~/nlriochecker-onderzoek/2026-09-05-fable-swarm/perf-uitvoer-geheugen/
bronnen_geheugen.py`: RSS uit `/proc/self/status`, met `gc.collect()` + `malloc_trim(0)`
zodat de gemeten piek de vastgehouden geometrie en dicts is en niet de allocator-arena.

BO-43 -- de lader waarop het getal rust: `gwsw-orox-helpers` v0.2.2
(commit `efa0ade7277a7c48b55fb1b5044a55191ebe876b`); de nlriochecker-code is die van de
tak/worktree waaruit dit script draait (voor/na = ec1b15a resp. issue #147).

Gebruik (elke run apart, achter flock, op de voorgrond):
    flock /tmp/nlrio-meting.lock uv run python scripts/meet_bronnen_kolomfilter.py
    flock /tmp/nlrio-meting.lock uv run --project <worktree-voor> \\
        python scripts/meet_bronnen_kolomfilter.py
"""

from __future__ import annotations

import ctypes
import gc
import time
from pathlib import Path

from nlriochecker.checkconfig import load_check_config
from nlriochecker.externedata import Dekkingseis, load_external_data

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "configs/dewoldenhoogeveen.toml"
BRONNEN = REPO / "data/gis_dewoldenhoogeveen"

_libc = ctypes.CDLL("libc.so.6")


def _rss_mib() -> int:
    """De resident set size van dit proces in MiB, uit `/proc/self/status`."""
    for regel in Path("/proc/self/status").read_text().splitlines():
        if regel.startswith("VmRSS:"):
            return int(regel.split()[1]) // 1024
    return 0


def _trim() -> int:
    """Ruimt op en levert de RSS erna, zodat de arena de meting niet vertroebelt."""
    gc.collect()
    _libc.malloc_trim(0)
    return _rss_mib()


def main() -> None:
    """Laadt de externe bronnen een keer en rapporteert tijd en RSS."""
    config = load_check_config(CONFIG)
    bronnen = config.bronnen.model_copy(update={"map": "."})
    eis = Dekkingseis(
        marge_m=config.drempels.ext_zoekafstand_max_m,
        tolerantie_m=config.bronnen.dekking_tolerantie_m,
    )

    voor = _trim()
    print(f"[meet] start rss {voor} MiB", flush=True)
    t = time.perf_counter()
    data = load_external_data(bronnen, BRONNEN, dekkingseis=eis)
    duur = time.perf_counter() - t
    na = _rss_mib()
    vast = _trim()

    lagen = {rol: len(laag) for rol, laag in sorted(data.layers.items())}
    print(
        f"[meet] load_external_data {duur:.1f} s; rss {voor}->{na} MiB; "
        f"na gc+malloc_trim {vast} MiB (delta {vast - voor} MiB)",
        flush=True,
    )
    print(f"[meet] lagen (features): {lagen}", flush=True)


if __name__ == "__main__":
    main()
