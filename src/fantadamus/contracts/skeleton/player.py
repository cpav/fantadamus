"""`SkeletonPlayer`: one row of the walking skeleton's payload (C10)."""

from __future__ import annotations

from pydantic import Field

from fantadamus.contracts.base import Contract
from fantadamus.contracts.types import Role


class SkeletonPlayer(Contract):
    """A synthetic player: id, name, club and Classic role (P, D, C, A)."""

    __version__ = "1.0.0"

    player_id: int = Field(gt=0, description="Positive player ID")
    name: str = Field(min_length=1, max_length=60)
    club: str = Field(min_length=1)
    role: Role = Field(description="Classic role: P keeper, D defender, C midfielder, A forward")
