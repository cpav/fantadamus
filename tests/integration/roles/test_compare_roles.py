"""mvp-roles tasks 5.1 and 5.2: `compare_players` for every role: season figures collected first, the lake's
facts read once a call, keepers and outfield players each on their own model (design C9; R1.4, R1.6, R2.5,
R3.5, R4.1, R4.3, R5.2, R6.3)."""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.tools import compare
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE, FakeWeb, round_collector
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.roles_data import ROLE_PLAYERS, season, squad_stats
from tests.xy_harness import (
    NOW,
    TAKERS,
    TEAM_TABLE,
    SetClock,
    ask,
    collect,
    lineup,
    odds_for,
    page,
    send,
    set_classic,
    tools,
)

pytestmark = pytest.mark.anyio

BASE = "https://example.org"
READ = NOW - dt.timedelta(hours=1)
STATISTICS = "https://www.fantacalcio.it/statistiche-serie-a"  # what the reading list lists first
ROUND = fco_round_page(
    FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")
).encode()
STATS = stats_page(squad_stats()).encode()
GOAL_BY_ROLE = {"keeper": 5, "defender": 4.5, "midfielder": 3.5, "forward": 3}


def _web(stats: Response) -> FakeWeb:
    return FakeWeb(
        {
            f"{BASE}/robots.txt": Response(404, {}, b""),
            f"{BASE}{ROUND_ROUTE}": Response(200, HTML, ROUND),
            f"{BASE}{STATS_ROUTE}": stats,
        }
    )


async def _with_roles(client: Client, **rules: object) -> None:
    await set_classic(client, **rules)
    await collect(client, READ)
    for player in ROLE_PLAYERS:
        result = await send(client, "submit_player_season", player, READ)
        assert not result.is_error, result


async def _table_and_takers(client: Client) -> None:
    """All an answer needs that the collector doesn't read."""
    await set_classic(client)
    for tool, payload in (("submit_team_season", TEAM_TABLE), ("submit_penalty_takers", TAKERS)):
        assert not (await send(client, tool, payload, READ)).is_error


def _collecting(store: LakeStore, tmp_path: Path, web: FakeWeb, clock: SetClock) -> dict[str, Any]:
    collector = round_collector(
        store, BASE, tmp_path / "robots", transport=web, hosts=["example.org"], clock=clock, statistics=True
    )
    return {"clock": clock, "collector": collector, "collect_log": CollectLog(tmp_path / "collect")}


async def test_season_figures_collected_first(tmp_path: Path) -> None:
    web, clock = _web(Response(200, HTML, STATS)), SetClock(NOW)
    store = LakeStore(tmp_path / "lake")
    async with tools(store, **_collecting(store, tmp_path, web, clock)) as client:
        await _table_and_takers(client)
        first = await ask(client, "Alfa Uno", "Gamma Uno")  # nobody asked for has figures yet
        assert first["status"] == "answer", first
        clock.now += dt.timedelta(hours=49)  # past the season figures' 48 hours
        second = await ask(client, "Alfa Uno", "Gamma Uno")
    assert second["status"] == "answer", second
    assert f"{BASE}{STATS_ROUTE}" in {
        source["source_url"] for source in first["answer"]["players"][0]["sources"]
    }
    runs = CollectLog(tmp_path / "collect").runs()
    assert [report.page for report in runs[0].pages] == ["round", "statistics"]
    assert runs[-1].pages[-1].page == "statistics"
    assert runs[-1].pages[-1].outcome == "unchanged"  # a read that found it unchanged keeps it fresh


@pytest.mark.parametrize(
    ("stats", "said"),
    [
        (Response(404, {}, b""), "couldn't read"),
        (Response(200, HTML, stats_page(squad_stats()[:-4]).encode()), "rejected"),  # AT-6: a club is missing
    ],
)
async def test_statistics_failure_in_plan(tmp_path: Path, stats: Response, said: str) -> None:
    web, clock = _web(stats), SetClock(NOW)
    store = LakeStore(tmp_path / "lake")
    async with tools(store, **_collecting(store, tmp_path, web, clock)) as client:
        await _table_and_takers(client)
        result = await ask(client, "Alfa Uno", "Gamma Uno")
    assert result["status"] == "refresh", result
    items = {item["about"]: item for item in result["refresh"]}
    item = items["Alfa Uno's season figures"]
    assert (item["fact"], item["read_with"], item["pages"][0]) == ("player_season", "read_page", STATISTICS)
    assert said in item["collector"]
    assert f"{BASE}{STATS_ROUTE}" in item["collector"]
    assert not [
        plan for plan in result["refresh"] if plan["fact"] != "player_season"
    ]  # the round page worked


