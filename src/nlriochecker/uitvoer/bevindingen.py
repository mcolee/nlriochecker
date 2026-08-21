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

from nlriochecker.checks import REGISTRY, CheckRun, Severity
from nlriochecker.taal import getal, vorm
from nlriochecker.uitvoer.herkomst import schrijf_csv, schrijf_markdown
from nlriochecker.uitvoer.melding import BRON_NULMETING, Melding, bouw_meldingen
from nlriochecker.uitvoer.omvang import omvangtabel, zonder_geometrie
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
]


def write_check_report(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    meldingen: list[Melding] | None = None,
    notities: Sequence[str] = (),
) -> tuple[Path, Path]:
    """Schrijft de bevindingen van de check-engine als Markdown en CSV.

    De beller mag de meldingenlijst meegeven; dan schrijven Markdown, CSV en de
    GeoPackage aantoonbaar dezelfde verzameling weg.

    `notities` zijn opmerkingen over de invoer die de run zelf niet kent, zoals de
    geometrieen die het studiegebiedbestand niet mocht bijdragen. Ze horen in het
    rapport: wat niet bekeken is, mag niet alleen in het logboek staan.
    """
    output_dir = prepare(output_dir)
    run_datum = run_datum or date.today()
    if meldingen is None:
        meldingen = bouw_meldingen(run, run_datum)

    markdown_path = schrijf_markdown(
        Path(output_dir) / FILE_CHECKS_MARKDOWN,
        f"# {_titel(run)}",
        _render_checks(run, meldingen, notities),
        run_datum,
        markering=markering(run),
    )

    csv_path = Path(output_dir) / FILE_CHECKS_CSV
    schrijf_csv(meldingen_tabel(meldingen), csv_path)

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
        }
        for melding in meldingen
    ]
    return pd.DataFrame(rows, columns=CSV_KOLOMMEN)


def _titel(run: CheckRun) -> str:
    """De titel van het rapport: de naam van het gebied waar het over gaat.

    De lezer moet aan de titel kunnen zien waar dit rapport over gaat; "Checkbevindingen
    dewolden_orox.ttl" zei dat niet zodra er per buurt gerapporteerd werd.

    Bij een gebied zonder `naam_gebied` -- een bestand met een enkele feature -- valt de
    titel terug op de aanduiding die `StudyArea` zelf samenstelt uit het bestand en de
    laag. Zonder studiegebied blijft de dataset de aanduiding.
    """
    if run.study_area is None:
        return f"Checkbevindingen {run.dataset.source.name}"
    return run.study_area.gebied or run.study_area.name


def _render_checks(
    run: CheckRun, meldingen: list[Melding], notities: Sequence[str] = ()
) -> list[str]:
    """Stelt de romp van het bevindingenrapport samen; de kop komt uit `schrijf_markdown`.

    De volgorde is die van issue #16 en is onderdeel van de uitvoer: eerst waar het
    over gaat (de aantallen), dan of het voldoet (de managementsamenvatting en de rode
    draad), dan de verantwoording van wat er wel en niet bekeken is, en pas daarna het
    detail -- eerst de compliance van de GWSW-nulmeting, dan de eigen bevindingen.
    """
    lines = _omvang_section(run)
    lines += _samenvatting_section(run, meldingen)
    # De rode draad hoort bij de samenvatting en niet bij het detail: hij zegt wat de
    # bevindingen samen betekenen, en dat is precies wat een lezer na de vier regels
    # hierboven wil weten -- niet pas achter de tabellen.
    lines += rode_draad(run, meldingen)
    lines += _verantwoording(run, meldingen, notities)
    lines += ["", "## Detailrapportage", ""]
    nulmeting = _detail_nulmeting(run, meldingen)
    lines += nulmeting
    lines += _detail_eigen(run, meldingen, genummerd=bool(nulmeting))
    lines += ["", f"Alle bevindingen staan in `{FILE_CHECKS_CSV}`."]
    return lines


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
    regels += [""]
    return regels


