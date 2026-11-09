"""Invented statistics reads for the review's tests: what the page would show for a player's true season."""

from __future__ import annotations

from collections.abc import Sequence

from fantadamus.domains.review import Read


def read(
    ratings: Sequence[float],
    *,
    goals: int = 0,
    penalties: tuple[int, int] = (0, 0),
    assists: int = 0,
    yellows: int = 0,
    reds: int = 0,
    saved: int = 0,
    conceded: int = 0,
    own_goals: int = 0,
    keeper: bool = False,
    with_new_columns: bool = True,
) -> Read:
    """A read after these rated games: each average rounded to two decimals as the page shows it. The
    fantasy average adds Fantacalcio.it's standard bonuses; without the new columns, it's a read stored before
    them."""
    rated, total = len(ratings), sum(ratings)
    scored, taken = penalties
    bonus = 3 * goals + assists - 0.5 * yellows - reds - 3 * (taken - scored) - 2 * own_goals
    if keeper:
        bonus += 3 * saved - conceded
    return Read(
        rated=rated,
        average=round(total / rated, 2) if rated else None,
        fantasy=round((total + bonus) / rated, 2) if rated and with_new_columns else None,
        goals=goals,
        assists=assists,
        yellows=yellows,
        penalties_scored=scored,
        penalties_taken=taken,
        reds=reds if with_new_columns else None,
        saved=saved if with_new_columns else None,
        conceded=conceded,
        keeper=keeper,
    )
