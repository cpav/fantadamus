"""The collector: Fantadamus reads Fantacalcio-Online's round page itself and stores its facts (mvp-collect
design C6; R1.1, R1.4, R2.4, R2.5, R3.4).

A run fetches the round page once, politely (C1), reads it with the round-page reader (C3.1), and stores each
kind of fact with `facts.submit_many` as `collector`: the fetch time is `captured_at`, and the odds carry the
page's own update time. A kind of fact whose payloads are the same as at the page's last stored read stores
nothing new (R1.4). The report says what was stored or why nothing was, and when the page couldn't be used it
names the facts Claude reads instead (R8.1).
"""

from __future__ import annotations

import datetime as dt
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.domains.availability.silver import OFFICIAL_LINEUPS, OUTLET_VIEWS
from fantadamus.domains.facts import (
    Domain,
    RefusedError,
    Submission,
    last_read,
    payload_hash,
    submit_many,
)
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.odds.silver import ODDS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.fetch import DisallowedError, Fetcher, FetchError, HostBlockedError, NotAllowedError
from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fco import RoundFacts, read_round

DEFAULT_READING_LIST = Path("config/reading_list.toml")
COLLECTOR = "collector"
ROUND_FACTS = ("fixtures", "probable_lineups", "official_lineups", "match_odds")
"""The reading list's facts the round page carries: Claude's to read when the page can't be used."""

Outcome = Literal[
    "stored",
    "unchanged",
    "rejected",
    "switched off",
    "not allowed",
    "disallowed",
    "blocked",
    "failed",
    "unreadable",
]
Submissions = dict[Domain[Any, Any], list[Submission[Any]]]


class RoundPageConfig(BaseModel):
    """The `[collector]` table in `config/reading_list.toml`: where the round page is, and if it's read."""

    enabled: bool = True
    current_round: str
    round: str
    """The address of round n, with `{round}` for n."""


def load_round_page(path: Path = DEFAULT_READING_LIST) -> RoundPageConfig:
    return RoundPageConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8"))["collector"])


class PageReport(BaseModel):
    url: str
    outcome: Outcome
    reason: str | None = None
    fetched_at: dt.datetime | None = None
    stored: dict[str, int] = {}
    """Silver rows stored, per table; a kind of fact left unchanged isn't listed."""
    problems: list[str] = []
    """Payloads left out, and why."""
    for_claude: list[str] = []
    """The facts Claude reads instead, when the page couldn't be used."""


class CollectReport(BaseModel):
    started_at: dt.datetime
    finished_at: dt.datetime
    round: int | None
    """The round asked for; None for the current one."""
    pages: list[PageReport]


def submissions(facts: RoundFacts) -> Submissions:
    """Each kind of fact the round page gave, ready to store."""
    return {
        FIXTURES: [Submission(facts.fixtures)],
        ODDS: [Submission(odds.payload, odds.published_at) for odds in facts.odds],
        OUTLET_VIEWS: [Submission(view) for view in facts.outlets],
        OFFICIAL_LINEUPS: [Submission(official) for official in facts.officials],
    }


def to_store(new: Submissions, last: Mapping[str, set[str]]) -> Submissions:
    """The kinds of fact whose payloads differ from the page's last stored read (`last`, content hashes by
    domain source): the rest would store nothing new."""
    return {
        domain: items
        for domain, items in new.items()
        if items and {payload_hash(item.payload) for item in items} != last.get(domain.source, set())
    }


def _outcome(error: FetchError) -> Outcome:
    if isinstance(error, NotAllowedError):
        return "not allowed"
    if isinstance(error, DisallowedError):
        return "disallowed"
    if isinstance(error, HostBlockedError):
        return "blocked"
    return "failed"


@dataclass(frozen=True)
class Collector:
    fetcher: Callable[[], Fetcher]
    """A new fetcher for each run: a host that blocks is stopped for that run only (R2.3)."""
    lake: LakeStore
    clubs: Clubs
    page: RoundPageConfig
    allowed_hosts: tuple[str, ...]
    clock: Clock

    def collect(self, round: int | None = None) -> CollectReport:
        """Read round `round`'s page, or the current round's, and store what's new."""
        started = self.clock()
        report = self._round_page(round)
        return CollectReport(started_at=started, finished_at=self.clock(), round=round, pages=[report])

    def _round_page(self, round: int | None) -> PageReport:
        url = self.page.round.format(round=round) if round is not None else self.page.current_round
        if not self.page.enabled:
            return PageReport(url=url, outcome="switched off", for_claude=list(ROUND_FACTS))
        try:
            fetched = self.fetcher().fetch(url)
        except FetchError as error:
            return PageReport(
                url=url, outcome=_outcome(error), reason=str(error), for_claude=list(ROUND_FACTS)
            )
        try:
            facts = read_round(fetched.text, round)
        except UnreadablePageError as error:
            return PageReport(
                url=fetched.url,
                outcome="unreadable",
                reason=str(error),
                fetched_at=fetched.fetched_at,
                for_claude=list(ROUND_FACTS),
            )
        new = submissions(facts)
        last = {domain.source: last_read(self.lake, domain, fetched.url) for domain in new}
        stored: dict[str, int] = {}
        problems = list(facts.problems)
        changed = to_store(new, last)
        try:
            for domain, items in changed.items():
                result = submit_many(
                    self.lake,
                    domain,
                    items,
                    source_url=fetched.url,
                    captured_at=fetched.fetched_at,
                    allowed_hosts=self.allowed_hosts,
                    clock=self.clock,
                    submitted_by=COLLECTOR,
                    clubs=self.clubs,
                )
                if result.receipts:
                    stored[domain.table.name] = sum(receipt.rows for receipt in result.receipts)
                problems += [f"{domain.source} {item.index}: {item.reason}" for item in result.rejections]
        except RefusedError as error:
            return PageReport(
                url=fetched.url, outcome="not allowed", reason=str(error), for_claude=list(ROUND_FACTS)
            )
        if changed and not stored:  # something new, and every payload refused: the facts are Claude's
            return PageReport(
                url=fetched.url,
                outcome="rejected",
                reason="every payload was refused",
                fetched_at=fetched.fetched_at,
                problems=problems,
                for_claude=list(ROUND_FACTS),
            )
        return PageReport(
            url=fetched.url,
            outcome="stored" if stored else "unchanged",
            fetched_at=fetched.fetched_at,
            stored=stored,
            problems=problems,
        )
