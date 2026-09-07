export const meta = {
  name: 'nlrio-fable-product',
  description: 'Fable 5.1-productswarm op nlriochecker langs vijf beheerderstaken (databeheerder, modelleur, bestuur, tweede gemeente, sector-gat): doorlopen taken met klok en tarief, Fable-skepticus op de grootste hefboom, Fable-regisseur met hefbomen10x en <=15 aanbevelingen',
  whenToUse: 'Issue #140. Eerst args:{stap:"audit"} als kostenmeting, dan volledig met resumeFromRunId; args:{stap:"droog"} spawnt geen agent en toont alleen de lenzen en promptlengtes.',
  phases: [
    { title: 'Audit', detail: '5 Fable-lenzen langs taken: elke lens loopt een taak door met de klok erbij, leest de gemeentebrede uitvoer en/of het RIONED-corpus, en rekent de huidige kosten in uren x tarief', model: 'fable' },
    { title: 'Verify', detail: 'Fable-skepticus: niet "is het echt" maar "is dit de grootste hefboom, en klopt het bewijs voor de huidige kosten"', model: 'fable' },
    { title: 'Regie', detail: 'Fable-regisseur: hefbomen10x (nu/straks in minuten, euro of regels), kosten per taak, een totaal-anker per gemeente-nulmeting, <=15 aanbevelingen, contract-rakers achteraan', model: 'fable' },
  ],
}

// args = { stap: 'droog' | 'audit' | undefined, scratch: '<map>', run: '<uitvoermap van de gemeentebrede run>' }
const SCRATCH = (args && args.scratch) || '/home/martin/nlriochecker-onderzoek/2026-09-07-fable-product'
const RUN = (args && args.run) || 'uitvoer/04092026_slotrun'

const TAAKTABEL = `
| # | Taak | Rol | Frequentie | Kostenkant | nlrio-hefboom |
|---|---|---|---|---|---|
| 1 | Aanlevering (RibX/GWSW) van bureau/aannemer inlezen, op kwaliteit controleren, beheerregister bijwerken | databeheerder | na elke inspectieronde/oplevering | aanlevering bureau EUR 120/u; controle intern EUR 100/u | kern: de toets zelf |
| 2 | Nulmeting/gegevenskwaliteit toetsen bij de GWSW-server voor uitwisseling of modelgebruik | databeheerder | voor elke uitwisseling/model | intern EUR 100/u | laag 1 (nulmeting inlezen) |
| 3 | Brongegevens/revisies continu actueel houden + kwaliteit labelen (incl. BGT-oppervlakkenkaart) | databeheerder | continu / periodiek | intern EUR 100/u | herhaalde toets, diff t.o.v. vorige |
| 4 | Herstelopdrachten/prioritering uit de bevindingen naar het beheerpakket (Kikker/Obsurv/GBI) | rioolbeheerder | na elke toets | intern EUR 100/u | export -> werklijst |
| 5 | Rekenmodel actualiseren/kalibreren; geometrische/topologische datafouten opsporen voor doorrekenen | modelleur | bij revisies / periodiek | bureau of intern EUR 120/100/u | checks vangen modelbrekende datafouten |
| 6 | Jaarlijkse trend/rapportage voor Wrp en raad; benchmark tussen jaren/gemeenten | beleidsadviseur / bestuursadvisering | jaarlijks (Wrp-cyclus; MIP 1-3 jr) | intern EUR 100/u | vergelijk |
| 7 | Tweede gemeente van niets tot eerste rapport (PDOK-download, config, installatie) | databeheerder / projectleider | eenmalig per gemeente | intern EUR 100/u | doorlooptijd-hefboom |`

