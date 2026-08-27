"""Uitsplitsingen achter de checkaudit van augustus 2026 (docs/checks-audit-2026-08.md).

De aantallen F/W en `bekeken` in dat verslag komen rechtstreeks uit `bevindingen.json`.
Dit script levert de uitsplitsingen die daar niet in staan en die het verslag wel citeert:
per melding de populatie van beide betrokken objecten, het aandeel `c*`-duplicaatlabels,
waar de niet-gesnapte strengeinden van TOP-002/003 aan hangen, en het effect van PRE-3 op
de scope van TOP-006/010/011.

Bewaard omdat een meetscript dat een getal in een verslag onderbouwt navolgbaar hoort te
zijn (`docs/agents/analyse-harness.md`).

Gemeten op:
    run      uitvoer/audit_27082026/ (2026-08-27)
    commit   6311502 (63115026ddfffc5b67af7b47eafd08b6d025eb8f)
    dataset  data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl

Draaien vanuit de repo-root:
    uv run python scripts/checkaudit_meting.py [uitvoermap]
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.selectie import (
    functieloze_knopen,
    hulpstukken,
    leidingen,
    lozeleidingen,
    mechanischeleidingen,
    vrijvervalrioolleidingen,
)
from nlriochecker.checks.verbanden import verbonden_knopen

WORTEL = Path(__file__).resolve().parent.parent
DATASET = WORTEL / "data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"
PROJECTCONFIG = WORTEL / "configs/dewoldenhoogeveen.toml"
STANDAARD_UITVOER = WORTEL / "uitvoer/audit_27082026"


def main(uitvoermap: Path) -> None:
    """Draait alle uitsplitsingen en print ze."""
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    context = CheckContext(dataset=dataset, config=load_check_config(PROJECTCONFIG))
    meldingen = json.loads((uitvoermap / "bevindingen.json").read_text(encoding="utf-8"))[
        "meldingen"
    ]

    alle = {conduit.uri for conduit in leidingen(context)}
    vrij = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
    mech = {conduit.uri for conduit in mechanischeleidingen(context)}
    loos = {conduit.uri for conduit in lozeleidingen(context)}
    duiker = set(dataset.of_class("Duiker")) & alle
    drain = set(dataset.of_class("Drain")) & alle
    rest = alle - vrij - mech - loos - duiker - drain

    def soort(uri: str) -> str:
        """De populatie waarin deze leiding valt; 'geen leiding' voor knopen."""
        for naam, verzameling in (
            ("vrijverval", vrij),
            ("mechanisch", mech),
            ("duiker", duiker),
            ("drain", drain),
            ("loos", loos),
            ("aansluitleiding", rest),
        ):
            if uri in verzameling:
                return naam
        return "geen leiding"

    print(
        f"populatie: leidingen {len(alle)}, vrijverval {len(vrij)}, mechanisch {len(mech)}, "
        f"drain {len(drain)}, duiker {len(duiker)}, aansluitleiding {len(rest)}, loos {len(loos)}"
    )
    print(
        "aansluitleidingen per type:",
        collections.Counter(
            dataset.beheerobjecttype(uri) or "(zonder type)" for uri in rest
        ).most_common(),
    )

    # 1. Per paarcheck de populatie aan weerszijden van de melding.
    for check_id in ("TOP-006", "TOP-010", "TOP-011"):
        eigen = [m for m in meldingen if m["check_id"] == check_id]
        paren = collections.Counter(
            tuple(sorted((soort(m["object_uri"]), soort(m["object2_uri"])))) for m in eigen
        )
        toegestaan = vrij | duiker
        pre3 = sum(
            1 for m in eigen if m["object_uri"] in toegestaan and m["object2_uri"] in toegestaan
        )
        print(f"-- {check_id}: {len(eigen)} meldingen, onder PRE-3 (vrijverval+duiker) {pre3}")
        for paar, aantal in paren.most_common():
            print(f"   {paar}: {aantal}")

    # 2. Het aandeel `c*`-duplicaatlabels per putcheck (PRE-7).
    for check_id in ("TOP-001", "TOP-005", "TOP-021"):
        eigen = [m for m in meldingen if m["check_id"] == check_id]
        met_postfix = sum(1 for m in eigen if "  c" in m["object_label"])
        types = collections.Counter(
            dataset.beheerobjecttype(m["object_uri"]) or "(zonder type)" for m in eigen
        )
        print(
            f"-- {check_id}: {len(eigen)} meldingen, {met_postfix} met een c*-postfix; "
            f"types {types.most_common()}"
        )

    # 3. Waar hangen de niet-gesnapte strengeinden van TOP-002/003 aan?
    hulp = {node.uri for node in hulpstukken(context)}
    for check_id in ("TOP-002", "TOP-003"):
        tellers: collections.Counter[tuple[str, ...]] = collections.Counter()
        for melding in meldingen:
            if melding["check_id"] != check_id:
                continue
            conduit = dataset.conduits.get(melding["object_uri"])
            if conduit is None:
                tellers[("(geen streng)",)] += 1
                continue
            einden = []
            for rauw in (conduit.start_node, conduit.end_node):
                if rauw is None:
                    einden.append("geen koppeling")
                elif rauw in hulp:
                    einden.append("hulpstuk")
                else:
                    einden.append(dataset.beheerobjecttype(rauw) or "onherleid")
            tellers[tuple(sorted(einden))] += 1
        print(f"-- {check_id} einden: {tellers.most_common()}")

    # 4. TOP-019: kan de check op deze configuratie uberhaupt aanslaan?
    functieloos = functieloze_knopen(context)
    uris = {node.uri for node in functieloos}
    treffers = sum(
        1
        for conduit in leidingen(context)
        for uri in verbonden_knopen(context, conduit)
        if uri in uris
    )
    soorten = collections.Counter(
        dataset.beheerobjecttype(node.uri) or "(zonder type)" for node in functieloos
    )
    print(
        f"-- TOP-019: {len(functieloos)} functieloze knopen ({soorten.most_common()}); "
        f"{treffers} van de {2 * len(alle)} strengeinden komt erop uit"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else STANDAARD_UITVOER)
