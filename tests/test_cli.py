"""Tests voor de opdrachtregel."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from nlriochecker.cli import _BalkVoortgang, main
from nlriochecker.register import default_register_path
from nlriochecker.reporting import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
    FILE_CHECKS_MARKDOWN,
    FILE_COMPARISON_MARKDOWN,
    FILE_COVERAGE_CSV,
    FILE_COVERAGE_MARKDOWN,
    FILE_CSV,
    FILE_MARKDOWN,
    FILE_OBJECT_CHANGES_CSV,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"


def _shacl_args(paden: list[Path]) -> list[str]:
    """Bouwt de --shacl-argumenten voor een volledige nulmeting."""
    return [arg for pad in paden for arg in ("--shacl", str(pad))]


def test_analyseer_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["analyseer", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_MARKDOWN).exists()
    assert (uitvoer / FILE_CSV).exists()
    assert "Hyd, MdsPlan, MdsProj" in resultaat.output
    assert "Niet geraakte geschrapte checks: RVZ-002, RVZ-003" in resultaat.output


def test_ontbrekende_cfk_geeft_exitcode_1(mini_hyd_shacl: Path, tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main, ["analyseer", "--shacl", str(mini_hyd_shacl), "--output", str(tmp_path)]
    )

    assert resultaat.exit_code == 1
    assert "mist conformiteitsklasse" in resultaat.output


def test_dekking_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["dekking", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_COVERAGE_MARKDOWN).exists()
    assert (uitvoer / FILE_COVERAGE_CSV).exists()
    assert "RVZ-003   niet geraakt" in resultaat.output


def test_vergelijk_schrijft_uitvoer(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    argumenten = ["vergelijk"]
    for pad in shacl_drieluik:
        argumenten += ["--eerder", str(pad), "--later", str(pad)]
    resultaat = CliRunner().invoke(main, [*argumenten, "--output", str(uitvoer)])

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_COMPARISON_MARKDOWN).exists()
    assert (uitvoer / FILE_OBJECT_CHANGES_CSV).exists()
    assert "niet nieuwer dan de eerste" in resultaat.output


def test_toets_schrijft_uitvoer(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_CSV).exists()
    assert "Geen typeringspoort toegepast" in resultaat.output
    assert "TOP-001   F      1 bevinding" in resultaat.output


def test_toets_met_studiegebied_meldt_wat_wegvalt(tmp_path: Path) -> None:
    """Put C ligt los en ver buiten gebied en buffer, en komt dus niet in de analyseset.

    De check ziet hem niet eens, dus valt er niets meer weg op het moment dat het
    rapport wordt afgebakend. Het rapport blijft leeg, alleen op een andere manier
    dan toen de check nog over de volledige dataset liep.
    """
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--studiegebied",
            str(GIS_DIR / "rond_put_ab.geojson"),
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "Studiegebied" in resultaat.output
    assert "0 bevindingen buiten het gebied weggelaten" in resultaat.output
    tabel = pd.read_csv(uitvoer / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    assert tabel.empty


def test_toets_meldt_bevindingen_die_in_de_schil_wegvallen(tmp_path: Path) -> None:
    """Put C ligt in de contextschil (binnen de buffer), niet in de kern.

    Anders dan bij `test_toets_met_studiegebied_meldt_wat_wegvalt` ziet TOP-001
    put C dus wel en meldt hem als losliggend; die bevinding valt pas weg zodra
    het rapport na de checks tot de kern afgebakend wordt. De teller die dat
    meldt, is wat de klant vertelt wat hij niet te zien krijgt, en moet hier dus
    niet op nul blijven staan.
    """
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggend_in_de_schil.ttl"),
            "--check",
            "TOP-001",
            "--studiegebied",
            str(GIS_DIR / "rond_put_ab.geojson"),
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "1 bevinding buiten het gebied weggelaten" in resultaat.output
    tabel = pd.read_csv(uitvoer / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    assert tabel.empty


def test_toets_meldt_de_omvang_van_de_analyseset(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            "--studiegebied",
            str(GIS_DIR / "afbakening_gebied.geojson"),
            "--check",
            "NET-001",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "kern" in resultaat.output and "contextschil" in resultaat.output


def test_toets_gebruikt_shacl_voor_de_typeringspoort(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    bron = (TTL_DIR / "top001_losliggende_put.ttl").read_text(encoding="utf-8")
    bron += "\n:PutC rdf:type gwsw:Overstortput .\ngwsw:Overstortput rdfs:subClassOf gwsw:Put .\n"
    dataset = tmp_path / "met_overstortput.ttl"
    dataset.write_text(bron, encoding="utf-8")

    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(dataset),
            *_shacl_args(shacl_drieluik),
            "--check",
            "TOP-001",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "met typeringsvoorbehoud" in resultaat.output


def test_toets_meldt_onbekende_check(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--check",
            "TOP-999",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 1
    assert "TOP-999" in resultaat.output
    assert "Bekende checks" in resultaat.output


def test_toets_meldt_onleesbare_dataset(tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.ttl"
    stuk.write_text("dit is <geen turtle", encoding="utf-8")

    resultaat = CliRunner().invoke(
        main, ["toets", "--dataset", str(stuk), "--output", str(tmp_path)]
    )

    assert resultaat.exit_code == 1
    assert "geldige Turtle" in resultaat.output


def test_toets_meldt_afwijkende_codering(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "codering_cp850.ttl"),
            "--check",
            "TOP-001",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "geen geldige UTF-8" in resultaat.output


def test_ongeldige_config_geeft_exitcode_1(shacl_drieluik: list[Path], tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text("dit is [geen geldige toml", encoding="utf-8")

    resultaat = CliRunner().invoke(
        main,
        [
            "dekking",
            *_shacl_args(shacl_drieluik),
            "--config",
            str(stuk),
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 1
    assert "geldige TOML" in resultaat.output


def _drift_config(pad: Path) -> Path:
    """Een dekkingmapping die een andere registerversie noemt dan het register."""
    pad.write_text(
        'checkregister_versie = "0.6"\n'
        'bron = "x"\n'
        "[[check]]\n"
        'id = "ADM-001"\n'
        'onderwerp = "x"\n'
        'claim = "x"\n'
        'vereiste_cfk = ["Hyd"]\n'
        'bewijs = [{ vorm = "LengteLeiding_val" }]\n',
        encoding="utf-8",
    )
    return pad


def test_dekking_faalt_als_de_mapping_niet_bij_het_register_past(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """De dekkingclaim is het onderwerp van dit commando, dus drift is fataal."""
    register = default_register_path()
    if not register.exists():
        pytest.skip("het checkregister staat niet in data/")

    resultaat = CliRunner().invoke(
        main,
        [
            "dekking",
            *_shacl_args(shacl_drieluik),
            "--config",
            str(_drift_config(tmp_path / "drift.toml")),
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code == 1
    assert "0.6" in resultaat.output
    assert "0.8" in resultaat.output


def test_analyseer_meldt_de_drift_in_het_rapport(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """Hier is de dekking bijzaak, dus de lezer houdt een rapport dat het zelf zegt."""
    register = default_register_path()
    if not register.exists():
        pytest.skip("het checkregister staat niet in data/")

    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer",
            *_shacl_args(shacl_drieluik),
            "--config",
            str(_drift_config(tmp_path / "drift.toml")),
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_MARKDOWN).read_text(encoding="utf-8")
    assert "Dekking vervallen" in tekst
    assert "geverifieerd op checkregister 0.6" in tekst


def test_toets_weigert_een_studiegebied_zonder_objecten(tmp_path: Path) -> None:
    """Een leeg gebied hoort te knallen, niet een leeg rapport op te leveren."""
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--studiegebied",
            str(GIS_DIR / "vierkant.gpkg"),
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "geen GWSW-objecten" in resultaat.output
    assert not (tmp_path / "uitvoer").exists()


def test_toets_schrijft_ook_een_geopackage(tmp_path: Path) -> None:
    """De GIS-uitvoer hoort bij de standaardoplevering van een toets."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    gepakt = list(uitvoer.glob("dq_*.gpkg"))
    assert len(gepakt) == 1
    assert gepakt[0].name in resultaat.output


