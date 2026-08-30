"""Een `Melding` of een `Nulbevinding` bouwen met alleen de velden die een test aangaan.

Drie testbestanden hadden hun eigen versie van de meldingconstructor
(`test_uitvoer_objectkaart.py`, `test_uitvoer_synthese.py`,
`test_uitvoer_rapportopbouw.py`). Een gedeelde plek voorkomt dat ze uit elkaar lopen
zodra `Melding` een veld krijgt. `nulbevinding` staat hier om dezelfde reden: hij komt
uit `test_uitvoer_melding.py` en wordt ook door `test_uitvoer_gelijkheid.py` gebruikt.
"""

from __future__ import annotations

from nlriochecker.nulbevinding import Nulbevinding
from nlriochecker.uitvoer.melding import Melding


def melding(**velden: object) -> Melding:
    """Een melding met neutrale standaardwaarden; overschrijf wat de test nodig heeft."""
    basis: dict[str, object] = {
        "melding_id": "0000000000000000",
        "check_id": "TOP-011",
        "categorie": "TOP",
        "bron": "register",
        "ernst": "F",
        "dimensie": "Consistentie",
        "object_uri": "http://example.org/toets#PutA",
        "object_id": "PutA",
        "object_label": "A",
        "object2_uri": "",
        "object2_id": "",
        "object2_label": "",
        "boodschap": "Er is iets mis met dit object.",
        "waarde": "",
        "drempel": "",
        "typering_betrouwbaar": True,
        "cluster_id": "",
        "scope": "geen_studiegebied",
        "gebied": "",
        "prioriteit": 2,
        "systemisch": False,
        "foutlocatie": None,
        "run_datum": "2026-08-19",
        "dataset": "toets.ttl",
    }
    basis.update(velden)
    if "categorie" not in velden and "check_id" in velden:
        basis["categorie"] = str(velden["check_id"]).split("-", 1)[0]
    return Melding(**basis)  # type: ignore[arg-type]


def nulbevinding(**overschrijf: object) -> Nulbevinding:
    """Een nulbevinding met verder onbelangrijke velden ingevuld.

    De standaardwaarden wijzen naar `PutA`, de put die de meeste TTL-fixtures kennen;
    een test die een ander object nodig heeft overschrijft `object_uri`, `object_label`
    en `objecttype`.
    """
    velden: dict[str, object] = {
        "check_id": "NULMETING-Put_HoogtePut_card",
        "vorm": "Put_HoogtePut_card",
        "focus_node": "PutA",
        "ernst": "F",
        "object_uri": "http://example.org/toets#PutA",
        "object_label": "A",
        "objecttype": "Inspectieput",
        "boodschap": "aantal voorkomens wijkt af (exact=1)",
        "waarde": "te weinig voorkomens",
        "cfk": ("MdsPlan", "MdsProj"),
        "systemisch": False,
        "herleid": True,
    }
    velden.update(overschrijf)
    return Nulbevinding(**velden)  # type: ignore[arg-type]
