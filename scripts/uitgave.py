"""Brengt een nieuwe versie uit: bumpt het nummer, toetst, commit en tagt.

Gebruik:

    uv run python scripts/uitgave.py patch|minor|major

De waarheid over het versienummer staat in `pyproject.toml`; `uv version --bump`
schrijft hem daar. De tag volgt het nummer (`vX.Y.Z`), nooit andersom. Pushen doet
dit script niet: dat blijft een bewuste handeling.

Faalt er onderweg iets, dan wordt alles wat dit script al gedaan had teruggedraaid --
eerst de commit, dan de bump. Een half opgehoogd nummer zonder tag is namelijk precies
de toestand waarin niemand meer weet wat er uitgebracht is.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SOORTEN = ("patch", "minor", "major")
TAKVOORWAARDE = "main"
VERSIEPATROON = re.compile(r"^\d+\.\d+\.\d+$")
VERSIEBESTANDEN = ("pyproject.toml", "uv.lock")


class ReleaseAbortedError(Exception):
    """Een voorwaarde is niet gehaald; de uitgave gaat niet door."""


def _draai(*opdracht: str, opvangen: bool = False) -> str:
    """Voert een opdracht uit en geeft stdout terug; faalt hij, dan ReleaseAbortedError."""
    resultaat = subprocess.run(opdracht, capture_output=opvangen, text=True, check=False)
    if resultaat.returncode != 0:
        uitleg = (resultaat.stderr or "").strip() if opvangen else ""
        raise ReleaseAbortedError(f"`{' '.join(opdracht)}` faalde{': ' + uitleg if uitleg else ''}")
    return (resultaat.stdout or "") if opvangen else ""


def _git(*argumenten: str) -> str:
    """Voert een git-opdracht uit en geeft de uitvoer terug, zonder witruimte eromheen."""
    return _draai("git", *argumenten, opvangen=True).strip()


def _meld(stap: str, uitkomst: str = "ok") -> None:
    """Schrijft een voortgangsregel; expliciet doorgespoeld zodat pipes op volgorde blijven."""
    print(f"  {stap.ljust(34, '.')} {uitkomst}", flush=True)


def _waarschuw(bericht: str) -> None:
    """Schrijft een regel naar stderr, naast de uitvoer van de opdrachten zelf."""
    print(f"  {bericht}", file=sys.stderr, flush=True)


def controleer_werkboom() -> None:
    """Eist een schone werkboom op de hoofdtak, zodat de commit alleen de bump bevat."""
    tak = _git("rev-parse", "--abbrev-ref", "HEAD")
    if tak != TAKVOORWAARDE:
        raise ReleaseAbortedError(f"je staat op tak '{tak}', niet op '{TAKVOORWAARDE}'")
    _meld(f"tak {tak}")

    vuil = _git("status", "--porcelain")
    if vuil:
        aantal = len(vuil.splitlines())
        raise ReleaseAbortedError(
            f"werkboom niet schoon ({aantal} gewijzigde bestanden); commit of stash ze eerst"
        )
    _meld("werkboom schoon")


def controleer_niet_achter() -> None:
    """Weigert te taggen op een commit die achterloopt op origin.

    Zonder deze controle komt de tag op een commit te staan die de remote niet als tip
    kent, en wordt de push erna geweigerd -- terwijl de tag lokaal al bestaat.
    Onbereikbare remote is geen reden om te stoppen; dan slaan we de controle over.
    """
    tracking = f"origin/{TAKVOORWAARDE}"
    try:
        _draai("git", "fetch", "--quiet", "origin", TAKVOORWAARDE, opvangen=True)
    except ReleaseAbortedError:
        _meld("origin onbereikbaar", "overgeslagen")
        return
    try:
        _git("rev-parse", "--verify", "--quiet", tracking)
    except ReleaseAbortedError:
        _meld(f"{tracking} bestaat niet", "overgeslagen")
        return

    achter = _git("rev-list", "--count", f"HEAD..{tracking}")
    if achter != "0":
        raise ReleaseAbortedError(f"main loopt {achter} commits achter op {tracking}; pull eerst")
    voor = _git("rev-list", "--count", f"{tracking}..HEAD")
    _meld(f"gelijk met {tracking}", "ok" if voor == "0" else f"{voor} voor")


def huidige_versie() -> str:
    """Leest het nummer zoals het nu in pyproject.toml staat."""
    return _draai("uv", "version", "--short", opvangen=True).strip()


def voorspel_versie(soort: str) -> str:
    """Berekent het volgende nummer zonder iets te schrijven (`--dry-run`).

    Daardoor kan de tagcontrole voor de bump, en kost een tag die al bestaat geen
    bump-en-terugdraai-rondgang.
    """
    uitvoer = _draai("uv", "version", "--bump", soort, "--dry-run", "--short", opvangen=True)
    nieuw = uitvoer.strip()
    if not VERSIEPATROON.match(nieuw):
        raise ReleaseAbortedError(f"'{nieuw}' is geen X.Y.Z-versie")
    return nieuw


def bump(soort: str, verwacht: str) -> str:
    """Hoogt het nummer op in pyproject.toml en uv.lock; geeft het nieuwe nummer terug."""
    oud = huidige_versie()
    _draai("uv", "version", "--bump", soort, opvangen=True)
    nieuw = huidige_versie()
    if nieuw != verwacht:
        raise ReleaseAbortedError(f"bump leverde {nieuw}, niet de voorspelde {verwacht}")
    _meld(f"{oud} -> {nieuw}")
    return nieuw


def controleer_tag_vrij(tag: str) -> None:
    """Weigert een tag die al bestaat; die zou een eerdere uitgave overschrijven."""
    if _git("tag", "--list", tag):
        raise ReleaseAbortedError(f"tag {tag} bestaat al")


def toets() -> None:
    """Draait dezelfde poort als bij elke wijziging: ruff en pytest."""
    _draai("uv", "run", "ruff", "check", ".")
    _meld("ruff check")
    _draai("uv", "run", "ruff", "format", "--check", ".")
    _meld("ruff format")
    _draai("uv", "run", "pytest", "-q")
    _meld("pytest")


def leg_vast(versie: str) -> None:
    """Commit alleen de twee bestanden die de bump raakt, nooit wat de toets achterliet."""
    _git("commit", "-m", f"Versie {versie}", "--", *VERSIEBESTANDEN)
    _meld(f"commit  Versie {versie}")


def _hersynchroniseer() -> None:
    """Zet de omgeving terug op het teruggedraaide nummer."""
    try:
        _draai("uv", "sync", "--quiet", opvangen=True)
    except ReleaseAbortedError as fout:
        _waarschuw(f"LET OP: `uv sync` mislukte na het terugdraaien: {fout}")
        _waarschuw("de omgeving kan een ander nummer dragen dan pyproject.toml; draai `uv sync`")


def draai_alles_terug(*, gebumpt: bool, vastgelegd: bool, versie: str | None) -> None:
    """Maakt de commit en de bump ongedaan, in die volgorde.

    Mislukt het terugdraaien zelf, dan blijft dat een waarschuwing: de oorspronkelijke
    fout is wat de gebruiker moet lezen, niet een traceback uit de opruiming.
    """
    if not gebumpt and not vastgelegd:
        return
    try:
        if vastgelegd:
            # Alleen onze eigen commit weghalen. Staat er iets anders bovenop, dan
            # blijft `reset --hard` uit -- dat zou werk van iemand anders vernietigen.
            kop = _git("log", "-1", "--pretty=%s")
            if kop != f"Versie {versie}":
                _waarschuw(f"LET OP: bovenste commit is '{kop}', niet 'Versie {versie}'")
                _waarschuw("niets teruggedraaid; ruim met de hand op")
                return
            _git("reset", "--hard", "HEAD~1")
            _waarschuw(f"versiecommit 'Versie {versie}' teruggedraaid")
        else:
            # Elk bestand apart: bij een enkele foute pathspec herstelt git er anders geen.
            for bestand in VERSIEBESTANDEN:
                _git("checkout", "--", bestand)
            _waarschuw("bump teruggedraaid")
    except ReleaseAbortedError as fout:
        _waarschuw(f"LET OP: terugdraaien mislukt: {fout}")
        _waarschuw("controleer pyproject.toml, uv.lock en `git log` met de hand")
        return
    _hersynchroniseer()


def main(argv: list[str] | None = None) -> int:
    """Ingang: leest het soort bump en doorloopt de uitgave."""
    ontleder = argparse.ArgumentParser(
        prog="uitgave", description="Bumpt de versie, toetst, commit en tagt."
    )
    ontleder.add_argument("soort", choices=SOORTEN, help="welk deel van het nummer ophoogt")
    argumenten = ontleder.parse_args(argv)

    gebumpt = False
    vastgelegd = False
    versie: str | None = None
    tag: str | None = None
    try:
        os.chdir(Path(_git("rev-parse", "--show-toplevel")))
        controleer_werkboom()
        controleer_niet_achter()

        doel = voorspel_versie(argumenten.soort)
        tag = f"v{doel}"
        controleer_tag_vrij(tag)

        # Vlag omhoog voor de aanroep: uv schrijft pyproject.toml voordat het lockt, dus
        # ook een halverwege gefaalde bump moet teruggedraaid kunnen worden.
        gebumpt = True
        versie = bump(argumenten.soort, doel)

        toets()

        leg_vast(versie)
        vastgelegd = True

        _git("tag", "-a", tag, "-m", f"Versie {versie}")
        _meld(f"tag     {tag}")
    except ReleaseAbortedError as fout:
        draai_alles_terug(gebumpt=gebumpt, vastgelegd=vastgelegd, versie=versie)
        print(f"\nUitgave afgebroken: {fout}", file=sys.stderr, flush=True)
        return 1

    print(f"\n{tag} staat klaar. Pushen met:\n\n    git push --follow-tags\n", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
