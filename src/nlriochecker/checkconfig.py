"""Inlezen en valideren van de projectconfiguratie voor de check-engine."""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from nlriochecker.errors import ConfigError

DEFAULT_CHECK_CONFIG_NAME = "checks.toml"

# De kenmerken waarop `markeer_vulwaarden` werkt: precies de vier velden die zij
# inspecteert (KLASSE_MAAIVELDHOOGTE, KLASSE_PUTDEKSELNIVEAU, KLASSE_BOB_BEGIN en
# KLASSE_BOB_EIND). Een andere naam in `[vulwaarden] hoogte_kenmerken` -- een tikfout,
# of een kenmerk dat de pijplijn niet inleest -- zou stil niets doen terwijl ATTR-013
# meldt dat de regel is toegepast; `VulwaardeOptions` hieronder weigert hem daarom.
# De lijst hoort bij de afnemer: `gwsw_orox_helpers.markeer_vulwaarden` neemt de
# kenmerken als parameter en kent deze keuze niet.
VULWAARDE_KENMERKEN: frozenset[str] = frozenset(
    {"Maaiveldhoogte", "Putdekselniveau", "BobBeginpuntLeiding", "BobEindpuntLeiding"}
)

# De Wolden-export: cp850-vervuiling in de aanlevering; zie de spec van gwsw-orox-helpers.
FALLBACK_ENCODING = "cp850"


