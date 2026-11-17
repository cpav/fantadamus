"""Several writers at once, as when two servers and a schedule collect together: found by the code review.
And a reader while a table is written again (mvp-store R1.4)."""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import pytest

from fantadamus.core.files import temporary_beside
from fantadamus.lake import duckdb_store
from fantadamus.lake.duckdb_store import Description, LakeStore, Table

_TABLE = Table("numbers", "CREATE TEMP TABLE numbers (captured_at TIMESTAMPTZ, value BIGINT)")
_DESCRIPTION = Description(columns=["captured_at", "value"], rows_version=1)
_WHEN = dt.datetime(2026, 11, 3, tzinfo=dt.UTC)


def _rows(count: int) -> list[tuple[str, str]]:
    return [
        ("2026-11", f'{{"captured_at": "{_WHEN.isoformat()}", "value": {number}}}') for number in range(count)
    ]


def test_writers_never_share_a_temporary_file(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rows = _rows(5_000)

    def write(_: int) -> None:
        store.replace_rows(_TABLE, rows, _DESCRIPTION)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(write, range(40)))
    assert [row["value"] for row in store.read_rows(_TABLE)] == list(range(5_000))
    assert sorted(path.name for path in (tmp_path / "silver" / "numbers").iterdir()) == [
        "2026-11.parquet",
        "_table.json",
    ]
    assert [path.name for path in tmp_path.iterdir()] == ["silver"]  # no scratch folder is left


def test_a_reader_never_sees_half_a_month(tmp_path: Path) -> None:
    """While the table is written again and again, with 1,000 rows or 2,000, a read gives one or the other."""
    store = LakeStore(tmp_path)
    sizes = (1_000, 2_000)
    store.replace_rows(_TABLE, _rows(sizes[0]), _DESCRIPTION)
    done = threading.Event()

    def write() -> None:
        try:
            for turn in range(30):
                store.replace_rows(_TABLE, _rows(sizes[turn % 2]), _DESCRIPTION)
        finally:
            done.set()

    def read() -> set[int]:
        seen = set()
        while not done.is_set():
            seen.add(len(store.read_rows(_TABLE)))
        return seen

    with ThreadPoolExecutor(5) as pool:
        readers = [pool.submit(read) for _ in range(4)]
        pool.submit(write).result()
        seen = set().union(*(reader.result() for reader in readers))
    assert seen <= set(sizes)
    assert seen


def _values(store: LakeStore) -> int:
    return len(store.read_rows(_TABLE))


def test_a_file_replaced_during_a_read_is_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DuckDB opens a file once for its description and again for its rows: a store between the two would
    give a read that is half of each, so a read whose file was replaced meanwhile doesn't count."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), _DESCRIPTION)
    read = duckdb_store._read_parquet
    reads: list[int] = []

    def stored_meanwhile(
        paths: Sequence[Path], since: dt.datetime | None = None, until: dt.datetime | None = None
    ) -> list[dict[str, object]]:
        found = read(paths, since, until)
        if not reads:
            store.replace_rows(_TABLE, _rows(5), _DESCRIPTION)
        reads.append(len(found))
        return found

    monkeypatch.setattr(duckdb_store, "_read_parquet", stored_meanwhile)
    assert _values(store) == 5
    assert reads == [3, 5]


def test_an_error_while_a_file_is_replaced_is_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), _DESCRIPTION)
    read = duckdb_store._read_parquet
    reads: list[str] = []

    def torn(
        paths: Sequence[Path], since: dt.datetime | None = None, until: dt.datetime | None = None
    ) -> list[dict[str, object]]:
        if not reads:
            reads.append("torn")
            store.replace_rows(_TABLE, _rows(5), _DESCRIPTION)
            raise duckdb.InvalidInputException("Prefetch registered for bytes outside file")
        reads.append("whole")
        return read(paths, since, until)

    monkeypatch.setattr(duckdb_store, "_read_parquet", torn)
    assert _values(store) == 5
    assert reads == ["torn", "whole"]


def test_an_error_of_a_file_nobody_replaced_is_raised(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, _rows(3), _DESCRIPTION)
    (tmp_path / "silver" / "numbers" / "2026-11.parquet").write_bytes(b"not a Parquet file")
    with pytest.raises(duckdb.Error):
        store.read_rows(_TABLE)


def test_a_file_removed_before_a_read_starts_is_listed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As when the earlier layout's file goes while a reader has just listed it."""
    store = LakeStore(tmp_path)
    store.replace_rows(_TABLE, [*_rows(3), ("2026-10", _rows(1)[0][1])], _DESCRIPTION)
    marks = duckdb_store._marks
    listed: list[list[str]] = []

    def removed_meanwhile(paths: Sequence[Path]) -> list[tuple[int, int, int]] | None:
        if not listed:
            store.replace_rows(_TABLE, _rows(5), _DESCRIPTION)  # October's file goes
        listed.append([path.name for path in paths])
        return marks(paths)

    monkeypatch.setattr(duckdb_store, "_marks", removed_meanwhile)
    assert _values(store) == 5
    assert listed[0] == ["2026-10.parquet", "2026-11.parquet"]
    assert listed[1:] == [["2026-11.parquet"], ["2026-11.parquet"]]


def test_a_temporary_file_is_hidden_beside_its_target_and_unique(tmp_path: Path) -> None:
    target = tmp_path / "rules.json"
    one, other = temporary_beside(target), temporary_beside(target)
    assert one != other
    assert one.parent == tmp_path
    assert one.name.startswith(".rules.json.")
    assert one.suffix == ".tmp"
