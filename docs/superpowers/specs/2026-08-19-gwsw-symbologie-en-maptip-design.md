# Ontwerp: GWSW-symbologie en hoverpopup (issues #14 en #15)

Datum: 2026-08-19. Bron: issues #14 en #15 op `mcolee/nlriochecker` plus de grillsessie
van diezelfde dag. Ze raken dezelfde twee bestanden en staan daarom in één ontwerp; de
uitvoering blijft per issue gescheiden.

## Wat er nu staat

`putten.qml` tekent drie ronde markers naar `ergste_ernst`, `strengen.qml` drie
lijnkleuren plus drie richtingsregels. Geen van beide zegt iets over het GWSW-type van
het object, en `tegen` krijgt twee tegengestelde pijlen (blauw voor de tekenrichting,
rood voor het verval).

## Wat het wordt

Symbool naar GWSW-objecttype, kleur uitsluitend naar de kolom `status` uit issue #13,
één richtingpijl per streng, en een maptip die `popup_html` toont.

## De openstaande keuzes, en hoe ze vallen

### K1. De SVG's uit de PDOK-SLD's zijn er niet

De aangeleverde SLD's (`data/gwsw_opmaak/PDOK; *.sld`) verwijzen hun symbolen niet
als bestand maar als `ExternalGraphic` naar `https://data.gwsw.nl/img/<naam>.svg`. Die
bestanden staan niet in de repository en zijn niet meegeleverd. Ze ophalen zou dit
pakket van een netwerkbron afhankelijk maken en bovendien symbolen van een derde in
onze uitvoer bakken.

Issue #14 voorziet dit geval met zoveel woorden: *"is een SVG niet parametriseerbaar,
herteken hem dan als eenvoudige marker in de GWSW-vorm"*. **Besluit: elk symbool wordt
een QGIS-`SimpleMarker`.** De SLD's blijven de bron voor de *indeling* — welk
objecttype welk symbool krijgt en welke typen samen één symbool delen — en die
indeling staat in de tabel in `stijlen/symbolen.py`, met bij elke regel de SLD-naam
die hij vervangt.

### K2. De QML's worden opgebouwd, niet met de hand geschreven

De regelstructuur die het issue voorschrijft is **objecttype × status**. De
De Wolden-export telt 13 knooptypen en 16 verbindingstypen; met een vangnet erbij en
vier statuswaarden zijn dat 56 respectievelijk 68 bladregels, elk met een eigen
symbool. Met de hand is dat ruim vijftienhonderd regels XML waarin een tikfout de
kaart stil leegtrekt, en waarin de typenlijst op twee plekken zou staan.

**Besluit: de twee QML's worden opgebouwd uit een tabel**, in
`src/nlriochecker/uitvoer/stijlen/symbolen.py`. De stijlen blijven daarmee in
`src/nlriochecker/uitvoer/stijlen/` staan, zoals het issue vraagt; alleen zijn ze daar
een tabel plus een opbouwer in plaats van twee grote XML-bestanden.
`bouwwerken.qml` en `waterdelen_zonder_zinker.qml` blijven onaangeroerde bestanden --
byte-gelijk, zoals het issue eist.

De waarborg is de PyQGIS-test: hij laadt de opgebouwde stijl in een echte QGIS en
controleert dat elke regel een symbool heeft, dat elke expressie naar een bestaande
kolom verwijst, en dat elk objecttype uit de dataset een regel heeft.

### K3. Welk symbool bij welk type

Uit de SLD's, met de shape die hem vervangt. Wat niet in de tabel staat valt in het
vangnet: een open cirkel met een kruis erin, gelabeld "objecttype niet in de
symbolentabel". Geen stille default -- een onbekend type moet als onbekend te zien
zijn.

Voor **verbindingen** kan het symbool het type maar half dragen. Het GWSW en de
PDOK-SLD onderscheiden leidingsoorten met kleur (gemengd oranje, vuilwater rood,
hemelwater blauw), en die kleur is hier vergeven aan de status. Wat overblijft is
lijndikte en streepjespatroon, en daarmee zijn zestien typen niet uit elkaar te
houden. **Besluit: elk type krijgt zijn eigen regel met zijn eigen legendalabel, maar
verwante typen delen een lijnstijl.** De legenda blijft dus volledig -- je kunt elk
type opzoeken -- en het kaartbeeld onderscheidt de families: vrijverval, mechanisch,
aansluiting, drain, duiker, berging, loos.

