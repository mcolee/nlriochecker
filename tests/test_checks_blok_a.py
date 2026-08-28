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
from gwsw_orox_helpers.dataset import GWSW, Aspect, load_dataset, markeer_vulwaarden

from nlriochecker.checkconfig import CheckConfig, VerhangStap, load_check_config
from nlriochecker.checks import REGISTRY, CheckContext, CheckOutcome, run_checks
from nlriochecker.checks.administratief import LozeLeidingAanActiefRiool, _LozeKeten
from nlriochecker.checks.verbanden import deelstelsel_ids
from nlriochecker.plausibiliteit import load_plausibility

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def fixtureconfig() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def context_voor(bestand: str, config: CheckConfig) -> CheckContext:
    """Laadt een fixture zoals `toetsrun` dat doet: met de vulwaarde-leesregel erop."""
    dataset = markeer_vulwaarden(
        load_dataset(TTL_DIR / bestand, []),
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
    # Issue #86: het constructietype gaat voor het materiaal. DT (Ø65 PVC) valt binnen het
    # drainagebereik en meldt niet meer; HW (hemelwaterriool, dezelfde maat en hetzelfde
    # materiaal) wel, en DIT (Ø45) valt onder het drainagebereik zelf.
    ("attr001_constructietype_drainage.ttl", "ATTR-001", ["DIT", "HW"]),
    ("attr002_kleine_diameter.ttl", "ATTR-002", ["1"]),
    # De ondergrens is nu stelselafhankelijk (issue #20): G (gemengd, Ø220) valt onder
    # 250 mm, V (vuilwater, Ø220) blijft boven 200 mm en is geen bevinding.
    ("attr002_stelseltype.ttl", "ATTR-002", ["G"]),
    ("attr003_pvc_te_vroeg.ttl", "ATTR-003", ["1"]),
    ("attr004_rond_ongelijk.ttl", "ATTR-004", ["1"]),
    ("attr005_centimeters.ttl", "ATTR-005", ["1", "1"]),
    ("attr006_te_grote_streng.ttl", "ATTR-006", ["1"]),
    ("attr006_twee_te_kleine_putten.ttl", "ATTR-006", ["1", "1"]),
    # Alleen put A (rond, 800x1000) telt; put B (rond, 800x800) en put C (rechthoekig,
    # 800x1000) blijven stil -- de drie verificatiegevallen uit issue #39 in een fixture.
    ("attr016_ronde_put_ongelijk.ttl", "ATTR-016", ["A"]),
    # Dezelfde conditie, de andere soort erbinnen: put A is rond met lengte 0 (issue #92).
    ("attr016_ronde_put_lengte_nul.ttl", "ATTR-016", ["A"]),
    ("attr007_toekomstig_jaar.ttl", "ATTR-007", ["1"]),
    # ATTR-018: alleen de vrijvervalstreng en de put zonder begindatum; persleiding 3
    # valt buiten de populatie.
    ("attr018_zonder_begindatum.ttl", "ATTR-018", ["1", "A"]),
    ("attr009_lengte_wijkt_af.ttl", "ATTR-009", ["1"]),
    ("attr010_materiaal_put.ttl", "ATTR-010", ["1"]),
    ("attr012_metselwerk_rond.ttl", "ATTR-012", ["1"]),
    ("attr013_vulwaarde_hoogte.ttl", "ATTR-013", ["1", "A", "B"]),
    # ATTR-014 meldt per kenmerk, niet per object: een aggregaatbevinding met de
    # kenmerknaam als label. Zie de gerichte tests onderaan dit bestand.
    ("attr014_wibon_hasvalue.ttl", "ATTR-014", ["WIBONThema"]),
    # ATTR-015 meldt systemisch per verdacht jaar; het label is het jaartal.
    ("attr015_vulwaardejaar.ttl", "ATTR-015", ["1900"]),
    # Alleen streng 2 (PE met de betonwaarde 30) telt; de schaal 1:10 volgt uit de
    # data, waardoor streng 1 (beton 30) en streng 3 (PE 4) wel bij hun materiaal passen.
    ("attr017_wandruwheid_pe_betonwaarde.ttl", "ATTR-017", ["2"]),
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
    # Issue #84: de enige aangesloten streng is loos; die telt niet als aansluiting.
    ("rvz001_overstort_aan_loze_leiding.ttl", "RVZ-001", ["O"]),
    ("rvz002_drempel_zonder_niveau.ttl", "RVZ-002", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-002", ["O"]),
    ("rvz003_drempel_zonder_breedte.ttl", "RVZ-003", ["O"]),
    ("rvz002_overstort_zonder_drempel.ttl", "RVZ-003", ["O"]),
    ("rvz004_overstort_zonder_water.ttl", "RVZ-004", ["O"]),
    ("rvz005_overstort_op_hemelwater.ttl", "RVZ-005", ["O"]),
    # Sinds #75 per gemengde streng: het deelstelsel telt er twee.
    ("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006", ["1", "2"]),
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
    # ADM-010 meldt per loze streng; de twee strengen van de doorgaande keten allebei.
    ("adm010_loze_keten_doorgaand.ttl", "ADM-010", ["X1", "X2"]),
    ("adm010_loze_keten_aanvoer.ttl", "ADM-010", ["X1"]),
    ("adm010_loze_keten_afvoer.ttl", "ADM-010", ["X1"]),
    ("btr006_afgeronde_bobs.ttl", "BTR-006", ["b0"]),
]


@pytest.mark.parametrize(("bestand", "check_id", "verwacht"), DEFECTEN)
def test_defect_wordt_gevonden(bestand: str, check_id: str, verwacht: list[str]) -> None:
    outcome = uitkomst(bestand, check_id)

    assert labels(outcome) == verwacht


def test_elk_defect_heeft_een_eigen_fixture() -> None:
    # Bewaakt dat er geen check-ID stilzwijgend zonder fixture blijft. HGT-001 t/m
    # HGT-003 en de EXT-checks hebben externe bronnen nodig en staan in blok C;
    # BTR-001, BTR-003 en BTR-004 zijn skeletten. ADM-003 heeft geen defectfixture maar wel
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
        # De twee tegenhangers uit issue #34: hun onderdeel repareert het defect, dus
        # hun hele groep hoort stil te zijn. Zonder deze regels bewaakt de suite
        # alleen de ene check waar ze voor gemaakt zijn.
        ("adm007_overstort_met_drempel.ttl", "ADM"),
        ("rvz008_bbb_met_lediging.ttl", "RVZ"),
    ],
)
def test_schone_fixture_geeft_geen_bevinding(bestand: str, groep: str) -> None:
    run = run_checks(context_voor(bestand, fixtureconfig()), ids_van(groep))

    gemeld = {outcome.check_id: labels(outcome) for outcome in run.outcomes if outcome.findings}
    assert gemeld == {}


