# Beslislog

Beslissingen die tijdens fase 4 genomen zijn zonder tussentijds overleg, met de
overweging en de verworpen alternatieven erbij.

## Blok 0 — fase 3 afmaken (TOP en NET)

### B0-1 De dekkingsmatrix wordt gegenereerd, niet bijgehouden

**Wat.** `docs/dekkingsmatrix.md` wordt geschreven door `scripts/dekkingsmatrix.py`,
dat het checkregister parst (`src/nlriochecker/register.py`), de registry van de
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

**Wat.** `src/nlriochecker/plausibiliteit.toml` bevat materiaal-versus-diameter,
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

## Blok C — externe bronnen

### BC-1 De externe bronnen worden alleen geladen als je erom vraagt

**Wat.** De EXT-checks en HGT-001 t/m HGT-003 draaien alleen met `--bronnen PAD`.
Zonder die optie melden ze "er zijn geen externe bronnen geladen" en toetsen ze
niets; `examined` staat dan op nul.

**Waarom.** De bronnen dekken 43 ha van een gemeente die er duizenden beslaat. Ze
stilzwijgend meeladen zou betekenen dat een gewone run 99% van de objecten als
"buiten studiegebied" afdoet zonder dat de gebruiker daarom gevraagd heeft. Nu is
het een bewuste keuze, en het rapport zegt welke kant het op is.

**Alternatieven.** Altijd laden op basis van `[bronnen]` in de config (verworpen:
maakt elke run trager en het rapport misleidender).

### BC-2 Buiten het studiegebied is geen uitslag, geen bevinding

**Wat.** Elke EXT- en AHN-check filtert eerst op de begrenzingspolygoon uit
`data/gis/cbs_buurt_koekangerveld_studiegebied.gpkg`. Objecten daarbuiten krijgen de
status *buiten studiegebied* en worden geteld in de toelichting.

**Waarom.** Dit is de harde regel uit de opdracht, en hij is ook inhoudelijk juist:
een put zonder BGT-deksel binnen 2 m is buiten Koekangerveld geen gebrek maar een
gevolg van ontbrekende brondata. Op De Wolden gaat het om 17.574 van de 17.603
strengen en 22.323 van de 22.363 putten; zonder deze regel zou de engine
tienduizenden valse bevindingen produceren.

**Let op.** Dit is iets anders dan `--studiegebied`. Die optie bakent de
*rapportage* af nadat alle checks op de volledige dataset gedraaid zijn (fase 2).
De bronbegrenzing hier bakent de *toetsing* van de externe checks af, omdat de bron
zelf niet verder reikt.

### BC-3 De typeringspoort haalt objecten uit de EXT-uitslag, niet alleen uit de vlag

**Wat.** Bij de EXT- en AHN-checks krijgt een te globaal getypeerd object geen
uitslag maar de markering *niet betrouwbaar toetsbaar*, geteld in de toelichting.
Bij de interne checks (TOP, NET, ATTR, HGT-004 e.v., RVZ, ADM, BTR) blijft de
bestaande werkwijze uit fase 3: de bevinding blijft staan met de vlag
`TyperingBetrouwbaar = False`, en het rapport legt uit wat dat betekent.

**Waarom.** De opdracht vraagt de markering "in plaats van een check-uitslag" voor
blok C. Voor de interne checks zou hetzelfde doen betekenen dat een bestaande,
geteste en in het rapport toegelichte uitkomst uit fase 3 verandert, met andere
cijfers als gevolg. Het onderscheid staat in de moduledocstring van `extern.py`.

**Alternatieven.** Overal objecten uit de uitslag halen (verworpen: verandert de
uitkomsten van fase 3 zonder dat daarom gevraagd is; wel een kandidaat voor een
volgende fase, dan als expliciete keuze in de config).

### BC-4 Het hoogteraster wordt nooit geherprojecteerd

**Wat.** Vectorlagen met een correct gedefinieerd afwijkend CRS worden naar
EPSG:28992 omgezet en dat wordt vastgelegd. Een raster met een ander CRS levert een
fout op met het verzoek het in RD aan te leveren.

**Waarom.** Een raster herprojecteren betekent resamplen: de hoogtewaarden
verschuiven en worden geïnterpoleerd. HGT-001 en HGT-002 toetsen op 5 en 25 cm; een
resample-artefact van enkele centimeters zou de uitkomst bepalen. Beter weigeren dan
stilzwijgend nauwkeurigheid verliezen.

