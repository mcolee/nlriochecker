# Voorbeeld Koekangerveld

Een compleet, klein voorbeeld om `nlriochecker toets` op te draaien: de buurt
Koekangerveld in de gemeente De Wolden, met de bijbehorende SHACL-nulmeting en externe
bronnen. GEGENEREERD met `scripts/maak_voorbeeld.py`; bewerk deze bestanden niet met de
hand, maar draai de generator opnieuw.

## Draaien

```
nlriochecker toets \
  --dataset voorbeelden/koekangerveld/koekangerveld_orox.ttl \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_Hyd.csv \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_conformiteit_MdsPlan.csv \
  --shacl voorbeelden/koekangerveld/gwsw_shacl_report_MdsProj.csv \
  --studiegebied voorbeelden/koekangerveld/cbs_buurt_koekangerveld_studiegebied.gpkg \
  --projectconfig voorbeelden/koekangerveld/koekangerveld.toml \
  --bronnen voorbeelden/koekangerveld \
  --output uitvoer/voorbeeld
```

## Wat erin zit

- De **analyseset** van de buurt zoals `toets --studiegebied` hem afbakent: kern
  (98 objecten) plus contextschil (118), van
  46925 objecten in de volledige export.
- Hun **onderdelen, orientaties en stelsels**: samen 8455 triples over
  2977 subjecten.
- De **SHACL-nulmeting** op alle drie de conformiteitsklassen, teruggebracht tot de
  1247 regels die op een object in dit voorbeeld uitkomen, plus de
  `CfkTypes_typ`-regels van de typeringspoort.
- De **externe bronnen** BGT, BAG, NWB en TOP10NL, bit voor bit zoals ze voor de hele
  buurt aangeleverd zijn; de EXT-checks geven hier dus dezelfde uitslag als op de
  volledige export.

| Bestand | Omvang |
|---|---|
| `BGT.gpkg` | 4,90 MB |
| `bag_pand_koekangerveld.gpkg` | 0,20 MB |
| `cbs_buurt_koekangerveld_studiegebied.gpkg` | 0,11 MB |
| `gwsw_shacl_report_MdsProj.csv` | 0,13 MB |
| `gwsw_shacl_report_conformiteit_Hyd.csv` | 0,19 MB |
| `gwsw_shacl_report_conformiteit_MdsPlan.csv` | 0,13 MB |
| `koekangerveld.toml` | 0,03 MB |
| `koekangerveld_orox.ttl` | 0,36 MB |
| `nwb_wegvakken_koekangerveld.gpkg` | 0,13 MB |
| `top10nl_plaats_vlak_koekangerveld.gpkg` | 0,10 MB |

## Wat er niet in zit

- **Het hoogteraster (AHN).** Dat extract is 12 MB en past niet in een repository. HGT-001
  tot en met HGT-003 melden daardoor zelf dat ze niets konden toetsen; het rapport zegt
  dat in de verantwoording.
- **De SHACL-regels zonder herleidbaar object.** Een overtreding waarvan de focusnode
  geen put of streng is -- een gemeentebreed stelsel -- gaat niet mee. Ze zouden in het
  rapport blijven staan zonder object en zonder gebied, en horen bij de volledige export
  en niet bij deze buurt.
- **De rest van de gemeente.** Een check die over de hele export gaat in plaats van over
  losse objecten (ADM-002 op dubbele identificaties, ATTR-014 en ATTR-015) ziet hier
  alleen deze buurt en kan dus minder vinden dan op de volledige export.

## Herkomst en licenties

- **`koekangerveld_orox.ttl`** -- uitsnede uit de OroX-export van de gemeente De Wolden (BrutIS).
  Met toestemming van de gemeente gepubliceerd; besluit van de auteur, 29-08-2026.
- **`gwsw_shacl_report_*.csv`** -- de GWSW-nulmeting op diezelfde export, gedraaid via
  [apps.gwsw.nl](https://apps.gwsw.nl/item_validate_shacl). Zelfde herkomst en
  toestemming.
- **`BGT.gpkg`** en **`bag_pand_koekangerveld.gpkg`** -- BGT en BAG via PDOK, CC0.
- **`nwb_wegvakken_koekangerveld.gpkg`** -- Nationaal Wegenbestand (Rijkswaterstaat), CC0.
- **`top10nl_plaats_vlak_koekangerveld.gpkg`** -- TOP10NL (Kadaster), CC-BY 4.0.
- **`cbs_buurt_koekangerveld_studiegebied.gpkg`** -- CBS-buurtkaart, CC-BY 4.0 (CBS).

De GWSW-ontologie waarmee `toets` de klassenhierarchie leest zit niet in deze map: zij
reist als package-resource mee met `gwsw-orox-helpers` en is CC0.
