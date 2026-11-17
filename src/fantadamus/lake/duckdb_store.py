"""The local lake: DuckDB over Parquet files (R16.3; mvp-store design C1 to C3).

Layout under the root (default `data/local/lake/`), which maps to `s3://fantadamus-lake-<account>/` later:

    bronze/<source>/<received_at>-<sha12>.parquet   one file per submission, never rewritten (R16.3)
    silver/<table>/_table.json                      the table: its columns, rows version and files
    silver/<table>/<YYYY-MM>.<id>.parquet           the rows captured in that month, in stored order
    silver/<table>/_storing                         there while a store is under way
    silver/<table>.parquet                          the earlier layout, read until a rebuild replaces it
    .lock                                           held by a store or a rebuild, one at a time

Timestamps are stored as TIMESTAMPTZ and read back as UTC datetimes. Silver rows reach DuckDB in bulk, through
a JSON-lines file read with the table's own column types: an insert a row takes about 25 times as long. All
SQL is static; paths and rows go through DuckDB's relation API and parameters.

A silver file is written once, under a name of its own, and never changed. `_table.json` names the table's
files, and writing it is the one moment a store or a rebuild takes effect: a reader takes the files it names,
so it sees the whole table before or after, never part of each (R1.4). A file `_table.json` no longer names
is removed afterwards; a reader that finds one gone reads `_table.json` again. Readers take no lock.

A store adds its rows after those of their month when the table is in step with bronze, and the table is
rebuilt when it isn't (`storing`; mvp-store C3). Either way the table is what a rebuild gives: the months
oldest first, and in each the rows of the bronze records as their files sort.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import functools
import json
import os
import re
import uuid
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, NamedTuple

import duckdb
from pydantic import ValidationError

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.core.files import temporary_beside
from fantadamus.core.hashing import canonical_json
from fantadamus.lake.months import MONTH, Description, in_step, months_in

DEFAULT_ROOT = Path("data/local/lake")
TIMESTAMPTZ = "TIMESTAMP WITH TIME ZONE"
BRONZE_BATCH = 500
"""How many bronze files are read at once: a rebuild's memory doesn't grow with the season."""
DESCRIPTION = "_table.json"
STORING = "_storing"
LOCK = ".lock"
_COLUMN = re.compile(r"[(,] *(\w+) (\w+)")

Row = Sequence[object]


@dataclass(frozen=True)
class Table:
    """A Parquet table: its name and the static SQL that says its columns."""

    name: str
    create_sql: str

    @property
    def columns(self) -> dict[str, str]:
        """Each column's SQL type, in the table's order."""
        return dict(_COLUMN.findall(self.create_sql))


class Incoming(NamedTuple):
    """A silver row on its way in."""

    bronze_id: str
    """The bronze record it came from."""
    month: str
    """The month it's stored under."""
    line: str
    """The row as JSON, a value for each of the table's columns."""


BRONZE = Table(
    "bronze",
    "CREATE TEMP TABLE bronze (source VARCHAR, source_url VARCHAR, published_at TIMESTAMPTZ, "
    "captured_at TIMESTAMPTZ, received_at TIMESTAMPTZ, content_sha256 VARCHAR, contract_version VARCHAR, "
    "submitted_by VARCHAR, payload VARCHAR)",
)
_BRONZE_INSERT = "INSERT INTO bronze VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"


@dataclass(frozen=True)
class BronzeRecord:
    """One bronze file: its ID (the file name without `.parquet`) and its validated envelope."""

    bronze_id: str
    envelope: BronzeEnvelope


@functools.cache
def _database() -> duckdb.DuckDBPyConnection:
    database = duckdb.connect()
    database.execute("SET GLOBAL TimeZone = 'UTC'")
    # The lake is small: a query is no slower on one thread, and a thread per core only competes with
    # everything else on a busy machine (a lineup took 1.44 CPU-seconds on one, 1.51 on eight).
    database.execute("SET GLOBAL threads = 1")
    return database


