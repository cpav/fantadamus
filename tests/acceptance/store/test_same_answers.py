"""AT-7 of mvp-store: reading everything and reading what an answer uses give the same answer, on a round
whose page was read and stored several times: every tool, a movement, a review and an alerts' check (R3.5).
Its property is P4, in `tests/property/store/test_same_answers.py`."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import shutil
from collections.abc import Awaitable, Callable, Collection, Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.availability.silver import OUTLET_VIEWS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.ratings.silver import MATCH_RATINGS, MatchRatingRow
from fantadamus.lake.alert_log import AlertLog
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import Advisor, Facts, load_reading_list
from fantadamus.mcp.alerts import check_alerts
from fantadamus.mcp.calibrate import Calibrator
from fantadamus.mcp.server import make_advisor
from fantadamus.web.collector import CollectReport, PageReport
from tests.acceptance.sources.test_raters import _stored as stored_ratings
from tests.alerts_harness import IN_WINDOW, Shown
from tests.collect_pages import FcoMatch
from tests.lineup_harness import AFTER_THE_ROUND, MATCHES, Round, a_round, finished, player_id
from tests.store_lake import newest_submissions
from tests.xy_harness import CLUBS, NOW, ROOT, lineup, odds_for, send, tools

pytestmark = pytest.mark.anyio

STEP = dt.timedelta(hours=2)
AS_OF = NOW + 4 * STEP
"""After the page's last read, before the round's deadline."""
ASKED: list[tuple[str, dict[str, Any]]] = [
    ("compare_players", {"first": "Beta Nove", "second": "Delta Nove"}),
    ("compare_players", {"first": "Alfa Uno", "second": "Gamma Uno"}),
    ("player_outlook", {"player": "Alfa Nove"}),
    ("player_outlook", {"player": "Gamma Due"}),
    ("best_lineup", {}),
    ("match_card", {"club": "Alfa"}),
    ("match_card", {"club": "Delta"}),
    ("round_overview", {}),
]
ANSWERED = ["answer", "answer", "outlook", "outlook", "lineup", "card", "card", "overview"]
REPORT = CollectReport(
    started_at=IN_WINDOW,
    finished_at=IN_WINDOW,
    round=None,
    pages=[PageReport(url="https://example.org/round", outcome="stored", stored={"official_lineups": 22})],
)
"""A scheduled run in the alerts' window that stored official lineups: what makes a check look."""

Asked = Callable[[Path], Awaitable[list[Any]]]


def _round(step: int) -> tuple[FcoMatch, FcoMatch]:
    """The round page at its `step`-th read: two starters' chances move, and so do the odds."""
    first = dataclasses.replace(
        MATCHES[0],
        percents={"Beta Nove": (90 - 15 * step, 85 - 10 * step, 95, 90)},
        odds=(f"2,{10 + step}", "3,30", f"3,{60 - step}"),
    )
    second = dataclasses.replace(MATCHES[1], percents={"Gamma Due": (55 + 10 * step, 70, 60, 65)})
    return first, second


BETWEEN_KICKOFFS = dt.datetime(2026, 10, 31, 15, 30, tzinfo=dt.UTC)
"""After Alfa v Beta has kicked off and before Gamma v Delta: what calibration reads at each kickoff."""


def _written(outlet: str, benched: tuple[str, ...] = ()) -> dict[str, Any]:
    """An outlet's written lineup for Alfa v Beta, as Claude would submit it, with `benched` on the bench."""
    payload = lineup("Alfa", "Beta", outlet)
    for team in (payload["home_team"], payload["away_team"]):
        for name in benched:
            if name in team["starters"]:
                team["starters"].remove(name)
                team["bench"].append(name)
                team["starters"].append(team["bench"].pop(0))
    return payload


def _season(club: str, word: str, goals: int) -> dict[str, Any]:
    """A player's season figures from his profile page, as Claude would submit them."""
    return {
        "player_id": player_id(club, word),
        "name": f"{club} {word}",
        "club": club,
        "role": "A",
        "mantra_role": "Pc",
        "appearances": 9,
        "rated_appearances": 9,
        "average_rating": 6.6,
        "goals": goals,
        "assists": 2,
        "yellow_cards": 1,
        "penalties_scored": 0,
        "penalties_taken": 0,
    }


async def _submitted(here: Round, step: int, at: dt.datetime) -> None:
    """What Claude read from other pages at a step: two outlets' written lineups, two bookmakers' odds and two
    players' profiles, each page holding several, and some of them changing from one step to the next."""
    benched = ("Beta Nove",) if step else ()
    payloads: list[tuple[str, dict[str, Any]]] = [
        ("submit_probable_lineups", _written("Uno", benched)),
        ("submit_probable_lineups", _written("Due")),
        ("submit_match_odds", odds_for("Alfa", "Beta") | {"home_win": 2.1 + step / 10}),
        (
            "submit_match_odds",
            odds_for("Alfa", "Beta") | {"bookmaker": "Banco Due", "home_win": 2.4, "away_win": 3.0},
        ),
        ("submit_player_season", _season("Beta", "Nove", 6 + step)),
        ("submit_player_season", _season("Delta", "Nove", 4)),
    ]
    for tool, payload in payloads:
        assert not (await send(here.client, tool, payload, at)).is_error


