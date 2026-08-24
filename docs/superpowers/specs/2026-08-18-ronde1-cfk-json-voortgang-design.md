# Ontwerp ronde 1: CFK-keuze, JSON-export en voortgang

Datum: 2026-08-18. Aanleiding: de masterinstructie "nlriochecker, vier functies in drie
rondes", ronde 1. Deze ronde levert drie functies: een expliciete keuze van
conformiteitsklassen via de CLI, een machine-leesbare JSON-export van de
meldingenstroom, en zichtbare voortgang bij de zware stappen.

De masterinstructie is de opdracht; dit document legt vast hoe die in deze codebase
landt, welke drie punten erin twee lezingen toelieten, en welke keuze daar gemaakt is.

## 1. Geverifieerde feiten

Vastgesteld op de codebase van commit `796789a`, niet aangenomen:

| Feit | Waarneming |
|---|---|
| Kwaliteitspoort bij aanvang | groen: ruff schoon, 104 bestanden geformatteerd, mypy schoon over 43 bestanden, 711 tests geslaagd, 4 gedeselecteerd |
| `analyseer` kent geen meldingenstroom | werkt op `MetingAnalysis`; er komt geen `CheckRun` en dus geen `list[Melding]` aan te pas |
| `toets` kan zonder nulmeting draaien | `--shacl` is optioneel; zonder die vlag is `typing_gate_applied` onwaar |
| `vergelijk` eist nu alle drie de CFK's | `cli.py:355-356` roept `laad_nulmeting` aan met `project.nulmeting.vereiste_cfk` |
| `laad_nulmeting` accepteert een rapport voor een niet-vereiste CFK | de lus toetst alleen op dubbele CFK's en op ontbrekende vereiste CFK's |
| De sweep bewaakt regel 1 en 3 van elk Markdown-rapport | `test_uitvoer_herkomst.py` asserteert `regels[0]` en `regels[2]`; regel 5 is vrij |
| Tests op `bevindingen.md` lezen substrings, geen regelposities | `test_cli.py:445`, `test_reporting.py:129` |
| Niemand construeert `CheckConfig` of `NulmetingOptions` rechtstreeks | alles loopt via `load_check_config()`; `klassen` is al verplicht zonder default |
| `[nulmeting] vereiste_cfk` staat in `checks.toml` | regel 139, én een tweede keer als pydantic-default op `checkconfig.py:232` |

## 2. Ontwerpbesluiten

| # | Punt | Keuze |
|---|---|---|
| 1 | JSON-export op `analyseer` | Vervalt; alleen `toets` schrijft JSON |
| 2 | `--cfk` op `vergelijk` | Wel, ondanks dat eis 1 hem niet noemt |
| 3 | `toets` zonder `--shacl` | Derde toestand "niet gemeten", los van volledig en deelset |
| 4 | Drager van de CFK-keuze | Waardeobject `Meetbereik`, gebouwd door `laad_nulmeting` |
| 5 | Markering in Markdown | Nieuwe optionele parameter op `schrijf_markdown`, tekst uit `Meetbereik` |
| 6 | `vereiste_cfk`-dubbeling | Opgeheven: `nulmeting` en `vereiste_cfk` worden verplicht |
| 7 | Gereserveerd veld `voorstel` | Gedocumenteerd, niet geschreven |
| 8 | Voortgang naar stderr | Wel; dat is geen TTY-detectie maar de juiste stroom |

### 2.1 Waarom `analyseer` geen JSON schrijft

Eis 5 van functie 2 noemt `toets` én `analyseer`. Eis 2 van diezelfde functie zegt dat
de inhoud uitsluitend uit de meldingenstroom komt en dat er geen pad mag bestaan
waarlangs een schrijver zelf een `Finding` interpreteert. Die twee eisen zijn op
`analyseer` niet tegelijk waar te maken: dat commando analyseert SHACL-rapporten en
kent geen bevindingen van de eigen check-engine.

De drie uitwegen waren: een tweede schema voor `analyseer` (tweede contract, tweede
versielijn, terwijl het doel juist één stabiel contract is), dezelfde envelop met een
lege meldingenlijst (een bestand dat "nul meldingen" zegt terwijl de nulmeting er
duizenden telt), of `analyseer` erbuiten laten. Het derde is gekozen: eis 2 weegt
zwaarder dan eis 5, want eis 2 is de reden dat het contract iets waard is.