class ClassRoots(BaseModel):
    """Wortelklassen per rol; de subklassen volgen uit de ontologie."""

    model_config = ConfigDict(extra="forbid")

    put: list[str] = Field(min_length=1)
    # Issue #64: de putten met een verwijderbare deksel (`gwsw:Rioolput`). Enger dan
    # `put`: de dekselchecks (putdiepte, putbodem) horen hier, niet op elke Put en niet op
    # een gemaal. De ontologie definieert Rioolput als "een put met een verwijderbare
    # deksel"; alleen daaraan hangen `Putdekselniveau` en de putdiepte betekenis.
    rioolput: list[str] = Field(default_factory=lambda: ["Rioolput"])
    vrijvervalleiding: list[str] = Field(min_length=1)
    # TOP-006, TOP-010 en TOP-011: de leidingen waarvan de onderlinge ligging getoetst
    # wordt. Ruimer dan `vrijvervalleiding` (een duiker hoort erbij) en enger dan `streng`
    # (drains, mechanische leidingen en aansluitleidingen horen er niet bij). De grens
    # komt uit de ontologie en niet uit een projectkeuze, dus een gevulde default -- zoals
    # bij `rioolput` en `waterlozingspunt`. Zie issue #82 en BO-69.
    nabijheidsleiding: list[str] = Field(
        default_factory=lambda: ["VrijvervalRioolleiding", "Duiker"]
    )
    # TOP-001 vraagt of er *enige* streng aansluit, niet of er een vrijvervalstreng
    # aansluit; een put aan een persleiding is niet losliggend.
    streng: list[str] = Field(default_factory=lambda: ["Leiding"])
    # Mechanisch riool: buiten scope voor de checks, wel zichtbaar in de GIS-uitvoer.
    mechanisch: list[str] = Field(default_factory=list)
    # TOP-022 en TOP-023: hulpstukken (T-stuk, kruisstuk, mof, afsluitstuk, ...). Een
    # hulpstuk is een knoop maar geen put; het verwachte aantal leidingen komt uit de
    # functierestrictie in de ontologie, niet uit deze lijst.
    hulpstuk: list[str] = Field(default_factory=list)
    # NET-001 en NET-002 vragen elk om een ander soort eindpunt; een vuilwaterstreng
    # die alleen een uitlaat bereikt is niet in orde.
    afvoer_eindpunt: list[str] = Field(default_factory=list)
    lozings_eindpunt: list[str] = Field(default_factory=list)
    # EXT-007: de lozingspunten die volgens de GWSW-ontologie op oppervlaktewater lozen.
    # Enger dan `lozings_eindpunt`, en met opzet: die bredere lijst blijft het
    # netwerkeindpunt van NET-001/002/008. De drie wortels komen uit de ontologie, niet uit
    # een projectkeuze -- vandaar een gevulde default, zoals bij `rioolput`. Zie BO-67.
    waterlozingspunt: list[str] = Field(
        default_factory=lambda: ["Uitlaatconstructie", "UitlaatPunt", "LozingspuntOppervlaktewater"]
    )
    vuilwater: list[str] = Field(default_factory=list)
    hemelwater: list[str] = Field(default_factory=list)
    infiltratie: list[str] = Field(default_factory=list)
    drempel: list[str] = Field(default_factory=list)
    # TOP-019: knopen die alleen twee strengen aan elkaar knopen zonder eigen functie.
    functieloze_knoop: list[str] = Field(default_factory=list)
    # ADM-006: klassen die aangeven dat een object vervallen of nog gepland is.
    # De status zelf komt uit Begindatum en Einddatum; deze lijst is voor
    # datasets die er een eigen klasse voor gebruiken.
    vervallen: list[str] = Field(default_factory=list)
    # ADM-010: leidingen die buiten gebruik zijn maar nog in de ondergrond
    # liggen. LozeLeiding hangt onder Leiding, niet onder VrijvervalRioolleiding, en
    # dekt GedammerdeLeiding, Uitlegger, VolgeschuimdeLeiding en VolgezandeLeiding.
    loze_leiding: list[str] = Field(default_factory=list)
    # RVZ: hoe overstorten en bergbezinkvoorzieningen in de export verschijnen.
    overstortput: list[str] = Field(default_factory=list)
    overstortleiding: list[str] = Field(default_factory=list)
    bergbezinkvoorziening: list[str] = Field(default_factory=list)
    # Bergbezinkriolen zijn leidingen en geen bouwwerken; ze horen niet in de
    # knopenrol maar moeten wel geteld en gemeld worden.
    bergbezinkleiding: list[str] = Field(default_factory=list)
    ledigingsvoorziening: list[str] = Field(default_factory=list)
    oppervlaktewater: list[str] = Field(default_factory=list)
    valconstructie: list[str] = Field(default_factory=list)
    # EXT-003: klassen die een kruising met een watergang verklaren.
    kruisingsleiding: list[str] = Field(default_factory=list)
    # Prioriteit 1 in de GIS-uitvoer: een fout op deze klassen weegt het zwaarst.
    kritiek: list[str] = Field(default_factory=list)
    # NET-005 en NET-006: welke leidingklassen tot welk stelseltype horen.
    stelseltypen: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _pompunit_heeft_een_uitweg(self) -> Self:
        """Zonder persnet mag `Pompunit` niet uit `afvoer_eindpunt` verdwijnen (BO-55).

        Een pompput is een overdrachtspunt naar de drukriolering: de streng die erop
        eindigt voert af langs het persnet naar het gemaal erachter.
        `checks/verbanden._bouw_bereikbaarheid` legt die route alleen als `mechanisch`
        klassen noemt, en `afbakening._componentstructuur` neemt hem alleen dan in de
        contextschil op. Is die lijst leeg terwijl `Pompunit` geen eindpunt meer is, dan
        meldt NET-001 elke vrijvervalstreng die op een pompput uitkomt als
        onbereikbaar -- op De Wolden en Hoogeveen 645 valse bevindingen. Precies daarom
        wachtte issue #73 op #72.

        Deze poort hoort hier en niet bij de nul-bewaking: `load_check_config` valideert
        een projectbestand op zichzelf en legt het niet over `checks.toml` heen, dus een
        weggelaten `mechanisch` levert een lege lijst op, en een rol zonder klassen valt
        uit de rollentelling weg (BO-52) in plaats van een signaal te geven.

        Een lege `afvoer_eindpunt` valt erbuiten: dan is er in het geheel geen
        afvoereindpunt en is de uitkomst van NET-001 meteen zichtbaar iets anders. Dat is
        een eigen toestand, geen pompput zonder uitweg.
        """
        if self.afvoer_eindpunt and not self.mechanisch and "Pompunit" not in self.afvoer_eindpunt:
            raise ValueError(
                "[klassen] afvoer_eindpunt noemt geen 'Pompunit' terwijl [klassen] "
                "mechanisch leeg is. Een pompput is dan geen afvoereindpunt en er is geen "
                "persnet om achterlangs een gemaal te bereiken, zodat NET-001 elke "
                "vrijvervalstreng op een pompput als onbereikbaar meldt. Noem de "
                "mechanische leidingklassen in 'mechanisch' (aanbevolen), of houd "
                "'Pompunit' in 'afvoer_eindpunt' zoals voor issue #73. Zie BO-55."
            )
        return self

    @property
    def netwerkknopen(self) -> list[str]:
        """De klassen die als knooppunt in de netwerkgraaf meetellen.

        Bergbezinkvoorzieningen horen erbij: een BBB is in het GWSW een Bouwwerk en
        geen Put, maar het water loopt er wel doorheen. Zonder die klassen zou elke
        streng die op een BBB uitkomt als niet-aangesloten gelden.
        """
        return [
            *self.put,
            *self.afvoer_eindpunt,
            *self.lozings_eindpunt,
            *self.bergbezinkvoorziening,
        ]

    def stelseltype(self, dataset_types: frozenset[str], closure) -> str | None:
        """Het stelseltype waar deze leidingklassen onder vallen, of None."""
        for naam in sorted(self.stelseltypen):
            for wortel in self.stelseltypen[naam]:
                if dataset_types & closure(wortel):
                    return naam
        return None