async def _build(folder: Path) -> None:
    async with a_round(folder) as here:
        await stored_ratings(here.client)  # five earlier rounds' ratings of Alfa Nove: a claim to show
        await here.ask()  # the first read of every page
        await _submitted(here, 0, NOW)
        collector = here.calibrator.collector
        assert collector is not None
        for step in (1, 2, 3):
            here.clock.now = NOW + step * STEP
            here.round_page(*_round(step))
            here.collect_log.append(collector.collect(facts=["probable_lineups", "match_odds"]))
            if step == 2:
                await _submitted(here, step, here.clock.now)
                # an answer the later ones move from
                await here.client.call_tool("compare_players", {"first": "Beta Nove", "second": "Delta Nove"})
        here.clock.now = NOW + 3 * STEP + dt.timedelta(minutes=30)
        here.collect_log.append(collector.collect(facts=["probable_lineups"]))  # unchanged: it confirms
        here.clock.now = BETWEEN_KICKOFFS
        here.round_page(*_round(4))
        here.collect_log.append(collector.collect(facts=["probable_lineups"]))
        finished(here)
        here.collect_log.append(collector.collect(facts=["player_season"]))  # the statistics after the round


@pytest.fixture(scope="module")
def history(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The round, built once: each test asks copies of it."""
    folder = tmp_path_factory.mktemp("history")
    anyio.run(_build, folder)
    return folder


@contextlib.contextmanager
def everything_read(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Answers that read as before this slice: every row of the window, and every club's ratings."""
    read = Facts.read

    def whole(lake: LakeStore, as_of: dt.datetime, history: bool = False) -> Facts:
        return read(lake, as_of, history=True)

    def every_club(self: Advisor, clubs: Collection[str], as_of: dt.datetime) -> list[MatchRatingRow]:
        return [row for row in read_silver(self.lake, MATCH_RATINGS, None, as_of) if row.club in clubs]

    with monkeypatch.context() as patched:
        patched.setattr(Facts, "read", whole)
        patched.setattr(Advisor, "ratings", every_club)
        yield


async def _both_ways(history: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ask: Asked) -> list[Any]:
    """What `ask` finds in a copy of the round read as this slice reads it; asserted the same in another copy
    read whole."""
    reduced = await ask(shutil.copytree(history, tmp_path / "reduced"))
    with everything_read(monkeypatch):
        whole = await ask(shutil.copytree(history, tmp_path / "whole"))
    assert reduced == whole
    return reduced


def _asking(asked: list[tuple[str, dict[str, Any]]], as_of: dt.datetime) -> Asked:
    async def ask(folder: Path) -> list[Any]:
        found = []
        store = LakeStore(folder / "lake")
        async with tools(
            store, clock=fixed_clock(as_of), collect_log=CollectLog(folder / "collect")
        ) as client:
            for tool, args in asked:
                result = await client.call_tool(tool, {**args, "as_of": as_of.isoformat()})
                assert not result.is_error, result
                found.append(result.structured_content)
        return found

    return ask


def test_the_round_was_read_and_stored_several_times(history: Path) -> None:
    """What the tests below rest on: the newest submissions are a part of the window's rows."""
    rows = read_silver(LakeStore(history / "lake"), OUTLET_VIEWS, AS_OF - FACTS_WINDOW, AS_OF)
    newest = newest_submissions(rows, ("home", "away", "outlet"))
    assert len({row.captured_at for row in rows}) >= 4
    assert len(newest) < len(rows) / 2


async def test_at7_every_tool_answers_the_same_both_ways(
    history: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = await _both_ways(history, tmp_path, monkeypatch, _asking(ASKED, AS_OF))
    assert [answer["status"] for answer in found] == ANSWERED
    [outlook] = found[2]["answer"]["players"]
    assert outlook["raters"]  # the claim, from the ratings of the club asked about


async def test_at7_a_movement_is_the_same(
    history: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From the answer logged at the second read, and over 24 hours for two players no answer had."""
    asked = [ASKED[0], ("compare_players", {"first": "Alfa Nove", "second": "Gamma Nove"})]
    found = await _both_ways(history, tmp_path, monkeypatch, _asking(asked, AS_OF))
    moved = [player["movement"] for answer in found for player in answer["answer"]["players"]]
    assert [movement["basis"] for movement in moved] == [
        "previous answer",
        "previous answer",
        "24 hours earlier",
        "24 hours earlier",
    ]
    assert any(movement["changes"] for movement in moved[:2])  # Beta Nove's chances moved since


async def test_at7_a_review_and_a_check_are_the_same(
    history: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review scores the round in each copy: calibration asks about each match at its own kickoff, and a
    read between the two kickoffs replaced the first match's lineups."""
    reviewed = _asking([("review_round", {"round": 10, "as_advised": True})], AFTER_THE_ROUND)

    async def ask(folder: Path) -> list[Any]:
        found = await reviewed(folder)
        store = LakeStore(folder / "lake")
        scored = CalibrationStore(store.root / "calibration")
        calibrator = Calibrator(
            lake=store,
            log=DecisionLog(store.root / "decisions"),
            store=scored,
            clock=fixed_clock(AFTER_THE_ROUND),
            collect_log=CollectLog(folder / "collect"),
        )
        report, kept = calibrator.report(10), scored.calibration_set(10)
        assert report is not None
        assert kept is not None
        found += [report.model_dump(), kept.model_dump()]
        advisor = make_advisor(
            store,
            rules=RulesStore(store.root / "league"),
            log=DecisionLog(store.root / "decisions"),
            clubs=CLUBS,
            reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
            user="user-1",
            clock=fixed_clock(IN_WINDOW),
            collect_log=CollectLog(folder / "collect"),
        )
        alerts = AlertLog(store.root / "alerts")
        checked = check_alerts(advisor, alerts, REPORT, Shown(), enabled=True)
        return [*found, dataclasses.asdict(checked), [line.model_dump() for line in alerts.read()]]

    review_found, _, _, checked, lines = await _both_ways(history, tmp_path, monkeypatch, ask)
    assert review_found["status"] == "review"
    assert checked["outcome"] == "sent"  # the lineup told at the first read has changed since
    assert [line["kind"] for line in lines] == ["alert"]
