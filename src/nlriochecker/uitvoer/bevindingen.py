"""Het bevindingenrapport: Markdown voor de lezer, CSV als volledig archief.

Beide worden uit dezelfde meldingenstroom (`uitvoer.melding`) opgebouwd, zodat ze
niet uit elkaar kunnen lopen -- en met de GeoPackage-export evenmin.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

from nlriochecker.checks import REGISTRY, CheckRun, Severity
from nlriochecker.taal import getal, vorm
from nlriochecker.uitvoer.herkomst import schrijf_csv, schrijf_markdown
from nlriochecker.uitvoer.melding import Melding, bouw_meldingen
from nlriochecker.uitvoer.synthese import rode_draad
from nlriochecker.uitvoer.tabel import prepare, table

FILE_CHECKS_MARKDOWN = "bevindingen.md"
FILE_CHECKS_CSV = "bevindingen.csv"

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
]


def write_check_report(
    run: CheckRun,
    output_dir: Path,
    run_datum: date | None = None,
    meldingen: list[Melding] | None = None,
) -> tuple[Path, Path]:
    """Schrijft de bevindingen van de check-engine als Markdown en CSV.

    De beller mag de meldingenlijst meegeven; dan schrijven Markdown, CSV en de
    GeoPackage aantoonbaar dezelfde verzameling weg.
    """
    output_dir = prepare(output_dir)
    run_datum = run_datum or date.today()
    if meldingen is None:
        meldingen = bouw_meldingen(run, run_datum)

    markdown_path = schrijf_markdown(
        Path(output_dir) / FILE_CHECKS_MARKDOWN,
        f"# Checkbevindingen {run.dataset.source.name}",
        _render_checks(run, meldingen),
        run_datum,
        markering=run.meetbereik.markering() if run.meetbereik is not None else None,
    )

    csv_path = Path(output_dir) / FILE_CHECKS_CSV
    schrijf_csv(meldingen_tabel(meldingen), csv_path)

    return markdown_path, csv_path


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
        }
        for melding in meldingen
    ]
    return pd.DataFrame(rows, columns=CSV_KOLOMMEN)


def _render_checks(run: CheckRun, meldingen: list[Melding]) -> list[str]:
    """Stelt de romp van het bevindingenrapport samen; de kop komt uit `schrijf_markdown`."""
    onbetrouwbaar = sum(outcome.unreliable_count for outcome in run.outcomes)
    lines = [
        f"Bron: `{run.dataset.source}` — {len(run.dataset.nodes)} knooppunten, "
        f"{len(run.dataset.conduits)} strengen.",
        "",
        f"{run.count(Severity.ERROR)} fouten en {run.count(Severity.WARNING)} waarschuwingen "
        f"uit {len(run.outcomes)} checks.",
        "",
    ]

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

    if run.study_area is not None:
        gebied = run.study_area
        weggelaten = sum(outcome.weggelaten for outcome in run.outcomes)
        lines += [
            f"**Studiegebied:** {gebied.name} ({gebied.area_ha:.1f} ha, "
            f"{gebied.feature_count} vlak(ken), bron `{gebied.source.name}`).",
            "",
            f"> De checks draaiden op de kern plus de contextschil -- ruim genoeg dat "
            f"netwerkchecks geen randeffecten krijgen van strengen die het gebied uit lopen "
            f"-- en pas daarna is tot de kern afgebakend. "
            f"**{getal(weggelaten, 'bevinding viel', 'bevindingen vielen')} buiten "
            "het gebied** en staat hier niet in; dit rapport zegt dus niets over de rest van "
            "de dataset.",
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

    per_check: dict[str, list[Melding]] = defaultdict(list)
    for melding in meldingen:
        per_check[melding.check_id].append(melding)

    lines += _zonder_locatie(meldingen)
    lines += rode_draad(run, meldingen)
    lines += table(_check_summary(run, per_check), "Samenvatting per check")

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

    for outcome in run.outcomes:
        eigen = per_check.get(outcome.check_id, [])
        lines += ["", f"## {outcome.check_id} — {outcome.title}", ""]
        markering = f" **Skelet: {outcome.skeleton}.**" if outcome.skeleton else ""
        lines += [
            f"Ernst {outcome.severity.value}, dimensie {outcome.dimension.value}. "
            f"{getal(len(eigen), 'bevinding', 'bevindingen')} op "
            f"{outcome.examined} bekeken objecten."
            f"{markering}",
        ]
        for note in outcome.notes:
            lines += ["", f"> {note}"]
        lines += _clusterduiding(eigen)
        if not eigen:
            lines += ["", "_geen bevindingen_"]
            continue
        lines += [""]
        maximum = _maximum_per_check(run)
        getoond = eigen if maximum == 0 else eigen[:maximum]
        lines += table(
            _findings_frame(getoond),
            f"Bevindingen ({len(eigen)})",
        )
        weggelaten = len(eigen) - len(getoond)
        if weggelaten:
            lines += [
                "",
                f"_{getal(weggelaten, 'bevinding', 'bevindingen')} niet getoond; "
                f"de volledige lijst staat in `{FILE_CHECKS_CSV}`._",
            ]

    lines += ["", f"Alle bevindingen staan in `{FILE_CHECKS_CSV}`."]
    return lines


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
    """Meldt hoeveel meldingen geen plek op de kaart kregen.

    De GeoPackage telt ze in `gwsw_run`, maar wie alleen het rapport leest zou
    denken dat de kaartlaag compleet is. Zwijgen leest hier als "alles staat erop".
    """
    zonder = [melding for melding in meldingen if melding.foutlocatie is None]
    if not zonder:
        return []

    checks = ", ".join(sorted({melding.check_id for melding in zonder}))
    return [
        f"> **{getal(len(zonder), 'melding heeft', 'meldingen hebben')} geen plek op de "
        f"kaart** gekregen, omdat het object geen bruikbare geometrie heeft ({checks}). "
        "Ze staan wel in de CSV en in de meldingentabel van de GeoPackage, maar niet in "
        "de laag `meldinglocaties`.",
        "",
    ]
