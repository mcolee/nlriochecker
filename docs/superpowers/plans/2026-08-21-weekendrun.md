# Weekendrun: 28 issues autonoom afhandelen — Implementatieplan

> **Voor agentische uitvoerders:** VERPLICHTE SUB-SKILL: gebruik
> `superpowers:subagent-driven-development` om dit plan golf voor golf uit te voeren.
> Stappen gebruiken checkbox-syntaxis (`- [ ]`) voor het bijhouden.

**Doel:** In één onbeheerde run zestien volledig gespecificeerde issues afmaken en committen,
tien issues tot een meting brengen die maandag een beslissing mogelijk maakt, en twee issues
bewust laten liggen — zonder dat er ook maar één domeinkeuze door een agent wordt gemaakt.

**Aanpak:** Zes sequentiële golven, gegroepeerd op bestandslocaliteit en afhankelijkheid. Eén
gedeelde basislijnmeting per golf in plaats van per issue. Harde stopvoorwaarden die de hele
run afbreken. Drie sporen van navolgbaarheid: één commit per issue, een comment op elk issue,
en een runjournaal.

**Techniek:** Python 3.12+, uv, pytest, ruff, mypy, rdflib, `gh` CLI.

**Spec:** De GitHub-issues op `mcolee/nlriochecker` zijn de specificatie. Elk issue draagt zijn
eigen bestandspaden, verwachte aantallen, verificatiecriteria en waar van toepassing een
stopregel. **Lees het issue voordat je eraan begint** — dit plan herhaalt de inhoud niet, het
regelt alleen volgorde, meetprotocol en grenzen.

```bash
gh issue list --state open --limit 50 \
  --json number,title,body,labels \
  --jq '.[] | {number, title, labels: [.labels[].name]}'
gh issue list --state open --limit 50 --json number,body \
  --jq '.[] | select(.number==NN) | .body'
```

Let op: `gh issue view` faalt in deze omgeving. Gebruik altijd `gh issue list --json`.

---

## Global Constraints

Deze gelden voor élke taak in dit plan. Ze komen uit `CLAUDE.md` en uit zes expliciete
besluiten van de auteur op 2026-08-21.

- **Werk op `dev`.** Niets naar `main`, geen tags, geen `scripts/uitgave.py`.
- **GWSW is leidend.** Bestaat een begrip in `data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl`,
  dan bestaat het — ongeacht wat een externe bron zegt. Grep die ontologie voordat je beweert
  dat iets niet bestaat. Let op inconsistent hoofdlettergebruik: `Vuilwaterstelsel` heeft een
  kleine s waar `GemengdStelsel` een hoofdletter heeft. Leidende versie: **GWSW 1.6**.
- **Geen enkele domeinbeslissing.** Komt een issue uit op een keuze die niet in het issue
  staat, dan stop je bij dat issue, schrijf je de vraag als comment, en ga je door met het
  volgende. Je verzint geen drempel, geen jaartal en geen klassenlijst.
- **Geloof onwaarschijnlijke uitkomsten niet.** Duizenden bevindingen wijzen op een
  modelleerfout, niet op duizenden gebreken.
- **Codekwaliteit per golf, niet per commit.** `uv run ruff check`, `uv run ruff format
  --check`, `uv run mypy` en `uv run pytest` draaien vóór élke commit. De twee reviewskills
  (`/superpowers:requesting-code-review` en
  `/python-library-complete:reviewing-python-libraries`) draaien **één keer per golf**, aan het
  eind, over de hele golf. Dit is een bewuste afwijking van `CLAUDE.md`, goedgekeurd door de
  auteur, en hij geldt alleen voor deze run.
- **CHANGELOG.** Elke noemenswaardige wijziging krijgt een regel onder `## [Unreleased]` in
  `CHANGELOG.md`.
- **Afbreekdrempel: 5 %.** Beweegt het totaal aantal bevindingen op De Wolden met meer dan
  vijf procent zonder dat het issue die beweging voorspelde, dan breekt de **hele run** af.
- **`uitvoer/` staat in `.gitignore`.** Schrijf runuitvoer daarheen, niet in `docs/` of `data/`.
- **Raak nooit een invoerbestand aan** in `data/`.

