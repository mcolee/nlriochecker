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
gwsw:Persleiding rdfs:subClassOf gwsw:MechanischeTransportleiding .
gwsw:MechanischeTransportleiding rdfs:subClassOf gwsw:Transportleiding .
gwsw:Transportleiding rdfs:subClassOf gwsw:Leiding .
gwsw:Rioolgemaal rdfs:subClassOf gwsw:Gemaal .
gwsw:Uitlaatconstructie rdfs:subClassOf gwsw:Bouwwerk .
gwsw:Bergbezinkbassin rdfs:subClassOf gwsw:Bouwwerk .
gwsw:Valput rdfs:subClassOf gwsw:Rioolput .
gwsw:Duiker rdfs:subClassOf gwsw:Leiding .
gwsw:Zinker rdfs:subClassOf gwsw:VrijvervalRioolleiding .
# Drain en Aansluitleiding hangen in de GWSW-ontologie rechtstreeks onder Leiding en
# niet onder VrijvervalRioolleiding (geverifieerd in de gebundelde ontologie); de
# prelude zei dat van Drain tot issue #82 verkeerd.
gwsw:Drain rdfs:subClassOf gwsw:Leiding .
gwsw:Aansluitleiding rdfs:subClassOf gwsw:Leiding .
gwsw:Sloot rdfs:subClassOf gwsw:Oppervlaktewater .
"""


def put(
    naam: str,
    label: str,
    x: float,
    y: float,
    klasse: str = "Inspectieput",
    extra: str = "",
    orientatie: str = "Putorientatie",
) -> str:
    return f''':{naam} rdf:type gwsw:{klasse} ; rdfs:label "{label}" ;
    gwsw:hasAspect :{naam}_ori .{extra}
:{naam}_ori rdf:type gwsw:{orientatie} ;
    gwsw:hasAspect [ rdf:type gwsw:Punt ;
        gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>{x} {y}</gml:pos></gml:Point>"^^geo:gmlLiteral ] .
'''


# Hulpstukken staan niet in de gedeelde prelude: alleen de fixtures van issue #60 hebben
# ze nodig, mét de functierestrictie waar TOP-022/TOP-023 het verwachte aantal leidingen
# uit lezen. Een fixture die dit blok opneemt krijgt ook de owl-prefix; een prefixregel
# mag in Turtle overal op statementniveau staan.
HULPSTUK_KLASSEN = (
    "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
    "# Hulpstukken, met de functierestrictie uit de GWSW-ontologie (issue #60).\n"
    "gwsw:Hulpstukorientatie rdfs:subClassOf gwsw:Knooppunt .\n"
    # Zoals in de echte ontologie draagt Verbindingsstuk zelf een functie zonder aantal;
    # T_stuk_Speciaal bestaat daar niet en staat hier om de overerving te toetsen: hij
    # heeft geen eigen restrictie en moet die van T_stuk krijgen, terwijl T_stuk zelf
    # zijn eigen restrictie houdt en niet die van Verbindingsstuk erft.
    "gwsw:Verbindingsstuk rdfs:subClassOf gwsw:Hulpstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:VerbindenVanLeidingen ] .\n"
    "gwsw:Afsluitstuk rdfs:subClassOf gwsw:Hulpstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:AfsluitenVanLeidingen ] .\n"
    "gwsw:T_stuk rdfs:subClassOf gwsw:Verbindingsstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:VerbindenVanDrieLeidingen ] .\n"
    "gwsw:T_stuk_Speciaal rdfs:subClassOf gwsw:T_stuk .\n"
    "gwsw:Kruisstuk rdfs:subClassOf gwsw:Verbindingsstuk ,\n"
    "    [ a owl:Restriction ; owl:onProperty gwsw:functie ;"
    " owl:hasValue gwsw:VerbindenVanVierLeidingen ] .\n\n"
)

# De loze leiding staat niet in de gedeelde prelude; alleen de fixtures van issue #62
# hebben haar nodig. Ze hangt onder Leiding en niet onder VrijvervalRioolleiding.
LOZE_KLASSE = "gwsw:LozeLeiding rdfs:subClassOf gwsw:Leiding .\n\n"

# De pompunit ("pompput in een drukrioleringsstelsel") hangt in de GWSW-ontologie onder
# Rioolput; alleen de fixtures van issue #104 hebben haar nodig.
POMP_KLASSE = "gwsw:Pompunit rdfs:subClassOf gwsw:Rioolput .\n\n"

# De twee drainageklassen die wél onder VrijvervalRioolleiding hangen (geverifieerd in de
# gebundelde ontologie: DIT-riool en DT-riool zijn rioolleidingen met doorlatende wanden).
# `Drain` staat in de prelude en hangt rechtstreeks onder Leiding; alleen de
# ATTR-001-fixture van issue #86 heeft deze twee nodig.
DRAINAGE_KLASSEN = (
    "gwsw:DIT_riool rdfs:subClassOf gwsw:VrijvervalRioolleiding .\n"
    "gwsw:DT_riool rdfs:subClassOf gwsw:VrijvervalRioolleiding .\n\n"
)


def hulpstuk(naam: str, label: str, x: float, y: float, klasse: str = "T_stuk") -> str:
    """Een hulpstuk: als een put, maar met een Hulpstukorientatie als knooppunt."""
    return put(naam, label, x, y, klasse=klasse, orientatie="Hulpstukorientatie")


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
    de BrutIS-export van De Wolden en Hoogeveen die schrijft: de inwinningswijze hangt daar aan
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


def deksel(
    naam: str,
    niveau: float,
    wijze: str | None = None,
    datum: str | None = None,
    klasse: str = "Putdeksel",
) -> str:
    """Hangt een putdeksel met dekselniveau (en eventueel inwinning) aan een put.

    Met `klasse` een subklasse als `Putdeksel_ZwaarVerkeer`; de fixture moet die dan
    zelf als subklasse van Putdeksel declareren, want de prelude kent haar niet.
    """
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
:{naam}_dek rdf:type gwsw:{klasse} ;
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


# Issue #100: de twee drempels van TOP-006 zelf. Drie paren die alleen in tolerantie en
# in samenvallengte verschillen, zodat de drempelgrens het enige is wat ze scheidt.
def _drempelpaar(nummer: int, y: float, lengte: float, afstand: float) -> str:
    """Twee strengen tussen dezelfde putten, `afstand` uit elkaar over `lengte` meter."""
    return (
        put(f"DrempelA{nummer}", f"DA{nummer}", 1000.0, y)
        + put(f"DrempelB{nummer}", f"DB{nummer}", 1000.0 + lengte, y)
        + leiding(
            f"D{nummer}a",
            f"D{nummer}a",
            [(1000.0, y), (1000.0 + lengte, y)],
            f"DrempelA{nummer}",
            f"DrempelB{nummer}",
        )
        + leiding(
            f"D{nummer}b",
            f"D{nummer}b",
            [(1000.0, y + afstand), (1000.0 + lengte, y + afstand)],
            f"DrempelA{nummer}",
            f"DrempelB{nummer}",
        )
    )


FIXTURES["top006_drempels.ttl"] = (
    "alleen paar 1 hoort te melden -- 3 m samenval op 1 cm. Paar 2 ligt even dicht maar "
    "valt over 1,5 m samen (onder de minimumlengte 2,0 m) en paar 3 valt lang samen maar "
    "op 4 cm (buiten de tolerantie 0,02 m); issue #100",
    _drempelpaar(1, 2000.0, 3.0, 0.01)
    + _drempelpaar(2, 2100.0, 1.5, 0.01)
    + _drempelpaar(3, 2200.0, 10.0, 0.04),
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


# Issue #82: TOP-006, TOP-010 en TOP-011 toetsen alleen paren waarvan beide leidingen een
# VrijvervalRioolleiding of een Duiker zijn. Twee groepen van elk drie paren, met dezelfde
# drie partnerklassen: bovenin kruist de partner de vrijvervalstreng (TOP-010 en TOP-011),
# onderin ligt hij er over zijn volle lengte op (TOP-006). Alleen het duikerpaar hoort in
# beide groepen te melden; het drain- en het aansluitleidingpaar vallen buiten de populatie.
def _kruispaar(nummer: int, y: float, partner: str, klasse: str) -> str:
    """Een vrijvervalstreng met een kruisende partner, beide met diameter 400."""
    return (
        put(f"KruisA{nummer}", f"KA{nummer}", 1000.0, y)
        + put(f"KruisB{nummer}", f"KB{nummer}", 1050.0, y)
        + put(f"KruisC{nummer}", f"KC{nummer}", 1025.0, y - 25.0)
        + put(f"KruisD{nummer}", f"KD{nummer}", 1025.0, y + 25.0)
        + leiding(
            f"V{nummer}",
            f"V{nummer}",
            [(1000.0, y), (1050.0, y)],
            f"KruisA{nummer}",
            f"KruisB{nummer}",
            kenmerken=maat(f"V{nummer}", 400, 400),
        )
        + leiding(
            partner,
            partner,
            [(1025.0, y - 25.0), (1025.0, y + 25.0)],
            f"KruisC{nummer}",
            f"KruisD{nummer}",
            klasse=klasse,
            kenmerken=maat(partner, 400, 400),
        )
    )


def _overlappaar(nummer: int, y: float, partner: str, klasse: str) -> str:
    """Een vrijvervalstreng met een partner die er over zijn volle lengte op ligt.

    Zonder maatvoering, zodat TOP-010 hier geen buffer heeft en alleen TOP-006 spreekt.
    """
    return (
        put(f"OverA{nummer}", f"OA{nummer}", 1000.0, y)
        + put(f"OverB{nummer}", f"OB{nummer}", 1050.0, y)
        + leiding(
            f"W{nummer}",
            f"W{nummer}",
            [(1000.0, y), (1050.0, y)],
            f"OverA{nummer}",
            f"OverB{nummer}",
        )
        + leiding(
            partner,
            partner,
            [(1000.0, y), (1050.0, y)],
            f"OverA{nummer}",
            f"OverB{nummer}",
            klasse=klasse,
        )
    )


FIXTURES["top_nabijheid_scope.ttl"] = (
    "alleen het duikerpaar hoort te melden; de drain en de aansluitleiding vallen buiten "
    "de populatie van TOP-006, TOP-010 en TOP-011 (issue #82)",
    _kruispaar(1, 2000.0, "KruisDrain", "Drain")
    + _kruispaar(2, 2100.0, "KruisAansluiting", "Aansluitleiding")
    + _kruispaar(3, 2200.0, "KruisDuiker", "Duiker")
    + _overlappaar(1, 2400.0, "OverDrain", "Drain")
    + _overlappaar(2, 2500.0, "OverAansluiting", "Aansluitleiding")
    + _overlappaar(3, 2600.0, "OverDuiker", "Duiker"),
)

# Issue #65: dezelfde kruising, maar streng 2 is een persleiding. Streng 3 is sinds issue
# #82 een duiker en levert het paar dat TOP-011 nog meldt: de persleiding valt sindsdien
# buiten de populatie van die check. TOP-011 meldt het paar een keer, met de
# vrijvervalstreng als hoofdobject en de duiker als tweede object; die melding hoort te
# blijven staan als `[rapport] onderdruk_klassen` op de klasse van het tweede object
# staat, want de onderdrukking kijkt naar het hoofdobject en niet naar object2. De
# persleiding blijft in de fixture: zij draagt de mechanische kleuring in de GIS-uitvoer
# en de nulmetingmelding die op klasse onderdrukt wordt.
FIXTURES["onderdruk_persleiding.ttl"] = (
    "een vrijvervalstreng kruist een persleiding en een duiker; onderdrukking per klasse "
    "(issue #65, populatie versmald in #82)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 1975.0)
    + put("PutD", "D", 1025.0, 2025.0)
    + put("PutE", "E", 1035.0, 1975.0)
    + put("PutF", "F", 1035.0, 2025.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1025.0, 1975.0), (1025.0, 2025.0)], "PutC", "PutD", klasse="Persleiding")
    + leiding("L3", "3", [(1035.0, 1975.0), (1035.0, 2025.0)], "PutE", "PutF", klasse="Duiker"),
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

# TOP-019 (issue #88): dezelfde pseudo-knoop, maar dan op een hulpstuk. Een T-stuk is
# geen netwerkknoop, dus de herleiding moet op de rauwe koppeling terugvallen. T1 draagt
# het defect; T2 staat ernaast met twee strengen van ongelijke diameter, en T3 draagt een
# enkele streng die op zichzelf terugkeert -- die telt als een streng en niet als twee.
FIXTURES["top019_pseudoknoop_hulpstuk.ttl"] = (
    "T-stuk T1 scheidt twee strengen met dezelfde diameter, hetzelfde materiaal en "
    "hetzelfde stelseltype; bij T2 verschilt de diameter en bij T3 komt een enkele "
    "streng met beide einden op het hulpstuk uit (issue #88)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1025.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0)],
        "PutA",
        "T1",
        kenmerken=maat("L1", 300, 300),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 2000.0), (1050.0, 2000.0)],
        "T1",
        "PutB",
        kenmerken=maat("L2", 300, 300),
    )
    + put("PutC", "C", 1000.0, 2100.0)
    + hulpstuk("T2", "T2", 1025.0, 2100.0)
    + put("PutD", "D", 1050.0, 2100.0)
    + leiding(
        "L3",
        "3",
        [(1000.0, 2100.0), (1025.0, 2100.0)],
        "PutC",
        "T2",
        kenmerken=maat("L3", 300, 300),
    )
    + leiding(
        "L4",
        "4",
        [(1025.0, 2100.0), (1050.0, 2100.0)],
        "T2",
        "PutD",
        kenmerken=maat("L4", 400, 400),
    )
    + hulpstuk("T3", "T3", 1025.0, 2200.0)
    + leiding(
        "L5",
        "5",
        [(1025.0, 2200.0), (1050.0, 2225.0), (1025.0, 2200.0)],
        "T3",
        "T3",
        kenmerken=maat("L5", 300, 300),
    ),
)

# TOP-020 verviel per issue #80 in NET-009; de fixture net009_omgekeerd_getekend dekt
# de omgekeerde tekenrichting nu.

# TOP-021: een put die naast een doorlopende streng ligt.
FIXTURES["top021_put_op_streng.ttl"] = (
    "put C ligt op streng 1 maar is er niet op aangesloten",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1025.0, 2000.1)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB"),
)

# Issue #85: de Kikker-export splitst een put per compartiment en hangt aan elk deel het
# putlabel plus een `c<n>`-postfix. Vier groepen naast elkaar, zodat alleen de eerste twee
# samengevoegd mogen worden en de dedup zich niet tot elke gelijknamige put uitbreidt.
FIXTURES["top005_compartimentduplicaat.ttl"] = (
    "K0001  c2 ligt 0,10 m van K0001  c1 en is het compartimentduplicaat; M0003  c1 ligt "
    "even dicht bij het postfixloze origineel M0003, dat de leiding juist niet draagt. "
    "V0002  c2 ligt 0,50 m van V0002  c1 en blijft een eigen put; de twee putten DUB "
    "dragen geen postfix en blijven een gewone dubbele put (issue #85)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("Comp1", "K0001  c1", 1100.0, 2000.0)
    + put("Comp2", "K0001  c2", 1100.1, 2000.0)
    + put("PutC", "C", 1150.0, 2000.0)
    + put("Ver1", "V0002  c1", 1200.0, 2000.0)
    + put("Ver2", "V0002  c2", 1200.5, 2000.0)
    + put("PutD", "D", 1250.0, 2000.0)
    + put("Dub1", "DUB", 1300.0, 2000.0)
    + put("Dub2", "DUB", 1300.1, 2000.0)
    + put("PutE", "E", 1350.0, 2000.0)
    + put("Mof", "M0003", 1400.0, 2000.0)
    + put("Mof1", "M0003  c1", 1400.1, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "Comp1")
    + leiding("L3", "3", [(1150.0, 2000.0), (1200.0, 2000.0)], "PutC", "Ver1")
    + leiding("L4", "4", [(1250.0, 2000.0), (1300.0, 2000.0)], "PutD", "Dub1")
    + leiding("L5", "5", [(1350.0, 2000.0), (1400.1, 2000.0)], "PutE", "Mof1"),
)

# Issue #85, blokreview: de prijs van de samenvoeging, in het venster tussen de twee
# toleranties in. `dubbele_put_tolerantie_m` (0,30 m) is drie keer zo ruim als
# `snapping_tolerantie_m` (0,10 m), dus een duplicaat op 0,20 m wordt wel samengevoegd
# maar vangt het strengeinde daarna niet meer op. Streng 6 eindigt op het duplicaat en
# raakt zijn aansluiting kwijt; streng 7 hangt aan de winnaar en houdt de zijne. Vóór de
# dedup meldt hier niets.
FIXTURES["top003_dedup_buiten_snapping.ttl"] = (
    "W0004  c2 ligt 0,20 m van W0004  c1: binnen de dubbele-put-tolerantie (samenvoegen) "
    "maar buiten de snapping-tolerantie, zodat streng 6 -- die op het duplicaat eindigt -- "
    "daarna nog maar aan een zijde een put heeft (issue #85, blokreview blok D)",
    put("PutF", "F", 1450.0, 2000.0)
    + put("Won1", "W0004  c1", 1500.0, 2000.0)
    + put("Won2", "W0004  c2", 1500.2, 2000.0)
    + put("PutG", "G", 1550.0, 2000.0)
    + leiding("L6", "6", [(1450.0, 2000.0), (1500.2, 2000.0)], "PutF", "Won2")
    + leiding("L7", "7", [(1500.0, 2000.0), (1550.0, 2000.0)], "Won1", "PutG"),
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

# NET-006 (issue #97): vuilwater komt op knoop B binnen en gaat als gemengd verder. Gemengd
# benedenstrooms van vuilwater is normaal; beide strengen lopen in de van-naar-richting met
# dalende BOB en meelopende geometrie, dus hun richting is betrouwbaar (NET-009 spreekt ze
# niet tegen) en NET-006 dempt de koppelingsmelding.
FIXTURES["net006_vuilwater_naar_gemengd.ttl"] = (
    "geen; vuilwater komt op knoop B binnen en gaat als gemengd verder (goede richting, issue #97)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0)
    + put("PutC", "C", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0)],
        "PutA",
        "PutB",
        klasse="Vuilwaterriool",
        bob=(10.5, 10.0),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 2000.0), (1050.0, 2000.0)],
        "PutB",
        "PutC",
        bob=(10.0, 9.5),
    ),
)

# NET-006 (issue #97): de omgekeerde, foute richting. Gemengd komt op knoop B binnen en gaat
# als vuilwater verder -- gemengd bovenstrooms van vuilwater is wel een koppelingsfout en
# blijft gemeld. Dezelfde betrouwbare richting (BOB daalt, geometrie mee).
FIXTURES["net006_gemengd_naar_vuilwater.ttl"] = (
    "op knoop B komt gemengd binnen en gaat als vuilwater verder (gemengd bovenstrooms van "
    "vuilwater, issue #97)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0)
    + put("PutC", "C", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.5, 10.0),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 2000.0), (1050.0, 2000.0)],
        "PutB",
        "PutC",
        klasse="Vuilwaterriool",
        bob=(10.0, 9.5),
    ),
)

# NET-006 (issue #97, optie B): een doorgaand gemengd hoofdriool (L1 A->B->C L2) waarop een
# vuilwatertak (L3 D->B) aansluit. Op knoop B stroomt gemengd zowel in als uit en vuilwater
# in; de foutvorm (vuilwater benedenstrooms van gemengd) ontbreekt en alle strengen zijn
# betrouwbaar gericht, dus NET-006 dempt de koppeling. De strikte regel (optie A) meldde deze
# nog omdat gemengd niet puur uitstroomt.
FIXTURES["net006_doorgaand_gemengd_hoofdriool.ttl"] = (
    "geen; doorgaand gemengd hoofdriool met een aansluitende vuilwatertak op knoop B "
    "(goede richting, issue #97)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1025.0, 2000.0)
    + put("PutC", "C", 1050.0, 2000.0)
    + put("PutD", "D", 1025.0, 2025.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1025.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.5, 10.0),
    )
    + leiding(
        "L2",
        "2",
        [(1025.0, 2000.0), (1050.0, 2000.0)],
        "PutB",
        "PutC",
        bob=(10.0, 9.5),
    )
    + leiding(
        "L3",
        "3",
        [(1025.0, 2025.0), (1025.0, 2000.0)],
        "PutD",
        "PutB",
        klasse="Vuilwaterriool",
        bob=(10.3, 10.0),
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


# NET-004 (issue #102): een kring C -> D -> E -> C die alleen administratief bestaat. Streng
# 7 (E -> C) heeft een stijgende BOB: NET-009 spreekt haar tegen, dus haar richting is
# onbetrouwbaar. Met de betrouwbare richting valt de kring uiteen en NET-004 zwijgt.
FIXTURES["net004_lus_door_richtingsfout.ttl"] = (
    "streng 7 (E->C) stijgt in de BOB; de kring bestaat alleen in de administratieve richting",
    put("PutC", "C", 2000.0, 3000.0)
    + put("PutD", "D", 2050.0, 3000.0)
    + put("PutE", "E", 2025.0, 3050.0)
    + leiding("L5", "5", [(2000.0, 3000.0), (2050.0, 3000.0)], "PutC", "PutD", bob=(10.0, 9.5))
    + leiding("L6", "6", [(2050.0, 3000.0), (2025.0, 3050.0)], "PutD", "PutE", bob=(9.5, 9.0))
    + leiding("L7", "7", [(2025.0, 3050.0), (2000.0, 3000.0)], "PutE", "PutC", bob=(9.0, 9.5)),
)

# NET-004 (issue #102): een BOB-consistente ring die vlak ligt en nergens in een put omhoog
# springt. In vlak Nederland is dit een bewust vermaasd net en geen fout; NET-004 dempt hem
# en telt hem in de toelichting.
FIXTURES["net004_vermaasde_ring.ttl"] = (
    "geen; kring C->D->E->C ligt vlak (BOB gelijk) zonder putsprong: bewust vermaasd net "
    "(issue #102)",
    put("PutC", "C", 2000.0, 3000.0)
    + put("PutD", "D", 2050.0, 3000.0)
    + put("PutE", "E", 2025.0, 3050.0)
    + leiding("L5", "5", [(2000.0, 3000.0), (2050.0, 3000.0)], "PutC", "PutD", bob=(10.0, 10.0))
    + leiding("L6", "6", [(2050.0, 3000.0), (2025.0, 3050.0)], "PutD", "PutE", bob=(10.0, 10.0))
    + leiding("L7", "7", [(2025.0, 3050.0), (2000.0, 3000.0)], "PutE", "PutC", bob=(10.0, 10.0)),
)

# NET-004 (issue #102): een BOB-consistente ring die per been keurig daalt maar alleen sluit
# via een BOB-sprong omhoog in put C (8,80 -> 10,00 m). Dat is het terrein van HGT-009, niet
# van NET-004; de kring wordt gedempt en apart geteld.
FIXTURES["net004_ring_met_putsprong.ttl"] = (
    "geen; kring C->D->E->C daalt per been maar sluit via een BOB-sprong omhoog in put C "
    "(HGT-009-terrein, issue #102)",
    put("PutC", "C", 2000.0, 3000.0)
    + put("PutD", "D", 2050.0, 3000.0)
    + put("PutE", "E", 2025.0, 3050.0)
    + leiding("L5", "5", [(2000.0, 3000.0), (2050.0, 3000.0)], "PutC", "PutD", bob=(10.0, 9.6))
    + leiding("L6", "6", [(2050.0, 3000.0), (2025.0, 3050.0)], "PutD", "PutE", bob=(9.6, 9.2))
    + leiding("L7", "7", [(2025.0, 3050.0), (2000.0, 3000.0)], "PutE", "PutC", bob=(9.2, 8.8)),
)


# NET-009: een streng die omgekeerd getekend is terwijl de BOB de administratie volgt.
# Geometrie tegen, BOB mee: de drie richtingssignalen spreken elkaar tegen.
FIXTURES["net009_omgekeerd_getekend.ttl"] = (
    "streng 1 is van B naar A getekend terwijl de administratie en de BOB A->B zeggen",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1050.0, 2000.0), (1000.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.5, 10.0),
    ),
)

# NET-009: een vlakke streng. De BOB is gelijk aan begin en eind (verval 0), dus de BOB
# zegt niets over de richting: geen bevinding, wel "geen uitspraak".
FIXTURES["net009_vlakke_streng.ttl"] = (
    "streng 1 ligt vlak (BOB begin en eind gelijk), dus de richting is niet uit de BOB te lezen",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1050.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.0, 10.0),
    ),
)

# NET-009: een streng met een BOB van 0,00 aan beide zijden. De vulwaardenregel leest die
# als niet geregistreerd; zonder BOB kan de richting niet op de bodem getoetst worden.
FIXTURES["net009_bob_vulwaarde.ttl"] = (
    "streng 1 draagt een BOB van 0,00 die als vulwaarde wordt gelezen en dus ontbreekt",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1050.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(0.0, 0.0),
    ),
)


# NET-009: twee tegenspraken met andere signaalcombinaties. Streng 1 is omgekeerd
# getekend maar ligt vlak (geometrie tegen, BOB vlak); streng 2 mist een bruikbare lijn
# maar heeft een stijgende BOB (geometrie onbekend, BOB tegen). Beide worden gemeld.
FIXTURES["net009_signaalvarianten.ttl"] = (
    "streng 1 is omgekeerd getekend en vlak; streng 2 mist geometrie en heeft een stijgende BOB",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1000.0, 2100.0)
    + put("PutD", "D", 1050.0, 2100.0)
    + leiding(
        "L1",
        "1",
        [(1050.0, 2000.0), (1000.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.0, 10.0),
    )
    + leiding("L2", "2", [(1000.0, 2100.0)], "PutC", "PutD", bob=(10.0, 10.5)),
)


# NET-009: streng 2 draagt geen bruikbare lijn (enkel punt) en geen BOB, dus geen enkel
# richtingssignaal. Ze wordt niet gemeld, maar mag ook niet stil verdwijnen: de
# toelichting telt haar. Streng 1 is schoon en zorgt dat er wel iets te bekijken valt.
FIXTURES["net009_geen_signaal.ttl"] = (
    "streng 2 mist zowel een bruikbare lijn als een BOB, dus geen enkel richtingssignaal",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1000.0, 2100.0)
    + put("PutD", "D", 1050.0, 2100.0)
    + leiding(
        "L1",
        "1",
        [(1000.0, 2000.0), (1050.0, 2000.0)],
        "PutA",
        "PutB",
        bob=(10.5, 10.0),
    )
    + leiding("L2", "2", [(1000.0, 2100.0)], "PutC", "PutD"),
)


# De ongerichte-graaf "harde waarheid" uit een bereikbaar lozingspunt is per issue #80 na
# de hermeting weer weggelaten (BO-76: 2.822 vals-alarmen op strengen die intern kloppen),
# dus NET-009 krijgt geen lozingspunt-fixtures.


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
C = (1100.0, 2000.0)
D = (1150.0, 2000.0)
E = (1200.0, 2000.0)

# De putten dragen sinds ATTR-018 een begindatum: zonder aanlegjaar is een put een
# bevinding, en deze fixture hoort de hele ATTR-groep stil te houden (issue #61).
FIXTURES["attr_schoon.ttl"] = (
    "geen; alle attributen zijn aannemelijk en onderling consistent",
    nette_put("PutA", "A", *A, Begindatum="1980-01-01")
    + nette_put("PutB", "B", *B, Begindatum="1980-01-01")
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

FIXTURES["attr001_constructietype_drainage.ttl"] = (
    "streng HW is een hemelwaterriool van PVC Ø65 en valt onder de PVC-ondergrens van "
    "100 mm; DT is een DT-riool van dezelfde maat en hetzelfde materiaal en valt binnen "
    "het drainagebereik dat vóór het materiaalbereik gaat; DIT is een DIT-riool van Ø45 "
    "en valt onder dat drainagebereik (issue #86)",
    DRAINAGE_KLASSEN
    + nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_put("PutC", "C", *C)
    + nette_put("PutD", "D", *D)
    + nette_leiding(
        "DT",
        "DT",
        [A, B],
        "PutA",
        "PutB",
        klasse="DT_riool",
        velden={"BreedteLeiding": 65, "HoogteLeiding": 65, "MateriaalLeiding_ref": "PVC"},
    )
    + nette_leiding(
        "HW",
        "HW",
        [B, C],
        "PutB",
        "PutC",
        klasse="Hemelwaterriool",
        velden={"BreedteLeiding": 65, "HoogteLeiding": 65, "MateriaalLeiding_ref": "PVC"},
    )
    + nette_leiding(
        "DIT",
        "DIT",
        [C, D],
        "PutC",
        "PutD",
        klasse="DIT_riool",
        velden={"BreedteLeiding": 45, "HoogteLeiding": 45, "MateriaalLeiding_ref": "PVC"},
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
    "streng 1 is PVC met begindatum 1940; PVC bestaat pas vanaf 1955",
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

FIXTURES["attr002_stelseltype.ttl"] = (
    "G (gemengd, Ø220) valt onder de gemengd-ondergrens van 250 mm; "
    "V (vuilwater, Ø220) blijft boven de vuilwater-ondergrens van 200 mm (issue #20)",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_put("PutC", "C", *C)
    + nette_leiding(
        "G",
        "G",
        [A, B],
        "PutA",
        "PutB",
        klasse="GemengdRiool",
        velden={"BreedteLeiding": 220, "HoogteLeiding": 220},
    )
    + nette_leiding(
        "V",
        "V",
        [B, C],
        "PutB",
        "PutC",
        klasse="Vuilwaterriool",
        velden={"BreedteLeiding": 220, "HoogteLeiding": 220},
    ),
)

FIXTURES["attr001_diameterbesluit.ttl"] = (
    "geen; de vier door issue #20 gecorrigeerde bereiken passen nu -- PP Ø80 (min 100->80), "
    "GewapendBeton Ø300 (min 400->300), Gres Ø1200 (max 1000->1400), "
    "Asbestcement Ø1500 (max 1000->1800)",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_put("PutC", "C", *C)
    + nette_put("PutD", "D", *D)
    + nette_put("PutE", "E", *E)
    + nette_leiding(
        "PP",
        "PP",
        [A, B],
        "PutA",
        "PutB",
        klasse="Vuilwaterriool",
        velden={"BreedteLeiding": 80, "HoogteLeiding": 80, "MateriaalLeiding_ref": "Polypropyleen"},
    )
    + nette_leiding(
        "GB",
        "GB",
        [B, C],
        "PutB",
        "PutC",
        klasse="Vuilwaterriool",
        velden={
            "BreedteLeiding": 300,
            "HoogteLeiding": 300,
            "MateriaalLeiding_ref": "GewapendBeton",
        },
    )
    + nette_leiding(
        "GR",
        "GR",
        [C, D],
        "PutC",
        "PutD",
        klasse="Vuilwaterriool",
        velden={"BreedteLeiding": 1200, "HoogteLeiding": 1200, "MateriaalLeiding_ref": "Gres"},
    )
    + nette_leiding(
        "AC",
        "AC",
        [D, E],
        "PutD",
        "PutE",
        klasse="Vuilwaterriool",
        velden={
            "BreedteLeiding": 1500,
            "HoogteLeiding": 1500,
            "MateriaalLeiding_ref": "Asbestcement",
        },
    ),
)

FIXTURES["attr003_begindatum_besluit.ttl"] = (
    "PVC56 (PVC, 1956) valt vóór 1958; PE65 en GB15 hebben geen tijdvakregel meer "
    "en zijn geen bevinding (issue #20)",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_put("PutC", "C", *C)
    + nette_put("PutD", "D", *D)
    + nette_leiding(
        "PVC56",
        "PVC56",
        [A, B],
        "PutA",
        "PutB",
        klasse="Vuilwaterriool",
        velden={"MateriaalLeiding_ref": "PVC", "Begindatum": "1956-01-01"},
    )
    + nette_leiding(
        "PE65",
        "PE65",
        [B, C],
        "PutB",
        "PutC",
        klasse="Vuilwaterriool",
        velden={"MateriaalLeiding_ref": "PE", "Begindatum": "1965-01-01"},
    )
    + nette_leiding(
        "GB15",
        "GB15",
        [C, D],
        "PutC",
        "PutD",
        klasse="Vuilwaterriool",
        velden={
            "BreedteLeiding": 400,
            "HoogteLeiding": 400,
            "MateriaalLeiding_ref": "GewapendBeton",
            "Begindatum": "1915-01-01",
        },
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

FIXTURES["attr004_muil_te_hoog.ttl"] = (
    "streng 1 heeft een muilprofiel dat hoger is dan breed; een muil is breder dan hoog.\n"
    "# Het muilprofiel zelf hoort bij metselwerk, dus ATTR-012 heeft hier niets te melden.",
    nette_put("PutA", "A", *A, MateriaalPut_ref="Metselwerk")
    + nette_put("PutB", "B", *B, MateriaalPut_ref="Metselwerk")
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={
            "BreedteLeiding": 600,
            "HoogteLeiding": 800,
            "MateriaalLeiding_ref": "Metselwerk",
            "VormLeiding_ref": "Muil",
            "Begindatum": "1930-01-01",
        },
    ),
)

FIXTURES["attr016_ronde_put_ongelijk.ttl"] = (
    "put A heet rond maar heeft breedte 800 en lengte 1000; een ronde put heeft een diameter.\n"
    "# Put B is rond met 800 bij 800 (geen bevinding), put C is rechthoekig met 800 bij 1000\n"
    "# (een rechthoekige put mag ongelijke maten hebben, dus ook geen bevinding).",
    nette_put("PutA", "A", *A, VormPut_ref="Rond", BreedtePut=800, LengtePut=1000)
    + nette_put("PutB", "B", *B, VormPut_ref="Rond", BreedtePut=800, LengtePut=800)
    + nette_put(
        "PutC", "C", 1100.0, 2000.0, VormPut_ref="Rechthoekig", BreedtePut=800, LengtePut=1000
    )
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB"),
)

FIXTURES["attr016_ronde_put_lengte_nul.ttl"] = (
    "put A is rond met breedte 800 en lengte 0; 0 is geen maat, dus de lengte is niet\n"
    "# geregistreerd. Dezelfde conditie als attr016_ronde_put_ongelijk.ttl, maar de andere\n"
    "# soort binnen die conditie -- en dus een andere boodschap (issue #92). Put B is rond\n"
    "# met 800 bij 800 (geen bevinding).",
    nette_put("PutA", "A", *A, VormPut_ref="Rond", BreedtePut=800, LengtePut=0)
    + nette_put("PutB", "B", *B, VormPut_ref="Rond", BreedtePut=800, LengtePut=800)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB"),
)

# ATTR-017: wandruwheid past niet bij het leidingmateriaal. De schaal wordt uit de
# data zelf bepaald (de lezing met de minste afwijkingen). Hier winnen tienden van
# een mm: bij schaal 1:10 valt maar een streng buiten zijn band, bij schaal 1:1 alle
# drie.
_P1, _P2, _P3, _P4 = (1000.0, 2000.0), (1050.0, 2000.0), (1100.0, 2000.0), (1150.0, 2000.0)
FIXTURES["attr017_wandruwheid_pe_betonwaarde.ttl"] = (
    "streng 2 is van PE met wandruwheid 30 (3,0 mm bij schaal 1:10), de betonwaarde;\n"
    "# PE hoort rond 0,4 mm te liggen. Streng 1 (beton, 30 = 3,0 mm) en streng 3 (PE, 4 =\n"
    "# 0,4 mm) passen wel bij hun materiaal en blijven stil.",
    nette_put("PutA", "A", *_P1)
    + nette_put("PutB", "B", *_P2)
    + nette_put("PutC", "C", *_P3)
    + nette_put("PutD", "D", *_P4)
    + nette_leiding(
        "L1",
        "1",
        [_P1, _P2],
        "PutA",
        "PutB",
        velden={
            "MateriaalLeiding_ref": "Beton",
            "WandruwheidBinnenboven": 30,
            "WandruwheidBinnenonder": 30,
        },
    )
    + nette_leiding(
        "L2",
        "2",
        [_P2, _P3],
        "PutB",
        "PutC",
        velden={
            "MateriaalLeiding_ref": "PE",
            "WandruwheidBinnenboven": 30,
            "WandruwheidBinnenonder": 30,
        },
    )
    + nette_leiding(
        "L3",
        "3",
        [_P3, _P4],
        "PutC",
        "PutD",
        velden={
            "MateriaalLeiding_ref": "PE",
            "WandruwheidBinnenboven": 4,
            "WandruwheidBinnenonder": 4,
        },
    ),
)

# ATTR-017 met een export in hele millimeters: een betonleiding met wandruwheid 3
# hoort geen bevinding te geven. Bewijst dat de schaallezing niet op tienden is
# vastgezet -- hier wint schaal 1:1 (nul afwijkingen tegen een afwijking bij 1:10).
FIXTURES["attr017_wandruwheid_hele_mm.ttl"] = (
    "geen; de betonleiding draagt wandruwheid 3, wat in hele mm precies de C2100-waarde is",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding(
        "L1",
        "1",
        [A, B],
        "PutA",
        "PutB",
        velden={
            "MateriaalLeiding_ref": "Beton",
            "WandruwheidBinnenboven": 3,
            "WandruwheidBinnenonder": 3,
        },
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

# ATTR-018: streng 1 en put A dragen geen begindatum en melden; streng 2 en put B
# dragen er wel een en zwijgen; persleiding 3 draagt er geen maar valt buiten de
# populatie (mechanisch riool) en zwijgt ook. `kenmerken()` slaat een None-waarde
# over, dus `velden={"Begindatum": None}` haalt de standaarddatum van nette_leiding weg.
FIXTURES["attr018_zonder_begindatum.ttl"] = (
    "streng 1 en put A hebben geen begindatum; streng 2, put B en persleiding 3 zijn "
    "geen bevinding (issue #61)",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B, Begindatum="1985-01-01")
    + nette_put("PutC", "C", *C, Begindatum="1985-01-01")
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"Begindatum": None})
    + nette_leiding("L2", "2", [B, C], "PutB", "PutC")
    + nette_leiding(
        "L3", "3", [C, D], "PutC", "PutD", klasse="Persleiding", velden={"Begindatum": None}
    )
    + nette_put("PutD", "D", *D, Begindatum="1985-01-01"),
)

FIXTURES["attr009_lengte_wijkt_af.ttl"] = (
    "streng 1 is 50 m getekend maar staat als 100 m geregistreerd",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB", velden={"LengteLeiding": 100.0}),
)

FIXTURES["attr010_materiaal_put.ttl"] = (
    "gemetselde streng 1 komt uit op put B van PVC.\n"
    "# Het putmateriaal was hier `Kunststof`, een waarde die MateriaalPutColl niet kent:\n"
    "# de fixture toetste een export die niet kan bestaan (issue #43).",
    nette_put("PutA", "A", *A, MateriaalPut_ref="Metselwerk")
    + nette_put("PutB", "B", *B, MateriaalPut_ref="PVC")
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

FIXTURES["attr010_gresput.ttl"] = (
    "geen; een betonnen streng tussen twee gresputten. Gres is een legaal lid van\n"
    "# MateriaalPutColl en een gresput onder een betonnen riool is niets bijzonders.\n"
    "# De tegenhanger van attr010_materiaal_put.ttl.",
    nette_put("PutA", "A", *A, MateriaalPut_ref="Gres")
    + nette_put("PutB", "B", *B, MateriaalPut_ref="Gres")
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB"),
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


def _begindatum_reeks(jaren: list[int]) -> str:
    """Een losse streng per jaartal, elk met een eigen begindatum en geometrie."""
    return "".join(
        nette_leiding(
            f"L{i}",
            str(i),
            [(1000.0 + i * 10, 2000.0), (1000.0 + i * 10 + 5, 2000.0)],
            None,
            None,
            velden={"Begindatum": f"{jaar}-01-01"},
        )
        for i, jaar in enumerate(jaren)
    )


# ATTR-015: 16 van de 40 strengen (40%) op begindatum 1900, ruim boven de signaaldrempel
# van 20%; de overige 24 elk een eigen jaar, zodat alleen 1900 opvalt.
FIXTURES["attr015_vulwaardejaar.ttl"] = (
    "16 van de 40 strengen dragen begindatum 1900 (40%); dat ruikt naar een vulwaarde",
    _begindatum_reeks([1900] * 16 + list(range(1980, 2004))),
)

# De tegenhanger: genoeg gedateerde strengen, maar geen enkel jaar overheerst.
FIXTURES["attr015_geen_piek.ttl"] = (
    "40 strengen met elk een eigen begindatumjaar; geen enkel jaar overheerst",
    _begindatum_reeks(list(range(1964, 2004))),
)

# --- HGT ------------------------------------------------------------------
#
# Het schone hoogtebeeld: maaiveld 10,00 m NAP, deksel 10,00, puthoogte 1,50 m
# (bodem dus 8,50) en een BOB die van 8,70 naar 8,50 daalt over 50 m: verhang 1:250,
# ruim boven wat de RIONED-staffel bij 300 mm vraagt (1:500, issue #29). Het beginpunt
# ligt hoog genoeg zodat de putbodem-BOB-relatie (HGT-015) ongemoeid blijft.

C = (1100.0, 2000.0)


def hoogteput(
    naam, label, punt, mv=10.0, dek=10.0, hoogte=1500, mv_wijze=None, dek_wijze=None, **extra
):
    """Een put met maaiveld, putdeksel en puthoogte.

    Met `dek=None` krijgt de put geen putdeksel. Zo ziet de De Wolden en Hoogeveen-export eruit:
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
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.70, 8.50)),
)

