# Eindverslag ronde 2: uitvoer, afbakening en checkregister v0.8

Datum: 2026-08-16. Opdracht: acht aandachtspunten van de opdrachtgever na de eerste
echte uitvoer (`uitvoer/koekangerveld_ronde2/`).
Ontwerp: `docs/superpowers/specs/2026-08-16-uitvoer-ronde2-design.md`.
Implementatieplan: `docs/superpowers/plans/2026-08-16-uitvoer-ronde2.md` (twaalf taken).
Voorganger: `docs/ronde1-gpkg-en-rapport-verslag.md`.
Commits: `6b77546` (ontwerp) en `ce0304d` (plan) legden de ronde vast; de twaalf
taken zelf lopen van `c5ec34a` tot de commit van deze taak, elk met tests en een
groene suite.

---

## 1. Brainstormuitkomsten en waar ik ervan afweek

De brainstorm behandelde negen ontwerppunten (§2 van het ontwerp). De uitkomsten:

| # | Punt | Keuze |
|---|---|---|
| 1 | Stijlen | `layer_styles` registreren in `gpkg_contents`; losse `.qml`-bestanden vervallen |
| 2 | EXT-008 | Vervalt, ID wordt niet hergebruikt |
| 3 | EXT-001 | Putten erbij, relatie `binnen` / `kruist` / `nabij` als waarde; ernst blijft W |
| 4 | Richtingspijlen | Twee pijlen bij strijd, grijze pijl met eigen legenda-regel bij onbekende BOB |
| 5 | Stapeling | Stapelkolommen plus datagestuurde schermoffset; geometrie blijft exact |
| 6 | Afbakening | Contextschil én datasetcache |
| 7 | Mechanisch riool | Alleen leidingen naar een eigen grijze laag; gemalen blijven in `putten` |
| 8 | `feature_id` | URI-fragment, volledige URI in `gwsw_uri` |
| 9 | Register | v0.8 met de contractwijzigingen én het scopebeleid |

Tijdens de bouw week ik op één punt af van wat de brainstorm veronderstelde:

**Punt 4 ging ervan uit dat een BOB-richting altijd te bepalen is zodra er een
BOB-verval is; dat bleek onjuist.** `richting_van_geometrie()` kan ook bij een
niet-nul verval `None` teruggeven — geen lijngeometrie, geen herleidbare putten, of
dezelfde put aan begin- en eindpunt. De eerste versie viel in dat geval stilzwijgend
terug op het administratieve teken en labelde de rij alsnog `mee` of `tegen`, alsof
er een vergelijking gemaakt was die er niet was. De kolom `richting_bob` kent daarom
drie gevallen onder `onbekend`: geen BOB, een vlak BOB (verval nul), én een
tekenrichting die niet tegen de getekende geometrie te toetsen viel. Zie §4a, eerste
bevinding. De legendatekst is dienovereenkomstig "BOB-richting niet te bepalen"
geworden, niet "BOB onbekend of vlak" zoals het ontwerp voorstelde.

---

## 2. Wat er per taak gebouwd is

### Taak 1 — Checkregister v0.8

`data/checkregister-gwsw-nulmeting-v0_8.md`, met een tabel vervallen checks
(EXT-008), de herschreven EXT-001-rij en het scopebeleid uit taak 9/10. Alle vijf
plekken die naar v0.7 verwezen (`checks.toml`, `dekking.toml`,
`default_register_path()`, `REGISTER` in de registrytest, de dekkingrapporttekst)
zijn omgezet. Het oude v0.7-bestand blijft staan; eerdere runs verwijzen ernaar.

### Taak 2 — EXT-008 vervalt

`PandZonderRiolering` en de bijbehorende tests zijn verwijderd. De dekkingvraag "is
elk pand op riolering aangesloten" hoort bij het rioleringsplan, niet bij een
datakwaliteitstoets op de bestaande registratie — en er zijn panden aangeleverd en
geen verblijfsobjecten, waardoor de check toch al alleen een benadering kon geven.
Het ID blijft gereserveerd.

### Taak 3 — EXT-001 toetst ook putten

