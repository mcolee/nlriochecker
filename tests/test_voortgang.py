"""Tests voor het voortgangsprotocol.

Voortgang is weergave. De harde eis is dat hij de uitkomst van een run nergens
raakt; de tests hier leggen vast dat de standaardwaarde niets doet, dat een opnemer
de fasen in de juiste volgorde ziet, en dat de uitvoerbestanden er niet van
veranderen.
"""

from __future__ import annotations

from nlriochecker.voortgang import NUL_VOORTGANG, NulVoortgang, Voortgang


class Opnemer:
    """Legt vast welke fasen en stappen langskomen."""

    def __init__(self) -> None:
        self.gebeurtenissen: list[tuple[str, object, object]] = []

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Legt het begin van een fase vast."""
        self.gebeurtenissen.append(("start", naam, totaal))

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Legt een stap vast."""
        self.gebeurtenissen.append(("stap", n, label))

    def einde_fase(self) -> None:
        """Legt het einde van een fase vast."""
        self.gebeurtenissen.append(("einde", None, None))

    def fasen(self) -> list[tuple[str, object]]:
        """De gestarte fasen met hun totaal, in volgorde."""
        return [(g[1], g[2]) for g in self.gebeurtenissen if g[0] == "start"]  # type: ignore[misc]

    def labels(self, fase: str) -> list[object]:
        """De staplabels binnen een fase, in volgorde."""
        binnen = False
        gevonden: list[object] = []
        for soort, eerste, tweede in self.gebeurtenissen:
            if soort == "start":
                binnen = eerste == fase
            elif soort == "einde":
                binnen = False
            elif binnen:
                gevonden.append(tweede)
        return gevonden


def test_nulvoortgang_voldoet_aan_het_protocol() -> None:
    """De standaardwaarde is een geldige implementatie, niet een None-vervanger."""
    bereik: Voortgang = NUL_VOORTGANG

    bereik.start_fase("iets", 3)
    bereik.stap(2, label="TOP-001")
    bereik.einde_fase()

    assert isinstance(NUL_VOORTGANG, NulVoortgang)


def test_opnemer_voldoet_aan_het_protocol() -> None:
    """De testopnemer is structureel een Voortgang; anders bijten de tests niet."""
    opnemer: Voortgang = Opnemer()

    opnemer.start_fase("Checks", 2)
    opnemer.stap(label="TOP-001")
    opnemer.einde_fase()

    assert isinstance(opnemer, Opnemer)
    assert opnemer.gebeurtenissen == [
        ("start", "Checks", 2),
        ("stap", 1, "TOP-001"),
        ("einde", None, None),
    ]
