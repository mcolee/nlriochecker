# De kaart en het rapport — implementatieplan (issues #13, #14, #15, #16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** de GeoPackage draagt twee objectlagen met de gebreken op het object, GWSW-conform
gesymboliseerd en met een hoverpopup, en het bevindingenrapport leest van gebied naar
detail.

**Architecture:** `uitvoer/objectkaart.py` bepaalt de status en bakt de popup;
`uitvoer/stijlen/symbolen.py` bouwt de twee QML's uit een symbolentabel;
`uitvoer/omvang.py` en `uitvoer/samenvatting.py` leveren de twee nieuwe kopsecties van het
rapport. Alles blijft uit de ene meldingenstroom komen.

**Specs:**
- `docs/superpowers/specs/2026-08-19-gpkg-twee-objectlagen-design.md` (#13)
- `docs/superpowers/specs/2026-08-19-gwsw-symbologie-en-maptip-design.md` (#14, #15)

## Global Constraints

- Eén meldingenstroom, één schrijver (`uitvoer/herkomst.py`); de sweep bewaakt dat.
- Multi-gebied-equivalentie (BO-12) en `melding_id` zonder gebied (BO-11).
- `bouwwerken.qml` en `waterdelen_zonder_zinker.qml` byte-gelijk.
- Richtinglogica (`gpkg._richting_bob`) AS IS; alleen de weergave verandert.
- Geen nieuwe afhankelijkheden, geen hardcoded drempels.
- De rapporten van `analyseer`, `dekking` en `vergelijk` blijven ongemoeid.

---

### Taak 1 (#13): status en popup

- [x] `uitvoer/objectkaart.py` met `STATUSSEN`, `bepaal_status` en `popup_html`, TDD.
- [x] `gpkg.py`: `FEATURELAGEN` en `GEOPACKAGE_STAPPEN` naar vier respectievelijk acht,
      kolommen `status` en `popup_html`, mechanisch riool en de contextring in de
      lijnenlaag, `meldinglocaties` en `mechanisch_riool` weg, `x`/`y` op `meldingen`.
- [x] Tests: statuswaarden, status tegen de meldingentabel, popupinhoud, de ring.
- [x] `ruff`, `mypy`, `pytest`; commit.

### Taak 2 (#14, #15): symbologie en maptip

- [x] `uitvoer/stijlen/symbolen.py`: symbolentabel uit de PDOK-SLD's plus de opbouwer.
- [x] `gpkg._stijl` bouwt `putten` en `strengen`, leest de andere twee.
- [x] Tests zonder QGIS (`tests/test_uitvoer_symbolen.py`) en met PyQGIS
      (`tests/test_uitvoer_qgis.py`): dekking van de typen, kleur alleen uit `status`,
      een rode pijl bij `tegen`, de maptip die op een echte feature HTML oplevert.
- [x] `ruff`, `mypy`, `pytest`; commit.

### Taak 3 (#16): het rapport

- [x] `uitvoer/omvang.py` (aantallen plus `stelseltypen`, verhuisd uit `gpkg.py`).
- [x] `uitvoer/samenvatting.py` (de vier regels met vinkje of kruisje).
- [x] `bevindingen.py`: titel, volgorde, twee herkomstblokken in het detail.
- [x] `tests/test_uitvoer_rapportopbouw.py`; `ruff`, `mypy`, `pytest`; commit.

### Taak 4: verantwoording

- [x] CHANGELOG, README, CLAUDE.md, BO-29 t/m BO-31.
- [x] Integratieverificatie op de volledige De Wolden-export, over twee CBS-buurten.
- [x] Codereview verwerkt (twee rondes).
