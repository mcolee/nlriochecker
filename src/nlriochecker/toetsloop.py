"""De toetsloop: dezelfde checks over nul, een of veel studiegebieden.

Het laden van de dataset kost op de De Wolden-export ruim drie minuten en circa
3 GB; N keer laden is uitgesloten. Deze module laadt daarom niets zelf, maar krijgt
de geladen dataset mee en bouwt er per gebied een eigen analyseset op. De
schilsemantiek blijft daarmee per gebied gelijk aan die van een losse run: dat is de
correctheidseis van de rapportage per gebied, en `tests/test_toetsloop.py` legt hem
vast.

Wat over gebieden heen gedeeld wordt, is uitsluitend wat niet van het gebied
afhangt:

- de geparseerde dataset en ontologie -- invoer;
- de ruimtelijke index en de vrijvervalcomponenten van het volledige net
  (`GedeeldeIndex`) -- de boom levert kandidaten, het oordeel blijft `area.bevat`,
  en de componentstructuur hing al niet van een gebied af;
- de volledige-export-`CheckContext` -- die hangt af van de volledige dataset, de
  config en de onbetrouwbare objecten, alle drie gebiedsonafhankelijk. Hierin zitten
  de datakarakteristiek en de structuren van de checks met `volledig_bereik`.

Nooit gedeeld: de context van een gebied en alles in zijn cache. De topologie-index
en de netwerkgraaf horen bij de uitgedunde dataset van dat ene gebied.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nlriochecker.afbakening import GedeeldeIndex, bouw_analyseset, bouw_gedeelde_index
from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import GwswDataset
from nlriochecker.externedata import ExternalData
from nlriochecker.meting import Meetbereik
from nlriochecker.plausibiliteit import PlausibilityTables, load_plausibility
from nlriochecker.studiegebied import Studiegebieden, StudyArea, mapnaam
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang


@dataclass(frozen=True)
class GebiedsRun:
    """Het resultaat van de checks op een enkel studiegebied."""

    gebied: StudyArea | None
    run: CheckRun
    # De gesaneerde naam van de submap, of leeg als de uitvoer in de uitvoermap
    # zelf hoort: zonder studiegebied, en bij een bestand met een enkele feature.
    map: str

    @property
    def naam(self) -> str:
        """De originele gebiedsnaam, zoals hij in het bestand staat."""
        return self.gebied.gebied if self.gebied is not None else ""


def toets_gebieden(
    dataset: GwswDataset,
    gebieden: Studiegebieden | None,
    config: CheckConfig,
    *,
    onbetrouwbaar: frozenset[str] = frozenset(),
    plausibiliteit: PlausibilityTables | None = None,
    bronnen: ExternalData | None = None,
    check_ids: list[str] | None = None,
    typing_gate_applied: bool = False,
    meetbereik: Meetbereik,
    voortgang: Voortgang = NUL_VOORTGANG,
) -> list[GebiedsRun]:
    """Draait de checks per studiegebied en levert een run per gebied.

    Zonder studiegebieden is er precies een run, over de volledige dataset. Met een
    enkel gebied ook, maar dan afgebakend -- exact zoals voor de rapportage per
    gebied bestond. Met meer gebieden is het er een per gebied, elk met een eigen
    kern, contextschil en uitgedunde dataset.
    """
    basis = CheckContext(
        dataset=dataset,
        config=config,
        unreliable_objects=onbetrouwbaar,
        plausibiliteit=plausibiliteit if plausibiliteit is not None else load_plausibility(),
        bronnen=bronnen,
        volledige_dataset=dataset,
    )
    if gebieden is None:
        return [
            GebiedsRun(
                gebied=None,
                run=_draai(basis, check_ids, typing_gate_applied, meetbereik, voortgang, "Checks"),
                map="",
            )
        ]

    gedeeld = bouw_gedeelde_index(dataset, config)
    volledig = basis.volledige_context()
    return [
        _per_gebied(
            basis,
            volledig,
            gedeeld,
            area,
            config,
            check_ids=check_ids,
            typing_gate_applied=typing_gate_applied,
            meetbereik=meetbereik,
            voortgang=voortgang,
            met_submap=not gebieden.enkel,
        )
        for area in gebieden.gebieden
    ]


def _per_gebied(
    basis: CheckContext,
    volledig: CheckContext,
    gedeeld: GedeeldeIndex,
    area: StudyArea,
    config: CheckConfig,
    *,
    check_ids: list[str] | None,
    typing_gate_applied: bool,
    meetbereik: Meetbereik,
    voortgang: Voortgang,
    met_submap: bool,
) -> GebiedsRun:
    """Bouwt de analyseset van een gebied en draait er de checks op."""
    analyseset = bouw_analyseset(basis.dataset, area, config, gedeeld=gedeeld)
    context = replace(
        basis,
        dataset=analyseset.dataset,
        analyseset=analyseset,
        gedeelde_volledige_context=volledig,
        _cache={},
    )
    naam = area.gebied or area.name
    fase = f"Checks {naam}" if met_submap else "Checks"
    run = _draai(context, check_ids, typing_gate_applied, meetbereik, voortgang, fase)
    return GebiedsRun(
        gebied=area,
        run=run.beperk_tot_studiegebied(area),
        map=mapnaam(naam) if met_submap else "",
    )


def _draai(
    context: CheckContext,
    check_ids: list[str] | None,
    typing_gate_applied: bool,
    meetbereik: Meetbereik,
    voortgang: Voortgang,
    fase: str,
) -> CheckRun:
    """Draait de checks en hangt er het meetbereik van de run aan."""
    run = run_checks(
        context,
        check_ids,
        typing_gate_applied=typing_gate_applied,
        voortgang=voortgang,
        fase=fase,
    )
    return replace(run, meetbereik=meetbereik)
