"""Meetstraat voor de checkfase op De Wolden en Hoogeveen (perf-issues, BO-43).

Onderbouwt de voor/na-getallen van een performance-wijziging aan de checks. Laadt de
dataset via de leeslaagcache en de externe bronnen zoals `toetsrun` dat doet, bouwt per
iteratie een verse `CheckContext` (lege cache) -- precies de checkfase van een run zonder
studiegebied en zonder nulmeting -- en meet `run_checks`. Drie standen:

  meet     [checks...]              één run_checks; schrijft `RESULTAAT <seconden> <sha256>`
  gepaard  <n> --ref <pad> [checks] n x (referentie, experiment) OM EN OM in aparte
                                    processen; vat samen met min/max en vingerafdruk
  profiel  <naam> [checks...]       cProfile over run_checks + tijd per check

De `gepaard`-stand leunt NIET op een monkeypatch: referentie en experiment zijn twee
codestanden die om en om in aparte processen draaien. Het experiment is de werkboom waarin
dit script staat; de referentie is een tweede checkout (git worktree) van de basiscommit,
meegegeven met `--ref`. Elke meting is een eigen `meet`-proces:

    referentie: uv run --project <ref-worktree> python <dit script> meet <checks>
    experiment: uv run                          python <dit script> meet <checks>

`uv run --project <ref-worktree>` draait dit script met de nlriochecker-install van die
worktree (de oude code); dit script leest zijn dataset- en bronpaden altijd relatief aan de
werkboom waarin het bestand zelf staat, dus beide processen lezen dezelfde data en alleen de
code verschilt. Zo hoeft de basiscommit dit script niet te kennen.

Draai `gepaard` op de voorgrond met een ruime `timeout` en achter een `flock`, zodat er
nooit twee metingen tegelijk om dezelfde vier cores strijden:

    flock /tmp/nlrio-meting.lock \
        uv run python scripts/harnas.py gepaard 3 --ref <ref-worktree> HGT-001 HGT-002 HGT-003

Eenduidig heet de uitslag als de traagste experiment-meting sneller is dan de snelste
referentie-meting; klopt de wijziging semantisch, dan zijn de vingerafdrukken van beide
standen gelijk.

Zwaar: een koude laadronde kost circa een halve minuut en piekt onder de 2 GB; met een
cachetreffer is het laden seconden. De harness-watchdog kilt achtergrond-runs op deze
machine, dus voorgrond.

Gemeten op codestand `3e40740` (dev) als basis -- de commit die dit script draagt bouwt
daarop voort (issue #143). Dataset-lader: `gwsw-orox-helpers` 0.2.2 (`laad_met_cache` +
gebundelde ontologie, ontologiekeuze `None` zoals `toetsrun._ontologiekeuze` zonder vlag).
Dataset `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`, config
`configs/dewoldenhoogeveen.toml`, bronnen `data/gis_dewoldenhoogeveen`.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import REGISTRY, CheckContext, CheckRun, run_checks
from nlriochecker.externedata import Dekkingseis, ExternalData, load_external_data
from nlriochecker.plausibiliteit import load_plausibility

# Data- en configpaden hangen aan de werkboom waarin dit bestand staat, niet aan de
# huidige werkmap: zo leest een referentieproces dat via `--project <ref-worktree>` draait
# toch de data van deze werkboom, en verschilt tussen de twee standen alleen de code.
WERKBOOM = Path(__file__).resolve().parents[1]
TTL = WERKBOOM / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
CONFIG = WERKBOOM / "configs" / "dewoldenhoogeveen.toml"
BRONNEN = WERKBOOM / "data" / "gis_dewoldenhoogeveen"

tijden: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))


def laad() -> tuple[object, object, ExternalData]:
    """Dataset (cache), config en bronnen -- eenmalig per proces, zoals `toetsrun`."""
    t0 = time.perf_counter()
    config = load_check_config(CONFIG)
    bronnen_cfg = config.bronnen.model_copy(update={"map": "."})
    eis = Dekkingseis(
        marge_m=config.drempels.ext_zoekafstand_max_m,
        tolerantie_m=config.bronnen.dekking_tolerantie_m,
    )
    bronnen = load_external_data(bronnen_cfg, BRONNEN, dekkingseis=eis)
    t1 = time.perf_counter()
    dataset, cache = laad_met_cache(TTL, None, None, True, fallback_encoding=FALLBACK_ENCODING)
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    t2 = time.perf_counter()
    print(
        f"[laad] bronnen {t1 - t0:.1f} s, dataset ({cache.bron}) {t2 - t1:.1f} s; "
        f"{len(dataset.nodes)} knopen, {len(dataset.conduits)} strengen",
        flush=True,
    )
    return dataset, config, bronnen


def verse_context(dataset: object, config: object, bronnen: ExternalData) -> CheckContext:
    """Een context met lege cache, zoals de checkfase hem zonder studiegebied bouwt."""
    return CheckContext(
        dataset=dataset,  # type: ignore[arg-type]
        config=config,  # type: ignore[arg-type]
        bronnen=bronnen,
        plausibiliteit=load_plausibility(None),
    )


def vingerafdruk(run: CheckRun) -> str:
    """sha256 over alle bevindingen + examined + notes, volgorde-onafhankelijk per check."""
    h = hashlib.sha256()
    for outcome in run.outcomes:
        rijen = sorted(
            json.dumps(
                [
                    f.check_id,
                    f.object_uri,
                    f.message,
                    sorted((k, repr(v)) for k, v in f.details.items()),
                    f.location,
                    f.systemisch,
                    f.typing_reliable,
                ],
                sort_keys=True,
            )
            for f in outcome.findings
        )
        h.update(json.dumps([outcome.check_id, outcome.examined, outcome.notes, rijen]).encode())
    return h.hexdigest()


def stand_meet(checks: list[str] | None) -> None:
    """Meet één run_checks en schrijf een machineleesbare `RESULTAAT`-regel."""
    dataset, config, bronnen = laad()
    context = verse_context(dataset, config, bronnen)
    t0 = time.perf_counter()
    run = run_checks(context, checks)
    dt = time.perf_counter() - t0
    print(f"RESULTAAT {dt:.4f} {vingerafdruk(run)}", flush=True)


def _meet_proces(python_project: Path | None, checks: list[str] | None) -> tuple[float, str]:
    """Draait één `meet` als apart proces en leest de tijd en de vingerafdruk terug.

    `python_project` is de projectmap van de referentie-worktree, of None voor de
    huidige werkboom (het experiment).
    """
    argv = ["uv", "run"]
    if python_project is not None:
        argv += ["--project", str(python_project)]
    argv += ["python", str(Path(__file__).resolve()), "meet", *(checks or [])]
    uitvoer = subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    for regel in uitvoer.splitlines():
        if regel.startswith("RESULTAAT "):
            _, dt, sha = regel.split()
            return float(dt), sha
    raise SystemExit(f"geen RESULTAAT-regel in de uitvoer van {argv}:\n{uitvoer}")


def stand_gepaard(n: int, ref: Path, checks: list[str] | None) -> None:
    """n x (referentie, experiment) om en om in aparte processen; vat de uitslag samen."""
    print(f"referentie-worktree: {ref}", flush=True)
    # Warming-up: één keer elke stand, zodat de OS-paginacache van het raster en de
    # leeslaagpickle warm zijn voordat er gemeten wordt.
    _meet_proces(ref, checks)
    _meet_proces(None, checks)
    metingen: list[tuple[str, float, str]] = []
    for i in range(n):
        for naam, project in (("ref", ref), ("exp", None)):
            dt, sha = _meet_proces(project, checks)
            metingen.append((naam, dt, sha))
            print(f"[{i}] {naam}: {dt:.2f} s  sha256 {sha[:16]}", flush=True)
    ref_tijden = [dt for naam, dt, _ in metingen if naam == "ref"]
    exp_tijden = [dt for naam, dt, _ in metingen if naam == "exp"]
    fps = {naam: {sha for n2, _, sha in metingen if n2 == naam} for naam in ("ref", "exp")}
    print(
        f"\nref: min {min(ref_tijden):.2f} max {max(ref_tijden):.2f}  "
        f"exp: min {min(exp_tijden):.2f} max {max(exp_tijden):.2f}"
    )
    print(f"eenduidig (traagste exp < snelste ref): {max(exp_tijden) < min(ref_tijden)}")
    print(f"vingerafdrukken ref {fps['ref']}  exp {fps['exp']}  gelijk: {fps['ref'] == fps['exp']}")


def _wikkel_tijden() -> None:
    """Timer per check-id om run/examined/notes voor de profielstand."""
    for check_id in sorted(REGISTRY):
        cls = REGISTRY[check_id]
        for methode in ("run", "examined", "notes"):
            origineel = getattr(cls, methode)

            def maak(orig, cid=check_id, m=methode):  # type: ignore[no-untyped-def]
                def getimed(self, context):  # type: ignore[no-untyped-def]
                    t = time.perf_counter()
                    resultaat = orig(self, context)
                    if m == "run":
                        resultaat = list(resultaat)
                    tijden[cid][m] += time.perf_counter() - t
                    return resultaat

                return getimed

            setattr(cls, methode, maak(origineel))


def stand_profiel(naam: str, checks: list[str] | None) -> None:
    """cProfile over run_checks plus de tijd per check; schrijft `<naam>.prof`."""
    dataset, config, bronnen = laad()
    _wikkel_tijden()
    context = verse_context(dataset, config, bronnen)
    prof = cProfile.Profile()
    t0 = time.perf_counter()
    prof.enable()
    run = run_checks(context, checks)
    prof.disable()
    wand = time.perf_counter() - t0
    prof.dump_stats(f"{naam}.prof")
    print(f"\nCHECKFASE (cProfile aan): {wand:.1f} s; vingerafdruk {vingerafdruk(run)[:16]}\n")
    print(f"{'check':<12} {'run':>9} {'examined':>9} {'notes':>9} {'totaal':>9}")
    rijen = [
        (cid, m.get("run", 0.0), m.get("examined", 0.0), m.get("notes", 0.0))
        for cid, m in tijden.items()
    ]
    for cid, r, e, no in sorted(rijen, key=lambda x: x[1] + x[2] + x[3], reverse=True):
        if r + e + no >= 0.05:
            print(f"{cid:<12} {r:>9.2f} {e:>9.2f} {no:>9.2f} {r + e + no:>9.2f}")
    print(f"\nSom per-check-totalen: {sum(r + e + no for _, r, e, no in rijen):.1f} s\n")
    stats = pstats.Stats(f"{naam}.prof")
    stats.sort_stats("tottime").print_stats(30)


def _checks(argv: list[str]) -> list[str] | None:
    """Een lege lijst betekent: alle geregistreerde checks."""
    return argv or None


def main() -> None:
    """Leest de stand en de checks van de opdrachtregel."""
    parser = argparse.ArgumentParser(description="Meetstraat voor de checkfase.")
    sub = parser.add_subparsers(dest="stand", required=True)

    p_meet = sub.add_parser("meet", help="één run_checks; schrijft een RESULTAAT-regel")
    p_meet.add_argument("checks", nargs="*")

    p_gepaard = sub.add_parser("gepaard", help="n x (ref, exp) om en om in aparte processen")
    p_gepaard.add_argument("n", type=int)
    p_gepaard.add_argument("--ref", type=Path, required=True, help="worktree van de basiscommit")
    p_gepaard.add_argument("checks", nargs="*")

    p_profiel = sub.add_parser("profiel", help="cProfile over run_checks")
    p_profiel.add_argument("naam")
    p_profiel.add_argument("checks", nargs="*")

    args = parser.parse_args()
    if args.stand == "meet":
        stand_meet(_checks(args.checks))
    elif args.stand == "gepaard":
        stand_gepaard(args.n, args.ref.resolve(), _checks(args.checks))
    elif args.stand == "profiel":
        stand_profiel(args.naam, _checks(args.checks))


if __name__ == "__main__":
    sys.exit(main())
