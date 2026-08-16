# Vijf kandidaat-checks — beoordeling en uitkomst

Opgeleverd 2026-08-16, naar aanleiding van `instructie-claude-code-nieuwe-checks.md`
v1.0. Basis: checkregister v0.7, dataset `dewolden_orox.ttl`, nulmetingsrapporten
Hyd, MdsPlan en MdsProj d.d. 2026-08-16, ontologie
`Ontologie_GWSW_Totaal.ttl`.

De opdracht was uitdrukkelijk niet om vijf checks te bouwen, maar om per kandidaat
te wegen of toevoeging aan deze codebase zinnig is. Uitkomst: **één kandidaat
gedeeltelijk doorgevoerd, twee doorgevoerd als rapportageregel, twee afgewezen**,
plus één verbeterstap aan de verwerkingskant die uit de afwijzing van kandidaat B
voortkwam.

| Kandidaat | Besluit | Waar het landde |
| --- | --- | --- |
| A — META-001, regressietoets dekkingsclaims | **deels doorgevoerd**, niet als registercheck | `coverage.py`, `dekking.toml`, `dekking`- en `analyseer`-commando |
| B — BTR-008, inwinningswijze past niet bij het kenmerk | **afgewezen**; bronverificatie geslaagd en wijst van de check af | kanttekening bij HGT-001 en HGT-002 |
| C — TYP-001, typeringsscore als poortwachter | **afgewezen**, dubbel | bestaat al als `TypingGate` plus `typeringsscore_minimum` |
| D — BTR-007, placeholder-datums | **doorgevoerd als rapportageregel** | `karakteristiek.py`, kop van `bevindingen.md` |
| E — BTR-009, expliciete onbekend-waarden | **doorgevoerd als rapportageregel** | idem |

---

## Kandidaat A: regressietoets op de dekkingsclaims

**Besluit: deels doorgevoerd. Twee van de drie onderdelen bestonden al; het derde
is gebouwd. Niet als rij in een registertabel.**

Langs het afwegingskader:

1. **Niet-dubbel — deels nee.** Onderdeel (a), beide CFK-rapporten aanwezig op
   hetzelfde RDF-bestand, is al een harde fout in `meting.laad_nulmeting`.
   Onderdeel (b), per geschrapte check een sentinel-vormpatroon, is al
   `coverage.py` met de data-gedreven tabel in `dekking.toml` — precies zoals de
   implementatienoot van de kandidaat voorschrijft. Alleen onderdeel (c),
   versiebewaking, ontbrak volledig.
2. **Actiegericht — ja.** Een gefaalde voorwaarde leidt tot een concrete
   handeling: de sentineltabel bijwerken of de schrapronde overdoen.
3. **Hefboom — ja.** Zes checks staan niet in de engine omdat de nulmeting ze zou
   dekken. Vervalt die dekking, dan kijkt er niets meer naar. Dat is precies het
   soort stille regressie dat je maar één keer wilt missen, en het is
   projectonafhankelijk.
4. **Implementeerbaar — ja, op één punt na.** Zie hieronder.
5. **Past in het register — ja, maar niet als registerrij.** Zie hieronder.

### Wat er gebouwd is

`verify_register()` legt de sentineltabel naast de tabel *Geschrapte checks* van
het register en faalt hard bij versieverschil, bij een geschrapte check zonder
sentinel, of bij een sentinel voor een check die niet (meer) geschrapt is. De
`dekking`- en `analyseer`-commando's roepen die controle aan vóór ze een
dekkingrapport schrijven; zonder register slaan ze de ijking over en zégt het
rapport dat, in plaats van stil door te gaan. Welk register geldt, is te sturen
met `--checkregister`; zonder die optie telt het register dat de mapping zelf in
`bron` noemt, want dáár is ze tegen geverifieerd.

Daarnaast zoekt de analyse **bewijsvormen die niet in alle vereiste CFK's
vuren**. Alle CFK's toetsen hetzelfde RDF-bestand, dus als een vorm in de ene wel
en in de andere geen meldingen oplevert, zit dat verschil in de meting en niet in
de data. Twee dingen kunnen het veroorzaken: de vormverzameling van de CFK
verschilt, of de rapporten zijn niet op dezelfde onderdelen gedraaid. Dat laatste
staat in het kopblok en wordt apart gecontroleerd, zodat het rapport zegt welke
van de twee overblijft. Nul meldingen in *álle* CFK's telt bewust niet mee: dat is
niet te onderscheiden van schone data en zou een vals alarm zijn.

