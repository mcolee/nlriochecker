"""Tests voor de toetsloop over nul, een of veel studiegebieden.

De kerntest is de equivalentie-eis: een gebied uit een bestand met meerdere buurten
moet exact dezelfde meldingen opleveren als een losse run met alleen dat gebied.
Zonder die eigenschap is rapportage per gebied niet te vertrouwen.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from shapely.geometry import Point, box, mapping

from gpkghelper import schrijf_buurten, schrijf_vlakken
from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.dataset import load_dataset
from nlriochecker.errors import StudyAreaError
from nlriochecker.externedata import load_external_data
from nlriochecker.meting import Meetbereik
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.studiegebied import load_studiegebieden
from nlriochecker.toetsloop import GebiedsRun, toets_gebieden
from nlriochecker.uitvoer.melding import Melding, bouw_meldingen
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer_gebieden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
RUNDATUM = date(2026, 8, 18)


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _sleutels(gebiedsrun: GebiedsRun) -> list[Melding]:
    """Alle meldingen van een run, op ID gesorteerd.

    Bewust de volledige `Melding` en niet een handvol velden: de equivalentie-eis
    zegt *identiek*, en een projectie op ID en check zou een verschil in boodschap,
    waarde of locatie niet zien -- precies het soort verschil dat een gedeelde
    structuur zou kunnen veroorzaken.
    """
    return sorted(bouw_meldingen(gebiedsrun.run, RUNDATUM), key=lambda m: m.melding_id)


def _uitslagen(gebiedsrun: GebiedsRun) -> list[tuple[str, int, int, tuple[str, ...]]]:
    """Per check wat er bekeken, weggelaten en toegelicht is."""
    return [(o.check_id, o.examined, o.weggelaten, tuple(o.notes)) for o in gebiedsrun.run.outcomes]


def _draai(
    bestand: str | None,
    ttl: str = "afbakening_kern_en_schil.ttl",
    nulbevindingen: tuple[Nulbevinding, ...] = (),
) -> list[GebiedsRun]:
    """Draait de toetsloop op een fixture, met of zonder studiegebiedbestand."""
    gebieden = load_studiegebieden(GIS_DIR / bestand) if bestand is not None else None
    return toets_gebieden(
        load_dataset(TTL_DIR / ttl),
        gebieden,
        _config(),
        onbetrouwbaar=frozenset(),
        meetbereik=Meetbereik.niet_gemeten(()),
        nulbevindingen=nulbevindingen,
    )


def _nulbevinding(focus: str, uri: str, herleid: bool = True) -> Nulbevinding:
    """Een nulmetingbevinding op een object uit de afbakeningsfixture."""
    return Nulbevinding(
        check_id="NULMETING-Put_HoogtePut_card",
        vorm="Put_HoogtePut_card",
        focus_node=focus,
        ernst="F",
        object_uri=uri,
        object_label=focus,
        objecttype="Inspectieput",
        boodschap="aantal voorkomens wijkt af (exact=1)",
        waarde="te weinig voorkomens",
        cfk=("Hyd", "MdsPlan"),
        systemisch=False,
        herleid=herleid,
    )


# De vier putten van `afbakening_kern_en_schil.ttl` liggen verdeeld over de buurten
# Noord en Zuid; welke waar ligt is wat de equivalentietest hieronder uitzoekt.
NULBEVINDINGEN = (
    _nulbevinding("PutA", "http://example.org/toets#PutA"),
    _nulbevinding("PutB", "http://example.org/toets#PutB"),
    _nulbevinding("PutC", "http://example.org/toets#PutC"),
    _nulbevinding("PutD", "http://example.org/toets#PutD"),
    _nulbevinding("Rioolstelsel", "", herleid=False),
)


def test_per_gebied_gelijk_aan_een_losse_run() -> None:
    """De kerntest: hetzelfde gebied geeft dezelfde meldingen, samen of alleen."""
    samen = _draai("buurten_twee.gpkg")
    los = _draai("buurt_noord.gpkg")

    noord = next(run for run in samen if run.naam == "Noord")

    assert _sleutels(noord) == _sleutels(los[0])
    assert _uitslagen(noord) == _uitslagen(los[0])


def test_ook_het_tweede_gebied_is_equivalent() -> None:
    samen = _draai("buurten_twee.gpkg")
    los = _draai("buurt_zuid.gpkg")

    zuid = next(run for run in samen if run.naam == "Zuid")

    assert _sleutels(zuid) == _sleutels(los[0])
    assert _uitslagen(zuid) == _uitslagen(los[0])


def test_de_analysesets_verschillen_per_gebied() -> None:
    """Anders zou de equivalentietest ook slagen als de afbakening niets deed."""
    noord, zuid = _draai("buurten_twee.gpkg")

    assert noord.run.analyseset is not None and zuid.run.analyseset is not None
    assert noord.run.analyseset.kern != zuid.run.analyseset.kern


def test_zonder_studiegebied_een_run_zonder_gebied() -> None:
    runs = _draai(None, "top001_losliggende_put.ttl")

    assert len(runs) == 1
    assert runs[0].gebied is None
    assert runs[0].map == ""
    assert runs[0].naam == ""


def test_een_gebied_krijgt_geen_submap() -> None:
    """Bij een enkel gebied blijft de uitvoer staan waar hij stond."""
    runs = _draai("buurt_noord.gpkg")

    assert len(runs) == 1
    assert runs[0].map == ""
    assert runs[0].naam == "Noord"


def test_twee_gebieden_krijgen_elk_een_mapnaam() -> None:
    runs = _draai("buurten_twee.gpkg")

    assert [run.map for run in runs] == ["noord", "zuid"]


def test_grensobject_verschijnt_in_beide_gebieden_met_hetzelfde_id() -> None:
    """Streng B-C raakt beide buurten; elk gebied ziet zijn eigen werkelijkheid.

    De melding-ID mag het gebied niet bevatten, anders is een grensobject in de
    synthese niet als een en hetzelfde defect te herkennen.
    """
    noord, zuid = _draai("buurten_twee.gpkg", "hgt010_diameterverjonging.ttl")

    gedeeld = {melding.melding_id for melding in _sleutels(noord)} & {
        melding.melding_id for melding in _sleutels(zuid)
    }

    assert gedeeld


def test_onbekend_gebied_faalt_met_de_beschikbare_namen() -> None:
    gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")

    with pytest.raises(StudyAreaError, match="Noord, Zuid"):
        gebieden.selecteer(["Oost"])


def _schrijf(
    bestand: str,
    doel: Path,
    ttl: str = "hgt010_diameterverjonging.ttl",
    config: CheckConfig | None = None,
    **opties,
):
    """Draait de toetsloop en schrijft de uitvoer weg."""
    gebieden = load_studiegebieden(GIS_DIR / bestand)
    runs = toets_gebieden(
        load_dataset(TTL_DIR / ttl),
        gebieden,
        config or _config(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    return runs, schrijf_uitvoer_gebieden(
        runs,
        doel,
        RUNDATUM,
        beschikbaar=gebieden.beschikbaar,
        overgeslagen=gebieden.overgeslagen,
        **opties,
    )


def test_twee_gebieden_leveren_twee_submappen_en_een_totaal(tmp_path: Path) -> None:
    _, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path)

    assert (tmp_path / "noord" / "bevindingen.md").exists()
    assert (tmp_path / "zuid" / "bevindingen.md").exists()
    assert (tmp_path / "totaal" / "synthese.md").exists()
    assert (tmp_path / "totaal" / "bevindingen.csv").exists()
    assert uitvoer.totaal_json is not None
    assert set(uitvoer.per_gebied) == {"Noord", "Zuid"}


def test_zonder_csv_schrijft_ook_totaal_geen_csv(tmp_path: Path) -> None:
    """Issue #66: `met_csv=False` geldt per gebied én voor `totaal/`."""
    _, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path, met_csv=False, met_geopackage=False)

    assert uitvoer.totaal_csv is None
    assert all(geschreven.csv is None for geschreven in uitvoer.per_gebied.values())
    assert not list(tmp_path.rglob("bevindingen.csv"))
    assert uitvoer.synthese is not None and uitvoer.synthese.exists()


