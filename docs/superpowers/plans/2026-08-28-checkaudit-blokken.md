# Uitvoeringsplan checkaudit-issues: negen blokken, één blok per sessie

Vervolg op `2026-08-22-issuevolgorde.md`; de **Regels voor elke sessie** daaruit blijven
gelden, met één wijziging: de eenheid is nu een **blok** van 1–4 samenhangende issues in
plaats van één issue. Peildatum 2026-08-28; de 23 issues #80–#102 uit de checkaudit-
besluitronde (hub #79).

## Blokregels (bovenop de sessieregels van 22-08)

1. **Binnen een blok strikt sequentieel**, in de volgorde hieronder — blokgenoten delen
   bestanden. Per issue: TDD, mechanische poort, commit, issue sluiten met commitverwijzing.
2. **Eén review per blok**, na het laatste issue, op het zwaarste niveau dat in het blok
   voorkomt (meting 26-08: een review per klein issue levert dubbele poorten en niets op).
   Verwerk bevindingen, draai de poort opnieuw, commit.
3. **Eén hermeting per blok**: de richtgetallen uit alle issues van het blok in één
   De Wolden-run controleren; het resultaat als comment op elk gesloten issue van het blok.
4. **Vóór de push** die datatests raakt: `uv run python scripts/runnerpoort.py`; daarna
   push en `gh run watch` op de eigen commit.
5. **Afsluiten van de sessie**: kort verslag + de startprompt van het volgende blok, zodat
   de auteur na `/clear` alleen die prompt hoeft te plakken.

## De blokken, in volgorde

| Blok | Issues | Samenhang | Reviewzwaarte blok |
|---|---|---|---|
| A | #81, #90, #95 | Schrapronde: drie keer hetzelfde recept (check weg, BO, register) | Klein |
| B | #83, #94, #99 | Alle drie in `checks/extern.py` + config; #83 let op de GPKG-vlakkoppeling | Substantieel (#94) |
| C | #82 → #100 | Zelfde checks (TOP-006/010/011): eerst de scope, dan de drempels; één hermeting | Substantieel (#82) |
| D | #85 → #89 → #88 | Topologie-structuur: dedup eerst (verandert de populatie van de rest), dan hulpstuk-eindobject, dan TOP-019-herleiding | Substantieel (#85) |
| E | #84, #92, #93, #96 | Kleine tekst- en declaratie-issues, disjuncte bestanden | Substantieel (#84, RVZ-001-index) |
| F | #91, #98, #101 | Uitvoer en publieke contracten: rapportkop, GPKG-lagen, nulmeting-teksten; één schema-/contractbump | Altijd Substantieel |
| G | #86 | ATTR-001 drains: begint met research (bron vastleggen in BO), dan het drempelrecept | Substantieel |
| H | #80 | Het richtingscluster — het grootste issue, alleen | Substantieel |
| I | #97, #102 | Beide geblokkeerd door #80, beide `checks/netwerk.py`, beide richting-bewust | Substantieel |

Volgorde-rationale: A–B halen de vervallen checks en kleine scopes eerst weg (minder
meldingsruis in elke latere hermeting); C–D herstellen de topologie-populaties; E–G zijn
onafhankelijk invulwerk; H als laatste grote klus, en I kan pas daarna (native
`blocked by`-dependencies op GitHub).

## Slotrun (eigen korte sessie, na blok I)

Eén volledige `toets`-run met de vlaggen van de audit (`docs/checks-audit-2026-08.md`,
sectie "De volle run"), alle richtgetallen uit #80–#102 naast de uitkomst leggen, en het
totaalverslag als comment op #79. Afwijkingen zijn een bevinding voor de auteur, geen
reden om zelf bij te sturen.

## Startprompts

Per blok, na `/clear`:

```
Los blok <letter> (issues <nummers>) op volgens docs/superpowers/plans/2026-08-28-checkaudit-blokken.md
```

Eerste: `Los blok A (issues #81, #90, #95) op volgens docs/superpowers/plans/2026-08-28-checkaudit-blokken.md`