FIXTURES["hgt004_bob_boven_deksel.ttl"] = (
    "de BOB van streng 1 ligt op 10,50 m NAP, boven het deksel van put A op 10,00",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(10.50, 8.55)),
)

# HGT-005 verviel per issue #80 in NET-009; licht tegenverhang krijgt geen eigen fixture
# meer.

FIXTURES["hgt006_tegenverhang_fors.ttl"] = (
    "de bodem van streng 1 stijgt 0,30 m in de afvoerrichting",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.90)),
)

FIXTURES["hgt006_net_onder_de_forsgrens.ttl"] = (
    "de bodem van streng 1 stijgt 0,08 m in de afvoerrichting: licht, onder de forsgrens 0,10 m",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.68)),
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
    "put B heeft een puthoogte van 12 m, boven de ontologiegrens van 4 m",
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

# ATTR-013: vulwaarden in hoogtekenmerken (issue #1). Staat hier omdat ze de
# HGT-helpers gebruikt. Put A heeft maaiveld 0,00 (en geen deksel), put B maaiveld
# 0,01, put C is schoon; streng 1 heeft een BOB van 0,000 aan het beginpunt. Met de
# standaardconfig meldt ATTR-013 put A, put B en streng 1; HGT-004 en HGT-014
# zwijgen over hen met een toelichting.
FIXTURES["attr013_vulwaarde_hoogte.ttl"] = (
    "put A (maaiveld 0,00), put B (maaiveld 0,01) en streng 1 (BOB begin 0,000) "
    "dragen een vulwaarde",
    hoogteput("PutA", "A", A, mv=0.0, dek=None)
    + hoogteput("PutB", "B", B, mv=0.01, dek=None)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(0.0, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.60, 8.55)),
)

