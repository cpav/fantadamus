"""mvp-roles task 6.1: `player_outlook`, one player's forecast, with the same steps as `compare_players`
before it (design C10; R5.1, R5.2, R5.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.roles_data import ROLE_PLAYERS
from tests.xy_harness import NOW, SetClock, ask, collect, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = NOW - dt.timedelta(hours=1)


async def _outlook(client: Client, player: str, **options: object) -> dict[str, Any]:
    result = await client.call_tool("player_outlook", {"player": player, **options})
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


async def _filled(client: Client) -> None:
    await set_classic(client)
    await collect(client, READ)
    for player in ROLE_PLAYERS:
        assert not (await send(client, "submit_player_season", player, READ)).is_error


async def test_outlook_statuses(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        assert (await _outlook(client, "Alfa Uno"))["status"] == "setup"
        await set_classic(client)
        missing = await _outlook(client, "Alfa Uno")
        assert missing["status"] == "refresh"
        assert "Alfa Uno's season figures" in [item["about"] for item in missing["refresh"]]
        await collect(client, READ)
        for player in ROLE_PLAYERS:
            assert not (await send(client, "submit_player_season", player, READ)).is_error
        choose = await _outlook(client, "Alfa")
        assert choose["status"] == "choose"
        assert "Alfa Uno" in [player["name"] for player in choose["candidates"]["Alfa"]]
        keeper = await _outlook(client, "Alfa Uno")
        striker = await _outlook(client, "Alfa Nove")
        out = await _outlook(client, "Alfa Quattordici")
    assert keeper["status"] == "outlook"
    answer = keeper["answer"]
    assert (answer["verdict"], answer["flip"]) == (None, None)
    [part] = answer["players"]
    assert part["name"] == "Alfa Uno"
    assert part["value"]["kind"] == "keeper"
    assert part["value"]["p_clean_sheet"] > 0
    assert part["outlets"]
    assert part["sources"]
    assert answer["rules"]["user"] == "user-1"
    assert answer["updated"]["newest"]
    assert "Alfa Uno (keeper)" in keeper["message"]
    assert "to start" in keeper["message"]
    [nove] = striker["answer"]["players"]
    assert nove["value"]["kind"] == "outfield"
    assert nove["penalty_taker"]
    assert "won't play" in out["message"]


async def test_outlook_logged(tmp_path: Path) -> None:
    """Each outlook goes in the decision log, and movement counts from any answer that included him."""
    clock = SetClock(NOW)
    store = LakeStore(tmp_path)
    async with tools(store, clock=clock) as client:
        await _filled(client)
        first = await _outlook(client, "Alfa Uno")
        clock.now += dt.timedelta(minutes=10)
        compared = await ask(client, "Alfa Uno", "Gamma Uno")
        clock.now += dt.timedelta(minutes=10)
        second = await _outlook(client, "Alfa Uno")
    assert first["answer"]["players"][0]["movement"]["basis"] == "24 hours earlier"
    assert compared["answer"]["players"][0]["movement"]["since"] == first["answer"]["as_of"]
    assert second["answer"]["players"][0]["movement"]["since"] == compared["answer"]["as_of"]
    outlook, comparison, again = DecisionLog(store.root / "decisions").read()
    assert (outlook.kind, comparison.kind, again.kind) == ("outlook", "compare", "outlook")
    assert [player.name for player in outlook.players] == ["Alfa Uno"]
    assert outlook.players[0].p_clean_sheet is not None
    assert (outlook.first, outlook.margin, outlook.label) == (None, None, None)
