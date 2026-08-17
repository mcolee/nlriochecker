# Eindverslag ronde 1: rapportverbeteringen en GeoPackage-export

Datum: 2026-08-16. Opdracht: `instructie-claude-code-gpkg-en-rapport.md`.
Ontwerp: `docs/superpowers/specs/2026-08-16-gpkg-en-rapport-design.md`.
Commits: `dd81b25` t/m `844a135` (zestien stappen, elk met tests en een groene suite).

---

## 1. Brainstormuitkomsten en waar ik ervan afweek

De brainstorm behandelde de zeven ontwerpvragen uit §1 van de instructie. De
uitkomsten:

| # | Vraag | Keuze |
|---|---|---|
| 1 | Graaf-fix | Alleen een naamfix plus regressietest — de diagnose in de instructie bleek onjuist, zie §3 |
| 2 | Clusteraggregatie | Per streng blijven melden, met een `cluster_id` op elke bevinding en een clusterduiding in het rapport |
| 3 | Scopebeleid | **Opdrachtgever week af van de instructie:** met een studiegebied bevatten MD, CSV én GPKG alleen de bevindingen uit dat gebied |
| 4 | Grensregel | Nul GWSW-objecten binnen het gebied is een harde fout |
| 5 | Melding-ID | Hash over check, beide objecten en de identificerende detailsleutels, met een luidruchtig volgnummer als vangnet |
| 6 | HGT-001/002 | Vaste, neutrale titel plus een verplichte toelichting met de telling van het feitelijk vergeleken kenmerk |
| 7 | Stijlen | QML in `layer_styles` én los ernaast; het `.qgz`-projectbestand vervalt |

Tijdens de bouw week ik op twee punten van de brainstormuitkomsten af:

**`Check.id_sleutels` heeft `("zijde",)` als default, niet `()`.** Het ontwerp
schreef een lege default voor met een declaratie per check. In de praktijk gebruiken
negen meldingen in vier modules `zijde` als onderscheid tussen twee bevindingen op
hetzelfde object. Een lege default zou betekenen dat elk van die checks het apart
moet declareren, met een botsing als iemand dat vergeet. `zijde` is in deze codebase
de standaarddiscriminant; een check die iets anders nodig heeft, declareert dat nog
steeds zelf. Het vangnet blijft: bij een botsing volgt een volgnummer én een
waarschuwing.

**De clusterduiding staat in de rapportlaag, niet in `notes()` van de check.** Zie
§4: dit kwam pas op de echte data naar boven.

---

## 2. Wat er per onderdeel gebouwd is

### A1 — Synthesesectie "Rode draad"

`src/nlriochecker/uitvoer/synthese.py`. Drie detecties, elk met een configureerbare
drempel in het nieuwe `[rapport]`-blok van `checks.toml`. Slaat geen enkele detectie
aan, dan komt de kop er niet.

Op de Koekangerveld-run levert dat:

> Bij 3918 van de 17603 strengen met bekende BOB's stijgt de bodem in de
> administratieve afvoerrichting (22%). Dat wijst op systematisch omgekeerd
> geregistreerde van-naar-richtingen, en die verklaren vermoedelijk het merendeel van
> de 53 bevindingen van HGT-005, HGT-006, NET-001, NET-003, NET-004 in een keer.

plus de zeventien objecten met meldingen uit drie of meer checks (waarvan er vijf bij
naam genoemd worden) en de twee deelstelsels die zowel bij NET-001 als bij RVZ-006
terugkomen.

### A2 — Clusterduiding en cluster-ID

`deelstelsel_ids()` in `checks/verbanden.py` nummert de samenhangende delen van het
vrijvervalnetwerk. NET-001, NET-002 en RVZ-006 gebruiken nu allemaal diezelfde
indeling, zodat het kruisverband uit A1 op gelijke ID's kan vergelijken. Op De Wolden:
de 24 NET-001-bevindingen betreffen `ds-ID0500` en `ds-Kv1G0002` — precies de twee
deelstelsels die ook RVZ-006 meldt.

### A3 — Graafopbouw

Geen graaf-fix maar een naamfix; zie §3.

### A4 — Semantiek HGT-001/002

Titel is nu "Deksel- of maaiveldhoogte wijkt af van AHN: meer dan 5 cm" (resp. 25 cm),
en beide checks dragen een verplichte toelichtingsregel die met aantallen zegt wat er
feitelijk vergeleken is. In De Wolden ontbreekt `Putdekselniveau` overal, dus die regel
noemt de maaiveldhoogte.

