#!/usr/bin/env python
"""Schrijft de TTL-fixtures onder tests/fixtures/ttl.

Elke fixture bevat precies een ingebouwd defect, met bovenaan in een DEFECT-regel
wat dat defect is. De uitzondering is `selectie_rollen.ttl`: die bevat geen defect
maar een object per klassenrol, om de selecties uit `checks/selectie.py` te dekken.
De prelude met de klassenhierarchie is voor alle fixtures gelijk; die staat hier een
keer in plaats van twintig keer in de bestanden.

Gebruik:  uv run python scripts/maak_ttl_fixtures.py
"""

from pathlib import Path

DOEL = Path("tests/fixtures/ttl")

PRELUDE = """@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix geo:  <http://www.opengis.net/ont/geosparql#> .
@prefix gwsw: <http://data.gwsw.nl/1.6/totaal/> .
@prefix :     <http://example.org/toets#> .

# Minimale klassenhierarchie, zodat de fixture zonder de volle ontologie werkt.
gwsw:Inspectieput rdfs:subClassOf gwsw:Rioolput .
gwsw:LozePut rdfs:subClassOf gwsw:Rioolput .
gwsw:Lozingsput rdfs:subClassOf gwsw:Rioolput .
gwsw:Overstortput rdfs:subClassOf gwsw:Rioolput .
gwsw:Rioolput rdfs:subClassOf gwsw:Put .
gwsw:Putorientatie rdfs:subClassOf gwsw:Knooppunt .
gwsw:Compartimentorientatie rdfs:subClassOf gwsw:Knooppunt .
gwsw:Bouwwerkorientatie rdfs:subClassOf gwsw:Knooppunt .
gwsw:Leidingorientatie rdfs:subClassOf gwsw:Verbinding .
gwsw:GemengdRiool rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Hemelwaterriool rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Vuilwaterriool rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Infiltratieriool rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Overstortleiding rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:VrijvervalRioolleiding rdfs:subClassOf gwsw:Rioolleiding .
gwsw:Rioolleiding rdfs:subClassOf gwsw:Leiding .
gwsw:Persleiding rdfs:subClassOf gwsw:Leiding .
gwsw:Rioolgemaal rdfs:subClassOf gwsw:Gemaal .
gwsw:Uitlaatconstructie rdfs:subClassOf gwsw:Bouwwerk .
gwsw:Bergbezinkbassin rdfs:subClassOf gwsw:Bouwwerk .
gwsw:Valput rdfs:subClassOf gwsw:Rioolput .
gwsw:Duiker rdfs:subClassOf gwsw:Leiding .
gwsw:Zinker rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Drain rdfs:subClassOf gwsw:VrijvervalRioolleiding .
gwsw:Sloot rdfs:subClassOf gwsw:Oppervlaktewater .
"""


def put(
    naam: str, label: str, x: float, y: float, klasse: str = "Inspectieput", extra: str = ""
) -> str:
    return f''':{naam} rdf:type gwsw:{klasse} ; rdfs:label "{label}" ;
    gwsw:hasAspect :{naam}_ori .{extra}
:{naam}_ori rdf:type gwsw:Putorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>{x} {y}</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
'''


def leiding(
    naam: str,
    label: str,
    punten: list[tuple[float, float]],
    begin: str | None,
    eind: str | None,
    klasse: str = "GemengdRiool",
    bob: tuple[float, float] | None = None,
    kenmerken: str = "",
    literal: str | None = None,
) -> str:
    poslist = " ".join(f"{x} {y}" for x, y in punten)
    meetkunde = literal or (
        f'<gml:LineString xmlns:gml=\\"http://www.opengis.net/gml\\">'
        f'<gml:posList srsDimension=\\"2\\">{poslist}</gml:posList></gml:LineString>'
    )
    bob_begin = (
        f"\n:{naam}_b gwsw:hasAspect [ rdf:type gwsw:BobBeginpuntLeiding ; gwsw:hasValue {bob[0]} ] ."
        if bob
        else ""
    )
    bob_eind = (
        f"\n:{naam}_e gwsw:hasAspect [ rdf:type gwsw:BobEindpuntLeiding ; gwsw:hasValue {bob[1]} ] ."
        if bob
        else ""
    )
    koppel_begin = f"\n:{naam}_b gwsw:hasConnection :{begin}_ori ." if begin else ""
    koppel_eind = f"\n:{naam}_e gwsw:hasConnection :{eind}_ori ." if eind else ""
    return f''':{naam} rdf:type gwsw:{klasse} ; rdfs:label "{label}" ;
    gwsw:hasAspect :{naam}_ori .{kenmerken}
:{naam}_ori rdf:type gwsw:Leidingorientatie ;
    gwsw:hasPart :{naam}_b , :{naam}_e ;
    gwsw:hasAspect [ rdf:type gwsw:Lijn ;
        gwsw:hasValue "{meetkunde}"^^geo:gmlLiteral ] .
:{naam}_b rdf:type gwsw:BeginpuntLeiding .
:{naam}_e rdf:type gwsw:EindpuntLeiding .{bob_begin}{bob_eind}{koppel_begin}{koppel_eind}
'''


def kenmerken(naam: str, **waarden) -> str:
    """Hangt kenmerken aan een object; `_ref`-suffix maakt er een hasReference van."""
    regels = []
    for sleutel, waarde in waarden.items():
        if waarde is None:
            continue
        soort = sleutel.removesuffix("_ref")
        if sleutel.endswith("_ref"):
            regels.append(f"[ rdf:type gwsw:{soort} ; gwsw:hasReference gwsw:{waarde} ]")
        elif isinstance(waarde, str):
            regels.append(f'[ rdf:type gwsw:{soort} ; gwsw:hasValue "{waarde}"^^xsd:date ]')
        else:
            regels.append(f"[ rdf:type gwsw:{soort} ; gwsw:hasValue {waarde} ]")
    if not regels:
        return ""
    return f"\n:{naam} gwsw:hasAspect " + " ,\n    ".join(regels) + " ."


def maat(naam: str, breedte: int, hoogte: int, materiaal: str = "Beton", vorm: str = "Rond") -> str:
    return kenmerken(
        naam,
        BreedteLeiding=breedte,
        HoogteLeiding=hoogte,
        MateriaalLeiding_ref=materiaal,
        VormLeiding_ref=vorm,
    )


