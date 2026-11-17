"""The local lake: DuckDB over Parquet files (R16.3; mvp-store design C1, C2).

Layout under the root (default `data/local/lake/`), which maps to `s3://fantadamus-lake-<account>/` later:

    bronze/<source>/<received_at>-<sha12>.parquet   one file per submission, never rewritten (R16.3)
    silver/<table>/<YYYY-MM>.parquet                the rows captured in that month, in stored order
    silver/<table>/_table.json                      what the files were written with
    silver/<table>.parquet                          the earlier layout, read until a rebuild replaces it

Timestamps are stored as TIMESTAMPTZ and read back as UTC datetimes. Silver rows reach DuckDB in bulk, through
a JSON-lines file read with the table's own column types: an insert a row takes about 25 times as long. All
SQL is static; paths and rows go through DuckDB's relation API and parameters.

A silver file is written under a temporary name and renamed into place, and a reader takes no lock. DuckDB
opens a file once for its description and again for its rows, so a read checks afterwards that no file it
read was replaced meanwhile, and reads again if one was (R1.4).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import functools
import json
import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import duckdb
from pydantic import BaseModel, ValidationError

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.core.files import temporary_beside
from fantadamus.core.hashing import canonical_json
from fantadamus.lake.months import MONTH, months_in

DEFAULT_ROOT = Path("data/local/lake")
TIMESTAMPTZ = "TIMESTAMP WITH TIME ZONE"
BRONZE_BATCH = 500
"""How many bronze files are read at once: a rebuild's memory doesn't grow with the season."""
DESCRIPTION = "_table.json"
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


class Description(BaseModel):
    """What a silver table's files were written with (`_table.json`)."""

    columns: list[str]
    rows_version: int
    """The domain's, raised when its payloads become other rows."""


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


def _marks(paths: Sequence[Path]) -> list[tuple[int, int, int]] | None:
    """What tells each file from one renamed over it: which file it is, its size and when it was written.
    None if one is gone."""
    try:
        found = [path.lstat() for path in paths]
    except FileNotFoundError:
        return None
    return [(stat.st_ino, stat.st_size, stat.st_mtime_ns) for stat in found]


@contextlib.contextmanager
def _spooled(directory: Path, rows: Iterable[tuple[str, str]]) -> Iterator[tuple[dict[str, Path], int]]:
    """The rows, each its month and its JSON line, as a JSON-lines file for each month beside the table,
    oldest month first, removed afterwards; and how many rows there are."""
    paths: dict[str, Path] = {}
    files: dict[str, IO[str]] = {}
    count = 0
    try:
        for month, line in rows:
            if not MONTH.fullmatch(month):
                raise ValueError(f"{month!r} isn't a month")
            if month not in files:
                paths[month] = temporary_beside(directory / f"{month}.ndjson")
                files[month] = paths[month].open("w", encoding="utf-8")
            files[month].write(line + "\n")
            count += 1
        for file in files.values():
            file.close()
        yield {month: paths[month] for month in sorted(paths)}, count
    finally:
        for file in files.values():
            file.close()
        for spooled in paths.values():
            spooled.unlink(missing_ok=True)


def _load(table: Table, lines: Path, target: Path) -> None:
    """Write `target` whole from a JSON-lines file, typed by the table's own columns: under a temporary name
    first, then renamed into place."""
    temporary = temporary_beside(target)
    try:
        with connect() as connection:
            loaded = connection.read_json(str(lines), format="newline_delimited", columns=table.columns)
            loaded.write_parquet(str(temporary))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


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

    def replace_rows(self, table: Table, rows: Iterable[tuple[str, str]], description: Description) -> int:
        """Write the table again from `rows`, each its month and its JSON line, and return how many there
        were. The months the table no longer has, and its earlier layout, are removed last."""
        directory = self._folder(table)
        directory.mkdir(parents=True, exist_ok=True)
        with _spooled(directory, rows) as (months, count):
            for month, lines in months.items():
                _load(table, lines, directory / f"{month}.parquet")
        for path in directory.glob("*.parquet"):
            if path.stem not in months:
                path.unlink()
        temporary = temporary_beside(directory / DESCRIPTION)
        temporary.write_text(description.model_dump_json() + "\n", encoding="utf-8")
        temporary.replace(directory / DESCRIPTION)
        self._earlier_layout(table).unlink(missing_ok=True)
        return count

    def _files(self, table: Table, since: dt.datetime | None, until: dt.datetime | None) -> list[Path]:
        """The files a read opens: the months its window touches; or the earlier layout's one file, until
        the table has been written again."""
        directory, earlier = self._folder(table), self._earlier_layout(table)
        if earlier.is_file() and not (directory / DESCRIPTION).is_file():
            return [earlier]
        names = [path.stem for path in directory.glob("*.parquet") if MONTH.fullmatch(path.stem)]
        return [directory / f"{month}.parquet" for month in months_in(names, since, until)]

    def _read[T](
        self,
        table: Table,
        since: dt.datetime | None,
        until: dt.datetime | None,
        read: Callable[[Sequence[Path]], T],
    ) -> T | None:
        """What `read` gives for the files of the table's window, or None if there are none; asked again
        whenever a store replaced or removed one of them meanwhile, so that no read is half of each."""
        while True:
            files = self._files(table, since, until)
            if not files:
                return None
            before = _marks(files)
            if before is None:
                continue
            try:
                found = read(files)
            except duckdb.Error:
                if _marks(files) == before:
                    raise
                continue
            if _marks(files) == before:
                return found

    def read_rows(
        self, table: Table, since: dt.datetime | None = None, until: dt.datetime | None = None
    ) -> list[dict[str, object]]:
        """The table's rows in the order they were stored, or no rows if it hasn't been built yet; with
        `since` or `until`, those captured from one to the other, both included, from the months they
        touch."""
        rows = self._read(table, since, until, lambda files: _read_parquet(files, since, until))
        return [{key: value for key, value in row.items() if key != "filename"} for row in rows or []]
