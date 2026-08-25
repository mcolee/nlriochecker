"""Tests voor de status en de popup van een object op de kaart."""

from __future__ import annotations

from shapely.geometry import Point

from helpers_melding import melding as _basismelding
from nlriochecker.uitvoer.melding import BRON_NULMETING, BRON_REGISTER, Melding
from nlriochecker.uitvoer.objectkaart import (
    MAX_MELDINGEN_IN_POPUP,
    STATUS_GRIJS,
    STATUS_GROEN,
    STATUS_ORANJE,
    STATUS_ROOD,
    Objectkop,
    bepaal_status,
    popup_html,
)


def _melding(
    ernst: str = "F",
    check_id: str = "TOP-011",
    bron: str = BRON_REGISTER,
    systemisch: bool = False,
    **velden: object,
) -> Melding:
    """Een melding met de velden die de kaartweergave leest."""
    return _basismelding(
        melding_id=f"{check_id}-{ernst}",
        check_id=check_id,
        bron=bron,
        ernst=ernst,
        systemisch=systemisch,
        prioriteit=2 if ernst == "F" else 3,
        foutlocatie=Point(0, 0),
        **velden,
    )


class TestStatus:
    """Vier waarden, en geen vijfde."""

    def test_een_fout_maakt_rood(self) -> None:
        assert bepaal_status([_melding("F")], geanalyseerd=True) == STATUS_ROOD

    def test_alleen_waarschuwingen_maakt_oranje(self) -> None:
        assert bepaal_status([_melding("W")], geanalyseerd=True) == STATUS_ORANJE

    def test_geen_meldingen_maakt_groen(self) -> None:
        assert bepaal_status([], geanalyseerd=True) == STATUS_GROEN

    def test_niet_geanalyseerd_maakt_grijs(self) -> None:
        assert bepaal_status([], geanalyseerd=False) == STATUS_GRIJS

    def test_een_gebrek_wint_van_niet_geanalyseerd(self) -> None:
        """Mechanisch riool wordt wel degelijk door TOP-010 en de nulmeting geraakt.

        Op de Koekangerveld-run dragen 17 van de 20 mechanische strengen een melding.
        Zouden die grijs blijven, dan beweert de kaart dat er niets bekeken is terwijl
        er fouten op staan -- en sinds `meldinglocaties` verviel is er geen tweede plek
        meer waar ze wel zichtbaar zijn.
        """
        assert bepaal_status([_melding("F")], geanalyseerd=False) == STATUS_ROOD
        assert bepaal_status([_melding("W")], geanalyseerd=False) == STATUS_ORANJE

    def test_grijs_blijft_grijs_zonder_meldingen(self) -> None:
        """Grijs betekent: niet beoordeeld en niets gevonden."""
        assert bepaal_status([], geanalyseerd=False) == STATUS_GRIJS
        assert bepaal_status([_melding("F", systemisch=True)], geanalyseerd=False) == STATUS_GRIJS

    def test_systemische_meldingen_tellen_niet_mee(self) -> None:
        """Anders is op De Wolden en Hoogeveen vrijwel elke put rood en zegt de kaart niets meer.

        Dezelfde regel als `ergste_ernst`, `n_fout` en `n_waarschuwing` al volgen.
        """
        assert bepaal_status([_melding("F", systemisch=True)], geanalyseerd=True) == STATUS_GROEN


