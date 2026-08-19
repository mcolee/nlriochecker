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
Die laatste vaststelling heeft de schrapping later ongedaan gemaakt: beide checks zijn
alsnog gebouwd (zie BO-26). De zin hierboven beschrijft de toestand van voor dat besluit.

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

### BO-5 De poort staat in CI, en mypy hoort erbij

**Wat.** `.github/workflows/toets.yml` draait `ruff check`, `ruff format --check`, `mypy`
en `pytest` op elke push naar `main` of `dev` en op elke pull request.
`scripts/uitgave.py` draait dezelfde vier bij een uitgave. Mypy staat schoon op
`src/nlriochecker`, met `ignore_missing_imports` omdat rdflib, shapely, geopandas en
rasterio geen bruikbare stubs leveren.

**Waarom.** De poort bestond al, maar draaide alleen lokaal en alleen bij een uitgave.
Alles ertussen leunde erop dat iemand eraan dacht. En de typehints waren nooit
gecontroleerd: mypy vond er bij de eerste run 55 fouten in dertien bestanden, in code die
volgens `CLAUDE.md` overal hints hoort te hebben.

Drieentwintig van die 55 kwamen uit een enkele oorzaak: `CheckContext.cached()` gaf
`object` terug, waardoor elke check die er een structuur uithaalde zijn type kwijtraakte.
Die functie is generiek gemaakt; de rest bleek versmallingsgrenzen (een geometrie die
`| None` is terwijl de bouwer er al op gefilterd heeft) en een handvol `set[str | None]`
die met `.discard(None)` werd opgeschoond in plaats van meteen goed opgebouwd. Geen van de
55 was een echt defect, maar dat was vooraf niet vast te stellen -- en dat is het punt.

**De ondergrens op geslaagde tests.** `data/` staat buiten versiebeheer: de OroX-export en
de GIS-bronnen beslaan gigabytes. Een schone kloon slaat de tests die erop leunen dus over
en leest groen. Gemeten bij het inrichten: met de volledige `data/` en PyQGIS erbij slagen
er lokaal 711; zonder `data/` zakt dat naar 490 met drie fouten. De eerste groene CI-run gaf
673 geslaagd en 33 overgeslagen -- die runner mist zowel de niet-getrackte data als PyQGIS.
CI zet daarom `NLRIOCHECKER_MIN_GESLAAGD=650`; `tests/conftest.py` laat de run vallen als er
minder slagen.

Wees precies over wat die grens doet: hij merkt een ontbrekende `data/` *niet* op, want 673
ligt er ruim boven -- dat is de normale toestand in CI. Hij vangt het wegvallen van meer dan
die bekende overslagen, bijvoorbeeld een fixturemap die niet meekomt of een importfout die
een heel testbestand laat overslaan. Zonder grens zou zoiets als "alles groen" lezen.

Deze aantallen verouderen bij elke nieuwe test. Ze staan hier als ijkpunt, niet als
contract; de grens hoort onder het CI-aantal te blijven en mag meegroeien.

**Wat er niet onder valt.** Mypy kijkt naar `src/nlriochecker`, niet naar `scripts/` en
`tests/`; daar staan samen nog negentien meldingen. En `disallow_untyped_defs` staat uit:
met die vlag erbij zijn het 67 meldingen in vijftien bestanden, met `cli.py` (16) en
`checks/extern.py` (9) voorop, niet de twee bestanden die je zou verwachten. Het annoteren
van die parameters trekt hun lichamen alsnog de controle in; dat is een eigen ronde waard.
Wel al schoon: `mypy --check-untyped-defs`, dus de nul is sterker dan alleen de
geannoteerde functies.

**Alternatieven.** Mypy meteen in strikte modus (verworpen: zie hierboven; een poort die je
op dag een op 67 meldingen zet, wordt een poort die je uitzet). De data in de repository zetten met git-lfs (verworpen: gigabytes, en
de brondata is niet van ons om te verspreiden). CI zonder ondergrens (verworpen: dat is
de gevaarlijkste variant, want hij geeft vertrouwen dat hij niet verdient).

### BO-6 Twee beveiligingsmeldingen die blijven staan

**Wat.** Bandit meldt twaalf punten op `src/`. Ze blijven alle twaalf staan, met deze
onderbouwing; `pip-audit` is schoon.

**B608, negen keer: SQL uit een f-string.** In `studiegebied.py` en `uitvoer/gpkg.py`
worden tabel- en kolomnamen geinterpoleerd, want SQLite laat identifiers niet als
parameter toe. Alle *waarden* gaan wel als parameter mee, en de identifiers gaan door
`_escape()`, dat aanhalingstekens verdubbelt -- de manier die SQLite daarvoor kent. De
enige identifier die van buiten komt is de laagnaam uit `--studiegebied-laag`; de rest
zijn constanten uit onze eigen kolomdefinities.

**B301/B403, drie keer: pickle.** De datasetcache in `~/.cache/nlriochecker` wordt door
dit gereedschap zelf geschreven en teruggelezen. Wie daar een vijandig bestand kan
neerzetten, kan ook gewoon code in de venv zetten; de cache voegt geen aanvalsvlak toe dat
er niet al was. Een rdflib-`Graph` is bovendien niet zonder verlies in een veiliger
formaat te bewaren, en dat was de hele reden voor de cache. De sleutel bevat de broncode
van de lader, dus een cache van een andere versie wordt nooit gelezen.

**Waarom niet onderdrukken.** Geen `# nosec` en geen bandit-configuratie: de meldingen
zijn juist, alleen niet van toepassing. Ze wegdrukken zou de volgende scan schoon laten
lijken zonder dat iemand de afweging nog ziet. Bandit draait niet in CI; wie hem draait,
leest dit.


### BO-7 De CFK-eis is versoepeld, maar elke afwijking is luid

**Wat.** Het checkregister v0.8 eist dat de dataset aan alle conformiteitsklassen
getoetst is: Hyd, MdsPlan en MdsProj. `--cfk` laat een run op een deelverzameling toe.

**Waarom.** De harde eis is goed voor een oplevering, maar hij blokkeert werk dat er
onderweg wel is: een tussentijdse meting waarbij nog niet alle drie de rapporten
getrokken zijn, of een gerichte controle op een enkele klasse. Zonder uitweg gaan
mensen om de pijplijn heen werken, en dan is er geen markering meer.

**De voorwaarde.** De versoepeling geldt alleen onder twee eisen, en die zijn niet
optioneel gemaakt:

1. De afwijking is **expliciet**. Zonder `--cfk` verandert er niets: alle drie vereist,
   en een ontbrekend rapport faalt. Er is geen configuratie die de standaard verzet.
2. De afwijking is **zichtbaar in elke uitvoervorm die hem kan dragen**. Een
   waarschuwingsregel boven elk Markdown-rapport, `cfk_set` en `volledig` in `gwsw_run`
   en in de JSON-envelop. De tekst komt uit `Meetbereik.markering()` en niet uit een
   schrijver, zodat geen twee uitvoervormen iets anders over dezelfde run kunnen zeggen;
   `tests/test_uitvoer_herkomst.py` legt die overeenstemming vast.

   **De CSV draagt hem bewust niet**, en dat is een erkend gat. De opdracht schrijft
   voor: geen extra kolom per rij, want de CFK-set hoort bij de run en niet bij de
   melding. Gevolg: `bevindingen.csv` uit een volle run en uit een `--cfk Hyd`-run
   verschillen alleen in `TyperingBetrouwbaar`. Wie die twee in Excel naast elkaar legt
   -- precies de doelgroep van dat bestand -- kan "de typering is verbeterd" lezen
   terwijl er alleen minder gemeten is. `dekking.csv` en `geaggregeerde_meldingen.csv`
   ontsnappen hieraan omdat zij een `CFK`-kolom per rij dragen. Een kolom `CfkSet` plus
   `Volledig` in `bevindingen.csv` zou het dichten; dat is een wijziging van het
   uitvoerformaat en daarmee een aparte beslissing.

Daarbij hoort dat een rapport voor een niet-gekozen klasse een fout is en geen stille
overslag: wie op Hyd toetst en per ongeluk alle drie de bestanden meegeeft, moet dat
horen. Anders meldt de markering "MdsProj ontbreekt" terwijl het bestand er lag.

