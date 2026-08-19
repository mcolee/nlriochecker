"""Tests voor de omzetting van SHACL-nulmetingovertredingen naar bevindingen."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.dataset import GwswDataset, load_dataset
from nlriochecker.meting import laad_nulmeting
from nlriochecker.nulbevinding import Nulbevinding, bouw_nulbevindingen

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"
CFKS = ["MdsPlan", "MdsProj"]
DREMPEL = 0.80


@pytest.fixture
def joinset() -> GwswDataset:
    """De dataset waarop de focusnodes van de join-fixtures uitkomen."""
    return load_dataset(TTL_DIR / "nulmeting_join.ttl")


@pytest.fixture
def bevindingen(joinset: GwswDataset) -> list[Nulbevinding]:
    """De nulbevindingen van de twee join-rapporten samen."""
    nulmeting = laad_nulmeting(
        [SHACL_DIR / "join_mdsplan.csv", SHACL_DIR / "join_mdsproj.csv"], CFKS
    )
    return bouw_nulbevindingen(nulmeting, joinset, DREMPEL)


def _een(bevindingen: list[Nulbevinding], vorm: str, focus: str) -> Nulbevinding:
    """De enige bevinding van deze vorm op deze focusnode."""
    gevonden = [b for b in bevindingen if b.vorm == vorm and b.focus_node == focus]
    assert len(gevonden) == 1, f"{vorm} op {focus}: {len(gevonden)} bevindingen"
    return gevonden[0]


def test_check_id_draagt_de_vormnaam(bevindingen: list[Nulbevinding]) -> None:
    """Het check-ID is afgeleid van de SHACL-vorm, met een vast voorvoegsel."""
    assert _een(bevindingen, "Put_HoogtePut_card", "PutA").check_id == (
        "NULMETING-Put_HoogtePut_card"
    )


def test_focusnode_op_een_knoop_joint_direct(
    bevindingen: list[Nulbevinding], joinset: GwswDataset
) -> None:
    """Een focusnode die de fragmentnaam van een knoop is, wijst die knoop aan."""
    bevinding = _een(bevindingen, "Put_HoogtePut_card", "PutA")

    assert bevinding.object_uri in joinset.nodes
    assert bevinding.object_label == "A"
    assert bevinding.herleid


def test_focusnode_op_een_eindpunt_herleidt_naar_de_streng(
    bevindingen: list[Nulbevinding], joinset: GwswDataset
) -> None:
    """Een BeginpuntLeiding hangt via hasPart en hasAspect onder zijn streng.

    Zonder die stap raakt geen enkele kardinaliteitsfout op een leidingeinde ooit
    de kaart, terwijl hij wel over een bestaande streng gaat.
    """
    bevinding = _een(bevindingen, "BeginpuntLeiding_Knooppunt_card", "L1_b")

    assert bevinding.object_uri in joinset.conduits
    assert bevinding.herleid


def test_focusnode_zonder_object_blijft_onherleid(bevindingen: list[Nulbevinding]) -> None:
    """Een stelsel of klassenaam komt nergens op uit; de melding blijft wel bestaan."""
    stelsel = _een(bevindingen, "Vuilwaterstelsel_Lozingspunt_card", "vw_geb_1")
    klasse = _een(bevindingen, "CfkTypes_typ", "Rioolstelsel")

    assert not stelsel.herleid and stelsel.object_uri == ""
    assert not klasse.herleid and klasse.object_uri == ""


def test_label_valt_terug_op_dat_van_het_rapport(bevindingen: list[Nulbevinding]) -> None:
    """Zonder object in de dataset draagt het rapport zelf nog een label."""
    assert _een(bevindingen, "Vuilwaterstelsel_Lozingspunt_card", "vw_geb_1").object_label == (
        "1_vw"
    )


def test_dezelfde_overtreding_in_twee_cfks_geeft_een_bevinding(
    bevindingen: list[Nulbevinding],
) -> None:
    """Ontdubbeld op focusnode, vorm en boodschap; de CFK's staan er alle bij."""
    assert _een(bevindingen, "Put_HoogtePut_card", "PutA").cfk == ("MdsPlan", "MdsProj")


def test_een_overtreding_uit_een_enkele_cfk_noemt_alleen_die(
    bevindingen: list[Nulbevinding],
) -> None:
    """Wat maar in een rapport staat, hoort ook maar een conformiteitsklasse te noemen."""
    assert _een(bevindingen, "LengteLeiding_val", "L1_e").cfk == ("MdsProj",)


