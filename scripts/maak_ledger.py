#!/usr/bin/env python
"""Schrijft de gouden ledger `tests/golden/ledger.json`.

De ledger legt vast wat de VOLLEDIGE registry op elke TTL-fixture doet: per
(fixture, check) het aantal bevindingen, de bekeken populatie en het aantal
toelichtingen, plus per check het aantal meldingen van het getrackte voorbeeld. De
suite toetste tot nu toe per defectfixture precies een check; wat de andere
achtentachtig daar doen zag niemand.

Dit script is de generator EN de enige veeglus: `tests/conftest.py` laadt het als
module en draait `veeg()` in een session-fixture, zodat de vastgelegde getallen niet
uit een tweede, net iets andere lus kunnen komen. Zie `tests/test_ledger.py`.

Twee dingen die de uitkomst bepalen en dus hier vastliggen:

* **Het laadrecept.** `load_dataset` met terugvalcodering (`codering_cp850.ttl` is met
  opzet geen UTF-8) gevolgd door `markeer_vulwaarden`, precies zoals `toetsrun.py` de
  pijplijn laadt. Zonder die markering legt de ledger iets vast wat geen enkele run
  oplevert: op `attr013_vulwaarde_hoogte.ttl` levert de kale lezing twaalf checks met
  vijfentwintig bevindingen en de gemarkeerde vijf met elf.
* **De peildatum.** Twee checks lezen de dag van vandaag: ATTR-007 valt terug op
  `date.today().year` als `[drempels] begindatum_maximum` leeg is, en ADM-006 leest
  `date.today()` zonder configknop. De eerste pinnen we via die knop, de tweede met een
  tijdelijke vervanging van de module-`date`. Zonder pin zou een fixture met een datum
  vlak bij nu de ledger laten schuiven zonder dat er iets veranderd is. De peildatum
  staat in het bestand, zodat een lezer weet waartegen gemeten is.

De voorbeeldrun wordt bewust NIET gepind: die draait het commando uit
`voorbeelden/koekangerveld/README.md`, en dat moet zo blijven.

De uitvoer is gegenereerd en wordt nooit met de hand bijgewerkt; zie de tabel
"Gegenereerde bestanden" in `docs/agents/analyse-harness.md`. Bestaat het bestand al,
dan meldt dit script eerst hoeveel rijen erbij komen, verdwijnen en veranderen: wie
regenereert hoort te zien wat hij accepteert.

Gebruik:  uv run python scripts/maak_ledger.py
"""

from __future__ import annotations

import json
import re
import tempfile
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from gwsw_orox_helpers.dataset import load_dataset, markeer_vulwaarden

from nlriochecker.checkconfig import FALLBACK_ENCODING, CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.checks import administratief as _administratief
from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit

WORTEL = Path(__file__).resolve().parents[1]
TTL_DIR = WORTEL / "tests" / "fixtures" / "ttl"
DOEL = WORTEL / "tests" / "golden" / "ledger.json"

VOORBEELD = WORTEL / "voorbeelden" / "koekangerveld"
VOORBEELD_TTL = VOORBEELD / "koekangerveld_orox.ttl"
VOORBEELD_GEBIED = VOORBEELD / "cbs_buurt_koekangerveld_studiegebied.gpkg"
VOORBEELD_SHACL = (
    VOORBEELD / "gwsw_shacl_report_conformiteit_Hyd.csv",
    VOORBEELD / "gwsw_shacl_report_conformiteit_MdsPlan.csv",
    VOORBEELD / "gwsw_shacl_report_MdsProj.csv",
)

# De dag waarop de fixtureveeg gemeten is. Elke vaste datum voldoet zolang zij in het
# bestand staat; deze verschuift de huidige tellingen niet (alle begindatums in de
# fixtures liggen tussen 1900 en 2003, op de 2099 van `attr007_toekomstig_jaar.ttl` na).
PEILDATUM = date(2026, 1, 1)


class _Peildatum(date):
    """`date` met een vastgezette `today()`, voor de checks die de klok lezen."""

    @classmethod
    def today(cls) -> date:  # type: ignore[override]
        return PEILDATUM


