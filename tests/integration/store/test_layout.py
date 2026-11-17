"""mvp-store task 1.4: a silver table is a folder of month files that `_table.json` names; a read takes its
window's files, in stored order; a rebuild writes the months from bronze, a batch of files at a time; a table
in the earlier layout is read until a rebuild replaces it (design C1, C4; R1.4, R2.5)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path

import duckdb
import pytest

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.core.hashing import content_sha256
from fantadamus.domains import facts
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.lake import duckdb_store
from fantadamus.lake.duckdb_store import Incoming, LakeStore, connect
from fantadamus.lake.months import Description
from tests.xy_harness import CLUBS

URL = "https://example.org/calendar"
OCTOBER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)
EARLY_NOVEMBER = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATE_NOVEMBER = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)


def fixtures(round: int, swap: bool = False) -> FixturesPayload:
    kickoff = dt.datetime(2026, 12, 1, 15, 0, tzinfo=dt.UTC) + dt.timedelta(days=7 * round)
    pairs = [("Alfa", "Beta"), ("Gamma", "Delta")] if not swap else [("Beta", "Alfa"), ("Delta", "Gamma")]
    return FixturesPayload.model_validate(
        {
            "round": round,
            "matches": [{"home": home, "away": away, "kickoff_at": kickoff} for home, away in pairs],
        }
    )


def submit(
    store: LakeStore, payload: FixturesPayload, captured_at: dt.datetime, received_at: dt.datetime
) -> None:
    facts.submit(
        store,
        FIXTURES,
        payload,
        source_url=URL,
        captured_at=captured_at,
        published_at=None,
        allowed_hosts=["example.org"],
        clock=fixed_clock(received_at),
        submitted_by="user-1",
        clubs=CLUBS,
    )


def three_reads(store: LakeStore) -> None:
    for round, when in ((9, OCTOBER), (10, EARLY_NOVEMBER), (11, LATE_NOVEMBER)):
        submit(store, fixtures(round), when, when)


def files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in (root / "silver").rglob("*") if path.is_file())


def month_file(store: LakeStore, month: str) -> Path:
    """The file `_table.json` names for a month."""
    written = store.description(FIXTURES.table)
    assert written is not None
    return store.root / "silver" / "fixtures" / written.files[month]


def named(store: LakeStore) -> list[str]:
    """`_table.json`, and the files it names: what the table's folder should hold."""
    written = store.description(FIXTURES.table)
    assert written is not None
    return sorted(f"silver/fixtures/{name}" for name in [*written.files.values(), "_table.json"])


