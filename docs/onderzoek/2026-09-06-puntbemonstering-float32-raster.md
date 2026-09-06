# Puntbemonstering uit een groot float32-raster: GDAL/rasterio-mechaniek (2026-09-06)

**Vraag:** stap 0 van issue #168 (aparte onderzoeksstap, issue #170) — welke technieken voor
puntbemonstering uit een groot, deels-niet-in-RAM-passend float32-raster zijn kansrijk, volgens
de officiële GDAL-, rasterio- en GeoTIFF/COG-documentatie, en welke van de acht bestands- en vier
leesstrategie-varianten uit #168 blijven, vervallen of erbij moeten op grond daarvan? Dit is
zuiver deskresearch tegen primaire bronnen; er is **geen meting gedaan** (die volgt in #168 zelf)
en **geen code gewijzigd**.

Al vastgesteld en niet opnieuw onderzocht: het probleem (`RasterSampler.sample_many`,
`src/nlriochecker/externedata.py:142-173`, één `reader.sample`-aanroep voor 22.357 punten op een
56.746×42.453 float32-raster van 9,64 GB, strips van 1 rij, dat niet in 16 GB RAM past), de harde
eisen (geen nieuwe dependency, float32/bit-gelijke uitkomst blijft, een leesstrategie mag geen
bestandsindeling vereisen), en de acht bestands- plus vier leesstrategie-varianten met hun al
gesnoeide kruisproduct (L1/L3 draaien niet op de strip-referentie #0). Die pruning is een
auteursbesluit uit #168 en wordt hieronder niet herhaald als eigen vondst, alleen verder
onderbouwd.

Twee getallen komen in bijna elke sectie terug (eigen berekening uit de dimensies in #168, geen
citaat): de rasterbreedte is 56.746 kolommen × 4 bytes (float32) = **226.984 bytes (≈ 221,7 KiB)
per rij**, en een 512×512-tegel is 512×512×4 = **1.048.576 bytes (1 MiB) per tegel**. Bij een
tegelraster van 512×512 geeft dat 111×83 = **9.213 tegels**; bij 1024×1024 (56×42=) **2.352
tegels**; bij 256×256 (222×166=) **36.852 tegels**. Ter controle: 9.213 tegels × 1 MiB komt uit op
9,66 GB — precies het bestand dat #168 noemt voor de teruggedraaide 512-tegelproef
(commit 68deb56), wat de tegel/pixel-rekensom hieronder bevestigt (edge-tegels aan de rand van het
raster worden op volle tegelgrootte opgeslagen, vandaar dat het niet exact 9,64 GB is).

## 1. GDAL/rasterio-blokcache (`GDAL_CACHEMAX`)

**Bron en mechanisme.** `GDAL_CACHEMAX` "Controls the default GDAL raster block cache size. When
blocks are read from disk, or written to disk, they are cached in a global block cache by the
GDALRasterBlock class" — standaard **5% van het beschikbare systeemgeheugen**
(gdal.org/en/stable/user/configoptions.html). RFC 26 (gdal.org/en/stable/development/rfc/
rfc26_blockcache.html) beschrijft het verdringingsmechanisme: "a static linked list is maintained
so as to track the access order of the blocks and keep the size of the cache within a desired
limit by dropping the oldest blocks out of the list" — een eenvoudige LRU zonder kennis van het
toegangspatroon. Dezelfde pagina geeft de rekenregel cachegrootte-naar-blokaantal: "Typically with
the default GDAL_CACHEMAX size of 40 MB, only 640 blocks of 256x256 pixels can be simultaneously
cached (for all datasets)" (dat 40 MB-getal is een oud voorbeeld, geen huidige default, maar de
formule cache/blokgrootte = aantal blokken staat).

**Bevinding.** Een grotere cache helpt uitsluitend als hetzelfde blok **meerdere keren** wordt
aangeraakt binnen één run (hergebruik), niet als elk blok maar één keer wordt bezocht — dan is de
hoeveelheid schijf-I/O onafhankelijk van de cachegrootte. Omdat `sample_gen` (zie vraag 5) de
punten in willekeurige (selectie-)volgorde afhandelt zonder zelf te sorteren of te batchen, moet
de cache — zonder L1-sortering — de **volledige verzameling geraakte blokken tegelijk** vasthouden
om herbezoek te garanderen, niet alleen het blok van het huidige punt. Dat is een omslagpunt van
ordegrootte gigabytes, niet megabytes: voor de 512-tegelvariant is dat tot ~9,66 GB (vrijwel het
hele bestand, zie boven), voor de stripreferentie tot ~5 GB (zie vraag 2). Onder die drempel
verdringt de LRU een blok voordat het tweede punt in dat blok aan de beurt is, en levert een
grotere cache dus geen enkele winst tot hij bijna het hele werkgebied dekt — geen geleidelijke
curve maar een drempeleffect. Dit verklaart ook waarom de auteur L1 (tegel-sortering) en L2
(cache omhoog) als losse varianten opneemt: L1 bereikt hergebruik met een kleine cache (opeen-
volgende punten delen hetzelfde blok), L2 zonder sortering heeft een cache nodig die het hele
werkgebied dekt.
**Lossless/richting:** dit is geen compressietechniek maar een geheugenbudget; geen precisie-
impact. Verwacht **koud gunstig** zodra de cache het werkgebied dekt (minder herhaalde
schijf-I/O), **warm neutraal** (het bestand staat toch al in de OS-pagecache; het GDAL-blokcache-
budget verandert daar weinig aan zolang het proces zelf niet ververst).

## 2. Tegelgrootte versus strips van 1 rij

**Bron en mechanisme.** De GTiff-driverpagina (gdal.org/en/stable/drivers/raster/gtiff.html)
zegt over de standaardindeling: "By default striped TIFF files are created" met "strip height
defaults to a value such that one strip is 8K or less" — bij een rijbreedte van 226.984 bytes kan
geen enkele strip aan die 8 KiB-grens voldoen, dus valt GDAL terug op één rij per strip (verklaart
waarom het aangeleverde bestand strips van 1 rij heeft). Voor tegels: "BLOCKXSIZE... Defaults to
256... Must be divisible by 16" en "BLOCKYSIZE... Tile height defaults to 256." De rasterio-
documentatie over windowed reading (rasterio.readthedocs.io/en/stable/topics/windowed-rw.html)
is expliciet over de minimale leeshoeveelheid: "In getting data to fill a window Rasterio will
read the entirety of one or more chunks of data from the dataset" en concreet: "If you're reading
from a GeoTIFF with 512 x 512 pixel chunks (blocks), that determines the minimum number of bytes
that will be read from disk or copied over your network, even if your read window is only 1 x 1
pixels."

**Bevinding (met eigen berekening).** Voor déze rasterbreedte is een strip juist **goedkoper per
punt** dan een 512- of 1024-tegel: één rij kost 221,7 KiB, een 512-tegel 1 MiB (4,5× zoveel), een
1024-tegel 4 MiB (18× zoveel). Buurpunten delen alleen iets bij een strip als ze in dezelfde rij
liggen (1D-lokaliteit); een tegel deelt in twee richtingen (2D-lokaliteit) maar kost per keer meer.
Met 22.357 verspreide punten over het hele gebied (De Wolden + Hoogeveen) en 9.213 tegels bij
512×512 raakt vermoedelijk vrijwel elke tegel minstens één keer — dan leest de 512-tegelvariant in
totaal ~9,66 GB (bijna het hele bestand), tegen naar schatting ~5,07 GB voor de stripreferentie
(22.357 rijen × 221,7 KiB, als aanname bovengrens dat elk punt een andere rij raakt — waarschijnlijk
íets lager door rij-overlap, maar niet in de orde van een factor 2). Dat is een plausibele
verklaring voor de "onverklaarde" 126 s van de 512-tegelproef in #149 (trager dan de strip, terwijl
tegels buurpunten beter zouden moeten bedienen): bij déze puntdichtheid en dít raster is de
tegel niet klein genoeg om voordeel te halen uit lokaliteit, en te groot om goedkoop te zijn per
gemiste tegel. Dit is een **afgeleide berekening, geen meting** — de echte puntverdeling
(geclusterd langs rioolstrengen, niet uniform) kan het aantal geraakte tegels omlaag brengen.
256×256-tegels (256 KiB per tegel, dicht bij de 221,7 KiB van een strip) zijn de kleinste
geteste tegelmaat en dus de goedkoopste per gemiste tegel terwijl ze nog steeds 2D-lokaliteit
bieden — een sterkere papieren kandidaat dan 512/1024 voor dít toegangspatroon.
**Lossless/richting:** geen precisie-impact (alleen indeling). Richting is
**rastervorm-afhankelijk**: voor dit brede-maar-niet-hoge raster is een kleine tegel (of de strip
zelf) koud vermoedelijk voordeliger dan een grote tegel; warm maakt de indeling weinig uit zodra
het bestand in de OS-pagecache staat, behalve dat een groter blok meer geheugen per GDAL-blok
vasthoudt.

