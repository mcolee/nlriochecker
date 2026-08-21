"""Meting bij issue #32: wat zouden de voorgestelde klassenlijsten op De Wolden doen?

Issue #32 stelt per punt een uitbreiding van een `[klassen]`-lijst in `checks.toml`
voor. Dit script wijzigt niets; het telt alleen hoeveel objecten in
`data/gwsw_orox_ttl/dewolden_orox.ttl` door zo'n uitbreiding van categorie zouden
veranderen, zodat de auteur per punt kan zien of de ingreep gedragsneutraal is.

Twee vragen worden hier streng gescheiden gehouden:

* **Bestaat de klasse in de GWSW-ontologie?** Dat is een eigenschap van
  `Ontologie_GWSW_Totaal.ttl` en zegt iets over ons model. Het antwoord staat per
  klasse in de kolom `bestaat`.
* **Komen er instanties van voor in deze dataset?** Dat is een eigenschap van de
  BrutIS-export van De Wolden en zegt iets over de aanlevering. Het antwoord staat
  in de kolommen `instanties`, `knopen` en `verbindingen`.

Een klasse die wel bestaat maar nul instanties heeft, verandert op deze dataset
niets -- en dat is precies de vraag die dit script beantwoordt.

**Waarom een eigen parser en niet `nlriochecker.dataset.load_dataset`.** De export
is 112 MB; rdflib heeft er ruim drie minuten en circa 3 GB voor nodig. De export is
regelgeoriënteerd en volstrekt regelmatig (elk subject op een eigen regel, elk
predicaat op een ingesprongen regel), dus een gerichte scan volstaat en kost acht
seconden. Twee waarborgen houden die kortere weg eerlijk:

* `_toets_regelvorm()` breekt af zodra de export de verkorte Turtle-notatie met
  blanke knopen gebruikt, want daar zou de regelscan een `rdf:type` aan het
  verkeerde object toekennen.
* `_controleer_parser()` haalt een uittreksel van dezelfde export door de
  pakketlader en vergelijkt knopen, verbindingen en beide klassentellingen met de
  regelscan over datzelfde uittreksel.
"""

from __future__ import annotations

import re
import sys
import tempfile
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDFS, Graph, URIRef

WORTEL = Path(__file__).resolve().parents[2]
ONTOLOGIE = WORTEL / "data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl"
EXPORT = WORTEL / "data/gwsw_orox_ttl/dewolden_orox.ttl"
# De twee bestanden waarin `[klassen]` staat. De huidige lijsten worden hieruit
# gelezen en niet overgeschreven uit het issue: anders zou de meting stil verouderen
# zodra iemand een lijst aanpast.
CONFIGS = (
    WORTEL / "src/nlriochecker/checks.toml",
    WORTEL / "configs/dewoldenhoogeveen.toml",
)
# Welke stukken van de export door de pakketlader gehaald worden om de regelscan te
# ijken, als (startregel, lengte). De export schrijft eerst alle putten en pas rond
# regel 1.49 miljoen de leidingen; twee vensters vangen dus beide objectsoorten.
CONTROLEVENSTERS = ((1, 150_000), (1_450_000, 150_000))

# Een Turtle-regel mag op een commentaar eindigen. De BrutIS-export van De Wolden doet
# dat nergens, maar het handgeschreven voorbeeldbestand -- waarmee `_controleer_parser`
# de scan ijkt -- wel: `rdf:type gwsw:VerdektePut ; # extra objecttype`. Zonder deze
# staart mist de scan die tripels stilzwijgend. Alleen een `#` na witruimte telt als
# commentaar, zodat een `#` binnenin een IRI blijft staan.
_STAART = r"\s*[;.]?\s*(?:#.*)?$"
_TYPE = re.compile(r"^\s*rdf:type\s+gwsw:(\S+?)" + _STAART)
_ASPECT = re.compile(r"^\s*gwsw:hasAspect\s+(\S+?)" + _STAART)
_DEEL = re.compile(r"^\s*gwsw:hasPart\s+(\S+?)" + _STAART)
_SUBJECT = re.compile(r"^(\S+)\s*(?:#.*)?$")


