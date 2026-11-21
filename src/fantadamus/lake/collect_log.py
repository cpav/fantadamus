"""The collection log: one JSON line per collector run (mvp-collect design C9; R8.2).

Runs go to `<root>/<YYYY-MM>.jsonl`, by default under the git-ignored `data/local/collect/`. `last` is the
newest run, `last_worked` the newest time each page was read, whether it stored facts or found them unchanged,
and `confirmed` when each page last confirmed a table's facts unchanged, which keeps them fresh (R1.5).
`last_answered` is the newest try at a page that got the site's answer, the read the cadence counts, and
`last_failed` the newest that got none (mvp-fixes R1.2).

Each takes `since`: the runs from then on are enough for an answer, whose rows are all captured in its window,
and for the schedule, whose cadences are a week at most (mvp-store C6). A run before it may still be read, as
the log is read a month's file at a time.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from fantadamus.lake.jsonl import read_lines
from fantadamus.web.collector import CollectReport, Outcome, PageKind, PageReport

DEFAULT_ROOT = Path("data/local/collect")
WORKED = {"stored", "unchanged"}
"""A read that gave facts, whether or not they were new."""
FAILED: frozenset[Outcome] = frozenset({"failed"})
"""A try that got no answer from the site: tried again at the next run (mvp-fixes R1.2)."""
ANSWERED: frozenset[Outcome] = frozenset(get_args(Outcome)) - FAILED
"""A try that got the site's answer, or the collector's own setting: it counts as the page's read."""


def newest(
    runs: Sequence[CollectReport], as_of: dt.datetime, page: PageKind, outcomes: Collection[Outcome]
) -> dt.datetime | None:
    """When the newest of `runs` at or before `as_of` that tried `page` with one of `outcomes` started."""
    return max(
        (
            run.started_at
            for run in runs
            if run.started_at <= as_of
            and any(report.page == page and report.outcome in outcomes for report in run.pages)
        ),
        default=None,
    )


@dataclass(frozen=True)
class CollectLog:
    root: Path = DEFAULT_ROOT

    def append(self, report: CollectReport) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / f"{report.started_at:%Y-%m}.jsonl").open("a", encoding="utf-8") as log:
            log.write(report.model_dump_json() + "\n")

    def runs(self, since: dt.datetime | None = None) -> list[CollectReport]:
        """Every run it can read, oldest first; with `since`, from the files of then on."""
        return read_lines(self.root, CollectReport, since)

    def last(self) -> CollectReport | None:
        runs = self.runs()
        return runs[-1] if runs else None

    def last_attempt(
        self, as_of: dt.datetime, page: PageKind = "round", since: dt.datetime | None = None
    ) -> dt.datetime | None:
        """When the newest run at or before `as_of` that tried `page` started, whatever came of it."""
        return max(
            (
                run.started_at
                for run in self.runs(since)
                if run.started_at <= as_of and any(report.page == page for report in run.pages)
            ),
            default=None,
        )

    def last_answered(
        self, as_of: dt.datetime, page: PageKind = "round", since: dt.datetime | None = None
    ) -> dt.datetime | None:
        """When the newest run at or before `as_of` that got the site's answer for `page` started: the read
        the cadence counts (mvp-fixes R1.2)."""
        return newest(self.runs(since), as_of, page, ANSWERED)

    def last_failed(
        self, as_of: dt.datetime, page: PageKind = "round", since: dt.datetime | None = None
    ) -> dt.datetime | None:
        """When the newest run at or before `as_of` whose try at `page` got no answer started (mvp-fixes
        R1.2)."""
        return newest(self.runs(since), as_of, page, FAILED)

    def last_worked(
        self, as_of: dt.datetime | None = None, since: dt.datetime | None = None
    ) -> dict[str, dt.datetime]:
        """For each page, the newest time (at or before `as_of`) it was read and gave facts."""
        worked: dict[str, dt.datetime] = {}
        for page, fetched_at in self._reads(as_of, since):
            if page.outcome in WORKED:
                worked[page.url] = max(fetched_at, worked.get(page.url, fetched_at))
        return worked

    def worked(
        self, page: PageKind, as_of: dt.datetime, since: dt.datetime | None = None
    ) -> list[dt.datetime]:
        """When this kind of page was read and gave facts, at or before `as_of`."""
        return [
            fetched_at
            for report, fetched_at in self._reads(as_of, since)
            if report.page == page and report.outcome in WORKED
        ]

    def confirmed(
        self, as_of: dt.datetime, since: dt.datetime | None = None
    ) -> dict[str, dict[str, dt.datetime]]:
        """By table, then page: the newest read at or before `as_of` that found the facts unchanged."""
        found: dict[str, dict[str, dt.datetime]] = {}
        for page, fetched_at in self._reads(as_of, since):
            for table in page.confirmed:
                pages = found.setdefault(table, {})
                pages[page.url] = max(fetched_at, pages.get(page.url, fetched_at))
        return found

    def _reads(
        self, as_of: dt.datetime | None, since: dt.datetime | None
    ) -> Iterator[tuple[PageReport, dt.datetime]]:
        for run in self.runs(since):
            for page in run.pages:
                if page.fetched_at is not None and (as_of is None or page.fetched_at <= as_of):
                    yield page, page.fetched_at
