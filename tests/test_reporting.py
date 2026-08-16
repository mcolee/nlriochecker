"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from gwswpijplijn.analysis import analyze
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import CheckContext, run_checks
from gwswpijplijn.comparison import compare_metingen
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import assess_coverage
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.errors import PipelineError, StudyAreaError
from gwswpijplijn.meting import laad_nulmeting
from gwswpijplijn.reporting import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_MARKDOWN,
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    write_check_report,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from gwswpijplijn.studiegebied import load_study_area

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


@pytest.fixture
def analyse(shacl_drieluik: list[Path]):
    """De analyse van de mini-nulmeting."""
    return analyze(laad_nulmeting(shacl_drieluik, VEREIST))


def test_schrijft_samenvatting_en_csv(analyse, tmp_path: Path) -> None:
    markdown_path, csv_path = write_reports(analyse, tmp_path / "uitvoer")

    assert markdown_path.name == FILE_MARKDOWN
    assert csv_path.name == FILE_CSV
    tabel = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    assert set(tabel["CFK"]) == {"Hyd", "MdsPlan", "MdsProj"}


def test_samenvatting_meldt_ontbrekende_dataset(analyse, tmp_path: Path) -> None:
    markdown_path, _ = write_reports(analyse, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "dewolden_orox.ttl" in tekst
    assert "## Typeringspoort" in tekst
    # Zonder dataset hoort er geen score te staan, maar wel een uitleg waarom niet.
    assert "geen OroX-dataset meegegeven" in tekst


def test_dekkingrapport(analyse, tmp_path: Path) -> None:
    coverage = assess_coverage(analyse, load_coverage_config())
    markdown_path, csv_path = write_coverage_report(coverage, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == FILE_COVERAGE_MARKDOWN
    assert csv_path.name == FILE_COVERAGE_CSV
    assert "RVZ-003" in tekst
    assert "niet goedgekeurd" in tekst
    assert "RVZ-002, RVZ-003" in tekst


def test_vergelijkingsrapport(analyse, tmp_path: Path) -> None:
    comparison = compare_metingen(analyse, analyse, load_coverage_config())
    markdown_path, csv_path, objects_path = write_comparison_reports(comparison, tmp_path)

    assert markdown_path.name == FILE_COMPARISON_MARKDOWN
    assert "# Trendvergelijking dewolden_orox.ttl" in markdown_path.read_text(encoding="utf-8")
    verschillen = pd.read_csv(csv_path, sep=";", encoding="utf-8")
    assert set(verschillen["Niveau"]) == {"vorm", "objecttype"}
    objecten = pd.read_csv(objects_path, sep=";", encoding="utf-8")
    assert set(objecten["Status"]) == {"gebleven"}


def test_uitvoer_overschrijft_nooit_de_invoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    invoermap = tmp_path / "invoer"
    invoermap.mkdir()
    paden = []
    for bron, naam in zip(shacl_drieluik, [FILE_MARKDOWN, "b.csv", "c.csv"], strict=True):
        doel = invoermap / naam
        doel.write_bytes(bron.read_bytes())
        paden.append(doel)
    analyse = analyze(laad_nulmeting(paden, VEREIST))

    with pytest.raises(PipelineError, match="invoerbestand"):
        write_reports(analyse, invoermap)


def test_checkrapport_meldt_het_studiegebied(tmp_path: Path) -> None:
    dataset = load_dataset(TTL_DIR / "top001_losliggende_put.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())
    run = run_checks(context, ["TOP-001"])
    assert len(run.findings) == 1

    # Een gebied rond put A en B, maar niet rond de losliggende put C op (1200, 2500):
    # er liggen dus wel objecten in, alleen niet het object van de bevinding.
    gebied_pad = tmp_path / "gebied.geojson"
    gebied_pad.write_text(
        json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[990, 1990], [1060, 1990], [1060, 2010], [990, 2010]]],
            }
        ),
        encoding="utf-8",
    )
    gebied = load_study_area(gebied_pad)
    beperkt = run.beperk_tot_studiegebied(gebied)

    markdown_path, csv_path = write_check_report(beperkt, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == FILE_CHECKS_MARKDOWN
    assert csv_path.name == FILE_CHECKS_CSV
    assert "Studiegebied" in tekst
    assert beperkt.findings == []
    assert sum(outcome.weggelaten for outcome in beperkt.outcomes) == 1


def test_studiegebied_zonder_enig_object_faalt_hard() -> None:
    """Een gebied naast het beheergebied levert anders stilzwijgend een leeg rapport.

    Nul bevindingen bij wel aanwezige objecten is een geldige uitkomst; nul objecten
    is een verkeerde laagkeuze of een verkeerd gebied, en dat hoort te knallen in
    plaats van als schone data te lezen.
    """
    dataset = load_dataset(TTL_DIR / "top001_losliggende_put.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())
    run = run_checks(context, ["TOP-001"])

    # Het vierkant ligt op (0, 0)-(100, 100); de fixture rond (1000, 2000).
    gebied = load_study_area(Path(__file__).parent / "fixtures" / "gis" / "vierkant.gpkg")

    with pytest.raises(StudyAreaError, match="geen GWSW-objecten"):
        run.beperk_tot_studiegebied(gebied)


def _fixtureconfig():
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _checkrun(bestand: str, *check_ids: str, config=None):
    """Draait checks op een TTL-fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=config or _fixtureconfig())
    return run_checks(context, list(check_ids) or None)


def test_bevindingen_csv_draagt_de_uitgebreide_kolommen(tmp_path: Path) -> None:
    """De CSV is het volledige archief; het GIS en het rapport zijn afgeleiden."""
    run = _checkrun("top011_hartlijnkruising.ttl", "TOP-011")

    _, csv_path = write_check_report(run, tmp_path)
    tabel = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    # De bestaande kolommen houden hun naam en plaats; hernoemen breekt bestaande
    # verwerking zonder dat er iets tegenover staat.
    assert list(tabel.columns)[:9] == [
        "Check",
        "Ernst",
        "Dimensie",
        "Label",
        "Object",
        "Melding",
        "TyperingBetrouwbaar",
        "X",
        "Y",
    ]
    nieuw = [
        "MeldingID",
        "Categorie",
        "Bron",
        "Object2Label",
        "Object2",
        "Waarde",
        "Drempel",
        "ClusterID",
        "Scope",
        "Gebied",
        "Prioriteit",
        "Systemisch",
        "RunDatum",
        "Dataset",
    ]
    assert [kolom for kolom in nieuw if kolom not in tabel.columns] == []


def test_bevindingen_csv_zet_de_foutlocatie_in_x_en_y(tmp_path: Path) -> None:
    """De coordinaat stond in de meldingtekst; als kolom is hij bruikbaar."""
    run = _checkrun("top011_hartlijnkruising.ttl", "TOP-011")

    _, csv_path = write_check_report(run, tmp_path)
    rij = pd.read_csv(csv_path, sep=";", encoding="utf-8").iloc[0]

    assert pd.notna(rij["X"]) and pd.notna(rij["Y"])
    assert rij["Object2"].startswith("http")


def test_rapport_toont_standaard_alle_bevindingen(tmp_path: Path) -> None:
    """Afkappen zonder het te zeggen leest als 'dit is alles'."""
    run = _checkrun("top013_parallel.ttl", "TOP-013")
    assert len(run.findings) == 3

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    for bevinding in run.findings:
        assert bevinding.object_label in tekst


def test_afkap_is_configureerbaar_en_wordt_gemeld(tmp_path: Path) -> None:
    config = _fixtureconfig()
    config.rapport.max_bevindingen_per_check = 1
    run = _checkrun("top013_parallel.ttl", "TOP-013", config=config)

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "2 bevindingen niet getoond" in tekst


def test_rapport_opent_met_de_rode_draad(tmp_path: Path) -> None:
    """De synthese hoort voor de tabellen te staan, niet erachter."""
    run = _checkrun("net003_tegen_de_richting.ttl")

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "**Rode draad**" in tekst
    assert tekst.index("**Rode draad**") < tekst.index("Samenvatting per check")


def test_rapport_zonder_rode_draad_heeft_geen_lege_kop(tmp_path: Path) -> None:
    """Een enkele losliggende put heeft geen gezamenlijke oorzaak, dus geen kop."""
    run = _checkrun("top001_losliggende_put.ttl", "TOP-001")
    assert run.findings

    markdown_path, _ = write_check_report(run, tmp_path)

    assert "Rode draad" not in markdown_path.read_text(encoding="utf-8")


def test_clusterduiding_telt_de_getoonde_bevindingen(tmp_path: Path) -> None:
    """De duiding hoort te slaan op wat in het rapport staat, niet op de hele dataset.

    Dataset-breed liggen er twee losse deelstelsels; het studiegebied dekt er een.
    Een telling over de volledige dataset zou hier 2 melden bij 1 bevinding -- op De
    Wolden werd dat "174 deelstelsels" bij 24 bevindingen.
    """
    run = _checkrun("net001_twee_losse_deelstelsels.ttl", "NET-001")
    assert len(run.findings) == 2

    gebied = load_study_area(
        Path(__file__).parent / "fixtures" / "gis" / "rond_deelstelsel_cd.geojson"
    )
    beperkt = run.beperk_tot_studiegebied(gebied)
    assert len(beperkt.findings) == 1

    markdown_path, _ = write_check_report(beperkt, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "betreffen 1 deelstelsel (ds-C)" in tekst
    assert "2 deelstelsels" not in tekst
