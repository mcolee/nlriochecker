"""Tests voor de meetkundige TOP-checks op fixtures met precies een defect."""

from __future__ import annotations

from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import load_dataset
from shapely.geometry import Point

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, Finding, run_checks
from nlriochecker.checks.meetkunde import (
    coords_of,
    coords_van,
    distinct_coords,
    unieke_coords_van,
)
from nlriochecker.checks.topologie import _nabijheid

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

MEETKUNDIGE_IDS = [
    "TOP-006",
    "TOP-007",
    "TOP-008",
    "TOP-009",
    "TOP-010",
    "TOP-011",
    "TOP-013",
    "TOP-014",
    "TOP-015",
    "TOP-016",
    "TOP-017",
    "TOP-018",
    "TOP-019",
    "TOP-021",
]


def fixtureconfig() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten.

    De fixtures spelen zich af rond (1000, 2000): een klein, leesbaar assenstelsel
    dat niet in het echte RD-vlak ligt. TOP-009 zou daar zonder meer op aanslaan.
    Dat het bereik hier verzet kan worden is precies waar de configureerbaarheid
    voor is; de standaardwaarden blijven het echte RD-bereik.
    """
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def bevindingen(pad: Path, check_id: str, config: CheckConfig | None = None) -> list[Finding]:
    """Draait een enkele check op een fixture."""
    dataset = load_dataset(pad, [])
    context = CheckContext(dataset=dataset, config=config or fixtureconfig())
    return run_checks(context, [check_id]).outcomes[0].findings


def labels(gevonden: list[Finding]) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in gevonden)


@pytest.mark.parametrize(
    ("bestand", "check_id", "verwachte_labels"),
    [
        ("top006_overlappende_streng.ttl", "TOP-006", ["1"]),
        ("top007_nul_lengte.ttl", "TOP-007", ["2"]),
        ("top008_boog.ttl", "TOP-008", ["1"]),
        ("top009_buiten_rd.ttl", "TOP-009", ["1", "B"]),
        ("top010_buffer_kruising.ttl", "TOP-010", ["1"]),
        ("top011_hartlijnkruising.ttl", "TOP-011", ["1"]),
        ("top013_parallel.ttl", "TOP-013", ["1", "2", "3"]),
        ("top014_vijf_strengen.ttl", "TOP-014", ["A"]),
        ("top015_multipart.ttl", "TOP-015", ["1"]),
        ("top016_ongeldige_geometrie.ttl", "TOP-016", ["1"]),
        ("top017_zelfkruisend.ttl", "TOP-017", ["1"]),
        ("top018_spike.ttl", "TOP-018", ["1"]),
        ("top019_pseudoknoop.ttl", "TOP-019", ["B"]),
        ("top019_pseudoknoop_hulpstuk.ttl", "TOP-019", ["T1"]),
        ("top021_put_op_streng.ttl", "TOP-021", ["C"]),
    ],
)
def test_defect_wordt_gevonden(bestand: str, check_id: str, verwachte_labels: list[str]) -> None:
    gevonden = bevindingen(TTL_DIR / bestand, check_id)

    assert labels(gevonden) == verwachte_labels
    assert {finding.check_id for finding in gevonden} == {check_id}


@pytest.mark.parametrize("check_id", MEETKUNDIGE_IDS)
def test_schone_fixture_geeft_geen_bevinding(check_id: str) -> None:
    assert bevindingen(TTL_DIR / "schoon.ttl", check_id) == []


def test_top006_meldt_de_overlaplengte() -> None:
    bevinding = bevindingen(TTL_DIR / "top006_overlappende_streng.ttl", "TOP-006")[0]

    assert bevinding.details["overlaplengte_m"] == pytest.approx(50.0, abs=0.2)
    assert bevinding.details["object2_label"] == "2"


def test_top006_meldt_alleen_binnen_de_twee_drempels() -> None:
    """Issue #100: samenvallen binnen 2 cm over minstens 2 m.

    De fixture legt drie paren naast elkaar die alleen in afstand en samenvallengte
    verschillen. Paar 2 toetst de minimumlengte (1,5 m op 1 cm), paar 3 de tolerantie
    (10 m op 4 cm); allebei meldden ze onder de oude 0,05 m / 1,0 m nog wel.
    """
    gevonden = bevindingen(TTL_DIR / "top006_drempels.ttl", "TOP-006")

    assert labels(gevonden) == ["D1a"], [
        (finding.object_label, finding.details.get("object2_label")) for finding in gevonden
    ]
    assert gevonden[0].details["object2_label"] == "D1b"


def test_top007_noemt_de_nul_lengte() -> None:
    bevinding = bevindingen(TTL_DIR / "top007_nul_lengte.ttl", "TOP-007")[0]

    assert "geen verloop" in bevinding.message


def test_top008_meldt_de_afwijking() -> None:
    bevinding = bevindingen(TTL_DIR / "top008_boog.ttl", "TOP-008")[0]

    assert bevinding.details["afwijking_m"] == pytest.approx(2.0, abs=0.01)
    assert bevinding.details["tussenpunten"] == 1


def test_top009_buiten_het_standaard_rd_bereik() -> None:
    # Met de standaardwaarden liggen de fixturecoordinaten zelf al buiten RD; dat
    # de check daarop aanslaat legt vast dat het bereik echt getoetst wordt.
    standaard = bevindingen(TTL_DIR / "schoon.ttl", "TOP-009", load_check_config())

    assert standaard
    assert all("RD-bereik" in finding.message for finding in standaard)


def test_top009_meldt_ook_wat_er_niet_getoetst_is() -> None:
    dataset = load_dataset(TTL_DIR / "top009_buiten_rd.ttl", [])
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    outcome = run_checks(context, ["TOP-009"]).outcomes[0]

    assert any("beheergebied" in note for note in outcome.notes)


def test_top010_slaat_niet_aan_zonder_maatvoering() -> None:
    # Dezelfde kruising, maar zonder diameter is er geen buis om te bufferen.
    assert bevindingen(TTL_DIR / "top011_hartlijnkruising.ttl", "TOP-010") == []


def test_top013_noemt_alle_parallelle_strengen() -> None:
    bevinding = bevindingen(TTL_DIR / "top013_parallel.ttl", "TOP-013")[0]

    assert bevinding.details["aantal"] == 3
    assert bevinding.details["maximum"] == 2


def test_top014_telt_de_aansluitingen() -> None:
    bevinding = bevindingen(TTL_DIR / "top014_vijf_strengen.ttl", "TOP-014")[0]

    assert bevinding.details["aantal"] == 5


def test_top018_meldt_de_scherpste_hoek() -> None:
    bevinding = bevindingen(TTL_DIR / "top018_spike.ttl", "TOP-018")[0]

    # Terugkeren en weer verder lopen levert twee scherpe knikken op: een bij het
    # keerpunt en een bij het punt waar de lijn de eerdere richting weer oppakt.
    assert bevinding.details["spikes"] == 2
    assert "graden" in bevinding.message


def test_top019_herleidt_ook_via_een_hulpstuk() -> None:
    """Issue #88: een T-stuk is geen netwerkknoop, maar wel een functieloze knoop.

    `verbonden_knopen()` herleidt elk strengeinde naar de rol `netwerkknopen`, en een
    hulpstuk zit daar niet in; zonder terugval op de rauwe koppeling bleef de index per
    constructie leeg en meldde de check nul. T2 staat ernaast om te tonen dat de
    kenmerkvergelijking onverkort geldt: ongelijke diameter is geen pseudo-knoop.
    """
    gevonden = bevindingen(TTL_DIR / "top019_pseudoknoop_hulpstuk.ttl", "TOP-019")

    assert labels(gevonden) == ["T1"]
    assert gevonden[0].details["strengen"] == ["1", "2"]


def test_top019_telt_een_streng_op_zichzelf_niet_als_twee() -> None:
    """Een streng met beide einden op dezelfde knoop is een streng, geen pseudo-knoop.

    Dezelfde grens als in `_bouw_hulpstuktelling` en `_bouw_aansluitingen`: zonder
    ontdubbeling staat streng 5 twee keer in de lijst van T3 en zou de check hem met
    zichzelf vergelijken -- altijd gelijk, dus altijd een melding.
    """
    gevonden = bevindingen(TTL_DIR / "top019_pseudoknoop_hulpstuk.ttl", "TOP-019")

    assert "T3" not in labels(gevonden)


def test_top019_draait_niet_zonder_functieloze_klassen() -> None:
    config = fixtureconfig()
    config.klassen.functieloze_knoop = []

    dataset = load_dataset(TTL_DIR / "top019_pseudoknoop.ttl", [])
    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["TOP-019"]).outcomes[0]

    assert outcome.findings == []
    assert any("niet gedraaid" in note for note in outcome.notes)


def test_top021_meldt_de_streng_waarlangs_de_put_ligt() -> None:
    bevinding = bevindingen(TTL_DIR / "top021_put_op_streng.ttl", "TOP-021")[0]

    assert bevinding.details["streng"] == "1"
    assert bevinding.details["afstand_m"] == pytest.approx(0.1, abs=0.01)


def test_top021_meldt_niets_bij_een_echt_losliggende_put() -> None:
    # TOP-001 vindt deze put wel; TOP-021 is de verfijning en hoort te zwijgen.
    assert bevindingen(TTL_DIR / "top001_losliggende_put.ttl", "TOP-021") == []
    assert bevindingen(TTL_DIR / "top001_losliggende_put.ttl", "TOP-001") != []


def test_paarmeldingen_dragen_het_tweede_object() -> None:
    """De uitvoer heeft de URI van de tegenpartij nodig, niet alleen haar label.

    TOP-005, TOP-006, TOP-010 en TOP-011 melden over precies twee objecten; zonder
    de tweede URI is de melding in CSV en GIS niet aan beide kanten te koppelen.
    """
    bevinding = bevindingen(TTL_DIR / "top011_hartlijnkruising.ttl", "TOP-011")[0]

    assert bevinding.details["object2_uri"].startswith("http")
    assert bevinding.details["object2_label"]


def _dataset_en_bevindingen(bestand: str, check_id: str):
    """De dataset plus de bevindingen van een check erop."""
    dataset = load_dataset(TTL_DIR / bestand, [])
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    return dataset, run_checks(context, [check_id]).outcomes[0].findings


def test_top011_zet_het_snijpunt_als_foutlocatie() -> None:
    """De kruising zit op het snijpunt, niet op het midden van een van de strengen.

    De coordinaat stond tot nu toe in de meldingtekst; als kolom en geometrie is
    hij bruikbaar, in een zin is hij dat niet.
    """
    dataset, gevonden = _dataset_en_bevindingen("top011_hartlijnkruising.ttl", "TOP-011")
    bevinding = gevonden[0]

    x, y = bevinding.details["foutlocatie"]
    eigen = dataset.conduits[bevinding.object_uri].line
    ander = dataset.conduits[bevinding.details["object2_uri"]].line

    assert eigen.distance(Point(x, y)) == pytest.approx(0.0, abs=1e-6)
    assert ander.distance(Point(x, y)) == pytest.approx(0.0, abs=1e-6)
    assert "(" not in bevinding.message


def test_top010_zet_de_foutlocatie_tussen_de_twee_strengen() -> None:
    """Het conflict zit waar de buizen elkaar naderen, niet op een strengmidden."""
    dataset, gevonden = _dataset_en_bevindingen("top010_buffer_kruising.ttl", "TOP-010")
    bevinding = gevonden[0]

    punt = Point(*bevinding.details["foutlocatie"])
    eigen = dataset.conduits[bevinding.object_uri].line
    ander = dataset.conduits[bevinding.details["object2_uri"]].line

    assert eigen.distance(punt) <= bevinding.details["afstand_m"] + 1e-6
    assert ander.distance(punt) <= bevinding.details["afstand_m"] + 1e-6


# Issue #82: TOP-006, TOP-010 en TOP-011 toetsen alleen paren waarvan beide leidingen een
# vrijvervalrioolleiding of een duiker zijn. De fixture legt per check drie gelijkvormige
# paren naast elkaar -- met een drain, een aansluitleiding en een duiker -- zodat de
# populatiegrens het enige verschil is.
@pytest.mark.parametrize(
    ("check_id", "paar"),
    [
        ("TOP-006", {"W3", "OverDuiker"}),
        ("TOP-010", {"V3", "KruisDuiker"}),
        ("TOP-011", {"V3", "KruisDuiker"}),
    ],
)
def test_alleen_het_duikerpaar_valt_binnen_de_scope(check_id: str, paar: set[str]) -> None:
    gevonden = bevindingen(TTL_DIR / "top_nabijheid_scope.ttl", check_id)

    assert len(gevonden) == 1, [
        (finding.object_label, finding.details.get("object2_label")) for finding in gevonden
    ]
    bevinding = gevonden[0]
    assert {bevinding.object_label, bevinding.details["object2_label"]} == paar


@pytest.mark.parametrize(
    ("check_id", "paar"),
    [
        ("TOP-006", {"W3", "OverDuiker"}),
        ("TOP-010", {"V3", "KruisDuiker"}),
        ("TOP-011", {"V3", "KruisDuiker"}),
    ],
)
def test_de_populatie_is_de_eigen_rol_en_niet_haar_doorsnede_met_de_leidingen(
    check_id: str, paar: set[str]
) -> None:
    """`[klassen] streng` en `[klassen] nabijheidsleiding` zijn los configureerbaar.

    Versmalt een project `streng` tot de vrijvervalleiding, dan valt de duiker uit de
    leidingenrol -- maar niet uit `nabijheidsleiding`. De populatie van TOP-006,
    TOP-010 en TOP-011 is die rol zelf, dus het duikerpaar hoort te blijven melden, en
    de verantwoordingsregel hoort over diezelfde populatie te tellen: totaal min buiten
    is de populatie, hier de zes vrijvervalleidingen plus de twee duikers.
    """
    config = fixtureconfig()
    config.klassen.streng = ["VrijvervalRioolleiding"]

    dataset = load_dataset(TTL_DIR / "top_nabijheid_scope.ttl", [])
    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, [check_id]).outcomes[0]
    gevonden = outcome.findings

    assert len(gevonden) == 1, [
        (finding.object_label, finding.details.get("object2_label")) for finding in gevonden
    ]
    bevinding = gevonden[0]
    assert {bevinding.object_label, bevinding.details["object2_label"]} == paar
    assert any("0 van de 8 leidingen" in note for note in outcome.notes), outcome.notes


@pytest.mark.parametrize("check_id", ["TOP-006", "TOP-010", "TOP-011"])
def test_de_toelichting_telt_de_leidingen_buiten_de_scope(check_id: str) -> None:
    """Stilte leest als "alles gecontroleerd"; de versmalling hoort in het rapport."""
    dataset = load_dataset(TTL_DIR / "top_nabijheid_scope.ttl", [])
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    outcome = run_checks(context, [check_id]).outcomes[0]

    # Vier van de twaalf leidingen zijn een drain of een aansluitleiding.
    assert any("4 van de 12 leidingen" in note for note in outcome.notes), outcome.notes
    assert any("VrijvervalRioolleiding, Duiker" in note for note in outcome.notes), outcome.notes


def test_top006_zet_de_foutlocatie_op_het_overlappende_deel() -> None:
    dataset, gevonden = _dataset_en_bevindingen("top006_overlappende_streng.ttl", "TOP-006")
    bevinding = gevonden[0]

    punt = Point(*bevinding.details["foutlocatie"])

    assert dataset.conduits[bevinding.object_uri].line.distance(punt) == pytest.approx(
        0.0, abs=1e-6
    )


# Issue #123: de coordinaten en de buffers worden per context een keer bepaald in plaats
# van per check opnieuw. Een cache mag de uitkomst niet raken, dus de tabel moet letterlijk
# geven wat de losse functies geven -- en hij moet werkelijk geraakt worden, anders is het
# geen cache maar een omweg.
GEOMETRIEFIXTURES = [
    "schoon.ttl",
    "top006_overlappende_streng.ttl",
    "top007_nul_lengte.ttl",
    "top008_boog.ttl",
    "top016_ongeldige_geometrie.ttl",
    "top017_zelfkruisend.ttl",
    "top018_spike.ttl",
]


def _context_van(bestand: str) -> CheckContext:
    """Een context over een fixture, zonder een check te draaien."""
    return CheckContext(dataset=load_dataset(TTL_DIR / bestand, []), config=fixtureconfig())


@pytest.mark.parametrize("bestand", GEOMETRIEFIXTURES)
def test_de_coordinatentabel_geeft_hetzelfde_als_de_losse_functies(bestand: str) -> None:
    context = _context_van(bestand)
    # Eerst de checks, zodat de tabel staat zoals een echte run hem achterlaat; de
    # vergelijking gaat dus over de gevulde tabel en niet alleen over het bijvullen.
    run_checks(context, MEETKUNDIGE_IDS)

    for conduit in context.dataset.conduits.values():
        assert coords_van(context, conduit.uri, conduit.line) == tuple(coords_of(conduit.line))
        assert unieke_coords_van(context, conduit.uri, conduit.line) == tuple(
            distinct_coords(conduit.line)
        )


def test_de_coordinatentabel_wordt_werkelijk_geraakt() -> None:
    """Een tweede aanroep geeft hetzelfde object terug; er wordt niets opnieuw gebouwd."""
    context = _context_van("top018_spike.ttl")
    conduit = next(iter(context.dataset.conduits.values()))

    coords = coords_van(context, conduit.uri, conduit.line)
    uniek = unieke_coords_van(context, conduit.uri, conduit.line)

    assert coords_van(context, conduit.uri, conduit.line) is coords
    assert unieke_coords_van(context, conduit.uri, conduit.line) is uniek


def test_de_buffer_van_een_streng_wordt_hergebruikt_per_tolerantie() -> None:
    """Stap 3 van issue #123: een buffer per (streng, tolerantie), niet per paar."""
    context = _context_van("top006_overlappende_streng.ttl")
    nabijheid = _nabijheid(context)
    conduit = nabijheid.conduits[0]

    eerste = nabijheid.buffer_van(conduit, 0.02)

    assert nabijheid.buffer_van(conduit, 0.02) is eerste
    assert nabijheid.buffer_van(conduit, 0.05) is not eerste
