# Fase 4 — eindverslag

Opgeleverd 2026-08-16. Dit verslag beschrijft wat er gebouwd is, wat er skelet
gebleven is en waarom, en wat de eerste run op de echte data laat zien. De
onderbouwing van de keuzes staat in `docs/beslislog.md`, de stand per check-ID in
`docs/dekkingsmatrix.md`, de bronnen in `docs/gis-inventarisatie.md` en het
NWB-voorstel in `docs/nwb-voorstel.md`.

## Stand van zaken

Het checkregister v0.7 telt 93 regels: 87 actieve checks en 6 geschrapte. **Alle 87
actieve checks zijn geïmplementeerd en hebben een test.** Er staat geen enkel ID meer
op *ontbreekt*.

| Categorie | Register | Geïmplementeerd met test | Geschrapt | Waarvan skelet |
| --- | ---: | ---: | ---: | ---: |
| TOP | 21 | 21 | 0 | 0 |
| ADM | 9 | 6 | 3 | 0 |
| ATTR | 12 | 11 | 1 | 0 |
| HGT | 18 | 18 | 0 | 0 |
| NET | 8 | 8 | 0 | 0 |
| RVZ | 11 | 9 | 2 | 0 |
| BTR | 6 | 6 | 0 | 5 |
| EXT | 8 | 8 | 0 | 1 |
| **totaal** | **93** | **87** | **6** | **6** |

De matrix wordt gegenereerd uit het register, de registry van de engine en de
testsuite (`scripts/dekkingsmatrix.py`), en er is een test die faalt zodra het
bestand achterloopt. De ernst en de dimensietag van elke check worden bij elke
testrun tegen het register gecontroleerd.

## Wat er per blok gebouwd is

**Blok 0 — TOP en NET compleet.** TOP-006 t/m TOP-011 en TOP-013 t/m TOP-021,
NET-003, NET-005, NET-006 en NET-008. Daarvoor is de dataset uitgebreid met
multipart-herkenning en met z-waarden op de strenggeometrie.

**Blok A — de interne checks.** ATTR-001 t/m ATTR-012, HGT-004 t/m HGT-018, RVZ-001
en RVZ-004 t/m RVZ-011, ADM-002, ADM-003, ADM-006 t/m ADM-009, en BTR-006. De
GWSW-kenmerken (materiaal, diameter, vorm, aanlegjaar, hoogten, inwinning) worden nu
bij het inlezen als aspecten aan knopen en strengen gehangen.

**Blok C — de externe bronnen.** EXT-001 t/m EXT-003 en EXT-005 t/m EXT-008, plus
HGT-001 t/m HGT-003 tegen het AHN5-DTM. De bronnenlaag (`externedata.py`) leest
GeoPackages met geopandas en het raster met rasterio, bewaakt het CRS en levert een
begrenzingspolygoon waarbinnen de checks mogen oordelen.

## Wat skelet gebleven is, en waarom

| ID | Markering | Reden |
| --- | --- | --- |
| BTR-001 | vereist inwinningsmetagegevens | De export bevat wel `WijzeVanInwinning` (circa 25.500 keer) maar op de puntgeometrie, niet op de BOB's, het dekselniveau of het drempelniveau. Er is geen enkele `DatumInwinning`. |
| BTR-002 | vereist inwinningsmetagegevens | Idem; wel bouwbaar zodra er een export met inwinning op de hoogtekenmerken is. |
| BTR-003 | vereist inwinningsmetagegevens | Geen `DatumInwinning`, en geen grondsoortenkaart om de drempel (zand 40 jaar, veen 10 jaar) op te differentiëren. |
| BTR-004 | vereist inwinningsmetagegevens | Geen enkel `Grondwaterniveau`-kenmerk in de export. |
| BTR-005 | vereist inwinningsmetagegevens | Geen inspectie- of toestandsgegevens; de weging naar risicoligging vraagt bronnen die niet aangeleverd zijn. |
| EXT-004 | bron buiten scope in deze fase | BRK-percelen zijn niet aangeleverd en er is geen vervangende bron gezocht. De bufferafstand staat wel al in de config. |

