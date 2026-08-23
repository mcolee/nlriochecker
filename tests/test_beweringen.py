"""Drifttest: getallen in de code die een machine gratis kan herleiden.

Issue #51: geen enkele bestaande drifttest bond een getal, terwijl elke onwaarheid die
in de weekendrun van 2026-08-21 werd betrapt een getal was. Een kaal getal in een
docstring wordt eenmaal met de hand gemeten en nooit opnieuw. Deze test bindt de
getallen in `symbolen.py` aan hun berekende waarheid: hij bouwt de zin op uit de
gemeten waarde en eist dat die letterlijk in de docstring staat. Wijzigt de
symbolentabel, dan valt de bijbehorende proza in plaats van stil te verouderen.
"""

from __future__ import annotations

import re

from nlriochecker.uitvoer.stijlen import symbolen


def _legendaregels(laag: str) -> int:
    """Het aantal symbooldragende <rule>-regels in de volledige QML van een laag."""
    qml = symbolen.bouw_qml(laag)
    return len(re.findall(r"<rule[^>]*symbol=", qml))


def _plat(tekst: str | None) -> str:
    """Docstring met genormaliseerde witruimte, zodat regelafbrekingen niet meetellen."""
    return re.sub(r"\s+", " ", tekst or "")


def test_symbolentabel_getallen_kloppen_met_de_docstrings() -> None:
    knooptypen = len(symbolen.PUNTSYMBOLEN)
    verbindingstypen = len(symbolen.LIJNSYMBOLEN)
    statusregels = len(symbolen._statusregels())
    put_bladregels = knooptypen * statusregels
    streng_bladregels = verbindingstypen * statusregels
    put_legenda = _legendaregels("putten")
    streng_legenda = _legendaregels("strengen")

    doc = _plat(symbolen.__doc__)
    assert f"{knooptypen} knooptypen" in doc
    assert f"{verbindingstypen} verbindingstypen" in doc
    assert f"{put_bladregels} respectievelijk {streng_bladregels} bladregels" in doc
    assert f"{put_legenda} legendaregels voor de putten en {streng_legenda} voor de strengen" in doc

    qml_doc = _plat(symbolen.bouw_qml.__doc__)
    assert f"{put_legenda} regels voor de putten en {streng_legenda} voor de" in qml_doc