## 3. Compressie-codecs op float32 met predictor (DEFLATE/ZSTD/LZW, `PREDICTOR=3`)

**Bron en mechanisme.** De GTiff-driverpagina somt de codecs op:
"COMPRESS=[JPEG/LZW/PACKBITS/DEFLATE/CCITTRLE/CCITTFAX3/CCITTFAX4/LZMA/ZSTD/LERC/.../NONE]" en de
predictor: "PREDICTOR=[1/2/3]: Defaults to 1... 2 is horizontal differencing and 3 is floating
point prediction", met "LZW, DEFLATE and ZSTD compressions can be used with the PREDICTOR creation
option." De libtiff-documentatie (libtiff.gitlab.io/libtiff/tools/tiffcp.html) bevestigt hetzelfde
op de referentie-implementatie: "A predictor value of 2 causes each scanline of the output image
to undergo horizontal differencing before it is encoded... A value 3 is for floating point
predictor which you can use if the encoded data are in floating point format", en "LZW, Deflate
and LZMA2 compression can be specified together with a predictor value." De COG-driverpagina
bevestigt expliciet welke van deze codecs verliesvrij zijn: "Lossless-compressies: LZW, DEFLATE,
ZSTD, LZMA en LERC (standaard)."

**Bevinding.** DEFLATE/ZSTD/LZW met `PREDICTOR=3` zijn **lossless** volgens zowel de GDAL- als de
libtiff-bron: de predictor is een omkeerbare voorbewerking (differencing tussen naburige pixels),
gevolgd door een lossless entropiecoder; geen van beide bronnen noemt een precisieverlies voor
deze combinatie (in tegenstelling tot JPEG/WEBP/JXL, die de COG-pagina expliciet als lossy
noemt). Geen van de geraadpleegde bronnen geeft een kwantitatieve decompressie-CPU-kost per
codec (ZSTD vs. DEFLATE vs. LZW) — dat blijft een open vraag voor de meting in #168 zelf, niet uit
documentatie te herleiden. De richting volgt wel uit het GDAL-cachearchitectuur: het blokcache
bewaart **gedecodeerde** pixels per proces (RFC 26); elk nieuw proces (elke `toets`-run) start met
een leeg GDAL-blokcache, ook als de OS-pagecache het gecomprimeerde bestand nog warm heeft. Dat
betekent dat compressie de schijf-I/O verlaagt (gunstig als het bestand koud is) maar de
decompressie-CPU per uniek blok altijd betaald wordt, ook op een "warme" herhaalrun binnen
hetzelfde proces zolang het GDAL-blok zelf niet meer in het (proces-lokale) blokcache zit.
**Lossless/richting:** **lossless**, bevestigd door zowel gdal.org als libtiff.gitlab.io.
**Koud gunstiger** (minder bytes van schijf); **warm minder of geen winst** (decompressie-CPU
vervangt de I/O-tijd die er anders al bijna niet was) — in lijn met de eigen hypothese in #168
("winnen koud... verliezen warm nauwelijks").

