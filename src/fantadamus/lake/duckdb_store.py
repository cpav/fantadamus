"""The local lake: DuckDB over Parquet files (R16.3, R16.8).

Layout under the root (default `data/local/lake/`), which maps to `s3://fantadamus-lake-<account>/` later:

    bronze/<source>/<received_at>-<sha12>.parquet   one file per submission, never rewritten (R16.3)
    silver/<table>.parquet                          rebuilt from bronze on every refresh
    gold/<table>.parquet                            rebuilt from silver on every refresh

Timestamps are stored as TIMESTAMPTZ and read back as UTC datetimes. All SQL is static; paths and rows go
through DuckDB's relation API and parameters.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import duckdb

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.core.hashing import canonical_json

DEFAULT_ROOT = Path("data/local/lake")
TIMESTAMPTZ = "TIMESTAMP WITH TIME ZONE"
INSERT_BATCH = 200

Layer = Literal["silver", "gold"]
Row = Sequence[object]


@dataclass(frozen=True)
class Table:
    """A Parquet table: its name and the static SQL that creates and fills it in DuckDB."""

    name: str
    create_sql: str
    insert_sql: str


BRONZE = Table(
    "bronze",
    "CREATE TEMP TABLE bronze (source VARCHAR, source_url VARCHAR, published_at TIMESTAMPTZ, "
    "captured_at TIMESTAMPTZ, received_at TIMESTAMPTZ, content_sha256 VARCHAR, contract_version VARCHAR, "
    "submitted_by VARCHAR, payload VARCHAR)",
    "INSERT INTO bronze VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
)


@dataclass(frozen=True)
class BronzeRecord:
    """One bronze file: its ID (the file name without `.parquet`) and its validated envelope."""

    bronze_id: str
    envelope: BronzeEnvelope


@functools.cache
def _database() -> duckdb.DuckDBPyConnection:
    database = duckdb.connect()
    database.execute("SET GLOBAL TimeZone = 'UTC'")
    return database


def connect() -> duckdb.DuckDBPyConnection:
    """A new connection to one shared in-memory DuckDB database whose time zone is UTC.

    Opening a database costs tens of milliseconds; a connection to an open one costs microseconds. Tables
    are created TEMP, so each connection sees only its own; close the connection when done.
    """
    return _database().cursor()


def fill(connection: duckdb.DuckDBPyConnection, table: Table, rows: Sequence[Row]) -> None:
    """Create `table` in the connection and insert the rows, up to `INSERT_BATCH` per statement: `executemany`
    runs one statement per row, about seven times slower. Only the static placeholders are repeated."""
    connection.execute(table.create_sql)
    placeholders = table.insert_sql[table.insert_sql.index("(") :]
    for start in range(0, len(rows), INSERT_BATCH):
        batch = rows[start : start + INSERT_BATCH]
        statement = ", ".join([table.insert_sql, *[placeholders] * (len(batch) - 1)])
        connection.execute(statement, [value for row in batch for value in row])


def _write_parquet(table: Table, rows: Sequence[Row], path: Path) -> None:
    with connect() as connection:
        fill(connection, table, rows)
        connection.table(table.name).write_parquet(str(path))


def _read_parquet(paths: Sequence[Path]) -> list[dict[str, object]]:
    with connect() as connection:
        relation = connection.read_parquet([str(path) for path in paths], filename=True)
        kinds = zip(relation.columns, relation.types, strict=True)
        zoned = {name for name, kind in kinds if str(kind) == TIMESTAMPTZ}
        columns = [
            f'"{name}"::TIMESTAMP AS "{name}"' if name in zoned else f'"{name}"' for name in relation.columns
        ]
        projected = relation.project(", ".join(columns))
        rows = [dict(zip(projected.columns, row, strict=True)) for row in projected.fetchall()]
    for row in rows:
        for name in zoned:
            value = row[name]
            if isinstance(value, dt.datetime):
                row[name] = value.replace(tzinfo=dt.UTC)
    return rows


class LakeStore:
    """Bronze, silver and gold under one root directory."""

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
        _write_parquet(BRONZE, [row], temporary)
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

    def read_bronze(self, source: str) -> list[BronzeRecord]:
        """Every bronze record of a source, oldest file name first, re-validated against the envelope."""
        files = self.bronze_files(source)
        if not files:
            return []
        records = []
        for row in sorted(_read_parquet(files), key=lambda row: str(row["filename"])):
            fields = {name: value for name, value in row.items() if name != "filename"}
            fields["payload"] = json.loads(str(row["payload"]))
            envelope = BronzeEnvelope.model_validate(fields)
            records.append(BronzeRecord(bronze_id=Path(str(row["filename"])).stem, envelope=envelope))
        return records

    def write_table(self, layer: Layer, table: Table, rows: Sequence[Row]) -> Path:
        """Replace a silver or gold table atomically."""
        path = self.root / layer / f"{table.name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        _write_parquet(table, rows, temporary)
        temporary.replace(path)
        return path

    def read_table(self, layer: Layer, name: str) -> list[dict[str, object]]:
        """A silver or gold table's rows, or no rows if it hasn't been built yet."""
        path = self.root / layer / f"{name}.parquet"
        if not path.is_file():
            return []
        return [
            {key: value for key, value in row.items() if key != "filename"} for row in _read_parquet([path])
        ]
