# Beslislog

Beslissingen die tijdens fase 4 genomen zijn zonder tussentijds overleg, met de
overweging en de verworpen alternatieven erbij.

## Blok 0 — fase 3 afmaken (TOP en NET)

### B0-1 De dekkingsmatrix wordt gegenereerd, niet bijgehouden

**Wat.** `docs/dekkingsmatrix.md` wordt geschreven door `scripts/dekkingsmatrix.py`,
dat het checkregister parst (`src/gwswpijplijn/register.py`), de registry van de
engine uitleest en de testsuite op check-ID's doorzoekt.

**Waarom.** Een met de hand bijgehouden matrix is na twee wijzigingen onbetrouwbaar,
en juist deze matrix moet vertellen wat er *niet* gebouwd is. Genereren maakt dat
onmogelijk om per ongeluk te laten verlopen.

**Alternatieven.** Handmatige tabel (verworpen: gaat drijven). Een pytest die de
matrix valideert (verworpen: dan staat de waarheid nog steeds twee keer opgeschreven).

### B0-2 Kenmerken worden bij het inlezen als aspecten meegenomen

**Wat.** `Node` en `Conduit` dragen nu een `aspects`-tupel met alle GWSW-kenmerken
(waarde of domeinlijstverwijzing) plus hun inwinningsmetagegevens. Maaiveldhoogte,
putdekselniveau en de BOB's krijgen een eigen veld omdat ze via een omweg in de
graaf hangen.

**Waarom.** ATTR, HGT, RVZ en BTR hebben alle materiaal, diameter, vorm, aanlegjaar
en hoogten nodig. Per check opnieuw door de rdflib-graaf lopen kost op De Wolden
minuten; een keer bij het inlezen kost seconden.

**Alternatieven.** Lui inladen per check met een cache (verworpen: dezelfde kosten,
meer complexiteit). Alleen expliciete velden zonder generiek aspect-tupel
(verworpen: elke nieuwe check zou dan de lader moeten wijzigen).

### B0-3 Er is geen `Putbodemniveau` in het GWSW; de putbodem wordt afgeleid

**Wat.** `Node.bodem` = bovenkantniveau min `HoogtePut`. Het bovenkantniveau is het
`Putdekselniveau`, en bij ontbreken daarvan de `Maaiveldhoogte`; welke van de twee
gebruikt is staat in de bevinding.

**Waarom.** De totaal-ontologie kent geen kenmerk voor het putbodemniveau. HGT-004,
HGT-012, HGT-015 en HGT-016 vragen er wel om. Zonder `HoogtePut` is de bodem niet
te bepalen en mag er niet op getoetst worden; die checks melden dat expliciet.

**Alternatieven.** De laagste aansluitende BOB als bodem nemen (verworpen: dan
toetst HGT-015 zichzelf). De checks schrappen (verworpen: ze staan in het register).

### B0-4 TOP-007 en TOP-017 overlappen bewust op zelfkruising

**Wat.** TOP-007 (F) meldt nul-lengte, te weinig verschillende punten, niet-eindige
coordinaten *en* zelfkruising. TOP-017 (W) meldt niet-simpele geometrie, waaronder
diezelfde zelfkruising. Beide checks zeggen dat in hun toelichting.

**Waarom.** Het register noemt "zelfkruisende" letterlijk onder TOP-007 (F) en
`ST_IsSimple` onder TOP-017 (W). `ST_IsSimple` *is* het begrip zelfkruising; de twee
zijn in de praktijk niet te scheiden. Een van beide half uitvoeren zou een ernst uit
het register laten vallen.

**Alternatieven.** Zelfkruising alleen onder TOP-017 (verworpen: verliest een F).
Alleen onder TOP-007 (verworpen: verliest TOP-017 vrijwel volledig).

### B0-5 TOP-009 toetst het RD-bereik, niet het beheergebied

