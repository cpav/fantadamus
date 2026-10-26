"""AT-4, AT-8, AT-9 and AT-10: `compare_players` end to end through the MCP tools (R7, R10, R11, R12, R14)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import NOW, ask, collect, error_text, lineup, odds_for, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = NOW - dt.timedelta(hours=2)
LATER = NOW - dt.timedelta(hours=1)


async def test_at4_scripted_collection(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        first = await ask(client)
        assert first["status"] == "refresh"
        assert {item["fact"] for item in first["refresh"]} == {
            "player_season",
            "fixtures",
            "team_season",
            "penalty_takers",
        }
        await collect(client, READ, facts=("season", "fixtures"))
        second = await ask(client)
        assert second["status"] == "refresh"
        assert {item["fact"] for item in second["refresh"]} == {"probable_lineups", "match_odds"}
        await collect(client, READ)
        third = await ask(client)
    assert third["status"] == "answer", third
    answer = third["answer"]
    assert answer["verdict"]["first"] == "Alfa Nove"
    assert answer["message"].startswith("Start Alfa Nove, put Gamma Nove first on the bench.")
    alfa = answer["players"][0]
    assert [view["p_start"] for view in alfa["outlets"]] == [0.9, 0.9]
    assert alfa["team_xg_from_odds"]
    assert alfa["sources"]
    assert all(source["captured_at"] == READ.isoformat().replace("+00:00", "Z") for source in alfa["sources"])
    assert {source["source_url"] for source in alfa["sources"]} == {"https://example.org/page"}


async def test_at8_earlier_as_of_ignores_later_facts(tmp_path: Path) -> None:
    benched = lineup("Alfa", "Beta", "Uno")
    benched["home_team"]["starters"].remove("Alfa Nove")
    benched["home_team"]["starters"].append("Alfa Dodici")
    benched["home_team"]["bench"] = ["Alfa Tredici"]
    benched["home_team"]["unavailable"].append("Alfa Nove")
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ)
        await send(client, "submit_probable_lineups", benched, LATER)
        before = await ask(client, as_of=(LATER - dt.timedelta(minutes=1)).isoformat())
        after = await ask(client, as_of=LATER.isoformat())
    assert before["answer"]["players"][0]["value"]["p_start"] == pytest.approx(0.9)
    assert after["answer"]["players"][0]["value"]["p_start"] == pytest.approx(0.45)
    assert after["answer"]["players"][0]["value"]["p_cameo"] == 0


async def test_at9_one_log_entry_per_answer(tmp_path: Path) -> None:
    log = DecisionLog(tmp_path / "decisions")
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ)
        await ask(client)
        [path] = sorted((tmp_path / "decisions").glob("*.jsonl"))
        first_line = path.read_text(encoding="utf-8")
        await ask(client, "Gamma Nove", "Alfa Nove")
    assert path.name == "2026-10.jsonl"
    assert path.read_text(encoding="utf-8").startswith(first_line)
    entries = log.read()
    assert len(entries) == 2
    assert entries[0].first == "Alfa Nove"
    assert {player.name for player in entries[0].players} == {"Alfa Nove", "Gamma Nove"}
    assert entries[0].rules.user == "user-1"
    assert entries[0].content_hashes
    assert all(0 <= player.p_start <= 1 and 0 <= player.p_scores <= 1 for player in entries[1].players)


async def test_at10_league_rules(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await collect(client, READ)
        setup = await ask(client)
        assert setup["status"] == "setup"
        assert setup["setup"]["tool"] == "set_league_rules"
        await set_classic(client)
        classic = await ask(client)
        await set_classic(client, goal=4.5)
        richer = await ask(client)
        rejected = await client.call_tool("set_league_rules", {"rules": {"goal": 12}})
    assert "goal" in error_text(rejected)
    assert classic["answer"]["rules"]["rules"]["goal"] == 3
    assert richer["answer"]["rules"]["rules"]["goal"] == 4.5
    assert (
        richer["answer"]["players"][0]["value"]["e_start"]
        > classic["answer"]["players"][0]["value"]["e_start"]
    )


async def test_at7_bad_submissions_rejected(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    ten = lineup("Alfa", "Beta", "Uno")
    ten["home_team"]["starters"].pop()
    split = lineup("Alfa", "Beta", "Uno")
    split["home_team"]["ballottaggi"] = [
        {"players": [{"name": "Alfa Nove", "percent": 50}, {"name": "Alfa Dodici", "percent": 30}]}
    ]
    async with tools(store) as client:
        off_list = await send(
            client,
            "submit_probable_lineups",
            lineup("Alfa", "Beta", "Uno"),
            READ,
            url="https://elsewhere.example/x",
        )
        assert "elsewhere.example is not on the allowlist" in error_text(off_list)
        assert "needs 11 starters, got 10" in error_text(
            await send(client, "submit_probable_lineups", ten, READ)
        )
        assert "shares sum to 80%" in error_text(await send(client, "submit_probable_lineups", split, READ))
        wide = odds_for("Alfa", "Beta") | {"home_win": 1.6, "draw": 3.2, "away_win": 3.2}
        assert "1X2 margin 25.0% is outside 0% to 15%" in error_text(
            await send(client, "submit_match_odds", wide, READ)
        )
    assert store.bronze_files("probable_lineups") == []
    assert store.bronze_files("match_odds") == []
