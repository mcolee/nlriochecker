"""Tests voor de projectconfiguratie van de check-engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.checkconfig import default_check_config_path, load_check_config
from nlriochecker.errors import ConfigError


def test_standaardconfig_laadt() -> None:
    config = load_check_config()

    assert default_check_config_path().exists()
    assert config.klassen.put == ["Put"]
    assert config.drempels.snapping_tolerantie_m == 0.10
    assert config.drempels.dubbele_put_tolerantie_m == 0.30


def test_mechanisch_riool_is_geconfigureerd() -> None:
    """Persleiding, drukleiding en vacuumleiding vallen buiten scope voor de checks.

    Ze moeten wel als klassenlijst beschikbaar zijn zodat de GIS-uitvoer ze in een
    eigen laag kan zetten in plaats van tussen de getoetste strengen.
    """
    config = load_check_config()

    assert config.klassen.mechanisch == ["Persleiding", "Drukleiding", "Vacuumleiding"]


def test_netwerkknopen_bundelen_putten_en_eindpunten() -> None:
    knopen = load_check_config().klassen.netwerkknopen

    assert knopen[0] == "Put"
    assert "Gemaal" in knopen


def test_eigen_config_vervangt_de_drempels(tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(
        "[klassen]\nput = ['Put']\nvrijvervalleiding = ['VrijvervalRioolleiding']\n"
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
    ],
)
def test_ongeldige_config(tmp_path: Path, inhoud: str, melding: str) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text(inhoud, encoding="utf-8")

    with pytest.raises(ConfigError, match=melding):
        load_check_config(stuk)


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
    assert rapport.register_versie == "v0.8"


def test_kritieke_klassen_bepalen_de_hoogste_prioriteit() -> None:
    """Een fout op een overstort weegt zwaarder dan een fout op een gewone put."""
    assert "Overstortput" in load_check_config().klassen.kritiek
