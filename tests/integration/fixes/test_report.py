"""mvp-fixes task 1.5: a failed page is shown as failed, with its cause, and as tried again, both in the run's
lines and in the refresh plan's note (design C4; R1.5)."""

from __future__ import annotations

import datetime as dt

from fantadamus.cli.__main__ import _page_lines
from fantadamus.mcp.advisor import tried_notes
from fantadamus.web.collector import CollectReport, PageReport

AT = dt.datetime(2026, 11, 21, 5, 1, tzinfo=dt.UTC)
URL = "https://site.example/statistiche-serie-a"
FAILED = PageReport(
    url=URL,
    page="statistics",
    outcome="failed",
    reason="robots.txt couldn't be read (timed out)",
    for_claude=["player_season"],
)


def test_a_failed_page_is_shown_with_its_cause_and_retry() -> None:
    assert _page_lines(FAILED) == [
        f"{URL}: failed (robots.txt couldn't be read (timed out)): tried again at the next run",
        "  for Claude, through read_page: player_season",
    ]
    refused = FAILED.model_copy(update={"outcome": "disallowed", "reason": f"robots.txt disallows {URL}"})
    assert (
        _page_lines(refused)[0] == f"{URL}: disallowed (robots.txt disallows {URL})"
    )  # a refusal isn't retried


def test_the_refresh_note_says_it_tries_again() -> None:
    notes = tried_notes(CollectReport(started_at=AT, finished_at=AT, round=None, pages=[FAILED]))
    assert notes["player_season"] == (
        f"Fantadamus couldn't read {URL}: failed (robots.txt couldn't be read (timed out)); "
        "it tries again at its next run"
    )