def test_de_synthese_noemt_alleen_de_geschreven_totaalbestanden(tmp_path: Path) -> None:
    """Issue #66: een verwijzing naar een uitgezette CSV stuurt de lezer naar niets."""
    _, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path, met_csv=False, met_geopackage=False)

    assert uitvoer.synthese is not None
    tekst = uitvoer.synthese.read_text(encoding="utf-8")

    assert "`bevindingen.json` hiernaast bevat" in tekst
    assert "bevindingen.csv" not in tekst


def test_een_gebied_schrijft_zonder_submap(tmp_path: Path) -> None:
    _, uitvoer = _schrijf("buurt_noord.gpkg", tmp_path)

    assert (tmp_path / "bevindingen.md").exists()
    assert not (tmp_path / "noord").exists()
    assert uitvoer.synthese is None


def test_per_gebied_json_noemt_het_gebied(tmp_path: Path) -> None:
    _schrijf("buurten_twee.gpkg", tmp_path)

    document = json.loads((tmp_path / "noord" / "bevindingen.json").read_text(encoding="utf-8"))

    assert document["gebied"] == "Noord"


def test_totaal_json_noemt_alle_gebieden(tmp_path: Path) -> None:
    _schrijf("buurten_twee.gpkg", tmp_path)

    document = json.loads((tmp_path / "totaal" / "bevindingen.json").read_text(encoding="utf-8"))

    assert document["gebied"] is None
    assert document["gebieden"] == ["Noord", "Zuid"]


