"""Tests voor EXT-009: straten in de bebouwde kom zonder (vrijverval)riolering.

De fixture bestaat uit twee helften die bij elkaar horen. `tests/fixtures/gis/ext`
draagt de externe bronnen (acht NWB-wegvakken, een TOP10NL-plaatsvlak met een bebouwde
kom, drie BGT-wegdelen), `tests/fixtures/ttl/ext009_straten.ttl` de riolering. Drie van
de acht wegvakken zijn kandidaat, en elk staat voor een van de drie uitkomsten:
Rioolstraat is bediend (groen), Lege Laan leeg (rood, W-melding) en Grindweg onverhard
(grijs, niet beoordeeld). De vijf andere vallen elk om een eigen reden uit de
kandidaatselectie; zie `scripts/maak_gis_fixtures.py`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from gwsw_orox_helpers.dataset import load_dataset
from shapely.geometry import GeometryCollection, LineString, box

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, CheckRun, run_checks
from nlriochecker.checks.treffers import Wegvakregister
from nlriochecker.checks.wegvakken import (
    REDEN_DRUKRIOLERING,
    REDEN_ONVERHARD,
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ROOD,
    Kenmerken,
    _alleen_vlakken,
    _bevat,
    _lengte_in,
    _nabij,
    classificeer,
)
from nlriochecker.errors import PipelineError
from nlriochecker.externedata import ExternalData, load_external_data
from nlriochecker.uitvoer.gpkg import VLAK_SOORT_WEGVAK, schrijf_geopackage
from nlriochecker.uitvoer.melding import bouw_meldingen, bouw_meldingenstroom
from nlriochecker.uitvoer.objectkaart import STATUSSEN

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis" / "ext"
STRATEN = TTL_DIR / "ext009_straten.ttl"
RUNDATUM = date(2026, 8, 29)

pytestmark = pytest.mark.skipif(
    not (GIS_DIR / "top10nl_plaats_vlak.gpkg").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)


@pytest.fixture
def config() -> CheckConfig:
    """De standaardconfig, afgestemd op het assenstelsel van de fixtures."""
    gekozen = load_check_config()
    gekozen.drempels.rd_y_min = 0.0
    return gekozen


@pytest.fixture(scope="session")
def bronnen() -> ExternalData:
    """De miniatuurbronnen uit tests/fixtures/gis/ext."""
    basis = load_check_config().bronnen
    aangepast = basis.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "bag_pand": "bag_pand.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "top10nl": "top10nl_plaats_vlak.gpkg",
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    return load_external_data(aangepast, GIS_DIR)


def draai(config: CheckConfig, bronnen: ExternalData | None) -> CheckRun:
    """Draait EXT-009 op de stratenfixture."""
    dataset = load_dataset(STRATEN, [])
    context = CheckContext(dataset=dataset, config=config, bronnen=bronnen)
    return run_checks(context, ["EXT-009"])


def uitkomst(config: CheckConfig, bronnen: ExternalData | None) -> CheckOutcome:
    """De uitslag van EXT-009 op de stratenfixture."""
    return draai(config, bronnen).outcomes[0]


def test_elke_kandidaatstraat_krijgt_haar_eigen_status(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Drie kandidaten, drie uitkomsten; de vijf andere wegvakken vallen af."""
    run = draai(config, bronnen)

    assert {oordeel.straat: oordeel.status for oordeel in run.wegvakken} == {
        "Rioolstraat": "groen",
        "Lege Laan": "rood",
        "Grindweg": "grijs",
    }


