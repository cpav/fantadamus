"""mvp-collect acceptance tests on the answer: collected first, sources compared, confidence and movement
(R1.3, R5, R6)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.collect_harness import HTML, ROUND_ROUTE, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page
from tests.xy_harness import (
    NOW,
    SetClock,
    ask,
    collect,
    lineup,
    odds_for,
    outlet_lineup,
    page,
    send,
    set_classic,
    tools,
)

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
CALENDAR = "https://www.fantacalcio.it/serie-a/calendario"
ROUND_PAGE = "https://www.fantacalcio-online.com/it/serie-a/2026-2027/probabili-formazioni/ultima-giornata"


async def test_at7_kickoff_disagreement_shown(tmp_path: Path) -> None:
    """AT-7: when Fantacalcio.it's calendar and Fantacalcio-Online's round page disagree on a kickoff, the
    answer uses Fantacalcio.it's and says so; its probabilities carry their confidence (R5.1, R5.3)."""
    hosts = ("example.org", "fantacalcio.it", "fantacalcio-online.com")
    later = page("fixtures")
    later["matches"][0]["kickoff_at"] = "2026-10-31T15:30:00+01:00"  # the round page has Alfa v Beta later
    async with tools(LakeStore(tmp_path), hosts=hosts) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            for outlet in ("Uno", "Due"):
                assert not (
                    await send(client, "submit_probable_lineups", lineup(home, away, outlet), READ)
                ).is_error
            assert not (await send(client, "submit_match_odds", odds_for(home, away), READ)).is_error
        assert not (await send(client, "submit_fixtures", page("fixtures"), READ, url=CALENDAR)).is_error
        newer = READ + dt.timedelta(hours=1)
        assert not (await send(client, "submit_fixtures", later, newer, url=ROUND_PAGE)).is_error
        answer = await ask(client)
    assert answer["status"] == "answer", answer
    nove = answer["answer"]["players"][0]
    assert nove["name"] == "Alfa Nove"
    assert dt.datetime.fromisoformat(nove["kickoff"]) == dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
    assert (
        "Sources disagree, the first is used: Alfa v Beta kickoff: Fantacalcio.it Sat 31 Oct 15:00, "
        "Fantacalcio-Online Sat 31 Oct 15:30."
    ) in nove["notes"]
    assert nove["p_start_confidence"] == {"sources": 2, "spread": 0.0, "label": "agree"}
    assert nove["win_confidence"]["label"] == "one source"  # one odds page
    assert nove["p_scores_confidence"]["label"] == "one source"  # the weaker of the two


async def test_at5_one_call_answer(tmp_path: Path) -> None:
    """AT-5: from a lake with the league rules and fresh season facts, `compare_players` answers in one call:
    the collector reads the round page, no submit tool is used, and the answer has sources and updates."""
    alfa, gamma = FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, fco_round_page(alfa, gamma).encode())}
    store, clock = LakeStore(tmp_path / "lake"), SetClock(NOW)
    with local_site(routes) as site:
        collector = round_collector(store, site.base_url, tmp_path / "robots", clock=clock)
        log = CollectLog(tmp_path / "collect")
        async with tools(store, clock=clock, collector=collector, collect_log=log) as client:
            await set_classic(client)
            await collect(client, READ, facts=("season",))
            result = await client.call_tool("compare_players", {"first": "Alfa Nove", "second": "Gamma Nove"})
    assert [path for path, _ in site.requests] == ["/robots.txt", ROUND_ROUTE]
    content = result.structured_content
    assert content is not None
    assert content["status"] == "answer", content
    answer = content["answer"]
    assert dt.datetime.fromisoformat(answer["updated"]["newest"]) == NOW  # the round page, read just now
    assert dt.datetime.fromisoformat(answer["updated"]["oldest"]) == READ  # the season facts
    urls = {source["source_url"] for source in answer["players"][0]["sources"]}
    assert site.base_url + ROUND_ROUTE in urls


async def test_at8_movement_named(tmp_path: Path) -> None:
    """AT-8: after an outlet moves a player to the bench, the next answer shows his p_start falling from the
    previous answer's value and names the change (R6.1)."""
    clock = SetClock(NOW - dt.timedelta(hours=2))
    async with tools(LakeStore(tmp_path), clock=clock) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season", "fixtures"))
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            for outlet in ("Uno", "Due"):
                assert not (
                    await send(client, "submit_outlet_lineup", outlet_lineup(outlet, home, away), READ)
                ).is_error
            assert not (await send(client, "submit_match_odds", odds_for(home, away), READ)).is_error
        first = await ask(client)
        clock.now = NOW
        benched = outlet_lineup("Due", Alfa_Nove=10)
        assert not (
            await send(client, "submit_outlet_lineup", benched, NOW - dt.timedelta(minutes=30))
        ).is_error
        second = await ask(client)
    before, after = first["answer"]["players"][0], second["answer"]["players"][0]
    movement = after["movement"]
    assert movement["basis"] == "previous answer"
    assert dt.datetime.fromisoformat(movement["since"]) == NOW - dt.timedelta(hours=2)
    assert movement["p_start"] == pytest.approx(before["value"]["p_start"])
    assert after["value"]["p_start"] < movement["p_start"]
    assert movement["changes"] == ["Due 90% → 10%"]