**Een derde toestand.** `toets` kan zonder `--shacl` draaien; dan is er geen meting.
Dat is niet hetzelfde als een deelset, want een deelset beweert dat er iets gemeten is.
`Meetbereik` kent daarom drie toestanden en de markering drie teksten. Dat volgt de
werkafspraak dat wat een check niet bekeken heeft in het rapport hoort: stilte leest als
"alles gecontroleerd".

**Geen forceer-vlag bij `vergelijk`.** Twee meetmomenten met ongelijke CFK-sets worden
geweigerd. Een daling in het aantal meldingen die uit een kleinere getoetste set komt is
geen verbetering, en een trendrapport dat hem als vooruitgang toont is onjuist, niet
onzeker. Wie beide momenten wil vergelijken, toetst ze op dezelfde set.

### BO-8 Het JSON-schema is een contract met een eigen versienummer

**Wat.** `toets` schrijft `bevindingen.json`: de volledige meldingenstroom met een
envelop. `schema_versie` begint op `"1.0"` en staat los van het versienummer van de
package. Het contract staat in `docs/json-schema.md`.

**Waarom een eigen nummer.** De afnemer is een nog te bouwen package die er
Kikker/BrutIS-mutaties uit afleidt. Die pint op het formaat, niet op onze checks. Elke
patchuitgave van `nlriochecker` verandert bevindingen; het formaat hoeft daar niet in mee
te gaan. Zouden ze samenvallen, dan zegt een versiebump niets meer over of de afnemer
werk heeft.

**De regel.** Nieuwe optionele velden mogen binnen een hoofdversie. Een verwijderd of
hernoemd veld, een gewijzigd type, een gewijzigde betekenis of een andere structuur
verhoogt het hoofdnummer. Een afnemer op `1.x` mag onbekende velden negeren en mag niet
aannemen dat `2.0` leesbaar blijft.

**Fase B is buiten scope.** Het veld `voorstel` (veld, huidige waarde, voorgestelde
waarde per melding) is gereserveerd en gedocumenteerd, maar wordt **niet geschreven** --
ook niet als `null`. Het importformaat van Kikker en BrutIS is nog niet gespecificeerd,
en een altijd-lege sleutel zou een belofte zijn die het schema nog niet waarmaakt.
Toevoegen kan later binnen 1.x.

**Twee drifttests.** `docs/json-schema.md` is een tweede plek waar de veldnamen staan, en
een afnemer programmeert daartegen. Twee tests houden het document aan de code vast: elk
veld van `Melding` moet erin beschreven zijn, en het voorbeeld moet de geschreven
`SCHEMA_VERSIE` noemen. Zonder die tests wordt het contract stil onvolledig zodra
`Melding` een veld krijgt -- en dat valt niemand op, want het bestand zelf klopt wel.

### BO-9 `analyseer` schrijft geen JSON

**Wat.** De opdracht noemde `toets` én `analyseer` als schrijvers van de JSON-export.
Alleen `toets` doet het.

**Waarom.** Diezelfde opdracht eist dat de inhoud uitsluitend uit de meldingenstroom
komt en dat er geen pad bestaat waarlangs een schrijver zelf een `Finding` interpreteert.
Op `analyseer` zijn die twee eisen niet tegelijk waar te maken: dat commando analyseert
SHACL-nulmetingrapporten en kent geen `CheckRun`, dus geen `Melding`.

**De afgewogen alternatieven.** Een tweede schema voor `analyseer` zou een tweede
contract met een eigen versielijn zijn, terwijl het doel juist één stabiel contract is.
Dezelfde envelop met een lege meldingenlijst zou "nul meldingen" zeggen terwijl de
nulmeting er duizenden telt -- een bestand dat aantoonbaar het verkeerde beweert.

**Gevolg.** `--geen-json` staat alleen op `toets`. Wie de SHACL-analyse machineleesbaar
wil, heeft `geaggregeerde_meldingen.csv`.

### BO-10 `[nulmeting] vereiste_cfk` is verplicht geworden

**Wat.** `NulmetingOptions.vereiste_cfk` had een pydantic-default
`["Hyd", "MdsPlan", "MdsProj"]`, en `CheckConfig.nulmeting` een `default_factory`. Beide
zijn verwijderd; een projectconfig zonder de sectie faalt nu met een `ConfigError`.

**Waarom.** De domeinregel is dat de lijst in `checks.toml` staat en niet in de code. Die
default schreef hem een tweede keer op, en een config die de sectie miste viel er
onzichtbaar op terug. Sinds `--cfk` weegt dat zwaarder: diezelfde lijst bepaalt nu ook
welke klassen die optie accepteert. Een project waarvan de GWSW-server andere klassen
aanbiedt, zou met een onvolledige config stilzwijgend de verkeerde geaccepteerd zien.

**Waarom dit veilig kon.** Niemand construeert `CheckConfig` of `NulmetingOptions`
rechtstreeks; alles loopt via `load_check_config()`. `klassen: ClassRoots` was al
verplicht zonder default, dus dit volgt een bestaand patroon. Vijf minimale testconfigs
die een geslaagde load verwachten dragen de sectie nu; de vier ongeldige-configgevallen
hadden hem niet nodig, want pydantic rapporteert alle fouten en die tests zoeken een
substring.

### BO-11 Een object op een gebiedsgrens telt in elk rakend gebied mee

**Wat.** Rapporteert `toets` per studiegebied-feature, dan wordt er tussen gebieden niet
ontdubbeld. `StudyArea.bevat` gebruikt `intersects`, dus een streng die de grens tussen
twee buurten kruist verschijnt in de uitvoer van allebei. De totaalsynthese telt de
unieke meldingen en zegt er expliciet bij hoeveel er in meer dan een gebied voorkomen.

**Waarom.** Elk gebied moet zijn eigen volledige werkelijkheid tonen: wie het rapport van
een buurt leest, ziet alle bevindingen die die buurt raken, ook die op de rand. Het
alternatief -- elk object aan precies een gebied toewijzen -- vraagt een regel (het gebied
waarin het zwaartepunt ligt? het eerste gebied in het bestand?) die op de grens altijd
willekeurig is, en dan mist een van de twee buurten een bevinding die er wel degelijk
ligt. Dat is de duurdere fout.

**Wat dat vraagt.** `melding_id` mag het gebied niet bevatten, anders is hetzelfde defect
in twee buurten niet als een defect te herkennen en telt de synthese het dubbel.
`uitvoer/identiteit.py` bouwt de ID uit check, objecten en detailsleutels; het gebied zit
er niet in en `tests/test_uitvoer_identiteit.py` legt dat vast op de handtekening, zodat
het er niet ongemerkt bij komt.

**Gevolg dat je moet kennen.** De som van de meldingen per gebied is hoger dan het aantal
unieke meldingen. `totaal/synthese.md` noemt beide getallen en het verschil;
`totaal/bevindingen.csv` en `totaal/bevindingen.json` bevatten de unieke meldingen,
waarbij een grensmelding het gebied van zijn eerste voorkomen bij oplopende gebiedsnaam
draagt.

### BO-12 Hybride uitvoeringsmodel: een keer laden, per gebied toetsen

**Wat.** `toetsloop.toets_gebieden` laadt niets zelf. De dataset en de ontologie worden
een keer geladen, daarna bouwt de loop per gebied een eigen analyseset met de bestaande
`bouw_analyseset`. Twee structuren worden over de gebieden heen gedeeld: de ruimtelijke
index (`shapely.STRtree`) over alle objectgeometrieen, en de samenhangende
vrijvervalcomponenten van het volledige net (`GedeeldeIndex`). Daarnaast wordt de
volledige-export-`CheckContext` een keer gebouwd en aan elke gebiedscontext meegegeven.

**Waarom.** Het laden van de De Wolden-export kost ruim drie minuten en circa 3 GB; de
referentiecasus telt 80+ buurten. Tachtig keer laden is uitgesloten, en tachtig keer de
componentgraaf en de datakarakteristiek van de volledige export herrekenen ook.

**De harde eis eronder.** De meldingen per gebied moeten gelijk zijn aan die van een
losse run met alleen dat gebied. Elke optimalisatie is daarop getoetst:

- De STRtree levert alleen *kandidaten* op omhullende; het oordeel blijft `area.bevat`.
  Een omhullende-query is per constructie een superset van de snijdende geometrieen, dus
  de uitkomst kan niet verschillen -- ook niet bij de ongeldige geometrieen die deze
  datasets bevatten (TOP-016), waar een voorbereid predicaat anders zou kunnen beslissen
  dan `intersects` zelf.
- De componentstructuur werd al over de volledige dataset berekend; alleen de vraag welke
  component de kern raakt hangt van het gebied af, en die blijft per gebied.
- De gedeelde volledige-export-context hangt af van de volledige dataset, de config en de
  onbetrouwbare objecten. Alle drie zijn gebiedsonafhankelijk. Wat aan de uitgedunde
  dataset van een gebied hangt -- de topologie-index, de netwerkgraaf -- wordt nooit
  gedeeld; elke gebiedscontext krijgt een lege cache.

`tests/test_toetsloop.py` toetst de equivalentie per gebied, en
`tests/test_afbakening.py` de gedeelde index tegen de directe route.

### BO-13 De CRS-heuristiek voor GeoJSON, en waarom de fixtures hun stelsel noemen

**Wat.** Een GeoPackage draagt zijn `srs_id` en wordt daarop getoetst. GeoJSON kent
formeel alleen WGS84 (RFC 7946), dus daar geldt: een legacy `crs`-member die EPSG:28992
noemt is afdoende, en anders moeten alle coordinaten binnen de RD-grenzen vallen. Die
grenzen komen uit `[drempels] rd_x_min` en verder in de projectconfiguratie -- dezelfde
waarden die TOP-009 gebruikt, geen tweede plek. Wie `load_studiegebieden` zonder grenzen
aanroept, krijgt de heuristiek niet: zonder grenzen is er geen oordeel te vellen, en een
verzonnen grens is erger dan geen.

**Waarom een harde fout.** Een studiegebiedbestand in WGS84 snijdt niets uit de
RD-dataset. Zonder deze toets levert dat geen foutmelding maar een leeg gebied, en dat
leest als "geen bevindingen".

**De fixtures.** Elke GeoJSON-fixture in deze repository ligt op lokale coordinaten rond
(1000, 2000) -- ver buiten de RD-grenzen, net als de TTL-fixtures, die datzelfde
assenstelsel voor RD laten doorgaan. Ze hebben daarom de `crs`-member gekregen die de
heuristiek accepteert. Dat is een wijziging in de fixturebestanden en niet in de tests:
geen enkele testregel is ervoor aangepast, en de fixtures zeggen nu expliciet wat ze
altijd al beweerden.

### BO-14 De lokaal/contextueel-optimalisatie is uitgesteld, niet vergeten

**Wat.** Lokale checks (attributen, hoogten) geven voor hetzelfde object dezelfde
bevinding, ongeacht welke subset eromheen zit. Ze zouden bij een run over tachtig buurten
een keer over de unie kunnen draaien in plaats van tachtig keer per gebied. Dat is
bewust *niet* gebouwd.

**Waarom niet.** Het vraagt een classificatie lokaal/contextueel per check, en een fout
in die classificatie breekt de equivalentiegarantie uit BO-12 stilzwijgend: een check die
ten onrechte als lokaal geldt, mist de context van het gebied en meldt te veel of te
weinig, zonder dat iets afwijkt behalve de uitkomst. De winst is bovendien onbekend
zolang er niet gemeten is.

**Waar de meting vandaan komt.** De voortgangsfasen dragen de gebiedsnaam (`Checks
<naam>`), en `tests/test_integration.py::test_schaal_tachtig_buurten` logt de duur van een
80-buurtenrun. Pas als die meting laat zien dat de checkfase de post is die telt, is deze
optimalisatie de moeite en het risico waard.

**Eerste meting (18 augustus 2026).** Op de volledige De Wolden-export, met de
Koekangerveld-omhullende in 80 stroken en TOP-001 als enige check: **2,7 seconden** voor
alle tachtig gebieden samen, tegen ruim twee en een halve minuut voor het inlezen van de
dataset. De post die telt is dus het laden, en dat gebeurt al maar een keer. Deze meting
is niet het hele verhaal -- met de volle checkset en echte buurten (groter, meer objecten
per gebied) loopt de checkfase op -- maar ze laat wel zien dat er op dit moment geen
aanleiding is om de equivalentiegarantie op het spel te zetten. Herhaal de meting op een
echt 80-buurtenbestand met alle checks voordat je BO-14 heroverweegt.

### BO-15 Een gebied zonder GWSW-objecten stopt een meervoudige run niet

**Wat.** Bij een run over meerdere studiegebied-features levert een gebied zonder enkele
put en zonder enkele streng een gewone uitvoer op met nul bevindingen, met een expliciete
regel in zijn eigen rapport ("Geen objecten in dit gebied") en een vermelding in de
totaalsynthese. Bij een run op een enkel gebied blijft het een harde fout, met dezelfde
melding als voorheen. `CheckRun.beperk_tot_studiegebied` heeft daarvoor het keyword
`leeg_toegestaan`; de toetsloop zet het alleen bij meerdere gebieden.

**Waarom.** Een CBS-buurtenbestand van een plattelandsgemeente bevat betrouwbaar buurten
zonder vrijvervalriolering: water, natuur, een bedrijventerrein op eigen beheer. De
schaaltest op 80 gegenereerde buurten liep hier ook op vast. Een hele run van uren laten
sneuvelen op de eerste zo'n buurt maakt de functie onbruikbaar voor precies het geval
waarvoor hij gebouwd is. Bij een enkel gebied is een leeg gebied juist bijna altijd een
verkeerd bestand of een verkeerde laagkeuze, en daar blijft de fout dus staan.

**Waarom niet stil.** Nul bevindingen leest als "hier is alles in orde". Daarom staat het
in het rapport van het gebied zelf en in de synthese, in de geest van de regel dat wat
niet bekeken is in het rapport hoort.

### BO-16 De mapnaam `totaal` is gereserveerd

**Wat.** Een gebiedsnaam die na sanering `totaal` oplevert, is een harde fout bij het
lezen van het gebiedsbestand.

**Waarom.** `totaal/` is de submap met de synthese en de unieke meldingen. Een buurt die
"Totaal" heet zou erin schrijven, waarna de synthesestap de CSV en de JSON van die buurt
overschrijft en er een map achterblijft die er compleet uitziet. Dat is stille corruptie;
de bestaande botsingscontrole tussen twee gebiedsnamen zag hem niet, want de tweede naam
is geen gebied. De constante staat in `studiegebied.py` en de uitvoerlaag leest hem daar,
zodat de reservering en het gebruik niet uit elkaar kunnen lopen.

### BO-17 De twee EXT-lagen volgen de meldingen, en erven hun beperkingen

**Wat.** De GeoPackage-lagen `bouwwerken` (EXT-001) en `waterdelen_zonder_zinker`
(EXT-003) worden uitsluitend gevuld door de meldingen van die uitvoer te joinen op het
trefferregister van de run (`checks/treffers.py`). De schrijver bevraagt geen externe
bron en doet geen ruimtelijke selectie.

**Waarom.** Een tweede pad naar dezelfde vraag is een tweede antwoord. Zou
`uitvoer/gpkg.py` zelf de BGT bevragen, dan kan de laag panden tonen waar geen melding
over gaat, of andersom -- en dan is niet meer te zeggen welk van beide de uitslag is.
Nu is de laag per constructie de verzameling unieke `object2_uri`'s van die check, en
de kerntest in `tests/test_uitvoer_gpkg.py` legt precies dat vast. Bij rapportage per
gebied volgt het juiste gedrag er gratis uit: per gebied de treffers van dát gebied.

**Twee beperkingen die bewust meekomen.** EXT-001 meldt per streng of put alleen het
sterkste bouwwerk (`_sterkste`); een object dat twee panden raakt levert dus één pand
in de laag. `_WatergangKruising.kruisingen()` breekt af na het eerste gevonden
waterdeel per streng; een streng die er twee kruist levert er één, en welke hangt van
de volgorde af. Beide zijn niet gerepareerd: dat zou meldingaantallen, rapporten en
trendvergelijkingen wijzigen, en dat is een eigen beslissing met een eigen ronde.

