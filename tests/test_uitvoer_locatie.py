"""Tests voor de foutlocatie van een melding.

Het punt in de kaartlaag `meldinglocaties` is de plek waar het probleem zit, niet
per se de plek van het object: een kruising hoort op het snijpunt te staan, een
attribuutfout op de streng in het midden ervan.
"""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.dataset import load_dataset

from nlriochecker.checks import Dimension, Finding, Severity
from nlriochecker.uitvoer.locatie import foutlocatie

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def _dataset():
    """De schone fixture: put A op (1000, 2000), put B op (1050, 2000), streng 1 ertussen."""
    return load_dataset(TTL_DIR / "schoon.ttl", [])


def _bevinding(uri: str, **kenmerken) -> Finding:
    """Een kale bevinding op een object."""
    return Finding(
        check_id="TOP-011",
        severity=Severity.ERROR,
        dimension=Dimension.CONSISTENCY,
        object_uri=uri,
        object_label="x",
        message="",
        typing_reliable=True,
        **kenmerken,
    )


def _uri(dataset, label: str, bron: str) -> str:
    """De URI van het object met dit label."""
    verzameling = dataset.nodes if bron == "nodes" else dataset.conduits
    return next(uri for uri, object_ in verzameling.items() if object_.label == label)


def test_eigen_foutlocatie_van_de_check_gaat_voor() -> None:
    """TOP-011 kent het snijpunt al; dat is de plek van het probleem."""
    dataset = _dataset()
    uri = _uri(dataset, "A", "nodes")

    punt = foutlocatie(_bevinding(uri, details={"foutlocatie": (1234.0, 5678.0)}), dataset)

    assert (punt.x, punt.y) == (1234.0, 5678.0)


def test_melding_op_een_put_krijgt_de_putlocatie() -> None:
    dataset = _dataset()

    punt = foutlocatie(_bevinding(_uri(dataset, "A", "nodes")), dataset)

    assert (punt.x, punt.y) == (1000.0, 2000.0)


def test_melding_op_een_streng_krijgt_het_middelpunt() -> None:
    """Het beginpunt zou de melding op de put leggen die er niets mee te maken heeft."""
    dataset = _dataset()

    punt = foutlocatie(_bevinding(_uri(dataset, "1", "conduits")), dataset)

    assert (punt.x, punt.y) == (1025.0, 2000.0)


def test_extern_object_gebruikt_zijn_eigen_coordinaat() -> None:
    """Een melding op een object buiten de GWSW-dataset draagt zijn eigen coordinaat.

    EXT-006 was tot issue #95 de enige check die zulke meldingen maakte (een BGT-deksel
    zonder put); de weg blijft bestaan voor een volgende check op een externe bron.
    """
    punt = foutlocatie(_bevinding("urn:bgt:deksel-1", location=(1111.0, 2222.0)), _dataset())

    assert (punt.x, punt.y) == (1111.0, 2222.0)


def test_object_zonder_geometrie_krijgt_geen_punt() -> None:
    """Zwijgen is hier het goede antwoord; de teller elders meldt hoeveel dat er zijn."""
    assert foutlocatie(_bevinding("urn:onbekend"), _dataset()) is None


def test_onverwachte_geometrie_levert_toch_een_punt() -> None:
    """Een streng met een vlak als geometrie mag de uitvoer niet laten omvallen.

    TOP-015 en TOP-016 melden juist zulke geometrie; als de foutlocatie er dan op
    struikelt, verdwijnt de melding waar hij het hardst nodig is. De fixture
    top016_ongeldige_geometrie.ttl bevat een object met een vlakgeometrie.
    """
    dataset = load_dataset(TTL_DIR / "top016_ongeldige_geometrie.ttl", [])
    uri, conduit = next(
        (uri, conduit)
        for uri, conduit in dataset.conduits.items()
        if conduit.line is not None and conduit.line.geom_type != "LineString"
    )

    punt = foutlocatie(_bevinding(uri), dataset)

    assert punt is not None
    assert conduit.line.distance(punt) == 0.0