### BC-5 Een bron zonder CRS wordt geweigerd

**Wat.** Een laag zonder gedefinieerd coordinaatstelsel levert een fout op in plaats
van de aanname dat het RD is.

**Waarom.** De GWSW-data staat in RD; een bron zonder CRS *lijkt* daar dan op te
passen ook als hij dat niet doet. Een stille misinterpretatie zou alle
afstandstoetsen onzin maken zonder dat iemand het merkt.

### BC-6 EXT-005 en EXT-006 zijn gebouwd maar draaien niet op deze data

**Empirische bevinding.** `BGT.gpkg` bevat de laag `put` wel, maar met nul features.
Dat is de BGT-laag met de putdeksels.

**Wat.** Beide checks zijn volledig geïmplementeerd en getest op miniatuurbronnen,
maar melden op de aangeleverde data *laag niet aanwezig in aangeleverde data* en
worden overgeslagen, met `examined = 0`. Ze draaien zonder wijziging zodra er een
BGT-export met gevulde `put`-laag komt.

**Alternatieven.** Ze als skelet opnemen (verworpen: ze zijn wel implementeerbaar,
alleen de data ontbreekt; dat is een ander soort gat en hoort ook anders te lezen).

### BC-7 EXT-008 gebruikt panden waar het register verblijfsobjecten vraagt

**Wat.** Er zijn 166 BAG-*panden* aangeleverd en geen verblijfsobjecten. De check
gebruikt de pandgeometrie en zet `aantal_verblijfsobjecten` in elke melding.

**Waarom.** Dit is de enige beschikbare benadering, en de opdracht schrijft hem
voor. Een pand met vijf verblijfsobjecten telt daardoor als een; die vertekening
staat in de melding zelf en in de toelichting van de check, zodat hij niet uit het
rapport kan wegvallen.

### BC-8 EXT-006 en EXT-008 melden objecten die niet in de GWSW-dataset staan

**Wat.** `Finding` heeft een veld `location` gekregen: een RD-coordinaat. De
afbakening tot een studiegebied gebruikt dat coordinaat wanneer de bevinding geen
dataset-URI heeft.

**Waarom.** Een BGT-deksel zonder put en een BAG-pand zonder riolering zijn
bevindingen *over* de beheerdata, maar hangen aan een extern object. Zonder eigen
coordinaat zouden ze bij `--studiegebied` als "buiten het gebied" wegvallen — precies
de bevindingen die er dan wel horen te staan.

### BC-9 Met de NWB is niets gebouwd

**Wat.** De 13 NWB-wegvakken zijn ingelezen (rol `nwb_wegvak`) maar voeden geen
enkele check. Het voorstel staat in `docs/nwb-voorstel.md`.

**Waarom.** Geen enkele check uit het register is aan deze bron gekoppeld, en de
opdracht vraagt er expliciet om er niets mee te implementeren. De sterkste kandidaat
is BTR-005 (weging naar wegfunctie), maar die staat als skelet omdat er geen
inspectiegegevens zijn.

### BC-10 De GIS-fixtures worden gegenereerd, niet met de hand gemaakt

**Wat.** `scripts/maak_gis_fixtures.py` schrijft `tests/fixtures/gis/ext` met
dezelfde laagnamen en attribuutnamen als de echte bronnen, in het lokale
assenstelsel van de TTL-fixtures.

**Waarom.** De echte bronnen zijn 24 MB en liggen in Koekangerveld; unit tests
moeten klein en snel zijn. Het raster wordt als eerste geschreven, voor geopandas
geladen is: rasterio en pyogrio brengen elk hun eigen GDAL mee, en die twee in een
proces door elkaar gebruiken bij het schrijven leverde een crash op.

## Onderhoud

### BO-1 Hernoemd naar nlriochecker; de historische documenten zijn meeverhuisd

**Wat.** De package, de distributienaam, het CLI-commando en de cachemap heten
`nlriochecker` in plaats van `gwswpijplijn`. De verslagen, specs en plannen onder
`docs/` zijn meegehernoemd, ook waar ze een gebeurtenis uit het verleden beschrijven.
De oude cachemap (`~/.cache/gwswpijplijn`, 434 MB) is verwijderd, niet gemigreerd.

