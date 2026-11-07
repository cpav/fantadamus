"""mvp-rules task 1: one table of events (design C1, C2; R1.1, R1.2, R1.6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import EventRow, LeagueRules
from fantadamus.engine import keepers, outfield
from fantadamus.engine.points import event_points, rare_points
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import (
    draw_rounds,
    keeper_player,
    keeper_points,
    outfield_player,
    outfield_points,
)
from fantadamus.lake.decision_log import Decision
from fantadamus.league.rules import CLASSIC, scoring_for
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as forward

ROLES: tuple[Role, ...] = ("P", "D", "C", "A")


def _rules(*rows: EventRow) -> LeagueRules:
    return LeagueRules(events=list(rows))


def test_an_event_not_in_the_table_isnt_scored() -> None:
    scoring = scoring_for(_rules(EventRow(event="goal", points=3.0, roles=list(ROLES))), "A")
    assert scoring.goal == 3
    assert (scoring.assist, scoring.yellow, scoring.red, scoring.penalty_missed, scoring.own_goal) == (
        0,
        0,
        0,
        0,
        0,
    )


def test_a_row_applies_only_to_its_roles() -> None:
    rules = _rules(
        EventRow(event="goal", points=4.0, roles=["D"]),
        EventRow(event="goal", points=3.0, roles=["P", "C", "A"]),
        EventRow(event="clean_sheet", points=1.0, roles=["P", "D"]),
    )
    assert scoring_for(rules, "D").goal == 4
    assert scoring_for(rules, "A").goal == 3
    assert scoring_for(rules, "D").clean_sheet == 1
    assert scoring_for(rules, "C").clean_sheet == 0


def test_classic_is_an_ordinary_table() -> None:
    """No special path: its values reach each role through the same rows."""
    keeper, forward = scoring_for(CLASSIC, "P"), scoring_for(CLASSIC, "A")
    assert (forward.goal, forward.assist, forward.penalty_scored, forward.penalty_missed) == (3, 1, 3, -3)
    assert (forward.yellow, forward.red, forward.own_goal) == (-0.5, -1, -2)
    assert (forward.clean_sheet, forward.goal_conceded, forward.penalty_saved) == (0, 0, 0)
    assert (keeper.clean_sheet, keeper.goal_conceded, keeper.penalty_saved) == (1, -1, 3)


def test_a_second_row_for_one_event_and_role_is_refused() -> None:
    with pytest.raises(ValidationError, match="goal is set twice for D"):
        _rules(
            EventRow(event="goal", points=3.0, roles=["D", "A"]),
            EventRow(event="goal", points=4.0, roles=["D"]),
        )


@pytest.mark.parametrize(
    ("event", "points", "says"),
    [
        ("goal", -1.0, "goal is a bonus"),
        ("yellow_card", 0.5, "yellow_card is a malus"),
        ("clean_sheet", 11.0, "less than or equal to 10"),
        ("red_card", -11.0, "greater than or equal to -10"),
    ],
)
def test_a_value_of_the_wrong_sign_or_size_is_refused(event: str, points: float, says: str) -> None:
    with pytest.raises(ValidationError, match=says):
        LeagueRules.model_validate({"events": [{"event": event, "points": points, "roles": ["D"]}]})


def test_a_keepers_save_on_another_role_is_refused() -> None:
    with pytest.raises(ValidationError, match="penalty_saved is a keeper's"):
        _rules(EventRow(event="penalty_saved", points=3.0, roles=["P", "D"]))


def test_a_table_needs_at_least_one_row() -> None:
    with pytest.raises(ValidationError):
        LeagueRules(events=[])


EARLIER = {
    "goal": {"keeper": 5.0, "defender": 4.5, "midfielder": 4.0, "forward": 3.0},
    "assist": 1.0,
    "penalty_scored": 2.5,
    "penalty_missed": -2.5,
    "penalty_saved": 3.0,
    "own_goal": -2.0,
    "yellow_card": -0.5,
    "red_card": -1.0,
    "goal_conceded": -1.0,
    "clean_sheet": 1.0,
}


def test_rules_in_the_earlier_form_read_as_the_same_table() -> None:
    rules = LeagueRules.model_validate(EARLIER | {"lineup": {"bench_size": 12}})
    assert rules.lineup is not None
    assert rules.lineup.bench_size == 12
    assert [scoring_for(rules, role).goal for role in ROLES] == [5, 4.5, 4, 3]
    assert scoring_for(rules, "A").penalty_missed == -2.5
    assert scoring_for(rules, "D").clean_sheet == 0  # in that form it was only ever a keeper's
    assert scoring_for(rules, "P").clean_sheet == 1


def test_an_old_log_line_still_reads() -> None:
    """Rules live inside every line of the decision log: if they stopped parsing, those lines go unread."""
    line = {
        "kind": "lineup",
        "as_of": "2026-11-06T19:19:00Z",
        "logged_at": "2026-11-06T19:19:00Z",
        "user": "user-1",
        "round": 11,
        "players": [],
        "rules": {"user": "user-1", "saved_at": "2026-11-06T14:11:00Z", "rules": EARLIER},
        "content_hashes": [],
    }
    decision = Decision.model_validate(line)
    assert scoring_for(decision.rules.rules, "A").goal == 3


def test_both_forms_at_once_are_refused() -> None:
    with pytest.raises(ValidationError, match="either"):
        LeagueRules.model_validate(EARLIER | {"events": [{"event": "goal", "points": 3.0, "roles": ["A"]}]})


def test_a_cameos_goal_follows_the_league() -> None:
    """9.8 was 6.8 plus a +3 goal: a league's own goal value has to reach it."""
    scored = outfield.p_scores(0.2)
    for goal_value in (3.0, 4.5):
        rated, worth = outfield.cameo_rating(0.2, goal_value)
        assert rated == pytest.approx(scored + (1 - scored) * 0.6)
        assert worth == pytest.approx((scored * (6.8 + goal_value) + (1 - scored) * 0.6 * 5.75) / rated)


