# Checkregister GWSW-nulmeting vrijverval

Versie 0.9, werkdocument (RVZ-002 en RVZ-003 terug in de engine, ATTR-013 toegevoegd, EXT-003 gepreciseerd d.d. 2026-08-19; afbakening tot een studiegebied toegevoegd d.d. 2026-08-16; EXT-008 vervallen). Scope: vrijvervalriolering inclusief randvoorzieningen (bergbezinkbassins, overstorten, drempels). Buiten scope: mechanische riolering en gemalen als object; gemalen en overnamepunten tellen wel mee als eindpunt in de netwerkanalyse. Bronnen: Brutis/Kikker-export (GWSW), AHN, BGT, BAG, BRK, waterschapsdata. Ernst: F = fout, W = waarschuwing. Elke check heeft een dimensietag conform het kwaliteitsraamwerk Omgevingswet/NORA (RIONED-kennisbank, Kwaliteit van gegevens). Alle drempelwaarden zijn configureerbaar per project.

De dataset wordt aan twee GWSW-conformiteitsklassen getoetst: Mds en Hyd (deelmodellen v1.6, filters collectie_MDSTOP_v16 respectievelijk collectie_HYDTOP5_v16). Checks die deze nulmetingen aantoonbaar dekken zijn geschrapt; zie de tabel Geschrapte checks onderaan. Vervallen ID's worden niet hergebruikt. Let op: de verplichte aanwezigheid van de administratieve put-strengkoppeling rust volledig op Hyd (in Mds is de koppeling optioneel, max=1); het gelijktijdig toetsen van beide conformiteitsklassen is daarmee een harde voorwaarde voor de geldigheid van de schrapronde.

## Afbakening van een analyse

Een toets kan tot een studiegebied beperkt worden. De pijplijn analyseert dan niet de
volledige export en ook niet alleen het gebied zelf, maar een analyseset:

- **kern** — de objecten waarvan de geometrie het studiegebied raakt; hierover, en alleen
  hierover, wordt gerapporteerd;
- **contextschil** — de samenhangende vrijvervalcomponenten die de kern raken, plus alle
  objecten binnen een instelbare buffer om het gebied.

De component is nodig omdat NET-001, NET-002, NET-004, NET-005 en NET-006 over een
samenhangend net redeneren: zonder de rest van de component zou een streng die het gebied
uit loopt ten onrechte als doodlopend gelden. De buffer is nodig voor de checks die naar
nabijheid kijken zonder netwerkverband: TOP-005, TOP-006, TOP-010, TOP-011, TOP-021 en de
EXT-checks. Mechanische leidingen doen bewust niet mee aan de component; ze verbinden
deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen, terwijl de
NET-checks ze niet volgen.

Checks die over de hele populatie gaan in plaats van over losse objecten — ADM-002, unieke
identificaties — draaien altijd op de volledige export. Welke dat zijn is configureerbaar.
Het rapport meldt per run hoeveel objecten er in de kern zitten, hoeveel in de schil en
hoeveel de export in totaal telt.

Mechanische riolering (persleiding, drukleiding, vacuumleiding) blijft buiten scope, zoals
de inleiding al zegt. In de GIS-uitvoer staat ze in een eigen laag met de aanduiding
"Mechanisch riool: niet geanalyseerd", zodat een leeg kaartbeeld daar niet als "geen
gebreken" leest.