def test_attr001_bereikcorrecties_uit_issue20() -> None:
    """De vier gecorrigeerde diameterbereiken geven geen valse ATTR-001 meer (issue #20).

    PP Ø80, GewapendBeton Ø300, Gres Ø1200 en Asbestcement Ø1500 vielen onder de oude
    tabel buiten hun bereik; onder de gecorrigeerde tabel passen ze er alle vier in.
    """
    assert labels(uitkomst("attr001_diameterbesluit.ttl", "ATTR-001")) == []


def test_attr001_constructietype_gaat_voor_het_materiaal() -> None:
    """Issue #86: een drainageleiding wordt tegen haar eigen bereik gehouden.

    DT (Ø65 PVC) valt binnen het drainagebereik en is geen bevinding meer, terwijl het
    hemelwaterriool HW van dezelfde maat en hetzelfde materiaal er wel een blijft: de
    uitzondering hangt aan het constructietype en niet aan de maat. DIT (Ø45) laat zien
    dat het drainagebereik zelf ook een ondergrens heeft.
    """
    outcome = uitkomst("attr001_constructietype_drainage.ttl", "ATTR-001")

    assert labels(outcome) == ["DIT", "HW"]
    per_label = {bevinding.object_label: bevinding for bevinding in outcome.findings}
    assert "het bereik 50-4000 mm dat bij constructietype DIT_riool" in per_label["DIT"].message
    assert "het bereik 100-800 mm dat bij materiaal PVC" in per_label["HW"].message

    telling = [note for note in outcome.notes if "constructietype getoetst" in note]
    assert len(telling) == 1, outcome.notes
    assert "2 van de 3 strengen" in telling[0]
    # `Drain` staat wel in de tabel maar hangt onder `Leiding`; de zin daarover wordt uit
    # de configuratie afgeleid en noemt dus precies die klasse en niet DIT_riool/DT_riool.
    assert "Drain valt in deze configuratie buiten de getoetste populatie" in telling[0]

    # De kolom Buiten bereik telt per streng tegen haar eigen anker: alle drie de PVC-
    # strengen staan in de rij, maar DT (Ø65, drainagebereik) telt er niet in mee.
    verdeling = [note for note in outcome.notes if "| Materiaal |" in note]
    assert len(verdeling) == 1, outcome.notes
    assert "| PVC | 3 | 2 | 45 | 65 |" in verdeling[0]


def test_attr002_ondergrens_per_stelseltype() -> None:
    """Een gemengd riool van Ø220 valt onder 250 mm; een vuilwaterriool van Ø220 niet."""
    assert labels(uitkomst("attr002_stelseltype.ttl", "ATTR-002")) == ["G"]