const CONTEXT = `
Repo-root (cwd): /home/martin/Development/nlriochecker  (Python 3.12+, src-layout, uv, versie 0.3.1, dev=1767485).
Package: src/nlriochecker/ — toetst de datakwaliteit van vrijvervalriolering: (1) de GWSW-nulmeting
(SHACL-rapporten, CSV) inlezen en analyseren (analyseer, dekking, vergelijk), (2) eigen checks op de
GWSW-OroX/TTL-dataset conform het checkregister v0.9 (TOP/NET/HGT/ATTR/RVZ/ADM/EXT), (3) EXT-checks
tegen BGT/BAG/AHN/NWB. Vier uitvoervormen uit een schrijver: Markdown, CSV (;-gescheiden), GeoPackage
(objectlagen met status rood/oranje/groen/grijs/geaccepteerd en popup), JSON (docs/json-schema.md).
De leeslaag (OroX inlezen, graaf, geometrie, ontologie, cache) is de aparte package gwsw-orox-helpers.

DEZE SWARM GAAT OVER HET PRODUCT, NIET OVER DE CODE. De vraag is niet "waar zit een defect" maar
"welke terugkerende taak van een beheerder kost vandaag uren of dagen en wordt met welke ontbrekende
functie minuten". Een lens loopt een echte taak door zoals de beheerder dat doet, met de klok erbij,
en zegt wat er mist. Een defect dat seconden kost is hier hooguit een voetnoot; een product-gat dat
dagen kost is de hoofdzaak: "liever een hefboom van dagen dan een defect van seconden".

DOEL VAN DE AUTEUR (manifesto.md, 93 r — lees hem eerst volledig): de digitale transformatie van de
rioleringssector 10-100x versnellen. De meetlat is de doorlooptijd van een terugkerende taak van een
rioolbeheerder: dagen -> minuten, met een controleerbare uitkomst. Beslisregels bij conflict, van
boven naar beneden: 1 correctheid en herleidbaarheid, 2 standaarden (GWSW voorop), 3 toetsbaarheid
aan metingen, 4 herbruikbaarheid, 5 begrijpelijkheid voor de eindgebruiker, 6 ontwikkelsnelheid,
7 elegantie. De primaire gebruiker is de DATABEHEERDER (taken 1-3); de MODELLEUR is een aparte
begunstigde (datakwaliteit is de poort voor het model); de BESTUURDER ziet een getal.

DE ZEVEN TERUGKERENDE PRAKTIJKTAKEN (uit het RIONED-corpus, grill-sessie 2026-09-06):
${TAAKTABEL}

TARIEVEN VOOR DE 10x-MEETLAT: extern bureau EUR 120/uur, intern EUR 100/uur. Elke taak-inspanning
(uren) -> euro's; de rol bepaalt het tarief. Meet PER TAAK en (de regisseur) EEN TOTAAL-ANKER per
gemeente-nulmeting. Het corpus geeft rollen en frequenties, zelden uren per taak: schat de uren MET
bron en markeer de schatting als aanname (kostenNu.aanname=true). Een aanname zonder bron telt niet.

LEES EERST, een keer volledig met Read (geen giswerk): manifesto.md, docs/gebruik.md (530 r: de vier
subcommando's, uitvoerbestanden, wat er in de GeoPackage staat), CONTEXT.md (begrippen). Van
docs/architectuur.md (514 r) alleen de secties die je lens raakt; data/checkregister-gwsw-nulmeting-
v0_9.md (415 r) volledig voor de modelleur-lens; docs/agents/analyse-harness.md (189 r) VOOR je een
telling of scratch-script tegen de dataset schrijft (dataset-API, verrassende maar correcte
aantallen, drempelrecept). docs/beslislog.md (5000+ r) alleen gericht met grep op BO-nummer of
trefwoord. docs/json-schema.md en docs/brutis-exportbevindingen.md zijn de bestaande gedachten over
een mutatie-/terugkoppelformaat naar Kikker/BrutIS (nog niet gebouwd). Geen cd; werkmap is de
repo-root. Wijzig NIETS in de repo; alles wat je schrijft gaat naar ${SCRATCH}/<lens>/ (maak de map
aan). Draai NIET de testsuite.

DE ECHTE UITVOER. De gemeentebrede run staat in ${RUN}/ (De Wolden-Hoogeveen, 23.485 knopen /
23.440 strengen, 161.158 meldingen, nlriochecker 0.3.1, 04-09-2026): bevindingen.md (49.660 regels),
bevindingen.csv (161.159 regels), bevindingen.json, dq_dewoldenhoogeveen_orox_20260904.gpkg.
Nieuwer is uitvoer/07092026_slotrun_F (161.661 meldingen, dev na #139-#172); noem het als je het
leest. Lees de uitvoer zoals de beheerder dat doet: welke sectie eerst, hoe lang duurt het om een
werklijst te vinden, wat is onleesbaar op deze schaal. Citeer regels uit de echte uitvoer (met
bestand:regel). Tel eerst op bestaande uitvoer voordat je een nieuwe run van minuten start.
Het getrackte voorbeeld draait in seconden (Koekangerveld, 374 meldingen) en is het speelgoed, niet
de meetlat:
  uv run nlriochecker toets --dataset voorbeelden/koekangerveld/koekangerveld_orox.ttl
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_Hyd.csv
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_MdsPlan.csv
    --shacl voorbeelden/koekangerveld/gwsw_shacl_report_MdsProj.csv
    --studiegebied voorbeelden/koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg
    --bronnen voorbeelden/koekangerveld --output ${SCRATCH}/<lens>/voorbeeld
De gemeentebrede run (minuten, tot ~4 GB; ALLEEN achter flock ${SCRATCH}/meet.lock, de machine
heeft 4 cores en 15 GB en andere lenzen draaien tegelijk):
  uv run nlriochecker toets --dataset data/gwsw_orox_ttl/dewoldenhoogeveen_orox.ttl
    --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_Hyd.csv
    --shacl data/shacl_nulmeting/gwsw_shacl_report_conformiteit_MdsPlan.csv
    --shacl data/shacl_nulmeting/gwsw_shacl_report_MdsProj.csv
    --projectconfig configs/dewoldenhoogeveen.toml --bronnen data/gis_dewoldenhoogeveen
    --output ${SCRATCH}/<lens>/dewolden

SECTORBRONNEN.
(a) RIONED Kennisbank Stedelijk Water — LOKAAL EN AFGESCHERMD. Vier Markdown-exports, samen 4,3 MB
(53.000 regels), dus NIET volledig in te lezen: grep op '^# ' voor de hoofdstukkoppen en op
trefwoorden (GWSW, RibX, revisie, beheerregister, inspectie, nulmeting, rekenmodel, kalibratie,
Wrp, benchmark, assetmanagement, BGT), lees dan alleen de secties die je nodig hebt (Read met
offset/limit):
  /home/martin/Development/rioned/rioned_instandhouden_md/_corpus_instandhouden_volledig.md (10.163 r)
  /home/martin/Development/rioned_2/rioned_onderzoek-uitvoeren_md/_corpus_onderzoek-uitvoeren_volledig.md (20.846 r)
  /home/martin/Development/rioned/rioned_ontwerpen_md/_corpus_ontwerpen_volledig.md (6.606 r)
  /home/martin/Development/rioned_2/rioned_organiseren-en-afwegen_md/_corpus_organiseren-en-afwegen_volledig.md (15.750 r)
HARDE REGEL: de INHOUD van dit corpus mag NOOIT letterlijk in de repo, in een uitvoerbestand, in
${SCRATCH} of in een GitHub-issue landen. Verwijzen (bestand:regel of hoofdstukkop) en KORT
PARAFRASEREN met bronvermelding mag; citeren niet — ook niet een halve zin. Een bevinding met een
letterlijk corpusfragment wordt door de skepticus afgekeurd en uit het resultaat verwijderd.
(b) Brede internetsearch voor GWSW-terugkoppeling/toetsing (apps.gwsw.nl, data.gwsw.nl) en de
beheerpakketten Kikker (Antea), Obsurv (Sweco), GBI (Antea): welke import-/uitwisselformaten
(GWSW-OroX, RibX, GWSW.hyd, SUF-RIB, CSV/GeoPackage) en welke terugkoppelroute een bevindingenlijst
in het pakket krijgt. Laad WebSearch en WebFetch eerst met ToolSearch("select:WebSearch,WebFetch").
Web-bronnen mag je wel citeren, met URL en datum; de auteur weegt de bron achteraf.

WAT AL BEKEND IS (niet opnieuw als nieuw melden; wel voortbouwen en het bewijs verscherpen):
- Issues #1-#172 zijn gesloten op #136 (1.7-vormtabel, needs-info) en #164 na. #164 is de
  geparkeerde contractwens 'vergelijk op twee bevindingen.json (melding_id-diff over alle meldingen)
  en de bestandsnaampoort als voorbehoud i.p.v. blokkade' — bekend; wat hier wel telt is de MAAT van
  die hefboom (uren x tarief, welke taak) en wat er daarnaast nog mist voor taak 3 en 6.
- De product-lens van de codeswarm van 05-09 (~/nlriochecker-onderzoek/2026-09-05-fable-swarm/,
  audit-ruw.json soort=product, plan.json hefbomen10x) vond zeven punten: dekking zonder --dataset
  zonder voorbehoud, de naampoort van vergelijk, het AHN-raster (gedaan: #168, tiles 256), de
  oninstalleerbare release-wheel (gedaan: #158), vergelijk zonder eigen checks (#164), een tweede
  gemeente kopieert ~540 regels config (gedaan/verwerkt in de reeks #141-#172; controleer met
  gh issue view), en ;-CSV met .-decimaal in Nederlandse Excel (vermoeden). Die lens was dun door:
  verkeerde bewijsstandaard, persona's zonder benoemde taak, nul sectorkennis, plafond 5, alleen
  Koekangerveld. Deze swarm herstelt precies dat; herhaal die punten niet als nieuw, maar zeg wel
  wat ze op de taak-meetlat waard zijn als dat nog nergens staat.
- Controleer voor je iets als 'ontbreekt' meldt: gh issue list --state all --search '<trefwoord>'.

BEVROREN CONTRACTEN (raaktContract=true, wel opnemen, wel labelen): de CLI (analyseer/dekking/
vergelijk/toets en hun opties); de JSON-envelop (docs/json-schema.md); de GeoPackage-structuur
(lagen, kolommen, status, popup, gwsw_run); de CSV-kolommen; checks.toml (Meetbereik verplicht);
check-ID's stabiel; de leeslaag-API. Een nieuwe uitvoervorm, laag, kolom of CLI-optie is per
definitie raaktContract=true — dat is geen bezwaar, alleen een eerlijk label: de auteur beslist.
GWSW IS LEIDEND: een terugkoppel- of exportformaat moet GWSW-begrippen dragen; voor je beweert dat
een klasse of property niet bestaat, grep de gebundelde ontologie (pad via
uv run python -c "from gwsw_orox_helpers.bronnen import gebundelde_ontologie as g; print(g())").

BEWIJSSTANDAARD (anders dan de codeswarm; een ontbrekende functie is hier juist het onderwerp):
- soort 'product-gat': bewijs is een DOORLOPEN TAAK — de stappen die de beheerder vandaag zet, elk
  met tijd in minuten (schrijf per stap 'date +%T' in je logboek onder ${SCRATCH}/<lens>/ en tel
  op), met citaten uit de echte uitvoer (${RUN}/…: bestand:regel) of uit het commando, plus de
  huidige kosten (kostenNu: uren x tarief, met bron of gemarkeerde aanname) en de kosten straks.
  Jouw agent-minuten zijn een ONDERGRENS voor de mens-minuten: schat de mens-tijd apart en zeg hoe
  (bv. 49.660 regels Markdown lezen is geen agent-taak van 1 minuut maar een mensdag).
- soort 'sector': bewijs is een sectorbron met verwijzing (corpus bestand:regel of hoofdstukkop,
  geparafraseerd; of URL met datum) die zegt wat de sector vandaag doet, wie het doet en hoe vaak.
- soort 'defect': alleen als hij een taak uit de tabel aantoonbaar blokkeert; dan met repro
  (pytest of commando, uitvoer geplakt) in ${SCRATCH}/<lens>/. Anders hoort hij in een issue, niet
  hier.
- zekerheid 'aangetoond' = doorlopen en geklokt, of bron gelezen; anders 'vermoeden'.
- hefboomgrootte = wat de ingreep de beheerder per keer scheelt: 'dagen', 'uren', 'minuten' of
  'seconden'. Plafond 8 per lens; liever 3 hefbomen van dagen dan 8 van seconden.
Benoem ook wat GOED is (sterkePunten, met citaat uit de uitvoer): de regisseur moet weten wat al
werkt en niet aangeraakt mag worden.`

