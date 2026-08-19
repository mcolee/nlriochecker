"""De herkomst van een uitvoerbestand: welk gereedschap het schreef.

Elk bestand dat deze package oplevert draagt de naam en het versienummer van de
package die het maakte. Zonder die vermelding is een rapport dat een half jaar
later opduikt niet meer te plaatsen: de checks veranderen, en een bevindingenlijst
zonder versie is niet te herleiden tot de logica die hem opleverde.

De vier uitvoervormen zeggen het met dezelfde string uit dezelfde bron, elk in de
vorm die zijn formaat verdraagt: een regel onder de titel in Markdown, een kolom
op elke rij in de CSV, een veld in `gwsw_run` in de GeoPackage, een veld in de
envelop van de JSON. Naam en versie komen uit de packagemetadata; ze staan nergens
een tweede keer opgeschreven.

`schrijf_markdown`, `schrijf_csv` en `schrijf_json` zijn de enige schrijvers van
deze package. Wie hier langsgaat draagt zijn herkomst; wie zelf `to_csv`,
`write_text` of `json.dump` aanroept niet, en dat merkt niemand.
`tests/test_uitvoer_herkomst.py` bewaakt dat er in `src/` geen tweede schrijver
bijkomt.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from nlriochecker import __version__

# De pakketnaam uit de modulenaam zelf, om hem niet naast `pyproject.toml` een
# tweede keer op te schrijven -- dezelfde reden waarom het versienummer uit de
# packagemetadata komt. Deze package is al een keer hernoemd.
PAKKET = __name__.split(".", 1)[0]

# De kolomnaam in de CSV's. De GeoPackage gebruikt snake_case, net als haar andere
# kolommen; de waarde erin is dezelfde.
KOLOM_GEREEDSCHAP = "Gereedschap"
VELD_GEREEDSCHAP = "gereedschap"

# De versie van het JSON-contract, los van het versienummer van deze package. Een
# afnemer pint hierop, niet op de packageversie: de checks mogen veranderen zonder
# dat het formaat dat doet. Zie `docs/json-schema.md` voor de versioneringsregel.
SCHEMA_VERSIE = "1.1"


def gereedschap() -> str:
    """De herkomststring: pakketnaam en versie, zoals elk uitvoerbestand hem draagt."""
    return f"{PAKKET} {__version__}"


def herkomstregel(run_datum: date | None = None) -> str:
    """De regel die in elk Markdown-rapport onder de titel komt."""
    return f"*Gemaakt met {gereedschap()} op {run_datum or date.today():%Y-%m-%d}.*"


def schrijf_markdown(
    pad: Path,
    titel: str,
    regels: list[str],
    run_datum: date | None = None,
    markering: str | None = None,
) -> Path:
    """Schrijft een Markdown-rapport als titel, herkomstregel en de meegegeven regels.

    De renderers leveren alleen de romp; de kop komt hiervandaan. Zo kan geen
    rapport zonder herkomst het bestand halen doordat een schrijver de kop vergeet.

    `markering` is de plek voor een voorbehoud dat de hele run raakt, zoals een
    meting op een deelverzameling conformiteitsklassen. Hij staat hier en niet in de
    romp, zodat geen enkel rapport hem kan overslaan; zonder markering blijft de kop
    exact zoals hij was.
    """
    kop = [titel, "", herkomstregel(run_datum), ""]
    if markering:
        kop += [markering, ""]
    pad.write_text("\n".join([*kop, *regels]) + "\n", encoding="utf-8")
    return pad


def schrijf_csv(tabel: pd.DataFrame, pad: Path) -> Path:
    """Schrijft een tabel als CSV met de herkomstkolom achteraan.

    De kolom staat op elke rij in plaats van in een commentaarregel bovenaan, zodat
    pandas, Excel en QGIS het bestand zonder extra opties blijven lezen -- de
    kolommen `ObjectURI` en `Object2URI` bevatten GWSW-URI's met een `#`, en
    `read_csv(comment="#")` zou die stilzwijgend afkappen.

    Een tabel zonder rijen krijgt wel de kolomkop maar geen enkele waarde; de
    herkomst van zo'n bestand staat dan alleen in het Markdown-rapport ernaast.
    """
    if KOLOM_GEREEDSCHAP in tabel.columns:
        raise ValueError(
            f"de tabel voor {pad.name} draagt zelf al een kolom {KOLOM_GEREEDSCHAP!r}; "
            "hernoem die, anders overschrijft de herkomst hem stilzwijgend."
        )
    tabel.assign(**{KOLOM_GEREEDSCHAP: gereedschap()}).to_csv(
        pad, sep=";", index=False, encoding="utf-8"
    )
    return pad


def schrijf_json(
    pad: Path,
    meldingen: list[dict[str, object]],
    *,
    run_datum: date,
    dataset: str,
    cfk_set: list[str],
    volledig: bool,
    typeringspoort_toegepast: bool,
    gebied: str | None = None,
    gebieden: list[str] | None = None,
) -> Path:
    """Schrijft de meldingenstroom als JSON, met een envelop die de run beschrijft.

    Bedoeld als stabiel contract voor een afnemer die er mutatievoorstellen uit
    afleidt. De meldingen komen kant-en-klaar binnen via `meldingen_json`; deze
    functie interpreteert geen enkel veld, precies zoals `schrijf_csv` een
    kant-en-klare tabel krijgt. Zo kan de JSON niet uit de pas lopen met de andere
    drie uitvoervormen.

    De sortering op `melding_id` maakt twee runs op dezelfde data diffbaar; zonder
    haar is elke trendvergelijking tussen twee bestanden ruis. Zie
    `docs/json-schema.md` voor de veldbeschrijvingen en de versioneringsregel.

    `typeringspoort_toegepast` staat in de envelop omdat elke melding anders
    `typering_betrouwbaar: true` draagt, ook als de poort nooit gedraaid heeft: zonder
    nulmeting is er niets wat een object onbetrouwbaar kan verklaren. Een afnemer die
    dat veld meeweegt, moet kunnen zien of het gemeten is of alleen niet weerlegd.

    `allow_nan=False`: een NaN-coordinaat zou als `[NaN, 1.0]` in het bestand komen,
    wat geen geldige JSON is en door een strikte parser geweigerd wordt. Luid falen is
    beter dan stil een onleesbaar contract wegschrijven.

    `gebied` en `gebieden` horen bij de rapportage per studiegebied-feature: de JSON
    van een gebied noemt zijn eigen naam, die van de totaalsynthese `gebied: null`
    plus de lijst gebieden waarover hij gaat. Een run zonder gebieden krijgt geen van
    beide velden, zodat zo'n bestand byte-voor-byte blijft zoals het was; een afnemer
    die de velden leest, moet ze dus als optioneel behandelen (zie
    `docs/json-schema.md`).
    """
    document: dict[str, object] = {
        "schema_versie": SCHEMA_VERSIE,
        "gereedschap": gereedschap(),
        "run_datum": run_datum.isoformat(),
        "dataset": dataset,
    }
    if gebieden is not None:
        document["gebied"] = None
        document["gebieden"] = list(gebieden)
    elif gebied is not None:
        document["gebied"] = gebied
    document |= {
        "cfk_set": list(cfk_set),
        "volledig": volledig,
        "typeringspoort_toegepast": typeringspoort_toegepast,
        "aantal_meldingen": len(meldingen),
        "meldingen": sorted(meldingen, key=lambda rij: str(rij["melding_id"])),
    }
    tekst = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    pad.write_text(tekst + "\n", encoding="utf-8")
    return pad
