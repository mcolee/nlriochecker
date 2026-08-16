"""Tests voor de synthesesectie: de rode draad door de bevindingen."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from gwswpijplijn.checkconfig import CheckConfig, load_check_config
from gwswpijplijn.checks import CheckContext, CheckRun, run_checks
from gwswpijplijn.dataset import load_dataset
from gwswpijplijn.uitvoer.melding import bouw_meldingen
from gwswpijplijn.uitvoer.synthese import rode_draad

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
