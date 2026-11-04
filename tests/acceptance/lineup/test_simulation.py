"""AT-2 to AT-4: method §A9 test 5, the league's substitution rules and its thresholds (R4)."""

from __future__ import annotations

import statistics

import pytest

from fantadamus.contracts.types import Role
from fantadamus.engine import keepers, outfield
from fantadamus.engine.lineup import arrange
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import (
    SimPlayer,
    draw_rounds,
    fantasy_goals,
    field,
    keeper_player,
    keeper_points,
    outfield_player,
    outfield_points,
    plan,
    simulate,
    summarize,
)
from tests.lineup_data import candidate, full_squad, lineup_rules
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)


def test_at2_a_goal_against_your_own_keeper() -> None:
    """§A9 test 5: about +2.5, or +1.5 if it breaks the clean sheet."""
    striker_inputs = outfield_inputs("A", "Pc", team_xg=1.4, p_start=1.0, p_cameo=0.0)
    striker = outfield_player(1, striker_inputs, outfield.value(striker_inputs, CLASSIC), CLASSIC, (0, 0))
    keeper_in = keeper_inputs(opponent_xg=1.4, p_start=1.0)
    keeper = keeper_player(2, keeper_in, keepers.value(keeper_in, CLASSIC), CLASSIC, (0, 1))

    def together(goals: int, conceded: int) -> float:
        return outfield_points(striker, 0.0, goals, 0, 0, False) + keeper_points(keeper, 0.0, conceded)

    assert together(1, 2) - together(0, 1) == pytest.approx(2.5)  # no clean sheet to lose
    assert together(1, 1) - together(0, 0) == pytest.approx(1.5)  # it breaks the clean sheet


def _team(*, linked: bool) -> tuple[list[SimPlayer], list[tuple[float, float]]]:
    """A keeper and three forwards who face him, or the same chances in another match."""
    keeper_in = keeper_inputs(opponent_xg=2.0, p_start=1.0)
    players: list[SimPlayer] = [
        keeper_player(1, keeper_in, keepers.value(keeper_in, CLASSIC), CLASSIC, (0, 1))
    ]
    side = (0, 0) if linked else (1, 0)
    for player_id in (2, 3, 4):
        inputs = outfield_inputs("A", "Pc", team_xg=2.0, p_start=1.0, p_cameo=0.0)
        players.append(outfield_player(player_id, inputs, outfield.value(inputs, CLASSIC), CLASSIC, side))
    return players, [(2.0, 1.0), (2.0, 1.0)]


def test_at2_the_link_narrows_the_spread_and_raises_the_first_threshold() -> None:
    """The same chances, with and without the link: the mean stays, the spread narrows, and a threshold just
    below the mean is reached more often (§A7)."""
    spreads = {}
    means = {}
    reached = {}
    for linked in (True, False):
        players, matches = _team(linked=linked)
        totals = [
            sum(score for score in scores.values() if score is not None)
            for scores, _ in draw_rounds(players, matches, rounds=20_000, seed=5)
        ]
        spreads[linked] = statistics.pstdev(totals)
        means[linked] = statistics.fmean(totals)
        reached[linked] = sum(total >= means[linked] - 1.0 for total in totals) / len(totals)
    assert means[True] == pytest.approx(means[False], abs=0.1)
    assert spreads[True] < spreads[False] - 0.1
    assert reached[True] > reached[False]


SQUAD = full_squad()
BY_ROLE: dict[Role, list[int]] = {
    role: [player.player_id for player in SQUAD if player.role == role] for role in ("P", "D", "C", "A")
}


def _scores(*missing: int) -> dict[int, float | None]:
    return {player.player_id: None if player.player_id in missing else 6.0 for player in SQUAD}


def _moves(formation: str, *missing: int, **rules: object) -> list[tuple[int, int]]:
    settings = lineup_rules(**rules)
    return field(_scores(*missing), plan(arrange(SQUAD, formation, settings), settings))[1]


D1, D2, D3, D4, D5 = BY_ROLE["D"][:5]
C1, C5 = BY_ROLE["C"][0], BY_ROLE["C"][4]
A1, A4 = BY_ROLE["A"][0], BY_ROLE["A"][3]
K1, K2, K3 = BY_ROLE["P"]


def test_at3_role_for_role_first_bench_player_with_a_rating() -> None:
    assert _moves("3-4-3", D1) == [(D1, D4)]
    assert _moves("3-4-3", D1, D4) == [(D1, D5)]  # the first on the bench has no rating either


