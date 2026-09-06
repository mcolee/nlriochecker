"""Meet de cachetreffer-laadtijd en de geheugenpiek van de leeslaag op De Wolden (issue #166).

Onderbouwt de voor/na-getallen van de bump `gwsw-orox-helpers` v0.2.2 -> v0.2.4: de winst
zit op het KOUDE-na-treffer-pad -- de luie graafpickle die pas bij de eerste graafaanraking
van schijf komt (`LuieGraaf._geladen`). Deze meetstraat draait daarom `laad_met_cache` op een
**cachetreffer** en dwingt daarna de graaf te laden (`len(dataset.graph)`), en meet de wandklok
over dat geheel plus `ru_maxrss` (de procespiek in kB).

De cachesleutel hangt aan het dataset-pad, de ontologiekeuze (`None` = gebundeld, zoals `toets`
zonder `--ontologie`) en `FALLBACK_ENCODING`; die worden hier exact als in `toetsrun` gekozen,
zodat de meting de treffer van een gewone slotrun raakt en niet stil mist. `LADER_VERSIE` leeft
in de leeslaag, dus v0.2.2 en v0.2.4 schrijven onder verschillende sleutels: beide caches
bestaan naast elkaar en de eerste v0.2.4-lading is koud (telt niet mee).

Één meting per proces (zodat `ru_maxrss` de piek van díé lading is). De voor/na-vergelijking
komt van buiten: draai dit script om en om onder de twee geïnstalleerde versies (via
`uv sync` op de gepinde tag), elke meetrun achter een `flock`, n >= 3. Eenduidig heet de
uitslag als de traagste v0.2.4-meting sneller is dan de snelste v0.2.2-meting (en idem voor
`ru_maxrss`).

    RESULTAAT <wandklok_s> <ru_maxrss_kB> <gwsw_versie> <cache.bron> <graaf_seconden>

Lader (de gemeten laag): `gwsw-orox-helpers`. v0.2.2 = commit efa0ade (tag `v0.2.2`), v0.2.4 =
commit f306f57 (annotated tag `v0.2.4`, tag-object 346af6c). De geïnstalleerde versie staat op
elke RESULTAAT-regel. Dataset `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`; in een worktree
zonder eigen `data/` wijst `--dataset` naar de hoofdrepo (BO-43).
"""

from __future__ import annotations

import argparse
import resource
import sys
import time
from importlib.metadata import version
from pathlib import Path

from gwsw_orox_helpers.cache import laad_met_cache
from rdflib import URIRef

from nlriochecker.checkconfig import FALLBACK_ENCODING


def meet(dataset_pad: Path) -> None:
    """Meet één cachetreffer-lading inclusief graafmaterialisatie; schrijft een RESULTAAT-regel."""
    begin = time.perf_counter()
    dataset, cache = laad_met_cache(
        dataset_pad, None, None, True, fallback_encoding=FALLBACK_ENCODING
    )
    # Dwing de luie graafpickle van schijf: dat is het pad waar #59/#62/#63 op winnen.
    _ = len(dataset.graph)
    # Een lees die zeker de graaf raakt, mocht __len__ ooit gememoiseerd zijn zonder lading.
    dataset.graph.heeft_subject(URIRef("urn:nlriochecker:meet"))
    wandklok = time.perf_counter() - begin
    ru_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # `graaf_seconden` is additief in v0.2.4 (#71); op v0.2.2 bestaat het veld nog niet.
    graaf_seconden = getattr(cache, "graaf_seconden", None)
    print(
        f"RESULTAAT {wandklok:.4f} {ru_maxrss} {version('gwsw-orox-helpers')} "
        f"{cache.bron} {graaf_seconden}",
        flush=True,
    )


def main() -> None:
    """Leest het dataset-pad van de opdrachtregel en meet één cachetreffer."""
    parser = argparse.ArgumentParser(
        description="Cachetreffer-meting van de leeslaag (issue #166)."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="pad naar dewoldenhoogeveen_orox.ttl (absoluut in een worktree zonder data/)",
    )
    args = parser.parse_args()
    meet(args.dataset.resolve())


if __name__ == "__main__":
    sys.exit(main())
