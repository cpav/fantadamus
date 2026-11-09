"""Formula rules: what a modifier or the captain gives in one simulated round (mvp-rules C5; R2.1, R2.2).

Pure, and the one place a formula rule is worked out. The simulation hands it who was fielded after
substitutions, each with a light mark: his pure vote, and whether he scored, conceded or saved a penalty.
"""

from __future__ import annotations

import bisect
import math
import operator
from collections.abc import Sequence
from typing import NamedTuple

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import Band, FormulaRule

_START = operator.attrgetter("from_value")


class Mark(NamedTuple):
    """What a formula rule reads about one fielded player in one round."""

    role: Role
    vote: float
    """His pure vote: his rating without bonuses or maluses."""
    bonus_or_goal: bool
    """Whether he scored, conceded or saved a penalty."""


def band_points(bands: Sequence[Band], value: float) -> float:
    """The points of the highest band that `value` reaches; below the first, none."""
    reached = bisect.bisect_right(bands, value, key=_START)
    return bands[reached - 1].points if reached else 0.0


def formula_points(rule: FormulaRule, fielded: Sequence[Mark], captain: Mark | None = None) -> float:
    """The points `rule` gives this round. `captain` is whoever counts as captain: the captain, or his vice
    when he has no rating; None when neither has one."""
    if rule.who == "captain":
        vote = captain.vote if captain is not None else (rule.stand_in[0] if rule.stand_in else None)
        return 0.0 if vote is None else band_points(rule.bands, vote)
    everyone = rule.leave_out == "nobody"
    votes: list[float] = []
    for unit in rule.who:
        mine = [mark for mark in fielded if mark.role == unit.role]
        if (unit.at_least is not None and len(mine) < unit.at_least) or (
            unit.at_most is not None and len(mine) > unit.at_most
        ):
            return 0.0
        counted = [mark.vote for mark in mine if everyone or not mark.bonus_or_goal]
        if unit.best is not None:
            counted.sort(reverse=True)
            del counted[unit.best :]
        votes += counted
    if rule.combine == "each":
        return math.fsum([band_points(rule.bands, vote) for vote in votes])
    if rule.base is not None:
        votes.sort(reverse=True)
        del votes[rule.base :]
        missing = rule.base - len(votes)
        if missing and rule.stand_in:
            votes += [rule.stand_in[0], *[rule.stand_in[-1]] * (missing - 1)]
    if not votes:
        return 0.0
    total = math.fsum(votes)
    return band_points(rule.bands, total if rule.combine == "sum" else total / len(votes))