Skeletten leveren nul bevindingen op **met** de markering en de reden in het rapport.
Een check die er niet is leest anders als een check zonder bevindingen; dat is precies
het verschil dat een skelet zichtbaar maakt.

Daarnaast draaien twee volledig gebouwde checks niet op déze data:

- **EXT-005 en EXT-006** — de BGT-laag `put` (de putdeksels) bestaat wel maar bevat
  nul features. Beide melden *laag niet aanwezig in aangeleverde data*, met
  `examined = 0`, en draaien zonder wijziging zodra er een gevulde export komt.

## Eerste run op De Wolden

Volledige dataset (23.485 knooppunten, 23.440 strengen), totaalontologie geladen,
externe bronnen erbij, geen typeringspoort en geen afbakening. Laden duurt circa
vier minuten; alle 87 checks samen daarna circa anderhalve minuut.

**36.012 bevindingen in totaal.** Afgebakend tot Koekangerveld blijven er **113**
over — een getal dat vooral zegt hoe klein het studiegebied is ten opzichte van de
dataset, niet hoe schoon de kern is.

| Check | Bev. | Bekeken | Check | Bev. | Bekeken | Check | Bev. | Bekeken |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: |
| TOP-001 | 102 | 22363 | ATTR-001 | 19 | 17603 | HGT-009 | 327 | 22363 |
| TOP-002 | 56 | 17603 | ATTR-002 | 1047 | 17603 | HGT-010 | 525 | 22363 |
| TOP-003 | 109 | 17603 | ATTR-003 | 27 | 17603 | HGT-011 | 0 | 22363 |
| TOP-004 | 24 | 17603 | ATTR-004 | 0 | 17603 | HGT-012 | 0 | 22363 |
| TOP-005 | 112 | 22363 | ATTR-005 | 0 | 17603 | HGT-013 | 2545 | 17603 |
| TOP-006 | 197 | 23440 | ATTR-006 | 51 | 17603 | HGT-014 | 889 | 17603 |
| TOP-007 | 7 | 23440 | ATTR-007 | 0 | 38361 | HGT-015 | 0 | 22363 |
| TOP-008 | 95 | 17603 | ATTR-008 | 12 | 17603 | HGT-016 | 0 | 22363 |
| TOP-009 | 0 | 45803 | ATTR-009 | 1 | 17603 | HGT-017 | 0 | 39966 |
| TOP-010 | 2551 | 23440 | ATTR-010 | 0 | 17603 | HGT-018 | 1190 | 17603 |
| TOP-011 | 2237 | 23440 | ATTR-012 | 0 | 17603 | NET-001 | 9062 | 17451 |
| TOP-012 | 0 | 17603 | ADM-002 | 0 | 45803 | NET-002 | 3054 | 17451 |
| TOP-013 | 140 | 23440 | ADM-003 | 0 | 0 | NET-003 | 3725 | 17451 |
| TOP-014 | 51 | 22363 | ADM-006 | 0 | 45803 | NET-004 | 17 | 17451 |
| TOP-015 | 0 | 45803 | ADM-007 | 181 | 273 | NET-005 | 24 | 17451 |
| TOP-016 | 0 | 45803 | ADM-008 | 0 | 22363 | NET-006 | 410 | 17345 |
| TOP-017 | 7 | 23440 | ADM-009 | 0 | 0 | NET-007 | 340 | 17451 |
| TOP-018 | 8 | 23440 | RVZ-001 | 1 | 245 | NET-008 | 11 | 17345 |
| TOP-019 | 0 | 1064 | RVZ-004 | 0 | 245 | BTR-006 | 0 | 57569 |
| TOP-020 | 6 | 17603 | RVZ-005 | 71 | 245 | HGT-004 | 532 | 17603 |
| TOP-021 | 5 | 22363 | RVZ-006 | 87 | 794 | HGT-005 | 1286 | 17603 |
| | | | RVZ-010 | 2 | 68 | HGT-006 | 2459 | 17603 |
| | | | RVZ-007/8/9/11 | 0 | 0 | HGT-007 | 2126 | 17603 |
| | | | | | | HGT-008 | 247 | 17603 |

