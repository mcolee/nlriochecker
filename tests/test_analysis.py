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


def _met_stelsel(doel: Path, stelsel: str = "") -> Path:
    """Een fixture-TTL met de stelselhierarchie, en desgevraagd een stelselinstantie.

    `Rioolstelsel` staat onder `Stelsel` en is dus knoop noch streng: `of_class()`
    geeft er `[]` op terug. Het verschil dat ertoe doet is of de graaf er instanties
    van draagt -- dan is die nul een gat in de beoordeling en geen echte nul.
    """
    bron = (TTL_DIR / "schoon.ttl").read_text(encoding="utf-8")
    # De keten zoals de ontologie hem legt: Vuilwaterstelsel onder
    # VrijvervalRioolstelsel onder Rioolstelsel onder Stelsel.
    bron += (
        "\ngwsw:VrijvervalRioolstelsel rdfs:subClassOf gwsw:Rioolstelsel ."
        "\ngwsw:Vuilwaterstelsel rdfs:subClassOf gwsw:VrijvervalRioolstelsel ."
        "\ngwsw:Rioolstelsel rdfs:subClassOf gwsw:Stelsel .\n"
    )
    if stelsel:
        bron += f"\n:Stelsel1 rdf:type gwsw:{stelsel} .\n"
    doel.write_text(bron, encoding="utf-8")
    return doel


def test_typeringspoort_noemt_een_stelselklasse_zonder_objecten_onbeoordeelbaar(
    mini_mdsplan_shacl: Path, tmp_path: Path
) -> None:
    """Het werkelijke geval, en niet het hypothetische.

    Over de drie aangeleverde SHACL-rapporten samen noemt `CfkTypes_typ` drie klassen;
    `Rioolstelsel` en `MechanischRioolstelsel` zijn er twee van. Die staan onder
    `Stelsel` en komen dus in het domeinmodel niet voor, dus `of_class()` geeft er stil
    `[]` op terug. Zonder deze tak scoort de poort er nul te globale objecten voor
    zonder een woord, terwijl de dataset de stelsels wel bevat.
    """
    dataset = load_dataset(_met_stelsel(tmp_path / "met_stelsel.ttl", "Vuilwaterstelsel"))

    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl), dataset).typing_gate

    assert dataset.of_class("Rioolstelsel") == []
    assert "Rioolstelsel" in poort.unassessable_classes
    # De klasse die er wel is blijft gewoon gewogen, en de score blijft bestaan.
    assert "Overstortput" not in poort.unassessable_classes
    assert poort.resolved is True and poort.score is not None


def test_een_klasse_die_niet_voorkomt_is_geen_onbeoordeelbare_klasse(
    mini_mdsplan_shacl: Path, tmp_path: Path
) -> None:
    """De tegenproef: nul objecten bij nul instanties is een echte nul.

    Dezelfde dataset zonder de stelselinstantie. Zou de tak alleen naar `of_class()`
    kijken, dan zou elke te globale klasse die in deze dataset niet voorkomt als
    onbeoordeelbaar in het rapport komen, en dat leest als een gat dat er niet is.
    """
    dataset = load_dataset(_met_stelsel(tmp_path / "zonder_stelsel.ttl"))

    poort = analyze_report(lees_shacl_rapport(mini_mdsplan_shacl), dataset).typing_gate

    assert dataset.of_class("Rioolstelsel") == []
    assert poort.unassessable_classes == []


def test_analyse_van_de_hele_nulmeting(shacl_drieluik: list[Path]) -> None:
    analyse = analyze(laad_nulmeting(shacl_drieluik, VEREIST))

    assert sorted(analyse.per_cfk) == ["Hyd", "MdsPlan", "MdsProj"]
    assert analyse.total_count == sum(deel.total_count for deel in analyse.per_cfk.values())