async def test_facts_read_once_a_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A season of statistics rows costs 0.8 s a read (task 1.3): an answer reads them once, and again only
    after the collector stored something."""
    reads = 0
    read = compare.Facts.read

    def counting(lake: LakeStore) -> compare.Facts:
        nonlocal reads
        reads += 1
        return read(lake)

    monkeypatch.setattr(compare.Facts, "read", counting)
    web, clock = _web(Response(200, HTML, STATS)), SetClock(NOW)
    store = LakeStore(tmp_path / "lake")
    async with tools(store, **_collecting(store, tmp_path, web, clock)) as client:
        await _table_and_takers(client)
        await ask(client, "Alfa Uno", "Gamma Uno")  # the collector stores: read before and after
        assert reads == 2
        reads = 0
        await ask(client, "Alfa Uno", "Gamma Uno")  # everything fresh: no collection
        assert reads == 1
        reads = 0
        clock.now += dt.timedelta(hours=49)
        assert (await ask(client, "Alfa Uno", "Gamma Uno"))["status"] == "answer"  # read, found unchanged
        assert reads == 1


async def test_keepers_compared(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await _with_roles(client)
        result = await ask(client, "Alfa Uno", "Gamma Uno")
    assert result["status"] == "answer", result
    answer = result["answer"]
    assert answer["verdict"]["first"] == "Alfa Uno"
    alfa, gamma = answer["players"]
    assert (alfa["role"], alfa["goals_conceded"], gamma["goals_conceded"]) == ("P", 9, 14)
    prior = 6.0 + 0.35 * 40 / 32  # the table: 40 goals in 32 team matches
    assert alfa["value"]["skill"] == pytest.approx(prior + 8 / 17 * (6.6 + 0.35 * 9 / 8 - prior))
    for part in (alfa, gamma):
        value = part["value"]
        assert value["kind"] == "keeper"
        assert value["expected_conceded"] == part["opponent_xg"]
        assert value["p_clean_sheet"] == pytest.approx(math.exp(-part["opponent_xg"]))
        assert value["e_start"] == pytest.approx(
            value["expected_vote"] + value["p_clean_sheet"] - value["expected_conceded"]
        )
    assert (answer["flip"]["p_start_below"], answer["flip"]["team_xg_below"]) == (None, None)
    assert answer["flip"]["opponent_xg_above"] > alfa["opponent_xg"]
    [logged] = DecisionLog(store.root / "decisions").read()
    assert logged.kind == "compare"
    assert logged.players[0].p_clean_sheet == pytest.approx(alfa["value"]["p_clean_sheet"])
    assert logged.players[0].expected_conceded == alfa["opponent_xg"]
    assert logged.players[0].p_scores is None


async def test_keeper_movement(tmp_path: Path) -> None:
    clock = SetClock(NOW)
    async with tools(LakeStore(tmp_path), clock=clock) as client:
        await _with_roles(client)
        before = (await ask(client, "Alfa Uno", "Gamma Uno"))["answer"]["players"][0]
        odds = odds_for("Alfa", "Beta") | {"home_win": 3.4, "draw": 3.4, "away_win": 2.1}
        clock.now += dt.timedelta(hours=1)
        assert not (await send(client, "submit_match_odds", odds, clock.now)).is_error
        after = (await ask(client, "Alfa Uno", "Gamma Uno"))["answer"]["players"][0]
    movement = after["movement"]
    assert movement["basis"] == "previous answer"
    assert movement["p_clean_sheet"] == pytest.approx(before["value"]["p_clean_sheet"])
    assert movement["p_scores"] is None
    assert f"opponent xG {before['opponent_xg']:.2f} → {after['opponent_xg']:.2f}" in movement["changes"]
    assert after["value"]["p_clean_sheet"] < before["value"]["p_clean_sheet"]


@pytest.mark.parametrize(
    ("first", "second", "bonus"), [("Alfa Due", "Gamma Due", 4.5), ("Alfa Sei", "Gamma Sei", 3.5)]
)
async def test_outfield_players_compared(tmp_path: Path, first: str, second: str, bonus: float) -> None:
    """A defender's or midfielder's answer, with the goal bonus of his Classic role (R2.5)."""
    async with tools(LakeStore(tmp_path)) as client:
        await _with_roles(client, goal=GOAL_BY_ROLE)
        result = await ask(client, first, second)
    assert result["status"] == "answer", result
    for part in result["answer"]["players"]:
        value = part["value"]
        assert value["kind"] == "outfield"
        assert value["e_start"] == pytest.approx(
            value["expected_vote"] + bonus * value["e_goals"] + value["e_assists"] - 0.5 * value["p_yellow"]
        )
        assert value["e_cameo"] == 5.5 or part["name"] == "Gamma Sei"  # his Mantra role is T: priced
    keys = [part["value"]["key"] for part in result["answer"]["players"]]
    assert result["answer"]["verdict"]["key_margin"] == pytest.approx(
        abs(keys[0] - keys[1])
    )  # the same bonus


async def test_defenders_compared(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await _with_roles(client)
        result = await ask(client, "Alfa Due", "Gamma Due")
    shares = [part["value"]["goal_share"] for part in result["answer"]["players"]]
    # Two goals in eight games, on the priors of a centre-back and a full-back, with a defender's weight
    assert shares == [
        pytest.approx((0.05 * 25 + 2) / (25 + 14)),
        pytest.approx((0.03 * 25 + 2) / (25 + 6)),
    ]


async def test_wont_play_names_the_role(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await _with_roles(client)
        out = await ask(client, "Alfa Quattordici", "Gamma Due")
        for keeper, player_id in (("Beta Quattordici", 9401), ("Gamma Quattordici", 9403)):
            profile = season(keeper, "P", "Por", player_id)
            assert not (await send(client, "submit_player_season", profile, READ)).is_error
        neither = await ask(client, "Beta Quattordici", "Gamma Quattordici")
    assert "so put a fit defender first on the bench" in out["message"]
    assert "field another keeper" in neither["message"]


async def test_outlets_name_by_surname(tmp_path: Path) -> None:
    """On the real round page an outlet writes a compound surname in part: he must get the outlets' chances,
    not the 5% of a player nobody mentions, and the answer says how he was matched."""
    rows = [row | {"name": "Zeta Due"} if row["name"] == "Alfa Due" else row for row in squad_stats()]
    web, clock = _web(Response(200, HTML, stats_page(rows).encode())), SetClock(NOW)
    store = LakeStore(tmp_path / "lake")
    async with tools(store, **_collecting(store, tmp_path, web, clock)) as client:
        await _table_and_takers(client)
        result = await ask(client, "Zeta Due", "Gamma Due")
    assert result["status"] == "answer", result
    zeta, gamma = result["answer"]["players"]
    assert zeta["value"]["p_start"] == pytest.approx(gamma["value"]["p_start"])
    assert any("by surname" in note and "DUE A" in note for note in zeta["notes"])
    assert not any("by surname" in note for note in gamma["notes"])


async def test_keeper_without_a_match(tmp_path: Path) -> None:
    """He won't play, so there's no clean sheet to log for him (R6.3)."""
    only_alfa = page("fixtures")
    only_alfa["matches"] = only_alfa["matches"][:1]
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        assert not (await send(client, "submit_fixtures", only_alfa, READ)).is_error
        for tool, payload in (
            ("submit_probable_lineups", lineup("Alfa", "Beta", "Uno")),
            ("submit_match_odds", odds_for("Alfa", "Beta")),
        ):
            assert not (await send(client, tool, payload, READ)).is_error
        for player in ROLE_PLAYERS:
            assert not (await send(client, "submit_player_season", player, READ)).is_error
        result = await ask(client, "Alfa Uno", "Gamma Uno")
    assert "Gamma Uno won't play, so put a fit keeper first on the bench" in result["message"]
    alfa, gamma = DecisionLog(store.root / "decisions").read()[0].players
    assert alfa.p_clean_sheet is not None
    assert (gamma.p_clean_sheet, gamma.expected_conceded) == (None, None)


async def test_a_page_just_read_is_not_read_again(tmp_path: Path) -> None:
    """Testing on the real tools: asking about a name nobody knows, or a match whose odds show no over/under,
    read the same page again on every question. An answer leaves it alone within its interval."""
    web, clock = _web(Response(200, HTML, STATS)), SetClock(NOW)
    store = LakeStore(tmp_path / "lake")

    def reads(route: str) -> int:
        return [url for url, _, _ in web.calls].count(f"{BASE}{route}")

    async with tools(store, **_collecting(store, tmp_path, web, clock)) as client:
        await _table_and_takers(client)
        await ask(client, "Alfa Uno", "Gamma Uno")
        assert (reads(STATS_ROUTE), reads(ROUND_ROUTE)) == (1, 1)
        unknown = await ask(client, "Lautaro", "Gamma Uno")
        assert unknown["status"] == "refresh"
        assert [item["fact"] for item in unknown["refresh"]] == ["player_season"]
        clock.now += dt.timedelta(hours=23)  # the page is read once a day at most
        assert (await ask(client, "Lautaro", "Gamma Uno"))["status"] == "refresh"
        assert reads(STATS_ROUTE) == 1
        clock.now += dt.timedelta(hours=2)
        assert (await ask(client, "Lautaro", "Gamma Uno"))["status"] == "refresh"
        assert reads(STATS_ROUTE) == 2
