"""De geparseerde dataset bewaren, zodat een tweede run niet opnieuw hoeft te parsen.

Gemeten op De Wolden: het TTL parsen kost circa 180 s, de structuren teruglezen 1,4 s
en de rdflib-graaf teruglezen 58 s. De graaf wordt daarom pas ingelezen als een check
hem aanraakt; wie alleen geometrie- en netwerkchecks draait, betaalt hem niet.

Het gevaar van een cache is dat hij achterloopt. De sleutel bevat daarom niet alleen
de inhoud van de invoerbestanden maar ook de broncode van de lader en de versies van
rdflib en shapely: wijzigt daar iets, dan is het een andere sleutel en wordt er
opnieuw ingelezen.
"""

from __future__ import annotations

import os
import pickle
import time
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

import rdflib
import shapely
from rdflib import Graph

from gwswpijplijn import dataset as dataset_module
from gwswpijplijn import geometry as geometry_module
from gwswpijplijn.dataset import GwswDataset, load_dataset

# Losstaand van de bestandshashes, zodat een test hem kan verzetten.
LADER_VERSIE = "1"

BESTAND_STRUCTUREN = "structuren.pickle"
BESTAND_GRAAF = "graaf.pickle"


@dataclass(frozen=True)
class CacheUitslag:
    """Waar de dataset vandaan kwam en wat dat kostte."""

    bron: str  # 'cache' of 'bestand'
    sleutel: str
    seconden: float
    melding: str = ""


class LuieGraaf:
    """Een rdflib-graaf die pas van schijf komt als er iets uit gevraagd wordt.

    De checks gebruiken de graaf voor onderdelen die niet in de structuren zitten
    (hasPart, hasConnection, labels van drempels). Dat is een minderheid van de
    checks, en de graaf teruglezen kost 58 s; hem pas laden bij het eerste gebruik
    scheelt die tijd in alle andere runs.
    """

    def __init__(self, pad: Path) -> None:
        self._pad = pad
        self._graaf: Graph | None = None

    def _geladen(self) -> Graph:
        """Leest de graaf de eerste keer dat er iets uit gevraagd wordt."""
        if self._graaf is None:
            with self._pad.open("rb") as bestand:
                self._graaf = pickle.load(bestand)
        return self._graaf

    def __getattr__(self, naam: str):
        """Alles wat een graaf kan, kan deze plaatsvervanger ook."""
        return getattr(self._geladen(), naam)

    def __len__(self) -> int:
        """Het aantal triples."""
        return len(self._geladen())

    def __contains__(self, triple) -> bool:
        """Of een triple in de graaf staat."""
        return triple in self._geladen()

    def __iter__(self):
        """De triples zelf."""
        return iter(self._geladen())


def cachesleutel(dataset_path: Path, ontology_paths: list[Path]) -> str:
    """De sleutel van deze combinatie van invoer, lader en bibliotheken."""
    haas = sha256()
    haas.update(LADER_VERSIE.encode("utf-8"))
    haas.update(f"rdflib{rdflib.__version__}shapely{shapely.__version__}".encode())
    for module in (dataset_module, geometry_module):
        haas.update(Path(module.__file__).read_bytes())
    for pad in [Path(dataset_path), *sorted(Path(p) for p in ontology_paths)]:
        haas.update(pad.name.encode("utf-8"))
        haas.update(_bestandshash(pad).encode("utf-8"))
    return haas.hexdigest()[:32]


def _bestandshash(pad: Path) -> str:
    """De sha256 van een bestand, in blokken gelezen."""
    haas = sha256()
    with pad.open("rb") as bestand:
        for blok in iter(lambda: bestand.read(1 << 20), b""):
            haas.update(blok)
    return haas.hexdigest()


def standaard_cachemap() -> Path:
    """De cachemap volgens de XDG-conventie."""
    basis = os.environ.get("XDG_CACHE_HOME")
    return Path(basis or Path.home() / ".cache") / "gwswpijplijn"


def laad_met_cache(
    dataset_path: Path,
    ontology_paths: list[Path],
    cache_dir: Path | None = None,
    gebruik_cache: bool = True,
) -> tuple[GwswDataset, CacheUitslag]:
    """Leest de dataset uit de cache, of leest hem in en legt hem weg."""
    begin = time.perf_counter()
    if not gebruik_cache:
        dataset = load_dataset(dataset_path, ontology_paths)
        return dataset, CacheUitslag("bestand", "", time.perf_counter() - begin)

    sleutel = cachesleutel(dataset_path, ontology_paths)
    map_ = (cache_dir or standaard_cachemap()) / sleutel
    melding = ""
    if (map_ / BESTAND_STRUCTUREN).exists() and (map_ / BESTAND_GRAAF).exists():
        try:
            with (map_ / BESTAND_STRUCTUREN).open("rb") as bestand:
                velden = pickle.load(bestand)
            dataset = replace(
                GwswDataset(graph=Graph(), **velden), graph=LuieGraaf(map_ / BESTAND_GRAAF)
            )
            return dataset, CacheUitslag("cache", sleutel, time.perf_counter() - begin)
        except (pickle.UnpicklingError, EOFError, TypeError, AttributeError) as fout:
            melding = f"De cache in {map_} is onbruikbaar ({fout}); opnieuw ingelezen."

    dataset = load_dataset(dataset_path, ontology_paths)
    _schrijf(map_, dataset)
    return dataset, CacheUitslag("bestand", sleutel, time.perf_counter() - begin, melding)


def _schrijf(map_: Path, dataset: GwswDataset) -> None:
    """Legt structuren en graaf weg, elk via een tijdelijk bestand.

    Zonder die omweg laat een afgebroken run een half bestand achter dat de volgende
    run als geldige cache zou lezen.
    """
    map_.mkdir(parents=True, exist_ok=True)
    velden = {naam: waarde for naam, waarde in vars(dataset).items() if naam != "graph"}
    for naam, inhoud in ((BESTAND_STRUCTUREN, velden), (BESTAND_GRAAF, dataset.graph)):
        tijdelijk = map_ / f"{naam}.tijdelijk"
        with tijdelijk.open("wb") as bestand:
            pickle.dump(inhoud, bestand, protocol=5)
        tijdelijk.replace(map_ / naam)
