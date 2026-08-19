# Domeinwoordenboek

De termen waarmee dit project over vrijvervalriolering praat, en waar ze vandaan
komen. De bron is de GWSW-ontologie (`data/gwsw_ontologieen/Ontologie_GWSW_Totaal.ttl`)
en het checkregister (`data/checkregister-gwsw-nulmeting-v0_8.md`). Staat een begrip
hier, gebruik dan dit woord -- in code, in bevindingsteksten en in issues.

Dit bestand beschrijft alleen begrippen waarover verwarring mogelijk is of geweest is.
Een term die eenduidig uit de ontologie volgt hoeft hier niet herhaald te worden.

## Put

`gwsw:Put`. Het fysieke object. Subklassen die in de De Wolden-export voorkomen zijn
onder meer `Inspectieput`, `Lozingsput`, `Overstortput`, `Valput` en `LozePut`; die
lopen alle via `gwsw:Rioolput` of `gwsw:Aansluitput`.

In de code: `selectie.putten()`, uit `[klassen] put`.

## Netwerkknoop

De objecten die in de netwerkdefinitie als knoop meedoen: de put, plus de afvoer- en
lozingseindpunten (gemaal, pompunit, lozingsput, uitlaatconstructie) en de
bergbezinkvoorzieningen. Een bergbezinkbassin is in het GWSW een `gwsw:Bouwwerk` en
geen put, maar het water loopt er wel doorheen.

**Dit is geen `gwsw:Knooppunt`.** Die klasse bestaat, maar is de *orientatie* en niet
het object: haar subklassen zijn `Putorientatie`, `Bouwwerkorientatie`,
`Hulpstukorientatie` en `Aansluitpunt`. Een `gwsw:Put` is dus geen `gwsw:Knooppunt`;
zijn orientatie is dat. De ontologie kent geen klasse die deze rol dekt, dus
"netwerkknoop" is een rolnaam van dit project.

In de code: `selectie.netwerkknopen()`, uit `[klassen] netwerkknopen`. Enger dan dit
is `putten()`; die twee zijn niet uitwisselbaar, en
`tests/test_checks_selectie.py::test_putten_zit_echt_binnen_netwerkknopen` bewaakt dat.

## Leiding

`gwsw:Leiding`. Alles wat transporteert, inclusief pers-, druk- en vacuumleiding.

In de code: `selectie.leidingen()`, uit `[klassen] streng` -- die configuratiesleutel
draagt nog de oude naam.

## Vrijvervalrioolleiding

`gwsw:VrijvervalRioolleiding`: een gesloten rioolleiding waarin het afvalwater door de
zwaartekracht getransporteerd wordt. Een echte deelverzameling van *leiding*. De
overstort-, bergbezink- en infiltratieleiding zijn subklassen en horen er dus bij.

In de code: `selectie.vrijvervalrioolleidingen()`, uit `[klassen] vrijvervalleiding`.

## Streng

Vakjargon voor de riolering tussen twee putmiddelpunten, en als zodanig het gangbare
woord in rapportteksten en in het checkregister. **Het is geen GWSW-klasse.**
`gwsw:Streng` bestaat niet; wat wel bestaat is `gwsw:Rioolstreng`, een
`RepresentatieFysiekObject` met als NEN 3300-omschrijving "aanduiding voor de riolering
tussen het hart van een put en het hart van een volgende put (niet noodzakelijk de
eerstvolgende)".

Gebruik "streng" dus wel in proza, maar niet als naam voor een klassenselectie: wat
daar geselecteerd wordt is een `gwsw:Leiding` of een `gwsw:VrijvervalRioolleiding`.

## Rol

Een verzameling GWSW-klassen die de checks als een geheel behandelen, vastgelegd in
`[klassen]` van de projectconfiguratie. Sommige rollen vallen samen met een
GWSW-klasse (*put*, *leiding*); andere niet (*netwerkknoop*, *bergbezinkvoorziening*,
*valconstructie*). Bij die laatste zegt de docstring van de selectiefunctie expliciet
dat het om een rol gaat, zodat de naam niet als ontologieterm gelezen wordt.

Alle rollen staan in `src/nlriochecker/checks/selectie.py`, elk als een functie. Er is
met opzet geen generieke opzoeking op naam; zie BO-20 in [de beslislog](docs/beslislog.md).
