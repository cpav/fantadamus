"""When the round page's facts are due for a fresh read, and the scheduled run that reads it then (mvp-collect
design C7; R7.1, R7.2).

| Fact | Cadence |
|---|---|
| Probable lineups | Twice a day from 72 hours before the match; every 3 hours in the last 24 |
| Official lineups | Every 15 minutes from 75 minutes before each kickoff until confirmed |
| Match odds | Daily from 72 hours before the match; every 3 hours in the last 24 |
| Fixtures | Weekly |
| Players' season figures | Daily (mvp-roles R1.4) |
| Penalty takers | Daily (mvp-lineup R10.3) |
| The table | Daily (mvp-cards C1) |
| The other competitions' matches | Weekly; daily when one of them is in the coming week (mvp-sources C9) |
| Injuries and bans | Daily; twice a day in the 48 hours before the round's first kickoff (mvp-sources C9) |
| Round ratings | Once a round, the morning after its last match (mvp-sources C9) |

A match's facts stop being due at its kickoff: there's nothing left to forecast. Each interval counts from the
collector's last attempt at the page that carries the fact, successful or not: a site that refuses is asked
again at the fact's own interval, not every 15 minutes. The matches are the next round's, whose deadline is
still ahead. A scheduled run reads only the pages whose facts are due, and an answer that finds a fact missing
leaves alone a page tried moments ago: it has nothing new for a name it doesn't list or odds it doesn't show.
"""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.availability.silver import OFFICIAL_LINEUPS
from fantadamus.domains.calibration import finished_round
from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.gold import matches, next_round
from fantadamus.domains.fixtures.silver import FIXTURES, OTHER_FIXTURES
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.collector import Collector, CollectReport, PageKind, page_of

SCHEDULED = (
    "fixtures",
    "probable_lineups",
    "official_lineups",
    "match_odds",
    "player_season",
    "penalty_takers",
    "team_season",
    "other_fixtures",
    "injuries",
    "suspensions",
    "match_ratings",
)
_HOUR = dt.timedelta(hours=1)
_ALWAYS = {
    "fixtures": 7 * 24 * _HOUR,
    "player_season": 24 * _HOUR,
    "penalty_takers": 24 * _HOUR,
    "team_season": 24 * _HOUR,
    "other_fixtures": 7 * 24 * _HOUR,
    "injuries": 24 * _HOUR,
    "suspensions": 24 * _HOUR,
}
"""Due at these intervals whatever the matches."""
_WEEK = 7 * 24 * _HOUR
_MATCH_WEEK = {"other_fixtures": 24 * _HOUR}
"""Due at these intervals instead when one of the fact's own matches is in the coming week."""
_BEFORE_ROUND = 48 * _HOUR
_NEAR_ROUND = {"injuries": 12 * _HOUR, "suspensions": 12 * _HOUR}
"""Due at these intervals instead in the 48 hours before the round's first kickoff."""
_MORNING_AFTER = {"match_ratings": 12 * _HOUR}
"""Due once a round, this long after its last kickoff: the morning after."""
_WINDOW = {
    "probable_lineups": 72 * _HOUR,
    "match_odds": 72 * _HOUR,
    "official_lineups": dt.timedelta(minutes=75),
}
_EVERY = {
    "probable_lineups": 12 * _HOUR,
    "match_odds": 24 * _HOUR,
    "official_lineups": dt.timedelta(minutes=15),
}
_LAST_DAY = {"probable_lineups": 3 * _HOUR, "match_odds": 3 * _HOUR}
_ON_DEMAND_EVERY: dict[PageKind, dt.timedelta] = {
    "round": dt.timedelta(minutes=15),
    "statistics": 24 * _HOUR,
    "finished_round": dt.timedelta(minutes=15),
    "takers": 24 * _HOUR,
    "table": 24 * _HOUR,
    "other_fixtures": 24 * _HOUR,
    "injuries": 12 * _HOUR,
    "suspensions": 12 * _HOUR,
    "ratings": 12 * _HOUR,
}
"""The shortest interval of each page's facts in the table."""


