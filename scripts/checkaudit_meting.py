"""Uitsplitsingen achter de checkaudit van augustus 2026 (docs/checks-audit-2026-08.md).

De aantallen F/W en `bekeken` in dat verslag komen rechtstreeks uit `bevindingen.json`,
en wat een check niet kon toetsen staat als toelichting in `bevindingen.md`. Dit script
levert de uitsplitsingen die in geen van beide staan en die het verslag wel citeert.

Deel A (TOP en ADM): per melding de populatie van beide betrokken objecten, het aandeel
`c*`-duplicaatlabels, waar de niet-gesnapte strengeinden van TOP-002/003 aan hangen, en
het effect van PRE-3 op de scope van TOP-006/010/011.

Deel B (ATTR en HGT): per check de uitsplitsing van de meldingstekst (materiaal, kant van
het bereik, objectsoort), de overlap tussen checks die op dezelfde grootheid rekenen
(HGT-004/013/018 op de buiskruin, HGT-005/006 tegen NET-003/009 voor PRE-1) en de
diepteverdeling van HGT-003, de meting achter de diepteligging-drempel.

Deel C (NET, RVZ, BTR en EXT): welke populatie NET-001 en NET-002 elk melden (het
verschil dat de steekproef niet zag), de deelverzameling NET-003 in NET-009 achter
PRE-1, de stelseltypecombinaties van NET-006, de gelijke populatie van RVZ-002 en
RVZ-003 achter S2, de gelijke uitslag van EXT-002 en EXT-003 achter PRE-4, en de
klassen achter de lozingspunten van EXT-007 (de scope-bug).

Bewaard omdat een meetscript dat een getal in een verslag onderbouwt navolgbaar hoort te
zijn (`docs/agents/analyse-harness.md`).

Gemeten op:
    run      uitvoer/audit_27082026/ (2026-08-27)
    commit   6311502 (63115026ddfffc5b67af7b47eafd08b6d025eb8f)
    dataset  data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl

Draaien vanuit de repo-root:
    uv run python scripts/checkaudit_meting.py [uitvoermap]
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

from gwsw_orox_helpers.bronnen import gebundelde_ontologie
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import GWSW
from rdflib import RDF, URIRef

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext
from nlriochecker.checks.hoogten import _staffeldrempel
from nlriochecker.checks.hoogten import _verhang as _hgt_verhang
from nlriochecker.checks.selectie import (
    functieloze_knopen,
    hulpstukken,
    infiltratieleidingen,
    leidingen,
    lozeleidingen,
    lozingspunten,
    mechanischeleidingen,
    overstortputten,
    vrijvervalrioolleidingen,
    vuilwaterleidingen,
)
from nlriochecker.checks.verbanden import verbonden_knopen

WORTEL = Path(__file__).resolve().parent.parent
DATASET = WORTEL / "data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl"
PROJECTCONFIG = WORTEL / "configs/dewoldenhoogeveen.toml"
STANDAARD_UITVOER = WORTEL / "uitvoer/audit_27082026"


def main(uitvoermap: Path) -> None:
    """Draait alle uitsplitsingen en print ze."""
    dataset, _ = laad_met_cache(
        DATASET, [gebundelde_ontologie()], fallback_encoding=FALLBACK_ENCODING
    )
    context = CheckContext(dataset=dataset, config=load_check_config(PROJECTCONFIG))
    meldingen = json.loads((uitvoermap / "bevindingen.json").read_text(encoding="utf-8"))[
        "meldingen"
    ]

    alle = {conduit.uri for conduit in leidingen(context)}
    vrij = {conduit.uri for conduit in vrijvervalrioolleidingen(context)}
    mech = {conduit.uri for conduit in mechanischeleidingen(context)}
    loos = {conduit.uri for conduit in lozeleidingen(context)}
    duiker = set(dataset.of_class("Duiker")) & alle
    drain = set(dataset.of_class("Drain")) & alle
    rest = alle - vrij - mech - loos - duiker - drain

    def soort(uri: str) -> str:
        """De populatie waarin deze leiding valt; 'geen leiding' voor knopen."""
        for naam, verzameling in (
            ("vrijverval", vrij),
            ("mechanisch", mech),
            ("duiker", duiker),
            ("drain", drain),
            ("loos", loos),
            ("aansluitleiding", rest),
        ):
            if uri in verzameling:
                return naam
        return "geen leiding"

    print(
        f"populatie: leidingen {len(alle)}, vrijverval {len(vrij)}, mechanisch {len(mech)}, "
        f"drain {len(drain)}, duiker {len(duiker)}, aansluitleiding {len(rest)}, loos {len(loos)}"
    )
    print(
        "aansluitleidingen per type:",
        collections.Counter(
            dataset.beheerobjecttype(uri) or "(zonder type)" for uri in rest
        ).most_common(),
    )

    # 1. Per paarcheck de populatie aan weerszijden van de melding.
    for check_id in ("TOP-006", "TOP-010", "TOP-011"):
        eigen = [m for m in meldingen if m["check_id"] == check_id]
        paren = collections.Counter(
            tuple(sorted((soort(m["object_uri"]), soort(m["object2_uri"])))) for m in eigen
        )
        toegestaan = vrij | duiker
        pre3 = sum(
            1 for m in eigen if m["object_uri"] in toegestaan and m["object2_uri"] in toegestaan
        )
        print(f"-- {check_id}: {len(eigen)} meldingen, onder PRE-3 (vrijverval+duiker) {pre3}")
        for paar, aantal in paren.most_common():
            print(f"   {paar}: {aantal}")

    # 2. Het aandeel `c*`-duplicaatlabels per putcheck (PRE-7).
    for check_id in ("TOP-001", "TOP-005", "TOP-021"):
        eigen = [m for m in meldingen if m["check_id"] == check_id]
        met_postfix = sum(1 for m in eigen if "  c" in m["object_label"])
        types = collections.Counter(
            dataset.beheerobjecttype(m["object_uri"]) or "(zonder type)" for m in eigen
        )
        print(
            f"-- {check_id}: {len(eigen)} meldingen, {met_postfix} met een c*-postfix; "
            f"types {types.most_common()}"
        )

    # 3. Waar hangen de niet-gesnapte strengeinden van TOP-002/003 aan?
    hulp = {node.uri for node in hulpstukken(context)}
    for check_id in ("TOP-002", "TOP-003"):
        tellers: collections.Counter[tuple[str, ...]] = collections.Counter()
        for melding in meldingen:
            if melding["check_id"] != check_id:
                continue
            conduit = dataset.conduits.get(melding["object_uri"])
            if conduit is None:
                tellers[("(geen streng)",)] += 1
                continue
            einden = []
            for rauw in (conduit.start_node, conduit.end_node):
                if rauw is None:
                    einden.append("geen koppeling")
                elif rauw in hulp:
                    einden.append("hulpstuk")
                else:
                    einden.append(dataset.beheerobjecttype(rauw) or "onherleid")
            tellers[tuple(sorted(einden))] += 1
        print(f"-- {check_id} einden: {tellers.most_common()}")

    # 4. TOP-019: kan de check op deze configuratie uberhaupt aanslaan?
    functieloos = functieloze_knopen(context)
    uris = {node.uri for node in functieloos}
    treffers = sum(
        1
        for conduit in leidingen(context)
        for uri in verbonden_knopen(context, conduit)
        if uri in uris
    )
    soorten = collections.Counter(
        dataset.beheerobjecttype(node.uri) or "(zonder type)" for node in functieloos
    )
    print(
        f"-- TOP-019: {len(functieloos)} functieloze knopen ({soorten.most_common()}); "
        f"{treffers} van de {2 * len(alle)} strengeinden komt erop uit"
    )

    deel_b(context, meldingen)


def _per_check(meldingen: list[dict]) -> dict[str, list[dict]]:
    """De meldingen gegroepeerd op check-ID."""
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for melding in meldingen:
        per[melding["check_id"]].append(melding)
    return per


def _tel(naam: str, meldingen: list[dict], patroon: str) -> None:
    """Telt de vangstgroepen van een regex over de meldingsteksten van een check."""
    teller: collections.Counter[tuple[str, ...]] = collections.Counter()
    ongevangen = 0
    for melding in meldingen:
        treffer = re.search(patroon, melding["boodschap"])
        if treffer is None:
            ongevangen += 1
        else:
            teller[treffer.groups()] += 1
    staart = f"; {ongevangen} zonder treffer" if ongevangen else ""
    print(f"-- {naam}: {len(meldingen)} meldingen{staart}")
    for groepen, aantal in teller.most_common(12):
        print(f"   {groepen}: {aantal}")


def _zijden(meldingen: list[dict]) -> set[tuple[str, str]]:
    """Per melding het paar (object, zijde); twee einden van dezelfde streng zijn twee gevallen."""
    gevonden = set()
    for melding in meldingen:
        treffer = re.search(r"aan het (beginpunt|eindpunt)", melding["boodschap"])
        gevonden.add((melding["object_uri"], treffer.group(1) if treffer else ""))
    return gevonden


def _objecten(meldingen: list[dict]) -> set[str]:
    """De URI's waarop een check heeft gemeld."""
    return {melding["object_uri"] for melding in meldingen}


