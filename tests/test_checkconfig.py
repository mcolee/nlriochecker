"""Tests voor de projectconfiguratie van de check-engine."""

from __future__ import annotations

import ast
import re
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
# De projectconfiguraties uit `configs/`; sinds issue #163 overlays op de standaard. De
# drifttests globben deze map zodat een tweede gemeenteconfig er vanzelf onder valt.
PROJECTCONFIGS = sorted((Path(__file__).resolve().parents[1] / "configs").glob("*.toml"))

# Een minimale, geldige projectconfig; `{extra}` haakt eventuele extra secties aan.
_MINIMALE_CONFIG = (
    "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
    "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n{extra}"
)


def _config_met_uitzonderingen(tmp_path: Path, json_inhoud: str | None, verwijzing: str) -> Path:
    """Schrijft een config die naar een uitzonderingenbestand `verwijzing` wijst.

    Is `json_inhoud` niet None, dan komt er een `uitz.json` naast; anders blijft die weg,
    om het ontbrekende-bestand-geval te toetsen.
    """
    if json_inhoud is not None:
        (tmp_path / "uitz.json").write_text(json_inhoud, encoding="utf-8")
    pad = tmp_path / "config.toml"
    pad.write_text(
        _MINIMALE_CONFIG.format(extra=f'[rapport]\nuitzonderingen = "{verwijzing}"\n'),
        encoding="utf-8",
    )
    return pad


def test_config_met_utf8_bom_laadt(tmp_path: Path) -> None:
    """Een in Excel/Notepad/PowerShell aangeraakte config draagt vaak een UTF-8-BOM (#156)."""
    pad = tmp_path / "met_bom.toml"
    pad.write_bytes(b"\xef\xbb\xbf" + _MINIMALE_CONFIG.format(extra="").encode("utf-8"))

    config = load_check_config(pad)

    assert config.klassen.put == ["Put"]


def test_standaardconfig_laadt() -> None:
    config = load_check_config()

    assert default_check_config_path().exists()
    assert config.klassen.put == ["Put"]
    assert config.drempels.snapping_tolerantie_m == 0.10
    assert config.drempels.dubbele_put_tolerantie_m == 0.30


def test_gemengd_zonder_overstort_buffer_heeft_een_default() -> None:
    """De bufferafstand van de RVZ-006-vlakken in de laag `vlakken` (#25, #75, #98).

    Projectkeuze zonder externe bron; 10 m buffert elke strenglijn tot een lint van
    20 m breed, zodat de strengen van een deelstelsel langs een straat samenvloeien.
    """
    assert load_check_config().drempels.gemengd_zonder_overstort_buffer_m == 10.0