def _kort(uri: object) -> str:
    """De lokale naam van een klasse-URI."""
    return str(uri).rsplit("/", 1)[-1]


def _huidige_klassen() -> dict[str, object]:
    """Het `[klassen]`-blok zoals het nu in de configuratie staat.

    Beide configbestanden dragen hun eigen kopie; lopen ze uiteen, dan is niet te
    zeggen welke lijst gemeten wordt en breekt dit script af.
    """
    gelezen = [tomllib.loads(pad.read_text(encoding="utf-8")).get("klassen", {}) for pad in CONFIGS]
    if gelezen[0] != gelezen[1]:
        afwijkend = sorted(
            sleutel
            for sleutel in set(gelezen[0]) | set(gelezen[1])
            if gelezen[0].get(sleutel) != gelezen[1].get(sleutel)
        )
        sys.exit(f"[klassen] verschilt tussen {CONFIGS[0]} en {CONFIGS[1]}: {afwijkend}")
    return dict(gelezen[0])


def _lijst(tabel: dict[str, object], sleutel: str) -> list[str]:
    """Een klassenlijst uit een TOML-tabel, met een duidelijke fout als hij ontbreekt."""
    waarde = tabel.get(sleutel)
    if not isinstance(waarde, list) or not all(isinstance(naam, str) for naam in waarde):
        sys.exit(f"[klassen] {sleutel}: geen lijst van klassenamen maar {waarde!r}.")
    return [str(naam) for naam in waarde]


def _stelseltabel(klassen: dict[str, object]) -> dict[str, object]:
    """De subtabel `[klassen.stelseltypen]`."""
    waarde = klassen.get("stelseltypen")
    if not isinstance(waarde, dict):
        sys.exit(f"[klassen.stelseltypen]: geen tabel maar {waarde!r}.")
    return dict(waarde)


def _stelselwortels(klassen: dict[str, object]) -> list[str]:
    """Alle wortelklassen die nu ergens in `[klassen.stelseltypen]` staan."""
    tabel = _stelseltabel(klassen)
    return sorted({naam for sleutel in tabel for naam in _lijst(tabel, sleutel)})


@dataclass(frozen=True)
class Ontologie:
    """De klassenboom van het GWSW, als korte namen."""

    kinderen: dict[str, frozenset[str]]
    ouders: dict[str, frozenset[str]]

    @classmethod
    def laad(cls, pad: Path) -> Ontologie:
        """Leest `rdfs:subClassOf` uit een ontologiebestand."""
        graaf = Graph()
        graaf.parse(pad, format="turtle")
        kinderen: dict[str, set[str]] = defaultdict(set)
        ouders: dict[str, set[str]] = defaultdict(set)
        for kind, ouder in graaf.subject_objects(RDFS.subClassOf):
            if isinstance(kind, URIRef) and isinstance(ouder, URIRef):
                kinderen[_kort(ouder)].add(_kort(kind))
                ouders[_kort(kind)].add(_kort(ouder))
        return cls(
            kinderen={k: frozenset(v) for k, v in kinderen.items()},
            ouders={k: frozenset(v) for k, v in ouders.items()},
        )

    def bestaat(self, klasse: str) -> bool:
        """Of de ontologie deze klasse kent."""
        return klasse in self.kinderen or klasse in self.ouders

    def afsluiting(self, wortels: Iterable[str]) -> frozenset[str]:
        """De wortels plus al hun subklassen, net als `GwswDataset.closure`."""
        gezien = set(wortels)
        stapel = list(gezien)
        while stapel:
            huidig = stapel.pop()
            for kind in self.kinderen.get(huidig, ()):
                if kind not in gezien:
                    gezien.add(kind)
                    stapel.append(kind)
        return frozenset(gezien)

    def voorouders(self, klasse: str) -> frozenset[str]:
        """Alle bovenklassen van een klasse."""
        gezien: set[str] = set()
        stapel = [klasse]
        while stapel:
            for ouder in self.ouders.get(stapel.pop(), ()):
                if ouder not in gezien:
                    gezien.add(ouder)
                    stapel.append(ouder)
        return frozenset(gezien)


