"""Eén gedeelde lezer voor de CSV's die deze package schrijft (issue #165).

`schrijf_csv` levert sinds issue #165 een NL-Excel-bestand: puntkomma als
scheidingsteken, komma als decimaalteken en een UTF-8-BOM. Een test die zo'n CSV
terugleest met de pandas-standaard (`,`-decimaal, geen BOM-afhandeling) leest de
X/Y-getallen verkeerd en krijgt een `﻿` vóór de eerste kolomnaam. Deze helper
zet de drie opties op één plek, zodat de veertien-en-meer lezingen in `tests/` niet
elk hun eigen variant dragen.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def lees_csv(pad: str | Path, **opties: object) -> pd.DataFrame:
    """Leest een `;`-gescheiden NL-Excel-CSV met komma-decimaal en BOM-afhandeling.

    Extra opties (`dtype=str`, `keep_default_na=False`) gaan ongewijzigd door naar
    `pandas.read_csv`; ze overschrijven de standaarden hier niet, maar vullen ze aan.
    """
    return pd.read_csv(pad, sep=";", decimal=",", encoding="utf-8-sig", **opties)  # type: ignore[arg-type]
