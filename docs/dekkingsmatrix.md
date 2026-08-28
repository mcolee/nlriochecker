# Dekkingsmatrix checkregister

Gegenereerd uit `data/checkregister-gwsw-nulmeting-v0_9.md` (versie 0.9) met `scripts/dekkingsmatrix.py`. Niet met de hand bijwerken.

Status per check-ID: *geimplementeerd met test*, *geimplementeerd zonder test*, *ontbreekt*, of *geschrapt (gedekt door nulmeting)*. Een check die als skelet geregistreerd staat telt als geimplementeerd, maar levert per definitie geen uitslag; de markering en de reden staan in de kolom Toelichting.

| Categorie | Register | Met test | Zonder test | Ontbreekt | Geschrapt |
| --- | ---: | ---: | ---: | ---: | ---: |
| TOP | 23 | 23 | 0 | 0 | 0 |
| ADM | 10 | 7 | 0 | 0 | 3 |
| ATTR | 18 | 16 | 0 | 0 | 2 |
| HGT | 18 | 18 | 0 | 0 | 0 |
| NET | 9 | 9 | 0 | 0 | 0 |
| RVZ | 11 | 11 | 0 | 0 | 0 |
| BTR | 4 | 4 | 0 | 0 | 0 |
| EXT | 4 | 4 | 0 | 0 | 0 |
| **totaal** | **97** | **92** | **0** | **0** | **5** |

