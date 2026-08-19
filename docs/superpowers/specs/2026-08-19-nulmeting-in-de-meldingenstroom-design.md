# Ontwerp: de SHACL-nulmeting in de meldingenstroom (issue #12)

Datum: 2026-08-19. Bron: issue #12 op `mcolee/nlriochecker`, plus de grillsessie van
diezelfde dag. Dit document legt vast wat de issuetekst openliet; de vastgelegde
ontwerpbesluiten uit het issue zijn hier niet heropend, alleen overgenomen.

## Wat er nu gebeurt

`toets --shacl` leest de nulmeting alleen om de typeringspoort te vullen
(`toetsrun._typeringspoort`). De SHACL-overtredingen zelf verdwijnen daarna. De
categorie `NULMETING` staat al in `gpkg.CATEGORIEEN` — met kolom `n_nulmeting` op
`putten` en `strengen` — maar er is geen producent.

## Gemeten uitgangssituatie (De Wolden, 2026-08-19)

Gemeten met `scripts`-loze verkenning op de drie meegeleverde rapporten en de
volledige OroX-export (23.485 knopen, 23.440 strengen):

| Rapport | Regels | Unieke focusnodes | Direct een object | Via `hasPart`/`hasAspect` omhoog | Niet herleidbaar |
|---|---:|---:|---:|---:|---:|
| Hyd | 105.582 | 32.343 | 27.554 | 3.025 | 1.764 |
| MdsPlan | 54.438 | 30.477 | 27.247 | 3.025 | 205 |
| MdsProj | 53.480 | 30.400 | 27.171 | 3.025 | 204 |

Samen 213.500 regels. Na ontdubbeling op (focus node, vorm, boodschap): **105.963
meldingen** — 87.017 `Violation` en 18.946 `Warning`. De verdeling over de
conformiteitsklassen: 53.106 in alle drie, 51.365 alleen in Hyd, 1.111 in Hyd plus
MdsPlan, 214 in MdsPlan plus MdsProj, 160 alleen MdsProj, 7 alleen MdsPlan.

Binnen één rapport is (focus node, vorm) al uniek; de boodschap in de sleutel is er
voor de ontdubbeling *tussen* rapporten, waar dezelfde vorm per CFK een andere
drempel kan noemen.

**Honderdduizend meldingen is geen modelleerfout.** Het is wat de GWSW-server
rapporteert: de top van de lijst is drie kardinaliteitsvormen die vrijwel elke
`Inspectieput` raken (`Put_HoogtePut_card`, `Rioolput_Maaiveldschematisering_card`,
`Rioolput_BergendOppervlak_card`, elk 19.322 keer op ongeveer 19,5 duizend
inspectieputten). Precies daar is de bestaande systemisch-vlag voor: zulke meldingen
zeggen iets over de export als geheel en horen niet even zwaar op de kaart te wegen
als een los gebrek.

## De openstaande keuzes, en hoe ze vallen

### K1. De join: alleen direct, of ook omhoog door de boom?

De issuetekst noemt de directe join een geverifieerd feit. Dat klopt voor 27 duizend
van de 30 duizend focusnodes, maar niet voor de eindpunten van leidingen: de
focusnode `lei2806-2807-1_lei2706_beg2706` is een `BeginpuntLeiding` die via
`hasPart` onder de orientatie `lei2806-2807-1_lei2706` hangt, die via `hasAspect`
onder de streng `lei2806-2807-1` hangt. Blijft de join strikt direct, dan raken 3.025
focusnodes (waaronder alle 1.846 `EindpuntLeiding_Knooppunt_card`-fouten) de kaart
nooit, terwijl ze wél over een bestaande streng gaan.

**Besluit: de join loopt omhoog.** Eerst direct; lukt dat niet, dan via inkomende
`hasPart`- en `hasAspect`-kanten omhoog tot een knoop of streng, met een
diepterem. Dat is dezelfde beweging die `dataset.resolve_network_node` al maakt en
die CLAUDE.md voorschrijft ("loop via hasPart omhoog tot een put"). Gemeten kost het
0,7 tot 1,6 s per rapport, dus de prijs is verwaarloosbaar.

De rem staat op zes stappen: de langste keten in de export is drie
(`beginpunt → orientatie → streng`), en zonder rem zou een cyclus in de brondata de
run laten hangen.

### K2. Wat "niet herleidbaar" betekent, en wat er dan met de melding gebeurt

Het issue noemt twee gevallen in één adem: "joinen op geen object, of object zonder
geometrie". Dat zijn twee verschillende dingen, en ze horen zich verschillend te
gedragen.

- **Geen object.** De focusnode komt nergens op uit: een klassenaam
  (`Rioolstelsel`, uit `CfkTypes_typ`) of een stelsel (`dru_geb_0`, `gm_geb_10`) dat
  geen knoop of streng is. Zo'n melding krijgt geen `object_uri`, geen locatie en
  een **leeg** `gebied` — hij is niet aan een gebied toe te wijzen. Hij blijft in
  elke gebiedsrun staan, want een losse run over dat ene gebied zou hem ook opnemen;
  dat is de equivalentie-eis van BO-12. In `totaal/` staat hij één keer, want daar
  wordt op `melding_id` ontdubbeld.
- **Object zonder geometrie.** De focusnode komt wél op een knoop of streng uit,
  maar die heeft geen punt of lijn. De melding houdt haar `object_uri` — de
  meldingentabel kan er nog op joinen — maar krijgt geen locatie. Onder een
  studiegebied valt zo'n object buiten `objecten_in_gebied` en verdwijnt de melding
  uit dat gebied, precies zoals een eigen-checkbevinding op datzelfde object.

