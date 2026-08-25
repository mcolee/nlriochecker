"""De nulmetingmeldingen in de vier uitvoervormen.

De omzetting zelf staat in `test_nulbevinding.py` en `test_uitvoer_melding.py`; hier
staat wat er van terechtkomt in het rapport, de CSV, de GeoPackage en de JSON. Dat
zijn vier bestanden uit een meldingenstroom, en dit bestand is de plek waar een
verschil tussen die vier opvalt.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import Meetbereik, laad_nulmeting
from nlriochecker.nulbevinding import bouw_nulbevindingen
from nlriochecker.uitvoer.bevindingen import FILE_CHECKS_CSV, FILE_CHECKS_JSON
from nlriochecker.uitvoer.melding import bouw_meldingen
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"
RUNDATUM = date(2026, 8, 19)
CFKS = ["MdsPlan", "MdsProj"]


def _run(check_ids: list[str] | None = None) -> CheckRun:
    """Een run over de join-fixture, met de nulbevindingen van twee CFK-rapporten.

    Zonder `check_ids` draait er geen enkele eigen check: deze tests gaan over de
    nulmeting. Een test die de twee bronnen naast elkaar wil zien, vraagt er een.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    dataset = load_dataset(TTL_DIR / "nulmeting_join.ttl")
    nulmeting = laad_nulmeting(
        [SHACL_DIR / "join_mdsplan.csv", SHACL_DIR / "join_mdsproj.csv"], CFKS, CFKS
    )
    run = run_checks(CheckContext(dataset=dataset, config=config), check_ids or [])
    return replace(
        run,
        nulbevindingen=tuple(
            bouw_nulbevindingen(nulmeting, dataset, config.rapport.systemisch_drempel)
        ),
        meetbereik=Meetbereik.van(CFKS, CFKS),
        typing_gate_applied=True,
    )


def test_de_csv_draagt_de_conformiteitsklassen(tmp_path: Path) -> None:
    """De kolom `CFK` somt op welke klassen de overtreding noemen."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM, met_geopackage=False)

    tabel = pd.read_csv(uitvoer.csv, sep=";")
    put_a = tabel[(tabel["Check"] == "NULMETING-Put_HoogtePut_card") & (tabel["Label"] == "A")]

    assert list(put_a["CFK"]) == ["MdsPlan, MdsProj"]
    assert list(put_a["Bron"]) == ["nulmeting"]


def test_een_eigen_check_laat_de_kolom_leeg(tmp_path: Path) -> None:
    """De kolom bestaat op elke rij; alleen de nulmeting vult hem."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM, met_geopackage=False)

    tabel = pd.read_csv(uitvoer.csv, sep=";", keep_default_na=False)
    eigen = tabel[tabel["Bron"] == "register"]

    assert set(eigen["CFK"]) <= {""}


def test_de_json_draagt_de_klassen_als_lijst(tmp_path: Path) -> None:
    """Een tuple in de code hoort in het contract een array te zijn."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM, met_geopackage=False)

    assert uitvoer.json is not None
    document = json.loads((tmp_path / FILE_CHECKS_JSON).read_text(encoding="utf-8"))
    nulmeldingen = [m for m in document["meldingen"] if m["bron"] == "nulmeting"]

    assert nulmeldingen
    assert all(isinstance(melding["cfk"], list) for melding in nulmeldingen)
    assert {"MdsPlan", "MdsProj"} == set(
        melding["cfk"][0] for melding in nulmeldingen if len(melding["cfk"]) == 1
    ) | {"MdsPlan"}


def test_de_geopackage_meldingtabel_draagt_de_kolom_cfk(tmp_path: Path) -> None:
    """Wie in QGIS op de meldingentabel joint, moet de klasse kunnen zien."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM)

    assert uitvoer.geopackage is not None
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        rijen = verbinding.execute(
            "select cfk from meldingen where check_id = 'NULMETING-Put_HoogtePut_card'"
        ).fetchall()
    finally:
        verbinding.close()

    assert rijen and all(rij[0] == "MdsPlan, MdsProj" for rij in rijen)


