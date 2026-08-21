# Runjournaal — onbeheerde weekendrun van 2026-08-21

Uitgevoerd volgens `docs/superpowers/plans/2026-08-21-weekendrun.md` met
`superpowers:subagent-driven-development`. Zes golven, één gedeelde basislijnmeting
per golf, harde stopvoorwaarden.

De basislijn draait zonder `--shacl` en zonder `--bronnen`, precies zoals het plan
het commando geeft: het totaal telt dus alleen de eigen checks, niet de ruim
105.000 nulmetingmeldingen en niet de EXT-checks. Twee correcties op het
plancommando: de CLI kent `--projectconfig` en `--output`, niet `--config` en
`--uitvoer`.

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --projectconfig configs/dewoldenhoogeveen.toml \
  --output uitvoer/<naam>
```

---

<!-- Per golf komt hier één sectie bij, aan het eind van die golf geschreven. -->
## Golf 1 — Fundament

- Basislijn: 35.370 bevindingen, 48 checks met bevindingen
- Na de golf: 35.370, verschil 0 (+0,0 %)
- Verklaring per verschil: geen enkele check beweegt. Beide issues waren
  gedragsneutraal en dat is gemeten, niet aangenomen.

| Issue | Tier | Uitkomst | Commit |
|---|---|---|---|
| #30 | A | afgerond en gesloten | `0996609`, `425892b`, `8d03927`, `99b91cf` |
| #28 | A | afgerond en gesloten | `19139fd`, `abe713a` |
| — | — | fixgolf op de twee golfreviews | `ad3bb0f` |

**#30 — GWSW-vocabulairetest.** De test vindt **zeven** schendende termen, niet zes
zoals het plan aannam: `AHN5`, `Interneoverstortput`, `Kunststof`, `Metselwerk`,
`Muilprofiel`, `Vacuumgemaal`, `Verholengoot`. Ze staan met hun reden op
`BEKENDE_AFWIJKINGEN`, en die lijst valt in beide richtingen — een opgeruimde term
die blijft staan is net zo rood als een nieuwe fout.

Het plan vroeg om "een falende test" terwijl de projectpoort een groene `pytest`
eist vóór elke commit. Dat kan niet allebei. Opgelost door de rode toestand als
*data* vast te leggen in plaats van als testuitkomst: de zeven termen staan
letterlijk in de commit, en het bewijs dat de test rood wordt is een run met een
lege lijst, vastgelegd in het rapport en niet gecommit.

**Het CI-gat en hoe het alsnog dicht ging.** Zoals eerst gebouwd sloeg de test op
de GitHub-runner 140 van de 142 gevallen over, omdat `data/` niet in versiebeheer
zit — een test die "in CI" heet maar daar niets afdwingt. Repareren leek een
herdistributievraag over GWSW-data en dus een auteursbeslissing. **De auteur
meldde tijdens de run dat de GWSW-ontologie onder CC0 staat**
(https://stichtingrioned.github.io/GWSW_Ontologie_RDF/), waarmee dat bezwaar
verviel: `data/*` staat in `.gitignore` vanwege bestandsgrootte, niet vanwege
licentie. Er is nu een afgeleide index `data/gwsw-vocabulaire-index.json` in
versiebeheer, met `scripts/maak_gwsw_index.py` om hem te regenereren en een
drifttest die hem tegen een vers geparseerde ontologie houdt. Op een schone kloon
zonder `data/` draaien nu **136 van de 144 gevallen** waar dat er 2 waren. Het
besluit staat als **BO-32** in de beslislog.

**#28 — alle 53 drempels expliciet.** In `checks.toml` én
`configs/dewoldenhoogeveen.toml`, want dat laatste bestand is een volledige kopie
en een gedeeltelijke zou stil op de Python-defaults terugvallen. Geen waarde is
inhoudelijk verschoven; dat is mechanisch bewezen en door de reviewer onafhankelijk
opnieuw opgebouwd (53 sleutels, geen ontbrekende, geen extra, geen waarde- of
typeverschil, ook niet via int/float-coërcie).

Eén claim moest terug: bij TOP-009 stond dat de RD-grenzen "het officiele
geldigheidsbereik van het Rijksdriehoeksstelsel" zijn. Dat is niet zo — de vier
waarden 0 / 300.000 / 300.000 / 630.000 zijn een afgeronde omhullende om Nederland
en alleen `rd_x_max` valt toevallig samen met iets gepubliceerds. Nu weer
"projectkeuze, geen externe bron".

**Reviewuitkomst.** Twee onafhankelijke golfreviews, geen Kritiek, en de
nul-gedragsverandering door beide nagerekend op de paden die de gemeten run niet
raakt (EXT, HGT-001 t/m 003, nulmeting). Twaalf punten zijn in `ad3bb0f` verwerkt.
De twee zwaarste kwamen bij allebei onafhankelijk boven:

1. **De vocabulairetest kon stil groen worden.** Zijn zelfgarantie putte uit
   `symbolen.py`, `plausibiliteit.toml` en de AST-sweep, maar uit géén van beide
   TOML-configuraties — 126 van de 278 termen onbewaakt. Nu heeft elke termenbron
   een eigen sentinel (19 disjuncte prefixen), en het weglaten van één bron maakt
   de module aantoonbaar rood.
2. **De drempeldrifttest bond namen maar geen waarden.** Er ontstonden drie
   kopieën van 53 getallen die stil uiteen konden lopen. Nu wordt waarde én type
   afgedwongen tegen `CheckThresholds()`, met voor de projectconfiguratie een
   expliciete, vandaag lege `BEWUSTE_AFWIJKINGEN`.

Verder: `BEKENDE_AFWIJKINGEN` is nu op `(naam, collectie)` gesleuteld in plaats van
op naam, er is een bovengrens op het aantal overgeslagen tests bijgekomen naast de
ondergrens op geslaagde (die was in deze golf al voor de tweede keer tandeloos
geworden), en de symbolentabeldekkingstest is er alsnog gekomen — niet als lijst
van 117 "bewuste weglatingen", maar als drifttest die afgaat zodra het gat groeit.
Dat vergde `subklasse_van` in de index (196 → 284 kB), wat als noodzakelijk
bevestigd is.

---

## Golf 2 — Naam- en configreparaties

- Basislijn: 35.370 bevindingen, 48 checks (de eindmeting van golf 1)
- Na de golf: 35.370, verschil 0 (+0,0 %)
- Verklaring per verschil: geen enkele check beweegt.

| Issue | Tier | Uitkomst | Commit |
|---|---|---|---|
| #31 | A | afgerond en gesloten | `82e9560` |
| #32 | B | gemeten, open gelaten — zie comment | `c4508b2`, `0101f30` |
| #11 | A | afgerond en gesloten | `85f5159`, `0f7e936` |

**#31 — vijf van de zeven namen opgeruimd.** `Muilprofiel` → `Muil`,
`Interneoverstortput` → `InterneOverstortput`, `Verholengoot` → `VerholenGoot`,
`Kunststof` als putmateriaal weg, en de `Vacuumgemaal`-symboolrij verwijderd. Dat
laatste omdat de ontologie "Vacuümgemaal" als `skos:altLabel` van het al aanwezige
`Vacuumpompstation` draagt — de rij was een synoniem van een bestaande rij, en er
bestaat geen `gwsw:Vacuumgemaal`, dus geen dataset kan die waarde dragen. Elke
vervangende naam is door de reviewer zelf in de ontologie geverifieerd, met
regelnummer.

**#32 — bijna overal nul.** Op één na komt elke voorgestelde uitbreiding van de
klassenlijsten op **nul** objecten uit; de enige uitzondering is één
`Bergbezinkleiding`, een klasse die het issue zelf niet noemt. Twaalf nullen is
precies het soort uitkomst dat verdacht hoort te zijn — een kapotte teller geeft
ook nul — dus de meting is drievoudig geijkt en daarna door de reviewer met een
eigen, onafhankelijk geschreven scan gereproduceerd. Ze klopt.

De uitzondering die het plan toestond (nul-rakende punten alvast doorvoeren) is
**niet** gebruikt: elke nul-klasse die je nu toevoegt wordt in golf 4 een extra
systemische waarschuwing van #22, en dat zou die meting onleesbaar maken.

**Vier stellingen in de issuetekst van #32 blijken onjuist**, alle vier bevestigd:
vijf van de acht klassen bij punt 7c zitten al in de afsluiting, punt 3 heeft
negen gaten en niet zes, `Beekriool` is een subklasse van `Overkluizing`, en —
de zwaarste — **`klassen.mechanisch` filtert geen enkele check maar bepaalt alleen
de kaartkleur**. Punt 1 van dat issue is daarmee een consistentiegat, geen
gedragsgat.

**#11 — het noodverband vastgelegd.** `Overnamepunt` (ontologie regel 31892,
`subClassOf gwsw:Aansluitpunt`) en de vier IT-stelselklassen bestaan wél; De Wolden
levert er nul instanties van. Dat onderscheid — een gat in ons model tegenover een
gat in de aanlevering — is de fout die dit issue repareert, en het staat nu in
BO-33 en BO-34 met ontologiebewijs en regelnummer. Dezelfde onjuiste bewering liep
nog rond in een docstring van NET-007 en in een zin van het checkregister; beide
zijn mee rechtgezet.

BO-34 moest na de review herschreven worden. Hij motiveerde het uitstel van
NET-007 met "die twee lezingen kunnen uiteenlopen zonder dat we weten welke gelijk
heeft", en dat is aantoonbaar onwaar: alle 340 infiltratieriolen zitten in de 13
`Infiltratiestelsel`-`hasPart`-bomen, nul erbuiten. Het besluit blijft, de reden is
vervangen door de reden die wél klopt — de engine leest de stelselboom nergens
(#17).

**Reviewuitkomst.** Alle drie de taken schoon afgesloten na één fixronde elk. De
belangrijkste vondst kwam uit de review van #11 en valt buiten alle drie de
issues: zie "Wat er maandag ligt".
