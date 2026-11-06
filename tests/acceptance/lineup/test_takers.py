"""AT-18 to AT-21: penalty credit follows who will take them, the list is read and watched, and an official
lineup that's out isn't still to check (R10)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.season.silver import PENALTY_TAKERS
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.cadence import collect_due, what_is_due
from fantadamus.web.fetch import Response
from tests.collect_harness import (
    HTML,
    ROUND_ROUTE,
    TAKERS_ROUTE,
    local_site,
    round_collector,
    ticking,
)
from tests.collect_pages import FcoMatch, fco_round_page, takers_page
from tests.lineup_harness import MATCHES, Round, a_round, rows
from tests.xy_harness import NOW, ask, send

pytestmark = pytest.mark.anyio

LATER = dt.timedelta(hours=49)
LISTS = {club: [f"{club} Nove", f"{club} Dieci"] for club in ("Alfa", "Beta", "Gamma", "Delta")}
A_WEEK_OFF = (
    FcoMatch("Alfa", "Beta", kickoff="03/11/2026 15:00"),
    FcoMatch("Gamma", "Delta", kickoff="03/11/2026 18:00"),
)


def _payload(**orders: list[str]) -> dict[str, Any]:
    return {"clubs": [{"club": club, "takers": orders.get(club, LISTS[club])} for club in LISTS]}


async def _outlook(here: Round, player: str) -> dict[str, Any]:
    result = await here.client.call_tool("player_outlook", {"player": player})
    assert not result.is_error, result
    content = result.structured_content
    assert content is not None
    part: dict[str, Any] = content["answer"]["players"][0]
    return part


async def test_at18_the_next_taker_gets_what_the_first_leaves(tmp_path: Path) -> None:
    doubtful = (FcoMatch("Alfa", "Beta", percents={"Beta Nove": (60, 60, 60, 60)}), MATCHES[1])
    async with a_round(tmp_path, matches=doubtful) as here:
        first = await _outlook(here, "Beta Nove")
        second = await _outlook(here, "Beta Dieci")
        unlisted = await _outlook(here, "Beta Undici")
    assert first["penalty_share"] == 1.0
    assert first["penalty_taker"]
    assert second["penalty_share"] == pytest.approx(1 - first["value"]["p_start"])
    assert not second["penalty_taker"]
    assert (
        "Beta Dieci takes Beta's penalties if Beta Nove misses the start: they count at 40%."
        in second["notes"]
    )
    assert (unlisted["penalty_share"], unlisted["penalty_taker"]) == (0.0, False)


async def test_at18_a_first_taker_out_hands_it_all_on(tmp_path: Path) -> None:
    """Beta Quattordici is out on every outlet: Beta Nove is worth what he would be as the first taker."""
    line = "Beta Nove takes Beta's penalties if Beta Quattordici misses the start: they count at 100%."
    async with a_round(tmp_path / "out") as here:
        await send(
            here.client, "submit_penalty_takers", _payload(Beta=["Beta Quattordici", "Beta Nove"]), NOW
        )
        handed = await _outlook(here, "Beta Nove")
        lineup = await here.ask()
    async with a_round(tmp_path / "first") as here:
        await send(here.client, "submit_penalty_takers", _payload(Beta=["Beta Nove", "Beta Dieci"]), NOW)
        listed = await _outlook(here, "Beta Nove")
    async with a_round(tmp_path / "behind") as here:
        await send(here.client, "submit_penalty_takers", _payload(Beta=["Beta Dieci", "Beta Nove"]), NOW)
        behind = await _outlook(here, "Beta Nove")
    assert handed["penalty_share"] == 1.0
    assert handed["penalty_taker"]
    assert handed["value"]["p_scores"] == pytest.approx(listed["value"]["p_scores"])
    assert behind["value"]["p_scores"] < handed["value"]["p_scores"]
    assert line in handed["notes"]
    assert line in lineup["lineup"]["warnings"]


def _site(takers: str = takers_page(LISTS)) -> dict[str, tuple[int, dict[str, str], bytes]]:
    return {
        "/robots.txt": (404, {}, b""),
        ROUND_ROUTE: (200, HTML, fco_round_page(*MATCHES).encode()),
        TAKERS_ROUTE: (200, HTML, takers.encode()),
    }


def test_at19_the_collector_reads_the_takers(tmp_path: Path) -> None:
    store = LakeStore(tmp_path / "lake")
    with local_site(_site()) as site:
        collector = round_collector(store, site.base_url, tmp_path, takers=True)
        [stored] = collector.collect(facts=["penalty_takers"]).pages
        [again] = collector.collect(facts=["penalty_takers"]).pages
    assert (stored.page, stored.outcome, stored.stored) == ("takers", "stored", {"penalty_takers": 8})
    assert (again.outcome, again.confirmed) == ("unchanged", ["penalty_takers"])
    found = {(row.club, row.rank): row.name for row in read_silver(store, PENALTY_TAKERS)}
    assert found[("beta", 1)] == "Beta Nove"
    assert found[("beta", 2)] == "Beta Dieci"
    assert len(found) == 8


def test_at19_a_changed_layout_goes_to_claude(tmp_path: Path) -> None:
    with local_site(_site(takers_page(LISTS, heading="Rigoristi"))) as site:
        collector = round_collector(LakeStore(tmp_path / "lake"), site.base_url, tmp_path, takers=True)
        [page] = collector.collect(facts=["penalty_takers"]).pages
    assert (page.outcome, page.for_claude) == ("unreadable", ["penalty_takers"])


def test_at19_switched_off_goes_to_claude(tmp_path: Path) -> None:
    with local_site(_site()) as site:
        collector = round_collector(
            LakeStore(tmp_path / "lake"), site.base_url, tmp_path, takers=True, takers_enabled=False
        )
        [page] = collector.collect(facts=["penalty_takers"]).pages
    assert (page.outcome, page.for_claude) == ("switched off", ["penalty_takers"])


def test_at19_due_daily(tmp_path: Path) -> None:
    start = dt.datetime(2026, 11, 3, 8, 0, tzinfo=dt.UTC)
    store = LakeStore(tmp_path / "lake")
    log = CollectLog(tmp_path / "collect")
    with local_site(_site()) as site:
        collector = round_collector(store, site.base_url, tmp_path, takers=True, clock=ticking(start))
        first = collect_due(collector, log)
        assert "penalty_takers" not in what_is_due(store, log, start + dt.timedelta(hours=23))
        assert "penalty_takers" in what_is_due(store, log, start + dt.timedelta(hours=25))
    assert first is not None
    assert "penalty_takers" in first.due
    assert [page.page for page in first.pages] == ["round", "takers"]


async def test_at19_a_missing_list_is_read_by_the_answer(tmp_path: Path) -> None:
    async with a_round(tmp_path, takers=takers_page(LISTS)) as here:
        answer = await here.ask()
        rows_stored = read_silver(here.store, PENALTY_TAKERS)
    assert answer["status"] == "lineup"
    assert any(row.name == "Beta Nove" and row.rank == 1 for row in rows_stored)


async def test_at19_an_unchanged_list_stays_fresh(tmp_path: Path) -> None:
    """Past its 48-hour target, a read that finds it unchanged keeps it fresh, and stores nothing new."""
    async with a_round(tmp_path, matches=A_WEEK_OFF, takers=takers_page(LISTS)) as here:
        assert (await here.ask())["status"] == "lineup"
        before = len(read_silver(here.store, PENALTY_TAKERS))
        here.clock.now = NOW + LATER
        answer = await here.ask()
        after = len(read_silver(here.store, PENALTY_TAKERS))
    assert answer["status"] == "lineup"
    assert after == before


async def test_at19_a_list_that_cant_be_read_goes_stale(tmp_path: Path) -> None:
    async with a_round(tmp_path, matches=A_WEEK_OFF, takers=takers_page(LISTS)) as here:
        assert (await here.ask())["status"] == "lineup"
        here.routes[f"{here.base}{TAKERS_ROUTE}"] = Response(503, {}, b"")
        here.clock.now = NOW + LATER
        answer = await here.ask()
    assert answer["status"] == "refresh"
    assert [item["why"] for item in answer["refresh"] if item["fact"] == "penalty_takers"] == ["stale"]


async def test_at20_a_changed_order_is_named(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await send(here.client, "submit_penalty_takers", _payload(Beta=["Beta Dieci", "Beta Nove"]), NOW)
        warnings = (await here.ask())["lineup"]["warnings"]
        compared = await ask(here.client, "Beta Nove", "Beta Dieci")
    line = "Beta's penalty order changed on 26 Oct: Beta Dieci, Beta Nove (was Beta Nove, Beta Dieci)."
    assert line in warnings
    assert not any("Delta's penalty order" in warning for warning in warnings)
    assert line in compared["answer"]["players"][0]["notes"]


async def test_at20_the_list_against_the_record(tmp_path: Path) -> None:
    """Beta's second taker has taken more; Alfa's too, but this squad has neither; Delta's are level."""
    figures = rows(
        Beta_Nove={"penalties_taken": 1, "penalties_scored": 0},
        Beta_Dieci={"penalties_taken": 2, "penalties_scored": 2},
        Alfa_Dieci={"penalties_taken": 2, "penalties_scored": 2},
        Delta_Nove={"penalties_taken": 1, "penalties_scored": 1},
        Delta_Dieci={"penalties_taken": 1, "penalties_scored": 1},
    )
    async with a_round(tmp_path, players=figures) as here:
        lineup = (await here.ask())["lineup"]
    warnings = lineup["warnings"]
    assert (
        "Beta's list puts Beta Nove first, but Beta Dieci has taken more penalties this season: "
        "2 (scored 2), against 1 (scored 0). The number follows the list."
    ) in warnings
    assert not any("Alfa's list" in warning or "Delta's list" in warning for warning in warnings)
    players = {player["name"]: player for player in lineup["starters"] + lineup["bench"]}
    assert players["Beta Nove"]["penalties"]
    assert not players["Beta Dieci"]["penalties"]


async def test_at21_the_note_follows_the_official_lineup(tmp_path: Path) -> None:
    async with a_round(tmp_path / "before") as here:
        before = (await here.ask())["lineup"]["check_before_lock"]
    confirmed = (FcoMatch("Alfa", "Beta", confirmed=True), MATCHES[1])
    async with a_round(tmp_path / "after", matches=confirmed) as here:
        after = (await here.ask())["lineup"]["check_before_lock"]
        compared = await ask(here.client, "Beta Nove", "Beta Dieci")
    assert len(before) == 1
    assert "so check it then" in before[0]
    assert after == ["The official lineup for Alfa v Beta is out, and this lineup uses it."]
    assert compared["answer"]["check_before_deadline"] == []