def test_het_checkoverzicht_draagt_naast_het_register_ook_de_nulmeting(tmp_path: Path) -> None:
    """Een dashboard dat zich als de checklijst presenteert, mist anders de helft."""
    run = _run(["ATTR-008"])
    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM)

    assert uitvoer.geopackage is not None
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        vormen = {
            rij[0]
            for rij in verbinding.execute(
                "select check_id from overzicht_checks where bron = 'nulmeting'"
            )
        }
        ((nulrijen,), (register,)) = verbinding.execute(
            "select count(*) from overzicht_checks group by bron order by bron"
        ).fetchall()
        ((meldingrijen,),) = verbinding.execute("select count(*) from meldingen").fetchall()
    finally:
        verbinding.close()

    assert vormen == {f"NULMETING-{bevinding.vorm}" for bevinding in run.nulbevindingen}
    # Een rij per vorm, niet een rij per overtreding: de verzameling hierboven ziet
    # een dubbele rij niet, deze telling wel.
    assert nulrijen == len(vormen)
    # De register-rijen blijven ongemoeid: precies de gedraaide checks, niet meer.
    assert register == len(run.outcomes) == 1
    # En de meldingentabel is niet veranderd door de tweede bron in het dashboard.
    assert meldingrijen == len(bouw_meldingen(run, RUNDATUM))


def test_een_nulmetingrij_telt_zijn_vorm_en_laat_de_checkkolommen_leeg(tmp_path: Path) -> None:
    """Wat alleen een `CheckOutcome` weet, blijft leeg; een verzonnen getal is erger."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM)

    assert uitvoer.geopackage is not None
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        (rij,) = verbinding.execute(
            "select omschrijving, ernst, categorie, dimensie, aantal_meldingen, bekeken, "
            "percentage_populatie, systemisch, aantal_gebieden, skelet, cfk "
            "from overzicht_checks where check_id = 'NULMETING-Put_HoogtePut_card'"
        ).fetchall()
    finally:
        verbinding.close()

    assert rij == ("", "F", "NULMETING", "Compliance", 4, None, None, 1, 0, "", "MdsPlan, MdsProj")


def test_de_puttenlaag_telt_de_nulmeldingen_in_haar_eigen_kolom(tmp_path: Path) -> None:
    """`n_nulmeting` stond al in de kolomset; nu is er ook een producent."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM)

    assert uitvoer.geopackage is not None
    verbinding = sqlite3.connect(f"file:{uitvoer.geopackage}?mode=ro", uri=True)
    try:
        ((aantal,),) = verbinding.execute(
            "select n_nulmeting from putten where label = 'A'"
        ).fetchall()
    finally:
        verbinding.close()

    assert aantal == 1


def test_het_rapport_noemt_de_nulmeting_en_wat_er_niet_op_de_kaart_kwam(tmp_path: Path) -> None:
    """Stilte over een gebrek dat de nulmeting telt, leest als 'alles gecontroleerd'."""
    uitvoer = schrijf_uitvoer(_run(), tmp_path, RUNDATUM, met_geopackage=False)

    tekst = uitvoer.markdown.read_text(encoding="utf-8")

    assert "GWSW-nulmeting" in tekst
    assert "MdsPlan" in tekst and "MdsProj" in tekst
    # Twee overtredingen komen niet op de kaart: de klassenaam `Rioolstelsel` uit
    # `CfkTypes_typ` en het geregistreerde stelsel `vw_geb_1`. Sinds issue #75 tekent de
    # GeoPackage geen stelselvlakken meer, dus die tweede hoort ook hier geteld te worden
    # in plaats van stil te verdwijnen.
    assert "2 overtredingen kregen geen kaartobject" in tekst
    assert "1 met een klassenaam uit `CfkTypes_typ`" in tekst
    assert "1 op een geregistreerd stelsel" in tekst


def test_zonder_nulmeting_schrijft_het_rapport_geen_nulmetingblok(tmp_path: Path) -> None:
    """Een run zonder `--shacl` is niet gemeten, en zegt dan ook niets over de meting."""
    run = replace(
        _run(),
        nulbevindingen=(),
        meetbereik=Meetbereik.niet_gemeten(CFKS),
        typing_gate_applied=False,
    )

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM, met_geopackage=False)
    tekst = uitvoer.markdown.read_text(encoding="utf-8")
    tabel = pd.read_csv(tmp_path / FILE_CHECKS_CSV, sep=";", keep_default_na=False)

    assert "**GWSW-nulmeting**" not in tekst
    assert "SHACL-nulmeting" not in tekst
    # Zonder meting geen nulmetingmeldingen; register en de datasetsignalen (issue #22)
    # mogen er wel zijn.
    assert "nulmeting" not in set(tabel["Bron"])


def test_een_gemeten_run_zonder_overtredingen_zegt_dat_met_zoveel_woorden(
    tmp_path: Path,
) -> None:
    """Nul overtredingen is een uitslag; hem verzwijgen leest als 'niet gemeten'."""
    run = replace(_run(), nulbevindingen=())

    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM, met_geopackage=False)
    tekst = uitvoer.markdown.read_text(encoding="utf-8")

    assert "**GWSW-nulmeting**" in tekst
    assert "0 overtredingen uit de SHACL-nulmeting" in tekst
