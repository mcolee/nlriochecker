"""ATTR-checks: plausibiliteit van de attribuutwaarden van strengen en putten.

De plausibiliteitstabellen (materiaal versus diameter, aanlegjaar en profielvorm)
staan in `plausibiliteit.toml`; deze module bevat alleen de redenering. Een
materiaal dat niet in de tabel staat wordt niet getoetst, en elke check meldt in
haar toelichting hoeveel strengen daardoor buiten beeld bleven.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date

from rdflib import RDF, URIRef

from nlriochecker import taal
from nlriochecker.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from nlriochecker.checks.selectie import netwerkknopen, putten, vrijvervalrioolleidingen
from nlriochecker.checks.verbanden import putten_van, verbonden_knopen
from nlriochecker.dataset import GWSW, HAS_REFERENCE, HAS_VALUE, Conduit, Node
from nlriochecker.plausibiliteit import MaterialDiameter, PlausibilityTables


@dataclass(frozen=True)
class OngetoetstePopulatie:
    """Uitsplitsing van de strengen die een plausibiliteitscheck niet kon toetsen.

    Twee redenen die makkelijk op een hoop belanden maar om verschillende acties
    vragen: `zonder_attribuut` is een gat in de aanlevering (geen materiaal, geen
    vorm), `zonder_regel` een gat in `plausibiliteit.toml`.
    """

    totaal: int
    zonder_attribuut: int
    zonder_regel: int


def _ongetoetst(
    context: CheckContext,
    attribuut: Callable[[Conduit], object | None],
    regel: Callable[[Conduit], object | None],
) -> OngetoetstePopulatie:
    """Splitst de ongetoetste strengen naar de reden: attribuut ontbreekt of geen regel."""
    strengen = vrijvervalrioolleidingen(context)
    zonder_attribuut = 0
    zonder_regel = 0
    for conduit in strengen:
        if attribuut(conduit) is None:
            zonder_attribuut += 1
        elif regel(conduit) is None:
            zonder_regel += 1
    return OngetoetstePopulatie(len(strengen), zonder_attribuut, zonder_regel)


def _ongetoetst_notes(
    populatie: OngetoetstePopulatie, zonder_attribuut: str, zonder_regel: str
) -> list[str]:
    """De twee toelichtingsregels voor een ongetoetste populatie, elk alleen bij >0."""
    regels = []
    if populatie.zonder_attribuut:
        regels.append(
            f"{populatie.zonder_attribuut} van de {populatie.totaal} strengen dragen "
            f"{zonder_attribuut} en zijn niet getoetst."
        )
    if populatie.zonder_regel:
        regels.append(
            f"{populatie.zonder_regel} van de {populatie.totaal} strengen dragen "
            f"{zonder_regel} en zijn niet getoetst."
        )
    return regels


class _StrengCheck(Check):
    """Basis voor de ATTR-checks die per vrijvervalstreng redeneren."""

    def examined(self, context: CheckContext) -> int:
        """Het aantal vrijvervalstrengen."""
        return len(vrijvervalrioolleidingen(context))


@register
class DiameterPastNietBijMateriaal(_StrengCheck):
    """ATTR-001: de diameter valt buiten het bereik dat bij het materiaal hoort."""

    id = "ATTR-001"
    title = "Diameter past niet bij materiaal"
    severity = Severity.ERROR
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de grootste profielmaat met het bereik uit de tabel."""
        tabel = context.plausibiliteit

        for conduit in vrijvervalrioolleidingen(context):
            regel = tabel.diameter(conduit.materiaal)
            maat = _grootste_maat(conduit)
            if regel is None or maat is None:
                continue
            kant = _kant_van_bereik(regel, maat)
            if kant is not None:
                yield self._bevinding(context, conduit, maat, regel, kant)

    def _bevinding(self, context, conduit: Conduit, maat: float, regel, kant: str) -> Finding:
        """Bouwt de bevinding met het overschreden bereik erbij."""
        bereik = f"{regel.minimum_mm or 0:g}-{regel.maximum_mm or 0:g} mm"
        return self.finding(
            context,
            conduit.uri,
            conduit.label,
            f"Profielmaat {maat:g} mm ligt {kant} het bereik {bereik} dat bij materiaal "
            f"{conduit.materiaal} hoort. {regel.toelichting}".strip(),
            materiaal=conduit.materiaal,
            maat_mm=maat,
            minimum_mm=regel.minimum_mm,
            maximum_mm=regel.maximum_mm,
        )

    def notes(self, context: CheckContext) -> list[str]:
        """Verantwoordt de ongetoetste strengen en de diameterverdeling per materiaal.

        Drie redenen waarom een streng buiten de toets valt, elk een eigen getal:
        geen materiaal (gat in de aanlevering), een materiaal zonder diameterregel
        (gat in `plausibiliteit.toml`) en een ontbrekende profielmaat -- die laatste
        met daarbinnen de strengen die een 0 als meting registreerden. De tabel toont
        per materiaal de feitelijke min- en max-diameter, zodat een onzinnige grens in
        de tabel opvalt.
        """
        tabel = context.plausibiliteit
        strengen = vrijvervalrioolleidingen(context)
        totaal = len(strengen)
        populatie = _ongetoetst(
            context,
            lambda conduit: conduit.materiaal,
            lambda conduit: tabel.diameter(conduit.materiaal),
        )
        regels = _ongetoetst_notes(
            populatie,
            "geen materiaal",
            "een materiaal zonder diameterregel in `plausibiliteit.toml`",
        )
        zonder_maat = [conduit for conduit in strengen if _grootste_maat(conduit) is None]
        if zonder_maat:
            nul = sum(1 for conduit in zonder_maat if _registreert_nulmaat(conduit))
            staart = (
                f", waarvan {nul} met een geregistreerde 0 in plaats van een ontbrekend kenmerk"
                if nul
                else ""
            )
            regels.append(
                f"{len(zonder_maat)} van de {totaal} strengen hebben geen bruikbare "
                f"profielmaat{staart}; ze zijn niet getoetst."
            )
        verdeling = _diameterverdeling(tabel, strengen)
        if verdeling is not None:
            regels.append(verdeling)
        return regels


