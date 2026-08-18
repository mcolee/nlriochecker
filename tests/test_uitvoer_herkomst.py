"""Tests voor de herkomstvermelding in elk uitvoerbestand.

Elk bestand dat deze package oplevert noemt de package en het versienummer waarmee
het gemaakt is. De drie uitvoervormen zeggen dat met dezelfde string, uit dezelfde
bron; die tests staan hier bij elkaar zodat een nieuwe uitvoervorm zonder herkomst
hier opvalt en niet stilzwijgend meelift.

De sweep onderaan is de eigenlijke waarborg: hij verbiedt een tweede schrijver in
`src/`. De tests daarboven toetsen de bestanden die er nu zijn, maar zouden een
nieuw rapport dat zijn eigen `to_csv` aanroept nooit zien.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from nlriochecker import __version__
from nlriochecker.analysis import MetingAnalysis, analyze
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.comparison import compare_metingen
from nlriochecker.config import load_coverage_config
from nlriochecker.coverage import assess_coverage
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import laad_nulmeting
from nlriochecker.reporting import (
    FILE_COMPARISON_CSV,
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    FILE_OBJECT_CHANGES_CSV,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from nlriochecker.uitvoer import schrijf_uitvoer
from nlriochecker.uitvoer.bevindingen import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_MARKDOWN,
    meldingen_json,
)
from nlriochecker.uitvoer.herkomst import (
    KOLOM_GEREEDSCHAP,
    PAKKET,
    SCHEMA_VERSIE,
    gereedschap,
    herkomstregel,
    schrijf_csv,
    schrijf_json,
    schrijf_markdown,
)
from nlriochecker.uitvoer.melding import Melding, bouw_meldingen

BRON = Path(__file__).resolve().parents[1] / "src"
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
RUNDATUM = date(2026, 8, 17)

# De schrijvers die de herkomst zouden omzeilen als een module ze rechtstreeks
# aanriep in plaats van via `uitvoer.herkomst`. `json.dump` staat erbij sinds de
# JSON-export: een tweede JSON-schrijver zou een envelop zonder herkomst en zonder
# schemaversie kunnen wegzetten, en geen test op de bestaande bestanden zou dat zien.
DIRECTE_SCHRIJVERS = (".to_csv(", ".write_text(", "json.dump")

MARKDOWN_BESTANDEN = {
    FILE_MARKDOWN,
    FILE_COVERAGE_MARKDOWN,
    FILE_COMPARISON_MARKDOWN,
    FILE_CHECKS_MARKDOWN,
}
CSV_BESTANDEN = {
    FILE_CSV,
    FILE_COVERAGE_CSV,
    FILE_COMPARISON_CSV,
    FILE_OBJECT_CHANGES_CSV,
    FILE_CHECKS_CSV,
}


@pytest.fixture
def analyse(shacl_drieluik: list[Path]) -> MetingAnalysis:
    """De analyse van de mini-nulmeting."""
    return analyze(laad_nulmeting(shacl_drieluik, VEREIST))


@pytest.fixture
def toets() -> CheckRun:
    """Een toetsrun met ten minste een bevinding, zodat de CSV rijen krijgt."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "hgt004_bob_boven_deksel.ttl")
    return run_checks(CheckContext(dataset=dataset, config=config))


@pytest.fixture
def uitvoermap(analyse: MetingAnalysis, toets: CheckRun, tmp_path: Path) -> Path:
    """Een map met elk bestand dat deze package kan opleveren.

    De toetsuitvoer loopt via `schrijf_uitvoer`, dezelfde ingang als de CLI, zodat
    deze tests de echte route langslopen en niet een nagebouwde.
    """
    write_reports(analyse, tmp_path)
    write_coverage_report(assess_coverage(analyse, load_coverage_config()), tmp_path)
    write_comparison_reports(compare_metingen(analyse, analyse, load_coverage_config()), tmp_path)
    schrijf_uitvoer(toets, tmp_path, RUNDATUM)
    return tmp_path


def test_gereedschap_noemt_pakket_en_versie() -> None:
    """De herkomststring is de pakketnaam plus het nummer uit de packagemetadata."""
    assert gereedschap() == f"{PAKKET} {__version__}"
    assert PAKKET == "nlriochecker"


