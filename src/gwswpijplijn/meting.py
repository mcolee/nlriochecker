"""De nulmeting: de verzameling SHACL-rapporten over een dataset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from gwswpijplijn.errors import NulmetingError
from gwswpijplijn.shaclrapport import ShaclReport, lees_shacl_rapport


@dataclass(frozen=True)
class Nulmeting:
    """Een dataset die aan alle vereiste conformiteitsklassen getoetst is."""

    dataset_file: str
    reports: dict[str, ShaclReport]

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


def laad_nulmeting(paden: list[Path], vereiste_cfk: list[str]) -> Nulmeting:
    """Leest de SHACL-rapporten en toetst de harde eisen.

    Alle vereiste conformiteitsklassen moeten aanwezig zijn en alle rapporten
    moeten over hetzelfde RDF-bestand gaan; anders zeggen de uitkomsten niets over
    dezelfde dataset.
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

    return Nulmeting(dataset_file=datasets.pop(), reports=rapporten)
