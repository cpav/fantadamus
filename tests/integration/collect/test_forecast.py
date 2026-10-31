"""mvp-collect task 6.2: each player's movement since the user's previous answer or 24 hours earlier, with the
facts that changed, when the answer's facts were last updated, and labelled sources (design C13; R6.1 to
R6.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import NOW, ask, collect, lineup, odds_for, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

YESTERDAY = NOW - dt.timedelta(hours=25)
TABLE_PAGE = "https://www.fantacalcio.it/serie-a/classifica"


async def _lineups_and_odds(client: Client, captured_at: dt.datetime, home_win: float = 2.1) -> None:
    for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
        for outlet in ("Uno", "Due"):
            assert not (
                await send(client, "submit_probable_lineups", lineup(home, away, outlet), captured_at)
            ).is_error
        odds = odds_for(home, away) | {"home_win": home_win}
        assert not (await send(client, "submit_match_odds", odds, captured_at)).is_error


async def test_movement_since_last_answer(tmp_path: Path) -> None:
    """With no previous answer, movement is against 24 hours earlier: here the official lineup came out and
    the odds moved."""
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, NOW - dt.timedelta(hours=30), facts=("season", "fixtures"))
        await _lineups_and_odds(client, YESTERDAY)
        await _lineups_and_odds(client, NOW - dt.timedelta(hours=1), home_win=1.8)
        official = await send(
            client, "submit_official_lineup", page("official_lineup"), NOW - dt.timedelta(minutes=30)
        )
        assert not official.is_error
        answer = await ask(client)
    nove = answer["answer"]["players"][0]
    movement = nove["movement"]
    assert movement["basis"] == "24 hours earlier"
    assert dt.datetime.fromisoformat(movement["since"]) == NOW - dt.timedelta(hours=24)
    assert movement["p_start"] == pytest.approx(0.9)  # two outlets with him starting
    assert nove["value"]["p_start"] == pytest.approx(1.0)  # now the official lineup has him starting
    assert movement["changes"][0] == "official lineup out: starter"
    assert movement["changes"][1].startswith("team xG ")
    assert movement["p_win"] < nove["p_win"]


async def test_updated_and_sources(tmp_path: Path) -> None:
    hosts = ("example.org", "fantacalcio.it")
    async with tools(LakeStore(tmp_path), hosts=hosts) as client:
        await set_classic(client)
        await collect(client, NOW - dt.timedelta(hours=30), facts=("season", "fixtures"))
        table = await send(
            client, "submit_team_season", page("team_season"), NOW - dt.timedelta(hours=3), url=TABLE_PAGE
        )
        assert not table.is_error
        await _lineups_and_odds(client, NOW - dt.timedelta(hours=1))
        answer = await ask(client)
    updated = answer["answer"]["updated"]
    assert dt.datetime.fromisoformat(updated["newest"]) == NOW - dt.timedelta(hours=1)
    assert dt.datetime.fromisoformat(updated["oldest"]) == NOW - dt.timedelta(hours=30)
    labels = {source["source_url"]: source["label"] for source in answer["answer"]["players"][0]["sources"]}
    assert labels[TABLE_PAGE] == "Fantacalcio.it, table"
    assert labels["https://example.org/page"] == "example.org"
