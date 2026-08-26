"""Tests voor de projectconfiguratie van de check-engine."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import (
    KLASSE_BOB_BEGIN,
    KLASSE_BOB_EIND,
    KLASSE_MAAIVELDHOOGTE,
    KLASSE_PUTDEKSELNIVEAU,
)
from pydantic import BaseModel

from nlriochecker.checkconfig import (
    VULWAARDE_KENMERKEN,
    CheckThresholds,
    ExternalSources,
    ReportOptions,
    StudyAreaOptions,
    VulwaardeOptions,
    default_check_config_path,
    load_check_config,
)
from nlriochecker.errors import ConfigError

PROJECTCONFIG = Path(__file__).resolve().parents[1] / "configs" / "dewoldenhoogeveen.toml"


def test_standaardconfig_laadt() -> None:
    config = load_check_config()

    assert default_check_config_path().exists()
    assert config.klassen.put == ["Put"]
    assert config.drempels.snapping_tolerantie_m == 0.10
    assert config.drempels.dubbele_put_tolerantie_m == 0.30


def test_gemengd_zonder_overstort_buffer_heeft_een_default() -> None:
    """De bufferafstand van de vlakkenlaag `gemengd_zonder_overstort` (#25, #75).

    Projectkeuze zonder externe bron; 10 m buffert elke strenglijn tot een lint van
    20 m breed, zodat de strengen van een deelstelsel langs een straat samenvloeien.
    """
    assert load_check_config().drempels.gemengd_zonder_overstort_buffer_m == 10.0


def test_maximale_strenglengte_volgt_de_ontologie() -> None:
    """De bovengrens van ATTR-008 is de GWSW-ontologiegrens, niet 200 m (issue #35).

    `Dt_LengteLeiding` declareert een bereik van 1-75 m. De oude drempel 200 keurde
    strengen goed die de SHACL-nulmeting in hetzelfde rapport afkeurde (op De Wolden en Hoogeveen
    431 vrijvervalstrengen); GWSW is leidend. De ondergrens 1 m valt al samen met de
    ontologie.
    """
    drempels = load_check_config().drempels
    assert drempels.maximale_strenglengte_m == 75.0
    assert drempels.minimale_strenglengte_m == 1.0


def test_putdiepte_volgt_de_ontologie() -> None:
    """De grenzen van HGT-012 volgen het GWSW-datatype Dt_HoogtePut (issue #35).

    `Dt_HoogtePut` declareert 500-4000 mm (0,5-4,0 m). De oude bovengrens 6,0 m keurde
    putten goed die de ontologie afkeurt, en de ondergrens toetste alleen op `> 0` in
    plaats van de gedeclareerde 500 mm. GWSW is leidend, dus beide grenzen volgen nu de
    ontologie.
    """
    drempels = load_check_config().drempels
    assert drempels.minimale_putdiepte_m == 0.5
    assert drempels.maximale_putdiepte_m == 4.0


def test_mechanisch_riool_is_geconfigureerd() -> None:
    """Mechanisch riool valt buiten scope voor de checks.

    Het staat als klassenlijst beschikbaar zodat de GIS-uitvoer die strengen in een eigen
    grijze laag kan zetten. De twee ontologische wortels in plaats van de losse bladen
    (issue #56): dat dekt ook Leidingsegment en Luchtpersleiding, die de symbolentabel al
    als mechanische streepjeslijn tekent.
    """
    config = load_check_config()

    assert config.klassen.mechanisch == ["MechanischeRioolleiding", "MechanischeTransportleiding"]


def test_afvoereindpunt_is_overnamepunt_en_gemaal() -> None:
    """`Pompunit` hoort niet in `afvoer_eindpunt` (BO-55, verfijnt BO-33).

    Een pompput is een overdrachtspunt naar de drukriolering, geen einde van de
    afvoer; sinds issue #72 is het persnet erachter traceerbaar, dus de streng die
    erop eindigt wordt via de bereikbaarheidsgraaf beoordeeld en niet meer door de
    pompput zelf als eindpunt te tellen. `Gemaal` blijft staan zolang `Overnamepunt`
    nul instanties heeft (het loslaatcriterium van BO-33).

    Deze lijst voedt NET-001 (`_eindpunten`) en RVZ-006 (`_afvoereindpunten`); wie
    haar wijzigt verschuift beide checks tegelijk, en dat hoort een bewuste daad met
    een BO te zijn.
    """
    assert load_check_config().klassen.afvoer_eindpunt == ["Overnamepunt", "Gemaal"]


def test_pompunit_eruit_zonder_persnet_is_een_configuratiefout(tmp_path: Path) -> None:
    """De voorwaarde onder BO-55 wordt afgedwongen, niet aangenomen.

    `load_check_config` valideert een projectbestand op zichzelf en legt het NIET over
    `checks.toml` heen: een projectconfig die `mechanisch` weglaat krijgt een lege lijst.
    Staat `Pompunit` dan ook niet meer in `afvoer_eindpunt`, dan is de pompput geen
    eindpunt en is er geen persnet om achterlangs bij het gemaal te komen -- precies de
    toestand met +645 valse NET-001-bevindingen waar BO-33 voor waarschuwde en waarvoor
    issue #73 op #72 moest wachten. Zonder deze poort zou zo'n config stil draaien: de
    nul-bewaking laat een rol met een lege klassenlijst juist weg, dus ook daar komt geen
    signaal vandaan.
    """
    pad = tmp_path / "zonder_persnet.toml"
    pad.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "afvoer_eindpunt = ['Overnamepunt', 'Gemaal']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as fout:
        load_check_config(pad)

    boodschap = str(fout.value)
    assert "afvoer_eindpunt" in boodschap
    assert "mechanisch" in boodschap
    assert "BO-55" in boodschap


def test_persnet_of_pompunit_maakt_de_config_wel_geldig(tmp_path: Path) -> None:
    """Beide uitwegen werken: het persnet declareren, of Pompunit laten staan.

    De tweede is de toestand van vóór issue #73 en blijft geldig; een project dat de
    drukriolering niet kan traceren hoort haar pompputten als eindpunt te houden.
    """
    basis = (
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "afvoer_eindpunt = ['Overnamepunt', 'Gemaal']\n{extra}"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
    )
    met_persnet = tmp_path / "met_persnet.toml"
    met_persnet.write_text(
        basis.format(extra="mechanisch = ['MechanischeRioolleiding']\n"), encoding="utf-8"
    )
    met_pompunit = tmp_path / "met_pompunit.toml"
    met_pompunit.write_text(
        basis.format(extra="").replace("'Gemaal'", "'Gemaal', 'Pompunit'"), encoding="utf-8"
    )

    assert load_check_config(met_persnet).klassen.mechanisch == ["MechanischeRioolleiding"]
    assert "Pompunit" in load_check_config(met_pompunit).klassen.afvoer_eindpunt


def test_een_lege_eindpuntlijst_valt_buiten_de_poort(tmp_path: Path) -> None:
    """Zonder enig afvoereindpunt gaat de poort van BO-55 niet op.

    Dan is er geen pompput-zonder-uitweg maar een config die NET-001 helemaal geen
    eindpunt geeft; dat is een andere, meteen zichtbare toestand, en de vele minimale
    testconfigs in deze suite leunen erop.
    """
    pad = tmp_path / "leeg.toml"
    pad.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n",
        encoding="utf-8",
    )

    assert load_check_config(pad).klassen.afvoer_eindpunt == []


def test_netwerkknopen_bundelen_putten_en_eindpunten() -> None:
    knopen = load_check_config().klassen.netwerkknopen

    assert knopen[0] == "Put"
    assert "Gemaal" in knopen


def test_eigen_config_vervangt_de_drempels(tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n"
        "[drempels]\nsnapping_tolerantie_m = 0.5\n",
        encoding="utf-8",
    )

    config = load_check_config(eigen)

    assert config.drempels.snapping_tolerantie_m == 0.5
    # Niet opgegeven drempels vallen terug op de standaard.
    assert config.drempels.dubbele_put_tolerantie_m == 0.30


@pytest.mark.parametrize(
    ("inhoud", "melding"),
    [
        ("dit is [geen toml", "geldige TOML"),
        ("[klassen]\nput = []\nvrijvervalleiding = ['X']\n", "at least 1"),
        (
            "[klassen]\nput = ['Put']\nvrijvervalleiding = ['X']\n[drempels]\n"
            "snapping_tolerantie_m = 0\n",
            "greater than 0",
        ),
        ("[klassen]\nput = ['Put']\nvrijvervalleiding = ['X']\nonbekend = ['Y']\n", "onbekend"),
        # Een tikfout in het hoofdlettergebruik gaf een leesregel die stil niets deed,
        # terwijl ATTR-013 meldde dat hij op dat kenmerk gold.
        (
            "[klassen]\nput = ['Put']\nvrijvervalleiding = ['X']\n[vulwaarden]\n"
            "hoogte_kenmerken = ['bobbeginpuntleiding']\n",
            "kent bobbeginpuntleiding niet",
        ),
        (
            "[klassen]\nput = ['Put']\nvrijvervalleiding = ['X']\n[vulwaarden]\n"
            "hoogte_kenmerken = ['HoogtePut']\n",
            "kent HoogtePut niet",
        ),
        # Een band die de dataset opslokt is geen drempelkeuze maar een eenheidsfout.
        (
            "[klassen]\nput = ['Put']\nvrijvervalleiding = ['X']\n[vulwaarden]\n"
            "hoogte_band_m = 1\n",
            "less than or equal to 0.5",
        ),
    ],
)
def test_ongeldige_config(tmp_path: Path, inhoud: str, melding: str) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text(inhoud, encoding="utf-8")

    with pytest.raises(ConfigError, match=melding):
        load_check_config(stuk)


def test_config_zonder_nulmetingsectie_faalt(tmp_path: Path) -> None:
    """De CFK-lijst hoort in checks.toml te staan, niet als default in Python.

    Zonder deze eis valt een projectconfig die de sectie mist stilzwijgend terug op
    drie klassen, en dan staat de lijst tweemaal opgeschreven. Dat is te meer een
    probleem sinds `--cfk` diezelfde lijst als toegestane waarden gebruikt: een
    project met andere conformiteitsklassen zou er dan de verkeerde geaccepteerd
    zien.
    """
    basis = default_check_config_path().read_text(encoding="utf-8")
    zonder = basis.replace('vereiste_cfk = ["Hyd", "MdsPlan", "MdsProj"]', "")
    pad = tmp_path / "zonder_nulmeting.toml"
    pad.write_text(zonder, encoding="utf-8")

    with pytest.raises(ConfigError, match="vereiste_cfk"):
        load_check_config(pad)


def test_ontbrekend_bestand(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="kan niet gelezen worden"):
        load_check_config(tmp_path / "weg.toml")


def test_rapportinstellingen_hebben_bruikbare_defaults() -> None:
    """Geen drempel hardgecodeerd: het rapport leest ze uit de projectconfig."""
    rapport = load_check_config().rapport

    assert rapport.richtingsdrempel == 0.10
    assert rapport.multi_melding_checks == 3
    assert rapport.max_bevindingen_per_check == 0
    assert rapport.systemisch_drempel == 0.80
    assert rapport.systemisch_minimum_bekeken == 100
    assert rapport.register_versie == "v0.9"
    assert rapport.onderdruk_klassen == []
    assert rapport.onderdruk_checks == []


def test_onbekend_onderdruk_check_id_faalt_bij_het_laden(tmp_path: Path) -> None:
    """Een typefout in `onderdruk_checks` zou stil niets onderdrukken (issue #65)."""
    bron = default_check_config_path().read_text(encoding="utf-8")
    pad = tmp_path / "checks.toml"
    pad.write_text(
        bron.replace("onderdruk_checks = []", 'onderdruk_checks = ["XYZ-999"]'), encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="XYZ-999"):
        load_check_config(pad)


def test_de_projectconfig_onderdrukt_het_mechanische_riool() -> None:
    """De Wolden: dezelfde twee wortels als `[klassen] mechanisch` (issue #56, #65)."""
    config = load_check_config(PROJECTCONFIG)

    assert config.rapport.onderdruk_klassen == config.klassen.mechanisch
    assert config.rapport.onderdruk_checks == []


def test_kritieke_klassen_bepalen_de_hoogste_prioriteit() -> None:
    """Een fout op een overstort weegt zwaarder dan een fout op een gewone put."""
    assert "Overstortput" in load_check_config().klassen.kritiek


# De configuratiemodellen met drempelvormige velden, met de TOML-sectie waarin ze
# horen. `CheckThresholds` was de enige die #28 afdekte; de acht velden daarbuiten
# (`context_buffer_m`, `hoogte_band_m`, `dekking_tolerantie_m`, de velden van `[rapport]`)
# vielen buiten elke bewaking, en een negende veld zou morgen hetzelfde gat heropenen.
# `ClassRoots`, `NulmetingOptions` en `NamingOptions` staan er niet bij: die dragen geen
# drempels maar klassenlijsten, en de eerste twee zijn al verplicht.
DREMPELMODELLEN: list[tuple[str, type[BaseModel]]] = [
    ("drempels", CheckThresholds),
    ("rapport", ReportOptions),
    ("studiegebied", StudyAreaOptions),
    ("vulwaarden", VulwaardeOptions),
    ("bronnen", ExternalSources),
]

CONFIGBESTANDEN = [
    pytest.param(default_check_config_path(), "src/nlriochecker/checks.toml", id="checks.toml"),
    pytest.param(PROJECTCONFIG, "configs/dewoldenhoogeveen.toml", id="dewoldenhoogeveen.toml"),
]

# Sleutels van `[drempels]` waarvoor `configs/dewoldenhoogeveen.toml` bewust van de
# `CheckThresholds`-default afwijkt, met de reden. Vandaag leeg: De Wolden en Hoogeveen draait op de
# standaardwaarden. Een project *mag* afwijken -- maar dan als bewuste daad die hier
# opgeschreven staat, niet als een getal dat stilzwijgend uit elkaar loopt.
BEWUSTE_AFWIJKINGEN: dict[str, str] = {}


def _verplichte_velden(model: type[BaseModel]) -> set[str]:
    """De velden die expliciet in de TOML horen te staan.

    Een veld met `None` als standaardwaarde valt af: TOML kent geen null, dus zo'n veld
    is niet expliciet op zijn default te zetten. Dat zijn de optionele bronpaden
    (`bgt`, `ahn_dtm`) en de twee naamgevingspatronen -- geen drempels.
    """
    return {
        naam
        for naam, veld in model.model_fields.items()
        if veld.get_default(call_default_factory=True) is not None
    }


@pytest.mark.parametrize(("sectie", "model"), DREMPELMODELLEN, ids=[s for s, _ in DREMPELMODELLEN])
@pytest.mark.parametrize(("pad", "herkomst"), CONFIGBESTANDEN)
def test_elke_drempel_staat_expliciet_in_de_toml(
    pad: Path, herkomst: str, sectie: str, model: type[BaseModel]
) -> None:
    """Issue #28: geen enkele drempel mag stilzwijgend op een Python-default vallen.

    Vergelijkt de veldnamen van het model met de sleutels die daadwerkelijk onder de
    sectie in het bestand staan (via `tomllib`, niet via de geladen `CheckConfig` --
    die vult ontbrekende velden juist met de default op en zou het verschil
    verbergen). Een nieuw veld dat hier niet bij komt, of een hernoeming die de TOML
    niet meekrijgt, maakt deze test rood.
    """
    verwacht = _verplichte_velden(model)
    aanwezig = set(tomllib.loads(pad.read_text(encoding="utf-8"))[sectie])

    assert verwacht and not (verwacht - aanwezig), (
        f"{herkomst} [{sectie}] mist {sorted(verwacht - aanwezig)}"
    )
    assert not (onbekend := aanwezig - set(model.model_fields)), (
        f"{herkomst} [{sectie}] draagt onbekende velden {sorted(onbekend)}"
    )


def _drempelafwijkingen(
    pad: Path, negeer: frozenset[str] | set[str] = frozenset()
) -> dict[str, tuple[object, object]]:
    """Per drempel in `[drempels]` de afwijking van de `CheckThresholds`-default.

    Op type af en niet alleen op waarde: `1` en `1.0` zijn in TOML twee dingen, en een
    int waar een float hoort valt in pydantic stil goed.
    """
    standaard = CheckThresholds()
    aanwezig = tomllib.loads(pad.read_text(encoding="utf-8"))["drempels"]
    return {
        veld: (waarde, verwacht)
        for veld, waarde in aanwezig.items()
        if veld not in negeer
        and ((verwacht := getattr(standaard, veld)) != waarde or type(waarde) is not type(verwacht))
    }


def test_de_meegeleverde_drempels_zijn_de_defaults() -> None:
    """`checks.toml` *is* de standaard, dus zijn waarden horen die van Python te zijn.

    De veldnamen bewaakt de test hierboven; hier gaan de 53 getallen zelf langs. Zonder
    deze test staan er drie kopieen van dezelfde reeks -- de Python-defaults, dit
    bestand en de projectconfiguratie -- waarvan er maar een bewaakt wordt: wie morgen
    `bob_sprong_m` in `checkconfig.py` verlegt, ziet geen van beide TOML's volgen.
    Op type af, niet alleen op waarde: `1` en `1.0` zijn in TOML twee dingen.
    """
    afwijkend = _drempelafwijkingen(default_check_config_path())

    assert not afwijkend, (
        "src/nlriochecker/checks.toml [drempels] wijkt af van de CheckThresholds-defaults "
        f"(veld: bestand, Python): {afwijkend}. Het meegeleverde bestand is de default; "
        "pas ze samen aan."
    )


def test_de_projectdrempels_wijken_alleen_bewust_af() -> None:
    """Een projectconfiguratie mag afwijken -- maar dan opgeschreven, niet stil.

    `load_check_config` voegt niets samen: een projectconfiguratie vervangt de
    meegeleverde in haar geheel. Een drempel die daar per ongeluk achterblijft bij een
    wijziging in `checkconfig.py` valt dus nergens op. Wie er bewust een verlegt, zet
    hem op `BEWUSTE_AFWIJKINGEN` met de reden erbij.
    """
    afwijkend = _drempelafwijkingen(PROJECTCONFIG, negeer=set(BEWUSTE_AFWIJKINGEN))

    assert not afwijkend, (
        "configs/dewoldenhoogeveen.toml [drempels] wijkt onaangekondigd af van de "
        f"CheckThresholds-defaults (veld: bestand, Python): {afwijkend}. Zet de "
        "afwijking met haar reden op BEWUSTE_AFWIJKINGEN, of zet de waarde terug."
    )


def test_bewuste_afwijking_wijkt_ook_werkelijk_af() -> None:
    """De andere richting: een afwijking die geen afwijking meer is hoort van de lijst.

    Zonder deze test blijft `BEWUSTE_AFWIJKINGEN` staan als een lijst keuzes die niemand
    meer maakt, en dekt hij stilzwijgend de volgende drift op datzelfde veld af.
    """
    nog_afwijkend = _drempelafwijkingen(PROJECTCONFIG)
    aanwezig = tomllib.loads(PROJECTCONFIG.read_text(encoding="utf-8"))["drempels"]

    for veld, reden in BEWUSTE_AFWIJKINGEN.items():
        assert veld in aanwezig, f"{veld} staat op BEWUSTE_AFWIJKINGEN maar niet in [drempels]"
        assert veld in nog_afwijkend, (
            f"{veld} is gelijk aan de default; haal hem uit BEWUSTE_AFWIJKINGEN ({reden})"
        )


# Sleutels van `[klassen]` waarvoor `configs/dewoldenhoogeveen.toml` bewust van
# `src/nlriochecker/checks.toml` afwijkt, met de reden. Vandaag leeg: De Wolden en Hoogeveen draait
# op dezelfde klassenlijsten. Een project *mag* afwijken -- dat is juist waar een
# projectconfiguratie voor dient -- maar dan als bewuste daad die hier opgeschreven
# staat, niet als een lijst die stilzwijgend uit elkaar loopt.
BEWUSTE_KLASSEN_AFWIJKINGEN: dict[str, str] = {}


def _klassenafwijkingen(
    negeer: frozenset[str] | set[str] = frozenset(),
) -> dict[str, tuple[object, object]]:
    """Per sleutel in `[klassen]` de afwijking tussen checks.toml en de projectconfig.

    Vergelijkt de twee `[klassen]`-blokken sleutel voor sleutel; het nest
    `[klassen.stelseltypen]` gaat als deelwoordenboek mee. Een sleutel die maar in een
    van beide bestanden staat telt ook als afwijking.
    """
    standaard = tomllib.loads(default_check_config_path().read_text(encoding="utf-8"))["klassen"]
    project = tomllib.loads(PROJECTCONFIG.read_text(encoding="utf-8"))["klassen"]
    return {
        sleutel: (project.get(sleutel), standaard.get(sleutel))
        for sleutel in standaard.keys() | project.keys()
        if sleutel not in negeer and project.get(sleutel) != standaard.get(sleutel)
    }


def test_de_klassenlijsten_zijn_in_beide_bestanden_gelijk() -> None:
    """De `[klassen]`-blokken van beide configbestanden horen gelijk te blijven.

    Niets dwong dat af (issue #52): wie een klasse aan de een toevoegt en de ander
    vergeet, krijgt een projectrun die stil andere objecten selecteert dan de
    meegeleverde configuratie. `test_checkconfig` bewaakt sinds #28 de drempels op
    waarde en type, maar de klassenlijsten vielen erbuiten. Een bewuste afwijking
    hoort met haar reden op `BEWUSTE_KLASSEN_AFWIJKINGEN`.
    """
    afwijkend = _klassenafwijkingen(negeer=set(BEWUSTE_KLASSEN_AFWIJKINGEN))

    assert not afwijkend, (
        "configs/dewoldenhoogeveen.toml [klassen] wijkt onaangekondigd af van "
        f"src/nlriochecker/checks.toml (sleutel: project, standaard): {afwijkend}. Zet de "
        "afwijking met haar reden op BEWUSTE_KLASSEN_AFWIJKINGEN, of maak de lijsten gelijk."
    )


def test_bewuste_klassenafwijking_wijkt_ook_werkelijk_af() -> None:
    """De andere richting: een afwijking die geen afwijking meer is hoort van de lijst.

    Zonder deze test blijft `BEWUSTE_KLASSEN_AFWIJKINGEN` staan als een lijst keuzes die
    niemand meer maakt, en dekt hij stilzwijgend de volgende drift op datzelfde veld af.
    """
    nog_afwijkend = _klassenafwijkingen()

    for sleutel, reden in BEWUSTE_KLASSEN_AFWIJKINGEN.items():
        assert sleutel in nog_afwijkend, (
            f"{sleutel} staat op BEWUSTE_KLASSEN_AFWIJKINGEN maar is gelijk in beide "
            f"bestanden; haal hem eruit ({reden})"
        )


def test_vulwaarden_uit_de_standaardconfig() -> None:
    """De vulwaarde-leesregel staat als projectconfiguratie in `[vulwaarden]`."""
    config = load_check_config()

    assert config.vulwaarden.hoogte_kenmerken == [
        "BobBeginpuntLeiding",
        "BobEindpuntLeiding",
        "Maaiveldhoogte",
        "Putdekselniveau",
    ]
    assert config.vulwaarden.hoogte_band_m == 0.01


def test_ondersteunde_kenmerken_volgen_de_vier_geladen_klassen() -> None:
    """`VULWAARDE_KENMERKEN` is precies wat `markeer_vulwaarden` inspecteert.

    De lijst hoort bij de afnemer sinds de leeslaag naar gwsw-orox-helpers verhuisde:
    `markeer_vulwaarden` neemt de kenmerken als parameter en kent deze keuze niet meer.
    De config weigert elke andere naam; loopt deze lijst uit de pas met de klassen die
    de lader in de vier hoogtevelden zet, dan zou ze een geldig kenmerk weigeren of een
    inert kenmerk toelaten.
    """
    klassen = (
        KLASSE_MAAIVELDHOOGTE,
        KLASSE_PUTDEKSELNIVEAU,
        KLASSE_BOB_BEGIN,
        KLASSE_BOB_EIND,
    )

    assert VULWAARDE_KENMERKEN == {str(klasse).rsplit("/", 1)[-1] for klasse in klassen}
