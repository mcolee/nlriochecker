"""Meet NET-006 op De Wolden en Hoogeveen door de echte pijplijn (issue #126, BO-87; #129, BO-92).

Onderbouwt de na-getallen van de koppelmatrix (BO-43: een getal in een BO krijgt een bewaard
meetscript). Draait NET-006 over de volledige OroX-dataset met de projectconfig
`configs/dewoldenhoogeveen.toml`, ná `markeer_vulwaarden` -- precies de stappen die
`toetsrun.py` vóór de checks zet, zodat het cijfer met een volle `toets`-run overeenkomt.

Sinds issue #129 meet dit script ook de VGS-voorwaarde (BO-92): het reproduceert NET-006
vóór (85, koppelregels mét `hemelwater → vuilwater`) en ná (107, zonder), het aantal knopen
met een betrouwbaar gerichte `hemelwater→vuilwater`-koppeling (24), daarvan de 2 die al een
NET-006-bevinding droegen (dus geen nieuwe rij -- NET-006 telt per knoop), en het aantal
VGS-instanties (0). Alles door dezelfde pijplijn, dus de +22 (85 → 107) is geen los scriptje.

Zwaar: een koude laadronde kost circa een halve minuut en piekt onder de 2 GB; start dit
script met `run_in_background`.

    uv run python scripts/meet_net006.py

Gemeten op codestand `fb6b586` (dev) -- de commit die de #129-checkwijziging (`[klassen] vgs`,
`_vgs_leden`, de conditie in `_bouw_koppelingen`) droeg; de fixronde-commit die dit uitgebreide
script draagt bouwt daarop voort (het scripteigen hash is pas ná committen bekend, zoals
`meet_stelsels.py` na #131). Dataset `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`. Bewaard
onder BO-43.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import GwswDataset, markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, run_checks

WORTEL = Path(__file__).resolve().parents[1]
DATASET = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
CONFIG = WORTEL / "configs" / "dewoldenhoogeveen.toml"

# De ene cel die issue #129 voorwaardelijk maakte (dezelfde tags als `checks/netwerk.py`).
_VGS_KOPPELING = "hemelwater→vuilwater"


def _net006(dataset: GwswDataset, config: CheckConfig) -> list:
    """Draait NET-006 met deze config en geeft de bevindingen terug."""
    context = CheckContext(dataset=dataset, config=config)
    return run_checks(context, ["NET-006"]).outcomes[0].findings


def _knoop_ids(findings: list) -> set[str]:
    """De object-URI's (knopen) waarop NET-006 aansloeg."""
    return {finding.object_uri for finding in findings}


def main() -> None:
    """Laadt de dataset en meet NET-006 na, plus de VGS-voorwaarde (voor/na, 24, 2, 0 VGS)."""
    config = load_check_config(CONFIG)
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )

    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["NET-006"]).outcomes[0]
    na = outcome.findings

    koppelingen: Counter[str] = Counter()
    for finding in na:
        for koppeling in finding.details.get("koppelingen", []):
            koppelingen[koppeling] += 1

    print(f"NET-006 bevindingen (na, whitelist): {len(na)}")
    print(f"NET-006 beoordeelde knopen (examined): {outcome.examined}")
    print("Overtreden gerichte koppelingen (aantal knoop-koppelingen):")
    for koppeling, aantal in koppelingen.most_common():
        print(f"  {koppeling}: {aantal}")
    print("Toelichting (wat niet beoordeeld is):")
    for note in outcome.notes:
        print(f"  - {note}")

    # Issue #129 / BO-92: de VGS-voorwaarde op de hemelwater->vuilwater-koppeling.
    # "Voor" is de stand vóór #129: `hemelwater` in de koppelregels mét `vuilwater`.
    voor_config = load_check_config(CONFIG)
    if "vuilwater" not in voor_config.koppelregels["hemelwater"]:
        voor_config.koppelregels["hemelwater"] = [
            *voor_config.koppelregels["hemelwater"],
            "vuilwater",
        ]
    voor = _net006(dataset, voor_config)

    hv_knopen = {
        finding.object_uri
        for finding in na
        if _VGS_KOPPELING in finding.details.get("koppelingen", [])
    }
    reeds_gemeld = hv_knopen & _knoop_ids(voor)
    # Dezelfde typesluiting als `_vgs_leden` in `checks/netwerk.py`: de VGS-instanties over
    # `[klassen] vgs` (rechtstreeks, want een VGS is een Systeem en geen Stelsel; BO-92).
    vgs_instanties = {
        str(subject)
        for wortel in config.klassen.vgs
        for subject in dataset.subjects_of_class(wortel)
    }

    print("--")
    print("Issue #129 / BO-92 (VGS-voorwaarde):")
    print(f"  NET-006 knopen voor (koppelregels mét hemelwater→vuilwater): {len(voor)}")
    print(f"  NET-006 knopen na  (zonder, VGS-voorwaardelijk):             {len(na)}")
    print(f"  netto nieuw: +{len(na) - len(voor)}")
    print(f"  knopen met een betrouwbaar gerichte hemelwater→vuilwater-koppeling: {len(hv_knopen)}")
    print(f"    waarvan al een NET-006-bevinding (geen nieuwe rij): {len(reeds_gemeld)}")
    print(f"  VGS-instanties in de dataset: {len(vgs_instanties)}")


if __name__ == "__main__":
    main()
