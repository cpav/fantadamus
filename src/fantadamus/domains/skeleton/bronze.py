"""Bronze for the skeleton: wrap a submitted payload in its envelope (R16.2)."""

from __future__ import annotations

import datetime as dt

from pydantic import JsonValue

from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.contracts.skeleton.player import SkeletonPlayer
from fantadamus.core.hashing import content_sha256

SOURCE = "skeleton"


def build_envelope(
    rows: JsonValue,
    *,
    source_url: str,
    captured_at: dt.datetime,
    published_at: dt.datetime | None,
    received_at: dt.datetime,
    submitted_by: str,
) -> BronzeEnvelope:
    """The bronze record for one submission; raises `ValidationError` if the envelope is invalid."""
    return BronzeEnvelope.model_validate(
        {
            "source": SOURCE,
            "source_url": source_url,
            "published_at": published_at,
            "captured_at": captured_at,
            "received_at": received_at,
            "content_sha256": content_sha256(rows),
            "contract_version": SkeletonPlayer.__version__,
            "submitted_by": submitted_by,
            "payload": rows,
        }
    )