**Waarom.** De repository, het product en de package heetten drie verschillende dingen.
De documenten zijn meegegaan omdat elk pad erin verwijst naar een bestand dat je moet
kunnen openen; een verslag dat naar `src/gwswpijplijn/uitvoer/` wijst is voor een lezer
van vandaag onbruikbaar. De prijs is dat een zin als die in
`docs/ronde1-gpkg-en-rapport-verslag.md` over commit `2ff975b` nu een naam gebruikt die
op dat moment nog niet bestond. Deze entry is de plek waar dat staat opgeschreven: waar
in de documenten `nlriochecker` staat naast een commit van voor deze wijziging, heette
het toen `gwswpijplijn`.

Migreren van de cache had gekund, maar heeft geen zin: de cachesleutel bevat de broncode
van de lader, dus die was door de hernoeming toch al ongeldig. Bovendien verwijzen de
oude pickles naar het modulepad `gwswpijplijn.dataset` en zouden ze bij het uitpakken
alsnog omvallen. De eerste `toets` na deze wijziging leest de dataset dus opnieuw in
(ruim drie minuten); dat is verwacht gedrag, geen regressie.

**Gevolg voor de uitvoer.** `layer_styles.owner` in de GeoPackage bevat voortaan
`nlriochecker`. GeoPackages van voor en na deze commit verschillen daarmee in dat veld;
QGIS trekt zich er niets van aan.

**Alternatieven.** Alleen de code hernoemen en de documenten met rust laten (verworpen:
levert dode paden op in stukken die juist als naslag dienen). Het commando
`gwswpijplijn` laten heten (verworpen: dan blijven er twee namen in omloop).

### BO-2 Het versienummer staat alleen in pyproject.toml

**Wat.** `version` in `pyproject.toml` is de enige plek waar het nummer staat.
`nlriochecker.__version__` leest het via `importlib.metadata`; het literal in
`__init__.py` is weg. `scripts/uitgave.py` bumpt, toetst, commit en tagt `vX.Y.Z`;
`tests/test_versie.py` bewaakt dat de twee niet uiteenlopen. De semantiek staat in
`docs/versionering.md`.

**Waarom.** Het nummer stond op twee plekken en was daarmee een kwestie van tijd
voordat het uiteen zou lopen — hetzelfde argument als bij de gegenereerde
dekkingsmatrix (B0-1): of één waarheid, of een controle die het afdwingt. Hier kan het
allebei. De tag volgt het nummer en niet andersom, zodat de versie ook leesbaar is
zonder git-geschiedenis, en zodat een export zonder `.git` nog een nummer heeft.

Het uitgavescript draait de bump terug als ruff of pytest omvalt. Zonder dat laat een
mislukte uitgave een opgehoogd nummer achter zonder bijbehorende tag, en dat is precies
de toestand waarin je niet meer weet wat er uitgebracht is.

**Alternatieven.** `hatch-vcs`, waarbij de tag de waarheid is en `pyproject.toml` geen
nummer bevat (verworpen: tussen tags in levert dat `0.2.1.dev4+g1a2b3c`, en zonder
`.git` helemaal geen versie). Het nummer op beide plekken laten met alleen een test
erop (verworpen: bewaakt de drift wel, maar lost hem niet op). Automatisch taggen bij
elke commit (verworpen: niet elke commit is een uitgave).

### BO-3 De licentie is EUPL-1.2

**Wat.** Het werk staat onder de European Union Public Licence v1.2. `LICENSE` bevat de
Engelse tekst zoals GitHub die herkent, `pyproject.toml` draagt de SPDX-expressie
`EUPL-1.2`, en de README draagt de notitie `Licensed under the EUPL` die artikel 1 van de
licentie zelf voorschrijft.

**Het checkregister hoort erbij.** `data/checkregister-gwsw-nulmeting-v0_8.md` is eigen
werk van de auteur, geen overname uit een externe bron. Er rust dus geen vreemd
auteursrecht op en het valt onder dezelfde EUPL-1.2 als de code. Het register verwijst
wel naar de GWSW-ontologie en naar de SHACL-vormen van apps.gwsw.nl, maar dat zijn
verwijzingen, geen overgenomen tekst; de formulering van elke check is van de auteur.
Dat betekent ook dat het register vrij te wijzigen is: geen externe partij hoeft ermee
in te stemmen.

