"""Meetstraat voor de UITVOERFASE op De Wolden en Hoogeveen (issue #149, BO-43).

Onderbouwt de voor/na-getallen van issue #149: de rapportkop (`_omvang_section` plus
`_afhankelijkheden_section`) en de meldingenstroom (`bouw_meldingenstroom`), plus de
gevectoriseerde xy-omzetting. De dataset, de externe bronnen en de SHACL-nulmeting worden
via de gewone toetspijplijn (`voer_toets_uit`, cache aan, geen bestanden) geladen, zodat de
gemeten `CheckRun` dezelfde is als in een echte gemeentebrede run.

Drie standen:

  meet                     één pijplijn; meet stroom en dan kop op dezelfde run/context
                           (de echte volgorde), schrijft twee `RESULTAAT`-regels
  gepaard  <n> --ref <pad> n x (referentie, experiment) OM EN OM in aparte processen;
                           vat stroom en kop apart samen met min/max en vingerafdruk
  xymicro  <n>             techniek-micro: n x A (4x `foutlocatie.x`/`.y` per melding,
                           zoals de vier schrijvers samen) vs B (één `get_coordinates`)

De `gepaard`-stand leunt NIET op een monkeypatch (net als `scripts/harnas.py`): referentie
en experiment zijn twee codestanden die om en om in aparte processen draaien. Het experiment
is de werkboom waarin dit script staat; de referentie is een tweede checkout (git worktree)
van de basiscommit, meegegeven met `--ref`. `uv run --project <ref-worktree>` draait dit
script met de nlriochecker-install van die worktree (de oude code); dit script leest zijn
paden altijd relatief aan de werkboom waarin het bestand zelf staat, dus beide processen
lezen dezelfde data en alleen de code verschilt.

Draai op de voorgrond met een ruime `timeout` en achter een `flock`, zodat er nooit twee
metingen tegelijk om dezelfde vier cores strijden:

    flock /tmp/nlrio-meting.lock \
        uv run python scripts/harnas_uitvoer.py gepaard 3 --ref <ref-worktree>

Eenduidig heet de uitslag als de traagste experiment-meting sneller is dan de snelste
referentie-meting; klopt de wijziging semantisch, dan zijn de vingerafdrukken van de
rapportkop en de meldingenstroom in beide standen gelijk (`gelijk_aan_A`). De xy-zijmap
telt niet mee in de vingerafdruk: de referentiecode kent hem niet, en dat de coordinaten
byte-gelijk blijven bewijst de bestandsvergelijking van bewijslast (2).

Zwaar: een cachetreffer maakt het laden seconden, maar elke pijplijn draait wel de volle
checkfase; `gepaard 3` is (1 warming-up + 3) x 2 = 8 pijplijnen. Voorgrond, want de
harness-watchdog kilt achtergrond-runs.

Basis: referentiecommit `97cd567` (dev, issue #148). Dataset-lader: `gwsw-orox-helpers`
0.2.2 (`voer_toets_uit` -> `laad_met_cache` + gebundelde ontologie). Dataset
`data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`, config `configs/dewoldenhoogeveen.toml`,
bronnen `data/gis_dewoldenhoogeveen`, de drie CFK-rapporten in `data/shacl_nulmeting`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import fields
from datetime import date
from pathlib import Path

import shapely

from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit
from nlriochecker.uitvoer.bevindingen import _afhankelijkheden_section, _omvang_section
from nlriochecker.uitvoer.melding import Melding, bouw_meldingenstroom

# Paden hangen aan de werkboom waarin dit bestand staat, niet aan de huidige werkmap: zo
# leest een referentieproces (via `--project <ref-worktree>`) toch de data van deze
# werkboom, en verschilt tussen de twee standen alleen de code.
WERKBOOM = Path(__file__).resolve().parents[1]
TTL = WERKBOOM / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
CONFIG = WERKBOOM / "configs" / "dewoldenhoogeveen.toml"
BRONNEN = WERKBOOM / "data" / "gis_dewoldenhoogeveen"
SHACL = tuple(
    WERKBOOM / "data" / "shacl_nulmeting" / naam
    for naam in (
        "gwsw_shacl_report_conformiteit_Hyd.csv",
        "gwsw_shacl_report_conformiteit_MdsPlan.csv",
        "gwsw_shacl_report_MdsProj.csv",
    )
)
RUN_DATUM = date(2026, 9, 6)


def _laad_run():  # type: ignore[no-untyped-def]
    """De gemeentebrede `CheckRun`, via de gewone pijplijn, zonder bestanden te schrijven."""
    with tempfile.TemporaryDirectory() as tmp:
        opdracht = Toetsopdracht(
            dataset_pad=TTL,
            uitvoermap=Path(tmp),
            shacl=SHACL,
            projectconfig=CONFIG,
            bronnen=BRONNEN,
            met_geopackage=False,
            met_csv=False,
            met_json=False,
            gebruik_cache=True,
        )
        uitslag = voer_toets_uit(opdracht)
    return uitslag.runs[0].run


def _kop_vingerafdruk(regels: list[str]) -> str:
    """sha256 over de rapportkop-regels."""
    return hashlib.sha256("\n".join(regels).encode()).hexdigest()


def _stroom_vingerafdruk(meldingen: list[Melding], feiten: dict, onderdrukking: object) -> str:
    """sha256 over de meldingen (velden), de feiten en de onderdrukking.

    De xy-zijmap telt niet mee: de referentiecode kent hem niet, en de bytegelijkheid van
    de coordinaten wordt door de bestandsvergelijking van bewijslast (2) bewezen. De
    veldnamen komen uit `fields(Melding)`, gelijk in beide standen.
    """
    namen = [veld.name for veld in fields(Melding)]
    rijen = []
    for melding in meldingen:
        rij = {naam: getattr(melding, naam) for naam in namen}
        punt = rij.pop("foutlocatie")
        rij["foutlocatie"] = None if punt is None else [punt.x, punt.y]
        rij["cfk"] = list(melding.cfk)
        rijen.append(json.dumps(rij, sort_keys=True, default=str))
    h = hashlib.sha256()
    h.update(json.dumps(sorted(rijen)).encode())
    h.update(json.dumps(feiten, sort_keys=True).encode())
    h.update(repr(onderdrukking).encode())
    return h.hexdigest()


def stand_meet() -> None:
    """Meet stroom en dan kop op dezelfde run/context; schrijf machineleesbare regels."""
    run = _laad_run()

    t0 = time.perf_counter()
    stroom = bouw_meldingenstroom(run, RUN_DATUM)
    dt_stroom = time.perf_counter() - t0
    sha_stroom = _stroom_vingerafdruk(stroom.meldingen, stroom.feiten, stroom.onderdrukking)

    t1 = time.perf_counter()
    regels = _omvang_section(run) + _afhankelijkheden_section(run)
    dt_kop = time.perf_counter() - t1
    sha_kop = _kop_vingerafdruk(regels)

    print(f"RESULTAAT stroom {dt_stroom:.4f} {sha_stroom}", flush=True)
    print(f"RESULTAAT kop {dt_kop:.4f} {sha_kop}", flush=True)


def _meet_proces(python_project: Path | None) -> dict[str, tuple[float, str]]:
    """Draait één `meet` als apart proces en leest de tijden en vingerafdrukken terug."""
    argv = ["uv", "run"]
    if python_project is not None:
        argv += ["--project", str(python_project)]
    argv += ["python", str(Path(__file__).resolve()), "meet"]
    uitvoer = subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    gevonden: dict[str, tuple[float, str]] = {}
    for regel in uitvoer.splitlines():
        if regel.startswith("RESULTAAT "):
            _, fase, dt, sha = regel.split()
            gevonden[fase] = (float(dt), sha)
    if {"stroom", "kop"} - set(gevonden):
        raise SystemExit(f"onvolledige RESULTAAT-uitvoer van {argv}:\n{uitvoer}")
    return gevonden


def stand_gepaard(n: int, ref: Path) -> None:
    """n x (referentie, experiment) om en om in aparte processen; vat de uitslag samen."""
    print(f"referentie-worktree: {ref}", flush=True)
    _meet_proces(ref)  # warming-up: OS-paginacache en leeslaagpickle warm
    _meet_proces(None)
    metingen: list[tuple[str, dict[str, tuple[float, str]]]] = []
    for i in range(n):
        for naam, project in (("ref", ref), ("exp", None)):
            gevonden = _meet_proces(project)
            metingen.append((naam, gevonden))
            print(
                f"[{i}] {naam}: stroom {gevonden['stroom'][0]:.2f} s "
                f"kop {gevonden['kop'][0]:.2f} s",
                flush=True,
            )
    for fase in ("kop", "stroom"):
        ref_tijden = [g[fase][0] for naam, g in metingen if naam == "ref"]
        exp_tijden = [g[fase][0] for naam, g in metingen if naam == "exp"]
        ref_fps = {g[fase][1] for naam, g in metingen if naam == "ref"}
        exp_fps = {g[fase][1] for naam, g in metingen if naam == "exp"}
        eenduidig = max(exp_tijden) < min(ref_tijden)
        print(
            f"\n[{fase}] ref: min {min(ref_tijden):.2f} max {max(ref_tijden):.2f}  "
            f"exp: min {min(exp_tijden):.2f} max {max(exp_tijden):.2f}"
        )
        print(f"[{fase}] eenduidig (traagste exp < snelste ref): {eenduidig}")
        print(f"[{fase}] gelijk_aan_A (vingerafdruk ref == exp): {ref_fps == exp_fps}")


def stand_xymicro(n: int) -> None:
    """Techniek-micro: 4x `foutlocatie.x`/`.y` per melding vs één `get_coordinates`."""
    run = _laad_run()
    meldingen = bouw_meldingenstroom(run, RUN_DATUM).meldingen
    punten = [m.foutlocatie for m in meldingen if m.foutlocatie is not None]
    print(f"{len(punten)} punten van {len(meldingen)} meldingen", flush=True)

    def a() -> list:
        # Zoals de vier schrijvers samen: elk las `foutlocatie.x`/`.y` per melding.
        uit = None
        for _ in range(4):
            uit = [(p.x, p.y) for p in punten]
        return uit

    def b() -> list:
        coords = shapely.get_coordinates(punten)
        return [(float(x), float(y)) for x, y in coords.tolist()]

    ra = rb = None
    for ronde in range(n):
        t = time.perf_counter()
        ra = a()
        ta = time.perf_counter() - t
        t = time.perf_counter()
        rb = b()
        tb = time.perf_counter() - t
        print(
            f"ronde {ronde + 1}: A(4x .x/.y) {ta:.3f} s  B(get_coordinates 1x) {tb:.3f} s  "
            f"ratio {ta / tb:.0f}x",
            flush=True,
        )
    print(f"uitkomst gelijk: {ra == rb} ({len(ra) if ra else 0} punten)", flush=True)


def main() -> None:
    """Leest de stand van de opdrachtregel."""
    parser = argparse.ArgumentParser(description="Meetstraat voor de uitvoerfase (issue #149).")
    sub = parser.add_subparsers(dest="stand", required=True)

    sub.add_parser("meet", help="één pijplijn; schrijft RESULTAAT-regels voor stroom en kop")

    p_gepaard = sub.add_parser("gepaard", help="n x (ref, exp) om en om in aparte processen")
    p_gepaard.add_argument("n", type=int)
    p_gepaard.add_argument("--ref", type=Path, required=True, help="worktree van de basiscommit")

    p_xymicro = sub.add_parser("xymicro", help="techniek-micro voor de xy-omzetting")
    p_xymicro.add_argument("n", type=int)

    args = parser.parse_args()
    if args.stand == "meet":
        stand_meet()
    elif args.stand == "gepaard":
        stand_gepaard(args.n, args.ref.resolve())
    elif args.stand == "xymicro":
        stand_xymicro(args.n)


if __name__ == "__main__":
    sys.exit(main())
