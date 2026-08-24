"""De telling van de klassen waar checks van afhangen, en de nul-waarschuwing (issue #22).

De fixtures worden hier programmatisch geschreven: er zijn veertien klassen in het
spel, en een variant per test (met of zonder een enkele klasse) is als losse
TTL-bestanden niet te overzien. Elke klasse krijgt precies een instantie, met de
inline klassenhierarchie die de lader nodig heeft om knopen en strengen aan hun
GWSW-type te herkennen -- geen geometrie, want `of_class` en `subjects_of_class`
tellen op type, niet op punt of lijn.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from nlriochecker.checkconfig import load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.uitvoer.bevindingen import _omvang_section, meldingen_json
from nlriochecker.uitvoer.melding import (
    BRON_DATASET,
    CHECK_HULPSTUKKOPPELING,
    bouw_meldingen,
)
from nlriochecker.uitvoer.omvang import (
    eindpunttelling,
    klassen_op_nul,
    klassentelling,
)

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"

# De veertien klassen uit de zes rollen die checks.toml als afhankelijkheid noemt.
ALLE_KLASSEN = {
    "Overnamepunt",
    "Gemaal",
    "Pompunit",
    "Lozingspunt",
    "UitlaatPunt",
    "Lozingsput",
    "Uitlaatconstructie",
    "Bergbezinkbassin",
    "Bergingsbassin",
    "Bezinkbassin",
    "Overstortdrempel",
    "Infiltratieriool",
    "MechanischeRioolleiding",
    "MechanischeTransportleiding",
}

# Klassen die het GWSW op de orientatie van een knoop legt (subklassen van Aansluitpunt).
_ORIENTATIE_KLASSEN = {"Overnamepunt", "Lozingspunt", "UitlaatPunt"}
# Klassen die als streng in de graaf staan.
_CONDUIT_KLASSEN = {"Infiltratieriool", "MechanischeRioolleiding", "MechanischeTransportleiding"}
# Onderdelen zonder eigen geometrie, alleen via subjects_of_class te vinden.
_ONDERDEEL_KLASSEN = {"Overstortdrempel"}

_HIERARCHIE = """
gwsw:Putorientatie rdfs:subClassOf gwsw:Knooppunt .
gwsw:Bouwwerkorientatie rdfs:subClassOf gwsw:Knooppunt .
gwsw:Aansluitpunt rdfs:subClassOf gwsw:Knooppunt .
gwsw:Overnamepunt rdfs:subClassOf gwsw:Aansluitpunt .
gwsw:Lozingspunt rdfs:subClassOf gwsw:Aansluitpunt .
gwsw:UitlaatPunt rdfs:subClassOf gwsw:Aansluitpunt .
gwsw:Leidingorientatie rdfs:subClassOf gwsw:Verbinding .
"""


def _instantie(klasse: str) -> str:
    """De TTL voor een enkele instantie van deze klasse."""
    if klasse in _ONDERDEEL_KLASSEN:
        return f":{klasse} rdf:type gwsw:{klasse} ."
    if klasse in _ORIENTATIE_KLASSEN:
        return f":{klasse} gwsw:hasAspect :{klasse}_ori .\n:{klasse}_ori rdf:type gwsw:{klasse} ."
    if klasse in _CONDUIT_KLASSEN:
        return (
            f":{klasse} rdf:type gwsw:{klasse} ; gwsw:hasAspect :{klasse}_ori .\n"
            f":{klasse}_ori rdf:type gwsw:Leidingorientatie ."
        )
    return (
        f":{klasse} rdf:type gwsw:{klasse} ; gwsw:hasAspect :{klasse}_ori .\n"
        f":{klasse}_ori rdf:type gwsw:Putorientatie ."
    )


def _maak_ttl(klassen: set[str]) -> str:
    """Een OroX-fragment met precies deze klassen, elk een keer."""
    prefixes = (
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix gwsw: <http://data.gwsw.nl/1.6/totaal/> .\n"
        "@prefix : <http://example.org/toets#> .\n"
    )
    lichamen = "\n".join(_instantie(klasse) for klasse in sorted(klassen))
    return f"{prefixes}{_HIERARCHIE}\n{lichamen}\n"


def _run(tmp_path: Path, weglaten: set[str]) -> CheckRun:
    """Een run over een fixture met alle klassen behalve de weggelaten."""
    pad = tmp_path / "klassen.ttl"
    pad.write_text(_maak_ttl(ALLE_KLASSEN - weglaten), encoding="utf-8")
    dataset = load_dataset(pad)
    config = load_check_config()
    return CheckRun(
        dataset=dataset,
        outcomes=[],
        typing_gate_applied=False,
        config=config,
        context=CheckContext(dataset=dataset, config=config),
    )


class TestKlassenOpNul:
    def test_alle_klassen_aanwezig_geeft_geen_enkele(self, tmp_path: Path) -> None:
        assert klassen_op_nul(_run(tmp_path, set())) == []

    def test_een_leeg_afvoereindpunt_staat_er_per_klasse_in(self, tmp_path: Path) -> None:
        op_nul = {signaal.label for signaal in klassen_op_nul(_run(tmp_path, {"Overnamepunt"}))}
        assert op_nul == {"Overnamepunt"}

    def test_een_ongebruikte_alternatieve_schrijfwijze_geeft_geen_signaal(
        self, tmp_path: Path
    ) -> None:
        # lozingseindpunt heeft vier klassen; ontbreekt er een terwijl de rol als
        # geheel gevuld is, dan is dat geen gebrek maar een andere schrijfwijze.
        assert klassen_op_nul(_run(tmp_path, {"Lozingspunt"})) == []

    def test_een_hele_lege_rol_geeft_een_signaal_op_rolniveau(self, tmp_path: Path) -> None:
        leeg = {"Lozingspunt", "UitlaatPunt", "Lozingsput", "Uitlaatconstructie"}
        op_nul = {signaal.label for signaal in klassen_op_nul(_run(tmp_path, leeg))}
        assert op_nul == {"lozingseindpunt"}


class TestSignaalMelding:
    def test_fixture_zonder_gemaal_geeft_precies_een_waarschuwing(self, tmp_path: Path) -> None:
        meldingen = bouw_meldingen(_run(tmp_path, {"Gemaal"}), date(2026, 8, 23))
        signaal = [melding for melding in meldingen if melding.bron == BRON_DATASET]
        assert len(signaal) == 1
        assert signaal[0].object_label == "Gemaal"
        assert signaal[0].ernst == "W"
        assert signaal[0].systemisch is True

    def test_fixture_met_gemaal_geeft_geen_waarschuwing(self, tmp_path: Path) -> None:
        meldingen = bouw_meldingen(_run(tmp_path, set()), date(2026, 8, 23))
        assert [melding for melding in meldingen if melding.bron == BRON_DATASET] == []

    def test_de_signaalmelding_wijst_geen_object_aan(self, tmp_path: Path) -> None:
        meldingen = bouw_meldingen(_run(tmp_path, {"Gemaal"}), date(2026, 8, 23))
        signaal = next(melding for melding in meldingen if melding.bron == BRON_DATASET)
        assert signaal.object_uri == ""
        assert signaal.foutlocatie is None

    def test_de_json_draagt_de_dataset_bron(self, tmp_path: Path) -> None:
        meldingen = bouw_meldingen(_run(tmp_path, {"Gemaal"}), date(2026, 8, 23))
        assert "dataset" in {rij["bron"] for rij in meldingen_json(meldingen)}


class TestEindpunttelling:
    def test_toont_elke_afvoereindpuntklasse_met_haar_aantal(self, tmp_path: Path) -> None:
        tabel = eindpunttelling(_run(tmp_path, {"Overnamepunt"}))
        rijen = dict(zip(tabel["Klasse"], tabel["Aantal"], strict=True))
        assert rijen == {"Overnamepunt": 0, "Gemaal": 1, "Pompunit": 1}


class TestKlassentelling:
    def test_telt_de_overstortdrempel_zonder_geometrie(self, tmp_path: Path) -> None:
        # De drempel is een onderdeel zonder punt of lijn; of_class zou hem missen,
        # subjects_of_class vindt hem -- zoals NET-007 hem leest.
        tabel = klassentelling(_run(tmp_path, set()))
        rijen = dict(zip(tabel["Rol"], tabel["Aantal"], strict=True))
        assert rijen["overstortdrempel"] == 1

    def test_telt_een_rol_over_haar_klassen(self, tmp_path: Path) -> None:
        tabel = klassentelling(_run(tmp_path, set()))
        rijen = dict(zip(tabel["Rol"], tabel["Aantal"], strict=True))
        # afvoereindpunt telt Overnamepunt + Gemaal + Pompunit.
        assert rijen["afvoereindpunt"] == 3


class TestOmvangSectie:
    def test_toont_de_rollentelling(self, tmp_path: Path) -> None:
        tekst = "\n".join(_omvang_section(_run(tmp_path, set())))
        assert "afvoereindpunt" in tekst

    def test_toont_de_afvoereindpunten_per_klasse(self, tmp_path: Path) -> None:
        tekst = "\n".join(_omvang_section(_run(tmp_path, {"Overnamepunt"})))
        assert "Afvoereindpunten per klasse" in tekst
        assert "Overnamepunt" in tekst

    def test_zonder_lege_klasse_geen_nul_notitie(self, tmp_path: Path) -> None:
        tekst = "\n".join(_omvang_section(_run(tmp_path, set())))
        assert "Nul waar een check op leunt" not in tekst

    def test_nul_notitie_noemt_de_lege_klasse(self, tmp_path: Path) -> None:
        tekst = "\n".join(_omvang_section(_run(tmp_path, {"Gemaal"})))
        assert "Nul waar een check op leunt" in tekst
        assert "Gemaal" in tekst


class TestZonderLocatie:
    def test_datasetsignaal_telt_niet_als_melding_zonder_plek(self) -> None:
        # Een datasetsignaal hoort niet in de "geen plek op de kaart"-telling: het is geen
        # bevinding die niet te plaatsen viel, maar een signaal dat de omvangsectie al noemt.
        from helpers_melding import melding
        from nlriochecker.uitvoer.bevindingen import _zonder_locatie

        signaal = melding(bron="dataset", check_id="SIG-nulklasse", object_uri="", foutlocatie=None)
        assert _zonder_locatie([signaal]) == []

    def test_een_echte_objectloze_melding_telt_nog_wel(self) -> None:
        from helpers_melding import melding
        from nlriochecker.uitvoer.bevindingen import _zonder_locatie

        onherleid = melding(
            bron="nulmeting", check_id="NULMETING-CfkTypes_typ", object_uri="", foutlocatie=None
        )
        regels = _zonder_locatie([onherleid])
        assert regels and "geen plek op de kaart" in regels[0]


class TestKoppelingsherstel:
    """Het herstel van de fantoomkoppeling is een datasetsignaal, geen stille reparatie."""

    def _run(self) -> CheckRun:
        config = load_check_config()
        config.drempels.rd_y_min = 0.0
        dataset = load_dataset(TTL_DIR / "dataset_fantoomkoppeling.ttl")
        return run_checks(CheckContext(dataset=dataset, config=config), ["TOP-001"])

    def test_herstelde_koppelingen_geven_een_systemische_waarschuwing(self) -> None:
        meldingen = bouw_meldingen(self._run(), date(2026, 8, 24))
        signaal = [m for m in meldingen if m.check_id == CHECK_HULPSTUKKOPPELING]

        assert len(signaal) == 1
        assert signaal[0].bron == BRON_DATASET
        assert signaal[0].ernst == "W" and signaal[0].systemisch is True
        assert signaal[0].object_uri == "" and signaal[0].foutlocatie is None
        assert signaal[0].waarde == "1"
        assert "1 leidingeind" in signaal[0].boodschap and "1 hulpstuk" in signaal[0].boodschap

    def test_het_rapport_noemt_het_herstel(self) -> None:
        tekst = "\n".join(_omvang_section(self._run()))
        assert "Herstelde hulpstukkoppelingen" in tekst