---

## Meetprotocol — lees dit vóór golf 1

Dit is de kern van het plan. Zonder dit protocol kost verificatie uren en gaat de cache
voortdurend stuk.

### De basislijn

Aan het begin van elke golf één run die de referentie vastlegt:

```bash
uv run nlriochecker toets \
  --dataset data/gwsw_orox_ttl/dewolden_orox.ttl \
  --ontologie data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl \
  --config configs/dewoldenhoogeveen.toml \
  --uitvoer uitvoer/basislijn-golf<N>
```

Koud kost dit ongeveer 3,5 minuut en 3 GB geheugen; warm ongeveer 48 seconden. **De
cachesleutel bevat de broncode van `dataset.py` en `geometry.py`** (`cache.py:132-134`), dus
elke wijziging daarin maakt de volgende run weer koud. Dat is de reden dat golf 3 alle
`dataset.py`-issues bundelt.

Aan het eind van de golf dezelfde run naar `uitvoer/na-golf<N>`, en dan:

```bash
uv run python - <<'PY'
import json, pathlib
def tel(p):
    d = json.loads(pathlib.Path(p).read_text())
    m = d["meldingen"]
    per = {}
    for x in m:
        per[x["check_id"]] = per.get(x["check_id"], 0) + 1
    return len(m), per
voor, pv = tel("uitvoer/basislijn-golfN/bevindingen.json")
na,   pn = tel("uitvoer/na-golfN/bevindingen.json")
print(f"totaal: {voor} -> {na}  ({(na-voor)/max(voor,1)*100:+.1f}%)")
for k in sorted(set(pv) | set(pn)):
    a, b = pv.get(k, 0), pn.get(k, 0)
    if a != b:
        print(f"  {k}: {a} -> {b}")
PY
```

Controleer het veld `schema_versie` in beide bestanden voordat je vergelijkt; wijkt het af,
dan is de vergelijking ongeldig en meld je dat.

**Elk issue dat "geen gedragsverandering" claimt, wordt door deze ene vergelijking bewezen.**
Draai geen eigen volledige run per issue. Fixture-tests draai je wél per issue.

### Wat je met de uitkomst doet

