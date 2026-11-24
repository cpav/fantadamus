"""P4 of mvp-fixes: the record counts the rounds whose app total was compared with the real score, each by the
latest of its reviews that had one, whatever order they come in; a later review without one doesn't drop the
round, and a line logged before the slice reads (design C8; R5.2, R5.3)."""

from __future__ import annotations

import datetime as dt
import json
import random

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.review import LoggedReview, record

AT = dt.datetime(2026, 11, 24, 9, 0, tzinfo=dt.UTC)
GAP = 0.5


@st.composite
def _reviews(draw: st.DrawFn) -> LoggedReview:
    real = draw(st.none() | st.just(70.0))
    app_total = draw(st.none() | st.sampled_from([69.5, 70.0, 72.0]))
    return LoggedReview(
        user="user-1",
        team=draw(st.sampled_from(["mine", "Rivals"])),
        round=draw(st.integers(1, 5)),
        as_of=AT,
        logged_at=AT + dt.timedelta(minutes=draw(st.integers(0, 3))),
        replayed=False,
        advice_expected=70.0,
        fielded_expected=70.0,
        advice_real=real,
        fielded_real=real,
        total_cost=0.0,
        total_gain=None if real is None else 0.0,
        choices=[],
        content_hashes=[],
        app_total=app_total,
        app_differs=None if app_total is None or real is None else abs(app_total - real) > GAP,
    )


def _counted(reviews: list[LoggedReview]) -> tuple[int, int]:
    """Oldest to latest, each compared review of "mine" takes its round over."""
    compared: dict[int, LoggedReview] = {}
    for review in sorted(reviews, key=lambda review: (review.logged_at, review.model_dump_json())):
        if review.team == "mine" and review.app_differs is not None:
            compared[review.round] = review
    return len(compared), sum(1 for review in compared.values() if not review.app_differs)


@given(
    reviews=st.lists(_reviews(), max_size=12),
    order=st.randoms(use_true_random=False),
    later=_reviews(),
)
def test_p4_the_app_count_follows_the_latest_reviews(
    reviews: list[LoggedReview], order: random.Random, later: LoggedReview
) -> None:
    found = record(reviews, user="user-1", team="mine")
    assert (found.app_rounds, found.app_matched) == _counted(reviews)
    assert found.app_matched <= found.app_rounds <= found.rounds
    shuffled = list(reviews)
    order.shuffle(shuffled)
    assert record(shuffled, user="user-1", team="mine") == found
    plain = later.model_copy(
        update={
            "team": "mine",
            "logged_at": AT + dt.timedelta(hours=1),
            "app_total": None,
            "app_differs": None,
        }
    )
    again = record([*reviews, plain], user="user-1", team="mine")
    assert (again.app_rounds, again.app_matched) == (found.app_rounds, found.app_matched)
    before = json.loads(later.model_dump_json())
    del before["app_total"], before["app_differs"]
    read = LoggedReview.model_validate_json(json.dumps(before))
    assert (read.app_total, read.app_differs) == (None, None)