def test_gereedschap_volgt_het_versienummer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Het nummer komt bij elke aanroep uit `__version__`, ook de terugvalwaarde.

    Een broncheckout zonder installatie levert `0.0.0+onbekend`; dat hoort dan
    gewoon in het bestand te staan in plaats van een verzonnen nummer.
    """
    monkeypatch.setattr("nlriochecker.uitvoer.herkomst.__version__", "0.0.0+onbekend")

    assert gereedschap() == "nlriochecker 0.0.0+onbekend"


def test_herkomstregel_noemt_gereedschap_en_datum() -> None:
    """De Markdown-regel draagt zowel de versie als de datum van de run."""
    regel = herkomstregel(RUNDATUM)

    assert gereedschap() in regel
    assert "2026-08-17" in regel


def test_herkomstregel_valt_terug_op_vandaag() -> None:
    """Zonder rundatum staat de dag van schrijven in het rapport."""
    assert f"{date.today():%Y-%m-%d}" in herkomstregel()


def test_schrijf_markdown_zet_de_herkomst_onder_de_titel(tmp_path: Path) -> None:
    """Titel, lege regel, herkomst, lege regel, dan pas de romp."""
    pad = schrijf_markdown(tmp_path / "r.md", "# Titel", ["## Kop", "", "tekst"], RUNDATUM)

    assert pad.read_text(encoding="utf-8").splitlines() == [
        "# Titel",
        "",
        herkomstregel(RUNDATUM),
        "",
        "## Kop",
        "",
        "tekst",
    ]


def test_schrijf_markdown_zet_de_markering_onder_de_herkomst(tmp_path: Path) -> None:
    """De markering staat boven de romp, zodat geen lezer hem kan missen."""
    pad = schrijf_markdown(
        tmp_path / "r.md",
        "# Titel",
        ["## Kop"],
        RUNDATUM,
        markering="**Onvolledige meting:** getoetst op Hyd; MdsPlan ontbreekt.",
    )

    assert pad.read_text(encoding="utf-8").splitlines() == [
        "# Titel",
        "",
        herkomstregel(RUNDATUM),
        "",
        "**Onvolledige meting:** getoetst op Hyd; MdsPlan ontbreekt.",
        "",
        "## Kop",
    ]


def test_schrijf_markdown_zonder_markering_blijft_ongewijzigd(tmp_path: Path) -> None:
    """Zonder markering is de kop exact als voorheen: geen lege regel erbij."""
    pad = schrijf_markdown(tmp_path / "r.md", "# Titel", ["## Kop"], RUNDATUM)

    assert pad.read_text(encoding="utf-8").splitlines() == [
        "# Titel",
        "",
        herkomstregel(RUNDATUM),
        "",
        "## Kop",
    ]


def test_schrijf_csv_zet_de_herkomstkolom_achteraan(tmp_path: Path) -> None:
    """De kolom komt achter de bestaande, zodat kolomvolgorde niet verschuift."""
    pad = schrijf_csv(pd.DataFrame({"Check": ["TOP-001", "NET-004"]}), tmp_path / "t.csv")
    tabel = pd.read_csv(pad, sep=";", encoding="utf-8")

    assert list(tabel.columns) == ["Check", KOLOM_GEREEDSCHAP]
    assert list(tabel[KOLOM_GEREEDSCHAP]) == [gereedschap(), gereedschap()]


def test_schrijf_csv_houdt_gwsw_uris_heel(tmp_path: Path) -> None:
    """De reden voor een kolom in plaats van een `#`-regel: URI's dragen een `#`.

    Met een commentaarregel bovenaan zou `read_csv(comment="#")` de voor de hand
    liggende lezing zijn, en die kapt elke URI af op het fragmentteken.
    """
    uri = "http://sparql.gwsw.nl/dewolden#knp3437"
    pad = schrijf_csv(pd.DataFrame({"ObjectURI": [uri]}), tmp_path / "t.csv")

    assert pd.read_csv(pad, sep=";", encoding="utf-8")["ObjectURI"][0] == uri


def test_schrijf_csv_laat_de_meegegeven_tabel_ongemoeid(tmp_path: Path) -> None:
    """De schrijver werkt op een kopie; de beller houdt zijn eigen kolommen."""
    tabel = pd.DataFrame({"Check": ["TOP-001"]})
    schrijf_csv(tabel, tmp_path / "t.csv")

    assert list(tabel.columns) == ["Check"]


def test_schrijf_csv_verdraagt_een_lege_tabel(tmp_path: Path) -> None:
    """Een tabel zonder rijen levert wel de kolomkop op, en geen uitzondering."""
    pad = schrijf_csv(pd.DataFrame(), tmp_path / "leeg.csv")

    assert KOLOM_GEREEDSCHAP in pd.read_csv(pad, sep=";", encoding="utf-8").columns


def test_schrijf_csv_weigert_een_eigen_herkomstkolom(tmp_path: Path) -> None:
    """Een botsing overschrijven zou de kolom stil van plaats en waarde veranderen."""
    tabel = pd.DataFrame({KOLOM_GEREEDSCHAP: ["iets anders"], "Check": ["TOP-001"]})

    with pytest.raises(ValueError, match=KOLOM_GEREEDSCHAP):
        schrijf_csv(tabel, tmp_path / "t.csv")


def test_alle_markdown_rapporten_noemen_het_gereedschap(uitvoermap: Path) -> None:
    """Elk geschreven .md-bestand draagt de herkomst op de derde regel.

    Op de datum na: de toetsuitvoer draagt de rundatum, de nulmetingrapporten de
    dag van schrijven. Vastpinnen op een van beide zou de test morgen laten vallen.
    """
    paden = sorted(uitvoermap.glob("*.md"))

    assert {pad.name for pad in paden} == MARKDOWN_BESTANDEN
    for pad in paden:
        regels = pad.read_text(encoding="utf-8").splitlines()
        assert regels[0].startswith("# "), pad.name
        assert regels[2].startswith(f"*Gemaakt met {gereedschap()} op "), pad.name
        assert regels[2].endswith(".*"), pad.name


def test_alle_csv_bestanden_dragen_de_herkomstkolom(uitvoermap: Path) -> None:
    """Elk geschreven .csv-bestand draagt de herkomst achteraan, op elke rij."""
    paden = sorted(uitvoermap.glob("*.csv"))

    assert {pad.name for pad in paden} == CSV_BESTANDEN
    for pad in paden:
        tabel = pd.read_csv(pad, sep=";", encoding="utf-8")
        assert list(tabel.columns)[-1] == KOLOM_GEREEDSCHAP, pad.name
        assert not tabel.empty, pad.name
        assert (tabel[KOLOM_GEREEDSCHAP] == gereedschap()).all(), pad.name


def test_geopackage_runtabel_noemt_het_gereedschap(uitvoermap: Path) -> None:
    """De GeoPackage draagt dezelfde string in haar runmetadata."""
    (pad,) = uitvoermap.glob("*.gpkg")
    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        rijen = verbinding.execute("select gereedschap from gwsw_run").fetchall()
    finally:
        verbinding.close()

    assert rijen == [(gereedschap(),)]


def test_geen_enkele_module_schrijft_buiten_herkomst_om() -> None:
    """`herkomst.py` is de enige schrijver in `src/`.

    Dit is de waarborg waar de andere tests op leunen: een nieuw rapport dat zelf
    `to_csv` of `write_text` aanroept draagt geen herkomst, en geen enkele test op
    de bestaande bestanden zou dat opmerken.
    """
    overtreders = sorted(
        pad.relative_to(BRON).as_posix()
        for pad in BRON.rglob("*.py")
        if pad.name != "herkomst.py"
        and any(aanroep in pad.read_text(encoding="utf-8") for aanroep in DIRECTE_SCHRIJVERS)
    )

    assert overtreders == []


def test_meldingen_json_spiegelt_de_dataclass(toets: CheckRun) -> None:
    """Elk veld van Melding komt in de JSON terug, met dezelfde naam.

    De rijen komen uit `dataclasses.asdict` en niet uit een lijst met de hand
    opgeschreven veldnamen: die zou stilzwijgend achterlopen zodra Melding een veld
    krijgt, en dan mist de JSON een gegeven dat de CSV wel heeft.
    """
    rijen = meldingen_json(bouw_meldingen(toets, RUNDATUM))

    assert rijen
    assert {veld.name for veld in fields(Melding)} == set(rijen[0])


def test_meldingen_json_zet_de_foutlocatie_als_coordinatenpaar(toets: CheckRun) -> None:
    """[x, y] in EPSG:28992, of null; er wordt niet geherprojecteerd."""
    meldingen = bouw_meldingen(toets, RUNDATUM)

    rijen = meldingen_json(meldingen)

    for melding, rij in zip(meldingen, rijen, strict=True):
        if melding.foutlocatie is None:
            assert rij["foutlocatie"] is None
        else:
            assert rij["foutlocatie"] == [melding.foutlocatie.x, melding.foutlocatie.y]


def test_meldingen_json_is_serialiseerbaar(toets: CheckRun) -> None:
    """Een shapely Point overleeft json.dumps niet; daarom wordt hij omgezet."""
    rijen = meldingen_json(bouw_meldingen(toets, RUNDATUM))

    json.dumps(rijen)


def test_schrijf_json_draagt_de_envelop(tmp_path: Path) -> None:
    """Herkomst, schemaversie en CFK-set horen bij de run, niet bij een melding."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "b"}, {"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="dewolden.ttl",
        cfk_set=["Hyd", "MdsPlan"],
        volledig=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert document["schema_versie"] == SCHEMA_VERSIE == "1.0"
    assert document["gereedschap"] == gereedschap()
    assert document["run_datum"] == "2026-08-17"
    assert document["dataset"] == "dewolden.ttl"
    assert document["cfk_set"] == ["Hyd", "MdsPlan"]
    assert document["volledig"] is False
    assert document["aantal_meldingen"] == 2


def test_schrijf_json_sorteert_op_melding_id(tmp_path: Path) -> None:
    """Twee runs op dezelfde data geven een diffbaar bestand."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "b"}, {"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert [rij["melding_id"] for rij in document["meldingen"]] == ["a", "b"]


def test_schrijf_json_reserveert_voorstel_zonder_het_te_schrijven(tmp_path: Path) -> None:
    """Fase B is buiten scope; een altijd-null veld zou een belofte zijn."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    assert "voorstel" not in pad.read_text(encoding="utf-8")


def test_schrijf_json_is_leesbaar_utf8(tmp_path: Path) -> None:
    """Geen ontsnapte codepunten en twee spaties inspringen, voor inspectie met het oog."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "a", "object_label": "Rioolstraat Zuidwolde een"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
    )

    tekst = pad.read_text(encoding="utf-8")
    assert '\n  "schema_versie"' in tekst
    assert tekst.endswith("\n")
