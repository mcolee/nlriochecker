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

---

## Golf 3 — `dataset.py` en de structuur

- Basislijn: 35.370 bevindingen, 48 checks (de eindmeting van golf 2)
- Na de golf: 35.370, verschil 0 (+0,0 %)
- Verklaring per verschil: geen enkele check beweegt. Bij #33 zijn `bevindingen.md`
  en `bevindingen.csv` bovendien **byte-identiek** aan de basislijn.

| Issue | Tier | Uitkomst | Commit |
|---|---|---|---|
| #34 | A | afgerond en gesloten | `855c018`, `dcb37a1` |
| #36 | A | afgerond en gesloten | `43eeda6`, `a2fa5a8` |
| #33 | A | afgerond en gesloten | `744c5f9`, `ac594b9`, `b941b17` |

Alle drie raken `dataset.py`, en alle drie repareren bugs die De Wolden **per
constructie niet triggert**: nul `Putdeksel`, nul `isPartOf`, nul meervoudig
getypeerde subjecten, nul `Overstortdrempel`, nul `Ledigingsvoorziening`. Het bewijs
moest dus volledig van handgeschreven fixtures komen, en dat is ook gebeurd — telkens
rood vóór, groen na, en bij #34 en #36 door de reviewer nagespeeld in een worktree op
de vóór-commit.

**Een les die dit journaal verdient: de bewijsrichting hangt af van wat de tak doet.**
Mijn opdracht bij #34 eiste "een bevinding die er vóór de reparatie niet was". De
implementeerder duwde terug: ADM-007 en RVZ-008 zijn *onderdrukkings*takken — ze doen
`continue` zodra het onderdeel gevonden is — dus een reparatie kan er alleen
bevindingen wégnemen. Hij volgde het issue in plaats van mijn brief, en dat was juist.

### Wat de golf aan het licht bracht

**#33's premisse klopte niet.** Het issue stelt dat de engine zonder ontologie "nul
objecten toetst". Een echte `--geen-ontologie`-run op De Wolden geeft **3.396
bevindingen** (2.393 F, 1.003 W) en zet *Bekeken* op **1874** voor twaalf checks.
Oorzaak: `checks.toml` zet `put`, `streng` en `vrijvervalleiding` op abstracte wortels
— nul instanties zonder hiërarchie — maar `netwerkknopen` somt óók concrete klassen op
die de export wél direct typeert.

Het probleem is dus niet "de engine toetst niets en zegt niets", maar **"de engine
toetst een deel en zegt niet welk deel"**. Subtieler, en gevaarlijker. De markering in
het rapport draagt daarom tellingen in plaats van een absolute claim.

Die weerlegde zin stond op **tien** plekken, waaronder `README.md`, `CLAUDE.md` en de
CLI-foutmelding zelf. Allemaal opgeruimd.

**#36 betrapte het issue op een onjuist voorbeeld.** Punt 4 gebruikt `Inspectieput`
tegenover `VerdektePut` als "kies de specifiekere", maar die twee zijn in de ontologie
onvergelijkbaar (`Inspectieput` ⊂ `Rioolput` ⊂ `Put`, regel 42191/31562;
`VerdektePut` ⊂ `Put`, regel 50231). Het bronbestand waar het issue naar verwijst
schrijft er zelf boven: *"heeft extra type (rol), is niet zichtbaar vanaf maaiveld"* —
de aanleveraar bedoelt het als rol, niet als soortnaam.

**Punt 4 is daarmee maar half opgelost, en dat is onvermijdelijk.** De subsumptieregel
werkt waar klassen vergelijkbaar zijn; bij onvergelijkbare typen valt hij terug op
alfabetisch, en dan wint de rol nog steeds van het functionele type:
`{Persleiding, GeboordeLeiding}` → `GeboordeLeiding`,
`{Vuilwaterriool, Parallelriool}` → `Parallelriool`,
`{Inspectieput, BlindePut}` → `BlindePut`. De ontologie levert daar geen tiebreak
voor. Er ís een grond (`gwsw:ExtraObjecttype`, "niet-functionele objecttypering") maar
`Valput` en `Zinker` vallen daar óók onder terwijl dit project ze als volwaardige
soortnaam gebruikt — dat is een keuze voor de auteur.

**Een reparatie was smaller dan het issue beschreef.** `closure("Putdeksel")` dekt
alleen `Putdeksel` en zijn twee `_LichtVerkeer`/`_ZwaarVerkeer`-varianten. `Straatpot`
is geen subklasse maar een **zuster** onder `gwsw:Deksel` (regel 47256 tegenover
35610), net als `Drainputdeksel` en `Peilbuisdeksel`; `Rooster`, `Luik` en `Afdekplaat`
hangen onder `Afdekking`. Een put met een `Straatpot` verliest haar dekselniveau dus
nog steeds stil. Verbreden is een domeinkeuze; het gat staat nu in de docstring.

### Reviewuitkomst

