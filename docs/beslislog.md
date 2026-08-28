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
verschuiven en worden geïnterpoleerd. HGT-001 en HGT-002 toetsen op 5 en 25 cm --
inmiddels op 10 en 25 cm, achterhaald door [[BO-44]] -- en een resample-artefact van
enkele centimeters zou de uitkomst bepalen. Beter weigeren dan
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
`scripts/uitgave.py` draait dezelfde vier bij een uitgave, en beide draaien sinds BO-38
ook een dekkingsondergrens. Mypy staat schoon op
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

**Achterhaald (deels).** De `break`-na-eerste-waterdeel voor de watergangkruisingen is
door [[BO-43]] opgepakt: `_WatergangKruising.kruisingen()` loopt voortaan alle
kandidaat-waterdelen per streng langs. De EXT-001-beperking (sterkste bouwwerk) blijft.

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

**Gevolg voor de meldingidentiteit.** Nu EXT-001 en EXT-003 -- en sinds [[BO-43]]
(#59) ook EXT-002 -- hun `object2_uri` vullen, verschuift hun `melding_id` eenmalig --
die hash bevat dat veld. Een trendvergelijking
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

Aan de knoopkant staat precies hetzelfde: `markeer_vulwaarden` loopt over *alle* knopen in
`dataset.nodes`, terwijl ATTR-013 de netwerkknopen meldt (put, afvoer- en lozingseindpunt,
bergbezinkvoorziening). Een maaiveldhoogte of dekselniveau op een compartiment- of
hulpstukorientatie wordt dus wel als ontbrekend gelezen en nooit gemeld.

Beide helften zijn sindsdien niet meer stil: de toelichting van ATTR-013 telt hoeveel knopen
en hoeveel strengen met een vulwaarde buiten haar gemelde populatie vallen. Het getal wordt
per run berekend uit de gemarkeerde dataset, zodat het niet uit de pas kan lopen met wat de
leesregel deed. Wat er nog niet staat is de klasse-uitsplitsing hierboven -- die staat hier,
gemeten op De Wolden, en niet in het rapport.

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

Ook de tabel met datakarakteristieken beweegt mee: `bepaal_karakteristiek` draait op de
gemarkeerde dataset, dus de kolom *Waarden* telt sindsdien alleen echte registraties.
Op De Wolden zakt de noemer met de kenmerken waarvoor hierboven een daling gemeten is: de
11.812 BOB-waarden binnen de band en de circa 3,1 duizend maaiveldhoogten daarbinnen (de
14% hierboven). Dat is geen volledige balans -- `Putdekselniveau` staat in dezelfde
leesregel en de noemer loopt over alle knopen, ook die buiten de netwerkknopen, maar
hoeveel er daar wegvalt is in deze ronde niet apart gemeten. Het histogram per
inwinningswijze zakt mee. Dat zijn de eerlijker getallen -- een vulwaarde is geen
registratie -- maar een noemer die zonder uitleg
verspringt leest als een meetfout, dus het rapport zegt het er zelf bij: onder de tabel
staat hoeveel hoogtewaarden de leesregel heeft weggezet.

### BO-28 De nulmeting is een tweede bron in de meldingenstroom, geen zeventigtal checks

**Context.** De SHACL-nulmeting voedde alleen de typeringspoort; de overtredingen zelf
verdwenen. Daardoor kon geen enkele uitvoervorm tonen dat een gebrek uit de GWSW-nulmeting
komt, laat staan uit welke conformiteitsklasse -- terwijl de categorie `NULMETING` en de
kolom `n_nulmeting` al in de GeoPackage stonden te wachten op een producent (issue #12).

**Besluit.** De overtredingen worden `Nulbevinding`'s (`nulbevinding.py`), hangen als veld
aan de `CheckRun` en worden door `bouw_meldingen` tot gewone `Melding`'s gemaakt, naast die
van het register. Ze dragen `bron = "nulmeting"`, categorie `NULMETING`, check-ID
`NULMETING-<SHACL-vorm>`, dimensie `Compliance` en een nieuw veld `cfk`.

**Verworpen: er `CheckOutcome`'s van maken.** Dan is elke SHACL-vorm een pseudo-check, geeft
`REGISTRY[outcome.check_id]` overal een `KeyError`, en krijgt het bevindingenrapport enkele
honderden vormsecties. De nulmeting is een tweede *bron*, geen tweede register.

**Verworpen: een tweede schrijver.** De vier uitvoervormen komen uit een meldingenstroom;
dat is geen afspraak maar een eigenschap van de code, en de sweep in
`tests/test_uitvoer_herkomst.py` bewaakt hem.

**De join loopt omhoog, en `hasConnection` mag alleen de eerste stap zijn.** De kolom
`Focus node` draagt het URI-fragment uit de dataset, maar wijst lang niet altijd een put of
streng aan: een `BeginpuntLeiding` hangt via `hasPart` onder zijn leidingorientatie, een
`Maaiveldorientatie` hangt via `hasConnection` onder de putorientatie. Er wordt daarom
omhooggelopen. `hasPart` en `hasAspect` zijn insluitingen en gaan altijd voor;
`hasConnection` is een symmetrische netwerkverbinding en zou de wandeling zijwaarts het
net in kunnen laten lopen, en doet daarom alleen in de eerste stap mee en pas als de twee
andere niets opleveren. Gemeten op De Wolden: strikt direct joint 87%, met insluitingen
98%, met de verbindingsstap erbij 99,5% (105.385 van de 105.963). Wat overblijft zijn 575
overtredingen op een stelsel (`vw_geb_6`) en drie klassenamen uit `CfkTypes_typ` --
objecten die geen put en geen streng zijn en dat ook niet horen te worden.

**Een overtreding zonder object verdwijnt niet.** Hij krijgt geen `object_uri`, geen
locatie en een **leeg** gebied: hij is aan geen enkel studiegebied toe te wijzen, en hem
het gebied van de run geven zou beweren dat hij daarbinnen ligt. Hij blijft daarom in elke
gebiedsrun staan -- een losse run over dat ene gebied zou hem ook opnemen, en dat is de
equivalentie-eis van BO-12. In `totaal/` staat hij een keer, want daar wordt op
`melding_id` ontdubbeld. Het rapport telt hem apart, ook als het er nul zijn: stilte over
een gebrek dat de nulmeting wel telt, leest als "alles gecontroleerd".

**De identiteit hangt aan de focusnode en de boodschap.** De object-URI onderscheidt niet
genoeg -- twee eindpunten van dezelfde streng herleiden naar diezelfde streng -- en de
boodschap is bovendien de ontdubbelsleutel, want dezelfde vorm noemt per CFK een andere
drempel. Prijs: herformuleert de GWSW-server een boodschap, dan verschuiven de
melding-ID's van die vorm eenmalig en leest een trendvergelijking ze als opgelost plus
nieuw. Dat staat in `docs/json-schema.md` en in de wijzigingslog.

**Honderdduizend meldingen is de uitslag, niet een modelleerfout.** De drie rapporten
tellen samen 213.500 regels; na ontdubbeling over de conformiteitsklassen blijven er
105.963 over (87.017 fouten, 18.946 waarschuwingen). De zwaarste posten zijn drie
kardinaliteitsvormen die vrijwel elke `Inspectieput` raken -- `Put_HoogtePut_card`,
`Rioolput_Maaiveldschematisering_card` en `Rioolput_BergendOppervlak_card`, elk 19.322 keer
op ongeveer 19,5 duizend inspectieputten. Daar is de systemisch-vlag voor: 68.882 van de
105.963 meldingen dragen hem, en zeggen daarmee iets over de export als geheel in plaats
van over een los gebrek. De noemer van die vlag is het aantal instanties van het
objecttype uit `type=`, geteld over de volledige export en niet over een studiegebied --
anders zou "systemisch" iets anders betekenen naargelang er een gebied is opgegeven.

**Wat de tweede bron elders brak, en hoe het gerepareerd is.** `bouw_meldingen` heeft meer
afnemers dan de vier schrijvers, en die waren op een enkele bron gebouwd. Drie plekken
moesten mee:

- `synthese._multi_melding` ("dit object draagt meldingen uit drie of meer verschillende
  checks, zoek een enkele verdachte waarde") telt voortaan alleen meldingen uit het
  register. De redenering gaat niet op voor de nulmeting: haar vormen zijn niet
  onafhankelijk maar per kenmerk gesplitst, dus `Put_HoogtePut_card`,
  `Rioolput_Maaiveldschematisering_card` en `Rioolput_BergendOppervlak_card` slaan per
  constructie samen aan. Op De Wolden dragen 23.296 van de 32.389 focusnodes drie of meer
  vormen; die alle als verdacht aanwijzen maakt van die sectie ruis met een advies dat
  nergens toe leidt. Meldingen zonder object doen ook niet mee -- die belandden samen in
  een naamloze emmer en verschenen als een verdacht object met het label van de laatste.
- `gwsw_run` telt `fouten` en `waarschuwingen` voortaan uit de meldingenstroom in plaats
  van uit `CheckRun.count`, want `meldingen_totaal` deed dat al. Ze liepen anders met de
  hele nulmeting uit elkaar.
- De opdrachtregel zegt "fouten uit de eigen checks" en noemt de overtredingen uit de
  nulmeting apart. Optellen zou twee ongelijksoortige tellingen op een hoop gooien;
  verzwijgen zou een regel "120 fouten" opleveren naast een CSV met er tienduizenden.

En `CheckRun.weggelaten` telt sindsdien ook de nulbevindingen die de afbakening tot een
studiegebied wegliet. Het is nu de ene plek waar dat getal vandaan komt, zodat de
opdrachtregel, het rapport en de synthese er niet drie kunnen noemen.

**Het dashboard draagt allebei de bronnen, met lege checkkolommen.** `overzicht_checks` in
de GeoPackage bleef aanvankelijk op `run.outcomes` staan en toonde dus alleen het register,
terwijl de tabel zich als de checklijst presenteert (issue #24). Er staat nu een rij per
SHACL-vorm naast de rijen per check, uit dezelfde meldingenstroom en met de kolom `cfk`
erbij. De kolommen die alleen een `CheckOutcome` kent -- de omschrijving, `bekeken`,
`percentage_populatie`, `skelet` -- blijven op zo'n rij **leeg**: er is geen populatie
bekeken en er is geen titel, en een gevuld getal zou een dekking beweren die niemand
gemeten heeft. Dat is dezelfde regel als hierboven bij de overtreding zonder object. De
ernst is de zwaarste binnen de vorm, gelijk aan wat het rapport per vorm toont; twee
uitvoervormen die over dezelfde vorm een andere ernst noemen zou erger zijn dan geen van
beide. `scripts/steekproef.py` leest deze tabel op naam en filtert al op
`bron = "register"`, dus de steekproef ziet hetzelfde als voorheen.

**Het contract.** `cfk` is een achterwaarts verenigbare toevoeging, dus `schema_versie`
gaat van `1.0` naar `1.1` en niet naar `2.0`. `docs/json-schema.md` beschrijft het veld en
de nulmetingmeldingen; de twee drifttests bewaken dat het document de velden en de versie
blijft noemen.

### BO-29 Twee objectlagen met een status, en wat daarvoor van de kaart verdwijnt

**Context.** De GeoPackage had zes featurelagen, waarvan drie over dezelfde riolering
gingen: `putten`, `strengen`, `mechanisch_riool` en daarnaast `meldinglocaties` met een
punt per melding. Voor de eindgebruiker in QGIS moeten dat twee objectlagen worden, met de
gebreken *op* het object (issue #13).

**Besluit.** `putten` (punt) en `strengen` (lijn) blijven over. Elk object draagt `status`
-- vier waarden waar de symbologie op filtert -- en `popup_html`, de voorgebakken
hoverpopup. `mechanisch_riool` gaat op in de lijnenlaag met status `grijs`;
`meldinglocaties` vervalt.

**Er komt een grijze ring om het gebied.** Het issue noemt bij `grijs` letterlijk "object
in de schil (niet de kern)", en dat kan alleen als er iets naast de kern in de laag staat.
Het weglaten laat de kaart bij de gebiedsgrens ophouden alsof daar niets ligt.

*Herzien na codereview:* de ring is `Analyseset.buffer` en **niet** de hele schil. De
schil bevat naast de buffer ook de samenhangende vrijvervalcomponent waar de kern in ligt,
en die is op de buurt Kattouw 12.106 objecten bij een kern van 507. Elk van de tachtig
buurtbestanden zou dan het net van de halve gemeente als grijze achtergrond meesturen, met
een popup van bijna een kilobyte per object, en hetzelfde object zou groen zijn in zijn
eigen buurtbestand en grijs in dat van de buurman. De buffer is precies wat een lezer om
zijn gebied heen ziet liggen en is naar constructie begrensd: op Kattouw 79 objecten.

De ring komt uit `run.analyseset` en niet uit "alles wat niet in de kern ligt": een run
die met `beperk_tot_studiegebied` op de volledige export is afgebakend heeft geen
analyseset, en dan hoort het bestand bij de grens op te houden zoals het altijd deed.

**`status` telt systemische meldingen niet mee.** Dit is de scherpste keuze van dit issue.
Op De Wolden draagt de nulmeting 68.882 systemische meldingen op 105.963; zouden die
meetellen, dan is vrijwel elke put rood en zegt de kaart niets meer. De bestaande kolommen
`ergste_ernst`, `n_fout` en `n_waarschuwing` doen het al zo, en om precies deze reden.
Gevolg dat je moet kennen: een object waarvan *alle* meldingen systemisch zijn krijgt
`groen`. Dat betekent hier "geen gebrek dat dit object van zijn buren onderscheidt", niet
"in orde". Twee dingen vangen dat op: `n_systemisch` blijft gevuld, en `popup_html` noemt
de systemische meldingen met zoveel woorden.

**Herzien na codereview: grijs wint niet van een gebrek.** De aanname in het issue dat
mechanisch riool ongetoetst blijft, klopt niet: TOP-010 en TOP-011 draaien er wel op en de
SHACL-nulmeting sowieso. Op de Koekangerveld-run droegen 17 van de 20 mechanische strengen
een melding, en 48 van de 874 meldingen stonden op een object dat de kaart grijs verfde.
Zouden die grijs blijven, dan beweert de kaart dat er niets bekeken is terwijl er fouten op
staan -- en sinds `meldinglocaties` verviel is er geen tweede plek meer waar ze wel
zichtbaar zijn. `grijs` betekent daarom: niet beoordeeld **en niets gevonden**. Wat er wel
gevonden is kleurt het object, en de popup zegt "Maar deels beoordeeld" met de reden. Op
de eindronde over twee buurten: nul grijze objecten met een melding.

**En de popup zet de niet-systemische meldingen vooraan.** Zonder die sorteersleutel kon
een rood object vijf systemische nulmetingmeldingen tonen en de fout die hem rood maakte
achter "en nog N andere" verstoppen -- 6 van de 44 gekleurde objecten op de
Koekangerveld-run. Er staat sindsdien ook een voetnoot onder de popup die zegt hoeveel
meldingen niet meetellen in de status en waarom; zonder haar leest een groene kop met
drie rode kruisen eronder als een tegenspraak.

**Verworpen: een vijfde status.** Het issue vraagt precies vier waarden, en elke waarde
erbij is een regel erbij in elke QML. De reden waarom een object buiten de beoordeling
viel -- mechanisch riool of de ring -- staat daarom in de popup en niet in een eigen
kolom.

**Bewust verlies.** Met `meldinglocaties` verdwijnen twee dingen van de kaart: de exacte
foutlocatie op een lijn (het snijpunt van een kruising, het midden van een streng) en het
naloopwerk in een kaal GIS-pakket zonder joins. De meldingen blijven volledig in de tabel
`meldingen`, en die tabel kreeg de kolommen `x` en `y` met diezelfde foutlocatie -- anders
zou hij stilzwijgend uit de GeoPackage verdwijnen terwijl de CSV en de JSON hem wel
dragen. Wie de punten terug wil, maakt er in QGIS een geometriegenerator van.

**`popup_html` is een fragment, geen document.** Geen `<style>`-blok en geen vaste breedte:
die staan een keer in de maptip van de QML (issue #15). Op De Wolden zou een stijlblok per
rij de GeoPackage tientallen megabytes groter maken zonder dat er iets bij komt. De inhoud
wordt geescaped -- labels en boodschappen komen uit de brondata en mogen de popup niet
kunnen breken.

**De tellingen in `gwsw_run`.** `n_putten` en `n_strengen` betekenen wat ze altijd
betekenden: het aantal rijen dat er werkelijk in staat. Doordat de lijnenlaag nu ook
mechanisch riool en de ring bevat, zijn dat er meer dan voorheen; `n_mechanisch` telt
hoeveel van die lijnen mechanisch zijn. Er komt geen kolom bij: wie het per status wil
weten, telt `select status, count(*) from strengen group by status`.

**De kolom `gebied` noemt het gebied van deze uitvoer, niet dat het object erin ligt.**
Een ringobject draagt dus de naam van de buurt waar het naast ligt. Dat is dezelfde
betekenis als in `meldingen.gebied` en `gwsw_run.gebied` -- de kolom hoort niet in de ene
laag iets anders te zeggen dan in de andere. Waar een object werkelijk ligt, staat in
`status`: `grijs` met "ligt naast het studiegebied en niet erin" in de popup.

### BO-30 De symbologie wordt opgebouwd, en de SVG's van de SLD's blijven buiten beeld

**Context.** Issue #14 vraagt GWSW-conforme symbolen waarvan alleen de kleur de
analysestatus draagt, met regelstructuur objecttype x status. Issue #15 vraagt een maptip
in dezelfde bestanden. De symbolen zouden uit de PDOK-SLD's in `data/gwsw_opmaak/` komen.

**De SVG's zijn er niet.** Die SLD's verwijzen hun beeld als `ExternalGraphic` naar
`https://data.gwsw.nl/img/*.svg`; de bestanden zelf zijn niet meegeleverd. Ophalen zou dit
pakket van een netwerkbron afhankelijk maken en symbolen van een derde in onze uitvoer
bakken, en een QML in `layer_styles` moet zelfstandig reizen. Het issue voorziet dit geval
en schrijft de uitweg voor: hertekenen als eenvoudige marker in de GWSW-vorm. De SLD's
blijven wel de bron voor de *indeling* -- welk type welk symbool krijgt en welke typen er
een delen -- en elke regel in `stijlen/symbolen.py` noemt de SLD-regel die hij vervangt.

**De QML's worden opgebouwd in plaats van geschreven.** Objecttype x status levert met de
44 knoop- en 37 verbindingstypen in de symbolentabel 225 bladregels voor de putten en 190
voor de strengen op, elk met een eigen symbool: samen ruim vierduizend regels XML. Met de hand onderhouden zou de typenlijst
op twee plekken zetten, en een tikfout in een markernaam trekt de kaart stil leeg -- QGIS
maakt van een onbekende vorm zonder morren een cirkel. De tabel plus een opbouwer staat in
`src/nlriochecker/uitvoer/stijlen/symbolen.py`, dus de stijlen blijven waar het issue ze
wil hebben. `bouwwerken.qml` en `waterdelen_zonder_zinker.qml` blijven onveranderde
bestanden.

**Een stijl draagt alleen de typen die in zijn laag staan.** Dat kwam uit de codereview,
en het is geen zuinigheid maar noodzaak: met de volledige tabel toont de lagenboom van
QGIS 225 legendaregels voor de putten en 193 voor de strengen, op een laag met zes
voorkomende objecttypen. Dat is geen legenda meer maar een muur -- precies wat de
handmatige QGIS-controle uit het issue zou hebben laten zien en wat de PyQGIS-test in zijn
eerste vorm niet zag. De stijl reist mee in het bestand waar hij bij hoort, dus hij hoeft
alleen te dragen wat erin zit; op Kattouw levert dat 35 respectievelijk 38 legendaregels.
Een type dat er later bij komt valt in het vangnet.

**Ook de statuskolom heeft een vangnet.** Een waarde die de vier niet is zou door geen
enkele regel geraakt worden en dus onzichtbaar zijn. Onbereikbaar zolang
`objectkaart.bepaal_status` de bron is, maar onzichtbaar is een stiller gebrek dan een
verkeerd symbool, en het objecttype kreeg om dezelfde reden zijn vangnet.

De waarborg is de PyQGIS-test: hij laadt de GeoPackage in een echte QGIS, past de
default-stijl toe, laat QGIS de markervorm van elk symbool terugcoderen om hem met de
tabel te vergelijken, en telt de legendaregels. Dat vangt precies de fouten die een blik
op het scherm mist -- en de kaart is tijdens de bouw ook een keer echt gerenderd, wat een
pijl opleverde die de putsymbolen overstemde.

**Kleur is van de status, en de legenda zegt wat groen betekent.** Het GWSW en de
PDOK-SLD onderscheiden leidingsoorten met kleur; die is hier aan de status vergeven. Voor
verbindingen blijft dus alleen lijndikte en streepjespatroon over, en daarmee zijn zestien
typen niet uit elkaar te houden. Elk type houdt wel zijn eigen regel met zijn eigen
legendalabel -- de legenda blijft volledig -- maar verwante typen delen een lijnstijl,
zodat het kaartbeeld de families toont: vrijverval, mechanisch, aansluiting, drain, duiker,
berging, loos. De legenda van groen zegt "geen eigen gebrek" en niet "in orde", want een
object waarvan alle meldingen systemisch zijn is groen (BO-29).

**Hoofdletterongevoelig filteren.** De De Wolden-export schrijft
`DwaPerceelaansluitleiding` waar de PDOK-SLD `DWAPerceelaansluitleiding` noemt.
Hoofdlettergevoelig filteren zou zulke objecten stil in het vangnet laten vallen, dus de
filters vergelijken op `lower("objecttype")`.

**De maptip is een expressie van een regel.** `[% "popup_html" %]`, met daaromheen een
stijlblok en een `<div style="width:300px">`. De vaste breedte houdt het popupframe stil in
plaats van bij elk object te herschalen. Het stijlblok staat in de QML en niet in de kolom:
per rij herhaald zou het op De Wolden tientallen megabytes aan de GeoPackage toevoegen
zonder dat er iets bij komt. Geen live joins of relations -- die reizen niet mee in
`layer_styles` -- en geen webfont of afbeelding-URL.

`styleCategories` moet `MapTips` expliciet noemen. Staat er alleen `Symbology`, dan leest
QGIS het `mapTip`-element niet terug uit `layer_styles`, blijft de popup leeg, en meldt
niets. Dat is met PyQGIS vastgesteld op deze uitvoer.

**De handmatige QGIS-controle is vervangen door de PyQGIS-test.** Die laadt de stijl
echt, controleert dat elke regel een symbool heeft, dat elke expressie naar een bestaande
kolom verwijst, dat de markervormen zijn wat de tabel zegt, en dat de maptipexpressie op
een echte feature HTML oplevert in plaats van een letterlijke `[% ... %]`. Dat toetst
harder dan een blik op het scherm; wat het niet toetst is of het er goed uitziet, en dat
blijft aan de gebruiker.

### BO-31 Het bevindingenrapport leest van gebied naar detail

**Context.** Het rapport opende met "Checkbevindingen <dataset>" en somde daarna per check
de meldingen op. De lezer -- beheerder of management -- wil eerst weten over welk gebied
het gaat, wat erin ligt en of het voldoet, en pas daarna het detail (issue #16).

**Besluit.** De volgorde is onderdeel van de uitvoer: titel met de gebiedsnaam, aantallen,
managementsamenvatting, rode draad, verantwoording, en dan het detail in twee
herkomstblokken -- eerst de GWSW-nulmeting, dan de eigen checks, elk met de fouten voorop.

**De aantallen tellen de kern, niet de schil.** De contextschil zit in de dataset van de
run omdat de netwerkchecks hem nodig hebben, maar er wordt niet over gerapporteerd. Hem
meetellen zou de aantallen laten afwijken van de bevindingen eronder; hij staat als
voetnoot. De meters zijn de **getekende** lengte en niet het kenmerk `LengteLeiding`: de
tabel hoort te zeggen wat er op de kaart ligt, en wijken de twee af dan is dat ATTR-009.

**Een vinkje betekent nul fouten, en zwijgt niet over waarschuwingen.** Vorm: "12 fouten
(waarvan 9 systemisch), 4 waarschuwingen (0 systemisch)". Een regel die vierhonderd
waarschuwingen weglaat leest als "niets aan de hand".

**Per CFK een oordeel, ook binnen een deelset.** Het issue schrijft voor dat de CFK-regels
bij een `--cfk`-deelset de toestandstekst uit `Meetbereik` tonen, "want er is niet
gemeten". Die reden gaat niet op voor een klasse die *wel* in de deelset zat: daar is
gemeten en valt er iets te oordelen. De regel volgt daarom de reden en niet de letter: een
gekozen klasse krijgt haar vinkje of kruisje, een niet-gekozen klasse de toestandstekst.
Het voorbehoud over de deelset als geheel staat al als markering boven het rapport (BO-7),
dus er gaat niets verloren.

**De klassen staan in de volgorde van de projectconfiguratie** (gesorteerd), niet in de
volgorde waarin het issue ze opsomt: zo krijgt een project met andere klassen dezelfde
opzet zonder dat er iets in de code hoeft te veranderen.

**De nulmeting per vorm, niet per melding.** De SHACL-vormen zijn er honderden en de
meldingen op De Wolden ruim honderdduizend; een lijst daarvan is geen rapport maar een CSV.
Wat een lezer nodig heeft is welke eis waar de mist in gaat, hoe vaak, en welke
conformiteitsklassen hem stellen. De losse meldingen staan in `bevindingen.csv`, in de
JSON en op de kaart.

**De rode draad schuift mee naar voren.** Hij zegt wat de bevindingen samen betekenen, en
dat is wat een lezer na de vier regels van de samenvatting wil weten -- niet pas achter de
tabellen.

**`stelseltypen` verhuist naar `uitvoer/omvang.py`.** Zowel de aantallentabel als de
GeoPackage heeft hem nodig; twee kopieen zouden op een dag verschillende stelsels aan
dezelfde put toekennen.

### BO-32 De GWSW-vocabulaire-index gaat mee in de repository

**Context.** `tests/test_gwsw_vocabulaire.py` toetst elke GWSW-naam die dit pakket gebruikt
tegen de ontologie. Die ontologie (`data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl`, 2,6 MB)
staat buiten versiebeheer, samen met de rest van `data/`. Gevolg: op de CI-runner sloeg die
test 140 van zijn 142 gevallen over -- precies de stilte die issue #30 wilde opheffen.

**Besluit.** Er komt een afgeleide in versiebeheer: `data/gwsw-vocabulaire-index.json`,
geschreven door `scripts/maak_gwsw_index.py`. Ze draagt per GWSW-naam zijn `rdf:type`s en zijn
directe superklassen, en niets meer -- genoeg om te beantwoorden of een begrip bestaat, of het
in de juiste collectie zit, en welke klassen onder een wortel hangen. Nu 285 kB bij 3.316
termen en 2.078 klassen met een superklasse, samen goed voor 2.124 subklasserelaties. (Dit
laatste getal stond hier eerst als "2.078 subklasserelaties": het script drukte het aantal
sleutels van `subklasse_van` af onder het label van het aantal kanten. Een klasse mag meer
dan een GWSW-ouder hebben: 42 klassen hebben er meerdere, samen goed voor 46 kanten boven
het aantal sleutels. Script en getal zijn rechtgezet.)

**Licentie is geen bezwaar.** De GWSW-ontologie staat onder CC0
(https://stichtingrioned.github.io/GWSW_Ontologie_RDF/); herdistributie, ook van een
afgeleide, is vrij en verplicht ons tot niets. De afweging gaat dus over bestandsgrootte en
onderhoud, niet over rechten.

**Bestandsgrootte.** 285 kB tekst met een regel per term is te overzien in een repository die
verder alleen broncode draagt, en de opmaak is met opzet diffbaar: een nieuwe GWSW-versie
levert een leesbare lijst toevoegingen op in plaats van één regel van tienduizend tekens.
De hele TTL tracken (2,6 MB, en de ontologie is niet het enige bestand in die map) zou de
grens over gaan waar `data/` juist voor buitengesloten is.

**Onderhoudsmodel.** De index wordt nooit met de hand bijgewerkt. Zet de auteur een nieuwe
ontologie neer, dan draait hij `uv run python scripts/maak_gwsw_index.py` en commit hij het
resultaat; `CLAUDE.md` en `README.md` zeggen dat op de plek waar hij kijkt.
`test_index_volgt_de_ontologie` vergelijkt de hele bestandstekst met een vers geparseerde TTL
en `test_indexversie_staat_in_claude_md` houdt de `versie=`-regel van de index gelijk aan de
GWSW-versie in `CLAUDE.md` -- die tweede draait ook op CI, want beide bestanden zijn getrackt.

**Dat de drifttest alleen lokaal draait is geen ongedekt gat.** De enige die de index kan
laten verouderen is de auteur die een nieuwe ontologie neerzet, en dat is dezelfde persoon op
dezelfde machine die als enige die test draait. `scripts/uitgave.py` draait `uv run pytest -q`
als uitgavepoort en `TAKVOORWAARDE` dwingt die poort af op `main`: een verouderde index kan
geen uitgave overleven.

**Eén restrisico, eerlijk benoemd.** Een term die een volgende GWSW-versie hernoemt of naar een
andere collectie verplaatst blijft gewoon valideren tegen de 1.6-index tot die vervangen is.
Nieuwe namen vallen luid om, hernoemde niet. Daarom moet `CLAUDE.md` gezaghebbend blijven over
welke GWSW-versie leidt, en bewaakt `test_indexversie_staat_in_claude_md` dat de twee niet elk
hun eigen versie gaan dragen.

**Alternatieven.** De TTL zelf tracken (verworpen: te groot, en dan verhuist de discussie naar
de rest van `data/`). De ontologie bij data.gwsw.nl ophalen in CI (verworpen: `CLAUDE.md`
verbiedt een automatische versiecontrole tegen die bron expliciet, en het maakt de suite
afhankelijk van een netwerkdienst van een derde). De test op CI laten overslaan (verworpen:
dat wás de toestand die #30 opheft).

### BO-33 Overnamepunt staat in `afvoer_eindpunt`; Gemaal en Pompunit zijn een erkend noodverband

**De klasse bestaat.** `data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl` (versie 1.6) draagt
op regel 31892:

```turtle
gwsw:Overnamepunt rdfs:label "Overnamepunt"@nl;
    rdfs:seeAlso "[NEN 3300:1996] locatie waar de overdracht plaatsvindt van het water uit de
                  riolering aan de beheerder van de afvalwaterzuiveringinrichting"@nl,
                 "[IRIS-RIOKEN:2012] Het punt waar de verantwoording over het afvalwater
                  overgaat van een gemeente/bedrijf op het waterschap of omgekeerd ..."@nl;
    skos:altLabel "Afgiftepunt"@nl, "Inprikpunt"@nl, "Overdrachtspunt"@nl;
    skos:scopeNote gwsw:Cof_BAS, gwsw:Cof_PLI, gwsw:Cof_DMO;
    a owl:Class;
    rdfs:subClassOf gwsw:Aansluitpunt, ... .
```

`Aansluitpunt` is een `Knooppunt`-subklasse, dus `Overnamepunt` staat op de **orientatie**,
net als `Lozingspunt`. `grep "rdfs:subClassOf.*gwsw:Overnamepunt"` levert niets: de klasse
heeft zelf geen subklassen, dus haar subklasse-afsluiting is zij alleen. Ze staat ook in
`data/gwsw-vocabulaire-index.json` als `owl:Class`. Ze ontbreekt in `Ontologie_GWSW_Mds.ttl`
en `Ontologie_GWSW_Hyd.ttl`, maar die dragen conversiedatum 20210920 en zijn ruim vier jaar
ouder dan het totaalbestand; daar valt geen modelleerkeuze uit af te lezen.

**Eerdere vastlegging was fout, en dat is de aanleiding.** `checks.toml` schreef in een
commentaar dat `Overnamepunt` "niet als klasse in de GWSW-ontologie" bestaat, en open punt 6
van het checkregister herhaalde dat. Onjuist, en het is precies de verwisseling waar
`CLAUDE.md` voor waarschuwt: "bestaat de klasse in de ontologie" en "komen er instanties voor
in deze dataset" zijn twee vragen met verschillende antwoorden en tegengestelde ingrepen. Een
ontbrekende klasse zou een gat in ons model zijn; ontbrekende instanties zijn een gat in de
aanlevering. Het tweede is hier het geval.

**De instanties ontbreken.** `grep -c "gwsw:Overnamepunt\b" data/gwsw_orox_ttl/dewolden_orox.ttl`
geeft **0** -- geen `rdf:type`, geen verwijzing. De export van De Wolden kent geen enkel
overnamepunt. (Hetzelfde beeld als bij `VerbeterdGescheidenStelsel`, zie #17.)

**Besluit.** `Overnamepunt` gaat in `[klassen] afvoer_eindpunt`, en `Gemaal` en `Pompunit`
blijven er voorlopig naast staan als **erkend noodverband**. De lijst is daarmee
`["Overnamepunt", "Gemaal", "Pompunit"]` in `src/nlriochecker/checks.toml` en in
`configs/dewoldenhoogeveen.toml`.

**Waarom `Overnamepunt` erbij, terwijl het vandaag niets doet.** Nul instanties betekent nul
verandering in de uitkomst -- geverifieerd, zie hieronder. Maar zodra een gemeente ze wel
levert werkt NET-001 meteen goed, zonder dat iemand deze redenering opnieuw moet voeren. En
het maakt de lijst leesbaar als wat ze is: één klasse die de rol dekt, plus twee die haar
vervangen zolang ze leeg blijft.

**Waarom `Gemaal` en `Pompunit` niet nu al weg kunnen.** Er is in De Wolden geen enkel
overnamepunt om te bereiken. Ze eruit halen zou NET-001 élke vuilwater- en gemengde streng
laten melden -- 9.062 bevindingen die niets over de data zeggen en alles over onze lijst. Dat
is het geval waar de huisregel voor waarschuwt: duizenden bevindingen wijzen op een
modelleerfout in de engine, niet op duizenden gebreken. Inhoudelijk is de brug ook niet
willekeurig: een vrijvervalstreng die op een drukrioleringspomp eindigt gaat daar het
mechanische stelsel in, en dat is in deze export de plek waar het vrijvervalnet ophoudt.

**De richting staat wel vast: ze moeten er allebei uit.** Een gemaal is geen overdrachtspunt
maar een knik in het stelsel; de NEN 3300-definitie hierboven legt de overdracht bij het
overnamepunt. `Pompunit` valt onder hetzelfde verhaal. Dit is een surrogaat, geen model.

**Het loslaatcriterium is meetbaar.** #22 voegt een rapportregel toe die toont wélke klassen
als afvoereindpunt gelden en hoeveel instanties er van elk gevonden zijn. Zolang die regel
voor `Overnamepunt` nul toont staat zwart op wit in het rapport dat de uitkomst van NET-001
op een surrogaat rust; zodra hij boven nul komt is de vraag rijp. Dat `Overnamepunt` daar
vandaag als nul verschijnt is de bedoeling van deze toevoeging, geen bijwerking.

**Wat hier expliciet niet besloten wordt.** Op welk moment `Gemaal` er precies uit gaat -- bij
het eerste overnamepunt in de data, of pas bij een af te spreken aandeel van de stelsels --
is een domeinoordeel met 9.062 bevindingen eronder en ligt bij de auteur. Het staat als vraag 3
van issue #47.

**Nagekomen (issue #47, vraag 3).** De auteur heeft het criterium bevestigd: `Gemaal` (en
`Pompunit`) blijven in `afvoer_eindpunt` zolang `Overnamepunt` nul instanties heeft, en gaan
eruit zodra dat aantal boven nul komt -- niet eerder, niet op een aandeel van de stelsels. Het
meetbare criterium uit deze BO is daarmee ook het besliscriterium. RVZ-006 (issue #23) bouwt
op deze ongewijzigde lijst voort.

**Hoe is vastgesteld dat er niets verschoof.** Niet met een gerichte run: `afvoer_eindpunt`
gaat behalve in NET-001 ook op in `ClassRoots.netwerkknopen`, en die rol draagt de hele
netwerkgraaf. Daarom een volle `toets` op De Wolden (`--dataset dewolden_orox.ttl
--ontologie Ontologie_GWSW_Totaal.ttl`, zonder `--shacl`, `--bronnen` en `--studiegebied`),
vóór en na. Uitkomst: 35.370 meldingen over 48 checks, geen enkele check beweegt, en de
35.370 rijen van `bevindingen.csv` zijn over alle kolommen behalve `RunDatum` identiek.

### BO-34 Met "IT-stelsel" bedoelen wij hier `Infiltratiestelsel`; NET-007 blijft voorlopig op de leidingen

**De klassen bestaan.** `checks.toml` schreef dat de ontologie geen klasse "IT-stelsel" kent.
Onjuist. `Ontologie_GWSW_Totaal.ttl` (versie 1.6) draagt vier kandidaten:

| regel | naam | label | `rdfs:subClassOf` |
|---|---|---|---|
| 38844 | `DIT_riool` | "DIT-riool" | `VrijvervalRioolleiding` |
| 38875 | `DT_riool` | "DT-riool" | `VrijvervalRioolleiding` |
| 39918 | `Infiltratiestelsel` | "Infiltratiestelsel" | `Rioolstelsel` |
| 38865 | `DrainageInfiltratieTransportStelsel` | "Drainage/infiltratie transportstelsel" | `Infiltratiestelsel` |

Alle vier `a owl:Class`, alle vier in `data/gwsw-vocabulaire-index.json`.

**Welke klasse wij eronder verstaan; het register zegt het niet.** Het checkregister noemt
NET-007 alleen bij titel en definieert de term "IT-stelsel" nergens, dus dit is een
afleiding van ons en geen registerfeit. NET-007 heet "IT-stelsel zonder drempel" en redeneert
over een stelsel, niet over een leiding. Dat is `Infiltratiestelsel`; het
`DrainageInfiltratieTransportStelsel` is daar een subklasse van en valt dus binnen dezelfde
subklasse-afsluiting. `DIT_riool` en `DT_riool` zijn `VrijvervalRioolleiding`-subklassen: die
benoemen de buis, niet het stelsel, en zijn hier het verkeerde niveau.

**Besluit: NET-007 blijft voorlopig de afleiding uit de infiltratieleidingen gebruiken.** De
check leest een zwak samenhangend deel met infiltratieleidingen (`[klassen] infiltratie`,
nu `["Infiltratieriool"]`) als IT-stelsel. Dat blijft zo, en het commentaar in `checks.toml`
zegt voortaan waarom: niet omdat de klasse ontbreekt, maar omdat **de engine de stelselboom
uit de export nergens leest.**

**Waarom niet meteen overgaan.** Niet omdat onduidelijk zou zijn welke van de twee lezingen
gelijk heeft: op deze data geven ze hetzelfde. De export modelleert stelsels wel degelijk als
objecten -- 13 `rdf:type gwsw:Infiltratiestelsel` (naast 57 `Vuilwaterstelsel`, 55
`GemengdStelsel`, 48 `Hemelwaterstelsel` en 4 `Drainagestelsel`), en die dertien dragen samen
687 `hasPart`-leden, waaronder **alle** 340 `Infiltratieriool`-instanties en geen enkel
infiltratieriool daarbuiten. De graafafleiding en de `hasPart`-boom wijzen hier dus dezelfde
strengen aan. Dat NET-007 op alle 340 uitkomt heeft trouwens een derde oorzaak:
`[klassen] drempel = ["Overstortdrempel"]`, en die klasse heeft in De Wolden nul instanties en
in de ontologie geen subklassen, dus de drempelverzameling is leeg en elk infiltratieriool
wordt onvoorwaardelijk gemeld. Dat is een bevinding op zichzelf en ligt buiten deze BO.

De reden om te wachten is dus een engine-feit en geen datavraag: **de engine leest de
stelselboom nergens.** Overgaan betekent NET-007 zijn graafanalyse laten inruilen voor een
`hasPart`-boom die verder geen enkele check kent -- een verbouwing van hoe dit pakket stelsels
leest, niet een regel in een klassenlijst. Dat bredere gat staat in #17, en omdat beide
lezingen vandaag dezelfde 340 opleveren is de overgang daar een aparte en veilige ingreep.
Deze BO legt de afleiding vast als bewuste keuze met een vervaldatum, niet als de laatste
stand.

**Wat dit besluit niet is.** Geen afwijking van GWSW in de zin van "wij kennen dit begrip
niet". De begrippen zijn erkend en staan hierboven met regelnummer; wat we uitstellen is het
gebruik van de stelselobjecten door de engine.

### BO-35 `Metselwerk` blijft voorlopig als putmateriaal staan: een bewuste, tijdelijke tolerantie

**Wat er feitelijk staat.** `src/nlriochecker/plausibiliteit.toml` noemt in alle drie de
regels van `[[leiding_put_materiaal]]` de waarde `Metselwerk` als verwacht putmateriaal.
Die waarde bestaat in de GWSW-ontologie, maar niet als putmateriaal: `gwsw:Metselwerk`
draagt `a gwsw:MateriaalLeidingColl` (regel 53856-53864 van
`data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl`, versie 1.6). `MateriaalPutColl` kent hem
niet; die collectie heeft `MetselwerkBaksteen`, `MetselwerkBepleisterd` en
`MetselwerkOnbepleisterd`. Geen legale export kan dus `gwsw:Metselwerk` op een put
schrijven.

**Waarom dit een BO is en geen configcommentaar.** Dit is een afwijking van de eerste regel
van `CLAUDE.md` -- "GWSW is leidend" -- en die regel zegt zelf dat zo'n afwijking als
BO-nummer in dit bestand hoort en *"niet als commentaar in een configbestand"*. Het
onderscheid met de andere twee openstaande vragen uit de weekendrun is dat deze regel
gedrag draagt. `AHN5` in `[vulwaarden] uit_hoogtemodel` is **inert**: `WijzeVanInwinningColl`
stopt bij `AHN4`, geen export kan die waarde schrijven, dus de regel doet vandaag niets.
`Metselwerk` doet wel iets, want de export schrijft de waarde wel.

**De data.** In `data/gwsw_orox_ttl/dewolden_orox.ttl` dragen **33 putten** een
`MateriaalPut` die naar `gwsw:Metselwerk` verwijst -- op 16.616 `MateriaalPut`-kenmerken,
naast `Beton` 16.215, `PVC` 361, `GewapendBeton` 5 en `PE` 2. Dat de export daarmee buiten
de domeinlijst valt is niet onopgemerkt: alle drie de SHACL-rapporten in
`data/shacl_nulmeting/` tellen precies 33 `MateriaalPut_ref`-regels. De nulmeting meldt het
dus al, per conformiteitsklasse.

**De kosten van beide kanten, gemeten.** ATTR-010 staat op De Wolden vandaag op **0**
bevindingen. Zou `Metselwerk` uit de drie rijen geschrapt worden, dan komt de check uit op
**51 bevindingen over 37 strengen, rakend aan 27 van de 33 putten** (gemeten met de engine
op de volledige export, ontologie `Ontologie_GWSW_Totaal.ttl`, alleen ATTR-010). Dat zijn 51
waarschuwingen op objecten waarvan het gebrek niet in de put-leidingcombinatie zit maar in
de gekozen domeinwaarde -- een gebrek dat de nulmeting al 33 keer per CFK meldt. Laten staan
kost het omgekeerde: een waarde in een projecttabel die het GWSW niet kent, plus een
permanente regel op `BEKENDE_AFWIJKINGEN` in `tests/test_gwsw_vocabulaire.py`.

**Besluit: de regel blijft staan, en dit is geen eindantwoord.** De tolerantie geldt zolang
vraag 2 van issue #47 niet beantwoord is. Dat is een domeinoordeel -- volgt deze tabel de
export of de domeinlijst? -- en het ligt bij de auteur, niet bij de engine. Wat hier
vastligt is alleen dat de afwijking bewust is, dat ze zichtbaar is, en op grond van welke
getallen ze voorlopig geaccepteerd wordt. Het loslaatcriterium is de beslissing zelf, niet
een meting: er is geen drempel die de vraag vanzelf beantwoordt.

**Samenhang met #43.** `verwachte_putmaterialen` mist negen klassen die wél in
`MateriaalPutColl` zitten, waaronder juist `MetselwerkBaksteen`, `MetselwerkBepleisterd` en
`MetselwerkOnbepleisterd`. Worden die drie toegevoegd, dan verandert het argument om de
niet-bestaande `Metselwerk` te laten staan -- een export die netjes `MetselwerkBaksteen`
schrijft heeft de tolerantie niet nodig. #43 en #47 vraag 2 horen daarom in één keer
beslist te worden.

**Wat dit besluit niet is.** Geen uitspraak dat `Metselwerk` niet bestaat: hij bestaat, als
leidingmateriaal, en op de leidingkant van dezelfde tabel staat hij volkomen terecht. De
afwijking zit uitsluitend in het gebruik als *put*materiaal.

**Nagekomen (BO-36, issue #43).** De tolerantie heeft geen drager meer. De tabel noemt sinds
de omkering alleen nog onwaarschijnlijke putmaterialen, en `Metselwerk` staat op geen van
die twee lijsten; de regel op `BEKENDE_AFWIJKINGEN` is daarmee vervallen. Dat is géén
antwoord op vraag 2 van #47 -- de 33 gemetselde putten van De Wolden werden voorheen niet
gemeld en worden dat nu evenmin -- maar het pakket claimt niet langer dat `Metselwerk` een
putmateriaal is, en dat was de afwijking van "GWSW is leidend".

**Nagekomen (issue #47, vraag 2).** De auteur heeft bevestigd dat hiermee niets meer op de
putkant hoeft te gebeuren: de verbodslijst accepteert de drie officiële put-varianten
`MetselwerkBaksteen`, `MetselwerkBepleisterd` en `MetselwerkOnbepleisterd` al, en de
niet-bestaande `Metselwerk` als putmateriaal is met deze BO en BO-36 afgehandeld. Wat open
blijft is uitsluitend de leidingkant (de whitelist op exacte naam, zie BO-36, "Wat deze BO niet
repareert"); dat is een aparte uitbreiding en valt buiten #47.

### BO-36 ATTR-010 noemt wat onwaarschijnlijk is, niet wat toegestaan is

**Wat.** `[[leiding_put_materiaal]]` in `src/nlriochecker/plausibiliteit.toml` heeft geen
veld `verwachte_putmaterialen` meer maar `onwaarschijnlijke_putmaterialen`, en de conditie
in `checks/attributen.py` is meegedraaid. Er zijn nog twee regels in plaats van drie:
`GewapendBeton` en `Metselwerk`, elk met dezelfde acht kunststoffen uit `MateriaalPutColl`
(`PVC`, `PE`, `HDPE`, `GVK`, `Polyester`, `Polypropyleen`, `PitchFibre`,
`UnidentifiedTypeOfPlastics`).

**Waarom.** Een lijst met *verwachte* materialen maakt van elk lid van `MateriaalPutColl`
dat niemand heeft ingetypt een bevinding. Dat waren er 26 van de 30 -- issue #43 telde er
negen, maar `Gres`, `Klei`, `Staal`, `Asbestcement`, `Vezelcement`, de drie gietijzers en
nog negen andere ontbraken net zo goed. Een gemeente die netjes volgens de GWSW-domeinlijst
exporteert kreeg daar een valse W op, en dat is de omgekeerde wereld van "GWSW is leidend".
De verbodsvorm zegt bovendien wat de check werkelijk bedoelt: de enige toelichting die het
blok ooit droeg was *"Een gemetselde streng op een kunststof put is bouwhistorisch
onmogelijk."* Een verbodslijst onderhoudt zichzelf ook: een nieuwe klasse in een volgende
GWSW-versie meldt niets tot iemand besluit dat ze onwaarschijnlijk is.

**Drie keuzes binnen de omkering.**

- **Elke regel houdt precies de uitsluitingen die hij had.** De omkering is bedoeld om
  valse positieven weg te nemen, niet om bestaande meldingen te laten vervallen. `Beton`
  verbiedt daarom zes van de acht kunststoffen: `PVC` en `PE` stonden op zijn oude lijst
  met verwachte putmaterialen en blijven toegestaan. `GewapendBeton` en `Metselwerk`
  verbieden alle acht, want die stonden op geen van beide oude lijsten.
- **`Epoxy` en `Bitumen` staan niet op de verbodslijst**, hoewel het kunststoffen zijn. Dat
  zijn coatings, en juist op een gerenoveerde gemetselde put; ze verbieden zou vals alarm
  geven op precies de oude riolen waar deze check over gaat.
- **ATTR-010 heeft een `notes()` gekregen.** `examined` telt alle vrijvervalstrengen, maar
  vergeleken worden alleen de materialen die in de tabel staan. Zonder die regel leest "0
  bevindingen op 17.603 bekeken objecten" als een schone rekening voor het hele stelsel.
  Op De Wolden meldt hij nu: *5634 van de 17603 strengen dragen een leidingmateriaal
  waarvoor de tabel geen regel heeft en zijn niet vergeleken (PVC 5376, zonder materiaal
  227, Gres 31).* Dat is de huisregel uit `CLAUDE.md` -- wat een check niet bekeken heeft
  hoort in het rapport -- en hij was hier niet nagekomen.

**Gemeten.** ATTR-010 stond op De Wolden op 0 bevindingen en staat er na de omkering nog
steeds op 0, over dezelfde 11.969 vergeleken strengen (volledige export,
`Ontologie_GWSW_Totaal.ttl`, alleen ATTR-010). Het gedrag op deze dataset verandert dus
niet; wat verandert is wat een andere, correcte export krijgt.

**Wat deze BO niet repareert.** De leidingkant van de tabel is nog steeds een whitelist, en
de vergelijking is exact op naam. `MateriaalLeidingColl` kent naast `Metselwerk` ook
`MetselwerkBaksteen`, `MetselwerkBepleisterd` en `MetselwerkOnbepleisterd`, en naast `Beton`
ook `BetonnenSegmenten`, `GespotenBeton` en `VoorgespannenBeton`; geen van die zes heeft een
regel. Een export die ze netjes schrijft komt ATTR-010 dus helemaal niet tegen. Dat is
hetzelfde gat als #43 beschreef, op de andere as. Zes bijna gelijke regels erbij is geen
goede reparatie -- dat vraagt een veld `leidingmaterialen` (meervoud) -- en het is dus een
uitbreiding voor de auteur, niet iets om er stilzwijgend bij te doen. De `notes()` hierboven
maakt het gat vanaf nu zichtbaar in elk rapport.

**Bijvangst.** De enige fixture van ATTR-010 gaf de put `gwsw:Kunststof` als materiaal --
een waarde die `MateriaalPutColl` niet kent. De fixture toetste dus een export die niet kan
bestaan; hij draagt nu `PVC`. Er is een tegenhanger bij gekomen
(`attr010_gresput.ttl`): een betonnen streng tussen twee gresputten, die zwijgt.

**Alternatieven.** De negen klassen uit #43 toevoegen (verworpen: laat zeventien andere
gaten open en herhaalt de fout bij elke volgende GWSW-versie). De whitelist compleet maken
tegen `MateriaalPutColl` met een drifttest erop (verworpen: drie lijsten van ruim twintig
namen die de eigenlijke regel -- geen kunststof onder metselwerk -- juist onzichtbaar
maken). De `Beton`-regel helemaal schrappen omdat hij `PVC` en `PE` toestond (verworpen in
de codereview, en terecht: die redenering stelt "kunststof" gelijk aan "PVC en PE", precies
de denkfout die #43 aanwees. `MateriaalPutColl` kent zes andere kunststoffen, en de check
zou van 11.969 naar 8 vergeleken strengen zijn gevallen zonder dat het rapport dat zei).

### BO-37 ATTR-014 meldt per kenmerk, niet per object; `Finding.systemisch` is een eigen vlag

**Wat.** `checks/attributen.py` heeft een nieuwe check ATTR-014 (F, Consistentie): een kenmerk
dat `hasValue` gebruikt waar de ontologie via een `owl:onProperty`/`owl:allValuesFrom`-restrictie
`hasReference` naar een collectie eist, of andersom. De verwachte property komt uit
`ontologie.verwachte_property`; bij het laden wordt dat over de subklassen van `Kenmerk`
afgeleid tot `GwswDataset.kenmerk_property` -- een klein woordenboek per kenmerktype, hetzelfde
soort afgeleide als `subclasses`, uit `ontology or graph` (dus werkt met inline-fixtures en
`--geen-ontologie`; leeg zonder klassenkennis). De hele ontologiegraaf wordt niet bewaard.
`Finding` draagt nu een veld `systemisch` dat een check zelf kan zetten; `uitvoer/melding.py`
OR't het met de bestaande populatieratio (`_is_systemisch`).

**Waarom generiek, geen WIBONThema-check.** De fout die dit vindt is precies het soort dat de
SHACL-nulmeting per constructie mist: `allValuesFrom` over een property die er niet staat is
vacuously true, en er is geen minimum-kardinaliteit. Een check die alleen naar WIBONThema kijkt
mist dezelfde fout op het volgende kenmerk in de volgende export. De generieke vorm onderhoudt
zichzelf: op De Wolden zijn 509 kenmerktypen tegen hun voorgeschreven property gehouden en is
`WIBONThema` de enige met een tegenspraak -- 23.440 objecten, waarvan 18.363 met de vulwaarde 0.
Nul valse positieven. Was er meer dan een melding geweest, dan stond de check te breed en was
dat gemeld, niet weggedraaid.

**Twee keuzes die het issue expliciet aan de auteur liet.**

- **Een systemische melding per kenmerk, niet 23.440 losse bevindingen.** De fout is per
  kenmerktype hetzelfde verhaal; 23.440 rijen in CSV en JSON zetten zou het kaartbeeld en de
  meldingenstroom overspoelen zonder een scherper signaal. De bevinding wijst geen los object
  aan (`object_uri=""`), draagt de kenmerknaam als label en `systemisch=True`. Objectloze
  meldingen kleuren de kaart al niet en het rapport telt ze al apart (`_zonder_locatie`), dus
  dit sluit aan op bestaand gedrag. `Finding.systemisch` is nieuw omdat de bestaande
  systemisch-vlag een populatieratio is (bevindingen/bekeken > 0,80) die bij een
  aggregaatbevinding niet vuurt; een aggregaat over een heel kenmerk is systemisch van vorm,
  niet van ratio.
- **ATTR-014, geen nieuwe categorie.** De fout gaat over een attribuut, alleen over hoe het
  geschreven is in plaats van over zijn waarde -- een lichte rek van ATTR. Een nieuwe categorie
  had `CATEGORIEEN` in `gpkg.py`, de registerkoppen en de samenvatting geraakt voor een enkele
  check; dat oppervlak weegt niet op tegen de zuiverheid. ATTR-011 is geschrapt en wordt nooit
  hergebruikt; ATTR-014 is het volgende vrije nummer.

**Meebewegende plumbing.** `beperk_tot_studiegebied` liet een bevinding zonder object en zonder
locatie vallen; nu blijft zo'n dataset-brede bevinding in elk gebiedsrapport staan -- dezelfde
regel als `_nul_hoort_erbij` voor een nulmetingbevinding die nergens op uitkwam (BO-12). De
check draait `volledig_bereik`, zodat de telling de hele export beslaat en niet met het
studiegebied meebeweegt. De sleutel van de datasetcache dekt sinds deze BO ook de broncode van
`ontologie.py`, want `kenmerk_property` wordt mee gecachet.

**Wat deze BO niet doet.** Geen tweede laag (thema versus leidingklasse: een duiker die "riool
vrijverval" draagt). Dat is inhoudelijker en discutabeler, en het issue liet het los ("apart of
niet"); het valt buiten deze sessie.

**Gemeten op De Wolden** (volledige export, `Ontologie_GWSW_Totaal.ttl`, alleen ATTR-014):
459.108 kenmerkinstanties met een property-restrictie bekeken, precies een bevinding --
`WIBONThema gebruikt hasValue in plaats van hasReference op 23440 objecten, waarvan 18363 met de
vulwaarde 0`. Op de handgeschreven fixtures: de defectfixtures (beide richtingen) geven een
melding, de correcte (`hasReference`) geeft er geen.

### BO-38 Een dekkingsondergrens van 95%, in beide poorten

**Wat.** De testdekking krijgt een ondergrens van 95% op het totaal, afgedwongen met
`pytest --cov=nlriochecker --cov-fail-under=95`. Die stap draait op CI
(`.github/workflows/toets.yml`) én in de uitgavepoort (`scripts/uitgave.py`,
`DEKKINGSONDERGRENS`) -- de twee blijven "dezelfde poort" (BO-5), nu vijf stappen. Het
meetcommando `uv run --with pytest-cov pytest --cov=nlriochecker` staat nu in `CLAUDE.md`
en `README.md`; `pytest-cov` blijft bewust buiten de dev-groep en wordt per run met
`--with` opgelost (MIT, dus geen licentiebezwaar; het is geen vaste afhankelijkheid).

**Waarom 95%, en waarom ook op CI.** De keuze ging eerst uit van "CI kan de dekking zonder
`data/` niet betekenisvol meten"; dat is nagemeten en bleek onwaar. In de runner-conditie
(een `git worktree` van dev zonder untracked `data/`, `GWSW_QGIS_SITE_PACKAGES` uitgezet)
haalt de suite **96,46%** (287 van 8102 regels gemist), tegen **96,69%** met de volledige
`data/` -- een verschil van circa 0,2 procentpunt en zo'n 58 tests, niet "honderden". De
handgeschreven fixtures dekken vrijwel alle regels; de data-afhankelijke integratietests
voegen nauwelijks unieke dekking toe. 95% ligt dus ruim onder beide getallen en bijt op
een echte regressie, niet op normale schommeling -- op CI net zo goed als lokaal. Daarmee
vervalt de reden om de grens tot de uitgave te beperken, en blijft de invariant uit BO-5
overeind: de grens vangt een regressie meteen bij de dev-commit.

**Een kanttekening voor later.** CI telt regels die alléén data-afhankelijke tests raken
als ongedekt (die tests slaan er over). Vandaag scheelt dat 0,2pp, maar groeit de
EXT/`externedata`-laag met code die alleen met de GIS-bronnen te toetsen is, dan zakt het
CI-getal sneller dan het lokale. Komt CI ooit tegen de 95% aan terwijl een volledige run
ruim boven zit, verlaag dan de CI-grens of splits de twee -- niet vóór dat gebeurt.

**Alleen een totaalgrens.** Geen grens per module: `externedata.py` staat op 87% en zou
meteen ongepland werk vragen. De per-module-cijfers blijven een observatie in de
rondeverslagen.

**Drift bewaakt.** `tests/test_uitgave.py` bindt het getal in de CI-workflow, de
uitgavepoort en `CLAUDE.md` aan `DEKKINGSONDERGRENS`, zodat de drie niet stil uiteen kunnen
lopen en de belofte in de documentatie niet afwijkt van wat de poort afdwingt.

**Alternatieven.** `pytest-cov` in de dev-groep (verworpen: dat overrulet de vastgelegde
keuze om hem eruit te houden, voor iets wat we een paar keer per ronde doen; `--with` lost
hem net zo goed op, ook op CI, met de setup-uv-cache erachter). De grens alleen in de
uitgavepoort (verworpen nadat de meting liet zien dat CI hem net zo goed haalt: dat zou de
invariant breken en een regressie pas bij de uitgave vangen, voor geen winst). Alleen het
commando vindbaar maken zonder ondergrens (verworpen: dan blijft de dekking een meting en
geen belofte -- de kern van issue #54).

### BO-39 De wandruwheid wordt gelezen op een uit de data afgeleide schaal, niet in hele mm

**Wat.** ATTR-017 leest de kenmerken `WandruwheidBinnenboven` en `WandruwheidBinnenonder`
niet als het gehele aantal millimeters dat het GWSW-datatype voorschrijft, maar op een schaal
die uit de data zelf volgt: de lezing (uit `wandruwheid_schalen`, default `[1.0, 10.0]`) met
de minste afwijkingen tegen de C2100-banden per materiaal. Op De Wolden en Hoogeveen wint
schaal 1:10 -- de export noteert de waarde in tienden van een millimeter.

**Waarom dit een afwijking van GWSW is, en waarom ze toch mag.** De hoofdregel in `CLAUDE.md`
is dat GWSW leidend is; een afwijking mag alleen als de auteur ze expliciet en onderbouwd
maakt, en dan hoort ze hier. `gwsw:Wandruwheid hasUnit "mm"` en `Dt_Wandruwheid` is een
`xsd:integer` van 0 tot 99 (`Ontologie_GWSW_Totaal.ttl:29402-29413`, `44106`). Een geheel
getal in millimeters kán de door RIONED geautoriseerde defaultwaarden uit Leidraad Riolering
C2100 tabel B2.1 niet uitdrukken: pvc 0,4 · HPE 0,4 · gres 0,5 worden als integer allemaal 0
of 1. De tienden-conventie is dus geen slordigheid van de leverancier maar de enige uitweg uit
een datatype dat de voorgeschreven waarden niet kan dragen. De auteur heeft beslist dat de
Leidraad hier leidend is (issue #38); onder de tienden-lezing volgt de export van De Wolden en
Hoogeveen die Leidraad exact voor 21.067 van de 22.078 leidingen, en blijven de PE-leidingen
over die de betonwaarde dragen in plaats van de kunststofwaarde.

**Waarom uit de data afgeleid en niet vast op tienden.** Een andere gemeente kan wél in hele
millimeters exporteren, en een vaste deling door tien zou dan elke leiding afkeuren. Door de
schaal per dataset te kiezen (de lezing met de minste afwijkingen) toetst de check beide
conventies correct; bij gelijke afwijkingen wint de eerste kandidaat (1:1, de lezing zonder
herschaling). De gekozen lezing staat in `notes()`, zodat de lezer van het rapport weet welke
schaal gold.

**Wat buiten beeld blijft.** Polypropyleen en Asbestcement kennen geen C2100-waarde en krijgen
dus geen band; hun leidingen worden niet getoetst en `notes()` telt ze. De 49 PP-leidingen die
op De Wolden dezelfde betonwaarde dragen als de PE-leidingen blijven daarmee ongemeld -- een
band bij analogie (0,4 mm, als HPE en LDPE) zou een nieuw domeinoordeel zijn zonder bron, en
dat is aan de auteur.

**Alternatieven.** Een vaste schaalfactor in de config (verworpen: keurt een export in hele mm
af, tenzij het project hem overschrijft -- de data-afleiding doet dat vanzelf). De schaal
hardcoderen op tienden (verworpen: strijdig met "geen hardcoded drempels" en niet overdraagbaar
naar een andere gemeente). PP meenemen op 0,4 mm (verworpen zonder bron; als nevenbevinding aan
de auteur voorgelegd).

### BO-40 `AHN6` staat in `uit_hoogtemodel` als vooruitloop op een latere GWSW-versie

**Wat.** `uit_hoogtemodel` in `src/nlriochecker/checks.toml` en
`configs/dewoldenhoogeveen.toml` noemt `AHN6` in plaats van `AHN5`. Op
`BEKENDE_AFWIJKINGEN` in `tests/test_gwsw_vocabulaire.py` staat het paar
`("AHN6", "WijzeVanInwinningColl")`.

**Waarom.** `AHN6` is de inwinningsbron die dit project gebruikt -- de maaiveldraster is
`AHN6_DeWoldenHoogeveen_DTM.tif` (`configs/dewoldenhoogeveen.toml`, `ahn_dtm`). De GWSW
1.6-ontologie kent hem nog niet: `WijzeVanInwinningColl` stopt bij `AHN4` (geverifieerd,
`Ontologie_GWSW_Totaal.ttl` bevat `AHN`, `AHN1`--`AHN4`, geen `AHN5` of `AHN6`). De waarde
die er tot nu toe stond, `AHN5`, was een even niet-bestaande vooruitloop én bovendien niet
de bron die het project gebruikt.

**Beslissing (issue #47, vraag 1).** De auteur heeft gekozen: het moet `AHN6` zijn, en de
waarde blijft staan als bewuste vooruitloop op een latere GWSW-versie. Dat houdt één
permanent rode term op de uitzonderingslijst, met zijn reden erbij; de drifttest
`test_bekende_afwijking_is_nog_niet_opgeruimd` bewaakt dat de term daar pas afgaat zodra een
GWSW-versie hem kent.

**Waarom een afwijking van "GWSW is leidend" mag.** De hoofdregel is dat GWSW leidend is;
een afwijking mag alleen als de auteur ze expliciet en onderbouwd maakt, en dan hoort ze
hier. Deze afwijking is niet "een begrip verzinnen dat GWSW niet kent voor de toetsing",
maar "de feitelijke inwinningsbron van dit project benoemen terwijl de ontologie nog niet is
bijgewerkt". `uit_hoogtemodel` bepaalt alleen welke inwinningswaarden HGT-001/HGT-002 een
kanttekening geven; een waarde die geen enkel object draagt, verandert geen bevinding.

**Alternatief.** `AHN5` laten staan (verworpen: bestaat evenmin en is niet de gebruikte
bron). `AHN6` weghalen (verworpen: verliest de vermelding van de werkelijk gebruikte bron).

### BO-41 `pyoxigraph` als harde afhankelijkheid voor de TTL-parse

**Wat.** De OroX-dataset wordt niet langer door rdflib's pure-Python `notation3`-parser
ingelezen maar door de Rust-parser van `pyoxigraph` (`pyoxigraph.parse`). De triples worden
daarna in een gewone `rdflib.Graph` overgezet, zodat de checks, de cache en de rest van de
lader onveranderd blijven. `pyoxigraph` is een **harde** afhankelijkheid, niet optioneel:
optioneel zou twee codepaden en twee testmatrices betekenen, en een standaardrun die traag
blijft terwijl snelheid het hele punt is (issue #26).

**Licentie.** `pyoxigraph` staat onder Apache-2.0 — permissief en EUPL-verenigbaar conform
[[BO-3]]. De afhankelijkheid dwingt geen copyleft af.

**Waarom alleen `pyoxigraph`, niet `oxrdflib`.** `oxrdflib` levert een Oxigraph-*store* achter
de rdflib-interface. Twee bezwaren: een Oxigraph-store is niet te picklen
(`cannot pickle 'pyoxigraph.Store'`), waardoor de graafcache in `cache.py` breekt; en het
parsen via `Graph(store="Oxigraph").parse()` bleek in de meting niet sneller dan rdflib zelf
(circa 124 s), want die weg gebruikt de native parser niet. De native `pyoxigraph.parse` doet
de 1,88 miljoen triples in circa 5 s. Daarom parseren we native en zetten we over naar een
gewone `rdflib.Graph`; `oxrdflib` is niet nodig.

**Waarom overzetten en niet de checks op de Oxigraph-store draaien.** De checks doen miljoenen
puntbevragingen (`graph.objects`, `graph.value`, `(s,p,o) in graph`); die tegen een store via
de Python/Rust-grens draaien zou per bevraging trager kunnen zijn dan rdflib's dicts, en zou
de cache en de check-semantiek raken -- een groter project met equivalentierisico, precies wat
het issue afwees. Het overzetten kost eenmalig circa 45 s (Python-invoeging in rdflib's store,
dezelfde kost die de oude parse ook al betaalde), maar houdt alles erna identiek.

**Equivalentie, geverifieerd.** De eis uit issue #26 is dat de uitkomst aantoonbaar identiek
blijft. `bevindingen.json` van een volledige `toets` op De Wolden en Hoogeveen is vóór en na de
omzetting **byte voor byte gelijk** (sha256 `fde7f23a…`), en de `zwaar`-tests houden hun exacte
aantallen (`conduits == 23440`, `nodes == 23485`, `decode_fallback.byte_count == 5`). Dat de
export geen blanke knopen bevat en `pyoxigraph` de lexicale vorm van literalen (ook de
ongeldige `xsd:date "20210830"` in de ontologie) net als rdflib ongemoeid laat, maakt die
gelijkheid mogelijk. Een gewone string-literaal krijgt in de omzetting datatype `None`, net als
rdflib's eigen parser. Let op de grens: een expliciet getypeerde `"x"^^xsd:string` zou rdflib's
parser wél als aparte term bewaren, maar pyoxigraph vouwt die (RDF 1.1) al samen met de gewone
vorm en levert hem niet apart aan -- die is dus niet te reconstrueren. De byte-gelijkheid steunt
er daarom op dat de ingelezen bestanden geen expliciet `^^xsd:string` dragen (nagegaan voor de
totaal-ontologie en de OroX-export), niet op een algemene reconstructiegarantie. Een toekomstige
invoer met zo'n literaal zou de gelijkheid stil kunnen doorbreken; de byte-vergelijking uit de
equivalentie-eis vangt dat.

**Cache-invalidatie.** De cachesleutel bevat al de broncode van `dataset.py` en de versies van
rdflib en shapely; `pyoxigraph.__version__` is toegevoegd, zodat een parser-upgrade de cache
net zo goed ongeldig maakt. Bestaande caches invalideren vanzelf doordat `dataset.py` wijzigde.

**Alternatief.** Een eigen streaming-TTL-lezer (verworpen in het issue: een project op zich,
strijdig met "minimum code dat het probleem oplost"). De rdflib-store-vulling verder pruimen
(een ruimtelijk voorfilter, de graaf snoeien tot de triples die de checks raken) is complementair
en blijft mogelijk vervolg, niet nu.

**Achterhaald (deels).** De opslagkeuze -- overzetten naar een gewone `rdflib.Graph`, met de
eenmalige circa 45 s -- is achterhaald door [[BO-42]]: de store is vervangen door eigen
graafindexen. De parsekeuze (`pyoxigraph` als harde afhankelijkheid) staat.

### BO-42 Eigen graafindexen (`GraafIndex`) vervangen de rdflib-store

**Wat.** `GwswDataset.graph` is geen `rdflib.Graph` meer maar een eigen `GraafIndex`
(`src/nlriochecker/graaf.py`): twee dicts (s→p→objecten en p→o→subjecten), rechtstreeks
gevuld uit de pyoxigraph-stream, met rdflib-termen (`URIRef`, `BNode`, `Literal`) als
munteenheid zodat de checks en alle vergelijkingen ongewijzigd blijven. De rdflib-store
bouwde drie geneste indexen (spo, pos, osp) met per triple dict-in-dict-in-dict-overhead,
terwijl de checks maar een handvol leesbewerkingen doen, allemaal met gebonden argumenten;
de moduledocstring van `graaf.py` draagt het volledige leescontract.

**Gemeten.** Koude toetsrun op De Wolden en Hoogeveen: 107 s totaal waarvan laden 27,9 s
(was 205 s totaal, laden 84,6 s). Warme run 98 s, cache-lezen 2,3 s (was 163 s / 34 s).
Piek-RSS 1,76 GB (was 3,98 GB). De graafpickle in de cache is 91 MB (was 436 MB).

**Cache: picklen, niet herbouwen.** Beide alternatieven zijn gemeten: de gepicklede index
laden kost 5,7 s, hem warm herbouwen uit een nieuwe pyoxigraph-parse 19,9 s. Daarom
pickle't de cache de index; herbouwen verworpen.

**Equivalentie, geborgd.** TDD tegen rdflib's `Memory`-semantiek: `tests/test_graaf.py`
toetst elke leesbewerking uit het contract tegen het rdflib-antwoord op dezelfde triples,
inclusief volgorde (eerste-toevoegvolgorde; de pos-groepering van `subject_objects`) en
dedupe. Daarbovenop is de uitvoer van een volledige `toets` op De Wolden en Hoogeveen
byte-/inhoudsgelijk aan die van vóór de omzetting, koud én warm.

**Cache-invalidatie.** `graaf.py` telt mee in de cachesleutel, naast `dataset.py`,
`geometry.py` en `ontologie.py`: een wijziging aan de termconversie of de volgordegarantie
is net zo goed een andere lader en dus een andere sleutel.

### BO-43 Een watergangkruising is een echte doorkruising van een actueel BGT-waterdeel, zonder drempels

**Wat.** De twee kruisingschecks op BGT-waterdelen (EXT-002, EXT-003) melden voortaan
alleen een *echte doorkruising*. Per (vrijvervalstreng `L`, BGT-waterdeel-polygoon `W`):
doorkruising ⟺ `L` snijdt `W` én beide eindpunten van `L` liggen buiten `W` (`e=0`) én
`L` kruist de rand van `W` minstens twee keer (`k≥2`). EXT-002 meldt die doorkruisingen,
EXT-003 de doorkruisingen waarvan de streng geen kruisingsconstructie (`Zinker`/`Duiker`)
is. Een leiding die alleen binnen de buffer ligt maar `W` niet snijdt (raakt niet), of
die in `W` eíndigt (lozingspunt, `e≥1`), is geen bevinding. De BGT-invoer wordt vooraf
op de actuele versie gefilterd (`eind_registratie` én `termination_date` leeg);
vervallen waterdelen tellen niet mee. Uitgewerkt in issues #58 (invoerfilter) en #59
(meetkunde).

**Waarom.** De oude toets was `distance ≤ ext_watergang_buffer_m` (1,0 m) — nabijheid,
geen doorkruising. Handmatig geclassificeerd op de laatste volledige De Wolden-run (638
gemelde waterdelen): 181 raakten de leiding niet eens, 155 waren lozingspunten, 58 waren
vervallen BGT-versies; slechts 234 waren echte doorkruisingen. De check meldde er 638 waar
er 234 terecht zijn. Een zinker is bovendien een vrijvervalbegrip: mechanisch riool
(pers/druk/vacuüm) gaat onder druk zonder zinker onderdoor, dus die populatie hoort er niet
in — de engine selecteert al op `VrijvervalRioolleiding` (`Infiltratieriool` en
`Overstortleiding` blíjven erin; die zijn vrijverval).

**Geen drempels.** Tien handmatig gelabelde grensgevallen (doorsnijding 0,30–0,50 m,
allemaal "goed") wezen uit dat een minimum-doorsnijding echte doorkruisingen van smalle
greppels wegfiltert, en dat een oevertolerantie overbodig is zodra "moet écht snijden" de
eis is. `e=0 ∧ k≥2` draagt de hele beslissing; `ext_watergang_buffer_m` blijft alleen de
zoekstraal voor kandidaten.

**Alternatieven.** Een oevertolerantie/straddle-correctie voor leidingen die door bronoffset
net náást het waterdeel liggen (verworpen: geen offset-correctie — raakt de leiding het
waterdeel niet, dan valt het eruit). Een minimum-doorsnijding tegen hoek-aantikkingen
(verworpen: filtert smalle-greppel-doorkruisingen weg, gemeten). Historie per check afhandelen
(verworpen: het actualiteitsfilter hoort in het BGT-leespad, zodat álle EXT-checks schone
invoer krijgen — #58).

**Herziening van [[BO-17]].** De daar bewust geaccepteerde `break`-na-eerste-waterdeel in
`_WatergangKruising.kruisingen()` vervalt: de nieuwe toets loopt alle kandidaat-waterdelen per
streng langs en geeft elke echte doorkruising terug. De EXT-001-beperking (alleen het sterkste
bouwwerk) uit BO-17 blijft staan.

**Gemeten uitkomst (2026-08-24).** EXT-002 en EXT-003 melden op De Wolden 319 doorkruisingen op
281 strengen, over 302 unieke waterdelen. Binnen de zoekstraal lagen 924 (streng, waterdeel)-paren:
319 doorkruisingen, 362 die het waterdeel niet raken, 243 lozingspunten en 0 tangentiële gevallen.
244 strengen kruisen één waterdeel, 36 er twee en 1 er drie. De vergelijking met de 234 handmatig
gevalideerde doorkruisingen hierboven gaat niet op: door de `break` droeg de oude run precies één
waterdeel per streng, dus die handmatige ronde beoordeelde een steekproef van één per streng en
nooit de volledige parenpopulatie. Van de 302 waterdelen zaten er 226 in de oude 638 (waarvan er
234 handmatig als doorkruising waren gelabeld) en 76 kwamen door de `break` nooit bovendrijven.
Alle 281 strengen stonden al in de oude run: geen enkele streng is nieuw. Dat de oude verzameling
volgordeafhankelijk was, bleek ook uit de tussenrun met alleen #58: die wisselde 70 waterdelen in
en 119 uit de 638. Het restverschil van 8 (226 tegen 234) is niet verklaard; de waarschijnlijkste
oorzaak is dat een eindpunt precies op de oever als "erin" telt en het paar dus lozingspunt wordt.
Dat is een bewuste, behoudende afwijking van de letterlijke eis "beide eindpunten buiten `W`":
liever een doorkruising missen dan er een melden die er geen is.

### BO-44 HGT-001 waarschuwt vanaf 10 cm AHN-afwijking (inclusief); de banden zijn halfopen en op de millimeter

**Wat.** `ahn_afwijking_waarschuwing_m` gaat van 0,05 naar 0,10 m; `ahn_afwijking_fout_m` blijft
0,25 m. De vergelijking wordt halfopen: HGT-001 meldt `[0,10 – 0,25)`, HGT-002 `[0,25 – ∞)`, zodat
een object nooit beide meldingen krijgt. De afwijking wordt op millimeters afgerond voordat hij
met de drempels vergeleken wordt; dat afgeronde getal is ook wat de melding toont
(`afwijking_m`). Beide checks noemen de gehanteerde drempel in hun toelichting. Uitgewerkt in
issue #63.

**Waarom.** Het checkregister v0.9 zegt "meer dan 5 cm", maar 5 cm ligt binnen de onzekerheid van
de AHN-inwinning zelf: een afwijking van die orde zegt niets over de beheerdata, daar staat
meetruis naast meetruis. Gemeten op de volledige run van 2026-08-24 lag de mediane HGT-001-afwijking
op 0,098 m; de nieuwe drempel ligt dus vrijwel op de mediaan en de helft van de 5811 waarschuwingen
valt weg. De afronding op millimeters is geen cosmetiek: `10,10 − 10,00` is in floating point
`0,0999…`, en zonder afronding zou een put met precies 0,100 m afwijking onder de inclusieve
ondergrens doorglippen terwijl de melding "0,100 m" zou tonen.

**Afwijking van het checkregister.** Dit is een bewuste afwijking van de registertekst; de
registerregels van HGT-001 en HGT-002 zijn bijgewerkt en verwijzen hierheen.

**Openstaand punt voor de auteur.** Draagt deze drempel een externe onderbouwing — een specificatie
die de systematische en stochastische fout van het AHN kwantificeert — of is het een projectkeuze
zonder externe bron? Hier is niets ingevuld en geen specificatiegetal verzonnen; `checks.toml`
gebruikt bij andere drempels de formulering "projectkeuze, geen externe bron".

**Alternatieven.** Alleen de ondergrens inclusief maken (verworpen: een object met precies 0,25 m
krijgt dan HGT-001 én HGT-002). Onafgerond vergelijken (verworpen: de grenstest "0,100 m meldt" is
dan onhaalbaar en band en getoond getal kunnen tegenspreken). Een lichtere categorie voor 5–10 cm
(verworpen: die afwijkingen zeggen niets, dus ze horen niet in de uitvoer).

**Gemeten uitkomst (2026-08-24).** Volledige toets op De Wolden na de wijziging: HGT-001 5811 →
2847 meldingen (kleinste afwijking 0,100 m, grootste 0,249 m), HGT-002 2128 → 2132 (kleinste
0,250 m, grootste 11,150 m). Geen enkel object staat in beide checks. De vier meldingen die op
0,250 m afronden stonden in de baseline nog in HGT-001 en staan nu in HGT-002, dat daarmee tien
meldingen op precies 0,250 m draagt; de 44 die op 0,100 m afronden staan in HGT-001. De getallen
zijn gelijk aan wat de baselinerun op afgeronde afwijkingen voorspelde, dus de nieuwe band is de
enige oorzaak van het verschil.

### BO-45 Een ontbrekende begindatum is een fout per object (ATTR-018), niet een notitieregel

**Wat.** ATTR-018 (F, Compleetheid) meldt per vrijvervalrioolleiding en per put dat `Begindatum`
ontbreekt. Populatie en `examined` zijn die van ATTR-007 (`vrijvervalrioolleidingen` plus
`putten`); mechanisch riool en andere niet-vrijvervalleidingen vallen erbuiten en worden in de
toelichting geteld. De GeoPackage-lagen `putten` en `strengen` krijgen de kolom `begindatum_jaar`
(integer, leeg zonder datum). De tweede notitieregel van ATTR-007, die het gat over de hele
meetset telde, vervalt. Uitgewerkt in issue #61.

**Waarom.** `notes()` gaat per ontwerp alleen naar het Markdown-rapport; een object zonder
aanlegjaar had dus geen spoor in de JSON, de CSV of de GeoPackage en kleurde groen -- "beoordeeld
en niets gevonden". Zonder aanlegjaar is er geen vervangingsplanning, geen levensduurberekening en
geen ATTR-003; dat is een gebrek in de aanlevering en geen signaal, vandaar F. Het jaar en niet de
datum in de kolom, omdat de rest van de code met het jaartal werkt (`Conduit.begindatum_jaar`).

**Gevolg dat je moet kennen.** Op De Wolden en Hoogeveen zijn het ongeveer 9274 bevindingen
(24,2% van 38361; putten 9063 van 20758, strengen 211 van 17603). Dat haalt de systemische
drempel (80%) niet, dus elke bevinding staat los in de CSV en op de kaart; het Markdown-rapport
groeit navenant (`max_bevindingen_per_check = 0`). Afkappen is een keuze voor de auteur, niet
voor de implementatie.

**Alternatieven.** Alleen de kolom (verworpen: een kolom kleurt niets en komt niet in de CSV of
JSON). Een systemische melding in plaats van per object (verworpen: het aandeel ligt onder de
drempel en het gat is per object te herstellen). `Einddatum` erbij (verworpen: dat is ADM-006, en
geen enkel object draagt er een).

**Gemeten uitkomst (2026-08-24).** Volledige toets op De Wolden en Hoogeveen: ATTR-018 meldt 9274
objecten (211 strengen, 9063 putten), niet systemisch -- precies de verwachting. Buiten de toets
vallen 5837 van de 23440 leidingen, waarvan 1703 zonder begindatum. Het Markdown-rapport groeit van
53479 naar 62763 regels (6,7 → 7,5 MB) ten opzichte van dezelfde run zonder ATTR-018; dat is de
enige verandering, want de bevindingentelling per check verschilt verder nergens. (Tegenover de
0.3.0-meting van 24 augustus, 57526 regels en 7,2 MB, is de groei kleiner omdat BO-44 daar 2964
HGT-001-meldingen liet vervallen.) In de GeoPackage staan 11534 lege `begindatum_jaar` op `putten`
en 1914 op `strengen`. Die twee lagen dragen de hele meetset en niet de ATTR-018-populatie: op
`strengen` komen de 1703 leidingen buiten de toets erbij (1703 + 211 = 1914) en op `putten` 2471
knopen die geen put zijn (2471 + 9063 = 11534). Samen 13448 van de 46925 objecten -- exact het
getal dat de vervallen meetsetregel van ATTR-007 gaf.

### BO-46 De lader herstelt de fantoomkoppeling naar hulpstukken en meldt dat; TOP-022/TOP-023 tellen richtingen tegen de GWSW-functie

**Wat.** (1) Wijst geen enkel `hasConnection`-doel van een leidingeinde naar een bekende
orientatie, dan strip de lader de staart `_put` en neemt hij de stam als knoop -- alleen als
die stam een knoop met een `Hulpstukorientatie` is. Het aantal herstelde koppelingen en
hulpstukken staat op `GwswDataset.koppelingsherstel` en gaat als datasetsignaal
`SIG-hulpstukkoppeling` (W, systemisch, zonder object) de meldingenstroom in. (2) TOP-022 (F)
en TOP-023 (W) vergelijken per hulpstuk het aantal richtingen -- verschillende buurknopen plus
losse einden -- met het aantal dat de `gwsw:functie`-restrictie op zijn klasse voorschrijft
(`VerbindenVanTwee/Drie/VierLeidingen` → 2/3/4). De klasse→functie-koppeling komt uit de
ontologie (`GwswDataset.functie_per_klasse`, overgeerfd naar subklassen); alleen de vertaling
van woord naar getal staat in code. Uitgewerkt in issue #60.

**Waarom.** De BrutIS-export koppelt élk leidingeinde op een hulpstuk aan `<hulpstuk>_put`, een
URI die nergens een type of aspect draagt; de orientatie heet `<hulpstuk>_put<n>`. Gemeten:
1122 hulpstukken, 1122 fantoom-URI's, 3024 koppelingen, 3024 strengeinden zonder knoop, 859
strengen met beide einden los, 0 T-stukken met een herkende aansluiting. De nulmeting meldt
hetzelfde (`Knooppunt_Netwerk_conn` 1123×, `EindpuntLeiding_Knooppunt_card` 1846×,
`BeginpuntLeiding_Knooppunt_card` 1178×). Zonder herstel meet een T-stukcheck niets; met een
stil herstel zou het rapport het gebrek in de aanlevering verzwijgen. Richtingen in plaats van
strengen: in Alteveer ligt elke vacuümrichting dubbel (108 knoopparen met meer dan een streng
ertussen, 266 strengen -- nagemeten en juist), en per streng geteld zouden 17 hulpstukken een
ander getal krijgen. Nagemeten valt dat uiteen: negen daarvan (zes strengen, drie richtingen)
zouden ten onrechte melden, de andere acht melden terecht maar met het verkeerde aantal (zes
strengen bij vier of vijf richtingen).

**Twee ID's, niet een.** Het issue nam een ID met F voor te weinig en W voor te veel aan. De
engine en het register kennen per check precies een ernst (`Check.severity`;
`test_ernst_en_dimensie_volgen_het_register`). Daarom TOP-022 voor te weinig (F: er ontbreekt
een leiding, of het is geen T-stuk) en TOP-023 voor te veel (W: waarschijnlijk de verkeerde
klasse).

**Alternatieven.** Ruimer herstellen op naam (verworpen: gokken in een kritiek pad). Het
verwachte aantal in `checks.toml` (verworpen: het staat in de ontologie en zou een tweede
waarheid worden). Een losse streng zonder eind niet meetellen (verworpen: die leiding hangt
wel degelijk aan het hulpstuk; dat haar andere eind los is, is een TOP-002/003-zaak).

**Gemeten uitkomst (2026-08-25).** Na het herstel: 3024 koppelingen naar 1122 hulpstukken
hersteld (1054 T_stuk, 58 Afsluitstuk, 10 Ontstoppingsstuk), strengeinden zonder knoop
3024 → 0 over 2165 strengen, strengen met beide einden los 859 → 0, T-stukken met minstens
een aansluiting 0 → 1054. TOP-022 meldt 224 T-stukken (94 met een richting, 130 met twee),
TOP-023 37 (36 met vier, 1 met vijf); de verdeling over alle 1054 telbare hulpstukken is
1: 94, 2: 130, 3: 793, 4: 36, 5: 1 -- precies de tabel uit issue #60. Losse einden komen
niet voor: alle 3024 herstelde einden hangen aan een hulpstuk. 68 hulpstukken vielen buiten
de toets (58 Afsluitstuk, 10 Ontstoppingsstuk), geteld in de toelichting van beide checks.
Verschuivingen in de andere checks: **geen enkele**. Alleen de drie nieuwe regels kwamen erbij
(TOP-022 +224, TOP-023 +37, SIG-hulpstukkoppeling +1; 167255 → 167517 bevindingen). Dat is
geen toeval en geen fout: de bestaande checks navigeren via `verbonden_knopen` →
`resolve_network_node`, en een hulpstuk is geen netwerkknoop en klimt via `hasPart` ook niet
naar een put -- van de 3024 herstelde einden herleidt er 0 tot een netwerkknoop. De 2165
strengen kregen hun knoop dus terug voor de hulpstuktelling, niet voor de netwerkgraaf.
Daarmee is ook de opmerking uit de review van taak 2 bevestigd: TOP-019 (0 bevindingen voor
en na) krijgt de T-stukken niet als kandidaat. `len(dataset.conduits)` en
`len(leidingen(context))` zijn op deze dataset allebei 23440; het verschil dat de docstring
van `_bouw_hulpstuktelling` noemt (25 om 19) is een eigenschap van het Juinen-voorbeeld, niet
van De Wolden. Onverklaard: niets. Vergelijkingsrun: `uitvoer/issue61/bevindingen.csv`
(2026-08-24 23:42, vóór a975d8d) tegen `uitvoer/issue60/bevindingen.csv`.

### BO-47 Loze leidingen in ketens: ADM-010 voor een keten aan actief riool, ADM-011 voor dode data

**Wat.** Loze leidingen (`LozeLeiding` en subklassen, rol `[klassen] loze_leiding`) die via een
knoop aan elkaar hangen vormen een keten. Per keten, in de administratieve begin→eindrichting:
`inkomend` zijn de niet-loze leidingen die eindigen in een beginknoop van de keten, `uitgaand`
de niet-loze leidingen die beginnen in een eindknoop. ADM-010 (F) meldt *doorgaand* (beide),
*aanvoer* (alleen inkomend) en *afvoer* (alleen uitgaand); ADM-011 (W) meldt *losgekoppeld*
(geen van beide). Melding per loze streng, keten in `cluster_id`, het transitieve aantal actieve
strengen bovenstrooms als detail `bovenstrooms` (zonder invloed op de ernst). Uitgewerkt in
issue #62.

**Waarom.** Een `LozeLeiding` is buiten gebruik; er kan per definitie geen actief riool op
afwateren. In De Wolden en Hoogeveen gebeurt dat in 19 van de 33 ketens, waarvan 3 doorgaand.
Geen enkele check zag het: `LozeLeiding` hangt onder `Leiding` en niet onder
`VrijvervalRioolleiding`, dus alle checks op `klassen.vrijvervalleiding` slaan haar over; de
nulmeting noemt loze leidingen 37 keer, alleen voor attribuutgebreken. Per streng melden en niet
per keten, zodat elke streng op de kaart kleurt; het keten-ID houdt ze in het rapport bij elkaar.

**Twee ID's, niet een.** Het issue nam ADM-010 met F én W aan; de engine en het register kennen
per check een ernst (`Check.severity`, `test_ernst_en_dimensie_volgen_het_register`). Vandaar
ADM-011 voor de losgekoppelde keten.

**Richting.** Altijd de administratieve richting, ongeacht `[netwerk] richting`: dat is de bron
die NET-003 toetst, en een verkeerd gerichte administratie is dáár een bevinding. Ook
`losgekoppeld` is dus richtingsgebaseerd -- een actieve streng die dezelfde put verlaat als de
loze streng sluit in de afvoerrichting niet aan -- en daarom noemt het detail `rakend` de actieve
strengen die een ketenknoop wél raken, tegen de richting in of ernaast; de meldingstekst claimt
niet meer dan de afvoerrichting.

**Alternatieven.** Melden per keten (verworpen: dan kleurt maar een streng). ADM-006 uitbreiden
(verworpen: die gaat over `Einddatum`/`Begindatum`, dit over de klasse; en ADM-006 vindt hier
niets, want geen enkel object draagt een `Einddatum`). De ernst laten afhangen van het aantal
strengen bovenstrooms (verworpen: het aantal is een sorteersleutel, geen norm).

**Gemeten uitkomst (2026-08-25).** Volledige toets op De Wolden en Hoogeveen: 54 loze leidingen
in 33 ketens -- doorgaand 3/8, aanvoer 11/16, afvoer 5/14, losgekoppeld 14/16 (ketens/strengen);
ADM-010 38 meldingen, ADM-011 16. Dat is precies de tabel uit het issue: het koppelingsherstel
van #60 heeft hier niets verschoven. Het Koekangerveld-controlegeval (`ID0500-Kv1X0002-1`,
`Kv1X0002-Kv1G0014-1`) is doorgaand met `ID6391-ID0500-1` als aanvoer en
`Kv1G0014-Kv1G0012-1`/`Kv1G0014-Kv1G0016-1` als afvoer. Grootste ketens naar actief riool
bovenstrooms: `Zu1G0932-Zu1X0006-1` 253 (doorgaand), `Wi1G0282-Wi1X0002-1` 126,
`An2G0048-An2X0002-1` 58, `Ru1G0138-Ru1X0004-1` 46 en `Ru1G0142-Ru1X0002-1` 41 (die vier
aanvoer).

**Niet alle buren zijn vrijverval.** Van de 36 aansluitende strengen bij ADM-010 zijn er 32
vrijverval, 2 duiker en 2 persleiding. Dat hoort zo: de check leest `selectie.leidingen`
(rol `[klassen] streng = ["Leiding"]`), dus "actief riool" is elke niet-loze `gwsw:Leiding`, en
`Duiker` hangt in de ontologie rechtstreeks onder `Leiding` -- niet onder
`VrijvervalRioolleiding`. Het raakt 3 van de 19 ADM-010-ketens, goed voor 6 van de 38 meldingen:
`loos-Ru1X0010-Ru1U0066-1` (afvoer, op de duikers `Ru1U0066-Ru1U0064-1` en
`Ru1U0066-Ru1U0068-1`), `loos-ID6480-RuBP0338-1` (afvoer, op persleiding `RuBP0338-ID4028-1`) en
`loos-Wi1G0680-Wi1X0010-1` (aanvoer, vanaf persleiding `ID7234-Wi1G0680-1`). Bij de overige 16
ADM-010-ketens is elke buur vrijverval.

**Het detail `rakend` op deze dataset.** Niet leeg bij 12 van de 19 ADM-010-ketens (24 van de 38
meldingen), en leeg bij alle 14 losgekoppelde ketens. De zin over een rakende actieve streng
staat alleen in de ADM-011-tekst -- daar was ze nodig -- en komt op De Wolden en Hoogeveen dus
in geen enkele melding voor; alleen de fixture dekt haar. Voor ADM-010 blijft `rakend` een
detailveld zonder eigen zin, want daar zegt de tekst al welke strengen aansluiten.

### BO-48 De CI-poort classificeert overslagen op reden; de telgrens vervalt

**Wat.** `NLRIOCHECKER_MAX_OVERGESLAGEN` (een bovengrens op het aantal overgeslagen tests)
vervalt. Met `NLRIOCHECKER_STRIKTE_OVERSLAG` gezet (CI, en `scripts/runnerpoort.py`) laat
`tests/conftest.py` de run vallen op elke test-overslag waarvan de reden geen `data/` en geen
`BO-` noemt, met nodeid en reden in de uitvoer. `NLRIOCHECKER_MIN_GESLAAGD` en
`NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` blijven. `scripts/runnerpoort.py` draait de poort lokaal
in de runner-conditie en leest grenzen en pytest-regel uit de workflow.

**Waarom.** De telgrens telde ook de bedoelde overslagen mee -- 57 van de 58 op de runner zijn
tests die de ontologie, het Juinen-voorbeeld, de SHACL-rapporten of de externe bronnen nodig
hebben, en die staan daar niet -- en klapte daardoor twee keer in twee dagen op legitieme groei
(24-08: 51 → grens 57; 25-08: 59 → grens 65). Wat hij moest vangen is een fixture die niet
meekomt, een generator die niet gedraaid is of een tool die ontbreekt: overslagen met een
ándere reden. Op reden classificeren vangt precies die, zonder getal dat met de suite mee
moet, en is strenger dan de oude marge van zes.

**Conventie die dit oplegt.** Een skip-reden zegt waar hij vandaan komt: "… staat niet in
data/" voor echte data, het BO-nummer voor een bewuste uitzondering. Een reden die geen van
beide draagt is op CI rood -- ook als de overslag terecht was; dan is de reden fout, niet de
poort.

**Alternatieven.** De telgrens blijven herijken (verworpen: twee keer in twee dagen, en elke
herijking is handwerk dat de volgende sessie herhaalt). Een aparte lijst verwachte tests
(verworpen: dubbele administratie die achterloopt). Alleen de lokale runnerpoort (verworpen:
vangt de fout vóór de push, maar de grens zelf blijft verkeerd).

### BO-49 Meldingen onderdrukken per klasse en per check is een uitvoerkeuze, op één plek, met telling

**Wat.** `[rapport]` krijgt `onderdruk_klassen` (GWSW-wortelklassen; subklassen via de ontologie) en
`onderdruk_checks` (check-ID's), beide standaard leeg. `bouw_meldingenstroom` houdt ná het samenstellen
van de drie bronnen elke melding uit de stroom waarvan het check-ID op de tweede lijst staat of waarvan
het hoofdobject (`object_uri`, niet `object2_uri`) onder een klasse van de eerste valt. Hij telt twee
dingen die geen partitie zijn: `per_check` telt élke weggevallen melding onder haar check-ID -- ook wat op
klasse wegviel, want dat is precies het verschil met de kolom Bevindingen van die check -- en `per_klasse`
alleen het deel dat op klasse wegviel. Het totaal is dus de som over `per_check`. Rapport
(verantwoording), `totaal/synthese.md`, `gwsw_run` (`onderdruk_klassen`, `onderdruk_checks`,
`meldingen_onderdrukt`) en de JSON-envelop (`onderdrukt`, optioneel) dragen de telling; de CSV niet. Elk
object van een onderdrukte klasse wordt grijs met de reden "klasse onderdrukt in de projectconfiguratie;
meldingen erop komen niet in de uitvoer" -- ook een object waarop niets gevonden was, want de reden hoort
bij de klasse -- en die reden gaat vóór "mechanisch". Een onbekend check-ID faalt bij het laden; alleen
register-ID's zijn toegestaan, een nulmetingsvorm of datasetsignaal onderdruk je via de klasse. De Wolden
onderdrukt `MechanischeRioolleiding` en `MechanischeTransportleiding`, dezelfde wortels als
`[klassen] mechanisch`. Uitgewerkt in issue #65.

**Waarom.** Het checkregister rekent mechanisch riool buiten scope, maar TOP-010, TOP-011 en de
SHACL-nulmeting melden er toch op (Koekangerveld: 17 van de 20 mechanische strengen gekleurd). De
kaartregel van BO-29 -- grijs wint niet van een gebrek -- is juist en blijft; wat weg moet is de melding
zelf, vóór hij een schrijver bereikt, anders lopen de vier uitvoervormen uit elkaar. Daarom één plek
(`bouw_meldingenstroom`) en geen filter per schrijver. Het is een uitvoerkeuze en geen toetskeuze:
`examined` en de systemisch-bepaling veranderen niet, anders zou een onderdrukte klasse de noemer van
een andere check verschuiven. De telling staat erbij omdat stilte leest als "alles gecontroleerd".

**Alternatieven.** Een CLI-vlag (verworpen: de keuze is projectgebonden en hoort reproduceerbaar in de
TOML). De checks zelf op `[klassen] mechanisch` laten filteren (verworpen: dan verdwijnt ook de
kruisingsmelding op de vrijvervalstreng, en de nulmeting filtert niet). Een kolom in de CSV (verworpen:
dezelfde reden als bij de CFK-set, BO-7). Het JSON-veld altijd schrijven (verworpen: een run zonder
lijsten blijft byte-voor-byte gelijk, zoals bij `markering`).

**Gemeten uitkomst (2026-08-25).** Volledige toets op De Wolden en Hoogeveen met de projectconfig: 10.345
meldingen onderdrukt van de 167.571 (1.832 uit het register, 8.513 uit de nulmeting, nul uit de
dataset-laag), per klasse MechanischeTransportleiding 9.917 en MechanischeRioolleiding 428. De grootste
posten zijn nulmetingsvormen op de leiding zelf -- LengteLeiding_val 1.955, EindpuntLeiding_Knooppunt_card
1.672, HoogteLeiding_val 1.193, BreedteLeiding_val 1.193, BeginpuntLeiding_Knooppunt_card 1.030 -- en van de
eigen checks ATTR-017 962, TOP-010 367 en TOP-011 365. Dat zijn de getallen die de verantwoording achter
"per check" zet: die telling loopt over álle weggevallen meldingen, ook die op klasse wegvielen -- anders
zou een check waarvan alle bevindingen wegvielen (TOP-007, 7 → 0) er met "geen" naast staan.
`n_mechanisch` blijft 3.720 en de kolom Bekeken
(`examined`, 23.440) en de systemisch-bepaling per check veranderen niet: het is een uitvoerkeuze; de kolom
Bevindingen in het rapport daalt per check met wat wegviel (TOP-010 2.551 → 2.184, TOP-011 2.237 → 1.872,
TOP-006 197 → 81, TOP-007 7 → 0). In de laag `strengen` gingen 3.652 strengen van gekleurd (2.719 rood, 933
oranje) naar grijs met de reden "klasse onderdrukt"; de overige 68 mechanische strengen waren al grijs
(en dragen die reden nu ook, want hij hoort bij de klasse en niet bij weggevallen meldingen),
en de laag `putten` verandert niet. Koekangerveld: van 17 gekleurde mechanische strengen (13 rood, 4 oranje)
naar 0, alle 20 grijs, 48 meldingen onderdrukt.

### BO-50 Eén vlakkenlaag `vlakken` voor de externe objecten, met de soort als kolom

**Wat.** De GeoPackage draagt de externe objecten waarnaar de EXT-meldingen verwijzen in één laag
`vlakken` (MULTIPOLYGON) in plaats van de aparte lagen `bouwwerken` (EXT-001) en
`waterdelen_zonder_zinker` (EXT-003) (issue #67). De kolom `soort` (`pand`, `bouwwerk`, `water`) scheidt de
categorieën en volgt op één plek uit `Treffer.bron`; `subtype` draagt het BGT-type, `relatie` en
`afstand_min_m` gelden alleen voor pand en bouwwerk (leeg bij water), en `check_ids` somt de checks op die
naar het vlak wijzen. De vroegere `buffer_m` vervalt -- runmetadata, staat in `gwsw_run`, waar `n_vlakken`
de laag telt. Er komt één stijl `vlakken.qml`, rule-based op `soort` met drie regels. EXT-002 registreert
voortaan zijn treffer onder dezelfde sleutel als EXT-003 (`bouw_sleutel(VOORVOEGSEL["bgt_water"], …)`),
zodat een waterdeel dat beide checks raken één rij met beide check-ID's krijgt en een waterdeel dat alleen
EXT-002 ziet -- een echte doorkruising door een geregistreerde zinker -- toch een vlak krijgt.

**Waarom.** Net als bij `putten` en `strengen`: één laag per geometriesoort, met de opmaak per categorie in
de laag, is eenvoudiger te koppelen en te stijlen dan drie parallelle lagen met eigen kolommen en QML. De
doorkruiste waterdelen van EXT-002 stonden sinds issue #59 wel als `object2` in de melding maar nergens op
de kaart, omdat de oude waterdelenlaag alleen EXT-003 volgde; met de merge en de EXT-002-registratie krijgen
ze eindelijk een vlak. De strikte aansluiting op het trefferregister (BO-18) blijft: de schrijver bevraagt
geen bron, dus laag en uitslag lopen niet uit elkaar.

**Alternatieven.** De twee lagen houden en een derde toevoegen voor EXT-002 (verworpen: nog meer parallelle
lagen, terwijl de geometriesoort dezelfde is). De volledige bronvlakken als achtergrond meeschrijven
(verworpen: BO-18 -- 81.661 actuele panden zouden de GeoPackage opblazen zonder dat een melding ernaar
wijst). `stelsels` mee in `vlakken` trekken (verworpen: dat zijn GWSW-objecten, geen externe bron).

**Contractbreuk.** De lagen `bouwwerken` en `waterdelen_zonder_zinker` en de kolommen `n_bouwwerken`/
`n_waterdelen` in `gwsw_run` bestaan niet meer; QGIS-projecten die erop wezen moeten opnieuw gekoppeld
worden aan `vlakken`.

### BO-51 Elke check declareert `rollen` en `kenmerken`; putdiepte/putbodem toetsen op `Rioolput`

**Wat.** Elke geregistreerde check declareert twee `ClassVar`s (issue #64): `rollen` (namen uit
`selectie._ROLLEN` -- de populatie die hij langsloopt) en `kenmerken` (GWSW-kenmerknamen zoals de code ze
aan `aspect`/`number`/`reference`/`date` geeft, of een `config:<pad>`-verwijzing voor ATTR-013, of `*` voor
ATTR-014). `register()` weigert een check zonder beide; ze reizen mee op `CheckOutcome` en voeden de
rapportregel "Toetst ⟨klassen⟩ op ⟨kenmerken⟩" en de dekkingsmatrix. Twee drifttests bewaken ze: een
AST-sweep tegen de feitelijke code (`checkdeclaratie_analyse.py`) en een tweede tegen de ontologie, die
leunt op twee nieuwe indexblokken `aspecten_van`/`onderdelen_van` (per klasse de directe
`hasAspect`/`hasPart`-doelen, beide richtingen gevouwen omdat het GWSW `isAspectOf`/`isPartOf` als inverse
declareert). Een nieuwe rol `rioolputten` (`gwsw:Rioolput`) vervangt `netwerkknopen` in HGT-012 (putdiepte)
en HGT-015 (putbodem); in HGT-004, HGT-016 en HGT-017 wordt alleen de deksel-/bodemtak tot de rioolputten
beperkt, terwijl de bovenkanttak (met terugval op maaiveld) breed blijft.

**Waarom.** Tot nu toe stond nergens over welke GWSW-begrippen een check ging, en het was voor geen enkele
check nagelopen. De putdiepte (deksel minus bodem) en het daaruit afgeleide bodemniveau hangen aan een put
mét een deksel; een gemaal of uitlaat draagt geen `HoogtePut` en geen `Putdekselniveau`. `Rioolput` is in de
ontologie letterlijk "een put met een verwijderbare deksel", en dat is de klassegrens die deze twee checks
horen te trekken.

**Meting (De Wolden en Hoogeveen, `configs/dewoldenhoogeveen.toml`).** `netwerkknopen` telt 22.363 objecten,
`rioolputten` 20.756: het verschil van 1.607 is 893 Rioolgemaal, 712 Uitlaatconstructie, 1 Kolk en 1
Drainageput -- klassen zonder deksel en zonder `HoogtePut`. Het aantal bevindingen van HGT-012 en HGT-015
verandert *niet* (0 vóór, 0 na): deze export bevat geen enkele `HoogtePut`, dus beide checks sloegen elk
object al over. Wat verandert is `examined` (van 22.363 naar 20.756) en de noemer van hun toelichting: die
telde 1.607 gemalen en uitlaten mee die het kenmerk structureel nooit konden dragen, en las daarmee als een
bredere toets dan hij was.

**Grens van de ontologietest.** De toets is een ondergrens, geen uitputtende lijst: de declaratie is plat
(welke rollen, welke kenmerken -- niet welk kenmerk op welke rol), dus een smalle mede-gedeclareerde rol kan
een kenmerk afdekken en de vlag onderdrukken. Het geval dat dit blootlegde was `(HGT-016, HoogtePut)`; met
de reparatie hierboven toetst HGT-016 de bodem op `rioolputten` en is die blinde vlek nu leeg, al blijft ze
theoretisch bestaan. Een sluitende oplossing (kenmerken per rol) is bewust uitgesteld. Het indexblok leest naast
`owl:onClass` ook `owl:someValuesFrom`/`owl:allValuesFrom`, zodat een forward-only binding als
`Deksel hasAspect MateriaalDeksel` niet ontbreekt.

**Grens (populatie).** De auteur koos (na de tabel in de sluitcomment) om HGT-004, HGT-016 en HGT-017 hun
deksel-/bodemtak tot `rioolputten` te laten beperken, en HGT-001/002/011/018 en BTR-006 *ongewijzigd* te
laten: die vallen terug op de maaiveldhoogte, en die terugval is zinvol voor elk object -- restrictie tot
`rioolputten` zou de maaiveld-vs-AHN/z-toets op gemalen en uitlaten laten vervallen. Die vijf staan met reden
op de uitzonderingslijst van de ontologietest. `Maaiveldhoogte` hangt via `hasConnection` aan de `Maaiveldorientatie`
en is daarom vanaf geen klasse bereikbaar in de index (die alleen `hasAspect`/`hasPart` volgt); die staat als
globale uitzondering. De nul-bewaking uit `omvang.py` is bewust niet op de declaraties omgebouwd: de
handlijst dekt via `via_onderdeel`/`per_klasse` gevallen (overstortdrempel, afvoereindpunt) die de rolnamen
niet uitdrukken, en dat omzetten raakt een goed geteste uitvoerlaag. De auteur koos dit als los vervolg,
buiten #64.

### BO-52 De nul-bewaking leidt haar rollen uit de checkdeclaraties af; twee bewakingen blijven expliciet

**Wat.** `omvang._rollen` (de bron voor de rollentelling en de `SIG-nulklasse`-bewaking) was een handlijst
van zes rollen. Sinds issue #71 verzamelt hij de rollen die de geregistreerde checks in `check.rollen`
declareren (`_gedeclareerde_rollen()` over de `REGISTRY`), lost ze via `selectie.klassen_van_rol` op naar hun
`[klassen]`-wortels en telt via `of_class`. De nul-melding noemt voortaan de check-ID's die op de lege rol
leunen -- het gat uit issue #22, nu generiek. `klassen_op_nul` en `klassentelling` lezen dezelfde lijst, dus
de "Per rol"-tabel en de nul-signalen kunnen niet meer uiteenlopen.

**Waarom expliciet, niet één bron.** Twee bewakingen drukken geen `selectie._ROLLEN`-rol uit en zijn niet
via `klassen_van_rol` bereikbaar; ze blijven daarom als aparte regels vóór de afgeleide lijst staan:
- het **afvoereindpunt** (`Overnamepunt`, `Gemaal`, `Pompunit`) wordt *per klasse* bewaakt, want elke klasse
  draagt een eigen betekenis -- noodverband (`Gemaal`/`Pompunit`) versus echt overdrachtspunt
  (`Overnamepunt`), BO-33 -- en er is geen rol `afvoer_eindpunt`;
- de **overstortdrempel** is een `Overstortdrempel`-onderdeel zonder eigen geometrie dat via
  `subjects_of_class` geteld wordt (NET-007 leest hem zo), niet via `of_class`, en heeft evenmin een rol.
Ze in dezelfde bron vatten zou een neprol of een tweede `_ROL_VELDEN`-ingang zonder selectiefunctie vergen
en `test_checks_selectie` breken. De check-attributie van deze twee is de canonieke check (NET-001 resp.
NET-007), niet een uitputtende afleiding zoals bij de gedeclareerde rollen; dat volstaat en houdt de melding
kort.

**Gevolg voor het rapport.** De "Per rol"-tabel gaat van 6 naar 19 rijen en gebruikt de `_ROLLEN`-rolnamen
(`putten`, `leidingen`, `lozingspunten`, ...) in plaats van zes zelfgekozen labels; `lozingseindpunt` heet
nu `lozingspunten`, en `mechanische leiding` verdwijnt omdat geen check die rol declareert (mechanisch riool
valt buiten het checkregister). Een gedeclareerde rol zonder geconfigureerde klassen (een project mag
`functieloze_knoop` leeg laten) valt weg: zonder verwachte populatie is er niets op nul te melden.

**Meting (De Wolden en Hoogeveen, `configs/dewoldenhoogeveen.toml`).** Vóór #71 stonden drie signalen op
nul: `Overnamepunt` (afvoereindpunt per klasse), `bergbezinkvoorziening` en `overstortdrempel`. Ná #71 zijn
het er vijf: `Overnamepunt`, `overstortdrempel`, `bergbezinkvoorzieningen` (dezelfde rol, nu onder haar
`_ROLLEN`-naam), plus twee *nieuwe* signalen die de oude handlijst niet dekte -- `oppervlaktewaterobjecten`
(0 in de export, RVZ-004 leunt erop) en `valconstructies` (0, HGT-009 en HGT-016 leunen erop). Beide zijn
terecht: staat de rol op nul terwijl een check erop toetst, dan heeft die check niets te beoordelen en hoort
dat in het rapport. De telling zelf sluit aan op BO-51: `netwerkknopen` 22.363, `rioolputten` 20.756,
`putten` 20.758.

### BO-53 Een lozingspunt is een geldig vuilwater-eindpunt voor NET-001

**Wat.** NET-001 (vuilwater/gemengd zonder afvoerpad) accepteerde alleen de rol
`afvoer_eindpunt` (`Overnamepunt`, `Gemaal`, `Pompunit`). Sinds issue #72 telt daarnaast
`lozings_eindpunt` (`Lozingspunt`, `UitlaatPunt`, `Lozingsput`, `Uitlaatconstructie`) mee; de
eindpuntverzameling van de check is de vereniging van beide rollen. Titel, `doel`-tekst, de
NET-001-regel in het checkregister en de dekkingsmatrix zijn meegegaan.

**Waarom.** Vuilwater loost in Nederland niet meer rechtstreeks op oppervlaktewater. Komt een
vuilwater- of gemengde streng op een lozingspunt uit, dan is dat per definitie het punt waar het
water het stelsel verlaat -- of dat nu een overstort, een uitlaatconstructie of een
overdrachtspunt naar de zuivering is. Er valt dus geen echt gebrek mee te maskeren, terwijl het
omgekeerde wel gebeurde: elke streng achter zo'n uitlaat werd als "zonder afvoerpad" gemeld.

**Wat het intrekt.** De oude regel stond als test vast (`test_lozingspunt_telt_niet_als_afvoerpad_voor_vuilwater`)
met de redenering "NET-001 vraagt een gemaal of overnamepunt, NET-002 een lozingspunt; met een
gedeelde eindpuntlijst zou de gemengde streng ten onrechte goedgekeurd worden". Die redenering
gold de scheiding tussen de twee checks, niet het domein. De scheiding blijft: NET-002 accepteert
géén gemaal, alleen een lozingspunt. Alleen NET-001 is verruimd, niet symmetrisch.

**Meting (De Wolden en Hoogeveen, door de echte pijplijn).** Samen met BO-54 gaat NET-001 van
9062 naar 7978 bevindingen; Koekangerveld van 24 naar 7. Zie de meting bij BO-54.

### BO-54 Het mechanische riool telt als ongerichte connectiviteit, doorlopend via hulpstukken

**Wat.** `checks/verbanden.py` kent sinds issue #72 naast de gerichte vrijvervalgraaf
(`_Netwerk.graph`) een tweede laag: `_bereikbaarheid(context)`, dezelfde graaf plus de mechanische
leidingen (rol `mechanischeleidingen`, `[klassen] mechanisch`) als kanten in beide richtingen.
Alleen de bereikbaarheidsvraag leest die laag -- `_bereikbaar_vanaf` (NET-001/NET-002),
`_eindpunten` en de notities eromheen. Kringlopen (NET-004), stelseltypen (NET-005/006) en de
afvoerpadanalyse (`afvoerpaden`, `afvoerpad_van_streng`) blijven op het zuivere vrijverval: dat
zijn vrijverval-begrippen, en ongerichte kanten zouden er onzin van maken -- elke persleiding zou
in NET-004 als kringloop van twee knopen verschijnen.

**Waarom ongericht.** Een persleiding is pompgestuurd; haar administratieve van-naar-richting
zegt niets over de stroomrichting en wordt elders ook niet vertrouwd (de grijze persleiding-pijlen
in de GIS-uitvoer). Voor de vraag of het water ergens uitkomt telt alleen de connectiviteit.

**Waarom via de rauwe koppeling.** `resolve_network_node` klimt via `hasPart` naar een put. Het
persnet komt samen op hulpstukken (`T_stuk`, `Hulpstukorientatie`) en die klimmen nergens naartoe,
dus zo'n knoop resolvet naar `None`: 1914 van de 3720 mechanische leidingen (51%) hebben geen twee
oplosbare knopen. Elke T zou het persnet in stukken hakken en het gemaal erachter onbereikbaar
laten. De kant valt daarom terug op de rauwe `Conduit.start_node`/`end_node`, zodat het hulpstuk
een doorgeefknoop wordt. `resolve_network_node` zelf blijft ongemoeid: die voedt de puttellingen en
de ADM-checks, en globaal wijzigen is een te groot risico-oppervlak.

**Aanname nagemeten.** Alle 939 niet-oplosbare tussenknopen in het persnet van De Wolden en
Hoogeveen zijn hulpstukken; er is er geen enkele die dat niet is. De terugval raakt dus precies de
hulpstukken en niets anders.

**Gevolg voor de declaraties.** Wie de laag opvraagt leest daarmee de rol
`mechanischeleidingen`, en de AST-sweep van BO-51 ziet dat. Dat zijn NET-001, NET-002 en NET-008;
die drie declareren de rol. De overige NET-checks blijven op het zuivere vrijverval en declareren
hem niet.

Dat de laag lui is (een eigen `context.cached("bereikbaarheid", ...)` in plaats van een veld op
`_Netwerk`) is precies daarvoor: bouwde `_bouw_netwerk` hem eager op, dan las elke check die de
graaf aanraakt het persnet en moest hij het declareren -- ook NET-004, dat er per se buiten moet
blijven. Tot de eindreview van #72--#77 stond het zo, en toen beweerden alle negen NET-checks in
rapport, `overzicht_checks.populatie` en JSON dat zij over mechanische leidingen gingen. Onwaar, en
in tegenspraak met deze BO zelf; de luie laag herstelt dat zonder de AST-sweep te omzeilen. De
uitkomsten van de checks veranderen er niet van: NET-001 blijft op 8467, NET-002 op 3031 (De Wolden
en Hoogeveen, na #73).

Dit trekt de opmerking in BO-52 in dat "`mechanische leiding` verdwijnt omdat geen check die rol
declareert": de rol staat weer in de rollentelling en in de `SIG-nulklasse`-bewaking, nu met drie
leunende checks. Voor een dataset zonder mechanisch riool levert dat een nul-signaal op; dat is de
bedoelde betekenis van die bewaking (een populatie waar checks op leunen komt niet voor), niet een
gebrek in de aanlevering.

**Meting (De Wolden en Hoogeveen, `configs/dewoldenhoogeveen.toml`, door de echte pijplijn met
`markeer_vulwaarden` vóór de checks).** NET-001 gaat van **9062** naar **7978** bevindingen op
17451 onderzochte strengen; binnen Koekangerveld van **24** naar **7**. Het onderbouwende issue
voorspelde 8467/7 voor #72 én #73 samen (Pompunit uit `afvoer_eindpunt`); dit issue alleen laat
Pompunit als eindpunt staan en komt daarmee onder die grens uit, zoals verwacht. De zeven die in
Koekangerveld overblijven horen echt zonder route te zijn. Onderbouwing en de causale trace:
`scripts/analyse_afvoer_pompunit.py`.

**Ook NET-002, en dat is gewogen.** `_bereikbaar_vanaf` is gedeeld, dus het persnet telt ook voor
de hemelwatercheck mee: NET-002 gaat van **3054** naar **3031** (Koekangerveld 0 → 0, geen enkele
nieuwe bevinding in beide checks -- de wijziging kan alleen bereikbaarheid toevoegen). Alle 23
weggevallen bevindingen liggen in drie deelstelsels, gebruiken minstens één mechanische kant en
komen op een `Lozingsput` uit; 21 van de 23 lopen daarbij uitsluitend mét de geregistreerde
richting mee, dus de ongerichtheid is er geen tweede versoepeling bovenop. Het typische geval is
een hemelwaterstelsel dat op een `Rioolgemaal` afwatert waarvan de drukleiding op de lozingsput
uitkomt (bv. `364786-319522-1`: negen vrijvervalstappen naar gemaal `ElBP0184`, dan drukleiding
`ElBP0184-El1G0124-1` naar lozingsput `El1G0124`). Dat is precies wat NET-002 vraagt -- een pad
naar een lozingspunt -- en dat het laatste stuk gepompt is maakt het niet minder waar. De
domeinredenering van BO-53 speelt hier niet mee: NET-002 vroeg altijd al om een lozingspunt, alleen
de route ernaartoe verandert. Vastgelegd in
`tests/test_checks_netwerk.py::test_hemelwater_door_het_persnet_geldt_ook_als_afgevoerd`.

### BO-55 `Pompunit` is geen afvoereindpunt; het noodverband uit BO-33 krimpt tot `Gemaal`

**Wat.** `[klassen] afvoer_eindpunt` is `["Overnamepunt", "Gemaal"]` geworden, in
`src/nlriochecker/checks.toml` en in `configs/dewoldenhoogeveen.toml`. Deze ene lijst voedt
NET-001 (`_eindpunten` in `checks/verbanden.py`) en RVZ-006 (`_afvoereindpunten` in
`checks/randvoorzieningen.py`), dus beide erven de correctie. Dit verfijnt BO-33; het draait
hem niet terug, want `Gemaal` blijft er om precies dezelfde reden in staan (nul
`Overnamepunt` in deze aanlevering) en met hetzelfde loslaatcriterium.

**Waarom ontologisch.** `gwsw:Pompunit` is een `Rioolput` in het mechanische stelsel, geen
`Gemaal` (dat is een `Bouwwerk`) en geen `Overnamepunt` (een `Aansluitpunt`, met de
NEN 3300-definitie van overdracht). Een pompput is een **overdrachtspunt naar de
drukriolering**, niet het einde van de afvoer. Dat einde is een gemaal of overnamepunt --
of, sinds BO-53, een lozingspunt.

**Waarom nu pas.** BO-33 zette `Pompunit` er bewust in als noodverband: de graaf traverseerde
het mechanische riool niet, dus zonder pompput-als-eindpunt gold heel de drukriolering als
onbereikbaar (+645 vuilwater/gemengd-strengen op De Wolden en Hoogeveen, waarvan 3 in
Koekangerveld; `scripts/analyse_afvoer_pompunit.py`). Dat waren valse positieven: het water
werd wel afgevoerd, wij konden het alleen niet traceren. Issue #72 heft die reden op (BO-54:
mechanische connectiviteit door hulpstukken; BO-53: het lozingspunt telt mee), en pas daarna
mag `Pompunit` eruit.

**Meting (De Wolden en Hoogeveen, `configs/dewoldenhoogeveen.toml`, door de echte pijplijn met
`markeer_vulwaarden` vóór de checks).** NET-001 gaat van **7978** naar **8467** bevindingen op
17451 onderzochte strengen; Koekangerveld blijft op **7**. Dat is exact wat het onderbouwende
issue voorspelde voor #72 + #73 samen (rij `(c'+L)` van `scripts/analyse_afvoer_pompunit.py`).
NET-002 blijft **3031**: die check leest `lozings_eindpunt`, niet `afvoer_eindpunt`. RVZ-006
gaat van **98** naar **99**; de ene nieuwe bevinding is deelstelsel `ds-Ko2G0002` (35 knopen,
gemengd, wel een overstort maar als enig eindpunt een pompunit). Negen bestaande
RVZ-006-boodschappen wijzigen alleen van tekst.

**Voorwaarde, en die wordt afgedwongen.** Dit besluit klopt alleen zolang de route achter de
pompput traceerbaar is, en dat is precies zolang `[klassen] mechanisch` klassen noemt:
`_bouw_bereikbaarheid` legt de kanten alleen dan, en `_componentstructuur` neemt de
route alleen dan in de contextschil op (BO-56). `load_check_config` valideert een projectbestand
**op zichzelf** en legt het niet over `checks.toml` heen, dus een projectconfig die deze nieuwe
`afvoer_eindpunt` overneemt maar `mechanisch` weglaat, krijgt een lege lijst en belandt stil in
de +645-toestand van BO-33. De nul-bewaking vangt dat niet: een gedeclareerde rol zonder
klassen valt juist uit de rollentelling weg (BO-52), dus er komt geen `SIG-nulklasse`. Daarom
weigert `ClassRoots._pompunit_heeft_een_uitweg` de combinatie "`afvoer_eindpunt` niet leeg,
zonder `Pompunit`" met "`mechanisch` leeg", met een foutmelding die beide sleutels en dit
BO-nummer noemt. Een lege `afvoer_eindpunt` valt er bewust buiten: dan is er in het geheel geen
afvoereindpunt, een eigen en meteen zichtbare toestand waar de minimale testconfigs op leunen.
De twee controlehelften die het persnet juist uitzetten om te bewijzen dat de route erdoorheen
loopt, maken `mechanisch` daarom ná de validatie leeg (`_zonder_persnet` in
`tests/test_checks_netwerk.py`); de poort bewaakt wat iemand als projectconfig opschrijft.

**Teksten die meeveranderden.** De deelreden van RVZ-006 (`_rvz006_gebrek`) luidt "zonder
afvoereindpunt (gemaal of overnamepunt)", net als de RVZ-006-regel van het checkregister; de
rapportregel onder de eindpunttelling noemt alleen `Gemaal` nog als noodverband. De
NET-001-regel van het register was door #72 al bijgewerkt naar "gemaal, overnamepunt of
lozingspunt". Vastgelegd in `tests/test_checkconfig.py::test_afvoereindpunt_is_overnamepunt_en_gemaal`,
`tests/test_checks_netwerk.py::test_pompunit_zonder_persnet_is_geen_afvoereindpunt` en
`tests/test_checks_blok_a.py::test_rvz006_telt_een_pompunit_niet_als_afvoereindpunt`.

### BO-56 De contextschil loopt door het persnet, anders houdt de gelijkwaardigheid niet

**Wat.** `_componentstructuur` in `afbakening.py` legt naast de vrijvervalleidingen ook de
mechanische leidingen (`[klassen] mechanisch`) als kanten in de componentgraaf, met dezelfde
terugval op de rauwe koppeling als `_bouw_bereikbaarheid` (BO-54). De contextschil
van een studiegebied is daardoor de samenhangende component over vrijverval **én** persnet.

**Waarom.** BO-12 eist gelijkwaardigheid: de meldingen van een gebied zijn gelijk aan die van
een losse run over dat gebied, en aan een gemeentebrede run beperkt tot dat gebied. Sinds
issue #72 loopt de bereikbaarheid van NET-001/NET-002 door het persnet en sinds BO-55 is een
pompput zelf geen eindpunt meer. Bakende de schil zich dan nog op het zuivere vrijverval af,
dan viel het gemaal achter de persleiding buiten de analyseset en meldde een gebiedsrun
strengen die de gemeentebrede run niet meldt. Het commentaar dat de mechanische leidingen hier
bewust buiten hield ("de NET-checks volgen ze niet") was met #72 onwaar geworden.

**Meting (88 CBS-buurten van De Wolden en Hoogeveen, per buurt de gebiedsrun tegen de
gemeentebrede run beperkt tot dezelfde kern).** Met de oude schil weken **17** buurten af op
NET-001, alle met méér bevindingen in de gebiedsrun en geen enkele met minder; met deze
wijziging zijn het er **0**. De afwijking bestond al vóór dit issue -- met `Pompunit` nog als
eindpunt weken er 7 af, een gevolg van #72 dat het #72-verslag als openstaand punt naar dit
issue doorschoof. Op een bredere steekproef van 8 buurten over alle 99 checks: 12 afwijkende
checks (NET-001 in alle acht, plus TOP-001, TOP-006, TOP-011, TOP-023) vóór, 1 erna. Het meetscript staat als
`scripts/analyse_contextschil_persnet.py` in de repo.

**De prijs, en waarom hij aanvaardbaar is.** De analysesets van de 88 buurten samen groeien van
303.570 naar 518.101 objecten (1,7x); de grootste gaat naar 15.739 van de 46.925 objecten in de
export. Dat is de vrees uit het oude commentaar -- "de schil dijt uit tot de hele gemeente" --
in gemeten vorm: een derde van de export in het zwaarste geval, geen geheel. De schil wordt
bovendien nooit kern, dus wat erbij komt kan geen bevinding in het gebied opleveren; het kan
alleen valse bevindingen wegnemen.

**Wat er niet mee opgelost is.** Eén afwijking blijft staan: TOP-023 (hulpstuk met te veel
leidingen) in de buurt "Verspreide huizen Koekange". Die bestond vóór deze wijziging ook al en
gaat niet over de bereikbaarheid maar over de leidingtelling rond een hulpstuk op de
gebiedsrand. Niet in dit issue aangepakt; hij hoort in een eigen issue thuis.

### BO-57 De laag `stelsels` vervalt; RVZ-006 meldt per gemengde streng en krijgt een eigen vlak

**Wat.** Drie samenhangende besluiten uit issue #75, allemaal op dezelfde polygooncode.

1. De cartografische laag `stelsels` verdwijnt uit de GeoPackage, met haar stijl `stelsels.qml`,
   de module `uitvoer/stelsels.py` en de kolom `n_stelsels` in `gwsw_run`. De kolom `stelsel` op
   `putten` en `strengen` (`uitvoer/omvang.stelseltypen`) blijft: dat is een labeling per object en
   geen vlak.
2. RVZ-006 meldt per **gemengde streng** (`GemengdRiool` en subklassen, via `[klassen] stelseltypen`)
   van het falende deelstelsel, in plaats van één bevinding op `sorted(deel)[0]`. Alle bevindingen
   van hetzelfde deel dragen dezelfde `cluster_id`, dezelfde die NET-001 en NET-002 gebruiken. Het
   zwaartepunt als foutlocatie vervalt: de melding zit op haar eigen streng. `examined` telt sindsdien
   de gemengde strengen en niet meer de netwerkdelen.
3. Daarvoor in de plaats komt de laag **`gemengd_zonder_overstort`** (MULTIPOLYGON, met eigen QML): een
   vlak per gemengd deelstelsel waarop RVZ-006 aansloeg, als buffer om de vrijvervalstrengen van de
   hele component. De buffer heet daarom `gemengd_zonder_overstort_buffer_m` (10 m, ongewijzigd) en
   `gwsw_run` telt de laag in `n_gemengd_zonder_overstort`.

**Wat de laag garandeert.** Zij kan niet groter zijn dan de uitslag, want haar rijen komen uit de
meldingen. Kleiner kan zij worden om twee redenen, en die krijgen bewust een verschillende
behandeling. Een `cluster_id` die de graaf van de run niet kent is een **interne tegenspraak** --
check en schrijver lezen dezelfde `deelstelsel_ids` van dezelfde context -- en faalt luid met een
`PipelineError`, dezelfde lijn die `_vul_trefferlaag` volgt bij een melding die naar een
niet-geregistreerde treffer wijst. Een deelstelsel waarvan geen enkele streng een bruikbare lijn
draagt is wél een datatoestand: er valt niets te tekenen. Dat levert geen rij op maar wordt geteld
in de kolom `n_gemengd_zonder_vlak` van `gwsw_run`, naast `n_gemengd_zonder_overstort`. Zonder die
telling kan een lezer "dit deelstelsel bestaat niet" niet onderscheiden van "we konden het niet
tekenen" -- en dat is precies de stilte die dit project niet toestaat. Op De Wolden komt het geval
vandaag niet voor (99 van de 99 gemelde deelstelsels krijgen een vlak); juist daarom zou het zonder
telling onopgemerkt blijven zodra het wél gebeurt.

**Waarom.** De stelsellaag groepeerde strengen via de GWSW-stelselregistratie, en de auteur heeft
vastgesteld dat die groepering niet betrouwbaar is. Wat de laag liet zien -- wel of geen afvoerroute --
is bovendien een eigenschap van het **netwerk** (`afvoerpad_van_streng`) en niet van de
stelselhiërarchie; die hiërarchie wordt door geen enkele check gebruikt. Een kaartlaag die op een
onbetrouwbare groepering een netwerkfeit tekent, wijst de lezer de verkeerde kant op.

RVZ-006 hing aan de lexicografisch eerste knoop van een deelstelsel. Er ís geen GWSW-object "gemengd
stelsel" -- gemengd volgt uit het leidingtype -- dus die knoop was een willekeurige drager, en op de
kaart moest een zwaartepunt goedmaken dat het gebrek niet bij die ene put zat. NET-001 lost hetzelfde
probleem (een subsysteem dat iets mist) al per streng op; RVZ-006 doet dat nu ook, en het vlak toont
waar het deelstelsel ligt. Dat vlak komt uit de **meldingen van deze uitvoer** en niet uit de graaf
alleen -- dezelfde strikte aansluiting als bij de trefferlaag (BO-18/BO-50), zodat laag en uitslag niet
uit elkaar kunnen lopen na afbakening of onderdrukking.

**Meting (De Wolden en Hoogeveen, `scripts/analyse_rvz006_per_streng.py`, `b9d6060` tegen `7000b5e`).**

| | vóór | ná |
|---|---|---|
| RVZ-006 gemeentebreed | 99 bevindingen op 99 deelstelsels (794 onderzocht) | **1062** op **99** deelstelsels (7784 onderzocht) |
| RVZ-006 Koekangerveld (gebiedsrun) | 2 op 2 deelstelsels (10 onderzocht) | **26** op **2** deelstelsels (26 onderzocht) |
| nulmeting zonder kaartobject | 578 (11 + 567) | 578 (11 + 567) |

Het aantal falende deelstelsels staat stil -- de selectie verandert niet, alleen de korrel. De 1062 is
dus geen nieuwe uitslag maar dezelfde uitslag per streng: gemiddeld 10,7 gemengde strengen per falend
deel, tegen 9,8 over alle 794 delen.

**De nulmetingjoin mag niet stil vallen.** Een SHACL-overtreding waarvan de focusnode een geregistreerd
stelsel is (`vw_geb_1` c.s.) landde sinds #25 op de stelsellaag. Zonder die laag komt zij nergens meer
op de kaart, en stilte leest als "alles gecontroleerd". De melding houdt haar stelsel als `object_uri`
-- zodat CSV, JSON en meldingentabel blijven zeggen waarover zij gaat -- en het rapport telt haar samen
met de klassenaam-overtredingen in één regel "geen kaartobject", met de opsplitsing in dezelfde zin. Op
De Wolden gaat het om 567 van de 578; die 567 waren dus precies de inhoud van de vervallen laag.

**Alternatieven.** De stelsellaag laten staan en alleen RVZ-006 verfijnen (verworpen: de laag tekent een
netwerkfeit op een onbetrouwbare groepering, en twee vlakkenlagen over hetzelfde net verwarren). Het
nieuwe vlak uit de graaf opbouwen in plaats van uit de meldingen (verworpen: dan kan de laag na
afbakening of onderdrukking meer tonen dan de uitslag). De stelseloverduidingen als eigen laag houden
(verworpen: één rij per stelsel zonder betrouwbare geometrie is precies wat hier vervalt). De
`stelsel`-kolom op `putten`/`strengen` meenemen in de opruiming (verworpen: die labeling komt uit
`stelseltypen` en niet uit de registratieboom, en niemand heeft haar ter discussie gesteld).

**Contractbreuk.** De laag `stelsels` en de kolom `n_stelsels` in `gwsw_run` bestaan niet meer;
QGIS-projecten die erop wezen moeten opnieuw gekoppeld worden. De drempel `stelselvlak_buffer_m` heet
`gemengd_zonder_overstort_buffer_m` -- een projectconfig met de oude naam wordt geweigerd
(`extra="forbid"`). RVZ-006 levert op dezelfde data meer meldingen dan voorheen; een vergelijking met
een meetmoment van vóór deze wijziging telt appels en peren, en `vergelijk` zegt dat niet.

### BO-58 `bekeken` draagt een scopelabel met drie waarden en de getelde populatie

**Wat.** Elke `CheckOutcome` draagt naast `examined` twee duidingen (issue #77):

- `bekeken_scope` (`checks.base.Scope`), met **precies drie** waarden:
  `analyseset`, `volledige_export` en `attribuut_instanties`;
- `populatie`, de populatie die de check **declareert** -- zijn rollen als leesbare
  opsomming; zonder rollen zijn kenmerken (`alle kenmerken` voor `*`); zonder beide leeg.

Ze staan in de checktabel van het Markdown-rapport (kolommen Bekeken scope en
Gaat over, met een voetnoot eronder), in de detailregel en de generieke systemische regel onder elke check, in
`overzicht_checks` van de GeoPackage (`bekeken_scope`, `populatie`) en in het optionele
enveloppeveld `checks` van `bevindingen.json`. **Niet** in de meldingen-CSV: bekeken
hoort bij de check en niet bij de rij, dezelfde scheiding als bij de CFK-set (BO-7).
`totaal/bevindingen.json` draagt het veld evenmin -- `bekeken` is per gebied gemeten.

**De taxonomie.** Het getal varieert langs twee onafhankelijke assen. De eerste is de
dataset die `run_checks` de check geeft: de analyseset (kern plus contextschil) of de
volledige export, afhankelijk van `Check.volledig_bereik` en
`[studiegebied] volledige_dataset_checks`. De tweede is wat `examined()` op die dataset
telt: objecten van een rol, of instanties van een kenmerk. De tweede as wint, want telt
een check geen objecten dan zegt "volledige export" niets over zijn noemer: ATTR-014
heeft `volledig_bereik` én telt instanties, en heet daarom `attribuut_instanties`.

**Onderstreping in plaats van een koppelteken.** Issue #77 schreef die derde waarde
letterlijk als `attribuut-instanties`. De uitgebrachte waarde is
`attribuut_instanties`, met een onderstreping: zij staat in hetzelfde veld als
`volledige_export`, en één van de drie waarden een ander scheidingsteken geven maakt
elke afnemer die op de string vergelijkt afhankelijk van welke waarde hij toevallig
tegenkomt. Het koppelteken had geen andere grond dan de schrijfwijze in het issue. De
correctie is bij de eindreview van #72--#77 gemaakt, vóór de eerste uitgave waarin het
veld voorkomt, dus er is geen afnemer die de oude spelling gezien heeft en de
JSON-schemaversie hoeft er niet voor omhoog.

Welke checks instanties tellen is niet uit de code af te leiden en staat daarom als
`Check.telt_instanties` op de klasse, bewaakt door
`test_alleen_de_twee_instantietellers_zijn_zo_gemarkeerd`. Het zijn er twee: **ATTR-014**
(elke kenmerkinstantie met een property-restrictie) en **BTR-006** (elke hoogtewaarde:
twee BOB's per streng, deksel en maaiveld per knoop).

`analyseset` betekent niet "minder gezien": zonder studiegebied valt de analyseset samen
met de volledige export. Het onderscheid zegt dat deze check met de afbakening meebeweegt
en `volledige_export` niet.

**`populatie` is geen noemer, en wordt nergens als noemer gepresenteerd.** De declaratie
is de vereniging van wat `run()`, `examined()` en `notes()` aanraken -- dat is wat de
AST-sweep van issue #64 verzamelt -- en dus structureel een bovengrens op wat `examined`
telt. ATTR-018 declareert ook `leidingen`, omdat zijn toelichting die telt, terwijl
`examined` alleen vrijvervalstrengen plus putten telt. Een machinale koppeling tussen
`examined()` en de rollen bestaat niet.

Daarom staat de populatie in elke uitvoervorm los van het getal, achter **"gaat over"**:
`119 bekeken (analyseset; gaat over: leidingen, putten, vrijvervalrioolleidingen)`. De
kolom in de checktabel heet **Gaat over** en niet Populatie, en onder de tabel staat een
voetnoot die het herhaalt. Een eerdere opzet zette de populatie achter een dubbele punt
direct achter de telling; dat leest als de noemer en is precies het misverstand dat dit
besluit wegneemt.

Om diezelfde reden **geen terugval op "de hele export"** als een check geen rollen
declareert. Die formulering hoort bij de regel "Toetst ...", waar zij zegt dat de check
niet tot een rol beperkt is; achter een telling zou zij beweren dat de hele export de
noemer was. RVZ-011 (telt de drempels die aan een put hangen) en ADM-007 (telt de putten
van de geconfigureerde puttypen) zijn precies de gevallen waar dat misging. RVZ-011 valt
nu terug op zijn kenmerken (`Drempelbreedte, Drempelniveau, Maaiveldhoogte,
Putdekselniveau`), ATTR-014 op `alle kenmerken`, en ADM-007 -- die geen van beide
declareert -- krijgt niets: dan zwijgt de uitvoer erover in plaats van iets te beweren.

**Waarom.** Eén kolom `bekeken` mengde 95, 45.803 en 459.108 zonder dat er iets bij stond,
en `percentage_populatie` in de GeoPackage deelt door precies dat ongelabelde getal --
de percentages waren daardoor onderling onvergelijkbaar. Het is nadrukkelijk een
labelprobleem en geen rekenfout: HGT-011 (bekeken 79 op Koekangerveld) en RVZ-002
(bekeken 0) tellen verschillende rollen -- `netwerkknopen` tegenover `overstortputten`
-- en géén van beide telt de klasse `Overstortdrempel`, want dat is een `Wand`-onderdeel
en geen knoop. De getallen gelijktrekken zou de fout zijn.

**Meting (`scripts/analyse_scope_per_check.py`, `36d2a2f`).** Alle 99 checks, twee runs
op `dewoldenhoogeveen_orox.ttl` met `configs/dewoldenhoogeveen.toml`:

| scope | aantal checks | voorbeeld | bekeken (gemeentebreed) | bekeken (Koekangerveld) |
|---|---:|---|---:|---:|
| `analyseset` | 95 | HGT-011 (`netwerkknopen`) | 22.363 | 79 |
| `volledige_export` | 2 | ADM-002 (`leidingen, netwerkknopen`) | 45.803 | 45.803 |
| `attribuut_instanties` | 2 | ATTR-014 (`alle kenmerken`) | 459.108 | 459.108 |

De andere twee: ATTR-015 (`volledige_export`, 29.087 gedateerde objecten) en BTR-006
(`attribuut_instanties`, 57.569 hoogtewaarden gemeentebreed, 161 op Koekangerveld).
ATTR-018 op Koekangerveld leest nu als "36 bevindingen op 119 bekeken (analyseset; gaat
over: leidingen, putten, vrijvervalrioolleidingen)". Let op het verschil met de 39 putten uit
`scripts/analyse_begindatum.py`: dat script telt de **kern**, terwijl `bekeken` de
analyseset telt -- kern plus contextschil, hier 78 putten plus 41 vrijvervalstrengen. Het
jaartalgat zelf is geen bug (3 van 39 Koekangerveldse putten dragen een `Begindatum`,
gemeentebreed 11.695 van 20.758, `aspect-zonder-datum` overal 0); deze duiding maakt het
alleen leesbaar.

**Alternatieven.** Twee waarden in plaats van drie en de instantietellers onder
`volledige_export` scharen (verworpen: dan staat 459.108 als "objecten" naast 45.803).
De scope uit `examined()` afleiden in plaats van hem te declareren (verworpen: er is niets
in de code dat objecten van instanties onderscheidt; een heuristiek zou stil verkeerd
kunnen labelen). Het veld `scope` noemen (verworpen: `Melding.scope` draagt in hetzelfde
JSON-bestand al een andere betekenis -- `binnen_studiegebied` of `geen_studiegebied`).
De noemers gelijktrekken (verworpen: het is een labelprobleem, zie hierboven). Het label
ook in de meldingen-CSV zetten (verworpen: zie BO-7). De populatie weglaten nu zij geen
noemer is (verworpen: zonder haar zegt een rij alleen nog "43 bekeken (analyseset)" en is
niet te zien waar de check over gaat; achter "gaat over" is zij precies wat zij is). Voor
een check zonder rollen én zonder kenmerken iets verzinnen -- "alle objecten", "de hele
export" (verworpen: dat is de fout die dit besluit wegneemt; zwijgen is hier eerlijk, en de
regel "Toetst ..." eronder zegt al dat de check niet tot een rol beperkt is).

**Contractbreuk.** Geen. `checks` is een optioneel, additief enveloppeveld en
`schema_versie` blijft daarom `1.1`, conform de versioneringsregel in
`docs/json-schema.md`. `overzicht_checks` krijgt er twee kolommen bij; bestaande
kolommen blijven ongewijzigd, en een lezer die op naam selecteert merkt er niets van.
De checktabel in het Markdown-rapport is twee kolommen breder.

### BO-59 De systemisch-vlag geldt pas vanaf 100 bekeken objecten

**Besluit.** `melding._is_systemisch` toetst de populatieratio (`bevindingen / bekeken >
systemisch_drempel`) alleen nog boven een minimumpopulatie: `[rapport]
systemisch_minimum_bekeken`, standaard **100** bekeken objecten. Daaronder is een uitslag
nooit systemisch, hoe hoog de ratio ook is. De vlag die een check zelf zet
(`Finding.systemisch`, ATTR-014/ATTR-015) staat hier los van en verandert niet; de
nulmeting heeft haar eigen bepaling per (vorm, objecttype) en blijft ook ongemoeid.

**Waarom een minimum.** De vlag is een uitspraak over de export als geheel: "dit gebrek
onderscheidt dit object niet van zijn buren, dus zet het niet even zwaar op de kaart". Die
uitspraak leunt op een populatie die groot genoeg is om er iets over te zeggen. Op een klein
gebied is zij onwaar en schadelijk. Issue #75 maakte `examined` van RVZ-006 de gemengde
strengen; op Koekangerveld zijn dat er 26 en slaat de check op alle 26 aan (ratio 1,00). De
vouwing van issue #76 haalde die meldingen daarna uit de kaartpopup en uit de tabel per
object, en het `gemengd_zonder_overstort`-vlak kreeg via `bepaal_status` de status *groen*,
met de tekst "geen eigen gebrek" -- terwijl elk vlak in die laag per constructie een
gebrek is. Een echt gebrek in een klein gebied verdween zo uit precies de views waarvoor het
bedoeld was. Hetzelfde geldt voor elke gebiedsrun: hoe kleiner het gebied, hoe eerder een
check "systemisch" heet.

**Waarom 100.** Een ronde ondergrens, ruim boven het bereik waarin de breuk toevallig hoog
uitvalt en ruim onder de populaties waar de vlag voor bedoeld is. Gemeten op De Wolden en
Hoogeveen (`configs/dewoldenhoogeveen.toml`, door de echte pijplijn) zijn er precies twee
uitslagen boven de ratiodrempel: RVZ-002 en RVZ-003, allebei 245 van 245 -- die blijven dus
systemisch, zoals bedoeld, want dat *is* een structureel verschijnsel over de hele export.
ATTR-014 blijft systemisch omdat de check dat zelf declareert. Aan de andere kant valt
RVZ-006 op Koekangerveld (26 van 26) er nu buiten en staat weer gewoon op de kaart. Er is
geen uitslag met een populatie tussen 26 en 245 die boven de drempel uitkomt, dus elke
waarde in dat bereik levert vandaag dezelfde uitkomst; 100 is de ronde waarde in het midden
en houdt marge naar beide kanten.

**Wat de auteur kan bijstellen.** `systemisch_minimum_bekeken` staat in `[rapport]` van
`src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml`, naast
`systemisch_drempel`. Op 1 zetten geeft het gedrag van vóór dit besluit terug (de
fixturetests doen dat, want fixtures tellen een handvol objecten). Hoger zetten maakt de
vlag zeldzamer; hij mag niet op 0, want een ratio over nul bekeken objecten bestaat niet.

**Alternatieven.** De ratio afhankelijk maken van de gebiedsgrootte (verworpen: dan
betekent "systemisch" opnieuw iets anders naargelang er een studiegebied is, precies wat de
correctie in BO-28 wegnam). Alleen de vlakkenlaag repareren en de vlag laten staan
(verworpen: dat is de helft -- de gemelde strengen zelf lezen dan nog steeds "geen eigen
gebrek" in hun popup; die kant is los daarvan wél gerepareerd, zie hieronder). RVZ-006
uitzonderen (verworpen: het is geen eigenschap van die check maar van kleine populaties,
en de volgende check met een smalle populatie loopt er weer in).

**Tweede helft: het vlak leidt zijn status niet meer af uit gefilterde meldingen.**
`gpkg._gemengd_rij` gaf de meldingen van het deelstelsel aan `bepaal_status` en
`popup_html`, die allebei systemische meldingen wegfilteren. Een rij in de laag
`gemengd_zonder_overstort` bestaat echter alleen omdat RVZ-006 op dat deelstelsel aansloeg;
er is daar geen "geen eigen gebrek"-toestand. De rij bepaalt haar status daarom nu uit de
ernst van haar eigen meldingen en toont ze in de popup, ook als zij systemisch heten. Dat is
geen uitzondering op BO-29: die regel gaat over objecten waarvan de systemische meldingen
één van vele soorten zijn, terwijl dit vlak niets anders draagt dan de bevinding die hem
liet bestaan.

### BO-60 ADM-011 vervalt: een losgekoppelde loze leiding is de gewenste eindtoestand

**Wat.** ADM-011 (W, Consistentie) vervalt. De check meldde per loze streng dat haar keten in
de administratieve afvoerrichting nergens op het actieve riool aansluit -- geval
`losgekoppeld` -- en noemde dat dode data. Het ID wordt niet hergebruikt; het register zet
ADM-011 in de tabel *Vervallen checks* naast EXT-008, niet in *Geschrapte checks*, want de
nulmeting dekt hem niet: er kijkt niets meer naar en dat is precies de bedoeling. ADM-010 (F)
blijft ongewijzigd, inclusief zijn gevallen (`doorgaand`, `aanvoer`, `afvoer`), zijn
detailvelden en zijn ketenbouw.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit (PRE-2,
`docs/checks-audit-2026-08.md`). Bij de handmatige steekproef op `ID8364-ID8365-1` schreef hij:
"dit is geen fout, maar dit is hoe het hoort te zijn: een loze leiding moet geen bovenstrooms
in gebruik zijnde riolen hebben, want dan is hij niet loos." Een `LozeLeiding` is buiten
gebruik gesteld; dat zij netjes van het actieve net is losgekoppeld is het eindbeeld waar het
beheer naartoe werkt. De check meldde dus de gewenste toestand als gebrek, en er is geen
handelingsperspectief: er valt niets te herstellen. Het omgekeerde geval -- actief riool dat
wel op een loze keten aansluit -- is het echte gebrek en dat meldt ADM-010 al volledig.

**Wat er in de engine blijft staan.** De ketenbouw (`_bouw_loze_ketens`), het geval
`losgekoppeld` en de telling ervan in de verantwoording van ADM-010. Die verantwoording blijft
melden hoeveel ketens en strengen er per geval zijn, dus "14 losgekoppeld (16 strengen)" staat
nog gewoon in het rapport -- als feit over de dataset, niet als bevinding. Wat wel weg is: de
meldingstekst voor `losgekoppeld` en de zin die daarin de actieve strengen noemde die een
ketenknoop wel raken maar niet in de afvoerrichting aansluiten. Het detail `rakend` zelf blijft
op de ADM-010-meldingen staan; het is daar een gemeten feit en het weghalen zou de uitvoer van
ADM-010 veranderen, en die blijft ongemoeid.

**Verwacht effect op De Wolden en Hoogeveen.** De 16 ADM-011-waarschuwingen (14 losgekoppelde
ketens) verdwijnen; de 38 ADM-010-fouten blijven ongewijzigd ten opzichte van
`uitvoer/audit_27082026`. De hermeting hoort bij blok A van de auditregie, niet bij dit besluit.

**Alternatieven.** De conditie omkeren, zodat een loze leiding *met* bovenstrooms actief riool
gemeld wordt (verworpen: dat is letterlijk ADM-010 en zou het ID een tweede betekenis geven,
terwijl `vergelijk` meetmomenten op check-ID naast elkaar zet). De ernst verlagen naar een
notitie (verworpen: een melding zonder handelingsperspectief hoort niet in de bevindingen,
ongeacht haar gewicht; de telling in de verantwoording van ADM-010 dekt de informatiebehoefte
al). Het ID hergebruiken voor een andere loze-leidingcheck (verworpen: harde regel, vervallen
ID's worden nooit hergebruikt).

### BO-61 ATTR-008 geschrapt: de nulmeting toetst exact hetzelfde lengtebereik

**Wat.** ATTR-008 (W, Plausibiliteit, "Strenglengte korter dan X m of langer dan X m") vervalt
uit de engine. Anders dan ADM-011 (BO-60) gaat hij niet naar de tabel *Vervallen checks* maar
naar *Geschrapte checks*: de nulmeting dekt hem aantoonbaar, dus hij krijgt -- zoals voorwaarde
3 van de schrapronde eist -- een sentinel in `src/nlriochecker/dekking.toml`, met
`LengteLeiding_val` als bewijsvorm in alle drie de conformiteitsklassen. Dat is letterlijk
dezelfde sentinel als die van ATTR-011. Het ID ATTR-008 wordt niet hergebruikt.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, ATTR-sectie en waarneming 4). De drempels van ATTR-008 zijn
met issue #35 op de grenzen van het GWSW-datatype `Dt_LengteLeiding` gezet (1-75 m), omdat GWSW
leidend is. Precies dat bereik toetst de SHACL-vorm `LengteLeiding_val`. Gemeten op De Wolden en
Hoogeveen (audit 27-08): alle 443 ATTR-008-objecten staan óók in `LengteLeiding_val`. De
overlap is niet gedeeltelijk maar volledig, en de vorm is bovendien breder -- zij telt er 932,
want zij ziet ook drains, duikers en aansluitleidingen, en daar bovenop 1.955 meldingen op
mechanisch riool die de projectconfiguratie onderdrukt. De check voegde dus niets toe: elk
gemeld object werd twee keer gemeld, één keer door de nulmeting en één keer door ons.

**Wat er blijft staan.** ATTR-009 (geometrische lengte tegen administratieve lengte) blijft
ongewijzigd: die vergelijkt twee bronnen met elkaar in plaats van één waarde met een bereik, en
de nulmeting kent de hartlijn niet. ATTR-005 verwees in zijn `notes()` naar ATTR-008 als de
plek waar lengtewaarden getoetst worden; die zin noemt nu `LengteLeiding_val`. Ook de twee
drempels `minimale_strenglengte_m` en `maximale_strenglengte_m` blijven in alle drie de
configbestanden staan, met een regel erbij dat geen check ze meer leest. Ze weghalen is een
losse beslissing en geen gevolg van deze: `CheckThresholds` staat op `extra="forbid"`, dus een
bestaande projectconfiguratie die de sleutels draagt zou na verwijdering niet meer laden. Dat
is een wijziging aan het configuratiecontract, en die hoort een eigen besluit te zijn -- niet
een bijvangst van een schrapping. Zolang de sleutels er staan houdt
`test_maximale_strenglengte_volgt_de_ontologie` hun waarde op de ontologiegrens.

**Verwacht effect op De Wolden en Hoogeveen.** De 443 ATTR-008-waarschuwingen verdwijnen uit de
bevindingen; de gevallen zelf blijven zichtbaar in het nulmetingblok van het rapport, onder de
vorm `LengteLeiding_val`. Er gaat dus geen signaal verloren, alleen een dubbeling. De hermeting
hoort bij blok A van de auditregie, niet bij dit besluit.

**Alternatieven.** De drempels losmaken van het datatype en er een plausibiliteitsband van
maken die stríkt binnen 1-75 m ligt, zodat de check wél iets toevoegt (verworpen door de
auteur: dat is een projectkeuze zonder bron, terwijl GWSW hier een expliciet bereik declareert;
een band die strenger is dan de ontologie zou strengen afkeuren die het model goedkeurt).
ATTR-008 als *vervallen* boeken zoals ADM-011 (verworpen: dat zou zeggen dat er niets meer naar
kijkt, en dat is aantoonbaar onwaar -- de nulmeting kijkt ernaar, en dan is de sentinel de
manier om die dekking te blijven bewaken). Het ID hergebruiken voor een andere lengtecheck
(verworpen: harde regel, vervallen ID's worden nooit hergebruikt).

### BO-62 BTR-002 vervalt voor nu: de inwinningswijze staat niet op de BOB's

**Wat.** BTR-002 (W, Traceerbaarheid, "Kritieke kenmerken ingewonnen via schatting, plan of
ontwerp in plaats van meting") vervalt uit de engine en gaat in het register naar de tabel
*Vervallen checks*, niet naar *Geschrapte checks*: de nulmeting toetst de inwinningswijze
nergens, dus er kijkt na dit besluit niets meer naar. Het skelet en zijn `reden` verdwijnen
mee. Het ID wordt niet hergebruikt.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, BTR-sectie). De check kan op deze aanlevering geen uitslag
geven: de wijze staat op 537 van de 46.880 BOB's en op 10.050 van de 22.363 maaiveldhoogten,
en zij hangt bovendien aan de puntgeometrie in plaats van aan het kenmerk. De audit bood één
tussenstap aan -- de check alleen op de maaiveldhoogte bouwen, waar 6.455 van de 10.050
gevulde waarden expliciet niet-gemeten zijn (`AHN2` of `NietAchterhaald`) -- en de auteur
heeft die afgewezen: dat versmalt de check ten opzichte van het register, dat over álle
kritieke kenmerken gaat.

**Waarom "voor nu", en waarom geen sentinel.** Het besluit hangt aan de bron en niet aan het
begrip. Levert een volgende export `WijzeVanInwinning` op de BOB's zelf, dan is deze toets
weer zinvol; hij keert dan terug onder een nieuw ID, want vervallen ID's worden nooit
hergebruikt. Een dekking-sentinel in `dekking.toml` hoort hier niet: die is het bewijs dat de
nulmeting een geschrapte check dekt (voorwaarde 3 van de schrapronde), en dat is hier
aantoonbaar niet zo. De vindplaats van het besluit is dit BO plus de registerregel.

**Wat er blijft staan.** BTR-001 (dezelfde metagegevens, vanaf de kant van het ontbreken),
BTR-003 en BTR-004 blijven skelet; BTR-006 blijft gebouwd. De kanttekening bij HGT-001 en
HGT-002 leest de inwinningswijze gewoon door: `[inwinning] uit_hoogtemodel` en
`[inwinning] onbekend` blijven ongewijzigd in de configuratie en worden door die twee checks
gelezen. Er raakt dus geen configuratiesleutel wees.

**Verwacht effect op De Wolden en Hoogeveen.** Eén "bekeken 0"-regel met de markering *vereist
inwinningsmetagegevens* verdwijnt uit het rapport. Er verdwijnt geen enkele melding: de check
stond op nul. De hermeting hoort bij blok A van de auditregie, niet bij dit besluit.

**Alternatieven.** De tussenstap op alleen de maaiveldhoogte bouwen (verworpen door de auteur,
zie hierboven). Het skelet laten staan omdat het zichtbaar maakt wat er ontbreekt (verworpen:
dat argument geldt nog voor BTR-001, dat precies over het ontbreken van de metagegevens gaat;
een tweede skelet op dezelfde lege bron voegt daar niets aan toe).

### BO-63 BTR-005 vervalt voor nu: inspectiegegevens noch risicowegingsbron bestaan

**Wat.** BTR-005 (W, Actualiteit, "Toestands- of inspectiegegevens ouder dan drempel, gewogen
naar risicoligging") vervalt uit de engine en gaat in het register naar de tabel *Vervallen
checks*. Het skelet en zijn `reden` verdwijnen mee. Het ID wordt niet hergebruikt.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, BTR-sectie), die BTR-005 de laagste prioriteit van de vijf
skeletten gaf en hem als enige BTR-kandidaat om te laten vervallen aanwees. Hij vraagt twee
dingen die er geen van beide zijn: inspectie- of toestandsgegevens in de GWSW-export, en een
bron voor de risicoligging (spoor, dijk, wegfunctie). Die weging is bovendien geen
GWSW-begrip; zij vraagt externe bronnen die buiten de EXT-scope van deze fase vallen. Er is
ook geen drempel voor geconfigureerd, dus er raakt geen configuratiesleutel wees.

**Waarom "voor nu", en waarom geen sentinel.** Zoals BO-62: het besluit hangt aan de twee
ontbrekende bronnen. Komen er inspectiedata én een risicowegingsbron, dan keert de toets
terug onder een nieuw ID. Een sentinel in `dekking.toml` hoort hier niet -- de nulmeting kent
geen inspectiegegevens en dekt hem dus niet.

**Verwacht effect op De Wolden en Hoogeveen.** Eén "bekeken 0"-regel verdwijnt uit het
rapport; er verdwijnt geen melding, want de check stond op nul. `docs/nwb-voorstel.md` noemde
BTR-005 als de sterkste kandidaat om de NWB-wegvakken aan op te hangen, met als aanbeveling
"bouw hier nu niets mee"; dat spoor loopt niet meer via déze check. De NWB-laag zelf verandert
niet: zij wordt geladen en door geen enkele check gelezen, precies zoals daarvoor.

**Alternatieven.** Alleen de leeftijdshelft bouwen, zonder risicoweging (verworpen: er zijn
ook geen inspectiedata, dus er valt geen leeftijd te meten -- dit is niet één ontbrekende
bron maar twee). Het skelet laten staan (verworpen op dezelfde grond als BO-62).

### BO-64 EXT-005 vervalt voor nu: er is geen bruikbare putdeksellaag

**Wat.** EXT-005 (W, Compleetheid, "Put zonder BGT-putdeksel binnen X m") vervalt uit de
engine en gaat in het register naar de tabel *Vervallen checks*. Het ID wordt niet
hergebruikt. Anders dan bij BTR-002 en BTR-005 gaat het hier niet om een skelet maar om een
volledig gebouwde check: de code verdwijnt, met haar tests.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, EXT-sectie). De aangeleverde BGT-laag `put` is geen
putdekselbron: zij telt 843 objecten, waarvan 595 van ProRail en 72 van de twee gemeenten
samen, tegenover ruim 23.000 GWSW-putten. Dat is spoorinfrastructuur. `configs/dewoldenhoogeveen.toml`
zette de rol daarom al leeg (`bgt_putdeksellagen = []`), zodat de check netjes oversloeg met
"laag niet aanwezig in aangeleverde data". De audit stelde als aanleveringsvraag of er een
gemeentelijke deksellaag bestaat die het gebied wél dekt; het antwoord van de auteur is nee,
en die komt er ook niet.

**Waarom "voor nu", en waarom geen sentinel.** Het besluit hangt aan de bron. Komt er alsnog
een deksellaag die het studiegebied dekt, dan is deze toets weer zinvol en keert hij terug
onder een nieuw ID. Een sentinel in `dekking.toml` hoort hier niet: de nulmeting kent geen
BGT en dekt deze check niet -- er kijkt na dit besluit niets meer naar, en dat is precies wat
de tabel *Vervallen checks* zegt.

**Wat er blijft staan, en waarom.** De bron-rol `bgt_putdeksel` blijft in
`externedata.ROLLEN`, en de sleutels `bgt_putdeksellagen` en `ext_putdeksel_afstand_m` blijven
in alle drie de configbestanden staan, elk met een regel dat geen check ze meer leest. Dezelfde
redenering als in BO-61: `CheckThresholds` en `ExternalSources` staan op `extra="forbid"`, dus een
bestaande projectconfiguratie die de sleutels draagt zou na verwijdering niet meer laden. Dat
is een wijziging aan het configuratiecontract en hoort een eigen besluit te zijn, geen bijvangst
van een schrapping. Twee gevolgen die je moet kennen zolang ze er staan: een aangeleverde
`put`-laag wordt nog steeds geladen én op dekking getoetst, dus een te klein extract van een
laag die niemand meer leest kan de harde dekkingspoort raken; en `ext_zoekafstand_max_m` telt
`ext_putdeksel_afstand_m` (2,0 m) nog mee in de marge van diezelfde poort -- zonder gevolg,
want `ext_lozingspunt_water_afstand_m` (10,0 m) is groter. De voorbeeldsleutel in de melding
van de dekkingspoort noemt daarom niet langer `bgt_putdeksellagen` maar `bgt_waterlagen`, een
laag die nog wel checks bedient.

**Verwacht effect op De Wolden en Hoogeveen.** Eén "bekeken 0"-regel verdwijnt uit het
rapport; er verdwijnt geen melding, want de check sloeg over. De hermeting hoort bij blok A van
de auditregie, niet bij dit besluit.

**Alternatieven.** De check laten staan zodat de overslag zichtbaar blijft (verworpen: de
overslag was luid en correct, maar zij herhaalt per run een aanleveringsvraag die inmiddels
beantwoord is -- het antwoord staat nu hier in plaats van in elk rapport). De `put`-laag toch
als deksellaag gebruiken (verworpen: 595 van de 843 objecten zijn ProRail; dat zou 23.000
putten als dekselloos melden en dat is een uitspraak over de bron, niet over de beheerdata).

### BO-65 EXT-006 vervalt voor nu, met EXT-005 mee

**Wat.** EXT-006 (W, Compleetheid, "BGT-putdeksel zonder put in de beheerdata") vervalt uit de
engine en gaat in het register naar de tabel *Vervallen checks*. Het ID wordt niet hergebruikt.
Een eigen BO en niet een alinea in BO-64, omdat elk vervallen ID zijn eigen vindplaats hoort te
hebben -- maar de grond is dezelfde en dit BO is er de spiegelzijde van.

**Waarom.** Zoals BO-64: EXT-006 is dezelfde vraag van de andere kant (elk BGT-deksel zonder
GWSW-put binnen 2,0 m), leest dezelfde rol `bgt_putdeksel`, en staat of valt dus met dezelfde
ontbrekende bron. De auditregel zei het al met zoveel woorden: "de twee staan of vallen met
dezelfde bron".

**Wat er met hem verdwijnt.** EXT-006 was de enige check die een bevinding op een object buiten
de GWSW-dataset legde: de bevinding hing aan het BGT-deksel en droeg zijn RD-coordinaat zelf
(`Finding.location`), zodat zij bij de afbakening tot een studiegebied niet wegviel. Die weg
blijft in de uitvoer bestaan (`uitvoer/locatie.foutlocatie` en de kolommen `x`/`y` van de
meldingentabel) en wordt door `tests/test_uitvoer_locatie.py` bewaakt, maar er is nu geen check
meer die hem vult. Dat is bewust: de mechaniek weghalen zou een tweede, veel bredere ingreep in
de uitvoer zijn, en de eerstvolgende check op een externe bron heeft hem weer nodig.

**Verwacht effect op De Wolden en Hoogeveen.** Eén "bekeken 0"-regel verdwijnt uit het rapport;
er verdwijnt geen melding.

**Alternatieven.** EXT-006 laten staan en alleen EXT-005 laten vervallen (verworpen: dan zou de
helft van een spiegelpaar blijven draaien op een bron die er niet is, en zou het rapport
suggereren dat de dekselvergelijking nog ergens gebeurt).

### BO-66 EXT-002 vervalt: de kale watergangkruising draagt geen handelingsperspectief

**Wat.** EXT-002 (W, Plausibiliteit, "Kruising met watergang (waterschaps- of BGT-data)")
vervalt uit de engine en gaat in het register naar de tabel *Vervallen checks*, op de eerste
grond die die tabel noemt: niet relevant voor deze opdracht. Het ID wordt niet hergebruikt.
EXT-003 blijft ongewijzigd en is voortaan de enige watergangmelding.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, PRE-4). Een streng die een watergang kruist is op zichzelf
geen gebrek -- dat gebeurt overal -- en er valt niets aan te herstellen. Het gebrek is dat zo'n
kruising niet als zinker geregistreerd staat, en dat meldt EXT-003. De meting maakt dat hard:
op De Wolden en Hoogeveen melden de twee exact dezelfde 281 strengen en dezelfde 319
doorkruisingen (audit 27-08, gemeten met `scripts/checkaudit_meting.py`), omdat de export geen
enkele als zinker geregistreerde streng bevat. Elke gemelde kruising kwam dus twee keer in de
bevindingen, één keer zonder en één keer met handelingsperspectief. De steekproef vroeg om
precies die samenvoeging: "Kunnen we dit niet combineren met de andere watergang check?"

**Waarom geen sentinel, en geen datalaag.** Geen sentinel in `dekking.toml`: de nulmeting kent
de BGT niet en dekt deze check niet, dus er kijkt na dit besluit niets meer naar de kale
kruising -- en dat is de bedoeling. De audit stelde als alternatief voor EXT-002 te laten
voortleven als GeoPackage-datalaag met alle doorkruisingen; de auteur heeft dat verworpen ("niet
relevant"). Er komt dus geen vervangende laag en geen vervangende telling: wat er blijft is de
telling in de toelichting van EXT-003, die elke doorkruising binnen de zoekstraal noemt,
inclusief die van een geregistreerde zinker.

**Wat er in de engine blijft staan.** De hele kruisingsdetectie: `_verhouding` met het
doorkruisingscriterium van BO-43, `_zoek_kruisingen`, de gedeelde cache-ingang
`ext:watergangkruisingen` en de basisklasse `_WatergangKruising` met haar populatie,
`buiten_populatie()` (de duikertelling van BO-25) en haar afvaltellingen. EXT-003 hangt daar als
enige nog onder; de basis is niet in de check gevouwen omdat zij de populatie, de toets en de
tellingen bij elkaar houdt en dit besluit alleen over de melding gaat. Eén regel is van EXT-002
naar EXT-003 verhuisd in plaats van weggevallen: "Waterschapsdata is niet aangeleverd; alleen de
BGT-waterdelen zijn gebruikt." Zonder die verhuizing zou het rapport niet meer zeggen op welke
waterbron getoetst is, terwijl het register die tweede bron expliciet toestaat.

**Gevolg voor de laag `vlakken` in de GeoPackage.** De watervlakken blijven bestaan en komen nu
uitsluitend van EXT-003, dat zijn doorkruiste waterdeel zelf als treffer registreert. `VLAK_CHECKS`
in `uitvoer/gpkg.py` gaat van drie naar twee ID's; de structuur van de laag (kolommen, `soort`,
`gwsw_run.n_vlakken`) verandert niet. Wat wél verdwijnt is het vlak dat alleen EXT-002 aanwees:
een doorkruising door een als zinker geregistreerde streng kreeg sinds issue #67 een vlak met
`check_ids = "EXT-002"`, en dat vlak hoort bij een melding die niet meer bestaat -- de laag toont
per constructie exact de externe objecten waarnaar de meldingen van díé uitvoer verwijzen. Op De
Wolden en Hoogeveen kost dat nul vlakken, want er is geen enkele zinker. `check_ids` op een
watervlak leest voortaan altijd `EXT-003`.

**Verwacht effect op De Wolden en Hoogeveen.** De 319 EXT-002-waarschuwingen (281 strengen)
verdwijnen; EXT-003 blijft op 319 waarschuwingen en 281 strengen. Er gaat geen signaal verloren,
alleen een dubbeling. De hermeting hoort bij blok B van de auditregie, niet bij dit besluit.

**Alternatieven.** EXT-002 laten voortleven als GeoPackage-datalaag (het PRE-4-voorstel uit de
audit; verworpen door de auteur). EXT-003 laten vervallen en EXT-002 houden (verworpen: dan
blijft juist de melding zonder handelingsperspectief over). De twee samenvoegen tot één check
onder een nieuw ID (verworpen: EXT-003 is al precies die check, en een nieuw ID zou een
trendvergelijking op check-ID breken zonder dat er iets aan de uitslag verandert). Het ID
EXT-002 hergebruiken (verworpen: harde regel, vervallen ID's worden nooit hergebruikt).

### BO-67 EXT-007 toetst alleen de lozingspunten die op oppervlaktewater lozen

**Wat.** De populatie van EXT-007 ("Lozingspunt zonder watergang binnen X m") is niet langer de
brede rol `lozingspunten` maar de nieuwe, engere rol `waterlozingspunten`: precies de klassen
waarvan de GWSW-ontologie zegt dat zij op oppervlaktewater lozen. De lijst staat als
`[klassen] waterlozingspunt` in beide configbestanden en als default in `ClassRoots`, niet in de
code van de check. De brede rol `lozingspunten` (`[klassen] lozings_eindpunt`) blijft ongewijzigd:
NET-001, NET-002 en NET-008 hebben haar als netwerkeindpunt nodig, en daar telt elke uitweg uit
het stelsel mee. ID, titel, ernst, dimensie en de drempel `ext_lozingspunt_water_afstand_m`
blijven zoals ze waren.

**De lijst, en het bewijs per klasse** (gebundelde ontologie uit `gwsw-orox-helpers`,
`Ontologie_GWSW_Totaal.ttl`; elke regel nagezocht):

| Klasse | In de lijst | Definitie in de ontologie |
|---|---|---|
| `Uitlaatconstructie` | ja | "De constructie waar uitstroming van water uit een leiding naar het oppervlaktewater mogelijk is." Een `Bouwwerk`; `Nooduitlaat` en `Uitstroombak` hangen eronder en komen via de subklasse-afsluiting mee |
| `UitlaatPunt` | ja | "Het punt waar uitstroming van water uit een leiding naar het oppervlaktewater mogelijk is." Een `Aansluitpunt` en dus een `Knooppunt`: hij staat op de orientatie, niet op het object |
| `LozingspuntOppervlaktewater` | ja | "Locatie van de lozing bevindt zich in het oppervlaktewater." Subklasse van `Lozingspunt` |
| `Lozingsput` | **nee** | "Een put waarop een rioolleiding is aangesloten waarmee het afvalwater het rioolstelsel verlaat naar, of ontvangt uit, een **ander rioolstelsel**." Een `Rioolput`; daar hoort per definitie geen open water te liggen |
| `Lozingspunt` (de wortel) | **nee** | "Een knooppunt in een stelsel waar het afvalwater het stelsel verlaat of binnenkomt" -- de ontologie splitst hem zelf in `LozingspuntOppervlaktewater` en `LozingspuntBodem`, dus de wortel zegt niet waarop geloosd wordt. Hem opnemen zou `LozingspuntBodem` ("locatie van de lozing bevindt zich in de bodem") meenemen |

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, EXT-007), met de opdracht GWSW-conform te blijven. De steekproef
wees het aan: "je hebt uitlaten/uitstroompunten waarbij je hemelwater OF overstortwater op een
oppervlaktewaterlichaam brengt. En je hebt locaties waar afvalwater, vaak uit mechanisch riool,
wordt geloosd op een gemengd stelsel in een kern." De meting bevestigt de omvang: van de 71
meldingen op De Wolden en Hoogeveen stonden er 32 op een `Lozingsput` (58% van de 55
lozingsputten) tegenover 39 op een `Uitlaatconstructie` (5% van de 712). Bij een lozingsput is
"geen watergang binnen 10 m" geen gebrek maar de verwachte toestand, en een melding zonder
handelingsperspectief kost de andere 39 hun geloofwaardigheid.

**Waarom een eigen rol en niet een filter in de check.** De klassenlijst hoort in de
configuratie (harde regel: geen hardgecodeerde drempels of klassenlijsten), en zodra hij daar
staat is een rolfunctie in `checks/selectie.py` de bestaande weg om hem te lezen -- met de
cachesleutel, de rollentelling in het rapport, de nul-bewaking (`SIG-nulklasse`) en de
dekkingsmatrix die daaraan vastzitten. EXT-007 declareert daarom `rollen = ("lozingspunten",
"waterlozingspunten")`: de smalle rol is zijn populatie, de brede leest hij alleen in `notes()`,
om te tellen hoeveel lozingspunten buiten de check vallen. Dat is precies wat de declaratie
belooft -- de vereniging van wat `run()`, `examined()` en `notes()` aanraken, een bovengrens en
geen noemer (BO-58).

**Wat het rapport erover zegt.** Twee regels in de toelichting van EXT-007: welke klassen
meetellen (met de configsleutel erbij) en hoeveel lozingspunten uit de bredere rol buiten de
check vielen, met de reden. Stilte zou hier lezen als "alle lozingspunten zijn getoetst".

**Verwacht effect op De Wolden en Hoogeveen.** 71 → 39 waarschuwingen; de bekeken populatie
zakt van 767 naar 712. `UitlaatPunt` en `LozingspuntOppervlaktewater` hebben in deze aanlevering
nul instanties -- dat is een gat in de aanlevering en geen reden om ze uit de lijst te laten
(de klassen bestaan in de ontologie, en dat is wat de lijst uitdrukt). De rol als geheel staat
niet op nul, dus er komt geen `SIG-nulklasse`-signaal bij. De hermeting hoort bij blok B van de
auditregie, niet bij dit besluit.

**Niet besloten, en dus niet gedaan.** De omgekeerde toets uit de audit -- een `Lozingsput` die
wél in het water ligt is verdacht -- blijft buiten dit besluit. Zij vraagt een eigen check-ID en
een eigen afweging.

**Alternatieven.** Een filter in `run()` op `dataset.is_a` met een klassenlijst in de code
(verworpen: hardgecodeerde klassenlijst, en de rollentelling en nul-bewaking zouden de smalle
populatie niet zien). De rol `lozingspunten` zelf versmallen (verworpen: NET-001/002/008 melden
dan elke vuilwaterstreng die op een lozingsput eindigt als onbereikbaar). `Lozingspunt` als
wortel opnemen (verworpen: `LozingspuntBodem` hangt eronder). EXT-007 helemaal laten vervallen
(verworpen: de 39 meldingen op uitlaatconstructies zijn wél een signaal).

### BO-68 HGT-003: de maximale diepteligging gaat van 3,0 naar 4,0 m

**Wat.** De drempel `bob_maximale_diepte_m` gaat van 3,0 naar **4,0 m**: hoe diep een BOB onder
het AHN-maaiveld mag liggen voordat HGT-003 dat onaannemelijk noemt. De waarde staat op de drie
gebruikelijke plekken (default in `CheckThresholds`, `src/nlriochecker/checks.toml` en
`configs/dewoldenhoogeveen.toml`) en nergens anders. De tweede tak van de check -- een BOB bóven
het AHN-maaiveld -- verandert niet: die is altijd fout en kent geen drempel. ID, ernst (F) en
dimensie (Plausibiliteit) blijven zoals ze waren.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08, uit de checkaudit
(`docs/checks-audit-2026-08.md`, HGT-003; het diepteligging-punt van #69). De 3,0 m kwam uit het
checkregister v0.9 ("meer dan 3 m eronder") en droeg geen externe bron. De research van 28-08
levert er wel een: het *PvE Functionele eisen vrijverval riolering* van de gemeente Rotterdam
(https://www.rotterdam.nl/media/2019) stelt de maximale aanlegdiepte -- BOB ten opzichte van
maaiveld -- in **nieuw** gebied op 3,0 m. Een landelijke máximumnorm bestaat niet; de Leidraad
Riolering normeert de mínimale gronddekking, niet de maximale diepte. In bestaand gebied ligt
riool legitiem dieper (bergings- en transportriolen), en de check draait op bestaand gebied. 4,0 m
is daarom die ontwerpnorm plus marge: onder de 4 m is een diepe ligging normaal, erboven is zij
het bekijken waard.

**Wat de meting zegt** (audit 27-08, `scripts/checkaudit_meting.py`, De Wolden en Hoogeveen).
HGT-003 gaf 1.090 fouten: 48 "BOB boven het AHN-maaiveld" en 1.042 "dieper dan 3 m". De verdeling
van die diepte: minimum 3,00 m, mediaan 3,37 m, p90 4,12 m, p99 7,84 m, maximum 11,75 m. Boven
4 m blijven er 123 over, boven 5 m 19 en boven 6 m 18. De mediaan van de huidige uitslag is dus
gewone rioleringsdiepte, en juist daar is het handelingsperspectief het zwakst: bij 3 tot 4 m valt
er meestal niets te herstellen. De steekproef zei hetzelfde in andere woorden
(`Ho6H0716-Ho6H0720-1`: "goed, met dezelfde opmerking over diepteligging").

**Waarom 4 en niet 5.** De audit stelde 5 m voor, als projectkeuze zonder externe bron (19
meldingen). De auteur koos 4 m: daarmee hangt de drempel aan een gepubliceerde ontwerpnorm in
plaats van aan de vorm van deze ene dataset, en blijft de band 4-5 m zichtbaar. Dat kost 104
meldingen meer dan de 5 m-variant.

**Waarom de titel neutraal wordt.** De titel luidde "BOB-sanity ten opzichte van AHN (boven
maaiveld, meer dan 3 m eronder)" en droeg de drempel dus als getal, terwijl de drempel
configureerbaar is (harde regel). Hij wordt "BOB-sanity ten opzichte van AHN (boven maaiveld of
onaannemelijk diep eronder)". Dat is geen cosmetiek: `Check.title` voedt de checkkop in het
Markdown-rapport, de kolom Omschrijving in de CSV en de laag `overzicht_checks` in de
GeoPackage, dus een verouderd getal daar leest als de gehanteerde grens. Een drifttest
(`test_hgt003_noemt_de_drempel_niet_als_getal_in_zijn_titel`) houdt hem vast.

**Correctie d.d. 2026-08-28** (blok B-review). Twee dingen stonden hierboven onjuist. (1) De
dekkingsmatrix rendert niet `Check.title` maar de titel uit het checkregister
(`scripts/dekkingsmatrix.py`, `entry.title`); een neutrale checktitel raakt die dus niet, en de
matrix bleef "meer dan 3 m eronder" tonen. (2) Het register bleef daardoor ook niet ongewijzigd:
de registerregel is nu geannoteerd volgens het huispatroon van HGT-001/BO-44 -- "meer dan 4,0 m
eronder; v0.9 zei 'meer dan 3 m'; afwijking in BO-68" -- en de matrix is geregenereerd. Het
versienummer van het register verandert daar niet van; de annotatie zegt juist dat dit een
gedocumenteerde afwijking van v0.9 is. Daarbij is ook de omissie hersteld dat het rapport de
gehanteerde grens nergens meer noemde: `notes()` van HGT-003 meldt hem voortaan uit de config,
in dezelfde vorm als HGT-001/002 ("Gemeld vanaf ...").

**Verwacht effect op De Wolden en Hoogeveen.** De dieptemeldingen gaan van 1.042 naar ~123; de 48
bovenmaaiveld-meldingen blijven staan, dus het totaal van HGT-003 gaat van 1.090 naar ~171. De
bekeken populatie (22.138, analyseset) verandert niet. De hermeting hoort bij blok B van de
auditregie, niet bij dit besluit.

**Hoe de fixture de grens vasthoudt.** Streng 2 in `ext_scenario.ttl` draagt sinds dit besluit
twee BOB's die precies om de drempel heen liggen, op het vlakke raster van 10,00 m NAP: het
beginpunt op 6,50 (3,50 m diep, stil) en het eindpunt op 5,50 (4,50 m diep, meldt). Zonder die
stille kant zou een latere verschuiving van de drempel geen enkele test raken.

**Alternatieven.** De drempel op 5 m (het auditvoorstel; verworpen door de auteur, zie hierboven).
Hem op 3 m laten met de registerherkomst erbij (verworpen: 1.042 meldingen waarvan de mediaan
gewone rioleringsdiepte is, kosten de rest van de check haar geloofwaardigheid). Een tweede
check-ID voor de bovenmaaiveld-helft, zodat die een eigen ernst kan krijgen (verworpen: botst met
"één ernst per ID" uit het richtingscluster, #79 §3). De diepte per stelseltype of per
leidingklasse differentiëren (verworpen: de meting onderbouwt dat niet, en het maakt van één
drempel een staffel die niemand kan navertellen).

### BO-69 TOP-006, TOP-010 en TOP-011 toetsen alleen vrijverval tegen vrijverval of duiker

**Wat.** De drie checks die twee leidingen naast elkaar leggen -- TOP-006 (overlap over lengte),
TOP-010 (buisbuffer op de diameter) en TOP-011 (hartlijnkruising) -- draaien niet langer op de
brede rol `leidingen` maar op een nieuwe, engere rol `nabijheidsleidingen`. **Beide** partijen van
een paar moeten erin zitten. De klassen staan als `[klassen] nabijheidsleiding` in beide
configbestanden en als default in `ClassRoots`, niet in de code:
`VrijvervalRioolleiding` en `Duiker`. Buiten de populatie vallen daarmee de drains, het
mechanische riool en de aansluitleidingen. ID's, ernst en dimensie van de drie checks blijven
ongewijzigd; `notes()` van alle drie verantwoordt voortaan hoeveel leidingen buiten de scope
vielen.

**Waarom.** Besluit van de auteur op het beslisdocument van 28-08 (PRE-3 plus vervolgvraag V3),
uit de checkaudit (`docs/checks-audit-2026-08.md`, TOP-011 is daar als enige met 🟠 scope-bug
gemarkeerd). De aanleiding is de steekproefbeoordeling van `Ho6V0440-Ho6V0436-1`: *"Let op:
kruising vrijverval riool met mechanisch riool is geen probleem. Deze check zou alleen kruisingen
van vrijverval leidingen moeten checken (en duikers, exclusief drains)."* Een persleiding ligt
onder een straat nu eenmaal dwars door het vrijvervalnet heen, en een drain evengoed; die
kruising is geen datakwaliteitsgebrek maar de normale ondergrond. Wat de check bedoelt te vinden
-- twee buizen die elkaar in de weg liggen -- geldt alleen tussen leidingen die in hetzelfde vlak
vrijverval water voeren.

**Waarom de duiker er wél bij hoort en de aansluitleiding niet.** `Duiker` is in het GWSW "een
leiding die oppervlaktewater-elementen verbindt": vrijverval, in hetzelfde vlak, en een
doorkruising ervan is een echt conflict. `Aansluitleiding` ("een leiding voor de aanvoer van
afvalwater", de kolk- en perceelaansluiting) voert óók vrijverval water, en een letterlijke lezing
van PRE-3 zou haar dus binnen laten; de auteur heeft haar op 28-08 expliciet buiten de toets
gehouden. Reden: een aansluitleiding loopt per definitie van de gevel of de kolk dwars naar het
hoofdriool en kruist daarbij routinematig andere leidingen; die kruisingen dragen geen
handelingsperspectief. Dat is een bewuste afwijking van de letterlijke PRE-3-tekst en staat
daarom hier.

**Wat de ontologie zegt** (gebundelde GWSW-ontologie, geverifieerd 28-08). `VrijvervalRioolleiding`
hangt onder `Rioolleiding` onder `Leiding`. `Duiker`, `Drain` én `Aansluitleiding` hangen alle
drie **rechtstreeks** onder `Leiding` en niet onder `VrijvervalRioolleiding`. De grens van deze rol
volgt dus geen enkele tak van de hierarchie -- ze is een opsomming, en daarom een rol met een
eigen `[klassen]`-lijst en geen bestaande selectie. `gwsw:Aansluitleiding` draagt in de ontologie
het Engelse label "Drain (EN)"; dat is een labelkwestie en zegt niets over de klassenhierarchie.

**Wat de meting zegt** (audit 27-08, `scripts/checkaudit_meting.py`, De Wolden en Hoogeveen).
TOP-006 gaf 81 fouten, waarvan 36 vrijverval x vrijverval, 30 mechanisch x vrijverval en 15 met
een drain, duiker of loze leiding erin. TOP-010 gaf 2.184 fouten: 1.189 vrijverval x vrijverval,
414 met een drain, 204 met een duiker, 171 met een mechanische leiding en 302 met een
aansluitleiding. TOP-011 gaf 1.872 waarschuwingen: 1.024 vrijverval x vrijverval, 390 met een
drain, 170 met een duiker, 170 met een mechanische leiding en 211 met een aansluitleiding. Met
alleen de drains en het persnet eruit blijven er 39, 1.359 en 1.161 over; met de aansluitleidingen
er ook uit verliest TOP-010 er nog 302 en TOP-011 er nog 149. De hermeting op de volle dataset
hoort bij de blokregie, niet bij dit besluit.

**Waarom een eigen index en niet een filter op `_Topologie`.** `_Topologie.lined` draagt élke
leiding met geometrie, en dat moet zo blijven: TOP-021 vraagt of er *enige* streng langs een put
doorloopt, en TOP-001 of er *enige* streng op aansluit. De drie nabijheidschecks krijgen daarom
een eigen structuur `_Nabijheid` (leidingen, STRtree, uiteinden, plus de telling van wat erbuiten
viel) die zelf over de leidingenrol loopt. Dat is bewust geen goedkopere afgeleide van
`_Topologie`: zou `_Nabijheid` die aanroepen, dan zou de AST-drifttest van issue #64 de rollen
`netwerkknopen` en `vrijvervalrioolleidingen` aan TOP-006 en TOP-011 blijven toeschrijven,
terwijl die twee checks er sinds dit besluit niets meer mee doen. De prijs is één extra pas over
de leidingen om hun uiteinden te bepalen.

**Waarom `notes()` telt wat erbuiten viel.** Stilte leest als "alles gecontroleerd" (de regel uit
`CLAUDE.md`). Een versmalde populatie die nergens genoemd wordt maakt van een daling in de
bevindingen een onzichtbare keuze. De toelichting noemt de klassen uit de configuratie en het
aantal leidingen dat erbuiten viel, zodat rapport en GeoPackage de versmalling dragen.

**Correctie in de fixtures.** De gedeelde prelude van `scripts/maak_ttl_fixtures.py` verklaarde
`gwsw:Drain` als subklasse van `gwsw:VrijvervalRioolleiding`. Dat is onjuist -- de ontologie hangt
hem onder `Leiding` -- en het zou de nieuwe populatiegrens in elke fixture wegpoetsen. De prelude
volgt nu de ontologie en draagt ook `gwsw:Aansluitleiding rdfs:subClassOf gwsw:Leiding`. Geen
enkele bestaande fixture had een `Drain`-instantie, dus geen enkele uitslag verandert erdoor.

**Alternatieven.** De rol beperken tot `vrijvervalrioolleidingen` (verworpen: een duiker is
vrijverval en een doorkruising ervan is een echt conflict; de auteur noemt hem expliciet).
`Aansluitleiding` erbij (verworpen door de auteur; zie hierboven -- het kost 302 respectievelijk
149 meldingen zonder handelingsperspectief). Alleen het hoofdobject beperken en de tegenpartij vrij
laten (verworpen: dan blijft precies de gemelde kruising vrijverval x persleiding staan, alleen
met het andere object voorop). De uitkomst laten staan en op `[rapport] onderdruk_klassen`
leunen (verworpen: onderdrukking werkt op het hoofdobject en niet op `object2_uri`, dus een
kruising met een persleiding als tegenpartij blijft er hoe dan ook staan -- en het zou een
scope-fout tot een uitvoerinstelling maken).

### BO-70 TOP-006 gaat naar 0,02 m over 2,0 m; de TOP-010-marge blijft 0,0 m

**Wat.** Twee drempels van de nabijheidschecks, in één besluit omdat ze dezelfde vraag stellen
(hoe dicht is te dicht) en de gevoeligheidsmeting ze naast elkaar legde. `overlap_tolerantie_m`
gaat van 0,05 naar **0,02 m** en `overlap_minimale_lengte_m` van 1,0 naar **2,0 m** (TOP-006).
`diameterbuffer_marge_m` blijft **0,0 m** (TOP-010) -- geen wijziging, maar expliciet bekrachtigd,
zodat de vraag niet elke audit terugkomt. ID's, ernst, dimensie en populatie van beide checks
blijven ongewijzigd; alleen de getallen in de drie configplekken verschuiven.

**Waarom.** Besluit van de auteur op 28-08 (checkaudit-vervolgvraag V5, aangehouden bij het
beslisdocument van 28-08 en daarna apart gemeten; issue #100). De aanleiding is de
steekproefbeoordeling bij TOP-006: dezelfde soort melding werd twee keer terecht genoemd
(`Kv1G0018-Kv1G0020-1`, `ID5694-ID5693-1`: *"lijkt niet plausibel, dus terecht dat ze naar voren
komen"*) en één keer plausibel (`Ho8H1118-Ho8H1120-1`: *"Is plausibel, dus geen fout"*). Twee
buizen die over lengte binnen 5 cm van elkaar blijven zijn niet per se dubbel ingetekend -- dat is
binnen de inwinnauwkeurigheid ook gewoon twee buizen naast elkaar in dezelfde sleuf. Wat de check
bedoelt te vinden is het duplicaat: dezelfde buis twee keer in de dataset. Op 2 cm over 2 m blijft
daar alleen dat van over; wie de bredere nabijheid wil zien houdt TOP-010 (buisbuffer op de
diameter) en TOP-013 (parallelle strengen tussen hetzelfde putpaar), die dezelfde ligging met een
andere maat meten.

**Wat de meting zegt** (28-08, `scripts/meet_v5_gevoeligheid.py`, De Wolden en Hoogeveen,
populatie ná #82: 18.213 strengen vrijverval + duiker, zelfde paarlogica als de checks).

- **TOP-006 -- de drempels sturen wél.** 0,05 m over 1,0 m (huidig) geeft **39** meldingen;
  0,02 m over 2,0 m geeft **13**.
- **TOP-010 -- de marge discrimineert niet.** −0,10 m geeft 1.325, 0,0 m geeft 1.359 en +0,10 m
  geeft 1.401: over 20 cm marge beweegt de uitslag 6%. De overlapdiepte van de huidige meldingen
  verklaart waarom -- mediaan 0,31 m, p90 0,63 m, max 1,60 m. Dat zijn diepe 2D-overlaps
  (kruisingen op verschillende diepte), geen schampgevallen die net binnen of net buiten een marge
  vallen. Een marge verleggen haalt dus geen groep meldingen weg; het verschuift alleen de staart.

**Waarom de TOP-010-marge dan niet weg of juist ruimer.** Omdat de vraag die de marge zou moeten
beantwoorden -- ligt hier een echt conflict -- niet in het platte vlak beantwoord kan worden. Twee
buizen die elkaar in 2D kruisen liggen meestal gewoon op verschillende diepte, en dat onderscheid
zit in de hoogte: HGT-004 (BOB-conflict tussen kruisende strengen), HGT-009 en HGT-018. TOP-010
levert de kandidaten, de HGT-checks vellen het oordeel. Een marge is dan een knop die aan de
verkeerde kant van de vraag zit; 0,0 m ("de buizen raken elkaar") is de enige waarde die zonder
hoogte een uitspraak is.

**Verwacht effect op De Wolden en Hoogeveen.** TOP-006 van 39 (ná #82) naar ~13; TOP-010
ongewijzigd op 1.359. De hermeting op de volle dataset hoort bij de blokregie, niet bij dit
besluit.

**Hoe het vastligt.** De twee getallen staan op de drie gebruikelijke plekken -- de default in
`CheckThresholds`, `src/nlriochecker/checks.toml` en `configs/dewoldenhoogeveen.toml` -- en de
configdrifttest houdt ze gelijk. De fixture `top006_drempels.ttl` legt drie paren naast elkaar die
alleen in afstand en samenvallengte verschillen: 3 m op 1 cm (meldt), 1,5 m op 1 cm (onder de
minimumlengte) en 10 m op 4 cm (buiten de tolerantie). De laatste twee meldden onder 0,05 m / 1,0 m
nog wel, dus de test valt als iemand één van beide drempels terugdraait zonder dit besluit te
herzien.

**Alternatieven.** Alleen de tolerantie verlagen en de minimumlengte op 1,0 m laten (verworpen: dan
blijft precies het geval staan waar de steekproef "plausibel" op zei -- twee buizen die elkaar bij
een bocht over ruim een meter naderen; de auteur heeft beide knoppen in één beweging gezet). Naar
5 of 10 m minimumlengte (verworpen: een duplicaat van een korte streng tussen twee putten is even
echt als een lange, en die zouden dan wegvallen; de meting is op die staffel niet gedraaid, dus er
is ook geen getal dat het zou dragen). De tolerantie aan de inwinnauwkeurigheid koppelen als
configureerbare afgeleide (verworpen: de dataset draagt die nauwkeurigheid niet per streng, dus dat
zou een tweede drempel zijn die zich als een meting voordoet). De TOP-010-marge op −0,05 m zetten
om de schampgevallen weg te nemen (verworpen: die schampgevallen bestaan niet -- de mediane overlap
is 0,31 m -- dus het kost meldingen zonder dat iemand kan navertellen waarom juist die).

### BO-71 Het compartimentduplicaat (`c<n>`-postfix) wordt vóór de topologiechecks samengevoegd

**Wat.** Een knoop waarvan het label op een `c<n>`-postfix na gelijk is aan dat van een andere
knoop, én die daar binnen `[drempels] dubbele_put_tolerantie_m` (0,30 m) van af ligt, is voor de
topologiechecks hetzelfde fysieke object. `_bouw_topologie` in `checks/topologie.py` houdt er één
van over; de rest valt uit de puttenindex. Beide eisen tellen: alleen op de naam matchen zou twee
echte putten samenvoegen die toevallig zo heten, en alleen op de ligging matchen is precies wat
TOP-005 al meldt. **Het origineel wint** -- de knoop wiens label géén postfix draagt; is die er
niet, dan de laagste postfix, en bij gelijke stand de laagste URI, zodat de uitkomst niet van de
leesvolgorde afhangt. Een knoop zónder postfix wordt nooit weggenomen: twee gelijknamige putten
zonder postfix blijven een gewone dubbele put.

**Waarom.** De Kikker/BrutIS-export schrijft een gecompartimenteerde put per compartiment uit, elk
als een eigen `Inspectieput`/`Overstortput`/`Stuwput`/`Rioolgemaal`/`Pompunit` op precies dezelfde
coördinaat, met het putlabel plus (met spaties uitgevuld) `c1`, `c2`, ... Dat is een
exportartefact, geen tweede put in de grond. De putchecks zien er wél twee: de strengeinden snappen
op de dichtstbijzijnde knoop en dat kan er maar één zijn, dus de andere heet losliggend (TOP-001),
het paar heet een dubbele put (TOP-005) en soms ligt de overgebleven knoop naast een doorlopende
streng (TOP-021). Het oordeel van de auteur bij de steekproef: *"Dit komt niet omdat er geen streng
nabij ligt ... maar omdat hij niet is aangesloten."* Zie de checkaudit (#79 §3, **PRE-7**), het
besluit van 28-08 en issue #85.

**Wat de meting zegt** (28-08, tekstscan op `data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl`, geen
toetsrun). 189 knoopslabels dragen een `c<n>`-postfix, in **98** groepen: 96 keer `c1`, 92 keer
`c2`, 1 keer `c3`. De postfix staat er altijd met minstens één spatie ervoor; geen enkel
strenglabel matcht het patroon. Binnen een groep is de onderlinge afstand **0,000 m** -- alle 92
meetbare groepen vallen exact samen, dus de tolerantie van 0,30 m is hier ruim en niet krap. In
slechts **3** van de 98 groepen bestaat er ook een knoop met het kale basislabel; in de overige 95
is `c1` het oudste dat er is. Dezelfde regel over dezelfde export levert **94** samengevoegde
knopen, en dat sluit aan bij de audit: 93 van de 102 TOP-001-meldingen en 92 van de 112
TOP-005-meldingen dragen deze postfix.

**Reikwijdte -- welke checks de samengevoegde populatie zien.** Rechtstreeks: de checks die de
puttenindex `_Topologie.nodes` aflopen, en dat zijn er zeven -- **TOP-001** (losliggende put),
**TOP-005** (dubbele put), **TOP-009** (RD-bereik), **TOP-014** (aansluitende strengen),
**TOP-015** (multipart), **TOP-016** (ongeldige geometrie) en **TOP-021** (put naast een
doorlopende streng). Indirect, via de snapping die op de STRtree over diezelfde lijst draait:
**TOP-002** en **TOP-003**. Alle negen verantwoorden het in hun `notes()`; stilte zou lezen als
"alles gecontroleerd".

**Wat de samenvoeging níét doet, en wat zij kán kosten.** Zij haalt de knoop uit de populatie en
rekent niets van het duplicaat bij het origineel op. Een gebrek dat alléén op het duplicaat stond
-- een multipart-geometrie (TOP-015), een ongeldige geometrie (TOP-016) -- wordt daarna dus
nergens meer gemeld, en TOP-014 telt de strengen van beide knopen niet bij elkaar op (drie plus
drie blijft twee keer drie). De toelichting zegt dat met zoveel woorden ("wat alleen op zo'n
duplicaat staat is hier niet getoetst") en belooft nadrukkelijk niet dat het gebrek op het
origineel opduikt.

Het strengeinde dat op een weggenomen duplicaat uitkwam snapt op de knoop die overbleef, maar
alleen als die binnen `snapping_tolerantie_m` (0,10 m) ligt -- en de samenvoeging zelf gebruikt de
ruimere `dubbele_put_tolerantie_m` (0,30 m). **Tussen die twee maten in kan een strengeinde zijn
aansluiting verliezen en levert de dedup dus een nieuwe TOP-002- of TOP-003-melding op.** Op De
Wolden en Hoogeveen gebeurt dat niet: alle 98 groepen vallen op 0,000 m samen, ruim binnen de
snapping-tolerantie. Maar de claim geldt alleen binnen die tolerantie, en daarom dragen TOP-002 en
TOP-003 de toelichting en noemt die beide drempels. De fixture
`top003_dedup_buiten_snapping.ttl` legt het venster vast (duplicaat op 0,20 m). Dat de twee
toleranties aan elkaar gekoppeld zouden moeten worden -- één maat in plaats van twee -- is een
open auteursvraag en bewust níét in dit besluit meegenomen. **TOP-004** blijft hoe dan ook buiten
schot: die leest de administratieve koppeling via `resolve_network_node` en niet de puttenindex.

Wat de dedup **niet** raakt, en met opzet: de netwerkgraaf in `checks/verbanden.py` en alles wat
daarop leunt (`verbonden_knopen`, dus TOP-013/014-telling, TOP-019, alle NET-checks), de
administratieve koppeling via `resolve_network_node` (TOP-004, TOP-012), de afbakening in
`afbakening.py`, en de uitvoer: het duplicaat blijft gewoon een object in de laag `putten` van de
GeoPackage. Dit is een analysestap vóór de topologiechecks, geen wijziging aan de dataset. De
leeslaag `gwsw-orox-helpers` blijft ongemoeid -- een wijziging dáár is een release plus een
`uv lock` (Harde regel), en de dedup is bovendien een projectinterpretatie en geen leesfeit.

**Randgeval dat bewust conservatief uitpakt.** Ligt het origineel verder dan de tolerantie van zijn
postfixdragers, dan wordt er in die groep niets samengevoegd -- ook niet als de postfixdragers
onderling wél samenvallen. Dat kost hooguit een melding die blijft staan (de veilige kant); een
clusterende variant zou code toevoegen voor een geval dat in deze export nul keer voorkomt.

**Hoe het vastligt.** `_COMPARTIMENT_POSTFIX`, `_basislabel` en `_dedupliceer` in
`checks/topologie.py`; de telling reist mee als `_Topologie.samengevoegd` en `_dedupnotitie` maakt
er de toelichtingsregel van, die de negen checks delen. De fixture
`top005_compartimentduplicaat.ttl` zet vier groepen naast
elkaar die alleen in het beslissende kenmerk verschillen: `K0001  c1`/`c2` op 0,10 m (samenvoegen),
`M0003` met `M0003  c1` op 0,10 m waarbij de leiding aan de postfixdrager hangt (het origineel wint
én de leiding snapt erop), `V0002  c1`/`c2` op 0,50 m (buiten de tolerantie, blijft staan) en twee
putten `DUB` zonder postfix (blijft een dubbele put). De drempel is de bestaande
`dubbele_put_tolerantie_m`; er komt geen nieuwe knop bij.

**Verwacht effect op De Wolden en Hoogeveen.** TOP-001 **102 → ~9**, TOP-005 **112 → ~20**,
TOP-021 **5 → ~3**. De hermeting hoort bij de blokregie, niet bij dit besluit.

**Alternatieven.** De dedup in de leeslaag leggen (verworpen: Harde regel, en het is een
interpretatie van één leverancier zijn export en geen leesfeit -- `gwsw-orox-helpers` moet de
export teruggeven zoals hij is). Het patroon configureerbaar maken als regex (verworpen: niet
gevraagd, en een verkeerd ingestelde regex zou stil echte putten samenvoegen; de tolerantie is de
knop die er al is). Een eigen aan/uit-schakelaar (verworpen: op een export zonder dit artefact
matcht de regel nul keer en kost zij niets). Samenvoegen op ligging alleen, zonder de naam
(verworpen: dat is TOP-005 zelf uitzetten). De duplicaten ook uit de netwerkgraaf en de uitvoer
halen (verworpen voor nu: dat raakt de NET-checks, de afbakening en de GIS-lagen, en het issue
vraagt de kleinste ingreep die TOP-001/005/021 dedupliceert).

### BO-72 Een hulpstuk met een telbare GWSW-functie is voor TOP-002/003 een geldig strengeinde

**Wat.** TOP-002 en TOP-003 tellen per vrijvervalstreng hoeveel uiteinden binnen
`[drempels] snapping_tolerantie_m` (0,10 m) op een geldig eindobject vallen -- nul is TOP-002,
precies één is TOP-003. Geldig is voortaan niet alleen een netwerkknoop (put, afvoer- en
lozingseindpunt, bergbezinkvoorziening) maar ook een **hulpstuk met een telbare GWSW-functie**:
de klasse draagt een `functie`-restrictie met een aantal leidingen erin
(`VerbindenVanTweeLeidingen` 2, `VerbindenVanDrieLeidingen` 3, `VerbindenVanVierLeidingen` 4).
Geverifieerd in de gebundelde ontologie: `Mof` draagt de eerste, `T_stuk` en `Y_stuk` de tweede,
`Kruisstuk` de derde; alle vier hangen onder `Verbindingsstuk` → `Hulpstuk`. Een `Afsluitstuk`
(`AfsluitenVanLeidingen`) en een `Ontstoppingsstuk` dragen wél een functie maar geen aantal en
tellen dus **niet** als eind.

**Waarom.** Een `Hulpstuk` valt in het GWSW onder `Constructieonderdeel` en niet onder `Put`, dus
de rol `netwerkknopen` bevat het niet en een streng die op een T-stuk eindigt heeft daar
geometrisch "geen put". Dat is wat de twee checks meldden, en het is niet wat zij bedoelen te
meten: de vraag is of de streng ergens op uitkomt. Het oordeel van de auteur bij de steekproef is
eenduidig -- *"Streng ligt tussen 2 T-stukken. Is voor deze analyse goed."*, *"Ligt tussen een
t-stuk en inspectieput. Voor deze analyse is dat goed"* -- en de audit meet dat het geen
uitzondering is: **45 van de 56** TOP-002-meldingen hebben beide einden aan een hulpstuk en
**107 van de 109** TOP-003-meldingen één (checkaudit 27-08, §rode draad 2). Wat overblijft zijn
de echte snapmissers: ~11 respectievelijk ~2.

**Het gebrek verdwijnt niet.** Dat een T-stuk maar twee van zijn drie leidingen verbindt blijft
zichtbaar via **TOP-022** (224 F op 1.054 telbare hulpstukken), vanaf de hulpstukkant en met het
handelingsperspectief dat daarbij hoort ("ontbrekende leiding registreren, of het hulpstuk een
klasse geven die bij het werkelijke aantal past"). TOP-002/003 gaan over de streng en TOP-022 over
het hulpstuk; ze meldden tot nu toe dezelfde situatie twee keer vanaf twee kanten, en de
strengkant was de minst bruikbare van de twee.

**Waarom precies de telbare functie als grens.** Dat is de grens die `_bouw_hulpstuktelling` voor
TOP-022/TOP-023 al hanteert (`_functie_met_aantal`, tabel `AANTAL_PER_FUNCTIE`), en de nieuwe index
leest letterlijk diezelfde populatie (`_hulpstuktelling().telbaar`) in plaats van een tweede
klassenlijst aan te leggen. Twee lijsten zouden stil uit elkaar lopen zodra er een klasse bijkomt.
Bijkomend argument: een hulpstuk dat volgens de ontologie leidingen verbindt ís een knooppunt in
het net; een afsluitstuk is dat niet, en een streng die daarop doodloopt hoort gemeld te worden.

**Randgeval dat bewust blijft melden.** Een streng die op een `Afsluitstuk` of `Ontstoppingsstuk`
eindigt houdt zijn TOP-002/003-melding (op De Wolden en Hoogeveen 58 respectievelijk 10 zulke
hulpstukken, waarvan de audit niet meet hoeveel strengen erop uitkomen). Dat is de veilige kant:
de ontologie zegt van die klassen niet dat zij leidingen verbinden, dus er is geen grond om ze als
netwerkeind te lezen.

**Hoe het vastligt.** `_Eindhulpstukken`, `_eindhulpstukken` en `_bouw_eindhulpstukken` in
`checks/topologie.py`, gelezen door `_StrengPutAansluiting.run`; de index is een STRtree over de
telbare hulpstukken met een punt en staat in dezelfde contextcache als de andere
topologiestructuren. Beide checks declareren de rol `hulpstukken` erbij en verantwoorden de regel
in hun `notes()` -- stilte zou lezen als "elk eind is aan een put getoetst". De meldingstekst noemt
het hulpstuk nu ook expliciet. Fixture `top002_streng_op_hulpstuk.ttl`: streng 1 tussen put en
T-stuk en streng 2 tussen twee T-stukken (beide goed), streng 3 met een afsluitstuk als tweede eind
(TOP-003) en streng 4 los in het veld (TOP-002); dezelfde fixture toont dat TOP-022 de twee
T-stukken onverkort meldt.

**Verhouding tot BO-71.** De `c<n>`-deduplicatie van issue #85 werkt op de puttenindex
`_Topologie.nodes`, en de snapping van TOP-002/003 leest diezelfde gededupliceerde lijst. De
hulpstukindex staat daarnaast en raakt hem niet: een hulpstuk is geen netwerkknoop en komt in de
dedup dus niet voor. De twee ingrepen werken op dezelfde strengeinden zonder elkaar te overlappen.

**Verwacht effect op De Wolden en Hoogeveen.** TOP-002 **56 → ~11**, TOP-003 **109 → ~2**. TOP-022
verandert niet. De hermeting hoort bij de blokregie, niet bij dit besluit.

**Alternatieven.** Het hulpstuk aan de rol `netwerkknopen` toevoegen (verworpen: dat raakt elke
check die die rol leest -- TOP-001 zou elk hulpstuk zonder streng als losliggende put melden, de
netwerkgraaf zou van vorm veranderen, en het is bovendien in strijd met de GWSW-hiërarchie, waar
een `Hulpstuk` geen `Put` is). Elk hulpstuk als eind laten tellen, ongeacht functie (verworpen: dan
verdwijnt ook de melding op een streng die op een afsluitstuk doodloopt, en dat is een echt gebrek).
De ernst van TOP-002/003 verlagen naar W in plaats van de populatie aan te passen (verworpen: het
gebrek is niet minder ernstig, het was er domweg niet -- een streng tussen twee T-stukken is
aangesloten). TOP-002/003 laten vervallen omdat TOP-022 hetzelfde meldt (verworpen: de ~11 en ~2
echte snapmissers zijn precies wat deze twee checks moeten vinden, en die ziet TOP-022 niet).
