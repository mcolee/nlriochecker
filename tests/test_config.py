"""Tests voor het inlezen en valideren van de dekkingmapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.config import default_config_path, load_coverage_config
from gwswpijplijn.errors import ConfigError

REGISTER_IDS = {"ADM-001", "ADM-004", "ADM-005", "ATTR-011", "RVZ-002", "RVZ-003"}

GELDIGE_TOML = """
checkregister_versie = "0.9"
bron = "eigen-register.md"

[drempels]
typeringsscore_minimum = 50.0

[[check]]
id = "EIGEN-001"
onderwerp = "Zelfbedachte check"
claim = "Eigen claim"
vereiste_cfk = ["Hyd"]
bewijs = [{ melding = "Collectie-item onbekend" }]
"""


def test_standaardmapping_bevat_de_geschrapte_checks() -> None:
    config = load_coverage_config()

    assert default_config_path().exists()
    assert config.checkregister_versie == "0.7"
    assert {mapping.id for mapping in config.check} == REGISTER_IDS


def test_rvz_003_leunt_uitsluitend_op_hyd() -> None:
    mapping = load_coverage_config().mapping("RVZ-003")

    assert mapping.vereiste_cfk == ["Hyd"]
    assert mapping.bewijs[0].aspect == ["Drempelbreedte"]


def test_adm_005_heeft_tegenbewijs() -> None:
    mapping = load_coverage_config().mapping("ADM-005")

    assert mapping.tegenbewijs[0].melding_prefix == "Collectie ontbreekt in deze CFK"


def test_eigen_config_vervangt_de_standaard(tmp_path: Path) -> None:
    eigen = tmp_path / "eigen.toml"
    eigen.write_text(GELDIGE_TOML, encoding="utf-8")

    config = load_coverage_config(eigen)

    assert [mapping.id for mapping in config.check] == ["EIGEN-001"]
    assert config.drempels.typeringsscore_minimum == 50.0


def test_ontbrekend_bestand_geeft_configerror(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="kan niet gelezen worden"):
        load_coverage_config(tmp_path / "bestaat_niet.toml")


def test_ongeldige_toml_geeft_configerror(tmp_path: Path) -> None:
    stuk = tmp_path / "stuk.toml"
    stuk.write_text("dit is [geen geldige toml", encoding="utf-8")

    with pytest.raises(ConfigError, match="geldige TOML"):
        load_coverage_config(stuk)


@pytest.mark.parametrize(
    ("vervanging", "melding"),
    [
        ('bewijs = [{ melding = "A", melding_prefix = "B" }]', "precies een"),
        ('bewijs = [{ aspect = ["A"] }]', "precies een"),
        ("vereiste_cfk = []", "at least 1"),
        ("bewijs = []", "at least 1"),
    ],
)
def test_ongeldige_mapping_geeft_configerror(tmp_path: Path, vervanging: str, melding: str) -> None:
    regels = [
        regel
        for regel in GELDIGE_TOML.splitlines()
        if not regel.startswith(("bewijs =", "vereiste_cfk ="))
    ]
    stuk = tmp_path / "stuk.toml"
    stuk.write_text("\n".join([*regels, vervanging]), encoding="utf-8")

    with pytest.raises(ConfigError, match=melding):
        load_coverage_config(stuk)


def test_dubbele_check_ids_geven_configerror(tmp_path: Path) -> None:
    stuk = tmp_path / "dubbel.toml"
    stuk.write_text(
        GELDIGE_TOML + "[[check]]" + GELDIGE_TOML.split("[[check]]")[1], encoding="utf-8"
    )

    with pytest.raises(ConfigError, match="dubbele check-ID"):
        load_coverage_config(stuk)