@register
class DiameterOnderMinimum(_StrengCheck):
    """ATTR-002: een riool met een diameter onder de gangbare ondergrens."""

    id = "ATTR-002"
    title = "Diameter kleiner dan rond 200 mm"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt strengen waarvan de grootste profielmaat onder het minimum ligt."""
        minimum = context.config.drempels.minimale_diameter_mm

        for conduit in vrijvervalrioolleidingen(context):
            maat = _grootste_maat(conduit)
            if maat is None or maat >= minimum:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Profielmaat {maat:g} mm ligt onder de gangbare ondergrens van "
                f"{minimum:g} mm voor een vrijvervalriool.",
                maat_mm=maat,
                minimum_mm=minimum,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Wijst op de grens met de nulmeting en op de aard van de kleine leidingen."""
        minimum = context.config.drempels.minimale_diameter_mm
        klein = [
            conduit
            for conduit in vrijvervalrioolleidingen(context)
            if (_grootste_maat(conduit) or minimum) < minimum
        ]
        notities = [
            "De nulmeting toetst alleen de harde ondergrens van 63 mm uit de "
            "GWSW-waardebereiken; deze check gaat over het gat daarboven.",
        ]
        if klein:
            telling: dict[str, int] = {}
            for conduit in klein:
                soort = _soortnaam(conduit)
                telling[soort] = telling.get(soort, 0) + 1
            top = ", ".join(
                f"{soort} {aantal}"
                for soort, aantal in sorted(telling.items(), key=lambda paar: -paar[1])[:6]
            )
            notities.append(
                f"De bevindingen verdelen zich over deze klassen: {top}. Drains en "
                "perceel- of kolkaansluitleidingen zijn van nature dunner dan 200 mm; die "
                "bevindingen zeggen meer over de klasse-indeling dan over een gebrek."
            )
        return notities


@register
class MateriaalPastNietBijAanlegjaar(_StrengCheck):
    """ATTR-003: een materiaal dat in het aanlegjaar nog niet of niet meer bestond."""

    id = "ATTR-003"
    title = "Materiaal past niet bij aanlegjaar"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt het aanlegjaar met het tijdvak waarin het materiaal bestond."""
        tabel = context.plausibiliteit

        for conduit in vrijvervalrioolleidingen(context):
            regel = tabel.aanlegjaar(conduit.materiaal)
            jaar = conduit.aanlegjaar
            if regel is None or jaar is None:
                continue
            if regel.vanaf_jaar is not None and jaar < regel.vanaf_jaar:
                yield self._bevinding(context, conduit, jaar, regel.vanaf_jaar, "voor", regel)
            elif regel.tot_jaar is not None and jaar > regel.tot_jaar:
                yield self._bevinding(context, conduit, jaar, regel.tot_jaar, "na", regel)

    def _bevinding(self, context, conduit, jaar: int, grens: int, kant: str, regel) -> Finding:
        """Bouwt de bevinding met de grens en de toelichting erbij."""
        return self.finding(
            context,
            conduit.uri,
            conduit.label,
            f"Materiaal {conduit.materiaal} met aanlegjaar {jaar}, {kant} {grens}. "
            f"{regel.toelichting}".strip(),
            materiaal=conduit.materiaal,
            aanlegjaar=jaar,
            grensjaar=grens,
        )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen aanlegjaar of geen regel hebben."""
        strengen = vrijvervalrioolleidingen(context)
        zonder_jaar = sum(1 for conduit in strengen if conduit.aanlegjaar is None)
        zonder_regel = sum(
            1
            for conduit in strengen
            if context.plausibiliteit.aanlegjaar(conduit.materiaal) is None
        )
        notities = []
        if zonder_jaar:
            notities.append(
                f"{zonder_jaar} van de {len(strengen)} strengen hebben geen begindatum en "
                "zijn niet op aanlegjaar getoetst."
            )
        if zonder_regel:
            notities.append(
                f"{zonder_regel} strengen hebben een materiaal zonder tijdvakregel in "
                "`plausibiliteit.toml`."
            )
        return notities


