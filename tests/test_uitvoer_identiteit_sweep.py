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

from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import CheckContext, run_checks
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.uitvoer.melding import bouw_meldingen

WORTEL = Path(__file__).resolve().parent.parent
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
RUNDATUM = date(2026, 8, 16)


def test_geen_enkele_fixture_levert_een_botsende_melding_id(caplog) -> None:
    """Het volgnummer-vangnet mag in de praktijk nooit hoeven aanslaan.

    Slaat het toch aan, dan mist een check een identificerende detailsleutel en is
    haar melding-ID afhankelijk van de verwerkingsvolgorde -- precies de
    eigenschap die de ID niet hoort te hebben.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0

    botsingen: list[tuple[str, str]] = []
    with caplog.at_level(logging.WARNING, logger="gwswpijplijn.uitvoer.melding"):
        for pad in sorted(TTL_DIR.glob("*.ttl")):
            dataset = load_dataset(pad)
            run = run_checks(CheckContext(dataset=dataset, config=config))
            for melding in bouw_meldingen(run, RUNDATUM):
                if "-" in melding.melding_id[16:]:
                    botsingen.append((pad.name, melding.check_id))

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
        for patroon in ("*.py", "*.toml", "*.qml")
        for pad in (WORTEL / "src").rglob(patroon)
        if "__pycache__" not in pad.parts
    }

    assert sorted(op_schijf - onder_versiebeheer) == []