def test_json_van_een_enkel_gebied_draagt_geen_gebiedsveld(tmp_path: Path) -> None:
    """Een run op een enkelvoudig bestand blijft precies wat hij was."""
    _schrijf("buurt_noord.gpkg", tmp_path)

    document = json.loads((tmp_path / "bevindingen.json").read_text(encoding="utf-8"))

    assert "gebied" not in document


def test_synthese_telt_unieke_en_meervoudige_meldingen(tmp_path: Path) -> None:
    """Streng B-C raakt beide buurten: twee meldingen, een uniek defect."""
    runs, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path)
    assert uitvoer.synthese is not None

    tekst = uitvoer.synthese.read_text(encoding="utf-8")
    totaal = json.loads((tmp_path / "totaal" / "bevindingen.json").read_text(encoding="utf-8"))

    per_gebied = sum(len(bouw_meldingen(run.run, RUNDATUM)) for run in runs)
    assert "in meer dan een gebied" in tekst
    assert totaal["aantal_meldingen"] < per_gebied


def test_synthese_telt_de_onderdrukte_meldingen_over_alle_gebieden(tmp_path: Path) -> None:
    """Issue #65: wat `[rapport]` uit de stroom hield, staat ook in de totaalsynthese.

    De som over de gebieden, niet ontdubbeld -- net als de kolom Meldingen ernaast; de
    telling per check en per klasse staat in de verantwoording van elk gebied.
    """
    config = _config()
    config.rapport.onderdruk_klassen = ["Leiding"]
    _, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path, config=config)
    assert uitvoer.synthese is not None

    tekst = uitvoer.synthese.read_text(encoding="utf-8")
    treffer = re.search(r"Over alle gebieden samen zijn (\d+) meldingen onderdrukt", tekst)
    totaal = json.loads((tmp_path / "totaal" / "bevindingen.json").read_text(encoding="utf-8"))

    assert treffer is not None, tekst
    assert int(treffer.group(1)) > 0
    assert "op grond van `[rapport]`" in tekst
    # Dezelfde som in de totaal-JSON: twee uitvoervormen die uit elkaar lopen is precies
    # wat de gedeelde meldingenstroom uitsluit.
    assert totaal["onderdrukt"] == {
        "klassen": ["Leiding"],
        "checks": [],
        "meldingen": int(treffer.group(1)),
    }