@dataclass
class Export:
    """De gescande OroX-export: typen, knopen, verbindingen en hasPart-leden."""

    ontologie: Ontologie
    types: dict[str, frozenset[str]] = field(default_factory=dict)
    knopen: dict[str, str] = field(default_factory=dict)
    verbindingen: set[str] = field(default_factory=set)
    delen: dict[str, frozenset[str]] = field(default_factory=dict)

    @classmethod
    def scan(cls, pad: Path, ontologie: Ontologie) -> Export:
        """Leest de export met een gerichte regelscan.

        Een knoop is een object met een orientatie van het type `Knooppunt`, een
        verbinding een object met een orientatie van het type `Verbinding` -- exact
        de definitie die `dataset._read_nodes` en `_read_conduits` hanteren.
        """
        rauwe_types: dict[str, set[str]] = defaultdict(set)
        aspecten: dict[str, set[str]] = defaultdict(set)
        delen: dict[str, set[str]] = defaultdict(set)
        subject = ""
        with pad.open(encoding="utf-8", errors="replace") as bestand:
            for regel in bestand:
                if not regel.strip():
                    continue
                if regel[0] in " \t":
                    if (treffer := _TYPE.match(regel)) is not None:
                        rauwe_types[subject].add(treffer.group(1))
                    elif (treffer := _ASPECT.match(regel)) is not None:
                        aspecten[subject].add(treffer.group(1))
                    elif (treffer := _DEEL.match(regel)) is not None:
                        delen[subject].add(treffer.group(1))
                elif regel[0] not in "#@" and (treffer := _SUBJECT.match(regel)) is not None:
                    subject = treffer.group(1)

        types = {uri: frozenset(namen) for uri, namen in rauwe_types.items()}
        knooppunt = ontologie.afsluiting(["Knooppunt"])
        verbinding = ontologie.afsluiting(["Verbinding"])
        knopen: dict[str, str] = {}
        verbindingen: set[str] = set()
        for uri, eigen in aspecten.items():
            for aspect in sorted(eigen):
                soorten = types.get(aspect, frozenset())
                if uri not in knopen and soorten & knooppunt:
                    knopen[uri] = aspect
                if soorten & verbinding:
                    verbindingen.add(uri)
        return cls(
            ontologie=ontologie,
            types=types,
            knopen=knopen,
            verbindingen=verbindingen,
            delen={uri: frozenset(leden) for uri, leden in delen.items()},
        )

    def knooptypen(self, uri: str) -> frozenset[str]:
        """De typen van een knoop plus die van zijn orientatie, als `types_of()`."""
        return self.types.get(uri, frozenset()) | self.types.get(self.knopen[uri], frozenset())

    def knopen_van(self, wortels: Iterable[str]) -> set[str]:
        """De knopen die onder een van deze wortelklassen vallen."""
        gesloten = self.ontologie.afsluiting(wortels)
        return {uri for uri in self.knopen if self.knooptypen(uri) & gesloten}

    def verbindingen_van(self, wortels: Iterable[str]) -> set[str]:
        """De verbindingen die onder een van deze wortelklassen vallen.

        Een verbinding draagt haar klasse op het object zelf; `_stelseltype` en de
        overige verbindingsselecties lezen dan ook `conduit.types` en niet de
        orientatie.
        """
        gesloten = self.ontologie.afsluiting(wortels)
        return {uri for uri in self.verbindingen if self.types.get(uri, frozenset()) & gesloten}

    def instanties(self, wortels: Iterable[str]) -> set[str]:
        """Alle objecten van deze klassen, ook die geen knoop of verbinding zijn."""
        gesloten = self.ontologie.afsluiting(wortels)
        return {uri for uri, soorten in self.types.items() if soorten & gesloten}


def _telling(export: Export, uris: Iterable[str]) -> list[tuple[str, int]]:
    """Hoe vaak elke klasse in deze verzameling objecten voorkomt."""
    teller: Counter[str] = Counter()
    for uri in uris:
        for naam in export.types.get(uri, frozenset()):
            teller[naam] += 1
    return sorted(teller.items(), key=lambda paar: (-paar[1], paar[0]))


