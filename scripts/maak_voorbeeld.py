#!/usr/bin/env python
"""Bouwt het getrackte voorbeeld `voorbeelden/koekangerveld/` uit de volle data.

De repository draagt geen invoerdata: `data/` staat op een handvol Markdown-bestanden
na buiten versiebeheer. Wie de package uitprobeert heeft daardoor niets om `toets` op
te draaien. Dit script snijdt uit de niet-getrackte De Wolden- en Hoogeveen-export een
voorbeeld dat wel klein genoeg is om mee te reizen: de buurt Koekangerveld.

Wat er gebeurt, in deze volgorde:

1. **De analyseset.** `afbakening.bouw_analyseset` levert kern en contextschil van de
   Koekangerveld-buurt -- dezelfde afbakening die `toets --studiegebied` gebruikt.
2. **De TTL.** De export wordt met pyoxigraph gestreamd (dezelfde parser als de
   leeslaag) en per subject bewaard. Het voorbeeld krijgt de triples van de objecten
   uit de analyseset, van alles wat er via `hasPart`/`hasAspect` onder hangt, van de
   `hasConnection`-buren (daar hangt de maaiveldhoogte) en van de stelsels, straten en
   gebieden waarin de objecten hangen. Een verwijzing naar een object dat niet meekomt
   wordt weggelaten, zodat het bestand op zichzelf klopt; zonder die snoei zou een
   gemeentebrede stelselbak alleen al duizenden dode verwijzingen meeslepen.
   Het resultaat is Turtle van rdflib -- schone UTF-8, dus zonder de CP850-bytes in de
   straatnamen van de BrutIS-export, en niet byte-gelijk aan het origineel.
3. **De SHACL-rapporten.** Per rapport blijven het kopblok en de regels over waarvan de
   focusnode in het voorbeeld op een object uitkomt, plus de `CfkTypes_typ`-regels: die
   dragen de typeringspoort en wijzen niet naar een object. Welke regel op een object
   uitkomt, beslist `nulbevinding.bouw_nulbevindingen` op het zojuist geschreven
   voorbeeld -- dezelfde join als de pijplijn, geen tweede afleiding.
4. **De externe bronnen.** BGT, BAG, NWB en TOP10NL gaan bit voor bit mee: dan kan de
   EXT-uitslag per constructie niet van de gebiedsrun verschillen. Het studiegebied
   wordt met `VACUUM INTO` gecompacteerd (7,8 MB aan vrije pagina's om een enkel vlak).
   Het AHN gaat niet mee (12 MB); HGT-001 t/m HGT-003 melden dan zelf dat ze niets
   konden toetsen. Welk bestand welke rol vervult komt uit `[bronnen]` in de
   meegeleverde `checks.toml`, niet uit een tweede lijst hier.
5. **De README** van de voorbeeldmap. Een eigen projectconfiguratie krijgt het voorbeeld
   niet: `toets` overschrijft `[bronnen] map` toch met de map achter `--bronnen`, dus een
   kopie van `checks.toml` zou geen enkele werkzame wijziging dragen en alleen uit de pas
   kunnen gaan lopen.

De uitvoer is gegenereerd en wordt nooit met de hand bijgewerkt; zie de tabel
"Gegenereerde bestanden" in `docs/agents/analyse-harness.md`.

Gebruik:  uv run python scripts/maak_voorbeeld.py
"""

from __future__ import annotations

import csv
import shutil
import sqlite3
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import pyoxigraph
from gwsw_orox_helpers.cache import laad_met_cache
from gwsw_orox_helpers.dataset import GWSW, GwswDataset, load_dataset
from gwsw_orox_helpers.graaf import naar_rdflib
from rdflib import Graph

from nlriochecker.afbakening import Analyseset, bouw_analyseset
from nlriochecker.checkconfig import FALLBACK_ENCODING, CheckConfig, load_check_config
from nlriochecker.meting import laad_nulmeting
from nlriochecker.nulbevinding import bouw_nulbevindingen
from nlriochecker.shaclrapport import DELIMITER, ENCODING, KOLOMMEN, VORM_TE_GLOBAAL
from nlriochecker.studiegebied import load_study_area

