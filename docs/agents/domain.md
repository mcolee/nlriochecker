# Domeindocumentatie

Hoe de engineering-skills de domeindocumentatie van dit repo lezen bij het verkennen van
de codebase.

## Lees dit voordat je gaat verkennen

- **`CONTEXT.md`** in de root van het repo, of
- **`CONTEXT-MAP.md`** in de root, als die bestaat — die wijst naar een `CONTEXT.md` per
  context. Lees elke context die het onderwerp raakt.
- **`docs/adr/`** — lees de ADR's die het gebied raken waarin je gaat werken. In een
  repo met meerdere contexten ook `src/<context>/docs/adr/` voor contextgebonden
  besluiten.

Bestaat een van deze bestanden niet, ga dan **stilzwijgend** verder. Meld het gemis niet
en stel niet voor ze vooraf aan te maken. De skill `/domain-modeling` (bereikbaar via
`/grill-with-docs` en `/improve-codebase-architecture`) maakt ze aan op het moment dat er
echt een begrip of besluit wordt vastgelegd.

Voor dit repo geldt bovendien: de bestaande beslissingen staan in `docs/beslislog.md`
(BO-nummers) en de domeinregels in `CLAUDE.md`. Raadpleeg die net zo goed.

## Bestandsindeling

Repo met een enkele context (zoals dit repo):

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-gebeurtenisgestuurde-orders.md
│   └── 0002-postgres-voor-het-schrijfmodel.md
└── src/
```

Repo met meerdere contexten (herkenbaar aan `CONTEXT-MAP.md` in de root):

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← systeembrede besluiten
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← contextgebonden besluiten
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## Gebruik het vocabulaire van de glossary

Noemt je uitvoer een domeinbegrip (in een issuetitel, een refactorvoorstel, een hypothese,
een testnaam), gebruik dan de term zoals `CONTEXT.md` hem definieert. Wijk niet uit naar
synoniemen die de glossary juist vermijdt.

Staat het begrip dat je nodig hebt nog niet in de glossary, dan is dat een signaal: of je
verzint taal die het project niet voert (heroverweeg), of er is een echt gat (noteer het
voor `/domain-modeling`).

## Meld strijd met een ADR

Spreekt je uitvoer een bestaande ADR tegen, benoem dat dan expliciet in plaats van hem
stilzwijgend te overrulen:

> _Strijdig met ADR-0007 (gebeurtenisgestuurde orders) — maar het is het heropenen waard omdat…_
