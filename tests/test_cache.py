"""Tests voor de datasetcache.

De cache mag nooit een ander antwoord geven dan opnieuw inlezen. Het gevaarlijkste
geval is een cache die achterloopt op de lader; daarom zit de broncode van de lader
in de sleutel.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gwswpijplijn.cache import cachesleutel, laad_met_cache
from gwswpijplijn.dataset import load_dataset

DATA = Path(__file__).resolve().parents[1] / "data"
VOORBEELD = DATA / "gwsw_orox_ttl" / "GwswDataset__Voorbeeld_v1_6_orox.ttl"

pytestmark = pytest.mark.skipif(
    not VOORBEELD.exists(), reason="het OroX-voorbeeldbestand staat niet in data/"
)


def test_de_cache_geeft_dezelfde_dataset_terug(tmp_path: Path) -> None:
    koud, eerste = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    warm, tweede = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)

    assert eerste.bron == "bestand"
    assert tweede.bron == "cache"
    assert set(warm.nodes) == set(koud.nodes)
    assert set(warm.conduits) == set(koud.conduits)
    assert warm.subclasses == koud.subclasses
    assert warm.source == koud.source


def test_de_graaf_werkt_ook_uit_de_cache(tmp_path: Path) -> None:
    """De graaf wordt lui geladen; hij moet zich als een graaf blijven gedragen."""
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    warm, _ = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    vers = load_dataset(VOORBEELD, [])

    assert len(warm.graph) == len(vers.graph)
    uri = next(iter(warm.nodes))
    assert set(warm.subjects_of_class("Put")) == set(vers.subjects_of_class("Put"))
    assert warm.beheerobjecttype(uri) == vers.beheerobjecttype(uri)


def test_de_sleutel_verandert_mee_met_de_lader(tmp_path: Path, monkeypatch) -> None:
    eerste = cachesleutel(VOORBEELD, [])
    monkeypatch.setattr("gwswpijplijn.cache.LADER_VERSIE", "gewijzigd")

    assert cachesleutel(VOORBEELD, []) != eerste


def test_een_beschadigde_cache_leidt_tot_opnieuw_inlezen(tmp_path: Path) -> None:
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)
    for bestand in tmp_path.rglob("*.pickle"):
        bestand.write_bytes(b"dit is geen pickle")

    dataset, uitslag = laad_met_cache(VOORBEELD, [], cache_dir=tmp_path)

    assert dataset.nodes
    assert uitslag.bron == "bestand"
    assert "cache" in uitslag.melding.lower()


def test_zonder_cache_wordt_er_niets_weggeschreven(tmp_path: Path) -> None:
    laad_met_cache(VOORBEELD, [], cache_dir=tmp_path, gebruik_cache=False)

    assert list(tmp_path.rglob("*.pickle")) == []