Dat levert op De Wolden meteen een echte bevinding op:

```
Let op: ADM-004 steunt op Put_MateriaalPut_card, die wel in Hyd meldingen
        geeft en niet in MdsPlan, MdsProj.
Let op: ADM-004 steunt op Rioolput_Maaiveldschematisering_card, die wel in
        Hyd meldingen geeft en niet in MdsPlan, MdsProj.
```

De drie rapporten zijn blijkens hun kopblok op dezelfde onderdelen gevalideerd,
dus het verschil zit in de vormverzameling. De dekkingclaim van ADM-004 schrijft
die eisen aan Mds toe; dat klopt niet. Opgenomen als open punt 11 in het
register.

### Wat er niet gebouwd is, en waarom

**Onderdeel (c), de CFK-versie, is niet te bouwen zoals beschreven.** De kandidaat
gaat ervan uit dat de rapportkop de gebruikte CFK-versie noemt (deelmodellen v1.6,
filters `collectie_MDSTOP_v16` en `collectie_HYDTOP5_v16`). Dat doet hij niet. Het
volledige kopblok van de GWSW-server is:

```
Rapport SHACL-meting dd, Gevalideerd RDF-bestand, Gebruikte SHACL-processor,
SHACL-meting op basis GWSW, SHACL-meting op basis CFK, Lokale kwaliteitseisen
uit bestand, Gevalideerd op onderdelen, Niet gevalideerd op, Maximaal aantal
meldingen, Draaitijd, Rapport 'conforms'
```

Geen versie, geen filternaam. In plaats daarvan bewaakt de controle nu de
*registerversie* van de sentineltabel — de kant die wél te verifiëren is. Dat de
meting nog op v1.6 draait blijft handwerk; opgenomen bij open punt 10.

**Niet als rij in een categorietabel van het register.** De instructie schrijft dat
voor, en dit wijkt daarvan af. Reden: de dekkingsmatrix (`scripts/dekkingsmatrix.py`)
wordt gegenereerd uit register én registry, en er is een test die faalt zodra ze
uiteenlopen. Een register-ID zonder implementatie in `REGISTRY` verschijnt daar als
*ontbreekt*. Om META-001 wél in de registry te krijgen zou een `Check` nodig zijn
die geen dataset-object heeft om een bevinding aan te hangen, en die bij een
studiegebiedafbakening stilzwijgend verdwijnt (`beperk_tot_studiegebied` laat
alleen bevindingen door met een URI in het gebied of een eigen coördinaat). Het
register beschrijft bovendien datachecks; dit is een controle op de pijplijn.

De inhoud van de kandidaat staat wel in het register: de voorwaarden bij
*Geschrapte checks* zijn uitgebreid met een derde, en er staat expliciet bij dat
alle drie machinaal gehandhaafd worden. Geen nieuw ID, dus ook geen risico op
hergebruik van een vervallen ID.

---

## Kandidaat B: inwinningswijze past niet bij het kenmerk

**Besluit: afgewezen als registercheck. De verplichte bronverificatie is geslaagd
en wijst van de check af. Wat er wél onder zat, is gebouwd.**

De kandidaat stelde als harde voorwaarde: verifieer eerst de betekenis van het
Punt-aspect en de plaats van de inwinningsmetadata in de bronconversie, en
implementeer niet als dat niet lukt. Dat is gelukt, langs twee wegen.

**Uit de ontologie.** In `Ontologie_GWSW_Totaal.ttl` dragen 36 klassen een
restrictie `hasAspect ... Inwinning`; `Geometrie` staat daarbij, en `Punt` is een
subklasse van `Geometrie`. De toegestane waarden komen uit één collectie
(`WijzeVanInwinningColl`) die geen onderscheid maakt naar kenmerksoort. Inwinning
op een Punt is dus ontologisch correct, en AHN2 is er een toegestane waarde.

**Uit de data.** Doorslaggevend is het patroon per maaiveldoriëntatie:

| wijze op het Punt | wijze op de Maaiveldhoogte | aantal |
| --- | --- | ---: |
| — | — | 12.313 |
| **AHN2** | **—** | **5.104** |
| Inmeting | Inmeting | 3.103 |
| NietAchterhaald | NietAchterhaald | 1.351 |
| Revisie | Revisie | 339 |
| Plan_Ontwerp | Plan_Ontwerp | 61 |
| Schatting | Schatting | 20 |
| Luchtfoto | Luchtfoto | 1 |
| Revisie / Schatting / Inmeting | — | 71 |

