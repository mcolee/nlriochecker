export const meta = {
  name: 'nlrio-swarm',
  description: 'Multi-lens review van nlriochecker; Opus-lenzen, Fable-regisseur levert <=25 aanbevelingen voor 10x beter',
  phases: [
    { title: 'Review', detail: '8 Opus-lens-agents beoordelen de package parallel' },
    { title: 'Verify', detail: 'adversariele Opus-verify + additief-vs-contract per aanbeveling' },
    { title: 'Regie', detail: 'Fable-regisseur rangschikt <=25 aanbevelingen', model: 'fable' },
  ],
}

const CONTEXT = `
Repo-root (cwd): /home/martin/nlriochecker  (Python 3.12+, src-layout, uv).
Package: src/nlriochecker/ (~24.5k LOC) — toetst de datakwaliteit van vrijvervalriolering
op de GWSW-nulmeting (SHACL-rapporten) en met eigen checks op de GWSW-OroX/TTL-dataset.
Grote modules (LOC): uitvoer/gpkg 1907, checks/attributen 1638, checks/topologie 1625,
uitvoer/bevindingen 1357, checks/extern 1307, checks/netwerk 1237, checks/randvoorzieningen
1158, checks/hoogten 1066, checks/administratief 768, checks/base 683, checkconfig 673,
checks/wegvakken 621, cli 610, externedata 602, studiegebied 585, uitvoer/melding 545.
Deps: click, geopandas, gwsw-orox-helpers, networkx, pandas, pydantic, rasterio, rdflib, shapely.

LEES EERST (geen giswerk): manifesto.md (missie/prioriteiten), docs/architectuur.md (engine +
uitvoer-interna), docs/gebruik.md (CLI/uitvoer), data/checkregister-gwsw-nulmeting-v0_9.md
(domeinregels). Onderzoek de code echt met Read/Grep/Bash in de repo voordat je oordeelt.

HARDE CONTEXTREGELS (staan in CLAUDE.md; overtreden = geen aanbeveling):
- GWSW IS LEIDEND. Bestaat een klasse/property in de gebundelde ontologie, dan bestaat het.
  Voor je beweert dat iets niet bestaat: grep de ontologie
  (uv run python -c "from gwsw_orox_helpers.bronnen import gebundelde_ontologie as g; print(g())").
  Scheid "bestaat de klasse" van "komen er instanties voor in deze dataset".
- De LEESLAAG is een APARTE package (gwsw-orox-helpers): OroX/TTL inlezen, graaf, geometrie,
  ontologie, cache, voortgang. Die API is BEVROREN — geen monkeypatch, geen afhankelijkheid
  van privegedrag, geen wijziging hier die een bestaande aanroep een andere betekenis geeft.
  Een leeslaagwijziging is een release van die package plus uv lock, GEEN patch hier.
- BEVROREN PUBLIEKE CONTRACTEN van deze repo (raakt een idee ze, dan is het een
  VOORSTEL-VOOR-DE-AUTEUR, niet iets uitvoerbaars — markeer dat expliciet):
  * de CLI (subcommando's analyseer/dekking/vergelijk/toets en hun opties);
  * de JSON-envelop (schema/veldnamen);
  * de GeoPackage-structuur (lagen, kolommen, status, popup, gwsw_run-velden);
  * de CSV-kolommen van bevindingen.csv;
  * checks.toml (de Meetbereik-lijst is daar verplicht, geen default in Python);
  * check-ID's uit het checkregister (TOP-001 enz.) zijn stabiel; vervallen ID's nooit hergebruiken.
- EEN UITVOERSCHRIJVER. Alle vier uitvoervormen (Markdown, CSV, GeoPackage, JSON) komen uit
  dezelfde meldingenstroom (uitvoer/melding.py) met herkomst uit uitvoer/herkomst.py — de enige
  schrijver. Nooit zelf to_csv/write_text/json.dump; nooit invoer overschrijven. Een tweede
  schrijver is verboden (tests/test_uitvoer_herkomst.py bewaakt dit).
- Elke check DECLAREERT rollen + kenmerken (issue #64); twee drifttests bewaken dat tegen de
  code (AST-sweep) en tegen de ontologie. Verander je wat een check selecteert/leest, dan MOET
  de declaratie mee — anders is het geen additieve aanbeveling maar een bug.
- Standaard toetst de dataset aan ALLE CFK's (Hyd, MdsPlan, MdsProj); een deelset alleen via
  --cfk. Drempels (toleranties, min/max, buffers) zijn per project configureerbaar via TOML —
  GEEN hardcoded drempels. Ernst F/W; dimensietag uit de enum Dimension.

Aanbevelingen moeten ADDITIEF zijn (nieuwe checks/modules/functies of pure test-/CI-toevoeging).
Raakt een idee een bevroren contract of de leeslaag-API, dan is het VOORSTEL-VOOR-DE-AUTEUR.
Poort: ruff check, ruff format, mypy over src/nlriochecker, pytest (zonder marker zwaar),
dekking >=95%. Kritieke paden (checks/, aansluiting op de leeslaag, uitvoer/, ontologie) vragen
substantiele review; noem dat waar een aanbeveling ze raakt.`

