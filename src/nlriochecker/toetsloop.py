"""De toetsloop: dezelfde checks over nul, een of veel studiegebieden.

Het laden van de dataset kost op de De Wolden en Hoogeveen-export ruim drie minuten en circa
3 GB; N keer laden is uitgesloten. Deze module laadt daarom niets zelf, maar krijgt
de geladen dataset mee.

Sinds BO-100 draaien de checks ook maar één keer: over de volledige export, precies
zoals zonder studiegebied. Daarna bakent de loop die ene run per gebied af tot de kern.
Een gebiedsrapport is daarmee per constructie gelijk aan de gemeentebrede run beperkt
tot dat gebied -- de correctheidseis van de rapportage per gebied, die
`tests/test_toetsloop.py` vastlegt. Tot BO-100 draaide elk gebied de checks op een
eigen analyseset (kern plus contextschil); bij 88 buurten kostte dat 51 minuten checks,
omdat de schil van elke buurt bijna het hele net besloeg.

Per gebied wordt alleen nog de kern en de ring bepaald (`afbakening.Afbakening`), via
één gedeelde ruimtelijke index (`GedeeldeIndex`): de boom levert kandidaten, het
oordeel blijft `area.bevat`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from gwsw_orox_helpers.dataset import GwswDataset
from gwsw_orox_helpers.voortgang import NUL_VOORTGANG, Voortgang

from nlriochecker.afbakening import GedeeldeIndex, bouw_afbakening, bouw_gedeelde_index
from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.externedata import ExternalData
from nlriochecker.meting import Meetbereik
from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.plausibiliteit import PlausibilityTables, load_plausibility
from nlriochecker.studiegebied import Studiegebieden, StudyArea, mapnaam


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
    max_meldingen: str = "",
    lokale_eisen: str = "",
    nulbevindingen: tuple[Nulbevinding, ...] = (),
    niet_beoordeelde_klassen: tuple[str, ...] = (),
    voortgang: Voortgang = NUL_VOORTGANG,
) -> list[GebiedsRun]:
    """Draait de checks één keer over de volledige export en levert een run per gebied.

    Zonder studiegebieden is er precies een run, over de volledige dataset. Met een
    enkel gebied ook, maar dan afgebakend tot de kern van dat gebied. Met meer gebieden
    is het er een per gebied: telkens dezelfde run, elk tot de eigen kern afgebakend
    (BO-100). Een enkel gebied gaat bewust dezelfde route, zodat de gelijkwaardigheid
    met de gemeentebrede run voor beide per constructie geldt.
    """
    context = CheckContext(
        dataset=dataset,
        config=config,
        unreliable_objects=onbetrouwbaar,
        plausibiliteit=plausibiliteit if plausibiliteit is not None else load_plausibility(),
        bronnen=bronnen,
        volledige_dataset=dataset,
    )
    run = run_checks(
        context,
        check_ids,
        typing_gate_applied=typing_gate_applied,
        voortgang=voortgang,
    )
    # De nulbevindingen zijn over de volledige export gebouwd, net als de
    # systemisch-vlag erop. Ze komen hier op de run en worden pas daarna door
    # `beperk_tot_studiegebied` tot de kern afgebakend -- dezelfde volgorde als bij de
    # checkbevindingen.
    run = replace(
        run,
        meetbereik=meetbereik,
        max_meldingen=max_meldingen,
        lokale_eisen=lokale_eisen,
        nulbevindingen=nulbevindingen,
        niet_beoordeelde_klassen=niet_beoordeelde_klassen,
    )
    if gebieden is None:
        return [GebiedsRun(gebied=None, run=run, map="")]

    gedeeld = bouw_gedeelde_index(dataset, config)
    met_submap = not gebieden.enkel
    return [_per_gebied(run, gedeeld, area, config, met_submap) for area in gebieden.gebieden]


def _per_gebied(
    run: CheckRun, gedeeld: GedeeldeIndex, area: StudyArea, config: CheckConfig, met_submap: bool
) -> GebiedsRun:
    """Bakent de run over de volledige export af tot de kern van een gebied."""
    afbakening = bouw_afbakening(run.dataset, area, config, gedeeld)
    beperkt = run.beperk_tot_studiegebied(area, afbakening.kern, leeg_toegestaan=met_submap)
    return GebiedsRun(
        gebied=area,
        run=replace(beperkt, afbakening=afbakening),
        map=mapnaam(area.gebied or area.name) if met_submap else "",
    )
