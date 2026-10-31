"""When the round page's facts are due for a fresh read, and the scheduled run that reads it then (mvp-collect
design C7; R7.1, R7.2).

| Fact | Cadence |
|---|---|
| Probable lineups | Twice a day from 72 hours before the match; every 3 hours in the last 24 |
| Official lineups | Every 15 minutes from 75 minutes before each kickoff until confirmed |
| Match odds | Daily from 72 hours before the match; every 3 hours in the last 24 |
| Fixtures | Weekly |

A match's facts stop being due at its kickoff: there's nothing left to forecast. The round page carries them
all, so each interval counts from the collector's last attempt at it, successful or not: a site that refuses
is asked again at the fact's own interval, not every 15 minutes. The matches are the next round's, whose
deadline is still ahead.
"""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.availability.silver import OFFICIAL_LINEUPS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.gold import matches, next_round
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.collector import Collector, CollectReport

SCHEDULED = ("fixtures", "probable_lineups", "official_lineups", "match_odds")
_HOUR = dt.timedelta(hours=1)
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


def due(
    fact: str,
    last_read: dt.datetime | None,
    now: dt.datetime,
    kickoff: dt.datetime | None,
    *,
    confirmed: bool = False,
) -> bool:
    """Whether `fact`, last read at `last_read` (None: never), is due at `now` for the match kicking off at
    `kickoff`; `confirmed` means the match's official lineup is already in."""
    if fact == "fixtures":
        every = 7 * 24 * _HOUR
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


def what_is_due(lake: LakeStore, log: CollectLog, now: dt.datetime) -> list[str]:
    """The round page's facts past their cadence at `now`, in the table's order."""
    last_read = log.last_attempt(now)
    fixtures = read_silver(lake, FIXTURES)
    round = next_round(fixtures, now)
    upcoming = [row for row in matches(fixtures, now) if row.round == round] if round is not None else []
    confirmed = {
        (row.home, row.away) for row in read_silver(lake, OFFICIAL_LINEUPS) if row.captured_at <= now
    }
    found = []
    for fact in SCHEDULED:
        if fact == "fixtures":
            if due(fact, last_read, now, None):
                found.append(fact)
        elif any(
            due(fact, last_read, now, row.kickoff_at, confirmed=(row.home, row.away) in confirmed)
            for row in upcoming
        ):
            found.append(fact)
    return found


def collect_due(collector: Collector, log: CollectLog) -> CollectReport | None:
    """`fantadamus collect --due`: read the round page if anything is due, and log the run; None when nothing
    is (R7.2: a scheduled run does nothing then)."""
    facts = what_is_due(collector.lake, log, collector.clock())
    if not facts:
        return None
    report = collector.collect().model_copy(update={"due": facts})
    log.append(report)
    return report
