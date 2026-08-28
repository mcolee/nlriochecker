"""Tests voor de datakarakteristieken in de kop van het bevindingenrapport.

Dit zijn geen checks. Het gaat om eigenschappen van de aangeleverde dataset die
niet per object te herstellen zijn, maar die wel bepalen hoe de bevindingen
gelezen moeten worden: op welke precisie de datums staan, en hoeveel
inwinningsregistraties expliciet "onbekend" zeggen.
"""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.dataset import load_dataset, markeer_vulwaarden

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, Severity, run_checks
from nlriochecker.karakteristiek import bepaal_karakteristiek
from nlriochecker.reporting import write_check_report

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
FIXTURE = TTL_DIR / "karakteristiek_datums.ttl"


def _karakteristiek(config: CheckConfig | None = None):
    """De karakteristieken van de fixture."""
    return bepaal_karakteristiek(load_dataset(FIXTURE, []), config or load_check_config())


def _vulling(karakteristiek, kenmerk: str):
    """De inwinningsvulling van dit kenmerk."""
    return next(item for item in karakteristiek.inwinning if item.kenmerk == kenmerk)


def test_datumprecisie_wordt_per_kenmerk_geteld() -> None:
    karakteristiek = _karakteristiek()

    begindatum = next(item for item in karakteristiek.datums if item.kenmerk == "Begindatum")
    assert begindatum.aantal == 4
    assert begindatum.op_jaargrens == 3
    assert begindatum.aandeel == 75.0


def test_een_datum_buiten_1_januari_ontkracht_de_jaarprecisie() -> None:
    """Een enkele echte datum is genoeg: dan is de dag wel degelijk vastgelegd."""
    karakteristiek = _karakteristiek()

    assert karakteristiek.jaarprecisie == []


def test_alles_op_1_januari_geldt_als_jaarprecisie(tmp_path: Path) -> None:
    tekst = FIXTURE.read_text(encoding="utf-8").replace("2003-07-04", "2003-01-01")
    kopie = tmp_path / "jaarprecisie.ttl"
    kopie.write_text(tekst, encoding="utf-8")

    karakteristiek = bepaal_karakteristiek(load_dataset(kopie, []), load_check_config())

    begindatum = next(item for item in karakteristiek.datums if item.kenmerk == "Begindatum")
    assert begindatum.jaarprecisie
    assert [item.kenmerk for item in karakteristiek.jaarprecisie] == ["Begindatum"]


def test_expliciete_onbekend_waarden_worden_apart_geteld() -> None:
    karakteristiek = _karakteristiek()

    maaiveld = _vulling(karakteristiek, "maaiveldhoogte")
    assert maaiveld.aantal == 5
    assert maaiveld.met_wijze == 2
    assert maaiveld.zonder_wijze == 3
    assert maaiveld.onbekend == 1
    assert maaiveld.per_wijze == {"AHN2": 1, "NietAchterhaald": 1}
    assert karakteristiek.onbekend_totaal == 1


def test_de_onbekend_lijst_is_configureerbaar() -> None:
    """Welke waarde "onbekend" betekent is een projectafspraak, geen code.

    De fixture heeft een AHN2 en een NietAchterhaald, dus een lijst met alleen
    NietAchterhaald geeft 1. Om aan te tonen dat de lijst echt gelezen wordt moet
    de telling meebewegen: leeg geeft 0, beide waarden geven 2.
    """
    standaard = _vulling(_karakteristiek(), "maaiveldhoogte")
    assert standaard.onbekend == 1

    leeg = load_check_config()
    leeg.inwinning.onbekend = []
    assert _vulling(_karakteristiek(leeg), "maaiveldhoogte").onbekend == 0

    beide = load_check_config()
    beide.inwinning.onbekend = ["AHN2", "NietAchterhaald"]
    ruim = _vulling(_karakteristiek(beide), "maaiveldhoogte")
    assert ruim.onbekend == 2
    # De telling per wijze blijft ongemoeid; alleen het onbekend-oordeel verschuift.
    assert ruim.per_wijze == {"AHN2": 1, "NietAchterhaald": 1}


