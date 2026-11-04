"""What the outfield and keeper models share: the league's values, the key that orders players, the verdict
and the search for what would flip it (mvp-roles design C8; method §A3; mvp-x-or-y R9.8, R10).

Bonuses and maluses are the league's signed values, so a yellow card at -0.5 lowers the score (R9.1).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fantadamus.engine.constants import CLEAR, COIN_FLIP

Label = Literal["coin flip", "lean", "clear", "covered"]
"""`covered`: two keepers of one club, of whom exactly one plays (method §A6)."""
_BISECTIONS = 40


class Scoring(BaseModel):
    """The league's signed values the models use (R12.5; mvp-roles R3.1)."""

    model_config = ConfigDict(frozen=True)

    goal: float
    """For the player's Classic role (mvp-roles R2.5)."""
    penalty_scored: float
    assist: float
    yellow: float
    clean_sheet: float
    goal_conceded: float


class Option(BaseModel):
    """A player as the ordering rule sees him."""

    model_config = ConfigDict(frozen=True)

    name: str
    p_start: float
    p_cameo: float
    e_start: float
    e_cameo: float

    def figures(self) -> dict[str, float]:
        return {
            "p_start": self.p_start,
            "e_start": self.e_start,
            "p_cameo": self.p_cameo,
            "e_cameo": self.e_cameo,
        }


class Verdict(BaseModel):
    first: str
    """Start him."""
    second: str
    """Put him first on the bench."""
    margin: float
    """The difference in keys, in points."""
    label: Label
    no_cover_first: str
    """Who to start if the bench can't cover (R10.6)."""
    no_cover_differs: bool
    first_plays: bool
    second_plays: bool
    """False when he has no chance of a rating, so he shouldn't take the bench place (R10.7)."""


def key(p_start: float, e_start: float, p_cameo: float, e_cameo: float) -> float:
    """Method §A3: the value of his rating, whichever way he gets it; 0 if he can't get one."""
    chance = p_start + p_cameo
    return (p_start * e_start + p_cameo * e_cameo) / chance if chance else 0.0


def no_cover(p_start: float, e_start: float, p_cameo: float, e_cameo: float) -> float:
    """His expected points when no bench player covers a missing rating (R10.6)."""
    return p_start * e_start + p_cameo * e_cameo


def label(margin: float) -> Label:
    if margin < COIN_FLIP:
        return "coin flip"
    return "lean" if margin <= CLEAR else "clear"


def _rank(option: Option) -> tuple[float, float, str]:
    return key(**option.figures()), no_cover(**option.figures()), option.name


def verdict(a: Option, b: Option) -> Verdict:
    """Start the higher key, put the other first on the bench (R10.1, R10.2, R10.6, R10.7)."""
    first, second = sorted((a, b), key=_rank, reverse=True)
    covered = max((a, b), key=lambda option: (no_cover(**option.figures()), option.name))
    return Verdict(
        first=first.name,
        second=second.name,
        margin=_rank(first)[0] - _rank(second)[0],
        label=label(_rank(first)[0] - _rank(second)[0]),
        no_cover_first=covered.name,
        no_cover_differs=covered.name != first.name,
        first_plays=first.p_start + first.p_cameo > 0,
        second_plays=second.p_start + second.p_cameo > 0,
    )


def covering(a: Option, b: Option) -> Verdict:
    """Two keepers of one club: one plays exactly when the other doesn't, so either order scores the same, and
    fielding the likelier starter saves a substitution (method §A6; mvp-roles R3.6)."""
    first, second = sorted((a, b), key=lambda option: (option.p_start, option.name), reverse=True)
    return Verdict(
        first=first.name,
        second=second.name,
        margin=0.0,
        label="covered",
        no_cover_first=first.name,
        no_cover_differs=False,
        first_plays=first.p_start > 0,
        second_plays=second.p_start > 0,
    )


def flip[I: BaseModel](
    leader: I, worth: Callable[[I], Option], field: str, bound: float, trailer: float
) -> float | None:
    """The value of the leader's `field`, between now and `bound`, at which his key falls to the trailer's;
    None if he stays ahead all the way (R10.4)."""

    def ahead(at: float) -> bool:
        return key(**worth(leader.model_copy(update={field: at})).figures()) >= trailer

    if ahead(bound):
        return None
    inside, outside = float(getattr(leader, field)), bound
    for _ in range(_BISECTIONS):
        middle = (inside + outside) / 2
        inside, outside = (middle, outside) if ahead(middle) else (inside, middle)
    return inside
