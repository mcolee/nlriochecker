# Voorstel: waarvoor de NWB-wegvakken gebruikt zouden kunnen worden

`data/gis/nwb_wegvakken_koekangerveld.gpkg` bevat 13 wegvakken uit het Nationaal
Wegenbestand (bronjaar 2025) binnen het studiegebied Koekangerveld. **Er is in dit
project niets mee gebouwd**: geen enkele check uit
`data/checkregister-gwsw-nulmeting-v0_7.md` is aan deze bron gekoppeld. Dit
document is het gevraagde voorstel, geen implementatie.

## Wat de bron biedt

Per wegvak onder meer: `stt_naam` (straatnaam, BAG-schrijfwijze), `wpsnaam`
(woonplaats), `wegbehnaam` en `wegbehsrt` (wegbeheerder en soort: G = gemeente),
`fow` en `frc` (functionele weg- en routeklasse), `wegtype`, `rijrichtng`,
`bag_orl` (BAG-openbareruimte-ID), `wvk_id` plus `jte_id_beg`/`jte_id_end` (de
juncties aan weerszijden) en de wegvakgeometrie als lijn.

## De sterkste kandidaat: BTR-005

> BTR-005 — Toestands- of inspectiegegevens ouder dan drempel, **gewogen naar
> risicoligging (spoor, dijk, wegfunctie)** — W, Actualiteit

Deze check vraagt letterlijk om een wegfunctie als weegfactor, en dat is precies
wat `frc` (functional road class) en `fow` (form of way) leveren. Een riool onder
een gebiedsontsluitingsweg heeft bij falen een groter gevolg dan een riool in een
doodlopende woonstraat, en mag dus een kortere inspectietermijn krijgen.

**Zo zou het werken.** Buffer elk wegvak met een instelbare afstand (de rijbaan is
niet in de NWB-lijn opgenomen; 5 tot 8 m is gebruikelijk), bepaal per streng het
wegvak met de laagste `frc` waar hij binnen valt, en gebruik die klasse als
vermenigvuldiger op de drempel uit `drempels.inspectie_maximale_leeftijd_jaar`.
Strengen die onder geen enkel wegvak liggen (achterpaden, particulier terrein)
houden de basisdrempel en krijgen dat in de melding vermeld.

**Waarom het nu niet gebouwd is.** BTR-005 staat als skelet in de engine omdat de
De Wolden-export geen inspectie- of toestandsgegevens bevat. De weging heeft geen
zin zolang er niets te wegen valt: elke streng zou dezelfde ontbreken-melding
krijgen. Zodra er inspectiedata is, is dit de eerste plek om de NWB in te zetten.

## Twee kleinere kandidaten

**ADM-003 (naamgeving) als plausibiliteitsbron, niet als toets.** Het GWSW koppelt
straten aan strengen via `gwsw:Straat` met een `Straatnaam`-kenmerk; De Wolden
gebruikt dat (1143 straten). De NWB-velden `stt_naam` en `bag_orl` maken het
mogelijk te toetsen of de straatnaam bij een streng overeenkomt met de straat waar
hij daadwerkelijk onder ligt. Dat is geen registercheck maar wel een bruikbare
kwaliteitsindicatie, en het zou als nieuwe ID aan het register toegevoegd moeten
worden in plaats van in ADM-003 geschoven — ADM-003 gaat over het *patroon* van de
identificatie, niet over de straatnaam.

**Een nieuwe EXT-check: streng buiten de openbare ruimte.** EXT-004 wil met
BRK-percelen bepalen of een streng op particulier terrein ligt. Zolang de BRK
ontbreekt is een NWB-wegvakbuffer een grove maar bruikbare benadering: een streng
die nergens binnen een wegvakbuffer valt, ligt vermoedelijk niet in de openbare
weg. Dat is nadrukkelijk zwakker dan de BRK — een riool in een groenstrook of
achterpad is niet particulier maar ligt ook niet onder een wegvak — en het is
daarom geen vervanging van EXT-004. Als het gebouwd wordt, hoort het een eigen ID
te krijgen met een expliciete kanttekening over de trefzekerheid.

## Wat de bron *niet* kan

- De NWB dekt alleen het studiegebied (13 wegvakken), net als de andere externe
  bronnen. Elke check erop kan dus alleen over Koekangerveld iets zeggen.
- De NWB legt de weg-as vast, niet de rijbaanbreedte of de verhardingsgrens. Elke
  afgeleide toets is daarmee een bufferbenadering, met de bijbehorende
  onzekerheid.
- De bron bevat geen verkeersintensiteit of asbelasting; een echte risicoweging
  vraagt meer dan `frc` alleen.

## Aanbeveling

Bouw hier nu niets mee. Neem BTR-005 op in de eerste ronde nadat er inspectiedata
beschikbaar is, en gebruik de NWB daar als weegfactor. Wil je de andere twee
ideeën, voeg ze dan eerst als nieuwe ID's aan het checkregister toe; het register
is de bron van waarheid en een check zonder registerregel hoort niet in de engine.
