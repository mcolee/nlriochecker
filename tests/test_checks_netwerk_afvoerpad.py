"""Tests voor de afvoerpadanalyse (#18, fase 1)."""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.dataset import GwswDataset, load_dataset

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.verbanden import afvoerpad_van_streng, afvoerpaden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def _context(bestand: str) -> CheckContext:
    """Bouwt een context op een netwerkfixture."""
    dataset = load_dataset(TTL_DIR / bestand, [])
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


def test_bij_gelijk_aantal_stappen_wint_het_eindpunt_met_de_kleinste_uri() -> None:
    """Determinisme: twee even dichtbije eindpunten, de kleinste URI beslist."""
    context = _context("net_afvoerpad_twee_eindpunten.ttl")
    dataset = context.dataset
    gemaal_a = _uri(dataset, "GA")
    gemaal_b = _uri(dataset, "GB")

    pad = afvoerpaden(context)[_uri(dataset, "A")]

    assert pad.stappen == 1
    assert pad.eindpunt == min(gemaal_a, gemaal_b)


def test_parallelle_strengen_gebruiken_deterministisch_dezelfde_lengte() -> None:
    """Op parallelle strengen leest de knoop de lengte van de kleinste-URI streng.

    De streng zelf leest haar eigen lengte, zodat de rechte (100 m) en de geknikte
    (~141 m) streng elk hun eigen padlengte houden.
    """
    context = _context("net_afvoerpad_parallel.ttl")
    dataset = context.dataset
    la, lb = _streng(dataset, "a"), _streng(dataset, "b")
    representant = min((la, lb), key=lambda streng: streng.uri)

    knoop = afvoerpaden(context)[_uri(dataset, "A")]
    assert knoop.meters == representant.line.length

    assert afvoerpad_van_streng(context, la).meters == la.line.length
    assert afvoerpad_van_streng(context, lb).meters == lb.line.length


def test_mechanische_streng_krijgt_geen_afvoerpad() -> None:
    """Een persleiding hoort niet in de vrijverval-afvoerpadanalyse.

    De vrijvervalstreng ernaast bereikt het gemaal wel; de persleiding niet, ook al
    komt ze op hetzelfde gemaal uit -- gepompt riool is geen vrijverval-afvoerpad.
    """
    context = _context("net_afvoerpad_mechanisch.ttl")
    dataset = context.dataset

    vrijverval = afvoerpad_van_streng(context, _streng(dataset, "1"))
    assert vrijverval is not None
    assert vrijverval.eindpunt == _uri(dataset, "G")

    assert afvoerpad_van_streng(context, _streng(dataset, "p")) is None


def test_afvoerpad_loopt_door_een_telbaar_hulpstuk() -> None:
    """Een streng die op een T-stuk eindigt houdt haar afvoerpad (issue #105, BO-83).

    Sinds het telbare hulpstuk een doorgeefknoop is, zit streng '1' in de graaf en noemt
    NET-001 haar bereikbaar. Zou het afvoerpad haar eindknoop nog met de putherleiding
    zoeken, dan bleef het pad leeg: de GeoPackage toonde dan geen uitstroompunt en geen
    padlengte op een streng die er wel een heeft, en de notitie die dat gat uitlegde staat
    inmiddels op nul.
    """
    context = _context("net_hulpstuk_doorgeefknoop.ttl")
    dataset = context.dataset

    pad = afvoerpad_van_streng(context, _streng(dataset, "1"))

    assert pad is not None
    # A -> T1 -> O -> gemaal: drie stappen van 50 m, met het T-stuk als doorgeefknoop.
    assert (pad.eindpunt, pad.stappen, pad.meters) == (_uri(dataset, "G"), 3, 150.0)


def test_knoop_zonder_afvoerpad_staat_niet_in_de_uitkomst() -> None:
    # In het losse deelstelsel C-D watert alles af op put D, en dat is geen eindpunt.
    context = _context("net001_geen_afvoerpad.ttl")
    dataset = context.dataset

    paden = afvoerpaden(context)

    assert _uri(dataset, "C") not in paden
    assert _uri(dataset, "D") not in paden
    # Het deel rond het gemaal bereikt het wel.
    assert paden[_uri(dataset, "A")].eindpunt == _uri(dataset, "G")