def _kop(tekst: str) -> None:
    """Zet een kop boven een blok."""
    print(f"\n{tekst}\n{'-' * len(tekst)}")


def _klasseregel(export: Export, klasse: str) -> str:
    """Een regel met bestaan, instanties en rol voor een enkele klasse."""
    bestaat = export.ontologie.bestaat(klasse)
    kinderen = sorted(export.ontologie.afsluiting([klasse]) - {klasse})
    return (
        f"  {klasse:<34} bestaat={str(bestaat).lower():<5} "
        f"instanties={len(export.instanties([klasse])):>6} "
        f"knopen={len(export.knopen_van([klasse])):>6} "
        f"verbindingen={len(export.verbindingen_van([klasse])):>6} "
        f"subklassen={len(kinderen)}"
    )


def _verschil(
    naam: str, oud: set[str], nieuw: set[str], export: Export, eenheid: str = "objecten"
) -> None:
    """Drukt af hoeveel objecten een lijstwijziging erbij of eraf haalt."""
    erbij = nieuw - oud
    eraf = oud - nieuw
    print(f"  {naam}: nu {len(oud)} {eenheid}, na de ingreep {len(nieuw)}.")
    print(f"    erbij: {len(erbij)}   eraf: {len(eraf)}")
    for lijst, label in ((erbij, "erbij"), (eraf, "eraf")):
        if lijst:
            print(f"    {label} per klasse: {_telling(export, lijst)}")


def _punt1(export: Export, klassen: dict[str, object]) -> None:
    """Punt 1: `mechanisch` van drie bladen naar de twee ontologische wortels."""
    _kop("PUNT 1 -- klassen.mechanisch: drie bladen -> twee wortels")
    oud_wortels = _lijst(klassen, "mechanisch")
    nieuw_wortels = ["MechanischeRioolleiding", "MechanischeTransportleiding"]
    print(f"  huidig  : {oud_wortels}")
    print(f"  voorstel: {nieuw_wortels}")
    print(f"  afsluiting van het voorstel: {sorted(export.ontologie.afsluiting(nieuw_wortels))}")
    for klasse in ("Luchtpersleiding", "Leidingsegment", "Spoelleiding"):
        print(_klasseregel(export, klasse))
    _verschil(
        "mechanische verbindingen",
        export.verbindingen_van(oud_wortels),
        export.verbindingen_van(nieuw_wortels),
        export,
    )
    overlap = export.ontologie.afsluiting(nieuw_wortels) & export.ontologie.afsluiting(
        ["VrijvervalRioolleiding"]
    )
    print(f"  overlap voorstel x VrijvervalRioolleiding-afsluiting: {sorted(overlap) or 'geen'}")
    vrijverval = export.verbindingen_van(["VrijvervalRioolleiding"])
    verschuift = export.verbindingen_van(nieuw_wortels) - export.verbindingen_van(oud_wortels)
    print(f"  daarvan nu ook vrijverval (dus checkgedrag): {len(verschuift & vrijverval)}")


def _punt2(export: Export, klassen: dict[str, object]) -> None:
    """Punt 2: `afvoer_eindpunt` mist RWZI en twee knooppuntklassen."""
    _kop("PUNT 2 -- klassen.afvoer_eindpunt: RWZI, Afleveringspunt, AfvoerpuntGebied")
    oud = _lijst(klassen, "afvoer_eindpunt")
    extra = ["RWZI", "Afleveringspunt", "AfvoerpuntGebied"]
    for klasse in (*oud, *extra, "Overnamepunt"):
        print(_klasseregel(export, klasse))
    _verschil(
        "afvoereindpunten",
        export.knopen_van(oud),
        export.knopen_van([*oud, *extra]),
        export,
        "knopen",
    )