### A5 — Geen afkap, taal, scope

De top-15-afkap is `rapport.max_bevindingen_per_check` geworden, default 0 =
onbeperkt; wordt er wel afgekapt, dan staat eronder hoeveel er niet getoond zijn.
`src/nlriochecker/taal.py` doet getal- en lidwoordcongruentie; een onbekend woord
geeft een `KeyError` in plaats van stilzwijgend "de". Dat ruimde vier fouten op:
"Het maaiveldhoogte", "1 bevindingen" (twee keer in de CLI), "1 eindknopen" en
"de overige 1 lopen dood".

Scope: met een studiegebied bevatten alle drie de uitvoervormen dezelfde verzameling;
de kolom `scope` legt vast welk beleid gold. Het rapport meldt onverminderd dat 35.899
bevindingen buiten het gebied vielen.

### A6 — CSV

Dertien kolommen erbij (23 in totaal). De bestaande negen houden hun naam en plaats.
`X` en `Y` dragen nu de foutlocatie in plaats van alleen de eigen coördinaat van
externe objecten; de coördinaat van TOP-011 is uit de meldingtekst gehaald.

### B — GeoPackage

`src/nlriochecker/uitvoer/gpkg.py`, met `sqlite3` en `shapely.wkb` — geen nieuwe
afhankelijkheid. Zes lagen, EPSG:28992, embedded QGIS-stijlen plus losse QML's.
`toets` schrijft het bestand standaard mee; `--geen-gpkg` slaat het over.

Op de Koekangerveld-run: 192 kB, 48 putten, 50 strengen, 113 meldingen, 113
meldinglocaties, 87 rijen in `overzicht_checks` (alle checks, ook de nulbevindingen en
de skeletten) en één rij `gwsw_run` met de herkomst en de grens. Per check komen de
aantallen in Markdown, CSV en GeoPackage exact overeen; alle 113 melding-ID's zijn
uniek zonder dat het volgnummer-vangnet eraan te pas kwam.

---

## 3. De graafkwestie: voor en na

De instructie (§A3) en het richtbeeld gingen ervan uit dat orientatie-aspecten als
knoop in de netwerkgraaf terechtkwamen, en verwachtten dat een fix de NET-aantallen
zou verschuiven. Dat is niet zo.

`_read_nodes()` (`dataset.py:730`) neemt als knoop het *subject* dat de orientatie via
`hasAspect` draagt, nooit het aspect zelf. In de De Wolden-TTL:

```
:knp1      rdf:type gwsw:Rioolgemaal ; rdfs:label "Nw2V0002" .
:knp1_put  rdf:type gwsw:Bouwwerkorientatie .
:knp1      gwsw:hasAspect :knp1_put .
```

De graafknoop is `:knp1`. De fout zat in `_soort()` (`checks/netwerk.py`), die de
alfabetisch eerste naam uit `types_of()` pakte — en `types_of()` voegt de
aspecttypen er bewust bij, want Lozingspunt en UitlaatPunt staan volgens het GWSW op
de orientatie. Alfabetisch won "Bouwwerkorientatie" van "Rioolgemaal" en
"Putorientatie" van "Stuwput".

**Voor en na in de eindknoop-verdeling van NET-001:**

| Voor | Na |
|---|---|
| Inspectieput 1543, **Bouwwerkorientatie 233**, Overstortput 47, Lozingsput 8, **Putorientatie 6** | Inspectieput 1543, **Uitlaatconstructie 233**, Overstortput 47, Lozingsput 8, **Stuwput 6** |

Dezelfde objecten, de juiste namen. **Geen enkel aantal is verschoven**: 113
bevindingen, 57 F en 56 W, NET-001 = 24, EXT-008 = 16 — alle ankerpunten uit §4.1 van
de instructie houden stand. De 233 "Bouwwerkorientaties" waren 233 uitlaatconstructies
met een verkeerd label, geen lek in de netwerkopbouw.

Een regressietest legt vast dat elke graafknoop een beheerobjecttype draagt, zodat een
latere wijziging in de lader niet alsnog aspecten de graaf in laat lopen.

---

## 4. Wat de echte data aan het licht bracht

De unit- en integratietests waren groen voordat de volledige De Wolden-run draaide.
Die run legde drie dingen bloot die geen enkele fixture had gevangen:

**Het rapport meldde "174 deelstelsels" bij 24 bevindingen.** De clusterduiding zat in
`notes()` van de check, en een check draait op de volledige dataset terwijl het rapport
tot Koekangerveld is afgebakend. Het getal was op zichzelf waar en in de context
volstrekt misleidend. De duiding is verhuisd naar de rapportlaag, waar ze telt wat de
lezer voor zich heeft: 24 bevindingen, 2 deelstelsels. Een fixture met twee losse
deelstelsels en een gebied dat er één dekt legt dat nu vast.

**De synthese schreef zeventien objecten voluit** in één alinea. Er worden er nu vijf
genoemd met een telling voor de rest.

**"voordat de losse meldingen wordt nagelopen"** — de grammatica-helper dekte het
zelfstandig naamwoord maar niet het werkwoord in dezelfde zin.

Dit is precies waar de regel "geloof onwaarschijnlijke uitkomsten niet" uit CLAUDE.md
voor bedoeld is; de fixtures waren te klein om het verschil tussen datasetbreed en
afgebakend te laten zien.

---

## 4a. Wat de code review aan het licht bracht

De review (`/superpowers:requesting-code-review`) vond één zaak die alles ervoor
waardeloos maakte en zes die er echt toe deden.

**De hele `uitvoer/`-package stond niet onder versiebeheer.** `.gitignore` bevatte
`uitvoer/` zonder leidende slash, bedoeld voor de uitvoermap van de pijplijn. Die regel
sloot ook `src/nlriochecker/uitvoer/` uit. Alle 1652 regels nieuwe code bestonden alleen
in mijn werkboom: elke commit vanaf `2ff975b` importeert niet vanaf een schone checkout.
Tweede gevolg: ruff respecteert `.gitignore`, dus ook de linter had de package nooit
gezien — het "All checks passed" van twaalf stappen was vals, en er stonden vier
lintfouten en een formatteerfout in. De regel is nu `/uitvoer/`, en een test controleert
dat elk bronbestand op schijf ook in git zit.

De overige punten, kort:

- **ATTR-005 botste op zijn eigen melding-ID.** Die check meldt per profielmaat
  (breedte, hoogte) en niet per strengeinde, dus de standaarddiscriminant `zijde` hielp
  er niet. Het vangnet sloeg op de fixtures dus al aan, met een volgnummer dat van de
  verwerkingsvolgorde afhangt — precies de eigenschap die de ID niet hoort te hebben.
  ATTR-005 declareert nu `kenmerk`, en een sweep over alle fixtures eist dat het vangnet
  nergens hoeft aan te slaan.
- **Die sweep vond twee crashes** die geen enkele test raakte, beide op een
  vlakgeometrie: `meetkunde._flat_coords` viel om doordat `hasattr` de
  `coords`-property van een shapely-Polygon aanroept (die gooit `NotImplementedError`,
  geen `AttributeError`), en de foutlocatie struikelde over `interpolate` op een vlak.
  Juist TOP-015 en TOP-016 melden zulke geometrie. `meetkunde.py` was deze ronde niet
  aangeraakt; de crash is ouder dan deze opdracht.
- **De consistentie tussen de drie uitvoervormen berustte op iteratievolgorde.** Het
  rapport en `overzicht_checks` telden `run.outcomes`, niet de meldingenstroom. Vandaag
  gaf dat dezelfde uitkomst; zodra ronde 2 nulmeting-meldingen toevoegt zouden MD en
  het dashboard stilzwijgend te laag rapporteren terwijl CSV en `meldingen` dat niet
  doen. Beide lezen nu per check uit de stroom.
- **Het richtingspercentage in de synthese is datasetbreed** en stond zonder
  kanttekening boven een afgebakende lijst — dezelfde fout als "174 deelstelsels". Bij
  een run met studiegebied staat dat er nu bij.
- **De systemisch-vlag deelde een afgebakende teller door een datasetbrede noemer** en
  kon na afbakening feitelijk nooit meer aanslaan. De teller telt nu ook de weggelaten
  bevindingen mee, zodat de vlag hetzelfde betekent met en zonder studiegebied.
- **`meldinglocaties.qml` beloofde een filter dat er niet in zat.** De toelichting zei
  dat systemische meldingen worden weggelaten, maar de stijl was een gecategoriseerde
  renderer zonder filter. Het is nu een regelgebaseerde renderer die wél filtert, en een
  test leest de regels na.

Verder is de `beheerobjecttype`-regel uit A3 — die op twee plekken stond, nadat ik hem
net op één plek had rechtgezet — naar `GwswDataset` verhuisd.

---

## 5. Afwijkingen van de instructie