@register
class VormVersusAfmetingen(_StrengCheck):
    """ATTR-004: de profielvorm strookt niet met breedte en hoogte."""

    id = "ATTR-004"
    title = "Vorm versus afmetingen inconsistent"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst de verhouding tussen breedte en hoogte tegen de profielvorm.

        Dat beide maten *aanwezig* zijn dwingt het MDSTOP-deelmodel al af; hier gaat
        het om hun onderlinge verhouding, en die toetst geen van beide
        conformiteitsklassen. Een ontbrekende maat wordt wel gemeld, want zonder
        maat is de verhouding niet vast te stellen.
        """
        tabel = context.plausibiliteit
        tolerantie = context.config.drempels.rondheid_tolerantie_mm

        for conduit in vrijvervalrioolleidingen(context):
            regel = tabel.afmetingen(conduit.vorm)
            if regel is None:
                continue
            breedte, hoogte = conduit.breedte_mm, conduit.hoogte_mm
            melding = self._melding(regel, breedte, hoogte, tolerantie)
            if melding is None:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                melding,
                vorm=conduit.vorm,
                breedte_mm=breedte,
                hoogte_mm=hoogte,
            )

    def _melding(self, regel, breedte, hoogte, tolerantie: float) -> str | None:
        """De reden waarom vorm en afmetingen niet bij elkaar passen, of None."""
        if breedte is None or hoogte is None:
            ontbreekt = "breedte" if breedte is None else "hoogte"
            return f"Profielvorm {regel.vorm} zonder {ontbreekt}; de verhouding is niet te toetsen."
        if regel.breedte_gelijk_hoogte and abs(breedte - hoogte) > tolerantie:
            return (
                f"Profielvorm {regel.vorm} met breedte {breedte:g} mm en hoogte "
                f"{hoogte:g} mm. {regel.toelichting}".strip()
            )
        if regel.hoogte_groter_dan_breedte and hoogte <= breedte:
            return (
                f"Profielvorm {regel.vorm} met hoogte {hoogte:g} mm niet groter dan breedte "
                f"{breedte:g} mm. {regel.toelichting}".strip()
            )
        if regel.hoogte_kleiner_dan_breedte and hoogte >= breedte:
            return (
                f"Profielvorm {regel.vorm} met hoogte {hoogte:g} mm niet kleiner dan breedte "
                f"{breedte:g} mm. {regel.toelichting}".strip()
            )
        return None

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen vorm dragen en hoeveel geen vormregel hebben."""
        populatie = _ongetoetst(
            context,
            lambda conduit: conduit.vorm,
            lambda conduit: context.plausibiliteit.afmetingen(conduit.vorm),
        )
        return _ongetoetst_notes(
            populatie,
            "geen profielvorm",
            "een profielvorm zonder regel in `plausibiliteit.toml`",
        )


@register
class EenhedenfoutBinnenBereik(_StrengCheck):
    """ATTR-005: een profielmaat die in centimeters lijkt te staan."""

    id = "ATTR-005"
    title = "Eenhedenfouten die binnen de GWSW-waardebereiken vallen"
    severity = Severity.ERROR
    dimension = Dimension.ACCURACY
    # Deze check meldt per profielmaat, niet per strengeinde: breedte en hoogte van
    # dezelfde streng zijn twee bevindingen en horen twee melding-ID's te krijgen.
    id_sleutels = ("kenmerk",)

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Zoekt maten die zelf geen handelsmaat zijn maar maal tien wel.

        Een breedte van 30 zou als 300 mm bedoeld kunnen zijn. Buiten het
        GWSW-waardebereik vangt de nulmeting zulke waarden al; binnen het bereik
        blijven ze onopgemerkt, en dat is precies dit gat.
        """
        tabel = context.plausibiliteit
        drempel = context.config.drempels.eenheidsverdenking_diameter_mm
        if not tabel.standaarddiameters_mm:
            return

        for conduit in vrijvervalrioolleidingen(context):
            for naam, maat in (("breedte", conduit.breedte_mm), ("hoogte", conduit.hoogte_mm)):
                if maat is None or maat <= 0 or maat > drempel:
                    continue
                if tabel.is_standaardmaat(maat) or not tabel.is_standaardmaat(maat * 10):
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"De {naam} van {maat:g} mm is geen handelsmaat, maar {maat * 10:g} mm "
                    "wel; de waarde lijkt in centimeters genoteerd.",
                    kenmerk=naam,
                    waarde_mm=maat,
                    vermoedelijke_waarde_mm=maat * 10,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Legt vast waar de check wel en niet naar kijkt."""
        drempel = context.config.drempels.eenheidsverdenking_diameter_mm
        if not context.plausibiliteit.standaarddiameters_mm:
            return [
                "Deze check is niet gedraaid: er staan geen handelsmaten in "
                "`plausibiliteit.toml` (`standaarddiameters_mm`)."
            ]
        return [
            f"Alleen breedte en hoogte van leidingen zijn getoetst, en alleen onder "
            f"{drempel:g} mm. Eenhedenfouten in lengte- of hoogtewaarden vallen hier niet "
            "onder; ATTR-008, ATTR-009 en de HGT-categorie kijken daarnaar."
        ]