def _punt3(export: Export, klassen: dict[str, object]) -> None:
    """Punt 3: zes vrijvervalklassen zonder stelseltype."""
    _kop("PUNT 3 -- klassen.stelseltypen: zes VrijvervalRioolleiding-subklassen ontbreken")
    gedekt = set(_stelselwortels(klassen))
    print(f"  [klassen.stelseltypen] noemt nu: {sorted(gedekt)}")
    kinderen = sorted(export.ontologie.kinderen.get("VrijvervalRioolleiding", ()))
    print(f"  VrijvervalRioolleiding heeft {len(kinderen)} directe subklassen: {kinderen}")
    ontbreekt = [naam for naam in kinderen if naam not in gedekt]
    print(f"  niet in [klassen.stelseltypen]: {ontbreekt}")
    for klasse in ontbreekt:
        print(_klasseregel(export, klasse))
    totaal = export.verbindingen_van(ontbreekt)
    print(f"  verbindingen die een stelseltype zouden krijgen: {len(totaal)}")
    zonder = export.verbindingen_van(["VrijvervalRioolleiding"]) - export.verbindingen_van(
        sorted(gedekt)
    )
    print(f"  vrijvervalverbindingen die nu geen stelseltype krijgen: {len(zonder)}")
    if zonder:
        print(f"    per klasse: {_telling(export, zonder)}")


def _punt4(export: Export, klassen: dict[str, object]) -> None:
    """Punt 4: `transport` staat op de verkeerde tak, en Zinker mist een stelseltype."""
    _kop("PUNT 4 -- klassen.stelseltypen.transport staat op de verkeerde tak")
    for klasse in (
        "Duiker",
        "VrijvervalTransportleiding",
        "Transportrioolleiding",
        "VrijvervalLeidingsegment",
        "Zinker",
    ):
        print(_klasseregel(export, klasse))
    print(f"  ouders van Duiker: {sorted(export.ontologie.ouders.get('Duiker', ()))}")
    print(f"  voorouders van Duiker: {sorted(export.ontologie.voorouders('Duiker'))}")
    huidig = _lijst(_stelseltabel(klassen), "transport")
    print(f"  huidig [klassen.stelseltypen] transport: {huidig}")
    _verschil(
        "verbindingen met stelseltype transport",
        export.verbindingen_van(huidig),
        export.verbindingen_van([*huidig, "VrijvervalTransportleiding"]),
        export,
        "verbindingen",
    )
    zinkers = len(export.verbindingen_van(["Zinker"]))
    print(f"  Zinker als extra stelseltype: {zinkers} verbindingen")


def _punt5(export: Export) -> None:
    """Punt 5: de ontologie kent wel degelijk IT-begrippen."""
    _kop("PUNT 5 -- 'de ontologie kent geen klasse IT-stelsel'")
    for klasse in ("DIT_riool", "DT_riool", "DrainageInfiltratieTransportStelsel"):
        print(_klasseregel(export, klasse))
    print(_klasseregel(export, "Infiltratiestelsel"))
    stelsels = export.instanties(["Infiltratiestelsel"])
    leden: set[str] = set()
    for uri in stelsels:
        leden |= export.delen.get(uri, frozenset())
    infiltratieriolen = export.verbindingen_van(["Infiltratieriool"])
    print(f"  Infiltratiestelsel-objecten in de export: {len(stelsels)}")
    print(f"    hun hasPart-leden: {len(leden)} -> {_telling(export, leden)}")
    print(f"  Infiltratieriool-verbindingen totaal: {len(infiltratieriolen)}")
    print(f"    daarvan lid van een Infiltratiestelsel: {len(infiltratieriolen & leden)}")
    stelselklassen = _telling(export, export.instanties(["Rioolstelsel"]))
    print(f"  alle Rioolstelsel-instanties per klasse: {stelselklassen}")


