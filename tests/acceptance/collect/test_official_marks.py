"""AT-12: the page's marks decide who starts, whichever table lists him (R3.1, R4.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.engine.constants import CAMEO_SHARE
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.collect_harness import HTML, ROUND_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page, squad
from tests.xy_harness import NOW, SetClock, ask, collect, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)


async def test_at12_the_marks_decide(tmp_path: Path) -> None:
    alfa, beta = squad("Alfa"), squad("Beta")
    # Alfa's real eleven: Alfa Nove, a probable starter, is out; Alfa Dodici, on the probable bench, is in.
    # Beta has 10 marks, because the page doesn't list its eleventh starter.
    marked = (*(name for name in alfa[:11] if name != "Alfa Nove"), "Alfa Dodici", *beta[:10])
    match = FcoMatch("Alfa", "Beta", marked=marked)
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, fco_round_page(match).encode())}
    store, clock = LakeStore(tmp_path / "lake"), SetClock(NOW)
    known = (
        ("Alfa Dodici", "Alfa", 9012),
        ("Alfa Sedici", "Alfa", 9016),
        ("Beta Sedici", "Beta", 9116),
        ("Beta Uno", "Beta", 9101),
    )
    with local_site(routes) as site:
        collector = round_collector(store, site.base_url, tmp_path / "robots", clock=clock)
        log = CollectLog(tmp_path / "collect")
        async with tools(store, clock=clock, collector=collector, collect_log=log) as client:
            await set_classic(client)
            await collect(client, READ, facts=("season",))
            for name, club, player_id in known:
                season = {**page("player_season"), "player_id": player_id, "name": name, "club": club}
                assert not (await send(client, "submit_player_season", season, READ)).is_error
            swapped = await ask(client, "Alfa Nove", "Alfa Dodici")
            off_the_sheet = await ask(client, "Alfa Sedici", "Beta Sedici")
            ten_marks = await ask(client, "Beta Uno", "Beta Sedici")

    assert swapped["status"] == "answer", swapped
    nove, dodici = (player for player in swapped["answer"]["players"])
    assert (nove["name"], nove["value"]["p_start"], nove["value"]["p_cameo"]) == (
        "Alfa Nove",
        0.0,
        CAMEO_SHARE,
    )
    assert nove["official"]["status"] == "bench"
    assert (dodici["name"], dodici["value"]["p_start"], dodici["value"]["p_cameo"]) == (
        "Alfa Dodici",
        1.0,
        0.0,
    )
    assert dodici["official"]["status"] == "starter"
    assert dodici["p_start_confidence"]["label"] == "official"

    assert off_the_sheet["status"] == "answer", off_the_sheet
    alfa_sedici, beta_sedici = (player for player in off_the_sheet["answer"]["players"])
    assert (
        alfa_sedici["official"]["status"] == "not listed"
    )  # Alfa's lineup names all 11, so he isn't playing
    assert alfa_sedici["value"]["p_start"] == 0.0
    assert beta_sedici["official"] is None  # Beta's can't name one starter, so he isn't ruled out
    assert beta_sedici["value"]["p_start"] > 0.0

    assert ten_marks["status"] == "answer", ten_marks
    uno = ten_marks["answer"]["players"][0]
    assert (uno["name"], uno["value"]["p_start"]) == ("Beta Uno", 1.0)  # a named starter stays settled
    assert uno["official"]["status"] == "starter"
