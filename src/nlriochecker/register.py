"""Inlezen van het checkregister als machineleesbare lijst van check-ID's.

Het register in `data/checkregister-gwsw-nulmeting-v0_8.md` is de bron van waarheid
voor ID, omschrijving, ernst en dimensietag. Door het te parsen in plaats van over
te tikken kan de dekkingsmatrix niet stilletjes uit de pas gaan lopen met het
register.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from nlriochecker.errors import PipelineError

CHECK_ID = re.compile(r"^[A-Z]{3,4}-\d{3}$")
CATEGORIE_KOP = re.compile(r"^##\s+(?P<code>[A-Z]{3,4}):\s+(?P<naam>.+?)\s*$")
GESCHRAPT_KOP = re.compile(r"^##\s+Geschrapte checks")
ANDERE_KOP = re.compile(r"^##\s+")


class RegisterError(PipelineError):
    """Het checkregister ontbreekt of heeft niet het verwachte formaat."""


@dataclass(frozen=True)
class RegisterEntry:
    """Een enkele regel uit het checkregister."""

    check_id: str
    category: str
    title: str
    severity: str
    dimension: str
    dropped: bool
    covered_by: str = ""

    @property
    def sort_key(self) -> tuple[str, int]:
        """Sorteersleutel: categorie, dan volgnummer."""
        code, nummer = self.check_id.split("-")
        return code, int(nummer)


@dataclass(frozen=True)
class Register:
    """Het volledige checkregister."""

    source: Path
    version: str
    entries: tuple[RegisterEntry, ...]

    def by_category(self, *categories: str) -> list[RegisterEntry]:
        """De regels van deze categorieen, op ID gesorteerd."""
        gekozen = [entry for entry in self.entries if entry.category in categories]
        return sorted(gekozen, key=lambda entry: entry.sort_key)

    def get(self, check_id: str) -> RegisterEntry:
        """De regel met dit ID, of `KeyError`."""
        for entry in self.entries:
            if entry.check_id == check_id:
                return entry
        raise KeyError(check_id)

    @property
    def categories(self) -> list[str]:
        """De categoriecodes in de volgorde waarin ze in het register staan."""
        volgorde: list[str] = []
        for entry in self.entries:
            if entry.category not in volgorde:
                volgorde.append(entry.category)
        return volgorde


def load_register(path: Path) -> Register:
    """Leest het checkregister uit de Markdown-brontekst."""
    path = Path(path)
    try:
        tekst = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RegisterError(f"{path}: checkregister kan niet gelezen worden ({error}).") from error

    entries: list[RegisterEntry] = []
    categorie: str | None = None
    geschrapt = False

    for regel in tekst.splitlines():
        kop = CATEGORIE_KOP.match(regel)
        if kop is not None:
            categorie, geschrapt = kop["code"], False
            continue
        if GESCHRAPT_KOP.match(regel):
            categorie, geschrapt = None, True
            continue
        if ANDERE_KOP.match(regel):
            categorie, geschrapt = None, False
            continue
        if not regel.startswith("|"):
            continue

        velden = [veld.strip() for veld in regel.strip().strip("|").split("|")]
        if not velden or not CHECK_ID.match(velden[0]):
            continue
        entry = _entry(velden, categorie, geschrapt)
        if entry is not None:
            entries.append(entry)

    if not entries:
        raise RegisterError(f"{path}: geen checkregels gevonden; klopt het formaat nog?")

    return Register(source=path, version=_version(tekst), entries=tuple(entries))


def _entry(velden: list[str], categorie: str | None, geschrapt: bool) -> RegisterEntry | None:
    """Bouwt een registerregel uit de kolommen van een tabelrij."""
    check_id = velden[0]
    if geschrapt:
        if len(velden) < 3:
            return None
        return RegisterEntry(
            check_id=check_id,
            category=check_id.split("-")[0],
            title=velden[1],
            severity="",
            dimension="",
            dropped=True,
            covered_by=velden[2],
        )
    if categorie is None or len(velden) < 4:
        return None
    return RegisterEntry(
        check_id=check_id,
        category=categorie,
        title=velden[1],
        severity=velden[2],
        dimension=velden[3],
        dropped=False,
    )


def _version(tekst: str) -> str:
    """De registerversie uit de eerste 'Versie x.y'-vermelding."""
    match = re.search(r"Versie (\d+\.\d+)", tekst)
    return match[1] if match else "onbekend"


def default_register_path() -> Path:
    """Pad naar het checkregister in de datamap van de repository."""
    return Path(__file__).resolve().parents[2] / "data" / "checkregister-gwsw-nulmeting-v0_8.md"
