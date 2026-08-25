"""Dekking van het GWSW-kenmerk `Begindatum` (aanlegjaar) op putten.

Onderbouwt de jaartal-cijfers in issue #65-vervolg (observatie 6): geen bug en geen
parse-fout, maar een reeel en lokaal schaars databgat. Getallen gemeten op HEAD 020b02c.

Draaien: `uv run python scripts/analyse_begindatum.py`
"""

from pathlib import Path

import geopandas as gpd
from shapely import unary_union

from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, selectie


def classificeer(nodes: list) -> dict:
    """Splitst knopen naar wel/geen begindatum en (parse-diagnose) aspect-zonder-datum."""
    met_datum = met_aspect_geen_datum = geen_aspect = 0
    for n in nodes:
        if n.date("Begindatum") is not None:
            met_datum += 1
        elif n.aspect("Begindatum") is not None:
            met_aspect_geen_datum += 1
        else:
            geen_aspect += 1
    return {
        "n": len(nodes),
        "met_datum": met_datum,
        "met_aspect_geen_datum": met_aspect_geen_datum,
        "geen_aspect": geen_aspect,
    }


def main() -> None:
    dataset, _ = laad_met_cache(
        Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
        [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")],
    )
    config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
    context = CheckContext(dataset=dataset, config=config)

    sg = gpd.read_file("data/gis_koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg")
    poly = unary_union(list(sg.geometry))

    putten = selectie.putten(context)
    binnen = [n for n in putten if n.point is not None and poly.contains(n.point)]
    print("putten heel de dataset:", classificeer(putten))
    print("putten in Koekangerveld:", classificeer(binnen))

    insp = [dataset.nodes[u] for u in dataset.of_class("Inspectieput") if u in dataset.nodes]
    insp_kv = [n for n in insp if n.point is not None and poly.contains(n.point)]
    print("inspectieput dataset:", classificeer(insp))
    print("inspectieput Koekangerveld:", classificeer(insp_kv))

    # parse-diagnose: 0 aspect-zonder-datum overal betekent "waar geen jaartal staat,
    # staat het echt niet in de bron" -- geen leesfout van de pijplijn.


if __name__ == "__main__":
    main()
