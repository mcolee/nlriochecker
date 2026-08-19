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

# En wat er in de kolom Lengte staat bij een object dat er geen heeft: een put. Een
# eigen constante, want hij betekent iets anders dan een ontbrekend stelseltype.
GEEN_LENGTE = "—"


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


def omvangtabel(run: CheckRun) -> pd.DataFrame:
    """Een rij per objecttype en stelseltype, met aantallen en meters.

    De meters staan alleen bij verbindingen, en het is de **getekende** lengte: dat
    is wat er op de kaart ligt. Wijkt hij af van het kenmerk `LengteLeiding`, dan is
    dat een bevinding van ATTR-009 en die staat verderop in het rapport.

    Lange vorm en geen kruistabel: het aantal stelseltypen ligt niet vast -- een put
    waar twee stelsels samenkomen draagt ze allebei -- en een kruistabel zou daar
    kolommen bij krijgen tot hij niet meer op een scherm past.

    Alleen objecten met een bruikbare geometrie tellen mee, ook zonder studiegebied.
    Mét een gebied gebeurde dat al vanzelf -- `objecten_in_gebied` kan een object
    zonder plek niet binnen een vlak leggen -- en zonder gebied telde de tabel ze wel,
    zodat dezelfde export twee verschillende aantallen opleverde naargelang er een
    gebied was opgegeven. `omvang_toelichting` telt wat er zo buiten valt.
    """
    binnen = run.objecten_binnen()
    stelsels = stelseltypen(run)
    aantallen: defaultdict[tuple[str, str], int] = defaultdict(int)
    meters: defaultdict[tuple[str, str], float] = defaultdict(float)

    for uri, node in run.dataset.nodes.items():
        if not _telt_mee(uri, binnen, node.point):
            continue
        aantallen[(run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))] += 1
    for uri, conduit in run.dataset.conduits.items():
        if not _telt_mee(uri, binnen, conduit.line):
            continue
        sleutel = (run.dataset.beheerobjecttype(uri), stelsels.get(uri, GEEN_STELSEL))
        aantallen[sleutel] += 1
        if conduit.line is not None:
            meters[sleutel] += conduit.line.length

    rijen = [
        {
            "Objecttype": objecttype or "(zonder type)",
            "Stelsel": stelsel or GEEN_STELSEL,
            "Aantal": aantal,
            "Lengte (m)": round(meters[(objecttype, stelsel)])
            if meters.get((objecttype, stelsel))
            else GEEN_LENGTE,
        }
        for (objecttype, stelsel), aantal in sorted(aantallen.items())
    ]
    return pd.DataFrame(rijen, columns=KOLOMMEN)


def _telt_mee(uri: str, binnen: frozenset[str] | None, geometrie: object) -> bool:
    """Of dit object in de tabel hoort: binnen het gebied en met een plek op de kaart."""
    if binnen is not None and uri not in binnen:
        return False
    return geometrie is not None and not geometrie.is_empty  # type: ignore[attr-defined]


def zonder_geometrie(run: CheckRun) -> int:
    """Het aantal objecten dat geen plek op de kaart heeft en dus niet in de tabel staat.

    Compartimenten en hulpstukken zonder eigen punt, bijvoorbeeld. Ze bestaan wel en de
    checks zien ze; ze zijn alleen niet te tekenen en niet aan een gebied toe te wijzen.
    Zwijgen zou de tabel als volledig laten lezen.
    """
    if run.objecten_binnen() is not None:
        return 0
    zonder = sum(1 for node in run.dataset.nodes.values() if _leeg(node.point))
    return zonder + sum(1 for conduit in run.dataset.conduits.values() if _leeg(conduit.line))


def _leeg(geometrie: object) -> bool:
    """Of een geometrie ontbreekt of leeg is."""
    return geometrie is None or geometrie.is_empty  # type: ignore[attr-defined]
