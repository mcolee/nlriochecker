"""Bewaakt dat elke verwijzing naar de registerversie dezelfde versie noemt.

De versie staat op vijf plekken: het registerbestand zelf, de dekkingmapping (twee
velden), de checkconfig en het pad in `register.py`. Loopt een van de vijf achter,
dan faalt `verify_register()` of rapporteert de uitvoer een versie waaraan niet
getoetst is.
"""

from __future__ import annotations

from nlriochecker.checkconfig import ReportOptions, load_check_config
from nlriochecker.config import load_coverage_config
from nlriochecker.register import default_register_path, load_register

VERWACHTE_VERSIE = "0.9"


def test_registerbestand_bestaat_en_draagt_de_versie() -> None:
    pad = default_register_path()

    assert pad.exists(), f"{pad} bestaat niet"
    assert pad.name == f"checkregister-gwsw-nulmeting-v0_{VERWACHTE_VERSIE[-1]}.md"
    assert load_register(pad).version == VERWACHTE_VERSIE


def test_dekkingmapping_wijst_naar_dezelfde_versie() -> None:
    config = load_coverage_config()

    assert config.checkregister_versie == VERWACHTE_VERSIE
    assert config.bron.endswith(f"v0_{VERWACHTE_VERSIE[-1]}.md")


def test_checkconfig_rapporteert_dezelfde_versie() -> None:
    assert load_check_config().rapport.register_versie == f"v{VERWACHTE_VERSIE}"


def test_reportoptions_default_wijst_naar_dezelfde_versie() -> None:
    """Een projectconfig die `register_versie` weglaat valt terug op deze default;
    die moet dus ook meelopen, anders rapporteert zo'n config stilzwijgend een
    verouderde versie (ook in de GIS-uitvoer).
    """
    assert ReportOptions().register_versie == f"v{VERWACHTE_VERSIE}"