class TestPopup:
    """Wat een gebruiker ziet als hij over het object hovert."""

    def test_de_kopregel_noemt_label_objecttype_en_status(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), [_melding()])

        assert "A" in html
        assert "Inspectieput" in html
        assert "s-rood" in html

    def test_elke_melding_krijgt_ernstsymbool_check_en_boodschap(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), [_melding()])

        assert "✕" in html
        assert "TOP-011" in html
        assert "Er is iets mis met dit object." in html

    def test_een_waarschuwing_krijgt_het_andere_symbool(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ORANJE), [_melding("W")])

        assert "⚠" in html

    def test_een_nulmetingmelding_noemt_haar_conformiteitsklassen(self) -> None:
        melding = _melding(bron=BRON_NULMETING, check_id="NULMETING-LengteLeiding_val")
        html = popup_html(
            Objectkop("A", "Inspectieput", STATUS_ROOD),
            [Melding(**{**melding.__dict__, "cfk": ("Hyd", "MdsPlan")})],
        )

        assert "nulmeting" in html
        assert "Hyd, MdsPlan" in html

    def test_een_eigen_check_noemt_dat_ze_eigen_is(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), [_melding()])

        assert "eigen check" in html

    def test_lege_waarde_en_drempel_worden_weggelaten(self) -> None:
        """Lege velden onderdrukken in plaats van lege cellen tonen."""
        zonder = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), [_melding()])
        met = popup_html(
            Objectkop("A", "Inspectieput", STATUS_ROOD),
            [_melding(waarde="12,3 m", drempel="75 m")],
        )

        assert "waarde" not in zonder
        assert "12,3 m" in met and "75 m" in met

    def test_boven_vijf_meldingen_volgt_een_afsluitende_regel(self) -> None:
        meldingen = [_melding(check_id=f"TOP-{nummer:03d}") for nummer in range(1, 9)]

        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), meldingen)

        assert html.count("<li") == MAX_MELDINGEN_IN_POPUP
        assert "en nog 3 andere" in html

    def test_fouten_staan_boven_waarschuwingen(self) -> None:
        """De cap van vijf mag niet net de fouten wegsnijden."""
        meldingen = [_melding("W", check_id=f"BTR-{n:03d}") for n in range(1, 8)]
        meldingen.append(_melding("F", check_id="TOP-001"))

        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), meldingen)

        assert "TOP-001" in html

    def test_een_streng_noemt_haar_kenmerken(self) -> None:
        kop = Objectkop(
            "L1",
            "GemengdRiool",
            STATUS_GROEN,
            feiten=("Stelsel: gemengd", "Lengte: 12,3 m", "BOB loopt met de lijn mee"),
        )

        html = popup_html(kop, [])

        assert "Stelsel: gemengd" in html
        assert "BOB loopt met de lijn mee" in html

    def test_een_grijs_object_zegt_waarom_het_niet_beoordeeld_is(self) -> None:
        """Grijs zonder reden leest als 'in orde', en dat is het niet."""
        kop = Objectkop("L1", "Persleiding", STATUS_GRIJS, reden="mechanisch riool")

        html = popup_html(kop, [])

        assert "mechanisch riool" in html

    def test_zonder_meldingen_staat_er_geen_lege_lijst(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_GROEN), [])

        assert "<li" not in html
        assert "geen" in html.lower()

    def test_systemische_meldingen_staan_niet_in_de_lijst(self) -> None:
        """Dezelfde kwestie op vrijwel elk object hoort niet per object in de popup (#76)."""
        html = popup_html(
            Objectkop("A", "Inspectieput", STATUS_GROEN),
            [_melding(systemisch=True, check_id="ATTR-014")],
        )

        assert "<li" not in html
        assert "ATTR-014" not in html

    def test_alleen_systemische_meldingen_leest_niet_als_geen_meldingen(self) -> None:
        """De slotregel zegt al wat er is; "geen meldingen" zou dat tegenspreken.

        Op de vlakkenlaag staat er bovendien een kopregel boven die het aantal gemelde
        strengen noemt.
        """
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_GROEN), [_melding(systemisch=True)])

        assert "Geen meldingen op dit object" not in html

    def test_zonder_enige_melding_staat_er_nog_wel_dat_er_niets_is(self) -> None:
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_GROEN), [])

        assert "Geen meldingen op dit object" in html

    def test_de_popup_zegt_hoeveel_systemische_meldingen_ze_weglaat(self) -> None:
        """Een groen object met alleen systemische meldingen mag niet zwijgen.

        Weglaten zonder tellen leest als "hier is niets gevonden"; dat is het niet.
        """
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_GROEN), [_melding(systemisch=True)])

        assert "1 systemische melding" in html
        assert "telt niet mee in de status" in html

    def test_de_cap_van_vijf_telt_alleen_de_getoonde_meldingen(self) -> None:
        """De weggelaten systemische meldingen mogen geen "en nog N andere" opleveren."""
        meldingen = [
            _melding("F", check_id=f"NULMETING-Vorm_{n}_card", systemisch=True) for n in range(1, 8)
        ]
        meldingen += [_melding("F", check_id=f"RVZ-{n:03d}") for n in range(1, 4)]

        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), meldingen)

        assert html.count("<li") == 3
        assert "en nog" not in html
        assert "7 systemische meldingen" in html

    def test_de_inhoud_wordt_geescaped(self) -> None:
        """Labels en boodschappen komen uit de brondata en mogen niets breken."""
        html = popup_html(
            Objectkop("<b>A</b>", "Inspectieput", STATUS_ROOD),
            [_melding(boodschap="a < b & c")],
        )

        assert "<b>A</b>" not in html
        assert "&lt;b&gt;A&lt;/b&gt;" in html
        assert "a &lt; b &amp; c" in html

    def test_er_zit_geen_externe_verwijzing_in(self) -> None:
        """De popup moet zelfstandig reizen: geen webfont, geen afbeelding-URL."""
        html = popup_html(Objectkop("A", "Inspectieput", STATUS_ROOD), [_melding()])

        assert "http://" not in html and "https://" not in html
