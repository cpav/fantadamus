"""mvp-store task 5.1: a generated season around the synthetic round, as the lake keeps one: month files,
`_table.json` and the logs, at the size the requirements' glossary gives (design C7; R5.1). The timing process
grows it once for the whole run, and says what it holds and what each answer gave."""

from __future__ import annotations

from typing import Any

from tests.season import ANSWERS, IN_WINDOW, LISTED, MATCHES, OUTLETS, READS, RUNS, STATISTICS


def test_the_season_has_its_size(timings: dict[str, Any]) -> None:
    size = timings["season"]["size"]
    assert MATCHES * len(OUTLETS) * LISTED == 2_200  # rows a read
    assert size["outlet_rows"] > READS * 2_200
    assert size["outlet_reads"] == READS + 1  # and the round's own
    assert size["window_reads"] == IN_WINDOW
    assert 200_000 < size["largest_month"] < 300_000  # a month: about a quarter of a million rows
    assert size["statistics_reads"] == STATISTICS + 1
    assert size["runs"] > RUNS
    assert size["answers"] == ANSWERS + 1
    assert size["bronze"] < 20  # the round's own: the season has none


def test_the_round_still_answers(timings: dict[str, Any]) -> None:
    assert timings["season"]["statuses"] == {
        "lineup": "lineup",
        "compare": "answer",
        "outlook": "outlook",
        "card": "card",
        "overview": "overview",
    }
