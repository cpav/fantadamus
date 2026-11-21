"""mvp-fixes AT-4: through the protocol, `collect` accepts every fact the collector reads and reads that
fact's page, the ratings for the round just played (R2.1, R2.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.server import AdvisorServer
from fantadamus.mcp.tools import collect
from fantadamus.web.collector import FACTS, page_of
from fantadamus.web.fetch import Response
from tests.collect_harness import FakeWeb, round_collector, ticking
from tests.xy_harness import NOW, page, send, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
CHAMPIONS = BASE + "/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw"
MORNING = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)  # 12 hours after round 9's last match


async def test_at4_collect_reads_every_fact(tmp_path: Path) -> None:
    store = LakeStore(tmp_path / "lake")
    async with tools(store) as client:  # a round played, for the ratings
        assert not (
            await send(client, "submit_fixtures", page("fixtures"), NOW - dt.timedelta(hours=1))
        ).is_error
    collector = round_collector(
        store,
        BASE,
        tmp_path / "robots",
        transport=FakeWeb({BASE + "/robots.txt": Response(404, {}, b"")}),
        hosts=["example.org"],
        clock=ticking(MORNING),
        statistics=True,
        takers=True,
        table=True,
        other_competitions=[CHAMPIONS],
        unavailable=True,
        ratings=True,
    )
    server = AdvisorServer(name="fantadamus-test")
    collect.register(server, collector, CollectLog(tmp_path / "collect"))
    async with Client(server) as client:
        for fact in FACTS:
            result = await client.call_tool("collect", {"fact": fact})
            assert not result.is_error, (fact, result)
            assert result.structured_content is not None
            assert [found["page"] for found in result.structured_content["pages"]] == [page_of(fact)], fact
