"""Tests voor de TOP-checks op kleine fixtures met een bekend defect."""

from __future__ import annotations

from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import GwswDataset, load_dataset

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, Finding, run_checks

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

TOP_IDS = [
    "TOP-001",
    "TOP-002",
    "TOP-003",
    "TOP-004",
    "TOP-005",
    "TOP-012",
    "TOP-022",
    "TOP-023",
]


def _bevindingen(pad: Path, check_id: str, config: CheckConfig | None = None) -> list[Finding]:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(pad, [])
    context = CheckContext(dataset=dataset, config=config or load_check_config())
    return run_checks(context, [check_id]).outcomes[0].findings


def _labels(bevindingen: list[Finding]) -> list[str]:
    """De labels van de gevonden objecten."""
    return sorted(finding.object_label for finding in bevindingen)


@pytest.mark.parametrize(
    ("bestand", "check_id", "label"),
    [
        ("top001_losliggende_put.ttl", "TOP-001", "C"),
        ("top002_losliggende_streng.ttl", "TOP-002", "2"),
        ("top003_een_put.ttl", "TOP-003", "2"),
        ("top004_niet_gesnapt.ttl", "TOP-004", "1"),
        ("top005_dubbele_put.ttl", "TOP-005", "B"),
        ("top012_zelfde_put.ttl", "TOP-012", "2"),
        ("top022_hulpstuk_te_weinig.ttl", "TOP-022", "T1"),
        ("top023_hulpstuk_te_veel.ttl", "TOP-023", "T2"),
    ],
)
def test_defect_wordt_gevonden(bestand: str, check_id: str, label: str) -> None:
    bevindingen = _bevindingen(TTL_DIR / bestand, check_id)

    assert len(bevindingen) == 1
    assert bevindingen[0].object_label == label
    assert bevindingen[0].check_id == check_id


@pytest.mark.parametrize("check_id", TOP_IDS)
def test_schone_fixture_geeft_geen_bevinding(check_id: str) -> None:
    assert _bevindingen(TTL_DIR / "schoon.ttl", check_id) == []


def test_top004_meldt_afstand_en_put() -> None:
    bevinding = _bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004")[0]

    assert bevinding.details["afstand_m"] == pytest.approx(0.5)
    assert bevinding.details["put"] == "B"
    assert bevinding.details["zijde"] == "eindpunt"


def test_top005_meldt_beide_putten_een_keer() -> None:
    bevindingen = _bevindingen(TTL_DIR / "top005_dubbele_put.ttl", "TOP-005")

    # Een paar levert een melding, niet twee spiegelbeelden.
    assert len(bevindingen) == 1
    assert bevindingen[0].details["object2_label"] == "B2"
    assert bevindingen[0].details["afstand_m"] == pytest.approx(0.1)


def test_drempel_uit_de_config_bepaalt_de_uitkomst(tmp_path: Path) -> None:
    ruim = tmp_path / "ruim.toml"
    ruim.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\nsnapping_tolerantie_m = 1.0\n",
        encoding="utf-8",
    )

    # Met de standaardtolerantie van 0,10 m is de streng niet gesnapt;
    # met 1,00 m valt hij ruim binnen de marge.
    assert len(_bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004")) == 1
    assert (
        _bevindingen(TTL_DIR / "top004_niet_gesnapt.ttl", "TOP-004", load_check_config(ruim)) == []
    )


def test_dubbele_put_drempel_uit_de_config(tmp_path: Path) -> None:
    streng = tmp_path / "streng.toml"
    streng.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\ndubbele_put_tolerantie_m = 0.05\n",
        encoding="utf-8",
    )

    assert (
        _bevindingen(TTL_DIR / "top005_dubbele_put.ttl", "TOP-005", load_check_config(streng)) == []
    )


def test_juinen_voorbeeld_levert_verklaarbare_bevindingen(juinen: GwswDataset) -> None:
    context = CheckContext(dataset=juinen, config=load_check_config())
    run = run_checks(context, TOP_IDS)
    per_check = {outcome.check_id: _labels(outcome.findings) for outcome in run.outcomes}

    # Kolk "75" hangt aan een kolkaansluitleiding en is dus niet losliggend;
    # leiding "13" eindigt niet op een put. De overige TOP-checks zijn schoon.
    assert per_check["TOP-001"] == []
    assert per_check["TOP-003"] == ["13"]
    assert per_check["TOP-002"] == []
    assert per_check["TOP-004"] == []
    assert per_check["TOP-005"] == []
    assert per_check["TOP-012"] == []


