"""`LeagueRules`: a Fantacalcio Classic league's bonuses and maluses, set by each user (R12.1, R12.2), and
what a lineup also needs: thresholds, the bench, substitutions and formations (mvp-lineup R2)."""

from __future__ import annotations

import itertools
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name
from fantadamus.contracts.xy import once_each

Bonus = Annotated[float, Field(ge=0, le=10)]
Malus = Annotated[float, Field(ge=-10, le=0)]
OUTFIELD = 10
FEWEST_ON_THE_BENCH = 4
_FORMATION = re.compile(r"\d-\d-\d")


def formation_lines(formation: str) -> tuple[int, int, int]:
    """Defenders, midfielders and forwards: `3-4-3` is (3, 4, 3)."""
    defenders, midfielders, forwards = map(int, formation.split("-"))
    return defenders, midfielders, forwards


class GoalByRole(Part):
    """A goal's bonus for each Classic role, for leagues that set it that way."""

    keeper: Bonus
    defender: Bonus
    midfielder: Bonus
    forward: Bonus


class LineupRules(Part):
    """What a lineup needs beyond bonuses and maluses. Any of it may still be unset: the setup step asks for
    what is (mvp-lineup R2.2)."""

    format: Literal["head_to_head", "total_points"] | None = Field(
        default=None, description="Head to head, where thresholds decide; or total points, where they don't"
    )
    thresholds: list[float] | None = Field(
        default=None,
        description="Rising points for the 1st, 2nd and later fantasy goals; past the last, its last step "
        "repeats",
    )
    bench_size: int | None = Field(default=None, le=25, description="Places on the bench")
    substitutions: int | None = Field(default=None, ge=0, le=11, description="Substitutions per match")
    substitution_mode: Literal["same_role", "role_first", "bench_order"] | None = Field(
        default=None,
        description="How a player without a rating is replaced: same role only (the formation never "
        "changes); role first, then bench order; or bench order first. The last two may change the "
        "formation, into an allowed one",
    )
    formations: list[str] | None = Field(
        default=None, description="Allowed formations, as defenders-midfielders-forwards: 3-4-3"
    )
    no_rating_vote: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="The vote a player without a rating keeps when nobody replaces him, if the league gives "
        "one",
    )
    other_rules: list[Name] = Field(
        default=[],
        description="Rules this league uses that Fantadamus leaves out, such as a modifier or a captain; "
        "every lineup says its score doesn't include them",
    )

    @field_validator("thresholds")
    @classmethod
    def _rising(cls, thresholds: list[float] | None) -> list[float] | None:
        if thresholds is None:
            return None
        if len(thresholds) < 2:
            raise ValueError("needs at least two thresholds: past the last, its last step repeats")
        if thresholds[0] <= 0:
            raise ValueError("thresholds must be above 0")
        for before, after in itertools.pairwise(thresholds):
            if after <= before:
                raise ValueError(f"thresholds must rise: {after:g} comes after {before:g}")
        return thresholds

    @field_validator("bench_size")
    @classmethod
    def _bench_covers_every_role(cls, places: int | None) -> int | None:
        if places is not None and places < FEWEST_ON_THE_BENCH:
            raise ValueError(
                f"a bench needs at least {FEWEST_ON_THE_BENCH} places, a keeper and one of each role: "
                f"got {places}"
            )
        return places

    @field_validator("formations")
    @classmethod
    def _eleven_players(cls, formations: list[str] | None) -> list[str] | None:
        if formations is None:
            return None
        if not formations:
            raise ValueError("needs at least one formation")
        once_each(formations, "{name} is listed twice")
        for formation in formations:
            if not _FORMATION.fullmatch(formation):
                raise ValueError(f"{formation} isn't three lines, such as 3-4-3")
            lines = formation_lines(formation)
            if min(lines) < 1:
                raise ValueError(f"{formation} needs at least one player in each line")
            if sum(lines) != OUTFIELD:
                raise ValueError(f"{formation} must add up to ten outfield players, and a keeper")
        return formations


class LeagueRules(Contract):
    """The league's bonus and malus table, and what a lineup needs. Bonuses are 0 to 10, maluses -10 to 0."""

    __version__ = "1.1.0"

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
    lineup: LineupRules | None = Field(
        default=None,
        description="What a lineup needs: thresholds, the bench, substitutions and formations. Not needed "
        "for 'X or Y?'. A call without it, or with only some of it, keeps what's stored",
    )
