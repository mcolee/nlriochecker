# AFK-regie 29-08-2026: issues #105, #106, #107 en #103

Geef dit aan een **verse (gecleared) Fable-sessie** in `/home/martin/nlriochecker`, in
auto-mode. Fable is de regisseur; het werk doen **Opus-subagents** (`model: opus`,
`subagent_type: general-purpose`, per taak een verse agent). De auteur is er niet bij:
**unattended, stel geen vragen**. Het sjabloon `docs/agents/afk-regie.md` geldt onverkort;
dit bestand vult alleen de issuelijst, de volgorde, de voorspelde getallen en de
bijzonderheden van deze reeks in. Bij tegenspraak wint `CLAUDE.md`, dan het sjabloon.

## Vooraf, één keer

1. Lees `CLAUDE.md`, `docs/agents/afk-regie.md`, `docs/agents/analyse-harness.md` en van
   `docs/architectuur.md` de delen over de netwerkgraaf (`checks/verbanden.py`, BO-53/54),
   de meldingenstroom en de GeoPackage. Eén keer volledig, niet per symbool.
2. Controleer de uitgangstoestand: `git status` schoon op `dev`, `git log --oneline -3`
   toont `2f02c01` (BO-82) of later, en `gh issue list --label ready-for-agent` toont
   precies #103, #105, #106, #107.
3. De referentierun voor alle metingen is **`uitvoer/29082027-02`** (koud, 29-08,
   147.649 meldingen; `bevindingen.csv` is `;`-gescheiden, kolom `Check`). Tel daar op;
   start geen nieuwe volle run vóór de slotstap.
4. Issues lezen kan met `gh issue view N --comments` (werkt weer sinds gh 2.98) of met
   `gh api repos/mcolee/nlriochecker/issues/N --jq .body` plus `/comments`. Lees altijd
   ook de comments: #106 draagt daar het domeinbesluit BO-82.

## Volgorde — strikt sequentieel

| # | Issue | Blocked by | BO | Review |
|---|---|---|---|---|
| 1 | **#105** telbaar hulpstuk als doorgeefknoop in de vrijvervalgraaf | — | BO-83 | Substantieel (`checks/`, graaf) |
| 2 | **#106** RVZ-006 benoemt aanwijzingen per deelstelsel | #105 (beide raken `rollen` van RVZ-006) | BO-84 | Substantieel (`checks/`, `uitvoer/`) |
| 3 | **#107** laag `vlakken`: één stijlregel per check | — (na #106 om `gpkg.py`-conflicten te vermijden) | BO-85 | Klein (`/code-review medium`) |
| 4 | **#103** README, `docs/gebruik.md`, voorbeeld Koekangerveld | #105–#107 (het voorbeeld en de schermafdruk tonen de eindstand) | geen | `/code-review medium` |

BO-nummers: BO-82 is bezet (RVZ-006: persleiding/lozingspunt geen afvoereindpunt). Neem
altijd `grep -n '^### BO-' docs/beslislog.md | tail -1` + 1; de kolom hierboven is de
verwachting, niet de waarheid.

Eén issue = commit + push + CI groen + comment + close vóór het volgende.

## Voorspelde getallen (De Wolden en Hoogeveen, tegen `uitvoer/29082027-02`)

| Issue | Meting | vóór | verwacht ná |
|---|---|---:|---:|
| #105 | strengen "buiten de netwerkanalyse" (NET-notitie) | 152 | **0** |
| #105 | netwerkdelen | 794 | **733** |
| #105 | RVZ-006 meldingen / deelstelsels | 1062 / 99 | **1058 / 96** (weg: `ds-Fo1G0080`, `ds-Wi1G0416`, `ds-Zu1G0510`) |
| #105 | NET-001 / NET-002 | 8467 / 3031 | **8543 / 3049** |
| #106 | RVZ-006 aantal | 1058 / 96 | **ongewijzigd**; alleen de tekst; aanwijzingen 13 / 8 / 14 / 18 / 27 / 24 (zie de tabel in #106; "geen van deze" na #105 = 24) |
| #107 | GeoPackage-inhoud | — | **ongewijzigd** op de rij `vlakken` in `layer_styles` na; 4 legendaregels |
| #103 | `toets` op `voorbeelden/koekangerveld/` | — | eigen checks gelijk aan de gebiedsrun Koekangerveld op de volle data; README ≤ 150 regels; voorbeeld ≤ 10 MB |

Elke andere check blijft per issue gelijk aan de referentierun. Wijkt iets af: verklaar het
in de issue-comment, verzin geen nieuwe waarheid.

## Bijzonderheden per issue

- **#105.** De importkring (`topologie.py` importeert `verbanden`) is de valkuil; het issue
  kiest een nieuwe module `checks/hulpstukken.py`. De AST-drifttest
  `test_declaratie_volgt_de_code` bepaalt welke checks `"hulpstukken"` in `rollen` krijgen --
  volg de test, niet de verwachting. Regenereer `docs/dekkingsmatrix.md`. Het meetscript
  staat in het issue; commit het als `scripts/meet_hulpstukgraaf.py` (BO-43) nadat de
  monkeypatch vervangen is door de echte code, of leg in het BO uit waarom niet.
