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

import ast
import json
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box, mapping

from nlriochecker import toetsrun as toetsrun_module
from nlriochecker.checkconfig import default_check_config_path
from nlriochecker.errors import OpdrachtError, StudyAreaError
from nlriochecker.externedata import ExternalDataError
from nlriochecker.toetsrun import (
    Toetsopdracht,
    Toetsuitslag,
    voer_toets_uit,
)
from nlriochecker.uitvoer.bevindingen import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
    FILE_CHECKS_MARKDOWN,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"
EXT_DIR = GIS_DIR / "ext"

# De namen van de miniatuurbronnen wijken af van de aangeleverde bestanden in
# `data/gis_koekangerveld`; een projectconfiguratie die ze aanwijst is precies de weg
# die een gebruiker met eigen bestandsnamen ook gaat.
BRONBESTANDEN = {
    'bgt = "BGT.gpkg"': 'bgt = "bgt.gpkg"',
    'bag_pand = "bag_pand_koekangerveld.gpkg"': 'bag_pand = "bag_pand.gpkg"',
    'nwb_wegvakken = "nwb_wegvakken_koekangerveld.gpkg"': 'nwb_wegvakken = "nwb_wegvakken.gpkg"',
    'studiegebied = "cbs_buurt_koekangerveld_studiegebied.gpkg"': (
        'studiegebied = "studiegebied.gpkg"'
    ),
    'ahn_dtm = "ahn5_dtm_koekangerveld.tif"': 'ahn_dtm = "ahn.tif"',
}


def bronnenconfig(tmp_path: Path, tolerantie: float | None = None) -> Path:
    """Schrijft een projectconfiguratie die naar de miniatuurbronnen wijst."""
    tekst = default_check_config_path().read_text(encoding="utf-8")
    for oud, nieuw in BRONBESTANDEN.items():
        assert oud in tekst, oud
        tekst = tekst.replace(oud, nieuw)
    if tolerantie is not None:
        tekst = tekst.replace(
            "dekking_tolerantie_m = 300.0", f"dekking_tolerantie_m = {tolerantie}"
        )
    pad = tmp_path / "project.toml"
    pad.write_text(tekst, encoding="utf-8")
    return pad


