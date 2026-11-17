"""P2 of mvp-store: a row is in the file of the month it was captured in, and the files chosen for a window
are exactly those whose month it touches (design C1; R1.2, R3.2)."""

from __future__ import annotations

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.lake.months import month_of, months_in

times = st.datetimes(
    min_value=dt.datetime(2026, 7, 1),
    max_value=dt.datetime(2027, 6, 30),
    timezones=st.sampled_from(
        [dt.UTC, dt.timezone(dt.timedelta(hours=2)), dt.timezone(dt.timedelta(hours=-5))]
    ),
)


def _first_instant(month: str) -> dt.datetime:
    year, number = map(int, month.split("-"))
    return dt.datetime(year, number, 1, tzinfo=dt.UTC)


def _next_month(month: str) -> dt.datetime:
    year, number = map(int, month.split("-"))
    return dt.datetime(year + number // 12, number % 12 + 1, 1, tzinfo=dt.UTC)


@given(st.lists(times, max_size=30), times, times)
def test_p2_a_window_reads_exactly_its_months(
    captured: list[dt.datetime], one: dt.datetime, other: dt.datetime
) -> None:
    since, until = sorted((one, other))
    names = {month_of(when) for when in captured}
    chosen = months_in(names, since, until)
    assert chosen == sorted(chosen)
    assert set(chosen) <= names
    for when in captured:
        month = month_of(when)
        assert _first_instant(month) <= when < _next_month(month)  # it is in its month's file
        if since <= when <= until:
            assert month in chosen  # nothing inside the window is missed
    for month in chosen:  # and every file chosen has a moment inside the window
        assert _first_instant(month) <= until
        assert since < _next_month(month)
    for month in names - set(chosen):
        assert until < _first_instant(month) or _next_month(month) <= since