Het rapport noemt beide aantallen apart, ook als ze nul zijn.

### K3. De dimensietag

Een SHACL-nulmeting toetst of de dataset aan een conformiteitsklasse voldoet. Dat is
`Dimension.COMPLIANCE`, en dat is het voor elke vorm gelijk: uit de vormnaam is geen
fijnere dimensie af te leiden zonder een tweede register van vorm naar dimensie te
onderhouden, en dat register zou bij elke serverwijziging achterlopen. Eén tag,
eerlijk en grof.

### K4. De identiteit van een nulmeldingsmelding

`melding_id` is een hash over check, object en de onderscheidende sleutels. De
`object_uri` is hier niet onderscheidend genoeg: twee eindpunten van dezelfde streng
herleiden naar dezelfde streng. De onderscheidende sleutels zijn daarom **de
focusnode en de boodschap** — samen precies de ontdubbelsleutel uit het issue,
minus de vorm die al in het check-ID zit.

Gevolg dat je moet kennen: herformuleert de GWSW-server een boodschap, dan verschuift
het `melding_id` van elke melding van die vorm en leest een trendvergelijking dat
eenmalig als opgelost plus nieuw. Dat is de prijs van een sleutel die de ontdubbeling
volgt; hem eruit laten zou twee verschillende overtredingen op dezelfde focusnode tot
één melding laten versmelten, en dat kost een gebrek.

### K5. Systemisch: wanneer, en tegen welke noemer

Zoals bij de eigen checks (`_is_systemisch`): het aandeel boven
`rapport.systemisch_drempel` (0,80). De groepering is **(vorm, objecttype)** — het
objecttype uit `type=` in `Detail-value`. De noemer is het aantal instanties van dat
type in de dataset (`dataset.of_class`). Zonder objecttype (drie meldingen op De
Wolden) of zonder instanties van dat type is er geen noemer en is de melding niet
systemisch; dat is de veilige kant, want een melding ten onrechte systemisch noemen
haalt hem van de kaart.

De teller telt over de **volledige export**, vóór afbakening tot een studiegebied —
dezelfde keuze als bij de eigen checks, en om dezelfde reden: anders betekent
"systemisch" iets anders naargelang er een gebied is opgegeven.

### K6. Waar de bevindingen in de code stromen

`Melding` komt uit `bouw_meldingen(run, run_datum)`, en dat is de enige plek waar
bevindingen naar uitvoer vertaald worden. De nulmetingbevindingen moeten daar dus
ook binnenkomen. Ze worden **één keer** gebouwd — over de volledige export, in
`toetsrun` naast de typeringspoort, die dezelfde nulmeting al leest — en als veld
`nulbevindingen` aan de `CheckRun` gehangen, net zoals `meetbereik`, `config` en
`analyseset` daar al hangen. `beperk_tot_studiegebied` filtert ze mee.

**Verworpen: er een `CheckOutcome` van maken.** Dan zou elke vorm een pseudo-check
zijn, zou `REGISTRY[outcome.check_id]` overal een `KeyError` geven, en zou het
bevindingenrapport 300 vormsecties krijgen. De nulmeting is een tweede bron naast het
register, geen zeventigtal extra checks.

**Verworpen: een tweede schrijver.** De vier uitvoervormen komen uit één
meldingenstroom; dat is geen afspraak maar een eigenschap van de code, en de sweep in
`tests/test_uitvoer_herkomst.py` bewaakt hem.

### K7. `CfkTypes_typ` telt mee als melding

Die vorm voedt de typeringspoort. Hij blijft ook een overtreding van de
conformiteitsklasse, dus hij wordt ook een melding — een zonder object, want zijn
focusnode is een klassenaam. Hem overslaan zou betekenen dat het rapport zwijgt over
een gebrek dat de nulmeting wél telt.

## Het contract

Het veld `cfk` op `Melding` is een toevoeging aan het geversioneerde JSON-contract:

- `SCHEMA_VERSIE` gaat van `"1.0"` naar `"1.1"` — een achterwaarts verenigbare
  toevoeging, precies het geval dat `docs/json-schema.md` als minor bump beschrijft.
- `docs/json-schema.md` krijgt het veld erbij, plus de nieuwe `bron`-waarde
  `nulmeting`, de nieuwe categorie `NULMETING` en een paragraaf over wat een
  nulmetingmelding is.
- De CSV krijgt de kolom `CFK` achteraan de bestaande kolommen (vóór `Gereedschap`,
  die `schrijf_csv` zelf aanhaakt).
- De GeoPackage-tabel `meldingen` krijgt de kolom `cfk`.
- De twee drifttests in `tests/test_uitvoer_herkomst.py` blijven groen: de eerste
  eist dat elk `Melding`-veld in het document staat, de tweede dat de geschreven
  schemaversie erin staat.

`voorstel` blijft ongeschreven.

## Wat er niet in deze stap zit

De herstructurering van het Markdown-rapport (gebiedskop, managementsamenvatting per
CFK, detail op prioriteit) is issue #16. Deze stap voegt aan het bestaande rapport
alleen toe wat het niet mag verzwijgen: hoeveel nulmetingmeldingen er zijn, hoe ze
over de conformiteitsklassen verdeeld zijn, en hoeveel focusnodes nergens op
uitkwamen.