Twee onafhankelijke golfreviews, geen Kritiek, en ze kwamen **onafhankelijk op dezelfde
hoofdbevinding** uit — allebei met een draaiend bewijs.

**Er zijn drie predicaten voor "kennen we de klassenhiërarchie" en ze zijn het niet
eens.** `klassenhierarchie_bekend` is `bool(self.subclasses)` (globaal), de werkelijke
terugval op geometrie wordt gestuurd door `_bruikbare_afsluiting` (per wortel), en er
is een derde in de waarheidswaarde van het `knooppunt_klassen`-argument. Eén
willekeurige `rdfs:subClassOf` zet het predicaat op `True` terwijl `of_class("Put")`
nul oplevert — en dan komt het rapport zónder voorbehoud en mét een echt oordeel. Dat
is precies de faalwijze die #33 moest sluiten, overlevend in de naad tussen #33 en #36.
**25 van de 114 fixtures zitten vandaag in die tussentoestand.**

Twee bevindingen van dezelfde soort:

- **De GeoPackage kleurt een run zonder oordeel volledig groen.** Onder
  `--geen-ontologie` vinden de checks niets, dus krijgt elk object `groen` —
  "beoordeeld en niets gevonden". De markering staat wél in `gwsw_run`, maar dat is
  een metadatatabel die niemand in QGIS openslaat.
- **`unassessable_classes` dekt de verkeerde klassenfamilie.** De drie klassen die de
  aangeleverde nulmetingen werkelijk als te globaal markeren — `Rioolstelsel`,
  `MechanischRioolstelsel`, `Overstortput` — vallen onder `Stelsel`, niet onder
  `Verbinding`. Daar geeft `of_class()` stil `[]` en scoort de poort nul, zonder een
  woord.

Alle drie zijn in de fixgolf van golf 3 verwerkt.

De fixgolf van golf 3 (`579637e`, `5cc6b2a`, `ec7b0b2`, `91cfce5`) heeft alle drie
verwerkt. Het predicaat wordt nu **afgeleid** uit dezelfde functie die de lader
gebruikt (`_bruikbare_afsluiting` over `Knooppunt` en `Verbinding`) in plaats van
opgeslagen — bewust, omdat een opgeslagen veld uit de pas kan lopen met `subclasses`
en dat vandaag al zou gebeuren in `test_uitvoer_voorbehoud._kaal()`, dat zijn kale
dataset met `replace(dataset, subclasses={})` maakt.

---

# Waar de run gestopt is

Afgebroken na golf 3, op verzoek, wegens tijd- en verbruikslimieten. **Golf 4, 5 en 6
zijn niet uitgevoerd.** Van de 26 ingeplande issues zijn er acht behandeld.

Twee sessielimieten kostten samen ruim drie uur. Belangrijker voor de planning van een
volgende run: het plan ging uit van ongeveer één ronde per issue, en de praktijk was
drie tot vier. Elke golf leverde een fixgolf op van twaalf, zestien en elf punten, en
elk van die fixgolven kreeg zelf weer een review. Dat is geen verspilling geweest —
de bevindingen waren echt, en drie ervan waren correctheidsgaten — maar het maakt de
oorspronkelijke tijdschatting onbruikbaar.

## Wat er ligt

| Issue | Uitkomst |
|---|---|
| #30 | Gesloten. Vocabulairetest plus getrackte GWSW-index; draait nu volledig in CI. |
| #28 | Gesloten. Alle 53 drempels expliciet in beide TOML's, drifttest op waarde én type. |
| #31 | Gesloten. Vijf GWSW-namen opgeruimd; twee blijven als open vraag (zie #47). |
| #32 | **Open**, tier B. Volledige meting als comment; geen enkele klassenlijst gewijzigd. |
| #11 | Gesloten. `Overnamepunt` in `afvoer_eindpunt`, BO-33 en BO-34. |
| #34 | Gesloten. `is_a()` werkt op `hasPart`-onderdelen; ADM-007 en RVZ-008 leven. |
| #36 | Gesloten. Vier latente bugs in de `hasPart`-boom; punt 4 half, zie hieronder. |
| #33 | Gesloten. Harde ontologie-eis, `--geen-ontologie`, samenstelplek voor voorbehouden. |

Vier nieuwe beslislogregels: **BO-32** (afgeleide GWSW-index in versiebeheer),
**BO-33** en **BO-34** (Overnamepunt en IT-stelsel), **BO-35** (`Metselwerk` als
tijdelijke, bewuste tolerantie).

## Wat er maandag op je bureau ligt

**Beslissingen die op jou wachten**

- **#47 — drie vragen.** `AHN5` laten staan of weghalen; `Metselwerk` als putmateriaal
  schrappen (kost **51 meldingen over 37 strengen, van 27 van de 33 putten** — niet 33,
  dat had ik eerst fout) of houden; en wanneer `Gemaal` uit `afvoer_eindpunt` gaat
  (schrappen raakt 893 objecten via de subklasse-afsluiting, niet nul).