def maaiveld(naam: str, hoogte: float, wijze: str | None = None) -> str:
    """Hangt een maaiveldorientatie met maaiveldhoogte aan een putorientatie.

    Met `wijze` krijgt de orientatie ook een puntgeometrie met inwinning erop, zoals
    de BrutIS-export van De Wolden die schrijft: de inwinningswijze hangt daar aan
    het Punt-aspect en niet aan de maaiveldhoogte zelf.
    """
    if wijze is None:
        return f"""
:{naam}_ori gwsw:hasConnection :{naam}_maa .
:{naam}_maa rdf:type gwsw:Maaiveldorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Maaiveldhoogte ; gwsw:hasValue {hoogte} ] .
"""
    return f"""
:{naam}_ori gwsw:hasConnection :{naam}_maa .
:{naam}_maa rdf:type gwsw:Maaiveldorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Maaiveldhoogte ; gwsw:hasValue {hoogte} ] ;
    gwsw:hasAspect :{naam}_maa_pun .
:{naam}_maa_pun rdf:type gwsw:Punt ;
    gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>0.0 0.0</gml:pos></gml:Point>"^^geo:gmlLiteral ;
    gwsw:hasAspect [ rdf:type gwsw:Inwinning ;
        gwsw:hasAspect [ rdf:type gwsw:WijzeVanInwinning ; gwsw:hasReference gwsw:{wijze} ] ] .
"""


def deksel(naam: str, niveau: float, wijze: str | None = None, datum: str | None = None) -> str:
    """Hangt een putdeksel met dekselniveau (en eventueel inwinning) aan een put."""
    inwinning = ""
    if wijze or datum:
        delen = []
        if wijze:
            delen.append(f"[ rdf:type gwsw:WijzeVanInwinning ; gwsw:hasReference gwsw:{wijze} ]")
        if datum:
            delen.append(f'[ rdf:type gwsw:DatumInwinning ; gwsw:hasValue "{datum}"^^xsd:date ]')
        inwinning = (
            " ;\n        gwsw:hasAspect [ rdf:type gwsw:Inwinning ;\n            "
            "gwsw:hasAspect " + " ,\n            ".join(delen) + " ]"
        )
    return f"""
:{naam} gwsw:hasPart :{naam}_dek .
:{naam}_dek rdf:type gwsw:Putdeksel ;
    gwsw:hasAspect :{naam}_dek_ori .
:{naam}_dek_ori rdf:type gwsw:Dekselorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Putdekselniveau ; gwsw:hasValue {niveau}{inwinning} ] .
"""


def drempel(put: str, naam: str, niveau: float | None = None, breedte: float | None = None) -> str:
    """Hangt een overstortdrempel als onderdeel aan een put."""
    aspecten = kenmerken(naam, Drempelniveau=niveau, Drempelbreedte=breedte)
    return f'''
:{put} gwsw:hasPart :{naam} .
:{naam} rdf:type gwsw:Overstortdrempel ; rdfs:label "{naam}" .{aspecten}
'''


FIXTURES: dict[str, tuple[str, str]] = {}

# TOP-006: twee strengen op precies dezelfde lijn.
FIXTURES["top006_overlappende_streng.ttl"] = (
    "twee strengen liggen over hun volle lengte op elkaar",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB"),
)

# TOP-007: een streng zonder lengte.
FIXTURES["top007_nul_lengte.ttl"] = (
    "streng 2 heeft begin- en eindpunt op dezelfde plek",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1050.0, 2000.0), (1050.0, 2000.0)], "PutB", "PutB"),
)

# TOP-008: een streng met een knik van 2 m uit de rechte lijn.
FIXTURES["top008_boog.ttl"] = (
    "streng 1 buigt 2 m uit de rechte put-putverbinding",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1025.0, 2002.0), (1050.0, 2000.0)], "PutA", "PutB"),
)

# TOP-009: een put ver buiten het RD-bereik.
FIXTURES["top009_buiten_rd.ttl"] = (
    "put B ligt op x = 999999, ver buiten het RD-bereik",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 999999.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (999999.0, 2000.0)], "PutA", "PutB"),
)

# TOP-010: twee strengen die elkaar kruisen, met diameter.
FIXTURES["top010_buffer_kruising.ttl"] = (
    "twee strengen met diameter 400 kruisen elkaar zonder gedeelde put",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 1975.0)
    + put("PutD", "D", 1025.0, 2025.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1050.0, 2000.0)],
        "PutA",
        "PutB",
        kenmerken=maat("L1", 400, 400),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 1975.0), (1025.0, 2025.0)],
        "PutC",
        "PutD",
        kenmerken=maat("L2", 400, 400),
    ),
)

# TOP-011: dezelfde kruising, maar zonder diameters, zodat alleen de hartlijn telt.
FIXTURES["top011_hartlijnkruising.ttl"] = (
    "twee strengen zonder maatvoering kruisen elkaar; alleen de hartlijnen raken",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 1975.0)
    + put("PutD", "D", 1025.0, 2025.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1025.0, 1975.0), (1025.0, 2025.0)], "PutC", "PutD"),
)

# TOP-013: drie strengen tussen hetzelfde putpaar.
FIXTURES["top013_parallel.ttl"] = (
    "drie strengen verbinden dezelfde twee putten",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1000.0, 2000.0), (1025.0, 2001.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L3", "3", [(1000.0, 2000.0), (1025.0, 1999.0), (1050.0, 2000.0)], "PutA", "PutB"),
)

# TOP-014: vijf strengen op een put.
FIXTURES["top014_vijf_strengen.ttl"] = (
    "op put A sluiten vijf strengen aan",
    put("PutA", "A", 1000.0, 2000.0)
    + "".join(put(f"Put{i}", f"P{i}", 1000.0 + 10.0 * i, 2010.0 + 10.0 * i) for i in range(1, 6))
    + "".join(
        leiding(
            f"L{i}",
            f"{i}",
            [(1000.0, 2000.0), (1000.0 + 10.0 * i, 2010.0 + 10.0 * i)],
            "PutA",
            f"Put{i}",
        )
        for i in range(1, 6)
    ),
)

