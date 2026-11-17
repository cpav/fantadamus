"""mvp-store task 1.3: rows reach DuckDB in bulk, through a JSON-lines file typed by the table's own columns
(design C2; R1.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pytest
from pydantic import BaseModel

from fantadamus.lake.duckdb_store import Description, LakeStore, Table
from fantadamus.lake.months import month_of

EVERY_TYPE = Table(
    "every_type",
    "CREATE TEMP TABLE every_type (source_url VARCHAR, captured_at TIMESTAMPTZ, content_sha256 VARCHAR, "
    "count BIGINT, share DOUBLE, flag BOOLEAN, day DATE, note VARCHAR)",
)
DESCRIPTION = Description(columns=list(EVERY_TYPE.columns), rows_version=1)


class Row(BaseModel):
    source_url: str
    captured_at: dt.datetime
    content_sha256: str
    count: int | None
    share: float | None
    flag: bool | None
    day: dt.date | None
    note: str | None


def row(index: int, when: dt.datetime, **changes: object) -> Row:
    base = Row(
        source_url="https://example.org/page",
        captured_at=when,
        content_sha256=f"{index:064x}",
        count=index,
        share=index / 7,
        flag=index % 2 == 0,
        day=dt.date(2026, 11, 21),
        note=f"row {index}",
    )
    return base.model_copy(update=changes)


def lines(rows: list[Row]) -> list[tuple[str, str]]:
    return [(month_of(item.captured_at), item.model_dump_json()) for item in rows]


def test_every_type_comes_back_as_it_went_in(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    when = dt.datetime(2026, 11, 15, 18, 47, 22, 847829, tzinfo=dt.UTC)
    rows = [
        row(1, when),
        row(2, when, count=None, share=None, flag=None, day=None, note=None),
        row(3, when, share=0.1 + 0.2, count=2**53 + 1, note='he said "così",\nthen left\ttwice — ok'),
        row(
            4,
            when.astimezone(dt.timezone(dt.timedelta(hours=1))),
            share=-1e-9,
            flag=False,
            day=dt.date(2027, 2, 28),
        ),
    ]
    assert store.replace_rows(EVERY_TYPE, lines(rows), DESCRIPTION) == 4
    found = [Row.model_validate(read) for read in store.read_rows(EVERY_TYPE)]
    assert found == rows
    assert all(read.captured_at.utcoffset() == dt.timedelta(0) for read in found)
    assert list(store.read_rows(EVERY_TYPE)[0]) == list(
        EVERY_TYPE.columns
    )  # the table's columns, in its order


def test_rows_keep_their_order(tmp_path: Path) -> None:
    """Within a month the order they were given in; the months oldest first."""
    store = LakeStore(tmp_path)
    october, november = (dt.datetime(2026, month, 3, tzinfo=dt.UTC) for month in (10, 11))
    rows = [row(index, november if index % 3 else october) for index in range(5_000)]
    store.replace_rows(EVERY_TYPE, lines(rows), DESCRIPTION)
    found = [read["count"] for read in store.read_rows(EVERY_TYPE)]
    assert found == [
        *(index for index in range(5_000) if index % 3 == 0),
        *(i for i in range(5_000) if i % 3),
    ]


def test_the_temporary_file_is_gone(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    store.replace_rows(EVERY_TYPE, lines([row(1, dt.datetime(2026, 11, 3, tzinfo=dt.UTC))]), DESCRIPTION)
    left = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file())
    assert left == ["silver/every_type/2026-11.parquet", "silver/every_type/_table.json"]
    assert not any(path.name.startswith(".") for path in tmp_path.rglob("*"))


def test_a_load_that_fails_leaves_no_file(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    good = lines([row(1, dt.datetime(2026, 11, 3, tzinfo=dt.UTC))])
    with pytest.raises(duckdb.Error):
        store.replace_rows(EVERY_TYPE, [*good, ("2026-11", "not a row")], DESCRIPTION)
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
    assert store.read_rows(EVERY_TYPE) == []


def test_a_table_without_rows(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    assert store.read_rows(EVERY_TYPE) == []  # never written
    assert store.replace_rows(EVERY_TYPE, [], DESCRIPTION) == 0
    assert store.read_rows(EVERY_TYPE) == []
    assert store.description(EVERY_TYPE) == DESCRIPTION
