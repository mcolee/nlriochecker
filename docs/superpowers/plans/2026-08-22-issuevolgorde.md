# Volgordeplan: alle open issues, één per sessie

Vervangt de golvenaanpak. Eén issue per sessie, `/clear` ertussen, geen parallelle
sporen. Peildatum 2026-08-22; 26 open issues.

## Regels voor elke sessie

1. **Eén issue, volledig af.** Niet beginnen aan het volgende.
2. **Geen nieuwe issues aanmaken.** Nooit `gh issue create`. Een nevenbevinding
   komt als één regel in het sessieverslag aan Martin; hij beslist.
3. **Karpathy-regels uit CLAUDE.md**: aannames expliciet, minimale code, chirurgisch,
   verifieerbaar doel vooraf.
4. **Skillvolgorde per sessie:**
   - lees het issue via `gh issue list --json` (nooit `gh issue view`, dat faalt);
   - `superpowers:brainstorming` bij ontwerpruimte, `superpowers:systematic-debugging`
     bij een bug;
   - `superpowers:test-driven-development`: eerst de falende test;
   - vóór commit: `/superpowers:requesting-code-review` én
     `/python-library-complete:reviewing-python-libraries`, bevindingen verwerken;
   - `superpowers:verification-before-completion`: ruff, mypy, pytest draaien en de
     uitkomst tonen, geen claims zonder bewijs.
5. **Afronden**: CHANGELOG-regel onder Unreleased, commit op `dev`, issue sluiten met
   een korte verwijzing naar de commit. Beknopt verslag: wat gedaan, wat bewust niet.
6. **Startprompt volgende sessie**: `Los issue #N op volgens
   docs/superpowers/plans/2026-08-22-issuevolgorde.md`.

## Volgorde

### Blok A — bugs die het rapport nu vervuilen

Valse bevindingen eerst: elke run die daarna ter controle draait, leest schoner.

| # | Issue | Waarom hier |
|---|-------|-------------|
| 1 | #42 | NET-007 meldt 100% van de infiltratieriolen — grootste vervuiler |
| 2 | #29 | HGT-007-norm raakt vrijwel alles wat volgens RIONED normaal is |
| 3 | #35 | 448 ATTR-008-gevallen waar de ontologie onze drempel tegenspreekt; GWSW is leidend |
| 4 | #19 | ATTR-001 telt twee verschillende problemen als één getal |
| 5 | #53 | lege rollijst zet de rol maar half uit |
| 6 | #56 | twee klassenlijsten doen iets anders dan ze zeggen |
| 7 | #37 | WIBONThema hasValue waar hasReference hoort; SHACL ziet het niet |

### Blok B — vangnetten

Voorkomt dat het patroon uit de weekendrun (onbewaakte waarheden, onware getallen)
terugkomt voordat de rest van het werk begint.

| # | Issue | Waarom hier |
|---|-------|-------------|
| 8 | #52 | vijf ontbrekende bewakingen plus tegenstrijdige documentatie |
| 9 | #51 | drifttests die getallen binden — elke betrapte onwaarheid was er een |
| 10 | #22 | tel de klassen waar checks van afhangen, waarschuw bij nul (generalisatie van de oorzaak van #42) |
| 11 | #55 | symbolen-drifttest en vier wortelklassen zonder symbool |
| 12 | #7 | dekkingclaims aan de juiste CFK toeschrijven (documentatie) |

### Tussenstap — geen agentsessie

**#47** (needs-info): drie auteursvragen — AHN5, Metselwerk, Gemaal in
`afvoer_eindpunt`. Alleen Martin kan die beantwoorden. De antwoorden ontgrendelen
#20 en de Gemaal-keuze die #23 raakt. Beantwoorden vóór blok C is het handigst,
maar alleen #20 en #23 wachten erop.

### Blok C — rapportage en bestaande checks verdiepen

| # | Issue | Waarom hier |
|---|-------|-------------|
| 13 | #21 | 28,7% zonder Begindatum, nergens gemeld — stilte leest als gecontroleerd |
| 14 | #54 | dekkingsgraad: ondergrens en vindbaar commando |
| 15 | #20 | plausibiliteit.toml onderbouwen (na #47) |
| 16 | #39 | VormPut lezen; 88 ronde putten met breedte ≠ lengte |
| 17 | #38 | wandruwheid: 962 PE-leidingen met de betonwaarde |

### Blok D — grotere features

Elk een eigen ontwerpstap (`superpowers:writing-plans`) binnen de sessie.

| # | Issue | Waarom hier |
|---|-------|-------------|
| 18 | #17 | stelselhiërarchie uit de export lezen; daarna de NET-007-afleiding herzien (BO-34) |
| 19 | #23 | RVZ-006 uitbreiden met afvoereindpunt (na de Gemaal-vraag uit #47) |
| 20 | #18 | afvoerpad naar benedenstrooms eindpunt, NET-009 |
| 21 | #25 | stelselvlakken als GeoPackage-laag |
| 22 | #40 | EXT-009 straatnaam tegen BGT/NWB |

### Blok E — prestaties

| # | Issue | Waarom hier |
|---|-------|-------------|
| 23 | #26 | pyoxigraph: nieuwe afhankelijkheid, dus eerst het BO-3-besluit aan Martin voorleggen; benchmark en equivalentie-eis staan in het issue |

### Voor de mens, geen agentsessie

- **#41** (ready-for-human): dekkingsanalyse omkeren.
- **#32** (ready-for-human): klassenlijsten tegen de volledige ontologie.
- **#47** (needs-info): zie tussenstap.

## Onderbouwing van de volgorde

- **Bugs vóór vangnetten**: een drifttest die een vervuild getal vastlegt, bewaakt
  de verkeerde waarheid.
- **Vangnetten vóór nieuw werk**: blok C en D voegen precies het soort beweringen
  toe dat in de weekendrun onbewaakt bleek; met #51 en #52 eerst worden die vanaf
  het begin gebonden.
- **#22 direct na #42**: hetzelfde gat (een lege klassenselectie die stil niets
  toetst), eerst het concrete geval, dan de generieke bewaking.
- **#17 vóór #23/#18**: wie de stelselhiërarchie leest, verandert waar de
  netwerkchecks hun stelseltype vandaan halen; dat eerst leggen scheelt herwerk.
- **#26 laatst**: prestaties raken geen uitkomst, en het profiel van 2026-08-22
  ligt er al als meetbasis.
