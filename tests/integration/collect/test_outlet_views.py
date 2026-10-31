"""mvp-collect task 1.2: outlets' percentages reach silver, and a page's chance of 3+ goals feeds the fit
(design C4, C5; R4.1, R4.2, R8.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability.silver import OUTLET_VIEWS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.odds import gold
from fantadamus.domains.odds.silver import ODDS
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import URL, outlet_lineup, page, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)


async def test_outlet_lineup_bronze_to_silver(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        result = await send(client, "submit_outlet_lineup", outlet_lineup("Uno", Alfa_Nove=55), READ)
        assert not result.is_error, result
    rows = read_silver(store, OUTLET_VIEWS)
    assert len(rows) == 28  # 13 players and 1 unavailable per team
    nove = next(row for row in rows if row.name == "Alfa Nove")
    assert (nove.outlet, nove.club, nove.role, nove.percent, nove.unavailable) == (
        "Uno",
        "alfa",
        "A",
        55,
        False,
    )
    out = next(row for row in rows if row.name == "Beta Quattordici")
    assert (out.club, out.percent, out.unavailable) == ("beta", None, True)
    assert {row.source_url for row in rows} == {URL}


async def test_percent_over_feeds_the_fit(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    page_percent = page("match_odds") | {"over_2_5": None, "under_2_5": None, "over_2_5_percent": 53}
    async with tools(store) as client:
        assert not (await send(client, "submit_match_odds", page_percent, READ)).is_error
    [row] = read_silver(store, ODDS)
    assert row.p_over == pytest.approx(0.53)
    xg = gold.team_xg([row], [], home="alfa", away="beta", as_of=READ)
    assert xg is not None
    assert xg.totals
