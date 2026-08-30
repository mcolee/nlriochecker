"""Raamwerk voor de checks: ernst, dimensie, bevindingen en de registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, TypeVar, cast

from gwsw_orox_helpers.dataset import GwswDataset
from gwsw_orox_helpers.voortgang import NUL_VOORTGANG, Voortgang
from shapely.geometry import Point

from nlriochecker.afbakening import Analyseset, objecten_in_gebied
from nlriochecker.checkconfig import CheckConfig
from nlriochecker.checks.treffers import Trefferregister, Wegvakregister
from nlriochecker.errors import StudyAreaError
from nlriochecker.externedata import ExternalData
from nlriochecker.karakteristiek import DataCharacteristics, bepaal_karakteristiek
from nlriochecker.meting import Meetbereik
from nlriochecker.plausibiliteit import PlausibilityTables, load_plausibility
from nlriochecker.studiegebied import StudyArea

if TYPE_CHECKING:  # pragma: no cover
    # Alleen als type. `nulbevinding` leest `uitvoer.identiteit`, en die module
    # trekt via haar package `checks` weer binnen; een gewone import zou de kring
    # rond maken.
    from nlriochecker.nulbevinding import Nulbevinding


class Severity(StrEnum):
    """Ernstniveau conform het checkregister."""

    ERROR = "F"
    WARNING = "W"


class Dimension(StrEnum):
    """Dimensietag conform het kwaliteitsraamwerk uit het checkregister."""

    CONSISTENCY = "Consistentie"
    COMPLETENESS = "Compleetheid"
    PLAUSIBILITY = "Plausibiliteit"
    TIMELINESS = "Actualiteit"
    TRACEABILITY = "Traceerbaarheid"
    PRECISION = "Precisie"
    ACCURACY = "Nauwkeurigheid"
    COMPLIANCE = "Compliance"


class Scope(StrEnum):
    """Waarover `CheckOutcome.examined` geteld is (issue #77).

    Het kale getal "bekeken" mengt drie noemers die niets met elkaar te maken hebben:
    een rol op de analyseset (kern plus contextschil), diezelfde rol op de volledige
    export, en de instanties van een kenmerk. Wie de drie zonder label naast elkaar
    zet, vergelijkt 95 met 45.803 en met 459.108, en `percentage_populatie` deelt door
    een noemer waarvan niemand weet wat hij telt. Zie BO-58.

    `ANALYSESET` is de scope die `run_checks` een gewone check meegeeft. Zonder
    studiegebied valt die samen met de volledige export; het onderscheid met
    `VOLLEDIGE_EXPORT` zegt dus niet dat er minder gezien is, maar dat deze check
    meebeweegt met de afbakening en de andere niet.
    """

    ANALYSESET = "analyseset"
    VOLLEDIGE_EXPORT = "volledige_export"
    ATTRIBUUT_INSTANTIES = "attribuut_instanties"


@dataclass(frozen=True)
class Finding:
    """Een enkele bevinding van een check op een object."""

    check_id: str
    severity: Severity
    dimension: Dimension
    object_uri: str
    object_label: str
    message: str
    typing_reliable: bool
    details: dict[str, object] = field(default_factory=dict)
    # De weg voor een bevinding op een object dat niet uit de GWSW-dataset komt: dat
    # heeft geen dataset-URI om op af te bakenen, dus zijn eigen RD-coordinaat neemt
    # die rol over. Geen enkele check vult dit veld nog sinds EXT-006 verviel; de weg
    # blijft bestaan voor de volgende check op een externe bron (BO-65).
    location: tuple[float, float] | None = None
    # Een bevinding die niet over een los object maar over de export als geheel gaat
    # (ATTR-014 meldt per kenmerk, over alle objecten samen). De meldingenlaag OR't
    # dit met de bestaande populatieratio; zie `melding._is_systemisch`.
    systemisch: bool = False


# Het type van een afgeleide structuur in de contextcache: wat `bouw` oplevert,
# krijgt de beller terug.
_Afgeleid = TypeVar("_Afgeleid")


# Wie welk cachevoorvoegsel vult (issue #118). `CheckContext._cache` is één platte
# stringruimte over alle checkmodules heen, en `cached` leunt met zijn ene `cast` op de
# afspraak dat een sleutel altijd met dezelfde `bouw` gevuld wordt. Die afspraak stond
# alleen in proza in de docstring hieronder; deze tabel maakt haar toetsbaar --
# `tests/test_checks_cachesleutels.py` houdt elke sleutel in `src/` ertegen, en een
# botsing is nergens anders aan te zien: de `cast` gelooft de beller op zijn woord.
#
# Het voorvoegsel is het deel voor de eerste dubbele punt. `ext:` is van de EXT-familie en
# `geo:` van de gedeelde geometrietabellen (issue #123); die twee hebben elk twee eigenaren.
CACHE_VOORVOEGSELS: dict[str, tuple[str, ...]] = {
    "aansluitingen": ("nlriochecker.checks.verbanden",),
    "adm010": ("nlriochecker.checks.administratief",),
    "ahn": ("nlriochecker.checks.extern",),
    "attr014": ("nlriochecker.checks.attributen",),
    "attr015": ("nlriochecker.checks.attributen",),
    "deelstelsel": ("nlriochecker.checks.verbanden",),
    "ext": ("nlriochecker.checks.extern", "nlriochecker.checks.wegvakken"),
    "geo": ("nlriochecker.checks.extern", "nlriochecker.checks.meetkunde"),
    "hgt": ("nlriochecker.checks.hoogten",),
    "hulpstukken": ("nlriochecker.checks.hulpstukken",),
    "net004": ("nlriochecker.checks.netwerk",),
    "net006": ("nlriochecker.checks.netwerk",),
    "onbereikbaar": ("nlriochecker.checks.netwerk",),
    "rvz": ("nlriochecker.checks.randvoorzieningen",),
    "sel": ("nlriochecker.checks.selectie",),
    "topologie": ("nlriochecker.checks.topologie",),
    "vrijverval": ("nlriochecker.checks.verbanden",),
}

# De sleutels zonder voorvoegsel, elk met de module die hem vult. Ze staan apart, want
# "begint met een bekend voorvoegsel" is niet hetzelfde als "heeft een voorvoegsel":
# `topologie` is allebei -- een kale sleutel én het voorvoegsel van `topologie:snapping`.
# Ze zijn niet fout en hoeven niet weg; ze moeten alleen opgeschreven staan, anders deelt
# een nieuwe kale sleutel ongemerkt de naamruimte met deze negen.
CACHE_KALE_SLEUTELS: dict[str, tuple[str, ...]] = {
    "afvoerpaden": ("nlriochecker.checks.verbanden",),
    "bereikbaarheid": ("nlriochecker.checks.verbanden",),
    "karakteristiek": ("nlriochecker.checks.base",),
    "net009": ("nlriochecker.checks.netwerk",),
    "netwerk": ("nlriochecker.checks.verbanden",),
    "netwerkdelen": ("nlriochecker.checks.verbanden",),
    "netwerkstrengen": ("nlriochecker.checks.verbanden",),
    "topologie": ("nlriochecker.checks.topologie",),
    "volledige-context": ("nlriochecker.checks.base",),
}


@dataclass(frozen=True)
class CheckContext:
    """Alles wat een check nodig heeft om te draaien."""

    dataset: GwswDataset
    config: CheckConfig
    unreliable_objects: frozenset[str] = frozenset()
    plausibiliteit: PlausibilityTables = field(default_factory=load_plausibility)
    bronnen: ExternalData | None = None
    # Met een studiegebied draaien de checks op de analyseset. Een check met
    # `volledig_bereik` heeft de volledige export nodig; die staat hier.
    volledige_dataset: GwswDataset | None = None
    analyseset: Analyseset | None = None
    # De volledige-export-context van een run over meerdere studiegebieden. Hij hangt
    # af van de volledige dataset, de config en de onbetrouwbare objecten -- alle drie
    # gebiedsonafhankelijk -- en mag daarom over gebieden heen gedeeld worden. Zonder
    # dit veld bouwt elk gebied zijn eigen volledige context met een lege cache, en
    # draaien de karakteristiek en de checks met `volledig_bereik` per gebied opnieuw
    # over de hele export.
    gedeelde_volledige_context: CheckContext | None = field(default=None, compare=False, repr=False)
    # De externe objecten die de EXT-checks tijdens deze run raken. Mutabel, net als
    # `_cache`: een check registreert zijn treffer terwijl hij draait, en `run_checks`
    # bouwt de `CheckOutcome` pas als de generator leeg is. Het register doet geen
    # uitspraken -- alleen wat een melding aanwijst komt in de uitvoer terecht -- dus
    # een entry die blijft staan kan geen verkeerde laag opleveren.
    treffers: Trefferregister = field(default_factory=Trefferregister, compare=False, repr=False)
    # Het oordeel van EXT-009 over elk kandidaat-wegvak (issue #104). Om dezelfde reden
    # mutabel als `treffers` hierboven; het verschil is dat de groene en grijze rijen
    # zonder melding in de laag `vlakken` terechtkomen, dus dit register bepaalt wél mee
    # wat de uitvoer toont. Zie `checks/treffers.Wegvakregister` en BO-79.
    wegvakken: Wegvakregister = field(default_factory=Wegvakregister, compare=False, repr=False)
    _cache: dict[str, object] = field(default_factory=dict, compare=False, repr=False)

    def volledige_context(self) -> CheckContext:
        """Dezelfde context, maar over de volledige export.

        Krijgt een eigen cache: de topologie-index en de netwerkgraaf van de
        volledige export zijn andere structuren dan die van de analyseset, en ze
        door elkaar halen zou de verkeerde antwoorden geven.
        """
        if self.gedeelde_volledige_context is not None:
            return self.gedeelde_volledige_context
        volledig = self.volledige_dataset
        if volledig is None or volledig is self.dataset:
            return self
        return self.cached(
            "volledige-context",
            lambda: replace(self, dataset=volledig, _cache={}),
        )

    def cached(self, sleutel: str, bouw: Callable[[], _Afgeleid]) -> _Afgeleid:
        """Bouwt een afgeleide structuur een keer per context en hergebruikt die.

        De topologie-index en de netwerkgraaf worden door meerdere checks en door
        `examined()` en `notes()` opgevraagd. Op een dataset met tienduizenden
        objecten is telkens opnieuw opbouwen merkbaar duur.

        Het type volgt uit `bouw`, zodat de bellers hun eigen structuur terugkrijgen
        en niet `object`. De cache zelf bewaart ze door elkaar en kan dat niet
        vasthouden; die ene `cast` is de prijs. Hij is veilig zolang een sleutel
        altijd met dezelfde `bouw` gevuld wordt, en daar zorgt het voorvoegsel voor:
        elk voorvoegsel heeft een eigenaar. `hgt:` en `rvz:` zijn van hun eigen
        checkmodule; `sel:` en `aansluitingen:` zijn juist gedeeld en horen bij
        `checks/selectie.py` respectievelijk `checks/verbanden.py`, die als enige
        die sleutels vullen; `ext:` is van de EXT-familie en heeft er twee --
        `checks/extern.py`, waar EXT-003 zijn kruisingenlijst onder bewaart, en
        `checks/wegvakken.py`, dat EXT-009 is. `geo:` draagt de gedeelde
        geometrietabellen (issue #123) en heeft er ook twee: `checks/meetkunde.py`
        voor de coordinaten (`geo:coords`, `geo:unieke-coords`) en `checks/extern.py`
        voor de geometrie waarmee de EXT-checks hun objecten selecteren.

        Welk voorvoegsel bij welke module hoort staat volledig in `CACHE_VOORVOEGSELS`
        hierboven, met de sleutels zonder voorvoegsel in `CACHE_KALE_SLEUTELS`; deze
        opsomming is een toelichting daarop en niet een tweede lijst.
        """
        if sleutel not in self._cache:
            self._cache[sleutel] = bouw()
        return cast(_Afgeleid, self._cache[sleutel])

    def is_reliable(self, uri: str) -> bool:
        """Geeft aan of de typering van dit object betrouwbaar genoeg is.

        De vergelijking gaat op URI. De SHACL-meting benoemt de te globale klassen
        en de instanties komen uit de dataset zelf, dus de koppeling is exact; het
        vervallen detailrapportformaat kon alleen op labels joinen.
        """
        return uri not in self.unreliable_objects

    def matched_objects(self) -> frozenset[str]:
        """De onbetrouwbare objecten die daadwerkelijk in de dataset voorkomen."""
        aanwezig = set(self.dataset.nodes) | set(self.dataset.conduits)
        return frozenset(self.unreliable_objects & aanwezig)

    def scope_in_woorden(self) -> str:
        """Noemt in woorden welk deel van de export deze context ziet.

        Bevindingsteksten citeerden lang "deze dataset". Onder een studiegebied is
        dat feitelijk onjuist: de check heeft dan alleen de kern plus de
        contextschil gezien, niet de volledige export. Elke check die die
        formulering zelf hardcodeert, loopt na de volgende afbakeningswijziging
        weer uit de pas; deze methode is de ene plek waar de formulering vandaan
        komt, zodat dat niet meer kan gebeuren.
        """
        if self.analyseset is None:
            return "deze dataset"
        return "het geanalyseerde deel (kern plus contextschil)"


@dataclass(frozen=True)
class CheckOutcome:
    """Het resultaat van een enkele check."""

    check_id: str
    title: str
    severity: Severity
    dimension: Dimension
    examined: int
    findings: list[Finding]
    # Uit de checkklasse overgenomen, net als `title` en `severity`: de uitvoerlaag
    # leest ze van de outcome en hoeft de registry er niet meer bij te halen.
    id_sleutels: tuple[str, ...]
    volledig_bereik: bool
    notes: list[str] = field(default_factory=list)
    weggelaten: int = 0
    skeleton: str = ""
    # Issue #64: overgenomen uit de checkklasse, net als `id_sleutels`. De uitvoerlaag
    # bouwt er de toelichtingsregel "Toetst <klassen> op <kenmerken>" mee op.
    rollen: tuple[str, ...] = ()
    kenmerken: tuple[str, ...] = ()
    # Issue #122: overgenomen uit de checkklasse, net als `id_sleutels`. De
    # meldingenlaag vult er de zijmap `Meldingenstroom.feiten` mee; hier met een
    # default, want `id_sleutels` hierboven staat vóór de eerste default.
    feit_sleutels: tuple[str, ...] = ()
    # Issue #96: de deelpopulatie in woorden van een check zonder rollen, overgenomen
    # uit de checkklasse. De uitvoerlaag zet hem in de regel "Toetst ..." waar anders
    # "de hele export" zou staan.
    populatie_omschrijving: str = ""
    # Issue #77: waarover `examined` geteld is. `run_checks` leidt hem af uit dezelfde
    # beslissing die de check zijn dataset gaf, dus hij kan er niet van afwijken.
    bekeken_scope: Scope = Scope.ANALYSESET

    @property
    def unreliable_count(self) -> int:
        """Het aantal bevindingen waarvan de typering onbetrouwbaar is."""
        return sum(1 for finding in self.findings if not finding.typing_reliable)

    @property
    def populatie(self) -> str:
        """De populatie die deze check declareert, in woorden (issue #77).

        Waar de check over *gaat*, en nadrukkelijk niet de noemer van `examined`: de
        declaratie is de vereniging van wat `run()`, `examined()` en `notes()`
        aanraken, en dus structureel een bovengrens. ATTR-018 declareert ook
        `leidingen` omdat zijn toelichting die telt, terwijl `examined` alleen
        vrijvervalstrengen plus putten telt. Wie het aantal wil, leest `examined`.

        De rollen gaan voor; declareert een check er geen, dan zeggen zijn kenmerken
        waar hij over gaat (RVZ-011 leest de drempelkenmerken, ATTR-014 alle
        kenmerken). Declareert hij geen van beide -- ADM-007 -- dan is er niets te
        noemen en blijft het leeg. Bewust géén terugval op "de hele export": die
        formulering hoort bij de regel "Toetst ...", waar zij betekent dat de check
        niet tot een rol beperkt is, en zou achter een telling als de noemer lezen.
        """
        if self.rollen:
            return ", ".join(self.rollen)
        return ", ".join("alle kenmerken" if k == "*" else k for k in self.kenmerken)


@dataclass(frozen=True)
class CheckRun:
    """Alle uitgevoerde checks over een dataset."""

    dataset: GwswDataset
    outcomes: list[CheckOutcome]
    typing_gate_applied: bool
    # De uitvoerlaag heeft de klassenlijsten en de rapportdrempels nodig; die
    # meegeven is minder broos dan ze langs elke schrijver door te reiken.
    #
    # Nooit None. Een ontbrekende config zou elke schrijver dwingen stil een eigen
    # `checks.toml` te lezen, en dan kan een run met projectconfig met andere
    # drempels rapporteren dan waarmee hij getoetst is -- dezelfde reden waarom
    # `meetbereik` hieronder nooit None is.
    config: CheckConfig
    # De context waarmee de checks daadwerkelijk gedraaid hebben. De schrijvers lezen
    # hem in plaats van zelf een `CheckContext` te bouwen: een eigen context begint
    # met een lege cache en kan -- bij een afwijkende opbouw -- een ander afvoerpad
    # tekenen dan de checks beoordeelden.
    context: CheckContext = field(compare=False, repr=False)
    unreliable_labels: int = 0
    unreliable_labels_in_dataset: int = 0
    study_area: StudyArea | None = None
    bronnen: ExternalData | None = None
    karakteristiek: DataCharacteristics | None = None
    # De kern en de contextschil waarop de checks gedraaid hebben; None zonder
    # studiegebied. De uitvoerlaag meldt hieruit hoe groot elk deel was.
    analyseset: Analyseset | None = None
    # Tegen welke conformiteitsklassen deze run getoetst is. De uitvoerlaag heeft het
    # nodig voor de markering boven het rapport, voor `gwsw_run` en voor de
    # JSON-envelop; het hier meegeven is minder broos dan het langs elke schrijver
    # doorreiken -- dezelfde reden waarom `config` en `analyseset` hier staan.
    #
    # Nooit None. Een run die zijn bereik niet kreeg is er een zonder nulmeting, en
    # dat is een toestand die `Meetbereik` al kent. Zou `None` toegestaan zijn, dan
    # moest elke schrijver dat vierde geval zelf duiden, en dan zeggen ze er
    # verschillende dingen over -- Markdown zweeg terwijl de JSON `volledig: false`
    # beweerde.
    meetbereik: Meetbereik = field(default_factory=lambda: Meetbereik.niet_gemeten(()))
    # De overtredingen uit de SHACL-nulmeting, herleid tot objecten uit deze dataset.
    # Ze zijn geen `CheckOutcome`: de nulmeting is een tweede bron naast het register,
    # geen zeventigtal extra checks. `uitvoer.melding.bouw_meldingen` maakt er
    # meldingen van naast die van de checks, zodat de vier uitvoervormen ook hiervoor
    # uit een stroom komen. Zie `nulbevinding.py` en BO-28.
    nulbevindingen: tuple[Nulbevinding, ...] = ()
    # Hoeveel nulmetingbevindingen de afbakening tot het studiegebied weggelaten
    # heeft. Het tegenhangertje van `CheckOutcome.weggelaten`, en om dezelfde reden:
    # een rapport dat wel afbakent maar niet zegt hoeveel er buiten viel, leest als
    # "dit is alles".
    nulbevindingen_weggelaten: int = 0
    # De klassen die de nulmeting te globaal noemt maar die de typeringspoort niet naar
    # objecten in het domeinmodel kon herleiden (`TypingGate.unassessable_classes`,
    # gebundeld over de conformiteitsklassen). Runmetadata zoals `meetbereik`, geen
    # melding: `analyseer` noemt ze al, en het toets-rapport zou er anders over zwijgen
    # -- stilte over een klasse die niet beoordeeld is leest als "beoordeeld en niets
    # gevonden". Zie `uitvoer/bevindingen.py` en issue #52.
    niet_beoordeelde_klassen: tuple[str, ...] = ()
    # Het trefferregister van de context waarop deze run gedraaid heeft; de
    # GeoPackage-schrijver joint de meldingen erop om de lagen met externe objecten te
    # vullen. Zie `checks/treffers.py`.
    treffers: Trefferregister = field(default_factory=Trefferregister, compare=False, repr=False)
    # Het wegvakregister van diezelfde context: de volledige EXT-009-classificatie,
    # waaruit de laag `vlakken` haar groene en grijze wegvakken haalt (BO-79). Anders dan
    # `treffers` wordt dit register in `beperk_tot_studiegebied` mee afgebakend, want zijn
    # rijen hangen niet aan een melding die daar al doorheen gaat.
    wegvakken: Wegvakregister = field(default_factory=Wegvakregister, compare=False, repr=False)
    _binnen: frozenset[str] | None = field(default=None, compare=False, repr=False)

    @property
    def findings(self) -> list[Finding]:
        """Alle bevindingen van alle checks, na afbakening tot het studiegebied."""
        return [finding for outcome in self.outcomes for finding in outcome.findings]

    def count(self, severity: Severity) -> int:
        """Het aantal bevindingen van een ernstniveau.

        Alleen de bevindingen van de eigen checks; de overtredingen uit de nulmeting
        staan in `nulbevindingen` en worden pas in `bouw_meldingen` meldingen. Wie
        het totaal wil, telt over de meldingenstroom.
        """
        return sum(1 for finding in self.findings if finding.severity is severity)

    @property
    def weggelaten(self) -> int:
        """Alles wat de afbakening tot het studiegebied heeft weggelaten.

        De bevindingen van de checks plus de overtredingen uit de nulmeting. Een
        rapport dat afbakent maar niet zegt hoeveel er buiten viel, leest als "dit is
        alles"; deze eigenschap is de ene plek waar dat getal vandaan komt, zodat de
        opdrachtregel, het rapport en de synthese er niet drie kunnen noemen.
        """
        return sum(outcome.weggelaten for outcome in self.outcomes) + self.nulbevindingen_weggelaten

    def objecten_binnen(self) -> frozenset[str] | None:
        """De objecten binnen het studiegebied, of None als er geen gebied is.

        Wordt een keer bepaald: de afbakening en de GIS-export vroegen het allebei,
        en het is een doorloop over alle put- en strenggeometrieen.
        """
        if self.study_area is None:
            return None
        if self._binnen is None:
            object.__setattr__(self, "_binnen", objecten_in_gebied(self.dataset, self.study_area))
        return self._binnen

    def beperk_tot_studiegebied(
        self,
        area: StudyArea,
        binnen: frozenset[str] | None = None,
        *,
        leeg_toegestaan: bool = False,
    ) -> CheckRun:
        """Geeft een run terug met alleen de bevindingen binnen het gebied.

        Met een studiegebied zijn de checks al op de kern plus de contextschil
        gedraaid -- ruim genoeg dat de netwerkchecks hetzelfde antwoord geven als
        op de volledige dataset -- en pas hier wordt tot de kern afgebakend. Zo
        ontstaan er geen randeffecten doordat een streng het gebied uit loopt.
        Checks die over de hele populatie gaan (`Check.volledig_bereik`, of hun
        ID in `config.studiegebied.volledige_dataset_checks`) zijn sowieso op de
        volledige export blijven draaien.

        `binnen` mag de beller meegeven als hij de kern al kent. Dat is precies
        `Analyseset.kern`: die is de verzameling objecten van de *volledige* export
        die het gebied raken, de schil is er per constructie van losgetrokken, en de
        uitgedunde dataset is kern plus schil. Opnieuw over alle geometrieen lopen
        levert dus dezelfde verzameling, tegen de prijs van een volledige doorloop
        per gebied.

        `leeg_toegestaan` is voor de rapportage over meerdere gebieden: een buurt
        zonder riolering (water, natuur, bedrijventerrein) is daar een normaal
        gegeven en mag de andere gebieden niet meeslepen. Bij een run op een enkel
        gebied blijft het een harde fout, want daar is het bijna altijd een verkeerd
        bestand of een verkeerde laagkeuze.
        """
        binnen = objecten_in_gebied(self.dataset, area) if binnen is None else binnen
        if not binnen and not leeg_toegestaan:
            raise StudyAreaError(
                f"studiegebied {area.name!r} ({area.area_ha:.1f} ha) bevat geen GWSW-objecten: "
                f"geen enkele put en geen enkele streng valt erbinnen. Controleer de laagkeuze "
                f"en of het gebied binnen het beheergebied van {self.dataset.source.name} ligt."
            )

        def hoort_erbij(finding: Finding) -> bool:
            """Geeft aan of deze bevinding binnen het studiegebied valt."""
            if finding.object_uri in binnen:
                return True
            if finding.location is not None:
                return area.bevat(Point(*finding.location))
            # Een dataset-brede bevinding zonder object en zonder locatie (ATTR-014
            # meldt per kenmerk) is aan geen enkel gebied toe te wijzen en blijft in
            # elk gebiedsrapport staan -- dezelfde regel als `_nul_hoort_erbij` voor
            # een nulmetingbevinding die nergens op uitkwam (BO-12).
            if not finding.object_uri:
                return True
            return False

        # `replace` in plaats van elk veld opsommen -- ook hier, en om dezelfde reden
        # als bij de run hieronder: de opsomming vergat `rollen` en `kenmerken`, zodat
        # elk gebiedsrapport "Toetst de hele export" zei, en het scopelabel van issue
        # #77 zou er langs diezelfde weg uitvallen.
        outcomes = []
        for outcome in self.outcomes:
            binnen_gebied = [f for f in outcome.findings if hoort_erbij(f)]
            outcomes.append(
                replace(
                    outcome,
                    findings=binnen_gebied,
                    weggelaten=len(outcome.findings) - len(binnen_gebied),
                )
            )
        # `replace` in plaats van elk veld opsommen: die opsomming vergat bij elke
        # uitbreiding een veld, en dan valt het stil weg op precies de runs met een
        # studiegebied.
        nulbevindingen = tuple(
            bevinding for bevinding in self.nulbevindingen if _nul_hoort_erbij(bevinding, binnen)
        )
        return replace(
            self,
            outcomes=outcomes,
            nulbevindingen=nulbevindingen,
            nulbevindingen_weggelaten=len(self.nulbevindingen) - len(nulbevindingen),
            study_area=area,
            # Op hun middelpunt, precies zoals `hoort_erbij` een bevinding met een eigen
            # locatie afbakent: de rode melding en het groene vlak van hetzelfde wegvak
            # horen niet aan verschillende kanten van de gebiedsgrens te vallen.
            wegvakken=self.wegvakken.binnen(area.bevat),
            _binnen=binnen,
        )


def _nul_hoort_erbij(bevinding: Nulbevinding, binnen: frozenset[str]) -> bool:
    """Geeft aan of deze nulmetingbevinding in het studiegebied hoort.

    Een bevinding die tot een knoop of streng herleid is, volgt de gewone regel: hij
    telt mee als dat object het gebied raakt. Een bevinding die nergens op uitkwam --
    een klassenaam uit `CfkTypes_typ`, een stelsel als `dru_geb_0` -- is aan geen
    enkel gebied toe te wijzen en blijft daarom in elke gebiedsrun staan. Een losse
    run over dat ene gebied zou hem ook opnemen, en dat is de equivalentie-eis van
    BO-12; hem hier wegfilteren zou hem uit *elk* gebiedsrapport laten verdwijnen.
    """
    return bevinding.object_uri in binnen if bevinding.herleid else True


class Check(ABC):
    """Basisklasse van een check uit het checkregister."""

    id: ClassVar[str]
    title: ClassVar[str]
    severity: ClassVar[Severity]
    dimension: ClassVar[Dimension]
    # De detailsleutels die twee bevindingen van deze check op hetzelfde object van
    # elkaar onderscheiden. 'zijde' is de gangbare: verschillende HGT-checks melden
    # per strengeinde. Heeft een check een eigen onderscheid, dan declareert ze dat
    # hier; de meldingenlaag waarschuwt als er toch twee dezelfde ID krijgen.
    id_sleutels: ClassVar[tuple[str, ...]] = ("zijde",)
    # Issue #122: de detailsleutels die deze check aan de uitvoer doorgeeft. Dezelfde
    # vorm als `id_sleutels` hierboven, en met dezelfde reden: `Finding.details` haalt
    # de meldingenstroom niet, en een algemeen doorgeefluik zou elke detailsleutel van
    # elke check tot een uitvoercontract maken. Wat hier staat reist mee in de zijmap
    # `Meldingenstroom.feiten` -- niet in een veld op `Melding`, want dat landt
    # reflectief in de bevroren JSON-envelop. Optioneel, anders moeten 99 checks een
    # lege tuple opschrijven.
    feit_sleutels: ClassVar[tuple[str, ...]] = ()
    # Checks die over de hele populatie gaan in plaats van over losse objecten
    # (ADM-002: dubbele identificaties kunnen overal in de export zitten). Ze
    # draaien ook met een studiegebied op de volledige export. Een project kan
    # hetzelfde bereiken zonder de code te wijzigen door het check-ID op te nemen
    # in `config.studiegebied.volledige_dataset_checks`; `run_checks` telt beide
    # bronnen mee.
    volledig_bereik: ClassVar[bool] = False
    # Checks waarvan `examined()` kenmerkinstanties telt in plaats van objecten
    # (ATTR-014 telt elke instantie van elk kenmerk, BTR-006 elke hoogtewaarde). Hun
    # noemer is van een andere soort dan die van de andere checks; `run_checks` zet
    # daarom de scope van hun uitslag op `Scope.ATTRIBUUT_INSTANTIES`. Zie BO-58.
    telt_instanties: ClassVar[bool] = False
    # Issue #64: de GWSW-populatie en -kenmerken die deze check declareert. `rollen` zijn
    # namen uit `selectie._ROLLEN` -- de populatie die de check langsloopt. `kenmerken`
    # zijn GWSW-kenmerknamen zoals de code ze aan `aspect`/`number`/`reference`/`date`
    # geeft, of een `config:<pad>`-verwijzing als de lijst uit de configuratie komt
    # (ATTR-013), of `*` voor een check die over alle kenmerken gaat (ATTR-014). Geen
    # default: `register()` weigert een check die er niet allebei declareert, zodat een
    # nieuwe check niet stilzwijgend zonder herkomst de registry in glipt. De twee
    # drifttests in `tests/test_checkdeclaraties.py` houden ze tegen de code en de
    # ontologie.
    rollen: ClassVar[tuple[str, ...]]
    kenmerken: ClassVar[tuple[str, ...]]
    # Issue #96: de deelpopulatie in woorden, voor een check die zijn objecten niet via
    # een rol haalt maar via engine-navigatie (RVZ-011 loopt de overstortdrempel-index)
    # of via de projectconfiguratie (ADM-007 leest `[[puttyperegels]]`). De regel
    # "Toetst ..." valt zonder rollen terug op "de hele export", en dat zegt van een
    # check die juist een smalle deelpopulatie bekeek het omgekeerde. Leeg bij elke
    # check met een rol -- daar komen de klassen uit de rollen -- en leeg bij ATTR-014,
    # die werkelijk de hele export op alle kenmerken langsloopt.
    populatie_omschrijving: ClassVar[str] = ""

    @abstractmethod
    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Levert de bevindingen van deze check op de dataset."""

    def notes(self, context: CheckContext) -> list[str]:
        """Toelichtingen bij het bereik van deze check, bijvoorbeeld wat er buiten viel."""
        return []

    def examined(self, context: CheckContext) -> int:
        """Het aantal objecten dat deze check bekeken heeft."""
        return len(context.dataset.nodes) + len(context.dataset.conduits)

    def finding(
        self,
        context: CheckContext,
        uri: str,
        label: str,
        message: str,
        location: tuple[float, float] | None = None,
        *,
        systemisch: bool = False,
        **details: object,
    ) -> Finding:
        """Bouwt een bevinding en zet de typeringsvlag op grond van het label.

        `systemisch` staat keyword-only en vóór `**details`, zodat de naam nooit als
        detailsleutel opgeslokt kan worden: een check die hem meegaf zou anders een
        melding per object krijgen met een detailveld dat het tegendeel beweert. Wat een
        systemische bevinding is en waar zij landt staat bij `Finding.systemisch`
        (issue #76).
        """
        return Finding(
            check_id=self.id,
            severity=self.severity,
            dimension=self.dimension,
            object_uri=uri,
            object_label=label,
            message=message,
            typing_reliable=context.is_reliable(uri),
            details=details,
            location=location,
            systemisch=systemisch,
        )


class SkeletonCheck(Check):
    """Een check die in het register staat maar (nog) geen uitslag kan geven.

    Stilzwijgend overslaan mag niet: een check die er niet is, leest in het rapport
    als een check zonder bevindingen. Een skelet levert daarom nul bevindingen op
    met een expliciete markering en reden erbij, zodat rapport en dekkingsmatrix
    laten zien wat er *niet* gekeken is.
    """

    markering: ClassVar[str]
    reden: ClassVar[str]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Levert nooit bevindingen; deze check is niet uitvoerbaar."""
        return iter(())

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de markering en de reden waarom er niets getoetst is."""
        return [f"**{self.markering}** — {self.reden}"]

    def examined(self, context: CheckContext) -> int:
        """Een skelet bekijkt niets."""
        return 0


REGISTRY: dict[str, type[Check]] = {}


def register(check: type[Check]) -> type[Check]:
    """Registreert een check onder haar ID uit het checkregister.

    Weigert een check die `rollen` of `kenmerken` niet declareert (issue #64): zonder die
    twee draagt de uitslag geen herkomst en ontsnapt de check aan de drifttests. Een
    lege declaratie (`()`) mag; het ontbreken ervan niet.
    """
    if check.id in REGISTRY:
        raise ValueError(f"check-ID {check.id} is al geregistreerd")
    for veld in ("rollen", "kenmerken"):
        if not hasattr(check, veld):
            raise ValueError(
                f"check-ID {check.id} declareert geen `{veld}`; elke check moet zijn "
                "GWSW-populatie en -kenmerken benoemen (issue #64)."
            )
    REGISTRY[check.id] = check
    return check


def _scope(check: Check, over_volledige_populatie: bool) -> Scope:
    """Waarover `examined()` van deze check geteld heeft (issue #77).

    Twee onafhankelijke assen, en de instantieteller wint: telt een check geen
    objecten, dan zegt "volledige export" niets over zijn noemer. ATTR-014 heeft
    `volledig_bereik` én telt instanties, en heet daarom `attribuut_instanties`.
    """
    if check.telt_instanties:
        return Scope.ATTRIBUUT_INSTANTIES
    return Scope.VOLLEDIGE_EXPORT if over_volledige_populatie else Scope.ANALYSESET


def run_checks(
    context: CheckContext,
    check_ids: list[str] | None = None,
    typing_gate_applied: bool = False,
    *,
    voortgang: Voortgang = NUL_VOORTGANG,
    fase: str = "Checks",
) -> CheckRun:
    """Draait de gevraagde checks; zonder selectie draait de hele registry.

    De voortgang meldt per check het ID, zodat zichtbaar is welke check loopt en
    niet alleen dat er iets loopt. Hij raakt de uitkomst niet. `fase` is het label
    van de voortgangsfase; een run over meerdere gebieden zet de gebiedsnaam erin,
    zodat zichtbaar blijft welk gebied loopt.
    """
    gekozen = sorted(REGISTRY) if check_ids is None else list(check_ids)

    onbekend = [check_id for check_id in gekozen if check_id not in REGISTRY]
    if onbekend:
        raise KeyError(f"onbekende check-ID's: {', '.join(sorted(onbekend))}")

    volledige_ids = set(context.config.studiegebied.volledige_dataset_checks)

    outcomes = []
    voortgang.start_fase(fase, len(gekozen))
    try:
        for check_id in gekozen:
            check = REGISTRY[check_id]()
            over_volledige_populatie = check.volledig_bereik or check.id in volledige_ids
            gebruikt = context.volledige_context() if over_volledige_populatie else context
            if gebruikt is not context:
                # De volledige-export-context heeft een eigen trefferregister, en bij
                # een run over meerdere gebieden is dat een gedeeld exemplaar. Een
                # check die daar zijn treffers in achterlaat, zou een melding met
                # `object2_uri` opleveren waarvan de GIS-laag het object niet meer kan
                # vinden -- precies de stille afwijking tussen laag en uitslag die dit
                # ontwerp uitsluit. `replace` deelt het cachewoordenboek, dus de dure
                # structuren van de volledige export blijven hergebruikt.
                gebruikt = replace(gebruikt, treffers=context.treffers, wegvakken=context.wegvakken)
            # De bevindingen bewust vóór de toelichting: `notes()` van de EXT-checks
            # leest wat `run()` in het register meldde. Als keyword-argument zou de
            # volgorde ook kloppen, maar dan staat ze nergens.
            bevindingen = list(check.run(gebruikt))
            outcomes.append(
                CheckOutcome(
                    check_id=check.id,
                    title=check.title,
                    severity=check.severity,
                    dimension=check.dimension,
                    examined=check.examined(gebruikt),
                    findings=bevindingen,
                    id_sleutels=check.id_sleutels,
                    feit_sleutels=check.feit_sleutels,
                    volledig_bereik=check.volledig_bereik,
                    notes=check.notes(gebruikt),
                    skeleton=check.markering if isinstance(check, SkeletonCheck) else "",
                    rollen=check.rollen,
                    kenmerken=check.kenmerken,
                    populatie_omschrijving=check.populatie_omschrijving,
                    bekeken_scope=_scope(check, over_volledige_populatie),
                )
            )
            voortgang.stap(label=check.id)
    finally:
        voortgang.einde_fase()

    # De datakarakteristiek en de telling van onbetrouwbaar getypeerde objecten
    # gaan altijd over de volledige export, ook met een studiegebied: het rapport
    # noemt ze expliciet stabiel onder afbakening, en beide zijn een goedkope
    # doorloop respectievelijk verzamelingsdoorsnede, dus versmallen heeft geen nut.
    volledig = context.volledige_context()
    return CheckRun(
        dataset=context.dataset,
        outcomes=outcomes,
        typing_gate_applied=typing_gate_applied,
        unreliable_labels=len(context.unreliable_objects),
        unreliable_labels_in_dataset=len(volledig.matched_objects()),
        bronnen=context.bronnen,
        karakteristiek=volledig.cached(
            "karakteristiek", lambda: bepaal_karakteristiek(volledig.dataset, context.config)
        ),
        config=context.config,
        context=context,
        analyseset=context.analyseset,
        treffers=context.treffers,
        wegvakken=context.wegvakken,
    )