const DIMENSIONS = [
  { key: 'architectuur', prompt: `LENS: ARCHITECTUUR & laagsnit. Beoordeel de laagindeling en importrichting (docs/architectuur.md): dataset/leeslaag -> selectie -> checks -> meldingenstroom -> uitvoer. Zijn de grote modules (uitvoer/gpkg 1907, checks/attributen 1638, checks/topologie 1625) diepe modules of god-modules? Waar lekt engine-kennis in de uitvoerlaag of andersom? Zoek deepening-kansen: smallere interfaces over complexere implementaties, zonder een bevroren contract te raken.` },
  { key: 'domein-correctheid', prompt: `LENS: DOMEIN-CORRECTHEID van de checks. Toets de check-implementaties tegen het checkregister v0.9 en de GWSW-ontologie. Zoek modelleerfouten in de engine (het soort dat "duizenden bevindingen" oplevert waar er een handvol horen): verkeerde populatieselectie (rollen), verkeerd gelezen kenmerken, richting/graaf-aannames, off-by-one op drempels, CFK-afhandeling. Verifieer bestaan van klassen/properties in de ontologie voor je iets "ontbrekend" noemt. Stel gerichte fixes of borgende tests voor.` },
  { key: 'uitvoer-contracten', prompt: `LENS: UITVOERLAAG & CONTRACTEN. De vier uitvoervormen komen uit een schrijver (uitvoer/melding.py + herkomst.py). Beoordeel of dat echt de enige schrijver is, of herkomst/voorbehoud/markering consistent in alle vier vormen landt, en of JSON-envelop, GeoPackage-structuur en CSV-kolommen intern samenhangen. Zoek plekken waar het "wat NIET is bekeken" (objecten buiten de graaf, ontbrekende typeringspoort) stil wegvalt. Contract-rakers apart markeren.` },
  { key: 'modulariteit', prompt: `LENS: MODULARITEIT & koppeling. Breng cyclische of te strakke koppeling in kaart tussen checks/, selectie, checkconfig en uitvoer/. Lekkende abstracties, verantwoordelijkheden die verkeerd wonen, gedupliceerde graaf-/geometrie-/drempellogica over de check-modules. Waar maakt een nieuwe seam de package losser en testbaarder zonder een bevroren contract of de leeslaag-API te raken?` },
  { key: 'beheerbaarheid', prompt: `LENS: BEHEERBAARHEID & leesbaarheid. Duplicatie tussen de zeven check-modules, te lange functies (attributen/topologie/netwerk), onduidelijke namen, ontbrekende types, dode code, inconsistente foutafhandeling (errors.py). Concrete vereenvoudigingen die de onderhoudslast verlagen — vooral gedeelde check-helpers die nu per module herhaald worden.` },
  { key: 'performance', prompt: `LENS: PERFORMANCE & geheugen. De volledige toetsrun op De Wolden piekt onder 2 GB en laadt koud ~30 s (BO-41/42). Zoek hotspots in de checks en in uitvoer/gpkg: onnodige materialisatie, O(n^2) over de graaf, herhaalde is_a/typeringsvragen, herhaalde geometrie-parses, pandas/geopandas-kopieen, GC-druk. Stel meetbare, additieve optimalisaties voor (memoisatie, snelpad naast bestaand pad) zonder de leeslaag te patchen.` },
  { key: 'testbaarheid', prompt: `LENS: TESTBAARHEID & correctheid. Dekking staat >=95% maar dekt dat de kritieke paden echt (elke check-familie, de meldingenstroom, de GeoPackage-schrijver, de drie Meetbereik-toestanden, --geen-ontologie)? Zoek zwakke asserties, ontbrekende edge-cases (lege/rommelige dataset, ontbrekende geometrie, ontbrekende CFK, deelrun), en drifttests die te los zijn. De zwaarste integratietests staan onder marker zwaar — draait het lichte pad genoeg? Stel gerichte tests/fixtures voor (handgeschreven TTL met precies een defect).` },
  { key: 'security-ci', prompt: `LENS: SECURITY & CI/repo-hygiene. Deze package leest onvertrouwde TTL/SHACL/GeoPackage/raster-invoer en schrijft bestanden. Zoek: path-traversal bij uitvoerpaden, invoer overschrijven, resource-uitputting (geen limieten) op vijandige input, onveilige deserialisatie, injectie. Beoordeel daarnaast .github/workflows (de vijf-staps-poort), GitHub Actions-efficientie (dubbele triggers, caching, concurrency, matrix), runnerpoort.py, en of er artefacten/secrets/junk getrackt worden die er niet horen (uitvoer/ hoort git-ignored). Wees concreet over de aanvalsinvoer.` },
]

