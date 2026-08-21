#!/usr/bin/env python
"""Schrijft `data/gwsw-vocabulaire-index.json` uit de GWSW-totaalontologie.

De vocabulairetest (`tests/test_gwsw_vocabulaire.py`) moet van elke GWSW-naam weten
welke `rdf:type`s de ontologie eraan geeft -- dat is tegelijk het antwoord op "bestaat
dit begrip" en op "zit het in de juiste collectie". Daarnaast toetst hij de andere kant
op -- dekken onze symbolentabellen de klassen die GWSW onder `Put`, `Bouwwerk`,
`Hulpstuk` en `Knooppunt` hangt -- en daarvoor zijn de directe `rdfs:subClassOf`-kanten
nodig. De ontologie zelf staat buiten versiebeheer omdat ze 2,6 MB weegt, en zonder
haar sloeg die test op de CI-runner vrijwel volledig over. Deze afgeleide index is
klein genoeg om wel getrackt te worden en draagt precies die twee gegevens, niets meer.

De ontologie is CC0 (https://stichtingrioned.github.io/GWSW_Ontologie_RDF/), dus aan
het opnemen van een afgeleide staat niets in de weg. De afweging is bestandsgrootte en
onderhoud, geen licentie; zie BO-32 in `docs/beslislog.md`.

Upgraden blijft handwerk van de auteur, zoals `CLAUDE.md` voorschrijft: hij zet nieuwe
ontologiebestanden in `data/gwsw_ontologieen/` en draait dit script. Er wordt met opzet
niets bij data.gwsw.nl opgehaald. Vergeet hij het script, dan valt
`test_index_volgt_de_ontologie` -- maar alleen op een machine die de ontologie heeft.

Gebruik:  uv run python scripts/maak_gwsw_index.py
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from nlriochecker.dataset import GWSW

WORTEL = Path(__file__).resolve().parents[1]
ONTOLOGIE = WORTEL / "data" / "gwsw_ontologieen" / "Ontologie_GWSW_Totaal.ttl"
DOEL = WORTEL / "data" / "gwsw-vocabulaire-index.json"


def termen_uit_graaf(graaf: Graph) -> dict[str, list[str]]:
    """Per GWSW-subject de `rdf:type`s die de ontologie eraan geeft.

    Een type binnen de GWSW-naamruimte wordt tot zijn korte naam gekort -- dat is de
    collectie waarin een domeinlijstwaarde zit (`VormLeidingColl`). De rest blijft een
    volledige URI (`owl:Class`), zodat er geen afkortingstabel bij hoort die de lezer
    en de schrijver uit elkaar kan laten lopen.
    """
    termen: dict[str, set[str]] = {}
    for subject, _, soort in graaf.triples((None, RDF.type, None)):
        if not isinstance(subject, URIRef) or not str(subject).startswith(GWSW):
            continue
        termen.setdefault(str(subject).removeprefix(GWSW), set()).add(str(soort).removeprefix(GWSW))
    return {naam: sorted(soorten) for naam, soorten in sorted(termen.items())}


def ouders_uit_graaf(graaf: Graph) -> dict[str, list[str]]:
    """Per GWSW-klasse haar directe GWSW-superklassen.

    Alleen de *directe* kanten, niet de afsluiting: die is uit deze kanten te bouwen en
    zou het bestand een orde van grootte groter maken. Kanten naar buiten de
    GWSW-naamruimte (`owl:Thing`, SKOS) blijven weg -- de vraag die de test hiermee
    beantwoordt is welke GWSW-klassen onder een GWSW-wortel hangen.
    """
    ouders: dict[str, set[str]] = {}
    for kind, ouder in graaf.subject_objects(RDFS.subClassOf):
        if not isinstance(kind, URIRef) or not isinstance(ouder, URIRef):
            continue
        if not str(kind).startswith(GWSW) or not str(ouder).startswith(GWSW):
            continue
        ouders.setdefault(str(kind).removeprefix(GWSW), set()).add(str(ouder).removeprefix(GWSW))
    return {naam: sorted(soorten) for naam, soorten in sorted(ouders.items())}


def versie_uit_graaf(graaf: Graph) -> str:
    """De `owl:versionInfo` van de ontologie, letterlijk overgenomen.

    Letterlijk, en niet uitgekleed tot "1.6": het nummer hoort in de ontologie thuis
    en `CLAUDE.md` is de enige plek waar het als projectafspraak staat. De regel reist
    hier mee als bewijs bij welke ontologie deze index hoort, niet als tweede
    gezaghebbende bron. Wie hem hier bijwerkt zonder de ontologie te vervangen, krijgt
    `test_index_volgt_de_ontologie` rood.
    """
    for _, _, waarde in graaf.triples((None, OWL.versionInfo, None)):
        return str(waarde)
    raise SystemExit(f"{ONTOLOGIE}: geen owl:versionInfo gevonden.")


def documenttekst(ttl: Path) -> str:
    """De volledige inhoud van het indexbestand voor deze ontologie.

    Handgezet in plaats van `json.dumps(indent=…)`, omdat een regel per term het
    bestand diffbaar houdt: een nieuwe GWSW-versie levert dan een leesbare lijst
    toevoegingen op in plaats van een blok van tienduizend regels.
    """
    graaf = Graph()
    graaf.parse(ttl, format="turtle")

    kop = {
        "bron": ttl.relative_to(WORTEL).as_posix(),
        "gwsw_versie": versie_uit_graaf(graaf),
        "script": Path(__file__).relative_to(WORTEL).as_posix(),
    }
    regels = ["{"]
    regels += [f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}," for k, v in kop.items()]
    for blok, inhoud in (
        ("termen", termen_uit_graaf(graaf)),
        ("subklasse_van", ouders_uit_graaf(graaf)),
    ):
        komma_blok = "," if blok != "subklasse_van" else ""
        regels.append(f'  "{blok}": {{')
        namen = list(inhoud)
        for nummer, naam in enumerate(namen, start=1):
            komma = "" if nummer == len(namen) else ","
            sleutel = json.dumps(naam, ensure_ascii=False)
            waarden = json.dumps(inhoud[naam], ensure_ascii=False)
            regels.append(f"    {sleutel}: {waarden}{komma}")
        regels.append(f"  }}{komma_blok}")
    regels.append("}")
    return "\n".join(regels) + "\n"


def main() -> None:
    """Schrijft de index en meldt hoeveel termen erin staan."""
    if not ONTOLOGIE.exists():
        raise SystemExit(f"{ONTOLOGIE} ontbreekt; zet de GWSW-ontologie in data/.")
    tekst = documenttekst(ONTOLOGIE)
    DOEL.write_text(tekst, encoding="utf-8")
    document = json.loads(tekst)
    print(
        f"{DOEL.relative_to(WORTEL)}: {len(document['termen'])} termen en "
        f"{len(document['subklasse_van'])} subklasserelaties geschreven."
    )


if __name__ == "__main__":
    main()
