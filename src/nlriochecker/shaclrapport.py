"""Inlezen van de SHACL-nulmetingrapporten die de GWSW-server oplevert."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from nlriochecker.errors import ReportFormatError

ENCODING = "utf-8"
DELIMITER = ";"

KOLOMMEN = [
    "Focus node",
    "Source",
    "Value",
    "Severity",
    "Message",
    "Path",
    "Detail-message",
    "Detail-value",
]

SLEUTEL_CFK = "SHACL-meting op basis CFK"
SLEUTEL_DATASET = "Gevalideerd RDF-bestand"
SLEUTEL_TIJDSTEMPEL = "Rapport SHACL-meting dd"
SLEUTEL_PROCESSOR = "Gebruikte SHACL-processor"
SLEUTEL_ONDERDELEN = "Gevalideerd op onderdelen"
SLEUTEL_NIET = "Niet gevalideerd op"
SLEUTEL_CONFORMS = "Rapport 'conforms'"

VORM_TE_GLOBAAL = "CfkTypes_typ"

DETAIL_TYPE = re.compile(r"\btype=([^,]+)")
DETAIL_LABEL = re.compile(r"\blabel=([^,]+)")


@dataclass(frozen=True)
class ShaclReport:
    """Een SHACL-nulmeting van een dataset tegen een conformiteitsklasse."""

    cfk: str
    dataset_file: str
    timestamp: datetime
    processor: str
    conforms: bool
    validated_parts: list[str]
    not_validated: str
    source_file: Path
    findings: pd.DataFrame

    @property
    def too_generic_classes(self) -> list[str]:
        """De klassen die deze CFK te globaal noemt.

        De SHACL-meting rapporteert dat per klasse, niet per object: de focus node
        van een CfkTypes_typ-melding is de klassenaam zelf.
        """
        meldingen = self.findings
        globaal = meldingen[meldingen["Source"] == VORM_TE_GLOBAAL]
        return sorted(set(globaal["Focus node"]))


def lees_shacl_rapport(path: Path) -> ShaclReport:
    """Leest een SHACL-rapport-CSV en geeft het terug als `ShaclReport`."""
    path = Path(path)
    rijen = _lees_rijen(path)
    kop_index = _kop_index(path, rijen)
    kopblok = _kopblok(rijen[:kop_index])

    return ShaclReport(
        cfk=_verplicht(path, kopblok, SLEUTEL_CFK),
        dataset_file=_verplicht(path, kopblok, SLEUTEL_DATASET),
        timestamp=_tijdstempel(path, kopblok),
        processor=kopblok.get(SLEUTEL_PROCESSOR, ""),
        conforms=kopblok.get(SLEUTEL_CONFORMS, "").strip().lower() == "true",
        validated_parts=_lijst(kopblok.get(SLEUTEL_ONDERDELEN, "")),
        not_validated=kopblok.get(SLEUTEL_NIET, ""),
        source_file=path,
        findings=_meldingen(path, rijen, kop_index),
    )


def _lees_rijen(path: Path) -> list[list[str]]:
    """Leest het hele bestand als CSV-rijen."""
    try:
        with path.open(encoding=ENCODING, newline="") as bestand:
            return list(csv.reader(bestand, delimiter=DELIMITER))
    except OSError as error:
        raise ReportFormatError(f"{path}: bestand kan niet gelezen worden ({error}).") from error
    except UnicodeDecodeError as error:
        raise ReportFormatError(f"{path}: geen geldige {ENCODING} ({error}).") from error
    except csv.Error as error:
        raise ReportFormatError(f"{path}: geen leesbare CSV ({error}).") from error


def _kop_index(path: Path, rijen: list[list[str]]) -> int:
    """De regel met de kolomkop; die staat niet op een vaste plek."""
    for index, rij in enumerate(rijen):
        if rij and rij[0].strip() == KOLOMMEN[0]:
            return index
    raise ReportFormatError(
        f"{path}: geen kolomkop met {KOLOMMEN[0]!r} gevonden. Is dit een SHACL-rapport "
        f"van de GWSW-server?"
    )


def _kopblok(rijen: list[list[str]]) -> dict[str, str]:
    """Het kopblok als sleutel-waardeparen."""
    blok: dict[str, str] = {}
    for rij in rijen:
        if len(rij) >= 2 and rij[0].strip():
            blok[rij[0].strip().strip('"')] = rij[1].strip()
    return blok


def _verplicht(path: Path, kopblok: dict[str, str], sleutel: str) -> str:
    """Haalt een verplichte kopwaarde op."""
    waarde = kopblok.get(sleutel, "").strip()
    if not waarde:
        raise ReportFormatError(f"{path}: het kopblok mist {sleutel!r}.")
    return waarde


def _tijdstempel(path: Path, kopblok: dict[str, str]) -> datetime:
    """Het tijdstip van de meting uit het kopblok."""
    rauw = _verplicht(path, kopblok, SLEUTEL_TIJDSTEMPEL)
    try:
        return datetime.fromisoformat(rauw)
    except ValueError as error:
        raise ReportFormatError(
            f"{path}: tijdstempel {rauw!r} is geen geldige ISO-datum."
        ) from error


def _lijst(waarde: str) -> list[str]:
    """Splitst een kommagescheiden opsomming uit het kopblok."""
    return [deel.strip() for deel in waarde.split(",") if deel.strip()]


def _meldingen(path: Path, rijen: list[list[str]], kop_index: int) -> pd.DataFrame:
    """Bouwt de meldingtabel, aangevuld met Label en Objecttype uit Detail-value."""
    kop = [naam.strip() for naam in rijen[kop_index] if naam.strip()]
    if kop != KOLOMMEN:
        raise ReportFormatError(
            f"{path}: onverwachte kolommen. Verwacht {KOLOMMEN}, gevonden {kop}."
        )

    inhoud = [rij[: len(KOLOMMEN)] for rij in rijen[kop_index + 1 :] if rij and any(rij)]
    meldingen = pd.DataFrame(inhoud, columns=KOLOMMEN).fillna("")
    for kolom in KOLOMMEN:
        meldingen[kolom] = meldingen[kolom].astype(str).str.strip()

    detail = meldingen["Detail-value"]
    meldingen["Objecttype"] = detail.str.extract(DETAIL_TYPE, expand=False).fillna("").str.strip()
    meldingen["Label"] = detail.str.extract(DETAIL_LABEL, expand=False).fillna("").str.strip()

    return meldingen
