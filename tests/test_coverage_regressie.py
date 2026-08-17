"""Tests voor de regressiebewaking op de dekkingclaims van de schrapronde.

De schrapronde is alleen geldig zolang de nulmeting het onderwerp van elke
geschrapte check daadwerkelijk raakt. Twee dingen kunnen dat stilzwijgend
ondermijnen: de dekkingmapping die uit de pas loopt met het checkregister, en een
CFK die de dekkende SHACL-vorm niet blijkt te bevatten. Deze tests leggen vast dat
beide zichtbaar worden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.analysis import MetingAnalysis, analyze
from nlriochecker.config import CoverageConfig, load_coverage_config
from nlriochecker.coverage import (
    CoverageResult,
    assess_coverage,
    verify_register,
)
from nlriochecker.errors import CoverageError
from nlriochecker.meting import laad_nulmeting
from nlriochecker.register import default_register_path, load_register

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]

REGISTER_KOP = """# Checkregister

Versie {versie}, werkdocument.

## TOP: Topologie en geometrie

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| TOP-001 | Losliggende putten | F | Consistentie |

## Geschrapte checks

| ID | Check | Gedekt door |
|---|---|---|
{rijen}
"""


def _register_bestand(pad: Path, versie: str, geschrapt: list[str]) -> Path:
    """Schrijft een miniregister met deze versie en deze geschrapte check-ID's."""
    rijen = "\n".join(f"| {check_id} | onderwerp | dekking |" for check_id in geschrapt)
    pad.write_text(REGISTER_KOP.format(versie=versie, rijen=rijen), encoding="utf-8")
    return pad


def _mapping_bestand(
    pad: Path, versie: str, ids: list[str], vorm: str = "LengteLeiding_val"
) -> Path:
    """Schrijft een dekkingmapping met deze versie en deze check-ID's."""
    blokken = [f'checkregister_versie = "{versie}"', 'bron = "x"']
    for check_id in ids:
        blokken.append(
            "[[check]]\n"
            f'id = "{check_id}"\n'
            'onderwerp = "x"\n'
            'claim = "x"\n'
            f"vereiste_cfk = {VEREIST!r}\n".replace("'", '"')
            + f'bewijs = [{{ vorm = "{vorm}" }}]\n'
        )
    pad.write_text("\n".join(blokken), encoding="utf-8")
    return pad


@pytest.fixture
def analyse(shacl_drieluik: list[Path]) -> MetingAnalysis:
    """De analyse van de mini-nulmeting."""
    return analyze(laad_nulmeting(shacl_drieluik, VEREIST))


@pytest.fixture
def config() -> CoverageConfig:
    """De meegeleverde standaardmapping."""
    return load_coverage_config()


def test_meegeleverde_mapping_klopt_met_het_checkregister(config: CoverageConfig) -> None:
    """De mapping in het package hoort bij het register in data/ te passen."""
    pad = default_register_path()
    if not pad.exists():
        pytest.skip("het checkregister staat niet in data/")

    controle = verify_register(config, load_register(pad))

    assert controle.klopt
    assert controle.register_versie == config.checkregister_versie
    assert controle.zonder_mapping == []
    assert controle.zonder_registerrij == []


def test_versieverschil_laat_de_dekking_vervallen(tmp_path: Path) -> None:
    register = load_register(_register_bestand(tmp_path / "reg.md", "0.8", ["ADM-001"]))
    config = load_coverage_config(_mapping_bestand(tmp_path / "map.toml", "0.7", ["ADM-001"]))

    controle = verify_register(config, register)

    assert not controle.klopt
    assert controle.register_versie == "0.8"
    assert controle.config_versie == "0.7"


def test_nieuw_geschrapte_check_zonder_sentinel_valt_op(tmp_path: Path) -> None:
    """Schrapt iemand een check zonder de sentinel toe te voegen, dan hoort dat op te vallen."""
    register = load_register(_register_bestand(tmp_path / "reg.md", "0.7", ["ADM-001", "HGT-020"]))
    config = load_coverage_config(_mapping_bestand(tmp_path / "map.toml", "0.7", ["ADM-001"]))

    controle = verify_register(config, register)

    assert not controle.klopt
    assert controle.zonder_mapping == ["HGT-020"]


