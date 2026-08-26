"""Het scopelabel en de getelde populatie per check (issue #77, BO-58).

Onderbouwt de tabel in BO-58: welke van de drie waarden van `bekeken_scope` waar
voorkomt, en hoe `bekeken` per check verschilt tussen een gemeentebrede run en een
gebiedsrun. De cijfers komen uit het nieuwe enveloppeveld `checks` van
`bevindingen.json`, dus langs de gewone uitvoerroute en niet uit een nagebouwde
telling. Getallen gemeten op HEAD 36d2a2f.

Draaien: `uv run python scripts/analyse_scope_per_check.py [uitvoermap]`
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from gwsw_orox_helpers.cache import laad_met_cache

from nlriochecker.checkconfig import load_check_config
from nlriochecker.meting import Meetbereik
from nlriochecker.studiegebied import Studiegebieden, load_studiegebieden
from nlriochecker.toetsloop import toets_gebieden
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer

TTL = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
ONTOLOGIE = [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")]
CONFIG = Path("configs/dewoldenhoogeveen.toml")
GEBIED = Path("data/gis_koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg")


def meet(doel: Path, gebieden: Studiegebieden | None) -> list[dict[str, object]]:
    """Draait de eigen checks en geeft het veld `checks` uit de geschreven JSON terug."""
    dataset, _ = laad_met_cache(TTL, ONTOLOGIE)
    runs = toets_gebieden(
        dataset,
        gebieden,
        load_check_config(CONFIG),
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    uitvoer = schrijf_uitvoer(runs[0].run, doel, met_geopackage=False, met_csv=False)
    assert uitvoer.json is not None
    document: dict[str, object] = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    rijen: list[dict[str, object]] = document["checks"]  # type: ignore[assignment]
    return rijen


def toon(naam: str, rijen: list[dict[str, object]]) -> None:
    """Print de tabel per check en daarna de telling per scope."""
    print(f"\n### {naam} ({len(rijen)} checks)\n")
    print("| Check | Bekeken | Bekeken scope | Populatie |")
    print("|---|---:|---|---|")
    for rij in rijen:
        print(
            f"| {rij['check_id']} | {rij['bekeken']} | {rij['bekeken_scope']} "
            f"| {rij['populatie']} |"
        )
    per_scope: dict[str, list[str]] = {}
    for rij in rijen:
        per_scope.setdefault(str(rij["bekeken_scope"]), []).append(str(rij["check_id"]))
    print()
    for scope, ids in sorted(per_scope.items()):
        print(f"{scope}: {len(ids)} checks -- {', '.join(ids)}")


def main() -> None:
    """Meet gemeentebreed en op Koekangerveld, en print beide tabellen."""
    doel = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    toon("De Wolden en Hoogeveen (geen studiegebied)", meet(doel / "gemeentebreed", None))
    toon("Koekangerveld (studiegebied)", meet(doel / "koekangerveld", load_studiegebieden(GEBIED)))


if __name__ == "__main__":
    main()
