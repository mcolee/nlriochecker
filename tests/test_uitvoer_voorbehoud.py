"""Tests voor de runbrede voorbehouden en hun samenstelplek.

`schrijf_markdown` heeft een markeringsslot, en er kan meer dan een voorbehoud
tegelijk gelden: een `--cfk`-deelset op een dataset zonder klassenhierarchie draagt er
twee. Zonder samenstelplek zou een schrijver er een moeten kiezen en verdwijnt de
andere stilzwijgend -- en een voorbehoud dat je niet ziet, is geen voorbehoud.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import Meetbereik
from nlriochecker.uitvoer.samenvatting import NIET_GEMETEN, REGEL_EIGEN_CHECKS, VINKJE
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer
from nlriochecker.uitvoer.voorbehoud import GEEN_KLASSENHIERARCHIE, markering, voorbehouden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
RUNDATUM = date(2026, 8, 21)

DEELSET = "**Onvolledige meting:** getoetst op Hyd, MdsPlan;"

# De kop van de managementsamenvatting, zoals `uitvoer/bevindingen.py` hem schrijft.
KOP_SAMENVATTING = "## Voldoen we in dit gebied?"


@pytest.fixture
def toets() -> CheckRun:
    """Een gewone toetsrun op een fixture die haar eigen klassenhierarchie draagt."""
    return run_checks(
        CheckContext(
            dataset=load_dataset(TTL_DIR / "top001_losliggende_put.ttl"),
            config=load_check_config(),
        )
    )


def _kaal(run: CheckRun) -> CheckRun:
    """Dezelfde run, maar op een dataset die geen enkele subklasserelatie kent.

    Precies wat de echte OroX-export zonder ontologie oplevert: `_subclass_closure`
    vindt niets, dus elke `closure()` is een singleton.
    """
    return replace(run, dataset=replace(run.dataset, subclasses={}))


def test_zonder_voorbehoud_blijft_de_kop_leeg(toets: CheckRun) -> None:
    """De volle meting op een gekende hierarchie heeft niets voor te behouden."""
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, VEREIST))

    assert voorbehouden(run) == []
    assert markering(run) is None


def test_twee_voorbehouden_komen_allebei_in_de_kop(toets: CheckRun, tmp_path: Path) -> None:
    """De test waar de samenstelplek voor bestaat.

    Een deelset-run zonder klassenhierarchie draagt twee runbrede voorbehouden. Met
    een enkel markeringsslot en zonder samenstelling zou een van beide stilzwijgend
    verdwijnen, en dan leest de lezer de stilte als "alles gecontroleerd". Markdown,
    GeoPackage en JSON moeten ze alle drie allebei tonen; de CSV bewust geen van
    beide, want een voorbehoud hoort bij de run en niet bij de melding.
    """
    run = _kaal(replace(toets, meetbereik=Meetbereik.van(VEREIST, ["Hyd", "MdsPlan"])))

    assert len(voorbehouden(run)) == 2

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.json is not None and uitvoer.geopackage is not None
    markdown = uitvoer.markdown.read_text(encoding="utf-8")
    document = json.loads(uitvoer.json.read_text(encoding="utf-8"))
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        ((uit_gpkg,),) = verbinding.execute("select markering from gwsw_run")
    finally:
        verbinding.close()

    for tekst in (GEEN_KLASSENHIERARCHIE, DEELSET):
        assert tekst in markdown
        assert tekst in document["markering"]
        assert tekst in uit_gpkg
    # De markering staat in de kop, boven de romp van het rapport.
    assert markdown.index(GEEN_KLASSENHIERARCHIE) < markdown.index("## ")
    csv = uitvoer.csv.read_text(encoding="utf-8")
    assert "Onvolledige meting" not in csv and "Geen klassenhierarchie" not in csv


def test_een_voorbehoud_alleen_verdringt_het_andere_niet(toets: CheckRun) -> None:
    """Elk van de twee bronnen moet ook in zijn eentje de kop kunnen vullen."""
    volledig = Meetbereik.van(VEREIST, VEREIST)

    alleen_deelset = markering(replace(toets, meetbereik=Meetbereik.van(VEREIST, ["Hyd"])))
    alleen_kaal = markering(_kaal(replace(toets, meetbereik=volledig)))

    assert alleen_deelset is not None and GEEN_KLASSENHIERARCHIE not in alleen_deelset
    assert alleen_kaal == GEEN_KLASSENHIERARCHIE


def _samenvattingstabel(markdown: str) -> list[str]:
    """De tabelregels van de managementsamenvatting, en niets eromheen.

    De legenda onder de tabel bevat zelf een vinkje ("Een ✔ betekent nul fouten"), dus
    een test die op de hele sectie snijdt zou nooit kunnen falen. En de kop van het
    rapport, waar een eerdere versie van deze test naar keek, bevat de samenvatting
    helemaal niet.
    """
    sectie = markdown.split(KOP_SAMENVATTING, 1)[1].split("\n## ", 1)[0]
    return [regel for regel in sectie.splitlines() if regel.startswith("|")]


def test_zonder_klassenhierarchie_is_er_geen_vinkje_in_de_samenvatting(
    toets: CheckRun, tmp_path: Path
) -> None:
    """Nul fouten uit een onvolledige selectie is geen vinkje waard.

    De regel van de eigen checks krijgt het streepje voor "geen oordeel", met de reden
    erbij. De tellingen blijven staan: ze weglaten zou lezen als "er is niets
    gevonden", en dat is iets anders dan "wat gevonden is draagt geen oordeel".

    Het meetbereik is hier `niet_gemeten`, want dat is de run uit de verificatie van
    issue #33: `--geen-ontologie` zonder `--shacl`. Dan hoort er in de hele tabel geen
    enkel vinkje te staan. Met een verzonnen volledig meetbereik zouden de drie
    CFK-regels er wel een dragen -- terecht, want die tellen de nulmeting -- en dan
    toetst deze assertie iets anders dan het issue vraagt.
    """
    run = _kaal(replace(toets, meetbereik=Meetbereik.niet_gemeten(VEREIST)))

    markdown = schrijf_uitvoer(run, tmp_path, RUNDATUM).markdown.read_text(encoding="utf-8")

    tabel = _samenvattingstabel(markdown)
    regel = next(line for line in tabel if REGEL_EIGEN_CHECKS in line)
    assert regel.startswith(f"| {NIET_GEMETEN} |")
    assert "geen klassenhierarchie" in regel and "onvolledige selectie" in regel
    assert "7 fouten en 0 waarschuwingen" in regel, regel
    assert VINKJE not in "\n".join(tabel), tabel


def test_de_vinkjeassertie_kan_werkelijk_falen(toets: CheckRun, tmp_path: Path) -> None:
    """De tegenproef bij de test hierboven.

    Een volledig gemeten run op dezelfde fixture zet drie vinkjes in diezelfde tabel --
    de conformiteitsklassen tellen nul overtredingen uit de nulmeting. Zonder deze
    tegenproef zou een assertie die op het verkeerde stuk tekst snijdt er groen uitzien
    terwijl zij niets borgt, en dat is precies wat de eerste versie ervan deed.
    """
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, VEREIST))

    markdown = schrijf_uitvoer(run, tmp_path, RUNDATUM).markdown.read_text(encoding="utf-8")

    tabel = _samenvattingstabel(markdown)
    assert sum(1 for regel in tabel if regel.startswith(f"| {VINKJE} |")) == 3


def test_de_json_zwijgt_zonder_voorbehoud(toets: CheckRun, tmp_path: Path) -> None:
    """Een run zonder voorbehoud draagt het veld niet, net als `gebied` en `gebieden`.

    Zo blijft `bevindingen.json` van een volledige run byte-voor-byte zoals hij was;
    zie de versioneringsregel in `docs/json-schema.md`.
    """
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, VEREIST))

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.json is not None
    assert "markering" not in json.loads(uitvoer.json.read_text(encoding="utf-8"))
