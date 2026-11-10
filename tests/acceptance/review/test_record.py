"""AT-6 of mvp-review: every review logged, append-only and privately, with the snapshots it used; the record
for each user and team, and how much it can tell yet (design C7; R4.1 to R4.3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
import statistics
from pathlib import Path

from fantadamus.domains.review import LoggedChoice, LoggedReview, Record, logged, record, review_choices
from fantadamus.lake.review_log import ReviewLog
from tests.review_choices import ADVICE, RULES, SQUAD, Stand

AT = dt.datetime(2026, 11, 24, 9, 0, tzinfo=dt.UTC)


def _review(
    round: int,
    gain: float | None,
    cost: float,
    *,
    team: str = "mine",
    user: str = "user-1",
    hours: float = 0.0,
    followed: bool = False,
) -> LoggedReview:
    choices = (
        []
        if followed
        else [
            LoggedChoice(
                kind="player", fielded=[7], advised=[6], expected_cost=cost, real_gain=gain, judged="cost"
            )
        ]
    )
    return LoggedReview(
        user=user,
        team=team,
        round=round,
        as_of=AT,
        logged_at=AT + dt.timedelta(hours=hours),
        replayed=False,
        advice_expected=70.0,
        fielded_expected=70.0 - cost,
        advice_real=68.0,
        fielded_real=None if gain is None else 68.0 + gain,
        total_cost=0.0 if followed else cost,
        total_gain=0.0 if followed else gain,
        choices=choices,
        content_hashes=["a" * 64],
    )


def test_at6_over_several_rounds() -> None:
    """Four rounds, one reviewed twice and one played as advised; another team's and another user's apart."""
    reviews = [
        _review(10, 3.0, 0.4),
        _review(11, -1.0, 0.2),
        _review(12, 9.0, 1.0),
        _review(12, 2.0, 0.5, hours=1.0),  # the later review of round 12 supersedes the first
        _review(13, None, 0.0, followed=True),
        _review(15, 5.0, 0.3, team="Rivals"),
        _review(14, 5.0, 0.3, user="user-2"),
    ]
    found = record(reviews, user="user-1", team="Mine")
    gains = [3.0, -1.0, 2.0]
    margin = 2 * statistics.stdev(gains) * math.sqrt(3)
    assert found == Record(
        rounds=4,
        overrides=3,
        expected_cost=1.1,  # 0.4 + 0.2 + 0.5
        real_gain=4.0,
        counted=3,
        margin=margin,
        verdict="mostly luck",  # 4 is within about 2 standard errors, 7.2 points
    )


def test_at6_too_early_to_tell() -> None:
    found = record([_review(10, 3.0, 0.4), _review(11, 9.0, 0.2)], user="user-1", team="mine")
    assert (found.counted, found.margin, found.verdict) == (2, None, "too early")
    assert record([], user="user-1", team="mine") == Record(0, 0, 0.0, 0.0, 0, None, "too early")


def test_at6_a_real_difference_shows() -> None:
    """Steady gains beyond about two standard errors paid off; steady losses cost."""
    steady = [_review(round, 3.0 + 0.1 * round, 0.2) for round in range(1, 6)]
    assert record(steady, user="user-1", team="mine").verdict == "paid off"
    losses = record(
        [_review(round, -3.0 - 0.1 * round, 0.2) for round in range(1, 6)], user="user-1", team="mine"
    )
    assert losses.verdict == "cost"


def test_at6_an_unknown_gain_isnt_counted() -> None:
    found = record(
        [_review(10, 3.0, 0.4), _review(11, None, 0.2), _review(12, 1.0, 0.1)], user="user-1", team="mine"
    )
    assert (found.overrides, found.counted, found.real_gain) == (3, 2, 4.0)
    assert round(found.expected_cost, 6) == 0.7


def test_at6_logged_with_its_snapshots(tmp_path: Path) -> None:
    """A review becomes a line with every choice, and the log appends it privately."""
    stand = Stand({7: 6.5}, {7: 7.0}, captain_expected={}, captain_real={}, bench_expected={}, bench_real={})
    fielded = dataclasses.replace(
        ADVICE,
        starters=tuple(7 if player == 6 else player for player in ADVICE.starters),
        bench=tuple(6 if player == 7 else player for player in ADVICE.bench),
    )
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=stand.price, score=stand.score)
    line = logged(
        reviewed, user="user-1", team="mine", round=12, as_of=AT, logged_at=AT, content_hashes=["b" * 64]
    )
    assert (line.total_cost, line.total_gain) == (reviewed.total_cost, reviewed.total_gain)
    assert (line.advice_real, line.fielded_real) == (66.0, 67.0)  # eleven 6s, then his 7 for one of them
    assert (line.advice_expected, line.fielded_expected) == (reviewed.advice.mean, reviewed.fielded.mean)
    made = reviewed.choices[0]
    assert [choice.model_dump() for choice in line.choices] == [
        {
            "kind": "player",
            "fielded": [7],
            "advised": [6],
            "expected_cost": made.expected_cost,
            "real_gain": 1.0,
            "judged": made.judged,
            "mattered": None,
        }
    ]
    bench = dataclasses.replace(made, kind="bench", mattered=True)
    with_bench = dataclasses.replace(reviewed, choices=[bench])
    assert (
        logged(with_bench, user="u", team="t", round=1, as_of=AT, logged_at=AT, content_hashes=[])
        .choices[0]
        .mattered
    )
    assert line.content_hashes == ["b" * 64]
    log = ReviewLog(tmp_path / "reviews")
    path = log.append(line)
    assert path == tmp_path / "reviews" / "2026-11.jsonl"
    assert log.read() == [line]
