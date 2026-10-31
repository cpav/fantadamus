"""Lineup contracts: one outlet's probable lineups for a match (R3.1), the official lineups (R4.1), and one
outlet's per-player start percentages (mvp-collect R4.1)."""

from __future__ import annotations

from typing import Self

from pydantic import Field, field_validator, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, Role
from fantadamus.contracts.xy import once_each

STARTERS = 11
SHARES_PERCENT = (95.0, 105.0)


def _eleven(starters: list[str]) -> list[str]:
    if len(starters) != STARTERS:
        raise ValueError(f"needs {STARTERS} starters, got {len(starters)}")
    once_each(starters, "{name} is listed twice")
    return starters


class Share(Part):
    name: Name
    percent: float = Field(ge=0, le=100, description="His share of the place, in percent")


class Ballottaggio(Part):
    """A contest for one starting place, with each player's share as the page shows it."""

    players: list[Share] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def _shares_sum_to_one_place(self) -> Self:
        once_each((share.name for share in self.players), "{name} is listed twice")
        total = sum(share.percent for share in self.players)
        low, high = SHARES_PERCENT
        if not low <= total <= high:
            raise ValueError(f"shares sum to {total:g}%, outside {low:g}% to {high:g}%")
        return self


class ProbableTeam(Part):
    starters: list[Name] = Field(
        description="The 11 expected starters, including each ballottaggio's favourite"
    )
    ballottaggi: list[Ballottaggio] = Field(default=[], description="Contested places with their shares")
    bench: list[Name] = Field(default=[], description="Players listed but not expected to start")
    unavailable: list[Name] = Field(default=[], description="Injured, suspended or otherwise out")

    _starters = field_validator("starters")(_eleven)


class ProbableLineupPayload(Contract):
    """One outlet's probable lineups for one match."""

    __version__ = "1.0.0"

    outlet: Name = Field(description="Whose view this is, e.g. the site or the newspaper it quotes")
    home: Name = Field(description="Home club")
    away: Name = Field(description="Away club")
    home_team: ProbableTeam
    away_team: ProbableTeam


class OfficialTeam(Part):
    starters: list[Name] = Field(description="The 11 starters")
    bench: list[Name] = Field(default=[], description="The substitutes")

    _starters = field_validator("starters")(_eleven)


class OfficialLineupPayload(Contract):
    """The official lineups of one match, published about an hour before kickoff."""

    __version__ = "1.0.0"

    home: Name = Field(description="Home club")
    away: Name = Field(description="Away club")
    home_team: OfficialTeam
    away_team: OfficialTeam


class OutletPlayer(Part):
    name: Name
    role: Role | None = Field(default=None, description="Classic role, when the page shows it")
    percent: float = Field(ge=0, le=100, description="The outlet's chance that he starts, in percent")


class OutletTeam(Part):
    players: list[OutletPlayer] = Field(description="Every player the outlet gives a percentage for")
    unavailable: list[Name] = Field(default=[], description="Players the page lists as injured or suspended")

    @field_validator("players")
    @classmethod
    def _enough_players(cls, players: list[OutletPlayer]) -> list[OutletPlayer]:
        if len(players) < STARTERS:
            raise ValueError(f"needs at least {STARTERS} players, got {len(players)}")
        once_each((player.name for player in players), "{name} is listed twice")
        return players


class OutletLineupPayload(Contract):
    """One outlet's chance of starting for each player of one match (mvp-collect R4.1)."""

    __version__ = "1.0.0"

    outlet: Name = Field(
        description="Whose percentages these are, e.g. Gazzetta, read from a page that may show several"
    )
    home: Name = Field(description="Home club")
    away: Name = Field(description="Away club")
    home_team: OutletTeam
    away_team: OutletTeam
