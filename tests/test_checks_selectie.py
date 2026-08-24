"""Karakterisatietests voor de klassenselecties van `checks/selectie.py`.

Deze module legt vast wat elke rol oplevert, zodat een verbouwing van de selecties
zichtbaar wordt in plaats van stil door te werken in de uitslag van tientallen
checks. De valkuil die deze tests moeten vangen is de verwisseling van twee rollen
die op elkaar lijken: `putten` (alleen `gwsw:Put`) en `netwerkknopen` (de put plus
de eindpunten en de bergbezinkvoorzieningen), en `vrijvervalrioolleidingen` binnen
`leidingen`.

Twee datasets, elk om een eigen reden. `selectie_rollen.ttl` bevat precies een
object per rol en dekt ze dus alle zeventien; die fixture staat in de repository en
is er altijd. Het Juinen-voorbeeld staat in `data/` -- dat ontbreekt in een schone
kloon -- en dient voor de verhoudingen van een echte export: daar is een selectie
groot genoeg dat een verwisseling van twee rollen in de aantallen opvalt.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import selectie
from nlriochecker.checks.base import CheckContext
from nlriochecker.checks.selectie import (
    _ROLLEN,
    leidingen,
    netwerkknopen,
    oppervlaktewaterobjecten,
    putten,
    vrijvervalrioolleidingen,
)
from nlriochecker.dataset import GwswDataset, load_dataset

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


@pytest.fixture(scope="module")
def rollenset() -> GwswDataset:
    """De fixture met precies een object per rol."""
    return load_dataset(TTL_DIR / "selectie_rollen.ttl")


def context_van(dataset: GwswDataset) -> CheckContext:
    """Een context op deze dataset met de meegeleverde projectconfiguratie."""
    return CheckContext(dataset=dataset, config=load_check_config())


# De aantallen per rol op de rollenfixture: 7 knopen en 7 verbindingen. Alle
# zeventien rollen komen erin voor; dat bewaakt `test_elke_rol_komt_erin_voor`.
ROLLENSET_AANTALLEN = {
    "netwerkknopen": 7,
    "putten": 5,
    "lozingspunten": 2,
    "overstortputten": 1,
    "bergbezinkvoorzieningen": 1,
    "valconstructies": 1,
    # Twee: de loze put en het T-stuk. Een T_stuk is een Verbindingsstuk, en dat staat
    # in `functieloze_knoop` in beide TOML's -- een verbindingsstuk knoopt leidingen aan
    # elkaar zonder zelf een functie te hebben. Dat gold al voor De Wolden en Hoogeveen;
    # het wordt hier alleen zichtbaar nu de fixture een hulpstuk draagt (issue #60).
    "functieloze_knopen": 2,
    "hulpstukken": 1,
    # Zes: L1 t/m L4, de persleiding P1 en de loze leiding Loos2 -- die laatste is een
    # gwsw:Leiding en telt dus mee (issue #62).
    "leidingen": 6,
    "lozeleidingen": 1,
    "vrijvervalrioolleidingen": 4,
    "overstortleidingen": 1,
    "bergbezinkleidingen": 1,
    "vuilwaterleidingen": 1,
    "infiltratieleidingen": 1,
    "oppervlaktewaterobjecten": 1,
}

# De aantallen per rol op het Juinen-voorbeeld: 25 knopen en 25 verbindingen. De
# rollen die daar niet voorkomen staan er niet in; die dekt de fixture hierboven.
JUINEN_AANTALLEN = {
    "netwerkknopen": 11,
    "putten": 10,
    "leidingen": 19,
    "vrijvervalrioolleidingen": 11,
    "vuilwaterleidingen": 11,
    "overstortputten": 2,
    "functieloze_knopen": 3,
}


def test_rollenlijst_is_volledig() -> None:
    """`_ROLLEN` noemt elke publieke selectie van de module, en niets anders.

    Zonder deze test is `_ROLLEN` een tweede plek om aan te denken: een vijftiende
    selectie die er niet in belandt, blijft ongetoetst zonder dat iets rood wordt.
    """
    publiek = {
        naam
        for naam, functie in inspect.getmembers(selectie, inspect.isfunction)
        if not naam.startswith("_") and functie.__module__ == selectie.__name__
    }
    assert set(_ROLLEN) == publiek


@pytest.mark.parametrize(("rol", "verwacht"), sorted(ROLLENSET_AANTALLEN.items()))
def test_rollen_op_de_rollenfixture(rollenset: GwswDataset, rol: str, verwacht: int) -> None:
    """Elke rol levert op de rollenfixture hetzelfde aantal als vastgelegd."""
    context = context_van(rollenset)
    assert len(_ROLLEN[rol](context)) == verwacht


@pytest.mark.parametrize(("rol", "verwacht"), sorted(JUINEN_AANTALLEN.items()))
def test_rollen_op_juinen(juinen: GwswDataset, rol: str, verwacht: int) -> None:
    """Elke rol levert op het Juinen-voorbeeld hetzelfde aantal als vastgelegd."""
    context = context_van(juinen)
    assert len(_ROLLEN[rol](context)) == verwacht


def test_elke_rol_komt_erin_voor(rollenset: GwswDataset) -> None:
    """Geen enkele rol wordt uitsluitend op een lege verzameling getoetst.

    Zonder deze test kan een selectie stil kapot zijn: nul objecten leest in een
    assertion op nul precies zo goed als in de werkelijkheid. Komt er een rol bij,
    dan dwingt deze test af dat er ook een object voor in de fixture komt. Hij
    draait bewust op de fixture en niet op Juinen: die laatste staat in `data/` en
    slaat over in een schone kloon, en dan zou deze waarborg stil verdwijnen.
    """
    context = context_van(rollenset)
    assert [rol for rol, kies in _ROLLEN.items() if not kies(context)] == []


def test_putten_zit_echt_binnen_netwerkknopen(rollenset: GwswDataset) -> None:
    """Elke put is een netwerkknoop, maar niet elke netwerkknoop is een put.

    Dit is het verschil dat een verbouwing van de selecties het gemakkelijkst
    wegpoetst: `netwerkknopen` telt ook de uitlaatconstructie en het
    bergbezinkbassin mee, en dat zijn bouwwerken en geen putten.
    """
    context = context_van(rollenset)
    put_uris = {node.uri for node in putten(context)}
    knoop_uris = {node.uri for node in netwerkknopen(context)}
    assert put_uris < knoop_uris
    extra = {node.label for node in netwerkknopen(context)} - {
        node.label for node in putten(context)
    }
    assert extra == {"Uitlaat1", "Bbb1"}


def test_vrijverval_zit_echt_binnen_leidingen(rollenset: GwswDataset) -> None:
    """Een persleiding en een loze leiding zijn wel `gwsw:Leiding`, geen vrijvervalrioolleiding."""
    context = context_van(rollenset)
    vrijverval = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
    alle = {conduit.uri for conduit in leidingen(context)}
    assert vrijverval < alle
    buiten = {conduit.label for conduit in leidingen(context)} - {
        conduit.label for conduit in vrijvervalrioolleidingen(context)
    }
    # Loos2 valt er sinds issue #62 ook buiten: LozeLeiding hangt onder Leiding.
    assert buiten == {"P1", "Loos2"}


def test_subklassen_tellen_mee(rollenset: GwswDataset) -> None:
    """De selectie volgt de klassenhierarchie, niet de letterlijke klassenaam.

    De overstort-, bergbezink- en infiltratieleiding zijn alle drie subklassen van
    `gwsw:VrijvervalRioolleiding` en horen dus in die selectie thuis; de lozingsput
    is een `gwsw:Rioolput` en dus ook een put.
    """
    context = context_van(rollenset)
    assert {conduit.label for conduit in vrijvervalrioolleidingen(context)} == {
        "L1",
        "L2",
        "L3",
        "L4",
    }
    assert "Lozing1" in {node.label for node in putten(context)}


def test_oppervlaktewater_kijkt_in_beide_verzamelingen(rollenset: GwswDataset) -> None:
    """Oppervlaktewater kan als knoop of als verbinding in de export staan."""
    context = context_van(rollenset)
    assert [object_.label for object_ in oppervlaktewaterobjecten(context)] == ["Sloot1"]


def test_selectie_wordt_per_context_een_keer_gebouwd(rollenset: GwswDataset) -> None:
    """Twee aanroepen leveren hetzelfde exemplaar; de tweede telt niets opnieuw."""
    context = context_van(rollenset)
    assert netwerkknopen(context) is netwerkknopen(context)


def test_elke_rol_heeft_een_eigen_cachesleutel(rollenset: GwswDataset) -> None:
    """Elke rol cachet onder `sel:<rolnaam>`, en geen twee rollen delen een sleutel.

    Dat is geen theoretisch risico: de sleutels waren voorheen per module
    voorgevoegd (`adm:putten`, `hgt:putten`), en juist het samenvoegen daarvan maakt
    een botsing mogelijk. Een botsing zou de ene rol de lijst van de andere geven,
    zonder foutmelding. Het cachewoordenboek is privé; deze test is de reden om er
    toch in te kijken, want van buiten is een botsing niet te zien.
    """
    context = context_van(rollenset)
    for kies in _ROLLEN.values():
        kies(context)
    sleutels = {sleutel for sleutel in context._cache if sleutel.startswith("sel:")}
    assert sleutels == {f"sel:{rol}" for rol in _ROLLEN}