def test_geen_gpkg_slaat_de_gis_uitvoer_over(tmp_path: Path) -> None:
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "top001_losliggende_put.ttl"),
            "--check",
            "TOP-001",
            "--geen-gpkg",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert list(uitvoer.glob("*.gpkg")) == []
    assert (uitvoer / FILE_CHECKS_CSV).exists()


def test_aantallen_komen_overeen_in_md_csv_en_gpkg(tmp_path: Path) -> None:
    """De drie uitvoervormen komen uit dezelfde meldingenstroom; dat hoort te blijken."""
    import sqlite3

    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "hgt004_bob_boven_deksel.ttl"),
            "--output",
            str(uitvoer),
        ],
    )
    assert resultaat.exit_code == 0, resultaat.output

    tabel = pd.read_csv(uitvoer / FILE_CHECKS_CSV, sep=";", encoding="utf-8")
    per_check_csv = tabel["Check"].value_counts().to_dict()

    gpkg = next(uitvoer.glob("dq_*.gpkg"))
    con = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        per_check_gpkg = dict(
            con.execute("select check_id, count(*) from meldingen group by check_id")
        )
        overzicht = dict(
            con.execute(
                "select check_id, aantal_meldingen from overzicht_checks where aantal_meldingen > 0"
            )
        )
    finally:
        con.close()

    tekst = (uitvoer / FILE_CHECKS_MARKDOWN).read_text(encoding="utf-8")

    assert per_check_csv == per_check_gpkg
    assert per_check_csv == overzicht
    for check_id, aantal in per_check_csv.items():
        kop = f"## {check_id} — "
        assert kop in tekst
        staart = tekst.split(kop, 1)[1]
        assert f"Bevindingen ({aantal})" in staart.split("\n## ", 1)[0]


