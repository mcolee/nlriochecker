"""Tests voor de toetsloop over nul, een of veel studiegebieden.

De kerntest is de equivalentie-eis: een gebied uit een bestand met meerdere buurten
moet exact dezelfde meldingen opleveren als een losse run met alleen dat gebied.
Zonder die eigenschap is rapportage per gebied niet te vertrouwen.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.dataset import load_dataset
from nlriochecker.errors import StudyAreaError
from nlriochecker.meting import Meetbereik
from nlriochecker.studiegebied import load_studiegebieden
from nlriochecker.toetsloop import GebiedsRun, toets_gebieden
from nlriochecker.uitvoer.melding import bouw_meldingen

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
RUNDATUM = date(2026, 8, 18)


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _sleutels(gebiedsrun: GebiedsRun) -> set[tuple[str, str, str]]:
    """De meldingen van een run, herleid tot wat ze identificeert."""
    return {
        (melding.melding_id, melding.check_id, melding.object_uri)
        for melding in bouw_meldingen(gebiedsrun.run, RUNDATUM)
    }


def _draai(bestand: str | None, ttl: str = "afbakening_kern_en_schil.ttl") -> list[GebiedsRun]:
    """Draait de toetsloop op een fixture, met of zonder studiegebiedbestand."""
    gebieden = load_studiegebieden(GIS_DIR / bestand) if bestand is not None else None
    return toets_gebieden(
        load_dataset(TTL_DIR / ttl),
        gebieden,
        _config(),
        onbetrouwbaar=frozenset(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )


def test_per_gebied_gelijk_aan_een_losse_run() -> None:
    """De kerntest: hetzelfde gebied geeft dezelfde meldingen, samen of alleen."""
    samen = _draai("buurten_twee.gpkg")
    los = _draai("buurt_noord.gpkg")

    noord = next(run for run in samen if run.naam == "Noord")

    assert _sleutels(noord) == _sleutels(los[0])


def test_ook_het_tweede_gebied_is_equivalent() -> None:
    samen = _draai("buurten_twee.gpkg")
    los = _draai("buurt_zuid.gpkg")

    zuid = next(run for run in samen if run.naam == "Zuid")

    assert _sleutels(zuid) == _sleutels(los[0])


def test_de_analysesets_verschillen_per_gebied() -> None:
    """Anders zou de equivalentietest ook slagen als de afbakening niets deed."""
    noord, zuid = _draai("buurten_twee.gpkg")

    assert noord.run.analyseset is not None and zuid.run.analyseset is not None
    assert noord.run.analyseset.kern != zuid.run.analyseset.kern


def test_zonder_studiegebied_een_run_zonder_gebied() -> None:
    runs = _draai(None, "top001_losliggende_put.ttl")

    assert len(runs) == 1
    assert runs[0].gebied is None
    assert runs[0].map == ""
    assert runs[0].naam == ""


def test_een_gebied_krijgt_geen_submap() -> None:
    """Bij een enkel gebied blijft de uitvoer staan waar hij stond."""
    runs = _draai("buurt_noord.gpkg")

    assert len(runs) == 1
    assert runs[0].map == ""
    assert runs[0].naam == "Noord"


def test_twee_gebieden_krijgen_elk_een_mapnaam() -> None:
    runs = _draai("buurten_twee.gpkg")

    assert [run.map for run in runs] == ["noord", "zuid"]


def test_grensobject_verschijnt_in_beide_gebieden_met_hetzelfde_id() -> None:
    """Streng B-C raakt beide buurten; elk gebied ziet zijn eigen werkelijkheid.

    De melding-ID mag het gebied niet bevatten, anders is een grensobject in de
    synthese niet als een en hetzelfde defect te herkennen.
    """
    noord, zuid = _draai("buurten_twee.gpkg", "hgt010_diameterverjonging.ttl")

    gedeeld = {sleutel[0] for sleutel in _sleutels(noord)} & {
        sleutel[0] for sleutel in _sleutels(zuid)
    }

    assert gedeeld


def test_onbekend_gebied_faalt_met_de_beschikbare_namen() -> None:
    gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")

    with pytest.raises(StudyAreaError, match="Noord, Zuid"):
        gebieden.selecteer(["Oost"])
