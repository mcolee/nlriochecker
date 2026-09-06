"""Tests voor de Markdown-tabelhulp: cellen die de tabel niet mogen breken (issue #156)."""

from __future__ import annotations

import pandas as pd

from nlriochecker.uitvoer.tabel import _cel, table


def test_cel_escapet_pipe_newline_en_html() -> None:
    """`|`, een regelovergang en `<` mogen de cel of de rij niet breken."""
    assert _cel("1 | 2") == r"1 \| 2"
    assert _cel("A\nB") == "A B"
    assert _cel("A\r\nB") == "A B"
    assert _cel("<b>x</b>") == "&lt;b>x&lt;/b>"


def test_table_houdt_een_pipe_label_in_een_cel() -> None:
    """Een label met een `|` en een regelovergang blijft één rij van drie cellen."""
    frame = pd.DataFrame([{"Nr": 1, "Label": "1 | zie ook <b>x</b>\nA", "Type": "gemengd"}])

    regels = table(frame, "Kop")

    datarijen = [r for r in regels if r.startswith("| 1 ")]
    assert len(datarijen) == 1
    rij = datarijen[0]
    # Drie cellen, dus vier pipes; de escaped `\|` telt niet als celgrens.
    assert rij.count(" | ") == 2
    assert r"\|" in rij
    assert "&lt;b>" in rij
    assert "\n" not in rij
    # Geen losgeslagen regel `| A` door de regelovergang.
    assert "| A" not in "\n".join(regels)
