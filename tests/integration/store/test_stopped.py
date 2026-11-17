"""mvp-store task 2.3: a store stopped after any of its steps leaves a lake whose next store ends with the
table a rebuild gives (design C3; R2.1). P3."""

from __future__ import annotations

import contextlib
import datetime as dt
import functools
import itertools
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

from hypothesis import given, settings
from hypothesis import strategies as st

from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.duckdb_store import LakeStore
from tests.integration.store.test_append import Step, store_step
from tests.store_lake import URL, Told, bronze_bytes, fixtures, table, told_by_bronze

OCTOBER = dt.datetime(2026, 10, 31, 22, 0, tzinfo=dt.UTC)
NOVEMBER = OCTOBER + dt.timedelta(hours=3)
FIRST, SECOND, THIRD, FOURTH = (NOVEMBER + dt.timedelta(hours=hour) for hour in (1, 2, 3, 4))
"""When a step was received."""
ALREADY: Step = ([fixtures(9)], OCTOBER, SECOND, False, URL)
STOPPED: list[Step] = [
    ([fixtures(10)], OCTOBER, THIRD, False, URL),  # one payload, for the month the table has
    ([fixtures(10), fixtures(11)], NOVEMBER, THIRD, True, URL),  # a page's two, for a month it hasn't
    ([fixtures(10)], NOVEMBER, FIRST, False, URL),  # received before the last one stored: a rebuild
]
NEXT: Step = ([fixtures(12)], NOVEMBER, FOURTH, False, URL)

WRITES: list[tuple[Any, str]] = [
    (LakeStore, "append_bronze"),
    (LakeStore, "append_rows"),
    (LakeStore, "replace_rows"),
    (LakeStore, "_write_month"),
    (LakeStore, "_describe"),
    (LakeStore, "_tidy"),
]
"""Everything a store writes or removes with, apart from its marker: stopped just after `_write_month`, a
month's new file is there and nothing names it."""


class StoppedError(Exception):
    """The run stops here."""


@contextlib.contextmanager
def stopping(at: int, done: bool) -> Iterator[None]:
    """StoppedError at the `at`-th write, counted over every write a store makes: before it happens, or with
    `done` just after."""
    calls = itertools.count(1)

    def stops(write: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(write)
        def wrapped(*args: Any, **options: Any) -> Any:
            number = next(calls)
            if number == at and not done:
                raise StoppedError
            found = write(*args, **options)
            if number == at and done:
                raise StoppedError
            return found

        return wrapped

    with contextlib.ExitStack() as stack:
        for owner, name in WRITES:
            stack.enter_context(mock.patch.object(owner, name, stops(getattr(owner, name))))
        yield


# A store makes at most six writes, so stopping before or after each of the first six, on a lake with a
# table and on one without, for each kind of store, is every way a store can stop: Hypothesis goes through
# all 72 and stops there.
@settings(deadline=None)
@given(
    already=st.booleans(),
    stopped=st.sampled_from(STOPPED),
    at=st.integers(1, 6),
    done=st.booleans(),
)
def test_p3_a_stopped_store_is_healed_by_the_next(already: bool, stopped: Step, at: int, done: bool) -> None:
    with tempfile.TemporaryDirectory() as root:
        store = LakeStore(Path(root))
        if already:
            store_step(store, Told(), ALREADY)
        kept = bronze_bytes(store)
        with stopping(at, done), contextlib.suppress(StoppedError):
            store_step(store, Told(), stopped)
        store_step(store, Told(), NEXT)
        now = bronze_bytes(store)
        assert {name: now[name] for name in kept} == kept  # bronze was only added to
        assert table(store) == told_by_bronze(store).table()  # what bronze holds, as a rebuild gives it
        folder = store.root / "silver" / "fixtures"
        written = store.description(FIXTURES.table)
        assert written is not None
        assert sorted(path.name for path in folder.iterdir()) == sorted(
            [*written.files.values(), "_table.json"]
        )


def test_a_store_makes_at_most_six_writes() -> None:
    """What P3 counts on: no kind of store writes more than six times, so six stops cover each."""
    for already in (False, True):
        for stopped in STOPPED:
            with tempfile.TemporaryDirectory() as root:
                store = LakeStore(Path(root))
                if already:
                    store_step(store, Told(), ALREADY)
                with stopping(7, done=False):
                    store_step(store, Told(), stopped)  # the seventh write never comes