**De verruiming als benoemde optie.** Alle geraakte objecten melden in plaats van
alleen het sterkste (en het eerste) is de voor de hand liggende volgende stap. Hij
staat niet gepland; wie hem oppakt, moet weten dat de meldingaantallen erdoor
veranderen en dat elke trendvergelijking over die grens heen breekt.

### BO-18 De sleutel van een extern object, met een geometriehash als terugval

**Wat.** `object2_uri` van een EXT-melding is `bgt:pand/<id>`, `bag:pand/<id>`,
`bgt:bouwwerk/<id>` of `bgt:waterdeel/<id>`. De `<id>` komt uit de eerste gevulde
kolom van `lokaal_id`, `identificatie`, `id` -- gemeten op `data/gis` én op de
fixtures: de BGT-lagen dragen `lokaal_id`, de BAG-laag `identificatie`, en beide
daarnaast een `id`. Draagt een bron geen van drieën, dan wordt de sleutel
`geo:<eerste 12 hex van sha256 over de WKB>`, met een notitie in de checkuitkomst.

**Waarom geen harde fout bij een ontbrekend ID.** Externe data is context, geen poort
(BC-1). Een bron zonder identificatie is nog steeds bruikbaar; alleen is de sleutel
dan gevoelig voor een wijziging in de geometrie, en dat hoort de lezer te weten.
Vandaar de notitie in plaats van een uitzondering.

**Waarom de geometrie en niet de rij-index.** Een index is niet stabiel over exports
en zegt niets als de bron opnieuw getrokken wordt. De hash over de WKB is stabiel
zolang de geometrie dat is, en ontdubbelt twee bestanden met hetzelfde object -- wat
hier precies de bedoeling is.

**Waarom de geometrie niet in de melding zit.** Een polygoon in `Finding.details` zou
in de CSV en de JSON als WKB terechtkomen. De geometrie gaat daarom via het
trefferregister naar de GeoPackage; de JSON draagt alleen de sleutel en het label.

### BO-19 De dekkingspoort meet tegen het bereik van de bronnen

**Wat.** Bij het laden van de externe bronnen wordt elke aangeleverde laag, plus het
AHN-raster, getoetst op dekking van de omhullende van `bronnen.studiegebied`. De
vectorlagen krijgen daar de grootste EXT-zoekafstand bij (`ext_zoekafstand_max_m`, in
de standaardconfig 10 m); het raster niet, want bemonsteren is puntsgewijs. Een tekort
groter dan `[bronnen] dekking_tolerantie_m` (standaard 0) is een `ExternalDataError`
die per falende bron beide omhullenden en het tekort per zijde noemt. Geen
forceer-vlag.

**Waarom een harde fout, terwijl externe data "context, geen poort" is.** Die
filosofie (BC-1, BC-2) gaat over *ontbrekende* data: een check die zijn bron mist,
meldt dat en geeft geen uitslag. Deze poort gaat over *aangeleverde maar te kleine*
data. Daar is de faalwijze omgekeerd: de check draait, vindt niets, en dat leest als
"geen probleem" terwijl de bron er domweg niet was. Stil falen is hier het gevaar, en
een waarschuwing in een rapport dat verder schoon oogt is niet genoeg.

**Waarom `bronnen.studiegebied` als referentie en niet het studiegebied van de run.**
Het masterdocument stelde de unie van de studiegebied-features voor. Dat de bronnen
maar een deel van de GWSW-dataset dekken is in dit project echter normaal en al
eerlijk afgevangen: objecten buiten het bereik krijgen de status *buiten studiegebied*
en worden geteld (BC-2). Wat overblijft is een laag die kleiner is dan het gebied
waarvoor je hem geldig verklaart, en dat gebied is precies `bronnen.studiegebied`.
Bijkomend voordeel: de poort blijft binnen `load_external_data`, zonder nieuwe
parameter en zonder volgorde-afspraak in de CLI die iemand later kan omdraaien.
Nadeel dat je moet kennen: dekt het bereik zelf maar de helft van je studiegebied, dan
zegt deze poort daar niets over -- de per-objectnotities doen dat.

**Waarom een instelbare tolerantie.** De omhullende van een laag is die van zijn
*features*. Een dunne laag met een lege rand is niet te onderscheiden van een
afgeknipt extract. Gemeten op de eigen bronnen van dit project: het AHN-raster komt
0,3 m tekort (afrondingsruis van de uitsnede) en `bgt_bouwwerk` 276 m (52 objecten die
aan de oostkant ophouden). Elke drempel daartussen is een keuze en geen meting, en die
keuze hoort in de projectconfiguratie. De standaard is 0, dus streng; voor `data/gis`
is ongeveer 300 m nodig.

**Wat deze poort niet kan.** Bbox-dekking is noodzakelijk maar niet voldoende: een gat
midden in het extract valt er niet mee op. Dat staat in de docstring, en er is een
test die het vastlegt (`test_gat_middenin_slaagt`) zodat de belofte niet stilletjes
groter wordt dan de meting.

**Overwogen en niet gedaan:** een raster een pixelmaat speling geven in plaats van de
gewone tolerantie. Het AHN-raster komt 0,3 m tekort door afronding van de uitsnede, en
een halve cel is daar een natuurlijker maat voor dan een drempel in meters. Het is niet
gebouwd: het zou een tweede drempelbegrip introduceren voor precies één bron, terwijl de
bestaande tolerantie het geval al afvangt. Wie het alsnog wil, heeft aan de celgrootte
uit `RasterSampler` genoeg.

**Gevolg voor de meldingidentiteit.** Nu EXT-001 en EXT-003 hun `object2_uri` vullen,
verschuift hun `melding_id` eenmalig -- die hash bevat dat veld. Een trendvergelijking
over die grens heen laat de meldingen als opgelost plus nieuw zien. Dat staat in het
wijzigingslog en in `docs/json-schema.md`; het alternatief (het veld buiten de hash
houden) zou twee meldingen over verschillende panden dezelfde identiteit geven.

### BO-20 De klassenselecties staan op een plek, met de GWSW-naam waar die bestaat

**Wat.** Elke rol waarop de checks selecteren -- netwerkknopen, putten, leidingen,
vrijvervalrioolleidingen en tien andere -- heeft een functie in
`src/nlriochecker/checks/selectie.py` en cachet daar onder `sel:<rolnaam>`. De
generieke ingang `verbanden.objecten_van_klassen` is verwijderd. De begrippen staan in
[CONTEXT.md](../CONTEXT.md).

**Waarom.** Dezelfde selectie werd op zes plaatsen opgebouwd. `netwerkknopen` had drie
cachesleutels (`adm:putten`, `hgt:putten`, `ext:putten`) plus een ongecachete aanroep
plus twee met de hand overgeschreven comprehensions; `vrijvervalleiding` idem.
`dataset.of_class` doet per wortelklasse een volledige doorloop over knopen en strengen
en wordt niet gememoiseerd, en `netwerkknopen` telt elf wortelklassen. Dat waren dus
tientallen doorlopen waar er elf nodig zijn, en evenveel kopieen van dezelfde lijst in
geheugen op een dataset van 3 GB.

**Waarom een module en geen methoden op `CheckContext`.** `context.putten()` leest
beter, maar `objecten_van_klassen` woonde in `verbanden.py` en dat importeert
`base.py`. Methoden zouden de implementatie naar `base.py` trekken, en dat bestand is
al de knoop waar elke checkmodule op leunt. Een module met functies die de context als
parameter nemen volgt bovendien het patroon dat `verbanden.aansluitingen(context)` al
had.

**Waarom de GWSW-naam.** De oude helper `_strengen` selecteerde `gwsw:Leiding`, en dat
is een verkeerd woord: `gwsw:Streng` bestaat niet en `gwsw:Rioolstreng` is iets anders
(de NEN 3300-aanduiding voor de riolering tussen twee putmiddelpunten). Waar een klasse
de rol dekt draagt de functie die klassenaam, ook als hij lang is
(`vrijvervalrioolleidingen`). Waar geen klasse de rol dekt is de naam een rolnaam en
zegt de docstring dat erbij. Bij `netwerkknopen` uitdrukkelijk: `gwsw:Knooppunt`
bestaat wel, maar is de orientatie en niet het object, dus die naam zou de ontologie
verkeerd citeren. Alle 22 wortelklassen uit `checks.toml` zijn tegen
`Ontologie_GWSW_Totaal.ttl` nagelopen en bestaan letterlijk.

