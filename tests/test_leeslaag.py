"""De leeslaag-delegaties van issue #166 geven byte-gelijk wat het oude lichaam gaf.

`leeslaag.houders` en `leeslaag.kenmerkinstanties` werden bij de bump naar
`gwsw-orox-helpers` v0.2.4 éénregelige delegaties naar `GwswDataset.houders`/`dragers`
respectievelijk `GwswDataset.kenmerkinstanties`. Deze test reproduceert het vroegere lichaam
(vóór #166) ter plekke en eist dat de delegatie er per fixture-object en per kenmerk exact
dezelfde lijst -- inclusief volgorde -- uit geeft. Zo is de gelijkheid met het oude gedrag
bewezen naast het byte-gelijke gouden ledger.

De fixtures dekken beide paden echt: `adm009_leiding_aan_put` draagt `hasPart`- en
`hasAspect`-relaties (put- en leidingonderdelen), `attr014_wibon_hasvalue` draagt
kenmerkinstanties met `hasValue`/`hasReference`. De coverage-asserts onderaan borgen dat de
paden niet stil leeg blijven.
"""

from __future__ import annotations

from pathlib import Path

from gwsw_orox_helpers.dataset import aspect_holders_of, load_dataset, part_holders_of
from gwsw_orox_helpers.namen import termen_voor
from rdflib import RDF, URIRef

from nlriochecker import leeslaag
from nlriochecker.checkconfig import FALLBACK_ENCODING

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

# Kenmerktypen die in attr014_wibon_hasvalue voorkomen (korte GWSW-namen).
KENMERKEN = ("BreedtePut", "MateriaalLeiding", "MateriaalPut", "LengtePut", "HoogtePut")


def _oud_houders(dataset, uri: str, *, aspecten: bool) -> list[str]:
    """Het lichaam van `leeslaag.houders` van vóór issue #166, ter vergelijking."""
    term = leeslaag._term(dataset, uri)
    graaf = dataset.graph
    gevonden = [str(houder) for houder in part_holders_of(graaf, term)]
    if aspecten:
        gevonden += [str(houder) for houder in aspect_holders_of(graaf, term)]
    return gevonden


def _oud_kenmerkinstanties(dataset, kenmerk: str) -> list[str]:
    """Het lichaam van `leeslaag.kenmerkinstanties` van vóór issue #166, ter vergelijking."""
    basis = termen_voor(dataset.gwsw_versie.basis).basis
    kenmerk_uri = URIRef(basis + kenmerk)
    return [str(instantie) for instantie in dataset.graph.subjects(RDF.type, kenmerk_uri)]


def test_houders_delegatie_is_gelijk_aan_het_oude_lichaam() -> None:
    """`leeslaag.houders` (delegatie) == het oude lichaam, per object en beide standen."""
    dataset = load_dataset(
        TTL_DIR / "adm009_leiding_aan_put.ttl", fallback_encoding=FALLBACK_ENCODING
    )
    objecten = set(dataset.nodes) | set(dataset.conduits)
    onderdelen = {deel for uri in objecten for deel in leeslaag.onderdelen_van(dataset, uri)}
    te_toetsen = objecten | onderdelen

    gedekt = 0
    for uri in sorted(te_toetsen):
        for aspecten in (False, True):
            verwacht = _oud_houders(dataset, uri, aspecten=aspecten)
            assert leeslaag.houders(dataset, uri, aspecten=aspecten) == verwacht
            gedekt += len(verwacht)
    # De hasPart-onderdelen hebben echt een houder; anders toetst de gelijkheid alleen leegte.
    assert gedekt > 0


def test_kenmerkinstanties_delegatie_is_gelijk_aan_het_oude_lichaam() -> None:
    """`leeslaag.kenmerkinstanties` (delegatie) == het oude lichaam, per kenmerktype."""
    dataset = load_dataset(
        TTL_DIR / "attr014_wibon_hasvalue.ttl", fallback_encoding=FALLBACK_ENCODING
    )
    gedekt = 0
    for kenmerk in KENMERKEN:
        verwacht = _oud_kenmerkinstanties(dataset, kenmerk)
        assert leeslaag.kenmerkinstanties(dataset, kenmerk) == verwacht
        gedekt += len(verwacht)
    assert gedekt > 0
