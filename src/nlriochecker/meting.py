"""De nulmeting: de verzameling SHACL-rapporten over een dataset."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from nlriochecker.errors import NulmetingError
from nlriochecker.shaclrapport import ShaclReport, lees_shacl_rapport
from nlriochecker.taal import vorm


@dataclass(frozen=True)
class Meetbereik:
    """Tegen welke conformiteitsklassen deze run getoetst is, en of dat de volle set was.

    Drie toestanden, want een run zonder nulmeting is iets anders dan een deelset:
    volledig (alle klassen uit de projectconfiguratie), deelset (een expliciete
    keuze via `--cfk`) en niet gemeten (`toets` zonder `--shacl`). Alleen deze
    klasse kent dat verschil; de schrijvers nemen de tekst en de velden over zoals
    ze hier staan, zodat Markdown, GeoPackage en JSON niet uit elkaar kunnen lopen.
    """

    volledige_set: tuple[str, ...]
    gekozen: tuple[str, ...]
    gemeten: bool

    @classmethod
    def van(cls, volledige_set: Sequence[str], gekozen: Sequence[str]) -> Meetbereik:
        """Een gemeten bereik, met beide verzamelingen gesorteerd en ontdubbeld."""
        return cls(tuple(sorted(set(volledige_set))), tuple(sorted(set(gekozen))), True)

    @classmethod
    def niet_gemeten(cls, volledige_set: Sequence[str]) -> Meetbereik:
        """Het bereik van een run zonder nulmeting: niets gekozen, niets gemeten."""
        return cls(tuple(sorted(set(volledige_set))), (), False)

    @property
    def volledig(self) -> bool:
        """Waar als er gemeten is, en op de volle set."""
        return self.gemeten and self.gekozen == self.volledige_set

    @property
    def ontbreekt(self) -> tuple[str, ...]:
        """De klassen uit de volle set waarop niet getoetst is."""
        return tuple(cfk for cfk in self.volledige_set if cfk not in self.gekozen)

    @property
    def cfk_tekst(self) -> str:
        """De gekozen set als kommagescheiden tekst, voor de GeoPackage."""
        return ", ".join(self.gekozen)

    def markering(self) -> str | None:
        """De waarschuwingsregel voor de rapporten, of None als er niets te melden is.

        Deze ene plek bepaalt de tekst voor alle uitvoervormen. Zou elke schrijver
        hem zelf samenstellen, dan zeggen Markdown en JSON op een dag iets anders
        over dezelfde run.
        """
        if self.volledig:
            return None
        if not self.gemeten:
            return (
                "**Geen nulmeting:** deze run is niet tegen de conformiteitsklassen "
                "getoetst; de typeringspoort is niet toegepast."
            )
        ontbreekt = ", ".join(self.ontbreekt)
        return (
            f"**Onvolledige meting:** getoetst op {self.cfk_tekst}; {ontbreekt} "
            f"{vorm(len(self.ontbreekt), 'ontbreekt', 'ontbreken')}."
        )


@dataclass(frozen=True)
class Nulmeting:
    """Een dataset die aan alle vereiste conformiteitsklassen getoetst is."""

    dataset_file: str
    reports: dict[str, ShaclReport]
    meetbereik: Meetbereik

    @property
    def cfks(self) -> list[str]:
        """De aanwezige conformiteitsklassen, in vaste volgorde."""
        return sorted(self.reports)

    @property
    def timestamps_differ(self) -> bool:
        """Geeft aan of de rapporten uit verschillende meetmomenten komen."""
        momenten = {rapport.timestamp for rapport in self.reports.values()}
        return len(momenten) > 1

    @property
    def latest(self) -> datetime:
        """Het laatste toetsmoment van de meting."""
        return max(rapport.timestamp for rapport in self.reports.values())

    def report(self, cfk: str) -> ShaclReport:
        """Het rapport van een conformiteitsklasse."""
        return self.reports[cfk]


def laad_nulmeting(
    paden: list[Path],
    vereiste_cfk: list[str],
    volledige_cfk: list[str] | None = None,
) -> Nulmeting:
    """Leest de SHACL-rapporten en toetst de harde eisen.

    Alle vereiste conformiteitsklassen moeten aanwezig zijn en alle rapporten
    moeten over hetzelfde RDF-bestand gaan; anders zeggen de uitkomsten niets over
    dezelfde dataset.

    `vereiste_cfk` is wat deze run eist, `volledige_cfk` wat de projectconfiguratie
    als volle set kent. Zijn ze ongelijk, dan is dit een deelset en zegt het
    `Meetbereik` dat tegen elke uitvoervorm. Zonder `volledige_cfk` gelden ze als
    gelijk, zodat bestaande aanroepen een volledig bereik houden.
    """
    if not paden:
        raise NulmetingError("Geef minstens een SHACL-rapport op.")

    rapporten: dict[str, ShaclReport] = {}
    for pad in paden:
        rapport = lees_shacl_rapport(Path(pad))
        eerder = rapporten.get(rapport.cfk)
        if eerder is not None:
            raise NulmetingError(
                f"Twee rapporten voor CFK {rapport.cfk!r}: {eerder.source_file} en "
                f"{rapport.source_file}. Geef er per conformiteitsklasse een."
            )
        rapporten[rapport.cfk] = rapport

    overtollig = sorted(cfk for cfk in rapporten if cfk not in vereiste_cfk)
    if overtollig:
        bestanden = ", ".join(f"{cfk}={rapporten[cfk].source_file}" for cfk in overtollig)
        raise NulmetingError(
            f"Rapport(en) voor niet-gekozen conformiteitsklasse(n) {', '.join(overtollig)} "
            f"({bestanden}). Deze run toetst op {', '.join(vereiste_cfk)}; laat ze weg of "
            f"breid de keuze uit."
        )

    ontbreekt = [cfk for cfk in vereiste_cfk if cfk not in rapporten]
    if ontbreekt:
        raise NulmetingError(
            f"De nulmeting mist conformiteitsklasse(n) {', '.join(ontbreekt)}. "
            f"Aangetroffen: {', '.join(sorted(rapporten)) or 'geen'}. "
            f"Vereist: {', '.join(vereiste_cfk)}."
        )

    datasets = {rapport.dataset_file for rapport in rapporten.values()}
    if len(datasets) > 1:
        overzicht = ", ".join(
            f"{cfk}={rapport.dataset_file}" for cfk, rapport in sorted(rapporten.items())
        )
        raise NulmetingError(
            f"De rapporten gaan over verschillende RDF-bestanden ({overzicht}). "
            f"Toets ze op dezelfde dataset."
        )

    return Nulmeting(
        dataset_file=datasets.pop(),
        reports=rapporten,
        meetbereik=Meetbereik.van(volledige_cfk or vereiste_cfk, vereiste_cfk),
    )