De EXT- en AHN-checks staan in de volgende paragraaf; die draaien op een ander
bereik. Checks met `Bekeken = 0` hebben niets kunnen toetsen: ADM-003 zonder
naamgevingspatroon, ADM-009 zonder gecompartimenteerde putten, RVZ-007 t/m RVZ-009
en RVZ-011 zonder bergbezinkvoorzieningen en zonder drempels, en de vijf
BTR-skeletten.

### Wat opvalt, en wat het waarschijnlijk betekent

**De richting van het net is het grootste probleem.** NET-003 meldt dat bij 3.725 van
de 17.451 strengen in de graaf (21%) de bodem *stijgt* in de administratieve
van-naar-richting. HGT-005 en HGT-006 zien hetzelfde verschijnsel als tegenverhang
(1.286 licht, 2.459 fors). Dat zijn geen 3.725 losse gebreken maar één systematisch
patroon: de van-naar-richting in de export is voor een vijfde van het net niet de
afvoerrichting. Dit raakt ook NET-001 en NET-002, die de richting volgen. De
projectconfig heeft er een knop voor (`netwerk.richting = "bob"`), maar die zet de
oorzaak niet recht; hij verplaatst hem naar de BOB-kwaliteit.

**NET-001 (9.062 strengen zonder afvoerpad) bevestigt het openstaande punt uit
CLAUDE.md.** De check meldt zelf hoeveel knopen in een deel liggen dát wel een
eindpunt heeft maar het niet bereikt in de gevolgde richting. Zolang die 21%
richtingsprobleem er ligt, is dit cijfer geen maat voor het aantal doodlopende
strengen.

**TOP-010 (2.551) en TOP-011 (2.237) zijn tweedimensionaal.** Leidingen kruisen
elkaar in vrijwel elke straat op verschillende diepte. Beide checks zeggen dat nu in
hun toelichting en verwijzen naar HGT-004, HGT-009 en HGT-018 om te bepalen welke
kruisingen echt conflicteren. Het register kent TOP-010 als fout; dat is voor een
platte kruising streng, en het aantal moet zo gelezen worden.

**ATTR-002 (1.047 strengen onder 200 mm) gaat grotendeels over drains en
aansluitleidingen.** De check geeft nu een verdeling naar klasse in haar toelichting;
die klassen zijn van nature dunner dan 200 mm. Dat zegt meer over de klasse-indeling
dan over een gebrek.

**ADM-007 (181 van 273) is een registratiepatroon, geen 181 gebreken.** De export
bevat 218 overstortputten tegenover 68 overstortleidingen en nul overstortdrempels;
bij de meeste overstortputten is de overstortfunctie dus simpelweg niet als object
geregistreerd.

**Vier HGT-checks konden niets toetsen.** HGT-011 (drempel), HGT-012 (putdiepte),
HGT-015 en HGT-016 (putbodem) staan alle op nul bevindingen, en dat betekent hier
niet dat het in orde is: de export bevat geen `HoogtePut`, geen `Putdekselniveau` en
geen `Drempelniveau`. De checks melden dat in hun toelichting. Waar het register over
dekselhoogte spreekt gebruikt de engine de `Maaiveldhoogte` als benadering; welke van
de twee gebruikt is staat in elke bevinding.

**BTR-006 vindt geen systematische afronding.** Van de 57.569 hoogtewaarden (BOB's en
maaiveldhoogten) valt te weinig op een raster van 5 cm om van geschatte waarden te
spreken. De BOB's staan op millimeternauwkeurigheid genoteerd.

**TOP-009 vindt geen coördinaat buiten het RD-bereik**, en TOP-015 en TOP-016 geen
multipart- of ongeldige geometrie. De geometrische basis van de export is op die
punten in orde.

## Eerste run op Koekangerveld (externe bronnen)

De externe bronnen dekken 43,2 ha; de GWSW-dataset de hele gemeente. Van de 17.603
vrijvervalstrengen liggen er **29** binnen het studiegebied, van de 22.363 putten
**40**. Al het andere krijgt de status *buiten studiegebied* en geen uitslag — dat is
de belangrijkste uitkomst van dit blok en staat in de toelichting van elke check.

