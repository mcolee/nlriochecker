"""Tests voor de synthesesectie: de rode draad door de bevindingen."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from helpers_melding import melding
from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.uitvoer.melding import Melding, bouw_meldingen
from nlriochecker.uitvoer.synthese import rode_draad

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
RUNDATUM = date(2026, 8, 16)


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _run(bestand: str, config: CheckConfig | None = None) -> CheckRun:
    """Draait alle checks op een fixture."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=config or _config())
    return run_checks(context)


def _tekst(bestand: str, config: CheckConfig | None = None) -> str:
    """De rode draad als een enkele tekst."""
    run = _run(bestand, config)
    return "\n".join(rode_draad(run, bouw_meldingen(run, RUNDATUM)))


def test_zonder_bevindingen_komt_er_geen_kop() -> None:
    """Een lege sectie is erger dan geen sectie."""
    assert rode_draad(_run("schoon.ttl"), []) == []


def test_omgekeerde_registratie_wordt_als_gezamenlijke_oorzaak_benoemd() -> None:
    """Stijgt de bodem bij veel strengen in de afvoerrichting, dan is dat een oorzaak.

    De fixture heeft een streng die administratief de verkeerde kant op staat; dat
    verklaart tegelijk de NET-003-, NET-001- en HGT-006-bevinding.
    """
    tekst = _tekst("net003_tegen_de_richting.ttl")

    assert "Rode draad" in tekst
    assert "omgekeerd" in tekst
    assert "100%" in tekst


def test_drempel_zet_de_richtingsdetectie_uit() -> None:
    """De drempel is configureerbaar; boven 100% kan niets aanslaan."""
    config = _config()
    config.rapport.richtingsdrempel = 1.0

    assert "omgekeerd" not in _tekst("net003_tegen_de_richting.ttl", config)


def test_object_met_meldingen_uit_meerdere_checks_wordt_apart_benoemd() -> None:
    """Vier meldingen op een streng zijn zelden vier gebreken."""
    tekst = _tekst("net003_tegen_de_richting.ttl")

    assert "HGT-006" in tekst
    assert "NET-003" in tekst


def test_gedeeld_deelstelsel_tussen_net_en_rvz_wordt_benoemd() -> None:
    """NET-001 en RVZ-006 melden hier over hetzelfde stuk net."""
    tekst = _tekst("hgt004_bob_boven_deksel.ttl")

    assert "deelstelsel" in tekst
    assert "RVZ-006" in tekst


def _melding(object_label: str, check_id: str) -> Melding:
    """Een kale melding, genoeg voor de synthese."""
    return Melding(
        melding_id=f"{object_label}-{check_id}",
        check_id=check_id,
        categorie=check_id.split("-")[0],
        bron="register",
        ernst="F",
        dimensie="Consistentie",
        object_uri=f"urn:{object_label}",
        object_id=object_label,
        object_label=object_label,
        object2_uri="",
        object2_id="",
        object2_label="",
        boodschap="",
        waarde="",
        drempel="",
        typering_betrouwbaar=True,
        cluster_id="",
        scope="geen_studiegebied",
        gebied="",
        prioriteit=2,
        systemisch=False,
        foutlocatie=None,
        run_datum="2026-08-16",
        dataset="x.ttl",
    )


def test_lijst_met_verdachte_objecten_wordt_afgekapt() -> None:
    """Zeventien objecten uitschrijven maakt de synthese onleesbaar.

    Op De Wolden en Hoogeveen droegen 17 objecten meldingen uit drie of meer checks; die alle
    in een zin noemen verdrinkt de boodschap.
    """
    meldingen = [
        _melding(f"streng-{nummer}", check)
        for nummer in range(8)
        for check in ("NET-001", "HGT-006", "TOP-010")
    ]

    tekst = "\n".join(rode_draad(_run("schoon.ttl"), meldingen))

    assert "8 objecten dragen" in tekst
    assert "en 3 andere" in tekst
    assert "streng-7" not in tekst


def test_meervoud_in_de_slotzin_klopt() -> None:
    meldingen = [
        _melding(f"streng-{nummer}", check)
        for nummer in range(2)
        for check in ("NET-001", "HGT-006", "TOP-010")
    ]

    tekst = "\n".join(rode_draad(_run("schoon.ttl"), meldingen))

    assert "worden nagelopen" in tekst
    assert "meldingen wordt nagelopen" not in tekst


def test_richtingspercentage_zegt_erbij_dat_het_datasetbreed_is() -> None:
    """Een datasetbreed percentage boven een afgebakende lijst leest misleidend.

    Dit is dezelfde fout die de clusterduiding maakte met "174 deelstelsels".
    """
    from nlriochecker.studiegebied import load_study_area

    run = _run("net003_tegen_de_richting.ttl")
    gebied = load_study_area(Path(__file__).parent / "fixtures" / "gis" / "rond_de_fixture.geojson")
    beperkt = run.beperk_tot_studiegebied(gebied)

    tekst = "\n".join(rode_draad(beperkt, bouw_meldingen(beperkt, RUNDATUM)))

    assert "over de volledige dataset geteld" in tekst


def test_zonder_studiegebied_komt_die_kanttekening_niet(tmp_path: Path) -> None:
    assert "over de volledige dataset geteld" not in _tekst("net003_tegen_de_richting.ttl")


class TestRodeDraadEnDeNulmeting:
    """De rode draad redeneert over eigen checks, niet over SHACL-vormen."""

    def test_nulmetingmeldingen_maken_geen_verdacht_object(self) -> None:
        """Drie SHACL-vormen op een put zijn geen drie onafhankelijke checks.

        Op De Wolden en Hoogeveen dragen 23.296 focusnodes drie of meer vormen; zouden die
        meetellen, dan wijst deze sectie vrijwel elke put aan als verdacht.
        """
        from nlriochecker.uitvoer.melding import BRON_NULMETING
        from nlriochecker.uitvoer.synthese import _multi_melding

        meldingen = [
            melding(
                melding_id=f"NULMETING-Vorm_{n}_card",
                check_id=f"NULMETING-Vorm_{n}_card",
                object_uri="http://example.org/toets#PutA",
                bron=BRON_NULMETING,
            )
            for n in range(1, 6)
        ]

        assert _multi_melding(meldingen, load_check_config()) == []

    def test_meldingen_zonder_object_belanden_niet_in_een_naamloze_emmer(self) -> None:
        """Anders staan ze samen als een verdacht object in het rapport."""
        from nlriochecker.uitvoer.synthese import _multi_melding

        meldingen = [
            melding(melding_id=f"TOP-{n:03d}", check_id=f"TOP-{n:03d}", object_uri="")
            for n in range(1, 6)
        ]

        assert _multi_melding(meldingen, load_check_config()) == []

    def test_eigen_checks_op_hetzelfde_object_blijven_wel_opvallen(self) -> None:
        from nlriochecker.uitvoer.synthese import _multi_melding

        meldingen = [
            melding(
                melding_id=f"TOP-{n:03d}",
                check_id=f"TOP-{n:03d}",
                object_uri="http://example.org/toets#PutA",
            )
            for n in range(1, 6)
        ]

        regels = _multi_melding(meldingen, load_check_config())

        assert regels and "verschillende checks" in regels[0]
