"""ATTR-checks: plausibiliteit van de attribuutwaarden van strengen en putten.

De plausibiliteitstabellen (materiaal versus diameter, aanlegjaar en profielvorm)
staan in `plausibiliteit.toml`; deze module bevat alleen de redenering. Een
materiaal dat niet in de tabel staat wordt niet getoetst, en elke check meldt in
haar toelichting hoeveel strengen daardoor buiten beeld bleven.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from gwswpijplijn.checks.base import (
    Check,
    CheckContext,
    Dimension,
    Finding,
    Severity,
    register,
)
from gwswpijplijn.checks.verbanden import objecten_van_klassen, putten_van
from gwswpijplijn.dataset import Conduit


def _strengen(context: CheckContext) -> list[Conduit]:
    """De vrijvervalstrengen waarop de ATTR-checks draaien."""
    return context.cached(
        "attr:strengen",
        lambda: objecten_van_klassen(context, context.config.klassen.vrijvervalleiding, "conduits"),
    )


def _zonder_regel(context: CheckContext, kies) -> tuple[int, int]:
    """Telt hoeveel strengen geen plausibiliteitsregel hebben, en hoeveel er zijn."""
    strengen = _strengen(context)
    return sum(1 for conduit in strengen if kies(conduit) is None), len(strengen)


class _StrengCheck(Check):
    """Basis voor de ATTR-checks die per vrijvervalstreng redeneren."""

    def examined(self, context: CheckContext) -> int:
        """Het aantal vrijvervalstrengen."""
        return len(_strengen(context))


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

        for conduit in _strengen(context):
            regel = tabel.diameter(conduit.materiaal)
            maat = _grootste_maat(conduit)
            if regel is None or maat is None:
                continue
            if regel.minimum_mm is not None and maat < regel.minimum_mm:
                yield self._bevinding(context, conduit, maat, regel, "onder")
            elif regel.maximum_mm is not None and maat > regel.maximum_mm:
                yield self._bevinding(context, conduit, maat, regel, "boven")

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
        """Meldt hoeveel strengen geen materiaalregel hebben."""
        zonder, totaal = _zonder_regel(
            context, lambda conduit: context.plausibiliteit.diameter(conduit.materiaal)
        )
        if not zonder:
            return []
        return [
            f"{zonder} van de {totaal} strengen hebben een materiaal zonder regel in "
            f"`plausibiliteit.toml` (of geen materiaal) en zijn niet getoetst."
        ]


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

        for conduit in _strengen(context):
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
            for conduit in _strengen(context)
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

        for conduit in _strengen(context):
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
        strengen = _strengen(context)
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

        for conduit in _strengen(context):
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
        """Meldt hoeveel strengen geen vormregel hebben."""
        zonder, totaal = _zonder_regel(
            context, lambda conduit: context.plausibiliteit.afmetingen(conduit.vorm)
        )
        if not zonder:
            return []
        return [
            f"{zonder} van de {totaal} strengen hebben een profielvorm zonder regel in "
            "`plausibiliteit.toml` (of geen vorm) en zijn niet getoetst."
        ]


@register
class EenhedenfoutBinnenBereik(_StrengCheck):
    """ATTR-005: een profielmaat die in centimeters lijkt te staan."""

    id = "ATTR-005"
    title = "Eenhedenfouten die binnen de GWSW-waardebereiken vallen"
    severity = Severity.ERROR
    dimension = Dimension.ACCURACY

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

        for conduit in _strengen(context):
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

        for conduit in _strengen(context):
            maat = _grootste_maat(conduit)
            if maat is None:
                continue
            for node in putten_van(context, conduit):
                putmaat = _grootste_putmaat(node)
                if putmaat is None or maat <= putmaat + marge:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Profielmaat {maat:g} mm is groter dan de grootste binnenmaat "
                    f"{putmaat:g} mm van put {node.label!r}.",
                    maat_mm=maat,
                    putmaat_mm=putmaat,
                    put=node.label,
                )

    def notes(self, context: CheckContext) -> list[str]:
        """Meldt hoeveel putten geen afmetingen hebben."""
        putten = objecten_van_klassen(context, context.config.klassen.put, "nodes")
        zonder = sum(1 for node in putten if _grootste_putmaat(node) is None)
        if not zonder:
            return []
        return [
            f"{zonder} van de {len(putten)} putten hebben geen breedte of lengte; "
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

        putten = objecten_van_klassen(context, context.config.klassen.put, "nodes")
        for object_ in (*_strengen(context), *putten):
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
        putten = objecten_van_klassen(context, context.config.klassen.put, "nodes")
        return len(_strengen(context)) + len(putten)


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

        for conduit in _strengen(context):
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
        strengen = _strengen(context)
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

        for conduit in _strengen(context):
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
        strengen = _strengen(context)
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

        for conduit in _strengen(context):
            regel = tabel.putmateriaal(conduit.materiaal)
            if regel is None:
                continue
            for node in putten_van(context, conduit):
                putmateriaal = node.reference("MateriaalPut") or node.reference("MateriaalBouwwerk")
                if putmateriaal is None or putmateriaal in regel.verwachte_putmaterialen:
                    continue
                yield self.finding(
                    context,
                    conduit.uri,
                    conduit.label,
                    f"Leidingmateriaal {conduit.materiaal} op put {node.label!r} van "
                    f"{putmateriaal}; verwacht wordt {', '.join(regel.verwachte_putmaterialen)}. "
                    f"{regel.toelichting}".strip(),
                    materiaal=conduit.materiaal,
                    putmateriaal=putmateriaal,
                    put=node.label,
                )


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

        for conduit in _strengen(context):
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
        """Meldt hoeveel strengen geen vormregel hebben."""
        zonder, totaal = _zonder_regel(
            context, lambda conduit: context.plausibiliteit.vorm(conduit.materiaal)
        )
        if not zonder:
            return []
        return [
            f"{zonder} van de {totaal} strengen hebben een materiaal zonder vormregel in "
            "`plausibiliteit.toml` (of geen materiaal) en zijn niet getoetst."
        ]


def _soortnaam(object_) -> str:
    """De korte GWSW-klassenaam van een object."""
    types = sorted(soort.rsplit("/", 1)[-1] for soort in object_.types)
    return types[0] if types else "onbekend"


def _grootste_maat(conduit: Conduit) -> float | None:
    """De grootste profielmaat van een streng in millimeters."""
    maten = [maat for maat in (conduit.breedte_mm, conduit.hoogte_mm) if maat and maat > 0]
    return max(maten) if maten else None


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