**Wat.** De check toetst ontbrekende coordinaten en het RD-bereik (configureerbaar).
Het beheergebied blijft ongetoetst; de check meldt dat in haar toelichting.

**Waarom.** Er is geen beheergebiedpolygoon aangeleverd. Het studiegebied
Koekangerveld is er geen vervanging voor: dat beslaat een kern binnen de gemeente,
terwijl het beheergebied de hele gemeente is. Objecten daarbuiten als fout melden
zou de dataset onterecht afkeuren.

**Alternatieven.** Het studiegebied als beheergebied gebruiken (verworpen: levert
duizenden valse fouten op). De check als skelet opnemen (verworpen: het RD-deel is
wel toetsbaar en vindt echte fouten).

### B0-6 TOP-019 draait alleen op expliciet geconfigureerde functieloze knopen

**Wat.** `klassen.functieloze_knoop` bepaalt welke knoopklassen als functieloos
gelden; standaard `LozePut`, `BlindePut`, `Ontstoppingsstuk`, `Verbindingsstuk`.
Zonder lijst draait de check niet en zegt dat.

**Waarom.** In een rioolstelsel zit op vrijwel elke knik een put, en een put *is*
een functie (toegang, onderhoud). Elke doorgaande put met twee gelijke strengen als
pseudo-knoop melden zou op De Wolden tienduizenden bevindingen opleveren die geen
gebrek zijn — precies de modelleerfout waar CLAUDE.md voor waarschuwt.

**Alternatieven.** Alle knopen met graad twee melden (verworpen: onbruikbaar aantal).
De check schrappen (verworpen: staat in het register).

### B0-7 NET-005 eist buren aan beide zijden

**Wat.** Een streng wordt pas gemeld als er aan de beginput *en* aan de eindput een
andere streng hangt, en geen van die buren hetzelfde stelseltype heeft.

**Waarom.** Het register zegt "wijkt af van boven- **en** benedenstroomse buren".
Een streng aan het uiteinde van een stelsel heeft maar aan een kant een buur; die is
niet afwijkend maar de laatste van zijn soort. Zonder deze eis meldt de check bij
elke legitieme stelselovergang drie strengen in plaats van nul.

**Alternatieven.** Elke streng melden die van al haar buren verschilt (verworpen:
meldt bij elke overgang beide zijden mee).

### B0-8 De TOP-fixtures gebruiken een lokaal assenstelsel; de test verzet het RD-bereik

**Wat.** De TTL-fixtures spelen zich af rond (1000, 2000). Voor TOP-009 verzet de
test `rd_y_min` naar 0; de standaardwaarden blijven het echte RD-bereik.

**Waarom.** De bestaande fixtures uit fase 3 gebruiken dat leesbare assenstelsel al.
Ze allemaal naar echte RD-coordinaten verzetten zou de fixtures moeilijker leesbaar
maken zonder iets aan de toetsing toe te voegen. Dat het bereik verzet kan worden is
precies waar de configureerbaarheid voor is; een aparte test legt vast dat de
standaardwaarden wel degelijk het echte RD-bereik afdwingen.

## Blok A — resterende interne checks

### BA-1 De plausibiliteitstabellen staan in een eigen configbestand

**Wat.** `src/gwswpijplijn/plausibiliteit.toml` bevat materiaal-versus-diameter,
materiaal-versus-aanlegjaar, materiaal-versus-profielvorm, leidingmateriaal-versus-
putmateriaal, vorm-versus-afmetingen en de lijst met handelsmaten. Te laden met
`--plausibiliteit`.

**Waarom.** Het zijn vakinhoudelijke aannames, geen GWSW-regels: ze zeggen wat je in
een Nederlandse vrijvervalriolering *verwacht*. Ze verschillen per gemeente en horen
per project herzien te worden. Een materiaal dat niet in de tabel staat wordt niet
getoetst, en de check meldt hoeveel strengen daardoor buiten beeld bleven.

