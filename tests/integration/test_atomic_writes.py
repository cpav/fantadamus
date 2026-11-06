"""Several writers at once, as when two servers and a schedule collect together: found by the code review."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fantadamus.core.files import temporary_beside
from fantadamus.lake.duckdb_store import LakeStore, Table

_TABLE = Table("numbers", "CREATE TEMP TABLE numbers (value INTEGER)", "INSERT INTO numbers VALUES (?)")


def test_writers_never_share_a_temporary_file(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rows = [(number,) for number in range(5_000)]

    def write(_: int) -> None:
        store.write_table("silver", _TABLE, rows)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(write, range(40)))
    assert len(store.read_table("silver", "numbers")) == 5_000
    assert [path.name for path in (tmp_path / "silver").iterdir()] == ["numbers.parquet"]


def test_a_temporary_file_is_hidden_beside_its_target_and_unique(tmp_path: Path) -> None:
    target = tmp_path / "rules.json"
    one, other = temporary_beside(target), temporary_beside(target)
    assert one != other
    assert one.parent == tmp_path
    assert one.name.startswith(".rules.json.")
    assert one.suffix == ".tmp"
