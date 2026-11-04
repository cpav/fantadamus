"""mvp-roles AT-7 to AT-9: two roles get two outlooks and no verdict; two keepers of one club cover each
other; one player's outlook in one call (R3.6, R4.2, R5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.core.clock import fixed_clock
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.roles_data import ROLE_PLAYERS, squad_stats
from tests.xy_harness import NOW, TAKERS, TEAM_TABLE, ask, collect, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = NOW - dt.timedelta(hours=1)


async def _filled(client: Client) -> None:
    await set_classic(client)
    await collect(client, READ)
    for player in ROLE_PLAYERS:
        assert not (await send(client, "submit_player_season", player, READ)).is_error


async def test_at7_two_roles_two_outlooks(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await _filled(client)
        result = await ask(client, "Alfa Due", "Gamma Sei")
    assert result["status"] == "outlooks", result
    assert "formation call" in result["message"]
    answer = result["answer"]
    assert (answer["verdict"], answer["flip"]) == (None, None)
    assert [part["name"] for part in answer["players"]] == ["Alfa Due", "Gamma Sei"]
    assert all(part["movement"] is not None for part in answer["players"])
    [logged] = DecisionLog(store.root / "decisions").read()
    assert (logged.kind, logged.first, logged.label) == ("outlooks", None, None)
    assert len(logged.players) == 2


async def test_at8_same_club_keepers(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await _filled(client)
        result = await ask(client, "Alfa Dodici", "Alfa Uno")
    assert result["status"] == "answer", result
    verdict = result["answer"]["verdict"]
    assert (verdict["first"], verdict["second"], verdict["label"]) == ("Alfa Uno", "Alfa Dodici", "covered")
    assert "plays exactly when" in result["message"]
    assert "Margin" not in result["message"]


async def test_at9_outlook_in_one_call(tmp_path: Path) -> None:
    """AT-9: from a lake with the league rules, the table and the takers, `player_outlook` answers in one
    call: the collector reads the pages, and the answer has its sources, update times and movement (R5)."""
    routes = {
        "/robots.txt": (404, {}, b""),
        ROUND_ROUTE: (200, HTML, fco_round_page(FcoMatch("Alfa", "Beta")).encode()),
        STATS_ROUTE: (200, HTML, stats_page(squad_stats()).encode()),
    }
    store = LakeStore(tmp_path / "lake")
    log = CollectLog(tmp_path / "collect")
    with local_site(routes) as site:
        collector = round_collector(store, site.base_url, tmp_path, statistics=True, clock=fixed_clock(NOW))
        async with tools(store, collector=collector, collect_log=log) as client:
            await set_classic(client)
            for tool, payload in (("submit_team_season", TEAM_TABLE), ("submit_penalty_takers", TAKERS)):
                assert not (await send(client, tool, payload, READ)).is_error
            result = await client.call_tool("player_outlook", {"player": "Alfa Due"})
    assert not result.is_error, result
    content = result.structured_content
    assert content is not None
    assert content["status"] == "outlook", content
    answer = content["answer"]
    [part] = answer["players"]
    assert part["value"]["p_start"] == pytest.approx(0.9125)
    urls = {source["source_url"] for source in part["sources"]}
    assert {site.base_url + ROUND_ROUTE, site.base_url + STATS_ROUTE} <= urls
    assert answer["updated"]["newest"]
    assert part["movement"]["basis"] == "24 hours earlier"
    assert len(DecisionLog(store.root / "decisions").read()) == 1
    assert [page.page for run in log.runs() for page in run.pages] == ["round", "statistics"]
