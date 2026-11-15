"""P1 of mvp-sources: rest days are never negative, the previous match is the latest before the kickoff and
the next the earliest after it, and a European week is one with a European match within its days (design C3;
R2.2)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.context import EUROPEAN, rest_days
from fantadamus.domains.fixtures.silver import FixtureRow, OtherFixtureRow
from fantadamus.engine.constants import EUROPEAN_WEEK_DAYS

KICKOFF = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
SOURCE = {
    "source_url": "https://example.org/page",
    "captured_at": dt.datetime(2026, 10, 26, tzinfo=dt.UTC),
    "content_sha256": "0" * 64,
}
NAMES = {"alfa": "Alfa", "beta": "Beta"}
_WHEN = st.integers(-40 * 24 * 4, 40 * 24 * 4).map(
    lambda quarters: KICKOFF + dt.timedelta(minutes=15 * quarters)
)
_COMPETITION = st.sampled_from(["Champions League", "Europa League", "Conference League", "Coppa Italia"])


@st.composite
def _other(draw: st.DrawFn) -> OtherFixtureRow:
    home = draw(st.booleans())
    rival = draw(st.sampled_from(["Kessel", "Ostrava Rovers", "beta"]))
    return OtherFixtureRow(
        **SOURCE,
        competition=draw(_COMPETITION),
        home="alfa" if home else rival,
        away=rival if home else "alfa",
        kickoff_at=draw(_WHEN),
    )


@st.composite
def _serie_a(draw: st.DrawFn) -> FixtureRow:
    home = draw(st.booleans())
    return FixtureRow(
        **SOURCE,
        round=draw(st.integers(1, 38)),
        home="alfa" if home else "beta",
        away="beta" if home else "alfa",
        kickoff_at=draw(_WHEN),
    )


@given(st.lists(_serie_a(), max_size=4), st.lists(_other(), max_size=8))
def test_p1_rest_days_in_order(serie_a: list[FixtureRow], other: list[OtherFixtureRow]) -> None:
    days = rest_days("alfa", KICKOFF, serie_a, other, NAMES).days
    kickoffs = [*(row.kickoff_at for row in serie_a), *(row.kickoff_at for row in other)]
    before = [when for when in kickoffs if when < KICKOFF]
    after = [when for when in kickoffs if when > KICKOFF]
    if before:
        assert days.previous is not None
        assert days.days_since is not None
        assert days.previous.kickoff.astimezone(dt.UTC) == max(before)  # the hour the clocks go back: PEP 495
        assert days.days_since >= 0
    else:
        assert days.previous is None
        assert days.days_since is None
    if after:
        assert days.next is not None
        assert days.days_to is not None
        assert days.next.kickoff.astimezone(dt.UTC) == min(after)
        assert days.days_to >= 0
    else:
        assert days.next is None
        assert days.days_to is None
    near = [
        (match.competition, gap)
        for match, gap in ((days.previous, days.days_since), (days.next, days.days_to))
        if match is not None and gap is not None
    ]
    assert days.european_week == any(name in EUROPEAN and gap <= EUROPEAN_WEEK_DAYS for name, gap in near)
    assert (days.line is None) == (days.previous is None and days.next is None)
