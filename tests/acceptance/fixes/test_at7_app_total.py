"""mvp-fixes AT-7: a review given the user's app total keeps it in the log, with whether it differed; the
record says in how many rounds it matched, from the first round with one; a line logged before the slice
still reads (R5.1 to R5.3)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from fantadamus.domains.review import LoggedReview
from fantadamus.lake.review_log import ReviewLog
from tests.integration.review.test_tool import review
from tests.lineup_harness import a_round, finished

pytestmark = pytest.mark.anyio

ROUND_9 = dt.datetime(2026, 10, 20, 9, 0, tzinfo=dt.UTC)


def _from_before(log: ReviewLog) -> None:
    """Round 9's review, as the log kept it before this slice: the advice followed, no app total."""
    line = LoggedReview(
        user="user-1",
        team="mine",
        round=9,
        as_of=ROUND_9,
        logged_at=ROUND_9,
        replayed=False,
        advice_expected=66.0,
        fielded_expected=66.0,
        advice_real=68.0,
        fielded_real=68.0,
        total_cost=0.0,
        total_gain=0.0,
        choices=[],
        content_hashes=[],
    )
    kept = json.loads(line.model_dump_json())
    del kept["app_total"], kept["app_differs"]
    log.root.mkdir(parents=True, exist_ok=True)
    (log.root / "2026-10.jsonl").write_text(json.dumps(kept) + "\n", encoding="utf-8")


async def test_at7_the_record_says_how_often_the_app_matched(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        log = ReviewLog(here.store.root / "reviews")
        _from_before(log)
        await here.ask()
        finished(here)
        first = (await review(here, as_advised=True))["review"]
        real = first["real"]
        matched = (await review(here, app_total=real))["review"]
        asked_again = (await review(here))["review"]
        differs = (await review(here, app_total=real + 3.0))["review"]
        lines = log.read()
    assert first["record"]["rounds"] == 2  # round 9's line, from before the slice, reads
    assert (first["record"]["app_rounds"], first["record"]["app_note"]) == (0, None)  # nothing to say yet
    assert matched["app_differs"] is False
    assert matched["record"]["app_note"] == "Your app's total matched in 1 of 1 round."
    assert asked_again["record"]["app_note"] == "Your app's total matched in 1 of 1 round."  # not dropped
    assert differs["app_differs"] is True
    assert (differs["record"]["app_rounds"], differs["record"]["app_matched"]) == (1, 0)
    assert differs["record"]["app_note"] == "Your app's total matched in 0 of 1 round."
    assert [(line.round, line.app_total, line.app_differs) for line in lines] == [
        (9, None, None),
        (10, None, None),
        (10, real, False),
        (10, None, None),
        (10, real + 3.0, True),
    ]
