"""Reading a JSON-lines log: one model per line, in `<root>/*.jsonl`, the oldest file first."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ValidationError

_LOG = logging.getLogger(__name__)


def read_lines[M: BaseModel](root: Path, model: type[M]) -> list[M]:
    """Every line it can read, in order. A line it can't, half-written or written by a newer version, is
    skipped with a warning naming where it is, never what it says: one bad line mustn't stop every answer."""
    found: list[M] = []
    for path in sorted(root.glob("*.jsonl")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                found.append(model.model_validate_json(line))
            except ValidationError:
                _LOG.warning("Skipped %s line %d: it can't be read", path.name, number)
    return found
