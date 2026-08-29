#!/usr/bin/env python
"""Telt hoeveel RVZ-006-deelstelsels elke soort aanwijzing dragen (issue #106, BO-84).

De aanwijzingen achter de RVZ-006-melding zeggen waardoor een gemengd deelstelsel los
ligt of onvolledig is. Dit script onderbouwt de aantallen in BO-84: het draait RVZ-006
via de gewone engine over de De Wolden en Hoogeveen-export en telt per soort aanwijzing
de deelstelsels die haar dragen. De uitslag verandert er niet door -- het aantal
meldingen en deelstelsels hoort gelijk te blijven aan de run ervoor.

Het script leest de meldingstekst terug in plaats van de diagnosefunctie opnieuw aan te
roepen: zo meet het wat de lezer werkelijk te zien krijgt. Een meting die de code
tweemaal aanroept meet alleen zichzelf.

Bewaard omdat een getal in een BO of een issue een script hoort te hebben dat het
herhaalt (BO-43). Gemeten op commit c6f42b5 (na issue #105).

Gebruik:  uv run python scripts/meet_rvz006_aanwijzingen.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.checks.randvoorzieningen import aanwijzingen_van

DATASET = Path("data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl")
PROJECTCONFIG = Path("configs/dewoldenhoogeveen.toml")
CHECK = "RVZ-006"

# Het aandeel gemengde strengen staat als telling in de melding ("1 van 190 strengen
# gemengd"); waar de grens van "een minderheid" ligt is geen uitspraak van de check maar
# van deze meting, en daarom staat de helft hier en niet in de engine.
AANDEEL = re.compile(r"^(\d+) van (\d+) strengen gemengd$")

# De overige soorten, elk met het tekstfragment waaraan de melding haar verraadt.
FRAGMENTEN = (
    ("samenvallende knoop", "valt samen met"),
    ("knoop op streng", "ligt op streng"),
    ("persleiding", "persleiding "),
    ("lozingspunt", "lozingspunt "),
)

MINDERHEID = "aandeel gemengd < helft"
GEEN = "geen van deze"


def soorten_van(boodschap: str) -> set[str]:
    """De soorten aanwijzing in een RVZ-006-melding."""
    aandeel, overige = aanwijzingen_van(boodschap)
    gevonden = {naam for naam, fragment in FRAGMENTEN if fragment in overige}
    treffer = AANDEEL.match(aandeel)
    if treffer is not None and 2 * int(treffer[1]) < int(treffer[2]):
        gevonden.add(MINDERHEID)
    return gevonden or {GEEN}


def main() -> None:
    """Draait RVZ-006 op de volledige export en telt de aanwijzingen per deelstelsel."""
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    config = load_check_config(PROJECTCONFIG)
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, [CHECK]).outcomes[0]

    per_deelstelsel: dict[str, set[str]] = {}
    for bevinding in outcome.findings:
        per_deelstelsel[bevinding.details["cluster_id"]] = soorten_van(bevinding.message)

    print(f"{CHECK}: {len(outcome.findings)} meldingen op {len(per_deelstelsel)} deelstelsels")
    print(f"bekeken: {outcome.examined} gemengde strengen")
    telling = Counter(soort for soorten in per_deelstelsel.values() for soort in soorten)
    for naam in (MINDERHEID, *(naam for naam, _ in FRAGMENTEN), GEEN):
        print(f"  {naam:<24} {telling[naam]:>4} deelstelsels")
    print("\ncombinaties:")
    for combinatie, aantal in Counter(
        " + ".join(sorted(soorten)) for soorten in per_deelstelsel.values()
    ).most_common():
        print(f"  {aantal:>4}x {combinatie}")


if __name__ == "__main__":
    main()
