"""Task 2.2: profiles, the league table and penalty takers, with their as-of reads (R1.1, R6, R7.1, R7.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season import gold
from fantadamus.domains.season.silver import PENALTY_TAKERS, PLAYER_SEASONS, TEAM_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import error_text, page, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 10, 27, 9, 0, tzinfo=dt.UTC)


async def test_profile_creates_player_and_season(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        result = await send(client, "submit_player_season", page("player_season"), READ)
        assert not result.is_error, result
        unknown = page("player_season") | {"club": "Omega"}
        assert "unknown club 'Omega'" in error_text(await send(client, "submit_player_season", unknown, READ))
    rows = read_silver(store, PLAYER_SEASONS)
    assert len(rows) == 1
    assert gold.known_players(rows, as_of=READ) == [
        KnownPlayer(player_id=9001, name="Alfa Nove", club="alfa")
    ]
    form = gold.player_form(rows, 9001, as_of=READ)
    assert form is not None
    assert (form.role, form.mantra_role, form.appearances, form.average_rating, form.goals) == (
        "A",
        "Pc",
        8,
        6.4,
        5,
    )
    assert form.source.captured_at == READ
    assert gold.player_form(rows, 9001, as_of=READ - dt.timedelta(minutes=1)) is None
    assert gold.player_form(rows, 1234, as_of=READ) is None


async def test_team_table_and_penalty_takers(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    changed = page("penalty_takers")
    changed["clubs"][0]["takers"] = ["Alfa Dieci", "Alfa Nove"]
    async with tools(store) as client:
        assert not (await send(client, "submit_team_season", page("team_season"), READ)).is_error
        assert not (await send(client, "submit_penalty_takers", page("penalty_takers"), READ)).is_error
        assert not (await send(client, "submit_penalty_takers", changed, LATER)).is_error
    table = gold.team_season(read_silver(store, TEAM_SEASONS), "alfa", as_of=READ)
    assert table is not None
    assert (table.played, table.goals_for, table.goals_against) == (8, 14, 9)
    takers = read_silver(store, PENALTY_TAKERS)
    first = gold.penalty_order(takers, "alfa", as_of=READ)
    assert first is not None
    assert first.takers == ["Alfa Nove", "Alfa Dieci"]
    later = gold.penalty_order(takers, "alfa", as_of=LATER)
    assert later is not None
    assert later.takers == ["Alfa Dieci", "Alfa Nove"]
    assert later.source.captured_at == LATER
    assert gold.penalty_order(takers, "gamma", as_of=LATER) is None


async def test_resubmission_keeps_history(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    updated = page("player_season") | {"appearances": 9, "rated_appearances": 9, "goals": 6, "club": "Beta"}
    async with tools(store) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        await send(client, "submit_player_season", updated, LATER)
    rows = read_silver(store, PLAYER_SEASONS)
    assert len(rows) == 2  # nothing overwritten
    before, after = gold.player_form(rows, 9001, as_of=READ), gold.player_form(rows, 9001, as_of=LATER)
    assert before is not None
    assert after is not None
    assert (before.goals, before.club, after.goals, after.club) == (5, "alfa", 6, "beta")
    assert gold.known_players(rows, as_of=LATER)[0].club == "beta"  # a transfer follows the latest profile
