"""Tests voor het inlezen van de OroX-dataset."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.dataset import GwswDataset, load_dataset
from gwswpijplijn.errors import DatasetError

JUINEN = "http://sparql.gwsw.nl/repositories/Juinen#"
NETWERKWORTELS = ["Put", "Gemaal", "Lozingspunt"]


def test_voorbeeld_levert_strengen_en_knooppunten(juinen: GwswDataset) -> None:
    # Het meegeleverde voorbeeld bevat negentien leidingen.
    assert len(juinen.conduits) == 19
    assert len(juinen.of_class("Put")) == 10
    assert juinen.of_class("Gemaal") == [f"{JUINEN}Rioolgemaal_3"]


def test_koppeling_loopt_via_de_putorientatie(juinen: GwswDataset) -> None:
    streng = juinen.conduits[f"{JUINEN}GemengdRiool_93"]

    assert streng.label == "4"
    assert streng.start_node == f"{JUINEN}Inspectieput_17"
    assert streng.end_node == f"{JUINEN}Inspectieput_20"
    assert streng.bob_start == 22.45
    assert streng.line is not None


def test_meervoudig_rdf_type(juinen: GwswDataset) -> None:
    put = juinen.nodes[f"{JUINEN}Inspectieput_17"]

    # De put is zowel Inspectieput als VerdektePut.
    assert "http://data.gwsw.nl/1.6/totaal/Inspectieput" in put.types
    assert "http://data.gwsw.nl/1.6/totaal/VerdektePut" in put.types


def test_klassenhierarchie_uit_de_ontologie(juinen: GwswDataset) -> None:
    assert juinen.is_a(f"{JUINEN}GemengdRiool_93", "VrijvervalRioolleiding")
    assert juinen.is_a(f"{JUINEN}Inspectieput_17", "Put")
    assert not juinen.is_a(f"{JUINEN}GemengdRiool_93", "Put")


def test_koppeling_aan_compartiment_wordt_naar_de_put_herleid(juinen: GwswDataset) -> None:
    # Leiding "6" koppelt aan compartimenten, niet aan de putten zelf.
    streng = juinen.conduits[f"{JUINEN}GemengdRiool_103"]

    assert streng.start_node == f"{JUINEN}Compartiment_25"
    assert juinen.resolve_network_node(streng.start_node, NETWERKWORTELS) == (
        f"{JUINEN}Inspectieput_20"
    )


def test_ontbrekende_koppeling_blijft_leeg(juinen: GwswDataset) -> None:
    # Leiding "5" heeft geen hasConnection op haar eindpunten.
    streng = juinen.conduits[f"{JUINEN}GemengdRiool_98"]

    assert streng.start_node is None
    assert streng.end_node is None


def test_onleesbaar_bestand_geeft_dataseterror(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="kan niet gelezen worden"):
        load_dataset(tmp_path / "bestaat_niet.ttl")


def test_ongeldige_turtle_geeft_dataseterror(tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.ttl"
    stuk.write_text("dit is <geen geldige turtle", encoding="utf-8")

    with pytest.raises(DatasetError, match="geldige Turtle"):
        load_dataset(stuk)


def test_dataset_zonder_objecten_geeft_dataseterror(tmp_path: Path) -> None:
    leeg = tmp_path / "leeg.ttl"
    leeg.write_text("@prefix ex: <http://example.org/> .\nex:a ex:b ex:c .\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="geen knooppunten of strengen"):
        load_dataset(leeg)
