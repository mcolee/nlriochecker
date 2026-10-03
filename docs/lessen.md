# Lessen per onderdeel

Begrensde zelfverbetering (principe 9 (voorstel) van `manifesto.md`): corrigeert de eigenaar een
uitkomst van de repo of van de agent, dan schrijft de agent hier een les. Ook als de fout
meteen gerepareerd is. De skill `onderhoud` (`.claude/skills/onderhoud/SKILL.md`) verwerkt de
lessen van één onderdeel tot één issue, één branch en één PR. De eigenaar merget.

Onderdeel = één kop hieronder: een CLI-subcommando (`analyseer`, `dekking`, `vergelijk`,
`toets`), een module van `src/nlriochecker/` (`checks`, `uitvoer`, `shaclrapport`,
`externedata`, `afbakening`, `studiegebied`) of `agent` (werkwijze van de agent). Maak de kop
aan als hij ontbreekt.

Vorm, nieuwste les bovenaan onder de kop:

```text
- <jjjj-mm-dd> · Fout: <wat de repo of agent deed>. Correctie: <wat de eigenaar wilde>.
  Bron: <sessie-id, issue of commit>.
```

Een verwerkte les verdwijnt hier; de PR en de test in `tests/test_lessen_<onderdeel>.py`
bewaren hem. Geen persoonsgegevens in een les.

## analyseer

## dekking

## vergelijk

## toets

## checks

## uitvoer

## shaclrapport

## externedata

## afbakening

## studiegebied

## agent
