"""P3 to P6: the simulation (design C7; R4)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.xy.league import formation_lines
from fantadamus.engine import keepers, outfield
from fantadamus.engine.constants import GOAL_VOTE_LIFT
from fantadamus.engine.lineup import arrange
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import (
    Outfielder,
    SimPlayer,
    draw_rounds,
    fantasy_goals,
    field,
    keeper_player,
    outfield_player,
    plan,
    simulate,
    summarize,
)
from tests.lineup_data import FORMATIONS, full_squad, lineup_rules
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
SQUAD = full_squad()
_THRESHOLDS = st.sampled_from(([66, 72], [66, 72, 77, 81, 85, 89], [60, 70, 75]))


@given(
    rated=st.lists(st.booleans(), min_size=len(SQUAD), max_size=len(SQUAD)),
    formation=st.sampled_from(FORMATIONS),
    mode=st.sampled_from(("same_role", "role_first", "bench_order")),
    cap=st.integers(0, 6),
    vote=st.sampled_from((None, 6.0)),
)
def test_p3_substitutions_keep_the_rules(
    rated: list[bool], formation: str, mode: str, cap: int, vote: float | None
) -> None:
    rules = lineup_rules(substitution_mode=mode, substitutions=cap, no_rating_vote=vote)
    arranged = arrange(SQUAD, formation, rules)
    scores: dict[int, float | None] = {
        player.player_id: 6.0 + player.player_id / 10 if flag else None
        for player, flag in zip(SQUAD, rated, strict=True)
    }
    total, moves = field(scores, plan(arranged, rules))
    role = {player.player_id: player.role for player in SQUAD}
    starters = {player.player_id for player in arranged.starters}
    bench = {player.player_id for player in arranged.bench}
    assert len(moves) <= cap
    assert len({substitute for _, substitute in moves}) == len(moves)
    lines = {"D": 0, "C": 1, "A": 2}
    now = list(formation_lines(formation))
    for out, substitute in moves:
        assert out in starters
        assert scores[out] is None  # a starter with a rating is never replaced
        assert substitute in bench
        assert scores[substitute] is not None  # a substitute has a rating
        assert (role[out] == "P") == (role[substitute] == "P")  # a keeper only for a keeper
        if mode == "same_role":
            assert role[out] == role[substitute]
        if role[out] != "P":
            now[lines[role[out]]] -= 1
            now[lines[role[substitute]]] += 1
            if role[out] != role[substitute]:
                assert tuple(now) in {formation_lines(allowed) for allowed in FORMATIONS}
    kept = sum(score for starter in starters if (score := scores[starter]) is not None)
    subs = sum(score for _, substitute in moves if (score := scores[substitute]) is not None)
    unfilled = sum(scores[starter] is None for starter in starters) - len(moves)
    assert total == pytest.approx(kept + subs + unfilled * (vote or 0.0))


_ROUNDS = 3000


@given(
    team_xg=st.sampled_from((0.6, 1.4, 2.5)),
    goals=st.sampled_from((0, 5)),
    taker=st.booleans(),
    cards=st.sampled_from((0, 4)),
    mantra=st.sampled_from(("Pc", "Dc")),
    bonus=st.sampled_from((3.0, 4.5)),
)
def test_p4_means_match_the_models(
    team_xg: float, goals: int, taker: bool, cards: int, mantra: str, bonus: float
) -> None:
    """Certain to start, a player's mean over many rounds is the model's E_start: the simulation adds spread,
    not value. A 5-sigma tolerance, on a fixed seed."""
    scoring = CLASSIC.model_copy(update={"goal": bonus})
    inputs = outfield_inputs(
        "A" if mantra == "Pc" else "D",
        mantra,
        appearances=8,
        rated_appearances=8,
        average_rating=6.3,
        goals=goals,
        yellow_cards=cards,
        penalty_taker=taker,
        team_xg=team_xg,
        p_start=1.0,
        p_cameo=0.0,
    )
    value = outfield.value(inputs, scoring)
    player = outfield_player(1, inputs, value, scoring, (0, 0))
    scored = [
        score
        for scores, _ in draw_rounds([player], [(team_xg, 1.0)], rounds=_ROUNDS, seed=11)
        if (score := scores[1]) is not None
    ]
    assert len(scored) == _ROUNDS
    assert sum(scored) / _ROUNDS == pytest.approx(value.e_start, abs=0.2)


@given(opponent_xg=st.sampled_from((0.5, 1.1, 2.0)), rating=st.sampled_from((5.8, 6.4)))
def test_p4_keepers_match_their_model(opponent_xg: float, rating: float) -> None:
    inputs = keeper_inputs(average_rating=rating, opponent_xg=opponent_xg, p_start=1.0)
    value = keepers.value(inputs, CLASSIC)
    player = keeper_player(1, inputs, value, CLASSIC, (0, 0))
    drawn = list(draw_rounds([player], [(1.0, opponent_xg)], rounds=_ROUNDS, seed=13))
    scored = [score for scores, _ in drawn if (score := scores[1]) is not None]
    assert sum(scored) / _ROUNDS == pytest.approx(value.e_start, abs=0.2)
    clean = sum(goals[0][1] == 0 for _, goals in drawn) / _ROUNDS
    assert clean == pytest.approx(math.exp(-opponent_xg), abs=0.05)


@given(
    scores=st.lists(st.floats(min_value=20, max_value=130, allow_nan=False), min_size=2, max_size=30),
    thresholds=_THRESHOLDS,
)
def test_p5_thresholds_never_fall(scores: list[float], thresholds: list[float]) -> None:
    ordered = sorted(scores)
    goals = [fantasy_goals(score, thresholds) for score in ordered]
    assert goals == sorted(goals)
    reached = summarize("3-4-3", scores, thresholds).thresholds
    chances = [mark.chance for mark in reached]
    assert chances == sorted(chances, reverse=True)
    points = [mark.points for mark in reached]
    assert points == sorted(points)
    assert len(set(points)) == len(points)


def _players() -> list[SimPlayer]:
    inputs = outfield_inputs("A", "Pc", appearances=8, goals=3, team_xg=1.4, p_start=0.8, p_cameo=0.15)
    keeper = keeper_inputs(opponent_xg=1.4, p_start=0.9)
    return [
        outfield_player(1, inputs, outfield.value(inputs, CLASSIC), CLASSIC, (0, 0)),
        keeper_player(2, keeper, keepers.value(keeper, CLASSIC), CLASSIC, (0, 1)),
    ]


@given(seed=st.integers(0, 3))
def test_p6_same_inputs_same_results(seed: int) -> None:
    players = _players()
    first = list(draw_rounds(players, [(1.4, 1.4)], rounds=50, seed=seed))
    second = list(draw_rounds(players, [(1.4, 1.4)], rounds=50, seed=seed))
    assert first == second


def test_p6_simulate_is_repeatable() -> None:
    rules = lineup_rules()
    arrangements = [arrange(SQUAD, formation, rules) for formation in FORMATIONS[:2]]
    players: list[SimPlayer] = [
        outfield_player(
            candidate.player_id,
            inputs := outfield_inputs("A", "Pc", p_start=candidate.p_start, p_cameo=candidate.p_cameo),
            outfield.value(inputs, CLASSIC),
            CLASSIC,
            (0, 0),
        )
        for candidate in SQUAD
    ]
    results = simulate(players, [(1.4, 1.2)], arrangements, rules, rounds=100)
    assert results == simulate(players, [(1.4, 1.2)], arrangements, rules, rounds=100)
    assert all(result.thresholds for result in results)  # each carries the league's thresholds


def test_p2_a_clubs_keepers_never_start_together() -> None:
    """The backup plays exactly when the starter doesn't: 92% and 12% add up to more than a place, so they
    share it."""
    scoring = CLASSIC
    starter_in = keeper_inputs(name="Titolare", club="alfa", opponent_xg=1.0, p_start=0.92)
    backup_in = keeper_inputs(name="Riserva", club="alfa", opponent_xg=1.0, p_start=0.12)
    other_in = keeper_inputs(name="Altro", club="beta", opponent_xg=1.0, p_start=0.92)
    players: list[SimPlayer] = [
        keeper_player(1, starter_in, keepers.value(starter_in, scoring), scoring, (0, 1)),
        keeper_player(2, backup_in, keepers.value(backup_in, scoring), scoring, (0, 1)),
        keeper_player(3, other_in, keepers.value(other_in, scoring), scoring, (1, 1)),
    ]
    rounds = list(draw_rounds(players, [(1.0, 1.0), (1.0, 1.0)], rounds=5000, seed=17))
    starter = sum(scores[1] is not None for scores, _ in rounds) / 5000
    backup = sum(scores[2] is not None for scores, _ in rounds) / 5000
    both = sum(scores[1] is not None and scores[2] is not None for scores, _ in rounds)
    other = sum(scores[3] is not None for scores, _ in rounds) / 5000
    assert both == 0
    assert starter + backup == pytest.approx(1.0)  # someone always plays: the two chances cover the place
    assert starter == pytest.approx(0.92 / 1.04, abs=0.02)
    assert other == pytest.approx(0.92, abs=0.02)  # another club's keeper keeps his own chance


def _taker(player_id: int, *, per_goal: float, per_assist: float, scoring: Scoring) -> Outfielder:
    return Outfielder(
        player_id=player_id,
        side=(0, 0),
        p_start=1.0,
        p_cameo=0.0,
        lowered_vote=0.0,
        per_goal=per_goal,
        per_assist=per_assist,
        cameo_per_goal=0.0,
        penalties=0.0,
        cameo_penalties=0.0,
        p_yellow=0.0,
        priced_cameo=False,
        scoring=scoring,
    )


def test_each_goal_goes_to_at_most_one_player() -> None:
    """Two players who between them are sure of every goal: their goals add up to the team's, exactly. A bonus
    far above the noise lets the score show how many each got."""
    big = Scoring(goal=100, penalty_scored=0, assist=0, yellow=0, clean_sheet=0, goal_conceded=0)
    players: list[SimPlayer] = [
        _taker(1, per_goal=0.5, per_assist=0.0, scoring=big),
        _taker(2, per_goal=0.5, per_assist=0.0, scoring=big),
    ]
    for scores, goals in draw_rounds(players, [(2.0, 1.0)], rounds=500, seed=19):
        total = sum(score for score in scores.values() if score is not None)
        assert round(total / (100 + GOAL_VOTE_LIFT)) == goals[0][0]


def test_each_assist_goes_to_at_most_one_player() -> None:
    big = Scoring(goal=0, penalty_scored=0, assist=100, yellow=0, clean_sheet=0, goal_conceded=0)
    players: list[SimPlayer] = [
        _taker(1, per_goal=0.0, per_assist=0.5, scoring=big),
        _taker(2, per_goal=0.0, per_assist=0.5, scoring=big),
    ]
    for scores, goals in draw_rounds(players, [(2.0, 1.0)], rounds=500, seed=23):
        total = sum(score for score in scores.values() if score is not None)
        assert round(total / 100) == goals[0][0]


def test_a_player_with_no_match_gets_no_rating() -> None:
    """His club has no match in the round (R2.3)."""
    inputs = outfield_inputs("A", "Pc", p_start=0.0, p_cameo=0.0)
    keeper_in = keeper_inputs(p_start=0.0)
    players: list[SimPlayer] = [
        outfield_player(1, inputs, outfield.value(inputs, CLASSIC), CLASSIC, None),
        keeper_player(2, keeper_in, keepers.value(keeper_in, CLASSIC), CLASSIC, None),
    ]
    for scores, _ in draw_rounds(players, [], rounds=20, seed=29):
        assert scores == {1: None, 2: None}