# TOP-015: een streng met een multi-geometrie.
FIXTURES["top015_multipart.ttl"] = (
    "streng 1 heeft een MultiCurve met twee losse delen",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [],
        "PutA",
        "PutB",
        literal=(
            '<gml:MultiCurve xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:curveMember>'
            '<gml:LineString><gml:posList srsDimension=\\"2\\">1000.0 2000.0 1020.0 2000.0'
            "</gml:posList></gml:LineString></gml:curveMember><gml:curveMember>"
            '<gml:LineString><gml:posList srsDimension=\\"2\\">1030.0 2000.0 1050.0 2000.0'
            "</gml:posList></gml:LineString></gml:curveMember></gml:MultiCurve>"
        ),
    ),
)

# TOP-016: een zelfsnijdende polygoon in de leidinggeometrie.
FIXTURES["top016_ongeldige_geometrie.ttl"] = (
    "streng 1 heeft een strikdas-polygoon als geometrie; die is niet OGC-geldig",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [],
        "PutA",
        "PutB",
        literal=(
            '<gml:Polygon xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:exterior>'
            '<gml:LinearRing><gml:posList srsDimension=\\"2\\">'
            "1000.0 2000.0 1050.0 2050.0 1050.0 2000.0 1000.0 2050.0 1000.0 2000.0"
            "</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
        ),
    ),
)

# TOP-017: een lijn die zichzelf kruist.
FIXTURES["top017_zelfkruisend.ttl"] = (
    "streng 1 kruist zichzelf",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1040.0, 2040.0), (1040.0, 2000.0), (1000.0, 2040.0)],
        "PutA",
        "PutB",
    ),
)

# TOP-018: een lijn met een spike.
FIXTURES["top018_spike.ttl"] = (
    "streng 1 heeft een knik van bijna nul graden: hij loopt terug over zichzelf",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0), (1010.0, 2000.0), (1050.0, 2000.0)],
        "PutA",
        "PutB",
    ),
)

# TOP-019: een loze put tussen twee gelijke strengen.
FIXTURES["top019_pseudoknoop.ttl"] = (
    "loze put B scheidt twee strengen met dezelfde diameter, materiaal en klasse",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0, klasse="LozePut")
    + put("PutC", "C", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0)],
        "PutA",
        "PutB",
        kenmerken=maat("L1", 300, 300),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 2000.0), (1050.0, 2000.0)],
        "PutB",
        "PutC",
        kenmerken=maat("L2", 300, 300),
    ),
)

# TOP-020: de lijn is tegen de administratieve richting in getekend.
FIXTURES["top020_omgekeerd_getekend.ttl"] = (
    "streng 1 is van B naar A getekend terwijl de administratie A naar B zegt",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1050.0, 2000.0), (1000.0, 2000.0)], "PutA", "PutB"),
)

# TOP-021: een put die naast een doorlopende streng ligt.
FIXTURES["top021_put_op_streng.ttl"] = (
    "put C ligt op streng 1 maar is er niet op aangesloten",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 2000.1)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB"),
)

# NET-003: de bodem stijgt in de administratieve richting.
FIXTURES["net003_tegen_de_richting.ttl"] = (
    "streng 1 loopt administratief van A naar B terwijl de bodem stijgt",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB", bob=(10.0, 10.5)),
)

# NET-005: een hemelwaterstreng midden tussen gemengde strengen.
FIXTURES["net005_afwijkend_stelseltype.ttl"] = (
    "streng 2 is hemelwater terwijl al haar buren gemengd zijn",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0)
    + put("PutC", "C", 1050.0, 2000.0)
    + put("PutD", "D", 1075.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1025.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "L2", "2", [(1025.0, 2000.0), (1050.0, 2000.0)], "PutB", "PutC", klasse="Hemelwaterriool"
    )
    + leiding("L3", "3", [(1050.0, 2000.0), (1075.0, 2000.0)], "PutC", "PutD"),
)

# NET-006: een put waar twee stelseltypen samenkomen.
FIXTURES["net006_koppeling_stelseltypen.ttl"] = (
    "op put B komen een gemengde en een hemelwaterstreng samen",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0)
    + put("PutC", "C", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1025.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "L2", "2", [(1025.0, 2000.0), (1050.0, 2000.0)], "PutB", "PutC", klasse="Hemelwaterriool"
    ),
)

# NET-008: drie lozingsputten in een deelstelsel van vier knopen.
FIXTURES["net008_veel_lozingspunten.ttl"] = (
    "een deelstelsel van vier knopen heeft drie lozingsputten",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutL1", "L1", 1025.0, 2010.0, klasse="Lozingsput")
    + put("PutL2", "L2", 1025.0, 2000.0, klasse="Lozingsput")
    + put("PutL3", "L3", 1025.0, 1990.0, klasse="Lozingsput")
    + leiding("La", "a", [(1000.0, 2000.0), (1025.0, 2010.0)], "PutA", "PutL1")
    + leiding("Lb", "b", [(1000.0, 2000.0), (1025.0, 2000.0)], "PutA", "PutL2")
    + leiding("Lc", "c", [(1000.0, 2000.0), (1025.0, 1990.0)], "PutA", "PutL3"),
)


# ---------------------------------------------------------------------------
# Blok A: ATTR, HGT, RVZ, ADM en BTR
# ---------------------------------------------------------------------------

STANDAARDPUT = dict(BreedtePut=1000, LengtePut=1000, MateriaalPut_ref="Beton", HoogtePut=1500)


def nette_put(
    naam: str, label: str, x: float, y: float, mv: float = 10.0, **extra_kenmerken
) -> str:
    """Een put met maatvoering, materiaal en maaiveldhoogte."""
    waarden = {**STANDAARDPUT, **extra_kenmerken}
    return put(naam, label, x, y, extra=kenmerken(naam, **waarden)) + maaiveld(naam, mv)


def nette_leiding(naam: str, label: str, punten, begin, eind, **extra) -> str:
    """Een leiding met materiaal, maatvoering, lengte en begindatum."""
    velden = {
        "BreedteLeiding": 300,
        "HoogteLeiding": 300,
        "MateriaalLeiding_ref": "Beton",
        "VormLeiding_ref": "Rond",
        "LengteLeiding": 50.0,
        "Begindatum": "1980-01-01",
    }
    velden.update(extra.pop("velden", {}))
    return leiding(naam, label, punten, begin, eind, kenmerken=kenmerken(naam, **velden), **extra)


