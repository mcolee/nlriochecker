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

[Unreleased]: https://github.com/mcolee/nlriochecker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mcolee/nlriochecker/releases/tag/v0.2.0
