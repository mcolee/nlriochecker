"""Tests voor de toetsrun als aanroepbare eenheid.

Deze tests staan op de seam die `toetsrun.py` blootlegt en niet op de opdrachtregel.
Dat scheelt niet alleen het parsen van argumenten: een test die wil weten of de
typeringspoort toegepast is, leest hier het veld `typeringspoort_toegepast` in plaats
van in de uitvoertekst naar een zin te zoeken. Wat er over het *scherm* te zeggen
valt -- de volgorde en de bewoording van `regels()` -- staat er apart in, want dat is
een eigen belofte.

`tests/test_cli.py` houdt wat echt over de opdrachtregel gaat: exitcodes,
vlagcombinaties en de voortgangsbalk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box, mapping

from nlriochecker.errors import OpdrachtError, StudyAreaError
from nlriochecker.toetsrun import Toetsopdracht, Toetsuitslag, voer_toets_uit
from nlriochecker.uitvoer.bevindingen import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
    FILE_CHECKS_MARKDOWN,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"


def toets(tmp_path: Path, bestand: str, **velden) -> Toetsuitslag:
    """Draait een toets op een fixture, met de uitvoer in `tmp_path`."""
    opdracht = Toetsopdracht(
        dataset=TTL_DIR / bestand,
        uitvoermap=tmp_path / "uitvoer",
        met_geopackage=False,
        **velden,
    )
    return voer_toets_uit(opdracht)


def drieluik() -> tuple[Path, ...]:
    """De drie SHACL-rapporten die samen een volledige nulmeting vormen."""
    return (
        SHACL_DIR / "mini_hyd.csv",
        SHACL_DIR / "mini_mdsplan.csv",
        SHACL_DIR / "mini_mdsproj.csv",
    )


def test_schrijft_rapport_en_archief(tmp_path: Path) -> None:
    """Een run zonder opties levert het rapport, de CSV en de JSON op."""
    uitslag = toets(tmp_path, "top001_losliggende_put.ttl", check_ids=("TOP-001",))

    geschreven = uitslag.uitvoer.per_gebied[""]
    assert geschreven.markdown.name == FILE_CHECKS_MARKDOWN
    assert geschreven.csv.name == FILE_CHECKS_CSV
    assert geschreven.json is not None and geschreven.json.name == FILE_CHECKS_JSON
    assert geschreven.geopackage is None
    assert len(uitslag.runs) == 1
    assert len(uitslag.runs[0].run.findings) == 1


def test_zonder_shacl_is_er_niet_gemeten(tmp_path: Path) -> None:
    """Geen nulmeting is een eigen toestand, los van een onvolledige set."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",))

    assert uitslag.typeringspoort_toegepast is False
    assert uitslag.meetbereik.volledig is False
    assert uitslag.meetbereik.markering() is not None


def test_met_shacl_wordt_de_typeringspoort_toegepast(tmp_path: Path) -> None:
    """Met alle drie de rapporten is de meting volledig en is de poort toegepast."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",), shacl=drieluik())

    assert uitslag.typeringspoort_toegepast is True
    assert uitslag.meetbereik.volledig is True
    assert uitslag.meetbereik.markering() is None


def test_cfk_deelset_markeert_de_uitslag(tmp_path: Path) -> None:
    """Een deelset is toegestaan maar wordt luid gemeld; zie BO-7."""
    uitslag = toets(
        tmp_path,
        "schoon.ttl",
        check_ids=("TOP-001",),
        shacl=(SHACL_DIR / "mini_hyd.csv",),
        cfk=("Hyd",),
    )

    assert uitslag.typeringspoort_toegepast is True
    assert uitslag.meetbereik.volledig is False
    assert uitslag.meetbereik.gekozen == ("Hyd",)
    markering = uitslag.meetbereik.markering()
    assert markering is not None
    assert any(markering in regel for regel in uitslag.regels())


def test_onbekende_cfk_is_een_opdrachtfout(tmp_path: Path) -> None:
    """En hij valt op vóór het laden, ook zonder SHACL-rapporten."""
    with pytest.raises(OpdrachtError, match="Onbekende conformiteitsklasse"):
        toets(tmp_path, "schoon.ttl", cfk=("Hydx",))


def test_onbekende_check_noemt_de_bekende(tmp_path: Path) -> None:
    """Een typefout in een check-ID hoort te melden wat er wel bestaat."""
    with pytest.raises(OpdrachtError, match="Bekende checks: ADM-002"):
        toets(tmp_path, "schoon.ttl", check_ids=("TOP-999",))


def test_gebiedskeuze_zonder_studiegebied_is_een_opdrachtfout(tmp_path: Path) -> None:
    """`gebieden` zonder `studiegebied` is geen stille overslag maar een fout."""
    with pytest.raises(OpdrachtError, match="--gebied werkt alleen samen"):
        toets(tmp_path, "schoon.ttl", gebieden=("noord",))


def test_studiegebied_zonder_objecten_faalt(tmp_path: Path) -> None:
    """Bij een run op een enkel gebied is een leeg gebied bijna altijd een fout."""
    leeg = tmp_path / "leeg.geojson"
    leeg.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:28992"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": mapping(box(200000, 500000, 200010, 500010)),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(StudyAreaError, match="geen GWSW-objecten"):
        toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",), studiegebied=leeg)


def test_analyseset_splitst_kern_en_schil(tmp_path: Path) -> None:
    """Met een studiegebied draaien de checks op de kern plus de contextschil."""
    uitslag = toets(
        tmp_path,
        "afbakening_kern_en_schil.ttl",
        check_ids=("TOP-001",),
        studiegebied=GIS_DIR / "afbakening_gebied.geojson",
    )

    analyseset = uitslag.runs[0].run.analyseset
    assert analyseset is not None
    assert analyseset.kern
    assert analyseset.schil
    assert analyseset.volledig_aantal >= len(analyseset.alles)


def test_afwijkende_codering_wordt_gemeld(tmp_path: Path) -> None:
    """Een BrutIS-export met CP850-bytes wordt gelezen, maar nooit stilzwijgend."""
    uitslag = toets(tmp_path, "codering_cp850.ttl", check_ids=("TOP-001",))

    assert uitslag.dataset.decode_fallback is not None
    assert any("geen geldige UTF-8" in regel for regel in uitslag.regels())


def test_zonder_bronnen_geen_externe_data(tmp_path: Path) -> None:
    """Zonder bronmap draaien de EXT-checks niet, en dat wordt gezegd."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",))

    assert uitslag.bronnen is None
    assert any("Geen externe bronnen geladen" in regel for regel in uitslag.regels())


