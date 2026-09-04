"""Het bevindingenrapport: Markdown voor de lezer, CSV en JSON als archief.

Alle drie worden uit dezelfde meldingenstroom (`uitvoer.melding`) opgebouwd, zodat
ze niet uit elkaar kunnen lopen -- en met de GeoPackage-export evenmin.

De CSV is er voor Excel en QGIS, de JSON voor een afnemer die de bevindingen
machinaal verwerkt; `docs/json-schema.md` beschrijft dat contract.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import fields
from datetime import date
from pathlib import Path

import pandas as pd

from nlriochecker.checks import CheckRun, Severity
from nlriochecker.checks.extern import bronrollen_met_check
from nlriochecker.checks.selectie import klassen_van_rol
from nlriochecker.externedata import rol_van
from nlriochecker.nulbevinding import CHECK_VOORVOEGSEL
from nlriochecker.nulmeting_teksten import vertaald
from nlriochecker.taal import getal, vorm
from nlriochecker.uitvoer.herkomst import schrijf_csv, schrijf_markdown
from nlriochecker.uitvoer.melding import (
    BRON_DATASET,
    BRON_NULMETING,
    BRON_REGISTER,
    GEEN_ONDERDRUKKING,
    GEEN_UITZONDERINGEN,
    Melding,
    Onderdrukking,
    Uitzonderingen,
    bouw_meldingenstroom,
)
from nlriochecker.uitvoer.omvang import (
    eindpunttelling,
    klassen_op_nul,
    klassentelling,
    koppelingsherstel,
    omvangtabel,
    putten_in_beeld,
    zonder_geometrie,
)
from nlriochecker.uitvoer.samenvatting import (
    NIET_GEMETEN,
    VINKJE,
    als_tabel,
    samenvatting,
)
from nlriochecker.uitvoer.synthese import rode_draad
from nlriochecker.uitvoer.tabel import prepare, table
from nlriochecker.uitvoer.voorbehoud import markering

FILE_CHECKS_MARKDOWN = "bevindingen.md"
FILE_CHECKS_CSV = "bevindingen.csv"
FILE_CHECKS_JSON = "bevindingen.json"

# Zoveel deelstelsel-ID's noemt de clusterduiding er hooguit bij naam.
MAX_CLUSTERS_IN_DUIDING = 5

# De check waarvan het aandeel bij de datakarakteristieken komt te staan (issue #91).
# Eén ID en geen configuratie: dit is geen instelbare drempel maar de vaststelling dat
# een ontbrekend aanlegjaar op tienduizenden putten één gebrek in de aanlevering is en
# geen tienduizenden losse gebreken. De meldingen per object blijven volledig staan.
CHECK_AANLEGJAAR = "ATTR-018"

# De kolommen van het archief. De eerste negen stonden er al en houden hun naam en
# plaats; hernoemen zou bestaande verwerking breken zonder dat er iets tegenover
# staat. `Object` draagt sinds v0.8 alleen nog het fragment; de volledige URI staat
# in `ObjectURI`. De nieuwe volgen dezelfde stijl; de GeoPackage gebruikt snake_case.
# `Gereedschap` staat hier niet bij: die zet `uitvoer.herkomst.schrijf_csv` achteraan,
# in elke CSV van deze package tegelijk.
CSV_KOLOMMEN = [
    "Check",
    "Ernst",
    "Dimensie",
    "Label",
    "Object",
    "Melding",
    "TyperingBetrouwbaar",
    "X",
    "Y",
    "MeldingID",
    "Categorie",
    "Bron",
    "Object2Label",
    "Object2",
    "Waarde",
    "Drempel",
    "ClusterID",
    "Scope",
    "Gebied",
    "Prioriteit",
    "Systemisch",
    "RunDatum",
    "Dataset",
    "ObjectURI",
    "Object2URI",
    "CFK",
    # De technische SHACL-tekst naast de leesbare zin in `Melding` (issue #101).
    # Achteraan, net als `CFK`: bestaande kolommen houden hun plaats, zodat een lezer
    # die op positie werkt niet omvalt. Leeg bij een eigen check en bij een
    # datasetsignaal.
    "MeldingTechnisch",
]

# Veld → kolom(men): de afbeelding die `meldingen_tabel` hieronder rij voor rij
# maakt, hier expliciet zodat de drifttest in `tests/test_uitvoer_herkomst.py` kan
# borgen dat elk `Melding`-veld een CSV-kolom heeft. `foutlocatie` splitst in X en Y.
CSV_VELD_NAAR_KOLOM: dict[str, tuple[str, ...]] = {
    "melding_id": ("MeldingID",),
    "check_id": ("Check",),
    "categorie": ("Categorie",),
    "bron": ("Bron",),
    "ernst": ("Ernst",),
    "dimensie": ("Dimensie",),
    "object_uri": ("ObjectURI",),
    "object_id": ("Object",),
    "object_label": ("Label",),
    "object2_uri": ("Object2URI",),
    "object2_id": ("Object2",),
    "object2_label": ("Object2Label",),
    "boodschap": ("Melding",),
    "waarde": ("Waarde",),
    "drempel": ("Drempel",),
    "typering_betrouwbaar": ("TyperingBetrouwbaar",),
    "cluster_id": ("ClusterID",),
    "scope": ("Scope",),
    "gebied": ("Gebied",),
    "prioriteit": ("Prioriteit",),
    "systemisch": ("Systemisch",),
    "foutlocatie": ("X", "Y"),
    "run_datum": ("RunDatum",),
    "dataset": ("Dataset",),
    "cfk": ("CFK",),
    "boodschap_technisch": ("MeldingTechnisch",),
}


def write_check_report(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    meldingen: list[Melding] | None = None,
    notities: Sequence[str] = (),
    *,
    met_csv: bool = True,
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
    uitzonderingen: Uitzonderingen = GEEN_UITZONDERINGEN,
) -> tuple[Path, Path | None]:
    """Schrijft de bevindingen van de check-engine als Markdown en CSV.

    Het Markdown-rapport komt er altijd: het draagt de markering en het voorbehoud,
    en zonder rapport zou een run zijn eigen beperkingen nergens zeggen. De CSV komt
    op verzoek; `met_csv=False` levert `None` in plaats van een pad.

    De beller mag de meldingenlijst meegeven; dan schrijven Markdown, CSV en de
    GeoPackage aantoonbaar dezelfde verzameling weg.

    `notities` zijn opmerkingen over de invoer die de run zelf niet kent, zoals de
    geometrieen die het studiegebiedbestand niet mocht bijdragen. Ze horen in het
    rapport: wat niet bekeken is, mag niet alleen in het logboek staan.

    `onderdrukking` komt uit dezelfde stroom als de meldingen en gaat naar de
    verantwoording: wat `[rapport]` wegliet staat in geen enkele uitvoervorm, en zwijgen
    zou lezen als "alles gecontroleerd" (BO-49). Bouwt deze functie de meldingen zelf,
    dan komt hij uit diezelfde stroom: het argument alleen honoreren zou een rapport
    opleveren dat wél gefilterd is maar dat nergens zegt.

    `uitzonderingen` komt uit dezelfde stroom (issue #132) en krijgt een eigen sectie: de
    geaccepteerde bevindingen per check plus de twee luide lijsten (dode uitzonderingen en
    gewijzigde waarden), volledig. Bouwt deze functie de stroom zelf, dan neemt hij ook de
    uitzonderingen daaruit, om dezelfde reden als bij de onderdrukking.
    """
    output_dir = prepare(output_dir)
    run_datum = run_datum or date.today()
    if meldingen is None:
        stroom = bouw_meldingenstroom(run, run_datum)
        meldingen = stroom.meldingen
        onderdrukking = stroom.onderdrukking
        uitzonderingen = stroom.uitzonderingen

    markdown_path = schrijf_markdown(
        Path(output_dir) / FILE_CHECKS_MARKDOWN,
        f"# {_titel(run)}",
        _render_checks(run, meldingen, notities, onderdrukking, uitzonderingen, met_csv=met_csv),
        run_datum,
        markering=markering(run),
    )

    csv_path = (
        schrijf_csv(meldingen_tabel(meldingen), Path(output_dir) / FILE_CHECKS_CSV)
        if met_csv
        else None
    )

    return markdown_path, csv_path


def meldingen_json(meldingen: list[Melding]) -> list[dict[str, object]]:
    """Zet de meldingen om in JSON-klare rijen met dezelfde veldnamen als de dataclass.

    De veldnamen komen uit `fields(Melding)` en niet uit een lijst met de hand: die
    zou achterlopen zodra `Melding` een veld krijgt, en dan mist de JSON
    stilzwijgend een gegeven dat de CSV wel heeft.

    Niet `dataclasses.asdict`: die deepcopyt elke waarde, dus op een dataset met
    tienduizenden meldingen worden er evenzoveel `Point`-kopieen gemaakt die de
    regel erna weggegooid worden. `Melding` heeft geen geneste dataclasses, dus een
    ondiepe kopie is hier gelijkwaardig.

    Twee velden worden omgezet. `foutlocatie` wordt `[x, y]` in EPSG:28992, want een
    shapely `Point` is niet serialiseerbaar; er wordt niet geherprojecteerd, net als
    in de rest van de uitvoer. `cfk` wordt een lijst: de JSON-schrijver maakt van een
    tuple ook een array, maar dan spreekt de code het contract niet uit.
    """
    namen = [veld.name for veld in fields(Melding)]
    rijen: list[dict[str, object]] = []
    for melding in meldingen:
        rij: dict[str, object] = {naam: getattr(melding, naam) for naam in namen}
        punt = melding.foutlocatie
        rij["foutlocatie"] = None if punt is None else [punt.x, punt.y]
        rij["cfk"] = list(melding.cfk)
        rijen.append(rij)
    return rijen


def checks_json(run: CheckRun) -> list[dict[str, object]]:
    """Wat elke check bekeken heeft, als JSON-klare rijen, gesorteerd op check-ID.

    Wat `bekeken` telde staat niet in de meldingen: het hoort bij de check en niet bij
    de rij, dezelfde scheiding waarom de CFK-set niet in de CSV staat. Zonder scope en
    populatie is `bekeken` een kaal getal waarvan een afnemer niet weet waarover het
    geteld is, en dan zijn ook de percentages die erop delen onvergelijkbaar (issue #77).
    """
    return [
        {
            "check_id": outcome.check_id,
            "bekeken": outcome.examined,
            "bekeken_scope": outcome.bekeken_scope.value,
            "populatie": outcome.populatie,
        }
        for outcome in sorted(run.outcomes, key=lambda outcome: outcome.check_id)
    ]


def meldingen_tabel(meldingen: list[Melding]) -> pd.DataFrame:
    """Zet de meldingen in de archieftabel."""
    rows = [
        {
            "Check": melding.check_id,
            "Ernst": melding.ernst,
            "Dimensie": melding.dimensie,
            "Label": melding.object_label,
            "Object": melding.object_id,
            "Melding": melding.boodschap,
            "TyperingBetrouwbaar": melding.typering_betrouwbaar,
            "X": melding.foutlocatie.x if melding.foutlocatie is not None else None,
            "Y": melding.foutlocatie.y if melding.foutlocatie is not None else None,
            "MeldingID": melding.melding_id,
            "Categorie": melding.categorie,
            "Bron": melding.bron,
            "Object2Label": melding.object2_label,
            "Object2": melding.object2_id,
            "Waarde": melding.waarde,
            "Drempel": melding.drempel,
            "ClusterID": melding.cluster_id,
            "Scope": melding.scope,
            "Gebied": melding.gebied,
            "Prioriteit": melding.prioriteit,
            "Systemisch": melding.systemisch,
            "RunDatum": melding.run_datum,
            "Dataset": melding.dataset,
            "ObjectURI": melding.object_uri,
            "Object2URI": melding.object2_uri,
            "CFK": ", ".join(melding.cfk),
            "MeldingTechnisch": melding.boodschap_technisch,
        }
        for melding in meldingen
    ]
    return pd.DataFrame(rows, columns=CSV_KOLOMMEN)


def _titel(run: CheckRun) -> str:
    """De titel van het rapport: de naam van het gebied waar het over gaat.

    De lezer moet aan de titel kunnen zien waar dit rapport over gaat; "Checkbevindingen
    dewoldenhoogeveen_orox.ttl" zei dat niet zodra er per buurt gerapporteerd werd.

    Bij een gebied zonder `naam_gebied` -- een bestand met een enkele feature -- valt de
    titel terug op de aanduiding die `StudyArea` zelf samenstelt uit het bestand en de
    laag. Zonder studiegebied blijft de dataset de aanduiding.
    """
    if run.study_area is None:
        return f"Checkbevindingen {run.dataset.source.name}"
    return run.study_area.gebied or run.study_area.name


def _render_checks(
    run: CheckRun,
    meldingen: list[Melding],
    notities: Sequence[str] = (),
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
    uitzonderingen: Uitzonderingen = GEEN_UITZONDERINGEN,
    *,
    met_csv: bool = True,
) -> list[str]:
    """Stelt de romp van het bevindingenrapport samen; de kop komt uit `schrijf_markdown`.

    De volgorde is die van issue #16 en is onderdeel van de uitvoer: eerst waar het
    over gaat (de aantallen), dan of het voldoet (de managementsamenvatting en de rode
    draad), dan de verantwoording van wat er wel en niet bekeken is, en pas daarna het
    detail -- eerst de compliance van de GWSW-nulmeting, dan de eigen bevindingen.

    `met_csv` zegt of de CSV ernaast geschreven wordt. Zonder haar mag het rapport er
    niet naar verwijzen: dat zou de lezer naar een bestand sturen dat er niet is,
    juist voor de bevindingen die het rapport zelf weglaat (issue #66).
    """
    geaccepteerd = frozenset(uitzonderingen.geaccepteerd)
    lines = _omvang_section(run)
    lines += _samenvatting_section(run, meldingen, geaccepteerd)
    # De rode draad hoort bij de samenvatting en niet bij het detail: hij zegt wat de
    # bevindingen samen betekenen, en dat is precies wat een lezer na de vier regels
    # hierboven wil weten -- niet pas achter de tabellen.
    lines += rode_draad(run, meldingen)
    lines += _verantwoording(run, meldingen, notities, onderdrukking, geaccepteerd, met_csv=met_csv)
    lines += _uitzonderingen_section(uitzonderingen, meldingen)
    lines += ["", "## Detailrapportage", ""]
    nulmeting = _detail_nulmeting(run, meldingen)
    lines += nulmeting
    lines += _detail_eigen(run, meldingen, genummerd=bool(nulmeting), met_csv=met_csv)
    lines += ["", _archiefzin(met_csv)]
    return lines


def _archiefzin(met_csv: bool) -> str:
    """Waar de lezer de volledige lijst vindt; zonder CSV verwijst hij daar niet naar.

    De andere twee vormen staan onder voorbehoud: dit rapport weet niet of ze gevraagd
    zijn, en beweren dat ze er zijn zou dezelfde fout zijn als naar een uitgezette CSV
    wijzen.
    """
    if met_csv:
        return f"Alle bevindingen staan in `{FILE_CHECKS_CSV}`."
    return (
        f"De CSV is met `--uitvoer` uitgezet; alle bevindingen staan in `{FILE_CHECKS_JSON}` "
        "en in de GeoPackage, voor zover die gevraagd zijn."
    )


def _omvang_section(run: CheckRun) -> list[str]:
    """Wat er in het gebied ligt: aantallen per objecttype en stelseltype.

    De schil staat als voetnoot en niet in de tabel: er wordt niet over gerapporteerd,
    en hem meetellen zou de aantallen laten afwijken van de bevindingen eronder.
    """
    regels = ["## Wat er in dit gebied ligt", ""]
    regels += table(omvangtabel(run), "Aantallen in de kern")
    ongetekend = zonder_geometrie(run)
    if ongetekend:
        regels += [
            "",
            f"> {getal(ongetekend, 'object heeft', 'objecten hebben')} geen bruikbare "
            "geometrie en staat daarom niet in deze tabel en niet op de kaart -- "
            "compartimenten en hulpstukken zonder eigen punt, bijvoorbeeld. De checks "
            "zien ze wel.",
        ]
    stel = run.analyseset
    if stel is not None:
        regels += [
            "",
            f"> De tabel telt de {getal(len(stel.kern), 'object', 'objecten')} in de kern. "
            f"Daarbuiten zag de analyse nog {len(stel.schil)} objecten in de contextschil, "
            "nodig om de netwerkchecks hun antwoord te laten houden; daar wordt niet over "
            "gerapporteerd.",
        ]
    regels += _afhankelijkheden_section(run)
    herstel = koppelingsherstel(run)
    if herstel is not None:
        regels += [
            "",
            f"> **Herstelde hulpstukkoppelingen:** {herstel.boodschap} Het signaal staat als "
            "systemische waarschuwing in de meldingenstroom.",
        ]
    regels += [""]
    return regels


def _afhankelijkheden_section(run: CheckRun) -> list[str]:
    """De klassen waar de zwaarste checks van afhangen, en de nul-bewaking (issue #22).

    De omvangtabel erboven telt object- en stelseltype maar zwijgt over overstorten,
    gemalen, overnamepunten en bergbezinkvoorzieningen -- juist de objecten waar de
    netwerkchecks op leunen. Deze telling maakt zichtbaar of ze er zijn. De
    afvoereindpuntregel apart, want zij is het criterium om het `Gemaal`-noodverband
    van NET-001 los te laten (BO-33): zodra `Overnamepunt` boven nul komt.

    Zonder klassenhierarchie herkent `of_class` geen klassen; elke telling zou dan nul
    zijn. De sectie vervalt in dat geval -- het rapport draagt daarvoor al zijn
    voorbehoud (issue #33).
    """
    if not run.dataset.klassenhierarchie_bekend:
        return []
    regels = ["", "**Objecten waar de checks van afhangen**", ""]
    if run.study_area is not None:
        regels += [
            "> Geteld over de **geanalyseerde export** (kern plus contextschil), niet "
            "alleen de kern: of een klasse voorkomt is een eigenschap van de aanlevering "
            "en verandert niet met de afbakening van de rapportage.",
            "",
        ]
    regels += table(klassentelling(run), "Per rol")
    regels += [
        "",
        "> Elke rij is een eigen rol waarop een of meer checks selecteren; de rollen "
        "kunnen elkaar overlappen (`netwerkknopen` omvat onder meer de putten, "
        "lozingspunten en bergbezinkvoorzieningen). De aantallen zijn niet bedoeld om "
        "op te tellen.",
        "",
    ]
    regels += table(eindpunttelling(run), "Afvoereindpunten per klasse")
    regels += [
        "",
        "> `Gemaal` staat als noodverband voor `Overnamepunt` in de "
        "bereikbaarheidstoets (NET-001, BO-33). Toont `Overnamepunt` een getal boven "
        "nul, dan kan dat noodverband weg.",
    ]

    op_nul = klassen_op_nul(run)
    if op_nul:
        namen = ", ".join(f"`{signaal.label}`" for signaal in op_nul)
        staat = vorm(len(op_nul), "staat", "staan")
        regels += [
            "",
            f"> **Nul waar een check op leunt:** {namen} {staat} op nul terwijl een check "
            "erop toetst; wat daarop toetst heeft niets te beoordelen. Elk geval staat als "
            "systemische waarschuwing in de meldingenstroom.",
        ]
    return regels


def _samenvatting_section(
    run: CheckRun, meldingen: list[Melding], geaccepteerd: frozenset[str] = frozenset()
) -> list[str]:
    """Voldoen we in dit gebied: een regel per conformiteitsklasse plus de eigen checks.

    Geaccepteerde bevindingen (issue #132) tellen hier niet mee: een vinkje slaat niet om
    naar een kruisje voor een bewust aanvaarde bevinding, net zoals de kaartstatus haar
    negeert.
    """
    regels = ["## Voldoen we in dit gebied?", ""]
    regels += als_tabel(
        samenvatting(
            meldingen,
            run.meetbereik,
            klassenhierarchie=run.dataset.klassenhierarchie_bekend,
            geaccepteerd=geaccepteerd,
        )
    )
    regels += [
        "",
        f"> Een {VINKJE} betekent nul fouten in dit gebied; waarschuwingen blokkeren niet "
        "maar staan er wel bij. Een melding die meerdere conformiteitsklassen noemt telt "
        "bij elke klasse mee, dus de som over de regels ligt hoger dan het totaal. "
        f"Een {NIET_GEMETEN} betekent dat er over die klasse niets te zeggen valt.",
        "",
    ]
    return regels


def _verantwoording(
    run: CheckRun,
    meldingen: list[Melding],
    notities: Sequence[str] = (),
    onderdrukking: Onderdrukking = GEEN_ONDERDRUKKING,
    geaccepteerd: frozenset[str] = frozenset(),
    *,
    met_csv: bool = True,
) -> list[str]:
    """Wat er bekeken is, wat niet, en waaronder de rest gelezen moet worden.

    Deze sectie stond voorheen boven aan het rapport. Ze is verplaatst, niet
    ingekort: wat een check *niet* bekeken heeft hoort in het rapport, en stilte
    leest als "alles gecontroleerd".

    Geaccepteerde bevindingen (issue #132) tellen niet in de foutentelling "X fouten en
    Y waarschuwingen": ze zijn bewust aanvaard en de kaartstatus negeert ze al. Ze
    blijven wel als rij in de archieven en in de detailtabellen staan.
    """
    onbetrouwbaar = sum(outcome.unreliable_count for outcome in run.outcomes)
    # `run.count` telt de eigen-check-bevindingen; trek de geaccepteerde register-
    # meldingen ervan af, zodat de foutentelling dezelfde bevindingen negeert als de
    # kaartstatus. De onderdrukking blijft ongemoeid: die zit niet in de stroom en dus
    # niet in `geaccepteerd`, dat alleen melding-ID's uit `over` bevat.
    geaccepteerd_fout = _geaccepteerd_eigen(meldingen, geaccepteerd, Severity.ERROR)
    geaccepteerd_waarschuwing = _geaccepteerd_eigen(meldingen, geaccepteerd, Severity.WARNING)
    lines = [
        "## Verantwoording",
        "",
        f"Bron: `{run.dataset.source}` — {len(run.dataset.nodes)} knooppunten, "
        f"{len(run.dataset.conduits)} strengen.",
        "",
        f"{run.count(Severity.ERROR) - geaccepteerd_fout} fouten en "
        f"{run.count(Severity.WARNING) - geaccepteerd_waarschuwing} waarschuwingen "
        f"uit {len(run.outcomes)} eigen checks.",
        "",
    ]
    lines += _nulmeting_section(run, meldingen)

    if run.typing_gate_applied:
        lines += [
            f"De typeringspoort is toegepast: {onbetrouwbaar} bevindingen staan op objecten "
            "die de nulmeting te globaal getypeerd noemt. Die bevindingen blijven staan, "
            "maar zijn niet betrouwbaar te duiden.",
            "",
        ]
        buiten = run.unreliable_labels - run.unreliable_labels_in_dataset
        if buiten:
            lines += [
                f"> Van de {run.unreliable_labels} objecten die de nulmeting te globaal "
                f"getypeerd noemt, komen er {run.unreliable_labels_in_dataset} in deze dataset "
                f"voor; {buiten} niet. De detailrapporten en de OroX-export zijn losse "
                "bestanden en hoeven niet uit dezelfde momentopname te komen.",
                "",
            ]
        if run.niet_beoordeelde_klassen:
            klassen = ", ".join(run.niet_beoordeelde_klassen)
            lines += [
                f"> Niet beoordeeld: {klassen}. Die klassen noemt de nulmeting te globaal, maar "
                "ze zijn niet naar objecten in het domeinmodel te herleiden: dat kent alleen "
                "knopen en strengen, en een verbindingsklasse staat bovendien op de orientatie "
                "van een streng en niet op de streng zelf. Ze tellen niet mee in het "
                "typeringsvoorbehoud hierboven; over hun objecten valt hier niets te zeggen.",
                "",
            ]
    else:
        lines += [
            "> **Let op:** er is geen typeringspoort toegepast. Zonder de nulmeting-"
            "detailrapporten (`--mds` en `--hyd`) is niet bekend welke objecten te globaal "
            "getypeerd zijn, en dus welke bevindingen onbetrouwbaar zijn.",
            "",
        ]

    fallback = run.dataset.decode_fallback
    if fallback is not None:
        lines += [
            f"> **Codering:** `{fallback.path.name}` is geen geldige UTF-8, zoals Turtle "
            f"voorschrijft. Het bestand is gelezen als {fallback.encoding}; "
            f"{fallback.byte_count} bytes vallen buiten ASCII. Controleer of deze waarden "
            "kloppen:",
            "",
        ]
        lines += [f"> - `{sample}`" for sample in fallback.samples]
        lines += [""]

    for notitie in notities:
        lines += [f"> **Studiegebiedbestand:** {notitie}", ""]

    if run.study_area is not None:
        gebied = run.study_area
        weggelaten = run.weggelaten
        lines += [
            f"**Studiegebied:** {gebied.name} ({gebied.area_ha:.1f} ha, "
            f"{gebied.feature_count} vlak(ken), bron `{gebied.source.name}`).",
            "",
            f"> De checks draaiden op de kern plus de contextschil -- ruim genoeg dat "
            f"netwerkchecks geen randeffecten krijgen van strengen die het gebied uit lopen "
            f"-- en pas daarna is tot de kern afgebakend. "
            f"**{getal(weggelaten, 'bevinding viel', 'bevindingen vielen')} buiten "
            f"het gebied** en {vorm(weggelaten, 'staat', 'staan')} hier niet in; dit rapport "
            "zegt dus niets over de rest van de dataset.",
            "",
        ]
        if run.analyseset is not None and not run.analyseset.kern:
            # Nul bevindingen op een leeg gebied leest als "hier is alles in orde".
            # Bij rapportage over meerdere gebieden is zo'n gebied normaal (water,
            # natuur, bedrijventerrein) en mag het de andere niet meeslepen, maar het
            # moet wel in zijn eigen rapport staan.
            lines += [
                "> **Geen objecten in dit gebied:** geen enkele put en geen enkele streng "
                "valt erbinnen. Er is hier dus niets getoetst; dat een leeg gebied geen "
                "bevindingen oplevert, zegt niets over de kwaliteit ervan.",
                "",
            ]

    lines += _onderdrukking_section(onderdrukking)

    if run.analyseset is not None:
        stel = run.analyseset
        zin = (
            f"Analyseset: {getal(len(stel.kern), 'object', 'objecten')} in de kern, "
            f"{len(stel.schil)} in de contextschil, van {stel.volledig_aantal} in de export. "
            "De checks redeneren over kern en schil samen; gerapporteerd wordt alleen de "
            "kern."
        )
        populatiechecks = _volledige_populatie_check_ids(run)
        if populatiechecks:
            zin += (
                f" Checks die over de hele populatie gaan ({', '.join(populatiechecks)}) "
                "draaien op de volledige export."
            )
        lines += [zin]
        if stel.strengen_zonder_netwerkverband:
            aantal = stel.strengen_zonder_netwerkverband
            lines += [
                f"{getal(aantal, 'vrijvervalstreng', 'vrijvervalstrengen')} "
                f"{vorm(aantal, 'heeft', 'hebben')} een uiteinde dat niet naar een "
                "netwerkknoop herleidt en kon daardoor niet meewegen bij het bepalen van de "
                "schil; ze tellen niet mee in de aantallen hierboven.",
            ]
        lines += [""]

    lines += _bronnen_section(run)
    lines += _karakteristiek_section(run, meldingen, met_csv=met_csv)

    if run.dataset.ontologies:
        namen = ", ".join(f"`{pad.name}`" for pad in run.dataset.ontologies)
        lines += [f"Klassenhierarchie uit {namen}.", ""]
    else:
        lines += [
            "> **Let op:** er is geen ontologie geladen. Knooppunten en verbindingen zijn "
            "dan aan hun geometrie herkend in plaats van aan hun GWSW-type, en "
            "klassenwortels dekken hun subklassen niet.",
            "",
        ]

    if run.dataset.structural_diff:
        onderdelen = ", ".join(
            f"{sleutel.replace('_', ' ')}: {waarde}"
            for sleutel, waarde in sorted(run.dataset.structural_diff.items())
        )
        lines += [
            f"> De GWSW-definitie en de herkenning op geometrie wijken af ({onderdelen}). "
            "Dat is geen fout, maar het laat zien hoezeer de dataset op geometrie leunt.",
            "",
        ]

    if run.dataset.geometry_errors:
        lines += [
            f"> {len(run.dataset.geometry_errors)} objecten hebben een onleesbare geometrie "
            "en konden niet volledig meedoen.",
            "",
        ]

    lines += _zonder_locatie(meldingen, met_csv=met_csv)
    lines += table(_check_summary(run, _per_check(meldingen)), "Samenvatting per check")
    lines += [
        "",
        "_Bekeken scope zegt waarover Bekeken geteld is. Gaat over noemt de populatie die "
        "de check zelf declareert (rollen en kenmerken); dat is niet noodzakelijk precies "
        "de verzameling die geteld is -- het aantal staat in Bekeken._",
    ]

    skeletten = [outcome for outcome in run.outcomes if outcome.skeleton]
    if skeletten:
        lines += [
            "",
            f"**{len(skeletten)} check{'s zijn' if len(skeletten) > 1 else ' is'} skelet** en "
            "levert per definitie geen uitslag: "
            + ", ".join(f"{outcome.check_id} ({outcome.skeleton})" for outcome in skeletten)
            + ". De reden staat bij de check zelf.",
            "",
        ]
    return lines


def _onderdrukking_section(onderdrukking: Onderdrukking) -> list[str]:
    """Wat `[rapport]` uit de meldingenstroom hield, en waar het gebleven is.

    De alinea staat er zodra de projectconfiguratie iets onderdrukt, ook als er nul
    meldingen wegvielen: de keuze zelf hoort verantwoord te worden, en "nul" is daarvan
    de uitslag. Zwijgen zou lezen als "alles gecontroleerd" (BO-49).

    "Per check" telt alle weggevallen meldingen per check-ID -- precies het verschil met
    de kolom Bevindingen in de tabel eronder, ook als ze op klasse wegvielen. "Per
    klasse" telt het deel dat op klasse wegviel. De twee zijn dus geen partitie en
    tellen niet bij elkaar op.
    """
    if not onderdrukking.actief:
        return []
    return [
        f"**{getal(onderdrukking.totaal, 'melding onderdrukt', 'meldingen onderdrukt')}** op "
        f"grond van `[rapport]` in de projectconfiguratie — per check: "
        f"{_telling(onderdrukking.per_check)}; per klasse: "
        f"{_telling(onderdrukking.per_klasse)}. Die meldingen staan in geen enkele "
        "uitvoervorm; wie ze wil zien draait zonder `onderdruk_klassen` en "
        "`onderdruk_checks`.",
        "",
    ]


def _telling(aantallen: dict[str, int]) -> str:
    """Een telling als `TOP-011 3, ATTR-001 2`, gesorteerd op sleutel; leeg is "geen"."""
    if not aantallen:
        return "geen"
    return ", ".join(f"{sleutel} {aantallen[sleutel]}" for sleutel in sorted(aantallen))


def _uitzonderingen_section(uitzonderingen: Uitzonderingen, meldingen: list[Melding]) -> list[str]:
    """De geaccepteerde bevindingen, met de twee luide lijsten volledig (issue #132).

    Een eigen sectie naast de onderdrukking, en met een tegengesteld doel: de
    onderdrukking houdt meldingen uit de uitvoer, een uitzondering laat ze staan en
    markeert ze alleen als geaccepteerd. De sectie staat er zodra de projectconfiguratie
    een uitzonderingenbestand aanwees, ook als er nul bevindingen matchten -- de keuze
    hoort verantwoord te worden.

    Twee lijsten vervallen nooit vanzelf en staan er daarom volledig, niet afgekapt: de
    dode uitzonderingen (een melding-ID uit het bestand dat deze run niet meer oplevert)
    en de gewijzigde waarden (de melding bestaat nog maar draagt een andere waarde dan de
    snapshot -- geen automatische acceptatie, maar een vraag om herbeoordeling).
    """
    if not uitzonderingen.actief:
        return []

    check_van = {melding.melding_id: melding.check_id for melding in meldingen}
    per_check: dict[str, int] = defaultdict(int)
    for melding_id in uitzonderingen.geaccepteerd:
        per_check[check_van.get(melding_id, "?")] += 1

    geaccepteerd = getal(
        len(uitzonderingen.geaccepteerd), "bevinding geaccepteerd", "bevindingen geaccepteerd"
    )
    regels = [
        "",
        "## Uitzonderingen",
        "",
        f"**{geaccepteerd}** op grond van `[rapport] uitzonderingen` "
        f"(`{uitzonderingen.bestand}`) — per check: {_telling(dict(per_check))}. Ze blijven in "
        "elke uitvoervorm staan en krijgen op de kaart de status `geaccepteerd`; alleen uit de "
        "foutentelling van hun object vallen ze weg.",
        "",
    ]

    if uitzonderingen.zonder_bevinding:
        dood = getal(
            len(uitzonderingen.zonder_bevinding),
            "uitzondering zonder bevinding",
            "uitzonderingen zonder bevinding",
        )
        regels += [
            f"**{dood}**: in het bestand genoemd, maar deze run levert die melding niet op "
            "(defect verholpen, URI hernummerd, of op de onderdrukking weggevallen). Ze "
            "vervallen niet vanzelf en vragen om een blik:",
            "",
        ]
        regels += [f"- `{melding_id}`" for melding_id in uitzonderingen.zonder_bevinding]
        regels += [""]

    if uitzonderingen.gewijzigde_waarde:
        gewijzigd_txt = getal(
            len(uitzonderingen.gewijzigde_waarde),
            "uitzondering met gewijzigde waarde",
            "uitzonderingen met gewijzigde waarde",
        )
        regels += [
            f"**{gewijzigd_txt}**: de melding bestaat nog maar draagt een andere waarde dan de "
            "snapshot. Niet automatisch geaccepteerd; herbeoordeel X → Y:",
            "",
        ]
        regels += [
            f"- `{gewijzigd.melding_id}`: {gewijzigd.snapshot or '(leeg)'} → "
            f"{gewijzigd.waarde or '(leeg)'}"
            for gewijzigd in uitzonderingen.gewijzigde_waarde
        ]
        regels += [""]

    return regels


def _geaccepteerd_eigen(
    meldingen: list[Melding], geaccepteerd: frozenset[str], severity: Severity
) -> int:
    """Hoeveel geaccepteerde eigen-check-meldingen deze ernst dragen (issue #132).

    Precies de bevindingen die `run.count` telde maar die de acceptatie uit de
    foutentelling haalt: register-meldingen met een geaccepteerde melding-ID. Nulmeting-
    en datasetmeldingen tellen niet in `run.count` en horen hier dus niet af.
    """
    if not geaccepteerd:
        return 0
    return sum(
        1
        for melding in meldingen
        if melding.bron == BRON_REGISTER
        and melding.ernst == severity.value
        and melding.melding_id in geaccepteerd
    )


def _per_check(meldingen: list[Melding]) -> dict[str, list[Melding]]:
    """De meldingen gegroepeerd op check-ID."""
    per_check: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        per_check[melding.check_id].append(melding)
    return per_check


def _detail_nulmeting(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Het detail van de GWSW-nulmeting: per SHACL-vorm, eerst fouten dan waarschuwingen.

    Per vorm en niet per melding. De vormen zijn er honderden en de meldingen op De
    Wolden en Hoogeveen ruim honderdduizend; een lijst daarvan is geen rapport maar een CSV. Wat
    een lezer hier nodig heeft is welke eis waar de mist in gaat, hoe vaak, en welke
    conformiteitsklassen hem stellen. De losse meldingen staan in `bevindingen.csv`
    en op de kaart.

    De kolom Omschrijving draagt de leesbare zin bij de vorm (issue #101). Zij komt uit
    de meldingen zelf en niet opnieuw uit de vertaaltabel: wat hier staat is dan per
    constructie dezelfde tekst als in de CSV, de JSON en de popup. Dragen de meldingen
    van een vorm meer dan een zin -- twee conformiteitsklassen met een andere grens --
    dan staan ze er allebei.
    """
    uit_nulmeting = [melding for melding in meldingen if melding.bron == BRON_NULMETING]
    if not run.meetbereik.gemeten:
        return []

    regels = ["### 1. GWSW-nulmeting", ""]
    if not uit_nulmeting:
        return [*regels, "_geen overtredingen_", ""]

    per_vorm: dict[str, list[Melding]] = defaultdict(list)
    for melding in uit_nulmeting:
        per_vorm[melding.check_id].append(melding)

    rijen: list[tuple[str, str, str, int, int, str]] = []
    for check_id, groep in per_vorm.items():
        klassen = sorted({cfk for melding in groep for cfk in melding.cfk})
        rijen.append(
            (
                check_id,
                "; ".join(sorted({melding.boodschap for melding in groep})),
                # De zwaarste ernst in de groep, niet die van de eerste melding: zouden
                # twee CFK-rapporten het oneens zijn over de Severity van dezelfde vorm,
                # dan hoort de tabel de zwaarste te noemen en niet de toevallig eerste.
                "F" if any(m.ernst == Severity.ERROR.value for m in groep) else "W",
                len(groep),
                sum(1 for melding in groep if melding.systemisch),
                ", ".join(klassen),
            )
        )
    kolommen = [
        "Vorm",
        "Omschrijving",
        "Ernst",
        "Overtredingen",
        "Systemisch",
        "Conformiteitsklassen",
    ]
    tabel = pd.DataFrame(
        # Fouten boven waarschuwingen, en binnen elk het zwaarste eerst; dat is de
        # volgorde waarin een lezer ze wil aflopen.
        sorted(rijen, key=lambda rij: (rij[2] != "F", -rij[3], rij[0])),
        columns=kolommen,
    )
    regels += table(tabel, f"Overtredingen per SHACL-vorm ({len(uit_nulmeting)})")
    return [*regels, ""]


def _kenmerk_labels(outcome, config) -> list[str]:
    """De gedeclareerde kenmerken van een check als leesbare labels.

    Een `config:<pad>`-verwijzing (ATTR-013) wordt naar de geconfigureerde lijst
    opgelost, `*` (ATTR-014) naar "alle kenmerken".
    """
    labels: list[str] = []
    for kenmerk in outcome.kenmerken:
        if kenmerk == "*":
            labels.append("alle kenmerken")
        elif kenmerk.startswith("config:"):
            waarde: object = config
            for deel in kenmerk.removeprefix("config:").split("."):
                waarde = getattr(waarde, deel, None)
            if isinstance(waarde, list | tuple):
                labels.extend(str(w) for w in waarde)
        else:
            labels.append(kenmerk)
    return labels


def _toetst_regel(outcome, config) -> str:
    """De regel "Toetst <klassen> op <kenmerken>" onder een eigen check (issue #64).

    Zonder rollen noemt de check zelf de deelpopulatie die hij bekeek
    (`populatie_omschrijving`, issue #96); "de hele export" blijft over voor de check
    die werkelijk niet tot een populatie beperkt is.
    """
    klassen = sorted({k for rol in outcome.rollen for k in klassen_van_rol(rol, config.klassen)})
    klassen_txt = ", ".join(klassen) or outcome.populatie_omschrijving or "de hele export"
    kenmerken = _kenmerk_labels(outcome, config)
    if not kenmerken:
        return f"Toetst {klassen_txt} (structuur en geometrie, geen kenmerk)."
    return f"Toetst {klassen_txt} op {', '.join(kenmerken)}."


def _detail_eigen(
    run: CheckRun, meldingen: list[Melding], *, genummerd: bool, met_csv: bool = True
) -> list[str]:
    """Het detail van de eigen checks, eerst de foutchecks dan de waarschuwingschecks.

    `genummerd` is onwaar als er geen nulmetingblok boven staat -- zonder `--shacl` is
    er geen blok 1, en dan is "2. Eigen checks" een verwijzing naar niets.

    Systemische bevindingen staan niet in de tabel maar in een generieke regel eronder
    (issue #76), net zoals het nulmetingblok per SHACL-vorm samenvat. De vlag zit op de
    melding, dus de scheiding gaat per melding: een check waarvan maar een deel
    systemisch is toont de rest gewoon per object.
    """
    per_check = _per_check(meldingen)
    kop = "### 2. Eigen checks" if genummerd else "### Eigen checks"
    regels = ["", kop, ""]
    volgorde = sorted(
        run.outcomes, key=lambda outcome: (outcome.severity is not Severity.ERROR, outcome.check_id)
    )
    for outcome in volgorde:
        eigen = per_check.get(outcome.check_id, [])
        regels += ["", f"#### {outcome.check_id} — {outcome.title}", ""]
        markering = f" **Skelet: {outcome.skeleton}.**" if outcome.skeleton else ""
        regels += [
            f"Ernst {outcome.severity.value}, dimensie {outcome.dimension.value}. "
            f"{getal(len(eigen), 'bevinding', 'bevindingen')} op "
            f"{_bekeken_regel(outcome)}."
            f"{markering}",
        ]
        regels += ["", f"_{_toetst_regel(outcome, run.config)}_"]
        for note in outcome.notes:
            regels += ["", f"> {note}"]
        regels += _clusterduiding(eigen)
        if not eigen:
            regels += ["", "_geen bevindingen_"]
            continue
        systemisch = [melding for melding in eigen if melding.systemisch]
        per_object = [melding for melding in eigen if not melding.systemisch]
        if per_object:
            regels += [""]
            maximum = _maximum_per_check(run)
            getoond = per_object if maximum == 0 else per_object[:maximum]
            regels += table(_findings_frame(getoond), f"Bevindingen ({len(per_object)})")
            weggelaten = len(per_object) - len(getoond)
            if weggelaten:
                regels += [
                    "",
                    f"_{getal(weggelaten, 'bevinding', 'bevindingen')} niet getoond; "
                    f"{_volledige_lijst(met_csv)}._",
                ]
        if systemisch:
            regels += _systemische_regel(
                len(systemisch), outcome, alle=not per_object, met_csv=met_csv
            )
    return regels


def _bekeken_regel(outcome) -> str:
    """Wat `bekeken` van deze check telde: het aantal en de scope, plus waar hij over gaat.

    Eén formulering voor de detailregel en voor de generieke systemische regel
    eronder. Het kale getal mengt drie noemers -- een rol op de analyseset, dezelfde
    rol op de volledige export, en kenmerkinstanties -- en "bekeken objecten" was voor
    de derde soort gewoon onwaar (issue #77).

    De scope hoort bij het getal; de gedeclareerde populatie staat er los van, achter
    "gaat over". Zij is een bovengrens en geen noemer (zie `CheckOutcome.populatie`),
    en direct achter een telling zou zij als de noemer lezen. Een check die niets
    declareert (ADM-007) krijgt de toevoeging niet.
    """
    kern = f"{outcome.examined} bekeken ({outcome.bekeken_scope.value}"
    if not outcome.populatie:
        return f"{kern})"
    return f"{kern}; gaat over: {outcome.populatie})"


def _volledige_lijst(met_csv: bool) -> str:
    """Waar de volledige lijst staat, als deelzin; zonder CSV noemt hij haar niet.

    Naar een met `--uitvoer` uitgezette CSV verwijzen stuurt de lezer naar een bestand
    dat er niet is, juist voor de bevindingen die het rapport zelf weglaat (issue #66).
    """
    if met_csv:
        return f"de volledige lijst staat in `{FILE_CHECKS_CSV}`"
    return (
        f"de CSV is met `--uitvoer` uitgezet, de volledige lijst staat in "
        f"`{FILE_CHECKS_JSON}` of de GeoPackage, voor zover die gevraagd zijn"
    )


def _systemische_regel(aantal: int, outcome, *, alle: bool, met_csv: bool) -> list[str]:
    """De generieke regel voor systemische bevindingen (issue #76).

    Check, aantal en bekeken populatie, in de vorm die het nulmetingblok per SHACL-vorm
    al gebruikt; de check zelf staat in de kop erboven. Een systemische bevinding is
    dezelfde structurele kwestie op (vrijwel) elk object -- zelf gedeclareerd door de
    check of afgeleid uit de populatieratio -- en per object opgesomd verdringt zij wat
    dit object van zijn buren onderscheidt. `alle` is onwaar als er ook niet-systemische
    bevindingen zijn; dan staat de regel onder hun tabel.

    De rijen zelf blijven in de CSV, de JSON en de meldingentabel van de GeoPackage
    staan: die zijn een archief, en het weglaten is een keuze van de weergave.
    """
    aanhef = "Systemisch" if alle else "Daarnaast systemisch"
    return [
        "",
        f"_{aanhef}: {getal(aantal, 'bevinding', 'bevindingen')} op "
        f"{_bekeken_regel(outcome)} -- dezelfde kwestie op vrijwel elk object, dus dit "
        f"rapport toont {vorm(aantal, 'haar', 'ze')} niet per object; "
        f"{_volledige_lijst(met_csv)}._",
    ]


def _nulmeting_section(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Wat de GWSW SHACL-nulmeting bijdroeg, en wat er niet van op de kaart kwam.

    Deze sectie staat er alleen als er gemeten is. Nul overtredingen is dan een
    uitslag en geen reden om te zwijgen. De aantallen komen uit de meldingenstroom en
    niet uit de rapporten zelf: wat hier staat is precies wat er in de CSV, de
    GeoPackage en de JSON terechtkomt, ook na afbakening tot een studiegebied.

    De tellingen per conformiteitsklasse tellen een melding bij elke klasse die hem
    noemt. Dat is met opzet: de klassen zijn geen partitie van de meldingen, en de
    som over de kolom is dus hoger dan het totaal.
    """
    if not run.meetbereik.gemeten:
        return []

    uit_nulmeting = [melding for melding in meldingen if melding.bron == BRON_NULMETING]
    fouten = sum(1 for melding in uit_nulmeting if melding.ernst == Severity.ERROR.value)
    systemisch = sum(1 for melding in uit_nulmeting if melding.systemisch)
    regels = [
        "**GWSW-nulmeting**",
        "",
        f"{getal(len(uit_nulmeting), 'overtreding', 'overtredingen')} uit de "
        f"SHACL-nulmeting: {fouten} fouten en {len(uit_nulmeting) - fouten} waarschuwingen, "
        f"waarvan {systemisch} systemisch. Dezelfde overtreding in meerdere "
        "conformiteitsklassen telt hier een keer; de klassen staan erbij.",
        "",
    ]

    per_cfk: defaultdict[str, int] = defaultdict(int)
    for melding in uit_nulmeting:
        for cfk in melding.cfk:
            per_cfk[cfk] += 1
    regels += table(
        pd.DataFrame(
            [
                {"Conformiteitsklasse": cfk, "Overtredingen": per_cfk.get(cfk, 0)}
                for cfk in run.meetbereik.gekozen
            ],
            columns=["Conformiteitsklasse", "Overtredingen"],
        ),
        "Overtredingen per conformiteitsklasse",
    )

    stelsel_uris = {str(subject) for subject in run.dataset.subjects_of_class("Stelsel")}
    op_stelsel = sum(1 for melding in uit_nulmeting if melding.object_uri in stelsel_uris)
    zonder_object = sum(1 for melding in uit_nulmeting if not melding.object_uri)
    zonder_plek = sum(
        1
        for melding in uit_nulmeting
        if melding.object_uri
        and melding.foutlocatie is None
        and melding.object_uri not in stelsel_uris
    )
    # Sinds issue #75 tekent de GeoPackage geen stelselvlakken meer, dus een overtreding
    # op een geregistreerd stelsel komt net zomin op de kaart als een op een klassenaam.
    # Ze staan daarom in een telling: ze laten wegvallen zou lezen als "alles bekeken".
    zonder_kaartobject = zonder_object + op_stelsel
    regels += [
        "",
        f"> **{getal(zonder_kaartobject, 'overtreding kreeg', 'overtredingen kregen')} "
        f"geen kaartobject** en {vorm(zonder_kaartobject, 'staat', 'staan')} dus niet op de "
        f"kaart: {zonder_object} met een klassenaam uit `CfkTypes_typ` als focusnode en "
        f"{op_stelsel} op een geregistreerd stelsel (#17). Een klassenaam wijst geen object "
        "aan, en een stelsel is geen knoop of streng -- sinds issue #75 tekent de GeoPackage "
        "er ook geen vlak meer omheen. Ze staan wel in dit rapport en in de meldingentabel, "
        "met een leeg gebied: ze zijn aan geen enkel studiegebied toe te wijzen (BO-12).",
        "",
        f"> **{getal(zonder_plek, 'overtreding staat', 'overtredingen staan')} op een "
        f"object zonder bruikbare geometrie** en {vorm(zonder_plek, 'kreeg', 'kregen')} "
        "daarom geen plek op de kaart.",
        "",
    ]
    regels += _onvertaald_section(uit_nulmeting)
    if run.nulbevindingen_weggelaten:
        buiten = getal(run.nulbevindingen_weggelaten, "overtreding viel", "overtredingen vielen")
        regels += [
            f"> **{buiten} buiten dit gebied** en "
            f"{vorm(run.nulbevindingen_weggelaten, 'staat', 'staan')} hier niet in. Ze horen "
            "bij objecten elders in de export; dit rapport zegt niets over die.",
            "",
        ]
    return regels


def _onvertaald_section(uit_nulmeting: list[Melding]) -> list[str]:
    """Hoeveel meldingen op de technische SHACL-tekst terugvielen, en van welke vormen.

    De vertaaltabel (issue #101) dekt de 43 vormen die de De Wolden-rapporten kennen.
    Een GWSW-server die een nieuwe vorm oplevert, of een andere gemeente met andere
    stelseltypen, levert een vorm zonder tekst; die melding blijft staan met haar
    technische boodschap. Zwijgen zou lezen als "alles is leesbaar gemaakt", terwijl de
    lezer dan zonder verklaring een regel SHACL-jargon voor zich krijgt.

    De regel blijft weg zodra elke vorm vertaald is: "0 meldingen van 0 onvertaalde
    vormen" is geen verantwoording maar ruis in een sectie die juist zegt wat er
    ontbreekt.
    """
    telling: dict[str, int] = defaultdict(int)
    for melding in uit_nulmeting:
        vormnaam = melding.check_id.removeprefix(f"{CHECK_VOORVOEGSEL}-")
        if not vertaald(vormnaam):
            telling[vormnaam] += 1
    if not telling:
        return []

    meldingen = sum(telling.values())
    namen = ", ".join(f"`{vormnaam}`" for vormnaam in sorted(telling))
    return [
        f"> **{getal(meldingen, 'melding draagt', 'meldingen dragen')} de technische "
        f"SHACL-tekst**: {getal(len(telling), 'vorm heeft', 'vormen hebben')} nog geen "
        f"vastgestelde Nederlandse omschrijving ({namen}). De overtreding zelf telt "
        "gewoon mee; alleen de zin erbij is nog die van de GWSW-server.",
        "",
    ]


def _volledige_populatie_check_ids(run: CheckRun) -> list[str]:
    """De check-ID's die altijd op de volledige export draaien, gesorteerd.

    Dat zijn checks met `Check.volledig_bereik` en checks die alleen via
    `config.studiegebied.volledige_dataset_checks` zijn aangewezen (zie
    `checks.base.run_checks`). Hardcoderen van een naam hier -- zoals eerder
    alleen "ADM-002" -- laat een via de config toegevoegde check onvermeld.
    """
    geconfigureerd = set(run.config.studiegebied.volledige_dataset_checks)
    ids = {
        outcome.check_id
        for outcome in run.outcomes
        if outcome.volledig_bereik or outcome.check_id in geconfigureerd
    }
    return sorted(ids)


def _karakteristiek_section(run: CheckRun, meldingen: list[Melding], *, met_csv: bool) -> list[str]:
    """Beschrijft eigenschappen van de dataset die de bevindingen kleuren.

    Geen bevindingen: datums die allemaal op 1 januari vallen en registraties die
    expliciet "niet achterhaald" zeggen, zijn niet per object te herstellen. Ze
    bepalen wel hoe de rest van dit rapport gelezen moet worden, en ze staan hier
    daarom als samenvattende regel in plaats van als duizenden meldingen.

    Het ontbrekende aanlegjaar staat vooraan (issue #91): dat is wél per object gemeld,
    maar het aandeel zegt iets anders dan de losse meldingen -- de kop hoort het te
    benoemen, ook als er verder geen enkele karakteristiek is.
    """
    aanlegjaar = _aanlegjaar_regel(run, meldingen, met_csv=met_csv)
    tabellen = _karakteristiek_tabellen(run)
    if not aanlegjaar and not tabellen:
        return []
    return ["**Datakarakteristieken**", "", *aanlegjaar, *tabellen]


def _aanlegjaar_regel(run: CheckRun, meldingen: list[Melding], *, met_csv: bool) -> list[str]:
    """Het aandeel putten zonder aanlegjaar, als eerste regel van de datakarakteristieken.

    Teller en noemer komen uit wat er al is: de ATTR-018-meldingen van *deze* uitvoer --
    dus na afbakening en na de onderdrukking uit `[rapport]` -- en de putpopulatie uit
    `uitvoer.omvang`. Een eigen doorloop over de dataset zou een tweede waarheid naast
    de check opleveren.

    Meldt ATTR-018 niets, of staat er geen put in beeld, dan blijft de regel weg. "0%
    van de putten zonder aanlegjaar" is geen karakteristiek van de aanlevering maar ruis
    in een sectie die juist zegt waaronder de rest gelezen moet worden. Dat de teller
    dan nul is dekt beide gevallen, en houdt de deling veilig.

    De regel wijst naar het **archief** en niet naar dit rapport of de kaart. Dat er per
    put een melding is blijft waar in elke toestand, maar waar die te zien is niet: komt
    ATTR-018 boven de systemisch-drempel, dan vouwt `_detail_eigen` de tabel tot een
    generieke regel (issue #76) en laat `objectkaart.popup_html` de meldingen weg
    (BO-59), en `max_bevindingen_per_check` kapt de tabel sowieso af. `_volledige_lijst`
    is de ene plek die weet waar de volledige lijst wél staat, inclusief het geval waarin
    `--uitvoer` de CSV uitzette (issue #66); die tweede plek hier zelf formuleren zou op
    een dag naar een bestand wijzen dat er niet is.
    """
    in_beeld = putten_in_beeld(run)
    zonder = sum(
        1
        for melding in meldingen
        if melding.check_id == CHECK_AANLEGJAAR and melding.object_uri in in_beeld
    )
    if not zonder:
        return []
    hier = " in dit gebied" if run.study_area is not None else ""
    return [
        f"**{100 * zonder / len(in_beeld):.1f}% van de putten{hier} draagt geen aanlegjaar** "
        f"({zonder} van de {len(in_beeld)}) — een aanleveringssignaal: het aanlegjaar "
        "ontbreekt stelselmatig, en dat is één gebrek in de aanlevering. "
        f"{CHECK_AANLEGJAAR} meldt elk geval afzonderlijk, zodat de putten aanwijsbaar "
        f"blijven: {_volledige_lijst(met_csv)}. Herstellen gaat via de aanlevering en niet "
        "put voor put.",
        "",
    ]


def _karakteristiek_tabellen(run: CheckRun) -> list[str]:
    """De tellingen van `karakteristiek.py`: datumprecisie en inwinningsvulling."""
    karakteristiek = run.karakteristiek
    if karakteristiek is None or (not karakteristiek.datums and not karakteristiek.inwinning):
        return []

    lines: list[str] = []
    if run.study_area is not None:
        # De cijfers zijn over de hele dataset geteld, terwijl de bevindingen erboven
        # tot het studiegebied zijn afgebakend. Zonder deze regel leest de tabel als
        # een beschrijving van de afbakening.
        lines += [
            f"> De tabellen hieronder tellen over de **volledige dataset**, niet over "
            f"{run.study_area.name}: het gaat om eigenschappen van de aangeleverde export, "
            "en die veranderen niet met de afbakening van de rapportage.",
            "",
        ]

    if karakteristiek.datums:
        lines += [
            "| Datumkenmerk | Waarden | Op 1 januari | Precisie |",
            "| --- | ---: | ---: | --- |",
        ]
        for precisie in karakteristiek.datums:
            lines.append(
                f"| {precisie.kenmerk} | {precisie.aantal} | {precisie.op_jaargrens} "
                f"({precisie.aandeel:.1f}%) | "
                f"{'jaar' if precisie.jaarprecisie else 'dag'} |"
            )
        jaar = karakteristiek.jaarprecisie
        if jaar:
            namen = ", ".join(precisie.kenmerk for precisie in jaar)
            lines += [
                "",
                f"> Elke waarde van {namen} valt op 1 januari: alleen het jaartal draagt "
                "informatie. Leeftijden en tijdsverschillen uit deze dataset gelden dus op "
                "jaarniveau; een uitkomst op dagniveau zou een precisie suggereren die de "
                "bron niet heeft.",
            ]
        lines += [""]

    if karakteristiek.inwinning:
        lines += [
            "| Hoogtekenmerk | Waarden | Met inwinningswijze | Waarvan expliciet onbekend |",
            "| --- | ---: | ---: | ---: |",
        ]
        for vulling in karakteristiek.inwinning:
            onbekend = (
                f"{vulling.onbekend} ({vulling.onbekend_aandeel:.1f}%)"
                if vulling.met_wijze
                else "—"
            )
            lines.append(
                f"| {vulling.kenmerk} | {vulling.aantal} | {vulling.met_wijze} | {onbekend} |"
            )
        if karakteristiek.vulwaarden:
            lines += [
                "",
                "> De kolom *Waarden* telt alleen echte registraties: "
                f"{karakteristiek.vulwaarden} hoogtewaarden vielen binnen de "
                "vulwaardeband en zijn als niet geregistreerd gelezen (zie ATTR-013). "
                "Zonder die leesregel stonden ze hier als gevulde waarde in de noemer.",
            ]
        if karakteristiek.onbekend_totaal:
            lines += [
                "",
                f"> {karakteristiek.onbekend_totaal} registraties zeggen expliciet dat de "
                "inwinning niet te achterhalen is. Die passeren elke kardinaliteits- en "
                "collectietoets van de nulmeting, maar dragen geen informatie: een "
                "compleetheidscijfer dat ze meetelt leest te rooskleurig.",
            ]
        lines += [""]

    return lines


def _bronnen_section(run: CheckRun) -> list[str]:
    """Beschrijft de externe bronnen, hun bereik en wat er niet bij zat.

    Zonder deze sectie zou een lezer van het rapport niet kunnen zien waarom de
    EXT-checks weinig of niets gevonden hebben; die informatie stond alleen op de
    opdrachtregel.
    """
    bronnen = run.bronnen
    if bronnen is None:
        return [
            "> **Externe bronnen:** geen geladen. De EXT-checks en HGT-001 t/m HGT-003 "
            "hebben daardoor niets kunnen toetsen; geef `--bronnen` op voor een volledig "
            "beeld.",
            "",
        ]

    regels = ["**Externe bronnen**", ""]
    if bronnen.extent is None:
        regels += [
            "> Er is geen begrenzingspolygoon geladen. Zonder begrenzing mag geen enkele "
            "EXT-check een uitslag geven; ze zijn alle overgeslagen.",
            "",
        ]
    lagen = pd.DataFrame(
        [
            {
                "Rol": laag.role,
                "Bestand": laag.source.name,
                "Laag": laag.layer,
                "Features": len(laag),
                "CRS": laag.crs,
                "Geherprojecteerd uit": laag.reprojected_from or "—",
            }
            for laag in bronnen.layers.values()
        ],
        columns=["Rol", "Bestand", "Laag", "Features", "CRS", "Geherprojecteerd uit"],
    )
    regels += table(lagen, "Ingelezen lagen")
    if bronnen.raster is not None:
        regels += ["", f"Hoogteraster: `{bronnen.raster.source.name}` ({bronnen.raster.crs})."]
    # Alleen de bronnen waar werkelijk een check op leunt: sinds EXT-005 en EXT-006
    # vervielen leest niets meer `bgt_putdeksel`, en `nwb_wegvak` had nooit een lezer.
    # Hun ontbreken slaat geen check over, dus deze zin zou er onwaar over zijn (BO-64).
    # De laag zelf blijft geladen en op dekking getoetst, en de terugkoppeling van
    # `toets` op de opdrachtregel somt nog steeds alles op wat er niet was.
    gemist = [regel for regel in bronnen.missing if rol_van(regel) in bronrollen_met_check()]
    if gemist:
        regels += [
            "",
            "> **Niet aangeleverd of leeg:** " + "; ".join(gemist) + ". De checks "
            "die deze bronnen nodig hebben zijn overgeslagen; nul bevindingen betekent daar "
            "niet dat het in orde is.",
        ]
    for note in bronnen.notes:
        regels += ["", f"> {note}"]
    return [*regels, ""]


def _check_summary(run: CheckRun, per_check: dict[str, list[Melding]]) -> pd.DataFrame:
    """Een regel per check met de aantallen uit de meldingenstroom.

    `Bekeken scope` staat naast `Bekeken` omdat dat getal anders drie onvergelijkbare
    noemers in een kolom mengt (issue #77). `Gaat over` is geen noemer maar de
    gedeclareerde populatie van de check; de voetnoot onder de tabel zegt dat erbij.
    """
    return pd.DataFrame(
        [
            {
                "Check": outcome.check_id,
                "Omschrijving": outcome.title,
                "Ernst": outcome.severity.value,
                "Dimensie": outcome.dimension.value,
                "Bekeken": outcome.examined,
                "Bekeken scope": outcome.bekeken_scope.value,
                "Gaat over": outcome.populatie,
                "Bevindingen": len(per_check.get(outcome.check_id, [])),
                "Typering onbetrouwbaar": sum(
                    1
                    for melding in per_check.get(outcome.check_id, [])
                    if not melding.typering_betrouwbaar
                ),
                "Skelet": outcome.skeleton or "—",
            }
            for outcome in run.outcomes
        ],
        columns=[
            "Check",
            "Omschrijving",
            "Ernst",
            "Dimensie",
            "Bekeken",
            "Bekeken scope",
            "Gaat over",
            "Bevindingen",
            "Typering onbetrouwbaar",
            "Skelet",
        ],
    )


def _findings_frame(meldingen: list[Melding]) -> pd.DataFrame:
    """Zet meldingen om in een tabel voor de Markdown-uitvoer."""
    return pd.DataFrame(
        [
            {
                "Label": melding.object_label or "—",
                "Melding": melding.boodschap,
                "Typering": "betrouwbaar" if melding.typering_betrouwbaar else "onbetrouwbaar",
            }
            for melding in meldingen
        ],
        columns=["Label", "Melding", "Typering"],
    )


def _maximum_per_check(run: CheckRun) -> int:
    """Het maximum aantal getoonde bevindingen per check; 0 is onbeperkt."""
    return run.config.rapport.max_bevindingen_per_check


def _clusterduiding(meldingen: list[Melding]) -> list[str]:
    """Vat samen hoeveel deelstelsels de getoonde bevindingen betreffen.

    24 bevindingen op twee deelstelsels zijn geen 24 losse gebreken. De telling
    gaat over de bevindingen die in dit rapport staan, dus na afbakening tot het
    studiegebied; over de volledige dataset geteld zou ze een heel ander getal
    opleveren dan de lezer voor zich ziet.
    """
    clusters = sorted({melding.cluster_id for melding in meldingen if melding.cluster_id})
    if not clusters:
        return []

    getoond = ", ".join(clusters[:MAX_CLUSTERS_IN_DUIDING])
    rest = len(clusters) - MAX_CLUSTERS_IN_DUIDING
    namen = f"{getoond} en {rest} andere" if rest > 0 else getoond
    return [
        "",
        f"> De bevindingen betreffen {getal(len(clusters), 'deelstelsel', 'deelstelsels')} "
        f"({namen}); elke bevinding draagt een cluster-ID, zodat het herstel per deelstelsel "
        "opgepakt kan worden.",
    ]


def _zonder_locatie(meldingen: list[Melding], *, met_csv: bool = True) -> list[str]:
    """Meldt hoeveel meldingen geen plek op de kaart kregen, en waarom.

    De GeoPackage telt ze in `gwsw_run`, maar wie alleen het rapport leest zou denken
    dat het kaartbeeld compleet is. Zwijgen leest hier als "alles staat erop".

    Twee oorzaken, en ze horen uit elkaar gehouden te worden: een melding die geen
    object aanwijst (dataset-breed, een EXT-verwijzing zonder rioolobject, een
    focusnode uit de nulmeting die nergens op uitkwam) en een melding op een object
    zonder bruikbare geometrie. Ze op een hoop gooien leverde een rapport op dat in
    de ene alinea 578 meldingen aan een ontbrekende geometrie weet en in de andere
    telde dat er nul zo'n geval was.
    """
    # Datasetsignalen (bron "dataset") horen hier niet: ze zijn geen bevinding die niet
    # te plaatsen viel maar een signaal over de export, dat de omvangsectie al noemt. Ze
    # meetellen zou `SIG-nulklasse` in deze telling zetten alsof een check zijn objecten
    # niet op de kaart kreeg.
    zonder = [
        melding
        for melding in meldingen
        if melding.foutlocatie is None and melding.bron != BRON_DATASET
    ]
    if not zonder:
        return []

    objectloos = [melding for melding in zonder if not melding.object_uri]
    zonder_geometrie = [melding for melding in zonder if melding.object_uri]
    # Zonder CSV mag die hier niet genoemd worden: dan verwijst het rapport naar een
    # bestand dat `--uitvoer` heeft uitgezet (issue #66).
    waar = (
        f"Ze staan wel in de CSV, in `{FILE_CHECKS_JSON}` en in de meldingentabel van de "
        "GeoPackage, die de kolommen `x` en `y` draagt"
        if met_csv
        else f"Ze staan wel in `{FILE_CHECKS_JSON}` en in de meldingentabel van de GeoPackage, "
        "die de kolommen `x` en `y` draagt, voor zover die gevraagd zijn"
    )
    regels = [
        f"> **{getal(len(zonder), 'melding heeft', 'meldingen hebben')} geen plek op de "
        f"kaart** gekregen. {_oorzaak(objectloos, 'wijst', 'wijzen')} geen object aan; "
        f"{_oorzaak(zonder_geometrie, 'staat', 'staan')} op een object zonder bruikbare "
        f"geometrie. {waar}; alleen kleuren ze geen object op de kaart.",
        "",
    ]
    return regels


def _oorzaak(meldingen: list[Melding], enkelvoud: str, meervoud: str) -> str:
    """Een deeltelling met de checks die haar leveren, of niets als ze nul is.

    De checks stonden eerder achter beide oorzaken samen, en kwamen daarmee terecht
    achter een telling van nul -- twaalf vormnamen bij "0 meldingen". Ze horen bij de
    oorzaak waar ze uit komen.
    """
    if not meldingen:
        return f"0 {meervoud}"
    checks = ", ".join(sorted({melding.check_id for melding in meldingen}))
    return f"{getal(len(meldingen), enkelvoud, meervoud)} ({checks})"
