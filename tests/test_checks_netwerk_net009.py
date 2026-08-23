"""Tests voor NET-009: de richtingsdiagnose (#18, fase 2)."""

from __future__ import annotations

from pathlib import Path

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckOutcome, run_checks
from nlriochecker.dataset import load_dataset, markeer_vulwaarden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def _outcome(bestand: str) -> CheckOutcome:
    """Draait NET-009 op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=load_check_config())
    return run_checks(context, ["NET-009"]).outcomes[0]


def test_schoon_netwerk_geeft_geen_bevinding() -> None:
    # net_schoon: geometrie in de van-naar-richting, geen BOB -> niets spreekt elkaar tegen.
    assert _outcome("net_schoon.ttl").findings == []


def test_omgekeerd_getekende_streng_noemt_alle_drie_de_signalen() -> None:
    outcome = _outcome("net009_omgekeerd_getekend.ttl")

    assert len(outcome.findings) == 1
    bevinding = outcome.findings[0]
    assert bevinding.object_label == "1"
    # Alle drie de signalen staan in de tekst: administratief (A->B), de omgekeerde
    # tekenrichting, en de dalende BOB.
    boodschap = bevinding.message
    assert "A" in boodschap and "B" in boodschap
    assert "omgekeerd" in boodschap
    assert "daalt" in boodschap
    assert bevinding.details["geometrie"] == "tegen"
    assert bevinding.details["bob"] == "mee"


def test_net009_omvat_het_tegenverhang_van_net003() -> None:
    # net003: BOB stijgt van begin naar eind (bob tegen), geometrie volgt de administratie.
    # NET-003 meldt dit als hoogteprobleem; NET-009 leest het als richtingsprobleem.
    outcome = _outcome("net003_tegen_de_richting.ttl")

    assert [f.object_label for f in outcome.findings] == ["1"]
    assert outcome.findings[0].details["bob"] == "tegen"
    assert outcome.findings[0].details["geometrie"] == "mee"


def test_vlakke_streng_geeft_geen_bevinding_maar_geen_uitspraak() -> None:
    outcome = _outcome("net009_vlakke_streng.ttl")

    assert outcome.findings == []
    assert any("geen uitspraak" in note for note in outcome.notes)
    assert any("1 streng" in note and "vlak" in note for note in outcome.notes)


def test_bob_vulwaarde_valt_buiten_beeld_en_wordt_gemeld() -> None:
    """Een BOB van 0,00 die als vulwaarde is gelezen, valt uit de BOB-toets.

    De streng krijgt geen bevinding (geometrie volgt de administratie, BOB ontbreekt) en
    de toelichting meldt hoeveel strengen om die reden buiten de BOB-toets vielen.
    """
    dataset = markeer_vulwaarden(
        load_dataset(TTL_DIR / "net009_bob_vulwaarde.ttl"),
        ["BobBeginpuntLeiding", "BobEindpuntLeiding"],
        0.01,
    )
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["NET-009"]).outcomes[0]

    assert outcome.findings == []
    assert any("vulwaarde" in note for note in outcome.notes)


def test_signaalvarianten_verwoorden_vlakke_bob_en_ontbrekende_geometrie() -> None:
    """Een omgekeerd-vlakke streng en een streng zonder lijn maar met stijgende BOB.

    Beide worden gemeld; de teksten verwoorden de vlakke BOB en de niet te bepalen
    tekenrichting expliciet.
    """
    outcome = _outcome("net009_signaalvarianten.ttl")
    per_label = {f.object_label: f for f in outcome.findings}

    assert set(per_label) == {"1", "2"}
    # Streng 1: omgekeerd getekend (geo tegen) maar vlak (bob vlak).
    assert per_label["1"].details["geometrie"] == "tegen"
    assert per_label["1"].details["bob"] == "vlak"
    assert "ligt vlak" in per_label["1"].message
    # Streng 2: geen bruikbare lijn (geo onbekend) maar stijgende BOB (bob tegen).
    assert per_label["2"].details["geometrie"] == "onbekend"
    assert per_label["2"].details["bob"] == "tegen"
    assert "niet te bepalen" in per_label["2"].message
    assert "stijgt" in per_label["2"].message


def test_streng_zonder_enig_signaal_wordt_niet_stil_overgeslagen() -> None:
    """Een streng zonder bruikbare lijn en zonder BOB is met geen signaal te toetsen.

    Ze levert geen bevinding, maar mag niet stil verdwijnen: de toelichting telt haar en
    `examined` rekent haar niet mee, want er viel niets aan te beoordelen.
    """
    outcome = _outcome("net009_geen_signaal.ttl")

    assert outcome.findings == []
    assert any("geen enkel richtingssignaal" in note for note in outcome.notes)
    # Alleen de schone streng 1 is te beoordelen; streng 2 valt buiten.
    assert outcome.examined == 1


def test_net009_severity_en_dimensie() -> None:
    outcome = _outcome("net009_omgekeerd_getekend.ttl")

    assert outcome.severity.value == "F"
    assert outcome.dimension.value == "Consistentie"
