"""The collection log: one JSON line per collector run (mvp-collect design C9; R8.2).

Runs go to `<root>/<YYYY-MM>.jsonl`, by default under the git-ignored `data/local/collect/`. `last` is the
newest run, `last_worked` the newest time each page was read, whether it stored facts or found them unchanged,
and `confirmed` when each page last confirmed a table's facts unchanged, which keeps them fresh (R1.5).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fantadamus.web.collector import CollectReport, PageReport

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

    def last_worked(self, as_of: dt.datetime | None = None) -> dict[str, dt.datetime]:
        """For each page, the newest time (at or before `as_of`) it was read and gave facts."""
        worked: dict[str, dt.datetime] = {}
        for page, fetched_at in self._reads(as_of):
            if page.outcome in _WORKED:
                worked[page.url] = max(fetched_at, worked.get(page.url, fetched_at))
        return worked

    def confirmed(self, as_of: dt.datetime) -> dict[str, dict[str, dt.datetime]]:
        """By table, then page: the newest read at or before `as_of` that found the facts unchanged."""
        found: dict[str, dict[str, dt.datetime]] = {}
        for page, fetched_at in self._reads(as_of):
            for table in page.confirmed:
                pages = found.setdefault(table, {})
                pages[page.url] = max(fetched_at, pages.get(page.url, fetched_at))
        return found

    def _reads(self, as_of: dt.datetime | None) -> Iterator[tuple[PageReport, dt.datetime]]:
        for run in self.runs():
            for page in run.pages:
                if page.fetched_at is not None and (as_of is None or page.fetched_at <= as_of):
                    yield page, page.fetched_at
