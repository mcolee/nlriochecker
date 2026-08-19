# Inventarisatie externe geodata (`data/gis_koekangerveld/`)

Opgemaakt op 2026-08-16 op de aangeleverde bestanden. Alles is gelezen met
`sqlite3` (GeoPackage-metadata), `geopandas`/`pyogrio` (features) en `rasterio`
(hoogteraster). Er is niets gedownload en er is geen vervangende bron gezocht.

## Wat er is, en wat het bereik ervan is

**Alle bronnen dekken uitsluitend het studiegebied Koekangerveld**, een kern van
43,2 ha binnen de gemeente De Wolden. De GWSW-dataset beslaat de hele gemeente
(23.485 knooppunten, 23.440 strengen). Dat verschil is het belangrijkste feit uit
deze inventarisatie: een GWSW-object buiten Koekangerveld zonder BGT-deksel of
BAG-pand in de buurt is geen bevinding maar een gevolg van ontbrekende brondata.
De engine filtert daarom eerst op het studiegebied; alles daarbuiten krijgt de
status *buiten studiegebied* en geen check-uitslag.

| Bestand | Formaat | CRS | Lagen (features) | Gekoppeld aan |
| --- | --- | --- | --- | --- |
| `cbs_buurt_koekangerveld_studiegebied.gpkg` | GeoPackage | EPSG:28992 | `buurt_gegeneraliseerd` (1) | begrenzing van alle EXT- en AHN-checks |
| `BGT.gpkg` | GeoPackage | EPSG:28992 | 49 lagen, 12 gevuld (zie hieronder) | EXT-001, EXT-002, EXT-003, EXT-005, EXT-006, EXT-007 |
| `bag_pand_koekangerveld.gpkg` | GeoPackage | EPSG:28992 | `output` (166) | EXT-001 (aanvulling) |
| `nwb_wegvakken_koekangerveld.gpkg` | GeoPackage | EPSG:28992 | `output` (13) | geen registercheck; zie `docs/nwb-voorstel.md` |
| `ahn5_dtm_koekangerveld.tif` | GeoTIFF | EPSG:28992 | 1617 x 1833 cellen van 0,5 m | HGT-001, HGT-002, HGT-003 |

Alle vijf bestanden staan al in RD New (EPSG:28992). **Er is niets
geherprojecteerd.** De lader controleert het CRS van elk bestand en herprojecteert
alleen een bron met een correct gedefinieerd afwijkend CRS; een bron zonder CRS
wordt geweigerd in plaats van als RD aangenomen. Voor het hoogteraster geldt een
strengere regel: dat wordt nooit geherprojecteerd, want dat verandert de ligging
van de meetwaarden.

## Studiegebied

`cbs_buurt_koekangerveld_studiegebied.gpkg`, laag `buurt_gegeneraliseerd`, een
CBS-buurtvlak.

- `statcode` `BU16901203`, `statnaam` `Koekangerveld`, `gmCode` `GM1690`, jaar 2025.
- Oppervlak 43,2 ha, omhullende (218637, 525338) tot (219445, 526255) in RD.
- Een enkele polygoon; er is geen laagkeuze nodig.

Dit vlak is de begrenzingspolygoon waarop de GWSW-objecten gefilterd worden
voordat een EXT- of AHN-check draait.

## BGT

`BGT.gpkg` bevat 49 feature-lagen, waarvan er 37 leeg zijn. De twaalf gevulde:

| Laag | Features | Geometrie | Rol in de engine |
| --- | ---: | --- | --- |
| `pand` | 199 | multipolygoon | `bgt_pand` — EXT-001 |
| `waterdeel` | 233 | polygoon | `bgt_water` — EXT-002, EXT-003, EXT-007 |
| `ondersteunendwaterdeel` | 94 | polygoon | `bgt_water` — idem |
| `wegdeel` | 192 | polygoon | geen check |
| `begroeidterreindeel` | 429 | polygoon | geen check |
| `onbegroeidterreindeel` | 136 | polygoon | geen check |
| `ondersteunendwegdeel` | 107 | polygoon | geen check |
| `pand_nummeraanduiding` | 98 | punt | geen check |
| `openbareruimtelabel` | 39 | punt | geen check |
| `gebouwinstallatie` | 40 | polygoon | `bgt_bouwwerk` — EXT-001 |
| `overigbouwwerk` | 11 | polygoon | `bgt_bouwwerk` — EXT-001 |
| `kunstwerkdeel_vlak` | 1 | polygoon | `bgt_bouwwerk` — EXT-001 |

