"""Tests voor de stabiele melding-ID."""

from __future__ import annotations

from gwswpijplijn.uitvoer.identiteit import melding_id


def test_id_is_zestien_hextekens() -> None:
    kenmerk = melding_id("TOP-011", "urn:a", "urn:b", {})

    assert len(kenmerk) == 16
    assert all(teken in "0123456789abcdef" for teken in kenmerk)


def test_gelijke_feiten_geven_hetzelfde_id() -> None:
    """De ID hoort tussen runs gelijk te blijven, ook over sessies heen."""
    assert melding_id("TOP-011", "urn:a", "urn:b", {}) == melding_id(
        "TOP-011", "urn:a", "urn:b", {}
    )


def test_andere_check_geeft_een_ander_id() -> None:
    assert melding_id("TOP-010", "urn:a", "urn:b", {}) != melding_id(
        "TOP-011", "urn:a", "urn:b", {}
    )


def test_ander_tweede_object_geeft_een_ander_id() -> None:
    """TOP-011 meldt dezelfde streng tegen meerdere kruisende strengen."""
    assert melding_id("TOP-011", "urn:a", "urn:b", {}) != melding_id(
        "TOP-011", "urn:a", "urn:c", {}
    )


def test_identificerende_sleutels_onderscheiden_twee_meldingen() -> None:
    """HGT-003 meldt per zijde; zonder die sleutel botsen de twee bevindingen."""
    begin = melding_id("HGT-003", "urn:a", "", {"zijde": "beginpunt"})
    eind = melding_id("HGT-003", "urn:a", "", {"zijde": "eindpunt"})

    assert begin != eind


def test_sleutelvolgorde_doet_er_niet_toe() -> None:
    """Anders hangt de ID af van de invoegvolgorde van de details."""
    een = melding_id("HGT-003", "urn:a", "", {"zijde": "beginpunt", "rol": "aanvoer"})
    twee = melding_id("HGT-003", "urn:a", "", {"rol": "aanvoer", "zijde": "beginpunt"})

    assert een == twee
