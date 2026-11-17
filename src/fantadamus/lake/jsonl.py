"""Reading a JSON-lines log: one model per line, in `<root>/<YYYY-MM>.jsonl`, the oldest file first.

A file is parsed once while its size and time are unchanged (mvp-store C6): an answer asks the collection log
several times, and a season of it is thousands of runs. An appended line changes both, so it's seen.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from fantadamus.lake.months import MONTH, month_of

_LOG = logging.getLogger(__name__)
_PARSED: dict[tuple[Path, type[BaseModel]], tuple[tuple[int, int], list[Any]]] = {}
"""Each file's lines as parsed, with the time and size it had then."""


def _parse[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    """Every line of the file it can read. A line it can't, half-written or written by a newer version, is
    skipped with a warning naming where it is, never what it says: one bad line mustn't stop every answer."""
    found: list[M] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            found.append(model.model_validate_json(line))
        except ValidationError:
            _LOG.warning("Skipped %s line %d: it can't be read", path.name, number)
    return found


def _lines[M: BaseModel](path: Path, model: type[M]) -> list[M]:
    """The file's lines, parsed again only if its time or size changed since they were kept."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return []
    mark = (stat.st_mtime_ns, stat.st_size)
    kept = _PARSED.get((path, model))
    if kept is not None and kept[0] == mark:
        lines: list[M] = kept[1]
        return lines
    found = _parse(path, model)
    _PARSED[(path, model)] = (mark, found)
    return found


def read_lines[M: BaseModel](root: Path, model: type[M], since: dt.datetime | None = None) -> list[M]:
    """Every line it can read, in order, in a list of its own: the models in it are shared, and never to be
    changed. With `since`, only the files from the month of the day before it on: a line goes to the file of
    the month it began in, and what began late on a month's last day may have gone on after midnight."""
    first = month_of(since - dt.timedelta(days=1)) if since is not None else None
    found: list[M] = []
    for path in sorted(root.glob("*.jsonl")):
        if first is None or not MONTH.fullmatch(path.stem) or path.stem >= first:
            found.extend(_lines(path, model))
    return found