def test_attr003_begindatumbesluit_uit_issue20() -> None:
    """Alleen PVC vóór 1958 is een bevinding; PE en GewapendBeton hebben geen regel meer.

    De tijdvakregels voor PE (1970), Polypropyleen (1975), GewapendBeton (1920) en
    Metselwerk (1960) zijn geschrapt omdat geen bron ze draagt (issue #20), dus ATTR-003
    toetst die materialen niet meer op begindatum.
    """
    assert labels(uitkomst("attr003_begindatum_besluit.ttl", "ATTR-003")) == ["PVC56"]


def test_adm007_ziet_een_ingebouwde_overstortdrempel() -> None:
    """De drempel hangt als constructieonderdeel aan de put, niet als knoop in het net.

    `gwsw:Overstortdrempel` is een `Wand` en dus een `Constructieonderdeel`; hij
    draagt nooit een Knooppunt-orientatie en wordt daarom geen knoop in het
    domeinmodel. `is_a()` gaf er altijd False op, waardoor deze tak van ADM-007
    nooit vuurde. Beide richtingen staan hier: zonder drempel een bevinding, met
    drempel geen -- alleen samen bewijzen ze dat de tak leeft.
    """
    assert labels(uitkomst("adm007_overstort_zonder_functie.ttl", "ADM-007")) == ["O"]
    assert labels(uitkomst("adm007_overstort_met_drempel.ttl", "ADM-007")) == []


def test_rvz008_ziet_een_geregistreerde_ledigingsvoorziening() -> None:
    """Een `Ledigingsvoorziening` is net als de drempel een constructieonderdeel.

    Zonder herkenning van zulke onderdelen meldde RVZ-008 elke bergbezinkvoorziening
    zonder terugvoerende streng, ook als de lediging netjes in de data stond.
    """
    assert labels(uitkomst("rvz008_bbb_zonder_lediging.ttl", "RVZ-008")) == ["BBB"]
    assert labels(uitkomst("rvz008_bbb_met_lediging.ttl", "RVZ-008")) == []


def test_muilprofiel_heet_muil_in_de_ontologie() -> None:
    """Een gemetseld muilprofiel is geen ATTR-012, en zijn verhouding wordt wel getoetst.

    `plausibiliteit.toml` schreef `Muilprofiel`, een naam die de GWSW-collectie
    `VormLeidingColl` niet kent -- daar heet hij `Muil` (issue #31 punt 1). Dat kostte
    twee dingen tegelijk: een valse ATTR-012 op een volkomen normaal gemetseld riool,
    en een ATTR-004-regel die op geen enkel muilprofiel vuurde. De fixture heeft een
    muil die hoger is dan breed, dus beide helften zijn hier zichtbaar.
    """
    assert labels(uitkomst("attr004_muil_te_hoog.ttl", "ATTR-012")) == []
    assert labels(uitkomst("attr004_muil_te_hoog.ttl", "ATTR-004")) == ["1"]


def test_attr010_meldt_alleen_de_kunststofput_en_niet_elk_ander_materiaal() -> None:
    """De tabel noemt wat onwaarschijnlijk is, niet wat toegestaan is (issue #43).

    Zolang `[[leiding_put_materiaal]]` de verwachte putmaterialen opsomde, gold elk
    lid van `MateriaalPutColl` dat niemand had ingetypt als bevinding -- 26 van de 30
    leden, waaronder `Gres`. Een gemeente die netjes volgens de domeinlijst
    exporteert kreeg daar een valse ATTR-010 op. Beide kanten staan hier: de
    kunststof put onder een gemetselde streng blijft melden, de gresput onder een
    betonnen streng zwijgt.

    De eerste assertie is de bewaker van de tweede. Zonder regel voor `Beton` stopt
    `run()` al vóór het putmateriaal, en dan zwijgt de gresput om de verkeerde reden:
    de test zou groen blijven ook als de tabel morgen weer een whitelist werd.
    """
    assert load_plausibility().putmateriaal("Beton") is not None
    assert labels(uitkomst("attr010_materiaal_put.ttl", "ATTR-010")) == ["1"]
    assert labels(uitkomst("attr010_gresput.ttl", "ATTR-010")) == []


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
    ruw = load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl", [])
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
    ruw = load_dataset(TTL_DIR / "attr013_vulwaarde_hoogte.ttl", [])
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


def test_attr001_splitst_de_ongetoetste_populatie_in_drie() -> None:
    """Geen materiaal, materiaal zonder regel en ontbrekende maat zijn drie getallen."""
    outcome = uitkomst("attr001_ongetoetste_uitsplitsing.ttl", "ATTR-001")

    # De uitsplitsing verandert de telling, niet het gedrag: geen enkele streng valt
    # buiten haar bereik, dus geen bevinding.
    assert outcome.findings == []

    def regel_met(term: str) -> str:
        treffers = [note for note in outcome.notes if term in note]
        assert len(treffers) == 1, outcome.notes
        return treffers[0]

    assert "1 van de 4 strengen" in regel_met("geen materiaal")
    zonder_regel = regel_met("zonder diameterregel")
    assert "1 van de 4 strengen" in zonder_regel
    maat = regel_met("geen bruikbare profielmaat")
    assert "1 van de 4 strengen" in maat
    assert "1 met een geregistreerde 0" in maat


