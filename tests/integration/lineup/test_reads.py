"""Task 2.2: reading a whole squad quickly (design C4; R4.6)."""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from typing import Any

import pytest

from fantadamus.contracts.types import Role
from fantadamus.core.clock import fixed_clock
from fantadamus.domains.availability import gold
from fantadamus.domains.availability.silver import LINEUP_VIEWS, LineupViewRow
from fantadamus.domains.facts import read_silver
from fantadamus.domains.freshness import FACTS_WINDOW, Fact, target
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.season.gold import known_players
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import Advisor, Facts, load_reading_list
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, local_site, round_collector, ticking
from tests.collect_pages import FcoMatch, fco_round_page, squad, stats_page
from tests.roles_data import season
from tests.xy_harness import (
    CLUBS,
    NOW,
    ROOT,
    SetClock,
    ask,
    collect,
    lineup,
    send,
    set_classic,
    tools,
)

pytestmark = pytest.mark.anyio

DAY = dt.timedelta(days=1)
ROLES: tuple[tuple[Role, str], ...] = (("P", "Por"), ("D", "Dc"), ("C", "C"), ("A", "Pc"))
FACTS: tuple[Fact, ...] = (
    "fixtures",
    "probable_lineups",
    "match_odds",
    "player_season",
    "team_season",
    "penalty_takers",
)


async def _lineups_at(store: LakeStore, *times: dt.datetime) -> None:
    async with tools(store) as client:
        for at in times:
            result = await send(client, "submit_probable_lineups", lineup("Alfa", "Beta", "Uno"), at)
            assert not result.is_error


async def test_window_moves_with_as_of(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    await _lineups_at(store, NOW - 30 * DAY, NOW - 20 * DAY, NOW - 10 * DAY, NOW - DAY)
    # The 14 days up to then: not what came later, nor what's older.
    assert {row.captured_at for row in Facts.read(store, NOW - 15 * DAY).views} == {NOW - 20 * DAY}
    assert {row.captured_at for row in Facts.read(store, NOW).views} == {NOW - 10 * DAY, NOW - DAY}


async def test_old_rows_left_out(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    edge, older = NOW - FACTS_WINDOW, NOW - FACTS_WINDOW - dt.timedelta(seconds=1)
    await _lineups_at(store, older, edge)
    assert {row.captured_at for row in Facts.read(store, NOW).views} == {edge}
    assert {row.captured_at for row in read_silver(store, LINEUP_VIEWS)} == {older, edge}  # all still stored


def test_no_freshness_target_outlives_the_window() -> None:
    """A live answer never needs an older row, and movement up to a week back still has its facts."""
    far = NOW + 30 * DAY
    assert max(target(fact, as_of=NOW, kickoff=far) for fact in FACTS) <= FACTS_WINDOW - 7 * DAY


async def test_replay_and_movement_within_a_week(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    earlier = NOW - 7 * DAY
    clock = SetClock(earlier)
    async with tools(store, clock=clock) as client:
        await set_classic(client)
        await collect(client, earlier - dt.timedelta(hours=2))
        first = await ask(client)
        assert first["status"] == "answer", first
        clock.now = NOW
        await collect(client, NOW - dt.timedelta(hours=1))
        later = await ask(client)
        replay = await ask(client, as_of=earlier.isoformat())
    assert later["status"] == "answer", later
    movement = later["answer"]["players"][0]["movement"]
    assert movement["basis"] == "previous answer"
    assert dt.datetime.fromisoformat(movement["since"]) == earlier
    assert movement["p_start"] == first["answer"]["players"][0]["value"]["p_start"]
    assert replay["status"] == "answer", replay
    assert replay["answer"]["players"][0]["value"] == first["answer"]["players"][0]["value"]


async def test_an_answer_reads_what_the_collector_just_stored(tmp_path: Path) -> None:
    """The window ends at the answer's time, so that time has to move on with the clock while the collector
    reads, or the answer would miss what it just stored."""
    page = fco_round_page(FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00"))
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, page.encode())}
    store, clock = LakeStore(tmp_path / "lake"), ticking(NOW)
    with local_site(routes) as site:
        collector = round_collector(store, site.base_url, tmp_path / "robots", clock=clock)
        log = CollectLog(tmp_path / "collect")
        async with tools(store, clock=clock, collector=collector, collect_log=log) as client:
            await set_classic(client)
            await collect(client, NOW - DAY, facts=("season",))
            result = await ask(client)
    assert result["status"] == "answer", result
    assert result["answer"]["players"][0]["outlets"]


def test_each_name_resolved_once_per_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outlets repeat one another's names, so each distinct name of a club is matched once in a call."""
    names = squad("Alfa")
    players = [KnownPlayer(player_id=index + 1, name=name, club="alfa") for index, name in enumerate(names)]
    views = [
        LineupViewRow(
            source_url=f"https://example.org/{outlet}",
            captured_at=NOW,
            content_sha256=outlet,
            home="alfa",
            away="beta",
            outlet=outlet,
            club="alfa",
            name=name,
            status="starter",
            share=None,
            contest=None,
        )
        for outlet in ("uno", "due", "tre", "quattro")
        for name in names[:11]
    ]
    calls: list[str] = []

    def counting(name: str, known: Any) -> Any:
        calls.append(name)
        return resolve(name, known)

    monkeypatch.setattr(gold, "resolve", counting)
    result = gold.availability(
        players[8], home="alfa", away="beta", views=views, officials=[], players=players, as_of=NOW
    )
    assert result is not None
    assert len(result.outlets) == 4
    assert all(view.status == "starter" for view in result.outlets)
    assert sorted(calls) == sorted(names[:11])


async def test_a_whole_squad_reads_quickly(tmp_path: Path) -> None:
    """Twenty-five players through the gathering step, on four clubs' full squads and four outlets: the time a
    lineup has before its simulation (R4.6). On the owner's real squad this took 1.27 s before names were
    cached."""
    clubs = ("Alfa", "Beta", "Gamma", "Delta")
    rows = [
        season(name, *ROLES[number % len(ROLES)], 8000 + 100 * index + number)
        for index, club in enumerate(clubs)
        for number, name in enumerate(squad(club))
    ]
    page = fco_round_page(FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00"))
    routes = {
        "/robots.txt": (404, {}, b""),
        ROUND_ROUTE: (200, HTML, page.encode()),
        STATS_ROUTE: (200, HTML, stats_page(rows).encode()),
    }
    store = LakeStore(tmp_path / "lake")
    with local_site(routes) as site:
        collector = round_collector(
            store, site.base_url, tmp_path / "robots", clock=SetClock(NOW), statistics=True
        )
        pages = collector.collect().pages
    assert {page.outcome for page in pages} == {"stored"}, pages
    async with tools(store) as client:
        await collect(client, NOW - DAY, facts=("season",))  # the table and the takers
    advisor = Advisor(
        lake=store,
        rules=RulesStore(store.root / "league"),
        log=DecisionLog(store.root / "decisions"),
        clubs=CLUBS,
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="user-1",
        clock=fixed_clock(NOW),
    )
    facts = Facts.read(store, NOW)
    known = known_players(facts.players, NOW)
    players = [player for player in known if player.player_id >= 8000][:25]
    started = time.perf_counter()
    gathered = advisor.gather(players, NOW, facts=facts, known=known)
    took = time.perf_counter() - started
    assert len(gathered.sides) == 25
    assert all(side.present is not None for side in gathered.sides)
    assert took < 1.0
