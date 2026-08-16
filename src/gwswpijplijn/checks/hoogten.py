"""HGT-checks: waardelogica op BOB's, deksel- en drempelniveaus en verhang.

Dat de hoogtekenmerken *bestaan* dwingen de conformiteitsklassen af (Hyd de BOB's,
Mds maaiveldhoogte, putdekselniveau en drempelniveau). Deze categorie toetst
uitsluitend of de waarden onderling kloppen. HGT-001 t/m HGT-003 vergelijken met
het AHN en staan in `extern.py`, want die hebben een externe bron nodig.

Ontbreekt een kenmerk in de dataset, dan meldt de check dat in haar toelichting.
Nul bevindingen omdat het kenmerk er niet is, is iets anders dan nul bevindingen
omdat alles klopt.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from gwswpijplijn.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from gwswpijplijn.checks.verbanden import aansluitingen, objecten_van_klassen, verbonden_knopen
from gwswpijplijn.dataset import Conduit, Node


@dataclass(frozen=True)
class _Uiteinde:
    """Een strengeinde met de put en de BOB die erbij horen."""

    conduit: Conduit
    node: Node
    bob: float | None
    zijde: str
    stroomafwaarts: bool


def _vrijverval(context: CheckContext) -> list[Conduit]:
    """De vrijvervalstrengen waarop de HGT-checks draaien."""
    return context.cached(
        "hgt:strengen",
        lambda: objecten_van_klassen(context, context.config.klassen.vrijvervalleiding, "conduits"),
    )


def _putten(context: CheckContext) -> list[Node]:
    """De putten van het netwerk."""
    return context.cached(
        "hgt:putten",
        lambda: objecten_van_klassen(context, context.config.klassen.netwerkknopen, "nodes"),
    )


def _uiteinden(context: CheckContext) -> list[_Uiteinde]:
    """Elk strengeinde met zijn put en BOB, een keer per context opgebouwd."""
    return context.cached("hgt:uiteinden", lambda: _bouw_uiteinden(context))


def _bouw_uiteinden(context: CheckContext) -> list[_Uiteinde]:
    """Loopt de strengen langs en koppelt elk uiteinde aan zijn put."""
    dataset = context.dataset
    gevonden: list[_Uiteinde] = []
    for conduit in _vrijverval(context):
        begin, eind = verbonden_knopen(context, conduit)
        for uri, bob, zijde, afwaarts in (
            (begin, conduit.bob_start, "beginpunt", False),
            (eind, conduit.bob_end, "eindpunt", True),
        ):
            node = dataset.nodes.get(uri) if uri else None
            if node is not None:
                gevonden.append(_Uiteinde(conduit, node, bob, zijde, afwaarts))
    return gevonden


def _ontbreekt(
    context: CheckContext,
    kenmerk: str,
    kies,
    objecten: list | None = None,
    soort: str = "putten",
) -> list[str]:
    """Een toelichting als een hoogtekenmerk in deze dataset nauwelijks voorkomt.

    De telling gaat over de objecten die de check zelf bekijkt; een strengcheck die
    over putten telt zou een getal noemen dat niet bij haar eenheid past.
    """
    objecten = _putten(context) if objecten is None else objecten
    if not objecten:
        return []
    zonder = sum(1 for object_ in objecten if kies(object_) is None)
    if not zonder:
        return []
    if zonder == len(objecten):
        return [
            f"Geen enkele van de {len(objecten)} {soort} in {context.scope_in_woorden()} "
            f"heeft een {kenmerk}. Deze check heeft daardoor niets kunnen toetsen; nul "
            "bevindingen betekent hier niet dat het in orde is."
        ]
    return [f"{zonder} van de {len(objecten)} {soort} hebben geen {kenmerk} en zijn overgeslagen."]


def _bovenkant_bron(node: Node) -> str:
    """Waar het bovenkantniveau vandaan komt: dekselniveau of maaiveld."""
    return "dekselniveau" if node.dekselniveau is not None else "maaiveldhoogte"


def _verhang(conduit: Conduit) -> float | None:
    """Het verval per meter in de administratieve richting; positief is afwaarts."""
    if conduit.bob_start is None or conduit.bob_end is None:
        return None
    lengte = conduit.lengte_m
    if lengte is None and conduit.line is not None and not conduit.line.is_empty:
        lengte = float(conduit.line.length)
    if not lengte or lengte <= 0:
        return None
    return (conduit.bob_start - conduit.bob_end) / lengte


class _StrengCheck(Check):
    """Basis voor de HGT-checks die per vrijvervalstreng redeneren."""

    def examined(self, context: CheckContext) -> int:
        """Het aantal vrijvervalstrengen."""
        return len(_vrijverval(context))


class _PutCheck(Check):
    """Basis voor de HGT-checks die per put redeneren."""

    def examined(self, context: CheckContext) -> int:
        """Het aantal putten."""
        return len(_putten(context))


@register
class BobBuitenDePut(_StrengCheck):
    """HGT-004: een BOB boven het deksel of onder de bodem van de eigen put."""

    id = "HGT-004"
    title = "BOB hoger dan dekselhoogte van de eigen put, of lager dan de putbodem"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst elke BOB tegen het bovenkant- en bodemniveau van zijn put."""
        for uiteinde in _uiteinden(context):
            if uiteinde.bob is None:
                continue
            node = uiteinde.node
            boven = node.bovenkant
            if boven is not None and uiteinde.bob > boven:
                yield self.finding(
                    context,
                    uiteinde.conduit.uri,
                    uiteinde.conduit.label,
                    f"De BOB aan het {uiteinde.zijde} ({uiteinde.bob:.3f} m NAP) ligt boven "
                    f"het {_bovenkant_bron(node)} van put {node.label!r} ({boven:.3f} m NAP).",
                    zijde=uiteinde.zijde,
                    bob=uiteinde.bob,
                    bovenkant=boven,
                    bron=_bovenkant_bron(node),
                    put=node.label,
                )
            bodem = node.bodem
            if bodem is not None and uiteinde.bob < bodem:
                yield self.finding(
                    context,
                    uiteinde.conduit.uri,
                    uiteinde.conduit.label,
                    f"De BOB aan het {uiteinde.zijde} ({uiteinde.bob:.3f} m NAP) ligt onder "
                    f"de bodem van put {node.label!r} ({bodem:.3f} m NAP).",
                    zijde=uiteinde.zijde,
                    bob=uiteinde.bob,
                    bodem=bodem,
                    put=node.label,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welk deel van de toets niet uitgevoerd kon worden."""
        putten = _putten(context)
        zonder_boven = sum(1 for node in putten if node.bovenkant is None)
        zonder_bodem = sum(1 for node in putten if node.bodem is None)
        notities = [
            "Het GWSW kent geen kenmerk `Putbodemniveau`; de bodem volgt uit het "
            "bovenkantniveau min `HoogtePut`. Ontbreekt een van die twee, dan blijft de "
            "bodemtoets achterwege."
        ]
        if zonder_boven:
            notities.append(
                f"{zonder_boven} van de {len(putten)} putten hebben geen putdekselniveau en "
                "geen maaiveldhoogte; daar is de bovenkant niet te toetsen."
            )
        if zonder_bodem:
            notities.append(
                f"{zonder_bodem} van de {len(putten)} putten hebben geen afleidbaar "
                "bodemniveau; daar is de bodemtoets overgeslagen."
            )
        return notities


class _Tegenverhang(_StrengCheck):
    """Gedeelde basis voor de twee tegenverhangchecks."""

    ondergrens: str
    bovengrens: str | None

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt strengen waarvan de bodem stijgt in de afvoerrichting."""
        drempels = context.config.drempels
        onder = getattr(drempels, self.ondergrens)
        boven = getattr(drempels, self.bovengrens) if self.bovengrens else None

        for conduit in _vrijverval(context):
            if conduit.bob_start is None or conduit.bob_end is None:
                continue
            stijging = conduit.bob_end - conduit.bob_start
            if stijging <= onder:
                continue
            if boven is not None and stijging > boven:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"De bodem stijgt {stijging:.3f} m in de afvoerrichting "
                f"(BOB {conduit.bob_start:.3f} naar {conduit.bob_end:.3f} m NAP).",
                stijging_m=round(stijging, 3),
                ondergrens_m=onder,
                bovengrens_m=boven,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen BOB-paar hebben en waar de overlap zit."""
        strengen = _vrijverval(context)
        zonder = sum(
            1 for conduit in strengen if conduit.bob_start is None or conduit.bob_end is None
        )
        notities = [
            "De afvoerrichting is hier de administratieve van-naar-richting. NET-003 leest "
            "hetzelfde verschijnsel als richtingsprobleem; het register kent beide."
        ]
        if zonder:
            notities.append(
                f"{zonder} van de {len(strengen)} strengen missen een BOB aan begin- of "
                "eindpunt en zijn niet getoetst."
            )
        return notities


@register
class TegenverhangLicht(_Tegenverhang):
    """HGT-005: licht tegenverhang, onder de drempel voor fors."""

    id = "HGT-005"
    title = "Tegenverhang bij vrijverval: licht (onder drempel)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY
    ondergrens = "tegenverhang_licht_m"
    bovengrens = "tegenverhang_fors_m"


@register
class TegenverhangFors(_Tegenverhang):
    """HGT-006: fors tegenverhang, boven de drempel."""

    id = "HGT-006"
    title = "Tegenverhang bij vrijverval: fors (boven drempel)"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY
    ondergrens = "tegenverhang_fors_m"
    bovengrens = None


@register
class OnvoldoendeVerhang(_StrengCheck):
    """HGT-007: te weinig verval voor zelfreiniging bij vuilwater of gemengd."""

    id = "HGT-007"
    title = "Verhang vuilwater of gemengd onder drempelwaarde"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst het verval per meter van vuilwater- en gemengde strengen.

        Alleen strengen met verval naar beneden doen mee. Loopt de bodem juist
        omhoog, dan is dat tegenverhang en melden HGT-005 en HGT-006 dat; hier nog
        eens meetellen zou dezelfde streng dubbel laten opduiken.
        """
        dataset = context.dataset
        drempel = context.config.drempels.minimaal_verhang_promille / 1000.0
        soorten = {
            uri
            for wortel in context.config.klassen.vuilwater
            for uri in dataset.of_class(wortel)
            if uri in dataset.conduits
        }

        for conduit in _vrijverval(context):
            if conduit.uri not in soorten:
                continue
            verhang = _verhang(conduit)
            if verhang is None or verhang < 0 or verhang >= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Verhang {verhang * 1000:.2f} promille, onder de drempel van "
                f"{drempel * 1000:g} promille voor vuilwater en gemengd.",
                verhang_promille=round(verhang * 1000, 3),
                drempel_promille=drempel * 1000,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Legt de afbakening vast."""
        return [
            "Alleen strengen met verval naar beneden zijn getoetst; tegenverhang meldt de "
            "check niet, dat doen HGT-005 en HGT-006."
        ]


@register
class ExtreemVerhang(_StrengCheck):
    """HGT-008: een verval dat te steil is om te kloppen."""

    id = "HGT-008"
    title = "Extreem verhang (steiler dan bijv. 1:50), indicatie verwisselde BOB's"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt strengen die steiler dalen dan een op zoveel."""
        een_op = context.config.drempels.extreem_verhang_een_op
        drempel = 1.0 / een_op

        for conduit in _vrijverval(context):
            verhang = _verhang(conduit)
            if verhang is None or verhang <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Verhang 1:{1 / verhang:.0f}, steiler dan 1:{een_op:g}; mogelijk zijn de "
                "BOB's verwisseld.",
                verhang=round(verhang, 5),
                een_op=een_op,
            )


