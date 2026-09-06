"""Meet het geheugengebruik van `uitvoer.herkomst.schrijf_json` (issue #148, BO-43).

De oude schrijver bouwde één JSON-string van de hele meldingenlijst (op De Wolden ~122 MB)
en gaf die aan `write_text`; de piek daarvan is een groot deel van de `ru_maxrss` van de
hele toetsrun. De nieuwe schrijver streamt de meldingen blok voor blok naar een tmp-bestand
en hernoemt het atomair. Dit script meet beide gepaard, in één proces:

* de pijplijn draait één keer (cache aan), daarna schrijft elk experiment de oude variant (A,
  hier ingebed zoals d42c90a hem had) en de nieuwe (B, `herkomst.schrijf_json` uit `src/`) om
  en om, `n` keer;
* per aanroep: de `tracemalloc`-piek en de sha256 van het bestand -- de sha bewijst dat de
  twee byte-voor-byte hetzelfde bestand opleveren.

De `ru_maxrss`-winst van de héle run meet je apart, met `/usr/bin/time -v` om een volle
`nlriochecker toets` heen (zie het rapport bij issue #148); dat kan dit script niet, want het
schrijft alleen de JSON opnieuw binnen één al warme proces.

    uv run python scripts/meet_uitvoer_geheugen.py <n>

De datasetpaden staan hieronder vast op De Wolden; pas ze aan voor een ander corpus.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tracemalloc
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TTL = REPO / "data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"
CONFIG = REPO / "configs/dewoldenhoogeveen.toml"
BRONNEN = REPO / "data/gis_dewoldenhoogeveen"
SHACL = (
    REPO / "data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv",
    REPO / "data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv",
    REPO / "data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv",
)
RUN_DATUM = date(2026, 9, 6)
BLOK = 5000


def _envelop(meldingen, **kw) -> dict:
    """Bouwt de enveloppedict, identiek aan `herkomst.schrijf_json`, zonder `meldingen`."""
    from nlriochecker.uitvoer.herkomst import SCHEMA_VERSIE, gereedschap

    document: dict[str, object] = {
        "schema_versie": SCHEMA_VERSIE,
        "gereedschap": gereedschap(),
        "run_datum": kw["run_datum"].isoformat(),
        "dataset": kw["dataset"],
    }
    if kw.get("gebieden") is not None:
        document["gebied"] = None
        document["gebieden"] = list(kw["gebieden"])
    elif kw.get("gebied") is not None:
        document["gebied"] = kw["gebied"]
    document |= {
        "cfk_set": list(kw["cfk_set"]),
        "volledig": kw["volledig"],
        "typeringspoort_toegepast": kw["typeringspoort_toegepast"],
    }
    onderdrukking = kw.get("onderdrukking")
    if onderdrukking is not None and onderdrukking.actief:
        document["onderdrukt"] = {
            "klassen": list(onderdrukking.klassen),
            "checks": list(onderdrukking.checks),
            "meldingen": onderdrukking.totaal,
        }
    uitzonderingen = kw.get("uitzonderingen")
    if uitzonderingen is not None and uitzonderingen.actief:
        document["uitzonderingen"] = {
            "bestand": uitzonderingen.bestand,
            "geaccepteerd": list(uitzonderingen.geaccepteerd),
            "zonder_bevinding": list(uitzonderingen.zonder_bevinding),
            "gewijzigde_waarde": [
                {"melding_id": g.melding_id, "snapshot": g.snapshot, "waarde": g.waarde}
                for g in uitzonderingen.gewijzigde_waarde
            ],
        }
    if kw.get("markering"):
        document["markering"] = kw["markering"]
    if kw.get("checks") is not None:
        document["checks"] = kw["checks"]
    document["aantal_meldingen"] = len(meldingen)
    return document


def schrijf_json_oud(pad: Path, meldingen, **kw) -> Path:
    """De schrijver zoals d42c90a hem had: één string van de hele lijst, dan `write_text`."""
    document = _envelop(meldingen, **kw)
    document["meldingen"] = sorted(meldingen, key=lambda rij: str(rij["melding_id"]))
    tekst = json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    pad.write_text(tekst + "\n", encoding="utf-8")
    return pad


def sha(pad: Path) -> str:
    return hashlib.sha256(pad.read_bytes()).hexdigest()[:16]


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    hier = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "uitvoer" / "_meet_issue148"
    hier.mkdir(parents=True, exist_ok=True)

    from nlriochecker.uitvoer import herkomst
    from nlriochecker.uitvoer.bevindingen import checks_json, meldingen_json
    from nlriochecker.uitvoer.melding import bouw_meldingenstroom
    from nlriochecker.uitvoer.voorbehoud import markering

    commit = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    print(f"[meet] repo-commit {commit}", flush=True)

    from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit

    opdracht = Toetsopdracht(
        dataset_pad=TTL,
        uitvoermap=hier / "basis",
        projectconfig=CONFIG,
        bronnen=BRONNEN,
        shacl=SHACL,
        met_geopackage=False,
        met_csv=False,
        met_json=False,
        gebruik_cache=True,
    )
    uitslag = voer_toets_uit(opdracht)
    run = uitslag.runs[0].run
    stroom = bouw_meldingenstroom(run, RUN_DATUM)
    rijen = meldingen_json(stroom.meldingen)
    print(f"[meet] pijplijn klaar, {len(rijen)} meldingen", flush=True)

    kw = dict(
        run_datum=RUN_DATUM,
        dataset=run.dataset.source.name,
        cfk_set=list(run.meetbereik.gekozen),
        volledig=run.meetbereik.volledig,
        typeringspoort_toegepast=run.typing_gate_applied,
        markering=markering(run),
        gebied=None,
        onderdrukking=stroom.onderdrukking,
        uitzonderingen=stroom.uitzonderingen,
        checks=checks_json(run),
    )
    varianten = {
        "A_oud": lambda pad: schrijf_json_oud(pad, rijen, **kw),
        "B_nieuw": lambda pad: herkomst.schrijf_json(pad, rijen, **kw),
    }

    for ronde in range(n):
        for naam, fn in varianten.items():
            pad = hier / f"bevindingen_{naam}.json"
            tracemalloc.start()
            tracemalloc.reset_peak()
            fn(pad)
            piek = tracemalloc.get_traced_memory()[1] / 2**20
            tracemalloc.stop()
            r = {
                "ronde": ronde + 1,
                "variant": naam,
                "tracemalloc_piek_mib": round(piek),
                "sha": sha(pad),
                "bytes": pad.stat().st_size,
            }
            print(f"[meet] {json.dumps(r)}", flush=True)


if __name__ == "__main__":
    main()