def test_maximale_strenglengte_volgt_de_ontologie() -> None:
    """De strenglengtegrenzen zijn de GWSW-ontologiegrenzen, niet 200 m (issue #35).

    `Dt_LengteLeiding` declareert een bereik van 1-75 m. De oude drempel 200 keurde
    strengen goed die de SHACL-nulmeting in hetzelfde rapport afkeurde (op De Wolden en Hoogeveen
    431 vrijvervalstrengen); GWSW is leidend. De ondergrens 1 m valt al samen met de
    ontologie. ATTR-008 las deze twee drempels tot issue #90; die check is geschrapt
    omdat de vorm `LengteLeiding_val` hem volledig dekt (BO-61), dus vandaag leest geen
    check ze. De sleutels blijven wel in de drie configbestanden staan, en dan hoort hun
    waarde de ontologiegrens te blijven in plaats van stil terug te lopen.
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
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n"
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
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n",
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
        "[nulmeting]\nvereiste_cfk = ['Hyd']\n[koppelregels]\n"
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
    """Een typefout in `onderdruk_checks` zou stil niets onderdrukken (issue #65).

    De controle leunt sinds issue #160 op de check-ID's die de beller meegeeft
    (`bekende_check_ids`), niet meer op een import van `nlriochecker.checks` in
    `checkconfig` -- dat sloot een importkring. De toetsrun geeft er `set(REGISTRY)`
    voor; deze test geeft precies dezelfde verzameling.
    """
    from nlriochecker.checks import REGISTRY

    bron = default_check_config_path().read_text(encoding="utf-8")
    pad = tmp_path / "checks.toml"
    pad.write_text(
        bron.replace("onderdruk_checks = []", 'onderdruk_checks = ["XYZ-999"]'), encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="XYZ-999"):
        load_check_config(pad, bekende_check_ids=set(REGISTRY))


def test_onbekend_onderdruk_check_id_glipt_door_zonder_bekende_ids(tmp_path: Path) -> None:
    """Zonder `bekende_check_ids` valideert het laden `onderdruk_checks` niet (issue #160).

    De subcommando's die geen rapport met onderdrukking schrijven hebben de controle
    niet nodig, en `checkconfig` mag `nlriochecker.checks` niet importeren om haar te
    kunnen doen. De toetsrun -- de enige die onderdrukt -- geeft de ID's wél mee, en de
    test hierboven bewaakt dat pad.
    """
    bron = default_check_config_path().read_text(encoding="utf-8")
    pad = tmp_path / "checks.toml"
    pad.write_text(
        bron.replace("onderdruk_checks = []", 'onderdruk_checks = ["XYZ-999"]'), encoding="utf-8"
    )

    config = load_check_config(pad)

    assert config.rapport.onderdruk_checks == ["XYZ-999"]


def test_de_projectconfig_onderdrukt_het_mechanische_riool_en_de_pompunit() -> None:
    """De Wolden: de twee `[klassen] mechanisch`-wortels plus `Pompunit`, de pompput van
    de drukriolering (issue #56, #65; `Pompunit` is een `Rioolput` in het mechanische
    stelsel, BO-55)."""
    config = load_check_config(PROJECTCONFIG)

    assert config.rapport.onderdruk_klassen == [*config.klassen.mechanisch, "Pompunit"]
    assert config.rapport.onderdruk_checks == []


def test_kritieke_klassen_bepalen_de_hoogste_prioriteit() -> None:
    """Een fout op een overstort weegt zwaarder dan een fout op een gewone put."""
    assert "Overstortput" in load_check_config().klassen.kritiek


def _schrijf(pad: Path, inhoud: str) -> Path:
    """Schrijft een configbestand en geeft het pad terug."""
    pad.write_text(inhoud, encoding="utf-8")
    return pad


class TestOverlay:
    """Issue #163: `--projectconfig` als overlay met `basis = "standaard"` (BO-98)."""

    def test_een_overlay_is_gelijk_aan_de_volledige_kopie(self, tmp_path: Path) -> None:
        """Een overlay met een paar sleutels geeft dezelfde config als een volle kopie.

        De volle kopie is de meegeleverde checks.toml met dezelfde twee sleutels
        (een scalar in `[drempels]`, een pad in `[bronnen]`) veranderd; de overlay
        noemt alleen die twee plus `basis`. `model_dump` vergelijkt elke sectie.
        """
        standaard = default_check_config_path().read_text(encoding="utf-8")
        gewijzigd = standaard.replace(
            "snapping_tolerantie_m = 0.10", "snapping_tolerantie_m = 0.5"
        ).replace('map = "data/gis_koekangerveld"', 'map = "data/anders"')
        volledig = _schrijf(tmp_path / "vol.toml", gewijzigd)
        overlay = _schrijf(
            tmp_path / "overlay.toml",
            'basis = "standaard"\n'
            "[drempels]\nsnapping_tolerantie_m = 0.5\n"
            '[bronnen]\nmap = "data/anders"\n',
        )

        assert load_check_config(overlay).model_dump() == load_check_config(volledig).model_dump()

    def test_niet_overschreven_secties_komen_uit_de_standaard(self, tmp_path: Path) -> None:
        """Een overlay draagt de rest van de standaard: hele secties en losse velden."""
        overlay = _schrijf(
            tmp_path / "o.toml", 'basis = "standaard"\n[drempels]\nbob_sprong_m = 0.30\n'
        )

        config = load_check_config(overlay)

        assert config.drempels.bob_sprong_m == 0.30
        assert config.drempels.snapping_tolerantie_m == 0.10
        assert config.klassen.put == ["Put"]
        assert config.nulmeting.vereiste_cfk == ["Hyd", "MdsPlan", "MdsProj"]

    def test_zonder_basis_faalt_een_kale_overlay_zoals_vandaag(self, tmp_path: Path) -> None:
        """Zonder `basis` blijft een bestand een volledige config: ontbrekende sectie = fout.

        Precies het gedrag van vóór #163: de acht-sleutel-overlay zonder `basis` mist
        `klassen`, `koppelregels` en `nulmeting` en valt om.
        """
        overlay = _schrijf(tmp_path / "o.toml", '[bronnen]\nmap = "data/anders"\n')

        with pytest.raises(ConfigError):
            load_check_config(overlay)

    def test_een_andere_basiswaarde_is_een_configfout(self, tmp_path: Path) -> None:
        """Alleen `basis = "standaard"` bestaat; de fout noemt de toegestane waarde."""
        overlay = _schrijf(tmp_path / "o.toml", 'basis = "anders"\n')

        with pytest.raises(ConfigError, match="standaard"):
            load_check_config(overlay)

    def test_een_lijst_wordt_als_geheel_vervangen(self, tmp_path: Path) -> None:
        """De staffel is een lijst (tabel-array): de overlay vervangt hem helemaal.

        De standaard heeft vier treden; een overlay met één trede laat er één over,
        geen deep-merge op index.
        """
        overlay = _schrijf(
            tmp_path / "o.toml",
            'basis = "standaard"\n[[verhang_staffel]]\nminimaal_verhang_een_op = 42\n',
        )

        staffel = load_check_config(overlay).verhang_staffel

        assert len(staffel) == 1
        assert staffel[0].minimaal_verhang_een_op == 42
        assert staffel[0].tot_diameter_mm is None

    def test_een_tabel_wordt_sleutel_voor_sleutel_gemerged(self, tmp_path: Path) -> None:
        """Eén sleutel in `[drempels]` overschrijft; de rest van de tabel blijft standaard."""
        overlay = _schrijf(
            tmp_path / "o.toml", 'basis = "standaard"\n[drempels]\nbob_sprong_m = 0.30\n'
        )

        drempels = load_check_config(overlay).drempels

        assert drempels.bob_sprong_m == 0.30
        assert drempels.nul_lengte_m == 0.01

    def test_een_typfout_sectie_wordt_geweigerd(self, tmp_path: Path) -> None:
        """`extra="forbid"` weigert een verkeerd gespelde sectie ná de merge."""
        overlay = _schrijf(
            tmp_path / "o.toml", 'basis = "standaard"\n[drampels]\nbob_sprong_m = 0.30\n'
        )

        with pytest.raises(ConfigError):
            load_check_config(overlay)

    def test_de_overschreven_paden_dragen_basis_en_projectwaarde(self, tmp_path: Path) -> None:
        """De config draagt per overschreven bladpad (basiswaarde, projectwaarde)."""
        overlay = _schrijf(
            tmp_path / "o.toml", 'basis = "standaard"\n[drempels]\nbob_sprong_m = 0.30\n'
        )

        assert load_check_config(overlay).overschreven_paden == [
            ("drempels.bob_sprong_m", 0.25, 0.30)
        ]

    def test_een_volledige_kopie_draagt_geen_overschreven_paden(self) -> None:
        """Zonder `basis` is er geen overlay; `overschreven_paden` is dan None."""
        assert load_check_config().overschreven_paden is None


def test_de_projectconfig_is_een_overlay_met_acht_overschreven_sleutels() -> None:
    """`configs/dewoldenhoogeveen.toml` is sinds #163 een overlay op de standaard.

    Precies de acht sleutels die van Koekangerveld naar De Wolden en Hoogeveen
    verschillen (zeven in `[bronnen]`, plus `rapport.onderdruk_klassen`).
    """
    paden = load_check_config(PROJECTCONFIG).overschreven_paden

    assert paden is not None
    assert [pad for pad, _, _ in paden] == [
        "bronnen.map",
        "bronnen.bag_pand",
        "bronnen.nwb_wegvakken",
        "bronnen.top10nl",
        "bronnen.studiegebied",
        "bronnen.ahn_dtm",
        "bronnen.bgt_putdeksellagen",
        "rapport.onderdruk_klassen",
    ]
    assert ("bronnen.map", "data/gis_koekangerveld", "data/gis_dewoldenhoogeveen") in paden


class TestUitzonderingen:
    """Issue #132: het uitzonderingenbestand met geaccepteerde bevindingen."""

    def test_zonder_verwijzing_is_er_geen_bestand_en_geen_record(self) -> None:
        """De standaardconfig wijst geen uitzonderingenbestand aan."""
        rapport = load_check_config().rapport

        assert rapport.uitzonderingen is None
        assert rapport.uitzonderingen_records == []

    def test_een_geldig_bestand_wordt_gelezen(self, tmp_path: Path) -> None:
        """De records reizen mee tot in de config, klaar voor de meldingenstroom."""
        pad = _config_met_uitzonderingen(
            tmp_path,
            '[{"melding_id": "abc123", "reden": "tegenverhang klopt", '
            '"waarde_snapshot": "0.02 m", "check_id": "HGT-006"}]',
            "uitz.json",
        )

        rapport = load_check_config(pad).rapport

        assert rapport.uitzonderingen == "uitz.json"
        assert len(rapport.uitzonderingen_records) == 1
        record = rapport.uitzonderingen_records[0]
        assert record.melding_id == "abc123"
        assert record.reden == "tegenverhang klopt"
        assert record.waarde_snapshot == "0.02 m"

    def test_het_pad_is_relatief_aan_het_configbestand(self, tmp_path: Path) -> None:
        """Aanname 1: config-relatief, niet t.o.v. de werkmap.

        De config staat in een submap; het bestand ernaast is `uitz.json`. Zou het pad
        t.o.v. de werkmap resolven, dan werd het hier niet gevonden.
        """
        sub = tmp_path / "project"
        sub.mkdir()
        pad = _config_met_uitzonderingen(sub, '[{"melding_id": "x", "reden": "ok"}]', "uitz.json")

        assert load_check_config(pad).rapport.uitzonderingen_records[0].melding_id == "x"

    def test_ontbrekend_bestand_faalt(self, tmp_path: Path) -> None:
        pad = _config_met_uitzonderingen(tmp_path, None, "weg.json")

        with pytest.raises(ConfigError, match="kan niet gelezen worden"):
            load_check_config(pad)

    def test_ongeldige_json_faalt(self, tmp_path: Path) -> None:
        pad = _config_met_uitzonderingen(tmp_path, "{ dit is geen json", "uitz.json")

        with pytest.raises(ConfigError, match="geen geldige JSON"):
            load_check_config(pad)

    def test_geen_lijst_faalt(self, tmp_path: Path) -> None:
        """Eén top-level JSON-lijst; een los object is geen bestand van records."""
        pad = _config_met_uitzonderingen(tmp_path, '{"melding_id": "a", "reden": "b"}', "uitz.json")

        with pytest.raises(ConfigError, match="JSON-lijst van records"):
            load_check_config(pad)

    def test_record_zonder_melding_id_faalt(self, tmp_path: Path) -> None:
        pad = _config_met_uitzonderingen(tmp_path, '[{"reden": "zonder sleutel"}]', "uitz.json")

        with pytest.raises(ConfigError, match="melding_id"):
            load_check_config(pad)

    def test_record_zonder_reden_faalt(self, tmp_path: Path) -> None:
        pad = _config_met_uitzonderingen(tmp_path, '[{"melding_id": "abc"}]', "uitz.json")

        with pytest.raises(ConfigError, match="reden"):
            load_check_config(pad)

    def test_een_onbekende_sleutel_faalt(self, tmp_path: Path) -> None:
        """Met de hand geschreven; een tikfout in een sleutelnaam hoort luid te falen."""
        pad = _config_met_uitzonderingen(
            tmp_path, '[{"melding_id": "a", "reden": "b", "waarde_snapshott": "x"}]', "uitz.json"
        )

        with pytest.raises(ConfigError):
            load_check_config(pad)


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

# De standaard (`checks.toml`, geen overlay) plus elke projectconfig uit `configs/`
# (sinds #163 overlays). Het derde veld zegt of het een overlay is: alleen de standaard
# hoort elk drempelveld expliciet te dragen, een overlay draagt alleen wat hij overschrijft.
CONFIGBESTANDEN = [
    pytest.param(
        default_check_config_path(), "src/nlriochecker/checks.toml", False, id="checks.toml"
    ),
    *[pytest.param(pad, f"configs/{pad.name}", True, id=pad.name) for pad in PROJECTCONFIGS],
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
@pytest.mark.parametrize(("pad", "herkomst", "is_overlay"), CONFIGBESTANDEN)
def test_elke_drempel_staat_expliciet_in_de_toml(
    pad: Path, herkomst: str, is_overlay: bool, sectie: str, model: type[BaseModel]
) -> None:
    """Issue #28: in de standaard mag geen drempel stilzwijgend op een Python-default vallen.

    Vergelijkt de veldnamen van het model met de sleutels die daadwerkelijk onder de
    sectie in het bestand staan (via `tomllib`, niet via de geladen `CheckConfig` --
    die vult ontbrekende velden juist met de default op en zou het verschil
    verbergen). Een nieuw veld dat hier niet bij komt, of een hernoeming die de TOML
    niet meekrijgt, maakt deze test rood.

    Voor een overlay (issue #163) geldt de volledigheidseis niet: hij draagt bewust
    alleen de sleutels die hij overschrijft. Wat wél voor beide geldt is dat een
    aanwezige sectie geen onbekend veld mag dragen -- een typfout hoort luid te falen.
    """
    verwacht = _verplichte_velden(model)
    aanwezig = set(tomllib.loads(pad.read_text(encoding="utf-8")).get(sectie, {}))

    if not is_overlay:
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
    # Sinds issue #163 draagt een overlay `[drempels]` niet altijd (De Wolden overschrijft
    # er geen). `.get` levert dan {} -- geen afwijkingen. Rauw uit het bestand en niet uit
    # de gemergede config, zodat het int/float-onderscheid (`1` vs `1.0`) hier zichtbaar
    # blijft; omdat de standaard gelijk is aan de defaults (bewaakt door
    # `test_de_meegeleverde_drempels_zijn_de_defaults`) zijn de eigen [drempels]-afwijkingen
    # van een overlay gelijk aan die van zijn gemergede config.
    aanwezig = tomllib.loads(pad.read_text(encoding="utf-8")).get("drempels", {})
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
    aanwezig = tomllib.loads(PROJECTCONFIG.read_text(encoding="utf-8")).get("drempels", {})

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
    pad: Path, negeer: frozenset[str] | set[str] = frozenset()
) -> dict[str, tuple[object, object]]:
    """Per sleutel in `[klassen]` de afwijking tussen de standaard en de projectconfig.

    Sinds issue #163 is een projectconfig een overlay die `[klassen]` niet zelf draagt;
    de vergelijking gaat daarom over de *gemergede* config (`load_check_config`) en niet
    over het rauwe bestand -- anders zou elke klasse als "ontbreekt in het project"
    lezen. Beide kanten via `model_dump`, zodat een veld met een default dat in geen van
    beide TOML's staat (bv. `vervallen`) aan beide zijden gelijk telt. Het nest
    `[klassen.stelseltypen]` gaat als deelwoordenboek mee.
    """
    standaard = load_check_config().klassen.model_dump()
    project = load_check_config(pad).klassen.model_dump()
    return {
        sleutel: (project.get(sleutel), standaard.get(sleutel))
        for sleutel in standaard.keys() | project.keys()
        if sleutel not in negeer and project.get(sleutel) != standaard.get(sleutel)
    }


@pytest.mark.parametrize("pad", PROJECTCONFIGS, ids=[p.name for p in PROJECTCONFIGS])
def test_de_klassenlijsten_zijn_in_beide_bestanden_gelijk(pad: Path) -> None:
    """De gemergede `[klassen]` van een projectconfig hoort gelijk te zijn aan de standaard.

    Niets dwong dat af (issue #52): wie een klasse aan de een toevoegt en de ander
    vergeet, krijgt een projectrun die stil andere objecten selecteert dan de
    meegeleverde configuratie. Sinds issue #163 erft een overlay de klassen; een bewuste
    afwijking hoort met haar reden op `BEWUSTE_KLASSEN_AFWIJKINGEN`.
    """
    afwijkend = _klassenafwijkingen(pad, negeer=set(BEWUSTE_KLASSEN_AFWIJKINGEN))

    assert not afwijkend, (
        f"configs/{pad.name} [klassen] wijkt (na de overlay-merge) onaangekondigd af van "
        f"src/nlriochecker/checks.toml (sleutel: project, standaard): {afwijkend}. Zet de "
        "afwijking met haar reden op BEWUSTE_KLASSEN_AFWIJKINGEN, of maak de lijsten gelijk."
    )


@pytest.mark.parametrize("pad", PROJECTCONFIGS, ids=[p.name for p in PROJECTCONFIGS])
def test_bewuste_klassenafwijking_wijkt_ook_werkelijk_af(pad: Path) -> None:
    """De andere richting: een afwijking die geen afwijking meer is hoort van de lijst.

    Zonder deze test blijft `BEWUSTE_KLASSEN_AFWIJKINGEN` staan als een lijst keuzes die
    niemand meer maakt, en dekt hij stilzwijgend de volgende drift op datzelfde veld af.
    """
    nog_afwijkend = _klassenafwijkingen(pad)

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


# --- issue #160: elk ext_*_m-veld dat een `nabij`-aanroep voedt zit in ext_zoekafstand_max_m ---

CHECKS_DIR = Path(__file__).resolve().parents[1] / "src" / "nlriochecker" / "checks"
CHECKCONFIG_BRON = (
    Path(__file__).resolve().parents[1] / "src" / "nlriochecker" / "checkconfig.py"
).read_text(encoding="utf-8")
_EXT_VELD = re.compile(r"^ext_\w+_m$")


def _funcvan(tree: ast.AST) -> dict[int, ast.FunctionDef | None]:
    """Per knoop de dichtstbijzijnde omvattende functie (of None op moduleniveau)."""
    mapping: dict[int, ast.FunctionDef | None] = {}

    def bind(node: ast.AST, func: ast.FunctionDef | None) -> None:
        mapping[id(node)] = func
        binnen = node if isinstance(node, ast.FunctionDef) else func
        for kind in ast.iter_child_nodes(node):
            bind(kind, binnen)

    for top in ast.iter_child_nodes(tree):
        bind(top, None)
    return mapping


def _drempelveld(node: ast.expr) -> str | None:
    """De veldnaam als `node` een `<...>.drempels.ext_*_m` leest, anders None."""
    if (
        isinstance(node, ast.Attribute)
        and _EXT_VELD.match(node.attr)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "drempels"
    ):
        return node.attr
    return None


def _lokale_drempels(func: ast.FunctionDef) -> dict[str, str]:
    """Per lokale variabele het `ext_*_m`-veld waaruit ze toegewezen is."""
    toewijzingen: dict[str, str] = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and (veld := _drempelveld(node.value)) is not None:
            for doel in node.targets:
                if isinstance(doel, ast.Name):
                    toewijzingen[doel.id] = veld
    return toewijzingen


def _naam_van_call(call: ast.Call) -> str | None:
    """De aangeroepen naam van een call (`f(...)` of `x.f(...)`)."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def nabij_gevoede_velden(bron: str) -> set[str]:
    """De `ext_*_m`-velden die als tweede argument van een `.nabij(...)`-aanroep landen.

    Uit de code afgeleid, niet aangenomen (issue #160). Een `.nabij`-argument is een
    variabele; die wordt teruggevolgd naar de `drempels.ext_*_m`-toewijzing in dezelfde
    functie, en anders -- als ze een parameter is -- via de aanroepplekken van die functie
    naar de toewijzing bij de aanroeper. Zo vindt hij zowel EXT-007 (`afstand` lokaal) als
    EXT-003 (`buffer` een parameter van `_zoek_kruisingen`, gezet in `kruisingstoets`).
    """
    tree = ast.parse(bron)
    functie_van = _funcvan(tree)
    velden: set[str] = set()

    def resolveer(var: str, func: ast.FunctionDef | None, diepte: int = 0) -> set[str]:
        if func is None or diepte > 4:
            return set()
        lokaal = _lokale_drempels(func)
        if var in lokaal:
            return {lokaal[var]}
        params = [arg.arg for arg in func.args.args]
        if var in params:
            index = params.index(var)
            gevonden: set[str] = set()
            for call in ast.walk(tree):
                if (
                    isinstance(call, ast.Call)
                    and _naam_van_call(call) == func.name
                    and index < len(call.args)
                    and isinstance(call.args[index], ast.Name)
                ):
                    gevonden |= resolveer(
                        call.args[index].id, functie_van.get(id(call)), diepte + 1
                    )
            return gevonden
        return set()

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "nabij"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Name)
        ):
            velden |= resolveer(node.args[1].id, functie_van.get(id(node)))
    return velden


def alle_nabij_gevoede_velden() -> set[str]:
    """De `ext_*_m`-velden die een `.nabij(...)` in *elke* checkmodule voedt (issue #171).

    De sweep leest sinds issue #160 wel de code van beide kanten, maar keek alleen naar
    `extern.py`; een `.nabij`-aanroep met een niet-gedekt veld in een andere checkmodule zou
    hem zo ontgaan. De verzameling loopt daarom over `checks/*.py` en verenigt het resultaat
    per module -- per module, want de argument-terugkoppeling van `nabij_gevoede_velden`
    werkt binnen één AST-boom.
    """
    velden: set[str] = set()
    for pad in sorted(CHECKS_DIR.glob("*.py")):
        velden |= nabij_gevoede_velden(pad.read_text(encoding="utf-8"))
    return velden


def zoekafstand_velden(bron: str) -> set[str]:
    """De `self.ext_*_m`-velden die in de `ext_zoekafstand_max_m`-property samenkomen."""
    tree = ast.parse(bron)
    velden: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "ext_zoekafstand_max_m":
            for kind in ast.walk(node):
                if (
                    isinstance(kind, ast.Attribute)
                    and _EXT_VELD.match(kind.attr)
                    and isinstance(kind.value, ast.Name)
                    and kind.value.id == "self"
                ):
                    velden.add(kind.attr)
    return velden


def test_elk_nabij_veld_zit_in_de_zoekafstand() -> None:
    """`ext_zoekafstand_max_m` dekt elk veld waarmee een EXT-check in een bron kijkt (#160).

    De dekkingspoort verruimt het bereik van de externe bronnen met deze afstand. Voedt een
    `.nabij(...)` een veld dat de handmatige `max()` niet meetelt, dan zoekt die check
    verder dan het geladen bereik en mist hij objecten net binnen -- zonder dat iets dat
    meldt. De velden komen uit de code van beide kanten, niet uit een aanname, en uit elke
    checkmodule -- niet alleen `extern.py` (issue #171).
    """
    gevoed = alle_nabij_gevoede_velden()
    gedekt = zoekafstand_velden(CHECKCONFIG_BRON)

    assert gevoed, "geen enkel `.nabij`-veld gevonden; is de sweep stuk?"
    assert gevoed <= gedekt, f"niet gedekt door ext_zoekafstand_max_m: {sorted(gevoed - gedekt)}"


def test_elk_nabij_veld_is_ook_op_waarde_niet_ruimer_dan_de_zoekafstand() -> None:
    """En op waarde: geen nabij-veld staat verder dan `ext_zoekafstand_max_m` (default)."""
    drempels = CheckThresholds()
    for veld in alle_nabij_gevoede_velden():
        assert getattr(drempels, veld) <= drempels.ext_zoekafstand_max_m


def test_de_nabij_sweep_kan_werkelijk_afgaan() -> None:
    """De tegenproef: een nabij-veld buiten de zoekafstand wordt gezien als een gat.

    Synthetische bron, geen echt bestand. Voegt iemand een `.nabij`-aanroep toe die
    gevoed wordt door een veld dat `ext_zoekafstand_max_m` niet meetelt, dan valt de
    hoofdtest -- dit bewijst dat de sweep dat kan zien.
    """
    extern = "def run(self):\n    a = self.config.drempels.ext_nieuw_m\n    laag.nabij(p, a)\n"
    zoekafstand = "def ext_zoekafstand_max_m(self):\n    return max(self.ext_pand_buffer_m)\n"

    gevoed = nabij_gevoede_velden(extern)

    assert gevoed == {"ext_nieuw_m"}
    assert not gevoed <= zoekafstand_velden(zoekafstand)
