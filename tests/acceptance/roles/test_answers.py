"""mvp-roles AT-7 and AT-8: two roles get two outlooks and no verdict; two keepers of one club cover each
other (R3.6, R4.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.roles_data import ROLE_PLAYERS
from tests.xy_harness import NOW, ask, collect, send, set_classic, tools

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
