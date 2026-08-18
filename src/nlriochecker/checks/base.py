"""Raamwerk voor de checks: ernst, dimensie, bevindingen en de registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import ClassVar, TypeVar, cast

from shapely.geometry import Point

from nlriochecker.afbakening import Analyseset, objecten_in_gebied
from nlriochecker.checkconfig import CheckConfig
from nlriochecker.dataset import GwswDataset
from nlriochecker.errors import StudyAreaError
from nlriochecker.externedata import ExternalData
from nlriochecker.karakteristiek import DataCharacteristics, bepaal_karakteristiek
from nlriochecker.meting import Meetbereik
from nlriochecker.plausibiliteit import PlausibilityTables, load_plausibility
from nlriochecker.studiegebied import StudyArea
from nlriochecker.voortgang import NUL_VOORTGANG, Voortgang


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
    # De EXT-checks melden ook objecten die niet uit de GWSW-dataset komen (een
    # BGT-putdeksel zonder put, een BAG-pand zonder riolering). Die hebben geen
    # dataset-URI om op af te bakenen; hun eigen RD-coordinaat neemt die rol over.
    location: tuple[float, float] | None = None


# Het type van een afgeleide structuur in de contextcache: wat `bouw` oplevert,
# krijgt de beller terug.
_Afgeleid = TypeVar("_Afgeleid")


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
        altijd met dezelfde `bouw` gevuld wordt -- de sleutels zijn per module
        voorvoegsel gescheiden (`rvz:`, `net:`, `top:`).
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
    notes: list[str] = field(default_factory=list)
    weggelaten: int = 0
    skeleton: str = ""

    @property
    def unreliable_count(self) -> int:
        """Het aantal bevindingen waarvan de typering onbetrouwbaar is."""
        return sum(1 for finding in self.findings if not finding.typing_reliable)


@dataclass(frozen=True)
class CheckRun:
    """Alle uitgevoerde checks over een dataset."""

    dataset: GwswDataset
    outcomes: list[CheckOutcome]
    typing_gate_applied: bool
    unreliable_labels: int = 0
    unreliable_labels_in_dataset: int = 0
    study_area: StudyArea | None = None
    bronnen: ExternalData | None = None
    karakteristiek: DataCharacteristics | None = None
    # De uitvoerlaag heeft de klassenlijsten en de rapportdrempels nodig; die
    # meegeven is minder broos dan ze langs elke schrijver door te reiken.
    config: CheckConfig | None = None
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
    _binnen: frozenset[str] | None = field(default=None, compare=False, repr=False)

    @property
    def findings(self) -> list[Finding]:
        """Alle bevindingen van alle checks, na afbakening tot het studiegebied."""
        return [finding for outcome in self.outcomes for finding in outcome.findings]

    def count(self, severity: Severity) -> int:
        """Het aantal bevindingen van een ernstniveau."""
        return sum(1 for finding in self.findings if finding.severity is severity)

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

    def beperk_tot_studiegebied(self, area: StudyArea) -> CheckRun:
        """Geeft een run terug met alleen de bevindingen binnen het gebied.

        Met een studiegebied zijn de checks al op de kern plus de contextschil
        gedraaid -- ruim genoeg dat de netwerkchecks hetzelfde antwoord geven als
        op de volledige dataset -- en pas hier wordt tot de kern afgebakend. Zo
        ontstaan er geen randeffecten doordat een streng het gebied uit loopt.
        Checks die over de hele populatie gaan (`Check.volledig_bereik`, of hun
        ID in `config.studiegebied.volledige_dataset_checks`) zijn sowieso op de
        volledige export blijven draaien.
        """
        binnen = objecten_in_gebied(self.dataset, area)
        if not binnen:
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
            return False

        outcomes = []
        for outcome in self.outcomes:
            binnen_gebied = [f for f in outcome.findings if hoort_erbij(f)]
            outcomes.append(
                CheckOutcome(
                    check_id=outcome.check_id,
                    title=outcome.title,
                    severity=outcome.severity,
                    dimension=outcome.dimension,
                    examined=outcome.examined,
                    findings=binnen_gebied,
                    notes=outcome.notes,
                    weggelaten=len(outcome.findings) - len(binnen_gebied),
                    skeleton=outcome.skeleton,
                )
            )
        # `replace` in plaats van elk veld opsommen: die opsomming vergat bij elke
        # uitbreiding een veld, en dan valt het stil weg op precies de runs met een
        # studiegebied.
        return replace(self, outcomes=outcomes, study_area=area, _binnen=binnen)


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
    # Checks die over de hele populatie gaan in plaats van over losse objecten
    # (ADM-002: dubbele identificaties kunnen overal in de export zitten). Ze
    # draaien ook met een studiegebied op de volledige export. Een project kan
    # hetzelfde bereiken zonder de code te wijzigen door het check-ID op te nemen
    # in `config.studiegebied.volledige_dataset_checks`; `run_checks` telt beide
    # bronnen mee.
    volledig_bereik: ClassVar[bool] = False

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
        **details: object,
    ) -> Finding:
        """Bouwt een bevinding en zet de typeringsvlag op grond van het label."""
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
    """Registreert een check onder haar ID uit het checkregister."""
    if check.id in REGISTRY:
        raise ValueError(f"check-ID {check.id} is al geregistreerd")
    REGISTRY[check.id] = check
    return check


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
            outcomes.append(
                CheckOutcome(
                    check_id=check.id,
                    title=check.title,
                    severity=check.severity,
                    dimension=check.dimension,
                    examined=check.examined(gebruikt),
                    findings=list(check.run(gebruikt)),
                    notes=check.notes(gebruikt),
                    skeleton=check.markering if isinstance(check, SkeletonCheck) else "",
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
        analyseset=context.analyseset,
    )
