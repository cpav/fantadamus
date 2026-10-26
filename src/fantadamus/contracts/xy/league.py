"""`LeagueRules`: a Fantacalcio Classic league's bonuses and maluses, set by each user (R12.1, R12.2)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from fantadamus.contracts.base import Contract, Part

Bonus = Annotated[float, Field(ge=0, le=10)]
Malus = Annotated[float, Field(ge=-10, le=0)]


class GoalByRole(Part):
    """A goal's bonus for each Classic role, for leagues that set it that way."""

    keeper: Bonus
    defender: Bonus
    midfielder: Bonus
    forward: Bonus


class LeagueRules(Contract):
    """The league's bonus and malus table. Bonuses are 0 to 10, maluses -10 to 0."""

    __version__ = "1.0.0"

    goal: Bonus | GoalByRole = Field(description="A goal scored: one value, or one per role")
    assist: Bonus = Field(description="An assist")
    penalty_scored: Bonus = Field(description="A penalty scored, counted in place of the goal bonus")
    penalty_missed: Malus = Field(description="A penalty missed")
    penalty_saved: Bonus = Field(description="A penalty saved, for keepers")
    own_goal: Malus = Field(description="An own goal")
    yellow_card: Malus = Field(description="A yellow card")
    red_card: Malus = Field(description="A red card")
    goal_conceded: Malus = Field(description="Each goal a keeper concedes")
    clean_sheet: Bonus = Field(description="A keeper's clean sheet")
