"""Task 3.1: the lineup submit tools and silver, names resolved on read (R3.1, R4.1, R7.1, R7.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability import gold
from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.availability.silver import LINEUP_VIEWS, OFFICIAL_LINEUPS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import PLAYER_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import alfa_team, page, probable, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 10, 30, 12, 0, tzinfo=dt.UTC)


def _availability(store: LakeStore, as_of: dt.datetime) -> Availability | None:
    players = known_players(read_silver(store, PLAYER_SEASONS), as_of)
    nove = next(player for player in players if player.player_id == 9001)
    return gold.availability(
        nove,
        home="alfa",
        away="beta",
        views=read_silver(store, LINEUP_VIEWS),
        officials=read_silver(store, OFFICIAL_LINEUPS),
        players=players,
        as_of=as_of,
    )


async def test_outlets_kept_side_by_side(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store, now=LATER) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        first = await send(client, "submit_probable_lineups", probable("Uno Formazioni"), READ)
        assert not first.is_error, first
        second = probable("Due Formazioni", home_team=alfa_team("ballottaggio"))
        assert not (await send(client, "submit_probable_lineups", second, READ)).is_error
        changed = probable("Uno Formazioni", home_team=alfa_team("bench"))
        assert not (await send(client, "submit_probable_lineups", changed, LATER)).is_error
        assert not (await send(client, "submit_official_lineup", page("official_lineup"), LATER)).is_error

    views = read_silver(store, LINEUP_VIEWS)
    assert {(row.outlet, row.captured_at) for row in views} == {
        ("Uno Formazioni", READ),
        ("Due Formazioni", READ),
        ("Uno Formazioni", LATER),
    }  # every submission kept
    assert {row.club for row in views} == {"alfa", "beta"}
    assert ("alfa", "Alfa Undici", "ballottaggio", 60.0) in {
        (row.club, row.name, row.status, row.share) for row in views
    }
    officials = read_silver(store, OFFICIAL_LINEUPS)
    assert sum(row.status == "starter" for row in officials) == 22

    before = _availability(store, READ)
    assert before is not None
    assert [(view.outlet, view.p_start) for view in before.outlets] == [
        ("Due Formazioni", 0.5),
        ("Uno Formazioni", 0.9),
    ]
    latest = _availability(store, LATER - dt.timedelta(seconds=1))
    assert latest is not None
    assert latest.p_start == pytest.approx(0.7)


async def test_unresolved_name_resolves_when_profile_arrives(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store, now=LATER) as client:
        await send(client, "submit_probable_lineups", probable("Uno Formazioni"), READ)
        assert known_players(read_silver(store, PLAYER_SEASONS), LATER) == []
        assert "Alfa Nove" in {row.name for row in read_silver(store, LINEUP_VIEWS)}  # kept by name
        await send(client, "submit_player_season", page("player_season"), LATER)
    resolved = _availability(store, LATER)
    assert resolved is not None
    assert [(view.status, view.p_start) for view in resolved.outlets] == [("starter", 0.9)]


async def test_ballottaggio_rivals_named(tmp_path: Path) -> None:
    """mvp-x-or-y task 13.1 (R10.8): each outlet's view names the players he's contesting the place with."""
    store = LakeStore(tmp_path)
    async with tools(store, now=LATER) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        await send(
            client, "submit_probable_lineups", probable("Uno", home_team=alfa_team("ballottaggio")), READ
        )
        await send(client, "submit_probable_lineups", probable("Due", home_team=alfa_team("starter")), READ)
    nove = _availability(store, READ)
    assert nove is not None
    assert [(view.outlet, view.status, view.rivals) for view in nove.outlets] == [
        ("Due", "starter", []),
        ("Uno", "ballottaggio", ["Alfa Dodici"]),
    ]
