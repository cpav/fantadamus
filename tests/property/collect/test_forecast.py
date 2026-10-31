"""P6: with no facts captured between two times, movement is zero and lists no changes (design C13; R6.1).

The lake is filled and read once; each example compares the answers the same facts give at two times."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.base import Contract
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.contracts.xy.lineups import ProbableLineupPayload
from fantadamus.contracts.xy.odds import MatchOddsPayload
from fantadamus.contracts.xy.season import PenaltyTakersPayload, PlayerSeasonPayload, TeamSeasonPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains import facts
from fantadamus.domains.availability.silver import LINEUP_VIEWS
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.season.silver import PENALTY_TAKERS, PLAYER_SEASONS, TEAM_SEASONS
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, RulesStore
from fantadamus.mcp.tools import compare
from tests.xy_harness import CLUBS, GAMMA_NOVE, NOW, ROOT, TAKERS, TEAM_TABLE, URL, lineup, odds_for, page

READ = NOW - dt.timedelta(hours=1)


@pytest.fixture(scope="module")
def lake(tmp_path_factory: pytest.TempPathFactory) -> tuple[compare.Advisor, compare.Facts]:
    return _filled(LakeStore(tmp_path_factory.mktemp("lake")))


def _filled(store: LakeStore) -> tuple[compare.Advisor, compare.Facts]:
    submissions: list[tuple[facts.Domain[Any, Any], type[Contract], dict[str, Any]]] = [
        (PLAYER_SEASONS, PlayerSeasonPayload, page("player_season")),
        (PLAYER_SEASONS, PlayerSeasonPayload, GAMMA_NOVE),
        (TEAM_SEASONS, TeamSeasonPayload, TEAM_TABLE),
        (PENALTY_TAKERS, PenaltyTakersPayload, TAKERS),
        (FIXTURES, FixturesPayload, page("fixtures")),
    ]
    for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
        submissions += [
            (LINEUP_VIEWS, ProbableLineupPayload, lineup(home, away, outlet)) for outlet in ("Uno", "Due")
        ]
        submissions.append((ODDS, MatchOddsPayload, odds_for(home, away)))
    for domain, contract, payload in submissions:
        facts.submit(
            store,
            domain,
            contract.model_validate_json(json.dumps(payload)),
            source_url=URL,
            captured_at=READ,
            published_at=None,
            allowed_hosts=["example.org"],
            clock=fixed_clock(READ),
            submitted_by="user-1",
            clubs=CLUBS,
        )
    rules = RulesStore(store.root / "league")
    rules.set("user-1", CLASSIC, at=READ)
    advisor = compare.Advisor(
        lake=store,
        rules=rules,
        log=DecisionLog(store.root / "decisions"),
        clubs=CLUBS,
        reading=compare.load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="user-1",
        clock=fixed_clock(NOW),
    )
    return advisor, compare.Facts.read(store)


@given(minutes=st.tuples(st.integers(0, 600), st.integers(0, 600)))  # within the lineups' 12 hours
def test_p6_no_new_facts_no_movement(
    lake: tuple[compare.Advisor, compare.Facts], minutes: tuple[int, int]
) -> None:
    advisor, known = lake
    earlier, later = (READ + dt.timedelta(minutes=minute) for minute in sorted(minutes))
    before = advisor.answer_at("Alfa Nove", "Gamma Nove", earlier, facts=known).answer
    now = advisor.answer_at("Alfa Nove", "Gamma Nove", later, facts=known).answer
    assert before is not None
    assert now is not None
    for then, part in zip(before.players, now.players, strict=True):
        moved = compare.movement(then, part, earlier, "previous answer")
        assert (moved.p_start, moved.p_scores, moved.p_win) == (
            part.value.p_start,
            part.value.p_scores,
            part.p_win,
        )
        assert moved.changes == []