- Nul verschil terwijl het issue nul voorspelde: goed, noteren, door.
- Verschil dat het issue exact voorspelde (#39 verwacht 88, #37 verwacht 1, #38 verwacht ±962):
  goed, noteren, door.
- Elk ander verschil: **stop de run**, journaal bijwerken, laatste werkende staat committen.

---

## Tierindeling

| Tier | Betekenis | Issues |
|---|---|---|
| **A** — afmaken en committen | Geen gedragsverandering, óf een gedragsverandering met een exact voorspeld aantal dat je zelf kunt verifiëren. Issue sluiten. | 4, 7, 11, 18 (alleen fase 1), 22, 23, 24, 27, 28, 30, 31, 33, 34, 36, 37, 39 |
| **B** — meten en stoppen | Het issue draagt een poort. Schrijf de meetcode, draai hem, zet de cijfers als comment, commit de meting, **laat het issue open**. | 17 (alleen fase 1), 19, 20, 21, 29, 32, 35, 38, 40, 41 |
| **C** — niet aanraken | Buiten scope van deze run. | 25, 26 |

**#26 (pyoxigraph)** wordt overgeslagen: een nieuwe afhankelijkheid plus een equivalentiebewijs
op een 3,5-minutenload is niets voor onbeheerd werk. **#25** is hoe dan ook geblokkeerd door
#17 en #18, die in deze run alleen hun fase 1 krijgen.

**Tier B sluit niet.** Dat is geen halve opbrengst: de auteur komt terug bij metingen in plaats
van bij gokken.

---

## Golf 1 — Fundament

**Basislijn:** `uitvoer/basislijn-golf1` (koud, ~3,5 min).

**Issues, in deze volgorde:**

- [ ] **#30 — GWSW-vocabulairetest in CI** (tier A)
  Bouw de test **vóór** #31. Hij moet aantoonbaar rood worden op de zes namen die #31
  repareert; dat is het bewijs dat de test werkt. Het issue draagt een uitgewerkt ontwerp in
  een comment: waar de termenlijst vandaan komt zonder duplicatie, de AST-sweep, de
  session-fixture van 3,7 s, en drie bronnen van vals alarm die je moet uitsluiten
  (`dekking.toml`, deelmodelverschil, hoofdletterafwijking).
  **Lever op:** een falende test plus een groene testrun voor alles behalve die zes termen.

- [ ] **#28 — Alle drempels expliciet in `checks.toml`** (tier A)
  Puur zichtbaarheid, geen gedragsverandering. `extra="forbid"` staat al aan, dus een tikfout
  faalt hard. Voeg de drifttest toe die afdwingt dat elk veld van `CheckThresholds` in
  `checks.toml` voorkomt.

**Waarom deze volgorde:** #30 vindt de fouten die golf 2 repareert, en #28 maakt de drempels
zichtbaar die golf 5 gaat meten.

**Afsluiting van de golf:**
- [ ] `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest`
- [ ] Run naar `uitvoer/na-golf1`, vergelijk met de basislijn. **Verwacht: nul verschil.**
- [ ] `/superpowers:requesting-code-review` over de golf
- [ ] `/python-library-complete:reviewing-python-libraries` over de golf
- [ ] Journaalregel schrijven (zie *Journaal* onderaan)

---

## Golf 2 — Naam- en configreparaties

**Basislijn:** `uitvoer/basislijn-golf2`.

Deze drie raken allemaal `checks.toml` en `plausibiliteit.toml`. **Doe ze sequentieel**, niet
parallel, ook niet in worktrees.

- [ ] **#31 — Zes GWSW-namen bestaan niet** (tier A)
  `Muilprofiel` → `Muil`, `Vacuumgemaal` verwijderen of vervangen, `Kunststof` als putmateriaal
  weg, `AHN5` bewust laten of weghalen, twee hoofdletterafwijkingen. De test uit #30 moet
  hierna groen worden.
  **Verwacht op De Wolden: nul verandering** (geen `Muil` in de dataset).

- [ ] **#32 — Klassenlijsten dekken de ontologie niet** (tier B — **alleen meten**)
  Dit issue verplaatst leidingen tussen mechanisch en vrijverval en verandert dus gedrag. Meet
  per punt hoeveel objecten van categorie zouden veranderen, zet dat als comment, **wijzig
  niets.** De punten die op De Wolden nul objecten raken mag je wél doorvoeren; die zijn per
  definitie gedragsneutraal — noteer expliciet welke dat waren.

- [ ] **#11 — Overnamepunt en IT-stelsel: noodverband vastleggen** (tier A)
  Twee BO-nummers in `docs/beslislog.md`, de onjuiste commentaren in `checks.toml` corrigeren,
  `Overnamepunt` toevoegen aan `afvoer_eindpunt`.
  **Verwacht: nul verandering** (nul instanties in de dataset).
  De restvraag "wanneer gaat `Gemaal` eruit" beantwoord je **niet**; die staat als open vraag
  in het issue en blijft daar.

**Afsluiting:** zelfde vijf stappen als golf 1. Verwacht verschil: **nul**.

---

## Golf 3 — `dataset.py` en de structuur

**Basislijn:** `uitvoer/basislijn-golf3`.

Alle drie raken `dataset.py`. **Sequentieel**, en samen kosten ze één cache-invalidatie in
plaats van drie. Reken op koude runs in deze golf.

- [ ] **#34 — `is_a()` faalt op `hasPart`-onderdelen** (tier A)
  Twee dode checktakken: ADM-007 en RVZ-008. `administratief.py:442-445` laat zien hoe het wél
  moet. Fixtures met een ingebouwde `Overstortdrempel` en een geregistreerde
  `Ledigingsvoorziening` zijn verplicht — die bewijzen dat de tak leeft.
  **Verwacht: nul verandering** (nul instanties van beide klassen in De Wolden).

- [ ] **#36 — Klimmen door de `hasPart`-boom** (tier A)
  Vier latente bugs: exacte typematch op `deksel_klassen`, één willekeurige houder in
  `_parent`, geen inverse properties, alfabetische `beheerobjecttype`. Volgorde op impact staat
  in het issue.
  **Verwacht: nul verandering.**

- [ ] **#33 — Zonder ontologie toetst de engine nul objecten** (tier A)
  Hard falen plus `--geen-ontologie` als ontsnappingsvlag. De body draagt vijf uitgewerkte
  stappen en is niet meer open. **Let op stap 3:** de runbrede markering wordt nu door precies
  één bron gevoed; een deelset-run zónder ontologie draagt er twee, dus er moet een
  samenstelplek komen. De test daarop is verplicht.
  **Verwacht mét ontologie: nul verandering.**

**Afsluiting:** zelfde vijf stappen. Verwacht verschil: **nul**.

---

## Golf 4 — Uitvoer, tellingen en redactie

**Basislijn:** `uitvoer/basislijn-golf4`.

Deze acht zijn grotendeels onafhankelijk. **Hier mag je `superpowers:using-git-worktrees`
inzetten** voor parallelle uitvoering — maar #22 en #23 raken allebei `checks.toml`-lijsten,
dus die twee sequentieel.

- [ ] **#24 — `overzicht_checks` mist de nulmeting** (tier A). Alleen die tabel; de rest van de
      GeoPackage is al in orde. Verwacht: nul verandering in het aantal meldingen.
- [ ] **#22 — Tel de klassen waar checks van afhangen** (tier A). Verwacht op De Wolden precies
      één systemische waarschuwing: nul overnamepunten.
- [ ] **#23 — RVZ-006 uitbreiden met afvoereindpunt** (tier A). Het VGS-deel (RVZ-012) is
      **uitdrukkelijk buiten scope** en wacht op #17.
- [ ] **#39 — VormPut: 88 ronde putten** (tier A). Nieuw ID ATTR-015, niet ATTR-004 uitbreiden —
      `vergelijk` zet runs naast elkaar op check-ID. **Verwacht exact 88.** Schrijf de test vóór
      de implementatie; het verwachte aantal staat vast, dus TDD is hier goedkoop.
- [ ] **#37 — WIBONThema gebruikt de verkeerde property** (tier A). Bouw de **generieke** check,
      niet één op `WIBONThema`. **Verwacht exact één melding.** Meer dan één betekent dat de
      check te breed staat — meld dat, draai niet aan de drempel.
- [ ] **#4 — Dekkingspoort: derde uitweg in de foutmelding** (tier A). Alleen tekst. Geen
      gedragsverandering.
- [ ] **#7 — Twee dekkingclaims op de verkeerde CFK** (tier A, met poort). Doe stap 1 en 2
      (empirisch vaststellen, register herformuleren). **Stop vóór stap 3** — die raakt BO-7 en
      een harde pijplijnvoorwaarde. Zet de bevinding als comment.
- [ ] **#27 — Architectuurhook per twintig commits** (tier A). De hook moet **nooit** een commit
      laten falen; elke fout stil slikken. Haal ook de dode verwijzing naar `docs/adr/` uit
      `CLAUDE.md` en `docs/agents/domain.md`.

**Afsluiting:** zelfde vijf stappen. **Verwacht verschil: +88 (ATTR-015), +1 (WIBONThema-check),
+1 systemisch (#22).** Elk ander verschil breekt de run af.

---

## Golf 5 — Meten en stoppen

**Basislijn:** `uitvoer/basislijn-golf5`.

Dit is de hele tier B op #17 en #32 na. Deze golf **verandert bijna niets** aan het gedrag en
levert vooral comments met cijfers.

**Volgorde is dwingend:** #19 en #21 vóór #20 — #20 hangt van beide af (natieve
GitHub-afhankelijkheid).

- [ ] **#19 — ATTR-001 telt twee problemen als één getal** (tier B, maar de splitsing zélf mag je
      doorvoeren). Het aantal **bevindingen** moet exact gelijk blijven; alleen de `notes()`
      veranderen. Verwachte uitkomst staat in het issue: 22.078 leidingen met materiaal, 1.362
      zonder, en de emmer "materiaal zonder regel" hoort **nul** te zijn.
