"""AT-1 of mvp-store: after every store, through the tools, each table holds exactly the rows a rebuild
gives, and no bronze file has changed (R1.1, R1.3). Its property is P1, in
`tests/integration/store/test_append.py`."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.availability.silver import LINEUP_VIEWS
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.odds.silver import ODDS
from fantadamus.lake.duckdb_store import LakeStore
from tests.store_lake import bronze_bytes, rebuilt_elsewhere, table
from tests.xy_harness import SetClock, alfa_team, odds_for, page, probable, send, tools

pytestmark = pytest.mark.anyio


def at(month: int, day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=dt.UTC)


READS: list[tuple[dt.datetime, str, dict[str, Any]]] = [
    (at(10, 30, 10), "submit_fixtures", page("fixtures")),
    (at(10, 30, 10, 5), "submit_match_odds", odds_for("Alfa", "Beta")),
    (at(10, 30, 18), "submit_probable_lineups", probable("Outlet One")),
    (at(10, 31, 23, 30), "submit_probable_lineups", probable("Outlet Two")),
    (at(11, 1, 0, 30), "submit_probable_lineups", probable("Outlet One", home_team=alfa_team("bench"))),
    (at(11, 1, 9), "submit_match_odds", odds_for("Gamma", "Delta")),
    (at(11, 1, 9), "submit_fixtures", page("fixtures")),  # the same content, read again
    (at(10, 31, 12), "submit_match_odds", odds_for("Alfa", "Beta")),  # read earlier, arriving late
]


async def test_at1_the_table_a_rebuild_gives(tmp_path: Path) -> None:
    store, clock = LakeStore(tmp_path / "lake"), SetClock(READS[0][0])
    kept: dict[str, bytes] = {}
    async with tools(store, clock=clock) as client:
        for index, (read_at, tool, payload) in enumerate(READS):
            clock.now = max(clock.now, read_at) + dt.timedelta(minutes=1)  # it arrives a minute later
            result = await send(client, tool, payload, read_at)
            assert not result.is_error, result
            now = bronze_bytes(store)
            assert {name: now[name] for name in kept} == kept  # no bronze file has changed
            assert len(now) == index + 1
            kept = now
            for domain in (FIXTURES, ODDS, LINEUP_VIEWS):
                if store.bronze_files(domain.source):  # a table exists from its first store
                    assert table(store, domain) == rebuilt_elsewhere(store, domain), (index, domain.source)
    for domain in (FIXTURES, ODDS, LINEUP_VIEWS):
        written = store.description(domain.table)
        assert written is not None
        assert list(written.files) == ["2026-10", "2026-11"]
        folder = store.root / "silver" / domain.table.name
        assert sorted(path.name for path in folder.iterdir()) == sorted(
            [*written.files.values(), "_table.json"]
        )