A = (1000.0, 2000.0)
B = (1050.0, 2000.0)

FIXTURES["attr_schoon.ttl"] = (
    "geen; alle attributen zijn aannemelijk en onderling consistent",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB"),
)

FIXTURES["attr001_diameter_bij_materiaal.ttl"] = (
    "streng 1 is van PVC met een diameter van 1000 mm; PVC gaat tot 800 mm",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B, BreedtePut=2000, LengtePut=2000)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"BreedteLeiding": 1000, "HoogteLeiding": 1000, "MateriaalLeiding_ref": "PVC"},
    ),
)

FIXTURES["attr002_kleine_diameter.ttl"] = (
    "streng 1 heeft een diameter van 160 mm, onder de ondergrens van 200 mm",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"BreedteLeiding": 160, "HoogteLeiding": 160, "MateriaalLeiding_ref": "PVC"},
    ),
)

FIXTURES["attr003_pvc_te_vroeg.ttl"] = (
    "streng 1 is PVC met aanlegjaar 1940; PVC bestaat pas vanaf 1955",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"MateriaalLeiding_ref": "PVC", "Begindatum": "1940-01-01"},
    ),
)

FIXTURES["attr004_rond_ongelijk.ttl"] = (
    "streng 1 heet rond maar heeft breedte 300 en hoogte 400",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding(
        "L1", "1", [A, B], "PutA", "PutB", velden={"BreedteLeiding": 300, "HoogteLeiding": 400}
    ),
)

FIXTURES["attr005_centimeters.ttl"] = (
    "streng 1 heeft breedte en hoogte 30; maal tien is dat 300 mm, een handelsmaat",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding(
        "L1", "1", [A, B], "PutA", "PutB", velden={"BreedteLeiding": 30, "HoogteLeiding": 30}
    ),
)

FIXTURES["attr006_te_grote_streng.ttl"] = (
    "streng 1 is 1200 mm terwijl put B maar 800 bij 800 mm is",
    nette_put("PutA", "A", *A, BreedtePut=2000, LengtePut=2000)
    + nette_put("PutB", "B", *B, BreedtePut=800, LengtePut=800)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"BreedteLeiding": 1200, "HoogteLeiding": 1200},
    ),
)

FIXTURES["attr006_twee_te_kleine_putten.ttl"] = (
    "streng 1 is 1200 mm terwijl put A en put B allebei 800 bij 800 mm zijn",
    nette_put("PutA", "A", *A, BreedtePut=800, LengtePut=800)
    + nette_put("PutB", "B", *B, BreedtePut=800, LengtePut=800)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={"BreedteLeiding": 1200, "HoogteLeiding": 1200},
    ),
)

FIXTURES["attr007_toekomstig_jaar.ttl"] = (
    "streng 1 heeft begindatum 2099-01-01",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"Begindatum": "2099-01-01"}),
)

FIXTURES["attr008_lange_streng.ttl"] = (
    "streng 1 is administratief 500 m lang, boven de bovengrens van 200 m",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", (1500.0, 2000.0)[0], 2000.0)
    + nette_leiding(
        "L1",
        "1",
        [A, (1500.0, 2000.0)],
        "PutA",
        "PutB",
        velden={"LengteLeiding": 500.0},
    ),
)

FIXTURES["attr009_lengte_wijkt_af.ttl"] = (
    "streng 1 is 50 m getekend maar staat als 100 m geregistreerd",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"LengteLeiding": 100.0}),
)

FIXTURES["attr010_materiaal_put.ttl"] = (
    "gemetselde streng 1 komt uit op put B van kunststof",
    nette_put("PutA", "A", *A, MateriaalPut_ref="Metselwerk")
    + nette_put("PutB", "B", *B, MateriaalPut_ref="Kunststof")
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={
            "BreedteLeiding": 400,
            "HoogteLeiding": 600,
            "MateriaalLeiding_ref": "Metselwerk",
            "VormLeiding_ref": "Eivormig",
            "Begindatum": "1930-01-01",
        },
    ),
)

FIXTURES["attr012_metselwerk_rond.ttl"] = (
    "streng 1 is gemetseld met een rond profiel; metselwerk is ei-, muil- of heulvormig",
    nette_put("PutA", "A", *A, MateriaalPut_ref="Metselwerk")
    + nette_put("PutB", "B", *B, MateriaalPut_ref="Metselwerk")
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={
            "BreedteLeiding": 400,
            "HoogteLeiding": 400,
            "MateriaalLeiding_ref": "Metselwerk",
            "VormLeiding_ref": "Rond",
            "Begindatum": "1930-01-01",
        },
    ),
)

# --- HGT ------------------------------------------------------------------
#
# Het schone hoogtebeeld: maaiveld 10,00 m NAP, deksel 10,00, puthoogte 1,50 m
# (bodem dus 8,50) en een BOB die van 8,60 naar 8,55 daalt over 50 m.

C = (1100.0, 2000.0)


def hoogteput(
    naam, label, punt, mv=10.0, dek=10.0, hoogte=1500, mv_wijze=None, dek_wijze=None, **extra
):
    """Een put met maaiveld, putdeksel en puthoogte.

    Met `dek=None` krijgt de put geen putdeksel. Zo ziet de De Wolden-export eruit:
    daarin komt `Putdekselniveau` geen enkele keer voor, zodat de hoogtechecks op de
    maaiveldhoogte terugvallen.
    """
    waarden = {**STANDAARDPUT, "HoogtePut": hoogte}
    waarden.update(extra)
    return (
        put(naam, label, punt[0], punt[1], extra=kenmerken(naam, **waarden))
        + maaiveld(naam, mv, mv_wijze)
        + (deksel(naam, dek, dek_wijze) if dek is not None else "")
    )


def hoogteleiding(naam, label, punten, begin, eind, bob, **velden):
    """Een leiding met BOB's en standaardmaatvoering."""
    basis = {
        "BreedteLeiding": 300,
        "HoogteLeiding": 300,
        "MateriaalLeiding_ref": "Beton",
        "VormLeiding_ref": "Rond",
        "LengteLeiding": 50.0,
        "Begindatum": "1980-01-01",
    }
    basis.update(velden)
    return leiding(naam, label, punten, begin, eind, bob=bob, kenmerken=kenmerken(naam, **basis))


