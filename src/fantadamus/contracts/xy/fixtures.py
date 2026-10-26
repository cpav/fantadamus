"""`FixturesPayload`: a round's matches and kickoffs, from Wikipedia's Serie A season page (R2.1)."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, UtcDatetime
from fantadamus.contracts.xy import once_each
from fantadamus.core.names import name_key


class Fixture(Part):
    home: Name = Field(description="Home club, as the page names it")
    away: Name = Field(description="Away club, as the page names it")
    kickoff_at: UtcDatetime = Field(description="Kickoff with its time zone, e.g. 2026-10-31T15:00:00+01:00")

    @model_validator(mode="after")
    def _two_clubs(self) -> Self:
        if name_key(self.home) == name_key(self.away):
            raise ValueError(f"{self.home} plays itself")
        return self


class FixturesPayload(Contract):
    """The matches of one round."""

    __version__ = "1.0.0"

    round: int = Field(ge=1, le=38, description="The round (giornata) number")
    matches: list[Fixture] = Field(min_length=1, max_length=10, description="The round's matches")

    @model_validator(mode="after")
    def _each_club_once(self) -> Self:
        once_each((club for match in self.matches for club in (match.home, match.away)), "{name} plays twice")
        return self
