"""Meetstraat voor de AHN-bemonstering: rasterindeling x leesstrategie, koud en warm (#168).

Onderbouwt het meetverslag van issue #168 (BO-43): welke bestandsindeling van het AHN6-DTM
(strips, tiles van 256/512/1024, DEFLATE/ZSTD/LZW met PREDICTOR=3) en welke leesstrategie
(`sample_many` zoals hij is, sortering per tegel, grotere GDAL-blokcache, eigen vensterlezer)
de kleinste koude en warme leestijd geven -- met de harde eis dat elke variant per positie
bit-gelijk aan de referentie is. Vier standen:

  punten                        de meetpunten (de `monstertabel`-selectie van HGT-001 op
                                De Wolden en Hoogeveen) eenmalig naar `punten.npy`
  bouw <nr>                     variant <nr> met gdal_translate uit het origineel; schrijft
                                `BOUW <nr> <pad> <seconden> <bytes>`
  meet <tif> <L0|L1|L3> [...]   één bemonstering in dit proces; schrijft
                                `RESULTAAT <seconden> <sha256> resident=<fractie> ...`
  gepaard <n> <tif> <L> [...]   n x (referentie, experiment) OM EN OM in aparte processen,
                                koud (`--koud`) of warm; vat samen en logt naar `resultaten.csv`

De referentie is altijd het origineel (strips van 1 rij) met L0, de huidige
`RasterSampler.sample_many`. Het experiment is `<tif>` met strategie `<L>`:

  L0  `sample_many` zoals hij in `src/` staat: één `reader.sample` in selectievolgorde
  L1  dezelfde `reader.sample`, maar de punten vooraf gesorteerd op tegel
      (`rij // blockysize, kolom // blockxsize` uit `reader.block_shapes`), uitkomst via de
      inverse permutatie terug in selectievolgorde
  L3  eigen vensterlezer: per geraakte tegel één `reader.read(window=...)` en de punten
      daaruit indexeren; dezelfde `rowcol`-afronding (floor) en dezelfde buiten-raster-
      afhandeling als rasterio's `sample_gen`
  L2 uit het issue is geen aparte strategie maar de vlag `--cachemax <MB>` (GDAL_CACHEMAX
  via `rasterio.Env`) op L0 of L1.

Elke meting is een eigen proces, zodat de GDAL-blokcache per meting leeg begint. Koud
betekent: vlak vóór de meting de OS-paginacache van beide bestanden legen met
`posix_fadvise(POSIX_FADV_DONTNEED)` (stdlib, geen root); het meetproces meldt de nog
residente fractie van het bestand (`mincore` via ctypes) zodat de koude toestand
controleerbaar is. Warm betekent: vlak vóór elke meting hetzelfde bestand met dezelfde
strategie één keer in een wegwerpproces doorlopen, zodat de geraakte pagina's in de
paginacache staan; met twee bestanden van 9,6 GB om en om past niet alles tegelijk in 16 GB,
vandaar per meting een eigen opwarmer in plaats van één opwarmronde vooraf.

Draai `gepaard` achter een `flock`, zodat er nooit twee metingen tegelijk om de schijf en de
vier cores strijden; een koude ronde overschrijdt de voorgrond-timeout, dus in de achtergrond:

    flock /tmp/nlrio-meting.lock uv run python scripts/meet_raster_bemonstering.py \\
        gepaard 3 data/gis_dewoldenhoogeveen/AHN6_v2_tiles512.tif L1 --koud

Eenduidig heet de uitslag als de traagste experiment-meting sneller is dan de snelste
referentie-meting (of andersom); bit-gelijk als `np.array_equal(..., equal_nan=True)` over
de per positie teruggegeven waarden (None als NaN) voor elke meting waar is.

Gemeten op codestand `8e00b38` (dev). Dataset-lader: `gwsw-orox-helpers` 0.2.4 via
`scripts/harnas.py::laad` (cache + gebundelde ontologie). Dataset
`data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`, config `configs/dewoldenhoogeveen.toml`,
bronnen `data/gis_dewoldenhoogeveen`. GDAL 3.8.4, rasterio 1.5.1.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import mmap
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

import numpy as np

WERKBOOM = Path(__file__).resolve().parents[1]
BRONMAP = WERKBOOM / "data" / "gis_dewoldenhoogeveen"
ORIGINEEL = BRONMAP / "AHN6_DeWoldenHoogeveen_DTM.tif"
MEETMAP = WERKBOOM / "uitvoer" / "meting_168"
PUNTEN = MEETMAP / "punten.npy"
RESULTATEN = MEETMAP / "resultaten.csv"


# De bestandsvarianten uit issue #168 na de snoei van #170 (COG vervalt). Elk uit het
# origineel met gdal_translate; float32 en nodata blijven zoals ze zijn.
def _tiles(maat: int) -> list[str]:
    return ["-co", "TILED=YES", "-co", f"BLOCKXSIZE={maat}", "-co", f"BLOCKYSIZE={maat}"]


_P3 = ["-co", "PREDICTOR=3"]
VARIANTEN: dict[int, tuple[str, list[str]]] = {
    1: ("tiles256", _tiles(256)),
    2: ("tiles512", _tiles(512)),
    3: ("tiles1024", _tiles(1024)),
    4: ("tiles512_deflate", [*_tiles(512), "-co", "COMPRESS=DEFLATE", *_P3]),
    5: ("tiles512_zstd", [*_tiles(512), "-co", "COMPRESS=ZSTD", *_P3]),
    6: ("tiles512_lzw", [*_tiles(512), "-co", "COMPRESS=LZW", *_P3]),
}
STRATEGIEEN = ("L0", "L1", "L3")


def variantpad(nr: int) -> Path:
    """Het bestand van variant `nr`, naast het origineel."""
    return BRONMAP / f"AHN6_v{nr}_{VARIANTEN[nr][0]}.tif"


# --- punten -----------------------------------------------------------------------


def stand_punten() -> None:
    """Schrijft de meetpunten: de putten die `_AhnCheck.monstertabel` bemonstert."""
    from gwsw_orox_helpers.dataset import Node
    from harnas import laad, verse_context

    from nlriochecker.checks import REGISTRY
    from nlriochecker.checks.extern import _van_soort

    dataset, config, bronnen = laad()
    context = verse_context(dataset, config, bronnen)
    check = REGISTRY["HGT-001"]()
    knopen = _van_soort(check.selectie(context), Node)
    coords = np.array([(node.point.x, node.point.y) for node in knopen], dtype=np.float64)
    MEETMAP.mkdir(parents=True, exist_ok=True)
    np.save(PUNTEN, coords)
    print(f"PUNTEN {len(coords)} -> {PUNTEN}", flush=True)


def laad_punten() -> list[tuple[float, float]]:
    """De meetpunten als lijst van (x, y), zoals `sample_many` ze krijgt."""
    if not PUNTEN.exists():
        raise SystemExit(f"{PUNTEN} ontbreekt; draai eerst de stand `punten`.")
    return [(float(x), float(y)) for x, y in np.load(PUNTEN)]


# --- bouw -------------------------------------------------------------------------


def stand_bouw(nr: int, forceer: bool) -> None:
    """Bouwt variant `nr` uit het origineel en meldt bouwtijd en grootte."""
    naam, opties = VARIANTEN[nr]
    doel = variantpad(nr)
    if doel.exists() and not forceer:
        print(f"BOUW {nr} {doel} bestaat-al {doel.stat().st_size}", flush=True)
        return
    argv = [
        "gdal_translate",
        "-of",
        "GTiff",
        "-co",
        "BIGTIFF=YES",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        *opties,
        str(ORIGINEEL),
        str(doel),
    ]
    t0 = time.perf_counter()
    subprocess.run(argv, check=True)
    dt = time.perf_counter() - t0
    os.sync()
    print(f"BOUW {nr} {doel} {dt:.1f} {doel.stat().st_size}", flush=True)


# --- paginacache ------------------------------------------------------------------


def koud_maken(paden: Sequence[Path]) -> None:
    """Haalt de pagina's van deze bestanden uit de OS-paginacache (geen root nodig)."""
    os.sync()
    for pad in paden:
        fd = os.open(pad, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def resident_fractie(pad: Path) -> float:
    """Welk deel van het bestand nu in de paginacache staat, via `mincore`."""
    grootte = pad.stat().st_size
    paginas = (grootte + mmap.PAGESIZE - 1) // mmap.PAGESIZE
    with open(pad, "rb") as f:
        # MAP_PRIVATE + PROT_WRITE: alleen om een schrijfbare buffer te krijgen waar ctypes
        # een adres van kan nemen; er wordt niets geschreven en niets aangeraakt.
        mm = mmap.mmap(f.fileno(), 0, flags=mmap.MAP_PRIVATE, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        try:
            vector = (ctypes.c_ubyte * paginas)()
            buffer = ctypes.c_char.from_buffer(mm)
            adres = ctypes.addressof(buffer)
            libc = ctypes.CDLL(None, use_errno=True)
            rc = libc.mincore(ctypes.c_void_p(adres), ctypes.c_size_t(grootte), vector)
            del buffer
            if rc != 0:
                raise OSError(ctypes.get_errno(), "mincore faalde")
            resident = int((np.frombuffer(vector, dtype=np.uint8) & 1).sum())
        finally:
            mm.close()
    return resident / paginas


# --- leesstrategieën --------------------------------------------------------------


def _filter(waarde: float, nodata: float | None) -> float | None:
    """De nodata- en sentinelfilters van `RasterSampler.sample_many`, één op één."""
    getal = float(waarde)
    if nodata is not None and abs(getal - nodata) < 1e-6:
        return None
    if getal > 1e6 or getal < -1e6:
        return None
    return getal


def _binnen(sampler, coords):  # type: ignore[no-untyped-def]
    """De punten binnen de rasterbounds, met hun positie -- zoals `sample_many` ze kiest."""
    links, onder, rechts, boven = sampler.bounds
    return [
        (i, xy)
        for i, xy in enumerate(coords)
        if links <= xy[0] <= rechts and onder <= xy[1] <= boven
    ]


def _rijkolom(reader, binnen):  # type: ignore[no-untyped-def]
    """Rij en kolom per punt, met dezelfde afronding (floor) als rasterio's `sample_gen`."""
    from rasterio.transform import rowcol

    xs = [xy[0] for _, xy in binnen]
    ys = [xy[1] for _, xy in binnen]
    rijen, kolommen = rowcol(reader.transform, xs, ys)
    return np.asarray(rijen, dtype=np.int64), np.asarray(kolommen, dtype=np.int64)


def strategie_l0(sampler, coords):  # type: ignore[no-untyped-def]
    """De code zoals hij in `src/` staat."""
    return sampler.sample_many(coords)


def strategie_l1(sampler, coords):  # type: ignore[no-untyped-def]
    """`reader.sample` over de punten gesorteerd op tegel; terug via de inverse permutatie."""
    resultaten: list[float | None] = [None] * len(coords)
    binnen = _binnen(sampler, coords)
    if not binnen:
        return resultaten
    reader = sampler.reader
    rijen, kolommen = _rijkolom(reader, binnen)
    bys, bxs = reader.block_shapes[0]
    volgorde = np.lexsort((kolommen // bxs, rijen // bys))
    monsters = reader.sample([binnen[k][1] for k in volgorde], 1)
    for k, waarde in zip(volgorde, monsters, strict=True):
        resultaten[binnen[k][0]] = _filter(waarde[0], sampler.nodata)
    return resultaten


def strategie_l3(sampler, coords):  # type: ignore[no-untyped-def]
    """Eén `reader.read(window=tegel)` per geraakte tegel; de punten daaruit indexeren."""
    from rasterio.windows import Window

    resultaten: list[float | None] = [None] * len(coords)
    binnen = _binnen(sampler, coords)
    if not binnen:
        return resultaten
    reader = sampler.reader
    rijen, kolommen = _rijkolom(reader, binnen)
    hoogte, breedte = reader.height, reader.width
    bys, bxs = reader.block_shapes[0]
    tegels_x = -(-breedte // bxs)
    # Buiten het raster geeft `sample_gen` de nodata-waarde (of 0) terug; hier hetzelfde.
    ruw = np.full(len(binnen), reader.nodata or 0, dtype=reader.dtypes[0])
    geldig = (rijen >= 0) & (rijen < hoogte) & (kolommen >= 0) & (kolommen < breedte)
    posities = np.nonzero(geldig)[0]
    sleutels = (rijen[posities] // bys) * tegels_x + kolommen[posities] // bxs
    orde = np.argsort(sleutels, kind="stable")
    posities, sleutels = posities[orde], sleutels[orde]
    uniek, start = np.unique(sleutels, return_index=True)
    for sleutel, groep in zip(uniek, np.split(posities, start[1:]), strict=True):
        ty, tx = divmod(int(sleutel), tegels_x)
        roff, coff = ty * bys, tx * bxs
        venster = Window(coff, roff, min(bxs, breedte - coff), min(bys, hoogte - roff))
        blok = reader.read(1, window=venster)
        ruw[groep] = blok[rijen[groep] - roff, kolommen[groep] - coff]
    for (i, _), waarde in zip(binnen, ruw, strict=True):
        resultaten[i] = _filter(waarde, sampler.nodata)
    return resultaten


STRATEGIE_FUNCTIES = {"L0": strategie_l0, "L1": strategie_l1, "L3": strategie_l3}


# --- meet -------------------------------------------------------------------------


def stand_meet(tif: Path, strategie: str, cachemax: int | None, uit: Path | None) -> None:
    """Eén bemonstering in dit proces; schrijft de RESULTAAT-regel en de waarden."""
    import rasterio

    from nlriochecker.externedata import RasterSampler

    coords = laad_punten()
    resident = resident_fractie(tif)
    omgeving = rasterio.Env(GDAL_CACHEMAX=cachemax) if cachemax else nullcontext()
    with omgeving, rasterio.open(tif) as reader:
        sampler = RasterSampler(
            source=tif,
            crs=str(reader.crs),
            nodata=reader.nodata,
            bounds=tuple(reader.bounds),
            reader=reader,
        )
        t0 = time.perf_counter()
        waarden = STRATEGIE_FUNCTIES[strategie](sampler, coords)
        dt = time.perf_counter() - t0
        blok = reader.block_shapes[0]
    reeks = np.array([np.nan if w is None else w for w in waarden], dtype=np.float64)
    if uit is not None:
        np.save(uit, reeks)
    sha = hashlib.sha256(reeks.tobytes()).hexdigest()
    print(
        f"RESULTAAT {dt:.4f} {sha} resident={resident:.4f} n={len(reeks)} "
        f"nodata={int(np.isnan(reeks).sum())} blok={blok[0]}x{blok[1]}",
        flush=True,
    )


# --- gepaard ----------------------------------------------------------------------


def _meet_proces(
    tif: Path, strategie: str, cachemax: int | None, uit: Path | None
) -> tuple[float, str, float]:
    """Draait één `meet` als apart proces; geeft tijd, sha en residente fractie terug."""
    argv = ["uv", "run", "python", str(Path(__file__).resolve()), "meet", str(tif), strategie]
    if cachemax:
        argv += ["--cachemax", str(cachemax)]
    if uit is not None:
        argv += ["--uit", str(uit)]
    uitvoer = subprocess.run(argv, capture_output=True, text=True, check=True).stdout
    for regel in uitvoer.splitlines():
        if regel.startswith("RESULTAAT "):
            velden = regel.split()
            return float(velden[1]), velden[2], float(velden[3].split("=")[1])
    raise SystemExit(f"geen RESULTAAT-regel in de uitvoer van {argv}:\n{uitvoer}")


def stand_gepaard(n: int, tif: Path, strategie: str, cachemax: int | None, koud: bool) -> None:
    """n x (referentie, experiment) om en om in aparte processen; vat de uitslag samen."""
    MEETMAP.mkdir(parents=True, exist_ok=True)
    label = f"{tif.stem}_{strategie}_cm{cachemax or 0}_{'koud' if koud else 'warm'}"
    print(f"experiment: {tif.name} {strategie} cachemax={cachemax} koud={koud}", flush=True)
    standen = (("ref", ORIGINEEL, "L0", None), ("exp", tif, strategie, cachemax))
    metingen: list[tuple[str, float, str, float]] = []
    reeksen: dict[str, list[np.ndarray]] = {"ref": [], "exp": []}
    for i in range(n):
        for naam, pad, strat, cm in standen:
            uit = MEETMAP / f"{label}_{naam}_{i}.npy"
            if koud:
                koud_maken([ORIGINEEL, tif])
            else:
                _meet_proces(pad, strat, cm, None)  # opwarmer, uitkomst weg
            dt, sha, resident = _meet_proces(pad, strat, cm, uit)
            metingen.append((naam, dt, sha, resident))
            reeksen[naam].append(np.load(uit))
            print(
                f"[{i}] {naam}: {dt:.2f} s  resident {resident:.3f}  sha256 {sha[:16]}",
                flush=True,
            )
    ref_t = [dt for naam, dt, _, _ in metingen if naam == "ref"]
    exp_t = [dt for naam, dt, _, _ in metingen if naam == "exp"]
    referentie = reeksen["ref"][0]
    bitgelijk = all(
        np.array_equal(referentie, reeks, equal_nan=True)
        for reeks in reeksen["ref"][1:] + reeksen["exp"]
    )
    eenduidig = max(exp_t) < min(ref_t) or max(ref_t) < min(exp_t)
    print(
        f"\nref: min {min(ref_t):.2f} max {max(ref_t):.2f}  "
        f"exp: min {min(exp_t):.2f} max {max(exp_t):.2f}"
    )
    print(f"eenduidig (traagste van de een < snelste van de ander): {eenduidig}")
    print(f"bit-gelijk over alle {len(metingen)} reeksen: {bitgelijk}")
    rij = {
        "tijdstip": datetime.now().isoformat(timespec="seconds"),
        "bestand": tif.name,
        "strategie": strategie,
        "cachemax_mb": cachemax or 0,
        "koud": koud,
        "n": n,
        "ref_tijden_s": " ".join(f"{t:.2f}" for t in ref_t),
        "exp_tijden_s": " ".join(f"{t:.2f}" for t in exp_t),
        "ref_min_s": f"{min(ref_t):.2f}",
        "exp_min_s": f"{min(exp_t):.2f}",
        "eenduidig": eenduidig,
        "bitgelijk": bitgelijk,
        "resident_ref": " ".join(f"{r:.3f}" for naam, _, _, r in metingen if naam == "ref"),
        "resident_exp": " ".join(f"{r:.3f}" for naam, _, _, r in metingen if naam == "exp"),
    }
    nieuw = not RESULTATEN.exists()
    with RESULTATEN.open("a", newline="") as f:
        schrijver = csv.DictWriter(f, fieldnames=list(rij))
        if nieuw:
            schrijver.writeheader()
        schrijver.writerow(rij)
    print(
        f"SAMENVATTING {label} ref_min={min(ref_t):.2f} exp_min={min(exp_t):.2f} "
        f"eenduidig={eenduidig} bitgelijk={bitgelijk}"
    )


# --- cli --------------------------------------------------------------------------


def main() -> None:
    """Leest de stand van de opdrachtregel."""
    parser = argparse.ArgumentParser(description="Meetstraat AHN-bemonstering (#168).")
    sub = parser.add_subparsers(dest="stand", required=True)
    sub.add_parser("punten", help="meetpunten naar punten.npy")

    p_bouw = sub.add_parser("bouw", help="variant bouwen met gdal_translate")
    p_bouw.add_argument("nr", type=int, choices=sorted(VARIANTEN))
    p_bouw.add_argument("--forceer", action="store_true")

    p_meet = sub.add_parser("meet", help="één bemonstering in dit proces")
    p_meet.add_argument("tif", type=Path)
    p_meet.add_argument("strategie", choices=STRATEGIEEN)
    p_meet.add_argument("--cachemax", type=int, default=None, help="GDAL_CACHEMAX in MB")
    p_meet.add_argument("--uit", type=Path, default=None, help="waarden als .npy")

    p_gep = sub.add_parser("gepaard", help="n x (ref, exp) om en om in aparte processen")
    p_gep.add_argument("n", type=int)
    p_gep.add_argument("tif", type=Path)
    p_gep.add_argument("strategie", choices=STRATEGIEEN)
    p_gep.add_argument("--cachemax", type=int, default=None, help="GDAL_CACHEMAX in MB")
    p_gep.add_argument("--koud", action="store_true", help="paginacache legen vóór elke meting")

    args = parser.parse_args()
    if args.stand == "punten":
        stand_punten()
    elif args.stand == "bouw":
        stand_bouw(args.nr, args.forceer)
    elif args.stand == "meet":
        stand_meet(args.tif.resolve(), args.strategie, args.cachemax, args.uit)
    elif args.stand == "gepaard":
        stand_gepaard(args.n, args.tif.resolve(), args.strategie, args.cachemax, args.koud)


if __name__ == "__main__":
    sys.exit(main())