## 4. COG-layout (IFD/tile-index vooraan)

**Bron en mechanisme.** De OGC-standaard (docs.ogc.org/is/21-026/21-026.html) motiveert de
lay-out expliciet vanuit netwerklatentie: "Fetching the header of a COG over 3 consecutive HTTP
requests adds ~540ms of latency which is large enough to be perceived by the user", en beschrijft
de aanbevolen volgorde: eerst de IFD van de volle resolutie, dan de tegelindex-arrays, dan de
tegeldata. cogeo.org zegt hetzelfde in eigen woorden: een COG "relies on two complementary pieces
of technology": interne tegeling én "HTTP GET range requests", zodat een client "the right parts
of the GeoTIFF" kan ophalen "instead of having to download the whole file." Overviews zijn
expliciet optioneel: "The presence of reduced-resolution subfiles in a COG file is optional"
(alleen verplicht voor bestanden die de aparte overviews-conformance-klasse claimen).

**Bevinding.** Het voordeel dat de spec beschrijft — vooraan geplaatste metadata bespaart
**HTTP-rondes** — is specifiek voor **externe/HTTP-toegang**; nlriochecker leest het AHN-bestand
van lokale schijf, niet over HTTP. Een lokale seek naar een IFD verderop in het bestand kost geen
netwerk-round-trip, dus de kernwinst van de COG-layout vertaalt zich naar verwachting **niet** naar
een lokaal leesscenario: een gewone tiled GeoTIFF met dezelfde tegelgrootte (bv. variant #2) geeft
lokaal dezelfde toegang tot losse tegels als een COG (#7) met die tegelgrootte — het verschil zit
alleen in wáár de IFD in het bestand staat, niet in of een tegel apart leesbaar is. Overviews zijn
hier sowieso niet relevant: de checks bemonsteren uitsluitend op volle resolutie (geen down-
sampled preview-toegang), en #168 noemt voor de COG-varianten zelf al "geen overviews" (#7) resp.
alleen compressie erbij (#8) — in lijn met wat de spec zegt over overviews als optioneel en
niet-gekoppeld aan volle-resolutietoegang.
**Lossless/richting:** de layout zelf heeft geen precisie-impact; lossless hangt volledig af van
de gekozen compressie binnen de COG (zie vraag 3). **Geen verschil verwacht** tussen een COG en
een gewone tiled GeoTIFF van gelijke tegelgrootte/compressie bij **lokale** toegang, koud én warm
— het COG-specifieke voordeel (minder HTTP-rondes) is hier niet van toepassing.

## 5. `rasterio.sample`/`sample_gen` versus een eigen vensterlezer

**Bron en mechanisme.** De rasterio-API-documentatie (rasterio.readthedocs.io/en/stable/api/
rasterio.io.html) beschrijft `sample(xy, indexes=None, masked=False)`: "Get the values of a
dataset at certain positions" met "Values are from the nearest pixel. They are not interpolated."
De brontekst van de generator (github.com/rasterio/rasterio, `rasterio/sample.py`) laat zien hoe
dat intern werkt: per coördinaat een eigen venster van 1×1 pixel — `win = Window(col, row, 1, 1);
data = read(indexes, window=win, masked=masked); yield data[:, 0, 0]` — zonder enige batching of
blok-hergebruik tussen punten; de coördinaat-naar-rij/kolom-omzetting gebeurt weliswaar in
stukken van 256 (`_transform_xy`), maar dat is alleen de coördinatentransformatie, niet de
daadwerkelijke rasterlezing. Dezelfde bron bevat expliciet het advies en een hulpfunctie voor de
oplossing die #168 als L1 voorstelt: "Note: Sorting coordinates can often yield better
performance. A sort_xy function is provided in this module for convenience" — al sorteert die
ingebouwde `sort_xy` alleen lexicografisch op (x, y) (`np.lexsort([y, x])`), niet tegel-bewust
zoals de `rij // blockysize, kolom // blockxsize`-sortering die #168 voorstelt; die laatste is dus
een sterkere, blok-specifieke variant van wat rasterio zelf al aanraadt.

**Bevinding.** De per-punt-overhead van `sample_gen` zit in precies dit patroon: elk punt triggert
een eigen `Window`-object, een eigen `read()`-aanroep door de GDAL-C-laag heen en een eigen
numpy-array-allocatie, ongeacht of het onderliggende blok toevallig al in het GDAL-blokcache zit.
Het cProfile-resultaat dat #168 al noemt (22.357 aanroepen, 2,84 s tottime ≈ 127 µs/aanroep) is
precies deze vaste overhead, niet schijf-I/O (die telt apart in de cumulatieve tijd). Een eigen
vensterlezer (L3: `reader.read(window=...)` per geraakte tegel, punten zelf indexeren) vervangt
"N punten × 1 GDAL-aanroep" door "N unieke tegels × 1 GDAL-aanroep, plus goedkope numpy-indexering
in Python" — dat loont zodra het aantal unieke geraakte tegels merkbaar kleiner is dan het aantal
punten. Uit de tegel/punt-verhouding in vraag 2: bij 512×512 gemiddeld ~2,4 punt/tegel en bij
1024×1024 ~9,5 punt/tegel is er reëel hergebruik; bij de strip-referentie (waar het aantal unieke
rijen dicht bij het aantal punten ligt) nauwelijks — wat aansluit bij de al gesnoeide keuze in
#168 om L3 niet op de strip-variant te draaien.
**Lossless/richting:** geen precisie-impact (dezelfde pixelwaarden, alleen anders opgehaald).
Verwacht **vooral warm gunstig** (minder Python/GDAL-call-overhead per punt, ongeacht of het blok
al gecachet is) en **koud gunstig zodra tegels reëel hergebruik geven** (minder herhaalde
schijf-I/O van hetzelfde blok); op de strip-referentie geen verwacht verschil.

## Herziene variantenlijst voor #168

**Bestandsvarianten:**

| # | variant | oordeel | reden |
|---|---|---|---|
| 0 | strips 1 rij (origineel) | BLIJFT | referentie; blijkt uit vraag 2 bovendien een verrassend goedkope kandidaat per punt (221,7 KiB/rij) |
| 1 | tiles 256×256, geen compressie | BLIJFT | kleinste geteste tegel, leescost per tegel (256 KiB) dicht bij de strip, met toch 2D-lokaliteit — sterkste papieren kandidaat tussen tegel en strip |
| 2 | tiles 512×512, geen compressie | BLIJFT | al gemeten (#149, 126 s); vraag 2 geeft er nu een verklaring bij (tegel te groot voor deze puntdichtheid) — herhalen met L1/L2/L3 is nu zinvoller |
| 3 | tiles 1024×1024, geen compressie | BLIJFT | hoogste punt/tegel-verhouding (~9,5); test of extra hergebruik de hogere leescost (4 MiB/tegel) compenseert |
| 4 | tiles 512, DEFLATE+PREDICTOR=3 | BLIJFT | lossless bevestigd (gdal.org + libtiff.gitlab.io); koud-gunstige hypothese intact |
| 5 | tiles 512, ZSTD+PREDICTOR=3 | BLIJFT | idem; geen bron geeft CPU-kost t.o.v. DEFLATE, dus vergelijking blijft nodig |
| 6 | tiles 512, LZW+PREDICTOR=3 | BLIJFT | idem |
| 7 | COG (tiles 512, geen overviews) | VERVALT | COG-layout wint alleen HTTP-rondes (OGC-spec, cogeo.org); lokaal identiek aan #2 met dezelfde tegelgrootte, dus geen aparte meting nodig |
| 8 | COG + beste compressie van 4/5 | VERVALT | zelfde reden als #7; de compressiewinst is al gedekt door #4/#5, de COG-laag voegt lokaal niets toe |
| — | ander rasterformaat (bv. GeoPackage-raster) | GEEN NIEUWE VARIANT | geen van de geraadpleegde bronnen (GDAL/rasterio/COG/libtiff) onderbouwt een specifieke winst van een ander formaat voor lokale puntbemonstering; iets toevoegen zou hier speculatie zijn zonder brondekking |

**Leesstrategieën:**

| # | strategie | oordeel | reden |
|---|---|---|---|
| L0 | huidige `sample_many` (één `reader.sample`) | BLIJFT | referentie; de rasterio-bron bevestigt dat dit intern één ongesorteerd venster per punt is (vraag 5) |
| L1 | coördinaten sorteren op tegel | BLIJFT | rasterio's eigen module beveelt sorteren expliciet aan (`sort_xy`-commentaar), al is de voorgestelde tegel-bewuste sortering in #168 sterker dan de ingebouwde lexicografische sort; nuttig zodra tegels reëel hergebruik geven (#1-#6) |
| L2 | `GDAL_CACHEMAX` omhoog | BLIJFT | maar met scherpere verwachting: zonder L1 moet de cache het hele werkgebied dekken (orde gigabytes, RFC 26) om iets te winnen — nuttig als controlemeting die laat zien hoeveel van de L1-winst een cache alleen al gratis geeft |
| L3 | eigen vensterlezer per tegel | BLIJFT | de rasterio-broncode toont expliciet dat `sample_gen` geen batching doet; L3 loont zodra unieke-tegels-geraakt << aantal punten (#2/#3, niet #0) |

## Bronnen

- GTiff-driver (strips/tiles, `BLOCKXSIZE`/`BLOCKYSIZE`, `COMPRESS`, `PREDICTOR`,
  `GTIFF_DIRECT_IO`) — <https://gdal.org/en/stable/drivers/raster/gtiff.html>
- `GDAL_CACHEMAX`-configoptie (default 5% van het systeemgeheugen) —
  <https://gdal.org/en/stable/user/configoptions.html>
- RFC 26: GDAL Block Cache Improvements (array- vs. hashtable-cache, LRU-verdringing,
  cache/blokgrootte-rekenregel) —
  <https://gdal.org/en/stable/development/rfc/rfc26_blockcache.html>
- COG-driver (IFD-layout, `BLOCK_LEADER`, overviews, compressie-opties, lossless-lijst) —
  <https://gdal.org/en/stable/drivers/raster/cog.html>
- cogeo.org (COG-concept, interne tegeling + HTTP-range-requests) — <https://cogeo.org/>
- OGC Cloud Optimized GeoTIFF Standard (21-026), tegel-/IFD-layout-vereisten, HTTP-latentie-
  motivatie, overviews optioneel, compressie-opties —
  <https://docs.ogc.org/is/21-026/21-026.html>
- rasterio `DatasetReader.sample`/`sample_gen` (API-referentie) —
  <https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html>
- rasterio windowed reading en `block_shapes`/`block_windows` (minimale leeshoeveelheid per
  chunk) — <https://rasterio.readthedocs.io/en/stable/topics/windowed-rw.html>
- rasterio brontekst `sample.py` (per-punt `Window(col, row, 1, 1)`, geen batching,
  `sort_xy`-hulpfunctie) —
  <https://github.com/rasterio/rasterio/blob/main/rasterio/sample.py>
- libtiff `tiffcp`-documentatie (predictor-waarden 1/2/3, horizontal/floating-point
  differencing, compressietypes) — <https://libtiff.gitlab.io/libtiff/tools/tiffcp.html>
- issue #170 (deze opdracht) en issue #168 (probleemstelling, variantenlijst, harde eisen,
  gesnoeid kruisproduct) — `gh api repos/mcolee/nlriochecker/issues/170` en `.../168`