class PutTypeRule(BaseModel):
    """ADM-007: welke leiding- of onderdeelklasse bij een puttype hoort."""

    model_config = ConfigDict(extra="forbid")

    puttype: str
    vereist_een_van: list[str] = Field(min_length=1)
    toelichting: str = ""


class VerhangStap(BaseModel):
    """HGT-007: één trede van de verhangstaffel per diameter.

    `tot_diameter_mm` is de bovengrens (inclusief) van de trede in millimeters;
    `None` is de vangnettrede zonder bovengrens. `minimaal_verhang_een_op` is het
    minimale afschot als noemer van 1:n, dus 250 betekent 1:250.
    """

    model_config = ConfigDict(extra="forbid")

    tot_diameter_mm: float | None = Field(default=None, gt=0.0)
    minimaal_verhang_een_op: float = Field(gt=0.0)


class CheckThresholds(BaseModel):
    """Configureerbare drempelwaarden van de checks."""

    model_config = ConfigDict(extra="forbid")

    snapping_tolerantie_m: float = Field(default=0.10, gt=0.0)
    dubbele_put_tolerantie_m: float = Field(default=0.30, gt=0.0)

    # TOP-006: hoeveel twee strengen mogen afwijken en hoe lang ze moeten samenvallen.
    # 2 cm over 2 m vangt het echte duplicaat; legitiem parallelle buizen vallen erbuiten
    # en blijven zichtbaar via TOP-010 en TOP-013. Zie BO-70.
    overlap_tolerantie_m: float = Field(default=0.02, gt=0.0)
    overlap_minimale_lengte_m: float = Field(default=2.0, gt=0.0)
    # TOP-007: onder deze lengte geldt een streng als nul-lengte.
    nul_lengte_m: float = Field(default=0.01, gt=0.0)
    # TOP-008: hoe ver de hartlijn van de rechte put-putverbinding mag afwijken.
    rechtheid_afwijking_m: float = Field(default=0.50, gt=0.0)
    # TOP-009: het geldige RD-bereik (EPSG:28992) in meters.
    rd_x_min: float = 0.0
    rd_x_max: float = 300_000.0
    rd_y_min: float = 300_000.0
    rd_y_max: float = 630_000.0
    # TOP-010: extra marge bovenop de halve diameter van beide strengen. Blijft 0,0:
    # de marge discrimineert niet, het plausibel/terecht-onderscheid zit in de hoogte.
    # Zie BO-70.
    diameterbuffer_marge_m: float = Field(default=0.0, ge=0.0)
    # TOP-013 en TOP-014: aantallen waarboven het onaannemelijk wordt.
    parallelle_strengen_maximum: int = Field(default=2, ge=1)
    aansluitende_strengen_maximum: int = Field(default=4, ge=1)
    # TOP-018: wanneer twee vertices als dubbel gelden en wanneer een hoek een spike is.
    dubbele_vertex_tolerantie_m: float = Field(default=0.01, gt=0.0)
    spike_hoek_graden: float = Field(default=5.0, gt=0.0, le=180.0)
    # TOP-021: hoe dicht een put bij een doorlopende streng mag liggen.
    put_op_streng_tolerantie_m: float = Field(default=0.50, gt=0.0)

    # ATTR-002: de ondergrens staat per stelseltype in `plausibiliteit.toml`
    # (`[[minimale_diameter]]`), niet als losse drempel -- ze draagt een bron per regel.
    # ATTR-005: eenheidsfout binnen bereik; een diameter onder deze waarde in
    # combinatie met een deelbaar-door-tien-patroon wijst op centimeters.
    eenheidsverdenking_diameter_mm: float = Field(default=100.0, gt=0.0)
    # ATTR-006: hoeveel de strengdiameter de putafmeting mag overschrijden.
    put_diameter_marge_mm: float = Field(default=0.0, ge=0.0)
    # ATTR-007: geldig bereik voor de begindatum (aanlegdatum).
    begindatum_minimum: int = Field(default=1870, ge=1)
    # ATTR-007: bovengrens van de begindatum. None betekent het huidige jaar
    # (`date.today().year`); een vast jaar maakt een run reproduceerbaar, los van
    # wanneer hij draait.
    begindatum_maximum: int | None = Field(default=None, ge=1)
    # ATTR-015: signaalwaarde, geen norm. Draagt een enkel jaartal meer dan dit
    # aandeel van de gedateerde objecten, dan ruikt dat naar een vulwaarde.
    begindatum_vulwaarde_aandeel: float = Field(default=0.20, gt=0.0, le=1.0)
    # ATTR-015: onder zoveel gedateerde objecten zegt een aandeel niets; dan zwijgt
    # de detector.
    begindatum_vulwaarde_minimum_objecten: int = Field(default=30, ge=1)
    # Aannemelijk bereik voor de strenglengte; de grenzen volgen het GWSW-datatype
    # Dt_LengteLeiding (1-75 m). Zie checks.toml en issue #35. Geen check leest ze
    # meer: ATTR-008 is met issue #90 geschrapt omdat de nulmetingvorm
    # LengteLeiding_val exact dit bereik toetst (BO-61).
    minimale_strenglengte_m: float = Field(default=1.0, gt=0.0)
    maximale_strenglengte_m: float = Field(default=75.0, gt=0.0)
    # ATTR-009: toegestane afwijking tussen geometrische en administratieve lengte.
    lengte_afwijking_procent: float = Field(default=5.0, gt=0.0)
    # ATTR-004: hoeveel breedte en hoogte bij een rond profiel mogen verschillen.
    rondheid_tolerantie_mm: float = Field(default=0.0, ge=0.0)
    # ATTR-017: de kandidaat-schalen waarmee de wandruwheid gelezen kan worden. Het
    # GWSW-datatype `Dt_Wandruwheid` is een geheel getal in mm (0-99) en kan de
    # kunststofwaarden uit C2100 niet uitdrukken, dus een export noteert de waarde soms
    # in tienden van een mm. ATTR-017 kiest de schaal die de minste afwijkingen oplevert;
    # met een tweede kandidaat blijft ook een export in hele mm goed getoetst. Zie BO-39.
    wandruwheid_schalen: list[float] = Field(default_factory=lambda: [1.0, 10.0], min_length=1)

    @field_validator("wandruwheid_schalen")
    @classmethod
    def _positieve_schalen(cls, schalen: list[float]) -> list[float]:
        """Weigert een schaalfactor van nul of minder; erdoor delen zou onzin geven."""
        if any(schaal <= 0 for schaal in schalen):
            raise ValueError("wandruwheid_schalen moet uit positieve getallen bestaan")
        return schalen

    # HGT-001 en HGT-002: afwijking van het maaiveld ten opzichte van het AHN.
    ahn_afwijking_waarschuwing_m: float = Field(default=0.10, gt=0.0)
    ahn_afwijking_fout_m: float = Field(default=0.25, gt=0.0)
    # HGT-003: hoe diep een BOB onder het AHN-maaiveld mag liggen. 4,0 m = de
    # ontwerpnorm voor nieuw gebied (3,0 m, PvE Rotterdam) plus marge voor bestaand
    # gebied; een landelijke maximumnorm bestaat niet. Zie BO-68.
    bob_maximale_diepte_m: float = Field(default=4.0, gt=0.0)
    # HGT-005 en HGT-006: tegenverhang licht en fors, in meter over de streng.
    tegenverhang_licht_m: float = Field(default=0.01, gt=0.0)
    tegenverhang_fors_m: float = Field(default=0.05, gt=0.0)
    # HGT-008: steiler dan een op zoveel is verdacht.
    extreem_verhang_een_op: float = Field(default=50.0, gt=0.0)
    # HGT-009 en HGT-016: BOB-sprong waarboven een valconstructie verwacht wordt.
    bob_sprong_m: float = Field(default=0.25, gt=0.0)
    # HGT-012: aannemelijk bereik voor de putdiepte; de grenzen volgen het
    # GWSW-datatype Dt_HoogtePut (500-4000 mm). Zie checks.toml en issue #35.
    minimale_putdiepte_m: float = Field(default=0.5, gt=0.0)
    maximale_putdiepte_m: float = Field(default=4.0, gt=0.0)
    # HGT-013: gronddekking op de buiskruin.
    minimale_gronddekking_m: float = Field(default=0.50, gt=0.0)
    maximale_gronddekking_m: float = Field(default=4.0, gt=0.0)
    # HGT-014: hoeveel het leidingverhang van het maaiveldverloop mag afwijken.
    maaiveldvolging_afwijking_m: float = Field(default=1.0, gt=0.0)
    # HGT-015: marge van het putbodemniveau ten opzichte van de laagste BOB.
    putbodem_boven_bob_m: float = Field(default=0.05, gt=0.0)
    putbodem_zonk_m: float = Field(default=0.50, gt=0.0)
    # HGT-017: afwijking tussen de z-waarde uit de geometrie en de administratie.
    z_afwijking_m: float = Field(default=0.05, gt=0.0)

    # RVZ-004: afstand tot ontvangend oppervlaktewater.
    overstort_water_afstand_m: float = Field(default=25.0, gt=0.0)
    # RVZ-011: minimale waking van de overstortdrempel.
    minimale_waking_m: float = Field(default=0.40, gt=0.0)
    # NET-008: wanneer een deelstelsel klein heet en hoeveel lozingspunten opvallen.
    klein_deelstelsel_knopen: int = Field(default=25, ge=1)
    lozingspunten_per_deelstelsel: int = Field(default=2, ge=1)

    # BTR-003: leeftijd van de inwinning per grondsoort, in jaren.
    inwinning_maximale_leeftijd_jaar: int = Field(default=40, ge=1)
    # BTR-004: geldig bereik van de grondwaterstand ten opzichte van maaiveld.
    grondwater_maximale_diepte_m: float = Field(default=5.0, gt=0.0)
    # BTR-006: raster waarop afronding gemeten wordt, en het aandeel waarboven het
    # cluster als systematisch geldt.
    afronding_raster_m: float = Field(default=0.05, gt=0.0)
    afronding_aandeel_procent: float = Field(default=80.0, gt=0.0, le=100.0)
    afronding_minimum_waarnemingen: int = Field(default=30, ge=1)

    # EXT-checks: bufferafstanden tot de externe bronnen.
    ext_pand_buffer_m: float = Field(default=1.0, ge=0.0)
    ext_watergang_buffer_m: float = Field(default=1.0, ge=0.0)
    # Geen check leest deze afstand meer: EXT-005 en EXT-006 zijn met issue #95
    # vervallen (BO-64 en BO-65). De sleutel blijft staan, en `ext_zoekafstand_max_m`
    # telt hem nog mee.
    ext_putdeksel_afstand_m: float = Field(default=2.0, gt=0.0)
    ext_lozingspunt_water_afstand_m: float = Field(default=10.0, gt=0.0)
    ext_perceel_buffer_m: float = Field(default=1.0, ge=0.0)

    # #75: bufferafstand om de strengen van een gemengd deelstelsel, voor de
    # cartografische RVZ-006-vlakken in de laag `vlakken` van de GeoPackage (#98). Geen
    # check-drempel; alleen de kaartlaag leest hem. De sleutel houdt zijn naam: hij staat
    # in elke projectconfig en `extra="forbid"` weigert een onbekende.
    gemengd_zonder_overstort_buffer_m: float = Field(default=10.0, gt=0.0)

    @property
    def ext_zoekafstand_max_m(self) -> float:
        """De verste blik van de EXT-checks in de externe lagen.

        De dekkingspoort verruimt het bereik van de bronnen hiermee: een pand net
        buiten dat bereik telt mee voor een object er net binnen. Bewust niet de
        contextschil uit `[studiegebied]` -- die hoort bij de afbakening van de
        GWSW-analyse en niet bij het zoekbereik in de externe lagen.
        """
        return max(
            self.ext_pand_buffer_m,
            self.ext_watergang_buffer_m,
            self.ext_putdeksel_afstand_m,
            self.ext_lozingspunt_water_afstand_m,
            self.ext_perceel_buffer_m,
        )


