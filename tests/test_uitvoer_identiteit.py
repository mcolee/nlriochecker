"""Tests voor de stabiele melding-ID."""

from __future__ import annotations

from nlriochecker.uitvoer.identiteit import kort, melding_id


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


def test_kort_geeft_het_fragment_van_een_gwsw_uri() -> None:
    assert kort("http://sparql.gwsw.nl/kikker_vrij#knp3437") == "knp3437"
    assert kort("http://sparql.gwsw.nl/kikker_vrij#lei3436-3435-1") == "lei3436-3435-1"


def test_kort_laat_een_uri_zonder_fragment_ongemoeid() -> None:
    """De EXT-checks melden objecten uit BGT en BAG; die hebben geen dataset-URI."""
    assert kort("bgt:put/deksel-los") == "bgt:put/deksel-los"
    assert kort("") == ""
