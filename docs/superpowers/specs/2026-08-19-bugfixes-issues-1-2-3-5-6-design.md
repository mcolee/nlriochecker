# Bugronde: de vijf open bug-issues — ontwerp

Datum: 2026-08-19. Status: goedgekeurd door de auteur in de brainstorm; dit document legt de
beslissingen vast waarop het implementatieplan rust.

Scope: de vijf issues met label `bug` op `mcolee/nlriochecker`: #1, #2, #3, #5 en #6.
Enhancements (#4, #8, #9) en documentatie-issues (#7, #11) vallen buiten deze ronde.

## Uitgangspunten voor de hele ronde

- Werk op `dev`; geen pakketversiebump; geen nieuwe afhankelijkheden.
- Elke fix is een eigen taak met een eigen commit en sluit zijn issue met een reactie die
  de commit en het gemeten effect noemt.
- Twee fixes raken het checkregister (#1 voegt een check toe, #6 haalt er twee uit de
  schraptabel). Volgens de eigen conventie van het register (0.8 kwam er door het vervallen
  van EXT-008) is dat een nieuwe registerversie: **v0.9**. Dat is een aparte taak die vóór
  #6 en #1 landt.
- Per taak de poort uit CLAUDE.md: `ruff check`, `ruff format --check`, `mypy`, `pytest`.
  De twee reviewskills (`superpowers:requesting-code-review`,
  `python-library-complete:reviewing-python-libraries`) draaien één keer aan het eind
  over de hele ronde, zoals het vorige plan dat ook deed.

## Beslissingen uit de brainstorm

| Vraag | Beslissing |
|---|---|
| #1: hoe modelleren | Leesregel in `dataset.py` (na het laden) + nieuwe compleetheidscheck **ATTR-013**, ernst **W**, dimensie **Compleetheid** |
| #1: configvorm | Nieuwe sectie `[vulwaarden]`: `hoogte_kenmerken` (lijst, leeg = uit) en `hoogte_band_m` (float ≥ 0, default 0.01) |
| #3: populatie EXT-002/003 | Blijft `klassen.vrijvervalleiding`; een Duiker is geen rioolleiding en valt buiten scope; de uitzondering van EXT-003 is in de praktijk `Zinker` |
| #6: wanneer RVZ-002/003 afgaan | Elke overstortput zonder geregistreerd niveau resp. breedte — ook als het `Overstortdrempel`-onderdeel zelf ontbreekt; ernst **W**, dimensie **Compleetheid** |
| Registerversie | v0.9, één bump voor #1 en #6 samen |

## Issue #5 — `_bouw_netwerk` en parallelle strengen

**Feit.** `checks/netwerk.py::_bouw_netwerk` zet `graph.add_edge(begin, eind, uri=…, label=…)`
op een `nx.DiGraph`; de tweede van twee parallelle strengen overschrijft de eerste.
`KringloopInNetwerk._eerste_streng` (NET-004) is de enige lezer van kantattributen in de
hele repo; alle andere NET-checks gebruiken de graaf structureel.

**Ontwerp.**
- `_Netwerk` krijgt `strengen_per_kant: dict[tuple[str, str], tuple[Conduit, ...]]`,
  gesleuteld op de gerichte kant zoals die in de graaf staat (dus ná de BOB-omdraaiing),
  gevuld in `_bouw_netwerk`. De strengen per kant staan gesorteerd op URI.
- `add_edge` krijgt geen attributen meer; de val verdwijnt in plaats van dat hij omzeild
  wordt.
- `_eerste_streng` leest `strengen_per_kant[(kring[0], kring[1])][0]`. Deterministisch,
  onafhankelijk van invoervolgorde.
- Handgeschreven fixture `tests/fixtures/ttl/net004_parallelle_strengen.ttl`: kopie van
  `net004_kringloop.ttl` met een tweede streng `L5b` (`5b`) naast `L5` op C→D, naar het
  patroon van `afbakening_parallelle_strengen.ttl`.
- Test: NET-004 levert precies één bevinding; `object_uri` is een streng die werkelijk op
  de kant `kring[0]→kring[1]` ligt (te controleren via `dataset.conduits[uri]` en
  `verbonden_knopen`); en de uitkomst is gelijk als de fixture de strengen in omgekeerde
  volgorde declareert (tweede fixture of in-memory DiGraph-test zoals
  `test_net004_voorbeeldkring_hangt_niet_van_de_knoopvolgorde_af`).

## Issue #2 — ATTR-006 en de botsende melding-ID's

**Feit.** `DiameterGroterDanPut` (ATTR-006) levert tot twee bevindingen op dezelfde streng
(begin- en eindput), zet geen `zijde` in `details` en erft `id_sleutels = ("zijde",)`; de
identiteit valt terug op een volgnummer. De sweep in
`tests/test_uitvoer_identiteit_sweep.py` bestaat al maar de fixture
`attr006_te_grote_streng.ttl` heeft maar één te kleine put.

**Ontwerp.**
- ATTR-006 loopt niet langer over `putten_van(...)` maar over de uiteinden met zijde, op
  dezelfde manier als HGT-004 (`_uiteinden`/`verbonden_knopen`: `"beginpunt"` /
  `"eindpunt"`), en zet `zijde=` in de details. `id_sleutels` blijft de default.
- Nieuwe generatorfixture `attr006_twee_te_kleine_putten.ttl` (beide putten 800×800):
  blok-A verwacht labels `["1", "1"]`; de sweep slaagt zonder volgnummer en zonder
  waarschuwing.
- CHANGELOG: de melding-ID's van ATTR-006 verschuiven eenmalig; `schema_versie` blijft
  1.0 (precedent EXT-001/003 in `docs/json-schema.md`).
- De suggestie "een sweep over alle checks" uit het issue is al gebouwd; in de
  sluitreactie benoemen dat de fixture te klein was, niet de sweep.

## Issue #3 — EXT-002/003 en duikers

**Feiten.** In `Ontologie_GWSW_Totaal.ttl` is `Duiker rdfs:subClassOf Leiding` (niet
VrijvervalRioolleiding; definitie "een leiding die oppervlaktewater-elementen verbindt") en
`Zinker rdfs:subClassOf VrijvervalRioolleiding`. De uitzondering van EXT-003 kán dus afgaan,
maar alleen op zinkers. De generator `scripts/maak_ttl_fixtures.py` verklaart `Duiker`
ten onrechte onder `VrijvervalRioolleiding`, waardoor `test_ext003_zwijgt_over_een_duiker`
groen is om een reden die op echte data niet geldt. Er is geen `Zinker`-fixture.

**Ontwerp.**
1. Generator-PRELUDE gelijktrekken met de ontologie: `Duiker rdfs:subClassOf Leiding`,
   `Zinker rdfs:subClassOf VrijvervalRioolleiding`. Alle fixtures regenereren
   (`uv run python scripts/maak_ttl_fixtures.py`), de drifttest
   `tests/test_ttl_fixtures.py` houdt dat vast. In `ext_scenario.ttl` wordt streng 3 een
   `Zinker` (blijft kruisend: EXT-002 meldt hem, EXT-003 niet) en komt er een `Duiker`
   bij die dezelfde watergang kruist en in geen van beide populaties zit. Verwachtingen
   in `tests/test_checks_extern.py` en alle andere tests die op het scenario of op
   `Duiker` leunen (ADM-007, stelseltypen `transport`) volgen de nieuwe hiërarchie; wat
   rood wordt, wordt per geval beoordeeld en niet weggemasseerd.
2. `_WatergangKruising.kruisingen()` wordt één keer per context berekend en gedeeld via
   `context.cached("ext:watergangkruisingen", …)` als tuple van treffers (conduit, vorm,
   rij, laag, buffer). Het voorvoegsel `ext:` krijgt een regel in de docstring van
   `CheckContext.cached` (eigenaar `checks/extern.py`). De BO-18-beperking (eerste
   waterdeel per streng) blijft ongewijzigd.
3. `notes()` van EXT-002 en EXT-003 melden hoeveel strengen van de klassen in
   `klassen.kruisingsleiding` die géén vrijvervalleiding zijn (op deze dataset dus
   duikers) buiten de populatie vallen en niet bekeken zijn. Nul is ook een regel waard
   als de klasse in de config staat.
4. Registerrij EXT-003 gepreciseerd: "Kruising met watergang zonder registratie als
   zinker; een duiker is geen rioolleiding en valt buiten de populatie". Ernst en dimensie
   ongewijzigd. Beslislog BO-25.
5. Geen verandering in de meldingen op De Wolden (859/859); het getal moet dat bevestigen.

## Issue #6 — RVZ-002 en RVZ-003 terug in de engine

**Feiten.** In geen van de drie SHACL-rapporten bestaat een vorm op `Drempelniveau` of
`Drempelbreedte`; de enige drempelvorm is `Overstortput_Overstortdrempel_card` (heeft de
put een drempel: Hyd 218, MdsPlan 218, MdsProj 0). `dekking.toml` claimt bewijsprefixen die
niet bestaan en de tests leggen `UNTOUCHED` als verwachting vast. `verify_register()`
toetst alleen ID-pariteit, niet of een sentinel iets aantoont. In De Wolden heeft geen van
de 218 overstortputten een `Overstortdrempel`-onderdeel. De bouwstenen staan er al:
`randvoorzieningen.py` leest `Drempel(uri, label, niveau, breedte, put_uri)` via
`drempels_per_put()`/`alle_drempels()`; `breedte` wordt nog door niets gebruikt.

**Ontwerp.**
- Register v0.9: rijen RVZ-002 en RVZ-003 verhuizen van *Geschrapte checks* naar de
  RVZ-tabel met `W | Compleetheid`. Open punt 7 ("RVZ-003 is juist wel geschrapt") wordt
  bijgewerkt. Versiehistorie benoemt de reden: dekkingclaim niet aantoonbaar in de
  rapporten.
- Twee checks in `randvoorzieningen.py`, populatie `klassen.overstortput`:
  - RVZ-002 `OverstortZonderDrempelniveau`: melding als geen enkele drempel van de put
    een `Drempelniveau` heeft, óók als er geen drempel is; details `drempels=<aantal>`.
  - RVZ-003 `OverstortZonderDrempelbreedte`: idem voor `Drempelbreedte`.
  - `examined()` = aantal overstortputten. Eigen `notes()`: het aantal putten zonder
    drempelonderdeel, en dat de nulmetingvorm `Overstortput_Overstortdrempel_card` dat
    deel ook meldt (bewuste overlap; de check werkt ook zonder `--shacl`).
- `dekking.toml`: de twee sentinels eruit (anders faalt `verify_register` op
  `zonder_registerrij`).
- Fixtures via de generator: `rvz002_overstort_zonder_niveau.ttl` (drempel met alleen
  breedte) en `rvz003_overstort_zonder_breedte.ttl` (drempel met alleen niveau), plus een
  variant zonder drempel die beide checks laat afgaan; `rvz_schoon.ttl` heeft al niveau en
  breedte.
- Tests die de schrapping vastleggen draaien om: `test_coverage.py` (parametrisering en
  `test_drempelvormen_ontbreken_in_de_shacl_meting`), `test_cli.py:48,69`,
  `test_reporting.py:74-76`, `test_integration.py:112-113`, `test_config.py:12`,
  `test_checks_registry.py:61`, blok-A `DEFECTEN` en `test_elk_defect_heeft_een_eigen_fixture`.
- `docs/dekkingsmatrix.md` regenereren met `scripts/dekkingsmatrix.py`.
- **Het gat dichten**: nieuwe regressietest op de De Wolden-rapporten dat
  `CoverageResult.untouched` leeg is — elke resterende geschrapte check is `TOUCHED`. Een
  toekomstige schrapping zonder aantoonbare dekking faalt daarmee in CI. Beslislog BO-26.
- Verwacht effect De Wolden: +218 W per check.

## Issue #1 — vulwaarde 0,000 in BOB en maaiveld

**Feiten.** 25,1% van de BOB's en 14% van de maaiveldhoogtes in De Wolden zijn 0,00(1);
het AHN ligt er op 5–17 m NAP. `_aspect_van_klasse` in `dataset.py` filtert alleen op
`None`; HGT-002/003/004/014/018 lezen de nul als meting (~5.700 van 31.901 fouten).
De HGT-checks slaan `None` al over en `_ontbreekt()` meldt de aantallen; HGT-018 heeft
nog geen `notes()`. `GwswDataset.nodes` en `.conduits` zijn de enige houders van
`Node`/`Conduit`.

**Ontwerp.**
- Config: nieuwe pydantic-sectie `VulwaardeOptions` in `checkconfig.py`, TOML-sectie
  `[vulwaarden]` in `checks.toml` en `configs/dewoldenhoogeveen.toml`:
  `hoogte_kenmerken = ["BobBeginpuntLeiding", "BobEindpuntLeiding", "Maaiveldhoogte",
  "Putdekselniveau"]` (lege lijst zet de regel uit) en `hoogte_band_m = 0.01`
  (|waarde| ≤ band is een vulwaarde). Geen hardcoded drempel.
- Leesregel: `dataset.markeer_vulwaarden(dataset, kenmerken, band_m) -> GwswDataset`,
  puur, geeft via `dataclasses.replace` een dataset terug waarin de betrokken aspecten
  `None` zijn en `Node`/`Conduit` een nieuw veld `vulwaarden: tuple[Vulwaarde, ...]`
  dragen (`kind`, ruwe waarde). Toegepast op één plek: `toetsrun.voer_toets_uit` direct na
  `laad_met_cache`, vóór de typeringspoort. Lader, cache en `analyseer`/`dekking` blijven
  onaangeraakt; de cache bewaart de ruwe parse.
- Check **ATTR-013** `HoogteOpVulwaarde` in `attributen.py`, W / Compleetheid, titel
  "Hoogtekenmerk op vulwaarde (rond 0 m NAP) geregistreerd als meting": één melding per
  object met `kenmerken` en `waarden` in details; populatie putten plus
  vrijvervalstrengen; `examined()` = beide samen; `notes()` noemt band en kenmerken uit de
  config en meldt expliciet als de regel uit staat.
- Register v0.9: rij ATTR-013 in de ATTR-tabel; beslislog BO-27 (waarom geen nieuw
  HGT-nummer: het is een registratiegebrek, geen hoogtefout; waarom een band en geen
  exacte nul: 0,01 komt ook voor; waarom in laag Nederland het uit kan).
- HGT-018 krijgt `notes()` via `_ontbreekt`, zodat de overgeslagen objecten ook daar in
  het rapport staan.
- Fixtures via de generator: `attr013_vulwaarde_hoogte.ttl` (een put met maaiveld 0,00 en
  een streng met BOB 0,000 aan één zijde), met tests: ATTR-013 meldt beide; HGT-004 en
  HGT-014 zwijgen op die fixture mét toelichting; `markeer_vulwaarden` met lege
  kenmerkenlijst is de identiteit; `hoogte_band_m = 0` markeert alleen exact 0.
- Verwacht effect De Wolden: F daalt met circa 5.700; W stijgt met het aantal objecten dat
  ten minste één vulwaarde draagt (orde 10.000). Beide getallen in de sluitreactie van het
  issue, gemeten, niet geschat.

## Registerbump v0.9 (gedeelde taak)

- `git mv data/checkregister-gwsw-nulmeting-v0_8.md …-v0_9.md`; kopregel "Versie 0.9";
  versiehistorie-alinea (2026-08-19): RVZ-002/003 terug uit de schraptabel, ATTR-013
  toegevoegd, EXT-003 gepreciseerd.
- De vijf versieplekken die `tests/test_register_versie.py` bewaakt (`register.py`,
  `dekking.toml` twee velden, `checkconfig.py` `ReportOptions.register_versie`, het
  bestand zelf) plus het vaste pad in `tests/test_checks_registry.py` en alle
  verwijzingen die `grep -rn 'v0_8' --include='*.md' --include='*.toml' --include='*.py'`
  vindt (`CLAUDE.md`, `CONTEXT.md`, `configs/`, `checks.toml`, `uitvoer/bevindingen.py`,
  tests). Historische plannen/specs/verslagen in `docs/` blijven staan zoals ze zijn.
- `docs/dekkingsmatrix.md` regenereren.

## Afronding

- Zware meting op De Wolden + Hoogeveen met het reproductiecommando uit issue #1 (marker
  `zwaar`, handmatig, `--geen-cache` niet nodig); de getallen per issue in de
  sluitreacties.
- `CHANGELOG.md` onder `## [Unreleased]`: per issue een regel, plus de ID-verschuiving van
  ATTR-006 en de registerversie.
- Beslislog BO-25 (EXT-003 en duikers), BO-26 (RVZ-002/003 terug; de inhoudelijke poort
  op sentinels), BO-27 (vulwaarden als leesregel + ATTR-013).
- Reviewskills, bevindingen verwerken, laatste commit. Geen merge naar `main`.
