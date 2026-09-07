# AHN-bemonstering: rasterindeling × leesstrategie, koud en warm gemeten (2026-09-07)

**Vraag:** stap 1 van issue #168 -- welke bestandsindeling van het AHN6-DTM (strips, tiles
van 256/512/1024, DEFLATE/ZSTD/LZW met `PREDICTOR=3`; float32 blijft) en welke leesstrategie
(`sample_many` zoals hij is, sortering per tegel, grotere GDAL-blokcache, eigen vensterlezer)
geven de kleinste koude én warme leestijd voor de 22.356 putten van De Wolden en Hoogeveen,
onder de harde eis dat elke waarde bit-gelijk aan de referentie blijft. Het deskresearch
(stap 0, `2026-09-06-puntbemonstering-float32-raster.md`) had de COG-varianten al geschrapt;
de overige zes bestandsvarianten en alle leesstrategieën zijn gemeten.

**Antwoord in één zin:** tiles van 256×256 zonder compressie winnen op elke as (koud 23 → 6,6–
8,5 s, warm 2,6 → 1,0–2,1 s op de bemonstering; volle `toets` koud 119,6 → 103,9 s, dus
−15,7 s / −13%, sha-gelijk); compressie verliest omdat decompressie meer kost dan de I/O die
ze bespaart; een grotere GDAL-blokcache helpt nergens; de eigen vensterlezer (L3) is de
snelste leesstrategie maar wint bovenop het betere bestand nog maar 1–2 s.

## 1. Opzet

- **Meetscript:** `scripts/meet_raster_bemonstering.py` (dev, a23b312; codestand `src/`
  8e00b38, gwsw-orox-helpers 0.2.4, GDAL 3.8.4, rasterio 1.5.1). Standen `punten`, `bouw`,
  `meet`, `gepaard`; de leesstrategieën L1 en L3 staan er als prototype in, `src/` is niet
  aangeraakt.
- **Meetpunten:** de selectie van `_AhnCheck.monstertabel` (HGT-001) via `scripts/harnas.py`:
  **22.356** putten (het issue noemt 22.357; het verschil van één is de typeringspoort, het
  harnas laadt zonder `--shacl`). Alle punten liggen binnen het raster, nul nodata.
- **Referentie:** het origineel (strips van 1 rij, 9,64 GB) met L0 = `RasterSampler.sample_many`
  zoals hij in `src/` staat. Elke meting is n=3, om en om met de referentie, elk in een eigen
  proces (lege GDAL-blokcache per meting), sequentieel achter `flock`.
- **Koud:** vóór elke meting `posix_fadvise(POSIX_FADV_DONTNEED)` over het hele bestand, van
  referentie én variant; het meetproces meet met `mincore` de nog residente fractie en die
  was in alle koude metingen **0,000**. Alleen het raster is koud: de leeslaag-cache, de
  GeoPackages en de Python-packages bleven warm, zodat de meting precies de variabele isoleert.
- **Warm:** vlak vóór elke meting hetzelfde bestand met dezelfde strategie één keer in een
  wegwerpproces doorlopen. Twee bestanden van 9,6 GB om en om passen niet samen in 16 GB;
  bij tiles 1024 (4 MiB per tegel, 40–50% van het bestand geraakt) zie je dat terug in een
  dalende residente fractie en een spreiding van 2,8–4,1 s.
- **Bit-gelijk:** `np.array_equal(..., equal_nan=True)` over de per positie teruggegeven
  waarden; alle 46 gemeten combinaties waar, sha256 van de reeks overal
  `3856797a605056d0…`.
- **Leesstrategieën:** L0 huidige code; L1 punten gesorteerd op `(rij // blockysize,
  kolom // blockxsize)` uit `reader.block_shapes`, zelfde `reader.sample`, inverse permutatie
  terug; L2 = `GDAL_CACHEMAX=2048` (MB) via `rasterio.Env` op L0 en L1; L3 per geraakte tegel
  één `reader.read(window=…)` en de punten daaruit indexeren, met dezelfde `rowcol`-afronding
  (floor) en dezelfde buiten-raster-afhandeling als rasterio's `sample_gen`. Alle drie leiden
  de blokgrootte uit het bestand af en vereisen geen indeling (harde eis 2).

