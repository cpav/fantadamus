"""The collection log: one JSON line per collector run (mvp-collect design C9; R8.2).

Runs go to `<root>/<YYYY-MM>.jsonl`, by default under the git-ignored `data/local/collect/`. `last` is the
newest run, and `last_worked` the newest time each page was read, whether it stored facts or found them
unchanged.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from fantadamus.web.collector import CollectReport

DEFAULT_ROOT = Path("data/local/collect")
_WORKED = {"stored", "unchanged"}


@dataclass(frozen=True)
class CollectLog:
    root: Path = DEFAULT_ROOT

    def append(self, report: CollectReport) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / f"{report.started_at:%Y-%m}.jsonl").open("a", encoding="utf-8") as log:
            log.write(report.model_dump_json() + "\n")

    def runs(self) -> list[CollectReport]:
        """Every run, oldest first."""
        return [
            CollectReport.model_validate_json(line)
            for path in sorted(self.root.glob("*.jsonl"))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def last(self) -> CollectReport | None:
        runs = self.runs()
        return runs[-1] if runs else None

    def last_worked(self) -> dict[str, dt.datetime]:
        """For each page, the newest time it was read and gave facts."""
        worked: dict[str, dt.datetime] = {}
        for run in self.runs():
            for page in run.pages:
                if page.outcome in _WORKED and page.fetched_at is not None:
                    worked[page.url] = max(page.fetched_at, worked.get(page.url, page.fetched_at))
        return worked