**De laag `put` bestaat wel maar bevat nul features.** Dat is de BGT-laag met de
putdeksels. EXT-005 (put zonder BGT-putdeksel) en EXT-006 (BGT-putdeksel zonder
put) kunnen daardoor niet draaien; beide melden *laag niet aanwezig in
aangeleverde data* en worden overgeslagen. Ze zijn wel volledig geïmplementeerd:
zodra er een BGT-export met gevulde `put`-laag komt, draaien ze zonder wijziging.

Bruikbare attributen: `type` en `plus_type` (bij `waterdeel` bijvoorbeeld
`waterloop`), `status` (`bestaand`), `relatieve_hoogteligging`, `lokaal_id` en
`bronhouder`. De engine gebruikt `type` in de melding bij EXT-002 en EXT-003 en
`lokaal_id` als identificatie bij EXT-006.

## BAG-panden

`bag_pand_koekangerveld.gpkg`, laag `output`, 166 multipolygonen.

Attributen: `identificatie` (BAG-pand-ID), `bouwjaar`, `status`,
`aantal_verblijfsobjecten`, `gebruiksdoel`, `geconstateerd`.

**Er zijn panden aangeleverd en geen verblijfsobjecten.** De laag voedt EXT-001
als aanvulling op de BGT-panden: beide dekken het gebied grotendeels maar niet
volledig, en de check gebruikt de vereniging van de twee lagen. Het veld
`aantal_verblijfsobjecten` staat in de export maar wordt niet gebruikt: EXT-008
(BAG-verblijfsobject zonder riolering binnen X m) is sinds checkregister v0.8
vervallen — de dekkingsvraag hoort bij het rioleringsplan, niet bij deze toets.
Zie `data/checkregister-gwsw-nulmeting-v0_8.md`.

## NWB-wegvakken

`nwb_wegvakken_koekangerveld.gpkg`, laag `output`, 13 multilijnen, bronjaar 2025.

Rijk aan attributen (`stt_naam`, `wegbehnaam`, `wegbehsrt`, `fow`, `frc`,
`wegtype`, `rijrichtng`, `wvk_id`, `jte_id_beg`/`jte_id_end`). **Geen enkele check
uit het register is aan deze bron gekoppeld**, dus er is niets mee gebouwd. Een
voorstel voor welke registercheck ze zouden kunnen voeden staat in
`docs/nwb-voorstel.md`.

## AHN5 DTM

`ahn5_dtm_koekangerveld.tif`, GeoTIFF, één band, `float32`.

- CRS EPSG:28992, celgrootte 0,5 bij 0,5 m, 1617 bij 1833 cellen.
- Omhullende (218637,0, 525338,0) tot (219445,5, 526254,5) — precies het
  studiegebied.
- Waardebereik 2,19 tot 8,29 m NAP over de gevulde cellen.
- `nodata` staat op 3,4028235e+38 (de `float32`-sentinel). Ruim 1,23 miljoen van de
  2,96 miljoen cellen zijn nodata; dat is normaal voor een DTM, waar alles onder
  gebouwen en begroeiing weggefilterd is.

De bemonstering slaat cellen met de nodata-waarde over, en ook waarden buiten
±1e6, zodat een sentinel zonder nodata-vlag nooit als maaiveldhoogte kan
doorgaan. HGT-001 t/m HGT-003 melden in hun toelichting hoeveel putten binnen het
studiegebied op een nodata-cel vielen.

## Bronnen die niet aangeleverd zijn

| Bron | Gevolg |
| --- | --- |
| BRK-percelen | EXT-004 is skelet met de markering *bron buiten scope in deze fase*. |
| Waterschapsdata (watergangen, overstortnormen) | EXT-002 draait alleen op BGT-waterdelen; het register staat die bron expliciet toe. |
| BGT-putdeksels (`put`-laag leeg) | EXT-005 en EXT-006 worden overgeslagen met de melding *laag niet aanwezig in aangeleverde data*. |
| Beheergebiedpolygoon | TOP-009 toetst wel het RD-bereik maar niet het beheergebied; het studiegebied is daar geen vervanging voor. |
| Grondsoortenkaart | BTR-003 blijft skelet; de drempel per grondsoort is niet te differentiëren. |

## Configuratie

Welke laag welke rol vervult staat in `src/nlriochecker/checks.toml` onder
`[bronnen]`. De laagnamen zijn per project aan te passen; een lege of ontbrekende
laag laat de bijbehorende checks overslaan met de melding *laag niet aanwezig in
aangeleverde data*. Alle bufferafstanden staan onder `[drempels]`
(`ext_pand_buffer_m`, `ext_watergang_buffer_m`, `ext_putdeksel_afstand_m`,
`ext_lozingspunt_water_afstand_m`, `ext_perceel_buffer_m`).