**Waarom geen generieke ingang.** Een opzoeking op naam
(`selecteer(context, "putten")`) zou de vijftien functies overbodig maken. Precies zo'n
ingang bestond al -- `objecten_van_klassen` stond klaar -- en dat is hoe elke
checkmodule aan zijn eigen variant kwam. Een nieuwe rol kost nu een sleutel in
`[klassen]` en een functie; dat is een regel meer werk en het houdt de seam heel. Om
dezelfde reden is de naam-naar-functietabel in de module privé (`_ROLLEN`) en bestaat
hij alleen zodat de tests kunnen bewaken dat geen rol uitsluitend op een lege
verzameling getoetst wordt.

**Wat er niet in zit, en waarom dat geen vergeetachtigheid is.** Drie plekken krijgen
de rol als *gegeven* mee, via `getattr(context.config.klassen, rol)`:
`verbanden._bouw_aansluitingen` (aangeroepen met `"streng"` en `"vrijvervalleiding"`),
`netwerk._eindpunten` (met `"afvoer_eindpunt"` en `"lozings_eindpunt"`) en de
`stelselrol` van de NET-checks (met `"vuilwater"` en `"hemelwater"`). Daar is de rol
een variabele, en een benoemde functie kan die niet bedienen zonder de opzoeking op
naam die hierboven juist verworpen is. Ze bouwen dus nog steeds hun eigen selectie.
Buiten de checklaag geldt hetzelfde voor `afbakening.py`, `analysis.py`,
`uitvoer/synthese.py` en `uitvoer/gpkg.py`: die hebben geen `CheckContext` en dus geen
cache om in te hangen. Ze horen bij de uitvoerlaag en gaan mee met de eerstvolgende
verbouwing daarvan. De belofte "de selecties staan op een plek" geldt dus voor de
vaste rollen in de checklaag, en niet verder.

**Hoe is vastgesteld dat er niets verschoof.** Een volledige run op De Wolden (23.485
knooppunten, 23.440 strengen, 35.975 bevindingen over 86 checks) voor en na de reeks
levert een byte-identieke `bevindingen.csv` en `bevindingen.json` op.
`tests/test_checks_selectie.py` legt daarnaast per rol de aantallen vast op het
Juinen-voorbeeld en op een fixture die alle rollen dekt, met de deelverzamelingsrelatie
tussen `putten` en `netwerkknopen` er expliciet bij -- dat is de verwisseling die deze
verbouwing had kunnen maken.

**Verworpen alternatieven.** De configuratiesleutels meehernoemen (`[klassen] streng`
naar `leiding`): dat maakt de laag consistent maar breekt bestaande projectconfiguraties
voor iets wat los staat van de duplicatie; `extra="forbid"` in de pydantic-modellen
zorgt wel dat zo'n breuk hard faalt en niet stil, dus het kan later alsnog. Een sweep
over de 448 keer "streng" in `src/`: dat is een andere verbouwing, en hij zou het bewijs
hierboven onleesbaar maken omdat elke rapportregel verandert.

### BO-21 De toetsrun is een module, en de opdrachtregel een adapter

**Wat.** `toetsrun.py` voert een toets uit: `Toetsopdracht` (paden en vlaggen) in,
`Toetsuitslag` uit. De module laadt, bewaakt de volgorde, toetst, schrijft en levert
met `regels()` het verhaal dat de gebruiker te zien krijgt. `cli.py` bouwt de
opdracht, roept aan en echoot; hij houdt alleen nog `_BalkVoortgang`, de click-kant
van het voortgangsprotocol. Alleen `toets` is omgezet -- `analyseer`, `dekking` en
`vergelijk` waren al dunne adapters van vijf tot acht statements zonder
domeinbeslissingen onderweg.

**Waarom.** De beslissingen in `check_command` waren geen presentatiekeuzes. De
volgorde (valideer de keuzes, de gebieden en de bronnen vóór je drie minuten en 3 GB
aan dataset laadt), de typeringspoort met haar drie samenhangende uitkomsten, en de
dekkingspoort op de bronnen zijn domeinregels. Ze stonden in privéfuncties van een
click-commando, en daarmee was `CliRunner` de enige seam om ze te bereiken:
`test_cli.py` telde 899 regels en 38 invokes, waarvan er veertien niets over de
opdrachtregel zeiden.

**Waarom de zinnen meegaan.** Het lag voor de hand om alleen data terug te geven en
de CLI de tekst te laten maken. Maar de tekst velt oordelen -- dat het net binnen een
gebied met vrijwel de hele export samenhangt, dat een gebied geen objecten bevat, dat
een check bevindingen met typeringsvoorbehoud heeft. Dat is interpretatie en geen
opmaak; in de CLI laten zou kandidaat A voor de helft laten mislukken. De uitslag
draagt daarom naast `regels()` ook negen velden, zodat een test op een veld kan
toetsen in plaats van op een zin, en een programmatische beller niet aan tekst vast
zit.

**Waarom `regels()` vlagnamen mag noemen.** Zinnen als "Geen typeringspoort toegepast
(--shacl niet opgegeven)" verwijzen naar de opdrachtregel. Neutraal formuleren maakt
de melding minder bruikbaar voor de enige gebruiker die er vandaag is; hem op twee
plekken zetten laat de twee uit elkaar lopen. De afspraak staat in de docstring:
`regels()` is de tekst voor de opdrachtregelgebruiker, en wie programmeert leest de
velden.

**Waarom `Toetsopdracht` paden draagt en geen geladen objecten.** Zou de opdracht een
geladen `Studiegebieden` en `ExternalData` bevatten, dan moest de beller ze zelf in
de goede volgorde laden -- precies de kennis die deze module overneemt. Dan was de
opdracht verplaatst en de kennis niet.

**Wat er niet in zit.** `_gekozen_cfk` kon niet mee: alle vier de commando's
gebruiken hem. Hij heet nu `meting.kies_cfk` en neemt twee reeksen in plaats van een
`CheckConfig`, zodat `meting.py` los blijft van de configuratielaag; dat sluit aan op
de regel dat de CFK-toestanden uit `Meetbereik` komen en nergens anders.

**Publiek, zonder belofte.** `toetsrun` is de bedoelde ingang voor een tweede beller
en de package levert `py.typed`, dus de hints komen bij een importeur aan. Onder 1.0
kan de vorm nog schuiven; `docs/versionering.md` noemt de Python-API nu expliciet
naast de CLI, de configuratie en het uitvoerformaat.

**Hoe is vastgesteld dat er niets verschoof.** De veertig verhaalregels verhuisden
naar een ander bestand, en daar kan een spatie of een omgekeerde volgorde bij
sneuvelen zonder dat een assertie faalt. Van een volledige run op De Wolden is
daarom de hele stdout vergeleken: 95 regels, identiek op de gemeten laadtijd na (2,6
tegen 2,5 seconden), en `bevindingen.csv` byte-identiek. De regeldekking is gemeten
op de staat vóór en na: `cli.py` had 18 ongedekte statements, en elke ongedekte regel
erna heeft een voorganger.

### BO-22 De GeoPackage-lagen krijgen geen gezamenlijke declaratie

**Wat.** Een architectuurreview stelde voor om elke laag van de GeoPackage als een
`Laagdefinitie` te beschrijven -- naam, geometriesoort, kolommen, omschrijving,
stijl, rijenbouwer -- en `schrijf_geopackage` die lijst te laten aflopen. Dat gaat
niet door. Wat er wel gebeurd is: het fase-totaal van de voortgang volgt nu uit een
rij staplabels in plaats van uit een met de hand geteld getal.

**Waarom niet.** De aanleiding was echt: een laag toevoegen raakt zes plaatsen, en de
laatste uitbreiding kostte 196 regels. Maar de zes featurelagen zijn niet
gelijkvormig. `putten` en `strengen` delen hun kolommen en lopen al door een
gezamenlijke lus. `mechanisch_riool`, `meldinglocaties`, `bouwwerken` en
`waterdelen_zonder_zinker` hebben elk een eigen schrijver met eigen ingrediënten: de
een heeft de verzameling objecten binnen het gebied nodig, de ander de meldingen per
object, de derde het trefferregister. Ze onder één declaratie brengen vraagt om een
rijenbouwer per laag met een eigen signatuur, en dan staat de complexiteit in een
tabel met lambda's in plaats van in zes functies. De deletion test valt negatief uit:
haal de declaratie weg en er verdwijnt niets, het verhuist alleen terug.

