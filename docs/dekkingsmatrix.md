# Dekkingsmatrix checkregister

Gegenereerd uit `data/checkregister-gwsw-nulmeting-v0_7.md` (versie 0.7) met `scripts/dekkingsmatrix.py`. Niet met de hand bijwerken.

Status per check-ID: *geimplementeerd met test*, *geimplementeerd zonder test*, *ontbreekt*, of *geschrapt (gedekt door nulmeting)*. Een check die als skelet geregistreerd staat telt als geimplementeerd, maar levert per definitie geen uitslag; de markering en de reden staan in de kolom Toelichting.

| Categorie | Register | Met test | Zonder test | Ontbreekt | Geschrapt |
| --- | ---: | ---: | ---: | ---: | ---: |
| TOP | 21 | 21 | 0 | 0 | 0 |
| ADM | 9 | 0 | 0 | 6 | 3 |
| ATTR | 12 | 0 | 11 | 0 | 1 |
| HGT | 18 | 0 | 0 | 18 | 0 |
| NET | 8 | 8 | 0 | 0 | 0 |
| RVZ | 11 | 0 | 0 | 9 | 2 |
| BTR | 6 | 0 | 0 | 6 | 0 |
| EXT | 8 | 0 | 0 | 8 | 0 |
| **totaal** | **93** | **29** | **11** | **47** | **6** |

## TOP

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| TOP-001 | Losliggende putten (geen enkele streng aangesloten); geometrische variant, de administratieve koppeling dekt de nulmeting (verplichting exact=1 komt… | F | Consistentie | geimplementeerd met test | — |
| TOP-002 | Losliggende strengen (aan geen van beide zijden een put); geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | — |
| TOP-003 | Streng met slechts aan een zijde een put; geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | — |
| TOP-004 | Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie) | F | Consistentie | geimplementeerd met test | — |
| TOP-005 | Dubbele putten: twee knopen binnen tolerantie (bijv. 0,30 m) | F | Compleetheid | geimplementeerd met test | — |
| TOP-006 | Dubbel ingetekende of (deels) overlappende strengen | F | Compleetheid | geimplementeerd met test | — |
| TOP-007 | Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie | F | Consistentie | geimplementeerd met test | — |
| TOP-008 | Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put) | F | Consistentie | geimplementeerd met test | — |
| TOP-009 | Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten | F | Nauwkeurigheid | geimplementeerd met test | — |
| TOP-010 | Streng met buffer op basis van diameter kruist of raakt andere strengen | F | Plausibiliteit | geimplementeerd met test | — |
| TOP-011 | Hartlijnkruisingen strengen onderling (zonder buffer) | W | Plausibiliteit | geimplementeerd met test | — |
| TOP-012 | Streng met dezelfde put aan begin- en eindpunt | F | Consistentie | geimplementeerd met test | — |
| TOP-013 | Meer dan twee parallelle strengen tussen hetzelfde putpaar | W | Plausibiliteit | geimplementeerd met test | — |
| TOP-014 | Meer dan vier aansluitende strengen op een put | W | Plausibiliteit | geimplementeerd met test | — |
| TOP-015 | Streng of put met multipart-geometrie (meerdere losse delen in een feature) | F | Consistentie | geimplementeerd met test | — |
| TOP-016 | Ongeldige geometrie volgens OGC Simple Features (ST_IsValid: zelf-intersectie, niet-gesloten ringen) | F | Consistentie | geimplementeerd met test | — |
| TOP-017 | Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren) | W | Consistentie | geimplementeerd met test | — |
| TOP-018 | Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie | W | Consistentie | geimplementeerd met test | — |
| TOP-019 | Pseudo-knoop: twee strengen gescheiden door een functieloze knoop, met identieke attributen (diameter, materiaal, stelseltype); zouden een streng moe… | W | Consistentie | geimplementeerd met test | — |
| TOP-020 | Digitalisatierichting (begin- naar eindvertex) komt niet overeen met de administratieve van-naar-richting | W | Consistentie | geimplementeerd met test | — |
| TOP-021 | Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een doorlopende streng (verfijning van TOP-001) | W | Consistentie | geimplementeerd met test | — |

