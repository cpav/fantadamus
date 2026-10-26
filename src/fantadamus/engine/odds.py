"""Team xG from the betting lines: de-margining, a Poisson model with the Dixon-Coles low-score correction,
and its fit (design C7; method §A4, §A5; R5.2, R5.3).

The correction only moves probability between 0-0, 1-0, 0-1 and 1-1, so it has closed forms. With
shift = rho·λμ·e^(-λ-μ), draws gain -2·shift, each win gains shift, both-teams-score loses shift, and total
goals, hence over/under 2.5, are untouched. One evaluation is a few dozen operations, so the fit (a coarse
grid, then a pattern search halving its step) takes milliseconds.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from fantadamus.engine.constants import DIXON_COLES_RHO, MAX_GOALS, TEAM_FORM_WEIGHT, XG_RANGE

_GRID_STEP = 0.2
_FINEST_STEP = 0.0005


class Market(BaseModel):
    """Match probabilities, de-margined: 1X2, over 2.5 goals and, when known, both teams to score."""

    model_config = ConfigDict(frozen=True)

    p_home: float
    p_draw: float
    p_away: float
    p_over: float
    p_btts: float | None = None


def de_margin(odds: Sequence[float]) -> list[float]:
    """Implied probabilities scaled to sum to 1 (proportional normalisation)."""
    implied = [1 / price for price in odds]
    total = math.fsum(implied)
    return [value / total for value in implied]


@functools.lru_cache(maxsize=4096)
def _pmf(rate: float) -> tuple[float, ...]:
    probabilities = [math.exp(-rate)]
    for goals in range(1, MAX_GOALS + 1):
        probabilities.append(probabilities[-1] * rate / goals)
    return tuple(probabilities)


def model(home: float, away: float, rho: float = DIXON_COLES_RHO) -> Market:
    """The market implied by team xG `home` and `away`."""
    home_pmf, away_pmf = _pmf(home), _pmf(away)
    home_cdf = list(_running_sum(home_pmf))
    away_cdf = list(_running_sum(away_pmf))
    p_home = math.fsum(home_pmf[x] * away_cdf[x - 1] for x in range(1, MAX_GOALS + 1))
    p_away = math.fsum(away_pmf[y] * home_cdf[y - 1] for y in range(1, MAX_GOALS + 1))
    p_draw = math.fsum(h * a for h, a in zip(home_pmf, away_pmf, strict=True))
    shift = rho * home * away * math.exp(-home - away)
    p_home, p_draw, p_away = p_home + shift, p_draw - 2 * shift, p_away + shift
    total = p_home + p_draw + p_away
    goals = home + away
    return Market(
        p_home=p_home / total,
        p_draw=p_draw / total,
        p_away=p_away / total,
        p_over=1 - math.exp(-goals) * (1 + goals + goals**2 / 2),
        p_btts=(1 - math.exp(-home)) * (1 - math.exp(-away)) - shift,
    )


def _running_sum(values: Sequence[float]) -> list[float]:
    total, sums = 0.0, []
    for value in values:
        total += value
        sums.append(total)
    return sums


def _error(market: Market, home: float, away: float) -> float:
    fitted = model(home, away)
    pairs = [
        (fitted.p_home, market.p_home),
        (fitted.p_draw, market.p_draw),
        (fitted.p_away, market.p_away),
        (fitted.p_over, market.p_over),
    ]
    if market.p_btts is not None and fitted.p_btts is not None:
        pairs.append((fitted.p_btts, market.p_btts))
    return math.fsum((a - b) ** 2 for a, b in pairs)


def fit(market: Market) -> tuple[float, float]:
    """The team xG (home, away) whose model is closest to `market`, by least squares."""
    low, high = XG_RANGE
    steps = round((high - low) / _GRID_STEP)
    grid = [round(low + index * _GRID_STEP, 6) for index in range(steps + 1)]
    best = min(((h, a) for h in grid for a in grid), key=lambda point: _error(market, *point))
    error, step = _error(market, *best), _GRID_STEP / 2
    while step >= _FINEST_STEP:
        moves = [(best[0] + dh, best[1] + da) for dh, da in ((step, 0), (-step, 0), (0, step), (0, -step))]
        inside = [(h, a) for h, a in moves if low <= h <= high and low <= a <= high]
        candidate = min(inside, key=lambda point: _error(market, *point))
        if (candidate_error := _error(market, *candidate)) < error:
            best, error = candidate, candidate_error
        else:
            step /= 2
    return best


def regressed(per_match: float, matches: int, league: float) -> float:
    """A team's goals per match, shrunk toward the league's with weight n / (n + 12)."""
    weight = matches / (matches + TEAM_FORM_WEIGHT)
    return weight * per_match + (1 - weight) * league


def form_xg(
    home: tuple[float, float, int], away: tuple[float, float, int], league: float
) -> tuple[float, float]:
    """Team xG without odds (R5.3): each side's regressed attack times the other's regressed defence,
    over the league average. Each team is (goals for per match, goals against per match, matches)."""
    home_attack, home_defence = regressed(home[0], home[2], league), regressed(home[1], home[2], league)
    away_attack, away_defence = regressed(away[0], away[2], league), regressed(away[1], away[2], league)
    return home_attack * away_defence / league, away_attack * home_defence / league
