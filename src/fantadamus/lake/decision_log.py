"""The decision log: one JSON line per answer, appended and never changed (design C12; R14, method §A8).

Files are `<root>/<YYYY-MM>.jsonl` by the answer's as-of month, under the git-ignored `data/local/`. Nothing
here opens a file except to append to it or read it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.lake.jsonl import read_lines
from fantadamus.league.rules import StoredRules

DEFAULT_ROOT = Path("data/local/decisions")


class LoggedPlayer(BaseModel):
    player_id: int
    name: str
    p_start: float
    p_cameo: float
    p_rating: float | None = None
    """His chance of a rating. Lines older than the cameo's fix (mvp-lineup R8.3) don't have it, and their
    `p_cameo` is his chance of coming on, so calibration can't score them on it."""
    p_scores: float | None = None
    """An outfield player's; a keeper has P(clean sheet) instead (mvp-roles R6.3)."""
    key: float
    p_clean_sheet: float | None = None
    expected_conceded: float | None = None


class Decision(BaseModel):
    """Every published probability of one answer, its verdict if it has one, the rules and the facts it used
    (R14.1; mvp-roles R5.3). Lines logged before there were other kinds are comparisons."""

    kind: Literal["compare", "outlooks", "outlook", "lineup"] = "compare"
    as_of: UtcDatetime
    logged_at: UtcDatetime
    user: str
    round: int
    players: list[LoggedPlayer]
    first: str | None = None
    second: str | None = None
    margin: float | None = None
    """What the choice was worth (mvp-lineup R8.1); in lines older than that, the difference in keys."""
    label: str | None = None
    rules: StoredRules
    content_hashes: list[str]
    team: str | None = None
    """A lineup's: whose squad it was (mvp-lineup R1.5, R7.1)."""
    formation: str | None = None
    expected: float | None = None
    thresholds: dict[str, float] | None = None
    """The chance of reaching each threshold, by its points."""
    starters: list[int] | None = None
    bench: list[int] | None = None
    """A lineup's players, by ID, in order (mvp-lineup R7.1)."""
    override_cost: float | None = None
    """What the user's own choice cost against the advice, in expected points (mvp-lineup R3.5)."""
    advised_starters: list[int] | None = None
    """With an override: who the advice would have fielded."""
    advised_formation: str | None = None
    """With an override, since mvp-review: the rest of the advice, so a review can compare with it."""
    advised_bench: list[int] | None = None
    advised_captain: int | None = None
    advised_vice: int | None = None
    rules_worth: dict[str, float] | None = None
    """What each of the league's formula rules added on average in this lineup (mvp-rules R3.2)."""
    captain: int | None = None
    """Where the league has a captain: who was told to wear the armband, and his vice (mvp-rules R3.3)."""
    vice: int | None = None


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
        return read_lines(self.root, Decision)
