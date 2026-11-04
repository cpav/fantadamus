"""Task 2.1: what's missing, sorted into what an answer needs and what's better to have (design C5; R3.1,
R5.5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.season.gold import known_players
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import Advisor, Facts, Gathered, load_reading_list
from tests.xy_harness import CLUBS, NOW, ROOT, ask, collect, lineup, odds_for, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)


def _advisor(store: LakeStore) -> Advisor:
    return Advisor(
        lake=store,
        rules=RulesStore(store.root / "league"),
        log=DecisionLog(store.root / "decisions"),
        clubs=CLUBS,
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="user-1",
        clock=fixed_clock(NOW),
    )


def _gathered(store: LakeStore, *wanted: str) -> Gathered:
    facts = Facts.read(store, NOW)
    known = known_players(facts.players, NOW)
    players = [player for player in known if player.name in wanted]
    return _advisor(store).gather(players, NOW, facts=facts, known=known)


async def test_needed_and_better_to_have(tmp_path: Path) -> None:
    """Without a match's lineups or odds, the player can still be priced, from what's known; without the
    table or the fixtures, he can't."""
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season", "fixtures"))
    gathered = _gathered(store, "Alfa Nove")
    assert gathered.needed == []
    assert {(item.fact, item.about) for item in gathered.better} == {
        ("probable_lineups", "Alfa v Beta"),
        ("match_odds", "Alfa v Beta"),
    }
    [side] = gathered.sides
    assert side.present is None  # his lineups aren't out
    assert side.xg is not None  # team form stands in for the odds
    assert not side.xg.from_odds
    assert gathered.round is not None
    assert gathered.first_kickoff is not None


async def test_needed_when_there_are_no_fixtures(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
    gathered = _gathered(store, "Alfa Nove")
    assert [item.fact for item in gathered.needed] == ["fixtures"]
    assert gathered.better == []
    assert gathered.round is None


async def test_with_every_fact_nothing_is_missing(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await set_classic(client)
        await collect(client, READ)
    gathered = _gathered(store, "Alfa Nove", "Gamma Nove")
    assert (gathered.needed, gathered.better) == ([], [])
    assert [side.player.name for side in gathered.sides] == ["Alfa Nove", "Gamma Nove"]
    [alfa, gamma] = gathered.sides
    assert alfa.present is not None
    assert alfa.xg is not None
    assert alfa.xg.from_odds
    assert gamma.present is not None


async def test_x_or_y_still_asks_for_what_is_only_better_to_have(tmp_path: Path) -> None:
    """Better to have matters for a lineup. "X or Y?" still asks for all of it first, lineups before odds, as
    before."""
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season", "fixtures"))
        result = await ask(client)
        assert result["status"] == "refresh"
        assert [item["fact"] for item in result["refresh"]][:2] == ["probable_lineups", "probable_lineups"]
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            for outlet in ("Uno", "Due"):
                await send(client, "submit_probable_lineups", lineup(home, away, outlet), READ)
        result = await ask(client)
        assert {item["fact"] for item in result["refresh"]} == {"match_odds"}
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            await send(client, "submit_match_odds", odds_for(home, away), READ)
        assert (await ask(client))["status"] == "answer"


async def test_freshness_is_each_match_own(tmp_path: Path) -> None:
    """Lineups go stale sooner close to kickoff, so the same read can be fresh for one match and stale for
    another, whichever is asked about first (R7.3 of `mvp-x-or-y`)."""
    store = LakeStore(tmp_path)
    as_of = dt.datetime(2026, 10, 31, 2, 0, tzinfo=dt.UTC)  # Alfa v Beta in 12 hours, Gamma v Delta in 40
    read = as_of - dt.timedelta(hours=8)
    later = page("fixtures")
    later["matches"][1]["kickoff_at"] = "2026-11-01T19:00:00+01:00"
    async with tools(store, now=as_of) as client:
        await set_classic(client)
        await collect(client, read, facts=("season",))
        assert not (await send(client, "submit_fixtures", later, read)).is_error
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            for outlet in ("Uno", "Due"):
                assert not (
                    await send(client, "submit_probable_lineups", lineup(home, away, outlet), read)
                ).is_error
            assert not (await send(client, "submit_match_odds", odds_for(home, away), read)).is_error
    facts = Facts.read(store, as_of)
    known = known_players(facts.players, as_of)
    by_name = {player.name: player for player in known}
    for order in (("Gamma Nove", "Alfa Nove"), ("Alfa Nove", "Gamma Nove")):
        players = [by_name[name] for name in order]
        gathered = _advisor(store).gather(players, as_of, facts=facts, known=known)
        stale = {(item.fact, item.about) for item in gathered.better}
        assert ("probable_lineups", "Alfa v Beta") in stale
        assert ("probable_lineups", "Gamma v Delta") not in stale
