"""Waardegelijkheid tussen de drie archieven, en de objectlagen tegen de meldingentabel.

De harde regel "één uitvoerschrijver" wordt bewaakt door een sweep die een tweede
schrijver in `src/` verbiedt, en door twee drifttests die kolom*namen* vergelijken
(`tests/test_uitvoer_herkomst.py`). Geen van drieën kijkt naar de geschreven *waarden*:
verwissel twee entries in `CSV_VELD_NAAR_KOLOM`, of laat `_melding_rij` het objectlabel
in de kolom `boodschap` zetten, en ze blijven alle drie groen. SQLite is zwak getypeerd
en de CSV is tekst, dus zo'n verwisseling leest als een geldige waarde.

Deze module dicht dat gat op drie plekken (issue #114):

1. per `melding_id` draagt elk veld van `Melding` in CSV, JSON en GeoPackage dezelfde
   waarde -- met precies de normalisaties die de drie formaten nu eenmaal verschillen
   (bool als tekst/`true`/`1`, een punt als X/Y-paar of lijst, `cfk` als tekst of lijst);
2. de samenvattingskolommen van `putten` en `strengen` kloppen met de meldingentabel in
   datzelfde bestand;
3. de negen categoriekolommen tellen samen precies de meldingen op het object.

Er wordt niets in `src/` beweerd dat er niet al staat: slaat een assertie aan, dan staat
er een echte verwisseling in de uitvoer.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, fields, replace
from pathlib import Path

import pandas as pd
import pytest

from nlriochecker.checks import CheckRun
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.uitvoer.bevindingen import (
    CSV_KOLOMMEN,
    CSV_VELD_NAAR_KOLOM,
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
)
from nlriochecker.uitvoer.gpkg import CATEGORIEEN, MELDING_KOLOMMEN, MELDING_VELD_NAAR_KOLOM
from nlriochecker.uitvoer.herkomst import KOLOM_GEREEDSCHAP
from nlriochecker.uitvoer.melding import Melding, Meldingenstroom, bouw_meldingenstroom
from nlriochecker.uitvoer.objectkaart import (
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ORANJE,
    STATUS_ROOD,
)
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer
from test_uitvoer_gpkg import RUNDATUM, _laagrijen, _run

# De fixture van issue #114: twee kruisende strengen en vier putten. Zij levert de drie
# randgevallen die deze test nodig heeft zonder extra machinerie -- een paarmelding
# (TOP-011 op L1, met L2 als tweede object), systemische meldingen en meldingen zonder
# object (`SIG-nulklasse`). Gegenereerd door `scripts/maak_ttl_fixtures.py`; niet met de
# hand bewerken.
FIXTURE = "top011_hartlijnkruising.ttl"

# De twee objectlagen. `vlakken` valt hierbuiten: die heeft een eigen kolomstelsel en
# draagt geen samenvatting per GWSW-object.
OBJECTLAGEN = ("putten", "strengen")

# De velden waarvan de drie formaten dezelfde waarde anders opschrijven. Precies deze en
# geen andere: elk ander verschil is een bevinding en geen reden om de test bij te buigen.
BOOLVELDEN = ("systemisch", "typering_betrouwbaar")
INTVELDEN = ("prioriteit",)
PUNTVELD = "foutlocatie"
LIJSTVELD = "cfk"


@dataclass(frozen=True)
class Archieven:
    """Eén `schrijf_uitvoer`, teruggelezen uit de drie bestanden die zij opleverde."""

    meldingen: list[Melding]
    csv: list[dict[str, str]]
    json: list[dict[str, object]]
    tabel: list[dict[str, object]]
    gpkg: Path


def _nulbevinding_op_put_a() -> Nulbevinding:
    """Een nulmetingmelding op put A, zodat `cfk` en `boodschap_technisch` gevuld zijn.

    Een leeg veld wordt vacuüm vergeleken: drie formaten die alle drie niets dragen zijn
    het per definitie eens. Deze bevinding vult de twee velden die een TTL-fixture niet
    kan leveren, met een `leesbaar` die van `boodschap` verschilt -- anders zou een
    verwisseling van `boodschap` en `boodschap_technisch` twee gelijke teksten ruilen.
    """
    return Nulbevinding(
        check_id="NULMETING-Put_HoogtePut_card",
        vorm="Put_HoogtePut_card",
        focus_node="PutA",
        ernst="F",
        object_uri="http://example.org/toets#PutA",
        object_label="A",
        objecttype="Inspectieput",
        boodschap="sh:minCount 1 op gwsw:HoogtePut",
        waarde="0 voorkomens",
        cfk=("MdsPlan", "MdsProj"),
        systemisch=False,
        herleid=True,
        leesbaar="De put draagt geen hoogte.",
    )


def _run_met_nulbevinding() -> CheckRun:
    """De fixture door alle checks, met één nulmetingbevinding erbij."""
    run = _run(FIXTURE)
    return replace(run, nulbevindingen=(_nulbevinding_op_put_a(),))


def _stroom_met_alle_velden(run: CheckRun) -> Meldingenstroom:
    """De meldingenstroom, met `drempel` en `gebied` op één melding gezet.

    Die twee zijn uit deze fixture niet te krijgen: `drempel` vullen alleen EXT-001 en
    EXT-009 (die externe bronnen vragen) en `gebied` vraagt een studiegebied. De keuze
    valt op een registermelding zónder tweede object, zodat de paarmelding ongemoeid
    blijft. Kunstmatig, en dat mag: het doel is kolomvulling, niet realisme.
    """
    stroom = bouw_meldingenstroom(run, RUNDATUM)
    meldingen = list(stroom.meldingen)
    doel = next(
        nummer
        for nummer, melding in enumerate(meldingen)
        if melding.bron == "register" and not melding.object2_uri
    )
    meldingen[doel] = replace(meldingen[doel], drempel="0.10", gebied="Testgebied")
    return Meldingenstroom(meldingen, stroom.onderdrukking)


@pytest.fixture(scope="module")
def archieven(tmp_path_factory: pytest.TempPathFactory) -> Archieven:
    """Schrijft de uitvoer één keer en leest de drie archieven terug.

    De CSV met `dtype=str, keep_default_na=False`: zonder die twee opties komen lege
    tekstkolommen als `float64`/`NaN` terug -- op deze fixture gemeten voor
    `Object2Label`, `Drempel`, `Gebied`, `CFK` en `MeldingTechnisch` -- en zou de
    vergelijking op een pandas-eigenaardigheid stuklopen in plaats van op de uitvoer.
    """
    run = _run_met_nulbevinding()
    stroom = _stroom_met_alle_velden(run)
    doel = tmp_path_factory.mktemp("gelijkheid")
    uitvoer = schrijf_uitvoer(run, doel, RUNDATUM, stroom=stroom)

    assert uitvoer.csv is not None and uitvoer.json is not None and uitvoer.geopackage is not None
    tabel = pd.read_csv(doel / FILE_CHECKS_CSV, sep=";", dtype=str, keep_default_na=False)
    document = json.loads((doel / FILE_CHECKS_JSON).read_text(encoding="utf-8"))
    return Archieven(
        meldingen=stroom.meldingen,
        csv=tabel.to_dict("records"),
        json=document["meldingen"],
        tabel=_laagrijen(uitvoer.geopackage, "meldingen"),
        gpkg=uitvoer.geopackage,
    )


def _op_id(rijen: list[dict], sleutel: str) -> dict[str, dict]:
    """De rijen op hun melding-ID; een dubbele ID valt hier op."""
    per_id = {rij[sleutel]: rij for rij in rijen}
    assert len(per_id) == len(rijen)
    return per_id


def _uit_csv(veld: str, rij: dict[str, str]) -> object:
    """De waarde van een `Melding`-veld zoals de CSV hem draagt, genormaliseerd."""
    kolommen = CSV_VELD_NAAR_KOLOM[veld]
    if veld == PUNTVELD:
        x, y = (rij[kolom] for kolom in kolommen)
        return None if x == "" else (float(x), float(y))
    (kolom,) = kolommen
    waarde = rij[kolom]
    if veld in BOOLVELDEN:
        # Een lookup en geen `== "True"`: een onverwachte waarde hoort luid te falen in
        # plaats van stilzwijgend als False te lezen.
        return {"True": True, "False": False}[waarde]
    if veld in INTVELDEN:
        return int(waarde)
    if veld == LIJSTVELD:
        return tuple(waarde.split(", ")) if waarde else ()
    return waarde


def _uit_json(veld: str, rij: dict[str, object]) -> object:
    """Dezelfde waarde uit de JSON; daar is de veldnaam de sleutel."""
    waarde = rij[veld]
    if veld == PUNTVELD:
        return None if waarde is None else (waarde[0], waarde[1])
    if veld == LIJSTVELD:
        return tuple(waarde)
    return waarde


def _uit_gpkg(veld: str, rij: dict[str, object]) -> object:
    """Dezelfde waarde uit de meldingentabel van de GeoPackage."""
    kolommen = MELDING_VELD_NAAR_KOLOM[veld]
    if veld == PUNTVELD:
        x, y = (rij[kolom] for kolom in kolommen)
        return None if x is None else (x, y)
    (kolom,) = kolommen
    waarde = rij[kolom]
    if veld in BOOLVELDEN:
        return {1: True, 0: False}[waarde]
    if veld == LIJSTVELD:
        return tuple(waarde.split(", ")) if waarde else ()
    return waarde


def test_de_drie_archieven_dragen_dezelfde_meldingen(archieven: Archieven) -> None:
    """Even veel rijen, dezelfde ID's, en geen kolom die geen veld draagt.

    De twee bestaande drifttests toetsen de kolomlijsten als *constanten*; deze assertie
    kijkt naar wat er werkelijk in de bestanden staat.
    """
    verwacht = {melding.melding_id for melding in archieven.meldingen}

    assert len(verwacht) == len(archieven.meldingen)
    assert len(archieven.csv) == len(archieven.json) == len(archieven.tabel) == len(verwacht)
    assert set(_op_id(archieven.csv, "MeldingID")) == verwacht
    assert set(_op_id(archieven.json, "melding_id")) == verwacht
    assert set(_op_id(archieven.tabel, "melding_id")) == verwacht

    # `Gereedschap` (CSV) en `stapel_aantal`/`stapel_nr` (GeoPackage) dragen geen veld en
    # blijven daarom buiten de join; `fid` haalt `_laagrijen` er al af.
    assert list(archieven.csv[0]) == [*CSV_KOLOMMEN, KOLOM_GEREEDSCHAP]
    assert list(archieven.tabel[0]) == [kolom.naam for kolom in MELDING_KOLOMMEN]


def test_elk_meldingveld_draagt_in_de_drie_archieven_dezelfde_waarde(
    archieven: Archieven,
) -> None:
    """De kern van issue #114: per veld en per melding dezelfde waarde in alle drie.

    De velden komen uit `fields(Melding)` en de kolommen uit de twee afbeeldingen, zodat
    de test met de dataclass meegroeit. `object2_label` heeft in de meldingentabel nooit
    een kolom gehad en staat daar expliciet leeg in de afbeelding; die overslag is de
    enige.
    """
    per_csv = _op_id(archieven.csv, "MeldingID")
    per_json = _op_id(archieven.json, "melding_id")
    per_tabel = _op_id(archieven.tabel, "melding_id")

    for melding_id in per_json:
        for veld in fields(Melding):
            uit_json = _uit_json(veld.name, per_json[melding_id])
            verwacht = uit_json if uit_json is None else pytest.approx(uit_json)
            assert _uit_csv(veld.name, per_csv[melding_id]) == verwacht, (melding_id, veld.name)
            if MELDING_VELD_NAAR_KOLOM[veld.name]:
                assert _uit_gpkg(veld.name, per_tabel[melding_id]) == verwacht, (
                    melding_id,
                    veld.name,
                )


def _vacuum(waarde: object) -> bool:
    """Of dit veld leeg meeloopt: een lege tekst, een lege tuple, None of False."""
    return waarde is None or waarde is False or waarde == "" or waarde == ()


def test_elk_meldingveld_is_op_minstens_een_melding_gevuld(archieven: Archieven) -> None:
    """Zonder deze waakassertie kan een nieuw veld vacuüm meelopen.

    Drie formaten die alle drie niets dragen zijn het per definitie eens; de test
    hierboven zou zo'n veld dan wel aflopen maar niets bewijzen. Met de vier
    invullingen in deze module is de uitzonderingslijst leeg, en die leegte is de eis.
    """
    leeg = [
        veld.name
        for veld in fields(Melding)
        if all(_vacuum(getattr(melding, veld.name)) for melding in archieven.meldingen)
    ]

    assert leeg == []


def _per_object(tabel: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """De meldingentabel gegroepeerd op het hoofdobject.

    Alleen op `gwsw_uri`: `_meldingen_per_object` in `gpkg.py` groepeert op
    `melding.object_uri`, dus een paarmelding telt niet mee op zijn tweede object. Deze
    test volgt dat gedrag; hem hier "corrigeren" zou de samenvatting toetsen tegen een
    andere regel dan de schrijver hanteert.
    """
    per_object: dict[str, list[dict[str, object]]] = defaultdict(list)
    for rij in tabel:
        per_object[rij["gwsw_uri"]].append(rij)
    return per_object


def _objectrijen(archieven: Archieven) -> list[dict[str, object]]:
    """De rijen van `putten` en `strengen` samen."""
    return [rij for laag in OBJECTLAGEN for rij in _laagrijen(archieven.gpkg, laag)]


def test_de_objectlagen_vatten_de_meldingentabel_samen(archieven: Archieven) -> None:
    """Zeven samenvattingskolommen tegen de meldingen in datzelfde bestand.

    Systemische meldingen tellen niet mee in `n_fout`, `n_waarschuwing`, `ergste_ernst`
    en `status` (BO-29/BO-59); in `n_systemisch` en `prioriteit` juist wel. Rijen met
    status `grijs` slaan de statusassertie over: die hangt ook aan `reden`, en die staat
    niet in de meldingentabel.
    """
    per_object = _per_object(archieven.tabel)
    rijen = _objectrijen(archieven)
    assert rijen

    geteld = 0
    for rij in rijen:
        eigen = per_object.get(rij["gwsw_uri"], [])
        geteld += len(eigen)
        los = [melding for melding in eigen if not melding["systemisch"]]
        fouten = [melding for melding in los if melding["ernst"] == "F"]
        waarschuwingen = [melding for melding in los if melding["ernst"] == "W"]

        assert rij["n_fout"] == len(fouten), rij["gwsw_uri"]
        assert rij["n_waarschuwing"] == len(waarschuwingen), rij["gwsw_uri"]
        assert rij["n_systemisch"] == sum(1 for m in eigen if m["systemisch"]), rij["gwsw_uri"]
        assert rij["checks_f"] == ", ".join(sorted({m["check_id"] for m in fouten}))
        assert rij["checks_w"] == ", ".join(sorted({m["check_id"] for m in waarschuwingen}))
        assert rij["ergste_ernst"] == ("F" if fouten else "W" if waarschuwingen else "geen")
        assert rij["prioriteit"] == min((m["prioriteit"] for m in eigen), default=None)
        if rij["status"] != STATUS_GRIJS:
            oranje = STATUS_ORANJE if waarschuwingen else STATUS_GROEN
            assert rij["status"] == (STATUS_ROOD if fouten else oranje), rij["gwsw_uri"]

    # Zonder deze regel zou de lus ook slagen op een bestand waarin geen enkel object een
    # melding draagt.
    assert geteld == sum(1 for rij in archieven.tabel if rij["gwsw_uri"])


def test_de_categoriekolommen_tellen_elke_melding_op_het_object(archieven: Archieven) -> None:
    """`sum(n_top … n_nulmeting)` is het aantal meldingen op het object, systemische erbij.

    `per_categorie` telt ze wel, `n_fout`/`n_waarschuwing` niet. Een melding met een
    categorie buiten `CATEGORIEEN` krijgt geen kolom; die hoort dan ook geen object te
    hebben, anders klopt de som per constructie niet. Op deze fixture is `SIG` de enige
    zo'n categorie.
    """
    buiten = [rij for rij in archieven.tabel if rij["categorie"] not in CATEGORIEEN]
    assert buiten
    assert all(rij["gwsw_uri"] == "" for rij in buiten)

    per_object = _per_object(archieven.tabel)
    for rij in _objectrijen(archieven):
        som = sum(rij[f"n_{naam.lower()}"] for naam in CATEGORIEEN)
        assert som == len(per_object.get(rij["gwsw_uri"], [])), rij["gwsw_uri"]


def test_een_paarmelding_telt_alleen_op_haar_hoofdobject(archieven: Archieven) -> None:
    """De paarmelding zit in de samenvatting van L1 en niet in die van L2 (gemeten).

    Streng L1 draagt vier meldingen: nul fouten, één waarschuwing (de TOP-011-paarmelding)
    en drie systemische. L2 draagt er drie, alle systemisch -- de paarmelding wijst er wel
    naar, maar `_meldingen_per_object` groepeert op het hoofdobject.
    """
    paren = [rij for rij in archieven.tabel if rij["gwsw_uri_2"]]
    assert len(paren) == 1
    paar = paren[0]

    strengen = {rij["gwsw_uri"]: rij for rij in _laagrijen(archieven.gpkg, "strengen")}
    hoofd = strengen[paar["gwsw_uri"]]
    tweede = strengen[paar["gwsw_uri_2"]]

    assert (hoofd["n_fout"], hoofd["n_waarschuwing"], hoofd["n_systemisch"]) == (0, 1, 3)
    assert hoofd["checks_w"] == paar["check_id"]
    assert (tweede["n_fout"], tweede["n_waarschuwing"], tweede["n_systemisch"]) == (0, 0, 3)
    assert tweede["checks_w"] == ""
