"""Meetscript bij issue #100 (V5): gevoeligheid van de TOP-006/010-drempels.

Onderbouwt het besluit van 2026-08-28: TOP-006 naar 0,02 m tolerantie en 2,0 m
minimumlengte; de TOP-010-marge blijft 0,0 m. Gedraaid op De Wolden
(`data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`), dataset-lader
gwsw-orox-helpers zoals vergrendeld op commit de56b0a van deze repo.

Populatie = na #82: beide partijen vrijverval of duiker (drains, mechanisch en
aansluitleidingen tellen niet mee). Zelfde paarlogica als de checks zelf:
- TOP-010: afstand hartlijnen <= som halve diameters + marge; paren die een put
  of een uiteinde delen vallen af.
- TOP-006: overlaplengte binnen tolerantie >= minimumlengte.

Draaien: `uv run python scripts/meet_v5_gevoeligheid.py`
"""

import statistics
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.topologie import (
    _buren,
    _nabijheid,
    half_diameter_m,
    overlap_length,
    verbonden_knopen,
)

dataset, _ = laad_met_cache(
    Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
    [gebundelde_ontologie()],
    fallback_encoding=FALLBACK_ENCODING,
)
config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
context = CheckContext(dataset=dataset, config=config)

# De populatie van TOP-006/010/011 zelf, niet een eigen nabouw ervan: `_nabijheid`
# draagt sinds #82 de rol `nabijheidsleidingen` (vrijverval + duiker) met een STRtree
# over hun hartlijnen. `_buren` leest die index; hem een `_Topologie` voeren levert de
# boom van putpunten en dus plausibel ogende verkeerde getallen (blok C-review).
nabijheid = _nabijheid(context)
scoped = nabijheid.conduits
print(f"leidingen: {nabijheid.totaal}, in scope (vrijverval+duiker, met lijn): {len(scoped)}")

# ---------- TOP-010: verdeling van gap = afstand - (r1 + r2) ----------
stralen = {c.uri: half_diameter_m(c.breedte_mm, c.hoogte_mm) for c in scoped}
knopen = {c.uri: verbonden_knopen(context, c) for c in scoped}
grootste = max(stralen.values(), default=0.0)
tol_snap = config.drempels.snapping_tolerantie_m

MARGES = [-0.10, -0.05, -0.02, 0.0, 0.05, 0.10]
ruimste = max(MARGES)


def deelt_put(a, b) -> bool:
    la = {u for u in knopen[a.uri] if u}
    lb = {u for u in knopen[b.uri] if u}
    return bool(la & lb)


def deelt_uiteinde(a, b) -> bool:
    ea, eb = nabijheid.eindpunten[a.uri], nabijheid.eindpunten[b.uri]
    return any(p.distance(q) <= tol_snap for p in ea for q in eb)


paren_gap: dict[tuple[str, str], float] = {}
for c in scoped:
    straal = stralen[c.uri]
    for ander in _buren(nabijheid, c, straal + grootste + ruimste):
        sleutel = (min(c.uri, ander.uri), max(c.uri, ander.uri))
        if sleutel in paren_gap:
            continue
        buffer = straal + stralen[ander.uri]
        if buffer <= 0.0:
            continue
        afstand = c.line.distance(ander.line)
        if afstand > buffer + ruimste:
            continue
        if deelt_put(c, ander) or deelt_uiteinde(c, ander):
            continue
        paren_gap[sleutel] = afstand - buffer  # gap <= 0 = buizen raken/overlappen

print("\nTOP-010 (scope na #82) — meldingen bij marge (gap < marge, huidige check: gap <= 0):")
for m in MARGES:
    n = sum(1 for g in paren_gap.values() if g <= m)
    print(f"  marge {m:+.2f} m: {n}")

# verdeling van de overlapdiepte voor de huidige meldingen (gap <= 0)
diepten = sorted(-g for g in paren_gap.values() if g <= 0)
if diepten:
    print(
        f"  overlapdiepte (gap<=0, n={len(diepten)}): min {diepten[0]:.3f}, "
        f"mediaan {statistics.median(diepten):.3f}, p90 {diepten[int(0.9 * len(diepten))]:.3f}, "
        f"max {diepten[-1]:.3f} m"
    )

# ---------- TOP-006: meldingen per (tolerantie, minimumlengte) ----------
TOLS = [0.02, 0.05, 0.10, 0.20]
MINS = [1.0, 2.0, 5.0, 10.0]
max_tol = max(TOLS)

paren_006: dict[tuple[str, str], dict[float, float]] = {}
for c in scoped:
    for ander in _buren(nabijheid, c, max_tol):
        sleutel = (min(c.uri, ander.uri), max(c.uri, ander.uri))
        if sleutel in paren_006:
            continue
        paren_006[sleutel] = {t: overlap_length(c.line, ander.line, t) for t in TOLS}

print("\nTOP-006 (scope na #82) — meldingen per tolerantie × minimumlengte:")
kop = "tol\\min | " + " | ".join(f"{m:>5.0f} m" for m in MINS)
print("  " + kop)
for t in TOLS:
    rij = [sum(1 for lens in paren_006.values() if lens[t] >= m) for m in MINS]
    print(f"  {t:.2f} m | " + " | ".join(f"{n:>7}" for n in rij))