WORTEL = Path(__file__).resolve().parents[1]
DOEL = WORTEL / "voorbeelden" / "koekangerveld"

BRON_TTL = WORTEL / "data" / "gwsw_orox_ttl" / "dewoldenhoogeveen_orox.ttl"
BRON_SHACL = WORTEL / "data" / "shacl_nulmeting"
BRON_GIS = WORTEL / "data" / "gis_koekangerveld"

DOEL_TTL = "koekangerveld_orox.ttl"

# De relaties waarlangs het voorbeeld omlaag sluit. `hasPart` en `hasAspect` zijn
# insluitingen: wat eraan hangt hoort bij de houder en moet mee, anders verliest een put
# haar deksel en een streng haar BOB. `hasConnection` is geen insluiting en gaat daarom
# maar een stap mee (zie `_buren`).
HAS_PART = pyoxigraph.NamedNode(f"{GWSW}hasPart")
HAS_ASPECT = pyoxigraph.NamedNode(f"{GWSW}hasAspect")
HAS_CONNECTION = pyoxigraph.NamedNode(f"{GWSW}hasConnection")
INSLUITEND = (HAS_PART, HAS_ASPECT)

# De prefixen van de export, zodat de Turtle net zo leest als het origineel.
PREFIXEN = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "geo": "http://www.opengis.net/ont/geosparql#",
    "gwsw": GWSW,
}

Triples = dict[pyoxigraph.NamedNode, list[tuple[pyoxigraph.NamedNode, object]]]


def _lees_export(pad: Path) -> Triples:
    """Leest de volledige export en groepeert de triples op subject.

    Met pyoxigraph en niet met rdflib: de rdflib-store kost op deze export minuten en
    gigabytes, deze lezing acht seconden en circa 800 MB. De export draagt geen enkele
    blanke knoop (nagemeten: 0 van 650.470 subjecten), dus een subject is altijd een
    benoemde knoop en er valt niets te sluiten over anonieme houders.
    """
    rauw = pad.read_bytes()
    try:
        # Turtle hoort UTF-8 te zijn; de BrutIS-export van De Wolden en Hoogeveen is dat
        # niet. Eerst UTF-8 proberen, net als de lader: cp850 decodeert elke bytereeks
        # zonder fout en zou een correct bestand stilzwijgend verminken.
        tekst = rauw.decode("utf-8")
    except UnicodeDecodeError:
        tekst = rauw.decode(FALLBACK_ENCODING)
    per_subject: Triples = defaultdict(list)
    for quad in pyoxigraph.parse(tekst.encode("utf-8"), format=pyoxigraph.RdfFormat.TURTLE):
        if not isinstance(quad.subject, pyoxigraph.NamedNode):
            raise SystemExit(f"{pad}: onverwacht subject {quad.subject!r}; geen benoemde knoop.")
        per_subject[quad.subject].append((quad.predicate, quad.object))
    return per_subject


def _omlaag(triples: Triples, start: Iterable[pyoxigraph.NamedNode]) -> set[pyoxigraph.NamedNode]:
    """Alles wat via hasPart en hasAspect onder deze subjecten hangt."""
    gevonden = set(start)
    laag = list(gevonden)
    while laag:
        volgende = []
        for subject in laag:
            for predicaat, object_ in triples.get(subject, ()):
                if predicaat not in INSLUITEND or not isinstance(object_, pyoxigraph.NamedNode):
                    continue
                if object_ not in gevonden:
                    gevonden.add(object_)
                    volgende.append(object_)
        laag = volgende
    return gevonden


