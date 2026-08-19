"""Tests voor de ATTR-, HGT-, RVZ-, ADM- en BTR-checks op kleine fixtures.

Elke fixture bevat precies een ingebouwd defect, maar in de HGT-categorie hangen de
kenmerken onderling samen: een BOB boven het deksel betekent per definitie ook te
weinig gronddekking en een buiskruin boven maaiveld. Deze tests kijken daarom per
check-ID of *die* check het defect vindt, en per schone fixture of geen enkele
check van de categorie iets meldt.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import REGISTRY, CheckContext, CheckOutcome, run_checks
from nlriochecker.checks.verbanden import deelstelsel_ids
from nlriochecker.dataset import GWSW, Aspect, load_dataset, markeer_vulwaarden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def fixtureconfig() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def context_voor(bestand: str, config: CheckConfig) -> CheckContext:
    """Laadt een fixture zoals `toetsrun` dat doet: met de vulwaarde-leesregel erop."""
    dataset = markeer_vulwaarden(
        load_dataset(TTL_DIR / bestand),
        config.vulwaarden.hoogte_kenmerken,
        config.vulwaarden.hoogte_band_m,
    )
    return CheckContext(dataset=dataset, config=config)


def uitkomst(bestand: str, check_id: str, config: CheckConfig | None = None) -> CheckOutcome:
    """Draait een enkele check op een fixture."""
    context = context_voor(bestand, config or fixtureconfig())
    return run_checks(context, [check_id]).outcomes[0]


def labels(outcome: CheckOutcome) -> list[str]:
    """De labels van de gevonden objecten, gesorteerd."""
    return sorted(finding.object_label for finding in outcome.findings)


def ids_van(groep: str) -> list[str]:
    """Alle geregistreerde check-ID's van een categorie."""
    return [check_id for check_id in sorted(REGISTRY) if check_id.startswith(f"{groep}-")]


