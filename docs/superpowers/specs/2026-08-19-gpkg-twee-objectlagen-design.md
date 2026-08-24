# Ontwerp: twee objectlagen met status en popup (issue #13)

Datum: 2026-08-19. Bron: issue #13 op `mcolee/nlriochecker` plus de grillsessie van
diezelfde dag. De vastgelegde ontwerpbesluiten uit het issue zijn hier niet heropend;
dit document legt vast wat de issuetekst openliet.

## Wat er nu staat

De GeoPackage draagt zes featurelagen: `putten`, `strengen`, `meldinglocaties`,
`mechanisch_riool`, `bouwwerken` en `waterdelen_zonder_zinker`. Alleen objecten
binnen de kern van het studiegebied komen erin; de contextschil valt weg.

## Wat het wordt

Twee objectlagen — `putten` (punt) en `strengen` (lijn) — met de gebreken *op* het
object. `meldinglocaties` vervalt als featurelaag, `mechanisch_riool` gaat op in
`strengen`. `bouwwerken`, `waterdelen_zonder_zinker`, `meldingen`, `overzicht_checks`
en `gwsw_run` blijven.

## De openstaande keuzes, en hoe ze vallen

### K1. Telt de contextschil mee, en met welke status?

Het issue noemt bij `grijs` letterlijk "object in de schil (niet de kern)". Dat kan
alleen als de schil ook in de laag staat, en vandaag staat hij er niet in.

**Besluit: er komt een grijze ring om het gebied.** Hem weglaten laat de kaart bij de
gebiedsgrens ophouden alsof daar niets ligt.

**Herzien na review: de ring is `Analyseset.buffer`, niet de hele schil.** De schil
bevat naast de buffer ook de samenhangende vrijvervalcomponent waar de kern in ligt, en
die kan in een stad het halve net zijn. Elk van tachtig buurtbestanden zou dan het net
van de hele stad als grijze achtergrond meesturen, met een popup van bijna een kilobyte
per object, en hetzelfde object zou groen zijn in zijn eigen buurtbestand en grijs in
dat van de buurman. De buffer is precies wat een lezer om zijn gebied heen ziet liggen
en is naar constructie begrensd. Op Koekangerveld gaat het om 3 objecten naast 98 in de
kern.

De equivalentie-eis (BO-12) blijft staan: de buffer van een gebied is per constructie
dezelfde in een meervoudige run als in een losse run over dat ene gebied.

Zonder studiegebied is er geen schil en verandert er niets: elk object is dan kern.

### K2. Wat doet `status` met systemische meldingen?

Dit is de scherpste keuze van dit issue. Op De Wolden draagt de nulmeting 105.963
meldingen, waarvan 68.882 systemisch — vormen die vrijwel elke inspectieput raken. Zou
`status` die meetellen, dan is vrijwel elke put rood en zegt de kaart niets meer.

De bestaande kolommen `ergste_ernst`, `n_fout` en `n_waarschuwing` tellen systemische
meldingen al niet mee, precies om die reden (zie de kop van `putten.qml`).

**Besluit: `status` volgt dezelfde regel als `ergste_ernst`.** Rood bij minstens één
niet-systemische F-melding, oranje bij alleen niet-systemische W-meldingen, groen als
er geen niet-systemische melding is.