def test_alleen_de_lege_straat_levert_een_waarschuwing(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """De melding hangt aan een NWB-sleutel en draagt het middelpunt als locatie."""
    outcome = uitkomst(config, bronnen)

    assert [bevinding.object_label for bevinding in outcome.findings] == ["Lege Laan (Fixturekom)"]
    bevinding = outcome.findings[0]
    assert bevinding.object_uri == "nwb:wegvak/3"
    assert bevinding.severity.value == "W"
    assert bevinding.location == (1060.0, 1940.0)
    assert outcome.examined == 3


def test_de_toelichting_telt_wat_er_niet_beoordeeld_is(
    config: CheckConfig, bronnen: ExternalData
) -> None:
    """Stilte over de grijze straten zou lezen als 'alles gecontroleerd'."""
    outcome = uitkomst(config, bronnen)

    assert any("1 groen" in notitie for notitie in outcome.notes), outcome.notes
    assert any(
        "niet beoordeeld" in notitie.lower() and "onverhard" in notitie for notitie in outcome.notes
    ), outcome.notes


def test_zonder_bronnen_wordt_er_niets_getoetst(config: CheckConfig) -> None:
    outcome = uitkomst(config, None)

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("geen externe bronnen" in notitie for notitie in outcome.notes)


def test_zonder_begrenzingspolygoon_meldt_de_check_niets(config: CheckConfig) -> None:
    """Zonder studiegebied geeft geen enkele EXT-check een uitslag; ook deze niet.

    De andere EXT-checks zijn hier per constructie veilig: zij lopen via `_selecteer` en
    `binnen_bereik`, en dat is bij `extent is None` altijd onwaar. EXT-009 komt daar niet
    langs -- zijn populatie zijn wegvakken en geen GWSW-objecten -- dus hij toetst het zelf
    in `_beoordeel`. Zonder die poort meldde hij straten naast de zin "er is dus niets
    getoetst", vulde hij de laag `vlakken` met drie vlakken, en deelde
    `percentage_populatie` door nul.
    """
    basis = load_check_config().bronnen
    zonder_gebied = basis.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "top10nl": "top10nl_plaats_vlak.gpkg",
            "studiegebied": None,
            "ahn_dtm": None,
        }
    )
    bronnen = load_external_data(zonder_gebied, GIS_DIR)
    run = draai(config, bronnen)
    outcome = run.outcomes[0]

    assert bronnen.extent is None
    assert bronnen.layer("nwb_wegvak") is not None
    assert outcome.findings == []
    assert outcome.examined == 0
    assert len(run.wegvakken) == 0
    assert any("geen begrenzingspolygoon" in notitie for notitie in outcome.notes), outcome.notes


def test_een_ontbrekende_bron_slaat_de_check_over(config: CheckConfig) -> None:
    """Zonder komlaag is er geen bebouwde kom en dus geen kandidaatselectie."""
    basis = load_check_config().bronnen
    zonder_kom = basis.model_copy(
        update={
            "map": ".",
            "bgt": "bgt.gpkg",
            "nwb_wegvakken": "nwb_wegvakken.gpkg",
            "top10nl": None,
            "studiegebied": "studiegebied.gpkg",
            "ahn_dtm": "ahn.tif",
        }
    )
    outcome = uitkomst(config, load_external_data(zonder_kom, GIS_DIR))

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("laag niet aanwezig in aangeleverde data" in n for n in outcome.notes), outcome.notes


def _kenmerken(**waarden: float | bool) -> Kenmerken:
    """Eén kandidaat met de opgegeven kenmerken; de rest op "niets gemeten"."""
    basis: dict[str, object] = {
        "streng_in_cel": 0.0,
        "put_in_cel": False,
        "persleiding_langs": 0.0,
        "pomp_nabij": False,
        "aandeel_onverhard": float("nan"),
    }
    basis.update(waarden)
    return Kenmerken(**{naam: np.array([waarde]) for naam, waarde in basis.items()})


def _status(**waarden: float | bool) -> tuple[str, str]:
    """De classificatie van één kandidaat met de standaarddrempels."""
    return classificeer(_kenmerken(**waarden), load_check_config().drempels)[0]


def test_genoeg_vrijverval_in_de_eigen_cel_is_bediend() -> None:
    assert _status(streng_in_cel=0.4) == ("groen", "")


def test_een_put_in_de_eigen_cel_bedient_de_straat_ongeacht_de_lengte() -> None:
    """De lus- en hoefijzeruitzondering: het riool loopt door de as van de straat.

    Zonder deze regel meldt de check elke hoefijzerweg als leeg, want de streng ligt daar
    niet langs de as maar er dwars doorheen -- en dan valt maar een fractie in de cel.
    """
    assert _status(streng_in_cel=0.01, put_in_cel=True) == ("groen", "")


def test_geen_vrijverval_is_een_bevinding() -> None:
    assert _status(streng_in_cel=0.0) == ("rood", "")


def test_een_overwegend_onverharde_straat_wordt_niet_beoordeeld() -> None:
    status, reden = _status(streng_in_cel=0.0, aandeel_onverhard=0.9)

    assert status == "grijs"
    assert reden == REDEN_ONVERHARD


