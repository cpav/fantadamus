"""`MatchOddsPayload`: one page's odds for one match, 1X2 plus over/under and goal/no goal when shown (R5.1),
with the margin check (R8.3)."""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract
from fantadamus.contracts.types import Name

MARGIN = (0.0, 0.15)

Odds = Annotated[float, Field(gt=1, le=1000, description="Decimal odds, e.g. 2.10")]


def _check_margin(market: str, *odds: float) -> None:
    margin = sum(1 / price for price in odds) - 1
    low, high = MARGIN
    if not low <= margin <= high:
        raise ValueError(f"{market} margin {margin:.1%} is outside {low:.0%} to {high:.0%}")


class MatchOddsPayload(Contract):
    """One bookmaker's prices for one match, as a page shows them."""

    __version__ = "1.2.0"

    home: Name = Field(description="Home club")
    away: Name = Field(description="Away club")
    bookmaker: Name = Field(description="The bookmaker the page quotes")
    home_win: Odds
    draw: Odds
    away_win: Odds
    over_2_5: Odds | None = Field(default=None, description="Over 2.5 goals, when the page shows it")
    under_2_5: Odds | None = Field(default=None, description="Under 2.5 goals, when the page shows it")
    goal: Odds | None = Field(default=None, description="Both teams to score, when the page shows it")
    no_goal: Odds | None = Field(default=None, description="Not both teams to score, when the page shows it")
    over_2_5_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="The page's own chance of 3 or more goals, when it gives that instead",
    )

    @model_validator(mode="after")
    def _margins(self) -> Self:
        _check_margin("1X2", self.home_win, self.draw, self.away_win)
        if (self.over_2_5 is None) != (self.under_2_5 is None):
            raise ValueError("over and under go together")
        if self.over_2_5 is not None and self.under_2_5 is not None:
            _check_margin("over/under 2.5", self.over_2_5, self.under_2_5)
        if (self.goal is None) != (self.no_goal is None):
            raise ValueError("goal and no goal go together")
        if self.goal is not None and self.no_goal is not None:
            _check_margin("goal/no goal", self.goal, self.no_goal)
        return self
