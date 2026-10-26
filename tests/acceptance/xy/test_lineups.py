"""AT-5 and AT-6: an official lineup overrides the outlets; two outlets that disagree are disputed
(R3.2, R3.3, R4.2)."""

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

READ = dt.datetime(2026, 10, 31, 9, 0, tzinfo=dt.UTC)
OFFICIAL = dt.datetime(2026, 10, 31, 13, 0, tzinfo=dt.UTC)


def _nove(store: LakeStore, as_of: dt.datetime) -> Availability:
    players = known_players(read_silver(store, PLAYER_SEASONS), as_of)
    found = gold.availability(
        players[0],
        home="alfa",
        away="beta",
        views=read_silver(store, LINEUP_VIEWS),
        officials=read_silver(store, OFFICIAL_LINEUPS),
        players=players,
        as_of=as_of,
    )
    assert found is not None
    return found


async def test_at5_official_lineup_overrides(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    official = page("official_lineup")
    official["home_team"]["starters"] = [
        name for name in official["home_team"]["starters"] if name != "Alfa Nove"
    ]
    official["home_team"]["starters"].append("Alfa Dodici")
    official["home_team"]["bench"] = ["Alfa Nove"]
    async with tools(store) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        for outlet, status in (("Uno", "starter"), ("Due", "ballottaggio"), ("Tre", "bench")):
            await send(client, "submit_probable_lineups", probable(outlet, home_team=alfa_team(status)), READ)
        await send(client, "submit_official_lineup", official, OFFICIAL)

    outlets = _nove(store, READ)
    assert [view.p_start for view in outlets.outlets] == [0.5, 0.05, 0.9]  # Due, Tre, Uno
    assert outlets.disputed
    settled = _nove(store, OFFICIAL)
    assert settled.official is not None
    assert (settled.official.status, settled.p_start, settled.p_cameo, settled.disputed) == (
        "bench",
        0,
        0.5,
        False,
    )
    assert settled.official.source.captured_at == OFFICIAL


async def test_at6_two_outlets_disputed(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        await send(client, "submit_probable_lineups", probable("Uno", home_team=alfa_team("starter")), READ)
        await send(
            client, "submit_probable_lineups", probable("Due", home_team=alfa_team("ballottaggio")), READ
        )
    nove = _nove(store, READ)
    assert nove.p_start == pytest.approx(0.70)
    assert nove.spread == pytest.approx(0.40)
    assert nove.disputed
    assert nove.p_cameo == pytest.approx(0.15)