def test_synthese_zwijgt_zonder_onderdrukking(tmp_path: Path) -> None:
    """Geen keuze om te verantwoorden, dus geen regel."""
    _, uitvoer = _schrijf("buurten_twee.gpkg", tmp_path)

    assert uitvoer.synthese is not None
    assert "op grond van `[rapport]`" not in uitvoer.synthese.read_text(encoding="utf-8")


def test_synthese_vermeldt_een_selectie(tmp_path: Path) -> None:
    gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")
    keuze = gebieden.selecteer(["Noord"])
    runs = toets_gebieden(
        load_dataset(TTL_DIR / "hgt010_diameterverjonging.ttl"),
        keuze,
        _config(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )

    uitvoer = schrijf_uitvoer_gebieden(runs, tmp_path, RUNDATUM, beschikbaar=keuze.beschikbaar)

    assert uitvoer.synthese is not None
    assert "Selectie" in uitvoer.synthese.read_text(encoding="utf-8")


def _met_leeg_gebied(pad: Path) -> Path:
    """Een gebiedsbestand met een gevulde buurt en een lege ernaast."""
    return schrijf_buurten(
        pad,
        [("Noord", box(990, 1990, 1060, 2010)), ("Leeg", box(5000, 5000, 5100, 5100))],
    )


def test_een_leeg_gebied_sloopt_de_run_niet(tmp_path: Path) -> None:
    """Een buurt zonder riolering (water, natuur) is normaal en mag geen fout zijn."""
    gebieden = load_studiegebieden(_met_leeg_gebied(tmp_path / "b.gpkg"))

    runs = toets_gebieden(
        load_dataset(TTL_DIR / "hgt010_diameterverjonging.ttl"),
        gebieden,
        _config(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )

    leeg = next(run for run in runs if run.naam == "Leeg")
    assert leeg.run.analyseset is not None
    assert not leeg.run.analyseset.kern
    assert not leeg.run.findings


def test_een_leeg_gebied_wordt_luid_gemeld(tmp_path: Path) -> None:
    """Nul bevindingen op een leeg gebied leest anders als 'hier is alles in orde'."""
    gebieden = load_studiegebieden(_met_leeg_gebied(tmp_path / "b.gpkg"))
    runs = toets_gebieden(
        load_dataset(TTL_DIR / "hgt010_diameterverjonging.ttl"),
        gebieden,
        _config(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )

    uitvoer = schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM)

    assert uitvoer.synthese is not None
    assert "geen enkel GWSW-object" in uitvoer.synthese.read_text(encoding="utf-8")
    rapport = (tmp_path / "uit" / "leeg" / "bevindingen.md").read_text(encoding="utf-8")
    assert "Geen objecten in dit gebied" in rapport


def test_een_leeg_enkel_gebied_blijft_een_harde_fout(tmp_path: Path) -> None:
    """Bij een run op een enkel gebied is een leeg gebied bijna altijd de verkeerde laag."""
    bestand = schrijf_buurten(tmp_path / "een.gpkg", [("Leeg", box(5000, 5000, 5100, 5100))])

    with pytest.raises(StudyAreaError, match="geen GWSW-objecten"):
        toets_gebieden(
            load_dataset(TTL_DIR / "hgt010_diameterverjonging.ttl"),
            load_studiegebieden(bestand),
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )


def test_overgeslagen_geometrieen_staan_in_het_rapport(tmp_path: Path) -> None:
    """Ook bij een enkel gebied, waar er geen synthese is om het in te zetten."""
    pad = tmp_path / "gemengd.geojson"
    pad.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:28992"}},
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": mapping(box(990, 1990, 1060, 2010)),
                    },
                    {"type": "Feature", "properties": {}, "geometry": mapping(Point(1000, 2000))},
                ],
            }
        ),
        encoding="utf-8",
    )
    gebieden = load_studiegebieden(pad)
    runs = toets_gebieden(
        load_dataset(TTL_DIR / "hgt010_diameterverjonging.ttl"),
        gebieden,
        _config(),
        meetbereik=Meetbereik.niet_gemeten(()),
    )

    schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM, overgeslagen=gebieden.overgeslagen)

    rapport = (tmp_path / "uit" / "bevindingen.md").read_text(encoding="utf-8")
    assert "Studiegebiedbestand" in rapport and "Point" in rapport