const DIMENSIONS = [
  {
    key: 'databeheerder-aanlevering',
    skills: 'SKILLS voor deze lens: laad eerst python-library-complete:building-python-clis (CLI-ergonomie: wat een gebruiker ziet, exit codes, voortgang) en python-library-complete:shipping-across-surfaces (hetzelfde feit op elk oppervlak: rapport, CSV, GeoPackage, JSON).',
    prompt: `LENS: DATABEHEERDER-AANLEVERING — taken 1, 2 en 3, plus taak 4 (export -> werklijst). Loop de keten door zoals de databeheerder na een inspectieronde: (1) een aanlevering (RibX/GWSW-OroX) binnenkrijgen en de toets draaien — welke bestanden, vlaggen en kennis heeft hij daarvoor nodig (docs/gebruik.md), en wat gebeurt er als hij er een mist; (2) de uitvoer van de GEMEENTEBREDE run openen (${RUN}/bevindingen.md, 49.660 regels; de CSV; de GeoPackage in QGIS in woorden) en binnen de klok een WERKLIJST maken: welke objecten eerst, per stelsel/wijk/aannemer, met de herstelhandeling erbij — hoe lang duurt dat en waar loopt het vast (te veel regels, geen prioriteit per object, geen samenvatting per stelsel, geen filter op 'wat is nieuw sinds de vorige aanlevering'); (3) die werklijst het beheerpakket in krijgen (Kikker/Obsurv/GBI: onderzoek welke import-/uitwisselformaten ze accepteren; lees docs/json-schema.md en docs/brutis-exportbevindingen.md over het nog te bouwen mutatieformaat) en de aanlevering terugkoppelen aan het bureau in GWSW-termen; (4) de nulmeting bij de GWSW-server (apps.gwsw.nl) — wat doet analyseer/dekking al en wat blijft handwerk; (5) na herstel de toets herhalen en het verschil zien (#164 is bekend: meet wat het waard is en wat er DAARNAAST nog mist voor 'wat is nieuw'). Reken per stap de uren x tarief van vandaag en van straks. Lever de hefbomen die de keten van dagen naar minuten brengen.`,
  },
  {
    key: 'modelleur-poort',
    skills: 'SKILLS voor deze lens: laad eerst mattpocock-skills:domain-modeling (begrippenmodel: welke datafout is welke modelfout; CONTEXT.md) en python-library-complete:reporting-derived-metrics (een oordeel uit tellingen dat eerlijk zegt wat niet gemeten is).',
    prompt: `LENS: MODELLEUR-POORT — taak 5. De modelleur (bureau EUR 120/u of intern EUR 100/u) actualiseert of kalibreert het hydraulisch rekenmodel en verliest vandaag uren tot dagen aan datafouten die pas bij het doorrekenen opduiken. Stel eerst met bron vast (RIONED-corpus: onderzoek-uitvoeren en ontwerpen, grep op rekenmodel/kalibratie/hydraulisch/BOB/GWSW.hyd; plus web) WELKE datafouten een model breken of vervuilen: losse strengen en putten, verkeerde stroomrichting, BOB-sprongen en tegenschot, ontbrekende diameters/hoogten/materiaal, dubbele knopen, foute stelselkoppeling, overstortdrempels, gemalen zonder capaciteit, onjuist afvoerend oppervlak (BGT). Leg die lijst naast het checkregister (data/checkregister-gwsw-nulmeting-v0_9.md) en de gemeentebrede uitvoer (${RUN}): welke modelbrekende fout vangt welke check (TOP/NET/HGT/ATTR/RVZ) en hoe vaak op De Wolden (tel in bevindingen.csv), welke vangt niets, en welke vangt hem maar zo dat de modelleur er niets mee kan (geen strenglijst, geen 'modelklaar ja/nee' per stelsel, geen export in het formaat dat het modelpakket leest). Loop de taak door: van bevindingen.csv naar een lijst 'deze N objecten eerst herstellen voor het model klopt' — klok erbij. Wat mist om de dataset MODELKLAAR op te leveren (een modelleur-samenvatting, een poortoordeel per stelsel, een export)? Reken de uren van vandaag en straks; markeer aannames.`,
  },
  {
    key: 'bestuurder-en-trend',
    skills: 'SKILLS voor deze lens: laad eerst python-library-complete:reporting-derived-metrics (een stuurgetal uit 161.158 meldingen zonder te liegen over wat niet gemeten is) en dataviz (alleen voor de vraag welke vorm een bestuurder in een oogopslag leest; bouw geen grafiek).',
    prompt: `LENS: BESTUURDER-EN-TREND — taak 6. De beleidsadviseur maakt jaarlijks (Wrp-cyclus; MIP 1-3 jaar) een rapportage voor college en raad en wil EEN stuurgetal per gemeente met een trend, plus een benchmark tussen jaren en tussen gemeenten. Stel met bron vast wat de sector daarvoor vandaag doet (RIONED-corpus organiseren-en-afwegen: grep op Wrp, benchmark, assetmanagement, prestatie-indicator, kwaliteit gegevens; plus web: RIONED-benchmark, GWSW-nulmeting) en wat het kost. Loop de taak door op de gemeentebrede uitvoer (${RUN}): probeer uit bevindingen.md/csv/json en de GeoPackage-status (rood/oranje/groen/grijs/geaccepteerd, docs/gebruik.md 'status') binnen de klok EEN getal te maken dat een wethouder begrijpt en dat volgend jaar herhaalbaar is — lukt dat, wat moet je daarvoor met de hand doen, en is het eerlijk (systemische meldingen, onderdrukking, deelset, wat niet bekeken is)? Beoordeel vergelijk (docs/gebruik.md, comparison.py, reporting.py) als stuurinstrument: wat kan het (SHACL-nulmeting op vormniveau), wat niet (#164 bekend: de eigen checks; geen gebieden; geen tweede gemeente), en wat moet het kunnen voor jaar-op-jaar en gemeente-op-gemeente. Welke vorm (een tabel van vijf regels? een kaart? een cijfer 1-10 per stelsel?) leest de bestuurder in een oogopslag — met bron waarom. Reken uren x tarief nu en straks.`,
  },
  {
    key: 'tweede-gemeente',
    skills: 'SKILLS voor deze lens: laad eerst mattpocock-skills:wizard (welke stappen kan alleen een mens zetten, welke zijn te automatiseren) en python-library-complete:packaging-python-libraries (installatie vanuit een release, zonder de repo).',
    prompt: `LENS: TWEEDE-GEMEENTE — taak 7. De databeheerder of projectleider van gemeente nummer twee wil van niets tot het eerste rapport, en de klok loopt. Doe het ECHT, met 'date +%T' per stap in ${SCRATCH}/tweede-gemeente/logboek.md: (1) installatie in een schone omgeving buiten de repo (uv venv in ${SCRATCH}/tweede-gemeente/, installeer vanuit de laatste GitHub-release of git-tag zoals README/docs/gebruik.md het voorschrijven; het referentiemateriaal van 05-09 staat in ~/nlriochecker-onderzoek/2026-09-05-fable-swarm/product-hefboom/ (install.log, venv-install/, voorbeeld_cleaninstall/) — #158 is daarna gedaan, controleer of het nu wel lukt); (2) de invoer bijeenbrengen: OroX-export uit het beheerpakket (wat moet de gemeente aan de leverancier vragen), SHACL-rapporten van apps.gwsw.nl (hoe, hoe lang), de externe bronnen van PDOK (BGT, BAG, AHN, NWB, CBS-buurten: welke download, welk formaat, welke omvang, welke bewerking — lees docs/gebruik.md 'Externe bronnen', configs/dewoldenhoogeveen.toml en data/gis_dewoldenhoogeveen/ als voorbeeld; download alleen wat klein is en schat de rest met bron, bv. de PDOK-documentatie); (3) de projectconfig maken (welke sleutels MOET een tweede gemeente zetten, welke zijn drempelkeuzes die zij niet kan maken zonder hulp); (4) de eerste run en het lezen van het rapport. Wat is automatiseerbaar (een 'nlriochecker init <gemeente>' die PDOK haalt en de config schrijft — raaktContract=true), wat blijft mensenwerk (leveranciersvraag, GWSW-upload), en wat kost het nu en straks in uren x EUR 100? Vergelijk met wat een bureau daarvoor rekent als je daar een bron voor vindt.`,
  },
  {
    key: 'sector-gat',
    skills: `SKILLS voor deze lens: laad eerst mattpocock-skills:research (methode: primaire bronnen, elke claim met verwijzing) — maar schrijf de bevindingen naar ${SCRATCH}/sector-gat/, NIET in de repo. Laad WebSearch en WebFetch met ToolSearch("select:WebSearch,WebFetch").`,
    prompt: `LENS: SECTOR-GAT — wat doet de sector vandaag voor dezelfde zeven taken, wie doet het (bureau of intern), hoe lang en voor hoeveel, en welke functie ontbreekt in nlriochecker om dat te vervangen. Bronnen: het RIONED-corpus (alle vier bestanden, via grep en gerichte secties; verwijs en parafraseer, citeer NOOIT) voor rollen, frequenties, werkwijzen en waar het corpus uren of kosten noemt; het web voor de GWSW-toets- en terugkoppelroute (apps.gwsw.nl: wat levert item_validate_shacl, wat doet een gemeente met het rapport), de beheerpakketten Kikker, Obsurv en GBI (import-/uitwisselformaten, of ze een externe bevindingenlijst kunnen importeren, of ze zelf een kwaliteitstoets hebben), RibX en GWSW.hyd, en wat adviesbureaus voor een 'datakwaliteitsscan' of 'nulmeting riolering' rekenen (offerte-indicaties, aanbestedingen, RIONED-publicaties over kosten van gegevensbeheer). Lever per taak uit de tabel: de huidige werkwijze in de sector met bron, de geschatte uren en het tarief (aanname gemarkeerd), en het GAT: welke concrete functie in nlriochecker die werkwijze vervangt of halveert — of de vaststelling, met bron, dat de sector dit al goedkoop oplost en nlriochecker hier geen hefboom heeft. Een eerlijke 'geen hefboom' met bron telt als bevinding. Sluit af met de drie grootste sectorhefbomen in euro's per gemeente per jaar.`,
  },
]

