"""mvp-next-round P1 and P2: the fixtures are due a day after the round page's last answered read, whatever is
stored, and with runs every 15 minutes the next round is read within a day and a run of the page showing it
(design; R1.1 to R1.3, R2.2, R2.3)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.lake.collect_log import ANSWERED, newest
from fantadamus.web.cadence import due
from fantadamus.web.collector import CollectReport, Outcome, PageReport

NOW = dt.datetime(2026, 11, 25, 18, 0, tzinfo=dt.UTC)
MINUTE = dt.timedelta(minutes=1)
A_DAY = 24 * 60
"""Minutes."""
ANSWERS: list[Outcome] = sorted(ANSWERED)
ago = st.integers(min_value=-60, max_value=30 * A_DAY)


def _tried(minutes_ago: int, outcome: Outcome) -> CollectReport:
    at = NOW - minutes_ago * MINUTE
    page = PageReport(url="https://site.example/round", outcome=outcome)
    return CollectReport(started_at=at, finished_at=at, round=None, pages=[page])


@given(
    answered=st.lists(ago, max_size=5),
    failed=st.lists(ago, max_size=5),
    answer=st.sampled_from(ANSWERS),
    kickoff=st.none() | ago,
    confirmed=st.booleans(),
)
def test_p1_due_a_day_after_the_last_answered_read(
    answered: list[int], failed: list[int], answer: Outcome, kickoff: int | None, confirmed: bool
) -> None:
    """Failed tries don't hold the read back, an answered one always does for a day, and no kickoff or
    official lineup changes it."""
    runs = [_tried(minutes, answer) for minutes in answered]
    runs += [_tried(minutes, "failed") for minutes in failed]
    last = newest(runs, NOW, "round", ANSWERED)
    past = [minutes for minutes in answered if minutes >= 0]
    when = None if kickoff is None else NOW - kickoff * MINUTE
    assert due("fixtures", last, NOW, when, confirmed=confirmed) == (not past or min(past) >= A_DAY)


@given(
    by_answers=st.lists(st.integers(min_value=0, max_value=10 * A_DAY), max_size=6),
    moves_on=st.integers(min_value=0, max_value=10 * A_DAY),
    offset=st.integers(min_value=0, max_value=14),
)
def test_p2_the_next_round_is_read_within_a_day_and_a_run(
    by_answers: list[int], moves_on: int, offset: int
) -> None:
    """Runs every 15 minutes from `offset`, and answers' own reads of the page before it moves on: the first
    read at or after `moves_on` comes at most a day and a run later."""
    pending = sorted(minute for minute in by_answers if minute < moves_on)
    last: dt.datetime | None = None
    minute = offset
    while True:
        while pending and pending[0] <= minute:
            read = NOW + pending.pop(0) * MINUTE
            last = read if last is None else max(last, read)
        if due("fixtures", last, NOW + minute * MINUTE, None):
            last = NOW + minute * MINUTE
            if minute >= moves_on:
                break
        minute += 15
        assert minute <= moves_on + A_DAY + 15
