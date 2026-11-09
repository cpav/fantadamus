"""mvp-review task 5.1: the review's lineups run through the real simulation and the real score, as the tool
will run them (design C3, C6; R3.2)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

import pytest

from fantadamus.domains.review import Events, RealScore, Round, real_score, review_choices
from fantadamus.engine import keepers, outfield
from fantadamus.engine.lineup import Arrangement
from fantadamus.engine.rank import Scoring
from fantadamus.engine.simulate import SimPlayer, Simulated, keeper_player, outfield_player, plan, simulate
from fantadamus.league.rules import CLASSIC, READY_MADE
from tests.review_choices import ADVICE, RULES, SQUAD
from tests.roles_data import keeper as keeper_inputs
from tests.roles_data import outfield as outfield_inputs

SCORING = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
CAPTAIN = next(entry.rule for entry in READY_MADE if entry.rule.name == "captain")
LEAGUE = CLASSIC.model_copy(update={"lineup": RULES, "formula_rules": [CAPTAIN]})
QUIET = Events(0, 0, 0, 0, 0, 0, 0, 0, 0)


def _players() -> list[SimPlayer]:
    found: list[SimPlayer] = []
    for candidate in SQUAD:
        if candidate.role == "P":
            inputs = keeper_inputs(name=candidate.name, club=candidate.club, p_start=1.0)
            found.append(
                keeper_player(candidate.player_id, inputs, keepers.value(inputs, SCORING), SCORING, None)
            )
        else:
            fielder = outfield_inputs(candidate.role, None, p_start=1.0, p_cameo=0.0)
            found.append(
                outfield_player(candidate.player_id, fielder, outfield.value(fielder, SCORING), SCORING, None)
            )
    return found


PLAYERS = _players()
ROUNDS = {player.player_id: Round(6.0 + (player.player_id == 7) * 1.5, QUIET) for player in SQUAD}


def price(arrangements: Sequence[Arrangement]) -> list[Simulated]:
    return simulate(PLAYERS, [], arrangements, RULES, formula_rules=[CAPTAIN], rounds=200)


def score(arranged: Arrangement, captain: int | None, vice: int | None) -> RealScore:
    return real_score(ROUNDS, plan(arranged, RULES), LEAGUE, captain=captain, vice=vice)


def test_following_the_advice_on_the_engine() -> None:
    reviewed = review_choices(ADVICE, ADVICE, SQUAD, RULES, price=price, score=score)
    assert reviewed.choices == []
    assert (reviewed.total_cost, reviewed.total_gain) == (0.0, 0.0)
    assert (reviewed.advice.captain, reviewed.advice.vice) == (20, 12)  # the advice's named pair


def test_a_swap_and_a_captain_on_the_engine() -> None:
    fielded = dataclasses.replace(
        ADVICE,
        starters=tuple(7 if player == 6 else player for player in ADVICE.starters),
        bench=tuple(6 if player == 7 else player for player in ADVICE.bench),
        captain=21,
        vice=20,
    )
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=price, score=score)
    assert [choice.kind for choice in reviewed.choices] == ["player", "captain"]
    player, captain = reviewed.choices
    assert player.real_gain == 1.5  # his 7.5 for a 6
    assert captain.real_gain == 0.0  # every captain was rated 6: nothing either way
    assert (reviewed.fielded.captain, reviewed.fielded.vice) == (21, 20)
    assert reviewed.total_cost == pytest.approx(reviewed.advice.mean - reviewed.fielded.mean)
    assert reviewed.total_gain == 1.5


def test_the_vice_covers_in_the_real_score() -> None:
    """His captain had no rating, so the vice's 8.5 is worth +2.5."""
    rounds = {**ROUNDS, 21: Round(None, QUIET), 20: Round(8.5, QUIET)}

    def score_round(arranged: Arrangement, captain: int | None, vice: int | None) -> RealScore:
        return real_score(rounds, plan(arranged, RULES), LEAGUE, captain=captain, vice=vice)

    fielded = dataclasses.replace(ADVICE, captain=21, vice=20)
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=price, score=score_round)
    assert reviewed.fielded_real.rules == {"captain": 2.5}
