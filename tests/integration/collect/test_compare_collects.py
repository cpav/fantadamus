"""mvp-collect task 6.1: `compare_players` collects the round page first, counts a read that found it
unchanged as fresh, and leaves Claude only what the collector couldn't get, through read_page (design C11;
R1.3, R1.5, R8.1)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, FakeWeb, round_collector
from tests.collect_pages import FcoMatch, fco_round_page
from tests.xy_harness import NOW, SetClock, ask, collect, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
READ = NOW - dt.timedelta(hours=1)
ROUND = fco_round_page(
    FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")
).encode()


def _web(round_page: Response) -> FakeWeb:
    return FakeWeb({f"{BASE}/robots.txt": Response(404, {}, b""), f"{BASE}{ROUND_ROUTE}": round_page})


async def _ask_with_collector(
    tmp_path: Path, web: FakeWeb, clock: SetClock, *moves: dt.timedelta
) -> list[dict[str, Any]]:
    """Season facts submitted, then `compare_players` asked now and after each move of the clock."""
    store = LakeStore(tmp_path / "lake")
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock
    )
    answers = []
    async with tools(
        store, clock=clock, collector=collector, collect_log=CollectLog(tmp_path / "collect")
    ) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        answers.append(await ask(client))
        for move in moves:
            clock.now += move
            answers.append(await ask(client))
        replay = clock.now - dt.timedelta(minutes=1)  # just before the last read: replays never collect
        answers.append(await ask(client, as_of=replay.isoformat()))
    return answers


async def test_missing_facts_collected_first(tmp_path: Path) -> None:
    web = _web(Response(200, HTML, ROUND))
    [answer, _] = await _ask_with_collector(tmp_path, web, SetClock(NOW))
    assert answer["status"] == "answer", answer
    assert [url for url, _, _ in web.calls] == [f"{BASE}/robots.txt", f"{BASE}{ROUND_ROUTE}"]
    [run] = CollectLog(tmp_path / "collect").runs()
    assert run.pages[0].outcome == "stored"


async def test_unchanged_read_counts_as_fresh(tmp_path: Path) -> None:
    web = _web(Response(200, HTML, ROUND))
    later = dt.timedelta(hours=13)  # past the probable lineups' 12 hours
    first, second, replay = await _ask_with_collector(tmp_path, web, SetClock(NOW), later)
    assert (first["status"], second["status"]) == ("answer", "answer")
    runs = CollectLog(tmp_path / "collect").runs()
    assert [run.pages[0].outcome for run in runs] == ["stored", "unchanged"]
    assert {"outlet_views", "odds", "fixtures"} <= set(runs[1].pages[0].confirmed)
    # A minute before that unchanged read, the lineups were stale: the read is what kept them fresh.
    assert replay["status"] == "refresh"
    assert {item["fact"] for item in replay["refresh"]} == {"probable_lineups"}


async def test_failures_named_in_plan(tmp_path: Path) -> None:
    web = _web(Response(429, {}, b""))
    store = LakeStore(tmp_path / "lake")
    clock = SetClock(NOW)
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock
    )
    async with tools(
        store, clock=clock, collector=collector, collect_log=CollectLog(tmp_path / "collect")
    ) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        assert not (await send(client, "submit_fixtures", page("fixtures"), READ)).is_error
        result = await ask(client)
    assert result["status"] == "refresh"
    assert "read_page" in result["message"]
    items = {(item["fact"], item["about"]): item for item in result["refresh"]}
    assert set(items) == {
        ("probable_lineups", "Alfa v Beta"),
        ("probable_lineups", "Gamma v Delta"),
        ("match_odds", "Alfa v Beta"),
        ("match_odds", "Gamma v Delta"),
    }
    lineups, odds = items["probable_lineups", "Alfa v Beta"], items["match_odds", "Alfa v Beta"]
    assert (lineups["read_with"], odds["read_with"]) == ("read_page", "search")
    assert lineups["pages"]
    assert not odds["pages"]
    reason = "example.org answered 429; stopped for this run"
    tried = f"Fantadamus couldn't read {BASE}{ROUND_ROUTE}: blocked ({reason})"
    assert lineups["collector"] == odds["collector"] == tried
