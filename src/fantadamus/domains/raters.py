"""The raters' bias, player by player (mvp-sources design C7; R5).

For each player and desk, over the matches all three desks rated, the bias is the mean of the desk's rating
less the other two desks' mean, with its count and a 90% interval: the mean plus or minus 1.645 standard
errors. The three desks' biases for a player add up to nothing. A bias of `RATER_BIAS_SHOWN` or more, either
way, over at least `RATER_BIAS_MATCHES` matches is said as a claim ("Fantacalcio.it rates him 0.30 above the
other desks, over 9 matches"). It moves nothing: the league's rater's bias is already in a player's average
rating (R5.3).
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from collections.abc import Sequence

from pydantic import BaseModel

from fantadamus.core.names import name_key
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname
from fantadamus.domains.ratings.silver import MatchRatingRow
from fantadamus.engine.constants import RATER_BIAS_MATCHES, RATER_BIAS_SHOWN

DESKS = ("Fantacalcio.it", "Roma", "Torino")
Z_90 = 1.645
"""A 90% interval's half-width, in standard errors."""


class Bias(BaseModel):
    club: str
    name: str
    """As the ratings page writes him."""
    desk: str
    bias: float
    matches: int
    low: float
    high: float
    """The 90% interval."""


def _newest(rows: Sequence[MatchRatingRow]) -> list[MatchRatingRow]:
    """Each round's rows from its newest read: a desk that published later is in it."""
    newest: dict[int, tuple[dt.datetime, str]] = {}
    for row in rows:
        stamp = (row.captured_at, row.content_sha256)
        newest[row.round] = max(newest.get(row.round, stamp), stamp)
    return [row for row in rows if (row.captured_at, row.content_sha256) == newest[row.round]]


def desk_bias(rows: Sequence[MatchRatingRow]) -> list[Bias]:
    """Each player's bias from each desk, over the matches all three desks rated; none for a player without
    such a match."""
    by_match: dict[tuple[str, str], dict[tuple[int, str, str], dict[str, float]]] = {}
    for row in _newest(rows):
        if row.rating is not None and row.desk in DESKS:
            player = by_match.setdefault((row.club, name_key(row.name)), {})
            player.setdefault((row.round, row.home, row.away), {})[row.desk] = row.rating
    names = {(row.club, name_key(row.name)): row.name for row in rows}
    found = []
    for (club, key), matches in sorted(by_match.items()):
        rated = [ratings for ratings in matches.values() if len(ratings) == len(DESKS)]
        if not rated:
            continue
        for desk in DESKS:
            gaps = [
                ratings[desk] - statistics.fmean(ratings[other] for other in DESKS if other != desk)
                for ratings in rated
            ]
            mean = statistics.fmean(gaps)
            error = statistics.stdev(gaps) / math.sqrt(len(gaps)) if len(gaps) > 1 else 0.0
            found.append(
                Bias(
                    club=club,
                    name=names[club, key],
                    desk=desk,
                    bias=mean,
                    matches=len(gaps),
                    low=mean - Z_90 * error,
                    high=mean + Z_90 * error,
                )
            )
    return found


def claim(bias: Bias) -> str | None:
    """The claim to show, or None below the threshold or the sample (both start values)."""
    if abs(bias.bias) < RATER_BIAS_SHOWN or bias.matches < RATER_BIAS_MATCHES:
        return None
    side = "above" if bias.bias > 0 else "below"
    return f"{bias.desk} rates him {abs(bias.bias):.2f} {side} the other desks, over {bias.matches} matches."


def claims_for(player: KnownPlayer, biases: Sequence[Bias], mates: Sequence[KnownPlayer]) -> list[str]:
    """The claims about `player`, his rows found among his club-mates by name, or by surname as the outlets'
    are."""

    def his(bias: Bias) -> bool:
        return (resolve(bias.name, mates).player or same_surname(bias.name, mates)) == player

    return [
        text
        for bias in biases
        if bias.club == player.club and (text := claim(bias)) is not None and his(bias)
    ]