def _laag_ids(pad: Path, laag: str) -> list[str]:
    """De id-kolom van een laag in een geschreven GeoPackage."""
    verbinding = sqlite3.connect(f"file:{pad}?mode=ro", uri=True)
    try:
        return [rij[0] for rij in verbinding.execute(f'select id from "{laag}"')]
    finally:
        verbinding.close()


def test_treffers_blijven_bij_hun_eigen_gebied(tmp_path: Path) -> None:
    """Een pand dat alleen vanuit Noord geraakt wordt, hoort niet in de uitvoer van Zuid.

    Dat volgt uit de strikte aansluiting: de laag komt uit de meldingen van dat
    gebied, niet uit het register.
    """
    bron = tmp_path / "bron"
    bron.mkdir()
    schrijf_vlakken(
        bron / "bgt.gpkg", "pand", [({"lokaal_id": "p-noord"}, box(1000, 2000.5, 1010, 2005))]
    )
    schrijf_vlakken(
        bron / "studiegebied.gpkg",
        "studiegebied",
        [({"lokaal_id": "g"}, box(990, 1985, 1160, 2015))],
    )
    config = _config()
    bronnen = load_external_data(
        config.bronnen.model_copy(
            update={
                "map": ".",
                "bgt": "bgt.gpkg",
                "bag_pand": None,
                "nwb_wegvakken": None,
                "studiegebied": "studiegebied.gpkg",
                "ahn_dtm": None,
                "bgt_pandlagen": ["pand"],
            }
        ),
        bron,
    )
    gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")

    runs = toets_gebieden(
        load_dataset(TTL_DIR / "ext_scenario.ttl"),
        gebieden,
        config,
        bronnen=bronnen,
        check_ids=["EXT-001"],
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM)

    noord = next((tmp_path / "uit" / "noord").glob("*.gpkg"))
    zuid = next((tmp_path / "uit" / "zuid").glob("*.gpkg"))

    assert _laag_ids(noord, "bouwwerken") == ["bgt:pand/p-noord"]
    assert _laag_ids(zuid, "bouwwerken") == []


def _ext_bronnen(bron: Path, panden: list[tuple[dict[str, str], object]]) -> object:
    """Miniatuurbronnen met een eigen pandenlaag over de EXT-scenariofixture."""
    bron.mkdir(parents=True, exist_ok=True)
    schrijf_vlakken(bron / "bgt.gpkg", "pand", panden)
    schrijf_vlakken(
        bron / "studiegebied.gpkg",
        "studiegebied",
        [({"lokaal_id": "g"}, box(990, 1985, 1160, 2015))],
    )
    return load_external_data(
        load_check_config().bronnen.model_copy(
            update={
                "map": ".",
                "bgt": "bgt.gpkg",
                "bag_pand": None,
                "nwb_wegvakken": None,
                "studiegebied": "studiegebied.gpkg",
                "ahn_dtm": None,
                "bgt_pandlagen": ["pand"],
            }
        ),
        bron,
    )


def test_grenspand_staat_in_beide_gebieden(tmp_path: Path) -> None:
    """Een pand dat vanuit beide buurten geraakt wordt, hoort in beide GeoPackages.

    De andere helft van de dubbeltellingskeuze: de per-gebied-join mag niets
    kwijtraken.
    """
    # Streng 2 loopt van (1050, 2000) naar (1090, 2000) en kruist de buurtgrens op
    # x = 1060; dit pand ligt eroverheen en wordt dus vanuit Noord en Zuid geraakt.
    bronnen = _ext_bronnen(
        tmp_path / "bron", [({"lokaal_id": "p-grens"}, box(1055, 1999, 1065, 2001))]
    )
    runs = toets_gebieden(
        load_dataset(TTL_DIR / "ext_scenario.ttl"),
        load_studiegebieden(GIS_DIR / "buurten_twee.gpkg"),
        _config(),
        bronnen=bronnen,
        check_ids=["EXT-001"],
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM)

    noord = next((tmp_path / "uit" / "noord").glob("*.gpkg"))
    zuid = next((tmp_path / "uit" / "zuid").glob("*.gpkg"))

    assert _laag_ids(noord, "bouwwerken") == ["bgt:pand/p-grens"]
    assert _laag_ids(zuid, "bouwwerken") == ["bgt:pand/p-grens"]