def toets(tmp_path: Path, bestand: str, **velden) -> Toetsuitslag:
    """Draait een toets op een fixture, met de uitvoer in `tmp_path`."""
    opdracht = Toetsopdracht(
        dataset_pad=TTL_DIR / bestand,
        uitvoermap=tmp_path / "uitvoer",
        met_geopackage=False,
        # Niet in de cache van de ontwikkelaar schrijven: die map wordt nergens
        # opgeruimd, en een test hoort geen sporen buiten haar tmp_path te laten.
        cachemap=tmp_path / "cache",
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
    # Een volledige meting krijgt geen markering en dus geen meetregel: stilte is
    # hier de juiste uitkomst, en die hoort net zo goed vastgelegd te zijn.
    assert not any("typeringspoort" in regel for regel in uitslag.regels())


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
    # De omvang van elk deel hoort ook op het scherm; wat een check niet gezien
    # heeft mag niet als "alles gecontroleerd" lezen.
    assert any(
        f"Analyseset: {len(analyseset.kern)} objecten in de kern, "
        f"{len(analyseset.schil)} in de contextschil" in regel
        for regel in uitslag.regels()
    )


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
    # Vanaf twee gebieden krijgt elk gebied een regel en geen blok per check; bij
    # tachtig buurten zou dat laatste duizenden regels opleveren.
    gebiedsregels = [regel for regel in uitslag.regels() if regel.startswith("  Gebied ")]
    assert len(gebiedsregels) == 2
    assert all("in de kern" in regel for regel in gebiedsregels)


def test_gebiedskeuze_beperkt_de_run_en_meldt_dat(tmp_path: Path) -> None:
    """Met een keuze draait alleen dat gebied, en de synthese zegt dat er gekozen is.

    Die tweede helft hangt aan de bedrading: `voer_toets_uit` geeft `beschikbaar` en
    `overgeslagen` door aan de uitvoerlaag. Valt dat weg, dan verdwijnt de mededeling
    dat het grootste deel van het gebiedsbestand niet gedraaid heeft -- en dan leest
    een schone synthese als een schoon beheergebied.
    """
    uitslag = toets(
        tmp_path,
        "hgt010_diameterverjonging.ttl",
        check_ids=("HGT-010",),
        studiegebied=GIS_DIR / "buurten_twee.gpkg",
        gebieden=("Noord",),
    )

    assert len(uitslag.runs) == 1
    assert set(uitslag.uitvoer.per_gebied) == {"Noord"}
    assert uitslag.uitvoer.synthese is not None
    assert "Selectie" in uitslag.uitvoer.synthese.read_text(encoding="utf-8")


def test_json_kan_uit(tmp_path: Path) -> None:
    """`met_json=False` laat het bestand weg en meldt het niet als geschreven."""
    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",), met_json=False)

    assert uitslag.uitvoer.per_gebied[""].json is None
    assert not any(FILE_CHECKS_JSON in regel for regel in uitslag.regels())


def test_geopackage_kan_aan(tmp_path: Path) -> None:
    """De GIS-uitvoer staat standaard aan en levert een bestand op."""
    opdracht = Toetsopdracht(
        dataset_pad=TTL_DIR / "schoon.ttl",
        uitvoermap=tmp_path / "uitvoer",
        check_ids=("TOP-001",),
        cachemap=tmp_path / "cache",
    )
    uitslag = voer_toets_uit(opdracht)

    geschreven = uitslag.uitvoer.per_gebied[""].geopackage
    assert geschreven is not None and geschreven.exists()
    assert any(regel == f"Geschreven: {geschreven}" for regel in uitslag.regels())


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


@pytest.mark.skipif(
    not (EXT_DIR / "ahn.tif").exists(),
    reason="de GIS-fixtures ontbreken; draai scripts/maak_gis_fixtures.py",
)
class TestExterneBronnen:
    """Het pad achter `--bronnen`, dat tot nu toe door geen enkele test liep."""

    def test_bronnen_worden_geladen_en_gemeld(self, tmp_path: Path) -> None:
        """Met een bronmap draaien de EXT-checks, en de uitslag zegt wat er meedeed."""
        uitslag = toets(
            tmp_path,
            "ext_scenario.ttl",
            check_ids=("EXT-001",),
            bronnen=EXT_DIR,
            projectconfig=bronnenconfig(tmp_path),
        )

        assert uitslag.bronnen is not None
        assert len(uitslag.bronnen.layers) == 6
        assert uitslag.bronnen.raster is not None
        assert uitslag.bronnen.missing == ()
        assert any(
            regel.startswith("  Externe bronnen: 6 lagen, hoogteraster, bereik ")
            for regel in uitslag.regels()
        )
        assert not any("Geen externe bronnen geladen" in regel for regel in uitslag.regels())

    def test_een_te_kleine_bron_is_een_harde_fout(self, tmp_path: Path) -> None:
        """De dekkingspoort van BO-19: stilte is hier gevaarlijker dan een fout.

        Met tolerantie 0 dekken de miniatuurbronnen hun eigen studiegebied net niet.
        Dat moet het laden afbreken en niet leiden tot EXT-checks die niets vinden --
        een te klein extract geeft anders een misleidend schone uitkomst.
        """
        with pytest.raises(ExternalDataError, match="dekken het bereik niet"):
            toets(
                tmp_path,
                "ext_scenario.ttl",
                check_ids=("EXT-001",),
                bronnen=EXT_DIR,
                projectconfig=bronnenconfig(tmp_path, tolerantie=0.0),
            )

    def test_de_dekkingspoort_gaat_vooraf_aan_het_laden(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Een bron die het bereik niet dekt hoort niet drie minuten laden af te wachten."""

        def val(*args: object, **kwargs: object) -> None:
            raise AssertionError("de dataset werd geladen voordat de bronnen getoetst waren")

        monkeypatch.setattr("nlriochecker.toetsrun.laad_met_cache", val)
        with pytest.raises(ExternalDataError):
            toets(
                tmp_path,
                "ext_scenario.ttl",
                check_ids=("EXT-001",),
                bronnen=EXT_DIR,
                projectconfig=bronnenconfig(tmp_path, tolerantie=0.0),
            )


def test_typeringsvoorbehoud_wordt_gemeld(tmp_path: Path) -> None:
    """Een object waarvan de typering te globaal is, komt met voorbehoud in de uitslag.

    De SHACL-meting benoemt de te globale klassen; de instanties volgen uit de
    dataset. Zonder deze test toont niets meer aan dat het voorbehoud daadwerkelijk
    doorwerkt tot in de melding op het scherm -- en een voorbehoud dat je niet ziet
    is geen voorbehoud.
    """
    bron = (TTL_DIR / "top001_losliggende_put.ttl").read_text(encoding="utf-8")
    bron += "\n:PutC rdf:type gwsw:Overstortput .\ngwsw:Overstortput rdfs:subClassOf gwsw:Put .\n"
    dataset = tmp_path / "met_overstortput.ttl"
    dataset.write_text(bron, encoding="utf-8")

    uitslag = voer_toets_uit(
        Toetsopdracht(
            dataset_pad=dataset,
            uitvoermap=tmp_path / "uitvoer",
            check_ids=("TOP-001",),
            shacl=drieluik(),
            met_geopackage=False,
            cachemap=tmp_path / "cache",
        )
    )

    assert uitslag.typeringspoort_toegepast is True
    assert uitslag.runs[0].run.outcomes[0].unreliable_count
    assert any("met typeringsvoorbehoud" in regel for regel in uitslag.regels())


def test_de_module_kent_de_opdrachtregel_niet() -> None:
    """`toetsrun` mag niet van click afhangen; dat is de hele scheiding.

    Een import die er stilletjes bij komt zou de module weer aan de opdrachtregel
    vastknopen zonder dat een test faalt -- pas de volgende beller merkt het.
    """
    boom = ast.parse(Path(toetsrun_module.__file__).read_text(encoding="utf-8"))
    namen = {
        knoop.module.split(".")[0]
        for knoop in ast.walk(boom)
        if isinstance(knoop, ast.ImportFrom) and knoop.module
    }
    namen |= {
        alias.name.split(".")[0]
        for knoop in ast.walk(boom)
        if isinstance(knoop, ast.Import)
        for alias in knoop.names
    }
    assert "click" not in namen


def test_onleesbare_geometrie_wordt_geteld_en_gemeld(tmp_path: Path) -> None:
    """Een object met een kapotte GML-literaal breekt de run niet af, maar zwijgt ook niet.

    De fixture bevat een streng waarvan de lijn maar een coordinaat heeft. GEOS
    weigert die; de lader telt het object als onleesbaar en de rest loopt door. Dat
    laatste hoort op het scherm te komen, anders leest een run over een deels
    onleesbare export als een volledige run.
    """
    uitslag = toets(tmp_path, "geometriefout.ttl", check_ids=("TOP-001",))

    assert len(uitslag.dataset.geometry_errors) == 1
    assert len(uitslag.dataset.conduits) == 2
    assert any(regel == "  1 objecten met onleesbare geometrie." for regel in uitslag.regels())


def test_een_beschadigde_cache_wordt_gemeld(tmp_path: Path) -> None:
    """Opnieuw inlezen omdat de cache stuk was, hoort de gebruiker te zien.

    Het herstel zelf is elders getoetst (`tests/test_cache.py`); wat hier telt is
    dat de melding erover het scherm haalt. Een run die er stilzwijgend drie minuten
    langer over doet, laat de gebruiker zoeken naar een oorzaak die het gereedschap
    al kent.
    """
    # `toets` zet de cachemap op tmp_path/cache; beide aanroepen delen hem dus.
    toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",))
    for bestand in (tmp_path / "cache").rglob("*.pickle"):
        bestand.write_bytes(b"dit is geen pickle")

    uitslag = toets(tmp_path, "schoon.ttl", check_ids=("TOP-001",))

    assert uitslag.cache.bron == "bestand"
    assert "onbruikbaar" in uitslag.cache.melding
    assert any(uitslag.cache.melding in regel for regel in uitslag.regels())