Gevolg: `--geen-json` komt alleen op `toets`. Wie de SHACL-analyse machineleesbaar wil,
heeft `geaggregeerde_meldingen.csv`.

### 2.2 Waarom `vergelijk` toch `--cfk` krijgt

Eis 5 van functie 1 wil dat `vergelijk` de CFK-set per meetmoment vastlegt en hard
weigert bij ongelijke sets, en de bijbehorende test wil dat hij "slaagt bij gelijke
deelsets". Eis 1 noemt `vergelijk` echter niet bij de commando's die `--cfk` krijgen.
Zonder vlag kan `vergelijk` nooit een deelset laden: hij eist vandaag alle drie.

De set afleiden uit de aangeleverde rapporten zou dat oplossen, maar dan vervalt daar de
harde eis zonder dat iemand erom vroeg, en een run die per ongeluk één rapport mist
slaagt voortaan stilzwijgend. Dat is precies de faalwijze die de domeinregel moet
voorkomen. Daarom krijgt `vergelijk` dezelfde vlag als de rest: zonder vlag de volle
drie-eis, met vlag de opgegeven set voor beide meetmomenten. De weigering bij ongelijke
sets blijft als tweede vangnet bestaan.

### 2.3 Waarom er een derde toestand is

`toets` draait zonder `--shacl`. Zo'n run is niet volledig gemeten, maar hem als deelset
markeren zou beweren dat er iets gemeten is. `Meetbereik` kent daarom drie toestanden en
de markering drie teksten. Dit sluit aan op de werkafspraak in `CLAUDE.md`: wat een check
niet heeft bekeken hoort in het rapport, want stilte leest als "alles gecontroleerd".

## 3. Functie 1: CFK-keuze via `--cfk`

### 3.1 Het waardeobject

In `meting.py`, naast `Nulmeting`:

```python
@dataclass(frozen=True)
class Meetbereik:
    """Tegen welke conformiteitsklassen deze run getoetst is, en of dat de volle set was."""

    volledige_set: tuple[str, ...]
    gekozen: tuple[str, ...]
    gemeten: bool

    @property
    def volledig(self) -> bool: ...  # gemeten en gekozen == volledige_set
    @property
    def ontbreekt(self) -> tuple[str, ...]: ...  # volledige_set minus gekozen
```

Beide tuples zijn gesorteerd; `Meetbereik` is de enige plek waar de gesorteerde,
kommagescheiden schrijfwijze voor de GeoPackage en de JSON vandaan komt.

`laad_nulmeting(paden, gekozen, volledige_set)` bouwt hem en `Nulmeting` draagt hem als
attribuut. Dat is het scharnier van dit ontwerp: `analyseer`, `dekking` en `vergelijk`
komen erbij via `analyse.meting.meetbereik`, zodat geen enkele schrijverssignatuur in
`reporting.py` verandert. `volledige_set` valt terug op `gekozen` als de beller hem niet
meegeeft, zodat bestaande aanroepen in tests blijven werken en "volledig" betekenen.

Alleen `toets` heeft een eigen route nodig, want daar kan de nulmeting ontbreken.
`CheckRun` krijgt `meetbereik: Meetbereik | None`, naast de al bestaande `config`,
`study_area` en `analyseset` — velden die er om dezelfde reden staan: de uitvoerlaag
heeft ze nodig en ze langs elke schrijver doorreiken is broos.

### 3.2 De CLI-optie

`--cfk` wordt meervoudig opgeefbaar op `analyseer`, `dekking`, `toets` en `vergelijk`.
De toegestane waarden komen uit `config.nulmeting.vereiste_cfk`, dat wil zeggen uit
`checks.toml`. Validatie gebeurt in het commando zelf, niet met `click.Choice`: de
toegestane waarden staan pas vast nadat `--projectconfig` gelezen is, en `click.Choice`
moet bij het opbouwen van het commando al weten wat het kiezen laat.

Een onbekende waarde is een `_CliError` die de toegestane waarden opsomt. Dubbele
waarden worden ontdubbeld, niet afgekeurd. Zonder `--cfk` is de gekozen set de volledige
set en verandert er niets.

### 3.3 Aanscherping in `laad_nulmeting`

Eis 3 verlangt dat een meegegeven rapport voor een niet-gekozen CFK een fout is en geen
stille overslag. Vandaag wordt zo'n rapport zwijgend geaccepteerd; de lus toetst alleen
op dubbelingen en op ontbrekende vereiste CFK's. Er komt een derde toets bij, met een
melding die het bestand en de CFK noemt en zegt welke set gekozen is.