Er is geen enkele regel waarin de twee wijzen verschillen. AHN2 komt 5.104 keer
op het Punt voor en **nul keer** op de maaiveldhoogte. De conversie spiegelt dus
één record-brede inwinningswijze op het Punt-aspect en laat hem bij AHN2 alleen
daar staan. "AHN2 als inwinningswijze van XY" is daarmee geen registratiefout
maar een leesconventie van de bronexport — het tweede scenario dat de kandidaat
zelf als ruis bestempelde.

Langs het afwegingskader valt de check dan ook op vraag 2: 10.210 meldingen met
één systematische oorzaak en geen enkele handeling per object. De instructie
formuleert dat zelf: "een check die op vrijwel 100% van de objecten aanslaat is
rapportage, geen check".

### De verbeterstap die eruit voortkwam

Onder de kandidaat zat wel iets van waarde, en dat is gebouwd. HGT-001 en HGT-002
vergelijken de geregistreerde hoogte met het AHN5-raster. De De Wolden-export
bevat geen enkel `Putdekselniveau`, dus die checks vallen terug op de
maaiveldhoogte — en **5.104 van de 22.363 maaiveldhoogten komen zelf uit het AHN**.
Voor die putten vergelijkt de check twee hoogtemodellen met elkaar. Een afwijking
daar is geen gebrek in de beheerdata en valt niet met een veldmeting te
herstellen, maar leest in het rapport wel zo.

Gebouwd:

- de lader leest de inwinningswijze van een maaiveldhoogte nu ook van het
  Punt-aspect van de maaiveldoriëntatie (`Node.maaiveld_inwinning`). Zonder die
  terugval zou juist de uit AHN afgeleide helft als herkomstloos gelden;
- HGT-001 en HGT-002 zetten de wijze in de bevinding, markeren of ze uit een
  hoogtemodel komt, voegen de kanttekening aan de meldingtekst toe, en tellen in
  de toelichting hoeveel van de vergeleken hoogten het betreft;
- welke wijzen als hoogtemodel gelden staat in `checks.toml` onder `[inwinning]`.
  Een lege lijst zet de kanttekening uit.

Op het studiegebied Koekangerveld verandert dit niets aan de uitslag: alle 15
HGT-001-bevindingen daar staan op gemeten maaiveldhoogten. Dat is precies wat je
wilt zien — de kwalificatie vuurt niet uit zichzelf.

---

## Kandidaat C: typeringsscore als poortwachter

**Besluit: afgewezen. Dubbel op vraag 1, en er valt in deze dataset niets te
vinden.**

De typeringspoort bestaat al. `analysis.TypingGate` leest de te globale klassen
uit de `CfkTypes_typ`-meldingen, zoekt de instanties op in de dataset en berekent
een score; `coverage.py` legt die score naast `drempels.typeringsscore_minimum`
(configureerbaar, standaard 95%) en zet een voorbehoud op elke dekkingclaim
waarvan een vereiste CFK eronder blijft. Dat is exact voorwaarde 2 uit de
schrapronde, en het is precies wat de kandidaat voorstelt.

Het datafeit uit de instructie klopt bovendien niet. De genoemde som van
specifieke subtypen (19.577) mist Pompunit, Lozingsput, Kruisingsput, Kolk en
Drainageput, en telt Ontstoppingsstuk mee dat een Hulpstuk is en geen put. Per
oriëntatie geteld:

| klasse achter de Putorientatie | aantal |
| --- | ---: |
| Inspectieput | 19.322 |
| Pompunit | 1.107 |
| Overstortput | 218 |
| Lozingsput | 55 |
| Stuwput | 27 |
| Kruisingsput | 27 |
| Kolk | 1 |
| Drainageput | 1 |
| **totaal** | **20.758** |

Dat is exact het aantal putorientaties. **Er is geen enkele generiek getypeerde
put in De Wolden.** Het verschil van ~1.180 waar de kandidaat op wees, is geen
generieke typering maar een telfout.

Opgenomen als open punt 12 in het register, zodat de meting vindbaar blijft.

---

## Kandidaten D en E: placeholder-datums en pseudo-vulling

