"""Gepaarde 1.6/1.7-drifttest: de checks lezen de graaf versie-onafhankelijk (issue #139).

Drie plekken bevroegen de graaf met de 1.6-namespaceconstanten -- `hasConnection`
(`nulbevinding._Joiner`, ADM-008), `hasValue`/`hasReference` en de kenmerkklasse-IRI
(ATTR-014). Op een GWSW-1.7-export (basis `http://data.gwsw.nl/1.7/totaal/`) matchte dat
niets en lazen ze stil nul: ADM-008 gaf een valse melding, ATTR-014 miste haar bevindingen.

Deze test laadt elke fixture **mét de gebundelde ontologie** in twee smaken -- de 1.6-set en
dezelfde fixture met de namespace naar 1.7 omgezet -- en eist per fixture dezelfde
`(check_id, aantal)`. Vandaag rood, na de fix groen; hij blijft na de leeslaagmigratie
(#159, #166) het bewijs dat die niets verschuift.

De 1.7-variant wordt hier ter plekke gemaakt door de namespace `1.6/totaal` -> `1.7/totaal`
om te zetten: dat is exact het enige verschil tussen `tests/fixtures/ttl` en de gegenereerde
`tests/fixtures/ttl17` (byte-voor-byte geverifieerd over de 156 gepaarde bestanden). Zo dekt
de test ook de graafrakende fixtures (attr014, net007) die de repo alleen in 1.6 draagt, en
zijn er echt 195 paren -- meer dan de 156 bestanden in `ttl17/`.

`load_dataset` zonder ontologiepad leest de gebundelde ontologie, versie-juist bij de
gedetecteerde basis; dat is precies de standaardweg van `toets` zonder `--ontologie`. De
1.6- en de 1.7-run gebruiken dezelfde config en hetzelfde laadrecept, dus elk verschil in de
uitkomst komt van de namespace -- wat deze test wil vangen. De klok hoeft niet gepind: een
datumcheck geeft op beide versies dezelfde uitkomst.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from gwsw_orox_helpers.dataset import load_dataset

from nlriochecker.checkconfig import FALLBACK_ENCODING, load_check_config
from nlriochecker.checks import CheckContext, run_checks

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

# De prefixes van de fixtures die de door #139 gerepareerde predicaten werkelijk raken:
# ADM-008/009 (hasConnection) en ATTR-014 (hasValue/hasReference, kenmerkklasse-IRI). De
# rvz- en net007-fixtures lopen de graaf ook af, maar hun uitkomst hangt niet aan een van
# die predicaat-namespaces (ze staan niet in `GEREPAREERD`); ze kostten de lichte set ~26 s
# zonder eigen #139-dekking en draaien daarom alleen nog in de zware set hieronder, die
# onverkort alles toetst (issue #171).
GRAAFRAKEND = ("adm008", "adm009", "attr014")

ALLE = sorted(p.name for p in TTL_DIR.glob("*.ttl"))
LICHT = [naam for naam in ALLE if naam.startswith(GRAAFRAKEND)]

# Twee fixtures verschillen tussen 1.6 en 1.7 om een reden BUITEN issue #139, en buiten
# deze repository: de GWSW-1.7-ontologie herclassificeert `Bergbezinkleiding`. In 1.6 valt
# die klasse in de afsluiting van `VrijvervalRioolleiding`, in 1.7 niet, dus de rol
# `vrijverval`/`leidingen` selecteert er een object minder. Dat verschuift alleen de
# selectie-afhankelijke checks (ATTR-009/018, HGT-*, TOP-009) -- niet de door #139
# gerepareerde plekken (ADM-008, ATTR-014, `nulbevinding`), die aan het predicaat-namespace
# hangen en niet aan de klassenhierarchie. Deze twee staan daarom apart: de gelijkheidstest
# hieronder bewaakt zuiver de namespace-fix, en `test_gerepareerde_checks_...` toont dat de
# fix ook op deze fixtures werkt. Het verschil zelf komt uit de gebundelde ontologie in
# `gwsw-orox-helpers` en is geen bug in deze repo.
ONTOLOGIE_VERSCHIL_16_17 = frozenset({"ext_scenario.ttl", "selectie_rollen.ttl"})

# De door #139 gerepareerde checks: hun uitkomst hangt aan het predicaat-namespace.
GEREPAREERD = ("ADM-008", "ADM-009", "ATTR-014")


def _telling(pad: Path) -> dict[str, int]:
    """De `(check_id -> aantal bevindingen)` van de volledige registry over deze fixture.

    Alleen checks die iets meldden staan erin, net als de gouden ledger: een check zonder
    bevinding draagt geen sleutel, dus een 0 die naar 1 verschuift (of andersom) valt op.
    """
    dataset = load_dataset(pad, fallback_encoding=FALLBACK_ENCODING)
    run = run_checks(CheckContext(dataset=dataset, config=load_check_config()))
    return {outcome.check_id: len(outcome.findings) for outcome in run.outcomes if outcome.findings}


def _als_zeventien(pad: Path, tmp: Path) -> Path:
    """Schrijft de fixture met de namespace naar 1.7 omgezet en geeft het pad terug.

    Byte-niveau, zodat de opzettelijk niet-UTF-8 fixture (`codering_cp850.ttl`) meekomt.
    """
    doel = tmp / pad.name
    doel.write_bytes(pad.read_bytes().replace(b"1.6/totaal", b"1.7/totaal"))
    return doel


def _vergelijk(naam: str, tmp: Path) -> None:
    """Eist dat 1.6 en 1.7 van dezelfde fixture dezelfde bevindingen per check geven."""
    pad = TTL_DIR / naam
    assert _telling(_als_zeventien(pad, tmp)) == _telling(pad)


@pytest.mark.parametrize("naam", LICHT)
def test_graafrakende_fixtures_gelijk_over_16_en_17(naam: str, tmp_path: Path) -> None:
    """De graafrakende fixtures geven op 1.6 en 1.7 dezelfde bevindingen (licht)."""
    _vergelijk(naam, tmp_path)


@pytest.mark.zwaar
@pytest.mark.parametrize("naam", [naam for naam in ALLE if naam not in ONTOLOGIE_VERSCHIL_16_17])
def test_alle_fixtures_gelijk_over_16_en_17(naam: str, tmp_path: Path) -> None:
    """Alle fixtureparen geven op 1.6 en 1.7 dezelfde bevindingen (zwaar).

    Op twee na (`ONTOLOGIE_VERSCHIL_16_17`), waar de ontologie zelf tussen 1.6 en 1.7
    verschilt; die worden hieronder apart getoetst.
    """
    _vergelijk(naam, tmp_path)


def test_joiner_herleidt_via_hasconnection_op_16_en_17(tmp_path: Path) -> None:
    """`_Joiner` herleidt een maaiveldorientatie via hasConnection, versie-onafhankelijk.

    De hasConnection-route van `_Joiner._ouders` loopt over `leeslaag.buren`, die het
    predicaat opzoekt via `termen_voor(dataset.gwsw_versie.basis)` (issue #139/BO-93). De
    fixtureparen hierboven dekken de check-kant (ADM-008 c.s.) via `run_checks`, maar raken
    de nulbevinding-kant niet: die draait op de SHACL-nulmeting, niet op `run_checks`. Deze
    gerichte proef dekt haar rechtstreeks -- een 1.6-namespace-constante zou op een
    1.7-export stil niets vinden en de maaiveldmelding van de put laten vallen. Beide
    schrijfrichtingen van hasConnection doen mee (PutC als subject, PutD als object).
    """
    from nlriochecker.nulbevinding import _Joiner

    bron = TTL_DIR / "nulmeting_join.ttl"
    for pad in (bron, _als_zeventien(bron, tmp_path)):
        dataset = load_dataset(pad, fallback_encoding=FALLBACK_ENCODING)
        joiner = _Joiner(dataset)

        put_c = joiner.herleid("PutC_ori_maa")
        assert put_c in dataset.nodes and dataset.nodes[put_c].label == "C"
        put_d = joiner.herleid("PutD_ori_maa")
        assert put_d in dataset.nodes and dataset.nodes[put_d].label == "D"


@pytest.mark.parametrize("naam", sorted(ONTOLOGIE_VERSCHIL_16_17))
def test_gerepareerde_checks_gelijk_ondanks_ontologieverschil(naam: str, tmp_path: Path) -> None:
    """Op de twee ontologie-verschilfixtures matchen de door #139 gerepareerde checks tóch.

    Deze fixtures verschillen tussen 1.6 en 1.7 in hun `vrijverval`/`leidingen`-selectie
    (`Bergbezinkleiding` is in 1.7 geen `VrijvervalRioolleiding`), dus selectie-afhankelijke
    checks lopen uiteen. De door #139 gerepareerde checks -- die aan het predicaat-namespace
    hangen -- horen wél gelijk te zijn: dit bewijst dat de fix ook hier werkt en dat de
    uitsluiting hierboven geen echte #139-regressie verbergt. En het verschil moet echt
    bestaan, anders hoort de fixture niet in de uitsluiting.
    """
    pad = TTL_DIR / naam
    telling16 = _telling(pad)
    telling17 = _telling(_als_zeventien(pad, tmp_path))
    assert telling16 != telling17
    for check in GEREPAREERD:
        assert telling16.get(check) == telling17.get(check)