`objecten()` levert nu vrijvervalstrengen én putten. De relatie (`binnen`, `kruist`,
`nabij`) staat in de kolom `waarde`, in die volgorde van zwaarte bepaald; bij
meerdere geraakte bouwwerken telt de zwaarste relatie en bij gelijke relatie het
dichtstbijzijnde. Ernst blijft W. Bronlagen: BGT-panden, BAG-panden (aanvulling —
beide dekken het gebied grotendeels maar niet volledig) en de overige
BGT-bouwwerklagen.

### Taak 4 — Stijlen die QGIS ook echt toepast

De kern van de hele ronde. Geverifieerd met de QGIS van deze machine via PyQGIS,
offscreen: `loadDefaultStyle()` gaf op de bestaande GPKG `False` op alle drie de
lagen, omdat `layer_styles` niet in `gpkg_contents` geregistreerd stond — zonder die
rij vindt de OGR-provider de tabel niet. `_schrijf_stijlen()` registreert de tabel nu
als `data_type = 'attributes'` met `srs_id = null`, en schrijft `update_time` in het
formaat dat GDAL zonder waarschuwing accepteert. Losse `.qml`-bestanden naast het
bestand zijn geschrapt: ze werken toch niet bij meerdere lagen in één GPKG en
suggereerden het tegendeel.

### Taak 5 — `feature_id` als fragment

`feature_id` (en `feature_id_2`) dragen voortaan alleen het URI-fragment
(`knp3437`); de volledige URI staat in de nieuwe kolom `gwsw_uri` (en `gwsw_uri_2`),
in `putten`, `strengen`, `mechanisch_riool`, `meldingen` en `meldinglocaties`.
URI's zonder `#` — de bevindingen op BGT- en BAG-objecten, die geen dataset-URI
hebben — blijven ongewijzigd. De melding-ID blijft over de volledige URI gehasht,
dus ID's blijven stabiel ten opzichte van eerdere runs.

### Taak 6 — Mechanisch riool als eigen laag

Nieuwe klassenwortel `klassen.mechanisch` en featurelaag `mechanisch_riool`
(LINESTRING, smalle kolomset, `omschrijving = "Mechanisch riool: niet
geanalyseerd"`). `strengen` bevat voortaan alles behalve het mechanische stelsel;
verbindingen die in geen van beide klassenlijsten vallen (LozeLeiding, Drain,
Duiker) blijven gewoon in `strengen` staan. `gwsw_run` telt per laag, zodat
zichtbaar is dat er 3.720 objecten verhuisd zijn ten opzichte van de vorige uitvoer.

### Taak 7 — Richtingspijlen op de strengen

`bob_verval_m` en `richting_bob` (`mee`/`tegen`/`onbekend`) afgeleid met dezelfde
code als NET-003 en TOP-020, zodat kaart en bevinding niet uit elkaar kunnen lopen.
Regelgebaseerde stijl: drie regels voor de lijnkleur (ernst F, W, geen) plus drie
regels die er pijlen overheen tekenen — één groene pijl bij `mee`, twee
tegengestelde pijlen (tekenrichting versus verval) bij `tegen`, één grijze pijl bij
`onbekend`. Zie §1 voor de afwijking in de semantiek van `onbekend`.

### Taak 8 — Stapelende meldingen uit elkaar

`meldinglocaties` krijgt `stapel_aantal` en `stapel_nr` (1-gebaseerd), bepaald per
foutlocatie afgerond op millimeters, in een vaste volgorde (melding-ID) zodat de
nummering tussen runs gelijk blijft. De stijl zet ze op het scherm uiteen met een
datagestuurde offset; de geometrie blijft exact op de foutlocatie. Zie §4a, tweede
bevinding, voor het gebrek in de eerste stabiliteitstest.

### Taak 9 — De analyseset: kern plus contextschil