def test_drukriolering_zondert_alleen_het_onzekere_middengebied_uit() -> None:
    """Een pompunit naast een straat met te weinig vrijverval: niet beoordeeld.

    Maar alleen als er iets ligt. Een straat met nul meter vrijverval in haar eigen cel is
    niet onzeker maar meetbaar leeg, en die blijft een bevinding -- zonder die grens
    verdwenen op De Wolden en Hoogeveen 31 terecht gemelde gaten uit beeld (BO-81).
    """
    onzeker = _status(streng_in_cel=0.1, pomp_nabij=True)
    leeg = _status(streng_in_cel=0.0, pomp_nabij=True)

    assert onzeker == ("grijs", REDEN_DRUKRIOLERING)
    assert leeg == ("rood", "")


def test_persleiding_langs_de_straat_telt_net_zo_als_een_pompunit() -> None:
    assert _status(streng_in_cel=0.1, persleiding_langs=0.5) == ("grijs", REDEN_DRUKRIOLERING)
    assert _status(streng_in_cel=0.1, persleiding_langs=0.2) == ("rood", "")


def test_een_lege_bron_levert_een_meetbare_nul_en_geen_fout() -> None:
    """Een dataset zonder pompunits of zonder riolering mag de meting niet laten omvallen.

    De drie meetfuncties krijgen dan een lege array. Nul meter streng in de cel is een
    meting en geen ontbrekende waarde; het onverhard-aandeel is dat juist niet -- zonder
    wegdeel naast de straat is er niets gemeten, en dat blijft NaN.
    """
    vlak = np.array([box(0.0, 0.0, 10.0, 10.0)], dtype=object)
    leeg = np.array([], dtype=object)

    assert _lengte_in(vlak, leeg).tolist() == [0.0]
    assert _bevat(vlak, leeg).tolist() == [False]
    assert _nabij(vlak, leeg, 5.0).tolist() == [False]


def test_een_lijnrestje_aan_een_doorsnede_verdwijnt(tmp_path: Path) -> None:
    """De laag `vlakken` is MULTIPOLYGON; een `GeometryCollection` past daar niet in.

    Twee elkaar rakende vlakken kunnen een doorsnede met een lijnstukje opleveren. Zonder
    deze opschoning zou zo'n straatvlak niet weg te schrijven zijn.
    """
    gemengd = GeometryCollection([box(0.0, 0.0, 1.0, 1.0), LineString([(2.0, 0.0), (3.0, 0.0)])])

    (schoon,) = _alleen_vlakken(np.array([gemengd], dtype=object))

    assert schoon.geom_type in {"Polygon", "MultiPolygon"}
    assert schoon.area == pytest.approx(1.0)


def test_de_drie_wegvakstatussen_zijn_kaartstatussen() -> None:
    """De laag `vlakken` schrijft ze ongewijzigd weg; een vijfde waarde mag er niet bij."""
    assert {STATUS_ROOD, STATUS_GROEN, STATUS_GRIJS} <= set(STATUSSEN)


def test_de_nwb_kolom_wordt_hoofdletterongevoelig_gelezen(bronnen: ExternalData) -> None:
    """De Wolden schrijft `WEGBEHSRT`, Koekangerveld `wegbehsrt`; één lezing dekt beide."""
    laag = bronnen.layer("nwb_wegvak")
    assert laag is not None

    assert laag.kolom("WEGBEHSRT") == laag.kolom("wegbehsrt")
    assert set(laag.kolom("STT_NAAM")) == {
        "Fixturestraat",
        "Rioolstraat",
        "Lege Laan",
        "Grindweg",
        "Buitenweg",
        "Rijksweg",
        "Fietspad",
        "Kort Straatje",
    }
    assert laag.kolom("bestaat_niet") == [None] * len(laag)


def _wegvakrijen(pad: Path) -> list[dict]:
    """De rijen van de laag `vlakken` met soort `wegvak`, zonder geometrie en fid."""
    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    verbinding.row_factory = sqlite3.Row
    try:
        return [
            {naam: rij[naam] for naam in rij.keys() if naam not in {"geom", "fid"}}
            for rij in verbinding.execute(
                'select * from "vlakken" where soort = ?', (VLAK_SOORT_WEGVAK,)
            )
        ]
    finally:
        verbinding.close()


