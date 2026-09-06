"""Re-export van de meldingidentificatie (issue #160).

De echte definitie woont sinds issue #160 in de bladmodule `nlriochecker.identiteit`,
zodat `nulbevinding` haar kan lezen zonder een importkring te sluiten. Deze module
blijft als vindplaats bestaan omdat de uitvoerlaag (`melding.py`, `gpkg.py`) haar
zo importeert; wie nieuw code schrijft mag rechtstreeks uit `nlriochecker.identiteit`
lezen.
"""

from __future__ import annotations

from nlriochecker.identiteit import ID_LENGTE, kort, melding_id

__all__ = ["ID_LENGTE", "kort", "melding_id"]
