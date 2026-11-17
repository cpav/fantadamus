"""Silver's files, the pure part (mvp-store design C1, C3): the month a row is stored under, the months a
window touches, what a table's files were written with, and whether a store can add its rows to them. A row
goes to the month, in UTC, of the time it was captured."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

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


class Description(BaseModel):
    """A silver table, kept beside its files as `_table.json`: what they were written with, and which they
    are."""

    model_config = ConfigDict(frozen=True)

    columns: list[tuple[str, str]]
    """Each column's name and SQL type, in the table's order."""
    rows_version: int
    """The domain's, raised when its payloads become other rows."""
    last_bronze: str | None = None
    """The bronze record the table's last row came from, as a rebuild reads them; None without a row."""
    files: dict[str, str] = {}
    """The file of each month the table has rows in."""


def in_step(
    written: Description | None,
    columns: Sequence[tuple[str, str]],
    rows_version: int,
    *,
    storing: bool,
    earlier_layout: bool,
    missing_file: bool = False,
) -> bool:
    """Whether a store can add its rows to a silver table as it stands: its files were written with these
    columns and this rows version, no earlier store stopped part-way (`storing`), it isn't one file in the
    layout from before month files, and none of its files is missing. Otherwise the table is rebuilt."""
    return (
        written is not None
        and written.columns == list(columns)
        and written.rows_version == rows_version
        and not storing
        and not earlier_layout
        and not missing_file
    )


def bronze_order(bronze_id: str) -> str:
    """What bronze records sort by, and so the order a rebuild reads them in: their file names."""
    return f"{bronze_id}.parquet"


def follows(last: str | None, bronze_ids: Iterable[str]) -> bool:
    """Whether new bronze records all sort after the last one a table holds: only then do their rows belong
    at the end of the table, where a rebuild would put them. Two stores in the same microsecond, or a clock
    set back, can sort the other way."""
    return last is None or all(bronze_order(found) > bronze_order(last) for found in bronze_ids)
