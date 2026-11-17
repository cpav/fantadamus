"""mvp-store task 3.1: a read can keep each page's newest submission for a domain's key, and only some values
of a column (design C5; R3.2, R3.5). P5."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from fantadamus.lake.duckdb_store import Incoming, LakeStore, Table
from fantadamus.lake.months import month_of
from tests.store_lake import newest_submissions

TABLE = Table(
    "views",
    "CREATE TEMP TABLE views (source_url VARCHAR, captured_at TIMESTAMPTZ, content_sha256 VARCHAR, "
    "home VARCHAR, outlet VARCHAR, name VARCHAR)",
)
KEYS = ("home", "outlet")
PAGES = ("https://example.org/a", "https://example.org/b")
START = dt.datetime(2026, 10, 29, 6, 0, tzinfo=dt.UTC)
STEP = dt.timedelta(hours=12)
"""Thirteen steps of twelve hours: six days, across the end of October."""

Submission = tuple[str, int, int, str, str, list[str]]
submissions = st.tuples(
    st.sampled_from(PAGES),
    st.integers(0, 12),  # when it was read, in steps
    st.integers(0, 3),  # its content: few hashes, so that ties come
    st.sampled_from(["alfa", "gamma"]),
    st.sampled_from(["Uno", "uno", "Due"]),  # an outlet, as each page spells it
    st.lists(st.sampled_from(["Rossi", "Bianchi", "Verdi"]), min_size=1, max_size=3),
)


def at(step: int) -> dt.datetime:
    return START + step * STEP


def lines(history: list[Submission]) -> list[Incoming]:
    found = []
    for index, (page, step, content, home, outlet, names) in enumerate(history):
        row = {"source_url": page, "captured_at": at(step).isoformat(), "content_sha256": f"{content:064x}"}
        for name in names:
            line = json.dumps({**row, "home": home, "outlet": outlet, "name": name})
            found.append(Incoming(f"{index:04d}", month_of(at(step)), line))
    return found


def stored(store: LakeStore, history: list[Submission]) -> list[dict[str, object]]:
    store.replace_rows(TABLE, lines(history), 1)
    return store.read_rows(TABLE)


@settings(deadline=None)
@given(
    history=st.lists(submissions, min_size=1, max_size=8),
    ends=st.tuples(st.integers(0, 12), st.integers(0, 12)),
)
def test_p5_the_newest_submission_and_nothing_later(history: list[Submission], ends: tuple[int, int]) -> None:
    since, until = (at(step) for step in sorted(ends))
    with tempfile.TemporaryDirectory() as root:
        store = LakeStore(Path(root))
        everything = stored(store, history)
        reduced = store.read_rows(TABLE, since, until, newest_by=KEYS)
        stamps = [row["captured_at"] for row in reduced]
        assert all(isinstance(at, dt.datetime) and since <= at <= until for at in stamps)  # nothing outside
        assert reduced == newest_submissions(everything, KEYS, since, until)
        assert store.read_rows(TABLE, newest_by=KEYS) == newest_submissions(everything, KEYS)


def test_a_tie_keeps_the_whole_submission(tmp_path: Path) -> None:
    """Read at the same time, the higher content hash is the newer, as `latest_by` has it; the same content
    stored twice is kept twice, as `latest_submissions` keeps both."""
    store = LakeStore(tmp_path)
    page = PAGES[0]
    history: list[Submission] = [
        (page, 3, 1, "alfa", "Uno", ["Rossi", "Bianchi"]),
        (page, 3, 2, "alfa", "Uno", ["Verdi", "Rossi"]),
        (page, 3, 2, "alfa", "Uno", ["Verdi", "Rossi"]),
        (page, 2, 3, "alfa", "Uno", ["Bianchi"]),  # an earlier read, with a higher hash
    ]
    stored(store, history)
    kept = store.read_rows(TABLE, newest_by=KEYS)
    assert [(row["content_sha256"], row["name"]) for row in kept] == [
        (f"{2:064x}", "Verdi"),
        (f"{2:064x}", "Rossi"),
        (f"{2:064x}", "Verdi"),
        (f"{2:064x}", "Rossi"),
    ]


def test_only_the_values_asked_for(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    history: list[Submission] = [
        (PAGES[0], 1, 0, "alfa", "Uno", ["Rossi"]),
        (PAGES[0], 2, 1, "gamma", "Uno", ["Bianchi"]),
        (PAGES[1], 3, 2, "alfa", "Due", ["Verdi"]),
        (PAGES[1], 4, 3, "alfa", "Due", ["Neri"]),
    ]
    stored(store, history)

    def names(
        since: dt.datetime | None = None,
        *,
        equals: dict[str, list[str]] | None = None,
        newest_by: tuple[str, ...] = (),
    ) -> list[object]:
        return [row["name"] for row in store.read_rows(TABLE, since, equals=equals, newest_by=newest_by)]

    assert names(equals={"home": ["alfa"]}) == ["Rossi", "Verdi", "Neri"]
    assert names(equals={"home": ["gamma", "alfa"]}) == ["Rossi", "Bianchi", "Verdi", "Neri"]
    assert names(equals={"home": ["alfa"], "outlet": ["Due"]}) == ["Verdi", "Neri"]
    assert names(equals={"home": ["alfa"]}, newest_by=KEYS) == ["Rossi", "Neri"]
    assert names(equals={"home": ["delta"]}) == []
    assert names(equals={"home": []}) == []  # no value asked for: no row
    assert names(since=at(2), equals={"home": ["alfa"]}) == ["Verdi", "Neri"]


def test_stored_order_is_kept(tmp_path: Path) -> None:
    """By month, oldest first, and then as the rows were stored: never by page, key or time."""
    store = LakeStore(tmp_path)
    history: list[Submission] = [
        (PAGES[1], 6, 0, "gamma", "Uno", ["Rossi"]),  # 1 November
        (PAGES[0], 5, 1, "alfa", "Due", ["Bianchi", "Verdi"]),  # 31 October, stored later
        (PAGES[0], 7, 2, "alfa", "Uno", ["Neri"]),  # 1 November
    ]
    everything = stored(store, history)
    assert [row["name"] for row in everything] == ["Bianchi", "Verdi", "Rossi", "Neri"]
    assert store.read_rows(TABLE, newest_by=KEYS) == everything
