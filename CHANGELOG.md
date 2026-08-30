# Wijzigingslog

Alle noemenswaardige wijzigingen aan dit project staan hier. De opzet volgt
[Keep a Changelog](https://keepachangelog.com/nl/1.1.0/), de nummering volgt
[semantische versionering](https://semver.org/lang/nl/) zoals
[docs/versionering.md](docs/versionering.md) die voor dit project uitlegt.

`scripts/uitgave.py` zet bij elke uitgave de sectie `Unreleased` om in een sectie met
het nieuwe nummer en de datum, en opent een lege nieuwe. Hij weigert uit te brengen als
`Unreleased` leeg is: een uitgave zonder wijzigingen is geen uitgave.

## [Unreleased]

### Toegevoegd

- **Gouden ledger** (`tests/golden/ledger.json`, generator `scripts/maak_ledger.py`): per
  (fixture, check) het aantal bevindingen, de bekeken populatie en het aantal
  toelichtingen over de hele registry op alle 183 TTL-fixtures, plus per check het aantal
  meldingen van het getrackte voorbeeld. De suite toetste per defectfixture precies één
  check; van de 869 rijen met minstens één bevinding lagen er 813 buiten elk vangnet.
  `tests/test_ledger.py` vergelijkt de veeg met het bestand (het verschil noemt fixture,
  check, vastgelegde en gemeten rij), bewaakt dat `examined` nooit kleiner is dan het
  aantal gemelde objecten en dat geen enkele fixture registrybreed stil is;
  `tests/test_voorbeeld.py` vergelijkt de meldingen per check met dezelfde ledger. De
  generator is ook de enige veeglus: `tests/test_uitvoer_identiteit_sweep.py` deelt hem
  via een session-fixture, dus de suite veegt één keer in plaats van twee (issue #113).
- **Waardegelijkheid tussen de drie archieven** (`tests/test_uitvoer_gelijkheid.py`): per
  `melding_id` draagt elk veld van `Melding` in `bevindingen.csv`, `bevindingen.json` en
  de meldingentabel van de GeoPackage dezelfde waarde, en de samenvattingskolommen van
  `putten` en `strengen` (`n_fout`, `n_waarschuwing`, `n_systemisch`, `checks_f`,
  `checks_w`, `ergste_ernst`, `prioriteit`, `status` en de negen categoriekolommen)
  kloppen met de meldingentabel in datzelfde bestand. De bestaande drifttests vergeleken
  alleen kolom*namen*: een verwisseling in `CSV_VELD_NAAR_KOLOM` of in de positionele
  tuple van `_melding_rij` (28 posities) bleef daarin groen. Test-only; geen regel in
  `src/` verandert (issue #114).

### Gewijzigd

- **HGT-010** heet voortaan *"Diameterverkleining in afvoerrichting"* in plaats van
  *"Diameterverjonging …"*: *verjonging* betekent vernieuwen, terwijl de check meldt dat
  de diameter benedenstrooms kleiner wordt. Puur een terminologiecorrectie — het check-ID,
  de logica en de tellingen (0 F / 525 W op De Wolden) veranderen niet (issue #112).
- `tests/test_uitgave.py::test_het_echte_wijzigingslog_is_verwerkbaar` roept
  `controleer_changelog` niet meer aan. Dat is een release-preconditie (een lege
  `[Unreleased]` afkeuren) en precies dat is de toestand van een release-commit, dus de
  `toets`-run op elke release-commit (en op `main` na de merge) werd er rood van. De
  preconditie blijft volledig gedekt door de synthetische gevallen in dezelfde testmodule
  (issue #110).

## [0.3.1] - 2026-08-30

### Toegevoegd

- **Release-workflow** (`.github/workflows/release.yml`): op de tag `vX.Y.Z` bouwt CI de
  wheel en de sdist met `uv build` en hangt ze aan een GitHub Release. De wheel hoeft niet
  meer met de hand gebouwd of geüpload te worden; zie [docs/versionering.md](docs/versionering.md).
- **EXT-009: straat in de bebouwde kom zonder vrijvervalriolering** (issue #104, BO-79 t/m
  BO-81). De eerste dekkingsvraag in het register: niet "ligt deze streng ergens
  doorheen?" maar "ligt er langs deze weg riolering?". Het toetsobject is daarom een
  NWB-wegvak en geen GWSW-object; de melding draagt een sleutel `nwb:wegvak/<WVK_ID>` en
  het middelpunt van het wegvak als locatie. Kandidaat is een gemeentelijk wegvak, geen pad
  of parkeervak, minstens 25 m lang, met zijn middelpunt in een TOP10NL-vlak met
  `bebouwdekom = ja`; buiten de kom hoort niet vanzelfsprekend riolering te liggen. De
  dragende maat is de lengte vrijvervalstreng in het eigen straatvlak -- de voronoi-cel om
  de wegas, geknipt op een buffer van 25 m en op de komgrens -- gedeeld door de
  straatlengte. Ligt er een put ín dat vlak, dan geldt de straat als bediend (lus- en
  hoefijzerwegen). **Drie uitkomsten in plaats van twee**: naast bediend (groen) en leeg
  (rood, een waarschuwing) is er *niet beoordeeld* (grijs) voor een overwegend onverharde
  straat en voor een straat met drukriolering-indicatie. Groen en grijs dragen geen melding
  maar wel een vlak in de GeoPackage, en het rapport telt ze -- stilte zou lezen als "alles
  gecontroleerd". De regel is deterministisch en met opzet geen model: op een validatieset
  van 485 handmatig beoordeelde straten haalt zij 32 fouten op 478 beoordeelde straten
  (93,3%) tegen 27 op 479 (94,4%) voor een getraind gradient-boosting-model -- vijf straten
  op een populatie van 4116, en daarvoor geen trainingsstap en geen nieuwe afhankelijkheid.
  De drempel is op die set geijkt met `scripts/ijk_ext009.py`.
- **De laag `vlakken` krijgt een vijfde soort en een kolom `status`** (issue #104, BO-79).
  `soort = wegvak` draagt de uitslag van EXT-009 per straat, met `status` in rood, groen of
  grijs -- dezelfde waarden als de objectlagen. Dit is de enige soort in die laag die ook
  zonder melding een rij krijgt; rood blijft strikt aan de meldingen van deze uitvoer
  hangen. `gwsw_run` telt ze in de nieuwe kolom `n_wegvakken`, en `vlakken.qml` krijgt drie
  regels met dezelfde kleuren als de objectlagen.
- **Drie nieuwe externe bronrollen en een nieuwe GWSW-rol** (issue #104, BO-80).
  `nwb_wegvak` werd al geladen maar door geen check gelezen; `top10nl_kom` (`[bronnen]
  top10nl` plus `top10nl_komlagen`) en `bgt_wegdeel` (`bgt_wegdeellagen`) zijn nieuw.
  `configs/dewoldenhoogeveen.toml` wijst ze alle drie aan -- de NWB-regel zei ten onrechte
  "niet aangeleverd voor dit gebied". De NWB-attributen worden hoofdletterongevoelig
  gelezen (`VectorLayer.kolom`), want De Wolden schrijft `WEGBEHSRT` en Koekangerveld
  `wegbehsrt`. De komlaag valt buiten de dekkingspoort van BO-19: een bebouwde kom is per
  definitie een deelgebied van het bereik. De rol `pompunits` (`[klassen] pompunit =
  ["Pompunit"]`) levert de pompputten voor de drukriolering-indicatie.

- **ATTR-001 kent een uitzondering per constructietype** (issue #86, BO-75). De nieuwe
  tabel `[[constructietype_diameter]]` in `plausibiliteit.toml` geeft een GWSW-klasse haar
  eigen diameterbereik, en dat gaat vóór het bereik van het materiaal: de materiaaltabellen
  zijn op vrijvervalriool geschreven en een drainageleiding is naar haar functie dunner --
  een drain van Ø65 is gangbaar en geen gebrek. `Drain`, `DIT_riool` en `DT_riool` staan er
  op 50-4000 mm. Research: de handelsmaatreeks voor drainagebuis loopt van 50 tot 200 mm
  (80 mm het meest toegepast; RIONED noemt in Kostenkengetallen drainage 80 of 100 mm bij
  rioolvervanging); een gangbare bovengrens die ook een DIT- of DT-riool dekt levert geen
  bron, dus die volgt de GWSW-waardegrens van 4000 mm. Op De Wolden verandert de uitslag
  niet: `Drain` en `Duiker` hangen rechtstreeks onder `Leiding` en vallen buiten de rol
  waarop ATTR-001 draait, en van `DIT_riool`/`DT_riool` levert die export er nul. De
  toelichting van de check telt voortaan hoeveel strengen tegen hun constructietype
  getoetst zijn en zegt erbij welke klassen buiten de check vallen.

- **De nulmeting spreekt Nederlands** (issue #101, BO-74). Elke overtreding uit de GWSW
  SHACL-nulmeting draagt een vaste, beschrijvende zin bij haar SHACL-vorm -- "Put zonder
  (of met meer dan één) geregistreerde puthoogte" in plaats van "Subject Put, path
  hasAspect, object HoogtePut - aantal voorkomens wijkt af (exact=1)". De 43 teksten zijn
  door de auteur vastgesteld en staan als package-resource in
  `src/nlriochecker/nulmeting_teksten.toml`; grenzen (`{min}`, `{max}`, `{n}`) komen uit
  de meldingsrij zelf, nooit uit de code of de configuratie. Het Markdown-rapport (ook de
  nieuwe kolom Omschrijving in de tabel per SHACL-vorm) en de GeoPackage-popup tonen
  alleen de zin; de drie archieven dragen beide teksten. Een vorm zonder tekst valt terug
  op de technische boodschap en het rapport telt hoeveel meldingen dat waren.
- **Nieuwe Harde regel (Techniek): functionaliteit mag `gwsw-orox-helpers` niet breken**
  (`CLAUDE.md`) — alleen de publieke API, geen patches op internals; leeslaagwijzigingen
  lopen via een release van die package (besluit auteur 28-08).
- **Checkaudit 2026-08 besloten: de Besluit-kolom is gevuld voor alle 99 checks**
  (`docs/checks-audit-2026-08.md`), op basis van het beantwoorde beslisdocument van de
  auteur (28-08). De vervolgissues staan als #80 t/m #97; drie punten zijn aangehouden
  voor een gezamenlijke sessie (V5 tolerantie, V9 diepteligging-research, V19 kringlopen).

- **`scripts/steekproef.py` trekt op buurt en splitst in kleine bestanden.** Nieuwe opties
  `--buurten <CBS-gpkg> --buurt <naam>...` (alleen meldingen met een foutlocatie in die
  buurten; de dekkingstabel telt `in_gebied` en meldt "geen bevindingen in de gekozen
  buurten (N erbuiten)"), `--per-bestand N` (genummerde bestanden in registervolgorde,
  elke check heel in één bestand, de dekkingstabel volledig in elk) en `--check ID`
  (herhaalbaar; beperkt steekproef en dekkingstabel tot die checks). Elke rij draagt nu
  ook alle kolommen van de put/streng uit de run (`obj_`-voorvoegsel bij een naamclash) en
  één lege kolom `feedback` in plaats van `oordeel` + `opmerking`. Voorbereiding op de
  checkaudit (#68–#70).
- **`bekeken` zegt per check waarover het geteld is** (issue #77, BO-58). Elke uitslag
  draagt `bekeken_scope` -- `analyseset`, `volledige_export` of `attribuut_instanties` --
  en `populatie`, de populatie die de check declareert (zijn rollen, anders zijn
  kenmerken) -- waar hij over gaat, niet de noemer van het getal, en daarom overal achter
  "gaat over". Ze staan in de checktabel van het
  rapport (kolommen Bekeken scope en Gaat over, met een voetnoot eronder), in de detailregel per check, in
  `overzicht_checks` van de GeoPackage en in het optionele enveloppeveld `checks` van
  `bevindingen.json` (`schema_versie` blijft `1.1`: optioneel en additief); niet in de
  meldingen-CSV. Zonder label mengde één kolom 95, 45.803 en 459.108 objecten
  respectievelijk kenmerkinstanties, en waren de percentages die erop delen
  onvergelijkbaar. Meting: `scripts/analyse_scope_per_check.py`.
- **Elke check declareert zijn GWSW-rollen en -kenmerken** (issue #64). `Check` krijgt
  `rollen` (namen uit `selectie._ROLLEN`: de populatie die de check langsloopt) en
  `kenmerken` (GWSW-kenmerknamen, of een `config:<pad>`-verwijzing voor ATTR-013, of `*`
  voor ATTR-014). `register()` weigert een check die er niet allebei declareert; de
  velden reizen mee op `CheckOutcome`. Twee drifttests bewaken ze: een AST-sweep houdt de
  declaratie tegen de feitelijke code (`tests/checkdeclaratie_analyse.py`,
  `tests/test_checkdeclaraties.py`) en een tweede tegen de ontologie
  (`tests/test_checkdeclaraties_ontologie.py`). De index draagt daarvoor twee nieuwe
  blokken `aspecten_van` en `onderdelen_van`. Het rapport toont per eigen check een regel
  "Toetst ⟨klassen⟩ op ⟨kenmerken⟩", en `docs/dekkingsmatrix.md` krijgt een kolom
  *Rollen · kenmerken*.
- **Een getrackt voorbeeld om `toets` op te draaien** (issue #103). `voorbeelden/koekangerveld/`
  draagt de buurt Koekangerveld als volwaardige invoer: de OroX-uitsnede van haar analyseset
  (kern, contextschil, onderdelen, orientaties en stelsels), de drie SHACL-rapporten
  teruggebracht tot de regels die op een object in het voorbeeld uitkomen, het studiegebied
  en de vier vectorbronnen. Het draait op de meegeleverde `checks.toml` en heeft geen eigen
  projectconfiguratie nodig: `toets` overschrijft `[bronnen] map` toch met de map achter
  `--bronnen`. Zonder dit voorbeeld had een lezer van de
  repository niets om de package op te draaien: `data/` staat op het checkregister na buiten
  versiebeheer. Gebouwd met `scripts/maak_voorbeeld.py`, bewaakt door een rooktest die geen
  `data/` nodig heeft en dus op de CI-runner meedraait (`tests/test_voorbeeld.py`), en
  vastgezet met een gelijkheidstest: voor de eigen checks levert het voorbeeld dezelfde
  bevindingen als een gebiedsrun Koekangerveld op de volledige export.
- **`docs/gebruik.md` en twee schermafdrukken** (issue #103). De gebruiksdocumentatie die
  in de README stond -- de commando's, de ontologie, de CFK-deelset, de nulmeting tussen
  de eigen bevindingen, de rapportage per gebied, het rapport, de uitvoer, de externe
  bronnen, de projectconfiguratie en de voortgang -- staat nu als eigen document in
  `docs/gebruik.md`, met een sectie *Snel proberen met het voorbeeld* erboven en elke
  bewering opnieuw tegen de code gehouden. Rechtgezet: de GeoPackage draagt drie
  featurelagen en niet twee plus `bouwwerken`/`waterdelen_zonder_zinker` (die bestaan
  sinds issue #98 niet meer); `dekking_tolerantie_m` staat in de code op 0,0 maar in de
  meegeleverde `checks.toml` op 300; zonder ontologie zien 63 van de 89 checks nul
  objecten (gemeten 29-08-2026, niet 62), en de veertien die het meest zien er 767 in
  plaats van 1.874; de nulmetingtelling van 105.963 is die vóór de onderdrukking uit
  `[rapport]`. Daarnaast rendert `scripts/maak_schermafdruk.py` uit de voorbeeldrun twee
  schermafdrukken: `docs/img/kaart-koekangerveld.png` (de drie featurelagen met hun stijl
  uit `layer_styles`, headless via PyQGIS, met de statuslegenda en een popup erop) en
  `docs/img/rapport-kop.png` (de kop van `bevindingen.md`). Beide zijn gegenereerd en
  worden nooit met de hand bijgewerkt.

### Gewijzigd

- **De README is een landingspagina geworden** (issue #103). De 388 regels opgestapeld
  wijzigingslog zijn er nog 149, Nederlands en zonder inhoudsopgave (GitHub maakt die uit de
  koppen), met een vaste opbouw: één alinea over wat het is, drie badges (de CI-workflow
  `toets` op `main`, de licentie, Python 3.12+), *Stand van zaken* (fase 4, getoetst op één
  echte export, niet op PyPI, API nog niet stabiel, versienummer via dit wijzigingslog in
  plaats van in de tekst), *Wat je krijgt* met de vier uitvoervormen en de twee
  schermafdrukken, *Snel proberen* met het getrackte voorbeeld in drie commando's en de
  echte CLI-uitvoer erbij, *Met je eigen data*, *Verder lezen*, *Ontwikkelen*, *Bijdragen*
  en *Licentie*. Het eerste scherm is voor de rioolbeheerder of data-adviseur; de
  ontwikkelaar staat onderaan. De gebruiksdocumentatie zelf staat in `docs/gebruik.md`, en
  de README linkt per onderwerp naar de kop daar. Bewust niet meegenomen: een "waarom"-blok,
  CONTRIBUTING.md, CODE_OF_CONDUCT, CITATION.cff, een roadmapsectie en een Engelse
  samenvatting.
- **De laag `vlakken` krijgt één stijlregel per check, en tekent groen en grijs niet meer**
  (issue #107, BO-85). De zeven regels van de standaardstijl worden er vier, met de
  checkcode voorop: `EXT-001 - Pand of bouwwerk (BGT/BAG)`, `EXT-003 - Waterdeel (BGT)`,
  `RVZ-006 - Gemengd stelsel zonder overstort` en `EXT-009 - Mogelijk ontbrekend riool`.
  Pand en bouwwerk delen nu één regel en de pand-kleur; de oranje bouwwerkkleur vervalt.
  **De groene en grijze wegvakken van EXT-009 worden niet meer getekend**: op De Wolden en
  Hoogeveen overstemden 3593 groene en 23 grijze vlakken de 500 rode. Ze blijven volledig
  als rij in de laag staan -- attributentabel, filter, popup en `n_wegvakken` -- zodat
  "gekeken, er ligt riolering" en "niet beoordeeld" na te gaan blijven; alleen bij openen
  zijn ze niet als kaartvlak te zien. Dat wijkt bewust af van BO-79. De GeoPackage zelf
  verandert niet: dezelfde rijen, dezelfde kolommen, dezelfde `gwsw_run`.
- **RVZ-006 benoemt de aanwijzingen bij het gebrek** (issue #106, BO-84). De melding zei
  wél welke eis een gemengd deelstelsel miste, maar niet waardóór het los lag of
  onvolledig was; bij de review van alle vlakken moest dat per vlak met de hand worden
  uitgezocht. Achter het gebrek staat nu een tweede zin met korte feiten die de check al
  kon zien: `1 van 190 strengen gemengd; knoop X valt samen met Y van ds-… (0.00 m);
  knoop X ligt op streng Y van ds-… (0.00 m)`, en -- alleen als er géén afvoereindpunt is
  -- `persleiding X vertrekt uit Y; geen afvoereindpunt (BO-82)` en `lozingspunt X
  aanwezig; geen afvoereindpunt (BO-82)`. Per soort hooguit drie, op URI-volgorde,
  gevolgd door "… en N meer". De popup van het deelstelselvlak in de GeoPackage draagt
  ze ook: `2 gemengde strengen gemeld` wordt `2 van 2 strengen gemengd, 2 gemeld`, met de
  overige aanwijzingen op een eigen feitenregel. **De uitslag verandert niet**: dezelfde
  afbakening, dezelfde twee eisen, en op De Wolden en Hoogeveen dezelfde 1058 meldingen op
  96 deelstelsels; een persleiding of lozingspunt blijft geen afvoereindpunt (BO-82). Er
  komt geen drempel bij -- de enige grens is de bestaande `snapping_tolerantie_m` -- en
  geen kolom: de aanwijzingen reizen in de meldingstekst. Gemeten met
  `scripts/meet_rvz006_aanwijzingen.py`: 13 deelstelsels met minder dan de helft gemengd,
  8 met een samenvallende knoop, 14 met een knoop op een vreemde streng, 18 met een
  persleiding, 27 met een lozingspunt en 50 met het kale gebrek.
- **Een telbaar hulpstuk is een doorgeefknoop in de vrijvervalgraaf** (issue #105, BO-83).
  Een streng die op een `Mof`, `T_stuk`, `Y_stuk` of `Kruisstuk` eindigt viel uit de
  netwerkanalyse -- een `Hulpstuk` is geen `Put`, dus de graaf liet haar vallen -- terwijl
  zij daar in werkelijkheid aan het net vastzit; het persnet had die terugval sinds BO-54
  al. Een `Afsluitstuk` of `Ontstoppingsstuk` blijft een breuk (dezelfde grens als BO-72).
  De telbare populatie verhuist naar de nieuwe module `checks/hulpstukken.py`, zodat
  `checks/verbanden.py` en `checks/topologie.py` haar allebei kunnen lezen zonder
  importkring. Gemeten op De Wolden en Hoogeveen
  (`scripts/meet_hulpstukgraaf.py`): strengen buiten de netwerkanalyse 152 → **0**,
  netwerkdelen 794 → **733**, RVZ-006 1062 op 99 deelstelsels → **1058 op 96** (precies de
  drie valse deelstelsels uit de review van 29-08, en niets nieuws), NET-001 8467 → **8499**,
  NET-002 3031 → **3046**, NET-006 329 → **332** en NET-009 3656 → **3667** -- strengen die
  nu voor het eerst beoordeeld worden. De deelstelsel-ID's (`ds-...`) kunnen verschuiven.
  Wie de graaf leest gebruikt dezelfde afleiding: de bereikbaarheid van NET-001/002, het
  afvoerpad van een streng (en daarmee het uitstroompunt in de GeoPackage) en de strengen
  van een deelstelsel, dat laatste via de nieuwe index `strengen_per_knoop` — de put-index
  `aansluitingen` kent een streng tussen twee T-stukken niet en blijft van TOP, HGT en
  ATTR. **Tellen gebeurt in putten**: een doorgeefhulpstuk zit wel in de graaf maar telt
  niet mee in "een deelstelsel van N knopen", in `knopen_in_deelstelsel`, in de drempel
  `klein_deelstelsel_knopen`, in `examined()` van NET-006/NET-008 of in `n_knopen` van het
  deelstelselvlak; het krijgt immers nooit een bevinding.
- **NET-004 wordt richting-bewust en onderscheidt vermaasd net** (issue #102, BO-77).
  Kringlopen worden gezocht op de betrouwbare richting (de strengen die NET-009 niet
  tegenspreekt, de richtingsbron uit #80/BO-76). Een kring die alleen op een omgekeerd
  geregistreerde streng leunt, valt met de betrouwbare richting uiteen en wordt niet meer
  gemeld -- NET-009 draagt dat signaal al. Een vlakke, BOB-consistente ring geldt als bewust
  vermaasd net (in vlak Nederland legitiem); een ring die alleen via een BOB-sprong omhoog in
  een put sluit, hoort bij HGT-009. Beide worden gedempt en in de toelichting geteld. Een
  echte melding blijft een kring die op de betrouwbare richting overeind blijft en waarvan de
  BOB geen uitsluitsel geeft. Richtgetal De Wolden: 17 → 0 (hermeet).
- **NET-006 meldt alleen nog vuilwater benedenstrooms van gemengd** (issue #97, optie B).
  Op een knoop waar precies gemengd en vuilwater samenkomen is er maar één koppelingsfout:
  gemengd stroomt de knoop ín en vuilwater eruit (vuilwater benedenstrooms van gemengd).
  Elke andere betrouwbaar gerichte gemengd+vuilwater-koppeling is normaal en wordt gedempt
  -- zowel vuilwater dat in gemengd overgaat als een doorgaand gemengd hoofdriool (gemengd
  in én uit) waarop een vuilwatertak aansluit. De foutvorm en elke onbetrouwbaar of onbekend
  gerichte koppeling blijven gemeld. "Betrouwbaar" leunt op NET-009's per-streng oordeel (de
  richtingsbron uit #80, BO-76): een streng waarvan geen enkel richtingssignaal de
  administratie tegenspreekt. De toelichting telt de gedempte koppelingen. Hermeting De
  Wolden + Hoogeveen: NET-006 van 410 (ongericht) via 393 (de eerdere strikte regel) naar
  330 -- 80 koppelingen gedempt, ruim onder het −213-plafond.
- **NET-009 wordt de integrale richtingscheck en de forsgrens verschuift** (issue #80,
  BO-76). NET-009 meldt elke streng waarvan de tekenrichting of de BOB de administratieve
  van-naar-richting tegenspreekt, en is daarmee een **W** (was F); NET-003 en TOP-020 gaan
  erin op. De ongerichte-graaf "harde waarheid" uit een bereikbaar lozingspunt is
  geprobeerd maar verworpen: op De Wolden gaf zij 2.822 vals-alarmen op strengen die intern
  kloppen (het topologisch dichtstbijzijnde lozingspunt is vaak niet de werkelijke
  uitstroom). HGT-006 (fors tegenverhang) blijft F, maar de drempel `tegenverhang_fors_m`
  gaat van 0,05 naar 0,10 m: onder tien centimeter is tegenverhang in vlak Nederland
  inwinnauwkeurigheid.

- **`schema_versie` van `bevindingen.json` gaat van `1.1` naar `1.2`** (issue #101,
  BO-74). Elke melding draagt het nieuwe veld `boodschap_technisch`, en bij een
  nulmetingmelding is `boodschap` voortaan de Nederlandse zin in plaats van de
  SHACL-tekst; die staat in het nieuwe veld. De CSV krijgt om dezelfde reden de kolom
  `MeldingTechnisch` achteraan (vóór `Gereedschap`) en de meldingentabel van de
  GeoPackage de kolom `boodschap_technisch` achteraan. Melding-ID's verschuiven niet: die
  hangen aan de technische tekst. Deze ene versiestap dekt het hele blok, dus ook de
  GeoPackage-herindeling van issue #98 hieronder.
- **De GeoPackage draagt nog drie objectlagen: `putten`, `strengen` en `vlakken`**
  (issue #98, BO-73; besluit auteur 28-08). De vierde laag `gemengd_zonder_overstort`
  vervalt: haar vlakken staan nu in `vlakken` met `soort = gemengd_deelstelsel`, naast de
  bestaande soorten `pand`, `bouwwerk` en `water`. Alles wat die vlakken bijzonder maakte
  verhuist mee -- de voorgebakken `popup_html` die als enige óók de systemische meldingen
  toont (BO-59), de kolommen `n_knopen`/`n_strengen`/`strenglengte_m` (leeg bij een extern
  vlak, zoals `relatie` en `afstand_min_m` dat al waren), en de harde fout bij een
  `cluster_id` die de graaf van de run niet kent. Twee kolommen krijgen de naam die de
  externe vlakken al gebruikten: de sleutel staat in `id` (was `cluster_id`) en het aantal
  meldingen in `aantal_meldingen` (was `n_meldingen`). `gwsw_run` houdt
  `n_gemengd_zonder_overstort` en `n_gemengd_zonder_vlak`; `n_vlakken` telt sindsdien de
  hele laag, dus ook de deelstelsels. Het kaartbeeld blijft gelijk: `vlakken.qml` krijgt
  het vlaksymbool van de vervallen `gemengd_zonder_overstort.qml` als vierde regel op
  `soort`. **Contractbreuk:** een QGIS-project dat de oude laag gebruikte moet op `vlakken`
  met een filter op `soort` gezet worden, en een trendlijn op `n_vlakken` over deze grens
  heen telt appels en peren.
- **De datakarakteristieken openen met het aandeel putten zonder aanlegjaar** (issue #91,
  checkaudit 27-08). ATTR-018 is met 9.274 meldingen verreweg de grootste post, en 9.063
  daarvan staan op putten. Dat is één gebrek in de aanlevering en geen 9.063 losse
  correcties, dus de kop van het bevindingenrapport benoemt het nu als eerste regel van de
  datakarakteristieken: "**43.7% van de putten draagt geen aanlegjaar** (9063 van de 20758)
  -- een aanleveringssignaal". Teller en noemer komen uit wat er al
  is (de ATTR-018-meldingen van díé uitvoer en de rol `putten` uit `uitvoer/omvang.py`,
  met een studiegebied tot de kern afgebakend); er is geen tweede teller en geen drempel.
  Meldt ATTR-018 niets of staat er geen put in beeld, dan blijft de regel weg in plaats van
  "0%" te melden. De regel verwijst voor de losse gevallen naar het archief en niet naar
  dit rapport of de kaart: boven de systemisch-drempel vouwt het detail ze tot één regel
  (issue #76) en laat de popup ze weg (BO-59). **De meldingen per object blijven volledig
  bestaan**, ook op putniveau, en aan de check zelf verandert niets.
- **Ook de checktitel van HGT-008 laat "indicatie verwisselde BOB's" weg** (issue #84,
  blok E review). De meldingstekst was die gok al kwijt, de titel nog niet -- en die voedt
  de checkkop in het rapport, de kolom Omschrijving in de CSV en `overzicht_checks` in de
  GeoPackage. De registerregel draagt de v0.9-formulering nu als annotatie en
  `docs/dekkingsmatrix.md` is opnieuw gegenereerd; conditie, ernst en drempel blijven.
- **Drie herkomstregels zeggen weer wat de check werkelijk doet** (issue #96, checkaudit
  27-08). **EXT-003** declareerde het kenmerk `VormLeiding` zonder het te lezen: de
  AST-sweep van issue #64 las `kruising.vorm` -- de geometrie van het waterdeel -- als de
  profielvorm van een streng. Dat veld heet nu `waterdeel`, en de declaratie is
  `kenmerken = ()`; de rapport- en dekkingsmatrixregel noemt dus geen kenmerk meer.
  **RVZ-011 en ADM-007** zeiden "Toetst de hele export" terwijl ze een smalle
  deelpopulatie bekeken; beide noemen die nu zelf (`Check.populatie_omschrijving`, ook op
  `CheckOutcome`): "de overstortdrempels die aan een put hangen" respectievelijk "de
  putten van de geconfigureerde puttypen (`[[puttyperegels]]`)". "De hele export" blijft
  staan waar ze klopt (ATTR-014). **Conditie, ernst en drempels wijzigen bij geen van de
  drie**, dus geen enkele bevinding beweegt. **BO-34** draagt een datumnotitie: NET-007
  meldt sinds issue #42 156 van de 340 infiltratieriolen, niet alle 340.
- **NET-001 en NET-002 noemen het stelseltype van de streng en het eindpunt dat ze zoeken**
  (issue #93). De twee checks delen nul objecten -- `vuilwater`/`gemengd` tegenover
  `hemelwater`, en elk een ander eindpunt -- maar zeiden allebei alleen "Geen afvoerpad
  naar ⟨doel⟩", zodat uit de melding zelf niet te lezen was welke van de twee aansloeg.
  De tekst luidt nu "Streng van stelseltype 'gemengd' zonder afvoerpad naar een gemaal,
  overnamepunt of lozingspunt". Het stelseltype komt per streng uit
  `[klassen.stelseltypen]` -- NET-001 gaat over twee typen tegelijk, dus de rol waarop hij
  selecteert (`vuilwater`) zegt minder dan het type van de streng zelf -- en staat ook in
  het detailveld `stelseltype`, dat tot nu toe de rol herhaalde. **NET-002 noemt als
  bestemming alleen nog het lozingspunt:** die check leest uitsluitend de rol
  `lozings_eindpunt`, en `Overnamepunt` staat in `afvoer_eindpunt`, dus een overnamepunt
  is er nooit een bestemming geweest terwijl de tekst hem wel noemde. De titel uit het
  checkregister (v0.9) noemt hem nog wel en blijft ongewijzigd. **Conditie, ernst en
  drempels wijzigen bij geen van beide**, dus de aantallen blijven 8.467 (NET-001) en
  3.031 (NET-002).
- **ATTR-016 scheidt een niet-geregistreerde maat van een echte tegenspraak** (issue #92).
  De uitslag bestaat uit twee soorten die om een andere ingreep vragen: op De Wolden en
  Hoogeveen dragen 67 van de 88 gemelde ronde putten een lengte van 0 mm -- geen meting
  maar een gat in de aanlevering, dat de nulmeting bij 70 van de 88 ook al als
  `LengtePut_val` meldt -- en de overige circa 21 twee echte maar ongelijke maten, de
  eigenlijke tegenspraak tussen vorm en maten. Een maat van 0 krijgt daarom de tekst
  "Putvorm Rond met breedte 800 mm, maar lengte 0 mm; 0 is geen maat, dus de lengte is
  niet geregistreerd"; twee echte maten houden de bestaande tekst. **De conditie, de
  ernst en `rondheid_tolerantie_mm` wijzigen niet**, dus het aantal blijft 88; alleen de
  boodschap splitst. Nieuwe fixture `attr016_ronde_put_lengte_nul.ttl`.
- **Drie meldingsteksten beweren niet langer meer dan de check meet** (issue #84, PRE-5).
  **HGT-008** laat "mogelijk zijn de BOB's verwisseld" weg: dat was een gok bovenop de
  meting, en een extreem verhang kan net zo goed een lengte- of een BOB-fout zijn of een
  echte val. **ATTR-003** vraagt om een controle in plaats van iets vast te stellen ("Te
  controleren of materiaal PVC in 1954 al werd toegepast: dat is voor 1958."): op één na
  (het asbestverbod van 1993) zijn de tijdvakken ervaringsregels, en een gerenoveerd riool
  zonder `DatumMaatregel` geeft dezelfde uitslag. **RVZ-001** zegt "geen actieve
  aangesloten streng (loze leidingen niet meegerekend)" én doet dat nu ook: de check
  filtert de rol `lozeleidingen` (`LozeLeiding` = buiten gebruik, dezelfde grens die
  ADM-010 hanteert) uit de aansluitingen, want een randvoorziening die alleen aan een
  leiding buiten gebruik hangt is feitelijk niet aangesloten. Het filter zit in RVZ-001 en
  niet in de gedeelde index van `verbanden.aansluitingen`, dus geen andere check verandert;
  RVZ-001 declareert de rol `lozeleidingen` erbij. Conditie, ernst en drempels blijven bij
  alle drie ongewijzigd; alleen RVZ-001 kan meer meldingen geven (op De Wolden en
  Hoogeveen nog niet gemeten -- de hermeting hoort bij de blokregie). Nieuwe fixture
  `rvz001_overstort_aan_loze_leiding.ttl`.
- **TOP-019 herleidt een strengeinde nu ook via een hulpstuk** (issue #88). De check zocht
  zijn functieloze knopen op `verbonden_knopen()`, en dat herleidt elk strengeinde naar de rol
  `netwerkknopen` -- een `Hulpstuk` zit daar niet in. Twee van de vier geconfigureerde
  functieloze klassen (`Ontstoppingsstuk`, `Verbindingsstuk`) zíjn een hulpstuk en de andere
  twee (`LozePut`, `BlindePut`) hebben in De Wolden en Hoogeveen nul instanties, dus de index
  bleef per constructie leeg: 0 van de 46.880 strengeinden kwam op een functieloze knoop uit
  en de nul in het rapport las als "geen pseudo-knopen gevonden" terwijl er niets gemeten was.
  De herleiding valt nu terug op de rauwe `start_node`/`end_node` waar `resolve_network_node`
  niets oplevert -- hetzelfde patroon dat `_bouw_hulpstuktelling` voor TOP-022/TOP-023 al
  gebruikt. Twee strengen die door een T-stuk gescheiden worden en in diameter, materiaal én
  stelseltype gelijk zijn, melden voortaan. Een streng met beide einden op dezelfde knoop
  telt daarbij als één streng en niet als een paar (zoals in `_bouw_aansluitingen`), anders
  zou zij met zichzelf vergeleken worden en altijd melden. De configuratie
  (`[klassen] functieloze_knoop`) en de kenmerkvergelijking blijven ongewijzigd; het effect op
  De Wolden en Hoogeveen is nog niet gemeten en hoort bij de blokregie.
- **TOP-002 en TOP-003: een hulpstuk met een telbare GWSW-functie is een geldig strengeinde**
  (issue #89, BO-72). Een `Hulpstuk` valt in het GWSW onder `Constructieonderdeel` en niet
  onder `Put`, dus een streng die op een T-stuk eindigt had daar geometrisch "geen put" --
  45 van de 56 TOP-002-meldingen en 107 van de 109 TOP-003-meldingen kwamen daaruit voort,
  terwijl het oordeel van de auteur bij de steekproef luidt: "Streng ligt tussen 2 T-stukken.
  Is voor deze analyse goed." Als geldig eind telt nu naast een netwerkknoop ook een hulpstuk
  waarvan de GWSW-klasse een functie mét aantal leidingen draagt (`Mof` 2, `T_stuk` en
  `Y_stuk` 3, `Kruisstuk` 4) -- precies de populatie die TOP-022 en TOP-023 al toetsen, uit
  dezelfde tabel, zodat er geen tweede klassenlijst ontstaat. Een `Afsluitstuk` of
  `Ontstoppingsstuk` draagt wel een functie maar geen aantal en telt dus **niet** als eind: een
  streng die daarop doodloopt blijft gemeld. Het gebrek "hulpstuk mist leidingen" blijft
  onverkort zichtbaar via **TOP-022** (224 F op 1.054 telbare hulpstukken). Beide checks
  declareren de rol `hulpstukken` erbij en verantwoorden de regel in hun toelichting. Verwacht
  effect op De Wolden en Hoogeveen: TOP-002 **56 → ~11**, TOP-003 **109 → ~2**; TOP-022
  verandert niet. De hermeting hoort bij de blokregie.
- **Het compartimentduplicaat (`c<n>`-postfix) wordt vóór de topologiechecks samengevoegd**
  (issue #85, BO-71). De Kikker/BrutIS-export schrijft een gecompartimenteerde put per
  compartiment uit: elk deel is een eigen put op dezelfde coördinaat, met het putlabel plus
  `c1`, `c2`, ... De putchecks zagen er twee -- het strengeinde snapt op één ervan, dus de
  ander heet losliggend (TOP-001) en het paar een dubbele put (TOP-005). Twee knopen gelden
  nu als hetzelfde object wanneer hun labels op die postfix na gelijk zijn **én** ze binnen
  `[drempels] dubbele_put_tolerantie_m` (0,30 m) samenvallen; het origineel wint (de knoop
  zonder postfix, anders de laagste postfix). Een knoop zonder postfix wordt nooit
  weggenomen, dus een gewone dubbele put blijft gemeld. Negen checks dragen de toelichting
  die de samenvoeging verantwoordt: de zeven die de puttenindex aflopen -- TOP-001, TOP-005,
  TOP-009, TOP-014, TOP-015, TOP-016 en TOP-021 -- plus TOP-002 en TOP-003, die hem via de
  snapping lezen. Twee dingen staan er met opzet bij, want ze zijn de prijs van de
  samenvoeging: wat alleen op het duplicaat stond is daarna niet meer getoetst (het wordt
  niet bij het origineel opgeteld), en omdat de dubbele-put-tolerantie ruimer is dan
  `snapping_tolerantie_m` (0,10 m) kan een duplicaat dat verder dan die maat van het
  origineel ligt zijn strengeinde de aansluiting kosten -- dan meldt TOP-002 of TOP-003 dat.
  Op De Wolden en Hoogeveen gebeurt dat niet: alle groepen vallen op 0,000 m samen. Bewust
  ongemoeid: de netwerkgraaf, de administratieve koppeling (dus ook TOP-004), de afbakening,
  de GIS-lagen en de leeslaag `gwsw-orox-helpers`. Gemeten op de export (tekstscan, geen
  toetsrun): 189 zulke labels in 98 groepen (`c1` 96x, `c2` 92x, `c3` 1x), onderling op
  0,000 m, waarvan er **94** samengevoegd worden. Verwacht effect op De Wolden en Hoogeveen:
  TOP-001 **102 → ~9**, TOP-005 **112 → ~20**, TOP-021 **5 → ~3**. De hermeting hoort bij de
  blokregie.
- **TOP-006 meldt pas bij 2 cm samenval over 2 m; de TOP-010-marge blijft 0,0 m**
  (issue #100, BO-70). `overlap_tolerantie_m` gaat van 0,05 naar 0,02 m en
  `overlap_minimale_lengte_m` van 1,0 naar 2,0 m: twee buizen die binnen 5 cm van elkaar
  blijven zijn niet per se dubbel ingetekend -- dat past binnen de inwinnauwkeurigheid --
  terwijl de check het echte duplicaat zoekt, dezelfde buis twee keer in de dataset. Wie
  de bredere nabijheid wil zien houdt TOP-010 en TOP-013. `diameterbuffer_marge_m` blijft
  0,0 m, nu expliciet bekrachtigd: over 20 cm marge beweegt TOP-010 maar 6% (1.325 →
  1.401) en de gemelde overlaps zijn diep (mediaan 0,31 m), dus of zo'n kruising een echt
  conflict is beslist de hoogte (HGT-004/009/018) en niet deze marge. Verwacht effect op
  De Wolden en Hoogeveen, ná #82: TOP-006 **39 → ~13**, TOP-010 ongewijzigd op 1.359. De
  hermeting hoort bij de blokregie. Meting: `scripts/meet_v5_gevoeligheid.py`.
- **TOP-006, TOP-010 en TOP-011 toetsen alleen nog vrijverval tegen vrijverval of duiker**
  (issue #82, BO-69). De drie checks die twee leidingen naast elkaar leggen -- overlap,
  buisbuffer en hartlijnkruising -- draaiden op de brede rol `leidingen` en meldden dus ook
  een vrijvervalriool dat een persleiding, een drain of een aansluitleiding kruist. Dat is
  geen gebrek: een persleiding ligt er nu eenmaal doorheen. **Beide** partijen van een paar
  moeten voortaan onder de nieuwe rol `nabijheidsleidingen` vallen (`[klassen]
  nabijheidsleiding` = `VrijvervalRioolleiding`, `Duiker`); drains, mechanische leidingen
  en aansluitleidingen vallen erbuiten. Verwacht effect op De Wolden en Hoogeveen:
  TOP-006 **81 → 39 of minder**, TOP-010 **2.184 → ~1.057** en TOP-011 **1.872 → ~1.012**
  (de audit-meting van 27-08 gaf 39, 1.359 en 1.161 met alleen de drains en het persnet
  eruit; de aansluitleidingen kosten TOP-010 er nog 302 en TOP-011 er nog 149). De
  hermeting hoort bij de blokregie. De toelichting van alle drie noemt de klassen en telt
  hoeveel leidingen erbuiten vielen. `[klassen] nabijheidsleiding` staat in beide
  configbestanden en als default in `ClassRoots`, niet in de code.
- **HGT-003 meldt pas boven de 4,0 m diepteligging** (issue #99, BO-68).
  `bob_maximale_diepte_m` gaat van 3,0 naar 4,0 m: 3,0 m is de aanlegdiepte die het PvE
  Functionele eisen vrijverval riolering van Rotterdam voor *nieuw* gebied stelt, en in
  bestaand gebied ligt riool legitiem dieper (een landelijke maximumnorm bestaat niet).
  Op De Wolden en Hoogeveen zakken de dieptemeldingen van **1.042 naar ~123**; de 48
  meldingen "BOB boven het AHN-maaiveld" blijven staan, dus het totaal gaat van 1.090
  naar ~171. De titel van de check draagt de drempel niet meer als getal ("boven maaiveld
  of onaannemelijk diep eronder" in plaats van "meer dan 3 m eronder"), want de drempel
  is configureerbaar; in plaats daarvan noemt de toelichting van HGT-003 de gehanteerde
  grens uit de config ("Gemeld vanaf een diepteligging van meer dan 4 m onder het
  AHN-maaiveld"), zoals HGT-001 en HGT-002 hun band al noemden.
- **EXT-007 toetst alleen nog de lozingspunten die op oppervlaktewater lozen** (issue #94,
  BO-67). De populatie is de nieuwe rol `waterlozingspunten` (`[klassen]
  waterlozingspunt`): `Uitlaatconstructie` (met `Nooduitlaat` en `Uitstroombak` eronder),
  `UitlaatPunt` en `LozingspuntOppervlaktewater` — de drie klassen waarvan de
  GWSW-ontologie zegt dat er water naast hoort te liggen. `Lozingsput` valt eruit: die
  loost volgens het GWSW "naar, of ontvangt uit, een ánder rioolstelsel", en de wortel
  `Lozingspunt` ook, want daaronder hangt `LozingspuntBodem`. Op De Wolden en Hoogeveen
  stond 32 van de 71 meldingen op een lozingsput; verwacht effect **71 → 39**, bekeken
  767 → 712. De brede rol `lozingspunten` verandert niet — NET-001, NET-002 en NET-008
  hebben haar als netwerkeindpunt nodig. De toelichting van de check noemt voortaan welke
  klassen meetellen en hoeveel lozingspunten erbuiten vielen. De klassenlijst staat in
  beide configbestanden en als default in `ClassRoots`, niet in de code.
- Leeslaag (dataset, graaf, geometrie, ontologie, cache, voortgang) afgesplitst naar de
  package gwsw-orox-helpers 0.1.0 (MIT); `--ontologie` is optioneel geworden en valt terug
  op de gebundelde GWSW-ontologie 1.6.
- **De standaardcachemap is verhuisd** van `~/.cache/nlriochecker` naar
  `~/.cache/gwsw-orox-helpers`, met de leeslaag mee. De oude map blijft als wees achter en
  ruim je zelf op; de eerste run na deze overgang vindt geen cache en parseert koud.
- **De systemisch-vlag geldt pas vanaf 100 bekeken objecten** (eindreview #72–#77,
  BO-59). Nieuwe drempel `[rapport] systemisch_minimum_bekeken` (standaard 100): onder
  dat aantal bekeken objecten is een uitslag nooit systemisch, hoe hoog de ratio ook is.
  Op een klein gebied haalde de ratio anders de grens op een handvol objecten — RVZ-006
  slaat op Koekangerveld op alle 26 gemengde strengen aan — en verdween een echt gebrek
  uit de kaartpopup en uit de tabel per object. Op De Wolden en Hoogeveen blijven RVZ-002
  en RVZ-003 (245 van 245) systemisch en blijft ATTR-014 dat op eigen declaratie; alleen
  de kleine populaties vallen eruit. Daarbij leidt het vlak in
  `gemengd_zonder_overstort` zijn status en popup niet langer af uit de
  systemisch-gefilterde meldingen: zo'n vlak bestaat alleen omdat RVZ-006 aansloeg en is
  per constructie een gebrek, dus "geen eigen gebrek" hoort er niet te staan.
- **Alleen de bereikbaarheidschecks gaan nog over het persnet** (eindreview #72–#77,
  BO-54). De bereikbaarheidsgraaf (vrijverval plus mechanisch riool als ongerichte
  kanten) was een veld op `_Netwerk` en werd dus door `_bouw_netwerk` altijd meegebouwd;
  de AST-sweep van BO-51 zag de rol `mechanischeleidingen` daardoor vanuit alle negen
  NET-checks, en sinds issue #77 stond dat als "gaat over: mechanischeleidingen" in het
  rapport, in `overzicht_checks.populatie` en in de JSON — ook bij NET-004, dat het
  persnet juist niet mág zien. De laag wordt nu lui gebouwd
  (`verbanden._bereikbaarheid`), en alleen NET-001, NET-002 en NET-008 declareren de rol.
  De uitkomsten veranderen niet: NET-001 8467 en NET-002 3031 op De Wolden en Hoogeveen,
  gelijk aan vóór deze wijziging.
- **De afbakening tot een studiegebied houdt de checkdeclaratie vast** (issue #77).
  `CheckRun.beperk_tot_studiegebied` bouwde elke uitslag opnieuw op met een opsomming die
  `rollen` en `kenmerken` oversloeg, zodat elk gebiedsrapport "Toetst de hele export" zei
  in plaats van de klassen en kenmerken van de check.
- **Systemische bevindingen staan generiek in het rapport en in de popup** (issue #76).
  Een systemische bevinding is dezelfde structurele kwestie op (vrijwel) elk object; per
  object opgesomd verdringt zij de gebreken die dat object van zijn buren onderscheiden.
  De detailsectie van een eigen check vervangt haar rijen daarom door een regel met
  check, aantal en bekeken populatie -- dezelfde vorm waarin het nulmetingblok al per
  SHACL-vorm samenvat -- en de GeoPackage-popup laat ze weg en telt ze in een
  afsluitende regel. De scheiding gaat per melding: is maar een deel van de bevindingen
  systemisch, dan staat de rest gewoon per object. CSV, JSON en de meldingentabel van de
  GeoPackage veranderen niet: daar blijft elke rij staan, met haar `systemisch`-vlag.
- **De stelsellaag maakt plaats voor een RVZ-006-vlak, en RVZ-006 meldt per gemengde
  streng** (issue #75, BO-57). De cartografische laag `stelsels` groepeerde strengen via de
  GWSW-stelselregistratie -- een groepering die niet betrouwbaar is -- en toonde er een
  netwerkfeit op (wel of geen afvoerroute). Zij vervalt, met `uitvoer/stelsels.py`,
  `stelsels.qml` en de kolom `n_stelsels` in `gwsw_run`; de kolom `stelsel` op `putten` en
  `strengen` blijft. RVZ-006 hangt zijn bevinding niet langer aan de lexicografisch eerste
  knoop van een gemengd deelstelsel maar aan **elke gemengde streng** ervan, met een
  gedeelde `cluster_id` zodat rapport en kaart ze als één deelstelsel groeperen; het
  zwaartepunt als foutlocatie vervalt en `examined` telt nu de gemengde strengen. Nieuw is
  de laag **`gemengd_zonder_overstort`** (MULTIPOLYGON, met eigen QML): een vlak per
  gemengd deelstelsel waarop RVZ-006 aansloeg, als buffer om de strengen van de hele
  component, gebouwd uit de meldingen van díé uitvoer. De drempel `stelselvlak_buffer_m`
  heet daarom `gemengd_zonder_overstort_buffer_m` (10 m, ongewijzigd) en `gwsw_run` telt de
  laag in `n_gemengd_zonder_overstort`, met `n_gemengd_zonder_vlak` ernaast voor de gemelde
  deelstelsels waarvan geen enkele streng een bruikbare lijn draagt; een `cluster_id` die de
  graaf niet kent is een harde fout, net als bij de trefferlaag. Op De Wolden en Hoogeveen gaat RVZ-006 van **99**
  naar **1062** bevindingen op dezelfde **99** deelstelsels (Koekangerveld 2 → **26** op 2);
  de selectie verandert niet, alleen de korrel. Een SHACL-overtreding op een geregistreerd
  stelsel landde op de vervallen laag en zou nu stil van de kaart verdwijnen; het rapport
  telt haar daarom expliciet als "geen kaartobject" (op De Wolden 567 van de 578). Meetscript:
  `scripts/analyse_rvz006_per_streng.py`.
- **Drukriolering is traceerbaar: het persnet telt mee in de bereikbaarheidsgraaf en een
  lozingspunt is een geldig vuilwater-eindpunt** (issue #72). `_bouw_netwerk` levert naast
  de gerichte vrijvervalgraaf een tweede laag `_Netwerk.bereikbaarheid`: dezelfde graaf plus
  de mechanische leidingen als **ongerichte** kanten, doorlopend via hulpstukken (waar
  `resolve_network_node` niets oplevert valt de kant terug op de rauwe koppeling, zodat een
  T-stuk een doorgeefknoop wordt in plaats van een breuk). Alleen `_bereikbaar_vanaf`,
  `_eindpunten` en de notities eromheen lezen die laag; kringlopen, stelseltypen en de
  afvoerpadanalyse blijven op het zuivere vrijverval. NET-001 accepteert daarnaast naast
  `afvoer_eindpunt` ook `lozings_eindpunt` als eindpunt -- vuilwater loost in Nederland niet
  meer rechtstreeks op oppervlaktewater, dus een lozingspunt is per definitie een geldig
  afvoereindpunt. Op De Wolden en Hoogeveen gaat NET-001 daarmee van **9062** naar **7978**
  bevindingen, in Koekangerveld van **24** naar **7**; NET-002 volgt hetzelfde persnet en gaat
  van **3054** naar **3031** (alle 23 komen langs het persnet op een lozingsput uit). Geen van
  beide checks krijgt er een bevinding bij. Alle 939 niet-oplosbare tussenknopen
  in het persnet blijken hulpstukken te zijn. De negen NET-checks declareren voortaan ook de
  rol `mechanischeleidingen`. Zie BO-53 en BO-54.

- **Een pompunit is geen afvoereindpunt meer, en de contextschil volgt het persnet**
  (issue #73, vervolg op #72). `[klassen] afvoer_eindpunt` is `["Overnamepunt", "Gemaal"]`:
  `gwsw:Pompunit` is een `Rioolput` in het mechanische stelsel en daarmee een
  overdrachtspunt naar de drukriolering, niet het einde van de afvoer. Hij stond er als
  noodverband in omdat de graaf het persnet niet volgde (BO-33); issue #72 heeft die reden
  weggenomen. NET-001 gaat op De Wolden en Hoogeveen van **7978** naar **8467** bevindingen
  (Koekangerveld blijft **7**, precies de voorspelling), RVZ-006 van **98** naar **99** --
  beide checks lezen dezelfde lijst -- en NET-002 blijft **3031**. De deelreden van RVZ-006
  luidt voortaan "zonder afvoereindpunt (gemaal of overnamepunt)". Daarnaast legt
  `afbakening._componentstructuur` de mechanische leidingen nu ook in de componentgraaf:
  zonder het persnet in de contextschil viel het gemaal achter de persleiding buiten de
  analyseset, en week een gebiedsrun af van de gemeentebrede run -- 17 van de 88 CBS-buurten,
  nu 0. De analysesets van die 88 buurten groeien daarmee 1,7x. Omdat een projectconfig
  standalone gevalideerd wordt en niet over `checks.toml` heen gelegd, weigert
  `ClassRoots` voortaan de combinatie van een `afvoer_eindpunt` zonder `Pompunit` met
  een lege `mechanisch`: zonder persnet zou NET-001 elke streng op een pompput vals als
  onbereikbaar melden. Zie BO-55 en BO-56.

- **Geen vrijvervalrichting meer op gepompte leidingen** (issue #74). De richtingspijl in
  de laag `strengen` komt uit het BOB-verval, maar een mechanische leiding is pompgestuurd
  en draagt geen betrouwbare vrijverval-BOB. De schrijver zet `richting_bob` daarom op
  `onbekend` voor elke leiding uit de rol `mechanischeleidingen` (`[klassen] mechanisch`:
  `MechanischeRioolleiding` met Drukleiding, Luchtpersleiding en Vacuumleiding, en
  `MechanischeTransportleiding` met Persleiding, Leidingsegment en Spoelleiding), in plaats
  van daar toevallig op terug te vallen: op De Wolden en Hoogeveen kregen **44** van de 3720
  mechanische strengen (23 mee, 21 tegen) een fysiek onjuiste groene of rode pijl, nu **0**.
  In de GeoPackage van 24-08 zijn dat er 22; die dateert van vóór de laderfix van issue #60,
  die 22 van deze leidingen alsnog een herleidbare tekenrichting gaf. **Alleen de pijl
  vervalt:** `bob_verval_m` wordt precies zo berekend als voorheen en blijft op zo'n leiding
  staan, want dat is een gemeten waarde en geen bewering over de stroomrichting -- zonder
  haar was een mechanische leiding mét BOB niet meer te onderscheiden van een zonder. De
  grijze `onbekend`-stijl wordt hergebruikt (geen QML-wijziging); alleen de popupregel
  splitst en zegt op zo'n leiding "mechanische leiding — geen vrijvervalrichting" in plaats
  van "BOB-richting niet te bepalen".

- **De nul-bewaking en de rollentelling leiden hun rollen uit de checkdeclaraties af**
  (issue #71, vervolg op #64). `omvang._rollen` was een handlijst van zes rollen; nu
  verzamelt hij de rollen die de geregistreerde checks in `check.rollen` declareren, lost
  ze via `selectie.klassen_van_rol` op naar klassen en telt via `of_class`. De
  `SIG-nulklasse`-melding noemt voortaan welke checks op de lege rol leunen (het gat uit
  issue #22, nu generiek). De twee bewakingen die geen `selectie._ROLLEN`-rol uitdrukken
  blijven expliciet: het afvoereindpunt per klasse (`Overnamepunt`/`Gemaal`, BO-33 en
  BO-55) en de overstortdrempel via `subjects_of_class` (NET-007). De "Per rol"-tabel en
  de nul-signalen lezen dezelfde bron en lopen niet meer uiteen. Zie BO-52.

- **De putdiepte-, putbodem- en dekselchecks toetsen op `Rioolput`, niet op elk netwerkknoop**
  (issue #64). Een nieuwe rol `rioolputten` (`[klassen] rioolput = ["Rioolput"]`) vervangt
  `netwerkknopen` in HGT-012 (putdiepte) en HGT-015 (putbodem); in HGT-004, HGT-016 en
  HGT-017 wordt alleen de deksel-/bodemtak tot de rioolputten beperkt, terwijl de
  bovenkanttak (met terugval op maaiveld) breed blijft. `HoogtePut` en het daaruit afgeleide
  bodemniveau hangen aan een put met een deksel, niet aan een gemaal of uitlaat. HGT-001/002/011/018
  en BTR-006 blijven op `netwerkknopen` (de maaiveld-terugval is zinvol voor elk object) en
  staan met reden op de uitzonderingslijst van de ontologietest.

- **Meldingen onderdrukken per klasse en per check** (issue #65). `[rapport]` krijgt
  `onderdruk_klassen` (GWSW-wortelklassen, subklassen via de ontologie) en `onderdruk_checks`
  (alleen ID's uit het checkregister; een onbekend ID faalt bij het laden -- een
  nulmetingsvorm of datasetsignaal onderdruk je via de klasse). Het filter zit op één plek,
  in de meldingenstroom vóór elke schrijver, en telt wat wegviel: in de
  verantwoording van het rapport, in `totaal/synthese.md`, in `gwsw_run`
  (`onderdruk_klassen`, `onderdruk_checks`, `meldingen_onderdrukt`) en als optioneel veld
  `onderdrukt` in de JSON-envelop (`schema_versie` blijft 1.1). "Per check" telt élke
  weggevallen melding onder haar check-ID -- precies het verschil met de kolom Bevindingen --
  en "per klasse" het deel dat op klasse wegviel. Elk object van een onderdrukte klasse is
  grijs op de kaart, ook zonder meldingen erop, met de reden "klasse onderdrukt in de
  projectconfiguratie; meldingen erop komen niet in de uitvoer". De CSV draagt de lijsten niet.
  `configs/dewoldenhoogeveen.toml` onderdrukt het mechanische riool. Op De Wolden en Hoogeveen
  vallen zo 10345 meldingen weg en gaan 3652 strengen van gekleurd naar grijs (BO-49).

- **ADM-010 en ADM-011: loze leidingen die in het actieve netwerk hangen** (issue #62).
  Loze leidingen (`LozeLeiding`, buiten gebruik) worden tot ketens gegroepeerd; ADM-010
  (F) meldt per loze streng een keten waar actief riool op aansluit (doorgaand, aanvoer
  of afvoer, in de administratieve richting), ADM-011 (W) een keten waar in die richting
  niets binnenkomt en niets verder gaat. De keten staat in `cluster_id`, het aantal actieve
  strengen bovenstrooms als detail, en `rakend` noemt de actieve strengen die een
  ketenknoop wel raken maar tegen de richting in of ernaast liggen.
  Nieuwe rol `[klassen] loze_leiding`. Gemeten op De Wolden en Hoogeveen: 54 loze
  leidingen in 33 ketens -- 3 doorgaand (8 strengen), 11 aanvoer (16), 5 afvoer (14) en
  14 losgekoppeld (16) -- dus 38 F en 16 W. Zie BO-47.

- **TOP-022 en TOP-023: hulpstuk met een ander aantal aansluitingen dan zijn
  GWSW-functie voorschrijft** (issue #60). Het verwachte aantal komt uit de
  `functie`-restrictie op de klasse in de ontologie (`Mof` 2, `T_stuk`/`Y_stuk` 3,
  `Kruisstuk` 4); geteld naar verschillende buurknopen, zodat een dubbel gelegde
  richting een keer telt. TOP-022 (F) meldt te weinig, TOP-023 (W) te veel; klassen
  zonder aantal in hun functie (afsluitstuk, ontstoppingsstuk, tubelure) vallen buiten
  de toets en staan geteld in de toelichting. Nieuwe rol `[klassen] hulpstuk`. Gemeten
  op De Wolden en Hoogeveen: TOP-022 224 (94 met een richting, 130 met twee) en
  TOP-023 37 (36 met vier, 1 met vijf) op 1054 T-stukken; 68 hulpstukken (58
  afsluitstuk, 10 ontstoppingsstuk) vielen buiten de toets. Zie BO-46.

- **ATTR-018: ontbrekende begindatum wordt per object gemeld** (issue #61). Een
  vrijvervalrioolleiding of put zonder `Begindatum` krijgt een fout (Compleetheid); tot nu
  toe stond het gat alleen als één regel in de toelichting van ATTR-007 en bleef zo'n
  object op de kaart groen. De GeoPackage-lagen `putten` en `strengen` dragen de nieuwe
  kolom `begindatum_jaar` (leeg zonder datum). De meetsetregel van ATTR-007 vervalt; de
  regel die zegt wat ATTR-007 zelf niet kon toetsen blijft. Op De Wolden en Hoogeveen:
  9274 bevindingen (9063 putten, 211 strengen), niet systemisch. Zie BO-45.

### Gewijzigd

- **RVZ-002 zegt in één melding welke drempelmaat ontbreekt** (issue #87, BO-78). De check
  meldt voortaan per overstortput welke van {`Drempelniveau`, `Drempelbreedte`} niet
  geregistreerd is -- in de tekst en in het nieuwe detailveld `ontbrekende_maten` -- ook als
  er helemaal geen `Overstortdrempel`-onderdeel aan de put hangt. RVZ-003 (de aparte
  breedtecheck) is hierin opgegaan (zie Verwijderd): op De Wolden meldden de twee exact
  dezelfde 245 putten, want de export draagt geen enkel drempelobject en dan ontbreken beide
  maten samen. Hermeting: 245 meldingen in plaats van 490, inhoud gelijk.

- **Eén GeoPackage-laag `vlakken` vervangt `bouwwerken` en `waterdelen_zonder_zinker`**
  (issue #67). De externe objecten waarnaar de EXT-meldingen verwijzen staan nu in één laag
  (MULTIPOLYGON) met de kolom `soort` (`pand`, `bouwwerk`, `water`); `subtype`, `relatie` en
  `afstand_min_m` (leeg bij water) en `check_ids` vervangen de aparte kolommen, en `buffer_m`
  vervalt (runmetadata, staat in `gwsw_run`). Eén stijl `vlakken.qml`, rule-based op `soort`,
  vervangt de twee oude QML's. EXT-002 registreert voortaan zijn doorkruiste waterdeel als
  treffer, zodat het eindelijk een vlak krijgt: een waterdeel dat zowel EXT-002 als EXT-003
  raakt is één rij met `check_ids = "EXT-002, EXT-003"`. In `gwsw_run` vervangt `n_vlakken` de
  kolommen `n_bouwwerken` en `n_waterdelen`. **Contractbreuk:** de lagen `bouwwerken` en
  `waterdelen_zonder_zinker` bestaan niet meer; QGIS-projecten die erop wezen moeten opnieuw
  gekoppeld worden aan `vlakken`. Op De Wolden en Hoogeveen met Koekangerveld als bereik: zie
  BO-50.

- **`toets --uitvoer csv|json|gpkg` vervangt `--geen-gpkg` en `--geen-json`** (issue #66).
  Eén bevestigende, herhaalbare optie zegt welke bijproducten er naast het Markdown-rapport
  komen; standaard alle drie, en ook de CSV is nu uit te zetten. Het rapport wordt altijd
  geschreven: het draagt de markering en het voorbehoud. De twee oude vlaggen vervallen
  zonder alias; wie ze opgeeft krijgt de gewone optiefout. `Toetsopdracht` krijgt `met_csv`,
  `Uitvoer.csv` kan `None` zijn en `write_check_report` geeft voortaan
  `tuple[Path, Path | None]` terug. Het rapport en de totaalsynthese verwijzen alleen naar de
  bijproducten die daadwerkelijk geschreven zijn.

- **`schrijf_uitvoer` neemt `stroom=` in plaats van `meldingen=`** (issue #65). Wie de vier
  uitvoervormen zelf aanstuurt gaf een `list[Melding]` mee; dat is nu een `Meldingenstroom`
  (`uitvoer.melding.bouw_meldingenstroom`), zodat de meldingen en de telling van de
  onderdrukking niet los van elkaar kunnen raken. Zonder argument bouwt hij de stroom zelf;
  alleen een beller die de lijst expliciet meegaf, past zijn aanroep aan.

- **De CI-poort classificeert overslagen op reden; de telgrens vervalt** (BO-48).
  `NLRIOCHECKER_MAX_OVERGESLAGEN` telde ook de bedoelde, datagebonden overslagen mee en
  klapte twee keer op legitieme testgroei. Met `NLRIOCHECKER_STRIKTE_OVERSLAG` is voortaan
  elke test-overslag zonder `data/` of `BO-` in zijn reden een harde fout. Nieuw:
  `scripts/runnerpoort.py` draait dezelfde poort lokaal in de conditie van de CI-runner
  (alleen getrackte `data/`, geen PyQGIS, dezelfde grenzen uit de workflow).

- **HGT-001 waarschuwt vanaf 10 cm AHN-afwijking, inclusief** (issue #63). De
  waarschuwingsdrempel `ahn_afwijking_waarschuwing_m` gaat van 0,05 naar 0,10 m, omdat
  5 cm binnen de onzekerheid van de AHN-inwinning zelf ligt. De banden zijn halfopen en
  worden op millimeters afgerond vergeleken: HGT-001 meldt `[0,10 – 0,25)`, HGT-002
  `[0,25 – ∞)`; een object krijgt nooit beide meldingen en de toelichting noemt de
  gehanteerde drempel. Op De Wolden: HGT-001 5811 → 2847 en HGT-002 2128 → 2132 (vier
  meldingen die op 0,250 m afronden schuiven van W naar F). Zie BO-44.

### Gerepareerd

- **De populatie van TOP-006, TOP-010 en TOP-011 is de rol `nabijheidsleidingen` zelf, en
  niet haar doorsnede met de leidingenrol** (blok C-review van #82). `_bouw_nabijheid` liep
  over `[klassen] streng` en hield daarvan wat óók onder `[klassen] nabijheidsleiding` viel;
  de twee lijsten zijn los configureerbaar, dus versmalde een project `streng` tot de
  vrijvervalleiding, dan viel de duiker stilzwijgend uit de populatie en meldden de drie
  checks er niets meer over. De verantwoordingsregel in de toelichting telt mee over de
  vereniging van beide rollen, zodat "X van de N leidingen vallen daarbuiten" met N − X de
  werkelijk getoetste populatie noemt. Met de standaardconfiguratie (`streng = ["Leiding"]`)
  verandert er niets. Het meetscript `scripts/meet_v5_gevoeligheid.py` achter BO-70 gaf `_buren` sinds
  #82 een `_Topologie` in plaats van de nabijheidsindex -- de STRtree van pútpunten -- en
  leest nu `_nabijheid(context)`.
- **Het rapport noemt alleen ontbrekende bronnen waar ook echt een check op leunt**
  (blok A-review van de schrapronde, BO-64). De regel *Niet aangeleverd of leeg: … De
  checks die deze bronnen nodig hebben zijn overgeslagen* somde elke rol op die niet
  geladen was, ook `bgt_putdeksel` (waarvan EXT-005 en EXT-006 de enige lezers waren) en
  `nwb_wegvak` (dat er nooit een had). Op de De Wolden-configuratie beweerde het rapport
  daardoor dat er checks waren overgeslagen die niet meer bestaan. Welke bronnen een check
  nodig heeft volgt nu uit de checks zelf (`checks/extern.bronrollen_met_check()`), zodat
  de regel niet opnieuw kan gaan liegen als er een check bij komt of afvalt. De lagen zelf
  worden onveranderd geladen en op dekking getoetst, en de terugkoppeling van `toets` op
  de opdrachtregel somt nog steeds elke ontbrekende bron op.
- **Leidingeinden op een hulpstuk krijgen hun knoop terug** (issue #60). De BrutIS-export
  koppelt elk leidingeinde dat op een hulpstuk uitkomt aan `<hulpstuk>_put`, een URI die
  nergens bestaat, waardoor de engine bij alle T-stukken nul leidingen zag. De lader
  herleidt zo'n doel nu op naamstam naar het hulpstuk -- alleen als geen enkel doel een
  bekende orientatie is én de stam een knoop met een `Hulpstukorientatie` is -- telt het
  in `GwswDataset.koppelingsherstel` en meldt het als datasetsignaal
  `SIG-hulpstukkoppeling` (W, systemisch, zonder object), met een regel in de
  omvangsectie van het rapport. Stil repareren zou de aanlevering uit beeld halen.
  Gemeten op De Wolden en Hoogeveen: 3024 koppelingen naar 1122 hulpstukken hersteld,
  strengeinden zonder knoop 3024 → 0 over 2165 strengen. Geen enkele bestaande check
  verschuift erdoor: een hulpstuk is geen netwerkknoop, dus de herstelde einden komen
  niet in `verbonden_knopen` terecht. Zie BO-46.

- **BGT-lagen worden op de actuele objectversie gefilterd** (issue #58). Elke ingelezen
  BGT-laag houdt alleen de rijen met `eind_registratie` én `termination_date` leeg
  over; verlopen versies telden tot nu toe in elke ruimtelijke toets mee (op De Wolden
  97.148 waterdelen waarvan 44.601 actueel). Het filter werkt alleen op lagen die de
  historievelden dragen en meldt per laag hoeveel rijen vervielen onder *Externe
  bronnen* in het rapport. Gemeten op De Wolden: `bgt_water` 97.148 → 44.601 features,
  `bgt_pand` 133.279 → 81.661, `bgt_bouwwerk` 39.789 → 19.045. Per check zakt EXT-001
  van 493 naar 455 meldingen en zakken EXT-002 en EXT-003 van 859 naar 770. EXT-007
  stíjgt van 58 naar 71: 13 lozingspunten liggen bij water dat in de BGT geen actuele
  versie meer heeft. Die stijging is terecht -- het zijn kandidaten voor "water gedempt,
  lozingspunt niet meegemuteerd", geen fout in het filter. Zie BO-43.
- **EXT-002 en EXT-003 melden een doorkruising, geen nabijheid** (issue #59). Een
  vrijvervalstreng meldt alleen als zij het BGT-waterdeel echt doorkruist: erin door
  de ene oever, eruit door de andere, zonder erin te eindigen (`e = 0`, `k >= 2`,
  geen drempel). Een streng die binnen de zoekstraal ligt maar het water niet snijdt,
  of erin eindigt (lozingspunt), is geen bevinding meer; de toelichting telt die
  gevallen. Elke doorkruising per streng telt, de stop na het eerste waterdeel is
  vervallen. Op De Wolden zakt EXT-003 van 859 meldingen op 859 strengen (638
  waterdelen) naar 319 doorkruisingen op 281 strengen (302 unieke waterdelen); 362
  paren raken het waterdeel niet en 243 eindigen erin. Van die daling komen 89
  meldingen (859 → 770) uit het actualiteitsfilter van #58 en de rest uit de nieuwe
  regel. Dat zijn er meer dan de 234 handmatig gevalideerde doorkruisingen uit BO-43;
  de herbeoordeling staat in issue #59 en de meetuitkomst in BO-43. EXT-002 draagt
  voortaan het doorkruiste waterdeel als tweede object (`Object2`), zodat twee
  doorkruisingen van één streng een eigen, stabiele melding-ID houden. **De
  melding-ID's van EXT-002 verschuiven eenmalig**: de ID hangt mede aan
  `object2_uri`, dat EXT-002 nu vult; `vergelijk` leest de oude EXT-002-meldingen
  daardoor één keer als opgelost én nieuw. `schema_versie` blijft 1.0.
  `ext_watergang_buffer_m` is voortaan alleen de zoekstraal. Zie BO-43.

### Verwijderd

- **RVZ-003 vervalt: opgegaan in RVZ-002** (issue #87, BO-78). De aparte check op de
  ontbrekende `Drempelbreedte` had dezelfde populatie, ernst, dimensie en herstelhandeling
  als RVZ-002 (`Drempelniveau`) en meldde op De Wolden exact dezelfde 245 putten. RVZ-002
  noemt nu beide maten in één melding; twee ID's leverden alleen een dubbeltelling (490 voor
  245 putten). Het ID RVZ-003 wordt niet hergebruikt en staat in de tabel Vervallen checks
  van het register.

- **NET-003, TOP-020 en HGT-005 vervallen: opgegaan in NET-009** (issue #80, BO-76). De
  drie losse richtingssignalen -- een stijgende BOB (NET-003), een omgekeerd getekende lijn
  (TOP-020) en licht tegenverhang (HGT-005) -- zijn deelgevallen van de integrale
  richtingscheck NET-009 en verdwijnen als aparte checks. Gemeten op De Wolden staan alle
  3.651 NET-003- en 1.284 van de 1.285 HGT-005-objecten óók in NET-009, dus er gaat geen
  signaal verloren. De ID's worden niet hergebruikt en staan in de tabel Vervallen checks
  van het register.

- **EXT-002 vervalt: de kale watergangkruising draagt geen handelingsperspectief**
  (issue #83, BO-66). De check meldde elke vrijvervalstreng die een BGT-waterdeel écht
  doorkruist, zonder te vragen of dat een gebrek is. Dat is het niet -- een kruising
  gebeurt overal en er valt niets aan te herstellen. Het gebrek is dat zo'n kruising niet
  als zinker geregistreerd staat, en dat meldt EXT-003, die ongewijzigd blijft en nu de
  enige watergangmelding is. Op De Wolden en Hoogeveen gaven de twee exact dezelfde
  uitslag (281 van 281 strengen, 319 doorkruisingen; audit 27-08), want de export bevat
  geen enkele als zinker geregistreerde streng: de 319 EXT-002-waarschuwingen verdwijnen
  en EXT-003 blijft op 319. Het register zet EXT-002 in de tabel *Vervallen checks* (niet
  *Geschrapte checks*: de nulmeting dekt hem niet, dus ook geen sentinel in
  `dekking.toml`); het ID wordt niet hergebruikt. De regel "Waterschapsdata is niet
  aangeleverd; alleen de BGT-waterdelen zijn gebruikt" verhuist mee naar de toelichting van
  EXT-003, zodat het rapport blijft zeggen op welke waterbron getoetst is. Gevolg voor de
  GeoPackage: de watervlakken in de laag `vlakken` komen nu uitsluitend van EXT-003, dat
  zijn doorkruiste waterdeel zelf registreert -- `check_ids` leest daar voortaan altijd
  `EXT-003`, de structuur van de laag verandert niet. Wat wél vervalt is het vlak dat
  alleen EXT-002 aanwees (de treffer die #67 hem gaf, zie hierboven onder Gewijzigd): een
  doorkruising door een geregistreerde zinker is geen bevinding meer en krijgt dus ook geen
  vlak. Op De Wolden en Hoogeveen kost dat nul vlakken, want er is geen enkele zinker.
- **BTR-002, BTR-005, EXT-005 en EXT-006 vervallen voor nu** (issue #95, BO-62 t/m BO-65).
  Alle vier kunnen op deze aanlevering structureel geen uitslag geven, en de bron die ze
  nodig hebben komt er niet. BTR-002 vraagt de inwinningswijze op de kritieke
  hoogtekenmerken (537 van de 46.880 BOB's dragen er een; de overwogen tussenstap op alleen
  de maaiveldhoogte is door de auteur afgewezen). BTR-005 vraagt inspectiegegevens én een
  risicowegingsbron, en geen van beide bestaat. EXT-005 en EXT-006 vragen een putdeksellaag:
  de BGT-laag `put` telt 843 objecten (595 van ProRail) tegenover ruim 23.000 GWSW-putten, en
  er komt geen gemeentelijke deksellaag. Er verdwijnt geen enkele melding -- alle vier stonden
  op nul -- wel vier "bekeken 0"-regels uit het rapport. Het register zet ze in de tabel
  *Vervallen checks* (niet *Geschrapte checks*: de nulmeting dekt ze niet, dus er is ook geen
  sentinel in `dekking.toml`); de ID's worden niet hergebruikt. "Voor nu" betekent dat het
  besluit aan de bron hangt: komt die er alsnog, dan keert de toets terug onder een nieuw ID.
  De sleutels `bgt_putdeksellagen` en `ext_putdeksel_afstand_m` blijven in de drie
  configbestanden staan met een regel dat geen check ze meer leest; de BGT-rol
  `bgt_putdeksel` wordt nog wel geladen en op dekking getoetst. De voorbeeldsleutel in de
  melding van de dekkingspoort noemt daarom `bgt_waterlagen` in plaats van
  `bgt_putdeksellagen`.
- **ATTR-008 geschrapt: de nulmeting toetst hetzelfde lengtebereik** (issue #90, BO-61). De
  check meldde een administratieve strenglengte buiten 1-75 m, en die twee grenzen zijn met
  issue #35 op het GWSW-datatype `Dt_LengteLeiding` gezet -- precies het bereik dat de
  SHACL-vorm `LengteLeiding_val` in alle drie de conformiteitsklassen toetst. Op De Wolden en
  Hoogeveen vielen alle 443 ATTR-008-objecten ook onder die vorm, die er zelfs 932 telt. De 443
  waarschuwingen verdwijnen uit de bevindingen; de gevallen blijven zichtbaar in het
  nulmetingblok van het rapport. Het register verhuist ATTR-008 naar de tabel *Geschrapte
  checks* mét sentinel in `dekking.toml` (dezelfde als die van ATTR-011), niet naar *Vervallen
  checks*; het ID wordt niet hergebruikt. ATTR-009 (geometrische lengte tegen administratieve
  lengte) blijft ongewijzigd. De drempels `minimale_strenglengte_m` en
  `maximale_strenglengte_m` blijven in de configuratie staan, maar geen check leest ze nog.
- **ADM-011 vervalt** (issue #81, BO-60). De check meldde een keten van loze leidingen die
  in de administratieve afvoerrichting nergens op het actieve riool aansluit als dode data,
  maar dat is juist de gewenste eindtoestand: buiten gebruik gesteld en netjes losgekoppeld.
  Er valt niets te herstellen. ADM-010 (F) blijft ongewijzigd -- dat is het echte gebrek,
  actief riool dat wél op een loze keten aansluit -- en de ketenbouw blijft, inclusief de
  telling per geval in zijn verantwoording ("… losgekoppeld (… strengen)"). Op De Wolden en
  Hoogeveen verdwijnen daarmee 16 waarschuwingen; de 38 ADM-010-fouten blijven staan. Het
  register zet ADM-011 in de tabel *Vervallen checks*; het ID wordt niet hergebruikt.
  ADM-011 kwam met #62 in deze zelfde nog niet uitgebrachte cyclus binnen (zie hierboven
  onder Toegevoegd) en heeft dus nooit in een uitgave gestaan.

## [0.3.0] - 2026-08-24

### Toegevoegd

- **Stelselvlakken als GeoPackage-laag** (issue #25). Een nieuwe featurelaag `stelsels`
  tekent per geregistreerd stelsel (de `hasPart`-boom uit #17) een MULTIPOLYGON: de
  buffer om zijn strengen, samengevoegd tot één vlak. De bufferafstand is de nieuwe
  drempel `stelselvlak_buffer_m` (10 m). Elke rij draagt het stelseltype,
  `bereikt_eindpunt` (of een streng een afvoer- of lozingseindpunt bereikt, uit #18),
  het aantal putten en strengen, de totale strenglengte en een popup. Alleen lokale
  stelsels (met alleen strengen) krijgen een vlak; de gemeentebrede `_geb_0`-buckets uit
  #17 (strengen én alle putten van een heel type, verspreid over de hele gemeente)
  zouden een uitgesmeerde vlek geven en worden overgeslagen. `gwsw_run` telt de
  geschreven stelsels in `n_stelsels`. De QGIS-stijl `stelsels.qml` toont standaard
  alleen de stelsels zonder afvoerroute; de rest zit in de laag maar staat uit.
- **Nulmetingovertredingen op een stelsel landen op de stelsellaag** (issue #25, na #17).
  Een SHACL-focusnode die een lokaal stelsel is (bv. `vw_geb_1`) kreeg tot nu toe geen
  object en kwam nergens op de kaart. De join koppelt zo'n overtreding nu aan het stelsel
  zelf, zodat ze via de laag `stelsels` zichtbaar wordt. Overtredingen op een `_geb_0`-
  bucket of op een `CfkTypes_typ`-klassenaam blijven objectloos (die krijgen geen vlak).
  Het rapport meldt de aantallen apart.

- **Richtingsdiagnose NET-009** (issue #18, fase 2). De nieuwe check **NET-009** (F,
  Consistentie) meldt per vrijvervalstreng waar de drie richtingssignalen elkaar
  tegenspreken: de administratieve van-naar-richting (de referentie), de tekenrichting
  van de lijn (als TOP-020) en de BOB-richting (als NET-003/HGT-005/006). De melding
  noemt alle drie de waarden, zodat de beheerder zelf ziet welke fout is; NET-003 en
  TOP-020 blijven bestaan als deelgeval. Een streng die vlak ligt (|verval| ≤ de
  drempel `tegenverhang_licht_m`) krijgt geen bevinding maar een expliciete "geen
  uitspraak", geteld in de toelichting; ook het aantal strengen waarvan de BOB als
  vulwaarde (rond 0 m NAP) wegviel staat daar.
- **Afvoerpad naar het benedenstroomse uitstroompunt** (issue #18, fase 1). De GeoPackage
  draagt op de lagen `putten` en `strengen` drie nieuwe kolommen: `afvoer_eindpunt` (het
  dichtstbijzijnde bereikte gemaal/overname- of lozingspunt, label of anders URI),
  `afvoer_meters` (padlengte langs de getekende lijnen) en `afvoer_stappen` (aantal
  strengen in het pad). De uitstroompunten komen uit de rollen `afvoer_eindpunt` en
  `lozings_eindpunt` samen; bij meerdere bereikbare punten wint het dichtstbijzijnde in
  stappen en bij gelijkspel de kleinste URI. Een streng zonder bruikbare lijngeometrie op
  het pad laat de meters leeg maar telt wel als stap. Dit is nog geen check.
- **Wandruwheid versus leidingmateriaal** (issue #38). De nieuwe check **ATTR-017** (W,
  Plausibiliteit) meldt een leiding waarvan de wandruwheid
  (`WandruwheidBinnenboven`/`-onder`, de k-Nikuradse waarde van de buiswand) niet bij het
  materiaal past. Elke leiding droeg deze kenmerken, maar geen enkele nulmeting toetst hun
  waarde. De aannemelijke band per materiaal komt uit Leidraad Riolering C2100 tabel B2.1 en
  staat in `plausibiliteit.toml`. Het GWSW-datatype is een geheel getal in mm en kan de
  kunststofwaarden (pvc en HPE 0,4 mm) niet uitdrukken, dus een export noteert de waarde soms
  in tienden van een mm; de schaal wordt daarom uit de data afgeleid (`wandruwheid_schalen`,
  de lezing met de minste afwijkingen) en in de toelichting benoemd, zodat een export in hele
  mm net zo goed getoetst wordt (BO-39). Polypropyleen en Asbestcement kennen geen
  C2100-waarde en blijven ongetoetst. Een eigen check-ID en geen hergebruik van ATTR-014, het
  door het issue aanbevolen maar inmiddels vergeven ID. Op De Wolden en Hoogeveen meldt hij de
  PE-leidingen die de betonwaarde dragen.

- **Vorm versus afmetingen voor putten** (issue #39). De nieuwe check **ATTR-016** (F,
  Consistentie) meldt een ronde put (`VormPut = Rond`) waarvan breedte en lengte
  verschillen -- een ronde put heeft een diameter. De export droeg 13.972 `VormPut`-kenmerken
  die het pakket nergens las; ATTR-016 is de tegenhanger van ATTR-004 (vorm versus afmetingen
  voor leidingen), met dezelfde tolerantie (`rondheid_tolerantie_mm`, standaard 0). Een eigen
  check-ID en geen uitbreiding van ATTR-004, want `vergelijk` zet meetmomenten op check-ID
  naast elkaar en dan mag de betekenis van een ID niet tussen twee metingen verschuiven; het
  door het issue aanbevolen ID (ATTR-015) was inmiddels vergeven. Op De Wolden meldt hij
  88 ronde putten.

- **Een ondergrens op de testdekking, en een vindbaar meetcommando** (issue #54). Beide
  poorten -- de CI (`.github/workflows/toets.yml`) en de uitgavepoort
  (`scripts/uitgave.py`) -- dwingen nu een dekking van minstens 95% af (`--cov-fail-under`,
  `DEKKINGSONDERGRENS`); de meting doe je met
  `uv run --with pytest-cov pytest --cov=nlriochecker`, nu vermeld in `CLAUDE.md` en
  `README.md` in plaats van alleen in de rondeverslagen. `pytest-cov` blijft bewust buiten
  de dev-groep en wordt per run met `--with` opgelost. Gemeten: 97% mét `data/`, 96% in de
  CI-conditie zonder -- beide ruim boven de grens (BO-38). Geen enkele bevinding verandert
  -- dit raakt de poort, niet de engine.

- **Begindatumdekking en een detector voor een vulwaardejaar** (issue #21). ATTR-007
  verantwoordt nu in zijn toelichting hoeveel strengen en putten geen begindatum dragen
  en dus niet getoetst zijn -- stilte las eerder als "alle aanlegdatums gecontroleerd".
  De nieuwe check **ATTR-015** (W, Compleetheid) meldt systemisch wanneer een enkel
  jaartal een onevenredig deel van de begindatums draagt, een signaal voor een vuljaar;
  de drempel (`begindatum_vulwaarde_aandeel`, standaard 20%) is een signaalwaarde en geen
  norm, en op De Wolden en Hoogeveen meldt hij niets. De bovengrens van ATTR-007 is
  instelbaar gemaakt (`begindatum_maximum`, standaard het huidige jaar) zodat een run
  reproduceerbaar vast te zetten is.

- **Vier wortelklassen een symbool, en een drifttest voor de lijnkant** (issue #55). De
  symbolentabel dekt nu ook de generieke wortelklassen: `Rioolput` (een cirkel in de
  puttenlaag) en `Rioolleiding`, `VrijvervalRioolleiding` en `Aansluitleiding` (het
  familiebeeld in de strengenlaag). Een export die generiek een wortel schrijft in plaats
  van een blad valt daarmee niet meer in het vangnet. De drifttest die de knoopklassen
  tegen de ontologie houdt meet nu ook de lijnkant (wortel `Leiding`, 23 nog ongedekte
  klassen) en bewaakt een tweede richting: een naam die inmiddels gedekt is of uit de
  klassenboom verdween moet van de lijst af. De Wolden en Hoogeveen verandert niet -- de
  vier wortels komen er nul keer voor.

- **Tel de klassen waar checks van afhangen, en waarschuw bij nul** (issue #22). De
  omvangsectie van het bevindingenrapport draagt nu een telling per rol waar de zwaarste
  checks op leunen (afvoereindpunt, lozingseindpunt, bergbezinkvoorziening,
  overstortdrempel, infiltratieleiding, mechanische leiding) en een aparte regel met de
  afvoereindpunten per klasse -- het criterium om het `Gemaal`/`Pompunit`-noodverband van
  NET-001 los te laten zodra `Overnamepunt` boven nul komt (BO-33). Staat een klasse of
  rol op nul terwijl een check erop leunt, dan komt er een systemische waarschuwing
  (ernst W, bron `dataset`, categorie `SIG`) in de meldingenstroom; systemisch, dus buiten
  `status` en `ergste_ernst` van de GeoPackage (BO-29). Het afvoereindpunt bewaakt per
  klasse, de andere rollen per rol -- een ongebruikte alternatieve schrijfwijze is geen
  gebrek. Zonder klassenhierarchie vervalt de bewaking, want dan herkent de lader geen
  klassen. De telling gaat over de volledige geanalyseerde export, niet over de kern van
  een studiegebied.

- **Een drifttest die een getal bindt** (issue #51). Geen van de vier bestaande drifttests bond
  een getal, terwijl elke onwaarheid uit de weekendrun van 2026-08-21 er een was. `tests/test_beweringen.py`
  bouwt de getalzinnen in de docstrings van `uitvoer/stijlen/symbolen.py` op uit de gemeten
  waarde (aantal knoop- en verbindingstypen, blad- en legendaregels) en eist dat ze letterlijk in
  de docstring staan; wijzigt de symbolentabel, dan valt de proza in plaats van stil te verouderen.
  Meteen betrapt: `bouw_qml` noemde 225 legendaregels voor de putten waar het er 220 zijn.

- **Vijf ontbrekende bewakingen plus een tegenstrijdige documentatieregel** (issue #52), stuk
  voor stuk hetzelfde patroon: iets wat waar hoort te zijn werd door niets afgedwongen, of een
  document zei iets anders dan de code deed.
  - De `[klassen]`-blokken van `checks.toml` en `configs/dewoldenhoogeveen.toml` worden nu
    gelijkgehouden door een drifttest, met een `BEWUSTE_KLASSEN_AFWIJKINGEN`-lijst (vandaag
    leeg) plus een omgekeerde test — hetzelfde patroon als de bestaande drempelbewaking uit #28.
  - De CI-poort kreeg een derde grens, `NLRIOCHECKER_MAX_MODULE_OVERGESLAGEN` (vandaag 1). Een
    `pytest.skip(allow_module_level=True)` telt in de bestaande grenzen als één overslag, hoeveel
    tests de module ook draagt; `conftest.py` onderscheidt nu modulewijde overslagen
    (`CollectReport`) van test-skips (`TestReport`), zodat een weggevallen fixturemap opvalt.
  - Het rapport van `toets` noemt nu de klassen die de nulmeting te globaal noemt maar die de
    typeringspoort niet naar objecten kon herleiden (`Niet beoordeeld: …`) — dezelfde mededeling
    die `analyseer` al gaf. `CheckRun` draagt daarvoor `niet_beoordeelde_klassen` als runmetadata,
    naast `meetbereik`; het is geen melding. Stilte over een niet-beoordeelde klasse las als
    "beoordeeld en niets gevonden".
  - `docs/json-schema.md` sprak zichzelf tegen over `schema_versie`: een puur optioneel, additief
    veld verhoogt het tweede nummer níét (afnemers pinnen op het hoofdnummer). `schema_versie`
    blijft `1.1`; een nieuwe drifttest bewaakt dat elk enveloppeveld in het document beschreven
    staat, niet alleen elk meldingveld.
  - Eén CLI-test draagt nu `--ontologie` en stelt vast dat de klassenhiërarchie werkelijk
    gebruikt is — de standaardweg van het gereedschap liep op CLI-niveau door geen enkele test.
- **ATTR-014 toetst de waardeproperty van elk kenmerk tegen de ontologie** (issue #37). Een
  kenmerk dat `hasValue` gebruikt waar de ontologie via een `owl:onProperty`/`allValuesFrom`-
  restrictie `hasReference` naar een collectie eist (of andersom) is een consistentiefout die
  de SHACL-nulmeting per constructie mist: een `allValuesFrom` over een afwezige property is
  vacuously true. De check is generiek over alle kenmerktypen en meldt per kenmerk één
  systemische bevinding over de hele export (op De Wolden: `WIBONThema`, dat 23.440× `hasValue`
  draagt in plaats van `hasReference`). De ontologische property komt uit `ontologie.verwachte_property`,
  bij het laden afgeleid tot `GwswDataset.kenmerk_property` — hetzelfde soort afgeleide als
  `subclasses`, geen tweede ontologiegraaf in het geheugen. `Finding` draagt nu een veld
  `systemisch` dat een check zelf kan zetten; de meldingenlaag OR't het met de bestaande
  populatieratio. Zie BO-37.
- **`ontologie.py` leest de gedeclareerde waardebereiken (facetten) uit de GWSW-ontologie**
  (issue #35). `facetbereik` lost de keten `Dt_X → equivalentClass → onDatatype +
  withRestrictions → min/maxInclusive` op, `datatype_van_kenmerk` de stap `Kenmerk →
  hasValue → allValuesFrom Dt_X`. Dit is de ontbrekende schakel waarmee een projectdrempel
  tegen de ontologie te houden is; de module leest alleen en raakt geen run. Dit is de
  onderzoeksstap met een poort: de gemeten tegenspraken (ATTR-008 `maximale_strenglengte_m`
  200 m vs ontologie 75 m — +431 op De Wolden; HGT-012 6,0 m vs 500–4000 mm — latent; PE
  `minimum_mm` 40 vs 63 mm) staan in een comment bij het issue.

### Gewijzigd

- **`bevindingen.json` wordt compact geschreven** (geen inspringing, geen spaties rond
  scheidingstekens). De structuur, veldvolgorde en sortering veranderen niet en het
  contract in `docs/json-schema.md` blijft `1.1`, maar de bytes van het bestand wijken
  bewust af van eerdere versies: een byte-diff tussen twee meetmomenten over deze grens
  heen vraagt eerst pretty-printen (`python -m json.tool`). Op De Wolden en Hoogeveen
  scheelt het circa een kwart in bestandsgrootte (149 MB naar 111 MB).
- **De rdflib-store is vervangen door eigen graafindexen uit de pyoxigraph-stream**
  (issue #26). `GwswDataset.graph` is voortaan een `graaf.GraafIndex`: twee dicts
  (s→p→objecten, p→o→subjecten), in stream-volgorde gevuld uit de pyoxigraph-parse en
  met rdflib-termen als munteenheid, die precies de door de checks gebruikte
  leesbewerkingen aanbiedt (`objects`, `subjects`, `value`, `subject_objects`,
  membership, `len`) met dezelfde antwoorden en volgorde als rdflib's `Memory`-store
  (`tests/test_graaf.py` toetst elk ervan tegen het rdflib-antwoord). De cache picklet
  de index (teruglezen circa 6 s in plaats van circa 30 s; gemeten tegen warm herbouwen
  uit de stream, dat circa 20 s kost), `graaf.py` telt mee in de cachesleutel, en de
  overslaglijst van de structurenpickle volgt nu de niet-init-velden van de dataclass.
  De `onderdeel_*`-lezers vinden een BNode-subject voortaan ook (voorheen verarmde de
  vaste `URIRef`-omweg zo'n onderdeel tot een lege lezing). De uitvoer verandert niet
  (vergelijker: gelijk op alle vier de uitvoervormen, koud én warm); een koude De
  Wolden en Hoogeveen-run daalt van circa 195 s naar circa 116 s, een warme van circa
  129 s naar circa 96 s, en het piekgeheugen van circa 4,0 GB naar circa 2,2 GB.
- **Snellere topologie- en netwerkchecks door ruimtelijke caches en memoisatie**. De
  puttenzoek (`nearest_node`) en de burenzoek van de strengen gebruiken
  `STRtree.query(..., predicate="dwithin")` in plaats van per aanroep een gebufferde
  geometrie; de strenguiteinden worden één keer bepaald bij het bouwen van de
  topologie-index en de snapping streng-einde→put staat als gedeelde tabel in de
  contextcache, zodat TOP-001/002/003/021 dezelfde afbeelding delen;
  `resolve_network_node` is gememoiseerd op de dataset en NET-007 loopt de strengen
  één keer langs een componenten-dict in plaats van per component over alle strengen.
  De uitvoer verandert niet (vergelijker: gelijk op alle vier de uitvoervormen); een
  warme De Wolden en Hoogeveen-run daalt van circa 163 s naar circa 129 s.
- **`uitvoer/__init__.py` is een lege naamruimte; de orkestratie woont in
  `uitvoer/schrijver.py`**. `schrijf_uitvoer`, `schrijf_uitvoer_gebieden` en de
  `Uitvoer`-dataclasses verhuisden ongewijzigd; importeer ze voortaan uit
  `nlriochecker.uitvoer.schrijver`. Een import van een lichte deelmodule
  (`uitvoer.identiteit`) trekt daardoor niet langer de hele uitvoerstack binnen, en
  de vier functie-lokale imports die de oude importkring omzeilden staan weer
  bovenaan hun module. Twee nieuwe drifttests borgen via een expliciete
  veld→kolom-afbeelding dat elk `Melding`-veld in `bevindingen.csv` én in de
  GeoPackage-meldingentabel verantwoord is (met `object2_label` als benoemde
  weglating: de tabel heeft er nooit een kolom voor gehad). De uitvoer verandert
  niet.
- **De checks lezen de graaf via een smalle onderdelen-API op `GwswDataset`**. Drie
  nieuwe methoden -- `onderdelen` (de directe `hasPart`-delen, optioneel gefilterd op een
  wortelklasse), `onderdeel_label` en `onderdeel_aspecten` -- vervangen de losse
  `parts_of`/`URIRef`/`graph.value`/`_read_aspects`-aanroepen in de ADM- en RVZ-checks,
  en de zes losse `resolve_network_node`-paren (topologie, netwerk, graafbouw, omvang,
  GeoPackage) gaan door het bestaande `verbanden.verbonden_knopen`. De graaftoegang
  blijft zo binnen `dataset.py`; de uitvoer verandert niet.
- **`CheckRun.config` is verplicht; de uitvoerlaag leest geen config meer stil bij**.
  Negen plekken in de uitvoerlaag vielen bij een ontbrekende `run.config` terug op
  `load_check_config()`, waardoor een run met projectconfig met de standaarddrempels
  kon rapporteren. Het veld is nu verplicht en elke schrijver gebruikt `run.config`
  rechtstreeks; de uitkomst van een normale run verandert niet.
- **De schrijvers lezen de runcontext; de afvoerpadberekening woont in
  `checks/verbanden.py`**. `CheckRun` draagt nu verplicht `context`: exact de
  `CheckContext` waarmee de checks draaiden. De GeoPackage- en synthese-schrijvers
  bouwden er elk een eigen (met lege cache), waardoor de vrijvervalgraaf en de
  afvoerpaden voor de kaart opnieuw gerekend werden en bij een afwijkende opbouw van
  de checkuitslag hadden kunnen afwijken; ze lezen nu de gecachte uitkomst van de
  NET-checks. `Afvoer`, `afvoerpad_van_streng` en `afvoerpaden` zijn daarvoor (met de
  graafbouw) van `checks/netwerk.py` naar `checks/verbanden.py` verhuisd, en
  `CheckOutcome` draagt `id_sleutels` en `volledig_bereik` zodat de uitvoerlaag de
  check-registry niet meer raadpleegt. De uitvoer verandert niet.
- **TTL-parse via de Rust-parser van `pyoxigraph`** (issue #26, BO-41). Het OroX-TTL wordt
  ingelezen met `pyoxigraph.parse` en daarna overgezet in een gewone `rdflib.Graph`; de checks,
  de cache en de rest van de lader blijven ongewijzigd. `pyoxigraph` is een nieuwe **harde**
  afhankelijkheid (Apache-2.0, EUPL-verenigbaar). De koude laadtijd van De Wolden en Hoogeveen
  daalt van circa 157 s naar circa 84 s (piekgeheugen 3207 -> 2796 MB); de parse-stap zelf gaat
  van circa 150 s naar circa 5 s (de rest is het vullen van rdflib's store, dezelfde kost die de
  oude parse ook al betaalde). De warme laadtijd (circa 34 s) verandert niet: die leest de
  gepicklede graaf terug en parseert niet. De uitkomst blijft aantoonbaar identiek:
  `bevindingen.json` is vóór en na byte voor byte gelijk. Bijkomend opgeruimd: het tellen van de niet-UTF-8-bytes in `_decode` gaat niet
  meer via een Python-lus over alle 112 MB maar via `bytes.translate` in C. De cachesleutel
  bevat nu ook `pyoxigraph.__version__`.
- **`plausibiliteit.toml` onderbouwd met bronnen, en de minimale diameter per stelseltype**
  (issue #20). Elke regel in de plausibiliteitstabellen draagt nu een verplicht `bron`-veld:
  een van de vier harde projectankers (`ontologie`, `checkregister`, `RIONED Kennisbank`,
  `Leidraad C2100`) of, eerlijk gemarkeerd, `ervaringsregel` -- met de specifieke bron in de
  toelichting. `tests/test_plausibiliteit_herkomst.py` dwingt dat af, zodat een nieuwe tabel
  of regel zonder herkomst opvalt. **Breaking voor een eigen `plausibiliteit`-bestand:** een
  regel zonder `bron` wordt geweigerd (`extra="forbid"`).
  - *ATTR-002 (diameter onder de ondergrens)* leest de ondergrens niet meer als één drempel
    `minimale_diameter_mm` (200 mm voor alles), maar per stelseltype uit de nieuwe tabel
    `[[minimale_diameter]]`: gemengd 250 en hemelwater 250 (RIONED Kennisbank; 300 mm is
    gangbaar), vuilwater 200 (checkregister), en een vangnet `overig` 200 voor infiltratie,
    drainage en onbekend. Het stelseltype volgt uit de eigen GWSW-klasse van de streng
    (`[klassen.stelseltypen]`). Op De Wolden en Hoogeveen stijgt ATTR-002 van 1047 naar 2289
    bevindingen: de +1242 zijn gemengd- en hemelwaterstrengen met Ø200-249, die onder de
    RIONED-ondergrens van 250 mm vallen (Ø200 is een gangbare maat, dus dit is een grote maar
    verklaarde stijging). `drempels.minimale_diameter_mm` is vervallen uit `checkconfig.py`,
    `checks.toml` en `configs/dewoldenhoogeveen.toml`.
  - *ATTR-001 (diameter versus materiaal)* neemt vier geciteerde bereikcorrecties over uit het
    bronnenonderzoek: GewapendBeton min 400->300 (VPB/De Hamer/LBN), Polypropyleen min
    100->80 (VPB/Pipelife), Gres max 1000->1400 (EN 295-1) en Asbestcement max 1000->1800
    (Wagenmaker 1968). Beton blijft 200-3000: de VPB geeft 250-1500, maar riolen tot 3000 mm
    bestaan aantoonbaar. Op De Wolden en Hoogeveen daalt ATTR-001 van 19 naar 13.
  - *ATTR-003 (materiaal versus begindatum)* volgt het auteursbesluit over de jaartallen: PVC
    1955->1958 (Wavin, NEN 7045:1977), Asbestcement-begin 1930->1967 (Wagenmaker; einde 1993
    blijft, Productenbesluit asbest). De ongedekte tijdvakken van PE, Polypropyleen,
    GewapendBeton en Metselwerk zijn geschrapt; ATTR-003 toetst die materialen daardoor niet
    meer op begindatum en meldt dat in haar toelichting. Op De Wolden en Hoogeveen stijgt
    ATTR-003 van 27 naar 40: de +13 zijn PVC-strengen met een begindatum in 1955-1957 (het gat
    dat de nieuwe drempel opent); de geschrapte materialen kennen in deze dataset geen
    strengen vóór hun oude grens, dus daar verandert niets.
  - *Bewust niet gedaan (deel 3 van het issue):* de ~15 ontbrekende GWSW-materiaalklassen
    (HDPE, Kunststof, Polymeerbeton, ...) zijn niet als lege `ervaringsregel`-regels
    toegevoegd. Sinds #19 meldt ATTR-001 het gat al expliciet ("N strengen met een materiaal
    zonder regel"); lege regels zouden dat gerapporteerde gat juist maskeren. In De Wolden en
    Hoogeveen komt geen van die klassen voor.

- **RVZ-006 eist nu ook een afvoereindpunt** (issue #23). De check
  `GemengdDeelstelselZonderOverstort` meldde een gemengd deelstelsel zonder externe overstort
  of BBB; hij meldt nu ook een gemengd deelstelsel zonder afvoereindpunt (gemaal, pompunit of
  overnamepunt), want het vuilwater moet in de gewone toestand ergens heen. De eindpuntklassen
  komen uit `klassen.afvoer_eindpunt`, dezelfde die NET-001 gebruikt; de deelstelsels uit
  `netwerkdelen()`, gedeeld met NET-001/002. De meldingtekst onderscheidt welke van de twee
  eisen faalt (geen overstort, geen afvoereindpunt, of geen van beide). De ernst gaat daarbij
  van W naar **F**: een gemengd stelsel dat zijn vuilwater nergens kwijt kan, is een fout, geen
  waarschuwing (auteursbesluit, wijkt af van de oorspronkelijke issue-tekst). De dimensie blijft
  Plausibiliteit. Op De Wolden en Hoogeveen gaat RVZ-006 van 87 naar 98 bevindingen: 11 gemengde
  deelstelsels dragen wel een overstort maar geen afvoereindpunt.

- **`AHN6` in plaats van `AHN5` als vooruitloop-inwinningswaarde** (issue #47, vraag 1). De
  lijst `uit_hoogtemodel` in `checks.toml` en `configs/dewoldenhoogeveen.toml` noemt nu `AHN6`,
  de inwinningsbron die het project werkelijk gebruikt; `AHN5` was noch de gebruikte bron noch
  een bestaande GWSW-waarde. `AHN6` bestaat evenmin in GWSW 1.6 (`WijzeVanInwinningColl` stopt
  bij `AHN4`) en blijft daarom als bewuste afwijking op de vocabulaire-uitzonderingslijst staan
  (BO-40).

- **"aanlegjaar" heet nu overal "begindatum"** (issue #21; breaking change voor
  projectconfiguraties). De GWSW-term is leidend, ook in de identifiers: de drempelsleutel
  `aanlegjaar_minimum` heet nu `begindatum_minimum`, de plausibiliteitstabel
  `[[materiaal_aanlegjaar]]` heet `[[materiaal_begindatum]]`, `Conduit.aanlegjaar` heet
  `Conduit.begindatum_jaar` en de bevindingsdetail `aanlegjaar` heet `begindatum_jaar`. Een
  oude projectconfiguratie met de oude sleutels faalt luid (`extra="forbid"`). De check-ID's
  ATTR-003 en ATTR-007 en hun ernst blijven; alleen hun titel verandert.

- **De dekkingclaim van ADM-004 is beperkt tot de CFK waar hij op rust** (issue #7). De
  put-vormen `MateriaalPut` en `Maaiveldschematisering` (hasAspect exact=1) leveren op De
  Wolden uitsluitend in Hyd meldingen op (4142 resp. 20756), nul in MdsPlan en MdsProj op
  hetzelfde RDF-bestand; het register schreef die twee attributen ten onrechte aan Mds toe.
  Register, de sentineltabel `dekking.toml` en de gegenereerde `docs/dekkingsmatrix.md`
  zijn bijgetrokken. De tweede claim uit #7 (ADM-001, de put-strengkoppeling) raakt de
  onderbouwing van de harde CFK-eis (BO-7) en is bewust ongemoeid gelaten in afwachting
  van akkoord.
- **De De Wolden-dataset heet overal "De Wolden en Hoogeveen"**. De zware integratietest
  laadt de volledige OroX-export die niet alleen De Wolden maar ook Hoogeveen beslaat; de
  oude naam suggereerde ten onrechte één gemeente. Het aangeleverde OroX-bestand heet nu
  `dewoldenhoogeveen_orox.ttl`, en identifiers, testnamen en proza volgen. De geleverde
  SHACL-nulmeting blijft `dewolden_orox.ttl` melden: dat is de naam waarmee die validatie
  destijds draaide, en aangeleverde invoer wijzigen we niet.
- **Twee klassenlijsten in `checks.toml` doen weer wat ze zeggen** (issue #56). `[klassen]
  mechanisch` noemt nu de twee ontologische wortels `MechanischeRioolleiding` en
  `MechanischeTransportleiding` in plaats van de drie losse bladen; dat sluit het gat met de
  symbolentabel, die `Leidingsegment` en `Luchtpersleiding` al als mechanische streepjeslijn
  tekende terwijl de kaartstatus ze als getoetste vrijvervalstreng kleurde. De nieuwe set
  `MECHANISCHE_LIJNEN` in `symbolen.py` maakt de mechanische lijnfamilie expliciet, en een
  drifttest houdt hem naast de afsluiting van `[klassen] mechanisch`. Daarnaast is de losse
  klasse `Uitlaat` uit `lozings_eindpunt` geschrapt: die hangt onder
  `RepresentatieFysiekObject` en belandt in geen selectiebak, dus de regel voegde niets toe
  (een stille nul). Op De Wolden verandert geen enkele bevinding — `mechanisch` stuurt alleen
  de kaartkleur, niet de checkselectie, en de dataset telt nul `Uitlaat`, `Leidingsegment`,
  `Luchtpersleiding` of `Spoelleiding`.
- **Een lege rollijst zet een externe-bron-rol altijd uit, ook bij een eenlaagsbestand**
  (issue #53). `_lees_rol` koos de terugval `beschikbaar[:1]` voorheen alsnog wanneer een
  BGT-rol met `bgt_...lagen = []` naar een bestand met precies een laag wees, waardoor een
  uitgezette rol tóch gelezen werd en de dekkingspoort hem noemde. De terugval hoort alleen
  bij de eenlaagsbronnen `bag_pand`/`nwb_wegvak` (nieuwe parameter `enige_laag`); voor de
  BGT-rollen is een lege lijst nu onvoorwaardelijk "niet gelezen". Op De Wolden verandert
  geen uitkomst of aantal bevindingen (`BGT.gpkg` heeft 48 lagen), alleen de meldingstekst
  voor die uitgezette rollen wordt korter ("geen laagnaam geconfigureerd" zonder het
  misleidende laagaantal).
- **ATTR-001, ATTR-004 en ATTR-012 splitsen de ongetoetste strengen naar reden** (issue
  #19). Het ene getal "materiaal zonder regel (of geen materiaal)" viel twee verschillende
  problemen samen: een gat in de aanlevering (geen attribuut) en een gat in
  `plausibiliteit.toml` (geen regel). De helper `_ongetoetst` telt ze nu apart, en ATTR-001
  meldt daarnaast de strengen zonder bruikbare profielmaat (met daarbinnen de als 0
  geregistreerde maten) plus een tabel met per materiaal het aantal, het aantal buiten
  bereik en de feitelijke min/max-diameter. Het aantal bevindingen verandert niet; alleen de
  toelichting. Op De Wolden blijft ATTR-001 op 19 bevindingen en is de emmer "materiaal
  zonder diameterregel" nul.

- **ATTR-008 toetst de strenglengte tegen de GWSW-ontologiegrens van 75 m** (issue #35).
  De bovengrens `maximale_strenglengte_m` gaat van 200 m naar 75 m, de waarde die het
  datatype `Dt_LengteLeiding` declareert (`owl:withRestrictions` 1–75 m). GWSW is leidend:
  de oude 200 m keurde strengen goed die de SHACL-nulmeting in hetzelfde rapport afkeurt.
  Op De Wolden loopt ATTR-008 daarmee van 12 naar 443 bevindingen (+431 vrijvervalstrengen
  tussen 75 en 200 m). De ondergrens 1 m viel al samen met de ontologie en blijft. De
  waarde staat in `checks.toml`, `checkconfig.py` en `configs/dewoldenhoogeveen.toml`, met
  de ontologie als bronregel.

- **HGT-012 toetst de putdiepte tegen het ontologiebereik 0,5–4,0 m** (issue #35). Het
  datatype `Dt_HoogtePut` declareert 500–4000 mm. `maximale_putdiepte_m` gaat van 6,0 m
  naar 4,0 m, en er komt een `minimale_putdiepte_m = 0,5` bij: de check toetste voorheen
  alleen op `> 0` in plaats van de gedeclareerde ondergrens. De melding is nu symmetrisch
  (`ligt onder/boven de grens van X m`), net als ATTR-008; een negatieve diepte valt
  vanzelf onder de ondergrens. Op De Wolden verandert er niets — de export draagt nul
  `HoogtePut` — maar de tegenspraak met de nulmeting is weg. De PE-40-regel
  (`plausibiliteit.toml`, #20) blijft over en hoort bij dat issue.

### Gewijzigd

- **HGT-007 toetst het minimale verhang met een diameterstaffel in plaats van één
  vlakke drempel** (issue #29). De oude drempel `minimaal_verhang_promille = 1.0`
  (1:1000) nam precies het afschot dat volgens de RIONED Kennisbank Stedelijk Water
  "in vuilwaterstelsels vrijwel niet voorkomt". Het minimale afschot hangt van de
  diameter af: kleine leidingen moeten steiler liggen. De staffel staat nu als
  `[[verhang_staffel]]` in `checks.toml` (1:250 ≤250 mm, 1:500 ≤350 mm, 1:750 ≤650 mm,
  1:1000 daarboven) met de citaten als commentaar; `minimaal_verhang_promille` vervalt.
  Op De Wolden loopt HGT-007 daarmee van 1559 naar 4757 bevindingen, vooral bij de
  kleine leidingen die 1:1000 te slap toetste. De `notes()` telt nu ook de strengen die
  niet getoetst konden worden (buiten de rol vuilwater, zonder BOB — met het aandeel dat
  de vulwaardenregel wegneemt — of zonder diameter). De C2100-lengtecorrectie is
  onderzocht en bewust niet ingebouwd: op De Wolden verschuift ze de uitkomst ~1,7%.

- **NET-007 meldt niet langer elk infiltratieriool** (issue #42). De check bouwde zijn
  drempelverzameling alleen uit `Overstortdrempel`-objecten; die klasse heeft op de De
  Wolden-export nul instanties en in de ontologie geen subklassen, dus de verzameling
  bleef leeg en elk van de 340 infiltratieriolen werd onvoorwaardelijk gemeld. NET-007
  herkent nu ook de overstortput zelf als overstortvoorziening -- dezelfde vormen die
  `checks/randvoorzieningen.py` al leest (BO-34, open punt 6) -- en wordt daarmee weer
  onderscheidend.

- **De CI-job heeft een tijdslimiet en legt vast waarom er geen padfilter is.**
  `.github/workflows/toets.yml` draagt `timeout-minutes: 15`; zonder grens mag een
  vastgelopen stap de volle zes uur van de runner opmaken, terwijl de run zelf circa
  veertig seconden duurt. Daarnaast staat er nu bij dat een `paths-ignore` op Markdown
  hier fout zou zijn -- `docs/json-schema.md`, `CLAUDE.md` en het checkregister zijn
  invoer van de suite -- en wat de triggerfilters wel en niet uitsluiten. Aan wat CI
  toetst verandert niets.

- **De dekkingspoort noemt de derde uitweg** (issue #4). Faalt een bron op dekking, dan
  wees de melding alleen naar een ruimer extract of een hogere
  `[bronnen] dekking_tolerantie_m`. Die tolerantie geldt voor alle lagen tegelijk, dus wie
  hem oprekte om één laag door te laten hief de poort voor élke bron op -- precies het
  stille falen waar BO-19 tegen bouwt. De melding zegt dat nu, en noemt de uitweg die
  alleen in de README stond: een bron die niet te klein maar ongeschikt is zet je uit
  (`bgt_putdeksellagen = []`), waarna de bijbehorende checks overslaan met uitleg in het
  rapport. De poort blokkeert dezelfde gevallen als voorheen.

- **ATTR-010 noemt wat onwaarschijnlijk is in plaats van wat toegestaan is** (issue #43).
  `[[leiding_put_materiaal]]` in `plausibiliteit.toml` draagt het veld
  `onwaarschijnlijke_putmaterialen` in plaats van `verwachte_putmaterialen`. Een lijst met
  verwachte materialen maakte van elk lid van `MateriaalPutColl` dat niemand had ingetypt
  een bevinding: 26 van de 30 leden, waaronder `Gres`, `Klei`, `Staal` en `Asbestcement`.
  Een gemeente die netjes volgens de GWSW-domeinlijst exporteerde kreeg daar een valse
  waarschuwing op. Elke regel houdt precies de uitsluitingen die hij had: `GewapendBeton` en
  `Metselwerk` verbieden alle acht kunststoffen uit `MateriaalPutColl`, `Beton` zes daarvan
  (`PVC` en `PE` stonden op zijn oude lijst en blijven toegestaan). Op De Wolden verandert
  er niets: ATTR-010 stond en staat op 0 bevindingen over dezelfde 11.969 vergeleken
  strengen. Zie BO-36; wie een eigen `plausibiliteit.toml` meegeeft moet het veld hernoemen.

### Toegevoegd

- **ATTR-010 meldt wat hij niet vergeleken heeft.** De check heeft een `notes()` gekregen:
  `examined` telt alle vrijvervalstrengen, maar vergeleken worden alleen de materialen die
  in `[[leiding_put_materiaal]]` staan. Op De Wolden zijn dat er 5634 van de 17603 niet
  (PVC 5376, zonder materiaal 227, Gres 31). Zonder die regel las "0 bevindingen op 17603
  bekeken objecten" als een schone rekening voor het hele stelsel.

- **`toets` weigert een run zonder `--ontologie`** (issue #33). Zonder
  klassenhierarchie typeert de OroX-export niets op wortelniveau en leveren `putten()`
  en `leidingen()` een lege verzameling; de checks draaien dan over een onvolledige
  selectie en hun uitkomst draagt geen oordeel, terwijl het rapport dat nergens zei.
  Hoe onvolledig verschilt per check: gemeten op De Wolden zien 62 van de 89 checks er
  **nul** -- die selecteren op `putten()`, `leidingen()` of
  `vrijvervalrioolleidingen()` -- en achttien zien er 1.874 van de 23.485, omdat
  `netwerkknopen` naast de wortels ook klassen opsomt die de export wel rechtstreeks
  typeert. 1.874 is dus een bovengrens en geen gemiddelde. Dat is nu een harde fout
  met een melding die zegt wat er ontbreekt en wat je eraan doet, en hij valt vóór het
  laden, dus in seconden. Wie zo'n run bewust wil, geeft `--geen-ontologie` mee; dan
  draagt het rapport het voorbehoud in de kop, staat de regel van de eigen checks in de
  managementsamenvatting op `–` in plaats van op een vinkje of kruisje (met de
  tellingen in de toelichting), en is `structural_diff` juist dan gevuld -- op De
  Wolden 23.485 knooppunten en 23.440 strengen die alleen op geometrie herkend zijn.
  Bestaande aanroepen zonder ontologie moeten de vlag krijgen.
- **`structural_diff` wordt nu altijd berekend**, ook zonder klassenhierarchie; hij
  werd juist dan overgeslagen, terwijl hij daar zijn diagnose voor doet. Dat is een
  uitvoerverandering voor datasets waarin `Knooppunt` noch `Verbinding` subklassen
  heeft: hun rapport krijgt er de regel "De GWSW-definitie en de herkenning op
  geometrie wijken af (…)" bij. De uitspraak was altijd al waar, alleen werd zij niet
  geteld. Van de 114 TTL-fixtures gaat het om 25 stuks; op De Wolden mét ontologie
  verandert er niets, want daar blijft de vergelijking leeg zoals voorheen.
- **De runbrede voorbehouden komen samen in `uitvoer/voorbehoud.py`.** De markering
  boven een rapport werd door precies een bron gevoed; een deelset-run zonder ontologie
  draagt er twee, en met een enkel slot zou er een stilzwijgend verdwijnen. Markdown,
  de kolom `markering` in `gwsw_run` en het gelijknamige optionele veld in de
  JSON-envelop dragen nu dezelfde samengestelde tekst. De CSV bewust niet: een
  voorbehoud hoort bij de run en niet bij elke melding. `schema_versie` blijft `1.1`;
  het veld is optioneel en ontbreekt als er niets voor te behouden valt.

### Gerepareerd

- **`overzicht_checks` in de GeoPackage draagt nu ook de nulmeting** (issue #24). De
  tabel presenteert zich als het overzicht van wat er gemeten is, maar haar rijen kwamen
  uitsluitend uit `run.outcomes` met `bron` hardgecodeerd op `"register"`. SHACL-vormen
  zijn geen `CheckOutcome`, dus wie de tabel als checklijst las, miste de tweede bron --
  op De Wolden 105.963 meldingen. Er komt nu een rij per SHACL-vorm bij, met
  `bron = "nulmeting"`, het aantal overtredingen, de zwaarste ernst van die vorm en de
  nieuwe kolom `cfk` met de conformiteitsklassen die hem stellen. Wat alleen een
  `CheckOutcome` weet -- de omschrijving, `bekeken`, `percentage_populatie`, `skelet` --
  blijft op die rijen leeg in plaats van verzonnen. De registerrijen zijn ongewijzigd en
  `scripts/steekproef.py` filtert al op `bron = "register"`, dus die leest hetzelfde als
  voorheen.
- **Vier manieren waarop het klimmen door de `hasPart`-boom stil het verkeerde
  antwoord gaf** (issue #36). Alle vier zijn latent op De Wolden en bijten bij de
  volgende aanlevering; ze falen zonder melding, met alleen een ontbrekende waarde als
  spoor. (1) Het putdekselniveau werd alleen onder een *exact* `gwsw:Putdeksel`
  gezocht. Het GWSW kent `Putdeksel_LichtVerkeer` en `Putdeksel_ZwaarVerkeer` als
  subklassen, en zo'n put verloor dus haar dekselniveau, waarna `Node.bovenkant` op de
  maaiveldhoogte terugviel en elke hoogtecheck op een andere hoogte rekende. De lader
  gebruikt nu de subklasse-afsluiting, zoals overal elders. (2) Een object onthield
  maar een houder, terwijl het GWSW er meer toestaat (`Put isPartOf` Straat *en*
  Afwateringsgebied) en de export ze ook schrijft. Welke houder de eerste was hing af
  van de schrijfvolgorde; viel de wandeling op de verkeerde tak, dan liep zij dood en
  telde de streng als niet aangesloten. `Node.parents` draagt ze nu alle,
  `GwswDataset.klim_naar_knoop()` loopt in de breedte omhoog -- zoals
  `nulbevinding._Joiner` al deed -- en `afbakening` gaat langs diezelfde wandeling in
  plaats van langs een eigen kopie. (3) `gwsw:isPartOf` en `gwsw:isAspectOf` werden
  nergens gelezen, terwijl de ontologie ze als inverse van `hasPart` en `hasAspect`
  declareert. Een conforme export die ze schrijft leverde nul knopen en nul strengen op
  -- geen foutmelding, alleen een leeg rapport dat er goed uitziet. Beide
  schrijfrichtingen tellen nu mee, net als bij `hasConnection`. (4) Bij meer dan een
  `rdf:type` koos `beheerobjecttype()` de alfabetisch eerste, zodat een object dat
  zowel `Bouwwerk` als `Uitlaatconstructie` is "Bouwwerk" ging heten. Nu wint de
  specifiekste klasse volgens de subsumptierelatie van de ontologie; blijven er
  onvergelijkbare typen over, dan beslist het alfabet, want de ontologie wijst daar
  geen winnaar aan. Vijf fixtures (`dataset_*.ttl`) leggen de vier vast. Op De Wolden
  verandert er niets: die aanlevering kent geen `Putdeksel`, geen `Putdekselniveau`,
  geen `isPartOf`, geen `isAspectOf` en geen enkel meervoudig getypeerd subject.

- **Twee checktakken die nooit konden vuren: een onderdeel dat via `hasPart` aan een
  object hangt was op klasse niet te herkennen** (issue #34). `is_a()` leest het
  domeinmodel, en dat kent alleen knopen en strengen; een `Overstortdrempel` of een
  `Ledigingsvoorziening` is een `Constructieonderdeel` zonder Knooppunt-orientatie en
  werd dus nooit herkend. Daardoor zag ADM-007 een ingebouwde overstortdrempel niet en
  meldde RVZ-008 elke bergbezinkvoorziening zonder terugvoerende streng, ook als de
  lediging netjes geregistreerd stond. `GwswDataset.graph_is_a()` toetst nu het type uit
  de graaf tegen de klassenafsluiting, zoals ADM-009 het al deed; beide checks gebruiken
  die weg. Twee fixtures (`adm007_overstort_met_drempel.ttl`,
  `rvz008_bbb_met_lediging.ttl`) leggen beide richtingen vast. `of_class()` weigert
  voortaan een klasse uit de Verbinding-afsluiting: die kan nooit een treffer geven,
  omdat een streng haar orientatietypen niet draagt, en een stille nul is daar de
  slechtste uitkomst. Die weigering geldt alleen voor een *geconfigureerde* rol; noemt
  de SHACL-nulmeting zo'n klasse te globaal, dan is dat een meetuitkomst en zet de
  typeringspoort haar als onbeoordeelbaar in het rapport in plaats van de run te laten
  vallen. Op De Wolden verandert er niets -- die aanlevering bevat nul
  overstortdrempels, nul ledigingsvoorzieningen en nul bergbezinkvoorzieningen; ADM-007
  blijft op 181 bevindingen.

- **Een half gedeclareerde klassenhierarchie gold als een gekende hierarchie.**
  `klassenhierarchie_bekend` was `bool(subclasses)` -- globaal -- terwijl de
  werkelijke terugval op geometrie per wortel door `_bruikbare_afsluiting` bepaald
  wordt. Eén willekeurige `rdfs:subClassOf` in een export zette het predicaat op
  `True` terwijl de lader knopen en strengen wel degelijk aan hun geometrie herkende,
  en dan kwam het rapport zónder voorbehoud en mét een oordeel: precies de faalwijze
  die issue #33 sloot, overlevend in de naad met #36. Het predicaat vraagt nu
  hetzelfde als de lader, met dezelfde functie, over `Knooppunt` én `Verbinding`.
  Zevenentwintig van de 114 TTL-fixtures stonden in die tussentoestand en dragen vanaf
  nu het voorbehoud; twee ervan (`top001_losliggende_put.ttl`,
  `afbakening_kern_en_schil.ttl`) declareren nu de twee orientatiewortels die ze
  bedoelden te hebben, zodat er vijfentwintig overblijven. Op De Wolden mét ontologie verandert er
  niets.
- **De GeoPackage kleurde een run zonder oordeel volledig groen.** Groen betekent hier
  "beoordeeld en niets gevonden"; onder `--geen-ontologie` toetsen de checks over een
  onvolledige selectie, vinden dus weinig, en dan beweerde elk object het
  tegenovergestelde van het voorbehoud dat in `gwsw_run` stond -- een metadatatabel die
  niemand in QGIS openslaat. Zo'n run kleurt haar objecten nu grijs, met de reden in de
  popup. Wat er wél op een object staat kleurt het nog steeds (BO-29), en `status`
  houdt zijn vier waarden.
- **De eerlijkheidsroute van de typeringspoort dekte de verkeerde klassenfamilie.**
  Een te globale klasse die op nul objecten uitkomt terwijl de graaf er instanties van
  draagt heet nu onbeoordeelbaar, niet alleen een verbindingsklasse. Dat is het
  werkelijke geval: over de drie SHACL-rapporten samen noemt `CfkTypes_typ` drie
  klassen, en `Rioolstelsel` en `MechanischRioolstelsel` staan onder `Stelsel` -- knoop
  noch streng -- dus scoorde de poort er nul te globale objecten voor zonder een woord.
  Nul objecten bij nul instanties blijft een echte nul.
- **De terminaluitvoer van `toets` noemde het voorbehoud niet.** Markdown, GeoPackage
  en JSON droegen het al; de vierde plek waar een mens de uitkomst leest zweeg.

### Gewijzigd

- **`Overnamepunt` en het IT-stelsel bestaan wel degelijk in GWSW; de configuratie zei
  het tegenovergestelde** (issue #11). Twee commentaren in `src/nlriochecker/checks.toml`
  en `configs/dewoldenhoogeveen.toml` beweerden dat de ontologie deze begrippen niet
  kent. Beide zijn onjuist: `Overnamepunt` staat er als subklasse van `Aansluitpunt`, en
  het IT-stelsel als `Infiltratiestelsel` met zijn subklasse
  `DrainageInfiltratieTransportStelsel` (plus de leidingklassen `DIT_riool` en
  `DT_riool`). Wat ontbreekt zijn de instanties: De Wolden levert nul overnamepunten.
  De commentaren, de docstring van NET-007 en open punt 6 van het checkregister zeggen dat
  nu, en `Overnamepunt` staat in `[klassen] afvoer_eindpunt`. Het noodverband (`Gemaal`
  en `Pompunit`) met zijn loslaatcriterium staat als BO-33 in `docs/beslislog.md`, de
  keuze om NET-007 voorlopig op de infiltratieleidingen te laten draaien als BO-34. De
  uitkomst op De Wolden verandert niet: 35.370 meldingen over 48 checks, voor en na.

- **De belofte onder BO-33 is nagemeten in plaats van aangenomen, en drie onware zinnen
  zijn rechtgezet.** Een nieuwe fixture (`net001_overnamepunt.ttl`) legt vast dat NET-001
  een `Overnamepunt` op de putorientatie als afvoereindpunt accepteert -- de route
  `_eindpunten` -> `of_class` -> `types_of` -> `orientation_types` draaide tot nu toe op
  geen enkele dataset en in geen enkele test, want De Wolden levert er nul. Diezelfde
  fixture legt het restrisico vast: een `Overnamepunt` als losstaande orientatie zonder
  dragend object wordt geen knoop, en de streng ernaartoe valt niet als onbereikbaar op
  maar verdwijnt uit de netwerkanalyse -- alleen de notitie van de check telt haar nog.
  Rechtgezet: `Kunststof` is uit `[[leiding_put_materiaal]]` geschrapt zonder dat er iets
  voor in de plaats kwam (`PVC` en `PE` stonden er al), `gwsw:Uitlaat` hangt onder
  `RepresentatieFysiekObject` en staat dus níét op de orientatie zoals `Lozingspunt` en
  `UitlaatPunt`, en `[klassen] mechanisch` filtert geen enkele check maar bepaalt alleen
  de kaartkleur. Dat `Metselwerk` als putmateriaal blijft staan is een bewuste, tijdelijke
  afwijking van "GWSW is leidend" en staat voortaan als **BO-35** in `docs/beslislog.md`,
  met de gemeten kosten van beide kanten: schrappen zou ATTR-010 van 0 op 51 bevindingen
  brengen, over 37 strengen en 27 van de 33 `Metselwerk`-putten. Verwijzingen naar de
  gesloten issues #31 en #11 wijzen nu naar issue #47, met de vraag erbij. Het eenmalige
  meetwerk in `scripts/metingen/` heeft een `README.md` met zijn afspraken en legt zijn
  uitvoer naast het script; de vormpoort van dat script weigert voortaan ook een
  objectlijst met komma. Geen gedragswijziging: 35.370 meldingen over 48 checks.

- **De bewaking rond de GWSW-vocabulairetest en de drempelconfiguratie bijt nu waar ze
  eerder groen kon blijven.** De zelfgarantie van `tests/test_gwsw_vocabulaire.py` hing
  aan vier sentinels die geen van alle uit een van de twee TOML-configuraties kwamen;
  beide bestanden konden dus stil uit de termenlijst wegvallen. Er is nu een sentinel
  per termenbron (`BRONSENTINELS`). `BEKENDE_AFWIJKINGEN` is op `(naam, collectie)`
  gesleuteld in plaats van op naam alleen, zodat de skip voor `Metselwerk` als
  putmateriaal de vier legitieme leidingmateriaal-vindplaatsen niet meer meeneemt. De
  drifttest op `[drempels]` bond alleen veldnamen; de 53 waarden zelf worden nu tegen de
  `CheckThresholds`-defaults gehouden, voor `configs/dewoldenhoogeveen.toml` met een
  expliciete (vandaag lege) lijst `BEWUSTE_AFWIJKINGEN`. Dezelfde presentietest loopt
  nu over vijf modellen in plaats van één, zodat ook `[rapport]`, `[studiegebied]`,
  `[vulwaarden]` en `[bronnen]` eronder vallen. Nieuw: een test die de GWSW-versie in
  `data/gwsw-vocabulaire-index.json` gelijkhoudt aan die in `CLAUDE.md`, en een
  drifttest die meldt wanneer de symbolentabellen verder achteropraken bij de klassen
  die GWSW onder `Put`, `Bouwwerk`, `Hulpstuk` en `Knooppunt` hangt (vandaag 95 van 137
  ongedekt). Daarvoor draagt de index ook de directe `rdfs:subClassOf`-kanten; hij groeit
  van 196 naar 284 kB. CI bewaakt naast `NLRIOCHECKER_MIN_GESLAAGD` nu ook
  `NLRIOCHECKER_MAX_OVERGESLAGEN`, een grens die niet met de suite mee omhoog kruipt.
  Het besluit om de afgeleide index te tracken staat als BO-32 in `docs/beslislog.md`.
  Geen enkele drempelwaarde is verschoven en er verandert niets aan de uitkomst van een
  run.

- **Het bevindingenrapport van `toets` is opnieuw opgebouwd** (issue #16). De volgorde
  is nu: de naam van het gebied als titel, dan wat er in dat gebied ligt, dan of het
  voldoet, dan de verantwoording, en pas daarna het detail. De rapporten van
  `analyseer`, `dekking` en `vergelijk` blijven ongewijzigd.

  - **Titel:** de `naam_gebied` van het studiegebied, met terugval op de aanduiding die
    `StudyArea` zelf samenstelt en, zonder studiegebied, op de dataset. De synthese in
    `totaal/` heet "Totaal (N gebieden)"; de dataset staat in de romp.
  - **Aantallen:** een tabel objecttype x stelseltype over de kern van het gebied, met
    bij de leidingen zowel het aantal als de getekende meters. De contextschil staat als
    voetnoot eronder en telt niet mee -- er wordt niet over gerapporteerd.
  - **Managementsamenvatting:** een regel per conformiteitsklasse uit `vereiste_cfk`
    plus een totaalregel voor de eigen checks. Een vinkje betekent nul fouten in dit
    gebied; waarschuwingen blokkeren niet maar hun aantal staat er wel bij, met tussen
    haakjes hoeveel er systemisch zijn. Een klasse waarop niet gemeten is -- geen
    `--shacl`, of een `--cfk`-deelset waar zij buiten valt -- krijgt geen oordeel maar de
    toestandstekst. Een klasse die wél in de deelset zat krijgt haar oordeel; het
    voorbehoud over de deelset staat als markering boven het rapport (BO-7).
  - **Detailrapportage** in twee herkomstblokken: eerst de GWSW-nulmeting (per SHACL-vorm,
    fouten boven waarschuwingen, met de conformiteitsklassen erbij), dan de eigen checks
    (de foutchecks boven de waarschuwingschecks).
  - De rode draad staat bij de samenvatting in plaats van achter de tabellen. De
    verantwoording -- niet-bekeken objecten, weggelaten bevindingen, ontbrekende
    typeringspoort, niet-herleidbare focusnodes, externe bronnen, datakarakteristieken --
    is verplaatst maar niet ingekort.

  Nieuwe modules `uitvoer/omvang.py` (de aantallen, plus `stelseltypen` die de
  GeoPackage ook gebruikt) en `uitvoer/samenvatting.py` (de vier regels).

- **GWSW-conforme symbologie voor `putten` en `strengen`, met de kleur uitsluitend uit
  `status`.** Het symbool zegt wat voor object het is -- de indeling komt uit de
  PDOK-SLD's in `data/gwsw_opmaak/` -- en de kleur zegt hoe het ervoor staat:
  `#b2182b` rood, `#e08214` oranje, `#4d9221` groen, `#9e9e9e` grijs. Rood is duidelijk
  donkerder dan groen, dus ze blijven ook in grijstinten en bij deuteranopie uit elkaar
  te houden. De richtingpijl van een streng is er nog een in plaats van twee: `tegen`
  krijgt een enkele rode pijl die 180 graden gedraaid is en dus in de
  BOB-vervalrichting wijst -- waar het water werkelijk heen loopt. De logica erachter
  (`_richting_bob`) is ongewijzigd.

  De SVG's waar de SLD's naar verwijzen staan op `data.gwsw.nl` en zijn niet
  meegeleverd; elk symbool is daarom hertekend als eenvoudige QGIS-marker in de
  GWSW-vorm, met in de tabel de SLD-regel die hij vervangt. Elk objecttype uit de
  De Wolden-export en uit het Juinen-voorbeeld heeft een eigen regel met een eigen
  legendalabel; wat niet in de tabel staat krijgt een expliciet vangnetsymbool
  gelabeld "objecttype niet in de symbolentabel". De filters vergelijken
  hoofdletterongevoelig, want de export schrijft `DwaPerceelaansluitleiding` waar de
  SLD `DWAPerceelaansluitleiding` noemt.

  De twee QML's worden opgebouwd uit een tabel in
  `src/nlriochecker/uitvoer/stijlen/symbolen.py` in plaats van als bestand
  meegeleverd: de regelstructuur objecttype x status levert met de 44 knoop- en 37
  verbindingstypen in die tabel 220 respectievelijk 185 bladregels op, en die met de
  hand in XML onderhouden zou de typenlijst op twee plekken zetten. De stijl die in een
  GeoPackage meegaat draagt bovendien alleen regels voor de typen die er werkelijk in
  staan: met de volledige tabel zou de lagenboom van QGIS 225 legendaregels tonen op
  een laag met zes typen, met de voorkomende typen zijn het er 35. `bouwwerken.qml` en
  `waterdelen_zonder_zinker.qml` blijven onveranderde bestanden. Zie BO-30 (issue #14).

- **Hoverpopups (QGIS Map Tips) op beide objectlagen.** De QML draagt een
  `<mapTip enabled="1">` met een stijlblok, een vaste breedte van 300 px en één
  expressie: `[% "popup_html" %]`. De inhoud komt uit de voorgebakken kolom van issue
  #13, dus er is geen live join of relation nodig -- die zouden niet meereizen in
  `layer_styles`. Het stijlblok staat een keer in de QML en niet in elke rij; per rij
  herhaald zou het de GeoPackage tientallen megabytes groter maken. Geen webfont en
  geen afbeelding-URL. `styleCategories` noemt `MapTips` expliciet, anders leest QGIS
  het element niet terug uit `layer_styles` en blijft de popup leeg zonder foutmelding.
  **Let op:** map tips verschijnen alleen als "Show Map Tips" in de QGIS-werkbalk
  aanstaat (issue #15).

- **De GeoPackage heeft nog twee objectlagen: `putten` en `strengen`.**
  `meldinglocaties` vervalt als featurelaag en `mechanisch_riool` gaat op in de
  lijnenlaag. Elk object draagt twee nieuwe kolommen: `status` met precies vier
  waarden (`rood` bij een fout, `oranje` bij alleen waarschuwingen, `groen` bij geen
  eigen gebrek, `grijs` als er niet beoordeeld is én niets gevonden) en `popup_html`
  met een voorgebakken hoverpopup. Mechanisch riool houdt zijn GWSW-objecttype; het
  wordt door de meeste checks overgeslagen, maar niet door alle -- TOP-010, TOP-011 en
  de SHACL-nulmeting raken het wel -- en dan kleurt het gewoon mee, met "maar deels
  beoordeeld" in zijn popup. Met een studiegebied komt er een grijze ring om het gebied
  heen: de objecten binnen de buffer, zodat de kaart niet bij de gebiedsgrens ophoudt
  alsof daar niets ligt. Niet de hele contextschil -- die bevat ook de samenhangende
  vrijvervalcomponent, op een buurt van 507 objecten al gauw 12.106, en dan zou elk
  buurtbestand het net van de halve gemeente meesturen. De popup zegt per grijs object
  waarom.

  **Bewust verlies:** de exacte foutlocatie op een lijn -- het snijpunt van een
  kruising, het midden van een streng -- en het naloopwerk in een kaal GIS-pakket
  zonder joins verdwijnen van de kaart. De meldingen zelf blijven volledig in de tabel
  `meldingen`, joinbaar op `feature_id`, en die tabel draagt nu de kolommen `x` en `y`
  met diezelfde foutlocatie -- anders zou hij stilzwijgend uit de GeoPackage
  verdwijnen. Objectloze meldingen (dataset-breed, EXT-verwijzingen zonder rioolobject,
  de onherleide focusnodes van de nulmeting) stonden ook voorheen niet op de kaart en
  blijven in rapport en meldingentabel staan. Zie BO-29 (issue #13).

- `status` telt systemische meldingen niet mee, net als `ergste_ernst`, `n_fout` en
  `n_waarschuwing` al deden. Op De Wolden draagt de nulmeting 68.882 systemische
  meldingen op 105.963; zouden die meetellen, dan is vrijwel elke put rood. Gevolg: een
  object waarvan alle meldingen systemisch zijn krijgt `groen`, wat hier "geen gebrek
  dat dit object van zijn buren onderscheidt" betekent en niet "in orde". De kolom
  `n_systemisch` en de popup zeggen het er allebei bij.

- De opdrachtregel noemt de tellingen van de eigen checks en die van de nulmeting
  apart, `gwsw_run` telt `fouten` en `waarschuwingen` uit de meldingenstroom (zodat ze
  niet met `meldingen_totaal` uit de pas lopen), en de rode draad in het rapport
  redeneert alleen nog over meldingen uit het checkregister -- de SHACL-vormen zijn per
  kenmerk gesplitst en slaan per constructie samen aan, dus "meerdere checks op
  hetzelfde object" zegt daar niets. Het rapport meldt voortaan ook hoeveel
  nulmetingovertredingen buiten het studiegebied vielen.

- **Alle 53 velden van `CheckThresholds` staan nu expliciet in `[drempels]`**, in zowel
  `src/nlriochecker/checks.toml` als `configs/dewoldenhoogeveen.toml`, elk met zijn
  huidige default en een commentaarregel over de betrokken check en de herkomst van het
  getal (checkregister of projectkeuze). Voorheen droeg `[drempels]` er twee van de
  drieënvijftig en vielen de overige stilzwijgend terug op de Python-default, onzichtbaar
  voor wie het configbestand las. Geen enkele waarde is veranderd; een nieuwe drifttest
  (`test_elke_drempel_staat_expliciet_in_de_toml` in `tests/test_checkconfig.py`) dwingt
  af dat beide bestanden elk veld blijven dragen (issue #28).

### Toegevoegd

- **`scripts/metingen/issue32_klassendekking.py` meet wat de voorgestelde
  klassenlijsten van issue #32 op De Wolden zouden doen.** Alleen meten: er is geen
  enkele lijst gewijzigd. Uitkomst: op één na raakt elke voorgestelde uitbreiding
  nul objecten, omdat de export maar 13 knoop- en 16 verbindingklassen gebruikt; alleen
  `Bergbezinkleiding` in `[klassen.stelseltypen]` raakt er een. Het script leest de
  huidige lijsten uit beide configbestanden, scant de 112 MB TTL regelgewijs in plaats
  van via rdflib, en ijkt die scan tegen `load_dataset` op een uittreksel van diezelfde
  export.
- **`data/gwsw-vocabulaire-index.json` gaat mee in versiebeheer**, zodat de
  vocabulairetest ook op de CI-runner draait in plaats van er 140 van zijn 142 gevallen
  over te slaan. Het is een afgeleide van `Ontologie_GWSW_Totaal.ttl` met per GWSW-naam
  zijn `rdf:type`s en niets meer (3.316 termen, 200 kB); de ontologie zelf blijft met
  haar 2,6 MB buiten versiebeheer. Licentie is geen bezwaar: de GWSW-ontologie staat
  onder CC0. Bijwerken doet `scripts/maak_gwsw_index.py`, met de hand, zoals het
  aanleveren van een nieuwe ontologie ook handwerk van de auteur is -- er wordt niets
  bij data.gwsw.nl opgehaald. `test_index_volgt_de_ontologie` bewaakt dat de index niet
  achterloopt, en draait alleen waar `data/gwsw_ontologieen/` staat.
- **`tests/test_gwsw_vocabulaire.py` bewaakt dat elke GWSW-naam die het pakket gebruikt
  werkelijk in `Ontologie_GWSW_Totaal.ttl` staat** (issue #30, laag A). De termen komen
  uit de geladen `CheckConfig` (`checks.toml` én `configs/dewoldenhoogeveen.toml`), de
  `PlausibilityTables`, de symbolentabellen en een AST-sweep over de aspectliteralen in
  `src/`; ze worden nergens overgeschreven. Er wordt op `rdf:type` getoetst en niet op
  het voorkomen van de naam, want `Kunststof` bestaat wel maar niet in
  `MateriaalPutColl`. De meldingtekst noemt vindplaats, verwachte collectie en de
  dichtstbijzijnde bestaande naam -- die laatste regel had de twee eerdere fouten
  voorkomen. Openstaande gevallen staan met hun reden in `BEKENDE_AFWIJKINGEN`; de test
  valt in beide richtingen, dus zowel een nieuwe fout als een opgeruimde term maakt hem
  rood. `dekking.toml` en `shaclrapport.py` blijven erbuiten (SHACL-vormnamen), een
  hoofdletterafwijking krijgt een eigen soort, en er wordt tegen Totaal gevalideerd en
  niet tegen de deelmodellen uit 2021. Kosten: circa vier seconden per testrun.
- **`scripts/steekproef.py`** trekt uit de GeoPackage van een `toets`-run een
  gemeentebrede steekproef van tien bevindingen per eigen check, om elke check met de
  hand na te kunnen lopen. De trekking spreidt over een vast grid van 1000 m, zodat de
  tien niet in een straat klonteren, en is reproduceerbaar via een seed per check. De
  bron is de GeoPackage van de run zelf -- de tabel `meldingen`, het dashboard
  `overzicht_checks` en de lagen `putten` en `strengen`, waarvan de geometrie als blob
  wordt overgenomen -- dus kan de steekproef niet afwijken van de run die hij
  bemonstert, en hoeft de dataset er niet voor ingelezen te worden. Alleen
  `bron = 'register'`: de nulmeting blijft erbuiten. Het bestand draagt de lagen
  `steekproef_putten`, `steekproef_strengen` en `steekproef_locaties` (de foutlocatie
  van elke getrokken melding), de tabel `steekproef_dekking` met een rij per eigen
  check -- ook de checks zonder bevindingen, met de reden erbij -- en `steekproef_run`
  met de herkomst en de trekkingsinstellingen. Elke rij heeft lege kolommen `oordeel`
  en `opmerking` om het handmatige oordeel in QGIS in te vullen. Een doelbestand dat
  de bron zelf is wordt geweigerd -- een typefout in `--uit` zou anders een run van
  minuten wissen -- en twee drifttests houden de kolomnamen die het script leest vast
  aan `MELDING_KOLOMMEN` en `OVERZICHT_KOLOMMEN` in `uitvoer/gpkg.py`. Die tweede lijst
  staat daarvoor nu op moduleniveau in plaats van in de schrijver.

- De SHACL-nulmetingovertredingen komen als meldingen in alle vier de uitvoervormen
  terecht, uit dezelfde meldingenstroom als de eigen checks: `Bron = nulmeting`,
  `Categorie = NULMETING`, check-ID `NULMETING-<SHACL-vorm>`, dimensie `Compliance`.
  Nieuw veld `cfk` op `Melding` -- kolom `CFK` in de CSV, kolom `cfk` in de
  GeoPackage-tabel `meldingen`, veld `cfk` in de JSON -- met de conformiteitsklassen
  die de overtreding noemen. Daarmee gaat `schema_versie` van `1.0` naar `1.1`; het is
  een achterwaarts verenigbare toevoeging, dus een afnemer die op het hoofdnummer pint
  merkt er niets van. Dezelfde overtreding in meerdere CFK-rapporten levert **een**
  melding met de klassen erbij. Een focusnode die niet zelf een put of streng is --
  het eindpunt van een leiding, de maaiveldorientatie van een put -- wordt via
  `hasPart`, `hasAspect` en als laatste `hasConnection` omhooggelopen tot het object
  waar hij bij hoort; op De Wolden herleidt daarmee 99,5% (105.385 van de 105.963),
  waar een strikt directe join op 87% was blijven steken. Komt hij nergens op uit --
  de 578 overtredingen op een stelsel of een klassenaam -- dan blijft de melding staan
  zonder object, zonder plek op de kaart en met een leeg gebied, en het rapport telt
  die gevallen expliciet -- ook als het er nul zijn. Op De
  Wolden leveren de drie rapporten samen 213.500 regels en na ontdubbeling 105.963
  meldingen (87.017 fouten, 18.946 waarschuwingen); de zwaarste posten zijn drie
  kardinaliteitsvormen die vrijwel elke inspectieput raken en die daardoor als
  systemisch gemarkeerd worden. Zie BO-28 (issue #12).

- RVZ-002 en RVZ-003 (W, Compleetheid): een overstortput zonder geregistreerd
  drempelniveau respectievelijk zonder geregistreerde drempelbreedte, ook als het
  `Overstortdrempel`-onderdeel zelf ontbreekt. De nulmeting kent geen vorm op die twee
  kenmerken, dus de schrapping rustte op niets; de sentinels zijn uit `dekking.toml`.
  Nieuwe regressietest: geen enkele geschrapte check mag in de referentiemeting ongeraakt
  blijven. Op De Wolden melden ze allebei alle 245 bekeken overstortputten (218
  `Overstortput` plus 27 `Stuwput`) -- de export bevat geen enkel
  `Overstortdrempel`-onderdeel. Zie BO-26 (issue #6).
- ATTR-013 (W, Compleetheid) en de vulwaarde-leesregel `dataset.markeer_vulwaarden`,
  geconfigureerd in `[vulwaarden]`: een hoogtekenmerk met |waarde| <= `hoogte_band_m`
  geldt als niet geregistreerd. De regel wordt na het laden toegepast, op een plek in
  `toetsrun`; de cache bewaart de ruwe parse. Op De Wolden vervallen daarmee 6.498 harde
  fouten en 3.647 waarschuwingen die op zo'n vulwaarde rustten (HGT-002 5.231 naar 2.128,
  HGT-003 2.813 naar 1.090, HGT-004 532 naar 31, HGT-018 1.190 naar 175, HGT-013 2.545
  naar 340, HGT-014 889 naar 157, HGT-007 2.126 naar 1.559, HGT-009 327 naar 282, en
  kleinere dalingen bij HGT-001, HGT-005, HGT-006, HGT-008 en NET-003); ATTR-013 meldt
  4.215 objecten. Er komt er geen bij, op twee HGT-009-bevindingen na: die check verliest
  er 47 en wint er 2, doordat een vulwaarde daar de werkelijke, kleinere BOB-sprong stond
  te verdringen. HGT-018 heeft nu een toelichting. De tabel met datakarakteristieken
  telt sindsdien alleen echte registraties -- een hoogte binnen de vulwaardeband staat
  niet meer als gevulde waarde in de noemer -- en het rapport zegt onder die tabel
  hoeveel waarden de leesregel heeft weggezet. Zie BO-27 (issue #1).
- `configs/dewoldenhoogeveen.toml`: de projectconfiguratie voor het hele gebied van de
  OroX-dataset, met de bronnen uit `data/gis_dewoldenhoogeveen`. Alleen het blok
  `[bronnen]` wijkt af van de meegeleverde `checks.toml`.
- `nlriochecker.toetsrun` voert een toets uit zonder de opdrachtregel:
  `Toetsopdracht` in, `Toetsuitslag` uit, met de gemeten uitkomsten als velden en het
  verhaal voor de gebruiker in `regels()`. Het commando `toets` is er de adapter van
  geworden; de uitvoer op het scherm en op schijf is ongewijzigd. Zie BO-21.
- `errors.OpdrachtError` voor een verzoek dat niet kan (een gebiedskeuze zonder
  studiegebied, een onbekende conformiteitsklasse, een onbekend check-ID), en
  `meting.kies_cfk` om een CFK-keuze tegen de vereiste set te toetsen.
- Twee lagen in de GeoPackage met de externe objecten waarnaar de EXT-checks verwijzen:
  `bouwwerken` (EXT-001) en `waterdelen_zonder_zinker` (EXT-003), elk met een eigen
  QGIS-stijl. Ze worden uitsluitend gevuld vanuit de meldingen van die uitvoer, dus hun
  inhoud is per constructie gelijk aan de testuitkomst -- ook per gebied.
- EXT-001 en EXT-003 wijzen het geraakte externe object aan in `object2_uri` en
  `object2_label` (`bgt:pand/...`, `bag:pand/...`, `bgt:bouwwerk/...`,
  `bgt:waterdeel/...`, met `geo:<hash>` als terugval voor een bron zonder
  identificatie). Achterwaarts verenigbaar binnen schemaversie 1.0; de conventies staan
  in [docs/json-schema.md](docs/json-schema.md).
- Een dekkingspoort op de externe bronnen: elke aangeleverde laag en het AHN-raster
  moeten het bereik uit `bronnen.studiegebied` dekken, vectorlagen inclusief de grootste
  EXT-zoekafstand. Een tekort boven `[bronnen] dekking_tolerantie_m` (standaard 0) is
  een harde fout die beide omhullenden en het tekort per zijde noemt. Een te kleine bron
  gaf tot nu toe stilte in plaats van bevindingen.
- Rapportage per studiegebied-feature. Bevat het studiegebiedbestand meer dan een vlak,
  dan schrijft `toets` per gebied een submap met alle vier de uitvoervormen, plus een
  `totaal/` met de synthese en de unieke meldingen over alle gebieden. De meldingen van
  een gebied zijn gelijk aan die van een losse run met alleen dat gebied; daar staat een
  test op. Met `--gebied` beperk je de run tot een of meer gebieden.
- Strenge validatie van het studiegebiedbestand, altijd voordat de dataset geladen wordt:
  alleen Polygon en MultiPolygon (overgeslagen typen worden geteld en gemeld), vanaf twee
  vlakken een verplichte, gevulde, unieke kolom `naam_gebied` waarvan de gesaneerde
  mapnamen niet mogen botsen, en voor GeoJSON een toets op het coordinaatstelsel: een
  legacy `crs`-member met EPSG:28992, of alle coordinaten binnen de RD-grenzen uit
  `[drempels]`.
- **De melding-ID's van EXT-001 en EXT-003 verschuiven.** `melding_id` is een hash over
  check, objecten en detailsleutels; nu die twee checks hun `object2_uri` vullen, krijgen
  hun meldingen een ander ID dan in de vorige versie. Wie meetmomenten vergelijkt, ziet
  ze eenmalig als opgelost plus nieuw. Datzelfde gebeurt bij een bron zonder
  identificatie zodra haar geometrie wijzigt, want dan verschuift de `geo:`-sleutel mee.
  Het JSON-schema blijft 1.0: het contract verandert niet, alleen de inhoud van een veld
  dat er al was.
- `[bronnen] dekking_tolerantie_m` staat in de meegeleverde `checks.toml` op 300 m. De
  code blijft standaard streng (0 m); deze waarde hoort bij de bronnen in `data/gis`,
  waarvan `bgt_bouwwerk` aan de oostkant 276 m voor de rand ophoudt.
- Uitbreidingen in de Python-API rond de externe bronnen (0.x, dus zonder
  deprecatietermijn): `load_external_data` kreeg een keyword-only `dekkingseis`,
  `CheckContext` en `CheckRun` kregen het veld `treffers`, en
  `_WatergangKruising.kruisingen()` levert `_Kruising`-objecten (streng, geometrie en
  attributen van het waterdeel, laag, buffer) in plaats van tuples van vier waarden --
  de geometrie van het waterdeel is erbij gekomen en de velden hebben een naam
  gekregen. De eerste twee zijn additief.
- Een gebied zonder GWSW-objecten stopt een run over meerdere gebieden niet meer, maar
  levert een eigen rapport met nul bevindingen en een expliciete melding -- in dat rapport
  en in de synthese. Bij een run op een enkel gebied blijft het een harde fout.
- De JSON-envelop kan `gebied` en `gebieden` dragen. Achterwaarts verenigbaar binnen
  schemaversie 1.0: een run zonder studiegebieden schrijft de velden niet.
- `--cfk` op `analyseer`, `dekking`, `toets` en `vergelijk`: toetsen op een
  deelverzameling conformiteitsklassen. Standaard blijven alle drie vereist; elke
  afwijking staat als waarschuwingsregel boven elk rapport en in de GeoPackage
  (`cfk_set`, `volledig`). Een run zonder `--shacl` meldt dat er niet gemeten is --
  dat is iets anders dan een deelset, en iets anders dan volledig.
- Een JSON-export van de meldingenstroom (`bevindingen.json`), met een envelop en een
  eigen `schema_versie` los van het packagenummer; uit te zetten met `--geen-json`.
  Het contract staat in [docs/json-schema.md](docs/json-schema.md).
- Zichtbare voortgang bij het inlezen van de TTL's, het inlezen van de
  SHACL-rapporten, het draaien van de checks en het wegschrijven van de GeoPackage.
  Als library via het protocol in `voortgang.py`, op de opdrachtregel als balk op
  stderr. Geen nieuwe afhankelijkheid.
- Elk uitvoerbestand noemt de package en versie die het schreef: de Markdown-rapporten
  in een regel onder de titel, de CSV's in de kolom `Gereedschap`, de GeoPackage in het
  veld `gereedschap` van `gwsw_run`.
- `py.typed`, zodat de typehints van deze package ook bij een importerende toepassing
  aankomen.
- CI (`.github/workflows/toets.yml`): ruff, mypy en pytest op elke push naar `main` of
  `dev` en op elke pull request naar `main`. De run valt als er nog meer tests overgeslagen
  worden dan de runner sowieso overslaat -- een fixturemap die niet meekomt leest anders
  als "alles groen".
- Mypy als poort, met een configuratie in `pyproject.toml`; de codebase is schoon.
- Dit wijzigingslog.

### Gewijzigd

- Checkregister v0.9: RVZ-002 en RVZ-003 zijn uit de tabel Geschrapte checks gehaald en
  gebouwd, ATTR-013 is toegevoegd, EXT-003 is gepreciseerd. De versieverwijzingen in code,
  configuratie en documentatie wijzen naar v0.9.
- Openstaand werk staat voortaan als GitHub-issue op `mcolee/nlriochecker` en niet meer in
  `CLAUDE.md` of in de open punten van het checkregister. Van de open punten van het
  register zijn 1, 9, 11 en 13 issues geworden en dragen ze nu een verwijzing daarheen;
  2 (drempelwaarden), 3 (ADM-003 als regex) en 6 (hoe overstorten in de export verschijnen)
  staan als afgehandeld gemarkeerd, elk met de plek waar dat te controleren is; en van
  punt 10 wordt het restant niet opgepakt -- er is geen Mds-nulmetingrapport beschikbaar,
  en daarmee valt het buiten scope -- wat er met de inhoud bij staat. Wat er onder
  punt 6 nog wel open stond -- de toenmalige lezing dat `Overnamepunt` en een klasse voor
  het IT-stelsel niet in de GWSW-ontologie zouden bestaan en de engine ze zelf invult --
  is een eigen issue geworden; de twee verwijzingen in `checks.toml` wijzen daarheen in
  plaats van naar open punt 6. Die lezing is inmiddels weerlegd: beide begrippen bestaan
  wel degelijk, zie BO-33 en BO-34 in `docs/beslislog.md` en de regel hierboven onder
  issue #11. De
  nummering van de open punten is ongemoeid gelaten, omdat `checks.toml` en twee modules er
  bij nummer naar verwijzen.
- `bgt_waterlagen` bevat alleen nog `waterdeel`; `ondersteunendwaterdeel` valt buiten
  scope. Dat is de oever en niet het water zelf, en een streng die een slootkant raakt
  kruist geen watergang. Op De Wolden gaan EXT-002 en EXT-003 daarmee van 993 naar 859
  meldingen, wijzen er 195 een andere watergang aan dan voorheen, en komen er bij EXT-007
  drie bevindingen bij die een oever eerder afdekte. Binnen `waterdeel` telt elk type mee.
  Zie BO-24.
- De aangeleverde geodata staat niet meer in `data/gis` maar in
  `data/gis_koekangerveld`; daarnaast is er `data/gis_dewoldenhoogeveen` met dezelfde
  bronsoorten voor het hele gebied van de OroX-dataset. De standaard `[bronnen] map`
  in `checks.toml` en de integratietests wijzen mee.
- De laatste twee plekken in de uitvoerlaag die hun eigen klassenselectie opbouwden
  (`uitvoer/synthese.py` en `uitvoer/gpkg.py`) gebruiken nu `checks/selectie.py`,
  waarmee het restant uit BO-20 weg is. De rol `mechanischeleidingen` is daar
  bijgekomen.

- De klassenselecties van de checks staan op een plek, `checks/selectie.py`, in plaats
  van in vijf checkmodules met elk hun eigen cachesleutel. De namen volgen de
  GWSW-ontologie waar een klasse de rol dekt; `gwsw:Streng` bestaat niet, dus wat
  `_strengen` heette selecteert `gwsw:Leiding` en heet nu `leidingen`. Interne
  wijziging: de uitvoer van een volledige run is byte-identiek gebleven. Zie BO-20 en
  [CONTEXT.md](CONTEXT.md).
- Een studiegebiedbestand met meerdere vlakken zonder kolom `naam_gebied` is voortaan een
  fout in plaats van een stilzwijgende samenvoeging tot een gebied. Datzelfde geldt voor
  niet-vlakken: die werden ingelezen en tellen nu niet meer mee.
- Breuken in de Python-API (0.x, dus zonder deprecatietermijn):
  - `load_study_area` levert nog steeds een `StudyArea` (de unie van alle vlakken), maar
    valideert nu als hierboven. `load_studiegebieden` levert de gebieden per feature.
  - `bouw_analyseset` kreeg een keyword-only `gedeeld`, `run_checks` een keyword-only
    `fase`, `CheckContext` het veld `gedeelde_volledige_context`, `schrijf_uitvoer` de
    keywords `gebied`, `meldingen` en `notities`, `write_check_report` de parameter
    `notities` en `beperk_tot_studiegebied` de parameters `binnen` en `leeg_toegestaan`.
    Alle additief.
  - `CheckContext.volledige_context()` draagt geen `analyseset` meer. Checks die op de
    volledige export draaien (`volledige_dataset_checks`) noemen hun bereik daardoor
    "deze dataset" in plaats van "het geanalyseerde deel"; dat laatste was onjuist, want
    ze zien de hele export. Raakt alleen projecten die zelf checks aan die lijst
    toevoegen; de standaard (ADM-002) noemt zijn bereik niet.
- `toets` zonder `--shacl` schrijft een extra regel `**Geen nulmeting:** ...` in
  `bevindingen.md`. Wie rapporten van voor en na deze versie vergelijkt, ziet die regel
  als verschil.
- Breuken in de Python-API (0.x, dus zonder deprecatietermijn):
  - `Nulmeting` kreeg het verplichte veld `meetbereik`; `CoverageResult` kreeg het
    verplichte veld `meetbereik` **tussen** `checks` en `discrepanties` in, en `Uitvoer`
    kreeg het verplichte veld `json`. Wie deze dataclasses positioneel construeerde,
    krijgt bij `CoverageResult` geen `TypeError` maar een stille verschuiving van
    argumenten. Construeer ze met sleutelwoorden.
  - `laad_nulmeting` kreeg een derde parameter `volledige_cfk`. Zonder die parameter
    geldt de meegegeven set als de volledige set, en dan meldt de run "volledig". Een
    library-gebruiker die op een deelset toetst, moet hem dus meegeven; de CLI doet dat.
  - `schrijf_uitvoer` kreeg `met_json` en `voortgang`; `load_dataset`, `laad_nulmeting`,
    `run_checks`, `laad_met_cache` en `schrijf_geopackage` kregen een keyword-only
    `voortgang`. Die laatste zijn additief.
  - `CheckRun.meetbereik` is nooit `None`; een run zonder opgegeven bereik draagt
    `Meetbereik.niet_gemeten(())`.
- De ondergrens van `click` is naar `>=8.2`: daarvoor mengde `CliRunner` stderr in
  stdout en bestond `Result.stderr` niet.
- `vergelijk` weigert twee nulmetingen die op verschillende conformiteitsklassen
  getoetst zijn: een daling in het aantal meldingen die uit een kleinere getoetste set
  komt is geen verbetering. Geen forceer-vlag.
- Een SHACL-rapport voor een conformiteitsklasse buiten de gekozen set is een fout in
  plaats van een stille overslag.
- `[nulmeting] vereiste_cfk` is verplicht in de projectconfiguratie. De lijst stond ook
  als default in `checkconfig.py`; een config die de sectie miste viel daar
  stilzwijgend op terug, en sinds `--cfk` bepaalt diezelfde lijst ook welke klassen die
  optie accepteert.
- `CheckContext.cached()` is generiek geworden: bellers krijgen hun eigen structuur terug
  in plaats van `object`. Dat haalde in een keer 23 typefouten weg.
- `scripts/uitgave.py` toetst nu ook met mypy en onderhoudt dit wijzigingslog.
- Werkafspraak: werk staat op `dev`, `main` draagt alleen uitgebrachte versies.
- `[vulwaarden]` weigert een kenmerk waarop de leesregel niet werkt: alleen
  `Maaiveldhoogte`, `Putdekselniveau`, `BobBeginpuntLeiding` en `BobEindpuntLeiding`
  (de verzameling staat als `VULWAARDE_KENMERKEN` bij `Vulwaarde` in `dataset.py`).
  Een tikfout in het hoofdlettergebruik gaf tot nu toe een run waarin de regel stil
  niets deed terwijl ATTR-013 meldde dat hij gold. `hoogte_band_m` heeft daarnaast een
  bovengrens van 0,5 m gekregen: dat is geen drempelkeuze maar een invoertoets, want een
  band in centimeters of millimeters leest elke BOB en elke maaiveldhoogte als ontbrekend,
  waarna dertien checks stilvallen en ATTR-013 elk object met een hoogte meldt.
- De toelichting van ATTR-013 telt hoeveel knopen en strengen met een vulwaarde buiten
  haar gemelde populatie vallen (persleidingen, drains, compartiment- en
  hulpstukorientaties). De leesregel raakt ze wel, geen enkele melding noemt ze; het
  getal komt per run uit de gemarkeerde dataset. Zie BO-27.

### Gerepareerd

- ATTR-006 zet de zijde (begin- of eindpunt) in de melding; de twee meldingen op een
  streng krijgen daarmee een eigen, stabiele ID in plaats van een volgnummer dat tussen
  runs kon verschuiven. **De melding-ID's van ATTR-006 verschuiven eenmalig**;
  `schema_versie` blijft 1.0 (issue #2).

- NET-004 noemt bij parallelle strengen de eerste op de kant (gesorteerd op URI) in plaats
  van de laatst ingelezen; de graafkanten dragen geen attributen meer. Twee parallelle
  strengen delen in een `DiGraph` een kantsleutel, dus de tweede `add_edge` overschreef de
  `uri` en het `label` van de eerste. De genoemde streng kan eenmalig verschuiven
  (issue #5).

- EXT-002 en EXT-003 delen een kruisingenlijst en melden in hun toelichting hoeveel
  duikers buiten de populatie vallen; de testfixtures volgen de ontologie (`Duiker` onder
  `Leiding`, `Zinker` onder `VrijvervalRioolleiding`). Geen verandering in de meldingen.
  Zie BO-25 (issue #3).

- Het fase-totaal van de GeoPackage-voortgang werd met de hand geteld en kon uit de
  pas lopen met het aantal gezette stappen. Het volgt nu uit dezelfde rij staplabels.

- Een streng met een lijngeometrie van precies een coordinaat brak het inlezen van de
  hele export af. GEOS gooit daar zijn eigen fout, en die erft niet van `ValueError`,
  dus vloog hij ongevangen door de GML-parser heen. Het object wordt nu als onleesbaar
  geteld en het rapport meldt het, zoals bij elke andere onleesbare geometrie.

- NET-004 wees per run een andere streng aan. `nx.find_cycle` zonder `source` begint bij
  de eerste knoop in invoegvolgorde, en die volgt uit de hashseed; twee runs op dezelfde
  data toonden daardoor een verschil dat er niet was. De kringloop start nu bij de
  kleinste URI van het samenhangende deel.

- **Vijf GWSW-namen in de configuratie bestonden niet zoals ze geschreven stonden**
  (issue #31, gevonden door de vocabulaire-audit uit #30). De profielvorm heet in
  `VormLeidingColl` `Muil` en niet `Muilprofiel`: daardoor kreeg een gemetseld
  muilprofielriool een valse ATTR-012 en vuurde de ATTR-004-regel over de
  hoogte-breedteverhouding op geen enkel muilprofiel. `Kunststof` stond als putmateriaal
  in `[[leiding_put_materiaal]]` maar zit niet in `MateriaalPutColl` (wel in
  `MateriaalAfsluiterColl`, `MaterialOfStepsColl` en `Uitvoering`), dus geen legale
  export kon die waarde schrijven; hij is geschrapt zonder dat er iets voor in de plaats
  kwam. `PVC` en `PE` stonden er al en dekken de kunststofrol maar deels: de overige
  kunststofklassen van `MateriaalPutColl` (`HDPE`, `GVK`, `Polyester`, `Polypropyleen`,
  `PitchFibre`, `UnidentifiedTypeOfPlastics`) staan er niet bij -- dat gat staat als
  issue #43. De
  symbolentabel schreef `Interneoverstortput` en `Verholengoot` waar de ontologie
  `InterneOverstortput` en `VerholenGoot` schrijft (de symboolkeuze werkte al, want ze
  vergelijkt hoofdletterongevoelig), en droeg een regel voor `Vacuumgemaal`, dat geen
  objecttype is maar een symboolklasse -- die regel kon nooit een treffer krijgen en is
  weg; `Vacuumpompstation` dekt het gemaal zelf. Op De Wolden verandert er niets: die
  dataset kent geen `Muil` en geen kunststof put, en ATTR-004, ATTR-010 en ATTR-012
  leveren er voor en na nul bevindingen. `AHN5` en `Metselwerk` blijven staan; dat zijn
  open vragen voor de auteur (vraag 1 en 2 van issue #47). Dat `Metselwerk` blijft staan
  is een bewuste, tijdelijke afwijking van "GWSW is leidend" en staat als BO-35 in
  `docs/beslislog.md`.

### Verwijderd

- De afhankelijkheid `pyproj`; die werd nergens geimporteerd en komt zo nodig via
  geopandas en rasterio mee.

## [0.2.0] - 2026-08-17

Eerste uitgave onder een vast versienummer.

### Toegevoegd

- Afbakening met een studiegebied: de checks draaien op een kern plus contextschil,
  het rapport gaat over de kern.
- Een cache van de geparseerde dataset (`~/.cache/nlriochecker`), met een sleutel die de
  broncode van de lader meeneemt.
- GeoPackage-uitvoer met QGIS-stijlen in `layer_styles`, uit dezelfde meldingenstroom
  als de Markdown- en CSV-uitvoer.
- Checkregister v0.8 als contract, met een dekkingsmatrix die uit het register
  gegenereerd wordt.
- `scripts/uitgave.py` en een enkele versiewaarheid in `pyproject.toml`.

### Gewijzigd

- Hernoemd naar `nlriochecker`: package, commando en cachemap.
- Onder EUPL-1.2 gebracht.

[Unreleased]: https://github.com/mcolee/nlriochecker/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/mcolee/nlriochecker/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/mcolee/nlriochecker/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mcolee/nlriochecker/releases/tag/v0.2.0
