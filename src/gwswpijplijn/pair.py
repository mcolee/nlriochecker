"""Het verplichte rapportenpaar: een Mds/MdsPlan-rapport naast een Hyd-rapport."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gwswpijplijn.analysis import ReportAnalysis, analyze
from gwswpijplijn.errors import ReportPairError
from gwswpijplijn.report import read_detail_report

CFK_MDS = frozenset({"Mds", "MdsPlan"})
CFK_HYD = frozenset({"Hyd"})


@dataclass(frozen=True)
class ReportPair:
    """Een dataset die aan beide verplichte conformiteitsklassen is getoetst."""

    dataset: str
    mds: ReportAnalysis
    hyd: ReportAnalysis

    @property
    def timestamps_differ(self) -> bool:
        """Geeft aan of beide rapporten uit verschillende toetsmomenten komen."""
        return self.mds.report.timestamp != self.hyd.report.timestamp


def load_pair(mds_path: Path, hyd_path: Path) -> ReportPair:
    """Leest en analyseert beide detailrapporten en toetst de harde eisen.

    De dataset moet altijd aan beide conformiteitsklassen getoetst zijn: Mds of
    MdsPlan en Hyd. Klopt de klasse of de datasetnaam niet, dan volgt een
    `ReportPairError`.
    """
    mds = read_detail_report(Path(mds_path))
    hyd = read_detail_report(Path(hyd_path))

    _check_cfk(mds.cfk, CFK_MDS, mds.source_file, hyd.cfk, "--mds")
    _check_cfk(hyd.cfk, CFK_HYD, hyd.source_file, mds.cfk, "--hyd")

    if mds.dataset != hyd.dataset:
        raise ReportPairError(
            f"De rapporten gaan over verschillende datasets: {mds.dataset!r} "
            f"({mds.source_file}) tegenover {hyd.dataset!r} ({hyd.source_file}). "
            f"Beide rapporten moeten dezelfde dataset betreffen."
        )

    return ReportPair(dataset=mds.dataset, mds=analyze(mds), hyd=analyze(hyd))


def _check_cfk(
    found: str,
    allowed: frozenset[str],
    source_file: Path,
    other_cfk: str,
    option: str,
) -> None:
    """Controleert de conformiteitsklasse van een rapport tegen de toegestane waarden."""
    if found in allowed:
        return

    expected = " of ".join(sorted(allowed))
    message = (
        f"Het rapport bij {option} ({source_file}) is getoetst aan CFK {found!r}, "
        f"maar {expected} wordt verwacht."
    )
    if other_cfk in allowed:
        message += " Vermoedelijk zijn --mds en --hyd verwisseld."
    raise ReportPairError(message)
