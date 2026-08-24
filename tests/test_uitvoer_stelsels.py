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


def test_een_gemeentebrede_bucket_met_putten_krijgt_geen_vlak() -> None:
    """De `_geb_0`-buckets uit #17 dragen naast strengen ook putten en liggen
    gemeentebreed; ze zouden een uitgesmeerde vlek geven en krijgen daarom geen vlak,
    ook al hebben ze strengen.
    """
    dataset = load_dataset(TTL_DIR / "stelsels_registratie.ttl")

    labels = {vlak.label for vlak in lees_stelsels(dataset)}

    assert "hemelwater-bucket" not in labels


def test_stelsel_leden_scheidt_lokale_stelsels_van_buckets() -> None:
    """`stelsel_leden` is de gedeelde regel van de laag en de nulmetingjoin.

    Een lokaal stelsel draagt alleen strengen; een bucket draagt strengen én putten.
    """
    dataset = load_dataset(TTL_DIR / "stelsels_registratie.ttl")

    lokaal = buckets = 0
    for subject in dataset.subjects_of_class("Stelsel"):
        strengen, knopen = dataset.stelsel_leden(str(subject))
        if strengen and not knopen:
            lokaal += 1
        elif strengen and knopen:
            buckets += 1

    assert lokaal == 2  # vuilwater-1 en gemengd-1
    assert buckets == 1  # de hemelwater-bucket met een streng én een put
