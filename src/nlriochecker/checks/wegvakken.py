"""EXT-009: welke straat in de bebouwde kom heeft geen vrijvervalriolering?

Dit is geen kruising met een externe bron zoals EXT-001 of EXT-003 -- die toetsen een
GWSW-object tegen een pand of een waterdeel. Het is een **dekkingsvraag**: ligt er langs
deze weg riolering? Het toetsobject is daarom een NWB-wegvak en geen GWSW-object, en het
antwoord is er een van drie: bediend, leeg, of niet beoordeeld.

De module is een diepe eenheid met een smalle voordeur -- `beoordeel(context)` levert het
oordeel over elk kandidaat-wegvak -- en vier naden erachter, die elk apart te toetsen
zijn omdat ze op gewone arrays en geometrieen werken in plaats van op een `CheckContext`:

1. `kies_kandidaten` -- welke NWB-wegvakken doen mee: gemeentelijk, geen pad of
   parkeervak, lang genoeg, en met hun middelpunt in een TOP10NL-bebouwde kom.
2. `bouw_vlakken` -- de voronoi-partitie. Elk wegvak krijgt het gebied dat dichter bij
   hem ligt dan bij enig ander wegvak, geknipt op een buffer om de eigen lijn en op het
   komvlak. Dat vlak is tegelijk de meetkamer van stap 3 en de uitvoergeometrie.
3. `meet_kenmerken` -- wat er in en langs dat vlak ligt: vrijvervalstreng, put, pompunit,
   persleiding, en het aandeel onverhard wegdek uit de BGT.
4. `classificeer` -- de deterministische regel die daar rood, groen of grijs van maakt.

**Deterministisch, geen model.** Op de validatieset van 485 handmatig beoordeelde straten
haalt deze regel 32 fouten op 478 beoordeelde straten (93,3%); een getraind
gradient-boosting-model kwam op dezelfde set uit op 27 op 479 (94,4%). Dat verschil van vijf
straten weegt niet op tegen wat de regel oplevert: zij is in één alinea uit te leggen, zij
verandert niet als iemand de dataset opnieuw laadt, en zij voegt geen zware afhankelijkheid
toe. Zie BO-81 voor de ijking en de fouttabel.

**Vectoriseren is hier geen optimalisatie maar een eis.** De volle gemeente telt ~4100
kandidaten en de voronoi loopt over ~100.000 punten; per straat een `sindex`-query doen
kost minuten. Elke ruimtelijke stap hieronder gaat daarom over arrays: een `STRtree` per
bron, een `query` over alle vlakken tegelijk, en `np.bincount` om per wegvak op te tellen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import shapely
from gwsw_orox_helpers.dataset import Conduit, Node
from shapely import STRtree
from shapely.geometry import box

from nlriochecker.checkconfig import CheckThresholds
from nlriochecker.checks.base import CheckContext
from nlriochecker.checks.selectie import (
    mechanischeleidingen,
    pompunits,
    putten,
    vrijvervalrioolleidingen,
)
from nlriochecker.checks.treffers import Wegvakoordeel
from nlriochecker.externedata import VectorLayer

# De drie uitkomsten. Ze zijn dezelfde tekst als de statuswaarden van de GeoPackage
# (`uitvoer/objectkaart.STATUSSEN`) en niet toevallig: de laag `vlakken` schrijft ze
# ongewijzigd weg en de QGIS-stijl filtert erop. Er komt geen vijfde statuswaarde bij;
# `tests/test_checks_ext009.py` bewaakt dat deze drie een deelverzameling blijven.
STATUS_ROOD = "rood"
STATUS_GROEN = "groen"
STATUS_GRIJS = "grijs"

# Waarom een straat niet beoordeeld is. Grijs zonder reden leest als "in orde".
REDEN_ONVERHARD = "overwegend onverhard wegdek"
REDEN_DRUKRIOLERING = "drukriolering: pompunit of persleiding langs de straat"

# De NWB-kolommen die deze module leest, hoofdletterongevoelig (`VectorLayer.kolom`):
# het De Wolden-extract schrijft ze in hoofdletters, het Koekangerveld-extract in
# kleine letters.
KOLOM_WEGBEHEERDER = "WEGBEHSRT"
KOLOM_BAANSUBSOORT = "BST_CODE"
KOLOM_WEGVAK_ID = "WVK_ID"
KOLOM_STRAATNAAM = "STT_NAAM"

# De TOP10NL-kolommen van het plaatsvlak.
KOLOM_BEBOUWDE_KOM = "bebouwdekom"
KOLOM_PLAATSNAAM = "naamnl"
WAARDE_BEBOUWDE_KOM = "ja"

# De BGT-kolom met de verharding van een wegdeel.
KOLOM_WEGDEK = "plus_fysiek_voorkomen"

# Hoeveel ruimer dan de omhullende van alle wegvakken de voronoi mag uitwaaieren. De
# buitenste cellen zijn onbegrensd en worden hierop afgeknipt; ze moeten minstens de
# eigen straatbuffer kunnen dekken, vandaar een veelvoud daarvan. Het getal raakt de
# uitslag niet -- elk vlak wordt daarna alsnog op die buffer geknipt.
VORONOI_MARGE = 2.0


@dataclass(frozen=True)
class Kandidaten:
    """De wegvakken waarover EXT-009 iets zegt, plus wat er afviel.

    `alle_lijnen` draagt *alle* NWB-wegvakken en niet alleen de kandidaten: de
    voronoi-partitie moet over het hele wegennet lopen, anders krijgt een kandidaat het
    gebied van een buurstraat erbij die toevallig geen kandidaat is. `index` wijst de
    kandidaten daarin aan; de overige arrays staan in die volgorde.
    """

    alle_lijnen: np.ndarray
    index: np.ndarray
    sleutels: tuple[str, ...]
    straten: tuple[str, ...]
    plaatsen: tuple[str, ...]
    lengtes: np.ndarray
    middelpunten: np.ndarray
    komvlakken: np.ndarray
    afgevallen: dict[str, int]

    def __len__(self) -> int:
        """Het aantal kandidaat-wegvakken."""
        return len(self.index)

    @property
    def lijnen(self) -> np.ndarray:
        """De lijngeometrie van de kandidaten."""
        return self.alle_lijnen[self.index]


@dataclass(frozen=True)
class Riool:
    """De GWSW-geometrie waartegen een straat beoordeeld wordt.

    Vier losse arrays in plaats van een `CheckContext`, zodat `meet_kenmerken` zonder
    dataset te toetsen is.
    """

    vrijverval: np.ndarray
    mechanisch: np.ndarray
    putten: np.ndarray
    pompen: np.ndarray


@dataclass(frozen=True)
class Kenmerken:
    """Wat er per kandidaat-wegvak gemeten is; alle arrays even lang.

    `aandeel_onverhard` is NaN waar er geen BGT-wegdeel naast de straat ligt: dan is er
    niets gemeten, en dat is iets anders dan een aandeel van nul.
    """

    streng_in_cel: np.ndarray
    put_in_cel: np.ndarray
    persleiding_langs: np.ndarray
    pomp_nabij: np.ndarray
    aandeel_onverhard: np.ndarray


@dataclass(frozen=True)
class Wegvakuitslag:
    """Het oordeel over elk kandidaat-wegvak, plus wat er buiten de selectie viel.

    De afvaltelling hoort erbij en niet in een tweede aanroep: het rapport moet kunnen
    zeggen hoeveel wegvakken er niet bekeken zijn en waarom, en stilte daarover leest als
    "alles gecontroleerd".
    """

    oordelen: tuple[Wegvakoordeel, ...] = ()
    afgevallen: dict[str, int] = field(default_factory=dict)
    wegvakken_totaal: int = 0

    def __len__(self) -> int:
        """Het aantal beoordeelde wegvakken."""
        return len(self.oordelen)

    def aantal(self, status: str) -> int:
        """Hoeveel wegvakken deze status kregen."""
        return sum(1 for oordeel in self.oordelen if oordeel.status == status)

    def reden_telling(self) -> dict[str, int]:
        """Per reden hoeveel wegvakken er niet beoordeeld zijn."""
        telling = {REDEN_ONVERHARD: 0, REDEN_DRUKRIOLERING: 0}
        for oordeel in self.oordelen:
            if oordeel.reden in telling:
                telling[oordeel.reden] += 1
        return telling


def beoordeel(context: CheckContext) -> Wegvakuitslag:
    """Het oordeel over elk kandidaat-wegvak, een keer per context berekend.

    Leeg als een van de drie bronnen ontbreekt: zonder wegvakken is er niets te
    beoordelen, zonder bebouwde kom geen kandidaatselectie en zonder wegdelen geen
    onverhard-uitzondering. De check meldt dat zelf; hier is stilte het juiste antwoord.
    """
    return context.cached("ext:wegvakken", lambda: _beoordeel(context))


def _beoordeel(context: CheckContext) -> Wegvakuitslag:
    """Rijgt de vier eenheden aaneen tot een oordeel per wegvak.

    De poort staat hier en niet in `run()`: dan volgen de bevindingen, `examined()`,
    `notes()` én het register uit één beslissing en kunnen zij elkaar niet tegenspreken.
    Zonder begrenzingspolygoon (`bronnen.extent`) geeft geen enkele EXT-check een uitslag
    -- de andere lopen daarvoor via `_selecteer` en `binnen_bereik`, dat bij `extent is
    None` altijd onwaar is. EXT-009 komt daar niet langs, want zijn populatie zijn
    wegvakken en geen GWSW-objecten, dus hij toetst het hier zelf. Zonder die poort meldde
    hij straten naast de zin "er is dus niets getoetst", met `examined = 0` ernaast.
    """
    bronnen = context.bronnen
    if bronnen is None or bronnen.extent is None:
        return Wegvakuitslag()
    nwb = bronnen.layer("nwb_wegvak")
    kom = bronnen.layer("top10nl_kom")
    wegdeel = bronnen.layer("bgt_wegdeel")
    if nwb is None or kom is None or wegdeel is None:
        return Wegvakuitslag()

    drempels = context.config.drempels
    kandidaten = kies_kandidaten(nwb, kom, drempels)
    if not len(kandidaten):
        return Wegvakuitslag(afgevallen=kandidaten.afgevallen, wegvakken_totaal=len(nwb))
    vlakken = bouw_vlakken(kandidaten, drempels)
    kenmerken = meet_kenmerken(kandidaten, vlakken, _riool(context), wegdeel, drempels)
    uitslag = classificeer(kenmerken, drempels)

    return Wegvakuitslag(
        oordelen=tuple(
            Wegvakoordeel(
                sleutel=kandidaten.sleutels[positie],
                straat=kandidaten.straten[positie],
                plaats=kandidaten.plaatsen[positie],
                status=status,
                reden=reden,
                straatlengte_m=float(kandidaten.lengtes[positie]),
                streng_in_cel=float(kenmerken.streng_in_cel[positie]),
                aandeel_onverhard=_of_niets(kenmerken.aandeel_onverhard[positie]),
                middelpunt=kandidaten.middelpunten[positie],
                vlak=vlakken[positie],
                bronbestand=nwb.source.name,
            )
            for positie, (status, reden) in enumerate(uitslag)
        ),
        afgevallen=kandidaten.afgevallen,
        wegvakken_totaal=len(nwb),
    )


def _riool(context: CheckContext) -> Riool:
    """De GWSW-geometrie die EXT-009 leest, als arrays.

    Vier rollen: de vrijvervalstrengen dragen de dekkingsmaat, de putten de
    lus-uitzondering, en de mechanische leidingen plus de pompunits de
    drukriolering-indicatie.
    """
    return Riool(
        vrijverval=_lijnen(vrijvervalrioolleidingen(context)),
        mechanisch=_lijnen(mechanischeleidingen(context)),
        putten=_punten(putten(context)),
        pompen=_punten(pompunits(context)),
    )


def _lijnen(conduits: Sequence[Conduit]) -> np.ndarray:
    """De bruikbare lijngeometrieen van een verbindingsselectie."""
    return np.array(
        [c.line for c in conduits if c.line is not None and not c.line.is_empty], dtype=object
    )


def _punten(nodes: Sequence[Node]) -> np.ndarray:
    """De bruikbare puntgeometrieen van een knoopselectie."""
    return np.array(
        [n.point for n in nodes if n.point is not None and not n.point.is_empty], dtype=object
    )


# --------------------------------------------------------------------------- #
# 1. Kandidaatselectie
# --------------------------------------------------------------------------- #


def kies_kandidaten(nwb: VectorLayer, kom: VectorLayer, drempels: CheckThresholds) -> Kandidaten:
    """De wegvakken waarover deze check een uitspraak doet.

    Vier voorwaarden, in de volgorde waarin ze geteld worden: gemeentelijk beheer
    (`WEGBEHSRT`), geen pad of parkeervak (`BST_CODE`), minstens de minimale lengte, en
    het middelpunt in een TOP10NL-vlak met `bebouwdekom = ja`. Buiten de kom hoort niet
    per se riolering te liggen -- daar zijn IBA's -- en dat is precies waarom de kom de
    grens is en niet de gemeentegrens.

    Op het middelpunt en niet op de hele lijn: een straat die de komgrens kruist hoort
    bij de kom waar haar hart ligt, en die keuze moet er een zijn en niet twee.
    """
    lijnen = np.asarray(nwb.geometries, dtype=object)
    lengtes = shapely.length(lijnen)
    middelpunten = shapely.line_interpolate_point(lijnen, 0.5, normalized=True)

    beheerder = _tekstkolom(nwb, KOLOM_WEGBEHEERDER)
    baansubsoort = _tekstkolom(nwb, KOLOM_BAANSUBSOORT)
    gemeentelijk = beheerder == drempels.ext_wegvak_wegbeheerder
    geen_pad = ~np.isin(baansubsoort, list(drempels.ext_wegvak_uitgesloten_bst))
    lang_genoeg = lengtes >= drempels.ext_wegvak_minimale_lengte_m

    komvlakken, komnamen = _bebouwde_kom(kom)
    komnummer = _eerste_treffer(middelpunten, komvlakken)
    binnen_kom = komnummer >= 0

    kandidaat = gemeentelijk & geen_pad & lang_genoeg & binnen_kom
    index = np.flatnonzero(kandidaat)
    gekozen = komnummer[index]
    return Kandidaten(
        alle_lijnen=lijnen,
        index=index,
        sleutels=_sleutels(nwb, index),
        straten=tuple(_tekstkolom(nwb, KOLOM_STRAATNAAM)[index]),
        plaatsen=tuple(komnamen[nummer] for nummer in gekozen),
        lengtes=lengtes[index],
        middelpunten=middelpunten[index],
        komvlakken=komvlakken[gekozen],
        afgevallen={
            "niet in gemeentelijk beheer": int((~gemeentelijk).sum()),
            "pad, parkeervak of op-/afrit": int((gemeentelijk & ~geen_pad).sum()),
            "korter dan de minimale straatlengte": int(
                (gemeentelijk & geen_pad & ~lang_genoeg).sum()
            ),
            "buiten de bebouwde kom": int(
                (gemeentelijk & geen_pad & lang_genoeg & ~binnen_kom).sum()
            ),
        },
    )


def _bebouwde_kom(kom: VectorLayer) -> tuple[np.ndarray, list[str]]:
    """De TOP10NL-vlakken met `bebouwdekom = ja`, met hun plaatsnaam.

    Een plaatsvlak buiten de kom (buurtschap, gehucht) staat in dezelfde laag; daar
    hoort niet vanzelfsprekend riolering te liggen en het valt dus af.
    """
    vlag = _tekstkolom(kom, KOLOM_BEBOUWDE_KOM)
    namen = _tekstkolom(kom, KOLOM_PLAATSNAAM)
    binnen = np.flatnonzero(np.char.lower(vlag) == WAARDE_BEBOUWDE_KOM)
    return np.asarray(kom.geometries, dtype=object)[binnen], list(namen[binnen])


def _eerste_treffer(punten: np.ndarray, vlakken: np.ndarray) -> np.ndarray:
    """Per punt het eerste vlak waar het in ligt, of -1.

    Vectoriseert wat anders een lus met `sindex`-queries zou zijn: één `STRtree.query`
    over alle punten tegelijk, en `np.unique` kiest per punt de eerste treffer.
    """
    gevonden = np.full(len(punten), -1, dtype=int)
    if not len(vlakken) or not len(punten):
        return gevonden
    paren = STRtree(vlakken).query(punten, predicate="intersects")
    if paren.size:
        uniek, eerste = np.unique(paren[0], return_index=True)
        gevonden[uniek] = paren[1][eerste]
    return gevonden


def _tekstkolom(laag: VectorLayer, naam: str) -> np.ndarray:
    """Een kolom als tekstarray; een ontbrekende kolom of waarde wordt een lege tekst."""
    return np.array([_tekst(waarde) for waarde in laag.kolom(naam)], dtype=object).astype(str)


def _tekst(waarde: object) -> str:
    """Een attribuutwaarde als tekst, zonder de `.0` van een float-geworden geheel getal."""
    if waarde is None:
        return ""
    if isinstance(waarde, float):
        return str(int(waarde)) if waarde.is_integer() else str(waarde)
    return str(waarde).strip()


def _sleutels(nwb: VectorLayer, index: np.ndarray) -> tuple[str, ...]:
    """De sleutel per kandidaat-wegvak: `nwb:wegvak/<WVK_ID>`.

    Een wegvak is geen GWSW-object en heeft dus geen dataset-URI; deze sleutel neemt die
    rol over in de melding, in de laag `vlakken` en in het register. Draagt het extract
    geen `WVK_ID`, dan valt hij terug op de rijpositie -- stabiel binnen een bestand, en
    het alternatief (alle wegvakken op één sleutel) zou ze op een hoop gooien.
    """
    kolom = _tekstkolom(nwb, KOLOM_WEGVAK_ID)
    return tuple(f"nwb:wegvak/{kolom[positie] or positie}" for positie in index)


# --------------------------------------------------------------------------- #
# 2. Voronoi-partitie
# --------------------------------------------------------------------------- #


def bouw_vlakken(kandidaten: Kandidaten, drempels: CheckThresholds) -> np.ndarray:
    """Het straatvlak per kandidaat: zijn voronoi-cel, geknipt op buffer en kom.

    De partitie loopt over alle wegvakken en niet alleen over de kandidaten: elk punt van
    het wegennet hoort bij de straat die er het dichtst bij ligt, ook als die straat zelf
    afviel. Zonder die buren zou een kandidaat het gebied van een parkeerplaats of een
    rijksweg erbij krijgen, en daarmee de riolering die daar ligt.

    De wegvakken worden eerst om de `verdichting` verdicht, zodat de cel de vorm van de
    lijn volgt in plaats van die van twee eindpunten. Junctiepunten die twee wegvakken
    delen worden ontdubbeld -- twee samenvallende punten leveren geen bruikbare cel op --
    en het eerste wegvak in de rij houdt zo'n punt.

    Levert een array met precies één geometrie per kandidaat, in dezelfde volgorde.
    """
    coordinaten, eigenaar = _verdicht(kandidaten.alle_lijnen, drempels.ext_wegvak_verdichting_m)
    buffer_m = drempels.ext_wegvak_buffer_m
    grenzen = shapely.total_bounds(kandidaten.alle_lijnen)
    marge = VORONOI_MARGE * buffer_m
    omhullende = box(grenzen[0] - marge, grenzen[1] - marge, grenzen[2] + marge, grenzen[3] + marge)
    cellen = shapely.get_parts(
        shapely.voronoi_polygons(
            shapely.multipoints(coordinaten), extend_to=omhullende, ordered=True
        )
    )

    # Van wegvaknummer naar plaats in de kandidatenlijst; -1 voor een wegvak dat afviel.
    plek = np.full(len(kandidaten.alle_lijnen), -1, dtype=int)
    plek[kandidaten.index] = np.arange(len(kandidaten))
    doel = plek[eigenaar]
    meedoen = doel >= 0

    # Eerst samenvoegen, dan knippen. Dat is dezelfde uitkomst -- de doorsnede verdeelt
    # zich over een vereniging -- maar aanzienlijk goedkoper: knippen per cel kostte op De
    # Wolden en Hoogeveen ruim 50.000 vlak-vlak-doorsnedes (5,3 s van de 11), en per
    # kandidaat zijn het er 4116. De cellen zijn ook onafgeknipt klein, want de punten
    # liggen maar `verdichting` meter uit elkaar.
    vlakken = _voeg_samen(cellen[meedoen], doel[meedoen], len(kandidaten))
    knipvormen = shapely.intersection(
        shapely.buffer(kandidaten.lijnen, buffer_m, cap_style="flat"), kandidaten.komvlakken
    )
    return _alleen_vlakken(shapely.intersection(vlakken, knipvormen))


def _alleen_vlakken(geometrieen: np.ndarray) -> np.ndarray:
    """Houdt van elke geometrie het vlakdeel over.

    Twee elkaar rakende vlakken kunnen een doorsnede opleveren waar een lijn- of
    puntrestje aan hangt, en dan is de uitkomst een `GeometryCollection` die niet als
    MULTIPOLYGON weg te schrijven is. `buffer(0)` snijdt die restjes eraf; hij draait
    alleen op de handvol geometrieen waar dat nodig is, want op een vlak is hij niet gratis.
    """
    soorten = shapely.get_type_id(geometrieen)
    gemengd = ~np.isin(soorten, (shapely.GeometryType.POLYGON, shapely.GeometryType.MULTIPOLYGON))
    if gemengd.any():
        geometrieen[gemengd] = shapely.buffer(geometrieen[gemengd], 0)
    return geometrieen


def _verdicht(lijnen: np.ndarray, afstand: float) -> tuple[np.ndarray, np.ndarray]:
    """De verdichte punten van alle lijnen, ontdubbeld, met hun wegvaknummer.

    Vectorisatie in plaats van een lus per lijn: het aantal punten per lijn volgt uit
    haar lengte, `np.repeat` maakt daar één lange rij van, en `line_interpolate_point`
    doet alle interpolaties in één aanroep. Op De Wolden en Hoogeveen zijn dat ruim
    honderdduizend punten.
    """
    lengtes = shapely.length(lijnen)
    aantallen = np.maximum(2, (lengtes // afstand).astype(int) + 1)
    volgnummer = np.arange(aantallen.sum()) - np.repeat(
        np.concatenate(([0], np.cumsum(aantallen)[:-1])), aantallen
    )
    fracties = volgnummer / np.repeat(aantallen - 1, aantallen)
    punten = shapely.line_interpolate_point(np.repeat(lijnen, aantallen), fracties, normalized=True)
    eigenaar = np.repeat(np.arange(len(lijnen)), aantallen)

    coordinaten = shapely.get_coordinates(punten)
    # Op een decimeter afgerond ontdubbeld: twee wegvakken die op een kruising eindigen
    # leveren daar hetzelfde punt op, en dat geeft geen bruikbare voronoi-cel.
    _, eerste = np.unique(np.round(coordinaten, 1), axis=0, return_index=True)
    eerste.sort()
    return coordinaten[eerste], eigenaar[eerste]


def _voeg_samen(delen: np.ndarray, groep: np.ndarray, aantal: int) -> np.ndarray:
    """Voegt de geometrieen per groep samen tot één vlak per groep.

    De groepen zijn ongelijk van lengte, dus dit is de ene plek waar er per kandidaat een
    aanroep staat; alles binnen die aanroep gebeurt in C. `np.argsort` plus
    `np.searchsorted` maakt er aaneengesloten plakken van, zodat er geen woordenboek van
    lijsten aan te pas komt.
    """
    vlakken = np.array([shapely.Polygon()] * aantal, dtype=object)
    volgorde = np.argsort(groep, kind="stable")
    gesorteerd = groep[volgorde]
    randen = np.searchsorted(gesorteerd, np.arange(aantal + 1))
    gerangschikt = delen[volgorde]
    for nummer in range(aantal):
        plak = gerangschikt[randen[nummer] : randen[nummer + 1]]
        if len(plak):
            vlakken[nummer] = shapely.union_all(plak)
    return vlakken


# --------------------------------------------------------------------------- #
# 3. Kenmerken tegen de riolering en het wegdek
# --------------------------------------------------------------------------- #


def meet_kenmerken(
    kandidaten: Kandidaten,
    vlakken: np.ndarray,
    riool: Riool,
    wegdeel: VectorLayer,
    drempels: CheckThresholds,
) -> Kenmerken:
    """Meet per kandidaat wat er in en langs zijn straatvlak ligt.

    `streng_in_cel` is de dragende maat: de lengte vrijvervalstreng binnen de eigen
    voronoi-cel, gedeeld door de straatlengte. Hij deelt door de straat en niet door de
    cel, zodat een lange straat met een kort stukje riool laag uitkomt.

    De drie andere maten dienen de uitzonderingen: een put in de eigen cel (een lus- of
    hoefijzerweg waar het riool door de as loopt), een pompunit vlakbij of persleiding
    langs de straat (drukriolering), en het aandeel onverhard wegdek (buiten scope).
    """
    lengtes = np.where(kandidaten.lengtes > 0, kandidaten.lengtes, 1.0)
    corridors = shapely.buffer(kandidaten.lijnen, drempels.ext_wegvak_corridor_m, cap_style="flat")
    return Kenmerken(
        streng_in_cel=_lengte_in(vlakken, riool.vrijverval) / lengtes,
        put_in_cel=_bevat(vlakken, riool.putten),
        persleiding_langs=_lengte_in(corridors, riool.mechanisch) / lengtes,
        pomp_nabij=_nabij(kandidaten.lijnen, riool.pompen, drempels.ext_wegvak_pomp_afstand_m),
        aandeel_onverhard=_onverhard(kandidaten.lijnen, wegdeel, drempels),
    )


def _lengte_in(vlakken: np.ndarray, lijnen: np.ndarray) -> np.ndarray:
    """Per vlak de totale lengte van de lijnen erbinnen."""
    totaal = np.zeros(len(vlakken))
    if not len(lijnen):
        return totaal
    paren = STRtree(lijnen).query(vlakken, predicate="intersects")
    if not paren.size:
        return totaal
    stukken = shapely.intersection(vlakken[paren[0]], lijnen[paren[1]])
    return np.bincount(paren[0], weights=shapely.length(stukken), minlength=len(vlakken))


def _bevat(vlakken: np.ndarray, punten: np.ndarray) -> np.ndarray:
    """Per vlak of er minstens een van de punten in ligt."""
    gevonden = np.zeros(len(vlakken), dtype=bool)
    if not len(punten):
        return gevonden
    paren = STRtree(punten).query(vlakken, predicate="contains")
    if paren.size:
        gevonden[paren[0]] = True
    return gevonden


def _nabij(lijnen: np.ndarray, punten: np.ndarray, afstand: float) -> np.ndarray:
    """Per lijn of er een punt binnen deze afstand ligt."""
    gevonden = np.zeros(len(lijnen), dtype=bool)
    if not len(punten):
        return gevonden
    paren = STRtree(punten).query(lijnen, predicate="dwithin", distance=afstand)
    if paren.size:
        gevonden[paren[0]] = True
    return gevonden


def _onverhard(lijnen: np.ndarray, wegdeel: VectorLayer, drempels: CheckThresholds) -> np.ndarray:
    """Per straat het aandeel onverhard wegdek, of NaN als er geen wegdeel naast ligt.

    Gemeten op oppervlak binnen een smalle strook om de hartlijn: dat is het wegdek zelf
    en niet de berm ernaast. Een wegdeel zonder `plus_fysiek_voorkomen` telt als verhard;
    dat is de behoudende kant, want het levert minder grijze straten op.
    """
    aandeel = np.full(len(lijnen), np.nan)
    vlakken = np.asarray(wegdeel.geometries, dtype=object)
    if not len(vlakken):
        return aandeel
    onverhard = np.isin(
        np.char.lower(_tekstkolom(wegdeel, KOLOM_WEGDEK)),
        [waarde.lower() for waarde in drempels.ext_wegvak_onverhard_wegdek],
    )
    stroken = shapely.buffer(lijnen, drempels.ext_wegvak_wegdek_buffer_m)
    paren = STRtree(vlakken).query(stroken, predicate="intersects")
    if not paren.size:
        return aandeel
    oppervlak = shapely.area(shapely.intersection(stroken[paren[0]], vlakken[paren[1]]))
    totaal = np.bincount(paren[0], weights=oppervlak, minlength=len(lijnen))
    deel = np.bincount(paren[0], weights=oppervlak * onverhard[paren[1]], minlength=len(lijnen))
    gemeten = totaal > 0
    aandeel[gemeten] = deel[gemeten] / totaal[gemeten]
    return aandeel


# --------------------------------------------------------------------------- #
# 4. De classificatieregel
# --------------------------------------------------------------------------- #


def classificeer(kenmerken: Kenmerken, drempels: CheckThresholds) -> tuple[tuple[str, str], ...]:
    """De status en de reden per kandidaat, in vier stappen.

    1. Overwegend onverhard wegdek: **niet beoordeeld**. Een zandweg in de kom hoort
       niet vanzelfsprekend riolering te hebben; het model is voor vrijverval-kernstraten
       gemaakt.
    2. Riolering aangetoond: **bediend**. Dat is `streng_in_cel` boven de drempel, of --
       de lus- en hoefijzeruitzondering -- een put in de eigen cel. Ligt de put daarin,
       dan loopt het riool door de as van de straat en zegt de lijnafstand niets meer.
    3. Anders, in het **onzekere middengebied** mét drukriolering-indicatie: **niet
       beoordeeld**. Een pompunit binnen de pompafstand of persleiding langs meer dan het
       gegeven aandeel van de straat betekent dat hier geen vrijverval hóéft te liggen.
       Twee grenzen aan die uitzondering, en beide doen ertoe. Zij geldt alleen ná stap 2
       -- een straat waar wél genoeg vrijverval ligt hoeft niet uitgezonderd te worden --
       en alleen waar er *iets* in de eigen cel ligt: een straat met nul meter
       vrijvervalstreng is niet onzeker, die is meetbaar leeg. Zonder die tweede grens
       verdween op De Wolden en Hoogeveen 31 van de 34 grijs geworden gelabelde straten
       als een terecht gemeld gat uit beeld; mét die grens zijn het er 4. Zie BO-81.
    4. Anders: **geen riolering** -- een waarschuwing.
    """
    onverhard = kenmerken.aandeel_onverhard > drempels.ext_wegvak_onverhard_aandeel
    bediend = kenmerken.put_in_cel | (kenmerken.streng_in_cel >= drempels.ext_wegvak_streng_in_cel)
    drukriolering = kenmerken.pomp_nabij | (
        kenmerken.persleiding_langs > drempels.ext_wegvak_persleiding_aandeel
    )
    onzeker = drukriolering & (kenmerken.streng_in_cel > 0)
    niet_beoordeeld = onverhard | (~bediend & onzeker)
    status = np.where(niet_beoordeeld, STATUS_GRIJS, np.where(bediend, STATUS_GROEN, STATUS_ROOD))
    reden = np.where(onverhard, REDEN_ONVERHARD, np.where(niet_beoordeeld, REDEN_DRUKRIOLERING, ""))
    return tuple(zip(status.tolist(), reden.tolist(), strict=True))


def _of_niets(waarde: float) -> float | None:
    """Een gemeten aandeel, of None als er niets te meten viel."""
    return None if np.isnan(waarde) else float(waarde)
