"""De toetsrun als aanroepbare eenheid, los van de opdrachtregel.

Een toets is meer dan "draai de checks": de keuzes en de externe bronnen moeten
gevalideerd zijn *voordat* de dataset geladen wordt, de typeringspoort levert drie
samenhangende uitkomsten op, en de uitvoer moet in een vaste volgorde geschreven
worden. Die kennis stond in de body van een click-commando en was daarmee alleen
via `CliRunner` te bereiken. Ze staat nu hier.

`Toetsopdracht` is wat de gebruiker opgeeft: paden en vlaggen. Dat is met opzet zo,
en niet een verzameling al geladen objecten -- anders zou de beller alsnog zelf de
volgorde moeten kennen waarin er geladen wordt, en dat is juist wat deze module
overneemt.

`Toetsuitslag.regels()` levert het verhaal zoals de opdrachtregelgebruiker het hoort
te zien, inclusief vlagnamen als `--shacl`. Wie deze module programmatisch gebruikt,
leest de velden uit; daarvoor staan ze er.

Deze module is de bedoelde ingang voor een tweede beller naast de CLI. Zolang het
pakket onder 1.0 staat kan de vorm nog schuiven; zie `docs/versionering.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nlriochecker.analysis import analyze
from nlriochecker.cache import CacheUitslag, laad_met_cache
from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import REGISTRY, Severity
from nlriochecker.dataset import GwswDataset, markeer_vulwaarden
from nlriochecker.errors import OpdrachtError
from nlriochecker.externedata import Dekkingseis, ExternalData, load_external_data
from nlriochecker.meting import Meetbereik, kies_cfk, laad_nulmeting
from nlriochecker.nulbevinding import Nulbevinding, bouw_nulbevindingen
from nlriochecker.plausibiliteit import load_plausibility
from nlriochecker.studiegebied import RdGrenzen, Studiegebieden, load_studiegebieden
from nlriochecker.taal import getal, vorm
from nlriochecker.toetsloop import GebiedsRun, toets_gebieden
from nlriochecker.uitvoer import UitvoerPerGebied, schrijf_uitvoer_gebieden
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang


@dataclass(frozen=True)
class Toetsopdracht:
    """Wat er getoetst moet worden: de paden en de keuzes van de gebruiker.

    De vlaggen staan bevestigend (`met_geopackage`, niet `geen_gpkg`), zodat ze
    aansluiten op `schrijf_uitvoer_gebieden` en niet als dubbele ontkenning lezen
    zodra je ze programmatisch zet.
    """

    dataset_pad: Path
    uitvoermap: Path
    ontologieen: tuple[Path, ...] = ()
    shacl: tuple[Path, ...] = ()
    check_ids: tuple[str, ...] = ()
    studiegebied: Path | None = None
    studiegebied_laag: str | None = None
    gebieden: tuple[str, ...] = ()
    projectconfig: Path | None = None
    plausibiliteit: Path | None = None
    bronnen: Path | None = None
    cfk: tuple[str, ...] = ()
    met_geopackage: bool = True
    met_json: bool = True
    gebruik_cache: bool = True
    cachemap: Path | None = None


@dataclass(frozen=True)
class Toetsuitslag:
    """Wat een toetsrun opleverde, en wat erover te melden valt."""

    config: CheckConfig
    dataset: GwswDataset
    cache: CacheUitslag
    runs: list[GebiedsRun]
    uitvoer: UitvoerPerGebied
    meetbereik: Meetbereik
    typeringspoort_toegepast: bool
    bronnen: ExternalData | None
    studiegebieden: Studiegebieden | None
    # De CFK-keuze van de opdracht; alleen nodig om te melden dat `--cfk` niets doet
    # zonder `--shacl`. Het meetbereik zelf zegt daar niets over, want zonder meting
    # is er geen bereik om een deelset van te zijn.
    cfk_keuze: tuple[str, ...] = ()

    def regels(self) -> list[str]:
        """Het verhaal van deze run, in de volgorde waarin het gelezen hoort te worden.

        De tekst is gericht op de gebruiker van het commando en noemt daarom
        vlagnamen. De volgorde is onderdeel van de uitvoer: een beller hoort deze
        lijst af te drukken en hem niet zelf samen te stellen.
        """
        # `source` is het pad waarmee de dataset gelezen is. Bij een cachetreffer
        # komt dat uit het bewaarde exemplaar, en dat klopt omdat de cachesleutel de
        # bestandsnaam meeneemt; zou die eruit gaan, dan zou hier de naam van een
        # andere export kunnen staan.
        regels = [
            f"{self.dataset.source.name}: {len(self.dataset.nodes)} knooppunten, "
            f"{len(self.dataset.conduits)} strengen"
        ]
        regels += self._laadregels()
        regels += self._meetregels()
        regels += self._bronregels()
        if len(self.runs) == 1:
            regels += _gebied_uitgebreid(self.runs[0], self.config)
        else:
            # Bij tachtig buurten zou een blok per gebied duizenden regels opleveren;
            # de tellingen per check staan in totaal/synthese.md.
            regels += [_gebied_kort(gebiedsrun) for gebiedsrun in self.runs]
        regels += self._geschreven()
        return regels

    def _laadregels(self) -> list[str]:
        """Waar de dataset vandaan kwam en wat er bij het lezen opviel."""
        herkomst = "uit de cache" if self.cache.bron == "cache" else "ingelezen"
        regels = [f"  Dataset {herkomst} in {self.cache.seconden:.1f} s."]
        if self.cache.melding:
            regels.append(f"  {self.cache.melding}")
        if self.dataset.decode_fallback is not None:
            fallback = self.dataset.decode_fallback
            regels.append(
                f"  Let op: geen geldige UTF-8; gelezen als {fallback.encoding} "
                f"({fallback.byte_count} bytes buiten ASCII). Zie het rapport."
            )
        if self.dataset.geometry_errors:
            regels.append(
                f"  {len(self.dataset.geometry_errors)} objecten met onleesbare geometrie."
            )
        return regels

    def _meetregels(self) -> list[str]:
        """Wat de nulmeting bijdroeg, of dat er niet gemeten is."""
        if not self.typeringspoort_toegepast:
            regels = ["  Geen typeringspoort toegepast (--shacl niet opgegeven)."]
            if self.cfk_keuze:
                regels.append("  Let op: --cfk doet niets zonder --shacl; er is niets gemeten.")
            return regels
        if not self.meetbereik.volledig:
            return [f"  {self.meetbereik.markering()}"]
        return []

    def _bronregels(self) -> list[str]:
        """Welke externe bronnen meededen, en welke ontbraken."""
        if self.bronnen is None:
            return ["  Geen externe bronnen geladen (--bronnen niet opgegeven)."]
        raster = ", hoogteraster" if self.bronnen.raster is not None else ""
        regels = [
            f"  Externe bronnen: {len(self.bronnen.layers)} lagen{raster}"
            f", bereik {self.bronnen.extent_name or 'onbekend'}."
        ]
        regels += [f"    Niet aanwezig: {ontbreekt}" for ontbreekt in self.bronnen.missing]
        return regels

    def _geschreven(self) -> list[str]:
        """De geschreven bestanden.

        De paden dragen de gesaneerde gebiedsnaam al als submap; die er nog eens bij
        zetten zou de lijst alleen langer maken.
        """
        regels = []
        for geschreven in self.uitvoer.per_gebied.values():
            for pad in (
                geschreven.markdown,
                geschreven.csv,
                geschreven.geopackage,
                geschreven.json,
            ):
                if pad is not None:
                    regels.append(f"Geschreven: {pad}")
        for pad in (self.uitvoer.synthese, self.uitvoer.totaal_csv, self.uitvoer.totaal_json):
            if pad is not None:
                regels.append(f"Geschreven: {pad}")
        return regels


def voer_toets_uit(
    opdracht: Toetsopdracht, *, voortgang: Voortgang = NUL_VOORTGANG
) -> Toetsuitslag:
    """Draait de checks uit het checkregister op een GWSW-OroX-dataset.

    De volgorde is niet vrij. De keuzes, de studiegebieden en de externe bronnen
    worden getoetst voordat de dataset geladen wordt: op De Wolden kost dat laden
    ruim drie minuten en circa 3 GB, en een typefout in `cfk` of `gebieden` hoort
    niet pas daarna te melden dat de run zinloos was. De dekkingspoort op de bronnen
    hangt alleen van die bronnen af en hoort om dezelfde reden vooraan.
    """
    config = load_check_config(opdracht.projectconfig)
    kies_cfk(opdracht.cfk, config.nulmeting.vereiste_cfk)
    gebieden = _studiegebieden(opdracht, config)
    bronnen = _externe_bronnen(opdracht, config)

    dataset, cache = laad_met_cache(
        opdracht.dataset_pad,
        list(opdracht.ontologieen),
        opdracht.cachemap,
        opdracht.gebruik_cache,
        voortgang=voortgang,
    )
    dataset = markeer_vulwaarden(
        dataset, config.vulwaarden.hoogte_kenmerken, config.vulwaarden.hoogte_band_m
    )
    onbetrouwbaar, poort_toegepast, meetbereik, nulbevindingen = _nulmeting(
        opdracht, config, dataset, voortgang
    )

    try:
        runs = toets_gebieden(
            dataset,
            gebieden,
            config,
            onbetrouwbaar=onbetrouwbaar,
            plausibiliteit=load_plausibility(opdracht.plausibiliteit),
            bronnen=bronnen,
            check_ids=list(opdracht.check_ids) or None,
            typing_gate_applied=poort_toegepast,
            meetbereik=meetbereik,
            nulbevindingen=nulbevindingen,
            voortgang=voortgang,
        )
    except KeyError as error:
        # Alleen de opzoeking in REGISTRY levert een KeyError op. Het blok hieronder
        # vangen zou ook een indexeerfout uit de schrijvers als "onbekende check"
        # laten lezen.
        bekend = ", ".join(sorted(REGISTRY))
        raise OpdrachtError(f"{error.args[0]}. Bekende checks: {bekend}.") from error

    uitvoer = schrijf_uitvoer_gebieden(
        runs,
        opdracht.uitvoermap,
        met_geopackage=opdracht.met_geopackage,
        met_json=opdracht.met_json,
        voortgang=voortgang,
        beschikbaar=gebieden.beschikbaar if gebieden is not None else (),
        overgeslagen=gebieden.overgeslagen if gebieden is not None else (),
    )
    return Toetsuitslag(
        config=config,
        dataset=dataset,
        cache=cache,
        runs=runs,
        uitvoer=uitvoer,
        meetbereik=meetbereik,
        typeringspoort_toegepast=poort_toegepast,
        bronnen=bronnen,
        studiegebieden=gebieden,
        cfk_keuze=opdracht.cfk,
    )


def _studiegebieden(opdracht: Toetsopdracht, config: CheckConfig) -> Studiegebieden | None:
    """Leest en selecteert de studiegebieden, of levert None zonder studiegebied.

    Het volledige bestand wordt altijd eerst gevalideerd en pas daarna geselecteerd:
    een run met een gebiedskeuze mag een defect in een ander gebied niet maskeren.
    """
    if opdracht.studiegebied is None:
        if opdracht.gebieden:
            raise OpdrachtError("--gebied werkt alleen samen met --studiegebied.")
        return None
    drempels = config.drempels
    gebieden = load_studiegebieden(
        opdracht.studiegebied,
        opdracht.studiegebied_laag,
        grenzen=RdGrenzen(
            drempels.rd_x_min, drempels.rd_x_max, drempels.rd_y_min, drempels.rd_y_max
        ),
    )
    return gebieden.selecteer(list(opdracht.gebieden)) if opdracht.gebieden else gebieden


def _externe_bronnen(opdracht: Toetsopdracht, config: CheckConfig) -> ExternalData | None:
    """Leest de externe geodata als er een bronmap opgegeven is.

    De aangeleverde bronnen dekken maar een deel van het beheergebied; ze worden
    daarom alleen geladen als de gebruiker er expliciet om vraagt, en de EXT-checks
    melden zelf wanneer ze niets konden toetsen. Wat wel hard faalt is een bron die
    kleiner is dan het bereik waarvoor hij geldig verklaard is; zie `_toets_dekking`.
    """
    if opdracht.bronnen is None:
        return None
    bronnen = config.bronnen.model_copy(update={"map": "."})
    # De poortcheck draait hier, voordat er ook maar een check gedraaid heeft: een
    # bron die het bereik niet dekt geeft anders een misleidend schone uitkomst.
    eis = Dekkingseis(
        marge_m=config.drempels.ext_zoekafstand_max_m,
        tolerantie_m=config.bronnen.dekking_tolerantie_m,
    )
    return load_external_data(bronnen, opdracht.bronnen, dekkingseis=eis)


def _nulmeting(
    opdracht: Toetsopdracht,
    config: CheckConfig,
    dataset: GwswDataset,
    voortgang: Voortgang,
) -> tuple[frozenset[str], bool, Meetbereik, tuple[Nulbevinding, ...]]:
    """Leest de nulmeting en haalt er twee dingen uit: de poort en de overtredingen.

    De typeringspoort levert de te globaal getypeerde objecten. De SHACL-meting
    noemt de te globale klassen; de instanties komen uit de dataset. Dat geeft een
    exacte verzameling in plaats van een labellijst.

    De overtredingen zelf worden bevindingen (`nulbevinding.py`), zodat elke
    uitvoervorm kan tonen welk gebrek uit de nulmeting komt en uit welke
    conformiteitsklasse. Beide komen uit hetzelfde ingelezen rapport: twee keer lezen
    zou op De Wolden ruim tweehonderdduizend regels dubbel parsen, en de twee zouden
    bij een wijziging uit elkaar kunnen lopen.

    Zonder SHACL-rapporten is er geen meting. Het meetbereik zegt dat dan expliciet,
    in plaats van de vereiste set te noemen alsof die gehaald is -- stilte over een
    niet-uitgevoerde meting leest als "alles gecontroleerd".
    """
    volledig = config.nulmeting.vereiste_cfk
    gekozen = kies_cfk(opdracht.cfk, volledig)
    if not opdracht.shacl:
        return frozenset(), False, Meetbereik.niet_gemeten(volledig), ()

    nulmeting = laad_nulmeting(list(opdracht.shacl), gekozen, volledig, voortgang=voortgang)
    analyse = analyze(nulmeting, dataset)
    objecten: set[str] = set()
    for deel in analyse.per_cfk.values():
        objecten.update(deel.typing_gate.objects)
    onbetrouwbaar = frozenset(objecten)
    bevindingen = bouw_nulbevindingen(
        nulmeting, dataset, config.rapport.systemisch_drempel, onbetrouwbaar
    )
    return onbetrouwbaar, True, nulmeting.meetbereik, tuple(bevindingen)


def _gebied_kort(gebiedsrun: GebiedsRun) -> str:
    """Vat een gebiedsrun samen in een regel; het detail staat in de synthese."""
    run = gebiedsrun.run
    kern = len(run.analyseset.kern) if run.analyseset is not None else 0
    weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
    leeg = " -- geen objecten in dit gebied, niets getoetst" if not kern else ""
    return (
        f"  Gebied {gebiedsrun.naam}: {getal(kern, 'object', 'objecten')} in de kern, "
        f"{run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen, "
        f"{weggelaten} buiten het gebied weggelaten{leeg}."
    )


def _gebied_uitgebreid(gebiedsrun: GebiedsRun, config: CheckConfig) -> list[str]:
    """De omvang en de uitslag van een enkele gebiedsrun, per check."""
    run = gebiedsrun.run
    regels = []
    if run.study_area is not None:
        gebied = run.study_area
        weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
        regels.append(
            f"  Studiegebied {gebied.name} ({gebied.area_ha:.1f} ha): "
            f"{getal(weggelaten, 'bevinding', 'bevindingen')} buiten het gebied weggelaten."
        )
    if run.analyseset is not None:
        stel = run.analyseset
        regels.append(
            f"  Analyseset: {getal(len(stel.kern), 'object', 'objecten')} in de kern, "
            f"{len(stel.schil)} in de contextschil, van {stel.volledig_aantal} in de export."
        )
        if stel.aandeel > config.studiegebied.component_waarschuwingsdrempel:
            regels.append(
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
        regels.append(
            f"  {outcome.check_id:9s} {outcome.severity.value}  "
            f"{aantal:5d} {vorm(aantal, 'bevinding', 'bevindingen')}{voorbehoud}"
        )
    regels.append(
        f"Totaal {run.count(Severity.ERROR)} fouten, {run.count(Severity.WARNING)} waarschuwingen"
    )
    return regels
