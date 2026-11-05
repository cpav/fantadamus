"""P9 and P10: scoring (design C10; R7.2, R7.4)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.calibration import brier, last_told, scored_chance
from fantadamus.lake.decision_log import Decision, LoggedPlayer
from fantadamus.league.rules import CLASSIC, StoredRules

_PAIRS = st.lists(st.tuples(st.floats(min_value=0.0, max_value=1.0), st.booleans()), min_size=1, max_size=40)
KICKOFF = dt.datetime(2026, 11, 6, 19, 45, tzinfo=dt.UTC)


@given(pairs=_PAIRS)
def test_p9_brier_scores_are_bounded(pairs: list[tuple[float, bool]]) -> None:
    assert 0.0 <= brier(pairs) <= 1.0
    chance = scored_chance("Starting", pairs)
    assert 0.0 <= chance.baseline <= 0.25
    assert sum(bucket.count for bucket in chance.buckets) == len(pairs)
    assert all(bucket.low <= bucket.said <= bucket.high for bucket in chance.buckets)
    assert all(0.0 <= bucket.happened <= 1.0 for bucket in chance.buckets)


@given(outcomes=st.lists(st.booleans(), min_size=1, max_size=40))
def test_p9_a_forecast_right_every_time_scores_0(outcomes: list[bool]) -> None:
    assert brier([(1.0 if outcome else 0.0, outcome) for outcome in outcomes]) == 0.0


_MINUTES = st.integers(min_value=-600, max_value=600)


@given(times=st.lists(st.tuples(_MINUTES, st.floats(min_value=0.0, max_value=1.0)), min_size=1, max_size=12))
def test_p10_nothing_after_kickoff(times: list[tuple[int, float]]) -> None:
    decisions = [
        Decision(
            as_of=KICKOFF + dt.timedelta(minutes=minutes),
            logged_at=KICKOFF + dt.timedelta(minutes=minutes),
            user="u",
            round=11,
            players=[LoggedPlayer(player_id=1, name="P", p_start=chance, p_cameo=0.0, key=6.0)],
            rules=StoredRules(user="u", saved_at=KICKOFF, rules=CLASSIC),
            content_hashes=[],
        )
        for minutes, chance in times
    ]
    told = last_told(decisions, 11, lambda _: KICKOFF)
    before = [(minutes, chance) for minutes, chance in times if minutes < 0]
    if not before:
        assert told == {}
    else:
        latest = max(minutes for minutes, _ in before)
        assert told[1].p_start in {chance for minutes, chance in before if minutes == latest}
