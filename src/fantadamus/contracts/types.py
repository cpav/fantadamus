"""Field types shared by contracts: UTC timestamps, readable source URLs, hashes, names and roles."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BeforeValidator, Field, StringConstraints

from fantadamus.core.urls import url_host


def _from_iso(value: object) -> object:
    # Strict contracts refuse strings for datetimes, but tool arguments arrive as JSON: accept ISO 8601 only.
    return dt.datetime.fromisoformat(value) if isinstance(value, str) else value


def _to_utc(value: dt.datetime) -> dt.datetime:
    return value.astimezone(dt.UTC)


def _readable_url(value: str) -> str:
    if url_host(value) is None:
        raise ValueError("must be an http(s) URL with a valid host and no user-info")
    return value


UtcDatetime = Annotated[AwareDatetime, BeforeValidator(_from_iso), AfterValidator(_to_utc)]
SourceUrl = Annotated[
    str, Field(max_length=2083, json_schema_extra={"format": "uri"}), AfterValidator(_readable_url)
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Role = Literal["P", "D", "C", "A"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
"""A player's or club's name as the page writes it; clubs are mapped through `config/clubs.toml` on submit."""