@register
class DiameterGroterDanPut(_StrengCheck):
    """ATTR-006: een streng die niet in de put past waaraan hij hangt."""

    id = "ATTR-006"
    title = "Strengdiameter groter dan afmeting van de aangesloten put"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de profielmaat met de grootste binnenmaat van de put.

        De grootste putmaat is de mildste vergelijking: een buis kan in een
        rechthoekige put langs de lange zijde binnenkomen. Zo blijven alleen de
        gevallen over waarin de buis in geen enkele richting past.
        """
        marge = context.config.drempels.put_diameter_marge_mm

        for conduit in vrijvervalrioolleidingen(context):
            maat = _grootste_maat(conduit)
            if maat is None:
                continue
            begin, eind = verbonden_knopen(context, conduit)
            for zijde, put_uri in (("beginpunt", begin), ("eindpunt", eind)):
                node = context.dataset.nodes.get(put_uri) if put_uri else None
                if node is None:
                    continue
                putmaat = _grootste_putmaat(node)
                if putmaat is None or maat <= putmaat + marge:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Profielmaat {maat:g} mm is groter dan de grootste binnenmaat "
                    f"{putmaat:g} mm van put {node.label!r} aan het {zijde}.",
                    maat_mm=maat,
                    putmaat_mm=putmaat,
                    put=node.label,
                    zijde=zijde,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten geen afmetingen hebben."""
        alle_putten = putten(context)
        zonder = sum(1 for node in alle_putten if _grootste_putmaat(node) is None)
        if not zonder:
            return []
        return [
            f"{zonder} van de {len(alle_putten)} putten hebben geen breedte of lengte; "
            "strengen die daaraan hangen zijn niet getoetst."
        ]


