"""De managementsamenvatting: voldoen we in dit gebied, en waaraan niet.

Vier regels boven aan het bevindingenrapport: een per conformiteitsklasse uit de
projectconfiguratie, en een voor de eigen checks buiten het GWSW om. Het criterium is
hard en eenvoudig: **een vinkje betekent nul fouten in dit gebied**. Waarschuwingen
blokkeren niet, maar hun aantal staat er wel bij -- een regel die zwijgt over vierhonderd
waarschuwingen leest als "niets aan de hand".

De tellingen komen uit de meldingenstroom van dit gebied, dus ze zijn precies wat de
lezer verderop in het rapport en in de CSV terugvindt. Een melding die meerdere
conformiteitsklassen noemt telt bij elke klasse mee; de klassen zijn geen verdeling van
de meldingen, en de som over de regels ligt daarom hoger dan het totaal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nlriochecker.checks import Severity
from nlriochecker.meting import Meetbereik
from nlriochecker.taal import getal
from nlriochecker.uitvoer.melding import BRON_NULMETING, BRON_REGISTER, Melding

VINKJE = "✔"
KRUISJE = "✘"
NIET_GEMETEN = "–"

REGEL_EIGEN_CHECKS = "Eigen checks buiten GWSW"


@dataclass(frozen=True)
class Regel:
    """Een regel van de samenvatting: waaraan, en hoe het ervoor staat."""

    onderwerp: str
    # Leeg als er niet gemeten is; dan staat er een toestandstekst in plaats van een
    # oordeel, en hoort er geen vinkje of kruisje bij.
    fouten: int = 0
    systemische_fouten: int = 0
    waarschuwingen: int = 0
    systemische_waarschuwingen: int = 0
    gemeten: bool = True
    toelichting: str = ""

    @property
    def teken(self) -> str:
        """Vinkje bij nul fouten, kruisje bij een of meer, streepje zonder meting."""
        if not self.gemeten:
            return NIET_GEMETEN
        return VINKJE if self.fouten == 0 else KRUISJE

    def tekst(self) -> str:
        """De regel zoals hij in het rapport komt te staan."""
        if not self.gemeten:
            return f"| {self.teken} | {self.onderwerp} | {self.toelichting} |"
        telling = (
            f"{getal(self.fouten, 'fout', 'fouten')} "
            f"(waarvan {self.systemische_fouten} systemisch), "
            f"{getal(self.waarschuwingen, 'waarschuwing', 'waarschuwingen')} "
            f"({self.systemische_waarschuwingen} systemisch)"
        )
        return f"| {self.teken} | {self.onderwerp} | {telling} |"


def samenvatting(
    meldingen: Sequence[Melding],
    meetbereik: Meetbereik,
    *,
    klassenhierarchie: bool = True,
) -> list[Regel]:
    """De regels van de managementsamenvatting, in vaste volgorde.

    Eerst een regel per conformiteitsklasse uit de projectconfiguratie, dan een
    totaalregel voor de eigen checks. De volgorde van de klassen volgt de
    projectconfiguratie (gesorteerd), zodat een project met andere klassen dezelfde
    opzet krijgt.

    Een klasse waarop deze run niet gemeten heeft -- geen `--shacl`, of een
    `--cfk`-deelset waar zij buiten valt -- krijgt geen vinkje en geen kruisje maar de
    toestandstekst: er valt niets te oordelen. Een klasse die wél in de gekozen set zit
    krijgt haar oordeel, ook als de set een deelset was; het voorbehoud over die deelset
    staat als markering boven het rapport (BO-7).

    `klassenhierarchie` gaat alleen over de eigen checks. Zonder haar is de lezing van
    knopen en strengen op geometrie teruggevallen -- en op een OroX-export leveren
    `putten()` en `leidingen()` bovendien nul objecten -- en draaien de checks dus over
    een onvolledige selectie; daar hoort geen oordeel bij, dus geen vinkje en geen
    kruisje. De CFK-regels blijven
    wel hun oordeel dragen: hun tellingen komen uit de SHACL-nulmeting, die de dataset
    wel degelijk gemeten heeft, en ze op "niet gemeten" zetten zou een uitgevoerde
    meting verzwijgen.
    """
    regels = [_cfk_regel(cfk, meldingen, meetbereik) for cfk in meetbereik.volledige_set]
    eigen = _eigen_regel(meldingen)
    regels.append(eigen if klassenhierarchie else _zonder_oordeel(eigen))
    return regels


def _zonder_oordeel(regel: Regel) -> Regel:
    """Dezelfde regel, maar zonder vinkje of kruisje: er valt niets te oordelen.

    De tellingen blijven staan, in de toelichting. Ze weglaten zou een lezer laten
    denken dat er niets gevonden is, en dat is iets anders dan dat het gevondene geen
    oordeel draagt -- de checks hebben over een onvolledige selectie gedraaid.
    """
    return Regel(
        onderwerp=regel.onderwerp,
        gemeten=False,
        toelichting=(
            f"geen klassenhierarchie: {getal(regel.fouten, 'fout', 'fouten')} en "
            f"{getal(regel.waarschuwingen, 'waarschuwing', 'waarschuwingen')} uit een "
            f"onvolledige selectie, niet als oordeel te lezen"
        ),
    )


def _cfk_regel(cfk: str, meldingen: Sequence[Melding], meetbereik: Meetbereik) -> Regel:
    """De regel van een conformiteitsklasse."""
    onderwerp = f"GWSW CFK {cfk}"
    if cfk not in meetbereik.gekozen:
        toelichting = (
            "niet gemeten in deze run"
            if meetbereik.gemeten
            else "geen nulmeting meegegeven (`--shacl` ontbreekt)"
        )
        return Regel(onderwerp=onderwerp, gemeten=False, toelichting=toelichting)
    eigen = [
        melding for melding in meldingen if melding.bron == BRON_NULMETING and cfk in melding.cfk
    ]
    return _tel(onderwerp, eigen)


def _eigen_regel(meldingen: Sequence[Melding]) -> Regel:
    """De totaalregel van de eigen check-engine.

    Een regel en niet een per categorie: de uitsplitsing staat in de detailrapportage
    eronder, en vier regels zijn nog te overzien terwijl twaalf dat niet zijn.
    """
    return _tel(
        REGEL_EIGEN_CHECKS,
        [melding for melding in meldingen if melding.bron == BRON_REGISTER],
    )


def _tel(onderwerp: str, meldingen: Sequence[Melding]) -> Regel:
    """Telt fouten en waarschuwingen, en hoeveel daarvan systemisch zijn."""
    fouten = [m for m in meldingen if m.ernst == Severity.ERROR.value]
    waarschuwingen = [m for m in meldingen if m.ernst == Severity.WARNING.value]
    return Regel(
        onderwerp=onderwerp,
        fouten=len(fouten),
        systemische_fouten=sum(1 for m in fouten if m.systemisch),
        waarschuwingen=len(waarschuwingen),
        systemische_waarschuwingen=sum(1 for m in waarschuwingen if m.systemisch),
    )


def als_tabel(regels: Sequence[Regel]) -> list[str]:
    """De samenvatting als Markdown-tabel."""
    return [
        "| | Voldoet aan | Bevindingen |",
        "| --- | --- | --- |",
        *[regel.tekst() for regel in regels],
    ]
