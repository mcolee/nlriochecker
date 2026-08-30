"""De gouden ledger: wat de hele registry op elke TTL-fixture doet.

De suite toetst per defectfixture precies een check (`DEFECTEN` in
`tests/test_checks_blok_a.py`) en per schone fixture alleen haar eigen groep. Wat de
andere achtentachtig checks op zo'n fixture doen ziet niemand: een nieuwe check of een
verruimde selectie die op tientallen fixtures valse bevindingen geeft, laat de suite
groen. Deze module legt dat vast -- per (fixture, check) het aantal bevindingen, de
bekeken populatie en het aantal toelichtingen -- in `tests/golden/ledger.json`.

De ledger *registreert*; hij oordeelt niet. Een rij die verkeerd lijkt is geen reden om
hier een check te wijzigen: dat is een eigen issue.

De veeg zelf komt uit `scripts/maak_ledger.py`, langs de session-fixture `fixtureveeg`.
Generator en test draaien daardoor letterlijk dezelfde lus, en de suite veegt een keer.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

from nlriochecker.checks import CheckRun

LEDGER = Path(__file__).parent / "golden" / "ledger.json"


def _vastgelegd() -> dict[str, dict[str, list[int]]]:
    """De vastgelegde rijen per fixture."""
    inhoud = json.loads(LEDGER.read_text(encoding="utf-8"))
    return inhoud["fixtures"]


def test_de_ledger_klopt_met_de_veeg(
    ledgergenerator: ModuleType, fixtureveeg: dict[str, CheckRun]
) -> None:
    """Elke rij is nog wat hij was; het verschil noemt fixture, check en beide waarden.

    Een assertie op een totaal zou wel afgaan maar niet zeggen wat er verschoof. De
    lijst hieronder noemt per verschil de fixture, de check, de vastgelegde rij en de
    gemeten rij; `None` betekent dat de rij aan die kant niet bestaat.
    """
    vastgelegd = _vastgelegd()
    gemeten = ledgergenerator.ledger(fixtureveeg)["fixtures"]

    verschillen = []
    for fixture in sorted(set(vastgelegd) | set(gemeten)):
        vast, meting = vastgelegd.get(fixture, {}), gemeten.get(fixture, {})
        for check in sorted(set(vast) | set(meting)):
            if vast.get(check) != meting.get(check):
                verschillen.append((fixture, check, vast.get(check), meting.get(check)))

    assert verschillen == []


def test_examined_telt_nooit_minder_dan_de_gemelde_objecten(
    fixtureveeg: dict[str, CheckRun],
) -> None:
    """`examined` is de noemer onder "bekeken"; hij kan niet kleiner zijn dan de teller.

    Het getal draagt in het rapport de regel "Bekeken: N" en in de GeoPackage
    `percentage_populatie`. Een `examined()`-override die zijn eigen populatie te klein
    telt, meldt daardoor meer objecten dan zij zegt bekeken te hebben -- en dat valt in
    geen enkele losse checktest op, want daar staat het getal nergens naast de
    bevindingen.
    """
    schendingen = [
        (naam, outcome.check_id, outcome.examined, len(objecten))
        for naam, run in sorted(fixtureveeg.items())
        for outcome in run.outcomes
        if (objecten := {f.object_uri for f in outcome.findings if f.object_uri})
        and outcome.examined < len(objecten)
    ]

    assert schendingen == []


def test_geen_enkele_fixture_is_registrybreed_stil(fixtureveeg: dict[str, CheckRun]) -> None:
    """Elke fixture levert minstens een bevinding, ook de vijf schone.

    Schoon is per groep bedoeld: `rvz_schoon.ttl` heeft geen RVZ-gebrek, maar mist wel
    een begindatum (ATTR-018) en een verhang (HGT-007). Dat is geen fout -- het staat
    hier zodat de dag dat een fixture registrybreed stil wordt een bewuste keuze is en
    geen stille verschuiving.
    """
    stil = sorted(
        naam for naam, run in fixtureveeg.items() if not any(o.findings for o in run.outcomes)
    )

    assert stil == []
