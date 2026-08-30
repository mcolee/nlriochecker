"""Tests voor de vertaaltabel van de SHACL-vormen naar leesbare zinnen (issue #101).

De drifttest tegen de echte De Wolden-rapporten staat in `test_integration.py`: die
heeft de rapporten uit `data/` nodig en slaat zonder die bestanden over. Hier staat
wat er zonder invoerdata te toetsen valt: de omvang van de tabel, het invullen van de
sjabloonvelden uit de meldingsrij, en de terugval op de technische tekst. De vormen
van het getrackte voorbeeld worden hier wél tegen echte serveruitvoer gehouden -- die
CSV's staan in de repository -- en die van De Wolden daar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.meting import laad_nulmeting
from nlriochecker.nulmeting_teksten import leesbaar, vertaald, vormteksten, vul_sjabloon

# Zoveel unieke SHACL-vormen komen er in de drie De Wolden-rapporten voor (gemeten
# 28-08-2026, kolom `Source` over Hyd, MdsPlan en MdsProj samen). De auteur heeft voor
# elk ervan een tekst vastgesteld (issue #101). Valt dit getal, dan is er een tekst
# gesneuveld; de drifttest tegen de rapporten zelf staat in `test_integration.py`.
VORMEN_DE_WOLDEN = 43

# De drie SHACL-rapporten van het getrackte voorbeeld; de bestandsnamen zijn niet
# symmetrisch, dus ze staan hier voluit (net als in `test_voorbeeld.py`).
VOORBEELD = Path(__file__).resolve().parents[1] / "voorbeelden" / "koekangerveld"
VOORBEELD_SHACL = [
    VOORBEELD / "gwsw_shacl_report_conformiteit_Hyd.csv",
    VOORBEELD / "gwsw_shacl_report_conformiteit_MdsPlan.csv",
    VOORBEELD / "gwsw_shacl_report_MdsProj.csv",
]

# Zoveel unieke SHACL-vormen dragen die drie rapporten samen (gemeten 30-08-2026:
# Hyd 527 rijen / 17 vormen, MdsPlan 361 / 12, MdsProj 359 / 11; de vereniging is 17).
# Vastgelegd en niet berekend, net als `MELDINGEN_IN_HET_VOORBEELD`: regenereert iemand
# het voorbeeld met `uv run python scripts/maak_voorbeeld.py` op een nieuwe export, dan
# kan het getal schuiven en hoort het hier bijgewerkt te worden met een nieuwe datum.
VORMEN_IN_HET_VOORBEELD = 17


def test_de_tabel_draagt_elke_vorm_uit_de_de_wolden_rapporten() -> None:
    """43 vormen, 43 teksten."""
    assert len(vormteksten()) == VORMEN_DE_WOLDEN


def test_elke_vorm_in_het_getrackte_voorbeeld_heeft_een_leesbare_zin() -> None:
    """De data-vrije helft van de drifttest van issue #101, op echte serveruitvoer.

    De 43-vormentest in `test_integration.py` heeft `data/` nodig en slaat op de
    CI-runner en in elke schone kloon over; daar bleef alleen de tabel-tegen-zichzelf
    over. Het voorbeeld is getrackt, dus deze 17 vormen worden overal gemeten -- via
    `laad_nulmeting`, zodat een wijziging in de kolomdetectie hier ook omvalt.

    De telling gaat vóór de vertaalvraag: over een lege verzameling is "alles vertaald"
    waar, dus zonder haar zou een mislukte parse vals-groen zijn. De omgekeerde
    bewering (elke tabeltekst komt in de rapporten voor) staat bewust alleen bij De
    Wolden: 26 van de 43 teksten komen in dit voorbeeld niet voor.
    """
    meting = laad_nulmeting(VOORBEELD_SHACL, ["Hyd", "MdsPlan", "MdsProj"])
    vormen = {vorm for cfk in meting.cfks for vorm in meting.report(cfk).findings["Source"]}

    assert len(vormen) == VORMEN_IN_HET_VOORBEELD
    assert sorted(vorm for vorm in vormen if not vertaald(vorm)) == []


def test_elke_tekst_is_een_beschrijvend_fragment() -> None:
    """Geen lege waarde, geen witruimte eromheen, geen afsluitende punt.

    De zin komt in een tabelcel, in een popup en in een CSV-kolom te staan; een punt
    aan het eind zou daar overal vreemd staan en suggereert een tweede zin.
    """
    for vorm, tekst in vormteksten().items():
        assert tekst and tekst.strip() == tekst, vorm
        assert not tekst.endswith("."), vorm


def test_een_kardinaliteitsvorm_krijgt_zijn_vaste_zin() -> None:
    """Zonder sjabloonveld blijft de zin zoals hij in de tabel staat."""
    zin = leesbaar(
        "Put_HoogtePut_card",
        "Subject Put, path hasAspect, object HoogtePut - aantal voorkomens wijkt af (exact=1)",
        "te weinig voorkomens",
    )

    assert zin == "Put zonder (of met meer dan één) geregistreerde puthoogte"


def test_de_grens_komt_uit_de_boodschap_van_de_rij() -> None:
    """`{min}` en `{max}` komen uit de meldingsrij, niet uit een vastgelegde waarde."""
    zin = leesbaar(
        "LengteLeiding_val",
        "Kenmerk LengteLeiding - waarde wijkt af (min=1,max=75)",
        "164.200 (decimal) ",
    )

    assert zin == "Strenglengte buiten het aannemelijke bereik (1–75 m)"


def test_een_andere_grens_in_de_rij_geeft_een_andere_zin() -> None:
    """De grens wordt gelezen en niet gekend: een tweede CFK mag een andere eisen."""
    zin = leesbaar(
        "HoogteTovNAP_val",
        "Kenmerk HoogteTovNAP - waarde wijkt af (min=-20,max=325)",
        "lei7547-7548-1_lei7224_ein7224_bob",
    )

    assert zin == "Hoogte t.o.v. NAP buiten het aannemelijke bereik (-20–325 m)"


def test_zonder_grens_in_de_rij_vervalt_de_haakjesgroep() -> None:
    """Geen verzonnen grens: de zin blijft staan zonder het stuk dat niet te vullen is."""
    zin = leesbaar("LengteLeiding_val", "Kenmerk LengteLeiding - waarde wijkt af", "")

    assert zin == "Strenglengte buiten het aannemelijke bereik"


def test_haakjes_zonder_sjabloonveld_blijven_staan() -> None:
    """Alleen een groep met een onvulbaar veld vervalt; gewone haakjes horen bij de tekst."""
    zin = leesbaar(
        "CfkTypes_typ", "Type individu wijkt af (is abstract, te globaal binnen CFK)", ""
    )

    assert zin == 'Objecttype te globaal voor deze toetsing (bijv. "Put" waar "Inspectieput" hoort)'


def test_een_onbekende_vorm_valt_terug_op_de_technische_tekst() -> None:
    """Het vangnet: liever de SHACL-tekst dan geen melding."""
    boodschap = "Subject Iets, path hasPart, object Anders - aantal voorkomens wijkt af (min=1)"

    assert leesbaar("Iets_Anders_card", boodschap, "te weinig voorkomens") == boodschap
    assert not vertaald("Iets_Anders_card")
    assert vertaald("Put_HoogtePut_card")


@pytest.mark.parametrize(
    ("waarde", "verwacht"),
    [
        ("3 (integer) ", "Proef met (3 stuks)"),
        ("te weinig voorkomens", "Proef met"),
        ("", "Proef met"),
    ],
)
def test_het_aantal_komt_uit_de_kolom_value(waarde: str, verwacht: str) -> None:
    """`{n}` is het getal waarmee `Value` opent; draagt zij er geen, dan vervalt de groep.

    Geen van de 43 vastgestelde teksten gebruikt `{n}` -- de auteur vangt "nul of meer
    dan één" in één zin op. Het veld bestaat voor een tekst die het wél nodig heeft, en
    deze test legt vast waar de waarde dan vandaan komt.
    """
    assert vul_sjabloon("Proef met ({n} stuks)", "boodschap zonder grens", waarde) == verwacht


def test_de_tabel_is_niet_te_wijzigen_via_de_teruggegeven_afbeelding() -> None:
    """De tabel is een package-resource; een beller die hem aanpast raakt elke run."""
    with pytest.raises(TypeError):
        vormteksten()["Put_HoogtePut_card"] = "iets anders"  # type: ignore[index]
