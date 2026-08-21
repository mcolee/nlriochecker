"""Tests voor het inlezen van de OroX-dataset."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.dataset import GwswDataset, load_dataset
from nlriochecker.errors import DatasetError

JUINEN = "http://sparql.gwsw.nl/repositories/Juinen#"
NETWERKWORTELS = ["Put", "Gemaal", "Lozingspunt"]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_voorbeeld_levert_strengen_en_knooppunten(juinen: GwswDataset) -> None:
    # Negentien leidingen plus zes onderdeelverbindingen; het GWSW rekent beide
    # tot de verbindingen van het netwerk.
    assert len(juinen.conduits) == 25
    assert len(juinen.of_class("VrijvervalRioolleiding")) == 11
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


def test_koppeling_aan_een_compartiment_zonder_geometrie(juinen: GwswDataset) -> None:
    """Een knooppunt hoeft geen puntgeometrie te hebben om een knoop te zijn.

    Leiding "5" koppelt aan twee compartimenten waarvan de orientatie geen Punt
    draagt. Wie knopen aan hun geometrie herkent, mist die koppeling.
    """
    streng = juinen.conduits[f"{JUINEN}GemengdRiool_98"]

    assert streng.start_node == f"{JUINEN}Compartiment_42"
    assert streng.end_node == f"{JUINEN}Compartiment_60"
    assert juinen.nodes[streng.start_node].point is None


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


def test_hasconnection_is_symmetrisch(tmp_path: Path) -> None:
    """gwsw:hasConnection is een owl:SymmetricProperty en heeft geen inverse.

    Een export die de tripel omgekeerd schrijft is even geldig; de lader moet
    beide richtingen herkennen.
    """
    bron = (Path(__file__).parent / "fixtures" / "ttl" / "schoon.ttl").read_text(encoding="utf-8")
    omgekeerd = bron.replace(
        ":L1_b gwsw:hasConnection :PutA_ori .", ":PutA_ori gwsw:hasConnection :L1_b ."
    )
    assert omgekeerd != bron, "de fixture bevat de verwachte koppeling niet"
    pad = tmp_path / "omgekeerd.ttl"
    pad.write_text(omgekeerd, encoding="utf-8")

    dataset = load_dataset(pad)
    streng = next(iter(dataset.conduits.values()))

    assert streng.start_node is not None
    assert streng.start_node.endswith("PutA")


def test_orientatietypen_zijn_selecteerbaar(tmp_path: Path) -> None:
    """Knooppunt-klassen als Lozingspunt staan op de orientatie, niet op het object."""
    bron = (Path(__file__).parent / "fixtures" / "ttl" / "schoon.ttl").read_text(encoding="utf-8")
    bron += "\n:PutB_ori rdf:type gwsw:Lozingspunt .\n"
    pad = tmp_path / "lozingspunt.ttl"
    pad.write_text(bron, encoding="utf-8")

    dataset = load_dataset(pad)
    lozingspunten = dataset.of_class("Lozingspunt")

    assert [uri.rsplit("#", 1)[-1] for uri in lozingspunten] == ["PutB"]


def test_onderdeel_uit_de_graaf_is_op_klasse_te_herkennen() -> None:
    """Een overstortdrempel hangt via hasPart aan de put en wordt nooit een knoop.

    `types_of()` kent alleen knopen en strengen en geeft er dus niets op terug;
    `graph_types_of()` leest het type uit de graaf en maakt de klasse toetsbaar.
    """
    dataset = load_dataset(TTL_DIR / "adm007_overstort_met_drempel.ttl")
    drempel = next(str(s) for s in dataset.subjects_of_class("Overstortdrempel"))

    assert dataset.types_of(drempel) == frozenset()
    assert not dataset.is_a(drempel, "Overstortdrempel")
    assert dataset.graph_is_a(drempel, "Overstortdrempel")


def test_of_class_weigert_een_verbindingsklasse() -> None:
    """Een verbindingsklasse als rol levert stil nul op; dat hoort een fout te zijn."""
    dataset = load_dataset(TTL_DIR / "schoon.ttl")

    with pytest.raises(DatasetError, match="verbindingsklasse"):
        dataset.of_class("Leidingorientatie")


def test_verschil_met_de_structurele_herkenning_wordt_gemeld(juinen: GwswDataset) -> None:
    """Zonder ontologie zou de lader knopen aan hun geometrie herkennen.

    Dat wijkt af van de GWSW-definitie: vijf compartimenten zijn wel knooppunt maar
    hebben geen punt, en een putdeksel en een ontluchter hebben wel een punt maar
    zijn geen knooppunt. Dat verschil hoort meetbaar te zijn.
    """
    assert juinen.structural_diff == {
        "knooppunten_zonder_geometrie": 5,
        "knooppunten_wel_geometrie_geen_rol": 2,
    }


def test_ontologie_wordt_vastgelegd(juinen: GwswDataset) -> None:
    assert [pad.name for pad in juinen.ontologies] == ["Ontologie_GWSW_Totaal.ttl"]


def test_beheerobjecttype_negeert_de_orientatie() -> None:
    """De soortnaam van een object is zijn eigen type, niet dat van zijn aspect.

    Deze regel wordt zowel door de netwerktoelichting als door de GIS-uitvoer
    gebruikt; hij hoort op een plek te staan, anders loopt hij bij de volgende
    wijziging uiteen.
    """
    dataset = load_dataset(
        Path(__file__).parent / "fixtures" / "ttl" / "net001_bouwwerk_eindknoop.ttl"
    )
    uri = next(uri for uri, node in dataset.nodes.items() if node.label == "U")

    assert "Bouwwerkorientatie" in {t.rsplit("/", 1)[-1] for t in dataset.types_of(uri)}
    assert dataset.beheerobjecttype(uri) == "Uitlaatconstructie"


def test_beheerobjecttype_valt_terug_op_het_aspect() -> None:
    """Is er niets anders bekend, dan is het aspecttype beter dan niets."""
    dataset = load_dataset(
        Path(__file__).parent / "fixtures" / "ttl" / "net001_bouwwerk_eindknoop.ttl"
    )

    assert dataset.beheerobjecttype("urn:bestaat-niet") == ""


def test_bob_verval_is_het_verschil_over_de_streng(juinen) -> None:
    conduit = next(c for c in juinen.conduits.values() if c.bob_start and c.bob_end)

    assert conduit.bob_verval == pytest.approx(conduit.bob_start - conduit.bob_end)


def test_bob_verval_ontbreekt_zonder_beide_bobs(juinen) -> None:
    conduit = next(
        (c for c in juinen.conduits.values() if c.bob_start is None or c.bob_end is None),
        None,
    )
    if conduit is None:
        pytest.skip("elke streng in het voorbeeld draagt beide BOB's")

    assert conduit.bob_verval is None


def test_richting_van_geometrie_ziet_een_omgekeerd_getekende_lijn() -> None:
    from nlriochecker.checkconfig import load_check_config

    dataset = load_dataset(TTL_DIR / "top020_omgekeerd_getekend.ttl")
    wortels = load_check_config().klassen.netwerkknopen
    conduit = next(iter(dataset.conduits.values()))

    uitslag = dataset.richting_van_geometrie(conduit, wortels)

    assert uitslag is not None
    omgekeerd, begin, eind = uitslag
    assert omgekeerd is True
    assert begin.uri != eind.uri