## ADM

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| ADM-001 | Streng verwijst naar niet-bestaande begin- of eindput | — | — | geschrapt (gedekt door nulmeting) | Generieke melding gerefereerd object onbekend (CFK-onafhankelijk); verplichte aanwezigheid van de koppeling alleen via Hyd (hasConnection Knooppunt e… |
| ADM-002 | Niet-unieke identificaties van putten of strengen; uitvoeren op de bronexport, voor de OroX-conversie (duplicaat-ID's smelten in RDF geruisloos samen) | F | Consistentie | ontbreekt | — |
| ADM-003 | Naamgeving knopen en strengen wijkt af van conventie (patroon configureerbaar) | F | Compliance | ontbreekt | — |
| ADM-004 | Verplichte GWSW-MdS-attributen niet gevuld | — | — | geschrapt (gedekt door nulmeting) | Mds via Top-laag van het MDSTOP-filter (someValuesFrom: materiaal, vorm, lengte, breedte, hoogte leiding) plus Mds-eigen min-eisen (putdekselniveau,… |
| ADM-005 | Attribuutwaarden buiten de GWSW-domeinlijsten | — | — | geschrapt (gedekt door nulmeting) | Beide CFK's: collectietoetsing hasReference |
| ADM-006 | Vervallen of geplande objecten die topologisch meedoen in het actieve netwerk | W | Consistentie | ontbreekt | — |
| ADM-007 | Puttype past niet bij het type aangesloten leiding (bijv. overstortput zonder overstortfunctie in het netwerk); netwerkfunctionele toets, de samenste… | F | Consistentie | ontbreekt | — |
| ADM-008 | Putcompartimenten of -onderdelen zonder onderlinge verbinding binnen de put | W | Consistentie | ontbreekt | — |
| ADM-009 | Leiding gekoppeld aan de put als geheel waar koppeling aan een compartiment vereist is | W | Consistentie | ontbreekt | — |

## ATTR

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| ATTR-001 | Diameter past niet bij materiaal | F | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-002 | Diameter kleiner dan rond 200 mm (de nulmeting toetst alleen de extreme ondergrens van 63 mm) | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-003 | Materiaal past niet bij aanlegjaar (bijv. PVC voor 1955, PE voor 1970) | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-004 | Vorm versus afmetingen inconsistent (eivorm zonder hoogte, rond met breedte ongelijk hoogte); NB het MDSTOP-deelmodel dwingt de aanwezigheid van bree… | F | Consistentie | geimplementeerd zonder test | — |
| ATTR-005 | Eenhedenfouten die binnen de GWSW-waardebereiken vallen (bijv. diameter 300 genoteerd in cm); fouten buiten bereik dekt de nulmeting | F | Nauwkeurigheid | geimplementeerd zonder test | — |
| ATTR-006 | Strengdiameter groter dan afmeting van de aangesloten put | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-007 | Aanlegjaar in de toekomst of voor 1870 (de nulmeting toetst alleen datatype, geen bereik) | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-008 | Strenglengte korter dan X m of langer dan X m | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-009 | Geometrische lengte wijkt meer dan X% af van administratieve lengte | W | Consistentie | geimplementeerd zonder test | — |
| ATTR-010 | Leidingmateriaal beton of metselwerk terwijl het putmateriaal daar niet bij past | W | Plausibiliteit | geimplementeerd zonder test | — |
| ATTR-011 | Absurde lengtewaarde boven harde bovengrens | — | — | geschrapt (gedekt door nulmeting) | Beide CFK's: waardebereik LengteLeiding 1-75 m (bevestigd in Mds-datatype Dt_LengteLeiding) |
| ATTR-012 | Materiaal past niet bij profielvorm (bijv. metselwerk met rond profiel in plaats van ei- of muilprofiel) | W | Plausibiliteit | geimplementeerd zonder test | — |

## HGT

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| HGT-001 | Dekselhoogte wijkt af van AHN: meer dan 5 cm | W | Nauwkeurigheid | ontbreekt | — |
| HGT-002 | Dekselhoogte wijkt af van AHN: meer dan 25 cm | F | Nauwkeurigheid | ontbreekt | — |
| HGT-003 | BOB-sanity ten opzichte van AHN (boven maaiveld, meer dan 3 m eronder) | F | Plausibiliteit | ontbreekt | — |
| HGT-004 | BOB hoger dan dekselhoogte van de eigen put, of lager dan de putbodem | F | Consistentie | ontbreekt | — |
| HGT-005 | Tegenverhang bij vrijverval: licht (onder drempel) | W | Plausibiliteit | ontbreekt | — |
| HGT-006 | Tegenverhang bij vrijverval: fors (boven drempel) | F | Plausibiliteit | ontbreekt | — |
| HGT-007 | Verhang vuilwater of gemengd onder drempelwaarde | W | Plausibiliteit | ontbreekt | — |
| HGT-008 | Extreem verhang (steiler dan bijv. 1:50), indicatie verwisselde BOB's | W | Plausibiliteit | ontbreekt | — |
| HGT-009 | BOB-sprong tussen aansluitende strengen boven drempel zonder valput | W | Plausibiliteit | ontbreekt | — |
| HGT-010 | Diameterverjonging in afvoerrichting (benedenstrooms kleiner dan bovenstrooms) | W | Plausibiliteit | ontbreekt | — |
| HGT-011 | Overstortdrempel lager dan BOB aanvoerende streng of hoger dan maaiveld | F | Consistentie | ontbreekt | — |
| HGT-012 | Putdiepte (deksel minus bodem) negatief of groter dan X m | F | Plausibiliteit | ontbreekt | — |
| HGT-013 | Gronddekking op bovenkant buis kleiner dan 0,5 m of groter dan 4 m | W | Plausibiliteit | ontbreekt | — |
| HGT-014 | Leidingverhang past niet bij het maaiveldverloop tussen de putten | W | Plausibiliteit | ontbreekt | — |
| HGT-015 | Putbodemniveau buiten marge ten opzichte van de laagste aansluitende BOB (hoger dan +50 mm, of zonk dieper dan 500 mm) | W | Consistentie | ontbreekt | — |
| HGT-016 | BOB van aansluitende streng ligt meer dan drempel boven de putbodem zonder geregistreerde zandvang- of valconstructie (ISYBAU Sohlsprung) | W | Plausibiliteit | ontbreekt | — |
| HGT-017 | Z-waarde uit de geometrie wijkt af van de administratieve BOB of dekselhoogte (Z-variant van ATTR-009) | W | Consistentie | ontbreekt | — |
| HGT-018 | Buiskruin (BOB plus diameter/hoogtemaat) boven maaiveld of dekselniveau | F | Plausibiliteit | ontbreekt | — |

## NET

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| NET-001 | Vuilwater- of gemengde streng zonder afvoerpad naar gemaal of overnamepunt (bereikbaarheidsanalyse) | F | Consistentie | geimplementeerd met test | — |
| NET-002 | Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt | F | Consistentie | geimplementeerd met test | — |
| NET-003 | Strengorientatie tegen de afvoerrichting in | F | Consistentie | geimplementeerd met test | — |
| NET-004 | Cirkels (kringlopen) in het vrijvervalnetwerk | F | Consistentie | geimplementeerd met test | — |
| NET-005 | Stelseltype streng wijkt af van boven- en benedenstroomse buren | F | Consistentie | geimplementeerd met test | — |
| NET-006 | Koppelingen tussen verschillende stelseltypen | W | Plausibiliteit | geimplementeerd met test | — |
| NET-007 | IT-stelsel zonder drempel | F | Compleetheid | geimplementeerd met test | — |
| NET-008 | Opvallend veel lozingspunten binnen een klein deelstelsel | W | Plausibiliteit | geimplementeerd met test | — |

## RVZ

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| RVZ-001 | Randvoorziening (BBB, overstortput) topologisch niet aangesloten op het netwerk; geometrisch-topologische variant, de administratieve koppeling dekt… | F | Consistentie | ontbreekt | — |
| RVZ-002 | Overstort zonder geregistreerde drempelhoogte | — | — | geschrapt (gedekt door nulmeting) | Beide CFK's: Drempelniveau exact=1 (Mds) / min=1 (Hyd) |
| RVZ-003 | Overstort zonder geregistreerde drempelbreedte | — | — | geschrapt (gedekt door nulmeting) | Alleen Hyd: Drempelbreedte exact=1; Mds staat ontbreken toe (max=1, geen min-eis) |
| RVZ-004 | Externe overstort zonder ontvangend oppervlaktewater binnen X m | W | Plausibiliteit | ontbreekt | — |
| RVZ-005 | Overstort aangesloten op een hemelwater- of IT-stelsel | W | Consistentie | ontbreekt | — |
| RVZ-006 | Gemengd deelstelsel zonder enige externe overstort of BBB | W | Plausibiliteit | ontbreekt | — |
| RVZ-007 | BBB zonder geregistreerde bergingsinhoud of afmetingen | W | Compleetheid | ontbreekt | — |
| RVZ-008 | BBB zonder ledigingsvoorziening of ledigingsroute terug naar het stelsel | W | Compleetheid | ontbreekt | — |
| RVZ-009 | BBB zonder nooduitlaat of externe overstortdrempel | W | Compleetheid | ontbreekt | — |
| RVZ-010 | Interne overstort waarbij beide zijden hetzelfde stelseltype hebben | W | Consistentie | ontbreekt | — |
| RVZ-011 | Waking overstortdrempel kleiner dan 0,40 m (dekselniveau minus drempelniveau) | W | Plausibiliteit | ontbreekt | — |

## BTR

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| BTR-001 | Kritieke hoogtekenmerken (BOB, dekselniveau, drempelniveau) zonder inwinningsmetagegevens | W | Traceerbaarheid | ontbreekt | — |
| BTR-002 | Kritieke kenmerken ingewonnen via schatting, plan of ontwerp in plaats van meting | W | Traceerbaarheid | ontbreekt | — |
| BTR-003 | Inwinningsdatum BOB ouder dan drempel, afhankelijk van grondsoort (indicatie: zand 40 jaar, veen 10 jaar) | W | Actualiteit | ontbreekt | — |
| BTR-004 | Geregistreerde grondwaterstand boven maaiveld of meer dan 5 m onder maaiveld | W | Plausibiliteit | ontbreekt | — |
| BTR-005 | Toestands- of inspectiegegevens ouder dan drempel, gewogen naar risicoligging (spoor, dijk, wegfunctie) | W | Actualiteit | ontbreekt | — |
| BTR-006 | Systematisch afgeronde hoogtewaarden: BOB's of dekselhoogten clusteren op ronde waarden (hele of halve decimeters), indicatie van geschatte in plaats… | W | Precisie | ontbreekt | — |

## EXT

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| EXT-001 | Kruising of nabijheid van BGT-panden en overige bouwwerken | W | Plausibiliteit | ontbreekt | — |
| EXT-002 | Kruising met watergang (waterschaps- of BGT-data) | W | Plausibiliteit | ontbreekt | — |
| EXT-003 | Kruising met watergang zonder registratie als zinker of duiker | W | Compleetheid | ontbreekt | — |
| EXT-004 | Streng op of nabij particulier terrein (op basis van BRK-percelen) | W | Plausibiliteit | ontbreekt | — |
| EXT-005 | Put zonder BGT-putdeksel binnen X m | W | Compleetheid | ontbreekt | — |
| EXT-006 | BGT-putdeksel zonder put in de beheerdata | W | Compleetheid | ontbreekt | — |
| EXT-007 | Lozingspunt zonder watergang binnen X m | W | Plausibiliteit | ontbreekt | — |
| EXT-008 | BAG-verblijfsobject zonder riolering binnen X m (dekkingscheck) | W | Compleetheid | ontbreekt | — |
