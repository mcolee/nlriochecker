"""Meetscript bij issue #102 (V19): zijn de 17 NET-004-kringlopen echt?

Onderbouwt het besluit van 2026-08-28: 14 van de 17 lussen bevatten een been
tegen het BOB-verval in, de overige 3 sluiten alleen via een BOB-sprong omhoog
in een put -- geen van de 17 is een echt hydraulisch gebrek. Gedraaid op de
auditrun `uitvoer/audit_27082026` op commit de56b0a van deze repo.

Per gemelde kringloop (putvolgorde uit de boodschap) zoekt dit script per
opeenvolgend putpaar de verbindende streng en vergelijkt de administratieve
richting met de BOB-richting.

Draaien: `uv run python scripts/meet_v19_kringlopen.py`
"""

import json
import re
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.topologie import verbonden_knopen

dataset, _ = laad_met_cache(
    Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"),
    [gebundelde_ontologie()],
    fallback_encoding=FALLBACK_ENCODING,
)
config = load_check_config(Path("configs/dewoldenhoogeveen.toml"))
context = CheckContext(dataset=dataset, config=config)

# label -> node-uri
label_naar_uri: dict[str, str] = {}
for uri, node in dataset.nodes.items():
    if node.label:
        label_naar_uri.setdefault(node.label, uri)

# (uri_a, uri_b) -> [conduit]
per_paar: dict[tuple[str, str], list] = {}
for conduit in dataset.conduits.values():
    a, b = verbonden_knopen(context, conduit)
    if a and b:
        per_paar.setdefault((a, b), []).append(conduit)

meldingen = json.load(open("uitvoer/audit_27082026/bevindingen.json"))["meldingen"]
loops = [m for m in meldingen if m["check_id"] == "NET-004"]
print(f"{len(loops)} kringloopmeldingen\n")

for m in loops:
    labels = re.findall(r"([A-Za-z0-9_]+) ->", m["boodschap"] + " ->")
    # boodschap: "voorbeeld: A -> B -> ... -> Z." — de lus sluit Z -> A
    labels = re.findall(r"voorbeeld: (.*)\.$", m["boodschap"])[0].split(" -> ")
    n = len(labels)
    regels = []
    tegen_bob = 0
    zonder_bob = 0
    for i in range(n):
        la, lb = labels[i], labels[(i + 1) % n]
        ua, ub = label_naar_uri.get(la), label_naar_uri.get(lb)
        cds = per_paar.get((ua, ub), []) + [("omgekeerd", c) for c in per_paar.get((ub, ua), [])]
        if not cds:
            regels.append(f"    {la} -> {lb}: geen streng gevonden")
            continue
        eerste = cds[0]
        if isinstance(eerste, tuple):
            richting, c = "tegen-administratie-in", eerste[1]
            bs, be = c.bob_end, c.bob_start  # gespiegeld lezen
        else:
            richting, c = "met-administratie-mee", eerste
            bs, be = c.bob_start, c.bob_end
        if bs is None or be is None:
            zonder_bob += 1
            oordeel = "BOB onbekend"
        elif be > bs + 1e-9:
            tegen_bob += 1
            oordeel = f"TEGEN BOB IN ({bs:.2f} -> {be:.2f})"
        else:
            oordeel = f"met verval mee ({bs:.2f} -> {be:.2f})"
        regels.append(f"    {la} -> {lb} [{richting}]: {oordeel}")
    kop = (
        f"Lus {labels[0]} ({n} putten): {tegen_bob} been(en) tegen BOB in, {zonder_bob} zonder BOB"
    )
    if tegen_bob:
        kop += "  => hydraulisch GEEN kringloop (richtingsfout waarschijnlijk)"
    elif zonder_bob == 0:
        kop += "  => BOB-consistent: mogelijk echte kringloop"
    print(kop)
    for r in regels:
        print(r)
    print()
