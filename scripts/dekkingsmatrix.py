#!/usr/bin/env python
"""Genereert docs/dekkingsmatrix.md uit het checkregister en de check-registry.

De matrix wordt niet met de hand bijgehouden: hij wordt afgeleid uit het register
(de bron van waarheid voor ID, ernst en dimensie), uit de registry van de engine
(wat er daadwerkelijk draait) en uit de testsuite (welke ID's een test hebben).
Zo kan de matrix niet uit de pas gaan lopen met de code.

Gebruik:  uv run python scripts/dekkingsmatrix.py [categorie ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from gwswpijplijn import checks as _checks  # noqa: F401  (vult de registry)
from gwswpijplijn.checks.base import REGISTRY, SkeletonCheck
from gwswpijplijn.register import Register, RegisterEntry, default_register_path, load_register

WORTEL = Path(__file__).resolve().parents[1]
TESTMAP = WORTEL / "tests"
DOELPAD = WORTEL / "docs" / "dekkingsmatrix.md"
CHECK_ID_PATROON = re.compile(r"\b[A-Z]{3,4}-\d{3}\b")

STATUS_MET_TEST = "geimplementeerd met test"
STATUS_ZONDER_TEST = "geimplementeerd zonder test"
STATUS_ONTBREEKT = "ontbreekt"
STATUS_GESCHRAPT = "geschrapt (gedekt door nulmeting)"


def check_ids_in_tests() -> set[str]:
    """De check-ID's die letterlijk in de testsuite voorkomen.

    Regels die met een `#` beginnen tellen niet mee: een ID dat alleen in een
    toelichting genoemd wordt ("HGT-001 staat in blok C") is geen test, en zou de
    matrix anders een dekking laten claimen die er niet is.
    """
    gevonden: set[str] = set()
    for pad in TESTMAP.rglob("*.py"):
        for regel in pad.read_text(encoding="utf-8").splitlines():
            if regel.lstrip().startswith("#"):
                continue
            gevonden.update(CHECK_ID_PATROON.findall(regel))
    return gevonden


def status(entry: RegisterEntry, getest: set[str]) -> tuple[str, str]:
    """De status van een check-ID plus een toelichting."""
    if entry.dropped:
        return STATUS_GESCHRAPT, entry.covered_by
    check = REGISTRY.get(entry.check_id)
    if check is None:
        return STATUS_ONTBREEKT, ""
    markering = check.markering if issubclass(check, SkeletonCheck) else ""
    toelichting = f"skelet: {markering} — {check.reden}" if markering else ""
    if entry.check_id in getest:
        return STATUS_MET_TEST, toelichting
    return STATUS_ZONDER_TEST, toelichting


def render(register: Register, categorieen: list[str]) -> str:
    """Bouwt de Markdown-matrix."""
    getest = check_ids_in_tests()
    regels = [
        "# Dekkingsmatrix checkregister",
        "",
        f"Gegenereerd uit `{register.source.relative_to(WORTEL)}` (versie {register.version}) "
        "met `scripts/dekkingsmatrix.py`. Niet met de hand bijwerken.",
        "",
        "Status per check-ID: *geimplementeerd met test*, *geimplementeerd zonder test*, "
        "*ontbreekt*, of *geschrapt (gedekt door nulmeting)*. Een check die als skelet "
        "geregistreerd staat telt als geimplementeerd, maar levert per definitie geen "
        "uitslag; de markering en de reden staan in de kolom Toelichting.",
        "",
    ]

    regels += _totalen(register, categorieen, getest)

    for categorie in categorieen:
        posten = register.by_category(categorie)
        if not posten:
            continue
        regels += [
            "",
            f"## {categorie}",
            "",
            "| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for entry in posten:
            stand, toelichting = status(entry, getest)
            regels.append(
                f"| {entry.check_id} | {_kort(entry.title)} | {entry.severity or '—'} | "
                f"{entry.dimension or '—'} | {stand} | {_kort(toelichting) or '—'} |"
            )

    onbekend = sorted(set(REGISTRY) - {entry.check_id for entry in register.entries})
    if onbekend:
        regels += [
            "",
            "## Checks in de engine zonder registerregel",
            "",
            f"{', '.join(onbekend)} — dit hoort niet voor te komen; een check-ID moet uit "
            "het register komen.",
        ]

    return "\n".join(regels) + "\n"


def _totalen(register: Register, categorieen: list[str], getest: set[str]) -> list[str]:
    """De samenvattende tabel met aantallen per categorie."""
    regels = [
        "| Categorie | Register | Met test | Zonder test | Ontbreekt | Geschrapt |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    totaal = dict.fromkeys(
        (STATUS_MET_TEST, STATUS_ZONDER_TEST, STATUS_ONTBREEKT, STATUS_GESCHRAPT), 0
    )
    for categorie in categorieen:
        posten = register.by_category(categorie)
        telling = dict.fromkeys(totaal, 0)
        for entry in posten:
            telling[status(entry, getest)[0]] += 1
        for sleutel, waarde in telling.items():
            totaal[sleutel] += waarde
        regels.append(
            f"| {categorie} | {len(posten)} | {telling[STATUS_MET_TEST]} | "
            f"{telling[STATUS_ZONDER_TEST]} | {telling[STATUS_ONTBREEKT]} | "
            f"{telling[STATUS_GESCHRAPT]} |"
        )
    aantal = sum(len(register.by_category(categorie)) for categorie in categorieen)
    regels.append(
        f"| **totaal** | **{aantal}** | **{totaal[STATUS_MET_TEST]}** | "
        f"**{totaal[STATUS_ZONDER_TEST]}** | **{totaal[STATUS_ONTBREEKT]}** | "
        f"**{totaal[STATUS_GESCHRAPT]}** |"
    )
    return regels


def _kort(tekst: str, limiet: int = 150) -> str:
    """Kapt een lange omschrijving af zodat de tabel leesbaar blijft."""
    tekst = tekst.replace("|", "\\|")
    return tekst if len(tekst) <= limiet else tekst[: limiet - 1].rstrip() + "…"


def main(argv: list[str]) -> int:
    """Schrijft de matrix naar docs/dekkingsmatrix.md."""
    register = load_register(default_register_path())
    categorieen = argv[1:] or register.categories
    DOELPAD.parent.mkdir(parents=True, exist_ok=True)
    DOELPAD.write_text(render(register, categorieen), encoding="utf-8")
    print(f"Geschreven: {DOELPAD.relative_to(WORTEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
