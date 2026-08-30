#!/usr/bin/env python
"""Meet wat het doorgeeflende hulpstuk in de vrijvervalgraaf oplevert (issue #105, BO-83).

Waarom dit script onder `scripts/` staat en niet in een scratchpad (BO-43): het
onderbouwt de getallen die in BO-83, in het `CHANGELOG` en in issue #105 staan, en het
is de enige manier om ze na een codewijziging opnieuw te meten. Het meet de HUIDIGE
toestand -- er zit geen monkeypatch in -- en drukt haar af; de vergelijking met de
toestand ervoor is de tabel hieronder.

Gemeten op `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl` met
`configs/dewoldenhoogeveen.toml`, leeslaag `gwsw-orox-helpers` v0.1.0
(git 49d93dfb87fd2a2197478a0f2accfb8d09483e9e, de commit die `uv.lock` vastlegt).

| Meting                                  | vóór  | voorspeld | gemeten |
|-----------------------------------------|------:|----------:|--------:|
| strengen buiten de netwerkanalyse       |   152 |         0 |       0 |
| netwerkdelen                            |   794 |       733 |     733 |
| RVZ-006 meldingen                       |  1062 |      1058 |    1058 |
| RVZ-006 deelstelsels                    |    99 |        96 |      96 |
| NET-001                                 |  8467 |      8543 |    8499 |
| NET-002                                 |  3031 |      3049 |    3046 |
| NET-006                                 |   329 |         - |     332 |
| NET-009                                 |  3656 |         - |    3667 |
| knopen in de graaf / beoordeeld         |     - |         - |   17514 / 17379 |
| strengen zonder afvoerpad               |     - |         - |   12654 |

De "vóór"-kolom komt uit `uitvoer/29082027-02/bevindingen.csv` (de koude herhaling van
`uitvoer/29082026_ext009_slotrun`); "voorspeld" is de monkeypatchmeting uit issue #105.
Dat NET-001 en NET-002 lager uitvallen dan voorspeld, komt doordat die monkeypatch
`_ZonderAfvoerpad._bouw_onbereikbaar` ongemoeid liet: die leidde het beginpunt nog met
`resolve_network_node` af en meldde daardoor elke streng die op een T-stuk begint
onvoorwaardelijk (44 + 3 vals-positieven, nagemeten met beide varianten). Zie BO-83.
Wijkt een uitkomst hiervan af, verklaar het verschil -- verzin er geen nieuwe waarheid
bij. NET-004, NET-005, NET-007 en NET-008 staan er niet omdat er iets van verwacht wordt,
maar omdat de graaf onder ze allemaal ligt: schuift een van die getallen, dan hoort dat
gezien te worden.

Twee getallen vragen om uitleg voor wie ze naast een check legt. Het verschil tussen de
17514 graafknopen en de 17379 beoordeelde zijn de 135 doorgeefhulpstukken; `examined()`
van NET-006 en NET-008 telt het tweede getal (BO-83). En de 12654 strengen zonder
afvoerpad zijn niet te vergelijken met de 8499 van NET-001: dit telt élke
vrijvervalstreng (9464 daarvan zijn vuilwater of gemengd) en `afvoerpaden` rekent op de
ZUIVERE vrijvervalgraaf, terwijl NET-001 de bereikbaarheidsgraaf leest -- 576 van deze
strengen bereiken langs het persnet wél een eindpunt. Dat is de scheiding van BO-54 en
staat los van dit issue.

Gebruik:  uv run python scripts/meet_hulpstukgraaf.py
"""

from __future__ import annotations

import time
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.checks.verbanden import (
    _netwerk,
    afvoerpad_van_streng,
    netwerkdelen,
    putknopen,
)

WORTEL = Path(__file__).resolve().parents[1]
DATASET = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
PROJECTCONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"

# RVZ-006 voorop: die deelt zijn deelstelsel-ID met NET-001 en NET-002. De overige
# NET-checks lezen dezelfde graaf en staan erbij als bewaking, niet als verwachting.
CHECKS = (
    "RVZ-006",
    "NET-001",
    "NET-002",
    "NET-004",
    "NET-005",
    "NET-006",
    "NET-007",
    "NET-008",
    "NET-009",
)


def main() -> int:
    """Laadt De Wolden en Hoogeveen en telt de graaf en de checks erop."""
    for pad in (DATASET, PROJECTCONFIG):
        if not pad.exists():
            print(f"overgeslagen: {pad} staat niet in data/")
            return 0

    config = load_check_config(PROJECTCONFIG)
    begin = time.perf_counter()
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    # Dezelfde voorbewerking als `toetsrun`: zonder de vulwaardemarkering leest NET-009
    # BOB's die de pijplijn juist wegstreept, en wijken de getallen af van een echte run.
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config)
    print(f"dataset geladen in {time.perf_counter() - begin:.1f} s")

    netwerk = _netwerk(context)
    zonder_pad = sum(
        1 for conduit in netwerk.conduits if afvoerpad_van_streng(context, conduit) is None
    )
    print(f"strengen in de netwerkanalyse : {len(netwerk.conduits)}")
    print(f"strengen buiten de analyse    : {len(netwerk.unconnected)}")
    print(f"knopen in de vrijvervalgraaf  : {netwerk.graph.number_of_nodes()}")
    print(f"beoordeelde knopen (putknopen): {len(putknopen(context, netwerk.graph))}")
    print(f"netwerkdelen                  : {len(netwerkdelen(context))}")
    # Een streng zonder `Afvoer` krijgt in de GeoPackage geen uitstroompunt en geen
    # padlengte. Dit getal hoort in de buurt van NET-001 te liggen (die telt alleen de
    # vuilwater- en gemengde strengen) en niet in de buurt van het aantal strengen.
    print(f"strengen zonder afvoerpad     : {zonder_pad}")

    for check_id in CHECKS:
        outcome = run_checks(context, [check_id]).outcomes[0]
        staart = ""
        if check_id == "RVZ-006":
            clusters = {bevinding.details.get("cluster_id") for bevinding in outcome.findings}
            staart = f" op {len(clusters)} deelstelsels"
        print(f"{check_id:<30}: {len(outcome.findings)}{staart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
