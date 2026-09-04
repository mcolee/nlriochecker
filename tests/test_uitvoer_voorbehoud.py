"""Tests voor de runbrede voorbehouden en hun samenstelplek.

`schrijf_markdown` heeft een markeringsslot, en er kan meer dan een voorbehoud
tegelijk gelden: een `--cfk`-deelset op een dataset zonder klassenhierarchie draagt er
twee. Zonder samenstelplek zou een schrijver er een moeten kiezen en verdwijnt de
andere stilzwijgend -- en een voorbehoud dat je niet ziet, is geen voorbehoud.

Onderaan staat sinds issue #118 de sweep die die belofte afdwingt in plaats van haar
alleen op te schrijven.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from dataclasses import fields, replace
from datetime import date
from pathlib import Path
from typing import get_args, get_type_hints

import pytest
from gwsw_orox_helpers.dataset import GwswDataset, load_dataset

from nlriochecker.analysis import MetingAnalysis
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.comparison import MetingComparison
from nlriochecker.coverage import CoverageResult
from nlriochecker.meting import Meetbereik, Nulmeting
from nlriochecker.uitvoer.samenvatting import NIET_GEMETEN, REGEL_EIGEN_CHECKS, VINKJE
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer
from nlriochecker.uitvoer.voorbehoud import (
    GEEN_KLASSENHIERARCHIE,
    markering,
    markering_van,
    voorbehouden,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
BRON = Path(__file__).resolve().parents[1] / "src"
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
RUNDATUM = date(2026, 8, 21)

# Wie `Meetbereik.markering()` rechtstreeks mag aanroepen, met de reden erbij. De
# definitie zelf (`meting.py`) staat er niet in: `def markering(self)` is geen aanroep en
# valt buiten deze sweep.
#
# Wie hier een module aan toevoegt, schrijft de reden erbij -- en bedenkt dat een
# rechtstreekse aanroep per definitie maar één voorbehoud kan dragen.
MAG_ZELF_MARKEREN = {
    # De samenstelplek zelf: hier komen het hierarchie- en het meetbereikvoorbehoud
    # samen tot één kop.
    "nlriochecker/uitvoer/voorbehoud.py",
    # Terminaluitvoer, geen rapport. Het hierarchie-voorbehoud staat daar als eigen regel
    # naast deze (`toetsrun.py`, `_datasetregels`), dus hier verdwijnt er niets.
    "nlriochecker/toetsrun.py",
}

# De uitslagtypen van `analyseer`, `dekking` en `vergelijk`, plus de `Nulmeting` waar
# `MetingAnalysis` naar wijst. Zij zijn de bellers van `markering_van`, en de premisse
# eronder is dat geen van hen een datasetobject draagt.
ZONDER_DATASETOBJECT = (CoverageResult, MetingAnalysis, MetingComparison, Nulmeting)


def _noemt_dataset(annotatie: object) -> bool:
    """Of deze annotatie ergens een `GwswDataset` noemt.

    Ook binnen een unie of een verzameling: `GwswDataset | None` is geen `GwswDataset`
    voor een `is`-vergelijking, maar draagt er wel een. Precies die vorm zou een
    optioneel datasetveld door de drifttest hieronder laten glippen.
    """
    return annotatie is GwswDataset or any(_noemt_dataset(deel) for deel in get_args(annotatie))


DEELSET = "**Onvolledige meting:** getoetst op Hyd, MdsPlan;"

# De kop van de managementsamenvatting, zoals `uitvoer/bevindingen.py` hem schrijft.
KOP_SAMENVATTING = "## Voldoen we in dit gebied?"


@pytest.fixture
def toets() -> CheckRun:
    """Een gewone toetsrun op een fixture die haar eigen klassenhierarchie draagt."""
    return run_checks(
        CheckContext(
            dataset=load_dataset(TTL_DIR / "top001_losliggende_put.ttl", []),
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
    # Vier fouten meer dan voorheen: ATTR-018 meldt de streng en de drie putten van deze
    # fixture, die geen van alle een begindatum dragen (issue #61). De drie waarschuwingen
    # zijn ATTR-019: geen van de drie putten draagt een `HoogtePut` (issue #133).
    assert "11 fouten en 3 waarschuwingen" in regel, regel
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


def test_markering_van_geeft_precies_de_meetbereikmarkering() -> None:
    """De ingang voor een beller zonder datasetobject verandert de tekst niet.

    `CoverageResult` draagt een datasetnaam en `MetingAnalysis`/`MetingComparison`
    dragen helemaal geen dataset, dus `klassenhierarchie_bekend` is daar onbereikbaar en
    kan er maar één voorbehoud gelden. Deze ingang bestaat om die aanroep zichtbaar te
    maken, niet om hem anders te laten luiden; alle drie de toestanden moeten dus
    letterlijk hetzelfde opleveren als de methode zelf.
    """
    for bereik in (
        Meetbereik.van(VEREIST, VEREIST),
        Meetbereik.van(VEREIST, ["Hyd"]),
        Meetbereik.niet_gemeten(VEREIST),
    ):
        assert markering_van(bereik) == bereik.markering()

    assert markering_van(Meetbereik.van(VEREIST, VEREIST)) is None


def test_de_bellers_van_markering_van_dragen_werkelijk_geen_datasetobject() -> None:
    """De premisse onder `markering_van`, als drifttest (issue #118).

    `markering_van` mag maar één voorbehoud doorgeven omdat zijn bellers de andere bron
    niet kúnnen kennen: `klassenhierarchie_bekend` hangt aan een `GwswDataset`, en
    `CoverageResult` draagt een datasetnáám terwijl `MetingAnalysis`, `MetingComparison`
    en de `Nulmeting` eronder alleen een bestandsnaam dragen. Krijgt een van hen ooit
    wél een datasetobject, dan is die premisse vervallen en verdwijnt het
    hierarchievoorbehoud uit `samenvatting.md`, `dekking.md` en `vergelijking.md`
    zonder dat er iets omvalt.

    Valt deze test om, dan is dat de opdracht: laat `markering_van` vervallen en laat de
    betreffende schrijver op `markering(run)` overgaan. Hem hier "even bijwerken" haalt
    precies de garantie weg waar hij voor bestaat.
    """
    met_dataset = sorted(
        f"{klasse.__name__}.{veld.name}"
        for klasse in ZONDER_DATASETOBJECT
        for hints in [get_type_hints(klasse)]
        for veld in fields(klasse)
        if _noemt_dataset(hints[veld.name])
    )

    assert met_dataset == []


def test_alleen_de_samenstelplek_roept_de_meetbereikmarkering_aan() -> None:
    """`docs/architectuur.md` belooft dit; tot issue #118 stond het er alleen.

    Een schrijver die `meetbereik.markering()` rechtstreeks aanroept, kan per constructie
    maar één voorbehoud doorgeven -- `schrijf_markdown` heeft één markeringsslot -- en
    laat het andere stilzwijgend vallen. Dat er nog geen fout uit volgde is structureel
    en niet toevallig: de drie bellers in `reporting.py` hebben geen datasetobject en
    kunnen het hierarchie-voorbehoud dus niet kennen. Krijgt `CoverageResult` er ooit
    een, dan is dit de test die de dan ontstane stilte tegenhoudt.
    """
    overtreders = sorted(
        pad.relative_to(BRON).as_posix()
        for pad in BRON.rglob("*.py")
        if pad.relative_to(BRON).as_posix() not in MAG_ZELF_MARKEREN
        and any(
            isinstance(knoop, ast.Call)
            and isinstance(knoop.func, ast.Attribute)
            and knoop.func.attr == "markering"
            for knoop in ast.walk(ast.parse(pad.read_text(encoding="utf-8")))
        )
    )

    assert overtreders == []


def test_de_markeringsweep_kan_werkelijk_afgaan() -> None:
    """De tegenproef: de sweep herkent een rechtstreekse aanroep ook echt.

    De vrijstellingslijst dekt twee modules, dus de sweep hierboven is groen. Zonder
    deze test is dat niet te onderscheiden van een sweep die de aanroep niet herkent --
    en dan staat er een hek dat nooit kan afgaan.
    """

    def roept_aan(bron: str) -> bool:
        """Of deze broncode ergens een `.markering()` aanroept."""
        return any(
            isinstance(knoop, ast.Call)
            and isinstance(knoop.func, ast.Attribute)
            and knoop.func.attr == "markering"
            for knoop in ast.walk(ast.parse(bron))
        )

    assert roept_aan("kop = analyse.meting.meetbereik.markering()")
    # De definitie in `meting.py` is geen aanroep, en de modulefunctie `markering(run)`
    # uit `voorbehoud.py` is geen attribuutaanroep: allebei terecht buiten de sweep.
    assert not roept_aan("def markering(self) -> str | None:\n    return None")
    assert not roept_aan("kop = markering(run)")


def test_de_json_zwijgt_zonder_voorbehoud(toets: CheckRun, tmp_path: Path) -> None:
    """Een run zonder voorbehoud draagt het veld niet, net als `gebied` en `gebieden`.

    Zo blijft `bevindingen.json` van een volledige run byte-voor-byte zoals hij was;
    zie de versioneringsregel in `docs/json-schema.md`.
    """
    run = replace(toets, meetbereik=Meetbereik.van(VEREIST, VEREIST))

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.json is not None
    assert "markering" not in json.loads(uitvoer.json.read_text(encoding="utf-8"))