**Besluit: beide afgewezen als registercheck, beide doorgevoerd als
rapportageregel — precies zoals de kandidaten zelf voorstelden.**

Beide datafeiten zijn geverifieerd: alle 33.477 begindatums vallen op 1 januari,
en 4.077 van de 25.546 inwinningsregistraties (16,0%) hebben de waarde
`NietAchterhaald`. Als check zouden ze tienduizenden meldingen produceren die
samen één mededeling zijn.

De voorwaarde was "alleen bij minimale ingreep in een bestaande laag". Het
bevindingenrapport heeft al een kop met dit soort context (coderingsterugval,
studiegebied, ontbrekende ontologie, externe bronnen). Daar is één sectie
**Datakarakteristieken** bij gekomen, gevoed door een nieuwe module
`karakteristiek.py`:

- **datumprecisie** per datumkenmerk: hoeveel waarden er zijn en hoeveel op 1
  januari vallen. Valt alles op 1 januari, dan meldt het rapport dat leeftijden
  en tijdsverschillen op jaarniveau gelden en een uitkomst op dagniveau een
  precisie zou suggereren die de bron niet heeft;
- **vulling van de inwinningsmetagegevens** per kritiek hoogtekenmerk
  (maaiveldhoogte, putdekselniveau, beide BOB's): hoeveel waarden er zijn,
  hoeveel er een wijze hebben, en hoeveel daarvan expliciet onbekend zijn, met de
  toelichting dat die elke kardinaliteits- en collectietoets passeren zonder
  informatie te dragen.

Welke kenmerken datums zijn, leidt de module uit de dataset af (GWSW-naam bevat
"datum", waarde is als datum te lezen) in plaats van uit een vaste lijst. Welke
waarden "onbekend" betekenen staat in `checks.toml`; dat is een projectafspraak
die de GWSW-ontologie niet maakt.

Zo ziet dat er op De Wolden uit:

| Hoogtekenmerk | Waarden | Met inwinningswijze | Waarvan expliciet onbekend |
| --- | ---: | ---: | ---: |
| maaiveldhoogte | 22.363 | 10.050 | 1.351 (13,4%) |
| BOB beginpunt | 23.440 | 266 | 12 (4,5%) |
| BOB eindpunt | 23.440 | 271 | 12 (4,4%) |

Let op het bereik: dit zijn de vier kritieke hoogtekenmerken die de pijplijn
inleest, samen 1.375 expliciete onbekend-waarden. De 4.077 uit het datafeit
tellen alle 25.546 inwinningsregistraties mee, ook die op kenmerken die de
pijplijn niet inleest. Het rapport claimt dus niet meer dan het bekeken heeft.
`Putdekselniveau` staat niet in de tabel: dat kenmerk komt in deze export nul
keer voor, en over een kenmerk dat er niet is valt niets te zeggen.

De voorgestelde *precisievlag die leeftijdsberekeningen op jaarniveau afdwingt* is
niet gebouwd. Er is geen consument: BTR-003 en BTR-005 zijn skelet, en ATTR-003
en ATTR-007 rekenen al met `Conduit.aanlegjaar`, dus met het jaartal. Een vlag
zonder consument is dode configuratie.

---

## De vraag uit sectie 2: zat mijn tijd hier goed?

De instructie stelt terecht dat de grootste openstaande waarde in de bestaande
meldingsstromen zit en niet in nieuwe checks. Mijn oordeel: **deels waar, maar de
diagnose "geen aggregatie, geen prioritering" klopt niet voor deze codebase, en de
grootste stromen zijn geen herstelwerk.**

Wat er al is: `bevindingen.md` heeft een samenvattingstabel per check, elke check
levert een toelichting over wat er *niet* bekeken is, bevindingen dragen
gestructureerde details, `bevindingen.csv` bevat alles, en de studiegebied-
afbakening meldt expliciet hoeveel er buiten viel. Aggregatie en context zijn dus
niet het gat.

Belangrijker is dat de drie genoemde stromen bij nadere beschouwing geen
herstelacties zijn:

- **20.758 putten zonder dekselniveau** — de export bevat *nul* `Putdekselniveau`-
  kenmerken. Dat is geen dataprobleem per put maar een eigenschap van de
  BrutIS-conversie; er valt niets per object te herstellen tot de bronexport
  verandert. Het is bovendien geen bevinding van deze engine maar een
  nulmetingmelding (`Put_HoogtePut_card`).
- **~3.000 incomplete put-strengkoppelingen** (1.178 + 1.846) — dit is ADM-001, een
  geschrapte check. Die stroom komt uit de nulmeting, niet uit de engine, en de
  dekkinganalyse rapporteert hem al.
- **1.123 knooppunten zonder netwerkverbinding** — ook een nulmeldingstroom
  (`Knooppunt_Netwerk_conn`), overwegend T-stukken van drukriolering.

Een export-naar-herstelacties bouwen op stromen waarvan er per object niets te
herstellen valt, zou de suggestie wekken dat er 20.758 putten te bezoeken zijn.
Dat leek me schadelijker dan nuttig.

Ik heb de toegestane verbeterstap daarom besteed aan de plek waar bevindingen wél
verkeerd gelezen werden: HGT-001 en HGT-002 markeerden 5.104 potentiële
vergelijkingen van AHN met AHN als afwijkingen in de beheerdata. Dat is een
kwaliteitsverbetering aan een bestaande meldingsstroom, en hij kwam rechtstreeks
uit de afwijzing van kandidaat B.

## Kritiek op de instructie

Eerlijkheidshalve, zoals gevraagd:

- **Kandidaat A ging uit van functionaliteit die er al was.** Onderdelen (a) en (b)
  waren volledig gebouwd, inclusief de data-gedreven sentineltabel die de
  implementatienoot voorschrijft. De weging "sterkste kandidaat" klopt inhoudelijk,
  maar het bouwwerk was voor twee derde al af.
- **Kandidaat A onderdeel (c) is niet uitvoerbaar zoals beschreven**: de
  rapportkoppen bevatten geen CFK-versie.
- **Het datafeit onder kandidaat C is een telfout.** De genoemde ~1.180 generiek
  getypeerde putten bestaan niet.
- **Kandidaat A's dekkingsbewijs voor RVZ-002 is zwakker dan gesteld.** De 218
  meldingen `Overstortput_Overstortdrempel_card` zeggen dat een overstortput geen
  drempel *heeft* — niet dat het *niveau* ervan ontbreekt. Er is in geen van de
  drie rapporten een vorm op `Drempelniveau`. Dat de dekking hier in De Wolden
  toevallig sluitend is (alle 218 overstortputten missen de drempel volledig) maakt
  de claim nog niet algemeen geldig. `dekking.toml` was hier al eerlijk over.
- **De aanname dat "beide CFK's" volstaat, is achterhaald.** Het register spreekt
  van twee conformiteitsklassen (Mds en Hyd), maar de GWSW-server levert er drie
  (Hyd, MdsPlan, MdsProj) en `checks.toml` eist ze alle drie. `Overstortput_Overstortdrempel_card`
  en `Gemaal_Pomp_card` vuren wel in Hyd en MdsPlan maar niet in MdsProj — een
  schrapronde die alleen op "Mds" redeneert, mist dat verschil.

## Meegenomen correctie: de toelichting van BTR-001 en BTR-002

Het meten voor kandidaat B legde bloot dat de skelettoelichting van BTR-001 en
BTR-002 een onjuiste bewering bevatte: "de inwinningswijze hangt aan de
puntgeometrie en niet aan de BOB's". Dat klopt niet. De export heeft wel degelijk
inwinning op de BOB's, alleen weinig: 266 van de 23.440 aan het beginpunt en 271
aan het eindpunt. Beide toelichtingen zijn vervangen door de gemeten cijfers. Een
skelet dat een verkeerde reden geeft, is schadelijker dan een skelet zonder
reden — het rapport leest als iets wat geverifieerd is.

## Code review

Na het bouwen is een review over de hele wijziging gedraaid. Die leverde tien
bevindingen op; alle tien zijn verwerkt. De belangrijkste:

1. **De registerdrift-bewaking was buiten deze machine inert.** `data/` stond in
   `.gitignore`, dus het checkregister zat niet in versiebeheer — en daarmee kon
   geen enkele geautomatiseerde controle zien dat het opschoof. Erger: de commit
   die "het checkregister bijgewerkt" heette, bevatte alleen de dekkingsmatrix.
   `.gitignore` maakt nu een uitzondering voor `data/checkregister-*.md`; de grote
   en externe bestanden blijven eruit. **Dit is een wijziging aan een projectkeuze
   en verdient een expliciet akkoord**; één regel draait hem terug.
2. **De HGT-tests raakten de verkeerde tak.** Elke put in de scenariofixture had
   een `Putdekselniveau`, dus de kanttekening werd altijd via de dekselwaarde
   getest en nooit via de maaiveldhoogte plus de Punt-terugval — precies het pad
   dat op De Wolden draait, waar géén enkele put een dekselniveau heeft. Put E in
   de fixture heeft nu geen deksel en een maaiveldhoogte uit AHN2.
3. **De discrepantieclaim was te stellig.** "Kan niet aan schone data liggen" is
   waar, maar het verschil kan ook uit een ongelijk gedraaide meting komen. Het
   kopblok noemt `Gevalideerd op onderdelen` en `Niet gevalideerd op`; die worden
   nu vergeleken, en het rapport zegt expliciet welke van de twee verklaringen
   overblijft. Voor De Wolden zijn de drie rapporten identiek gedraaid, dus open
   punt 11 blijft staan.
4. **De kolom "Met inwinningswijze" mengde twee definities.** De maaiveldrij las
   de herkomst mét Punt-terugval, de andere rijen zonder. Nu leest elke rij hem
   zoals de rest van de pijplijn hem leest.
5. **De dekseltak van de kanttekening miste de terugval.** Voor een export die wél
   een `Putdekselniveau` levert met de BrutIS-conventie zou de kanttekening
   stilzwijgend nooit vuren — exact de fout die de terugval een niveau hoger juist
   voorkomt. `_deksel_kenmerk` doet nu hetzelfde als `_maaiveld_kenmerk`.
6. **Een test bewees niets.** De configureerbaarheid van de onbekend-lijst werd
   getoetst met een waarde die toevallig hetzelfde getal opleverde als de
   standaard. De test beweegt nu mee (leeg → 0, beide waarden → 2).
7. **De "dekking vervallen"-tak in het rapport was onbereikbaar.** Beide commando's
   faalden hard vóór er iets geschreven werd. Nu faalt alleen `dekking` hard —
   daar ís de dekkingclaim het onderwerp — en meldt `analyseer` de drift in de
   samenvatting, zodat de lezer een rapport houdt dat zelf zegt wat eraan mankeert.
8. **Het AHN-raster werd drie keer per check bemonsterd.** De bemonstering staat nu
   in de contextcache, waar de topologie-index en de netwerkgraaf ook staan.
9. **Een getal klopte niet.** De toelichting van BTR-001 gaf 5.104 als
   terugvalaantal; dat is de AHN2-telling. Via de terugval komen er 5.175 binnen
   (5.104 AHN2 plus 71 andere wijzen), en 4.875 staan op het kenmerk zelf.
10. **De datakarakteristieken tellen over de volledige dataset**, terwijl ze onder
    de studiegebied-afbakening staan. Bij een afgebakend rapport staat dat er nu
    expliciet bij.

Bevindingen 2, 3, 5, 6, 7 en 9 waren echte fouten in mijn werk, geen stijlpunten.
Vier daarvan gingen over tests of teksten die iets beweerden wat ze niet
aantoonden — precies het soort fout dat een groene suite verbergt.

## Verificatie

- `pytest`: 524 geslaagd, 3 gedeselecteerd (marker `zwaar`).
- `ruff check` en `ruff format`: schoon.
- `dekking` en `toets` gedraaid op de volledige De Wolden-bestanden; de
  registerdrift-bewaking is met een gewijzigde versie in de mapping op falen
  getest (exitcode 1, expliciete melding).
- `docs/dekkingsmatrix.md` opnieuw gegenereerd; de test die op achterlopen faalt,
  is groen.

De cijfers in dit verslag zijn tweemaal onafhankelijk geteld: eerst rechtstreeks
op de Turtle-tekst, daarna via de ingeladen dataset met de totaalontologie. Ze
komen exact overeen:

| Meting | rauwe telling | via de lader |
| --- | ---: | ---: |
| knopen met maaiveldhoogte | 22.363 | 22.363 |
| maaiveldhoogte met inwinningswijze | 10.050 | 10.050 |
| waarvan AHN2 | 5.104 | 5.104 |
| waarvan NietAchterhaald | 1.351 | 1.351 |
| `Begindatum`, alle op 1 januari | 33.477 | 33.477 |
| BOB beginpunt met wijze | 266 | 266 |
| BOB eindpunt met wijze | 271 | 271 |
| `Putdekselniveau` | 0 | 0 |
