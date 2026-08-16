"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

from pathlib import Path

import click

from gwswpijplijn import __version__
from gwswpijplijn.analysis import MetingAnalysis, analyze
from gwswpijplijn.checkconfig import load_check_config
from gwswpijplijn.checks import REGISTRY, CheckContext, Severity, run_checks
from gwswpijplijn.comparison import compare_metingen
from gwswpijplijn.config import load_coverage_config
from gwswpijplijn.coverage import assess_coverage
from gwswpijplijn.dataset import GwswDataset, load_dataset
from gwswpijplijn.errors import PipelineError
from gwswpijplijn.externedata import load_external_data
from gwswpijplijn.meting import laad_nulmeting
from gwswpijplijn.plausibiliteit import load_plausibility
from gwswpijplijn.reporting import (
    write_check_report,
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from gwswpijplijn.studiegebied import load_study_area


class _CliError(click.ClickException):
    """ClickException met een Nederlandse aanhef."""

    def show(self, file: object | None = None) -> None:
        """Toont de foutmelding op stderr."""
        click.echo(f"Fout: {self.format_message()}", err=True)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Toetst de datakwaliteit van vrijvervalriolering (GWSW-nulmeting)."""


RAPPORT_TYPE = click.Path(exists=True, dir_okay=False, path_type=Path)


def _report_option(naam: str, doel: str, hulp: str):
    """Bouwt een verplichte optie die naar een detailrapport wijst."""
    return click.option(naam, doel, required=True, type=RAPPORT_TYPE, help=hulp)


def _config_option():
    """Bouwt de optionele optie voor een eigen dekkingmapping."""
    return click.option(
        "--config",
        "config_path",
        default=None,
        type=RAPPORT_TYPE,
        help="Eigen dekkingmapping (TOML); standaard de meegeleverde dekking.toml.",
    )


def _output_option(hulp: str):
    """Bouwt de optie voor de uitvoermap."""
    return click.option(
        "--output",
        "output_dir",
        default=Path("uitvoer"),
        show_default=True,
        type=click.Path(file_okay=False, path_type=Path),
        help=hulp,
    )


def _shacl_option():
    """Bouwt de optie voor de SHACL-rapporten; meermaals toegestaan."""
    return click.option(
        "--shacl",
        "shacl_paths",
        multiple=True,
        required=True,
        type=RAPPORT_TYPE,
        help="SHACL-nulmetingrapport (CSV); geef er een per conformiteitsklasse.",
    )


def _dataset_options():
    """Bouwt de opties voor de OroX-dataset en de ontologie."""

    def versier(functie):
        """Hangt de dataset- en ontologieopties aan een commando."""
        functie = click.option(
            "--ontologie",
            "ontology_paths",
            multiple=True,
            type=RAPPORT_TYPE,
            help="GWSW-ontologie (TTL); meermaals toegestaan.",
        )(functie)
        return click.option(
            "--dataset",
            "dataset_path",
            default=None,
            type=RAPPORT_TYPE,
            help="GWSW-OroX-dataset (TTL); nodig om de typeringspoort te kunnen wegen.",
        )(functie)

    return versier


def _studiegebied_options():
    """Bouwt de opties voor de afbakening tot een studiegebied."""

    def versier(functie):
        """Hangt de studiegebiedopties aan een commando."""
        functie = click.option(
            "--studiegebied-laag",
            "study_layer",
            default=None,
            help="Laagnaam binnen het studiegebiedbestand, als dat er meerdere heeft.",
        )(functie)
        return click.option(
            "--studiegebied",
            "study_path",
            default=None,
            type=RAPPORT_TYPE,
            help="GeoPackage of GeoJSON met het gebied waartoe de rapportage beperkt wordt.",
        )(functie)

    return versier


def _projectconfig_option():
    """Bouwt de optie voor de projectconfiguratie."""
    return click.option(
        "--projectconfig",
        "project_config_path",
        default=None,
        type=RAPPORT_TYPE,
        help="Projectconfiguratie (TOML); standaard de meegeleverde checks.toml.",
    )


def _plausibiliteit_option():
    """Bouwt de optie voor de plausibiliteitstabellen van de ATTR-checks."""
    return click.option(
        "--plausibiliteit",
        "plausibility_path",
        default=None,
        type=RAPPORT_TYPE,
        help=(
            "Plausibiliteitstabellen (TOML) voor de ATTR-checks; standaard de "
            "meegeleverde plausibiliteit.toml."
        ),
    )


def _bronnen_option():
    """Bouwt de optie voor de map met externe geodata."""
    return click.option(
        "--bronnen",
        "bronnen_dir",
        default=None,
        type=click.Path(exists=True, file_okay=False, path_type=Path),
        help=(
            "Map met de externe geodata (BGT, BAG, NWB, studiegebied, AHN). Zonder deze "
            "optie draaien de EXT-checks en HGT-001 t/m HGT-003 niet en melden ze dat."
        ),
    )


def _laad_meting(shacl_paths, project_config_path, dataset_path, ontology_paths):
    """Leest de nulmeting en optioneel de dataset, en analyseert ze."""
    project = load_check_config(project_config_path)
    nulmeting = laad_nulmeting(list(shacl_paths), project.nulmeting.vereiste_cfk)
    dataset = load_dataset(dataset_path, list(ontology_paths)) if dataset_path is not None else None
    return project, nulmeting, analyze(nulmeting, dataset), dataset


def _echo_meting(analyse: MetingAnalysis, dataset: GwswDataset | None) -> None:
    """Toont de kern van een nulmeting op de opdrachtregel."""
    click.echo(f"Dataset {analyse.meting.dataset_file}: {', '.join(analyse.meting.cfks)}")
    for cfk in analyse.meting.cfks:
        deel = analyse.per_cfk[cfk]
        poort = deel.typing_gate
        score = f", typeringsscore {poort.score:.1f}%" if poort.score is not None else ""
        click.echo(
            f"  {cfk:8s} {deel.total_count:7d} meldingen "
            f"({deel.error_count} F / {deel.warning_count} W){score}"
        )
    if dataset is None:
        click.echo("  Geen --dataset opgegeven; typeringsscore niet te bepalen.")


@main.command("analyseer")
@_shacl_option()
@_dataset_options()
@_projectconfig_option()
@_config_option()
@_output_option("Map waarin de samenvatting en de geaggregeerde CSV worden geschreven.")
def analyze_command(
    shacl_paths: tuple[Path, ...],
    dataset_path: Path | None,
    ontology_paths: tuple[Path, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Analyseert een SHACL-nulmeting en schrijft samenvatting en aggregaties weg."""
    try:
        _, _, analyse, dataset = _laad_meting(
            shacl_paths, project_config_path, dataset_path, ontology_paths
        )
        coverage = assess_coverage(analyse, load_coverage_config(config_path))
        markdown_path, csv_path = write_reports(analyse, output_dir, coverage)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    _echo_meting(analyse, dataset)
    niet_geraakt = [check.mapping.id for check in coverage.untouched]
    if niet_geraakt:
        click.echo(f"  Niet geraakte geschrapte checks: {', '.join(niet_geraakt)}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


@main.command("dekking")
@_shacl_option()
@_dataset_options()
@_projectconfig_option()
@_config_option()
@_output_option("Map waarin het dekkingrapport wordt geschreven.")
def coverage_command(
    shacl_paths: tuple[Path, ...],
    dataset_path: Path | None,
    ontology_paths: tuple[Path, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Toetst of de nulmeting de geschrapte checks in deze dataset daadwerkelijk raakt."""
    try:
        _, _, analyse, _ = _laad_meting(
            shacl_paths, project_config_path, dataset_path, ontology_paths
        )
        result = assess_coverage(analyse, load_coverage_config(config_path))
        markdown_path, csv_path = write_coverage_report(result, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(
        f"Dataset {result.dataset}, checkregister {result.config.checkregister_versie}: "
        f"{len(result.checks)} geschrapte checks getoetst"
    )
    for check in result.checks:
        gevonden = ", ".join(check.evidence_cfks) or "geen bewijs"
        voorbehoud = "" if check.typing_reliable else "  [typeringsvoorbehoud]"
        click.echo(f"  {check.mapping.id:9s} {check.verdict.value:14s} {gevonden}{voorbehoud}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


@main.command("vergelijk")
@click.option(
    "--eerder",
    "earlier_paths",
    multiple=True,
    required=True,
    type=RAPPORT_TYPE,
    help="SHACL-rapport van het eerste meetmoment; meermaals toegestaan.",
)
@click.option(
    "--later",
    "later_paths",
    multiple=True,
    required=True,
    type=RAPPORT_TYPE,
    help="SHACL-rapport van het tweede meetmoment; meermaals toegestaan.",
)
@_projectconfig_option()
@_config_option()
@_output_option("Map waarin de vergelijking wordt geschreven.")
def compare_command(
    earlier_paths: tuple[Path, ...],
    later_paths: tuple[Path, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Zet twee nulmetingen van dezelfde dataset naast elkaar voor trendbewaking."""
    try:
        project = load_check_config(project_config_path)
        eerder = analyze(laad_nulmeting(list(earlier_paths), project.nulmeting.vereiste_cfk))
        later = analyze(laad_nulmeting(list(later_paths), project.nulmeting.vereiste_cfk))
        comparison = compare_metingen(eerder, later, load_coverage_config(config_path))
        markdown_path, csv_path, objects_path = write_comparison_reports(comparison, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(f"Dataset {comparison.dataset_file}")
    if comparison.timestamps_out_of_order:
        click.echo("  Let op: de latere meting is niet nieuwer dan de eerste.")
    for item in comparison.per_cfk:
        telling = item.status_counts()
        click.echo(
            f"  {item.cfk:8s} meldingen {item.total_delta:+d}, fouten {item.error_delta:+d}, "
            f"{telling['opgelost']} opgelost / {telling['nieuw']} nieuw / "
            f"{telling['gebleven']} gebleven"
        )
    gewijzigd = comparison.coverage_changes[comparison.coverage_changes["Gewijzigd"]]
    for _, rij in gewijzigd.iterrows():
        click.echo(f"  Dekking {rij['Check']}: {rij['Eerder']} -> {rij['Later']}")
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")
    click.echo(f"Geschreven: {objects_path}")


@main.command("toets")
@click.option(
    "--dataset",
    "dataset_path",
    required=True,
    type=RAPPORT_TYPE,
    help="GWSW-OroX-dataset (TTL).",
)
@click.option(
    "--ontologie",
    "ontology_paths",
    multiple=True,
    type=RAPPORT_TYPE,
    help="GWSW-ontologie (TTL) voor de klassenhierarchie; meermaals toegestaan.",
)
@click.option(
    "--shacl",
    "shacl_paths",
    multiple=True,
    type=RAPPORT_TYPE,
    help="SHACL-nulmetingrapport, voor de typeringspoort; geef ze alle op.",
)
@click.option(
    "--check",
    "check_ids",
    multiple=True,
    help="Check-ID uit het register; meermaals toegestaan. Zonder deze optie draaien ze alle.",
)
@_studiegebied_options()
@_projectconfig_option()
@_plausibiliteit_option()
@_bronnen_option()
@_output_option("Map waarin het bevindingenrapport wordt geschreven.")
def check_command(
    dataset_path: Path,
    ontology_paths: tuple[Path, ...],
    shacl_paths: tuple[Path, ...],
    check_ids: tuple[str, ...],
    study_path: Path | None,
    study_layer: str | None,
    project_config_path: Path | None,
    plausibility_path: Path | None,
    bronnen_dir: Path | None,
    output_dir: Path,
) -> None:
    """Draait de checks uit het checkregister op een GWSW-OroX-dataset."""
    try:
        config = load_check_config(project_config_path)
        dataset = load_dataset(dataset_path, list(ontology_paths))
        onbetrouwbaar, gate_applied = _typing_gate(shacl_paths, config, dataset)
        bronnen = _externe_bronnen(config, bronnen_dir)
        context = CheckContext(
            dataset=dataset,
            config=config,
            unreliable_objects=onbetrouwbaar,
            plausibiliteit=load_plausibility(plausibility_path),
            bronnen=bronnen,
        )
        run = run_checks(context, list(check_ids) or None, typing_gate_applied=gate_applied)
        if study_path is not None:
            run = run.beperk_tot_studiegebied(load_study_area(study_path, study_layer))
        markdown_path, csv_path = write_check_report(run, output_dir)
    except PipelineError as error:
        raise _CliError(str(error)) from error
    except KeyError as error:
        bekend = ", ".join(sorted(REGISTRY))
        raise _CliError(f"{error.args[0]}. Bekende checks: {bekend}.") from error

    click.echo(
        f"{dataset_path.name}: {len(dataset.nodes)} knooppunten, {len(dataset.conduits)} strengen"
    )
    if dataset.decode_fallback is not None:
        fallback = dataset.decode_fallback
        click.echo(
            f"  Let op: geen geldige UTF-8; gelezen als {fallback.encoding} "
            f"({fallback.byte_count} bytes buiten ASCII). Zie het rapport."
        )
    if dataset.geometry_errors:
        click.echo(f"  {len(dataset.geometry_errors)} objecten met onleesbare geometrie.")
    if run.study_area is not None:
        gebied = run.study_area
        weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
        click.echo(
            f"  Studiegebied {gebied.name} ({gebied.area_ha:.1f} ha): "
            f"{weggelaten} bevindingen buiten het gebied weggelaten."
        )
    if not gate_applied:
        click.echo("  Geen typeringspoort toegepast (--shacl niet opgegeven).")
    if bronnen is None:
        click.echo("  Geen externe bronnen geladen (--bronnen niet opgegeven).")
    else:
        click.echo(
            f"  Externe bronnen: {len(bronnen.layers)} lagen"
            f"{', hoogteraster' if bronnen.raster is not None else ''}"
            f", bereik {bronnen.extent_name or 'onbekend'}."
        )
        for ontbreekt in bronnen.missing:
            click.echo(f"    Niet aanwezig: {ontbreekt}")
    for outcome in run.outcomes:
        voorbehoud = (
            f", {outcome.unreliable_count} met typeringsvoorbehoud"
            if outcome.unreliable_count
            else ""
        )
        click.echo(
            f"  {outcome.check_id:9s} {outcome.severity.value}  "
            f"{len(outcome.findings):5d} bevindingen{voorbehoud}"
        )
    click.echo(
        f"Totaal {run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen"
    )
    click.echo(f"Geschreven: {markdown_path}")
    click.echo(f"Geschreven: {csv_path}")


def _externe_bronnen(config, bronnen_dir: Path | None):
    """Leest de externe geodata als er een bronmap opgegeven is.

    De aangeleverde bronnen dekken maar een deel van het beheergebied; ze worden
    daarom alleen geladen als de gebruiker er expliciet om vraagt, en de EXT-checks
    melden zelf wanneer ze niets konden toetsen.
    """
    if bronnen_dir is None:
        return None
    bronnen = config.bronnen.model_copy(update={"map": "."})
    return load_external_data(bronnen, bronnen_dir)


def _typing_gate(
    shacl_paths: tuple[Path, ...], config, dataset: GwswDataset
) -> tuple[frozenset[str], bool]:
    """Haalt de te globaal getypeerde objecten uit de nulmeting.

    De SHACL-meting noemt de te globale klassen; de instanties komen uit de dataset.
    Dat geeft een exacte verzameling in plaats van een labellijst.
    """
    if not shacl_paths:
        return frozenset(), False

    nulmeting = laad_nulmeting(list(shacl_paths), config.nulmeting.vereiste_cfk)
    analyse = analyze(nulmeting, dataset)
    objecten: set[str] = set()
    for deel in analyse.per_cfk.values():
        objecten.update(deel.typing_gate.objects)
    return frozenset(objecten), True