def test_violation_wordt_f_en_warning_wordt_w(bevindingen: list[Nulbevinding]) -> None:
    """De ernst komt uit de kolom Severity, zoals het checkregister voorschrijft."""
    assert _een(bevindingen, "Put_HoogtePut_card", "PutA").ernst == "F"
    assert _een(bevindingen, "LengteLeiding_val", "L1_e").ernst == "W"


def test_de_waarde_komt_uit_de_kolom_value(bevindingen: list[Nulbevinding]) -> None:
    """De aangetroffen waarde staat in de meldingkolom Value."""
    assert _een(bevindingen, "LengteLeiding_val", "L1_e").waarde == "164.200 (decimal)"


def test_systemisch_boven_de_drempel_per_vorm_en_objecttype(
    bevindingen: list[Nulbevinding],
) -> None:
    """Alle drie de inspectieputten missen hun hoogte: dat zegt iets over de export."""
    assert _een(bevindingen, "Put_HoogtePut_card", "PutA").systemisch


def test_objecttype_zonder_instanties_is_nooit_systemisch(
    bevindingen: list[Nulbevinding],
) -> None:
    """BeginpuntLeiding is geen knoop of streng; er is dus geen noemer.

    Een melding ten onrechte systemisch noemen haalt hem van de kaart; zonder
    noemer valt de vlag daarom naar de veilige kant.
    """
    assert not _een(bevindingen, "BeginpuntLeiding_Knooppunt_card", "L1_b").systemisch


def test_een_hogere_drempel_maakt_dezelfde_bevinding_niet_systemisch(
    joinset: GwswDataset,
) -> None:
    """De drempel komt uit de projectconfiguratie en staat nergens in de code."""
    nulmeting = laad_nulmeting(
        [SHACL_DIR / "join_mdsplan.csv", SHACL_DIR / "join_mdsproj.csv"], CFKS
    )

    streng = bouw_nulbevindingen(nulmeting, joinset, 1.0)

    assert not _een(streng, "Put_HoogtePut_card", "PutA").systemisch


def test_de_bevindingen_staan_in_een_vaste_volgorde(bevindingen: list[Nulbevinding]) -> None:
    """Twee runs op dezelfde bestanden leveren dezelfde volgorde op."""
    sleutels = [(b.vorm, b.focus_node, b.boodschap) for b in bevindingen]

    assert sleutels == sorted(sleutels)


def test_maaiveldorientatie_herleidt_via_hasconnection(
    bevindingen: list[Nulbevinding], joinset: GwswDataset
) -> None:
    """De maaiveldorientatie hangt via hasConnection onder de putorientatie.

    Op De Wolden zijn dat 1.605 overtredingen die anders geen put zouden vinden,
    terwijl ze wel over het maaiveld van een bestaande put gaan.
    """
    bevinding = _een(bevindingen, "Maaiveldorientatie_Putorientatie_card", "PutC_ori_maa")

    assert bevinding.object_uri in joinset.nodes
    assert bevinding.object_label == "C"


def test_een_leidingeinde_herleidt_naar_zijn_streng_en_niet_naar_de_put(
    bevindingen: list[Nulbevinding], joinset: GwswDataset
) -> None:
    """hasConnection wordt pas als laatste geprobeerd, en alleen als eerste stap.

    Een BeginpuntLeiding heeft zowel een hasPart-houder (zijn leidingorientatie) als
    een hasConnection naar de putorientatie. Zou de verbinding voorgaan, dan zou de
    melding op de verkeerde soort object landen.
    """
    bevinding = _een(bevindingen, "BeginpuntLeiding_Knooppunt_card", "L1_b")

    assert bevinding.object_uri in joinset.conduits


def test_hasconnection_wordt_in_beide_schrijfrichtingen_gelezen(
    bevindingen: list[Nulbevinding], joinset: GwswDataset
) -> None:
    """`hasConnection` is symmetrisch en zonder inverse.

    Welke van de twee objecten subject is, is een keuze van de exporteur. Alleen de
    ene richting lezen zou op een andere export stil meldingen van de kaart laten
    vallen.
    """
    bevinding = _een(bevindingen, "Maaiveldorientatie_Putorientatie_card", "PutD_ori_maa")

    assert bevinding.object_uri in joinset.nodes
    assert bevinding.object_label == "D"