DEFECTEN = [
    ("attr001_diameter_bij_materiaal.ttl", "ATTR-001", ["1"]),
    ("attr002_kleine_diameter.ttl", "ATTR-002", ["1"]),
    ("attr003_pvc_te_vroeg.ttl", "ATTR-003", ["1"]),
    ("attr004_rond_ongelijk.ttl", "ATTR-004", ["1"]),
    ("attr005_centimeters.ttl", "ATTR-005", ["1", "1"]),
    ("attr006_te_grote_streng.ttl", "ATTR-006", ["1"]),
    ("attr006_twee_te_kleine_putten.ttl", "ATTR-006", ["1", "1"]),
    ("attr007_toekomstig_jaar.ttl", "ATTR-007", ["1"]),
    ("attr008_lange_streng.ttl", "ATTR-008", ["1"]),
    ("attr009_lengte_wijkt_af.ttl", "ATTR-009", ["1"]),
    ("attr010_materiaal_put.ttl", "ATTR-010", ["1"]),
    ("attr012_metselwerk_rond.ttl", "ATTR-012", ["1"]),
    ("attr013_vulwaarde_hoogte.ttl", "ATTR-013", ["1", "A", "B"]),
    ("hgt004_bob_boven_deksel.ttl", "HGT-004", ["1"]),
    ("hgt005_tegenverhang_licht.ttl", "HGT-005", ["1"]),
    ("hgt006_tegenverhang_fors.ttl", "HGT-006", ["1"]),
    ("hgt007_te_weinig_verhang.ttl", "HGT-007", ["1"]),
    ("hgt008_extreem_verhang.ttl", "HGT-008", ["1"]),
    ("hgt009_bob_sprong.ttl", "HGT-009", ["B"]),
    ("hgt010_diameterverjonging.ttl", "HGT-010", ["2"]),
    ("hgt011_drempel_onder_bob.ttl", "HGT-011", ["B"]),
    ("hgt012_putdiepte.ttl", "HGT-012", ["B"]),
    ("hgt013_gronddekking.ttl", "HGT-013", ["1", "1"]),
    ("hgt014_maaiveldverloop.ttl", "HGT-014", ["1"]),
    ("hgt015_putbodem_te_hoog.ttl", "HGT-015", ["B"]),
    ("hgt016_bob_boven_bodem.ttl", "HGT-016", ["1", "1"]),
    ("hgt017_z_wijkt_af.ttl", "HGT-017", ["1", "1"]),
    ("hgt018_buiskruin_boven_maaiveld.ttl", "HGT-018", ["1"]),
    ("rvz001_losse_overstort.ttl", "RVZ-001", ["O"]),
    ("rvz002_drempel_zonder_niveau.ttl", "RVZ-002", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-002", ["O"]),
    ("rvz003_drempel_zonder_breedte.ttl", "RVZ-003", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-003", ["O"]),
    ("rvz004_overstort_zonder_water.ttl", "RVZ-004", ["O"]),
    ("rvz005_overstort_op_hemelwater.ttl", "RVZ-005", ["O"]),
    ("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006", ["A"]),
    ("rvz007_bbb_zonder_berging.ttl", "RVZ-007", ["BBB"]),
    ("rvz008_bbb_zonder_lediging.ttl", "RVZ-008", ["BBB"]),
    ("rvz009_bbb_zonder_nooduitlaat.ttl", "RVZ-009", ["BBB"]),
    ("rvz010_interne_overstort.ttl", "RVZ-010", ["2"]),
    ("rvz011_te_weinig_waking.ttl", "RVZ-011", ["O"]),
    ("adm002_dubbel_label.ttl", "ADM-002", ["A", "A"]),
    ("adm006_vervallen_object.ttl", "ADM-006", ["1"]),
    ("adm007_overstort_zonder_functie.ttl", "ADM-007", ["O"]),
    ("adm008_losse_compartimenten.ttl", "ADM-008", ["B"]),
    ("adm009_leiding_aan_put.ttl", "ADM-009", ["1"]),
    ("btr006_afgeronde_bobs.ttl", "BTR-006", ["b0"]),
]


@pytest.mark.parametrize(("bestand", "check_id", "verwacht"), DEFECTEN)
def test_defect_wordt_gevonden(bestand: str, check_id: str, verwacht: list[str]) -> None:
    outcome = uitkomst(bestand, check_id)

    assert labels(outcome) == verwacht


def test_elk_defect_heeft_een_eigen_fixture() -> None:
    # Bewaakt dat er geen check-ID stilzwijgend zonder fixture blijft. HGT-001 t/m
    # HGT-003 en de EXT-checks hebben externe bronnen nodig en staan in blok C;
    # BTR-001 t/m BTR-005 zijn skeletten. ADM-003 heeft geen defectfixture maar wel
    # een eigen test, want zonder projectpatroon is er geen defect te bouwen.
    gedekt = {check_id for _, check_id, _ in DEFECTEN} | {"ADM-003"}
    verwacht = {
        *ids_van("ATTR"),
        *[f"HGT-{nummer:03d}" for nummer in range(4, 19)],
        *ids_van("RVZ"),
        *ids_van("ADM"),
        "BTR-006",
    }

    assert verwacht - gedekt == set()


@pytest.mark.parametrize(
    ("bestand", "groep"),
    [
        ("attr_schoon.ttl", "ATTR"),
        ("hgt_schoon.ttl", "HGT"),
        ("rvz_schoon.ttl", "RVZ"),
    ],
)
def test_schone_fixture_geeft_geen_bevinding(bestand: str, groep: str) -> None:
    run = run_checks(context_voor(bestand, fixtureconfig()), ids_van(groep))

    gemeld = {outcome.check_id: labels(outcome) for outcome in run.outcomes if outcome.findings}
    assert gemeld == {}


def test_attr013_meldt_een_keer_per_object_met_de_kenmerken() -> None:
    outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", "ATTR-013")
    per_label = {bevinding.object_label: bevinding for bevinding in outcome.findings}

    assert per_label["1"].details["kenmerken"] == ["BobBeginpuntLeiding"]
    assert per_label["1"].details["waarden"] == [0.0]
    assert per_label["A"].details["kenmerken"] == ["Maaiveldhoogte"]
    assert outcome.examined == 5  # 3 netwerkknopen + 2 strengen
    # De band staat in de toelichting zoals de code hem opmaakt (`:g`), niet in een
    # van twee toegestane schrijfwijzen: dan pint de assertie er geen.
    assert any("Als vulwaarde gold |waarde| <= 0.01 m" in note for note in outcome.notes), (
        outcome.notes
    )


def test_attr013_noemt_twee_kenmerken_elk_met_hun_eigen_waarde() -> None:
    """Bij meer dan een vulwaarde blijft de zin lopen en staat het werkwoord in het meervoud.

    De fixture heeft geen object met twee vulwaarden -- put C is er juist de schone
    tegenhanger -- dus die situatie wordt hier op de geladen dataset nagebootst.
    """
    config = fixtureconfig()
    ruw = load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl")
    put = next(node for node in ruw.nodes.values() if node.label == "C")
    nodes = dict(ruw.nodes)
    nodes[put.uri] = replace(
        put,
        maaiveld_aspect=Aspect("Maaiveldhoogte", "0.0"),
        deksel_aspect=Aspect("Putdekselniveau", "0.0"),
    )
    dataset = markeer_vulwaarden(
        replace(ruw, nodes=nodes),
        config.vulwaarden.hoogte_kenmerken,
        config.vulwaarden.hoogte_band_m,
    )

    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["ATTR-013"]).outcomes[0]
    melding = next(f.message for f in outcome.findings if f.object_label == "C")

    assert melding == (
        "Maaiveldhoogte op 0.000 m NAP en Putdekselniveau op 0.000 m NAP vallen binnen de "
        "vulwaardeband van 0.01 m en zijn als niet geregistreerd gelezen in plaats van "
        "als meting."
    )


@pytest.mark.parametrize(
    ("check_id", "toelichting"),
    [
        ("HGT-004", "2 van de 3 putten hebben geen putdekselniveau en geen maaiveldhoogte"),
        ("HGT-014", "Geen enkele van de 2 strengen in deze dataset heeft een maaiveldhoogte"),
    ],
)
def test_hoogtechecks_zwijgen_over_vulwaarden_met_toelichting(
    check_id: str, toelichting: str
) -> None:
    """De hoogtecheck zwijgt over een vulwaarde en zegt in haar toelichting waarom.

    De assertie pint de zin die de stilte verklaart: een toelichting over iets anders
    zou de belofte van deze test niet waarmaken.
    """
    outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", check_id)

    assert labels(outcome) == [], check_id
    assert any(toelichting in note for note in outcome.notes), outcome.notes


def test_attr013_telt_de_vulwaarden_buiten_haar_populatie() -> None:
    """De leesregel raakt meer objecten dan deze check meldt; dat hoort in de toelichting.

    `markeer_vulwaarden` loopt over alle knopen en alle strengen, ATTR-013 meldt de
    netwerkknopen plus de vrijvervalstrengen. Een persleiding of een compartiment houdt
    daardoor een weggezette hoogte die in geen enkele melding terugkomt (BO-27). De
    fixture kent zulke objecten niet, dus ze worden hier op de geladen dataset
    nagebootst: streng 1 en put A krijgen een klasse buiten de populatie.
    """
    config = fixtureconfig()
    ruw = load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl")
    streng = next(conduit for conduit in ruw.conduits.values() if conduit.label == "1")
    put = next(node for node in ruw.nodes.values() if node.label == "A")
    conduits = dict(ruw.conduits)
    conduits[streng.uri] = replace(streng, types=frozenset({f"{GWSW}Persleiding"}))
    nodes = dict(ruw.nodes)
    nodes[put.uri] = replace(put, types=frozenset({f"{GWSW}Compartiment"}))
    dataset = markeer_vulwaarden(
        replace(ruw, conduits=conduits, nodes=nodes),
        config.vulwaarden.hoogte_kenmerken,
        config.vulwaarden.hoogte_band_m,
    )

    context = CheckContext(dataset=dataset, config=config)
    outcome = run_checks(context, ["ATTR-013"]).outcomes[0]

    assert labels(outcome) == ["B"]
    assert any(
        "daarnaast 1 knoop en 1 streng buiten de gemelde populatie" in note
        for note in outcome.notes
    ), outcome.notes


def test_attr013_zegt_dat_de_regel_uit_staat() -> None:
    config = fixtureconfig()
    config.vulwaarden.hoogte_kenmerken = []

    outcome = uitkomst("attr013_vulwaarde_hoogte.ttl", "ATTR-013", config)

    assert outcome.findings == []
    assert any("De vulwaarde-leesregel staat uit" in note for note in outcome.notes)


def test_hgt018_verantwoordt_alle_drie_de_overslagredenen() -> None:
    """`run` heeft BOB, profielmaat en bovenkant nodig; alle drie horen in de notes.

    De fixture levert de eerste twee (put A en B dragen een vulwaarde in het maaiveld,
    streng 1 een vulwaarde in de BOB); de profielmaat wordt hier weggehaald, want geen
    enkele fixture kent een streng zonder maatvoering.
    """
    config = fixtureconfig()
    context = context_voor("attr013_vulwaarde_hoogte.ttl", config)
    conduits = dict(context.dataset.conduits)
    for uri, conduit in conduits.items():
        conduits[uri] = replace(
            conduit,
            aspects=tuple(
                aspect
                for aspect in conduit.aspects
                if aspect.kind not in ("BreedteLeiding", "HoogteLeiding")
            ),
        )
    kaal = CheckContext(dataset=replace(context.dataset, conduits=conduits), config=config)

    notes = run_checks(kaal, ["HGT-018"]).outcomes[0].notes

    assert any("BOB" in note for note in notes)
    assert any("profielmaat" in note for note in notes)
    assert any("bovenkant" in note for note in notes)


def test_attr001_noemt_het_bereik_en_het_materiaal() -> None:
    bevinding = uitkomst("attr001_diameter_bij_materiaal.ttl", "ATTR-001").findings[0]

    assert bevinding.details["materiaal"] == "PVC"
    assert bevinding.details["maat_mm"] == pytest.approx(1000)
    assert bevinding.details["maximum_mm"] == pytest.approx(800)


def test_attr005_noemt_de_vermoedelijke_waarde() -> None:
    bevinding = uitkomst("attr005_centimeters.ttl", "ATTR-005").findings[0]

    assert bevinding.details["waarde_mm"] == pytest.approx(30)
    assert bevinding.details["vermoedelijke_waarde_mm"] == pytest.approx(300)


def test_attr006_onderscheidt_de_twee_zijden() -> None:
    bevindingen = uitkomst("attr006_twee_te_kleine_putten.ttl", "ATTR-006").findings

    assert sorted(b.details["zijde"] for b in bevindingen) == ["beginpunt", "eindpunt"]
    assert sorted(b.details["put"] for b in bevindingen) == ["A", "B"]


def test_attr009_meldt_beide_lengten() -> None:
    bevinding = uitkomst("attr009_lengte_wijkt_af.ttl", "ATTR-009").findings[0]

    assert bevinding.details["administratieve_lengte_m"] == pytest.approx(100.0)
    assert bevinding.details["geometrische_lengte_m"] == pytest.approx(50.0)
    assert bevinding.details["afwijking_procent"] == pytest.approx(50.0)


def test_hgt004_meldt_de_bron_van_het_bovenkantniveau() -> None:
    bevinding = uitkomst("hgt004_bob_boven_deksel.ttl", "HGT-004").findings[0]

    assert bevinding.details["bron"] == "dekselniveau"
    assert bevinding.details["put"] == "A"


def test_hgt004_meldt_dat_het_gwsw_geen_putbodemniveau_kent() -> None:
    outcome = uitkomst("hgt004_bob_boven_deksel.ttl", "HGT-004")

    assert any("Putbodemniveau" in note for note in outcome.notes)


def test_hgt005_en_hgt006_sluiten_elkaar_uit() -> None:
    # Licht tegenverhang mag niet ook als fors gelden, en omgekeerd.
    assert uitkomst("hgt005_tegenverhang_licht.ttl", "HGT-006").findings == []
    assert uitkomst("hgt006_tegenverhang_fors.ttl", "HGT-005").findings == []


def test_hgt011_zwijgt_zonder_drempelobjecten() -> None:
    outcome = uitkomst("hgt_schoon.ttl", "HGT-011")

    assert outcome.findings == []
    assert any("geen enkel `Overstortdrempel`-object" in note for note in outcome.notes)


def test_hgt017_meldt_dat_de_geometrie_plat_is() -> None:
    outcome = uitkomst("hgt_schoon.ttl", "HGT-017")

    assert outcome.findings == []
    assert any("geen enkele strenggeometrie" in note.lower() for note in outcome.notes)


def test_rvz004_zwijgt_zonder_oppervlaktewater() -> None:
    outcome = uitkomst("rvz001_losse_overstort.ttl", "RVZ-004")

    assert outcome.findings == []
    assert any("geen enkel `Oppervlaktewater`-object" in note for note in outcome.notes)


def test_rvz002_zwijgt_bij_een_drempel_met_niveau() -> None:
    assert labels(uitkomst("rvz003_drempel_zonder_breedte.ttl", "RVZ-002")) == []


def test_rvz002_verantwoordt_de_putten_zonder_drempel() -> None:
    outcome = uitkomst("rvz002_overstort_zonder_drempel.ttl", "RVZ-002")

    assert outcome.examined == 1
    assert any("zonder enig `Overstortdrempel`-onderdeel" in note for note in outcome.notes), (
        outcome.notes
    )
    assert any("Overstortput_Overstortdrempel_card" in note for note in outcome.notes)


@pytest.mark.parametrize(
    ("bestand", "check_id", "boodschap"),
    [
        (
            "rvz002_drempel_zonder_niveau.ttl",
            "RVZ-002",
            "De enige overstortdrempel van deze put heeft geen drempelniveau "
            "(`Drempelniveau`) geregistreerd.",
        ),
        (
            "rvz003_drempel_zonder_breedte.ttl",
            "RVZ-003",
            "De enige overstortdrempel van deze put heeft geen drempelbreedte "
            "(`Drempelbreedte`) geregistreerd.",
        ),
    ],
)
def test_overstort_met_drempel_zonder_waarde_meldt_lopend_nederlands(
    bestand: str, check_id: str, boodschap: str
) -> None:
    """De tak 'wel een drempel, geen waarde' had geen test op haar tekst.

    Bij een enkele drempel liep de zin fout ("Geen van de 1 overstortdrempels"), en het
    voltooid deelwoord stond ervoor, waar het bij de breedte niet klopte ("een
    geregistreerd drempelbreedte"). De toelichting noemt nu het bereik zoals de andere
    notities in deze module dat doen.
    """
    outcome = uitkomst(bestand, check_id)

    assert [bevinding.message for bevinding in outcome.findings] == [boodschap]
    assert outcome.notes == ["Bekeken: 1 overstortput in deze dataset (Overstortput, Stuwput)."]


def test_rvz011_meldt_de_waking() -> None:
    bevinding = uitkomst("rvz011_te_weinig_waking.ttl", "RVZ-011").findings[0]

    assert bevinding.details["waking_m"] == pytest.approx(0.10, abs=0.001)
    assert bevinding.details["minimum_m"] == pytest.approx(0.40)


def test_adm002_meldt_wat_er_niet_getoetst_kan_worden() -> None:
    outcome = uitkomst("adm002_dubbel_label.ttl", "ADM-002")

    assert any("bronexport" in note for note in outcome.notes)


def test_adm003_draait_niet_zonder_patroon() -> None:
    outcome = uitkomst("attr_schoon.ttl", "ADM-003")

    assert outcome.findings == []
    assert outcome.examined == 0
    assert any("geen naamgevingspatroon" in note for note in outcome.notes)


def test_adm003_toetst_het_ingestelde_patroon() -> None:
    config = fixtureconfig()
    config.naamgeving.putpatroon = r"^PUT-\d{4}$"

    outcome = uitkomst("attr_schoon.ttl", "ADM-003", config)

    assert labels(outcome) == ["A", "B"]
    assert outcome.findings[0].details["patroon"] == r"^PUT-\d{4}$"


def test_btr006_meldt_het_aandeel_op_het_raster() -> None:
    bevinding = uitkomst("btr006_afgeronde_bobs.ttl", "BTR-006").findings[0]

    assert bevinding.details["kenmerk"] == "BOB-waarden"
    assert bevinding.details["aandeel_procent"] == pytest.approx(100.0)
    assert bevinding.details["aantal"] == 80


def test_btr006_zwijgt_bij_te_weinig_waarnemingen() -> None:
    # Twee BOB's zijn geen reeks; een aandeel van 100% zegt daar niets.
    outcome = uitkomst("hgt_schoon.ttl", "BTR-006")

    assert outcome.findings == []


@pytest.mark.parametrize("check_id", ["BTR-001", "BTR-002", "BTR-003", "BTR-004", "BTR-005"])
def test_btr_skeletten_melden_hun_markering(check_id: str) -> None:
    outcome = uitkomst("attr_schoon.ttl", check_id)

    assert outcome.findings == []
    assert outcome.skeleton == "vereist inwinningsmetagegevens"
    assert any("vereist inwinningsmetagegevens" in note for note in outcome.notes)


def test_rvz006_draagt_hetzelfde_deelstelsel_id_als_de_net_checks() -> None:
    """RVZ-006 en NET-001 melden over hetzelfde deelstelsel.

    Alleen met een gedeeld ID is in rapport en GIS te zien dat het om hetzelfde
    stuk net gaat; anders lijkt het twee losse gebreken.
    """
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl")
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    ids = deelstelsel_ids(context)

    outcome = run_checks(context, ["RVZ-006"]).outcomes[0]

    bevinding = outcome.findings[0]
    assert bevinding.details["cluster_id"] == ids[bevinding.object_uri]


def test_rvz006_zet_het_zwaartepunt_van_het_deelstelsel_als_foutlocatie() -> None:
    """Het gebrek zit in het deelstelsel, niet in de knoop waar de melding aan hangt.

    Op de kaart hoort de melding daarom midden in dat deel te staan.
    """
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl")
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    ids = deelstelsel_ids(context)

    bevinding = run_checks(context, ["RVZ-006"]).outcomes[0].findings[0]

    cluster = ids[bevinding.object_uri]
    punten = [
        dataset.nodes[uri].point
        for uri, deel in ids.items()
        if deel == cluster and dataset.nodes.get(uri) is not None
        if dataset.nodes[uri].point is not None
    ]
    verwacht_x = sum(punt.x for punt in punten) / len(punten)
    verwacht_y = sum(punt.y for punt in punten) / len(punten)
    x, y = bevinding.details["foutlocatie"]

    assert x == pytest.approx(verwacht_x)
    assert y == pytest.approx(verwacht_y)


def test_gedeelde_volledige_context_wordt_hergebruikt() -> None:
    """Anders herrekent elk gebied de karakteristiek van de volledige export.

    De volledige-export-context hangt alleen af van de volledige dataset, de config
    en de onbetrouwbare objecten; die zijn alle drie gebiedsonafhankelijk, dus mag
    hij over gebieden heen gedeeld worden.
    """
    dataset = load_dataset(TTL_DIR / "schoon.ttl")
    config = load_check_config()
    gedeeld = CheckContext(
        dataset=dataset, config=config, volledige_dataset=dataset
    ).volledige_context()

    eerste = CheckContext(
        dataset=dataset,
        config=config,
        volledige_dataset=dataset,
        gedeelde_volledige_context=gedeeld,
    )
    tweede = CheckContext(
        dataset=dataset,
        config=config,
        volledige_dataset=dataset,
        gedeelde_volledige_context=gedeeld,
    )

    assert eerste.volledige_context() is gedeeld
    assert tweede.volledige_context() is gedeeld


def test_de_run_draagt_het_trefferregister_van_zijn_context() -> None:
    """De GeoPackage-schrijver joint de meldingen later op dit register."""
    dataset = load_dataset(TTL_DIR / "schoon.ttl")
    context = CheckContext(dataset=dataset, config=load_check_config())

    run = run_checks(context, ["TOP-001"])

    assert run.treffers is context.treffers