## TOP: Topologie en geometrie

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| TOP-001 | Losliggende putten (geen enkele streng aangesloten); geometrische variant, de administratieve koppeling dekt de nulmeting (verplichting exact=1 komt uitsluitend uit Hyd; Mds staat ontbreken toe) | F | Consistentie |
| TOP-002 | Losliggende strengen (aan geen van beide zijden een put); geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie |
| TOP-003 | Streng met slechts aan een zijde een put; geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie |
| TOP-004 | Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie) | F | Consistentie |
| TOP-005 | Dubbele putten: twee knopen binnen tolerantie (bijv. 0,30 m) | F | Compleetheid |
| TOP-006 | Dubbel ingetekende of (deels) overlappende strengen | F | Compleetheid |
| TOP-007 | Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie | F | Consistentie |
| TOP-008 | Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put) | F | Consistentie |
| TOP-009 | Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten | F | Nauwkeurigheid |
| TOP-010 | Streng met buffer op basis van diameter kruist of raakt andere strengen | F | Plausibiliteit |
| TOP-011 | Hartlijnkruisingen strengen onderling (zonder buffer) | W | Plausibiliteit |
| TOP-012 | Streng met dezelfde put aan begin- en eindpunt | F | Consistentie |
| TOP-013 | Meer dan twee parallelle strengen tussen hetzelfde putpaar | W | Plausibiliteit |
| TOP-014 | Meer dan vier aansluitende strengen op een put | W | Plausibiliteit |
| TOP-015 | Streng of put met multipart-geometrie (meerdere losse delen in een feature) | F | Consistentie |
| TOP-016 | Ongeldige geometrie volgens OGC Simple Features (ST_IsValid: zelf-intersectie, niet-gesloten ringen) | F | Consistentie |
| TOP-017 | Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren) | W | Consistentie |
| TOP-018 | Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie | W | Consistentie |
| TOP-019 | Pseudo-knoop: twee strengen gescheiden door een functieloze knoop, met identieke attributen (diameter, materiaal, stelseltype); zouden een streng moeten zijn | W | Consistentie |
| TOP-020 | Digitalisatierichting (begin- naar eindvertex) komt niet overeen met de administratieve van-naar-richting | W | Consistentie |
| TOP-021 | Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een doorlopende streng (verfijning van TOP-001) | W | Consistentie |