**Alternatieven.** In `checks.toml` (verworpen: dat bestand gaat over klassen en
drempels en zou onleesbaar worden). Hardcoded in Python (verworpen: expliciet
verboden door de opdracht en door CLAUDE.md).

### BA-2 ATTR-005 kijkt naar profielmaten, niet naar alle waarden

**Wat.** De check meldt een breedte- of hoogtemaat die zelf geen handelsmaat is maar
maal tien wel, en die onder de verdenkingsdrempel (standaard 100 mm) ligt.

**Waarom.** "Eenhedenfouten binnen bereik" is zonder aanknopingspunt niet
detecteerbaar: een BOB in centimeters is van een BOB in meters niet te onderscheiden
zonder een tweede bron. Bij profielmaten is er wel een aanknopingspunt, namelijk de
lijst met handelsmaten. De check zegt in haar toelichting welk deel zij niet dekt.

**Alternatieven.** Ook lengten en hoogten meenemen (verworpen: geen betrouwbaar
signaal; ATTR-009 en de HGT-categorie dekken die kant met een tweede bron).

### BA-3 ATTR-006 vergelijkt met de grootste putmaat

**Wat.** Een streng wordt gemeld als haar grootste profielmaat groter is dan de
grootste binnenmaat van de put.

**Waarom.** Een buis kan een rechthoekige put langs de lange zijde binnenkomen; met
de kleinste putmaat vergelijken zou elke rechthoekige put met een grote streng
afkeuren. De grootste maat is de mildste vergelijking en houdt alleen de gevallen
over waarin de buis in geen enkele richting past.

**Alternatieven.** De kleinste putmaat (verworpen: te veel valse meldingen). De
gemiddelde maat (verworpen: heeft geen fysieke betekenis).

### BA-4 De putbodem, de puthoogte en HGT-012

**Wat.** HGT-012 (putdiepte) toetst `HoogtePut` rechtstreeks, niet "deksel min bodem".

**Waarom.** `Node.bodem` wordt zelf afgeleid als bovenkant min `HoogtePut` (zie B0-3).
Deksel min bodem zou daardoor per definitie weer `HoogtePut` opleveren: een
cirkelredenering die altijd binnen de marge valt. De check meldt in haar toelichting
hoeveel putten geen puthoogte hebben.

**Alternatieven.** De laagste aansluitende BOB als bodem nemen (verworpen: dan toetst
HGT-012 hetzelfde als HGT-015).

### BA-5 HGT-007 telt alleen verval naar beneden

**Wat.** HGT-007 (te weinig verhang) meldt alleen strengen met een verval tussen nul
en de drempel. Loopt de bodem omhoog, dan zwijgt de check.

**Waarom.** Tegenverhang is een ander gebrek met een eigen ID (HGT-005 en HGT-006) en
een eigen ernst. Zonder deze afbakening zou elke streng met tegenverhang in drie
checks tegelijk opduiken en zou het totaal een verkeerd beeld geven.

### BA-6 De HGT-fixtures raken meerdere checks tegelijk

**Wat.** Elke HGT-fixture bevat precies een ingebouwd defect, maar zo'n defect laat
meestal meerdere checks aanslaan: een BOB boven het deksel betekent per definitie ook
te weinig gronddekking (HGT-013) en een buiskruin boven maaiveld (HGT-018).

**Waarom.** Het hoogtemodel is een samenhangend geheel; deksel, maaiveld, puthoogte,
bodem, BOB en profielhoogte zitten in elkaars formules. Een fixture bouwen die maar
een check raakt zou fysiek onmogelijke combinaties vragen. De tests toetsen daarom per
check-ID of *die* check het defect vindt, en er is per categorie een schone fixture
waarop geen enkele check iets mag melden.

### BA-7 RVZ-001 en RVZ-011 zijn wel gebouwd

**Wat.** De opdracht noemt voor blok A alleen RVZ-004 t/m RVZ-010; RVZ-001 en RVZ-011
zijn ook gebouwd.

