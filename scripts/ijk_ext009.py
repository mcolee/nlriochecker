#!/usr/bin/env python
"""IJkt de EXT-009-drempel op de validatieset en telt de gemeente door (BO-81).

Wat dit script doet, en waarom het onder `scripts/` staat en niet in een scratchpad
(BO-43): het onderbouwt twee getallen die in de beslislog en in `checks.toml` staan --
de gekozen waarde van `ext_wegvak_streng_in_cel`, en de gemeentebrede telling
rood/groen/grijs waarmee een volgende run zich kan vergelijken.

De validatieset zijn 485 handmatig beoordeelde straten uit de POC van issue #104. Zij
staat als kolom `y` op `WVK_ID` in `uitvoer/poc_straten_scoring_final.gpkg` (1 = bediend,
0 = leeg) en blijft bewust buiten de repository: te groot, en zij hoort bij deze ene
dataset. Staat dat bestand er niet, dan slaat het script de ijking over en telt het
alleen de gemeente; ontbreekt de dataset of de bronmap, dan slaat het helemaal over.

De fouttabel telt op de **beoordeelde** straten: de grijze (onverhard of drukriolering)
vallen erbuiten, want daar doet de regel met opzet geen uitspraak. Twee soorten fout,
en ze wegen niet gelijk. Een *vals-rood* is een bediende straat die als leeg gemeld
wordt: hinderlijk, maar de lezer ziet het meteen op de kaart. Een *gemiste* is een lege
straat die groen blijft: die verdwijnt uit beeld, en dat is precies het gat dat deze
check moet vinden. De keuze valt daarom op de drempel met de minste fouten waarbij
vals-rood minstens zo groot is als gemist.

Gebruik:  uv run python scripts/ijk_ext009.py
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.wegvakken import (
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ROOD,
    _riool,
    bouw_vlakken,
    classificeer,
    kies_kandidaten,
    meet_kenmerken,
)
from nlriochecker.externedata import load_external_data

WORTEL = Path(__file__).resolve().parents[1]
DATASET = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
BRONMAP = WORTEL / "data" / "gis_dewoldenhoogeveen"
PROJECTCONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"
VALIDATIESET = WORTEL / "uitvoer" / "poc_straten_scoring_final.gpkg"
VALIDATIELAAG = "scoring"

# De kandidaat-drempels. De POC draaide op 0,25; de reeks eromheen is fijn genoeg om de
# knik te zien en grof genoeg om een tabel te blijven.
KANDIDATEN = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.75]


def _labels() -> dict[str, int]:
    """De handmatige labels per WVK_ID, of leeg als de validatieset er niet is."""
    if not VALIDATIESET.exists():
        return {}
    verbinding = sqlite3.connect(f"file:{VALIDATIESET}?mode=ro", uri=True)
    try:
        rijen = verbinding.execute(
            f'select "WVK_ID", "y" from "{VALIDATIELAAG}" where "y" is not null'
        )
        return {str(int(wvk)): int(y) for wvk, y in rijen}
    finally:
        verbinding.close()


def main() -> int:
    """Meet de kenmerken op De Wolden en Hoogeveen en rapporteert de ijking."""
    for pad in (DATASET, BRONMAP, PROJECTCONFIG):
        if not pad.exists():
            print(f"overgeslagen: {pad} staat niet in data/")
            return 0

    config = load_check_config(PROJECTCONFIG)
    # Alleen de drie lagen die EXT-009 leest; de panden, waterdelen en het AHN kosten
    # minuten en veranderen niets aan deze meting. Zonder dekkingseis, om dezelfde reden.
    bronnen = load_external_data(
        config.bronnen.model_copy(
            update={
                "map": ".",
                "bag_pand": None,
                "ahn_dtm": None,
                "bgt_pandlagen": [],
                "bgt_waterlagen": [],
                "bgt_putdeksellagen": [],
                "bgt_overige_bouwwerklagen": [],
            }
        ),
        BRONMAP,
    )

    begin = time.perf_counter()
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)
    print(f"dataset geladen in {time.perf_counter() - begin:.1f} s")

    drempels = config.drempels
    nwb = bronnen.layer("nwb_wegvak")
    kom = bronnen.layer("top10nl_kom")
    wegdeel = bronnen.layer("bgt_wegdeel")
    if nwb is None or kom is None or wegdeel is None:
        print("overgeslagen: een van de drie EXT-009-bronnen ontbreekt")
        return 0

    tijden: dict[str, float] = {}
    klok = time.perf_counter()
    kandidaten = kies_kandidaten(nwb, kom, drempels)
    tijden["kandidaatselectie"] = time.perf_counter() - klok

    klok = time.perf_counter()
    vlakken = bouw_vlakken(kandidaten, drempels)
    tijden["voronoi-partitie"] = time.perf_counter() - klok

    klok = time.perf_counter()
    riool = _riool(context)
    tijden["rioolselectie"] = time.perf_counter() - klok

    klok = time.perf_counter()
    kenmerken = meet_kenmerken(kandidaten, vlakken, riool, wegdeel, drempels)
    tijden["kenmerken"] = time.perf_counter() - klok

    print(f"\nwegvakken {len(nwb)}, kandidaten {len(kandidaten)}")
    print("afgevallen: " + "; ".join(f"{a} {r}" for r, a in kandidaten.afgevallen.items()))
    print("\ntijd per stap (s):")
    for naam, duur in tijden.items():
        print(f"  {naam:20s} {duur:7.2f}")
    print(f"  {'totaal':20s} {sum(tijden.values()):7.2f}")

    labels = _labels()
    if labels:
        _fouttabel(kandidaten, kenmerken, drempels, labels)
    else:
        print(f"\nijking overgeslagen: {VALIDATIESET} staat niet in uitvoer/")

    _telling(kandidaten, kenmerken, drempels)
    return 0


def _fouttabel(kandidaten, kenmerken, drempels, labels: dict[str, int]) -> None:
    """De fouttabel per kandidaat-drempel, op de beoordeelde gelabelde straten."""
    sleutels = [sleutel.rsplit("/", 1)[-1] for sleutel in kandidaten.sleutels]
    gelabeld = [(positie, labels[wvk]) for positie, wvk in enumerate(sleutels) if wvk in labels]
    print(f"\nvalidatieset: {len(labels)} labels, waarvan {len(gelabeld)} onder de kandidaten")
    print("\ndrempel  beoordeeld  vals-rood  gemist  fouten  juist%")
    for waarde in KANDIDATEN:
        uitslag = classificeer(
            kenmerken, drempels.model_copy(update={"ext_wegvak_streng_in_cel": waarde})
        )
        beoordeeld = [(p, y) for p, y in gelabeld if uitslag[p][0] != STATUS_GRIJS]
        vals_rood = sum(1 for p, y in beoordeeld if y == 1 and uitslag[p][0] == STATUS_ROOD)
        gemist = sum(1 for p, y in beoordeeld if y == 0 and uitslag[p][0] == STATUS_GROEN)
        fouten = vals_rood + gemist
        juist = 100 * (len(beoordeeld) - fouten) / len(beoordeeld) if beoordeeld else 0.0
        print(
            f"{waarde:7.2f}  {len(beoordeeld):10d}  {vals_rood:9d}  {gemist:6d}  "
            f"{fouten:6d}  {juist:5.1f}"
        )

    # Wat de grijze uitzondering kost: elke lege straat die grijs wordt is een gat dat de
    # check niet meldt. Dat getal hoort erbij -- zonder die regel leest "beoordeeld" als
    # de hele populatie.
    uitslag = classificeer(kenmerken, drempels)
    grijs = [(p, y) for p, y in gelabeld if uitslag[p][0] == STATUS_GRIJS]
    leeg = sum(1 for _, y in grijs if y == 0)
    print(
        f"\nniet beoordeeld bij drempel {drempels.ext_wegvak_streng_in_cel:g}: "
        f"{len(grijs)} van de {len(gelabeld)} gelabelde straten, waarvan {leeg} leeg en "
        f"{len(grijs) - leeg} bediend"
    )


def _telling(kandidaten, kenmerken, drempels) -> None:
    """De gemeentebrede telling bij de geconfigureerde drempel."""
    uitslag = classificeer(kenmerken, drempels)
    per_status = {STATUS_ROOD: 0, STATUS_GROEN: 0, STATUS_GRIJS: 0}
    per_reden: dict[str, int] = {}
    for status, reden in uitslag:
        per_status[status] += 1
        if reden:
            per_reden[reden] = per_reden.get(reden, 0) + 1
    print(f"\ngemeentebreed bij drempel {drempels.ext_wegvak_streng_in_cel:g}:")
    for status, aantal in per_status.items():
        print(f"  {status:6s} {aantal:5d}")
    for reden, aantal in per_reden.items():
        print(f"  grijs door {reden}: {aantal}")


if __name__ == "__main__":
    raise SystemExit(main())