def _punt6(export: Export, klassen: dict[str, object]) -> None:
    """Punt 6: bergbezinkvoorzieningen dekken 3 van de 22 Reservoir-subklassen."""
    _kop("PUNT 6 -- klassen.bergbezinkvoorziening: 3 van de Reservoir-subklassen")
    afsluiting = sorted(export.ontologie.afsluiting(["Reservoir"]))
    huidig = _lijst(klassen, "bergbezinkvoorziening")
    print(f"  Reservoir-afsluiting telt {len(afsluiting)} klassen (inclusief Reservoir zelf).")
    print(f"  huidig: {huidig}")
    ontbreekt = [naam for naam in afsluiting if naam not in huidig]
    print(f"  niet gedekt ({len(ontbreekt)}): {ontbreekt}")
    met_instanties = [naam for naam in afsluiting if export.instanties([naam])]
    print(f"  Reservoir-klassen met instanties in De Wolden: {met_instanties or 'geen'}")
    _verschil(
        "bergbezinkvoorzieningen",
        export.knopen_van(huidig),
        export.knopen_van(afsluiting),
        export,
        "knopen",
    )


def _punt7(export: Export, klassen: dict[str, object]) -> None:
    """Punt 7: de kleinere gaten in lozingseindpunt, valconstructie en functieloze knoop."""
    _kop("PUNT 7a -- klassen.lozings_eindpunt")
    huidig = _lijst(klassen, "lozings_eindpunt")
    extra = ["Uitstroombak", "InlaatOppervlaktewater", "Ontlastput", "Beekriool", "Overkluizing"]
    for klasse in (*huidig, *extra):
        print(_klasseregel(export, klasse))
    print(
        f"  Beekriool zit al in de afsluiting van Overkluizing: "
        f"{'Beekriool' in export.ontologie.afsluiting(['Overkluizing'])}"
    )
    _verschil(
        "lozingseindpunten",
        export.knopen_van(huidig),
        export.knopen_van([*huidig, *extra]),
        export,
        "knopen",
    )

    _kop("PUNT 7b -- klassen.valconstructie")
    huidig = _lijst(klassen, "valconstructie")
    extra = ["Wervelput", "Werveloverstortput", "VerdieptePut", "Ontlastput"]
    for klasse in (*huidig, *extra):
        print(_klasseregel(export, klasse))
    _verschil(
        "valconstructies",
        export.knopen_van(huidig),
        export.knopen_van([*huidig, *extra]),
        export,
        "knopen",
    )

    _kop("PUNT 7c -- klassen.functieloze_knoop")
    huidig = _lijst(klassen, "functieloze_knoop")
    extra = [
        "Mof",
        "Overgangsstuk",
        "Verloopstuk",
        "Bochtstuk",
        "Pendelstuk",
        "Zadel",
        "Putbuis",
        "VolgeschuimdePut",
    ]
    gesloten = export.ontologie.afsluiting(huidig)
    print(f"  huidige afsluiting ({len(gesloten)} klassen): {sorted(gesloten)}")
    for klasse in extra:
        al_gedekt = klasse in gesloten
        print(f"{_klasseregel(export, klasse)} al_gedekt={str(al_gedekt).lower()}")
    _verschil(
        "functieloze knopen",
        export.knopen_van(huidig),
        export.knopen_van([*huidig, *extra]),
        export,
        "knopen",
    )

    _kop("PUNT 7d -- symbolentabel: de wortelklassen hebben geen symbool")
    print("  Telling op de exacte klassenaam: de symbolentabel doet geen subklasse-afsluiting.")
    for klasse in ("Rioolput", "Rioolleiding", "VrijvervalRioolleiding", "Aansluitleiding"):
        exact = sum(1 for soorten in export.types.values() if klasse in soorten)
        print(
            f"  {klasse:<34} bestaat={str(export.ontologie.bestaat(klasse)).lower():<5} "
            f"exacte instanties={exact}"
        )


def _uitlaat(export: Export) -> None:
    """De losse bevinding uit het comment: `Uitlaat` kan nooit een treffer geven."""
    _kop("BEVINDING -- 'Uitlaat' in klassen.lozings_eindpunt is een stille nul")
    print(f"  ouders van Uitlaat    : {sorted(export.ontologie.ouders.get('Uitlaat', ()))}")
    print(f"  voorouders van Uitlaat: {sorted(export.ontologie.voorouders('Uitlaat'))}")
    knooppunt = export.ontologie.afsluiting(["Knooppunt"])
    fysiek = export.ontologie.afsluiting(["FysiekObject"])
    print(f"  Uitlaat in de Knooppunt-afsluiting   : {'Uitlaat' in knooppunt}")
    print(f"  Uitlaat in de FysiekObject-afsluiting: {'Uitlaat' in fysiek}")
    print(_klasseregel(export, "Uitlaat"))


