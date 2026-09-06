"""sha256 van twee `bevindingen.csv` na het blanken van RunDatum, CSV-bewust.

Het bewijs dat een performance-wijziging geen enkele melding verschuift: twee volle
`toets`-runs (met en zonder de wijziging) leveren een `bevindingen.csv` die na het
neutraliseren van de kolom `RunDatum` byte-voor-byte gelijk is. Elk volgend perf-issue
gebruikt dit script naast `scripts/harnas.py` (issue #143, BO-43).

Een naïeve `awk`-split op ';' telt mis op rijen waarvan de meldingstekst zelf een ';'
draagt (ATTR-001: "... 200 mm; daaronder ..."). Deze versie leest met `csv.reader`
(quotechar-bewust) en blankt de kolom op naam.

    uv run python scripts/vergelijk_csv.py <ref.csv> <exp.csv>
"""

from __future__ import annotations

import csv
import hashlib
import sys

# De volle bevindingen.csv van De Wolden en Hoogeveen heeft rijen die de standaardlimiet
# van csv ruim overschrijden; anders faalt de lezer met "field larger than field limit".
csv.field_size_limit(10_000_000)


def lees(pad: str) -> tuple[list[str], list[tuple[str, ...]]]:
    """De kop en de rijen van een `;`-gescheiden bevindingen-CSV, met RunDatum geblankt."""
    with open(pad, newline="", encoding="utf-8") as f:
        lezer = csv.reader(f, delimiter=";")
        kop = next(lezer)
        blank = {kop.index("RunDatum")}
        rijen = [tuple("RUNDATUM" if i in blank else v for i, v in enumerate(rij)) for rij in lezer]
    return kop, rijen


def main(ref: str, exp: str) -> int:
    """Vergelijkt twee CSV's en drukt de sha256 van beide; retourneert 0 bij gelijkheid."""
    kop_a, a = lees(ref)
    kop_b, b = lees(exp)
    print("kolommen gelijk:", kop_a == kop_b, "| rijen:", len(a), len(b))
    ha = hashlib.sha256("\n".join(";".join(r) for r in sorted(a)).encode()).hexdigest()
    hb = hashlib.sha256("\n".join(";".join(r) for r in sorted(b)).encode()).hexdigest()
    print("ref", ha)
    print("exp", hb)
    if ha == hb:
        print("GELIJK")
        return 0
    sa, sb = set(a), set(b)
    print("VERSCHIL: alleen in ref", len(sa - sb), "alleen in exp", len(sb - sa))
    for rij in sorted(sa ^ sb)[:10]:
        print(("REF " if rij in sa else "EXP "), rij[:6])
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
