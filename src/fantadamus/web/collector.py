"""The collector: Fantadamus reads Fantacalcio-Online's round page and Fantacalcio.it's statistics, penalty
takers and table pages itself and stores their facts (mvp-collect design C6; R1.1, R1.4, R2.4, R2.5, R3.4;
mvp-roles design C4; mvp-lineup C13; mvp-cards C1).

A run fetches each page its facts call for once, politely (C1), with one fetcher for the run, reads it with
its reader (C3.1), and stores each kind of fact with `facts.submit_many` as `collector`: the fetch time is
`captured_at`, and the odds carry the page's own update time. A kind of fact whose payloads are the same as at
the page's last stored read stores nothing new (R1.4). Each page gets its own report, which says what was
stored or why nothing was, and when the page couldn't be used names the facts Claude reads instead (R8.1).
"""

from __future__ import annotations

import datetime as dt
import tomllib
from collections.abc import Callable, Collection, Mapping
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
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.season.silver import PENALTY_TAKERS, SEASON_STATS, TEAM_SEASONS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.fetch import DisallowedError, Fetcher, FetchError, HostBlockedError, NotAllowedError, Page
from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_stats import StatsFacts, read_stats
from fantadamus.web.readers.fcit_table import TableFacts, read_table
from fantadamus.web.readers.fcit_takers import TakersFacts, read_takers
from fantadamus.web.readers.fco import RoundFacts, read_round

DEFAULT_READING_LIST = Path("config/reading_list.toml")
COLLECTOR = "collector"
ROUND_FACTS = ("fixtures", "probable_lineups", "official_lineups", "match_odds")
"""The reading list's facts the round page carries: Claude's to read when the page can't be used."""
STATS_FACTS = ("player_season",)
"""And the statistics page's (mvp-roles R1.6)."""
TAKERS_FACTS = ("penalty_takers",)
"""And the penalty-takers page's (mvp-lineup R10.3)."""
TABLE_FACTS = ("team_season",)
"""And the table's (mvp-cards C1)."""
FACTS = ROUND_FACTS + STATS_FACTS + TAKERS_FACTS + TABLE_FACTS
PageKind = Literal["round", "statistics", "finished_round", "takers", "table"]
PAGE_FACTS: dict[PageKind, tuple[str, ...]] = {
    "round": ROUND_FACTS,
    "finished_round": ROUND_FACTS,
    "statistics": STATS_FACTS,
    "takers": TAKERS_FACTS,
    "table": TABLE_FACTS,
}


def page_of(fact: str) -> PageKind:
    """The kind of page that carries `fact`."""
    if fact in STATS_FACTS:
        return "statistics"
    if fact in TABLE_FACTS:
        return "table"
    return "takers" if fact in TAKERS_FACTS else "round"


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


class CollectorConfig(BaseModel):
    """The `[collector]` table in `config/reading_list.toml`: where the pages are, and if each is read."""

    enabled: bool = True
    """Whether the round page is read."""
    current_round: str
    round: str
    """The address of round n, with `{round}` for n."""
    statistics: str | None = None
    """The statistics page; None reads none (mvp-roles R1.1)."""
    statistics_enabled: bool = True
    takers: str | None = None
    """The penalty-takers page; None reads none (mvp-lineup R10.3)."""
    takers_enabled: bool = True
    table: str | None = None
    """The table; None reads none, and Claude submits it (mvp-cards C1)."""
    table_enabled: bool = True
    other_competitions: list[str] = []
    """Wikipedia's pages of the other competitions, as raw wikitext (mvp-sources C2, ADR-0007)."""
    injuries: str | None = None
    """Fantacalcio.it's injured page (mvp-sources C4)."""
    suspensions: str | None = None
    """Fantacalcio.it's suspended-and-diffidati page (mvp-sources C4)."""
    ratings: str | None = None
    """Fantacalcio-Online's round ratings page, with `{round}` for n (mvp-sources C6)."""


def load_collector(path: Path = DEFAULT_READING_LIST) -> CollectorConfig:
    return CollectorConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8"))["collector"])