def _buren(triples: Triples, gekozen: set[pyoxigraph.NamedNode]) -> set[pyoxigraph.NamedNode]:
    """De hasConnection-buren van de gekozen subjecten, een stap ver.

    Een stap, want hasConnection is symmetrisch en zonder rem loopt hij het hele net
    door. Die ene stap is wel nodig: het GWSW hangt de maaiveldhoogte niet aan de put
    maar aan een maaiveldorientatie die er via hasConnection naast staat, en zonder die
    buur verliest elke put in het voorbeeld haar maaiveld.
    """
    gevonden: set[pyoxigraph.NamedNode] = set()
    for subject in gekozen:
        for predicaat, object_ in triples.get(subject, ()):
            if predicaat == HAS_CONNECTION and isinstance(object_, pyoxigraph.NamedNode):
                gevonden.add(object_)
    return gevonden - gekozen


def _houders(triples: Triples, gekozen: set[pyoxigraph.NamedNode]) -> set[pyoxigraph.NamedNode]:
    """De stelsels, straten en gebieden die een gekozen object via hasPart dragen.

    Ze komen er als geheel bij en niet alleen als naam: `nulbevinding` herkent een
    stelsel aan zijn `rdf:type` en leest zijn leden. Hun ledenlijst wordt bij het
    schrijven gesnoeid tot wat er werkelijk in staat (zie `_schrijf_ttl`); de drie
    gemeentebrede bakken van deze export dragen samen ruim achttienduizend leden.
    """
    gevonden: set[pyoxigraph.NamedNode] = set()
    for subject, uitgaand in triples.items():
        if subject in gekozen:
            continue
        if any(predicaat == HAS_PART and object_ in gekozen for predicaat, object_ in uitgaand):
            gevonden.add(subject)
    return gevonden


def _subjectverzameling(
    triples: Triples, dataset: GwswDataset, analyseset: Analyseset
) -> set[pyoxigraph.NamedNode]:
    """De subjecten die het voorbeeld draagt, in vier lagen."""
    basis = {pyoxigraph.NamedNode(uri) for uri in analyseset.alles}
    basis |= {
        pyoxigraph.NamedNode(node.orientation)
        for uri in analyseset.alles
        if (node := dataset.nodes.get(uri)) is not None and node.orientation
    }
    gekozen = _omlaag(triples, basis)
    gekozen = _omlaag(triples, gekozen | _buren(triples, gekozen))
    return gekozen | _houders(triples, gekozen)


def _naamruimte(gekozen: set[pyoxigraph.NamedNode]) -> str:
    """De naamruimte van de export, afgeleid uit de gekozen subjecten.

    Een OroX-export gebruikt een enkele naamruimte voor al haar objecten
    (`http://sparql.gwsw.nl/<export>#`); dezelfde afleiding als `nulbevinding._basis`.
    Zonder deze binding schrijft rdflib elke URI voluit en is het voorbeeld drie keer
    zo groot en onleesbaar.
    """
    for subject in sorted(knoop.value for knoop in gekozen):
        if "#" in subject:
            return subject.rsplit("#", 1)[0] + "#"
    raise SystemExit("geen naamruimte met '#' gevonden in de gekozen subjecten.")


def _schrijf_ttl(
    triples: Triples, gekozen: set[pyoxigraph.NamedNode], doel: Path, alle_subjecten: set[str]
) -> tuple[int, int]:
    """Schrijft de gekozen triples als Turtle; geeft (triples, subjecten) terug.

    Een verwijzing naar een subject dat niet meekomt gaat eruit: anders draagt het
    voorbeeld dode verwijzingen die alleen ruimte kosten. Verwijzingen naar iets dat in
    de volledige export ook geen subject is blijven staan -- de BrutIS-export koppelt
    elk leidingeinde op een hulpstuk aan een `<hulpstuk>_put`-URI zonder eigen triples,
    en het koppelingsherstel van de lader hangt daarop (SIG-hulpstukkoppeling).

    Het aantal subjecten komt uit de geschreven graaf en niet uit `gekozen`: die
    verzameling draagt ook de dertig `hasConnection`-doelen zonder eigen triples, en die
    komen als subject nergens in het bestand terug.
    """
    graaf = Graph()
    for prefix, ruimte in {**PREFIXEN, "": _naamruimte(gekozen)}.items():
        graaf.bind(prefix, ruimte)
    aantal = 0
    for subject in gekozen:
        for predicaat, object_ in triples.get(subject, ()):
            if isinstance(object_, pyoxigraph.NamedNode):
                if object_.value in alle_subjecten and object_ not in gekozen:
                    continue
            graaf.add((naar_rdflib(subject), naar_rdflib(predicaat), naar_rdflib(object_)))
            aantal += 1
    graaf.serialize(destination=doel, format="turtle", encoding="utf-8")
    return aantal, len(set(graaf.subjects()))