Dit is strikt genomen een gedragswijziging ook zonder `--cfk`: wie vandaag een vierde
rapport van een onbekende CFK meegeeft, krijgt straks een fout. Geen enkele bestaande
test raakt dit — de fixtures kennen alleen de drie — maar het staat hier omdat eis 2
zegt dat er zonder `--cfk` niets verandert, en dit is de ene plek waar dat niet
helemaal waar is.

### 3.4 De markering

`schrijf_markdown` krijgt één nieuwe optionele parameter `markering: str | None`,
geplaatst na de herkomstregel:

```
# Checkbevindingen dewolden.ttl
                                     <- lege regel
*Gemaakt met nlriochecker 0.2.0 op 2026-08-18.*
                                     <- lege regel
**Onvolledige meting:** getoetst op Hyd, MdsPlan; MdsProj ontbreekt.
                                     <- lege regel
## Samenvatting
```

De drie teksten komen uit `Meetbereik`, niet uit een schrijver:

| Toestand | Regel |
|---|---|
| volledig | geen regel; het bestand is byte-voor-byte als nu |
| deelset | `**Onvolledige meting:** getoetst op <gekozen>; <ontbreekt> ontbreekt.` |
| niet gemeten | `**Geen nulmeting:** deze run is niet tegen de conformiteitsklassen getoetst; de typeringspoort is niet toegepast.` |

De enkelvoud/meervoud-vorm van "ontbreekt" loopt via de bestaande `taal.py`, zoals de
rest van de uitvoer dat doet.

Dat de markering op regel 5 landt is geverifieerd veilig: de sweep asserteert `regels[0]`
en `regels[2]`, en de tests op `bevindingen.md` lezen substrings.

### 3.5 CSV en GeoPackage

De CSV krijgt geen extra kolom: de CFK-set hoort bij de run, niet bij de melding.
`gwsw_run` krijgt twee velden achter de bestaande, in de volgorde waarin de kolomlijst
ze noemt:

- `cfk_set` (tekst, kommagescheiden en gesorteerd; leeg bij een niet-gemeten run)
- `volledig` (integer 0/1, zoals `typeringspoort` dat al doet)

### 3.6 `vergelijk` weigert bij ongelijke sets

`compare_metingen` krijgt de twee meetbereiken mee en weigert met een `PipelineError` die
beide sets noemt en uitlegt waarom vergelijken dan zinloos is: een daling in het aantal
meldingen die uit een kleinere getoetste set komt is geen verbetering. Geen forceer-vlag.

### 3.7 De `vereiste_cfk`-dubbeling

`checkconfig.py:232` draagt de lijst een tweede keer als pydantic-default. Dat botst met
de domeinregel dat de lijst in `checks.toml` staat en niet in de code. Hij wordt
opgeheven:

- `vereiste_cfk: list[str] = Field(min_length=1)` — verplicht, zonder default
- `nulmeting: NulmetingOptions` op `CheckConfig` — verplicht, zonder `default_factory`

Dat volgt het patroon dat `klassen: ClassRoots` al heeft. Het is veilig: niemand
construeert `CheckConfig` of `NulmetingOptions` rechtstreeks, alles loopt via
`load_check_config()`, en `checks.toml` heeft de sectie. Een projectconfig zonder
`[nulmeting]` faalt voortaan bij het laden met de bestaande `ConfigError` in plaats van
stilzwijgend op drie klassen terug te vallen — wat het gewenste gedrag is, want die
terugval was onzichtbaar.

## 4. Functie 2: `schrijf_json`

### 4.1 Plaats en sweep

`schrijf_json` komt in `uitvoer/herkomst.py`, naast `schrijf_markdown` en `schrijf_csv`.
Het bestand heet `bevindingen.json`, naast `bevindingen.md` en `bevindingen.csv`, met
een constante `FILE_CHECKS_JSON` in `uitvoer/bevindingen.py` bij de twee bestaande.

De sweep in `tests/test_uitvoer_herkomst.py` leert `json.dump(`, `json.dumps(` en
`.write_text(` kennen als verboden aanroep buiten `herkomst.py`, en de bestaande test op
de verzameling geschreven bestanden krijgt de JSON erbij. Zonder die uitbreiding zou een
tweede JSON-schrijver ongezien binnenkomen, en dat is precies wat de sweep moet
voorkomen.

### 4.2 Formaat

