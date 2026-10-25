"""The skeleton's silver table and gold data product (C10, data models)."""

from __future__ import annotations

from pydantic import Field

from fantadamus.contracts.base import Contract
from fantadamus.contracts.types import Role, Sha256, SourceUrl, UtcDatetime


class SkeletonPlayerRecord(Contract):
    """Silver `skeleton_players`: one row per player, the latest by `captured_at`, with its provenance."""

    __version__ = "1.0.0"

    player_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=60)
    club: str = Field(min_length=1)
    role: Role
    source_url: SourceUrl
    captured_at: UtcDatetime
    bronze_sha256: Sha256 = Field(description="`content_sha256` of the bronze record the row came from")


class SkeletonRoleCount(Contract):
    """Gold `skeleton_role_counts`: players per club and role, with the source URLs they were read from."""

    __version__ = "1.0.0"

    club: str = Field(min_length=1)
    role: Role
    n_players: int = Field(gt=0)
    source_urls: list[str] = Field(min_length=1, description="Sorted, without duplicates")