def connect() -> duckdb.DuckDBPyConnection:
    """A new connection to one shared in-memory DuckDB database whose time zone is UTC.

    Opening a database costs tens of milliseconds; a connection to an open one costs microseconds. Tables
    are created TEMP, so each connection sees only its own; close the connection when done.
    """
    return _database().cursor()


def _write_bronze(row: Row, path: Path) -> None:
    with connect() as connection:
        connection.execute(BRONZE.create_sql)
        connection.execute(_BRONZE_INSERT, list(row))
        connection.table(BRONZE.name).write_parquet(str(path))


def _read_parquet(
    paths: Sequence[Path], since: dt.datetime | None = None, until: dt.datetime | None = None
) -> list[dict[str, object]]:
    """The files' rows, each with its file's name, by file name and then by place in the file; with `since`
    or `until`, those captured from one to the other."""
    with connect() as connection:
        relation = connection.read_parquet([str(path) for path in paths], filename=True, file_row_number=True)
        captured = duckdb.ColumnExpression("captured_at")
        if since is not None:
            relation = relation.filter(captured >= duckdb.ConstantExpression(since))
        if until is not None:
            relation = relation.filter(captured <= duckdb.ConstantExpression(until))
        relation = relation.order("filename, file_row_number")
        kinds = zip(relation.columns, relation.types, strict=True)
        zoned = {name for name, kind in kinds if str(kind) == TIMESTAMPTZ}
        columns = [
            f'"{name}"::TIMESTAMP AS "{name}"' if name in zoned else f'"{name}"'
            for name in relation.columns
            if name != "file_row_number"
        ]
        projected = relation.project(", ".join(columns))
        rows = [dict(zip(projected.columns, row, strict=True)) for row in projected.fetchall()]
    for row in rows:
        for name in zoned:
            value = row[name]
            if isinstance(value, dt.datetime):
                row[name] = value.replace(tzinfo=dt.UTC)
    return rows


@dataclass
class _Spooled:
    """Rows written out for loading: a JSON-lines file for each month, how many rows there are, and the
    bronze record the last one came from."""

    months: dict[str, Path] = field(default_factory=dict)
    rows: int = 0
    last_bronze: str | None = None


@contextlib.contextmanager
def _spooled(directory: Path, rows: Iterable[Incoming]) -> Iterator[_Spooled]:
    """The rows as a JSON-lines file for each month beside the table, oldest month first, removed
    afterwards."""
    found = _Spooled()
    files: dict[str, IO[str]] = {}
    try:
        for row in rows:
            if not MONTH.fullmatch(row.month):
                raise ValueError(f"{row.month!r} isn't a month")
            if row.month not in files:
                found.months[row.month] = temporary_beside(directory / f"{row.month}.ndjson")
                files[row.month] = found.months[row.month].open("w", encoding="utf-8")
            files[row.month].write(row.line + "\n")
            found.rows += 1
            found.last_bronze = row.bronze_id
        for file in files.values():
            file.close()
        found.months = {month: found.months[month] for month in sorted(found.months)}
        yield found
    finally:
        for file in files.values():
            file.close()
        for spooled in found.months.values():
            spooled.unlink(missing_ok=True)


def _load(table: Table, lines: Path, target: Path, *, after: Path | None = None) -> None:
    """Write `target` from a JSON-lines file, typed by the table's own columns; with `after`, the lines'
    rows follow those of that file."""
    with connect() as connection:
        loaded = connection.read_json(str(lines), format="newline_delimited", columns=table.columns)
        if after is not None:
            loaded = connection.read_parquet(str(after)).union(loaded)  # all of both, in that order
        loaded.write_parquet(str(target))


