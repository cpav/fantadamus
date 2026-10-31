"""mvp-collect acceptance tests on collected facts (R4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability import gold
from fantadamus.domains.availability.silver import LINEUP_VIEWS, OFFICIAL_LINEUPS, OUTLET_VIEWS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import PLAYER_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import outlet_lineup, page, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)


async def test_at4_four_outlets_disputed(tmp_path: Path) -> None:
    """AT-4: outlets at 90%, 90%, 55% and 90% give a p_start of 0.8125, disputed (spread 0.35)."""
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await send(client, "submit_player_season", page("player_season"), READ)
        for outlet, percent in (("Uno", 90), ("Due", 90), ("Tre", 55), ("Quattro", 90)):
            await send(client, "submit_outlet_lineup", outlet_lineup(outlet, Alfa_Nove=percent), READ)
    players = known_players(read_silver(store, PLAYER_SEASONS), READ)
    nove = gold.availability(
        players[0],
        home="alfa",
        away="beta",
        views=read_silver(store, LINEUP_VIEWS),
        outlet_views=read_silver(store, OUTLET_VIEWS),
        officials=read_silver(store, OFFICIAL_LINEUPS),
        players=players,
        as_of=READ,
    )
    assert nove is not None
    assert len(nove.outlets) == 4
    assert {view.status for view in nove.outlets} == {"percentage"}
    assert nove.p_start == pytest.approx(0.8125)
    assert (nove.spread, nove.disputed) == (0.35, True)