def _samenvatting_section(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Voldoen we in dit gebied: een regel per conformiteitsklasse plus de eigen checks."""
    regels = ["## Voldoen we in dit gebied?", ""]
    regels += als_tabel(
        samenvatting(
            meldingen,
            run.meetbereik,
            klassenhierarchie=run.dataset.klassenhierarchie_bekend,
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
    run: CheckRun, meldingen: list[Melding], notities: Sequence[str] = ()
) -> list[str]:
    """Wat er bekeken is, wat niet, en waaronder de rest gelezen moet worden.

    Deze sectie stond voorheen boven aan het rapport. Ze is verplaatst, niet
    ingekort: wat een check *niet* bekeken heeft hoort in het rapport, en stilte
    leest als "alles gecontroleerd".
    """
    onbetrouwbaar = sum(outcome.unreliable_count for outcome in run.outcomes)
    lines = [
        "## Verantwoording",
        "",
        f"Bron: `{run.dataset.source}` — {len(run.dataset.nodes)} knooppunten, "
        f"{len(run.dataset.conduits)} strengen.",
        "",
        f"{run.count(Severity.ERROR)} fouten en {run.count(Severity.WARNING)} waarschuwingen "
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
    lines += _karakteristiek_section(run)

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

    lines += _zonder_locatie(meldingen)
    lines += table(_check_summary(run, _per_check(meldingen)), "Samenvatting per check")

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


def _per_check(meldingen: list[Melding]) -> dict[str, list[Melding]]:
    """De meldingen gegroepeerd op check-ID."""
    per_check: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        per_check[melding.check_id].append(melding)
    return per_check


def _detail_nulmeting(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Het detail van de GWSW-nulmeting: per SHACL-vorm, eerst fouten dan waarschuwingen.

    Per vorm en niet per melding. De vormen zijn er honderden en de meldingen op De
    Wolden ruim honderdduizend; een lijst daarvan is geen rapport maar een CSV. Wat
    een lezer hier nodig heeft is welke eis waar de mist in gaat, hoe vaak, en welke
    conformiteitsklassen hem stellen. De losse meldingen staan in `bevindingen.csv`
    en op de kaart.
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

    rijen: list[tuple[str, str, int, int, str]] = []
    for check_id, groep in per_vorm.items():
        klassen = sorted({cfk for melding in groep for cfk in melding.cfk})
        rijen.append(
            (
                check_id,
                # De zwaarste ernst in de groep, niet die van de eerste melding: zouden
                # twee CFK-rapporten het oneens zijn over de Severity van dezelfde vorm,
                # dan hoort de tabel de zwaarste te noemen en niet de toevallig eerste.
                "F" if any(m.ernst == Severity.ERROR.value for m in groep) else "W",
                len(groep),
                sum(1 for melding in groep if melding.systemisch),
                ", ".join(klassen),
            )
        )
    kolommen = ["Vorm", "Ernst", "Overtredingen", "Systemisch", "Conformiteitsklassen"]
    tabel = pd.DataFrame(
        # Fouten boven waarschuwingen, en binnen elk het zwaarste eerst; dat is de
        # volgorde waarin een lezer ze wil aflopen.
        sorted(rijen, key=lambda rij: (rij[1] != "F", -rij[2], rij[0])),
        columns=kolommen,
    )
    regels += table(tabel, f"Overtredingen per SHACL-vorm ({len(uit_nulmeting)})")
    return [*regels, ""]


def _detail_eigen(run: CheckRun, meldingen: list[Melding], *, genummerd: bool) -> list[str]:
    """Het detail van de eigen checks, eerst de foutchecks dan de waarschuwingschecks.

    `genummerd` is onwaar als er geen nulmetingblok boven staat -- zonder `--shacl` is
    er geen blok 1, en dan is "2. Eigen checks" een verwijzing naar niets.
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
            f"{outcome.examined} bekeken objecten."
            f"{markering}",
        ]
        for note in outcome.notes:
            regels += ["", f"> {note}"]
        regels += _clusterduiding(eigen)
        if not eigen:
            regels += ["", "_geen bevindingen_"]
            continue
        regels += [""]
        maximum = _maximum_per_check(run)
        getoond = eigen if maximum == 0 else eigen[:maximum]
        regels += table(_findings_frame(getoond), f"Bevindingen ({len(eigen)})")
        weggelaten = len(eigen) - len(getoond)
        if weggelaten:
            regels += [
                "",
                f"_{getal(weggelaten, 'bevinding', 'bevindingen')} niet getoond; "
                f"de volledige lijst staat in `{FILE_CHECKS_CSV}`._",
            ]
    return regels


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

    zonder_object = sum(1 for melding in uit_nulmeting if not melding.object_uri)
    zonder_plek = sum(
        1 for melding in uit_nulmeting if melding.object_uri and melding.foutlocatie is None
    )
    regels += [
        "",
        f"> **{getal(zonder_object, 'overtreding kwam', 'overtredingen kwamen')} "
        f"nergens op uit** en {vorm(zonder_object, 'staat', 'staan')} dus niet op de "
        "kaart: de focusnode is een klassenaam uit `CfkTypes_typ`, of een stelsel dat geen "
        "knoop of streng is. Ze staan wel in dit rapport en in de meldingentabel, met een "
        "leeg gebied -- ze zijn aan geen enkel studiegebied toe te wijzen.",
        "",
        f"> **{getal(zonder_plek, 'overtreding staat', 'overtredingen staan')} op een "
        f"object zonder bruikbare geometrie** en {vorm(zonder_plek, 'kreeg', 'kregen')} "
        "daarom geen plek op de kaart.",
        "",
    ]
    if run.nulbevindingen_weggelaten:
        buiten = getal(run.nulbevindingen_weggelaten, "overtreding viel", "overtredingen vielen")
        regels += [
            f"> **{buiten} buiten dit gebied** en "
            f"{vorm(run.nulbevindingen_weggelaten, 'staat', 'staan')} hier niet in. Ze horen "
            "bij objecten elders in de export; dit rapport zegt niets over die.",
            "",
        ]
    return regels


