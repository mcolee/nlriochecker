# Dekkingsmatrix checkregister

Gegenereerd uit `data/checkregister-gwsw-nulmeting-v0_7.md` (versie 0.7) met `scripts/dekkingsmatrix.py`. Niet met de hand bijwerken.

Status per check-ID: *geimplementeerd met test*, *geimplementeerd zonder test*, *ontbreekt*, of *geschrapt (gedekt door nulmeting)*. Een check die als skelet geregistreerd staat telt als geimplementeerd, maar levert per definitie geen uitslag; de markering en de reden staan in de kolom Toelichting.

| Categorie | Register | Met test | Zonder test | Ontbreekt | Geschrapt |
| --- | ---: | ---: | ---: | ---: | ---: |
| TOP | 21 | 6 | 0 | 15 | 0 |
| NET | 8 | 4 | 0 | 4 | 0 |
| **totaal** | **29** | **10** | **0** | **19** | **0** |

## TOP

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| TOP-001 | Losliggende putten (geen enkele streng aangesloten); geometrische variant, de administratieve koppeling dekt de nulmeting (verplichting exact=1 komt… | F | Consistentie | geimplementeerd met test | — |
| TOP-002 | Losliggende strengen (aan geen van beide zijden een put); geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | — |
| TOP-003 | Streng met slechts aan een zijde een put; geometrische variant, administratieve verplichting alleen via Hyd | F | Consistentie | geimplementeerd met test | — |
| TOP-004 | Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie) | F | Consistentie | geimplementeerd met test | — |
| TOP-005 | Dubbele putten: twee knopen binnen tolerantie (bijv. 0,30 m) | F | Compleetheid | geimplementeerd met test | — |
| TOP-006 | Dubbel ingetekende of (deels) overlappende strengen | F | Compleetheid | ontbreekt | — |
| TOP-007 | Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie | F | Consistentie | ontbreekt | — |
| TOP-008 | Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put) | F | Consistentie | ontbreekt | — |
| TOP-009 | Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten | F | Nauwkeurigheid | ontbreekt | — |
| TOP-010 | Streng met buffer op basis van diameter kruist of raakt andere strengen | F | Plausibiliteit | ontbreekt | — |
| TOP-011 | Hartlijnkruisingen strengen onderling (zonder buffer) | W | Plausibiliteit | ontbreekt | — |
| TOP-012 | Streng met dezelfde put aan begin- en eindpunt | F | Consistentie | geimplementeerd met test | — |
| TOP-013 | Meer dan twee parallelle strengen tussen hetzelfde putpaar | W | Plausibiliteit | ontbreekt | — |
| TOP-014 | Meer dan vier aansluitende strengen op een put | W | Plausibiliteit | ontbreekt | — |
| TOP-015 | Streng of put met multipart-geometrie (meerdere losse delen in een feature) | F | Consistentie | ontbreekt | — |
| TOP-016 | Ongeldige geometrie volgens OGC Simple Features (ST_IsValid: zelf-intersectie, niet-gesloten ringen) | F | Consistentie | ontbreekt | — |
| TOP-017 | Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren) | W | Consistentie | ontbreekt | — |
| TOP-018 | Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie | W | Consistentie | ontbreekt | — |
| TOP-019 | Pseudo-knoop: twee strengen gescheiden door een functieloze knoop, met identieke attributen (diameter, materiaal, stelseltype); zouden een streng moe… | W | Consistentie | ontbreekt | — |
| TOP-020 | Digitalisatierichting (begin- naar eindvertex) komt niet overeen met de administratieve van-naar-richting | W | Consistentie | ontbreekt | — |
| TOP-021 | Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een doorlopende streng (verfijning van TOP-001) | W | Consistentie | ontbreekt | — |

## NET

| ID | Omschrijving | Ernst | Dimensie | Status | Toelichting |
| --- | --- | --- | --- | --- | --- |
| NET-001 | Vuilwater- of gemengde streng zonder afvoerpad naar gemaal of overnamepunt (bereikbaarheidsanalyse) | F | Consistentie | geimplementeerd met test | — |
| NET-002 | Hemelwaterstreng zonder afvoerpad naar lozingspunt of overnamepunt | F | Consistentie | geimplementeerd met test | — |
| NET-003 | Strengorientatie tegen de afvoerrichting in | F | Consistentie | ontbreekt | — |
| NET-004 | Cirkels (kringlopen) in het vrijvervalnetwerk | F | Consistentie | geimplementeerd met test | — |
| NET-005 | Stelseltype streng wijkt af van boven- en benedenstroomse buren | F | Consistentie | ontbreekt | — |
| NET-006 | Koppelingen tussen verschillende stelseltypen | W | Plausibiliteit | ontbreekt | — |
| NET-007 | IT-stelsel zonder drempel | F | Compleetheid | geimplementeerd met test | — |
| NET-008 | Opvallend veel lozingspunten binnen een klein deelstelsel | W | Plausibiliteit | ontbreekt | — |