def test_put_aan_alleen_een_persleiding_is_niet_losliggend() -> None:
    """TOP-001 vraagt of er enige streng aansluit, niet of er vrijverval aansluit.

    Zou alleen op vrijvervalleidingen gekeken worden, dan zou elke put van de
    drukriolering als losliggend gelden; in De Wolden en Hoogeveen zijn dat er duizenden.
    """
    bevindingen = _bevindingen(TTL_DIR / "top001_put_aan_persleiding.ttl", "TOP-001")

    assert _labels(bevindingen) == ["LOS"]


def _uitslag(bestand: str, check_id: str):
    """Draait een enkele check op een fixture en geeft de hele uitslag terug."""
    dataset = load_dataset(TTL_DIR / bestand, [])
    context = CheckContext(dataset=dataset, config=load_check_config())
    return run_checks(context, [check_id]).outcomes[0]


def test_compartimentduplicaat_valt_voor_de_topologiechecks_weg() -> None:
    """Issue #85: `K0001  c2` en `M0003  c1` zijn samengevoegd, de rest blijft staan.

    De twee groepen die overblijven tonen waar de dedup ophoudt: `V0002  c2` ligt 0,50 m
    van zijn naamgenoot -- buiten de dubbele-put-tolerantie -- en de twee putten `DUB`
    dragen geen postfix. Beide horen gewoon gemeld te worden.
    """
    losliggend = _bevindingen(TTL_DIR / "top005_compartimentduplicaat.ttl", "TOP-001")
    dubbel = _bevindingen(TTL_DIR / "top005_compartimentduplicaat.ttl", "TOP-005")

    assert _labels(losliggend) == ["DUB", "V0002  c2"]
    assert _labels(dubbel) == ["DUB"]


def test_het_postfixloze_origineel_wint_en_houdt_de_leiding() -> None:
    """`M0003` blijft over, ook al hangt de leiding administratief aan `M0003  c1`.

    De leiding eindigt op de plek van het duplicaat. Zou de dedup het origineel laten
    vallen, dan bleef de melding staan met de andere knoop erin; zou zij de leiding niet
    op de overgebleven knoop laten snappen, dan werd het origineel alsnog losliggend.
    """
    uitslag = _uitslag("top005_compartimentduplicaat.ttl", "TOP-001")

    assert "M0003" not in _labels(uitslag.findings)
    # Dertien knopen in de fixture, twee samengevoegd.
    assert uitslag.examined == 11


def test_de_samengevoegde_duplicaten_staan_in_de_toelichting() -> None:
    uitslag = _uitslag("top005_compartimentduplicaat.ttl", "TOP-005")

    assert any("2 knopen" in note and "c<n>" in note for note in uitslag.notes), uitslag.notes


def test_zonder_duplicaten_zwijgt_de_toelichting() -> None:
    assert _uitslag("top005_dubbele_put.ttl", "TOP-005").notes == []


def test_samenvoegen_kan_een_strengeinde_zijn_aansluiting_kosten() -> None:
    """De prijs van de dedup, in het venster tussen de twee toleranties in.

    `dubbele_put_tolerantie_m` (0,30 m) is drie keer zo ruim als `snapping_tolerantie_m`
    (0,10 m). `W0004  c2` ligt op 0,20 m van de winnaar: wel samengevoegd, maar te ver om
    het eind van streng '6' nog op te vangen. Die streng houdt dus nog maar een zijde en
    dat is precies wat TOP-003 hoort te melden -- niet stil, want de toelichting van
    TOP-002 en TOP-003 noemt de samenvoeging en beide toleranties.
    """
    pad = TTL_DIR / "top003_dedup_buiten_snapping.ttl"
    een_put = _uitslag("top003_dedup_buiten_snapping.ttl", "TOP-003")

    assert _labels(een_put.findings) == ["6"]
    assert _bevindingen(pad, "TOP-002") == []
    # De winnaar zelf blijft aangesloten en het duplicaat is geen dubbele put meer.
    assert _bevindingen(pad, "TOP-001") == []
    assert _bevindingen(pad, "TOP-005") == []
    assert any("1 knoop" in note and "0,1" in note.replace(".", ",") for note in een_put.notes), (
        een_put.notes
    )