def _volledige_populatie_check_ids(run: CheckRun) -> list[str]:
    """De check-ID's die altijd op de volledige export draaien, gesorteerd.

    Dat zijn checks met `Check.volledig_bereik` en checks die alleen via
    `config.studiegebied.volledige_dataset_checks` zijn aangewezen (zie
    `checks.base.run_checks`). Hardcoderen van een naam hier -- zoals eerder
    alleen "ADM-002" -- laat een via de config toegevoegde check onvermeld.
    """
    geconfigureerd = set(run.config.studiegebied.volledige_dataset_checks) if run.config else set()
    ids = {
        outcome.check_id
        for outcome in run.outcomes
        if REGISTRY[outcome.check_id].volledig_bereik or outcome.check_id in geconfigureerd
    }
    return sorted(ids)


def _karakteristiek_section(run: CheckRun) -> list[str]:
    """Beschrijft eigenschappen van de dataset die de bevindingen kleuren.

    Geen bevindingen: datums die allemaal op 1 januari vallen en registraties die
    expliciet "niet achterhaald" zeggen, zijn niet per object te herstellen. Ze
    bepalen wel hoe de rest van dit rapport gelezen moet worden, en ze staan hier
    daarom als samenvattende regel in plaats van als duizenden meldingen.
    """
    karakteristiek = run.karakteristiek
    if karakteristiek is None or (not karakteristiek.datums and not karakteristiek.inwinning):
        return []

    lines = ["**Datakarakteristieken**", ""]
    if run.study_area is not None:
        # De cijfers zijn over de hele dataset geteld, terwijl de bevindingen erboven
        # tot het studiegebied zijn afgebakend. Zonder deze regel leest de tabel als
        # een beschrijving van de afbakening.
        lines += [
            f"> Geteld over de **volledige dataset**, niet over {run.study_area.name}: het "
            "gaat om eigenschappen van de aangeleverde export, en die veranderen niet met "
            "de afbakening van de rapportage.",
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
    if bronnen.missing:
        regels += [
            "",
            "> **Niet aangeleverd of leeg:** " + "; ".join(bronnen.missing) + ". De checks "
            "die deze bronnen nodig hebben zijn overgeslagen; nul bevindingen betekent daar "
            "niet dat het in orde is.",
        ]
    for note in bronnen.notes:
        regels += ["", f"> {note}"]
    return [*regels, ""]


def _check_summary(run: CheckRun, per_check: dict[str, list[Melding]]) -> pd.DataFrame:
    """Een regel per check met de aantallen uit de meldingenstroom."""
    return pd.DataFrame(
        [
            {
                "Check": outcome.check_id,
                "Omschrijving": outcome.title,
                "Ernst": outcome.severity.value,
                "Dimensie": outcome.dimension.value,
                "Bekeken": outcome.examined,
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
    return run.config.rapport.max_bevindingen_per_check if run.config is not None else 0


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


def _zonder_locatie(meldingen: list[Melding]) -> list[str]:
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
    zonder = [melding for melding in meldingen if melding.foutlocatie is None]
    if not zonder:
        return []

    objectloos = [melding for melding in zonder if not melding.object_uri]
    zonder_geometrie = [melding for melding in zonder if melding.object_uri]
    regels = [
        f"> **{getal(len(zonder), 'melding heeft', 'meldingen hebben')} geen plek op de "
        f"kaart** gekregen. {_oorzaak(objectloos, 'wijst', 'wijzen')} geen object aan; "
        f"{_oorzaak(zonder_geometrie, 'staat', 'staan')} op een object zonder bruikbare "
        f"geometrie. Ze staan wel in de CSV, in `{FILE_CHECKS_JSON}` en in de "
        "meldingentabel van de GeoPackage, die de kolommen `x` en `y` draagt; alleen "
        "kleuren ze geen object op de kaart.",
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