def test_attr001_verdeelt_de_diameter_per_materiaal() -> None:
    """De verdelingstabel toont per materiaal het aantal en de feitelijke min/max."""
    outcome = uitkomst("attr001_ongetoetste_uitsplitsing.ttl", "ATTR-001")

    tabel = [note for note in outcome.notes if "| Materiaal |" in note]
    assert len(tabel) == 1, outcome.notes
    rijen = tabel[0].splitlines()

    beton = [r for r in rijen if r.startswith("| Beton ")]
    assert beton == ["| Beton | 2 | 0 | 500 | 500 |"]
    gvk = [r for r in rijen if r.startswith("| GVK ")]
    assert gvk == ["| GVK | 1 | 0 | 500 | 500 |"]


def test_attr005_noemt_de_vermoedelijke_waarde() -> None:
    bevinding = uitkomst("attr005_centimeters.ttl", "ATTR-005").findings[0]

    assert bevinding.details["waarde_mm"] == pytest.approx(30)
    assert bevinding.details["vermoedelijke_waarde_mm"] == pytest.approx(300)


def test_attr006_onderscheidt_de_twee_zijden() -> None:
    bevindingen = uitkomst("attr006_twee_te_kleine_putten.ttl", "ATTR-006").findings

    assert sorted(b.details["zijde"] for b in bevindingen) == ["beginpunt", "eindpunt"]
    assert sorted(b.details["put"] for b in bevindingen) == ["A", "B"]


def test_attr016_noemt_de_vorm_en_de_twee_maten() -> None:
    """De bevinding draagt de vorm en beide maten, zoals ATTR-004 dat voor leidingen doet."""
    bevinding = uitkomst("attr016_ronde_put_ongelijk.ttl", "ATTR-016").findings[0]

    assert bevinding.details["vorm"] == "Rond"
    assert bevinding.details["breedte_mm"] == pytest.approx(800)
    assert bevinding.details["lengte_mm"] == pytest.approx(1000)
    assert bevinding.severity.value == "F"


def test_attr016_scheidt_een_niet_geregistreerde_maat_van_een_tegenspraak() -> None:
    """Binnen dezelfde conditie zijn er twee soorten, en die krijgen elk hun eigen tekst.

    Een maat van 0 mm is geen meting maar een niet-geregistreerde maat -- een gat in de
    aanlevering, dat de nulmeting meestal al als `LengtePut_val` meldt. Twee echte maar
    ongelijke maten zijn de tegenspraak tussen vorm en maten, en dat is de eigen waarde
    van deze check (issue #92).
    """
    nul = uitkomst("attr016_ronde_put_lengte_nul.ttl", "ATTR-016").findings[0]
    tegenspraak = uitkomst("attr016_ronde_put_ongelijk.ttl", "ATTR-016").findings[0]

    assert "lengte 0 mm" in nul.message
    assert "de lengte is niet geregistreerd" in nul.message
    assert nul.details["breedte_mm"] == pytest.approx(800)
    assert nul.details["lengte_mm"] == pytest.approx(0)
    assert "een ronde put heeft een diameter" in tegenspraak.message
    assert "niet geregistreerd" not in tegenspraak.message


def test_attr016_verantwoordt_de_ronde_putten_zonder_maat() -> None:
    """Een ronde put zonder breedte of lengte is niet te toetsen; dat hoort in de toelichting.

    De fixture kent zulke putten niet -- alle drie dragen beide maten -- dus put A wordt
    hier van zijn lengte ontdaan, zodat de verantwoordingsregel zichtbaar wordt.
    """
    config = fixtureconfig()
    ruw = load_dataset(TTL_DIR / "attr016_ronde_put_ongelijk.ttl", [])
    put = next(node for node in ruw.nodes.values() if node.label == "A")
    nodes = dict(ruw.nodes)
    nodes[put.uri] = replace(put, aspects=tuple(a for a in put.aspects if a.kind != "LengtePut"))
    context = CheckContext(dataset=replace(ruw, nodes=nodes), config=config)

    outcome = run_checks(context, ["ATTR-016"]).outcomes[0]

    assert labels(outcome) == []
    assert any(
        "1 van de 2 ronde putten missen een breedte of een lengte" in note for note in outcome.notes
    ), outcome.notes


def test_attr017_noemt_materiaal_schaal_en_band() -> None:
    """De bevinding draagt de ruwe waarde, de gelezen schaal en de band per materiaal."""
    bevinding = uitkomst("attr017_wandruwheid_pe_betonwaarde.ttl", "ATTR-017").findings[0]

    assert bevinding.details["materiaal"] == "PE"
    assert bevinding.details["wandruwheid"] == pytest.approx(30)
    assert bevinding.details["schaal"] == pytest.approx(10)
    assert bevinding.details["wandruwheid_mm"] == pytest.approx(3.0)
    assert bevinding.details["minimum_mm"] == pytest.approx(0.1)
    assert bevinding.details["maximum_mm"] == pytest.approx(1.0)
    assert bevinding.severity.value == "W"