**Wat er wel fout was.** `start_fase("GeoPackage", 10)` was een getal dat met de hand
geteld werd over drie functies heen (twee in de featurelus, twee losse lagen, twee
trefferlagen, vier attribuuttabellen en stijlen). Niets hield het gelijk aan het
aantal `stap()`-aanroepen. Liep het uit de pas, dan telde de balk over of stopte hij
te vroeg -- geen verkeerde uitslag, wel een verkeerd beeld van wat er gebeurt tijdens
de duurste schrijffase. Het totaal is nu `len(GEOPACKAGE_STAPPEN)`, en een test
toetst dat de gezette labels precies die rij zijn.

**Wanneer dit heroverwogen hoort te worden.** Als er een derde trefferlaag bijkomt --
`bouwwerken` en `waterdelen_zonder_zinker` delen wél hun vorm, want ze komen allebei
uit het trefferregister via `_vul_trefferlaag`. Twee is krap voor een seam; drie
maakt het een echte. Voor die twee alleen is de bestaande gedeelde functie genoeg.

### BO-23 De uitvoerlaag krijgt geen gezamenlijk `(run, meldingen)`-object

**Wat.** Een architectuurreview stelde voor om het paar `(run, meldingen)` -- dat
door negen functies in de uitvoerlaag reist -- in een `Meldingenstroom` te vatten:
run plus rundatum in, meldingen erbij gebouwd, en de schrijvers nemen die ene waarde.
Dat is gebouwd en weer teruggedraaid. Wat er wel van over is: de twee plekken die nog
hun eigen klassenselectie opbouwden gebruiken nu `checks/selectie.py` (het restant dat
BO-20 aankondigde), en `mechanischeleidingen` is daar als rol bijgekomen.

**Waarom het aantrekkelijk leek.** De vier uitvoervormen moeten aantoonbaar dezelfde
meldingen wegschrijven. Dat de meldingen bij die run horen, en met dezelfde rundatum
gebouwd zijn, stond nergens in een interface. `schrijf_uitvoer` had er zelfs een
optionele parameter voor, met als enige reden dat de gebiedenlus de lijst niet twee
keer wilde bouwen.

**Waarom het niet doorgaat.** Bij het omzetten van de tests bleek dat vijf tests de
meldinglijst met opzet los van de run aanleveren, en dat ze daar gelijk in hebben:

- de stapelnummering moet onafhankelijk zijn van de volgorde van de lijst, dus voert
  de test dezelfde meldingen omgekeerd in;
- een melding die naar een niet-geregistreerde treffer wijst moet luid falen, dus
  voert de test één zelfgemaakte melding in;
- de afkapping van de verdachte-objectenlijst slaat pas aan bij acht objecten met
  meldingen uit drie checks, en het meervoud in de slotzin bij precies één;
- het rapport moet een melding zonder foutlocatie apart benoemen.

Die toestanden zijn uit een echte dataset niet of alleen met veel moeite te bouwen.
De `Meldingenstroom` maakt ze onbereikbaar, en dan verruil je een invariant die in de
productiecode nooit geschonden werd -- de enige plek die het kon, gaf de lijst door
die hij een regel eerder zelf gebouwd had -- voor testbaarheid die wel echt gebruikt
wordt. Een escape hatch (`Meldingenstroom.van_meldingen(...)`) zou precies de
ontkoppeling terugbrengen die het object moest opheffen, en dan is de winst nul.

**Wat het wel zegt over de code.** De optionele `meldingen`-parameter van
`schrijf_uitvoer` en `write_check_report` blijft een parameter die er alleen staat om
dubbel rekenwerk te vermijden. Dat is een prijs die we bewust betalen; hij staat in de
docstring van beide functies uitgelegd.

**Wanneer dit heroverwogen hoort te worden.** Als er een schrijver bijkomt die zijn
meldingen zelf ophaalt in plaats van ze aangereikt te krijgen. Dan is de invariant wel
degelijk schendbaar, en weegt hij op tegen de testbaarheid.

### BO-24 De oever telt niet als watergang

**Wat.** `bgt_waterlagen` bevat alleen `waterdeel`, nooit `ondersteunendwaterdeel`. Die
laatste laag valt buiten scope voor de hele analyse. Binnen `waterdeel` telt elk type
mee; er wordt niet op `type` gefilterd.

**Waarom.** EXT-002 en EXT-003 gaan over een streng die een watergang kruist, en EXT-007
over een lozingspunt bij ontvangend oppervlaktewater. `ondersteunendwaterdeel` is in de
BGT de oever: van de 44.144 objecten in de De Wolden-export draagt 44.143 het type
`oever, slootkant` en één `transitie`. Een streng die een slootkant raakt kruist geen
water. Erger nog: de check stopt na het eerste waterdeel per streng (BO-18), dus een
oever die eerder in de index staat dan de sloot waar hij bij hoort, verdringt de echte
kruising uit de melding.

**De meting.** Op de eerste volledige run over De Wolden + Hoogeveen (2026-08-19) meldden
EXT-002 en EXT-003 elk 993 strengen. Naar BGT-type: waterloop 514, oever/slootkant 306,
greppel/droge sloot 109, watervlakte 64. Bijna een derde van de meldingen ging dus over
een oever. Op Koekangerveld viel dat niet op: daar telt `ondersteunendwaterdeel` 94
objecten en ging het om enkele meldingen.

**Waarom niet op type filteren binnen `waterdeel`.** De verleiding is om ook
`greppel, droge sloot` (21.673 van de 97.148 objecten in De Wolden) te laten vallen: droog
is geen watergang. Dat is niet gedaan. Een greppel is een watervoerend element dat bij
neerslag wel degelijk water afvoert, en of hij ter plaatse droog staat is een momentopname
en geen eigenschap van de kruising. Bovendien is de scheiding tussen laag en type
principieel: de laag zegt *wat het object is* (water of oever), het type zegt *hoe het
eruitziet*. Alleen het eerste hoort de populatie te bepalen.

**Waarom in de config en niet in de code.** `bgt_waterlagen` blijft een lijst in de
projectconfiguratie, zoals alle laagrollen. Een export met andere laagnamen moet die
kunnen aanwijzen. Wat hier verandert is de standaard, en de reden staat in het configbestand
zelf zodat wie hem overschrijft weet wat hij weggooit.

**Het gemeten effect.** Dezelfde run opnieuw gedraaid met alleen `waterdeel`:

| | voor | na |
|---|---:|---:|
| EXT-002 / EXT-003 | 993 | 859 |
| EXT-007 | 55 | 58 |
| meldingen totaal | 52.373 | 52.108 |

Er vielen 134 strengen weg en er kwam er geen enkele bij. De overige 172 oevertreffers
bleken strengen die óók een echte watergang kruisen; die worden nu op dat waterdeel gemeld.
Bij **195 strengen** wijst de melding daardoor een ander object aan dan voorheen -- dat is
de verdringing uit BO-18 die zichtbaar wordt, en meteen de belangrijkste winst: die
meldingen wezen naar de verkeerde watergang. Wat overblijft is waterloop 657,
greppel/droge sloot 123, watervlakte 79.

EXT-007 gaat juist *omhoog*, van 55 naar 58. Drie lozingspunten lagen naast een oever en
telden daardoor als aangesloten op oppervlaktewater terwijl er geen waterdeel in de buurt
lag. Dat zijn geen valse meldingen erbij maar drie gemiste bevindingen die nu boven water
komen.

**Gevolg voor de meldingidentiteit.** De meldingen die op een oever stonden verdwijnen, en
de 195 strengen die op een ander object gemeld worden krijgen een andere `object2_uri`.
Hun `melding_id` verschuift daarmee eenmalig, net als bij BO-19: een trendvergelijking over
die grens heen laat ze als opgelost plus nieuw zien.

### BO-25 Een duiker is geen rioolleiding; EXT-002 en EXT-003 blijven op VrijvervalRioolleiding

