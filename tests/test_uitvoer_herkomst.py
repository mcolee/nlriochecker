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
import re
import sqlite3
from dataclasses import fields, replace
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
from nlriochecker.meting import Meetbereik, laad_nulmeting
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
from nlriochecker.uitvoer import gpkg
from nlriochecker.uitvoer.bevindingen import (
    CSV_KOLOMMEN,
    CSV_VELD_NAAR_KOLOM,
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
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
from nlriochecker.uitvoer.melding import (
    GEEN_ONDERDRUKKING,
    Melding,
    Onderdrukking,
    bouw_meldingen,
)
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer

BRON = Path(__file__).resolve().parents[1] / "src"
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
RUNDATUM = date(2026, 8, 17)

# Aanroepen waarmee een module een bestand kan wegzetten zonder langs
# `uitvoer.herkomst` te gaan. Een eerdere versie was een lijst van drie substrings;
# een probe met `pad.open("w")`, `write_bytes` en `DataFrame.to_json` liep daar
# dwars doorheen.
#
# Patronen in plaats van substrings, om twee redenen. Het Nederlandse `knopen(`
# eindigt op `open(`, dus een kale substring vlagt de halve check-engine. En
# `pad.open("rb")` is lezen: alleen een modus met w, a of x telt als schrijven.
DIRECTE_SCHRIJVERS = (
    r"\.to_(csv|json|excel|parquet)\(",
    r"\.write_(text|bytes)\(",
    # `pad.open("w")` en `open(pad, "w")`. De modus moet op zijn eigen plek staan;
    # anders telt `path.open(encoding=..., newline="")` als schrijven.
    r"\bopen\(\s*[\"'][^\"']*[wax]",
    r"\bopen\([^,)]+,\s*[\"'][^\"']*[wax]",
    r"\bjson\.dump",
    r"\bpickle\.dump",
    r"\bshutil\.(copy|move)",
    r"\bos\.write\b",
)

# Modules die wel zelf een bestand mogen schrijven, met de reden erbij. Een
# allowlist naast de patronen: bij alleen een verbodslijst is de volgende
# ontsnappingsroute altijd een die niemand bedacht had.
MAG_ZELF_SCHRIJVEN = {
    # De enige herkomstdragende schrijver; hierom draait de hele regel.
    "nlriochecker/uitvoer/herkomst.py",
    # De GeoPackage is een sqlite-bestand; dat gaat niet door een tekstschrijver
    # heen. Hij draagt zijn herkomst in het veld `gereedschap` van `gwsw_run`, en
    # `test_geopackage_runtabel_noemt_het_gereedschap` bewaakt dat.
    "nlriochecker/uitvoer/gpkg.py",
    # Schrijft de datasetcache, geen uitvoer voor een lezer. De cachesleutel draagt
    # de broncode van de lader, dus een cache van een andere versie wordt genegeerd.
    "nlriochecker/cache.py",
}

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
    een bestand wegzet draagt geen herkomst, en geen enkele test op de bestaande
    bestanden zou dat opmerken.

    De vrijstelling gaat op het volledige pad en niet op de bestandsnaam: met een
    naamvergelijking zou een nieuwe `uitvoer/ext/herkomst.py` zichzelf vrijstellen.
    Wie hier een module aan `MAG_ZELF_SCHRIJVEN` toevoegt, schrijft de reden erbij.
    """
    overtreders = sorted(
        pad.relative_to(BRON).as_posix()
        for pad in BRON.rglob("*.py")
        if pad.relative_to(BRON).as_posix() not in MAG_ZELF_SCHRIJVEN
        and any(
            re.search(patroon, pad.read_text(encoding="utf-8")) for patroon in DIRECTE_SCHRIJVERS
        )
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


def test_csv_kolommen_dekken_elk_meldingveld() -> None:
    """Elk veld van `Melding` heeft een CSV-kolom, en elke kolom een veld.

    Direct groen geschreven -- de kolomlijst was al compleet. De test is het
    vangnet: krijgt `Melding` een veld zonder plek in `CSV_VELD_NAAR_KOLOM`, of
    komt er een kolom bij die geen veld draagt, dan valt hij hier om in plaats van
    dat de CSV stilzwijgend een gegeven mist dat de JSON wel heeft.
    """
    assert set(CSV_VELD_NAAR_KOLOM) == {veld.name for veld in fields(Melding)}

    gedekt = [kolom for kolommen in CSV_VELD_NAAR_KOLOM.values() for kolom in kolommen]
    assert sorted(gedekt) == sorted(CSV_KOLOMMEN)


def test_gpkg_kolommen_dekken_elk_meldingveld() -> None:
    """Elk veld van `Melding` is in de GeoPackage-meldingentabel verantwoord.

    Direct groen geschreven -- de kolomlijst was al compleet, op één bekende
    weglating na: `object2_label` heeft in de tabel nooit een kolom gehad en staat
    daarom expliciet leeg in de afbeelding. De test is het vangnet: een nieuw veld
    zonder vermelding in `MELDING_VELD_NAAR_KOLOM` valt hier om. `stapel_aantal` en
    `stapel_nr` zijn uit de hele meldingenlijst afgeleid en horen bij geen veld.
    """
    assert set(gpkg.MELDING_VELD_NAAR_KOLOM) == {veld.name for veld in fields(Melding)}

    gedekt = [kolom for kolommen in gpkg.MELDING_VELD_NAAR_KOLOM.values() for kolom in kolommen]
    namen = [kolom.naam for kolom in gpkg.MELDING_KOLOMMEN]
    assert sorted(gedekt + ["stapel_aantal", "stapel_nr"]) == sorted(namen)


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
        typeringspoort_toegepast=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert document["schema_versie"] == SCHEMA_VERSIE == "1.1"
    assert document["gereedschap"] == gereedschap()
    assert document["run_datum"] == "2026-08-17"
    assert document["dataset"] == "dewolden.ttl"
    assert document["cfk_set"] == ["Hyd", "MdsPlan"]
    assert document["volledig"] is False
    assert document["typeringspoort_toegepast"] is False
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
        typeringspoort_toegepast=False,
    )

    document = json.loads(pad.read_text(encoding="utf-8"))
    assert [rij["melding_id"] for rij in document["meldingen"]] == ["a", "b"]


def test_voorstel_is_gereserveerd_en_wordt_niet_geschreven(toets: CheckRun) -> None:
    """Fase B is buiten scope; een altijd-null veld zou een belofte zijn.

    Toetst de echte route. Een eerdere versie voerde een handgemaakte dict in en
    kon daardoor per constructie niet falen: kreeg `Melding` morgen een veld
    `voorstel`, dan bleef hij groen terwijl het contract stil gebroken was.
    """
    rijen = meldingen_json(bouw_meldingen(toets, RUNDATUM))

    assert "voorstel" not in {veld.name for veld in fields(Melding)}
    assert all("voorstel" not in rij for rij in rijen)


def test_schrijf_json_is_compacte_utf8(tmp_path: Path) -> None:
    """Geen ontsnapte codepunten, en compact geschreven: wie het met het oog wil
    lezen heeft `bevindingen.md`, dus de JSON draagt geen inspringing meer."""
    pad = schrijf_json(
        tmp_path / "b.json",
        [{"melding_id": "a", "object_label": "Ruinerwold \u00e9\u00e9n, Dwingelo\u00f6"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
        typeringspoort_toegepast=False,
    )

    tekst = pad.read_text(encoding="utf-8")
    # Niet-ASCII staat er als teken, niet als \uXXXX-ontsnapping.
    assert "Ruinerwold \u00e9\u00e9n, Dwingelo\u00f6" in tekst
    assert "\\u00e9" not in tekst
    # Compact: geen inspringing en geen spaties rond scheidingstekens.
    assert tekst.startswith('{"schema_versie":')
    assert tekst.endswith("\n")


def test_schrijf_uitvoer_levert_de_json_uit_dezelfde_meldingenstroom(
    toets: CheckRun, tmp_path: Path
) -> None:
    """De vier uitvoervormen tellen hetzelfde aantal meldingen.

    Dit is de eigenschap waar de single-writer-regel voor bestaat: liepen ze uit
    elkaar, dan zou hier een verschil staan.
    """
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM)

    assert uitvoer.json is not None
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    csv = pd.read_csv(tmp_path / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    assert document["aantal_meldingen"] == len(document["meldingen"]) == len(csv)


def test_twee_identieke_runs_geven_een_identiek_json_bestand(
    toets: CheckRun, tmp_path: Path
) -> None:
    """Diffbaar tussen meetmomenten; anders is elke trendvergelijking ruis."""
    eerste = schrijf_uitvoer(toets, tmp_path / "a", RUNDATUM).json
    tweede = schrijf_uitvoer(toets, tmp_path / "b", RUNDATUM).json

    assert eerste is not None and tweede is not None
    assert eerste.read_text(encoding="utf-8") == tweede.read_text(encoding="utf-8")


def test_json_zonder_geopackage_blijft_geschreven(toets: CheckRun, tmp_path: Path) -> None:
    """De twee vlaggen staan los van elkaar."""
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_geopackage=False)

    assert uitvoer.geopackage is None
    assert uitvoer.json is not None


def test_zonder_json_laat_het_bestand_weg(toets: CheckRun, tmp_path: Path) -> None:
    """Wie de JSON niet wil, houdt de andere drie."""
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_json=False)

    assert uitvoer.json is None
    assert not (tmp_path / FILE_CHECKS_JSON).exists()
    assert uitvoer.markdown.exists()


def test_json_schemadocument_beschrijft_elk_meldingveld() -> None:
    """`docs/json-schema.md` is een tweede plek waar de veldnamen staan.

    Een afnemer programmeert tegen dat document. Komt er een veld bij `Melding` en
    blijft de beschrijving achter, dan is het contract stil onvolledig geworden --
    en dat valt niemand op, want het bestand zelf klopt wel.
    """
    doc = (Path(__file__).resolve().parents[1] / "docs" / "json-schema.md").read_text(
        encoding="utf-8"
    )

    ontbreekt = [veld.name for veld in fields(Melding) if f"`{veld.name}`" not in doc]

    assert ontbreekt == []


def test_json_schemadocument_beschrijft_elk_enveloppeveld(tmp_path: Path) -> None:
    """`docs/json-schema.md` beschrijft ook de envelop, niet alleen de meldingvelden.

    De drifttest hierboven loopt over `fields(Melding)`; de enveloppevelden vielen
    erbuiten. Daardoor kon een niet-gedocumenteerd enveloppeveld ongemerkt bijkomen
    zonder dat een test omviel (issue #52). Deze test schrijft een envelop met alle
    optionele velden erin en eist dat elk topniveauveld in het document beschreven staat.
    """
    pad = schrijf_json(
        tmp_path / "envelop.json",
        [{"melding_id": "a"}],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=False,
        typeringspoort_toegepast=True,
        markering="een voorbehoud",
        gebieden=["Koekange", "Ruinen"],
        onderdrukking=Onderdrukking(
            klassen=("Leiding",), checks=("TOP-001",), per_check={"TOP-001": 1}, per_klasse={}
        ),
        checks=[
            {
                "check_id": "TOP-001",
                "bekeken": 3,
                "bekeken_scope": "analyseset",
                "populatie": "netwerkknopen",
            }
        ],
    )
    document = json.loads(pad.read_text(encoding="utf-8"))
    doc = (Path(__file__).resolve().parents[1] / "docs" / "json-schema.md").read_text(
        encoding="utf-8"
    )

    ontbreekt = [veld for veld in document if f"`{veld}`" not in doc]
    ontbreekt += [veld for veld in document["checks"][0] if f"`{veld}`" not in doc]

    assert ontbreekt == []


def test_json_schemadocument_noemt_de_geschreven_schemaversie() -> None:
    """De versie in het document en die in de code horen dezelfde te zijn."""
    doc = (Path(__file__).resolve().parents[1] / "docs" / "json-schema.md").read_text(
        encoding="utf-8"
    )

    assert f'"schema_versie": "{SCHEMA_VERSIE}"' in doc


def test_alle_uitvoervormen_zeggen_hetzelfde_over_de_cfk_set(
    toets: CheckRun, tmp_path: Path
) -> None:
    """De assertie waar het hele ontwerp op rust.

    Markdown, GeoPackage en JSON leiden hun CFK-uitspraak alle drie uit hetzelfde
    `Meetbereik` af. Zou een van hen zijn eigen conclusie trekken, dan staat hier
    een verschil. De CSV doet bewust niet mee: de CFK-set hoort bij de run en niet
    bij de melding, dus hij staat in de envelop en in `gwsw_run` (zie BO-7).
    """
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"]))

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.json is not None and uitvoer.geopackage is not None
    markdown = uitvoer.markdown.read_text(encoding="utf-8")
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        ((cfk_set, volledig),) = verbinding.execute("select cfk_set, volledig from gwsw_run")
    finally:
        verbinding.close()

    assert "**Onvolledige meting:** getoetst op Hyd, MdsPlan;" in markdown
    assert document["cfk_set"] == ["Hyd", "MdsPlan"] and document["volledig"] is False
    assert (cfk_set, volledig) == ("Hyd, MdsPlan", 0)


def test_alle_uitvoervormen_zwijgen_bij_een_volledige_meting(
    toets: CheckRun, tmp_path: Path
) -> None:
    """De keerzijde: op de volle set getoetst zegt geen van hen iets over een gebrek."""
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, VEREIST))

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.json is not None and uitvoer.geopackage is not None
    assert "Onvolledige meting" not in uitvoer.markdown.read_text(encoding="utf-8")
    assert "Geen nulmeting" not in uitvoer.markdown.read_text(encoding="utf-8")
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    assert document["cfk_set"] == VEREIST and document["volledig"] is True


def test_een_run_zonder_meetbereik_zwijgt_nergens(toets: CheckRun, tmp_path: Path) -> None:
    """Zonder opgegeven bereik melden alle drie 'niet gemeten', niemand zwijgt.

    Dit was het gat: `meetbereik` mocht None zijn, en dan zette de Markdown geen
    markering terwijl de JSON `volledig: false` beweerde en de GeoPackage `("", 0)`.
    Drie uitvoervormen zeiden "niet volledig gemeten" en de vierde zweeg.
    """
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM)

    assert uitvoer.json is not None and uitvoer.geopackage is not None
    assert "**Geen nulmeting:**" in uitvoer.markdown.read_text(encoding="utf-8")
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    assert document["cfk_set"] == [] and document["volledig"] is False
    assert document["typeringspoort_toegepast"] is False


def _envelop(pad: Path, **extra: object) -> dict[str, object]:
    """Schrijft een minimale JSON en leest de envelop terug."""
    geschreven = schrijf_json(
        pad,
        [],
        run_datum=RUNDATUM,
        dataset="d.ttl",
        cfk_set=["Hyd"],
        volledig=True,
        typeringspoort_toegepast=False,
        **extra,  # type: ignore[arg-type]
    )
    document: dict[str, object] = json.loads(geschreven.read_text(encoding="utf-8"))
    return document


def test_json_zonder_gebied_noemt_er_geen(tmp_path: Path) -> None:
    """Een run zonder studiegebieden blijft byte-voor-byte wat hij was."""
    document = _envelop(tmp_path / "b.json")

    assert "gebied" not in document
    assert "gebieden" not in document


def test_json_van_een_gebied_noemt_het(tmp_path: Path) -> None:
    assert _envelop(tmp_path / "b.json", gebied="Noord")["gebied"] == "Noord"


def test_totaal_json_noemt_alle_gebieden(tmp_path: Path) -> None:
    """De totaalsynthese hoort bij geen enkel gebied en bij ze allemaal."""
    document = _envelop(tmp_path / "b.json", gebieden=["Noord", "Zuid"])

    assert document["gebied"] is None
    assert document["gebieden"] == ["Noord", "Zuid"]


def test_json_zonder_onderdrukking_draagt_het_veld_niet(tmp_path: Path) -> None:
    """Optioneel en additief: een run zonder lijsten blijft byte-voor-byte gelijk (BO-49)."""
    zonder = _envelop(tmp_path / "zonder.json")
    leeg = _envelop(tmp_path / "leeg.json", onderdrukking=GEEN_ONDERDRUKKING)

    assert "onderdrukt" not in zonder
    assert "onderdrukt" not in leeg
    assert (tmp_path / "zonder.json").read_text(encoding="utf-8") == (
        tmp_path / "leeg.json"
    ).read_text(encoding="utf-8")


def test_json_met_onderdrukking_draagt_de_lijsten_en_de_telling(tmp_path: Path) -> None:
    """De telling hoort bij de run; de CSV draagt hem niet (BO-49)."""
    document = _envelop(
        tmp_path / "b.json",
        onderdrukking=Onderdrukking(
            klassen=("Leiding",), checks=("TOP-001",), per_check={"TOP-001": 1}, per_klasse={}
        ),
    )

    assert document["onderdrukt"] == {"klassen": ["Leiding"], "checks": ["TOP-001"], "meldingen": 1}
    assert document["schema_versie"] == "1.1"


def test_json_zonder_checks_draagt_het_veld_niet(tmp_path: Path) -> None:
    """Optioneel en additief, net als `onderdrukt`: geen checks, geen veld (issue #77)."""
    document = _envelop(tmp_path / "b.json")

    assert "checks" not in document


def test_json_labelt_per_check_waarover_bekeken_geteld_is(toets: CheckRun, tmp_path: Path) -> None:
    """Elke check draagt de scope van zijn noemer en zijn declaratie (issue #77).

    Zonder label mengt `bekeken` een rol op de analyseset, dezelfde rol op de
    volledige export en kenmerkinstanties, en zijn de percentages die erop delen
    onderling onvergelijkbaar. `populatie` is de declaratie en geen noemer: zonder
    rollen zijn dat de kenmerken (RVZ-011), en zonder beide is het leeg (ADM-007).
    """
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_geopackage=False)

    assert uitvoer.json is not None
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    per_check = {rij["check_id"]: rij for rij in document["checks"]}

    assert [rij["check_id"] for rij in document["checks"]] == sorted(per_check)
    assert len(per_check) == len(toets.outcomes)
    assert per_check["ADM-002"]["bekeken_scope"] == "volledige_export"
    assert per_check["ATTR-014"]["bekeken_scope"] == "attribuut_instanties"
    assert per_check["ATTR-014"]["populatie"] == "alle kenmerken"
    assert per_check["RVZ-011"]["populatie"] == (
        "Drempelbreedte, Drempelniveau, Maaiveldhoogte, Putdekselniveau"
    )
    assert per_check["ADM-007"]["populatie"] == ""
    assert all(rij["populatie"] != "de hele export" for rij in document["checks"])
    assert per_check["TOP-001"] == {
        "check_id": "TOP-001",
        "bekeken": next(o.examined for o in toets.outcomes if o.check_id == "TOP-001"),
        "bekeken_scope": "analyseset",
        "populatie": "leidingen, netwerkknopen, vrijvervalrioolleidingen",
    }


def test_de_csv_krijgt_de_checkscope_niet(toets: CheckRun, tmp_path: Path) -> None:
    """Bekeken hoort bij de check, niet bij de rij -- dezelfde scheiding als de CFK-set."""
    uitvoer = schrijf_uitvoer(toets, tmp_path, RUNDATUM, met_geopackage=False)

    assert uitvoer.csv is not None
    kolommen = list(pd.read_csv(uitvoer.csv, sep=";", encoding="utf-8").columns)

    assert "bekeken_scope" not in kolommen
    assert "Gaat over" not in kolommen
    assert "Populatie" not in kolommen
    assert "Bekeken" not in kolommen