class NetworkOptions(BaseModel):
    """Keuzes voor de netwerkanalyse."""

    model_config = ConfigDict(extra="forbid")

    # 'administratief' volgt de van-naar-richting uit het GWSW-model, zoals het
    # register bedoelt; NET-003 toetst juist of die richting klopt. 'bob' leidt de
    # richting af uit het bodemverloop en valt terug op de administratieve richting
    # als een BOB ontbreekt of beide gelijk zijn.
    richting: Literal["administratief", "bob"] = "administratief"


class StudyAreaOptions(BaseModel):
    """Hoe de analyse wordt afgebakend als er een studiegebied is opgegeven."""

    model_config = ConfigDict(extra="forbid")

    # Hoe ver om het gebied heen objecten meedoen die geen netwerkverband met de
    # kern hebben. Nodig voor TOP-005, TOP-006, TOP-010, TOP-011, TOP-021 en de
    # EXT-checks, die naar buren kijken zonder de graaf te volgen.
    context_buffer_m: float = Field(default=50.0, ge=0.0)
    # Checks die over de hele populatie gaan in plaats van over losse objecten; die
    # draaien altijd op de volledige export.
    volledige_dataset_checks: list[str] = Field(default_factory=lambda: ["ADM-002"])
    # Boven dit aandeel van de dataset levert de afbakening zo weinig op dat de run
    # dat meldt. Een mededeling, geen fout.
    component_waarschuwingsdrempel: float = Field(default=0.5, gt=0.0, le=1.0)