def test_die_melding_komt_van_de_dedup_en_niet_van_de_geometrie(tmp_path: Path) -> None:
    """Met een krappere dubbele-put-tolerantie voegt niets samen en zwijgt TOP-003.

    Hetzelfde bestand, alleen de drempel verschilt: op 0,05 m valt `W0004  c2` buiten de
    samenvoeging, blijft hij een eigen put en houdt streng '6' zijn twee zijden. Dat pint
    de oorzaak van de melding hierboven op de dedup vast en niet op de fixture.
    """
    krap = tmp_path / "krap.toml"
    krap.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\ndubbele_put_tolerantie_m = 0.05\n",
        encoding="utf-8",
    )
    pad = TTL_DIR / "top003_dedup_buiten_snapping.ttl"

    assert _bevindingen(pad, "TOP-003", load_check_config(krap)) == []
    assert _bevindingen(pad, "TOP-002", load_check_config(krap)) == []
    assert _bevindingen(pad, "TOP-001", load_check_config(krap)) == []


def test_de_toelichting_belooft_niet_dat_het_duplicaat_elders_gemeld_wordt() -> None:
    """TOP-014/015/016 rekenen niets van het duplicaat bij het origineel op.

    Een multipart-geometrie of een vijfde streng op het duplicaat verdwijnt met de knoop
    uit de populatie; de toelichting hoort dat te zeggen en niet te beloven dat het
    gebrek op het origineel opduikt.
    """
    notities = _uitslag("top005_compartimentduplicaat.ttl", "TOP-015").notes

    assert any("niet getoetst" in note for note in notities), notities
    assert not any("op het origineel gemeld" in note for note in notities), notities


def test_streng_op_een_hulpstuk_met_telbare_functie_meldt_niet() -> None:
    """Issue #89: een T-stuk is een geldig strengeinde, een afsluitstuk niet.

    Streng '2' ligt tussen twee T-stukken en streng '1' tussen een put en een T-stuk;
    allebei goed. Wat overblijft is de echte snapmisser: streng '4' ligt los in het veld
    (TOP-002) en streng '3' heeft aan de andere zijde alleen een afsluitstuk, dat geen
    functie met een aantal leidingen draagt en dus niet als eind telt (TOP-003).
    """
    pad = TTL_DIR / "top002_streng_op_hulpstuk.ttl"

    assert _labels(_bevindingen(pad, "TOP-002")) == ["4"]
    assert _labels(_bevindingen(pad, "TOP-003")) == ["3"]


def test_het_hulpstukgebrek_blijft_bij_top022() -> None:
    """Dezelfde T-stukken missen leidingen; TOP-022 draagt dat gebrek onverkort."""
    bevindingen = _bevindingen(TTL_DIR / "top002_streng_op_hulpstuk.ttl", "TOP-022")

    assert _labels(bevindingen) == ["T1", "T2"]


def test_de_hulpstukregel_staat_in_de_toelichting() -> None:
    """Stilte zou lezen als 'elk eind is aan een put getoetst'."""
    uitslag = _uitslag("top002_streng_op_hulpstuk.ttl", "TOP-002")

    assert any("hulpstuk" in note and "TOP-022" in note for note in uitslag.notes), uitslag.notes


def test_top022_telt_richtingen_en_niet_strengen() -> None:
    """T3 heeft vier strengen maar drie richtingen (een dubbel gelegd) en zwijgt; T1 meldt."""
    pad = TTL_DIR / "top022_hulpstuk_te_weinig.ttl"
    bevindingen = _bevindingen(pad, "TOP-022")

    assert _labels(bevindingen) == ["T1"]
    assert bevindingen[0].details["verwacht"] == 3
    assert bevindingen[0].details["aangesloten"] == 2
    assert bevindingen[0].details["functie"] == "VerbindenVanDrieLeidingen"
    assert bevindingen[0].details["strengen"] == "1, 2"
    assert _bevindingen(pad, "TOP-023") == []


def test_top023_meldt_een_t_stuk_met_vier_richtingen() -> None:
    pad = TTL_DIR / "top023_hulpstuk_te_veel.ttl"
    bevindingen = _bevindingen(pad, "TOP-023")

    assert _labels(bevindingen) == ["T2"]
    assert bevindingen[0].details["aangesloten"] == 4
    assert _bevindingen(pad, "TOP-022") == []


def test_hulpstukchecks_verantwoorden_de_klassen_zonder_aantal() -> None:
    """Afsluitstuk A1 draagt geen functie met een aantal: buiten de toets, wel geteld."""
    dataset = load_dataset(TTL_DIR / "top022_hulpstuk_te_weinig.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())
    outcome = run_checks(context, ["TOP-022"]).outcomes[0]

    assert outcome.examined == 3
    assert any("1 Afsluitstuk" in note for note in outcome.notes), outcome.notes