@contextmanager
def _klok_op_peildatum() -> Iterator[None]:
    """Zet `date.today()` in `checks/administratief.py` op de peildatum.

    ADM-006 heeft geen configknop voor "vandaag" en die erbij bouwen raakt
    `src/nlriochecker/checks/` -- een auteursbesluit, geen testkwestie. De module heeft
    `from __future__ import annotations`, dus het vervangen van het module-attribuut
    raakt de annotaties niet.
    """
    origineel = _administratief.date
    _administratief.date = _Peildatum  # type: ignore[misc]
    try:
        yield
    finally:
        _administratief.date = origineel  # type: ignore[misc]


def veegconfig() -> CheckConfig:
    """De configuratie van de veeg: standaard, met twee gerichte afwijkingen.

    De RD-ondergrens gaat naar 0, want de fixturecoordinaten vallen buiten het
    RD-bereik (zoals `fixtureconfig()` in `tests/test_checks_blok_a.py` dat ook doet),
    en de bovengrens van ATTR-007 wordt op het peiljaar gezet in plaats van op de
    dag van vandaag.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    config.drempels.begindatum_maximum = PEILDATUM.year
    return config


def veeg(config: CheckConfig) -> dict[str, CheckRun]:
    """Per fixturenaam de `CheckRun` van de volledige registry over alle TTL-fixtures.

    Het laadrecept en de klokpin staan in de moduledocstring; ze horen bij deze lus en
    niet bij de beller, zodat de generator en de suite niet uit elkaar kunnen lopen.
    """
    runs: dict[str, CheckRun] = {}
    with _klok_op_peildatum():
        for pad in sorted(TTL_DIR.glob("*.ttl")):
            dataset = markeer_vulwaarden(
                load_dataset(pad, [], fallback_encoding=FALLBACK_ENCODING),
                config.vulwaarden.hoogte_kenmerken,
                config.vulwaarden.hoogte_band_m,
            )
            runs[pad.name] = run_checks(CheckContext(dataset=dataset, config=config))
    return runs


def ledger(runs: Mapping[str, CheckRun]) -> dict[str, object]:
    """De vastgelegde vorm van de fixtureveeg: peildatum plus een rij per bevinding.

    De rij is `[bevindingen, examined, notes]` en staat er alleen als de check op die
    fixture iets meldde. Alle rijen zijn er 16.287 en "bevindingen of toelichtingen"
    11.593; bij 869 blijft een diff nog te lezen. De prijs staat in `tests/test_ledger.py`:
    `examined` van een check die nergens aanslaat blijft onbewaakt. `weggelaten` gaat er
    niet in -- zonder studiegebied is dat veld op elke rij 0.

    De fixturenaam staat er ook zonder rijen, zodat een fixture die verdwijnt of erbij
    komt in de diff zichtbaar is.

    `main()` zet de sectie `voorbeeld` erbij; die komt niet uit deze veeg.
    """
    return {
        "peildatum": PEILDATUM.isoformat(),
        "fixtures": {
            naam: {
                outcome.check_id: [len(outcome.findings), outcome.examined, len(outcome.notes)]
                for outcome in run.outcomes
                if outcome.findings
            }
            for naam, run in runs.items()
        },
    }


def _voorbeeldtelling() -> dict[str, int]:
    """Per check het aantal meldingen van een `toets` op het getrackte voorbeeld.

    Uit `envelop["meldingen"]`, dus inclusief de `NULMETING-*`-vormen en de
    `SIG-*`-datasetsignalen: die zitten in dezelfde meldingenstroom. De opdracht is die
    van `voorbeelden/koekangerveld/README.md` -- zonder `--projectconfig` en zonder
    klokpin. `tests/test_voorbeeld.py` draait dezelfde opdracht en vergelijkt de telling
    met deze sectie; wijken de twee opdrachten uit elkaar, dan valt die test om.
    """
    with tempfile.TemporaryDirectory() as tijdelijk:
        uitslag = voer_toets_uit(
            Toetsopdracht(
                dataset_pad=VOORBEELD_TTL,
                uitvoermap=Path(tijdelijk),
                shacl=VOORBEELD_SHACL,
                studiegebied=VOORBEELD_GEBIED,
                bronnen=VOORBEELD,
                gebruik_cache=False,
            )
        )
        pad = uitslag.uitvoer.per_gebied[uitslag.runs[0].naam].json
        if pad is None:
            raise SystemExit("de voorbeeldrun schreef geen JSON; ledger niet te vullen.")
        envelop = json.loads(pad.read_text(encoding="utf-8"))
    return dict(Counter(str(melding["check_id"]) for melding in envelop["meldingen"]))


# `json.dumps(indent=2)` breekt ook de drieledige rijen open -- vijf regels per rij --
# en zonder indent staat het hele bestand op een regel. Beide maken een diff onleesbaar;
# deze uitdrukking vouwt de rijen weer op tot een regel. Het blijft geldige JSON, en
# `_schrijf` controleert dat door het teruggelezen document te vergelijken.
_RIJ_OP_EEN_REGEL = re.compile(r"\[\s+(\d+),\s+(\d+),\s+(\d+)\s+\]")


def _tekst(inhoud: Mapping[str, object]) -> str:
    """De ledger als JSON-tekst: gesorteerd, een regel per rij, afsluitend regeleinde."""
    ruw = json.dumps(inhoud, indent=2, sort_keys=True, ensure_ascii=False)
    return _RIJ_OP_EEN_REGEL.sub(r"[\1, \2, \3]", ruw) + "\n"


def _rijen(inhoud: Mapping[str, object]) -> dict[tuple[str, str], list[int]]:
    """De rijen als platte afbeelding (fixture, check) -> rij, om te kunnen vergelijken."""
    fixtures = inhoud["fixtures"]
    assert isinstance(fixtures, dict)
    return {
        (fixture, check): rij for fixture, rijen in fixtures.items() for check, rij in rijen.items()
    }


def _meld_verschil(oud: Mapping[str, object], nieuw: Mapping[str, object]) -> None:
    """Drukt af hoeveel rijen erbij komen, verdwijnen en veranderen.

    Wie de ledger regenereert accepteert een verschuiving; hij hoort te zien hoe groot
    zij is voordat het bestand overschreven wordt.
    """
    voor, na = _rijen(oud), _rijen(nieuw)
    erbij = sorted(set(na) - set(voor))
    weg = sorted(set(voor) - set(na))
    anders = sorted(sleutel for sleutel in set(voor) & set(na) if voor[sleutel] != na[sleutel])
    print(f"verschil: {len(erbij)} erbij, {len(weg)} verdwenen, {len(anders)} veranderd")
    for fixture, check in erbij[:20]:
        print(f"  + {fixture} {check} {na[fixture, check]}")
    for fixture, check in weg[:20]:
        print(f"  - {fixture} {check} {voor[fixture, check]}")
    for fixture, check in anders[:20]:
        print(f"  ~ {fixture} {check} {voor[fixture, check]} -> {na[fixture, check]}")
    if oud.get("voorbeeld") != nieuw.get("voorbeeld"):
        print("  ~ de sectie `voorbeeld` verandert")


def _schrijf(inhoud: Mapping[str, object]) -> None:
    """Schrijft het bestand, na een terugleescontrole op de opgemaakte tekst."""
    tekst = _tekst(inhoud)
    if json.loads(tekst) != inhoud:
        raise SystemExit("de opgemaakte JSON leest niet terug als hetzelfde document.")
    DOEL.parent.mkdir(parents=True, exist_ok=True)
    DOEL.write_text(tekst, encoding="utf-8")


def main() -> None:
    """Bouwt de ledger opnieuw op."""
    begin = time.monotonic()
    runs = veeg(veegconfig())
    inhoud = ledger(runs)
    inhoud["voorbeeld"] = _voorbeeldtelling()

    fixtures = inhoud["fixtures"]
    assert isinstance(fixtures, dict)
    checks = len(next(iter(runs.values())).outcomes) if runs else 0
    print(
        f"veeg: {len(runs)} fixtures x {checks} checks, "
        f"{len(_rijen(inhoud))} rijen met minstens een bevinding "
        f"({time.monotonic() - begin:.1f} s)"
    )

    if DOEL.exists():
        _meld_verschil(json.loads(DOEL.read_text(encoding="utf-8")), inhoud)
    _schrijf(inhoud)
    print(f"{DOEL.relative_to(WORTEL)}: {DOEL.stat().st_size / 1000:.1f} kB")


if __name__ == "__main__":
    main()
