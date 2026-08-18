"""Tests voor het samenstellen van een nulmeting uit SHACL-rapporten."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.errors import NulmetingError
from nlriochecker.meting import Meetbereik, laad_nulmeting

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]


def test_volledige_nulmeting(shacl_drieluik: list[Path]) -> None:
    meting = laad_nulmeting(shacl_drieluik, VEREIST)

    assert meting.dataset_file == "dewolden_orox.ttl"
    assert meting.cfks == ["Hyd", "MdsPlan", "MdsProj"]
    assert meting.timestamps_differ is True


def test_ontbrekende_cfk_is_een_harde_fout(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="mist conformiteitsklasse"):
        laad_nulmeting([mini_hyd_shacl], VEREIST)


def test_zonder_rapporten(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="minstens een"):
        laad_nulmeting([], VEREIST)


def test_dubbele_cfk(mini_hyd_shacl: Path) -> None:
    with pytest.raises(NulmetingError, match="Twee rapporten voor CFK"):
        laad_nulmeting([mini_hyd_shacl, mini_hyd_shacl], ["Hyd"])


def test_verschillende_datasets(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    afwijkend = tmp_path / "ander.csv"
    tekst = shacl_drieluik[0].read_text(encoding="utf-8")
    afwijkend.write_text(
        tekst.replace("dewolden_orox.ttl", "andere_gemeente.ttl"), encoding="utf-8"
    )

    with pytest.raises(NulmetingError, match="verschillende RDF-bestanden"):
        laad_nulmeting([afwijkend, shacl_drieluik[1], shacl_drieluik[2]], VEREIST)


def test_eigen_eisenlijst(mini_hyd_shacl: Path) -> None:
    # De vereiste klassen komen uit de projectconfig, niet uit de code.
    meting = laad_nulmeting([mini_hyd_shacl], ["Hyd"])

    assert meting.cfks == ["Hyd"]


def test_meetbereik_op_de_volle_set_is_volledig() -> None:
    """Alle klassen gekozen betekent volledig en niets ontbrekend."""
    bereik = Meetbereik.van(VEREIST, VEREIST)

    assert bereik.volledig
    assert bereik.ontbreekt == ()
    assert bereik.cfk_tekst == "Hyd, MdsPlan, MdsProj"


def test_meetbereik_sorteert_en_ontdubbelt() -> None:
    """De schrijfwijze voor GeoPackage en JSON is vast, wat de beller ook aanlevert."""
    bereik = Meetbereik.van(["MdsProj", "Hyd", "MdsPlan"], ["MdsPlan", "Hyd", "Hyd"])

    assert bereik.gekozen == ("Hyd", "MdsPlan")
    assert bereik.volledige_set == ("Hyd", "MdsPlan", "MdsProj")


def test_meetbereik_op_een_deelset_noemt_wat_ontbreekt() -> None:
    """Een deelset is niet volledig en weet welke klassen buiten de meting vielen."""
    bereik = Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"])

    assert not bereik.volledig
    assert bereik.ontbreekt == ("MdsProj",)


def test_meetbereik_zonder_meting_is_niet_volledig() -> None:
    """Een run zonder nulmeting is een eigen toestand, geen deelset van nul klassen."""
    bereik = Meetbereik.niet_gemeten(VEREIST)

    assert not bereik.gemeten
    assert not bereik.volledig
    assert bereik.gekozen == ()
    assert bereik.cfk_tekst == ""
    assert bereik.ontbreekt == ("Hyd", "MdsPlan", "MdsProj")


def test_nulmeting_draagt_het_meetbereik(shacl_drieluik: list[Path]) -> None:
    """De volledige drieluik levert een gemeten, volledig bereik."""
    meting = laad_nulmeting(shacl_drieluik, VEREIST)

    assert meting.meetbereik.volledig
    assert meting.meetbereik.gekozen == ("Hyd", "MdsPlan", "MdsProj")


def test_nulmeting_op_een_deelset_kent_de_volle_set(mini_hyd_shacl: Path) -> None:
    """De volle set komt uit de projectconfig, niet uit wat er aangeleverd is.

    Zonder dat onderscheid kan geen rapport melden wat er ontbreekt: een deelset
    zou dan altijd "volledig" heten.
    """
    meting = laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST)

    assert not meting.meetbereik.volledig
    assert meting.meetbereik.ontbreekt == ("MdsPlan", "MdsProj")


def test_laad_nulmeting_weigert_een_rapport_voor_een_niet_gekozen_cfk(
    shacl_drieluik: list[Path],
) -> None:
    """Een rapport buiten de gekozen set is een fout, geen stille overslag.

    Wie op een deelset toetst en per ongeluk alle rapporten meegeeft, moet dat
    horen; anders zegt de markering "MdsProj ontbreekt" terwijl het bestand er lag.
    """
    with pytest.raises(NulmetingError, match="MdsProj"):
        laad_nulmeting(shacl_drieluik, ["Hyd", "MdsPlan"], VEREIST)