def test_at3_the_cap() -> None:
    assert _moves("3-4-3", K1, D1, A1, substitutions=2) == [(K1, K2), (D1, D4)]  # keeper, defenders, then on
    assert _moves("3-4-3", D1, substitutions=0) == []


def test_at3_a_cameo_with_a_rating_blocks_his_substitute() -> None:
    """A rating is a rating: whoever has one stays, however he got it (§A2)."""
    only_a_cameo = _scores()
    only_a_cameo[D1] = 5.5
    settings = lineup_rules()
    total, moves = field(only_a_cameo, plan(arrange(SQUAD, "3-4-3", settings), settings))
    assert moves == []
    assert total == pytest.approx(10 * 6.0 + 5.5)


@pytest.mark.parametrize("taker", [False, True])
def test_at3_a_cameo_can_end_with_no_rating_and_then_is_replaced(taker: bool) -> None:
    """A forward's cameo gets a rating 60% of the time without a goal (R9.7): both happen, and the mean is the
    model's, with a taker's penalties in it."""
    inputs = outfield_inputs("A", "Pc", team_xg=1.4, penalty_taker=taker, p_start=0.0, p_cameo=1.0)
    value = outfield.value(inputs, CLASSIC)
    player = outfield_player(1, inputs, value, CLASSIC, (0, 0))
    scores = [scores[1] for scores, _ in draw_rounds([player], [(1.4, 1.0)], rounds=40_000, seed=3)]
    rated = [score for score in scores if score is not None]
    assert 0 < len(rated) < len(scores)
    assert sum(rated) / len(scores) == pytest.approx(value.e_cameo, abs=0.05)


def test_at3_a_defenders_flat_cameo_always_counts() -> None:
    inputs = outfield_inputs("D", "Dc", team_xg=1.4, p_start=0.0, p_cameo=1.0)
    player = outfield_player(1, inputs, outfield.value(inputs, CLASSIC), CLASSIC, (0, 0))
    assert {scores[1] for scores, _ in draw_rounds([player], [(1.4, 1.0)], rounds=50, seed=3)} == {5.5}


def test_at3_a_keeper_only_for_a_keeper() -> None:
    assert _moves("3-4-3", K1) == [(K1, K2)]
    assert _moves("3-4-3", K1, K2) == [(K1, K3)]
    assert _moves("3-4-3", K1, K2, K3) == []
    # An outfield player never goes in goal, nor a keeper outfield.
    assert _moves("3-4-3", K1, K2, K3, substitution_mode="bench_order") == []
    assert _moves("3-4-3", D1, substitution_mode="bench_order")[0][1] not in (K2, K3)


ALLOWED = ["4-3-3", "3-4-3"]


def test_at3_a_formation_change_only_into_an_allowed_formation() -> None:
    """From 4-3-3, a missing defender may become a midfielder (3-4-3) but not a forward (3-3-4)."""
    all_bench_defenders = BY_ROLE["D"][4:]
    settings = {"substitution_mode": "role_first", "formations": ALLOWED}
    [(out, substitute)] = _moves("4-3-3", D1, *all_bench_defenders, **settings)
    assert out == D1
    assert substitute in BY_ROLE["C"]
    only_forwards = [*BY_ROLE["C"][3:], *all_bench_defenders]
    assert _moves("4-3-3", D1, *only_forwards, **settings) == []  # 3-3-4 isn't allowed
    assert _moves("4-3-3", D1, *all_bench_defenders, substitution_mode="same_role", formations=ALLOWED) == []


def test_at3_role_first_prefers_his_role_and_bench_order_does_not() -> None:
    """The bench's order runs by key across roles: here its first is a midfielder."""
    squad = [
        candidate(1, "P"),
        *(candidate(10 + n, "D", key=6.0 - n / 10) for n in range(5)),
        *(candidate(20 + n, "C", key=7.0 - n / 10) for n in range(5)),
        *(candidate(30 + n, "A", key=6.0 - n / 10) for n in range(4)),
    ]
    scores: dict[int, float | None] = {player.player_id: 6.0 for player in squad}
    scores[10] = None
    for mode, expected in (("same_role", 14), ("role_first", 14), ("bench_order", 23)):
        settings = lineup_rules(substitution_mode=mode, formations=["4-3-3", "3-4-3"])
        _, moves = field(scores, plan(arrange(squad, "4-3-3", settings), settings))
        assert moves == [(10, expected)]


