# Project: nlriochecker

## Doel
Python-package dat de datakwaliteit van vrijvervalriolering toetst in twee lagen:
1. Inlezen en analyseren van GWSW-nulmeting-detailrapporten (conformiteitsklassen Mds/MdsPlan en Hyd).
2. Eigen aanvullende checks conform het checkregister (data/checkregister-gwsw-nulmeting-v0_7.md) op de GWSW-dataset (OroX/TTL) en later externe bronnen.

We bouwen gefaseerd: eerst een kleine werkende MVP (fase 1), daarna uitbouwen. Implementeer nooit meer dan de actuele fase vraagt.

## Domeinregels (hard, uit het checkregister v0.7)
- De dataset moet ALTIJD aan beide conformiteitsklassen (CFK's) getoetst zijn: Mds (of MdsPlan) EN Hyd. De verplichte administratieve put-strengkoppeling rust volledig op Hyd. Ontbreekt een van beide rapporten, dan faalt de pijplijn met een duidelijke foutmelding.
- Typeringspoort: meldingen van het type "Objecttype te globaal voor deze CFK" maken vervolgvalidaties voor die objecten onbetrouwbaar. De pijplijn berekent een typeringsscore en rapporteert deze prominent als kwaliteitsvoorwaarde.
- Alle drempelwaarden (toleranties, min/max-waarden, bufferafstanden) zijn configureerbaar per project via een configbestand (TOML of YAML). Geen hardcoded drempels.
- Check-ID's uit het checkregister (TOP-001 enz.) zijn stabiel; vervallen ID's worden nooit hergebruikt.
- Ernstniveaus: F = fout, W = waarschuwing. Elke check heeft een dimensietag (Consistentie, Compleetheid, Plausibiliteit, Actualiteit, Traceerbaarheid, Precisie).

## Feiten over de invoerbestanden (detailrapporten, geverifieerd)
- CSV met puntkomma (;) als scheidingsteken, encoding Windows-1252 (cp1252). NIET utf-8 aannemen.
- Regel 1 is een titelregel, bijvoorbeeld:
  ;Detailrapport GWSW-Nulmeting van dataset DeWolden (Toetsing aan CFK: MdsPlan) (dd 2026-08-14T14:06:53)
  Parse hieruit: datasetnaam, CFK en tijdstempel.
- Regel 2 is de header: Aantal;Type Melding;Type object;Naam;Type aspect;Opmerking
- Aantal is een integer (aggregatiegewicht). Naam kan leeg zijn of een object-ID bevatten. Voorbeeldmeldingen: "Collectie-item onbekend", "Ontbrekende relatie [hasAspect]", "Objecttype te globaal voor deze CFK [type = onvoldoende]".
- Testbestanden: data/dewolden_nulmeting.csv (MdsPlan, ~22k regels) en data/dewolden_nulmeting_1.csv (Hyd, ~44k regels).

## Technische afspraken
- Python 3.12+, src-layout (src/gwswpijplijn/), pyproject.toml, beheer met uv.
- Afhankelijkheden minimaal houden. Fase 1: pandas, click (CLI), pydantic (config). Pas rdflib, shapely en networkx toe vanaf fase 3, niet eerder.
- Tests met pytest. Fixtures: kleine uittreksels (20-50 regels) van de echte rapporten, plus een integratietest op de volledige De Wolden-bestanden.
- Codekwaliteit: ruff (lint en format), type hints overal, Nederlandse docstrings, Engelse code-identifiers.
- CLI-ingang: gwswpijplijn (via entry point), subcommands per functie.
- Rapportage-output: Markdown en CSV naar een output-map; nooit invoerbestanden overschrijven.

## Werkwijze
- Kleine stappen, na elke werkende stap een git-commit met een duidelijke boodschap.
- Bij twijfel over domeinlogica: raadpleeg eerst data/checkregister-gwsw-nulmeting-v0_7.md; verzin geen eigen interpretaties.
- Voer na elke wijziging pytest en ruff uit voordat je afrondt.
