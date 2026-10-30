"""Task 7.2: `compare_players`, from the refresh plan to the answer (design C10; R1.3, R1.4, R2.2, R2.3, R10,
R11, R12.3, R12.4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import NOW, ask, collect, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = NOW - dt.timedelta(hours=1)


async def test_refresh_plan_order(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ, facts=("fixtures",))
        await send(client, "submit_player_season", page("player_season"), READ)
        plan = await ask(client, "Alfa Nove", "Delta Sette")
        assert plan["status"] == "refresh"
        assert [(item["fact"], item["about"]) for item in plan["refresh"]] == [
            ("probable_lineups", "Alfa v Beta"),
            ("match_odds", "Alfa v Beta"),
            ("player_season", "Delta Sette's profile"),
            ("team_season", "the Serie A table"),
            ("penalty_takers", "the penalty takers"),
        ]  # everything already known to be needed, so collection takes few round trips
        assert plan["refresh"][2]["search"][0] == "Delta Sette site:fantacalcio.it/serie-a/squadre"

        await send(
            client,
            "submit_player_season",
            page("player_season") | {"player_id": 9004, "name": "Delta Sette", "club": "Delta"},
            READ,
        )
        plan = await ask(client, "Alfa Nove", "Delta Sette")
    items = [(item["fact"], item["why"], item["about"]) for item in plan["refresh"]]
    assert items == [
        ("probable_lineups", "missing", "Alfa v Beta"),
        ("probable_lineups", "missing", "Gamma v Delta"),
        ("match_odds", "missing", "Alfa v Beta"),
        ("match_odds", "missing", "Gamma v Delta"),
        ("team_season", "missing", "the Serie A table"),
        ("penalty_takers", "missing", "the penalty takers"),
    ]
    odds = plan["refresh"][2]
    assert odds["submit_tool"] == "submit_match_odds"
    assert odds["search"][0] == "Alfa Beta quote over under goal no goal site:livetipsportal.com"


async def test_forwards_only(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ)
        await send(
            client,
            "submit_player_season",
            page("player_season")
            | {"player_id": 9002, "name": "Beta Sei", "club": "Beta", "role": "C", "mantra_role": "M"},
            READ,
        )
        result = await ask(client, "Alfa Nove", "Beta Sei")
    assert result["status"] == "forwards only"
    assert "Beta Sei" in result["message"]


async def test_no_fixture_means_not_playing(tmp_path: Path) -> None:
    only_alfa = page("fixtures")
    only_alfa["matches"] = only_alfa["matches"][:1]
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        await send(client, "submit_fixtures", only_alfa, READ)
        for tool, payload in (("submit_probable_lineups", {"outlet": "Uno"}), ("submit_match_odds", {})):
            base = page("probable_lineup") if tool == "submit_probable_lineups" else page("match_odds")
            await send(client, tool, base | payload, READ)
        result = await ask(client)
    assert result["status"] == "answer", result
    answer = result["answer"]
    assert answer["verdict"]["first"] == "Alfa Nove"
    gamma = answer["players"][1]
    assert gamma["fixture"] is None
    assert gamma["value"]["p_start"] == 0
    assert any("no match in round 9" in note for note in gamma["notes"])


async def test_first_match_to_check(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ)
        result = await ask(client)
    answer = result["answer"]
    assert answer["round"] == 9
    assert answer["deadline"] == "2026-10-31T15:00:00+01:00"  # Europe/Rome
    assert answer["players"][0]["kickoff"] == "2026-10-31T15:00:00+01:00"
    assert len(answer["check_before_deadline"]) == 1
    assert "Alfa Nove" in answer["check_before_deadline"][0]
    assert "Gamma Nove" not in answer["check_before_deadline"][0]
    assert answer["rules"]["user"] == "user-1"


async def test_player_who_cannot_play_is_not_benched(tmp_path: Path) -> None:
    only_alfa = page("fixtures")
    only_alfa["matches"] = only_alfa["matches"][:1]
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        await send(client, "submit_fixtures", only_alfa, READ)
        await send(client, "submit_probable_lineups", page("probable_lineup"), READ)
        await send(client, "submit_match_odds", page("match_odds"), READ)
        result = await ask(client, "Gamma Nove", "Alfa Nove")
    message = result["answer"]["message"]
    assert message.startswith(
        "Start Alfa Nove; Gamma Nove won't play, so put a fit forward first on the bench."
    )
    assert "put Gamma Nove first on the bench" not in message
    assert result["answer"]["verdict"]["second_plays"] is False