def _vectorbronnen(config: CheckConfig) -> list[str]:
    """De bestandsnamen van de vectorbronnen, uit de meegeleverde configuratie.

    Niet als eigen lijst hier: `[bronnen]` in `checks.toml` is de plek waar staat welk
    bestand welke rol vervult, en een tweede lijst zou bij een hernoeming stil
    achterblijven. Het hoogteraster staat er bewust niet bij -- dat gaat niet mee.
    """
    bronnen = config.bronnen
    namen = [bronnen.bgt, bronnen.bag_pand, bronnen.nwb_wegvakken, bronnen.top10nl]
    return [naam for naam in namen if naam]


def _kopieer_bronnen(doel: Path, config: CheckConfig) -> None:
    """Kopieert de vectorbronnen en compacteert het studiegebied."""
    for naam in _vectorbronnen(config):
        shutil.copy2(BRON_GIS / naam, doel / naam)

    gebied = _studiegebiednaam(config)
    uit = doel / gebied
    uit.unlink(missing_ok=True)
    verbinding = sqlite3.connect(f"file:{BRON_GIS / gebied}?mode=ro", uri=True)
    try:
        verbinding.execute("vacuum into ?", (str(uit),))
    finally:
        verbinding.close()


def _studiegebiednaam(config: CheckConfig) -> str:
    """Het bestand dat `[bronnen] studiegebied` als bereik aanwijst."""
    naam = config.bronnen.studiegebied
    if not naam:
        raise SystemExit("`[bronnen] studiegebied` staat niet in de meegeleverde configuratie.")
    return naam


def _schrijf_shacl(doel: Path, voorbeeld: GwswDataset, config: CheckConfig) -> tuple[int, int]:
    """Filtert de drie SHACL-rapporten op wat in het voorbeeld terechtkomt.

    Geeft (behouden, weggelaten) regels terug. De join is die van de pijplijn zelf:
    `bouw_nulbevindingen` op het geschreven voorbeeld zegt welke focusnode op een knoop
    of streng uitkomt. Wat daar niet op uitkomt gaat eruit, met een uitzondering voor
    `CfkTypes_typ`: die regels noemen een te globale klasse in plaats van een object en
    dragen de typeringspoort, en zonder hen zou het voorbeeld die poort missen.
    """
    paden = sorted(BRON_SHACL.glob("*.csv"))
    nulmeting = laad_nulmeting(paden, config.nulmeting.vereiste_cfk)
    behouden_sleutels = {
        (bevinding.vorm, bevinding.focus_node)
        for bevinding in bouw_nulbevindingen(
            nulmeting, voorbeeld, config.rapport.systemisch_drempel
        )
        if bevinding.herleid or bevinding.vorm == VORM_TE_GLOBAAL
    }

    behouden = weggelaten = 0
    for pad in paden:
        rijen = _lees_csv(pad)
        kop = next(
            index for index, rij in enumerate(rijen) if rij and rij[0].strip() == KOLOMMEN[0]
        )
        gekozen = []
        for rij in rijen[kop + 1 :]:
            if not rij or not any(rij):
                continue
            # Een rij met minder dan twee velden draagt geen vorm en kan dus nooit
            # behouden worden; `shaclrapport._meldingen` vult zo'n rij op met lege
            # velden en laat hem staan, dus hij mag hier niet omvallen maar wel weg.
            sleutel = (rij[1].strip(), rij[0].strip()) if len(rij) > 1 else None
            if sleutel is not None and sleutel in behouden_sleutels:
                gekozen.append(rij)
            else:
                weggelaten += 1
        behouden += len(gekozen)
        _schrijf_csv(doel / pad.name, rijen[: kop + 1] + gekozen)
    return behouden, weggelaten


