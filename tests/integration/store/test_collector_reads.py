"""mvp-store task 3.4: the collector asks for a page's newest stored hashes, and the schedule's check reads
the window's official lineups, not the whole table (design C5; R1.2, R1.5)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

import pytest

from fantadamus.domains import facts
from fantadamus.domains.availability.silver import OFFICIAL_LINEUPS
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.lake import duckdb_store
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore, Table
from fantadamus.web.cadence import what_is_due
from tests.store_lake import URL, fixtures, store_one, store_page

OCTOBER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)
NOVEMBER = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
OTHER = "https://example.org/other"


def test_the_newest_reads_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hashes of the page's newest stored read, a page's payloads at once among them, from DuckDB: no row
    becomes a Python object."""
    store = LakeStore(tmp_path)
    store_one(store, fixtures(9), OCTOBER)
    newest = store_page(store, [fixtures(10), fixtures(11)], NOVEMBER)  # one read, two payloads
    store_one(store, fixtures(12), NOVEMBER + dt.timedelta(days=1), url=OTHER)  # another page, later
    hashes = {facts.payload_hash(fixtures(10)), facts.payload_hash(fixtures(11))}
    assert len(newest.receipts) == 2

    def no_rows(*args: object, **options: object) -> list[dict[str, object]]:
        raise AssertionError("the hashes come back without reading the rows")

    monkeypatch.setattr(duckdb_store, "_read_parquet", no_rows)
    assert store.newest_hashes(FIXTURES.table, URL) == hashes
    assert facts.last_read(store, FIXTURES, URL) == hashes
    assert store.newest_hashes(FIXTURES.table, URL, since=NOVEMBER + dt.timedelta(hours=1)) == set()
    assert store.newest_hashes(FIXTURES.table, URL, since=OCTOBER) == hashes
    assert store.newest_hashes(FIXTURES.table, OTHER) == {facts.payload_hash(fixtures(12))}
    assert store.newest_hashes(FIXTURES.table, "https://example.org/never") == set()
    assert store.newest_hashes(OFFICIAL_LINEUPS.table, URL) == set()  # a table never written


def test_what_is_due_reads_the_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LakeStore(tmp_path / "lake")
    store_one(store, fixtures(9), OCTOBER)
    read_rows = LakeStore.read_rows
    windows: dict[str, tuple[dt.datetime | None, dt.datetime | None]] = {}

    def recording(
        self: LakeStore,
        table: Table,
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
        *,
        newest_by: Sequence[str] = (),
        equals: Mapping[str, Collection[object]] | None = None,
    ) -> list[dict[str, object]]:
        windows[table.name] = (since, until)
        return read_rows(self, table, since, until, newest_by=newest_by, equals=equals)

    monkeypatch.setattr(LakeStore, "read_rows", recording)
    what_is_due(store, CollectLog(tmp_path / "collect"), NOVEMBER)
    assert windows["official_lineups"] == (NOVEMBER - FACTS_WINDOW, NOVEMBER)