def test_at3_the_leagues_vote_for_a_place_left_empty() -> None:
    for vote, expected in ((None, 10 * 6.0), (4.0, 10 * 6.0 + 4.0)):
        settings = lineup_rules(no_rating_vote=vote, substitutions=0)
        total, _ = field(_scores(D1), plan(arrange(SQUAD, "3-4-3", settings), settings))
        assert total == pytest.approx(expected)


@pytest.mark.parametrize(
    ("score", "goals"),
    [
        (0, 0),
        (65.5, 0),
        (66, 1),
        (71.5, 1),
        (72, 2),
        (76.5, 2),
        (77, 3),
        (85, 5),
        (89, 6),
        (92.5, 6),
        (93, 7),
        (101, 9),
    ],
)
def test_at4_the_preset_table(score: float, goals: int) -> None:
    assert fantasy_goals(score, [66, 72, 77, 81, 85, 89]) == goals


@pytest.mark.parametrize(
    ("score", "goals"), [(65.5, 0), (66, 1), (71.5, 1), (72, 2), (77.5, 2), (78, 3), (84, 4), (90, 5)]
)
def test_at4_the_fixed_step(score: float, goals: int) -> None:
    assert fantasy_goals(score, [66, 72]) == goals


def test_at4_a_total_points_league_has_no_fantasy_goals() -> None:
    assert fantasy_goals(90, None) == 0
    result = summarize("3-4-3", [60.0, 70.0], None)
    assert result.fantasy_goals == 0
    assert result.thresholds == []
    assert result.mean == 65


def test_at4_by_hand_from_known_scores() -> None:
    totals = [60.0, 62.0, 65.0, 66.0, 68.0, 70.0, 72.0, 74.0, 78.0, 90.0]
    result = summarize("3-4-3", totals, [66, 72])
    assert result.mean == pytest.approx(70.5)
    assert (result.low, result.high) == (62.0, 78.0)  # eight rounds out of ten fall from one to the other
    assert result.fantasy_goals == pytest.approx((0 + 0 + 0 + 1 + 1 + 1 + 2 + 2 + 3 + 5) / 10)
    assert {mark.points: mark.chance for mark in result.thresholds} == {
        66: 0.7,
        72: 0.4,
        78: 0.2,
        84: 0.1,
        90: 0.1,
        96: 0.0,
    }


def test_at4_the_chance_of_a_threshold_by_hand() -> None:
    """Eleven certain starters at an expected vote of 6.1, with no bonuses to win or lose: only the noise
    moves the total of 67.1, with a standard deviation of sqrt(10 x 0.6^2 + 0.75^2) = 2.04. So 66 is
    reached Phi(1.1 / 2.04) = 70.5% of the time, and 72 is reached 1 - Phi(4.9 / 2.04) = 0.8% of the time."""
    no_bonus = Scoring(goal=0, penalty_scored=0, assist=0, yellow=0, clean_sheet=0, goal_conceded=0)
    keeper_in = keeper_inputs(
        rated_appearances=9,
        average_rating=6.2,
        goals_conceded=0,
        league_goals_per_match=0.0,
        opponent_xg=0.0,
        p_start=1.0,
    )
    players: list[SimPlayer] = [
        keeper_player(1, keeper_in, keepers.value(keeper_in, no_bonus), no_bonus, (0, 1))
    ]
    candidates = [candidate(1, "P", p_start=1.0, p_cameo=0.0)]
    lines: list[tuple[int, Role, str]] = [
        *((10 + n, "D", "Dc") for n in range(3)),
        *((20 + n, "C", "C") for n in range(4)),
        *((30 + n, "A", "Pc") for n in range(3)),
    ]
    for player_id, role, mantra in lines:
        inputs = outfield_inputs(
            role,
            mantra,
            rated_appearances=10,
            average_rating=6.2,
            team_xg=0.0,
            p_win=0.0,
            p_loss=0.0,
            p_start=1.0,
            p_cameo=0.0,
        )
        players.append(outfield_player(player_id, inputs, outfield.value(inputs, no_bonus), no_bonus, (0, 0)))
        candidates.append(candidate(player_id, role, p_start=1.0, p_cameo=0.0))
    settings = lineup_rules(formations=["3-4-3"], thresholds=[66, 72])
    arranged = arrange(candidates, "3-4-3", settings)
    [result] = simulate(players, [(0.0, 0.0)], [arranged], settings)
    assert result.mean == pytest.approx(67.1, abs=0.1)
    chances = {mark.points: mark.chance for mark in result.thresholds}
    assert chances[66] == pytest.approx(0.705, abs=0.02)
    assert chances[72] == pytest.approx(0.008, abs=0.005)