class _KnoopVergelijking(_PutCheck):
    """Basis voor de checks die boven- en benedenstroomse strengen op een put vergelijken."""

    def paren(self, context: CheckContext):
        """Levert per put de aanvoerende en afvoerende strengen op.

        Aanvoerend is een streng die met haar eindpunt op deze put uitkomt,
        afvoerend een streng die er met haar beginpunt begint. De richting is de
        administratieve van-naar-richting.
        """
        index = aansluitingen(context, "vrijvervalleiding")
        dataset = context.dataset
        for knoop_uri, strengen in index.per_knoop.items():
            node = dataset.nodes.get(knoop_uri)
            if node is None:
                continue
            aanvoer = [c for c in strengen if index.knopen(c.uri)[1] == knoop_uri]
            afvoer = [c for c in strengen if index.knopen(c.uri)[0] == knoop_uri]
            if aanvoer and afvoer:
                yield node, aanvoer, afvoer


@register
class BobSprongZonderValput(_KnoopVergelijking):
    """HGT-009: een hoogtesprong tussen aansluitende strengen zonder valconstructie."""

    id = "HGT-009"
    title = "BOB-sprong tussen aansluitende strengen boven drempel zonder valput"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de BOB van aanvoer en afvoer op elke put."""
        drempel = context.config.drempels.bob_sprong_m
        valconstructies = _valconstructies(context)

        for node, aanvoer, afvoer in self.paren(context):
            if node.uri in valconstructies:
                continue
            binnen = [c.bob_end for c in aanvoer if c.bob_end is not None]
            uit = [c.bob_start for c in afvoer if c.bob_start is not None]
            if not binnen or not uit:
                continue
            sprong = min(binnen) - max(uit)
            if sprong <= drempel:
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"De aanvoerende BOB ligt {sprong:.3f} m boven de afvoerende, zonder "
                f"geregistreerde valconstructie (drempel {drempel:g} m).",
                sprong_m=round(sprong, 3),
                drempel_m=drempel,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt welke klassen als valconstructie gelden."""
        klassen = context.config.klassen.valconstructie
        if not klassen:
            return [
                "Er zijn geen valconstructieklassen geconfigureerd "
                "(`klassen.valconstructie`); elke sprong telt daardoor mee."
            ]
        return [f"Als valconstructie gelden: {', '.join(klassen)}."]