**Waarom.** Beide staan in het register, zijn niet geschrapt en zijn met de aanwezige
gegevens implementeerbaar. Ze overslaan zou twee gaten in de dekkingsmatrix laten die
niet uit de data of de architectuur volgen maar uit een opsomming.

### BA-8 Bergbezinkriolen vallen buiten RVZ-007 t/m RVZ-009

**Wat.** `klassen.bergbezinkvoorziening` bevat alleen bouwwerkklassen. `Bergbezinkleiding`
en `Bergingsleiding` staan apart in `klassen.bergbezinkleiding` en worden geteld en
gemeld, maar niet getoetst.

**Waarom.** Die twee klassen zijn `VrijvervalRioolleiding`: ze komen in `conduits`
terecht en niet in `nodes`. RVZ-007 t/m RVZ-009 redeneren over de voorziening als
knoop in het netwerk (aanvoer, lediging, nooduitlaat), en dat werkt niet op een kant.
Ze stilzwijgend in de knopenrol laten staan zou betekenen dat de toelichting "deze
dataset bevat geen bergbezinkvoorziening" zegt terwijl er wel een bergbezinkriool is.

### BA-9 De inwinningswijze zit in De Wolden op de geometrie, niet op de hoogten

**Empirische bevinding.** De De Wolden-export bevat 25.546 keer `WijzeVanInwinning`
(waarden AHN2, Inmeting, Revisie, Schatting, Plan_Ontwerp, NietAchterhaald,
Afgeleid, Luchtfoto, Inspectie), maar telkens gekoppeld aan de *puntgeometrie* van de
put of het maaiveld — niet aan de BOB's, het dekselniveau of het drempelniveau die het
register bij BTR-001 en BTR-002 noemt. Er is geen enkele `DatumInwinning`.

**Wat.** BTR-001 t/m BTR-005 blijven skelet, conform de opdracht. De reden bij elk
skelet noemt deze bevinding, zodat duidelijk is dat BTR-002 wel bouwbaar wordt zodra
er een export met inwinning op de BOB's is.

### BA-10 Empirische bevinding: hoe overstorten in de De Wolden-export staan

**Bevinding.** Getoetst op de volledige export (`rdf:type`-telling over 112 MB TTL):
- `Overstortput` 218 keer, `Stuwput` 27 keer — overstorten zijn dus *putten met een
  eigen klasse*, geen kunstwerken en geen aparte objecten;
- `Overstortleiding` 68 keer — de leiding van de overstort naar buiten;
- `Overstortdrempel` **nul** keer, en dus ook geen `Drempelniveau` en geen
  `Drempelbreedte`; `Bergbezinkbassin` **nul** keer; `Ledigingsvoorziening` **nul** keer.

Het GWSW-voorbeeldbestand (Juinen) kent die objecten wel: daar hangt een
`Overstortdrempel` met `Drempelniveau` en `Drempelbreedte` via `hasPart` aan een
`Overstortput`, met begin- en eindpunt op twee compartimenten.

**Keuze.** De RVZ-module leest beide vormen. De overstort wordt herkend aan de
putklasse (`klassen.overstortput`) en de overstortleiding aan de leidingklasse
(`klassen.overstortleiding`); drempels worden gezocht als `hasPart`-onderdelen van het
type `Overstortdrempel`. Waar de drempelgegevens ontbreken meldt de check dat
expliciet in plaats van nul bevindingen te tonen. Dit bevestigt het openstaande punt
uit CLAUDE.md: RVZ-002 en RVZ-003 zijn geschrapt omdat de nulmeting ze zou dekken,
maar er is in deze dataset geen enkele SHACL-vorm en geen enkel object dat ze raakt.

**Gevolg voor ADM-007.** 181 van de 273 overstort- en lozingsputten hebben geen
overstortleiding of -drempel. Dat is geen 181 losse gebreken maar een systematisch
registratiepatroon: er zijn 218 overstortputten tegenover 68 overstortleidingen.
