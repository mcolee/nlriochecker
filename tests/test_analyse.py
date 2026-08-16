"""Tests voor de aggregaties en de typeringspoort."""

from __future__ import annotations

from pathlib import Path

from gwswpijplijn.analyse import analyseer
from gwswpijplijn.rapport import lees_detailrapport

# Het MdsPlan-uittreksel telt 20 meldingregels met samen Aantal 155.
MINI_MDS_TOTAAL = 155


def test_totaal_is_gewogen_som(mini_mds: Path) -> None:
    analyse = analyseer(lees_detailrapport(mini_mds))

    assert analyse.totaal_aantal == MINI_MDS_TOTAAL


def test_aggregaties_tellen_op_tot_het_totaal(mini_mds: Path) -> None:
    analyse = analyseer(lees_detailrapport(mini_mds))

    assert int(analyse.per_melding["Aantal"].sum()) == MINI_MDS_TOTAAL
    assert int(analyse.per_objecttype["Aantal"].sum()) == MINI_MDS_TOTAAL
    assert int(analyse.per_melding_objecttype["Aantal"].sum()) == MINI_MDS_TOTAAL
    assert int(analyse.per_melding["Regels"].sum()) == len(analyse.rapport.meldingen)


def test_aggregatie_is_aflopend_gesorteerd(mini_mds: Path) -> None:
    per_melding = analyseer(lees_detailrapport(mini_mds)).per_melding

    assert list(per_melding["Aantal"]) == sorted(per_melding["Aantal"], reverse=True)
    assert per_melding.iloc[0]["Type Melding"].startswith("Collectie ontbreekt")


def test_typeringspoort_telt_unieke_objecten(mini_mds: Path) -> None:
    poort = analyseer(lees_detailrapport(mini_mds)).typeringspoort

    # 16 benoemde objecten, waarvan 4 Overstortputten te globaal getypeerd zijn.
    assert poort.aantal_benoemde_objecten == 16
    assert poort.aantal_te_globaal == 4
    assert poort.score == 75.0
    assert list(poort.objecten.columns) == ["Type object", "Naam"]
    assert set(poort.objecten["Type object"]) == {"Overstortput"}


def test_typeringspoort_zonder_meldingen_is_volledig(mini_hyd: Path) -> None:
    poort = analyseer(lees_detailrapport(mini_hyd)).typeringspoort

    assert poort.aantal_te_globaal == 0
    assert poort.score == 100.0
    assert poort.objecten.empty