def test_de_vlakkenlaag_draagt_elk_beoordeeld_wegvak(
    config: CheckConfig, bronnen: ExternalData, tmp_path: Path
) -> None:
    """De derde uitvoertoestand (BO-79): groen en grijs krijgen een vlak zonder melding.

    Voor elke andere soort in deze laag geldt "een vlak bestaat alleen als er een melding
    naar wijst". Hier niet: juist het onderscheid tussen "gekeken, er ligt riolering" en
    "niet gekeken" is de winst, en dat is zonder groene en grijze vlakken niet te zien.
    """
    run = draai(config, bronnen)
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    rijen = {rij["label"]: rij for rij in _wegvakrijen(pad)}

    assert {label: rij["status"] for label, rij in rijen.items()} == {
        "Rioolstraat (Fixturekom)": "groen",
        "Lege Laan (Fixturekom)": "rood",
        "Grindweg (Fixturekom)": "grijs",
    }
    assert {label: rij["aantal_meldingen"] for label, rij in rijen.items()} == {
        "Rioolstraat (Fixturekom)": 0,
        "Lege Laan (Fixturekom)": 1,
        "Grindweg (Fixturekom)": 0,
    }
    leeg = rijen["Lege Laan (Fixturekom)"]
    assert (leeg["id"], leeg["bron"], leeg["check_ids"]) == (
        "nwb:wegvak/3",
        "nwb_wegvak",
        "EXT-009",
    )
    assert leeg["bronbestand"] == "nwb_wegvakken.gpkg"
    # De grijze straat zegt in haar popup waarom zij niet beoordeeld is; grijs zonder
    # reden leest als "in orde".
    assert "onverhard" in rijen["Grindweg (Fixturekom)"]["popup_html"]


def test_een_onderdrukte_melding_haalt_haar_rode_vlak_weg(
    config: CheckConfig, bronnen: ExternalData, tmp_path: Path
) -> None:
    """Rood hangt aan de meldingen van déze uitvoer, ook na `[rapport] onderdruk_checks`.

    Zou het register de kaart alleen vullen, dan toonde zij een gebrek dat in geen enkele
    andere uitvoervorm staat. Groen en grijs blijven wél staan: die zijn geen gebrek maar
    het antwoord op "is hier gekeken?" (BO-79).
    """
    config.rapport.onderdruk_checks = ["EXT-009"]
    run = draai(config, bronnen)
    stroom = bouw_meldingenstroom(run, RUNDATUM)
    pad = schrijf_geopackage(
        run, stroom.meldingen, tmp_path, RUNDATUM, onderdrukking=stroom.onderdrukking
    )

    assert stroom.onderdrukking.totaal == 1
    assert {rij["status"] for rij in _wegvakrijen(pad)} == {"groen", "grijs"}


def test_een_melding_zonder_geregistreerd_wegvak_faalt_luid(
    config: CheckConfig, bronnen: ExternalData, tmp_path: Path
) -> None:
    """Dezelfde strikte aansluiting als bij de externe vlakken.

    Check en schrijver lezen hetzelfde register van dezelfde run; wijst een melding naar
    een wegvak dat er niet in staat, dan is dat een interne tegenspraak en geen
    datatoestand. Stil overslaan zou de laag kleiner maken dan de uitslag.
    """
    run = draai(config, bronnen)
    meldingen = bouw_meldingen(run, RUNDATUM)
    zonder_register = replace(run, wegvakken=Wegvakregister())

    with pytest.raises(PipelineError, match="wegvakregister"):
        schrijf_geopackage(zonder_register, meldingen, tmp_path, RUNDATUM)


def test_de_runmetadata_telt_de_wegvakken_apart(
    config: CheckConfig, bronnen: ExternalData, tmp_path: Path
) -> None:
    """Zonder eigen telling zou `n_vlakken` de externe vlakken niet meer laten narekenen."""
    run = draai(config, bronnen)
    pad = schrijf_geopackage(run, bouw_meldingen(run, RUNDATUM), tmp_path, RUNDATUM)

    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        rij = verbinding.execute("select n_vlakken, n_wegvakken from gwsw_run").fetchone()
    finally:
        verbinding.close()

    assert rij == (3, 3)
