"""Een `Melding` bouwen met alleen de velden die een test aangaan.

Meerdere testbestanden hadden hun eigen versie van deze constructor. Een gedeelde
plek voorkomt dat ze uit elkaar lopen zodra `Melding` een veld krijgt.
"""

from __future__ import annotations

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
