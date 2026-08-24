"""Uitvoervormen van de checkbevindingen: Markdown, CSV, GeoPackage en JSON.

De orkestratie -- `schrijf_uitvoer` en `schrijf_uitvoer_gebieden`, die de vier
vormen uit dezelfde meldingenstroom schrijven -- woont in `uitvoer.schrijver`.
Deze `__init__` blijft er bewust leeg naast: zo laadt een import van een lichte
deelmodule als `uitvoer.identiteit` niet de hele uitvoerstack mee.
"""
