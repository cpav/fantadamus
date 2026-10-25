"""The bronze envelope: the fields every bronze record carries, whatever its payload (R16.2)."""

from __future__ import annotations

from typing import Self

from pydantic import Field, JsonValue, model_validator

from fantadamus.contracts.base import SEMVER_PATTERN, Contract
from fantadamus.contracts.types import Sha256, SourceUrl, UtcDatetime
from fantadamus.core.hashing import content_sha256


class BronzeEnvelope(Contract):
    """One submission as received: provenance, times, hash and the payload exactly as submitted."""

    __version__ = "1.0.0"

    source: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$", description="Logical source name, e.g. `skeleton`")
    source_url: SourceUrl = Field(description="The page the facts were read from; must pass the allowlist")
    published_at: UtcDatetime | None = Field(default=None, description="When the source published it (UTC)")
    captured_at: UtcDatetime = Field(description="When the source was read (UTC); as-of queries use this")
    received_at: UtcDatetime = Field(description="When the server received it (UTC), from the injected clock")
    content_sha256: Sha256 = Field(description="SHA-256 of the canonical JSON payload")
    contract_version: str = Field(pattern=SEMVER_PATTERN, description="Version of the payload's contract")
    submitted_by: str = Field(
        pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$", description="Pseudonymous user ID, never a real name"
    )
    payload: JsonValue = Field(description="The submitted rows, as received")

    @model_validator(mode="after")
    def _hash_matches_payload(self) -> Self:
        if content_sha256(self.payload) != self.content_sha256:
            raise ValueError("content_sha256 does not match the payload")
        return self