class NulmetingOptions(BaseModel):
    """Eisen aan de aangeleverde nulmeting."""

    model_config = ConfigDict(extra="forbid")

    # Het checkregister eist dat de dataset aan alle conformiteitsklassen getoetst is;
    # welke dat zijn, hangt af van wat de GWSW-server aanbiedt. Bewust zonder default:
    # de lijst hoort in checks.toml te staan en nergens anders. Een default hier zou
    # hem een tweede keer opschrijven en een config die de sectie mist onzichtbaar
    # laten terugvallen -- wat sinds `--cfk` zwaarder weegt, want deze lijst bepaalt
    # ook welke klassen die optie accepteert.
    vereiste_cfk: list[str] = Field(min_length=1)


class InwinningOptions(BaseModel):
    """Hoe de inwinningsmetagegevens van deze bronexport gelezen moeten worden.

    Welke waarden in `WijzeVanInwinning` voorkomen verschilt per bronsysteem, en de
    betekenis ervan is een projectafspraak. De GWSW-ontologie zet ze alle in een
    collectie zonder onderscheid, dus de code kan het niet zelf afleiden.
    """

    model_config = ConfigDict(extra="forbid")

    # HGT-001 en HGT-002 vergelijken de geregistreerde hoogte met een AHN-raster.
    # Is die hoogte zelf uit een hoogtemodel afgeleid, dan vergelijkt de check twee
    # modellen met elkaar en is een afwijking geen fout in de beheerdata. Een lege
    # lijst zet die kanttekening uit.
    uit_hoogtemodel: list[str] = Field(default_factory=list)
    # Waarden die "onbekend" zeggen zonder het kenmerk leeg te laten. Ze passeren
    # elke kardinaliteits- en collectietoets maar dragen geen informatie.
    onbekend: list[str] = Field(default_factory=list)