```json
{
  "schema_versie": "1.0",
  "gereedschap": "nlriochecker 0.2.0",
  "run_datum": "2026-08-18",
  "dataset": "dewolden.ttl",
  "cfk_set": ["Hyd", "MdsPlan"],
  "volledig": false,
  "aantal_meldingen": 2,
  "meldingen": [
    {
      "melding_id": "...",
      "check_id": "TOP-001",
      "...": "alle overige velden van de dataclass Melding, snake_case",
      "foutlocatie": [233123.45, 528901.2]
    }
  ]
}
```

- UTF-8, `ensure_ascii=False`, ingesprongen met 2 spaties, afsluitende regelovergang.
- `foutlocatie` als `[x, y]` in EPSG:28992 of `null`; er wordt niet geherprojecteerd.
- `meldingen` gesorteerd op `melding_id`, zodat twee runs op dezelfde data een diffbaar
  bestand geven.
- `cfk_set` gesorteerd; `volledig` uit `Meetbereik`. Bij een niet-gemeten run is
  `cfk_set` leeg en `volledig` onwaar.

`run_datum` en `dataset` staan zowel in de envelop als op elke melding. Dat is dubbel en
bewust: de meldingenlijst blijft een getrouwe spiegel van de dataclass — dat is wat eis 3
vraagt — en de envelop is de run-waarheid. `docs/json-schema.md` benoemt het, zodat een
lezer niet gaat zoeken naar het verschil dat er niet is.

### 4.3 Schemaversionering

`schema_versie` start op `"1.0"` en staat los van het packageversienummer. Nieuwe
optionele velden mogen binnen een versie; een verwijderd of hernoemd veld, een gewijzigde
betekenis of een gewijzigd type verhoogt het hoofdnummer. `docs/json-schema.md` legt dat
vast met een volledig voorbeeld en per veld een omschrijving.

Het veld `voorstel` wordt in dat document gereserveerd voor fase B (mutatievoorstellen
voor Kikker/BrutIS) en nu níét geschreven. Een altijd-`null` veld zou een belofte zijn die
het schema nog niet waarmaakt; een afwezig veld dat gedocumenteerd gereserveerd is, is
eerlijker en achterwaarts even goed toe te voegen.

### 4.4 CLI

`toets` schrijft de JSON standaard mee naar de uitvoermap, uit te zetten met
`--geen-json`, symmetrisch met `--geen-gpkg`. `schrijf_uitvoer` krijgt `met_json: bool =
True` en `Uitvoer` een veld `json: Path | None`. De bestaande weigering om
invoerbestanden te overschrijven geldt onverkort.

## 5. Functie 3: `voortgang.py`

### 5.1 Protocol

```python
class Voortgang(Protocol):
    def start_fase(self, naam: str, totaal: int | None) -> None: ...
    def stap(self, n: int = 1, label: str | None = None) -> None: ...
    def einde_fase(self) -> None: ...


class NulVoortgang:
    """Doet niets; de standaardwaarde overal."""


NUL_VOORTGANG: Final[Voortgang] = NulVoortgang()
```

Voortgang is weergave, geen logica. Er is geen state die een check leest en geen aanroep
die de uitkomst van een run beïnvloedt.

### 5.2 Waar geïnstrumenteerd wordt

Vier ingangen krijgen een keyword-only parameter `voortgang: Voortgang = NUL_VOORTGANG`.
Bestaande aanroepen blijven ongewijzigd werken.

| Fase | Ingang | Totaal | Stap |
|---|---|---|---|
| TTL laden | `load_dataset` | 1 + aantal ontologieën | per bestand, bestandsnaam als label |
| SHACL-rapporten | `laad_nulmeting` | aantal rapporten | per rapport |
| Checks | `run_checks` | aantal draaiende checks | per check, check-ID als label |
| GeoPackage | `schrijf_geopackage` | aantal lagen en tabellen | per laag |

rdflib geeft geen tussenstand binnen één bestand. De laadfase toont daarom
fasevoortgang en geen verzonnen percentage; dat staat in de docstring van de module en
van `load_dataset`.

Bij een cachetreffer start `laad_met_cache` géén laadfase: er wordt niets geparseerd, en
een balk die in nul seconden vol schiet liegt over waar de tijd blijft. Ook dat staat in
de docstring.

### 5.3 CLI-adapter

