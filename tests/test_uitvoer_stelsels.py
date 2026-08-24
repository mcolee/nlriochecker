"""Tests voor het lezen van de geregistreerde stelselboom (#17, #25).

De boom `Stelsel -> hasPart -> strengen` staat in de OroX-export en werd tot #25
nergens gelezen. `lees_stelsels` leest hem uit de graaf; de cartografische laag
`stelsels` in de GeoPackage bouwt erop voort.
"""

from __future__ import annotations

from pathlib import Path

from nlriochecker.dataset import load_dataset
from nlriochecker.uitvoer.stelsels import lees_stelsels

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_lees_stelsels_geeft_de_geregistreerde_stelsels_met_hun_strengen() -> None:
    dataset = load_dataset(TTL_DIR / "stelsels_registratie.ttl")

    vlakken = {vlak.label: vlak for vlak in lees_stelsels(dataset)}

    assert set(vlakken) == {"vuilwater-1", "gemengd-1"}
    assert vlakken["vuilwater-1"].stelseltype == "Vuilwaterstelsel"
    assert len(vlakken["vuilwater-1"].strengen) == 2
    assert vlakken["gemengd-1"].stelseltype == "GemengdStelsel"
    assert len(vlakken["gemengd-1"].strengen) == 1


def test_een_stelsel_zonder_strengen_krijgt_geen_vlak() -> None:
    """De gemeentebrede put-buckets uit #17 bevatten alleen putten, geen strengen.

    Een vlak baseert zich op de strengen, dus zo'n bucket levert geen vlak op.
    """
    dataset = load_dataset(TTL_DIR / "stelsels_registratie.ttl")

    labels = {vlak.label for vlak in lees_stelsels(dataset)}

    assert "hemelwater-bucket" not in labels