class PageReport(BaseModel):
    url: str
    page: PageKind = "round"
    """Which page this is; lines logged before the statistics page was read are the round page's."""
    outcome: Outcome
    reason: str | None = None
    fetched_at: dt.datetime | None = None
    stored: dict[str, int] = {}
    """Silver rows stored, per table; a kind of fact left unchanged isn't listed."""
    confirmed: list[str] = []
    """Tables whose facts the page stated as at its last stored read: confirmed now, stored before (R1.5)."""
    problems: list[str] = []
    """Payloads left out, and why."""
    for_claude: list[str] = []
    """The facts Claude reads instead, when the page couldn't be used."""


class CollectReport(BaseModel):
    started_at: dt.datetime
    finished_at: dt.datetime
    round: int | None
    """The round asked for; None for the current one."""
    due: list[str] = []
    """For a scheduled run, the facts past their cadence that called for it (C7)."""
    pages: list[PageReport]


def submissions(facts: RoundFacts) -> Submissions:
    """Each kind of fact the round page gave, ready to store."""
    return {
        FIXTURES: [Submission(facts.fixtures)],
        ODDS: [Submission(odds.payload, odds.published_at) for odds in facts.odds],
        OUTLET_VIEWS: [Submission(view) for view in facts.outlets],
        OFFICIAL_LINEUPS: [Submission(official) for official in facts.officials],
    }


def season_submissions(facts: StatsFacts) -> Submissions:
    """The statistics page's one read, ready to store (mvp-roles C1)."""
    return {SEASON_STATS: [Submission(facts.payload)]}


def takers_submissions(facts: TakersFacts) -> Submissions:
    """The penalty-takers page's one read, ready to store (mvp-lineup C13)."""
    return {PENALTY_TAKERS: [Submission(facts.payload)]}


