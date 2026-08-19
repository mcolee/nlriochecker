"""Opdrachtregel-ingang van de pijplijn."""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

import click

from nlriochecker import __version__
from nlriochecker.analysis import MetingAnalysis, analyze
from nlriochecker.cache import laad_met_cache
from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import REGISTRY, Severity
from nlriochecker.comparison import compare_metingen
from nlriochecker.config import CoverageConfig, load_coverage_config
from nlriochecker.coverage import assess_coverage, verify_register
from nlriochecker.dataset import GwswDataset, load_dataset
from nlriochecker.errors import PipelineError
from nlriochecker.externedata import Dekkingseis, load_external_data
from nlriochecker.meting import Meetbereik, laad_nulmeting
from nlriochecker.plausibiliteit import load_plausibility
from nlriochecker.register import Register, default_register_path, load_register
from nlriochecker.reporting import (
    write_comparison_reports,
    write_coverage_report,
    write_reports,
)
from nlriochecker.studiegebied import RdGrenzen, Studiegebieden, load_studiegebieden
from nlriochecker.taal import getal, vorm
from nlriochecker.toetsloop import GebiedsRun, toets_gebieden
from nlriochecker.uitvoer import schrijf_uitvoer_gebieden
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang


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


def _gekozen_cfk(cfk_keuze: tuple[str, ...], config: CheckConfig) -> list[str]:
    """Toetst de opgegeven conformiteitsklassen tegen de projectconfiguratie.

    Geen `click.Choice`: de toegestane waarden staan pas vast nadat
    `--projectconfig` gelezen is, en `click.Choice` moet ze al kennen op het moment
    dat het commando opgebouwd wordt.
    """
    volledig = config.nulmeting.vereiste_cfk
    if not cfk_keuze:
        return list(volledig)
    onbekend = sorted({keuze for keuze in cfk_keuze if keuze not in volledig})
    if onbekend:
        raise _CliError(
            f"Onbekende conformiteitsklasse(n): {', '.join(onbekend)}. "
            f"Toegestaan: {', '.join(volledig)}."
        )
    return sorted(set(cfk_keuze))


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
    gekozen = _gekozen_cfk(cfk_keuze, project)
    nulmeting = laad_nulmeting(list(shacl_paths), gekozen, project.nulmeting.vereiste_cfk)
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
    except PipelineError as error:
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
        gekozen = _gekozen_cfk(cfk_keuze, project)
        eerder = analyze(laad_nulmeting(list(earlier_paths), gekozen, volledig))
        later = analyze(laad_nulmeting(list(later_paths), gekozen, volledig))
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
    "--geen-gpkg",
    "geen_gpkg",
    is_flag=True,
    help="Sla de GeoPackage-export over; schrijf alleen het rapport en de CSV.",
)
@click.option(
    "--geen-json",
    "geen_json",
    is_flag=True,
    help="Sla de JSON-export over; schrijf alleen het rapport, de CSV en de GeoPackage.",
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
    help="Waar de geparseerde dataset bewaard wordt; standaard ~/.cache/nlriochecker.",
)
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
    cfk_keuze: tuple[str, ...],
    gebied_keuze: tuple[str, ...],
    geen_gpkg: bool,
    geen_json: bool,
    geen_cache: bool,
    cache_dir: Path | None,
    output_dir: Path,
) -> None:
    """Draait de checks uit het checkregister op een GWSW-OroX-dataset."""
    try:
        voortgang: Voortgang = _BalkVoortgang()
        config = load_check_config(project_config_path)
        # Toets de keuzes voordat de dataset geladen wordt. Op De Wolden kost dat
        # laden ruim drie minuten; een typefout in --cfk of --gebied hoort niet pas
        # daarna te melden dat de run zinloos was.
        _gekozen_cfk(cfk_keuze, config)
        gebieden = _studiegebieden(study_path, study_layer, gebied_keuze, config)
        dataset, cache = laad_met_cache(
            dataset_path, list(ontology_paths), cache_dir, not geen_cache, voortgang=voortgang
        )
        onbetrouwbaar, gate_applied, meetbereik = _typing_gate(
            shacl_paths, config, dataset, cfk_keuze, voortgang
        )
        bronnen = _externe_bronnen(config, bronnen_dir)
        try:
            runs = toets_gebieden(
                dataset,
                gebieden,
                config,
                onbetrouwbaar=onbetrouwbaar,
                plausibiliteit=load_plausibility(plausibility_path),
                bronnen=bronnen,
                check_ids=list(check_ids) or None,
                typing_gate_applied=gate_applied,
                meetbereik=meetbereik,
                voortgang=voortgang,
            )
        except KeyError as error:
            # Alleen de opzoeking in REGISTRY levert een KeyError op. Het blok
            # hieronder vangen zou ook een indexeerfout uit de schrijvers als
            # "onbekende check" laten lezen.
            bekend = ", ".join(sorted(REGISTRY))
            raise _CliError(f"{error.args[0]}. Bekende checks: {bekend}.") from error
        uitvoer = schrijf_uitvoer_gebieden(
            runs,
            output_dir,
            met_geopackage=not geen_gpkg,
            met_json=not geen_json,
            voortgang=voortgang,
            beschikbaar=gebieden.beschikbaar if gebieden is not None else (),
            overgeslagen=gebieden.overgeslagen if gebieden is not None else (),
        )
    except PipelineError as error:
        raise _CliError(str(error)) from error

    click.echo(
        f"{dataset_path.name}: {len(dataset.nodes)} knooppunten, {len(dataset.conduits)} strengen"
    )
    herkomst = "uit de cache" if cache.bron == "cache" else "ingelezen"
    click.echo(f"  Dataset {herkomst} in {cache.seconden:.1f} s.")
    if cache.melding:
        click.echo(f"  {cache.melding}")
    if dataset.decode_fallback is not None:
        fallback = dataset.decode_fallback
        click.echo(
            f"  Let op: geen geldige UTF-8; gelezen als {fallback.encoding} "
            f"({fallback.byte_count} bytes buiten ASCII). Zie het rapport."
        )
    if dataset.geometry_errors:
        click.echo(f"  {len(dataset.geometry_errors)} objecten met onleesbare geometrie.")
    if not gate_applied:
        click.echo("  Geen typeringspoort toegepast (--shacl niet opgegeven).")
        if cfk_keuze:
            click.echo("  Let op: --cfk doet niets zonder --shacl; er is niets gemeten.")
    elif not meetbereik.volledig:
        click.echo(f"  {meetbereik.markering()}")
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
    if len(runs) == 1:
        _meld_gebied(runs[0], config)
    else:
        # Bij tachtig buurten zou een blok per gebied duizenden regels opleveren; de
        # tellingen per check staan in totaal/synthese.md.
        for gebiedsrun in runs:
            _meld_gebied_kort(gebiedsrun)

    # De paden dragen de gesaneerde gebiedsnaam al als submap; die er nog eens bij
    # zetten zou de lijst alleen langer maken.
    for geschreven in uitvoer.per_gebied.values():
        for pad in (geschreven.markdown, geschreven.csv, geschreven.geopackage, geschreven.json):
            if pad is not None:
                click.echo(f"Geschreven: {pad}")
    for pad in (uitvoer.synthese, uitvoer.totaal_csv, uitvoer.totaal_json):
        if pad is not None:
            click.echo(f"Geschreven: {pad}")


