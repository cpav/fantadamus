"""Canonical JSON and its SHA-256 (R16.2).

Two payloads get the same `content_sha256` exactly when their canonical JSON is equal: keys sorted, no
insignificant whitespace, UTF-8. Key order and formatting in the submission don't matter.
"""

from __future__ import annotations

import hashlib
import json


def canonical_json(value: object) -> str:
    """JSON with sorted keys and no whitespace; NaN and infinities are refused."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def content_sha256(value: object) -> str:
    """Hex SHA-256 of the canonical JSON, encoded as UTF-8."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