def test_a_cameos_goal_follows_the_league_in_the_rounds() -> None:
    """The simulation prices it as the model does: 4.5 for a goal makes 11.3, not 9.8."""
    scoring = Scoring(goal=4.5, penalty_scored=4.5, assist=1, yellow=-0.5, clean_sheet=0, goal_conceded=0)
    inputs = forward("A", "Pc", penalty_share=1.0, p_start=0.0, p_cameo=1.0)
    player = outfield_player(1, inputs, outfield.value(inputs, scoring), scoring, (0, 0))
    seen = {
        score
        for scores, _ in draw_rounds([player], [(2.0, 1.0)], rounds=2000, seed=3)
        if (score := scores[1]) is not None
    }
    assert sorted(seen) == pytest.approx([5.75, 6.8 + 4.5])


def test_a_keepers_rare_events_reach_the_rounds() -> None:
    """Exactly, with no noise: a saved penalty is too small for a simulated mean to show."""
    rows = [EventRow(event="penalty_saved", points=3.0, roles=["P"])]
    with_saves = scoring_for(LeagueRules(events=rows), "P")
    inputs = keeper_inputs(p_start=1.0)
    none = Scoring(goal=0, penalty_scored=0, assist=0, yellow=0, clean_sheet=0, goal_conceded=0)
    saves = keeper_player(1, inputs, keepers.value(inputs, with_saves), with_saves, (0, 0))
    plain = keeper_player(1, inputs, keepers.value(inputs, none), none, (0, 0))
    gained = keeper_points(saves, 0.0, 1) - keeper_points(plain, 0.0, 1)
    assert gained == pytest.approx(3.0 * 0.15 * (1 - 0.78) * 0.80)


def test_an_outfielders_rare_events_reach_the_rounds() -> None:
    rows = [EventRow(event="penalty_missed", points=-3.0, roles=["A"])]
    with_misses = scoring_for(LeagueRules(events=rows), "A")
    inputs = forward("A", "Pc", penalty_share=1.0, p_start=1.0, p_cameo=0.0)
    none = Scoring(goal=0, penalty_scored=0, assist=0, yellow=0, clean_sheet=0, goal_conceded=0)
    misses = outfield_player(1, inputs, outfield.value(inputs, with_misses), with_misses, (0, 0))
    plain = outfield_player(1, inputs, outfield.value(inputs, none), none, (0, 0))
    lost = outfield_points(plain, 0.0, 0, 0, 0, False) - outfield_points(misses, 0.0, 0, 0, 0, False)
    assert lost == pytest.approx(3.0 * 0.15 * (1 - 0.78) * 0.85)


def test_event_points_by_hand() -> None:
    scoring = Scoring(goal=3, penalty_scored=2.5, assist=1, yellow=-0.5, clean_sheet=2, goal_conceded=-1)
    counted = event_points(scoring, goals=2, penalties=1, assists=1, yellows=1, clean_sheets=1, conceded=1)
    assert counted == pytest.approx(6 + 2.5 + 1 - 0.5 + 2 - 1)
    assert event_points(scoring) == 0


def test_rare_points_by_hand() -> None:
    scoring = Scoring(
        goal=0,
        penalty_scored=0,
        assist=0,
        yellow=0,
        clean_sheet=0,
        goal_conceded=0,
        penalty_missed=-3,
        penalty_saved=3,
        own_goal=-2,
        red=-1,
    )
    steady = -1 * 0.005 - 2 * 0.005  # a defender's red cards and own goals
    assert rare_points(scoring, "D") == pytest.approx(steady)
    assert rare_points(scoring, "D", penalties_missed=0.1, penalties_saved=0.2) == pytest.approx(
        steady - 0.3 + 0.6
    )


def test_a_clean_sheet_counts_only_with_no_goals_against() -> None:
    scoring = Scoring(goal=0, penalty_scored=0, assist=0, yellow=0, clean_sheet=2, goal_conceded=0)
    inputs = forward("D", "Dc", opponent_xg=1.0, p_start=1.0, p_cameo=0.0)
    player = outfield_player(1, inputs, outfield.value(inputs, scoring), scoring, (0, 0))
    untouched = outfield_points(player, 0.0, 0, 0, 0, False)
    assert outfield_points(player, 0.0, 0, 0, 0, False, 0) == pytest.approx(untouched + 2)
    assert outfield_points(player, 0.0, 0, 0, 0, False, 1) == pytest.approx(untouched)
