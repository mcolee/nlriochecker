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

import logging
import os
import pickle
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from hashlib import sha256
from pathlib import Path

import rdflib
import shapely
from rdflib import Graph

from gwswpijplijn import dataset as dataset_module
from gwswpijplijn import geometry as geometry_module
from gwswpijplijn.dataset import GwswDataset, load_dataset

logger = logging.getLogger(__name__)

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
    checks, en de graaf teruglezen kost tot een minuut; hem pas laden bij het eerste
    gebruik scheelt die tijd in alle andere runs.

    Blijkt de graafcache zelf beschadigd (de structurencache was dat niet, anders
    was er nooit een `LuieGraaf` gemaakt), dan is dat geen fout: `_herstel` leest
    de graaf alsnog uit de brondata en de cache wordt opnieuw weggeschreven, zodat
    de volgende aanraking weer de snelle weg neemt. `cache.py` stelt die functie
    samen; deze klasse kent zelf geen paden naar de brondata en geen `load_dataset`.
    """

    def __init__(self, pad: Path, herstel: Callable[[], Graph]) -> None:
        self._pad = pad
        self._herstel = herstel
        self._graaf: Graph | None = None

    def _geladen(self) -> Graph:
        """Leest de graaf de eerste keer dat er iets uit gevraagd wordt."""
        if self._graaf is None:
            begin = time.perf_counter()
            try:
                with self._pad.open("rb") as bestand:
                    self._graaf = pickle.load(bestand)
            except (pickle.UnpicklingError, EOFError, TypeError, AttributeError) as fout:
                logger.warning(
                    "De graafcache in %s is onbruikbaar (%s); graaf opnieuw "
                    "ingelezen uit de brondata.",
                    self._pad,
                    fout,
                )
                self._graaf = self._herstel()
                _schrijf_atomair(self._pad, self._graaf)
            logger.info(
                "Graaf van schijf gelezen in %.1f s (%d triples).",
                time.perf_counter() - begin,
                len(self._graaf),
            )
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
    pad_structuren = map_ / BESTAND_STRUCTUREN
    pad_graaf = map_ / BESTAND_GRAAF
    if pad_structuren.exists() and pad_graaf.exists():
        try:
            with pad_structuren.open("rb") as bestand:
                velden = pickle.load(bestand)
        except (pickle.UnpicklingError, EOFError, TypeError, AttributeError) as fout:
            melding = f"De cache in {map_} is onbruikbaar ({fout}); opnieuw ingelezen."
        else:
            # De structurencache is geldig; de graafcache wordt niet hier al
            # gelezen (dat kost tot een minuut) maar pas als een check hem
            # aanraakt. Is die dan beschadigd, dan herstelt LuieGraaf zichzelf
            # via deze functie in plaats van de hele run te laten crashen.
            herstel = partial(_herlees_graaf, dataset_path, ontology_paths)
            dataset = replace(
                GwswDataset(graph=Graph(), **velden), graph=LuieGraaf(pad_graaf, herstel)
            )
            return dataset, CacheUitslag("cache", sleutel, time.perf_counter() - begin)

    dataset = load_dataset(dataset_path, ontology_paths)
    _schrijf(map_, dataset)
    return dataset, CacheUitslag("bestand", sleutel, time.perf_counter() - begin, melding)


def _herlees_graaf(dataset_path: Path, ontology_paths: list[Path]) -> Graph:
    """Leest de rdflib-graaf opnieuw uit de brondata; herstelweg voor `LuieGraaf`.

    Alleen `cache.py` kent paden en `load_dataset`; `LuieGraaf` krijgt enkel deze
    kant-en-klare functie mee en hoeft van beide dus niets te weten.
    """
    return load_dataset(dataset_path, ontology_paths).graph


def _schrijf(map_: Path, dataset: GwswDataset) -> None:
    """Legt structuren en graaf weg, elk via een tijdelijk bestand."""
    velden = {naam: waarde for naam, waarde in vars(dataset).items() if naam != "graph"}
    _schrijf_atomair(map_ / BESTAND_STRUCTUREN, velden)
    _schrijf_atomair(map_ / BESTAND_GRAAF, dataset.graph)


def _schrijf_atomair(pad: Path, inhoud: object) -> None:
    """Schrijft eerst naar een tijdelijk bestand en hernoemt dan atomisch.

    Zonder die omweg laat een afgebroken schrijfactie een half bestand achter dat
    een volgende lezer als geldige cache zou lezen. Zowel het wegschrijven van een
    verse dataset als het zelfherstel van een beschadigde `LuieGraaf` lopen via
    deze functie, dus de garantie geldt voor beide schrijfmomenten.
    """
    pad.parent.mkdir(parents=True, exist_ok=True)
    tijdelijk = pad.with_name(f"{pad.name}.tijdelijk")
    with tijdelijk.open("wb") as bestand:
        pickle.dump(inhoud, bestand, protocol=5)
    tijdelijk.replace(pad)