def due(
    fact: str,
    last_read: dt.datetime | None,
    now: dt.datetime,
    kickoff: dt.datetime | None,
    *,
    confirmed: bool = False,
) -> bool:
    """Whether `fact`, last read at `last_read` (None: never), is due at `now` for the match kicking off at
    `kickoff`; `confirmed` means the match's official lineup is already in. For the other competitions'
    matches, `kickoff` is the next of them; for injuries and bans, the next round's first; for the ratings,
    the last of the round just played."""
    if fact in _MORNING_AFTER:
        if kickoff is None:
            return False
        morning = kickoff + _MORNING_AFTER[fact]
        return now >= morning and (last_read is None or last_read < morning)
    if fact in _ALWAYS:
        if fact in _MATCH_WEEK and kickoff is not None and now <= kickoff <= now + _WEEK:
            every = _MATCH_WEEK[fact]
        elif fact in _NEAR_ROUND and kickoff is not None and now <= kickoff <= now + _BEFORE_ROUND:
            every = _NEAR_ROUND[fact]
        else:
            every = _ALWAYS[fact]
    elif (
        kickoff is None
        or now >= kickoff
        or kickoff - now > _WINDOW[fact]
        or (fact == "official_lineups" and confirmed)
    ):
        return False
    elif kickoff - now <= 24 * _HOUR and fact in _LAST_DAY:
        every = _LAST_DAY[fact]
    else:
        every = _EVERY[fact]
    return last_read is None or now - last_read >= every


def may_read(fact: str, log: CollectLog | None, now: dt.datetime) -> bool:
    """Whether an answer may ask the collector for `fact` now (mvp-collect R1.4)."""
    return may_read_page(page_of(fact), log, now)


def may_read_page(page: PageKind, log: CollectLog | None, now: dt.datetime) -> bool:
    """Whether this kind of page may be read now: each has its shortest interval."""
    if log is None:
        return True
    last = log.last_attempt(now, page, since=now - FACTS_WINDOW)
    return last is None or now - last >= _ON_DEMAND_EVERY[page]


def what_is_due(lake: LakeStore, log: CollectLog, now: dt.datetime) -> list[str]:
    """The facts past their cadence at `now`, in the table's order. A cadence is a week at most, so the
    attempts of the window are enough: an older one would be due all the same."""
    since = now - FACTS_WINDOW
    last_read = log.last_attempt(now, since=since)
    fixtures = read_silver(lake, FIXTURES)
    round = next_round(fixtures, now)
    upcoming = [row for row in matches(fixtures, now) if row.round == round] if round is not None else []
    officials = read_silver(lake, OFFICIAL_LINEUPS, since, now, newest=True)
    confirmed = {(row.home, row.away) for row in officials}  # a match asked about kicks off within days
    other = min(
        (
            row.kickoff_at
            for row in read_silver(lake, OTHER_FIXTURES)
            if row.captured_at <= now <= row.kickoff_at
        ),
        default=None,
    )
    found = []
    first = min((row.kickoff_at for row in upcoming), default=None)
    played = finished_round(fixtures, now)
    last = max((row.kickoff_at for row in matches(fixtures, now) if row.round == played), default=None)
    for fact in SCHEDULED:
        if fact in _MORNING_AFTER:
            if due(fact, log.last_attempt(now, page_of(fact), since), now, last):
                found.append(fact)
        elif fact in _ALWAYS:
            kickoff = other if fact in _MATCH_WEEK else first if fact in _NEAR_ROUND else None
            if due(fact, log.last_attempt(now, page_of(fact), since), now, kickoff):
                found.append(fact)
        elif any(
            due(fact, last_read, now, row.kickoff_at, confirmed=(row.home, row.away) in confirmed)
            for row in upcoming
        ):
            found.append(fact)
    return found


def collect_due(collector: Collector, log: CollectLog) -> CollectReport | None:
    """`fantadamus collect --due`: read the pages whose facts are due, and log the run; None when nothing is
    (R7.2: a scheduled run does nothing then). A fact no page of this collector carries isn't due."""
    facts = [fact for fact in what_is_due(collector.lake, log, collector.clock()) if collector.reads(fact)]
    if not facts:
        return None
    report = collector.collect(facts=facts).model_copy(update={"due": facts})
    log.append(report)
    return report