def test_attr017_leest_hele_millimeters() -> None:
    """Een export in hele mm keurt de check niet af: de schaal komt uit de data.

    De betonleiding draagt wandruwheid 3; op schaal 1:1 is dat 3,0 mm, de C2100-waarde.
    Zou de schaal op tienden vastgezet zijn, dan las de check 0,3 mm en gaf een
    bevinding. Dit is de tegenproef bij `attr017_wandruwheid_pe_betonwaarde.ttl`.
    """
    outcome = uitkomst("attr017_wandruwheid_hele_mm.ttl", "ATTR-017")

    assert labels(outcome) == []
    assert any("schaal 1:1" in note for note in outcome.notes), outcome.notes


def test_attr017_verantwoordt_de_ongetoetste_leidingen() -> None:
    """Een materiaal zonder band en een leiding zonder wandruwheid horen in de toelichting.

    Streng 3 (PE) krijgt hier materiaal Polypropyleen -- dat kent geen C2100-band -- en
    streng 1 (beton) wordt van zijn wandruwheid ontdaan. Beide horen als niet getoetst
    in de toelichting te staan; de PE-30-streng blijft de enige bevinding.
    """
    config = fixtureconfig()
    ruw = load_dataset(TTL_DIR / "attr017_wandruwheid_pe_betonwaarde.ttl", [])
    conduits = dict(ruw.conduits)
    streng3 = next(c for c in ruw.conduits.values() if c.label == "3")
    conduits[streng3.uri] = replace(
        streng3,
        aspects=tuple(
            replace(a, reference="Polypropyleen") if a.kind == "MateriaalLeiding" else a
            for a in streng3.aspects
        ),
    )
    streng1 = next(c for c in ruw.conduits.values() if c.label == "1")
    conduits[streng1.uri] = replace(
        streng1,
        aspects=tuple(a for a in streng1.aspects if not a.kind.startswith("Wandruwheid")),
    )
    context = CheckContext(dataset=replace(ruw, conduits=conduits), config=config)

    outcome = run_checks(context, ["ATTR-017"]).outcomes[0]

    assert labels(outcome) == ["2"]
    assert any("dragen geen wandruwheid" in note for note in outcome.notes), outcome.notes
    assert any("Polypropyleen" in note for note in outcome.notes), outcome.notes


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


def test_hgt006_zwijgt_onder_de_forsgrens_van_tien_centimeter() -> None:
    # 0,08 m stijging ligt onder de forsgrens van 0,10 m (issue #80): geen forse bevinding.
    assert uitkomst("hgt006_net_onder_de_forsgrens.ttl", "HGT-006").findings == []


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


@pytest.mark.parametrize("check_id", ["BTR-001", "BTR-003", "BTR-004"])
def test_btr_skeletten_melden_hun_markering(check_id: str) -> None:
    outcome = uitkomst("attr_schoon.ttl", check_id)

    assert outcome.findings == []
    assert outcome.skeleton == "vereist inwinningsmetagegevens"
    assert any("vereist inwinningsmetagegevens" in note for note in outcome.notes)


def test_rvz006_meldt_per_gemengde_streng() -> None:
    """Sinds issue #75 hangt de bevinding aan de gemengde strengen, niet aan een knoop.

    Het gebrek zit in het deelstelsel als geheel, maar een deelstelsel is geen
    GWSW-object; de dragers zijn de gemengde strengen ervan. Beide strengen van de
    fixture krijgen een eigen bevinding.
    """
    outcome = uitkomst("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006")

    assert labels(outcome) == ["1", "2"]
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl", [])
    assert all(bevinding.object_uri in dataset.conduits for bevinding in outcome.findings)


def test_rvz006_draagt_hetzelfde_deelstelsel_id_als_de_net_checks() -> None:
    """RVZ-006 en NET-001 melden over hetzelfde deelstelsel.

    Alleen met een gedeeld ID is in rapport en GIS te zien dat het om hetzelfde
    stuk net gaat; anders lijken twee gemengde strengen twee losse gebreken.
    """
    dataset = load_dataset(TTL_DIR / "rvz006_gemengd_zonder_overstort.ttl", [])
    context = CheckContext(dataset=dataset, config=fixtureconfig())
    ids = deelstelsel_ids(context)

    outcome = run_checks(context, ["RVZ-006"]).outcomes[0]

    clusters = {bevinding.details["cluster_id"] for bevinding in outcome.findings}
    assert len(outcome.findings) == 2
    assert len(clusters) == 1
    assert clusters <= set(ids.values())