class VulwaardeOptions(BaseModel):
    """Welke hoogtekenmerken een vulwaarde rond 0 m NAP kunnen dragen.

    Sommige bronsystemen schrijven 0,000 als "niet geregistreerd" in plaats van het
    kenmerk leeg te laten. Dat is per project te beoordelen: in laag Nederland kan
    0,00 m NAP een echte meting zijn. Een lege lijst zet de leesregel uit.
    """

    model_config = ConfigDict(extra="forbid")

    # De kenmerken (korte GWSW-naam, zoals `Aspect.kind`) waarop de leesregel werkt.
    hoogte_kenmerken: list[str] = Field(default_factory=list)
    # |waarde| kleiner dan of gelijk aan deze band telt als vulwaarde. De bovengrens is
    # geen drempel maar een invoertoets: een halve meter is als vulwaardeband al veel
    # ruimer dan enig project nodig heeft (De Wolden en Hoogeveen komt uit op 0,01),
    # en wie de eenheid
    # mist en centimeters of millimeters invult (1 of 10 in plaats van 0,01) leest zonder
    # die grens elke BOB en elke maaiveldhoogte als ontbrekend: dertien checks vallen dan
    # stil en ATTR-013 meldt elk object dat een hoogte draagt.
    hoogte_band_m: float = Field(default=0.01, ge=0.0, le=0.5)

    @field_validator("hoogte_kenmerken")
    @classmethod
    def _bekende_kenmerken(cls, kenmerken: list[str]) -> list[str]:
        """Weigert een kenmerk waarop de leesregel niet werkt.

        `markeer_vulwaarden` kijkt naar vier velden. Een naam die daar niet bij hoort,
        of dezelfde naam met ander hoofdlettergebruik, doet stil niets terwijl ATTR-013
        in haar toelichting meldt dat de regel op dat kenmerk gold.
        """
        onbekend = [kenmerk for kenmerk in kenmerken if kenmerk not in VULWAARDE_KENMERKEN]
        if onbekend:
            raise ValueError(
                f"hoogte_kenmerken kent {', '.join(onbekend)} niet; de leesregel werkt "
                f"alleen op {', '.join(sorted(VULWAARDE_KENMERKEN))}"
            )
        return kenmerken