def table_submissions(facts: TableFacts) -> Submissions:
    """The table's one read, ready to store (mvp-cards C1)."""
    return {TEAM_SEASONS: [Submission(facts.payload)]}


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
    config: CollectorConfig
    allowed_hosts: tuple[str, ...]
    clock: Clock

    def reads(self, fact: str) -> bool:
        """Whether a page this collector reads carries `fact`."""
        return (
            fact in ROUND_FACTS
            or (fact in STATS_FACTS and self.config.statistics is not None)
            or (fact in TAKERS_FACTS and self.config.takers is not None)
            or (fact in TABLE_FACTS and self.config.table is not None)
        )

    def collect(self, round: int | None = None, facts: Collection[str] | None = None) -> CollectReport:
        """Read the pages that carry `facts`, by default the round page and, without `round`, the statistics,
        penalty-takers and table pages: round `round`'s page, or the current round's. Store what's new."""
        started = self.clock()
        wanted = set(facts) if facts is not None else set(ROUND_FACTS if round is not None else FACTS)
        fetcher = self.fetcher()
        reports = []
        if wanted & set(ROUND_FACTS):
            reports.append(self._round_page(fetcher, round))
        if wanted & set(STATS_FACTS) and self.config.statistics is not None:
            reports.append(self._statistics_page(fetcher, self.config.statistics))
        if wanted & set(TAKERS_FACTS) and self.config.takers is not None:
            reports.append(self._takers_page(fetcher, self.config.takers))
        if wanted & set(TABLE_FACTS) and self.config.table is not None:
            reports.append(self._table_page(fetcher, self.config.table))
        return CollectReport(started_at=started, finished_at=self.clock(), round=round, pages=reports)

    def collect_finished(self, round: int) -> CollectReport:
        """A finished round's page, for who really started (mvp-lineup R7.2). It's a kind of its own in the
        log, so that it doesn't count as an attempt at the current round's page."""
        started = self.clock()
        page = self._round_page(self.fetcher(), round, kind="finished_round")
        return CollectReport(started_at=started, finished_at=self.clock(), round=round, pages=[page])

    def _round_page(self, fetcher: Fetcher, round: int | None, *, kind: PageKind = "round") -> PageReport:
        url = self.config.round.format(round=round) if round is not None else self.config.current_round
        if not self.config.enabled:
            return PageReport(url=url, page=kind, outcome="switched off", for_claude=list(ROUND_FACTS))
        fetched = _fetch(fetcher, url, kind, ROUND_FACTS)
        if isinstance(fetched, PageReport):
            return fetched
        try:
            facts = read_round(fetched.text, round)
        except UnreadablePageError as error:
            return _unreadable(fetched, kind, ROUND_FACTS, error)
        return self._store(fetched, kind, ROUND_FACTS, submissions(facts), facts.problems)

    def _statistics_page(self, fetcher: Fetcher, url: str) -> PageReport:
        if not self.config.statistics_enabled:
            return PageReport(
                url=url, page="statistics", outcome="switched off", for_claude=list(STATS_FACTS)
            )
        fetched = _fetch(fetcher, url, "statistics", STATS_FACTS)
        if isinstance(fetched, PageReport):
            return fetched
        try:
            facts = read_stats(fetched.text)
        except UnreadablePageError as error:
            return _unreadable(fetched, "statistics", STATS_FACTS, error)
        return self._store(fetched, "statistics", STATS_FACTS, season_submissions(facts), facts.problems)

    def _takers_page(self, fetcher: Fetcher, url: str) -> PageReport:
        if not self.config.takers_enabled:
            return PageReport(url=url, page="takers", outcome="switched off", for_claude=list(TAKERS_FACTS))
        fetched = _fetch(fetcher, url, "takers", TAKERS_FACTS)
        if isinstance(fetched, PageReport):
            return fetched
        try:
            facts = read_takers(fetched.text)
        except UnreadablePageError as error:
            return _unreadable(fetched, "takers", TAKERS_FACTS, error)
        return self._store(fetched, "takers", TAKERS_FACTS, takers_submissions(facts), facts.problems)

    def _table_page(self, fetcher: Fetcher, url: str) -> PageReport:
        if not self.config.table_enabled:
            return PageReport(url=url, page="table", outcome="switched off", for_claude=list(TABLE_FACTS))
        fetched = _fetch(fetcher, url, "table", TABLE_FACTS)
        if isinstance(fetched, PageReport):
            return fetched
        try:
            facts = read_table(fetched.text)
        except UnreadablePageError as error:
            return _unreadable(fetched, "table", TABLE_FACTS, error)
        return self._store(fetched, "table", TABLE_FACTS, table_submissions(facts), facts.problems)

    def _store(
        self, fetched: Page, page: PageKind, carried: tuple[str, ...], new: Submissions, found: list[str]
    ) -> PageReport:
        """Store each kind of fact that changed since the page's last stored read (R1.4). A read older than an
        answer's window doesn't count, so that an unchanged page's facts stay where answers look for them."""
        since = fetched.fetched_at - FACTS_WINDOW
        last = {domain.source: last_read(self.lake, domain, fetched.url, since) for domain in new}
        stored: dict[str, int] = {}
        problems = list(found)
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
                url=fetched.url, page=page, outcome="not allowed", reason=str(error), for_claude=list(carried)
            )
        if changed and not stored:  # something new, and every payload refused: the facts are Claude's
            return PageReport(
                url=fetched.url,
                page=page,
                outcome="rejected",
                reason="every payload was refused",
                fetched_at=fetched.fetched_at,
                problems=problems,
                for_claude=list(carried),
            )
        return PageReport(
            url=fetched.url,
            page=page,
            outcome="stored" if stored else "unchanged",
            fetched_at=fetched.fetched_at,
            stored=stored,
            confirmed=[domain.table.name for domain, items in new.items() if items and domain not in changed],
            problems=problems,
        )


def _fetch(fetcher: Fetcher, url: str, page: PageKind, carried: tuple[str, ...]) -> Page | PageReport:
    try:
        return fetcher.fetch(url)
    except FetchError as error:
        return PageReport(
            url=url, page=page, outcome=_outcome(error), reason=str(error), for_claude=list(carried)
        )


def _unreadable(
    fetched: Page, page: PageKind, carried: tuple[str, ...], error: UnreadablePageError
) -> PageReport:
    return PageReport(
        url=fetched.url,
        page=page,
        outcome="unreadable",
        reason=str(error),
        fetched_at=fetched.fetched_at,
        for_claude=list(carried),
    )