def _meld_gebied_kort(gebiedsrun: GebiedsRun) -> None:
    """Vat een gebiedsrun samen in een regel; het detail staat in de synthese."""
    run = gebiedsrun.run
    kern = len(run.analyseset.kern) if run.analyseset is not None else 0
    weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
    leeg = " -- geen objecten in dit gebied, niets getoetst" if not kern else ""
    click.echo(
        f"  Gebied {gebiedsrun.naam}: {getal(kern, 'object', 'objecten')} in de kern, "
        f"{run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen, "
        f"{weggelaten} buiten het gebied weggelaten{leeg}."
    )


def _meld_gebied(gebiedsrun: GebiedsRun, config: CheckConfig) -> None:
    """Meldt de omvang en de uitslag van een enkele gebiedsrun op het scherm."""
    run = gebiedsrun.run
    if run.study_area is not None:
        gebied = run.study_area
        weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
        click.echo(
            f"  Studiegebied {gebied.name} ({gebied.area_ha:.1f} ha): "
            f"{getal(weggelaten, 'bevinding', 'bevindingen')} buiten het gebied weggelaten."
        )
    if run.analyseset is not None:
        stel = run.analyseset
        click.echo(
            f"  Analyseset: {getal(len(stel.kern), 'object', 'objecten')} in de kern, "
            f"{len(stel.schil)} in de contextschil, van {stel.volledig_aantal} in de export."
        )
        if stel.aandeel > config.studiegebied.component_waarschuwingsdrempel:
            click.echo(
                "  Let op: het net binnen dit gebied hangt met vrijwel de hele export samen; "
                "de afbakening levert weinig tijdwinst op."
            )
    for outcome in run.outcomes:
        voorbehoud = (
            f", {outcome.unreliable_count} met typeringsvoorbehoud"
            if outcome.unreliable_count
            else ""
        )
        aantal = len(outcome.findings)
        click.echo(
            f"  {outcome.check_id:9s} {outcome.severity.value}  "
            f"{aantal:5d} {vorm(aantal, 'bevinding', 'bevindingen')}{voorbehoud}"
        )
    click.echo(
        f"Totaal {run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen"
    )