# --- RVZ ------------------------------------------------------------------


def _overstortstelsel(drempelregel: str) -> str:
    """Een gemengd stelsel met een aangesloten overstortput O die op een sloot loost.

    `drempelregel` is de TTL van de overstortdrempel van put O (uit `drempel(...)`),
    of een lege string voor een put zonder drempelonderdeel. Basis van rvz_schoon en
    van de RVZ-002/003-fixtures.
    """
    return (
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
        + drempelregel
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
"""
    )


def gemaal(naam: str, label: str, punt: tuple[float, float]) -> str:
    """Een rioolgemaal als afvoereindpunt in het netwerk (subklasse van Gemaal)."""
    return put(naam, label, punt[0], punt[1], klasse="Rioolgemaal")


# NET (#18, fase 1): een keten van drie strengen naar een gemaal. Elke streng bereikt
# hetzelfde eindpunt en telt een aflopend aantal stappen; de afstanden zijn 50 m per
# streng, zodat de meters netjes optellen.
FIXTURES["net_afvoerpad_keten.ttl"] = (
    "geen; drie strengen A->B->C->gemaal, invoer voor de afvoerpadanalyse",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + gemaal("Gem", "G", (1150.0, 2000.0))
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC")
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutC", "Gem"),
)

# NET (#18, fase 1): een streng met een lijngeometrie van een enkel punt. Die is niet
# als lijn te lezen (line=None), maar de netwerkkoppelingen blijven staan: de streng
# krijgt wel een afvoerpad in stappen en geen padlengte in meters.
FIXTURES["net_afvoerpad_zonder_lijn.ttl"] = (
    "streng 1 heeft een lijngeometrie van een enkel punt en dus geen bruikbare lengte",
    put("PutA", "A", 1000.0, 2000.0)
    + gemaal("Gem", "G", (1050.0, 2000.0))
    + leiding("L1", "1", [(1000.0, 2000.0)], "PutA", "Gem"),
)

# NET (#18, fase 1): put A bereikt twee gemalen in evenveel stappen. Het dichtstbijzijnde
# in stappen is een gelijkspel, dus wint de kleinste URI (GemA < GemB) -- het determinisme.
FIXTURES["net_afvoerpad_twee_eindpunten.ttl"] = (
    "geen; put A bereikt gemaal A en gemaal B beide in een stap",
    put("PutA", "A", 1000.0, 2000.0)
    + gemaal("GemA", "GA", (1050.0, 2010.0))
    + gemaal("GemB", "GB", (1050.0, 1990.0))
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2010.0)], "PutA", "GemA")
    + leiding("L2", "2", [(1000.0, 2000.0), (1050.0, 1990.0)], "PutA", "GemB"),
)

# NET (#18, fase 1): twee parallelle strengen van A naar het gemaal, met verschillende
# getekende lengte (La recht = 100 m, Lb met knik = ~141 m). De knoop A leest de lengte
# van de kleinste-URI streng (La); elke streng leest haar eigen lengte.
FIXTURES["net_afvoerpad_parallel.ttl"] = (
    "geen; twee parallelle strengen A->gemaal met verschillende lengte",
    put("PutA", "A", 1000.0, 2000.0)
    + gemaal("Gem", "G", (1100.0, 2000.0))
    + leiding("La", "a", [(1000.0, 2000.0), (1100.0, 2000.0)], "PutA", "Gem")
    + leiding("Lb", "b", [(1000.0, 2000.0), (1050.0, 2050.0), (1100.0, 2000.0)], "PutA", "Gem"),
)

# NET (#18, fase 1): een persleiding (mechanisch, geen vrijverval) naar het gemaal. Ze
# hoort niet in de vrijverval-afvoerpadanalyse: een streng-afvoerpad is er alleen voor
# vrijvervalstrengen, niet voor gepompt riool.
FIXTURES["net_afvoerpad_mechanisch.ttl"] = (
    "geen; naast de vrijvervalstreng 1 loopt een persleiding p naar hetzelfde gemaal",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutX", "X", 1000.0, 2100.0)
    + gemaal("Gem", "G", (1050.0, 2000.0))
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Gem")
    + leiding("P1", "p", [(1000.0, 2100.0), (1050.0, 2000.0)], "PutX", "Gem", klasse="Persleiding"),
)


# De drukrioleringsklassen, inline: de gedeelde prelude kent ze niet. Pompunit is een
# Rioolput, Drukleiding een MechanischeRioolleiding en die weer een Rioolleiding; het
# T-stuk waarop het persnet samenkomt komt uit HULPSTUK_KLASSEN.
DRUKRIOLERING_KLASSEN = (
    "gwsw:Pompunit rdfs:subClassOf gwsw:Rioolput .\n"
    "gwsw:MechanischeRioolleiding rdfs:subClassOf gwsw:Rioolleiding .\n"
    "gwsw:Drukleiding rdfs:subClassOf gwsw:MechanischeRioolleiding .\n\n"
)

# NET-001 (#72): drukriolering. De vuilwaterstreng '1' eindigt op een pompunit en komt
# alleen door het persnet bij het gemaal uit: drukleiding, T-stuk, drukleiding. Twee
# dingen zitten er bewust in. Het T-stuk is geen netwerkknoop -- het klimt via hasPart
# niet naar een put, dus `resolve_network_node` geeft er None voor -- zodat het persnet
# zonder de terugval op de rauwe koppeling in stukken uiteenvalt. En de laatste
# drukleiding 'd2' staat administratief van het GEMAAL naar het T-stuk geregistreerd:
# alleen omdat de mechanische kanten ongericht zijn loopt de route er toch doorheen.
# Zie BO-54; `net001_drukriolering_lozingsput.ttl` dekt de meelopende registratie.
FIXTURES["net001_drukriolering_gemaal.ttl"] = (
    "geen; vuilwaterstreng '1' bereikt het gemaal alleen via pompunit -> drukleiding "
    "-> T-stuk -> drukleiding, waarvan de laatste tegen de looprichting in geregistreerd staat",
    DRUKRIOLERING_KLASSEN
    + HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("Pomp", "P", 1050.0, 2000.0, klasse="Pompunit")
    + hulpstuk("T1", "T", 1100.0, 2000.0)
    + gemaal("Gem", "G", (1150.0, 2000.0))
    + leiding(
        "L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Pomp", klasse="Vuilwaterriool"
    )
    + leiding("D1", "d1", [(1050.0, 2000.0), (1100.0, 2000.0)], "Pomp", "T1", klasse="Drukleiding")
    + leiding("D2", "d2", [(1150.0, 2000.0), (1100.0, 2000.0)], "Gem", "T1", klasse="Drukleiding"),
)

# NET-001 (#72): dezelfde keten, maar het persnet komt op een lozingsput uit in plaats
# van op een gemaal. Vuilwater loost in Nederland niet meer rechtstreeks op
# oppervlaktewater, dus een lozingspunt is een geldig vuilwater-eindpunt (BO-53).
FIXTURES["net001_drukriolering_lozingsput.ttl"] = (
    "geen; vuilwaterstreng '1' bereikt alleen via het persnet een lozingsput, geen gemaal",
    DRUKRIOLERING_KLASSEN
    + HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("Pomp", "P", 1050.0, 2000.0, klasse="Pompunit")
    + hulpstuk("T1", "T", 1100.0, 2000.0)
    + put("Loz", "L", 1150.0, 2000.0, klasse="Lozingsput")
    + leiding(
        "L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Pomp", klasse="Vuilwaterriool"
    )
    + leiding("D1", "d1", [(1050.0, 2000.0), (1100.0, 2000.0)], "Pomp", "T1", klasse="Drukleiding")
    + leiding("D2", "d2", [(1100.0, 2000.0), (1150.0, 2000.0)], "T1", "Loz", klasse="Drukleiding"),
)

# NET-002 (#72): dezelfde keten met een HEMELWATERstreng ervoor. De bereikbaarheidsgraaf
# is gedeeld, dus het persnet telt ook voor NET-002 mee; deze fixture legt dat gedrag
# vast in plaats van het onopgemerkt te laten. Zie BO-54 en de meting daarin.
FIXTURES["net002_drukriolering_lozingsput.ttl"] = (
    "geen; hemelwaterstreng '1' bereikt de lozingsput alleen via pompunit -> drukleiding "
    "-> T-stuk -> drukleiding",
    DRUKRIOLERING_KLASSEN
    + HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("Pomp", "P", 1050.0, 2000.0, klasse="Pompunit")
    + hulpstuk("T1", "T", 1100.0, 2000.0)
    + put("Loz", "L", 1150.0, 2000.0, klasse="Lozingsput")
    + leiding(
        "L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Pomp", klasse="Hemelwaterriool"
    )
    + leiding("D1", "d1", [(1050.0, 2000.0), (1100.0, 2000.0)], "Pomp", "T1", klasse="Drukleiding")
    + leiding("D2", "d2", [(1100.0, 2000.0), (1150.0, 2000.0)], "T1", "Loz", klasse="Drukleiding"),
)

# NET-001 (#73): een pompunit is een overdrachtspunt naar de drukriolering en geen
# afvoereindpunt (BO-55). Deze keten heeft geen persleiding achter de pompunit, dus
# streng '1' komt nergens uit en hoort gemeld te worden. Het tegenbeeld staat hierboven:
# met een persnet erachter zwijgt NET-001 wel.
FIXTURES["net001_pompunit_zonder_persnet.ttl"] = (
    "vuilwaterstreng '1' eindigt op een pompunit zonder persleiding erachter: geen afvoerpad",
    "gwsw:Pompunit rdfs:subClassOf gwsw:Rioolput .\n\n"
    + put("PutA", "A", 1000.0, 2000.0)
    + put("Pomp", "P", 1050.0, 2000.0, klasse="Pompunit")
    + leiding(
        "L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Pomp", klasse="Vuilwaterriool"
    ),
)

# NET/RVZ (#105): een hulpstuk met een telbare GWSW-functie is een doorgeefknoop in de
# VRIJVERVALgraaf, niet alleen in het persnet. De gemengde streng '1' loopt van put A naar
# T-stuk T1 en '2' van T1 naar overstortput O; '3' brengt het water van O naar het gemaal.
# Zonder de terugval op de rauwe koppeling valt de graaf hier in twee delen uiteen -- put A
# alleen, en O met het gemaal -- vallen '1' en '2' buiten de netwerkanalyse en meldt RVZ-006
# op streng '1'. Met het T-stuk als doorgeefknoop is het een deelstelsel mét overstort en
# afvoereindpunt, en is er niets te melden.
FIXTURES["net_hulpstuk_doorgeefknoop.ttl"] = (
    "geen; de gemengde strengen '1' en '2' hangen aan T-stuk T1 en bereiken via "
    "overstortput O het gemaal",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + put("PutO", "O", 1100.0, 2000.0, klasse="Overstortput")
    + gemaal("Gem", "G", (1150.0, 2000.0))
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "PutO")
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutO", "Gem"),
)

# RVZ-006 (#105): een gemengd deelstelsel dat over twee T-stukken doorloopt, zonder
# overstort en zonder afvoereindpunt. Streng '2' hangt met BEIDE einden aan een hulpstuk:
# zij ligt als kant in het deelstelsel maar staat in geen enkele put-index, dus wie de
# strengen van een deel bij `aansluitingen` opzoekt telt haar niet mee. En de twee
# T-stukken zijn doorgeefknopen: het deel telt twee knopen (put A en put B), niet vier.
FIXTURES["rvz006_gemengd_over_hulpstukken.ttl"] = (
    "een gemengd deelstelsel van drie strengen over twee T-stukken, zonder overstort en "
    "zonder afvoereindpunt; streng '2' hangt met beide einden aan een T-stuk",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + hulpstuk("T2", "T2", 1100.0, 2000.0)
    + put("PutB", "B", 1150.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "T2")
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "T2", "PutB"),
)


# NET/RVZ (#105): dezelfde keten met een afsluitstuk op de plaats van het T-stuk. Een
# `Afsluitstuk` draagt wel een GWSW-functie maar geen aantal leidingen (AfsluitenVanLeidingen),
# dus het is geen doorgeefknoop en blijft een breuk -- dezelfde grens als BO-72 voor TOP-002
# en TOP-003 trekt. Put A houdt daarom zijn eigen deelstelsel, zonder overstort en zonder
# afvoereindpunt.
FIXTURES["net_hulpstuk_afsluitstuk.ttl"] = (
    "de gemengde streng '1' eindigt op afsluitstuk A1, dat geen functie met een aantal "
    "draagt; put A blijft daardoor een deelstelsel zonder overstort en zonder afvoereindpunt",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("A1", "A1", 1050.0, 2000.0, klasse="Afsluitstuk")
    + put("PutO", "O", 1100.0, 2000.0, klasse="Overstortput")
    + gemaal("Gem", "G", (1150.0, 2000.0))
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "A1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "A1", "PutO")
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutO", "Gem"),
)


# Afbakening (#73): de kern kan het gemaal alleen via het persnet bereiken, en dat
# gemaal ligt ver buiten de contextbuffer van 50 m. Zonder de mechanische kanten in
# de componentberekening valt de route buiten de contextschil en meldt een
# gebiedsrun streng '1' terwijl de gemeentebrede run zwijgt -- precies de
# gelijkwaardigheid die BO-12 eist. Het gebied is `tests/fixtures/gis/
# afbakening_gebied.geojson` (990-1060 x 1990-2010).
FIXTURES["afbakening_persnet.ttl"] = (
    "geen; vuilwaterstreng '1' in de kern bereikt het gemaal alleen via twee drukleidingen",
    DRUKRIOLERING_KLASSEN
    + HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("Pomp", "P", 1050.0, 2000.0, klasse="Pompunit")
    + hulpstuk("T1", "T", 1200.0, 2000.0)
    + gemaal("Gem", "G", (1500.0, 2000.0))
    + leiding(
        "L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "Pomp", klasse="Vuilwaterriool"
    )
    + leiding("D1", "d1", [(1050.0, 2000.0), (1200.0, 2000.0)], "Pomp", "T1", klasse="Drukleiding")
    + leiding("D2", "d2", [(1200.0, 2000.0), (1500.0, 2000.0)], "T1", "Gem", klasse="Drukleiding"),
)


# De subklassehierarchie van de stelselfamilie, inline: de gedeelde prelude kent haar
# niet, en haar aan de prelude toevoegen zou alle 140 fixtures herschrijven.
STELSEL_HIERARCHIE = """gwsw:Vuilwaterstelsel rdfs:subClassOf gwsw:Rioolstelsel .
gwsw:GemengdStelsel rdfs:subClassOf gwsw:Rioolstelsel .
gwsw:Hemelwaterstelsel rdfs:subClassOf gwsw:Rioolstelsel .
gwsw:Rioolstelsel rdfs:subClassOf gwsw:Stelsel .
"""


def stelsel(naam: str, label: str, klasse: str, leden: list[str]) -> str:
    """Een geregistreerd stelselobject dat zijn leden via `hasPart` draagt (#17)."""
    delen = " , ".join(f":{lid}" for lid in leden)
    return f':{naam} rdf:type gwsw:{klasse} ; rdfs:label "{label}" ;\n    gwsw:hasPart {delen} .\n'


# De geregistreerde stelselboom die #17 blootlegde: twee lokale stelsels met alleen
# strengen plus een gemeentebrede `_geb_0`-bucket die naast een streng ook putten bevat.
# `dataset.stelsel_leden` scheidt die twee; de nulmetingjoin gebruikt dat onderscheid om
# een stelsel als focusnode te herkennen. Sinds issue #75 tekent de GeoPackage geen
# stelselvlakken meer, dus deze fixture voedt alleen nog die regel.
FIXTURES["stelsels_registratie.ttl"] = (
    "geen; twee lokale stelsels met alleen strengen plus een gemeentebrede bucket met "
    "strengen en putten",
    STELSEL_HIERARCHIE
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + gemaal("Gem", "G", (1100.0, 2000.0))
    + put("PutC", "C", 1000.0, 2100.0)
    + put("PutD", "D", 1050.0, 2100.0)
    + put("PutE", "E", 1000.0, 2200.0)
    + leiding(
        "LV1", "V1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB", klasse="Vuilwaterriool"
    )
    + leiding(
        "LV2", "V2", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "Gem", klasse="Vuilwaterriool"
    )
    + leiding("LG1", "G1", [(1000.0, 2100.0), (1050.0, 2100.0)], "PutC", "PutD")
    + leiding(
        "LH1", "H1", [(1000.0, 2200.0), (1050.0, 2200.0)], "PutE", None, klasse="Hemelwaterriool"
    )
    + stelsel("stelV", "vuilwater-1", "Vuilwaterstelsel", ["LV1", "LV2"])
    + stelsel("stelG", "gemengd-1", "GemengdStelsel", ["LG1"])
    + stelsel("stelH", "hemelwater-bucket", "Hemelwaterstelsel", ["LH1", "PutE"]),
)


# Het afvoereindpunt van de schone stelsels: net onder de overstort-/BBB-put.
GEM = (1050.0, 1950.0)

FIXTURES["rvz_schoon.ttl"] = (
    "geen; een gemengd stelsel met een aangesloten overstortput die op een sloot loost en "
    "een gemaal als afvoereindpunt, dus het voldoet aan beide eisen van RVZ-006",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=9.00, breedte=2000.0))
    + gemaal("Gem", "G", GEM)
    # Aan de gemengde trunk (vanaf PutO), bewust niet achter de overstortleiding L2: dan
    # zou L2 tussen twee gemengde zijden komen te liggen en RVZ-010 vuren.
    + hoogteleiding("L3", "3", [B, GEM], "PutO", "Gem", bob=(8.50, 8.45)),
)