def test_toets_met_cfk_deelset_markeert_het_rapport(tmp_path: Path, mini_hyd_shacl: Path) -> None:
    """Een deelsetrun zegt het in het rapport, niet alleen op de opdrachtregel."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--shacl",
            str(mini_hyd_shacl),
            "--cfk",
            "Hyd",
            "--geen-cache",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_CHECKS_MARKDOWN).read_text(encoding="utf-8")
    assert "**Onvolledige meting:** getoetst op Hyd;" in tekst
    assert "MdsPlan, MdsProj ontbreken" in tekst


def test_toets_zonder_shacl_meldt_dat_er_niet_gemeten_is(tmp_path: Path) -> None:
    """Stilte mag niet lezen als 'alles gecontroleerd'."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--geen-cache",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_CHECKS_MARKDOWN).read_text(encoding="utf-8")
    assert "**Geen nulmeting:**" in tekst


def test_cfk_met_onbekende_waarde_somt_de_toegestane_op(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """Een typefout hoort de lijst te tonen in plaats van stil een lege set te maken."""
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer",
            *_shacl_args(shacl_drieluik),
            "--cfk",
            "Hydro",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "Hydro" in resultaat.output
    assert "Hyd, MdsPlan, MdsProj" in resultaat.output


def test_cfk_deelset_weigert_een_rapport_buiten_de_keuze(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """Alle drie meegeven bij --cfk Hyd is een fout, geen stille overslag."""
    resultaat = CliRunner().invoke(
        main,
        [
            "analyseer",
            *_shacl_args(shacl_drieluik),
            "--cfk",
            "Hyd",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "MdsPlan" in resultaat.output


def test_analyseer_zonder_cfk_gedraagt_zich_als_voorheen(
    tmp_path: Path, shacl_drieluik: list[Path]
) -> None:
    """De standaardrun verandert niet: geen markering, alle drie vereist."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main, ["analyseer", *_shacl_args(shacl_drieluik), "--output", str(uitvoer)]
    )

    assert resultaat.exit_code == 0, resultaat.output
    tekst = (uitvoer / FILE_MARKDOWN).read_text(encoding="utf-8")
    assert "Onvolledige meting" not in tekst
    assert "Geen nulmeting" not in tekst


def test_dekking_met_cfk_deelset(tmp_path: Path, mini_hyd_shacl: Path) -> None:
    """Ook `dekking` accepteert een deelset en markeert zijn rapport."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "dekking",
            "--shacl",
            str(mini_hyd_shacl),
            "--cfk",
            "Hyd",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "**Onvolledige meting:**" in (uitvoer / FILE_COVERAGE_MARKDOWN).read_text(
        encoding="utf-8"
    )


def test_vergelijk_met_cfk_deelset(tmp_path: Path, mini_hyd_shacl: Path) -> None:
    """`vergelijk` heeft de vlag nodig; zonder hem eist hij alle drie de klassen."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "vergelijk",
            "--eerder",
            str(mini_hyd_shacl),
            "--later",
            str(mini_hyd_shacl),
            "--cfk",
            "Hyd",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "**Onvolledige meting:**" in (uitvoer / FILE_COMPARISON_MARKDOWN).read_text(
        encoding="utf-8"
    )


def test_cfk_typefout_valt_ook_op_zonder_shacl(tmp_path: Path) -> None:
    """De keuze wordt getoetst voordat blijkt dat er niets te meten valt.

    Zonder deze toets accepteert juist de aanroepvorm die niets met de vlag doet
    hem stilzwijgend, en denkt de gebruiker dat hij op Hydro getoetst heeft.
    """
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--cfk",
            "Hydro",
            "--geen-cache",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code != 0
    assert "Hydro" in resultaat.output
    assert "Hyd, MdsPlan, MdsProj" in resultaat.output


def test_cfk_zonder_shacl_meldt_dat_de_vlag_niets_doet(tmp_path: Path) -> None:
    """Een vlag die geen effect heeft hoort dat te zeggen."""
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--cfk",
            "Hyd",
            "--geen-cache",
            "--output",
            str(tmp_path / "uitvoer"),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert "--cfk doet niets zonder --shacl" in resultaat.output


def test_toets_schrijft_de_json_standaard_mee(tmp_path: Path) -> None:
    """Symmetrie met de GeoPackage: standaard erbij, uit te zetten met een vlag."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--geen-cache",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_JSON).exists()
    assert str(uitvoer / FILE_CHECKS_JSON) in resultaat.output


def test_toets_met_geen_json_laat_het_bestand_weg(tmp_path: Path) -> None:
    """De vlag doet wat hij zegt."""
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--geen-cache",
            "--geen-json",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert not (uitvoer / FILE_CHECKS_JSON).exists()
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()


def test_toets_draait_met_de_voortgangsbalk(tmp_path: Path) -> None:
    """Rooktest: de adapter mag de run niet breken, ook niet zonder terminal.

    CliRunner is geen tty; click zet de balk dan zelf uit. Er komt hier geen eigen
    TTY-toets bij, dus deze test is de enige waarborg dat de adapter in die
    omgeving niet omvalt -- en dat de balk de uitvoer op stdout niet vervuilt.
    """
    uitvoer = tmp_path / "uitvoer"
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--geen-cache",
            "--output",
            str(uitvoer),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (uitvoer / FILE_CHECKS_MARKDOWN).exists()
    assert (uitvoer / FILE_CHECKS_JSON).exists()
    # stdout houdt de tellingen en de paden; de balk hoort er niet in te staan.
    assert resultaat.stdout.startswith("schoon.ttl: 2 knooppunten")
    assert "TTL laden" not in resultaat.stdout
    # In een niet-interactieve omgeving echoot click per fase een enkele regel op
    # stderr. Een regel per check zou hier veertig regels ruis geven.
    assert resultaat.stderr.splitlines() == ["TTL laden", "Checks", "GeoPackage"]


class _StukkeStroom(io.TextIOBase):
    """Een stroom die bij elke schrijfactie afbreekt, zoals een gesloten pijp."""

    def write(self, s: str) -> int:
        """Gooit altijd, net als schrijven naar een pijp zonder lezer."""
        raise BrokenPipeError(32, "Broken pipe")

    def isatty(self) -> bool:
        """Geen terminal; click zet de balk dan in verborgen modus."""
        return False


def test_balkvoortgang_laat_geen_schrijffout_ontsnappen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Voortgang is weergave en mag een run nooit om zeep helpen.

    `nlriochecker toets ... 2>&1 | head -1` laat de lezer van stderr wegvallen.
    Zonder afscherming sloeg de BrokenPipeError dwars door `run_checks` heen:
    exitcode 1 en geen enkel uitvoerbestand -- op De Wolden ruim drie minuten
    laadwerk kwijt omdat een balk niet getekend kon worden.

    Getoetst op de adapter zelf en niet via een pijplijn: of een echte pijp op tijd
    afbreekt hangt van buffergroottes en timing af, en zo'n test zou de invariant
    soms wel en soms niet bewaken.
    """
    monkeypatch.setattr(sys, "stderr", _StukkeStroom())
    voortgang = _BalkVoortgang()

    voortgang.start_fase("Checks", 3)
    voortgang.stap(label="TOP-001")
    voortgang.stap(label="TOP-002")
    voortgang.einde_fase()


def test_balkvoortgang_verdraagt_opeenvolgende_fasen() -> None:
    """Een tweede fase sluit de eerste; einde_fase zonder start is stil."""
    voortgang = _BalkVoortgang()

    voortgang.start_fase("TTL laden", 1)
    voortgang.stap(label="schoon.ttl")
    voortgang.start_fase("Checks", 2)
    voortgang.stap(label="TOP-001")
    voortgang.einde_fase()
    voortgang.einde_fase()


def test_toets_schrijft_per_gebied(tmp_path: Path) -> None:
    """Twee buurten in een bestand: twee submappen plus een totaalsynthese."""
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "hgt010_diameterverjonging.ttl"),
            "--studiegebied",
            str(GIS_DIR / "buurten_twee.gpkg"),
            "--check",
            "HGT-010",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (tmp_path / "noord" / FILE_CHECKS_CSV).exists()
    assert (tmp_path / "zuid" / FILE_CHECKS_CSV).exists()
    assert (tmp_path / "totaal" / "synthese.md").exists()
    assert "Gebied Noord:" in resultaat.output


def test_toets_beperkt_zich_tot_het_gekozen_gebied(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "hgt010_diameterverjonging.ttl"),
            "--studiegebied",
            str(GIS_DIR / "buurten_twee.gpkg"),
            "--gebied",
            "Noord",
            "--check",
            "HGT-010",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code == 0, resultaat.output
    assert (tmp_path / "noord").exists()
    assert not (tmp_path / "zuid").exists()
    assert "Selectie" in (tmp_path / "totaal" / "synthese.md").read_text(encoding="utf-8")


def test_toets_onbekend_gebied_noemt_de_beschikbare(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "hgt010_diameterverjonging.ttl"),
            "--studiegebied",
            str(GIS_DIR / "buurten_twee.gpkg"),
            "--gebied",
            "Oost",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code != 0
    assert "Noord, Zuid" in resultaat.stderr


def test_toets_gebied_zonder_studiegebied_faalt(tmp_path: Path) -> None:
    resultaat = CliRunner().invoke(
        main,
        [
            "toets",
            "--dataset",
            str(TTL_DIR / "schoon.ttl"),
            "--gebied",
            "Noord",
            "--output",
            str(tmp_path),
        ],
    )

    assert resultaat.exit_code != 0
    assert "--studiegebied" in resultaat.stderr
