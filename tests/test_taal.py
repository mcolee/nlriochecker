"""Tests voor de grammaticahulp bij gegenereerde meldingen."""

from __future__ import annotations

import pytest

from nlriochecker.taal import getal, met_lidwoord, vorm


def test_getal_gebruikt_enkelvoud_bij_een():
    """Een telwoord van 1 hoort bij de enkelvoudsvorm."""
    assert getal(1, "bevinding", "bevindingen") == "1 bevinding"


def test_getal_gebruikt_meervoud_boven_een():
    """Alles boven 1 krijgt de meervoudsvorm."""
    assert getal(2, "bevinding", "bevindingen") == "2 bevindingen"


def test_getal_gebruikt_meervoud_bij_nul():
    """Nul is in het Nederlands meervoud: 'geen 0 bevinding'."""
    assert getal(0, "bevinding", "bevindingen") == "0 bevindingen"


def test_lidwoord_de_woord():
    """De maaiveldhoogte, niet het maaiveldhoogte."""
    assert met_lidwoord("maaiveldhoogte") == "de maaiveldhoogte"


def test_lidwoord_het_woord():
    """Het putdekselniveau houdt zijn eigen lidwoord."""
    assert met_lidwoord("putdekselniveau") == "het putdekselniveau"


def test_onbekend_woord_faalt_hard():
    """Een onbekend woord mag niet stilzwijgend 'de' krijgen.

    Anders sluipt er een grammaticafout het rapport in zodra iemand een nieuw
    meldingsjabloon schrijft; nu valt het om in de test.
    """
    with pytest.raises(KeyError, match="drempelniveau"):
        met_lidwoord("drempelniveau")


def test_vorm_kiest_enkelvoud_bij_een():
    """Voor een werkwoord of zelfstandig naamwoord zonder telwoord ervoor."""
    assert vorm(1, "loopt", "lopen") == "loopt"


def test_vorm_kiest_meervoud_boven_een():
    assert vorm(3, "loopt", "lopen") == "lopen"


def test_vorm_kiest_meervoud_bij_nul():
    assert vorm(0, "loopt", "lopen") == "lopen"