# RVZ-002: de drempel draagt geen Drempelniveau.
FIXTURES["rvz002_drempel_zonder_niveau.ttl"] = (
    "de drempel van overstortput O heeft wel een breedte maar geen Drempelniveau",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=None, breedte=2000.0)),
)

# RVZ-002 (nam RVZ-003 op, #87): de drempel draagt geen Drempelbreedte.
FIXTURES["rvz003_drempel_zonder_breedte.ttl"] = (
    "de drempel van overstortput O heeft wel een niveau maar geen Drempelbreedte",
    _overstortstelsel(drempel("PutO", "DrempelO", niveau=9.00, breedte=None)),
)

# RVZ-002: er is helemaal geen drempelonderdeel, dus beide maten ontbreken.
FIXTURES["rvz002_overstort_zonder_drempel.ttl"] = (
    "overstortput O heeft geen enkel Overstortdrempel-onderdeel; RVZ-002 meldt beide "
    "ontbrekende maten in één melding",
    _overstortstelsel(""),
)

# RVZ-002: twee drempels op één put, beide met niveau maar zonder breedte -- de
# meervoudstak ("Geen van de N ...") die op De Wolden niet voorkomt.
FIXTURES["rvz002_twee_drempels_zonder_breedte.ttl"] = (
    "overstortput O heeft twee drempels, beide met een niveau maar zonder Drempelbreedte",
    _overstortstelsel(
        drempel("PutO", "DrempelO", niveau=9.00, breedte=None)
        + drempel("PutO", "DrempelP", niveau=9.50, breedte=None)
    ),
)

