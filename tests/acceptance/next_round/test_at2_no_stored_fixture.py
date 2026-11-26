"""mvp-next-round AT-2: no stored fixture holds the daily read back: a locked round's later matches, a match
postponed from an earlier round, or a later round stored by hand (R1.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.web.cadence import what_is_due
from tests.collect_pages import FcoMatch
from tests.next_round_harness import BASE, DAY, FIRST, HOUR, MINUTE, RUN, a_schedule, moving_on, round_page

SECOND = FIRST + dt.timedelta(days=6, hours=5, minutes=45)
POSTPONED = round_page(
    8,
    FcoMatch("Alfa", "Delta", kickoff="16/12/2026 20:45"),  # put off to December
    FcoMatch("Beta", "Gamma", kickoff="18/10/2026 15:00"),
)
LATER = round_page(
    20,
    FcoMatch("Gamma", "Alfa", kickoff="16/01/2027 15:00", odds=None, lineups=False),
    FcoMatch("Beta", "Delta", kickoff="16/01/2027 18:00", odds=None, lineups=False),
)
BY_HAND = {"only the locked round": None, "a postponed match": 8, "a later round": 20}


@pytest.mark.parametrize("stored", list(BY_HAND))
def test_at2_no_stored_fixture_holds_it_back(tmp_path: Path, stored: str) -> None:
    here = a_schedule(tmp_path, moving_on(SECOND))
    here.web.routes = {
        **here.web.routes,
        f"{BASE}/probabili-formazioni/8-giornata": POSTPONED,
        f"{BASE}/probabili-formazioni/20-giornata": LATER,
    }
    here.runs(FIRST - 2 * HOUR, FIRST)
    by_hand = BY_HAND[stored]
    if by_hand is not None:  # `fantadamus collect --round N`, an hour after the deadline
        here.clock.now = FIRST + HOUR
        here.log.append(here.collector.collect(by_hand))
    assert here.next_round(FIRST + 2 * HOUR) == (20 if by_hand == 20 else None)
    last = here.log.last_answered(FIRST + 2 * HOUR)
    assert last is not None
    assert "fixtures" not in what_is_due(here.store, here.log, last + DAY - MINUTE)
    assert "fixtures" in what_is_due(here.store, here.log, last + DAY)
    here.run(last + DAY + RUN)
    assert here.next_round(last + DAY + RUN) == 11
