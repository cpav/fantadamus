"""AT-3 of mvp-store: a run stopped between bronze and silver, two runs at once, and a domain whose rows
changed each end with the table a rebuild gives (R2.1 to R2.3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from scripts.checks._common import run_command

from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain, Source
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.lake.duckdb_store import STORING, LakeStore, Table
from tests.store_lake import bronze_bytes, fixtures, rebuilt_elsewhere, store_one, table
from tests.store_runs import page_of

ROOT = Path(__file__).resolve().parents[3]
OCTOBER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)
EARLY_NOVEMBER = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATE_NOVEMBER = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)
DECEMBER = dt.datetime(2026, 12, 4, 9, 0, tzinfo=dt.UTC)
READS = 20


class StoppedError(Exception):
    """The run stops here."""


def _rounds(store: LakeStore) -> list[object]:
    return [row["round"] for row in store.read_rows(FIXTURES.table)]


def test_at3_a_run_stopped_between_bronze_and_silver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LakeStore(tmp_path)
    store_one(store, fixtures(9), OCTOBER)
    marker = tmp_path / "silver" / "fixtures" / STORING

    def stop(*args: object, **options: object) -> int:
        raise StoppedError

    with monkeypatch.context() as stopped:
        stopped.setattr(LakeStore, "append_rows", stop)
        with pytest.raises(StoppedError):
            store_one(store, fixtures(10), EARLY_NOVEMBER)
    assert len(store.bronze_files("fixtures")) == 2  # bronze has the read
    assert _rounds(store) == [9, 9]  # and silver doesn't
    assert marker.exists()
    kept = bronze_bytes(store)
    store_one(store, fixtures(11), LATE_NOVEMBER)  # the next store finds it out, and rebuilds first
    assert _rounds(store) == [9, 9, 10, 10, 11, 11]
    assert table(store) == rebuilt_elsewhere(store)
    assert not marker.exists()
    assert {name: bronze_bytes(store)[name] for name in kept} == kept


def test_at3_two_runs_at_once_keep_both(tmp_path: Path) -> None:
    """The server and the schedule, each its own process, storing to one lake at the same time."""
    lake, go, names = tmp_path / "lake", tmp_path / "go", ("server", "schedule")

    def run(name: str) -> int:
        command = [sys.executable, "-m", "tests.store_runs", str(lake), name, str(READS), str(go)]
        return run_command(command, cwd=ROOT, timeout=100).returncode

    with ThreadPoolExecutor(2) as pool:
        runs = [pool.submit(run, name) for name in names]
        deadline = time.monotonic() + 60
        while not all((tmp_path / f"{name}.ready").exists() for name in names):
            assert time.monotonic() < deadline, "the two runs never started"
            time.sleep(0.01)
        go.touch()  # both start storing now
        assert [found.result() for found in runs] == [0, 0]
    store = LakeStore(lake)
    assert len(store.bronze_files("fixtures")) == 2 * READS
    rows, description = table(store)
    assert (rows, description) == rebuilt_elsewhere(store)
    for name in names:  # every read of each run is there, whole
        assert len([row for row in rows if row["source_url"] == page_of(name)]) == 2 * READS
    assert not (lake / "silver" / "fixtures" / STORING).exists()


def _shouting(payload: FixturesPayload, clubs: Clubs, source: Source) -> list[FixtureRow]:
    """The same payload as other rows: the home club in capitals."""
    rows = FIXTURES.to_rows(payload, clubs, source)
    return [row.model_copy(update={"home": row.home.upper()}) for row in rows]


class NotedRow(FixtureRow):
    note: str


def _noted(payload: FixturesPayload, clubs: Clubs, source: Source) -> list[NotedRow]:
    return [
        NotedRow(**row.model_dump(), note=f"round {row.round}") for row in _shouting(payload, clubs, source)
    ]


def test_at3_a_domain_whose_rows_changed(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    store_one(store, fixtures(9), OCTOBER)
    store_one(store, fixtures(10), EARLY_NOVEMBER)
    assert {row["home"] for row in store.read_rows(FIXTURES.table)} == {"alfa", "gamma"}
    # The code changes how a payload becomes rows, and the domain says so with its version.
    changed = dataclasses.replace(FIXTURES, to_rows=_shouting, rows_version=FIXTURES.rows_version + 1)
    store_one(store, fixtures(11), LATE_NOVEMBER, domain=changed)
    rows = store.read_rows(changed.table)
    assert [row["round"] for row in rows] == [9, 9, 10, 10, 11, 11]
    assert {row["home"] for row in rows} == {"ALFA", "GAMMA"}  # the earlier reads too
    assert table(store, changed) == rebuilt_elsewhere(store, changed)
    described = store.description(changed.table)
    assert described is not None
    assert described.rows_version == FIXTURES.rows_version + 1
    # Then the table gets another column: the next store finds that out by itself.
    wider = Table("fixtures", FIXTURES.table.create_sql.replace(")", ", note VARCHAR)"))
    noted: Domain[FixturesPayload, NotedRow] = Domain(
        "fixtures", FixturesPayload, NotedRow, _noted, wider, rows_version=changed.rows_version
    )
    assert wider.create_sql.startswith(f"CREATE TEMP TABLE fixtures ({PROVENANCE_COLUMNS}, ")
    store_one(store, fixtures(12), DECEMBER, domain=noted)
    rows = store.read_rows(noted.table)
    assert [row["note"] for row in rows] == [f"round {number}" for number in (9, 9, 10, 10, 11, 11, 12, 12)]
    assert table(store, noted) == rebuilt_elsewhere(store, noted)