def _toets_regelvorm(pad: Path) -> None:
    """Toetst dat de export de vlakke schrijfwijze aanhoudt die de scan aanneemt.

    De regelscan is alleen juist voor Turtle waarin elk subject op een eigen regel
    staat en elk predicaat ingesprongen. Zodra een export de verkorte notatie met
    blanke knopen gebruikt (`gwsw:hasAspect [ rdf:type gwsw:Punt ; ... ]`) hoort een
    binnenste `rdf:type` bij de blanke knoop en niet bij het subject erboven, en zou
    de scan die stilzwijgend aan het verkeerde object toekennen. Het handgeschreven
    voorbeeldbestand doet dat wel; de BrutIS-export van De Wolden nergens. Deze
    toets breekt af in plaats van een fout getal op te schrijven.
    """
    verboden = ("[", "]", "_:")
    for nummer, regel in enumerate(pad.open(encoding="utf-8", errors="replace"), start=1):
        if not regel.strip():
            continue
        if any(teken in regel for teken in verboden):
            sys.exit(f"{pad}:{nummer}: verkorte Turtle-notatie; de regelscan is hier niet geldig.")
        if regel[0] in "#@":
            continue
        if regel[0] in " \t":
            if len(regel.split(None, 2)) < 2:
                sys.exit(f"{pad}:{nummer}: ingesprongen regel zonder predicaat en object.")
        elif _SUBJECT.match(regel) is None:
            sys.exit(f"{pad}:{nummer}: subjectregel met meer dan een term.")


def _uittreksel(pad: Path, vensters: Sequence[tuple[int, int]]) -> Path:
    """Schrijft een aantal vensters uit een export naar een tijdelijk bestand.

    Een venster begint bij de eerste subjectregel op of na zijn startregel en loopt
    door tot de eerste subjectregel na zijn lengte. In deze schrijfwijze eindigt het
    statement voor een subjectregel altijd op een punt, dus het uittreksel is geldig
    Turtle. Er zijn twee vensters nodig omdat de export eerst alle putten en pas
    daarna alle leidingen schrijft; met een enkel venster vooraan zou de controle
    nul verbindingen vergelijken.

    Een venster kan een object bevatten waarvan het `rdf:type` buiten het venster
    valt. Dat is geen bezwaar: de pakketlader en de regelscan lezen hetzelfde
    uittreksel en lopen dus tegen precies dezelfde afkapping aan.
    """
    doel = Path(tempfile.mkdtemp(prefix="issue32-")) / f"uittreksel_{pad.name}"
    grenzen = sorted(vensters)
    with pad.open(encoding="utf-8", errors="replace") as bron, doel.open("w") as uit:
        actief: tuple[int, int] | None = None
        for nummer, regel in enumerate(bron, start=1):
            subjectregel = bool(regel.strip()) and regel[0] not in " \t#@"
            if regel.startswith("@"):
                uit.write(regel)
                continue
            if actief is not None and nummer > actief[0] + actief[1] and subjectregel:
                actief = None
            if actief is None and grenzen and subjectregel and nummer >= grenzen[0][0]:
                actief = grenzen.pop(0)
            if actief is not None:
                uit.write(regel)
    return doel