def test_kenmerken_zonder_waarden_komen_niet_in_de_tabel() -> None:
    """Over een kenmerk dat er niet is, valt niets te zeggen."""
    karakteristiek = _karakteristiek()

    kenmerken = [item.kenmerk for item in karakteristiek.inwinning]
    assert "maaiveldhoogte" in kenmerken
    assert "BOB beginpunt" in kenmerken


def test_de_sectie_staat_in_het_bevindingenrapport(tmp_path: Path) -> None:
    """Het rapport hoort te vermelden op welke precisie de datums staan."""
    context = CheckContext(dataset=load_dataset(FIXTURE, []), config=load_check_config())
    run = run_checks(context, ["ATTR-007"])

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "**Datakarakteristieken**" in tekst
    assert "| Begindatum | 4 | 3 (75.0%) | dag |" in tekst
    assert "| maaiveldhoogte | 5 | 2 | 1 (50.0%) |" in tekst
    assert "expliciet dat de inwinning niet te achterhalen is" in tekst


def test_het_aandeel_putten_zonder_aanlegjaar_opent_de_sectie(tmp_path: Path) -> None:
    """Het ontbrekende aanlegjaar is een aanleveringsgebrek en hoort in de kop (issue #91).

    De fixture heeft vier putten waarvan er een geen begindatum draagt: 25%. Teller en
    noemer komen uit wat er al is -- de ATTR-018-meldingen van deze uitvoer en de
    putpopulatie -- en niet uit een tweede telling naast de check.
    """
    context = CheckContext(
        dataset=load_dataset(TTL_DIR / "attr018_zonder_begindatum.ttl", []),
        config=load_check_config(),
    )
    run = run_checks(context, ["ATTR-018"])

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "**25.0% van de putten draagt geen aanlegjaar** (1 van de 4)" in tekst
    assert "aanleveringssignaal" in tekst
    # De regel opent de sectie; de tabellen komen erna.
    assert tekst.index("**Datakarakteristieken**") < tekst.index("van de putten draagt geen")
    assert tekst.index("van de putten draagt geen") < tekst.index("| Datumkenmerk |")


def test_zonder_ontbrekend_aanlegjaar_blijft_de_regel_weg(tmp_path: Path) -> None:
    """Nul meldingen is geen karakteristiek; "0% van de putten" zou ruis zijn."""
    context = CheckContext(
        dataset=load_dataset(TTL_DIR / "attr_schoon.ttl", []), config=load_check_config()
    )
    run = run_checks(context, ["ATTR-018"])

    assert run.count(Severity.ERROR) == 0

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "**Datakarakteristieken**" in tekst
    assert "van de putten draagt geen aanlegjaar" not in tekst


def test_de_weggezette_vulwaarden_staan_onder_de_inwinningstabel(tmp_path: Path) -> None:
    """De vulwaarde-leesregel verlaagt de noemers van deze tabel; het rapport zegt het erbij.

    `bepaal_karakteristiek` draait op de gemarkeerde dataset, dus een hoogte binnen de
    band telt niet meer als registratie. Op De Wolden en Hoogeveen scheelt dat bijna 15.000 waarden
    (BO-27); een noemer die zonder uitleg verspringt leest als een meetfout.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = markeer_vulwaarden(
        load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl", []),
        config.vulwaarden.hoogte_kenmerken,
        config.vulwaarden.hoogte_band_m,
    )
    run = run_checks(CheckContext(dataset=dataset, config=config), ["ATTR-013"])

    assert run.karakteristiek is not None
    assert run.karakteristiek.vulwaarden == 3

    markdown_path, _ = write_check_report(run, tmp_path)
    tekst = markdown_path.read_text(encoding="utf-8")

    assert "3 hoogtewaarden vielen binnen de vulwaardeband" in tekst
