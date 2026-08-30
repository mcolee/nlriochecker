"""Waardegelijkheid tussen de drie archieven, en de objectlagen tegen de meldingentabel.

De harde regel "één uitvoerschrijver" wordt bewaakt door een sweep die een tweede
schrijver in `src/` verbiedt, en door twee drifttests die kolom*namen* vergelijken
(`tests/test_uitvoer_herkomst.py`). Geen van drieën kijkt naar de geschreven *waarden*:
verwissel twee entries in `CSV_VELD_NAAR_KOLOM`, of laat `_melding_rij` het objectlabel
in de kolom `boodschap` zetten, en ze blijven alle drie groen. SQLite is zwak getypeerd
en de CSV is tekst, dus zo'n verwisseling leest als een geldige waarde.

Deze module dicht dat gat op drie plekken (issue #114):

1. per melding draagt elk veld van `Melding` in CSV, JSON en GeoPackage dezelfde waarde
   -- met precies de normalisaties die de drie formaten nu eenmaal verschillen (bool als
   tekst/`true`/`1`, een punt als X/Y-paar of lijst, `cfk` als tekst of lijst);
2. de samenvattingskolommen van `putten` en `strengen` kloppen met de meldingentabel in
   datzelfde bestand;
3. elke categoriekolom telt de meldingen van haar eigen categorie op het object.

**De meldingenstroom is het orakel, niet één van de drie archieven.** Zou de JSON de maat
zijn, dan blijven drie schrijvers groen die alle drie hetzelfde verkeerde antwoord geven
-- een leeg `gebied` bij een stroom die er wel een draagt. Elke schrijver wordt daarom
apart tegen `Melding` gehouden en apart bij naam genoemd als hij afwijkt.

Het Markdown-rapport valt hier bewust buiten: dat is een view die samenvat en weglaat
(systemische bevindingen, `max_bevindingen_per_check`) en draagt dus per definitie niet
dezelfde rijen. Deze module gaat over de drie *archieven*.

Er wordt niets in `src/` beweerd dat er niet al staat: slaat een assertie aan, dan staat
er een echte verwisseling in de uitvoer.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, fields, replace
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import Point

from helpers_melding import nulbevinding
from nlriochecker.checks import CheckRun
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

# Een coördinaat met méér cijfers dan de fixture zelf oplevert (die is rond: 1000.0,
# 2000.0). Zonder zo'n waarde blijft een afronding in één schrijver -- een `round(x, 1)`
# in `meldingen_json`, een `float_format` op de CSV -- onzichtbaar, want alle drie de
# formaten schrijven een rond getal rond weg.
ONRONDE_LOCATIE = Point(1023.4567890123, 1987.6543210987)

# Waarmee de coördinaten vergeleken worden. Absoluut en scherp: `pytest.approx` staat
# standaard op rel=1e-6, en dat is op echte RD-coördinaten (x ~200.000, y ~500.000) een
# halve meter -- ruim genoeg om een afronding door te laten.
LOCATIE_TOLERANTIE = 1e-9


@dataclass(frozen=True)
class Archieven:
    """Eén `schrijf_uitvoer`, teruggelezen uit de drie bestanden die zij opleverde."""

    meldingen: list[Melding]
    csv: list[dict[str, str]]
    json: list[dict[str, object]]
    tabel: list[dict[str, object]]
    gpkg: Path


def _run_met_nulbevinding() -> CheckRun:
    """De fixture door alle checks, met één nulmetingbevinding erbij.

    Zij vult `cfk` en `boodschap_technisch`, die een TTL-fixture niet kan leveren; een
    leeg veld wordt vacuüm vergeleken, want drie formaten die alle drie niets dragen zijn
    het per definitie eens. De `leesbaar` verschilt van `boodschap`, anders zou een
    verwisseling van `boodschap` en `boodschap_technisch` twee gelijke teksten ruilen.
    De overige velden komen uit de gedeelde bouwer en wijzen al naar `PutA`.
    """
    run = _run(FIXTURE)
    bevinding = nulbevinding(
        boodschap="sh:minCount 1 op gwsw:HoogtePut",
        waarde="0 voorkomens",
        leesbaar="De put draagt geen hoogte.",
    )
    return replace(run, nulbevindingen=(bevinding,))


def _stroom_met_alle_velden(run: CheckRun) -> Meldingenstroom:
    """De meldingenstroom, met `drempel`, `gebied` en een onronde plek op één melding.

    De eerste twee zijn uit deze fixture niet te krijgen: `drempel` vullen alleen EXT-001
    en EXT-009 (die externe bronnen vragen) en `gebied` vraagt een studiegebied. De derde
    is er omdat de fixturecoördinaten rond zijn en een afronding in één schrijver daarop
    onzichtbaar blijft. De keuze valt op een registermelding zónder tweede object, zodat
    de paarmelding ongemoeid blijft. Kunstmatig, en dat mag: het doel is kolomvulling,
    niet realisme.
    """
    stroom = bouw_meldingenstroom(run, RUNDATUM)
    meldingen = list(stroom.meldingen)
    doel = next(
        nummer
        for nummer, melding in enumerate(meldingen)
        if melding.bron == "register" and not melding.object2_uri
    )
    meldingen[doel] = replace(
        meldingen[doel], drempel="0.10", gebied="Testgebied", foutlocatie=ONRONDE_LOCATIE
    )
    return Meldingenstroom(meldingen, stroom.onderdrukking, stroom.feiten)


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


def _uit_melding(veld: str, melding: Melding) -> object:
    """De waarde van een veld op de melding zelf, in dezelfde vorm als de drie lezers.

    Dit is het orakel: de stroom die `schrijf_uitvoer` aan alle drie de schrijvers gaf.
    Zou een van de archieven de maat zijn, dan blijven drie schrijvers die samen
    hetzelfde verkeerde antwoord geven onopgemerkt.
    """
    waarde = getattr(melding, veld)
    if veld == PUNTVELD:
        return None if waarde is None else (waarde.x, waarde.y)
    return waarde


def _uit_csv(veld: str, rij: dict[str, str]) -> object:
    """De waarde van een `Melding`-veld zoals de CSV hem draagt, genormaliseerd."""
    kolommen = CSV_VELD_NAAR_KOLOM[veld]
    if veld == PUNTVELD:
        x, y = (rij[kolom] for kolom in kolommen)
        # De schrijver vult X en Y los (`bevindingen.meldingen_tabel`); alleen naar X
        # kijken zou een half geschreven coördinaat als "geen locatie" laten passeren.
        assert (x == "") == (y == ""), (veld, x, y)
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
        # Idem: `_melding_rij` vult x en y als twee losse posities in de tuple.
        assert (x is None) == (y is None), (veld, x, y)
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
    """De kern van issue #114: elk veld van elke melding komt ongeschonden in alle drie.

    De lus loopt over de **stroom** en niet over een van de bestanden: die stroom is wat
    `schrijf_uitvoer` aan de drie schrijvers gaf, en dus het enige orakel dat drie
    schrijvers met hetzelfde verkeerde antwoord kan betrappen. Elke schrijver wordt apart
    vergeleken en apart bij naam genoemd.

    De velden komen uit `fields(Melding)` en de kolommen uit de twee afbeeldingen, zodat
    de test met de dataclass meegroeit. `object2_label` heeft in de meldingentabel nooit
    een kolom gehad en staat daar expliciet leeg in de afbeelding; die overslag is de
    enige. `pytest.approx` staat alleen op de coördinaten en met een absolute tolerantie:
    op de andere velden zou hij de vergelijking nodeloos oprekken.
    """
    per_csv = _op_id(archieven.csv, "MeldingID")
    per_json = _op_id(archieven.json, "melding_id")
    per_tabel = _op_id(archieven.tabel, "melding_id")

    for melding in archieven.meldingen:
        sleutel = melding.melding_id
        for veld in fields(Melding):
            uit_stroom = _uit_melding(veld.name, melding)
            verwacht = (
                pytest.approx(uit_stroom, abs=LOCATIE_TOLERANTIE)
                if veld.name == PUNTVELD and uit_stroom is not None
                else uit_stroom
            )
            assert _uit_csv(veld.name, per_csv[sleutel]) == verwacht, ("csv", sleutel, veld.name)
            assert _uit_json(veld.name, per_json[sleutel]) == verwacht, ("json", sleutel, veld.name)
            if MELDING_VELD_NAAR_KOLOM[veld.name]:
                assert _uit_gpkg(veld.name, per_tabel[sleutel]) == verwacht, (
                    "geopackage",
                    sleutel,
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
    """Acht samenvattingskolommen tegen de meldingen in datzelfde bestand.

    Systemische meldingen tellen niet mee in `n_fout`, `n_waarschuwing`, `ergste_ernst`
    en `status` (BO-29/BO-59); in `n_systemisch` en `prioriteit` juist wel.

    Een grijze rij krijgt de andere helft van dezelfde regel: `bepaal_status` geeft alleen
    grijs als er geen enkele niet-systemische melding op het object staat -- "grijs wint
    niet van een gebrek". De reden waaróm hij grijs is staat niet in de meldingentabel, dus
    die kant valt hier buiten; dat er dan niets gevonden is, staat er wel.
    """
    per_object = _per_object(archieven.tabel)
    rijen = _objectrijen(archieven)
    assert rijen
    # Zonder deze regel zou de statusassertie hieronder vacuüm worden op een bestand
    # waarin elke rij grijs is.
    assert any(rij["status"] != STATUS_GRIJS for rij in rijen)

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
        else:
            assert not los, rij["gwsw_uri"]

    # Zonder deze regel zou de lus ook slagen op een bestand waarin geen enkel object een
    # melding draagt. Alleen over de meldingen die een objectrij hébben: `_schrijf_features`
    # slaat een object zonder geometrie over, en een melding op een stelsel of op een
    # hasPart-onderdeel krijgt sowieso geen rij (BO-12).
    met_rij = {rij["gwsw_uri"] for rij in rijen}
    assert geteld == sum(1 for rij in archieven.tabel if rij["gwsw_uri"] in met_rij)
    assert geteld
    # En op deze fixture is die verzameling toevallig alles: elke melding met een object
    # landt ook op een objectrij. Apart geasserteerd, zodat de regel hierboven niet stil
    # meldingen wegfiltert zodra dat verandert.
    assert [rij["melding_id"] for rij in archieven.tabel if rij["gwsw_uri"] not in met_rij] == [
        rij["melding_id"] for rij in archieven.tabel if not rij["gwsw_uri"]
    ]


def test_de_categoriekolommen_tellen_elke_melding_op_het_object(archieven: Archieven) -> None:
    """Elke `n_<categorie>` telt haar eigen categorie, en samen tellen ze alles.

    Per kolom en niet alleen hun som: de som blijft kloppen als twee categoriekolommen
    verwisseld zijn, en dat is precies de faalwijze waar dit issue over gaat. Systemische
    meldingen tellen hier wél mee -- `per_categorie` telt ze, `n_fout`/`n_waarschuwing`
    niet.

    Een melding met een categorie buiten `CATEGORIEEN` krijgt geen kolom; die hoort dan
    ook geen object te hebben, anders klopt de som per constructie niet. Op deze fixture
    is `SIG` de enige zo'n categorie.
    """
    buiten = [rij for rij in archieven.tabel if rij["categorie"] not in CATEGORIEEN]
    assert buiten
    assert all(rij["gwsw_uri"] == "" for rij in buiten)

    per_object = _per_object(archieven.tabel)
    for rij in _objectrijen(archieven):
        eigen = per_object.get(rij["gwsw_uri"], [])
        telling = Counter(melding["categorie"] for melding in eigen)
        for naam in CATEGORIEEN:
            assert rij[f"n_{naam.lower()}"] == telling[naam], (rij["gwsw_uri"], naam)
        assert sum(rij[f"n_{naam.lower()}"] for naam in CATEGORIEEN) == len(eigen)


def test_een_paarmelding_telt_alleen_op_haar_hoofdobject(archieven: Archieven) -> None:
    """`_meldingen_per_object` groepeert op `object_uri`; het tweede object telt niet mee.

    Alleen de relationele eigenschap, geen absolute fixturetellingen: hoeveel meldingen L1
    en L2 dragen bewijst `test_de_objectlagen_vatten_de_meldingentabel_samen` al per rij,
    en het hier nog eens vastpinnen breekt zodra de fixturegenerator iets verschuift.
    """
    paren = [rij for rij in archieven.tabel if rij["gwsw_uri_2"] and not rij["systemisch"]]
    assert paren

    strengen = {rij["gwsw_uri"]: rij for rij in _laagrijen(archieven.gpkg, "strengen")}
    for paar in paren:
        kolom = "checks_f" if paar["ernst"] == "F" else "checks_w"
        hoofd = strengen[paar["gwsw_uri"]]
        tweede = strengen[paar["gwsw_uri_2"]]
        # De voorwaarde die de regel eronder pas iets laat bewijzen: droeg het tweede
        # object deze check zelf ook, dan zou zijn kolom hem terecht noemen.
        assert paar["check_id"] not in {
            rij["check_id"]
            for rij in archieven.tabel
            if rij["gwsw_uri"] == paar["gwsw_uri_2"] and not rij["systemisch"]
        }

        assert paar["check_id"] in hoofd[kolom].split(", "), paar["melding_id"]
        assert paar["check_id"] not in tweede[kolom].split(", "), paar["melding_id"]