- **#106.** Lees de comment met BO-82 vóór je begint: persleiding en lozingspunt tellen niet
  als afvoereindpunt; de aanwijzingen zeggen "geen afvoereindpunt (BO-82)". Geen nieuwe
  drempel; `snapping_tolerantie_m` is de enige grens. Controleer in `uitvoer/melding.py` of
  `details` naar de JSON stroomt vóór je `details["diagnose"]` toevoegt; het JSON-schema
  (`docs/json-schema.md`, `schema_versie`) mag in dit issue niet veranderen.
- **#107.** Wijkt bewust af van BO-79; het BO legt vast dat de rijen blijven en alleen de
  standaardstijl verandert. De PyQGIS-test draait lokaal wél (er is PyQGIS op deze machine)
  en in CI niet; draai `uv run pytest tests/test_uitvoer_qgis.py` op de voorgrond en plak de
  uitvoer.
- **#103.** Het grootste issue; splits het in drie implementer-taken in deze volgorde:
  (a) `scripts/maak_voorbeeld.py` + `voorbeelden/koekangerveld/` + rooktest
  `tests/test_voorbeeld.py`; (b) `docs/gebruik.md` (verhuizen én controleren) +
  `scripts/maak_schermafdruk.py` + `docs/img/`; (c) de README zelf (≤ 150 regels, opbouw
  uit het issue). Elk deel krijgt zijn eigen poort en commit. Geen "waarom"-blok, geen
  Engels, geen CONTRIBUTING. De rooktest moet op de runner draaien (geen `data/` nodig);
  bewijs dat met `scripts/runnerpoort.py`. De schermafdruk: headless via PyQGIS; lukt de
  popup niet, laat hem weg en zeg dat in de comment. Bewaar de README-review voor de auteur:
  sluit #103 wél, maar noem in de comment dat de auteur de README nog leest.

## De lus per issue

Precies het sjabloon (`docs/agents/afk-regie.md`, "De lus per issue N"), met deze
aanscherpingen uit de metingen van 24–26-08:

- Brief aan elke implementer bevat letterlijk: *"Lees `docs/architectuur.md` en
  `docs/agents/analyse-harness.md` één keer volledig vóór je begint, en daarna elk bestand
  dat je aanraakt één keer volledig; geen `cd`; draai de poort en elke meetrun op de
  voorgrond en plak de uitvoer; niet pushen."* Taaklabel "Task N" in het Engels.
- Vertrouw de geplakte poort van de implementer; draai hem niet nog eens.
  `scripts/runnerpoort.py` één keer, vlak vóór de push, nooit parallel aan een pytest.
- Re-review alleen als de fixronde meer dan één bevinding of meer dan ~100 diffregels
  raakte.
- Comment pas na het reviewoordeel; dan `gh issue close`.
- Push: `timeout 45 git push`; CI selecteren op `gh run list --commit <sha>`, dan
  `gh run watch <id> --exit-status`. Rood → fixen, niet door naar het volgende issue.
- Na een dispatch of een achtergrondcommando: niets doen tot de melding komt.
- Classifier-blokkade (`gh issue create`, soms de eerste dispatch): geen varianten proberen;
  noteer het en ga door. Er hoeft in deze reeks geen issue aangemaakt te worden.

## Slotstap

1. Volledige gemeentebrede run op de eindstand van `dev`, met **dezelfde vlaggen** als
   `docs/checks-audit-2026-08.md:20` (drie `--shacl`, `--projectconfig
   configs/dewoldenhoogeveen.toml`, `--bronnen data/gis_dewoldenhoogeveen`), naar
   `uitvoer/<datum>_slotrun`, als `run_in_background` (4,5–5,5 min, ~4 GB).
2. Vergelijk per check met `uitvoer/29082027-02/bevindingen.csv`; verwacht: alleen RVZ-006,
   NET-001 en NET-002 anders (tabel hierboven), totaal 147.649 → 147.739 (+76 +18 −4).
3. Open de GeoPackage niet zelf; controleer `layer_styles` met de PyQGIS-test.
4. Slotrapport in `uitvoer/<datum>_slotrun/_slotrapport.md` én als laatste bericht: per
   issue wat er landde, gemeten naast voorspeld, BO-nummers, open gebleven punten en de
   uitgestelde minors uit de reviews (de ledger is git-ignored en telt niet als bewaarplek).
5. Laat `dev` schoon achter: alles gecommit en gepusht, CI groen, geen half bewerkt bestand.

## Harde grenzen

- Nooit `main`; geen uitgave; geen `scripts/uitgave.py`.
- Geen wijziging aan een Harde regel of publiek contract zonder Substantiële review;
  het JSON-schema verandert in deze reeks niet.
- Overschrijf nooit invoerbestanden; alleen `uitvoer/` schrijft; versienummer alleen in
  `pyproject.toml`.
- Bij twijfel over domeinlogica: GWSW is leidend, de issue-sectie **Aannames** is de
  tweede bron, een comment de derde; nooit een vraag aan de auteur.
