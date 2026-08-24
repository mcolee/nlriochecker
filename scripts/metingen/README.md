# scripts/metingen -- eenmalig meetwerk

Hier staan scripts die een vraag beantwoorden die één keer beantwoord moest worden,
plus de uitvoer waarmee ze dat deden. Ze zijn geen onderdeel van het pakket.

De afspraken:

- **Niets in `src/nlriochecker/` mag hieruit importeren.** Andersom mag wel: een
  meting mag de pakketlader gebruiken om zichzelf te ijken.
- **De testsuite draait ze niet en mypy kijkt er niet naar.** `[tool.mypy] files` in
  `pyproject.toml` noemt alleen `src/nlriochecker`. Ruff wel: die loopt over de hele
  repository, dus lint en opmaak blijven ook hier groen. Dat is een opmaakpoort, geen
  gedragspoort -- niets toetst wat een meting uitrekent.
- **Ze mogen breken zonder dat iemand ze repareert.** Een meting hoort bij de dataset,
  de ontologie en de configuratie van het moment waarop ze gedraaid is; verandert daar
  iets, dan is het antwoord verouderd en niet het script kapot. Wie de vraag opnieuw
  wil stellen, herleest eerst wat er gemeten is.
- **De uitvoer ligt naast het script**, als `<naam>.txt`. Dat is nodig omdat de
  invoer het niet is: `data/` staat op twee uitzonderingen na buiten versiebeheer, dus
  niemand anders dan de auteur kan een meting nadraaien. Zonder de vastgelegde uitvoer
  ligt in de repository wel de redenering maar niet het getal waarop een besluit rust.

## Wat er staat

| Script | Vraag | Uitvoer |
| --- | --- | --- |
| `issue32_klassendekking.py` | Wat zouden de in issue #32 voorgestelde `[klassen]`-lijsten op de De Wolden-export doen? | `issue32_klassendekking.txt` |
