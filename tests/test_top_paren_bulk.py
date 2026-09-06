"""TDD-test voor de bulk-paarvorm van TOP-006/010/011 (issue #145).

De drie nabijheidschecks zochten hun kandidaatparen per streng met `_buren`; ze doen dat
nu in bulk met `_paren` (één STRtree-query over alle lijnen tegelijk). `_buren` blijft als
orakel staan: de bulkvorm moet exact dezelfde gerichte (a, b)-indexparen opleveren, zowel
met een vaste marge (TOP-006/011) als met een marge per streng (TOP-010).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from gwsw_orox_helpers.dataset import load_dataset

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.meetkunde import half_diameter_m
from nlriochecker.checks.topologie import _buren, _Nabijheid, _nabijheid, _paren

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

FIXTURES = [
    "top_nabijheid_scope.ttl",
    "top006_drempels.ttl",
    "top006_overlappende_streng.ttl",
    "top010_buffer_kruising.ttl",
    "top011_hartlijnkruising.ttl",
]


def _config() -> CheckConfig:
    """De standaardconfig met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _context(bestand: str) -> CheckContext:
    """Een context over een fixture, zonder een check te draaien."""
    return CheckContext(dataset=load_dataset(TTL_DIR / bestand, []), config=_config())


def _bulk(a: np.ndarray, b: np.ndarray) -> set[tuple[int, int]]:
    """De gerichte indexparen die `_paren` teruggeeft, als set."""
    return {(int(i), int(j)) for i, j in zip(a, b, strict=True)}


def _orakel(nabijheid: _Nabijheid, marges: list[float]) -> set[tuple[int, int]]:
    """De gerichte (a, b)-indexparen die `_buren` per streng oplevert.

    `marges[i]` is de zoekafstand waarmee streng `i` bevraagd wordt; een vaste marge
    geef je als een lijst met overal dezelfde waarde.
    """
    index_van = {conduit.uri: i for i, conduit in enumerate(nabijheid.conduits)}
    paren: set[tuple[int, int]] = set()
    for i, conduit in enumerate(nabijheid.conduits):
        for ander in _buren(nabijheid, conduit, marges[i]):
            paren.add((i, index_van[ander.uri]))
    return paren


@pytest.mark.parametrize("bestand", FIXTURES)
@pytest.mark.parametrize("marge", [0.0, 0.02, 1.0, 5.0])
def test_paren_matcht_het_buren_orakel_met_vaste_marge(bestand: str, marge: float) -> None:
    """TOP-006 en TOP-011 bevragen met één vaste marge over alle strengen."""
    nabijheid = _nabijheid(_context(bestand))
    if nabijheid.tree is None:
        pytest.skip("geen nabijheidsleidingen met geometrie in deze fixture")

    a, b = _paren(nabijheid, predicate="dwithin", distance=marge)

    assert _bulk(a, b) == _orakel(nabijheid, [marge] * len(nabijheid.conduits))


@pytest.mark.parametrize("bestand", FIXTURES)
def test_paren_matcht_het_buren_orakel_met_marge_per_streng(bestand: str) -> None:
    """TOP-010 bevraagt met een marge per streng (`straal_i + grootste + marge`)."""
    nabijheid = _nabijheid(_context(bestand))
    if nabijheid.tree is None:
        pytest.skip("geen nabijheidsleidingen met geometrie in deze fixture")

    stralen = np.array(
        [half_diameter_m(c.breedte_mm, c.hoogte_mm) for c in nabijheid.conduits], dtype=float
    )
    grootste = float(stralen.max()) if stralen.size else 0.0
    afstanden = stralen + grootste + 0.1

    a, b = _paren(nabijheid, predicate="dwithin", distance=afstanden)

    assert _bulk(a, b) == _orakel(nabijheid, [float(d) for d in afstanden])


@pytest.mark.parametrize("bestand", FIXTURES)
def test_paren_laat_geen_streng_met_zichzelf_paren(bestand: str) -> None:
    """`_paren` filtert het zelfpaar weg, net als `_buren` op de URI doet."""
    nabijheid = _nabijheid(_context(bestand))
    if nabijheid.tree is None:
        pytest.skip("geen nabijheidsleidingen met geometrie in deze fixture")

    a, b = _paren(nabijheid, predicate="dwithin", distance=100.0)

    assert all(int(i) != int(j) for i, j in zip(a, b, strict=True))