FIXTURES["hgt_schoon.ttl"] = (
    "geen; hoogten en verhang zijn onderling consistent",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.50)),
)

FIXTURES["hgt004_bob_boven_deksel.ttl"] = (
    "de BOB van streng 1 ligt op 10,50 m NAP, boven het deksel van put A op 10,00",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(10.50, 8.55)),
)

FIXTURES["hgt005_tegenverhang_licht.ttl"] = (
    "de bodem van streng 1 stijgt 0,02 m in de afvoerrichting",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.62)),
)

FIXTURES["hgt006_tegenverhang_fors.ttl"] = (
    "de bodem van streng 1 stijgt 0,30 m in de afvoerrichting",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.90)),
)

FIXTURES["hgt007_te_weinig_verhang.ttl"] = (
    "gemengde streng 1 daalt 0,01 m over 50 m: 0,2 promille",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.59)),
)

FIXTURES["hgt008_extreem_verhang.ttl"] = (
    "streng 1 daalt 5 m over 50 m: 1 op 10",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, mv=5.0, dek=5.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 3.60)),
)

FIXTURES["hgt009_bob_sprong.ttl"] = (
    "op put B komt de BOB op 8,55 binnen en gaat op 8,00 verder, zonder valput",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, hoogte=2500)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.00, 7.95)),
)

FIXTURES["hgt010_diameterverjonging.ttl"] = (
    "op put B komt 400 mm binnen en gaat 300 mm verder",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteput("PutC", "C", C)
    + hoogteleiding(
        "L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55), BreedteLeiding=400, HoogteLeiding=400
    )
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.55, 8.50)),
)

FIXTURES["hgt011_drempel_onder_bob.ttl"] = (
    "de drempel van overstortput B ligt op 8,00 terwijl de aanvoerende BOB op 8,55 ligt",
    hoogteput("PutA", "A", A)
    + put(
        "PutB",
        "B",
        B[0],
        B[1],
        klasse="Overstortput",
        extra=kenmerken(
            "PutB", BreedtePut=1000, LengtePut=1000, HoogtePut=1500, MateriaalPut_ref="Beton"
        ),
    )
    + maaiveld("PutB", 10.0)
    + deksel("PutB", 10.0)
    + drempel("PutB", "DrempelB", niveau=8.00, breedte=2000.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

FIXTURES["hgt012_putdiepte.ttl"] = (
    "put B heeft een puthoogte van 12 m, boven de grens van 6 m",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, hoogte=12000)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

FIXTURES["hgt013_gronddekking.ttl"] = (
    "streng 1 ligt met 0,20 m grond op de buiskruin onder de minimale dekking",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(9.50, 9.48)),
)

FIXTURES["hgt014_maaiveldverloop.ttl"] = (
    "het maaiveld daalt 3 m terwijl de leiding maar 0,05 m daalt",
    hoogteput("PutA", "A", A, mv=12.0, dek=12.0, hoogte=3500)
    + hoogteput("PutB", "B", B, mv=9.0, dek=9.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

FIXTURES["hgt015_putbodem_te_hoog.ttl"] = (
    "de bodem van put B ligt op 9,50 terwijl de laagste aansluitende BOB op 8,55 ligt",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, hoogte=500)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

FIXTURES["hgt016_bob_boven_bodem.ttl"] = (
    "de BOB komt 1,45 m boven de bodem van put B binnen, zonder val- of zandvangconstructie",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, hoogte=1500)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(10.00, 9.95)),
)

FIXTURES["hgt017_z_wijkt_af.ttl"] = (
    "de z-waarden van de lijn staan op 5,00 terwijl de BOB's rond 8,60 liggen",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + leiding(
        "L1",
        "1",
        [],
        "PutA",
        "PutB",
        bob=(8.60, 8.55),
        kenmerken=kenmerken(
            "L1",
            BreedteLeiding=300,
            HoogteLeiding=300,
            MateriaalLeiding_ref="Beton",
            VormLeiding_ref="Rond",
            LengteLeiding=50.0,
        ),
        literal=(
            '<gml:LineString xmlns:gml=\\"http://www.opengis.net/gml\\">'
            '<gml:posList srsDimension=\\"3\\">1000.0 2000.0 5.0 1050.0 2000.0 5.0'
            "</gml:posList></gml:LineString>"
        ),
    ),
)

FIXTURES["hgt018_buiskruin_boven_maaiveld.ttl"] = (
    "de buiskruin van streng 1 ligt op 10,30 m NAP, boven het deksel op 10,00",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(9.98, 8.55)),
)

# --- RVZ ------------------------------------------------------------------

FIXTURES["rvz_schoon.ttl"] = (
    "geen; een gemengd stelsel met een aangesloten overstortput die op een sloot loost",
    hoogteput("PutA", "A", A)
    + put(
        "PutO",
        "O",
        B[0],
        B[1],
        klasse="Overstortput",
        extra=kenmerken(
            "PutO", BreedtePut=1000, LengtePut=1000, HoogtePut=1500, MateriaalPut_ref="Beton"
        ),
    )
    + maaiveld("PutO", 10.0)
    + deksel("PutO", 10.0)
    + drempel("PutO", "DrempelO", niveau=9.00, breedte=2000.0)
    + hoogteput("PutU", "U", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55))
    + hoogteleiding(
        "L2", "2", [B, C], "PutO", "PutU", bob=(9.00, 8.95), Begindatum="1980-01-01"
    ).replace("gwsw:GemengdRiool", "gwsw:Overstortleiding")
    + """:Sloot1 rdf:type gwsw:Sloot ; rdfs:label "sloot" ;
    gwsw:hasAspect :Sloot1_ori .
:Sloot1_ori rdf:type gwsw:Putorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1062.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
""",
)

FIXTURES["rvz001_losse_overstort.ttl"] = (
    "overstortput O hangt aan geen enkele streng",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + put("PutO", "O", C[0], C[1], klasse="Overstortput")
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

FIXTURES["rvz004_overstort_zonder_water.ttl"] = (
    "overstortput O ligt 500 m van de enige sloot",
    hoogteput("PutA", "A", A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput")
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55))
    + """:Sloot1 rdf:type gwsw:Sloot ; rdfs:label "sloot" ;
    gwsw:hasAspect :Sloot1_ori .
:Sloot1_ori rdf:type gwsw:Putorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1550.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
""",
)

