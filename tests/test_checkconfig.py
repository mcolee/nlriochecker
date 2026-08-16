"""Tests voor de projectconfiguratie van de check-engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.checkconfig import default_check_config_path, load_check_config
from gwswpijplijn.errors import ConfigError


def test_standaardconfig_laadt() -> None:
    config = load_check_config()

    assert default_check_config_path().exists()
    assert config.klassen.put == ["Put"]
    assert config.drempels.snapping_tolerantie_m == 0.10
    assert config.drempels.dubbele_put_tolerantie_m == 0.30


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
