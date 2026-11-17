"""mvp-store task 3.2: `Facts` reads the five tables that grow with every read as each page's newest
submission, keeps its window's start, and reads them again as they stood when an answer is about an earlier
time; calibration reads every row of its window (design C5; R3.2, R3.5)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fantadamus.contracts.xy.lineups import ProbableLineupPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains import facts
from fantadamus.domains.availability.silver import LINEUP_VIEWS
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.advisor import Facts
from tests.property.collect.test_forecast import READ, _filled
from tests.store_lake import newest_submissions
from tests.xy_harness import CLUBS, NOW, URL, alfa_team, lineup

DAY = dt.timedelta(days=1)
KEYS = ("home", "away", "outlet")
READS = (NOW - 20 * DAY, NOW - 10 * DAY, NOW - 3 * DAY, NOW - DAY)
"""One outlet's lineup for Alfa v Beta, read from one page four times, different each time."""


NOVE = ("starter", "bench", "ballottaggio", "unavailable")
"""Alfa Nove, in each of the four reads."""


def _lineup(index: int) -> ProbableLineupPayload:
    payload = lineup("Alfa", "Beta", "Uno") | {"home_team": alfa_team(NOVE[index])}
    return ProbableLineupPayload.model_validate_json(json.dumps(payload))


def _stored(store: LakeStore) -> None:
    for index, at in enumerate(READS):
        facts.submit(
            store,
            LINEUP_VIEWS,
            _lineup(index),
            source_url=URL,
            captured_at=at,
            published_at=None,
            allowed_hosts=["example.org"],
            clock=fixed_clock(at),
            submitted_by="user-1",
            clubs=CLUBS,
        )


def test_calibration_reads_everything(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    _stored(store)
    every = Facts.read(store, NOW, history=True)
    reduced = Facts.read(store, NOW)
    assert {row.captured_at for row in every.views} == set(READS[1:])  # every read in the window
    assert {row.captured_at for row in reduced.views} == {READS[-1]}  # the page's newest
    assert reduced.views == newest_submissions(every.views, KEYS)
    assert every.since == reduced.since == NOW - FACTS_WINDOW
    assert (every.as_of, reduced.as_of) == (NOW, NOW)
    assert every.at(store, NOW - 2 * DAY) is every  # every row is already there


def test_a_movement_reads_the_same_window(tmp_path: Path) -> None:
    """As they stood two days back, over the window of the answer: not the one of two days back."""
    store = LakeStore(tmp_path)
    _stored(store)
    now = Facts.read(store, NOW)
    then = now.at(store, NOW - 2 * DAY)
    assert (then.since, then.as_of) == (now.since, NOW - 2 * DAY)
    assert {row.captured_at for row in then.views} == {READS[2]}
    every = Facts.read(store, NOW, history=True).views
    assert then.views == newest_submissions(every, KEYS, now.since, NOW - 2 * DAY)
    assert then.fixtures is now.fixtures  # the others are the answer's own
    assert now.at(store, NOW) is now
    assert now.at(store, READS[-1] + dt.timedelta(hours=1)) is now  # nothing kept is later: no read again
    assert now.at(store, NOW + DAY) is now  # nothing captured after it was read is in it anyway
    assert now.at(store, NOW - 15 * DAY).views == []  # before the window's start


def test_an_answer_about_an_earlier_time_reads_it_as_it_stood(tmp_path: Path) -> None:
    """Facts read now, asked about an hour ago: the lineup that came since replaced the one read before it in
    the newest read, and the answer must still see the earlier one."""
    store = LakeStore(tmp_path)
    advisor, _ = _filled(store)
    later = READ + dt.timedelta(minutes=30)
    facts.submit(
        store,
        LINEUP_VIEWS,
        ProbableLineupPayload.model_validate_json(
            json.dumps(lineup("Alfa", "Beta", "Uno") | {"home_team": alfa_team("bench")})
        ),
        source_url=URL,
        captured_at=later,
        published_at=None,
        allowed_hosts=["example.org"],
        clock=fixed_clock(later),
        submitted_by="user-1",
        clubs=CLUBS,
    )
    earlier = READ + dt.timedelta(minutes=10)
    names = ("Alfa Nove", "Gamma Nove")
    asked = advisor.answer_at(names, earlier, facts=Facts.read(store, NOW))
    assert asked == advisor.answer_at(names, earlier, facts=Facts.read(store, earlier))
    assert asked.answer is not None
    after = later + dt.timedelta(minutes=1)
    assert asked != advisor.answer_at(names, after, facts=Facts.read(store, after))  # the later lineup counts