@register
class AanlegjaarBuitenBereik(_StrengCheck):
    """ATTR-007: een aanlegjaar in de toekomst of voor het riooltijdperk."""

    id = "ATTR-007"
    title = "Aanlegjaar in de toekomst of voor 1870"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst het aanlegjaar van strengen en putten op een aannemelijk bereik."""
        minimum = context.config.drempels.aanlegjaar_minimum
        dit_jaar = date.today().year

        alle_putten = putten(context)
        alles: list[Node | Conduit] = [*vrijvervalrioolleidingen(context), *alle_putten]
        for object_ in alles:
            datum = object_.date("Begindatum")
            if datum is None:
                continue
            if minimum <= datum.year <= dit_jaar:
                continue
            kant = "voor" if datum.year < minimum else "na"
            grens = minimum if datum.year < minimum else dit_jaar
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"Begindatum {datum.isoformat()} ligt {kant} {grens}.",
                aanlegjaar=datum.year,
                grensjaar=grens,
            )

    def examined(self, context: CheckContext) -> int:
        """Het aantal strengen plus putten."""
        alle_putten = putten(context)
        return len(vrijvervalrioolleidingen(context)) + len(alle_putten)


@register
class StrenglengteBuitenBereik(_StrengCheck):
    """ATTR-008: een strenglengte buiten het aannemelijke bereik."""

    id = "ATTR-008"
    title = "Strenglengte korter dan X m of langer dan X m"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst de administratieve lengte op het geconfigureerde bereik."""
        drempels = context.config.drempels
        minimum = drempels.minimale_strenglengte_m
        maximum = drempels.maximale_strenglengte_m

        for conduit in vrijvervalrioolleidingen(context):
            lengte = conduit.lengte_m
            if lengte is None or minimum <= lengte <= maximum:
                continue
            kant = "onder" if lengte < minimum else "boven"
            grens = minimum if lengte < minimum else maximum
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Administratieve lengte {lengte:g} m ligt {kant} de grens van {grens:g} m.",
                lengte_m=lengte,
                grens_m=grens,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen lengte hebben."""
        strengen = vrijvervalrioolleidingen(context)
        zonder = sum(1 for conduit in strengen if conduit.lengte_m is None)
        if not zonder:
            return []
        return [f"{zonder} van de {len(strengen)} strengen hebben geen administratieve lengte."]


@register
class LengteWijktAfVanGeometrie(_StrengCheck):
    """ATTR-009: de getekende lengte klopt niet met de geregistreerde lengte."""

    id = "ATTR-009"
    title = "Geometrische lengte wijkt meer dan X% af van administratieve lengte"
    severity = Severity.WARNING
    dimension = Dimension.CONSISTENCY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt de lengte van de hartlijn met de administratieve lengte."""
        drempel = context.config.drempels.lengte_afwijking_procent

        for conduit in vrijvervalrioolleidingen(context):
            administratief = conduit.lengte_m
            if administratief is None or administratief <= 0:
                continue
            if conduit.line is None or conduit.line.is_empty:
                continue
            gemeten = float(conduit.line.length)
            afwijking = 100.0 * abs(gemeten - administratief) / administratief
            if afwijking <= drempel:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"De hartlijn is {gemeten:.2f} m lang terwijl de administratie "
                f"{administratief:g} m zegt: {afwijking:.1f}% afwijking (drempel "
                f"{drempel:g}%).",
                geometrische_lengte_m=round(gemeten, 3),
                administratieve_lengte_m=administratief,
                afwijking_procent=round(afwijking, 2),
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen niet te vergelijken waren."""
        strengen = vrijvervalrioolleidingen(context)
        zonder = sum(
            1
            for conduit in strengen
            if conduit.lengte_m is None or conduit.line is None or conduit.line.is_empty
        )
        if not zonder:
            return []
        return [
            f"{zonder} van de {len(strengen)} strengen missen een administratieve lengte of "
            "een geometrie en konden niet vergeleken worden."
        ]


@register
class LeidingmateriaalPastNietBijPut(_StrengCheck):
    """ATTR-010: een betonnen of gemetselde streng op een put die daar niet bij past."""

    id = "ATTR-010"
    title = "Leidingmateriaal beton of metselwerk terwijl het putmateriaal daar niet bij past"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Vergelijkt het leidingmateriaal met dat van de aangesloten putten."""
        tabel = context.plausibiliteit

        for conduit in vrijvervalrioolleidingen(context):
            regel = tabel.putmateriaal(conduit.materiaal)
            if regel is None:
                continue
            for node in putten_van(context, conduit):
                putmateriaal = node.reference("MateriaalPut") or node.reference("MateriaalBouwwerk")
                onwaarschijnlijk = regel.onwaarschijnlijke_putmaterialen
                if putmateriaal is None or putmateriaal not in onwaarschijnlijk:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Leidingmateriaal {conduit.materiaal} op put {node.label!r} van "
                    f"{putmateriaal}; dat putmateriaal is daar onwaarschijnlijk. "
                    f"{regel.toelichting}".strip(),
                    materiaal=conduit.materiaal,
                    putmateriaal=putmateriaal,
                    put=node.label,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen regel in de tabel hebben en dus ongemoeid bleven.

        `examined` telt alle vrijvervalstrengen, maar vergeleken worden alleen de
        materialen die in `[[leiding_put_materiaal]]` staan. Zonder deze regel leest
        "0 bevindingen op 17.603 bekeken objecten" als een schone rekening voor het
        hele stelsel, terwijl de tabel er misschien maar een handvol van aanraakt.
        """
        tabel = context.plausibiliteit
        strengen = vrijvervalrioolleidingen(context)
        zonder = Counter(
            conduit.materiaal or "zonder materiaal"
            for conduit in strengen
            if tabel.putmateriaal(conduit.materiaal) is None
        )
        if not zonder:
            return []
        verdeling = ", ".join(f"{naam} {aantal}" for naam, aantal in zonder.most_common())
        return [
            f"{sum(zonder.values())} van de {len(strengen)} strengen dragen een "
            f"leidingmateriaal waarvoor de tabel geen regel heeft en zijn niet "
            f"vergeleken ({verdeling})."
        ]


@register
class MateriaalPastNietBijProfielvorm(_StrengCheck):
    """ATTR-012: een profielvorm die het materiaal niet kent."""

    id = "ATTR-012"
    title = "Materiaal past niet bij profielvorm"
    severity = Severity.WARNING
    dimension = Dimension.PLAUSIBILITY

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Toetst de profielvorm tegen de vormen die bij het materiaal horen."""
        tabel = context.plausibiliteit

        for conduit in vrijvervalrioolleidingen(context):
            regel = tabel.vorm(conduit.materiaal)
            if regel is None or conduit.vorm is None:
                continue
            if conduit.vorm in regel.toegestane_vormen:
                continue
            yield self.finding(
                context,
                conduit.uri,
                conduit.label,
                f"Materiaal {conduit.materiaal} met profielvorm {conduit.vorm}; verwacht "
                f"wordt {', '.join(regel.toegestane_vormen)}. {regel.toelichting}".strip(),
                materiaal=conduit.materiaal,
                vorm=conduit.vorm,
                toegestane_vormen=regel.toegestane_vormen,
            )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel strengen geen materiaal dragen en hoeveel geen vormregel hebben."""
        populatie = _ongetoetst(
            context,
            lambda conduit: conduit.materiaal,
            lambda conduit: context.plausibiliteit.vorm(conduit.materiaal),
        )
        return _ongetoetst_notes(
            populatie,
            "geen materiaal",
            "een materiaal zonder vormregel in `plausibiliteit.toml`",
        )


@register
class HoogteOpVulwaarde(Check):
    """ATTR-013: een hoogtekenmerk dat een vulwaarde draagt in plaats van een meting.

    De leesregel zelf staat in `dataset.markeer_vulwaarden` (toegepast in `toetsrun`);
    deze check meldt per object een keer wat die regel heeft weggezet, zodat het in de
    uitvoer staat en niet alleen in de toelichting van de hoogtechecks.
    """

    id = "ATTR-013"
    title = "Hoogtekenmerk op vulwaarde (rond 0 m NAP) geregistreerd als meting"
    severity = Severity.WARNING
    dimension = Dimension.COMPLETENESS

    def _objecten(self, context: CheckContext) -> list[Node | Conduit]:
        """De objecten die een hoogtekenmerk kunnen dragen: knopen plus strengen."""
        return [*netwerkknopen(context), *vrijvervalrioolleidingen(context)]

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt elk object waarop ten minste een hoogtekenmerk een vulwaarde was."""
        band = context.config.vulwaarden.hoogte_band_m
        for object_ in self._objecten(context):
            if not object_.vulwaarden:
                continue
            aantal = len(object_.vulwaarden)
            opsomming = " en ".join(
                f"{vul.kind} op {vul.value:.3f} m NAP" for vul in object_.vulwaarden
            )
            yield self.finding(
                context,
                object_.uri,
                object_.label,
                f"{opsomming} {taal.vorm(aantal, 'valt', 'vallen')} binnen de vulwaardeband "
                f"van {band:g} m en {taal.vorm(aantal, 'is', 'zijn')} als niet geregistreerd "
                "gelezen in plaats van als meting.",
                kenmerken=[vul.kind for vul in object_.vulwaarden],
                waarden=[vul.value for vul in object_.vulwaarden],
                band_m=band,
            )

    def _buiten_populatie(self, context: CheckContext) -> tuple[int, int]:
        """Knopen en strengen met een vulwaarde die deze check niet meldt.

        De leesregel loopt over alle knopen en alle strengen van de dataset; deze check
        meldt de netwerkknopen plus de vrijvervalstrengen. Wat daarbuiten valt -- een
        persleiding of een drain, een compartiment- of hulpstukorientatie -- is wel als
        ontbrekend gelezen maar staat in geen enkele melding (BO-27).
        """
        gemeld = {object_.uri for object_ in self._objecten(context)}
        knopen = sum(
            1
            for node in context.dataset.nodes.values()
            if node.vulwaarden and node.uri not in gemeld
        )
        strengen = sum(
            1
            for conduit in context.dataset.conduits.values()
            if conduit.vulwaarden and conduit.uri not in gemeld
        )
        return knopen, strengen

    def notes(self, context: CheckContext) -> list[str]:
        """Zegt waarop de leesregel werkte, of dat hij uit staat."""
        opties = context.config.vulwaarden
        if not opties.hoogte_kenmerken:
            return [
                "De vulwaarde-leesregel staat uit (`[vulwaarden] hoogte_kenmerken` is leeg); "
                "een 0,000 in een hoogtekenmerk is in dit project als meting gelezen."
            ]
        notities = [
            f"Als vulwaarde gold |waarde| <= {opties.hoogte_band_m:g} m op "
            f"{', '.join(opties.hoogte_kenmerken)}. Zo'n kenmerk is als ontbrekend gelezen; "
            "de hoogtechecks slaan het object daardoor over en tellen het in hun toelichting "
            "mee bij de objecten zonder dat kenmerk, zonder de vulwaarde als reden te noemen."
        ]
        knopen, strengen = self._buiten_populatie(context)
        if knopen or strengen:
            geraakt = " en ".join(
                deel
                for deel in (
                    taal.getal(knopen, "knoop", "knopen") if knopen else "",
                    taal.getal(strengen, "streng", "strengen") if strengen else "",
                )
                if deel
            )
            notities.append(
                f"De leesregel raakte daarnaast {geraakt} buiten de gemelde populatie "
                "(netwerkknopen plus vrijvervalstrengen) -- een persleiding, een drain, "
                "een compartiment- of hulpstukorientatie. Ook daar geldt het kenmerk als "
                "ontbrekend, maar deze check meldt die objecten niet."
            )
        return notities

    def examined(self, context: CheckContext) -> int:
        """Netwerkknopen plus vrijvervalstrengen."""
        return len(self._objecten(context))


