"""P1, P3 and P4 of mvp-alerts: no alert outside the window or without its league, whatever the facts; two
checks on the same facts send at most one alert; a call that changes back is sent again (design C4; R1.3,
R3.3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.alerts import Call, call_of, changes, decide, newest
from fantadamus.engine.constants import ALERT_WINDOW_HOURS
from tests.alerts_data import AT, NAMES, ROLES
from tests.alerts_harness import (
    DEADLINE,
    IN_WINDOW,
    Shown,
    alerts,
    benchable,
    check,
    collect_officials,
)
from tests.lineup_harness import a_round

pytestmark = pytest.mark.anyio
EIGHT_DAYS = 8 * 24 * 60  # minutes


@st.composite
def _calls(draw: st.DrawFn) -> Call:
    squad = sorted(ROLES)
    starters = draw(st.lists(st.sampled_from(squad), unique=True, min_size=1, max_size=11))
    return call_of(
        round=12,
        formation=draw(st.sampled_from(["3-4-3", "4-4-2"])),
        starters=starters,
        bench=draw(st.permutations([player for player in squad if player not in starters])),
        roles=ROLES,
        captain=draw(st.sampled_from(starters)),
        vice=None,
        chances={},
        at=AT,
    )


def _run(calls: list[Call]) -> int:
    """Each call checked in turn, a minute apart, the way `check_alerts` keeps its log: the alerts sent."""
    seen: list[Call] = []
    sent = 0
    for minute, call in enumerate(calls, start=1):
        now = dataclasses.replace(call, at=AT + dt.timedelta(minutes=minute))
        decided = decide(newest(seen), now, saved_at=AT, roles=ROLES, latest={}, names=NAMES)
        if decided.step != "unchanged":
            seen.append(now)
        sent += decided.step == "alert"
    return sent


@given(_calls(), _calls())
def test_p3_one_alert_for_the_same_facts(first: Call, second: Call) -> None:
    assert _run([first, second, second]) == (1 if changes(first, second, ROLES) else 0)


@given(_calls(), _calls())
def test_p4_a_change_back_alerts_again(first: Call, second: Call) -> None:
    assert _run([first, second, first]) == (2 if changes(first, second, ROLES) else 0)


async def test_p1_nothing_outside_the_window(tmp_path: Path) -> None:
    """A run that benched a starter, checked at any time from eight days before the deadline to eight after,
    switched on or off, for the user or for someone with no league: an alert only inside the window, switched
    on, with the league."""
    async with a_round(tmp_path) as here:
        told = (await here.ask())["lineup"]
        benched = benchable(told)["name"]
        report = collect_officials(here, IN_WINDOW, [benched])

        @given(st.integers(-EIGHT_DAYS, EIGHT_DAYS), st.booleans(), st.sampled_from(["user-1", "nobody"]))
        def gates(minutes: int, enabled: bool, user: str) -> None:
            here.clock.now = DEADLINE + dt.timedelta(minutes=minutes)
            before = len(alerts(here).read())
            shown = Shown()
            check(here, report, shown, user=user, enabled=enabled)
            opened = -ALERT_WINDOW_HOURS * 60 <= minutes < 0
            if not (opened and enabled and user == "user-1"):
                assert shown.sent == []
                assert len(alerts(here).read()) == before

        gates()