Wat afweek van het plan: de Sonnet-meetagents draaiden hun metingen in de achtergrond en de
geheugenwatchdog van deze machine kilde die (de paginacache vult zich per koude meting met
gigabytes); varianten #1 en #2 kwamen zo binnen, #3 half, en de rest is op de voorgrond
gemeten. De eerste build van #6 (LZW) bleef als afgebroken restant van 73 MB staan; de drie
metingen daarop gaven `bitgelijk=False` en zijn geschrapt, het bestand is geforceerd
herbouwd en opnieuw gemeten. Niet gemeten, op aanwijzing van de auteur (07-09, "skip
variant 6, richt je op de winnaar"): L1+cachemax op #6, en L2 op de strip-referentie (#0);
gezien het beeld hieronder (cachemax helpt nergens en schaadt met compressie) verandert dat
niets aan de uitkomst.

## 2. Bemonstering: bestand × leesstrategie (beste van n=3, seconden)

| # | bestand | grootte | bouw | koud L0 | koud L1 | koud L3 | koud L0 +cache | koud L1 +cache | warm L0 | warm L1 | warm L3 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | strips 1 rij (referentie) | 9,64 GB | -- | 22,3–24,7 | -- | -- | n.g. | -- | 2,5–3,4 | -- | -- |
| 1 | **tiles 256** | 9,66 GB | 62 s | 8,5 | 7,7 | **6,6** | 8,6 | 7,6 | 2,1 | 2,1 | **1,0** |
| 2 | tiles 512 | 9,66 GB | 61 s | 10,3 | 8,5 | 7,7 | 10,8 | 8,3 | 2,3 | 2,2 | 1,2 |
| 3 | tiles 1024 | 9,87 GB | n.v. | 14,7 | 10,8 | 10,2 | 16,5 | 10,7 | 2,8 | 2,8 | 2,8 |
| 4 | tiles 512 DEFLATE p3 | 3,53 GB | 109 s | 17,1 | 13,6 | 12,4 | 35,3 | 13,0 | 11,6 | 9,9 | 8,7 |
| 5 | tiles 512 ZSTD p3 | 3,46 GB | 123 s | 13,8 | 10,8 | 9,6 | 24,9 | 10,2 | 8,2 | 7,1 | 6,0 |
| 6 | tiles 512 LZW p3 | 4,67 GB | 89 s | 25,2 | 20,0 | 18,8 | 55,9 | n.g. | 18,3 | 15,2 | 14,2 |

Referentie per blok: koud min 22,3–23,6, warm min 2,5–2,7 (de kolom voor #0 geeft de
spreiding over alle 46 blokken). "n.g." = niet gemeten; "n.v." = bouwtijd niet vastgelegd (log
overschreven door de herstart na de kill). Bouwtijden met `NUM_THREADS=ALL_CPUS`, 4 cores.
Alle cellen bit-gelijk; alle koud-cellen eenduidig (traagste van de een sneller dan snelste
van de ander); warm waren #3 L1 en L3 níét eenduidig (spreiding door paginacachedruk), de
rest wel. Volledige reeksen: `uitvoer/meting_168/resultaten.csv` en `log_v*.txt`.

Als verbetering ten opzichte van nu (strips + huidige code; koud 22,8 s, warm 2,6 s;
positief = sneller):

| # | koud L0 | koud L1 | koud L3 | warm L0 | warm L1 | warm L3 |
|---|---|---|---|---|---|---|
| 1 tiles 256 | +63% | +66% | **+71%** | +19% | +19% | **+62%** |
| 2 tiles 512 | +55% | +63% | +66% | +12% | +15% | +54% |
| 3 tiles 1024 | +36% | +53% | +55% | −8% | −8% | −8% |
| 4 DEFLATE | +25% | +40% | +46% | −346% | −281% | −235% |
| 5 ZSTD | +39% | +53% | +58% | −215% | −173% | −131% |
| 6 LZW | −10% | +12% | +18% | −604% | −485% | −446% |

## 3. Volle `toets` met de winnaar (bestandsas alleen, code ongewijzigd)

Dezelfde vlaggen als `docs/checks-audit-2026-08.md:20` (drie SHACL-rapporten,
`--projectconfig`, `--bronnen`), `/usr/bin/time`, projectconfig gekopieerd met alleen
`ahn_dtm` omgezet; koud = raster met `posix_fadvise` geleegd (resident 0,0), warm = de run
direct erna.

| bestand | koud | warm | maxrss |
|---|---|---|---|
| strips (nu) | 119,6 s | 99,7 s | 2,98 GB |
| tiles 256 | **103,9 s** | 101,9 s | 2,98 GB |

Koud **−15,7 s (−13%)**, boven het kill-criterium van ≥10 s of ≥10%. Warm is het verschil
ruis (de bemonstering is dan 2 van de 100 s). Het echte effect is dat de koude straf van het
AHN vrijwel verdwijnt: een eerste run van de dag is even snel als een herhaalrun. Alle vier
de runs zijn sha-gelijk aan `uitvoer/07092026_slotrun_F` (codestand 8e00b38):
`scripts/vergelijk_csv.py` GELIJK (`52ed74b2…`, 161.661 rijen) en `bevindingen.json` na
`del(.run_datum)` gelijk (`15c8a5c9…`). Het issue noemde slotrun B (1ebcaa1) als referentie;
sindsdien wijzigde #165 de CSV-vorm, dus F is de juiste sha-referentie voor deze codestand.

## 4. Wat de cijfers zeggen

1. **Kleinere tegel wint, en de onverklaarde 126 s uit #149 was geen tiling.** Tiles 512
   zijn koud twee keer zo snel als de strips (10,3 tegen 22,8 s), niet trager. De eigen
   berekening in het stap-0-verslag (§2: "vrijwel elke tegel wordt geraakt, dus 9,66 GB
   gelezen") klopt niet voor deze puntverdeling: de warme residente fractie laat zien hoeveel
   van het bestand werkelijk gelezen wordt -- strips 44% (4,3 GB), tiles 512 31% (3,0 GB),
   **tiles 256 16% (1,6 GB)**, tiles 1024 40–50%. Putten liggen geclusterd langs strengen; een
   kleine tegel deelt in twee richtingen en kost per misser het minst. De 126 s van #149 moet
   dus een andere oorzaak hebben gehad (paginacachedruk van een eerdere run is de voor de hand
   liggende; niet gereconstrueerd).
2. **Compressie verliest, warm hard.** DEFLATE en ZSTD lezen 2,7 keer minder bytes maar
   betalen decompressie per uniek blok, en die CPU-kost (8–12 s warm) is groter dan de I/O
   die ze koud besparen; ZSTD decodeert sneller dan DEFLATE, LZW is op elke as de slechtste
   en zelfs koud trager dan de strips. Dat de GDAL-blokcache gedecodeerde pixels per proces
   bewaart (stap 0, §3) is precies waarom warm hier niets helpt: elke `toets`-run start met een
   lege blokcache.
3. **`GDAL_CACHEMAX` omhoog helpt nergens en schaadt met compressie.** Op de ongecomprimeerde
   tiles ±0,3 s (ruis); op DEFLATE/ZSTD/LZW koud L0 wordt het 2 keer zo traag (35, 25, 56 s).
   Dat laatste is niet verder onderzocht (L2 valt hoe dan ook af); een grotere cache dwingt
   GDAL vermoedelijk tot het vasthouden van gedecodeerde blokken die het anders weggooit, en
   dat geheugenverkeer kost meer dan de herlezing bespaart.
4. **Leesstrategie: L3 > L1 > L0, overal, maar de marge is klein zodra het bestand goed is.**
   Op tiles 256: L1 wint 0,8 s koud en niets warm; L3 wint 1,9 s koud en 1,1 s warm. Op de
   gecomprimeerde bestanden is de winst van L3 groter (3–6 s) omdat elke tegel dan maar één
   keer gedecodeerd wordt, maar die bestanden vallen af. Dat L3 warm van 2,1 naar 1,0 s gaat
   bevestigt de analyse van stap 0 (§5): de vaste overhead van `sample_gen` per punt (127 µs
   × 22.356) is ruim de helft van de warme tijd.

## 5. Aanbeveling (hooguit één per as)

- **Bestandsas: tiles 256×256, geen compressie, float32, BigTIFF** (`gdal_translate -co
  TILED=YES -co BLOCKXSIZE=256 -co BLOCKYSIZE=256 -co BIGTIFF=YES`, 62 s, gelijke grootte).
  Boven het kill-criterium (−15,7 s / −13% koud op de volle run, bit- en sha-gelijk). Wordt
  een advies in `docs/gebruik.md` ("zo leest het sneller"), geen eis: de package leest elk
  raster dat rasterio opent. De auteur besloot op 07-09 `configs/dewoldenhoogeveen.toml` naar
  het getilede bestand te laten wijzen (BO-99); het heet nu
  `data/gis_dewoldenhoogeveen/AHN6_DeWoldenHoogeveen_DTM_tiles256.tif` (niet getrackt, naast
  het origineel; de andere varianten zijn verwijderd).
- **Leesstrategie-as: L3 (vensterlezer) niet bouwen.** Hij is de snelste, maar bovenop tiles
  256 wint hij nog 1,9 s koud en 1,1 s warm op een run van 104 s -- onder het kill-criterium.
  Daar staat een eigen lezer tegenover die de `rowcol`-afronding en de randafhandeling van
  rasterio moet blijven spiegelen. Wil de auteur die 1–2 s toch, dan is het een klein
  `ready-for-agent`-issue met deze cijfers als bewijslast; L1 en L2 vallen af.

## 6. Bronnen en bestanden

- Issue #168 (opzet, harde eisen, kill-criterium), #170 en
  `docs/onderzoek/2026-09-06-puntbemonstering-float32-raster.md` (stap 0).
- `scripts/meet_raster_bemonstering.py` (a23b312); `uitvoer/meting_168/` (git-ignored):
  `resultaten.csv`, `log_v1..6.txt`, `punten.npy`, de waardenreeksen per meting (`*.npy`),
  de vier `toets`-runs `toets_{ref,v1}_{koud,warm}/` met `.log`.
- Referentierun `uitvoer/07092026_slotrun_F` (8e00b38).
