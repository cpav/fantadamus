"""Silver's month files, the pure part (mvp-store design C1): the month a row is stored under, and the months
a window touches. A row goes to the month, in UTC, of the time it was captured."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable

MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
"""A month file's name, without `.parquet`: `2026-11`."""


def month_of(when: dt.datetime) -> str:
    """The month a row captured at `when` is stored under."""
    if when.utcoffset() is None:
        raise ValueError("a month needs a timezone-aware time")
    return f"{when.astimezone(dt.UTC):%Y-%m}"


def months_in(
    names: Iterable[str], since: dt.datetime | None = None, until: dt.datetime | None = None
) -> list[str]:
    """Of the months `names`, those a window from `since` to `until` touches, oldest first; without a bound,
    every month on that side."""
    low = month_of(since) if since is not None else None
    high = month_of(until) if until is not None else None
    return sorted(name for name in names if (low is None or name >= low) and (high is None or name <= high))
