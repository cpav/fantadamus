"""Small helpers for files."""

from __future__ import annotations

import uuid
from pathlib import Path


def temporary_beside(path: Path) -> Path:
    """A hidden name for writing `path` and renaming it into place. It's unique, because a second server, the
    schedule or another thread may be writing the same file."""
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
