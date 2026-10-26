"""Task 4.1: `submit_match_odds` and silver `odds`, de-margined per page (R5.1, R7.1, R7.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.odds import gold
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.season.silver import TEAM_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import URL, error_text, page, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)
OTHER = "https://example.org/other-preview"


async def test_submit_odds_de_margined(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        assert not (await send(client, "submit_match_odds", page("match_odds"), READ)).is_error
        wide = page("match_odds") | {"home_win": 1.6, "draw": 2.9, "away_win": 2.9}
        assert "1X2 margin 31.5%" in error_text(await send(client, "submit_match_odds", wide, READ))
    [row] = read_silver(store, ODDS)
    total = 1 / 2.10 + 1 / 3.30 + 1 / 3.60
    assert (row.home, row.away, row.bookmaker) == ("alfa", "beta", "Banco Esempio")
    assert row.p_home == pytest.approx((1 / 2.10) / total)
    assert row.p_home + row.p_draw + row.p_away == pytest.approx(1)
    assert row.p_over == pytest.approx((1 / 1.95) / (1 / 1.95 + 1 / 1.85))
    assert row.p_btts == pytest.approx((1 / 1.80) / (1 / 1.80 + 1 / 1.95))


async def test_pages_kept_side_by_side(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    other = page("match_odds") | {"goal": None, "no_goal": None, "home_win": 2.0, "away_win": 3.8}
    async with tools(store) as client:
        await send(client, "submit_match_odds", page("match_odds"), READ)
        await send(client, "submit_match_odds", other, READ, url=OTHER)
    rows = read_silver(store, ODDS)
    assert {row.source_url for row in rows} == {URL, OTHER}
    xg = gold.team_xg(rows, read_silver(store, TEAM_SEASONS), home="alfa", away="beta", as_of=READ)
    assert xg is not None
    assert xg.from_odds
    assert {source.source_url for source in xg.sources} == {URL, OTHER}
    assert xg.home_xg > xg.away_xg
    assert xg.p_home_win + xg.p_draw + xg.p_away_win == pytest.approx(1)
    assert gold.team_xg(rows, [], home="alfa", away="beta", as_of=READ - dt.timedelta(seconds=1)) is None
