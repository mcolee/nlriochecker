# Issuetracker: GitHub

Issues en specificaties van dit repo leven als GitHub-issues op `mcolee/nlriochecker`.
Gebruik de `gh` CLI voor alle bewerkingen.

## Conventies

- **Issue aanmaken**: `gh issue create --title "..." --body "..."`. Gebruik een heredoc voor een meerregelige body.
- **Issue lezen**: `gh issue view <nummer> --json title,body,labels,comments --jq '{title, body, labels: [.labels[].name], comments: [.comments[].body]}'`. Let op: de kale `gh issue view <nummer>` en `--comments` breken op gh 2.45 met *"Projects (classic) is being deprecated … repository.issue.projectCards"* -- de `--json`-vorm omzeilt dat. Filter met de ingebouwde `--jq`; de losse `jq`-CLI is op deze machine niet geïnstalleerd.
- **Issues lijsten**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`, met de passende `--label`- en `--state`-filters.
- **Reageren op een issue**: `gh issue comment <nummer> --body "..."`
- **Labels toevoegen of verwijderen**: `gh issue edit <nummer> --add-label "..."` / `--remove-label "..."`
- **Sluiten**: `gh issue close <nummer> --comment "..."`

Het repo volgt uit `git remote -v`; `gh` leidt dat vanzelf af binnen een kloon.

## Huisstijl van een issue

Een `ready-for-agent`-issue is zelf de specificatie; de agent leest niets anders vooraf. Vaste
opbouw, in deze volgorde (zie #62 en #63 als voorbeeld):

1. **Het probleem** met gemeten getallen op De Wolden, en wat het níét is (de aangrenzende
   check of het mechanisme dat er lijkt op maar iets anders doet).
2. **Wat er verandert**, met bestand:regel voor elke plek, en de keuzes die al gemaakt zijn.
3. **Verwacht effect op De Wolden** — het getal dat de agent na afloop moet meten.
4. **Waar het overal staat** — een tabel over code, config, tests, docs, `CHANGELOG.md` en een
   BO-nummer in `docs/beslislog.md` als er een domeinregel verschuift.
5. **Verificatie** — de fixture-test, de poort, de meting, en de reviewzwaarte
   (`CLAUDE.md`, Werkwijze).
6. **Aannames** die niet met de auteur zijn afgestemd; de agent corrigeert ze in een comment.

Getallen in een issue komen uit een run of uit `CHANGELOG.md`/`docs/beslislog.md`, nooit uit
het geheugen; een aanname over een vrij check-ID controleer je in de check-module
(`id = "…"`), want die nummers zijn vaak al bezet.

## Pull requests als triagekanaal

**PR's als verzoekkanaal: nee.** _(Zet op `ja` als dit repo externe PR's als functieverzoek behandelt; `/triage` leest deze vlag.)_

Staat hij op `ja`, dan lopen PR's door dezelfde labels en toestanden als issues, met de `gh pr`-equivalenten:

- **PR lezen**: `gh pr view <nummer> --comments`, en `gh pr diff <nummer>` voor de wijziging.
- **Externe PR's lijsten voor triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` en daarna alleen `authorAssociation` `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` of `NONE` houden (`OWNER`/`MEMBER`/`COLLABORATOR` laten vallen).
- **Reageren, labelen, sluiten**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub deelt een nummerreeks tussen issues en PR's, dus een kale `#42` kan beide zijn: probeer `gh pr view 42` en val terug op `gh issue view 42`.

## Als een skill zegt "publiceer naar de issuetracker"

Maak een GitHub-issue aan.

## Als een skill zegt "haal het bijbehorende ticket op"

Draai `gh issue view <nummer> --json title,body,labels,comments` (niet `--comments`: dat breekt op de projectCards-deprecation, zie boven).

## Wayfinder-operaties

Gebruikt door `/wayfinder`. De **map** is een enkel issue met **kind**-issues als tickets.

- **Map**: een enkel issue met label `wayfinder:map`, met de body Notes / Decisions-so-far / Fog. `gh issue create --label wayfinder:map`.
- **Kindticket**: een issue dat als GitHub-sub-issue aan de map hangt (`gh api` op het sub-issues-eindpunt). Waar sub-issues niet aanstaan: zet het kind in een takenlijst in de body van de map en `Part of #<map>` bovenaan de body van het kind. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Zodra het geclaimd is, wordt het ticket toegewezen aan de uitvoerende ontwikkelaar.
- **Blokkeren**: GitHub's **native issue dependencies** — de canonieke, in de UI zichtbare weergave. Een kant toevoegen met `gh api --method POST repos/<owner>/<repo>/issues/<kind>/dependencies/blocked_by -F issue_id=<blokkeerder-db-id>`, waarbij `<blokkeerder-db-id>` het numerieke **database-id** van de blokkeerder is (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _niet_ het `#nummer` en niet het `node_id`). GitHub rapporteert `issue_dependencies_summary.blocked_by` (alleen open blokkeerders — de levende poort). Waar dependencies niet beschikbaar zijn, val terug op een regel `Blocked by: #<n>, #<n>` bovenaan de body van het kind. Een ticket is vrij zodra elke blokkeerder gesloten is.
- **Frontier-query**: lijst de open kinderen van de map (`gh issue list --state open`, beperkt tot de sub-issues of de takenlijst van de map), laat alles vallen met een open blokkeerder (`issue_dependencies_summary.blocked_by > 0`, of een open issue in de `Blocked by`-regel) of met een toegewezene; de eerste in de volgorde van de map wint.
- **Claimen**: `gh issue edit <n> --add-assignee @me` — de eerste schrijfactie van de sessie.
- **Afronden**: `gh issue comment <n> --body "<antwoord>"`, dan `gh issue close <n>`, dan een contextverwijzing (gist plus link) toevoegen aan Decisions-so-far in de map.
