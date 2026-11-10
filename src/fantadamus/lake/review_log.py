"""The review log: every lineup review, appended privately, one JSON line each (mvp-review design C7; R4.1).

One file per month under the git-ignored `data/local/reviews/`. A review names a team's real lineup, so the
log never reaches the repository. Lines are only ever appended; a later review of the same round and team
takes over in the record, and the earlier one stays.
"""

from __future__ import annotations

from pathlib import Path

from fantadamus.domains.review import LoggedReview
from fantadamus.lake.jsonl import read_lines

DEFAULT_ROOT = Path("data/local/reviews")


class ReviewLog:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def append(self, review: LoggedReview) -> Path:
        path = self.root / f"{review.logged_at:%Y-%m}.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(review.model_dump_json() + "\n")
        return path

    def read(self) -> list[LoggedReview]:
        return read_lines(self.root, LoggedReview)
