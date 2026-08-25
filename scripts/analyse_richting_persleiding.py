"""Hoeveel mechanische strengen een vrijvervalrichting kregen, voor en na issue #74.

Onderbouwt de CHANGELOG-regel bij issue #74. De richtingspijl in de laag `strengen` komt
uit het BOB-verval (`uitvoer/gpkg._richting_bob`), maar een mechanische leiding is
pompgestuurd en draagt geen betrouwbare vrijverval-BOB. Meestal viel zo'n leiding al op
`onbekend` terug omdat het BOB ontbreekt; dit script telt de gevallen waarin dat niet zo
was en de kaart dus een fysiek onjuiste groene of rode pijl tekende.

Het roept `_richting_bob` twee keer aan op exact de populatie die de GeoPackage-schrijver
als mechanisch beschouwt (`selectie.mechanischeleidingen`, `[klassen] mechanisch`): een
keer met `mechanisch=False` (het gedrag van vóór #74) en een keer met `mechanisch=True`
(erna). Het schrijft de dataset niet weg -- dat scheelt een volle toetsrun.

Gemeten op De Wolden en Hoogeveen (3720 mechanische leidingen), commit f3e520b:

  voor issue #74:  3676 onbekend, 23 mee, 21 tegen  ->  44 onjuiste pijlen
  na  issue #74:   3720 onbekend                    ->   0 onjuiste pijlen

Let op bij het vergelijken met een oudere run: de GeoPackage van 24-08
(`uitvoer/volledig_24082026/`) telt er 22, niet 44. Die dateert van vóór de laderfix van
issue #60 (de fantoomkoppeling van leidingeinden), waardoor 22 van deze leidingen toen nog
geen herleidbare tekenrichting hadden en om die reden al op `onbekend` stonden.

Draaien: `uv run python scripts/analyse_richting_persleiding.py [configpad]`
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.selectie import mechanischeleidingen
from nlriochecker.uitvoer.gpkg import _richting_bob

DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
ONTOLOGIE = Path("data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl")
CONFIG = Path("configs/dewoldenhoogeveen.toml")


def main() -> None:
    config_pad = Path(sys.argv[1]) if len(sys.argv) > 1 else CONFIG
    dataset, _ = laad_met_cache(DATASET, [ONTOLOGIE])
    config = load_check_config(config_pad)
    context = CheckContext(dataset=dataset, config=config)
    # `_richting_bob` leest van de run alleen `run.dataset`; een volle CheckRun zou hier
    # een toetsronde van minuten kosten zonder dat het cijfer verandert.
    run = SimpleNamespace(dataset=dataset)

    leidingen = mechanischeleidingen(context)
    voor: Counter[str] = Counter()
    na: Counter[str] = Counter()
    for conduit in leidingen:
        voor[_richting_bob(run, conduit, config, mechanisch=False)[0]] += 1
        na[_richting_bob(run, conduit, config, mechanisch=True)[0]] += 1

    print(f"mechanische leidingen: {len(leidingen)}")
    print(f"voor issue #74: {dict(voor)} -> {voor['mee'] + voor['tegen']} onjuiste pijlen")
    print(f"na  issue #74: {dict(na)} -> {na['mee'] + na['tegen']} onjuiste pijlen")


if __name__ == "__main__":
    main()
