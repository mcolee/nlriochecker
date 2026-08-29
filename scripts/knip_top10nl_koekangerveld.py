#!/usr/bin/env python
"""Knipt het TOP10NL-plaatsvlak van Koekangerveld uit het De Wolden-extract.

Voor Koekangerveld is geen eigen TOP10NL-levering aangeleverd, terwijl EXT-009 de
bebouwde kom nodig heeft (`[bronnen] top10nl` in `src/nlriochecker/checks.toml`). Dit
script maakt hem uit het De Wolden-extract, dat het gebied dekt: alles wat de omhullende
van het studiegebied raakt, in dezelfde laag- en kolomvorm.

Bewust een script en geen handmatige stap: het getal in de configuratie moet herleidbaar
blijven, en een met de hand geknipt bestand is dat niet. De uitvoer staat in `data/`,
dat git-ignored is; een bestaand bestand wordt overschreven, en een invoerbestand nooit.

Gebruik:  uv run python scripts/knip_top10nl_koekangerveld.py
"""

from __future__ import annotations

from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
BRON = WORTEL / "data" / "gis_dewoldenhoogeveen" / "TOP10NL_plaats_vlak_DeWoldenHoogeveen.gpkg"
GEBIED = WORTEL / "data" / "gis_koekangerveld" / "cbs_buurt_koekangerveld_studiegebied.gpkg"
DOEL = WORTEL / "data" / "gis_koekangerveld" / "top10nl_plaats_vlak_koekangerveld.gpkg"
LAAG = "plaats_vlak"


def main() -> int:
    """Schrijft het geknipte plaatsvlak; slaat over als een bron ontbreekt."""
    import geopandas as gpd

    for pad in (BRON, GEBIED):
        if not pad.exists():
            print(f"overgeslagen: {pad} staat niet in data/")
            return 0

    from shapely.geometry import box

    plaatsen = gpd.read_file(BRON, layer=LAAG).to_crs(28992)
    gebied = gpd.read_file(GEBIED).to_crs(28992)
    # De omhullende van het studiegebied en niet het gebied zelf: een komvlak dat net
    # buiten de buurtgrens begint hoort er nog steeds bij, anders valt een straat op de
    # rand ten onrechte buiten de kom.
    binnen = plaatsen[plaatsen.intersects(box(*gebied.total_bounds))]
    binnen.to_file(DOEL, layer=LAAG, driver="GPKG")
    print(f"Geschreven: {DOEL.relative_to(WORTEL)} ({len(binnen)} plaatsvlakken)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