const RECS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['recommendations'],
  properties: {
    recommendations: {
      type: 'array', maxItems: 6,
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'probleem', 'voorstel', 'bestanden', 'impact', 'ernst', 'inspanning', 'raaktContract'],
        properties: {
          title: { type: 'string' },
          probleem: { type: 'string', description: 'wat is er mis, concreet en met bewijs uit de code' },
          voorstel: { type: 'string', description: 'de additieve wijziging' },
          bestanden: { type: 'array', items: { type: 'string' } },
          impact: { type: 'string', enum: ['architectuur','domein-correctheid','uitvoer-contracten','modulariteit','beheerbaarheid','performance','testbaarheid','security-ci'] },
          ernst: { type: 'string', enum: ['laag','midden','hoog','kritiek'] },
          inspanning: { type: 'string', enum: ['S','M','L','XL'] },
          raaktContract: { type: 'boolean', description: 'true als het een bevroren nlriochecker-contract of de leeslaag-API raakt' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['isEcht', 'additief', 'redenering', 'tienXhefboom'],
  properties: {
    isEcht: { type: 'boolean', description: 'false als de aanbeveling onjuist, al opgelost, of speculatief is' },
    additief: { type: 'boolean', description: 'true als uitvoerbaar zonder een bevroren contract of de leeslaag-API te breken; false = voorstel-voor-de-auteur' },
    redenering: { type: 'string' },
    tienXhefboom: { type: 'string', enum: ['triviaal','klein','noemenswaardig','groot'], description: 'bijdrage aan 10x beter' },
  },
}

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['aanbevelingen', 'themas', 'slotnoot'],
  properties: {
    aanbevelingen: {
      type: 'array', maxItems: 25,
      items: {
        type: 'object', additionalProperties: false,
        required: ['rang','titel','waarom10x','categorie','additief','inspanning','bestanden'],
        properties: {
          rang: { type: 'integer' },
          titel: { type: 'string' },
          waarom10x: { type: 'string' },
          categorie: { type: 'string' },
          additief: { type: 'boolean' },
          inspanning: { type: 'string', enum: ['S','M','L','XL'] },
          hangtAf: { type: 'string', description: 'rang(en) waar dit van afhangt, of leeg' },
          bestanden: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    themas: { type: 'array', items: { type: 'string' }, description: 'de rode draden' },
    slotnoot: { type: 'string', description: 'wat de auteur zelf moet beslissen (contract-rakers) en wat additief kan' },
  },
}

phase('Review')
log(`Swarm start: ${DIMENSIONS.length} Opus-lenzen over nlriochecker`)

const reviewed = await pipeline(
  DIMENSIONS,
  (d) => agent(
    `${CONTEXT}\n\n${d.prompt}\n\nLever maximaal 6 aanbevelingen met de hoogste hefboom voor "10x beter". Elke aanbeveling concreet, met bewijs uit de code en de geraakte bestanden.`,
    { label: `review:${d.key}`, phase: 'Review', schema: RECS_SCHEMA, model: 'opus', effort: 'high' },
  ),
  (review, d) => parallel(((review && review.recommendations) || []).map((r, i) => () =>
    agent(
      `${CONTEXT}\n\nVERIFIEER adversarieel deze aanbeveling (lens ${d.key}).\nTITEL: ${r.title}\nPROBLEEM: ${r.probleem}\nVOORSTEL: ${r.voorstel}\nBESTANDEN: ${(r.bestanden||[]).join(', ')}\nAUTEUR-CLAIM raaktContract=${r.raaktContract}.\n\nControleer in de echte code: is het probleem echt en nog niet opgelost? Is het voorstel additief of raakt het een BEVROREN contract (CLI/JSON-envelop/GeoPackage/CSV-kolommen/checks.toml/check-ID's/de uitvoerschrijver) of de leeslaag-API (gwsw-orox-helpers)? Standaard isEcht=false bij twijfel.`,
      { label: `verify:${d.key}:${i}`, phase: 'Verify', schema: VERDICT_SCHEMA, model: 'opus', effort: 'medium' },
    ).then((v) => (v ? { ...r, dimension: d.key, verdict: v } : null)),
  )),
)

const overleefd = reviewed.flat().filter(Boolean).filter((x) => x.verdict && x.verdict.isEcht)
log(`Geverifieerd: ${overleefd.length} echte aanbevelingen naar de regisseur`)

phase('Regie')
const bundel = overleefd.map((x, i) => ({
  n: i + 1, lens: x.dimension, titel: x.title, probleem: x.probleem, voorstel: x.voorstel,
  bestanden: x.bestanden, impact: x.impact, ernst: x.ernst, inspanning: x.inspanning,
  additief: x.verdict.additief, hefboom: x.verdict.tienXhefboom, verifyNoot: x.verdict.redenering,
}))

const plan = await agent(
  `${CONTEXT}\n\nJij bent de REGISSEUR. Hieronder ${bundel.length} geverifieerde aanbevelingen uit 8 lenzen:\n\n${JSON.stringify(bundel, null, 1)}\n\nSynthetiseer tot MAXIMAAL 25 aanbevelingen die samen de package ~10x beter maken op architectuur, domein-correctheid, uitvoer-contracten, modulariteit, beheerbaarheid, performance, testbaarheid en security. Ontdubbel overlappende ideeen, fuseer waar lenzen elkaar raken, en RANGSCHIK op (hefboom x haalbaarheid). Elke aanbeveling: waarom het 10x-relevant is, additief-vlag (contract-rakers en leeslaag-rakers apart en achteraan, als voorstel-voor-de-auteur), inspanning, afhankelijkheden en bestanden. Benoem de rode draden en zet in de slotnoot scherp wat de auteur zelf moet beslissen versus wat een agent additief mag oppakken.`,
  { label: 'regisseur:fable', phase: 'Regie', model: 'fable', schema: PLAN_SCHEMA, effort: 'high' },
)

return { geverifieerd: overleefd.length, plan }