def _controleer_parser(ontologie: Ontologie, vensters: Sequence[tuple[int, int]]) -> None:
    """Toetst de regelscan tegen `load_dataset` op een uittreksel van de gemeten export.

    Zonder deze controle steunt elk getal hierna op een handgeschreven parser. De
    hele export door rdflib halen kost ruim drie minuten en circa 3 GB; een
    uittreksel van dezelfde export is dezelfde schrijfwijze, dezelfde klassen en
    dezelfde structuur, en gaat er in seconden doorheen. Vergeleken worden het
    aantal knopen, het aantal verbindingen en beide klassentellingen -- precies de
    grootheden waar de meting op steunt.
    """
    _kop("CONTROLE -- regelscan tegen nlriochecker.dataset.load_dataset")
    from nlriochecker.dataset import load_dataset

    pad = _uittreksel(EXPORT, vensters)
    print(f"  uittreksel van {EXPORT.name}, vensters (startregel, lengte): {list(vensters)}")
    geladen = load_dataset(pad, [ONTOLOGIE])
    gescand = Export.scan(pad, ontologie)

    lader_knopen: Counter[str] = Counter()
    for knoop in geladen.nodes.values():
        for soort in knoop.types | knoop.orientation_types:
            lader_knopen[_kort(soort)] += 1
    lader_verbindingen: Counter[str] = Counter()
    for verbinding in geladen.conduits.values():
        for soort in verbinding.types:
            lader_verbindingen[_kort(soort)] += 1
    verwacht = (
        len(geladen.nodes),
        len(geladen.conduits),
        sorted(lader_knopen.items()),
        sorted(lader_verbindingen.items()),
    )

    scan_knopen: Counter[str] = Counter()
    for uri in gescand.knopen:
        for soort in gescand.knooptypen(uri):
            scan_knopen[soort] += 1
    scan_verbindingen: Counter[str] = Counter()
    for uri in gescand.verbindingen:
        for soort in gescand.types.get(uri, frozenset()):
            scan_verbindingen[soort] += 1
    eigen = (
        len(gescand.knopen),
        len(gescand.verbindingen),
        sorted(scan_knopen.items()),
        sorted(scan_verbindingen.items()),
    )

    print(f"  lader : {verwacht[0]} knopen, {verwacht[1]} verbindingen")
    print(f"  scan  : {eigen[0]} knopen, {eigen[1]} verbindingen")
    if eigen == verwacht:
        print(
            f"  GELIJK -- ook beide klassentellingen ({len(scan_knopen)} knoopklassen, "
            f"{len(scan_verbindingen)} verbindingklassen) komen overeen."
        )
        return
    print("  VERSCHIL -- de regelscan wijkt af van de pakketlader:")
    for label, links, rechts in zip(
        ("knopen", "verbindingen", "knoopklassen", "verbindingklassen"),
        eigen,
        verwacht,
        strict=True,
    ):
        if links != rechts:
            print(f"    {label}: scan={links} lader={rechts}")
    sys.exit(1)


def main() -> None:
    """Draait de hele meting en drukt het verslag af."""
    print(f"Ontologie : {ONTOLOGIE.relative_to(WORTEL)}")
    print(f"Export    : {EXPORT.relative_to(WORTEL)}")
    print(f"Config    : {' + '.join(str(pad.relative_to(WORTEL)) for pad in CONFIGS)}")
    klassen = _huidige_klassen()
    print(f"  [klassen] is in beide bestanden gelijk; {len(klassen)} sleutels gelezen.")
    ontologie = Ontologie.laad(ONTOLOGIE)
    _toets_regelvorm(EXPORT)
    print(f"  regelvorm van {EXPORT.name}: vlak, geen verkorte notatie -- scan is geldig.")
    _controleer_parser(ontologie, CONTROLEVENSTERS)

    export = Export.scan(EXPORT, ontologie)
    _kop("OMVANG van de export")
    print(f"  getypeerde objecten: {len(export.types)}")
    print(f"  knopen             : {len(export.knopen)}")
    print(f"  verbindingen       : {len(export.verbindingen)}")
    print(f"  knoopklassen       : {_telling(export, export.knopen)}")
    print(f"  verbindingklassen  : {_telling(export, export.verbindingen)}")

    _punt1(export, klassen)
    _punt2(export, klassen)
    _punt3(export, klassen)
    _punt4(export, klassen)
    _punt5(export)
    _punt6(export, klassen)
    _punt7(export, klassen)
    _uitlaat(export)


if __name__ == "__main__":
    main()
