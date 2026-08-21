"""Tests voor de aggregaties en de typeringspoort op SHACL-basis."""

from __future__ import annotations

from pathlib import Path

import pytest

from nlriochecker.analysis import analyze, analyze_report
from nlriochecker.dataset import load_dataset
from nlriochecker.errors import DatasetError
from nlriochecker.meting import laad_nulmeting
from nlriochecker.shaclrapport import lees_shacl_rapport

VEREIST = ["Hyd", "MdsPlan", "MdsProj"]
TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"


def test_totalen_en_ernst(mini_hyd_shacl: Path) -> None:
    analyse = analyze_report(lees_shacl_rapport(mini_hyd_shacl))

    assert analyse.total_count == len(analyse.report.findings)
    assert analyse.error_count + analyse.warning_count == analyse.total_count
    # De ernst komt uit de nulmeting zelf; het oude formaat kende die niet.
    assert analyse.error_count > 0


def test_aggregatie_per_vorm(mini_hyd_shacl: Path) -> None:
    per_vorm = analyze_report(lees_shacl_rapport(mini_hyd_shacl)).by_shape

    assert list(per_vorm.columns) == ["Source", "Meldingen", "Fouten", "Waarschuwingen"]
    assert int(per_vorm["Meldingen"].sum()) == len(lees_shacl_rapport(mini_hyd_shacl).findings)
    assert list(per_vorm["Meldingen"]) == sorted(per_vorm["Meldingen"], reverse=True)


def test_typeringspoort_zonder_dataset(mini_mdsplan_shacl: Path) -> None:
    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl)).typing_gate

    assert poort.classes == ["MechanischRioolstelsel", "Overstortput", "Rioolstelsel"]
    assert poort.resolved is False
    # Zonder dataset zijn de objecten niet te bepalen; dan ook geen score verzinnen.
    assert poort.score is None
    assert poort.objects == []


def test_typeringspoort_met_dataset(mini_mdsplan_shacl: Path, tmp_path: Path) -> None:
    bron = (TTL_DIR / "schoon.ttl").read_text(encoding="utf-8")
    # Geef put B het te globale type Overstortput uit het SHACL-rapport.
    bron += "\n:PutB rdf:type gwsw:Overstortput .\ngwsw:Overstortput rdfs:subClassOf gwsw:Put .\n"
    pad = tmp_path / "met_overstortput.ttl"
    pad.write_text(bron, encoding="utf-8")
    dataset = load_dataset(pad)

    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl), dataset).typing_gate

    assert poort.resolved is True
    assert [uri.rsplit("#", 1)[-1] for uri in poort.objects] == ["PutB"]
    assert poort.total_objects == len(dataset.nodes) + len(dataset.conduits)
    assert poort.score is not None


TE_GLOBALE_VERBINDINGSKLASSE = (
    "Afvoerrelatie;CfkTypes_typ;;Violation;"
    "Type individu wijkt af (is abstract, te globaal binnen CFK);b178037;;"
)


def meting_met_verbindingsklasse(bron: Path, doel: Path) -> Path:
    """Kopieert een SHACL-rapport met een te globale verbindingsklasse erbij."""
    regels = bron.read_text(encoding="utf-8").rstrip("\n").splitlines()
    regels.append(TE_GLOBALE_VERBINDINGSKLASSE)
    doel.write_text("\n".join(regels) + "\n", encoding="utf-8")
    return doel


def dataset_met_verbindingsklasse(doel: Path) -> Path:
    """Een fixture-TTL waarin Afvoerrelatie als verbindingsklasse bekend is."""
    bron = (TTL_DIR / "schoon.ttl").read_text(encoding="utf-8")
    bron += "\ngwsw:Afvoerrelatie rdfs:subClassOf gwsw:Verbinding .\n"
    doel.write_text(bron, encoding="utf-8")
    return doel


def test_typeringspoort_noemt_een_verbindingsklasse_onbeoordeelbaar(
    mini_mdsplan_shacl: Path, tmp_path: Path
) -> None:
    """Een te globale verbindingsklasse laat de meting niet vallen.

    De klassenlijst komt hier uit de SHACL-meting en niet uit de configuratie: een
    verbindingsklasse is dan een meetuitkomst, geen vergissing van de gebruiker.
    `of_class()` zou hem weigeren, dus de poort vraagt vooraf en zet hem als
    onbeoordeelbaar opzij -- de andere klassen worden gewoon gewogen.
    """
    rapport = meting_met_verbindingsklasse(mini_mdsplan_shacl, tmp_path / "verbinding.csv")
    dataset = load_dataset(dataset_met_verbindingsklasse(tmp_path / "verbinding.ttl"))

    poort = analyze_report(lees_shacl_rapport(rapport), dataset).typing_gate

    assert "Afvoerrelatie" in poort.classes
    assert poort.unassessable_classes == ["Afvoerrelatie"]
    assert poort.resolved is True
    assert poort.score is not None
    # En dit is waar het om gaat: langs de configweg valt dezelfde klasse wel om.
    with pytest.raises(DatasetError):
        dataset.of_class("Afvoerrelatie")


def test_analyse_van_de_hele_nulmeting(shacl_drieluik: list[Path]) -> None:
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))

    assert sorted(analyse.per_cfk) == ["Hyd", "MdsPlan", "MdsProj"]
    assert analyse.total_count == sum(deel.total_count for deel in analyse.per_cfk.values())
