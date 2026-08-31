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
deelgebieden onderling en zouden de schil tot de hele gemeente laten uitdijen. Binnen de
analyseset volgen de bereikbaarheidschecks NET-001 en NET-002 ze sinds issue #72 wel, als
ongerichte connectiviteit (BO-54); de afbakening van de schil blijft vrijverval.

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
| TOP-002 | Losliggende strengen (aan geen van beide zijden een put); geometrische variant, administratieve verplichting alleen via Hyd. Als geldig eind telt naast een put ook een hulpstuk met een telbare GWSW-functie (T-stuk, kruisstuk, mof): een streng die tussen twee T-stukken ligt komt ergens op uit. Mist zo'n hulpstuk zelf een leiding, dan meldt TOP-022 dat. v0.9 kende alleen de put als eindobject; afwijking in BO-72 (issue #89) | F | Consistentie |
| TOP-003 | Streng met slechts aan een zijde een put; geometrische variant, administratieve verplichting alleen via Hyd. Zelfde afbakening van het eindobject als TOP-002: ook een hulpstuk met een telbare GWSW-functie telt mee (BO-72, issue #89) | F | Consistentie |
| TOP-004 | Strengeindpunt niet gesnapt op putlocatie (afstand > tolerantie) | F | Consistentie |
| TOP-005 | Dubbele putten: twee knopen binnen tolerantie (bijv. 0,30 m) | F | Compleetheid |
| TOP-006 | Dubbel ingetekende of (deels) overlappende strengen. Beide leidingen van een paar moeten een `VrijvervalRioolleiding` of een `Duiker` zijn (`[klassen] nabijheidsleiding`); drains, mechanische leidingen en aansluitleidingen vallen erbuiten, want een vrijvervalriool dat daar dwars doorheen ligt is geen gebrek. v0.9 zei "strengen" zonder die afbakening; afwijking in BO-69 (issue #82) | F | Compleetheid |
| TOP-007 | Nul-lengte, zelfkruisende of anderszins degeneratieve geometrie | F | Consistentie |
| TOP-008 | Vrijvervalstreng niet recht van put tot put (bogen, knikpunten zonder put) | F | Consistentie |
| TOP-009 | Objecten buiten beheergebied of buiten valide RD-bereik, ontbrekende coordinaten | F | Nauwkeurigheid |
| TOP-010 | Streng met buffer op basis van diameter kruist of raakt andere strengen. Zelfde populatie-afbakening als TOP-006: beide leidingen van een paar zijn een `VrijvervalRioolleiding` of een `Duiker` (BO-69, issue #82) | F | Plausibiliteit |
| TOP-011 | Hartlijnkruisingen strengen onderling (zonder buffer). Zelfde populatie-afbakening als TOP-006 (BO-69, issue #82) | W | Plausibiliteit |
| TOP-012 | Streng met dezelfde put aan begin- en eindpunt | F | Consistentie |
| TOP-013 | Meer dan twee parallelle strengen tussen hetzelfde putpaar | W | Plausibiliteit |
| TOP-014 | Meer dan vier aansluitende strengen op een put | W | Plausibiliteit |
| TOP-015 | Streng of put met multipart-geometrie (meerdere losse delen in een feature) | F | Consistentie |
| TOP-016 | Ongeldige geometrie volgens OGC Simple Features (ST_IsValid: zelf-intersectie, niet-gesloten ringen) | F | Consistentie |
| TOP-017 | Niet-simple geometrie (ST_IsSimple: spikes, herhaalde structuren) | W | Consistentie |
| TOP-018 | Opeenvolgende dubbele vertices of spikes (hoek nabij 0 graden) in strenggeometrie | W | Consistentie |
| TOP-019 | Pseudo-knoop: twee strengen gescheiden door een functieloze knoop, met identieke attributen (diameter, materiaal, stelseltype); zouden een streng moeten zijn | W | Consistentie |
| TOP-021 | Put valt niet samen met enig strengeindpunt maar ligt wel naast of op een doorlopende streng (verfijning van TOP-001) | W | Consistentie |
| TOP-022 | Hulpstuk verbindt minder leidingen dan zijn GWSW-functie voorschrijft. Het verwachte aantal volgt uit de `functie`-restrictie op de klasse in de ontologie (`VerbindenVanTweeLeidingen` 2 voor `Mof`, `VerbindenVanDrieLeidingen` 3 voor `T_stuk` en `Y_stuk`, `VerbindenVanVierLeidingen` 4 voor `Kruisstuk`); geteld naar verschillende knopen aan de andere kant, zodat een dubbel gelegde richting een keer telt. Klassen zonder aantal in hun functie (`Afsluitstuk`, `Ontstoppingsstuk`, `Tubelure`, `Bochtstuk`, `Verloopstuk`, `Overgangsstuk`) vallen erbuiten en worden in de toelichting geteld. De nulmeting kent geen kardinaliteit op `hasConnection` van een hulpstuk (issue #60) | F | Consistentie |
| TOP-023 | Hulpstuk verbindt meer leidingen dan zijn GWSW-functie voorschrijft; waarschijnlijk de verkeerde klasse gekozen (voor vier bestaat `Kruisstuk`). Zelfde telling als TOP-022 (issue #60) | W | Consistentie |

## ADM: Administratief en referentieel

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| ADM-002 | Niet-unieke identificaties van putten of strengen; uitvoeren op de bronexport, voor de OroX-conversie (duplicaat-ID's smelten in RDF geruisloos samen) | F | Consistentie |
| ADM-003 | Naamgeving knopen en strengen wijkt af van conventie (patroon configureerbaar) | F | Compliance |
| ADM-006 | Vervallen of geplande objecten die topologisch meedoen in het actieve netwerk | W | Consistentie |
| ADM-007 | Puttype past niet bij het type aangesloten leiding (bijv. overstortput zonder overstortfunctie in het netwerk); netwerkfunctionele toets, de samenstellingsregels per puttype dekt de nulmeting | F | Consistentie |
| ADM-008 | Putcompartimenten of -onderdelen zonder onderlinge verbinding binnen de put | W | Consistentie |
| ADM-009 | Leiding gekoppeld aan de put als geheel waar koppeling aan een compartiment vereist is | W | Consistentie |
| ADM-010 | Loze leiding (`LozeLeiding` en subklassen: buiten gebruik, nog in de ondergrond) waar actief riool op aansluit. Loze leidingen die een knoop delen vormen een keten; per keten in de administratieve richting: actief riool dat in een beginknoop eindigt (aanvoer), actief riool dat in een eindknoop begint (afvoer), of beide (doorgaand: het actieve riool loopt volgens het model door een buiten gebruik gestelde streng). Melding per loze streng met de keten in `cluster_id` en het aantal actieve strengen bovenstrooms als detail; de nulmeting noemt loze leidingen alleen voor attribuutgebreken, nooit voor hun plaats in het net (issue #62) | F | Consistentie |

## ATTR: Attribuutplausibiliteit

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| ATTR-001 | Diameter past niet bij materiaal | F | Plausibiliteit |
| ATTR-002 | Diameter kleiner dan rond 200 mm (de nulmeting toetst alleen de extreme ondergrens van 63 mm) | W | Plausibiliteit |
| ATTR-003 | Materiaal past niet bij begindatum (bijv. PVC voor 1955, PE voor 1970) | W | Plausibiliteit |
| ATTR-004 | Vorm versus afmetingen inconsistent (eivorm zonder hoogte, rond met breedte ongelijk hoogte); NB het MDSTOP-deelmodel dwingt de aanwezigheid van breedte en hoogte per leiding af (someValuesFrom in de Top-laag), Hyd verplicht breedte exact=1; de consistentietoets vorm versus afmetingen doet geen van beide | F | Consistentie |
| ATTR-005 | Eenhedenfouten die binnen de GWSW-waardebereiken vallen (bijv. diameter 300 genoteerd in cm); fouten buiten bereik dekt de nulmeting | F | Nauwkeurigheid |
| ATTR-006 | Strengdiameter groter dan afmeting van de aangesloten put | W | Plausibiliteit |
| ATTR-007 | Begindatum in de toekomst of voor 1870 (de nulmeting toetst alleen datatype, geen bereik) | W | Plausibiliteit |
| ATTR-009 | Geometrische lengte wijkt meer dan X% af van administratieve lengte | W | Consistentie |
| ATTR-010 | Leidingmateriaal beton of metselwerk terwijl het putmateriaal daar niet bij past | W | Plausibiliteit |
| ATTR-012 | Materiaal past niet bij profielvorm (bijv. metselwerk met rond profiel in plaats van ei- of muilprofiel) | W | Plausibiliteit |
| ATTR-013 | Hoogtekenmerk (BOB, maaiveldhoogte, putdekselniveau) op een vulwaarde rond 0 m NAP dat als meting geregistreerd staat; de band en de kenmerken zijn projectconfiguratie (`[vulwaarden]`), de leesregel zet het kenmerk op ontbrekend en de hoogtechecks slaan het object over | W | Compleetheid |
| ATTR-014 | Kenmerk gebruikt `hasValue` waar de ontologie via een restrictie `hasReference` naar een collectie eist (of andersom); een fout die de SHACL-nulmeting per constructie mist (issue #37). Generiek over alle kenmerktypen, uit de ontologische `owl:onProperty`/`owl:allValuesFrom`-keten; een systemische melding per kenmerk, niet per object | F | Consistentie |
| ATTR-015 | Jaartal draagt een onevenredig deel van de begindatums (mogelijke vulwaarde); een signaaldetector, geen norm, met een instelbare drempel (`begindatum_vulwaarde_aandeel`); een systemische melding per verdacht jaar, zwijgt bij een natuurlijke verdeling of bij te weinig gedateerde objecten (issue #21) | W | Compleetheid |
| ATTR-016 | Vorm put versus afmetingen inconsistent: een ronde put (`VormPut = Rond`) waarvan breedte en lengte verschillen; een ronde put heeft een diameter. De tegenhanger van ATTR-004 voor putten in plaats van leidingen, met dezelfde tolerantie (`rondheid_tolerantie_mm`); de nulmeting toetst alleen de aanwezigheid van de vorm (`Put_VormPut_card`), niet de samenhang met de afmetingen (issue #39) | F | Consistentie |
| ATTR-017 | Wandruwheid (`WandruwheidBinnenboven`/`-onder`) past niet bij het leidingmateriaal; de aannemelijke band per materiaal komt uit Leidraad Riolering C2100 tabel B2.1 (`plausibiliteit.toml`). Het GWSW-datatype is een geheel getal in mm en kan de kunststofwaarden niet uitdrukken, dus de schaal wordt uit de data afgeleid (`wandruwheid_schalen`); de nulmeting toetst de wandruwheid nergens (issue #38, BO-39) | W | Plausibiliteit |
| ATTR-018 | Begindatum ontbreekt op een vrijvervalrioolleiding of put. ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een aanwezige datum en de nulmeting eist `Begindatum` in geen van de drie CFK-rapporten; zonder aanlegjaar is er geen vervangingsplanning, geen levensduur en geen ATTR-003. Mechanisch riool valt buiten de populatie en wordt in de toelichting geteld (issue #61) | F | Compleetheid |

## HGT: Hoogten en verhang

Hyd dwingt het bestaan van alle benodigde hoogtedata af (BOB begin- en eindpunt min=1, maaiveldhoogte, drempelniveau); Mds dwingt daarvan maaiveldhoogte, putdekselniveau en drempelniveau af, maar laat de BOB's optioneel (min=0). Deze categorie toetst uitsluitend de waarde-logica.

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| HGT-001 | Dekselhoogte wijkt af van AHN: 10 cm of meer (v0.9 zei "meer dan 5 cm"; afwijking in BO-44); is de gebruikte hoogte zelf uit een hoogtemodel ingewonnen, dan vergelijkt de check twee modellen en krijgt de bevinding een kanttekening (wijzen configureerbaar) | W | Nauwkeurigheid |
| HGT-002 | Dekselhoogte wijkt af van AHN: 25 cm of meer; zelfde kanttekening als HGT-001 | F | Nauwkeurigheid |
| HGT-003 | BOB-sanity ten opzichte van AHN (boven maaiveld, meer dan 4,0 m eronder; v0.9 zei "meer dan 3 m"; afwijking in BO-68) | F | Plausibiliteit |
| HGT-004 | BOB hoger dan dekselhoogte van de eigen put, of lager dan de putbodem | F | Consistentie |
| HGT-006 | Tegenverhang bij vrijverval: fors (boven drempel) | F | Plausibiliteit |
| HGT-007 | Verhang vuilwater of gemengd onder drempelwaarde | W | Plausibiliteit |
| HGT-008 | Extreem verhang (steiler dan bijv. 1:50; v0.9 zei "…, indicatie verwisselde BOB's"; tekstherstel in #84) | W | Plausibiliteit |
| HGT-009 | BOB-sprong tussen aansluitende strengen boven drempel zonder valput | W | Plausibiliteit |
| HGT-010 | Diameterverkleining in afvoerrichting (benedenstrooms kleiner dan bovenstrooms) | W | Plausibiliteit |
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
| NET-001 | Vuilwater- of gemengde streng zonder afvoerpad naar gemaal, overnamepunt of lozingspunt (bereikbaarheidsanalyse); een pompput telt niet als eindpunt, dus de configuratie moet de mechanische leidingklassen noemen zodat de route door het persnet traceerbaar is. Een hulpstuk met een telbare GWSW-functie geldt als knoop in het net (BO-83) | F | Consistentie |
| NET-002 | Hemelwaterstreng zonder afvoerpad naar lozingspunt; een overnamepunt of gemaal telt ook als bestemming zodra de streng benedenstrooms in gemengd riool overgaat (BO-88) | F | Consistentie |
| NET-004 | Cirkels (kringlopen) in het vrijvervalnetwerk; gezocht op de betrouwbare richting (de strengen die NET-009 niet tegenspreekt). Een kring die alleen administratief bestaat valt uiteen en telt niet; een vlakke BOB-consistente ring is bewust vermaasd net (legitiem) en een ring die via een BOB-sprong omhoog sluit hoort bij HGT-009 -- beide gedempt (BO-77) | F | Consistentie |
| NET-005 | Stelseltype streng wijkt af van boven- en benedenstroomse buren | F | Consistentie |
| NET-006 | Ongeldige koppeling tussen stelseltypen: een gerichte koppeling (bovenstroom → benedenstroom, op de betrouwbare stroomrichting) die niet in de configureerbare koppelmatrix `[koppelregels]` staat. Koppelingen zonder betrouwbare richting en typeloze strengen worden niet beoordeeld (BO-87) | W | Plausibiliteit |
| NET-007 | IT-stelsel zonder drempel | F | Compleetheid |
| NET-008 | Opvallend veel lozingspunten binnen een klein deelstelsel | W | Plausibiliteit |
| NET-009 | Richtingssignalen (administratie, geometrie, BOB) spreken elkaar tegen | W | Consistentie |

## RVZ: Randvoorzieningen (BBB's, overstorten, drempels)

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| RVZ-001 | Randvoorziening (BBB, overstortput) topologisch niet aangesloten op het netwerk; geometrisch-topologische variant, de administratieve koppeling dekt de nulmeting | F | Consistentie |
| RVZ-002 | Overstort zonder geregistreerd drempelniveau en/of drempelbreedte (Drempelniveau, Drempelbreedte), ook als het drempelonderdeel zelf ontbreekt; één melding per put die zegt welke maat mist. RVZ-003 (aparte breedtecheck) is hierin opgegaan (BO-78). Overlapt bewust met de nulmetingvorm Overstortput_Overstortdrempel_card, want die toetst alleen of de put een drempel heeft, dekt de Stuwput niet en de check werkt ook zonder nulmeting | W | Compleetheid |
| RVZ-004 | Externe overstort zonder ontvangend oppervlaktewater binnen X m | W | Plausibiliteit |
| RVZ-005 | Overstort aangesloten op een hemelwater- of IT-stelsel | W | Consistentie |
| RVZ-006 | Gemengd deelstelsel zonder enige externe overstort of BBB, óf zonder afvoereindpunt (gemaal of overnamepunt); het deelstelsel loopt door over een hulpstuk met een telbare GWSW-functie, dat als knoop in het net geldt (BO-83). De melding noemt de aanwijzingen bij het gebrek (aandeel gemengd, samenvallende knoop, knoop op streng, persleiding, lozingspunt); ze verklaren het en veranderen de uitslag niet (BO-84) | F | Plausibiliteit |
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
| BTR-003 | Inwinningsdatum BOB ouder dan drempel, afhankelijk van grondsoort (indicatie: zand 40 jaar, veen 10 jaar) | W | Actualiteit |
| BTR-004 | Geregistreerde grondwaterstand boven maaiveld of meer dan 5 m onder maaiveld | W | Plausibiliteit |
| BTR-006 | Systematisch afgeronde hoogtewaarden: BOB's of dekselhoogten clusteren op ronde waarden (hele of halve decimeters), indicatie van geschatte in plaats van gemeten waarden | W | Precisie |

## EXT: Externe bronnen (BGT, BAG, waterschap, BRK)

| ID | Check | Ernst | Dimensie |
|---|---|---|---|
| EXT-001 | Kruising of nabijheid van BGT-panden en overige bouwwerken; getoetst op strengen en putten, met als uitkomst de relatie binnen, kruist of nabij | W | Plausibiliteit |
| EXT-003 | Kruising met watergang zonder registratie als zinker; een duiker is in het GWSW geen rioolleiding (subklasse van Leiding) en valt buiten de populatie van deze check, het rapport meldt hoeveel dat er zijn. Getoetst wordt op BGT-waterdelen; waterschapsdata is toegestaan maar niet aangeleverd | W | Compleetheid |
| EXT-004 | Streng op of nabij particulier terrein (op basis van BRK-percelen) | W | Plausibiliteit |
| EXT-007 | Lozingspunt zonder watergang binnen X m; alleen de klassen die op oppervlaktewater lozen (`[klassen] waterlozingspunt`); scopeafwijking in BO-67 | W | Plausibiliteit |
| EXT-009 | Straat in de bebouwde kom zonder vrijvervalriolering. Het toetsobject is een NWB-wegvak en geen GWSW-object: gemeentelijk beheer, geen pad of parkeervak, minstens de minimale lengte, en het middelpunt in een TOP10NL-vlak met `bebouwdekom = ja`. De maat is de lengte vrijvervalstreng in het eigen straatvlak (de voronoi-cel om de wegas, geknipt op buffer en komgrens) gedeeld door de straatlengte; een put in dat vlak telt als bediend (lus- en hoefijzerwegen). Drie uitkomsten in plaats van twee: naast bediend en leeg is er *niet beoordeeld* voor een overwegend onverharde straat en voor een straat met drukriolering-indicatie (BO-79). Deterministische regel, geen model (BO-81); de bronafhankelijkheid staat in BO-80 | W | Compleetheid |

## Geschrapte checks (gedekt door GWSW-nulmeting)

Schrapronde d.d. 2026-08-14, geactualiseerd naar toetsbasis Mds. Oorspronkelijke dekkinganalyse op basis van MdsPlan v1.5 SHACL en deelmodellen MdsPlan en Hyd v1.6; herverifieerd op de deelmodellen Mds v1.6 (filter collectie_MDSTOP_v16) en Hyd v1.6 (filter collectie_HYDTOP5_v16, detailrapporten De Wolden). Voorwaarden voor geldigheid van de dekking: (1) de dataset wordt aan beide conformiteitsklassen getoetst; dit is een harde eis, want de verplichting van de administratieve put-strengkoppeling komt uitsluitend uit Hyd; (2) de objecttypering is op orde; bij te globaal getypeerde objecten verklaart de nulmeting haar eigen vervolgvalidaties onbetrouwbaar; (3) de sentineltabel waarmee de dekking wordt aangetoond hoort bij deze registerversie, en elke geschrapte check heeft er een sentinel in.

Alle drie de voorwaarden worden machinaal gehandhaafd (2026-08-16). Voorwaarde 1 laat de pijplijn falen zodra een conformiteitsklasse ontbreekt of de rapporten over verschillende RDF-bestanden gaan. Voorwaarde 2 zet een voorbehoud op elke dekkingclaim waarvan een vereiste CFK onder de typeringsdrempel scoort. Voorwaarde 3 legt de sentineltabel naast dit register en faalt bij versieverschil of een gat aan een van beide kanten. Daarnaast meldt de dekkinganalyse bewijsvormen die in de ene vereiste CFK wel en in de andere geen meldingen opleveren: omdat alle CFK's hetzelfde RDF-bestand toetsen, kan dat niet aan schone data liggen en rust een claim "beide CFK's" dan in werkelijkheid op een deel ervan. Een geschrapte check zit niet in de engine, dus als de dekking vervalt kijkt er niets anders meer naar.

| ID | Check | Gedekt door |
|---|---|---|
| ADM-001 | Streng verwijst naar niet-bestaande begin- of eindput | Generieke melding gerefereerd object onbekend (CFK-onafhankelijk); verplichte aanwezigheid van de koppeling alleen via Hyd (hasConnection Knooppunt exact=1); Mds eist slechts max=1 |
| ADM-004 | Verplichte GWSW-MdS-attributen niet gevuld | Mds via Top-laag van het MDSTOP-filter (someValuesFrom: materiaal, vorm, lengte, breedte, hoogte leiding) plus Mds-eigen min-eisen (putdekselniveau, maaiveldhoogte); Hyd aanvullend inclusief BOB's, afmetingen exact=1 en de put-vormen materiaal (MateriaalPut) en maaiveldschematisering (Maaiveldschematisering) — die twee hasAspect-eisen (exact=1) leveren uitsluitend in Hyd meldingen op (4142 resp. 20756 op De Wolden, nul in MdsPlan en MdsProj op hetzelfde RDF-bestand), dus de dekking van díé twee attributen rust op Hyd en niet op Mds (mechanisch na te lopen via [#41](https://github.com/mcolee/nlriochecker/issues/41)) |
| ADM-005 | Attribuutwaarden buiten de GWSW-domeinlijsten | Beide CFK's: collectietoetsing hasReference |
| ATTR-008 | Strenglengte korter dan X m of langer dan X m | Alle drie de CFK's: waardebereik LengteLeiding 1-75 m (vorm LengteLeiding_val, bevestigd in Mds-datatype Dt_LengteLeiding) — dezelfde dekking als ATTR-011. Gemeten op De Wolden en Hoogeveen (checkaudit 27-08): alle 443 ATTR-008-objecten staan ook in LengteLeiding_val, die er 932 telt en dus breder is (ook drains, duikers en aansluitleidingen) |
| ATTR-011 | Absurde lengtewaarde boven harde bovengrens | Beide CFK's: waardebereik LengteLeiding 1-75 m (bevestigd in Mds-datatype Dt_LengteLeiding) |

## Vervallen checks (niet relevant, of zonder bruikbare bron)

Anders dan de geschrapte checks hierboven zijn deze niet door de nulmeting gedekt; er
kijkt niets meer naar. Er zijn twee gronden om te vervallen, en de kolom Reden zegt per
rij welke van de twee geldt. De eerste is inhoudelijk: de check geeft voor deze opdracht
geen bruikbare uitkomst, en komt dus ook niet terug. De tweede is de bron: de vraag is op
zichzelf zinvol, maar de gegevens die de check nodig heeft bestaan in deze aanlevering
niet en er komen er ook geen -- die checks vervallen *voor nu* en herleven zodra de bron
er wel is. De ID's worden in beide gevallen niet hergebruikt; een herleefde check komt
terug onder een nieuw ID.

| ID | Check | Vervallen in | Reden |
|---|---|---|---|
| EXT-008 | BAG-verblijfsobject zonder riolering binnen X m (dekkingscheck) | v0.8 | Niet relevant voor deze opdracht: de vraag of elk pand op riolering is aangesloten hoort bij het rioleringsplan, niet bij een datakwaliteitstoets op de bestaande registratie. Bovendien zijn er panden aangeleverd en geen verblijfsobjecten, waardoor de check alleen een benadering kon geven. |
| ADM-011 | Loze leiding in een keten zonder aansluiting op actief riool in de afvoerrichting | v0.9 | Meldde het gewenste eindbeeld als gebrek: een loze leiding is buiten gebruik gesteld, en dat zij geen verbinding meer heeft met het actieve net is precies goed. Er valt niets te herstellen. Het echte gebrek -- actief riool dat wel op een loze keten aansluit -- meldt ADM-010 (F) en dat blijft ongewijzigd. De ketenbouw blijft bestaan en telt de losgekoppelde ketens in de verantwoording van ADM-010. Zie de checkaudit (`docs/checks-audit-2026-08.md`, PRE-2), [#81](https://github.com/mcolee/nlriochecker/issues/81) en BO-60. |
| BTR-002 | Kritieke kenmerken ingewonnen via schatting, plan of ontwerp in plaats van meting | v0.9 | Vervallen *voor nu*: de bron ontbreekt. De inwinningswijze staat op te weinig kritieke kenmerken om een uitslag te dragen (537 van de 46.880 BOB's). De overwogen tussenstap op alleen de maaiveldhoogte is door de auteur afgewezen, want die versmalt de check ten opzichte van dit register. Herleeft zodra een export de wijze op de BOB's zelf meelevert; dan komt hij terug onder een nieuw ID. Zie [#95](https://github.com/mcolee/nlriochecker/issues/95) en BO-62. |
| BTR-005 | Toestands- of inspectiegegevens ouder dan drempel, gewogen naar risicoligging (spoor, dijk, wegfunctie) | v0.9 | Vervallen *voor nu*: twee bronnen ontbreken. De export bevat geen inspectie- of toestandsgegevens, en de weging naar risicoligging vraagt bronnen (spoor, dijk, wegfunctie) die niet zijn aangeleverd. Herleeft zodra er inspectiedata en een risicowegingsbron zijn; dan komt hij terug onder een nieuw ID. Zie [#95](https://github.com/mcolee/nlriochecker/issues/95) en BO-63. |
| EXT-005 | Put zonder BGT-putdeksel binnen X m | v0.9 | Vervallen *voor nu*: er is geen bruikbare putdeksellaag. De BGT-laag `put` telt in De Wolden en Hoogeveen 843 objecten (595 van ProRail) tegenover ruim 23.000 GWSW-putten, en een gemeentelijke deksellaag komt er niet. Herleeft zodra er een deksellaag is die het gebied dekt; dan komt hij terug onder een nieuw ID. Zie [#95](https://github.com/mcolee/nlriochecker/issues/95) en BO-64. |
| EXT-006 | BGT-putdeksel zonder put in de beheerdata | v0.9 | Vervallen *voor nu*, met EXT-005 mee: dezelfde ontbrekende deksellaag, van de andere kant bekeken. De twee staan of vallen met dezelfde bron. Zie [#95](https://github.com/mcolee/nlriochecker/issues/95) en BO-65. |
| EXT-002 | Kruising met watergang (waterschaps- of BGT-data) | v0.9 | Niet relevant voor deze opdracht: een kruising met een watergang is op zichzelf geen gebrek en draagt geen handelingsperspectief. De vraag die er wél een draagt -- moet deze streng een zinker zijn? -- stelt EXT-003, en die meldde op De Wolden en Hoogeveen exact dezelfde 281 strengen en dezelfde 319 doorkruisingen (audit 27-08), want de export bevat geen enkele als zinker geregistreerde streng. EXT-003 blijft en is nu de enige watergangmelding; de doorkruisingen die hij overslaat blijven in zijn toelichting geteld. Zie de checkaudit (`docs/checks-audit-2026-08.md`, PRE-4), [#83](https://github.com/mcolee/nlriochecker/issues/83) en BO-66. |
| NET-003 | Strengorientatie tegen de afvoerrichting in | v0.9 | Opgegaan in de integrale richtingscheck NET-009. NET-003 meldde een BOB die in de van-naar-richting stijgt; gemeten op De Wolden en Hoogeveen (audit 27-08) staan alle 3.651 NET-003-objecten óók in de 3.656 van NET-009. De BOB-tegen-richting is nu een deelgeval van NET-009, dus er gaat geen signaal verloren. Zie de checkaudit (`docs/checks-audit-2026-08.md`, PRE-1), [#80](https://github.com/mcolee/nlriochecker/issues/80) en BO-76. |
| TOP-020 | Digitalisatierichting (begin- naar eindvertex) komt niet overeen met de administratieve van-naar-richting | v0.9 | Opgegaan in de integrale richtingscheck NET-009. TOP-020 meldde het losse cosmetische signaal (tekenrichting tegen de administratie); NET-009 leest de tekenrichting samen met de administratie en de BOB. Zie de checkaudit (`docs/checks-audit-2026-08.md`, PRE-1), [#80](https://github.com/mcolee/nlriochecker/issues/80) en BO-76. |
| HGT-005 | Tegenverhang bij vrijverval: licht (onder drempel) | v0.9 | Opgegaan in NET-009. Licht tegenverhang (1 tot 5 cm) is in vlak Nederland inwinnauwkeurigheid zonder handelingsperspectief; gemeten staan 1.284 van de 1.285 HGT-005-objecten óók in NET-009 (audit 27-08). De richting meldt NET-009; HGT-006 (fors) blijft als F bestaan, met de forsgrens per #80 op 0,10 m. Zie de checkaudit (`docs/checks-audit-2026-08.md`, PRE-1), [#80](https://github.com/mcolee/nlriochecker/issues/80) en BO-76. |
| RVZ-003 | Overstort zonder geregistreerde drempelbreedte | v0.9 | Opgegaan in RVZ-002. Dezelfde populatie (overstortputten), ernst (W), dimensie (Compleetheid) en herstelhandeling als de niveaucheck RVZ-002; op De Wolden en Hoogeveen meldden de twee exact dezelfde 245 putten (audit 27-08), want de export draagt geen enkel drempelobject en dan ontbreken beide maten samen. RVZ-002 noemt nu in één melding per put welke van {Drempelniveau, Drempelbreedte} ontbreekt. Zie de checkaudit (`docs/checks-audit-2026-08.md`, S2), [#87](https://github.com/mcolee/nlriochecker/issues/87) en BO-78. |

## Open punten

1. Verplaatst naar de issuetracker: [#8 EXT-004 bouwen op BRK-percelen](https://github.com/mcolee/nlriochecker/issues/8).
2. Afgehandeld (2026-08-19). Alle vijf staan als instelbare waarde in `[drempels]` van de projectconfiguratie, met de standaard tussen haakjes: snapping-tolerantie (`snapping_tolerantie_m`, 0,10 m), min/max strenglengte (`minimale_strenglengte_m` 1 m en `maximale_strenglengte_m` 200 m, ATTR-008), minimaal verhang voor vuilwater en gemengd (HGT-007; sinds issue #29 geen enkele waarde meer maar de RIONED-diameterstaffel `[[verhang_staffel]]`, met 1:250 voor de kleinste leidingen tot 1:1000 voor de grootste), valput-drempel (`bob_sprong_m`, 0,25 m, HGT-009 en HGT-016) en de bufferafstanden van de EXT-checks (`ext_pand_buffer_m`, `ext_watergang_buffer_m`, `ext_putdeksel_afstand_m`, `ext_lozingspunt_water_afstand_m`, `ext_perceel_buffer_m`). Er staat geen drempel hardgecodeerd in de engine.
3. Afgehandeld (2026-08-19). `naamgeving.putpatroon` en `naamgeving.strengpatroon` in de projectconfiguratie nemen elk een regex, en een onbruikbaar patroon faalt bij het laden in plaats van tijdens de run. Er is bewust geen standaardpatroon: staat er geen, dan draait ADM-003 niet en meldt het rapport dat met zoveel woorden, want een verzonnen conventie zou elke dataset afkeuren. `examined` telt dan ook alleen de objectsoorten waarvoor wel een patroon geldt.
4. Buiten scope: persleiding- en gemaalconsistentiechecks (mechanisch); gemalen, overnamepunten en lozingspunten doen wel mee als eindpunt in NET-001, en het mechanische riool telt sinds issue #72 als ongerichte connectiviteit mee in de bereikbaarheidsgraaf (BO-53 en BO-54). Getoetst wordt het mechanische riool niet.
5. RVZ-008 (lediging BBB) raakt de scopegrens: lediging loopt in de praktijk vaak via een gemaal. De check toetst alleen of er een ledigingsroute geregistreerd staat, niet het gemaal zelf. NB: de nulmeting dekt dit niet (Ledigingsvoorziening heeft in beide CFK's, Mds en Hyd, max=1 en geen min-eis); alleen als er wel een ledigingsvoorziening geregistreerd is, eist Hyd daarin minimaal een pomp.
6. Afgehandeld (2026-08-19). Empirisch vastgesteld op de De Wolden-export en vastgelegd in de beslislog: overstorten staan er als `Overstortput` met een `Overstortleiding` eraan; losse `Overstortdrempel`-objecten met `Drempelniveau` en `Drempelbreedte` komen er niet in voor, terwijl het GWSW-voorbeeldbestand ze wel kent. `checks/randvoorzieningen.py` leest daarom beide vormen en meldt in de toelichting welke het in deze dataset heeft aangetroffen; de klassen staan in `[klassen]` van de projectconfiguratie (`overstortput`, `overstortleiding`, `drempel`). RVZ-004 t/m RVZ-011 zijn gebouwd en draaien. NB: dezelfde vraag speelt voor `Overnamepunt` en voor het IT-stelsel. Die twee zijn eerder ten onrechte als ontbrekende GWSW-begrippen opgeschreven; de ontologie kent ze wel (`Overnamepunt` als subklasse van `Aansluitpunt`, het IT-stelsel als `Infiltratiestelsel` met zijn subklasse `DrainageInfiltratieTransportStelsel`), maar de De Wolden-export levert nul `Overnamepunt`-instanties. Wat er wel en niet uit volgt staat in BO-33 en BO-34 van de beslislog; het spoor loopt via [#11](https://github.com/mcolee/nlriochecker/issues/11).
7. Afgehandeld: schrapronde uitgevoerd en geactualiseerd naar toetsbasis Mds, zie tabel Geschrapte checks. Afwijkingen ten opzichte van de oorspronkelijke verwachting: ADM-002 en ADM-003 blijven staan (duplicaat-ID's smelten in RDF geruisloos samen respectievelijk geen patroontoetsing), ADM-008/009 blijven staan (in de nulmeting-beschrijving expliciet aangemerkt als externe validatie), ATTR-011 is juist wel geschrapt; RVZ-003 was dat ook maar is in v0.9 teruggehaald (issue #6) en vervolgens opgegaan in RVZ-002 (issue #87, BO-78; ID vervalt, wordt nooit hergebruikt). In het proces borgen dat beide nulmeting-rapporten (Mds en Hyd) beschikbaar zijn en dat de typeringsscore als voorwaarde geldt.
8. Afgehandeld voor de inwinningswijze; open voor de rest. De eerste run op De Wolden (2026-08-16) laat zien dat BTR-001 t/m BTR-005 op deze export inderdaad vrijwel alleen ontbreken-meldingen opleveren: er is geen enkele `DatumInwinning` en geen `Grondwaterniveau`, en de wijze hangt aan de puntgeometrie in plaats van aan het kenmerk (zie de inleiding van BTR). BTR-001, BTR-003 en BTR-004 blijven skelet; BTR-002 en BTR-005 zijn met [#95](https://github.com/mcolee/nlriochecker/issues/95) vervallen voor nu, zie de tabel Vervallen checks. Een voorgestelde uitbreiding BTR-008 (inwinningswijze past niet bij het kenmerk) is afgewezen, zie de BTR-inleiding. Twee andere kandidaten, placeholder-datums en expliciete onbekend-waarden, zijn afgewezen als check en opgenomen als datakarakteristieken in de kop van het bevindingenrapport: ze slaan op vrijwel de hele dataset aan en leveren per object geen handeling op, maar bepalen wel op welke precisie leeftijden gelden en hoe rooskleurig een compleetheidscijfer leest.
9. Uit het onderzoeksrapport zijn de geometrie- en hoogtechecks verwerkt (N2 t/m N5, N7, N17 t/m N22, als TOP-015 t/m TOP-021, ATTR-011/012, HGT-016 t/m HGT-018). N1 (BOB onder putbodem) was al gedekt door HGT-004. Het restant is verplaatst naar de issuetracker: [#9 Resterende checks uit het onderzoeksrapport](https://github.com/mcolee/nlriochecker/issues/9).
10. Deels afgehandeld (2026-08-16). Wat een regressietoets per run kan bewaken, wordt nu bewaakt; zie de voorwaarden bij Geschrapte checks. Wat niet kan: de rapportkoppen van de GWSW-server bevatten geen CFK-versie of filternaam, dus of de meting nog op deelmodel v1.6 en de filters collectie_MDSTOP_v16 en collectie_HYDTOP5_v16 draait, is niet uit de rapporten af te leiden en blijft handwerk. Het restant wordt niet opgepakt (besloten 2026-08-19): er is geen Mds-nulmetingrapport beschikbaar, en daarmee valt het buiten scope. Beide onderdelen staan of vallen met die bron -- zonder rapport is er niets om aan te verifieren en niets om een dekkinganalyse op te draaien. Komt er alsnog een Mds-rapport, dan is dit punt weer te openen. Dat restant was: (a) verifieren aan een echt Mds-nulmetingrapport of de someValuesFrom-eisen uit de Top-laag (waaronder HoogteLeiding, hasValidity-codering 1t 3t) daadwerkelijk als melding verschijnen, wat de NB-noot bij ATTR-004 raakt; en (b) een hernieuwde dekkinganalyse op Mds, die extra schrapkandidaten zou kunnen opleveren. (c) blijft staan als vaststelling: geen enkele geschrapte check hoeft terug, want Mds eist meer dan MdsPlan en niet minder.

11. Verplaatst naar de issuetracker: [#7 Twee dekkingclaims schrijven eisen aan de verkeerde conformiteitsklasse toe](https://github.com/mcolee/nlriochecker/issues/7).

12. Typering De Wolden (2026-08-16): een voorgestelde poortwachtercheck op te globaal getypeerde objecten is afgewezen als dubbel. De typeringspoort bestaat al (de SHACL-meting benoemt de te globale klassen, de dataset levert de instanties) en de drempel waaronder een dekkingclaim een voorbehoud krijgt is configureerbaar. Meten helpt hier bovendien niet: alle 20.758 putorientaties in De Wolden hangen aan een specifieke subklasse (19.322 Inspectieput, 1.107 Pompunit, 218 Overstortput, 55 Lozingsput, 27 Stuwput, 27 Kruisingsput, 1 Kolk, 1 Drainageput). Er is geen generiek getypeerde put.

13. Verplaatst naar de issuetracker: [#5 _bouw_netwerk overschrijft de kantattributen van parallelle strengen](https://github.com/mcolee/nlriochecker/issues/5).

## Versiehistorie

Versie 0.9, addendum (2026-08-29): EXT-009 toegevoegd -- straat in de bebouwde kom zonder
vrijvervalriolering (W, Compleetheid). Nieuw is niet alleen de check maar ook zijn soort: dit
is de eerste **dekkingsvraag** in het register. EXT-001, EXT-003 en EXT-007 toetsen een
GWSW-object tegen een externe bron; EXT-009 vraagt of er langs een weg riolering *bestaat*, en
neemt daarvoor het NWB-wegvak als toetsobject. Drie gevolgen die het register vastlegt. (1) De
melding hangt aan een sleutel `nwb:wegvak/<WVK_ID>` en niet aan een dataset-URI; haar plek op
de kaart komt uit het middelpunt van het wegvak. (2) De uitslag kent drie toestanden in plaats
van twee: naast bediend (groen) en leeg (rood) is er *niet beoordeeld* (grijs) voor een
overwegend onverharde straat en voor een straat met drukriolering-indicatie. Groen en grijs
dragen geen melding maar wel een vlak in de GeoPackage, en het rapport telt ze -- stilte zou
lezen als "alles gecontroleerd". Zie BO-79. (3) De check leunt op drie externe bronnen die het
register nog niet kende: NWB-wegvakken, TOP10NL `plaats_vlak` (bebouwde kom) en BGT `wegdeel`
(verharding); ontbreekt er een, dan slaat de check over met de gebruikelijke melding. Zie
BO-80. De regel is deterministisch en met opzet geen model: op een validatieset van 485
handmatig beoordeelde straten haalt zij 32 fouten op 478 beoordeelde straten tegen 27 op
479 voor een getraind gradient-boosting-model, met de foutrichting naar valse alarmen. De
ijking van de dragende drempel en de fouttabel staan in BO-81. EXT-008 blijft vervallen en is niet hergebruikt; zie de
tabel Vervallen checks. Zie [#104](https://github.com/mcolee/nlriochecker/issues/104).

Versie 0.9, addendum (2026-08-28): EXT-002 vervallen (zie de tabel Vervallen checks). De check
meldde elke vrijvervalstreng die een BGT-waterdeel echt doorkruist, zonder te vragen of dat een
gebrek is; het handelingsperspectief zit in EXT-003 ("moet dit een zinker zijn?"). Op De Wolden
en Hoogeveen gaven de twee dezelfde uitslag -- 281 van 281 strengen, 319 doorkruisingen (audit
27-08) -- omdat de export geen enkele als zinker geregistreerde streng bevat. EXT-003 blijft
ongewijzigd en is nu de enige watergangmelding; hij telt in zijn toelichting nog steeds elke
doorkruising, ook die van een geregistreerde zinker, en noemt daar voortaan ook dat alleen
BGT-waterdelen gebruikt zijn (de regel die tot nu toe bij EXT-002 stond). Het ID EXT-002 wordt
niet hergebruikt. Uit de checkaudit (PRE-4, `docs/checks-audit-2026-08.md`); het daar
voorgestelde alternatief -- EXT-002 laten voortleven als GeoPackage-datalaag -- is door de
auteur verworpen. Zie [#83](https://github.com/mcolee/nlriochecker/issues/83) en BO-66.

Versie 0.9, addendum (2026-08-28): BTR-002, BTR-005, EXT-005 en EXT-006 vervallen *voor nu*
(zie de tabel Vervallen checks). Alle vier vervallen om dezelfde soort reden: de bron die ze
nodig hebben bestaat niet in deze aanlevering, en er komt er ook geen. BTR-002 vraagt de
inwinningswijze op de BOB's (537 van de 46.880), BTR-005 vraagt inspectiegegevens én een
risicowegingsbron (geen van beide bestaat), en EXT-005/EXT-006 vragen een putdeksellaag -- de
BGT-laag `put` telt 843 objecten waarvan 595 van ProRail, tegenover ruim 23.000 GWSW-putten.
Ze gingen niet naar de tabel Geschrapte checks: de nulmeting dekt ze niet, er kijkt niets meer
naar. "Voor nu" betekent dat het besluit aan de bron hangt en niet aan het begrip; komt de
bron er alsnog, dan keert de check terug onder een nieuw ID, want de ID's BTR-002, BTR-005,
EXT-005 en EXT-006 worden niet hergebruikt. Uit de checkaudit
(`docs/checks-audit-2026-08.md`, BTR- en EXT-sectie). Zie
[#95](https://github.com/mcolee/nlriochecker/issues/95) en BO-62 t/m BO-65.

Versie 0.9, addendum (2026-08-28): ATTR-008 geschrapt (zie de tabel Geschrapte checks). De
drempels van de check stonden op de grenzen van het GWSW-datatype `Dt_LengteLeiding` (1-75 m,
issue #35), en precies dat bereik toetst de nulmetingvorm `LengteLeiding_val` in alle drie de
conformiteitsklassen. Op De Wolden en Hoogeveen viel elk van de 443 ATTR-008-objecten ook
onder die vorm; de vorm is bovendien breder, want zij ziet ook drains, duikers en
aansluitleidingen. Dit is dezelfde dekking waarvoor ATTR-011 eerder geschrapt is, dus ATTR-008
gaat naar de tabel Geschrapte checks (mét sentinel in `dekking.toml`), niet naar Vervallen
checks. ATTR-009 (geometrische lengte tegen administratieve lengte) blijft ongewijzigd: die
toetst iets anders. Het ID ATTR-008 wordt niet hergebruikt. Uit de checkaudit
(`docs/checks-audit-2026-08.md`). Zie
[#90](https://github.com/mcolee/nlriochecker/issues/90) en BO-61.

Versie 0.9, addendum (2026-08-28): ADM-011 vervallen (zie de tabel Vervallen checks). De check
meldde een loze keten zonder aansluiting op actief riool in de afvoerrichting als dode data,
maar dat is de gewenste eindtoestand: buiten gebruik gesteld en netjes losgekoppeld. Het
omgekeerde geval -- actief riool dat wel op een loze keten aansluit -- blijft als ADM-010 (F)
staan, ongewijzigd, en de ketenbouw blijft in de engine. Het ID ADM-011 wordt niet hergebruikt.
Uit de checkaudit (PRE-2, `docs/checks-audit-2026-08.md`). Zie
[#81](https://github.com/mcolee/nlriochecker/issues/81) en BO-60.

Versie 0.9, addendum (2026-08-24): ADM-010 (F) en ADM-011 (W), beide Consistentie, toegevoegd:
loze leidingen, tot ketens gegroepeerd, waar actief riool op aansluit (doorgaand, aanvoer of
afvoer) respectievelijk die aan niets hangen. Melding per loze streng met de keten in
`cluster_id`. Twee ID's en niet één met twee ernsten, want elke check draagt hier precies één
ernst. De klasse komt uit `[klassen] loze_leiding`; ADM-006 blijft ongemoeid (dat meldt op
`Einddatum`/`Begindatum`, dit op de klasse). Zie
[#62](https://github.com/mcolee/nlriochecker/issues/62) en BO-47.

Versie 0.9, addendum (2026-08-24): TOP-022 (F) en TOP-023 (W), beide Consistentie, toegevoegd:
een hulpstuk verbindt minder respectievelijk meer leidingen dan de `functie`-restrictie op
zijn GWSW-klasse voorschrijft; het aantal komt uit de ontologie en niet uit de configuratie,
geteld naar buurknopen en niet naar strengen. Twee ID's en niet één met twee ernsten, want
elke check draagt hier precies één ernst. Tegelijk herstelt de lader de fantoomkoppeling van
de BrutIS-export (`<hulpstuk>_put`) en meldt dat als datasetsignaal; zonder dat herstel zag
de engine bij alle 1054 T-stukken van De Wolden en Hoogeveen nul leidingen. Zie
[#60](https://github.com/mcolee/nlriochecker/issues/60) en BO-46.

Versie 0.9, addendum (2026-08-24): ATTR-018 toegevoegd (F, Compleetheid): een
vrijvervalrioolleiding of put zonder `Begindatum`. Tot nu toe kreeg zo'n object nergens een
melding -- ATTR-003, ATTR-007 en ATTR-015 toetsen alleen een aanwezige datum, de nulmeting
eist het kenmerk niet -- en bleef het op de kaart groen. De GeoPackage-lagen `putten` en
`strengen` dragen sindsdien ook de kolom `begindatum_jaar`. Op De Wolden en Hoogeveen meldt
hij ongeveer 9274 objecten (24% van de populatie), vooral putten. Zie
[#61](https://github.com/mcolee/nlriochecker/issues/61) en BO-45.

Versie 0.9, addendum (2026-08-23): ATTR-017 toegevoegd (W, Plausibiliteit): de wandruwheid
(`WandruwheidBinnenboven`/`-onder`) past niet bij het leidingmateriaal. De aannemelijke band
per materiaal komt uit Leidraad Riolering C2100 tabel B2.1 en staat in `plausibiliteit.toml`;
het GWSW-datatype `Dt_Wandruwheid` is een geheel getal in mm (0-99) en kan de kunststofwaarden
niet uitdrukken, dus de export noteert de waarde in tienden van een mm en de check leidt die
schaal uit de data af (`wandruwheid_schalen`). Polypropyleen en Asbestcement kennen geen
C2100-waarde en blijven ongetoetst. Het aanbevolen ID uit het issue (ATTR-014) was inmiddels
vergeven; ATTR-017 is het eerstvolgende vrije. Op De Wolden en Hoogeveen meldt hij de
PE-leidingen die de betonwaarde dragen. Zie
[#38](https://github.com/mcolee/nlriochecker/issues/38) en BO-39.

Versie 0.9, addendum (2026-08-23): ATTR-016 toegevoegd (F, Consistentie): een ronde put
(`VormPut = Rond`) waarvan breedte en lengte verschillen -- een ronde put heeft een diameter.
De tegenhanger van ATTR-004 voor putten in plaats van leidingen, met dezelfde tolerantie
(`rondheid_tolerantie_mm`); een eigen check-ID en geen uitbreiding van ATTR-004, want
`vergelijk` zet meetmomenten op check-ID naast elkaar en dan mag de betekenis van een ID niet
verschuiven. Het aanbevolen ID uit het issue (ATTR-015) was inmiddels vergeven; ATTR-016 is
het eerstvolgende vrije. Op De Wolden meldt hij 88 ronde putten. Zie
[#39](https://github.com/mcolee/nlriochecker/issues/39).

Versie 0.9, addendum (2026-08-23): ATTR-015 toegevoegd (W, Compleetheid): een systemische
melding wanneer een enkel jaartal een onevenredig deel van de begindatums draagt -- een
signaaldetector voor een vulwaardejaar, met een instelbare drempel
(`begindatum_vulwaarde_aandeel`) en geen norm; op De Wolden en Hoogeveen meldt hij niets.
ATTR-003 en ATTR-007 zijn hernoemd van "aanlegjaar" naar "begindatum" (de GWSW-term is
leidend, ook in de titels en de identifiers); het check-ID en de ernst blijven. ATTR-007
verantwoordt nu in zijn toelichting hoeveel objecten geen begindatum dragen en dus niet
getoetst zijn, en zijn bovengrens is instelbaar (`begindatum_maximum`, standaard het huidige
jaar) zodat een run reproduceerbaar te maken is. Zie
[#21](https://github.com/mcolee/nlriochecker/issues/21).

Versie 0.9, addendum (2026-08-23): geen checks toegevoegd, geschrapt of van ernst of
dimensie veranderd; het contract is ongewijzigd. Redactioneel: de dekkingclaim van ADM-004
is beperkt tot de conformiteitsklasse waar hij aantoonbaar op rust. De put-vormen MateriaalPut
en Maaiveldschematisering (hasAspect exact=1) leveren op De Wolden uitsluitend in Hyd meldingen
op, niet in MdsPlan of MdsProj op hetzelfde RDF-bestand; de dekking van die twee attributen
rust dus op Hyd. De sentineltabel `dekking.toml` en de gegenereerde `docs/dekkingsmatrix.md`
volgen. De tweede claim uit issue #7 (ADM-001, de put-strengkoppeling) is bewust ongemoeid
gelaten: die raakt de onderbouwing van de harde CFK-eis (BO-7) en wacht op akkoord van de
auteur. Zie [#7](https://github.com/mcolee/nlriochecker/issues/7).

Versie 0.9 (2026-08-28): RVZ-003 (drempelbreedte) is opgegaan in RVZ-002 (issue #87,
BO-78). Op De Wolden meldden de twee exact dezelfde 245 putten -- de export draagt geen
enkel drempelobject, dus beide maten ontbreken altijd samen. RVZ-002 zegt nu in één
melding per put welke van {Drempelniveau, Drempelbreedte} ontbreekt. Het ID RVZ-003
vervalt en wordt nooit hergebruikt.

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
