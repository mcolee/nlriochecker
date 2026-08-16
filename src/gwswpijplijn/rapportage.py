"""Wegschrijven van de analyse als Markdown-samenvatting en geaggregeerde CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gwswpijplijn.fouten import GwswPijplijnFout
from gwswpijplijn.paar import RapportPaar

BESTAND_MARKDOWN = "samenvatting.md"
BESTAND_CSV = "geaggregeerde_meldingen.csv"
TOP_N = 15


def schrijf_rapportage(paar: RapportPaar, uitvoermap: Path) -> tuple[Path, Path]:
    """Schrijft de Markdown-samenvatting en de geaggregeerde CSV naar `uitvoermap`."""
    uitvoermap = Path(uitvoermap)
    uitvoermap.mkdir(parents=True, exist_ok=True)
    return schrijf_markdown(paar, uitvoermap), schrijf_csv(paar, uitvoermap)


def schrijf_markdown(paar: RapportPaar, uitvoermap: Path) -> Path:
    """Schrijft de samenvatting als Markdown en geeft het geschreven pad terug."""
    doel = _controleer_doel(Path(uitvoermap) / BESTAND_MARKDOWN, paar)
    doel.write_text(_markdown(paar), encoding="utf-8")
    return doel


def schrijf_csv(paar: RapportPaar, uitvoermap: Path) -> Path:
    """Schrijft de geaggregeerde meldingen van beide CFK's als een enkele CSV."""
    doel = _controleer_doel(Path(uitvoermap) / BESTAND_CSV, paar)
    _geaggregeerde_tabel(paar).to_csv(doel, sep=";", index=False, encoding="utf-8")
    return doel


def _geaggregeerde_tabel(paar: RapportPaar) -> pd.DataFrame:
    """Zet beide analyses onder elkaar in een lang formaat met een CFK-kolom."""
    delen = []
    for analyse in (paar.mds, paar.hyd):
        deel = analyse.per_melding_objecttype.copy()
        deel.insert(0, "CFK", analyse.rapport.cfk)
        delen.append(deel)
    return pd.concat(delen, ignore_index=True)


def _controleer_doel(doel: Path, paar: RapportPaar) -> Path:
    """Weigert te schrijven als het doelpad een van de invoerbestanden is."""
    invoer = {
        paar.mds.rapport.bronbestand.resolve(),
        paar.hyd.rapport.bronbestand.resolve(),
    }
    if doel.resolve() in invoer:
        raise GwswPijplijnFout(
            f"{doel}: de uitvoer zou een invoerbestand overschrijven. Kies een andere uitvoermap."
        )
    return doel


def _markdown(paar: RapportPaar) -> str:
    """Stelt de volledige Markdown-samenvatting samen."""
    regels = [
        f"# Nulmeting-samenvatting {paar.dataset}",
        "",
        "## Herkomst",
        "",
        "| CFK | Bronbestand | Toetsmoment | Meldingregels | Totaal Aantal |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for analyse in (paar.mds, paar.hyd):
        rapport = analyse.rapport
        regels.append(
            f"| {rapport.cfk} | `{rapport.bronbestand}` | "
            f"{rapport.tijdstempel:%Y-%m-%d %H:%M:%S} | {len(rapport.meldingen)} | "
            f"{analyse.totaal_aantal} |"
        )
    if paar.tijdstempels_verschillen:
        regels += [
            "",
            "> **Let op:** de twee rapporten komen uit verschillende toetsmomenten.",
        ]

    regels += ["", "## Typeringspoort", ""]
    regels += _typeringssectie(paar)

    for analyse in (paar.mds, paar.hyd):
        regels += ["", f"## Meldingen CFK {analyse.rapport.cfk}", ""]
        regels += _tabel(
            analyse.per_melding.head(TOP_N), _titel("Meldingstypen", analyse.per_melding)
        )
        regels += [""]
        regels += _tabel(
            analyse.per_objecttype.head(TOP_N), _titel("Objecttypen", analyse.per_objecttype)
        )

    return "\n".join(regels) + "\n"


def _typeringssectie(paar: RapportPaar) -> list[str]:
    """Bouwt de sectie over de typeringspoort, inclusief de ondergrens-toelichting."""
    regels = [
        "Meldingen van het type *Objecttype te globaal voor deze CFK* maken vervolg-",
        "validaties voor die objecten onbetrouwbaar. De score hieronder is een",
        "**ondergrens**: het detailrapport bevat alleen objecten met minstens een",
        "melding, dus objecten zonder meldingen ontbreken in de noemer.",
        "",
        "| CFK | Typeringsscore | Te globaal getypeerd | Benoemde objecten |",
        "| --- | ---: | ---: | ---: |",
    ]
    for analyse in (paar.mds, paar.hyd):
        poort = analyse.typeringspoort
        regels.append(
            f"| {analyse.rapport.cfk} | {poort.score:.1f}% | {poort.aantal_te_globaal} | "
            f"{poort.aantal_benoemde_objecten} |"
        )

    for analyse in (paar.mds, paar.hyd):
        poort = analyse.typeringspoort
        if poort.aantal_te_globaal == 0:
            continue
        per_type = (
            poort.objecten.groupby("Type object").size().sort_values(ascending=False).reset_index()
        )
        per_type.columns = ["Type object", "Objecten"]
        regels += ["", f"### Te globaal getypeerde objecten ({analyse.rapport.cfk})", ""]
        regels += _tabel(per_type, "Per objecttype")
        voorbeelden = ", ".join(f"`{naam}`" for naam in poort.objecten["Naam"].head(10))
        regels += ["", f"Eerste tien objecten: {voorbeelden}"]

    return regels


def _titel(noemer: str, frame: pd.DataFrame) -> str:
    """Maakt een tabeltitel die alleen 'top N' vermeldt als er daadwerkelijk is afgekapt."""
    if len(frame) > TOP_N:
        return f"{noemer} (top {TOP_N} van {len(frame)})"
    return f"{noemer} ({len(frame)})"


def _tabel(frame: pd.DataFrame, titel: str) -> list[str]:
    """Rendert een DataFrame als Markdown-tabel met een vetgedrukte titelregel."""
    regels = [f"**{titel}**", ""]
    if frame.empty:
        return [*regels, "_geen_"]

    kolommen = list(frame.columns)
    uitlijning = ["---:" if _is_getal(frame[kolom]) else "---" for kolom in kolommen]
    regels.append("| " + " | ".join(kolommen) + " |")
    regels.append("| " + " | ".join(uitlijning) + " |")
    for rij in frame.itertuples(index=False):
        regels.append("| " + " | ".join(str(waarde) for waarde in rij) + " |")
    return regels


def _is_getal(kolom: pd.Series) -> bool:
    """Geeft aan of een kolom numeriek is en dus rechts uitgelijnd hoort te worden."""
    return pd.api.types.is_numeric_dtype(kolom)
