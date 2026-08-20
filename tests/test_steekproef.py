"""Tests voor `scripts/steekproef.py`: de handmatige-controlesteekproef.

De fixture is een miniatuur van wat `toets` schrijft: een `meldingen`-tabel met de
kolommen die het script leest, een `overzicht_checks` met een rij per check, en de
lagen `putten` en `strengen` met geometrie in hetzelfde blobformaat als de echte
uitvoer. Zo toetst de test het script en niet een eigen nabootsing van de bron.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from shapely.geometry import LineString, Point

from nlriochecker.uitvoer import gpkg

WORTEL = Path(__file__).resolve().parents[1]


def _laad_script() -> ModuleType:
    """Laadt `scripts/steekproef.py` als module; scripts/ is geen package."""
    pad = WORTEL / "scripts" / "steekproef.py"
    specificatie = importlib.util.spec_from_file_location("steekproef", pad)
    assert specificatie is not None and specificatie.loader is not None
    module = importlib.util.module_from_spec(specificatie)
    sys.modules["steekproef"] = module
    specificatie.loader.exec_module(module)
    return module


steekproef = _laad_script()


def _melding(melding_id: str, check_id: str, x: float | None, y: float | None) -> dict[str, Any]:
    """Een melding met alleen de velden die de trekking leest."""
    return {"melding_id": melding_id, "check_id": check_id, "x": x, "y": y}


def _bron_geopackage(pad: Path, meldingen: list[tuple], checks: list[tuple]) -> Path:
    """Schrijft een miniatuur van de GeoPackage die `toets` oplevert."""
    verbinding = sqlite3.connect(pad)
    verbinding.execute(
        "create table meldingen (melding_id text, check_id text, categorie text, ernst text, "
        "dimensie text, boodschap text, waarde text, drempel text, systemisch integer, "
        "feature_id text, label text, feature_id_2 text, gwsw_uri text, gwsw_uri_2 text, "
        "gebied text, prioriteit integer, x real, y real, run_datum text, bron text)"
    )
    verbinding.executemany(
        "insert into meldingen values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        meldingen,
    )
    verbinding.execute(
        "create table overzicht_checks (check_id text, omschrijving text, bron text, "
        "ernst text, categorie text, dimensie text, aantal_meldingen integer, bekeken integer, "
        "skelet text)"
    )
    verbinding.executemany(
        "insert into overzicht_checks values (?, ?, ?, ?, ?, ?, ?, ?, ?)", checks
    )
    for laag, geometrie in (
        ("putten", Point(220000.0, 526000.0)),
        ("strengen", LineString([(220000.0, 526000.0), (220050.0, 526050.0)])),
    ):
        verbinding.execute(
            f'create table "{laag}" (fid integer primary key, gwsw_uri text, objecttype text, '
            "geom blob)"
        )
        verbinding.execute(
            f'insert into "{laag}" (gwsw_uri, objecttype, geom) values (?, ?, ?)',
            (f"http://x#{laag}1", laag[:-1], steekproef.GPB_KOP + geometrie.wkb),
        )
    verbinding.commit()
    verbinding.close()
    return pad


def test_trekking_is_gespreid_over_de_cellen() -> None:
    """Een check waarvan alle bevindingen op een hoop liggen levert toch spreiding op."""
    dichtbij = [_melding(f"a{i:03d}", "TOP-001", 220000.0 + i, 526000.0) for i in range(50)]
    verspreid = [
        _melding(f"b{i:03d}", "TOP-001", 220000.0 + i * 3000.0, 526000.0) for i in range(5)
    ]
    keuze = steekproef.trek(dichtbij + verspreid, 5, "seed:TOP-001", 1000.0)

    cellen = {steekproef.cel(m["x"], m["y"], 1000.0) for m in keuze}
    assert len(keuze) == 5
    assert len(cellen) == 5, "elke getrokken melding hoort uit een andere cel te komen"


def test_trekking_is_reproduceerbaar_en_verschilt_per_check() -> None:
    """Dezelfde seed geeft dezelfde trekking; een andere check een andere."""
    meldingen = [
        _melding(f"a{i:03d}", "TOP-001", 220000.0 + i * 100.0, 526000.0) for i in range(40)
    ]

    eerst = steekproef.trek(meldingen, 10, "seed:TOP-001", 1000.0)
    nogmaals = steekproef.trek(meldingen, 10, "seed:TOP-001", 1000.0)
    andere_check = steekproef.trek(meldingen, 10, "seed:TOP-002", 1000.0)

    assert [m["melding_id"] for m in eerst] == [m["melding_id"] for m in nogmaals]
    assert [m["melding_id"] for m in eerst] != [m["melding_id"] for m in andere_check]


def test_minder_dan_gevraagd_levert_alles_op() -> None:
    """Een check met drie bevindingen levert die drie, niet een fout."""
    meldingen = [_melding(f"a{i}", "TOP-001", 220000.0 + i * 2000.0, 526000.0) for i in range(3)]
    assert len(steekproef.trek(meldingen, 10, "seed", 1000.0)) == 3


def test_meldingen_zonder_locatie_komen_pas_als_laatste_aan_de_beurt() -> None:
    """Wie geen plek heeft is in QGIS niet aan te wijzen en gaat dus achteraan."""
    met_plek = [_melding(f"a{i}", "TOP-001", 220000.0 + i * 2000.0, 526000.0) for i in range(3)]
    zonder = [_melding(f"z{i}", "TOP-001", None, None) for i in range(5)]

    keuze = steekproef.trek(met_plek + zonder, 4, "seed", 1000.0)

    assert sum(1 for m in keuze if m["x"] is not None) == 3
    assert all(m["melding_id"].startswith("a") for m in keuze[:3])
    assert keuze[-1]["melding_id"].startswith("z")


@pytest.mark.parametrize(
    ("skelet", "bekeken", "verwacht"),
    [
        ("", 100, "geen bevindingen"),
        ("", 0, "niets bekeken"),
        ("vereist inwinningsmetagegevens", 0, "skelet: vereist inwinningsmetagegevens"),
    ],
)
def test_reden_maakt_stilte_leesbaar(skelet: str, bekeken: int, verwacht: str) -> None:
    """Een lege steekproef krijgt altijd een reden; stilte leest anders als 'schoon'."""
    check = {"skelet": skelet, "bekeken": bekeken}
    assert steekproef.reden(check, 0) == verwacht
    assert steekproef.reden(check, 3) == ""


def test_schrijft_een_geopackage_met_de_vier_lagen(tmp_path: Path) -> None:
    """De volledige gang: van een run-GeoPackage naar een steekproefbestand."""
    meldingen = [
        (
            f"TOP-001-{i:03d}",
            "TOP-001",
            "TOP",
            "F",
            "Consistentie",
            "boodschap",
            "1,0",
            "0,5",
            0,
            "putten1",
            "Put 1",
            "",
            "http://x#putten1",
            "",
            "",
            1,
            220000.0 + i * 2000.0,
            526000.0,
            "2026-08-20",
            "register",
        )
        for i in range(4)
    ] + [
        (
            "NET-003-001",
            "NET-003",
            "NET",
            "F",
            "Plausibiliteit",
            "bodem stijgt",
            "",
            "",
            0,
            "strengen1",
            "Streng 1",
            "",
            "http://x#strengen1",
            "",
            "",
            1,
            220025.0,
            526025.0,
            "2026-08-20",
            "register",
        ),
        (
            "NUL-001",
            "LengteLeiding_val",
            "NULMETING",
            "F",
            "Compliance",
            "uit de nulmeting",
            "",
            "",
            0,
            "putten1",
            "Put 1",
            "",
            "http://x#putten1",
            "",
            "",
            1,
            220000.0,
            526000.0,
            "2026-08-20",
            "nulmeting",
        ),
    ]
    checks = [
        ("TOP-001", "Put zonder aansluiting", "register", "F", "TOP", "Consistentie", 4, 100, ""),
        ("NET-003", "Bodem stijgt", "register", "F", "NET", "Plausibiliteit", 1, 100, ""),
        ("BTR-001", "Inwinning", "register", "W", "BTR", "Traceerbaarheid", 0, 0, "vereist meta"),
    ]
    bron = _bron_geopackage(tmp_path / "run.gpkg", meldingen, checks)
    doel = tmp_path / "steekproef.gpkg"

    tellingen = steekproef.schrijf_steekproef(bron, doel, 10, "seed", 1000.0)

    assert tellingen[steekproef.LAAG_PUTTEN] == 4
    assert tellingen[steekproef.LAAG_STRENGEN] == 1
    assert tellingen[steekproef.LAAG_LOCATIES] == 5

    verbinding = sqlite3.connect(doel)
    lagen = {naam for (naam,) in verbinding.execute("select table_name from gpkg_contents")}
    assert lagen == {
        steekproef.LAAG_PUTTEN,
        steekproef.LAAG_STRENGEN,
        steekproef.LAAG_LOCATIES,
        steekproef.TABEL_DEKKING,
        steekproef.TABEL_RUN,
    }

    # De nulmeting blijft erbuiten: alleen de eigen checks.
    check_ids = {
        naam for (naam,) in verbinding.execute(f"select check_id from {steekproef.LAAG_LOCATIES}")
    }
    assert check_ids == {"TOP-001", "NET-003"}

    # Elke eigen check staat in de dekkingstabel, ook het skelet zonder bevindingen.
    dekking = {
        rij[0]: rij[1:]
        for rij in verbinding.execute(
            f"select check_id, getrokken, reden from {steekproef.TABEL_DEKKING}"
        )
    }
    assert dekking == {
        "TOP-001": (4, ""),
        "NET-003": (1, ""),
        "BTR-001": (0, "skelet: vereist meta"),
    }

    # De herkomst staat in het bestand, en de trekking is over te doen.
    gereedschap, seed = verbinding.execute(
        f"select gereedschap, seed from {steekproef.TABEL_RUN}"
    ).fetchone()
    assert gereedschap.startswith("nlriochecker ")
    assert seed == "seed"

    # De omhullende is gevuld; zonder haar zoomt QGIS niet naar de laag.
    grenzen = verbinding.execute(
        "select min_x, min_y, max_x, max_y from gpkg_contents where table_name = ?",
        (steekproef.LAAG_PUTTEN,),
    ).fetchone()
    assert grenzen == (220000.0, 526000.0, 220000.0, 526000.0)
    verbinding.close()


def test_weigert_een_geopackage_met_een_vreemde_geometriekop() -> None:
    """Een blob van ander gereedschap wordt geweigerd in plaats van verkeerd ontleed."""
    with pytest.raises(ValueError, match="onbekende geometriekop"):
        steekproef._wkb(b"GP" + bytes([0, 3]) + b"\x00" * 8)


def test_leest_alleen_namen_die_de_schrijver_van_de_run_ook_kent() -> None:
    """De namen die dit script leest komen uit `uitvoer/gpkg.py` en mogen niet driften.

    Het script leest de tabellen van een andere module op naam. Die namen zijn al een
    keer veranderd (`meldinglocaties` werd `x`/`y`, issue #13), en de fixture hierboven
    is met de hand geschreven en zou zo'n hernoeming dus niet merken. Deze drie
    beweringen wel: twee kolomlijsten en de koptekst van elke geometrieblob.
    """
    assert set(steekproef.MELDINGVELDEN) <= {kolom.naam for kolom in gpkg.MELDING_KOLOMMEN}
    assert set(steekproef.CHECKVELDEN) <= {kolom.naam for kolom in gpkg.OVERZICHT_KOLOMMEN}
    assert steekproef.GPB_KOP == gpkg._blob(Point(0.0, 0.0))[: len(steekproef.GPB_KOP)]


@pytest.mark.parametrize(
    ("aantal", "meldingen"),
    [
        (0, "gevuld"),
        (10, "leeg"),
        (10, "alleen_zonder_locatie"),
        (1, "een_cel"),
    ],
)
def test_trekking_loopt_niet_vast_op_de_randgevallen(aantal: int, meldingen: str) -> None:
    """De trekking eindigt altijd; een lus die blijft hangen bevriest het script."""
    bakken = {
        "gevuld": [_melding(f"a{i}", "T", 220000.0 + i * 2000.0, 526000.0) for i in range(5)],
        "leeg": [],
        "alleen_zonder_locatie": [_melding(f"z{i}", "T", None, None) for i in range(3)],
        "een_cel": [_melding(f"a{i}", "T", 220000.0 + i, 526000.0) for i in range(4)],
    }
    keuze = steekproef.trek(bakken[meldingen], aantal, "seed", 1000.0)
    assert len(keuze) <= max(aantal, 0)
    assert len({m["melding_id"] for m in keuze}) == len(keuze)


def test_doel_mag_de_bron_niet_zijn(tmp_path: Path) -> None:
    """Een typefout in `--uit` mag geen run van minuten wissen."""
    bron = _bron_geopackage(tmp_path / "run.gpkg", [], [])
    with pytest.raises(ValueError, match="de bron-GeoPackage zelf"):
        steekproef.schrijf_steekproef(bron, tmp_path / "run.gpkg", 10, "seed", 1000.0)
    assert bron.is_file(), "de bron hoort er na de weigering nog te staan"


def test_weigert_een_geopackage_die_geen_toets_run_is(tmp_path: Path) -> None:
    """Wie het script op een willekeurige GeoPackage richt krijgt een leesbare melding."""
    vreemd = tmp_path / "vreemd.gpkg"
    verbinding = sqlite3.connect(vreemd)
    verbinding.execute("create table iets (a text)")
    verbinding.commit()
    verbinding.close()

    with pytest.raises(ValueError, match="mist de tabellen"):
        steekproef.schrijf_steekproef(vreemd, tmp_path / "uit.gpkg", 10, "seed", 1000.0)


def test_geschreven_bestand_is_met_gdal_te_lezen(tmp_path: Path) -> None:
    """QGIS leest via GDAL; een bestand dat pyogrio niet opent is onbruikbaar."""
    pyogrio = pytest.importorskip("pyogrio")
    meldingen = [
        (
            "TOP-001-001",
            "TOP-001",
            "TOP",
            "F",
            "Consistentie",
            "boodschap",
            "",
            "",
            0,
            "putten1",
            "Put 1",
            "",
            "http://x#putten1",
            "",
            "",
            1,
            220000.0,
            526000.0,
            "2026-08-20",
            "register",
        ),
        (
            "NET-003-001",
            "NET-003",
            "NET",
            "F",
            "Plausibiliteit",
            "bodem stijgt",
            "",
            "",
            0,
            "strengen1",
            "Streng 1",
            "",
            "http://x#strengen1",
            "",
            "",
            1,
            220025.0,
            526025.0,
            "2026-08-20",
            "register",
        ),
    ]
    checks = [
        ("TOP-001", "Put", "register", "F", "TOP", "Consistentie", 1, 100, ""),
        ("NET-003", "Streng", "register", "F", "NET", "Plausibiliteit", 1, 100, ""),
    ]
    bron = _bron_geopackage(tmp_path / "run.gpkg", meldingen, checks)
    doel = tmp_path / "steekproef.gpkg"
    steekproef.schrijf_steekproef(bron, doel, 10, "seed", 1000.0)

    lagen = {naam: soort for naam, soort in pyogrio.list_layers(doel)}
    assert lagen[steekproef.LAAG_PUTTEN] == "Point"
    assert lagen[steekproef.LAAG_STRENGEN] == "LineString"
    assert lagen[steekproef.LAAG_LOCATIES] == "Point"

    tabel = pyogrio.read_dataframe(doel, layer=steekproef.LAAG_LOCATIES)
    assert tabel.crs.to_epsg() == 28992
    assert set(tabel["objectlaag"]) == {"putten", "strengen"}
    assert list(tabel["oordeel"]) == ["", ""]


def test_dekking_telt_de_lagen_sluitend(tmp_path: Path) -> None:
    """`getrokken` is de som van de puttenlaag, de strengenlaag en wat nergens landde."""
    meldingen = [
        (
            "TOP-001-001",
            "TOP-001",
            "TOP",
            "F",
            "Consistentie",
            "op een put",
            "",
            "",
            0,
            "putten1",
            "Put 1",
            "",
            "http://x#putten1",
            "",
            "",
            1,
            220000.0,
            526000.0,
            "2026-08-20",
            "register",
        ),
        (
            "TOP-001-002",
            "TOP-001",
            "TOP",
            "F",
            "Consistentie",
            "op niets",
            "",
            "",
            0,
            "weg",
            "Weg",
            "",
            "http://x#bestaat-niet",
            "",
            "",
            1,
            221000.0,
            526000.0,
            "2026-08-20",
            "register",
        ),
    ]
    checks = [("TOP-001", "Put", "register", "F", "TOP", "Consistentie", 2, 100, "")]
    bron = _bron_geopackage(tmp_path / "run.gpkg", meldingen, checks)
    doel = tmp_path / "steekproef.gpkg"
    tellingen = steekproef.schrijf_steekproef(bron, doel, 10, "seed", 1000.0)

    verbinding = sqlite3.connect(doel)
    getrokken, zonder_locatie, zonder_object = verbinding.execute(
        f'select getrokken, zonder_locatie, zonder_object from "{steekproef.TABEL_DEKKING}"'
    ).fetchone()
    verbinding.close()

    assert (getrokken, zonder_locatie, zonder_object) == (2, 0, 1)
    assert getrokken == tellingen[steekproef.LAAG_PUTTEN] + zonder_object