@register
class DiameterverjongingInAfvoerrichting(_KnoopVergelijking):
    """HGT-010: benedenstrooms een kleinere buis dan bovenstrooms."""

    id = "HGT-010"
    title = "Diameterverjonging in afvoerrichting (benedenstrooms kleiner dan bovenstrooms)"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de grootste aanvoerdiameter met de grootste afvoerdiameter."""
        for node, aanvoer, afvoer in self.paren(context):
            binnen = [_maat(c) for c in aanvoer if _maat(c) is not None]
            uit = [_maat(c) for c in afvoer if _maat(c) is not None]
            if not binnen or not uit:
                continue
            if max(uit) >= max(binnen):
                continue
            afvoerend = max(afvoer, key=lambda c: _maat(c) or 0)
            yield self.finding(
                context,
                afvoerend.uri,
                afvoerend.label,
                f"Voert af uit put {node.label!r} met {max(uit):g} mm terwijl er "
                f"{max(binnen):g} mm binnenkomt.",
                afvoer_mm=max(uit),
                aanvoer_mm=max(binnen),
                put=node.label,
            )


@register
class DrempelBuitenBereik(_PutCheck):
    """HGT-011: een overstortdrempel onder de aanvoerende BOB of boven maaiveld."""

    id = "HGT-011"
    title = "Overstortdrempel lager dan BOB aanvoerende streng of hoger dan maaiveld"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst elk drempelniveau tegen de aanvoerende BOB en het maaiveld."""
        from gwswpijplijn.checks.randvoorzieningen import drempels_per_put

        index = aansluitingen(context, "vrijvervalleiding")
        for knoop_uri, groep in drempels_per_put(context).items():
            node = context.dataset.nodes.get(knoop_uri)
            if node is None:
                continue
            aanvoer = [
                conduit.bob_end
                for conduit in index.strengen(knoop_uri)
                if index.knopen(conduit.uri)[1] == knoop_uri and conduit.bob_end is not None
            ]
            for drempel in groep:
                niveau = drempel.niveau
                if niveau is None:
                    continue
                if aanvoer and niveau < min(aanvoer):
                    yield self.finding(
                        context,
                        node.uri,
                        node.label,
                        f"Drempelniveau van {drempel.label!r} ({niveau:.3f} m NAP) ligt onder "
                        f"de laagste aanvoerende BOB ({min(aanvoer):.3f} m NAP).",
                        drempel=drempel.label,
                        drempelniveau=niveau,
                        laagste_bob=min(aanvoer),
                    )
                boven = node.bovenkant
                if boven is not None and niveau > boven:
                    yield self.finding(
                        context,
                        node.uri,
                        node.label,
                        f"Drempelniveau van {drempel.label!r} ({niveau:.3f} m NAP) ligt boven "
                        f"het {_bovenkant_bron(node)} ({boven:.3f} m NAP).",
                        drempel=drempel.label,
                        drempelniveau=niveau,
                        bovenkant=boven,
                    )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt of er uberhaupt drempelniveaus in de dataset staan."""
        from gwswpijplijn.checks.randvoorzieningen import drempelnotitie

        return drempelnotitie(context)


@register
class PutdiepteBuitenBereik(_PutCheck):
    """HGT-012: een putdiepte die negatief of onwaarschijnlijk groot is."""

    id = "HGT-012"
    title = "Putdiepte (deksel minus bodem) negatief of groter dan X m"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst `HoogtePut` op een aannemelijk bereik.

        Het GWSW kent geen bodemniveau; de putdiepte staat als `HoogtePut` in
        millimeters geregistreerd. Deksel min bodem zou hier hetzelfde getal
        opleveren, want de bodem wordt juist uit die twee afgeleid.
        """
        maximum = context.config.drempels.maximale_putdiepte_m

        for node in _putten(context):
            diepte = node.hoogte_m
            if diepte is None:
                continue
            if 0 < diepte <= maximum:
                continue
            kant = "negatief of nul" if diepte <= 0 else f"groter dan {maximum:g} m"
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"Putdiepte {diepte:.3f} m is {kant}.",
                putdiepte_m=round(diepte, 3),
                maximum_m=maximum,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten geen hoogte hebben."""
        return _ontbreekt(context, "puthoogte (`HoogtePut`)", lambda node: node.number("HoogtePut"))


@register
class GronddekkingBuitenBereik(_StrengCheck):
    """HGT-013: te weinig of te veel grond op de buiskruin."""

    id = "HGT-013"
    title = "Gronddekking op bovenkant buis kleiner dan 0,5 m of groter dan 4 m"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Berekent per strengeinde de dekking tussen maaiveld en buiskruin."""
        drempels = context.config.drempels
        minimum = drempels.minimale_gronddekking_m
        maximum = drempels.maximale_gronddekking_m

        for uiteinde in _uiteinden(context):
            hoogte = uiteinde.conduit.hoogte_mm or uiteinde.conduit.breedte_mm
            maaiveld = uiteinde.node.maaiveld
            if uiteinde.bob is None or hoogte is None or maaiveld is None:
                continue
            kruin = uiteinde.bob + hoogte / 1000
            dekking = maaiveld - kruin
            if minimum <= dekking <= maximum:
                continue
            kant = "onder" if dekking < minimum else "boven"
            grens = minimum if dekking < minimum else maximum
            yield self.finding(
                context,
                uiteinde.conduit.uri,
                uiteinde.conduit.label,
                f"Gronddekking {dekking:.2f} m aan het {uiteinde.zijde} ligt {kant} de grens "
                f"van {grens:g} m (maaiveld {maaiveld:.2f}, buiskruin {kruin:.2f} m NAP).",
                zijde=uiteinde.zijde,
                gronddekking_m=round(dekking, 3),
                grens_m=grens,
                put=uiteinde.node.label,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengeinden niet te berekenen waren."""
        uiteinden = _uiteinden(context)
        zonder = sum(
            1
            for uiteinde in uiteinden
            if uiteinde.bob is None
            or uiteinde.node.maaiveld is None
            or (uiteinde.conduit.hoogte_mm or uiteinde.conduit.breedte_mm) is None
        )
        if not zonder:
            return []
        return [
            f"{zonder} van de {len(uiteinden)} strengeinden missen een BOB, een maaiveldhoogte "
            "of een profielmaat; daar is geen gronddekking te berekenen."
        ]


@register
class VerhangVolgtMaaiveldNiet(_StrengCheck):
    """HGT-014: het leidingverhang wijkt sterk af van het maaiveldverloop."""

    id = "HGT-014"
    title = "Leidingverhang past niet bij het maaiveldverloop tussen de putten"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt het verval van de bodem met dat van het maaiveld."""
        drempel = context.config.drempels.maaiveldvolging_afwijking_m
        dataset = context.dataset

        for conduit in _vrijverval(context):
            if conduit.bob_start is None or conduit.bob_end is None:
                continue
            begin_uri, eind_uri = verbonden_knopen(context, conduit)
            begin = dataset.nodes.get(begin_uri) if begin_uri else None
            eind = dataset.nodes.get(eind_uri) if eind_uri else None
            if begin is None or eind is None:
                continue
            if begin.maaiveld is None or eind.maaiveld is None:
                continue
            leiding = conduit.bob_start - conduit.bob_end
            maaiveld = begin.maaiveld - eind.maaiveld
            afwijking = abs(leiding - maaiveld)
            if afwijking <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Het bodemverval is {leiding:+.3f} m terwijl het maaiveld {maaiveld:+.3f} m "
                f"verloopt: {afwijking:.3f} m verschil (drempel {drempel:g} m).",
                bodemverval_m=round(leiding, 3),
                maaiveldverval_m=round(maaiveld, 3),
                afwijking_m=round(afwijking, 3),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen niet met het maaiveld te vergelijken waren."""
        dataset = context.dataset

        def maaiveldpaar(conduit: Conduit) -> float | None:
            """De maaiveldhoogten aan weerszijden, of None als er een ontbreekt."""
            begin_uri, eind_uri = verbonden_knopen(context, conduit)
            begin = dataset.nodes.get(begin_uri) if begin_uri else None
            eind = dataset.nodes.get(eind_uri) if eind_uri else None
            if begin is None or eind is None:
                return None
            if begin.maaiveld is None or eind.maaiveld is None:
                return None
            return begin.maaiveld - eind.maaiveld

        return _ontbreekt(
            context,
            "maaiveldhoogte aan beide putten",
            maaiveldpaar,
            objecten=_vrijverval(context),
            soort="strengen",
        )


@register
class PutbodemBuitenMarge(_PutCheck):
    """HGT-015: het bodemniveau past niet bij de laagste aansluitende BOB."""

    id = "HGT-015"
    title = "Putbodemniveau buiten marge ten opzichte van de laagste aansluitende BOB"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de putbodem met de laagste BOB die op de put uitkomt."""
        drempels = context.config.drempels
        boven_marge = drempels.putbodem_boven_bob_m
        zonk_marge = drempels.putbodem_zonk_m

        laagste: dict[str, float] = {}
        for uiteinde in _uiteinden(context):
            if uiteinde.bob is None:
                continue
            uri = uiteinde.node.uri
            laagste[uri] = min(laagste.get(uri, uiteinde.bob), uiteinde.bob)

        for node in _putten(context):
            bodem = node.bodem
            bob = laagste.get(node.uri)
            if bodem is None or bob is None:
                continue
            if bodem > bob + boven_marge:
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"De putbodem ({bodem:.3f} m NAP) ligt {bodem - bob:.3f} m boven de "
                    f"laagste aansluitende BOB ({bob:.3f} m NAP).",
                    bodem=bodem,
                    laagste_bob=bob,
                    marge_m=boven_marge,
                )
            elif bodem < bob - zonk_marge:
                yield self.finding(
                    context,
                    node.uri,
                    node.label,
                    f"De putbodem ({bodem:.3f} m NAP) ligt {bob - bodem:.3f} m onder de "
                    f"laagste aansluitende BOB: een zonk dieper dan {zonk_marge:g} m.",
                    bodem=bodem,
                    laagste_bob=bob,
                    marge_m=zonk_marge,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten geen afleidbaar bodemniveau hebben."""
        return _ontbreekt(context, "afleidbaar bodemniveau", lambda node: node.bodem)


@register
class BobBovenPutbodemZonderConstructie(_PutCheck):
    """HGT-016: een aansluitende BOB ver boven de putbodem zonder val of zandvang."""

    id = "HGT-016"
    title = "BOB van aansluitende streng ligt meer dan drempel boven de putbodem"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt strengen die hoog in de put binnenkomen zonder verklaring."""
        drempel = context.config.drempels.bob_sprong_m
        valconstructies = _valconstructies(context)

        for uiteinde in _uiteinden(context):
            node = uiteinde.node
            bodem = node.bodem
            if uiteinde.bob is None or bodem is None or node.uri in valconstructies:
                continue
            verschil = uiteinde.bob - bodem
            if verschil <= drempel:
                continue
            yield self.finding(
                context,
                uiteinde.conduit.uri,
                uiteinde.conduit.label,
                f"Komt {verschil:.3f} m boven de bodem van put {node.label!r} binnen zonder "
                f"geregistreerde zandvang- of valconstructie (drempel {drempel:g} m).",
                zijde=uiteinde.zijde,
                verschil_m=round(verschil, 3),
                put=node.label,
                drempel_m=drempel,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt de afhankelijkheid van het afgeleide bodemniveau."""
        return _ontbreekt(context, "afleidbaar bodemniveau", lambda node: node.bodem)


@register
class ZWaardeWijktAf(_StrengCheck):
    """HGT-017: de z-waarde uit de geometrie klopt niet met de administratie."""

    id = "HGT-017"
    title = "Z-waarde uit de geometrie wijkt af van de administratieve BOB of dekselhoogte"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de z uit de GML met de BOB's en met het dekselniveau."""
        drempel = context.config.drempels.z_afwijking_m

        for conduit in _vrijverval(context):
            for zijde, z_waarde, bob in (
                ("beginpunt", conduit.z_start, conduit.bob_start),
                ("eindpunt", conduit.z_end, conduit.bob_end),
            ):
                if z_waarde is None or bob is None or abs(z_waarde - bob) <= drempel:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"De z-waarde van het {zijde} ({z_waarde:.3f}) wijkt "
                    f"{abs(z_waarde - bob):.3f} m af van de BOB ({bob:.3f} m NAP).",
                    zijde=zijde,
                    z=z_waarde,
                    bob=bob,
                    drempel_m=drempel,
                )

        for node in _putten(context):
            niveau = node.dekselniveau
            if node.z is None or niveau is None or abs(node.z - niveau) <= drempel:
                continue
            yield self.finding(
                context,
                node.uri,
                node.label,
                f"De z-waarde van de putgeometrie ({node.z:.3f}) wijkt "
                f"{abs(node.z - niveau):.3f} m af van het putdekselniveau ({niveau:.3f} m NAP).",
                z=node.z,
                dekselniveau=niveau,
                drempel_m=drempel,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel geometrieen tweedimensionaal zijn."""
        strengen = _vrijverval(context)
        plat = sum(1 for conduit in strengen if conduit.z_start is None)
        if not plat:
            return []
        if plat == len(strengen):
            return [
                f"Geen enkele strenggeometrie in {context.scope_in_woorden()} draagt een "
                "z-waarde (srsDimension 2). Deze check heeft daardoor niets kunnen "
                "vergelijken."
            ]
        return [f"{plat} van de {len(strengen)} strengen hebben een geometrie zonder z-waarde."]

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen plus putten."""
        return len(_vrijverval(context)) + len(_putten(context))


@register
class BuiskruinBovenMaaiveld(_StrengCheck):
    """HGT-018: de bovenkant van de buis steekt boven het maaiveld uit."""

    id = "HGT-018"
    title = "Buiskruin (BOB plus diameter/hoogtemaat) boven maaiveld of dekselniveau"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Telt de profielhoogte bij de BOB op en vergelijkt met de bovenkant."""
        for uiteinde in _uiteinden(context):
            hoogte = uiteinde.conduit.hoogte_mm or uiteinde.conduit.breedte_mm
            boven = uiteinde.node.bovenkant
            if uiteinde.bob is None or hoogte is None or boven is None:
                continue
            kruin = uiteinde.bob + hoogte / 1000
            if kruin <= boven:
                continue
            yield self.finding(
                context,
                uiteinde.conduit.uri,
                uiteinde.conduit.label,
                f"De buiskruin aan het {uiteinde.zijde} ({kruin:.3f} m NAP) ligt boven het "
                f"{_bovenkant_bron(uiteinde.node)} van put {uiteinde.node.label!r} "
                f"({boven:.3f} m NAP).",
                zijde=uiteinde.zijde,
                buiskruin=round(kruin, 3),
                bovenkant=boven,
                bron=_bovenkant_bron(uiteinde.node),
                put=uiteinde.node.label,
            )


def _valconstructies(context: CheckContext) -> set[str]:
    """De knopen die als val- of zandvangconstructie geregistreerd staan."""
    dataset = context.dataset
    return {
        uri
        for wortel in context.config.klassen.valconstructie
        for uri in dataset.of_class(wortel)
        if uri in dataset.nodes
    }


def _maat(conduit: Conduit) -> float | None:
    """De grootste profielmaat van een streng in millimeters."""
    maten = [maat for maat in (conduit.breedte_mm, conduit.hoogte_mm) if maat and maat > 0]
    return max(maten) if maten else None
