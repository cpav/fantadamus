"""The simulation's arithmetic by hand, in tests fast enough for the mutation run (task 9.4; R3, R4)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import pytest

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LineupRules
from fantadamus.engine.lineup import Arrangement, Candidate
from fantadamus.engine.simulate import (
    Plan,
    Simulated,
    fantasy_goals,
    field,
    plan,
    ranked,
    recommended,
    summarize,
)

Mode = Literal["same_role", "role_first", "bench_order"]
ROLES: dict[int, Role] = {
    1: "P",
    2: "D",
    3: "D",
    4: "D",
    5: "D",
    6: "C",
    7: "C",
    8: "C",
    9: "A",
    10: "A",
    11: "A",
}
ROLES |= {12: "P", 13: "D", 14: "C", 15: "A", 16: "C", 17: "D"}
"""A 4-3-3, and who can sit on the bench."""
FORMATIONS = ("4-3-3", "3-4-3", "3-5-2")


def _player(player_id: int) -> Candidate:
    return Candidate(
        player_id=player_id,
        name=f"P{player_id}",
        role=ROLES[player_id],
        club="alfa",
        p_start=0.9,
        p_cameo=0.05,
        key=6.0,
    )


def _plan(
    mode: Mode = "same_role",
    bench: Sequence[int] = (12, 13, 14, 15),
    *,
    substitutions: int = 3,
    vote: float | None = None,
    formations: Sequence[str] = FORMATIONS,
) -> Plan:
    arrangement = Arrangement(
        formation="4-3-3",
        starters=tuple(_player(player_id) for player_id in range(1, 12)),
        bench=tuple(_player(player_id) for player_id in bench),
        left_off=(),
    )
    rules = LineupRules(
        format="head_to_head",
        thresholds=[66.0, 72.0],
        bench_size=7,
        substitutions=substitutions,
        substitution_mode=mode,
        formations=list(formations),
        no_rating_vote=vote,
    )
    return plan(arrangement, rules)


def _scores(*missing: int, **given: float) -> dict[int, float | None]:
    scores: dict[int, float | None] = dict.fromkeys(ROLES, 6.0)
    scores.update(dict.fromkeys(missing))
    scores.update({int(player.removeprefix("p")): score for player, score in given.items()})
    return scores


def test_nobody_missing() -> None:
    assert field(_scores(), _plan()) == (66.0, [])


@pytest.mark.parametrize(("out", "comes_on"), [(1, 12), (2, 13), (6, 14), (9, 15)])
def test_like_for_like(out: int, comes_on: int) -> None:
    assert field(_scores(out, p13=7.0, p14=7.0, p15=7.0, p12=7.0), _plan()) == (67.0, [(out, comes_on)])


def test_the_next_on_the_bench_with_a_rating() -> None:
    assert field(_scores(2, 13), _plan(bench=(12, 13, 17))) == (66.0, [(2, 17)])


def test_a_player_comes_on_once() -> None:
    assert field(_scores(2, 3), _plan()) == (60.0, [(2, 13)])


@pytest.mark.parametrize(("vote", "total"), [(None, 60.0), (3.0, 63.0)])
def test_an_empty_place_keeps_the_leagues_vote(vote: float | None, total: float) -> None:
    assert field(_scores(2, 13), _plan(vote=vote)) == (total, [])


@pytest.mark.parametrize(("cap", "total", "moves"), [(1, 60.0, [(2, 13)]), (0, 54.0, [])])
def test_substitutions_stop_at_the_cap(cap: int, total: float, moves: list[tuple[int, int]]) -> None:
    assert field(_scores(2, 6), _plan(substitutions=cap)) == (total, moves)


def test_a_keeper_is_only_replaced_by_a_keeper() -> None:
    assert field(_scores(1, 12), _plan("bench_order")) == (60.0, [])


@pytest.mark.parametrize(("mode", "comes_on"), [("same_role", 13), ("role_first", 13), ("bench_order", 14)])
def test_who_comes_first_by_the_leagues_rule(mode: Mode, comes_on: int) -> None:
    assert field(_scores(2), _plan(mode, (14, 13))) == (66.0, [(2, comes_on)])


def test_another_role_only_into_an_allowed_formation() -> None:
    """Without his own role, a forward would make 3-3-4, which isn't allowed; a midfielder makes 3-4-3."""
    assert field(_scores(2, 13), _plan("role_first", (15, 14, 13))) == (66.0, [(2, 14)])
    assert field(_scores(2, 13), _plan("role_first", (14, 13), formations=("4-3-3",))) == (60.0, [])