| Check | Bevindingen | Bekeken | Opmerking |
| --- | ---: | ---: | --- |
| EXT-001 | 1 | 29 | streng langs of door een BGT-pand of bouwwerk |
| EXT-002 | 1 | 29 | kruising met een BGT-waterdeel |
| EXT-003 | 1 | 29 | diezelfde kruising, niet als zinker of duiker geregistreerd |
| EXT-004 | — | 0 | skelet, BRK niet aangeleverd |
| EXT-005 | — | 0 | overgeslagen, BGT-laag `put` leeg |
| EXT-006 | — | 0 | idem |
| EXT-007 | 2 | 2 | beide lozingspunten in het gebied liggen verder dan 10 m van een BGT-waterdeel |
| EXT-008 | 16 | 166 | BAG-panden zonder streng of put binnen 40 m |
| HGT-001 | 15 | 40 | dekselhoogte 5 tot 25 cm van het AHN5 |
| HGT-002 | 0 | 40 | geen enkele put wijkt meer dan 25 cm af |
| HGT-003 | 1 | 40 | BOB boven het AHN-maaiveld of meer dan 3 m eronder |

Dat HGT-002 nul oplevert en HGT-001 vijftien is een gunstig beeld: de
maaiveldhoogten in de export sluiten goed aan op het AHN5. Wel telt mee dat de
export geen `Putdekselniveau` bevat, zodat hier de `Maaiveldhoogte` met het DTM
vergeleken wordt — twee grootheden die dichter bij elkaar liggen dan deksel en
maaiveld zouden doen.

De 16 BAG-panden zonder riolering binnen 40 m verdienen navolging, met twee
kanttekeningen: er zijn panden aangeleverd en geen verblijfsobjecten (een pand met
meerdere woningen telt als één), en een pand aan een particuliere uitweg kan
legitiem via een niet-geregistreerde aansluiting lozen.

## Wat de engine nadrukkelijk *niet* heeft bekeken

- Het **beheergebied** (TOP-009): er is geen beheergebiedpolygoon; alleen het
  RD-bereik is getoetst.
- **Duplicaat-ID's in de bronexport** (ADM-002): die smelten in de RDF-conversie
  samen tot één subject en zijn in de OroX-dataset niet meer te zien. Alleen
  verschillende subjecten met hetzelfde `rdfs:label` komen naar voren.
- De **naamgevingsconventie** (ADM-003): er is geen projectpatroon geconfigureerd,
  dus de check draait niet. Een verzonnen patroon zou elke dataset afkeuren.
- **Pseudo-knopen** (TOP-019): alleen op de expliciet als functieloos aangemerkte
  knoopklassen. In een rioolstelsel zit op vrijwel elke knik een put, en een put is
  een functie.
- **Waterschapsdata** (EXT-002): niet aangeleverd; alleen BGT-waterdelen zijn
  gebruikt, wat het register expliciet toestaat.
- **Alles buiten Koekangerveld** voor de EXT- en AHN-checks.

## Aanbevelingen voor een volgende fase

1. **Zoek de oorzaak van de 21% tegendraadse richting** voordat NET-001 en NET-002
   als kwaliteitscijfer gebruikt worden. Is het de export, de conversie of de
   bronadministratie? Zolang dat open staat zijn die twee cijfers niet te duiden.
2. **Vraag de ontbrekende hoogtekenmerken op** (`Putdekselniveau`, `HoogtePut`,
   `Drempelniveau`). Vier HGT-checks en twee RVZ-checks kunnen nu niets toetsen.
3. **Vraag een BGT-export met gevulde `put`-laag.** EXT-005 en EXT-006 zijn klaar en
   wachten alleen op data.
4. **Vraag inspectiegegevens** voordat de BTR-categorie zin heeft; dan wordt ook de
   NWB bruikbaar als weegfactor (zie `docs/nwb-voorstel.md`).
5. **Herzie `plausibiliteit.toml` samen met de beheerder.** De tabellen zijn een
   werkafspraak, geen norm; de 19 ATTR-001-bevindingen en 27 ATTR-003-bevindingen
   staan of vallen ermee.
6. **Overweeg de typeringspoort overal als uitsluitingsgrond**, zoals nu bij de
   EXT-checks. Dat is een bewuste breuk met fase 3 en hoort een expliciete keuze in
   de config te worden.
