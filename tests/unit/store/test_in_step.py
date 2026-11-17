"""mvp-store task 2.1: whether a store can add its rows to a silver table as it stands, and whether new bronze
records sort after the last one it holds (design C3; R2.1, R2.3)."""

from __future__ import annotations

from collections.abc import Sequence

from fantadamus.lake.months import Description, follows, in_step

COLUMNS = [("source_url", "VARCHAR"), ("captured_at", "TIMESTAMPTZ"), ("round", "BIGINT")]
LAST = "20261101T100000000000Z-aaaaaaaaaaaa"
WRITTEN = Description(
    columns=COLUMNS,
    rows_version=2,
    last_bronze=LAST,
    files={"2026-10": "2026-10.0123456789ab.parquet", "2026-11": "2026-11.ba9876543210.parquet"},
)


def _in_step(
    written: Description | None = WRITTEN,
    columns: Sequence[tuple[str, str]] = COLUMNS,
    rows_version: int = 2,
    storing: bool = False,
    earlier_layout: bool = False,
    missing_file: bool = False,
) -> bool:
    return in_step(
        written,
        columns,
        rows_version,
        storing=storing,
        earlier_layout=earlier_layout,
        missing_file=missing_file,
    )


def test_in_step() -> None:
    assert _in_step()
    assert _in_step(columns=tuple(COLUMNS))
    assert _in_step(WRITTEN.model_copy(update={"last_bronze": None}))  # written, with no row yet
    assert Description.model_validate_json(WRITTEN.model_dump_json()) == WRITTEN  # as `_table.json` keeps it


def test_each_way_out_of_step() -> None:
    assert not _in_step(written=None)  # never written, or its description can't be read
    assert not _in_step(columns=COLUMNS[:-1])  # the domain has a column fewer
    assert not _in_step(columns=[*COLUMNS, ("home", "VARCHAR")])  # or one more
    assert not _in_step(columns=[COLUMNS[1], COLUMNS[0], COLUMNS[2]])  # or the same in another order
    assert not _in_step(columns=[*COLUMNS[:2], ("round", "DOUBLE")])  # or one of another type
    assert not _in_step(rows_version=3)  # the domain makes other rows now
    assert not _in_step(rows_version=1)
    assert not _in_step(storing=True)  # an earlier store stopped part-way
    assert not _in_step(earlier_layout=True)  # one file, from before the slice
    assert not _in_step(missing_file=True)  # a month's file removed by hand


def test_new_records_sort_after_the_last() -> None:
    """As their files sort, which is the order a rebuild reads them in."""
    assert follows(None, [LAST])  # the table has no row yet
    assert follows(LAST, [])
    assert follows(LAST, ["20261101T100000000001Z-000000000000"])  # a microsecond later
    assert follows(LAST, ["20261101T100000000000Z-bbbbbbbbbbbb"])  # the same instant, a higher hash
    assert not follows(LAST, ["20261101T100000000000Z-999999999999"])  # the same instant, a lower one
    assert not follows(LAST, ["20261031T100000000000Z-ffffffffffff"])  # a clock set back
    assert not follows(LAST, ["20261101T100000000001Z-000000000000", "20261101T090000000000Z-0"])
    # The same content at the same instant gets a number, and its file sorts before the first: "-" before ".".
    assert not follows(LAST, [f"{LAST}-1"])
    assert follows(f"{LAST}-1", [LAST])
    assert not follows(LAST, [LAST])