def test_rvz006_zet_geen_eigen_foutlocatie_meer() -> None:
    """De melding zit op de streng zelf, dus de gewone objectlocatie volstaat.

    Het zwaartepunt van het deelstelsel was er om een melding op een willekeurige
    knoop midden in het deel te zetten; per streng is dat niet meer nodig en zou het
    de melding juist van haar eigen streng wegtrekken.
    """
    outcome = uitkomst("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006")

    assert all("foutlocatie" not in bevinding.details for bevinding in outcome.findings)


def test_rvz006_zonder_afvoereindpunt_noemt_alleen_die_reden() -> None:
    """Een gemengd deel met overstort maar zonder gemaal mist alleen het afvoereindpunt.

    De melding noemt dan die ene reden en niet de overstort, die er wel is (issue #23).
    """
    outcome = uitkomst("rvz006_gemengd_zonder_afvoereindpunt.ttl", "RVZ-006")

    assert len(outcome.findings) == 1
    boodschap = outcome.findings[0].message
    assert "zonder afvoereindpunt (gemaal of overnamepunt)" in boodschap
    assert "externe overstort" not in boodschap


def test_rvz006_zonder_beide_noemt_beide_redenen() -> None:
    """Een gemengd deel zonder overstort en zonder afvoereindpunt noemt beide redenen."""
    outcome = uitkomst("rvz006_gemengd_zonder_overstort.ttl", "RVZ-006")

    assert len(outcome.findings) == 2
    for bevinding in outcome.findings:
        assert "zonder enige externe overstort of bergbezinkvoorziening" in bevinding.message
        assert "en zonder afvoereindpunt (gemaal of overnamepunt)" in bevinding.message


def test_rvz006_telt_een_pompunit_niet_als_afvoereindpunt() -> None:
    """Een pompput is een overdrachtspunt naar de drukriolering, geen eindpunt (BO-55).

    RVZ-006 leest dezelfde lijst `afvoer_eindpunt` als NET-001, dus het gemengde
    deelstelsel dat alleen op een pompunit uitkomt mist nog steeds zijn eindpunt.
    De melding noemt precies die ene reden: de overstort is er wel.
    """
    outcome = uitkomst("rvz006_gemengd_alleen_pompunit.ttl", "RVZ-006")

    assert labels(outcome) == ["1", "2"]
    for bevinding in outcome.findings:
        assert "zonder afvoereindpunt (gemaal of overnamepunt)" in bevinding.message
        assert "externe overstort" not in bevinding.message


def test_rvz006_met_overstort_en_afvoereindpunt_zwijgt() -> None:
    """Met een overstort en een gemaal is het gemengde stelsel compleet: geen RVZ-006.

    `rvz_schoon.ttl` draagt beide; de bredere `test_schone_fixture_geeft_geen_bevinding`
    bewaakt de hele RVZ-groep, deze wijst de RVZ-006-tak expliciet aan (issue #23).
    """
    assert labels(uitkomst("rvz_schoon.ttl", "RVZ-006")) == []


def test_gedeelde_volledige_context_wordt_hergebruikt() -> None:
    """Anders herrekent elk gebied de karakteristiek van de volledige export.

    De volledige-export-context hangt alleen af van de volledige dataset, de config
    en de onbetrouwbare objecten; die zijn alle drie gebiedsonafhankelijk, dus mag
    hij over gebieden heen gedeeld worden.
    """
    dataset = load_dataset(TTL_DIR / "schoon.ttl", [])
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
    dataset = load_dataset(TTL_DIR / "schoon.ttl", [])
    context = CheckContext(dataset=dataset, config=load_check_config())

    run = run_checks(context, ["TOP-001"])

    assert run.treffers is context.treffers


def _vlakke_staffel_config() -> CheckConfig:
    """De oude, vlakke HGT-007-drempel als staffel: overal 1:1000, ongeacht diameter."""
    config = fixtureconfig()
    config.verhang_staffel = [VerhangStap(minimaal_verhang_een_op=1000)]
    return config


def test_hgt007_staffel_meldt_de_te_vlakke_kleine_streng() -> None:
    """Issue #29: het minimale afschot hangt van de diameter af.

    L1 is 200 mm en ligt op 1:500. Onder de RIONED-staffel (200 mm vraagt 1:250) is
    dat te vlak en hoort er een melding te komen; onder de oude vlakke 1:1000 was
    1:500 juist steil genoeg en zweeg de check. Beide gedragingen staan hier, want
    alleen samen bewijzen ze dat de staffel het verschil maakt.
    """
    assert labels(uitkomst("hgt007_staffel.ttl", "HGT-007")) == ["L1"]
    assert labels(uitkomst("hgt007_staffel.ttl", "HGT-007", _vlakke_staffel_config())) == []


