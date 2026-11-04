"""AT-11: the worth of a choice. A 12% backup keeper ahead of a 92% starter on the key is a coin flip, not
"clear", and the order doesn't change (R8)."""

from __future__ import annotations

from fantadamus.engine import keepers
from fantadamus.engine.rank import Scoring
from tests.roles_data import keeper

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)


def test_at11_backup_keeper_is_a_coin_flip() -> None:
    backup = keeper(
        name="Riserva",
        club="alfa",
        rated_appearances=0,
        average_rating=None,
        goals_conceded=None,
        p_start=0.12,
        opponent_xg=0.9,
    )
    starter = keeper(
        name="Titolare",
        club="beta",
        rated_appearances=10,
        average_rating=5.9,
        goals_conceded=18,
        p_start=0.92,
        opponent_xg=1.7,
    )
    verdict = keepers.compare(starter, backup, CLASSIC).verdict
    assert (verdict.first, verdict.second) == ("Riserva", "Titolare")  # the order still follows the key
    assert verdict.key_margin > 0.5  # alone, that would have said "clear"
    assert verdict.margin < 0.15
    assert verdict.label == "coin flip"
