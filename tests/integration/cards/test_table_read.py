"""mvp-cards task 1.1: Fantadamus reads the table page itself, daily, and stores each club's record and last
five results; Claude can still submit the table, with them or without (design C1; R2.4, R6.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import TEAM_SEASONS
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import what_is_due
from fantadamus.web.collector import page_of
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, TABLE_ROUTE, FakeWeb, round_collector, ticking
from tests.collect_pages import TableClub, table_page
from tests.xy_harness import NOW, send, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
TABLE = [
    TableClub("Alfa", won=6, drawn=2, lost=1, goals_for=17, goals_against=8, form="WWDLW"),
    TableClub("Beta", won=5, drawn=3, lost=1, goals_for=18, goals_against=11, form="DWWDW"),
    TableClub("Gamma", won=3, drawn=2, lost=4, goals_for=12, goals_against=12, form="LWDLW"),
    TableClub("Delta", won=1, drawn=2, lost=6, goals_for=9, goals_against=18, form="LDLLW"),
]


def test_the_collector_reads_the_table(tmp_path: Path) -> None:
    store = LakeStore(tmp_path / "lake")
    routes = {
        f"{BASE}/robots.txt": Response(404, {}, b""),
        f"{BASE}{TABLE_ROUTE}": Response(200, HTML, table_page(TABLE).encode()),
    }
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=FakeWeb(routes), hosts=["example.org"], table=True
    )
    assert collector.reads("team_season")
    assert page_of("team_season") == "table"

    first = collector.collect(facts=["team_season"])
    assert [(page.page, page.outcome, page.stored) for page in first.pages] == [
        ("table", "stored", {"team_seasons": 4})
    ]
    rows = read_silver(store, TEAM_SEASONS)
    assert sorted((row.club, row.played, row.wins, row.draws, row.losses, row.form) for row in rows) == [
        ("alfa", 9, 6, 2, 1, "WWDLW"),
        ("beta", 9, 5, 3, 1, "DWWDW"),
        ("delta", 9, 1, 2, 6, "LDLLW"),
        ("gamma", 9, 3, 2, 4, "LWDLW"),
    ]
    again = collector.collect(facts=["team_season"])
    assert [(page.page, page.outcome) for page in again.pages] == [("table", "unchanged")]


def test_switched_off_the_table_is_claudes(tmp_path: Path) -> None:
    """With `table_enabled = false` the page isn't fetched, and the report hands the table to Claude."""
    store = LakeStore(tmp_path / "lake")
    web = FakeWeb({f"{BASE}/robots.txt": Response(404, {}, b"")})
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=web,
        hosts=["example.org"],
        table=True,
        table_enabled=False,
    )
    report = collector.collect(facts=["team_season"])
    assert [(page.page, page.outcome, page.for_claude) for page in report.pages] == [
        ("table", "switched off", ["team_season"])
    ]
    assert web.calls == []


def test_the_table_is_due_daily(tmp_path: Path) -> None:
    """Like the statistics page: the answers' target for the table stays a week, but a read a day keeps it
    from falling a round behind."""
    store = LakeStore(tmp_path / "lake")
    log = CollectLog(tmp_path / "collect")
    routes = {
        f"{BASE}/robots.txt": Response(404, {}, b""),
        f"{BASE}{TABLE_ROUTE}": Response(200, HTML, table_page(TABLE).encode()),
    }
    clock = ticking(NOW)
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb(routes),
        hosts=["example.org"],
        clock=clock,
        table=True,
    )
    assert "team_season" in what_is_due(store, log, NOW)
    log.append(collector.collect(facts=["team_season"]))
    assert "team_season" not in what_is_due(store, log, NOW + dt.timedelta(hours=23))
    assert "team_season" in what_is_due(store, log, NOW + dt.timedelta(hours=25))


async def test_claude_still_submits_it(tmp_path: Path) -> None:
    """When the page can't be read, Claude submits the table from its text, which shows the record but not
    the form's dots: a table with the record, or with neither, is stored."""
    store = LakeStore(tmp_path / "lake")
    plain = {"teams": [{"club": "Alfa", "played": 9, "goals_for": 17, "goals_against": 8}]}
    record = {"teams": [plain["teams"][0] | {"wins": 6, "draws": 2, "losses": 1}]}
    async with tools(store) as client:
        earlier = NOW - dt.timedelta(hours=1)
        assert not (await send(client, "submit_team_season", plain, earlier)).is_error
        assert not (await send(client, "submit_team_season", record, NOW)).is_error
    rows = sorted(read_silver(store, TEAM_SEASONS), key=lambda row: row.captured_at)
    assert [(row.wins, row.draws, row.losses, row.form) for row in rows] == [
        (None, None, None, None),
        (6, 2, 1, None),
    ]