def test_meerdere_gebieden_leveren_een_run_per_gebied(tmp_path: Path) -> None:
    """Bij twee features rapporteert de toets per gebied, plus een totaal."""
    uitslag = toets(
        tmp_path,
        "schoon.ttl",
        check_ids=("TOP-001",),
        studiegebied=GIS_DIR / "buurten_twee.gpkg",
    )

    assert len(uitslag.runs) == 2
    assert uitslag.studiegebieden is not None
    assert len(uitslag.uitvoer.per_gebied) == 2
    assert uitslag.uitvoer.synthese is not None


def test_gebiedskeuze_beperkt_de_run(tmp_path: Path) -> None:
    """Met een keuze draait alleen dat gebied, maar wordt het bestand wel volledig gelezen."""
    uitslag = toets(
        tmp_path,
        "schoon.ttl",
        check_ids=("TOP-001",),
        studiegebied=GIS_DIR / "buurten_twee.gpkg",
        gebieden=(_eerste_gebiedsnaam(tmp_path),),
    )

    assert len(uitslag.runs) == 1


def _eerste_gebiedsnaam(tmp_path: Path) -> str:
    """De naam van het eerste gebied in de tweebuurten-fixture."""
    from nlriochecker.studiegebied import load_studiegebieden

    return load_studiegebieden(GIS_DIR / "buurten_twee.gpkg", None).beschikbaar[0]


def test_json_kan_uit(tmp_path: Path) -> None:
    """`met_json=False` laat het bestand weg en meldt het niet als geschreven."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",), met_json=False)

    assert uitslag.uitvoer.per_gebied[""].json is None
    assert not any(FILE_CHECKS_JSON in regel for regel in uitslag.regels())


def test_geopackage_kan_aan(tmp_path: Path) -> None:
    """De GIS-uitvoer staat standaard aan en levert een bestand op."""
    opdracht = Toetsopdracht(
        dataset=TTL_DIR / "schoon.ttl",
        uitvoermap=tmp_path / "uitvoer",
        check_ids=("TOP-001",),
    )
    uitslag = voer_toets_uit(opdracht)

    geschreven = uitslag.uitvoer.per_gebied[""].geopackage
    assert geschreven is not None and geschreven.exists()


def test_de_csv_en_de_uitslag_tellen_hetzelfde(tmp_path: Path) -> None:
    """Het archief en de uitslag komen uit dezelfde meldingenstroom."""
    uitslag = toets(tmp_path, "hgt010_diameterverjonging.ttl")

    tabel = pd.read_csv(uitslag.uitvoer.per_gebied[""].csv, sep=";", encoding="utf-8")
    assert len(tabel) == len(uitslag.runs[0].run.findings)


def test_regels_beginnen_met_de_omvang_en_eindigen_met_de_bestanden(tmp_path: Path) -> None:
    """De volgorde van `regels()` is onderdeel van de uitvoer, niet toevallig.

    De beller hoort deze lijst af te drukken en hem niet zelf samen te stellen; deze
    test legt de kop en de staart vast zodat een herschikking opvalt.
    """
    uitslag = toets(tmp_path, "top001_losliggende_put.ttl", check_ids=("TOP-001",))
    regels = uitslag.regels()

    assert regels[0].startswith("top001_losliggende_put.ttl: ")
    assert "knooppunten" in regels[0] and "strengen" in regels[0]
    assert regels[1].startswith("  Dataset ")
    assert regels[-1].startswith("Geschreven: ")
    assert any(regel.startswith("Totaal ") for regel in regels)
