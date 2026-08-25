"""Tests voor het voortgangsprotocol.

Voortgang is weergave. De harde eis is dat hij de uitkomst van een run nergens
raakt; de tests hier leggen vast dat de standaardwaarde niets doet, dat een opnemer
de fasen in de juiste volgorde ziet, en dat de uitvoerbestanden er niet van
veranderen.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import laad_nulmeting
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer
from nlriochecker.voortgang import NUL_VOORTGANG, NulVoortgang, Voortgang

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
RUNDATUM = date(2026, 8, 18)


class Opnemer:
    """Legt vast welke fasen en stappen langskomen."""

    def __init__(self) -> None:
        self.gebeurtenissen: list[tuple[str, object, object]] = []

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Legt het begin van een fase vast."""
        self.gebeurtenissen.append(("start", naam, totaal))

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Legt een stap vast."""
        self.gebeurtenissen.append(("stap", n, label))

    def einde_fase(self) -> None:
        """Legt het einde van een fase vast."""
        self.gebeurtenissen.append(("einde", None, None))

    def fasen(self) -> list[tuple[str, object]]:
        """De gestarte fasen met hun totaal, in volgorde."""
        return [(g[1], g[2]) for g in self.gebeurtenissen if g[0] == "start"]  # type: ignore[misc]

    def labels(self, fase: str) -> list[object]:
        """De staplabels binnen een fase, in volgorde."""
        binnen = False
        gevonden: list[object] = []
        for soort, eerste, tweede in self.gebeurtenissen:
            if soort == "start":
                binnen = eerste == fase
            elif soort == "einde":
                binnen = False
            elif binnen:
                gevonden.append(tweede)
        return gevonden


def test_nulvoortgang_voldoet_aan_het_protocol() -> None:
    """De standaardwaarde is een geldige implementatie, niet een None-vervanger."""
    bereik: Voortgang = NUL_VOORTGANG

    bereik.start_fase("iets", 3)
    bereik.stap(2, label="TOP-001")
    bereik.einde_fase()

    assert isinstance(NUL_VOORTGANG, NulVoortgang)


def test_opnemer_voldoet_aan_het_protocol() -> None:
    """De testopnemer is structureel een Voortgang; anders bijten de tests niet."""
    opnemer: Voortgang = Opnemer()

    opnemer.start_fase("Checks", 2)
    opnemer.stap(label="TOP-001")
    opnemer.einde_fase()

    assert isinstance(opnemer, Opnemer)
    assert opnemer.gebeurtenissen == [
        ("start", "Checks", 2),
        ("stap", 1, "TOP-001"),
        ("einde", None, None),
    ]


def test_laadfase_zet_een_stap_per_bestand() -> None:
    """rdflib geeft geen tussenstand binnen een bestand; dit is wat er wel te melden is."""
    opnemer = Opnemer()

    load_dataset(TTL_DIR / "schoon.ttl", voortgang=opnemer)

    assert opnemer.fasen() == [("TTL laden", 1)]
    assert opnemer.labels("TTL laden") == ["schoon.ttl"]
    assert opnemer.gebeurtenissen[-1] == ("einde", None, None)


def test_shaclfase_zet_een_stap_per_rapport(shacl_drieluik: list[Path]) -> None:
    """Drie rapporten, drie stappen."""
    opnemer = Opnemer()

    laad_nulmeting(shacl_drieluik, VEREIST, voortgang=opnemer)

    assert opnemer.fasen() == [("SHACL-rapporten", 3)]
    assert opnemer.labels("SHACL-rapporten") == [pad.name for pad in shacl_drieluik]


def test_checksfase_zet_een_stap_per_check() -> None:
    """De gebruiker ziet welke check loopt, niet alleen dat er iets loopt."""
    opnemer = Opnemer()
    dataset = load_dataset(TTL_DIR / "schoon.ttl")

    run = run_checks(CheckContext(dataset=dataset, config=load_check_config()), voortgang=opnemer)

    assert opnemer.fasen() == [("Checks", len(run.outcomes))]
    assert opnemer.labels("Checks") == [outcome.check_id for outcome in run.outcomes]
    assert opnemer.gebeurtenissen[-1] == ("einde", None, None)


def test_geopackagefase_zet_een_stap_per_laag(tmp_path: Path) -> None:
    """Acht tabellen en lagen, acht stappen."""
    opnemer = Opnemer()
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "hgt004_bob_boven_deksel.ttl")
    run = run_checks(CheckContext(dataset=dataset, config=config))

    schrijf_uitvoer(run, tmp_path, RUNDATUM, voortgang=opnemer)

    assert opnemer.fasen() == [("GeoPackage", 8)]
    assert opnemer.labels("GeoPackage") == [
        "putten",
        "strengen",
        "vlakken",
        "gemengd_zonder_overstort",
        "meldingen",
        "overzicht_checks",
        "gwsw_run",
        "layer_styles",
    ]


def test_cachetreffer_start_geen_laadfase(tmp_path: Path) -> None:
    """Een balk die in nul seconden vol schiet liegt over waar de tijd blijft."""
    laad_met_cache(TTL_DIR / "schoon.ttl", [], tmp_path, True)
    opnemer = Opnemer()

    _, uitslag = laad_met_cache(TTL_DIR / "schoon.ttl", [], tmp_path, True, voortgang=opnemer)

    assert uitslag.bron == "cache"
    assert opnemer.gebeurtenissen == []


def test_cachemisser_start_wel_een_laadfase(tmp_path: Path) -> None:
    """Wordt er wel geparseerd, dan hoort de fase er te zijn."""
    opnemer = Opnemer()

    _, uitslag = laad_met_cache(TTL_DIR / "schoon.ttl", [], tmp_path, True, voortgang=opnemer)

    assert uitslag.bron != "cache"
    assert opnemer.fasen() == [("TTL laden", 1)]


def test_geen_voortgang_verandert_de_uitvoerbestanden_niet(tmp_path: Path) -> None:
    """Met de standaardwaarde is de uitvoer identiek aan die met een opnemer.

    De harde eis: voortgang is weergave. Zou een fase iets aan de run veranderen,
    dan zouden deze bestanden verschillen.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "hgt004_bob_boven_deksel.ttl")
    context = CheckContext(dataset=dataset, config=config)

    zonder = schrijf_uitvoer(run_checks(context), tmp_path / "a", RUNDATUM)
    met = schrijf_uitvoer(
        run_checks(context, voortgang=Opnemer()), tmp_path / "b", RUNDATUM, voortgang=Opnemer()
    )

    assert zonder.markdown.read_text(encoding="utf-8") == met.markdown.read_text(encoding="utf-8")
    assert zonder.csv.read_text(encoding="utf-8") == met.csv.read_text(encoding="utf-8")
    assert zonder.json is not None and met.json is not None
    assert zonder.json.read_text(encoding="utf-8") == met.json.read_text(encoding="utf-8")


def test_checksfase_kan_de_gebiedsnaam_dragen() -> None:
    """Met meerdere gebieden moet zichtbaar zijn welk gebied loopt."""
    opnemer = Opnemer()
    dataset = load_dataset(TTL_DIR / "schoon.ttl")

    run_checks(
        CheckContext(dataset=dataset, config=load_check_config()),
        ["TOP-001"],
        voortgang=opnemer,
        fase="Checks Noord",
    )

    assert opnemer.fasen() == [("Checks Noord", 1)]