### K4. De statuskleuren

Kleurenblind-veilig, en rood tegen groen ook op helderheid te onderscheiden:

| Status | Kleur | Helderheid (L\*) | Betekenis in de legenda |
|---|---|---:|---|
| `rood` | `#b2182b` | donker | fouten |
| `oranje` | `#e08214` | midden | alleen waarschuwingen |
| `groen` | `#4d9221` | midden-licht | geen eigen gebrek |
| `grijs` | `#9e9e9e` | licht, laag verzadigd | niet geanalyseerd |

Rood is duidelijk donkerder dan groen, dus ook in grijstinten en bij deuteranopie
blijven ze uit elkaar te houden. Grijs is als enige onverzadigd en valt daarmee weg
uit de reeks -- precies wat "niet beoordeeld" hoort te doen.

De legenda van groen zegt **"geen eigen gebrek"** en niet "in orde": een object
waarvan alle meldingen systemisch zijn is groen (BO-29), en de legenda mag dat niet
verzwijgen.

### K5. De richtingpijl

De logica blijft ongewijzigd (`gpkg._richting_bob`, kolom `richting_bob`); alleen de
weergave verandert.

- `mee` → één groene pijl met de lijnrichting mee, **klein** (1,8). Dit is het normale
  geval: op een echte kaart draagt vrijwel elke streng een pijl, en een pijl die groter
  is dan het putsymbool overstemt precies datgene waar de kaart over gaat. Dat is met
  een echte PyQGIS-render vastgesteld en daarna bijgesteld van 3,0 naar 1,8.
- `tegen` → één **rode** pijl, gedraaid over 180°, zodat hij in de BOB-vervalrichting
  wijst: waar het water werkelijk heen loopt. Groter (3,0) dan de andere twee, want dit
  is de uitzondering en die mag opvallen. De dubbele pijl (blauw voor de tekenrichting,
  rood voor het verval) vervalt.
- `onbekend` → één grijze pijl met de lijnrichting mee.

De pijlkleur staat los van de statuskleur van de lijn; beide lagen het symbool over
elkaar, zoals de huidige `strengen.qml` al doet.

### K6. De maptip (issue #15)

`<mapTip enabled="1">` in beide objectlaag-QML's, zoals het referentiebestand
`data/gwsw_opmaak/voorbeeld_maptip_qgis344.qml` het op regel 1085 doet.

De inhoud is één expressie -- `[% "popup_html" %]` -- met daaromheen wat niet per rij
herhaald hoort te worden: een `<style>`-blok en een `<div style="width:300px">`. Die
vaste breedte houdt het popupframe stil in plaats van bij elk object te herschalen.
Het stijlblok staat één keer in de QML en niet in elke rij van de kolom: op De Wolden
zou een stijlblok per object de GeoPackage tientallen megabytes groter maken zonder
dat er iets bij komt.

Geen live joins of relations in de expressie: die reizen niet mee in `layer_styles`.
Geen webfont en geen afbeelding-URL: de popup moet zelfstandig reizen.

**UX-feit dat gedocumenteerd moet worden:** map tips verschijnen alleen als "Show Map
Tips" in de QGIS-werkbalk aan staat. Zonder die aanwijzing leest "geen popup" als
kapot. Komt in de README.

### K7. Hoe dit geverifieerd wordt

Het issue vraagt handmatige verificatie in QGIS 3.44. Die vervangen we door de
PyQGIS-test (`tests/test_uitvoer_qgis.py`), die op deze machine echt draait: hij laadt
de GeoPackage als `QgsVectorLayer`, past de default-stijl toe en leest de renderer en
de maptip terug. Dat toetst harder dan een blik op het scherm -- een ontbrekend
symbool of een expressie naar een niet-bestaande kolom valt er meteen uit -- maar het
zegt niets over of het er *goed uitziet*. Daarvoor is de kaart tijdens de bouw een keer
met `QgsMapRendererParallelJob` naar een PNG gerenderd en bekeken; dat leverde één
bijstelling op (de pijlgrootte hierboven). Het eindoordeel blijft aan de gebruiker.
