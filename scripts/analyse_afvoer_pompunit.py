"""NET-001-bereikbaarheid onder varianten van het afvoereindpunt-model.

Onderbouwt issues A (drukriolering traceerbaar) en B (Pompunit geen eindpunt), het
#65-vervolg. Meet hoeveel vuilwater/gemengd-strengen NET-001 onbereikbaar acht onder:

  huidig   : Pompunit telt als eindpunt, graaf = alleen vrijverval        -> 9062 / 24
  hard-weg : Pompunit uit afvoer_eindpunt, verder niets                   -> 9707 / 27
  (c)      : mechanisch als edges via GERESOLVEERDE putten, geen Pompunit -> 9410 / 27
  (c')     : mechanisch DOOR hulpstukken (rauwe knoop), geen Pompunit     -> 9206 / 26
  (c'+L)   : (c') plus lozingspunten als geldig vuilwater-eindpunt        -> 8467 /  7

Oorzaak dat (c) faalt: het persnet komt samen op T_stukken/hulpstukken, die via
`resolve_network_node` naar None resolven (geen netwerkknoop). Elke T versplintert de
graaf; het gemaal is er wel (bv. Rioolgemaal knp3437), maar onbereikbaar via geresolveerde
edges. Getallen gemeten op HEAD 020b02c met een richting-agnostische (ongerichte)
mechanische connectiviteit.

Draaien: `uv run python scripts/analyse_afvoer_pompunit.py`
"""

from pathlib import Path

import geopandas as gpd
from gwsw_orox_helpers.cache import laad_met_cache
from shapely import unary_union

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.selectie import mechanischeleidingen
from nlriochecker.checks.verbanden import _netwerk, verbonden_knopen


def reverse_bereikt(graph, eindpunten: set[str]) -> set[str]:
    """Knopen die stroomafwaarts een van deze eindpunten bereiken (reverse BFS)."""
    omgekeerd = graph.reverse(copy=False)
    bereikt = {u for u in eindpunten if u in omgekeerd}
    stapel = list(bereikt)
    while stapel:
        knoop = stapel.pop()
        for buur in omgekeerd.successors(knoop):
            if buur not in bereikt:
                bereikt.add(buur)
                stapel.append(buur)
    return bereikt


def main() -> None:
    dataset, _ = laad_met_cache(
        Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
        [Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")],
    )
    config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
    context = CheckContext(dataset=dataset, config=config)
    sg = gpd.read_file("data/gis_koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg")
    poly = unary_union(list(sg.geometry))

    netwerk = _netwerk(context)
    basis = netwerk.graph
    wortels = config.klassen.netwerkknopen
    gezocht = {
        u for w in config.klassen.vuilwater for u in dataset.of_class(w) if u in dataset.conduits
    }
    mech = mechanischeleidingen(context)
    afvoer = config.klassen.afvoer_eindpunt
    lozing = config.klassen.lozings_eindpunt

    def in_kv(conduit) -> bool:
        ln = conduit.line
        return ln is not None and poly.contains(ln.centroid)

    def augment(passthrough: bool):
        graph = basis.copy()
        for c in mech:
            b, e = verbonden_knopen(context, c)
            if passthrough:
                b = b or c.start_node
                e = e or c.end_node
            if b and e:
                graph.add_edge(b, e)
                graph.add_edge(e, b)
        return graph

    def onbereikbaar(graph, eindpuntklassen) -> tuple[int, int]:
        eps = {u for w in eindpuntklassen for u in dataset.of_class(w) if u in graph}
        bereikt = reverse_bereikt(graph, eps)
        tot = kv = 0
        for c in netwerk.conduits:
            if c.uri not in gezocht:
                continue
            begin = dataset.resolve_network_node(c.start_node, wortels)
            if begin not in bereikt:
                tot += 1
                if in_kv(c):
                    kv += 1
        return tot, kv

    zonder_pomp = [k for k in afvoer if k != "Pompunit"]
    aug_pt = augment(passthrough=True)
    varianten = {
        "huidig  (Pompunit-eindpunt, geen mechanisch)": (basis, afvoer),
        "hard-weg (Pompunit uit afvoer, geen mechanisch)": (basis, zonder_pomp),
        "(c)  mechanisch via geresolveerde putten": (augment(False), zonder_pomp),
        "(c') mechanisch door hulpstukken": (aug_pt, zonder_pomp),
        "(c'+L) door hulpstukken + lozing telt mee": (aug_pt, zonder_pomp + lozing),
    }
    print(f"{'variant':50} onbereikbaar tot / Koekangerveld")
    for naam, (graph, klassen) in varianten.items():
        tot, kv = onbereikbaar(graph, klassen)
        print(f"  {naam:48} {tot:5} / {kv}")


if __name__ == "__main__":
    main()
