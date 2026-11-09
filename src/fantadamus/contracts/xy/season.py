"""Season contracts: a player's profile (R6.1), a read of the statistics page (mvp-roles R1.1), the league
table (R6.2) and penalty takers (R6.3)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, Role
from fantadamus.contracts.xy import once_each

ROUNDS = 38
GOALS_PER_MATCH = 5
CONCEDED_PER_MATCH = 10
STATS_PLAYERS = 1000

MantraRole = Literal["Por", "Ds", "Dc", "Dd", "B", "E", "M", "C", "T", "W", "A", "Pc"]


class PlayerSeason(Part):
    """A player's Serie A season so far: the figures and checks a profile and a statistics-page row share."""

    player_id: int = Field(gt=0, description="The numeric ID at the end of his profile URL")
    name: Name = Field(description="His name as the profile writes it")
    club: Name
    role: Role = Field(description="Classic role: P keeper, D defender, C midfielder, A forward")
    mantra_role: MantraRole | None = Field(default=None, description="The first Mantra role on the profile")
    appearances: int = Field(
        ge=0,
        le=ROUNDS,
        description="Presenze; from the statistics page, which gives none, the same as rated appearances",
    )
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
    goals_conceded: int | None = Field(
        default=None,
        ge=0,
        description="A keeper's goals conceded (gol subiti); none where the page doesn't say",
    )
    fantasy_average: float | None = Field(
        default=None,
        ge=-10,
        le=30,
        description="Fantamedia (FM), with Fantacalcio.it's standard bonuses; none without rated appearances "
        "or where the page doesn't say",
    )
    penalties_saved: int | None = Field(
        default=None, ge=0, description="A keeper's penalties saved (rigori parati); none where not read"
    )
    red_cards: int | None = Field(default=None, ge=0, description="Espulsioni; none where not read")

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
        conceded = self.goals_conceded or 0
        if conceded and self.role != "P":
            raise ValueError(f"only a keeper concedes goals, and {self.name} isn't one")
        if conceded > self.rated_appearances * CONCEDED_PER_MATCH:
            raise ValueError(
                f"{conceded} goals conceded in {self.rated_appearances} rated appearances is impossible"
            )
        return self


class PlayerSeasonPayload(PlayerSeason, Contract):
    """A player's Serie A season so far, from his Fantacalcio.it profile or the statistics page."""

    __version__ = "1.2.0"


class SeasonStatsPayload(Contract):
    """One read of Fantacalcio.it's statistics page: every player it lists, with his season so far."""

    __version__ = "1.1.0"

    players: list[PlayerSeason] = Field(min_length=1, max_length=STATS_PLAYERS)

    @model_validator(mode="after")
    def _each_player_once(self) -> Self:
        seen: set[int] = set()
        for player in self.players:
            if player.player_id in seen:
                raise ValueError(f"player {player.player_id} is listed twice")
            seen.add(player.player_id)
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
