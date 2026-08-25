"""De opbouw van het bevindingenrapport (issue #16).

Vier eisen: de titel noemt het gebied, de aantallen staan bovenaan, de
managementsamenvatting zegt of het gebied voldoet, en het detail staat in twee
herkomstblokken met de fouten voorop.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

from nlriochecker.checkconfig import CheckConfig, load_check_config
from nlriochecker.checks import CheckContext, CheckRun, run_checks
from nlriochecker.dataset import load_dataset
from nlriochecker.meting import Meetbereik, laad_nulmeting
from nlriochecker.nulbevinding import Nulbevinding, bouw_nulbevindingen
from nlriochecker.studiegebied import load_studiegebieden
from nlriochecker.toetsloop import toets_gebieden
from nlriochecker.uitvoer.bevindingen import _telling
from nlriochecker.uitvoer.omvang import omvangtabel
from nlriochecker.uitvoer.samenvatting import KRUISJE, NIET_GEMETEN, VINKJE
from nlriochecker.uitvoer.schrijver import schrijf_uitvoer, schrijf_uitvoer_gebieden

TTL_DIR = Path(__file__).parent / "fixtures" / "ttl"
GIS_DIR = Path(__file__).parent / "fixtures" / "gis"
SHACL_DIR = Path(__file__).parent / "fixtures" / "shacl"
RUNDATUM = date(2026, 8, 19)
CFKS = ["MdsPlan", "MdsProj"]


def _config() -> CheckConfig:
    """De standaardconfig, met het RD-bereik verruimd tot de fixturecoordinaten."""
    config = load_check_config()
    config.drempels.rd_y_min = 0.0
    return config


def _run(bestand: str, *check_ids: str) -> CheckRun:
    """Een run zonder studiegebied."""
    dataset = load_dataset(TTL_DIR / bestand)
    context = CheckContext(dataset=dataset, config=_config())
    return run_checks(context, list(check_ids) or None)


def _met_nulmeting(bestand: str = "nulmeting_join.ttl") -> CheckRun:
    """Een gemeten run: de join-fixture met haar twee CFK-rapporten."""
    config = _config()
    dataset = load_dataset(TTL_DIR / bestand)
    nulmeting = laad_nulmeting(
        [SHACL_DIR / "join_mdsplan.csv", SHACL_DIR / "join_mdsproj.csv"], CFKS, CFKS
    )
    run = run_checks(CheckContext(dataset=dataset, config=config), [])
    return replace(
        run,
        nulbevindingen=tuple(
            bouw_nulbevindingen(nulmeting, dataset, config.rapport.systemisch_drempel)
        ),
        meetbereik=Meetbereik.van(CFKS, CFKS),
        typing_gate_applied=True,
    )


def _rapport(run: CheckRun, tmp_path: Path) -> str:
    """Schrijft de uitvoer en geeft het Markdown-rapport terug."""
    uitvoer = schrijf_uitvoer(run, tmp_path, RUNDATUM, met_geopackage=False)
    return uitvoer.markdown.read_text(encoding="utf-8")


class TestTitel:
    def test_zonder_studiegebied_noemt_de_titel_de_dataset(self, tmp_path: Path) -> None:
        tekst = _rapport(_run("schoon.ttl"), tmp_path)

        assert tekst.startswith("# Checkbevindingen schoon.ttl")

    def test_met_een_gebied_is_de_gebiedsnaam_de_titel(self, tmp_path: Path) -> None:
        """De lezer moet aan de titel zien waar het rapport over gaat."""
        gebieden = load_studiegebieden(GIS_DIR / "buurt_noord.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )

        tekst = _rapport(runs[0].run, tmp_path)

        assert tekst.startswith("# Noord")

    def test_de_totaalsynthese_heet_totaal(self, tmp_path: Path) -> None:
        gebieden = load_studiegebieden(GIS_DIR / "buurten_twee.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )

        schrijf_uitvoer_gebieden(runs, tmp_path, RUNDATUM, met_geopackage=False)
        tekst = (tmp_path / "totaal" / "synthese.md").read_text(encoding="utf-8")

        assert tekst.startswith("# Totaal (2 gebieden)")
        assert "afbakening_kern_en_schil.ttl" in tekst


class TestAantallen:
    def test_de_tabel_staat_boven_de_verantwoording(self, tmp_path: Path) -> None:
        """Eerst waar het over gaat, dan of het voldoet, dan de kleine letters."""
        tekst = _rapport(_run("net003_tegen_de_richting.ttl"), tmp_path)

        assert tekst.index("Wat er in dit gebied ligt") < tekst.index("Voldoen we in dit gebied?")
        assert tekst.index("Voldoen we in dit gebied?") < tekst.index("## Verantwoording")

    def test_de_metrages_kloppen_met_de_dataset(self) -> None:
        """De fixture heeft een streng van 1000 naar 1050: vijftig meter."""
        tabel = omvangtabel(_run("net003_tegen_de_richting.ttl"))
        leidingen = tabel[tabel["Objecttype"] == "GemengdRiool"]

        assert list(leidingen["Aantal"]) == [1]
        assert list(leidingen["Lengte (m)"]) == [50]

    def test_putten_krijgen_geen_lengte(self) -> None:
        tabel = omvangtabel(_run("net003_tegen_de_richting.ttl"))
        putten = tabel[tabel["Objecttype"] == "Inspectieput"]

        assert list(putten["Aantal"]) == [2]
        assert set(putten["Lengte (m)"]) == {"—"}

    def test_de_tabel_telt_alleen_de_kern(self, tmp_path: Path) -> None:
        """De schil zit in de dataset van de run maar wordt niet gerapporteerd."""
        gebieden = load_studiegebieden(GIS_DIR / "buurt_noord.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )
        run = runs[0].run
        assert run.analyseset is not None and run.analyseset.schil

        tabel = omvangtabel(run)

        assert int(tabel["Aantal"].sum()) == len(run.analyseset.kern)

    def test_het_rapport_noemt_de_schil_als_voetnoot(self, tmp_path: Path) -> None:
        gebieden = load_studiegebieden(GIS_DIR / "buurt_noord.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )

        tekst = _rapport(runs[0].run, tmp_path)

        assert "in de contextschil" in tekst


class TestManagementsamenvatting:
    def test_elke_conformiteitsklasse_krijgt_een_regel(self, tmp_path: Path) -> None:
        tekst = _rapport(_met_nulmeting(), tmp_path)

        assert "GWSW CFK MdsPlan" in tekst
        assert "GWSW CFK MdsProj" in tekst
        assert "Eigen checks buiten GWSW" in tekst

    def test_fouten_leveren_een_kruisje(self, tmp_path: Path) -> None:
        """De join-fixture bevat Violations, dus de klassen halen het niet."""
        tekst = _rapport(_met_nulmeting(), tmp_path)
        regel = next(r for r in tekst.splitlines() if "GWSW CFK MdsPlan" in r)

        assert KRUISJE in regel

    def test_alleen_waarschuwingen_leveren_een_vinkje_met_zichtbaar_aantal(self) -> None:
        """Een gebied met alleen waarschuwingen voldoet, maar zwijgt er niet over."""
        from helpers_melding import melding
        from nlriochecker.uitvoer.samenvatting import samenvatting

        regels = samenvatting([melding(ernst="W", bron="register")], Meetbereik.van(CFKS, CFKS))
        eigen = next(r for r in regels if r.onderwerp == "Eigen checks buiten GWSW")

        assert eigen.teken == VINKJE
        assert "1 waarschuwing" in eigen.tekst()

    def test_zonder_meting_staat_er_een_toestandstekst(self, tmp_path: Path) -> None:
        """Geen vinkje en geen kruisje: er valt niets te oordelen."""
        run = replace(_run("schoon.ttl"), meetbereik=Meetbereik.niet_gemeten(CFKS))

        tekst = _rapport(run, tmp_path)
        regels = [r for r in tekst.splitlines() if "GWSW CFK" in r]

        assert regels
        for regel in regels:
            assert NIET_GEMETEN in regel
            assert "--shacl" in regel or "`--shacl`" in regel

    def test_een_niet_gekozen_klasse_krijgt_geen_oordeel(self) -> None:
        """Bij een deelset valt er over de overige klassen niets te zeggen."""
        from nlriochecker.uitvoer.samenvatting import samenvatting

        regels = samenvatting([], Meetbereik.van(["Hyd", "MdsPlan"], ["Hyd"]))
        hyd = next(r for r in regels if r.onderwerp == "GWSW CFK Hyd")
        mdsplan = next(r for r in regels if r.onderwerp == "GWSW CFK MdsPlan")

        assert hyd.teken == VINKJE
        assert mdsplan.teken == NIET_GEMETEN
        assert "niet gemeten" in mdsplan.tekst()


class TestDetailrapportage:
    def test_de_nulmeting_staat_boven_de_eigen_checks(self, tmp_path: Path) -> None:
        """Eerst compliance, dan eigen bevindingen."""
        tekst = _rapport(_met_nulmeting(), tmp_path)

        assert tekst.index("### 1. GWSW-nulmeting") < tekst.index("### 2. Eigen checks")

    def test_de_nulmeting_wordt_per_vorm_getoond_met_haar_klassen(self, tmp_path: Path) -> None:
        tekst = _rapport(_met_nulmeting(), tmp_path)

        assert "Overtredingen per SHACL-vorm" in tekst
        assert "NULMETING-Put_HoogtePut_card" in tekst
        assert "MdsPlan, MdsProj" in tekst

    def test_de_foutchecks_staan_boven_de_waarschuwingschecks(self, tmp_path: Path) -> None:
        """De ernst komt uit de run zelf; een prefixheuristiek zou hem verkeerd raden."""
        run = _run("net003_tegen_de_richting.ttl")
        ernst_van = {outcome.check_id: outcome.severity.value for outcome in run.outcomes}
        tekst = _rapport(run, tmp_path)

        koppen = [regel for regel in tekst.splitlines() if regel.startswith("#### ")]
        ernsten = [ernst_van[kop.split()[1]] for kop in koppen]

        assert koppen
        assert set(ernsten) == {"F", "W"}, "de fixture moet beide soorten checks bevatten"
        assert ernsten == sorted(ernsten), "alle F-checks boven alle W-checks"

    def test_zonder_nulmeting_is_er_geen_nulmetingblok_en_geen_nummering(
        self, tmp_path: Path
    ) -> None:
        """Zonder blok 1 is "2. Eigen checks" een verwijzing naar niets."""
        tekst = _rapport(_run("schoon.ttl"), tmp_path)

        assert "### 1. GWSW-nulmeting" not in tekst
        assert "### 2. Eigen checks" not in tekst
        assert "### Eigen checks" in tekst

    def test_de_detailkop_staat_er_altijd_boven(self, tmp_path: Path) -> None:
        """Anders hangt het checkdetail als H3 onder "Verantwoording" in elke TOC."""
        for run in (_run("schoon.ttl"), _met_nulmeting()):
            tekst = _rapport(run, tmp_path)
            kop = next(r for r in tekst.splitlines() if r.startswith("### ") and "Eigen" in r)

            assert "## Detailrapportage" in tekst
            assert tekst.index("## Detailrapportage") < tekst.index(kop)


class TestVerantwoordingBlijft:
    """Verplaatsen mag, schrappen niet."""

    def test_de_verantwoording_noemt_nog_alles_wat_ze_noemde(self, tmp_path: Path) -> None:
        gebieden = load_studiegebieden(GIS_DIR / "buurt_noord.gpkg")
        runs = toets_gebieden(
            load_dataset(TTL_DIR / "afbakening_kern_en_schil.ttl"),
            gebieden,
            _config(),
            meetbereik=Meetbereik.niet_gemeten(()),
        )

        tekst = _rapport(runs[0].run, tmp_path)

        assert "Samenvatting per check" in tekst
        assert "buiten het gebied" in tekst
        assert "typeringspoort" in tekst
        assert "Analyseset:" in tekst
        assert "Externe bronnen" in tekst


class TestOnderdrukking:
    """Issue #65: wat `[rapport]` uit de stroom houdt, staat in de verantwoording.

    De fixture: vrijvervalstreng L1 kruist persleiding L2; TOP-011 meldt het paar een
    keer, met L1 als hoofdobject. De nulbevinding geeft L2 een eigen melding, en die
    is het enige wat `MechanischeTransportleiding` hier onderdrukt.
    """

    @staticmethod
    def _run_onderdrukt(klassen: Sequence[str]) -> CheckRun:
        config = _config()
        config.rapport.onderdruk_klassen = list(klassen)
        dataset = load_dataset(TTL_DIR / "onderdruk_persleiding.ttl")
        run = run_checks(CheckContext(dataset=dataset, config=config), ["TOP-011"])
        return replace(
            run,
            nulbevindingen=(
                Nulbevinding(
                    check_id="NULMETING-Put_HoogtePut_card",
                    vorm="Put_HoogtePut_card",
                    focus_node="L2",
                    ernst="F",
                    object_uri="http://example.org/toets#L2",
                    object_label="2",
                    objecttype="Persleiding",
                    boodschap="aantal voorkomens wijkt af (exact=1)",
                    waarde="te weinig voorkomens",
                    cfk=("MdsPlan",),
                    systemisch=False,
                    herleid=True,
                ),
            ),
        )

    def test_de_verantwoording_telt_wat_er_onderdrukt_is(self, tmp_path: Path) -> None:
        """Stilte leest als "alles gecontroleerd"; de telling hoort in het rapport."""
        tekst = _rapport(self._run_onderdrukt(["MechanischeTransportleiding"]), tmp_path)

        assert "**1 melding onderdrukt**" in tekst
        assert "per check: geen" in tekst
        assert "per klasse: MechanischeTransportleiding 1" in tekst

    def test_zonder_lijsten_zwijgt_het_rapport_erover(self, tmp_path: Path) -> None:
        """Geen keuze om te verantwoorden, dus geen alinea."""
        tekst = _rapport(self._run_onderdrukt([]), tmp_path)

        assert "op grond van `[rapport]`" not in tekst

    def test_de_telling_staat_gesorteerd_en_zegt_geen_bij_niets(self) -> None:
        """Gesorteerd op sleutel: anders verschilt de zin tussen twee runs op dezelfde data."""
        assert _telling({"TOP-011": 3, "ATTR-001": 2}) == "ATTR-001 2, TOP-011 3"
        assert _telling({}) == "geen"