- [ ] **#21 — `Begindatum`: dekkingsgat plus renovatieonderzoek** (tier B). Drie delen: de note
      met 13.448 ontbrekende datums, de vulwaardedetector (die op De Wolden **niets** hoort te
      melden — dat is een geldige uitkomst), en de hernoeming van `aanlegjaar` naar een
      GWSW-term. Die hernoeming raakt 30 vindplaatsen en **breekt projectconfiguraties**; zet
      hem in `CHANGELOG.md`. Doe ook het renovatieonderzoek: zijn de 33 PVC-leidingen van vóór
      1955 gerenoveerde riolen?
- [ ] **#20 — `plausibiliteit.toml` onderbouwen** (tier B). De zeven jaartalbesluiten staan
      onderaan de body en zijn vastgesteld beleid. **Behalve PVC** — die wacht op de uitkomst
      van #21. Voer de andere zes door, voeg de bronvelden toe, en meet wat het doet.
- [ ] **#29 — HGT-007 verhangstaffel** (tier B, **alleen meten**). Bereken zonder de check te
      wijzigen hoeveel bevindingen de RIONED-staffel zou opleveren, uitgesplitst per
      diameterklasse. Zet beide getallen als comment. **Wijzig de check niet.**
- [ ] **#35 — Ontologische waardebereiken tegenspreken onze drempels** (tier B). Bouw de
      facettenlezer (`Kenmerk → allValuesFrom → Dt_X → equivalentClass → withRestrictions`),
      inventariseer, rapporteer. **Wijzig geen drempel.** ATTR-008 zou er ~448 bevindingen bij
      krijgen; dat is de auteur zijn beslissing.