- **#45 — 95 GWSW-klassen zonder eigen symbool.** Welke horen er een te krijgen? Let op
  BO-30: met de hele tabel krijgt de lagenboom van QGIS ruim tweehonderd legendaregels.
- **#43 — `verwachte_putmaterialen` mist negen `MateriaalPutColl`-klassen.** Een
  gemeente die netjes volgens de domeinlijst exporteert krijgt daar een valse ATTR-010.
  Hangt samen met de `Metselwerk`-vraag uit #47.
- **`beheerobjecttype` bij onvergelijkbare typen** (uit #36). De ontologie levert geen
  tiebreak; `gwsw:ExtraObjecttype` zou er een geven maar `Valput` en `Zinker` vallen er
  ook onder. Nog geen issue — staat hierboven beschreven.
- **De dekselafsluiting** (uit #36). `Straatpot`, `Rooster`, `Luik` en drie andere
  vallen buiten `closure("Putdeksel")`. Verbreden naar `Deksel` of `Afdekking` is jouw
  keuze; het gat staat in de docstring van `_deksel_kenmerk`.

**Echte fouten die nog open staan**

- **#42 — NET-007 meldt 340 van de 340 infiltratieriolen.** Zijn enige drempelklasse
  `Overstortdrempel` heeft nul instanties, dus `_knopen_met_drempel` is leeg en de
  check meldt onvoorwaardelijk. Die 340 zitten in het totaal van 35.370.
  `randvoorzieningen.py` leest voor hetzelfde probleem wél `Overstortput` plus
  `Overstortleiding`; NET-007 niet.
- **#51 — geen enkele drifttest bindt een getal.** Alle vier de bestaande drifttests
  binden een naam of een structuur. Elke onware bewering die deze run betrapte was een
  getal. Met vier voorgestelde ingrepen, van goedkoop naar duur.
- **#52 — vijf ontbrekende bewakingen**, samengevoegd uit wat eerst vijf losse issues
  waren.

**Waar de cijfers staan**

- `bevindingen.json` / `.md` / `.csv` en de GeoPackage van elke golf in `uitvoer/`
  (git-ignored): `basislijn-golf1` t/m `na-golf3` plus `eindmeting`.
- De meting van #32 als comment op dat issue, en het script plus zijn uitvoer in
  `scripts/metingen/`.
- Het volledige werkdossier — ledger met alle beslissingen, taakbriefs,
  implementeerdersrapporten en reviewuitkomsten — in
  `.superpowers/sdd/2026-08-21-weekendrun/` (git-ignored, dus alleen lokaal).

## Beslissingen die ik namens jou genomen heb

Zesendertig in totaal; ze staan alle in het ledger. De zes die er inhoudelijk toe doen:

1. **Stopvoorwaarde 3 breekt de run niet af.** Het plan zei zowel "stop bij dat issue
   en ga door" als "breek de hele run af" voor hetzelfde geval. Ik volgde de eerste.
   *Als dat fout is:* je vindt meer open issues en minder commits dan het plan beloofde.
2. **#22 telt per klasse, niet per lijst**, en het verwachte aantal is niet +1 maar wat
   de lijsten opleveren (zeven vandaag, acht na #11). Het issue is leidend boven het
   plan. Golf 4 is niet uitgevoerd, dus dit is nog niet gebouwd.
3. **Het checkregister mag wijzigen.** "Raak nooit een invoerbestand aan in `data/`"
   slaat op de aangeleverde bronbestanden; het register is jouw eigen normdocument en
   vijf issues dragen op het te wijzigen.
4. **`Metselwerk` krijgt wél een BO, `AHN5` niet.** `AHN5` is inert — geen legale export
   kan die waarde schrijven. `Metselwerk` is gedragsdragend: de regel onderdrukt
   vandaag ATTR-010 op 33 putten. Een afwijking die in werking is hoort in de beslislog.
5. **`schema_versie` blijft 1.1** ondanks het nieuwe enveloppeveld `markering`. Bumpen
   zou elke golfvergelijking ongeldig hebben gemaakt. De tegenspraak in
   `docs/json-schema.md` ligt als #52 bij jou. *Als dat fout is:* drie regels.
6. **Golf 4 draait sequentieel, geen worktrees.** Het plan stond ze toe, maar vier
   issues in die golf raken het checkregister en alle acht dezelfde CHANGELOG-sectie.
   Niet meer relevant nu golf 4 niet gedraaid is.

## Twee dingen die ik zelf fout deed

**Ik sloot #31 en #11 terwijl de code er nog naar verwees als open vraag.** Daarmee
stonden drie punten in twee toestanden, wat `CLAUDE.md` uitdrukkelijk verbiedt.
Rechtgezet met #47, maar dat issue had niet hoeven bestaan.

**Ik gaf elke bevinding een eigen issue.** De lijst groeide van 28 naar 34 voordat ik
hem terugbracht naar 30 door vijf samen te voegen. Een bevinding in het journaal is
ook zichtbaar; niet alles hoeft een ticket.