def test_hgt007_notes_tellen_de_ongetoetste_strengen() -> None:
    """De toelichting zegt waarom strengen buiten de toetsing vielen.

    In de fixture: L3 valt buiten de rol (hemelwater), L4 mist een diameter en L5
    mist een BOB. Stilte zou lezen als 'alles getoetst'.
    """
    run = run_checks(context_voor("hgt007_staffel.ttl", fixtureconfig()), ["HGT-007"])
    tekst = " ".join(run.outcomes[0].notes)

    assert "1 strengen buiten de rol vuilwater" in tekst
    assert "1 zonder bruikbare BOB" in tekst
    assert "1 zonder diameter" in tekst


def test_attr014_meldt_een_keer_per_kenmerk_met_de_aantallen() -> None:
    """De WIBONThema-fout wordt een aggregaatbevinding, geen bevinding per object.

    De fixture draagt twee WIBONThema-kenmerken die hasValue gebruiken waar de
    ontologie hasReference eist -- een met de vulwaarde 0, een met een tekstlabel.
    Precies een bevinding, met de aantallen in de boodschap en de kenmerknaam als
    onderscheidende sleutel.
    """
    outcome = uitkomst("attr014_wibon_hasvalue.ttl", "ATTR-014")
    assert len(outcome.findings) == 1

    bevinding = outcome.findings[0]
    assert bevinding.details["kenmerk"] == "WIBONThema"
    assert bevinding.systemisch is True
    # Een aggregaat over een heel kenmerk wijst geen los object aan.
    assert bevinding.object_uri == ""
    assert bevinding.location is None
    assert "WIBONThema gebruikt hasValue in plaats van hasReference op 2 objecten" in (
        bevinding.message
    )
    assert "waarvan 1 met de vulwaarde 0" in bevinding.message


def test_attr015_meldt_het_dominante_vulwaardejaar() -> None:
    """16 van de 40 strengen op 1900 (40%) is een systemische melding op dat jaar.

    Een aggregaat over de hele meetset: het jaartal is het label, er is geen los object,
    en het aandeel staat in de boodschap en de details.
    """
    outcome = uitkomst("attr015_vulwaardejaar.ttl", "ATTR-015")
    assert len(outcome.findings) == 1

    bevinding = outcome.findings[0]
    assert bevinding.object_label == "1900"
    assert bevinding.systemisch is True
    assert bevinding.object_uri == ""
    assert bevinding.details["jaar"] == 1900
    assert bevinding.details["aantal"] == 16
    assert bevinding.details["aandeel_procent"] == pytest.approx(40.0)
    assert outcome.examined == 40
    assert "40.0% van de 40 gedateerde objecten" in bevinding.message
    assert "vulwaarde" in bevinding.message


def test_attr015_zwijgt_zonder_piek() -> None:
    """Genoeg gedateerde strengen, maar geen enkel jaar overheerst: geen melding.

    Dit is de test die bewijst dat de detector niet overgevoelig is -- hij vuurt niet
    op een natuurlijke verdeling, en zegt in zijn toelichting wat het drukste jaar was.
    """
    outcome = uitkomst("attr015_geen_piek.ttl", "ATTR-015")

    assert outcome.findings == []
    assert any("drukste jaar" in note and "signaalwaarde" in note for note in outcome.notes), (
        outcome.notes
    )


def test_attr015_zwijgt_bij_te_weinig_gedateerde_objecten() -> None:
    """Onder het minimum zegt een aandeel niets; de detector zwijgt met een toelichting.

    `attr_schoon.ttl` draagt drie gedateerde objecten, alle drie uit 1980 (de putten
    kregen hun begindatum met ATTR-018, issue #61); zonder deze ondergrens zou dat ene
    jaar 100% halen en vals aanslaan.
    """
    outcome = uitkomst("attr_schoon.ttl", "ATTR-015")

    assert outcome.findings == []
    assert any("te weinig" in note and "minimum van 30" in note for note in outcome.notes), (
        outcome.notes
    )


def test_attr007_verantwoordt_de_objecten_zonder_begindatum() -> None:
    """De putten zonder begindatum horen in de toelichting; de meetsettelling niet meer.

    De fixture heeft twee putten zonder begindatum en een streng met een (te toekomstige)
    datum. De tweede regel van voorheen ("In deze meetset hebben … geen begindatum")
    telde wat ATTR-018 nu per object meldt; twee plekken die hetzelfde zeggen lopen
    uit elkaar (issue #61).
    """
    outcome = uitkomst("attr007_toekomstig_jaar.ttl", "ATTR-007")

    assert any("2 van de 2 putten in deze toets" in note for note in outcome.notes), outcome.notes
    assert not any("meetset" in note for note in outcome.notes), outcome.notes


def test_attr018_meldt_per_object_en_benoemt_de_soort() -> None:
    """Streng 1 en put A missen de begindatum; de melding zegt welke soort object het is."""
    outcome = uitkomst("attr018_zonder_begindatum.ttl", "ATTR-018")

    per_label = {f.object_label: f for f in outcome.findings}
    assert set(per_label) == {"1", "A"}
    assert per_label["1"].details["objectsoort"] == "streng"
    assert per_label["A"].details["objectsoort"] == "put"
    assert all("begindatum" in f.message.lower() for f in outcome.findings)
    # Twee vrijvervalstrengen plus vier putten; de persleiding telt niet mee.
    assert outcome.examined == 6


