"""P7: a fact due at one time stays due at every later time until it is collected, up to its match's kickoff,
after which there's nothing left to forecast (design C7; R7.1)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.web.cadence import SCHEDULED, due

BASE = dt.datetime(2026, 10, 25, tzinfo=dt.UTC)
minutes = st.integers(min_value=0, max_value=10 * 24 * 60).map(
    lambda count: BASE + dt.timedelta(minutes=count)
)


@given(
    fact=st.sampled_from(SCHEDULED),
    kickoff=minutes,
    last_read=st.none() | minutes,
    now=minutes,
    later=minutes,
    confirmed=st.booleans(),
)
def test_p7_due_stays_due(
    fact: str,
    kickoff: dt.datetime,
    last_read: dt.datetime | None,
    now: dt.datetime,
    later: dt.datetime,
    confirmed: bool,
) -> None:
    match_kickoff = None if fact == "fixtures" else kickoff
    if last_read is not None and last_read > now:
        return  # nothing is read in the future
    before_kickoff = match_kickoff is None or later < match_kickoff
    if due(fact, last_read, now, match_kickoff, confirmed=confirmed) and now <= later and before_kickoff:
        assert due(fact, last_read, later, match_kickoff, confirmed=confirmed)