Nieuw: `src/gwswpijplijn/afbakening.py`. `bouw_analyseset()` bepaalt de kern
(objecten die het gebied raken, ongewijzigd van betekenis) plus een contextschil:
de samenhangende netwerkcomponent die de kern raakt (alleen over de
vrijvervalleidingen — mechanische leidingen verbinden dorpen onderling en zouden de
schil tot bijna de hele gemeente laten uitdijen) én alles binnen
`studiegebied.context_buffer_m` van het gebied. Zie §4a, derde bevinding, voor het
gebrek in de componentberekening zelf.

### Taak 10 — De analyseset in de pijplijn

Checks draaien nu op de analyseset in plaats van op de volledige export. Een check
kan `volledig_bereik = True` declareren om toch op de volledige dataset te draaien
(vooralsnog alleen ADM-002: een duplicaat kan overal in de export zitten). `CheckRun`
onthoudt de analyseset; de CLI en het bevindingenrapport melden de omvang van kern,
schil en export, plus het aantal vrijvervalstrengen dat de afbakening niet kon
meewegen omdat een uiteinde niet naar een netwerkknoop herleidt. Zie §4a, vijfde
bevinding (de regressie in de wiring).

### Taak 11 — Datasetcache

Nieuw: `src/gwswpijplijn/cache.py`. Sleutel: sha256 over de inhoud van
dataset- en ontologiebestanden, de broncode van `dataset.py` en `geometry.py`, en
de rdflib-/shapely-versies — wijzigt de lader, dan is het een andere sleutel.
Opslag onder `~/.cache/gwswpijplijn/<sleutel>/`, weggeschreven via een tijdelijk
bestand plus `rename`. De rdflib-graaf (423 MB op De Wolden) gaat achter een luie
plaatsvervanger (`LuieGraaf`) die pas van schijf leest zodra een check hem
aanraakt; de structuren (knopen, strengen, klassenhierarchie, 31 MB) worden altijd
meteen gelezen. CLI: standaard aan, `--geen-cache` slaat over, `--cache-map`
verlegt de locatie. Zie §4a, vierde bevinding, voor het gebrek dat de review hier
vond.

**Gemeten looptijden op De Wolden (taak 11, stap 7):**

| Run | Totaal | Waarvan |
|---|---|---|
| Koud | 3m30,8s | parsen 199,4 s (inclusief het wegschrijven van de cache) |
| Warm | 47,9s | dataset teruglezen 2,5 s |

Cachemap: 434 MB. Beide runs leverden dezelfde 98 bevindingen op.

Twee kanttekeningen bij die cijfers, voor de eerlijkheid:

- de warme graaflezing profiteerde van de pagecache van het besturingssysteem; het
  geïsoleerde cijfer voor alleen het graaf-teruglezen is niet apart gereproduceerd;
- "dezelfde 98 bevindingen" is een steekproef, geen bewijs van volledige
  round-trip-gelijkheid — dat bewijs leveren de eenheidstests in `tests/test_cache.py`
  (schrijven en teruglezen levert dezelfde dataset, de graaf werkt ook uit de cache,
  een gewijzigde loaderbroncode geeft een andere sleutel, een beschadigde cache of
  beschadigde graafcache leidt tot opnieuw inlezen).

### Taak 12 — Sluitstuk

Dit verslag, de PyQGIS-smoketest (`tests/test_uitvoer_qgis.py`) en de zware
afbakeningstest op De Wolden (§3). CLAUDE.md is bijgewerkt: de regel "Analyseer
breed, rapporteer smal" is vervangen (§4.6 van het ontwerp), er staan twee nieuwe
technische afspraken (stijlen in `layer_styles`, de datasetcache) en het open punt
over de 1773 doodlopende eindknopen heeft een aantekening over de contextschil
gekregen. `docs/gis-inventarisatie.md` is bijgewerkt: EXT-008 is eruit (de
BAG-panden voeden nu alleen nog EXT-001 als aanvulling op de BGT-panden), en de
vervallen drempel `ext_riolering_bij_pand_m` is uit de configuratielijst gehaald.
Dat document beschrijft de actuele koppeling van bronnen aan checks en moest dus
mee; `docs/fase4-verslag.md` en de oudere specs zijn een verslag van hun moment en
blijven ongewijzigd.

---

## 3. De PyQGIS-smoketest en de zware afbakeningstest

