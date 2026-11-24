"""Invented calibration set rows for `mvp-cameos`' tests: benched players of each kind of cameo."""

from __future__ import annotations

from fantadamus.contracts.types import Role
from fantadamus.domains.calibration import Outcome, SetRow

FLAT_RATING = 0.2 + 0.5 * 0.8
"""A defender at 20% to start: he comes on with a rating half the time he doesn't start."""
ONCE_ON = 0.1 + 0.9 * 0.6
"""A forward with a 10% chance of scoring once on: rated if he scores, or 60% of the time if not."""
PRICED_RATING = 0.2 + 0.5 * 0.8 * ONCE_ON


def row(
    round: int,
    match: int,
    player_id: int,
    *,
    role: Role = "D",
    priced: bool | None = False,
    rated: bool | str = False,
    started: bool | str = False,
    p_start: float = 0.2,
    p_rating: float | None = FLAT_RATING,
    p_scores_cameo: float | None = None,
) -> SetRow:
    return SetRow(
        round=round,
        home=f"club{match}",
        away=f"other{match}",
        club=f"club{match}",
        player_id=player_id,
        role=role,
        consensus=p_start,
        p_start=p_start,
        p_rating=p_rating,
        p_scores=None,
        p_scores_cameo=p_scores_cameo,
        p_clean_sheet=None,
        priced_cameo=priced,
        outcome=Outcome(started=started, rated=rated, scored=False, clean_sheet=False),
    )


def flat(round: int, match: int, player_id: int, *, rated: bool) -> SetRow:
    """A benched defender, a flat cameo."""
    return row(round, match, player_id, rated=rated)


def priced(round: int, match: int, player_id: int, *, rated: bool, role: Role = "A") -> SetRow:
    """A benched forward, or an attacking midfielder: a priced cameo with a 10% chance of scoring once on."""
    return row(
        round,
        match,
        player_id,
        role=role,
        priced=True,
        rated=rated,
        p_rating=PRICED_RATING,
        p_scores_cameo=0.1,
    )


def brier(chance: float, happened: int, of: int) -> float:
    """The summed squared error of `of` chances, `happened` of which happened."""
    return happened * (1 - chance) ** 2 + (of - happened) * chance**2