def _lees_csv(pad: Path) -> list[list[str]]:
    """Een SHACL-rapport als rijen."""
    with pad.open(encoding=ENCODING, newline="") as bestand:
        return list(csv.reader(bestand, delimiter=DELIMITER))


def _schrijf_csv(pad: Path, rijen: list[list[str]]) -> None:
    """Schrijft de rijen terug in het formaat dat `shaclrapport` leest."""
    with pad.open("w", encoding=ENCODING, newline="") as bestand:
        csv.writer(bestand, delimiter=DELIMITER, lineterminator="\r\n").writerows(rijen)


def _megabyte(pad: Path) -> str:
    """De omvang van een bestand in MB, met een Nederlandse decimale komma."""
    return f"{pad.stat().st_size / 1_000_000:.2f}".replace(".", ",")


def _schrijf_readme(doel: Path, feiten: dict[str, object]) -> None:
    """Schrijft de herkomst, de licenties en het commando naast het voorbeeld."""
    omvang = "\n".join(
        f"| `{pad.name}` | {_megabyte(pad)} MB |"
        for pad in sorted(doel.iterdir())
        if pad.name != "README.md"
    )
    (doel / "README.md").write_text(
        f"""# Voorbeeld Koekangerveld

Een compleet, klein voorbeeld om `nlriochecker toets` op te draaien: de buurt
Koekangerveld in de gemeente De Wolden, met de bijbehorende SHACL-nulmeting en externe
bronnen. GEGENEREERD met `scripts/maak_voorbeeld.py`; bewerk deze bestanden niet met de
hand, maar draai de generator opnieuw.

## Draaien

```
nlriochecker toets \\
  --dataset voorbeelden/koekangerveld/{DOEL_TTL} \\
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_Hyd.csv \\
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_MdsPlan.csv \\
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_MdsProj.csv \\
  --studiegebied voorbeelden/koekangerveld/{feiten["gebied"]} \\
  --bronnen voorbeelden/koekangerveld \\
  --output uitvoer/voorbeeld
```

Er is geen `--projectconfig` bij: het voorbeeld draait op de meegeleverde
standaardconfiguratie (`src/nlriochecker/checks.toml`). Wil je zien hoe een eigen
projectconfiguratie eruitziet, kijk dan in `configs/dewoldenhoogeveen.toml`.

## Wat erin zit

- De **analyseset** van de buurt zoals `toets --studiegebied` hem afbakent: kern
  ({feiten["kern"]} objecten) plus contextschil ({feiten["schil"]}), van
  {feiten["export"]} objecten in de volledige export.
- Hun **onderdelen, orientaties en stelsels**: samen {feiten["triples"]} triples over
  {feiten["subjecten"]} subjecten.
- De **SHACL-nulmeting** op alle drie de conformiteitsklassen, teruggebracht tot de
  {feiten["shacl"]} regels die op een object in dit voorbeeld uitkomen, plus de
  `CfkTypes_typ`-regels van de typeringspoort.
- De **externe bronnen** BGT, BAG, NWB en TOP10NL, bit voor bit zoals ze voor de hele
  buurt aangeleverd zijn; de EXT-checks geven hier dus dezelfde uitslag als op de
  volledige export.

| Bestand | Omvang |
|---|---|
{omvang}

## Wat er niet in zit

- **Het hoogteraster (AHN).** Dat extract is 12 MB en past niet in een repository. HGT-001
  tot en met HGT-003 melden daardoor zelf dat ze niets konden toetsen; het rapport zegt
  dat in de verantwoording.
- **De SHACL-regels zonder herleidbaar object.** Een overtreding waarvan de focusnode
  geen put of streng is -- een gemeentebreed stelsel -- gaat niet mee. Ze zouden in het
  rapport blijven staan zonder object en zonder gebied, en horen bij de volledige export
  en niet bij deze buurt.
- **De rest van de gemeente.** Een check die over de hele export gaat in plaats van over
  losse objecten (ADM-002 op dubbele identificaties, ATTR-014 en ATTR-015) ziet hier
  alleen deze buurt en kan dus minder vinden dan op de volledige export.

## Herkomst en licenties

- **`{DOEL_TTL}`** -- uitsnede uit de OroX-export van de gemeente De Wolden (BrutIS).
  Met toestemming van de gemeente gepubliceerd; besluit van de auteur, 29-08-2026.
- **`gwsw_shacl_report_*.csv`** -- de GWSW-nulmeting op diezelfde export, gedraaid via
  [apps.gwsw.nl](https://apps.gwsw.nl/item_validate_shacl). Zelfde herkomst en
  toestemming.
- **`BGT.gpkg`** en **`bag_pand_koekangerveld.gpkg`** -- BGT en BAG via PDOK, CC0.
- **`nwb_wegvakken_koekangerveld.gpkg`** -- Nationaal Wegenbestand (Rijkswaterstaat), CC0.
- **`top10nl_plaats_vlak_koekangerveld.gpkg`** -- TOP10NL (Kadaster), CC-BY 4.0.
- **`{feiten["gebied"]}`** -- CBS-buurtkaart, CC-BY 4.0 (CBS).

De GWSW-ontologie waarmee `toets` de klassenhierarchie leest zit niet in deze map: zij
reist als package-resource mee met `gwsw-orox-helpers` en is CC0.
""",
        encoding="utf-8",
    )