`tests/test_uitvoer_qgis.py` is de enige test die het echte antwoord geeft op de
vraag waar deze ronde mee begon: past QGIS de meegeleverde stijlen toe? Hij wordt
overgeslagen waar `qgis.core` niet importeerbaar is — QGIS is geen afhankelijkheid
van dit project. Op deze machine staat QGIS wel (`/usr/bin/qgis`), maar de
project-venv (`uv run`) is geïsoleerd (`include-system-site-packages = false`) en
ziet die installatie niet: `uv run pytest tests/test_uitvoer_qgis.py -v` slaat de
test dus standaard over, en dat is precies het gedrag dat de test moet vertonen.
Om hem echt te draaien heb ik de systeem-`dist-packages` (waar PyQGIS in zit) achter
de venv aan `sys.path` geplakt, zodat de nieuwere `pydantic`/`typing_extensions` uit
de venv voorrang houden en alleen de ontbrekende modules (`qgis`, `PyQt5`, `osgeo`)
van het systeem komen. Zo gedraaid: alle zes tests slagen — `loadDefaultStyle()`
geeft op alle vier de featurelagen `(True, "... Provider ...")`, de strengenlaag
kent de drie richtingslabels (met de gecorrigeerde tekst uit §1), en geen enkele
stijlexpressie verwijst naar een kolom die niet bestaat.

De zware test `test_afbakening_op_koekangerveld_verandert_de_bevindingen_niet` in
`tests/test_integration.py` toetst het kernbeloofde van taak 9/10: dezelfde
bevindingen op NET-001, NET-002, NET-004, TOP-001 en TOP-005, of de checks nu op de
volledige De Wolden-dataset draaien of op de analyseset rond Koekangerveld — en de
analyseset is aantoonbaar kleiner dan de volledige export.

---

## 4a. Wat de code review aan het licht bracht

CLAUDE.md schrijft voor `/superpowers:requesting-code-review` te draaien voor elke
commit. Over de hele ronde heeft dat vier echte gebreken in de eigen code van deze
ronde blootgelegd, en één regressie in de bekabeling tussen twee taken.

