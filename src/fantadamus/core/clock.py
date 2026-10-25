"""The injected clock: logic takes a `Clock` and never reads the wall clock itself (structure.md)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

Clock = Callable[[], dt.datetime]


def utc_now() -> dt.datetime:
    """The wall clock, in UTC. Only the edges (CLI, server start-up) pass this in."""
    return dt.datetime.now(dt.UTC)


def fixed_clock(instant: dt.datetime) -> Clock:
    """A clock that always returns `instant`, converted to UTC."""
    if instant.utcoffset() is None:
        raise ValueError("a clock needs a timezone-aware instant")
    utc = instant.astimezone(dt.UTC)
    return lambda: utc