def main() -> None:
    """Bouwt de voorbeeldmap opnieuw op."""
    DOEL.mkdir(parents=True, exist_ok=True)
    config = load_check_config()

    gebied = _studiegebiednaam(config)
    begin = time.monotonic()
    dataset, cache = laad_met_cache(BRON_TTL, None, fallback_encoding=FALLBACK_ENCODING)
    area = load_study_area(BRON_GIS / gebied)
    analyseset = bouw_analyseset(dataset, area, config)
    print(
        f"analyseset: {len(analyseset.kern)} kern, {len(analyseset.schil)} schil, "
        f"van {analyseset.volledig_aantal} ({cache.bron}, {time.monotonic() - begin:.1f} s)",
        flush=True,
    )

    triples = _lees_export(BRON_TTL)
    gekozen = _subjectverzameling(triples, dataset, analyseset)
    aantal, subjecten = _schrijf_ttl(triples, gekozen, DOEL / DOEL_TTL, {s.value for s in triples})
    print(f"TTL: {aantal} triples over {subjecten} subjecten", flush=True)

    _kopieer_bronnen(DOEL, config)

    voorbeeld = load_dataset(DOEL / DOEL_TTL, None)
    print(f"voorbeeld: {len(voorbeeld.nodes)} knopen, {len(voorbeeld.conduits)} strengen")
    behouden, weggelaten = _schrijf_shacl(DOEL, voorbeeld, config)
    print(f"SHACL: {behouden} regels behouden, {weggelaten} weggelaten", flush=True)

    _schrijf_readme(
        DOEL,
        {
            "kern": len(analyseset.kern),
            "schil": len(analyseset.schil),
            "export": analyseset.volledig_aantal,
            "triples": aantal,
            "subjecten": subjecten,
            "shacl": behouden,
            "gebied": gebied,
        },
    )
    totaal = sum(pad.stat().st_size for pad in DOEL.iterdir())
    print(f"{DOEL.relative_to(WORTEL)}: {totaal / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