**De richtingspijl tekende een zelfverzekerde `mee`/`tegen` waar de tekenrichting
niet vast te stellen was.** `_richting_bob()` viel bij een niet-bepaalbare
tekenrichting (geen lijngeometrie, geen herleidbare putten, of dezelfde put aan
beide zijden) stilzwijgend terug op het administratieve BOB-teken en labelde de rij
toch als `mee` of `tegen`. Dat las als een vergelijking die gemaakt was, terwijl er
geen richting was om het verval tegen te spiegelen. De kolom geeft nu `onbekend` in
dat geval. Nieuwe fixture `richting_niet_bepaalbaar_met_bob.ttl` (dezelfde put aan
begin- en eindpunt, twee verschillende niet-nul BOB's) legt dit vast; zonder de fix
faalt hij.

**De stabiliteitstest voor de stapelnummering kon de eigen bug niet ontkrachten.**
`test_stapelnummering_is_onafhankelijk_van_lijstvolgorde` gaf beide runs dezelfde
meldingenlijst in dezelfde volgorde mee; een implementatie die simpelweg op
lijstvolgorde nummert was daar even goed doorheen gekomen als een die op
melding-ID sorteert. De tweede run krijgt nu de omgekeerde lijst, en de vergelijking
gebeurt per melding-ID. De nummeringstest zelf groepeerde bovendien op stapelgrootte
in plaats van op de echte locatie, waardoor twee even grote stapels de assertie
hadden kunnen laten sluipen; die groepeert nu op locatie.

**`nx.Graph` in `_component()` liet parallelle strengen stilzwijgend vallen.** Een
gewone `nx.Graph` onthoudt van twee kanten tussen hetzelfde knopenpaar alleen de
laatst toegevoegde; `add_edge(..., uri=...)` per streng liet zo een van twee
evenwijdige strengen (in dit domein normaal, zie TOP-013) uit de analyseset vallen.
De graaf bepaalt nu alleen de samenhang tussen knopen; welke strengen bij een
component horen, wordt er los van bijgehouden. Nieuwe fixture
`afbakening_parallelle_strengen.ttl` en een test die de fout eerst rood laat zien
(de derde streng viel weg) en na de fix groen.

**Een beschadigde graafcache werd als gezonde cachetreffer gemeld en liet de run
daarna alsnog crashen.** Was de structurencache intact maar `graaf.pickle`
beschadigd, dan meldde `laad_met_cache` een schone cachetreffer; de
`UnpicklingError` klapte pas op, ongevangen, zodra een check `dataset.graph`
aanraakte — middenin `run_checks`. `LuieGraaf` herstelt zichzelf nu: bij een
mislukte `pickle.load` meldt hij dat via de logger, leest de graaf alsnog uit de
brondata en schrijft de cache atomisch opnieuw weg. Een nieuwe test bederft alleen
`graaf.pickle` (de bestaande test die beide cachebestanden bederft, dekt dit pad
niet: daar faalt de structurencache het eerst) en is gereproduceerd tegen de vorige
commit: daar propageert de `UnpicklingError` ongevangen.

**Regressie in de wiring tussen taak 9 en taak 10: de datakarakteristiek liep
stilzwijgend mee naar de analyseset.** Taak 10 liet de checks op de analyseset
(kern plus schil) draaien, maar de datakarakteristiek en het aantal onbetrouwbaar
getypeerde objecten (uit de typeringspoort) werden toen ook over die analyseset
berekend — terwijl het rapport ze expliciet "stabiel onder afbakening" noemt en dus
suggereert dat ze over de hele export gaan. `run_checks` berekent ze nu op
`context.volledige_context().dataset`. Zonder studiegebied verandert er niets, want
dan zijn beide hetzelfde object. Vier plekken die nog beweerden dat de checks op de
volledige dataset draaiden zijn tegelijk gecorrigeerd naar de nieuwe werkelijkheid
(de rapportregel in `uitvoer/bevindingen.py`, de docstrings van
`beperk_tot_studiegebied` en `schrijf_geopackage`, en de `notes()`-docstring van
`_ZonderAfvoerpad` in `checks/netwerk.py`).

---

## 5. Tests

De volledige suite (`uv run pytest -m "not zwaar"`) is groen; ruff (lint en format)
is schoon. De vier zware De Wolden-tests in `tests/test_integration.py` staan onder
de marker `zwaar` en draaien niet standaard mee; apart gedraaid (`uv run pytest -m
zwaar`) zijn ze ook groen — zie de exacte tijden en aantallen in het taakrapport
van deze taak.

De PyQGIS-smoketest staat onder de nieuwe marker `qgis` (geregistreerd in
`pyproject.toml`, naast `zwaar`), niet omdat de suite hem apart moet kunnen
uitsluiten — `pytest.importorskip` doet dat al — maar zodat hij herkenbaar is als
"vereist PyQGIS" voor wie later met `-m qgis` selectief wil draaien.

---

## 6. Wat open blijft

- **De rdflib-graaf pruimen.** Het ontwerp (§4.5) noemt dit expliciet als volgende
  stap: de graaf terugbrengen tot de triples die de checks werkelijk raken
  (`hasPart`, `hasConnection`, `type`, `label`, aspecten), of die gegevens in de
  structuren opnemen zodat de graaf helemaal kan vervallen. Dat raakt vier
  checkmodules en hoort niet in deze ronde.
- **De koude run parst nog steeds ruim 180 s.** De cache verbergt dat bij een
  tweede run, maar lost het niet op; een ruimtelijk voorfilter tijdens het parsen
  zou kunnen helpen, maar vraagt een eigen TTL-lezer.
- De negentien nog niet gebouwde TOP- en NET-checks uit het register (ongewijzigd
  ten opzichte van ronde 1).
- Waterschapsdata en BRK: EXT-004 blijft skelet.
- EXT-005 en EXT-006 zijn volledig geïmplementeerd maar draaien niet op de
  aangeleverde data: de BGT-laag `put` bevat nul features. Ongewijzigd ten opzichte
  van ronde 1.
