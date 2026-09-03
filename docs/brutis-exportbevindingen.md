# BrutIS/Kikker: bevindingen aan de bron van de OroX-export

Notitie voor de opdrachtgever richting de leverancier van BrutIS/Kikker. nlriochecker
toetst uitsluitend de OroX-dataset en kent geen BRUTIS-kolommen; wat hier staat verandert
dus geen check, maar verklaart wel waarom sommige kenmerken in de aanlevering ontbreken
en wat de leverancier eraan kan doen. Zie issue
[#133](https://github.com/mcolee/nlriochecker/issues/133) (ATTR-019, putdiepte ontbreekt).

Onderzocht op 2026-09-03: `swodewolden.dbb` (BRUTIS-export van 27/08/26, zlib-gecomprimeerde
`$BRUTIS-CSV`-blokken), het Kikker-importlog van dezelfde aanlevering, en de kolomcode-tabel
en het Turtle-exportsjabloon uit de resource-strings van `BrutIS64.exe`. Kolombetekenissen
zijn afgeleid uit de dialooglabels in de exe en getoetst aan de verdeling van de waarden.

## 1. Putdiepte staat in de bron, maar de ORO-X-export laat hem weg

- Knooptabel (`KNOOP`, 23.889 rijen): `CAG` = lengte, `CAF` = breedte, `CAH` = hoogte, alle
  drie in mm. `CAH` is voor **10.225** knopen gevuld (9.752 van de 16.626 inspectieputten;
  mediaan 1,61 m, 5–95 % tussen 1,17 en 2,85 m). Dat is de GWSW-`HoogtePut`.
- Het exportsjabloon in de exe schrijft per put `CAF → BreedtePut`, `CAG → LengtePut`,
  `CAC → Maaiveldhoogte`, `CCD → VormPut`, materiaal en begindatum, maar **geen
  `CAH → HoogtePut`** en geen `Putdekselniveau`. De OroX van De Wolden en Hoogeveen bevestigt
  het: 20.758 × `BreedtePut`/`LengtePut`, 0 × `HoogtePut`, 0 × `Putdekselniveau`.
- Gevolg: 43 % van de putten heeft in de bron een putdiepte, 0 % in OroX. De hoogtechecks
  HGT-004/012/015/016 kunnen daardoor geen putbodem afleiden en slaan de put over.
- **Vraag aan de leverancier:** `CAH` als `gwsw:HoogtePut` exporteren (en `Putdekselniveau`
  als dat een eigen veld heeft). Zonder één meting komen er 10.225 putdieptes bij.

## 2. Bodempeil is in de bron nooit geregistreerd

- `CAD` ("Knp.Bodempeil") is voor **alle** 23.889 knopen leeg. Kikker leest leeg als
  `10000.00` en vervangt dat bij import door de laagste aansluitende BOB (dialoog
  "Putbodem-peilen corrigeren met laagste BOB-peilen?"; 21.275 vervangingen in het log).
- Dat is een dataprobleem, geen exportprobleem. Na de fix onder 1 resteren circa 10.500 putten
  zonder putdiepte in de bron.

## 3. `Overnamepunt` bestaat niet in BrutIS

- De puttypetabel (`SPU`, 30 typen) kent geen overnamepunt; de exe bevat de string
  `Overnamepunt` nergens; de OroX heeft 0 instanties.
- Het dichtstbijzijnde type is `hulppunt` (2.725 stuks). Dat draagt in de typetabel de
  GWSW-klasse "onbekend" en komt in OroX als `Inspectieput` terecht (16.626 + 2.725 ≈ 19.322
  `Inspectieput` in de export).
- Gevolg: een overnamepunt naar het waterschap is in BrutIS niet als zodanig vast te leggen.
  De nul voor `Overnamepunt` in NET-001/RVZ-006 is een gat in de aanlevering, niet in ons
  model (zie ook de correctie op issue #11).
- **Vraag aan de leverancier:** `Overnamepunt` als puttype opnemen, of `hulppunt` een
  instelbare GWSW-klasse geven.

## 4. Wat wij er níét mee doen

- Geen BRUTIS-kennis in de checks: GWSW is leidend en de tool blijft dataset-onafhankelijk.
- Geen tweede invoerbron naast de OroX om de splitsing "niet gemeten / niet geëxporteerd"
  per put te rapporteren; die splitsing staat alleen hier en in issue #133.