def test_attr018_verantwoordt_de_leidingen_buiten_de_populatie() -> None:
    """De persleiding zonder begindatum is geen bevinding, maar hoort wel geteld te zijn."""
    outcome = uitkomst("attr018_zonder_begindatum.ttl", "ATTR-018")

    assert any(
        "1 van de 3 leidingen" in note
        and "geen vrijvervalrioolleiding" in note
        and "1 zonder" in note
        for note in outcome.notes
    ), outcome.notes


def test_attr014_zwijgt_bij_de_juiste_property() -> None:
    """Dezelfde kenmerken, nu met hasReference geschreven -- geen bevinding."""
    assert labels(uitkomst("attr014_wibon_correct.ttl", "ATTR-014")) == []


def test_attr014_meldt_ook_de_omgekeerde_richting() -> None:
    """hasReference op een kenmerk dat de ontologie aan hasValue bindt, is ook een fout.

    Het issue omvat 'of andersom' expliciet; deze fixture heeft een LengteLeiding met
    hasReference waar hasValue hoort.
    """
    outcome = uitkomst("attr014_reference_op_waardekenmerk.ttl", "ATTR-014")
    assert len(outcome.findings) == 1

    bevinding = outcome.findings[0]
    assert bevinding.details["kenmerk"] == "LengteLeiding"
    assert (
        bevinding.message == "LengteLeiding gebruikt hasReference in plaats van hasValue op "
        "1 objecten."
    )


def test_adm010_doorgaande_keten_draagt_keten_buren_en_omvang() -> None:
    """Beide loze strengen delen een keten-ID en noemen de aansluitende actieve strengen."""
    outcome = uitkomst("adm010_loze_keten_doorgaand.ttl", "ADM-010")

    per_label = {f.object_label: f for f in outcome.findings}
    assert set(per_label) == {"X1", "X2"}
    assert per_label["X1"].details["cluster_id"] == per_label["X2"].details["cluster_id"]
    assert per_label["X1"].details["cluster_id"].startswith("loos-")
    for bevinding in per_label.values():
        assert bevinding.details["geval"] == "doorgaand"
        assert bevinding.details["keten_strengen"] == 2
        assert bevinding.details["inkomend"] == "1"
        assert bevinding.details["uitgaand"] == "3"
        # Streng 1 en streng 0 liggen transitief bovenstrooms.
        assert bevinding.details["bovenstrooms"] == 2
        assert "1" in bevinding.message and "3" in bevinding.message
    assert outcome.examined == 2


@pytest.mark.parametrize(
    ("bestand", "geval"),
    [
        ("adm010_loze_keten_aanvoer.ttl", "aanvoer"),
        ("adm010_loze_keten_afvoer.ttl", "afvoer"),
    ],
)
def test_adm010_benoemt_het_geval(bestand: str, geval: str) -> None:
    outcome = uitkomst(bestand, "ADM-010")

    assert [f.details["geval"] for f in outcome.findings] == [geval]


def test_adm010_noemt_de_actieve_streng_die_de_keten_alleen_raakt() -> None:
    """Streng 9 verlaat dezelfde put B, maar sluit in de afvoerrichting niet aan (issue #62)."""
    outcome = uitkomst("adm010_loze_keten_rakend.ttl", "ADM-010")

    assert labels(outcome) == ["X1"]
    bevinding = outcome.findings[0]
    assert bevinding.details["geval"] == "aanvoer"
    assert bevinding.details["inkomend"] == "1"
    assert bevinding.details["rakend"] == "9"


def test_adm010_weigert_een_geval_zonder_meldingstekst() -> None:
    """Wie `losgekoppeld` weer aan `gevallen` toevoegt krijgt een fout, geen afvoertekst."""
    keten = _LozeKeten("loos-X1", (), (), (), (), 0)
    assert keten.geval == "losgekoppeld"

    with pytest.raises(ValueError, match="losgekoppeld"):
        LozeLeidingAanActiefRiool._boodschap(keten)


def test_adm010_telt_de_losgekoppelde_keten_wel_maar_meldt_hem_niet() -> None:
    """De losgekoppelde keten hoort in de verantwoording, niet in de bevindingen (issue #81)."""
    outcome = uitkomst("adm010_loze_keten_losgekoppeld.ttl", "ADM-010")

    assert labels(outcome) == []
    assert any("1 losgekoppeld (1 streng)" in note for note in outcome.notes), outcome.notes


def test_adm010_verantwoordt_de_ketens_per_geval() -> None:
    outcome = uitkomst("adm010_loze_keten_doorgaand.ttl", "ADM-010")

    assert any(
        "2 loze leidingen in 1 keten" in note and "1 doorgaand" in note for note in outcome.notes
    ), outcome.notes