def deel_b(context: CheckContext, meldingen: list[dict]) -> None:
    """De uitsplitsingen achter de ATTR- en HGT-secties van het verslag."""
    dataset = context.dataset
    per = _per_check(meldingen)

    # 1. Wat de meldingstekst per check uitsplitst.
    _tel("ATTR-001", per["ATTR-001"], r"ligt (onder|boven) het bereik .* materiaal (\w+)")
    _tel("ATTR-003", per["ATTR-003"], r"Materiaal (\w+) met begindatum (\d{4})")
    _tel("ATTR-008", per["ATTR-008"], r"ligt (onder|boven) de grens van (\S+) m")
    _tel("ATTR-016", per["ATTR-016"], r"breedte \S+ mm en lengte (0|\S+) mm")
    _tel("ATTR-018", per["ATTR-018"], r"Deze (put|streng)")
    _tel("HGT-003", per["HGT-003"], r"ligt (boven het AHN-maaiveld|[\d.]+ m onder)")
    _tel("HGT-004", per["HGT-004"], r"ligt (boven het \w+|onder de bodem)")
    _tel("HGT-013", per["HGT-013"], r"ligt (onder|boven) de grens")
    _tel("HGT-018", per["HGT-018"], r"aan het (beginpunt|eindpunt)")
    _tel("ATTR-002", per["ATTR-002"], r"gangbare ondergrens van (\S+) mm voor (.*?)\.")

    # 1b. ATTR-002: hoeveel meldingen komen alleen door de 250 mm van gemengd/hemelwater?
    boven_200 = sum(
        1
        for melding in per["ATTR-002"]
        if (
            t := re.search(r"Profielmaat (\S+) mm .* ondergrens van (\S+) mm", melding["boodschap"])
        )
        and float(t.group(2)) > 200
        and float(t.group(1)) >= 200
    )
    print(
        f"-- ATTR-002: {boven_200} meldingen zouden bij een enkele ondergrens van 200 mm wegvallen"
    )

    # 1c. De omvang van het tegenverhang: waar ligt de grens tussen licht en fors?
    for check_id in ("HGT-005", "HGT-006"):
        stijgingen = sorted(
            float(t.group(1))
            for melding in per[check_id]
            if (t := re.search(r"stijgt ([\d.]+) m", melding["boodschap"])) is not None
        )
        if stijgingen:
            deel = len(stijgingen)
            boven = {f">{g:g} m": sum(1 for s in stijgingen if s > g) for g in (0.1, 0.2, 0.5)}
            print(
                f"-- {check_id} stijging: min {stijgingen[0]:.3f}, mediaan "
                f"{stijgingen[deel // 2]:.3f}, p90 {stijgingen[9 * deel // 10]:.3f}, "
                f"max {stijgingen[-1]:.3f}, {boven}"
            )

    # 2. ATTR-013 meldt op twee objectsoorten tegelijk; de kenmerken staan in de tekst.
    knoop = sum(1 for m in per["ATTR-013"] if m["object_uri"] in dataset.nodes)
    streng = sum(1 for m in per["ATTR-013"] if m["object_uri"] in dataset.conduits)
    kenmerken: collections.Counter[str] = collections.Counter()
    for melding in per["ATTR-013"]:
        for kenmerk in re.findall(r"(Bob\w+|Maaiveldhoogte|Putdekselniveau)", melding["boodschap"]):
            kenmerken[kenmerk] += 1
    print(f"-- ATTR-013: {knoop} knopen, {streng} strengen; kenmerken {kenmerken.most_common()}")

    # 3. De kanttekening van HGT-001/002: hoogte tegen hoogtemodel in plaats van tegen meting.
    for check_id in ("HGT-001", "HGT-002"):
        eigen = per[check_id]
        uit_model = sum(1 for m in eigen if "Let op:" in m["boodschap"])
        print(f"-- {check_id}: {len(eigen)} meldingen, {uit_model} met de hoogtemodel-kanttekening")

    # 4. De diepteverdeling achter HGT-003: waar zou een diepteligging-drempel liggen?
    diepten = sorted(
        float(treffer.group(1))
        for melding in per["HGT-003"]
        if (treffer := re.search(r"ligt ([\d.]+) m onder", melding["boodschap"])) is not None
    )
    if diepten:
        deel = len(diepten)
        kwantielen = {f"p{pct}": diepten[min(deel - 1, pct * deel // 100)] for pct in (50, 90, 99)}
        boven = [4.0, 5.0, 6.0]
        tellingen = {f">{grens:g} m": sum(1 for d in diepten if d > grens) for grens in boven}
        print(
            f"-- HGT-003 diepte onder AHN: {deel} meldingen, min {diepten[0]:.2f}, "
            f"max {diepten[-1]:.2f}, {kwantielen}, {tellingen}"
        )

    # 5. Overlap tussen de checks die op dezelfde grootheid rekenen.
    paren = (
        ("HGT-004", "HGT-018", "buiskruin ligt per definitie boven de BOB"),
        ("HGT-013", "HGT-018", "negatieve gronddekking is kruin boven maaiveld"),
        ("ATTR-001", "ATTR-002", "twee ondergrenzen op dezelfde profielmaat"),
        ("HGT-005", "NET-003", "PRE-1: zit het richtingsdeel al in de NET-checks?"),
        ("HGT-006", "NET-003", "PRE-1"),
        ("HGT-006", "NET-009", "PRE-1"),
        ("HGT-005", "NET-009", "PRE-1"),
        ("HGT-014", "HGT-006", "tegenverhang verklaart een afwijkend maaiveldverloop"),
        ("HGT-013", "HGT-003", "te veel gronddekking is dezelfde diepteligging"),
    )
    for links, rechts, waarom in paren:
        gedeeld = _objecten(per[links]) & _objecten(per[rechts])
        print(
            f"-- {links} n {rechts}: {len(gedeeld)} objecten gedeeld "
            f"({len(_objecten(per[links]))} resp. {len(_objecten(per[rechts]))}) -- {waarom}"
        )
    op_zijde = _zijden(per["HGT-004"]) & _zijden(per["HGT-018"])
    print(f"-- HGT-004 n HGT-018 op (object, zijde): {len(op_zijde)} van de {len(per['HGT-004'])}")

    # 6. De buiskruin-methode: kent deze export een wanddikte om mee te rekenen?
    for kenmerk in ("Wanddikte", "HoogtePut", "Putdekselniveau", "Overstortdrempel"):
        aantal = sum(1 for _ in dataset.graph.subjects(RDF.type, URIRef(GWSW + kenmerk)))
        print(f"-- instanties van {kenmerk}: {aantal}")

    # 7. De echte noemer van HGT-007: `bekeken` telt alle vrijvervalstrengen, maar de
    # check toetst alleen de vuilwaterrol met verval naar beneden en een staffeldrempel.
    vuilwater = {conduit.uri for conduit in vuilwaterleidingen(context)}
    staffel = context.config.verhang_staffel
    toetsbaar = 0
    for conduit in vrijvervalrioolleidingen(context):
        if conduit.uri not in vuilwater:
            continue
        verhang = _hgt_verhang(conduit)
        if verhang is None or verhang < 0 or _staffeldrempel(staffel, conduit.breedte_mm) is None:
            continue
        toetsbaar += 1
    print(
        f"-- HGT-007: {len(per['HGT-007'])} meldingen op {toetsbaar} werkelijk getoetste strengen"
    )

    deel_c(context, meldingen)


def _clusters(meldingen: list[dict]) -> int:
    """Het aantal verschillende deelstelsels waarop een check meldt."""
    return len({melding["cluster_id"] for melding in meldingen if melding["cluster_id"]})


def deel_c(context: CheckContext, meldingen: list[dict]) -> None:
    """De uitsplitsingen achter de NET-, RVZ-, BTR- en EXT-secties van het verslag."""
    dataset = context.dataset
    klassen = context.config.klassen
    per = _per_check(meldingen)

    def stelseltype(uri: str) -> str:
        """Het stelseltype van de gemelde streng, of waarom er geen is."""
        conduit = dataset.conduits.get(uri)
        if conduit is None:
            return "(geen streng)"
        return klassen.stelseltype(conduit.types, dataset.closure) or "(geen stelseltype)"

    # 1. NET-001 en NET-002 melden op verschillende populaties en met verschillende
    # eindpunten; de steekproef vroeg wat het verschil is.
    for check_id in ("NET-001", "NET-002"):
        soorten = collections.Counter(stelseltype(m["object_uri"]) for m in per[check_id])
        print(
            f"-- {check_id}: {len(per[check_id])} meldingen in {_clusters(per[check_id])} "
            f"deelstelsels; stelseltypen {soorten.most_common()}"
        )
    print(
        f"-- NET-001 n NET-002: {len(_objecten(per['NET-001']) & _objecten(per['NET-002']))} "
        "objecten gedeeld"
    )

    # 2. Het richtingscluster van PRE-1: is NET-003 een deelverzameling van NET-009?
    net003, net009 = _objecten(per["NET-003"]), _objecten(per["NET-009"])
    print(
        f"-- NET-003 n NET-009: {len(net003 & net009)} van de {len(net003)} NET-003-objecten "
        f"({len(net009)} bij NET-009); alleen NET-009: {len(net009 - net003)}"
    )
    _tel("NET-009 geometrie", per["NET-009"], r"De lijn is (omgekeerd getekend|in de van-naar)")
    _tel("NET-009 bob", per["NET-009"], r"De BOB (stijgt|daalt|ligt vlak|ontbreekt)")

    # 3. De stelseltype-checks: wat melden ze precies?
    _tel(
        "NET-005",
        per["NET-005"],
        r"stelseltype '(\w+)' terwijl alle \d+ buurstrengen van type (.*?) zijn",
    )
    _tel("NET-006", per["NET-006"], r"Hier komen (\d+) stelseltypen samen")
    _tel("RVZ-005", per["RVZ-005"], r"uitsluitend aan strengen van type (.*?)\.")
    _tel("RVZ-010", per["RVZ-010"], r"ligt uitsluitend stelseltype (.*?);")

    # 3b. NET-006 op de combinatie van soorten, zonder de strenglabels ertussen.
    combinaties: collections.Counter[tuple[str, ...]] = collections.Counter()
    for melding in per["NET-006"]:
        treffer = re.search(r"stelseltypen samen \((.*)\)\.$", melding["boodschap"])
        if treffer is not None:
            combinaties[
                tuple(sorted(deel.split(":")[0].strip() for deel in treffer.group(1).split("; ")))
            ] += 1
    print(f"-- NET-006 combinaties: {combinaties.most_common(12)}")

    # 4. NET-007 en RVZ-006: hoeveel van de populatie melden ze, en op hoeveel stelsels?
    infiltratie = len(infiltratieleidingen(context))
    print(
        f"-- NET-007: {len(per['NET-007'])} meldingen op {infiltratie} infiltratieleidingen; "
        f"{len(overstortputten(context))} overstortputten in de dataset"
    )
    print(
        f"-- RVZ-006: {len(per['RVZ-006'])} meldingen in {_clusters(per['RVZ-006'])} deelstelsels"
    )

    # 5. RVZ-002 en RVZ-003 (S2): dezelfde putten, dezelfde basis?
    print(
        f"-- RVZ-002 n RVZ-003: {len(_objecten(per['RVZ-002']) & _objecten(per['RVZ-003']))} van "
        f"elk {len(_objecten(per['RVZ-002']))} resp. {len(_objecten(per['RVZ-003']))} objecten"
    )

    # 6. EXT-001: welke relatie, en op welk objectsoort?
    _tel("EXT-001", per["EXT-001"], r"Dit object (ligt volledig binnen|kruist|ligt [\d.]+ m van)")
    knoop = sum(1 for m in per["EXT-001"] if m["object_uri"] in dataset.nodes)
    print(f"-- EXT-001: {knoop} putten, {len(per['EXT-001']) - knoop} strengen")

    # 7. EXT-002 en EXT-003 (PRE-4): dezelfde doorkruisingen?
    print(
        f"-- EXT-002 n EXT-003: {len(_objecten(per['EXT-002']) & _objecten(per['EXT-003']))} van "
        f"elk {len(_objecten(per['EXT-002']))} resp. {len(_objecten(per['EXT-003']))} objecten"
    )

    # 8. EXT-007 (scope-bug): welke lozingspuntklassen melden en welke bestaan er?
    gemeld = collections.Counter(
        dataset.beheerobjecttype(m["object_uri"]) or "(zonder type)" for m in per["EXT-007"]
    )
    populatie = collections.Counter(
        dataset.beheerobjecttype(node.uri) or "(zonder type)" for node in lozingspunten(context)
    )
    print(f"-- EXT-007 gemeld: {gemeld.most_common()}; populatie: {populatie.most_common()}")
    for naam in (
        "Lozingspunt",
        "LozingspuntBodem",
        "LozingspuntOppervlaktewater",
        "UitlaatPunt",
        "Uitlaatconstructie",
        "Uitlaat",
        "Lozingsput",
        "Overnamepunt",
    ):
        direct = sum(1 for _ in dataset.graph.subjects(RDF.type, URIRef(GWSW + naam)))
        print(
            f"-- klasse {naam}: {direct} directe instanties, "
            f"{len(dataset.of_class(naam))} incl. subklassen"
        )


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else STANDAARD_UITVOER)