class NamingOptions(BaseModel):
    """ADM-003: de naamgevingsconventie als configureerbaar regex-patroon."""

    model_config = ConfigDict(extra="forbid")

    # Zonder patroon draait ADM-003 niet; een verzonnen conventie zou elke dataset
    # afkeuren. Het register noemt het patroon expliciet projectafhankelijk.
    putpatroon: str | None = None
    strengpatroon: str | None = None

    @model_validator(mode="after")
    def _geldige_patronen(self) -> Self:
        """Eist dat de opgegeven patronen te compileren zijn."""
        for naam, patroon in (
            ("putpatroon", self.putpatroon),
            ("strengpatroon", self.strengpatroon),
        ):
            if patroon is None:
                continue
            try:
                re.compile(patroon)
            except re.error as error:
                raise ValueError(f"{naam} is geen geldig regex-patroon: {error}") from error
        return self


class ExternalSources(BaseModel):
    """Paden en laagnamen van de externe bronnen uit data/gis_koekangerveld/."""

    model_config = ConfigDict(extra="forbid")

    # Hoeveel een aangeleverde laag kleiner mag zijn dan het bereik waarvoor je hem
    # geldig verklaart (`studiegebied` hieronder), voordat het laden faalt. Nul is
    # streng. De omhullende van een laag is die van zijn *features*: een dunne laag
    # met een lege rand is niet te onderscheiden van een afgeknipt extract, en die
    # afweging hoort in het project thuis en niet in de code. Zie BO-19 in de
    # beslislog.
    dekking_tolerantie_m: float = Field(default=0.0, ge=0.0)

    map: str = "data/gis_koekangerveld"
    bgt: str | None = None
    bag_pand: str | None = None
    nwb_wegvakken: str | None = None
    studiegebied: str | None = None
    ahn_dtm: str | None = None
    # Welke BGT-lagen welke rol vervullen; per aangeleverde export in te vullen.
    bgt_pandlagen: list[str] = Field(default_factory=list)
    bgt_waterlagen: list[str] = Field(default_factory=list)
    # Geen check leest deze rol meer sinds EXT-005 en EXT-006 met issue #95 vervielen
    # (BO-64 en BO-65); de sleutel blijft staan en de laag wordt nog wel geladen.
    bgt_putdeksellagen: list[str] = Field(default_factory=list)
    bgt_overige_bouwwerklagen: list[str] = Field(default_factory=list)


