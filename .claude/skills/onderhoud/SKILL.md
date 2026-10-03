---
name: onderhoud
description: Verwerkt de lessen van één onderdeel uit docs/lessen.md tot één issue, één branch en één PR met per les een rode test die groen wordt (begrensde zelfverbetering, principe 9 (voorstel) van manifesto.md). Gebruik bij "verwerk de lessen", "onderhoud <onderdeel>" of "/onderhoud". Niet voor een nieuwe functie zonder les: dat is een gewoon issue.
---

# Onderhoud: lessen verwerken

Uitvoering van principe 9 (voorstel) van `manifesto.md`: begrensde zelfverbetering, nooit een
gesloten lus. De lus wijzigt code en voegt tests toe; de eigenaar merget elke PR zelf.
Testcommando's, lint en beschermde paden staan in `.claude/cyclus.toml`; kopieer ze niet.

```text
les → rode test → wijziging → groen → volledige suite groen → PR → eigenaar merget
```

## 1. Onderdeel kiezen

Noemt de eigenaar geen onderdeel, vraag er één (AskUserQuestion), uit de koppen in
`docs/lessen.md` met minstens één les. Eén run raakt precies één onderdeel.

## 2. Open PR controleren

`gh pr list --state open --search "Onderhoud lessen: <onderdeel> in:title"`. Staat er al één
open, stop dan en meld die PR. Per onderdeel staat er maximaal één onderhouds-PR open.

## 3. Lezen

Eén keer volledig: de sectie `## <onderdeel>` in `docs/lessen.md`, `CLAUDE.md`, de broncode van
het onderdeel (onder `src/nlriochecker/`), de relevante sectie van `docs/architectuur.md`, en
`tests/test_lessen_<onderdeel>.py` als dat bestaat.

## 4. Per les een route

Nieuwste les eerst. Kies per les één route:

- **Wijziging**: de les wijst een concrete aanpassing aan.
- **Geen wijziging**: al verwerkt, achterhaald of een eenmalig incident zonder structurele
  oorzaak. Noteer waarom.
- **Vraag aan de eigenaar**: dubbelzinnig, een keuze die de agent niet mag maken (principe 7),
  of de les raakt iets uit "Beschermd". Formuleer één gerichte vraag.

## 5. Issue en branch

1. `gh issue create --title "Onderhoud lessen: <onderdeel>" --label ready-for-agent`. Body: per
   les de route en de reden.
2. Werk in een worktree vanaf `dev`: `git worktree add -b issue-<nr>-onderhoud-<onderdeel> <pad> origin/dev`.

## 6. Rood, wijzigen, groen

Per les met route "wijziging":

1. **Rood.** Een nieuwe testfunctie in `tests/test_lessen_<onderdeel>.py` (maak het bestand aan
   als het ontbreekt; vorm: de fixtures en helpers van de bestaande tests, bijvoorbeeld
   `tests/helpers_melding.py`). Draai alleen die test: `uv run pytest
   tests/test_lessen_<onderdeel>.py::<test>`. Hij faalt, om de reden die de les noemt. Zonder
   rood bewijs weet niemand of de wijziging iets oplost.
2. **Wijzigen.** Een check of module volgt de regels van `CLAUDE.md`: elke check declareert
   `rollen` en `kenmerken` (en zo nodig `klassenlijsten`); drempels staan in `checks.toml`,
   niet in Python; GWSW is leidend.
3. **Groen.** Dezelfde test slaagt.
4. **Maximaal twee pogingen.** Niet groen na twee pogingen: draai de wijziging én de nieuwe test
   terug. De les wordt een "vraag aan de eigenaar", met de testcode in de vraag.

Blijkt het gedrag alleen op data die niet in de repo staat (`data/` is deels niet getrackt;
De Wolden-bestanden, de zware tests), dan is een rode test niet altijd mogelijk. Voer de
wijziging dan door, markeer de les als "niet bevestigd" en laat de eigenaar de meting draaien.

Na de laatste les: de `snel`-suite en de `lint`-commando's uit `.claude/cyclus.toml`, dan
eenmaal `volledig`. Geen andere test wordt rood; anders telt de veroorzakende les als
mislukte poging. Raakt de wijziging `src/**.py`, `checks/` of `uitvoer/`, noem dat in de PR:
`CLAUDE.md` vraagt daar een review naar risico.

## 7. Verdachte winst

Meld in de PR "verdacht, extra controle nodig" als één hiervan geldt:

- meer dan twee rode tests worden groen door één wijziging;
- een functie of bestand verliest meer dan een derde van zijn regels;
- de diff verwijdert een check, guard, drempel, declaratie of voorbehoudsmelding;
- het aantal bevindingen op een dataset verandert met een orde van grootte (CLAUDE.md:
  "geloof onwaarschijnlijke uitkomsten niet").

Een grote sprong komt vaker van een uitgeholde regel dan van een betere uitkomst.

## 8. Lessen bijwerken

Haal uit `docs/lessen.md` elke les met route "wijziging" (groen) of "geen wijziging". Een
"vraag aan de eigenaar" blijft staan tot het antwoord er is. Een "niet bevestigde" les blijft
staan met `(toegepast, niet bevestigd)` erachter.

## 9. Commit en PR

1. Eén commit: code, nieuwe test, `docs/lessen.md`, een regel onder `## [Unreleased]` in
   `CHANGELOG.md`, zo nodig `CLAUDE.md`-documentatie van een nieuwe functie (alleen de
   beschrijving, nooit de werkregels). Boodschap eindigt met `Closes #<nr>`.
2. `timeout 45 git push -u origin <branch>`; PR naar `dev` (niet naar `main`) met titel
   "Onderhoud lessen: <onderdeel>". Body: `Closes #<nr>`; per les route, reden en testnaam
   (rood vóór, groen na); niet bevestigde lessen (label `niet bevestigd`); verdachte winst;
   open vragen.
3. CI-keten uit `~/.claude/CLAUDE.md` (`gh run watch <id> --exit-status`).
4. Merge nooit zelf.

## Beschermd

De lus wijzigt deze nooit, ook niet als een les erom vraagt; zo'n les wordt een vraag aan de
eigenaar. De lijst staat in `.claude/cyclus.toml`, onder `[beschermd]` (`generiek` en
`domein`). Kort: het manifesto, de werkregels van `CLAUDE.md`, deze skill, de CI-workflows,
`tests/conftest.py`, elke bestaande testfunctie, en de meetlat van het domein (checkregister,
drempels in `checks.toml`, beslislog, JSON-contract, golden-bestanden, dekkingsondergrens).
Een nieuwe testfunctie in `tests/test_lessen_<onderdeel>.py` toevoegen mag.

## Harde grenzen

| Verleidelijke gedachte | Tegenargument |
|---|---|
| "De PR is klein, ik merge hem zelf." | De eigenaar merget elke PR. |
| "Deze bestaande test is te streng; ik pas hem aan." | Dat is de eigen meetlat wijzigen. Vraag aan de eigenaar. |
| "Deze drempel staat te laag; ik zet hem hoger." | Drempels zijn de meetlat. Vraag aan de eigenaar. |
| "Geen rode test, maar de fix is evident." | Zonder rood bewijs is de les "niet bevestigd". |
| "Ik neem ook de lessen van een ander onderdeel mee." | Eén run, één onderdeel. |
| "Ik push even naar `main`." | `main` draagt alleen uitgebrachte versies; PR's gaan naar `dev`. |
