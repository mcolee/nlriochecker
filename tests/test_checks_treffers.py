"""Tests voor het trefferregister: de externe objecten die de checks raken."""

from __future__ import annotations

from shapely.geometry import box

from nlriochecker.checks.treffers import Treffer, Trefferregister, bouw_sleutel

VLAK = box(0, 0, 10, 10)


def _treffer(sleutel: str = "bgt:pand/p1") -> Treffer:
    """Een treffer om het register mee te vullen."""
    return Treffer(
        sleutel=sleutel,
        bron="bgt_pand",
        label="pand p1",
        bronbestand="bgt.gpkg",
        geometrie=VLAK,
        attributen={"lokaal_id": "p1"},
    )


def test_sleutel_komt_uit_het_bron_id() -> None:
    sleutel, terugval = bouw_sleutel("bgt:pand", {"lokaal_id": "p1"}, VLAK)

    assert sleutel == "bgt:pand/p1"
    assert terugval is False


def test_sleutel_valt_terug_op_de_geometriehash() -> None:
    """Zonder bron-ID moet de sleutel toch stabiel en herhaalbaar zijn."""
    sleutel, terugval = bouw_sleutel("bgt:pand", {"status": "bestaand"}, VLAK)
    opnieuw, _ = bouw_sleutel("bgt:pand", {"status": "bestaand"}, VLAK)

    assert sleutel.startswith("geo:")
    assert len(sleutel) == len("geo:") + 12
    assert sleutel == opnieuw
    assert terugval is True


def test_sleutelvolgorde_lokaal_id_wint_van_identificatie() -> None:
    sleutel, _ = bouw_sleutel("bgt:pand", {"identificatie": "b", "lokaal_id": "a"}, VLAK)

    assert sleutel == "bgt:pand/a"


def test_lege_waarde_telt_niet_als_id() -> None:
    sleutel, terugval = bouw_sleutel("bgt:pand", {"lokaal_id": "  ", "id": "x"}, VLAK)

    assert sleutel == "bgt:pand/x"
    assert terugval is False


def test_registreren_ontdubbelt_op_de_sleutel() -> None:
    register = Trefferregister()

    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:a", afstand_m=0.0)
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:b", afstand_m=0.5)

    assert len(register) == 1
    assert register.get("bgt:pand/p1") is not None


def test_afstand_wordt_per_melding_bewaard() -> None:
    """`Melding` draagt de afstand niet; de schrijver moet hem hier terugvinden."""
    register = Trefferregister()
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:a", afstand_m=0.0)
    register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:b", afstand_m=0.5)

    assert register.afstand("bgt:pand/p1", "EXT-001", "urn:b") == 0.5
    assert register.afstand("bgt:pand/p1", "EXT-001", "urn:onbekend") is None


def test_registreren_levert_de_sleutel_terug() -> None:
    register = Trefferregister()

    sleutel = register.registreer(_treffer(), check_id="EXT-001", object_uri="urn:a")

    assert sleutel == "bgt:pand/p1"


def test_over_de_treffers_lopen() -> None:
    register = Trefferregister()
    register.registreer(_treffer("bgt:pand/a"), check_id="EXT-001", object_uri="urn:a")
    register.registreer(_treffer("bgt:pand/b"), check_id="EXT-001", object_uri="urn:b")

    assert sorted(treffer.sleutel for treffer in register) == ["bgt:pand/a", "bgt:pand/b"]


def test_onbekende_sleutel_geeft_none() -> None:
    assert Trefferregister().get("bgt:pand/weg") is None


def test_bron_zonder_id_wordt_per_check_gemeld() -> None:
    """De check meldt in haar toelichting dat de sleutel uit de geometrie komt."""
    register = Trefferregister()

    register.meld_zonder_id("EXT-001", "bgt.gpkg")
    register.meld_zonder_id("EXT-001", "bgt.gpkg")

    assert register.zonder_id("EXT-001") == ("bgt.gpkg",)
    assert register.zonder_id("EXT-003") == ()