class ReportOptions(BaseModel):
    """Instellingen van de rapportage en de GIS-uitvoer."""

    model_config = ConfigDict(extra="forbid")

    # A1: boven welk aandeel strengen met stijgende bodem de rode draad wordt benoemd.
    richtingsdrempel: float = Field(default=0.10, ge=0.0, le=1.0)
    # A1: vanaf hoeveel verschillende checks op een object dat als een enkele fout geldt.
    multi_melding_checks: int = Field(default=3, ge=2)
    # A5.1: 0 betekent alle bevindingen tonen; het rapport kapt niet af.
    max_bevindingen_per_check: int = Field(default=0, ge=0)
    # Boven welk aandeel van de bekeken populatie een meldingtype systemisch heet.
    systemisch_drempel: float = Field(default=0.80, gt=0.0, le=1.0)
    # En vanaf hoeveel bekeken objecten dat aandeel iets mag betekenen. Onder dit
    # aantal is een ratio geen uitspraak over de export maar een toevallige breuk van
    # kleine getallen; zie BO-59.
    systemisch_minimum_bekeken: int = Field(default=100, ge=1)
    # Versie van het checkregister, voor de metadata in de GIS-uitvoer.
    register_versie: str = "v0.9"
    # Issue #65: meldingen die de uitvoer niet haalt. Wortelklassen (subklassen via de
    # ontologie) van het hoofdobject, en check-ID's. Een uitvoerkeuze: de checks draaien
    # ongewijzigd, `bouw_meldingenstroom` filtert en telt. De CSV draagt de lijsten niet,
    # om dezelfde reden als de CFK-set; zie BO-49.
    onderdruk_klassen: list[str] = Field(default_factory=list)
    onderdruk_checks: list[str] = Field(default_factory=list)

    @field_validator("onderdruk_checks")
    @classmethod
    def _bekende_check_ids(cls, check_ids: list[str]) -> list[str]:
        """Weigert een check-ID dat het register niet kent; dat zou stil niets onderdrukken."""
        # Lazy: `checks/base.py` importeert deze module, dus een import op moduleniveau
        # is een kringimport. Bij het valideren is het register allang geladen.
        from nlriochecker.checks import REGISTRY

        onbekend = [check_id for check_id in check_ids if check_id not in REGISTRY]
        if onbekend:
            raise ValueError(
                f"onderdruk_checks kent {', '.join(onbekend)} niet; bekende checks: "
                f"{', '.join(sorted(REGISTRY))}"
            )
        return check_ids


class CheckConfig(BaseModel):
    """De volledige projectconfiguratie van de check-engine."""

    model_config = ConfigDict(extra="forbid")

    klassen: ClassRoots
    drempels: CheckThresholds = Field(default_factory=CheckThresholds)
    netwerk: NetworkOptions = Field(default_factory=NetworkOptions)
    studiegebied: StudyAreaOptions = Field(default_factory=StudyAreaOptions)
    nulmeting: NulmetingOptions
    naamgeving: NamingOptions = Field(default_factory=NamingOptions)
    inwinning: InwinningOptions = Field(default_factory=InwinningOptions)
    vulwaarden: VulwaardeOptions = Field(default_factory=VulwaardeOptions)
    puttyperegels: list[PutTypeRule] = Field(default_factory=list)
    # HGT-007: de RIONED-verhangstaffel per diameter. Leeg betekent dat HGT-007 niets
    # toetst en dat in zijn toelichting zegt; de staffel hoort in checks.toml te staan.
    verhang_staffel: list[VerhangStap] = Field(default_factory=list)
    bronnen: ExternalSources = Field(default_factory=ExternalSources)
    rapport: ReportOptions = Field(default_factory=ReportOptions)


def default_check_config_path() -> Path:
    """Pad naar de meegeleverde standaardconfiguratie in het package."""
    return Path(str(resources.files("nlriochecker").joinpath(DEFAULT_CHECK_CONFIG_NAME)))


def load_check_config(path: Path | None = None) -> CheckConfig:
    """Leest de projectconfiguratie; zonder pad de meegeleverde standaard."""
    path = Path(path) if path is not None else default_check_config_path()

    try:
        inhoud = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"{path}: configbestand kan niet gelezen worden ({error}).") from error

    try:
        rauw = tomllib.loads(inhoud.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ConfigError(f"{path}: geen geldige TOML ({error}).") from error

    try:
        return CheckConfig.model_validate(rauw)
    except ValidationError as error:
        raise ConfigError(f"{path}: configuratie is ongeldig.\n{error}") from error