def test_mapping_voor_een_niet_geschrapte_check_valt_op(tmp_path: Path) -> None:
    """Een claim op een check die weer in het register staat, is geen dekking meer."""
    register = load_register(_register_bestand(tmp_path / "reg.md", "0.7", ["ADM-001"]))
    config = load_coverage_config(
        _mapping_bestand(tmp_path / "map.toml", "0.7", ["ADM-001", "RVZ-002"])
    )

    controle = verify_register(config, register)

    assert not controle.klopt
    assert controle.zonder_registerrij == ["RVZ-002"]


def test_eis_register_werpt_een_pijplijnfout(tmp_path: Path) -> None:
    register = load_register(_register_bestand(tmp_path / "reg.md", "0.8", ["ADM-001"]))
    config = load_coverage_config(_mapping_bestand(tmp_path / "map.toml", "0.7", ["ADM-001"]))

    with pytest.raises(CoverageError) as fout:
        verify_register(config, register, eisen=True)

    assert "0.8" in str(fout.value)
    assert "0.7" in str(fout.value)


def test_vorm_in_de_ene_cfk_maar_niet_in_de_andere(analyse: MetingAnalysis, tmp_path: Path) -> None:
    """`Vuilwaterstelsel_Lozingspunt_card` vuurt in Mds wel en in Hyd niet.

    Beide CFK's toetsen hetzelfde RDF-bestand. Vuurt een vorm in de ene CFK wel en
    in de andere niet, dan kan dat niet aan schone data liggen: de vormverzameling
    verschilt. Een claim "beide CFK's" rust dan op een van de twee.
    """
    config = load_coverage_config(
        _mapping_bestand(
            tmp_path / "map.toml", "0.7", ["ADM-001"], vorm="Vuilwaterstelsel_Lozingspunt_card"
        )
    )

    result = assess_coverage(analyse, config)

    assert len(result.discrepanties) == 1
    afwijking = result.discrepanties[0]
    assert afwijking.check_id == "ADM-001"
    assert afwijking.patroon == "Vuilwaterstelsel_Lozingspunt_card"
    assert afwijking.met_meldingen == ["MdsPlan", "MdsProj"]
    assert afwijking.zonder_meldingen == ["Hyd"]


def test_vorm_die_nergens_vuurt_is_geen_discrepantie(
    analyse: MetingAnalysis, tmp_path: Path
) -> None:
    """Nul meldingen in alle CFK's kan gewoon schone data zijn; dat is geen bewijs."""
    config = load_coverage_config(
        _mapping_bestand(tmp_path / "map.toml", "0.7", ["ADM-001"], vorm="Drempelniveau_card")
    )

    result = assess_coverage(analyse, config)

    assert result.discrepanties == []


def test_meegeleverde_mapping_kent_geen_discrepanties_op_de_minimeting(
    analyse: MetingAnalysis, config: CoverageConfig
) -> None:
    result: CoverageResult = assess_coverage(analyse, config)

    assert result.discrepanties == []


def test_ongelijk_gedraaide_rapporten_ontkrachten_de_vergelijking(
    shacl_drieluik: list[Path], tmp_path: Path
) -> None:
    """Vormverschillen zeggen niets als de rapporten niet gelijk gedraaid zijn.

    Twee CFK's over hetzelfde RDF-bestand zijn alleen vergelijkbaar als ze op
    dezelfde onderdelen gevalideerd zijn. Is dat niet zo, dan verklaart dat een
    vormverschil evengoed en mag het rapport er geen conclusie aan hangen.
    """
    paden = []
    for bron in shacl_drieluik:
        kopie = tmp_path / bron.name
        tekst = bron.read_text(encoding="utf-8")
        if bron.name.endswith("hyd.csv"):
            tekst = tekst.replace(
                "Gevalideerd op onderdelen;Datatype kenmerk,",
                "Gevalideerd op onderdelen;Kardinaliteit,",
            )
        kopie.write_text(tekst, encoding="utf-8")
        paden.append(kopie)

    analyse = analyze(laad_nulmeting(paden, VEREIST))
    result = assess_coverage(analyse, load_coverage_config())

    assert result.ongelijke_meting
    assert "verschillende onderdelen" in result.ongelijke_meting[0]


def test_gelijk_gedraaide_rapporten_geven_geen_voorbehoud(analyse: MetingAnalysis) -> None:
    result = assess_coverage(analyse, load_coverage_config())

    assert result.ongelijke_meting == []