## ADM: Administratief en referentieel

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| ADM-002 | Niet-unieke identificaties van putten of strengen; uitvoeren op de bronexport, voor de OroX-conversie (duplicaat-ID's smelten in RDF geruisloos samen) | F | Consistentie |
| ADM-003 | Naamgeving knopen en strengen wijkt af van conventie (patroon configureerbaar) | F | Compliance |
| ADM-006 | Vervallen of geplande objecten die topologisch meedoen in het actieve netwerk | W | Consistentie |
| ADM-007 | Puttype past niet bij het type aangesloten leiding (bijv. overstortput zonder overstortfunctie in het netwerk); netwerkfunctionele toets, de samenstellingsregels per puttype dekt de nulmeting | F | Consistentie |
| ADM-008 | Putcompartimenten of -onderdelen zonder onderlinge verbinding binnen de put | W | Consistentie |
| ADM-009 | Leiding gekoppeld aan de put als geheel waar koppeling aan een compartiment vereist is | W | Consistentie |

## ATTR: Attribuutplausibiliteit

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| ATTR-001 | Diameter past niet bij materiaal | F | Plausibiliteit |
| ATTR-002 | Diameter kleiner dan rond 200 mm (de nulmeting toetst alleen de extreme ondergrens van 63 mm) | W | Plausibiliteit |
| ATTR-003 | Materiaal past niet bij aanlegjaar (bijv. PVC voor 1955, PE voor 1970) | W | Plausibiliteit |
| ATTR-004 | Vorm versus afmetingen inconsistent (eivorm zonder hoogte, rond met breedte ongelijk hoogte); NB het MDSTOP-deelmodel dwingt de aanwezigheid van breedte en hoogte per leiding af (someValuesFrom in de Top-laag), Hyd verplicht breedte exact=1; de consistentietoets vorm versus afmetingen doet geen van beide | F | Consistentie |
| ATTR-005 | Eenhedenfouten die binnen de GWSW-waardebereiken vallen (bijv. diameter 300 genoteerd in cm); fouten buiten bereik dekt de nulmeting | F | Nauwkeurigheid |
| ATTR-006 | Strengdiameter groter dan afmeting van de aangesloten put | W | Plausibiliteit |
| ATTR-007 | Aanlegjaar in de toekomst of voor 1870 (de nulmeting toetst alleen datatype, geen bereik) | W | Plausibiliteit |
| ATTR-008 | Strenglengte korter dan X m of langer dan X m | W | Plausibiliteit |
| ATTR-009 | Geometrische lengte wijkt meer dan X% af van administratieve lengte | W | Consistentie |
| ATTR-010 | Leidingmateriaal beton of metselwerk terwijl het putmateriaal daar niet bij past | W | Plausibiliteit |
| ATTR-012 | Materiaal past niet bij profielvorm (bijv. metselwerk met rond profiel in plaats van ei- of muilprofiel) | W | Plausibiliteit |
| ATTR-013 | Hoogtekenmerk (BOB, maaiveldhoogte, putdekselniveau) op een vulwaarde rond 0 m NAP dat als meting geregistreerd staat; de band en de kenmerken zijn projectconfiguratie (`[vulwaarden]`), de leesregel zet het kenmerk op ontbrekend en de hoogtechecks slaan het object over | W | Compleetheid |

## HGT: Hoogten en verhang

Hyd dwingt het bestaan van alle benodigde hoogtedata af (BOB begin- en eindpunt min=1, maaiveldhoogte, drempelniveau); Mds dwingt daarvan maaiveldhoogte, putdekselniveau en drempelniveau af, maar laat de BOB's optioneel (min=0). Deze categorie toetst uitsluitend de waarde-logica.

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| HGT-001 | Dekselhoogte wijkt af van AHN: meer dan 5 cm; is de gebruikte hoogte zelf uit een hoogtemodel ingewonnen, dan vergelijkt de check twee modellen en krijgt de bevinding een kanttekening (wijzen configureerbaar) | W | Nauwkeurigheid |
| HGT-002 | Dekselhoogte wijkt af van AHN: meer dan 25 cm; zelfde kanttekening als HGT-001 | F | Nauwkeurigheid |
| HGT-003 | BOB-sanity ten opzichte van AHN (boven maaiveld, meer dan 3 m eronder) | F | Plausibiliteit |
| HGT-004 | BOB hoger dan dekselhoogte van de eigen put, of lager dan de putbodem | F | Consistentie |
| HGT-005 | Tegenverhang bij vrijverval: licht (onder drempel) | W | Plausibiliteit |
| HGT-006 | Tegenverhang bij vrijverval: fors (boven drempel) | F | Plausibiliteit |
| HGT-007 | Verhang vuilwater of gemengd onder drempelwaarde | W | Plausibiliteit |
| HGT-008 | Extreem verhang (steiler dan bijv. 1:50), indicatie verwisselde BOB's | W | Plausibiliteit |
| HGT-009 | BOB-sprong tussen aansluitende strengen boven drempel zonder valput | W | Plausibiliteit |
| HGT-010 | Diameterverjonging in afvoerrichting (benedenstrooms kleiner dan bovenstrooms) | W | Plausibiliteit |
| HGT-011 | Overstortdrempel lager dan BOB aanvoerende streng of hoger dan maaiveld | F | Consistentie |
| HGT-012 | Putdiepte (deksel minus bodem) negatief of groter dan X m | F | Plausibiliteit |
| HGT-013 | Gronddekking op bovenkant buis kleiner dan 0,5 m of groter dan 4 m | W | Plausibiliteit |
| HGT-014 | Leidingverhang past niet bij het maaiveldverloop tussen de putten | W | Plausibiliteit |
| HGT-015 | Putbodemniveau buiten marge ten opzichte van de laagste aansluitende BOB (hoger dan +50 mm, of zonk dieper dan 500 mm) | W | Consistentie |
| HGT-016 | BOB van aansluitende streng ligt meer dan drempel boven de putbodem zonder geregistreerde zandvang- of valconstructie (ISYBAU Sohlsprung) | W | Plausibiliteit |
| HGT-017 | Z-waarde uit de geometrie wijkt af van de administratieve BOB of dekselhoogte (Z-variant van ATTR-009) | W | Consistentie |
| HGT-018 | Buiskruin (BOB plus diameter/hoogtemaat) boven maaiveld of dekselniveau | F | Plausibiliteit |

## NET: Netwerklogica

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| NET-001 | Vuilwater- of gemengde streng zonder afvoerpad naar gemaal of overnamepunt (bereikbaarheidsanalyse) | F | Consistentie |
| NET-002 | Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt | F | Consistentie |
| NET-003 | Strengorientatie tegen de afvoerrichting in | F | Consistentie |
| NET-004 | Cirkels (kringlopen) in het vrijvervalnetwerk | F | Consistentie |
| NET-005 | Stelseltype streng wijkt af van boven- en benedenstroomse buren | F | Consistentie |
| NET-006 | Koppelingen tussen verschillende stelseltypen | W | Plausibiliteit |
| NET-007 | IT-stelsel zonder drempel | F | Compleetheid |
| NET-008 | Opvallend veel lozingspunten binnen een klein deelstelsel | W | Plausibiliteit |

## RVZ: Randvoorzieningen (BBB's, overstorten, drempels)

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| RVZ-001 | Randvoorziening (BBB, overstortput) topologisch niet aangesloten op het netwerk; geometrisch-topologische variant, de administratieve koppeling dekt de nulmeting | F | Consistentie |
| RVZ-002 | Overstort zonder geregistreerde drempelhoogte (Drempelniveau), ook als het drempelonderdeel zelf ontbreekt; overlapt bewust met de nulmetingvorm Overstortput_Overstortdrempel_card, want die toetst alleen of de put een drempel heeft en de check werkt ook zonder nulmeting | W | Compleetheid |
| RVZ-003 | Overstort zonder geregistreerde drempelbreedte (Drempelbreedte), ook als het drempelonderdeel zelf ontbreekt | W | Compleetheid |
| RVZ-004 | Externe overstort zonder ontvangend oppervlaktewater binnen X m | W | Plausibiliteit |
| RVZ-005 | Overstort aangesloten op een hemelwater- of IT-stelsel | W | Consistentie |
| RVZ-006 | Gemengd deelstelsel zonder enige externe overstort of BBB | W | Plausibiliteit |
| RVZ-007 | BBB zonder geregistreerde bergingsinhoud of afmetingen | W | Compleetheid |
| RVZ-008 | BBB zonder ledigingsvoorziening of ledigingsroute terug naar het stelsel | W | Compleetheid |
| RVZ-009 | BBB zonder nooduitlaat of externe overstortdrempel | W | Compleetheid |
| RVZ-010 | Interne overstort waarbij beide zijden hetzelfde stelseltype hebben | W | Consistentie |
| RVZ-011 | Waking overstortdrempel kleiner dan 0,40 m (dekselniveau minus drempelniveau) | W | Plausibiliteit |

Zie ook HGT-011 (overstortdrempel versus BOB en maaiveld) en NET-007 (IT-stelsel zonder drempel).

## BTR: Betrouwbaarheid en metagegevens

Deze categorie is grotendeels afhankelijk van gevulde inwinningsmetagegevens (wijze en datum van inwinning); in de praktijk zijn die vaak leeg. BTR-006 vormt de uitzondering: die werkt op de waarden zelf.

Bevindingen uit de eerste run op echte data (De Wolden, 2026-08-16), zie open punt 8. De export bevat 25.546 registraties van `WijzeVanInwinning` en geen enkele `DatumInwinning`. De wijze hangt niet aan het kenmerk waar hij over gaat maar aan de puntgeometrie van de orientatie: waar de maaiveldhoogte zelf een wijze draagt is die in alle 4.875 gevallen gelijk aan die op het Punt, en AHN2 komt 5.104 keer op het Punt voor en geen enkele keer op de maaiveldhoogte. Dat is een conversieconventie van de bronexport, geen registratiefout: de GWSW-ontologie staat `Inwinning` op `Geometrie` (en daarmee op `Punt`) expliciet toe, en de collectie `WijzeVanInwinningColl` maakt geen onderscheid naar kenmerksoort. Een check op onlogische combinaties van kenmerk en wijze is daarom afgewezen; de leesregel is verwerkt in de lader (terugval op de wijze van het Punt) en in de kanttekening bij HGT-001 en HGT-002.

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| BTR-001 | Kritieke hoogtekenmerken (BOB, dekselniveau, drempelniveau) zonder inwinningsmetagegevens | W | Traceerbaarheid |
| BTR-002 | Kritieke kenmerken ingewonnen via schatting, plan of ontwerp in plaats van meting | W | Traceerbaarheid |
| BTR-003 | Inwinningsdatum BOB ouder dan drempel, afhankelijk van grondsoort (indicatie: zand 40 jaar, veen 10 jaar) | W | Actualiteit |
| BTR-004 | Geregistreerde grondwaterstand boven maaiveld of meer dan 5 m onder maaiveld | W | Plausibiliteit |
| BTR-005 | Toestands- of inspectiegegevens ouder dan drempel, gewogen naar risicoligging (spoor, dijk, wegfunctie) | W | Actualiteit |
| BTR-006 | Systematisch afgeronde hoogtewaarden: BOB's of dekselhoogten clusteren op ronde waarden (hele of halve decimeters), indicatie van geschatte in plaats van gemeten waarden | W | Precisie |

## EXT: Externe bronnen (BGT, BAG, waterschap, BRK)

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| EXT-001 | Kruising of nabijheid van BGT-panden en overige bouwwerken; getoetst op strengen en putten, met als uitkomst de relatie binnen, kruist of nabij | W | Plausibiliteit |
| EXT-002 | Kruising met watergang (waterschaps- of BGT-data) | W | Plausibiliteit |
| EXT-003 | Kruising met watergang zonder registratie als zinker; een duiker is in het GWSW geen rioolleiding (subklasse van Leiding) en valt buiten de populatie van EXT-002 en EXT-003, het rapport meldt hoeveel dat er zijn | W | Compleetheid |
| EXT-004 | Streng op of nabij particulier terrein (op basis van BRK-percelen) | W | Plausibiliteit |
| EXT-005 | Put zonder BGT-putdeksel binnen X m | W | Compleetheid |
| EXT-006 | BGT-putdeksel zonder put in de beheerdata | W | Compleetheid |
| EXT-007 | Lozingspunt zonder watergang binnen X m | W | Plausibiliteit |

## Geschrapte checks (gedekt door GWSW-nulmeting)

Schrapronde d.d. 2026-08-14, geactualiseerd naar toetsbasis Mds. Oorspronkelijke dekkinganalyse op basis van MdsPlan v1.5 SHACL en deelmodellen MdsPlan en Hyd v1.6; herverifieerd op de deelmodellen Mds v1.6 (filter collectie_MDSTOP_v16) en Hyd v1.6 (filter collectie_HYDTOP5_v16, detailrapporten De Wolden). Voorwaarden voor geldigheid van de dekking: (1) de dataset wordt aan beide conformiteitsklassen getoetst; dit is een harde eis, want de verplichting van de administratieve put-strengkoppeling komt uitsluitend uit Hyd; (2) de objecttypering is op orde; bij te globaal getypeerde objecten verklaart de nulmeting haar eigen vervolgvalidaties onbetrouwbaar; (3) de sentineltabel waarmee de dekking wordt aangetoond hoort bij deze registerversie, en elke geschrapte check heeft er een sentinel in.

Alle drie de voorwaarden worden machinaal gehandhaafd (2026-08-16). Voorwaarde 1 laat de pijplijn falen zodra een conformiteitsklasse ontbreekt of de rapporten over verschillende RDF-bestanden gaan. Voorwaarde 2 zet een voorbehoud op elke dekkingclaim waarvan een vereiste CFK onder de typeringsdrempel scoort. Voorwaarde 3 legt de sentineltabel naast dit register en faalt bij versieverschil of een gat aan een van beide kanten. Daarnaast meldt de dekkinganalyse bewijsvormen die in de ene vereiste CFK wel en in de andere geen meldingen opleveren: omdat alle CFK's hetzelfde RDF-bestand toetsen, kan dat niet aan schone data liggen en rust een claim "beide CFK's" dan in werkelijkheid op een deel ervan. Een geschrapte check zit niet in de engine, dus als de dekking vervalt kijkt er niets anders meer naar.

| ID | Check | Gedekt door |
|---|---|---|
| ADM-001 | Streng verwijst naar niet-bestaande begin- of eindput | Generieke melding gerefereerd object onbekend (CFK-onafhankelijk); verplichte aanwezigheid van de koppeling alleen via Hyd (hasConnection Knooppunt exact=1); Mds eist slechts max=1 |
| ADM-004 | Verplichte GWSW-MdS-attributen niet gevuld | Mds via Top-laag van het MDSTOP-filter (someValuesFrom: materiaal, vorm, lengte, breedte, hoogte leiding) plus Mds-eigen min-eisen (putdekselniveau, maaiveldhoogte); Hyd aanvullend inclusief BOB's en afmetingen exact=1 |
| ADM-005 | Attribuutwaarden buiten de GWSW-domeinlijsten | Beide CFK's: collectietoetsing hasReference |
| ATTR-011 | Absurde lengtewaarde boven harde bovengrens | Beide CFK's: waardebereik LengteLeiding 1-75 m (bevestigd in Mds-datatype Dt_LengteLeiding) |

## Vervallen checks (niet relevant voor deze toepassing)

Anders dan de geschrapte checks hierboven zijn deze niet door de nulmeting gedekt; er
kijkt niets meer naar. Ze zijn vervallen omdat ze voor deze opdracht geen bruikbare
uitkomst geven. De ID's worden niet hergebruikt.

| ID | Check | Vervallen in | Reden |
|---|---|---|---|
| EXT-008 | BAG-verblijfsobject zonder riolering binnen X m (dekkingscheck) | v0.8 | Niet relevant voor deze opdracht: de vraag of elk pand op riolering is aangesloten hoort bij het rioleringsplan, niet bij een datakwaliteitstoets op de bestaande registratie. Bovendien zijn er panden aangeleverd en geen verblijfsobjecten, waardoor de check alleen een benadering kon geven. |

## Open punten

1. Verplaatst naar de issuetracker: [#8 EXT-004 bouwen op BRK-percelen](https://github.com/mcolee/nlriochecker/issues/8).
2. Afgehandeld (2026-08-19). Alle vijf staan als instelbare waarde in `[drempels]` van de projectconfiguratie, met de standaard tussen haakjes: snapping-tolerantie (`snapping_tolerantie_m`, 0,10 m), min/max strenglengte (`minimale_strenglengte_m` 1 m en `maximale_strenglengte_m` 200 m, ATTR-008), minimaal verhang voor vuilwater en gemengd (HGT-007; sinds issue #29 geen enkele waarde meer maar de RIONED-diameterstaffel `[[verhang_staffel]]`, met 1:250 voor de kleinste leidingen tot 1:1000 voor de grootste), valput-drempel (`bob_sprong_m`, 0,25 m, HGT-009 en HGT-016) en de bufferafstanden van de EXT-checks (`ext_pand_buffer_m`, `ext_watergang_buffer_m`, `ext_putdeksel_afstand_m`, `ext_lozingspunt_water_afstand_m`, `ext_perceel_buffer_m`). Er staat geen drempel hardgecodeerd in de engine.
3. Afgehandeld (2026-08-19). `naamgeving.putpatroon` en `naamgeving.strengpatroon` in de projectconfiguratie nemen elk een regex, en een onbruikbaar patroon faalt bij het laden in plaats van tijdens de run. Er is bewust geen standaardpatroon: staat er geen, dan draait ADM-003 niet en meldt het rapport dat met zoveel woorden, want een verzonnen conventie zou elke dataset afkeuren. `examined` telt dan ook alleen de objectsoorten waarvoor wel een patroon geldt.
4. Buiten scope: persleiding- en gemaalconsistentiechecks (mechanisch); gemalen en overnamepunten doen wel mee als eindpunt in NET-001.
5. RVZ-008 (lediging BBB) raakt de scopegrens: lediging loopt in de praktijk vaak via een gemaal. De check toetst alleen of er een ledigingsroute geregistreerd staat, niet het gemaal zelf. NB: de nulmeting dekt dit niet (Ledigingsvoorziening heeft in beide CFK's, Mds en Hyd, max=1 en geen min-eis); alleen als er wel een ledigingsvoorziening geregistreerd is, eist Hyd daarin minimaal een pomp.
6. Afgehandeld (2026-08-19). Empirisch vastgesteld op de De Wolden-export en vastgelegd in de beslislog: overstorten staan er als `Overstortput` met een `Overstortleiding` eraan; losse `Overstortdrempel`-objecten met `Drempelniveau` en `Drempelbreedte` komen er niet in voor, terwijl het GWSW-voorbeeldbestand ze wel kent. `checks/randvoorzieningen.py` leest daarom beide vormen en meldt in de toelichting welke het in deze dataset heeft aangetroffen; de klassen staan in `[klassen]` van de projectconfiguratie (`overstortput`, `overstortleiding`, `drempel`). RVZ-004 t/m RVZ-011 zijn gebouwd en draaien. NB: dezelfde vraag speelt voor `Overnamepunt` en voor het IT-stelsel. Die twee zijn eerder ten onrechte als ontbrekende GWSW-begrippen opgeschreven; de ontologie kent ze wel (`Overnamepunt` als subklasse van `Aansluitpunt`, het IT-stelsel als `Infiltratiestelsel` met zijn subklasse `DrainageInfiltratieTransportStelsel`), maar de De Wolden-export levert nul `Overnamepunt`-instanties. Wat er wel en niet uit volgt staat in BO-33 en BO-34 van de beslislog; het spoor loopt via [#11](https://github.com/mcolee/nlriochecker/issues/11).
7. Afgehandeld: schrapronde uitgevoerd en geactualiseerd naar toetsbasis Mds, zie tabel Geschrapte checks. Afwijkingen ten opzichte van de oorspronkelijke verwachting: ADM-002 en ADM-003 blijven staan (duplicaat-ID's smelten in RDF geruisloos samen respectievelijk geen patroontoetsing), ADM-008/009 blijven staan (in de nulmeting-beschrijving expliciet aangemerkt als externe validatie), ATTR-011 is juist wel geschrapt; RVZ-003 was dat ook maar is in v0.9 teruggehaald (issue #6). In het proces borgen dat beide nulmeting-rapporten (Mds en Hyd) beschikbaar zijn en dat de typeringsscore als voorwaarde geldt.
8. Afgehandeld voor de inwinningswijze; open voor de rest. De eerste run op De Wolden (2026-08-16) laat zien dat BTR-001 t/m BTR-005 op deze export inderdaad vrijwel alleen ontbreken-meldingen opleveren: er is geen enkele `DatumInwinning` en geen `Grondwaterniveau`, en de wijze hangt aan de puntgeometrie in plaats van aan het kenmerk (zie de inleiding van BTR). Ze blijven skelet. Een voorgestelde uitbreiding BTR-008 (inwinningswijze past niet bij het kenmerk) is afgewezen, zie de BTR-inleiding. Twee andere kandidaten, placeholder-datums en expliciete onbekend-waarden, zijn afgewezen als check en opgenomen als datakarakteristieken in de kop van het bevindingenrapport: ze slaan op vrijwel de hele dataset aan en leveren per object geen handeling op, maar bepalen wel op welke precisie leeftijden gelden en hoe rooskleurig een compleetheidscijfer leest.
9. Uit het onderzoeksrapport zijn de geometrie- en hoogtechecks verwerkt (N2 t/m N5, N7, N17 t/m N22, als TOP-015 t/m TOP-021, ATTR-011/012, HGT-016 t/m HGT-018). N1 (BOB onder putbodem) was al gedekt door HGT-004. Het restant is verplaatst naar de issuetracker: [#9 Resterende checks uit het onderzoeksrapport](https://github.com/mcolee/nlriochecker/issues/9).
10. Deels afgehandeld (2026-08-16). Wat een regressietoets per run kan bewaken, wordt nu bewaakt; zie de voorwaarden bij Geschrapte checks. Wat niet kan: de rapportkoppen van de GWSW-server bevatten geen CFK-versie of filternaam, dus of de meting nog op deelmodel v1.6 en de filters collectie_MDSTOP_v16 en collectie_HYDTOP5_v16 draait, is niet uit de rapporten af te leiden en blijft handwerk. Het restant wordt niet opgepakt (besloten 2026-08-19): er is geen Mds-nulmetingrapport beschikbaar, en daarmee valt het buiten scope. Beide onderdelen staan of vallen met die bron -- zonder rapport is er niets om aan te verifieren en niets om een dekkinganalyse op te draaien. Komt er alsnog een Mds-rapport, dan is dit punt weer te openen. Dat restant was: (a) verifieren aan een echt Mds-nulmetingrapport of de someValuesFrom-eisen uit de Top-laag (waaronder HoogteLeiding, hasValidity-codering 1t 3t) daadwerkelijk als melding verschijnen, wat de NB-noot bij ATTR-004 raakt; en (b) een hernieuwde dekkinganalyse op Mds, die extra schrapkandidaten zou kunnen opleveren. (c) blijft staan als vaststelling: geen enkele geschrapte check hoeft terug, want Mds eist meer dan MdsPlan en niet minder.

11. Verplaatst naar de issuetracker: [#7 Twee dekkingclaims schrijven eisen aan de verkeerde conformiteitsklasse toe](https://github.com/mcolee/nlriochecker/issues/7).

12. Typering De Wolden (2026-08-16): een voorgestelde poortwachtercheck op te globaal getypeerde objecten is afgewezen als dubbel. De typeringspoort bestaat al (de SHACL-meting benoemt de te globale klassen, de dataset levert de instanties) en de drempel waaronder een dekkingclaim een voorbehoud krijgt is configureerbaar. Meten helpt hier bovendien niet: alle 20.758 putorientaties in De Wolden hangen aan een specifieke subklasse (19.322 Inspectieput, 1.107 Pompunit, 218 Overstortput, 55 Lozingsput, 27 Stuwput, 27 Kruisingsput, 1 Kolk, 1 Drainageput). Er is geen generiek getypeerde put.

13. Verplaatst naar de issuetracker: [#5 _bouw_netwerk overschrijft de kantattributen van parallelle strengen](https://github.com/mcolee/nlriochecker/issues/5).

## Versiehistorie

Versie 0.9 (2026-08-19): RVZ-002 en RVZ-003 zijn uit de tabel Geschrapte checks gehaald
en gebouwd (W, Compleetheid): in geen van de drie SHACL-rapporten bestaat een vorm op
Drempelniveau of Drempelbreedte, de enige drempelvorm
(Overstortput_Overstortdrempel_card) toetst of de put een drempel heeft, dus de
dekkingclaim was niet aantoonbaar en er keek niets naar die twee eigenschappen (issue
#6). ATTR-013 toegevoegd (W, Compleetheid): een hoogtekenmerk op een vulwaarde rond 0 m
NAP dat als meting geregistreerd staat (issue #1). EXT-003 gepreciseerd: een duiker is
geen rioolleiding en valt buiten de populatie (issue #3). Verder geen checks toegevoegd,
geschrapt of van ernst of dimensie veranderd. Vervallen ID's worden niet hergebruikt.

Versie 0.8, addendum (2026-08-19): geen checks toegevoegd, geschrapt of van ernst of
dimensie veranderd; het contract is ongewijzigd. Wel opgeschoond in de open punten: 1, 9,
11 en 13 zijn verplaatst naar de issuetracker op GitHub en vervangen door een verwijzing;
2, 3 en 6 staan als afgehandeld gemarkeerd, elk met de plek in de configuratie of de code
waar dat te controleren is; en van punt 10 wordt het restant niet opgepakt, wat er met de
inhoud bij staat. De nummering is bewust ongemoeid gelaten, omdat `checks.toml` en twee
modules naar punt 6 en punt 8 bij nummer verwijzen.

Versie 0.8 (2026-08-16): EXT-008 vervallen (BAG-verblijfsobjecten zijn voor deze opdracht
niet relevant; het ID wordt niet hergebruikt). EXT-001 uitgebreid van strengen naar
strengen en putten, met de relatie binnen, kruist of nabij als uitkomst; ernst en
dimensie ongewijzigd. Nieuwe paragraaf Afbakening van een analyse, waarin het scopebeleid
kern-plus-contextschil staat en de mechanische riolering expliciet als niet-geanalyseerd
wordt benoemd. Verder geen checks toegevoegd, geschrapt of van ernst of dimensie
veranderd.

Versie 0.7, addendum (2026-08-16): geen checks toegevoegd, geschrapt of van ernst of dimensie veranderd; het contract is ongewijzigd. Wel bijgewerkt: de voorwaarden bij Geschrapte checks (derde voorwaarde toegevoegd en alle drie machinaal gehandhaafd), de inleiding van BTR (waar de inwinningswijze in de export hangt), de annotaties bij HGT-001 en HGT-002 (kanttekening bij een hoogte uit een hoogtemodel) en de open punten 8, 10, 11 en 12.

Versie 0.7 (2026-08-14): toetsbasis gewijzigd van MdsPlan naar Mds (deelmodel v1.6, filter collectie_MDSTOP_v16). Dekkingclaims van ADM-001, ADM-004, RVZ-002 en RVZ-003 geherformuleerd op basis van verificatie in de deelmodel-ontologieen; annotaties TOP-001 t/m TOP-003 aangescherpt (administratieve koppeling rust volledig op Hyd); NB-noot ATTR-004 herzien (MDSTOP dwingt aanwezigheid breedte en hoogte af); HGT-inleiding gepreciseerd (Mds dwingt maaiveldhoogte, putdekselniveau en drempelniveau af, BOB's blijven exclusief Hyd); open punt 10 toegevoegd. Geen checks toegevoegd of geschrapt.

Versie 0.6 (2026-08-14): schrapronde uitgevoerd op basis van dekkinganalyse MdsPlan v1.5 SHACL en deelmodellen MdsPlan en Hyd v1.6.
