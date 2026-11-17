"""Several writers at once, as when two servers and a schedule collect together: found by the code review.
And readers while a table is written again: they see it whole, before or after (mvp-store R1.4)."""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import duckdb
import pytest

from fantadamus.core.files import temporary_beside
from fantadamus.lake import duckdb_store
from fantadamus.lake.duckdb_store import Incoming, LakeStore, Table
from fantadamus.lake.months import Description

_TABLE = Table("numbers", "CREATE TEMP TABLE numbers (captured_at TIMESTAMPTZ, value BIGINT)")
_OCTOBER = dt.datetime(2026, 10, 30, tzinfo=dt.UTC)
_NOVEMBER = dt.datetime(2026, 11, 3, tzinfo=dt.UTC)
_VERSION = 1_000_000
"""A value's version is how many millions it holds."""


def _rows(count: int, version: int = 0, when: dt.datetime = _NOVEMBER) -> list[Incoming]:
    month = f"{when:%Y-%m}"
    return [
        Incoming("a-bronze-record", month, f'{{"captured_at": "{when.isoformat()}", "value": {value}}}')
        for value in range(version * _VERSION, version * _VERSION + count)
    ]


def _folder(tmp_path: Path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "silver" / "numbers").iterdir())


def _named(store: LakeStore) -> list[str]:
    written = store.description(_TABLE)
    assert written is not None
    return sorted([*written.files.values(), "_table.json"])


def test_writers_take_turns(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rows = _rows(5_000)

    def write(_: int) -> None:
        with store.lock():
            store.replace_rows(_TABLE, rows, 1)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(write, range(40)))
    assert [row["value"] for row in store.read_rows(_TABLE)] == list(range(5_000))
    assert _folder(tmp_path) == _named(store)  # one month's file, and no other
    assert sorted(path.name for path in tmp_path.iterdir()) == [".lock", "silver"]  # no scratch is left


def test_a_reader_never_sees_half_a_table(tmp_path: Path) -> None:
    """The table is written again and again, two months at a time, as one version or the other: a read gives
    the whole of one, never one month of each."""
    store = LakeStore(tmp_path)
    sizes = {0: 1_000, 1: 2_000}

    def version(number: int) -> list[Incoming]:
        return [*_rows(sizes[number], number, _OCTOBER), *_rows(sizes[number], number, _NOVEMBER)]

    store.replace_rows(_TABLE, version(0), 1)
    done = threading.Event()

    def write() -> None:
        try:
            for turn in range(30):
                with store.lock():
                    store.replace_rows(_TABLE, version((turn + 1) % 2), 1)
        finally:
            done.set()

    def read() -> set[tuple[int, frozenset[int]]]:
        seen = set()
        while not done.is_set():
            values = [int(str(row["value"])) for row in store.read_rows(_TABLE)]
            seen.add((len(values), frozenset(value // _VERSION for value in values)))
        return seen

    with ThreadPoolExecutor(5) as pool:
        readers = [pool.submit(read) for _ in range(4)]
        pool.submit(write).result()
        seen = set().union(*(reader.result() for reader in readers))
    assert seen <= {(2_000, frozenset({0})), (4_000, frozenset({1}))}
    assert seen


def _values(store: LakeStore) -> int:
    return len(store.read_rows(_TABLE))


Read = list[dict[str, object]]


def test_a_read_while_a_store_takes_effect_gives_the_table_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It read the files `_table.json` named when it started, and they don't change: what it read is whole."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), 1)
    read = duckdb_store._read_parquet
    reads: list[int] = []

    def stored_meanwhile(
        paths: Sequence[Path],
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
        **options: Any,
    ) -> Read:
        found = read(paths, since, until, **options)
        if not reads:
            store.replace_rows(_TABLE, _rows(5), 1)
        reads.append(len(found))
        return found

    monkeypatch.setattr(duckdb_store, "_read_parquet", stored_meanwhile)
    assert _values(store) == 3
    assert _values(store) == 5
    assert reads == [3, 5]


def test_a_file_a_store_removed_is_listed_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The store took effect after the read listed its files and before it opened them: they're gone."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, [*_rows(3), *_rows(1, when=_OCTOBER)], 1)
    read = duckdb_store._read_parquet
    asked: list[list[str]] = []

    def stored_first(
        paths: Sequence[Path],
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
        **options: Any,
    ) -> Read:
        if not asked:
            store.replace_rows(_TABLE, _rows(5), 1)  # October's file, and November's, go
        asked.append([path.name for path in paths])
        return read(paths, since, until, **options)

    monkeypatch.setattr(duckdb_store, "_read_parquet", stored_first)
    assert _values(store) == 5
    assert len(asked) == 2
    assert [name[:7] for name in asked[0]] == ["2026-10", "2026-11"]
    assert asked[1] == [name for name in _named(store) if name != "_table.json"]


def test_a_file_gone_before_it_is_opened_is_listed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The store took effect after the read listed its files and before it looked for them: reading what was
    left would be part of the table, so it lists them again."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, [*_rows(3), *_rows(1, when=_OCTOBER)], 1)
    files = LakeStore._files
    listed: list[int] = []

    def stored_after_listing(
        self: LakeStore,
        table: Table,
        written: Description | None,
        since: dt.datetime | None,
        until: dt.datetime | None,
    ) -> list[Path]:
        found = files(self, table, written, since, until)
        if not listed:
            self.replace_rows(_TABLE, _rows(5), 1)
        listed.append(len(found))
        return found

    monkeypatch.setattr(LakeStore, "_files", stored_after_listing)
    assert _values(store) == 5
    assert listed == [2, 1]


def test_an_error_while_the_table_is_replaced_is_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), 1)
    read = duckdb_store._read_parquet
    reads: list[str] = []

    def torn(
        paths: Sequence[Path],
        since: dt.datetime | None = None,
        until: dt.datetime | None = None,
        **options: Any,
    ) -> Read:
        if not reads:
            reads.append("failed")
            store.replace_rows(_TABLE, _rows(5), 1)
            raise duckdb.InvalidInputException("Prefetch registered for bytes outside file")
        reads.append("whole")
        return read(paths, since, until, **options)

    monkeypatch.setattr(duckdb_store, "_read_parquet", torn)
    assert _values(store) == 5
    assert reads == ["failed", "whole"]


def test_an_error_of_a_file_nobody_replaced_is_raised(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), 1)
    written = store.description(_TABLE)
    assert written is not None
    (tmp_path / "silver" / "numbers" / written.files["2026-11"]).write_bytes(b"not a Parquet file")
    with pytest.raises(duckdb.Error):
        store.read_rows(_TABLE)


def test_a_file_removed_by_hand_leaves_its_rows_out(tmp_path: Path) -> None:
    """Its rows are missing, and the read doesn't fail: the table's next store rebuilds it."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, [*_rows(2, when=_OCTOBER), *_rows(3)], 1)
    written = store.description(_TABLE)
    assert written is not None
    (tmp_path / "silver" / "numbers" / written.files["2026-10"]).unlink()
    assert _values(store) == 3
    assert store.description(_TABLE) == written


def test_a_temporary_file_is_hidden_beside_its_target_and_unique(tmp_path: Path) -> None:
    target = tmp_path / "rules.json"
    one, other = temporary_beside(target), temporary_beside(target)
    assert one != other
    assert one.parent == tmp_path
    assert one.name.startswith(".rules.json.")
    assert one.suffix == ".tmp"