@dataclass(frozen=True)
class _PropertyTelling:
    """Per kenmerktype hoeveel instanties de verkeerde waardeproperty gebruiken."""

    verwacht: str
    totaal: int
    fout: int
    vulwaarde_nul: int


def _is_vulwaarde_nul(waarde: object) -> bool:
    """Of een waarde de numerieke vulwaarde 0 is (0, 0.0, "0"), en geen tekstlabel.

    De BrutIS-export vult een ontbrekend WIBONThema met de literal 0; een tekstlabel
    als "riool vrijverval" is een ander soort fout en telt hier niet mee.
    """
    try:
        return float(str(waarde)) == 0.0
    except ValueError:
        return False


def _property_tellingen(context: CheckContext) -> dict[str, _PropertyTelling]:
    """Telt per kenmerktype de instanties die de door de ontologie geeiste property missen.

    De verwachte property komt uit `dataset.kenmerk_property` (de `owl:onProperty`-keten,
    afgeleid bij het laden); de daadwerkelijke property leest deze functie rechtstreeks uit
    de datagraaf. Een fout is een instantie die de geeiste property mist maar de andere wel
    draagt -- `hasValue` waar `hasReference` hoort, of andersom. Een instantie zonder beide
    is geen property-fout maar een leeg kenmerk en telt niet mee.
    """
    graph = context.dataset.graph
    tellingen: dict[str, _PropertyTelling] = {}
    for kenmerk, verwacht in context.dataset.kenmerk_property.items():
        totaal = fout = vulwaarde_nul = 0
        for instantie in graph.subjects(RDF.type, URIRef(GWSW + kenmerk)):
            totaal += 1
            waarde = graph.value(instantie, HAS_VALUE)
            referentie = graph.value(instantie, HAS_REFERENCE)
            if verwacht == "hasReference" and referentie is None and waarde is not None:
                fout += 1
                if _is_vulwaarde_nul(waarde):
                    vulwaarde_nul += 1
            elif verwacht == "hasValue" and waarde is None and referentie is not None:
                fout += 1
        tellingen[kenmerk] = _PropertyTelling(verwacht, totaal, fout, vulwaarde_nul)
    return tellingen


