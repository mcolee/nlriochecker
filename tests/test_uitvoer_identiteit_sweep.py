"""Bewaking van twee eigenschappen die alleen over de hele codebase te toetsen zijn.

De melding-ID belooft uniek te zijn zonder op verwerkingsvolgorde te steunen, en de
broncode belooft te draaien vanaf een schone checkout. Beide zijn per bestand niet
te zien; deze tests kijken daarom over alles heen.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import date
from pathlib import Path

import pytest

from nlriochecker.checks import CheckRun
from nlriochecker.uitvoer.melding import bouw_meldingen

WORTEL = Path(__file__).resolve().parent.parent
RUNDATUM = date(2026, 8, 16)


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
    """
    botsingen: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="nlriochecker.uitvoer.melding"):
        for naam, run in sorted(fixtureveeg.items()):
            for melding in bouw_meldingen(run, RUNDATUM):
                if "-" in melding.melding_id[16:]:
                    botsingen.append((naam, melding.check_id))

    assert botsingen == []
    assert [record.message for record in caplog.records if "id_sleutels" in record.message] == []


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
