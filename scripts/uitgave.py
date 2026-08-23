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
from datetime import date
from pathlib import Path

SOORTEN = ("patch", "minor", "major")
TAKVOORWAARDE = "main"
# De ondergrens op de testdekking (percentage), afgedwongen met `--cov-fail-under`. Dezelfde
# grens draait op CI (`.github/workflows/toets.yml`); dit is het enige getal in code, en
# tests/test_uitgave.py bindt CI, deze poort en `CLAUDE.md` eraan (BO-38, issue #54).
DEKKINGSONDERGRENS = 95
VERSIEPATROON = re.compile(r"^\d+\.\d+\.\d+$")
CHANGELOG = "CHANGELOG.md"
# Deze drie gaan mee in de versiecommit en worden bij het terugdraaien hersteld.
VERSIEBESTANDEN = ("pyproject.toml", "uv.lock", CHANGELOG)
KOP_UNRELEASED = "## [Unreleased]"
# De kop moet aan het begin van een regel staan; anders zou dezelfde tekst in de
# inleiding het wijzigingslog stilzwijgend op de verkeerde plek doorsnijden.
PATROON_UNRELEASED = re.compile(rf"^{re.escape(KOP_UNRELEASED)}$", re.M)
# De verwijzingsregel onderaan draagt het vorige nummer; daaruit volgt de vergelijking.
PATROON_VERWIJZING = re.compile(
    r"^\[Unreleased\]: (?P<basis>\S*/compare/)v(?P<vorige>\d+\.\d+\.\d+)\.\.\.HEAD$",
    re.M,
)


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
    """Draait dezelfde poort als de CI: ruff, mypy, pytest en een dekkingsondergrens.

    `pytest-cov` staat bewust niet in de dev-groep en wordt per run met `--with` opgelost;
    `--cov-fail-under=DEKKINGSONDERGRENS` laat de run vallen zodra de dekking eronder zakt.
    Zowel deze poort (met de volledige `data/`) als de CI (zonder) meet ruim boven die
    grens; zie BO-38.
    """
    _draai("uv", "run", "ruff", "check", ".")
    _meld("ruff check")
    _draai("uv", "run", "ruff", "format", "--check", ".")
    _meld("ruff format")
    _draai("uv", "run", "mypy")
    _meld("mypy")
    _draai(
        "uv",
        "run",
        "--with",
        "pytest-cov",
        "pytest",
        "-q",
        "--cov=nlriochecker",
        f"--cov-fail-under={DEKKINGSONDERGRENS}",
    )
    _meld(f"pytest + dekking >={DEKKINGSONDERGRENS}%")


def _secties(tekst: str) -> tuple[str, str, str]:
    """Splitst het wijzigingslog in wat voor, in en na de Unreleased-sectie staat."""
    treffer = PATROON_UNRELEASED.search(tekst)
    if treffer is None:
        raise ReleaseAbortedError(f"{CHANGELOG} heeft geen sectie {KOP_UNRELEASED!r}")
    romp_start = treffer.end()
    volgende = tekst.find("\n## ", romp_start)
    einde = len(tekst) if volgende == -1 else volgende + 1
    return tekst[: treffer.start()], tekst[romp_start:einde], tekst[einde:]


def controleer_changelog(tekst: str) -> None:
    """Weigert een uitgave waarvan het wijzigingslog niets te melden heeft.

    Een lege sectie betekent dat niemand heeft opgeschreven wat er veranderde, en
    precies dan is het nummer straks niet meer te duiden.
    """
    _, romp, _ = _secties(tekst)
    inhoud = [
        regel
        for regel in romp.splitlines()
        if regel.strip() and not regel.lstrip().startswith("###")
    ]
    if not inhoud:
        raise ReleaseAbortedError(f"{CHANGELOG}: de sectie {KOP_UNRELEASED!r} is leeg")
    if PATROON_VERWIJZING.search(tekst) is None:
        raise ReleaseAbortedError(
            f"{CHANGELOG}: de regel `[Unreleased]: .../compare/vX.Y.Z...HEAD` onderaan "
            "ontbreekt; zonder die regel is niet af te leiden waartegen vergeleken wordt "
            "en zouden de verwijzingen na deze uitgave doodlopen."
        )


def verwerk_changelog(tekst: str, versie: str, vandaag: date) -> str:
    """Zet Unreleased om in een uitgavesectie en opent een lege nieuwe erboven.

    De verwijzingen onderaan gaan mee: zonder dat zou de nieuwe kop als letterlijke
    `[X.Y.Z]` renderen en zou `[Unreleased]` voor altijd tegen de oude tag blijven
    vergelijken.
    """
    kop, romp, staart = _secties(tekst)
    nieuw = f"{KOP_UNRELEASED}\n\n## [{versie}] - {vandaag:%Y-%m-%d}{romp.rstrip()}\n\n"
    return _verwerk_verwijzingen(f"{kop}{nieuw}{staart}", versie)


def _verwerk_verwijzingen(tekst: str, versie: str) -> str:
    """Richt `[Unreleased]` op de nieuwe tag en zet de vergelijking van deze uitgave erbij."""
    treffer = PATROON_VERWIJZING.search(tekst)
    if treffer is None:
        raise ReleaseAbortedError(f"{CHANGELOG}: de verwijzing naar `[Unreleased]` ontbreekt")
    basis, vorige = treffer.group("basis"), treffer.group("vorige")
    vervanging = f"[Unreleased]: {basis}v{versie}...HEAD\n[{versie}]: {basis}v{vorige}...v{versie}"
    return tekst[: treffer.start()] + vervanging + tekst[treffer.end() :]


def schrijf_changelog(versie: str) -> None:
    """Werkt het wijzigingslog bij voor deze uitgave."""
    pad = Path(CHANGELOG)
    pad.write_text(
        verwerk_changelog(pad.read_text(encoding="utf-8"), versie, date.today()),
        encoding="utf-8",
    )
    _meld(f"changelog {versie}")


def leg_vast(versie: str) -> None:
    """Commit alleen de bestanden die de uitgave raakt, nooit wat de toets achterliet."""
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

        controleer_changelog(Path(CHANGELOG).read_text(encoding="utf-8"))

        doel = voorspel_versie(argumenten.soort)
        tag = f"v{doel}"
        controleer_tag_vrij(tag)

        # Vlag omhoog voor de aanroep: uv schrijft pyproject.toml voordat het lockt, dus
        # ook een halverwege gefaalde bump moet teruggedraaid kunnen worden.
        gebumpt = True
        versie = bump(argumenten.soort, doel)
        schrijf_changelog(versie)

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