FIXTURES["rvz005_overstort_op_hemelwater.ttl"] = (
    "overstortput O hangt uitsluitend aan een hemelwaterstreng",
    hoogteput("PutA", "A", A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput")
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55)).replace(
        "gwsw:GemengdRiool", "gwsw:Hemelwaterriool"
    ),
)

FIXTURES["rvz006_gemengd_zonder_overstort.ttl"] = (
    "een gemengd deelstelsel zonder enige overstort of bergbezinkvoorziening",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)


def bbb(naam: str, label: str, punt, met_maten: bool = True) -> str:
    """Een bergbezinkbassin, desgewenst met afmetingen."""
    maten = (
        kenmerken(naam, BreedteBouwwerk=4000, LengteBouwwerk=8000, Inhoud=120) if met_maten else ""
    )
    return (
        put(naam, label, punt[0], punt[1], klasse="Bergbezinkbassin", extra=maten)
        + maaiveld(naam, 10.0)
        + deksel(naam, 10.0)
    )


D = (1150.0, 2000.0)

FIXTURES["rvz007_bbb_zonder_berging.ttl"] = (
    "bergbezinkbassin BBB heeft geen inhoud en geen afmetingen",
    hoogteput("PutA", "A", A)
    + bbb("BBB", "BBB", B, met_maten=False)
    + drempel("BBB", "DrempelBBB", niveau=9.5, breedte=2000.0)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "BBB", bob=(8.60, 8.50))
    + hoogteleiding("L2", "2", [B, C], "BBB", "PutC", bob=(8.50, 8.40)),
)

FIXTURES["rvz008_bbb_zonder_lediging.ttl"] = (
    "bergbezinkbassin BBB heeft geen ledigingsvoorziening en geen afvoerende streng",
    hoogteput("PutA", "A", A)
    + bbb("BBB", "BBB", B)
    + drempel("BBB", "DrempelBBB", niveau=9.5, breedte=2000.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "BBB", bob=(8.60, 8.50)),
)

FIXTURES["rvz009_bbb_zonder_nooduitlaat.ttl"] = (
    "bergbezinkbassin BBB heeft geen overstortdrempel en geen overstortleiding",
    hoogteput("PutA", "A", A)
    + bbb("BBB", "BBB", B)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "BBB", bob=(8.60, 8.50))
    + hoogteleiding("L2", "2", [B, C], "BBB", "PutC", bob=(8.50, 8.40)),
)

FIXTURES["rvz010_interne_overstort.ttl"] = (
    "de overstortleiding tussen B en C heeft aan beide zijden gemengde strengen",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteput("PutC", "C", C)
    + hoogteput("PutD", "D", (1150.0, 2000.0))
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.55, 8.50)).replace(
        "gwsw:GemengdRiool", "gwsw:Overstortleiding"
    )
    + hoogteleiding("L3", "3", [C, (1150.0, 2000.0)], "PutC", "PutD", bob=(8.50, 8.45)),
)

FIXTURES["rvz011_te_weinig_waking.ttl"] = (
    "de drempel van overstortput O ligt 0,10 m onder het deksel",
    hoogteput("PutA", "A", A)
    + put(
        "PutO",
        "O",
        B[0],
        B[1],
        klasse="Overstortput",
        extra=kenmerken(
            "PutO", BreedtePut=1000, LengtePut=1000, HoogtePut=1500, MateriaalPut_ref="Beton"
        ),
    )
    + maaiveld("PutO", 10.0)
    + deksel("PutO", 10.0)
    + drempel("PutO", "DrempelO", niveau=9.90, breedte=2000.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55)),
)

# --- ADM ------------------------------------------------------------------

FIXTURES["adm002_dubbel_label.ttl"] = (
    "twee verschillende putten dragen allebei de identificatie A",
    nette_put("PutA", "A", *A)
    + nette_put("PutA2", "A", 1010.0, 2010.0)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB"),
)

FIXTURES["adm006_vervallen_object.ttl"] = (
    "streng 1 heeft een einddatum in 2001 maar hangt nog aan twee putten",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"Einddatum": "2001-01-01"}),
)

