"""De orkestratie van de vier uitvoervormen: Markdown, CSV, GeoPackage en JSON.

`schrijf_uitvoer` is de enige ingang die ze alle vier tegelijk wegschrijft. Hij
bouwt de meldingenstroom een keer -- meldingen plus de onderdrukking die `[rapport]`
erop toepaste -- en geeft hem aan elke schrijver door, zodat de vier uitvoervormen
niet uit elkaar kunnen lopen. Wat de onderdrukking wegliet bereikt geen van hen; drie
van de vier dragen de telling ervan (BO-49).

`schrijf_uitvoer_gebieden` doet hetzelfde voor een run over meerdere
studiegebied-features: per gebied een submap met dezelfde vier vormen, plus een
`totaal/` met de synthese en de unieke meldingen. Ook daar komt geen nieuwe
schrijver aan te pas.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from nlriochecker.checkconfig import ReportOptions
from nlriochecker.checks import CheckRun
from nlriochecker.studiegebied import MAP_TOTAAL
from nlriochecker.taal import getal
from nlriochecker.toetsloop import GebiedsRun
from nlriochecker.uitvoer.bevindingen import (
    FILE_CHECKS_CSV,
    FILE_CHECKS_JSON,
    meldingen_json,
    meldingen_tabel,
    write_check_report,
)
from nlriochecker.uitvoer.gpkg import schrijf_geopackage
from nlriochecker.uitvoer.herkomst import schrijf_csv, schrijf_json, schrijf_markdown
from nlriochecker.uitvoer.melding import (
    Melding,
    Meldingenstroom,
    Onderdrukking,
    bouw_meldingenstroom,
)
from nlriochecker.uitvoer.synthese import GebiedsSamenvatting, totaalsynthese
from nlriochecker.uitvoer.tabel import prepare
from nlriochecker.uitvoer.voorbehoud import markering
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang

# De naam van het bestand met de synthese over alle gebieden. De mapnaam ernaast
# (`MAP_TOTAAL`) staat in `studiegebied.py`, want daar wordt hij als gebiedsnaam
# geweigerd: een buurt die "Totaal" heet zou anders in deze map schrijven en de
# synthese overschrijven.
FILE_SYNTHESE = "synthese.md"


@dataclass(frozen=True)
class Uitvoer:
    """De geschreven bestanden van een toets."""

    markdown: Path
    csv: Path
    geopackage: Path | None
    json: Path | None


@dataclass(frozen=True)
class UitvoerPerGebied:
    """De geschreven bestanden van een toets over een of meer studiegebieden."""

    # De uitvoer per gebied, op de originele gebiedsnaam. Zonder studiegebied staat
    # er een enkele sleutel met een lege naam in.
    per_gebied: dict[str, Uitvoer]
    synthese: Path | None = None
    totaal_csv: Path | None = None
    totaal_json: Path | None = None


def schrijf_uitvoer(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    *,
    met_geopackage: bool = True,
    met_json: bool = True,
    voortgang: Voortgang = NUL_VOORTGANG,
    gebied: str | None = None,
    stroom: Meldingenstroom | None = None,
    notities: Sequence[str] = (),
) -> Uitvoer:
    """Schrijft rapport, archief, GIS-uitvoer en JSON uit dezelfde meldingenstroom.

    De JSON komt na het rapport: `write_check_report` maakt de uitvoermap aan. Zet
    hem er niet voor zonder zelf `prepare` te roepen.

    `gebied` komt in de JSON-envelop terecht en is alleen gevuld bij een run over
    meerdere studiegebied-features; `stroom` mag de beller meegeven om dezelfde
    meldingen en dezelfde onderdrukkingstelling ook voor de totaalsynthese te
    gebruiken. `notities` gaan naar het rapport en melden wat het studiegebiedbestand
    niet mocht bijdragen.
    """
    run_datum = run_datum or date.today()
    stroom = stroom if stroom is not None else bouw_meldingenstroom(run, run_datum)
    meldingen = stroom.meldingen

    markdown, csv = write_check_report(
        run, output_dir, run_datum, meldingen, notities, onderdrukking=stroom.onderdrukking
    )
    geopackage = (
        schrijf_geopackage(
            run,
            meldingen,
            output_dir,
            run_datum,
            voortgang=voortgang,
            onderdrukking=stroom.onderdrukking,
        )
        if met_geopackage
        else None
    )
    json_pad = (
        schrijf_json(
            Path(output_dir) / FILE_CHECKS_JSON,
            meldingen_json(meldingen),
            run_datum=run_datum,
            dataset=run.dataset.source.name,
            cfk_set=list(run.meetbereik.gekozen),
            volledig=run.meetbereik.volledig,
            typeringspoort_toegepast=run.typing_gate_applied,
            markering=markering(run),
            gebied=gebied,
            onderdrukking=stroom.onderdrukking,
        )
        if met_json
        else None
    )
    return Uitvoer(markdown=markdown, csv=csv, geopackage=geopackage, json=json_pad)


def schrijf_uitvoer_gebieden(
    runs: Sequence[GebiedsRun],
    output_dir: Path,
    run_datum: date | None = None,
    *,
    met_geopackage: bool = True,
    met_json: bool = True,
    voortgang: Voortgang = NUL_VOORTGANG,
    beschikbaar: Sequence[str] = (),
    overgeslagen: Sequence[str] = (),
) -> UitvoerPerGebied:
    """Schrijft de uitvoer van elke gebiedsrun, met een totaalsynthese bij meerdere.

    Is er maar een run -- geen studiegebied, of een bestand met een enkele feature --
    dan gaat de uitvoer naar de uitvoermap zelf en is er geen synthese: precies de
    uitvoer die deze package altijd al schreef. Vanaf twee gebieden krijgt elk gebied
    een eigen submap en komt er een `totaal/` bij.
    """
    run_datum = run_datum or date.today()
    if len(runs) == 1 and not runs[0].map:
        alleen = runs[0]
        return UitvoerPerGebied(
            per_gebied={
                alleen.naam: schrijf_uitvoer(
                    alleen.run,
                    output_dir,
                    run_datum,
                    met_geopackage=met_geopackage,
                    met_json=met_json,
                    voortgang=voortgang,
                    notities=overgeslagen,
                )
            }
        )

    per_gebied: dict[str, Uitvoer] = {}
    verzameld: list[GebiedsSamenvatting] = []
    for gebiedsrun in runs:
        stroom = bouw_meldingenstroom(gebiedsrun.run, run_datum)
        per_gebied[gebiedsrun.naam] = schrijf_uitvoer(
            gebiedsrun.run,
            Path(output_dir) / gebiedsrun.map,
            run_datum,
            met_geopackage=met_geopackage,
            met_json=met_json,
            voortgang=voortgang,
            gebied=gebiedsrun.naam,
            stroom=stroom,
            notities=overgeslagen,
        )
        analyseset = gebiedsrun.run.analyseset
        verzameld.append(
            GebiedsSamenvatting(
                naam=gebiedsrun.naam,
                oppervlak_ha=gebiedsrun.gebied.area_ha if gebiedsrun.gebied is not None else 0.0,
                weggelaten=gebiedsrun.run.weggelaten,
                kern_objecten=len(analyseset.kern) if analyseset is not None else 0,
                meldingen=stroom.meldingen,
                onderdrukking=stroom.onderdrukking,
            )
        )

    synthese, totaal_csv, totaal_json = _schrijf_totaal(
        runs, verzameld, output_dir, run_datum, beschikbaar, overgeslagen, met_json
    )
    return UitvoerPerGebied(
        per_gebied=per_gebied,
        synthese=synthese,
        totaal_csv=totaal_csv,
        totaal_json=totaal_json,
    )


def _schrijf_totaal(
    runs: Sequence[GebiedsRun],
    verzameld: Sequence[GebiedsSamenvatting],
    output_dir: Path,
    run_datum: date,
    beschikbaar: Sequence[str],
    overgeslagen: Sequence[str],
    met_json: bool,
) -> tuple[Path, Path, Path | None]:
    """Schrijft de synthese en de unieke meldingen over alle gebieden.

    Geen GeoPackage: de featurelagen zijn per gebied afgebakend, en een unie ervan
    zou objecten op een gebiedsgrens dubbel bevatten of ze stilzwijgend ontdubbelen.
    Wie het geheel in GIS wil, opent de bestanden per gebied naast elkaar.
    """
    doel = prepare(Path(output_dir) / MAP_TOTAAL)
    eerste = runs[0].run

    # Ontdubbelen op melding_id, met de gebieden op naam gesorteerd: welk gebied een
    # melding uit meerdere gebieden meekrijgt, hangt dan niet van de volgorde in het
    # gebiedsbestand af.
    uniek: dict[str, Melding] = {}
    for deel in sorted(verzameld, key=lambda deel: deel.naam):
        for melding in deel.meldingen:
            uniek.setdefault(melding.melding_id, melding)
    unieke = list(uniek.values())

    synthese = schrijf_markdown(
        doel / FILE_SYNTHESE,
        # De titel noemt het gebied waar het rapport over gaat, net als het
        # bevindingenrapport per gebied; de dataset staat in de romp.
        f"# Totaal ({getal(len(runs), 'gebied', 'gebieden')})",
        totaalsynthese(verzameld, beschikbaar, overgeslagen, eerste.dataset.source.name),
        run_datum,
        markering=markering(eerste),
    )
    totaal_csv = schrijf_csv(meldingen_tabel(unieke), doel / FILE_CHECKS_CSV)
    totaal_json = (
        schrijf_json(
            doel / FILE_CHECKS_JSON,
            meldingen_json(unieke),
            run_datum=run_datum,
            dataset=eerste.dataset.source.name,
            cfk_set=list(eerste.meetbereik.gekozen),
            volledig=eerste.meetbereik.volledig,
            typeringspoort_toegepast=eerste.typing_gate_applied,
            markering=markering(eerste),
            gebieden=[gebiedsrun.naam for gebiedsrun in runs],
            onderdrukking=_som_onderdrukking(verzameld, eerste.config.rapport),
        )
        if met_json
        else None
    )
    return synthese, totaal_csv, totaal_json


def _som_onderdrukking(
    verzameld: Sequence[GebiedsSamenvatting], rapport: ReportOptions
) -> Onderdrukking:
    """De onderdrukking van alle gebieden samen, als som en niet ontdubbeld.

    Dezelfde regel als de kolom Meldingen in de synthese: een object op een gebiedsgrens
    telt in elk rakend gebied mee. Ontdubbelen zou een derde getal opleveren dat noch bij
    de gebiedsrapporten noch bij de synthese aansluit. De twee lijsten komen uit de
    projectconfiguratie, die voor alle gebieden dezelfde is.
    """
    per_check: dict[str, int] = {}
    per_klasse: dict[str, int] = {}
    for deel in verzameld:
        for sleutel, aantal in deel.onderdrukking.per_check.items():
            per_check[sleutel] = per_check.get(sleutel, 0) + aantal
        for sleutel, aantal in deel.onderdrukking.per_klasse.items():
            per_klasse[sleutel] = per_klasse.get(sleutel, 0) + aantal
    return Onderdrukking(
        tuple(rapport.onderdruk_klassen), tuple(rapport.onderdruk_checks), per_check, per_klasse
    )