@register
class PropertyTegenOntologie(Check):
    """ATTR-014: een kenmerk gebruikt de verkeerde waardeproperty tegenover de ontologie.

    De ontologie bindt de waarde van een kenmerk via een restrictie aan `hasReference`
    (naar een domeinlijstcollectie) of aan `hasValue`. Een export die de verkeerde
    property schrijft -- `WIBONThema` met `hasValue 0` waar `hasReference` hoort -- is een
    consistentiefout tegen de ontologie zelf, en de SHACL-nulmeting mist hem per
    constructie: een `allValuesFrom` over een afwezige property is vacuously true (issue
    #37). De check is generiek over alle kenmerktypen en meldt per kenmerk een keer, als
    systemische melding over de hele export -- niet per object, want dat zijn er op De
    Wolden en Hoogeveen 23.440.
    """

    id = "ATTR-014"
    title = "Kenmerk gebruikt de verkeerde waardeproperty tegenover de ontologie"
    severity = Severity.ERROR
    dimension = Dimension.CONSISTENCY
    id_sleutels = ("kenmerk",)
    volledig_bereik = True

    def _tellingen(self, context: CheckContext) -> dict[str, _PropertyTelling]:
        return context.cached("attr014:tellingen", lambda: _property_tellingen(context))

    def run(self, context: CheckContext) -> Iterator[Finding]:
        """Meldt per kenmerktype met een property-fout een aggregaatbevinding."""
        for kenmerk, telling in sorted(self._tellingen(context).items()):
            if telling.fout == 0:
                continue
            yield Finding(
                check_id=self.id,
                severity=self.severity,
                dimension=self.dimension,
                object_uri="",
                object_label=kenmerk,
                message=_property_boodschap(kenmerk, telling),
                typing_reliable=True,
                details={"kenmerk": kenmerk},
                systemisch=True,
            )

    def examined(self, context: CheckContext) -> int:
        """Alle kenmerkinstanties die tegen een property-restrictie gehouden zijn."""
        return sum(telling.totaal for telling in self._tellingen(context).values())

    def notes(self, context: CheckContext) -> list[str]:
        """Zegt hoeveel kenmerktypen een voorgeschreven property hadden, of dat er geen zijn."""
        aantal = len(context.dataset.kenmerk_property)
        if aantal == 0:
            return [
                "Geen enkel kenmerktype droeg een ontologische property-restrictie "
                "(geen klassenhierarchie geladen); er is niets tegen de ontologie gehouden."
            ]
        return [
            f"{taal.getal(aantal, 'kenmerktype', 'kenmerktypen')} met een voorgeschreven "
            "property (`hasValue` of `hasReference`) getoetst. Kenmerken zonder zo'n "
            "restrictie -- zoals Straatnaam -- kennen geen voorgeschreven property en "
            "vallen buiten deze toets."
        ]