Een implementatie van het protocol op basis van `click.progressbar`, uitsluitend in
`cli.py`. De adapter houdt de balk open tussen `start_fase` en `einde_fase`. Bij
`totaal is None` is er geen bepaalbare lengte; dan wordt de fasenaam één keer geëchood in
plaats van een balk getoond. Er komt geen eigen TTY-detectie bij: click degradeert zelf.

De balk schrijft naar **stderr**. Dat is de juiste stroom voor voortgang en het houdt de
geschreven paden en tellingen op stdout schoon, zodat wie de uitvoer van `toets` pipet
daar geen balkresten in krijgt.

Bekend risico: `click.progressbar` echoot in niet-interactieve omgevingen het label één
keer. Als een bestaande CLI-test op exacte uitvoer asserteert kan dat bijten. Dat blijkt
bij het draaien van de suite; treedt het op, dan wordt het gemeld en opgelost, niet
weggeconfigureerd met een eigen TTY-toets.

Er komt geen `--geen-voortgang`-vlag. Niemand heeft erom gevraagd en click zet de balk in
een niet-interactieve omgeving al uit.

## 6. Volgorde van uitvoering

CFK eerst, want de JSON-envelop heeft `cfk_set` en `volledig` nodig. Daarna de JSON,
daarna de voortgang. Per functie test-eerst, per werkende stap een commit.

## 7. Tests

**Functie 1**

1. Deelsetrun levert de markering in Markdown en de velden `cfk_set` en `volledig` in
   `gwsw_run`.
2. Rapport voor een niet-gekozen CFK faalt met een melding die bestand en CFK noemt.
3. Ontbrekend rapport voor een gekozen CFK faalt (bestaand gedrag, nu ook op een
   deelset).
4. Standaardrun zonder `--cfk` levert byte-voor-byte hetzelfde als voorheen.
5. Onbekende `--cfk`-waarde faalt en somt de toegestane waarden op.
6. `vergelijk` weigert bij ongelijke sets met een melding die beide sets noemt, en
   slaagt bij gelijke deelsets.
7. `toets` zonder `--shacl` levert de niet-gemeten-markering, lege `cfk_set` en
   `volledig` onwaar.
8. Een projectconfig zonder `[nulmeting]` faalt met een `ConfigError`.

**Functie 2**

9. Rondrit: schrijven en herlezen levert alle meldingvelden identiek aan de
   meldingenstroom.
10. De envelop draagt herkomst, schemaversie en CFK-set; `volledig` klopt bij een
    deelset.
11. Twee identieke runs met dezelfde `run_datum` geven identieke bestanden; de
    sortering op `melding_id` is stabiel.
12. `voorstel` komt in geen enkele melding voor.
13. `--geen-json` laat het bestand achterwege; zonder de vlag staat het er.
14. De sweep vangt een tweede JSON-schrijver in `src/` af.

**Functie 3**

15. Met `NulVoortgang` zijn alle uitvoerbestanden identiek aan de situatie zonder
    voortgangscode.
16. Een opnamecallback ontvangt de fasen in de verwachte volgorde en het verwachte
    aantal stappen; in de checksfase is het aantal stappen gelijk aan het aantal
    checks.
17. Een cachetreffer start geen laadfase.
18. CLI-rooktest: `toets` op een kleine fixture draait met de adapter zonder fouten.

## 8. Afronding

1. `CHANGELOG.md`: de drie functies onder `## [Unreleased]`, in de rubrieken
   Toegevoegd en Gewijzigd.
2. `README.md`: `--cfk`, `--geen-json` en een verwijzing naar `docs/json-schema.md`.
3. `docs/json-schema.md`: nieuw, met volledig voorbeeld, veldbeschrijvingen, de
   versioneringsregel en het gereserveerde veld `voorstel`.
4. `docs/beslislog.md`: vier vermeldingen — de CFK-versoepeling met de voorwaarde dat
   elke afwijking gemarkeerd wordt, het JSON-stabiliteitscontract, het buiten scope
   laten van `analyseer` bij de JSON-export, en het verplicht maken van `[nulmeting]`.
5. `CLAUDE.md`, domeinregels: standaard alle drie de CFK's, een deelset alleen
   expliciet en altijd gemarkeerd.
6. Reviewstappen: `/superpowers:requesting-code-review`, daarna
   `/python-library-complete:reviewing-python-libraries`; bevindingen verwerken vóór de
   afsluitende commit.
7. Kwaliteitspoort schoon. Versienummer blijft 0.2.0; uitbrengen gaat apart via
   `scripts/uitgave.py`.