def _studiegebieden(
    study_path: Path | None,
    study_layer: str | None,
    gebied_keuze: tuple[str, ...],
    config: CheckConfig,
) -> Studiegebieden | None:
    """Leest en selecteert de studiegebieden, of levert None zonder studiegebied.

    Het volledige bestand wordt altijd eerst gevalideerd en pas daarna geselecteerd:
    een run met `--gebied` mag een defect in een ander gebied niet maskeren.
    """
    if study_path is None:
        if gebied_keuze:
            raise _CliError("--gebied werkt alleen samen met --studiegebied.")
        return None
    drempels = config.drempels
    gebieden = load_studiegebieden(
        study_path,
        study_layer,
        grenzen=RdGrenzen(
            drempels.rd_x_min, drempels.rd_x_max, drempels.rd_y_min, drempels.rd_y_max
        ),
    )
    return gebieden.selecteer(list(gebied_keuze)) if gebied_keuze else gebieden


def _externe_bronnen(config, bronnen_dir: Path | None):
    """Leest de externe geodata als er een bronmap opgegeven is.

    De aangeleverde bronnen dekken maar een deel van het beheergebied; ze worden
    daarom alleen geladen als de gebruiker er expliciet om vraagt, en de EXT-checks
    melden zelf wanneer ze niets konden toetsen. Wat wel hard faalt is een bron die
    kleiner is dan het bereik waarvoor hij geldig verklaard is; zie `_toets_dekking`.
    """
    if bronnen_dir is None:
        return None
    bronnen = config.bronnen.model_copy(update={"map": "."})
    # De poortcheck draait hier, voordat er ook maar een check gedraaid heeft: een
    # bron die het bereik niet dekt geeft anders een misleidend schone uitkomst.
    eis = Dekkingseis(
        marge_m=config.drempels.ext_zoekafstand_max_m,
        tolerantie_m=config.bronnen.dekking_tolerantie_m,
    )
    return load_external_data(bronnen, bronnen_dir, dekkingseis=eis)


def _typing_gate(
    shacl_paths: tuple[Path, ...],
    config: CheckConfig,
    dataset: GwswDataset,
    cfk_keuze: tuple[str, ...] = (),
    voortgang: Voortgang = NUL_VOORTGANG,
) -> tuple[frozenset[str], bool, Meetbereik]:
    """Haalt de te globaal getypeerde objecten uit de nulmeting.

    De SHACL-meting noemt de te globale klassen; de instanties komen uit de dataset.
    Dat geeft een exacte verzameling in plaats van een labellijst.

    Zonder `--shacl` is er geen meting. Het meetbereik zegt dat dan expliciet, in
    plaats van de vereiste set te noemen alsof die gehaald is -- stilte over een
    niet-uitgevoerde meting leest als "alles gecontroleerd".
    """
    volledig = config.nulmeting.vereiste_cfk
    # Eerst toetsen, dan pas beslissen of er iets te meten valt: een typefout in
    # --cfk moet ook opvallen bij een run zonder --shacl, waar de vlag geen effect
    # heeft. Anders accepteert juist de aanroepvorm die er niets mee doet hem stil.
    gekozen = _gekozen_cfk(cfk_keuze, config)
    if not shacl_paths:
        return frozenset(), False, Meetbereik.niet_gemeten(volledig)

    nulmeting = laad_nulmeting(list(shacl_paths), gekozen, volledig, voortgang=voortgang)
    analyse = analyze(nulmeting, dataset)
    objecten: set[str] = set()
    for deel in analyse.per_cfk.values():
        objecten.update(deel.typing_gate.objects)
    return frozenset(objecten), True, nulmeting.meetbereik