- [ ] **#38 — Wandruwheid** (tier B). ATTR-014 mag je bouwen — het besluit is genomen en het
      verwachte aantal (±962 PE) staat vast. De schaalfactor moet **configureerbaar**, niet
      hardgecodeerd. Schrijf het BO-nummer over de tienden-conventie.
- [ ] **#40 — EXT-009 straatnaam tegen BGT en NWB** (tier B). Doe **alleen stap 3**: de
      naamdekking meten. Bouw de liggingscheck niet — het issue heeft daar een expliciete poort.
- [ ] **#41 — Dekkingsanalyse omkeren** (tier B). Bouw de restrictie-evaluator en **valideer hem
      eerst** tegen restricties waarvan we weten dat de nulmeting ze dekt. De twee bekende
      valkuilen (`Rioolput hasConnection VrijvervalRioolleiding` en `Leiding hasAspect
      Wandruwheid max=1`) moeten nul schendingen geven. Lukt die validatie niet, stop bij dit
      issue en meld het.

**Let op de gedeelde schakel:** #35, #37 en #41 hebben alle drie een module nodig die
OWL-restricties uit de ontologie oplost. #37 bouwt hem in golf 4. **Hergebruik die**, bouw hem
niet drie keer.

**Afsluiting:** zelfde vijf stappen. **Verwacht verschil: ±962 (ATTR-014).** Plus wat #20 doet
met de zes jaartallen — noteer dat apart en verklaar het.

---

## Golf 6 — Analyse

**Basislijn:** `uitvoer/basislijn-golf6`.

- [ ] **#17 — Stelselhiërarchie, fase 1** (tier B). Puur onderzoek, geen gedragsverandering.
      Vijf vragen staan in het issue. **Let op de CRLF-val:** `dewolden_orox.ttl` heeft
      CRLF-regeleindes, en een awk-script dat `\r` niet stript geeft **stil nul resultaten**.
      Verwachting uit een eerdere telling: 437 objecten, elke put en leiding aan exact één
      stelsel, geen mismatch. Bevestig of weerleg dat.
      **Stop na fase 1.** Bouw niets.

- [ ] **#18 — Afvoerpad, alleen fase 1** (tier A). Drie kolommen op `putten` en `strengen`:
      `afvoer_eindpunt`, `afvoer_meters`, `afvoer_stappen`. Determinisme is een harde eis: bij
      meerdere bereikbare eindpunten wint het dichtstbijzijnde in stappen, bij gelijkspel de
      kleinste URI.
      **Fase 2 (NET-009) is uitdrukkelijk buiten scope van deze run.** Die voegt een check en een
      registerregel toe; dat is domeinwerk.

**Afsluiting:** zelfde vijf stappen. **Verwacht verschil: nul** (fase 1 voegt kolommen toe, geen
bevindingen).

