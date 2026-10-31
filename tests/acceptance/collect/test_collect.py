"""mvp-collect acceptance tests on collected facts (R1, R2.4, R3, R4, R8.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.availability import gold
from fantadamus.domains.availability.silver import LINEUP_VIEWS, OFFICIAL_LINEUPS, OUTLET_VIEWS
from fantadamus.domains.facts import Domain, read_silver
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import PLAYER_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.collector import ROUND_FACTS
from tests.collect_harness import HTML, ROUND_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page
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


def _bronze(root: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in sorted(root.rglob("bronze/**/*.parquet"))}


def test_at1_one_collection_stores_everything(tmp_path: Path) -> None:
    """AT-1: one collection from a local server stores the fixtures, four outlets' views, the odds and the
    confirmed official lineups, each with the page's address; a second run stores nothing new."""
    gamma = FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True)
    routes = {
        "/robots.txt": (404, {}, b""),
        ROUND_ROUTE: (200, HTML, fco_round_page(FcoMatch("Alfa", "Beta"), gamma).encode()),
    }
    with local_site(routes) as site:
        store = LakeStore(tmp_path / "lake")
        collector = round_collector(store, site.base_url, tmp_path / "robots")
        [first] = collector.collect().pages
        stored = _bronze(tmp_path / "lake")
        [second] = collector.collect().pages
    assert (first.outcome, first.stored) == (
        "stored",
        {"fixtures": 2, "odds": 2, "outlet_views": 224, "official_lineups": 26},
    )
    domains: tuple[Domain[Any, Any], ...] = (FIXTURES, ODDS, OUTLET_VIEWS, OFFICIAL_LINEUPS)
    for domain in domains:
        assert {row.source_url for row in read_silver(store, domain)} == {site.base_url + ROUND_ROUTE}, (
            domain.source
        )
    assert {view.outlet for view in read_silver(store, OUTLET_VIEWS)} == {
        "Fantacalcio.it",
        "Gazzetta",
        "SOS Fanta",
        "Sky",
    }
    assert (second.outcome, second.stored) == ("unchanged", {})
    assert _bronze(tmp_path / "lake") == stored


def test_at6_unexpected_layout_falls_back(tmp_path: Path) -> None:
    """AT-6: a round page with an unexpected layout stores nothing; the report names it and hands its facts to
    Claude (the refresh plan lists them, with the pages to read through read_page, from task 6.1)."""
    renamed = fco_round_page(FcoMatch("Alfa", "Beta")).replace('title="Gazzetta"', 'title="La Gazzetta"', 1)
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, renamed.encode())}
    with local_site(routes) as site:
        [read] = (
            round_collector(LakeStore(tmp_path / "lake"), site.base_url, tmp_path / "robots").collect().pages
        )
    assert read.outcome == "unreadable"
    assert read.reason is not None
    assert "outlet columns" in read.reason
    assert read.for_claude == list(ROUND_FACTS)
    assert _bronze(tmp_path / "lake") == {}
