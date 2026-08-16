"""Tests voor de NET-checks op kleine netwerkfixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, CheckOutcome, run_checks
from gwswpijplijn.dataset import load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
NET_IDS = ["NET-001", "NET-002", "NET-004", "NET-007"]


def _outcome(bestand: str, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def _labels(bestand: str, check_id: str) -> list[str]:
    """De labels van de gevonden objecten."""
    return sorted(finding.object_label for finding in _outcome(bestand, check_id).findings)


@pytest.mark.parametrize("check_id", NET_IDS)
def test_schoon_netwerk_geeft_geen_bevinding(check_id: str) -> None:
    assert _outcome("net_schoon.ttl", check_id).findings == []


def test_net001_vindt_het_losse_deelstelsel() -> None:
    # Streng "1" en "2" bereiken het gemaal; "3" ligt in een los deelstelsel.
    assert _labels("net001_geen_afvoerpad.ttl", "NET-001") == ["3"]


def test_net002_vindt_hemelwater_zonder_lozingspunt() -> None:
    assert _labels("net002_hemelwater_zonder_lozingspunt.ttl", "NET-002") == ["4"]


def test_net002_raakt_de_gemengde_strengen_niet() -> None:
    # De gemengde strengen vallen onder NET-001, niet onder NET-002.
    assert _labels("net001_geen_afvoerpad.ttl", "NET-002") == []


def test_net004_vindt_de_kringloop() -> None:
    bevindingen = _outcome("net004_kringloop.ttl", "NET-004").findings

    # Een melding per samenhangend deel met een kringloop, niet per enkelvoudige
    # kringloop: dat laatste groeit exponentieel op een echt stelsel.
    assert len(bevindingen) == 1
    assert bevindingen[0].details["putten_in_deel"] == 3
    assert set(bevindingen[0].details["voorbeeldkring"]) == {"C", "D", "E"}


def test_net007_vindt_it_zonder_drempel() -> None:
    assert _labels("net007_it_zonder_drempel.ttl", "NET-007") == ["8"]


def test_net007_zwijgt_als_er_een_drempel_is() -> None:
    assert _labels("net007_it_met_drempel.ttl", "NET-007") == []


def test_ontbrekend_eindpunt_wordt_expliciet_gemeld() -> None:
    # In de TOP-fixture zit geen gemaal; dan is elke streng onbereikbaar en dat
    # hoort met zoveel woorden in de bevinding en in de notities te staan.
    outcome = _outcome("schoon.ttl", "NET-001")

    assert len(outcome.findings) == 1
    assert "geen enkel bereikbaar eindpunt" in outcome.findings[0].message
    assert outcome.findings[0].details["geen_eindpunten_in_graaf"] is True
    assert any("geen enkel eindpunt" in notitie for notitie in outcome.notes)


def test_strengen_buiten_de_graaf_worden_geteld() -> None:
    # Streng "2" heeft geen koppelingen; die valt buiten de netwerkanalyse en
    # dat mag niet stilzwijgend gebeuren.
    outcome = _outcome("top002_losliggende_streng.ttl", "NET-001")

    assert any("buiten de netwerkanalyse" in notitie for notitie in outcome.notes)
    assert any("2" in notitie for notitie in outcome.notes)


def test_eindpuntklassen_komen_uit_de_config(tmp_path: Path) -> None:
    zonder_gemaal = tmp_path / "zonder.toml"
    zonder_gemaal.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "lozings_eindpunt = ['Lozingspunt']\nvuilwater = ['GemengdRiool']\n",
        encoding="utf-8",
    )

    # Met de standaardconfig bereikt alles het gemaal.
    assert _labels("net_schoon.ttl", "NET-001") == []

    # Zonder Gemaal als eindpuntklasse telt het gemaal ook niet meer als knoop:
    # streng "2" eindigt daarop en valt daarmee buiten de graaf, streng "1"
    # blijft over en bereikt niets.
    gevonden = _outcome("net_schoon.ttl", "NET-001", load_check_config(zonder_gemaal))

    assert sorted(finding.object_label for finding in gevonden.findings) == ["1"]
    assert any("buiten de netwerkanalyse" in notitie for notitie in gevonden.notes)


def test_lozingspunt_telt_niet_als_afvoerpad_voor_vuilwater() -> None:
    """Een gemengde streng die alleen een lozingsput bereikt is niet in orde.

    NET-001 vraagt een gemaal of overnamepunt, NET-002 een lozingspunt. Met een
    gedeelde eindpuntlijst zou de gemengde streng ten onrechte goedgekeurd worden.
    """
    bestand = "net001_alleen_lozingspunt.ttl"

    assert _labels(bestand, "NET-001") == ["1"]
    assert _labels(bestand, "NET-002") == []
