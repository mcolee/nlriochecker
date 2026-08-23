"""Tests voor de herkomstvermelding in de plausibiliteitstabellen.

Elke regel in `plausibiliteit.toml` is een vakinhoudelijke aanname, en het issue
(#20) eist dat elke regel zegt waar zijn waarde vandaan komt: een van de vier harde
projectankers (`ontologie`, `checkregister`, `RIONED Kennisbank`, `Leidraad C2100`)
of, eerlijk gemarkeerd, een `ervaringsregel`. De sweep onderaan is de eigenlijke
waarborg: hij verbiedt dat een nieuwe tabel of een nieuwe regel zonder herkomst
stilzwijgend meelift, net als `tests/test_uitvoer_herkomst.py` een tweede
uitvoerschrijver verbiedt.
"""

from __future__ import annotations

from pydantic import BaseModel

from nlriochecker.plausibiliteit import PlausibilityTables, load_plausibility

TOEGESTANE_BRONNEN = {
    "ontologie",
    "checkregister",
    "RIONED Kennisbank",
    "Leidraad C2100",
    "ervaringsregel",
}


def _tabellen(tables: PlausibilityTables) -> list[list[BaseModel]]:
    """Alle regellijsten van BaseModel-regels; `standaarddiameters_mm` valt af (floats)."""
    lijsten = []
    for naam in type(tables).model_fields:
        waarde = getattr(tables, naam)
        if isinstance(waarde, list) and waarde and isinstance(waarde[0], BaseModel):
            lijsten.append(waarde)
    return lijsten


def test_elke_tabelregel_is_een_model_met_bron() -> None:
    """Elke regelklasse in de tabellen draagt een `bron`-veld; geen tabel ontsnapt."""
    tables = load_plausibility()
    lijsten = _tabellen(tables)
    # Er zijn meer dan een handvol tabellen; een lege sweep zou niets bewaken.
    assert len(lijsten) >= 6
    for regels in lijsten:
        for regel in regels:
            assert "bron" in type(regel).model_fields, type(regel).__name__


def test_elke_regel_noemt_een_geldige_bron() -> None:
    """Elke regel in de meegeleverde tabellen draagt een van de toegestane bronnen."""
    tables = load_plausibility()
    for regels in _tabellen(tables):
        for regel in regels:
            assert regel.bron in TOEGESTANE_BRONNEN, (type(regel).__name__, regel.bron)