FIXTURES["adm007_overstort_zonder_functie.ttl"] = (
    "overstortput O heeft geen overstortleiding en geen drempel",
    nette_put("PutA", "A", *A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput")
    + nette_leiding("L1", "1", [A, B], "PutA", "PutO"),
)

FIXTURES["adm008_losse_compartimenten.ttl"] = (
    "put B heeft twee compartimenten zonder onderlinge verbinding",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB")
    + """:PutB gwsw:hasPart :PutB_c1 , :PutB_c2 .
:PutB_c1 rdf:type gwsw:Compartiment ; rdfs:label "B/c1" ;
    gwsw:hasAspect :PutB_c1_ori .
:PutB_c1_ori rdf:type gwsw:Compartimentorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1050.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
:PutB_c2 rdf:type gwsw:Compartiment ; rdfs:label "B/c2" ;
    gwsw:hasAspect :PutB_c2_ori .
:PutB_c2_ori rdf:type gwsw:Compartimentorientatie ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1050.5 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
""",
)

FIXTURES["adm009_leiding_aan_put.ttl"] = (
    "streng 1 hangt aan put B als geheel terwijl die twee compartimenten heeft",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB")
    + """:PutB gwsw:hasPart :PutB_c1 , :PutB_c2 .
:PutB_c1 rdf:type gwsw:Compartiment ; rdfs:label "B/c1" ;
    gwsw:hasAspect :PutB_c1_ori .
:PutB_c1_ori rdf:type gwsw:Compartimentorientatie .
:PutB_c2 rdf:type gwsw:Compartiment ; rdfs:label "B/c2" ;
    gwsw:hasAspect :PutB_c2_ori .
:PutB_c2_ori rdf:type gwsw:Compartimentorientatie .
:PutB_c1_ori gwsw:hasConnection :PutB_c2_ori .
""",
)

# --- BTR ------------------------------------------------------------------

_BTR_PUNTEN = [(1000.0 + 50.0 * i, 2000.0) for i in range(41)]

FIXTURES["btr006_afgeronde_bobs.ttl"] = (
    "veertig strengen met BOB's die allemaal precies op een halve decimeter vallen",
    "".join(
        hoogteput(
            f"Put{i}",
            f"P{i}",
            punt,
            mv=round(20.0 + 0.013 * i, 3),
            dek=round(19.99 + 0.013 * i, 3),
            hoogte=5000,
        )
        for i, punt in enumerate(_BTR_PUNTEN)
    )
    + "".join(
        hoogteleiding(
            f"Lb{i}",
            f"b{i}",
            [_BTR_PUNTEN[i], _BTR_PUNTEN[i + 1]],
            f"Put{i}",
            f"Put{i + 1}",
            bob=(round(16.0 - 0.05 * i, 2), round(16.0 - 0.05 * (i + 1), 2)),
        )
        for i in range(40)
    ),
)


# --- EXT en AHN ------------------------------------------------------------
#
# Deze fixture hoort bij tests/fixtures/gis/ext (zie scripts/maak_gis_fixtures.py).
# Het studiegebied loopt van (980, 1980) tot (1120, 2020) en het hoogteraster staat
# overal op 10,00 m NAP, met een nodata-vlek rond (1040, 2010).

EXT_A = (1000.0, 2000.0)
EXT_B = (1050.0, 2000.0)
EXT_C = (1090.0, 2000.0)
EXT_D = (2000.0, 2000.0)
EXT_E = (1000.0, 2010.0)
EXT_F = (1040.0, 2010.0)

# Datakarakteristieken: jaarprecisie van de datums en expliciete onbekend-waarden.
# Vier strengen met een begindatum, waarvan drie op 1 januari; vier putten met een
# maaiveldhoogte, waarvan twee met een inwinningswijze en een daarvan NietAchterhaald.
_KAR_PUNTEN = [(1000.0 + 40.0 * i, 2000.0) for i in range(5)]

FIXTURES["karakteristiek_datums.ttl"] = (
    "geen; deze fixture legt eigenschappen van de dataset vast, geen defect",
    hoogteput("KarA", "A", _KAR_PUNTEN[0], mv_wijze="AHN2")
    + hoogteput("KarB", "B", _KAR_PUNTEN[1], mv_wijze="NietAchterhaald")
    + hoogteput("KarC", "C", _KAR_PUNTEN[2])
    + hoogteput("KarD", "D", _KAR_PUNTEN[3])
    + hoogteput("KarE", "E", _KAR_PUNTEN[4])
    + hoogteleiding(
        "KarL1", "1", _KAR_PUNTEN[0:2], "KarA", "KarB", bob=(9.5, 9.4), Begindatum="1975-01-01"
    )
    + hoogteleiding(
        "KarL2", "2", _KAR_PUNTEN[1:3], "KarB", "KarC", bob=(9.4, 9.3), Begindatum="1980-01-01"
    )
    + hoogteleiding(
        "KarL3", "3", _KAR_PUNTEN[2:4], "KarC", "KarD", bob=(9.3, 9.2), Begindatum="1992-01-01"
    )
    # Deze ene valt niet op 1 januari, dus de precisie is niet gemaskeerd.
    + hoogteleiding(
        "KarL4", "4", _KAR_PUNTEN[3:5], "KarD", "KarE", bob=(9.2, 9.1), Begindatum="2003-07-04"
    ),
)

FIXTURES["ext_scenario.ttl"] = (
    "meerdere; deze fixture voedt de EXT- en AHN-checks tegelijk, zie de tests",
    # Put A: maaiveld en deksel gelijk aan het AHN.
    hoogteput("PutA", "A", EXT_A, mv=10.00, dek=10.00)
    # Put B: 0,10 m afwijking van het AHN, dus HGT-001. Zijn maaiveldhoogte komt
    # zelf uit het AHN; de vergelijking met het raster is voor deze put dus een
    # vergelijking van twee hoogtemodellen.
    + hoogteput("PutB", "B", EXT_B, mv=10.10, dek=10.10, mv_wijze="AHN2", dek_wijze="AHN2")
    # Put C: 0,50 m afwijking, dus HGT-002; en geen BGT-deksel in de buurt.
    + hoogteput("PutC", "C", EXT_C, mv=10.50, dek=10.50, mv_wijze="Inmeting", dek_wijze="Inmeting")
    # Put D ligt buiten het studiegebied en mag geen enkele uitslag krijgen.
    + hoogteput("PutD", "D", EXT_D, mv=99.00, dek=99.00)
    # Put F ligt op de nodata-vlek van het raster.
    # Put E heeft geen putdekselniveau, net als elke put in De Wolden. De hoogtechecks
    # vallen dan terug op de maaiveldhoogte, en die komt hier uit AHN2. Zijn afwijking
    # is 0,08 m, dus hij komt in HGT-001 terecht.
    + hoogteput("PutE", "E", EXT_E, mv=10.08, dek=None, mv_wijze="AHN2")
    + hoogteput("PutF", "F", EXT_F, mv=12.00, dek=12.00)
    # Lozingsput ver van het water; Lozingsput vlakbij water-1.
    + put("PutL1", "L1", 1005.0, 1990.0, klasse="Lozingsput")
    + put("PutL2", "L2", 1072.0, 2008.0, klasse="Lozingsput")
    # Streng 1 loopt door pand-1 heen: EXT-001.
    + hoogteleiding("L1", "1", [EXT_A, EXT_B], "PutA", "PutB", bob=(11.00, 9.50))
    # Streng 2 kruist water-1 en is geen duiker: EXT-002 en EXT-003.
    + hoogteleiding("L2", "2", [EXT_B, EXT_C], "PutB", "PutC", bob=(9.50, 6.30))
    # Streng 3 is een zinker die water-2 kruist: wel EXT-002, geen EXT-003. Een zinker
    # is in de ontologie een VrijvervalRioolleiding en zit dus in de populatie.
    + hoogteleiding("L3", "3", [EXT_E, EXT_F], "PutE", "PutF", bob=(9.60, 9.55)).replace(
        "gwsw:GemengdRiool", "gwsw:Zinker"
    )
    # Streng 6 is een duiker op dezelfde route: een duiker is geen rioolleiding
    # (subklasse van Leiding, niet van VrijvervalRioolleiding) en valt buiten de
    # populatie van EXT-002 en EXT-003; geen van beide meldt hem.
    + leiding("L6", "6", [EXT_E, EXT_F], "PutE", "PutF", klasse="Duiker")
    # Streng 4 verbindt de lozingsputten met het net.
    + hoogteleiding("L4", "4", [EXT_C, (1072.0, 2008.0)], "PutC", "PutL2", bob=(9.40, 9.35))
    + "\n"
    # Put P, put Q en streng "4" liggen binnen het BGT-pand; EXT-001 moet ze als
    # "binnen" melden, in tegenstelling tot streng "1" die de gevel kruist. Ze
    # krijgen geen maaiveldhoogte, BOB of inwinning, zodat ze de HGT- en BTR-tests
    # niet raken -- vandaar `put`/`leiding` en niet `hoogteput`/`hoogteleiding`.
    + '# Put P, put Q en streng "4" liggen binnen het BGT-pand (1020, 1998)-(1030, 2002);\n'
    + '# EXT-001 moet ze als "binnen" melden, in tegenstelling tot streng "1" die de gevel\n'
    + "# kruist. Ze krijgen geen maaiveldhoogte, BOB of inwinning, zodat ze de HGT- en\n"
    + "# BTR-tests niet raken.\n"
    + put("PutP", "P", 1022.0, 2000.0)
    + put("PutQ", "Q", 1028.0, 2000.0)
    + leiding("L5", "4", [(1022.0, 2000.0), (1028.0, 2000.0)], "PutP", "PutQ"),
)


# Geen check maar de klassenselecties uit checks/selectie.py: het Juinen-voorbeeld
# bevat maar zes van de veertien rollen, en een selectie die stil leeg blijft leest
# als "die rol komt niet voor". Hier staat precies een object per ontbrekende rol.
FIXTURES["selectie_rollen.ttl"] = (
    "geen -- deze fixture dekt de klassenselecties, niet een gebrek",
    # Bergbezinkleiding staat niet in de gedeelde prelude; alleen deze fixture heeft
    # hem nodig. De regel gaat met een toelichting mee het bestand in, zodat hij daar
    # niet als een losse zwerver leest.
    "# Alleen deze fixture heeft de bergbezinkleiding nodig; de gedeelde prelude"
    " kent haar niet.\n"
    "gwsw:Bergbezinkleiding rdfs:subClassOf gwsw:VrijvervalRioolleiding .\n\n"
    + put("Put1", "Put1", 1000.0, 2000.0)
    + put("Lozing1", "Lozing1", 1050.0, 2000.0, klasse="Lozingsput")
    + put("Val1", "Val1", 1200.0, 2000.0, klasse="Valput")
    # Overstortput en loze put staan hier ook, zodat de fixture alle veertien rollen
    # dekt zonder het Juinen-voorbeeld: dat staat in data/ en ontbreekt in een
    # schone kloon, en dan zou de dekkingstest stil overslaan.
    + put("Overstort1", "Overstort1", 1250.0, 2000.0, klasse="Overstortput")
    + put("Loos1", "Loos1", 1300.0, 2000.0, klasse="LozePut")
    # Een uitlaatconstructie en een bergbezinkbassin zijn bouwwerken, geen putten;
    # hun orientatie is dus een Bouwwerkorientatie.
    + put("Uitlaat1", "Uitlaat1", 1100.0, 2000.0, klasse="Uitlaatconstructie").replace(
        "gwsw:Putorientatie", "gwsw:Bouwwerkorientatie"
    )
    + put("Bbb1", "Bbb1", 1150.0, 2000.0, klasse="Bergbezinkbassin").replace(
        "gwsw:Putorientatie", "gwsw:Bouwwerkorientatie"
    )
    + leiding("L1", "L1", [(1000.0, 2000.0), (1050.0, 2000.0)], "Put1", "Lozing1")
    + leiding(
        "L2",
        "L2",
        [(1050.0, 2000.0), (1100.0, 2000.0)],
        "Lozing1",
        "Uitlaat1",
        klasse="Overstortleiding",
    )
    + leiding(
        "L3",
        "L3",
        [(1100.0, 2000.0), (1150.0, 2000.0)],
        "Uitlaat1",
        "Bbb1",
        klasse="Bergbezinkleiding",
    )
    + leiding(
        "L4",
        "L4",
        [(1150.0, 2000.0), (1200.0, 2000.0)],
        "Bbb1",
        "Val1",
        klasse="Infiltratieriool",
    )
    # Een persleiding is wel een gwsw:Leiding maar geen vrijvervalrioolleiding.
    + leiding("P1", "P1", [(1200.0, 2000.0), (1250.0, 2000.0)], "Val1", None, klasse="Persleiding")
    # Oppervlaktewater is lijnvormig en komt dus bij de verbindingen terecht.
    + leiding("Sloot1", "Sloot1", [(1000.0, 2100.0), (1250.0, 2100.0)], None, None, klasse="Sloot"),
)


# Een streng waarvan de GML-literaal een lijn met precies een coordinaat bevat. GEOS
# weigert die, en de lader hoort het object als onleesbaar te tellen in plaats van af
# te breken. Er staat een gezonde streng naast, zodat zichtbaar is dat de rest
# gewoon doorloopt.
FIXTURES["geometriefout.ttl"] = (
    "streng 2 heeft een lijngeometrie met maar een coordinaat en is dus onleesbaar",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "L2",
        "2",
        [],
        "PutB",
        "PutC",
        literal=(
            '<gml:LineString xmlns:gml=\\"http://www.opengis.net/gml\\">'
            '<gml:posList srsDimension=\\"2\\">1050.0 2000.0</gml:posList></gml:LineString>'
        ),
    ),
)


def render(defect: str, inhoud: str) -> str:
    """De volledige tekst van een fixture: de prelude, de DEFECT-regel en de inhoud.

    Staat apart van `main` zodat `tests/test_ttl_fixtures.py` dezelfde regel gebruikt
    om te bewaken dat de bestanden op schijf nog bij dit script passen. Zou de test
    de opmaak overschrijven, dan bewaakte hij zijn eigen kopie.
    """
    return f"{PRELUDE}\n# DEFECT: {defect}\n\n{inhoud}"


def main() -> None:
    DOEL.mkdir(parents=True, exist_ok=True)
    for naam, (defect, inhoud) in FIXTURES.items():
        (DOEL / naam).write_text(render(defect, inhoud), encoding="utf-8")
        print(naam)


if __name__ == "__main__":
    main()
