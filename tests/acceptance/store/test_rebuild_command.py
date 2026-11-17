"""AT-4 of mvp-store: `fantadamus rebuild` rebuilds every table, or one, and sends no request; a lake in the
layout it had before the slice answers after it, its bronze untouched (R2.4, R2.5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.cli import __main__ as cli
from fantadamus.contracts.xy.fixtures import OtherFixturesPayload
from fantadamus.domains.fixtures.silver import FIXTURES, OTHER_FIXTURES
from fantadamus.domains.tables import DOMAINS
from fantadamus.lake.duckdb_store import LakeStore
from tests.lineup_harness import a_round
from tests.store_lake import (
    Told,
    bronze_bytes,
    fixtures,
    store_one,
    table,
    to_earlier_layout,
    told_by_bronze,
)
from tests.xy_harness import CLUBS, NOW

OCTOBER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)
EARLY_NOVEMBER = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATE_NOVEMBER = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)
OTHER = OtherFixturesPayload.model_validate(
    {
        "competition": "Champions League",
        "matches": [{"home": "Alfa", "away": "Omega", "kickoff_at": "2026-11-04T21:00:00+01:00"}],
    }
)


@pytest.fixture
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LakeStore:
    """Three reads of the calendar over two months and one of another competition, with the command line
    reading the four invented clubs."""
    monkeypatch.setattr(cli, "_clubs", lambda: CLUBS)
    store = LakeStore(tmp_path / "lake")
    for round, when in ((9, OCTOBER), (10, EARLY_NOVEMBER), (11, LATE_NOVEMBER)):
        store_one(store, fixtures(round), when)
    store_one(store, OTHER, EARLY_NOVEMBER, domain=OTHER_FIXTURES)
    return store


def _rebuild(store: LakeStore, *options: str) -> int:
    return cli.main(["rebuild", "--lake", str(store.root), *options])


def test_at4_every_table_or_one(lake: LakeStore, capsys: pytest.CaptureFixture[str]) -> None:
    right = {domain.source: told_by_bronze(lake, domain).table() for domain in (FIXTURES, OTHER_FIXTURES)}
    kept = bronze_bytes(lake)
    for domain, month in ((FIXTURES, "2026-10"), (OTHER_FIXTURES, "2026-11")):
        written = lake.description(domain.table)
        assert written is not None
        broken = lake.root / "silver" / domain.table.name / written.files[month]
        if domain is FIXTURES:
            broken.unlink()  # a month removed by hand
        else:
            broken.write_bytes(b"not a Parquet file")
    assert [row["round"] for row in lake.read_rows(FIXTURES.table)] == [10, 10, 11, 11]
    assert _rebuild(lake, "--table", "fixtures") == 0
    assert capsys.readouterr().out.splitlines() == ["fixtures: 3 bronze records, 6 rows, 2 months"]
    assert table(lake, FIXTURES) == right["fixtures"]
    assert _rebuild(lake) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(DOMAINS) == 13
    assert "fixtures: 3 bronze records, 6 rows, 2 months" in lines
    assert "other_fixtures: 1 bronze record, 1 row, 1 month" in lines
    assert "odds: 0 bronze records, 0 rows, 0 months" in lines
    for domain in (FIXTURES, OTHER_FIXTURES):
        assert table(lake, domain) == right[domain.source]
    assert bronze_bytes(lake) == kept
    with pytest.raises(SystemExit):
        _rebuild(lake, "--table", "nonsense")


@pytest.mark.disable_socket
def test_at4_no_request_is_sent(lake: LakeStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """It builds no fetcher and no collector, so it can't read a page; and no socket may open."""

    def refuse(*args: object, **options: object) -> None:
        raise AssertionError("rebuilding reads no page")

    for name in ("Fetcher", "Collector", "load_collector", "_collector"):
        monkeypatch.setattr(cli, name, refuse)
    assert _rebuild(lake) == 0
    assert table(lake) == told_by_bronze(lake).table()


@pytest.mark.anyio
async def test_at4_a_lake_in_the_earlier_layout_answers_after_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_clubs", lambda: CLUBS)
    async with a_round(tmp_path) as here:
        await here.ask()  # reads the round's pages and stores them
        asked = {"as_of": NOW.isoformat()}
        before = await here.ask(**asked)
        silver = here.store.root / "silver"
        stored = [domain for domain in DOMAINS if here.store.description(domain.table) is not None]
        for domain in stored:
            to_earlier_layout(here.store, domain)  # as it was stored before the slice
        assert sorted(path.name for path in silver.iterdir()) == sorted(
            f"{domain.table.name}.parquet" for domain in stored
        )
        kept = bronze_bytes(here.store)
        assert await here.ask(**asked) == before  # read as it is
        assert _rebuild(here.store) == 0
        assert sorted(path.name for path in silver.iterdir()) == sorted(
            domain.table.name for domain in DOMAINS
        )
        assert all((silver / domain.table.name / "_table.json").is_file() for domain in DOMAINS)
        assert await here.ask(**asked) == before  # and after it
        assert bronze_bytes(here.store) == kept
    assert len(stored) >= 6


def test_told_is_what_the_fixture_stored(lake: LakeStore) -> None:
    """The oracle the tests above compare with says what was stored here."""
    rows, description = Told.table(told_by_bronze(lake))
    assert [row["round"] for row in rows] == [9, 9, 10, 10, 11, 11]
    assert description is not None
    assert description["last_bronze"] == lake.bronze_files("fixtures")[-1].stem
    assert description["months"] == ["2026-10", "2026-11"]