const KOSTEN = {
  type: 'object', additionalProperties: false,
  required: ['uren', 'rol', 'tariefEuroPerUur', 'euro', 'bron', 'aanname'],
  properties: {
    uren: { type: 'number' },
    rol: { type: 'string', description: 'databeheerder, rioolbeheerder, modelleur, beleidsadviseur, projectleider of bureau' },
    tariefEuroPerUur: { type: 'integer', enum: [100, 120] },
    euro: { type: 'number', description: 'uren x tarief' },
    bron: { type: 'string', description: 'corpus bestand:regel of hoofdstukkop (geparafraseerd), URL met datum, of je eigen klok (logboekpad)' },
    aanname: { type: 'boolean', description: 'true als de uren geschat zijn en niet uit de bron of de klok komen' },
  },
}

const RECS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['bevindingen', 'sterkePunten', 'logboek'],
  properties: {
    logboek: { type: 'string', description: 'pad van je stappenlogboek met date +%T per stap onder de werkmap' },
    sterkePunten: { type: 'array', items: { type: 'string' }, description: 'wat aantoonbaar al werkt voor de beheerder, met citaat uit de echte uitvoer (bestand:regel) of commando' },
    bevindingen: {
      type: 'array', maxItems: 8,
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'soort', 'taak', 'probleem', 'bewijs', 'zekerheid', 'hefboomgrootte', 'kostenNu', 'kostenStraks', 'ontbrekendeFunctie', 'raaktContract', 'bestanden'],
        properties: {
          title: { type: 'string' },
          soort: { type: 'string', enum: ['product-gat', 'sector', 'defect'] },
          taak: { type: 'array', items: { type: 'integer', minimum: 1, maximum: 7 }, description: 'taaknummers uit de tabel' },
          probleem: { type: 'string', description: 'wat de beheerder vandaag doet en waar het vastloopt, concreet' },
          bewijs: { type: 'string', description: 'de doorlopen stappen met minuten en citaten uit de echte uitvoer (bestand:regel), of de sectorbron (geparafraseerd, met verwijzing), of de repro' },
          zekerheid: { type: 'string', enum: ['aangetoond', 'vermoeden'] },
          hefboomgrootte: { type: 'string', enum: ['dagen', 'uren', 'minuten', 'seconden'], description: 'wat de ingreep de beheerder per keer scheelt' },
          kostenNu: KOSTEN,
          kostenStraks: KOSTEN,
          ontbrekendeFunctie: { type: 'string', description: 'de kleinste functie die het gat dicht: commando, optie, uitvoervorm, laag, samenvatting' },
          raaktContract: { type: 'boolean' },
          bestanden: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['isEcht', 'taakBevestigd', 'kostenBewijsGecontroleerd', 'eigenKostenNu', 'grootsteHefboom', 'hefboomgrootte', 'geenCorpusLek', 'additief', 'redenering'],
  properties: {
    isEcht: { type: 'boolean', description: 'true alleen als jij de taak en de huidige kosten zelf bevestigde (bron gelezen, stappen nagelopen of de uitvoer zelf bekeken)' },
    taakBevestigd: { type: 'boolean', description: 'bestaat deze taak zo in de sector (corpus/web) en raakt de bevinding hem echt' },
    kostenBewijsGecontroleerd: { type: 'boolean', description: 'heb je de bron voor uren en tarief zelf gelezen of de klok zelf nagelopen' },
    eigenKostenNu: { type: 'string', description: 'jouw eigen schatting van de huidige kosten (uren x tarief) met bron, onafhankelijk van de vinder' },
    grootsteHefboom: { type: 'string', enum: ['ja', 'nee', 'onbeslist'], description: 'is dit binnen zijn taak de grootste hefboom, of is er een grotere die de vinder miste (noem hem in redenering)' },
    hefboomgrootte: { type: 'string', enum: ['dagen', 'uren', 'minuten', 'seconden'], description: 'jouw eigen inschatting, niet die van de vinder' },
    geenCorpusLek: { type: 'boolean', description: 'false als de bevinding een letterlijk fragment uit het RIONED-corpus bevat' },
    additief: { type: 'boolean', description: 'te bouwen zonder een bevroren contract of de leeslaag-API te breken' },
    redenering: { type: 'string' },
  },
}

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['productOordeel', 'hefbomen10x', 'perTaak', 'totaalAnker', 'aanbevelingen', 'sectorNoot', 'themas', 'slotnoot'],
  properties: {
    productOordeel: {
      type: 'object', additionalProperties: false,
      required: ['cijfer', 'sterk', 'zwak', 'richting10'],
      properties: {
        cijfer: { type: 'integer', minimum: 1, maximum: 10, description: '10 = elke taak uit de tabel in minuten met een controleerbare uitkomst' },
        sterk: { type: 'array', items: { type: 'string' }, description: 'wat al werkt en bewaard moet blijven, met citaat' },
        zwak: { type: 'array', items: { type: 'string' }, description: 'de taken waar de beheerder nog dagen kwijt is' },
        richting10: { type: 'string' },
      },
    },
    hefbomen10x: {
      type: 'array', maxItems: 6, description: 'de ingrepen die de doorlooptijd van een taak het meest verkorten; nu en straks in minuten, euro of regels',
      items: {
        type: 'object', additionalProperties: false,
        required: ['hefboom', 'taak', 'nu', 'straks', 'factor', 'waarom', 'rangen', 'raaktContract'],
        properties: {
          hefboom: { type: 'string' },
          taak: { type: 'array', items: { type: 'integer', minimum: 1, maximum: 7 } },
          nu: { type: 'string', description: 'gemeten of bebrond: minuten, euro of regels, met de bron' },
          straks: { type: 'string', description: 'na de ingreep, in dezelfde eenheid' },
          factor: { type: 'string', description: 'nu/straks als getal, bv. "12x" of "onbekend"' },
          waarom: { type: 'string' },
          rangen: { type: 'array', items: { type: 'integer' }, description: 'de aanbevelingsrangen die deze hefboom samen vormen' },
          raaktContract: { type: 'boolean' },
        },
      },
    },
    perTaak: {
      type: 'array', minItems: 7, maxItems: 7, description: 'een regel per taak uit de tabel, in volgorde 1-7',
      items: {
        type: 'object', additionalProperties: false,
        required: ['taak', 'rol', 'frequentiePerJaar', 'nuUren', 'tariefEuroPerUur', 'nuEuroPerJaar', 'straksUren', 'straksEuroPerJaar', 'bron', 'aanname'],
        properties: {
          taak: { type: 'integer', minimum: 1, maximum: 7 },
          rol: { type: 'string' },
          frequentiePerJaar: { type: 'number', description: 'hoe vaak per jaar; taak 7 eenmalig = 1' },
          nuUren: { type: 'number', description: 'uren per keer, vandaag' },
          tariefEuroPerUur: { type: 'integer', enum: [100, 120] },
          nuEuroPerJaar: { type: 'number' },
          straksUren: { type: 'number', description: 'uren per keer na de hefbomen' },
          straksEuroPerJaar: { type: 'number' },
          bron: { type: 'string' },
          aanname: { type: 'boolean' },
        },
      },
    },
    totaalAnker: {
      type: 'object', additionalProperties: false,
      required: ['nuEuroPerJaar', 'straksEuroPerJaar', 'factor', 'onderbouwing', 'aanname'],
      properties: {
        nuEuroPerJaar: { type: 'number', description: 'som van perTaak.nuEuroPerJaar: wat een gemeente-nulmeting vandaag per jaar kost' },
        straksEuroPerJaar: { type: 'number' },
        factor: { type: 'number', description: 'nu/straks' },
        onderbouwing: { type: 'string', description: 'het ene getal voor de bestuurder, in een zin, met de zwakste aanname erbij' },
        aanname: { type: 'boolean' },
      },
    },
    aanbevelingen: {
      type: 'array', maxItems: 15,
      items: {
        type: 'object', additionalProperties: false,
        required: ['rang', 'titel', 'soort', 'taak', 'lens', 'hefboomgrootte', 'bewijs', 'ontbrekendeFunctie', 'winst', 'additief', 'raaktContract', 'inspanning', 'hangtAf', 'bestanden'],
        properties: {
          rang: { type: 'integer' },
          titel: { type: 'string' },
          soort: { type: 'string', enum: ['product-gat', 'sector', 'defect'] },
          taak: { type: 'array', items: { type: 'integer', minimum: 1, maximum: 7 } },
          lens: { type: 'string' },
          hefboomgrootte: { type: 'string', enum: ['dagen', 'uren', 'minuten', 'seconden'] },
          bewijs: { type: 'string' },
          ontbrekendeFunctie: { type: 'string' },
          winst: { type: 'string', description: 'uren of euro per keer en per jaar, met de bron of aanname' },
          additief: { type: 'boolean' },
          raaktContract: { type: 'boolean' },
          inspanning: { type: 'string', enum: ['S', 'M', 'L', 'XL'] },
          hangtAf: { type: 'string', description: 'rang(en) waar dit van afhangt, of leeg' },
          bestanden: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    sectorNoot: { type: 'string', description: 'wat de sector vandaag doet voor dezelfde vraag (bureau, dagen, euro) met bron; waar nlriochecker geen hefboom heeft' },
    themas: { type: 'array', items: { type: 'string' } },
    slotnoot: { type: 'string', description: 'contract-rakers en auteursbeslissingen; wat een agent additief mag oppakken; de aanbevolen volgorde; de zwakste aannames in de kostenrekening' },
  },
}

// Auditstap als losse functie: byte-identieke prompt/opts, zodat een latere volledige run
// met resumeFromRunId de auditresultaten uit de cache haalt.
const auditeer = (d) => agent(
  `${CONTEXT}\n\n${d.skills}\n\n${d.prompt}\n\nLever maximaal 8 bevindingen; liever 3 doorlopen en geklokte hefbomen van dagen dan 8 vermoedens van seconden. Elke bevinding draagt kostenNu en kostenStraks met bron of gemarkeerde aanname. Noem ook de sterke punten. Werkmap voor logboek, scratch-scripts en uitvoer: ${SCRATCH}/${d.key}/ (maak hem aan; nooit letterlijke corpustekst erin).`,
  { label: `audit:${d.key}`, phase: 'Audit', model: 'fable', schema: RECS_SCHEMA, effort: 'high' },
)

phase('Audit')
log(`Fable-productswarm nlriochecker: ${DIMENSIONS.length} lenzen langs 7 taken, uitvoer ${RUN}, werk in ${SCRATCH}`)

if (args && args.stap === 'droog') {
  // Geen enkele agent: alleen de opbouw tonen, als parse- en logica-check.
  return {
    stap: 'droog', run: RUN, scratch: SCRATCH,
    lenzen: DIMENSIONS.map((d) => ({ key: d.key, skills: d.skills, promptTekens: CONTEXT.length + d.skills.length + d.prompt.length })),
    plafondPerLens: RECS_SCHEMA.properties.bevindingen.maxItems,
    maxAanbevelingen: PLAN_SCHEMA.properties.aanbevelingen.maxItems,
  }
}

if (args && args.stap === 'audit') {
  const ruw = await parallel(DIMENSIONS.map((d) => () => auditeer(d).then((r) => ({ lens: d.key, ...(r || { bevindingen: [], sterkePunten: [], logboek: '' }) }))))
  const n = ruw.filter(Boolean).reduce((s, r) => s + r.bevindingen.length, 0)
  log(`Audit klaar: ${n} ruwe bevindingen, geen verify (stap=audit)`)
  return { stap: 'audit', ruw: ruw.filter(Boolean) }
}

const reviewed = await pipeline(
  DIMENSIONS,
  auditeer,
  (review, d) => parallel(((review && review.bevindingen) || []).map((r, i) => () =>
    agent(
      `${CONTEXT}\n\nJij bent de SKEPTICUS van de productswarm (lens ${d.key}). Je vraag is NIET "is het echt" — een ontbrekende functie is hier het onderwerp — maar: (a) IS DIT DE GROOTSTE HEFBOOM binnen deze taak, of miste de vinder een grotere; (b) KLOPT HET BEWIJS VOOR DE HUIDIGE KOSTEN (uren x tarief): lees de sectorbron zelf (corpus: verwijzing nalopen, parafraseren, nooit citeren; web: URL openen), loop de geklokte stappen na in het logboek en in de echte uitvoer (${RUN}), en maak een EIGEN kostenschatting met bron; (c) bestaat de taak zo in de sector; (d) is het al gedaan of bekend (gh issue list --state all --search; #164; de product-lens van 05-09) en zegt de vinder dan iets nieuws over de maat; (e) bevat de bevinding een letterlijk corpusfragment (dan geenCorpusLek=false, ongeacht de rest); (f) is de fix additief.\n\nTITEL: ${r.title}\nSOORT: ${r.soort}; TAAK: ${JSON.stringify(r.taak)}; HEFBOOMGROOTTE (vinder): ${r.hefboomgrootte}; zekerheid=${r.zekerheid}; raaktContract=${r.raaktContract}\nPROBLEEM: ${r.probleem}\nGECLAIMD BEWIJS: ${r.bewijs}\nKOSTEN NU (vinder): ${JSON.stringify(r.kostenNu)}\nKOSTEN STRAKS (vinder): ${JSON.stringify(r.kostenStraks)}\nONTBREKENDE FUNCTIE: ${r.ontbrekendeFunctie}\nLOGBOEK VINDER: ${review.logboek}\n\nWerkmap: ${SCRATCH}/verify-${d.key}-${i}/. isEcht=true ALLEEN als jij taak en huidige kosten zelf bevestigde; hefboomgrootte is jouw eigen oordeel.`,
      { label: `verify:${d.key}:${i}`, phase: 'Verify', model: 'fable', schema: VERDICT_SCHEMA, effort: 'medium' },
    ).then((v) => (v ? { ...r, lens: d.key, verdict: v } : null)),
  )).then((vs) => ({ lens: d.key, sterkePunten: (review && review.sterkePunten) || [], logboek: (review && review.logboek) || '', items: vs })),
)

const alle = reviewed.filter(Boolean)
const items = alle.flatMap((r) => r.items).filter(Boolean)
const corpusLek = items.filter((x) => x.verdict && !x.verdict.geenCorpusLek)
const overleefd = items.filter((x) => x.verdict && x.verdict.isEcht && x.verdict.geenCorpusLek)
const gesneuveld = items.length - overleefd.length
const sterk = alle.flatMap((r) => r.sterkePunten.map((s) => `[${r.lens}] ${s}`))
if (corpusLek.length) log(`LET OP: ${corpusLek.length} bevinding(en) verwijderd wegens letterlijke corpustekst: ${corpusLek.map((x) => `${x.lens}/${x.title}`).join('; ')}`)
log(`Verify: ${overleefd.length} bevestigd, ${gesneuveld} afgevallen (waarvan ${corpusLek.length} corpuslek); ${sterk.length} sterke punten`)

phase('Regie')
const bundel = overleefd.map((x, i) => ({
  n: i + 1, lens: x.lens, soort: x.soort, taak: x.taak, titel: x.title, probleem: x.probleem, bewijs: x.bewijs,
  hefboomgrootteVinder: x.hefboomgrootte, hefboomgrootteSkepticus: x.verdict.hefboomgrootte,
  grootsteHefboom: x.verdict.grootsteHefboom, kostenNu: x.kostenNu, kostenStraks: x.kostenStraks,
  eigenKostenNuSkepticus: x.verdict.eigenKostenNu, ontbrekendeFunctie: x.ontbrekendeFunctie,
  bestanden: x.bestanden, additief: x.verdict.additief, raaktContract: x.raaktContract,
  verifyNoot: x.verdict.redenering,
}))

const plan = await agent(
  `${CONTEXT}\n\nJij bent de REGISSEUR van de productswarm. ${bundel.length} bevestigde bevindingen uit ${DIMENSIONS.length} lenzen:\n\n${JSON.stringify(bundel, null, 1)}\n\nSTERKE PUNTEN volgens de lenzen:\n${sterk.map((s) => `- ${s}`).join('\n')}\n\nLogboeken van de lenzen: ${alle.map((r) => `${r.lens}: ${r.logboek}`).join('; ')}.\n\nLees zelf manifesto.md en docs/gebruik.md en open zelf ${RUN}/bevindingen.md en de CSV zoals een beheerder; leun niet alleen op de lenzen. Geef een PRODUCTOORDEEL (cijfer 1-10: 10 = elke taak uit de tabel in minuten met een controleerbare uitkomst). Vul PERTAAK voor alle zeven taken: rol, frequentie per jaar, uren per keer nu en straks, tarief, euro per jaar nu en straks, bron, aanname — neem waar lenzen elkaar tegenspreken de best bebronde schatting en zeg dat. Tel op tot het TOTAALANKER: het ene getal per gemeente-nulmeting per jaar dat een bestuurder ziet, met de zwakste aanname erbij. Benoem de HEFBOMEN10X: de ingrepen die de doorlooptijd het meest verkorten, elk met nu en straks in minuten, euro of regels (gemeten of bebrond, geen gevoel), de factor, en de rangen die hem vormen. Ontdubbel (zelfde ontbrekende functie = een punt), fuseer waar lenzen dezelfde taak raken, rangschik de <=15 AANBEVELINGEN op hefboomgrootte x zekerheid x winst per jaar; per punt de kleinste functie die het gat dicht, inspanning en afhankelijkheden. Contract-rakers (nieuwe CLI-optie, uitvoervorm, laag, kolom, formaat) ACHTERAAN en eerlijk gelabeld: de auteur beslist. Zet in de SECTORNOOT wat de sector vandaag doet (bureau, dagen, euro, met bron) en waar nlriochecker geen hefboom heeft. Corpusregel geldt ook voor jou: verwijzen en parafraseren, nooit citeren. Slotnoot: auteursbeslissingen, wat een agent additief mag oppakken, de volgorde, en de zwakste aannames in de rekening.`,
  { label: 'regisseur:fable', phase: 'Regie', model: 'fable', schema: PLAN_SCHEMA, effort: 'high' },
)

return { bevestigd: overleefd.length, afgevallen: gesneuveld, corpusLek: corpusLek.length, sterkePunten: sterk, plan }
