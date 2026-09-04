"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

import click
from gwsw_orox_helpers.dataset import GwswDataset, load_dataset
from gwsw_orox_helpers.errors import DatasetError

from nlriochecker import __version__
from nlriochecker.analysis import MetingAnalysis, analyze
from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.comparison import compare_metingen
from nlriochecker.config import CoverageConfig, load_coverage_config
from nlriochecker.coverage import assess_coverage, verify_register
from nlriochecker.errors import PipelineError
from nlriochecker.meting import kies_cfk, laad_nulmeting
from nlriochecker.register import Register, default_register_path, load_register
from nlriochecker.reporting import (
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from nlriochecker.toetsrun import Toetsopdracht, voer_toets_uit


class _CliError(click.ClickException):
    """ClickException met een Nederlandse aanhef."""

    def show(self, file: object | None = None) -> None:
        """Toont de foutmelding op stderr."""
        click.echo(f"Fout: {self.format_message()}", err=True)


class _BalkVoortgang:
    """Voortgang als `click.progressbar`, op stderr.

    De balk gaat naar stderr en niet naar stdout: daar staan de geschreven paden en
    de tellingen, en wie die doorpipet moet er geen balkresten in krijgen.

    Er komt geen eigen TTY-detectie bij; click zet de balk in een niet-interactieve
    omgeving zelf uit. Zonder bepaalbaar totaal is er geen balk te tekenen -- dan
    wordt de fasenaam een keer gemeld, want een balk met een verzonnen lengte zou
    over de resterende tijd liegen.

    Elke schrijfactie is afgeschermd met `suppress(OSError)`. Voortgang is weergave
    en mag een run nooit laten mislukken: valt de lezer van stderr weg
    (`nlriochecker toets ... 2>&1 | head`), dan gooit de balk een
    `BrokenPipeError`, en die zou dwars door `run_checks` heen slaan en de hele run
    afbreken zonder een enkel uitvoerbestand -- op een echte dataset ruim drie
    minuten laadwerk kwijt omdat een balk niet getekend kon worden. Alleen `OSError`
    wordt gedempt; een fout in onze eigen boekhouding hoort gewoon om te vallen.
    """

    def __init__(self) -> None:
        # `click.progressbar` levert een ProgressBar uit een private module; die
        # importeren om hem te kunnen annoteren zou een privaat pad vastleggen.
        # `Optional[Any]` collapst naar `Any`; die `| None` zou nauwkeurigheid
        # suggereren die mypy hier niet levert.
        self._balk: Any = None
        self._stap_label: str | None = None

    def start_fase(self, naam: str, totaal: int | None) -> None:
        """Opent een balk voor deze fase, of meldt hem als er geen totaal is."""
        # Een fase die nog openstaat hoort eerst dicht; anders wordt zijn balk
        # overschreven en nooit afgesloten.
        self.einde_fase()
        self._stap_label = None
        if totaal is None:
            with suppress(OSError):
                click.echo(f"{naam}...", err=True)
            return
        # `click.progressbar` is generiek in het itemtype; zonder items kan mypy
        # dat niet afleiden.
        balk: Any = click.progressbar(
            length=totaal,
            label=naam,
            file=sys.stderr,
            item_show_func=lambda _: self._stap_label,
        )
        with suppress(OSError):
            balk.__enter__()
            self._balk = balk

    def stap(self, n: int = 1, label: str | None = None) -> None:
        """Schuift de balk op en zet erachter wat er net klaar is.

        Het staplabel gaat via `item_show_func` en niet door `balk.label` te
        overschrijven. Click spreekt die functie alleen aan als hij echt een balk
        tekent; in een niet-interactieve omgeving echoot hij enkel het vaste
        faselabel, en dan een keer. Zou het faselabel per stap wisselen, dan zette
        een run met veertig checks veertig regels ruis in een CI-log.

        Dat is ook de reden dat hier niet naar het verborgen-zijn van de balk
        gekeken wordt: dat attribuut heet per clickversie anders (`hidden` dan wel
        `is_hidden`), terwijl `item_show_func` gedocumenteerd is.
        """
        if label is not None:
            self._stap_label = label
        if self._balk is None:
            return
        with suppress(OSError):
            self._balk.update(n)

    def einde_fase(self) -> None:
        """Sluit de balk van deze fase.

        `_balk` gaat eerst op None: gooit `__exit__` alsnog, dan blijft er geen
        halfdode balk staan die de volgende fase overschrijft.
        """
        balk: Any = self._balk
        self._balk = None
        if balk is None:
            return
        with suppress(OSError):
            balk.__exit__(None, None, None)


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


def _checkregister_option():
    """Bouwt de optie voor het checkregister waartegen de mapping geijkt wordt."""
    return click.option(
        "--checkregister",
        "register_path",
        type=RAPPORT_TYPE,
        help=(
            "Checkregister (Markdown) om de dekkingmapping tegen te ijken. Zonder deze "
            "optie wordt het register gebruikt dat de mapping zelf noemt in 'bron', en "
            "anders de kopie in data/."
        ),
    )


def _laad_register(register_path: Path | None, config: CoverageConfig) -> Register | None:
    """Leest het checkregister waartegen de dekkingmapping geijkt wordt.

    Zonder expliciet pad telt het register dat de mapping zelf in `bron` noemt; die
    mapping is er immers tegen geverifieerd. Bestaat dat niet, dan de kopie in
    data/. Is er helemaal geen register, dan wordt de ijking overgeslagen en meldt
    het rapport dat: stil doorgaan zou een dekking suggereren die niemand
    vergeleken heeft.
    """
    if register_path is None:
        kandidaten = [Path(config.bron), default_register_path()]
        register_path = next((pad for pad in kandidaten if pad.is_file()), None)
        if register_path is None:
            return None
    return load_register(register_path)


def _cfk_option():
    """Bouwt de optie voor een deelverzameling conformiteitsklassen."""
    return click.option(
        "--cfk",
        "cfk_keuze",
        multiple=True,
        help=(
            "Conformiteitsklasse om op te toetsen; meermaals toegestaan. Zonder deze optie "
            "gelden alle klassen uit de projectconfiguratie en is een ontbrekend rapport een "
            "fout. Een deelset wordt in alle uitvoervormen gemarkeerd."
        ),
    )


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


def _laad_meting(shacl_paths, project_config_path, dataset_path, ontology_paths, cfk_keuze=()):
    """Leest de nulmeting en optioneel de dataset, en analyseert ze."""
    project = load_check_config(project_config_path)
    gekozen = kies_cfk(cfk_keuze, project.nulmeting.vereiste_cfk)
    nulmeting = laad_nulmeting(list(shacl_paths), gekozen, project.nulmeting.vereiste_cfk)
    dataset = (
        load_dataset(dataset_path, list(ontology_paths), fallback_encoding=FALLBACK_ENCODING)
        if dataset_path is not None
        else None
    )
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
@_cfk_option()
@_projectconfig_option()
@_config_option()
@_checkregister_option()
@_output_option("Map waarin de samenvatting en de geaggregeerde CSV worden geschreven.")
def analyze_command(
    shacl_paths: tuple[Path, ...],
    dataset_path: Path | None,
    ontology_paths: tuple[Path, ...],
    cfk_keuze: tuple[str, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    register_path: Path | None,
    output_dir: Path,
) -> None:
    """Analyseert een SHACL-nulmeting en schrijft samenvatting en aggregaties weg."""
    try:
        _, _, analyse, dataset = _laad_meting(
            shacl_paths, project_config_path, dataset_path, ontology_paths, cfk_keuze
        )
        config = load_coverage_config(config_path)
        register = _laad_register(register_path, config)
        # Anders dan bij `dekking` is de dekkingclaim hier bijzaak: dit commando
        # analyseert de nulmeting. Drift laat de samenvatting daarom niet falen maar
        # verschijnt erin, zodat de lezer een rapport houdt dat zelf zegt wat eraan
        # mankeert.
        coverage = assess_coverage(analyse, config, register)
        markdown_path, csv_path = write_reports(analyse, output_dir, coverage)
    except (PipelineError, DatasetError) as error:
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
@_cfk_option()
@_projectconfig_option()
@_config_option()
@_checkregister_option()
@_output_option("Map waarin het dekkingrapport wordt geschreven.")
def coverage_command(
    shacl_paths: tuple[Path, ...],
    dataset_path: Path | None,
    ontology_paths: tuple[Path, ...],
    cfk_keuze: tuple[str, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    register_path: Path | None,
    output_dir: Path,
) -> None:
    """Toetst of de nulmeting de geschrapte checks in deze dataset daadwerkelijk raakt."""
    try:
        _, _, analyse, _ = _laad_meting(
            shacl_paths, project_config_path, dataset_path, ontology_paths, cfk_keuze
        )
        config = load_coverage_config(config_path)
        register = _laad_register(register_path, config)
        # Loopt de mapping uit de pas met het register, dan zegt de rest van dit
        # rapport niets meer; dan is stoppen eerlijker dan een dekking tonen.
        verify_register(config, register, eisen=True)
        result = assess_coverage(analyse, config, register)
        markdown_path, csv_path = write_coverage_report(result, output_dir)
    except (PipelineError, DatasetError) as error:
        raise _CliError(str(error)) from error

    click.echo(
        f"Dataset {result.dataset}, checkregister {result.config.checkregister_versie}: "
        f"{len(result.checks)} geschrapte checks getoetst"
    )
    if register is None:
        click.echo("  Geen checkregister gevonden; de mapping is er niet tegen geijkt.")
    for check in result.checks:
        gevonden = ", ".join(check.evidence_cfks) or "geen bewijs"
        voorbehoud = "" if check.typing_reliable else "  [typeringsvoorbehoud]"
        click.echo(f"  {check.mapping.id:9s} {check.verdict.value:14s} {gevonden}{voorbehoud}")
    for afwijking in result.discrepanties:
        click.echo(
            f"  Let op: {afwijking.check_id} steunt op {afwijking.patroon}, die wel in "
            f"{', '.join(afwijking.met_meldingen)} meldingen geeft en niet in "
            f"{', '.join(afwijking.zonder_meldingen)}."
        )
    if result.vervallen:
        click.echo(
            f"  Dekking niet aangetoond voor: {', '.join(result.vervallen)}. "
            "Die checks zitten niet in de engine."
        )
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
@_cfk_option()
@_projectconfig_option()
@_config_option()
@_output_option("Map waarin de vergelijking wordt geschreven.")
def compare_command(
    earlier_paths: tuple[Path, ...],
    later_paths: tuple[Path, ...],
    cfk_keuze: tuple[str, ...],
    project_config_path: Path | None,
    config_path: Path | None,
    output_dir: Path,
) -> None:
    """Zet twee nulmetingen van dezelfde dataset naast elkaar voor trendbewaking."""
    try:
        project = load_check_config(project_config_path)
        volledig = project.nulmeting.vereiste_cfk
        gekozen = kies_cfk(cfk_keuze, project.nulmeting.vereiste_cfk)
        eerder = analyze(laad_nulmeting(list(earlier_paths), gekozen, volledig))
        later = analyze(laad_nulmeting(list(later_paths), gekozen, volledig))
        comparison = compare_metingen(eerder, later, load_coverage_config(config_path))
        markdown_path, csv_path, objects_path = write_comparison_reports(comparison, output_dir)
    except (PipelineError, DatasetError) as error:
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
    help=(
        "GWSW-ontologie (TTL); standaard de gebundelde ontologie die bij de GWSW-versie "
        "van de dataset past (1.6 of 1.7, standaard 1.6); meermaals toegestaan."
    ),
)
@click.option(
    "--geen-ontologie",
    "geen_ontologie",
    is_flag=True,
    help=(
        "Draai zonder klassenhierarchie. De checks draaien dan over een onvolledige "
        "selectie en hun uitkomst draagt geen oordeel; het rapport zegt dat."
    ),
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
@_cfk_option()
@click.option(
    "--gebied",
    "gebied_keuze",
    multiple=True,
    help=(
        "Beperk de run tot deze naam_gebied-waarde uit het studiegebiedbestand; "
        "meermaals toegestaan. Zonder deze optie draaien alle gebieden."
    ),
)
@click.option(
    "--uitvoer",
    "uitvoervormen",
    multiple=True,
    type=click.Choice(["csv", "json", "gpkg"]),
    default=("csv", "json", "gpkg"),
    show_default=True,
    help=(
        "Welke bijproducten naast het Markdown-rapport geschreven worden; meermaals "
        "toegestaan. Het rapport wordt altijd geschreven."
    ),
)
@click.option(
    "--geen-cache",
    "geen_cache",
    is_flag=True,
    help="Lees de dataset opnieuw in plaats van uit de cache; ook geen cache wegschrijven.",
)
@click.option(
    "--cache-map",
    "cache_dir",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Waar de geparseerde dataset bewaard wordt; standaard ~/.cache/gwsw-orox-helpers.",
)
@_output_option("Map waarin het bevindingenrapport wordt geschreven.")
def check_command(
    dataset_path: Path,
    ontology_paths: tuple[Path, ...],
    geen_ontologie: bool,
    shacl_paths: tuple[Path, ...],
    check_ids: tuple[str, ...],
    study_path: Path | None,
    study_layer: str | None,
    project_config_path: Path | None,
    plausibility_path: Path | None,
    bronnen_dir: Path | None,
    cfk_keuze: tuple[str, ...],
    gebied_keuze: tuple[str, ...],
    uitvoervormen: tuple[str, ...],
    geen_cache: bool,
    cache_dir: Path | None,
    output_dir: Path,
) -> None:
    """Draait de checks uit het checkregister op een GWSW-OroX-dataset."""
    opdracht = Toetsopdracht(
        dataset_pad=dataset_path,
        ontologieen=ontology_paths,
        geen_ontologie=geen_ontologie,
        shacl=shacl_paths,
        check_ids=check_ids,
        studiegebied=study_path,
        studiegebied_laag=study_layer,
        gebieden=gebied_keuze,
        projectconfig=project_config_path,
        plausibiliteit=plausibility_path,
        bronnen=bronnen_dir,
        cfk=cfk_keuze,
        uitvoermap=output_dir,
        met_csv="csv" in uitvoervormen,
        met_geopackage="gpkg" in uitvoervormen,
        met_json="json" in uitvoervormen,
        gebruik_cache=not geen_cache,
        cachemap=cache_dir,
    )
    try:
        uitslag = voer_toets_uit(opdracht, voortgang=_BalkVoortgang())
    except (PipelineError, DatasetError) as error:
        raise _CliError(str(error)) from error

    for regel in uitslag.regels():
        click.echo(regel)
