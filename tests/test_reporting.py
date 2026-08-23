"""Tests voor de Markdown- en CSV-uitvoer."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from nlriochecker.afbakening import bouw_analyseset
from nlriochecker.analysis import analyze
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.comparison import compare_metingen
from nlriochecker.config import load_coverage_config
from nlriochecker.coverage import assess_coverage
from nlriochecker.dataset import load_dataset
from nlriochecker.errors import PipelineError, StudyAreaError
from nlriochecker.meting import laad_nulmeting
from nlriochecker.reporting import (
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
from nlriochecker.studiegebied import load_study_area
from test_analysis import dataset_met_verbindingsklasse, meting_met_verbindingsklasse

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


def test_samenvatting_noemt_een_onbeoordeelbare_verbindingsklasse(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """Een te globale verbindingsklasse is niet te wegen; dat hoort in het rapport.

    Zwijgen zou lezen als "beoordeeld en niets gevonden", terwijl de klasse juist
    niet naar objecten te herleiden is.
    """
    hyd, mdsplan, mdsproj = shacl_drieluik
    aangepast = meting_met_verbindingsklasse(mdsplan, tmp_path / "verbinding.csv")
    dataset = load_dataset(dataset_met_verbindingsklasse(tmp_path / "verbinding.ttl"))
    meting = laad_nulmeting([hyd, aangepast, mdsproj], VEREIST)

    markdown_path, _ = write_reports(analyze(meting, dataset), tmp_path / "uitvoer")
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "Niet beoordeeld: Afvoerrelatie" in tekst


def test_dekkingrapport(analyse, tmp_path: Path) -> None:
    coverage = assess_coverage(analyse, load_coverage_config())
    markdown_path, csv_path = write_coverage_report(coverage, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == FILE_COVERAGE_MARKDOWN
    assert csv_path.name == FILE_COVERAGE_CSV
    assert "ADM-001" in tekst
    assert "niet goedgekeurd" in tekst
    assert "raakt de nulmeting alle geschrapte checks" in tekst


def test_dekkingrapport_noemt_een_sentinel_zonder_bewijs(
    analyse, mapping_zonder_bewijs: Path, tmp_path: Path
) -> None:
    """De andere tak van dezelfde weergave: een check die de nulmeting niet raakt."""
    coverage = assess_coverage(analyse, load_coverage_config(mapping_zonder_bewijs))
    markdown_path, _ = write_coverage_report(coverage, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "niet goedgekeurd" in tekst
    assert "In deze dataset geldt dat voor: ADM-001." in tekst


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


def test_checkrapport_meldt_de_omvang_van_de_analyseset(tmp_path: Path) -> None:
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    gebied = load_study_area(
        Path(__file__).parent / "fixtures" / "gis" / "afbakening_gebied.geojson"
    )
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    analyseset = bouw_analyseset(dataset, gebied, config)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    # ADM-002 draait mee zodat de zin over checks met een volledig bereik iets te
    # noemen heeft; die zin wordt sinds de reparatie afgeleid uit de checks die
    # daadwerkelijk gedraaid hebben, niet meer hardcoded.
    run = run_checks(context, ["NET-001", "ADM-002"]).beperk_tot_studiegebied(gebied)

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert (
        f"Analyseset: {len(analyseset.kern)} objecten in de kern, "
        f"{len(analyseset.schil)} in de contextschil, van {analyseset.volledig_aantal} "
        "in de export." in tekst
    )
    assert (
        "Checks die over de hele populatie gaan (ADM-002) draaien op de volledige export." in tekst
    )


def test_checkrapport_noemt_ook_een_via_config_aangewezen_check(tmp_path: Path) -> None:
    """De opsomming moet ADM-002 (klasse-attribuut) en een via de config aangewezen
    check allebei noemen, gesorteerd, in plaats van alleen "ADM-002" hard te coderen.
    """
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    gebied = load_study_area(
        Path(__file__).parent / "fixtures" / "gis" / "afbakening_gebied.geojson"
    )
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    config.studiegebied.volledige_dataset_checks = ["ADM-002", "TOP-001"]
    analyseset = bouw_analyseset(dataset, gebied, config)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    run = run_checks(context, ["TOP-001", "ADM-002"]).beperk_tot_studiegebied(gebied)

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "(ADM-002, TOP-001)" in tekst


def test_checkrapport_blijft_zonder_analyseset_stil_over_de_analyseset(tmp_path: Path) -> None:
    """Zonder studiegebied is er geen analyseset en dus geen regel erover."""
    dataset = load_dataset(TTL_DIR / "top001_losliggende_put.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())
    run = run_checks(context, ["TOP-001"])

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "Analyseset" not in tekst


def test_checkrapport_meldt_strengen_zonder_netwerkverband(tmp_path: Path) -> None:
    """Wat de afbakening niet kon meewegen, hoort net zo goed in het rapport."""
    dataset = load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl")
    gebied = load_study_area(
        Path(__file__).parent / "fixtures" / "gis" / "afbakening_gebied.geojson"
    )
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    analyseset = replace(bouw_analyseset(dataset, gebied, config), strengen_zonder_netwerkverband=3)

    context = CheckContext(
        dataset=analyseset.dataset,
        config=config,
        volledige_dataset=dataset,
        analyseset=analyseset,
    )
    run = run_checks(context, ["NET-001"]).beperk_tot_studiegebied(gebied)

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "3 vrijvervalstrengen hebben" in tekst


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
        "ObjectURI",
        "Object2URI",
    ]
    assert [kolom for kolom in nieuw if kolom not in tabel.columns] == []


def test_bevindingen_csv_zet_de_foutlocatie_in_x_en_y(tmp_path: Path) -> None:
    """De coordinaat stond in de meldingtekst; als kolom is hij bruikbaar."""
    run = _checkrun("top011_hartlijnkruising.ttl", "TOP-011")

    _, csv_path = write_check_report(run, tmp_path)
    rij = pd.read_csv(csv_path, sep=";", encoding="utf-8").iloc[0]

    assert pd.notna(rij["X"]) and pd.notna(rij["Y"])
    assert "#" not in rij["Object2"]
    assert rij["Object2URI"].startswith("http")
    assert rij["Object2URI"].endswith(f"#{rij['Object2']}")


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
    Wolden en Hoogeveen werd dat "174 deelstelsels" bij 24 bevindingen.
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


def test_rapport_volgt_de_meegegeven_meldingen(tmp_path: Path) -> None:
    """Het rapport telt de meldingenstroom, niet opnieuw de bevindingen.

    Zolang beide toevallig dezelfde volgorde hebben valt het verschil niet op.
    Zodra ronde 2 nulmeting-meldingen aan de stroom toevoegt, zou een rapport dat
    zelf run.outcomes telt stilzwijgend te laag rapporteren terwijl CSV en GPKG dat
    niet doen. Deze test geeft een halve stroom mee en eist dat het rapport die
    volgt.
    """
    from nlriochecker.uitvoer.melding import bouw_meldingen

    run = _checkrun("top013_parallel.ttl", "TOP-013")
    # Alleen de checkmeldingen; de datasetsignalen (bron "dataset", issue #22) staan
    # los van wat deze test over het volgen van de meegegeven stroom aantoont.
    volledig = [m for m in bouw_meldingen(run, date(2026, 8, 16)) if m.bron == "register"]
    assert len(volledig) == 3

    markdown_path, csv_path = write_check_report(
        run, tmp_path, date(2026, 8, 16), meldingen=volledig[:2]
    )
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "Bevindingen (2)" in tekst
    assert "| TOP-013 |" in tekst and "| 2 |" in tekst
    assert len(pd.read_csv(csv_path, sep=";", encoding="utf-8")) == 2


def test_rapport_meldt_bevindingen_zonder_plek_op_de_kaart(tmp_path: Path) -> None:
    """Zwijgen hierover leest als "alles staat op de kaart".

    De GeoPackage telt ze in gwsw_run; wie alleen het rapport leest moet het daar
    ook zien. Op de fixtures en op De Wolden en Hoogeveen komt dit niet voor -- daarom wordt het
    hier met een aangepaste meldingenstroom afgedwongen.
    """
    import dataclasses

    from nlriochecker.uitvoer.melding import bouw_meldingen

    run = _checkrun("top013_parallel.ttl", "TOP-013")
    # Alleen de checkmeldingen: de datasetsignalen hebben zelf geen plek op de kaart en
    # zouden de telling die deze test afdwingt vertroebelen.
    meldingen = [m for m in bouw_meldingen(run, date(2026, 8, 16)) if m.bron == "register"]
    zonder = [dataclasses.replace(meldingen[0], foutlocatie=None), *meldingen[1:]]

    markdown_path, _ = write_check_report(run, tmp_path, date(2026, 8, 16), meldingen=zonder)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "1 melding heeft geen plek op de kaart" in tekst
    assert "TOP-013" in tekst


def test_rapport_zwijgt_als_elke_melding_een_plek_heeft(tmp_path: Path) -> None:
    from nlriochecker.uitvoer.melding import bouw_meldingen

    run = _checkrun("top013_parallel.ttl", "TOP-013")
    # De checkmeldingen hebben alle een plek; de datasetsignalen (issue #22) horen per
    # definitie geen plek te hebben en staan hier los van.
    meldingen = [m for m in bouw_meldingen(run, date(2026, 8, 16)) if m.bron == "register"]

    markdown_path, _ = write_check_report(run, tmp_path, date(2026, 8, 16), meldingen=meldingen)

    assert "geen plek op de kaart" not in markdown_path.read_text(encoding="utf-8")


def test_samenvatting_markeert_een_deelmeting(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    """Een deelset staat boven het rapport, niet ergens in een voetnoot."""
    analyse = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))

    markdown_path, _ = write_reports(analyse, tmp_path)

    regels = markdown_path.read_text(encoding="utf-8").splitlines()
    assert regels[4].startswith("**Onvolledige meting:**")
    assert "MdsPlan, MdsProj ontbreken" in regels[4]


def test_samenvatting_van_een_volledige_meting_draagt_geen_markering(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """Zonder deelset blijft het rapport byte-voor-byte als voorheen."""
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))

    markdown_path, _ = write_reports(analyse, tmp_path)

    assert "Onvolledige meting" not in markdown_path.read_text(encoding="utf-8")


def test_dekkingrapport_markeert_een_deelmeting(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    """Ook de dekkinganalyse zegt op hoeveel klassen zij steunt."""
    analyse = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))
    coverage = assess_coverage(analyse, load_coverage_config())

    markdown_path, _ = write_coverage_report(coverage, tmp_path)

    assert "**Onvolledige meting:**" in markdown_path.read_text(encoding="utf-8")


def test_vergelijkingsrapport_markeert_een_deelmeting(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    """Een trend over een deelset is een trend over minder dan de norm."""
    analyse = analyze(laad_nulmeting([mini_hyd_shacl], ["Hyd"], VEREIST))
    vergelijking = compare_metingen(analyse, analyse, load_coverage_config())

    markdown_path, _, _ = write_comparison_reports(vergelijking, tmp_path)

    assert "**Onvolledige meting:**" in markdown_path.read_text(encoding="utf-8")