**Waarom.** Doel is dat wie dit verbetert die verbetering ook deelt. De afhankelijkheden
dwingen niets af: alle 28 pakketten zijn permissief (BSD, MIT, Apache, MPL-2.0, PSF), en
de copyleft die er is — GEOS en libquadmath onder LGPL-2.1, libgfortran onder GPL-3 met
de GCC-uitzondering — zit in de wheels van shapely, rasterio en numpy, die wij niet
verspreiden maar als afhankelijkheid declareren. Deze package bevat zelf geen enkel
binair bestand. De keuze was dus vrij.

De EUPL boven de GPL omdat het een publieke-sectorlicentie is, rechtsgeldig in het
Nederlands, en omdat artikel 1 "Distribution or Communication" definieert als mede
`providing access to its essential functionalities` — draaien als dienst telt daarmee als
verspreiding, waar de GPL daarvoor de AGPL nodig zou hebben. De Appendix noemt GPL v2 en
v3, AGPL v3, LGPL, MPL v2, EPL en CeCILL als verenigbare licenties, dus de keuze sluit
niemand buiten.

**Let op bij bundelen.** Zodra er een gebundelde distributie komt (PyInstaller, een
image met de wheels erin) verspreiden we GEOS wel, en gelden de LGPL-2.1-verplichtingen:
licentietekst meeleveren en de bibliotheek vervangbaar houden. Een los `.so` voldoet aan
dat laatste.

**Alternatieven.** MIT (verworpen: een leverancier mag dit dan in een gesloten product
bouwen zonder iets terug te geven, en dat is precies wat we niet willen). GPL-3.0-or-later
(verworpen: dekt draaien-als-dienst niet, en is niet in het Nederlands rechtsgeldig).
AGPL-3.0 (verworpen: dekt hetzelfde als de EUPL hier, maar zonder de publieke-sector- en
taalvoordelen).

### BO-4 Elk uitvoerbestand draagt de package en versie die het schreef

**Wat.** Elk bestand dat deze package oplevert noemt zijn herkomst: `nlriochecker <versie>`.
Markdown krijgt een cursieve regel direct onder de titel, elke CSV de kolom `Gereedschap`
op elke rij, en de GeoPackage het veld `gereedschap` in de tabel `gwsw_run`. De string
komt uit `uitvoer/herkomst.py` en leest het nummer via `__version__`, dus uit de
packagemetadata; hij staat nergens een tweede keer opgeschreven (zie BO-2).

**Waarom.** De checks veranderen tussen versies. Een bevindingenlijst die een half jaar
later opduikt is zonder versienummer niet te herleiden tot de logica die hem opleverde:
of een object toen niet gemeld werd omdat het goed was, of omdat de check nog niet
bestond, is dan niet meer vast te stellen. Dat is precies de vraag die een nulmeting
over tijd moet kunnen beantwoorden. De drie uitvoervormen zeggen het met dezelfde string
uit dezelfde functie, zodat ze niet uit elkaar kunnen lopen — dezelfde reden waarom ze
al uit een enkele meldingenstroom komen.

**Waarom een kolom en geen commentaarregel in de CSV.** Een `#`-regel bovenaan is
compacter, maar breekt elke lezer die hem niet verwacht, en `comment="#"` is hier
bovendien de verkeerde oplossing: de kolommen `ObjectURI` en `Object2URI` bevatten
GWSW-URI's van de vorm `http://sparql.gwsw.nl/dewolden#knp3437`, en pandas kapt met die
optie elke regel af vanaf het eerste `#`. Dat zou stilzwijgend alle URI's halveren. Een
kolom kost herhaling, maar houdt het archief leesbaar voor pandas, Excel en QGIS zonder
extra opties, zoals `bevindingen.csv` al doet met `RunDatum` en `Dataset`. De vier andere
CSV's droegen nog geen runmetadata; voor hen is dit de eerste zo'n kolom.

**De grens.** Een CSV zonder rijen krijgt wel de kolomkop maar geen enkele waarde, en
noemt de versie dus niet. Dat is inherent aan een kolom en niet met een kolom te
repareren. Het raakt alleen een toets die niets vond; het Markdown-rapport ernaast draagt
de herkomst dan wel, want die staat in de kop en niet in de rijen.

**Alternatieven.** Een los `herkomst.json` in de uitvoermap (verworpen: raakt los van de
CSV zodra iemand alleen die CSV doorstuurt, en dan is de herkomst weg). De versie alleen
in de GeoPackage (verworpen: dan draagt juist het bestand dat het vaakst wordt
doorgestuurd, de CSV, hem niet).
