"""Wat er in het gebied ligt: de aantallen per objecttype en stelseltype.

Het bevindingenrapport opent met deze tabel. De lezer wil eerst weten waar het over
gaat -- hoeveel putten, hoeveel meter riool, van welk stelsel -- en pas daarna of het
in orde is.

De telling gaat over de **kern**: de objecten binnen het studiegebied. De contextschil
zit wel in de dataset van de run, want de netwerkchecks hebben hem nodig, maar er wordt
niet over gerapporteerd; hij staat als voetnoot onder de tabel. Zonder studiegebied is
alles kern.

`stelseltypen` staat hier omdat zowel deze tabel als de GeoPackage hem nodig heeft. Hij
stond in `gpkg.py`; twee kopieen zouden op een dag verschillende stelsels aan dezelfde
put toekennen.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckRun

KOLOMMEN = ["Objecttype", "Stelsel", "Aantal", "Lengte (m)"]

# Wat er in de kolom Stelsel staat als een object er geen heeft. Een leeg veld leest
# als een ontbrekende waarde in de tabel; dit zegt wat het is.
GEEN_STELSEL = "—"


def stelseltypen(run: CheckRun) -> dict[str, str]:
    """Het stelseltype per streng, en per put dat van de aansluitende strengen.

    Het GWSW legt het stelseltype op de leiding vast; een put ontleent het aan wat
    erop uitkomt. Komen daar meerdere soorten samen, dan staan ze er allemaal --
    dat is voor NET-006 juist het interessante geval.
    """
    config = run.config if run.config is not None else load_check_config()
    dataset = run.dataset
    per_object: dict[str, str] = {}
    per_put: dict[str, set[str]] = defaultdict(set)

    for uri, conduit in dataset.conduits.items():
        soort = config.klassen.stelseltype(conduit.types, dataset.closure)
        if soort is None:
            continue
        per_object[uri] = soort
        for kant in (conduit.start_node, conduit.end_node):
            knoop = dataset.resolve_network_node(kant, config.klassen.netwerkknopen)
            if knoop is not None:
                per_put[knoop].add(soort)

    for knoop, soorten in per_put.items():
        per_object[knoop] = ", ".join(sorted(soorten))
    return per_object


def kern(run: CheckRun) -> frozenset[str] | None:
    """De objecten waarover gerapporteerd wordt, of None zonder studiegebied."""
    return run.objecten_binnen()


def omvangtabel(run: CheckRun) -> pd.DataFrame:
    """Een rij per objecttype en stelseltype, met aantallen en meters.

    De meters staan alleen bij verbindingen, en het is de **getekende** lengte: dat
    is wat er op de kaart ligt. Wijkt hij af van het kenmerk `LengteLeiding`, dan is
    dat een bevinding van ATTR-009 en die staat verderop in het rapport.

    Lange vorm en geen kruistabel: het aantal stelseltypen ligt niet vast -- een put
    waar twee stelsels samenkomen draagt ze allebei -- en een kruistabel zou daar
    kolommen bij krijgen tot hij niet meer op een scherm past.
    """
    binnen = kern(run)
    stelsels = stelseltypen(run)
    aantallen: defaultdict[tuple[str, str], int] = defaultdict(int)
    meters: defaultdict[tuple[str, str], float] = defaultdict(float)

    for uri in run.dataset.nodes:
        if binnen is not None and uri not in binnen:
            continue
        aantallen[(run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))] += 1
    for uri, conduit in run.dataset.conduits.items():
        if binnen is not None and uri not in binnen:
            continue
        sleutel = (run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))
        aantallen[sleutel] += 1
        if conduit.line is not None and not conduit.line.is_empty:
            meters[sleutel] += conduit.line.length

    rijen = [
        {
            "Objecttype": objecttype or "(zonder type)",
            "Stelsel": stelsel or GEEN_STELSEL,
            "Aantal": aantal,
            "Lengte (m)": round(meters[(objecttype, stelsel)])
            if meters.get((objecttype, stelsel))
            else GEEN_STELSEL,
        }
        for (objecttype, stelsel), aantal in sorted(aantallen.items())
    ]
    return pd.DataFrame(rijen, columns=KOLOMMEN)
