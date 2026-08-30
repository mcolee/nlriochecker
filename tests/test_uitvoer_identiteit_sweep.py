"""Bewaking van twee eigenschappen die alleen over de hele codebase te toetsen zijn.

De melding-ID belooft uniek te zijn zonder op verwerkingsvolgorde te steunen, en de
broncode belooft te draaien vanaf een schone checkout. Beide zijn per bestand niet
te zien; deze tests kijken daarom over alles heen.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from nlriochecker.checks import CheckRun
from nlriochecker.uitvoer.melding import bouw_meldingen

WORTEL = Path(__file__).resolve().parent.parent
RUNDATUM = date(2026, 8, 16)
# Een letterlijk fragment van de waarschuwing die `uitvoer.melding._uniek_id` bij een
# botsing schrijft ("... levert twee meldingen met dezelfde ID op ..."). Verandert die
# tekst, dan valt deze test niet stil om: `test_de_botsingswaarschuwing_is_te_herkennen`
# hieronder houdt het fragment aan de echte boodschap vast.
MELDING_BIJ_BOTSING = "twee meldingen met dezelfde ID"


def test_geen_enkele_fixture_levert_een_botsende_melding_id(
    fixtureveeg: dict[str, CheckRun], caplog
) -> None:
    """Het volgnummer-vangnet mag in de praktijk nooit hoeven aanslaan.

    Slaat het toch aan, dan mist een check een identificerende detailsleutel en is
    haar melding-ID afhankelijk van de verwerkingsvolgorde -- precies de
    eigenschap die de ID niet hoort te hebben.

    De veeg over alle fixtures komt uit de gedeelde session-fixture (zie
    `scripts/maak_ledger.py`), zodat de suite hem een keer draait; het bouwen van de
    meldingen en de logcontrole blijven hier, want die bewaken het gedrag dat deze test
    toetst.

    Twee asserties, elk vanaf een andere kant: het volgnummer in de ID zelf, en de
    waarschuwing die `_uniek_id` bij een botsing schrijft. De tweede filterde tot deze
    wijziging op de tekst "id_sleutels", en die staat niet in die waarschuwing -- zij
    kon dus nooit aanslaan. `MELDING_BIJ_BOTSING` is een letterlijk fragment van de
    boodschap in `uitvoer/melding.py`.
    """
    botsingen: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="nlriochecker.uitvoer.melding"):
        for naam, run in sorted(fixtureveeg.items()):
            for melding in bouw_meldingen(run, RUNDATUM):
                if "-" in melding.melding_id[16:]:
                    botsingen.append((naam, melding.check_id))

    assert botsingen == []
    gewaarschuwd = [
        record.message for record in caplog.records if MELDING_BIJ_BOTSING in record.message
    ]
    assert gewaarschuwd == []


def test_de_botsingswaarschuwing_is_te_herkennen(fixtureveeg: dict[str, CheckRun], caplog) -> None:
    """Het fragment hierboven staat echt in de waarschuwing.

    Een filter op een tekst die de logger nooit schrijft leest als bewaking maar is er
    geen -- precies wat er met "id_sleutels" gebeurde. Twee keer dezelfde bevinding
    levert per definitie twee keer dezelfde ID op, dus hier hoort het vangnet wel aan te
    slaan; slaat het niet aan, dan is `MELDING_BIJ_BOTSING` verouderd en toetst de test
    hierboven niets meer.
    """
    run = fixtureveeg["adm006_vervallen_object.ttl"]
    outcome = next(o for o in run.outcomes if o.check_id == "ADM-006")
    verdubbeld = replace(run, outcomes=[replace(outcome, findings=outcome.findings * 2)])

    with caplog.at_level(logging.WARNING, logger="nlriochecker.uitvoer.melding"):
        meldingen = bouw_meldingen(verdubbeld, RUNDATUM)

    assert [melding.melding_id for melding in meldingen if "-2" in melding.melding_id[16:]]
    assert [record.message for record in caplog.records if MELDING_BIJ_BOTSING in record.message]


def test_alle_broncode_staat_onder_versiebeheer() -> None:
    """Een bestand dat alleen in de werkboom bestaat, draait nergens anders.

    Een niet-verankerde regel in .gitignore hield ooit het hele uitvoer-package
    buiten de repository: de tests waren groen en de commits importeerden niet.
    """
    gevolgd = subprocess.run(
        ["git", "ls-files", "src"],
        cwd=WORTEL,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not gevolgd:
        pytest.skip("geen git-checkout")

    onder_versiebeheer = {WORTEL / naam for naam in gevolgd}
    op_schijf = {
        pad
        for patroon in ("*.py", "*.toml", "*.qml", "py.typed")
        for pad in (WORTEL / "src").rglob(patroon)
        if "__pycache__" not in pad.parts
    }

    assert sorted(op_schijf - onder_versiebeheer) == []
