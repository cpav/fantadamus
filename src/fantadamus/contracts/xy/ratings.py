"""`RatingsPayload`: a round's base ratings from three desks, from Fantacalcio-Online's round ratings page
(mvp-sources design C6; R4.2). Evidence for the rating constants and for the raters' bias; no answer prices
it."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, Role
from fantadamus.contracts.xy import once_each
from fantadamus.core.names import name_key

Desk = Literal["Fantacalcio.it", "Roma", "Torino"]


class DeskRating(Part):
    desk: Desk
    rating: float | None = Field(ge=1, le=10, description="The base rating, without bonuses; None for s.v.")


class PlayerRatings(Part):
    club: Name
    name: Name = Field(description="As the page writes him, his initial after his surname")
    role: Role
    came_on: bool = Field(default=False, description="He started on the bench")
    minutes: int | None = Field(
        default=None,
        ge=0,
        le=130,
        description="Minutes played, where the page says: a substitute's, or a starter's taken off",
    )
    ratings: list[DeskRating] = Field(
        max_length=3, description="Each desk that has published: a desk that hasn't is left out"
    )

    @model_validator(mode="after")
    def _each_desk_once(self) -> Self:
        once_each((rated.desk for rated in self.ratings), f"{self.name}: {{name}} rates him twice")
        return self


class MatchRatings(Part):
    home: Name
    away: Name
    players: list[PlayerRatings] = Field(max_length=60)

    @model_validator(mode="after")
    def _their_clubs(self) -> Self:
        clubs = {name_key(self.home), name_key(self.away)}
        for player in self.players:
            if name_key(player.club) not in clubs:
                raise ValueError(f"{player.name}: {player.club} plays in neither {self.home} nor {self.away}")
        return self


class RatingsPayload(Contract):
    """A round's players with each desk's base rating."""

    __version__ = "1.0.0"

    round: int = Field(ge=1, le=38)
    matches: list[MatchRatings] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _each_club_once(self) -> Self:
        once_each((club for match in self.matches for club in (match.home, match.away)), "{name} plays twice")
        return self
