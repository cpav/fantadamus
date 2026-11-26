"""mvp-next-round AT-6 (the design's P3): every fact but the fixtures is due exactly when its cadence says,
and an answer may read each page exactly when it may today (R1.4, R2.4). The cadences are written out again
here, from the specs, so that a change to any of them fails."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.web.cadence import due, may_read_after
from fantadamus.web.collector import PageKind

NOW = dt.datetime(2026, 11, 25, 18, 0, tzinfo=dt.UTC)
MINUTE, HOUR = dt.timedelta(minutes=1), dt.timedelta(hours=1)
DAY = 24 * HOUR
OTHERS = (
    "probable_lineups",
    "match_odds",
    "official_lineups",
    "player_season",
    "penalty_takers",
    "team_season",
    "other_fixtures",
    "injuries",
    "suspensions",
    "match_ratings",
)
DAILY = {"player_season": DAY, "penalty_takers": DAY, "team_season": DAY}
WINDOWS = {"probable_lineups": 72 * HOUR, "match_odds": 72 * HOUR, "official_lineups": 75 * MINUTE}
ON_DEMAND: dict[PageKind, dt.timedelta] = {
    "round": 15 * MINUTE,
    "statistics": DAY,
    "finished_round": 15 * MINUTE,
    "takers": DAY,
    "table": DAY,
    "other_fixtures": DAY,
    "injuries": 12 * HOUR,
    "suspensions": 12 * HOUR,
    "ratings": 12 * HOUR,
}
minutes = st.integers(min_value=-9 * 24 * 60, max_value=9 * 24 * 60)


def _every(fact: str, kickoff: dt.datetime | None, confirmed: bool) -> dt.timedelta | None:
    """The fact's interval at `NOW` for a match at `kickoff`, or None when it isn't due at all."""
    ahead = kickoff is not None and kickoff >= NOW
    if fact in DAILY:
        return DAILY[fact]
    if fact == "other_fixtures":
        return DAY if ahead and kickoff is not None and kickoff <= NOW + 7 * DAY else 7 * DAY
    if fact in ("injuries", "suspensions"):
        return 12 * HOUR if ahead and kickoff is not None and kickoff <= NOW + 48 * HOUR else DAY
    if kickoff is None or kickoff <= NOW or kickoff - NOW > WINDOWS[fact]:
        return None
    if fact == "official_lineups":
        return None if confirmed else 15 * MINUTE
    last_day = kickoff - NOW <= DAY
    if fact == "probable_lineups":
        return 3 * HOUR if last_day else 12 * HOUR
    return 3 * HOUR if last_day else DAY


def _due(fact: str, last: dt.datetime | None, kickoff: dt.datetime | None, confirmed: bool) -> bool:
    if fact == "match_ratings":  # once a round, the morning after its last kickoff
        morning = None if kickoff is None else kickoff + 12 * HOUR
        return morning is not None and morning <= NOW and (last is None or last < morning)
    every = _every(fact, kickoff, confirmed)
    return every is not None and (last is None or NOW - last >= every)


@given(
    fact=st.sampled_from(OTHERS),
    last=st.none() | st.integers(min_value=0, max_value=9 * 24 * 60),
    kickoff=st.none() | minutes,
    confirmed=st.booleans(),
)
def test_at6_every_other_fact_keeps_its_cadence(
    fact: str, last: int | None, kickoff: int | None, confirmed: bool
) -> None:
    read = None if last is None else NOW - last * MINUTE
    when = None if kickoff is None else NOW + kickoff * MINUTE
    assert due(fact, read, NOW, when, confirmed=confirmed) == _due(fact, read, when, confirmed)


@given(
    page=st.sampled_from(sorted(ON_DEMAND)),
    answered=st.none() | st.integers(min_value=0, max_value=3 * 24 * 60),
    failed=st.none() | st.integers(min_value=0, max_value=120),
)
def test_at6_an_answer_reads_as_today(page: PageKind, answered: int | None, failed: int | None) -> None:
    last = None if answered is None else NOW - answered * MINUTE
    tried = None if failed is None else NOW - failed * MINUTE
    allowed = (last is None or NOW - last >= ON_DEMAND[page]) and (
        tried is None or NOW - tried >= 15 * MINUTE
    )
    assert may_read_after(page, last, tried, NOW) == allowed
