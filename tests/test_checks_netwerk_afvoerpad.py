"""Tests voor de afvoerpadanalyse (#18, fase 1)."""

from __future__ import annotations

from pathlib import Path

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.netwerk import afvoerpad_van_streng, afvoerpaden
from nlriochecker.dataset import GwswDataset, load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def _context(bestand: str) -> CheckContext:
    """Bouwt een context op een netwerkfixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    return CheckContext(dataset=dataset, config=load_check_config())


def _uri(dataset: GwswDataset, label: str) -> str:
    """De URI van de knoop met dit label."""
    return next(uri for uri, node in dataset.nodes.items() if node.label == label)


def _streng(dataset: GwswDataset, label: str):
    """De streng met dit label."""
    return next(streng for streng in dataset.conduits.values() if streng.label == label)


def test_keten_geeft_elke_knoop_hetzelfde_eindpunt_met_aflopende_stappen() -> None:
    context = _context("net_afvoerpad_keten.ttl")
    dataset = context.dataset
    gemaal = _uri(dataset, "G")

    paden = afvoerpaden(context)

    # Elke knoop bereikt het gemaal; de stappen lopen af naar het gemaal toe.
    assert paden[_uri(dataset, "A")].eindpunt == gemaal
    assert paden[_uri(dataset, "A")].stappen == 3
    assert paden[_uri(dataset, "B")].stappen == 2
    assert paden[_uri(dataset, "C")].stappen == 1
    assert paden[gemaal].stappen == 0
    # 50 m per streng, dus 150 m vanaf A en 0 m op het gemaal zelf.
    assert paden[_uri(dataset, "A")].meters == 150.0
    assert paden[gemaal].meters == 0.0


def test_keten_geeft_elke_streng_hetzelfde_eindpunt_met_aflopende_stappen() -> None:
    context = _context("net_afvoerpad_keten.ttl")
    dataset = context.dataset
    gemaal = _uri(dataset, "G")

    per_streng = {
        label: afvoerpad_van_streng(context, _streng(dataset, label)) for label in ("1", "2", "3")
    }

    assert {label: pad.eindpunt for label, pad in per_streng.items()} == {
        "1": gemaal,
        "2": gemaal,
        "3": gemaal,
    }
    # De streng zelf is de eerste stap: 3, 2, 1 richting het gemaal.
    assert [per_streng["1"].stappen, per_streng["2"].stappen, per_streng["3"].stappen] == [3, 2, 1]
    assert [per_streng["1"].meters, per_streng["2"].meters, per_streng["3"].meters] == [
        150.0,
        100.0,
        50.0,
    ]


def test_streng_zonder_lijn_krijgt_stappen_maar_geen_meters() -> None:
    context = _context("net_afvoerpad_zonder_lijn.ttl")
    dataset = context.dataset

    pad = afvoerpad_van_streng(context, _streng(dataset, "1"))

    assert pad is not None
    assert pad.eindpunt == _uri(dataset, "G")
    assert pad.stappen == 1
    # Zonder bruikbare lijngeometrie is er geen padlengte in meters.
    assert pad.meters is None
    # En de bovenstroomse knoop erft dat: wel stappen, geen meters.
    assert afvoerpaden(context)[_uri(dataset, "A")].meters is None


def test_knoop_zonder_afvoerpad_staat_niet_in_de_uitkomst() -> None:
    # In het losse deelstelsel C-D watert alles af op put D, en dat is geen eindpunt.
    context = _context("net001_geen_afvoerpad.ttl")
    dataset = context.dataset

    paden = afvoerpaden(context)

    assert _uri(dataset, "C") not in paden
    assert _uri(dataset, "D") not in paden
    # Het deel rond het gemaal bereikt het wel.
    assert paden[_uri(dataset, "A")].eindpunt == _uri(dataset, "G")
