"""mvp-review task 4.2: the advice a user was given, the last lineup answer logged before the lock, or, when
there was none, the advice replayed at the lock and marked so (design C5; R3.4, R3.5)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fantadamus.domains.review import Advice, advice_for, last_advice
from fantadamus.lake.decision_log import Decision
from fantadamus.league.rules import CLASSIC, StoredRules

LOCK = dt.datetime(2026, 11, 21, 19, 45, tzinfo=dt.UTC)
RULES = StoredRules(user="user-1", saved_at=LOCK - dt.timedelta(days=9), rules=CLASSIC)


def _decision(hours_before: float, starters: list[int], **changes: Any) -> Decision:
    when = LOCK - dt.timedelta(hours=hours_before)
    settings: dict[str, Any] = {
        "kind": "lineup",
        "as_of": when,
        "logged_at": when,
        "user": "user-1",
        "round": 12,
        "players": [],
        "rules": RULES,
        "content_hashes": [],
        "team": "mine",
        "formation": "3-4-3",
        "starters": starters,
        "bench": [90, 91],
        "captain": starters[0],
        "vice": starters[1],
    }
    return Decision.model_validate(settings | changes)


EARLY = _decision(30, [1, 2, 3])
LATE = _decision(2, [4, 5, 6])


def test_the_last_before_the_lock() -> None:
    after = _decision(-1, [7, 8, 9])
    at_the_lock = _decision(0, [7, 8, 9])  # the deadline has passed: not advice
    elsewhere = [
        _decision(1, [10, 11], user="user-2"),
        _decision(1, [12, 13], team="Rivals"),
        _decision(1, [14, 15], round=11),
        _decision(1, [16, 17], kind="compare"),
    ]
    found = last_advice(
        [EARLY, LATE, after, at_the_lock, *elsewhere], user="user-1", team="Mine", round=12, lock=LOCK
    )
    assert found == Advice("3-4-3", [4, 5, 6], [90, 91], 4, 5, LATE.as_of)
    assert last_advice([], user="user-1", team="mine", round=12, lock=LOCK) is None


def test_an_override_shows_the_advice_it_was_priced_against() -> None:
    """The user's own choice is logged with the advice beside it; an older line without it is skipped."""
    priced = _decision(
        1,
        [20, 21, 22],
        override_cost=0.4,
        advised_starters=[4, 5, 30],
        advised_formation="4-3-3",
        advised_bench=[92],
        advised_captain=30,
        advised_vice=4,
    )
    found = last_advice([EARLY, LATE, priced], user="user-1", team="mine", round=12, lock=LOCK)
    assert found == Advice("4-3-3", [4, 5, 30], [92], 30, 4, priced.as_of)
    older = _decision(1, [20, 21, 22], override_cost=0.4, advised_starters=[4, 5, 30])
    assert last_advice([EARLY, LATE, older], user="user-1", team="mine", round=12, lock=LOCK) == Advice(
        "3-4-3", [4, 5, 6], [90, 91], 4, 5, LATE.as_of
    )


def test_a_replay_when_none_was_asked() -> None:
    replayed = Advice("4-4-2", [1], [2], None, None, LOCK)
    calls: list[int] = []

    def replay() -> Advice | None:
        calls.append(1)
        return replayed

    found = advice_for([], user="user-1", team="mine", round=12, lock=LOCK, replay=replay)
    assert found == Advice("4-4-2", [1], [2], None, None, LOCK, replayed=True)
    assert advice_for([LATE], user="user-1", team="mine", round=12, lock=LOCK, replay=replay) == last_advice(
        [LATE], user="user-1", team="mine", round=12, lock=LOCK
    )
    assert calls == [1]  # not asked when there was advice
    assert advice_for([], user="user-1", team="mine", round=12, lock=LOCK, replay=lambda: None) is None