def test_the_formation_moves_with_each_substitution() -> None:
    """4-3-3 becomes 3-4-3 becomes 3-5-2. From the first, the second change would make 4-4-2, not allowed."""
    moves = field(_scores(2, 13, 9), _plan("role_first", (14, 16, 13)))[1]
    assert moves == [(2, 14), (9, 16)]


def test_same_role_never_changes_role() -> None:
    assert field(_scores(2, 13), _plan("same_role", (14, 13))) == (60.0, [])


@pytest.mark.parametrize(
    ("score", "goals"),
    [(65.9, 0), (66.0, 1), (71.9, 1), (72.0, 2), (77.9, 2), (78.0, 3), (84.0, 4), (90.5, 5)],
)
def test_fantasy_goals_past_the_last_threshold(score: float, goals: int) -> None:
    assert fantasy_goals(score, [66.0, 72.0]) == goals


def test_the_last_step_counts_from_the_last_threshold() -> None:
    assert fantasy_goals(85.0, [66.0, 72.0, 77.0]) == 4


def test_no_thresholds_no_fantasy_goals() -> None:
    assert fantasy_goals(90.0, None) == 0
    assert fantasy_goals(90.0, []) == 0


def test_summary_by_hand() -> None:
    """Totals of 1 to 20: 34 fantasy goals, by hand, with thresholds at 5 and 10 and a step of 5 after."""
    result = summarize("3-4-3", [float(total) for total in range(20, 0, -1)], [5.0, 10.0])
    assert result.formation == "3-4-3"
    assert result.mean == pytest.approx(10.5)
    assert (result.low, result.high) == (3.0, 18.0)
    assert result.fantasy_goals == pytest.approx(34 / 20)
    assert [(mark.points, mark.chance) for mark in result.thresholds] == [
        (5.0, 0.8),
        (10.0, 0.55),
        (15.0, 0.3),
        (20.0, 0.05),
        (25.0, 0.0),
        (30.0, 0.0),
    ]


def test_a_total_points_league_has_no_goals_to_show() -> None:
    result = summarize("3-4-3", [66.0, 72.0], None)
    assert (result.fantasy_goals, result.thresholds) == (0.0, [])


def _simulated(formation: str, mean: float, goals: float) -> Simulated:
    return Simulated(formation=formation, mean=mean, low=0.0, high=0.0, fantasy_goals=goals, thresholds=[])


def test_the_formation_by_the_leagues_format() -> None:
    results = [
        _simulated("3-5-2", 70.0, 1.5),
        _simulated("4-3-3", 72.0, 1.4),
        _simulated("3-4-3", 70.0, 1.5),
        _simulated("4-4-2", 71.0, 1.5),
    ]
    head_to_head = LineupRules(format="head_to_head")
    assert [result.formation for result in ranked(results, head_to_head)] == [
        "4-4-2",
        "3-4-3",
        "3-5-2",
        "4-3-3",
    ]
    assert recommended(results, head_to_head).formation == "4-4-2"
    total_points = LineupRules(format="total_points")
    assert [result.formation for result in ranked(results, total_points)] == [
        "4-3-3",
        "4-4-2",
        "3-4-3",
        "3-5-2",
    ]
    assert recommended(results, total_points).formation == "4-3-3"
