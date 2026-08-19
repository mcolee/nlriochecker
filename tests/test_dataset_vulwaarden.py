"""De vulwaarde-leesregel: 0,000 in een hoogtekenmerk is geen meting (issue #1)."""

from __future__ import annotations

from pathlib import Path

from nlriochecker.dataset import GwswDataset, Vulwaarde, load_dataset, markeer_vulwaarden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
KENMERKEN = ["BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte", "Putdekselniveau"]


def _dataset() -> GwswDataset:
    """De fixture met een vulwaarde in het maaiveld en in een BOB."""
    return load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl")


def test_markeren_zet_de_vulwaarde_op_none_en_onthoudt_haar() -> None:
    dataset = markeer_vulwaarden(_dataset(), KENMERKEN, 0.01)
    put = next(node for node in dataset.nodes.values() if node.label == "A")
    streng = next(conduit for conduit in dataset.conduits.values() if conduit.label == "1")

    assert put.maaiveld is None
    assert put.vulwaarden == (Vulwaarde("Maaiveldhoogte", 0.0),)
    assert streng.bob_start is None
    assert streng.bob_end == 8.55
    assert streng.vulwaarden == (Vulwaarde("BobBeginpuntLeiding", 0.0),)


def test_ruwe_dataset_blijft_onaangeraakt() -> None:
    ruw = _dataset()
    markeer_vulwaarden(ruw, KENMERKEN, 0.01)
    put = next(node for node in ruw.nodes.values() if node.label == "A")

    assert put.maaiveld == 0.0
    assert put.vulwaarden == ()


def test_lege_kenmerkenlijst_is_de_identiteit() -> None:
    ruw = _dataset()

    assert markeer_vulwaarden(ruw, [], 0.01) is ruw


def test_band_nul_markeert_alleen_exact_nul() -> None:
    dataset = markeer_vulwaarden(_dataset(), KENMERKEN, 0.0)
    put_b = next(node for node in dataset.nodes.values() if node.label == "B")

    # Put B heeft maaiveld 0,01: binnen band 0,01, buiten band 0,0.
    assert put_b.maaiveld == 0.01
    assert put_b.vulwaarden == ()


def test_een_kenmerk_buiten_de_lijst_blijft_staan() -> None:
    """Alleen de gekozen kenmerken doen mee; de rest houdt zijn waarde."""
    dataset = markeer_vulwaarden(_dataset(), ["Putdekselniveau"], 0.01)
    put = next(node for node in dataset.nodes.values() if node.label == "A")

    assert put.maaiveld == 0.0
    assert put.vulwaarden == ()