**Wat.** De populatie van EXT-002 en EXT-003 blijft `klassen.vrijvervalleiding`
(`VrijvervalRioolleiding`). Een `Duiker` valt daar buiten en wordt dus niet op een
watergangkruising getoetst. De uitzondering van EXT-003 luistert nog steeds naar
`klassen.kruisingsleiding` (zinker en duiker), maar alleen de zinker kan binnen de
populatie voorkomen; titel en meldingstekst noemen daarom de zinker. Het rapport telt in
de toelichting hoeveel strengen van een kruisingsklasse buiten de populatie vielen.

**Waarom.** De ontologie is er ondubbelzinnig over.
`gwsw:Duiker rdfs:subClassOf gwsw:Leiding`, met als definitie "Een leiding die
oppervlaktewater-elementen verbindt" -- een duiker *is* de watergang, hij kruist er geen.
`gwsw:Zinker rdfs:subClassOf gwsw:VrijvervalRioolleiding`: die zit dus wel in de
populatie, en daar is de uitzondering van EXT-003 ook voor bedoeld. Issue #3 las de
gelijkheid van EXT-002 en EXT-003 als een fout in de populatie; ze is een gevolg van de
klassenhierarchie. Wat er wel aan mankeerde is dat niets dat opschreef.

**Verworpen: de populatie verbreden naar `Leiding`.** Dan komen ook drains (1.216),
kolkaansluitleidingen (124), loze leidingen (54) en perceelaansluitleidingen (113) in
beeld, en meldt EXT-002 elke drain die langs een sloot ligt als watergangkruising. Dat is
niet wat het register met "kruising met watergang" bedoelt, en het zou de meldingenstroom
met ruis vullen om een uitzondering te kunnen laten afgaan.

**Verworpen: EXT-003 een eigen, bredere populatie geven.** Duikers erbij halen om ze
vervolgens door de uitzondering te laten uitzonderen levert per constructie nul extra
meldingen op. Objecten binnenhalen met de enige bedoeling ze weer weg te strepen is
vertoon, geen toets.

**De fixtures.** `scripts/maak_ttl_fixtures.py` zette `Duiker` en `Zinker` allebei onder
`VrijvervalRioolleiding`. Daarmee testte het EXT-scenario een hierarchie die niet bestaat
en kon de fout uit issue #3 in de tests niet zichtbaar worden. De fixtures volgen nu de
totaal-ontologie: `Duiker` onder `Leiding`, `Zinker` onder `VrijvervalRioolleiding`.

**De meting.** Op De Wolden + Hoogeveen melden EXT-002 en EXT-003 elk 859 strengen op
17.603 bekeken -- ongewijzigd ten opzichte van BO-24, zoals de bedoeling was: deze ronde
verandert geen enkele melding van de twee. Nieuw is de regel in de toelichting van EXT-003:
"Buiten de populatie (geen vrijvervalleiding) en dus niet bekeken: 610 strengen van de
klasse Duiker." Dat is precies de 610 uit issue #3, nu in het rapport zelf.

**Gevolg.** EXT-002 en EXT-003 delen sinds deze ronde een kruisingenlijst
(`context.cached("ext:watergangkruisingen")`): hun `toetsbaar`-verzameling, buffer en laag
zijn aantoonbaar dezelfde, dus de ruimtelijke toets liep twee keer voor niets. De uitslag
verandert daar niet van. Dat EXT-003 gelijk is aan EXT-002 blijft waar zolang de dataset
geen zinker bevat -- De Wolden heeft er nul -- maar het staat nu in het rapport in plaats
van dat het opvalt als raadsel. De `break` na het eerste waterdeel per streng blijft staan
(BO-17, BO-18).

### BO-26 RVZ-002 en RVZ-003 terug in de engine; een sentinel moet iets aantonen

**Wat.** RVZ-002 (drempelniveau) en RVZ-003 (drempelbreedte) zijn uit de tabel Geschrapte
checks van het register gehaald en gebouwd: W, Compleetheid, een melding per overstortput
zonder geregistreerd niveau respectievelijk zonder geregistreerde breedte. Hun sentinels
zijn uit `dekking.toml`. De dekkinganalyse eist voortaan dat elke overgebleven sentinel
in de referentiemeting werkelijk iets aantoont.

**Waarom.** De schrapping rustte op de claim dat de nulmeting de twee zou dekken. In geen
van de drie SHACL-rapporten over De Wolden bestaat een vorm op `Drempelniveau` of op
`Drempelbreedte`; de enige drempelvorm is `Overstortput_Overstortdrempel_card`, en die
toetst of de put een drempel *heeft*, niet of het niveau of de breedte geregistreerd is.
Er keek dus niets naar die twee eigenschappen: de engine niet, want de check was
geschrapt, de nulmeting niet, want de vorm bestaat niet, en het rapport meldde geen gat,
want een geschrapte check hoort daar niet meer thuis. Het register waarschuwt onder de
tabel Geschrapte checks precies voor dit geval.

**Waarom ook putten zonder drempelonderdeel.** De check meldt een overstortput ook als er
helemaal geen `Overstortdrempel`-onderdeel aan hangt -- en dat is in De Wolden de regel,
niet de uitzondering. Die melding overlapt met `Overstortput_Overstortdrempel_card`, en
die overlap is bewust: het register vraagt naar de geregistreerde *waarde*, en `toets`
moet ook zonder `--shacl` iets zien. De toelichting benoemt de overlap, zodat wie beide
rapporten naast elkaar legt weet dat hij hetzelfde gebrek twee keer telt.

**Waarom W en Compleetheid.** Naar analogie van RVZ-007 t/m RVZ-009: een ontbrekende
registratie op een randvoorziening is een gat in de gegevens, geen aantoonbare fout in de
werkelijkheid. Een drempel die niet geregistreerd staat hoeft er fysiek niet te ontbreken.

**De poort eronder.** Het echte gat zat in de dekkinganalyse zelf: `verify_register`
toetste alleen ID-pariteit tussen het register en de sentineltabel, nooit of een sentinel
in de referentiemeting iets aantoont. Daar is nu een inhoudelijke poort naast gezet:
`CoverageResult.untouched == []`, op de mini-nulmeting (`tests/test_coverage.py`) en op de
volledige De Wolden-rapporten (`tests/test_integration.py`). Een schrapping waarvan het
bewijs nul meldingen oplevert valt daarmee in CI om. De weergave van "niet geraakt" blijft
apart getoetst met een fixture-mapping waarvan de sentinel nergens vuurt.

**De meting.** Op De Wolden + Hoogeveen melden RVZ-002 en RVZ-003 allebei alle 245 bekeken
overstortputten: 218 `Overstortput` plus 27 `Stuwput`, want `klassen.overstortput` bevat ze
allebei. Dat is geen 245 losse gebreken maar een systematisch registratiepatroon -- de
export bevat geen enkel `Overstortdrempel`-onderdeel (BA-10) -- en de toelichting van de
check zegt dat er met zoveel woorden bij. De twee checks samen brengen 490 waarschuwingen
in de totaaltelling.

**Gevolg.** Het aantal ID's in de engine groeit met twee; de dekkingsmatrix en de
versiehistorie van het register (v0.9) volgen. De ID's zijn nooit hergebruikt, dus RVZ-002
en RVZ-003 betekenen nog steeds wat ze in v0.1 betekenden.

### BO-27 Een vulwaarde rond 0 m NAP is geen meting: een leesregel plus ATTR-013

**Wat.** Een hoogtekenmerk uit `[vulwaarden] hoogte_kenmerken` met |waarde| <=
`hoogte_band_m` wordt gelezen als *niet geregistreerd*. De regel staat in
`dataset.markeer_vulwaarden`, wordt op precies een plek toegepast -- in
`toetsrun.voer_toets_uit`, direct na `laad_met_cache` -- en onthoudt op het object welk
kenmerk welke waarde droeg. De nieuwe check ATTR-013 (W, Compleetheid) meldt dat een keer
per object.

