"""The decision log: one JSON line per answer, appended and never changed (design C12; R14, method §A8).

Files are `<root>/<YYYY-MM>.jsonl` by the answer's as-of month, under the git-ignored `data/local/`. Nothing
here opens a file except to append to it or read it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.league.rules import StoredRules

DEFAULT_ROOT = Path("data/local/decisions")


class LoggedPlayer(BaseModel):
    player_id: int
    name: str
    p_start: float
    p_cameo: float
    p_scores: float | None = None
    """An outfield player's; a keeper has P(clean sheet) instead (mvp-roles R6.3)."""
    key: float
    p_clean_sheet: float | None = None
    expected_conceded: float | None = None


class Decision(BaseModel):
    """Every published probability of one answer, its verdict if it has one, the rules and the facts it used
    (R14.1; mvp-roles R5.3). Lines logged before there were other kinds are comparisons."""

    kind: Literal["compare", "outlooks", "outlook"] = "compare"
    as_of: UtcDatetime
    logged_at: UtcDatetime
    user: str
    round: int
    players: list[LoggedPlayer]
    first: str | None = None
    second: str | None = None
    margin: float | None = None
    label: str | None = None
    rules: StoredRules
    content_hashes: list[str]


class DecisionLog:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def append(self, decision: Decision) -> Path:
        path = self.root / f"{decision.as_of:%Y-%m}.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(decision.model_dump_json() + "\n")
        return path

    def read(self) -> list[Decision]:
        return [
            Decision.model_validate_json(line)
            for path in sorted(self.root.glob("*.jsonl"))
            for line in path.read_text(encoding="utf-8").splitlines()
        ]
