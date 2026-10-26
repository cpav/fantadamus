"""Season contracts: a player's profile (R6.1), the league table (R6.2) and penalty takers (R6.3)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, Role
from fantadamus.contracts.xy import once_each

ROUNDS = 38
GOALS_PER_MATCH = 5

MantraRole = Literal["Por", "Ds", "Dc", "Dd", "B", "E", "M", "C", "T", "W", "A", "Pc"]


class PlayerSeasonPayload(Contract):
    """A player's Serie A season so far, from his Fantacalcio.it profile."""

    __version__ = "1.0.0"

    player_id: int = Field(gt=0, description="The numeric ID at the end of his profile URL")
    name: Name = Field(description="His name as the profile writes it")
    club: Name
    role: Role = Field(description="Classic role: P keeper, D defender, C midfielder, A forward")
    mantra_role: MantraRole | None = Field(default=None, description="The first Mantra role on the profile")
    appearances: int = Field(ge=0, le=ROUNDS, description="Presenze")
    rated_appearances: int = Field(ge=0, le=ROUNDS, description="Appearances with a rating (presenze a voto)")
    average_rating: float | None = Field(
        default=None,
        ge=3,
        le=10,
        description="Media voto (MV), not fantamedia; none without rated appearances",
    )
    goals: int = Field(ge=0)
    assists: int = Field(ge=0)
    yellow_cards: int = Field(ge=0)
    penalties_scored: int = Field(ge=0)
    penalties_taken: int = Field(ge=0)

    @model_validator(mode="after")
    def _plausible(self) -> Self:
        if self.goals > self.appearances * GOALS_PER_MATCH:
            raise ValueError(f"{self.goals} goals in {self.appearances} appearances is impossible")
        if self.rated_appearances > self.appearances:
            raise ValueError(f"{self.rated_appearances} rated appearances out of {self.appearances}")
        if (self.average_rating is None) != (self.rated_appearances == 0):
            raise ValueError("an average rating goes with rated appearances, and only with them")
        if self.penalties_scored > self.penalties_taken:
            raise ValueError(f"{self.penalties_scored} penalties scored out of {self.penalties_taken} taken")
        return self


class TeamRow(Part):
    club: Name
    played: int = Field(ge=0, le=ROUNDS, description="Matches played")
    goals_for: int = Field(ge=0)
    goals_against: int = Field(ge=0)


class TeamSeasonPayload(Contract):
    """The Serie A table: matches played and goals for and against, per club."""

    __version__ = "1.0.0"

    teams: list[TeamRow] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _each_club_once(self) -> Self:
        once_each((row.club for row in self.teams), "{name} is listed twice")
        return self


class ClubTakers(Part):
    club: Name
    takers: list[Name] = Field(
        min_length=1, max_length=5, description="Designated takers, first choice first"
    )


class PenaltyTakersPayload(Contract):
    """Each club's penalty takers in order, from the penalty-takers page."""

    __version__ = "1.0.0"

    clubs: list[ClubTakers] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _each_club_once(self) -> Self:
        once_each((row.club for row in self.clubs), "{name} is listed twice")
        for row in self.clubs:
            once_each(row.takers, "{name} is listed twice")
        return self
