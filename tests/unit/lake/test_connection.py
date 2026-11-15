"""The lake's DuckDB connection: UTC, and one worker thread. The lake is small, so a query runs no slower on
one thread, and DuckDB's default of a thread per core only competed with everything else on a busy machine:
a lineup took 1.44 CPU-seconds on one thread against 1.51 on eight, and its budget test failed under load."""

from __future__ import annotations

from fantadamus.lake.duckdb_store import connect


def test_utc_and_one_thread() -> None:
    connection = connect()
    try:
        assert connection.execute("SELECT current_setting('TimeZone')").fetchone() == ("UTC",)
        assert connection.execute("SELECT current_setting('threads')").fetchone() == (1,)
    finally:
        connection.close()