| # | Bron | Afwijking | Reden |
|---|---|---|---|
| 1 | §A3 | Naamfix in plaats van graaf-fix; geen verschuiving in de NET-aantallen | De diagnose in de instructie klopt niet; zie §3 |
| 2 | §A5.3, §A6 | CSV en GPKG volgen de MD-afbakening in plaats van alles te bewaren | Beslissing van de opdrachtgever; lost tegelijk de tegenstrijdigheid met §3.1 op |
| 3 | §3.2 | Nulmeting-integratie naar ronde 2 | Drie nieuwe onderdelen bovenop de rest; kleine stappen conform CLAUDE.md |
| 4 | §3.2 | `--shacl` in plaats van `--mds` / `--hyd` | Die vlaggen bestaan niet; `--shacl` neemt alle drie de CFK-rapporten aan |
| 5 | Ontwerp §1 | Geen `.qgz`-projectbestand | Broos met de hand te maken en zonder QGIS in de build niet te verifiëren |
| 6 | §A6 | CSV-kolomnamen in de bestaande CamelCase-stijl; GPKG wél snake_case | Hernoemen breekt bestaande verwerking zonder tegenprestatie |
| 7 | Ontwerp §2.3 | Hash uitgebreid met identificerende detailsleutels | `check + feature + feature_2` botst bij checks die per zijde melden |
| 8 | Ontwerp §5.2 | `gebied` uit het studiegebiedbestand | Er is geen dekkende buurtenlaag, en die is bij een begrensde export niet nodig |
| 9 | §A6 | `object2` alleen gevuld bij TOP-005, TOP-006, TOP-010 en TOP-011 | TOP-013 en TOP-019 hebben géén enkele tegenpartij maar een verzameling; die staat in de details, niet in een kolom die één object suggereert |
| 10 | Ontwerp §3 | `Check.id_sleutels` heeft `("zijde",)` als default | Negen meldingen in vier modules gebruiken `zijde`; een check met een eigen onderscheid declareert dat nog steeds zelf (ATTR-005 doet dat met `kenmerk`) |
| 11 | Ontwerp §7.3 | Symboolgrootte vast per ernstcategorie, niet afgeleid van `n_fout + n_waarschuwing` | Een data-defined grootte is QGIS-versiegevoelige XML die zonder QGIS in de build niet te verifiëren is; dezelfde afweging als bij het `.qgz`-bestand |
| 12 | Ontwerp §6.6 | `taal.LIDWOORDEN` bevat twee woorden, niet negen | Alleen woorden die daadwerkelijk in een sjabloon voorkomen; een onbekend woord valt hard om, dus de lijst groeit vanzelf mee |

---

## 6. Tests

626 tests, groen. De drie zware De Wolden-tests staan onder de marker `zwaar` en
draaien niet standaard mee; ze zijn apart gedraaid en zijn ook groen (14 minuten).
Ruff (lint en format) is schoon — nu ook aantoonbaar, want de linter zag de nieuwe
package eerst helemaal niet.

Twee tests kijken bewust over de hele codebase heen in plaats van naar één module:
één sweept alle TTL-fixtures op botsende melding-ID's, één controleert dat elk
bronbestand op schijf ook in git staat. Beide vonden meteen een echt gebrek.

De acht testgroepen uit §10 van het ontwerp zijn alle gedekt: de graaf-regressietest,
de zes GPKG-tests (a t/m f, inclusief het teruglezen van het geschreven bestand met de
eigen lezer uit `studiegebied.py`), de grammaticatests, de consistentietest die per
check de aantallen in MD, CSV en GPKG vergelijkt, de melding-ID-tests, de
synthesetests en de foutlocatietests.

---

## 7. Openstaand

- **Ronde 2**: de nulmeting-meldingen in de GPKG — focusnode-herleiding,
  Mds/Hyd-deduplicatie, systemisch-vlag op nulmetingtypen, en de keuze tussen
  doorgeven of vertalen van de SHACL-boodschappen.
- De negentien nog niet gebouwde TOP- en NET-checks uit het register.
- `prioriteit` gebruikt een klassenlijst, geen netwerkanalyse van de hoofdafvoerroute;
  het ontwerpdocument staat dat voor een eerste versie expliciet toe.
- Op de Koekangerveld-run komt prioriteit 1 niet voor: binnen de buurtgrens ligt geen
  overstort, BBB of gemaal. Dat is consistent met wat RVZ-006 daar meldt, maar het
  betekent ook dat de prioriteitsindeling op deze run niet in de breedte beproefd is.
