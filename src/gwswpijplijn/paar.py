"""Het verplichte rapportenpaar: een Mds/MdsPlan-rapport naast een Hyd-rapport."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gwswpijplijn.analyse import RapportAnalyse, analyseer
from gwswpijplijn.fouten import RapportPaarFout
from gwswpijplijn.rapport import lees_detailrapport

CFK_MDS = frozenset({"Mds", "MdsPlan"})
CFK_HYD = frozenset({"Hyd"})


@dataclass(frozen=True)
class RapportPaar:
    """Een dataset die aan beide verplichte conformiteitsklassen is getoetst."""

    dataset: str
    mds: RapportAnalyse
    hyd: RapportAnalyse

    @property
    def tijdstempels_verschillen(self) -> bool:
        """Geeft aan of beide rapporten uit verschillende toetsmomenten komen."""
        return self.mds.rapport.tijdstempel != self.hyd.rapport.tijdstempel


def laad_paar(mds_pad: Path, hyd_pad: Path) -> RapportPaar:
    """Leest en analyseert beide detailrapporten en toetst de harde eisen.

    De dataset moet altijd aan beide conformiteitsklassen getoetst zijn: Mds of
    MdsPlan en Hyd. Klopt de klasse of de datasetnaam niet, dan volgt een
    `RapportPaarFout`.
    """
    mds = lees_detailrapport(Path(mds_pad))
    hyd = lees_detailrapport(Path(hyd_pad))

    _controleer_cfk(mds.cfk, CFK_MDS, mds.bronbestand, hyd.cfk, "--mds")
    _controleer_cfk(hyd.cfk, CFK_HYD, hyd.bronbestand, mds.cfk, "--hyd")

    if mds.dataset != hyd.dataset:
        raise RapportPaarFout(
            f"De rapporten gaan over verschillende datasets: {mds.dataset!r} "
            f"({mds.bronbestand}) tegenover {hyd.dataset!r} ({hyd.bronbestand}). "
            f"Beide rapporten moeten dezelfde dataset betreffen."
        )

    return RapportPaar(dataset=mds.dataset, mds=analyseer(mds), hyd=analyseer(hyd))


def _controleer_cfk(
    gevonden: str,
    toegestaan: frozenset[str],
    bronbestand: Path,
    andere_cfk: str,
    optie: str,
) -> None:
    """Controleert de conformiteitsklasse van een rapport tegen de toegestane waarden."""
    if gevonden in toegestaan:
        return

    verwacht = " of ".join(sorted(toegestaan))
    melding = (
        f"Het rapport bij {optie} ({bronbestand}) is getoetst aan CFK {gevonden!r}, "
        f"maar {verwacht} wordt verwacht."
    )
    if andere_cfk in toegestaan:
        melding += " Vermoedelijk zijn --mds en --hyd verwisseld."
    raise RapportPaarFout(melding)
