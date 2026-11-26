"""mvp-next-round AT-1: the next round is stored at the first run 24 hours after the round page's last
answered read, and from then on its lineups and odds keep today's cadence (R1.1, R1.3, R1.4)."""

from __future__ import annotations

import datetime as dt
import itertools
from pathlib import Path

from tests.next_round_harness import DAY, FIRST, HOUR, MINUTE, RUN, a_schedule, moving_on

SECOND = FIRST + dt.timedelta(days=6, hours=5, minutes=45)
"""Round 11's deadline: as far after round 10's as round 13's was after round 12's."""


def test_at1_the_next_round_is_found_in_time(tmp_path: Path) -> None:
    here = a_schedule(tmp_path, moving_on(SECOND))
    here.runs(FIRST - 2 * HOUR, FIRST)
    last = here.log.last_answered(FIRST)
    assert last is not None
    assert here.next_round(FIRST) is None  # round 10 has locked, its second match still to come

    [(found_at, report)] = here.runs(FIRST, last + DAY + RUN)
    assert last + DAY <= found_at < last + DAY + RUN
    assert report.due == ["fixtures"]
    assert [page.stored for page in report.pages] == [{"fixtures": 2}]  # an early page: its fixtures alone
    assert here.next_round(found_at) == 11
    assert found_at < SECOND - DAY  # before round 11's alert window opens

    early = here.runs(found_at + RUN, SECOND - 72 * HOUR, HOUR)
    assert early
    assert [run.due for _, run in early] == [["fixtures"]] * len(early)  # once a day, until the last three
    window = here.runs(SECOND - 72 * HOUR, SECOND - 2 * HOUR, HOUR) + here.runs(SECOND - 2 * HOUR, SECOND)
    assert all(len(run.pages) == 1 for _, run in early + window)  # one read of the page a run
    last_day = [when for when, run in window if "probable_lineups" in run.due and SECOND - when <= DAY]
    assert len(last_day) >= 7
    assert all(later - earlier >= 3 * HOUR for earlier, later in itertools.pairwise(last_day))
    officials = [when for when, run in window if "official_lineups" in run.due]
    assert officials[0] == SECOND - 75 * MINUTE
