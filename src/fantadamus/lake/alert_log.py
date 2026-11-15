"""The alert log: one JSON line per call compared, appended and never changed (mvp-alerts C5; R3.2, R4.2).

Files are `<root>/<YYYY-MM>.jsonl` by the line's time, under the git-ignored `data/local/`. A `baseline` line
is a call kept to compare with, nothing sent; an `alert` line is a changed call and what was sent about it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.domains.alerts import Call, Change
from fantadamus.lake.jsonl import read_lines

DEFAULT_ROOT = Path("data/local/alerts")


class AlertLine(BaseModel):
    kind: Literal["baseline", "alert"]
    logged_at: UtcDatetime
    user: str
    team: str
    round: int
    call: Call
    changes: list[Change] = []
    title: str | None = None
    subtitle: str | None = None
    text: str | None = None
    delivered: bool | None = None
    """Whether macOS took the notification; None for a baseline."""
    reason: str | None = None
    """Why it didn't, or why the call became a baseline."""


class AlertLog:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def append(self, line: AlertLine) -> Path:
        path = self.root / f"{line.logged_at:%Y-%m}.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(line.model_dump_json() + "\n")
        return path

    def read(self) -> list[AlertLine]:
        return read_lines(self.root, AlertLine)