class LakeStore:
    """Bronze and silver under one root directory."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def bronze_files(self, source: str) -> list[Path]:
        return sorted((self.root / "bronze" / source).glob("*.parquet"))

    def append_bronze(self, envelope: BronzeEnvelope) -> str:
        """Write the envelope to a new bronze file and return its ID. Existing files are never touched."""
        directory = self.root / "bronze" / envelope.source
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{envelope.received_at:%Y%m%dT%H%M%S%fZ}-{envelope.content_sha256[:12]}"
        row = (
            envelope.source,
            envelope.source_url,
            envelope.published_at,
            envelope.captured_at,
            envelope.received_at,
            envelope.content_sha256,
            envelope.contract_version,
            envelope.submitted_by,
            canonical_json(envelope.payload),
        )
        temporary = directory / f".{stem}.tmp"
        _write_bronze(row, temporary)
        attempt = 0
        try:
            while True:
                bronze_id = stem if attempt == 0 else f"{stem}-{attempt}"
                try:
                    os.link(temporary, directory / f"{bronze_id}.parquet")  # fails rather than overwrite
                except FileExistsError:
                    attempt += 1
                else:
                    return bronze_id
        finally:
            temporary.unlink()

    def iter_bronze(self, source: str) -> Iterator[BronzeRecord]:
        """Every bronze record of a source, oldest file name first, re-validated against the envelope, read
        `BRONZE_BATCH` files at a time."""
        files = self.bronze_files(source)
        for start in range(0, len(files), BRONZE_BATCH):
            for row in _read_parquet(files[start : start + BRONZE_BATCH]):
                fields = {name: value for name, value in row.items() if name != "filename"}
                fields["payload"] = json.loads(str(row["payload"]))
                envelope = BronzeEnvelope.model_validate(fields)
                yield BronzeRecord(bronze_id=Path(str(row["filename"])).stem, envelope=envelope)

    def read_bronze(self, source: str) -> list[BronzeRecord]:
        return list(self.iter_bronze(source))

    def _folder(self, table: Table) -> Path:
        return self.root / "silver" / table.name

    def _earlier_layout(self, table: Table) -> Path:
        return self.root / "silver" / f"{table.name}.parquet"

    def description(self, table: Table) -> Description | None:
        """What the table's files were written with; None if it was never written, or can't be read."""
        try:
            text = (self._folder(table) / DESCRIPTION).read_text(encoding="utf-8")
            return Description.model_validate_json(text)
        except (OSError, ValidationError):
            return None

    def _describe(self, table: Table, written: Description) -> None:
        """Write `_table.json`: from here, the table is what it says."""
        target = self._folder(table) / DESCRIPTION
        temporary = temporary_beside(target)
        temporary.write_text(written.model_dump_json() + "\n", encoding="utf-8")
        temporary.replace(target)

    def _tidy(self, table: Table, written: Description) -> None:
        """Remove what the table no longer is: a month's file a store replaced, what a stopped store left, and
        the earlier layout's file. A reader still about to read one finds it gone and looks again."""
        keep = {*written.files.values(), DESCRIPTION, STORING}
        for path in self._folder(table).iterdir():
            if path.name not in keep and not path.is_dir():
                path.unlink(missing_ok=True)
        self._earlier_layout(table).unlink(missing_ok=True)

    def _write_month(self, table: Table, month: str, lines: Path, *, after: str | None = None) -> str:
        """A new file for a month, from a JSON-lines file and, with `after`, the rows of that file first; its
        name. Nothing reads it until `_table.json` names it."""
        name = f"{month}.{uuid.uuid4().hex[:12]}.parquet"
        target = self._folder(table) / name
        try:
            _load(table, lines, target, after=self._folder(table) / after if after else None)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return name

    def months(self, table: Table) -> list[str]:
        """The months the table has a file for, oldest first."""
        written = self.description(table)
        return sorted(written.files) if written is not None else []

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        """Hold the lake's lock, as a store and a rebuild do: one at a time, in this process or another,
        each waiting its turn. It isn't re-entrant, and readers don't take it."""
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / LOCK).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield  # closing the file lets the lock go

    @contextlib.contextmanager
    def storing(self, table: Table, rows_version: int) -> Iterator[Description | None]:
        """A store to a silver table, entered holding the lock: what the table is if rows can be added to it,
        or None if it has to be rebuilt. `_storing` is there from here until the store has finished, so a
        store that stops part-way leaves it behind, and the next one rebuilds."""
        directory = self._folder(table)
        marker = directory / STORING
        written = self.description(table)
        missing = written is not None and not all(
            (directory / name).is_file() for name in written.files.values()
        )
        addable = in_step(
            written,
            list(table.columns.items()),
            rows_version,
            storing=marker.exists(),
            earlier_layout=self._earlier_layout(table).is_file(),
            missing_file=missing,
        )
        directory.mkdir(parents=True, exist_ok=True)
        marker.touch()
        yield written if addable else None
        marker.unlink()

    def replace_rows(self, table: Table, rows: Iterable[Incoming], rows_version: int) -> int:
        """Write the table again from `rows`, given as a rebuild reads them, and return how many there were.
        Called holding the lock."""
        self._folder(table).mkdir(parents=True, exist_ok=True)
        with _spooled(self._folder(table), rows) as spooled:
            files = {month: self._write_month(table, month, lines) for month, lines in spooled.months.items()}
        written = Description(
            columns=list(table.columns.items()),
            rows_version=rows_version,
            last_bronze=spooled.last_bronze,
            files=files,
        )
        self._describe(table, written)
        self._tidy(table, written)
        return spooled.rows

    def append_rows(self, table: Table, rows: Iterable[Incoming], written: Description) -> int:
        """Add `rows` after those of their months, and return how many there were. Only for a table in step,
        with rows of bronze records that sort after `written.last_bronze`; called holding the lock."""
        files = dict(written.files)
        with _spooled(self._folder(table), rows) as spooled:
            for month, lines in spooled.months.items():
                files[month] = self._write_month(table, month, lines, after=written.files.get(month))
        if spooled.rows:
            now = written.model_copy(update={"files": files, "last_bronze": spooled.last_bronze})
            self._describe(table, now)
            self._tidy(table, now)
        return spooled.rows

    def _files(
        self, table: Table, written: Description | None, since: dt.datetime | None, until: dt.datetime | None
    ) -> list[Path]:
        """The files a read opens: those `_table.json` names for the months the window touches; or the
        earlier layout's one file, until the table has been written again."""
        if written is not None:
            chosen = months_in(written.files, since, until)
            return [self._folder(table) / written.files[month] for month in chosen]
        earlier = self._earlier_layout(table)
        return [earlier] if earlier.is_file() else []

    def _read[T](
        self,
        table: Table,
        since: dt.datetime | None,
        until: dt.datetime | None,
        read: Callable[[Sequence[Path]], T],
    ) -> T | None:
        """What `read` gives for the files of the table's window, or None if there are none. A store that
        takes effect meanwhile removes files the read had listed: it then lists them again. A file that is
        gone while `_table.json` still names it was removed by hand, and its rows are left out."""
        while True:
            written = self.description(table)
            files = self._files(table, written, since, until)
            present = [path for path in files if path.is_file()]
            try:
                found = read(present) if present else None
            except (duckdb.Error, OSError):
                if self.description(table) != written:
                    continue
                raise
            if len(present) < len(files) and self.description(table) != written:
                continue
            return found

    def read_rows(
        self, table: Table, since: dt.datetime | None = None, until: dt.datetime | None = None
    ) -> list[dict[str, object]]:
        """The table's rows in the order they were stored, or no rows if it hasn't been built yet; with
        `since` or `until`, those captured from one to the other, both included, from the months they
        touch."""
        rows = self._read(table, since, until, lambda files: _read_parquet(files, since, until))
        return [{key: value for key, value in row.items() if key != "filename"} for row in rows or []]