**Waarom.** In de De Wolden-export is 11.786 van de 46.880 BOB-waarden (25,1%) exact
`0.000`; de op een na meest voorkomende waarde komt 399 keer voor. Van de 22.363
maaiveldhoogten staat 14% op `0,00` of `0,01`. Het AHN ligt in dit gebied tussen 5,09 en
17,09 m NAP. Dat is een vulwaarde voor "niet geregistreerd", geen buisbodem op zeeniveau.
De hoogtechecks lazen hem als meting. Een regex over de meldingteksten in issue #1 vond een
nul in 94% van de HGT-004-meldingen, 85% van HGT-018, 61% van HGT-003 en 48% van HGT-002 --
samen circa 5.700 van de 31.901 harde fouten. Dat zijn de cijfers van die regex, niet van de
meting hieronder: hij zag de nul alleen waar die in de tekst stond. Dat is de situatie waar
CLAUDE.md voor waarschuwt: duizenden bevindingen wijzen op een modelleerfout in de engine,
niet op duizenden gebreken.

**Het gemeten effect.** Dezelfde run over De Wolden + Hoogeveen twee keer gedraaid, alleen
`hoogte_kenmerken` leeggemaakt in de tweede: dat isoleert de leesregel van de rest van deze
bugronde. De tabel noemt elke check die beweegt -- veertien -- zodat beide kolommen op hun
totaal uitkomen; alle overige checks staan links en rechts op hetzelfde getal.

| | zonder leesregel | met leesregel |
|---|---:|---:|
| HGT-002 (deksel vs AHN) F | 5.231 | 2.128 |
| HGT-003 (BOB-sanity vs AHN) F | 2.813 | 1.090 |
| HGT-004 (BOB boven deksel) F | 532 | 31 |
| HGT-018 (buiskruin boven maaiveld) F | 1.190 | 175 |
| HGT-006 (fors tegenverhang) F | 2.459 | 2.377 |
| NET-003 (stroming tegen het verhang) F | 3.725 | 3.651 |
| HGT-013 (gronddekking) W | 2.545 | 340 |
| HGT-014 (verhang vs maaiveld) W | 889 | 157 |
| HGT-007 (te weinig verhang) W | 2.126 | 1.559 |
| HGT-008 (extreem verhang) W | 247 | 159 |
| HGT-009 (BOB-sprong zonder valput) W | 327 | 282 |
| HGT-001 (dekselhoogte vs AHN, 5 cm) W | 5.820 | 5.811 |
| HGT-005 (licht tegenverhang) W | 1.286 | 1.285 |
| ATTR-013 W | 0 | 4.215 |
| **fouten totaal** | **31.901** | **25.403** |
| **waarschuwingen totaal** | **20.697** | **21.265** |

Beide kolommen komen van de code *na* deze bugronde; alleen de leesregel verschilt. Dat de
linkerkolom precies de 31.901 uit issue #1 reproduceert, en HGT-002/003/004/014/018 daar op
precies 5.231 / 2.813 / 532 / 889 / 1.190 staan, is dus zelf een uitkomst: geen andere
wijziging van deze ronde verschuift een van die aantallen. Er verdwijnen
6.498 fouten en 3.647 waarschuwingen. Elke verdwenen melding is terug te voeren op een
vulwaarde op het gemelde object zelf of op een van zijn twee putten -- nagelopen op de
melding-ID's, met nul onverklaarde gevallen. Er komt er ook bijna geen bij: alleen HGT-009
wint er twee, doordat een 0,000-BOB de werkelijke, kleinere BOB-sprong op die put stond te
verdringen.

De schatting van circa 5.700 uit issue #1 was een ondergrens: die regex keek naar vijf
checks en naar de waarde in de meldingtekst. HGT-002 verliest er 566 meer dan de regex
zag, en HGT-006 en NET-003 stonden er niet eens in. Wie op de vulwaarde in de tekst zoekt,
mist de melding waarin het buurobject de nul draagt.

**Wat ATTR-013 niet meldt.** Van de 11.812 BOB-waarden binnen de band liggen er 2.003
op een `VrijvervalRioolleiding`; de overige 9.809 zitten op klassen die de hoogtechecks
sowieso niet bekijken -- `Persleiding` 6.894 van 7.096 (97%), `Drain` 1.593, `Duiker` 483,
`Kolkaansluitleiding` 244, de perceelaansluitleidingen 223, `Vacuumleiding` 294 (alle),
`Drukleiding` 49, `LozeLeiding` 29. Dat is geen gat maar dezelfde afbakening: ATTR-013
bekijkt de netwerkknopen plus de vrijvervalstrengen, en meldt 2.003 BOB's op 1.095
strengen plus 3.120 maaiveldhoogten, samen 4.215 objecten. Wie het getal 11.786 uit issue
#1 naast 4.215 legt, moet dat verschil kennen: een persleiding zonder BOB is geen gebrek
dat deze checks aanwijzen.

Let wel: de leesregel zelf loopt over *alle* strengen in `dataset.conduits` en zet die 9.809
BOB's dus ook op ontbrekend. Wat de populatie buitensluit is niet de bewerking maar de
melding: ATTR-013 rapporteert die objecten nooit. Dat is hier zonder gevolg -- geen enkele
hoogtecheck kijkt naar een persleiding -- maar het is een stille plek, en zodra een check op
die klassen gebouwd wordt moet ATTR-013's populatie meebewegen.

**Waarom een leesregel na het laden en niet in de lader.** De cache bewaart de ruwe parse;
de band is projectconfiguratie. Zou de lader hem toepassen, dan zat een projectkeuze in de
cachesleutel en leverde dezelfde TTL onder twee configuraties twee cache-ingangen op. Nu
is `markeer_vulwaarden` een pure functie op een geladen dataset -- ze geeft via
`dataclasses.replace` een nieuwe dataset terug -- met precies een aanroepplek. `analyseer`
en `dekking` raken hem niet: die gaan over de nulmeting en niet over de hoogten.

**Waarom een nieuw ATTR-nummer en geen HGT.** Wat er gemeld wordt is dat een kenmerk niet
geregistreerd is terwijl het als meting in de export staat. Dat is een registratiegebrek
(Compleetheid), geen hoogtefout (Plausibiliteit of Nauwkeurigheid). Een HGT-nummer zou het
tussen de verhang- en dekkingchecks zetten, waar de lezer een uitspraak over de hoogte
verwacht. En het is er precies een per object, niet een per hoogtevergelijking.

**Waarom een band en geen exacte nul.** Naast `0,000` komt `0,01` voor: 11.786 BOB's staan
exact op nul, 11.812 binnen de band, dus 26 waarden zitten ertussenin. `hoogte_band_m`
staat daarom op 0,01 en de regel toetst `abs(waarde) <= band`, zodat ook `-0,01` meetelt.
Een exacte gelijkheid op een float zou bovendien een broze toets zijn.

**Waarom `[vulwaarden]` met een lege lijst als uit-schakelaar.** TOML kent geen null, dus
een aparte `aan`-vlag naast een kenmerkenlijst zou twee waarheden opleveren die uit elkaar
kunnen lopen. Een lege `hoogte_kenmerken` is de uit-stand, en die stand staat met zoveel
woorden in de toelichting van ATTR-013: in laag Nederland kan 0,00 m NAP een echte meting
zijn, en stilte mag daar niet als "alles gecontroleerd" lezen.

**Verworpen: elke HGT-check filtert zelf.** Dan staat dezelfde drempel in dertien checks
opgeschreven -- zoveel blijken er in de meting geraakt te worden, en NET-003 zit er ook bij,
dus het is niet eens tot de HGT-familie beperkt. Het filter verschuift bij de eerste die
het vergeet, en geen enkele check kan dan zeggen hoeveel objecten er om deze reden zijn
overgeslagen. Een leesregel op een plek laat de checks doen waar ze voor zijn, en laat een
van hen -- ATTR-013 -- het gebrek benoemen.

**Gevolg.** De hoogtechecks slaan de betrokken objecten over en tellen ze in hun
toelichting mee bij de objecten zonder dat kenmerk; HGT-018 kreeg daarvoor de `notes()`
die ze nog niet had. Ze noemen de vulwaarde niet als reden -- dat doet ATTR-013 -- dus wie
alleen een HGT-toelichting leest, ziet "geen BOB" en niet "een BOB van 0,000". De
`melding_id`'s van de vervallen HGT-meldingen verdwijnen; een trendvergelijking over deze
grens heen ziet ze eenmalig als opgelost.
