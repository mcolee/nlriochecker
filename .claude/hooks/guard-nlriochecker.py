#!/usr/bin/env python3
"""PreToolUse-hook (nlriochecker): vier bewakingen op harde regels uit CLAUDE.md
en docs/agents/analyse-harness.md. Faalt open (bij twijfel geen output, exit 0);
parseert stdin met python3 want de losse jq-CLI staat niet op deze machine.

Edit/Write/MultiEdit:
  - naar een invoermap onder data/  -> DENY  (CLAUDE.md: nooit invoer overschrijven)
  - naar een gegenereerd bestand    -> WARN  (bewerk de generator, anders valt de drifttest)
Bash:
  - shell-redirect naar een invoermap -> DENY
  - `git commit`/`git push` op main   -> WARN (werk op dev, tenzij uitgave)
  - `git commit` met src-wijziging zonder CHANGELOG -> WARN (uitgave.py weigert lege sectie)
"""

import json
import os
import re
import subprocess
import sys


def emit(warns=None, deny=None):
    """Schrijf de hook-uitvoer en stop. deny blokkeert; warns nudget niet-blokkerend."""
    hso = {"hookEventName": "PreToolUse"}
    if deny:
        hso["permissionDecision"] = "deny"
        hso["permissionDecisionReason"] = deny
    if warns:
        hso["additionalContext"] = "Nudge (CLAUDE.md/analyse-harness): " + " ".join(warns)
    print(json.dumps({"hookSpecificOutput": hso}, ensure_ascii=False))
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool = data.get("tool_name", "")
ti = data.get("tool_input", {}) or {}
root = os.environ.get("CLAUDE_PROJECT_DIR", "") or "."

# Invoermappen die nooit overschreven mogen worden (CLAUDE.md).
INPUT_DIRS = (
    "data/gwsw_ontologieen/",
    "data/shacl_nulmeting/",
    "data/gwsw_orox_ttl/",
    "data/gwsw_opmaak/",
    "data/gis_dewoldenhoogeveen/",
    "data/gis_koekangerveld/",
)
# Gegenereerde bestanden (analyse-harness): bewerk de generator.
GENERATED = [
    (re.compile(r"(^|/)tests/fixtures/ttl/[^/]+\.ttl$"), "scripts/maak_ttl_fixtures.py"),
    (re.compile(r"(^|/)docs/dekkingsmatrix\.md$"), "scripts/dekkingsmatrix.py"),
]


def rel(path):
    """Maak het pad repo-relatief zodat de prefixvergelijkingen kloppen."""
    if not path:
        return ""
    if root != "." and path.startswith(root):
        path = path[len(root) :]
    return path.lstrip("./")


def git(*args):
    try:
        return subprocess.run(
            ["git", "-C", root, *args],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except Exception:
        return ""


if tool in ("Edit", "Write", "MultiEdit"):
    fp = rel(ti.get("file_path", ""))
    if any(fp.startswith(d) for d in INPUT_DIRS):
        emit(
            deny=f"`{fp}` ligt in een invoermap; invoerbestanden worden nooit "
            "overschreven (CLAUDE.md). Uitvoer hoort in uitvoer/."
        )
    for rx, gen in GENERATED:
        if rx.search(fp):
            emit(
                warns=[
                    f"`{fp}` wordt gegenereerd door `{gen}` -- bewerk de "
                    "generator en regenereer, anders valt de drifttest."
                ]
            )
    sys.exit(0)

if tool == "Bash":
    cmd = ti.get("command", "")
    if not isinstance(cmd, str) or not cmd:
        sys.exit(0)

    for d in INPUT_DIRS:
        if re.search(r"(>>?|tee(\s+-a)?\s+)\s*['\"]?" + re.escape(d), cmd):
            emit(
                deny=f"schrijft naar invoermap `{d}`; invoerbestanden worden nooit "
                "overschreven (CLAUDE.md)."
            )

    warns = []
    is_commit = bool(re.search(r"\bgit\s+commit\b", cmd))
    is_push = bool(re.search(r"\bgit\s+push\b", cmd))

    if is_commit or is_push:
        branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch == "main":
            warns.append(
                "je zit op `main` -- commit/push hoort op `dev` (tenzij dit "
                "een uitgave via scripts/uitgave.py is)."
            )

    if is_commit:
        staged = git("diff", "--cached", "--name-only").splitlines()
        touches_src = any(s.startswith("src/") and s.endswith(".py") for s in staged)
        touches_changelog = "CHANGELOG.md" in staged
        if touches_src and not touches_changelog:
            warns.append(
                "src/ gewijzigd maar CHANGELOG.md niet gestaged -- zet een "
                "regel onder `## [Unreleased]` (uitgave.py weigert een lege sectie)."
            )

    if warns:
        emit(warns=warns)
    sys.exit(0)

sys.exit(0)