---

## Stopvoorwaarden

Breek de **hele run** af — niet alleen het lopende issue — bij elk van deze:

1. `ruff`, `ruff format --check`, `mypy` of `pytest` wordt rood en is niet binnen de scope van
   het lopende issue te repareren.
2. Het totaal aantal bevindingen beweegt met meer dan **5 %** zonder dat het issue die beweging
   voorspelde.
3. Een tier-A-issue blijkt toch een domeinbeslissing nodig te hebben.
4. Een golf duurt langer dan **vier uur** wandkloktijd.
5. `git status` toont onverwachte wijzigingen buiten de bestanden die het issue noemt.

**Bij afbreken:** journaal bijwerken met de reden en de laatste groene commit, de werkende
staat committen, stoppen. Niet doorploeteren, niet "even proberen of het toch lukt".

---

## Journaal

Schrijf `docs/weekendrun-2026-08-21.md` en werk hem bij **aan het eind van elke golf** — niet
pas aan het eind van de run, want dan is hij weg als de run afbreekt.

Per golf:

```markdown
## Golf N — <naam>

- Basislijn: <totaal aantal bevindingen>, <aantal checks met bevindingen>
- Na de golf: <totaal>, verschil <±n> (<±x %>)
- Verklaring per verschil: <check-ID>: <voor> → <na>, omdat <reden>

| Issue | Tier | Uitkomst | Commit |
|---|---|---|---|
| #NN | A | afgerond en gesloten | `abc1234` |
| #NN | B | gemeten, open gelaten — zie comment | `def5678` |
| #NN | — | overgeslagen omdat <reden> | — |

Reviewuitkomst: <wat de twee reviewskills opleverden en wat ermee gedaan is>
```

En aan het eind een sectie **"Wat er maandag ligt"**: welke issues open staan, welke beslissing
elk daarvan vraagt, en waar de cijfers staan.

---

## Wat de auteur maandag doet

1. `git log --oneline dev` — één regel per issue, elk terug te draaien met één `git revert`.
2. `docs/weekendrun-2026-08-21.md` — wat er gebeurd is en waarom.
3. `gh issue list --state open` — de tien tier-B-issues met hun metingen in de comments.

De beslissingen die dan liggen te wachten, voor zover nu te voorzien: de verhangstaffel van
#29, de drempels die de ontologie tegenspreken uit #35, wanneer `Gemaal` uit `afvoer_eindpunt`
gaat (#11), de PVC-drempel (#20, afhankelijk van het renovatieonderzoek in #21), en wat er met
de klassenlijsten uit #32 moet gebeuren.

---

## Zelfcontrole van dit plan

**Dekking:** alle 28 open issues zijn ingedeeld — 16 tier A, 10 tier B, 2 tier C. Geteld:
4, 7, 11, 18, 22, 23, 24, 27, 28, 30, 31, 33, 34, 36, 37, 39 (A); 17, 19, 20, 21, 29, 32, 35,
38, 40, 41 (B); 25, 26 (C).

**Afwijking van de skill-sjabloon, bewust:** dit plan herhaalt niet per issue de TDD-stappen en
codeblokken. Dat zou 28 issuebodies dupliceren die al op de tracker staan, compleet met
bestandspaden, verwachte aantallen en verificatiecriteria — en een kopie loopt uit de pas met
het origineel. De issues zijn de spec; dit plan is het protocol eromheen. Wat hier wél volledig
staat is alles wat *niet* in een issue kan staan: volgorde, gedeelde basislijn, tiergrenzen,
stopvoorwaarden en journaalvorm.

**Afhankelijkheden gecontroleerd:** #30 vóór #31 (de test moet rood worden op wat #31
repareert). #19 en #21 vóór #20 (natieve GitHub-afhankelijkheid). #37 vóór #35 en #41 (gedeelde
restrictielezer). #17 en #18 leveren alleen fase 1, dus #25 blijft terecht geblokkeerd.

**Consistentie van verwachte aantallen:** #39 → 88, #37 → 1, #38 → ±962, #22 → 1 systemisch,
#19 → 0 verandering in bevindingen. Deze staan zowel in dit plan als in de issues; wijken ze
af, dan is het issue leidend.