## TOP

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| TOP-001 | Losliggende putten (geen enkele streng aangesloten); geometrische variant, de administratieve koppeling dekt de nulmeting (verplichting exact=1 komt… | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-002 | Losliggende strengen (aan geen van beide zijden een put); geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-003 | Streng met slechts aan een zijde een put; geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-004 | Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie) | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-005 | Dubbele putten: twee knopen binnen tolerantie (bijv. 0,30 m) | F | Compleetheid | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-006 | Dubbel ingetekende of (deels) overlappende strengen. Beide leidingen van een paar moeten een `VrijvervalRioolleiding` of een `Duiker` zijn (`[klassen… | F | Compleetheid | geimplementeerd met test | leidingen, nabijheidsleidingen · — | — |
| TOP-007 | Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-008 | Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put) | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-009 | Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten | F | Nauwkeurigheid | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-010 | Streng met buffer op basis van diameter kruist of raakt andere strengen. Zelfde populatie-afbakening als TOP-006: beide leidingen van een paar zijn e… | F | Plausibiliteit | geimplementeerd met test | leidingen, nabijheidsleidingen · BreedteLeiding, HoogteLeiding | — |
| TOP-011 | Hartlijnkruisingen strengen onderling (zonder buffer). Zelfde populatie-afbakening als TOP-006 (BO-69, issue #82) | W | Plausibiliteit | geimplementeerd met test | leidingen, nabijheidsleidingen · — | — |
| TOP-012 | Streng met dezelfde put aan begin- en eindpunt | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-013 | Meer dan twee parallelle strengen tussen hetzelfde putpaar | W | Plausibiliteit | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-014 | Meer dan vier aansluitende strengen op een put | W | Plausibiliteit | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-015 | Streng of put met multipart-geometrie (meerdere losse delen in een feature) | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-016 | Ongeldige geometrie volgens OGC Simple Features (ST_IsValid: zelf-intersectie, niet-gesloten ringen) | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-017 | Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren) | W | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-018 | Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie | W | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-019 | Pseudo-knoop: twee strengen gescheiden door een functieloze knoop, met identieke attributen (diameter, materiaal, stelseltype); zouden een streng moe… | W | Consistentie | geimplementeerd met test | functieloze_knopen, leidingen, netwerkknopen, vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding, MateriaalLeiding | — |
| TOP-020 | Digitalisatierichting (begin- naar eindvertex) komt niet overeen met de administratieve van-naar-richting | W | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-021 | Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een doorlopende streng (verfijning van TOP-001) | W | Consistentie | geimplementeerd met test | leidingen, netwerkknopen, vrijvervalrioolleidingen · — | — |
| TOP-022 | Hulpstuk verbindt minder leidingen dan zijn GWSW-functie voorschrijft. Het verwachte aantal volgt uit de `functie`-restrictie op de klasse in de onto… | F | Consistentie | geimplementeerd met test | hulpstukken, leidingen · — | — |
| TOP-023 | Hulpstuk verbindt meer leidingen dan zijn GWSW-functie voorschrijft; waarschijnlijk de verkeerde klasse gekozen (voor vier bestaat `Kruisstuk`). Zelf… | W | Consistentie | geimplementeerd met test | hulpstukken, leidingen · — | — |

## ADM

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| ADM-001 | Streng verwijst naar niet-bestaande begin- of eindput | — | — | geschrapt (gedekt door nulmeting) | — | Generieke melding gerefereerd object onbekend (CFK-onafhankelijk); verplichte aanwezigheid van de koppeling alleen via Hyd (hasConnection Knooppunt e… |
| ADM-002 | Niet-unieke identificaties van putten of strengen; uitvoeren op de bronexport, voor de OroX-conversie (duplicaat-ID's smelten in RDF geruisloos samen) | F | Consistentie | geimplementeerd met test | leidingen, netwerkknopen · — | — |
| ADM-003 | Naamgeving knopen en strengen wijkt af van conventie (patroon configureerbaar) | F | Compliance | geimplementeerd met test | leidingen, netwerkknopen · — | — |
| ADM-004 | Verplichte GWSW-MdS-attributen niet gevuld | — | — | geschrapt (gedekt door nulmeting) | — | Mds via Top-laag van het MDSTOP-filter (someValuesFrom: materiaal, vorm, lengte, breedte, hoogte leiding) plus Mds-eigen min-eisen (putdekselniveau,… |
| ADM-005 | Attribuutwaarden buiten de GWSW-domeinlijsten | — | — | geschrapt (gedekt door nulmeting) | — | Beide CFK's: collectietoetsing hasReference |
| ADM-006 | Vervallen of geplande objecten die topologisch meedoen in het actieve netwerk | W | Consistentie | geimplementeerd met test | leidingen, netwerkknopen · Begindatum, Einddatum | — |
| ADM-007 | Puttype past niet bij het type aangesloten leiding (bijv. overstortput zonder overstortfunctie in het netwerk); netwerkfunctionele toets, de samenste… | F | Consistentie | geimplementeerd met test | — · — | — |
| ADM-008 | Putcompartimenten of -onderdelen zonder onderlinge verbinding binnen de put | W | Consistentie | geimplementeerd met test | netwerkknopen · — | — |
| ADM-009 | Leiding gekoppeld aan de put als geheel waar koppeling aan een compartiment vereist is | W | Consistentie | geimplementeerd met test | netwerkknopen · — | — |
| ADM-010 | Loze leiding (`LozeLeiding` en subklassen: buiten gebruik, nog in de ondergrond) waar actief riool op aansluit. Loze leidingen die een knoop delen vo… | F | Consistentie | geimplementeerd met test | leidingen, lozeleidingen · — | — |

## ATTR

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| ATTR-001 | Diameter past niet bij materiaal | F | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding, MateriaalLeiding | — |
| ATTR-002 | Diameter kleiner dan rond 200 mm (de nulmeting toetst alleen de extreme ondergrens van 63 mm) | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding | — |
| ATTR-003 | Materiaal past niet bij begindatum (bijv. PVC voor 1955, PE voor 1970) | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · Begindatum, MateriaalLeiding | — |
| ATTR-004 | Vorm versus afmetingen inconsistent (eivorm zonder hoogte, rond met breedte ongelijk hoogte); NB het MDSTOP-deelmodel dwingt de aanwezigheid van bree… | F | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding, VormLeiding | — |
| ATTR-005 | Eenhedenfouten die binnen de GWSW-waardebereiken vallen (bijv. diameter 300 genoteerd in cm); fouten buiten bereik dekt de nulmeting | F | Nauwkeurigheid | geimplementeerd met test | vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding | — |
| ATTR-006 | Strengdiameter groter dan afmeting van de aangesloten put | W | Plausibiliteit | geimplementeerd met test | putten, vrijvervalrioolleidingen · BreedteBouwwerk, BreedteLeiding, BreedtePut, DiameterPut, HoogteLeiding, LengteBouwwerk, LengtePut | — |
| ATTR-007 | Begindatum in de toekomst of voor 1870 (de nulmeting toetst alleen datatype, geen bereik) | W | Plausibiliteit | geimplementeerd met test | putten, vrijvervalrioolleidingen · Begindatum | — |
| ATTR-008 | Strenglengte korter dan X m of langer dan X m | — | — | geschrapt (gedekt door nulmeting) | — | Alle drie de CFK's: waardebereik LengteLeiding 1-75 m (vorm LengteLeiding_val, bevestigd in Mds-datatype Dt_LengteLeiding) — dezelfde dekking als ATT… |
| ATTR-009 | Geometrische lengte wijkt meer dan X% af van administratieve lengte | W | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · LengteLeiding | — |
| ATTR-010 | Leidingmateriaal beton of metselwerk terwijl het putmateriaal daar niet bij past | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · MateriaalBouwwerk, MateriaalLeiding, MateriaalPut | — |
| ATTR-011 | Absurde lengtewaarde boven harde bovengrens | — | — | geschrapt (gedekt door nulmeting) | — | Beide CFK's: waardebereik LengteLeiding 1-75 m (bevestigd in Mds-datatype Dt_LengteLeiding) |
| ATTR-012 | Materiaal past niet bij profielvorm (bijv. metselwerk met rond profiel in plaats van ei- of muilprofiel) | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · MateriaalLeiding, VormLeiding | — |
| ATTR-013 | Hoogtekenmerk (BOB, maaiveldhoogte, putdekselniveau) op een vulwaarde rond 0 m NAP dat als meting geregistreerd staat; de band en de kenmerken zijn p… | W | Compleetheid | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · config:hoogte_kenmerken | — |
| ATTR-014 | Kenmerk gebruikt `hasValue` waar de ontologie via een restrictie `hasReference` naar een collectie eist (of andersom); een fout die de SHACL-nulmetin… | F | Consistentie | geimplementeerd met test | — · alle kenmerken | — |
| ATTR-015 | Jaartal draagt een onevenredig deel van de begindatums (mogelijke vulwaarde); een signaaldetector, geen norm, met een instelbare drempel (`begindatum… | W | Compleetheid | geimplementeerd met test | putten, vrijvervalrioolleidingen · Begindatum | — |
| ATTR-016 | Vorm put versus afmetingen inconsistent: een ronde put (`VormPut = Rond`) waarvan breedte en lengte verschillen; een ronde put heeft een diameter. De… | F | Consistentie | geimplementeerd met test | putten · BreedtePut, LengtePut, VormPut | — |
| ATTR-017 | Wandruwheid (`WandruwheidBinnenboven`/`-onder`) past niet bij het leidingmateriaal; de aannemelijke band per materiaal komt uit Leidraad Riolering C2… | W | Plausibiliteit | geimplementeerd met test | leidingen · MateriaalLeiding, WandruwheidBinnenboven, WandruwheidBinnenonder | — |
| ATTR-018 | Begindatum ontbreekt op een vrijvervalrioolleiding of put. ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een aanwezige datum en de nulmeting eist `Be… | F | Compleetheid | geimplementeerd met test | leidingen, putten, vrijvervalrioolleidingen · Begindatum | — |

## HGT

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| HGT-001 | Dekselhoogte wijkt af van AHN: 10 cm of meer (v0.9 zei "meer dan 5 cm"; afwijking in BO-44); is de gebruikte hoogte zelf uit een hoogtemodel ingewonn… | W | Nauwkeurigheid | geimplementeerd met test | netwerkknopen · Maaiveldhoogte, Putdekselniveau | — |
| HGT-002 | Dekselhoogte wijkt af van AHN: 25 cm of meer; zelfde kanttekening als HGT-001 | F | Nauwkeurigheid | geimplementeerd met test | netwerkknopen · Maaiveldhoogte, Putdekselniveau | — |
| HGT-003 | BOB-sanity ten opzichte van AHN (boven maaiveld, meer dan 4,0 m eronder; v0.9 zei "meer dan 3 m"; afwijking in BO-68) | F | Plausibiliteit | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| HGT-004 | BOB hoger dan dekselhoogte van de eigen put, of lager dan de putbodem | F | Consistentie | geimplementeerd met test | netwerkknopen, rioolputten, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, HoogtePut, Maaiveldhoogte, Putdekselniveau | — |
| HGT-005 | Tegenverhang bij vrijverval: licht (onder drempel) | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| HGT-006 | Tegenverhang bij vrijverval: fors (boven drempel) | F | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| HGT-007 | Verhang vuilwater of gemengd onder drempelwaarde | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen, vuilwaterleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, BreedteLeiding, LengteLeiding | — |
| HGT-008 | Extreem verhang (steiler dan bijv. 1:50), indicatie verwisselde BOB's | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, LengteLeiding | — |
| HGT-009 | BOB-sprong tussen aansluitende strengen boven drempel zonder valput | W | Plausibiliteit | geimplementeerd met test | netwerkknopen, valconstructies, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| HGT-010 | Diameterverjonging in afvoerrichting (benedenstrooms kleiner dan bovenstrooms) | W | Plausibiliteit | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · BreedteLeiding, HoogteLeiding | — |
| HGT-011 | Overstortdrempel lager dan BOB aanvoerende streng of hoger dan maaiveld | F | Consistentie | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · BobEindpuntLeiding, Maaiveldhoogte, Putdekselniveau | — |
| HGT-012 | Putdiepte (deksel minus bodem) negatief of groter dan X m | F | Plausibiliteit | geimplementeerd met test | rioolputten · HoogtePut | — |
| HGT-013 | Gronddekking op bovenkant buis kleiner dan 0,5 m of groter dan 4 m | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, BreedteLeiding, HoogteLeiding, Maaiveldhoogte | — |
| HGT-014 | Leidingverhang past niet bij het maaiveldverloop tussen de putten | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, Maaiveldhoogte | — |
| HGT-015 | Putbodemniveau buiten marge ten opzichte van de laagste aansluitende BOB (hoger dan +50 mm, of zonk dieper dan 500 mm) | W | Consistentie | geimplementeerd met test | rioolputten, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, HoogtePut, Maaiveldhoogte, Putdekselniveau | — |
| HGT-016 | BOB van aansluitende streng ligt meer dan drempel boven de putbodem zonder geregistreerde zandvang- of valconstructie (ISYBAU Sohlsprung) | W | Plausibiliteit | geimplementeerd met test | rioolputten, valconstructies, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, HoogtePut, Maaiveldhoogte, Putdekselniveau | — |
| HGT-017 | Z-waarde uit de geometrie wijkt af van de administratieve BOB of dekselhoogte (Z-variant van ATTR-009) | W | Consistentie | geimplementeerd met test | rioolputten, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, Putdekselniveau | — |
| HGT-018 | Buiskruin (BOB plus diameter/hoogtemaat) boven maaiveld of dekselniveau | F | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, BreedteLeiding, HoogteLeiding, Maaiveldhoogte, Putdekselniveau | — |

## NET

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| NET-001 | Vuilwater- of gemengde streng zonder afvoerpad naar gemaal, overnamepunt of lozingspunt (bereikbaarheidsanalyse); een pompput telt niet als eindpunt,… | F | Consistentie | geimplementeerd met test | lozingspunten, mechanischeleidingen, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-002 | Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt | F | Consistentie | geimplementeerd met test | lozingspunten, mechanischeleidingen, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-003 | Strengorientatie tegen de afvoerrichting in | F | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-004 | Cirkels (kringlopen) in het vrijvervalnetwerk | F | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-005 | Stelseltype streng wijkt af van boven- en benedenstroomse buren | F | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-006 | Koppelingen tussen verschillende stelseltypen | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-007 | IT-stelsel zonder drempel | F | Compleetheid | geimplementeerd met test | infiltratieleidingen, overstortputten, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-008 | Opvallend veel lozingspunten binnen een klein deelstelsel | W | Plausibiliteit | geimplementeerd met test | lozingspunten, mechanischeleidingen, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |
| NET-009 | Richtingssignalen (administratie, geometrie, BOB) spreken elkaar tegen | F | Consistentie | geimplementeerd met test | vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding | — |

## RVZ

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| RVZ-001 | Randvoorziening (BBB, overstortput) topologisch niet aangesloten op het netwerk; geometrisch-topologische variant, de administratieve koppeling dekt… | F | Consistentie | geimplementeerd met test | bergbezinkvoorzieningen, overstortputten · — | — |
| RVZ-002 | Overstort zonder geregistreerde drempelhoogte (Drempelniveau), ook als het drempelonderdeel zelf ontbreekt; overlapt bewust met de nulmetingvorm Over… | W | Compleetheid | geimplementeerd met test | overstortputten · Drempelbreedte, Drempelniveau | — |
| RVZ-003 | Overstort zonder geregistreerde drempelbreedte (Drempelbreedte), ook als het drempelonderdeel zelf ontbreekt | W | Compleetheid | geimplementeerd met test | overstortputten · Drempelbreedte, Drempelniveau | — |
| RVZ-004 | Externe overstort zonder ontvangend oppervlaktewater binnen X m | W | Plausibiliteit | geimplementeerd met test | oppervlaktewaterobjecten, overstortputten · — | — |
| RVZ-005 | Overstort aangesloten op een hemelwater- of IT-stelsel | W | Consistentie | geimplementeerd met test | overstortputten, vrijvervalrioolleidingen · — | — |
| RVZ-006 | Gemengd deelstelsel zonder enige externe overstort of BBB, óf zonder afvoereindpunt (gemaal of overnamepunt) | F | Plausibiliteit | geimplementeerd met test | bergbezinkvoorzieningen, overstortputten, vrijvervalrioolleidingen · — | — |
| RVZ-007 | BBB zonder geregistreerde bergingsinhoud of afmetingen | W | Compleetheid | geimplementeerd met test | bergbezinkleidingen, bergbezinkvoorzieningen · Inhoud, NettoBerging, NuttigeBerging, BreedteBouwwerk, LengteBouwwerk, HoogteBouwwerk | — |
| RVZ-008 | BBB zonder ledigingsvoorziening of ledigingsroute terug naar het stelsel | W | Compleetheid | geimplementeerd met test | bergbezinkleidingen, bergbezinkvoorzieningen · — | — |
| RVZ-009 | BBB zonder nooduitlaat of externe overstortdrempel | W | Compleetheid | geimplementeerd met test | bergbezinkleidingen, bergbezinkvoorzieningen, overstortleidingen · Drempelbreedte, Drempelniveau | — |
| RVZ-010 | Interne overstort waarbij beide zijden hetzelfde stelseltype hebben | W | Consistentie | geimplementeerd met test | overstortleidingen, vrijvervalrioolleidingen · — | — |
| RVZ-011 | Waking overstortdrempel kleiner dan 0,40 m (dekselniveau minus drempelniveau) | W | Plausibiliteit | geimplementeerd met test | — · Drempelbreedte, Drempelniveau, Maaiveldhoogte, Putdekselniveau | — |

## BTR

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| BTR-001 | Kritieke hoogtekenmerken (BOB, dekselniveau, drempelniveau) zonder inwinningsmetagegevens | W | Traceerbaarheid | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · — | skelet: vereist inwinningsmetagegevens — Niet gebouwd in deze fase. De De Wolden en Hoogeveen-export bevat 25.546 keer `WijzeVanInwinning` en geen en… |
| BTR-003 | Inwinningsdatum BOB ouder dan drempel, afhankelijk van grondsoort (indicatie: zand 40 jaar, veen 10 jaar) | W | Actualiteit | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · — | skelet: vereist inwinningsmetagegevens — Niet gebouwd in deze fase. Er is geen enkele `DatumInwinning` in de De Wolden en Hoogeveen-export, en er is… |
| BTR-004 | Geregistreerde grondwaterstand boven maaiveld of meer dan 5 m onder maaiveld | W | Plausibiliteit | geimplementeerd met test | netwerkknopen · — | skelet: vereist inwinningsmetagegevens — Niet gebouwd in deze fase. De De Wolden en Hoogeveen-export bevat geen enkel `Grondwaterniveau`-kenmerk; er… |
| BTR-006 | Systematisch afgeronde hoogtewaarden: BOB's of dekselhoogten clusteren op ronde waarden (hele of halve decimeters), indicatie van geschatte in plaats… | W | Precisie | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · BobBeginpuntLeiding, BobEindpuntLeiding, Maaiveldhoogte, Putdekselniveau | — |

## EXT

| ID | Omschrijving | Ernst | Dimensie | Status | Rollen · kenmerken | Toelichting |
| --- | --- | --- | --- | --- | --- | --- |
| EXT-001 | Kruising of nabijheid van BGT-panden en overige bouwwerken; getoetst op strengen en putten, met als uitkomst de relatie binnen, kruist of nabij | W | Plausibiliteit | geimplementeerd met test | netwerkknopen, vrijvervalrioolleidingen · — | — |
| EXT-003 | Kruising met watergang zonder registratie als zinker; een duiker is in het GWSW geen rioolleiding (subklasse van Leiding) en valt buiten de populatie… | W | Compleetheid | geimplementeerd met test | vrijvervalrioolleidingen · VormLeiding | — |
| EXT-004 | Streng op of nabij particulier terrein (op basis van BRK-percelen) | W | Plausibiliteit | geimplementeerd met test | vrijvervalrioolleidingen · — | skelet: bron buiten scope in deze fase — BRK-percelen zijn in deze fase niet aangeleverd en er wordt geen vervangende bron gezocht. De check is als s… |
| EXT-007 | Lozingspunt zonder watergang binnen X m; alleen de klassen die op oppervlaktewater lozen (`[klassen] waterlozingspunt`); scopeafwijking in BO-67 | W | Plausibiliteit | geimplementeerd met test | lozingspunten, waterlozingspunten · — | — |