def test_a_rebuild_writes_a_file_for_each_month(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    three_reads(store)
    written = store.description(FIXTURES.table)
    assert written == Description(
        columns=list(FIXTURES.table.columns.items()),
        rows_version=FIXTURES.rows_version,
        last_bronze=store.bronze_files("fixtures")[-1].stem,
        files=written.files if written is not None else {},
    )
    assert written is not None
    assert list(written.files) == ["2026-10", "2026-11"]
    assert all(name.startswith(f"{month}.") for month, name in written.files.items())
    assert files(tmp_path) == named(store)  # and nothing else
    assert store.months(FIXTURES.table) == ["2026-10", "2026-11"]
    rows = facts.read_silver(store, FIXTURES)
    assert [(row.round, row.captured_at) for row in rows] == [
        (9, OCTOBER),
        (9, OCTOBER),
        (10, EARLY_NOVEMBER),
        (10, EARLY_NOVEMBER),
        (11, LATE_NOVEMBER),
        (11, LATE_NOVEMBER),
    ]
    assert facts.rebuild(store, FIXTURES, CLUBS) == 6  # and again gives the same
    assert facts.read_silver(store, FIXTURES) == rows
    again = store.description(FIXTURES.table)
    assert again is not None
    assert set(again.files.values()).isdisjoint(written.files.values())  # in files of its own
    assert files(tmp_path) == named(store)  # the earlier ones gone


def test_a_window_reads_only_its_months(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    three_reads(store)
    month_file(store, "2026-10").write_bytes(b"not a Parquet file")
    november = facts.read_silver(store, FIXTURES, dt.datetime(2026, 11, 1, tzinfo=dt.UTC), LATE_NOVEMBER)
    assert [row.round for row in november] == [10, 10, 11, 11]  # October's file is never opened
    late = facts.read_silver(store, FIXTURES, dt.datetime(2026, 11, 10, tzinfo=dt.UTC), LATE_NOVEMBER)
    assert [row.round for row in late] == [11, 11]  # and within a month, only the window's rows
    instant = facts.read_silver(store, FIXTURES, EARLY_NOVEMBER, EARLY_NOVEMBER)
    assert [row.round for row in instant] == [10, 10]  # both ends are included
    assert facts.read_silver(store, FIXTURES, until=dt.datetime(2026, 9, 30, tzinfo=dt.UTC)) == []
    with pytest.raises(duckdb.Error):
        facts.read_silver(store, FIXTURES)  # without a window, every month is read


def test_rows_come_back_in_stored_order(tmp_path: Path) -> None:
    """Within a month, in the order the submissions arrived; the months oldest first, whenever they came."""
    store = LakeStore(tmp_path)
    arrived = dt.datetime(2026, 11, 21, 8, 0, tzinfo=dt.UTC)
    submit(store, fixtures(11), LATE_NOVEMBER, arrived)
    submit(store, fixtures(10, swap=True), EARLY_NOVEMBER, arrived + dt.timedelta(minutes=1))
    submit(store, fixtures(9), OCTOBER, arrived + dt.timedelta(minutes=2))  # read long ago, submitted last
    rows = facts.read_silver(store, FIXTURES)
    assert [(row.round, row.home) for row in rows] == [
        (9, "alfa"),
        (9, "gamma"),
        (11, "alfa"),
        (11, "gamma"),
        (10, "beta"),
        (10, "delta"),
    ]


def test_files_are_read_oldest_name_first_however_they_are_given(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    three_reads(store)
    october, november = month_file(store, "2026-10"), month_file(store, "2026-11")
    rows = duckdb_store._read_parquet([november, october])
    assert [row["round"] for row in rows] == [9, 9, 10, 10, 11, 11]
    assert [Path(str(row["filename"])) for row in rows] == [october] * 2 + [november] * 4


def test_a_file_that_isnt_named_is_never_read(tmp_path: Path) -> None:
    """As one a stopped store wrote, or a copy made by hand: `_table.json` doesn't name it."""
    store = LakeStore(tmp_path)
    three_reads(store)
    rows = facts.read_silver(store, FIXTURES)
    strays = [tmp_path / "silver" / "fixtures" / name for name in ("2026-10.parquet", "2026-11.0123.parquet")]
    for stray in strays:
        stray.write_bytes(b"not a Parquet file")
    assert facts.read_silver(store, FIXTURES) == rows
    assert facts.read_silver(store, FIXTURES, OCTOBER, LATE_NOVEMBER) == rows
    submit(store, fixtures(12), LATE_NOVEMBER + dt.timedelta(days=1), LATE_NOVEMBER + dt.timedelta(days=1))
    assert not any(stray.exists() for stray in strays)  # a store removes what the table doesn't name
    assert files(tmp_path) == named(store)


def test_a_month_removed_by_hand_comes_back_at_the_next_store(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    three_reads(store)
    rows = facts.read_silver(store, FIXTURES)
    month_file(store, "2026-10").unlink()
    assert [row.round for row in facts.read_silver(store, FIXTURES)] == [10, 10, 11, 11]  # its rows missing
    later = LATE_NOVEMBER + dt.timedelta(days=1)
    submit(store, fixtures(12), later, later)  # the store finds a file missing, and rebuilds
    assert facts.read_silver(store, FIXTURES)[:6] == rows
    assert files(tmp_path) == named(store)


def _envelope(payload: FixturesPayload, captured_at: dt.datetime) -> BronzeEnvelope:
    data = payload.model_dump(mode="json")
    return BronzeEnvelope(
        source=FIXTURES.source,
        source_url=URL,
        published_at=None,
        captured_at=captured_at,
        received_at=captured_at,
        content_sha256=content_sha256(data),
        contract_version=payload.__version__,
        submitted_by="user-1",
        payload=data,
    )


def _in_the_earlier_layout(store: LakeStore) -> list[FixtureRow]:
    """A lake as it was stored before this slice: bronze, and one Parquet file for the table."""
    rows: list[FixtureRow] = []
    for round, when in ((9, OCTOBER), (10, EARLY_NOVEMBER)):
        envelope = _envelope(fixtures(round), when)
        store.append_bronze(envelope)
        source = facts.Source(
            source_url=URL, captured_at=envelope.captured_at, content_sha256=envelope.content_sha256
        )
        rows += FIXTURES.to_rows(fixtures(round), CLUBS, source)
    target = store.root / "silver" / "fixtures.parquet"
    target.parent.mkdir(parents=True)
    with connect() as connection:
        connection.execute(FIXTURES.table.create_sql)
        for row in rows:
            connection.execute(
                "INSERT INTO fixtures VALUES (?, ?, ?, ?, ?, ?, ?)", list(row.model_dump().values())
            )
        connection.table("fixtures").write_parquet(str(target))
    return rows


def test_the_earlier_layout_is_read_until_a_rebuild_replaces_it(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rows = _in_the_earlier_layout(store)
    assert files(tmp_path) == ["silver/fixtures.parquet"]
    assert store.description(FIXTURES.table) is None
    assert facts.read_silver(store, FIXTURES) == rows
    assert facts.read_silver(store, FIXTURES, since=dt.datetime(2026, 11, 1, tzinfo=dt.UTC)) == rows[2:]
    # A rebuild stopped before `_table.json` was written: the earlier file is still the table.
    half = tmp_path / "silver" / "fixtures"
    half.mkdir()
    (half / "2026-10.0123456789ab.parquet").write_bytes(b"half a rebuild")
    assert facts.read_silver(store, FIXTURES) == rows
    assert facts.rebuild(store, FIXTURES, CLUBS) == 4
    assert files(tmp_path) == named(store)  # the earlier file and the half rebuild gone
    assert store.months(FIXTURES.table) == ["2026-10", "2026-11"]
    assert facts.read_silver(store, FIXTURES) == rows


def test_a_store_by_earlier_code_is_noticed(tmp_path: Path) -> None:
    """A server still running code from before the slice stores as it did: its bronze file, then the whole
    table again as one file. The next store finds that file beside the month files, and rebuilds."""
    store = LakeStore(tmp_path)
    three_reads(store)
    earlier_read = LATE_NOVEMBER + dt.timedelta(hours=1)
    store.append_bronze(_envelope(fixtures(12), earlier_read))  # the earlier code's store
    (tmp_path / "silver" / "fixtures.parquet").write_bytes(b"the whole table, as the earlier code wrote it")
    later = LATE_NOVEMBER + dt.timedelta(days=1)
    submit(store, fixtures(13), later, later)
    assert [row.round for row in facts.read_silver(store, FIXTURES)] == [9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
    assert files(tmp_path) == named(store)  # its file gone


def test_a_rebuild_reads_bronze_in_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LakeStore(tmp_path)
    for index in range(5):
        store.append_bronze(_envelope(fixtures(index + 1), OCTOBER + dt.timedelta(hours=index)))
    whole = store.read_bronze(FIXTURES.source)
    read = duckdb_store._read_parquet
    batches: list[int] = []

    def counting(
        paths: Sequence[Path], since: dt.datetime | None = None, until: dt.datetime | None = None
    ) -> list[dict[str, object]]:
        batches.append(len(paths))
        return read(paths, since, until)

    monkeypatch.setattr(duckdb_store, "BRONZE_BATCH", 2)
    monkeypatch.setattr(duckdb_store, "_read_parquet", counting)
    assert store.read_bronze(FIXTURES.source) == whole
    assert batches == [2, 2, 1]
    assert [record.envelope.captured_at for record in whole] == [
        OCTOBER + dt.timedelta(hours=i) for i in range(5)
    ]
    batches.clear()
    assert facts.rebuild(store, FIXTURES, CLUBS) == 10
    assert batches == [2, 2, 1]


def test_a_month_that_isnt_one_is_refused(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    with pytest.raises(ValueError, match="isn't a month"):
        store.replace_rows(FIXTURES.table, [Incoming("a-bronze-record", "../elsewhere", "{}")], 1)
    assert not any(path.is_file() for path in tmp_path.rglob("*"))