**Gevolg dat je moet kennen:** een object waarvan álle meldingen systemisch zijn krijgt
`groen`. Dat betekent hier "geen gebrek dat dit object van zijn buren onderscheidt", niet
"in orde". Op de Koekangerveld-run geldt dat voor alle 27 groene putten, dus het is de
regel en niet de uitzondering. Drie dingen vangen het op: de kolom `n_systemisch` staat
er al en blijft gevuld, de popup zet er een regel onder die zegt hoeveel meldingen niet
meetellen en waarom, en de legenda van de QML zegt "geen eigen gebrek" in plaats van
"in orde" (issue #14).

**Herzien na review: grijs wint niet van een gebrek.** De aanname dat mechanisch riool
ongetoetst blijft, klopt niet: TOP-010 en TOP-011 draaien er wel op en de SHACL-nulmeting
sowieso. Op de Koekangerveld-run dragen 17 van de 20 mechanische strengen een melding.
Zouden die grijs blijven, dan zou de kaart beweren dat er niets bekeken is terwijl er
fouten op staan -- en sinds `meldinglocaties` verviel is er geen tweede plek meer waar ze
wel zichtbaar zijn. `grijs` betekent daarom: niet beoordeeld **en niets gevonden**. Wat
er wel gevonden is kleurt het object, en de popup zegt erbij dat het maar deels
beoordeeld is en waarom.

### K3. Waar wordt `popup_html` gerenderd?

In een eigen module `src/nlriochecker/uitvoer/objectkaart.py`, aangeroepen door
`gpkg.py`. Niet in `gpkg.py` zelf: dat bestand telt al ruim duizend regels, en de
opmaak van een popup is een ander soort werk dan het schrijven van een GeoPackage.
Het blijft binnen `uitvoer/`, dus de kolom komt nog steeds uit de ene meldingenstroom
en er komt geen tweede schrijver bij.

### K4. Wat er in de popup staat, en wat niet

Kopregel: label, GWSW-objecttype en de status in woorden. Bij een streng ook het
stelsel, de lengte en de BOB-richtingsregel uit `richting_bob` — de logica daarvan
blijft ongewijzigd (issue #14 verandert alleen de weergave).

Daaronder maximaal vijf meldingen, gesorteerd op systemisch, dan prioriteit, dan
check-ID -- die eerste sleutel is na review toegevoegd, omdat een rood object anders
vijf systemische nulmetingmeldingen kon tonen en de fout die hem rood maakte achter "en
nog N andere" verstopte (6 van de 44 gekleurde objecten op de Koekangerveld-run). Elk
met ernst-symbool (`✕` / `⚠`), check-ID, boodschap en een herkomst-tag: `nulmeting ·
MdsPlan` (met de conformiteitsklassen uit `cfk`) of `eigen check`. Waarde en drempel
alleen als ze gevuld zijn. Zijn er meer dan vijf, dan sluit een regel af met "… en nog
N andere".

Een grijs object noemt in de popup **waarom** het niet beoordeeld is: mechanisch riool
of contextschil. Daar komt geen eigen kolom voor — het issue vraagt precies vier
statuswaarden, en een vijfde kolom om die te verbijzonderen zou de kaartlegenda niet
helpen.

De HTML wordt geëscaped voordat hij de kolom in gaat: labels en boodschappen komen uit
de brondata en mogen de popup niet kunnen breken.

De klassenamen zijn kort (`k`, `l`, `t`, ...). De markup staat per object in de
GeoPackage, de stijl staat er een keer in de QML; wat een teken scheelt, scheelt op de
volledige export tienduizenden keren zoveel. Gemeten op de Koekangerveld-run: 1.284
bytes per object met lange namen en 1.085 met korte, wat op de 46.925 objecten van de
volledige export neerkomt op circa 60 tegen circa 51 MB alleen aan `popup_html`. De rest
is de boodschaptekst, en die valt niet in te korten zonder er informatie uit te halen.

### K5. Wat er met de tellingen in `gwsw_run` gebeurt

`n_putten` en `n_strengen` betekenen wat ze altijd betekend hebben: het aantal rijen
dat er werkelijk in die laag staat. Doordat de laag nu ook mechanisch riool en de
contextschil bevat, zijn dat er meer dan voorheen. `n_mechanisch` blijft staan en telt
hoeveel van die lijnen mechanisch riool zijn. Er komt geen kolom bij: wie het per status
wil weten, telt `select status, count(*) from strengen group by status` — dat is precies
waarvoor de kolom er is.

### K6. Wat er verloren gaat

De laag `meldinglocaties` vervalt. Twee dingen verdwijnen daarmee van de kaart: de
exacte foutlocatie op een lijn (het snijpunt van een kruising, het midden van een
streng) en het naloopwerk in een kaal GIS-pakket zonder joins. De meldingen zelf
blijven volledig in de tabel `meldingen`, joinbaar op `feature_id`. Die tabel krijgt de
kolommen `x` en `y` met diezelfde foutlocatie -- anders zou hij stilzwijgend uit de
GeoPackage verdwijnen terwijl de CSV hem als `X`/`Y` en de JSON hem als `foutlocatie`
wel draagt. Objectloze meldingen — dataset-breed,
EXT-verwijzingen zonder rioolobject, de onherleide focusnodes uit issue #12 — stonden
ook voorheen niet op die laag en blijven zichtbaar in rapport en meldingentabel.

Dat verlies hoort in de CHANGELOG te staan, met de plek waar de informatie bleef.

## Wat er niet in deze stap zit

De symbology (issue #14) en de maptip (issue #15). Dit issue levert de kolommen
`status` en `popup_html`; de QML's blijven voorlopig op `ergste_ernst` en
`richting_bob` filteren, met de twee vervallen lagen eruit.