def test_een_check_op_de_volledige_export_verliest_zijn_treffers_niet(tmp_path: Path) -> None:
    """`volledige_dataset_checks` draait op een gedeelde context met een eigen register.

    Zonder het doorgeven van het register zou de melding wel een `object2_uri` dragen
    en de laag leeg blijven -- de stille afwijking tussen laag en uitslag die dit
    ontwerp uitsluit.
    """
    bronnen = _ext_bronnen(
        tmp_path / "bron", [({"lokaal_id": "p-noord"}, box(1000, 2000.5, 1010, 2005))]
    )
    config = _config()
    config.studiegebied.volledige_dataset_checks = ["EXT-001"]

    runs = toets_gebieden(
        load_dataset(TTL_DIR / "ext_scenario.ttl"),
        load_studiegebieden(GIS_DIR / "buurten_twee.gpkg"),
        config,
        bronnen=bronnen,
        check_ids=["EXT-001"],
        meetbereik=Meetbereik.niet_gemeten(()),
    )
    schrijf_uitvoer_gebieden(runs, tmp_path / "uit", RUNDATUM)

    noord = next(run for run in runs if run.naam == "Noord")
    aangewezen = {m.object2_uri for m in bouw_meldingen(noord.run, RUNDATUM) if m.object2_uri}
    geschreven = set(_laag_ids(next((tmp_path / "uit" / "noord").glob("*.gpkg")), "bouwwerken"))

    assert aangewezen == {"bgt:pand/p-noord"}
    assert geschreven == aangewezen


class TestNulmetingPerGebied:
    """De nulmetingmeldingen volgen dezelfde equivalentie-eis als de eigen checks."""

    def test_een_gebied_is_gelijk_aan_een_losse_run(self) -> None:
        samen = _draai("buurten_twee.gpkg", nulbevindingen=NULBEVINDINGEN)
        los = _draai("buurt_noord.gpkg", nulbevindingen=NULBEVINDINGEN)

        noord = next(run for run in samen if run.naam == "Noord")

        assert _sleutels(noord) == _sleutels(los[0])

    def test_de_gebieden_zien_verschillende_putten(self) -> None:
        """Anders zou de equivalentietest ook slagen als de afbakening niets deed."""
        noord, zuid = _draai("buurten_twee.gpkg", nulbevindingen=NULBEVINDINGEN)

        def herleid(run: GebiedsRun) -> set[str]:
            return {b.focus_node for b in run.run.nulbevindingen if b.herleid}

        assert herleid(noord) and herleid(zuid)
        assert herleid(noord) != herleid(zuid)

    def test_een_onherleide_bevinding_staat_in_elk_gebied(self) -> None:
        """Hij is aan geen gebied toe te wijzen, dus hij mag uit geen gebied verdwijnen."""
        noord, zuid = _draai("buurten_twee.gpkg", nulbevindingen=NULBEVINDINGEN)

        for run in (noord, zuid):
            assert any(not b.herleid for b in run.run.nulbevindingen)

    def test_de_totaalsynthese_ontdubbelt_de_onherleide_bevinding(self, tmp_path: Path) -> None:
        """In `totaal/` staat hij een keer, want daar wordt op melding-ID ontdubbeld."""
        gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
            nulbevindingen=NULBEVINDINGEN,
        )
        schrijf_uitvoer_gebieden(runs, tmp_path, RUNDATUM, met_geopackage=False)

        regels = (tmp_path / "totaal" / "bevindingen.csv").read_text(encoding="utf-8").splitlines()
        onherleid = [regel for regel in regels if "Rioolstelsel" in regel]

        assert len(onherleid) == 1
