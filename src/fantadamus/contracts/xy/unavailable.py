"""`InjuriesPayload` and `SuspensionsPayload`: who's out and why, from Fantacalcio.it's injured page and its
suspended-and-diffidati page (mvp-sources design C4; R3.1). Facts only: the pages' sentences aren't kept."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import IsoDate, Name
from fantadamus.contracts.xy import once_each
from fantadamus.core.names import name_key

InjuryKind = Literal[
    "muscle", "knock", "fracture", "ligament", "surgery", "illness", "national team", "other"
]
BodyPart = Literal[
    "thigh", "calf", "knee", "ankle", "adductor", "hamstring", "foot", "shoulder", "back", "other"
]


class Injury(Part):
    name: Name = Field(description="The player, as the page names him")
    kind: InjuryKind = Field(description="What's wrong; 'other' when the sentence doesn't say")
    body_part: BodyPart | None = Field(default=None, description="Where, when the sentence says")
    back_from: IsoDate | None = Field(default=None, description="The earliest return the page gives")
    back_until: IsoDate | None = Field(
        default=None, description="The end of that window: late November is 2026-11-21 to 2026-11-30"
    )
    to_be_assessed: bool = Field(default=False, description="The page says his return is to be assessed")

    @model_validator(mode="after")
    def _one_window(self) -> Self:
        if (self.back_from is None) != (self.back_until is None):
            raise ValueError(f"{self.name}: give back_from and back_until both or neither")
        if self.back_from is not None and self.back_until is not None:
            if self.back_until < self.back_from:
                raise ValueError(f"{self.name}: back_until is before back_from")
            if self.to_be_assessed:
                raise ValueError(f"{self.name}: give a window or to be assessed, not both")
        return self


class ClubInjuries(Part):
    club: Name
    players: list[Injury] = Field(max_length=40, description="Its injured players; none is an empty list")


class InjuriesPayload(Contract):
    """Each club's injured players, from the injured page."""

    __version__ = "1.0.0"

    clubs: list[ClubInjuries] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _each_once(self) -> Self:
        once_each((row.club for row in self.clubs), "{name} is listed twice")
        for row in self.clubs:
            once_each((player.name for player in row.players), "{name} is listed twice")
        return self


class Banned(Part):
    name: Name
    rounds: list[Annotated[int, Field(ge=1, le=38)]] = Field(
        default=[], max_length=10, description="The rounds he misses, where the page says; none if it doesn't"
    )


class ClubBans(Part):
    club: Name
    banned: list[Banned] = Field(default=[], max_length=20, description="Its players banned")
    one_booking: list[Name] = Field(
        default=[], max_length=20, description="Its players one booking from a ban (diffidati)"
    )

    @model_validator(mode="after")
    def _each_once(self) -> Self:
        once_each((player.name for player in self.banned), "{name} is listed twice")
        once_each(self.one_booking, "{name} is listed twice")
        banned = {name_key(player.name) for player in self.banned}
        both = [name for name in self.one_booking if name_key(name) in banned]
        if both:
            raise ValueError(f"{both[0]} is both banned and one booking from a ban")
        return self


class SuspensionsPayload(Contract):
    """Each club's banned players and those one booking from a ban, from the suspended-and-diffidati page."""

    __version__ = "1.0.0"

    clubs: list[ClubBans] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _each_club_once(self) -> Self:
        once_each((row.club for row in self.clubs), "{name} is listed twice")
        return self
