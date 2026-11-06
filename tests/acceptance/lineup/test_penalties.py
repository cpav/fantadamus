"""AT-17: a taker's penalties count once: in his penalty term, and not in his goal share too (R8.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.engine import outfield
from fantadamus.engine.rank import Scoring
from tests.lineup_harness import a_round, rows
from tests.roles_data import outfield as outfield_inputs

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)


def _forward(**changes: Any) -> outfield.OutfieldInputs:
    return outfield_inputs("A", "Pc", appearances=10, rated_appearances=10, average_rating=6.5, **changes)


def test_at17_a_share_counts_open_play_goals() -> None:
    """A centre-forward's prior is 0.30 at a weight of 15, and his club scores 1.5 a match over his 10."""
    value = outfield.value(_forward(goals=5, penalties_scored=3, penalty_share=1.0), CLASSIC)
    assert value.goal_share == pytest.approx((0.30 * 15 + 2) / (15 + 15))


def test_at17_the_same_open_play_goals_the_same_share() -> None:
    taker = outfield.value(_forward(goals=5, penalties_scored=3, penalty_share=1.0), CLASSIC)
    open_play = outfield.value(_forward(goals=2, penalties_scored=0, penalty_share=1.0), CLASSIC)
    assert taker.goal_share == pytest.approx(open_play.goal_share)
    assert taker.p_scores == pytest.approx(open_play.p_scores)
    assert taker.key == pytest.approx(open_play.key)


def test_at17_a_share_never_goes_below_the_prior() -> None:
    """A profile could give penalties without goals: it can't make a negative count."""
    odd = outfield.value(_forward(goals=1, penalties_scored=3), CLASSIC)
    assert odd.goal_share == pytest.approx(0.30 * 15 / (15 + 15))


@pytest.mark.anyio
async def test_at17_the_tools_pass_the_penalties_through(tmp_path: Path) -> None:
    """The same figures, but with his goals from the spot, are worth less."""

    async def worth(folder: str, **figures: Any) -> float:
        async with a_round(tmp_path / folder, players=rows(Beta_Nove=figures)) as here:
            lineup = (await here.ask())["lineup"]
        return float(
            next(
                player["value"]
                for player in (*lineup["starters"], *lineup["bench"])
                if player["name"] == "Beta Nove"
            )
        )

    open_play = await worth("open", goals=4, penalties_scored=0, penalties_taken=0)
    from_the_spot = await worth("spot", goals=4, penalties_scored=3, penalties_taken=3)
    assert from_the_spot < open_play