def _property_boodschap(kenmerk: str, telling: _PropertyTelling) -> str:
    """De aggregaattekst voor een kenmerk dat de verkeerde waardeproperty gebruikt."""
    if telling.verwacht == "hasReference":
        kern = f"{kenmerk} gebruikt hasValue in plaats van hasReference op {telling.fout} objecten"
        if telling.vulwaarde_nul:
            kern += f", waarvan {telling.vulwaarde_nul} met de vulwaarde 0"
        return kern + "."
    return f"{kenmerk} gebruikt hasReference in plaats van hasValue op {telling.fout} objecten."


def _soortnaam(object_) -> str:
    """De korte GWSW-klassenaam van een object."""
    types = sorted(soort.rsplit("/", 1)[-1] for soort in object_.types)
    return types[0] if types else "onbekend"


def _grootste_maat(conduit: Conduit) -> float | None:
    """De grootste profielmaat van een streng in millimeters."""
    maten = [maat for maat in (conduit.breedte_mm, conduit.hoogte_mm) if maat and maat > 0]
    return max(maten) if maten else None


def _kant_van_bereik(regel: MaterialDiameter, maat: float) -> str | None:
    """'onder' of 'boven' als de maat buiten het diameterbereik valt, anders None."""
    if regel.minimum_mm is not None and maat < regel.minimum_mm:
        return "onder"
    if regel.maximum_mm is not None and maat > regel.maximum_mm:
        return "boven"
    return None


def _registreert_nulmaat(conduit: Conduit) -> bool:
    """True als een profielmaat als 0 geregistreerd staat in plaats van te ontbreken.

    `_grootste_maat` filtert de 0 weg net als een ontbrekend kenmerk; deze regel maakt
    de twee weer uit elkaar door het kenmerk zelf op te vragen.
    """
    for kind in ("BreedteLeiding", "HoogteLeiding"):
        aspect = conduit.aspect(kind)
        if aspect is not None and aspect.number == 0:
            return True
    return False


def _diameterverdeling(tabel: PlausibilityTables, strengen: Sequence[Conduit]) -> str | None:
    """Een Markdown-tabel met per materiaal het aantal, het aantal buiten bereik en de
    feitelijke min- en max-diameter uit de data.

    Het aantal telt alle strengen met dat materiaal; de min en max komen alleen uit de
    strengen met een bruikbare profielmaat, en het aantal buiten bereik is 0 voor een
    materiaal zonder regel -- zonder grens valt er niets te overschrijden. Geeft None als
    geen streng een materiaal draagt.
    """
    per_materiaal: dict[str, list[Conduit]] = defaultdict(list)
    for conduit in strengen:
        if conduit.materiaal is not None:
            per_materiaal[conduit.materiaal].append(conduit)
    if not per_materiaal:
        return None
    regels = [
        "| Materiaal | Aantal | Buiten bereik | Min mm | Max mm |",
        "|---|---|---|---|---|",
    ]
    for materiaal in sorted(per_materiaal):
        groep = per_materiaal[materiaal]
        regel = tabel.diameter(materiaal)
        maten = [maat for conduit in groep if (maat := _grootste_maat(conduit)) is not None]
        buiten = (
            sum(1 for maat in maten if _kant_van_bereik(regel, maat) is not None)
            if regel is not None
            else 0
        )
        min_mm = f"{min(maten):g}" if maten else "–"
        max_mm = f"{max(maten):g}" if maten else "–"
        regels.append(f"| {materiaal} | {len(groep)} | {buiten} | {min_mm} | {max_mm} |")
    return "\n".join(regels)


def _grootste_putmaat(node) -> float | None:
    """De grootste binnenmaat van een put in millimeters."""
    maten = [
        node.number(kenmerk)
        for kenmerk in (
            "BreedtePut",
            "LengtePut",
            "DiameterPut",
            "BreedteBouwwerk",
            "LengteBouwwerk",
        )
    ]
    bruikbaar = [maat for maat in maten if maat and maat > 0]
    return max(bruikbaar) if bruikbaar else None
