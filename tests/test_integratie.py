"""Integratietest op de volledige De Wolden-detailrapporten."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gwswpijplijn.analyse import MELDING_TE_GLOBAAL_PREFIX
from gwswpijplijn.paar import laad_paar
from gwswpijplijn.rapportage import schrijf_rapportage

DATAMAP = Path(__file__).resolve().parents[1] / "data"
MDS_VOLLEDIG = DATAMAP / "dewolden_nulmeting.csv"
HYD_VOLLEDIG = DATAMAP / "dewolden_nulmeting_1.csv"

pytestmark = [
    pytest.mark.integratie,
    pytest.mark.skipif(
        not (MDS_VOLLEDIG.exists() and HYD_VOLLEDIG.exists()),
        reason="de volledige De Wolden-bestanden staan niet in data/",
    ),
]


def _onafhankelijke_telling(pad: Path) -> dict[str, object]:
    """Telt het bestand na met een kale csv.reader, buiten de parser om."""
    with pad.open(encoding="cp1252", newline="") as bestand:
        rijen = list(csv.reader(bestand, delimiter=";"))

    meldingen = rijen[2:]
    benoemd = {(rij[2], rij[3]) for rij in meldingen if rij[3].strip()}
    te_globaal = {
        (rij[2], rij[3])
        for rij in meldingen
        if rij[3].strip() and rij[1].startswith(MELDING_TE_GLOBAAL_PREFIX)
    }
    return {
        "regels": len(meldingen),
        "som": sum(int(rij[0]) for rij in meldingen),
        "benoemd": len(benoemd),
        "te_globaal": len(te_globaal),
    }


@pytest.fixture(scope="module")
def paar():
    """Het volledige rapportenpaar van De Wolden, eenmalig ingelezen."""
    return laad_paar(MDS_VOLLEDIG, HYD_VOLLEDIG)


def test_metadata(paar) -> None:
    assert paar.dataset == "DeWolden"
    assert paar.mds.rapport.cfk == "MdsPlan"
    assert paar.hyd.rapport.cfk == "Hyd"


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_totalen_komen_overeen_met_onafhankelijke_telling(paar, cfk: str) -> None:
    analyse = getattr(paar, cfk)
    telling = _onafhankelijke_telling(analyse.rapport.bronbestand)

    assert len(analyse.rapport.meldingen) == telling["regels"]
    assert analyse.totaal_aantal == telling["som"]
    assert int(analyse.per_melding["Aantal"].sum()) == telling["som"]
    assert int(analyse.per_objecttype["Aantal"].sum()) == telling["som"]
    assert int(analyse.per_melding_objecttype["Aantal"].sum()) == telling["som"]


@pytest.mark.parametrize("cfk", ["mds", "hyd"])
def test_typeringspoort_komt_overeen_met_onafhankelijke_telling(paar, cfk: str) -> None:
    analyse = getattr(paar, cfk)
    telling = _onafhankelijke_telling(analyse.rapport.bronbestand)
    poort = analyse.typeringspoort

    assert poort.aantal_benoemde_objecten == telling["benoemd"]
    assert poort.aantal_te_globaal == telling["te_globaal"]


def test_bekende_kerncijfers(paar) -> None:
    # Vastgelegde cijfers van de De Wolden-rapporten van 2026-08-14.
    assert paar.mds.totaal_aantal == 24938
    assert paar.hyd.totaal_aantal == 47440
    assert paar.mds.typeringspoort.aantal_te_globaal == 1228
    assert paar.mds.typeringspoort.aantal_benoemde_objecten == 10146
    assert paar.mds.typeringspoort.score == pytest.approx(87.9, abs=0.05)
    assert paar.hyd.typeringspoort.aantal_te_globaal == 0


def test_rapportage_op_volledige_bestanden(paar, tmp_path: Path) -> None:
    markdown_pad, csv_pad = schrijf_rapportage(paar, tmp_path)

    assert "DeWolden" in markdown_pad.read_text(encoding="utf-8")
    assert csv_pad.stat().st_size > 0
