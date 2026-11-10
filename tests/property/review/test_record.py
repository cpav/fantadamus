"""P5 of mvp-review: appending a review never changes an earlier line, and the record of the same reviews is
the same whatever their order (design C7; R4.1, R4.2)."""

from __future__ import annotations

import datetime as dt
import random
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.review import LoggedChoice, LoggedReview, record
from fantadamus.lake.review_log import ReviewLog

AT = dt.datetime(2026, 11, 24, 9, 0, tzinfo=dt.UTC)


@st.composite
def _reviews(draw: st.DrawFn) -> LoggedReview:
    gain = draw(st.none() | st.floats(-20, 20))
    cost = draw(st.floats(-2, 2))
    return LoggedReview(
        user=draw(st.sampled_from(["user-1", "user-2"])),
        team=draw(st.sampled_from(["mine", "Rivals"])),
        round=draw(st.integers(1, 6)),
        as_of=AT,
        logged_at=AT + dt.timedelta(minutes=draw(st.integers(0, 3))),
        replayed=draw(st.booleans()),
        advice_expected=70.0,
        fielded_expected=70.0 - cost,
        advice_real=68.0,
        fielded_real=None if gain is None else 68.0 + gain,
        total_cost=cost,
        total_gain=gain,
        choices=[
            LoggedChoice(
                kind="player", fielded=[7], advised=[6], expected_cost=cost, real_gain=gain, judged="even"
            )
        ],
        content_hashes=[],
    )


@given(reviews=st.lists(_reviews(), max_size=12), order=st.randoms(use_true_random=False))
def test_p5_append_only(reviews: list[LoggedReview], order: random.Random) -> None:
    with tempfile.TemporaryDirectory() as folder:
        log = ReviewLog(Path(folder))
        before = b""
        for review in reviews:
            path = log.append(review)
            now = path.read_bytes()
            assert now.startswith(before)
            before = now
        assert log.read() == reviews
    shuffled = list(reviews)
    order.shuffle(shuffled)
    for user in ("user-1", "user-2"):
        for team in ("mine", "Rivals"):
            assert record(reviews, user=user, team=team) == record(shuffled, user=user, team=team)