FIXTURES["rvz001_losse_overstort.ttl"] = (
    "overstortput O hangt aan geen enkele streng",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + put("PutO", "O", C[0], C[1], klasse="Overstortput")
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)

# RVZ-001 (issue #84): overstortput O hangt aan precies een streng, en die is loos
# (`LozeLeiding` = "leiding is buiten gebruik"). Sinds #84 telt een loze leiding niet
# meer als aansluiting, dus de put is net zo goed niet aangesloten als hierboven.
FIXTURES["rvz001_overstort_aan_loze_leiding.ttl"] = (
    "overstortput O hangt uitsluitend aan de loze leiding X1",
    LOZE_KLASSE
    + hoogteput("PutA", "A", A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput")
    + leiding("X1", "X1", [A, B], "PutA", "PutO", klasse="LozeLeiding"),
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

# RVZ-006 (issue #75): twee gemengde strengen in hetzelfde deelstelsel. De check meldt
# sinds #75 per gemengde streng en niet meer op een representatieve knoop, dus de fixture
# heeft er twee nodig om te laten zien dat beide bevindingen dezelfde `cluster_id` dragen
# en samen één deelstelselvlak in de laag `vlakken` opleveren.
FIXTURES["rvz006_gemengd_zonder_overstort.ttl"] = (
    "een gemengd deelstelsel van twee strengen zonder enige overstort of bergbezinkvoorziening",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteput("PutC", "C", C)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutB", "PutC", bob=(8.55, 8.50)),
)

# RVZ-006 (issue #75): hetzelfde gebrek, maar geen enkele streng draagt een bruikbare
# lijn -- de posList telt één punt, zoals `net_afvoerpad_zonder_lijn.ttl`. De bevindingen
# komen er gewoon (de check leest de graaf, niet de geometrie), maar er valt geen
# deelstelselvlak omheen te tekenen. De GeoPackage telt zo'n deelstelsel in
# `n_gemengd_zonder_vlak` in plaats van het stil weg te laten.
FIXTURES["rvz006_gemengd_zonder_geometrie.ttl"] = (
    "een gemengd deelstelsel zonder overstort waarvan de enige streng geen bruikbare "
    "lijngeometrie heeft",
    hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B)
    + hoogteleiding("L1", "1", [A], "PutA", "PutB", bob=(8.60, 8.55)),
)

# RVZ-006, tweede tak (issue #23): wel een overstort, geen afvoereindpunt.
FIXTURES["rvz006_gemengd_zonder_afvoereindpunt.ttl"] = (
    "een gemengd deelstelsel met overstort maar zonder afvoereindpunt (gemaal of overnamepunt)",
    hoogteput("PutA", "A", A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput", extra=kenmerken("PutO", **STANDAARDPUT))
    + drempel("PutO", "DrempelO", niveau=9.0, breedte=2000.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55)),
)

# RVZ-006 (issue #73): dezelfde tak, maar het deelstelsel eindigt op een pompunit. Die
# is een overdrachtspunt naar de drukriolering en geen afvoereindpunt (BO-55), dus het
# gemengde stelsel mist nog steeds zijn eindpunt.
FIXTURES["rvz006_gemengd_alleen_pompunit.ttl"] = (
    "een gemengd deelstelsel met overstort waarvan het enige eindpunt een pompunit is",
    "gwsw:Pompunit rdfs:subClassOf gwsw:Rioolput .\n\n"
    + hoogteput("PutA", "A", A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput", extra=kenmerken("PutO", **STANDAARDPUT))
    + drempel("PutO", "DrempelO", niveau=9.0, breedte=2000.0)
    + put("Pomp", "P", C[0], C[1], klasse="Pompunit", extra=kenmerken("Pomp", **STANDAARDPUT))
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutO", bob=(8.60, 8.55))
    + hoogteleiding("L2", "2", [B, C], "PutO", "Pomp", bob=(8.55, 8.50)),
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

FIXTURES["rvz008_bbb_met_lediging.ttl"] = (
    "geen; zelfde als rvz008_bbb_zonder_lediging maar de BBB draagt een "
    "geregistreerde ledigingsvoorziening en het stelsel voert af op een gemaal",
    hoogteput("PutA", "A", A)
    + bbb("BBB", "BBB", B)
    + drempel("BBB", "DrempelBBB", niveau=9.5, breedte=2000.0)
    + hoogteleiding("L1", "1", [A, B], "PutA", "BBB", bob=(8.60, 8.50))
    + """
:BBB gwsw:hasPart :BBB_led .
:BBB_led rdf:type gwsw:Ledigingsvoorziening ; rdfs:label "BBB/lediging" .
"""
    # Een afvoereindpunt, anders vuurt RVZ-006 op dit gemengde deel (issue #23).
    + gemaal("Gem", "G", GEM)
    + hoogteleiding("L2", "2", [B, GEM], "BBB", "Gem", bob=(8.40, 8.35)),
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

FIXTURES["adm007_overstort_met_drempel.ttl"] = (
    "geen; zelfde als adm007_overstort_zonder_functie maar put 'O' draagt een "
    "ingebouwde overstortdrempel",
    nette_put("PutA", "A", *A)
    + put("PutO", "O", B[0], B[1], klasse="Overstortput")
    + drempel("PutO", "DrempelO", niveau=9.00, breedte=2000.0)
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

# ADM-010: loze leidingen in ketens (issue #62). Elke fixture bevat precies een
# keten en precies een geval. Streng 0 en 1 zijn actief en komen binnen (bovenstrooms 2),
# X1 en X2 zijn loos, streng 3 is actief en gaat verder.
FIXTURES["adm010_loze_keten_doorgaand.ttl"] = (
    "actief riool loopt via loze strengen X1 en X2 door: aanvoer via 1, afvoer via 3 (issue #62)",
    LOZE_KLASSE
    + put("PutA0", "A0", 950.0, 2000.0)
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + put("PutD", "D", 1150.0, 2000.0)
    + put("PutE", "E", 1200.0, 2000.0)
    + leiding("L0", "0", [(950.0, 2000.0), (1000.0, 2000.0)], "PutA0", "PutA")
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"
    )
    + leiding(
        "X2", "X2", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutC", "PutD", klasse="LozeLeiding"
    )
    + leiding("L3", "3", [(1150.0, 2000.0), (1200.0, 2000.0)], "PutD", "PutE"),
)

FIXTURES["adm010_loze_keten_aanvoer.ttl"] = (
    "actieve streng 1 watert af op loze streng X1; er gaat niets verder (issue #62)",
    LOZE_KLASSE
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"
    ),
)

FIXTURES["adm010_loze_keten_afvoer.ttl"] = (
    "loze streng X1 voert af op actieve streng 3; er komt niets binnen (issue #62)",
    LOZE_KLASSE
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + put("PutD", "D", 1150.0, 2000.0)
    + leiding(
        "X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"
    )
    + leiding("L3", "3", [(1100.0, 2000.0), (1150.0, 2000.0)], "PutC", "PutD"),
)

# Dezelfde aanvoerketen, plus streng 9: die verlaat put B en raakt de keten dus wel,
# maar sluit in de afvoerrichting niet aan (inkomend blijft 1, er gaat niets verder).
# Het geval verandert er niet door; streng 9 staat alleen in het detail `rakend`.
FIXTURES["adm010_loze_keten_rakend.ttl"] = (
    "actieve streng 1 watert af op loze streng X1; actieve streng 9 verlaat dezelfde put B "
    "maar sluit niet aan (issue #62)",
    LOZE_KLASSE
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + put("PutE", "E", 1050.0, 2050.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB")
    + leiding(
        "X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"
    )
    + leiding("L9", "9", [(1050.0, 2000.0), (1050.0, 2050.0)], "PutB", "PutE"),
)

# Geen defect meer sinds #81: een loze keten zonder aansluiting op actief riool is de
# gewenste eindtoestand. ADM-010 telt hem in zijn verantwoording en meldt hem niet.
FIXTURES["adm010_loze_keten_losgekoppeld.ttl"] = (
    "loze streng X1 hangt aan geen enkele actieve streng; geen gebrek (issue #81)",
    LOZE_KLASSE
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1100.0, 2000.0)
    + leiding(
        "X1", "X1", [(1050.0, 2000.0), (1100.0, 2000.0)], "PutB", "PutC", klasse="LozeLeiding"
    ),
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
# De duiker (streng 6) kruist water-2 op eigen hoogte, los van streng 3.
EXT_G = (1010.0, 2013.0)
EXT_H = (1030.0, 2013.0)

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
    # Put E heeft geen putdekselniveau, net als elke put in De Wolden en Hoogeveen. De hoogtechecks
    # vallen dan terug op de maaiveldhoogte, en die komt hier uit AHN2. Zijn afwijking
    # is 0,12 m, dus hij komt in HGT-001 terecht (vanaf 0,10 m, issue #63).
    + hoogteput("PutE", "E", EXT_E, mv=10.12, dek=None, mv_wijze="AHN2")
    + hoogteput("PutF", "F", EXT_F, mv=12.00, dek=12.00)
    # Lozingsput ver van het water; Lozingsput vlakbij water-1. Geen van beide is sinds
    # issue #94 een bevinding van EXT-007: een Lozingsput loost volgens het GWSW naar een
    # ander rioolstelsel, dus daar hoort geen open water te liggen.
    + put("PutL1", "L1", 1005.0, 1990.0, klasse="Lozingsput")
    + put("PutL2", "L2", 1072.0, 2008.0, klasse="Lozingsput")
    # Uitlaatpunt U1, ver van het water: dit is wel een EXT-007-bevinding. Het GWSW legt
    # UitlaatPunt op de orientatie (een Aansluitpunt en dus een Knooppunt) en niet op het
    # object; de twee subklasseregels staan hier omdat de gedeelde prelude ze niet kent.
    + "# Het uitlaatpunt van issue #94: een bouwwerk met een UitlaatPunt-orientatie.\n"
    + "gwsw:Aansluitpunt rdfs:subClassOf gwsw:Knooppunt .\n"
    + "gwsw:UitlaatPunt rdfs:subClassOf gwsw:Aansluitpunt .\n"
    + put("PuntU1", "U1", 1005.0, 1985.0, klasse="Bouwwerk", orientatie="UitlaatPunt")
    # Streng 1 loopt door pand-1 heen: EXT-001.
    + hoogteleiding("L1", "1", [EXT_A, EXT_B], "PutA", "PutB", bob=(11.00, 9.50))
    # Streng 2 kruist water-1 en is geen zinker: EXT-003. Haar twee BOB's zijn tegelijk
    # de grensgevallen van HGT-003 op het vlakke raster van 10,00 m NAP: het beginpunt
    # ligt 3,50 m onder het maaiveld en blijft stil, het eindpunt 4,50 m en meldt.
    # De diepte-drempel ligt sinds BO-68 op 4,0 m.
    + hoogteleiding("L2", "2", [EXT_B, EXT_C], "PutB", "PutC", bob=(6.50, 5.50))
    # Streng 3 is een zinker die water-2 kruist: een echte doorkruising die EXT-003
    # bewust niet meldt. Een zinker is in de ontologie een VrijvervalRioolleiding en
    # zit dus in de populatie.
    + hoogteleiding("L3", "3", [EXT_E, EXT_F], "PutE", "PutF", bob=(9.60, 9.55)).replace(
        "gwsw:GemengdRiool", "gwsw:Zinker"
    )
    # Streng 6 is een duiker die water-2 kruist, net als streng 3, maar drie meter
    # noordelijker en op een eigen route: een duiker is geen rioolleiding (subklasse
    # van Leiding, niet van VrijvervalRioolleiding) en valt buiten de populatie van
    # EXT-003, dat hem dus niet meldt. Hij verbindt oppervlaktewater en
    # heeft dus geen rioolputten aan zijn uiteinden. Boven op streng 3 leverde hij
    # TOP-006 een samenvalmelding op; die check draait op alle leidingen.
    + leiding("L6", "6", [EXT_G, EXT_H], None, None, klasse="Duiker")
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
    + leiding("L5", "4", [(1022.0, 2000.0), (1028.0, 2000.0)], "PutP", "PutQ")
    + "\n"
    # De grensgevallen van issue #59, allemaal in de vrije strook y 1982-1995. Kale
    # putten en strengen (geen hoogte, BOB of inwinning), zodat alleen de
    # kruisingschecks ze zien. Streng 7 eindigt in water-3: lozingspunt, geen
    # bevinding. Streng 8 ligt 0,5 m naast water-4: binnen de zoekstraal, snijdt
    # niet, geen bevinding. Streng 9 doorkruist de 0,3 m smalle greppel water-5:
    # echte doorkruising, wel een bevinding. Streng 10 loopt over de oostrand van
    # water-6 (x = 1103): tangentieel, geen bevinding.
    + "# Grensgevallen van issue #59: streng 7 eindigt in een waterdeel (lozingspunt),\n"
    + "# streng 8 ligt 0,5 m naast een waterdeel, streng 9 doorkruist een 0,3 m smalle\n"
    + "# greppel, streng 10 loopt over de rand van een waterdeel. Alleen 9 is een bevinding.\n"
    + put("PutR", "R", 1060.0, 1988.0)
    + put("PutS", "S", 1082.0, 1988.0)
    + leiding("L7", "7", [(1060.0, 1988.0), (1082.0, 1988.0)], "PutR", "PutS")
    + put("PutT", "T", 1088.0, 1992.5)
    + put("PutU", "U", 1097.0, 1992.5)
    + leiding("L8", "8", [(1088.0, 1992.5), (1097.0, 1992.5)], "PutT", "PutU")
    + put("PutV", "V", 1045.0, 1988.0)
    + put("PutW", "W", 1055.0, 1988.0)
    + leiding("L9", "9", [(1045.0, 1988.0), (1055.0, 1988.0)], "PutV", "PutW")
    + put("PutX", "X", 1103.0, 1984.0)
    + put("PutY", "Y", 1103.0, 1994.0)
    + leiding("L10", "10", [(1103.0, 1984.0), (1103.0, 1994.0)], "PutX", "PutY"),
)


# De vijf grensgevallen van issue #63 op het vlakke raster van 10,00 m NAP uit
# tests/fixtures/gis/ext: 0,099 m zwijgt, 0,100 m is HGT-001 (ondergrens inclusief),
# 0,249 m blijft HGT-001, en 0,250 m is al HGT-002 -- de bovengrens van HGT-001 is
# exclusief en die van HGT-002 inclusief, dus precies op de gedeelde grens meldt alleen
# de zware check. 0,251 m ligt er net boven. Geen putdeksel, zoals in De Wolden en
# Hoogeveen; de maaiveldhoogte is dan het getoetste kenmerk. De afwijking wordt op
# millimeters afgerond vergeleken, anders is 10,10 - 10,00 in floating point 0,0999.
FIXTURES["hgt001_grens.ttl"] = (
    "de halfopen banden van HGT-001 en HGT-002, op de millimeter (issue #63)",
    hoogteput("Grens099", "099", (1000.0, 1990.0), mv=10.099, dek=None)
    + hoogteput("Grens100", "100", (1010.0, 1990.0), mv=10.100, dek=None)
    + hoogteput("Grens249", "249", (1020.0, 1990.0), mv=10.249, dek=None)
    + hoogteput("Grens250", "250", (1040.0, 1990.0), mv=10.250, dek=None)
    + hoogteput("Grens251", "251", (1030.0, 1990.0), mv=10.251, dek=None),
)


# Geen check maar de klassenselecties uit checks/selectie.py: het Juinen-voorbeeld
# bevat maar zes van de zeventien rollen, en een selectie die stil leeg blijft leest
# als "die rol komt niet voor". Hier staat precies een object per ontbrekende rol.
FIXTURES["selectie_rollen.ttl"] = (
    "geen -- deze fixture dekt de klassenselecties, niet een gebrek",
    # Bergbezinkleiding staat niet in de gedeelde prelude; alleen deze fixture heeft
    # hem nodig. De regel gaat met een toelichting mee het bestand in, zodat hij daar
    # niet als een losse zwerver leest.
    HULPSTUK_KLASSEN
    + LOZE_KLASSE
    + POMP_KLASSE
    + (
        "# Alleen deze fixture heeft de bergbezinkleiding nodig; de gedeelde prelude"
        " kent haar niet.\n"
        "gwsw:Bergbezinkleiding rdfs:subClassOf gwsw:VrijvervalRioolleiding .\n\n"
    )
    + put("Put1", "Put1", 1000.0, 2000.0)
    # De pompunit van issue #104: de drukriolering-indicatie van EXT-009 leest de rol
    # `pompunits`, en zonder object hier zou die rol uitsluitend op een lege selectie
    # getoetst worden.
    + put("Pomp1", "Pomp1", 1400.0, 2000.0, klasse="Pompunit")
    + put("Lozing1", "Lozing1", 1050.0, 2000.0, klasse="Lozingsput")
    + put("Val1", "Val1", 1200.0, 2000.0, klasse="Valput")
    # Overstortput en loze put staan hier ook, zodat de fixture alle zeventien rollen
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
    # Een T-stuk is een knoop (Hulpstukorientatie is een Knooppunt) maar geen put en
    # geen netwerkknoop; TOP-022/TOP-023 tellen er de leidingen op (issue #60).
    + hulpstuk("Tstuk1", "Tstuk1", 1350.0, 2000.0)
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
    # Een loze leiding is wel een gwsw:Leiding maar geen vrijvervalrioolleiding en
    # geen mechanische leiding (issue #62).
    + leiding(
        "Loos2", "Loos2", [(1300.0, 2000.0), (1300.0, 2050.0)], "Loos1", None, klasse="LozeLeiding"
    )
    # Een duiker is wel een gwsw:Leiding maar geen vrijvervalrioolleiding; hij hoort wel
    # bij de rol `nabijheidsleidingen`, en die grens is zonder hem niet zichtbaar (#82).
    + leiding(
        "Duiker1", "Duiker1", [(1000.0, 2200.0), (1050.0, 2200.0)], None, None, klasse="Duiker"
    )
    # Oppervlaktewater is lijnvormig en komt dus bij de verbindingen terecht.
    + leiding("Sloot1", "Sloot1", [(1000.0, 2100.0), (1250.0, 2100.0)], None, None, klasse="Sloot"),
)


# Issue #60, stap 1: de BrutIS-export koppelt elk leidingeinde op een hulpstuk aan
# `<hulpstuk>_put`, een URI zonder type of aspect, terwijl de orientatie `<hulpstuk>_ori`
# heet (in De Wolden `_put<n>`). Streng 1 heeft zo'n fantoomdoel en hoort na het herstel
# aan T1 te hangen. De andere drie zijn de tegenproeven: streng 2 koppelt netjes aan de
# orientatie, streng 3 wijst naar een stam die helemaal geen knoop is, en streng 4 naar
# `:PutB_put` -- put B bestaat en is een knoop, maar draagt een Putorientatie en geen
# Hulpstukorientatie. Zonder die vierde is de guard `stam in hulpstukken` niet te
# onderscheiden van een zwakkere `stam in nodes`.
FIXTURES["dataset_fantoomkoppeling.ttl"] = (
    "streng 1 koppelt haar eindpunt aan :T1_put, een URI die niet bestaat; de orientatie "
    "van T-stuk T1 heet :T1_ori (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", None)
    + ":L1_e gwsw:hasConnection :T1_put .\n"
    + put("PutB", "B", 1100.0, 2000.0)
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "PutB")
    + put("PutC", "C", 1050.0, 2050.0)
    + leiding("L3", "3", [(1050.0, 2050.0), (1050.0, 2000.0)], "PutC", None)
    + ":L3_e gwsw:hasConnection :Onbekend_put .\n"
    + put("PutD", "D", 1100.0, 2050.0)
    + leiding("L4", "4", [(1100.0, 2050.0), (1100.0, 2000.0)], "PutD", None)
    + ":L4_e gwsw:hasConnection :PutB_put .\n",
)


# TOP-022: T-stuk T1 heeft twee richtingen waar zijn functie er drie voorschrijft. De
# rest is in orde en mag niet melden: T3 heeft drie richtingen waarvan een dubbel gelegd
# (twee strengen naar put D, hartlijnen 5 cm uit elkaar), kruisstuk K1 heeft er vier
# en afsluitstuk A1 draagt geen functie met een aantal en valt buiten de toets.
FIXTURES["top022_hulpstuk_te_weinig.ttl"] = (
    "T-stuk T1 verbindt twee leidingen waar zijn GWSW-functie er drie voorschrijft; T3 "
    "(drie richtingen, een dubbel gelegd), kruisstuk K1 (vier) en afsluitstuk A1 zijn in "
    "orde (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1100.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "PutB")
    + put("PutC", "C", 1000.0, 2100.0)
    + put("PutD", "D", 1100.0, 2100.0)
    + put("PutE", "E", 1050.0, 2150.0)
    + hulpstuk("T3", "T3", 1050.0, 2100.0)
    + leiding("L3", "3", [(1000.0, 2100.0), (1050.0, 2100.0)], "PutC", "T3")
    + leiding("L4a", "4a", [(1050.0, 2100.0), (1100.0, 2100.0)], "T3", "PutD")
    + leiding("L4b", "4b", [(1050.0, 2100.0), (1075.0, 2100.05), (1100.0, 2100.0)], "T3", "PutD")
    + leiding("L5", "5", [(1050.0, 2100.0), (1050.0, 2150.0)], "T3", "PutE")
    + put("PutF", "F", 1000.0, 2200.0)
    + put("PutG", "G", 1100.0, 2200.0)
    + put("PutH", "H", 1050.0, 2250.0)
    + put("PutI", "I", 1050.0, 2170.0)
    + hulpstuk("K1", "K1", 1050.0, 2200.0, klasse="Kruisstuk")
    + leiding("L6", "6", [(1000.0, 2200.0), (1050.0, 2200.0)], "PutF", "K1")
    + leiding("L7", "7", [(1050.0, 2200.0), (1100.0, 2200.0)], "K1", "PutG")
    + leiding("L8", "8", [(1050.0, 2200.0), (1050.0, 2250.0)], "K1", "PutH")
    + leiding("L9", "9", [(1050.0, 2170.0), (1050.0, 2200.0)], "PutI", "K1")
    + put("PutJ", "J", 1150.0, 2000.0)
    + hulpstuk("A1", "A1", 1200.0, 2000.0, klasse="Afsluitstuk")
    + leiding("L10", "10", [(1150.0, 2000.0), (1200.0, 2000.0)], "PutJ", "A1"),
)

# TOP-023: T-stuk T2 verbindt vier verschillende knopen; voor vier bestaat Kruisstuk.
FIXTURES["top023_hulpstuk_te_veel.ttl"] = (
    "T-stuk T2 verbindt vier leidingen naar vier verschillende knopen waar zijn "
    "GWSW-functie er drie voorschrijft (issue #60)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1100.0, 2000.0)
    + put("PutC", "C", 1050.0, 2050.0)
    + put("PutD", "D", 1050.0, 1950.0)
    + hulpstuk("T2", "T2", 1050.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T2")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T2", "PutB")
    + leiding("L3", "3", [(1050.0, 2000.0), (1050.0, 2050.0)], "T2", "PutC")
    + leiding("L4", "4", [(1050.0, 1950.0), (1050.0, 2000.0)], "PutD", "T2"),
)


# TOP-002/TOP-003 (issue #89): een strengeinde dat op een hulpstuk met een telbare
# GWSW-functie valt is een geldig eind. Streng 1 loopt van put A naar T-stuk T1 en streng 2
# tussen T1 en T2; geen van beide is een gebrek. Streng 3 eindigt op afsluitstuk A1 -- dat
# draagt wel een functie maar geen aantal, dus het telt niet als eind -- en streng 4 ligt
# los in het veld. Het hulpstukgebrek zelf blijft bij TOP-022: T1 verbindt er twee en T2
# een, waar VerbindenVanDrieLeidingen er drie voorschrijft.
FIXTURES["top002_streng_op_hulpstuk.ttl"] = (
    "streng '4' ligt met beide einden los in het veld en streng '3' heeft aan een zijde "
    "alleen een afsluitstuk; de strengen '1' en '2' eindigen op een T-stuk en zijn goed "
    "(issue #89)",
    HULPSTUK_KLASSEN
    + put("PutA", "A", 1000.0, 2000.0)
    + hulpstuk("T1", "T1", 1050.0, 2000.0)
    + hulpstuk("T2", "T2", 1100.0, 2000.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "T1")
    + leiding("L2", "2", [(1050.0, 2000.0), (1100.0, 2000.0)], "T1", "T2")
    + put("PutB", "B", 1000.0, 2100.0)
    + hulpstuk("A1", "A1", 1050.0, 2100.0, klasse="Afsluitstuk")
    + leiding("L3", "3", [(1000.0, 2100.0), (1050.0, 2100.0)], "PutB", "A1")
    + leiding("L4", "4", [(1500.0, 2500.0), (1550.0, 2500.0)], None, None),
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

# ---------------------------------------------------------------------------
# Vier vormen die de lader zelf moeten bijten. De Wolden en Hoogeveen kent ze geen van vieren,
# dus zonder deze fixtures is er geen dataset waarop de reparaties uit issue #36
# zichtbaar zijn. Ze dragen geen defect: ze zijn conform GWSW 1.6 geschreven en
# horen dus juist wél gelezen te worden.
# ---------------------------------------------------------------------------

FIXTURES["dataset_zwaarverkeerdeksel.ttl"] = (
    "geen; put B draagt een Putdeksel_ZwaarVerkeer in plaats van een kaal Putdeksel",
    "# De subklasse staat niet in de gedeelde prelude; alleen deze fixture heeft haar nodig.\n"
    "gwsw:Putdeksel_ZwaarVerkeer rdfs:subClassOf gwsw:Putdeksel .\n\n"
    + hoogteput("PutA", "A", A)
    + hoogteput("PutB", "B", B, dek=None)
    + deksel("PutB", 9.95, klasse="Putdeksel_ZwaarVerkeer")
    + hoogteleiding("L1", "1", [A, B], "PutA", "PutB", bob=(8.60, 8.55)),
)


def _twee_houders(straat_eerst: bool) -> str:
    """Een compartiment onder twee houders, in de gevraagde schrijfvolgorde.

    Het GWSW staat meer dan een houder toe en rdflib levert ze in schrijfvolgorde
    op. Staat de straat vooraan, dan loopt een wandeling die de eerste houder volgt
    dood: een `Straat` is geen knoop en draagt zelf geen houder.
    """
    houders = [":PutB gwsw:hasPart :PutB_c1 .", ":Straat1 gwsw:hasPart :PutB_c1 ."]
    if straat_eerst:
        houders.reverse()
    return (
        nette_put("PutA", "A", *A)
        + nette_put("PutB", "B", *B)
        + nette_leiding("L1", "1", [A, B], "PutA", "PutB_c1")
        + '\n:Straat1 rdf:type gwsw:Straat ; rdfs:label "Dorpsstraat" .\n'
        + "\n".join(houders)
        + '\n:PutB_c1 rdf:type gwsw:Compartiment ; rdfs:label "B/c1" ;\n'
        "    gwsw:hasAspect :PutB_c1_ori .\n"
        ":PutB_c1_ori rdf:type gwsw:Compartimentorientatie .\n"
    )


FIXTURES["dataset_twee_houders_put_eerst.ttl"] = (
    "geen; compartiment B/c1 hangt onder put B en onder een straat, put eerst geschreven",
    _twee_houders(straat_eerst=False),
)

FIXTURES["dataset_twee_houders_straat_eerst.ttl"] = (
    "geen; hetzelfde compartiment onder dezelfde twee houders, straat eerst geschreven",
    _twee_houders(straat_eerst=True),
)

# Dezelfde twee putten en streng als elders, maar met `isPartOf` en `isAspectOf`
# geschreven. Het GWSW declareert die als de inverse van `hasPart` en `hasAspect`,
# dus dit is een conforme export -- alleen een andere schrijfrichting.
FIXTURES["dataset_inverse_properties.ttl"] = (
    "geen; alle insluitingen staan als isPartOf/isAspectOf in plaats van hasPart/hasAspect",
    """:PutA rdf:type gwsw:Inspectieput ; rdfs:label "A" .
:PutA_ori rdf:type gwsw:Putorientatie ; gwsw:isAspectOf :PutA .
:PutA_pun rdf:type gwsw:Punt ; gwsw:isAspectOf :PutA_ori ;
    gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1000.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral .
:PutB rdf:type gwsw:Inspectieput ; rdfs:label "B" .
:PutB_ori rdf:type gwsw:Putorientatie ; gwsw:isAspectOf :PutB .
:PutB_pun rdf:type gwsw:Punt ; gwsw:isAspectOf :PutB_ori ;
    gwsw:hasValue "<gml:Point xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:pos>1050.0 2000.0</gml:pos></gml:Point>"^^geo:gmlLiteral .
:L1 rdf:type gwsw:GemengdRiool ; rdfs:label "1" .
:L1_ori rdf:type gwsw:Leidingorientatie ; gwsw:isAspectOf :L1 .
:L1_lij rdf:type gwsw:Lijn ; gwsw:isAspectOf :L1_ori ;
    gwsw:hasValue "<gml:LineString xmlns:gml=\\"http://www.opengis.net/gml\\"><gml:posList srsDimension=\\"2\\">1000.0 2000.0 1050.0 2000.0</gml:posList></gml:LineString>"^^geo:gmlLiteral .
:L1_b rdf:type gwsw:BeginpuntLeiding ; gwsw:isPartOf :L1_ori ; gwsw:hasConnection :PutA_ori .
:L1_b_bob rdf:type gwsw:BobBeginpuntLeiding ; gwsw:isAspectOf :L1_b ; gwsw:hasValue 8.60 .
:L1_e rdf:type gwsw:EindpuntLeiding ; gwsw:isPartOf :L1_ori ; gwsw:hasConnection :PutB_ori .
:L1_e_bob rdf:type gwsw:BobEindpuntLeiding ; gwsw:isAspectOf :L1_e ; gwsw:hasValue 8.55 .
""",
)

# Een export mag beide schrijfrichtingen naast elkaar zetten -- ze zeggen hetzelfde.
# Wie ze allebei leest zonder te ontdubbelen, telt het kenmerk en het onderdeel twee
# keer, en dat is precies het soort dubbeltelling dat nergens een melding oplevert.
FIXTURES["dataset_dubbele_schrijfrichting.ttl"] = (
    "geen; put B schrijft dezelfde twee relaties zowel voorwaarts als invers",
    nette_put("PutA", "A", *A)
    + nette_put("PutB", "B", *B)
    + nette_leiding("L1", "1", [A, B], "PutA", "PutB")
    + """
:PutB gwsw:hasAspect :PutB_bd .
:PutB_bd gwsw:isAspectOf :PutB .
:PutB_bd rdf:type gwsw:Begindatum ; gwsw:hasValue "1980-01-01"^^xsd:date .
:PutB gwsw:hasPart :PutB_c1 .
:PutB_c1 gwsw:isPartOf :PutB .
:PutB_c1 rdf:type gwsw:Compartiment ; rdfs:label "B/c1" ;
    gwsw:hasAspect :PutB_c1_ori .
:PutB_c1_ori rdf:type gwsw:Compartimentorientatie .
""",
)

# Een uitlaatconstructie die daarnaast als bouwwerk getypeerd is. Alfabetisch wint
# "Bouwwerk", maar dat is de algemenere van de twee: de ontologie zegt dat
# Uitlaatconstructie een subklasse van Bouwwerk is.
FIXTURES["dataset_meervoudig_objecttype.ttl"] = (
    "geen; bouwwerk U draagt zowel gwsw:Bouwwerk als gwsw:Uitlaatconstructie",
    put("Uitlaat1", "U", 1100.0, 2000.0, klasse="Uitlaatconstructie").replace(
        "gwsw:Putorientatie", "gwsw:Bouwwerkorientatie"
    )
    + ":Uitlaat1 rdf:type gwsw:Bouwwerk .\n",
)


# Issue #74: de richtingspijl in de GeoPackage komt uit het BOB-verval, maar een
# persleiding is pompgestuurd en draagt geen vrijverval-BOB. Beide leidingen hier dragen
# hetzelfde verval (8,00 -> 7,50, dalend langs de getekende lijn); de vrijvervalstreng
# hoort daarvan `mee` te krijgen en de persleiding `onbekend`.
FIXTURES["richting_persleiding_met_bob.ttl"] = (
    "geen; een persleiding met een BOB-verval naast een vrijvervalstreng met hetzelfde "
    "verval (issue #74)",
    put("PutA", "A", 1000.0, 2000.0)
    + put("PutB", "B", 1050.0, 2000.0)
    + put("PutC", "C", 1000.0, 2050.0)
    + put("PutD", "D", 1050.0, 2050.0)
    + leiding("L1", "1", [(1000.0, 2000.0), (1050.0, 2000.0)], "PutA", "PutB", bob=(8.00, 7.50))
    + leiding(
        "P1",
        "p",
        [(1000.0, 2050.0), (1050.0, 2050.0)],
        "PutC",
        "PutD",
        klasse="Persleiding",
        bob=(8.00, 7.50),
    ),
)


# EXT-009 (issue #104): drie kandidaat-wegvakken uit `tests/fixtures/gis/ext`, waarvan
# er precies een riolering in zijn eigen voronoi-cel heeft. De NWB-lijnen, de bebouwde
# kom en de BGT-wegdelen komen uit `scripts/maak_gis_fixtures.py`:
#   Rioolstraat  (920, 1940)-(1000, 1940)  asfalt  -> deze riolering ligt erin: groen
#   Lege Laan   (1020, 1940)-(1100, 1940)  klinkers -> geen riolering: rood, W-melding
#   Grindweg     (920, 1910)-(1000, 1910)  zand     -> onverhard: niet beoordeeld, grijs
# De twee putten liggen ruim binnen de voronoi-cel van Rioolstraat (de buffer heeft een
# platte kap en eindigt op x = 920 en x = 1000, dus een put op het uiteinde zou op de
# rand liggen). Kale putten en leidingen zonder hoogte of BOB: alleen EXT-009 hoort
# deze fixture te lezen.
# Put W3 staat er los bij, op (1200, 1905): buiten elke kandidaat-cel (die reiken tot
# x = 1125), buiten elke corridor en buiten elke wegdekstrook, dus hij verandert geen enkel
# oordeel. Hij is er voor de equivalentietest van `tests/test_toetsloop.py`: die heeft een
# oostelijk studiegebied nodig dat de riolering van Rioolstraat *niet* in zijn analyseset
# krijgt maar wel een GWSW-object bevat -- een gebied zonder enig object is bij een run op
# een enkel gebied een harde fout, en dan valt de losse run niet te draaien.
FIXTURES["ext009_straten.ttl"] = (
    "een van de drie kandidaat-straten heeft geen riolering in haar eigen voronoi-cel",
    put("PutW1", "W1", 930.0, 1940.0)
    + put("PutW2", "W2", 990.0, 1940.0)
    + leiding("LW1", "W1-W2", [(930.0, 1940.0), (990.0, 1940.0)], "PutW1", "PutW2")
    + "# Losse put ver van elke straat; zie de toelichting in scripts/maak_ttl_fixtures.py.\n"
    + put("PutW3", "W3", 1200.0, 1905.0),
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
